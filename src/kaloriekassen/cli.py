"""Single command-line entry point."""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="kaloriekassen")
    parser.add_argument("jobs", nargs="+", choices=["intervals", "myfitnesspal", "google-health-export", "google-health-read", "google-health-auth"])
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    for job in args.jobs:
        if job == "intervals":
            from kaloriekassen.services.intervals_ingestion import ingest
            ingest(args.days)
        elif job == "myfitnesspal":
            from kaloriekassen.services.myfitnesspal_ingestion import ingest
            ingest(args.days)
        elif job == "google-health-export":
            from kaloriekassen.services.google_health_export import export
            export()
        elif job == "google-health-auth":
            from kaloriekassen.integrations.google_health.setup import run_oauth_flow
            run_oauth_flow()
        else:
            from kaloriekassen.services.google_health_replication import replicate
            replicate()


if __name__ == "__main__":
    main()
