import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from emr.xray_fracture_inference import predict_xray_fracture

test_file = 'media/temp_raw/raw_e77f4253-36db-4630-860a-1fe9dac4b44c_xray.jpeg'
print(f"Testing on {test_file}")
result = predict_xray_fracture(test_file)
print("Result:", result)
