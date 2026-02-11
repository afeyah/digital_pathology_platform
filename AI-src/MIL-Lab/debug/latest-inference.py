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
import random
from PIL import Image, ImageOps 
from src.builder import create_model
from scipy.ndimage import gaussian_filter, maximum_filter

# ----------------- CONFIGURATION -----------------
ROOT_DIR = '/mnt/k/work/wsl/wsi/'
# Just change this ID to test different slides
SLIDE_NAME = 'TCGA-86-A4D0-01Z-00-DX1.165461AD-A8DA-4B7B-87CE-F5DBDBD2C0A7'

CHECKPOINT_PATH = '../abmil_luad_best.pth'
MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
OUTPUT_DIR = './inference_reports'
PATCH_SIZE = 256 

# ----------------- UTILS -----------------

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def find_file(root, filename_pattern):
    search_pattern = os.path.join(root, "**", filename_pattern)
    files = glob.glob(search_pattern, recursive=True)
    return files[0] if files else None

def create_base_matrix(coords, attention_scores, slide_dims, patch_size=256):
    """
    Creates the raw mathematical matrix of attention scores.
    """
    slide_w, slide_h = slide_dims
    grid_h = int(slide_h // patch_size) + 1
    grid_w = int(slide_w // patch_size) + 1
    
    grid = np.zeros((grid_h, grid_w))
    coords = coords.squeeze()
    if coords.ndim > 1 and coords.shape[1] > 2: coords = coords[:, :2]
    
    for i in range(coords.shape[0]):
        try:
            x = coords[i, 0].item()
            y = coords[i, 1].item()
            score = attention_scores[i].item()
            col = int(x // patch_size)
            row = int(y // patch_size)
            if row < grid_h and col < grid_w:
                grid[row, col] = score
        except: continue
    return grid

# ----------------- REPORT GENERATOR -----------------

def generate_cloud_report(slide_path, coords, attention, pred_label, confidence, output_path):
    print(f"--- Generating Cloud Report for {os.path.basename(slide_path)} ---")
    
    if attention.dim() > 1:
        if attention.shape[0] == 1: attention = attention.squeeze(0)
        if attention.dim() > 1 and attention.shape[1] > 1: attention = attention.mean(dim=1)
    attention = attention.view(-1).cpu()

    # 1. Load Slide & Thumbnail
    try:
        wsi = openslide.OpenSlide(slide_path)
        slide_dims = wsi.dimensions
        # High Res Thumbnail for final report
        thumbnail = wsi.get_thumbnail((2000, 2000)).convert("RGB")
        thumb_size = thumbnail.size
    except Exception as e:
        print(f"❌ Error reading slide: {e}")
        return

    # 2. Create The "Organic Cloud"
    # Step A: Create raw matrix
    raw_matrix = create_base_matrix(coords, attention, slide_dims, PATCH_SIZE)
    if raw_matrix.max() > 0: norm_matrix = raw_matrix / raw_matrix.max()
    else: norm_matrix = raw_matrix

    # Step B: Dilation (Connect the dots)
    # We expand every dot by 1 pixel so neighbors touch
    dilated_matrix = maximum_filter(norm_matrix, size=2) 

    # Step C: Resize to Thumbnail & Heavy Blur
    img_dilated = Image.fromarray((dilated_matrix * 255).astype(np.uint8))
    heatmap_cloud = np.array(img_dilated.resize(thumb_size, resample=Image.BILINEAR))
    
    # Sigma=15 creates that smooth, weather-map fog effect
    heatmap_cloud = gaussian_filter(heatmap_cloud, sigma=15)

    # 3. Setup Report Layout
    plt.figure(figsize=(20, 12))
    gs = gridspec.GridSpec(2, 3, height_ratios=[1, 0.35])

    # --- MAIN HEATMAP (Spans Top Row) ---
    ax_map = plt.subplot(gs[0, :])
    ax_map.imshow(thumbnail)
    
    # Mask out low values so the background tissue is visible
    # Values < 10 (out of 255) become transparent
    masked_cloud = np.ma.masked_where(heatmap_cloud < 10, heatmap_cloud)
    
    # 'jet' gives the classic blue->red look. 
    # Alpha 0.5 ensures we can see the tissue structure underneath.
    ax_map.imshow(masked_cloud, cmap='jet', alpha=0.5)
    
    ax_map.axis('off')
    ax_map.set_title(f"AI Attention Heatmap ({pred_label})", fontsize=20, weight='bold')

    # --- TEXT INFO (Bottom Left) ---
    ax_text = plt.subplot(gs[1, 0])
    ax_text.axis('off')
    
    color = 'red' if pred_label == 'CANCER' else 'green'
    text_str = (
        f"Slide:\n{os.path.basename(slide_path)[:20]}...\n\n"
        f"Prediction:\n{pred_label}\n\n"
        f"Confidence:\n{confidence:.2f}%"
    )
    ax_text.text(0.1, 0.5, text_str, fontsize=18, va='center')
    # Add colored label for emphasis
    ax_text.text(0.1, 0.5, f"\n{pred_label}", fontsize=24, weight='bold', color=color, va='center', alpha=0) # Invisible spacer
    
    # --- TOP PATCHES (Bottom Right) ---
    # Extract coords safely
    coords = coords.squeeze()
    if coords.ndim > 1 and coords.shape[1] > 2: coords_safe = coords[:, :2]
    else: coords_safe = coords

    _, top_indices = torch.topk(attention, 2)
    top_indices = top_indices.cpu().numpy()
    
    for i, idx in enumerate(top_indices):
        ax_patch = plt.subplot(gs[1, i + 1])
        try:
            x = coords_safe[idx, 0].item()
            y = coords_safe[idx, 1].item()
            patch_img = wsi.read_region((int(x), int(y)), 0, (256, 256)).convert("RGB")
            ax_patch.imshow(patch_img)
            ax_patch.set_title(f"Highest Risk Area #{i+1}\nScore: {attention[idx]:.4f}", fontsize=14)
            ax_patch.axis('off')
            
            # Red border if Cancer
            if pred_label == 'CANCER':
                for spine in ax_patch.spines.values(): 
                    spine.set_edgecolor('red')
                    spine.set_linewidth(3)
        except: pass

    # Save
    os.makedirs(output_path, exist_ok=True)
    save_path = os.path.join(output_path, f"{SLIDE_NAME}_cloud_report.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()
    print(f"✓ Report saved: {save_path}")

# ----------------- INFERENCE LOGIC -----------------

def run_inference(slide_name, root_dir, model_path):
    set_seed(42)
    print(f"--- Processing: {slide_name} ---")
    
    h5_path = find_file(root_dir, f"{slide_name}*.h5")
    slide_path = find_file(root_dir, f"{slide_name}*.svs")
    if not slide_path: slide_path = find_file(root_dir, f"{slide_name}*.tif")
    if not h5_path: return print("❌ H5 not found.")

    model = create_model(MODEL_NAME, num_classes=2, dropout=0, from_pretrained=False)
    state_dict = torch.load(model_path, map_location=DEVICE)
    
    ckpt_key = list(state_dict.keys())[0]
    model_key = list(model.state_dict().keys())[0]
    if ckpt_key.startswith('model.') and not model_key.startswith('model.'):
        state_dict = {k.replace('model.', ''): v for k, v in state_dict.items()}
    
    try: model.load_state_dict(state_dict, strict=True)
    except: model.load_state_dict(state_dict, strict=False) 

    model.to(DEVICE)
    model.eval()

    priorities = ['attention_c', 'attention_b', 'attention_a']
    target_layer = None
    candidates = {name: module for name, module in model.named_modules() if any(p in name for p in priorities)}
    for p in priorities:
        for name in candidates:
             if name.endswith(p): target_layer = name; break
        if target_layer: break
    
    captured = {}
    if target_layer:
        for n, m in model.named_modules():
            if n == target_layer: m.register_forward_hook(lambda m, i, o: captured.update({'A': o})); break

    with h5py.File(h5_path, 'r') as f:
        features = torch.from_numpy(f['features'][:])
        if features.dim() == 3: features = features.squeeze(0)
        coords = f['coords'][:] if 'coords' in f else None

    features = features.to(DEVICE).unsqueeze(0)
    
    with torch.no_grad():
        results = model(features)
        
        # Safe Logit Extraction
        logits = None
        if isinstance(results, dict): logits = results.get('logits')
        elif isinstance(results, tuple):
            if isinstance(results[0], dict): logits = results[0].get('logits')
            else: logits = results[0]
        else: logits = results
        if isinstance(logits, dict): logits = logits['logits']
        
        probs = torch.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_idx].item()
        pred_label = {0: "NORMAL", 1: "CANCER"}[pred_idx]

        # Safe Attention Extraction
        attention = None
        if 'A' in captured: attention = captured['A']
        elif isinstance(results, dict) and 'A' in results: attention = results['A']
        elif isinstance(results, tuple) and isinstance(results[0], dict) and 'A' in results[0]: attention = results[0]['A']
        
        if attention is None:
            attention = torch.zeros((features.shape[1], 1))
            
        if isinstance(attention, tuple): attention = attention[0]
        attention = attention.clone().detach().cpu()

    # Generate the Cloud Report
    generate_cloud_report(slide_path, coords, attention, pred_label, confidence * 100, OUTPUT_DIR)

if __name__ == "__main__":
    run_inference(SLIDE_NAME, ROOT_DIR, CHECKPOINT_PATH)