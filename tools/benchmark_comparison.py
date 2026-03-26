#!/usr/bin/env python3
"""
Benchmark Extractor Tool: Extract benchmark data from research papers.

This tool extracts numerical benchmark data from PDF papers and generates
comparison tables in Markdown and LaTeX formats.

Usage:
    # Automatic extraction (may miss some data due to PDF complexity)
    python3 benchmark_comparison.py auto papers/*.pdf -o output/

    # Manual extraction with JSON config (recommended for accuracy)
    python3 benchmark_comparison.py manual papers/2306.00978.pdf --config my_config.json

    # Compare multiple papers
    python3 benchmark_comparison.py compare paper1.json paper2.json -o comparison.md

    # Generate LaTeX from comparison
    python3 benchmark_comparison.py latex comparison.md -o tables.tex

Notes:
    - PDF table extraction is inherently imprecise due to varying table formats
    - For best results, use the --config option to provide known benchmark values
    - Or use the 'manual' command to interactively specify values

Dependencies:
    pip install pymupdf
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF required. Install: pip install pymupdf")
    sys.exit(1)


# ============================================================================
# Data Structures
# ============================================================================

class BenchmarkData:
    """Container for benchmark data from a single paper."""

    def __init__(self, paper_id: str, title: str = ""):
        self.paper_id = paper_id
        self.title = title
        self.models: Dict[str, Dict[str, str]] = {}  # model -> {metric -> value}

    def add(self, model: str, metric: str, value: str):
        """Add a benchmark value."""
        if model not in self.models:
            self.models[model] = {}
        self.models[model][metric] = value

    def to_dict(self) -> Dict:
        return {
            'paper_id': self.paper_id,
            'title': self.title,
            'models': self.models
        }

    @classmethod
    def from_dict(cls, d: Dict) -> 'BenchmarkData':
        data = cls(d.get('paper_id', 'unknown'), d.get('title', ''))
        data.models = d.get('models', {})
        return data


# ============================================================================
# PDF Extraction
# ============================================================================

def extract_paper_info(pdf_path: str) -> Tuple[str, str]:
    """Extract paper ID and title from PDF."""
    doc = fitz.open(pdf_path)
    paper_id = Path(pdf_path).stem
    title = ""

    if len(doc) > 0:
        text = doc[0].get_text()
        lines = text.split('\n')

        # Title: first substantial line
        for line in lines[:15]:
            line = line.strip()
            if 20 < len(line) < 200 and not line.startswith('http'):
                if any(c.isupper() for c in line[:10]):
                    title = line
                    break

        # arXiv ID
        for line in lines[:50]:
            match = re.search(r'arXiv[:\s]*(\d{4}\.\d{4,5})', line, re.IGNORECASE)
            if match:
                paper_id = match.group(1)
                break

    doc.close()
    return paper_id, title


def extract_from_page_blocks(page) -> List[Tuple[str, str, str]]:
    """
    Extract (model, metric, value) tuples from a PDF page using block analysis.
    Returns list of tuples.
    """
    results = []

    # Get blocks sorted by position
    blocks = page.get_text("blocks")
    sorted_blocks = sorted(blocks, key=lambda b: (b[1], b[0]))  # y, then x

    # Collect numbers by y-position
    y_groups = {}
    current_y = None
    current_group = []

    for block in sorted_blocks:
        x0, y0, x1, y1, text, btype, bno = block
        text = text.strip()

        if not text or len(text) < 2:
            continue

        # Group by approximate y position (within 10 points)
        if current_y is None or abs(y0 - current_y) < 10:
            current_y = y0
            current_group.append((x0, text))
        else:
            if current_group:
                y_groups[current_y] = sorted(current_group, key=lambda x: x[0])
            current_y = y0
            current_group = [(x0, text)]

    if current_group:
        y_groups[current_y] = sorted(current_group, key=lambda x: x[0])

    # Known model patterns
    model_patterns = [
        r'LLaMA[-\s]?\d*[B]?',
        r'LLM[-\s]?\d*[B]?',
        r'OPT[-\s]?\d*[B]?',
        r'Mistral[-\s]?\d*[B]?',
        r'Mixtral[-\s]?\d+x\d*[B]?',
        r'Qwen[23]?[-\s]?\d*[B]?',
        r'Vicuna[-\s]?\d*[B]?',
        r'CodeLLaMA[-\s]?\d*[B]?',
        r'GPTQ[-\s]?\d*[B]?',
    ]

    # Known metrics
    metric_keywords = ['WikiText', 'C4', 'PTB', 'PPL', 'ARC', 'BoolQ', 'HellaSwag',
                       'PIQA', 'MMLU', 'GSM8K', 'Average', 'perplexity']

    # Process each y-group
    for y, group in y_groups.items():
        line_text = ' '.join([t for _, t in group])

        # Skip if too short or looks like prose
        if len(line_text) < 10:
            continue

        # Check for model name
        model_name = None
        for pattern in model_patterns:
            match = re.search(pattern, line_text, re.IGNORECASE)
            if match:
                model_name = match.group(0)
                # Normalize
                model_name = re.sub(r'[-\s]', '', model_name, count=1)
                if 'llama' in model_name.lower():
                    model_name = re.sub(r'(\d+)', r'-\1B', model_name, flags=re.IGNORECASE)
                elif model_name.lower().startswith('opt'):
                    model_name = re.sub(r'(\d+)', r'-\1B', model_name, flags=re.IGNORECASE)
                break

        # Extract numbers
        numbers = re.findall(r'\d+\.?\d*', line_text)

        # If we have a model name and numbers, try to assign metrics
        if model_name and len(numbers) >= 1:
            # Default to perplexity if no specific metric mentioned
            if any(kw in line_text.lower() for kw in metric_keywords):
                # Try to identify specific metrics
                for num in numbers:
                    if 'wiki' in line_text.lower():
                        results.append((model_name, 'WikiText-2', num))
                    elif 'arc-c' in line_text.lower():
                        results.append((model_name, 'ARC-C', num))
                    elif 'arc' in line_text.lower():
                        results.append((model_name, 'ARC', num))
                    elif 'bool' in line_text.lower():
                        results.append((model_name, 'BoolQ', num))
                    elif 'hella' in line_text.lower():
                        results.append((model_name, 'HellaSwag', num))
                    elif 'piqa' in line_text.lower():
                        results.append((model_name, 'PIQA', num))
                    elif 'ppl' in line_text.lower() or 'perplexity' in line_text.lower():
                        results.append((model_name, 'PPL', num))
                    else:
                        results.append((model_name, 'Value', num))
            else:
                # No metric keyword - assume perplexity for language modeling papers
                for num in numbers:
                    results.append((model_name, 'PPL', num))

    return results


def auto_extract(pdf_path: str, pages: Optional[List[int]] = None) -> BenchmarkData:
    """
    Automatically extract benchmark data from PDF.
    Returns BenchmarkData object.
    """
    paper_id, title = extract_paper_info(pdf_path)
    data = BenchmarkData(paper_id, title)

    doc = fitz.open(pdf_path)

    # Determine which pages to scan
    if pages:
        page_range = [p - 1 for p in pages if 0 < p <= len(doc)]
    else:
        # Scan all pages
        page_range = range(len(doc))

    for page_num in page_range:
        page = doc[page_num]
        results = extract_from_page_blocks(page)

        for model, metric, value in results:
            data.add(model, metric, value)

    doc.close()

    # Deduplicate and take first value for each (model, metric)
    seen = {}
    for model, metrics in data.models.items():
        for metric, value in metrics.items():
            if (model, metric) not in seen:
                seen[(model, metric)] = value

    # Rebuild with deduplicated values
    data.models = {}
    for (model, metric), value in seen.items():
        if model not in data.models:
            data.models[model] = {}
        data.models[model][metric] = value

    return data


# ============================================================================
# Comparison and Output Generation
# ============================================================================

def normalize_metric(metric: str) -> str:
    """Normalize metric name."""
    metric = metric.strip()
    metric_lower = metric.lower()

    if 'wiki' in metric_lower:
        return 'WikiText-2'
    if 'c4' in metric_lower:
        return 'C4'
    if 'ptb' in metric_lower:
        return 'PTB'
    if 'ppl' in metric_lower or 'perplexity' in metric_lower:
        return 'PPL'
    if 'arc-c' in metric_lower:
        return 'ARC-C'
    if 'arc-e' in metric_lower:
        return 'ARC-E'
    if 'arc' in metric_lower:
        return 'ARC'
    if 'bool' in metric_lower:
        return 'BoolQ'
    if 'hella' in metric_lower:
        return 'HellaSwag'
    if 'piqa' in metric_lower:
        return 'PIQA'
    if 'mmlu' in metric_lower:
        return 'MMLU'
    if 'gsm' in metric_lower or 'math' in metric_lower:
        return 'GSM8K'
    if 'avg' in metric_lower or 'average' in metric_lower:
        return 'Average'

    return metric


def normalize_model(model: str) -> str:
    """Normalize model name, preserving parameter count."""
    model = model.strip()
    model_lower = model.lower()

    # LLaMA: size is the number immediately before "B" (handles LLaMA-2-7B, LLaMA-3-8B, etc.)
    if 'llama' in model_lower:
        match = re.search(r'(\d+)B\b', model)
        size = match.group(1) if match else ''
        return f"LLaMA-{size}B" if size else "LLaMA"

    # OPT: size is the number before "B" (OPT-1.3B, OPT-6.7B, OPT-13B)
    if model_lower.startswith('opt'):
        match = re.search(r'(\d+(?:\.\d+)?)B\b', model)
        size = match.group(1) if match else ''
        return f"OPT-{size}B" if size else "OPT"

    # Mistral
    if 'mistral' in model_lower:
        match = re.search(r'(\d+)B\b', model)
        return f"Mistral-{match.group(1)}B" if match else 'Mistral-7B'

    # Mixtral
    if 'mixtral' in model_lower:
        match = re.search(r'(\d+x\d+)B\b', model)
        return f"Mixtral-{match.group(1)}B" if match else 'Mixtral-8x7B'

    # Qwen: size is the number immediately before "B" (Qwen-2-7B, Qwen-3-8B, etc.)
    if 'qwen' in model_lower:
        match = re.search(r'(\d+)B\b', model)
        size = match.group(1) if match else ''
        return f"Qwen-{size}B" if size else "Qwen"

    return model


def escape_latex(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\\_'),
        ('^', r'\^{}'),
        ('~', r'\textasciitilde{}'),
        ('{', r'\{'),
        ('}', r'\}'),
    ]
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    return text


def generate_comparison(all_data: List[BenchmarkData]) -> Tuple[str, str]:
    """Generate markdown and LaTeX comparison strings."""

    # Collect all models and metrics
    all_models = set()
    all_metrics = set()

    for data in all_data:
        for model, metrics in data.models.items():
            if not isinstance(metrics, dict):
                continue
            all_models.add(normalize_model(model))
            for metric in metrics:
                all_metrics.add(normalize_metric(metric))

    # Sort
    model_order = ['LLaMA-7B', 'LLaMA-13B', 'LLaMA-30B', 'LLaMA-65B',
                   'LLaMA-1-7B', 'LLaMA-1-13B', 'LLaMA-1-30B', 'LLaMA-1-65B',
                   'LLaMA-8B', 'LLaMA-70B',
                   'Mistral-7B', 'Mistral-13B', 'Mixtral-8x7B',
                   'Qwen-7B', 'Qwen-14B', 'Qwen-8B', 'Qwen-14B',
                   'OPT-1.3B', 'OPT-6.7B', 'OPT-13B']

    sorted_models = sorted(all_models, key=lambda m: (
        m not in model_order,
        model_order.index(m) if m in model_order else 999
    ))

    metric_order = ['WikiText-2', 'PPL', 'C4', 'PTB', 'ARC-C', 'ARC-E', 'ARC',
                    'BoolQ', 'HellaSwag', 'PIQA', 'MMLU', 'GSM8K', 'Average']

    sorted_metrics = sorted(all_metrics, key=lambda m: (
        m not in metric_order,
        metric_order.index(m) if m in metric_order else 999
    ))

    # Build markdown
    md = "# Benchmark Comparison\n\n"

    # Paper list
    md += "## Papers\n\n"
    for data in all_data:
        title = data.title or data.paper_id
        md += f"- **{title}** (`{data.paper_id}`)\n"
    md += "\n---\n\n"

    # Group by metric
    for metric in sorted_metrics:
        # Find models that have this metric
        metric_models = []
        for model in sorted_models:
            values = []
            for data in all_data:
                # Find value for this paper (use '--' if missing)
                found = None
                for orig_model, metrics in data.models.items():
                    if not isinstance(metrics, dict):
                        continue
                    if normalize_model(orig_model) == model:
                        for m, v in metrics.items():
                            if normalize_metric(m) == metric:
                                found = v
                                break
                        break
                values.append(found if found is not None else '--')
            if any(v != '--' for v in values):
                metric_models.append((model, values))

        if not metric_models:
            continue

        # Add table for this metric
        md += f"## {metric}\n\n"

        # Header
        headers = [f"`{d.paper_id}`" for d in all_data]
        md += "| Model | " + " | ".join(headers) + " |\n"
        md += "|-------|" + "|-------|" * len(all_data) + "\n"

        for model, values in metric_models:
            md += f"| {model} | " + " | ".join(str(v) for v in values) + " |\n"

        md += "\n"

    # Build LaTeX
    latex = ""

    for metric in sorted_metrics[:6]:  # Limit tables
        metric_models = []
        for model in sorted_models:
            values = []
            for data in all_data:
                found = None
                for orig_model, metrics in data.models.items():
                    if not isinstance(metrics, dict):
                        continue
                    if normalize_model(orig_model) == model:
                        for m, v in metrics.items():
                            if normalize_metric(m) == metric:
                                found = v
                                break
                        break
                values.append(found if found is not None else '--')
            if any(v != '--' for v in values):
                metric_models.append((model, values))

        if not metric_models:
            continue

        # Safe label (alphanumeric only)
        safe_label = re.sub(r'[^a-zA-Z]', '', metric).lower()[:10]
        caption_metric = escape_latex(metric)

        latex += f"""\\begin{{table}}[t]
