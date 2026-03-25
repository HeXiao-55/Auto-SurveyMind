# SurveyMind: Automated Research Survey Agent

> An autonomous AI agent framework for conducting comprehensive literature surveys in any research subfield. From topic specification to structured survey report — fully automated.

## Overview

SurveyMind automates the entire process of writing a research survey paper:

- **Input**: A research subfield (e.g., "efficient inference for large language models")
- **Output**: A structured survey report with taxonomy, benchmark analysis, and research gap identification
- **Process**: Multi-source literature search → paper classification → taxonomy construction → gap analysis → survey writing

The system runs autonomously — literature retrieval, paper analysis with structured classification, evidence extraction, taxonomy construction, and academic writing are all automated.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SurveyMind Pipeline                             │
│                                                                       │
│  /survey-pipeline "efficient LLM inference"                          │
│        │                                                              │
│        ▼                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │ Paper Search │───▶│ Paper       │───▶│ Taxonomy     │           │
│  │ & Download   │    │ Analysis &  │    │ Build &      │           │
│  │ (arXiv/DBLP/ │    │ Classification│   │ Gap ID       │           │
│  │  Scholar)    │    │ (8-dim)     │    │              │           │
│  └──────────────┘    └──────────────┘    └──────────────┘           │
│          │                   │                    │                  │
│          ▼                   ▼                    ▼                  │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │              Structured Survey Report                        │     │
│  │  • Hierarchical taxonomy by methodology & application       │     │
│  │  • Benchmark comparison tables (accuracy, efficiency)       │     │
│  │  • Research gaps & future directions                        │     │
│  │  • Evidence binding (every claim cites original paper)      │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-source Search** | ArXiv, DBLP, Semantic Scholar, web — automatically find relevant papers |
| **Structured Paper Analysis** | 8-dimension classification: model type, method category, training paradigm, evaluation focus, hardware co-design, etc. |
| **Evidence Binding** | Every classification cites original paper text — fully auditable |
| **Auto Taxonomy** | Hierarchical taxonomy built from classified papers (method → submethod → specific technique) |
| **Gap Analysis** | Identifies unexplored combinations, under-explored settings, benchmark gaps |
| **Benchmark Synthesis** | Extracts and normalizes numbers across papers into unified comparison tables |
| **Survey Generation** | Produces publication-ready survey document with proper academic structure |

## Taxonomy System

Papers are classified across 8 structured dimensions:

| Dimension | Example Categories |
|-----------|-------------------|
| **Model Type** | LLM, MLLM, MoE-LLM, SLM, VLM |
| **Method Category** | Representation Enhancement, Sparsity Exploitation, Knowledge Transfer, Hardware Co-design, Analysis |
| **Specific Method** | Learnable Scaling, Structured Sparsity, Distillation, Rotation, KV-specific Quantization |
| **Training Paradigm** | QAT, PTQ, Hybrid, From-Scratch Low-bit Pretraining |
| **Evaluation Focus** | Perplexity, Downstream Accuracy, End-to-end Latency, Energy Efficiency |
| **Hardware Co-design** | CPU Kernel, GPU Mixed-precision, PIM/CIM Architecture, ASIC-friendly |

## Workflows

### Full Survey Pipeline

```bash
/survey-pipeline "your research subfield"
```

Single command: search → analyze → classify → build taxonomy → identify gaps → write survey.

### Step-by-Step

| Step | Command | What it does |
|------|---------|--------------|
| 1 | `/research-lit "subfield"` | Multi-source literature search |
| 2 | `/paper-analysis "papers/"` | Analyze papers with 8-dimension taxonomy |
| 3 | `/taxonomy-build` | Build hierarchical taxonomy from classified papers |
| 4 | `/gap-identify` | Identify research gaps and future directions |
| 5 | `/survey-write` | Generate structured survey document |

## Output Example

The pipeline produces a structured survey report:

