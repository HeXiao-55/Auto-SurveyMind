---
name: algo-plan
description: Generate a structured algorithm plan (preprocessing pipeline + model architecture) from TASK_SPEC.json using SurveyMind knowledge base. Use when the task spec is ready and you need a concrete technical plan before implementation. Trigger words: "plan algorithm", "算法规划", "plan preprocessing", "choose model".
argument-hint: [path-to-TASK_SPEC.json]
allowed-tools: Bash(*), Read, Write, WebSearch, mcp_deepxiv_search_papers
---

# Algorithm Planner

Plan preprocessing + model architecture for: $ARGUMENTS

## Constants

- **DOMAIN_PROFILE = "templates/domain_profiles/wifi_csi_har.json"**
- **SURVEY_RESULTS_DIR = "surveys/"** (gate2 paper analysis output from SurveyMind)
- **MAX_SURVEY_PAPERS = 20** (number of papers to retrieve for context)
- **CPU_PARAM_LIMIT_M = 1.0** (max model parameters for CPU targets)

## Workflow

### Step 1: Load Task Specification

```bash
cat "$ARGUMENTS"
```

Extract key constraints:
- `domain`, `dataset`, `num_classes`, `actions`
- `constraints.device` (cpu/gpu)
- `constraints.max_params_M`, `constraints.max_inference_ms`
- `target_metrics.accuracy`

### Step 2: Survey Knowledge Retrieval

Search SurveyMind's existing knowledge base for relevant methods:

```bash
# If survey results exist for this domain
ls surveys/*/gate2_paper_analysis/ 2>/dev/null | head -5
```

If no cached survey exists, trigger a targeted search using DeepXiv:

```
mcp_deepxiv_search_papers({
  "query": "WiFi CSI human activity recognition deep learning CPU efficient",
  "max_results": 10
})
```

Then search for preprocessing-specific and model-specific papers:
```
mcp_deepxiv_search_papers({
  "query": "CSI signal preprocessing Hampel filter phase sanitization activity recognition",
  "max_results": 5
})
```

### Step 3: Select Preprocessing Strategy

Read the domain profile preprocessing strategies:

```bash
python3 -c "
import json
p = json.load(open('templates/domain_profiles/wifi_csi_har.json'))
for s in p['preprocessing_strategies']:
    print(s['name'], '-', s['description'], '|', s['cpu_cost'])
"
```

**Selection rules:**
- If `cpu_cost == high` → skip unless explicitly required
- If `constraints.real_time == true` → prefer `amplitude_only` (fastest)
- If actions include fine-grained gestures → prefer `phase_sanitized` or `spectrogram`
- If dataset == WIDAR3.0 → use `spectrogram` (literature standard)
- Default for basic HAR → `amplitude_only` or `pca_denoised`

### Step 4: Select Model Architecture

Read domain profile models and filter by constraints:

```bash
python3 -c "
import json
p = json.load(open('templates/domain_profiles/wifi_csi_har.json'))
device = 'cpu'  # from task spec
max_p = 1.0
for m in p['model_architectures']:
    if m.get('recommended_cpu') or device != 'cpu':
        print(m['name'], f\"{m['params_k']}K params\", f\"{m['cpu_inference_ms']}ms\", '-', m['description'])
"
```

**Selection rules (CPU-only):**
- `max_params_M <= 0.1` → `csi_1dcnn` (50K params)
- `max_inference_ms <= 10` → `csi_1dcnn` or `csi_bilstm`
- accuracy target >= 90% → `csi_resnet1d` or `csi_lite_transformer`
- accuracy target >= 85% (standard) → `csi_resnet1d` (strong, CPU-friendly)
- quick prototyping → `csi_1dcnn`

**Always verify:**
- Model input format matches preprocessing output
- CPU inference time estimate meets constraint

### Step 5: Design Training Configuration

Based on dataset size and constraints, set hyperparameters:

| Dataset | Epochs | Batch | LR | Early Stop |
|---------|--------|-------|----|------------|
| UT-HAR | 50 | 32 | 1e-3 | 10 |
| NTU-Fi | 80 | 32 | 5e-4 | 15 |
| WIDAR3.0 (subset) | 100 | 16 | 1e-3 | 20 |
| Custom | 60 | 32 | 1e-3 | 12 |

### Step 6: Write ALGO_PLAN.json

```json
{
  "task_id": "...",
  "created_at": "...",
  "preprocessing": {
    "strategy": "amplitude_only",
    "steps": [
      {"name": "extract_amplitude", "params": {}},
      {"name": "hampel_filter", "params": {"k": 5, "threshold": 3.0}},
      {"name": "bandpass_filter", "params": {"low_hz": 0.3, "high_hz": 3.0}},
      {"name": "normalize", "params": {"method": "per_channel_z_score"}}
    ],
    "output_shape": "[C, T]",
    "rationale": "CPU-friendly, robust to hardware variation"
  },
  "model": {
    "architecture": "csi_resnet1d",
    "display_name": "ResNet-1D",
    "params_M": 0.4,
    "estimated_cpu_inference_ms": 20,
    "input_format": "[B, C, T]",
    "rationale": "Strong baseline, residual connections prevent gradient vanishing"
  },
  "training": {
    "optimizer": "Adam",
    "lr": 1e-3,
    "lr_scheduler": "ReduceLROnPlateau",
    "batch_size": 32,
    "epochs": 50,
    "early_stopping_patience": 10,
    "weight_decay": 1e-4,
    "device": "cpu",
    "augmentation": ["time_shift", "amplitude_jitter"]
  },
  "ablation_candidates": [
    {"name": "no_hampel", "change": "remove hampel filter step"},
    {"name": "bilstm_arch", "change": "replace ResNet-1D with BiLSTM"},
    {"name": "lr_0.01", "change": "increase initial LR to 0.01"}
  ],
  "literature_support": [
    {"paper": "...", "supports": "ResNet for time-series classification"}
  ]
}
```

Update TASK_SPEC.json pipeline status:

```bash
python3 -c "
from tools.task_parser import update_pipeline_state
update_pipeline_state('$ARGUMENTS', 'algo_plan', 'completed',
  'Selected amplitude_only preprocessing + ResNet-1D model (0.4M params, CPU-friendly)')
"
```

### Step 7: Generate Code Scaffold

```bash
python3 tools/csi_har_scaffold.py "$ARGUMENTS"
```

Confirm scaffold files created:
- `experiments/<task_id>/code/train.py`
- `experiments/<task_id>/code/inference.py`
- `experiments/<task_id>/code/requirements.txt`

### Step 8: Report

```text
Algorithm Plan Complete
=======================
Preprocessing : amplitude_only → Hampel + bandpass + z-score
Model         : ResNet-1D (0.4M params, ~20ms CPU inference)
Training      : Adam, lr=1e-3, batch=32, 50 epochs, early-stop@10
Target        : 85% accuracy
Device        : CPU-only

ALGO_PLAN.json → experiments/<task_id>/ALGO_PLAN.json
Code scaffold  → experiments/<task_id>/code/

Suggested next step:
/algo-implement "experiments/<task_id>/TASK_SPEC.json"
```

## Key Rules

- Always explain rationale for preprocessing + model choice with literature references
- Never select GPU-heavy architectures (ViT-large, ResNet-50+) when device=cpu
- Estimate parameter count before selecting; reject if over max_params_M
- Update TASK_SPEC.json pipeline_status after writing ALGO_PLAN.json
- Keep ablation_candidates list for reflection phase
- ALGO_PLAN.json is the contract between planning and implementation
