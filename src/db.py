"""Database utilities and connection management."""
import logging
import os

import psycopg2

try:
    from dotenv import load_dotenv
except ImportError:  # Optional in test/minimal environments
    def load_dotenv():
        return None

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def get_db_connection():
    """Create a PostgreSQL database connection from environment variables."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "kaloriekassen"),
        user=os.getenv("DB_USER", "kalorie"),
        password=os.getenv("DB_PASSWORD", "kalorie"),
    )
