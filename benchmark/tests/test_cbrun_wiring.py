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


def test_run_argv_bind_mounts_judge_substrates() -> None:
    argv = Container.build_run_argv(
        "img",
        network="none",
        mounts=[("/tmp/cow", "/mnt/cb-substrate/cow_fs")],
    )
    assert "-v" in argv
    assert argv[argv.index("-v") + 1] == "/tmp/cow:/mnt/cb-substrate/cow_fs"
    assert "docker.sock" not in " ".join(argv)


def test_run_argv_blocks_github_hosts() -> None:
    argv = Container.build_run_argv("img", block_hosts=("github.com", "api.github.com"))
    assert "--add-host" in argv
    assert "github.com:0.0.0.0" in argv
    assert "api.github.com:0.0.0.0" in argv


_UNPINNED = {"CBRUN_ALLOW_UNPINNED_CLI": "1"}


def test_agent_dockerfile_clears_app_workspace() -> None:
    from cbrun.images import _build_dockerfile  # noqa: WPS433

    df = _build_dockerfile("codingbench-benchmark/sample:deliverable", _UNPINNED)
    assert "rm -rf /app" in df
    assert "/opt/codingbench/repo" in df
    assert "/opt/cb-warm" in df
    assert "mkdir -p /app" in df
    assert "rm -rf /tests/final" in df


def test_agent_dockerfile_all_backends_uses_per_cli_install() -> None:
    from cbrun.images import _build_dockerfile  # noqa: WPS433

    df = _build_dockerfile("codingbench-benchmark/sample:deliverable", _UNPINNED)
    assert '"$NODE" "$NPM" install -g --prefix' in df
    assert "@openai/codex" in df
    assert "opencode-ai" in df
    assert "@anthropic-ai/claude-code" in df
    assert "cursor.com/install" in df
    # Each npm CLI is installed on its own; the old concatenated line is gone.
    assert "codex@latest opencode-ai" not in df
    assert "opencode-ai@latest @anthropic" not in df
    assert "/opt/cbrun/runtime/node" in df
    assert "deb.nodesource.com" not in df
    assert "/usr/local/bin/node" not in df


def test_agent_dockerfile_cursor_installs_only_cursor_cli() -> None:
    from cbrun.images import _build_dockerfile, agent_tag  # noqa: WPS433

    df = _build_dockerfile(
        "codingbench-benchmark/sample:deliverable",
        _UNPINNED,
        backend="cursor",
    )
    assert "cursor.com/install" in df
    assert "@openai/codex" not in df
    assert "opencode-ai" not in df
    assert "@anthropic-ai/claude-code" not in df
    assert "setup_22.x" not in df
    assert agent_tag("sample", "cursor") == "codingbench-benchmark/sample:agent-cursor"
    assert agent_tag("sample") == "codingbench-benchmark/sample:agent"


# --- judge wiring: report parsing and judge_error classification -------------

class _FakeContainer:
    """Records injected files; returns a canned report on cp_from."""

    def __init__(self, report: dict | None, exec_result: ExecResult):
        self._report = report
        self._exec_result = exec_result
        self.injected: list[str] = []
        self.written: list[str] = []
        self.commands: list[str] = []
        self.contents: dict[str, bytes] = {}
        self.judge_env: dict[str, str] = {}

    def exec(self, command, *, env=None, timeout_sec=None, workdir=None, user=None):
        self.commands.append(command)
        if "final_judge.py" in command:
            self.judge_env = dict(env or {})
            return self._exec_result
        if "command -v node" in command and "readlink" in command:
            return ExecResult(exit_code=0, tail="/opt/nodejs/bin/node\n")
        return ExecResult(exit_code=0)

    def cp_to(self, src, dst):
        self.injected.append(dst)

    def write_file(self, path, content):
        self.written.append(path)
        self.contents[path] = content

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
        report={
            "reward": 1.0,
            "judge_error": None,
            "final": {
                "counts_parsed": True,
                "total_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "error_count": 0,
            },
        },
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
    assert outcome.completed is False
    assert outcome.incomplete_reason == "judge:no_report"


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
    assert outcome.completed is False
    assert outcome.incomplete_reason == "judge:timeout"


