# SurveyMind: Automated Research Survey Agent

> An autonomous AI agent framework for conducting comprehensive literature surveys in any research subfield. From fuzzy idea to structured survey report — fully automated.

---

## Two Entry Points

SurveyMind supports two parallel workflows:

| Entry Point | Command | Best For |
|-------------|---------|----------|
| **Skill (agentic)** | `/survey-pipeline "{TOPIC}"` | Full autonomous pipeline with LLM-powered reasoning at each stage |
| **CLI (scriptable)** | `python3 tools/surveymind_run.py --stage all` | Reproducible batch execution, CI/CD integration |

Both produce the same outputs. The skill-based pipeline invokes LLM reasoning between stages; the CLI runs tools directly.

## Output Layout (Default)

All generated artifacts are stored under a survey-specific root:

`surveys/survey_<topic_slug>/`

With gate-based subfolders:

- `gate0_scope`
- `gate1_research_lit`
- `gate2_paper_analysis`
- `gate3_taxonomy`
- `gate4_gap_analysis`
- `gate5_survey_write`

---

## Complete Pipeline Flow

```
Stage 0 (Skill) ─────────────────────────────────────────────────────────────
  /survey-brainstorm "fuzzy idea"
        │
        │  tools/arxiv_fetch.py search ──▶ field landscape exploration
        │  WebSearch ──▶ recent trends & existing surveys
        │
        ▼
  SURVEY_SCOPE.md  (refined topic + keywords + section outline)

Stage 1 ──────────────────────────────────────────────────────────────────────
  /research-lit "refined subfield"   [Skill]
        │
        │  tools/arxiv_fetch.py search ──▶ arXiv paper list
        │  WebSearch / Semantic Scholar ──▶ additional references
        │  MCP: Zotero / Obsidian ──▶ local library integration
        │
        ▼
  gate1_research_lit/paper_list.json  (machine-readable paper inventory)
  gate1_research_lit/papers/*.pdf     (downloaded PDFs, optional)

Stage 2 ──────────────────────────────────────────────────────────────────────
  /paper-analysis "topic"   [Skill]
        │
        │  LLM reads each paper PDF
        │  Extracts 8-dim / 12-field classification + evidence snippets
        │
        ▼
  gate2_paper_analysis/*_analysis.md  (per-paper structured analysis)

  ── OR, for bulk API-level coverage check ──
  python3 tools/surveymind_run.py --stage paper-analysis   [CLI]
        │
        │  tools/batch_paper_triage.py  (12-field via arXiv API, no deep PDF)
        │
        ▼
  gate2_paper_analysis/all_papers_triage.json  (12-field triage for all papers in gate1 paper_list.json)

Stage 3 ──────────────────────────────────────────────────────────────────────
  /taxonomy-build "topic"   [Skill]
        │
        │  Reads gate2_paper_analysis/*.md
        │  Groups by method category, bit-width, training paradigm
        │
        ▼
  gate3_taxonomy/taxonomy.md  (hierarchical classification structure)

Stage 4 ──────────────────────────────────────────────────────────────────────
  /gap-identify "topic"   [Skill]
        │
        │  Reads gate3_taxonomy/taxonomy.md
        │  Identifies: unexplored combinations, benchmark gaps, method gaps
        │
        ▼
  gate4_gap_analysis/gap_analysis.md  (research gaps ranked by severity + confidence)

Stage 5 ──────────────────────────────────────────────────────────────────────
  /survey-write "topic"   [Skill]
        │
        │  Reads gate3_taxonomy/taxonomy.md + gate4_gap_analysis/gap_analysis.md
        │  Synthesizes into academic survey structure
        │
        ▼
  gate5_survey_write/SURVEY_DRAFT.md  (publication-ready survey document)

Stage 6 ──────────────────────────────────────────────────────────────────────
  python3 tools/surveymind_run.py --stage corpus-extract   [CLI]
        │
        │  tools/arxiv_json_extractor.py
        │  Parses arXiv JSON (e.g. arxiv_results.json) ──▶ corpus_report.md
        │  Tier classification: Tier 1 (core), Tier 2 (high), Tier 3 (related), Tier 4 (peripheral)
        │
        ▼
  corpus_report.md  (tiered corpus overview)

Stage 7 (Full CLI Orchestration) ──────────────────────────────────────────
  python3 tools/surveymind_run.py --stage all   [CLI orchestrator]
        │
        ├──> brainstorm        ──▶ tools/surveymind_run.py (in-process) ──▶ gate0_scope/SURVEY_SCOPE.md
  ├──> arxiv-discover    ──▶ tools/arxiv_discover.py ──▶ gate1_research_lit/arxiv_results.json
        ├──> corpus-extract     ──▶ tools/arxiv_json_extractor.py ──▶ gate1_research_lit/corpus_report.md
        ├──> batch-triage      ──▶ tools/batch_paper_triage.py ──▶ gate2_paper_analysis/all_papers_triage.json
        ├──> paper-analysis    ──▶ coverage check vs gate1_research_lit/paper_list.json
        ├──> trace-init       ──▶ tools/survey_trace_init.py ──▶ survey_trace/ directory tree
        ├──> convert-12field  ──▶ tools/convert_to_12field.py ──▶ upgraded 12-field analyses
        ├──> trace-sync       ──▶ tools/survey_trace_sync.py ──▶ survey_trace/**/SUBSECTION_RECORD.md
        └──> validate          ──▶ validation/run_validation.py ──▶ validation report
```

