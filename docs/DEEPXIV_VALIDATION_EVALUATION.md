# DeepXiv Validation, Evaluation, and MCP Integration Draft

## Scope

This report covers:

1. DeepXiv minimum viability validation
2. Side-by-side evaluation against existing `arxiv_client` and `arxiv_fetch`
3. Downstream data-contract compatibility check
4. MCP tool interface draft for DeepXiv
5. Go/No-Go recommendation with phased rollout and rollback

All commands and raw artifacts are stored under `tmp/deepxiv_eval/`.

## 1) Validation Results (DeepXiv CLI)

### Environment

- Python: `3.12.7`
- Installed package: `deepxiv-sdk==0.2.4`
- CLI binary path: `$HOME/Library/Python/3.12/bin/deepxiv`

### Commands executed

- `deepxiv --help`
- `deepxiv search "agent memory" --limit 5 --format json`
- `deepxiv paper 2602.16493 --brief`
- `deepxiv paper 2602.16493 --head`
- `deepxiv paper 2602.16493 --section Experiments`

### Outcome summary

- Success rate: `5/5` (100%)
- Auto-token behavior: first search auto-created token (`/Users/river/.env`) and reported daily limit
- Observed command latency:
  - search: `0.57s`
  - brief: `0.29s`
  - head: `0.29s`
  - section: `0.57s`
- Error types observed in this run: none

## 2) Comparative Evaluation vs Existing arXiv Tools

### Baseline checks

- Existing project baseline command:
  - `make check-arxiv` -> success (`OK: found 1 paper`)

### Comparison setup

Query: `"agent memory"`, limit `5`

Compared sources:

- DeepXiv: `deepxiv search ...`
- Legacy: `python3 tools/arxiv_fetch.py search ...`
- Current core: `tools.arxiv_client.search(...)`

### Quantitative summary

- Result count:
  - DeepXiv: `5`
  - arxiv_fetch: `5`
  - arxiv_client: `5`
- Search latency:
  - DeepXiv: `0.57s`
  - arxiv_fetch: `1.11s`
  - arxiv_client: `0.75s`

### Data-shape and semantic differences


| Dimension                                              | DeepXiv                                   | arxiv_fetch | arxiv_client              |
| ------------------------------------------------------ | ----------------------------------------- | ----------- | ------------------------- |
| Core ID                                                | `id` + `arxiv_id`                         | `id`        | `arxiv_id`                |
| Basic metadata                                         | yes                                       | yes         | yes                       |
| Section-level summary                                  | yes (`sections_text`, `paper --head`)     | no          | no                        |
| Rich ranking fields                                    | yes (`score`, `highlight`, `token_count`) | no          | no                        |
| Deterministic query overlap (same top IDs in this run) | no overlap with arXiv top-5               | n/a         | overlaps with arxiv_fetch |


Notes:

- DeepXiv top-5 and arXiv top-5 were different for the same query in this run.
- This implies DeepXiv should be introduced as an additional provider, not treated as a strict drop-in ranking-equivalent replacement.

## 3) Downstream Contract Compatibility Check

### Files audited

- `tools/arxiv_discover.py`
- `tools/arxiv_json_extractor.py`
- `tools/stages/_helpers.py`
- `tools/stages/survey_synthesis.py`

### Minimal compatible paper record (required for pipeline continuity)

To keep current pipeline behavior stable, adapter output should provide:

- `id` (string, arXiv-style paper id)
- `title` (string)
- `published` (string/date)
- `authors` (list of strings)
- `categories` (list of strings)

Recommended additional fields for better compatibility:

- `arxiv_id` (same as `id` during transition)
- `abstract`
- `pdf_url`
- `query_hit` (for discovery merge auditability)

### Alias strategy

The current code uses multiple ID keys in different paths:

- `id`
- `arxiv_id`
- `arXiv_id` (in paper list paths)

Adapter rule:

- Always emit both `id` and `arxiv_id` for discovery/search outputs.
- If generating `paper_list.json`, emit `arXiv_id` too.

### Identified integration risk points

