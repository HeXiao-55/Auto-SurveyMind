"""Code Discovery stage — find GitHub repos associated with survey papers.

Multi-source strategy (cascading, first hit wins):
1. Parse paper metadata (abstract text) for GitHub URLs
2. Query Papers With Code API for official repos
3. Scrape arXiv abstract page for code links
4. Scan local PDF text (if available)
5. GitHub Search API fallback (uses GITHUB_TOKEN if set)

Returns 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

from stages._helpers import TIER_SCOPE_MAP


GITHUB_URL_RE = re.compile(
    r"https?://github\.com/([a-zA-Z0-9\-_.]+/[a-zA-Z0-9\-_.]+)"
)
PAPERSWITHCODE_API = "https://paperswithcode.com/api/v1/papers"


def _http_get_json(url: str, timeout: int = 30) -> Any | None:
    """HTTP GET returning parsed JSON, with optional GitHub token auth."""
    headers: dict[str, str] = {"User-Agent": "SurveyMind-CodeDiscover/1.0"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _http_get_text(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "SurveyMind-CodeDiscover/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_github_urls(text: str) -> list[str]:
    """Extract unique, clean GitHub repo URLs from arbitrary text."""
    matches = GITHUB_URL_RE.findall(text)
    urls: list[str] = []
    seen: set[str] = set()
    for m in matches:
        # Strip sub-paths (/tree/main, /blob/…, trailing slashes)
        clean = m.rstrip("/").split("/tree/")[0].split("/blob/")[0]
        parts = clean.split("/")
        if len(parts) != 2:
            continue
        # Skip obvious non-repos (e.g. github.com/user only)
        if not parts[1]:
            continue
        repo_url = f"https://github.com/{clean}"
        if repo_url.lower() not in seen:
            seen.add(repo_url.lower())
            urls.append(repo_url)
    return urls


def _search_paperswithcode(arxiv_id: str) -> list[dict[str, Any]]:
    """Query Papers With Code API for repos linked to an arXiv paper."""
    url = f"{PAPERSWITHCODE_API}/?arxiv_id={arxiv_id}"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []

    repos: list[dict[str, Any]] = []
    for paper in data.get("results", []):
        pwc_id = paper.get("id")
        if not pwc_id:
            continue
        repo_data = _http_get_json(f"{PAPERSWITHCODE_API}/{pwc_id}/repositories/")
        if not isinstance(repo_data, dict):
            continue
        for r in repo_data.get("results", []):
            if r.get("url"):
                repos.append(
                    {
                        "url": r["url"],
                        "stars": r.get("stars", 0),
                        "framework": r.get("framework", ""),
                        "is_official": r.get("is_official", False),
                    }
                )
    return repos


def _search_arxiv_page(arxiv_id: str) -> list[str]:
    """Scrape arXiv abstract page for embedded GitHub links."""
    html = _http_get_text(f"https://arxiv.org/abs/{arxiv_id}")
    return _extract_github_urls(html) if html else []


def _search_github_api(title: str, arxiv_id: str) -> list[str]:
    """Search GitHub API by paper title + arXiv ID (fallback, rate-limited without token)."""
    # Use a short query: first 8 words of the title
    short_title = " ".join(title.split()[:8])
    q = urllib.parse.quote(f"{short_title} {arxiv_id}")
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page=3"
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return []
    return [item["html_url"] for item in data.get("items", []) if item.get("html_url")]


def _get_github_repo_info(repo_url: str) -> dict[str, Any] | None:
    """Fetch basic GitHub repo metadata (stars, updated date, archived flag)."""
    m = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?$", repo_url)
    if not m:
        return None
    data = _http_get_json(f"https://api.github.com/repos/{m.group(1)}")
    if not isinstance(data, dict):
        return None
    return {
        "stars": data.get("stargazers_count", 0),
        "last_updated": (data.get("pushed_at") or "")[:10],
        "archived": data.get("archived", False),
        "language": data.get("language", ""),
    }


def _discover_repos_for_paper(
    paper: dict[str, Any],
    pdf_dir: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Discover the best code repo for a single paper using cascading sources."""
    arxiv_id = (paper.get("arxiv_id") or paper.get("paper_id") or "").strip()
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")

    if not arxiv_id:
        return None

    # Source 1: metadata text (title + abstract)
    urls_from_text = _extract_github_urls(f"{title} {abstract}")

    # Source 2: Papers With Code API
    pwc_repos: list[dict[str, Any]] = []
    try:
        pwc_repos = _search_paperswithcode(arxiv_id)
        time.sleep(0.5)
    except Exception:
        pass

    # Source 3: arXiv abstract page
    urls_from_arxiv: list[str] = []
    try:
        urls_from_arxiv = _search_arxiv_page(arxiv_id)
        time.sleep(0.3)
    except Exception:
        pass

    # Source 4: local PDF text
    urls_from_pdf: list[str] = []
    if pdf_dir:
        for candidate in [
            pdf_dir / f"{arxiv_id.replace('/', '_')}.pdf",
            pdf_dir / f"{arxiv_id}.pdf",
        ]:
            if candidate.exists():
                try:
                    from stages._helpers import _extract_pdf_text
                    pdf_text = _extract_pdf_text(candidate)
                    if pdf_text:
                        urls_from_pdf = _extract_github_urls(pdf_text)
                except Exception:
                    pass
                break

    # Source 5: GitHub Search API fallback
    urls_from_github_search: list[str] = []

    # --- consolidate: pick best URL with source label ---
    best_url: str | None = None
    source = ""

    for r in pwc_repos:
        if r.get("is_official"):
            best_url = r["url"]
            source = "paperswithcode_official"
            break
    if not best_url and pwc_repos:
        best_url = pwc_repos[0]["url"]
        source = "paperswithcode"
    if not best_url and urls_from_text:
        best_url = urls_from_text[0]
        source = "metadata_text"
    if not best_url and urls_from_arxiv:
        best_url = urls_from_arxiv[0]
        source = "arxiv_page"
    if not best_url and urls_from_pdf:
        best_url = urls_from_pdf[0]
        source = "pdf_text"

    # GitHub Search API as last resort
    if not best_url:
        try:
            urls_from_github_search = _search_github_api(title, arxiv_id)
            time.sleep(1.0)  # conservative rate-limit for unauthenticated
        except Exception:
            pass
        if urls_from_github_search:
            best_url = urls_from_github_search[0]
            source = "github_search"

    if not best_url:
        return None

    # Fetch GitHub metadata (stars, last update)
    stars = 0
    last_updated = ""
    repo_info = _get_github_repo_info(best_url)
    if repo_info:
        stars = repo_info.get("stars", 0)
        last_updated = repo_info.get("last_updated", "")

    # Map paper tier to priority string
    tier = paper.get("tier", "")
    if "Tier 1" in tier:
        priority = "tier1"
    elif "Tier 2" in tier:
        priority = "tier2"
    else:
        priority = "tier3"

    return {
        "paper_id": arxiv_id,
        "title": title,
        "repo_url": best_url,
        "repo_source": source,
        "stars": stars,
        "last_updated": last_updated,
        "has_readme": True,
        "priority": priority,
    }


