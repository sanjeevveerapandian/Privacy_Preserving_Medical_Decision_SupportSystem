# core/utils.py
import json
import requests
import logging
import base64
import joblib
import numpy as np
import math
from django.conf import settings
from django.core.mail import send_mail
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .models import *
from backend.services import ml_service

logger = logging.getLogger(__name__)

# ============================================
# ENCRYPTION FUNCTIONS
# ============================================

def get_fernet_key():
    """Generate or retrieve Fernet key properly"""
    password = b"medical_assistant_system_password_2024"
    salt = b"medical_system_salt_2024"
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

# Initialize encryption
try:
    fernet_key = get_fernet_key()
    cipher = Fernet(fernet_key)
except Exception as e:
    logger.error(f"Failed to initialize encryption: {e}")
    cipher = None

def encrypt_data(data):
    """Encrypt data"""
    if cipher is None:
        return json.dumps(data) if isinstance(data, dict) else str(data)
    
    try:
        if isinstance(data, dict):
            data = json.dumps(data)
        return cipher.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return json.dumps(data) if isinstance(data, dict) else str(data)

def decrypt_data(encrypted_data):
    """Decrypt data"""
    if cipher is None or not encrypted_data:
        return encrypted_data
    
    try:
        decrypted = cipher.decrypt(encrypted_data.encode()).decode()
        try:
            return json.loads(decrypted)
        except json.JSONDecodeError:
            return decrypted
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        return encrypted_data

# ============================================
# OLLAMA INTEGRATION
# ============================================

def query_ollama(prompt, model_name=None):
    """
    Query local Ollama model for responses - FIXED VERSION with correct API endpoint
    """
    try:
        # Default model if not specified
        if model_name is None:
            model_name = getattr(settings, 'OLLAMA_DEFAULT_MODEL', 'llama2')
        
        # Ollama API endpoint - CORRECTED
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        
        # Prepare the prompt
        system_prompt = """You are a medical AI assistant for doctors. Provide professional, evidence-based medical information.
        Rules:
        1. Answer clearly and simply
        2. If you don't know something, say "I don't know"
        3. Do not hallucinate or assume internet access
        4. Behave like a helpful medical assistant
        5. You are fully offline and running locally
        
        Question: {prompt}
        
        Response:""".format(prompt=prompt)
        
        payload = {
            "model": model_name,
            "prompt": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9
            }
        }
        
        logger.debug(f"Sending request to Ollama with model: {model_name}")
        
        # Make request to CORRECT endpoint
        response = requests.post(
            f"{ollama_url}/api/generate",  # CORRECT ENDPOINT
            json=payload, 
            timeout=300,  # Longer timeout for model loading on slow hardware
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        )
        
        # Log response for debugging
        logger.debug(f"Ollama response status: {response.status_code}")
        logger.debug(f"Ollama response headers: {response.headers}")
        
        if response.status_code != 200:
            logger.error(f"Ollama API error {response.status_code}: {response.text[:200]}")
            
            # Try to get more specific error
            try:
                error_data = response.json()
                error_msg = error_data.get('error', response.text[:100])
            except:
                error_msg = response.text[:100] if response.text else "No response body"
                
            return f"Error: Ollama API returned status {response.status_code} - {error_msg}"
        
        # Parse response
        try:
            result = response.json()
            ai_response = result.get('response', '').strip()
            
            if not ai_response:
                # Check for error in response
                if 'error' in result:
                    return f"Error: {result['error']}"
                return "I apologize, but I couldn't generate a response."
            
            return ai_response
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, Response: {response.text[:200]}")
            # Try to extract response from text
            if 'response' in response.text:
                import re
                match = re.search(r'"response"\s*:\s*"([^"]+)"', response.text)
                if match:
                    return match.group(1)
            return "Error: Could not parse Ollama response"
        
    except requests.exceptions.ConnectionError:
        logger.error("Ollama connection failed. Is Ollama running on localhost:11434?")
        return "Error: Cannot connect to Ollama. Please ensure Ollama is running locally on port 11434."
    
    except requests.exceptions.Timeout:
        logger.error("Ollama request timeout")
        return "Error: Request timeout. The model is taking too long to respond. Try a simpler question or check if the model is loaded."
    
    except Exception as e:
        logger.error(f"Ollama query error: {str(e)}")
        return f"Error: {str(e)}"

