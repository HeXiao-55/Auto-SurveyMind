"""Repo Reproduce stage — execute setup plans and run demos with real env isolation.

Progressive reproduction:
1. Create an isolated environment (venv / conda run / docker build) per repo
2. Install dependencies inside that environment
3. Run demo commands
4. Validate output (exit codes, tracebacks)
5. Write reproduction_log.json, pipeline_summary.md, adaptation_candidates.json

Returns 0 on success, 1 on failure.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


STEP_TIMEOUT = 300   # 5 min per setup step
DEMO_TIMEOUT = 600   # 10 min per demo command
ENV_TIMEOUT  = 600   # 10 min for conda env creation


# ---------------------------------------------------------------------------
# Low-level subprocess helper
# ---------------------------------------------------------------------------

def _run_cmd(
    cmd: str,
    cwd: Path,
    timeout: int = STEP_TIMEOUT,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a shell command and return a structured result dict."""
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "cmd": cmd,
            "exit_code": result.returncode,
            "stdout_tail": result.stdout[-2000:] if result.stdout else "",
            "stderr_tail": result.stderr[-2000:] if result.stderr else "",
            "elapsed_s": elapsed,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd,
            "exit_code": -1,
            "stdout_tail": "",
            "stderr_tail": f"TIMEOUT after {timeout}s",
            "elapsed_s": timeout,
            "success": False,
        }
    except Exception as exc:
        return {
            "cmd": cmd,
            "exit_code": -2,
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "elapsed_s": round(time.time() - start, 2),
            "success": False,
        }


# ---------------------------------------------------------------------------
# Environment isolation helpers
# ---------------------------------------------------------------------------

def _has_traceback(text: str) -> bool:
    return "Traceback (most recent call last)" in text or "Error:" in text


def _setup_venv(repo_path: Path, verbose: bool) -> tuple[bool, str, list[dict]]:
    """Create a .venv inside repo_path. Returns (ok, python_bin, step_results)."""
    venv_dir = repo_path / ".venv"
    results: list[dict] = []

    if not venv_dir.exists():
        r = _run_cmd(
            f"{sys.executable} -m venv {venv_dir}",
            cwd=repo_path,
            timeout=120,
        )
        results.append({"type": "env_create", **r})
        if not r["success"]:
            if verbose:
                print(f"        venv creation failed: {r['stderr_tail'][:200]}")
            return False, "", results
    else:
        results.append({"type": "env_create", "cmd": "venv already exists", "skipped": True, "success": True})

    # Detect the venv python binary
    py_bin = str(venv_dir / "bin" / "python")
    if not Path(py_bin).exists():
        py_bin = str(venv_dir / "Scripts" / "python.exe")  # Windows
    if not Path(py_bin).exists():
        results.append({"type": "env_create", "cmd": "locate venv python", "success": False,
                        "stderr_tail": f"python binary not found in {venv_dir}"})
        return False, "", results

    return True, py_bin, results


def _install_deps_venv(
    py_bin: str, repo_path: Path, verbose: bool
) -> tuple[bool, list[dict]]:
    """Install dependencies into an existing venv. Returns (ok, step_results)."""
    results: list[dict] = []
    pip = f"{py_bin} -m pip install --quiet"

    if (repo_path / "requirements.txt").exists():
        r = _run_cmd(f"{pip} -r requirements.txt", cwd=repo_path, timeout=STEP_TIMEOUT)
        results.append({"type": "install_deps", "cmd": f"{pip} -r requirements.txt", **r})
        if not r["success"]:
            # Retry once without version pins (best-effort)
            r2 = _run_cmd(
                f"{pip} --no-deps -r requirements.txt",
                cwd=repo_path,
                timeout=STEP_TIMEOUT,
            )
            results.append({"type": "install_deps_retry", "cmd": f"{pip} --no-deps -r requirements.txt", **r2})
            if not r2["success"]:
                return False, results
    elif (repo_path / "pyproject.toml").exists() or (repo_path / "setup.py").exists():
        r = _run_cmd(f"{pip} -e .", cwd=repo_path, timeout=STEP_TIMEOUT)
        results.append({"type": "install_deps", **r})
        if not r["success"]:
            return False, results
    else:
        results.append({"type": "install_deps", "cmd": "no dependency file found", "skipped": True, "success": True})

    return True, results


