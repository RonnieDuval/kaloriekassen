from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
# import googleapiclient.discovery
import settings

def get_credentials(refresh_token: str) -> Credentials:
    # Du gemmer dine credentials i et objekt
    creds = Credentials(
        token=None, # Vi starter uden access_token
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    # Denne linje er magisk: Den tjekker om token er gyldig, 
    # og hvis ikke, så refresher den den automatisk!
    if not creds.valid:
        creds.refresh(Request())
    
    return creds
breakpoint()
# Nu kan du bare bruge 'creds.token' uden at tænke på tid eller udløb.

# denne er den professionelle måde at gøre det på, da den håndterer alt det kedelige for dig.