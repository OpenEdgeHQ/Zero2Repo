"""Unit tests for the Harbor adapter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BENCHMARK_ROOT.parent
sys.path.insert(0, str(BENCHMARK_ROOT))

sys.path.insert(0, str(REPO_ROOT / "tools"))
from artifact_contracts import parse_milestone_step_dir_name  # noqa: E402

from coding_bench_harbor.adapter import (  # noqa: E402
    _harbor_manifest,
    discover_case,
    iter_benchmark_case_dirs,
)
from coding_bench_harbor.run_adapter import _iter_case_dirs  # noqa: E402

CASES_ROOT = BENCHMARK_ROOT / "cases"
SAMPLE_CASE_ID = "case027"


@pytest.mark.parametrize("name,expected", [
    ("step_1", 1),
    ("step_10", 10),
    ("step_1_opencode", None),
    ("step_1_claude-code", None),
])
def test_parse_milestone_step_dir_name(name: str, expected: int | None) -> None:
    assert parse_milestone_step_dir_name(name) == expected


def test_iter_benchmark_case_dirs_finds_manifest_cases() -> None:
    dirs = iter_benchmark_case_dirs(CASES_ROOT)
    ids = {d.name for d in dirs}
    assert SAMPLE_CASE_ID in ids
    assert "source" not in ids
    assert len(ids) == 6


def test_discover_benchmark_case() -> None:
    assets = discover_case(CASES_ROOT / SAMPLE_CASE_ID, require_gt=False)
    assert assets.case_id == SAMPLE_CASE_ID
    assert assets.acceptance.acceptance_dir.name == "final"
    assert assets.acceptance.test_files
    assert (assets.acceptance.acceptance_dir / "test_manifest.json").is_file()


def test_iter_case_dirs_all_discovers_manifest_cases() -> None:
    dirs = _iter_case_dirs(CASES_ROOT, None, build_all=True)
    assert {d.name for d in dirs} == {d.name for d in iter_benchmark_case_dirs(CASES_ROOT)}


def test_build_task_uses_single_prd_document(tmp_path: Path) -> None:
    from coding_bench_harbor.adapter import build_task

    task_dir = build_task(
        CASES_ROOT / SAMPLE_CASE_ID,
        tmp_path / "out",
        force=True,
        allow_leakage=True,
    )
    full_prd = task_dir / "environment" / "prd" / "Full_PRD.md"
    assert full_prd.is_file()
    assert not (task_dir / "environment" / "prd" / "steps").exists()
    instruction = (task_dir / "instruction.md").read_text(encoding="utf-8")
    prd_body = full_prd.read_text(encoding="utf-8")
    assert prd_body in instruction
    assert "# Interface Contract" in instruction


def test_build_task_creates_final_tests_and_acceptance_script(tmp_path: Path) -> None:
    from coding_bench_harbor.adapter import build_task

    task_dir = build_task(
        CASES_ROOT / SAMPLE_CASE_ID,
        tmp_path / "out",
        force=True,
        allow_leakage=True,
    )
    final_dir = task_dir / "tests" / "final"
    assert (final_dir / "test_manifest.json").is_file()
    assert (task_dir / "tests" / "final_judge.py").is_file()
    assert not (task_dir / "tests" / "milestones").exists()


def test_harbor_manifest_rewrites_test_paths() -> None:
    acceptance_dir = CASES_ROOT / SAMPLE_CASE_ID / "milestones" / "final"
    manifest = json.loads((acceptance_dir / "test_manifest.json").read_text(encoding="utf-8"))
    out = _harbor_manifest(manifest, acceptance_dir, "/tests/final")
    cmd = out["test_command"]
    assert "/tests/final/tests/" in cmd
    assert "milestones/" not in cmd
