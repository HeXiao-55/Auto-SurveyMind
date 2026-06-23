"""CSI-HAR code scaffold generator.

Given a TASK_SPEC.json, generates ready-to-run training and inference scripts
with appropriate dataset loaders, preprocessors, and model architectures.
All generated code runs on CPU only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Model architecture code snippets
# ---------------------------------------------------------------------------

_MODEL_CODE: dict[str, str] = {
    "csi_1dcnn": """
class CSI1DCNN(nn.Module):
    \"\"\"Lightweight 1D-CNN for CSI time-series classification.\"\"\"

    def __init__(self, in_channels: int, num_classes: int, seq_len: int = 500):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, 64, kernel_size=7, padding=3)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=5, padding=2)
        self.conv3 = nn.Conv1d(128, 64, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(64)
        self.bn2 = nn.BatchNorm1d(128)
        self.bn3 = nn.BatchNorm1d(64)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(64, num_classes)

    def forward(self, x):
        # x: [B, C, T]
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x).squeeze(-1)
        x = self.dropout(x)
        return self.fc(x)
""",

    "csi_bilstm": """
class CSIBiLSTM(nn.Module):
    \"\"\"Bidirectional LSTM for CSI sequential modeling.\"\"\"

    def __init__(self, in_channels: int, num_classes: int, hidden_size: int = 64, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            in_channels, hidden_size, num_layers=num_layers,
            batch_first=True, bidirectional=True, dropout=0.3 if num_layers > 1 else 0
        )
        self.dropout = nn.Dropout(0.3)
        self.fc = nn.Linear(hidden_size * 2, num_classes)

    def forward(self, x):
        # x: [B, T, C] (time-first for LSTM)
        if x.ndim == 3 and x.shape[1] != x.shape[2]:
            x = x.transpose(1, 2)  # [B, C, T] → [B, T, C]
        out, _ = self.lstm(x)
        out = self.dropout(out[:, -1, :])  # last time step
        return self.fc(out)
""",

    "csi_cnn_lstm": """
class CSICnnLstm(nn.Module):
    \"\"\"CNN feature extractor + LSTM temporal modeling.\"\"\"

    def __init__(self, in_channels: int, num_classes: int):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=5, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.MaxPool1d(2),
        )
        self.lstm = nn.LSTM(128, 64, num_layers=1, batch_first=True)
        self.dropout = nn.Dropout(0.4)
        self.fc = nn.Linear(64, num_classes)

    def forward(self, x):
        # x: [B, C, T]
        x = self.cnn(x)          # [B, 128, T//4]
        x = x.transpose(1, 2)    # [B, T//4, 128]
        _, (h, _) = self.lstm(x)
        x = self.dropout(h[-1])
        return self.fc(x)
""",

    "csi_lite_transformer": """
class CSILiteTransformer(nn.Module):
    \"\"\"Lightweight Transformer for CSI recognition (CPU-friendly).\"\"\"

    def __init__(self, in_channels: int, num_classes: int, seq_len: int = 500,
                 d_model: int = 64, nhead: int = 2, num_layers: int = 2):
        super().__init__()
        self.proj = nn.Linear(in_channels, d_model)
        self.pos_enc = nn.Embedding(seq_len + 1, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=128,
            dropout=0.1, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model))
        self.fc = nn.Linear(d_model, num_classes)

    def forward(self, x):
        # x: [B, C, T] → [B, T, C]
        if x.ndim == 3:
            x = x.transpose(1, 2)
        B, T, _ = x.shape
        x = self.proj(x)
        cls = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls, x], dim=1)                   # [B, T+1, d_model]
        pos = self.pos_enc(torch.arange(T + 1, device=x.device)).unsqueeze(0)
        x = x + pos
        x = self.transformer(x)
        return self.fc(x[:, 0])                           # CLS token output
""",

    "csi_resnet1d": """
