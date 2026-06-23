---
name: algo-implement
description: Generate code and execute CPU-only training from TASK_SPEC + ALGO_PLAN. Use after algo-plan completes. Trigger words: "run training", "implement algorithm", "执行训练", "start experiment", "generate code and run".
argument-hint: [path-to-TASK_SPEC.json]
allowed-tools: Bash(*), Read, Write
---

# Algorithm Implementer

Generate and execute training code for: $ARGUMENTS

## Constants

- **TIMEOUT_S = 3600** (max training time, 1 hour)
- **CPU_THREADS = 4** (OMP/MKL thread limit for CPU training)
- **MAX_RETRY = 2** (auto-retry on recoverable errors)

## Workflow

### Step 1: Pre-flight Checks

```bash
# Verify task spec and plan exist
cat "$ARGUMENTS"
ls "$(dirname "$ARGUMENTS")/ALGO_PLAN.json" 2>/dev/null || echo "ALGO_PLAN missing"
```

If ALGO_PLAN.json is missing → run `/algo-plan "$ARGUMENTS"` first.

Check data directory exists:
```bash
python3 -c "
import json
spec = json.load(open('$ARGUMENTS'))
dataset = spec.get('dataset', 'UT-HAR')
data_dir = spec.get('data_dir', f'data/{dataset}')
import os
print('data_dir:', data_dir, '| exists:', os.path.exists(data_dir))
"
```

If data not found → provide download instructions based on dataset:
- **UT-HAR**: `git clone https://github.com/ermongroup/Wifi_Activity_Recognition data/UT-HAR`
- **NTU-Fi**: `git clone https://github.com/xyanchen/WiFi-CSI-Sensing-Benchmark data/NTU-Fi`
- **Custom**: ask user for data path

### Step 2: Run Algo-Implement Stage

```bash
python3 -m stages.algo_implement "$ARGUMENTS" --timeout 3600
```

Or via CLI:
```bash
python3 tools/stages/algo_implement.py "$ARGUMENTS"
```

This will:
1. Load TASK_SPEC.json + ALGO_PLAN.json
2. Scaffold `code/train.py` and `code/inference.py` (if absent)
3. Create isolated `.venv` and install `requirements.txt`
4. Execute training with CPU thread limits
5. Save metrics to `runs.jsonl` and `train_log.jsonl`

### Step 3: Monitor Progress

Check training output in real time:
```bash
tail -f "$(dirname "$ARGUMENTS")/implement_log.txt"
```

Check epoch-by-epoch metrics:
```bash
tail -20 "$(dirname "$ARGUMENTS")/train_log.jsonl" | python3 -c "
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    print(f\"Epoch {m['epoch']:3d} | train_acc={m.get('train_acc',0):.3f} val_acc={m.get('val_acc',0):.3f}\")
"
```

### Step 4: Error Recovery

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError` | Missing dependency | Add to requirements.txt, rerun |
| `FileNotFoundError: data` | Data dir wrong | Set `data_dir` in task spec |
| `RuntimeError: CUDA` | GPU code on CPU target | Check model doesn't use `.cuda()` |
| `ValueError: out of range` | Wrong num_classes | Check dataset label range |
| `MemoryError` | Batch too large | Halve batch_size in ALGO_PLAN.json |
| Training stuck at random | Seed issue | Add `--seed 42` |

For each error:
1. Read the error carefully
2. Patch `code/train.py` or `experiments/<task_id>/ALGO_PLAN.json`
3. Re-run: `python3 tools/stages/algo_implement.py "$ARGUMENTS" --skip-install`

### Step 5: Evaluate Results

```bash
cat "$(dirname "$ARGUMENTS")/result.json"
```

Parse key metrics:
```text
test_acc      : 0.823
target_met    : false  (target was 0.85)
best_val_acc  : 0.841
best_epoch    : 38
elapsed_s     : 847
```

**Decision tree:**
- `target_met == true` → proceed to `/model-deliver`
- `target_met == false` AND gap ≤ 3% → try `/reflect-improve` (minor tuning)
- `target_met == false` AND gap > 5% → `/reflect-improve` (architecture change)
- Training failed → fix error, rerun

### Step 6: Report

```text
Implementation Complete
=======================
Arch      : ResNet-1D (0.4M params)
Test Acc  : 82.3%  (target: 85%)
Best Epoch: 38 / 50
Elapsed   : 847s (CPU)
Status    : below target (gap: -2.7%)

runs.jsonl → experiments/<task_id>/runs.jsonl
checkpoint → experiments/<task_id>/best_model.pt

Suggested next step:
/reflect-improve "experiments/<task_id>/TASK_SPEC.json"
```

## Key Rules

- Always verify data directory exists before starting training
- Set OMP_NUM_THREADS=4 and MKL_NUM_THREADS=4 for CPU efficiency
- Never kill a running training job silently; log the termination reason
- If venv creation fails, fall back to system Python with a warning
- Log every run to `runs.jsonl` for the reflection phase
- Record every decision and error in TASK_SPEC.json `agent_decisions[]`
