"""Operational tracking for synchronization runs and date coverage."""

from __future__ import annotations

import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from kaloriekassen.db import execute, get_db_connection


RUN_STATUSES = {"running", "success", "partial", "failed"}
COVERAGE_STATUSES = {"complete_data", "complete_empty", "failed"}
SECRET_ENV_VARS = (
    "INTERVALS_API_KEY",
    "MFP_COOKIE_HEADER",
    "GOOGLE_ACCESS_TOKEN",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def requested_date_range(days_back: int) -> tuple[date, date]:
    if days_back < 1:
        raise ValueError("days_back must be at least 1")
    end = date.today()
    return end - timedelta(days=days_back - 1), end


def _safe_error_message(error: BaseException) -> str:
    """Return a bounded error message with known secrets and headers removed."""
    message = str(error)
    for variable in SECRET_ENV_VARS:
        secret = os.getenv(variable)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(
        r"(?i)(authorization|cookie|api[_-]?key|access[_-]?token)\s*[:=]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        message,
    )
    return message[:1000]


def start_sync_run(
    job: str,
    source: str,
    requested_from: date | str | None = None,
    requested_to: date | str | None = None,
) -> str:
    run_id = str(uuid.uuid4())
    with get_db_connection() as connection:
        execute(
            connection,
            """INSERT INTO sync_runs
               (run_id, job, source, requested_from, requested_to, status, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', ?)""",
            (
                run_id,
                job,
                source,
                str(requested_from) if requested_from is not None else None,
                str(requested_to) if requested_to is not None else None,
                utc_now(),
            ),
        )
    return run_id


def finish_sync_run(
    run_id: str,
    status: str,
    fetched_count: int = 0,
    stored_count: int = 0,
    error: BaseException | None = None,
) -> None:
    if status not in RUN_STATUSES - {"running"}:
        raise ValueError(f"Invalid completed sync status: {status}")
    with get_db_connection() as connection:
        execute(
            connection,
            """UPDATE sync_runs SET status = ?, fetched_count = ?, stored_count = ?,
               completed_at = ?, error_type = ?, error_message = ?
               WHERE run_id = ?""",
            (
                status,
                fetched_count,
                stored_count,
                utc_now(),
                type(error).__name__ if error is not None else None,
                _safe_error_message(error) if error is not None else None,
                run_id,
            ),
        )


def record_coverage(
    connection: Any,
    source: str,
    day: date | str,
    status: str,
    record_count: int,
    run_id: str,
) -> None:
    if status not in COVERAGE_STATUSES:
        raise ValueError(f"Invalid coverage status: {status}")
    successful_run_id = run_id if status != "failed" else None
    execute(
        connection,
        """INSERT INTO sync_coverage
           (source, date, status, record_count, last_successful_run_id, checked_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(source, date) DO UPDATE SET
           status=excluded.status, record_count=excluded.record_count,
           last_successful_run_id=COALESCE(
               excluded.last_successful_run_id,
               sync_coverage.last_successful_run_id
           ), checked_at=excluded.checked_at""",
        (source, str(day), status, record_count, successful_run_id, utc_now()),
    )


def get_sync_status() -> list[dict[str, Any]]:
    """Return the latest run and current coverage health for every job."""
    with get_db_connection() as connection:
        rows = execute(
            connection,
            """WITH ranked AS (
                   SELECT run_id, job, source, status, requested_from, requested_to,
                          fetched_count, stored_count, started_at, completed_at,
                          error_type, error_message,
                          ROW_NUMBER() OVER (PARTITION BY job ORDER BY started_at DESC) AS rank
                   FROM sync_runs
               )
               SELECT r.run_id, r.job, r.source, r.status, r.requested_from,
                      r.requested_to, r.fetched_count, r.stored_count, r.started_at,
                      r.completed_at, r.error_type, r.error_message,
                      (SELECT MAX(s.completed_at) FROM sync_runs s
                       WHERE s.job = r.job AND s.status = 'success'),
                      (SELECT MAX(c.date) FROM sync_coverage c
                       WHERE c.source = r.source
                         AND c.status IN ('complete_data', 'complete_empty')),
                      (SELECT COUNT(*) FROM sync_coverage c
                       WHERE c.source = r.source AND c.status = 'failed')
               FROM ranked r WHERE r.rank = 1 ORDER BY r.job""",
        ).fetchall()

    keys = (
        "run_id", "job", "source", "status", "requested_from", "requested_to",
        "fetched_count", "stored_count", "started_at", "completed_at",
        "error_type", "error_message", "last_success_at", "covered_through",
        "failed_days",
    )
    return [dict(zip(keys, row)) for row in rows]


def _freshness(completed_at: str | None) -> str:
    if not completed_at:
        return "ukendt"
    completed = datetime.fromisoformat(completed_at)
    age = datetime.now(timezone.utc) - completed.astimezone(timezone.utc)
    if age <= timedelta(days=1):
        return "frisk"
    if age <= timedelta(days=3):
        return "forsinket"
    return "forældet"


def format_status_report() -> str:
    rows = get_sync_status()
    if not rows:
        return "Der er endnu ikke registreret nogen sync-kørsler."

    sections: list[str] = []
    for row in rows:
        sections.extend(
            [
                f"{row['job']} ({row['source']})",
                f"  Status: {row['status']}",
                f"  Datafriskhed: {_freshness(row['last_success_at'])}",
                f"  Seneste afslutning: {row['completed_at'] or '-'}",
                f"  Seneste succes: {row['last_success_at'] or '-'}",
                f"  Hentet/gemt: {row['fetched_count']}/{row['stored_count']}",
                f"  Dækning til og med: {row['covered_through'] or '-'}",
                f"  Fejlede dage: {row['failed_days']}",
            ]
        )
        if row["error_type"]:
            sections.append(f"  Seneste fejl: {row['error_type']}: {row['error_message']}")
        sections.append("")
    return "\n".join(sections).rstrip()
