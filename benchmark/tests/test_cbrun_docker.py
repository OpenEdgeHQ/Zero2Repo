"""Docker-gated integration tests for cbrun.

These exercise the real judge wiring, the per-case ``:agent`` image derivation
and the fairness invariant against actual benchmark images. They are skipped
automatically when Docker or the required images are unavailable, so the suite
stays runnable on hosts without the heavy image set. They never call a model:
the oracle check injects the case GT in place of an agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BENCHMARK_ROOT.parent
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun import images, judge  # noqa: E402
from cbrun.assets import load_case  # noqa: E402
from cbrun.docker_env import Container, docker_available, image_exists  # noqa: E402
from cbrun.isolation import synthesize_task_toml  # noqa: E402
from cbrun.steps import discover_steps  # noqa: E402

ORACLE_CASE = "case002"  # CPU-only pytest acceptance; cheapest oracle.
GENERIC_JUDGE_IMAGE = "codingbench-base/ubuntu:24.04"


def _case_dir(case_id: str) -> Path:
    for root in (BENCHMARK_ROOT / "cases", REPO_ROOT / "cases"):
        candidate = root / case_id
        if (candidate / "source" / "manifest.json").is_file():
            return candidate
    return BENCHMARK_ROOT / "cases" / case_id


def _require_generic_judge_image() -> str:
    if not docker_available():
        pytest.skip("docker unavailable")
    if not image_exists(GENERIC_JUDGE_IMAGE):
        pytest.skip(f"image missing: {GENERIC_JUDGE_IMAGE}")
    return GENERIC_JUDGE_IMAGE


def _seed_hidden_pytest(dest: Path) -> Path:
    final_dir = dest / "final"
    tests_dir = final_dir / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_pkg.py").write_text(
        "import pkg\n\ndef test_hello():\n    assert pkg.hello() == 'ok'\n",
        encoding="utf-8",
    )
    (final_dir / "test_manifest.json").write_text(
        '{"test_files": ["tests/test_pkg.py"],'
        ' "test_command": "PYTHONPATH=src python3 -m pytest",'
        ' "workdir": "."}\n',
        encoding="utf-8",
    )
    return final_dir


def _require_docker_and_deliverable(case_id: str) -> str:
    if not docker_available():
        pytest.skip("docker unavailable")
    tag = images.deliverable_tag(case_id)
    if not image_exists(tag):
        pytest.skip(f"deliverable image missing: {tag}")
    return tag


@pytest.mark.slow
def test_oracle_gt_scores_reward_one(tmp_path: Path) -> None:
    """Injecting the case GT into /app must score reward 1 (env is solvable)."""
    deliverable = _require_docker_and_deliverable(ORACLE_CASE)
    case = load_case(_case_dir(ORACLE_CASE))
    step = discover_steps(case)[0]

    final_dir = images.extract_hidden_tests(deliverable, tmp_path / "tests")
    gt_code = case.assets.gt_milestone.code_dir
    if not gt_code.is_dir():
        pytest.skip(f"GT code not available in public bundle: {gt_code}")
    assert gt_code.is_dir()

    container = Container.start(deliverable, gpus=case.docker_gpus or None, network="host")
    try:
        container.exec("mkdir -p /app")
        # Inject GT as the "agent output".
        for child in sorted(gt_code.iterdir()):
            container.cp_to(child, "/app/")
        outcome = judge.run_isolated_judge(
            container,
            image=deliverable,
            tests_final_dir=final_dir,
            task_toml=synthesize_task_toml(case, step),
            test_timeout_sec=900.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
            gpus=case.docker_gpus or None,
        )
    finally:
        container.remove()

    assert outcome.judge_error is None, outcome.judge_error
    assert outcome.reward == 1.0


@pytest.mark.slow
def test_agent_image_has_cbagent_user(tmp_path: Path) -> None:
    """The derived :agent image must include the fixed non-root cbagent user."""
    _require_docker_and_deliverable(ORACLE_CASE)
    case_dir = _case_dir(ORACLE_CASE)
    image = images.ensure_agent_image(
        ORACLE_CASE, cache_root=tmp_path / "cache", case_dir=case_dir, force=True
    )
    container = Container.start(image.agent_image, network="host")
    try:
        res = container.exec("id -u cbagent")
        assert res.exit_code == 0, res.tail
    finally:
        container.remove()


@pytest.mark.slow
def test_codex_setup_writes_config_without_secrets_in_command(tmp_path: Path) -> None:
    """Codex setup should write auth/config under CODEX_HOME before solve."""
    from cbrun.agent_spec import resolve_agent

    _require_docker_and_deliverable(ORACLE_CASE)
    case_dir = _case_dir(ORACLE_CASE)
    image = images.ensure_agent_image(
        ORACLE_CASE, cache_root=tmp_path / "cache", case_dir=case_dir, force=True
    )
    inv = resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={"OPENAI_API_KEY": "sk-test-secret", "OPENAI_BASE_URL": "http://example/v1"},
    )
    container = Container.start(image.agent_image, network="host")
    try:
        container.exec(inv.prepare_workspace, timeout_sec=60.0)
        setup = container.exec(
            inv.setup_script or "true",
            env=inv.env,
            timeout_sec=60.0,
        )
        assert setup.exit_code == 0, setup.tail
        auth = container.exec("cat /root/.codex/auth.json")
        assert auth.exit_code == 0
        assert "sk-test-secret" in (auth.tail or "")
        cfg = container.exec("cat /root/.codex/config.toml")
        assert cfg.exit_code == 0
        assert "http://example/v1" in (cfg.tail or "")
        # Setup script itself must not echo secrets when logged.
        assert "set -x" not in (inv.setup_script or "")
    finally:
        container.remove()


@pytest.mark.slow
def test_agent_image_denylist_shim_blocks_upstream_pip(tmp_path: Path) -> None:
    """pip shim in :agent image should reject upstream packages from denylist."""
    _require_docker_and_deliverable(ORACLE_CASE)
    case_dir = _case_dir(ORACLE_CASE)
    image = images.ensure_agent_image(
        ORACLE_CASE, cache_root=tmp_path / "cache", case_dir=case_dir, force=True
    )
    container = Container.start(image.agent_image, network="host")
    try:
        res = container.exec("pip install cutlass", timeout_sec=30.0)
        assert res.exit_code != 0
        assert "denylist" in (res.tail or "").lower()
    finally:
        container.remove()


@pytest.mark.slow
def test_solve_container_blocks_github(tmp_path: Path) -> None:
    from cbrun.denylist import GITHUB_BLOCK_HOSTS

    _require_docker_and_deliverable(ORACLE_CASE)
    case_dir = _case_dir(ORACLE_CASE)
    image = images.ensure_agent_image(
        ORACLE_CASE, cache_root=tmp_path / "cache", case_dir=case_dir, force=False
    )
    container = Container.start(
        image.agent_image,
        network="host",
        block_hosts=GITHUB_BLOCK_HOSTS,
    )
    try:
        res = container.exec(
            "python3 -c \"import socket; s=socket.create_connection(('github.com', 443), 2)\"",
            timeout_sec=10.0,
        )
        assert res.exit_code != 0
    finally:
        container.remove()


@pytest.mark.slow
def test_agent_image_has_no_hidden_tests(tmp_path: Path) -> None:
    """The derived :agent image must not contain /tests/final in any layer."""
    _require_docker_and_deliverable(ORACLE_CASE)
    case_dir = _case_dir(ORACLE_CASE)
    image = images.ensure_agent_image(
        ORACLE_CASE, cache_root=tmp_path / "cache", case_dir=case_dir, force=True
    )
    # Host cache must hold the extracted hidden tests.
    assert (image.tests_cache_dir / "final" / "test_manifest.json").is_file()

    container = Container.start(image.agent_image, network="host")
    try:
        assert container.path_exists("/tests/final") is False
        # CLIs were installed in the agent layer.
        for bin_name in ("codex", "opencode", "claude", "cursor-agent"):
            res = container.exec(f"command -v {bin_name}")
            assert res.exit_code == 0, f"{bin_name} missing from :agent image"
    finally:
        container.remove()


@pytest.mark.slow
def test_app_pytest_shadow_is_judge_error_after_isolation(tmp_path: Path) -> None:
    """A candidate pytest.py copied with /app must not score reward 1."""
    deliverable = _require_docker_and_deliverable(ORACLE_CASE)
    case = load_case(_case_dir(ORACLE_CASE))
    step = discover_steps(case)[0]
    final_dir = images.extract_hidden_tests(deliverable, tmp_path / "tests")

    container = Container.start(deliverable, gpus=case.docker_gpus or None, network="host")
    try:
        container.exec("mkdir -p /app")
        container.exec(
            "printf '%s\\n' 'import sys' 'print(\"FAKE_PYTEST_EXECUTED\")' "
            "'sys.exit(0)' > /app/pytest.py"
        )
        outcome = judge.run_isolated_judge(
            container,
            image=deliverable,
            tests_final_dir=final_dir,
            task_toml=synthesize_task_toml(case, step),
            test_timeout_sec=120.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
            gpus=case.docker_gpus or None,
        )
    finally:
        container.remove()

    assert outcome.reward == 0.0
    assert outcome.judge_error
    assert "shadowed pytest" in outcome.judge_error


@pytest.mark.slow
def test_dirty_solve_pytest_does_not_reach_judge(tmp_path: Path) -> None:
    """Replacing pytest only in the solve container must not follow /app across."""
    deliverable = _require_docker_and_deliverable(ORACLE_CASE)
    case = load_case(_case_dir(ORACLE_CASE))
    step = discover_steps(case)[0]
    final_dir = images.extract_hidden_tests(deliverable, tmp_path / "tests")
    gt_code = case.assets.gt_milestone.code_dir
    if not gt_code.is_dir():
        pytest.skip(f"GT code not available in public bundle: {gt_code}")

    container = Container.start(deliverable, gpus=case.docker_gpus or None, network="host")
    try:
        container.exec("mkdir -p /app")
        for child in sorted(gt_code.iterdir()):
            container.cp_to(child, "/app/")
        container.exec(
            "printf '%s\\n' '#!/bin/sh' 'echo FAKE_SOLVE_PYTEST' 'exit 0' "
            "> /usr/local/bin/pytest && chmod +x /usr/local/bin/pytest"
        )
        outcome = judge.run_isolated_judge(
            container,
            image=deliverable,
            tests_final_dir=final_dir,
            task_toml=synthesize_task_toml(case, step),
            test_timeout_sec=900.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
            gpus=case.docker_gpus or None,
        )
    finally:
        container.remove()

    assert outcome.judge_error is None, outcome.judge_error
    assert outcome.reward == 1.0


def _generic_task_toml() -> bytes:
    return (
        b"schema_version = '1.1'\n"
        b"[metadata]\n"
        b"[metadata.runner]\n"
        b"install_command = 'pip install -e .'\n"
        b"test_command = 'PYTHONPATH=src python3 -m pytest'\n"
        b"workdir = '.'\n"
    )


@pytest.mark.slow
def test_generic_gt_like_workspace_scores_one(tmp_path: Path) -> None:
    """Honest src-layout tree + hidden pytest must score 1 on a clean judge image."""
    image = _require_generic_judge_image()
    final_dir = _seed_hidden_pytest(tmp_path / "tests")
    container = Container.start(image, network="none")
    try:
        container.exec("mkdir -p /app/src")
        container.exec("printf '%s\\n' 'def hello():' \"    return 'ok'\" > /app/src/pkg.py")
        outcome = judge.run_isolated_judge(
            container,
            image=image,
            tests_final_dir=final_dir,
            task_toml=_generic_task_toml(),
            test_timeout_sec=120.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
        )
    finally:
        container.remove()
    assert outcome.judge_error is None, outcome.judge_error
    assert outcome.reward == 1.0


@pytest.mark.slow
def test_generic_shadow_pytest_is_judge_error(tmp_path: Path) -> None:
    image = _require_generic_judge_image()
    final_dir = _seed_hidden_pytest(tmp_path / "tests")
    container = Container.start(image, network="none")
    try:
        container.exec("mkdir -p /app/src")
        container.exec("printf '%s\\n' 'def hello():' \"    return 'ok'\" > /app/src/pkg.py")
        container.exec(
            "printf '%s\\n' 'import sys' 'print(\"FAKE_PYTEST_EXECUTED\")' "
            "'sys.exit(0)' > /app/pytest.py"
        )
        outcome = judge.run_isolated_judge(
            container,
            image=image,
            tests_final_dir=final_dir,
            task_toml=_generic_task_toml(),
            test_timeout_sec=120.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
        )
    finally:
        container.remove()
    assert outcome.reward == 0.0
    assert outcome.judge_error
    assert "shadowed pytest" in outcome.judge_error


@pytest.mark.slow
def test_generic_dirty_solve_pytest_stays_behind(tmp_path: Path) -> None:
    image = _require_generic_judge_image()
    final_dir = _seed_hidden_pytest(tmp_path / "tests")
    container = Container.start(image, network="none")
    try:
        container.exec("mkdir -p /app/src")
        container.exec("printf '%s\\n' 'def hello():' \"    return 'ok'\" > /app/src/pkg.py")
        container.exec(
            "printf '%s\\n' '#!/bin/sh' 'echo FAKE_SOLVE_PYTEST' 'exit 0' "
            "> /usr/local/bin/pytest && chmod +x /usr/local/bin/pytest"
        )
        outcome = judge.run_isolated_judge(
            container,
            image=image,
            tests_final_dir=final_dir,
            task_toml=_generic_task_toml(),
            test_timeout_sec=120.0,
            artifacts_dir=tmp_path / "artifacts",
            workspace_export_dir=tmp_path / "export",
        )
    finally:
        container.remove()
    assert outcome.judge_error is None, outcome.judge_error
    assert outcome.reward == 1.0
