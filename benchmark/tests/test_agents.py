"""Smoke tests for CodingBench Harbor agent shims."""

from __future__ import annotations

import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from coding_bench_harbor.agents.claude_code import (  # noqa: E402
    CodingBenchClaudeCode,
    _claude_oauth_access_token_from_credentials,
)
from coding_bench_harbor.agents.codex import CodingBenchCodex  # noqa: E402
from coding_bench_harbor.agents.opencode import CodingBenchOpenCode  # noqa: E402


def test_opencode_shim_version_command(tmp_path: Path) -> None:
    agent = CodingBenchOpenCode(logs_dir=tmp_path)
    assert agent.get_version_command() == "opencode --version"


def test_claude_shim_version_command_uses_path(tmp_path: Path) -> None:
    agent = CodingBenchClaudeCode(logs_dir=tmp_path)
    cmd = agent.get_version_command()
    assert cmd is not None
    assert "claude --version" in cmd
    assert ".local/bin" in cmd


def test_claude_oauth_token_from_credentials(tmp_path: Path) -> None:
    cred = tmp_path / ".credentials.json"
    cred.write_text(
        '{"claudeAiOauth": {"accessToken": "tok-abc", "refreshToken": "r"}}',
        encoding="utf-8",
    )
    assert _claude_oauth_access_token_from_credentials(cred) == "tok-abc"
    assert _claude_oauth_access_token_from_credentials(tmp_path / "missing.json") is None


def test_codex_shim_version_command_defaults_to_no_profile(tmp_path: Path) -> None:
    agent = CodingBenchCodex(logs_dir=tmp_path)
    assert agent.get_version_command() == "codex --version"


def test_codex_shim_builds_noninteractive_exec_command(tmp_path: Path) -> None:
    agent = CodingBenchCodex(
        logs_dir=tmp_path,
        model_name="openai/gpt-5.5",
    )
    cmd = agent._build_codex_exec_command("build the project", "")
    assert cmd.startswith("codex exec --dangerously-bypass-approvals-and-sandbox")
    assert "--profile" not in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--cd /app" in cmd
    assert "--model gpt-5.5" in cmd
    assert "--json" in cmd
    assert "--enable unified_exec" in cmd
    assert "/logs/agent/codex.txt" in cmd


def test_codex_shim_profile_config_is_model_only(tmp_path: Path) -> None:
    agent = CodingBenchCodex(
        logs_dir=tmp_path,
        model_name="openai/gpt-5.5",
    )
    profile = agent._build_profile_config()
    assert profile.strip() == 'model = "gpt-5.5"'


def test_codex_shim_preserves_provider_prefix_when_requested(tmp_path: Path) -> None:
    agent = CodingBenchCodex(
        logs_dir=tmp_path,
        model_name="openai/gpt-5.5",
        preserve_model_provider_prefix=True,
    )
    assert 'model = "openai/gpt-5.5"' in agent._build_profile_config()
    assert "--model openai/gpt-5.5" in agent._build_codex_exec_command("x", "")


def test_codex_shim_allows_explicit_profile(tmp_path: Path) -> None:
    agent = CodingBenchCodex(
        logs_dir=tmp_path,
        model_name="openai/gpt-5.5",
        codex_command="codex",
        codex_profile="myprofile",
    )
    assert agent.get_version_command() == "codex --profile myprofile --version"
    assert agent._build_codex_exec_command("x", "").startswith(
        "codex exec --profile myprofile "
    )
