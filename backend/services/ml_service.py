# backend/services/ml_service.py

import os
import joblib
import pandas as pd
import numpy as np
from django.conf import settings
from backend.services.ollama_service import query_ollama
from backend.services.audit_service import log_event
import traceback

# Model paths - using absolute paths
BASE_DIR = settings.BASE_DIR

# Try multiple possible model paths
MODEL_PATHS = [
    os.path.join(BASE_DIR, 'ml_models', 'disease_predictor.joblib'),
    os.path.join(BASE_DIR, 'backend', 'ml_models', 'disease_predictor.joblib'),
    os.path.join(BASE_DIR, 'data', 'disease_predictor.joblib'),
]

# Try multiple possible training data paths
TRAIN_PATHS = [
    os.path.join(BASE_DIR, 'data', 'Train.csv'),
    os.path.join(BASE_DIR, 'ml_models', 'Train.csv'),
    os.path.join(BASE_DIR, 'backend', 'ml_models', 'Train.csv'),
]

# Global variables
model = None
FEATURES = []
MODEL_LOADED = False
FEATURES_LOADED = False

def load_model():
    """Load ML model with error handling"""
    global model, MODEL_LOADED
    
    if MODEL_LOADED and model is not None:
        return model
    
    print("[ML] Attempting to load model...")
    
    for model_path in MODEL_PATHS:
        try:
            if os.path.exists(model_path):
                print(f"[ML] Loading model from: {model_path}")
                model = joblib.load(model_path)
                MODEL_LOADED = True
                print(f"[ML] Model loaded successfully!")
                return model
            else:
                print(f"[ML] Model not found at: {model_path}")
        except Exception as e:
            print(f"[ML] Error loading model from {model_path}: {str(e)}")
    
    # If model not found, create a dummy model for fallback
    print("[ML] Creating fallback model...")
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import LabelEncoder
        import numpy as np
        
        # Create a simple fallback model
        class FallbackModel:
            def __init__(self):
                self.classes_ = ['Common Cold', 'Flu', 'Migraine', 'Allergy']
                self.n_classes_ = len(self.classes_)
                self.le = LabelEncoder()
                self.le.fit(self.classes_)
            
            def predict(self, X):
                # Simple rule-based fallback
                n_samples = X.shape[0]
                # Return most common conditions
                return [self.classes_[0] for _ in range(n_samples)]
            
            def predict_proba(self, X):
                n_samples = X.shape[0]
                # Return uniform probabilities for fallback
                prob = 1.0 / self.n_classes_
                return np.full((n_samples, self.n_classes_), prob)
        
        model = FallbackModel()
        MODEL_LOADED = True
        print("[ML] Fallback model created")
    except Exception as e:
        print(f"[ML] Failed to create fallback model: {str(e)}")
        model = None
    
    return model

