"""Long-running, single-process scheduler for private NAS deployments."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    interval_seconds: int
    action: Callable[[], None]


def _positive_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer") from error
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _run_activity_sync(days: int) -> None:
    from kaloriekassen.google_health.export import export
    from kaloriekassen.intervals.sync import ingest

    stored = ingest(days)
    logger.info("Intervals scheduler: stored %d activities.", stored)
    exported = export(days)
    logger.info("Google Health scheduler: processed %d exports.", exported)


def _run_myfitnesspal_sync(days: int) -> None:
    from kaloriekassen.myfitnesspal.sync import ingest

    stored = ingest(days)
    logger.info("MyFitnessPal scheduler: stored %d diary days.", stored)


def _run_google_health_read(days: int) -> None:
    from kaloriekassen.google_health.replication import replicate

    stored = replicate(days)
    logger.info("Google Health scheduler: replicated %d records.", stored)


def _run_google_health_daily(days: int) -> None:
    from kaloriekassen.google_health.daily_replication import replicate_daily

    stored = replicate_daily(days)
    logger.info("Google Health scheduler: stored %d daily summaries.", stored)


def _run_google_health_today() -> None:
    from kaloriekassen.google_health.daily_replication import replicate_today

    stored = replicate_today()
    logger.info("Google Health scheduler: stored %d provisional daily summaries.", stored)


def _run_withings_sync(days: int) -> None:
    from kaloriekassen.withings.sync import ingest

    stored = ingest(days)
    logger.info("Withings scheduler: stored %d measurement groups.", stored)


def build_schedule(fallback_days: int = 7) -> list[ScheduledJob]:
    days = _positive_int_env("SYNC_DAYS", fallback_days)
    activity_minutes = _positive_int_env("INTERVALS_SYNC_MINUTES", 30)
    mfp_hours = _positive_int_env("MFP_SYNC_HOURS", 3)
    google_read_hours = _positive_int_env("GOOGLE_HEALTH_READ_HOURS", 6)
    google_daily_hours = _positive_int_env("GOOGLE_HEALTH_DAILY_HOURS", 6)
    google_today_minutes = _positive_int_env("GOOGLE_HEALTH_TODAY_MINUTES", 15)
    withings_hours = _positive_int_env("WITHINGS_SYNC_HOURS", 6)
    return [
        ScheduledJob(
            "intervals-and-google-health-export",
            activity_minutes * 60,
            lambda: _run_activity_sync(days),
        ),
        ScheduledJob(
            "myfitnesspal",
            mfp_hours * 3600,
            lambda: _run_myfitnesspal_sync(days),
        ),
        ScheduledJob(
            "google-health-read",
            google_read_hours * 3600,
            lambda: _run_google_health_read(days),
        ),
        ScheduledJob(
            "google-health-daily",
            google_daily_hours * 3600,
            lambda: _run_google_health_daily(days),
        ),
        ScheduledJob(
            "google-health-today",
            google_today_minutes * 60,
            _run_google_health_today,
        ),
        ScheduledJob(
            "withings",
            withings_hours * 3600,
            lambda: _run_withings_sync(days),
        ),
    ]


def run_forever(
    fallback_days: int = 7,
    *,
    stop_event: threading.Event | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Run all jobs immediately, then repeat each at its configured interval."""
    jobs = build_schedule(fallback_days)
    stop = stop_event or threading.Event()
    next_runs = {job.name: monotonic() for job in jobs}
    logger.info(
        "Scheduler started with jobs: %s.",
        ", ".join(job.name for job in jobs),
    )

    while not stop.is_set():
        now = monotonic()
        for job in jobs:
            if now < next_runs[job.name]:
                continue
            logger.info("Starting scheduled job %s.", job.name)
            try:
                job.action()
            except Exception:
                logger.exception("Scheduled job %s failed.", job.name)
            finally:
                next_runs[job.name] = monotonic() + job.interval_seconds

        wait_seconds = max(0.0, min(next_runs.values()) - monotonic())
        stop.wait(min(wait_seconds, 60.0))
