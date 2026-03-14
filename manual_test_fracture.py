import os
import django
import logging

# Setup logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from emr.xray_fracture_inference import predict_xray_fracture

# Manually test the first image in media/temp_raw
media_dir = 'media/temp_raw'
files = [f for f in os.listdir(media_dir) if f.endswith('.jpeg')]
if files:
    test_file = os.path.join(media_dir, files[0])
    logger.info(f"Testing on {test_file} with current 0.01 threshold...")
    result = predict_xray_fracture(test_file)
    logger.info(f"Result: {result}")
else:
    logger.info("No xray found in temp_raw")
