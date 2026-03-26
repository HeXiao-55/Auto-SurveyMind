#!/usr/bin/env python3
"""
Benchmark Extractor: Extract numerical benchmark data from research papers.

Usage:
    python3 benchmark_extractor.py extract <pdf_path> [--keywords KEYWORDS]
    python3 benchmark_extractor.py compare <file1.md> <file2.md> [--output OUTPUT.md]
    python3 benchmark_extractor.py latex <comparison.md> [--output OUTPUT.tex]

Examples:
    # Extract benchmarks from a single paper
    python3 benchmark_extractor.py extract papers/2306.00978.pdf --keywords "WikiText,PPL,ARC"

    # Extract with custom output
    python3 benchmark_extractor.py extract papers/2306.00978.pdf -o extracted.md

    # Generate LaTeX tables from comparison
    python3 benchmark_extractor.py latex benchmark_comparison.md -o tables.tex
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF is required. Install with: pip install pymupdf")
    sys.exit(1)


# Default benchmark keywords to search for
DEFAULT_KEYWORDS = [
    "WikiText", "WikiText-2", "WikiText2",
    "PPL", "Perplexity", "perplexity",
    "ARC", "ARC-C", "ARC-E",
    "BoolQ", "HellaSwag", "PIQA", "MMLU",
    "GSM8K", "Math", "C4",
    " latency", "Latency", "throughput", "Throughput",
    "Memory", "memory", "accuracy", "Accuracy",
    "bleu", "BLEU", "rouge", "ROUGE"
]

# Table indicators
TABLE_INDICATORS = [
    "Table", "TABLE",
    "Method", "method",
    "Model", "model",
    "FP16", "FP32", "INT", "4-bit", "3-bit", "2-bit", "1-bit",
    "AWQ", "GPTQ", "PTQ", "quantization"
]


def extract_text_from_pdf(pdf_path: str, start_page: int = 0, max_pages: Optional[int] = None) -> str:
    """Extract text from PDF using PyMuPDF.

    Args:
        pdf_path: Path to PDF file
        start_page: Starting page (0-indexed)
        max_pages: Maximum number of pages to read (None for all)

    Returns:
        Extracted text content
    """
    doc = fitz.open(pdf_path)
    text = ""

    end_page = len(doc) if max_pages is None else min(start_page + max_pages, len(doc))

    for page_num in range(start_page, end_page):
        page = doc[page_num]
        text += f"\n\n=== Page {page_num + 1} ===\n\n"
        text += page.get_text()

    doc.close()
    return text


def find_benchmark_sections(text: str, keywords: List[str]) -> List[Dict]:
    """Find sections containing benchmark data.

    Args:
        text: Full text content
        keywords: List of keywords to search for

    Returns:
        List of dicts with 'context', 'page', 'line_num'
    """
    lines = text.split('\n')
    matches = []

    for line_num, line in enumerate(lines):
        line_lower = line.lower()
        # Check if line contains any benchmark keyword
        if any(kw.lower() in line_lower for kw in keywords):
            # Get surrounding context (5 lines before and after)
            start = max(0, line_num - 5)
            end = min(len(lines), line_num + 10)
            context = '\n'.join(lines[start:end])

            # Extract page number if available
            page_match = re.search(r'=== Page (\d+) ===', context)
            page = int(page_match.group(1)) if page_match else None

            matches.append({
                'line_num': line_num,
                'page': page,
                'context': context,
                'matched_keyword': next(kw for kw in keywords if kw.lower() in line_lower)
            })

    return matches


def extract_tables_from_text(text: str) -> List[Dict]:
    """Extract potential table data from text.

    Args:
        text: Text content to search

    Returns:
        List of extracted table data
    """
    lines = text.split('\n')
    tables = []

    current_table = []
    in_table = False
    table_start = -1

    for line_num, line in enumerate(lines):
        stripped = line.strip()

        # Detect table start (has multiple numbers or has Table label)
        if 'Table' in stripped or 'table' in stripped:
            if current_table:
                tables.append({
                    'lines': current_table,
                    'start_line': table_start,
                    'end_line': line_num - 1
                })
            current_table = [stripped]
            in_table = True
            table_start = line_num
            continue

        if in_table:
            # Check if line looks like table row (has numbers or formatting chars)
            if stripped and (re.search(r'\d', stripped) or
                             stripped.startswith('|') or
                             stripped.startswith('-') or
                             'FP16' in stripped or
                             'INT' in stripped or
                             re.search(r'[A-Z][a-z]+-\d', stripped)):  # Model names like LLaMA-7B
                current_table.append(stripped)
            elif stripped == '' or len(stripped) > 200:
                # End of table
                in_table = False

    # Don't forget last table
    if current_table:
        tables.append({
            'lines': current_table,
            'start_line': table_start,
            'end_line': line_num
        })

    return tables


def parse_table_rows(table_lines: List[str]) -> List[List[str]]:
    """Parse table lines into structured rows.

    Args:
        table_lines: Lines from a table

    Returns:
        List of rows, each row is a list of cell values
    """
    rows = []

    for line in table_lines:
        # Skip separator lines
        if line.startswith('|') and set(line.replace('-', '').replace('|', '').replace(':', '').strip()) == set():
            continue

        # Parse pipe-separated or space-separated values
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')]
            cells = [c for c in cells if c]  # Remove empty
        else:
            # Try to split by whitespace while preserving structure
            cells = line.split()

        if cells:
            rows.append(cells)

    return rows


def extract_numbers_from_text(text: str) -> Dict[str, List[Tuple[str, str]]]:
    """Extract numerical results keyed by benchmark type.

    Args:
        text: Text content

    Returns:
        Dict mapping benchmark names to list of (model, value) tuples
    """
    results = {
        'WikiText-2 PPL': [],
        'C4 PPL': [],
        'ARC-C': [],
        'ARC-E': [],
        'BoolQ': [],
        'HellaSwag': [],
        'PIQA': [],
        'MMLU': [],
        'GSM8K': [],
        'Other': []
    }

    lines = text.split('\n')

    # Look for model + number patterns
    for i, line in enumerate(lines):
        # WikiText-2 PPL pattern
        if 'WikiText' in line or 'wikitext' in line.lower():
            # Look for numbers nearby
            context = ' '.join(lines[max(0, i-2):i+5])
            numbers = re.findall(r'\d+\.\d+', context)
            if numbers:
                # Try to identify model name
                model_match = re.search(r'(LLaMA[12]?[- ]?\d+B?|OPT[ -]?\d+[A-Z]?|Mistral[- ]?\d+B?|Qwen[ -]?\d+)',
                                       context, re.IGNORECASE)
                model = model_match.group(0) if model_match else "Unknown"
                results['WikiText-2 PPL'].append((model, numbers[0]))

        # ARC-C pattern
        if 'ARC-C' in line or 'ARC-c' in line:
            numbers = re.findall(r'\d+\.\d+', line)
            if numbers:
                results['ARC-C'].append((line[:50].strip(), numbers[0]))

        # BoolQ pattern
        if 'BoolQ' in line:
            numbers = re.findall(r'\d+\.\d+', line)
            if numbers:
                results['BoolQ'].append((line[:50].strip(), numbers[0]))

    return results


def generate_comparison_markdown(papers_data: List[Dict], output_path: Optional[str] = None) -> str:
    """Generate markdown comparison from extracted paper data.

    Args:
        papers_data: List of dicts with 'paper_id', 'title', 'benchmarks'
        output_path: Optional path to write file

    Returns:
        Markdown string
    """
    md = """# Benchmark Comparison