# ============================================
# FUZZY LOGIC FUNCTIONS
# ============================================

def calculate_fuzzy_membership(value, low_range, medium_range, high_range):
    """
    Calculate fuzzy membership for a value across risk categories
    
    Args:
        value: Input value (0-1)
        low_range: Tuple (start, end) for low risk membership
        medium_range: Tuple (start, end) for medium risk membership
        high_range: Tuple (start, end) for high risk membership
    
    Returns:
        Dictionary with membership values for each risk category
    """
    def triangular_mf(x, a, b, c):
        """Triangular membership function"""
        if x <= a or x >= c:
            return 0.0
        elif a < x <= b:
            return (x - a) / (b - a)
        elif b < x < c:
            return (c - x) / (c - b)
        return 0.0
    
    low_membership = triangular_mf(value, *low_range)
    medium_membership = triangular_mf(value, *medium_range)
    high_membership = triangular_mf(value, *high_range)
    
    # Normalize if needed
    total = low_membership + medium_membership + high_membership
    if total > 0:
        low_membership /= total
        medium_membership /= total
        high_membership /= total
    
    return {
        'low': round(low_membership, 3),
        'medium': round(medium_membership, 3),
        'high': round(high_membership, 3)
    }

def calculate_fuzzy_risk(confidence, symptom_count, severity_factors=0, age=35):
    """
    Calculate fuzzy risk level with improved logic
    
    Args:
        confidence: ML confidence score (0-1)
        symptom_count: Number of symptoms
        severity_factors: Number of severe symptoms (optional)
        age: Patient age (optional)
    
    Returns:
        Dictionary with risk level and detailed scores
    """
    # Base risk from confidence (0-1)
    base_risk = confidence
    
    # Adjust for symptom count (normalized to 0-1)
    symptom_factor = min(1.0, symptom_count / 10)
    
    # Adjust for severity factors
    severity_factor = min(1.0, severity_factors * 0.2)
    
    # Adjust for age (higher risk for extremes)
    if age < 10 or age > 65:
        age_factor = 0.3
    elif age < 18 or age > 50:
        age_factor = 0.2
    else:
        age_factor = 0.1
    
    # Calculate composite risk score using weighted average
    risk_score = (
        base_risk * 0.5 +        # 50% weight to confidence
        symptom_factor * 0.3 +    # 30% weight to symptom count
        severity_factor * 0.15 +  # 15% weight to severity
        age_factor * 0.05         # 5% weight to age
    )
    
    # Ensure risk_score is between 0-1
    risk_score = max(0.0, min(1.0, risk_score))
    
    # Calculate fuzzy membership
    fuzzy_membership = calculate_fuzzy_membership(
        risk_score,
        low_range=(0.0, 0.2, 0.4),
        medium_range=(0.3, 0.5, 0.7),
        high_range=(0.6, 0.8, 1.0)
    )
    
    # Determine dominant risk level
    dominant_risk = max(fuzzy_membership.items(), key=lambda x: x[1])[0]
    
    # Determine final risk level based on dominant membership
    if fuzzy_membership['high'] > 0.6:
        final_risk = 'high'
    elif fuzzy_membership['medium'] > 0.6:
        final_risk = 'medium'
    elif fuzzy_membership['low'] > 0.6:
        final_risk = 'low'
    else:
        # If no clear dominant, use weighted decision
        if fuzzy_membership['high'] > fuzzy_membership['medium']:
            final_risk = 'high'
        elif fuzzy_membership['medium'] > fuzzy_membership['low']:
            final_risk = 'medium'
        else:
            final_risk = 'low'
    
    # Critical if confidence > 0.9 AND symptom_count > 5
    if confidence > 0.9 and symptom_count > 5:
        final_risk = 'critical'
    
    return {
        'risk_level': final_risk,
        'risk_score': round(risk_score, 3),
        'confidence_score': round(confidence, 3),
        'fuzzy_membership': fuzzy_membership,
        'components': {
            'base_risk': round(base_risk, 3),
            'symptom_factor': round(symptom_factor, 3),
            'severity_factor': round(severity_factor, 3),
            'age_factor': round(age_factor, 3)
        }
    }

