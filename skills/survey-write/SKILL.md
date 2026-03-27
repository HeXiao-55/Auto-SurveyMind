---
name: survey-write
description: "Generate a structured survey document from taxonomy and gap analysis. Use when user says \"write survey\", \"generate survey\", \"create survey draft\", or needs to synthesize research into a comprehensive survey document. Input: taxonomy.md + gap_analysis.md. Output: SURVEY_DRAFT.md"
argument-hint: "survey-topic"
---

# Survey Write Skill

Generates a comprehensive survey document from taxonomy and gap analysis.

## Input

**$ARGUMENTS**: The survey topic (e.g., "Graph Robustness", "Scientific Foundation Models")

**Expected Input Files**:
1. `taxonomy.md` - hierarchical taxonomy (from `/taxonomy-build`)
2. `gap_analysis.md` - research gap analysis (from `/gap-identify`)

**Optional Input**:
- `paper_analysis_results/` directory - for detailed paper references

## Output

**File**: `SURVEY_DRAFT.md` in the current working directory
- Follows `templates/SURVEY_TEMPLATE.md`
- Standard academic survey structure

## Workflow

### Step 1: Verify Input Files

1. Check that `taxonomy.md` exists and is readable
2. Check that `gap_analysis.md` exists and is readable
3. If either is missing, error: "Missing required input. Run `/taxonomy-build` and `/gap-identify` first."

### Step 2: Parse Taxonomy

Extract from `taxonomy.md`:
- Hierarchical structure (Method Categories -> Submethods -> Specific Techniques)
- Paper counts per category
- Coverage statistics
- Interconnections and patterns

### Step 3: Parse Gap Analysis

Extract from `gap_analysis.md`:
- All 5 gap types
- Prioritized gap list
- Research opportunities
- Supporting evidence

### Step 4: Draft Introduction

Write Section 1: Introduction
- 1.1 Motivation: Why is this topic important?
- 1.2 Scope and Definitions: What does the survey cover?
- 1.3 Organization: How is the survey organized?

### Step 5: Draft Background

Write Section 2: Background and Motivation
- 2.1 Historical Context
- 2.2 Fundamental Concepts
- 2.3 Challenges Overview
- 2.4 Evaluation Metrics

### Step 6: Draft Taxonomy Section

Write Section 3: Taxonomy of Methods
- 3.1 Taxonomy Overview
- 3.2 Classification by Method Category (use hierarchy from taxonomy.md)
- 3.3 Classification by Training Paradigm
- 3.4 Classification by Core Challenge

### Step 7: Draft Detailed Survey

Write Section 4: Detailed Survey by Category
For each Method Category:
- 4.X.1 Submethod 1
  - Description
  - Representative Papers (cite with paper IDs)
  - Key Techniques
  - Strengths
  - Limitations
- 4.X.2 Submethod 2
  - ...

### Step 8: Draft Gap Analysis Section

Write Section 5: Research Gaps and Future Directions
- 5.1 Unexplored Combinations
- 5.2 Benchmark Gaps
- 5.3 Methodological Gaps
- 5.4 Scale Gaps
- 5.5 Generalization Gaps
- 5.6 Recommended Future Directions

### Step 9: Draft Conclusion

Write Section 6: Conclusion
- 6.1 Summary of Contributions
- 6.2 Key Findings
- 6.3 Closing Remarks

### Step 10: Add References

Extract paper information from `paper_analysis_results/` and format as references.

### Step 11: Quality Check

Verify:
- All sections follow the template
- Evidence is properly cited
- Gap analysis is integrated
- Structure is hierarchical and clear

## Survey Structure

```
1. Introduction
   1.1 Motivation
   1.2 Scope and Definitions
   1.3 Organization

2. Background and Motivation
   2.1 Historical Context
   2.2 Fundamental Concepts
   2.3 Challenges Overview
   2.4 Evaluation Metrics

3. Taxonomy of Methods
   3.1 Taxonomy Overview
   3.2 Classification by Method Category
   3.3 Classification by Training Paradigm
   3.4 Classification by Core Challenge

4. Detailed Survey by Category
   [For each method category and submethod]

5. Research Gaps and Future Directions
   5.1 Unexplored Combinations
   5.2 Benchmark Gaps
   5.3 Methodological Gaps
   5.4 Scale Gaps
   5.5 Generalization Gaps
   5.6 Recommended Future Directions

6. Conclusion
   6.1 Summary of Contributions
   6.2 Key Findings
   6.3 Closing Remarks

References
Appendix A: Detailed Comparison Tables
Appendix B: Implementation Resources
```

## Citation Format

Use the following format for citing papers:
- In text: "[PaperID]" (e.g., "[2401.12345]")
- In references: Full citation with title, authors, venue, year

## Key Rules

- **Academic tone**: Write in formal academic style
- **Evidence-based**: Every claim should be supported by cited papers
- **Comprehensive**: Cover all method categories and submethods
- **Hierarchical**: Use clear heading hierarchy
- **Gap-focused**: Emphasize research gaps and future directions
- **Machine-readable metadata**: Include YAML frontmatter for tool compatibility

## Example Output Structure

```markdown
---
title: "Survey on [Topic]"
topic: "[Topic]"
date: "YYYY-MM-DD"
---

# Survey on [Topic]

## Abstract

This survey provides a comprehensive review of methods for [topic]...

## 1. Introduction

### 1.1 Motivation
[Topic background sentence]...
```

---

*For survey construction workflow, see `/survey-pipeline`*
