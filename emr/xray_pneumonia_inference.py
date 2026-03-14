import os
import logging
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import torch.nn.functional as F
import numpy as np
import cv2
import matplotlib
matplotlib.use('Agg')
from django.conf import settings
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

logger = logging.getLogger(__name__)

# Constants
CLASS_NAMES = ['normal', 'pneumonia']
NUM_CLASSES = len(CLASS_NAMES)
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]

class PneumoniaModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PneumoniaModel, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        torch.set_num_threads(1)
        # Based on my inspection, it's a ResNet variant
        self.model = models.resnet18(weights=None)
        num_ftrs = self.model.fc.in_features
        self.model.fc = nn.Linear(num_ftrs, NUM_CLASSES)
        
        model_path = os.path.join(settings.BASE_DIR, 'ai_model', 'xray_pneumonia_model.pth')
        if os.path.exists(model_path):
            state_dict = torch.load(model_path, map_location=torch.device('cpu'))
            self.model.load_state_dict(state_dict)
            self.model.eval()
        
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=NORM_MEAN, std=NORM_STD)
        ])

_pneumonia_model_container = None

def get_pneumonia_model():
    global _pneumonia_model_container
    if _pneumonia_model_container is None:
        _pneumonia_model_container = PneumoniaModel()
    return _pneumonia_model_container

def predict_xray_pneumonia(image_path):
    try:
        model_container = get_pneumonia_model()
        image = Image.open(image_path).convert('RGB')
        input_tensor = model_container.transform(image).unsqueeze(0)
        
        with torch.no_grad():
            outputs = model_container.model(input_tensor)
            probabilities = F.softmax(outputs[0], dim=0)
            
        conf, idx = torch.max(probabilities, 0)
        prediction = CLASS_NAMES[idx]
        confidence = max(0.0, min(100.0, float(conf) * 100))
        
        return {
            "prediction": prediction,
            "confidence": round(confidence, 2)
        }
    except Exception as e:
        logger.error(f"Pneumonia inference error: {e}")
        return {"prediction": "Error", "confidence": 0.0}

def get_pneumonia_summary(prediction, confidence):
    if prediction == 'pneumonia':
        return f"AI analysis detected patterns consistent with Pneumonia (Confidence: {confidence}%). Immediate clinical correlation and antibiotic therapy consideration recommended."
    else:
        return f"No signs of typical pneumonia detected (Confidence: {confidence}%). Lungs appear clear at this resolution."

def generate_pneumonia_gradcam(image_path):
    try:
        model_container = get_pneumonia_model()
        model = model_container.model
        target_layers = [model.layer4[-1]]
        
        image_pil = Image.open(image_path).convert('RGB')
        input_tensor = model_container.transform(image_pil).unsqueeze(0)
        
        with torch.no_grad():
            outputs = model(input_tensor)
            idx = torch.argmax(outputs[0]).item()
        
        targets = [ClassifierOutputTarget(idx)]
        cam = GradCAM(model=model, target_layers=target_layers)
        grayscale_cam = cam(input_tensor=input_tensor, targets=targets)[0, :]
        
        rgb_img = np.array(image_pil.resize((224, 224))).astype(np.float32) / 255
        visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)
        
        heatmap_name = f"heatmap_pneu_{os.path.basename(image_path)}.jpg"
        heatmap_path = os.path.join(settings.HEATMAP_ROOT, heatmap_name)
        
        cv2.imwrite(heatmap_path, cv2.cvtColor((visualization * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        return os.path.join('heatmaps', heatmap_name)
    except Exception as e:
        logger.error(f"Pneumonia Grad-CAM error: {e}")
        return None