def load_features():
    """Load feature list from training data"""
    global FEATURES, FEATURES_LOADED
    
    if FEATURES_LOADED and FEATURES:
        return FEATURES
    
    print("[ML] Attempting to load features...")
    
    for train_path in TRAIN_PATHS:
        try:
            if os.path.exists(train_path):
                print(f"[ML] Loading features from: {train_path}")
                df = pd.read_csv(train_path)
                
                # Try different possible column names for the target
                target_columns = ['prognosis', 'diagnosis', 'disease', 'Prognosis', 'Diagnosis', 'Disease']
                target_col = None
                
                for col in target_columns:
                    if col in df.columns:
                        target_col = col
                        break
                
                if target_col:
                    FEATURES = df.drop(columns=[target_col]).columns.tolist()
                else:
                    # Assume last column is target
                    FEATURES = df.columns[:-1].tolist()
                
                FEATURES_LOADED = True
                print(f"[ML] Loaded {len(FEATURES)} features")
                return FEATURES
            else:
                print(f"[ML] Training data not found at: {train_path}")
        except Exception as e:
            print(f"[ML] Error loading features from {train_path}: {str(e)}")
    
    # Create fallback features based on common symptoms
    print("[ML] Creating fallback features...")
    common_symptoms = [
        'itching', 'skin_rash', 'nodal_skin_eruptions', 'continuous_sneezing',
        'shivering', 'chills', 'joint_pain', 'stomach_pain', 'acidity',
        'ulcers_on_tongue', 'muscle_wasting', 'vomiting', 'burning_micturition',
        'fatigue', 'weight_gain', 'anxiety', 'cold_hands_and_feets',
        'mood_swings', 'weight_loss', 'restlessness', 'lethargy',
        'patches_in_throat', 'irregular_sugar_level', 'cough', 'high_fever',
        'sunken_eyes', 'breathlessness', 'sweating', 'dehydration',
        'indigestion', 'headache', 'yellowish_skin', 'dark_urine',
        'nausea', 'loss_of_appetite', 'pain_behind_the_eyes', 'back_pain',
        'constipation', 'abdominal_pain', 'diarrhoea', 'mild_fever',
        'yellow_urine', 'yellowing_of_eyes', 'acute_liver_failure',
        'fluid_overload', 'swelling_of_stomach', 'swelled_lymph_nodes',
        'malaise', 'blurred_and_distorted_vision', 'phlegm', 'throat_irritation',
        'redness_of_eyes', 'sinus_pressure', 'runny_nose', 'congestion',
        'chest_pain', 'weakness_in_limbs', 'fast_heart_rate',
        'pain_during_bowel_movements', 'pain_in_anal_region', 'bloody_stool',
        'irritation_in_anus', 'neck_pain', 'dizziness', 'cramps',
        'bruising', 'obesity', 'swollen_legs', 'swollen_blood_vessels',
        'puffy_face_and_eyes', 'enlarged_thyroid', 'brittle_nails',
        'swollen_extremeties', 'excessive_hunger', 'extra_marital_contacts',
        'drying_and_tingling_lips', 'slurred_speech', 'knee_pain', 'hip_joint_pain',
        'muscle_weakness', 'stiff_neck', 'swelling_joints', 'movement_stiffness',
        'spinning_movements', 'loss_of_balance', 'unsteadiness',
        'weakness_of_one_body_side', 'loss_of_smell', 'bladder_discomfort',
        'foul_smell_of_urine', 'continuous_feel_of_urine', 'passage_of_gases',
        'internal_itching', 'toxic_look_(typhos)', 'depression', 'irritability',
        'muscle_pain', 'altered_sensorium', 'red_spots_over_body', 'belly_pain',
        'abnormal_menstruation', 'dischromic_patches', 'watering_from_eyes',
        'increased_appetite', 'polyuria', 'family_history', 'mucoid_sputum',
        'rusty_sputum', 'lack_of_concentration', 'visual_disturbances',
        'receiving_blood_transfusion', 'receiving_unsterile_injections',
        'coma', 'stomach_bleeding', 'distention_of_abdomen',
        'history_of_alcohol_consumption', 'fluid_overload.1', 'blood_in_sputum',
        'prominent_veins_on_calf', 'palpitations', 'painful_walking',
        'pus_filled_pimples', 'blackheads', 'scurring', 'skin_peeling',
        'silver_like_dusting', 'small_dents_in_nails', 'inflammatory_nails',
        'blister', 'red_sore_around_nose', 'yellow_crust_ooze'
    ]
    
    FEATURES = common_symptoms
    FEATURES_LOADED = True
    print(f"[ML] Created {len(FEATURES)} fallback features")
    
    return FEATURES

def calculate_risk(confidence: float) -> str:
    """Calculate risk level based on confidence score"""
    if confidence < 0.40: 
        return "Low"
    if confidence < 0.60: 
        return "Medium"
    if confidence < 0.80: 
        return "High"
    return "Critical"

def generate_llm_explanation(prediction, confidence, risk_level, symptoms):
    """Generate explanation using LLM"""
    symptom_str = ", ".join(symptoms) if symptoms else "none reported"
    
    prompt = f"""
As a medical AI assistant, provide a simple explanation based on the following analysis:

**Analysis Results:**
- Predicted Condition: {prediction}
- Confidence Level: {confidence:.1%}
- Risk Assessment: {risk_level}
- Symptoms Considered: {symptom_str}

**Please provide:**
1. A brief, layman-friendly explanation of what this prediction means
2. General advice on next steps (always consult a doctor)
3. Important disclaimers about AI medical advice
4. Suggested questions to ask a healthcare provider

Keep the response under 4 sentences, simple, and emphasize that this is not a diagnosis.
"""
    
    try:
        response = query_ollama(prompt)
        if response and len(response.strip()) > 10:
            return response.strip()
        else:
            return f"Based on the symptoms {symptom_str}, there may be indications of {prediction.lower()}. Please consult with a healthcare professional for proper diagnosis and treatment."
    except Exception as e:
        print(f"[ML] LLM explanation failed: {e}")
        return f"This analysis suggests {prediction.lower()} based on the reported symptoms. IMPORTANT: This is an AI-generated suggestion, not a medical diagnosis. Always consult with a qualified healthcare provider."

def triangular(x, a, b, c):
    """Refined triangular membership function per user spec"""
    if x <= a or x >= c: return 0.0
    if x == b: return 1.0
    if x < b: return (x - a) / (b - a)
    return (c - x) / (c - b)

