"""Fitbit sync entry point."""
from src.logging_config import setup_logging
from src.syncs.fitbit import FitbitSync

logger = setup_logging(__name__)


def main() -> None:
    """Run Fitbit sync."""
    sync = FitbitSync()
    sync.run()


if __name__ == "__main__":
    main()
