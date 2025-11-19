# triage_engine.py
import os
import json
from typing import List

import google.generativeai as genai

from models import SymptomInput, TriageDecision

# Load Gemini API key from environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Please export it as an environment variable."
    )

genai.configure(api_key=GEMINI_API_KEY)

# Gemini model used for triage (can be switched depending on permissions)
MODEL_NAME = "gemini-2.5-flash"


def call_gemini_for_triage(symptoms: SymptomInput) -> dict:
    """
    Call Gemini with a structured prompt and request a JSON-only response.
    The model returns:
        {
            "score": 1-4,
            "urgency": "HOME" | "CLINIC" | "URGENT" | "ER",
            "explanation": "...",
            "red_flags": [...]
        }
    """
    model = genai.GenerativeModel(MODEL_NAME)

    # Convert vitals to readable strings for the prompt
    temp_str = "unknown" if symptoms.vitals.temperature_c is None else symptoms.vitals.temperature_c
    pain_str = "unknown" if symptoms.vitals.pain_score is None else symptoms.vitals.pain_score
    preg_str = "unknown" if symptoms.vitals.pregnant is None else symptoms.vitals.pregnant
    trauma_str = "unknown" if symptoms.vitals.trauma is None else symptoms.vitals.trauma

    # Clear, conservative triage instructions for Gemini
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

    response = model.generate_content(prompt)
    text = response.text.strip()

    # --- JSON Parsing Logic ---
    # First: try direct JSON parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second: extract substring between first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end + 1]
        return json.loads(json_str)

    # Final fallback if model output is malformed
    raise ValueError(f"Gemini did not return valid JSON. Raw output: {text}")


def apply_rule_safety_layer(symptoms: SymptomInput, gemini_result: dict) -> TriageDecision:
    """
    Apply additional rule-based safety checks on top of the Gemini output.
    These rules guarantee conservative escalation for critical symptoms.
    """
    score = int(gemini_result.get("score", 2))
    urgency = str(gemini_result.get("urgency", "CLINIC")).upper()
    explanation = str(gemini_result.get("explanation", "")).strip()
    red_flags: List[str] = gemini_result.get("red_flags", []) or []

    text = symptoms.text.lower()

    # Rule 1: Chest pain + shortness of breath → automatic ER
    if "chest pain" in text and (
        "shortness of breath" in text or "difficulty breathing" in text
    ):
        if "Chest pain + shortness of breath / difficulty breathing" not in red_flags:
            red_flags.append("Chest pain + shortness of breath / difficulty breathing")
        score = max(score, 4)
        urgency = "ER"

    # Rule 2: Noticeable breathing difficulty → at least Urgent Care
    if ("cant breathe" in text or "can't breathe" in text or
        "difficulty breathing" in text or "trouble breathing" in text):
        if "Respiratory distress" not in red_flags:
            red_flags.append("Respiratory distress")
        score = max(score, 3)
        if urgency in ["HOME", "CLINIC"]:
            urgency = "URGENT"

    # Rule 3: High fever (>=40°C) → escalate from HOME
    if symptoms.vitals.temperature_c is not None and symptoms.vitals.temperature_c >= 40:
        if "High fever (>=40C)" not in red_flags:
            red_flags.append("High fever (>=40C)")
        score = max(score, 3)
        if urgency == "HOME":
            urgency = "CLINIC"

    return TriageDecision(
        urgency_level=urgency,
        score=score,
        explanation=explanation,
        red_flags=red_flags,
    )

