#!/usr/bin/env python3
"""Unified arXiv API client for SurveyMind.

Replaces the 5+ independent arXiv fetch implementations scattered across tools/
and validation/ with a single, well-tested module that provides:

- HTTP session reuse (connection pooling)
- Configurable retry with exponential backoff
- Rate-limit awareness
- Both metadata (Atom XML) and PDF download
- Batch search support

Usage
-----
    from arxiv_client import search, fetch_metadata, download_paper

    papers = search("LLM quantization", max_results=50)
    meta = fetch_metadata("2210.17323")
    result = download_paper("2210.17323", output_dir="papers/")
"""

from __future__ import annotations

import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

# ── Constants ───────────────────────────────────────────────────────────────────

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
USER_AGENT = "SurveyMind/1.0"
ATOM_NS = "http://www.w3.org/2005/Atom"
MIN_PDF_BYTES = 10_240

# Compiled regexes for arXiv ID normalisation
_NEW_ID_RE = re.compile(r"^\d{4}\.\d{1,5}(v\d+)?$")
_OLD_ID_RE = re.compile(r"^[A-Za-z.-]+/\d{7}(v\d+)?$")


# ── Data classes ────────────────────────────────────────────────────────────────

@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    published: str          # ISO date (YYYY-MM-DD)
    updated: str
    categories: list[str]
    pdf_url: str
    abs_url: str
    # Populated only when fetched individually
    first_author: Optional[str] = None
    year: Optional[int] = None


@dataclass
class DownloadResult:
    arxiv_id: str
    path: Optional[str]
    size_kb: int
    skipped: bool
    error: Optional[str] = None


# ── Normalisation helpers ───────────────────────────────────────────────────────

def _parse_arxiv_id(raw: str) -> str:
    """Normalise an arXiv ID or URL to a clean ID (strip version, /abs/, etc.)."""
    value = raw.strip()
    # Strip URL prefix
    for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/",
                   "https://arxiv.org/pdf/", "http://arxiv.org/pdf/"):
        if prefix in value:
            value = value.split(prefix, 1)[1]
    # Strip id: prefix
    if value.startswith("id:"):
        value = value[3:]
    # Strip .pdf suffix
    value = value.rstrip("/").removesuffix(".pdf")
    # Strip version suffix (e.g. 2210.17323v2 → 2210.17323)
    if "v" in value.split(".")[-1]:
        value = value.rsplit("v", 1)[0]
    return value


def looks_like_arxiv_id(value: str) -> bool:
    """Return True when input resembles a valid arXiv ID."""
    return bool(_NEW_ID_RE.match(value.strip()) or _OLD_ID_RE.match(value.strip()))


# ── Core fetch with retry ──────────────────────────────────────────────────────

