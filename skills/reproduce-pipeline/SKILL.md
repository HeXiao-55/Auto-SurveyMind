---
name: reproduce-pipeline
description: End-to-end reproduction pipeline — discover code repos, clone, reproduce demos, and optionally adapt for user's task. Use when user says "reproduce pipeline", "replicate papers", "find and run code", "reproduce survey papers", or needs the full automated reproduction workflow.
argument-hint: [survey-name]
allowed-tools: Bash(*), Read, Write, Glob, Grep, WebFetch, WebSearch, Agent, Skill
---

# Reproduce Pipeline

Automated paper reproduction pipeline: $ARGUMENTS

## Constants

- **AUTO_PROCEED = true** — Automatically proceed between gates without user confirmation
- **MAX_REPOS = 5** — Maximum repos to process in one run
- **REPRODUCTION_DIR** — Output root (default: `<survey_root>/gate7_reproduction/`)
- **SKIP_ADAPT = false** — Skip adaptation step (only discover + reproduce)
- **SKIP_GPU = false** — Skip GPU-requiring repos on CPU-only machines
- **TIER_SCOPE = "tier1_tier2"** — Paper tier filter for code discovery

> Overrides:
> - `/reproduce-pipeline "my_survey" - max: 10` — process more repos
> - `/reproduce-pipeline "my_survey" - AUTO_PROCEED: false` — require confirmation at each gate
> - `/reproduce-pipeline "my_survey" - SKIP_ADAPT: true` — stop after reproduction
> - `/reproduce-pipeline "my_survey" - tier: all` — include all paper tiers

## Workflow

### Gate 0: Verify Survey Brain

Check that the survey has the required upstream outputs:

```bash
SURVEY_ROOT="surveys/survey_<name>"
# Required:
ls "$SURVEY_ROOT/gate1_research_lit/paper_list.json"
# Optional (enhances discovery):
ls "$SURVEY_ROOT/gate2_paper_analysis/"
ls "$SURVEY_ROOT/gate3_taxonomy/"
```

If paper_list.json is missing, abort with instructions to run the survey first.

---

### Gate 1: Code Discovery

Invoke `/code-discover "$ARGUMENTS"` or run the CLI stage:

```bash
python3 tools/surveymind_run.py --stage code-discover \
  --survey-name "<name>" \
  --reproduction-max-repos $MAX_REPOS
```

**Checkpoint:** Verify `gate6_code_discovery/code_repos.json` exists and has entries.

If AUTO_PROCEED is false, display the discovery report and ask:
```
Found N repos. Proceed with cloning and reproduction? [Y/n]
```

---

### Gate 2: Repo Setup

Invoke `/repo-setup "$ARGUMENTS"` or run CLI:

```bash
python3 tools/surveymind_run.py --stage repo-setup \
  --survey-name "<name>" \
  --reproduction-max-repos $MAX_REPOS
```

**Checkpoint:** Verify setup plans exist in `gate7_reproduction/setups/`.

If AUTO_PROCEED is false, display setup summaries and ask:
```
Setup plans generated for N repos. Proceed with reproduction? [Y/n]
```

---

### Gate 3: Reproduction

Invoke `/repo-reproduce "$ARGUMENTS"` or run CLI:

```bash
python3 tools/surveymind_run.py --stage repo-reproduce \
  --survey-name "<name>" \
  --reproduction-max-repos $MAX_REPOS
```

**Checkpoint:** Check `reproduction_log.json` for results.

Report reproduction outcomes:
- Which repos had successful demos
- Which repos failed and why
- Which repos need GPU (if SKIP_GPU is true, flag them for later)

---

### Gate 4: Adaptation (optional)

If SKIP_ADAPT is false AND at least one repo has `status: demo_passed`:

For each successfully reproduced repo, invoke `/repo-adapt`:

```
/repo-adapt "<paper_id> - task: <user's task description from SURVEY_SCOPE.md>"
```

The user's task context comes from:
1. `gate0_scope/SURVEY_SCOPE.md` — the survey topic
2. `$ARGUMENTS` — any additional task description provided

---

### Final Report

Generate `gate7_reproduction/pipeline_summary.md`:

```markdown
# Reproduction Pipeline Summary

## Survey: <name>
## Date: <date>

### Results Overview
- Papers scanned: N
- Repos discovered: M
- Repos cloned: K
- Demos passed: P
- Adaptations attempted: A

### Successfully Reproduced
| Paper | Repo | Status | Demo Command |
|-------|------|--------|--------------|
| ... | ... | ... | ... |

### Failed (needs manual attention)
| Paper | Repo | Error Summary |
|-------|------|---------------|
| ... | ... | ... |

### Next Steps
- For failed repos: check reproduction_log.json for error details
- For adapted repos: see adaptation_notes.md
- To reproduce more: increase MAX_REPOS and re-run
```

## Key Rules

- The survey MUST be completed (at least through gate1) before running this pipeline
- Each gate is idempotent — re-running skips already-completed work
- Failures in one repo do NOT abort the pipeline — continue with remaining repos
- AUTO_PROCEED=true is recommended for fully automated runs
- If a repo requires a dataset download >5GB, pause and ask the user
- Total pipeline timeout: respect system limits, report partial progress on interrupt
- All state is persisted to JSON files — pipeline can be resumed after interruption
- Never push changes to remote repos — all work stays local
