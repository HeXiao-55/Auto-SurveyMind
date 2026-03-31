#!/usr/bin/env python3
"""Domain profile loader for SurveyMind.

Centralizes schema-light profile loading so tools can share relevance keywords,
routing rules, and fallback behaviors without hardcoding a specific domain.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_RELATIVE = "templates/domain_profiles/general_profile.json"


class DomainProfileError(ValueError):
    """Raised when a domain profile is missing or malformed."""


def resolve_profile_path(profile_path: str | None, project_root: Path) -> Path:
    """Resolve profile path relative to project root when not absolute."""
    candidate = Path(profile_path) if profile_path else Path(DEFAULT_PROFILE_RELATIVE)
    return candidate if candidate.is_absolute() else (project_root / candidate).resolve()


def _require_dict(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DomainProfileError(f"profile.{name} must be an object")
    return value


def _require_str_list(name: str, value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise DomainProfileError(f"profile.{name} must be a list of strings")
    return [x.strip() for x in value if x.strip()]


def load_domain_profile(profile_path: str | None, project_root: Path) -> tuple[dict[str, Any], Path]:
    """Load and validate a domain profile from JSON.

    Returns (profile_dict, resolved_path).
    """
    resolved = resolve_profile_path(profile_path, project_root)
    if not resolved.exists():
        raise DomainProfileError(f"domain profile not found: {resolved}")

    try:
        profile = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DomainProfileError(f"invalid domain profile JSON at {resolved}: {exc}") from exc

    if not isinstance(profile, dict):
        raise DomainProfileError("profile root must be an object")

    _ = profile.get("name")

    if "relevance" not in profile:
        raise DomainProfileError("profile.relevance must be an object")
    relevance = _require_dict("relevance", profile.get("relevance"))

    if "routing" not in profile:
        raise DomainProfileError("profile.routing must be an object")
    routing = _require_dict("routing", profile.get("routing"))

    _require_str_list("relevance.keywords", relevance.get("keywords", []))
    _require_str_list("relevance.core_keywords", relevance.get("core_keywords", []))
    _require_str_list("relevance.context_keywords", relevance.get("context_keywords", []))

    fallback = routing.get("fallback_subsection", "")
    if not isinstance(fallback, str) or not fallback.strip():
        raise DomainProfileError("profile.routing.fallback_subsection must be a non-empty string")

    rules = routing.get("rules", [])
    if not isinstance(rules, list):
        raise DomainProfileError("profile.routing.rules must be a list")
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise DomainProfileError(f"profile.routing.rules[{idx}] must be an object")
        subsection = rule.get("subsection", "")
        if not isinstance(subsection, str) or not subsection.strip():
            raise DomainProfileError(
                f"profile.routing.rules[{idx}].subsection must be a non-empty string"
            )

    _require_str_list(
        "routing.framework_anchor_terms",
        routing.get("framework_anchor_terms", []),
    )

    return profile, resolved


def profile_keywords(profile: dict[str, Any]) -> list[str]:
    relevance = profile.get("relevance", {})
    return _require_str_list("relevance.keywords", relevance.get("keywords", []))


def profile_core_keywords(profile: dict[str, Any]) -> list[str]:
    relevance = profile.get("relevance", {})
    return _require_str_list("relevance.core_keywords", relevance.get("core_keywords", []))


def profile_context_keywords(profile: dict[str, Any]) -> list[str]:
    relevance = profile.get("relevance", {})
    return _require_str_list("relevance.context_keywords", relevance.get("context_keywords", []))


def profile_routing_rules(profile: dict[str, Any]) -> list[dict[str, Any]]:
    routing = profile.get("routing", {})
    rules = routing.get("rules", [])
    return rules if isinstance(rules, list) else []


def profile_routing_fallback(profile: dict[str, Any], default: str) -> str:
    routing = profile.get("routing", {})
    value = routing.get("fallback_subsection")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def profile_framework_anchor_terms(profile: dict[str, Any]) -> list[str]:
    routing = profile.get("routing", {})
    return _require_str_list(
        "routing.framework_anchor_terms",
        routing.get("framework_anchor_terms", []),
    )
