# geolocation.py
import os
from typing import Tuple

import requests

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodingError(Exception):
    """Custom exception for geocoding-related failures."""
    pass


def geocode_address(address: str) -> Tuple[float, float, str]:
    """
    Convert a user-entered address (street, city, zip code, etc.)
    into geographic coordinates using the Google Geocoding API.

    Returns:
        (latitude, longitude, formatted_address)

    Raises:
        GeocodingError - if the API key is missing or the request fails.
    """
    # Ensure API key is available before making the request
    if not GOOGLE_MAPS_API_KEY:
        raise GeocodingError(
            "GOOGLE_MAPS_API_KEY is not set. Please export your key as an environment variable."
        )

    # Build request parameters
    params = {
        "address": address,
        "key": GOOGLE_MAPS_API_KEY,
    }

    # Make request to Google Geocoding API
    resp = requests.get(GEOCODE_URL, params=params, timeout=10)
    if resp.status_code != 200:
        raise GeocodingError(f"HTTP error from Geocoding API: {resp.status_code}")

    data = resp.json()
    status = data.get("status")
    if status != "OK":
        # Use Google's error message if available
        msg = data.get("error_message") or status
        raise GeocodingError(f"Geocoding failed: {msg}")

    # Extract the first matching result
    result = data["results"][0]
    loc = result["geometry"]["location"]
    lat = loc["lat"]
    lon = loc["lng"]

    # Google's formatted address (cleaned, complete address)
    formatted = result.get("formatted_address", address)

    return lat, lon, formatted
