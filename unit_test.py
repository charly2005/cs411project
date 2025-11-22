import unittest

from triage_engine import call_gemini_for_triage, apply_rule_safety_layer
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
        print("Gemini Raw Output: ", gemini_raw)
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
        print("Recommendation Output: ", rec)
        assert rec is not None

    def test_red_flag_1(self):
        print("==Testing red flag rules...")

        text = "Mild chest pain and shortness of breath"
        vitals = Vitals(
            temperature_c=36.5,
            pain_score=0, 
            pregnant=False, 
            trauma=False
        )
        symptom = SymptomInput(
                text=text,
                vitals=vitals
            )
        
        gemini_raw = call_gemini_for_triage(
            symptom
        )

        decision = apply_rule_safety_layer(symptom, gemini_raw)

        print("Gemini Raw Output: ", gemini_raw.get("red_flags", []) or [])
        assert int(gemini_raw.get("score", 2)) > 3

    def test_red_flag_2(self):
        text = "Can't breathe properly"
        vitals = Vitals(
            temperature_c=36.5,
            pain_score=0, 
            pregnant=False, 
            trauma=False
        )
        symptom = SymptomInput(
                text=text,
                vitals=vitals
            )
        
        gemini_raw = call_gemini_for_triage(
            symptom
        )

        decision = apply_rule_safety_layer(symptom, gemini_raw)

        print("Gemini Raw Output: ", gemini_raw.get("red_flags", []) or [])
        assert int(gemini_raw.get("score", 2)) > 2

    def test_red_flag_3(self):
        text = "Feeling ok"
        vitals = Vitals(
            temperature_c=41.1,
            pain_score=0, 
            pregnant=False, 
            trauma=False
        )
        symptom = SymptomInput(
                text=text,
                vitals=vitals
            )
        
        gemini_raw = call_gemini_for_triage(
            symptom
        )

        decision = apply_rule_safety_layer(symptom, gemini_raw)

        print("Gemini Raw Output: ", gemini_raw.get("red_flags", []) or [])
        assert int(gemini_raw.get("score", 2)) > 2

if __name__ == "__main__":
    unittest.main()