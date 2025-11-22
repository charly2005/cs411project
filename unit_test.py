import unittest

from triage_engine import call_gemini_for_triage, apply_rule_safety_layer
from models import SymptomInput, Vitals, TriageDecision
from facilities_google import recommend_facilities
from geolocation import geocode_address, GeocodingError
from history import append_record, load_history

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

    def test_geo_code(self):
        print("==Testing geocoding...")

        address = "02134"
        
        try:
            lat, lon, formatted = geocode_address(address)
            print(f"Geocoded Address: {formatted}, Lat: {lat}, Lon: {lon}")
            assert lat > 0 and lon < 0
        except GeocodingError as e:
            self.fail(f"GeocodingError raised: {e}")

    def test_history(self):
        print("==Testing history logging...")

        decision = TriageDecision(
            urgency_level="CLINIC",
            score=2,
            explanation="Mild symptoms, can wait for clinic visit.",
            red_flags=[]
        )

        append_record(
            symptoms_text="Mild cough and sore throat",
            decision=decision,
            facility_names=["Clinic A", "Clinic B"]
        )

        records = load_history()
        print("Loaded History Records: ", records)
        assert len(records) > 0

if __name__ == "__main__":
    unittest.main()