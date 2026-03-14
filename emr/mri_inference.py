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
CLASS_NAMES = ['glioma', 'meningioma', 'notumor', 'pituitary']
NUM_CLASSES = len(CLASS_NAMES)
NORM_MEAN = [0.485, 0.456, 0.406]
NORM_STD = [0.229, 0.224, 0.225]

class BrainTumorModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrainTumorModel, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        torch.set_num_threads(1)
        self.model = models.resnet18(weights=None)
        num_ftrs = self.model.fc.in_features
        self.model.fc = nn.Linear(num_ftrs, NUM_CLASSES)
        
        model_path = getattr(settings, 'BRAIN_TUMOR_MODEL_PATH', os.path.join(settings.BASE_DIR, 'ai_model', 'best_brain_tumor_model.pth'))
        if os.path.exists(model_path):
            state_dict = torch.load(model_path, map_location=torch.device('cpu'))
            self.model.load_state_dict(state_dict)
            self.model.eval()
        
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=NORM_MEAN, std=NORM_STD)
        ])

_brain_model_container = None

def get_mri_model():
    global _brain_model_container
    if _brain_model_container is None:
        _brain_model_container = BrainTumorModel()
    return _brain_model_container

def predict_mri_image(image_path):
    try:
        model_container = get_mri_model()
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
        logger.error(f"Inference error: {e}")
        return {"prediction": "Error", "confidence": 0.0}

def get_mri_summary(prediction, confidence):
    summaries = {
        'glioma': f"Detected patterns consistent with a Glioma (Confidence: {confidence}%). Heatmap highlights infiltrative mass patterns.",
        'meningioma': f"Features characteristic of a Meningioma identified (Confidence: {confidence}%). Heatmap shows well-circumscribed lesion features.",
        'pituitary': f"High focus in sellar region suggestive of Pituitary tumor (Confidence: {confidence}%).",
        'notumor': f"AI screening did not identify typical tumor characteristics (Confidence: {confidence}%)."
    }
    return summaries.get(prediction, f"AI analysis completed with {confidence}% confidence.")

def generate_mri_gradcam(image_path):
    try:
        model_container = get_mri_model()
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
        
        heatmap_name = f"heatmap_mri_{os.path.basename(image_path)}.jpg"
        heatmap_path = os.path.join(settings.HEATMAP_ROOT, heatmap_name)
        
        cv2.imwrite(heatmap_path, cv2.cvtColor((visualization * 255).astype(np.uint8), cv2.COLOR_RGB2BGR))
        return os.path.join('heatmaps', heatmap_name)
    except Exception as e:
        logger.error(f"Grad-CAM error: {e}")
        return None
