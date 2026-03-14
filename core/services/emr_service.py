# backend/services/emr_service.py

import os
import base64
import json
import re
from datetime import datetime
import tempfile
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Try to import OCR libraries (optional)
try:
    import pytesseract
    from PIL import Image
    import pdf2image
    
    # Set Tesseract path for Windows
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            OCR_AVAILABLE = True
        else:
            OCR_AVAILABLE = False
            print(f"Tesseract not found at {tesseract_path}")
    else:  # Linux/Mac
        OCR_AVAILABLE = True
        
    # Poppler path for Windows (used by pdf2image)
    POPPLER_PATH = None
    if os.name == 'nt':
        POPPLER_PATH = r'C:\poppler\Library\bin'
        
except ImportError:
    OCR_AVAILABLE = False
    print("OCR libraries not installed. Install with: pip install Pillow pytesseract pdf2image")

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
            'symptom': re.compile(r'(fever|cough|pain|headache|nausea|fatigue|weakness|shortness of breath|vomiting|diarrhea|rash)', re.IGNORECASE),
            'vital_sign': re.compile(r'(BP|Blood Pressure):?\s*(\d+)/(\d+)|(HR|Heart Rate):?\s*(\d+)|(Temp|Temperature):?\s*([\d\.]+)', re.IGNORECASE),
        }
    
    def save_encrypted_document(self, file_obj, document_type, patient_id):
        """Save document with encryption"""
        try:
            # Read file content
            file_content = file_obj.read()
            original_filename = file_obj.name
            
            # Generate completely random filename (Metadata Encryption)
            import uuid
            encrypted_filename = f"{uuid.uuid4()}.enc"
            
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
            import traceback
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
                    images = pdf2image.convert_from_path(
                        file_path,
                        poppler_path=POPPLER_PATH  # This fixes the Poppler error on Windows
                    )
                    for image in images:
                        text += pytesseract.image_to_string(image) + "\n"
                except Exception as e:
                    error_msg = str(e)
                    if "poppler" in error_msg.lower() or "page count" in error_msg.lower():
                        return {
                            "success": False,
                            "error": "PDF processing requires poppler. Check that POPPLER_PATH is correct and Poppler is installed.",
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
            import traceback
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
                if len(match) > 1:
                    entities['diagnoses'].append(match[1].strip())
            
            # Extract medications
            medications = self.patterns['medication'].findall(text)
            for match in medications:
                if match and len(match) >= 2:
                    entities['medications'].append({
                        'name': match[0],
                        'dosage': f"{match[1]} {match[2]}" if len(match) > 2 else match[1],
                        'frequency': match[3] if len(match) > 3 else 'daily'
                    })
            
            # Extract symptoms
            symptoms = self.patterns['symptom'].findall(text)
            if symptoms:
                entities['symptoms'] = list(set([s for s in symptoms if s]))
            
            return entities
            
        except Exception as e:
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
            
            # Update document - ENSURE DATA IS JSON-SERIALIZABLE
            if extracted_text:
                # Convert encrypted bytes to base64 string for JSON serialization
                encrypted_text_bytes = encrypt_data({'text': extracted_text})
                document.extracted_text = base64.b64encode(encrypted_text_bytes).decode('utf-8')
            else:
                document.extracted_text = ''
            
            if entities:
                # Convert encrypted bytes to base64 string for JSON serialization
                encrypted_entities_bytes = encrypt_data(entities)
                document.extracted_data = base64.b64encode(encrypted_entities_bytes).decode('utf-8')
            else:
                # Use empty string instead of encrypt_data({})
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
                entities_found=list(entities.keys())
            )
            
            # Convert entities to JSON-serializable format
            serializable_entities = {}
            for key, value in entities.items():
                if isinstance(value, list):
                    serializable_entities[key] = value
                else:
                    serializable_entities[key] = str(value)
            
            return {
                'success': True,
                'document_id': str(document.document_id),
                'text_length': len(extracted_text),
                'entities_found': serializable_entities,
                'processing_time': processing_time
            }
            
        except Exception as e:
            import traceback
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
                    error_details={'traceback': error_trace}
                )
            
            return {
                'success': False,
                'error': str(e),
                'traceback': error_trace
            }
    
    def predict_from_emr(self, document_id):
        """Generate predictions from EMR data"""
        try:
            from core.models import MedicalDocument, EMRPrediction
            
            document = MedicalDocument.objects.get(document_id=document_id)
            
            # Get extracted data - handle base64 decoding
            extracted_data = {}
            if document.extracted_data:
                try:
                    import base64
                    
                    # Check if extracted_data is base64 encoded string
                    if isinstance(document.extracted_data, str) and document.extracted_data.strip():
                        # Decode base64 string back to bytes
                        encrypted_bytes = base64.b64decode(document.extracted_data)
                        extracted_data = decrypt_data(encrypted_bytes)
                    else:
                        # Try to decrypt directly (for backward compatibility)
                        extracted_data = decrypt_data(document.extracted_data)
                except Exception as e:
                    print(f"Error decrypting extracted data for prediction: {e}")
                    extracted_data = {'symptoms': []}
            else:
                extracted_data = {'symptoms': []}
            
            symptoms_list = extracted_data.get('symptoms', [])
            
            # Convert symptoms to ML model format
            ml_input = {}
            symptom_mapping = {
                'fever': 'high_fever',
                'cough': 'cough',
                'headache': 'headache',
                'nausea': 'nausea',
                'fatigue': 'fatigue',
                'pain': 'joint_pain',
                'weakness': 'fatigue',
                'shortness of breath': 'breathlessness',
                'vomiting': 'vomiting',
                'diarrhea': 'diarrhoea',
                'rash': 'skin_rash'
            }
            
            for symptom in symptoms_list:
                mapped_symptom = symptom_mapping.get(symptom.lower())
                if mapped_symptom:
                    ml_input[mapped_symptom] = 1
            
            # Get ML prediction (simulate if not available)
            if ml_input:
                try:
                    from backend.services.ml_service import predict
                    ml_result = predict(ml_input)
                except ImportError:
                    # Simulate prediction for testing
                    ml_result = {
                        'prediction': 'Common Cold',
                        'confidence': 0.75,
                        'risk_level': 'low',
                        'llm_explanation': 'Based on symptoms, this appears to be a common viral infection.'
                    }
                
                # Encrypt LLM analysis for security
                llm_explanation = ml_result.get('llm_explanation', '')
                encrypted_analysis = ""
                if llm_explanation:
                    encrypted_bytes = encrypt_data({'analysis': llm_explanation})
                    encrypted_analysis = base64.b64encode(encrypted_bytes).decode('utf-8')

                # Create EMR prediction record
                prediction = EMRPrediction.objects.create(
                    document=document,
                    patient=document.patient,
                    predicted_conditions=[ml_result['prediction']],
                    confidence_scores={ml_result['prediction']: ml_result['confidence']},
                    risk_level=ml_result['risk_level'],
                    symptoms_detected=symptoms_list,
                    llm_analysis=encrypted_analysis
                )
                
                return {
                    'success': True,
                    'prediction_id': str(prediction.prediction_id),
                    'prediction': ml_result['prediction'],
                    'confidence': ml_result['confidence'],
                    'risk_level': ml_result['risk_level'],
                    'symptoms': symptoms_list
                }
            else:
                # Create a generic prediction if no symptoms detected
                prediction = EMRPrediction.objects.create(
                    document=document,
                    patient=document.patient,
                    predicted_conditions=['No specific condition detected'],
                    confidence_scores={'No condition': 0.5},
                    risk_level='low',
                    symptoms_detected=[],
                    llm_analysis='No specific symptoms detected for analysis.'
                )
                
                return {
                    'success': True,
                    'prediction_id': str(prediction.prediction_id),
                    'prediction': 'No specific condition',
                    'confidence': 0.5,
                    'risk_level': 'low',
                    'symptoms': []
                }
                
        except Exception as e:
            import traceback
            error_msg = str(e)
            if not error_msg:
                error_msg = 'Unknown prediction error'
            
            return {
                'success': False,
                'error': error_msg,
                'traceback': traceback.format_exc()
            }