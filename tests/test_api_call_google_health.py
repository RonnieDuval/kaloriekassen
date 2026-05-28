import requests

from GOOGLE_HEALTH_API.google_health_access import get_credentials

creds = get_credentials()

response = requests.get(
    "https://health.googleapis.com/v4/users/me/dataTypes/exercise/dataPoints",
    headers={
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json",
    },
    timeout=30,
)

response.raise_for_status()
print(response.json())