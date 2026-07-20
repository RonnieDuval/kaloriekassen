"""Single command-line entry point."""
import argparse
import logging
from collections.abc import Sequence


logger = logging.getLogger(__name__)


def run_jobs(jobs: Sequence[str], days: int) -> None:
    """Run jobs in the order provided and report their completed work."""
    for job in jobs:
        if job == "intervals":
            from kaloriekassen.services.intervals_ingestion import ingest

            stored = ingest(days)
            logger.info("Intervals: stored %d activities from the last %d days.", stored, days)
        elif job == "myfitnesspal":
            from kaloriekassen.services.myfitnesspal_ingestion import ingest

            stored = ingest(days)
            logger.info("MyFitnessPal: stored %d diary days.", stored)
        elif job == "google-health-export":
            from kaloriekassen.services.google_health_export import export

            attempted = export()
            logger.info("Google Health: processed %d unexported activities.", attempted)
        elif job == "google-health-auth":
            from kaloriekassen.integrations.google_health.setup import run_oauth_flow

            run_oauth_flow()
            logger.info("Google Health: OAuth authorization completed.")
        else:
            from kaloriekassen.services.google_health_replication import replicate

            replicated = replicate()
            logger.info("Google Health: replicated %d exercise records.", replicated)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kaloriekassen")
    parser.add_argument("jobs", nargs="+", choices=["intervals", "myfitnesspal", "google-health-export", "google-health-read", "google-health-auth"])
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_jobs(args.jobs, args.days)


if __name__ == "__main__":
    main()
