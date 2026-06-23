---
name: algo-pipeline
description: End-to-end automated algorithm R&D pipeline for ML tasks. Chains task-parser → algo-plan → algo-implement → reflect-improve → model-deliver. Use when user provides a business requirement and wants fully automated algorithm development. Trigger words: "算法自演化", "end-to-end pipeline", "全流程", "auto R&D", "build a model for me", "start algo pipeline".
argument-hint: [natural-language-requirement-or-TASK_SPEC-path]
allowed-tools: Bash(*), Read, Write, WebSearch, mcp_deepxiv_search_papers
---

# Automated Algorithm R&D Pipeline

Full pipeline for: $ARGUMENTS

## Constants

- **MAX_REFLECT_ITERATIONS = 3**
- **TRAINING_TIMEOUT_S = 3600**
- **CHECKPOINT_AFTER_EACH_STAGE = true** (save state, allow resume)
- **DASHBOARD_AUTO_START = false** (user can enable)

## Pipeline Overview

```
NL Requirement
      │
      ▼
[Stage 1] task-parser     → TASK_SPEC.json
      │
      ▼
[Stage 2] algo-plan       → ALGO_PLAN.json + code scaffold
      │
      ▼
[Stage 3] algo-implement  → training + best_model.pt
      │
      ▼
[Stage 4] reflect-improve → diagnosis + patches + retrain (≤3 rounds)
      │
      ▼
[Stage 5] model-deliver   → ONNX + API + MODEL_CARD.md
      │
      ▼
     Done ✅
```

## Workflow

### Step 0: Input Routing

Check if input is a TASK_SPEC.json path or raw description:

```bash
python3 -c "
import sys, os
arg = '''$ARGUMENTS'''
if os.path.exists(arg) and arg.endswith('.json'):
    print('RESUME:' + arg)
else:
    print('NEW:' + arg)
"
```

- If `RESUME:` → load existing spec, find the first `pending` stage, continue from there
- If `NEW:` → start from Stage 1

### Step 1: Parse Task

```
/task-parser "$ARGUMENTS"
```

Wait for TASK_SPEC.json creation. Confirm:
```bash
cat experiments/*/TASK_SPEC.json | tail -1  # verify latest
```

**Human checkpoint**: Review the parsed spec. Key fields to verify:
- `domain` (should be `wifi_csi_har` for WiFi CSI tasks)
- `dataset` (confirm data is available or plan to download)
- `constraints.device` (confirm `cpu` for CPU-only requirement)
- `actions` (all expected activity classes listed)
- `target_metrics.accuracy` (reasonable target, 0.80-0.95)

If any field wrong → correct TASK_SPEC.json and continue:
```bash
python3 -c "
import json
from pathlib import Path
p = Path('experiments/TASK_ID/TASK_SPEC.json')
spec = json.load(open(p))
spec['dataset'] = 'NTU-Fi'  # override
p.write_text(json.dumps(spec, indent=2))
"
```

### Step 2: Plan Algorithm

```
/algo-plan "experiments/TASK_ID/TASK_SPEC.json"
```

Expected outputs:
- `experiments/TASK_ID/ALGO_PLAN.json`
- `experiments/TASK_ID/code/train.py`
- `experiments/TASK_ID/code/inference.py`
- `experiments/TASK_ID/code/requirements.txt`

**Human checkpoint (optional)**: Review ALGO_PLAN.json before training.
Critical fields:
- `model.architecture`: confirm CPU-compatible
- `model.params_M`: must be ≤ `constraints.max_params_M`
- `training.epochs` and `training.lr`: reasonable defaults?

### Step 3: Implement — Generate Code & Train

**Prerequisite: ensure data directory exists**:
```bash
python3 -c "
import json; spec = json.load(open('experiments/TASK_ID/TASK_SPEC.json'))
print('Dataset:', spec.get('dataset'), '| data_dir:', spec.get('data_dir', 'data/' + (spec.get('dataset') or 'UT-HAR')))
"
```

If data not downloaded yet, follow dataset-specific instructions:
- **UT-HAR** (smallest, recommended for quick start):
  ```bash
  git clone https://github.com/ermongroup/Wifi_Activity_Recognition data/UT-HAR
  ```
- **NTU-Fi**:
  ```bash
  git clone https://github.com/xyanchen/WiFi-CSI-Sensing-Benchmark data/NTU-Fi
  ```
