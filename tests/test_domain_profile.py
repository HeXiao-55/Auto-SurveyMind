"""Tests for tools/domain_profile.py."""

import copy

import pytest

from tools.domain_profile import (
    DomainProfileError,
    load_domain_profile,
    profile_core_keywords,
    profile_keywords,
    profile_routing_fallback,
    profile_routing_rules,
)

SAMPLE_PROFILE = {
    "name": "test-profile",
    "relevance": {
        "keywords": ["quantization", "LLM", "binary"],
        "core_keywords": ["ultra-low bit", "1-bit"],
        "context_keywords": ["NLP", "transformer"],
    },
    "routing": {
        "fallback_subsection": "02/01_general",
        "framework_anchor_terms": ["AWQ", "GPTQ"],
        "rules": [
            {
                "subsection": "05/01_training",
                "training": ["QAT"],
                "method": ["binary"],
                "bits": ["1-bit"],
            },
        ],
    },
}


class TestLoadDomainProfile:
    def test_loads_valid_profile(self, tmp_path):
        import json
        profile_path = tmp_path / "test_profile.json"
        profile_path.write_text(json.dumps(SAMPLE_PROFILE))
        profile, resolved = load_domain_profile(str(profile_path), tmp_path)
        assert profile["name"] == "test-profile"
        assert resolved == profile_path

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(DomainProfileError, match="not found"):
            load_domain_profile("does_not_exist.json", tmp_path)

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json{{")
        with pytest.raises(DomainProfileError, match="invalid domain profile JSON"):
            load_domain_profile(str(p), tmp_path)

    def test_missing_required_fields_raise(self, tmp_path):
        import json
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"name": "no-relevance"}))
        with pytest.raises(DomainProfileError, match=r"profile\.relevance"):
            load_domain_profile(str(p), tmp_path)

    def test_empty_fallback_raises(self, tmp_path):
        import json
        bad = copy.deepcopy(SAMPLE_PROFILE)
        bad["routing"]["fallback_subsection"] = ""
        p = tmp_path / "bad.json"
        p.write_text(json.dumps(bad))
        with pytest.raises(DomainProfileError, match="fallback_subsection"):
            load_domain_profile(str(p), tmp_path)


class TestAccessors:
    @pytest.fixture
    def profile(self, tmp_path):
        import json
        p = tmp_path / "p.json"
        p.write_text(json.dumps(SAMPLE_PROFILE))
        loaded, _ = load_domain_profile(str(p), tmp_path)
        return loaded

    def test_keywords(self, profile):
        kw = profile_keywords(profile)
        assert "quantization" in kw
        assert "LLM" in kw

    def test_core_keywords(self, profile):
        core = profile_core_keywords(profile)
        assert "ultra-low bit" in core

    def test_routing_rules(self, profile):
        rules = profile_routing_rules(profile)
        assert len(rules) == 1
        assert rules[0]["subsection"] == "05/01_training"

    def test_routing_fallback(self, profile):
        fb = profile_routing_fallback(profile, "default/subsection")
        assert fb == "02/01_general"

    def test_routing_fallback_uses_default_when_missing(self, profile):
        # Override profile with no fallback set
        profile["routing"]["fallback_subsection"] = None
        fb = profile_routing_fallback(profile, "fallback/default")
        assert fb == "fallback/default"
