---
name: task-parser
description: Parse natural language business requirements into a structured TASK_SPEC.json. Use when user says "我想做", "解析需求", "parse task", "task specification", or provides a plain-text ML task requirement. Entry point of the automated algorithm R&D pipeline.
argument-hint: [natural-language-requirement]
allowed-tools: Bash(*), Read, Write, WebSearch
---

# Task Parser

Parse business requirement into structured task specification: $ARGUMENTS

## Constants

- **OUTPUT_DIR** — where to write TASK_SPEC.json (default: `experiments/<task_id>/`)
- **DOMAIN_PROFILE_DIR = "templates/domain_profiles/"**
- **INTERACTIVE = true** — ask clarifying questions when confidence is low

## Workflow

### Step 1: Extract Structured Fields

Call the task parser tool:

```bash
python3 tools/task_parser.py "$ARGUMENTS" --output-dir experiments/$(date +%Y%m%d_%H%M%S) --print
```

Extracted fields:
- **domain**: wifi_csi_har / har_generic / vision / generic_ml
- **data_modality**: CSI matrix / image / time-series / tabular
- **dataset**: detected dataset name (WIDAR3.0, UT-HAR, NTU-Fi, etc.)
- **actions**: list of activity classes mentioned
- **num_classes**: number of classes
- **constraints**: device (cpu/gpu), max_params, max_inference_ms, real_time
- **target_metrics**: accuracy≥X%, f1≥X, inference≤Xms

### Step 2: Validate and Clarify

Review extracted fields. If any critical field is low-confidence or missing:

**Missing dataset** → suggest based on domain:
- WiFi CSI HAR, CPU, small → recommend UT-HAR (300MB, 7 classes)
- WiFi CSI HAR, gestures → recommend SignFi or WIDAR3.0
- WiFi CSI HAR, benchmark → recommend NTU-Fi

**Missing accuracy target** → ask:
```
No accuracy target detected. For WiFi CSI HAR, typical targets are:
- Quick validation: 75%
- Publication-ready: 85-90%
- State-of-the-art: 92%+
What is your target? (default: 85%)
```

**Missing action classes** → for WiFi CSI HAR, default to:
`[sit, stand, walk, fall, wave]`

### Step 3: Load Domain Profile

Read the matching domain profile:

```bash
cat templates/domain_profiles/wifi_csi_har.json
```

Cross-check:
- Are the specified actions in `domain_profile.actions`?
- Does the dataset exist in `domain_profile.datasets_info`?
- Are constraints compatible with available model architectures?

### Step 4: Write TASK_SPEC.json

```json
{
  "task_id": "task_20260623_140000",
  "domain": "wifi_csi_har",
  "data_modality": "CSI matrix",
  "domain_profile": "templates/domain_profiles/wifi_csi_har.json",
  "dataset": "UT-HAR",
  "num_classes": 7,
  "actions": ["lie", "fall", "walk", "pickup", "run", "sit", "stand"],
  "constraints": {
    "device": "cpu",
    "max_params_M": 1.0,
    "max_inference_ms": 100,
    "real_time": false
  },
  "target_metrics": {
    "accuracy": 0.85
  },
  "pipeline_status": {
    "task_parse": "completed",
    "algo_plan": "pending",
    "algo_implement": "pending",
    "reflect_improve": "pending",
    "model_deliver": "pending"
  },
  "agent_decisions": [...]
}
```

### Step 5: Report

```text
Task Specification Complete
===========================
Domain    : WiFi CSI Human Activity Recognition
Dataset   : UT-HAR  (7 classes, ~300MB, CPU-friendly)
Target    : accuracy ≥ 85%
Device    : CPU-only
Actions   : lie, fall, walk, pickup, run, sit, stand
Output    : experiments/task_20260623_140000/TASK_SPEC.json

Suggested next step:
/algo-plan "experiments/task_20260623_140000/TASK_SPEC.json"
```

## Key Rules

- If domain cannot be detected, ask before proceeding
- Default to cpu device when no constraint is specified (safe for all environments)
- Always write TASK_SPEC.json before calling next step
- Append every decision to `agent_decisions[]` for Dashboard traceability
- Keep TASK_SPEC.json as the single source of truth for the entire pipeline
