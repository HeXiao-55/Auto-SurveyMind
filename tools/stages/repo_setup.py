"""Repo Setup stage — clone discovered repos and parse READMEs into structured setup plans.

For each repo in code_repos.json:
1. git clone --depth 1
2. Parse README.md + environment files (requirements.txt, environment.yml, Dockerfile, etc.)
3. Generate a machine-readable setup plan JSON

Returns 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _clone_repo(repo_url: str, dest: Path, timeout: int = 120) -> bool:
    """Shallow-clone a repo. Returns True on success."""
    if dest.exists() and (dest / ".git").exists():
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", repo_url, str(dest)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def _find_readme(repo_path: Path) -> Path | None:
    """Find the primary README file in a repo."""
    candidates = [
        "README.md", "readme.md", "Readme.md",
        "README.rst", "README.txt", "README",
    ]
    for name in candidates:
        p = repo_path / name
        if p.exists():
            return p
    return None


def _find_install_docs(repo_path: Path) -> list[Path]:
    """Find installation/setup documentation files."""
    candidates = [
        "INSTALL.md", "INSTALLATION.md", "install.md",
        "docs/install.md", "docs/INSTALL.md", "docs/installation.md",
        "docs/getting_started.md", "docs/setup.md",
        "SETUP.md", "setup.md",
    ]
    found = []
    for name in candidates:
        p = repo_path / name
        if p.exists():
            found.append(p)
    return found


def _detect_env_type(repo_path: Path) -> str:
    """Detect the environment/package manager type."""
    if (repo_path / "environment.yml").exists() or (repo_path / "environment.yaml").exists():
        return "conda"
    if (repo_path / "Dockerfile").exists():
        return "docker"
    if (repo_path / "pyproject.toml").exists():
        return "pip"
    if (repo_path / "requirements.txt").exists():
        return "pip"
    if (repo_path / "setup.py").exists():
        return "pip"
    if (repo_path / "package.json").exists():
        return "npm"
    if (repo_path / "Cargo.toml").exists():
        return "cargo"
    return "unknown"


def _detect_language(repo_path: Path) -> str:
    """Detect primary programming language."""
    py_files = list(repo_path.glob("**/*.py"))
    js_files = list(repo_path.glob("**/*.js")) + list(repo_path.glob("**/*.ts"))
    rs_files = list(repo_path.glob("**/*.rs"))

    counts = {"python": len(py_files), "javascript": len(js_files), "rust": len(rs_files)}
    if max(counts.values()) == 0:
        return "unknown"
    return max(counts, key=counts.get)


def _detect_gpu_required(readme_text: str, repo_path: Path) -> bool:
    """Heuristic: does this project require a GPU?"""
    gpu_indicators = [
        "cuda", "gpu", "nvidia", "torch.cuda", "tensorflow-gpu",
        "CUDA_VISIBLE_DEVICES", "nvidia-smi", "nccl",
    ]
    text_lower = readme_text.lower()
    for indicator in gpu_indicators:
        if indicator.lower() in text_lower:
            return True
    # Check requirements files
    for req_file in ["requirements.txt", "environment.yml", "setup.py"]:
        p = repo_path / req_file
        if p.exists():
            content = p.read_text(encoding="utf-8", errors="replace").lower()
            if any(ind.lower() in content for ind in ["torch", "tensorflow", "jax"]):
                return True
    return False


def _extract_setup_steps(readme_text: str, env_type: str, repo_path: Path) -> list[dict[str, Any]]:
    """Extract setup steps from README and environment files."""
    steps: list[dict[str, Any]] = []
    step_num = 0

    if env_type == "conda":
        env_file = "environment.yml" if (repo_path / "environment.yml").exists() else "environment.yaml"
        step_num += 1
        steps.append({
            "step": step_num,
            "type": "env_create",
            "cmd": f"conda env create -f {env_file}",
            "note": "Create conda environment from spec file",
        })
    elif env_type == "pip":
        step_num += 1
        steps.append({
            "step": step_num,
            "type": "env_create",
            "cmd": "python -m venv .venv && source .venv/bin/activate",
            "note": "Create isolated virtual environment",
        })
        if (repo_path / "requirements.txt").exists():
            step_num += 1
            steps.append({
                "step": step_num,
                "type": "install_deps",
                "cmd": "pip install -r requirements.txt",
            })
        elif (repo_path / "pyproject.toml").exists():
            step_num += 1
            steps.append({
                "step": step_num,
                "type": "install_deps",
                "cmd": "pip install -e .",
            })
        elif (repo_path / "setup.py").exists():
            step_num += 1
            steps.append({
                "step": step_num,
                "type": "install_deps",
                "cmd": "pip install -e .",
            })
    elif env_type == "docker":
        step_num += 1
        steps.append({
            "step": step_num,
            "type": "env_create",
            "cmd": "docker build -t repro_env .",
            "note": "Build Docker image",
        })

    # Parse README bash blocks for data-download commands only.
    # run_demo commands go into demo_commands (extracted separately) — never here.
    code_blocks = re.findall(r"```(?:bash|shell|sh)?\s*\n(.*?)```", readme_text, re.DOTALL)
    data_patterns = re.compile(
        r"(wget|curl|gdown|kaggle|huggingface-cli|hf\s)", re.IGNORECASE
    )

    for block in code_blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
        for line in lines:
            if data_patterns.search(line):
                step_num += 1
                steps.append({
                    "step": step_num,
                    "type": "download_data",
                    "cmd": line,
                    "note": "Data download command from README",
                })

    return steps


def _extract_demo_commands(readme_text: str) -> list[str]:
    """Extract likely demo/example run commands from README."""
    demos: list[str] = []
    demo_section = re.search(
        r"(?:##?\s*(?:Quick\s*Start|Getting\s*Started|Usage|Demo|Example|Run|Inference).*?)\n(.*?)(?=\n##|\Z)",
        readme_text,
        re.IGNORECASE | re.DOTALL,
    )
    if demo_section:
        code_blocks = re.findall(r"```(?:bash|shell|sh|python)?\s*\n(.*?)```", demo_section.group(1), re.DOTALL)
        for block in code_blocks:
            for line in block.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("$"):
                    demos.append(line.lstrip("$ "))
                elif line.startswith("$ "):
                    demos.append(line[2:])

    if not demos:
        # Look for common demo patterns anywhere
        patterns = [
            r"python\s+(?:demo|example|test|inference|run|main)\S*\.py",
            r"bash\s+(?:demo|example|run|test)\S*\.sh",
        ]
        for pat in patterns:
            matches = re.findall(pat, readme_text)
            demos.extend(matches[:3])

    return demos[:5]


def _generate_setup_plan(paper_id: str, repo_url: str, repo_path: Path) -> dict[str, Any]:
    """Generate a structured setup plan for a cloned repo."""
    readme_path = _find_readme(repo_path)
    readme_text = ""
    if readme_path:
        readme_text = readme_path.read_text(encoding="utf-8", errors="replace")

    env_type = _detect_env_type(repo_path)
    language = _detect_language(repo_path)
    gpu_required = _detect_gpu_required(readme_text, repo_path)
    setup_steps = _extract_setup_steps(readme_text, env_type, repo_path)
    demo_commands = _extract_demo_commands(readme_text)

    return {
        "paper_id": paper_id,
        "repo_url": repo_url,
        "repo_path": str(repo_path),
        "language": language,
        "env_type": env_type,
        "gpu_required": gpu_required,
        "has_readme": readme_path is not None,
        "has_dockerfile": (repo_path / "Dockerfile").exists(),
        "has_requirements": (repo_path / "requirements.txt").exists(),
        "has_environment_yml": (repo_path / "environment.yml").exists() or (repo_path / "environment.yaml").exists(),
        "setup_steps": setup_steps,
        "demo_commands": demo_commands,
        "install_docs": [str(p.relative_to(repo_path)) for p in _find_install_docs(repo_path)],
        "estimated_time": "5-15min",
        "generated_at": datetime.now().isoformat(),
    }


def run_repo_setup(args) -> int:
    """Clone discovered repos and generate setup plans."""
    gate6_dir = Path(args.gate6_dir)
    gate7_dir = Path(args.gate7_dir)
    repos_dir = gate7_dir / "repos"
    setups_dir = gate7_dir / "setups"

    repos_dir.mkdir(parents=True, exist_ok=True)
    setups_dir.mkdir(parents=True, exist_ok=True)

    # Load discovered repos
    code_repos_path = gate6_dir / "code_repos.json"
    if not code_repos_path.exists():
        print(f"ERROR: code_repos.json not found at {code_repos_path}")
        print("Run code-discover first.")
        return 1

    repos = json.loads(code_repos_path.read_text(encoding="utf-8"))
    if not repos:
        print("WARNING: No repos to clone")
        return 0

    verbose = getattr(args, "verbose", False)
    clone_timeout = getattr(args, "reproduction_timeout", 120)
    max_repos = getattr(args, "reproduction_max_repos", 10)
    repos = repos[:max_repos]

    print(f"Setting up {len(repos)} repositories...")
    results = []

    for idx, repo in enumerate(repos, start=1):
        paper_id = repo["paper_id"]
        repo_url = repo["repo_url"]
        safe_id = paper_id.replace("/", "_")
        dest = repos_dir / safe_id

        print(f"  [{idx}/{len(repos)}] Cloning {repo_url}...")

        clone_ok = _clone_repo(repo_url, dest, timeout=clone_timeout)
        if not clone_ok:
            print(f"    FAILED to clone {repo_url}")
            results.append({"paper_id": paper_id, "status": "clone_failed"})
            continue

        plan = _generate_setup_plan(paper_id, repo_url, dest)
        plan_path = setups_dir / f"{safe_id}_setup.json"
        plan_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        results.append({
            "paper_id": paper_id,
            "status": "ready",
            "setup_plan": str(plan_path),
            "demo_commands": plan["demo_commands"],
            "env_type": plan["env_type"],
        })

        if verbose:
            print(f"    OK: {plan['env_type']}, {len(plan['setup_steps'])} steps, {len(plan['demo_commands'])} demos")

    # Write summary log
    log_path = gate7_dir / "reproduction_log.json"
    log_data = {
        "generated_at": datetime.now().isoformat(),
        "total_repos": len(repos),
        "cloned": sum(1 for r in results if r["status"] == "ready"),
        "failed": sum(1 for r in results if r["status"] != "ready"),
        "repos": results,
    }
    log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nRepo setup complete:")
    print(f"  Cloned: {log_data['cloned']}/{len(repos)}")
    print(f"  Failed: {log_data['failed']}")
    print(f"  Setup plans: {setups_dir}")
    return 0
