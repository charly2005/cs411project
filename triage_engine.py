# triage_engine.py
# ------------------------------------------------------------
# This module connects the CareRoute app to the Gemini API and
# applies a rule-based safety layer on top of the AI result.
#
# It:
#   - loads GEMINI_API_KEY from environment / .env
#   - configures the google.generativeai client
#   - builds a conservative triage prompt
#   - parses JSON output from Gemini safely
#   - applies override rules for critical symptoms (e.g. chest pain)
#   - returns a TriageDecision dataclass used by the UI
# ------------------------------------------------------------

import os                      # For reading environment variables (API key)
import json                    # For parsing JSON returned by Gemini
from typing import List        # For type hinting lists (e.g. red_flags)
from dotenv import load_dotenv # For automatically loading variables from a .env file

import google.generativeai as genai  # Official Gemini Python client

from models import SymptomInput, TriageDecision
# SymptomInput: dataclass bundling symptom text + vitals
# TriageDecision: dataclass representing final triage result


# Load environment variables from .env file into os.environ
load_dotenv()

# ------------------------------------------------------------
# Load Gemini API key from environment
# ------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # Read the GEMINI_API_KEY env var
if not GEMINI_API_KEY:  # If the key is missing or empty
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Please export it as an environment variable."
    )

# Configure the Gemini client with the API key
genai.configure(api_key=GEMINI_API_KEY)

# Name of the Gemini model to use for triage
# (can be changed if you have access to other versions)
MODEL_NAME = "gemini-2.5-flash"


def call_gemini_for_triage(symptoms: SymptomInput) -> dict:
    """
    Call Gemini with a structured prompt and request a JSON-only response.

    The model is instructed to return a JSON object like:

        {
            "score": 1-4,
            "urgency": "HOME" | "CLINIC" | "URGENT" | "ER",
            "explanation": "...",
            "red_flags": [...]
        }

    Returns:
        dict: Parsed JSON structure from Gemini.
    """

    # Create a GenerativeModel instance for the chosen model
    model = genai.GenerativeModel(MODEL_NAME)

    # --------------------------------------------------------
    # Convert vitals to "readable" values for the text prompt.
    # If a vital is missing, use "unknown" instead of None.
    # --------------------------------------------------------
    temp_str = (
        "unknown"
        if symptoms.vitals.temperature_c is None
        else symptoms.vitals.temperature_c
    )
    pain_str = (
        "unknown"
        if symptoms.vitals.pain_score is None
        else symptoms.vitals.pain_score
    )
    preg_str = (
        "unknown"
        if symptoms.vitals.pregnant is None
        else symptoms.vitals.pregnant
    )
    trauma_str = (
        "unknown"
        if symptoms.vitals.trauma is None
        else symptoms.vitals.trauma
    )

    # --------------------------------------------------------
    # Prompt: conservative triage instructions for Gemini
    # --------------------------------------------------------
    prompt = f"""
You are a conservative medical triage assistant.

The user is describing their symptoms. You must assign an urgency level and briefly explain why.
ALWAYS choose a higher urgency level if there is any uncertainty.

Input:
- Symptoms (free text): {symptoms.text}
- Temperature (C): {temp_str}
- Pain score (0-10): {pain_str}
- Pregnant: {preg_str}
- Recent trauma: {trauma_str}

Output:
Return ONLY a JSON object with exactly:
- "score": integer 1-4
- "urgency": "HOME", "CLINIC", "URGENT", or "ER"
- "explanation": short explanation (1–3 sentences)
- "red_flags": list of triggered red flags (or [])
"""

    # Call the Gemini model with the constructed prompt
    response = model.generate_content(prompt)

    # Extract the plain text from the response and strip whitespace
    text = response.text.strip()

    # --------------------------------------------------------
    # JSON Parsing Logic
    # --------------------------------------------------------

    # First attempt: assume the model returned clean JSON only
    try:
        return json.loads(text)  # Try to parse the entire text as JSON
    except json.JSONDecodeError:
        # If this fails, continue to the next parsing strategy
        pass

    # Second attempt: try to extract a substring between the
    # first '{' and the last '}' and parse that substring.
    start = text.find("{")      # Index of first '{'
    end = text.rfind("}")       # Index of last '}'
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end + 1]  # Slice that includes the braces
        return json.loads(json_str)     # Attempt to parse this substring as JSON

    # If both strategies fail, bubble up a clear error with raw output shown
    raise ValueError(f"Gemini did not return valid JSON. Raw output: {text}")


