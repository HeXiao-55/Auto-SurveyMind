#!/usr/bin/env python3
"""
batch_paper_triage.py — SurveyMind Batch Paper Triage

Reads an arxiv JSON file, runs 12-field classification on every paper,
and produces a complete coverage report mapping all papers to survey_trace
subsections.

Designed to be reusable for ANY survey — routing rules are parameterised
via --routing-config or built-in defaults.

Usage
-----
    # Triage all papers in arxiv JSON
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --output all_papers_triage.json

    # Tier 1 only (Priority)
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --tier-filter 1 \\
        --output tier1_triage.json

    # With API delay control
    python3 tools/batch_paper_triage.py \\
        --input tpami_tem/arxiv_results.json \\
        --delay 2.0

Exit codes
    0  success
    1  input not found / parse error
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

# ─── arXiv API ────────────────────────────────────────────────────────────────

ARXIV_API = "http://export.arxiv.org/api/query"
USER_AGENT = "SurveyMind-batch-triage/1.0"
_ATOM_NS = "http://www.w3.org/2005/Atom"


def fetch_arxiv_metadata(arxiv_id: str, retries: int = 2) -> Optional[dict]:
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
                return {"_error": str(exc), "arxiv_id": arxiv_id}
    return None


# ─── Relevance scoring ────────────────────────────────────────────────────────

DEFAULT_KEYWORDS = [
    "quantization", "quantize", "quantiz", "low-bit", "ultra-low", "sub-bit",
    "binary", "ternary", "1-bit", "1.58-bit", "2-bit", "4-bit",
    "llm", "large language model", "transformer", "language model",
    "post-training", "qat", "ptq",
    "outlier", "pruning",
    "awq", "gptq", "spqr", "quip", "quarot", "smoothquant",
    "bitnet", "ternaryllm",
    "weight compression", "model compression",
]


def compute_relevance_score(
    title: str, abstract: str = "", categories: list[str] = None,
    keywords: list[str] = None,
) -> tuple[int, list[str]]:
    categories = categories or []
    keywords = keywords or DEFAULT_KEYWORDS
    text = (title + " " + (abstract or "")).lower()
    matched = [kw for kw in keywords if kw.lower() in text]
    core_kws = {"quantization", "quantiz", "quantize", "low-bit", "binary",
                "ternary", "1-bit", "1.58-bit", "2-bit", "sub-bit", "post-training"}
    core_matches = {k.lower() for k in matched} & core_kws
    has_llm = any(k in text for k in ["llm", "large language model", "transformer",
                                        "language model", "bert", "gpt", "lama"])
    if core_matches and has_llm:
        return 3, matched
    if core_matches:
        return 2, matched
    if matched:
        return 1, matched
    return 0, []


# ─── 12-field classification ─────────────────────────────────────────────────

def classify_12field(meta: dict, keywords: list[str]) -> dict:
    text = (meta.get("title", "") + " " + meta.get("abstract", "")).lower()
    score, matched_kws = compute_relevance_score(
        title=meta.get("title", ""), abstract=meta.get("abstract", ""),
        categories=meta.get("categories", []), keywords=keywords)

    fields = {}

    if any(k in text for k in ["llm", "large language model", "gpt", "bert", "lama", "llama"]):
        fields["model_type"] = "LLM"
    elif any(k in text for k in ["vision", "vlm", "multimodal", "image"]):
        fields["model_type"] = "VLM / Multimodal"
    elif any(k in text for k in ["vit", "transformer", "encoder", "decoder"]):
        fields["model_type"] = "Transformer"
    else:
        fields["model_type"] = "Neural Network (unspecified)"

    if any(k in text for k in ["binary", "1-bit", "binariz"]):
        fields["method_category"] = "Binarization"
    elif any(k in text for k in ["ternary", "1.58", "ternariz"]):
        fields["method_category"] = "Ternarization"
    elif any(k in text for k in ["outlier", "smoothquant", "quarot", "quip"]):
        fields["method_category"] = "Outlier-Aware Quantization"
    elif any(k in text for k in ["pruning", "sparse", "mask"]):
        fields["method_category"] = "Pruning / Sparse"
    elif any(k in text for k in ["quarot", "hadamard rotation", "orthogonal transform"]):
        fields["method_category"] = "Rotation / Transform"
    elif any(k in text for k in ["reconstruction", "calibrate", "optimize weight", "per-channel", "per-token"]):
        fields["method_category"] = "Reconstruction-based"
    else:
        fields["method_category"] = "Standard Quantization"

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

    if any(k in text for k in ["post-training", "ptq", "post training", "pretrained"]):
        fields["training"] = "PTQ (Post-Training Quantization)"
    elif any(k in text for k in ["qat", "quantization-aware", "aware training"]):
        fields["training"] = "QAT (Quantization-Aware Training)"
    elif any(k in text for k in ["from scratch", "train from scratch", "from-scratch"]):
        fields["training"] = "From-Scratch Training"
    else:
        fields["training"] = "Unspecified"

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

    fields["summary"] = meta.get("abstract", "")[:300]

    import re as _re
    def _has(t, w): return bool(_re.search(r'\b' + _re.escape(w) + r'\b', t))
    if _has(text, "1-bit") or (_has(text, "binary") and not _has(text, "ternary")):
        fields["bit_scope"] = "1-bit"
    elif _has(text, "1.58") or (_has(text, "ternary") and not _has(text, "bitnet")):
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

    fields["core_challenge_addressed"] = fields["core_challenge"]
    fields["survey_contribution"] = "[needs full PDF analysis]"
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
     "subsection": "05/01_binary_networks_1_bit"},
    {"training": ["QAT", "From-Scratch"], "method": ["Ternary", "ternarization", "1.58-bit"], "bits": ["1.58-bit"],
     "subsection": "05/02_ternary_networks_1_58_bit"},
    {"training": ["QAT"], "method": ["curvature", "hessian", "low-rank", "sparse", "co-training"], "bits": [],
     "subsection": "05/03_recent_qat_advances"},
    {"training": ["PTQ"], "method": ["Ultra-low", "sub-2-bit", "structured", "mask", "trit-plane",
                                     "dual-scale", "deviation", "block reconstruction", "layer-wise",
                                     "butterfly", "rotation"], "bits": ["1-bit", "1.61-bit", "sub-2-bit", "1.58-bit"],
     "subsection": "06/01_ultra_low_ptq_sub_2_bit"},
    {"training": ["PTQ"], "method": ["2-bit", "INT2", "progressive"], "bits": ["2-bit"],
     "subsection": "06/03_2bit_quantization_methods"},
    {"training": ["PTQ"], "method": ["standard", "4-bit", "per-channel", "per-token", "mixed-precision"], "bits": ["3-bit", "4-bit"],
     "subsection": "06/04_transform_based_and_mixed_precision_methods"},
    {"training": ["PTQ"], "method": [], "bits": [],
     "subsection": "06/01_ultra_low_ptq_sub_2_bit"},
    {"training": [], "method": ["outlier", "smoothquant", "quarot", "quip", "prefix", "rotation",
                                 "redistribution", "migration", "asymmetric"], "bits": [],
     "subsection": "07/02_categorization_of_outlier_handling_methods"},
    {"training": [], "method": ["CPU", "GPU", "ASIC", "CIM", "PIM", "kernel", "hardware",
                                "inference", "SIMD", "async", "dequantization"], "bits": [],
     "subsection": "08/01_cpu_implementations"},
    {"training": [], "method": ["multimodal", "MLLM", "VLM", "VLA", "agent", "KV cache"], "bits": [],
     "subsection": "11/01_vision_language_action_models"},
    {"training": [], "method": ["benchmark", "perplexity", "accuracy", "latency", "throughput", "energy", "memory"], "bits": [],
     "subsection": "09/02_performance_comparison"},
    {"training": [], "method": ["gap", "limitation", "challenge", "generalization", "theory", "standardization"], "bits": [],
     "subsection": "10/01_gap_standardized_protocols"},
]


def route_paper(classification: dict, rules: list[dict]) -> str:
    training = (classification.get("training") or "").upper()
    method = (classification.get("method_category") + " " +
              classification.get("specific_method") + " " +
              classification.get("general_method")).upper()
    bits = (classification.get("bit_scope") or "").upper()
    for rule in rules:
        rt = [r.upper() for r in rule.get("training", [])]
        rm = [r.upper() for r in rule.get("method", [])]
        rb = [r.upper() for r in rule.get("bits", [])]
        if rt and not any(t in training for t in rt):
            continue
        if rm and not any(kw in method for kw in rm):
            continue
        if rb and not any(b in bits for b in rb):
            continue
        return rule["subsection"]
    return "02/01_general_model_quantization_surveys"


def build_framework_vocabulary(rules: list[dict]) -> set[str]:
    """Build a loose keyword pool from routing rules for framework-aware pruning."""
    vocab: set[str] = set()
    for rule in rules:
        for key in ("training", "method", "bits"):
            for item in rule.get(key, []) or []:
                text = str(item).lower()
                vocab.add(text)
                for tok in re.findall(r"[a-z0-9\.\-\+]+", text):
                    if len(tok) >= 3:
                        vocab.add(tok)
    # Keep a few broad anchors to avoid over-pruning borderline but relevant papers.
    vocab.update({"quantization", "low-bit", "llm", "language model", "transformer"})
    return vocab


def framework_match_keywords(text: str, framework_vocab: set[str]) -> list[str]:
    hits = [kw for kw in framework_vocab if kw and kw in text]
    # Deterministic order for stable outputs.
    return sorted(hits)[:12]


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


# ─── Main ─────────────────────────────────────────────────────────────────

def load_arxiv_json(path: str) -> list[dict]:
    with open(path) as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        for key in ("results", "papers", "data", "items"):
            if key in raw:
                raw = raw[key]
                break
    if not isinstance(raw, list):
        raise ValueError(f"Expected list of papers in {path}")
    return raw


def build_triage_report(
    arxiv_json_path: str,
    output_path: str,
    keywords: list[str],
    routing_config_path: str | None = None,
    tier_filter: int | None = None,
    min_score: int = 0,
    coarse_prune: bool = True,
    delay: float = 1.0,
    verbose: bool = False,
) -> dict:
    papers = load_arxiv_json(arxiv_json_path)
    rules = load_routing_config(routing_config_path)
    framework_vocab = build_framework_vocabulary(rules)

    results = []
    tier_counts = {"Tier 1 – Core": 0, "Tier 2 – High Relevance": 0,
                   "Tier 3 – Related": 0, "Tier 4 – Peripheral": 0}
    subsection_counts = {}
    kept_count = 0
    pruned_count = 0

    for i, entry in enumerate(papers):
        arid = entry.get("id") or entry.get("arxiv_id", "")
        if not arid:
            continue

        # Progress indicator every 10 papers
        if verbose and (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(papers)}] processed...")

        meta = fetch_arxiv_metadata(arid)
        if not meta or "_error" in meta:
            results.append({
                "arxiv_id": arid,
                "title": entry.get("title", "Unknown"),
                "status": "error",
                "error": meta.get("_error") if meta else "not found",
                "classification": None,
                "subsection": None,
            })
            if delay > 0:
                time.sleep(delay)
            continue

        classification = classify_12field(meta, keywords)
        subsection = route_paper(classification, rules)
        text = (meta.get("title", "") + " " + meta.get("abstract", "")).lower()
        fw_hits = framework_match_keywords(text, framework_vocab)
        classification["framework_match_count"] = len(fw_hits)
        classification["framework_matched_keywords"] = fw_hits

        # Coarse prune policy: keep high recall, only remove clearly irrelevant.
        # Clearly irrelevant = below min_score and no framework evidence.
        keep = True
        if coarse_prune:
            keep = (classification["relevance_score"] >= min_score) or bool(fw_hits)
        else:
            keep = classification["relevance_score"] >= min_score

        if tier_filter is not None:
            if classification["relevance_score"] < 3 and tier_filter == 1:
                if delay > 0:
                    time.sleep(0.5)
                continue

        if keep:
            kept_count += 1
        else:
            pruned_count += 1

        if not keep:
            results.append({
                "arxiv_id": arid,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", []),
                "published": meta.get("published", ""),
                "categories": meta.get("categories", []),
                "pdf_url": meta.get("pdf_url", ""),
                "status": "pruned_irrelevant",
                "classification": classification,
                "subsection": subsection,
            })
            if delay > 0:
                time.sleep(delay)
            continue

        tier = classification["relevance_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        subsection_counts[subsection] = subsection_counts.get(subsection, 0) + 1

        results.append({
            "arxiv_id": arid,
            "title": meta.get("title", ""),
            "authors": meta.get("authors", []),
            "published": meta.get("published", ""),
            "categories": meta.get("categories", []),
            "pdf_url": meta.get("pdf_url", ""),
            "status": "ok",
            "classification": classification,
            "subsection": subsection,
        })

        if delay > 0:
            time.sleep(delay)

    report = {
        "generated_at": datetime.now().isoformat(),
        "source": arxiv_json_path,
        "total": len(papers),
        "kept": kept_count,
        "pruned": pruned_count,
        "coarse_prune": coarse_prune,
        "min_score": min_score,
        "tier_counts": tier_counts,
        "subsection_counts": subsection_counts,
        "papers": results,
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="SurveyMind Batch Paper Triage")
    ap.add_argument("--input", "-i", required=True, help="Input arxiv JSON file")
    ap.add_argument("--output", "-o", default="batch_triage.json",
                   help="Output JSON path (default: batch_triage.json)")
    ap.add_argument("--tier-filter", type=int, choices=[1, 2, 3, 4],
                   help="Only process papers of this tier (1-4)")
    ap.add_argument("--topic-keywords", "-k",
                   default="quantization,LLM,binary,ternary,low-bit,post-training,1-bit,1.58-bit",
                   help="Comma-separated topic keywords")
    ap.add_argument("--routing-config", "-r",
                   help="JSON routing config (default: built-in ultra-low bit rules)")
    ap.add_argument("--min-score", type=int, choices=[0, 1, 2, 3], default=0,
                   help="Keep papers with relevance_score >= min-score (default: 0)")
    ap.add_argument("--coarse-prune", action=argparse.BooleanOptionalAction, default=True,
                   help="Enable framework-aware coarse pruning (default: on)")
    ap.add_argument("--delay", type=float, default=1.0,
                   help="Seconds between API calls (default: 1.0, use 0 to disable)")
    ap.add_argument("--verbose", "-v", action="store_true")

    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    root_dir = tools_dir.parent
    input_path = (root_dir / args.input).resolve()

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = (root_dir / args.output).resolve()
    keywords = [k.strip() for k in args.topic_keywords.split(",") if k.strip()]

    print(f"SurveyMind batch_paper_triage")
    print(f"  Input:   {input_path}")
    print(f"  Output:  {output_path}")
    print(f"  Delay:   {args.delay}s between API calls")
    if args.tier_filter:
        print(f"  Filter:  Tier {args.tier_filter} only")
    print(f"  Coarse:  {'on' if args.coarse_prune else 'off'} (min-score={args.min_score})")

    report = build_triage_report(
        arxiv_json_path=str(input_path),
        output_path=str(output_path),
        keywords=keywords,
        routing_config_path=args.routing_config,
        tier_filter=args.tier_filter,
        min_score=args.min_score,
        coarse_prune=args.coarse_prune,
        delay=args.delay,
        verbose=args.verbose,
    )

    print(f"\n{'='*50}")
    print(f"Total:    {report['total']}")
    print(f"Kept:     {report['kept']}")
    print(f"Pruned:   {report['pruned']}")
    for tier, count in report['tier_counts'].items():
        print(f"  {tier}: {count}")
    print(f"\nSubsection distribution:")
    for sub, count in sorted(report['subsection_counts'].items(), key=lambda x: -x[1]):
        print(f"  {sub}: {count}")
    print(f"{'='*50}")
    print(f"Output → {output_path}")


if __name__ == "__main__":
    main()
