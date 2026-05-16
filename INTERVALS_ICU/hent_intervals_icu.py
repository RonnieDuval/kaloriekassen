from io import BytesIO

import requests

import settings

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None


def fetch_intervals_activities(athlete_id=None, api_key=None):
    if athlete_id is None:
        athlete_id = getattr(settings, "INTERVALS_ATHLETE_ID", None)
    if api_key is None:
        api_key = getattr(settings, "INTERVALS_API_KEY", None)

    if not athlete_id or not api_key:
        raise ValueError("INTERVALS_ATHLETE_ID and INTERVALS_API_KEY must be set")

    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities.csv"
    response = requests.get(url, auth=("API_KEY", api_key), timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Fejl: {response.status_code} - {response.text}")

    if pd is None:
        raise ImportError("pandas is required to parse CSV response")

    return pd.read_csv(BytesIO(response.content))


def main():
    try:
        df = fetch_intervals_activities()
        print("Aktiviteter hentet!")
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nKolonner: {df.columns.tolist()}")
        print("\nFørste rækker:")
        print(df.head())
    except Exception as exc:
        print(str(exc))


if __name__ == "__main__":
    main()
