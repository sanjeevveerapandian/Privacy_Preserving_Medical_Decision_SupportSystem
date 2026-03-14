import os
import sys
import json
import torch
import logging

# Minimal setup
logging.basicConfig(level=logging.ERROR)

def run_inference(image_path, conf=0.05, imgsz=640):
    from ultralytics import YOLO
    
    # Path to model relative to project root
    model_path = os.path.join(os.getcwd(), 'ai_model', 'best_fracture_model.pt')
    if not os.path.exists(model_path):
        return {"prediction": "Error", "error": "Model not found"}
        
    model = YOLO(model_path)
    torch.set_num_threads(1)
    
    results = model(image_path, device='cpu', verbose=False, conf=conf, imgsz=imgsz)
    
    detections = []
    max_conf = 0.0
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            c = float(box.conf[0])
            cls = int(box.cls[0])
            name = model.names[cls]
            if c > max_conf:
                max_conf = c
            
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "class": name,
                "confidence": round(c * 100, 2),
                "bbox": [x1, y1, x2, y2]
            })
            
    if detections:
        prediction = "fracture detected"
        confidence = round(max_conf * 100, 2)
    else:
        prediction = "no arrow signs"
        confidence = 90.0
        
    return {
        "prediction": prediction,
        "confidence": confidence,
        "detections": detections
    }

def save_overlay(image_path, output_path, conf=0.05):
    from ultralytics import YOLO
    import cv2
    
    model_path = os.path.join(os.getcwd(), 'ai_model', 'best_fracture_model.pt')
    model = YOLO(model_path)
    torch.set_num_threads(1)
    
    results = model(image_path, device='cpu', verbose=False, conf=conf)
    res_plotted = results[0].plot()
    cv2.imwrite(output_path, res_plotted)
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No image path"}))
        sys.exit(1)
        
    img_path = sys.argv[1]
    conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    imgsz = int(sys.argv[3]) if len(sys.argv) > 3 else 640
    
    # Check for overlay request
    if "--overlay" in sys.argv:
        try:
            out_path = sys.argv[sys.argv.index("--overlay") + 1]
            res = save_overlay(img_path, out_path, conf)
            print(json.dumps({"success": True, "path": res}))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(0)
        
    try:
        res = run_inference(img_path, conf, imgsz)
        print(json.dumps(res))
    except Exception as e:
        print(json.dumps({"prediction": "Error", "error": str(e)}))