# ============================================
# ML MODEL FUNCTIONS
# ============================================

# Load ML model (simplified version - in production, load actual model)
_ml_model = None
_ml_features = []

def load_ml_model():
    """Load ML model from disk"""
    global _ml_model, _ml_features
    
    if _ml_model is None:
        try:
            # Try to load actual model if exists
            model_path = getattr(settings, 'ML_MODEL_PATH', None)
            if model_path:
                _ml_model = joblib.load(model_path)
                logger.info("ML model loaded successfully")
            else:
                # Create dummy model for testing
                logger.warning("No ML model found, using dummy model")
                _ml_model = None
                
            # Load or create features
            features_path = getattr(settings, 'ML_FEATURES_PATH', None)
            if features_path:
                with open(features_path, 'r') as f:
                    _ml_features = json.load(f)
            else:
                # Create dummy features
                _ml_features = [
                    'fever', 'cough', 'headache', 'fatigue', 'nausea',
                    'shortness_of_breath', 'chest_pain', 'dizziness',
                    'muscle_pain', 'sore_throat', 'loss_of_taste_smell',
                    'diarrhea', 'abdominal_pain', 'vomiting', 'rash'
                ]
                
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            _ml_model = None
            _ml_features = []
    
    return _ml_model, _ml_features

def ml_predict(symptoms, patient_age=35, severity_score=3):
    """
    Make ML prediction using the redesigned Hybrid AI Stratification System.
    """
    try:
        # Convert list of symptoms to dict with default values or use provided ones
        symptom_dict = {s: 1 for s in symptoms}
        
        # Call the redesigned pipeline
        # Note: We pass severity_score as a fallback or if we had a per-symptom map
        result = ml_service.predict(symptom_dict, age=patient_age)
        
        if "error" in result:
             return {
                'success': False,
                'error': result["error"],
                'prediction': 'Error in prediction',
                'confidence': 0.0,
                'confidence_score': 0.0,
                'risk_level': 'medium',
                'risk_score': 0.5,
                'explanation': 'An error occurred during analysis.'
            }

        # Map results to UI format
        prediction = result["primary_prediction"]
        # In this redesign, we show disease_confidence separately from risk
        disease_confidence = result["disease_confidence"] / 100.0
        risk_level = result["risk_level"].lower()
        
        components = {
            'base_risk': result["ml_probability"],
            'symptom_factor': result["symptom_factor"],
            'severity_factor': result["severity_factor"],
            'age_factor': result["age_factor"]
        }
        
        return {
            'success': True,
            'prediction': prediction,
            'confidence': disease_confidence,
            'confidence_score': disease_confidence,
            'risk_level': risk_level,
            'risk_score': result["risk_score"],
            'fuzzy_membership': result.get("fuzzy_membership", {"low": 0, "medium": 0, "high": 0}),
            'explanation': result["explanation"],
            'components': components,
            'symptoms_analyzed': len(symptoms),
            'critical_sign_detected': result.get("critical_sign_detected", False)
        }
        
    except Exception as e:
        logger.error(f"ML prediction error: {e}")
        return {
            'success': False,
            'error': str(e),
            'prediction': 'Error in prediction',
            'confidence': 0.0,
            'confidence_score': 0.0,
            'risk_level': 'medium',
            'risk_score': 0.5,
            'explanation': 'An error occurred during analysis.'
        }

