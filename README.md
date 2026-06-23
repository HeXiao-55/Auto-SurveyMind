# SurveyMind: Automated Research Survey Agent

> End-to-end survey construction for research topics, from fuzzy scope to structured draft.

[English](README.md) | [简体中文](README_CN.md)

## What This Project Does

SurveyMind provides two complementary ways to run the survey workflow:

- **Skill pipeline (agentic):** run stage-by-stage reasoning with skills like `/survey-brainstorm`, `/research-lit`, `/paper-analysis`, `/taxonomy-build`, `/gap-identify`, `/survey-write`
- **CLI pipeline (scriptable):** run deterministic stages with `tools/surveymind_run.py` for automation, CI, and reproducibility

Outputs are isolated per survey under:

`surveys/survey_<topic_slug>/`

With gate directories:

- `gate0_scope`
- `gate1_research_lit`
- `gate2_paper_analysis`
- `gate3_taxonomy`
- `gate4_gap_analysis`
- `gate5_survey_write`
- `gate6_code_discovery`
- `gate7_reproduction`

## Quick Start

### 1) Install

```bash
cp .env.example .env
make install
./install.sh
```

### 2) Skill Workflow (recommended for first run)

```bash
claude
> /survey-brainstorm "your fuzzy topic"
> /survey-pipeline "your refined topic"
```

### 3) CLI Workflow

```bash
python3 tools/surveymind_run.py --stage brainstorm \
  --scope-topic "your topic description" \
  --survey-name "your_survey_name" \
  --topic-keywords "keyword1,keyword2,keyword3"

python3 tools/surveymind_run.py --stage all \
  --survey-name "your_survey_name" \
  --topic-keywords "keyword1,keyword2,keyword3"
```

## CLI Stages (`tools/surveymind_run.py`)

Current supported stages:

- `brainstorm`
- `arxiv-discover`
- `corpus-extract`
- `paper-download`
- `paper-analysis`
- `batch-triage`
- `taxonomy-build`
- `gap-identify`
- `survey-write`
- `trace-init`
- `trace-sync`
- `taxonomy-alloc`
- `validate`
- `validate-and-improve`
- `code-discover`
- `repo-setup`
- `repo-reproduce`
- `reproduce-all`
- `all`

`--stage all` runs this order by default:

1. `brainstorm`
2. `arxiv-discover` (can be disabled via `--no-discover-arxiv`)
3. `corpus-extract`
4. `batch-triage`
5. `paper-download`
6. `paper-analysis`
7. `taxonomy-build`
8. `gap-identify`
9. `survey-write`
10. `trace-init`
11. `taxonomy-alloc`
12. `trace-sync`
13. `validate-and-improve`

## Algorithm R&D Pipeline

End-to-end automated algorithm development for ML tasks (WiFi CSI HAR focus, CPU-only):

```bash
# Option A: Full automated pipeline via agent skill
claude
> /algo-pipeline "WiFi CSI人体行为识别，识别坐站走摔倒挥手，CPU，准确率85%以上，UT-HAR数据集"

# Option B: Step-by-step via CLI

# 1. Parse NL description → TASK_SPEC.json
python3 tools/task_parser.py "WiFi CSI HAR, 5 activities, CPU, 85% accuracy" \
    --output-dir experiments/

# 2. Generate code scaffold from TASK_SPEC
python3 tools/csi_har_scaffold.py experiments/task_xxx/TASK_SPEC.json

# 3. Train model (installs venv + runs training)
python3 tools/stages/algo_implement.py experiments/task_xxx/TASK_SPEC.json

# 4. Diagnose issues and retrain in a loop
python3 tools/stages/reflect_improve.py experiments/task_xxx/TASK_SPEC.json \
    --max-iterations 3

# 5. Package for delivery (ONNX + inference API + model card)
python3 tools/stages/model_deliver.py experiments/task_xxx/TASK_SPEC.json
```

Start the Dashboard:
```bash
pip install gradio matplotlib
python3 mcp-servers/dashboard/server.py --experiments-dir experiments
# Open: http://localhost:7860
```

Experiment outputs are saved under: `experiments/task_<id>/`

## Reproduction Pipeline

After completing a survey, use the reproduction pipeline to find and run code implementations:

