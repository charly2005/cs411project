# history.py
import json
from datetime import datetime
from pathlib import Path
from typing import List

from models import HistoryRecord, TriageDecision

# Local JSON file used to store past triage results
HISTORY_FILE = Path(__file__).parent / "history.json"

# Maximum number of history entries to retain
MAX_RECORDS = 20


def load_history() -> List[HistoryRecord]:
    """
    Load stored triage history from history.json.

    Returns:
        List of HistoryRecord objects (possibly empty).
    """
    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open(encoding="utf-8") as f:
        data = json.load(f)

    records: List[HistoryRecord] = []
    for item in data:
        records.append(HistoryRecord(
            timestamp=datetime.fromisoformat(item["timestamp"]),
            symptoms_text=item["symptoms_text"],
            urgency_level=item["urgency_level"],
            facility_names=item["facility_names"],
        ))
    return records


def save_history(records: List[HistoryRecord]) -> None:
    """
    Save a list of HistoryRecord objects into history.json
    using a compact, readable JSON structure.
    """
    data = [
        {
            "timestamp": r.timestamp.isoformat(),
            "symptoms_text": r.symptoms_text,
            "urgency_level": r.urgency_level,
            "facility_names": r.facility_names,
        }
        for r in records
    ]

    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def append_record(symptoms_text: str, decision: TriageDecision, facility_names: List[str]) -> None:
    """
    Add a new triage history entry at the top of the list.

    - Uses UTC timestamp for consistency.
    - Keeps only the most recent MAX_RECORDS entries.
    - Saves back to history.json.
    """
    records = load_history()

    # Insert new record at the beginning (most recent first)
    records.insert(0, HistoryRecord(
        timestamp=datetime.utcnow(),
        symptoms_text=symptoms_text,
        urgency_level=decision.urgency_level,
        facility_names=facility_names,
    ))

    # Trim history to fixed size
    records = records[:MAX_RECORDS]

    save_history(records)
