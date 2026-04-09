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
├── skills/                 # Skill definitions and pipelines
├── tools/                  # CLI tools and orchestrators
├── templates/              # Templates and domain profiles
├── validation/             # Validation rules and runner
├── tests/                  # pytest suite
├── surveys/                # Per-survey outputs
├── .mcp.example.json       # MCP server configuration template
├── .env.example            # Environment variable template
├── Makefile
├── README.md
└── README_CN.md
```

## MCP and Integrations

SurveyMind supports MCP-based integrations. Start from:

- `.mcp.example.json`
- `mcp-servers/`
- `tools/mcp_base.py` for implementing new MCP server adapters

## Troubleshooting

- **Skill not found:** run `./install.sh` again
- **No papers found:** broaden topic keywords and retry `arxiv-discover`
- **Download timeout:** reduce scope first (`--literature-scope focused`)
- **Trace init missing LaTeX:** pass `--survey-tex` or use `--trace-init-missing-policy skip`

## License

MIT License — see [LICENSE](LICENSE).