def _setup_conda(
    env_name: str, plan: dict[str, Any], repo_path: Path, verbose: bool
) -> tuple[bool, str, list[dict]]:
    """Create/reuse a conda env. Returns (ok, conda_run_prefix, step_results)."""
    results: list[dict] = []
    conda_bin = shutil.which("conda") or "conda"

    # Check if env already exists
    check = subprocess.run(
        [conda_bin, "env", "list"], capture_output=True, text=True, timeout=30
    )
    env_exists = env_name in (check.stdout or "")

    if not env_exists:
        if plan.get("has_environment_yml"):
            env_file = "environment.yml" if (repo_path / "environment.yml").exists() else "environment.yaml"
            r = _run_cmd(
                f"{conda_bin} env create -f {env_file} -n {env_name} --quiet",
                cwd=repo_path,
                timeout=ENV_TIMEOUT,
            )
        else:
            r = _run_cmd(
                f"{conda_bin} create -n {env_name} python=3.10 -y --quiet",
                cwd=repo_path,
                timeout=ENV_TIMEOUT,
            )
        results.append({"type": "env_create", **r})
        if not r["success"]:
            if verbose:
                print(f"        conda env creation failed: {r['stderr_tail'][:200]}")
            return False, "", results
    else:
        results.append({"type": "env_create", "cmd": f"conda env {env_name} already exists", "skipped": True, "success": True})

    # Install deps if not handled by environment.yml
    if not plan.get("has_environment_yml"):
        pip_cmd = f"{conda_bin} run -n {env_name} pip install --quiet"
        if (repo_path / "requirements.txt").exists():
            r = _run_cmd(
                f"{pip_cmd} -r requirements.txt", cwd=repo_path, timeout=STEP_TIMEOUT
            )
            results.append({"type": "install_deps", **r})

    run_prefix = f"{conda_bin} run -n {env_name}"
    return True, run_prefix, results


def _build_docker(repo_path: Path, tag: str, verbose: bool) -> tuple[bool, list[dict]]:
    """Build Docker image. Returns (ok, step_results)."""
    results: list[dict] = []
    r = _run_cmd(
        f"docker build -t {tag} .",
        cwd=repo_path,
        timeout=ENV_TIMEOUT,
    )
    results.append({"type": "env_create", **r})
    if not r["success"] and verbose:
        print(f"        docker build failed: {r['stderr_tail'][:200]}")
    return r["success"], results


# ---------------------------------------------------------------------------
# Core execution logic
# ---------------------------------------------------------------------------

