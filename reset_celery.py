import os
import sys
import django
import redis

# Add current directory to path
sys.path.append(os.getcwd())

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from core.models import MedicalDocument
from django.conf import settings

def reset_and_clear():
    # 1. Reset stuck documents
    stuck_docs = MedicalDocument.objects.filter(ai_status='Processing')
    count = stuck_docs.count()
    stuck_docs.update(ai_status='Failed')
    print(f"✅ Reset {count} stuck documents to 'Failed'.")

    # 2. Clear Redis queue
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.flushall()
        print("✅ Cleared Redis task queue.")
    except Exception as e:
        print(f"❌ Failed to clear Redis: {e}")

if __name__ == "__main__":
    reset_and_clear()
