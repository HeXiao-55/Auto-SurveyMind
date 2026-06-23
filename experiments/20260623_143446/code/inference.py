#!/usr/bin/env python3
"""Auto-generated inference script for task_20260623_143446.
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

ACTIONS = ["sit", "stand", "walk", "fall", "wave"]
CHECKPOINT_DIR = Path("experiments/20260623_143446")


def load_model(checkpoint_path: str = str(CHECKPOINT_DIR / "best_model.pt")):
    ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    arch = ckpt.get("arch", "csi_1dcnn")
    num_classes = ckpt.get("num_classes", 5)
    in_channels = ckpt.get("in_channels", 90)

    arch_map = {
        "csi_1dcnn":          "CSI1DCNN",
        "csi_bilstm":         "CSIBiLSTM",
        "csi_cnn_lstm":       "CSICnnLstm",
        "csi_lite_transformer": "CSILiteTransformer",
        "csi_resnet1d":       "CSIResNet1D",
    }
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

    return {
        "class_id": class_id,
        "class_name": ACTIONS[class_id] if class_id < len(ACTIONS) else f"class_{class_id}",
        "confidence": float(probs[class_id]),
        "probabilities": {ACTIONS[i]: float(probs[i]) for i in range(len(probs))},
    }


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
