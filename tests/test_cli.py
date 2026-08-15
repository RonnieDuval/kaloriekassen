import logging
import sys
from types import SimpleNamespace

from kaloriekassen import cli


def test_intervals_are_ingested_before_google_health_export(monkeypatch, caplog):
    calls = []

    def ingest(days):
        calls.append(("intervals", days))
        return 3

    def export(days):
        calls.append(("google-health-export", days))
        return 2

    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.intervals.sync",
        SimpleNamespace(ingest=ingest),
    )
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.google_health.export",
        SimpleNamespace(export=export),
    )

    with caplog.at_level(logging.INFO):
        cli.run_jobs(["intervals", "google-health-export"], days=7)

    assert calls == [("intervals", 7), ("google-health-export", 7)]
    assert "Intervals: stored 3 activities from the last 7 days." in caplog.messages
    assert "Google Health: processed 2 unexported activities." in caplog.messages


def test_status_reports_when_no_sync_runs_exist(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "status.db"))

    cli.run_jobs(["status"], days=7)

    assert capsys.readouterr().out.strip() == (
        "Der er endnu ikke registreret nogen sync-kørsler."
    )


def test_google_health_daily_receives_days(monkeypatch, caplog):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.google_health.daily_replication",
        SimpleNamespace(replicate_daily=lambda days: calls.append(days) or 7),
    )

    with caplog.at_level(logging.INFO):
        cli.run_jobs(["google-health-daily"], days=14)

    assert calls == [14]
    assert (
        "Google Health: stored 7 completed daily activity summaries."
        in caplog.messages
    )


def test_withings_receives_days(monkeypatch, caplog):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.withings.sync",
        SimpleNamespace(ingest=lambda days: calls.append(days) or 2),
    )

    with caplog.at_level(logging.INFO):
        cli.run_jobs(["withings"], days=730)

    assert calls == [730]
    assert "Withings: stored 2 measurement groups." in caplog.messages
