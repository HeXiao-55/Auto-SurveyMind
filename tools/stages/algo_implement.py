"""Algo Implement stage — generate and execute training code from TASK_SPEC + ALGO_PLAN.

This stage:
  1. Loads TASK_SPEC.json + ALGO_PLAN.json from the experiment directory
  2. Scaffolds training code (if not already scaffolded)
  3. Installs Python dependencies in an isolated venv
  4. Runs the training script, capturing metrics to train_log.jsonl
  5. Updates TASK_SPEC.json pipeline status
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: str | None = None, timeout: int = 600,
         env: dict | None = None) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, timeout=timeout, env=env or os.environ.copy(),
    )
    return result.returncode, result.stdout, result.stderr


def _log(msg: str, log_path: Path | None = None) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if log_path:
        with open(log_path, "a") as f:
            f.write(line + "\n")


def _ensure_venv(code_dir: Path, log_path: Path) -> str:
    """Create venv in code_dir/.venv if absent. Return python executable path."""
    venv_dir = code_dir / ".venv"
    python_bin = venv_dir / "bin" / "python"
    pip_bin = venv_dir / "bin" / "pip"

    if not python_bin.exists():
        _log(f"Creating venv at {venv_dir}", log_path)
        rc, out, err = _run([sys.executable, "-m", "venv", str(venv_dir)])
        if rc != 0:
            _log(f"WARNING: venv creation failed: {err}", log_path)
            return sys.executable  # fall back to system Python

    # Install / upgrade requirements
    req_file = code_dir / "requirements.txt"
    if req_file.exists():
        _log("Installing requirements ...", log_path)
        rc, out, err = _run(
            [str(pip_bin), "install", "-q", "-r", str(req_file)],
            timeout=300,
        )
        if rc != 0:
            _log(f"WARNING: pip install failed:\n{err[-1000:]}", log_path)

    return str(python_bin)


def _scaffold_code(spec: dict[str, Any], code_dir: Path, log_path: Path) -> None:
    """Generate training + inference scripts if they don't exist."""
    train_py = code_dir / "train.py"
    if train_py.exists():
        _log(f"Code scaffold already exists at {code_dir}", log_path)
        return

    _log("Scaffolding training code ...", log_path)
    spec_path = code_dir.parent / "TASK_SPEC.json"
    if not spec_path.exists():
        spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    rc, out, err = _run(
        [sys.executable, "tools/csi_har_scaffold.py", str(spec_path), "--output-dir", str(code_dir)],
        cwd=str(Path(__file__).parents[2]),
    )
    if rc != 0:
        _log(f"WARNING: scaffold failed:\n{err[-1000:]}", log_path)
        return
    _log(f"Scaffold created: {train_py}", log_path)


def _apply_algo_plan(code_dir: Path, algo_plan: dict[str, Any], log_path: Path) -> None:
    """Patch train.py with hyperparameters from ALGO_PLAN.json if possible."""
    train_py = code_dir / "train.py"
    if not train_py.exists():
        return

    training_cfg = algo_plan.get("training", {})
    lr = training_cfg.get("lr", 1e-3)
    batch_size = training_cfg.get("batch_size", 32)
    epochs = training_cfg.get("epochs", 50)

    content = train_py.read_text(encoding="utf-8")
    original = content

    # Patch default argument values in the train() function signature
    import re
    content = re.sub(r"epochs:\s*int\s*=\s*\d+", f"epochs: int = {epochs}", content)
    content = re.sub(r"batch_size:\s*int\s*=\s*\d+", f"batch_size: int = {batch_size}", content)
    content = re.sub(r"lr:\s*float\s*=\s*[\d.e+-]+", f"lr: float = {lr}", content)

    if content != original:
        train_py.write_text(content, encoding="utf-8")
        _log(f"Patched train.py: epochs={epochs}, batch={batch_size}, lr={lr}", log_path)