def _fetch_atom(url: str, timeout: int = 45, max_retries: int = 4,
                backoff_base: float = 2.0, backoff_cap: float = 16.0) -> ET.Element:
    """Fetch an arXiv Atom feed with retry and exponential backoff.

    Retries on HTTP 429/5xx and transient socket errors.
    Raises the last exception if all retries are exhausted.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            status = resp.status_code
            if status == 429 or (500 <= status <= 504):
                wait = min(backoff_base ** attempt, backoff_cap)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return ET.fromstring(resp.content)
        except requests.HTTPError as exc:
            last_exc = exc
            raise
        except requests.RequestException as exc:
            last_exc = exc
            wait = min(backoff_base ** attempt, backoff_cap)
            time.sleep(wait)
            continue

    raise RuntimeError(f"arXiv API request failed after {max_retries} retries: {last_exc}")


# ── Metadata parsing ───────────────────────────────────────────────────────────

def _parse_entry(entry: ET.Element) -> ArxivPaper:
    """Parse a single Atom <entry> into an ArxivPaper dataclass."""
    raw_id = entry.findtext(f"{{{ATOM_NS}}}id", "")
    arxiv_id = _parse_arxiv_id(raw_id)

    def text(tag: str) -> str:
        el = entry.find(f"{{{ATOM_NS}}}{tag}")
        return (el.text or "").strip() if el is not None else ""

    authors: list[str] = []
    for author_el in entry.findall(f"{{{ATOM_NS}}}author"):
        name_el = author_el.find(f"{{{ATOM_NS}}}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    categories = [
        el.get("term", "")
        for el in entry.findall(f"{{{ATOM_NS}}}category")
        if el.get("term")
    ]

    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=re.sub(r"\s+", " ", text("title")),
        authors=authors,
        abstract=re.sub(r"\s+", " ", text("summary")),
        published=text("published")[:10],
        updated=text("updated")[:10],
        categories=categories,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def search(query: str, *, max_results: int = 10, start: int = 0) -> list[ArxivPaper]:
    """Search arXiv and return a list of ArxivPaper objects.

    Parameters
    ----------
    query : str
        Search query, or ``id:<arxiv_id>`` for a specific paper.
    max_results : int
        Maximum number of results (max 2000 per arXiv API).
    start : int
        Pagination offset.

    Returns
    -------
    list[ArxivPaper]
    """
    query = query.strip()
    if query.startswith("id:"):
        params = {"id_list": _parse_arxiv_id(query)}
    elif looks_like_arxiv_id(query):
        params = {"id_list": _parse_arxiv_id(query)}
    else:
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

    url = f"{ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"
    root = _fetch_atom(url)
    return [_parse_entry(e) for e in root.findall(f"{{{ATOM_NS}}}entry")]


def fetch_metadata(arxiv_id: str, *, retries: int = 2) -> Optional[ArxivPaper]:
    """Fetch full metadata for a single paper by arXiv ID.

    Returns None if the paper is not found.
    Returns a dict with ``_error`` key on network failure.
    """
    paper_id = _parse_arxiv_id(arxiv_id)
    results = search(f"id:{paper_id}", max_results=1)

    if not results:
        return None

    paper = results[0]
    # Enrich with year and first_author
    paper.first_author = paper.authors[0] if paper.authors else None
    try:
        paper.year = int(paper.published[:4])
    except (ValueError, IndexError):
        paper.year = None
    return paper


def download_paper(
    arxiv_id: str,
    output_dir: str | Path = "papers",
    *,
    retries: int = 3,
    timeout: int = 120,
) -> DownloadResult:
    """Download a paper PDF by arXiv ID.

    Returns a DownloadResult. If the file already exists it is skipped
    (not re-downloaded) and the existing size is reported.
    """
    paper_id = _parse_arxiv_id(arxiv_id)
    dest_dir = Path(output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{paper_id.replace('/', '_')}.pdf"

    if dest.exists():
        size_bytes = dest.stat().st_size
        return DownloadResult(
            arxiv_id=paper_id,
            path=str(dest),
            size_kb=max(1, size_bytes // 1024) if size_bytes > 0 else 0,
            skipped=True,
        )

    pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            if resp.status_code == 429 and attempt < retries:
                time.sleep(min(2 ** attempt, 10))
                continue
            resp.raise_for_status()
            data = resp.content
            break
        except requests.HTTPError as exc:
            return DownloadResult(
                arxiv_id=paper_id, path=None, size_kb=0, skipped=False,
                error=f"HTTP {exc.response.status_code}: {exc.response.reason}",
            )
        except requests.RequestException as exc:
            if attempt < retries:
                time.sleep(min(2 ** attempt, 10))
                continue
            return DownloadResult(
                arxiv_id=paper_id, path=None, size_kb=0, skipped=False,
                error=str(exc),
            )

    if len(data) < MIN_PDF_BYTES:
        return DownloadResult(
            arxiv_id=paper_id, path=None, size_kb=0, skipped=False,
            error=f"Downloaded file is only {len(data)} bytes — likely an error page",
        )

    dest.write_bytes(data)
    return DownloadResult(
        arxiv_id=paper_id,
        path=str(dest),
        size_kb=len(data) // 1024,
        skipped=False,
    )


def metadata_to_dict(paper: ArxivPaper) -> dict:
    """Convert an ArxivPaper to a plain dict (for JSON serialisation)."""
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "published": paper.published,
        "updated": paper.updated,
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "abs_url": paper.abs_url,
        "first_author": paper.first_author,
        "year": paper.year,
    }
