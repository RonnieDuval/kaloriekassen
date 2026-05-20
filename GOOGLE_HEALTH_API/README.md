# Google Health API Integration

## Overview

This module syncs Intervals.icu workout data to Google Health API as exercise records. It includes:

- **mappers.py** - Convert Intervals data to Google Health Exercise format
- **uploader.py** - POST exercise records to Google Health API
- **sync_adapter.py** - Orchestrates fetch, map, and upload pipeline
- **google_health_access.py** - OAuth credential management (existing)

## Setup

### 1. Authenticate with Google Health API

Run the interactive OAuth setup to get a valid token:

```bash
uv run python GOOGLE_HEALTH_API/setup_google_health.py
```

This will:
- Open Google OAuth login in your browser
- Request `googlehealth.activity_and_fitness` scope
- Save the refresh token to `secrets/google_oauth_token.json`

### 2. Verify Intervals.icu API Credentials

Ensure you have environment variables set:
```bash
INTERVALS_API_KEY=<your_api_key>
INTERVALS_ATHLETE_ID=<your_athlete_id>
```

## Usage

### Manual Sync

Upload last 7 days of Intervals workouts to Google Health:

```bash
# Run Google Health sync individually
uv run python run_sync.py google-health

# Or run with other syncs
uv run python run_sync.py intervals myfitnesspal google-health
```

### Scheduled via Docker

Docker Compose services are configured in `docker-compose.yml` (when needed):

```yaml
sync_google_health:
  build: .
  command: ["python", "run_sync.py", "google-health"]
  depends_on:
    - db
  env_file:
    - .env
  volumes:
    - ./secrets:/app/secrets  # For Google OAuth token
  restart: "no"
```

## Data Mapping

### Exercise Type Conversion

| Intervals.icu | Google Health |
|---|---|
| VirtualRide | BIKING |
| Ride, MountainBike | BIKING |
| Run, Trail | RUNNING |
| Walk | WALKING |
| Hike | HIKING |
| Swim | SWIMMING |
| Yoga | YOGA |
| Strength, WeightTraining | STRENGTH_TRAINING |
| HIIT | HIIT |
| Pilates | PILATES |
| Other | WORKOUT (default) |

### Metric Conversions

```
Distance:   kilometers × 1,000,000 = millimeters
Elevation:  meters × 1,000 = millimeters
Calories:   kilocalories (direct, as provided)
```

### Example Mapping

**Raw Intervals Data:**
```json
{
  "date": "2026-05-15",
  "workout_type": "VirtualRide",
  "calories_out": 746,
  "distance_km": 28.6194,
  "elevation_gain": 436
}
```

**Google Health API DataPoint:**
```json
{
  "exercise": {
    "interval": {
      "startTime": "2026-05-15T00:00:00+02:00",
      "startUtcOffset": "7200s",
      "endTime": "2026-05-15T23:59:59+02:00",
      "endUtcOffset": "7200s"
    },
    "exerciseType": "BIKING",
    "metricsSummary": {
      "caloriesKcal": 746.0,
      "distanceMillimeters": 28619400,
      "elevationGainMillimeters": 436000
    },
    "displayName": "BIKING: 28.6km"
  },
  "dataSource": {
    "application": {"packageName": "com.intervals.icu"},
    "recordingMethod": "ACTIVELY_MEASURED"
  }
}
```

## Error Handling

The uploader handles various error scenarios:

| Error | Status | Action |
|---|---|---|
| Invalid token | 401 Unauthorized | Token refresh recommended |
| Missing scope | 403 Forbidden | Re-run OAuth setup with correct scopes |
| Network error | ConnectionError | Automatic retry on next sync |
| Malformed data | 400 Bad Request | Check mapping logic |

Results include success/failure tracking:

```python
{
  "successful": ["2026-05-15", "2026-05-14"],
  "failed": [{"date": "2026-05-13", "error": "..."}],
  "total": 3
}
```

## Testing

### Test Mappers

```bash
uv run python -c "
from GOOGLE_HEALTH_API.mappers import map_intervals_to_google_exercise
import datetime as dt

test = {
    'date': dt.date(2026, 5, 15),
    'workout_type': 'VirtualRide',
    'calories_out': 746,
    'distance_km': 28.6194,
    'elevation_gain': 436
}
result = map_intervals_to_google_exercise(test)
print(result)
"
```

### Validate Access Token

```bash
uv run python -c "
from GOOGLE_HEALTH_API.uploader import validate_access_token
from GOOGLE_HEALTH_API.google_health_access import get_credentials

creds = get_credentials()
valid = validate_access_token(creds.token)
print('Token valid:', valid)
"
```

## Troubleshooting

### "No refresh token available"
- Run `setup_google_health.py` to authenticate
- Ensure `secrets/google_oauth_token.json` exists

### "Invalid access token (401)"
- Token may have expired
- Re-run `setup_google_health.py` to refresh

### "Insufficient permissions (403)"
- Check that OAuth scope includes `googlehealth.activity_and_fitness`
- Clear `secrets/google_oauth_token.json` and re-authenticate

### "No valid exercise records to upload"
- Check that raw_intervals has rows with non-null `workout_type`
- Empty workouts are filtered out (this is expected)

## References

- [Google Health API Documentation](https://developers.google.com/health)
- [Exercise Data Type Reference](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints#Exercise)
- [OAuth 2.0 Setup Guide](https://developers.google.com/health/get-started)