def get_fuzzy_membership(score):
    """
    Layer 3: Continuous Fuzzy Membership Functions
    - LOW: [0, 0.2, 0.4] (capped)
    - MED: [0.3, 0.5, 0.7]
    - HIGH: [0.6, 0.8, 1.0] (capped)
    """
    s = clamp(score)
    
    # LOW membership: 1.0 if s <= 0.2, then triangular
    if s <= 0.2:
        m_low = 1.0
    else:
        m_low = triangular(s, 0, 0.2, 0.4)
        
    # MEDIUM membership: triangular
    m_med = triangular(s, 0.3, 0.5, 0.7)
    
    # HIGH membership: triangular, then 1.0 if s >= 0.8
    if s >= 0.8:
        m_high = 1.0
    else:
        m_high = triangular(s, 0.6, 0.8, 1.0)
        
    # Convert to percentages for UI (toFixed(1) equivalent)
    return {
        "low": round(m_low * 100, 1),
        "medium": round(m_med * 100, 1),
        "high": round(m_high * 100, 1)
    }

def calculate_fuzzy_risk_category(score):
    """Layer 4: Risk Category Thresholds"""
    if score < 0.33: return "LOW"
    if score < 0.66: return "MEDIUM"
    return "HIGH"

def clamp(value, min_val=0, max_val=1):
    """Safe clamping to prevent NaN/Infinity"""
    try:
        if value is None: return min_val
        val = float(value)
        if not np.isfinite(val): return min_val
        return max(min_val, min(val, max_val))
    except (ValueError, TypeError):
        return min_val

def get_critical_symptom_flag(symptoms):
    """Check for high-risk clinical signs"""
    critical_terms = ["chest_pain", "shortness_of_breath", "breathlessness", "difficulty_breathing"]
    for symp in symptoms:
        norm = str(symp).lower().strip().replace(" ", "_")
        if any(term in norm for term in critical_terms):
            return True
    return False

