---
name: code-discover
description: Discover GitHub repositories associated with survey papers. Use when user says "find code", "discover repos", "find implementations", "code discovery", or needs to find open-source implementations of papers from the survey.
argument-hint: [survey-name-or-path]
allowed-tools: Bash(*), Read, Write, WebFetch, WebSearch, Glob, Grep
---

# Code Discovery

Find code implementations for survey papers: $ARGUMENTS

## Constants

- **MAX_REPOS = 10** — Maximum repos to discover per run
- **TIER_SCOPE = "tier1_tier2"** — Paper tier filter (tier1, tier1_tier2, all)
- **GATE6_DIR** — Output directory (default: `<survey_root>/gate6_code_discovery/`)

> Overrides (append to arguments):
> - `/code-discover "my_survey" - max: 20` — discover up to 20 repos
> - `/code-discover "my_survey" - tier: all` — include all tiers
> - `/code-discover "my_survey" - dir: /custom/path` — custom output dir

## Workflow

### Step 1: Locate Survey Outputs

Find the survey paper list to use as input:

```bash
# Look for paper_list.json in the survey directory
SURVEY_ROOT=$(find surveys/ -maxdepth 1 -name "survey_*" -type d | head -1)
PAPER_LIST="$SURVEY_ROOT/gate1_research_lit/paper_list.json"
```

If `$ARGUMENTS` specifies a survey name, use `surveys/survey_<name>/`.

Verify the paper list exists. If not, suggest running `/survey-pipeline` or `surveymind --stage corpus-extract` first.

### Step 2: Multi-Source Repo Discovery

For each paper in the list (filtered by TIER_SCOPE), search for code repos using cascading sources:

**Source 1 — Paper metadata text:**
Extract GitHub URLs from the paper's abstract and title.

```python
import re
GITHUB_RE = re.compile(r"https?://github\.com/([a-zA-Z0-9\-_.]+/[a-zA-Z0-9\-_.]+)")
```

**Source 2 — Papers With Code API:**
```bash
curl -s "https://paperswithcode.com/api/v1/papers/?arxiv_id=ARXIV_ID" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for paper in data.get('results', []):
    pid = paper['id']
    repos = json.loads(
        __import__('urllib.request', fromlist=['urlopen'])
        .urlopen(f'https://paperswithcode.com/api/v1/papers/{pid}/repositories/')
        .read()
    )
    for r in repos.get('results', []):
        print(f\"{r['url']} stars={r.get('stars',0)} official={r.get('is_official', False)}\")
"
```

**Source 3 — arXiv abstract page:**
Fetch `https://arxiv.org/abs/ARXIV_ID` and extract GitHub links from the HTML.

**Source 4 — PDF text (fallback):**
If PDF is available locally, extract text and search for GitHub URLs.

Rate limit: wait 0.5s between API calls.

### Step 3: Validate and Rank Repos

For each discovered repo URL:

1. Verify the URL is accessible (HTTP 200)
2. Check if README exists
3. Get star count and last update date via GitHub API (if available)
4. Rank by: official > high stars > recent update

### Step 4: Generate Output

Write `code_repos.json`:

```json
[{
  "paper_id": "2301.07041",
  "title": "Paper Title",
  "repo_url": "https://github.com/org/repo",
  "repo_source": "paperswithcode_official",
  "stars": 1234,
  "last_updated": "2025-12-01",
  "has_readme": true,
  "priority": "tier1"
}]
```

Write `discovery_report.md` with a summary table.

### Step 5: Report Results

```text
Code Discovery Complete:
- Papers scanned: N
- Repos found: M
- Output: <gate6_dir>/code_repos.json

Suggested next steps:
/repo-setup "<survey-name>" — Clone repos and generate setup plans
```

## Key Rules

- Never clone repos in this step — only discover and validate URLs
- Rate limit all API calls (0.5s between requests)
- Skip papers that already have a repo entry in code_repos.json (idempotent)
- If Papers With Code API is unavailable, continue with other sources
- Prefer official repos (is_official=true) over community forks
- Report both found and not-found papers in the discovery report
- Handle both arXiv ID formats: `2301.07041` and `cs/0601001`
