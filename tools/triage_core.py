#!/usr/bin/env python3
"""triage_core.py — Shared 12-field classification and routing for SurveyMind.

Eliminates duplicate code between paper_triage.py, batch_paper_triage.py, and
arxiv_json_extractor.py.
"""

from __future__ import annotations

import re

# ─── Relevance scoring ────────────────────────────────────────────────────────

DEFAULT_KEYWORDS = ["survey", "review", "benchmark", "evaluation", "method", "model"]


def compute_relevance_score(
    title: str,
    abstract: str = "",
    categories: list[str] | None = None,
    keywords: list[str] | None = None,
    core_keywords: list[str] | None = None,
    context_keywords: list[str] | None = None,
) -> tuple[int, list[str]]:
    """Score 0-3. Returns (score, matched_keywords)."""
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

def _has(text: str, word: str) -> bool:
    """Word-boundary-aware keyword check."""
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))


def classify_12field(
    meta: dict,
    keywords: list[str],
    core_keywords: list[str] | None = None,
    context_keywords: list[str] | None = None,
) -> dict:
    """Perform 12-field classification from arXiv metadata (no PDF needed).

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
    elif any(k in text for k in ["vision", "vlm", "multimodal", "image"]):
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

    # Field 9: Quantization Bit Scope
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
    method = (
        str(classification.get("method_category") or "") + " " +
        str(classification.get("specific_method") or "") + " " +
        str(classification.get("general_method") or "")
    ).upper()
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
