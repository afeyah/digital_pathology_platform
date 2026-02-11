import os
import h5py
import numpy as np
import torch
import torch.nn as nn
from tqdm import tqdm  # <--- NEW IMPORT
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler, Subset
from sklearn.model_selection import train_test_split
from torchmetrics.classification import BinaryAccuracy, BinaryAUROC
from src.builder import create_model

# ==========================================
# 1. CONFIGURATION
# ==========================================
CANCER_DIR = '/mnt/k/work/wsl/wsi/fine-tune/TCGA-LUAD'          # Folder containing Cancer .h5 files (Label 1)
NORMAL_DIR = '/mnt/k/work/wsl/wsi/fine-tune/TCGA-LUAD-NORMAL'   # Folder containing Normal .h5 files (Label 0)
SAVE_PATH = 'abmil_luad_best.pth'

MODEL_NAME = 'abmil.base.uni_v2.pc108-24k'
NUM_CLASSES = 2
DROPOUT = 0.25
LR = 2e-4
WEIGHT_DECAY = 1e-4
NUM_EPOCHS = 25
BATCH_SIZE = 1 
PATIENCE = 5
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ==========================================
# 2. UTILITY CLASSES
# ==========================================
class EarlyStopping:
    def __init__(self, patience=5, min_delta=0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.early_stop = False

    def __call__(self, val_loss, model, path):
        if self.best_loss is None:
            self.best_loss = val_loss
            self.save_checkpoint(val_loss, model, path)
        elif val_loss > self.best_loss + self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_loss = val_loss
            self.save_checkpoint(val_loss, model, path)
            self.counter = 0

    def save_checkpoint(self, val_loss, model, path):
        torch.save(model.state_dict(), path)

class TCGALUADDataset(Dataset):
    def __init__(self, cancer_dir, normal_dir):
        self.files = []
        self.labels = []
        
        if os.path.exists(cancer_dir):
            for f in os.listdir(cancer_dir):
                if f.endswith('.h5'):
                    self.files.append(os.path.join(cancer_dir, f))
                    self.labels.append(1)
        
        if os.path.exists(normal_dir):
            for f in os.listdir(normal_dir):
                if f.endswith('.h5'):
                    self.files.append(os.path.join(normal_dir, f))
                    self.labels.append(0)

        print(f"Dataset Initialized: {self.labels.count(1)} Cancer (01Z), {self.labels.count(0)} Normal (11A)")

    def __len__(self): return len(self.files)

    def __getitem__(self, idx):
        h5_path = self.files[idx]
        label = self.labels[idx]
        with h5py.File(h5_path, 'r') as f:
            features = torch.from_numpy(f['features'][:]).squeeze(0)
        return features, torch.tensor(label).long()

# ==========================================
# 3. MAIN TRAINING FLOW
# ==========================================
def main():
    # --- A. Prepare Data ---
    full_dataset = TCGALUADDataset(CANCER_DIR, NORMAL_DIR)
    
    train_idx, val_idx = train_test_split(
        np.arange(len(full_dataset)), 
        test_size=0.2, 
        stratify=full_dataset.labels, 
        random_state=42
    )
    
    train_set = Subset(full_dataset, train_idx)
    val_set = Subset(full_dataset, val_idx)
    
    # --- B. Handle Class Imbalance ---
    train_labels = np.array([full_dataset.labels[i] for i in train_idx])
    class_counts = np.bincount(train_labels)
    class_weights = 1. / class_counts
    sample_weights = [class_weights[label] for label in train_labels]
    
    sampler = WeightedRandomSampler(weights=sample_weights, num_samples=len(sample_weights), replacement=True)
    
    train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, sampler=sampler, num_workers=4)
    val_loader = DataLoader(val_set, batch_size=BATCH_SIZE, shuffle=False, num_workers=4)
    
    # --- C. Load Model ---
    print(f"Loading Model: {MODEL_NAME}...")
    model = create_model(MODEL_NAME, num_classes=NUM_CLASSES, dropout=DROPOUT, from_pretrained=True)
    model.to(DEVICE)
    
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    criterion = nn.CrossEntropyLoss()
    early_stopping = EarlyStopping(patience=PATIENCE, min_delta=0.001)
    
    acc_metric = BinaryAccuracy().to(DEVICE)
    auc_metric = BinaryAUROC().to(DEVICE)
    
    # ==========================================
    # 4. TRAINING LOOP
    # ==========================================
    print(f"Starting training on {DEVICE}...")
    
    for epoch in range(NUM_EPOCHS):
        # --- TRAIN ---
        model.train()
        train_loss = 0
        
        # Wrapped with tqdm for progress bar
        train_loop = tqdm(train_loader, desc=f"Epoch {epoch+1}/{NUM_EPOCHS} [Train]", leave=False)
        
        for features, label in train_loop:
            features, label = features.to(DEVICE), label.to(DEVICE)
            
            results, _ = model(features, loss_fn=criterion, label=label)
            loss = results['loss']
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
            # Update progress bar with current loss
            train_loop.set_postfix(loss=loss.item())
            
        avg_train_loss = train_loss / len(train_loader)
        
        # --- VALIDATION ---
        model.eval()
        val_loss = 0
        val_probs_list = []
        val_labels_list = []
        
        # Wrapped with tqdm
        val_loop = tqdm(val_loader, desc=f"Epoch {epoch+1}/{NUM_EPOCHS} [Val  ]", leave=False)
        
        with torch.no_grad():
            for features, label in val_loop:
                features, label = features.to(DEVICE), label.to(DEVICE)
                
                results, _ = model(features, loss_fn=criterion, label=label)
                val_loss += results['loss'].item()
                
                probs = torch.softmax(results['logits'], dim=1)[:, 1]
                val_probs_list.append(probs)
                val_labels_list.append(label)
        
        avg_val_loss = val_loss / len(val_loader)
        
        # Compute Metrics
        val_probs = torch.cat(val_probs_list)
        val_labels = torch.cat(val_labels_list)
        
        epoch_acc = acc_metric(val_probs, val_labels)
        epoch_auc = auc_metric(val_probs, val_labels)
        
        # Print summary for the epoch
        print(f"Epoch {epoch+1:02d} | "
              f"Train Loss: {avg_train_loss:.4f} | "
              f"Val Loss: {avg_val_loss:.4f} | "
              f"Val Acc: {epoch_acc:.4f} | "
              f"Val AUC: {epoch_auc:.4f}")
        
        # --- CHECK EARLY STOPPING ---
        early_stopping(avg_val_loss, model, SAVE_PATH)
        
        if early_stopping.early_stop:
            print(f"Early stopping triggered at Epoch {epoch+1}. Best model saved.")
            break

    print(f"Training Complete. Best model saved to: {SAVE_PATH}")

if __name__ == "__main__":
    main()