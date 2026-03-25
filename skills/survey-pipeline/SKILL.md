---
name: survey-pipeline
description: "End-to-end survey construction pipeline: research literature → paper analysis → taxonomy building → gap identification → survey writing. Use when user says \"survey pipeline\", \"full survey\", \"build a survey\", \"automated survey\", or wants to generate a comprehensive research survey document. Command: /survey-pipeline \"research subfield\""
argument-hint: [research-subfield]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, mcp__zotero__*, mcp__obsidian-vault__*
---

# Survey Pipeline

End-to-end automated survey construction pipeline that goes from a research topic to a comprehensive survey document.

## Overview

```
/research-lit → /paper-analysis → /taxonomy-build → /gap-identify → /survey-write
```

**Pipeline Flow:**
```
Research Literature → Paper Analysis → Taxonomy Building → Gap Identification → Survey Writing
       ↓                    ↓                  ↓                ↓                ↓
  paper_list.json     paper_analysis/       taxonomy.md     gap_analysis.md   SURVEY_DRAFT.md
```

## Arguments

**$ARGUMENTS**: The research subfield to survey (e.g., "Efficient LLM inference", "Model quantization")

## Constants

- **MAX_PAPERS = 20** — Maximum number of papers to analyze
- **PAPER_DOWNLOAD = true** — Download PDFs for deeper analysis
- **MIN_PAPERS_FOR_TAXONOMY = 5** — Minimum papers needed to build taxonomy

## Pipeline Stages

### Stage 1: Research Literature (`/research-lit`)

**Command**: `/research-lit "$ARGUMENTS — arxiv download: true"`

**What happens:**
1. Searches for papers on the topic via arXiv API
2. Downloads top relevant PDFs
3. Returns structured paper list with metadata

**Output:**
- `paper_list.json` — Machine-readable paper list with paper_id, title, authors, year, venue, arXiv ID, and pdf_path
- Saved PDFs in `papers/` or `literature/`

**🚦 Gate 1 — Confirmation:**
After Stage 1, present paper count and ask for confirmation to proceed:
```
📚 Found N papers on "$ARGUMENTS"

Top papers:
1. [Title] - [Authors] ([Year])
2. [Title] - [Authors] ([Year])
...

Proceed to paper analysis?
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
- Directory: `paper_analysis_results/`
- Files: `{paper_id}_analysis.md` for each paper

**🚦 Gate 2 — Review:**
After Stage 2, report analysis completion:
```
✅ Paper analysis complete: N papers analyzed
📁 Results saved to: paper_analysis_results/

Classification summary:
- LLM papers: N
- MLLM papers: N
- QAT methods: N
- PTQ methods: N
...
```

### Stage 3: Taxonomy Building (`/taxonomy-build`)

**Command**: `/taxonomy-build "$ARGUMENTS"`

**What happens:**
1. Reads all `paper_analysis_results/*.md` files
2. Builds hierarchical taxonomy
3. Analyzes coverage and interconnections

**Output:**
- `taxonomy.md` — Hierarchical classification structure

**🚦 Gate 3 — Review:**
After Stage 3, present taxonomy summary:
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
After Stage 4, present gap summary:
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

- **Sequential execution**: Each stage depends on the previous
- **Human checkpoints**: Pause at each gate for user review
- **Graceful degradation**: If a stage finds few papers, continue with warning
- **Evidence binding**: All claims must be traceable to original papers
- **Machine-readable outputs**: All intermediate files must be parseable by downstream stages

## Error Handling

- **No papers found**: Report error, suggest broadening topic
- **Insufficient papers for taxonomy**: Warn but continue (MIN_PAPERS_FOR_TAXONOMY = 5)
- **Stage failure**: Report error with specific issue, offer to retry

## Integration with Existing Skills

The pipeline chains these skills:
1. `/research-lit` — Paper discovery
2. `/paper-analysis` — Paper analysis (NEW)
3. `/taxonomy-build` — Taxonomy construction (NEW)
4. `/gap-identify` — Gap identification (NEW)
5. `/survey-write` — Survey generation (NEW)

## Typical Use Cases

```
/survey-pipeline "efficient LLM inference"
/survey-pipeline "model quantization for LLMs"
/survey-pipeline "sparse methods for transformer models"
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