## Extracted Benchmark Data

"""

    for paper in papers_data:
        md += f"### {paper.get('title', paper.get('paper_id', 'Unknown'))}\n\n"
        md += f"- **Paper ID**: {paper.get('paper_id', 'N/A')}\n"

        if 'source' in paper:
            md += f"- **Source**: {paper['source']}\n"

        md += "\n"

        if 'benchmarks' in paper and paper['benchmarks']:
            for metric, data in paper['benchmarks'].items():
                md += f"**{metric}**:\n\n"
                md += "| Model | Value | Notes |\n"
                md += "|-------|-------|-------|\n"

                if isinstance(data, dict):
                    for model, values in data.items():
                        if isinstance(values, dict):
                            val_str = " | ".join(f"{k}: {v}" for k, v in values.items())
                            md += f"| {model} | {val_str} | |\n"
                        else:
                            md += f"| {model} | {values} | |\n"
                        md += "\n"

        md += "---\n\n"

    if output_path:
        Path(output_path).write_text(md)

    return md


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


def generate_latex_tables(comparison_md: str, output_path: Optional[str] = None) -> str:
    """Generate LaTeX tables from markdown comparison.

    Args:
        comparison_md: Markdown comparison content
        output_path: Optional path to write file

    Returns:
        LaTeX string
    """
    latex = """\\begin{table}[t]
