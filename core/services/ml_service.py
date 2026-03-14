import joblib
import pandas as pd
from backend.services.ollama_service import query_ollama
from backend.services.audit_service import log_event


MODEL_PATH = r"C:\Users\pande\Desktop\Documents\medical_chatbots_project\backend\services\trained_model.joblib"
TRAIN_PATH = r"C:\Users\pande\Desktop\Documents\medical_chatbots_project\data\Train.csv"

# Load model
model = joblib.load(MODEL_PATH)

# Build feature list automatically (EXACT order as training)
df = pd.read_csv(TRAIN_PATH)
FEATURES = df.drop(columns=["prognosis"]).columns.tolist()


# 🔹 FUZZY LOGIC
def calculate_risk(confidence: float) -> str:
    if confidence < 0.40:
        return "Low"
    elif confidence < 0.60:
        return "Medium"
    elif confidence < 0.80:
        return "High"
    else:
        return "Critical"


# 🔹 LLM EXPLANATION
def generate_llm_explanation(prediction, confidence, risk_level, symptoms):
    symptom_list = ", ".join(symptoms)

    prompt = f"""
You are a medical doctor assistant.

Predicted disease: {prediction}
Confidence score: {confidence:.2f}
Risk level: {risk_level}
Reported symptoms: {symptom_list}

Explain the condition in simple medical terms.
Provide general advice and precautions.
Do NOT give a final diagnosis.
Limit the explanation to 4–5 sentences.

"""

    return query_ollama(prompt)


def predict(input_symptoms: dict):
    # Initialize all features to 0
    full_data = {feature: 0 for feature in FEATURES}

    for key, value in input_symptoms.items():
        if key in full_data:
            full_data[key] = value

    X = pd.DataFrame([full_data])[FEATURES].values

    prediction = model.predict(X)[0]
    confidence = model.predict_proba(X).max()
    risk_level = calculate_risk(confidence)

    active_symptoms = [k for k, v in input_symptoms.items() if v == 1]

    llm_explanation = generate_llm_explanation(
        prediction,
        confidence,
        risk_level,
        active_symptoms
    )
    log_event(
    action="ML_PREDICTION",
    role="doctor",
    details={
        "prediction": str(prediction),
        "risk_level": risk_level
    }
)


    return {
        "prediction": str(prediction),
        "confidence": round(float(confidence), 3),
        "risk_level": risk_level,
        "llm_explanation": llm_explanation
    }
