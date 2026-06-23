"""Model Packager — export checkpoint to ONNX + generate inference API + model card.

Packages a trained PyTorch model for deployment:
  1. Export best_model.pt → model.onnx (CPU-optimized)
  2. Generate a FastAPI inference server script
  3. Write a model card (Markdown) with metrics and usage
  4. Create a delivery bundle manifest
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# ONNX export
# ---------------------------------------------------------------------------

_ONNX_EXPORT_SCRIPT = """
import sys, json, torch, torch.nn as nn, torch.nn.functional as F
from pathlib import Path

sys.path.insert(0, "{code_dir}")
# Bring model class definitions into scope
exec(open("{train_py}").read(), globals())

ckpt = torch.load("{checkpoint}", map_location="cpu", weights_only=False)
arch = ckpt.get("arch", "csi_1dcnn")
num_classes = ckpt.get("num_classes", {num_classes})
in_channels = ckpt.get("in_channels", {in_channels})
seq_len = {seq_len}

arch_map = {{
    "csi_1dcnn":           "CSI1DCNN",
    "csi_bilstm":          "CSIBiLSTM",
    "csi_cnn_lstm":        "CSICnnLstm",
    "csi_lite_transformer": "CSILiteTransformer",
    "csi_resnet1d":        "CSIResNet1D",
}}
ModelClass = globals()[arch_map[arch]]
model = ModelClass(in_channels=in_channels, num_classes=num_classes)
model.load_state_dict(ckpt["model_state_dict"])
model.eval()

dummy = torch.randn(1, in_channels, seq_len)
try:
    torch.onnx.export(
        model, dummy, "{onnx_path}",
        export_params=True, opset_version=17,
        do_constant_folding=True,
        input_names=["csi_input"],
        output_names=["class_logits"],
        dynamic_axes={{"csi_input": {{0: "batch_size", 2: "seq_len"}}}},
    )
    print(json.dumps({{"status": "ok", "onnx_path": "{onnx_path}"}}))
except Exception as e:
    print(json.dumps({{"status": "error", "error": str(e)}}))
"""


def export_onnx(
    checkpoint_path: str,
    code_dir: str,
    output_path: str,
    num_classes: int = 7,
    in_channels: int = 90,
    seq_len: int = 500,
) -> dict[str, Any]:
    """Export PyTorch checkpoint to ONNX format."""
    train_py = Path(code_dir) / "train.py"
    script = _ONNX_EXPORT_SCRIPT.format(
        code_dir=code_dir,
        train_py=str(train_py),
        checkpoint=checkpoint_path,
        onnx_path=output_path,
        num_classes=num_classes,
        in_channels=in_channels,
        seq_len=seq_len,
    )

    tmp = Path(output_path).parent / "_onnx_export_tmp.py"
    tmp.write_text(script, encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        tmp.unlink(missing_ok=True)
        if result.returncode == 0:
            last_line = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
            if last_line:
                return json.loads(last_line[-1])
        return {"status": "error", "stderr": result.stderr[-500:]}
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# FastAPI inference server
# ---------------------------------------------------------------------------

def generate_api_server(
    spec: dict[str, Any],
    checkpoint_dir: str,
    output_path: str,
) -> str:
    """Generate a FastAPI inference server script."""
    actions = spec.get("actions") or [f"class_{i}" for i in range(spec.get("num_classes", 7))]
    num_classes = spec.get("num_classes") or len(actions)
    task_id = spec.get("task_id", "task_000")
    domain = spec.get("domain", "wifi_csi_har")

    server_code = f'''#!/usr/bin/env python3
"""Auto-generated inference API for {task_id}.
Domain : {domain}
Classes: {actions}

Usage:
    pip install fastapi uvicorn numpy
    uvicorn api_server:app --host 0.0.0.0 --port 8000

POST /predict  {{  "data": [[...]] }}
               {{  "class_name": "walk", "confidence": 0.91, "probabilities": {{...}} }}
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F

# Ensure model code is importable
CODE_DIR = Path(__file__).parent / "code"
sys.path.insert(0, str(CODE_DIR))
exec(open(CODE_DIR / "train.py").read(), globals())

CHECKPOINT = Path(__file__).parent / "best_model.pt"
ACTIONS = {json.dumps(actions)}
_model = None


