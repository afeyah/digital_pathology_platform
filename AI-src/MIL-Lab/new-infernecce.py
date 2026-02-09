import torch
import h5py
import os
import glob
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import openslide
from src.builder import create_model

# ================= CONFIGURATION =================
# Set your paths here
ROOT_DIR = '/mnt/k/work/wsl/wsi/'
SLIDE_NAME = 'TCGA-44-6145-11A-01-TS1.1ce37c11-0439-4903-be45-68cd55baf942' 
CHECKPOINT_PATH = 'abmil_luad_best.pth'
MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
OUTPUT_DIR = './inference_reports'

# ================= UTILS =================

def find_file(root, filename_pattern):
    """Recursively searches for a file matching the pattern."""
    search_pattern = os.path.join(root, "**", filename_pattern)
    files = glob.glob(search_pattern, recursive=True)
    return files[0] if files else None

def get_attention_map(coords, attention_scores, patch_size=256):
    """Maps attention scores to a 2D grid for the heatmap."""
    coords = coords.astype(int)
    min_x, min_y = np.min(coords, axis=0)
    max_x, max_y = np.max(coords, axis=0)
    
    w = (max_x - min_x) // patch_size + 1
    h = (max_y - min_y) // patch_size + 1
    
    heatmap = np.zeros((h, w))
    
    for i, (x, y) in enumerate(coords):
        grid_x = (x - min_x) // patch_size
        grid_y = (y - min_y) // patch_size
        if grid_y < h and grid_x < w:
            heatmap[grid_y, grid_x] = attention_scores[i]
            
    return heatmap

