# geolocation.py
# ------------------------------------------------------------
# This module performs address → geographic coordinate resolution
# using the Google Geocoding API.
#
# It:
#   - loads environment variables (including Google API key)
#   - calls Google Geocoding API with user input
#   - validates the response and extracts coordinates
#   - raises a clean custom GeocodingError on failure
# ------------------------------------------------------------

import os                    # For reading environment variables
from typing import Tuple     # For returning (lat, lon, formatted_address)
from dotenv import load_dotenv  # For loading .env file automatically
import requests              # For making HTTP requests to Google API

load_dotenv()  # Load variables from .env into environment on import

# Read API key from OS environment (after load_dotenv)
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

# Base URL for the Google Geocoding API
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


class GeocodingError(Exception):
    """Custom exception for geocoding-related failures."""
    pass  # No extra behavior needed—just used to signal specific error type


def geocode_address(address: str) -> Tuple[float, float, str]:
    """
    Convert a user-entered address (street, city, ZIP code, etc.)
    into geographic coordinates using the Google Geocoding API.

    Args:
        address (str): A free-form address entered by the user.

    Returns:
        Tuple(lat, lon, formatted_address):
            lat (float): Latitude
            lon (float): Longitude
            formatted_address (str): Google’s normalized version of the address

    Raises:
        GeocodingError:
            - If the API key is missing
            - If the API request fails
            - If Google returns an error or NO results
    """

    # ------------------------------------------------------------
    # Ensure the Google API key exists before calling the API
    # ------------------------------------------------------------
    if not GOOGLE_MAPS_API_KEY:
        raise GeocodingError(
            "GOOGLE_MAPS_API_KEY is not set. Please export your key as an environment variable."
        )

    # ------------------------------------------------------------
    # Build request parameters for the Google Geocoding API
    # ------------------------------------------------------------
    params = {
        "address": address,                 # Address text the user typed
        "key": GOOGLE_MAPS_API_KEY,        # API key for authentication
    }

    # ------------------------------------------------------------
    # Make HTTP GET request to Google Geocoding API
    # ------------------------------------------------------------
    resp = requests.get(GEOCODE_URL, params=params, timeout=10)

    # If Google returns a non-200 HTTP status, treat as an error
    if resp.status_code != 200:
        raise GeocodingError(f"HTTP error from Geocoding API: {resp.status_code}")

    # Parse JSON from the response body
    data = resp.json()

    # Check the Google-specific "status" field
    status = data.get("status")
    if status != "OK":
        # Google sometimes provides an "error_message" explaining the issue
        msg = data.get("error_message") or status
        raise GeocodingError(f"Geocoding failed: {msg}")

    # ------------------------------------------------------------
    # Extract the first result from Google's results list
    # ------------------------------------------------------------
    result = data["results"][0]                  # First (best) result from Google
    loc = result["geometry"]["location"]         # Location object inside geometry

    lat = loc["lat"]                             # Extract latitude
    lon = loc["lng"]                             # Extract longitude

    # Google's official, cleaned-up full address
    formatted = result.get("formatted_address", address)

    # Return the geocoded coordinates and formatted address
    return lat, lon, formatted
