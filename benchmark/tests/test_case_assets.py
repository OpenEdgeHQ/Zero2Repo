"""Regression checks for released case assets."""

from __future__ import annotations

from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
RELEASED_CASE_IDS = tuple(f"case{i:03d}" for i in range(27, 33))


def test_released_suite_has_required_public_assets() -> None:
    cases_root = BENCHMARK_ROOT / "cases"
    present = sorted(
        p.name
        for p in cases_root.iterdir()
        if p.is_dir() and (p / "source" / "manifest.json").is_file()
    )
    assert present == list(RELEASED_CASE_IDS)
    for case_id in RELEASED_CASE_IDS:
        case_dir = cases_root / case_id
        assert (case_dir / "public" / "Full_PRD.md").is_file()
        assert (case_dir / "public" / "Interface_Contract.md").is_file()
        assert (case_dir / "source" / "manifest.json").is_file()
        assert (case_dir / "milestones" / "final" / "test_manifest.json").is_file()
        tests_dir = case_dir / "milestones" / "final" / "tests"
        assert tests_dir.is_dir()
        assert any(tests_dir.iterdir())
