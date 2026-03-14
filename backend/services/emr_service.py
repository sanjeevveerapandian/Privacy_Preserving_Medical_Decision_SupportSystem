# backend/services/emr_service.py

import os
import base64
import json
import re
from datetime import datetime
import tempfile
import traceback
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Try to import OCR libraries (optional)
# OCR setup
OCR_AVAILABLE = False
POPPLER_PATH = None

try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path

    # Windows configuration
    if os.name == 'nt':
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                OCR_AVAILABLE = True
                break

        # Poppler for Windows
        poppler_bin = r"C:\poppler\Library\bin"
        if os.path.exists(poppler_bin):
            POPPLER_PATH = poppler_bin
        else:
            raise RuntimeError("Poppler not found at C:\\poppler\\Library\\bin")

    else:
        # Linux / Mac
        OCR_AVAILABLE = True

except Exception as e:
    OCR_AVAILABLE = False
    print("OCR initialization failed:", e)

# Import crypto service
try:
    from backend.services.crypto_service import (
        encrypt_data, decrypt_data, encrypt_file_content, decrypt_file_content,
        store_encrypted_emr, load_encrypted_emr
    )
except ImportError:
    # Fallback if crypto_service doesn't exist
    from cryptography.fernet import Fernet
    import json
    
    # Simple fallback encryption
    class SimpleCrypto:
        def __init__(self):
            key = b'default_key_for_dev_only_change_in_production='
            self.fernet = Fernet(base64.urlsafe_b64encode(key.ljust(32)[:32]))
        
        def encrypt_data(self, data):
            json_data = json.dumps(data).encode()
            return self.fernet.encrypt(json_data)
        
        def decrypt_data(self, token):
            decrypted = self.fernet.decrypt(token)
            return json.loads(decrypted.decode())
        
        def encrypt_file_content(self, content):
            return self.encrypt_data({"file_content": base64.b64encode(content).decode('utf-8')})
        
        def decrypt_file_content(self, encrypted):
            data = self.decrypt_data(encrypted)
            return base64.b64decode(data["file_content"])
    
    crypto = SimpleCrypto()
    encrypt_data = crypto.encrypt_data
    decrypt_data = crypto.decrypt_data
    encrypt_file_content = crypto.encrypt_file_content
    decrypt_file_content = crypto.decrypt_file_content


