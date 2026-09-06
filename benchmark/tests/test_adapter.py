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
SAMPLE_CASE_ID = "case001"


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
    assert "cmake -G Ninja -B build" in instruction
    assert "does **not** run any install or build" in instruction
    assert "/tests/final" not in instruction


def _write_minimal_case(
    root: Path,
    *,
    build_command: str,
    sensitive_terms: list[str],
) -> Path:
    case = root / "leakcase"
    (case / "source").mkdir(parents=True)
    (case / "public").mkdir()
    tests_dir = case / "milestones" / "final" / "tests"
    tests_dir.mkdir(parents=True)
    (case / "public" / "Full_PRD.md").write_text("A harmless PRD.\n")
    (case / "public" / "Interface_Contract.md").write_text("A harmless contract.\n")
    (tests_dir / "test_dummy.py").write_text("def test_ok():\n    assert True\n")
    (case / "source" / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "case_id": "leakcase",
                "sensitive_terms": sensitive_terms,
                "runner": {
                    "schema_version": 1,
                    "language_label": "python",
                    "install_command": "",
                    "build_command": build_command,
                    "test_command_template": "python3 -m pytest {test_files}",
                    "workdir": ".",
                },
            }
        ),
        encoding="utf-8",
    )
    (case / "milestones" / "final" / "test_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "step": "final",
                "test_files": ["tests/test_dummy.py"],
                "test_command": "python3 -m pytest {test_files}",
                "workdir": ".",
            }
        ),
        encoding="utf-8",
    )
    return case


def test_build_task_rejects_leak_in_build_command(tmp_path: Path) -> None:
    from coding_bench_harbor.adapter import AdapterError, build_task

    case_dir = _write_minimal_case(
        tmp_path,
        build_command="make UNIQUE_LEAK_TOKEN_XYZ",
        sensitive_terms=["UNIQUE_LEAK_TOKEN_XYZ"],
    )
    with pytest.raises(AdapterError, match="UNIQUE_LEAK_TOKEN_XYZ"):
        build_task(
            case_dir,
            tmp_path / "out",
            force=True,
            allow_leakage=False,
            require_released=False,
        )


@pytest.mark.parametrize(
    "case_id",
    ["case001", "case002", "case003", "case004", "case005", "case006"],
)
def test_harbor_instruction_surfaces_case_build_command(case_id: str) -> None:
    from coding_bench_harbor.adapter import _build_instruction

    assets = discover_case(CASES_ROOT / case_id, require_gt=False)
    contract = assets.contract_path.read_text(encoding="utf-8")
    out = _build_instruction(assets, contract)
    cmd = assets.runner.build_command.strip()
    if cmd:
        assert cmd in out
        assert "no build step" not in out
    else:
        assert "no build step" in out
    assert "/tests/final" not in out
    assert "does **not** run any install or build" in out


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