def _execute_setup_plan(plan: dict[str, Any], verbose: bool = False) -> dict[str, Any]:
    """Set up environment and run demos for one repo. Returns a result dict."""
    repo_path = Path(plan["repo_path"])
    if not repo_path.exists():
        return {
            "paper_id": plan["paper_id"],
            "status": "error",
            "error": f"Repo path does not exist: {repo_path}",
            "steps_results": [],
            "demo_results": [],
        }

    env_type = plan.get("env_type", "unknown")
    safe_id = plan["paper_id"].replace("/", "_").replace(".", "_")
    steps_results: list[dict] = []
    run_prefix = ""        # prefix for demo commands (e.g. "conda run -n env")
    py_bin = sys.executable  # fallback: current python
    env_ok = False

    # ---- 1. Environment creation ----
    if env_type == "pip":
        ok, py_bin, venv_steps = _setup_venv(repo_path, verbose)
        steps_results.extend(venv_steps)
        if ok:
            ok2, dep_steps = _install_deps_venv(py_bin, repo_path, verbose)
            steps_results.extend(dep_steps)
            env_ok = ok2
        # Commands run via the venv python
        run_prefix = str(Path(py_bin).parent)  # directory for bin path

    elif env_type == "conda":
        env_name = f"repro_{safe_id}"
        ok, conda_run, conda_steps = _setup_conda(env_name, plan, repo_path, verbose)
        steps_results.extend(conda_steps)
        if ok:
            run_prefix = conda_run  # e.g. "conda run -n repro_xxx"
            env_ok = True

    elif env_type == "docker":
        docker_tag = f"repro_{safe_id}"
        ok, docker_steps = _build_docker(repo_path, docker_tag, verbose)
        steps_results.extend(docker_steps)
        env_ok = ok
        # Docker demos need explicit `docker run` — skip automated demo for now
        if ok:
            return {
                "paper_id": plan["paper_id"],
                "repo_url": plan.get("repo_url", ""),
                "repo_path": str(repo_path),
                "status": "setup_ok_no_demo",
                "env_type": env_type,
                "gpu_required": plan.get("gpu_required", False),
                "steps_results": steps_results,
                "demo_results": [],
                "note": "Docker build succeeded. Run demo manually: docker run repro_" + safe_id,
                "attempted_at": datetime.now().isoformat(),
            }

    else:
        # unknown / npm / cargo — try to run without isolation as best-effort
        env_ok = True
        steps_results.append({
            "type": "env_create",
            "cmd": "no isolation (unknown env type)",
            "skipped": True,
            "success": True,
        })

    if not env_ok:
        return {
            "paper_id": plan["paper_id"],
            "repo_url": plan.get("repo_url", ""),
            "repo_path": str(repo_path),
            "status": "setup_failed",
            "env_type": env_type,
            "gpu_required": plan.get("gpu_required", False),
            "steps_results": steps_results,
            "demo_results": [],
            "attempted_at": datetime.now().isoformat(),
        }

    # ---- 2. Download data steps (optional, best-effort) ----
    for step in plan.get("setup_steps", []):
        if step.get("type") != "download_data":
            continue
        cmd = step.get("cmd", "")
        if not cmd:
            continue
        if verbose:
            print(f"      data: {cmd[:80]}")
        r = _run_cmd(cmd, cwd=repo_path, timeout=STEP_TIMEOUT)
        steps_results.append({"type": "download_data", **r})
        # data download failure is non-fatal — log and continue

    # ---- 3. Demo commands ----
    demo_results: list[dict] = []
    for demo_cmd in plan.get("demo_commands", [])[:3]:
        if not demo_cmd.strip():
            continue

        # Patch command to use isolated environment
        patched = _patch_demo_cmd(demo_cmd, env_type, run_prefix, py_bin, repo_path)
        if verbose:
            print(f"      demo: {patched[:80]}")

        r = _run_cmd(patched, cwd=repo_path, timeout=DEMO_TIMEOUT)
        demo_results.append(r)

        if r["success"] and not _has_traceback(r["stderr_tail"]):
            if verbose:
                print(f"        OK ({r['elapsed_s']}s)")
            break
        if verbose:
            print(f"        FAILED (exit {r['exit_code']})")

    # ---- 4. Determine status ----
    any_demo_passed = any(d.get("success") and not _has_traceback(d.get("stderr_tail", "")) for d in demo_results)
    if any_demo_passed:
        status = "demo_passed"
    elif not plan.get("demo_commands"):
        status = "setup_ok_no_demo"
    else:
        status = "demo_failed"

    return {
        "paper_id": plan["paper_id"],
        "repo_url": plan.get("repo_url", ""),
        "repo_path": str(repo_path),
        "status": status,
        "env_type": env_type,
        "gpu_required": plan.get("gpu_required", False),
        "steps_results": steps_results,
        "demo_results": demo_results,
        "attempted_at": datetime.now().isoformat(),
    }


