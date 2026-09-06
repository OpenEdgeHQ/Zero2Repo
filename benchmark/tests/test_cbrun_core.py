"""Unit tests for cbrun instruction, limits, steps, isolation and results."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun import instruction as instr_mod  # noqa: E402
from cbrun import isolation, results  # noqa: E402
from cbrun.assets import CaseSpec  # noqa: E402
from cbrun.limits import (  # noqa: E402
    DEFAULT_AGENT_TIMEOUT_SEC,
    DEFAULT_TEST_TIMEOUT_SEC,
    TerminalStatus,
    classify_terminal,
    resolve_limits,
)
from cbrun.submit import (  # noqa: E402
    CONTAINER_SUBMIT_PATH,
    SUBMIT_TOKEN,
    is_valid_submit,
)
from cbrun.results import TrialResult  # noqa: E402
from cbrun.steps import discover_steps  # noqa: E402


# --- instruction --------------------------------------------------------------

def test_instruction_contains_spec_and_environment_notes() -> None:
    out = instr_mod.build_instruction("PRD BODY", "CONTRACT BODY")
    assert "PRD BODY" in out
    assert "CONTRACT BODY" in out
    assert "/app" in out
    assert "/environment/prd/Full_PRD.md" in out
    assert "hidden acceptance test" in out.lower()
    # Free development with only a time limit is stated.
    assert "no limit on the number of steps" in out
    assert "implement from scratch" in out.lower()
    assert "github" in out.lower()
    assert CONTAINER_SUBMIT_PATH in out
    assert SUBMIT_TOKEN in out
    assert "Finishing is your submission" not in out
    assert "ending the session is **not**" in out.lower()


def test_instruction_includes_hardware_when_provided() -> None:
    out = instr_mod.build_instruction(
        "PRD BODY",
        "CONTRACT BODY",
        hardware_text="GPU required",
    )
    assert "GPU required" in out
    assert "/environment/Hardware_Requirements.md" in out
    assert "# Hardware Requirements" in out


def test_instruction_does_not_leak_hidden_test_paths() -> None:
    out = instr_mod.build_instruction("prd", "contract")
    assert "/tests/final" not in out
    assert "test_manifest" not in out
    assert "no build step" in out
    assert "pip install -e ." not in out


def test_instruction_includes_nonempty_build_command() -> None:
    cmd = "cmake -G Ninja -B build && cmake --build build"
    out = instr_mod.build_instruction(
        "PRD BODY",
        "CONTRACT BODY",
        build_command=cmd,
        workdir=".",
    )
    assert cmd in out
    assert "does **not** run any install or build" in out
    assert "no build step" not in out
    assert "You must run this exact command" not in out


def test_instruction_states_test_workdir_only_when_not_root() -> None:
    root = instr_mod.build_instruction(
        "P", "C", build_command="make", workdir="."
    )
    assert "as their working directory" not in root
    assert "from the `/app` root" in root

    nested = instr_mod.build_instruction(
        "P", "C", build_command="make", workdir="src"
    )
    assert "`/app/src` as their working directory" in nested
    assert "from the `/app` root" in nested


def test_instruction_empty_build_command_declares_no_build_step() -> None:
    out = instr_mod.build_instruction(
        "PRD BODY", "CONTRACT BODY", build_command="", workdir="."
    )
    assert "no build step" in out
    assert "does **not** run any install or build" in out


@pytest.mark.parametrize(
    "case_id",
    ["case001", "case002", "case003", "case004", "case005", "case006"],
)
def test_instruction_surfaces_each_case_build_command(case_id: str) -> None:
    from cbrun.assets import load_case

    case = load_case(BENCHMARK_ROOT / "cases" / case_id)
    out = instr_mod.build_instruction(
        "PRD",
        "CONTRACT",
        build_command=case.build_command,
        workdir=case.workdir,
    )
    cmd = case.build_command.strip()
    if cmd:
        assert cmd in out
        assert "no build step" not in out
    else:
        assert "no build step" in out
    assert "/tests/final" not in out
    assert "does **not** run any install or build" in out


# --- limits -------------------------------------------------------------------

def test_resolve_limits_defaults_to_two_hour_solve() -> None:
    limits = resolve_limits()
    assert limits.max_agent_timeout_sec == DEFAULT_AGENT_TIMEOUT_SEC == 7200.0
    assert limits.max_test_timeout_sec == DEFAULT_TEST_TIMEOUT_SEC


def test_resolve_limits_applies_multiplier_to_wall_clocks_only() -> None:
    limits = resolve_limits(
        agent_timeout_sec=100, test_timeout_sec=10, stall_window_sec=50, multiplier=2.0
    )
    assert limits.max_agent_timeout_sec == 200
    assert limits.max_test_timeout_sec == 20
    assert limits.stall_window_sec == 50  # not multiplied


def test_resolve_limits_rejects_bad_values() -> None:
    with pytest.raises(ValueError):
        resolve_limits(multiplier=0)
    with pytest.raises(ValueError):
        resolve_limits(agent_timeout_sec=0)


def test_terminal_status_classification() -> None:
    assert TerminalStatus.from_run(exit_code=0, timed_out=False, stall_killed=False) is TerminalStatus.COMPLETED
    assert TerminalStatus.from_run(exit_code=1, timed_out=False, stall_killed=False) is TerminalStatus.ERROR
    assert TerminalStatus.from_run(exit_code=137, timed_out=True, stall_killed=False) is TerminalStatus.TIMEOUT
    assert TerminalStatus.from_run(exit_code=-1, timed_out=False, stall_killed=True) is TerminalStatus.ERROR


def test_classify_terminal_requires_submit_for_completed() -> None:
    assert (
        classify_terminal(
            exit_code=0, timed_out=False, stall_killed=False, submitted=False
        )
        is TerminalStatus.ERROR
    )
    assert (
        classify_terminal(
            exit_code=0, timed_out=False, stall_killed=False, submitted=True
        )
        is TerminalStatus.COMPLETED
    )


def test_classify_terminal_timeout_without_submit() -> None:
    assert (
        classify_terminal(
            exit_code=137, timed_out=True, stall_killed=False, submitted=False
        )
        is TerminalStatus.TIMEOUT
    )


def test_classify_terminal_timeout_with_submit_still_timeout() -> None:
    assert (
        classify_terminal(
            exit_code=137, timed_out=True, stall_killed=False, submitted=True
        )
        is TerminalStatus.TIMEOUT
    )


def test_is_valid_submit_accepts_only_exact_token() -> None:
    assert is_valid_submit(SUBMIT_TOKEN) is True
    assert is_valid_submit(f"  {SUBMIT_TOKEN}  \n") is True
    assert is_valid_submit(f"{SUBMIT_TOKEN}\n\n") is True
    assert is_valid_submit("") is False
    assert is_valid_submit(None) is False
    assert is_valid_submit("SUBMIT") is False
    assert is_valid_submit(f"{SUBMIT_TOKEN}\nextra") is False


# --- steps / isolation --------------------------------------------------------

def _make_case(
    *,
    install_command: str,
    test_command: str = "pytest {test_files}",
    workdir: str = ".",
    test_manifest: dict | None = None,
    tmp_path: Path,
    build_command: str = "",
    sensitive_terms: list[str] | None = None,
) -> CaseSpec:
    from types import SimpleNamespace

    acceptance = SimpleNamespace(
        acceptance_dir=tmp_path,
        test_manifest=test_manifest or {"test_command": test_command, "workdir": workdir},
    )
    assets = SimpleNamespace(acceptance=acceptance)
    return CaseSpec(
        case_id="demo-001",
        language="python",
        prd_text="PRD",
        contract_text="CONTRACT",
        sensitive_terms=list(sensitive_terms or []),
        install_command=install_command,
        build_command=build_command,
        test_command=test_command,
        workdir=workdir,
        docker_image="",
        docker_gpus="",
        hardware_text=None,
        assets=assets,  # type: ignore[arg-type]
    )


def test_discover_steps_single_final(tmp_path: Path) -> None:
    case = _make_case(install_command="pip install -e .", tmp_path=tmp_path)
    steps = discover_steps(case)
    assert len(steps) == 1
    assert steps[0].index == 1
    assert steps[0].is_final is True
    assert steps[0].prd_text == "PRD"
    assert steps[0].contract_text == "CONTRACT"


def test_merge_runner_test_manifest_install_overrides_source(tmp_path: Path) -> None:
    # srush-like: install lives in the test_manifest, not the source runner.
    case = _make_case(
        install_command="",
        test_manifest={"install_command": "pip install numba", "test_command": "x {test_files}"},
        tmp_path=tmp_path,
    )
    step = discover_steps(case)[0]
    merged = isolation.merge_runner(case, step)
    assert merged["install_command"] == "pip install numba"


def test_merge_runner_source_install_used_when_manifest_absent(tmp_path: Path) -> None:
    # cccl-like: install lives in the source runner, test_manifest has none.
    case = _make_case(
        install_command="setup nvtx",
        test_manifest={"test_command": "ctest {test_dir}"},
        tmp_path=tmp_path,
    )
    step = discover_steps(case)[0]
    merged = isolation.merge_runner(case, step)
    assert merged["install_command"] == "setup nvtx"


def test_synthesize_task_toml_round_trips(tmp_path: Path) -> None:
    case = _make_case(
        install_command="pip install -e .",
        test_command="pytest {test_files}",
        workdir="src",
        tmp_path=tmp_path,
    )
    step = discover_steps(case)[0]
    raw = isolation.synthesize_task_toml(case, step)
    doc = tomllib.loads(raw.decode("utf-8"))
    runner = doc["metadata"]["runner"]
    assert runner["install_command"] == "pip install -e ."
    assert runner["workdir"] == "src"
    assert doc["metadata"]["case_id"] == "demo-001"
    assert doc["metadata"]["judge_mode"] == "final_tests"


def test_check_public_leakage_rejects_term_in_build_command(tmp_path: Path) -> None:
    from cbrun.assets import AdapterError
    from cbrun.run_case import _check_public_leakage

    case = _make_case(
        install_command="",
        tmp_path=tmp_path,
        build_command="make UNIQUE_LEAK_TOKEN_XYZ",
        sensitive_terms=["UNIQUE_LEAK_TOKEN_XYZ"],
    )
    with pytest.raises(AdapterError, match="UNIQUE_LEAK_TOKEN_XYZ"):
        _check_public_leakage(case, allow_leakage=False)
    _check_public_leakage(case, allow_leakage=True)


# --- results ------------------------------------------------------------------

def test_write_summary_and_aggregate(tmp_path: Path) -> None:
    trials = [
        TrialResult("c1", "codex", "m", reward=1.0, terminal_status="completed"),
        TrialResult("c1", "opencode", "m", reward=0.0, terminal_status="timeout"),
        TrialResult("c2", "codex", "m", reward=0.0, terminal_status="error", judge_error="boom"),
    ]
    path = results.write_summary(trials, tmp_path)
    import json

    payload = json.loads(path.read_text())
    agg = payload["aggregate"]
    assert agg["total"] == 3
    assert agg["passed"] == 1
    assert agg["terminal_status"]["timeout"] == 1
    assert agg["judge_errors"] == 1


def test_format_reward_matrix_renders_cells() -> None:
    trials = [
        TrialResult("c1", "codex", "m", reward=1.0, terminal_status="completed"),
        TrialResult("c1", "opencode", "m", reward=0.0, terminal_status="timeout"),
    ]
    text = results.format_reward_matrix(trials)
    assert "c1" in text
    assert "codex" in text
    assert "opencode" in text
    assert "PASS" in text
    assert "FAIL" in text
