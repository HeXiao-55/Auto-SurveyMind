---
name: survey-pipeline
description: "End-to-end survey construction pipeline: research literature → paper analysis → taxonomy building → gap identification → survey writing. Use when user says \"survey pipeline\", \"full survey\", \"build a survey\", \"automated survey\", or wants to generate a comprehensive research survey document. Command: /survey-pipeline \"research subfield\""
argument-hint: "research-subfield"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, mcp__zotero__*, mcp__obsidian-vault__*
---

# Survey Pipeline

End-to-end automated survey construction pipeline that goes from a research topic to a comprehensive survey document.

## Overview

```
/survey-brainstorm → /research-lit → /paper-analysis → /taxonomy-build → /gap-identify → /survey-write
```

**Pipeline Flow:**
```
Brainstorm & Scope → Research Literature → Paper Analysis → Taxonomy Building → Gap Identification → Survey Writing
       ↓                    ↓                  ↓                ↓                ↓                ↓
  SURVEY_SCOPE.md     paper_list.json   paper_analysis/     taxonomy.md     gap_analysis.md   SURVEY_DRAFT.md
```

## Arguments

**$ARGUMENTS**: The research subfield to survey (e.g., "graph robustness", "multimodal reasoning evaluation"). If the idea is fuzzy or too broad, the pipeline will invoke `/survey-brainstorm` first to refine the scope.

## Constants

- **AUTO_PROCEED = true** — When true, auto-continue through all gates without waiting for confirmation. Set to false to pause at each gate.
- **USE_EXISTING_ARXIV_JSON = true** — When true, check for existing arxiv_results.json before fresh search. If found, use batch-triage to process all papers.
- **MAX_PAPERS = 20** — Maximum number of papers to analyze
- **PAPER_DOWNLOAD = true** — Download PDFs for deeper analysis
- **MIN_PAPERS_FOR_TAXONOMY = 5** — Minimum papers needed to build taxonomy

## Stage 0: Brainstorm & Topic Refinement (`/survey-brainstorm`)

**Command**: `/survey-brainstorm "$ARGUMENTS"`

**When to run**: If the user's idea is fuzzy (e.g., "I want to write a survey about AI systems") rather than a specific subfield, invoke this stage FIRST to jointly refine the scope.

**What happens:**
1. Explores the broad field via arXiv search and web search
2. Presents sub-directions to the user
3. Asks clarifying questions (problem scope, target entities/tasks, method families, target venue)
4. Outputs `SURVEY_SCOPE.md` with refined topic and parameters

**Output:** `SURVEY_SCOPE.md` — refined survey specification

**🚦 Gate 0 — Scope confirmation:**
After Stage 0, present the refined scope. If `AUTO_PROCEED=true`, auto-continue. Otherwise ask for confirmation:
```
📋 Refined Survey Scope:

Topic: Robust graph learning under distribution shift
Keywords: graph neural network, robustness, distribution shift, benchmark
Problem scope: method + evaluation protocol
Venue: TPAMI

[Auto] Proceeding to literature search... (AUTO_PROCEED=true)
```

## Pipeline Stages

### Stage 1: Research Literature (`/research-lit` OR batch-triage)

**Logic** (runs automatically when skill is invoked):

1. **Check for existing arxiv_results.json**:
   - Check `./arxiv_results.json`
   - Check `./tpami_tem/arxiv_results.json`
   - Check `../tpami_tem/arxiv_results.json` (parent dir)

2. **If arxiv_results.json exists AND USE_EXISTING_ARXIV_JSON=true**:
   - Run batch-triage via CLI:
     ```bash
     python3 tools/surveymind_run.py --stage batch-triage --arxiv-json <path>
     ```
   - This processes ALL papers in arxiv_results.json (up to 170 papers)
   - Output: `corpus_report.json`, `corpus_report.md` with tier classification

3. **If arxiv_results.json NOT found**:
   - Run fresh search: `/research-lit "$ARGUMENTS — arxiv download: true"`
   - This searches arXiv API and creates paper_list.json

