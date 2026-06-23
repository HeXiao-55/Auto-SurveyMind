---
name: repo-reproduce
description: Execute reproduction plans for cloned paper repos — install deps, run demos, validate output. Use when user says "reproduce", "run demo", "test repo", "verify implementation", or needs to validate that a paper's code works.
argument-hint: [survey-name-or-paper-id]
allowed-tools: Bash(*), Read, Write, Grep, Glob, Agent
---

# Repo Reproduce

Execute reproduction for paper implementations: $ARGUMENTS

## Constants

- **MAX_ATTEMPTS = 3** — Max retry attempts per repo on failure
- **STEP_TIMEOUT = 300** — Timeout per setup step (seconds)
- **DEMO_TIMEOUT = 600** — Timeout per demo command (seconds)
- **SKIP_GPU = false** — Skip repos that require GPU (set true on CPU-only machines)

> Overrides:
> - `/repo-reproduce "my_survey" - attempts: 5` — more retries
> - `/repo-reproduce "2301.07041"` — reproduce a specific paper only
> - `/repo-reproduce "my_survey" - skip-gpu: true` — skip GPU-requiring repos

## Workflow

### Step 1: Load Setup Plans

```bash
GATE7_DIR="<survey_root>/gate7_reproduction"
SETUPS_DIR="$GATE7_DIR/setups"
ls "$SETUPS_DIR"/*_setup.json
```

If a specific paper_id is provided in `$ARGUMENTS`, filter to that plan only.

### Step 2: Environment Setup

For each repo setup plan:

**Conda environment:**
```bash
cd <repo_path>
conda env create -f environment.yml -n "repro_<paper_id>"
conda activate "repro_<paper_id>"
```

**Pip virtual environment:**
```bash
cd <repo_path>
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Docker:**
```bash
cd <repo_path>
docker build -t "repro_<paper_id>" .
```

Check each step's exit code. On failure, attempt common fixes:
- `pip install --upgrade pip` then retry
- Remove version pins that cause conflicts
- Install missing system dependencies

### Step 3: Run Demo Commands

Execute demo commands from the setup plan:

```bash
cd <repo_path>
# Activate environment first
<demo_command>
```

Validate success:
1. Exit code == 0
2. Check for expected output files (if mentioned in README)
3. No Python tracebacks in stderr

### Step 4: Error Recovery (on failure)

If demo fails, attempt intelligent recovery (up to MAX_ATTEMPTS):

1. **Read error message** — identify the root cause
2. **Common fixes:**
   - Missing dependency → `pip install <package>`
   - Version conflict → try compatible version
   - Missing data file → check if download step was skipped
   - CUDA version mismatch → try CPU mode if available (`--device cpu`)
   - Import error → check if package was renamed or restructured
3. **Re-run demo** after fix

If all attempts fail, log the error details for manual review.

### Step 5: Record Results

Update `reproduction_log.json`:

```json
{
  "paper_id": "2301.07041",
  "status": "demo_passed",
  "attempts": 1,
  "steps_results": [...],
  "demo_results": [{
    "cmd": "python demo.py",
    "exit_code": 0,
    "elapsed_s": 12.5,
    "success": true
  }],
  "attempted_at": "2025-06-23T10:30:00"
}
```

Status values: `demo_passed`, `setup_ok_no_demo`, `demo_failed`, `setup_failed`, `error`

### Step 6: Summary Report

```text
Reproduction Results:
- Demo passed: N repos (ready for adaptation)
- Setup OK (no demo available): M repos
- Failed: K repos (see reproduction_log.json for details)

Successfully reproduced:
- [paper_id_1] repo_name — "python demo.py" passed in 12.5s
- [paper_id_2] repo_name — "bash run_example.sh" passed in 45.2s

Suggested next steps:
/repo-adapt "<survey-name>" — Adapt successful reproductions for your task
```

## Key Rules

- ALWAYS activate the correct environment before running commands
- NEVER run commands as root or with sudo
- Set timeouts for every command — kill hung processes
- Each repo's environment MUST be isolated (conda env or venv per repo)
- On failure, try up to MAX_ATTEMPTS with different fixes before giving up
- Log ALL outputs (stdout, stderr, exit codes) for debugging
- If SKIP_GPU is true, skip repos where `gpu_required: true`
- Do not modify the original repo code during reproduction (work on understanding, not changing)
- If a repo requires a large dataset download (>5GB), ask the user before proceeding
- Report both successes and failures with actionable error messages
