#!/usr/bin/env python3
"""Broad arXiv discovery for SurveyMind gate1 research stage.

This stage runs right after scope confirmation. It performs high-recall arXiv
retrieval, deduplicates results by arXiv ID, and writes canonical
`arxiv_results.json` for downstream corpus extraction and triage.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from arxiv_fetch import search


def _parse_keywords(value: str) -> list[str]:
	return [x.strip() for x in value.split(",") if x.strip()]


def _load_scope_terms(scope_file: str | None) -> list[str]:
	if not scope_file:
		return []
	path = Path(scope_file)
	if not path.exists():
		return []
	text = path.read_text(encoding="utf-8", errors="ignore")
	terms = []
	for line in text.splitlines():
		if line.lower().startswith("**refined topic**:"):
			topic = line.split(":", 1)[1].strip()
			if topic:
				terms.append(topic)
		if "**primary**:" in line.lower() or "**secondary**:" in line.lower():
			item = line.split(":", 1)[1].strip()
			if item:
				terms.extend([x.strip() for x in item.split(",") if x.strip()])
	return terms


def _build_queries(
	topic_keywords: list[str],
	scope_terms: list[str],
	max_queries: int,
	discover_queries: str | None,
) -> list[str]:
	if discover_queries:
		queries = [q.strip() for q in discover_queries.split(";") if q.strip()]
		return queries[:max_queries]

	seeds: list[str] = []
	for term in scope_terms + topic_keywords:
		if term and term not in seeds:
			seeds.append(term)

	default_high_recall = [
		"large language model quantization",
		"ultra-low bit LLM",
		"1-bit LLM",
		"ternary LLM",
		"low-bit transformer",
	]
	for q in default_high_recall:
		if q not in seeds:
			seeds.append(q)

	return seeds[:max_queries]


def _dedup(records: list[dict]) -> list[dict]:
	seen = set()
	out = []
	for rec in records:
		rid = str(rec.get("id", "")).strip()
		if not rid or rid in seen:
			continue
		seen.add(rid)
		out.append(
			{
				"id": rid,
				"title": rec.get("title", ""),
				"published": rec.get("published", ""),
				"authors": rec.get("authors", []),
				"categories": rec.get("categories", []),
				"query_hit": rec.get("query_hit", []),
			}
		)
	return out


def run_discovery(
	queries: list[str],
	max_per_query: int,
	page_size: int,
	delay: float,
) -> list[dict]:
	merged: list[dict] = []
	for query in queries:
		got = 0
		start = 0
		while got < max_per_query:
			batch = min(page_size, max_per_query - got)
			results = search(query, max_results=batch, start=start)
			if not results:
				break
			for item in results:
				item["query_hit"] = [query]
				merged.append(item)
			got += len(results)
			start += len(results)
			if len(results) < batch:
				break
			time.sleep(delay)
	return merged


def _merge_query_hits(records: list[dict]) -> list[dict]:
	by_id: dict[str, dict] = {}
	for rec in records:
		rid = str(rec.get("id", "")).strip()
		if not rid:
			continue
		if rid not in by_id:
			by_id[rid] = rec
			by_id[rid]["query_hit"] = list(rec.get("query_hit", []))
			continue
		hits = set(by_id[rid].get("query_hit", []))
		hits.update(rec.get("query_hit", []))
		by_id[rid]["query_hit"] = sorted(hits)
	return list(by_id.values())


def main() -> int:
	ap = argparse.ArgumentParser(description="SurveyMind broad arXiv discovery")
	ap.add_argument("--topic-keywords", required=True, help="Comma-separated keywords")
	ap.add_argument("--scope-file", help="Optional SURVEY_SCOPE.md path")
	ap.add_argument("--discover-queries", help="Optional semicolon-separated custom queries")
	ap.add_argument("--output", required=True, help="Output arxiv_results.json path")
	ap.add_argument("--max-per-query", type=int, default=80)
	ap.add_argument("--page-size", type=int, default=40)
	ap.add_argument("--max-queries", type=int, default=8)
	ap.add_argument("--delay", type=float, default=0.8)
	ap.add_argument(
		"--require-scope",
		action=argparse.BooleanOptionalAction,
		default=True,
		help="Require scope-derived terms (or explicit --discover-queries) before discovery (default: on)",
	)
	args = ap.parse_args()

	topic_keywords = _parse_keywords(args.topic_keywords)
	scope_terms = _load_scope_terms(args.scope_file)
	queries = _build_queries(
		topic_keywords=topic_keywords,
		scope_terms=scope_terms,
		max_queries=args.max_queries,
		discover_queries=args.discover_queries,
	)
	if args.require_scope and not scope_terms and not args.discover_queries:
		print(
			"ERROR: scope terms are empty. Please run brainstorm first to generate SURVEY_SCOPE.md, "
			"or pass --discover-queries explicitly.",
			file=sys.stderr,
		)
		return 1
	if not queries:
		print("ERROR: no discovery queries available", file=sys.stderr)
		return 1

	print("SurveyMind arxiv_discover")
	print(f"  Queries: {len(queries)}")
	for idx, q in enumerate(queries, start=1):
		print(f"    {idx}. {q}")

	merged = run_discovery(
		queries=queries,
		max_per_query=args.max_per_query,
		page_size=args.page_size,
		delay=args.delay,
	)
	merged = _merge_query_hits(merged)
	deduped = _dedup(merged)

	out_path = Path(args.output)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	out_path.write_text(json.dumps(deduped, indent=2, ensure_ascii=False), encoding="utf-8")

	print(f"  Raw hits: {len(merged)}")
	print(f"  Unique papers: {len(deduped)}")
	print(f"  Output: {out_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
