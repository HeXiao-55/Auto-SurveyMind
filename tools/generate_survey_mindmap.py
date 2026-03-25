#!/usr/bin/env python3
"""Generate a TikZ mindmap from survey_trace folder structure.

Default inputs:
- trace root: my idea/survey_trace
- template: templates/MINDMAP_TIKZ_TEMPLATE.tex

Outputs:
- survey_mindmap.tex
- survey_mindmap_paths.md
- optional: survey_mindmap.pdf and survey_mindmap.png
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
from pathlib import Path

COLOR_CYCLE = [
    "blue!65",
    "teal!65",
    "green!60!black",
    "orange!80!black",
    "red!70",
    "purple!70",
    "cyan!70!black",
    "brown!75!black",
    "magenta!70",
    "lime!60!black",
    "violet!70",
    "olive!70!black",
    "gray!70",
]


def strip_index(name: str) -> str:
    return re.sub(r"^\d+_", "", name)


def pretty_label(name: str) -> str:
    raw = strip_index(name).replace("_", " ").strip()
    raw = raw.replace("1bit", "1-bit")
    raw = raw.replace("1 58bit", "1.58-bit")
    raw = raw.replace("sub2bit", "sub-2-bit")
    raw = raw.replace("codesign", "co-design")
    raw = raw.replace("coopt", "co-optimization")
    return raw


def tex_escape(text: str) -> str:
    repl = {
        "\\": r"\\textbackslash{}",
        "&": r"\\&",
        "%": r"\\%",
        "$": r"\\$",
        "#": r"\\#",
        "_": r"\\_",
        "{": r"\\{",
        "}": r"\\}",
        "~": r"\\textasciitilde{}",
        "^": r"\\textasciicircum{}",
    }
    out = []
    for ch in text:
        out.append(repl.get(ch, ch))
    return "".join(out)


def collect_tree(trace_root: Path) -> list[tuple[str, list[tuple[str, Path]], Path]]:
    sections = []
    for sec in sorted([p for p in trace_root.iterdir() if p.is_dir() and re.match(r"^\d+_", p.name)]):
        subsecs: list[tuple[str, Path]] = []
        for sub in sorted([p for p in sec.iterdir() if p.is_dir() and re.match(r"^\d+_", p.name)]):
            subsecs.append((pretty_label(sub.name), sub))
        sections.append((pretty_label(sec.name), subsecs, sec))
    return sections


def build_children(tree: list[tuple[str, list[tuple[str, Path]], Path]]) -> str:
    parts = []
    for idx, (sec_label, subsecs, _sec_path) in enumerate(tree):
        color = COLOR_CYCLE[idx % len(COLOR_CYCLE)]
        sec_node = [f"  child[concept color={color}] {{ node[concept] {{{tex_escape(sec_label)}}}"]
        for sub_label, _ in subsecs:
            sec_node.append(f"    child {{ node[concept] {{{tex_escape(sub_label)}}} }}")
        sec_node.append("  }")
        parts.append("\n".join(sec_node))
    return "\n".join(parts)


def write_paths_file(path_file: Path, trace_root: Path, tree: list[tuple[str, list[tuple[str, Path]], Path]]) -> None:
    lines = [
        "# Survey Mindmap Node-to-Path Mapping",
        "",
        "Generated from folder structure under:",
        f"- {trace_root}",
        "",
        "## Section Nodes",
    ]
    for sec_label, subsecs, sec_path in tree:
        rel_sec = sec_path.relative_to(trace_root)
        lines.append(f"- {sec_label}: ./{rel_sec}")
        for sub_label, sub_path in subsecs:
            rel_sub = sub_path.relative_to(trace_root)
            lines.append(f"  - {sub_label}: ./{rel_sub}")
    path_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_tex(output_dir: Path, tex_file: Path) -> None:
    if shutil.which("latexmk") is None:
        raise RuntimeError("latexmk not found in PATH")
    subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", tex_file.name],
        cwd=output_dir,
        check=True,
    )


def export_png(output_dir: Path, pdf_file: Path, png_file: Path) -> bool:
    tool = shutil.which("pdftoppm")
    if tool is None:
        print("Warning: pdftoppm not found; skip PNG export (install poppler to enable).")
        return False
    subprocess.run(
        [tool, "-png", "-singlefile", pdf_file.name, png_file.stem],
        cwd=output_dir,
        check=True,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate survey mindmap from survey_trace")
    parser.add_argument(
        "--trace-root",
        default="my idea/survey_trace",
        help="Path to trace root folder",
    )
    parser.add_argument(
        "--template",
        default="templates/MINDMAP_TIKZ_TEMPLATE.tex",
        help="Path to TikZ template",
    )
    parser.add_argument(
        "--out-dir",
        default="my idea/survey_trace/mindmap",
        help="Output directory",
    )
    parser.add_argument(
        "--root-label",
        default="Ultra-Low Bit LLM Survey",
        help="Root label shown at center",
    )
    parser.add_argument("--compile", action="store_true", help="Compile TeX to PDF")
    parser.add_argument("--png", action="store_true", help="Export PNG from generated PDF")
    args = parser.parse_args()

    trace_root = Path(args.trace_root)
    template_path = Path(args.template)
    out_dir = Path(args.out_dir)

    if not trace_root.exists():
        raise FileNotFoundError(f"trace root not found: {trace_root}")
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_path}")

    tree = collect_tree(trace_root)
    if not tree:
        raise RuntimeError("no section folders found under trace root")

    level1_angle = max(12, int(math.floor(360 / len(tree))))
    children = build_children(tree)

    template = template_path.read_text(encoding="utf-8")
    tex_content = (
        template.replace("__ROOT_LABEL__", tex_escape(args.root_label))
        .replace("__LEVEL1_ANGLE__", str(level1_angle))
        .replace("__CHILDREN__", children)
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    tex_file = out_dir / "survey_mindmap.tex"
    tex_file.write_text(tex_content, encoding="utf-8")

    paths_file = out_dir / "survey_mindmap_paths.md"
    write_paths_file(paths_file, trace_root, tree)

    print(f"Generated: {tex_file}")
    print(f"Generated: {paths_file}")

    if args.compile:
        compile_tex(out_dir, tex_file)
        pdf_file = out_dir / "survey_mindmap.pdf"
        print(f"Generated: {pdf_file}")
        if args.png:
            png_file = out_dir / "survey_mindmap.png"
            ok = export_png(out_dir, pdf_file, png_file)
            if ok:
                print(f"Generated: {png_file}")
    elif args.png:
        raise RuntimeError("--png requires --compile")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
