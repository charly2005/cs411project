import unittest

from triage_engine import call_gemini_for_triage
from models import SymptomInput, Vitals

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

if __name__ == "__main__":
    unittest.main()