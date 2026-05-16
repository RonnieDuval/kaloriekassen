import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App-wide OAuth configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI')
GOOGLE_AUTH_CODE = os.getenv('GOOGLE_AUTH_CODE')

# Local Level-1 storage location for refresh token
GOOGLE_TOKEN_STORE_PATH = os.getenv('GOOGLE_TOKEN_STORE_PATH', 'secrets/google_oauth_token.json')

INTERVALS_ATHLETE_ID = os.getenv('INTERVALS_ATHLETE_ID')
INTERVALS_API_KEY = os.getenv('INTERVALS_API_KEY')