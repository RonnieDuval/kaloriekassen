import logging
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from kaloriekassen import cli


def test_myfitnesspal_specific_dates_use_range_ingestion(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.myfitnesspal.sync",
        SimpleNamespace(
            ingest=lambda days: calls.append(("days", days)) or 1,
            ingest_range=lambda start, end: calls.append((start, end)) or 2,
        ),
    )

    cli.run_jobs(
        ["myfitnesspal"],
        days=7,
        mfp_from=date(2026, 8, 1),
        mfp_to=date(2026, 8, 10),
    )

    assert calls == [(date(2026, 8, 1), date(2026, 8, 10))]


def test_myfitnesspal_cli_parses_specific_dates(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_jobs", lambda *args: calls.append(args))

    cli.main(["myfitnesspal", "--from", "2026-08-01", "--to", "2026-08-10"])

    assert calls == [
        (["myfitnesspal"], 7, date(2026, 8, 1), date(2026, 8, 10))
    ]


def test_myfitnesspal_cli_rejects_incomplete_range():
    try:
        cli.main(["myfitnesspal", "--from", "2026-08-01"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("Expected argparse to reject an incomplete date range")


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


def test_google_health_today_runs_provisional_sync(monkeypatch, caplog):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.google_health.daily_replication",
        SimpleNamespace(replicate_today=lambda: calls.append("today") or 1),
    )

    with caplog.at_level(logging.INFO):
        cli.run_jobs(["google-health-today"], days=7)

    assert calls == ["today"]
    assert (
        "Google Health: stored 1 provisional daily activity summaries."
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


def test_withings_auth_uploads_client_and_token_after_oauth(monkeypatch):
    calls = []
    client_path = Path("secrets/withings-client.json")
    token_path = Path("secrets/withings-token.json")
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.withings.setup",
        SimpleNamespace(run_oauth_flow=lambda: calls.append("oauth")),
    )
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.withings.auth",
        SimpleNamespace(
            _client_secrets_path=lambda: client_path,
            _token_store_path=lambda: token_path,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "kaloriekassen.oauth_upload",
        SimpleNamespace(
            upload_oauth_artifacts=lambda paths, remove_after_upload: calls.append(
                (paths, remove_after_upload)
            )
        ),
    )

    cli.run_jobs(["withings-auth"], days=7)

    assert calls == ["oauth", ([client_path, token_path], [token_path])]