def test_run_judge_classifies_137_near_budget_as_timeout(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report=None,
        exec_result=ExecResult(exit_code=137, timed_out=True, seconds=60.0),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.completed is False
    assert outcome.incomplete_reason == "judge:timeout"
    assert "timed out" in (outcome.judge_error or "")


def test_run_judge_classifies_137_far_below_budget_as_killed(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report=None,
        exec_result=ExecResult(exit_code=137, timed_out=False, seconds=4.0),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.completed is False
    assert outcome.incomplete_reason == "judge:killed"
    assert "no report" in (outcome.judge_error or "")


def test_run_judge_report_internal_error_stays_completed(tmp_path: Path) -> None:
    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(
        report={
            "reward": 0.0,
            "judge_error": "shadowed pytest",
            "final": {"counts_parsed": True, "total_count": 1},
        },
        exec_result=ExecResult(exit_code=0),
    )
    outcome = judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
    )
    assert outcome.completed is True
    assert outcome.incomplete_reason is None
    assert outcome.judge_error == "shadowed pytest"
    assert outcome.reward == 0.0


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
        report={
            "reward": 1.0,
            "judge_error": None,
            "final": {
                "counts_parsed": True,
                "total_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "error_count": 0,
            },
        },
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
    assert started == [
        (
            "codingbench-benchmark/demo:agent",
            {"gpus": None, "network": "none", "mounts": []},
        )
    ]


_OK_REPORT = {
    "reward": 1.0,
    "judge_error": None,
    "final": {
        "counts_parsed": True,
        "total_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "error_count": 0,
    },
}


def _run_judge_with_denylist(tmp_path: Path, denylist, judge_bans=()) -> _FakeContainer:
    from types import SimpleNamespace

    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(report=_OK_REPORT, exec_result=ExecResult(exit_code=0))
    judge.run_judge(
        fake,  # type: ignore[arg-type]
        tests_final_dir=final_dir,
        task_toml=b"x = 1\n",
        test_timeout_sec=60.0,
        artifacts_dir=tmp_path / "art",
        denylist=SimpleNamespace(**denylist) if denylist else None,
        judge_bans=judge_bans,
    )
    return fake


def test_npm_import_ban_installs_node_shim_and_probes_it(tmp_path: Path) -> None:
    """The Node gate must not depend on the hidden harness keeping NODE_OPTIONS:
    a ``node`` wrapper with the ban baked in goes first on PATH via the launcher."""
    fake = _run_judge_with_denylist(
        tmp_path, {"ecosystem": "npm", "import_ban": ("js-yaml", "js-yaml/")}, judge_bans=("socket",)
    )
    # Both CJS and ESM preloads plus the hooks module are injected.
    assert judge.CONTAINER_NODE_BLOCK_PATH in fake.injected
    assert judge.CONTAINER_NODE_BLOCK_ESM_PATH in fake.injected
    assert judge.CONTAINER_NODE_BLOCK_HOOKS_PATH in fake.injected
    shim = fake.contents[judge.CONTAINER_NODE_SHIM_PATH].decode()
    assert shim.startswith("#!/bin/sh")
    exports = [line for line in shim.splitlines() if line.startswith("export ")]
    assert exports == [
        "export CODING_BENCH_WORKSPACE=/app",
        "export CODING_BENCH_IMPORT_BAN=js-yaml,js-yaml/",
        "export CODING_BENCH_JUDGE_BANS=socket",
    ]
    assert shim.rstrip().endswith(
        f"exec /opt/nodejs/bin/node --require {judge.CONTAINER_NODE_BLOCK_PATH} "
        f"--import {judge.CONTAINER_NODE_BLOCK_ESM_PATH} \"$@\""
    )
    env = fake.judge_env
    assert env["NODE_OPTIONS"] == (
        f"--require {judge.CONTAINER_NODE_BLOCK_PATH} --import {judge.CONTAINER_NODE_BLOCK_ESM_PATH}"
    )
    assert env[judge.NODE_SHIM_DIR_ENV] == judge.CONTAINER_NODE_SHIM_DIR
    # A canary ran before the judge: both hooks refuse a banned import, shim first on PATH.
    probes = [c for c in fake.commands if "esm hook inactive" in c]
    assert probes and "cjs hook inactive" in probes[0] and "node shim not first on PATH" in probes[0]
    assert fake.commands.index(probes[0]) < fake.commands.index(
        next(c for c in fake.commands if "final_judge.py" in c)
    )


def test_npm_gate_probe_failure_is_a_hard_error(tmp_path: Path) -> None:
    from types import SimpleNamespace

    import pytest

    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(report=_OK_REPORT, exec_result=ExecResult(exit_code=0))
    real_exec = fake.exec

    def failing_probe(command, **kwargs):
        if "esm hook inactive" in command:
            return ExecResult(exit_code=3, tail="esm hook inactive")
        return real_exec(command, **kwargs)

    fake.exec = failing_probe  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="gate probe failed"):
        judge.run_judge(
            fake,  # type: ignore[arg-type]
            tests_final_dir=final_dir,
            task_toml=b"x = 1\n",
            test_timeout_sec=60.0,
            artifacts_dir=tmp_path / "art",
            denylist=SimpleNamespace(ecosystem="npm", import_ban=("js-yaml",)),
        )