def run_code_discover(args) -> int:
    """Discover GitHub repos for papers in the survey."""
    gate6_dir = Path(args.gate6_dir)
    gate6_dir.mkdir(parents=True, exist_ok=True)

    paper_list_path = Path(args.paper_list)
    if not paper_list_path.exists():
        print(f"ERROR: paper_list.json not found at {paper_list_path}")
        print("Run corpus-extract or batch-triage first.")
        return 1

    papers_data = json.loads(paper_list_path.read_text(encoding="utf-8"))
    all_papers = papers_data.get("papers", [])
    if not all_papers:
        print("WARNING: No papers found in paper_list.json")
        return 0

    max_repos = getattr(args, "reproduction_max_repos", 10)
    tier_filter = getattr(args, "code_discover_tier_scope", "tier1_tier2")
    allowed_tiers = TIER_SCOPE_MAP.get(tier_filter, TIER_SCOPE_MAP["all"])

    # Filter papers by tier, then cap candidate scan at 3× max_repos
    filtered: list[dict[str, Any]] = [
        p for p in all_papers
        if not allowed_tiers or any(t in p.get("tier", "") for t in allowed_tiers)
    ]
    if not filtered:
        filtered = all_papers
    filtered = filtered[: max_repos * 3]

    pdf_dir = Path(args.pdf_dir) if getattr(args, "pdf_dir", None) else None
    verbose = getattr(args, "verbose", False)

    print(f"Searching for code repos: {len(filtered)} candidate papers (max={max_repos})")

    discovered: list[dict[str, Any]] = []
    for idx, paper in enumerate(filtered, start=1):
        if len(discovered) >= max_repos:
            break
        if verbose:
            print(f"  [{idx}/{len(filtered)}] {paper.get('title', '')[:60]}")

        result = _discover_repos_for_paper(paper, pdf_dir=pdf_dir, verbose=verbose)
        if result:
            discovered.append(result)
            if verbose:
                print(f"    -> {result['repo_url']}  (via {result['repo_source']})")
        elif verbose:
            print("    -> no repo found")

    # Sort: tier1 first, then by star count desc
    priority_order = {"tier1": 0, "tier2": 1, "tier3": 2}
    discovered.sort(key=lambda x: (priority_order.get(x["priority"], 9), -x["stars"]))

    # Write outputs
    output_json = gate6_dir / "code_repos.json"
    output_json.write_text(
        json.dumps(discovered, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    report_lines = [
        "# Code Discovery Report",
        "",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Tier filter**: {tier_filter}",
        f"- **Papers scanned**: {len(filtered)}",
        f"- **Repos discovered**: {len(discovered)}",
        "",
        "## Discovered Repositories",
        "",
        "| Paper ID | Title | Repo | Source | Stars |",
        "|----------|-------|------|--------|-------|",
    ]
    for r in discovered:
        short_title = r["title"][:50] + "…" if len(r["title"]) > 50 else r["title"]
        repo_slug = r["repo_url"].split("github.com/")[-1]
        report_lines.append(
            f"| {r['paper_id']} | {short_title} | [{repo_slug}]({r['repo_url']}) | {r['repo_source']} | {r['stars']} |"
        )

    not_found = len(filtered) - len(discovered)
    if not_found > 0:
        report_lines += [
            "",
            f"## Papers Without Discoverable Code ({not_found})",
            "",
            "No public repository was found for these papers.",
        ]

    (gate6_dir / "discovery_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )

    print(f"\nCode discovery complete:")
    print(f"  Repos found : {len(discovered)}")
    print(f"  Not found   : {not_found}")
    print(f"  Output      : {output_json}")
    return 0
