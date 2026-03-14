
import os
import sys
import numpy as np

# Mock Django setup
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        BASE_DIR=os.path.dirname(os.path.abspath(__file__)),
        INSTALLED_APPS=[],
    )
    django.setup()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services import ml_service

def test_redesign():
    print("🧪 Verifying Hybrid AI Risk Stratification System Redesign...")
    
    test_cases = [
        {
            "name": "Case 1: Young, 2 mild symptoms",
            "symptoms": {"itching": 1, "skin_rash": 1},
            "age": 25,
            "severity_map": {"itching": 2, "skin_rash": 2},
            "expected_risk": "LOW"
        },
        {
            "name": "Case 2: Middle Age, 4 moderate symptoms",
            "symptoms": {"fever": 1, "cough": 1, "fatigue": 1, "headache": 1},
            "age": 45,
            "severity_map": {"fever": 3, "cough": 3, "fatigue": 3, "headache": 3},
            "expected_risk": "MEDIUM"
        },
        {
            "name": "Case 3: Elderly, Chest Pain, 6 symptoms",
            "symptoms": {"chest_pain": 1, "dizziness": 1, "fatigue": 1, "headache": 1, "nausea": 1, "vomiting": 1},
            "age": 87,
            "severity_map": {"chest_pain": 5, "dizziness": 4, "fatigue": 4, "headache": 3, "nausea": 3, "vomiting": 3},
            "expected_risk": "HIGH"
        },
        {
            "name": "Rule 5 Check: Age > 75 + Many Symptoms",
            "symptoms": {s: 1 for s in ["fever", "cough", "fatigue", "headache", "nausea", "vomiting"]},
            "age": 80,
            "severity_map": {s: 2 for s in ["fever", "cough", "fatigue", "headache", "nausea", "vomiting"]},
            "expected_risk": "MEDIUM" # Min Medium due to Rule 5
        }
    ]
    
    all_passed = True
    
    for case in test_cases:
        print(f"\n--- Testing: {case['name']} ---")
        result = ml_service.predict(case['symptoms'], age=case['age'], severity_map=case['severity_map'])
        
        # Display key metrics
        print(f"Prediction: {result['primary_prediction']} ({result['disease_confidence']}%)")
        print(f"Risk Logic: Score={result['risk_score']} | Level={result['risk_level']}")
        print(f"Fuzzy Membership: {result['fuzzy_membership']}")
        print(f"Factors: Age={result['age_factor']}, Symp={result['symptom_factor']}, Sev={result['severity_factor']}, ML={result['ml_probability']}")
        print(f"Explanation: {result['explanation']}")
        
        # Check against expected
        if result['risk_level'] == case['expected_risk']:
            print(f"✅ PASSED: Expected {case['expected_risk']}, got {result['risk_level']}")
        else:
            print(f"❌ FAILED: Expected {case['expected_risk']}, got {result['risk_level']}")
            all_passed = False

        # Safety Check for finite values and percentage ranges
        for k, v in result.items():
            if k == "fuzzy_membership":
                for mk, mv in v.items():
                    if not (0 <= mv <= 100):
                        print(f"❌ LOGIC ERROR: Fuzzy membership '{mk}' is outside 0-100 range: {mv}")
                        all_passed = False
            elif isinstance(v, (int, float)) and not np.isfinite(v):
                print(f"❌ SAFETY ERROR: Key '{k}' contains non-finite value: {v}")
                all_passed = False
    
    if all_passed:
        print("\n✨ ALL REDESIGN TEST CASES PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED.")

if __name__ == "__main__":
    test_redesign()
