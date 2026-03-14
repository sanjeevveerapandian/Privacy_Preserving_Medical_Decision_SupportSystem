import os
import sys
import django

# Add current directory to path
sys.path.append(os.getcwd())

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import MedicalDocument
from emr.tasks import process_mri_ai

def rescue_scans():
    print("🚀 Starting MRI Deep Rescue Mission...")
    temp_dir = os.path.join("media", "temp_raw")
    if not os.path.exists(temp_dir):
        print(f"❌ Temp directory {temp_dir} does not exist.")
        return

    files = [f for f in os.listdir(temp_dir) if f.startswith("raw_")]
    print(f"📂 Found {len(files)} raw files in temp_raw.")

    for filename in files:
        # Pattern: raw_<uuid>_original_name.ext
        # We need to extract the original name
        parts = filename.split('_', 2)
        if len(parts) < 3:
            continue
        original_name = parts[2]
        
        # Find a document that matches the original name and isn't completed
        doc = MedicalDocument.objects.filter(
            original_filename=original_name,
            document_type='mri'
        ).exclude(ai_status='Completed').first()
        
        if doc:
            full_path = os.path.join(temp_dir, filename)
            print(f"🛠️ Processing file {filename} for Doc {doc.document_id}...")
            try:
                result = process_mri_ai(doc.pk, full_path)
                print(f"   ✅ Done: {result}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print(f"❓ No pending document found for {original_name} (File: {filename})")

if __name__ == "__main__":
    rescue_scans()