def get_mock_prediction(symptoms, patient_age=35):
    """Return mock prediction for testing with fuzzy logic"""
    # Define symptom patterns and their typical diseases
    patterns = {
        ('fever', 'cough', 'fatigue', 'body_aches'): ('Influenza (Flu)', 0.87),
        ('headache', 'nausea', 'sensitivity_to_light', 'aura'): ('Migraine', 0.79),
        ('abdominal_pain', 'nausea', 'vomiting', 'diarrhea'): ('Gastroenteritis', 0.83),
        ('sneezing', 'runny_nose', 'itchy_eyes', 'congestion'): ('Allergic Rhinitis', 0.77),
        ('cough', 'chest_pain', 'shortness_of_breath', 'fever'): ('Pneumonia', 0.91),
        ('fever', 'dry_cough', 'loss_of_taste', 'fatigue'): ('COVID-19', 0.85),
        ('frequent_urination', 'thirst', 'fatigue', 'blurred_vision'): ('Diabetes Type 2', 0.88),
        ('chest_pain', 'shortness_of_breath', 'dizziness', 'sweating'): ('Cardiac Issues', 0.94),
    }
    
    # Count severe symptoms
    severe_symptoms = ['chest_pain', 'shortness_of_breath', 'high_fever', 'severe_headache']
    severity_count = sum(1 for symptom in symptoms if any(severe in symptom.lower() for severe in severe_symptoms))
    
    # Find best matching pattern
    best_match = None
    best_score = 0
    best_disease = ''
    best_confidence = 0.0
    
    symptom_set = set(s.lower().replace(' ', '_').replace('-', '_') for s in symptoms)
    
    for pattern, (disease, confidence) in patterns.items():
        pattern_set = set(pattern)
        match_count = len(symptom_set.intersection(pattern_set))
        match_score = match_count / len(pattern_set) if pattern_set else 0
        
        if match_score > best_score:
            best_score = match_score
            best_match = pattern
            best_disease = disease
            best_confidence = confidence
    
    # If no good match, use default
    if best_score < 0.3:
        best_disease = 'Common Cold'
        best_confidence = 0.65
    
    # Calculate fuzzy risk
    risk_result = calculate_fuzzy_risk(
        confidence=best_confidence,
        symptom_count=len(symptoms),
        severity_factors=severity_count,
        age=patient_age
    )
    
    # Generate explanation
    explanation = f"""
Based on analysis of {len(symptoms)} symptoms, the most likely condition is {best_disease}.
The prediction confidence is {best_confidence:.1%}.

Fuzzy Risk Analysis:
- Low risk membership: {risk_result['fuzzy_membership']['low']:.1%}
- Medium risk membership: {risk_result['fuzzy_membership']['medium']:.1%}
- High risk membership: {risk_result['fuzzy_membership']['high']:.1%}

Severity factors detected: {severity_count}
"""
    
    return {
        'success': True,
        'prediction': best_disease,
        'confidence': best_confidence,
        'confidence_score': best_confidence,
        'risk_level': risk_result['risk_level'],
        'risk_score': risk_result['risk_score'],
        'fuzzy_membership': risk_result['fuzzy_membership'],
        'components': risk_result['components'],
        'explanation': explanation,
        'symptoms_analyzed': len(symptoms),
        'severe_symptoms_count': severity_count,
        'recommendations': get_recommendations(best_disease, risk_result['risk_level'], best_confidence)
    }

def generate_explanation(prediction, symptoms, confidence, risk_result):
    """Generate explanation for prediction with fuzzy logic details"""
    
    explanation = f"""
## Analysis Results

**Prediction:** {prediction}
**Confidence Score:** {confidence:.1%}

### Risk Assessment
**Overall Risk Level:** {risk_result['risk_level'].upper()}
**Risk Score:** {risk_result['risk_score']:.3f}

### Fuzzy Logic Breakdown
The system uses fuzzy logic to determine risk levels:

- **Low Risk Membership:** {risk_result['fuzzy_membership']['low']:.1%}
- **Medium Risk Membership:** {risk_result['fuzzy_membership']['medium']:.1%}
- **High Risk Membership:** {risk_result['fuzzy_membership']['high']:.1%}

### Contributing Factors
- Base Confidence: {risk_result['components']['base_risk']:.3f}
- Symptom Count Factor: {risk_result['components']['symptom_factor']:.3f}
- Severity Factor: {risk_result['components']['severity_factor']:.3f}
- Age Factor: {risk_result['components']['age_factor']:.3f}

### Analysis Details
- Symptoms analyzed: {len(symptoms)}
- Prediction made using machine learning with fuzzy logic inference
- Risk assessment considers multiple factors including symptom severity and patient age

**Note:** This analysis is for informational purposes only. Please consult with a healthcare professional for proper diagnosis and treatment.
"""
    
    return explanation