def _get_model():
    global _model
    if _model is None:
        ckpt = torch.load(str(CHECKPOINT), map_location="cpu", weights_only=False)
        arch = ckpt.get("arch", "csi_1dcnn")
        num_classes = ckpt.get("num_classes", {num_classes})
        in_channels = ckpt.get("in_channels", 90)
        arch_map = {{
            "csi_1dcnn": "CSI1DCNN", "csi_bilstm": "CSIBiLSTM",
            "csi_cnn_lstm": "CSICnnLstm",
            "csi_lite_transformer": "CSILiteTransformer",
            "csi_resnet1d": "CSIResNet1D",
        }}
        cls = globals()[arch_map[arch]]
        _model = cls(in_channels=in_channels, num_classes=num_classes)
        _model.load_state_dict(ckpt["model_state_dict"])
        _model.eval()
    return _model


def predict_array(x: np.ndarray) -> dict:
    """Run inference on CSI array [T, C] or [C, T]."""
    t = torch.tensor(x.astype(np.float32))
    if t.ndim == 2 and t.shape[0] > t.shape[1]:
        t = t.T
    t = (t - t.mean(-1, keepdim=True)) / (t.std(-1, keepdim=True) + 1e-8)
    t = t.unsqueeze(0)
    model = _get_model()
    with torch.no_grad():
        probs = F.softmax(model(t), dim=-1).squeeze(0)
        class_id = probs.argmax().item()
    return {{
        "class_id": class_id,
        "class_name": ACTIONS[class_id] if class_id < len(ACTIONS) else f"class_{{class_id}}",
        "confidence": float(probs[class_id]),
        "probabilities": {{ACTIONS[i]: float(probs[i]) for i in range(min(len(probs), len(ACTIONS)))}},
    }}


try:
    from fastapi import FastAPI
    from pydantic import BaseModel
    from typing import List

    app = FastAPI(title="{task_id} Inference API", version="1.0")

    class PredictRequest(BaseModel):
        data: List[List[float]]

    @app.get("/health")
    def health():
        return {{"status": "ok", "task_id": "{task_id}", "classes": ACTIONS}}

    @app.post("/predict")
    def predict(req: PredictRequest):
        x = np.array(req.data)
        return predict_array(x)

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

except ImportError:
    # FastAPI not available — provide basic CLI mode
    if __name__ == "__main__":
        import argparse
        ap = argparse.ArgumentParser()
        ap.add_argument("--npy", required=True)
        args = ap.parse_args()
        x = np.load(args.npy)
        result = predict_array(x)
        import json
        print(json.dumps(result, indent=2))
