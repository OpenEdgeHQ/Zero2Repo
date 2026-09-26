#!/usr/bin/env python3
"""Legacy in-container milestone judge (multi-step scoring).

Deprecated: released benchmark tasks use ``final_judge.py`` (single final-step
tests under ``/tests/final``). This module remains for backward compatibility.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(os.environ.get("CODING_BENCH_WORKSPACE", "/app"))
TESTS_ROOT = Path(os.environ.get("CODING_BENCH_TESTS", "/tests/milestones"))
VERIFIER_DIR = Path(os.environ.get("CODING_BENCH_VERIFIER_DIR", "/logs/verifier"))
TASK_TOML = Path(os.environ.get("CODING_BENCH_TASK_TOML", "/task.toml"))


class JudgeError(RuntimeError):
    """Raised when the judge cannot run the tests (a harness problem)."""


def _load_runner_metadata() -> dict:
    """Load runner metadata from task.toml metadata.runner."""
    candidates = [
        TASK_TOML,
        WORKSPACE / "task.toml",
        Path.cwd() / "task.toml",
        Path("/tests") / "task.toml",
    ]
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            return {}
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with open(candidate, "rb") as f:
                data = tomllib.load(f)
            runner = data.get("metadata", {}).get("runner", {})
            if runner:
                if "test_command_template" not in runner and "test_command" in runner:
                    runner = {**runner, "test_command_template": runner["test_command"]}
                return runner
        except Exception:
            continue
    return {}


def _discover_steps(tests_root: Path) -> list[tuple[int, Path, dict]]:
    """Return (step_num, step_dir, test_manifest) for each milestone."""
    steps: list[tuple[int, Path, dict]] = []
    for step_dir in sorted(tests_root.glob("step_*")):
        if not step_dir.is_dir():
            continue
        try:
            num = int(step_dir.name.split("_", 1)[1])
        except (IndexError, ValueError):
            continue
        tm_path = step_dir / "test_manifest.json"
        if not tm_path.exists():
            raise JudgeError(f"step {num} missing test_manifest.json at {tm_path}")
        try:
            manifest = json.loads(tm_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JudgeError(f"invalid test_manifest.json for step {num}: {exc}") from exc
        if not manifest.get("test_files"):
            raise JudgeError(f"step {num} test_manifest.json has empty test_files")
        if not manifest.get("test_command", "").strip():
            raise JudgeError(f"step {num} test_manifest.json missing test_command")
        steps.append((num, step_dir, manifest))
    steps.sort(key=lambda item: item[0])
    return steps


def _ensure_importable(workspace: Path, runner: dict) -> dict:
    install_cmd = runner.get("install_command", "")
    if not install_cmd.strip():
        return {"install_command": install_cmd, "editable_install": "skipped"}
    proc = subprocess.run(
        install_cmd,
        shell=True,
        cwd=str(workspace),
        capture_output=True,
        text=True,
    )
    return {
        "install_command": install_cmd,
        "editable_install": "ok" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
    }


def _parse_counts(output: str) -> tuple[int, int]:
    passed = int(m.group(1)) if (m := re.search(r"(\d+)\s+passed", output, re.I)) else 0
    failed = int(m.group(1)) if (m := re.search(r"(\d+)\s+failed", output, re.I)) else 0
    errors = int(m.group(1)) if (m := re.search(r"(\d+)\s+error", output, re.I)) else 0
    return passed, failed + errors


def _classify(returncode: int) -> str:
    if returncode == 0:
        return "passed"
    if returncode == 1:
        return "failed"
    if returncode == 5:
        return "no_tests"
    return "judge_error"


def _run_step(step_num: int, step_dir: Path, manifest: dict, workspace: Path) -> dict:
    workdir_rel = manifest.get("workdir", ".")
    workdir = workspace if workdir_rel == "." else workspace / workdir_rel

    test_files = []
    for rel in manifest.get("test_files", []):
        p = step_dir / rel
        if not p.is_file():
            p = step_dir / "tests" / Path(rel).name
        if p.is_file():
            test_files.append(p)

    cmd = manifest.get("test_command", "")
    if "{test_files}" in cmd or "{test_dir}" in cmd:
        cmd = cmd.replace("{test_files}", " ".join(str(p) for p in test_files))
        cmd = cmd.replace("{test_dir}", str(step_dir / "tests"))

    if not cmd.strip():
        raise JudgeError(f"empty test_command for step {step_num}")

    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(workdir), capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise JudgeError(f"test command not available: {exc}") from exc

    output = proc.stdout + proc.stderr
    status = _classify(proc.returncode)
    if status == "judge_error":
        raise JudgeError(
            f"test command failed for step {step_num} (exit {proc.returncode}).\n" + output[-2000:]
        )
    passed, failed = _parse_counts(output)
    log_path = VERIFIER_DIR / f"milestone_step_{step_num}.log"
    log_path.write_text(output, encoding="utf-8")
    return {
        "id": step_num,
        "status": "passed" if status == "passed" else "failed",
        "passed": passed,
        "failed": failed,
        "total": passed + failed,
        "exit_code": proc.returncode,
        "log": str(log_path),
    }


def main() -> int:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"reward": 0.0, "judge_error": None, "milestones": []}

    try:
        if not WORKSPACE.is_dir():
            raise JudgeError(f"workspace not found: {WORKSPACE}")
        steps = _discover_steps(TESTS_ROOT)
        if not steps:
            raise JudgeError(f"no milestone tests found under {TESTS_ROOT}")

        runner = _load_runner_metadata()
        report["runner"] = runner
        report["install"] = _ensure_importable(WORKSPACE, runner) if runner else {}

        results = [_run_step(num, step_dir, manifest, WORKSPACE) for num, step_dir, manifest in steps]
        report["milestones"] = results

        total = len(results)
        passed = sum(1 for r in results if r["status"] == "passed")
        report["milestones_passed"] = passed
        report["milestones_total"] = total
        report["reward"] = passed / total if total else 0.0
    except JudgeError as exc:
        report["judge_error"] = str(exc)
        report["reward"] = 0.0
        print(f"JUDGE ERROR: {exc}", file=sys.stderr)

    (VERIFIER_DIR / "milestone_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    flat = {
        "reward": report["reward"],
        "milestones_passed": report.get("milestones_passed", 0),
        "milestones_total": report.get("milestones_total", 0),
    }
    (VERIFIER_DIR / "reward.json").write_text(json.dumps(flat), encoding="utf-8")
    (VERIFIER_DIR / "reward.txt").write_text(str(report["reward"]), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 1 if report["judge_error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