def _patch_demo_cmd(
    cmd: str,
    env_type: str,
    run_prefix: str,
    py_bin: str,
    repo_path: Path,
) -> str:
    """Rewrite a demo command to use the isolated environment's python/pip."""
    cmd = cmd.strip()

    if env_type == "conda" and run_prefix:
        # Prefix with `conda run -n <env>` unless already prefixed
        if not cmd.startswith(run_prefix):
            return f"{run_prefix} {cmd}"
        return cmd

    if env_type == "pip" and py_bin and py_bin != sys.executable:
        # Replace bare `python` / `python3` with the venv python
        cmd = cmd.replace("python3 ", f"{py_bin} ").replace("python ", f"{py_bin} ")
        if cmd.startswith("python") and not cmd.startswith(py_bin):
            cmd = f"{py_bin} {cmd.split(None, 1)[1] if ' ' in cmd else ''}"
        return cmd

    return cmd


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def _write_pipeline_summary(
    gate7_dir: Path,
    results: list[dict[str, Any]],
) -> None:
    """Write pipeline_summary.md and adaptation_candidates.json."""
    passed = [r for r in results if r["status"] == "demo_passed"]
    setup_ok = [r for r in results if r["status"] == "setup_ok_no_demo"]
    failed = [r for r in results if r["status"] in ("demo_failed", "setup_failed", "error")]

    # adaptation_candidates.json — input for /repo-adapt skill
    candidates = [
        {
            "paper_id": r["paper_id"],
            "repo_url": r.get("repo_url", ""),
            "repo_path": r.get("repo_path", ""),
            "env_type": r.get("env_type", ""),
            "gpu_required": r.get("gpu_required", False),
            "successful_demo": next(
                (d["cmd"] for d in r.get("demo_results", []) if d.get("success")), None
            ),
        }
        for r in passed
    ]
    (gate7_dir / "adaptation_candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # pipeline_summary.md
    lines = [
        "# Reproduction Pipeline Summary",
        "",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Results Overview",
        "",
        f"- Total attempted : {len(results)}",
        f"- Demo passed     : {len(passed)}",
        f"- Setup OK (no demo): {len(setup_ok)}",
        f"- Failed          : {len(failed)}",
        "",
    ]

    if passed:
        lines += [
            "## Successfully Reproduced",
            "",
            "| Paper ID | Repo | Demo Command |",
            "|----------|------|--------------|",
        ]
        for r in passed:
            demo_cmd = next(
                (d["cmd"] for d in r.get("demo_results", []) if d.get("success")), "N/A"
            )
            repo_slug = r.get("repo_url", "").split("github.com/")[-1]
            lines.append(f"| {r['paper_id']} | [{repo_slug}]({r.get('repo_url','')}) | `{demo_cmd[:60]}` |")
        lines.append("")

    if failed:
        lines += [
            "## Failed (needs manual attention)",
            "",
            "| Paper ID | Status | Error Summary |",
            "|----------|--------|---------------|",
        ]
        for r in failed:
            err = ""
            if r.get("demo_results"):
                err = r["demo_results"][-1].get("stderr_tail", "")[:80]
            elif r.get("steps_results"):
                for s in reversed(r["steps_results"]):
                    if not s.get("success") and not s.get("skipped"):
                        err = s.get("stderr_tail", "")[:80]
                        break
            lines.append(f"| {r['paper_id']} | {r['status']} | {err} |")
        lines.append("")

    lines += [
        "## Next Steps",
        "",
        "- For failed repos: inspect `reproduction_log.json` for full error output",
        "- For adaptation: run `/repo-adapt` with candidates from `adaptation_candidates.json`",
        "- To reproduce more: increase `--reproduction-max-repos` and re-run `repo-reproduce`",
    ]

    (gate7_dir / "pipeline_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------

def run_repo_reproduce(args) -> int:
    """Execute reproduction plans for all cloned repos."""
    gate7_dir = Path(args.gate7_dir)
    setups_dir = gate7_dir / "setups"
    log_path = gate7_dir / "reproduction_log.json"

    if not setups_dir.exists():
        print(f"ERROR: setups directory not found at {setups_dir}")
        print("Run repo-setup first.")
        return 1

    setup_files = sorted(setups_dir.glob("*_setup.json"))
    if not setup_files:
        print("WARNING: No setup plans found in setups/")
        return 0

    max_repos = getattr(args, "reproduction_max_repos", 10)
    verbose = getattr(args, "verbose", False)
    setup_files = setup_files[:max_repos]

    print(f"Reproducing {len(setup_files)} repositories...")
    results: list[dict[str, Any]] = []

    for idx, setup_file in enumerate(setup_files, start=1):
        plan = json.loads(setup_file.read_text(encoding="utf-8"))
        paper_id = plan.get("paper_id", "unknown")
        gpu_req = plan.get("gpu_required", False)
        print(f"  [{idx}/{len(setup_files)}] {paper_id}  (env={plan.get('env_type','?')}, gpu={gpu_req})")

        result = _execute_setup_plan(plan, verbose=verbose)
        results.append(result)

        icon = {
            "demo_passed": "PASS",
            "setup_ok_no_demo": "SETUP_OK",
            "demo_failed": "DEMO_FAIL",
            "setup_failed": "SETUP_FAIL",
            "error": "ERROR",
        }.get(result["status"], "?")
        print(f"    -> {icon}")

    # Write reproduction log
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_attempted": len(results),
        "demo_passed":  sum(1 for r in results if r["status"] == "demo_passed"),
        "setup_ok":     sum(1 for r in results if r["status"] == "setup_ok_no_demo"),
        "demo_failed":  sum(1 for r in results if r["status"] == "demo_failed"),
        "setup_failed": sum(1 for r in results if r["status"] == "setup_failed"),
        "errors":       sum(1 for r in results if r["status"] == "error"),
        "repos": results,
    }
    log_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Write summary documents
    _write_pipeline_summary(gate7_dir, results)

    print(f"\nReproduction summary:")
    print(f"  Demo passed     : {summary['demo_passed']}")
    print(f"  Setup OK        : {summary['setup_ok']}")
    print(f"  Demo failed     : {summary['demo_failed']}")
    print(f"  Setup failed    : {summary['setup_failed']}")
    print(f"  Errors          : {summary['errors']}")
    print(f"  Log             : {log_path}")
    print(f"  Summary         : {gate7_dir / 'pipeline_summary.md'}")
    print(f"  Adapt candidates: {gate7_dir / 'adaptation_candidates.json'}")
    return 0
