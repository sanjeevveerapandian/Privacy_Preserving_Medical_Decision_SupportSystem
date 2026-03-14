import os
from celery import shared_task
from django.conf import settings
from core.models import MedicalDocument
import logging

logger = logging.getLogger(__name__)

def get_document(document_id):
    try:
        return MedicalDocument.objects.get(id=document_id)
    except:
        return MedicalDocument.objects.get(document_id=document_id)

@shared_task
def process_mri_ai(document_id, temp_file_path):
    """Process MRI Brain Tumor AI"""
    try:
        from emr.mri_inference import predict_mri_image, generate_mri_gradcam, get_mri_summary
        from core.services.emr_service import EMRProcessor
        
        document = get_document(document_id)
        document.ai_status = 'Processing'
        document.save(update_fields=['ai_status'])
        
        if not os.path.exists(temp_file_path):
            document.ai_status = 'Failed'
            document.save()
            return "Error: Temp file not found"

        # 1. Run AI Inference
        result = predict_mri_image(temp_file_path)
        document.ai_prediction = result.get('prediction')
        document.ai_confidence = result.get('confidence')
        
        # Encrypt summary for security
        raw_summary = get_mri_summary(document.ai_prediction, document.ai_confidence)
        from core.services.crypto_service import encrypt_data
        import base64
        encrypted_bytes = encrypt_data({'summary': raw_summary})
        document.ai_summary = base64.b64encode(encrypted_bytes).decode('utf-8')
        
        # 2. Generate visualization
        heatmap_rel_path = generate_mri_gradcam(temp_file_path)
        if heatmap_rel_path:
            document.ai_heatmap = heatmap_rel_path
            
        document.save()
        
        # 3. Secure and Finalize
        finalize_document(document, temp_file_path)
        return f"Success: Processed MRI {document_id}"

    except Exception as e:
        handle_task_error(document_id, e)
        return f"Error: {e}"

@shared_task
def process_xray_ai(document_id, temp_file_path):
    """Unified Smart X-Ray AI (Pneumonia + Fracture Detection)"""
    try:
        from emr.xray_pneumonia_inference import predict_xray_pneumonia, generate_pneumonia_gradcam, get_pneumonia_summary
        from emr.xray_fracture_inference import predict_xray_fracture, generate_fracture_overlay, get_fracture_summary
        
        document = get_document(document_id)
        document.ai_status = 'Processing'
        document.save(update_fields=['ai_status'])
        
        if not os.path.exists(temp_file_path):
            document.ai_status = 'Failed'
            document.save()
            return "Error: Temp file not found"

        # 1. Run Bone Fracture Detection (YOLOv8)
        frac_result = predict_xray_fracture(temp_file_path)
        
        document.extracted_data = {
            'fracture': frac_result
        }
        
        frac_pred = frac_result.get('prediction', '')
        
        if frac_pred == "fracture detected":
            document.ai_prediction = "Fracture Detected"
            document.ai_confidence = frac_result.get('confidence', 0)
            overlay = generate_fracture_overlay(temp_file_path)
            if overlay: document.ai_heatmap = overlay
            raw_summary = get_fracture_summary(frac_pred, document.ai_confidence, frac_result.get('detections', []))
        elif frac_pred == "Error":
            document.ai_prediction = "Analysis Error"
            document.ai_confidence = 0
            raw_summary = "AI encountered an error during bone analysis. Manual radiologist review is required."
        else:
            document.ai_prediction = "Normal (No Fracture)"
            document.ai_confidence = frac_result.get('confidence', 90)
            if document.ai_confidence < 95:
                 raw_summary = f"AI analysis indicates no clear signs of bone fractures (Confidence: {document.ai_confidence}%). Note: Subtle or complex displacements may require manual clinical correlation."
            else:
                 raw_summary = "AI analysis indicates no high-confidence signs of bone fractures. The scanned structural integrity appears intact."

        # Encrypt summary for security
        from core.services.crypto_service import encrypt_data
        import base64
        encrypted_bytes = encrypt_data({'summary': raw_summary})
        document.ai_summary = base64.b64encode(encrypted_bytes).decode('utf-8')

        document.save()
        
        # 4. Secure and Finalize
        finalize_document(document, temp_file_path)
        return f"Success: Processed Smart X-Ray {document_id}"

    except Exception as e:
        handle_task_error(document_id, e)
        return f"Error: {e}"

def finalize_document(document, temp_file_path):
    """Helper to encrypt and cleanup"""
    from core.services.emr_service import EMRProcessor
    with open(temp_file_path, 'rb') as f:
        class FileWrapper:
            def __init__(self, fh, name):
                self.fh = fh
                self.name = name
            def read(self): return self.fh.read()
            def __getattr__(self, name): return getattr(self.fh, name)

        upload_result = EMRProcessor().save_encrypted_document(
            FileWrapper(f, document.original_filename), 
            document.document_type, 
            document.patient.id
        )
        
    if upload_result.get('success'):
        document.encrypted_filename = upload_result['encrypted_filename']
        document.file_size = upload_result['file_size']
        document.processing_status = 'processed'
        document.is_processed = True
        document.ai_status = 'Completed'
        document.save()
        os.remove(temp_file_path)
    else:
        document.ai_status = 'Failed'
        document.save()

def handle_task_error(document_id, error):
    logger.error(f"Task error for {document_id}: {error}")
    try:
        document = get_document(document_id)
        document.ai_status = 'Failed'
        document.save()
    except:
        pass
