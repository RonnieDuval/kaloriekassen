"""Google Health API uploader for exercise data."""
import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

# Google Health API endpoint for exercise data
GOOGLE_HEALTH_EXERCISE_ENDPOINT = "https://health.googleapis.com/v4/users/me/dataTypes/exercise/dataPoints"


class GoogleHealthUploadError(Exception):
    """Exception raised when Google Health API upload fails."""
    pass


def upload_exercise_records(
    access_token: str,
    exercise_data_points: List[Dict[str, Any]],
    batch_size: int = 10,
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Upload exercise records to Google Health API.

    Args:
        access_token: Valid Google OAuth 2.0 access token with
                      https://www.googleapis.com/auth/googlehealth.activity_and_fitness scope
        exercise_data_points: List of DataPoint dicts with "exercise" field populated
        batch_size: Number of records to upload per request (Google Health recommends batching)
        timeout: Request timeout in seconds

    Returns:
        Dictionary with upload results:
        {
            "successful": List[{"date": date, "google_health_id": str}],
            "failed": List[{"date": date, "error": str}],
            "total": int
        }

    Raises:
        GoogleHealthUploadError: If authentication fails or API returns unexpected error
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    results = {
        "successful": [],
        "failed": [],
        "total": len(exercise_data_points)
    }

    # Upload records (can batch or send individually)
    for i, data_point in enumerate(exercise_data_points):
        try:
            logger.info(f"Uploading exercise record {i+1}/{len(exercise_data_points)}")
            
            response = requests.post(
                GOOGLE_HEALTH_EXERCISE_ENDPOINT,
                headers=headers,
                json=data_point,
                timeout=timeout
            )

            # Handle authentication errors
            if response.status_code == 401:
                raise GoogleHealthUploadError(
                    "Invalid access token (401 Unauthorized). Token may be expired."
                )
            elif response.status_code == 403:
                raise GoogleHealthUploadError(
                    "Insufficient permissions (403 Forbidden). "
                    "Ensure token has googlehealth.activity_and_fitness scope."
                )

            # Handle successful responses
            if response.status_code in [200, 201]:
                response_data = response.json()
                data_point_name = response_data.get("name")
                results["successful"].append({
                    "date": extract_date_from_datapoint(data_point),
                    "google_health_id": data_point_name,
                })
                logger.debug(f"Successfully uploaded: {data_point_name}")

            # Handle other errors
            elif response.status_code >= 400:
                error_msg = extract_error_message(response)
                results["failed"].append({
                    "date": extract_date_from_datapoint(data_point),
                    "error": error_msg,
                    "status_code": response.status_code
                })
                logger.warning(f"Upload failed: {error_msg} (HTTP {response.status_code})")
            else:
                logger.warning(f"Unexpected status code: {response.status_code}")

        except requests.exceptions.RequestException as e:
            results["failed"].append({
                "date": extract_date_from_datapoint(data_point),
                "error": f"Network error: {str(e)}"
            })
            logger.error(f"Network error during upload: {str(e)}")

        except Exception as e:
            results["failed"].append({
                "date": extract_date_from_datapoint(data_point),
                "error": f"Unexpected error: {str(e)}"
            })
            logger.error(f"Unexpected error during upload: {str(e)}")

    # Summary logging
    logger.info(
        f"Upload summary: {len(results['successful'])} successful, "
        f"{len(results['failed'])} failed out of {results['total']}"
    )

    return results


def extract_date_from_datapoint(data_point: Dict[str, Any]) -> Optional[str]:
    """Extract date string from a Google Health DataPoint."""
    try:
        start_time = data_point.get("exercise", {}).get("interval", {}).get("startTime", "")
        if start_time:
            # Extract date portion from ISO format (e.g., "2026-05-15" from "2026-05-15T00:00:00+02:00")
            return start_time.split("T")[0]
    except (KeyError, AttributeError, IndexError):
        pass
    return "unknown"


def extract_error_message(response: requests.Response) -> str:
    """Extract human-readable error message from Google Health API response."""
    try:
        error_json = response.json()
        if "error" in error_json:
            error_obj = error_json["error"]
            if isinstance(error_obj, dict):
                return error_obj.get("message", str(error_obj))
            return str(error_obj)
    except (ValueError, KeyError):
        pass
    return response.text or f"HTTP {response.status_code}"


def validate_access_token(access_token: str) -> bool:
    """
    Quick validation of access token by making a test API call.

    Args:
        access_token: Token to validate

    Returns:
        True if token is valid, False otherwise
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        # Use a simple list query (returns empty list but validates auth)
        response = requests.get(
            f"{GOOGLE_HEALTH_EXERCISE_ENDPOINT}?pageSize=1",
            headers=headers,
            timeout=10
        )
        return response.status_code == 200
    except Exception:
        return False