'''

    Path(output_path).write_text(server_code, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Model card generator
# ---------------------------------------------------------------------------

def generate_model_card(spec: dict[str, Any], result: dict[str, Any], output_path: str) -> str:
    """Generate a Markdown model card."""
    task_id = spec.get("task_id", "task_000")
    domain = spec.get("domain", "wifi_csi_har")
    dataset = spec.get("dataset") or "Unknown"
    num_classes = spec.get("num_classes") or 0
    actions = spec.get("actions") or []
    target = spec.get("target_metrics", {}).get("accuracy", 0.85)
    test_acc = result.get("test_acc", 0.0)
    best_val_acc = result.get("best_val_acc", 0.0)
    arch = result.get("arch", "unknown")
    in_channels = result.get("in_channels", "?")
    total_epochs = result.get("total_epochs", "?")
    device = spec.get("constraints", {}).get("device", "cpu")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    card = f"""# Model Card: {task_id}

**Generated by SurveyMind Algorithm R&D Pipeline**
Date: {now}

---

## Model Overview

| Field | Value |
|-------|-------|
| Domain | {domain} |
| Architecture | {arch} |
| Input | [B, {in_channels}, T] (CSI time-series) |
| Output | {num_classes} classes |
| Target Device | {device.upper()} |

## Performance

| Metric | Value | Target |
|--------|-------|--------|
| Test Accuracy | **{test_acc:.1%}** | {target:.0%} |
| Best Val Accuracy | {best_val_acc:.1%} | — |
| Target Met | {'✅ Yes' if test_acc >= target else '❌ No (gap: ' + f'{target - test_acc:.1%})'} |

## Training Details

- **Dataset**: {dataset}
- **Classes** ({num_classes}): {', '.join(actions) if actions else 'N/A'}
- **Training Epochs**: {total_epochs}
- **Device**: {device}

## Usage

### Python API

```python
import numpy as np
from inference import predict, load_model

model, _ = load_model("best_model.pt")
x = np.load("your_csi_data.npy")   # shape [T, C]
result = predict(x, model=model)
print(result)
# {{"class_name": "walk", "confidence": 0.91, ...}}
```

### REST API

```bash
pip install fastapi uvicorn
python api_server.py  # starts on :8000

curl -X POST http://localhost:8000/predict \\
     -H "Content-Type: application/json" \\
     -d '{{"data": [[...]]}}'
```

### ONNX Inference

```python
import onnxruntime as ort
import numpy as np

session = ort.InferenceSession("model.onnx")
x = np.random.randn(1, {in_channels}, 500).astype(np.float32)
logits = session.run(["class_logits"], {{"csi_input": x}})[0]
class_id = logits.argmax()
```

## Limitations

- Trained on {dataset}; performance may degrade on different hardware/environments
- Designed for CPU inference; GPU acceleration not tested
- Performance assumes same CSI collection configuration as training data

## License

Generated code is under the same license as SurveyMind (MIT). Training data license
follows {dataset} dataset terms.

---
*Model card auto-generated by SurveyMind model_packager.py*
"""

    Path(output_path).write_text(card, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Main packaging function
# ---------------------------------------------------------------------------

def package_model(task_spec_path: str, skip_onnx: bool = False) -> dict[str, Any]:
    """Package trained model for delivery.

    Args:
        task_spec_path: Path to TASK_SPEC.json
        skip_onnx: Skip ONNX export (e.g., if torch.onnx unavailable)

    Returns:
        Delivery manifest dict.
    """
    spec_path = Path(task_spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    exp_dir = spec_path.parent
    code_dir = exp_dir / "code"
    task_id = spec.get("task_id", "task_000")

    checkpoint = exp_dir / "best_model.pt"
    if not checkpoint.exists():
        return {"status": "error", "error": f"Checkpoint not found: {checkpoint}"}

    # Load training result
    result_path = exp_dir / "result.json"
    result: dict[str, Any] = {}
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))

    num_classes = result.get("num_classes") or spec.get("num_classes") or 7
    in_channels = result.get("in_channels", 90)

    deliver_dir = exp_dir / "delivery"
    deliver_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "checkpoint": str(checkpoint),
        "status": {},
    }

    # 1. Copy checkpoint
    import shutil
    shutil.copy2(checkpoint, deliver_dir / "best_model.pt")
    manifest["checkpoint_copy"] = str(deliver_dir / "best_model.pt")
    print(f"Checkpoint copied to {deliver_dir / 'best_model.pt'}")

    # 2. ONNX export
    onnx_path = str(deliver_dir / "model.onnx")
    if not skip_onnx:
        print("Exporting to ONNX ...")
        onnx_result = export_onnx(
            str(checkpoint), str(code_dir), onnx_path,
            num_classes=num_classes, in_channels=in_channels,
        )
        manifest["onnx"] = onnx_result
        manifest["status"]["onnx"] = onnx_result.get("status", "error")
        print(f"ONNX export: {onnx_result.get('status')}")
    else:
        manifest["status"]["onnx"] = "skipped"

    # 3. Inference API
    api_path = str(deliver_dir / "api_server.py")
    generate_api_server(spec, str(exp_dir), api_path)
    manifest["api_server"] = api_path
    manifest["status"]["api"] = "ok"
    print(f"Inference API: {api_path}")

    # 4. Model card
    card_path = str(deliver_dir / "MODEL_CARD.md")
    generate_model_card(spec, result, card_path)
    manifest["model_card"] = card_path
    manifest["status"]["model_card"] = "ok"
    print(f"Model card: {card_path}")

    # 5. Copy inference.py
    inference_py = code_dir / "inference.py"
    if inference_py.exists():
        shutil.copy2(inference_py, deliver_dir / "inference.py")
        manifest["inference_script"] = str(deliver_dir / "inference.py")

    # 6. Write API requirements
    api_req_path = deliver_dir / "requirements_api.txt"
    api_req_path.write_text("fastapi>=0.100.0\nuvicorn>=0.20.0\nnumpy>=1.24.0\ntorch>=2.0.0\n")
    manifest["api_requirements"] = str(api_req_path)

    # 7. Save manifest
    manifest_path = deliver_dir / "delivery_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    # Update task spec
    spec["pipeline_status"]["model_deliver"] = "completed"
    spec["model_artifact"] = {
        "checkpoint": str(checkpoint),
        "delivery_dir": str(deliver_dir),
        "onnx": onnx_path if not skip_onnx else None,
        "api_server": api_path,
        "model_card": card_path,
    }
    spec["agent_decisions"].append({
        "step": "model_deliver",
        "timestamp": datetime.now().isoformat(),
        "decision": f"Packaged model to {deliver_dir}. ONNX={manifest['status'].get('onnx')}, API=ok",
    })
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    print(f"\nDelivery bundle ready: {deliver_dir}")
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Package trained model for delivery")
    ap.add_argument("task_spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--skip-onnx", action="store_true", help="Skip ONNX export")
    args = ap.parse_args()
    manifest = package_model(args.task_spec, skip_onnx=args.skip_onnx)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
