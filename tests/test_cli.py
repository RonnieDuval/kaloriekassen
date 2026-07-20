import logging
import sys
from types import SimpleNamespace

from kaloriekassen import cli


def test_intervals_are_ingested_before_google_health_export(monkeypatch, caplog):
    calls = []

    def ingest(days):
        calls.append(("intervals", days))
        return 3

    def export():
        calls.append(("google-health-export", None))
        return 2

    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.services.intervals_ingestion",
        SimpleNamespace(ingest=ingest),
    )
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.services.google_health_export",
        SimpleNamespace(export=export),
    )

    with caplog.at_level(logging.INFO):
        cli.run_jobs(["intervals", "google-health-export"], days=7)

    assert calls == [("intervals", 7), ("google-health-export", None)]
    assert "Intervals: stored 3 activities from the last 7 days." in caplog.messages
    assert "Google Health: processed 2 unexported activities." in caplog.messages