**What happens (batch-triage mode):**
1. Reads arxiv_results.json (all papers)
2. Calls arXiv API for metadata/enrichment for each paper
3. Applies 12-field classification
4. Outputs tiered corpus report

**Output (batch-triage mode):**
- `corpus_report.json` — Machine-readable corpus with tier 1-4 classification
- `corpus_report.md` — Human-readable tier summary

**Output (fresh search mode):**
- `paper_list.json` — Machine-readable paper list with paper_id, title, authors, year, venue, arXiv ID, and pdf_path
- Saved PDFs in `papers/` or `literature/`

**🚦 Gate 1 — Confirmation:**
After Stage 1, present paper count. If `AUTO_PROCEED=true`, auto-continue. Otherwise ask for confirmation:

**Batch-triage mode:**
```
📚 Using existing arxiv_results.json: N papers
├── Tier 1 (core): X papers
├── Tier 2 (high relevance): X papers
├── Tier 3 (related): X papers
└── Tier 4 (peripheral): X papers

[Auto] Proceeding to paper analysis... (AUTO_PROCEED=true)
```

**Fresh search mode:**
```
📚 Found N papers on "$ARGUMENTS"

Top papers:
1. [Title] - [Authors] ([Year])
2. [Title] - [Authors] ([Year])
...

[Auto] Proceeding to paper analysis... (AUTO_PROCEED=true)
```

When auto-proceeding, also append to `findings.md`:
```markdown
- [Gate 1] research-lit complete: N papers for "$ARGUMENTS" (source: batch-triage/fresh-search)
```

### Stage 2: Paper Analysis (`/paper-analysis`)

**Command**: `/paper-analysis "$ARGUMENTS"`

**What happens:**
1. **Reads `paper_list.json`** from Stage 1 output to get paper_id and pdf_path
2. Loads papers from the paths specified in paper_list.json
3. Applies 8-dimensional classification to each paper
4. Generates structured analysis files

**Data Flow:**
```
Stage 1 output (paper_list.json) ──▶ Stage 2 input
         │
         └── paper_id, pdf_path, title, authors, venue
```

**Output:**
- Directory: `surveys/survey_<topic_slug>/gate2_paper_analysis/`
- Files: `{paper_id}_analysis.md` for each paper

**🚦 Gate 2 — Review:**
After Stage 2, report analysis completion. If `AUTO_PROCEED=true`, auto-continue:
```
✅ Paper analysis complete: N papers analyzed
📁 Results saved to: gate2_paper_analysis/

Classification summary:
- Model family A: N
- Model family B: N
- Method family A: N
- Method family B: N
...

[Auto] Proceeding to taxonomy building... (AUTO_PROCEED=true)
```

When auto-proceeding, also append to `findings.md`:
```markdown
- [Gate 2] paper-analysis complete: N papers classified across X categories
```

### Stage 3: Taxonomy Building (`/taxonomy-build`)

**Command**: `/taxonomy-build "$ARGUMENTS"`

**What happens:**
1. Reads all `gate2_paper_analysis/*.md` files
2. Builds hierarchical taxonomy
3. Analyzes coverage and interconnections

**Output:**
- `taxonomy.md` — Hierarchical classification structure

**🚦 Gate 3 — Review:**
After Stage 3, present taxonomy summary. If `AUTO_PROCEED=true`, auto-continue:
```
📊 Taxonomy built successfully

Hierarchy:
├── Representation Enhancement (N papers)
│   ├── Learnable Scaling (N)
│   └── Rotation Transform (N)
├── Sparsity Exploitation (N papers)
│   └── ...
...

Coverage:
- Method Categories: N
- Submethods: N
- Most common: [Method] (N papers)

[Auto] Proceeding to gap identification... (AUTO_PROCEED=true)
```

When auto-proceeding, also append to `findings.md`:
```markdown
- [Gate 3] taxonomy built: X categories, Y submethods identified
```

