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
from scipy.ndimage import gaussian_filter

# ================= CONFIGURATION =================
ROOT_DIR = '/mnt/k/work/wsl/wsi/'
SLIDE_NAME = 'TCGA-86-A4D0-01Z-00-DX1.165461AD-A8DA-4B7B-87CE-F5DBDBD2C0A7'
CHECKPOINT_PATH = 'abmil_luad_best.pth'
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
    Creates a gap-free grid by mapping patches to matrix indices 
    rather than pixel coordinates.
    """
    slide_w, slide_h = slide_dims
    
    # 1. Calculate Grid Dimensions (How many 256x256 patches fit in the slide?)
    # We add +1 to handle edge cases
    grid_h = int(slide_h // patch_size) + 1
    grid_w = int(slide_w // patch_size) + 1
    
    # 2. Create the Matrix
    grid = np.zeros((grid_h, grid_w))
    
    # 3. Clean Coords
    coords = coords.squeeze()
    if coords.ndim > 1 and coords.shape[1] > 2: coords = coords[:, :2]
    
    # 4. Populate Matrix (Mathematical Adjacency)
    for i in range(coords.shape[0]):
        try:
            x = coords[i, 0].item()
            y = coords[i, 1].item()
            score = attention_scores[i].item()
            
            # Map absolute x,y to grid integer indices
            col = int(x // patch_size)
            row = int(y // patch_size)
            
            if row < grid_h and col < grid_w:
                grid[row, col] = score
        except:
            continue
            
    return grid

# ================= 9-STYLE GENERATOR =================

def generate_mega_sheet(slide_path, coords, attention, pred_label, confidence, output_path):
    print(f"--- Generating 9-Style Comparison for {os.path.basename(slide_path)} ---")
    
    # Prepare Data
    if attention.dim() > 1:
        if attention.shape[0] == 1: attention = attention.squeeze(0)
        if attention.dim() > 1 and attention.shape[1] > 1: attention = attention.mean(dim=1)
    attention = attention.view(-1).cpu()

    try:
        wsi = openslide.OpenSlide(slide_path)
        slide_dims = wsi.dimensions
        
        # Get Thumbnail
        thumbnail = wsi.get_thumbnail((1500, 1500)).convert("RGB")
        thumb_size = thumbnail.size
        thumbnail_gray = ImageOps.grayscale(thumbnail).convert("RGB")
    except Exception as e:
        print(f"❌ Error reading slide: {e}")
        return

    # --- THE FIX: Create Perfect Matrix & Resize ---
    # 1. Create the gap-free matrix representing the full slide
    full_slide_matrix = create_perfect_grid(coords, attention, slide_dims, PATCH_SIZE)
    
    # 2. Normalize
    if full_slide_matrix.max() > 0: 
        heatmap_norm = full_slide_matrix / full_slide_matrix.max()
    else: 
        heatmap_norm = full_slide_matrix

    # 3. Resize Matrix to Match Thumbnail Exactly
    # 'NEAREST' preserves the sharp squares (for scientific view)
    # 'BILINEAR' creates the smooth gradients (for classic view)
    
    heatmap_img = Image.fromarray((heatmap_norm * 255).astype(np.uint8))
    
    # Smooth (Classic)
    heatmap_smooth = np.array(heatmap_img.resize(thumb_size, resample=Image.BILINEAR))
    
    # Blocky (Scientific) - This will now look solid, no gaps!
    heatmap_blocky = np.array(heatmap_img.resize(thumb_size, resample=Image.NEAREST))
    
    # Apply slight blur to smooth version to remove pixelation artifacts
    heatmap_smooth = gaussian_filter(heatmap_smooth, sigma=3)

    # --- PLOTTING ---
    plt.figure(figsize=(24, 28))
    gs = gridspec.GridSpec(4, 3, height_ratios=[1, 1, 1, 0.4])

    def plot_style(ax_idx, title, bg_img, overlay_data, cmap, alpha=0.5, thresh=0.0, contour=False):
        ax = plt.subplot(gs[ax_idx])
        ax.imshow(bg_img)
        
        data = overlay_data.copy()
        
        # Proper Masking
        if thresh > 0:
            masked = np.ma.masked_where(data < (thresh * 255), data)
        else:
            # Mask absolute zeros
            masked = np.ma.masked_where(data <= 1, data) # <=1 handles noise
            
        if contour:
            h, w = data.shape
            X, Y = np.meshgrid(np.arange(w), np.arange(h))
            try:
                # Use fewer, thicker levels for better visibility
                ax.contour(X, Y, data, levels=[50, 100, 150, 200], cmap=cmap, linewidths=2, alpha=0.9)
                ax.imshow(masked, cmap=cmap, alpha=0.2)
            except:
                ax.imshow(masked, cmap=cmap, alpha=alpha)
        else:
            ax.imshow(masked, cmap=cmap, alpha=alpha, interpolation='none')
            
        ax.set_title(title, fontsize=18, weight='bold')
        ax.axis('off')

    # Row 1
    plot_style((0,0), "1. Classic (Jet, Smooth)", thumbnail, heatmap_smooth, 'jet', alpha=0.5)
    plot_style((0,1), "2. Scientific (Viridis, Blocky)", thumbnail, heatmap_blocky, 'viridis', alpha=0.6)
    plot_style((0,2), "3. High Contrast (Plasma)", thumbnail, heatmap_smooth, 'plasma', alpha=0.6)

    # Row 2
    plot_style((1,0), "4. Hotspots Only (>20%)", thumbnail, heatmap_smooth, 'magma', alpha=0.7, thresh=0.2)
    plot_style((1,1), "5. Red Clouds (Alpha Weighted)", thumbnail, heatmap_smooth, 'Reds', alpha=0.6)
    plot_style((1,2), "6. Diverging (Coolwarm)", thumbnail, heatmap_smooth, 'coolwarm', alpha=0.5)

    # Row 3
    plot_style((2,0), "7. Pop Art (Grayscale BG)", thumbnail_gray, heatmap_smooth, 'jet', alpha=0.4) 
    plot_style((2,1), "8. Turbo (High-Vis)", thumbnail, heatmap_smooth, 'turbo', alpha=0.5)
    plot_style((2,2), "9. Contour Lines", thumbnail, heatmap_smooth, 'jet', contour=True)

    # Row 4 (Info & Patches)
    ax_text = plt.subplot(gs[3, 0])
    ax_text.axis('off')
    color = 'red' if pred_label == 'CANCER' else 'green'
    ax_text.text(0.1, 0.7, f"Slide: {os.path.basename(slide_path)[:15]}...", fontsize=16)
    ax_text.text(0.1, 0.5, f"Prediction: {pred_label}", fontsize=24, weight='bold', color=color)
    ax_text.text(0.1, 0.3, f"Confidence: {confidence:.2f}%", fontsize=20)

    # Coords safe slicing
    coords = coords.squeeze()
    if coords.ndim > 1 and coords.shape[1] > 2: coords_safe = coords[:, :2]
    else: coords_safe = coords

    _, top_indices = torch.topk(attention, 2)
    top_indices = top_indices.cpu().numpy()
    
    for i, idx in enumerate(top_indices):
        ax_patch = plt.subplot(gs[3, i + 1])
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
    save_path = os.path.join(output_path, f"MEGA_{SLIDE_NAME}.png")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"✓ Mega Comparison Saved: {save_path}")

# ================= INFERENCE LOGIC =================

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
    
    try:
        model.load_state_dict(state_dict, strict=True)
    except:
        model.load_state_dict(state_dict, strict=False) 

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

        attention = None
        if 'A' in captured: attention = captured['A']
        elif isinstance(results, dict) and 'A' in results: attention = results['A']
        elif isinstance(results, tuple) and isinstance(results[0], dict) and 'A' in results[0]: attention = results[0]['A']
        
        if attention is None: attention = torch.zeros((features.shape[1], 1))
        if isinstance(attention, tuple): attention = attention[0]
        attention = attention.clone().detach().cpu()

    generate_mega_sheet(slide_path, coords, attention, pred_label, confidence * 100, OUTPUT_DIR)

if __name__ == "__main__":
    run_inference(SLIDE_NAME, ROOT_DIR, CHECKPOINT_PATH)