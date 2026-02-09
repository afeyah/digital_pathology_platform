import torch
import h5py
import os
import argparse
from src.builder import create_model

# ================= CONFIGURATION =================
# Path to the specific slide .h5 file you want to test
TEST_SLIDE_PATH = '/mnt/k/work/wsl/wsi/fine-tune/TCGA-LUAD-NORMAL/TCGA-38-4631-11A-01-BS1.8777cd1a-1d4d-4d5e-b036-5fd2cb9406f8.h5' 

# Path to the weights you trained (The binary classifier)
CHECKPOINT_PATH = 'abmil_luad_best.pth'

# Model Name (Must match what you trained with)
MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def run_inference(h5_path, model_path):
    print(f"--- Running Inference on {os.path.basename(h5_path)} ---")

    # 1. Load the Model Architecture
    # We must specify num_classes=2 because that's how we fine-tuned it
    model = create_model(MODEL_NAME, num_classes=2, dropout=0, from_pretrained=False)
    
    # 2. Load Your Fine-Tuned Weights
    try:
        state_dict = torch.load(model_path, map_location=DEVICE)
        model.load_state_dict(state_dict)
        print("✓ Loaded fine-tuned weights successfully.")
    except FileNotFoundError:
        print(f"❌ Error: Could not find model weights at {model_path}")
        return

    model.to(DEVICE)
    model.eval()

    # 3. Load the Slide Features
    try:
        with h5py.File(h5_path, 'r') as f:
            # Features are saved as (1, num_patches, 1536) -> Squeeze to (num_patches, 1536)
            features = torch.from_numpy(f['features'][:]).squeeze(0)
            
        print(f"✓ Loaded {features.shape[0]} patches.")
    except Exception as e:
        print(f"❌ Error loading H5 file: {e}")
        return

    # 4. Run Prediction
    features = features.to(DEVICE)
    features = features.unsqueeze(0)
    
    with torch.no_grad():
        # Forward pass (get logits)
        results, _ = model(features)
        logits = results['logits'] # Shape: (1, 2)
        
        # Convert logits to probabilities (Softmax)
        probs = torch.softmax(logits, dim=1)
        
        # Get probability of Cancer (Index 1)
        cancer_prob = probs[0][1].item()
        normal_prob = probs[0][0].item()
        
        # Get Predicted Label (0 or 1)
        pred_idx = torch.argmax(probs, dim=1).item()

    # 5. Output Results
    label_map = {0: "NORMAL", 1: "CANCER"}
    
    print("\n" + "="*30)
    print(f"PREDICTION:  {label_map[pred_idx]}")
    print(f"Confidence:  {cancer_prob*100:.2f}% (Cancer Score)")
    print("="*30 + "\n")

    return cancer_prob

if __name__ == "__main__":
    # You can update TEST_SLIDE_PATH at the top, or pass it via command line if you prefer
    run_inference(TEST_SLIDE_PATH, CHECKPOINT_PATH)