class EMRProcessor:
    """Service for processing EMR documents"""
    
    def __init__(self):
        self.upload_dir = os.path.join(settings.MEDIA_ROOT, 'emr_documents')
        os.makedirs(self.upload_dir, exist_ok=True)
        
        # Medical entity patterns
        self.patterns = {
            'diagnosis': re.compile(r'(diagnosis|dx|diagnosed)[:\s]+(.+)', re.IGNORECASE),
            'medication': re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(\d+)\s*(mg|g|ml|mcg)\s*(?:oral|iv|im)?\s*(\d+)\s*(?:times|x)\s*(?:daily|weekly|monthly)?', re.IGNORECASE),
            'lab_result': re.compile(r'([A-Za-z\s]+):?\s+([\d\.]+)\s*(?:mg/dL|mmol/L|g/dL|U/L)?', re.IGNORECASE),
            'symptom': re.compile(r'(fever|cough|pain|headache|nausea|fatigue|weakness|shortness of breath|vomiting|diarrhea|rash|chills|sweating|dizziness|chest pain|abdominal pain|back pain)', re.IGNORECASE),
            'vital_sign': re.compile(r'(BP|Blood Pressure):?\s*(\d+)/(\d+)|(HR|Heart Rate):?\s*(\d+)|(Temp|Temperature):?\s*([\d\.]+)', re.IGNORECASE),
        }
    
    def save_encrypted_document(self, file_obj, document_type, patient_id):
        """Save document with encryption"""
        try:
            # Read file content
            file_content = file_obj.read()
            original_filename = file_obj.name
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            encrypted_filename = f"{patient_id}_{document_type}_{timestamp}.enc"
            
            # Encrypt file content
            encrypted_content = encrypt_file_content(file_content)
            
            # Save encrypted file
            file_path = os.path.join(self.upload_dir, encrypted_filename)
            with open(file_path, 'wb') as f:
                f.write(encrypted_content)
            
            return {
                'success': True,
                'encrypted_filename': encrypted_filename,
                'file_path': file_path,
                'original_filename': original_filename,
                'file_size': len(file_content),
                'mime_type': getattr(file_obj, 'content_type', 'application/octet-stream')
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def extract_text_from_document(self, file_path, file_type):
        """Extract text from various document types"""
        try:
            if not OCR_AVAILABLE:
                return {
                    "success": False,
                    "error": "OCR not available. Please install Tesseract OCR and required Python packages.",
                    "text": "",
                    "text_length": 0
                }
            
            text = ""
            file_ext = file_type.lower().replace('.', '')
            
            if file_ext == 'pdf':
                # Convert PDF to images and extract text
                try:
                    images = convert_from_path(
                        file_path,
                        poppler_path=POPPLER_PATH
                    )
                    for image in images:
                        text += pytesseract.image_to_string(image) + "\n"
                except Exception as e:
                    error_msg = str(e)
                    if "poppler" in error_msg.lower():
                        return {
                            "success": False,
                            "error": "PDF processing requires poppler. Please install Poppler.",
                            "text": "",
                            "text_length": 0
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"PDF processing error: {error_msg}",
                            "text": "",
                            "text_length": 0
                        }
            
            elif file_ext in ['jpg', 'jpeg', 'png', 'tiff', 'bmp']:
                # Extract text from image
                try:
                    image = Image.open(file_path)
                    text = pytesseract.image_to_string(image)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Image processing error: {str(e)}",
                        "text": "",
                        "text_length": 0
                    }
            
            else:
                return {
                    "success": False, 
                    "error": f"Unsupported file type: {file_type}",
                    "text": "",
                    "text_length": 0
                }
            
            return {
                "success": True,
                "text": text.strip(),
                "text_length": len(text)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "text": "",
                "text_length": 0
            }
    
    def extract_medical_entities(self, text):
        """Extract medical entities from text"""
        entities = {
            'diagnoses': [],
            'medications': [],
            'lab_results': [],
            'symptoms': [],
            'vital_signs': [],
        }
        
        try:
            # Extract diagnoses
            diagnoses = self.patterns['diagnosis'].findall(text)
            for match in diagnoses:
                if len(match) > 1 and match[1].strip():
                    entities['diagnoses'].append(match[1].strip())
            
            # Extract symptoms
            symptoms = set()
            for match in self.patterns['symptom'].finditer(text):
                if match.group(1):
                    symptoms.add(match.group(1).lower())
            
            if symptoms:
                entities['symptoms'] = list(symptoms)
            
            # Extract medications
            medications = self.patterns['medication'].findall(text)
            for match in medications:
                if match and len(match) >= 2:
                    entities['medications'].append({
                        'name': match[0],
                        'dosage': f"{match[1]} {match[2]}" if len(match) > 2 else match[1],
                        'frequency': match[3] if len(match) > 3 else 'daily'
                    })
            
            # Extract vital signs
            vital_signs = []
            for match in self.patterns['vital_sign'].finditer(text):
                if match.group(1):  # Blood Pressure
                    vital_signs.append(f"BP: {match.group(2)}/{match.group(3)}")
                elif match.group(4):  # Heart Rate
                    vital_signs.append(f"HR: {match.group(5)} bpm")
                elif match.group(6):  # Temperature
                    vital_signs.append(f"Temp: {match.group(7)}°C")
            
            if vital_signs:
                entities['vital_signs'] = vital_signs
            
            return entities
            
        except Exception as e:
            print(f"[EMR] Error extracting entities: {e}")
            return entities  # Return empty entities if extraction fails
    
    def process_document(self, document_id, auto_extract=True):
        """Process document: extract text and entities"""
        try:
            from core.models import MedicalDocument, EMRExtractionLog
            
            document = MedicalDocument.objects.get(document_id=document_id)
            
            # Decrypt file for processing
            encrypted_file_path = os.path.join(self.upload_dir, document.encrypted_filename)
            
            if not os.path.exists(encrypted_file_path):
                raise Exception(f"Encrypted file not found: {encrypted_file_path}")
            
            with open(encrypted_file_path, 'rb') as f:
                encrypted_content = f.read()
            
            start_time = datetime.now()
            
            # Create temporary file
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.temp') as tmp_file:
                    decrypted_content = decrypt_file_content(encrypted_content)
                    tmp_file.write(decrypted_content)
                    temp_path = tmp_file.name
                
                # Extract text
                file_ext = os.path.splitext(document.original_filename)[1].lower()
                extraction_result = self.extract_text_from_document(temp_path, file_ext)
                
            finally:
                # Clean up temp file
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            
            if not extraction_result['success']:
                raise Exception(f"Text extraction failed: {extraction_result.get('error', 'Unknown error')}")
            
            extracted_text = extraction_result['text']
            
            # Extract medical entities
            entities = self.extract_medical_entities(extracted_text) if auto_extract else {}
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Update document
            if extracted_text:
                encrypted_text_bytes = encrypt_data({'text': extracted_text})
                document.extracted_text = base64.b64encode(encrypted_text_bytes).decode('utf-8')
            else:
                document.extracted_text = ''
            
            if entities:
                encrypted_entities_bytes = encrypt_data(entities)
                document.extracted_data = base64.b64encode(encrypted_entities_bytes).decode('utf-8')
            else:
                document.extracted_data = ''
            
            document.is_processed = True
            document.processing_status = 'processed'
            document.save()
            
            # Create extraction log
            EMRExtractionLog.objects.create(
                document=document,
                extraction_method='OCR' if file_ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp'] else 'PDF+OCR',
                processing_time=processing_time,
                success=True,
                text_length=len(extracted_text),
                entities_found=len([k for k, v in entities.items() if v])
            )
            
            return {
                'success': True,
                'document_id': str(document.document_id),
                'text_length': len(extracted_text),
                'entities_found': entities,
                'processing_time': processing_time
            }
            
        except Exception as e:
            error_trace = traceback.format_exc()
            
            # Update document status
            if 'document' in locals():
                document.processing_status = 'failed'
                document.save()
                
                # Log failure
                EMRExtractionLog.objects.create(
                    document=document,
                    extraction_method='OCR',
                    processing_time=0,
                    success=False,
                    error_message=str(e),
                    error_details=error_trace[:500]  # Limit error details
                )
            
            return {
                'success': False,
                'error': str(e),
                'traceback': error_trace
            }
        

    # backend/services/emr_service.py - Update the predict_from_emr method:

