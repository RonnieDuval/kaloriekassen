"""Intervals.icu sync entry point."""
from src.logging_config import setup_logging
from src.syncs.intervals import IntervalsSync

logger = setup_logging(__name__)


def main() -> None:
    """Run Intervals.icu sync."""
    sync = IntervalsSync()
    sync.run()


if __name__ == "__main__":
    main()