def generate_report(slide_path, coords, attention, pred_label, confidence, output_path):
    print(f"--- Generating Report for {os.path.basename(slide_path)} ---")
    
    num_patches = coords.shape[0]
    
    # 1. Robust Attention Shape Handling
    if attention.dim() > 1:
        if attention.shape[0] == 1: 
            attention = attention.squeeze(0)
        if attention.dim() > 1 and attention.shape[1] > 1:
            attention = attention.mean(dim=1)
            
    attention = attention.view(-1).cpu()

    # 2. Safety Check
    if attention.shape[0] != num_patches:
        print(f"⚠️ Size Mismatch. Skipping report.")
        return

    # 3. Load Slide Thumbnail
    try:
        wsi = openslide.OpenSlide(slide_path)
        # Get a larger thumbnail for better resolution
        thumbnail = wsi.get_thumbnail((1024, 1024)).convert("RGB")
    except Exception as e:
        print(f"❌ Error reading slide: {e}")
        return

    # 4. Get Top Patches
    top_k = 5
    _, top_indices = torch.topk(attention, min(top_k, num_patches))
    top_indices = top_indices.cpu().numpy()
    
    # 5. Create Heatmap Overlay
    # A. Generate the raw grid (e.g., 50x50)
    raw_heatmap = get_attention_map(coords, attention.numpy())
    
    # B. Resize grid to match Thumbnail dimensions (e.g., 1024x1024)
    # We use PIL to resize smoothly
    from PIL import Image
    
    # Normalize raw heatmap to 0-255 for resizing
    if raw_heatmap.max() > 0:
        raw_heatmap_norm = raw_heatmap / raw_heatmap.max()
    else:
        raw_heatmap_norm = raw_heatmap
        
    heatmap_img = Image.fromarray((raw_heatmap_norm * 255).astype(np.uint8))
    heatmap_resized = heatmap_img.resize(thumbnail.size, resample=Image.BILINEAR)
    heatmap_array = np.array(heatmap_resized)

    # 6. Create Plot
    plt.figure(figsize=(20, 10))
    gs = gridspec.GridSpec(2, 4, width_ratios=[1, 1, 1, 1])

    # Text Info
    ax_text = plt.subplot(gs[0, 0])
    ax_text.axis('off')
    color = 'red' if pred_label == 'CANCER' else 'green'
    ax_text.text(0.1, 0.6, f"Slide:\n{os.path.basename(slide_path)[:15]}...", fontsize=14)
    ax_text.text(0.1, 0.4, f"Prediction: {pred_label}", fontsize=18, weight='bold', color=color)
    ax_text.text(0.1, 0.3, f"Confidence: {confidence:.2f}%", fontsize=16, weight='bold')

    # --- THE OVERLAY FIX ---
    ax_heat = plt.subplot(gs[0, 1:3])
    
    # Layer 1: The Tissue Thumbnail
    ax_heat.imshow(thumbnail)
    
    # Layer 2: The Heatmap (using imshow with alpha transparency)
    # We mask out the zeros (background) so they don't darken the tissue
    masked_heatmap = np.ma.masked_where(heatmap_array < 1, heatmap_array)
    
    ax_heat.imshow(masked_heatmap, cmap='jet', alpha=0.5, interpolation='nearest')
    
    ax_heat.axis('off')
    ax_heat.set_title("Attention Heatmap Overlay", fontsize=14)
    # -----------------------

    # Top Patches
    for i, idx in enumerate(top_indices):
        ax_patch = plt.subplot(gs[1, i if i < 4 else 3])
        x, y = coords[idx]
        try:
            patch_img = wsi.read_region((int(x), int(y)), 0, (256, 256)).convert("RGB")
            ax_patch.imshow(patch_img)
            ax_patch.set_title(f"Rank #{i+1}\nAttn: {attention[idx]:.4f}", fontsize=10)
            ax_patch.axis('off')
            if pred_label == 'CANCER':
                for spine in ax_patch.spines.values():
                    spine.set_edgecolor('red'); spine.set_linewidth(2)
        except: pass

    os.makedirs(output_path, exist_ok=True)
    save_path = os.path.join(output_path, f"{os.path.basename(slide_path)}_report.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"✓ Report saved: {save_path}")


# ================= INFERENCE LOGIC =================

def run_inference(slide_name, root_dir, model_path):
    print(f"--- Processing: {slide_name} ---")

    # 1. Find Files
    h5_path = find_file(root_dir, f"{slide_name}*.h5")
    slide_path = find_file(root_dir, f"{slide_name}*.svs")
    if not slide_path: slide_path = find_file(root_dir, f"{slide_name}*.tif")
    
    if not h5_path:
        print("❌ H5 file not found.")
        return

    # 2. Load Model
    model = create_model(MODEL_NAME, num_classes=2, dropout=0, from_pretrained=False)
    try:
        state_dict = torch.load(model_path, map_location=DEVICE)
        # Fix 'model.' prefix issue
        if list(state_dict.keys())[0].startswith('model.'):
            state_dict = {k.replace('model.', ''): v for k, v in state_dict.items()}
        model.load_state_dict(state_dict, strict=False)
    except Exception as e:
        print(f"❌ Weight loading error: {e}")
        return

    model.to(DEVICE)
    model.eval()

    # 3. Setup Attention Hook (Smart Detection)
    attention_layer_name = None
    # We prefer 'attention_c' (linear score) but accept 'attention_b' (gating vector)
    priorities = ['attention_c', 'attention_b', 'attention_a']
    
    # Find valid layers
    candidates = {}
    for name, module in model.named_modules():
        if any(p in name for p in priorities): candidates[name] = module

    # Select best layer
    for p in priorities:
        for name in candidates.keys():
            if name.endswith(p):
                attention_layer_name = name
                break
        if attention_layer_name: break

    # Attach Hook
    captured_attn = {}
    def get_attention_hook(module, input, output):
        captured_attn['A'] = output

    if attention_layer_name:
        for name, module in model.named_modules():
            if name == attention_layer_name:
                module.register_forward_hook(get_attention_hook)
                break
    
    # 4. Load Data & Run
    with h5py.File(h5_path, 'r') as f:
        features = torch.from_numpy(f['features'][:])
        if features.dim() == 3: features = features.squeeze(0)
        coords = f['coords'][:] if 'coords' in f else None

    features = features.to(DEVICE).unsqueeze(0)
    
    with torch.no_grad():
        results = model(features)

        # Unpack Logits
        logits = None
        if isinstance(results, tuple):
            if isinstance(results[0], dict): logits = results[0].get('logits')
            else: logits = results[0]
        elif isinstance(results, dict):
            logits = results.get('logits')
        else:
            logits = results
            
        if isinstance(logits, dict): logits = logits['logits']
        
        # --- CALCULATE CONFIDENCE ---
        probs = torch.softmax(logits, dim=1)           # e.g., [0.20, 0.80]
        pred_idx = torch.argmax(probs, dim=1).item()   # e.g., 1 (Cancer)
        confidence = probs[0][pred_idx].item()         # e.g., 0.80
        
        label_map = {0: "NORMAL", 1: "CANCER"}
        pred_label = label_map[pred_idx]

        # Retrieve Attention
        attention = None
        if 'A' in captured_attn: attention = captured_attn['A']
        elif isinstance(results, dict) and 'A' in results: attention = results['A']
             
        if attention is None: attention = torch.zeros((features.shape[1], 1))
        if isinstance(attention, tuple): attention = attention[0]
        attention = attention.clone().detach().cpu()

    # 5. Output
    print("\n" + "="*30)
    print(f"PREDICTION:  {pred_label}")
    print(f"Confidence:  {confidence*100:.2f}%")
    print("="*30 + "\n")

    if slide_path and coords is not None:
        generate_report(slide_path, coords, attention, pred_label, confidence * 100, OUTPUT_DIR)

if __name__ == "__main__":
    run_inference(SLIDE_NAME, ROOT_DIR, CHECKPOINT_PATH)