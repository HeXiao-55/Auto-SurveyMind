---
name: paper-analysis
description: "Analyze research papers using an 8-dimensional classification framework. Use when user says \"analyze paper\", \"classify this paper\", \"paper analysis\", or wants to extract structured information from academic papers for survey construction. Input: topic or paper document. Output: structured analysis in paper_analysis_results/"
argument-hint: "paper-topic-or-url-or-arXiv-ID"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, mcp__zotero__*, mcp__obsidian-vault__*
---

# Paper Analysis Skill

Analyzes research papers using a standardized 8-dimensional classification framework for survey construction.
The concrete labels should be aligned with the active domain profile instead of hardcoded domain terms.

## Input

**$ARGUMENTS** can be:
- An arXiv ID (e.g., `2401.12345`)
- An arXiv URL (e.g., `https://arxiv.org/abs/2401.12345`)
- A research topic to search and analyze top papers
- A local PDF path
- A path to `paper_list.json` (e.g., `papers/paper_list.json`) — for batch processing from `/research-lit` output

## Output

- **Directory**: `paper_analysis_results/`
- **File**: `{paper_id}_analysis.md` (e.g., `2401.12345_analysis.md`)
- Each analysis follows `templates/PAPER_ANALYSIS_TEMPLATE.md`

## 8-Dimensional Classification Framework

### Dimension Definitions

1. **Model Type**: The primary model/task family studied in the paper.
2. **Method Category**: The high-level method family in the active survey profile.
3. **Specific Method**: The concrete technique name or mechanism used by the paper.
4. **Training Paradigm**: The optimization/training/deployment paradigm (if applicable).
5. **Core Challenge**: The main bottleneck or problem the method addresses.
6. **Evaluation Focus**: The primary metrics, tasks, or benchmarks emphasized.
7. **Hardware Co-design**: Any explicit systems/hardware implementation coupling.
8. **Summary**: 1-2 sentence core contribution summary

Note: If a field label set is defined by the current profile, prefer profile labels over generic examples.

## Workflow

### Step 1: Acquire Paper

If input is a `paper_list.json` path:
1. Read the JSON file to get list of papers with `paper_id` and `pdf_path`
2. For each paper in the list, read the PDF from `pdf_path`
3. Process papers in batch

If input is a topic:
1. Search arXiv for top relevant papers using `tools/arxiv_fetch.py`
2. Download top 3-5 most relevant papers
3. Extract paper content

If input is an arXiv ID/URL:
1. Use `tools/arxiv_fetch.py download <id> --dir papers/`
2. Extract paper content

If input is a local PDF path:
1. Read the PDF directly

### Step 2: Extract Paper Metadata

For each paper, extract:
- Title, Authors, Year/Month, Venue
- arXiv ID (if applicable)
- Source (arXiv/Zotero/Local/Web)

### Step 3: Analyze Paper Content

Read and analyze:
- Abstract (for high-level summary)
- Introduction (for motivation and scope)
- Method section (for technical details)
- Experiments (for evaluation metrics and results)
- Conclusion (for key takeaways)

### Step 4: Apply 8-Dimensional Classification

For each dimension:
1. Classify based on paper content
2. **Evidence binding**: Quote the specific text from the paper that supports the classification
3. Note the evidence type (Abstract/Method/Experiment/Conclusion)
4. Assign confidence (High/Med/Low)
5. If the paper does not fit existing profile labels, mark as `Other` and explain why.

### Step 5: Generate Evidence Table

Create a table with:
| Claim | Evidence Type | Source Snippet | Confidence |

Each row must have a quote from the paper.

### Step 6: Identify Gap Indicators

For each paper, note:
- Does it identify any research gaps?
- Gap type: Unexplored Combination, Benchmark Gap, Methodological Gap, Scale Gap, Generalization Gap

### Step 7: Write Output

Using `templates/PAPER_ANALYSIS_TEMPLATE.md`, write:
```
paper_analysis_results/{paper_id}_analysis.md
```

## Quality Control Checklist

- [ ] Paper ID assigned
- [ ] All 8 dimensions classified
- [ ] Each classification has evidence binding (quote + source location)
- [ ] Evidence table complete with ≥3 rows
- [ ] Summary is ≤2 sentences, innovation-focused
- [ ] Gap indicator filled
- [ ] File written to `paper_analysis_results/`

## Evidence Binding Rules (MANDATORY)

- **Every classification must cite specific text from the paper**
- Use format: `Source: [Abstract/Method/Experiment/Conclusion]`, `Quote: "{{original_text}}"`
- If evidence is insufficient for a classification, write: `Evidence: Insufficient - based on [what you have]`
- Never make up classifications without evidence
- Never classify something as "High" confidence if you're guessing

## Key Rules

- **Be conservative**: Only claim what the paper actually says
- **Cite precisely**: Use exact quotes or close paraphrases with page/section references
- **Distinguish claims**: Clearly separate author claims from your interpretation
- **Note limitations**: If a paper only tests on small models, say so
- **机器可读格式**: Output must be parseable by downstream skills (taxonomy-build, gap-identify)
- **Profile alignment**: Use the active profile's taxonomy vocabulary when assigning categories

## Example Output Structure

```markdown
# Paper Analysis: 2401.12345

## Paper Metadata
- **Paper ID**: 2401.12345
- **Title**: Example Paper Title
- **Authors**: Author et al.
- **Year/Month**: 2024/01
- **Venue**: arXiv
- **Source**: arXiv

## 8-Dimensional Classification

### 1. Model Type
**Classification**: [profile-aligned category]
**Evidence**:
- Source: Abstract
- Quote: "{{exact excerpt from the paper}}"

### 2. Method Category
...
```

---

*For survey construction workflow, see `/survey-pipeline`*
