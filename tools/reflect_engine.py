"""Reflection Engine — analyze training history and suggest targeted improvements.

Reads train_log.jsonl and result.json, diagnoses issues, and generates
structured improvement suggestions written to REFLECT_REPORT.json.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Diagnostic rules
# ---------------------------------------------------------------------------

def _load_train_log(log_path: Path) -> list[dict]:
    """Load train_log.jsonl as a list of epoch dicts."""
    if not log_path.exists():
        return []
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return sorted(rows, key=lambda r: r.get("epoch", 0))


def _smooth(values: list[float], k: int = 3) -> list[float]:
    """Simple moving average smoothing."""
    out = []
    for i, v in enumerate(values):
        window = values[max(0, i - k) : i + 1]
        out.append(sum(window) / len(window))
    return out


def _diagnose_overfitting(log: list[dict]) -> dict[str, Any] | None:
    if len(log) < 10:
        return None
    train_accs = [r["train_acc"] for r in log if "train_acc" in r]
    val_accs   = [r["val_acc"]   for r in log if "val_acc"   in r]
    if len(train_accs) < 5 or len(val_accs) < 5:
        return None

    last_5_train = train_accs[-5:]
    last_5_val   = val_accs[-5:]
    gap = sum(last_5_train) / 5 - sum(last_5_val) / 5

    if gap > 0.15:
        return {
            "type": "overfitting",
            "severity": "high" if gap > 0.25 else "medium",
            "evidence": f"train_acc={sum(last_5_train)/5:.3f} vs val_acc={sum(last_5_val)/5:.3f}, gap={gap:.3f}",
            "suggestions": [
                {"change": "increase_dropout", "detail": "Increase dropout to 0.5 in model", "priority": 1},
                {"change": "add_weight_decay", "detail": "Set weight_decay=1e-3 (was 1e-4)", "priority": 2},
                {"change": "add_augmentation", "detail": "Add time_shift + amplitude_jitter augmentation", "priority": 3},
                {"change": "reduce_model_size", "detail": "Use smaller model (csi_1dcnn instead of csi_resnet1d)", "priority": 4},
            ],
        }
    return None


def _diagnose_underfitting(log: list[dict], target_acc: float) -> dict[str, Any] | None:
    if len(log) < 5:
        return None
    train_accs = [r["train_acc"] for r in log if "train_acc" in r]
    if not train_accs:
        return None
    best_train = max(train_accs)

    if best_train < target_acc - 0.10:
        return {
            "type": "underfitting",
            "severity": "high" if best_train < target_acc - 0.20 else "medium",
            "evidence": f"best_train_acc={best_train:.3f}, target={target_acc:.2f}",
            "suggestions": [
                {"change": "increase_lr", "detail": "Try lr=5e-3 (was 1e-3)", "priority": 1},
                {"change": "upgrade_arch", "detail": "Switch to stronger architecture (csi_lite_transformer)", "priority": 2},
                {"change": "increase_epochs", "detail": "Set epochs=100 with early-stop=20", "priority": 3},
                {"change": "reduce_regularization", "detail": "Lower weight_decay to 1e-5", "priority": 4},
            ],
        }
    return None


def _diagnose_unstable_training(log: list[dict]) -> dict[str, Any] | None:
    if len(log) < 8:
        return None
    val_accs = [r["val_acc"] for r in log if "val_acc" in r]
    if len(val_accs) < 8:
        return None

    smoothed = _smooth(val_accs, k=3)
    # Oscillation: std of (raw - smoothed)
    diffs = [abs(v - s) for v, s in zip(val_accs[-10:], smoothed[-10:])]
    instability = sum(diffs) / len(diffs)

    if instability > 0.04:
        return {
            "type": "unstable_training",
            "severity": "medium",
            "evidence": f"val_acc oscillation amplitude={instability:.3f}",
            "suggestions": [
                {"change": "reduce_lr", "detail": "Halve learning rate to 5e-4", "priority": 1},
                {"change": "add_grad_clip", "detail": "Reduce gradient clip from 1.0 to 0.5", "priority": 2},
                {"change": "increase_batch", "detail": "Double batch_size to 64 for smoother gradients", "priority": 3},
            ],
        }
    return None


def _diagnose_lr_schedule(log: list[dict]) -> dict[str, Any] | None:
    if len(log) < 10:
        return None
    lrs = [r["lr"] for r in log if "lr" in r]
    val_accs = [r["val_acc"] for r in log if "val_acc" in r]
    if len(lrs) < 5 or len(val_accs) < 5:
        return None

    # If LR decayed early but accuracy still low
    initial_lr = lrs[0]
    final_lr = lrs[-1]
    lr_ratio = final_lr / (initial_lr + 1e-10)
    best_val = max(val_accs)
    last_val = val_accs[-1]

    # LR decayed to near-zero but model still improving
    if lr_ratio < 0.01 and best_val > last_val + 0.01:
        return {
            "type": "lr_schedule_mismatch",
            "severity": "low",
            "evidence": f"LR decayed to {final_lr:.2e} ({lr_ratio:.1%} of initial), but best val was {best_val:.3f}",
            "suggestions": [
                {"change": "cosine_schedule", "detail": "Switch to CosineAnnealingLR for smoother decay", "priority": 1},
                {"change": "warmup_lr", "detail": "Add 5-epoch linear warmup before main schedule", "priority": 2},
            ],
        }
    return None


def _diagnose_plateau(log: list[dict], patience: int = 10) -> dict[str, Any] | None:
    """Detect training plateau: val_acc not improving for `patience` epochs."""
    val_accs = [r["val_acc"] for r in log if "val_acc" in r]
    if len(val_accs) < patience + 2:
        return None

    recent = val_accs[-patience:]
    older = val_accs[-(patience + 5):-patience] if len(val_accs) >= patience + 5 else []
    if not older:
        return None

    improvement = max(recent) - max(older)
    if improvement < 0.002:
        return {
            "type": "plateau",
            "severity": "medium",
            "evidence": f"val_acc improvement in last {patience} epochs: {improvement:.4f}",
            "suggestions": [
                {"change": "reduce_lr_manual", "detail": "Manually reduce lr by 5x and continue training", "priority": 1},
                {"change": "different_optimizer", "detail": "Try SGD with momentum=0.9 instead of Adam", "priority": 2},
                {"change": "change_preprocessing", "detail": "Try different preprocessing strategy (e.g., spectrogram)", "priority": 3},
            ],
        }
    return None


# ---------------------------------------------------------------------------
# Code patch generators
# ---------------------------------------------------------------------------

def _generate_patches(diagnoses: list[dict], train_py: Path) -> list[dict[str, str]]:
    """Generate code patches for the top suggestions across all diagnoses."""
    patches = []
    seen_changes: set[str] = set()

    # Collect top-priority suggestion from each diagnosis
    for diag in diagnoses:
        sugs = sorted(diag.get("suggestions", []), key=lambda s: s.get("priority", 99))
        for sug in sugs[:2]:  # Top 2 per diagnosis
            change = sug["change"]
            if change in seen_changes:
                continue
            seen_changes.add(change)
            patch = _make_patch(change, sug["detail"], train_py)
            if patch:
                patches.append(patch)

    return patches


def _make_patch(change: str, detail: str, train_py: Path) -> dict[str, str] | None:
    """Create a code-level patch description."""
    patch_map = {
        "increase_dropout": {
            "file": str(train_py),
            "description": detail,
            "regex": r"nn\.Dropout\(([\d.]+)\)",
            "replacement": "nn.Dropout(0.5)",
        },
        "add_weight_decay": {
            "file": str(train_py),
            "description": detail,
            "regex": r"weight_decay=[\d.e+-]+",
            "replacement": "weight_decay=1e-3",
        },
        "reduce_lr": {
            "file": str(train_py),
            "description": detail,
            "regex": r"lr:\s*float\s*=\s*[\d.e+-]+",
            "replacement": "lr: float = 5e-4",
        },
        "increase_lr": {
            "file": str(train_py),
            "description": detail,
            "regex": r"lr:\s*float\s*=\s*[\d.e+-]+",
            "replacement": "lr: float = 5e-3",
        },
        "increase_epochs": {
            "file": str(train_py),
            "description": detail,
            "regex": r"epochs:\s*int\s*=\s*\d+",
            "replacement": "epochs: int = 100",
        },
        "increase_batch": {
            "file": str(train_py),
            "description": detail,
            "regex": r"batch_size:\s*int\s*=\s*\d+",
            "replacement": "batch_size: int = 64",
        },
        "cosine_schedule": {
            "file": str(train_py),
            "description": detail,
            "regex": r"ReduceLROnPlateau\(optimizer,\s*patience=\d+,\s*factor=[\d.]+\)",
            "replacement": "CosineAnnealingLR(optimizer, T_max=50)",
        },
    }
    p = patch_map.get(change)
    if not p:
        return {"file": str(train_py), "description": detail, "change": change, "manual": True}
    return p


def _apply_patches(patches: list[dict[str, str]]) -> list[str]:
    """Apply regex patches to files. Returns list of applied patch descriptions."""
    applied = []
    for patch in patches:
        if patch.get("manual"):
            applied.append(f"[MANUAL] {patch['description']}")
            continue
        file_path = Path(patch["file"])
        if not file_path.exists():
            applied.append(f"[SKIP] {file_path} not found")
            continue
        content = file_path.read_text(encoding="utf-8")
        new_content = re.sub(patch["regex"], patch["replacement"], content)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            applied.append(f"[PATCHED] {patch['description']} in {file_path.name}")
        else:
            applied.append(f"[NO-MATCH] {patch['description']} (pattern not found in {file_path.name})")
    return applied


# ---------------------------------------------------------------------------
# Main reflection function
# ---------------------------------------------------------------------------

def reflect(
    task_spec_path: str,
    auto_patch: bool = False,
    max_iterations: int = 3,
) -> dict[str, Any]:
    """Analyze training results and generate improvement suggestions.

    Args:
        task_spec_path: Path to TASK_SPEC.json
        auto_patch: If True, automatically apply code patches for top suggestions
        max_iterations: Max number of reflect→retrain iterations allowed

    Returns:
        REFLECT_REPORT dict with diagnoses, suggestions, and patches.
    """
    spec_path = Path(task_spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    exp_dir = spec_path.parent
    task_id = spec.get("task_id", "task_000")

    target_acc = spec.get("target_metrics", {}).get("accuracy", 0.85)
    result_path = exp_dir / "result.json"
    log_path = exp_dir / "train_log.jsonl"
    train_py = exp_dir / "code" / "train.py"

    # Load latest run result
    result: dict[str, Any] = {}
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))

    # Load training history
    log = _load_train_log(log_path)

    test_acc = result.get("test_acc", 0.0)
    best_val_acc = result.get("best_val_acc", 0.0)
    target_met = result.get("target_met", False)

    # Count previous iterations
    runs_log = exp_dir / "runs.jsonl"
    num_runs = 0
    if runs_log.exists():
        num_runs = sum(1 for _ in runs_log.read_text().splitlines() if _.strip())

    report: dict[str, Any] = {
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "iteration": num_runs,
        "test_acc": test_acc,
        "best_val_acc": best_val_acc,
        "target_acc": target_acc,
        "target_met": target_met,
        "accuracy_gap": round(target_acc - test_acc, 4),
        "diagnoses": [],
        "patches": [],
        "applied_patches": [],
        "recommendation": "",
    }

    if target_met:
        report["recommendation"] = "TARGET MET — proceed to model delivery."
        _save_report(exp_dir, report)
        return report

    if num_runs >= max_iterations:
        report["recommendation"] = (
            f"MAX ITERATIONS ({max_iterations}) reached. "
            f"Best test_acc={test_acc:.3f}. Consider relaxing target or changing architecture."
        )
        _save_report(exp_dir, report)
        return report

    # Run diagnostics
    diagnoses = []
    for diag_fn, *args in [
        (_diagnose_overfitting, log),
        (_diagnose_underfitting, log, target_acc),
        (_diagnose_unstable_training, log),
        (_diagnose_lr_schedule, log),
        (_diagnose_plateau, log),
    ]:
        d = diag_fn(*args)
        if d:
            diagnoses.append(d)

    if not diagnoses:
        # Default: accuracy gap but no specific diagnosis
        gap = target_acc - test_acc
        diagnoses.append({
            "type": "accuracy_gap",
            "severity": "medium",
            "evidence": f"test_acc={test_acc:.3f}, target={target_acc:.2f}, gap={gap:.3f}",
            "suggestions": [
                {"change": "increase_epochs", "detail": "Increase epochs to 100", "priority": 1},
                {"change": "upgrade_arch", "detail": "Try csi_lite_transformer for better capacity", "priority": 2},
                {"change": "reduce_lr", "detail": "Try lower lr=5e-4 for finer convergence", "priority": 3},
            ],
        })

    report["diagnoses"] = diagnoses

    # Generate patches
    patches = _generate_patches(diagnoses, train_py)
    report["patches"] = patches

    # Optionally apply
    if auto_patch:
        applied = _apply_patches(patches)
        report["applied_patches"] = applied

    # Recommendation
    diag_types = [d["type"] for d in diagnoses]
    if "overfitting" in diag_types:
        report["recommendation"] = (
            "Apply regularization patches (dropout + weight_decay) and retrain. "
            f"Run: python3 tools/stages/algo_implement.py '{task_spec_path}' --skip-install"
        )
    elif "underfitting" in diag_types:
        report["recommendation"] = (
            "Increase model capacity or learning rate. "
            "Consider switching to csi_lite_transformer architecture."
        )
    elif "plateau" in diag_types:
        report["recommendation"] = "Reduce LR manually by 5x and retrain for 30 more epochs."
    else:
        report["recommendation"] = (
            "Minor tuning needed. Apply top-priority patches and retrain. "
            f"Gap = {report['accuracy_gap']:.3f}"
        )

    # Update task spec
    spec["pipeline_status"]["reflect_improve"] = "in_progress"
    spec["agent_decisions"].append({
        "step": "reflect_improve",
        "timestamp": datetime.now().isoformat(),
        "decision": (
            f"Diagnosis: {', '.join(diag_types) or 'none'}. "
            f"Gap={report['accuracy_gap']:.3f}. "
            f"Recommendation: {report['recommendation'][:100]}"
        ),
    })
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    _save_report(exp_dir, report)
    return report


def _save_report(exp_dir: Path, report: dict[str, Any]) -> None:
    out_path = exp_dir / "REFLECT_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"REFLECT_REPORT written: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Analyze training results and suggest improvements")
    ap.add_argument("task_spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--auto-patch", action="store_true", help="Automatically apply code patches")
    ap.add_argument("--max-iterations", type=int, default=3)
    args = ap.parse_args()
    report = reflect(args.task_spec, auto_patch=args.auto_patch, max_iterations=args.max_iterations)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
