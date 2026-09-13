"""Exercise real shell pipeline status without requiring a Docker daemon."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.docker_env import Container  # noqa: E402


@pytest.mark.skipif(shutil.which("bash") is None, reason="requires Bash")
@pytest.mark.parametrize("agent_exit", [0, 7, 42])
def test_logging_pipeline_preserves_agent_exit(tmp_path: Path, monkeypatch, agent_exit: int) -> None:
    container = Container("unused-docker-id")

    def local_exec(command: str, **kwargs) -> list[str]:
        # Only replace the Docker/timeout boundary. Run the actual inner shell
        # assembled by exec_solve, including its shell options and pipeline.
        argv = shlex.split(command)
        assert argv[:2] == ["timeout", "--signal=KILL"]
        return argv[3:]

    monkeypatch.setattr(container, "_exec_argv", local_exec)
    monkeypatch.setattr(container, "_stop_agent", lambda marker: None)
    tee_log = tmp_path / "tee output.log"
    command = (
        f"(printf 'agent output\\n'; exit {agent_exit}) "
        f"2>&1 | tee {shlex.quote(str(tee_log))}"
    )
    result = container.exec_solve(
        command, workdir=str(tmp_path), env=None, wall_timeout_sec=10,
        stall_window_sec=0, log_path=tmp_path / "agent.log", stall_marker="unused",
    )
    assert result.exit_code == agent_exit
    assert not result.timed_out
    assert not result.stall_killed
    assert result.tail == "agent output\n"
    assert tee_log.read_text() == "agent output\n"
