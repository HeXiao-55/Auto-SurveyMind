# Survey Mindmap Auto-Generation Guide

This guide explains how to generate a manuscript-level mindmap from the section/subsection trace folders.

## Inputs
- Folder structure in `my idea/survey_trace/`
- TikZ template in `templates/MINDMAP_TIKZ_TEMPLATE.tex`
- Tool script `tools/generate_survey_mindmap.py`

## Commands

1. Generate TeX + node-path mapping

```bash
python3 tools/generate_survey_mindmap.py
```

Outputs:
- `my idea/survey_trace/mindmap/survey_mindmap.tex`
- `my idea/survey_trace/mindmap/survey_mindmap_paths.md`

2. Generate and compile PDF

```bash
python3 tools/generate_survey_mindmap.py --compile
```

Additional output:
- `my idea/survey_trace/mindmap/survey_mindmap.pdf`

3. Export PNG (for slides/docs)

```bash
python3 tools/generate_survey_mindmap.py --compile --png
```

Additional output:
- `my idea/survey_trace/mindmap/survey_mindmap.png`

## Notes
- The script derives hierarchy from folder names and strips numeric prefixes.
- For many sections, node density can be high; adjust spacing in the template:
  - `level 1 concept/.append style`
  - `level 2 concept/.append style`
- If PDF compilation fails, ensure `latexmk` and TikZ packages are installed.
- If PNG export fails, install `poppler` (`pdftoppm`).

## Why this method
- Directly tied to your traceability folder (`survey_trace`), so updates are automatic.
- Produces publication-friendly vector graphics via LaTeX/TikZ.
- Generates node-to-path mapping for exact evidence location during review.

## Alternative (optional)
If layout becomes too crowded, a better automatic layout option is Graphviz (`dot`) with hierarchical or radial graph layout. It is easier for very large graphs, but less aligned with LaTeX-native publication styling than TikZ.
