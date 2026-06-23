"""Model Deliver stage — package and validate trained model for deployment."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def run_model_deliver(task_spec_path: str, skip_onnx: bool = False) -> dict[str, Any]:
    """Run model packaging and delivery stage.

    Args:
        task_spec_path: Path to TASK_SPEC.json
        skip_onnx: Skip ONNX export

    Returns:
        Delivery manifest.
    """
    sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))
    from model_packager import package_model  # noqa: PLC0415

    print(f"=== Model Deliver Stage | spec={task_spec_path} ===")
    manifest = package_model(task_spec_path, skip_onnx=skip_onnx)

    if manifest.get("status", {}).get("onnx") == "error":
        print("WARNING: ONNX export failed. Delivery bundle still created without ONNX.")
        print("To retry ONNX: python3 tools/model_packager.py", task_spec_path)

    return manifest


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Run model-deliver stage")
    ap.add_argument("task_spec", help="Path to TASK_SPEC.json")
    ap.add_argument("--skip-onnx", action="store_true")
    args = ap.parse_args()
    manifest = run_model_deliver(args.task_spec, skip_onnx=args.skip_onnx)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
