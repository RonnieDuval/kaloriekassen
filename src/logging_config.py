"""Logging configuration."""
import logging


def setup_logging(name: str = None) -> logging.Logger:
    """Configure logging with consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    return logging.getLogger(name or __name__)