def predict(input_symptoms: dict, age=None, severity_map=None):
    """
    HYBRID AI RISK STRATIFICATION SYSTEM (REDESIGN)
    """
    print(f"[ML-RE] Pipeline started with symptoms: {list(input_symptoms.keys())}")

    # --- LAYER 1: INPUT PROCESSING & VALIDATION ---
    if not input_symptoms:
        return {
            "error": "No symptoms provided",
            "primary_prediction": "Healthy / Unknown",
            "disease_confidence": 0,
            "risk_level": "LOW",
            "risk_score": 0,
            "explanation": "No symptoms reported for analysis."
        }

    # Default fallbacks
    clean_age = clamp(float(age) if age is not None else 35, 0, 110)
    
    # Severity calculation (1-5 scale)
    severities = []
    if severity_map:
        for s in input_symptoms:
            severities.append(clamp(severity_map.get(s, 3), 1, 5))
    else:
        # Default to 3 if no map provided
        severities = [3] * len(input_symptoms)
    
    avg_severity = sum(severities) / len(severities) if severities else 3
    
    # Normalization
    age_factor = clamp(clean_age / 100.0)
    severity_factor = clamp(avg_severity / 5.0)
    
    features = load_features()
    total_features = len(features) if features else 132
    symptom_count = len(input_symptoms)
    symptom_count_factor = clamp(symptom_count / 15.0) # Normalized count factor
    
    critical_flag = get_critical_symptom_flag(input_symptoms.keys())

    # --- LAYER 2: DISEASE PREDICTION MODEL (ML) ---
    model = load_model()
    base_disease_probability = 0.5
    prediction_name = "Undetermined"
    
    try:
        # Build feature vector
        vector = {f: 0 for f in features}
        for symp_raw in input_symptoms:
            symp = str(symp_raw).lower().strip().replace(" ", "_").replace("-", "_")
            if symp in vector:
                vector[symp] = 1
        
        X = pd.DataFrame([vector])[features]
        
        # Ensemble Prediction (Robust try/catch)
        if hasattr(model, 'predict_proba'):
            probs = model.predict_proba(X)[0]
            base_disease_probability = float(max(probs))
            
            # Predict Label
            raw_idx = model.predict(X)[0]
            if hasattr(model, 'label_encoder_'):
                prediction_name = model.label_encoder_.inverse_transform([raw_idx])[0]
            else:
                prediction_name = str(raw_idx)
        else:
            base_disease_probability = 0.5
            prediction_name = "System Fallback"
            
    except Exception as e:
        print(f"[ML-RE] Layer 2 Failed: {e}")
        base_disease_probability = 0.5
        prediction_name = "Clinical Screening"

    # Ensure no NaN
    base_disease_probability = clamp(base_disease_probability)

    # --- LAYER 3: FUZZY RISK ENGINE ---
    # Define Fuzzy Rules (Overrides)
    risk_override = None
    
    # 1) IF age is Elderly (>0.65) AND critical symptom present -> HIGH
    if age_factor > 0.65 and critical_flag:
        risk_override = "HIGH"
    
    # 2) IF symptom_count is Many AND severity is Severe -> HIGH
    elif symptom_count_factor > 0.6 and severity_factor > 0.7:
        risk_override = "HIGH"
        
    # 5) IF age > 75 AND symptom_count > 5 -> minimum risk = MEDIUM
    elif clean_age > 75 and symptom_count > 5:
        risk_override = "MEDIUM"

    # --- LAYER 4: NUMERIC RISK CALCULATION ---
    # Formula: (0.30 * symptom_count_factor) + (0.30 * severity_factor) + (0.25 * age_factor) + (0.15 * base_disease_probability)
    risk_score = (0.30 * symptom_count_factor) + \
                 (0.30 * severity_factor) + \
                 (0.25 * age_factor) + \
                 (0.15 * base_disease_probability)
    
    risk_score = clamp(risk_score)
    
    # Initial Category
    risk_category = calculate_fuzzy_risk_category(risk_score)
    
    # 1. Apply Rule Overrides
    if risk_override:
        if risk_override == "HIGH":
            risk_category = "HIGH"
            risk_score = max(risk_score, 0.67) # Force into HIGH range
        elif risk_override == "MEDIUM" and risk_category == "LOW":
            risk_category = "MEDIUM"
            risk_score = max(risk_score, 0.34) # Force into MEDIUM range

    # 2. Continuous Fuzzy Membership (UI percentage)
    fuzzy_membership = get_fuzzy_membership(risk_score)

    # 3. Explanation Generation
    if risk_category == "HIGH":
        if critical_flag:
            expl = f"High clinical risk due to critical signs and age factors ({clean_age}y)."
        else:
            expl = "High risk due to high symptom count and significant severity."
    elif risk_category == "MEDIUM":
        expl = f"Moderate risk based on patient profile and ongoing symptoms."
    else:
        expl = "Risk profile remains low based on current symptoms and vital statistics."

    # --- OUTPUT FORMAT (STRICT) ---
    return {
        "primary_prediction": str(prediction_name),
        "disease_confidence": round(base_disease_probability * 100, 1),
        "risk_level": risk_category,
        "risk_score": round(risk_score, 3),
        "fuzzy_membership": fuzzy_membership,
        "explanation": expl,
        # Extended fields for transparency
        "age_factor": round(age_factor, 2),
        "severity_factor": round(severity_factor, 2),
        "symptom_factor": round(symptom_count_factor, 2),
        "ml_probability": round(base_disease_probability, 2),
        "critical_sign_detected": critical_flag
    }

def get_fallback_prediction(input_symptoms):
    """Get fallback prediction when model fails"""
    print("[ML] Using fallback prediction")
    
    symptoms_list = list(input_symptoms.keys()) if isinstance(input_symptoms, dict) else []
    
    # Simple rule-based fallback
    if 'headache' in str(symptoms_list).lower():
        prediction = "Migraine or Tension Headache"
        confidence = 65.0
        risk = "Medium"
    elif 'fever' in str(symptoms_list).lower() and 'cough' in str(symptoms_list).lower():
        prediction = "Common Cold or Flu"
        confidence = 70.0
        risk = "Medium"
    elif 'pain' in str(symptoms_list).lower():
        prediction = "General Pain Condition"
        confidence = 50.0
        risk = "Low"
    else:
        prediction = "General Medical Consultation Needed"
        confidence = 40.0
        risk = "Low"
    
    explanation = generate_llm_explanation(
        prediction, confidence/100, risk, symptoms_list
    )
    
    return {
        "prediction": prediction,
        "confidence": confidence,
        "risk_level": risk,
        "llm_explanation": explanation,
        "symptoms_used": symptoms_list,
        "model_status": "fallback",
        "note": "Using rule-based fallback analysis"
    }

def get_model_status():
    """Get current model status"""
    return {
        "model_loaded": MODEL_LOADED,
        "features_loaded": FEATURES_LOADED,
        "model_paths_tried": MODEL_PATHS,
        "train_paths_tried": TRAIN_PATHS,
        "num_features": len(FEATURES) if FEATURES else 0
    }

# Initialize on import
print("[ML] Initializing ML Service...")
load_model()
load_features()
print(f"[ML] Initialization complete. Model loaded: {MODEL_LOADED}, Features loaded: {FEATURES_LOADED}")