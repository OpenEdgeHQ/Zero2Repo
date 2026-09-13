"""Release and environment checks that discover cases from their manifests."""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

from .assets import load_case
from .recipe import load_lock, validate_lock_env_install, stage_benchmark_bundle
from .state import platform_name


def validate_case(case_dir: Path, *, allow_leakage: bool = False, require_denylist: bool = False) -> dict:
    from .run_case import _check_public_leakage
    from .denylist import load_denylist
    case_dir = Path(case_dir)
    case = load_case(case_dir)
    manifest = json.loads((case_dir / "source/manifest.json").read_text())
    if manifest.get("case_id", case_dir.name) != case_dir.name:
        raise ValueError("manifest case_id must match its directory")
    _check_public_leakage(case, allow_leakage=allow_leakage)
    lock = load_lock(case_dir)
    validate_lock_env_install(lock)
    if lock["base_image"].startswith("codingbench-base/") and platform_name() != "linux/amd64":
        raise ValueError("the bundled base requires linux/amd64")
    runner = manifest["runner"]
    for name in ("install_command", "build_command"):
        if str(runner.get(name) or "").strip() != str(lock["runner"].get(name) or "").strip():
            raise ValueError(f"{name} differs between manifest and recipe.lock")
    final = case_dir / "milestones/final"
    tests = case.assets.acceptance.test_manifest
    if not tests.get("test_files"):
        raise ValueError("hidden suite has no test_files")
    if not (tests.get("test_command") or case.test_command):
        raise ValueError("hidden suite has no test command")
    for name in tests["test_files"]:
        path = (final / name).resolve()
        if not path.is_relative_to(final.resolve()) or not path.is_file():
            raise ValueError(f"invalid hidden test file: {name}")
    for field in ("install_command", "build_command", "env_probe_command"):
        command = runner.get(field)
        if command:
            check = subprocess.run(["bash", "-n", "-c", command], capture_output=True, text=True, timeout=10)
            if check.returncode:
                raise ValueError(f"invalid shell syntax in {field}: {check.stderr.strip()}")
    _environment_checks(runner)
    if runner.get("judge_profile", "standard") not in {"standard", "cow"}:
        raise ValueError("unknown judge_profile")
    denylist = load_denylist(case_dir)
    if require_denylist and (denylist is None or not denylist.enabled):
        raise ValueError("required denylist is missing or disabled")
    # Exercise the same public/test staging contract used by image builds.
    with stage_benchmark_bundle(case_dir, final):
        pass
    return {"case_id": case.case_id, "language": case.language, "status": "ready",
            "platform": platform_name(), "public_leakage": "overridden" if allow_leakage else "passed",
            "denylist": "available" if denylist and denylist.enabled else "unavailable",
            "judge_profile": runner.get("judge_profile", "standard")}


def _environment_checks(runner: dict) -> list[dict]:
    checks = runner.get("environment_checks", [])
    if not isinstance(checks, list):
        raise ValueError("environment_checks must be a list")
    names = set()
    for check in checks:
        if not isinstance(check, dict) or not check.get("name") or not check.get("command"):
            raise ValueError("each environment check needs a name and command")
        if check["name"] in names:
            raise ValueError("duplicate environment check name")
        names.add(check["name"])
        if check.get("phase", "both") not in {"solve", "judge", "both"}:
            raise ValueError("environment check phase must be solve, judge or both")
        timeout = float(check.get("timeout_sec", 30))
        if not 0 < timeout <= 300:
            raise ValueError("environment check timeout must be in (0, 300]")
    return checks


def check_container(container, case_dir: Path, *, phase: str) -> dict:
    """Check toolchain and public inputs before injecting a candidate or tests."""
    case_dir = Path(case_dir)
    pairs = [("Full_PRD.md", "/environment/prd/Full_PRD.md"),
             ("Interface_Contract.md", "/environment/Interface_Contract.md"),
             ("Hardware_Requirements.md", "/environment/Hardware_Requirements.md")]
    expected = {dest: hashlib.sha256((case_dir / "public" / source).read_bytes()).hexdigest()
                for source, dest in pairs if (case_dir / "public" / source).is_file()}
    test_manifest = json.loads((case_dir / "milestones/final/test_manifest.json").read_text())
    pytest_import = "import pytest; " if re.search(r"\bpytest\b", test_manifest.get("test_command", "")) else ""
    program = ("import hashlib,json,pathlib; " + pytest_import +
               f"expected=json.loads({json.dumps(json.dumps(expected))}); "
               "assert all(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()==h for p,h in expected.items()), 'public input hash mismatch'; "
               "assert not pathlib.Path('/tests/final').exists(), 'hidden tests present before injection'; "
               "assert not pathlib.Path('/var/run/docker.sock').exists(), 'Docker socket present'; "
               "assert not any(pathlib.Path('/app').iterdir()), 'workspace is not empty'; "
               "print('runtime and public inputs verified')")
    checks = [{"name": "baseline", "command": "command -v bash && command -v timeout && python3 -I -c " + shlex.quote(program)}]
    runner = json.loads((case_dir / "source/manifest.json").read_text())["runner"]
    checks += [c for c in _environment_checks(runner) if c.get("phase", "both") in {phase, "both"}]
    report = {}
    for check in checks:
        outcome = container.exec(check["command"], timeout_sec=float(check.get("timeout_sec", 30)))
        report[check["name"]] = {"exit_code": outcome.exit_code, "timed_out": outcome.timed_out, "output": outcome.tail}
        if outcome.exit_code:
            raise RuntimeError(f"{phase} environment check {check['name']} failed: {outcome.tail}")
    return report