\\centering
\\caption{Benchmark Comparison}
\\label{tab:benchmark_comparison}
"""

    # Parse markdown tables and convert to LaTeX
    lines = comparison_md.split('\n')
    table_started = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and '--' not in stripped:
            cells = [escape_latex(c.strip()) for c in stripped.split('|')[1:-1]]
            if cells:
                if not table_started:
                    col_count = len(cells)
                    latex += "\\begin{tabular}{" + ('l' + 'c' * (col_count - 1)) + "}\n"
                    latex += "\\toprule\n"
                    table_started = True
                    latex += " & ".join("\\textbf{" + h + "}" for h in cells) + " \\\\\n"
                    latex += "\\midrule\n"
                else:
                    latex += " & ".join(cells) + " \\\\\n"
        elif table_started and not stripped:
            table_started = False
            latex += "\\bottomrule\n\\end{tabular}\n\\end{table}\n"

    if table_started:
        latex += "\\bottomrule\n\\end{tabular}\n\\end{table}\n"

    if output_path:
        Path(output_path).write_text(latex)

    return latex

def extract_benchmarks_from_pdf(pdf_path: str,
                                 keywords: Optional[List[str]] = None,
                                 pages_to_scan: Optional[int] = None) -> Dict:
    """Main function to extract benchmarks from a PDF.

    Args:
        pdf_path: Path to PDF file
        keywords: List of keywords to search for (uses defaults if None)
        pages_to_scan: Number of pages to scan (None for all)

    Returns:
        Dict with extracted benchmark data
    """
    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    print(f"Extracting benchmarks from: {pdf_path}")

    # Extract text
    text = extract_text_from_pdf(pdf_path, max_pages=pages_to_scan)

    # Find benchmark sections
    matches = find_benchmark_sections(text, keywords)
    print(f"Found {len(matches)} benchmark-related sections")

    # Extract tables
    tables = extract_tables_from_text(text)
    print(f"Found {len(tables)} potential tables")

    # Extract numbers
    numbers = extract_numbers_from_text(text)

    # Build result
    result = {
        'pdf_path': pdf_path,
        'paper_id': Path(pdf_path).stem,
        'num_benchmark_sections': len(matches),
        'num_tables_found': len(tables),
        'benchmarks': numbers,
        'tables': [
            {
                'start_line': t['start_line'],
                'rows': parse_table_rows(t['lines'][:10])  # First 10 rows
            }
            for t in tables[:5]  # First 5 tables
        ]
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Extract benchmark data from research papers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract benchmarks from PDF')
    extract_parser.add_argument('pdf_path', help='Path to PDF file')
    extract_parser.add_argument('-o', '--output', help='Output file path')
    extract_parser.add_argument('-k', '--keywords', help='Comma-separated keywords')
    extract_parser.add_argument('-p', '--pages', type=int, default=None,
                                help='Number of pages to scan (default: all)')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare extracted benchmarks')
    compare_parser.add_argument('files', nargs=2, help='Two JSON benchmark files')
    compare_parser.add_argument('-o', '--output', help='Output markdown file')

    # LaTeX command
    latex_parser = subparsers.add_parser('latex', help='Generate LaTeX tables')
    latex_parser.add_argument('input', help='Input markdown comparison file')
    latex_parser.add_argument('-o', '--output', help='Output LaTeX file')

    args = parser.parse_args()

    if args.command == 'extract':
        keywords = args.keywords.split(',') if args.keywords else None
        result = extract_benchmarks_from_pdf(args.pdf_path, keywords, args.pages)

        # Output
        output = json.dumps(result, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"Results saved to: {args.output}")
        else:
            print(output)

    elif args.command == 'compare':
        # Load two benchmark files
        data1 = json.loads(Path(args.files[0]).read_text())
        data2 = json.loads(Path(args.files[1]).read_text())

        # Generate comparison
        md = generate_comparison_markdown([data1, data2])

        if args.output:
            Path(args.output).write_text(md)
            print(f"Comparison saved to: {args.output}")
        else:
            print(md)

    elif args.command == 'latex':
        # Read markdown comparison
        md = Path(args.input).read_text()

        # Generate LaTeX
        latex = generate_latex_tables(md)

        if args.output:
            Path(args.output).write_text(latex)
            print(f"LaTeX saved to: {args.output}")
        else:
            print(latex)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
