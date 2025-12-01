# history.py
# ------------------------------------------------------------
# This module handles persistent storage of triage history.
# It:
#   - saves triage records to a local history.json file
#   - loads them back as HistoryRecord objects
#   - adds new records (with timestamp) and trims old ones
# ------------------------------------------------------------

import json                      # For reading/writing JSON files
from datetime import datetime     # For timestamps on history records
from pathlib import Path          # For cleaner file path handling
from typing import List           # For type hinting lists of HistoryRecord objects

from models import HistoryRecord, TriageDecision
# HistoryRecord: dataclass storing timestamp, symptoms text, urgency, facility names
# TriageDecision: contains urgency_level and other triage details


# ------------------------------------------------------------
# Path to the local JSON file storing history data.
# It lives in the same directory as this Python module.
# ------------------------------------------------------------
HISTORY_FILE = Path(__file__).parent / "history.json"

# Maximum number of triage history entries to keep.
MAX_RECORDS = 20


def load_history() -> List[HistoryRecord]:
    """
    Load stored triage history from history.json.

    Returns:
        A list of HistoryRecord objects.
        Returns an empty list if no history file exists.
    """

    # If the history file does not exist yet, return empty list
    if not HISTORY_FILE.exists():
        return []

    # Open and read JSON data from disk
    with HISTORY_FILE.open(encoding="utf-8") as f:
        data = json.load(f)

    # Parse each JSON item into a HistoryRecord instance
    records: List[HistoryRecord] = []
    for item in data:
        records.append(
            HistoryRecord(
                timestamp=datetime.fromisoformat(item["timestamp"]),  # convert ISO string → datetime
                symptoms_text=item["symptoms_text"],                 # stored symptom description
                urgency_level=item["urgency_level"],                 # stored urgency level (string)
                facility_names=item["facility_names"],               # list of facility names
            )
        )

    return records  # Return the list of parsed HistoryRecord objects


def save_history(records: List[HistoryRecord]) -> None:
    """
    Save a list of HistoryRecord objects into history.json.
    Uses a compact but readable JSON format with indent=2.
    """

    # Convert each HistoryRecord to a dict suitable for JSON serialization
    data = [
        {
            "timestamp": r.timestamp.isoformat(),  # datetime → ISO 8601 string
            "symptoms_text": r.symptoms_text,
            "urgency_level": r.urgency_level,
            "facility_names": r.facility_names,
        }
        for r in records
    ]

    # Write JSON data to disk (overwriting previous contents)
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)  # Save as readable JSON with indentation


def append_record(
    symptoms_text: str,
    decision: TriageDecision,
    facility_names: List[str]
) -> None:
    """
    Add a new triage record to the history file.

    Behavior:
      - Inserts new record at the top of the list (most recent first)
      - Uses UTC timestamp for consistency
      - Keeps only the most recent MAX_RECORDS entries
      - Immediately writes updated history back to disk
    """

    records = load_history()  # Load existing history list

    # Create a new HistoryRecord and insert it at index 0
    records.insert(
        0,
        HistoryRecord(
            timestamp=datetime.utcnow(),          # store standardized UTC timestamp
            symptoms_text=symptoms_text,          # text user entered
            urgency_level=decision.urgency_level, # urgency classification from triage
            facility_names=facility_names,        # facilities recommended
        )
    )

    # Trim list so it only keeps MAX_RECORDS most recent entries
    records = records[:MAX_RECORDS]

    # Write updated list back to disk
    save_history(records)