def predict_from_emr(self, document_id):
    """Generate predictions from EMR data"""
    try:
        from core.models import MedicalDocument, EMRPrediction
        
        document = MedicalDocument.objects.get(document_id=document_id)
        
        # Decrypt extracted data
        extracted_data = {}
        if document.extracted_data and document.extracted_data.strip():
            try:
                # Handle both base64 encoded string and direct bytes
                if isinstance(document.extracted_data, str) and document.extracted_data.strip():
                    encrypted_bytes = base64.b64decode(document.extracted_data)
                    extracted_data = decrypt_data(encrypted_bytes)
                else:
                    extracted_data = decrypt_data(document.extracted_data)
            except Exception as e:
                print(f"[EMR] Decrypt error: {e}")
                extracted_data = {}

        # Get symptoms from extracted data
        symptoms_list = []
        if extracted_data and 'symptoms' in extracted_data:
            symptoms_list = extracted_data['symptoms']
        
        # Also extract symptoms from text if available
        if not symptoms_list and document.extracted_text:
            try:
                # Try to extract symptoms from raw text
                import re
                # Common symptoms pattern
                symptom_patterns = [
                    r'\b(headache|migraine)\b',
                    r'\b(fever|temperature)\b',
                    r'\b(cough|sneeze)\b',
                    r'\b(pain|ache)\b',
                    r'\b(nausea|vomit)\b',
                    r'\b(fatigue|tired)\b',
                    r'\b(dizziness|vertigo)\b',
                    r'\b(shortness of breath|breathless)\b',
                    r'\b(rash|itching)\b',
                    r'\b(diarrhea|diarrhoea)\b',
                ]
                
                encrypted_text_bytes = base64.b64decode(document.extracted_text)
                text_data = decrypt_data(encrypted_text_bytes)
                text_content = text_data.get('text', '').lower()
                
                found_symptoms = set()
                for pattern in symptom_patterns:
                    matches = re.findall(pattern, text_content)
                    if matches:
                        found_symptoms.update(matches)
                
                if found_symptoms:
                    symptoms_list = list(found_symptoms)
            except Exception as e:
                print(f"[EMR] Error extracting symptoms from text: {e}")

        print(f"[EMR] Final symptoms list for prediction: {symptoms_list}")

        if not symptoms_list:
            print("[EMR] No symptoms found, using default consultation prediction")
            # Return a thoughtful prediction when no symptoms are found
            return {
                'success': True,
                'prediction_id': 'no_symptoms_prediction',
                'prediction': "Routine Medical Checkup Recommended",
                'confidence': 40.0,
                'risk_level': "Low",
                'explanation': "No specific symptoms were detected in the document. This suggests either a routine checkup or that the document may not contain symptom information. A general medical consultation is recommended.",
                'symptoms': [],
                'confidence_percentage': "40.0%",
                'note': "No symptoms detected in document"
            }

        # Prepare input for ML
        ml_input = {}
        for symptom in symptoms_list:
            if isinstance(symptom, str) and symptom.strip():
                ml_input[symptom.strip().lower()] = 1

        # Call prediction - handle model errors gracefully
        try:
            from backend.services.ml_service import predict
            ml_result = predict(ml_input)
            
            print(f"[EMR] ML result: {ml_result}")
            
            # Ensure all required fields are present
            if 'prediction' not in ml_result:
                ml_result['prediction'] = "Medical Consultation Required"
            
            if 'confidence' not in ml_result:
                ml_result['confidence'] = 50.0
            elif isinstance(ml_result['confidence'], (int, float)):
                # Ensure confidence is properly formatted
                ml_result['confidence'] = float(ml_result['confidence'])
            else:
                ml_result['confidence'] = 50.0
            
            if 'risk_level' not in ml_result:
                ml_result['risk_level'] = "Medium"
            
            if 'llm_explanation' not in ml_result or not ml_result['llm_explanation']:
                ml_result['llm_explanation'] = generate_default_explanation(
                    ml_result['prediction'], 
                    ml_result['confidence'],
                    symptoms_list
                )
            
            if 'symptoms_used' not in ml_result:
                ml_result['symptoms_used'] = symptoms_list
            
        except Exception as e:
            print(f"[EMR] ML predict failed with error: {str(e)}")
            ml_result = {
                "prediction": "Medical Analysis Required",
                "confidence": 30.0,
                "risk_level": "Low",
                "llm_explanation": f"AI analysis encountered an error. Based on detected symptoms ({', '.join(symptoms_list[:3])}), a medical consultation is recommended. Please have a healthcare professional review this document.",
                "symptoms_used": symptoms_list,
                "model_status": "error"
            }

        # Save to database
        try:
            prediction = EMRPrediction.objects.create(
                document=document,
                patient=document.patient,
                predicted_conditions=[ml_result['prediction']],
                confidence_scores={ml_result['prediction']: ml_result['confidence']},
                risk_level=ml_result['risk_level'],
                symptoms_detected=symptoms_list,
                llm_analysis=ml_result.get('llm_explanation', ''),
                model_status=ml_result.get('model_status', 'primary')
            )
            prediction_id = str(prediction.prediction_id)
        except Exception as e:
            print(f"[EMR] Error saving prediction: {e}")
            prediction_id = "unsaved"

        return {
            'success': True,
            'prediction_id': prediction_id,
            'prediction': ml_result['prediction'],
            'confidence': ml_result['confidence'],
            'risk_level': ml_result['risk_level'],
            'symptoms': symptoms_list,
            'explanation': ml_result.get('llm_explanation', ''),
            'confidence_percentage': f"{ml_result['confidence']:.1f}%",
            'model_status': ml_result.get('model_status', 'primary')
        }

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[EMR] Full error in predict_from_emr: {e}\n{error_trace}")
        return {
            'success': False,
            'error': str(e),
            'traceback': error_trace
        }

def generate_default_explanation(prediction, confidence, symptoms):
    """Generate a default explanation when LLM fails"""
    symptom_str = ", ".join(symptoms[:5]) if symptoms else "general symptoms"
    return f"Based on analysis of {symptom_str}, this suggests {prediction.lower()} with {confidence:.1f}% confidence. This is an AI-generated suggestion for informational purposes only. Always consult with a healthcare professional for proper diagnosis and treatment."







