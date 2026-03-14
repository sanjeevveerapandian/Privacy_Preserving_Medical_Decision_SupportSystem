import torch
import sys
import os

model_path = '/Users/pyt/Downloads/1CP25-754 2/ml_models/xray_pneumonia_model.pth'
print(f"Checking if file exists: {os.path.exists(model_path)}")
try:
    state_dict = torch.load(model_path, map_location='cpu')
    print(f"Loaded {model_path}")
    print("Keys in state dict:")
    keys = list(state_dict.keys())
    print(keys[:10], '...' if len(keys) > 10 else '')
    
    # Try to deduce architecture from keys
    if any('fc.weight' in k for k in keys):
        fc_weight = state_dict['fc.weight']
        print(f"Detected fc.weight shape: {fc_weight.shape}")
        print(f"Number of classes: {fc_weight.shape[0]}")
        print("Looks like a ResNet variant.")
    elif any('classifier.weight' in k or 'classifier.6.weight' in k or 'classifier.1.weight' in k for k in keys):
        classifier_keys = [k for k in keys if 'classifier' in k and 'weight' in k]
        if classifier_keys:
            last_layer = state_dict[classifier_keys[-1]]
            print(f"Detected classifier shape: {last_layer.shape}")
            print(f"Number of classes: {last_layer.shape[0]}")
            print("Looks like a DenseNet, VGG, or MobileNet variant.")
        else:
            print("Could not find classifier weight.")
except Exception as e:
    import traceback
    traceback.print_exc()
