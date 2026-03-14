import os
import django
import tempfile
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import MedicalDocument
from core.services.emr_service import decrypt_file_content
from emr.xray_fracture_inference import predict_xray_fracture

# Test the most recent xray
doc = MedicalDocument.objects.filter(document_type='xray_fracture').order_by('-upload_date').first()
if doc and doc.encrypted_filename:
    print(f"Testing Doc: {doc.original_filename} ({doc.encrypted_filename})")
    file_path = os.path.join('media', 'emr_documents', doc.encrypted_filename)
    
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    
    decrypted_data = decrypt_file_content(encrypted_data)
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        tmp.write(decrypted_data)
        tmp_path = tmp.name
    
    print(f"Running inference on {tmp_path} with conf=0.01 and imgsz=1024...")
    result = predict_xray_fracture(tmp_path)
    print(f"Result: {result}")
    
    os.unlink(tmp_path)
else:
    print("No recent xray found.")
