import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App-wide OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Local Level-1 storage location for refresh token
GOOGLE_TOKEN_STORE_PATH = os.getenv('GOOGLE_TOKEN_STORE_PATH', 'secrets/google_oauth_token.json')
