"""MyFitnessPal sync entry point."""
from src.logging_config import setup_logging
from src.syncs.mfp import MFPSync

logger = setup_logging(__name__)


def main() -> None:
    """Run MyFitnessPal sync."""
    sync = MFPSync()
    sync.run()


if __name__ == "__main__":
    main()