class _ResBlock1D(nn.Module):
    def __init__(self, channels: int, kernel_size: int = 3):
        super().__init__()
        pad = kernel_size // 2
        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=pad)
        self.bn1 = nn.BatchNorm1d(channels)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=pad)
        self.bn2 = nn.BatchNorm1d(channels)

    def forward(self, x):
        residual = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return F.relu(x + residual)


class CSIResNet1D(nn.Module):
    \"\"\"1D ResNet for CSI time-series classification.\"\"\"

    def __init__(self, in_channels: int, num_classes: int, base_channels: int = 64):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, base_channels, kernel_size=7, padding=3),
            nn.BatchNorm1d(base_channels),
            nn.ReLU(),
        )
        self.blocks = nn.Sequential(
            _ResBlock1D(base_channels),
            _ResBlock1D(base_channels),
            nn.Conv1d(base_channels, base_channels * 2, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm1d(base_channels * 2),
            nn.ReLU(),
            _ResBlock1D(base_channels * 2),
            _ResBlock1D(base_channels * 2),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(base_channels * 2, num_classes)

    def forward(self, x):
        # x: [B, C, T]
        x = self.stem(x)
        x = self.blocks(x)
        x = self.pool(x).squeeze(-1)
        return self.fc(x)
""",
}


# ---------------------------------------------------------------------------
# Dataset loader templates
# ---------------------------------------------------------------------------

_DATASET_LOADERS = {
    "UT-HAR": """
class UTHARDataset(Dataset):
    \"\"\"UT-HAR WiFi Activity Recognition Dataset.
    Source: https://github.com/ermongroup/Wifi_Activity_Recognition
    Classes: lie=0, fall=1, walk=2, pickup=3, run=4, sit=5, stand=6
    \"\"\"
    LABELS = ["lie", "fall", "walk", "pickup", "run", "sit", "stand"]

    def __init__(self, data_dir: str, split: str = "train", transform=None):
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.samples, self.labels = self._load(split)

    def _load(self, split: str):
        # UT-HAR stores data as numpy arrays
        # data_x.npy: [N, 250, 90], data_y.npy: [N,]
        x_path = self.data_dir / "data_x.npy"
        y_path = self.data_dir / "data_y.npy"
        if not x_path.exists():
            raise FileNotFoundError(f"UT-HAR data not found at {self.data_dir}. "
                                    f"Download from https://github.com/ermongroup/Wifi_Activity_Recognition")
        X = np.load(str(x_path)).astype(np.float32)
        y = np.load(str(y_path)).astype(np.int64)
        return self._split(X, y, split)

    @staticmethod
    def _split(X, y, split: str):
        n = len(y)
        idx = np.random.permutation(n)
        t = int(0.6 * n); v = int(0.8 * n)
        splits = {"train": idx[:t], "val": idx[t:v], "test": idx[v:]}
        sel = splits[split]
        return X[sel], y[sel]

    def __len__(self): return len(self.labels)

    def __getitem__(self, idx):
        x = torch.tensor(self.samples[idx]).permute(1, 0)  # [C, T]
        y = torch.tensor(self.labels[idx], dtype=torch.long)
        if self.transform:
            x = self.transform(x)
        return x, y
""",

    "NTU-Fi": """
class NTUFiDataset(Dataset):
    \"\"\"NTU-Fi WiFi CSI HAR Dataset.
    Source: https://github.com/xyanchen/WiFi-CSI-Sensing-Benchmark
    Classes: box, circle, clean, fall, run, walk (6 classes)
    \"\"\"
    LABELS = ["box", "circle", "clean", "fall", "run", "walk"]

    def __init__(self, data_dir: str, split: str = "train", transform=None):
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.samples, self.labels = self._load(split)

    def _load(self, split: str):
        import scipy.io as sio
        all_x, all_y = [], []
        for cls_idx, cls_name in enumerate(self.LABELS):
            mat_path = self.data_dir / f"{cls_name}.mat"
            if not mat_path.exists():
                continue
            data = sio.loadmat(str(mat_path))
            key = [k for k in data if not k.startswith("_")][0]
            x = data[key].astype(np.float32)
            if x.ndim == 2:
                x = x[np.newaxis]
            for i in range(x.shape[0]):
                all_x.append(x[i])
                all_y.append(cls_idx)
        X = np.array(all_x)
        y = np.array(all_y)
        return UTHARDataset._split(X, y, split)

    def __len__(self): return len(self.labels)

    def __getitem__(self, idx):
        x = torch.tensor(self.samples[idx])
        if x.ndim == 1:
            x = x.unsqueeze(0)
        y = torch.tensor(self.labels[idx], dtype=torch.long)
        if self.transform:
            x = self.transform(x)
        return x, y
""",

    "WIDAR3.0": """
class WIDAR3Dataset(Dataset):
    \"\"\"WIDAR3.0 Gesture Dataset (subset mode for CPU-friendly training).
    Source: http://tns.thss.tsinghua.edu.cn/widar3/
    Uses pre-extracted BVP (Body-coordinate Velocity Profile) features.
    \"\"\"
    def __init__(self, data_dir: str, split: str = "train", max_samples: int = 2000):
        self.data_dir = Path(data_dir)
        self.max_samples = max_samples
        self.samples, self.labels = self._load(split)

    def _load(self, split: str):
        npy_file = self.data_dir / f"{split}_data.npy"
        lbl_file = self.data_dir / f"{split}_label.npy"
        if not npy_file.exists():
            raise FileNotFoundError(
                f"WIDAR3 data not found at {self.data_dir}. "
                "Please pre-process raw .mat files using tools/csi_har_scaffold.py --preprocess-widar"
            )
        X = np.load(str(npy_file)).astype(np.float32)
        y = np.load(str(lbl_file)).astype(np.int64)
        if len(y) > self.max_samples:
            idx = np.random.choice(len(y), self.max_samples, replace=False)
            X, y = X[idx], y[idx]
        return X, y

    def __len__(self): return len(self.labels)

    def __getitem__(self, idx):
        x = torch.tensor(self.samples[idx])
        if x.ndim == 2:
            x = x.unsqueeze(0)
        return x, torch.tensor(self.labels[idx], dtype=torch.long)
""",
}

_GENERIC_DATASET_LOADER = """
class GenericCSIDataset(Dataset):
    \"\"\"Generic loader for custom numpy/npz data.
    Expects data_dir containing data.npz with keys 'X' and 'y'.
    X shape: [N, T, C] or [N, C, T], y shape: [N,]
    \"\"\"
    def __init__(self, data_dir: str, split: str = "train"):
        data = np.load(Path(data_dir) / "data.npz")
        X = data["X"].astype(np.float32)
        y = data["y"].astype(np.int64)
        n = len(y)
        idx = np.random.RandomState(42).permutation(n)
        t = int(0.6 * n); v = int(0.8 * n)
        splits = {"train": idx[:t], "val": idx[t:v], "test": idx[v:]}
        sel = splits[split]
        self.X, self.y = X[sel], y[sel]

    def __len__(self): return len(self.y)

    def __getitem__(self, idx):
        x = torch.tensor(self.X[idx])
        if x.ndim == 1:
            x = x.unsqueeze(0)
        elif x.ndim == 2 and x.shape[0] > x.shape[1]:
            x = x.T  # ensure [C, T]
        return x, torch.tensor(self.y[idx], dtype=torch.long)
"""


def build_training_script(spec: dict[str, Any], output_dir: str) -> str:
    """Generate a complete training script from TASK_SPEC."""
    domain = spec.get("domain", "wifi_csi_har")
    dataset = spec.get("dataset") or "UT-HAR"
    num_classes = spec.get("num_classes") or 7
    constraints = spec.get("constraints", {})
    device = constraints.get("device", "cpu")
    target_acc = spec.get("target_metrics", {}).get("accuracy", 0.85)

    # Pick model based on constraints
    max_params = constraints.get("max_params_M", 1.0)
    if max_params <= 0.1:
        arch = "csi_1dcnn"
    elif max_params <= 0.3:
        arch = "csi_bilstm"
    elif constraints.get("real_time"):
        arch = "csi_1dcnn"
    else:
        arch = "csi_resnet1d"

    model_code = _MODEL_CODE.get(arch, _MODEL_CODE["csi_1dcnn"])
    dataset_code = _DATASET_LOADERS.get(dataset, _GENERIC_DATASET_LOADER)
    model_class = {
        "csi_1dcnn": "CSI1DCNN",
        "csi_bilstm": "CSIBiLSTM",
        "csi_cnn_lstm": "CSICnnLstm",
        "csi_lite_transformer": "CSILiteTransformer",
        "csi_resnet1d": "CSIResNet1D",
    }[arch]

    task_id = spec.get("task_id", "task_000")

    script = f'''#!/usr/bin/env python3
"""Auto-generated training script for {domain} ({dataset}).
Task: {spec.get("raw_description", "")[:80]}
Target accuracy: {target_acc:.0%}
Device: {device}
Generated by SurveyMind csi_har_scaffold.py
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------
{model_code}

# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------
{dataset_code}

# ---------------------------------------------------------------------------
# Preprocessing transforms
# ---------------------------------------------------------------------------

def normalize_csi(x: torch.Tensor) -> torch.Tensor:
    """Per-sample, per-channel normalization."""
    mu = x.mean(dim=-1, keepdim=True)
    sigma = x.std(dim=-1, keepdim=True) + 1e-8
    return (x - mu) / sigma


def hampel_filter_1d(x: torch.Tensor, k: int = 5, threshold: float = 3.0) -> torch.Tensor:
    """Hampel filter for outlier removal on 1D signal."""
    T = x.shape[-1]
    out = x.clone()
    for i in range(k, T - k):
        window = x[..., i - k : i + k + 1]
        med = window.median(dim=-1).values
        mad = (window - med.unsqueeze(-1)).abs().median(dim=-1).values
        dev = (x[..., i] - med).abs()
        mask = dev > threshold * 1.4826 * mad
        out[..., i] = torch.where(mask, med, x[..., i])
    return out


# ---------------------------------------------------------------------------
# Metrics logging
# ---------------------------------------------------------------------------

LOG_DIR = Path("{output_dir}") / "{task_id}"

def log_metrics(epoch: int, metrics: dict, log_path: Path | None = None) -> None:
    if log_path is None:
        log_path = LOG_DIR / "train_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps({{"epoch": epoch, "ts": time.time(), **metrics}}) + "\\n")


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, correct, n = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item() * len(y)
        correct += (logits.argmax(1) == y).sum().item()
        n += len(y)
    return total_loss / n, correct / n


def eval_epoch(model, loader, criterion, device):
    model.eval()
    total_loss, correct, n = 0.0, 0, 0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = criterion(logits, y)
            total_loss += loss.item() * len(y)
            correct += (logits.argmax(1) == y).sum().item()
            n += len(y)
    return total_loss / n, correct / n


def train(
    data_dir: str = "data/{dataset}",
    checkpoint_dir: str = str(LOG_DIR),
    epochs: int = 50,
    batch_size: int = 32,
    lr: float = 1e-3,
    device_str: str = "{device}",
    seed: int = 42,
) -> dict:
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device(device_str)

    # Datasets
    train_ds = {dataset.replace("-", "").replace(".", "")}Dataset(data_dir, split="train")
    val_ds   = {dataset.replace("-", "").replace(".", "")}Dataset(data_dir, split="val")
    test_ds  = {dataset.replace("-", "").replace(".", "")}Dataset(data_dir, split="test")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False, num_workers=0)

    # Sample shape
    sample_x, _ = train_ds[0]
    in_channels = sample_x.shape[0]

    # Model
    model = {model_class}(in_channels={num_classes}, num_classes={num_classes}).to(device)
    # Override in_channels from data
    model = {model_class}(in_channels=in_channels, num_classes={num_classes}).to(device)

    n_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"Model: {model_class}, params: {{n_params:.3f}}M, device: {{device}}")

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

    out_dir = Path(checkpoint_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "train_log.jsonl"

    best_val_acc, patience_cnt, best_epoch = 0.0, 0, 0
    early_stop_patience = 15

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        tr_loss, tr_acc = train_epoch(model, train_loader, optimizer, criterion, device)
        va_loss, va_acc = eval_epoch(model, val_loader, criterion, device)
        scheduler.step(va_loss)
        elapsed = time.time() - t0

        metrics = dict(
            train_loss=round(tr_loss, 4), train_acc=round(tr_acc, 4),
            val_loss=round(va_loss, 4), val_acc=round(va_acc, 4),
            lr=round(optimizer.param_groups[0]["lr"], 6), epoch_s=round(elapsed, 2),
        )
        log_metrics(epoch, metrics, log_path)

        if va_acc > best_val_acc:
            best_val_acc = va_acc
            best_epoch = epoch
            patience_cnt = 0
            ckpt_path = out_dir / "best_model.pt"
            torch.save({{"model_state_dict": model.state_dict(),
                         "epoch": epoch, "val_acc": va_acc,
                         "arch": "{arch}", "num_classes": {num_classes},
                         "in_channels": in_channels}}, ckpt_path)
        else:
            patience_cnt += 1

        print(f"Epoch {{epoch:3d}}/{{epochs}} | "
              f"train_loss={{tr_loss:.4f}} acc={{tr_acc:.3f}} | "
              f"val_loss={{va_loss:.4f}} acc={{va_acc:.3f}} | "
              f"best={{best_val_acc:.3f}}@{{best_epoch}} | {{elapsed:.1f}}s")

        if patience_cnt >= early_stop_patience:
            print(f"Early stopping at epoch {{epoch}}")
            break

    # Test evaluation
    model.load_state_dict(torch.load(out_dir / "best_model.pt",
                                     map_location=device)["model_state_dict"])
    _, test_acc = eval_epoch(model, test_loader, criterion, device)
    print(f"\\nTest accuracy: {{test_acc:.4f}} (target: {target_acc:.2f})")

    result = dict(
        best_val_acc=best_val_acc, test_acc=test_acc,
        best_epoch=best_epoch, total_epochs=epoch,
        target_met=test_acc >= {target_acc},
        checkpoint=str(out_dir / "best_model.pt"),
        arch="{arch}", num_classes={num_classes}, in_channels=in_channels,
    )
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/{dataset}")
    ap.add_argument("--checkpoint-dir", default=str(LOG_DIR))
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--device", default="{device}")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    result = train(
        data_dir=args.data_dir,
        checkpoint_dir=args.checkpoint_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        device_str=args.device,
        seed=args.seed,
    )
    print("\\nFinal result:")
    print(json.dumps(result, indent=2))
