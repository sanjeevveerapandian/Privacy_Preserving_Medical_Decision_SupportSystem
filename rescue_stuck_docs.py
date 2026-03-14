import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import MedicalDocument
from emr.tasks import process_xray_ai

# Map discovered temp files to docs 46 and 47
mapping = {
    46: "media/temp_raw/raw_774e7201-1ebf-43bd-8dc5-b1be292309f4_hand.jpeg",
    47: "media/temp_raw/raw_8079186f-0fa5-4c19-881f-51594881e460_hand.jpeg"
}

for doc_id, temp_path in mapping.items():
    try:
        doc = MedicalDocument.objects.get(id=doc_id)
        abs_temp_path = os.path.abspath(temp_path)
        
        if os.path.exists(abs_temp_path):
            print(f"Rescuing Doc {doc_id} with file {temp_path}")
            doc.ai_status = 'Pending'
            doc.save()
            process_xray_ai.delay(doc.id, abs_temp_path)
            print(f"  Enqueued successfully.")
        else:
            print(f"  File not found for Doc {doc_id}: {abs_temp_path}")
    except Exception as e:
        print(f"  Error rescuing Doc {doc_id}: {e}")
