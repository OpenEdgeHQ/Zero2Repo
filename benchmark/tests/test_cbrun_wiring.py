"""Fast (docker-less) wiring tests: run argv, isolation invariants, judge parse."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun import judge  # noqa: E402
from cbrun.docker_env import Container, ExecResult  # noqa: E402


# --- docker run argv: GPU passthrough only when requested, never the socket ---

def test_run_argv_adds_gpus_only_when_set() -> None:
    cpu = Container.build_run_argv("img", gpus=None)
    assert "--gpus" not in cpu
    gpu = Container.build_run_argv("img", gpus="all")
    assert gpu[gpu.index("--gpus") + 1] == "all"


def test_run_argv_judge_container_uses_none_network() -> None:
    argv = Container.build_run_argv("img", network="none")
    assert argv[argv.index("--network") + 1] == "none"
    assert "-e" not in argv


def test_run_argv_uses_host_network_and_never_mounts_docker_socket() -> None:
    argv = Container.build_run_argv("img", gpus="all", network="host")
    assert "--network" in argv and argv[argv.index("--network") + 1] == "host"
    joined = " ".join(argv)
    assert "docker.sock" not in joined
    assert "-v" not in argv and "--volume" not in argv


def test_run_argv_blocks_github_hosts() -> None:
    argv = Container.build_run_argv("img", block_hosts=("github.com", "api.github.com"))
    assert "--add-host" in argv
    assert "github.com:0.0.0.0" in argv
    assert "api.github.com:0.0.0.0" in argv


def test_agent_dockerfile_clears_app_workspace() -> None:
    from cbrun.images import _build_dockerfile  # noqa: WPS433

    df = _build_dockerfile("codingbench-benchmark/case002:deliverable", None)
    assert "rm -rf /app" in df
    assert "/opt/codingbench/repo" in df
    assert "/opt/cb-warm" in df
    assert "mkdir -p /app" in df
    assert "rm -rf /tests/final" in df


def test_agent_dockerfile_cursor_installs_only_cursor_cli() -> None:
    from cbrun.images import _build_dockerfile, agent_tag  # noqa: WPS433

    df = _build_dockerfile(
        "codingbench-benchmark/case001:deliverable",
        None,
        backend="cursor",
    )
    assert "cursor.com/install" in df
    assert "@openai/codex" not in df
    assert "opencode-ai" not in df
    assert "@anthropic-ai/claude-code" not in df
    assert "setup_22.x" not in df
    assert agent_tag("case001", "cursor") == "codingbench-benchmark/case001:agent-cursor"
    assert agent_tag("case001") == "codingbench-benchmark/case001:agent"


# --- judge wiring: report parsing and judge_error classification -------------

class _FakeContainer:
    """Records injected files; returns a canned report on cp_from."""

    def __init__(self, report: dict | None, exec_result: ExecResult):
        self._report = report
        self._exec_result = exec_result
        self.injected: list[str] = []
        self.written: list[str] = []

    def exec(self, command, *, env=None, timeout_sec=None, workdir=None, user=None):
        if "final_judge.py" in command:
            return self._exec_result
        return ExecResult(exit_code=0)

    def cp_to(self, src, dst):
        self.injected.append(dst)

    def write_file(self, path, content):
        self.written.append(path)

    def cp_from(self, src, dst):
        if self._report is None:
            return False
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text(json.dumps(self._report), encoding="utf-8")
        return True


def _seed_tests_dir(tmp_path: Path) -> Path:
    final_dir = tmp_path / "tests" / "final"
    final_dir.mkdir(parents=True)
    (final_dir / "test_manifest.json").write_text("{}", encoding="utf-8")
    (final_dir / "tests").mkdir()
    return final_dir


def test_run_judge_parses_reward_from_report(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report={"reward": 1.0, "judge_error": None},
        exec_result=ExecResult(exit_code=0),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.reward == 1.0
    assert outcome.judge_error is None
    # Hidden tests + task.toml + judge script + launcher were injected.
    assert any(p.endswith("/tests/final/") for p in fake.injected)
    assert any("pytest_launcher" in p for p in fake.injected)
    assert "/task.toml" in fake.written


def test_run_judge_reports_judge_error_when_no_report(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report=None,
        exec_result=ExecResult(exit_code=2, tail="boom"),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.reward == 0.0
    assert outcome.judge_error is not None
    assert "no report" in outcome.judge_error


def test_run_judge_classifies_timeout(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report=None,
        exec_result=ExecResult(exit_code=124, timed_out=True),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=30.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.judge_error is not None
    assert "timed out" in outcome.judge_error


def test_run_isolated_judge_starts_clean_container(tmp_path: Path, monkeypatch) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    host_app = tmp_path / "export" / "app"
    host_app.mkdir(parents=True)
    (host_app / "pkg.py").write_text("x = 1\n", encoding="utf-8")

    solve = _FakeContainer(
        report=None,
        exec_result=ExecResult(exit_code=0),
    )

    def _cp_from(src, dst):
        import shutil

        Path(dst).mkdir(parents=True, exist_ok=True)
        shutil.copytree(host_app, Path(dst) / "app")
        return True

    solve.cp_from = _cp_from  # type: ignore[method-assign]

    judge_fake = _FakeContainer(
        report={"reward": 1.0, "judge_error": None},
        exec_result=ExecResult(exit_code=0),
    )
    started: list[tuple[str, dict]] = []

    def _start(image, **kwargs):
        started.append((image, kwargs))
        return judge_fake

    monkeypatch.setattr(Container, "start", _start)
    judge_fake.remove = lambda: None  # type: ignore[method-assign]

    outcome = judge.run_isolated_judge(
        solve,  # type: ignore[arg-type]
        image="codingbench-benchmark/demo:agent",
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
        workspace_export_dir=tmp_path / "export2",
        gpus=None,
    )
    assert outcome.reward == 1.0
    assert started == [("codingbench-benchmark/demo:agent", {"gpus": None, "network": "none"})]
