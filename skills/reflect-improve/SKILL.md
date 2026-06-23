---
name: reflect-improve
description: Analyze training results, diagnose issues, apply code patches, and retrain in a loop. Use after algo-implement when target accuracy is not met. Trigger words: "reflect", "improve accuracy", "反思优化", "diagnose training", "retrain", "accuracy not met".
argument-hint: [path-to-TASK_SPEC.json]
allowed-tools: Bash(*), Read, Write
---

# Reflect & Improve

Diagnose and improve training results for: $ARGUMENTS

## Constants

- **MAX_ITERATIONS = 3** (reflect-retrain cycles before giving up)
- **MIN_IMPROVEMENT = 0.005** (minimum accuracy gain to continue)
- **CONVERGENCE_CHECK = true** (stop if accuracy regresses)

## Workflow

### Step 1: Load Current Status

```bash
python3 -c "
import json
spec = json.load(open('$ARGUMENTS'))
r = json.load(open('$(dirname "$ARGUMENTS")/result.json'))
print('test_acc:', r.get('test_acc', 0))
print('target  :', spec['target_metrics'].get('accuracy', 0.85))
print('gap     :', spec['target_metrics'].get('accuracy', 0.85) - r.get('test_acc', 0))
"
```

If `gap <= 0` → target already met. Skip to `/model-deliver`.

### Step 2: Run Reflection Engine

```bash
python3 tools/reflect_engine.py "$ARGUMENTS" --auto-patch
```

Expected output format:
```json
{
  "diagnoses": [
    {
      "type": "overfitting",
      "severity": "high",
      "evidence": "train_acc=0.92 vs val_acc=0.71, gap=0.21",
      "suggestions": [...]
    }
  ],
  "patches": [...],
  "applied_patches": ["[PATCHED] Increase dropout to 0.5 in model"],
  "recommendation": "Apply regularization patches and retrain."
}
```

### Step 3: Interpret Diagnoses

**Overfitting** (train >> val):
- Increase dropout (→ 0.5), weight_decay (→ 1e-3)
- Add augmentation: time_shift, amplitude_jitter
- Reduce model size if needed

**Underfitting** (train_acc << target):
- Increase lr (→ 5e-3), epochs (→ 100)
- Upgrade architecture (→ csi_lite_transformer)
- Check data quality and preprocessing

**Unstable Training** (val oscillating):
- Reduce lr, reduce grad_clip
- Increase batch_size for smoother gradients

**Plateau** (no improvement for 10+ epochs):
- Manual lr reduction (÷5) and continue
- Try different optimizer (SGD + momentum)
- Change preprocessing strategy

**No specific diagnosis (just accuracy gap)**:
- Default: more epochs + lower lr

### Step 4: Apply and Verify Patches

After `--auto-patch`, confirm changes in train.py:

```bash
grep -n "Dropout\|weight_decay\|lr\s*=" "$(dirname "$ARGUMENTS")/code/train.py" | head -20
```

If manual patch needed (e.g., architecture change):

For architecture change to `csi_lite_transformer`:
```bash
python3 -c "
import json, re
from pathlib import Path
train_py = Path('$(dirname "$ARGUMENTS")/code/train.py')
content = train_py.read_text()
# Update model class instantiation
content = re.sub(
    r'CSIResNet1D\(in_channels=in_channels',
    'CSILiteTransformer(in_channels=in_channels',
    content
)
content = re.sub(r'arch=\"csi_resnet1d\"', 'arch=\"csi_lite_transformer\"', content)
train_py.write_text(content)
print('Patched: ResNet1D → LiteTransformer')
"
```

### Step 5: Retrain

```bash
python3 tools/stages/algo_implement.py "$ARGUMENTS" --skip-install
```

Monitor:
```bash
tail -f "$(dirname "$ARGUMENTS")/implement_log.txt"
```

### Step 6: Compare Results

```bash
python3 -c "
import json
from pathlib import Path
runs = [json.loads(l) for l in Path('$(dirname "$ARGUMENTS")/runs.jsonl').read_text().splitlines() if l.strip()]
print('Run history:')
for r in runs:
    print(f\"  {r.get('run_id','?')} | test_acc={r.get('test_acc',0):.3f} | {r.get('arch','?')}\")
"
```

**Decision tree after retraining:**
- `test_acc >= target` → Proceed to `/model-deliver`
- `test_acc improved but still below target AND iterations < MAX` → Loop back to Step 2
- `test_acc regressed` → Revert patch, try different suggestion
- `iterations >= MAX` → Accept best result, proceed to `/model-deliver` with caveat

### Step 7: Run Full Loop (Alternative)

For full automated loop:
```bash
python3 tools/stages/reflect_improve.py "$ARGUMENTS" --max-iterations 3
```

### Step 8: Report

```text
Reflect & Improve Complete
==========================
Iterations  : 2
Initial acc : 82.3%
Final acc   : 87.1%  (target: 85%)
Target met  : YES

Diagnoses:
  [1] overfitting (high) → applied: increase_dropout, add_weight_decay
  [2] plateau (medium)   → applied: reduce_lr

reflect_summary.json → experiments/<task_id>/reflect_summary.json

Suggested next step:
/model-deliver "experiments/<task_id>/TASK_SPEC.json"
```

## Key Rules

- Read REFLECT_REPORT.json carefully before applying any patch
- Never apply a dropout increase AND an architecture downgrade simultaneously
- Track every iteration in runs.jsonl — never overwrite, always append
- If after 3 iterations accuracy is still 5%+ below target, flag for human review
- Always record reflect-loop outcome in TASK_SPEC.json `agent_decisions[]`
- Prefer incremental changes over drastic ones; one patch per iteration
