"""Tests for tools/triage_core.py — shared 12-field classification and routing."""

from tools.triage_core import (
    DEFAULT_ROUTING_RULES,
    classify_12field,
    compute_relevance_score,
    route_paper,
)


class TestComputeRelevanceScore:
    def test_score_0_no_match(self):
        score, matched = compute_relevance_score(
            title="A paper about cooking",
            abstract="This is about food",
        )
        assert score == 0
        assert matched == []

    def test_score_1_single_keyword_match(self):
        score, matched = compute_relevance_score(
            title="Survey of deep learning",
            abstract="",
            keywords=["survey", "review", "benchmark"],
        )
        assert score == 1
        assert "survey" in matched

    def test_score_2_two_keyword_match(self):
        score, matched = compute_relevance_score(
            title="Benchmark evaluation of methods",
            abstract="",
            keywords=["survey", "review", "benchmark", "evaluation"],
        )
        assert score == 2
        assert "benchmark" in matched
        assert "evaluation" in matched

    def test_score_3_three_keyword_match(self):
        score, _ = compute_relevance_score(
            title="Survey benchmark evaluation of methods",
            abstract="",
            keywords=["survey", "review", "benchmark", "evaluation"],
        )
        assert score == 3

    def test_score_3_with_core_and_context_keywords(self):
        score, _ = compute_relevance_score(
            title="Binary quantization for LLMs",
            abstract="We propose a new 1-bit quantization method",
            keywords=["survey"],
            core_keywords=["quantization", "binary"],
            context_keywords=["llm", "language model"],
        )
        assert score == 3

    def test_score_2_with_only_core_keyword(self):
        score, _ = compute_relevance_score(
            title="Binary quantization technique",
            abstract="",
            keywords=["survey"],
            core_keywords=["quantization"],
            context_keywords=[],
        )
        assert score == 2

    def test_score_2_with_two_context_keywords(self):
        score, _ = compute_relevance_score(
            title="Efficient LLM compression",
            abstract="",
            keywords=["survey"],
            core_keywords=[],
            context_keywords=["llm", "compression"],
        )
        assert score == 2

    def test_case_insensitive(self):
        score, matched = compute_relevance_score(
            title="A SURVEY of DEEP LEARNING",
            abstract="",
            keywords=["survey", "review"],
        )
        assert score == 1
        assert "survey" in matched

    def test_empty_title_and_abstract(self):
        score, matched = compute_relevance_score(title="", abstract="", keywords=["survey"])
        assert score == 0
        assert matched == []


class TestClassify12Field:
    def _meta(self, title, abstract="", categories=None):
        return {
            "title": title,
            "abstract": abstract,
            "categories": categories or [],
        }

    def test_model_type_llm(self):
        meta = self._meta("Quantization for Large Language Models")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["model_type"] == "LLM"

    def test_model_type_vlm(self):
        meta = self._meta("Vision Language Model Compression")
        fields = classify_12field(meta, keywords=["compression"])
        assert fields["model_type"] == "VLM / Multimodal"

    def test_model_type_transformer(self):
        meta = self._meta("Efficient Transformer Architecture")
        fields = classify_12field(meta, keywords=["efficient"])
        assert fields["model_type"] == "Transformer"

    def test_method_category_binarization(self):
        meta = self._meta("Binary quantization", "1-bit quantization")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["method_category"] == "Binarization"

    def test_method_category_ternarization(self):
        meta = self._meta("Ternary quantization paper", "1.58-bit")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["method_category"] == "Ternarization"

    def test_method_category_outlier_aware(self):
        meta = self._meta("SmoothQuant for LLM", "outlier handling")
        fields = classify_12field(meta, keywords=["quantization", "llm"])
        assert fields["method_category"] == "Outlier-Aware Quantization"

    def test_specific_method_awq(self):
        meta = self._meta("AWQ quantization method")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["specific_method"] == "AWQ"

    def test_specific_method_gptq(self):
        meta = self._meta("GPTQ: Post-Training Quantization")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["specific_method"] == "GPTQ"

    def test_training_ptq(self):
        meta = self._meta("Post-training quantization", "PTQ method")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["training"] == "PTQ (Post-Training Quantization)"

    def test_training_qat(self):
        meta = self._meta("Quantization-aware training for LLMs")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["training"] == "QAT (Quantization-Aware Training)"

    def test_core_challenge_outlier(self):
        meta = self._meta("Handling outliers in quantization")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["core_challenge"] == "Outlier Handling"

    def test_bit_scope_1bit(self):
        meta = self._meta("1-bit quantization", "binary network")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["bit_scope"] == "1-bit"

    def test_bit_scope_ternary(self):
        meta = self._meta("1.58-bit quantization", "ternary")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["bit_scope"] == "1.58-bit (ternary)"

    def test_bit_scope_mixed(self):
        meta = self._meta("Mixed precision quantization", "mixed-precision")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["bit_scope"] == "Mixed (2-4-bit)"

    def test_evaluation_perplexity(self):
        meta = self._meta("LLM quantization", "perplexity evaluation")
        fields = classify_12field(meta, keywords=["quantization", "llm"])
        assert fields["evaluation"] == "Perplexity (language modeling)"

    def test_hardware_gpu(self):
        meta = self._meta("GPU-efficient quantization", "CUDA kernels")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["hardware"] == "GPU / CUDA"

    def test_hardware_asic(self):
        meta = self._meta("FPGA accelerator for quantization")
        fields = classify_12field(meta, keywords=["quantization"])
        assert fields["hardware"] == "ASIC / FPGA"

    def test_relevance_tier_core(self):
        meta = self._meta("Core LLM quantization survey", "survey benchmark evaluation")
        fields = classify_12field(meta, keywords=["survey", "benchmark", "evaluation", "method", "model"])
        assert fields["relevance_tier"] == "Tier 1 – Core"
        assert fields["relevance_score"] == 3

    def test_relevance_tier_peripheral(self):
        meta = self._meta("Unrelated computer graphics paper")
        fields = classify_12field(meta, keywords=["survey", "review"])
        assert fields["relevance_tier"] == "Tier 4 – Peripheral"