- **WIDAR3.0**: Manual download from http://tns.thss.tsinghua.edu.cn/widar3/

Update `data_dir` in TASK_SPEC.json if data is in non-standard location.

Then run:
```
/algo-implement "experiments/TASK_ID/TASK_SPEC.json"
```

Monitor:
```bash
tail -f experiments/TASK_ID/implement_log.txt
```

After completion, check:
```bash
cat experiments/TASK_ID/result.json
```

### Step 4: Reflect & Improve (conditional)

Check whether target was met:
```bash
python3 -c "
import json
r = json.load(open('experiments/TASK_ID/result.json'))
t = json.load(open('experiments/TASK_ID/TASK_SPEC.json'))['target_metrics']['accuracy']
met = r.get('test_acc', 0) >= t
print('Target met:', met, '| acc:', r.get('test_acc'), '| target:', t)
"
```

**If target met** → skip to Step 5.

**If target not met**:
```
/reflect-improve "experiments/TASK_ID/TASK_SPEC.json"
```

This runs up to MAX_REFLECT_ITERATIONS=3 diagnosis→patch→retrain cycles automatically.

After reflect-improve:
```bash
cat experiments/TASK_ID/reflect_summary.json
```

If after 3 iterations accuracy is still significantly below target (>5% gap):
- Consider accepting current best result with a caveat in the model card
- Or update ALGO_PLAN.json with a stronger architecture and re-run Step 3
- Report the issue to the user and ask for guidance

### Step 5: Deliver Model

```
/model-deliver "experiments/TASK_ID/TASK_SPEC.json"
```

Verify delivery:
```bash
ls -lh experiments/TASK_ID/delivery/
cat experiments/TASK_ID/delivery/MODEL_CARD.md
```

### Step 6: Start Dashboard (optional)

```bash
pip install gradio matplotlib -q
python3 mcp-servers/dashboard/server.py --experiments-dir experiments --port 7860
```

Open: http://localhost:7860

### Step 7: Final Report

Generate and present a full pipeline completion report:

```bash
python3 -c "
import json
from pathlib import Path

task_id = 'TASK_ID'
exp_dir = Path('experiments') / task_id
spec = json.load(open(exp_dir / 'TASK_SPEC.json'))
result = json.load(open(exp_dir / 'result.json')) if (exp_dir / 'result.json').exists() else {}
reflect = json.load(open(exp_dir / 'reflect_summary.json')) if (exp_dir / 'reflect_summary.json').exists() else {}

print('=' * 50)
print('ALGORITHM R&D PIPELINE — COMPLETE')
print('=' * 50)
print(f'Task ID  : {spec[\"task_id\"]}')
print(f'Domain   : {spec[\"domain\"]}')
print(f'Dataset  : {spec.get(\"dataset\",\"?\")}')
print(f'Device   : {spec[\"constraints\"][\"device\"]}')
print()
print('RESULTS:')
print(f'  Architecture : {result.get(\"arch\", \"?\")}')
print(f'  Parameters   : {result.get(\"arch\",\"?\"):<15s}')
print(f'  Test Acc     : {result.get(\"test_acc\", 0):.1%}  (target: {spec[\"target_metrics\"][\"accuracy\"]:.0%})')
print(f'  Target Met   : {\"YES ✅\" if result.get(\"target_met\") else \"NO ❌\"}')
print(f'  Reflect Iters: {reflect.get(\"iterations\", 0)}')
print()
print('DELIVERY:')
for f in Path(f'{exp_dir}/delivery').glob('*'):
    print(f'  {f.name:<25s}  ({f.stat().st_size//1024}KB)')
print()
print('PIPELINE STATUS:')
for stage, status in spec['pipeline_status'].items():
    icon = '✅' if status == 'completed' else '❌' if status == 'failed' else '⏳'
    print(f'  {icon} {stage:<20s}: {status}')
"
```

## Key Rules

- Always start with TASK_SPEC.json validation (Stage 1) before any code execution
- Never skip the data directory check before training (Stage 3 prerequisite)
- Append every stage result to `agent_decisions[]` in TASK_SPEC.json
- Human checkpoints after task-parse and algo-plan are MANDATORY for first runs
- If a stage fails, check the `implement_log.txt` or `reflect_summary.json` for details
- Do NOT restart from scratch if a stage fails — resume from the failed stage
- Keep `runs.jsonl` as an immutable audit log; never delete it
- Total wall-clock time budget: 2 hours (CPU training limit)
