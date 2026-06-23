---
name: repo-adapt
description: Adapt successfully reproduced paper implementations for user's own task. Use when user says "adapt method", "use this approach", "apply to my data", "customize implementation", or needs to repurpose a paper's code for their own problem.
argument-hint: [paper-id-and-task-description]
allowed-tools: Bash(*), Read, Write, Grep, Glob, Agent, Skill
---

# Repo Adapt

Adapt a reproduced implementation for your task: $ARGUMENTS

## Constants

- **WORK_ON_BRANCH = true** — Always create a new git branch for adaptations
- **PRESERVE_ORIGINAL = true** — Never modify original code directly

> Overrides:
> - `/repo-adapt "2301.07041 - task: sentiment classification on my dataset"` — specify the target task
> - `/repo-adapt "2301.07041 - data: /path/to/my/data"` — specify your data path

## Workflow

### Step 1: Understand the Method

Read the paper's analysis and the repo's documentation:

1. Read `gate2_paper_analysis/<paper_id>_analysis.md` for method summary
2. Read the repo's README for usage instructions
3. Identify the core method, input/output format, and configuration options
4. Understand what the demo does vs. what the full pipeline does

### Step 2: Analyze Adaptation Points

Identify what needs to change for the user's task:

- **Data format:** Does the user's data match the expected input format?
- **Configuration:** Which config files/arguments control the method behavior?
- **Model:** Is the model pre-trained or needs training? Can it be swapped?
- **Evaluation:** What metrics apply to the user's task?

Create a short adaptation plan:

```markdown
## Adaptation Plan for <paper_id>

**Original task:** <what the paper does>
**Target task:** <what the user wants>

### Changes needed:
1. Data loading: modify `data/loader.py` to read user's format
2. Config: adjust `configs/default.yaml` for new task parameters
3. Evaluation: add metrics relevant to user's task
```

### Step 3: Create Adaptation Branch

```bash
cd <repo_path>
git checkout -b adapt_<task_slug>
```

### Step 4: Make Adaptations

Apply minimal changes to make the method work on the user's task:

1. **Data adapter:** Create/modify data loading to accept user's format
2. **Config changes:** Update configuration for the target task
3. **Minimal code changes:** Only modify what's necessary
4. **Keep it working:** Run the adapted version to verify it executes

### Step 5: Validate Adaptation

Run the adapted pipeline on the user's data:

```bash
cd <repo_path>
# Run with user's data/config
python <script> --config <adapted_config> --data <user_data>
```

Check:
- Execution completes without errors
- Output format is as expected
- Results are reasonable (not NaN, not empty)

### Step 6: Document Changes

Write `adaptation_notes.md` in the reproduction directory:

```markdown
## Adaptation: <paper_id> → <user_task>

### Method Summary
<Brief description of the paper's approach>

### Changes Made
- <file>: <what was changed and why>
- <file>: <what was changed and why>

### How to Run
```bash
<command to run the adapted version>
```

### Results
<Initial results on user's data>

### Limitations
<Known limitations of this adaptation>
```

## Key Rules

- ALWAYS work on a git branch — never modify the main/master branch
- ALWAYS preserve the original code's ability to run its demo unchanged
- Make MINIMAL changes — adapt, don't rewrite
- If the adaptation requires significant code changes, ask the user first
- Document every change with clear rationale
- If the method fundamentally doesn't fit the user's task, say so honestly
- Test the adaptation before declaring success
- If the user's data is too large, work with a small sample first
- Keep the adaptation reproducible — document all steps