def apply_rule_safety_layer(symptoms: SymptomInput, gemini_result: dict) -> TriageDecision:
    """
    Apply additional rule-based safety checks on top of the Gemini output.

    This function:
      - extracts score, urgency, explanation, and red_flags from Gemini JSON
      - applies conservative override rules for critical symptoms
      - returns a TriageDecision dataclass

    The rules:
      1. Chest pain + breathing issues → force ER (score ≥ 4)
      2. Breathing difficulty alone → at least URGENT (score ≥ 3)
      3. Very high fever (>= 40°C) → at least CLINIC (score ≥ 3 if HOME)
    """

    # Extract and sanitize model outputs with reasonable defaults
    score = int(gemini_result.get("score", 2))                # Default score = 2 if missing
    urgency = str(gemini_result.get("urgency", "CLINIC")).upper()  # Default urgency = "CLINIC"
    explanation = str(gemini_result.get("explanation", "")).strip()  # Clean up explanation text
    red_flags: List[str] = gemini_result.get("red_flags", []) or []  # Use empty list if missing or None

    # Lowercase version of symptom text for easier substring matching
    text = symptoms.text.lower()

    # --------------------------------------------------------
    # Rule 1: Chest pain + shortness of breath → automatic ER
    # --------------------------------------------------------
    if "chest pain" in text and (
        "shortness of breath" in text or "difficulty breathing" in text
    ):
        # Only add this red flag once if it's not already present
        if "Chest pain + shortness of breath / difficulty breathing" not in red_flags:
            red_flags.append("Chest pain + shortness of breath / difficulty breathing")

        # Escalate severity score to at least 4
        score = max(score, 4)

        # Force urgency to ER
        urgency = "ER"

    # --------------------------------------------------------
    # Rule 2: Noticeable breathing difficulty → at least URGENT
    # --------------------------------------------------------
    if (
        "cant breathe" in text               # "cant breathe" (no apostrophe)
        or "can't breathe" in text          # "can't breathe" with apostrophe
        or "difficulty breathing" in text   # generic difficulty breathing phrase
        or "trouble breathing" in text      # another common phrase
    ):
        # Add a generic respiratory red flag if not already present
        if "Respiratory distress" not in red_flags:
            red_flags.append("Respiratory distress")

        # Ensure minimum severity score of 3
        score = max(score, 3)

        # If model said HOME or CLINIC, escalate to URGENT
        if urgency in ["HOME", "CLINIC"]:
            urgency = "URGENT"

    # --------------------------------------------------------
    # Rule 3: High fever (>=40°C) → escalate from HOME
    # --------------------------------------------------------
    if (
        symptoms.vitals.temperature_c is not None      # Only apply rule if temp is known
        and symptoms.vitals.temperature_c >= 40        # Very high fever threshold
    ):
        # Add red flag for high fever if not already present
        if "High fever (>=40C)" not in red_flags:
            red_flags.append("High fever (>=40C)")

        # Ensure at least score 3 if temperature is that high
        score = max(score, 3)

        # If model returned HOME, bump to CLINIC (but not higher by rule)
        if urgency == "HOME":
            urgency = "CLINIC"

    # --------------------------------------------------------
    # Construct and return the final TriageDecision dataclass
    # --------------------------------------------------------
    return TriageDecision(
        urgency_level=urgency,      # Final urgency after safety rules
        score=score,                # Possibly escalated severity score
        explanation=explanation,    # Original explanation from model
        red_flags=red_flags,        # Combined model + rule-based red flags
    )
