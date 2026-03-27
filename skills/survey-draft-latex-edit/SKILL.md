---
name: survey-draft-latex-edit
description: "Edit a LaTeX survey document using an existing survey draft as source-of-truth. Use when user says '根据 draft 改 latex', 'edit latex from survey draft', 'synchronize survey draft to tex', or wants to revise a .tex manuscript based on SURVEY_DRAFT.md."
argument-hint: [survey-draft-path] [latex-file-path]
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(*)
---

# Survey Draft -> LaTeX Edit Skill

Use this skill to update an existing LaTeX survey manuscript according to a generated survey draft.

## Required Inputs

This skill MUST collect and confirm two paths before any edit:

1. **Survey draft path** (Markdown source)
2. **Target LaTeX file path** (file to be edited)

If either path is missing, ask the user explicitly:

- "请提供 survey draft 的文件路径（例如: surveys/survey_xxx/gate5_survey_write/SURVEY_DRAFT.md）"
- "请提供需要编辑的 LaTeX 文件路径（例如: surveys/survey_xxx/gate5_survey_write/literature_review_survey.tex）"

Do not proceed to editing until both paths are confirmed.

## Input Contract

- **$ARGUMENTS**: Should contain two paths: `<draft_path> <latex_path>`
- If arguments are ambiguous, request clarification first.

## Output

- Updated LaTeX file at the provided `latex_path`
- Optional brief change summary (section-level)

## Workflow

### Step 1: Validate Paths

1. Check that `draft_path` exists and is readable.
2. Check that `latex_path` exists and is readable.
3. If any file is missing, stop and request corrected path.

### Step 2: Read and Align Structure

1. Parse the draft headings and major sections.
2. Parse LaTeX section structure (`\\section`, `\\subsection`, `\\subsubsection`).
3. Build a section mapping:
   - exact title match first
   - semantic match second
   - unmatched content should be proposed as insertions

### Step 3: Apply Edits Conservatively

Edit LaTeX with minimal, localized changes:

1. Update section text according to draft content.
2. Preserve existing LaTeX macros, labels, refs, and citation commands.
3. Keep equations, figures, and tables unless draft explicitly requires updates.
4. Do not rewrite unrelated sections.

### Step 4: Maintain Citation Safety

1. Do not fabricate citations.
2. Keep existing `\\cite{...}` keys unless user asks for citation refactor.
3. If draft contains unsupported citation placeholders, keep `TODO-CITATION` markers in LaTeX comments.

### Step 5: Basic Sanity Check

1. Ensure braces and environments are balanced.
2. Ensure no accidental deletion of `\\begin{document}` / `\\end{document}`.
3. Ensure modified sections compile logically as LaTeX text.

## Editing Rules

- Prefer small diffs and section-level replacement over full-file rewrite.
- Preserve original writing style where possible, but prioritize draft-aligned content.
- Keep path-specific operations explicit; never guess file locations.
- If requested changes are too broad, do staged edits and summarize each stage.

## Example Invocation

```text
/survey-draft-latex-edit surveys/survey_ultra_low_bit/gate5_survey_write/SURVEY_DRAFT.md surveys/survey_ultra_low_bit/gate5_survey_write/literature_review_survey.tex
```

If called without arguments, start by asking for the two required paths.

---

This skill is intended for the final writing phase after survey draft generation.