---

## Tool & Skill Reference

### Skills (Agentic — LLM-powered stages)

| Skill | Stage | Input | Output |
|-------|-------|-------|--------|
| `/survey-brainstorm` | 0 | `{TOPIC_DESCRIPTION}` | `surveys/survey_<slug>/gate0_scope/SURVEY_SCOPE.md` |
| `/research-lit` | 1 | `{TOPIC}` | `surveys/survey_<slug>/gate1_research_lit/paper_list.json`, `surveys/survey_<slug>/gate1_research_lit/papers/*.pdf` |
| `/paper-analysis` | 2 | `{TOPIC}` / `paper_list` | `surveys/survey_<slug>/gate2_paper_analysis/*_analysis.md` |
| `/taxonomy-build` | 3 | `gate2_paper_analysis/` | `surveys/survey_<slug>/gate3_taxonomy/taxonomy.md` |
| `/gap-identify` | 4 | `gate3_taxonomy/taxonomy.md` | `surveys/survey_<slug>/gate4_gap_analysis/gap_analysis.md` |
| `/survey-write` | 5 | `gate3_taxonomy/taxonomy.md` + `gate4_gap_analysis/gap_analysis.md` | `surveys/survey_<slug>/gate5_survey_write/SURVEY_DRAFT.md` |

### Tools (CLI — programmatic stages)

| Tool | What It Does | Input | Output |
|------|-------------|-------|--------|
| `tools/arxiv_fetch.py search "query" --max N` | Search arXiv API | query | JSON paper list |
| `tools/arxiv_fetch.py download <id> --dir papers/` | Download PDF by arXiv ID | arXiv ID | `papers/<id>.pdf` |
| `tools/arxiv_json_extractor.py` | Parse arXiv JSON → tier classification | `arxiv_results.json` | `corpus_report.md` |
| `tools/batch_paper_triage.py` | 12-field triage of ALL papers via arXiv API | `arxiv_results.json` | `all_papers_triage.json` |
| `tools/paper_triage.py <arxiv_id>` | Single-paper 12-field classification | arXiv ID | printed 12-field + subsection |
| `tools/convert_to_12field.py` | Upgrade 8-field → 12-field + POST_TASK_QC | `gate2_paper_analysis/*.md` | updated analyses |
| `tools/survey_trace_init.py` | Parse LaTeX → create survey_trace/ tree | survey `.tex` | `survey_trace/13 sections/` |
| `tools/survey_trace_sync.py` | Sync analyses → survey_trace records | `gate2_paper_analysis/` | `survey_trace/**/SUBSECTION_RECORD.md` |
| `tools/generate_survey_mindmap.py` | Generate mindmap from survey_trace | `survey_trace/` | `mindmap/survey_mindmap.pdf` |
| `validation/run_validation.py` | Citation, benchmark, guardrail validation | survey files | validation report |

---

## surveymind_run.py Stages

`tools/surveymind_run.py` exposes 9 executable stages:

```
python3 tools/surveymind_run.py --stage <name>
```

| Stage | Tool(s) Called | Description |
|-------|---------------|-------------|
| `brainstorm` | in-process | Generate `SURVEY_SCOPE.md` from `--scope-topic` + `--topic-keywords` |
| `arxiv-discover` | `arxiv_discover.py` | Broad-recall arXiv retrieval after scope confirmation, outputs gate1 `arxiv_results.json` |
| `corpus-extract` | `arxiv_json_extractor.py` | Parse `arxiv_results.json` → tiered corpus report |
| `paper-analysis` | `batch_paper_triage.py` (API) | Check coverage of `gate1_research_lit/paper_list.json` vs `gate2_paper_analysis/` |
| `batch-triage` | `batch_paper_triage.py` | 12-field triage of ALL papers in `arxiv_results.json` via arXiv API |
| `trace-init` | `survey_trace_init.py` | Parse LaTeX → create `survey_trace/` directory tree |
| `convert-12field` | `convert_to_12field.py` | Upgrade existing analyses from 8-field → 12-field format |
| `trace-sync` | `survey_trace_sync.py` | Sync paper analyses → `survey_trace/` subsection records |
| `validate` | `validation/run_validation.py` | Citation integrity, benchmark sanity, guardrail checks |
| `all` | all above | Run full pipeline in dependency order |

