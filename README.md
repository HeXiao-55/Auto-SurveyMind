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
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

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
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

Stage 2 ──────────────────────────────────────────────────────────────────────
  /paper-analysis "topic"   [Skill]
        │
        │  LLM reads each paper PDF
        │  Extracts multi-dimensional classification + evidence snippets (dimensions emerge from corpus)
        │
        ▼
  gate2_paper_analysis/*_analysis.md  (per-paper structured analysis)
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

  ── OR, for bulk API-level coverage check ──
  python3 tools/surveymind_run.py --stage paper-analysis   [CLI]
        │
        │  tools/batch_paper_triage.py  (multi-field via arXiv API, no deep PDF)
        │
        ▼
  gate2_paper_analysis/all_papers_triage.json  (multi-field triage for all papers in gate1 paper_list.json)
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

Stage 3 ──────────────────────────────────────────────────────────────────────
  /taxonomy-build "topic"   [Skill]
        │
        │  Reads gate2_paper_analysis/*.md
        │  Groups by method category, bit-width, training paradigm
        │
        ▼
  gate3_taxonomy/taxonomy.md  (hierarchical classification structure)
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

Stage 4 ──────────────────────────────────────────────────────────────────────
  /gap-identify "topic"   [Skill]
        │
        │  Reads gate3_taxonomy/taxonomy.md
        │  Identifies: unexplored combinations, benchmark gaps, method gaps
        │
        ▼
  gate4_gap_analysis/gap_analysis.md  (research gaps ranked by severity + confidence)
        │
        ▼ [state saved: WORKLOG.md + findings.md updated]

Stage 5 ──────────────────────────────────────────────────────────────────────
  /survey-write "topic"   [Skill]
        │
        │  Reads gate3_taxonomy/taxonomy.md + gate4_gap_analysis/gap_analysis.md
        │  Synthesizes into academic survey structure
        │
        ▼
  gate5_survey_write/SURVEY_DRAFT.md  (publication-ready survey document)
        │
        ▼ [state saved: WORKLOG.md + findings.md updated — survey complete]

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
        ├──> paper-download    ──▶ download PDFs for target tiers (Tier1/2 by default)
        ├──> paper-analysis    ──▶ tier-priority deep analysis + coverage report (Tier1/2 by default)
        ├──> trace-init       ──▶ tools/survey_trace_init.py ──▶ survey_trace/ directory tree
        ├──> taxonomy-alloc   ──▶ tools/taxonomy_alloc.py ──▶ taxonomy-derived field allocation
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
| `tools/batch_paper_triage.py` | multi-field triage of ALL papers via arXiv API | `arxiv_results.json` | `all_papers_triage.json` |
| `tools/paper_triage.py <arxiv_id>` | Single-paper multi-field classification | arXiv ID | printed multi-field + subsection |
| `tools/taxonomy_alloc.py` | Derive taxonomy-based fields from `taxonomy.md` and update analyses | `gate2_paper_analysis/*.md` + `gate3_taxonomy/taxonomy.md` | updated analyses |
| `tools/survey_trace_init.py` | Parse LaTeX → create survey_trace/ tree | survey `.tex` | `survey_trace/13 sections/` |
| `tools/survey_trace_sync.py` | Sync analyses → survey_trace records | `gate2_paper_analysis/` | `survey_trace/**/SUBSECTION_RECORD.md` |
| `tools/generate_survey_mindmap.py` | Generate mindmap from survey_trace | `survey_trace/` | `mindmap/survey_mindmap.pdf` |
| `validation/run_validation.py` | Citation, benchmark, guardrail validation | survey files | validation report |

---

## surveymind_run.py Stages

`tools/surveymind_run.py` exposes 10 executable stages:

```
python3 tools/surveymind_run.py --stage <name>
```

| Stage | Tool(s) Called | Description |
|-------|---------------|-------------|
| `brainstorm` | in-process | Generate `SURVEY_SCOPE.md` from `--scope-topic` + `--topic-keywords` |
| `arxiv-discover` | `arxiv_discover.py` | Broad-recall arXiv retrieval after scope confirmation, outputs gate1 `arxiv_results.json` |
| `corpus-extract` | `arxiv_json_extractor.py` | Parse `arxiv_results.json` → tiered corpus report |
| `paper-download` | in-process + `arxiv_fetch.py` | Ensure local PDFs exist for target tiers before deep analysis |
| `paper-analysis` | in-process + `paper_triage.py` fallback | Build target set from `all_papers_triage`, optionally generate missing analysis drafts, and emit coverage report |
| `batch-triage` | `batch_paper_triage.py` | multi-field triage of ALL papers in `arxiv_results.json` via arXiv API |
| `trace-init` | `survey_trace_init.py` | Parse LaTeX → create `survey_trace/` directory tree |
| `taxonomy-alloc` | `taxonomy_alloc.py` | Derive analysis fields from taxonomy structure and method-challenge mappings |
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
python3 tools/surveymind_run.py --stage paper-download --download-tier-scope tier1_tier2
python3 tools/surveymind_run.py --stage trace-sync --verbose
```

Priority-scope control for optional Tier3/4 operations:

```bash
# Download Tier3/4 PDFs only when you decide to expand later-stage analysis
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name "{SURVEY_NAME}" \
  --download-tier-scope tier3_tier4

# Run deep analysis on Tier3/4 on demand
python3 tools/surveymind_run.py --stage paper-analysis \
  --survey-name "{SURVEY_NAME}" \
  --analysis-tier-scope tier3_tier4 \
  --analysis-mode deep+coverage
```

---

## Quick Start

