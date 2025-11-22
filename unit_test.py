import unittest

from triage_engine import call_gemini_for_triage
from models import SymptomInput, Vitals, TriageDecision
from facilities_google import recommend_facilities

class TestMyModule(unittest.TestCase):
    def test_symptom(self):
        print("==Testing symptom input to Gemini model...")

        text = "Severe headache and dizziness"
        vitals = Vitals(
            temperature_c=37.5,
            pain_score=8, 
            pregnant=False, 
            trauma=False
        )
        
        gemini_raw = call_gemini_for_triage(
            SymptomInput(
                text=text,
                vitals=vitals
            )
        )
        print("Gemini Raw Output:", gemini_raw)
        assert gemini_raw is not None

    def test_recommendation(self):
        print("==Testing recommendation...")

        decision = TriageDecision(
            urgency_level="URGENT",
            score=3,
            explanation="Severe symptoms requiring prompt attention.",
            red_flags=["severe headache", "dizziness"]
        )
        
        rec = recommend_facilities(decision, 34.032845, -118.266266)
        print("Recommendation Output:", rec)
        assert rec is not None

if __name__ == "__main__":
    unittest.main()