# models.py
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Vitals:
    """
    Optional vital signs provided by the user.
    These may influence triage severity.
    """
    temperature_c: Optional[float] = None
    pain_score: Optional[int] = None
    pregnant: Optional[bool] = None
    trauma: Optional[bool] = None


@dataclass
class SymptomInput:
    """
    Combined user symptom description and optional vitals.
    This is the full input passed into the triage model.
    """
    text: str
    vitals: Vitals


@dataclass
class TriageDecision:
    """
    Result from the AI triage system.

    urgency_level:
        "HOME", "CLINIC", "URGENT", or "ER"

    score:
        1–4 numeric value tied to severity logic (if needed)

    explanation:
        Natural language explanation from the model.

    red_flags:
        List of triggered clinical red flags (if any).
    """
    urgency_level: str
    score: int
    explanation: str
    red_flags: List[str]


@dataclass
class Facility:
    """
    Basic information about a healthcare facility.
    Returned by Google Places and enriched for UI display.
    """
    name: str
    type: str          # e.g., "CLINIC", "URGENT", "ER"
    lat: float
    lon: float
    address: str
    phone: str


@dataclass
class FacilityRecommendation:
    """
    A facility plus distance and Google Maps deep link.
    One recommendation corresponds to one result in the UI.
    """
    facility: Facility
    distance_km: float
    maps_url: str


@dataclass
class HistoryRecord:
    """
    A single entry in the user's triage history.

    timestamp:
        Stored as UTC datetime.

    symptoms_text:
        The user's original symptom description.

    urgency_level:
        The triage recommendation level.

    facility_names:
        Names of facilities recommended at that time.
    """
    timestamp: datetime
    symptoms_text: str
    urgency_level: str
    facility_names: List[str]
