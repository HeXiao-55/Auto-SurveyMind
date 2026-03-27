# SurveyMind Validation

This directory contains strict validation scripts for:

- citation integrity and anti-hallucination checks
- benchmark extraction/data sanity checks
- guardrails to prevent unauthorized project logic changes

## Quick start

```bash
python3 validation/run_validation.py --scope all --strict --retry 2
```

## Scope modes

```bash
python3 validation/run_validation.py --scope citations --strict --retry 2
python3 validation/run_validation.py --scope benchmarks --strict --retry 2
python3 validation/run_validation.py --scope guardrails --strict
```

## Baseline workflow for guardrails

If your repository is already dirty, record a baseline first:

```bash
python3 validation/run_validation.py --scope guardrails --record-guardrails-baseline
```

Then new out-of-policy changes will be detected relative to the baseline.

## Output reports

Reports are generated under `validation/reports/`:

- `citation_validation_report.json` and `.md`
- `benchmark_validation_report.json` and `.md`
- `guardrails_validation_report.json` and `.md`
- `validation_summary.json` and `.md`
- `validation_failures.json` and `.md` (only when failures exist)

## Policy config

Edit `validation/policy.json` to control:

- strict default
- retry default
- allow/protected path patterns
- report and baseline paths
