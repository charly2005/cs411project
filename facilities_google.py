# ------------------------------------------------------------
# facilities_google.py
#
# This module connects our triage decision to Google Maps Places.
# It:
#   - maps urgency levels to Google Places query types/keywords
#   - calls the Google Places Nearby Search API
#   - computes distances using the Haversine formula
#   - returns a list of FacilityRecommendation objects
# ------------------------------------------------------------

import os        # To read environment variables (API key)
import math      # For trigonometric functions in the Haversine distance
from typing import List  # For type hinting a list of FacilityRecommendation objects

import requests  # HTTP library used to call Google Places API

from models import Facility, FacilityRecommendation, TriageDecision
# Facility: data class representing a medical facility
# FacilityRecommendation: wraps Facility with distance and maps URL
# TriageDecision: contains urgency_level and other triage info


# Read the Google Maps API key from environment variables at import time
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

# Base URL for Google Places Nearby Search API
PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


def urgency_to_google_query(urgency: str):
    """
    Map our triage urgency level to Google Places search parameters.
    - ER → emergency room
    - URGENT → urgent care
    - CLINIC → doctor/clinic
    - HOME / default → pharmacy
    """

    # Normalize urgency string to uppercase for consistent comparison
    urgency = urgency.upper()

    # For emergency cases, search for hospitals with "emergency room" keyword
    if urgency == "ER":
        return {"type": "hospital", "keyword": "emergency room"}

    # For urgent cases, search for hospitals with "urgent care" keyword
    if urgency == "URGENT":
        return {"type": "hospital", "keyword": "urgent care"}

    # For clinic-level cases, search for doctors/clinics
    if urgency == "CLINIC":
        return {"type": "doctor", "keyword": "clinic"}

    # For HOME or any unknown urgency, default to pharmacies
    return {"type": "pharmacy", "keyword": "pharmacy"}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """
    Compute approximate distance between two coordinates using the Haversine formula.
    Returns distance in kilometers.
    """

    # Earth's radius in kilometers (approximate)
    R = 6371.0

    # Convert the first latitude and second latitude from degrees to radians
    phi1, phi2 = math.radians(lat1), math.radians(lat2)

    # Compute the difference in latitude in radians
    dphi = math.radians(lat2 - lat1)

    # Compute the difference in longitude in radians
    dlambda = math.radians(lon2 - lon1)

    # Haversine formula: compute 'a', a component of the great-circle distance
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )

    # 'c' is the angular distance in radians
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Multiply by Earth radius to get the distance in kilometers
    return R * c


def recommend_facilities(
    decision: TriageDecision,
    user_lat: float,
    user_lon: float,
    radius_m: int = 5000,
    max_results: int = 3,
) -> List[FacilityRecommendation]:
    """
    Use Google Places Nearby Search to recommend facilities based on:
    - user's location
    - triage urgency level
    - configurable search radius and result count

    Returns a sorted list of FacilityRecommendation (closest first).
    """

    # Ensure that the Google Maps API key is available; fail early if missing
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    # Determine Google Places query parameters based on the urgency in the decision
    query = urgency_to_google_query(decision.urgency_level)

    # Build query parameters for the Nearby Search API call
    params = {
        "key": GOOGLE_MAPS_API_KEY,               # API key for authentication
        "location": f"{user_lat},{user_lon}",     # User's location as "lat,lon" string
        "radius": radius_m,                       # Search radius in meters
        "type": query["type"],                    # Place type based on urgency (e.g., hospital, doctor, pharmacy)
    }

    # If a keyword was provided by urgency_to_google_query, include it in the request
    if query.get("keyword"):
        params["keyword"] = query["keyword"]

    # Execute HTTP GET request to Google Places Nearby Search API
    resp = requests.get(PLACES_URL, params=params, timeout=10)

    # If the HTTP response code is not 200 (OK), return an empty list (no results)
    if resp.status_code != 200:
        return []

    # Parse JSON body from the HTTP response
    data = resp.json()

    # Google Places uses a "status" field; if it's not "OK", treat as no usable results
    if data.get("status") != "OK":
        return []

    # Extract the "results" array from the response and limit to max_results
    results = data.get("results", [])[:max_results]

    # Initialize our list of FacilityRecommendation objects
    recs: List[FacilityRecommendation] = []

    # Iterate over each place returned by Google
    for place in results:
        # Safely get the place name; default to "Unknown place" if missing
        name = place.get("name", "Unknown place")

        # Extract geometry/location object from the place
        loc = place["geometry"]["location"]

        # Latitude of the facility
        plat = loc["lat"]

        # Longitude of the facility
        plon = loc["lng"]

        # Nearby Search usually returns 'vicinity' for a short address.
        # If 'vicinity' is not available, fall back to 'formatted_address' (if present).
        address = place.get("vicinity") or place.get("formatted_address", "")

        # Nearby Search does not include phone numbers, so we leave this blank
        phone = ""

        # Compute distance from user to facility using the Haversine formula
        distance = haversine_km(user_lat, user_lon, plat, plon)

        # Construct a direct Google Maps search URL using the facility coordinates
        maps_url = f"https://www.google.com/maps/search/?api=1&query={plat},{plon}"

        # Create a Facility data object with relevant information
        fac = Facility(
            name=name,                     # Facility name
            type=decision.urgency_level,   # Store the triage urgency as the facility "type" label
            lat=plat,                      # Facility latitude
            lon=plon,                      # Facility longitude
            address=address,               # Facility address (vicinity or formatted)
            phone=phone,                   # Phone (empty because not provided by this API)
        )

        # Wrap Facility into a FacilityRecommendation including distance and Google Maps URL
        recs.append(
            FacilityRecommendation(
                facility=fac,          # Facility object created above
                distance_km=distance,  # Distance from user in kilometers
                maps_url=maps_url,     # Direct Google Maps URL for this facility
            )
        )

    # Sort recommendations by ascending distance (closest first)
    recs.sort(key=lambda r: r.distance_km)

    # Return the sorted list of FacilityRecommendation objects
    return recs
