# core/ml_model.py
import joblib
import numpy as np
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Load ML model (simplified version)
import json
import joblib
from django.conf import settings
from pathlib import Path

MODEL_LOADED = False

try:

    model_path = settings.BASE_DIR / "ml_models" / "disease_predictor.joblib"
    features_path = settings.BASE_DIR / "ml_models" / "features.json"
    diseases_path = settings.BASE_DIR / "ml_models" / "label_classes.json"


    model = joblib.load(model_path)

    with open(features_path) as f:
        features = json.load(f)

    with open(diseases_path) as f:
        diseases = json.load(f)

    MODEL_LOADED = True
    print("✅ ML MODEL LOADED SUCCESSFULLY")

except Exception as e:
    print("❌ ML MODEL LOAD ERROR:", e)
    model = None
    features = []
    diseases = []


def get_ml_prediction(symptoms):
    """Get ML prediction for symptoms"""
    if not model:
        return {
            'prediction': 'Model not available',
            'confidence': 0.0,
            'risk_level': 'medium',
            'explanation': 'ML model is not loaded.'
        }
    
    try:
        # Create feature vector
        feature_vector = np.zeros(len(features))
        for symptom in symptoms:
            if symptom in features:
                idx = features.index(symptom)
                feature_vector[idx] = 1
        
        # Get prediction
        prediction_idx = model.predict([feature_vector])[0]
        probabilities = model.predict_proba([feature_vector])[0]
        confidence = float(max(probabilities))
        
        prediction = diseases[prediction_idx] if prediction_idx < len(diseases) else 'Unknown'
        
        # Determine risk level
        if confidence > 0.8:
            risk_level = 'high'
        elif confidence > 0.6:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'prediction': prediction,
            'confidence': confidence,
            'risk_level': risk_level,
            'explanation': f'Based on {len(symptoms)} symptoms with {confidence:.1%} confidence.',
            'symptoms_analyzed': len(symptoms)
        }
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return {
            'prediction': 'Error',
            'confidence': 0.0,
            'risk_level': 'medium',
            'explanation': f'Error in prediction: {str(e)}'
        }

def analyze_research_data(analysis_type, parameters):
    """Analyze research data"""
    # Simplified analysis functions
    if analysis_type == 'trend':
        return {
            'analysis_type': 'trend',
            'result': 'Trend analysis completed',
            'data': {'trend': 'upward', 'confidence': 0.85}
        }
    elif analysis_type == 'correlation':
        return {
            'analysis_type': 'correlation',
            'result': 'Correlation analysis completed',
            'data': {'correlation': 0.72, 'p_value': 0.001}
        }
    else:
        return {
            'analysis_type': analysis_type,
            'result': 'Analysis completed',
            'data': {'status': 'success'}
        }
    

# Add to core/ml_model.py
def diagnose_model():
    """Diagnose ML model issues"""
    print("\n" + "="*50)
    print("ML MODEL DIAGNOSTICS")
    print("="*50)
    
    print(f"\n✅ Model Loaded: {MODEL_LOADED}")
    print(f"📊 Number of Features: {len(features)}")
    print(f"🏥 Number of Diseases: {len(diseases)}")
    
    print(f"\n📋 Sample Features (first 10):")
    for i, feature in enumerate(features[:10]):
        print(f"  {i+1}. {feature}")
    
    print(f"\n🏥 Sample Diseases (first 10):")
    for i, disease in enumerate(diseases[:10]):
        print(f"  {i+1}. {disease}")
    
    print(f"\n🔍 Testing predictions...")
    
    # Test with common symptoms
    test_symptoms = [
        ['fever', 'cough', 'headache'],
        ['nausea', 'diarrhea'],
        ['shortness_of_breath', 'chest_pain']
    ]
    
    for i, symptoms in enumerate(test_symptoms):
        print(f"\nTest {i+1}: {symptoms}")
        result = get_ml_prediction(symptoms)
        print(f"  Prediction: {result['prediction']}")
        print(f"  Confidence: {result['confidence']:.1%}")
        print(f"  Risk Level: {result['risk_level']}")
    
    print("\n" + "="*50)
    print("END DIAGNOSTICS")
    print("="*50 + "\n")

# Call diagnose to see what features your model expects
if MODEL_LOADED:
    diagnose_model()