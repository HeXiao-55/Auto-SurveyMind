"""SurveyMind Algorithm R&D Dashboard (Gradio-based).

Provides a web UI for:
  - System configuration (task description input, constraints)
  - Agent decision tracking (pipeline status, per-stage decisions)
  - Experiment results visualization (accuracy curves, comparison table)
  - Model delivery download

Launch: python mcp-servers/dashboard/server.py [--experiments-dir experiments]
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr


# ---------------------------------------------------------------------------
# Data loading utilities
# ---------------------------------------------------------------------------

EXPERIMENTS_DIR = Path(os.environ.get("EXPERIMENTS_DIR", "experiments"))


def _list_experiments() -> list[str]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted(
        [d.name for d in EXPERIMENTS_DIR.iterdir() if d.is_dir() and (d / "TASK_SPEC.json").exists()],
        reverse=True,
    )


def _load_json(path: Path) -> dict | None:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _load_experiment(task_id: str) -> dict[str, Any]:
    exp_dir = EXPERIMENTS_DIR / task_id
    spec  = _load_json(exp_dir / "TASK_SPEC.json") or {}
    result = _load_json(exp_dir / "result.json") or {}
    plan  = _load_json(exp_dir / "ALGO_PLAN.json") or {}
    reflect = _load_json(exp_dir / "REFLECT_REPORT.json") or {}
    manifest = _load_json(exp_dir / "delivery" / "delivery_manifest.json") or {}
    # Load training log
    log_path = exp_dir / "train_log.jsonl"
    log = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    log.append(json.loads(line))
                except Exception:
                    pass
    return dict(spec=spec, result=result, plan=plan, reflect=reflect, manifest=manifest, log=log)


# ---------------------------------------------------------------------------
# Tab 1 — Configuration & Task Parser
# ---------------------------------------------------------------------------

def run_task_parser(description: str, device: str, target_acc: float, dataset: str) -> tuple[str, str]:
    """Call task_parser.py and return TASK_SPEC content + status."""
    import subprocess
    import tempfile

    # Augment description with constraints
    full_desc = description
    if device == "CPU":
        full_desc += " CPU only."
    if dataset != "Auto-detect":
        full_desc += f" Dataset: {dataset}."
    if target_acc > 0:
        full_desc += f" Target accuracy: {target_acc:.0%}."

    # Create temp dir
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = EXPERIMENTS_DIR / f"task_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).parents[2]
    result = subprocess.run(
        [sys.executable, "tools/task_parser.py", full_desc, "--output-dir", str(out_dir), "--print"],
        cwd=str(repo_root), capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0:
        return f"Error: {result.stderr}", "❌ Parser failed"

    # Find the JSON output
    lines = result.stdout.splitlines()
    json_start = next((i for i, l in enumerate(lines) if l.strip().startswith("{")), None)
    if json_start is not None:
        spec_json = "\n".join(lines[json_start:])
    else:
        spec_json = result.stdout

    spec_file = out_dir / "TASK_SPEC.json"
    status = f"✅ TASK_SPEC.json created: {spec_file}"
    return spec_json, status


# ---------------------------------------------------------------------------
# Tab 2 — Pipeline Status
# ---------------------------------------------------------------------------

def get_pipeline_status(task_id: str) -> tuple[str, str, str]:
    """Return (status_table_html, decisions_log, metadata)."""
    if not task_id:
        return "No experiment selected", "", ""

    data = _load_experiment(task_id)
    spec = data["spec"]
    result = data["result"]

    if not spec:
        return f"Experiment '{task_id}' not found or missing TASK_SPEC.json", "", ""

    pipeline = spec.get("pipeline_status", {})
    status_icons = {"completed": "✅", "in_progress": "🔄", "failed": "❌", "pending": "⏳"}

    rows = []
    for stage, status in pipeline.items():
        icon = status_icons.get(status, "❓")
        rows.append(f"| {icon} | {stage} | {status} |")

    table = "| Status | Stage | State |\n|--------|-------|-------|\n" + "\n".join(rows)

    # Agent decisions
    decisions = spec.get("agent_decisions", [])
    dec_lines = []
    for d in reversed(decisions[-20:]):
        ts = d.get("timestamp", "")[:19]
        step = d.get("step", "?")
        decision = d.get("decision", "")
        dec_lines.append(f"**[{ts}] {step}**\n{decision}\n")
    decisions_log = "\n---\n".join(dec_lines) if dec_lines else "No decisions recorded yet."

    # Metadata
    test_acc = result.get("test_acc", 0)
    target = spec.get("target_metrics", {}).get("accuracy", 0.85)
    meta = (
        f"**Task**: {spec.get('task_id', '?')}\n"
        f"**Domain**: {spec.get('domain', '?')}\n"
        f"**Dataset**: {spec.get('dataset', '?')}\n"
        f"**Device**: {spec.get('constraints', {}).get('device', '?')}\n"
        f"**Target Acc**: {target:.0%}\n"
        f"**Test Acc**: {test_acc:.1%}\n"
        f"**Target Met**: {'✅' if test_acc >= target else '❌'}"
    )

    return table, decisions_log, meta


# ---------------------------------------------------------------------------
# Tab 3 — Training Curves
# ---------------------------------------------------------------------------

def get_training_plot(task_id: str):
    """Return a Gradio-compatible plot of training history."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    if not task_id:
        return None

    data = _load_experiment(task_id)
    log = data["log"]

    if not log:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No training log found", ha="center", va="center")
        return fig

    epochs = [r.get("epoch", i + 1) for i, r in enumerate(log)]
    train_accs = [r.get("train_acc", 0) for r in log]
    val_accs   = [r.get("val_acc", 0)   for r in log]
    train_loss = [r.get("train_loss", 0) for r in log]
    val_loss   = [r.get("val_loss", 0)   for r in log]

    spec = data["spec"]
    target = spec.get("target_metrics", {}).get("accuracy", 0.85)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Accuracy
    ax1.plot(epochs, train_accs, label="Train Acc", color="#2196F3")
    ax1.plot(epochs, val_accs,   label="Val Acc",   color="#4CAF50")
    ax1.axhline(target, color="#F44336", linestyle="--", label=f"Target {target:.0%}")
    ax1.set_title("Accuracy")
    ax1.set_xlabel("Epoch"); ax1.set_ylabel("Accuracy")
    ax1.legend(); ax1.grid(alpha=0.3)
    ax1.set_ylim(0, 1)

    # Loss
    ax2.plot(epochs, train_loss, label="Train Loss", color="#2196F3")
    ax2.plot(epochs, val_loss,   label="Val Loss",   color="#4CAF50")
    ax2.set_title("Loss")
    ax2.set_xlabel("Epoch"); ax2.set_ylabel("Loss")
    ax2.legend(); ax2.grid(alpha=0.3)

    plt.suptitle(f"Training History: {task_id}", fontsize=12)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Tab 4 — Experiment Comparison
