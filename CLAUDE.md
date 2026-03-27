# SurveyMind

Automated survey construction pipeline for academic research.

## Pipeline Status

```yaml
stage: survey-pipeline
topic: "Ultra-Low Bit Quantization for Large Language Models"
pipeline_status:
  gate0_scope: complete       # SURVEY_SCOPE.md exists
  gate1_research_lit: complete   # paper_list.json (24 papers)
  gate2_paper_analysis: complete # paper_analysis_results/ (24 analyses)
  gate3_taxonomy: complete        # taxonomy.md (275 lines)
  gate4_gap_identification: complete # gap_analysis.md (265 lines)
  gate5_survey_write: complete     # SURVEY_DRAFT.md regenerated
papers_analyzed: 24
next: Review SURVEY_DRAFT.md for completeness and target venue customization
```

## Survey Pipeline Flow

```
/survey-pipeline "research topic"
       ↓
research-lit → paper-analysis → taxonomy-build → gap-identify → survey-write
       ↓              ↓                ↓              ↓              ↓
  paper_list.json  paper_analysis/    taxonomy.md   gap_analysis.md  SURVEY_DRAFT.md
```

**Key constant**: `AUTO_PROCEED = true` (set to false to pause at gates)

## Reading Order for Session Recovery

1. **CLAUDE.md** (this file) → Pipeline Status (30-second orientation)
2. **WORKLOG.md** → Phase-by-phase execution log with timestamps
3. **findings.md** → Recent discoveries and gate summaries (if exists)
4. **paper_analysis_results/*.md** → Individual paper analyses
5. **taxonomy.md** → Current taxonomy structure (if exists)
6. **gap_analysis.md** → Identified gaps (if exists)

## File Organization

| Path | Purpose |
|------|---------|
| `paper_analysis_results/` | 8-field paper analyses (per paper) |
| `my idea/survey_trace/` | Survey manuscript structure with evidence |
| `papers/` | Downloaded PDF papers |
| `skills/` | Skill definitions (do not modify) |
| `tools/` | Utility scripts (do not modify) |
| `templates/` | Output templates |
| `validation/` | Validation rules and reports |

## State Persistence Rules

### Pipeline Status update triggers:
- Stage transitions (gate 1→2→3→4→5)
- Paper count confirmed
- Taxonomy structure finalized
- Gap analysis complete
- User says "save" / "record" / "new session"

### On new session or post-compaction recovery:
1. Read `## Pipeline Status` in CLAUDE.md
2. Read WORKLOG.md for phase details
3. Read findings.md for recent progress (if exists)
4. Resume work without asking the user

### At each pipeline gate, agent must:
- Report completion status
- Append one-line summary to findings.md
- Automatically proceed if `AUTO_PROCEED=true`

## Skills

| Command | Description |
|---------|-------------|
| `/survey-pipeline "topic"` | Full pipeline: research → analysis → taxonomy → gaps → survey |
| `/paper-analysis "topic"` | Analyze papers from paper_list.json |
| `/taxonomy-build "topic"` | Build taxonomy from paper analyses |
| `/gap-identify "topic"` | Identify gaps from taxonomy |
| `/survey-write "topic"` | Write survey from taxonomy + gaps |

## Validation

SurveyMind uses `validation/policy.json` to restrict agent file operations:

- **Allowed**: `paper_analysis_results/**`, `my idea/**`, `WORKLOG.md`, `taxonomy.md`, `gap_analysis.md`, `SURVEY_DRAFT.md`, etc.
- **Protected (do not modify)**: `tools/**`, `skills/**`, `templates/**`, `mcp-servers/**`, `install.sh`, `README.md`

## Key Rules

- **Sequential execution**: Each stage depends on the previous
- **Auto-proceed by default**: When `AUTO_PROCEED=true`, automatically continue through gates
- **Evidence binding**: All survey claims must be traceable to paper analyses
- **Machine-readable outputs**: All intermediate files must be parseable by downstream stages
