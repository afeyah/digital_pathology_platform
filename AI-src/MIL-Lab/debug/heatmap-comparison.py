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

# ================= CONFIGURATION =================
ROOT_DIR = '/mnt/k/work/wsl/wsi/'
SLIDE_NAME = 'TCGA-86-A4D0-01Z-00-DX1.165461AD-A8DA-4B7B-87CE-F5DBDBD2C0A7'
CHECKPOINT_PATH = '../abmil_luad_best.pth'
MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
OUTPUT_DIR = './heatmap_mega_comparison'
PATCH_SIZE = 256 

# ================= UTILS =================

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

def create_perfect_grid(coords, attention_scores, slide_dims, patch_size=256):
    """
    Creates a gap-free grid by mapping patches to matrix indices.
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

# ================= STYLE GENERATOR =================

def generate_mega_sheet(slide_path, coords, attention, pred_label, confidence, output_path):
    print(f"--- Generating Varied Styles for {os.path.basename(slide_path)} ---")
    
    if attention.dim() > 1:
        if attention.shape[0] == 1: attention = attention.squeeze(0)
        if attention.dim() > 1 and attention.shape[1] > 1: attention = attention.mean(dim=1)
    attention = attention.view(-1).cpu()

    try:
        wsi = openslide.OpenSlide(slide_path)
        slide_dims = wsi.dimensions
        thumbnail = wsi.get_thumbnail((1500, 1500)).convert("RGB")
        thumb_size = thumbnail.size
        thumbnail_gray = ImageOps.grayscale(thumbnail).convert("RGB")
    except Exception as e:
        print(f"❌ Error reading slide: {e}")
        return

    # 1. Base Matrix
    raw_matrix = create_perfect_grid(coords, attention, slide_dims, PATCH_SIZE)
    if raw_matrix.max() > 0: norm_matrix = raw_matrix / raw_matrix.max()
    else: norm_matrix = raw_matrix

    # 2. TRANSFORMATIONS (The "Circle Fixer")
    
    # A. DILATION (Merges neighbors)
    # This expands every dot by 1 pixel in all directions before resizing
    dilated_matrix = maximum_filter(norm_matrix, size=2) 

    # Resize to thumbnail
    img_raw = Image.fromarray((norm_matrix * 255).astype(np.uint8))
    img_dilated = Image.fromarray((dilated_matrix * 255).astype(np.uint8))

    # STYLE 1: SOLID MOSAIC (The "Tetris" Look)
    # Nearest neighbor ensures sharp squares, no blurred circles
    heatmap_mosaic = np.array(img_raw.resize(thumb_size, resample=Image.NEAREST))

    # STYLE 2: SMOOTH CLOUD (The "Weather Map" Look)
    # Heavy blur merges everything into one organic shape
    heatmap_cloud = np.array(img_dilated.resize(thumb_size, resample=Image.BILINEAR))
    heatmap_cloud = gaussian_filter(heatmap_cloud, sigma=15) # High sigma = no dots, just clouds

    # STYLE 3: CONNECTED BLOB (Moderate)
    heatmap_blob = np.array(img_dilated.resize(thumb_size, resample=Image.BILINEAR))
    heatmap_blob = gaussian_filter(heatmap_blob, sigma=5)

    # --- PLOTTING ---
    plt.figure(figsize=(24, 20))
    gs = gridspec.GridSpec(3, 3, height_ratios=[1, 1, 0.4])

    def plot_overlay(ax_idx, title, bg, data, cmap, alpha=0.6, type='imshow', levels=None):
        ax = plt.subplot(gs[ax_idx])
        ax.imshow(bg)
        
        # Mask Background
        masked_data = np.ma.masked_where(data < 5, data) # Hide very low values
        
        if type == 'contour':
            # Solid Filled Contours (Topographic)
            h, w = data.shape
            X, Y = np.meshgrid(np.arange(w), np.arange(h))
            # contourf fills the gaps!
            ax.contourf(X, Y, data, levels=levels, cmap=cmap, alpha=alpha)
        else:
            # Standard Image
            ax.imshow(masked_data, cmap=cmap, alpha=alpha, interpolation='nearest' if 'Mosaic' in title else 'bicubic')
            
        ax.set_title(title, fontsize=18, weight='bold')
        ax.axis('off')

    # ROW 1: DISTINCT STYLES
    plot_overlay((0,0), "1. Solid Mosaic (No Gaps)", thumbnail, heatmap_mosaic, 'viridis', alpha=0.5)
    
    # Filled Contours: Creates solid islands, not dots
    plot_overlay((0,1), "2. Topographic (Filled Contours)", thumbnail, heatmap_cloud, 'plasma', alpha=0.5, 
                 type='contour', levels=[50, 100, 150, 200, 255])
    
    # Cloud: One big smooth region
    plot_overlay((0,2), "3. Organic Cloud (Heavy Blur)", thumbnail, heatmap_cloud, 'jet', alpha=0.5)

    # ROW 2: COLOR VARIATIONS
    plot_overlay((1,0), "4. Hotspots (Magma)", thumbnail, heatmap_blob, 'magma', alpha=0.6)
    plot_overlay((1,1), "5. Red Alert (Alpha Weighted)", thumbnail, heatmap_cloud, 'Reds', alpha=0.6)
    plot_overlay((1,2), "6. Pop Art (Grayscale BG)", thumbnail_gray, heatmap_mosaic, 'jet', alpha=0.4)

    # ROW 3: INFO
    ax_text = plt.subplot(gs[2, 0])
    ax_text.axis('off')
    color = 'red' if pred_label == 'CANCER' else 'green'
    ax_text.text(0.1, 0.6, f"Prediction: {pred_label}", fontsize=24, weight='bold', color=color)
    ax_text.text(0.1, 0.3, f"Confidence: {confidence:.2f}%", fontsize=20)

    # Patches
    coords = coords.squeeze()
    if coords.ndim > 1 and coords.shape[1] > 2: coords_safe = coords[:, :2]
    else: coords_safe = coords

    _, top_indices = torch.topk(attention, 2)
    top_indices = top_indices.cpu().numpy()
    
    for i, idx in enumerate(top_indices):
        ax_patch = plt.subplot(gs[2, i + 1])
        try:
            x = coords_safe[idx, 0].item()
            y = coords_safe[idx, 1].item()
            patch_img = wsi.read_region((int(x), int(y)), 0, (256, 256)).convert("RGB")
            ax_patch.imshow(patch_img)
            ax_patch.set_title(f"Rank #{i+1}\nAttn: {attention[idx]:.4f}", fontsize=14)
            ax_patch.axis('off')
            for spine in ax_patch.spines.values(): spine.set_edgecolor('black'); spine.set_linewidth(1)
        except: pass

    os.makedirs(output_path, exist_ok=True)
    save_path = os.path.join(output_path, f"STYLES_{SLIDE_NAME}.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"✓ Styles Comparison Saved: {save_path}")

# ================= INFERENCE LOGIC =================
# (Keeping your existing robust inference logic)
def run_inference(slide_name, root_dir, model_path):
    set_seed(42)
    print(f"--- Processing: {slide_name} ---")
    
    # 1. File Location
    h5_path = find_file(root_dir, f"{slide_name}*.h5")
    slide_path = find_file(root_dir, f"{slide_name}*.svs")
    if not slide_path: slide_path = find_file(root_dir, f"{slide_name}*.tif")
    if not h5_path: return print("❌ H5 not found.")

    # 2. Model Loading
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

    # 3. Hook Registration
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

    # 4. Data Loading
    with h5py.File(h5_path, 'r') as f:
        features = torch.from_numpy(f['features'][:])
        if features.dim() == 3: features = features.squeeze(0)
        coords = f['coords'][:] if 'coords' in f else None

    features = features.to(DEVICE).unsqueeze(0)
    
    # 5. Forward Pass
    with torch.no_grad():
        results = model(features)
        
        # --- SAFE LOGIT EXTRACTION ---
        logits = None
        if isinstance(results, dict):
            logits = results.get('logits')
        elif isinstance(results, tuple):
            if isinstance(results[0], dict): logits = results[0].get('logits')
            else: logits = results[0]
        else:
            logits = results
            
        # Nested dict safety (sometimes logits key points to another dict)
        if isinstance(logits, dict): logits = logits['logits']
        
        # Calculate Confidence
        probs = torch.softmax(logits, dim=1)
        pred_idx = torch.argmax(probs, dim=1).item()
        confidence = probs[0][pred_idx].item()
        pred_label = {0: "NORMAL", 1: "CANCER"}[pred_idx]

        # --- SAFE ATTENTION EXTRACTION (FIXED) ---
        attention = None
        
        # Priority 1: Hook (Best for consistency)
        if 'A' in captured:
            attention = captured['A']
        
        # Priority 2: Return Dict
        elif isinstance(results, dict) and 'A' in results:
            attention = results['A']
            
        # Priority 3: Return Tuple (Dict inside tuple)
        elif isinstance(results, tuple) and isinstance(results[0], dict) and 'A' in results[0]:
            attention = results[0]['A']
        
        # Fallback: Zero vector
        if attention is None:
            print("⚠️ Attention not found. Heatmap will be blank.")
            attention = torch.zeros((features.shape[1], 1))
            
        if isinstance(attention, tuple): attention = attention[0]
        attention = attention.clone().detach().cpu()

    # 6. Generate Report
    generate_mega_sheet(slide_path, coords, attention, pred_label, confidence * 100, OUTPUT_DIR)

if __name__ == "__main__":
    run_inference(SLIDE_NAME, ROOT_DIR, CHECKPOINT_PATH)