```bash
# Discover GitHub repos for survey papers
python3 tools/surveymind_run.py --stage code-discover \
    --survey-name "your_survey_name"

# Clone repos and generate setup plans
python3 tools/surveymind_run.py --stage repo-setup \
    --survey-name "your_survey_name"

# Execute demos and validate
python3 tools/surveymind_run.py --stage repo-reproduce \
    --survey-name "your_survey_name"

# Or run all reproduction stages at once
python3 tools/surveymind_run.py --stage reproduce-all \
    --survey-name "your_survey_name" \
    --reproduction-max-repos 5
```

Skill workflow (agentic):
```bash
claude
> /reproduce-pipeline "your_survey_name"
```

## Common Commands

```bash
# Full test and quality checks
make test
make lint
make format

# arXiv connectivity smoke test
make check-arxiv

# Validation only
python3 validation/run_validation.py --scope all --strict --retry 2
```

Tier scope control examples:

```bash
# Download Tier1+Tier2 PDFs (default behavior)
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name "your_survey_name" \
  --download-tier-scope tier1_tier2

# Analyze Tier3+Tier4 on demand
python3 tools/surveymind_run.py --stage paper-analysis \
  --survey-name "your_survey_name" \
  --analysis-tier-scope tier3_tier4 \
  --analysis-mode deep+coverage
```

## Key Files and Directories

```text
SurveyMind/
├── skills/                         # Skill definitions and pipelines
│   ├── survey-pipeline/            # Survey skills (existing)
│   ├── reproduce-pipeline/         # Reproduction skills
│   ├── task-parser/                # NL → TASK_SPEC (NEW)
│   ├── algo-plan/                  # Algorithm planning (NEW)
│   ├── algo-implement/             # Code generation + training (NEW)
│   ├── reflect-improve/            # Reflection + patch loop (NEW)
│   ├── model-deliver/              # Model packaging (NEW)
│   └── algo-pipeline/             # End-to-end orchestrator (NEW)
├── tools/                          # CLI tools and orchestrators
│   ├── surveymind_run.py           # Main CLI
│   ├── task_parser.py              # NL task parser (NEW)
│   ├── csi_har_scaffold.py         # Code generator for CSI-HAR (NEW)
│   ├── reflect_engine.py           # Training diagnosis engine (NEW)
│   ├── model_packager.py           # ONNX + API generator (NEW)
│   └── stages/
│       ├── algo_implement.py       # Training stage (NEW)
│       ├── reflect_improve.py      # Reflect-retrain stage (NEW)
│       └── model_deliver.py        # Delivery stage (NEW)
├── templates/
│   └── domain_profiles/
│       └── wifi_csi_har.json       # WiFi CSI HAR domain profile (NEW)
├── mcp-servers/
│   ├── deepxiv/                    # DeepXiv MCP server
│   └── dashboard/                  # Gradio dashboard (NEW)
│       ├── server.py
│       └── requirements.txt
├── experiments/                    # Algorithm R&D outputs (created at runtime)
├── surveys/                        # Per-survey outputs
├── .mcp.example.json               # MCP server configuration template
├── .env.example                    # Environment variable template
├── Makefile
├── README.md
└── README_CN.md
```

## MCP and Integrations

SurveyMind supports MCP-based integrations. Start from:

- `.mcp.example.json`
- `mcp-servers/`
- `tools/mcp_base.py` for implementing new MCP server adapters

Optional DeepXiv MCP bridge is available at:

- `mcp-servers/deepxiv/server.py`
- `mcp-servers/deepxiv/README.md`

## Troubleshooting

**Survey Pipeline**
- **Skill not found:** run `./install.sh` again
- **No papers found:** broaden topic keywords and retry `arxiv-discover`
- **Download timeout:** reduce scope first (`--literature-scope focused`)
- **Trace init missing LaTeX:** pass `--survey-tex` or use `--trace-init-missing-policy skip`

**Algorithm R&D Pipeline**
- **Data not found:** check `data_dir` in TASK_SPEC.json; download dataset first
- **Training stuck:** check `experiments/<task_id>/implement_log.txt`
- **ONNX export failed:** run `python3 tools/model_packager.py --skip-onnx`
- **Dashboard not starting:** install `pip install gradio matplotlib`
- **Low accuracy after reflection:** check `REFLECT_REPORT.json` for diagnosis details

## License

MIT License — see [LICENSE](LICENSE).
