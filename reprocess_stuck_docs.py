import os
import django
import tempfile
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import MedicalDocument
from core.services.emr_service import decrypt_file_content
from emr.tasks import process_xray_ai

# Find documents that were stuck or just reset to Pending
docs = MedicalDocument.objects.filter(id__in=[46, 47])

for doc in docs:
    print(f"Re-processing Doc ID {doc.id}: {doc.original_filename}")
    
    if not doc.encrypted_filename:
        print(f"  Error: No encrypted file for doc {doc.id}")
        continue
        
    file_path = os.path.join('media', 'emr_documents', doc.encrypted_filename)
    if not os.path.exists(file_path):
        print(f"  Error: Encrypted file missing at {file_path}")
        continue
        
    with open(file_path, 'rb') as f:
        encrypted_data = f.read()
    
    try:
        decrypted_data = decrypt_file_content(encrypted_data)
        
        # Create a temp file for the task to swallow
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(doc.original_filename)[1], delete=False) as tmp:
            tmp.write(decrypted_data)
            temp_path = tmp.name
        
        print(f"  Enqueuing task for {temp_path}...")
        # We call the task directly or via delay. 
        # Since we want to see immediate results and we are in a script, let's use delay to let the worker do it.
        process_xray_ai.delay(doc.id, temp_path)
        print(f"  Successfully re-enqueued doc {doc.id}")
        
    except Exception as e:
        print(f"  Error processing doc {doc.id}: {e}")

print("Done.")