class TestRoutePaper:
    def test_routes_qat_binary_to_training_strategies(self):
        classification = {
            "training": "QAT (Quantization-Aware Training)",
            "method_category": "Binarization",
            "specific_method": "[inferred]",
            "general_method": "Standard Quantization",
            "bit_scope": "1-bit",
        }
        result = route_paper(classification, DEFAULT_ROUTING_RULES, "02/01_general")
        assert result == "05/01_method_training_strategies"

    def test_routes_ptq_reconstruction_to_post_training(self):
        classification = {
            "training": "PTQ (Post-Training Quantization)",
            "method_category": "Reconstruction-based",
            "specific_method": "GPTQ",
            "general_method": "Reconstruction-based",
            "bit_scope": "4-bit",
        }
        result = route_paper(classification, DEFAULT_ROUTING_RULES, "02/01_general")
        assert result == "06/01_post_training_methods"

    def test_routes_outlier_to_stability(self):
        classification = {
            "training": "Unspecified",
            "method_category": "Outlier-Aware Quantization",
            "specific_method": "SmoothQuant",
            "general_method": "Outlier-Aware",
            "bit_scope": "Not specified",
        }
        result = route_paper(classification, DEFAULT_ROUTING_RULES, "02/01_general")
        assert result == "07/01_stability_and_generalization"

    def test_routes_hardware_to_system(self):
        classification = {
            "training": "Unspecified",
            "method_category": "GPU Kernel Optimization",
            "specific_method": "CustomMethod",
            "general_method": "Kernel Tuning",
            "bit_scope": "4-bit",
        }
        # Use a rule that matches GPU in the method field
        rules = [{"training": [], "method": ["GPU", "CPU", "ASIC", "FPGA"], "bits": [], "subsection": "08/01_system_and_hardware"}]
        result = route_paper(classification, rules, "02/01_general")
        assert result == "08/01_system_and_hardware"

    def test_fallback_when_no_rule_matches(self):
        classification = {
            "training": "Unspecified",
            "method_category": "Neural Network (unspecified)",
            "specific_method": "[inferred]",
            "general_method": "Standard Quantization",
            "bit_scope": "Not specified",
        }
        result = route_paper(classification, [], "99/01_misc")
        assert result == "99/01_misc"


class TestDefaultRoutingRules:
    def test_default_routing_rules_has_9_entries(self):
        assert len(DEFAULT_ROUTING_RULES) == 9

    def test_all_rules_have_subsection(self):
        for rule in DEFAULT_ROUTING_RULES:
            assert "subsection" in rule

    def test_training_rules_qat(self):
        qat_rules = [r for r in DEFAULT_ROUTING_RULES if "QAT" in r.get("training", [])]
        assert len(qat_rules) == 2
