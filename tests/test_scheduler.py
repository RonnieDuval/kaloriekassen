import logging
import sys
from types import SimpleNamespace

import pytest

from kaloriekassen import scheduler


class StopAfterFirstWait:
    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped

    def wait(self, _timeout):
        self.stopped = True
        return True


def test_build_schedule_uses_configured_intervals(monkeypatch):
    monkeypatch.setenv("SYNC_DAYS", "14")
    monkeypatch.setenv("INTERVALS_SYNC_MINUTES", "15")
    monkeypatch.setenv("MFP_SYNC_HOURS", "4")
    monkeypatch.setenv("GOOGLE_HEALTH_READ_HOURS", "8")
    monkeypatch.setenv("GOOGLE_HEALTH_DAILY_HOURS", "9")
    monkeypatch.setenv("WITHINGS_SYNC_HOURS", "10")

    jobs = scheduler.build_schedule()

    assert [(job.name, job.interval_seconds) for job in jobs] == [
        ("intervals-and-google-health-export", 15 * 60),
        ("myfitnesspal", 4 * 3600),
        ("google-health-read", 8 * 3600),
        ("google-health-daily", 9 * 3600),
        ("withings", 10 * 3600),
    ]


def test_activity_job_ingests_before_export(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.intervals.sync",
        SimpleNamespace(ingest=lambda days: calls.append(("intervals", days)) or 1),
    )
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.google_health.export",
        SimpleNamespace(export=lambda days: calls.append(("export", days)) or 1),
    )

    scheduler._run_activity_sync(7)

    assert calls == [("intervals", 7), ("export", 7)]


def test_scheduler_runs_jobs_sequentially_and_continues_after_failure(
    monkeypatch, caplog
):
    calls = []

    def fail():
        calls.append("failed")
        raise RuntimeError("temporary failure")

    jobs = [
        scheduler.ScheduledJob("first", 60, lambda: calls.append("first")),
        scheduler.ScheduledJob("failing", 60, fail),
        scheduler.ScheduledJob("last", 60, lambda: calls.append("last")),
    ]
    monkeypatch.setattr(scheduler, "build_schedule", lambda _days: jobs)

    with caplog.at_level(logging.ERROR):
        scheduler.run_forever(
            stop_event=StopAfterFirstWait(),
            monotonic=lambda: 100.0,
        )

    assert calls == ["first", "failed", "last"]
    assert "Scheduled job failing failed." in caplog.messages


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_scheduler_rejects_invalid_intervals(monkeypatch, value):
    monkeypatch.setenv("INTERVALS_SYNC_MINUTES", value)

    with pytest.raises(ValueError, match="positive integer"):
        scheduler.build_schedule()
