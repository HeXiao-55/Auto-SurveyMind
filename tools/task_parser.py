"""Task Parser — convert natural language business requirement into structured TASK_SPEC.json.

Handles WiFi CSI HAR and generic ML task specifications.
Can be called standalone or imported by pipeline stages.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Keyword → structured field extractors
# ---------------------------------------------------------------------------

_DATASET_ALIASES: dict[str, str] = {
    "widar": "WIDAR3.0", "widar3": "WIDAR3.0", "widar 3": "WIDAR3.0",
    "ut-har": "UT-HAR", "ut har": "UT-HAR", "uthar": "UT-HAR",
    "ntu-fi": "NTU-Fi", "ntuffi": "NTU-Fi", "ntu fi": "NTU-Fi",
    "signfi": "SignFi", "sign fi": "SignFi",
    "falldefi": "FallDefi", "fall defi": "FallDefi",
    "wiar": "WiAR",
}

_DEVICE_PATTERNS = [
    (r"\bcpu[\s-]only\b|\bcpu\b", "cpu"),
    (r"\bgpu\b|\bcuda\b|\bnvidia\b", "gpu"),
    (r"\bmps\b|\bapple silicon\b|\bm[12]\b", "mps"),
]

_METRIC_PATTERNS = [
    (r"(\d+(?:\.\d+)?)\s*%\s*(?:accuracy|acc)", "accuracy"),
    (r"accuracy[^\d]*(\d+(?:\.\d+)?)\s*%?", "accuracy"),
    (r"f1[^\d]*(\d+(?:\.\d+)?)", "f1"),
    (r"(\d+(?:\.\d+)?)\s*ms\s*(?:inference|latency)", "inference_ms"),
]

_ACTIVITY_KEYWORDS: dict[str, list[str]] = {
    "basic_activities": ["sit", "stand", "walk", "run", "fall", "lie", "sleep"],
    "gestures":         ["wave", "push", "pull", "clap", "slide", "draw", "gesture"],
    "fine_grained":     ["bend", "jump", "punch", "kick", "rotate", "twist"],
}

_CSI_SIGNALS = ["csi", "channel state information", "wifi sensing", "wifi csi", "wi-fi"]


def _extract_device(text: str) -> str:
    text_l = text.lower()
    for pat, device in _DEVICE_PATTERNS:
        if re.search(pat, text_l):
            return device
    return "cpu"  # default safe for demo


def _extract_dataset(text: str) -> str | None:
    text_l = text.lower()
    for alias, canonical in _DATASET_ALIASES.items():
        if alias in text_l:
            return canonical
    return None


def _extract_target_metrics(text: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for pat, name in _METRIC_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1))
                if name == "accuracy" and val > 1.0:
                    val /= 100.0
                metrics[name] = val
            except (ValueError, IndexError):
                pass
    return metrics


def _extract_actions(text: str) -> list[str]:
    text_l = text.lower()
    found: list[str] = []
    for group, keywords in _ACTIVITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                found.append(kw)
    return list(dict.fromkeys(found))  # deduplicate while preserving order


def _detect_domain(text: str) -> str:
    text_l = text.lower()
    if any(s in text_l for s in _CSI_SIGNALS):
        return "wifi_csi_har"
    if any(s in text_l for s in ["activity", "gesture", "fall", "har"]):
        return "har_generic"
    if any(s in text_l for s in ["image", "vision", "detection", "classification"]):
        return "vision"
    return "generic_ml"


def _extract_num_classes(text: str, actions: list[str]) -> int | None:
    m = re.search(r"(\d+)\s*(?:class|categor|action|activit|gesture)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if actions:
        return len(actions)
    return None


def _extract_constraints(text: str, device: str) -> dict[str, Any]:
    constraints: dict[str, Any] = {"device": device}
    # Parameter budget
    m = re.search(r"(\d+(?:\.\d+)?)\s*[mM]\s*(?:param|parameter)", text)
    if m:
        constraints["max_params_M"] = float(m.group(1))
    # Inference latency
    m = re.search(r"(\d+)\s*ms", text)
    if m:
        constraints["max_inference_ms"] = int(m.group(1))
    # Real-time constraint
    if re.search(r"real.?time|realtime|online", text, re.IGNORECASE):
        constraints["real_time"] = True
    return constraints


# ---------------------------------------------------------------------------
# Main parsing function
# ---------------------------------------------------------------------------

def parse_task(description: str, output_dir: str | None = None) -> dict[str, Any]:
    """Parse a natural language task description into a structured TASK_SPEC.

    Args:
        description: Free-form business requirement text.
        output_dir: If given, write TASK_SPEC.json to this directory.

    Returns:
        Structured task specification dict.
    """
    domain = _detect_domain(description)
    device = _extract_device(description)
    dataset = _extract_dataset(description)
    target_metrics = _extract_target_metrics(description)
    actions = _extract_actions(description)
    num_classes = _extract_num_classes(description, actions)
    constraints = _extract_constraints(description, device)

    # Default metrics if not specified
    if not target_metrics:
        target_metrics = {"accuracy": 0.85}

    # Domain-specific defaults
    data_modality = "CSI matrix" if domain == "wifi_csi_har" else "unknown"
    domain_profile = "templates/domain_profiles/wifi_csi_har.json" if domain == "wifi_csi_har" else \
                     "templates/domain_profiles/general_profile.json"

    spec: dict[str, Any] = {
        "task_id": f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.now().isoformat(),
        "raw_description": description,
        "domain": domain,
        "data_modality": data_modality,
        "domain_profile": domain_profile,
        "dataset": dataset,
        "num_classes": num_classes,
        "actions": actions if actions else (["sit", "stand", "walk", "fall", "wave"] if domain == "wifi_csi_har" else []),
        "constraints": constraints,
        "target_metrics": target_metrics,
        "pipeline_status": {
            "task_parse": "completed",
            "algo_plan": "pending",
            "algo_implement": "pending",
            "reflect_improve": "pending",
            "model_deliver": "pending",
        },
        "agent_decisions": [
            {
                "step": "task_parse",
                "timestamp": datetime.now().isoformat(),
                "decision": f"Detected domain={domain}, device={device}, dataset={dataset}",
            }
        ],
    }

    if output_dir:
        out_path = Path(output_dir) / "TASK_SPEC.json"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"TASK_SPEC written to: {out_path}")

    return spec


def load_task_spec(path: str | Path) -> dict[str, Any]:
    """Load an existing TASK_SPEC.json."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def update_pipeline_state(spec_path: str | Path, stage: str, status: str, decision: str = "") -> None:
    """Update pipeline status in an existing TASK_SPEC.json."""
    path = Path(spec_path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["pipeline_status"][stage] = status
    if decision:
        spec["agent_decisions"].append({
            "step": stage,
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
        })
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Parse natural language task description → TASK_SPEC.json")
    ap.add_argument("description", nargs="?", help="Task description text (or use --file)")
    ap.add_argument("--file", help="Read description from text file")
    ap.add_argument("--output-dir", default=".", help="Directory to write TASK_SPEC.json (default: .)")
    ap.add_argument("--print", action="store_true", help="Print parsed spec to stdout")
    args = ap.parse_args()

    if args.file:
        desc = Path(args.file).read_text(encoding="utf-8")
    elif args.description:
        desc = args.description
    else:
        print("ERROR: provide a description or --file", file=sys.stderr)
        sys.exit(1)

    spec = parse_task(desc, output_dir=args.output_dir)

    if args.print or not args.output_dir:
        print(json.dumps(spec, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
