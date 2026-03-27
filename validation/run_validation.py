#!/usr/bin/env python3
"""Validation entrypoint for SurveyMind.

Scopes:
- citations: reference integrity and anti-hallucination checks
- benchmarks: benchmark data integrity checks
- guardrails: writable path policy checks
- all: run all checks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List

from citation_validator import run_citation_validation
from benchmark_validator import run_benchmark_validation
from guardrails_validator import run_guardrails_validation


@dataclass
class ValidationResult:
    name: str
    passed: bool
    critical_count: int
    warning_count: int
    retried: int
    report_json: str
    report_md: str


def _load_policy(project_root: Path) -> Dict:
    policy_file = project_root / "validation" / "policy.json"
    if not policy_file.exists():
        return {}
    return json.loads(policy_file.read_text(encoding="utf-8"))


def _write_summary(project_root: Path, report_dir: Path, results: List[ValidationResult]) -> None:
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "overall_passed": all(r.passed for r in results),
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "critical_count": r.critical_count,
                "warning_count": r.warning_count,
                "retried": r.retried,
                "report_json": r.report_json,
                "report_md": r.report_md,
            }
            for r in results
        ],
    }
    out_json = report_dir / "validation_summary.json"
    out_md = report_dir / "validation_summary.md"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# Validation Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Overall passed: {summary['overall_passed']}",
        "",
        "| Scope | Passed | Critical | Warning | Retries |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.name} | {str(r.passed).lower()} | {r.critical_count} | {r.warning_count} | {r.retried} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_terminal_summary(results: List[ValidationResult]) -> str:
    lines = ["", "Validation summary:"]
    for r in results:
        state = "PASS" if r.passed else "FAIL"
        lines.append(
            f"- {r.name}: {state} (critical={r.critical_count}, warning={r.warning_count}, retries={r.retried})"
        )
    return "\n".join(lines)


def _maybe_record_failure_rollup(project_root: Path, report_dir: Path, results: List[ValidationResult]) -> None:
    failures = [r for r in results if not r.passed]
    if not failures:
        return
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "failures": [
            {
                "scope": r.name,
                "critical_count": r.critical_count,
                "warning_count": r.warning_count,
                "retried": r.retried,
                "report_json": r.report_json,
            }
            for r in failures
        ],
    }
    (report_dir / "validation_failures.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    md_lines = [
        "# Validation Failures",
        "",
        f"- Generated at: {payload['generated_at']}",
        "",
    ]
    for f in payload["failures"]:
        md_lines.append(f"## {f['scope']}")
        md_lines.append(f"- Critical: {f['critical_count']}")
        md_lines.append(f"- Warning: {f['warning_count']}")
        md_lines.append(f"- Retry attempts: {f['retried']}")
        md_lines.append(f"- Report: {f['report_json']}")
        md_lines.append("")
    (report_dir / "validation_failures.md").write_text(
        "\n".join(md_lines), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SurveyMind validation checks")
    parser.add_argument(
        "--scope",
        choices=["citations", "benchmarks", "guardrails", "all"],
        default="all",
        help="Validation scope",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=None,
        help="Retry times for re-fetch/re-extract on failures (recommended 1-2)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail non-zero if any critical issue is found",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (default: auto detect from this file)",
    )
    parser.add_argument(
        "--survey-root",
        default=None,
        help="Survey run root (e.g., surveys/survey_xxx) for gate-structured inputs",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Override report output directory",
    )
    parser.add_argument(
        "--record-guardrails-baseline",
        action="store_true",
        help="Record current changed files as guardrails baseline",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve() if args.project_root else Path(__file__).resolve().parents[1]
    survey_root = Path(args.survey_root).resolve() if args.survey_root else None
    policy = _load_policy(project_root)

    retry = args.retry if args.retry is not None else int(policy.get("max_retry_default", 2))
    strict = bool(args.strict or policy.get("strict_default", False))
    if args.report_dir:
        report_dir = Path(args.report_dir).resolve()
    else:
        report_dir = project_root / policy.get("report_dir", "validation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    scope_handlers: Dict[str, Callable[..., ValidationResult]] = {
        "citations": run_citation_validation,
        "benchmarks": run_benchmark_validation,
        "guardrails": run_guardrails_validation,
    }
    requested = list(scope_handlers.keys()) if args.scope == "all" else [args.scope]

    results: List[ValidationResult] = []
    for name in requested:
        handler = scope_handlers[name]
        if name == "guardrails":
            raw = handler(
                project_root=project_root,
                report_dir=report_dir,
                policy=policy,
                strict=strict,
                record_baseline=args.record_guardrails_baseline,
                survey_root=survey_root,
            )
        else:
            raw = handler(
                project_root=project_root,
                report_dir=report_dir,
                policy=policy,
                strict=strict,
                retry=retry,
                survey_root=survey_root,
            )

        results.append(
            ValidationResult(
                name=name,
                passed=raw["passed"],
                critical_count=int(raw["critical_count"]),
                warning_count=int(raw["warning_count"]),
                retried=int(raw.get("retried", 0)),
                report_json=raw["report_json"],
                report_md=raw["report_md"],
            )
        )

    _write_summary(project_root, report_dir, results)
    _maybe_record_failure_rollup(project_root, report_dir, results)

    print(_format_terminal_summary(results))

    has_critical = any(r.critical_count > 0 for r in results)
    if strict and has_critical:
        return 1
    if not strict and not all(r.passed for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
