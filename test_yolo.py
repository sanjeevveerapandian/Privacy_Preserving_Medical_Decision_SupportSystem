import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from emr.xray_fracture_inference import predict_xray_fracture

# Manually test the first image in media/temp_raw
media_dir = 'media/temp_raw'
files = [f for f in os.listdir(media_dir) if f.endswith('.jpeg')]
if files:
    test_file = os.path.join(media_dir, files[0])
    print(f"Testing on {test_file}")
    result = predict_xray_fracture(test_file)
    print("Result:", result)
else:
    print("No xray found in temp_raw")