def get_recommendations(prediction, risk_level, confidence):
    """Get recommendations based on prediction and risk level"""
    recommendations = []
    
    # Base recommendations
    recommendations.append("Consult with a healthcare professional for proper diagnosis")
    recommendations.append("Monitor symptoms closely and note any changes")
    recommendations.append("Get adequate rest and stay hydrated")
    
    # Risk-specific recommendations
    if risk_level == 'critical':
        recommendations.insert(0, "🚨 SEEK EMERGENCY MEDICAL CARE IMMEDIATELY")
        recommendations.append("Do not delay seeking medical attention")
        recommendations.append("Call emergency services if symptoms worsen")
    
    elif risk_level == 'high':
        recommendations.insert(0, "🔴 URGENT: Schedule appointment within 24 hours")
        recommendations.append("Avoid strenuous activities")
        recommendations.append("Monitor vital signs regularly")
    
    elif risk_level == 'medium':
        recommendations.insert(0, "🟡 Schedule appointment within 48-72 hours")
        recommendations.append("Consider follow-up tests as advised")
        recommendations.append("Keep a symptom diary")
    
    else:  # low risk
        recommendations.insert(0, "🟢 Schedule routine check-up when convenient")
        recommendations.append("Practice preventive measures")
        recommendations.append("Follow up if symptoms persist beyond 7 days")
    
    # Condition-specific recommendations
    if 'influenza' in prediction.lower() or 'flu' in prediction.lower():
        recommendations.append("Consider antiviral medication if within 48 hours of symptom onset")
        recommendations.append("Isolate to prevent spread to others")
    
    if 'covid' in prediction.lower():
        recommendations.append("Get tested for COVID-19")
        recommendations.append("Isolate for at least 5 days")
        recommendations.append("Monitor oxygen saturation levels")
    
    if 'cardiac' in prediction.lower() or 'chest pain' in prediction.lower():
        recommendations.append("Avoid physical exertion")
        recommendations.append("Monitor blood pressure and heart rate")
    
    # High confidence specific
    if confidence > 0.85:
        recommendations.append("High confidence in prediction - consider targeted treatment")
    
    return recommendations

# ============================================
# LOGGING FUNCTIONS
# ============================================

def log_event(action, user=None, details=None, request=None):
    """Log an audit event"""
    log_entry = AuditLog(
        user=user,
        action=action,
        details=details or {}
    )
    
    if request:
        log_entry.ip_address = request.META.get('REMOTE_ADDR')
        log_entry.user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    log_entry.save()
    return log_entry

# ============================================
# EMAIL FUNCTIONS
# ============================================

def send_approval_email(user):
    """Send account approval email"""
    try:
        subject = 'Your Account Has Been Approved'
        message = f"""
Dear {user.get_full_name() or user.username},

Your account has been approved by the administrator.

You can now login to the Medical Decision Support System at:
{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/login/

Role: {user.get_role_display()}

Best regards,
Medical Decision Support System Team
"""
        
        send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Approval email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send approval email: {e}")
        return False

def send_welcome_email(user):
    """Send welcome email after registration"""
    try:
        subject = 'Welcome to Medical Decision Support System'
        message = f"""
Dear {user.get_full_name() or user.username},

Thank you for registering with the Medical Decision Support System.

Your account is pending administrator approval. You will receive 
another email once your account is approved.

Registration Details:
- Username: {user.username}
- Role: {user.get_role_display()}
- Status: Pending Approval

If you have any questions, please contact support.

Best regards,
Medical Decision Support System Team
"""
        
        send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        return False

def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    try:
        reset_url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/reset-password/{reset_token}/"
        
        subject = 'Password Reset Request'
        message = f"""
Dear {user.get_full_name() or user.username},

You have requested to reset your password.

Click the link below to reset your password:
{reset_url}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
Medical Decision Support System Team
"""
        
        send_mail(
            subject,
            message.strip(),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False

# ============================================
# UTILITY FUNCTIONS
# ============================================

def calculate_fuzzy_risk_simple(confidence, age=35, severity_factors=0):
    """Simple fuzzy risk calculation (for backward compatibility)"""
    result = calculate_fuzzy_risk(confidence, 1, severity_factors, age)
    return result['risk_level']

def similarity_search(query_vector, threshold=0.7, max_results=10):
    """Simplified similarity search (for backward compatibility)"""
    # This is a placeholder function
    # In production, implement actual similarity search
    return []