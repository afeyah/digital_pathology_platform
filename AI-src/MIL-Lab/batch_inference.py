import torch
import h5py
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from sklearn.metrics import accuracy_score, roc_auc_score, confusion_matrix, classification_report
from src.builder import create_model

# ================= CONFIGURATION =================
# Define your specific paths
NORMAL_DIR = '/mnt/k/work/wsl/wsi/fine-tune/TCGA-LUAD-NORMAL/'
CANCER_DIR = '/mnt/k/work/wsl/wsi/fine-tune/TCGA-LUAD/'

# Model Settings
CHECKPOINT_PATH = 'abmil_luad_best.pth'
MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def load_slide_features(h5_path):
    """Loads features from h5 and ensures correct shape (1, N, 1536)."""
    try:
        with h5py.File(h5_path, 'r') as f:
            features = torch.from_numpy(f['features'][:])
            
            # If shape is (N, 1536), add batch dim -> (1, N, 1536)
            if features.dim() == 2:
                features = features.unsqueeze(0)
        return features
    except Exception as e:
        print(f"Error loading {h5_path}: {e}")
        return None

def main():
    print(f"--- Starting Batch Inference on {DEVICE} ---")
    
    # 1. Load Model
    print(f"Loading model: {MODEL_NAME}...")
    model = create_model(MODEL_NAME, num_classes=2, dropout=0, from_pretrained=False)
    
    # Load your fine-tuned weights
    if os.path.exists(CHECKPOINT_PATH):
        model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=DEVICE))
        print("✓ Weights loaded successfully.")
    else:
        print(f"❌ Error: Checkpoint not found at {CHECKPOINT_PATH}")
        return

    model.to(DEVICE)
    model.eval()

    # 2. Prepare File List
    slides = []
    
    # Add Normal Slides (Label 0)
    if os.path.exists(NORMAL_DIR):
        for f in os.listdir(NORMAL_DIR):
            if f.endswith('.h5'):
                slides.append({'path': os.path.join(NORMAL_DIR, f), 'label': 0})
    
    # Add Cancer Slides (Label 1)
    if os.path.exists(CANCER_DIR):
        for f in os.listdir(CANCER_DIR):
            if f.endswith('.h5'):
                slides.append({'path': os.path.join(CANCER_DIR, f), 'label': 1})

    print(f"Found {len(slides)} total slides to process.")
    
    if len(slides) == 0:
        print("No .h5 files found in the specified directories.")
        return

    # 3. Inference Loop
    results = []
    true_labels = []
    pred_probs = []
    pred_labels = []

    # Iterate with progress bar
    for slide in tqdm(slides, desc="Processing Slides"):
        features = load_slide_features(slide['path'])
        
        if features is not None:
            features = features.to(DEVICE)
            
            with torch.no_grad():
                output, _ = model(features)
                logits = output['logits']
                probs = torch.softmax(logits, dim=1)
                
                # Get Cancer Probability (Class 1)
                cancer_prob = probs[0][1].item()
                predicted_label = torch.argmax(probs, dim=1).item()
            
            # Store Result
            results.append({
                'filename': os.path.basename(slide['path']),
                'true_label': slide['label'],
                'predicted_label': predicted_label,
                'cancer_prob': cancer_prob,
                'status': 'Correct' if slide['label'] == predicted_label else 'WRONG'
            })
            
            true_labels.append(slide['label'])
            pred_probs.append(cancer_prob)
            pred_labels.append(predicted_label)

    # 4. Calculate Metrics
    acc = accuracy_score(true_labels, pred_labels)
    auc = roc_auc_score(true_labels, pred_probs)
    cm = confusion_matrix(true_labels, pred_labels)

    print("\n" + "="*40)
    print("       FINAL RESULTS       ")
    print("="*40)
    print(f"Total Slides: {len(results)}")
    print(f"Accuracy:     {acc:.4f}")
    print(f"AUC Score:    {auc:.4f}")
    print("-" * 40)
    print("Classification Report:")
    print(classification_report(true_labels, pred_labels, target_names=['Normal', 'Cancer']))
    
    print("-" * 40)
    print("Confusion Matrix:")
    print(f"TN: {cm[0][0]} | FP: {cm[0][1]}")
    print(f"FN: {cm[1][0]} | TP: {cm[1][1]}")
    print("="*40)

    # 5. Save Report to CSV
    df = pd.DataFrame(results)
    csv_filename = "batch_inference_results.csv"
    df.to_csv(csv_filename, index=False)
    print(f"\nDetailed report saved to: {csv_filename}")

    # 6. Plot Confusion Matrix (Optional)
    try:
        plt.figure(figsize=(6, 5))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                    xticklabels=['Normal', 'Cancer'], 
                    yticklabels=['Normal', 'Cancer'])
        plt.xlabel('Predicted')
        plt.ylabel('Actual')
        plt.title('Confusion Matrix: LUAD vs Normal')
        plt.savefig('confusion_matrix.png')
        print("Confusion matrix plot saved to: confusion_matrix.png")
    except Exception as e:
        print("Skipped plotting (matplotlib/seaborn issue).")

if __name__ == "__main__":
    main()