**CLI Examples:**
```bash
# Placeholder-first usage
python3 tools/surveymind_run.py --stage brainstorm \
  --scope-topic "{TOPIC_DESCRIPTION}" \
  --survey-name "{SURVEY_NAME}" \
  --topic-keywords "{KEYWORDS}"

# Full CLI pipeline
python3 tools/surveymind_run.py --stage all \
  --survey-name "{SURVEY_NAME}" \
  --arxiv-json "{ARXIV_JSON}" \
  --topic-keywords "{KEYWORDS}"

# Concrete example
python3 tools/surveymind_run.py --stage all \
  --survey-name "llm_reasoning_compression" \
  --topic-keywords "compression,quantization,reasoning,LLM"

# Individual stages
python3 tools/surveymind_run.py --stage corpus-extract
python3 tools/surveymind_run.py --stage arxiv-discover
python3 tools/surveymind_run.py --stage batch-triage --verbose
python3 tools/surveymind_run.py --stage trace-sync --verbose
```

---

## Quick Start

```bash
# Option A: Skill-based (recommended for new surveys)
claude
> /survey-brainstorm "{TOPIC_DESCRIPTION}"
> /survey-pipeline "{TOPIC}"

# Option B: CLI-based (reproducible, scriptable)
cd SurveyMind
python3 tools/surveymind_run.py --stage brainstorm \
  --scope-topic "{TOPIC_DESCRIPTION}" \
  --survey-name "{SURVEY_NAME}" \
  --topic-keywords "{KEYWORDS}"
python3 tools/surveymind_run.py --stage all \
  --survey-name "{SURVEY_NAME}" \
  --arxiv-json "{ARXIV_JSON}" \
  --topic-keywords "{KEYWORDS}"
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           SurveyMind Pipeline                              │
│                                                                           │
│  Skill-based: /survey-pipeline "topic"                                    │
│    Stage 0 ──▶ Stage 1 ──▶ Stage 2 ──▶ Stage 3 ──▶ Stage 4 ──▶ Stage 5 │
│    Brainstorm   Search    Analysis   Taxonomy   Gap-ID    Survey-Write    │
│       │          │          │          │          │          │          │
│       ▼          ▼          ▼          ▼          ▼          ▼          │
│  SURVEY_    paper_     paper_     taxonomy  gap_      SURVEY_          │
│  SCOPE.md   list.json  analysis/   .md     analysis.md  DRAFT.md      │
│                                                                           │
│  CLI-based: python3 tools/surveymind_run.py --stage all                  │
│    brainstorm ──▶ corpus-extract ──▶ batch-triage ──▶ paper-analysis     │
│         │              │                │                 │             │
│    SURVEY_       corpus_         all_papers_        coverage            │
│    SCOPE.md      report.md       triage.json         check              │
│                                                                           │
│         │              │                │                 │             │
│         ▼              ▼                ▼                 ▼             │
│    trace-init ──▶ convert-12field ──▶ trace-sync ──▶ validate            │
│         │              │                │                 │             │
│    survey_trace/   upgraded          survey_trace/     validation         │
│                    analyses         /**/SUBSECTION_      report         │
│                                    RECORD.md                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Auto-Proceed Mode** | Once confirmed, the pipeline runs autonomously through all stages — no repeated user confirmation needed |
| **Topic Refinement** | `/survey-brainstorm` jointly refines fuzzy topics into focused survey scopes |
| **Multi-source Search** | ArXiv, DBLP, Semantic Scholar, web — automatically find relevant papers |
| **Structured Paper Analysis** | 12-field classification: model type, method category, training paradigm, evaluation focus, hardware co-design, quantization bit scope, etc. |
| **Evidence Binding** | Every classification cites original paper text — fully auditable |
| **Auto Taxonomy** | Hierarchical taxonomy built from classified papers (method → submethod → specific technique) |
| **Gap Analysis** | Identifies unexplored combinations, under-explored settings, benchmark gaps |
| **Benchmark Synthesis** | Extracts and normalizes numbers across papers into unified comparison tables |
| **survey_trace** | Per-section evidence directory for traceable survey construction |
| **Validation Gate** | Automated citation integrity and benchmark sanity checks before final output |

---

## Taxonomy System — 12 Fields

Papers are classified across 12 structured fields:

| # | Field | Description |
|---|-------|-------------|
| 1 | Model Type | LLM, MLLM, MoE-LLM, SLM, VLM |
| 2 | Method Category | Representation Enhancement, Sparsity Exploitation, Knowledge Transfer, Hardware Co-design |
| 3 | Specific Method | Learnable Scaling, Structured Sparsity, Distillation, Rotation, KV-specific Quantization |
| 4 | Training Paradigm | QAT, PTQ, Hybrid, From-Scratch Low-bit Pretraining |
| 5 | Core Challenge | Outlier sensitivity, representation capacity, gradient flow disruption |
| 6 | Evaluation Focus | Perplexity, Downstream Accuracy, End-to-end Latency, Energy Efficiency |
| 7 | Hardware Co-design | CPU Kernel, GPU Mixed-precision, PIM/CIM Architecture, ASIC-friendly |
| 8 | Summary | Paper summary + survey contribution mapping |
| 9 | Quantization Bit Scope | 1-bit, 1.58-bit, 2-bit, 3-bit, 4-bit |
| 10 | General Method Type | Rotation/Transform, Reconstruction-based, Sparsity-aware, Learnable threshold |
| 11 | Core Challenge Addressed | Which of the 3 core challenges this method addresses |
| 12 | Ultra-low-bit Relevance Summary | Relevance to ultra-low bit (<2-bit) survey scope |

---

## Project Structure

```
SurveyMind/
├── skills/                          # Modular skill components
│   ├── survey-pipeline/           # End-to-end orchestrator skill
│   ├── survey-brainstorm/          # Topic refinement & scope definition (NEW)
│   ├── research-lit/              # Literature search
│   ├── paper-analysis/            # Paper classification (12-dim framework)
│   ├── taxonomy-build/           # Taxonomy construction
│   ├── gap-identify/             # Research gap analysis
│   ├── survey-write/             # Survey generation
│   └── [other ML research skills]
├── tools/                          # CLI utility scripts
│   ├── surveymind_run.py         # Pipeline orchestrator (8 stages)
│   ├── arxiv_fetch.py            # arXiv search & download
│   ├── arxiv_json_extractor.py   # arXiv JSON → corpus report
│   ├── batch_paper_triage.py     # Bulk 12-field triage via API
│   ├── paper_triage.py           # Single-paper 12-field triage
│   ├── convert_to_12field.py     # 8-field → 12-field upgrade
│   ├── survey_trace_init.py      # LaTeX → survey_trace/ tree
│   ├── survey_trace_sync.py      # Analyses → survey_trace records
│   ├── generate_survey_mindmap.py # Mindmap generation
│   └── benchmark_extractor.py    # Extract benchmarks from papers
├── templates/                      # Analysis & record templates
├── validation/                     # Validation rules (guardrails)
├── surveys/                        # Per-survey isolated outputs
│   └── survey_<topic_slug>/
│       ├── gate0_scope/
│       ├── gate1_research_lit/
│       ├── gate2_paper_analysis/
│       ├── gate3_taxonomy/
│       ├── gate4_gap_analysis/
│       ├── gate5_survey_write/
│       ├── survey_trace/
│       └── validation/
├── WORKLOG.md                      # Optional global execution log
└── README.md
```

---

## Session Recovery

SurveyMind maintains state across sessions:

- **CLAUDE.md** — Pipeline status, reading order, file organization
- **WORKLOG.md** — Phase-by-phase execution log
- **findings.md** — Gate-by-gate summaries for context recovery

When resuming a session, the agent automatically reads these files to restore context.

---

## Troubleshooting

### SSL Certificate Errors (macOS)
```bash
brew install curl-ca-bundle
/Applications/Python\ 3.x/Install\ Certificates.command
pip install certifi
```

### arXiv Download Timeout
1. Check your internet connection
2. Try using a proxy or VPN
3. Reduce the number of papers
4. Use local papers: `--sources local`

### No Papers Found
1. Broaden the search topic
2. Check spelling and keyword variations
3. Ensure API keys are set
4. Try: `--sources all`

### Skill Not Found
```bash
cd SurveyMind && ./install.sh
ls ~/.claude/skills/
```

### Analysis Results Empty
1. Verify PDFs were downloaded successfully
2. Check that `surveys/survey_<slug>/gate1_research_lit/paper_list.json` exists
3. Ensure papers are not password-protected

---

## Citation

```bibtex
@software{surveymind,
  title = {SurveyMind: Automated Research Survey Agent},
  author = {[Author]},
  year = {2026},
  url = {[Repository URL]}
}
```

## License

MIT License — see [LICENSE](LICENSE) for details.