def _run_training(
    python_bin: str,
    code_dir: Path,
    spec: dict[str, Any],
    log_path: Path,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Execute train.py and return parsed result."""
    dataset = spec.get("dataset") or "UT-HAR"
    data_dir = spec.get("data_dir") or f"data/{dataset}"
    checkpoint_dir = str(code_dir.parent)
    task_id = spec.get("task_id", "task_000")

    cmd = [
        python_bin, str(code_dir / "train.py"),
        "--data-dir", data_dir,
        "--checkpoint-dir", checkpoint_dir,
        "--device", spec.get("constraints", {}).get("device", "cpu"),
    ]

    _log(f"Starting training: {' '.join(cmd)}", log_path)
    t0 = time.time()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(code_dir)
    env["OMP_NUM_THREADS"] = "4"   # CPU thread limit
    env["MKL_NUM_THREADS"] = "4"

    try:
        process = subprocess.Popen(
            cmd, cwd=str(code_dir), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )

        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            lines.append(line)
            _log(f"  {line}", log_path)
            # Check timeout
            if time.time() - t0 > timeout:
                process.terminate()
                _log("Training timeout reached, terminating ...", log_path)
                break

        process.wait()
        rc = process.returncode

    except subprocess.TimeoutExpired:
        process.terminate()
        rc = -1
        lines = ["TIMEOUT"]

    elapsed = round(time.time() - t0, 1)

    # Parse result from result.json
    result_path = code_dir.parent / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {"error": "result.json not found", "returncode": rc}

    result.update({
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "task_id": task_id,
        "elapsed_s": elapsed,
        "returncode": rc,
        "stdout_tail": "\n".join(lines[-20:]),
    })
    return result


def run_algo_implement(
    task_spec_path: str,
    algo_plan_path: str | None = None,
    timeout: int = 3600,
    skip_install: bool = False,
) -> dict[str, Any]:
    """Main entry point for the algo-implement stage.

    Args:
        task_spec_path: Path to TASK_SPEC.json
        algo_plan_path: Path to ALGO_PLAN.json (default: same dir as task spec)
        timeout: Training timeout in seconds
        skip_install: Skip venv + pip install (for re-runs)

    Returns:
        Result dict with training metrics and status.
    """
    spec_path = Path(task_spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    task_id = spec.get("task_id", "task_000")

    exp_dir = spec_path.parent
    code_dir = exp_dir / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    log_path = exp_dir / "implement_log.txt"

    _log(f"=== Algo Implement Stage | task={task_id} ===", log_path)

    # Load algo plan
    plan_path = Path(algo_plan_path) if algo_plan_path else exp_dir / "ALGO_PLAN.json"
    algo_plan: dict[str, Any] = {}
    if plan_path.exists():
        algo_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        _log(f"Loaded ALGO_PLAN from {plan_path}", log_path)
    else:
        _log("ALGO_PLAN.json not found, using task spec defaults", log_path)

    # Scaffold code
    _scaffold_code(spec, code_dir, log_path)

    # Apply hyperparameters from plan
    if algo_plan:
        _apply_algo_plan(code_dir, algo_plan, log_path)

    # Environment setup
    if skip_install:
        python_bin = sys.executable
    else:
        python_bin = _ensure_venv(code_dir, log_path)

    # Run training
    result = _run_training(python_bin, code_dir, spec, log_path, timeout=timeout)

    # Save experiment record
    runs_log = exp_dir / "runs.jsonl"
    with open(runs_log, "a") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    # Update task spec status
    target_acc = spec.get("target_metrics", {}).get("accuracy", 0.85)
    test_acc = result.get("test_acc", 0.0)
    status = "completed" if result.get("returncode", -1) == 0 else "failed"
    decision = (
        f"Training {status}. test_acc={test_acc:.3f} "
        f"(target={target_acc:.2f}, met={result.get('target_met', False)}). "
        f"arch={result.get('arch', '?')}, elapsed={result.get('elapsed_s', 0)}s"
    )

    from stages._helpers import _safe_json_write  # noqa: F401 — optional

    # Update pipeline status in task spec
    spec["pipeline_status"]["algo_implement"] = status
    spec["agent_decisions"].append({
        "step": "algo_implement",
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "run_id": result.get("run_id", ""),
    })
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    _log(f"=== Result: {decision} ===", log_path)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Run algo-implement stage")
    ap.add_argument("task_spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--algo-plan", help="Path to ALGO_PLAN.json")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--skip-install", action="store_true")
    args = ap.parse_args()
    result = run_algo_implement(args.task_spec, args.algo_plan, args.timeout, args.skip_install)
    print("\nFinal result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