\\centering
\\caption{{{caption_metric} Comparison}}
\\label{{tab:{safe_label}}}
\\begin{{tabular}}{{l{"c" * len(all_data)}}}
\\toprule
\\textbf{{Model}} & {" & ".join([f"\\textit{{{escape_latex(d.paper_id[:8])}}}" for d in all_data])} \\\\
\\midrule
"""

        for model, values in metric_models:
            escaped_model = escape_latex(model)
            escaped_values = " & ".join(escape_latex(str(v)) for v in values)
            latex += f"\\texttt{{{escaped_model}}} & {escaped_values} \\\\\n"

        latex += """\\bottomrule
\\end{tabular}
\\end{table}

"""

    return md, latex


# ============================================================================
# Manual Data Entry
# ============================================================================

def create_template(paper_id: str, output_path: str):
    """Create a template JSON file for manual data entry."""
    template = {
        "paper_id": paper_id,
        "title": "Paper Title",
        "models": {
            "LLaMA-2-7B": {
                "WikiText-2": "",
                "PPL": "",
                "ARC-C": "",
                "BoolQ": ""
            }
        }
    }

    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)

    print(f"Template created: {output_path}")
    print("Edit this file with your benchmark values, then use:")
    print(f"  python3 benchmark_comparison.py merge {output_path} -o output/")


# ============================================================================
# Main CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Benchmark Extractor Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Auto extract
    auto_parser = subparsers.add_parser('auto', help='Auto-extract from PDFs')
    auto_parser.add_argument('pdfs', nargs='+', help='PDF files')
    auto_parser.add_argument('-o', '--output', default='extracted', help='Output dir')
    auto_parser.add_argument('-p', '--pages', type=int, nargs='+',
                            help='Specific pages to scan (1-indexed)')

    # Manual template
    manual_parser = subparsers.add_parser('manual', help='Create manual entry template')
    manual_parser.add_argument('paper_id', help='Paper ID (e.g., 2306.00978)')
    manual_parser.add_argument('-o', '--output', default='benchmark_template.json',
                              help='Template output path')

    # Merge/manual data
    merge_parser = subparsers.add_parser('merge', help='Merge manual data')
    merge_parser.add_argument('files', nargs='+', help='JSON files')
    merge_parser.add_argument('-o', '--output', default='merged.json', help='Output')

    # Compare
    compare_parser = subparsers.add_parser('compare', help='Compare papers')
    compare_parser.add_argument('files', nargs='+', help='JSON files')
    compare_parser.add_argument('-o', '--output', default='comparison.md', help='Output')

    # LaTeX
    latex_parser = subparsers.add_parser('latex', help='Generate LaTeX')
    latex_parser.add_argument('input', help='JSON or Markdown file')
    latex_parser.add_argument('-o', '--output', default='tables.tex', help='Output')

    # Full pipeline
    full_parser = subparsers.add_parser('full', help='Full pipeline')
    full_parser.add_argument('pdfs', nargs='+', help='PDF files')
    full_parser.add_argument('-o', '--output', default='benchmark_output', help='Output dir')
    full_parser.add_argument('--pages', type=int, nargs='+', help='Pages to scan')

    args = parser.parse_args()

    if args.command == 'auto':
        out_dir = Path(args.output)
        out_dir.mkdir(exist_ok=True)

        for pdf in args.pdfs:
            print(f"Extracting: {pdf}")
            data = auto_extract(pdf, args.pages)

            out_file = out_dir / f"{data.paper_id}.json"
            with open(out_file, 'w') as f:
                json.dump(data.to_dict(), f, indent=2)

            num_models = len(data.models)
            print(f"  -> {out_file} ({num_models} models)")

    elif args.command == 'manual':
        create_template(args.paper_id, args.output)

    elif args.command == 'merge':
        merged = {
            'paper_id': 'merged',
            'title': 'Combined Data',
            'models': {}
        }

        for f in args.files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: skipping {f}: {e}", file=sys.stderr)
                continue
            for model, metrics in data.get('models', {}).items():
                if not isinstance(metrics, dict):
                    print(f"Warning: skipping malformed entry '{model}' in {f} (expected dict, got {type(metrics).__name__})", file=sys.stderr)
                    continue
                if model not in merged['models']:
                    merged['models'][model] = {}
                for metric, value in metrics.items():
                    if not merged['models'][model].get(metric):
                        merged['models'][model][metric] = value

        with open(args.output, 'w') as f:
            json.dump(merged, f, indent=2)
        print(f"Merged data: {args.output}")

    elif args.command == 'compare':
        all_data = []
        for f in args.files:
            try:
                with open(f) as fp:
                    d = json.load(fp)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: skipping {f}: {e}", file=sys.stderr)
                continue
            all_data.append(BenchmarkData.from_dict(d))

        md, latex = generate_comparison(all_data)

        # Write markdown
        with open(args.output, 'w') as f:
            f.write(md)

        # Write LaTeX
        latex_file = args.output.replace('.md', '.tex')
        with open(latex_file, 'w') as f:
            f.write(latex)

        print(f"Markdown: {args.output}")
        print(f"LaTeX: {latex_file}")

    elif args.command == 'latex':
        if args.input.endswith('.json'):
            try:
                with open(args.input) as f:
                    all_data = [BenchmarkData.from_dict(json.load(f))]
            except (json.JSONDecodeError, OSError) as e:
                print(f"Error reading {args.input}: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Markdown input - just convert what's there
            md = open(args.input).read()
            latex = """\\begin{table}[h]
