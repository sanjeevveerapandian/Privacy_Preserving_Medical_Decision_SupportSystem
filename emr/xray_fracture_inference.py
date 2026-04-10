import os
import logging
import cv2
import numpy as np
import torch
from django.conf import settings

logger = logging.getLogger(__name__)

class FractureModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FractureModel, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        from ultralytics import YOLO
        model_path = os.path.join(settings.BASE_DIR, 'ai_model', 'best_fracture_model.pt')
        if os.path.exists(model_path):
            self.model = YOLO(model_path)
            logger.info("✅ YOLOv8 Fracture Model Ready.")
        else:
            logger.error(f"❌ Fracture Model weights NOT found at {model_path}")
            self.model = None

_fracture_model_container = None

def get_fracture_model():
    global _fracture_model_container
    if _fracture_model_container is None:
        _fracture_model_container = FractureModel()
    return _fracture_model_container.model

def predict_xray_fracture(image_path):
    logger.info("Running YOLOv8 forward pass via Subprocess (CLI)...")
    import subprocess
    import json
    
    import sys
    
    cli_path = os.path.join(os.path.dirname(__file__), 'fracture_cli.py')
    python_path = sys.executable
    
    try:
        cmd = [python_path, cli_path, image_path, "0.05", "640"]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        res = json.loads(output.decode().strip().split('\n')[-1]) # Get last line in case of noise
        
        if res.get('prediction') == "Error":
            logger.error(f"CLI Error: {res.get('error')}")
            return {"prediction": "Error", "confidence": 0.0, "detections": []}
            
        return res
        
    except subprocess.CalledProcessError as e:
        logger.error(f"CLI process failed: {e.output.decode()}")
        return {"prediction": "Error", "confidence": 0.0, "detections": []}
    except Exception as e:
        logger.error(f"CLI execution failed: {e}")
        return {"prediction": "Error", "confidence": 0.0, "detections": []}

def get_fracture_summary(prediction, confidence, detections):
    if prediction == "fracture detected":
        return f"AI detected {len(detections)} potential fracture site(s) (Confidence: {confidence}%). Orthopedic evaluation is advised."
    else:
        return f"No signs of bone fractures detected (Confidence: {confidence}%). The structural integrity appears intact."

def generate_fracture_overlay(image_path):
    import subprocess
    import json
    import tempfile
    
    import sys
    
    logger.info(f"Generating fracture overlay via CLI for: {image_path}")
    cli_path = os.path.join(os.path.dirname(__file__), 'fracture_cli.py')
    python_path = sys.executable
    
    # Create a temporary output path for the plotted image
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        cmd = [python_path, cli_path, image_path, "0.05", "640", "--overlay", output_path]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        res = json.loads(output.decode().strip().split('\n')[-1])
        
        if res.get('success'):
            # The CLI saves to output_path. We move it to HEATMAP_ROOT.
            overlay_name = f"bbox_{os.path.basename(image_path)}.jpg"
            final_path = os.path.join(settings.HEATMAP_ROOT, overlay_name)
            
            import shutil
            shutil.move(output_path, final_path)
            return os.path.join('heatmaps', overlay_name)
        else:
            logger.error(f"CLI Overlay Error: {res.get('error')}")
            if os.path.exists(output_path): os.remove(output_path)
            return None
            
    except Exception as e:
        logger.error(f"CLI Overlay failed: {e}")
        if os.path.exists(output_path): os.remove(output_path)
        return None
