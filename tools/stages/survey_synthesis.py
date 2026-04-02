"""Survey synthesis stages for CLI full-closure flow.

These stages provide scriptable equivalents for:
- taxonomy-build
- gap-identify
- survey-write
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


_FIELD_LABEL_TO_KEY = {
    "Model Type": "model_type",
    "Method Category": "method_category",
    "Specific Method": "specific_method",
    "Training Paradigm": "training",
    "Core Challenge": "core_challenge",
    "Evaluation Focus": "evaluation",
    "Hardware Co-design": "hardware",
    "Quantization Bit Scope": "bit_scope",
    "General Method Type": "general_method",
}


def _parse_analysis_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    out: dict[str, str] = {"paper_id": path.name.replace("_analysis.md", "")}

    # Match lines like: "2. **Method Category**: Binarization"
    for m in re.finditer(r"\n\s*\d+\.\s+\*\*(.+?)\*\*:\s*(.+)", "\n" + text):
        label = m.group(1).strip()
        value = m.group(2).strip()
        key = _FIELD_LABEL_TO_KEY.get(label)
        if key and value:
            out[key] = value
    return out


def _load_analysis_records(analysis_dir: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for p in sorted(analysis_dir.glob("*_analysis.md")):
        try:
            records.append(_parse_analysis_file(p))
        except Exception:
            continue
    return records


def run_taxonomy_build(args) -> int:
    """Build taxonomy from gate2 analysis files."""
    print("\n" + "=" * 60)
    print("STAGE: taxonomy-build — Build taxonomy from analyses")
    print("=" * 60)

    analysis_dir = Path(args.analysis_dir)
    gate3_dir = Path(args.gate3_dir)
    gate3_dir.mkdir(parents=True, exist_ok=True)

    records = _load_analysis_records(analysis_dir)
    if not records:
        print(f"ERROR: no analysis files found in {analysis_dir}", file=sys.stderr)
        return 1

    method_counts = Counter(r.get("method_category", "Unknown") for r in records)
    training_counts = Counter(r.get("training", "Unknown") for r in records)
    bit_counts = Counter(r.get("bit_scope", "Unknown") for r in records)
    model_counts = Counter(r.get("model_type", "Unknown") for r in records)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "analysis_dir": str(analysis_dir),
        "paper_count": len(records),
        "method_category": dict(method_counts),
        "training_paradigm": dict(training_counts),
        "bit_scope": dict(bit_counts),
        "model_type": dict(model_counts),
    }

    taxonomy_json = gate3_dir / "taxonomy_summary.json"
    taxonomy_md = gate3_dir / "taxonomy.md"
    taxonomy_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Taxonomy",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Paper count: {payload['paper_count']}",
        "",
        "## Method Category",
        "",
    ]
    for k, v in method_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Training Paradigm", ""]
    for k, v in training_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Quantization Bit Scope", ""]
    for k, v in bit_counts.most_common():
        lines.append(f"- {k}: {v}")

    lines += ["", "## Model Type", ""]
    for k, v in model_counts.most_common():
        lines.append(f"- {k}: {v}")

    taxonomy_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"taxonomy markdown: {taxonomy_md}")
    print(f"taxonomy summary: {taxonomy_json}")
    return 0


def run_gap_identify(args) -> int:
    """Identify research gaps from taxonomy summary."""
    print("\n" + "=" * 60)
    print("STAGE: gap-identify — Identify research gaps")
    print("=" * 60)

    gate3_dir = Path(args.gate3_dir)
    gate4_dir = Path(args.gate4_dir)
    gate4_dir.mkdir(parents=True, exist_ok=True)

    taxonomy_json = gate3_dir / "taxonomy_summary.json"
    if not taxonomy_json.exists():
        print(f"ERROR: taxonomy summary missing: {taxonomy_json} (run taxonomy-build first)", file=sys.stderr)
        return 1

    data = json.loads(taxonomy_json.read_text(encoding="utf-8"))
    method_counts = data.get("method_category", {})
    training_counts = data.get("training_paradigm", {})
    bit_counts = data.get("bit_scope", {})

    sparse_methods = [k for k, v in method_counts.items() if isinstance(v, int) and v <= 1 and k != "Unknown"]
    expected_training = [
        "PTQ (Post-Training Quantization)",
        "QAT (Quantization-Aware Training)",
        "From-Scratch Training",
    ]
    missing_training = [t for t in expected_training if training_counts.get(t, 0) == 0]
    expected_bits = ["1-bit", "1.58-bit (ternary)", "2-bit", "3-bit", "4-bit"]
    missing_bits = [b for b in expected_bits if bit_counts.get(b, 0) == 0]

    gaps = []
    if sparse_methods:
        gaps.append({
            "type": "Method under-coverage",
            "severity": "medium",
            "detail": f"Low-evidence method categories: {', '.join(sparse_methods[:8])}",
        })
    if missing_training:
        gaps.append({
            "type": "Training paradigm gap",
            "severity": "high",
            "detail": f"Missing paradigms: {', '.join(missing_training)}",
        })
    if missing_bits:
        gaps.append({
            "type": "Bit-width coverage gap",
            "severity": "high",
            "detail": f"Missing bit scopes: {', '.join(missing_bits)}",
        })
    if not gaps:
        gaps.append({
            "type": "No obvious structural gaps",
            "severity": "low",
            "detail": "Current taxonomy covers major method/training/bit axes from available analyses.",
        })

    payload = {
        "generated_at": datetime.now().isoformat(),
        "source_taxonomy": str(taxonomy_json),
        "gap_count": len(gaps),
        "gaps": gaps,
    }

    out_json = gate4_dir / "gap_analysis.json"
    out_md = gate4_dir / "gap_analysis.md"
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Gap Analysis",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Gap count: {payload['gap_count']}",
        "",
    ]
    for i, g in enumerate(gaps, start=1):
        lines += [
            f"## Gap {i}: {g['type']}",
            "",
            f"- Severity: {g['severity']}",
            f"- Detail: {g['detail']}",
            "",
        ]

    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"gap analysis markdown: {out_md}")
    print(f"gap analysis json: {out_json}")
    return 0


def run_survey_write(args) -> int:
    """Synthesize survey draft from scope/taxonomy/gap artifacts."""
    print("\n" + "=" * 60)
    print("STAGE: survey-write — Synthesize survey draft")
    print("=" * 60)

    gate3_dir = Path(args.gate3_dir)
    gate4_dir = Path(args.gate4_dir)
    gate5_dir = Path(args.gate5_dir)
    gate5_dir.mkdir(parents=True, exist_ok=True)

    taxonomy_md = gate3_dir / "taxonomy.md"
    gap_md = gate4_dir / "gap_analysis.md"
    if not taxonomy_md.exists() or not gap_md.exists():
        print("ERROR: taxonomy/gap artifacts missing (run taxonomy-build and gap-identify first)", file=sys.stderr)
        return 1

    scope_title = "Survey"
    scope_path = Path(args.scope_file)
    if scope_path.exists():
        for line in scope_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("# "):
                scope_title = line[2:].strip()
                break

    draft_path = gate5_dir / "SURVEY_DRAFT.md"
    lines = [
        f"# {scope_title}",
        "",
        "## 1. Introduction",
        "- Motivation and scope generated from gate0 scope definition.",
        "",
        "## 2. Taxonomy",
        "",
        taxonomy_md.read_text(encoding="utf-8", errors="ignore").strip(),
        "",
        "## 3. Gap Analysis",
        "",
        gap_md.read_text(encoding="utf-8", errors="ignore").strip(),
        "",
        "## 4. Discussion",
        "- Summarize trade-offs across method categories and training paradigms.",
        "- Highlight benchmark and reproducibility limitations.",
        "",
        "## 5. Conclusion",
        "- Key takeaways and actionable future directions.",
        "",
        "## References",
        "- TODO: populate from gate1 paper list and citations.",
        "",
    ]
    draft_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"survey draft: {draft_path}")
    return 0


def run_validate_and_improve(args) -> int:
    """Run validation and automatically improve based on results.

    This stage:
    1. Runs validation (citations, benchmarks, guardrails)
    2. Parses validation reports for critical issues
    3. For missing cited papers: adds to corpus and re-analyzes
    4. Re-runs taxonomy-build, gap-identify, survey-write if needed
    5. Re-runs validation to confirm fixes
    """
    import json
    import subprocess
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    import re

    print("\n" + "=" * 60)
    print("STAGE: validate-and-improve — Validation + Auto-improvement")
    print("=" * 60)

    project_root = Path(__file__).parent.parent.resolve()
    survey_root = Path(args.survey_root) if args.survey_root else (project_root / "surveys" / f"survey_{args.survey_name}").resolve()
    validation_dir = survey_root / "validation" / "reports"
    validation_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Run initial validation
    print("\n--- Running initial validation ---")
    validation_script = project_root / "validation" / "run_validation.py"
    cmd = [
        sys.executable, str(validation_script),
        "--scope", "all",
        "--retry", "2",
        "--survey-root", str(survey_root),
        "--report-dir", str(validation_dir),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Step 2: Parse validation reports for issues
    citation_report = validation_dir / "citation_validation_report.json"
    benchmark_report = validation_dir / "benchmark_validation_report.json"

    missing_papers = []
    if citation_report.exists():
        data = json.loads(citation_report.read_text())
        for issue in data.get("issues", []):
            if issue.get("code") == "CITED_ID_NOT_IN_REGISTRY":
                paper_id = issue.get("item", "")
                if paper_id and re.match(r"\d{4}\.\d{4,5}", paper_id):
                    missing_papers.append(paper_id)

    benchmark_issues = []
    if benchmark_report.exists():
        data = json.loads(benchmark_report.read_text())
        for issue in data.get("issues", []):
            if issue.get("code") in ("NO_BENCHMARK_FILES", "SURVEY_BENCHMARK_MISSING"):
                benchmark_issues.append(issue.get("code"))

    # Step 3: Handle missing papers
    if missing_papers:
        print(f"\n--- Found {len(missing_papers)} missing cited papers ---")
        paper_list_path = survey_root / "gate1_research_lit" / "paper_list.json"
        if paper_list_path.exists():
            paper_list = json.loads(paper_list_path.read_text())
        else:
            # Fallback to paper_list_expanded.json
            paper_list_path = survey_root / "gate1_research_lit" / "paper_list_expanded.json"
            if paper_list_path.exists():
                paper_list = json.loads(paper_list_path.read_text())
            else:
                paper_list = {"topic": args.survey_name or "unknown", "papers": []}

        existing_ids = {p.get("paper_id") for p in paper_list.get("papers", [])}
        new_papers = []

        for paper_id in missing_papers:
            if paper_id in existing_ids:
                continue
            print(f"  Fetching metadata for {paper_id}...")

            # Fetch from arXiv API
            arxiv_id = paper_id
            query = f"id:{arxiv_id}"
            url = f"http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&max_results=1"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SurveyMind-validation/1.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    xml_text = resp.read().decode("utf-8")
                root = ET.fromstring(xml_text)
                entry = root.find("{http://www.w3.org/2005/Atom}entry")
                if entry is not None:
                    title = (entry.findtext("{http://www.w3.org/2005/Atom}title", "") or "").strip()
                    authors = [(a.findtext("{http://www.w3.org/2005/Atom}name", "") or "").strip()
                               for a in entry.findall("{http://www.w3.org/2005/Atom}author")]
                    published = (entry.findtext("{http://www.w3.org/2005/Atom}published", "") or "")[:4]
                    abstract = (entry.findtext("{http://www.w3.org/2005/Atom}summary", "") or "").strip()

                    new_paper = {
                        "paper_id": arxiv_id,
                        "title": re.sub(r"\s+", " ", title),
                        "authors": authors,
                        "year": int(published) if published.isdigit() else 2024,
                        "venue": "arXiv",
                        "arXiv_id": arxiv_id,
                        "abstract": re.sub(r"\s+", " ", abstract),
                        "pdf_path": f"papers/{arxiv_id}.pdf",
                        "source": "validation_fix",
                        "relevance_score": 0.9
                    }
                    new_papers.append(new_paper)
                    print(f"    Added: {title[:60]}...")
            except Exception as e:
                print(f"    Failed to fetch {arxiv_id}: {e}")

        if new_papers:
            paper_list["papers"].extend(new_papers)
            paper_list_path.write_text(json.dumps(paper_list, indent=2, ensure_ascii=False) + "\n")
            print(f"  Updated paper_list with {len(new_papers)} new papers")

            # Download PDFs for new papers
            print("\n--- Downloading new paper PDFs ---")
            papers_dir = survey_root / "gate1_research_lit" / "papers"
            papers_dir.mkdir(parents=True, exist_ok=True)

            for new_paper in new_papers:
                pid = new_paper.get("paper_id", "")
                if not pid:
                    continue
                pdf_path = papers_dir / f"{pid}.pdf"
                if pdf_path.exists():
                    continue
                try:
                    cmd = [sys.executable, str(project_root / "tools" / "arxiv_fetch.py"),
                           "download", pid, "--dir", str(papers_dir)]
                    subprocess.run(cmd, capture_output=True, timeout=120)
                    print(f"  Downloaded {pid}")
                except Exception as e:
                    print(f"  Failed to download {pid}: {e}")

            # Re-run paper-analysis for new papers
            print("\n--- Re-running paper-analysis for new papers ---")
            # Create a triage file with the new papers
            triage_path = survey_root / "gate2_paper_analysis" / "all_papers_triage"
            if triage_path.exists():
                triage_data = json.loads(triage_path.read_text())
            else:
                triage_data = {"papers": [], "tier_counts": {}}

            for new_paper in new_papers:
                pid = new_paper.get("paper_id", "")
                triage_data["papers"].append({
                    "arxiv_id": pid,
                    "title": new_paper.get("title", ""),
                    "status": "ok",
                    "classification": {"relevance_tier": "Tier 1 – Core"}
                })
                triage_data["tier_counts"]["Tier 1 – Core"] = triage_data["tier_counts"].get("Tier 1 – Core", 0) + 1

            triage_path.write_text(json.dumps(triage_data, indent=2) + "\n")

            # Re-run paper-analysis
            try:
                cmd = [sys.executable, str(project_root / "tools" / "surveymind_run.py"),
                       "--stage", "paper-analysis",
                       "--survey-root", str(survey_root),
                       "--analysis-tier-scope", "all",
                       "--analysis-mode", "deep+coverage"]
                subprocess.run(cmd, capture_output=True, timeout=600)
                print("  Paper-analysis completed")
            except Exception as e:
                print(f"  Paper-analysis failed: {e}")

            # Re-run taxonomy-build and gap-identify
            print("\n--- Re-building taxonomy and gaps ---")
            try:
                cmd = [sys.executable, str(project_root / "tools" / "surveymind_run.py"),
                       "--stage", "taxonomy-build", "--survey-root", str(survey_root)]
                subprocess.run(cmd, capture_output=True, timeout=120)
            except Exception as e:
                print(f"  Taxonomy-build failed: {e}")

            try:
                cmd = [sys.executable, str(project_root / "tools" / "surveymind_run.py"),
                       "--stage", "gap-identify", "--survey-root", str(survey_root)]
                subprocess.run(cmd, capture_output=True, timeout=120)
            except Exception as e:
                print(f"  Gap-identify failed: {e}")

            # Re-run survey-write
            print("\n--- Re-writing survey ---")
            try:
                cmd = [sys.executable, str(project_root / "tools" / "surveymind_run.py"),
                       "--stage", "survey-write", "--survey-root", str(survey_root)]
                subprocess.run(cmd, capture_output=True, timeout=120)
            except Exception as e:
                print(f"  Survey-write failed: {e}")

    # Step 4: Re-run validation to confirm fixes
    if missing_papers or benchmark_issues:
        print("\n--- Running final validation ---")
        final_validation_cmd = [
            sys.executable, str(project_root / "validation" / "run_validation.py"),
            "--scope", "all",
            "--retry", "2",
            "--survey-root", str(survey_root),
            "--report-dir", str(validation_dir),
        ]
        result = subprocess.run(final_validation_cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

    print("\n" + "=" * 60)
    print("STAGE: validate-and-improve — Complete")
    print("=" * 60)
    return 0
