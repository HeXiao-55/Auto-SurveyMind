#!/usr/bin/env python3
"""
paper_triage.py — SurveyMind Single-Paper 12-Field Triage + Routing

Given an arXiv ID, fetches metadata (title, abstract, categories) via the
arXiv API, performs 12-field classification, and outputs the recommended
survey_trace subsection path — all without requiring a local PDF.

Designed to be reusable for ANY survey topic — routing rules are
parameterised via --routing-config or built-in defaults.

Usage
-----
    # Triage a single paper
    python3 tools/paper_triage.py 2210.17323

    # With custom routing rules
    python3 tools/paper_triage.py 2210.17323 --routing-config my_routing.json

    # With verbose output
    python3 tools/paper_triage.py 2210.17323 --verbose

    # JSON output (machine-readable)
    python3 tools/paper_triage.py 2210.17323 --format json

    # Batch mode: multiple IDs
    python3 tools/paper_triage.py 2210.17323 2211.10438 2306.00978

Exit codes
    0  success
    1  arXiv ID not found / API error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Optional

from domain_profile import (
    DomainProfileError,
    load_domain_profile,
    profile_context_keywords,
    profile_core_keywords,
    profile_keywords,
    profile_routing_fallback,
    profile_routing_rules,
)

# ─── arXiv API ────────────────────────────────────────────────────────────────

ARXIV_API = "http://export.arxiv.org/api/query"
USER_AGENT = "SurveyMind-paper-triage/1.0"
_ATOM_NS = "http://www.w3.org/2005/Atom"


def fetch_arxiv_metadata(arxiv_id: str, retries: int = 2) -> Optional[dict]:
    """Fetch title, abstract, authors, categories, published from arXiv API."""
    query = f"id:{arxiv_id}"
    url = f"{ARXIV_API}?search_query={urllib.parse.quote(query)}&max_results=1"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_text = resp.read().decode("utf-8")
            root = ET.fromstring(xml_text)
            entry = root.find(f"{{{_ATOM_NS}}}entry")
            if entry is None:
                return None
            authors = [
                a.findtext(f"{{{_ATOM_NS}}}name", "")
                for a in entry.findall(f"{{{_ATOM_NS}}}author")
            ]
            categories = [
                c.get("term", "")
                for c in entry.findall(f"{{{_ATOM_NS}}}category")
            ]
            summary_el = entry.find(f"{{{_ATOM_NS}}}summary")
            abstract = summary_el.text.strip() if summary_el is not None else ""
            published_el = entry.find(f"{{{_ATOM_NS}}}published")
            published = published_el.text[:7] if published_el is not None else ""
            title_el = entry.find(f"{{{_ATOM_NS}}}title")
            title = title_el.text.strip() if title_el is not None else ""
            pdf_link_el = entry.find(f"{{{_ATOM_NS}}}link[@title='pdf']")
            pdf_url = pdf_link_el.get("href", "") if pdf_link_el is not None else ""
            return {
                "arxiv_id": arxiv_id,
                "title": re.sub(r"\s+", " ", title),
                "abstract": re.sub(r"\s+", " ", abstract),
                "authors": authors,
                "categories": categories,
                "published": published,
                "pdf_url": pdf_url,
            }
        except Exception as exc:
            if attempt < retries:
                time.sleep(2 ** attempt)
            else:
                return {"_error": str(exc)}
    return None


# ─── Relevance scoring ────────────────────────────────────────────────────────

DEFAULT_KEYWORDS = ["survey", "review", "benchmark", "evaluation", "method", "model"]


def compute_relevance_score(
    title: str,
    abstract: str = "",
    categories: list[str] = None,
    keywords: list[str] = None,
    core_keywords: list[str] = None,
    context_keywords: list[str] = None,
) -> tuple[int, list[str]]:
    """Score 0–3. Returns (score, matched_keywords)."""
    categories = categories or []
    keywords = keywords or DEFAULT_KEYWORDS
    core_keywords = core_keywords or []
    context_keywords = context_keywords or []
    text = (title + " " + (abstract or "")).lower()

    matched = [kw for kw in keywords if kw.lower() in text]

    if core_keywords or context_keywords:
        core_hits = [kw for kw in core_keywords if kw.lower() in text]
        context_hits = [kw for kw in context_keywords if kw.lower() in text]
        if core_hits and context_hits:
            return 3, matched
        if core_hits or len(context_hits) >= 2:
            return 2, matched
        if matched:
            return 1, matched
        return 0, []

    if len(matched) >= 3:
        return 3, matched
    if len(matched) >= 2:
        return 2, matched
    if matched:
        return 1, matched
    return 0, []


# ─── 12-field classification ─────────────────────────────────────────────────

def classify_12field(
    meta: dict,
    keywords: list[str],
    core_keywords: list[str] | None = None,
    context_keywords: list[str] | None = None,
) -> dict:
    """
    Perform 12-field classification from arXiv metadata (no PDF needed).

    Returns a dict with all 12 classification fields + subsection routing.
    """
    text = (meta.get("title", "") + " " + meta.get("abstract", "")).lower()
    score, matched_kws = compute_relevance_score(
        title=meta.get("title", ""),
        abstract=meta.get("abstract", ""),
        categories=meta.get("categories", []),
        keywords=keywords,
        core_keywords=core_keywords,
        context_keywords=context_keywords,
    )

    fields = {}

    # Field 1: Model Type
    if any(k in text for k in ["llm", "large language model", "gpt", "bert", "lama", "llama"]):
        fields["model_type"] = "LLM"
    elif any(k in text for k in ["vision", "vlm", "multimodal", "image", "vlm"]):
        fields["model_type"] = "VLM / Multimodal"
    elif any(k in text for k in ["vit", "transformer", "encoder", "decoder"]):
        fields["model_type"] = "Transformer"
    else:
        fields["model_type"] = "Neural Network (unspecified)"

    # Field 2: Method Category
    if any(k in text for k in ["binary", "1-bit", "binariz"]):
        fields["method_category"] = "Binarization"
    elif any(k in text for k in ["ternary", "1.58", "ternariz"]):
        fields["method_category"] = "Ternarization"
    elif any(k in text for k in ["outlier", "smoothquant", "quarot", "quip"]):
        fields["method_category"] = "Outlier-Aware Quantization"
    elif any(k in text for k in ["pruning", "sparse", "mask"]):
        fields["method_category"] = "Pruning / Sparse"
    elif any(k in text for k in ["quarot", "hadamard rotation", "orthogonal transform", "random rotation"]):
        fields["method_category"] = "Rotation / Transform"
    elif any(k in text for k in ["reconstruction", "calibrate", "optimize weight", "per-channel", "per-token"]):
        fields["method_category"] = "Reconstruction-based"
    else:
        fields["method_category"] = "Standard Quantization"

    # Field 3: Specific Method
    if "awq" in text:
        fields["specific_method"] = "AWQ"
    elif "gptq" in text:
        fields["specific_method"] = "GPTQ"
    elif "spqr" in text:
        fields["specific_method"] = "SpQR"
    elif "quip" in text:
        fields["specific_method"] = "QuIP"
    elif "quarot" in text:
        fields["specific_method"] = "QuaRot"
    elif "smoothquant" in text:
        fields["specific_method"] = "SmoothQuant"
    elif "bitnet" in text:
        fields["specific_method"] = "BitNet"
    elif "ternaryllm" in text:
        fields["specific_method"] = "TernaryLLM"
    elif "ptq" in text:
        fields["specific_method"] = "PTQ (generic)"
    elif "qat" in text:
        fields["specific_method"] = "QAT (generic)"
    else:
        fields["specific_method"] = "[inferred from abstract]"

    # Field 4: Training Paradigm
    if any(k in text for k in ["post-training", "ptq", "post training", "pretrained"]):
        fields["training"] = "PTQ (Post-Training Quantization)"
    elif any(k in text for k in ["qat", "quantization-aware", "aware training"]):
        fields["training"] = "QAT (Quantization-Aware Training)"
    elif any(k in text for k in ["from scratch", "train from scratch", "from-scratch"]):
        fields["training"] = "From-Scratch Training"
    else:
        fields["training"] = "Unspecified"

    # Field 5: Core Challenge
    if any(k in text for k in ["outlier", "activation outlier"]):
        fields["core_challenge"] = "Outlier Handling"
    elif any(k in text for k in ["memory", "storage"]):
        fields["core_challenge"] = "Memory / Storage Reduction"
    elif any(k in text for k in ["latency", "speedup", "throughput"]):
        fields["core_challenge"] = "Inference Speed / Throughput"
    elif any(k in text for k in ["accuracy", "performance degradation", "loss"]):
        fields["core_challenge"] = "Accuracy Preservation"
    elif any(k in text for k in ["hardware", "asic", "cpu", "gpu", "edge"]):
        fields["core_challenge"] = "Hardware Deployment"
    else:
        fields["core_challenge"] = "General Quantization Quality"

    # Field 6: Evaluation Focus
    if any(k in text for k in ["perplexity"]):
        fields["evaluation"] = "Perplexity (language modeling)"
    elif any(k in text for k in ["accuracy", "classification", "benchmark"]):
        fields["evaluation"] = "Downstream Task Accuracy"
    elif any(k in text for k in ["throughput", "latency", "speedup"]):
        fields["evaluation"] = "Inference Speed / Throughput"
    elif any(k in text for k in ["memory", "storage"]):
        fields["evaluation"] = "Memory / Storage Reduction"
    else:
        fields["evaluation"] = "Multiple metrics"

    # Field 7: Hardware Co-design
    if any(k in text for k in ["cpu", "gpu", "cuda"]):
        fields["hardware"] = "GPU / CUDA"
    elif any(k in text for k in ["asic", "fpga", "hardware accelerator"]):
        fields["hardware"] = "ASIC / FPGA"
    elif any(k in text for k in ["cim", "compute-in-memory", "pim"]):
        fields["hardware"] = "CIM / Compute-in-Memory"
    elif any(k in text for k in ["edge", "mobile", "iot"]):
        fields["hardware"] = "Edge / Mobile"
    else:
        fields["hardware"] = "Not specified"

    # Field 8: Summary
    fields["summary"] = meta.get("abstract", "")[:300]

    # Field 9: Quantization Bit Scope (inferred) — use word boundaries
    import re as _re
    def _has(text: str, word: str) -> bool:
        return bool(_re.search(r'\b' + _re.escape(word) + r'\b', text))

    if _has(text, "1-bit") or _has(text, "binary") and not _has(text, "ternary"):
        fields["bit_scope"] = "1-bit"
    elif _has(text, "1.58") or _has(text, "ternary") and not _has(text, "bitnet"):
        fields["bit_scope"] = "1.58-bit (ternary)"
    elif _has(text, "2-bit") or "2bit" in text:
        fields["bit_scope"] = "2-bit"
    elif _has(text, "3-bit"):
        fields["bit_scope"] = "3-bit"
    elif _has(text, "4-bit") and "mixed" not in text:
        fields["bit_scope"] = "4-bit"
    elif "mixed" in text or "mixed-precision" in text:
        fields["bit_scope"] = "Mixed (2-4-bit)"
    elif any(k in text for k in ["ultra-low", "sub-2", "sub-bit"]):
        fields["bit_scope"] = "Sub-4-bit"
    else:
        fields["bit_scope"] = "Not specified"

    # Field 10: General Method Type
    if any(k in text for k in ["outlier", "smoothquant", "quarot", "quip"]):
        fields["general_method"] = "Outlier-Aware"
    elif any(k in text for k in ["reconstruction", "calibrate", "optimize weight"]):
        fields["general_method"] = "Reconstruction-based"
    elif any(k in text for k in ["rotation", "orthogonal", "hadamard"]):
        fields["general_method"] = "Rotation / Transform"
    elif any(k in text for k in ["pruning", "sparse", "mask"]):
        fields["general_method"] = "Sparse / Masking"
    elif any(k in text for k in ["knowledge distillation", "kd", "distillation"]):
        fields["general_method"] = "Knowledge Distillation"
    else:
        fields["general_method"] = "Standard Quantization"

    # Field 11: Core Challenge Addressed
    fields["core_challenge_addressed"] = fields["core_challenge"]

    # Field 12: Survey Contribution Mapping
    fields["survey_contribution"] = "[needs full PDF analysis]"

    # Relevance
    fields["relevance_score"] = score
    fields["relevance_tier"] = (
        "Tier 1 – Core" if score >= 3 else
        "Tier 2 – High Relevance" if score == 2 else
        "Tier 3 – Related" if score == 1 else
        "Tier 4 – Peripheral"
    )
    fields["matched_keywords"] = matched_kws[:10]

    return fields


# ─── Routing ─────────────────────────────────────────────────────────────────

DEFAULT_ROUTING_RULES: list[dict] = [
    {"training": ["QAT", "From-Scratch"], "method": ["Binary", "binarization", "1-bit"], "bits": ["1-bit"],
     "subsection": "05/01_method_training_strategies"},
    {"training": ["QAT", "From-Scratch"], "method": ["Ternary", "ternarization", "1.58-bit"], "bits": ["1.58-bit", "ternary"],
     "subsection": "05/02_method_variants"},
    {"training": ["PTQ"], "method": ["reconstruction", "calibrate", "layer-wise", "rotation"], "bits": [],
     "subsection": "06/01_post_training_methods"},
    {"training": ["PTQ"], "method": ["mixed-precision", "4-bit", "3-bit", "2-bit"], "bits": ["2-bit", "3-bit", "4-bit"],
     "subsection": "06/02_precision_design_space"},
    {"training": [], "method": ["outlier", "normalization", "stability", "generalization"], "bits": [],
     "subsection": "07/01_stability_and_generalization"},
    {"training": [], "method": ["CPU", "GPU", "ASIC", "FPGA", "hardware", "kernel", "throughput"], "bits": [],
     "subsection": "08/01_system_and_hardware"},
    {"training": [], "method": ["multimodal", "vision", "language", "agent"], "bits": [],
     "subsection": "11/01_cross_domain_applications"},
    {"training": [], "method": ["benchmark", "accuracy", "latency", "memory", "energy", "efficiency"], "bits": [],
     "subsection": "09/01_evaluation_protocols"},
    {"training": [], "method": ["gap", "limitation", "challenge", "open problem"], "bits": [],
     "subsection": "10/01_open_challenges"},
]


def route_paper(classification: dict, rules: list[dict], fallback_subsection: str) -> str:
    """Route a classified paper to its survey_trace subsection."""
    training = (classification.get("training") or "").upper()
    method = (classification.get("method_category") + " " +
              classification.get("specific_method") + " " +
              classification.get("general_method")).upper()
    bits = (classification.get("bit_scope") or "").upper()

    for rule in rules:
        rule_training = [r.upper() for r in rule.get("training", [])]
        rule_method = [r.upper() for r in rule.get("method", [])]
        rule_bits = [r.upper() for r in rule.get("bits", [])]

        if rule_training and not any(t in training for t in rule_training):
            continue
        if rule_method and not any(kw in method for kw in rule_method):
            continue
        if rule_bits and not any(b in bits for b in rule_bits):
            continue

        return rule["subsection"]

    return fallback_subsection


def load_routing_config(path: str) -> list[dict]:
    if not path:
        return DEFAULT_ROUTING_RULES
    with open(path) as f:
        cfg = json.load(f)
    if isinstance(cfg, list):
        return cfg
    if "rules" in cfg:
        return cfg["rules"]
    return DEFAULT_ROUTING_RULES


# ─── Output formatters ────────────────────────────────────────────────────────

FIELD_LABELS = [
    ("model_type", "Model Type"),
    ("method_category", "Method Category"),
    ("specific_method", "Specific Method"),
    ("training", "Training Paradigm"),
    ("core_challenge", "Core Challenge"),
    ("evaluation", "Evaluation Focus"),
    ("hardware", "Hardware Co-design"),
    ("summary", "Summary"),
    ("bit_scope", "Quantization Bit Scope"),
    ("general_method", "General Method Type"),
    ("core_challenge_addressed", "Core Challenge Addressed"),
    ("survey_contribution", "Survey Contribution Mapping"),
]


def format_text(arxiv_id: str, meta: dict, fields: dict, subsection: str) -> str:
    """Human-readable text output."""
    lines = [
        f"arXiv ID:   {arxiv_id}",
        f"Title:      {meta.get('title', '?')}",
        f"Authors:    {', '.join(meta.get('authors', [])[:3])}{' et al.' if len(meta.get('authors', [])) > 3 else ''}",
        f"Published:  {meta.get('published', '?')}",
        f"Categories: {', '.join(meta.get('categories', [])[:5])}",
        f"PDF:        {meta.get('pdf_url', 'N/A')}",
        "",
        "── 12-Field Classification ──────────────────────────────",
        f"  [Tier {fields['relevance_score']}] {fields['relevance_tier']}",
        f"  Matched keywords: {', '.join(fields['matched_keywords'][:6])}",
        "",
    ]
    for key, label in FIELD_LABELS:
        val = fields.get(key, "")
        if val:
            lines.append(f"  {label}: {val}")

    lines.extend([
        "",
        "── Routing ──────────────────────────────────────────────",
        f"  → survey_trace: {subsection}",
    ])
    return "\n".join(lines)


def format_json(arxiv_id: str, meta: dict, fields: dict, subsection: str) -> str:
    """Machine-readable JSON output."""
    output = {
        "arxiv_id": arxiv_id,
        "title": meta.get("title", ""),
        "authors": meta.get("authors", []),
        "published": meta.get("published", ""),
        "categories": meta.get("categories", []),
        "pdf_url": meta.get("pdf_url", ""),
        "classification": fields,
        "survey_trace_subsection": subsection,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="SurveyMind Single-Paper 12-Field Triage")
    ap.add_argument("arxiv_ids", nargs="+", help="One or more arXiv IDs (e.g. 2210.17323)")
    ap.add_argument("--routing-config", "-r", help="JSON routing config")
    ap.add_argument("--domain-profile",
                   default="templates/domain_profiles/general_profile.json",
                   help="Domain profile JSON path")
    ap.add_argument("--topic-keywords", "-k",
                   default="",
                   help="Comma-separated topic keywords (overrides profile keywords)")
    ap.add_argument("--format", "-f", choices=["text", "json"], default="text",
                   help="Output format (default: text)")
    ap.add_argument("--verbose", "-v", action="store_true")

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    try:
        profile, profile_path = load_domain_profile(args.domain_profile, root_dir)
    except DomainProfileError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    keywords = [k.strip() for k in args.topic_keywords.split(",") if k.strip()] or profile_keywords(profile)
    core_keywords = profile_core_keywords(profile)
    context_keywords = profile_context_keywords(profile)
    rules = load_routing_config(args.routing_config or "") if args.routing_config else profile_routing_rules(profile)
    fallback_subsection = profile_routing_fallback(profile, "02/01_general_related_work")

    shown_keywords = ",".join(keywords[:6])
    print(f"SurveyMind paper_triage — {len(args.arxiv_ids)} paper(s), keywords: {shown_keywords}")
    print(f"Domain profile: {profile_path}")
    print()

    for arid in args.arxiv_ids:
        if args.verbose:
            print(f"Fetching {arid}...")

        meta = fetch_arxiv_metadata(arid)
        if not meta or "_error" in meta:
            print(f"ERROR: Could not fetch {arid}: {meta.get('_error', 'unknown error')}", file=sys.stderr)
            continue

        fields = classify_12field(
            meta,
            keywords,
            core_keywords=core_keywords,
            context_keywords=context_keywords,
        )
        subsection = route_paper(fields, rules, fallback_subsection)

        if args.format == "json":
            print(format_json(arid, meta, fields, subsection))
        else:
            print(format_text(arid, meta, fields, subsection))

        if not args.verbose:
            print()


if __name__ == "__main__":
    main()
