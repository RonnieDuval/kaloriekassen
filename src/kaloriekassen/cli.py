"""Single command-line entry point."""
import argparse
import logging
from collections.abc import Sequence
from datetime import date

from dotenv import load_dotenv


logger = logging.getLogger(__name__)


def run_jobs(
    jobs: Sequence[str],
    days: int,
    mfp_from: date | None = None,
    mfp_to: date | None = None,
) -> None:
    """Run jobs in the order provided and report their completed work."""
    for job in jobs:
        match job:
            case "intervals":
                from kaloriekassen.intervals.sync import ingest
                stored = ingest(days)
                logger.info("Intervals: stored %d activities from the last %d days.", stored, days)

            case "myfitnesspal":
                from kaloriekassen.myfitnesspal.sync import ingest, ingest_range
                stored = (
                    ingest_range(mfp_from, mfp_to)
                    if mfp_from is not None and mfp_to is not None
                    else ingest(days)
                )
                logger.info("MyFitnessPal: stored %d diary days.", stored)

            case "google-health-export":
                from kaloriekassen.google_health.export import export
                attempted = export(days)
                logger.info("Google Health: processed %d unexported activities.", attempted)

            case "google-health-auth":
                from kaloriekassen.google_health.auth import (
                    _client_secrets_path,
                    _token_store_path,
                )
                from kaloriekassen.google_health.setup import run_oauth_flow
                from kaloriekassen.oauth_upload import upload_oauth_artifacts
                run_oauth_flow()
                upload_oauth_artifacts(
                    [_client_secrets_path(), _token_store_path()],
                    remove_after_upload=[_token_store_path()],
                )
                logger.info("Google Health: OAuth completed.")

            case "google-health-read":
                from kaloriekassen.google_health.replication import replicate
                replicated = replicate(days)
                logger.info("Google Health: replicated %d records.", replicated)

            case "google-health-daily":
                from kaloriekassen.google_health.daily_replication import replicate_daily
                replicated = replicate_daily(days)
                logger.info(
                    "Google Health: stored %d completed daily activity summaries.",
                    replicated,
                )

            case "google-health-today":
                from kaloriekassen.google_health.daily_replication import replicate_today
                replicated = replicate_today()
                logger.info(
                    "Google Health: stored %d provisional daily activity summaries.",
                    replicated,
                )

            case "google-health-heart-rate-backfill":
                from kaloriekassen.google_health.heart_rate_backfill import (
                    backfill_average_heart_rate,
                )
                updated = backfill_average_heart_rate(days)
                logger.info(
                    "Google Health: updated %d exercises with average heart rate.",
                    updated,
                )

            case "withings-auth":
                from kaloriekassen.oauth_upload import upload_oauth_artifacts
                from kaloriekassen.withings.auth import (
                    _client_secrets_path,
                    _token_store_path,
                )
                from kaloriekassen.withings.setup import run_oauth_flow
                run_oauth_flow()
                upload_oauth_artifacts(
                    [_client_secrets_path(), _token_store_path()],
                    remove_after_upload=[_token_store_path()],
                )
                logger.info("Withings: OAuth completed.")

            case "withings":
                from kaloriekassen.withings.sync import ingest
                stored = ingest(days)
                logger.info("Withings: stored %d measurement groups.", stored)

            case "status":
                from kaloriekassen.sync_tracking import format_status_report
                print(format_status_report())

            case "scheduler":
                from kaloriekassen.scheduler import run_forever
                run_forever(fallback_days=days)

            case _:
                # Wildcard: fanger alt, der ikke matchede de andre cases
                raise ValueError(f"Ukendt job modtaget: {job}")


def main(argv: Sequence[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="kaloriekassen")
    parser.add_argument(
        "jobs",
        nargs="+",
        choices=[
            "intervals",
            "myfitnesspal",
            "google-health-export",
            "google-health-read",
            "google-health-daily",
            "google-health-today",
            "google-health-auth",
            "google-health-heart-rate-backfill",
            "withings-auth",
            "withings",
            "status",
            "scheduler",
        ],
    )
    parser.add_argument("--days", type=int)
    parser.add_argument(
        "--from",
        dest="mfp_from",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="First MyFitnessPal diary date to ingest (inclusive).",
    )
    parser.add_argument(
        "--to",
        dest="mfp_to",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Last MyFitnessPal diary date to ingest (inclusive).",
    )
    args = parser.parse_args(argv)
    has_mfp_range = args.mfp_from is not None or args.mfp_to is not None
    if has_mfp_range and (args.mfp_from is None or args.mfp_to is None):
        parser.error("--from and --to must be provided together")
    if has_mfp_range and args.jobs != ["myfitnesspal"]:
        parser.error("--from and --to can only be used with the myfitnesspal job")
    if has_mfp_range and args.days is not None:
        parser.error("--days cannot be combined with --from and --to")
    if has_mfp_range and args.mfp_from > args.mfp_to:
        parser.error("--from must be on or before --to")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_jobs(args.jobs, args.days if args.days is not None else 7, args.mfp_from, args.mfp_to)


if __name__ == "__main__":
    main()