# ---------------------------------------------------------------------------

def get_comparison_table() -> list[list]:
    """Return list of rows for comparison table."""
    rows = []
    for task_id in _list_experiments():
        data = _load_experiment(task_id)
        spec = data["spec"]
        result = data["result"]
        if not spec:
            continue
        test_acc = result.get("test_acc", 0)
        target   = spec.get("target_metrics", {}).get("accuracy", 0.85)
        rows.append([
            task_id,
            spec.get("dataset", "?"),
            spec.get("constraints", {}).get("device", "?"),
            result.get("arch", "?"),
            f"{result.get('best_val_acc', 0):.1%}",
            f"{test_acc:.1%}",
            f"{target:.0%}",
            "✅" if test_acc >= target else "❌",
            spec.get("pipeline_status", {}).get("model_deliver", "pending"),
        ])
    return rows


# ---------------------------------------------------------------------------
# Tab 5 — Quick Actions (CLI triggers)
# ---------------------------------------------------------------------------

def run_pipeline_step(task_spec_path: str, step: str) -> str:
    """Trigger a pipeline step via CLI and return output."""
    import subprocess
    repo_root = Path(__file__).parents[2]
    cmd_map = {
        "algo-plan": [sys.executable, "tools/csi_har_scaffold.py", task_spec_path],
        "algo-implement": [sys.executable, "tools/stages/algo_implement.py", task_spec_path],
        "reflect-improve": [sys.executable, "tools/stages/reflect_improve.py", task_spec_path],
        "model-deliver": [sys.executable, "tools/stages/model_deliver.py", task_spec_path],
    }
    cmd = cmd_map.get(step)
    if not cmd:
        return f"Unknown step: {step}"

    try:
        result = subprocess.run(
            cmd, cwd=str(repo_root), capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + ("\n--- STDERR ---\n" + result.stderr if result.stderr else "")
        return output[:5000]
    except subprocess.TimeoutExpired:
        return "Command is running (timeout in 30s). Check experiment directory for progress."
    except Exception as e:
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Gradio App
# ---------------------------------------------------------------------------

def build_app() -> gr.Blocks:
    with gr.Blocks(
        title="SurveyMind — Algorithm R&D Dashboard",
        theme=gr.themes.Soft(),
        css=".gradio-container { max-width: 1200px; margin: auto; }",
    ) as app:

        gr.Markdown("""
# 🔬 SurveyMind Algorithm R&D Dashboard
**Automated algorithm self-evolution pipeline for WiFi CSI HAR**
---
""")

        with gr.Tab("⚙️ Configuration"):
            gr.Markdown("### Parse a new task description into a structured TASK_SPEC")

            with gr.Row():
                with gr.Column(scale=2):
                    task_desc = gr.Textbox(
                        label="Task Description (natural language)",
                        placeholder="E.g.: 我需要一个WiFi CSI人体行为识别系统，识别坐、站、走、摔倒、挥手五个动作，要求在CPU上运行，准确率85%以上，使用UT-HAR数据集。",
                        lines=4,
                    )
                    with gr.Row():
                        device_choice = gr.Radio(["CPU", "GPU"], value="CPU", label="Device")
                        target_acc_slider = gr.Slider(0.5, 1.0, value=0.85, step=0.05, label="Target Accuracy")
                    dataset_choice = gr.Dropdown(
                        ["Auto-detect", "UT-HAR", "NTU-Fi", "WIDAR3.0", "SignFi", "Custom"],
                        value="Auto-detect", label="Dataset"
                    )
                    parse_btn = gr.Button("🚀 Parse Task", variant="primary")

                with gr.Column(scale=2):
                    spec_output = gr.Code(label="TASK_SPEC.json", language="json", lines=20)
                    parse_status = gr.Textbox(label="Status", lines=1)

            parse_btn.click(
                run_task_parser,
                inputs=[task_desc, device_choice, target_acc_slider, dataset_choice],
                outputs=[spec_output, parse_status],
            )

        with gr.Tab("📊 Pipeline Status"):
            gr.Markdown("### Agent decision tracking and pipeline state")

            with gr.Row():
                exp_selector = gr.Dropdown(
                    choices=_list_experiments(),
                    label="Select Experiment",
                    interactive=True,
                )
                refresh_btn = gr.Button("🔄 Refresh", scale=0)

            with gr.Row():
                with gr.Column():
                    pipeline_table = gr.Markdown(label="Pipeline Stages")
                with gr.Column():
                    meta_box = gr.Markdown(label="Experiment Info")

            decisions_log = gr.Markdown(label="Agent Decisions")

            def refresh_experiments():
                return gr.Dropdown(choices=_list_experiments())

            refresh_btn.click(refresh_experiments, outputs=[exp_selector])
            exp_selector.change(
                get_pipeline_status,
                inputs=[exp_selector],
                outputs=[pipeline_table, decisions_log, meta_box],
            )

        with gr.Tab("📈 Training Curves"):
            gr.Markdown("### Training accuracy and loss curves")

            with gr.Row():
                curve_exp_selector = gr.Dropdown(
                    choices=_list_experiments(),
                    label="Select Experiment",
                    interactive=True,
                )
                curve_refresh_btn = gr.Button("🔄 Refresh", scale=0)

            plot_output = gr.Plot(label="Training History")

            curve_refresh_btn.click(
                lambda: gr.Dropdown(choices=_list_experiments()),
                outputs=[curve_exp_selector],
            )
            curve_exp_selector.change(
                get_training_plot,
                inputs=[curve_exp_selector],
                outputs=[plot_output],
            )

        with gr.Tab("🏆 Experiment Comparison"):
            gr.Markdown("### Compare all experiments")

            cmp_refresh_btn = gr.Button("🔄 Refresh Table", variant="secondary")
            comparison_table = gr.Dataframe(
                headers=["Task ID", "Dataset", "Device", "Arch", "Val Acc", "Test Acc", "Target", "Met?", "Deliver"],
                datatype=["str"] * 9,
                value=get_comparison_table(),
                interactive=False,
                label="Experiment Comparison",
            )
            cmp_refresh_btn.click(get_comparison_table, outputs=[comparison_table])

        with gr.Tab("⚡ Quick Actions"):
            gr.Markdown("### Trigger pipeline steps (runs in background, check log files for progress)")

            with gr.Row():
                action_spec = gr.Textbox(label="TASK_SPEC.json path", placeholder="experiments/task_xxx/TASK_SPEC.json")
                action_step = gr.Dropdown(
                    ["algo-plan", "algo-implement", "reflect-improve", "model-deliver"],
                    label="Pipeline Step",
                )
            action_btn = gr.Button("▶ Run Step", variant="primary")
            action_output = gr.Textbox(label="Output (first 5000 chars)", lines=15)

            action_btn.click(
                run_pipeline_step,
                inputs=[action_spec, action_step],
                outputs=[action_output],
            )

        with gr.Tab("📚 Help"):
            gr.Markdown("""
## Pipeline Overview

```
NL Description
     │
     ▼
task-parser ──► TASK_SPEC.json
     │
     ▼
algo-plan ──► ALGO_PLAN.json + code scaffold
     │
     ▼
algo-implement ──► training + best_model.pt
     │
     ▼
reflect-improve ──► diagnosis + patches + retrain loop
     │
     ▼
model-deliver ──► ONNX + inference API + MODEL_CARD.md
```

## CLI Quick Reference

```bash
# Parse task
python3 tools/task_parser.py "WiFi CSI HAR, CPU, 85% accuracy" --output-dir experiments/

# Run full pipeline
python3 tools/stages/algo_implement.py experiments/task_xxx/TASK_SPEC.json
python3 tools/stages/reflect_improve.py experiments/task_xxx/TASK_SPEC.json
python3 tools/stages/model_deliver.py experiments/task_xxx/TASK_SPEC.json

# Agent skills (in Cursor)
/task-parser "..."
/algo-plan "experiments/task_xxx/TASK_SPEC.json"
/algo-implement "experiments/task_xxx/TASK_SPEC.json"
/reflect-improve "experiments/task_xxx/TASK_SPEC.json"
/model-deliver "experiments/task_xxx/TASK_SPEC.json"
/algo-pipeline "..." (full auto)
```

## Key Files

| File | Description |
|------|-------------|
| `TASK_SPEC.json` | Task specification + pipeline status |
| `ALGO_PLAN.json` | Preprocessing + model architecture plan |
| `train_log.jsonl` | Per-epoch training metrics |
| `result.json` | Final training result |
| `runs.jsonl` | All training runs history |
| `REFLECT_REPORT.json` | Reflection diagnoses + patches |
| `delivery/` | Deployment bundle |
""")

    return app


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="SurveyMind Dashboard")
    ap.add_argument("--experiments-dir", default="experiments", help="Experiments directory")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--share", action="store_true", help="Create Gradio public URL")
    args = ap.parse_args()

    global EXPERIMENTS_DIR
    EXPERIMENTS_DIR = Path(args.experiments_dir)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Dashboard starting at http://{args.host}:{args.port}")
    print(f"Experiments dir: {EXPERIMENTS_DIR.resolve()}")

    app = build_app()
    app.launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