def test_npm_gate_requires_node_in_judge_image(tmp_path: Path) -> None:
    from types import SimpleNamespace

    import pytest

    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(report=_OK_REPORT, exec_result=ExecResult(exit_code=0))
    real_exec = fake.exec

    def no_node(command, **kwargs):
        if "command -v node" in command:
            return ExecResult(exit_code=0, tail="")
        return real_exec(command, **kwargs)

    fake.exec = no_node  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="no `node` is on PATH"):
        judge.run_judge(
            fake,  # type: ignore[arg-type]
            tests_final_dir=final_dir,
            task_toml=b"x = 1\n",
            test_timeout_sec=60.0,
            artifacts_dir=tmp_path / "art",
            denylist=SimpleNamespace(ecosystem="npm", import_ban=("js-yaml",)),
        )


def test_pip_import_ban_does_not_touch_node(tmp_path: Path) -> None:
    fake = _run_judge_with_denylist(tmp_path, {"ecosystem": "pip", "import_ban": ("yaml",)})
    assert judge.CONTAINER_NODE_SHIM_PATH not in fake.contents
    assert judge.CONTAINER_NODE_BLOCK_PATH not in fake.injected
    assert "NODE_OPTIONS" not in fake.judge_env
    assert judge.NODE_SHIM_DIR_ENV not in fake.judge_env
    assert fake.judge_env["CODING_BENCH_IMPORT_BAN"] == "yaml"
    assert any("cbrun_denylist_hook" in c and "sys.modules" in c for c in fake.commands)


def test_pip_gate_probe_failure_is_a_hard_error(tmp_path: Path) -> None:
    from types import SimpleNamespace

    import pytest

    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(report=_OK_REPORT, exec_result=ExecResult(exit_code=0))
    real_exec = fake.exec

    def failing_probe(command, **kwargs):
        if "cbrun_denylist_hook" in command and "sys.modules" in command:
            return ExecResult(exit_code=7, tail="hook missing")
        return real_exec(command, **kwargs)

    fake.exec = failing_probe  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="pip denylist hook not loaded"):
        judge.run_judge(
            fake,  # type: ignore[arg-type]
            tests_final_dir=final_dir,
            task_toml=b"x = 1\n",
            test_timeout_sec=60.0,
            artifacts_dir=tmp_path / "art",
            denylist=SimpleNamespace(ecosystem="pip", import_ban=("yaml",)),
        )


def test_pip_gate_probe_rejects_pth_processing_error(tmp_path: Path) -> None:
    from types import SimpleNamespace

    import pytest

    final_dir = _seed_tests_dir(tmp_path)
    fake = _FakeContainer(report=_OK_REPORT, exec_result=ExecResult(exit_code=0))
    real_exec = fake.exec

    def noisy_probe(command, **kwargs):
        if "cbrun_denylist_hook" in command and "sys.modules" in command:
            return ExecResult(exit_code=0, tail="Error processing line 1 of zz_cbrun_denylist.pth")
        return real_exec(command, **kwargs)

    fake.exec = noisy_probe  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="pip denylist hook not loaded"):
        judge.run_judge(
            fake,  # type: ignore[arg-type]
            tests_final_dir=final_dir,
            task_toml=b"x = 1\n",
            test_timeout_sec=60.0,
            artifacts_dir=tmp_path / "art",
            denylist=SimpleNamespace(ecosystem="pip", import_ban=("yaml",)),
        )


def test_probe_cli_version_fails_fast_with_path() -> None:
    from cbrun.run_case import _probe_cli_version  # noqa: WPS433

    class _MissingCli:
        def exec(self, command, **_kwargs):
            if "command -v" in command:
                return ExecResult(exit_code=127, tail="codex: not found")
            if "PATH" in command:
                return ExecResult(exit_code=0, tail="/usr/bin:/bin")
            return ExecResult(exit_code=0)

    try:
        _probe_cli_version(_MissingCli(), "codex")  # type: ignore[arg-type]
    except RuntimeError as exc:
        msg = str(exc)
        assert "codex" in msg
        assert "/usr/bin:/bin" in msg
        assert "not found" in msg
    else:
        raise AssertionError("expected RuntimeError when the CLI is missing")


def test_probe_cli_version_unknown_spec_returns_none() -> None:
    from cbrun.run_case import _probe_cli_version  # noqa: WPS433

    assert _probe_cli_version(_FakeContainer(None, ExecResult(exit_code=0)), "custom") is None
