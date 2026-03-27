---
name: taxonomy-build
description: "Build a hierarchical taxonomy from paper analysis results. Use when user says \"build taxonomy\", \"create taxonomy\", \"organize papers by category\", or needs to synthesize paper analysis results into a structured classification system. Input: paper_analysis_results/ directory. Output: taxonomy.md"
argument-hint: "survey-topic"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Taxonomy Build Skill

Builds a hierarchical taxonomy from paper analysis results for survey construction.

## Input

**$ARGUMENTS**: The survey topic (e.g., "Graph Robustness", "Scientific Foundation Models")

**Expected Input Directory**: `paper_analysis_results/`
- Contains `{paper_id}_analysis.md` files
- Each file follows `templates/PAPER_ANALYSIS_TEMPLATE.md`

## Output

**File**: `taxonomy.md` in the current working directory
- Follows `templates/TAXONOMY_TEMPLATE.md`

## Workflow

### Step 1: Verify Input Directory

1. Check that `paper_analysis_results/` exists
2. Count the number of `{paper_id}_analysis.md` files
3. If < 3 papers, warn user: "Low paper count for taxonomy building. Consider running `/paper-analysis` first."

### Step 2: Parse All Paper Analyses

For each paper analysis file:
1. Extract the 8-dimensional classification
2. Extract paper metadata (ID, title, authors)
3. Extract the evidence table
4. Collect all classifications

### Step 3: Build Hierarchical Structure

#### Level 1: Method Category

Group papers by `Method Category` dimension:
- Method Family A
- Method Family B
- Method Family C
- System/Deployment-oriented Methods
- Evaluation/Analysis-oriented Methods
- Other

#### Level 2: Submethod

Within each Method Category, group by `Specific Method`:
- Technique A
- Technique B
- Technique C
- etc.

#### Level 3: Specific Technique

Group by combinations of `Specific Method` + `Training Paradigm` or other relevant sub-groupings.

### Step 4: Cross-Cutting Dimensions

Also organize by:
- **Training/Optimization Paradigm**: profile-aligned paradigms
- **Core Challenge**: profile-aligned challenge set
- **Evaluation Focus**: profile-aligned metric/task set

### Step 5: Coverage Analysis

Calculate statistics:
- Papers per Model Type
- Papers per Evaluation Focus
- Papers per Hardware Co-design
- Most common method categories
- Most common challenges

### Step 6: Interconnection Analysis

Identify patterns:
- Which method categories address which challenges?
- Which training paradigms work best for which challenges?
- Any notable method combinations?

### Step 7: Generate Output

Write `taxonomy.md` following `templates/TAXONOMY_TEMPLATE.md`:

```
# Taxonomy

## Hierarchical Taxonomy Structure

### Level 1: Method Category

#### Representation Enhancement
##### Level 2: Submethod
###### Learnable Scaling/Offset
...
```

### Step 8: Update Coverage Analysis Table

Include:
- Papers by Model Type
- Papers by Evaluation Focus
- Papers by Hardware Co-design
- Method-Challenge Matrix

## Taxonomy Statistics to Report

- Total Papers Analyzed
- Number of Level-1 Categories
- Number of Level-2 Submethods
- Most Common Method Category
- Most Common Challenge
- Coverage gaps (e.g., "no papers on X")

## Key Rules

- **Derive from evidence**: Taxonomy must be grounded in actual paper analyses
- **Evidence binding**: Each taxonomy node should list supporting paper IDs
- **Machine-readable**: Output must be parseable by `/gap-identify` skill
- **Hierarchical clarity**: Ensure clear parent-child relationships
- **Cross-references**: Link related categories where methods overlap

## Example Output Structure

```markdown
# Taxonomy: [Survey Topic]

## Hierarchical Taxonomy Structure

### Level 1: Method Category

#### Representation Enhancement
**Definition**: Methods that share a common mechanism under this category
**Papers**: [2401.12345, 2402.23456]

##### Level 2: Submethod

###### Learnable Scaling/Offset
**Definition**: Submethod definition grounded in paper evidence
**Papers**: [2401.12345]
**Key Techniques**: [list concrete techniques from evidence]

###### Rotation/Orthogonal Transform
**Definition**: Methods that apply rotations to weight matrices
**Papers**: [2402.23456]
**Key Techniques**: Hadamard transform, orthogonal matrices

### Level 1: Training Paradigm

#### [Paradigm Name]
**Definition**: Paradigm definition grounded in paper evidence
**Papers**: [2401.12345, 2402.23456, 2403.34567]

...
```

---

*For survey construction workflow, see `/survey-pipeline`*
*For gap identification, see `/gap-identify`*
