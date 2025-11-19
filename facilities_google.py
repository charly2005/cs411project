# facilities_google.py
import os
import math
from typing import List

import requests

from models import Facility, FacilityRecommendation, TriageDecision

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


def urgency_to_google_query(urgency: str):
    """
    Map our triage urgency level to Google Places search parameters.
    - ER → emergency room
    - URGENT → urgent care
    - CLINIC → doctor/clinic
    - HOME / default → pharmacy
    """
    urgency = urgency.upper()
    if urgency == "ER":
        return {"type": "hospital", "keyword": "emergency room"}
    if urgency == "URGENT":
        return {"type": "hospital", "keyword": "urgent care"}
    if urgency == "CLINIC":
        return {"type": "doctor", "keyword": "clinic"}
    # HOME or any other level → pharmacy
    return {"type": "pharmacy", "keyword": "pharmacy"}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """
    Compute approximate distance between two coordinates using the Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
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
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set.")

    # Determine Google Places query parameters based on urgency
    query = urgency_to_google_query(decision.urgency_level)

    # Build request parameters
    params = {
        "key": GOOGLE_MAPS_API_KEY,
        "location": f"{user_lat},{user_lon}",
        "radius": radius_m,
        "type": query["type"],
    }
    if query.get("keyword"):
        params["keyword"] = query["keyword"]

    # Execute Google Places request
    resp = requests.get(PLACES_URL, params=params, timeout=10)
    if resp.status_code != 200:
        return []

    data = resp.json()
    if data.get("status") != "OK":
        return []

    # Limit to max_results
    results = data.get("results", [])[:max_results]

    recs: List[FacilityRecommendation] = []
    for place in results:
        name = place.get("name", "Unknown place")
        loc = place["geometry"]["location"]
        plat = loc["lat"]
        plon = loc["lng"]

        # 'vicinity' is typical for Nearby Search (formatted_address appears in some cases)
        address = place.get("vicinity") or place.get("formatted_address", "")

        # Nearby Search does not provide phone number
        phone = ""

        # Compute distance
        distance = haversine_km(user_lat, user_lon, plat, plon)

        # Google Maps link
        maps_url = f"https://www.google.com/maps/search/?api=1&query={plat},{plon}"

        fac = Facility(
            name=name,
            type=decision.urgency_level,
            lat=plat,
            lon=plon,
            address=address,
            phone=phone,
        )
        recs.append(FacilityRecommendation(
            facility=fac,
            distance_km=distance,
            maps_url=maps_url,
        ))

    # Sort by distance ascending
    recs.sort(key=lambda r: r.distance_km)
    return recs
