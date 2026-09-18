"""Regression checks for released case files, plus synthetic asset-rule tests.

The new checker is exercised on temporary fixtures only. Released cases are
not used as oracles for leakage / denylist / install-path rules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.case_checks import check_case_assets, check_case_warnings  # noqa: E402


def test_released_suite_has_required_public_assets() -> None:
    cases_root = BENCHMARK_ROOT / "cases"
    present = sorted(
        p.name
        for p in cases_root.iterdir()
        if p.is_dir() and (p / "source" / "manifest.json").is_file()
    )
    assert present, f"no cases with source/manifest.json under {cases_root}"
    for case_id in present:
        case_dir = cases_root / case_id
        assert (case_dir / "public" / "Full_PRD.md").is_file()
        assert (case_dir / "public" / "Interface_Contract.md").is_file()
        assert (case_dir / "source" / "manifest.json").is_file()
        assert (case_dir / "milestones" / "final" / "test_manifest.json").is_file()
        tests_dir = case_dir / "milestones" / "final" / "tests"
        assert tests_dir.is_dir()
        assert any(tests_dir.iterdir())
        assert check_case_assets(case_dir) == []


def _write_case(root: Path, **overrides: object) -> Path:
    case = root / "case999"
    (case / "public").mkdir(parents=True)
    (case / "source" / "env").mkdir(parents=True)
    final = case / "milestones" / "final" / "tests"
    final.mkdir(parents=True)
    (final / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    runner = {
        "install_command": "true",
        "build_command": "",
        "judge_bans": ["socket"],
    }
    runner.update(overrides.get("runner") or {})  # type: ignore[arg-type]
    manifest = {
        "case_id": "case999",
        "sensitive_terms": overrides.get("sensitive_terms", ["upstreamsecret"]),
        "runner": runner,
    }
    lock = {"runner": {k: runner.get(k, "") for k in ("install_command", "build_command")}}
    tests_manifest = {
        "test_files": ["tests/test_ok.py"],
        "support_files": [],
    }
    if "manifest" in overrides:
        manifest.update(overrides["manifest"])  # type: ignore[arg-type]
    if "lock" in overrides:
        lock.update(overrides["lock"])  # type: ignore[arg-type]
    if "tests_manifest" in overrides:
        tests_manifest.update(overrides["tests_manifest"])  # type: ignore[arg-type]
    (case / "source" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (case / "source" / "recipe.lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (case / "public" / "Full_PRD.md").write_text(
        str(overrides.get("prd", "A public product spec.")), encoding="utf-8"
    )
    (case / "public" / "Interface_Contract.md").write_text(
        str(overrides.get("contract", "Public API names only.")), encoding="utf-8"
    )
    (case / "milestones" / "final" / "test_manifest.json").write_text(
        json.dumps(tests_manifest), encoding="utf-8"
    )
    if overrides.get("denylist"):
        (case / "source" / "denylist.json").write_text(
            json.dumps(overrides["denylist"]), encoding="utf-8"
        )
    if overrides.get("resources"):
        (case / "source" / "env" / "resources.json").write_text(
            json.dumps(overrides["resources"]), encoding="utf-8"
        )
    return case


def test_check_case_assets_accepts_clean_fixture(tmp_path: Path) -> None:
    case = _write_case(tmp_path)
    assert check_case_assets(case) == []


def test_check_case_assets_flags_boundary_leakage(tmp_path: Path) -> None:
    case = _write_case(tmp_path, prd="Mentions upstreamsecret in the PRD.")
    errors = check_case_assets(case)
    assert any("leakage" in item for item in errors)


def test_check_case_assets_ignores_substring_of_sensitive_term(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        sensitive_terms=["ada"],
        prd="the adapter loads data",
    )
    assert check_case_assets(case) == []


def test_check_case_assets_flags_lock_drift_and_private_cache(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        runner={"install_command": "cp -a /opt/cb-cache/models .", "build_command": ""},
        lock={"runner": {"install_command": "true", "build_command": ""}},
    )
    errors = "\n".join(check_case_assets(case))
    assert "disagree" in errors
    assert "/opt/cb-cache" in errors


def test_check_case_assets_allows_cache_when_resources_declared(tmp_path: Path) -> None:
    install = "cp -a /opt/cb-cache/models ."
    case = _write_case(
        tmp_path,
        runner={"install_command": install, "build_command": ""},
        lock={"runner": {"install_command": install, "build_command": ""}},
        resources={"destination": "/opt/models", "resources": []},
    )
    errors = check_case_assets(case)
    assert not any("/opt/cb-cache" in item for item in errors)


def test_check_case_assets_flags_unknown_judge_ban_and_missing_test(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        runner={"install_command": "true", "build_command": "", "judge_bans": ["laser"]},
        tests_manifest={"test_files": ["tests/missing.py"], "support_files": []},
    )
    errors = "\n".join(check_case_assets(case))
    assert "unknown judge_bans" in errors
    assert "missing tests/missing.py" in errors


def test_check_case_assets_flags_test_command_template_drift(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        runner={
            "install_command": "true",
            "build_command": "",
            "test_command_template": "python3 -m unittest {test_files}",
        },
        tests_manifest={
            "test_files": ["tests/test_ok.py"],
            "support_files": [],
            "test_command_template": "python3 -m pytest {test_files}",
        },
    )
    errors = "\n".join(check_case_assets(case))
    assert "disagree on test_command_template" in errors


def test_check_case_assets_accepts_matching_test_command_template(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        runner={
            "install_command": "true",
            "build_command": "",
            "test_command_template": "PYTHONPATH=src python3 -m pytest {test_files}",
        },
        tests_manifest={
            "test_files": ["tests/test_ok.py"],
            "support_files": [],
            "test_command_template": "PYTHONPATH=src python3 -m pytest {test_files}",
        },
    )
    assert check_case_assets(case) == []


def test_privilege_markers_require_judge_substrates(tmp_path: Path) -> None:
    case = _write_case(tmp_path)
    helper = case / "milestones" / "final" / "tests" / "helper.py"
    helper.write_text("def setup():\n    losetup('/dev/loop0')\n", encoding="utf-8")
    issues = check_case_assets(case)
    assert issues and "judge substrate" in issues[0]
    assert check_case_warnings(case) == []


def test_privilege_markers_ok_with_declared_substrate(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        tests_manifest={
            "test_files": ["tests/test_ok.py"],
            "support_files": [],
            "judge_substrates": ["cow_fs"],
        },
    )
    helper = case / "milestones" / "final" / "tests" / "helper.py"
    helper.write_text("def setup():\n    losetup('/dev/loop0')\n", encoding="utf-8")
    assert check_case_assets(case) == []


def test_unknown_judge_substrate_is_error(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        tests_manifest={
            "test_files": ["tests/test_ok.py"],
            "support_files": [],
            "judge_substrates": ["not-a-provider"],
        },
    )
    issues = check_case_assets(case)
    assert issues and "unknown judge_substrates" in issues[0]


def test_suite_wall_fields_must_be_numbers(tmp_path: Path) -> None:
    case = _write_case(
        tmp_path,
        tests_manifest={
            "test_files": ["tests/test_ok.py"],
            "support_files": [],
            "suite_wall_seconds": "fast",
            "judge_timeout_sec": -1,
            "suite_wall_measured_on": "remote",
        },
    )
    issues = check_case_assets(case)
    joined = " ".join(issues)
    assert "suite_wall_seconds must be a non-negative number" in joined
    assert "judge_timeout_sec must be a non-negative number" in joined
    assert "suite_wall_measured_on must be an object" in joined


def test_privilege_markers_ignore_amount_substring(tmp_path: Path) -> None:
    case = _write_case(tmp_path)
    helper = case / "milestones" / "final" / "tests" / "helper.py"
    helper.write_text(
        "def _runtime_grouped_amount():\n    return 1\n",
        encoding="utf-8",
    )
    assert check_case_assets(case) == []
    assert check_case_warnings(case) == []
