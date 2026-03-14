import os
import sys
import torch
import numpy as np
from PIL import Image

# Add current directory to path
sys.path.append(os.getcwd())

# Mock Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
import django
django.setup()

from django.conf import settings
from emr.ai_inference import predict_image, generate_gradcam

def verify_ai():
    print("🧪 Starting AI Verification...")
    
    # 1. Create a dummy MRI-like image (224x224)
    dummy_path = "media/test_mri.jpg"
    os.makedirs("media", exist_ok=True)
    
    if not os.path.exists(dummy_path):
        dummy_img = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
        Image.fromarray(dummy_img).save(dummy_path)
        print(f"✅ Created dummy image at {dummy_path}")
    
    # 2. Test Prediction
    print("📈 Testing Prediction...")
    result = predict_image(dummy_path)
    print(f"   Result: {result}")
    
    if result.get('prediction') in ['glioma', 'meningioma', 'notumor', 'pituitary']:
        print("✅ Prediction successful.")
    else:
        print("❌ Prediction failed or returned unknown class.")

    # 3. Test Grad-CAM
    print("🗺️ Testing Grad-CAM Generation...")
    heatmap_path = generate_gradcam(dummy_path)
    if heatmap_path and os.path.exists(os.path.join(settings.MEDIA_ROOT, heatmap_path)):
        print(f"✅ Grad-CAM successful. Heatmap saved at: {heatmap_path}")
    else:
        print("❌ Grad-CAM generation failed.")

    print("\n🏁 Verification Complete.")

if __name__ == "__main__":
    verify_ai()