```bash
# Option A: Skill-based (recommended for new surveys)
claude
> /survey-brainstorm "{TOPIC_DESCRIPTION}"
> /survey-pipeline "{TOPIC}"

# Resume: the agent automatically reads WORKLOG.md + findings.md
# on session start to recover pipeline state — no manual action needed

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

## Common Use Cases

### Use Case 1: Resume & Expand Literature Coverage (add recent open-source papers, re-stratify)

Use this when you want to grow your paper corpus with newer results.

```bash
# 1. Re-search arXiv for new papers
python3 tools/surveymind_run.py --stage arxiv-discover \
  --survey-name graph_robustness \
  --topic-keywords "graph neural network,robustness,distribution shift,benchmark"

# 2. Re-stratify the updated corpus
python3 tools/surveymind_run.py --stage corpus-extract --survey-name ultra_low_bit

# 3. Re-run batch triage on all papers
python3 tools/surveymind_run.py --stage batch-triage \
  --survey-name graph_robustness \
  --topic-keywords "graph neural network,robustness,distribution shift,benchmark"

# 4. Download Tier1/2 PDFs before deep analysis
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name graph_robustness \
  --download-tier-scope tier1_tier2
```

Then deep-analyze newly added papers with a Skill:

```bash
> /paper-analysis "graph neural network robustness"
```

### Use Case 2: Structure & Conclusion Convergence (regenerate taxonomy / gap / survey)

Use this when your literature base is sufficient and you want to polish the survey toward submission-readiness.

```bash
> /taxonomy-build "graph neural network robustness"
> /gap-identify "graph neural network robustness"
> /survey-write "graph neural network robustness"
```

### Use Case 3: Rerun from Scratch Without Touching Existing Data

The safest approach: run the pipeline under a new survey name — old results stay completely untouched.

```bash
# Keep the old directory (survey_ultra_low_bit) intact
# New results go to: surveys/survey_graph_robustness_rerun_20260327/

# Step 1: brainstorm
python3 tools/surveymind_run.py --stage brainstorm \
  --survey-name graph_robustness_rerun_20260327 \
  --scope-topic "Robust learning for graph neural networks" \
  --topic-keywords "graph neural network,robustness,distribution shift,adversarial"

# Step 2: full pipeline rerun
python3 tools/surveymind_run.py --stage all \
  --survey-name graph_robustness_rerun_20260327 \
  --topic-keywords "graph neural network,robustness,distribution shift,adversarial" \
  --validation-strict
```

**Advanced strategy — reuse old corpus to save time**: If you want to re-run the full pipeline but reuse the existing arXiv corpus to skip re-discovery:

1. Copy the old `gate1_research_lit/arxiv_results.json` into the new survey directory
2. When running `stage all`, point to the old JSON as the input source

This gives you a fully reproducible re-run while keeping zero overlap with and zero damage to historical results — true zero-overwrite, full rollback support.

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
│    brainstorm ──▶ corpus-extract ──▶ batch-triage ──▶ paper-download      │
│        └──────────────────────────────────────────────▶ paper-analysis     │
│         │              │                │                 │             │
│    SURVEY_       corpus_         all_papers_        coverage            │
│    SCOPE.md      report.md       triage.json         check              │
│                                                                           │
│         │              │                │                 │             │
│         ▼              ▼                ▼                 ▼             │
│    trace-init ──▶ taxonomy-alloc ──▶ trace-sync ──▶ validate            │
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
| **Structured Paper Analysis** | Multi-dimensional classification extracted dynamically from the collected paper corpus — classification dimensions are not fixed in advance but emerge from the literature itself |
| **Evidence Binding** | Every classification cites original paper text — fully auditable |
| **Auto Taxonomy** | Hierarchical taxonomy built from classified papers (method → submethod → specific technique) |
| **Gap Analysis** | Identifies unexplored combinations, under-explored settings, benchmark gaps |
| **Benchmark Synthesis** | Extracts and normalizes numbers across papers into unified comparison tables |
| **survey_trace** | Per-section evidence directory for traceable survey construction |
| **Validation Gate** | Automated citation integrity and benchmark sanity checks before final output |

---

## How Taxonomy Emerges from Literature

The taxonomy is **not predefined** — it is induced from the collected paper corpus. Stage 2 (paper analysis) extracts classification dimensions dynamically from each paper, including:

- **Method dimensions**: what technique family does this paper belong to (e.g., rotation, reconstruction, pruning, distillation)?
- **Problem dimensions**: what challenge does it address (e.g., outlier handling, gradient flow, representation collapse)?
- **Evaluation dimensions**: what metrics and benchmarks does it report?
- **Scope dimensions**: what model types, bit-widths, and training paradigms are covered?

Stage 3 (`/taxonomy-build`) then clusters all papers into a **hierarchical structure** — groupings are derived entirely from the papers found, not from any fixed schema. The resulting taxonomy is therefore unique to each survey topic and corpus.

---

## Project Structure

```
SurveyMind/
├── skills/                          # Modular skill components
│   ├── survey-pipeline/           # End-to-end orchestrator skill
│   ├── survey-brainstorm/          # Topic refinement & scope definition (NEW)
│   ├── research-lit/              # Literature search
│   ├── paper-analysis/            # Paper classification (dynamic multi-dim framework)
│   ├── taxonomy-build/           # Taxonomy construction
│   ├── gap-identify/             # Research gap analysis
│   ├── survey-write/             # Survey generation
│   └── [other ML research skills]
├── tools/                          # CLI utility scripts
│   ├── surveymind_run.py         # Pipeline orchestrator (8 stages)
│   ├── arxiv_fetch.py            # arXiv search & download
│   ├── arxiv_json_extractor.py   # arXiv JSON → corpus report
│   ├── batch_paper_triage.py     # Bulk multi-field triage via API
│   ├── paper_triage.py           # Single-paper multi-field triage
│   ├── taxonomy_alloc.py         # Taxonomy-based field allocation
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
