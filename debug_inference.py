import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medical_assistant.settings')
django.setup()

from emr.ai_inference import predict_image, get_model, CLASS_NAMES
from core.services.emr_service import decrypt_file_content
from core.models import MedicalDocument
import torch
from torchvision import transforms
from PIL import Image
import tempfile

doc = MedicalDocument.objects.filter(document_type='mri', ai_prediction='notumor').order_by('-upload_date').first()

if doc and doc.encrypted_filename:
    print(f"Testing encrypted doc ID: {doc.document_id}")
    file_path = os.path.join('media', 'emr_documents', doc.encrypted_filename)
    
    if os.path.exists(file_path):
        import traceback
        try:
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = decrypt_file_content(encrypted_data)
            
            fd, temp_path = tempfile.mkstemp(suffix='.jpg')
            os.write(fd, decrypted_data)
            os.close(fd)
            
            print(f"File successfully decrypted to {temp_path}")
            
            model_container = get_model()
            image = Image.open(temp_path).convert('RGB')
            input_tensor = model_container.transform(image).unsqueeze(0)
            
            with torch.no_grad():
                outputs = model_container.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
            
            print("\nRaw File Inference:")
            for i, p in enumerate(probabilities):
                print(f"Class {i} ({CLASS_NAMES[i]}): {p.item()*100:.2f}%")
                
            os.remove(temp_path)
            
        except Exception as e:
            print(traceback.format_exc())
    else:
        print(f"Encrypted file missing at {file_path}")
else:
    print("No recent notumor docs found")
