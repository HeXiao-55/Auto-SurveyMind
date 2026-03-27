---
name: survey-brainstorm
description: "Brainstorming and topic refinement for survey writing. Use when user says 'I want to write a survey on X', 'help me narrow my survey topic', 'what should my survey focus on', or wants to refine a fuzzy research idea into a concrete survey scope before invoking /survey-pipeline."
argument-hint: "fuzzy-research-idea"
---

# Survey Topic Brainstorming & Refinement

Refine a fuzzy research idea into a concrete, focused survey scope. This is **Stage 0** of the survey pipeline — it runs BEFORE `/survey-pipeline` to ensure the survey has a well-defined scope.

## Overview

When a user says "I want to write a survey about X" or "我想写一篇关于X的综述", the topic is often too broad. This skill helps the user and SurveyMind jointly narrow it down through structured exploration and clarification.

## Constants

- **MAX_INITIAL_RESULTS = 15** — Maximum papers to fetch during initial direction exploration
- **ARXIV_SCRIPT** — `tools/arxiv_fetch.py` relative to project root, or inline fallback
- **SURVEY_SCOPE_FILE = `SURVEY_SCOPE.md`** — Output file in project root

## Workflow

### Step 1: Parse User's Fuzzy Idea

Parse `$ARGUMENTS` to extract the raw research interest. If `$ARGUMENTS` is empty or vague (e.g., just "survey" or "写综述"), ask the user to elaborate.

Common patterns:
- `"survey on graph neural network robustness"` → "graph neural network robustness"
- `"我想写关于强化学习安全的文章"` → "强化学习安全"
- `"multimodal reasoning"` → "multimodal reasoning"

### Step 2: Initial Field Exploration (10-15 min)

Quickly scan the landscape to understand what sub-directions exist within the user's broad interest.

**Search arXiv** using `tools/arxiv_fetch.py` with multiple keyword variations:
```bash
python3 tools/arxiv_fetch.py search "<topic primary phrase>" --max 5
python3 tools/arxiv_fetch.py search "<topic primary phrase> methods" --max 5
python3 tools/arxiv_fetch.py search "<topic primary phrase> benchmark" --max 5
python3 tools/arxiv_fetch.py search "<topic primary phrase> survey" --max 5
```

**Web search** for recent surveys and trends:
```bash
# Check if recent surveys already exist on this topic
WebSearch: "<topic> survey 2024 2025 site:arxiv.org OR site:paperswithcode.com"
WebSearch: "<topic> benchmark OR taxonomy"
```

**Build a quick landscape map** (3-5 min):
- What sub-areas exist within this broad topic?
- What key settings/regimes are active in this field?
- What problem variants and data/task types are common?
- What method families and implementation styles dominate?
- Are there already recent surveys on this? How does this differ?

### Step 3: Clarifying Questions (Interactive Dialogue)

Present the landscape map, then ask the user to narrow down through structured questions.
The questions must be generated from the search findings collected in Step 2, not from a fixed domain checklist.

**Present to user:**
```
I found several active sub-directions in this area:
1. Method family A: [examples from retrieved papers]
2. Method family B: [examples from retrieved papers]
3. Evaluation-focused line: [benchmarks/metrics emphasis]
4. System/deployment line: [platform/efficiency emphasis]
5. Domain adaptation line: [task/data/application emphasis]
6. Emerging direction: [new trend from recent papers]

To help define your survey scope, please clarify:
```

**Then ask 5-7 key questions (evidence-driven):**

Question generation rules:
1. Each question must reference at least one concrete finding from Step 2.
2. Prioritize dimensions where the search results show divergence or ambiguity.
3. Avoid pre-baked domain terms unless they actually appeared in the retrieved evidence.
4. Include at least one exclusion question derived from noisy/adjacent topics in results.

Suggested question dimensions (choose 5-7 based on evidence):
- Scope width: narrow vs mid vs broad, tied to observed sub-direction spread.
- Method focus: which method families to include/exclude, tied to dominant clusters.
- Task/entity focus: which datasets, tasks, or application settings to prioritize.
- Evaluation focus: which metrics/benchmarks are most decision-critical.
- System/deployment context: only if retrieval shows clear platform split.
- Time window: whether to emphasize recent trends vs foundational works.
- Output target: venue/style constraints that affect breadth and depth.

Question style template:
"From the papers I found, X and Y are both active but lead to different evaluation protocols.
Do you want the survey to focus on X, Y, or compare both?"

### Step 4: Refine Scope Based on Answers

After user responds, synthesize their answers into a concrete scope grounded in Step 2 evidence.
If answers are vague, ask follow-up questions that explicitly resolve the most ambiguous evidence splits.

Refinement rules:
1. Convert answers into explicit include/exclude boundaries.
2. For each boundary, cite the corresponding evidence signal from retrieval.
3. Resolve conflicts by favoring user intent, then record trade-offs.
4. Produce a final scope statement that is executable by downstream stages.

**Example refinement:**
- User said: "I want to survey graph robustness"
- User answered: "Middle scope, two major method families, benchmark focus, edge deployment, TPAMI"
- Refined: "A survey of robust learning methods for graph neural networks with emphasis on benchmark protocols and deployment-oriented evaluation"

### Step 5: Generate SURVEY_SCOPE.md

Write the refined scope to `SURVEY_SCOPE.md`:

```markdown
# Survey Scope: [Refined Topic Title]

**Original idea**: [User's original fuzzy input]
**Refined by**: SurveyMind + User
**Date**: [timestamp]

## Refined Topic
[Brief, precise description of the survey scope — 2-3 sentences]

## Evidence Snapshot (from Step 2)
- Finding 1: [paper/URL + one-line relevance]
- Finding 2: [paper/URL + one-line relevance]
- Finding 3: [paper/URL + one-line relevance]

## Scope Boundaries (derived from answers + evidence)
- **Include**: [methods/tasks/settings retained]
- **Exclude**: [adjacent topics explicitly out of scope]
- **Rationale**: [why these boundaries are chosen]

## Target Keywords (for arXiv search)
- **Primary**: [main keywords extracted from retained evidence clusters]
- **Secondary**: [supporting keywords from secondary clusters]
- **Excluded terms**: [noise terms identified in retrieval]

## Survey Parameters
| Parameter | Value |
|-----------|-------|
| **Problem scope** | [narrow / medium / broad, per user decision] |
| **Method scope** | [selected method families] |
| **Target entities/tasks** | [selected entities/tasks] |
| **Primary focus** | [algorithm / system / benchmark / theory / mixed] |
| **Deployment** | [if applicable] |
| **Target venue** | [if specified] |
| **Time window** | [if constrained] |

## Anticipated Sections
1. Introduction & Background
2. Taxonomies & Problem Formulation
3. [Section derived from dominant cluster 1]
4. [Section derived from dominant cluster 2]
5. [Evaluation section aligned with selected metrics]
6. [Optional system/deployment section]
7. Comparative Analysis
8. Research Gaps & Future Directions
9. Conclusion

## Exclusion List
| Excluded Area | Reason |
|--------------|--------|
| [Excluded topic from retrieval noise] | Out of current scope |
| [Adjacent but large branch] | Requires separate survey |
| [Non-target setting] | Not aligned with selected evaluation goal |

## Suggested arXiv Search Query Candidates
```
[Query candidate 1 derived from primary keywords]
[Query candidate 2 for recall expansion]
[Optional exclusion-enhanced query]
```

## Next Steps
The refined scope above is ready for `/survey-pipeline`. To proceed:
```
/survey-pipeline "[refined topic]"
```
