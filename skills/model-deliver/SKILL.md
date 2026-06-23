---
name: model-deliver
description: Package trained model into deployment-ready bundle (ONNX + inference API + model card). Use after training succeeds or reflect-improve completes. Trigger words: "deliver model", "export model", "package model", "模型交付", "ONNX export", "inference API".
argument-hint: [path-to-TASK_SPEC.json]
allowed-tools: Bash(*), Read, Write
---

# Model Delivery

Package and deliver trained model for: $ARGUMENTS

## Constants

- **DELIVER_DIR = experiments/<task_id>/delivery/**
- **ONNX_OPSET = 17**
- **API_PORT = 8000**

## Workflow

### Step 1: Pre-flight Check

```bash
python3 -c "
import json
from pathlib import Path
spec = json.load(open('$ARGUMENTS'))
exp = Path('$ARGUMENTS').parent
print('checkpoint:', (exp / 'best_model.pt').exists())
print('result.json:', (exp / 'result.json').exists())
r = json.load(open(exp / 'result.json'))
print('test_acc:', r.get('test_acc', 0))
"
```

Ensure `best_model.pt` exists. If not, run `/algo-implement` first.

### Step 2: Package Model

```bash
python3 tools/model_packager.py "$ARGUMENTS"
```

Or via stage:
```bash
python3 tools/stages/model_deliver.py "$ARGUMENTS"
```

This creates:
```
experiments/<task_id>/delivery/
├── best_model.pt         # model checkpoint copy
├── model.onnx            # ONNX exported model (CPU-optimized)
├── inference.py          # standalone inference script
├── api_server.py         # FastAPI REST server
├── requirements_api.txt  # API dependencies
├── MODEL_CARD.md         # model card with metrics
└── delivery_manifest.json
```

### Step 3: Verify ONNX Export

```bash
python3 -c "
try:
    import onnxruntime as ort
    import numpy as np
    sess = ort.InferenceSession('$(dirname "$ARGUMENTS")/delivery/model.onnx')
    inp = sess.get_inputs()[0]
    print('Input name:', inp.name, 'shape:', inp.shape)
    # Run a dummy forward pass
    x = np.random.randn(1, inp.shape[1] if inp.shape[1] else 90, 500).astype(np.float32)
    out = sess.run(None, {inp.name: x})
    print('Output shape:', out[0].shape, '✓ ONNX OK')
except ImportError:
    print('onnxruntime not installed, skipping ONNX validation')
    print('Install: pip install onnxruntime')
except Exception as e:
    print('ONNX validation failed:', e)
"
```

If ONNX fails due to missing torch.onnx support:
```bash
# Skip ONNX and package rest
python3 tools/model_packager.py "$ARGUMENTS" --skip-onnx
```

### Step 4: Test Inference API

```bash
# Start server in background
cd "$(dirname "$ARGUMENTS")/delivery"
pip install fastapi uvicorn -q
python api_server.py &

# Test health endpoint
curl -s http://localhost:8000/health | python3 -m json.tool

# Test prediction
python3 -c "
import numpy as np, json, urllib.request
x = np.random.randn(500, 90).tolist()  # [T, C] → flatten to list of lists
req = urllib.request.Request(
    'http://localhost:8000/predict',
    data=json.dumps({'data': x}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = urllib.request.urlopen(req)
print(json.loads(resp.read()))
"
```

### Step 5: Review Model Card

```bash
cat "$(dirname "$ARGUMENTS")/delivery/MODEL_CARD.md"
```

Verify:
- Accuracy numbers correct
- Class names match dataset
- Usage examples working
- Limitations section appropriate

If any updates needed, edit directly:
```bash
# Edit manually
nano "$(dirname "$ARGUMENTS")/delivery/MODEL_CARD.md"
```

### Step 6: Create Delivery Summary

```bash
python3 -c "
import json
from pathlib import Path

manifest = json.load(open('$(dirname "$ARGUMENTS")/delivery/delivery_manifest.json'))
spec = json.load(open('$ARGUMENTS'))
result = json.load(open('$(dirname "$ARGUMENTS")/result.json'))

print('=== DELIVERY BUNDLE SUMMARY ===')
print(f'Task ID    : {spec[\"task_id\"]}')
print(f'Domain     : {spec[\"domain\"]}')
print(f'Test Acc   : {result.get(\"test_acc\", 0):.1%}')
print(f'Target Met : {result.get(\"target_met\", False)}')
print()
print('Files:')
for k, v in manifest.items():
    if isinstance(v, str) and Path(v).exists():
        size = Path(v).stat().st_size
        print(f'  {k:20s} : {v} ({size//1024}KB)')
"
```

### Step 7: Report

```text
Model Delivery Complete
========================
Task ID  : task_20260623_140000
Domain   : WiFi CSI HAR
Test Acc : 87.1%  (target: 85%)  ✅

Delivery Bundle: experiments/task_20260623_140000/delivery/
  best_model.pt      : 1.6 MB
  model.onnx         : 0.9 MB
  inference.py       : standalone inference
  api_server.py      : FastAPI REST (port 8000)
  MODEL_CARD.md      : model documentation

Pipeline Status: COMPLETED ✅

All stages: task_parse → algo_plan → algo_implement → reflect_improve → model_deliver
```

## Key Rules

- Always copy (not move) checkpoint to delivery directory
- If ONNX export fails, still deliver checkpoint + API + model card
- Verify ONNX with a dummy forward pass before marking as complete
- MODEL_CARD.md must include actual test accuracy, not estimated
- Update TASK_SPEC.json `model_artifact` and `pipeline_status.model_deliver`
- Check for inference correctness with at least one sample prediction