```markdown
# Survey: Efficient LLM Inference

## 1. Introduction
## 2. Background

## 3. Taxonomy

### 3.1 Quantization Methods
#### 3.1.1 Post-Training Quantization (PTQ)
- **1-bit**: QAT-LLM, BiLLM, ...
- **1.58-bit**: TinyChat, ...
#### 3.1.2 Quantization-Aware Training (QAT)
- ...

### 3.2 Pruning Methods
### 3.3 Knowledge Distillation

## 4. Benchmark Comparison

| Method | Type | WikiText-2 PPL | ARC | Latency | Memory |
|--------|------|----------------|-----|---------|--------|
| QAT-LLM 1-bit | QAT | 12.3 | 45.2 | 1.0x | 0.9GB |
| TinyChat 1.58b | PTQ | 13.1 | 43.8 | 0.9x | 0.8GB |

## 5. Research Gaps

1. **Unexplored combination**: Sub-2-bit quantization + speculative decoding
2. **Benchmark gap**: No unified benchmark covering accuracy + efficiency + energy
3. **Methodology gap**: Limited analysis of outliers in extreme quantization
```

## Quick Start

```bash
# 1. Clone and install (or copy locally)
git clone <REPO_URL>  # or: cp -r /path/to/SurveyMind .
cd SurveyMind
./install.sh

# 2. Configure API keys (optional)
export ARXIV_API_KEY=your_key    # for enhanced search
export GEMINI_API_KEY=your_key   # for paper illustration

# 3. Run a survey
claude
> /survey-pipeline "efficient LLM inference"
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--topic` | required | Research subfield to survey |
| `--depth` | `standard` | `quick` (20 papers) / `standard` (50) / `comprehensive` (100+) |
| `--sources` | `all` | `arxiv`, `semantic`, `dblp`, `web`, `zotero`, `local`, or `all` |
| `--output` | `survey.md` | Output file path |

## Project Structure

```
SurveyMind/
├── skills/                          # Modular skill components
│   ├── survey-pipeline/            # End-to-end orchestrator
│   ├── research-lit/              # Literature search
│   ├── paper-analysis/            # Paper classification (8-dim taxonomy)
│   ├── taxonomy-build/            # Taxonomy construction
│   ├── gap-identify/              # Research gap analysis
│   ├── survey-write/              # Survey generation
│   └── [other ML research skills] # Reusable components
├── templates/                       # Output templates
│   ├── paper_analysis_template.md
│   ├── taxonomy_template.md
│   ├── gap_analysis_template.md
│   └── survey_template.md
├── tools/                          # Utility scripts
│   ├── arxiv_fetch.py             # ArXiv paper retrieval
│   ├── bibtex_fetch.py            # BibTeX from DBLP/CrossRef
│   └── [domain-specific tools]    # Analysis tools
└── README.md
```

## Troubleshooting

### SSL Certificate Errors (macOS)

If you encounter SSL certificate errors when downloading from arXiv:

```bash
# Option 1: Install certificates via Homebrew
brew install curl-ca-bundle

# Option 2: Run Python's certificate installer
/Applications/Python\ 3.x/Install\ Certificates.command

# Option 3: Install certifi package
pip install certifi
/Applications/Python\ 3.x/Install\ Certificates.command
```

### arXiv Download Timeout

If downloads are slow or timing out:

1. Check your internet connection
2. Try using a proxy or VPN
3. Reduce the number of papers in `--depth quick` mode
4. Use local papers by setting `--sources local`

### No Papers Found

If the search returns no papers:

1. Try broadening the search topic (e.g., "machine learning" instead of "specific technique")
2. Check spelling and keyword variations
3. Ensure API keys are set for enhanced search
4. Try different sources: `--sources all`

### Skill Not Found

If `/survey-pipeline` command is not recognized:

```bash
# Re-run installation
cd SurveyMind
./install.sh

# Verify skills are installed
ls ~/.claude/skills/
```

### Analysis Results Empty

If paper analysis produces empty results:

1. Verify PDFs were downloaded successfully
2. Check that `paper_list.json` exists in the working directory
3. Ensure papers are in readable format (not password-protected)

### Memory Issues

For large surveys (100+ papers):

1. Use `--depth standard` instead of `--depth comprehensive`
2. Process papers in batches
3. Clear intermediate files between runs

## Citation

If this tool helped your research, please cite:

```bibtex
@software{surveymind,
  title = {SurveyMind: Automated Research Survey Agent},
  author = {[Author]},
  year = {2026},
  url = {[Repository URL]}
}
```

## License

MIT License - see [LICENSE](LICENSE) for details.