### Stage 4: Gap Identification (`/gap-identify`)

**Command**: `/gap-identify "$ARGUMENTS"`

**What happens:**
1. Reads `taxonomy.md`
2. Identifies 5 types of research gaps
3. Prioritizes gaps by severity and confidence

**Output:**
- `gap_analysis.md` — Research gaps and opportunities

**🚦 Gate 4 — Review:**
After Stage 4, present gap summary. If `AUTO_PROCEED=true`, auto-continue:
```
🔍 Gap analysis complete

Gap Summary:
| Gap Type | Count | Top Priority |
|----------|-------|--------------|
| Unexplored Combinations | N | Yes |
| Benchmark Gaps | N | |
...

Top Research Opportunities:
1. [Opportunity 1] (Impact: High, Difficulty: Med)
2. [Opportunity 2] (Impact: Med, Difficulty: High)

[Auto] Proceeding to survey writing... (AUTO_PROCEED=true)
```

When auto-proceeding, also append to `findings.md`:
```markdown
- [Gate 4] gap analysis complete: Z gaps identified, top opportunity: [description]
```

### Stage 5: Survey Writing (`/survey-write`)

**Command**: `/survey-write "$ARGUMENTS"`

**What happens:**
1. Reads `taxonomy.md` and `gap_analysis.md`
2. Synthesizes into standard academic survey structure
3. Generates comprehensive survey document

**Output:**
- `SURVEY_DRAFT.md` — Complete survey document

### Final Report

After Stage 5, present completion summary:
```
🎉 Survey pipeline complete!

📄 Output files:
├── SURVEY_SCOPE.md (refined survey specification)
├── paper_analysis_results/ (N analysis files)
├── taxonomy.md
├── gap_analysis.md
└── SURVEY_DRAFT.md

Survey Statistics:
- Papers analyzed: N
- Method categories: N
- Research gaps identified: N
- Survey sections: 6

Next steps:
- Review SURVEY_DRAFT.md
- Add missing references
- Refine gap prioritization
- Customize for target venue
```

## Key Rules

- **Fuzzy topic detection**: If `$ARGUMENTS` is too broad or vague (e.g., "survey on AI", "写综述", "optimization"), invoke `/survey-brainstorm` FIRST to refine the scope before proceeding to Stage 1.
- **Sequential execution**: Each stage depends on the previous
- **Auto-proceed by default**: When `AUTO_PROCEED=true`, automatically continue through gates (default behavior)
- **Graceful degradation**: If a stage finds few papers, continue with warning
- **Evidence binding**: All claims must be traceable to original papers
- **Machine-readable outputs**: All intermediate files must be parseable by downstream stages
- **Findings tracking**: At each gate, append a one-line summary to `findings.md` for session recovery

## Error Handling

- **No papers found**: Report error, suggest broadening topic
- **Insufficient papers for taxonomy**: Warn but continue (MIN_PAPERS_FOR_TAXONOMY = 5)
- **Stage failure**: Report error with specific issue, offer to retry

## Integration with Existing Skills

The pipeline chains these skills:
0. `/survey-brainstorm` — Topic refinement & scope definition (Stage 0, pre-survey)
1. `/research-lit` — Paper discovery
2. `/paper-analysis` — Paper analysis
3. `/taxonomy-build` — Taxonomy construction
4. `/gap-identify` — Gap identification (NEW)
5. `/survey-write` — Survey generation (NEW)

## Typical Use Cases

```
/survey-pipeline "graph neural network robustness"
/survey-pipeline "multimodal reasoning evaluation"
/survey-pipeline "privacy-preserving federated optimization"
```

## Files Generated

```
paper_analysis_results/
├── 2401.12345_analysis.md
├── 2402.23456_analysis.md
└── ...
taxonomy.md
gap_analysis.md
SURVEY_DRAFT.md
```

---

*This skill orchestrates the complete survey construction workflow.*
