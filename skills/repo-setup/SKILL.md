---
name: repo-setup
description: Clone discovered repos and generate structured setup plans from their documentation. Use when user says "clone repos", "setup repos", "parse readme", "repo setup", or needs to prepare paper implementations for reproduction.
argument-hint: [survey-name-or-path]
allowed-tools: Bash(*), Read, Write, Glob, Grep
---

# Repo Setup

Clone and analyze repositories for reproduction: $ARGUMENTS

## Constants

- **MAX_REPOS = 10** — Maximum repos to process
- **CLONE_TIMEOUT = 120** — Git clone timeout in seconds
- **REPOS_DIR** — Clone destination (default: `<survey_root>/gate7_reproduction/repos/`)
- **SETUPS_DIR** — Setup plans output (default: `<survey_root>/gate7_reproduction/setups/`)

> Overrides:
> - `/repo-setup "my_survey" - max: 5` — process up to 5 repos
> - `/repo-setup "my_survey" - dir: /custom/reproductions/` — custom output path

## Workflow

### Step 1: Load Code Repos List

```bash
GATE6_DIR="<survey_root>/gate6_code_discovery"
CODE_REPOS="$GATE6_DIR/code_repos.json"
```

Verify `code_repos.json` exists. If not, suggest running `/code-discover` first.

### Step 2: Clone Repositories

For each repo in `code_repos.json` (up to MAX_REPOS):

```bash
SAFE_ID=$(echo "$PAPER_ID" | tr '/' '_')
DEST="$REPOS_DIR/$SAFE_ID"

# Shallow clone to save space and time
git clone --depth 1 "$REPO_URL" "$DEST"
```

- Skip if already cloned (`.git` directory exists)
- Report failures but continue with remaining repos
- Use `--depth 1` to minimize disk and network usage

### Step 3: Parse Documentation

For each successfully cloned repo, read and analyze:

1. **README.md** (or README.rst, etc.)
2. **requirements.txt** / **environment.yml** / **pyproject.toml** / **setup.py**
3. **Dockerfile** (if present)
4. **docs/** directory (INSTALL.md, getting_started.md, etc.)

Extract:
- Environment type: conda, pip, docker, npm, cargo, or unknown
- Primary language: python, javascript, rust, etc.
- GPU requirement: scan for CUDA, nvidia, torch.cuda indicators
- Setup commands: env creation, dependency installation
- Data download commands: wget, curl, gdown, huggingface patterns
- Demo/run commands: python scripts, bash scripts in Quick Start/Usage sections

### Step 4: Generate Setup Plans

For each repo, write `<paper_id>_setup.json`:

```json
{
  "paper_id": "2301.07041",
  "repo_url": "https://github.com/org/repo",
  "repo_path": "gate7_reproduction/repos/2301_07041/",
  "language": "python",
  "env_type": "conda",
  "gpu_required": true,
  "has_readme": true,
  "setup_steps": [
    {"step": 1, "type": "env_create", "cmd": "conda env create -f environment.yml"},
    {"step": 2, "type": "install_deps", "cmd": "pip install -r requirements.txt"},
    {"step": 3, "type": "download_data", "cmd": "bash scripts/download_data.sh"}
  ],
  "demo_commands": ["python demo.py --config configs/default.yaml"],
  "estimated_time": "10min"
}
```

### Step 5: Summarize

Update `reproduction_log.json` with clone status and setup plan locations.

Report:
```text
Repo Setup Complete:
- Cloned: N/M repos
- Setup plans generated: N
- GPU required: K repos
- Ready for reproduction

Suggested next steps:
/repo-reproduce "<survey-name>" — Execute setup plans and run demos
```

## Key Rules

- ALWAYS use `--depth 1` for cloning (save disk space and bandwidth)
- NEVER run `sudo` commands — all setup must be user-level
- Isolate environments: each repo gets its own conda env or venv (named after paper_id)
- Skip repos that are already cloned (check for `.git` directory)
- Parse README tolerantly — not all repos have structured docs
- If README is missing, still generate a minimal plan from detected files (requirements.txt, etc.)
- Set clone timeout to avoid hanging on large repos
- Record all failures in the log but do not abort the pipeline