'''
    return script


def build_inference_script(spec: dict[str, Any], checkpoint_dir: str) -> str:
    """Generate a minimal inference/serving script."""
    num_classes = spec.get("num_classes") or 7
    actions = spec.get("actions") or [f"class_{i}" for i in range(num_classes)]
    task_id = spec.get("task_id", "task_000")
    return f'''#!/usr/bin/env python3
"""Auto-generated inference script for {task_id}.
Loads best_model.pt and serves predictions.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Re-import model definitions (from the training script in same dir)
sys.path.insert(0, str(Path(__file__).parent))

ACTIONS = {json.dumps(actions)}
CHECKPOINT_DIR = Path("{checkpoint_dir}")


def load_model(checkpoint_path: str = str(CHECKPOINT_DIR / "best_model.pt")):
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    arch = ckpt.get("arch", "csi_1dcnn")
    num_classes = ckpt.get("num_classes", {num_classes})
    in_channels = ckpt.get("in_channels", 90)

    arch_map = {{
        "csi_1dcnn":          "CSI1DCNN",
        "csi_bilstm":         "CSIBiLSTM",
        "csi_cnn_lstm":       "CSICnnLstm",
        "csi_lite_transformer": "CSILiteTransformer",
        "csi_resnet1d":       "CSIResNet1D",
    }}
    from train import *   # noqa: F401,F403 — load model classes
    cls = globals()[arch_map[arch]]
    model = cls(in_channels=in_channels, num_classes=num_classes)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, num_classes


def predict(x: np.ndarray, model=None, checkpoint_path: str | None = None) -> dict:
    """Predict activity class from raw CSI data.

    Args:
        x: numpy array [T, C] or [C, T], will be normalized automatically.
        model: pre-loaded model (optional, to avoid reloading).
        checkpoint_path: path to model checkpoint.

    Returns:
        dict with "class_id", "class_name", "confidence", "probabilities".
    """
    if model is None:
        model, _ = load_model(checkpoint_path or str(CHECKPOINT_DIR / "best_model.pt"))

    # Normalize
    t = torch.tensor(x.astype(np.float32))
    if t.ndim == 2 and t.shape[0] > t.shape[1]:
        t = t.T
    t = (t - t.mean(-1, keepdim=True)) / (t.std(-1, keepdim=True) + 1e-8)
    t = t.unsqueeze(0)   # [1, C, T]

    with torch.no_grad():
        logits = model(t)
        probs = F.softmax(logits, dim=-1).squeeze(0)
        class_id = probs.argmax().item()

    return {{
        "class_id": class_id,
        "class_name": ACTIONS[class_id] if class_id < len(ACTIONS) else f"class_{{class_id}}",
        "confidence": float(probs[class_id]),
        "probabilities": {{ACTIONS[i]: float(probs[i]) for i in range(len(probs))}},
    }}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--npy", required=True, help="Path to .npy file with CSI data [T,C]")
    ap.add_argument("--checkpoint", default=str(CHECKPOINT_DIR / "best_model.pt"))
    args = ap.parse_args()
    x = np.load(args.npy)
    model, _ = load_model(args.checkpoint)
    result = predict(x, model=model)
    print(json.dumps(result, indent=2))
'''


def scaffold(spec_path: str, output_dir: str | None = None) -> dict[str, str]:
    """Main entry point: generate all files from TASK_SPEC.json."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    task_id = spec.get("task_id", "task_000")
    out_dir = Path(output_dir or f"experiments/{task_id}/code")
    out_dir.mkdir(parents=True, exist_ok=True)

    train_script = build_training_script(spec, str(out_dir.parent))
    infer_script = build_inference_script(spec, str(out_dir.parent))

    train_path = out_dir / "train.py"
    infer_path = out_dir / "inference.py"
    train_path.write_text(train_script, encoding="utf-8")
    infer_path.write_text(infer_script, encoding="utf-8")

    reqs_path = out_dir / "requirements.txt"
    reqs_path.write_text(
        "torch>=2.0.0\nnumpy>=1.24.0\nscipy>=1.10.0\n", encoding="utf-8"
    )

    files = {
        "train_script": str(train_path),
        "inference_script": str(infer_path),
        "requirements": str(reqs_path),
    }
    manifest_path = out_dir / "scaffold_manifest.json"
    manifest_path.write_text(json.dumps(files, indent=2), encoding="utf-8")
    print(f"Scaffold generated: {out_dir}")
    for k, v in files.items():
        print(f"  {k}: {v}")
    return files


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate CSI-HAR training scaffold from TASK_SPEC.json")
    ap.add_argument("spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--output-dir", help="Output directory (default: experiments/<task_id>/code)")
    args = ap.parse_args()
    scaffold(args.spec, args.output_dir)
