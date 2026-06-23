"""Reflect-Improve stage — run reflection engine, apply patches, retrain.

Orchestrates the reflection loop:
  1. Run reflect_engine to get diagnostics and patches
  2. Apply recommended patches to code
  3. Re-run training
  4. Compare with previous best and decide whether to continue
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def run_reflect_improve(
    task_spec_path: str,
    max_iterations: int = 3,
    auto_patch: bool = True,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run the full reflect-and-improve loop.

    Args:
        task_spec_path: Path to TASK_SPEC.json
        max_iterations: Maximum reflection-retrain cycles
        auto_patch: Automatically apply code patches
        timeout: Per-run training timeout

    Returns:
        Final result dict after all iterations.
    """
    sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
    from reflect_engine import reflect  # noqa: PLC0415
    from stages.algo_implement import run_algo_implement  # noqa: PLC0415

    spec_path = Path(task_spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    target_acc = spec.get("target_metrics", {}).get("accuracy", 0.85)

    print(f"=== Reflect-Improve Loop | target={target_acc:.2%} ===")

    best_test_acc = 0.0
    final_result: dict[str, Any] = {}

    for iteration in range(1, max_iterations + 1):
        print(f"\n--- Iteration {iteration}/{max_iterations} ---")

        # Step 1: Reflect
        report = reflect(task_spec_path, auto_patch=auto_patch, max_iterations=max_iterations)
        print(f"Diagnosis: {[d['type'] for d in report.get('diagnoses', [])]}")
        print(f"Recommendation: {report.get('recommendation', '')}")

        if report.get("target_met"):
            print("Target already met. Skipping retraining.")
            break

        if "MAX ITERATIONS" in report.get("recommendation", ""):
            print("Max iterations reached by reflect_engine.")
            break

        # Step 2: Apply patches (already done inside reflect if auto_patch=True)
        if report.get("applied_patches"):
            print(f"Applied patches: {len(report['applied_patches'])}")
            for p in report["applied_patches"]:
                print(f"  {p}")

        # Step 3: Retrain with skip_install (venv already set up)
        print(f"\nRetraining (iteration {iteration}) ...")
        result = run_algo_implement(
            task_spec_path,
            timeout=timeout,
            skip_install=True,  # reuse existing venv
        )

        test_acc = result.get("test_acc", 0.0)
        print(f"Iteration {iteration} result: test_acc={test_acc:.3f}")

        if test_acc > best_test_acc:
            best_test_acc = test_acc
            final_result = result

        if result.get("target_met"):
            print(f"Target {target_acc:.2%} met at iteration {iteration}!")
            break

        # Step 4: Check convergence — if no improvement from previous iteration, stop
        if iteration > 1 and test_acc < best_test_acc - 0.005:
            print("Accuracy regressed. Stopping reflect loop.")
            break

    # Mark reflect_improve as completed in task spec
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    final_status = "completed" if final_result.get("target_met") else "partial"
    spec["pipeline_status"]["reflect_improve"] = final_status
    spec["agent_decisions"].append({
        "step": "reflect_improve",
        "timestamp": datetime.now().isoformat(),
        "decision": (
            f"Completed {iteration} iteration(s). "
            f"best_test_acc={best_test_acc:.3f}, target={target_acc:.2f}, "
            f"status={final_status}"
        ),
    })
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    summary = {
        "iterations": iteration,
        "best_test_acc": best_test_acc,
        "target_acc": target_acc,
        "target_met": best_test_acc >= target_acc,
        "final_result": final_result,
    }

    summary_path = spec_path.parent / "reflect_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"\nReflect-Improve summary: {summary_path}")
    print(json.dumps({k: v for k, v in summary.items() if k != "final_result"}, indent=2))
    return summary


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Run reflect-improve loop")
    ap.add_argument("task_spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--max-iterations", type=int, default=3)
    ap.add_argument("--no-auto-patch", action="store_true")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()
    run_reflect_improve(
        args.task_spec,
        max_iterations=args.max_iterations,
        auto_patch=not args.no_auto_patch,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