- `tools/stages/_helpers.py` still uses `arxiv_fetch.download` directly.
- `tools/stages/survey_synthesis.py` (`run_validate_and_improve`) manually calls arXiv API and `arxiv_fetch.py`.
- These paths bypass `arxiv_client` abstraction; provider-level migration requires refactoring these call sites to a single provider abstraction.

## 4) DeepXiv MCP Tool Design Draft

Target path:

- `mcp-servers/deepxiv/server.py`

### Proposed tool set

1. `search_papers`
  - Input:
    - `query` (string, required)
    - `limit` (int, default 20)
    - `date_from` (string, optional)
    - `format` (`json`/`markdown`, default `json`)
  - Output:
    - `results` list in normalized schema (see below)
    - `total` (int)
2. `get_paper`
  - Input:
    - `paper_id` (string, required)
    - `mode` (`brief`/`head`/`section`, default `brief`)
    - `section` (string, required only when mode is `section`)
  - Output:
    - normalized paper payload
    - optional section payload depending on mode
3. `download_pdf`
  - Input:
    - `paper_id` (string, required)
    - `output_dir` (string, required)
  - Output:
    - `arxiv_id`
    - `path`
    - `size_kb`
    - `skipped` (bool)
    - `error` (optional)

### Normalized output schema (pipeline-compatible)

```json
{
  "id": "2602.16493",
  "arxiv_id": "2602.16493",
  "title": "MMA: Multimodal Memory Agent",
  "authors": ["Yihao Lu", "Wanru Cheng"],
  "abstract": "...",
  "published": "2026-02-18",
  "categories": ["cs.CV"],
  "pdf_url": "https://arxiv.org/pdf/2602.16493",
  "abs_url": "https://arxiv.org/abs/2602.16493",
  "query_hit": ["agent memory"]
}
```

Provider-specific rich fields may be included under:

- `provider_meta` (object), to avoid polluting core contract.

## 5) Go/No-Go and Rollout Recommendation

## Go/No-Go

- **Go (conditional)** for introducing DeepXiv as an additional provider via MCP.
- **No-Go** for immediate hard replacement of arXiv provider in all stages.

Rationale:

- DeepXiv is operational and returns richer, agent-friendly structures.
- Ranking/recall semantics differ from current arXiv path.
- Existing pipeline still has legacy direct `arxiv_fetch` call sites.

## Phased rollout

1. **Phase A (low risk, recommended now)**
  - Add DeepXiv MCP server and adapter only.
  - Do not change default `surveymind_run` provider.
  - Run parallel evaluation on selected topics.
2. **Phase B (optional)**
  - Add provider switch in `arxiv_client` abstraction.
  - Keep output schema stable and backward-compatible.
3. **Phase C (optional)**
  - Refactor legacy direct calls (`_helpers.py`, `survey_synthesis.py`) to provider-agnostic API.
  - Deprecate direct `arxiv_fetch` usage.

## Rollback plan

- If DeepXiv path degrades quality/stability:
  - Disable DeepXiv MCP from client config.
  - Keep `surveymind_run` defaulting to current arXiv chain.
  - Preserve all output contracts (`id`, `arxiv_id`, etc.) to prevent downstream breakage.

## Deliverables generated in this run

- Raw validation outputs:
  - `tmp/deepxiv_eval/01_help.txt`
  - `tmp/deepxiv_eval/02_search.json`
  - `tmp/deepxiv_eval/03_brief.txt`
  - `tmp/deepxiv_eval/04_head.txt`
  - `tmp/deepxiv_eval/05_section.txt`
- Timing logs:
  - `tmp/deepxiv_eval/02_search.time`
  - `tmp/deepxiv_eval/03_brief.time`
  - `tmp/deepxiv_eval/04_head.time`
  - `tmp/deepxiv_eval/05_section.time`
  - `tmp/deepxiv_eval/11_arxiv_fetch_search.time`
  - `tmp/deepxiv_eval/12_arxiv_client_search.time`
- Comparison summary:
  - `tmp/deepxiv_eval/20_comparison_summary.json`

