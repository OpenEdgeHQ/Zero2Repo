"""Unit tests for the shared final judge: launcher, shadows, fail-closed counts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
HARBOR = BENCHMARK_ROOT / "coding_bench_harbor"
sys.path.insert(0, str(HARBOR))

import final_judge as fj  # noqa: E402

PYTEST_OK = "===== 3 passed in 0.01s =====\n"
PYTEST_FAIL = "===== 1 failed, 2 passed in 0.02s =====\n"


@pytest.fixture
def judge_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workspace = tmp_path / "app"
    tests_final = tmp_path / "tests" / "final"
    verifier = tmp_path / "verifier"
    workspace.mkdir()
    tests_final.mkdir(parents=True)
    verifier.mkdir()
    monkeypatch.setattr(fj, "WORKSPACE", workspace)
    monkeypatch.setattr(fj, "TESTS_FINAL", tests_final)
    monkeypatch.setattr(fj, "VERIFIER_DIR", verifier)
    monkeypatch.setattr(fj, "LAUNCHER_PATH", HARBOR / "pytest_launcher.py")
    monkeypatch.setenv("CODING_BENCH_PYTEST_USER", "")
    return tests_final


def _write_manifest(tests_final: Path, **extra) -> None:
    payload = {
        "test_files": ["tests/t.py"],
        "test_command": "PYTHONPATH=src python3 -m pytest",
        "workdir": ".",
    }
    payload.update(extra)
    (tests_final / "test_manifest.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    tests_dir = tests_final / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "t.py").write_text("def test_x(): pass\n", encoding="utf-8")


def _report() -> dict:
    return json.loads((fj.VERIFIER_DIR / "final_report.json").read_text())


def test_shadow_pytest_py_is_judge_error(judge_env: Path) -> None:
    _write_manifest(judge_env)
    (fj.WORKSPACE / "pytest.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["reward"] == 0.0
    assert report["judge_error"]
    assert "shadowed pytest" in report["judge_error"]


def test_shadow_src_pytest_py_is_judge_error(judge_env: Path) -> None:
    _write_manifest(judge_env)
    src = fj.WORKSPACE / "src"
    src.mkdir()
    (src / "pytest.py").write_text("import sys; sys.exit(0)\n", encoding="utf-8")
    rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["reward"] == 0.0
    assert "shadowed pytest" in (report["judge_error"] or "")


def test_empty_exit_zero_is_judge_error(judge_env: Path) -> None:
    _write_manifest(judge_env)
    mock_proc = MagicMock(returncode=0, stdout="", stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc):
        rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["reward"] == 0.0
    assert report["judge_error"]
    assert "parseable" in report["judge_error"]


def test_unparseable_summary_is_judge_error(judge_env: Path) -> None:
    _write_manifest(judge_env)
    mock_proc = MagicMock(returncode=0, stdout="all good\n", stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc):
        rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["reward"] == 0.0
    assert report["judge_error"]


def test_count_mismatch_is_judge_error(judge_env: Path) -> None:
    _write_manifest(judge_env, expected_test_count=99)
    mock_proc = MagicMock(returncode=0, stdout=PYTEST_OK, stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc):
        rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["reward"] == 0.0
    assert "expected_test_count" in (report["judge_error"] or "")


def test_parsed_failures_are_failed_not_harness_error(judge_env: Path) -> None:
    _write_manifest(judge_env)
    mock_proc = MagicMock(returncode=1, stdout=PYTEST_FAIL, stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc):
        rc = fj.main()
    report = _report()
    assert rc == 0
    assert report["reward"] == 0.0
    assert report["judge_error"] is None
    assert report["final"]["status"] == "failed"


def test_pytest_runs_as_cbagent_when_account_exists(judge_env: Path, monkeypatch) -> None:
    _write_manifest(judge_env)
    monkeypatch.delenv("CODING_BENCH_PYTEST_USER", raising=False)
    fake = type("U", (), {"pw_name": "cbagent"})()
    monkeypatch.setattr(fj.pwd, "getpwnam", lambda name: fake if name == "cbagent" else (_ for _ in ()).throw(KeyError(name)))
    mock_proc = MagicMock(returncode=0, stdout=PYTEST_OK, stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc) as run:
        rc = fj.main()
    assert rc == 0
    argv = run.call_args.args[0]
    assert argv[:3] == ["runuser", "-u", "cbagent"]


def test_valid_pytest_summary_scores_one_and_skips_install(judge_env: Path, tmp_path: Path) -> None:
    _write_manifest(judge_env)
    task = tmp_path / "task.toml"
    task.write_text(
        "[metadata.runner]\ninstall_command = \"pip install -e .\"\n"
        "build_command = \"python setup.py build\"\n",
        encoding="utf-8",
    )
    fj.TASK_TOML = task
    mock_proc = MagicMock(returncode=0, stdout=PYTEST_OK, stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc) as run:
        rc = fj.main()
    report = _report()
    assert rc == 0
    assert report["reward"] == 1.0
    assert report["judge_error"] is None
    assert report["final"]["counts_parsed"] is True
    assert report["install"]["install_command_status"] == "skipped"
    assert report["install"]["build_command_status"] == "skipped"
    argv = run.call_args.args[0]
    assert isinstance(argv, list)
    assert "-I" in argv
    assert any("pytest_launcher.py" in str(part) for part in argv)
    joined = " ".join(str(p) for p in argv)
    assert "pip install" not in joined


def test_run_acceptance_empty_exit_zero_is_judge_error(judge_env: Path) -> None:
    script = judge_env / "run_acceptance.sh"
    script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    _write_manifest(judge_env)
    mock_proc = MagicMock(returncode=0, stdout="ok\n", stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc):
        rc = fj.main()
    report = _report()
    assert rc == 1
    assert report["judge_mode"] == "run_acceptance"
    assert report["reward"] == 0.0
    assert report["judge_error"]


def test_pytest_rest_args_and_product_paths(judge_env: Path) -> None:
    cmd = "PYTHONPATH=src python3 -m pytest tests/F01_acceptance.py -q"
    assert fj._pytest_rest_args(cmd) == ["tests/F01_acceptance.py", "-q"]
    paths = fj._product_paths(cmd, fj.WORKSPACE, fj.WORKSPACE)
    assert paths == [str(fj.WORKSPACE / "src")]
    assert fj._pytest_rest_args("ctest --output-on-failure") is None


def test_run_acceptance_valid_summary_scores_one(judge_env: Path) -> None:
    script = judge_env / "run_acceptance.sh"
    script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    _write_manifest(judge_env)
    mock_proc = MagicMock(returncode=0, stdout=PYTEST_OK, stderr="")
    with patch.object(fj.subprocess, "run", return_value=mock_proc) as run:
        rc = fj.main()
    report = _report()
    assert rc == 0
    assert report["judge_mode"] == "run_acceptance"
    assert report["reward"] == 1.0
    assert "run_acceptance.sh" in run.call_args.args[0]