\\centering
\\caption{Benchmark Results}
\\begin{tabular}{lc}
\\toprule
\\textbf{Method} & \\textbf{Value} \\\\
\\midrule
"""
            for line in md.split('\n'):
                if line.startswith('|') and '---' not in line:
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    if len(cells) == 2:
                        latex += f"{cells[0]} & {cells[1]} \\\\\n"
            latex += """\\bottomrule
\\end{tabular}
\\end{table}
"""
            all_data = None

        if all_data:
            _, latex = generate_comparison(all_data)

        with open(args.output, 'w') as f:
            f.write(latex)
        print(f"LaTeX: {args.output}")

    elif args.command == 'full':
        out_dir = Path(args.output)
        out_dir.mkdir(exist_ok=True)

        # Extract
        print("Step 1: Extracting...")
        json_files = []
        for pdf in args.pdfs:
            data = auto_extract(pdf, args.pages)
            json_file = out_dir / f"{data.paper_id}.json"
            with open(json_file, 'w') as f:
                json.dump(data.to_dict(), f, indent=2)
            json_files.append(str(json_file))
            print(f"  {data.paper_id}: {len(data.models)} models")

        # Compare
        print("\\nStep 2: Comparing...")
        all_data = [BenchmarkData.from_dict(json.load(open(f))) for f in json_files]
        md, latex = generate_comparison(all_data)

        md_file = out_dir / 'comparison.md'
        tex_file = out_dir / 'tables.tex'

        with open(md_file, 'w') as f:
            f.write(md)
        with open(tex_file, 'w') as f:
            f.write(latex)

        print(f"  Markdown: {md_file}")
        print(f"  LaTeX: {tex_file}")
        print(f"\\nDone: {out_dir}/")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
