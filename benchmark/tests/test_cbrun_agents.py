"""Unit tests for cbrun agent command templates and provider env selection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun import agents  # noqa: E402


def test_backends_are_the_four_supported() -> None:
    assert set(agents.BACKENDS) == {"codex", "opencode", "claude-code", "cursor"}


def test_codex_command_shape() -> None:
    cmd = agents.build_agent_command(
        "codex",
        model="openai/gpt-5.5",
        instruction_path="/tmp/cbrun/instruction.md",
        log_path="/logs/agent/agent.txt",
        workdir="/app",
    )
    # No profile by default: the runner stays provider-neutral.
    assert cmd.startswith("codex exec --dangerously-bypass-approvals-and-sandbox")
    assert "--profile" not in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--skip-git-repo-check" in cmd
    assert "--cd /app" in cmd
    # provider prefix kept by default for OpenAI-compatible gateways
    assert "--model openai/gpt-5.5" in cmd or "--model 'openai/gpt-5.5'" in cmd
    assert "--json" in cmd
    assert "--enable unified_exec" in cmd
    assert "cat /tmp/cbrun/instruction.md" in cmd
    assert "tee /logs/agent/agent.txt" in cmd


def test_codex_can_strip_model_prefix() -> None:
    cmd = agents.build_agent_command(
        "codex",
        model="openai/gpt-5.5",
        instruction_path="/i.md",
        log_path="/l.txt",
        preserve_model_provider_prefix=False,
    )
    # Default spec keeps prefix; explicit strip via resolve_invocation override:
    cmd_strip = agents.resolve_invocation(
        "codex",
        model="openai/gpt-5.5",
        instruction_path="/i.md",
        log_path="/l.txt",
        model_prefix="strip",
    ).command
    assert "--model gpt-5.5" in cmd_strip or "--model 'gpt-5.5'" in cmd_strip
    assert "openai/gpt-5.5" not in cmd_strip


def test_codex_can_preserve_provider_prefix() -> None:
    cmd = agents.build_agent_command(
        "codex",
        model="openai/gpt-5.5",
        instruction_path="/i.md",
        log_path="/l.txt",
        codex_profile="",
        preserve_model_provider_prefix=True,
    )
    assert cmd.startswith("codex exec --dangerously-bypass-approvals-and-sandbox")
    assert "--model openai/gpt-5.5" in cmd


def test_opencode_command_shape() -> None:
    cmd = agents.build_agent_command(
        "opencode",
        model="openai/gpt-5.5",
        instruction_path="/i.md",
        log_path="/l.txt",
    )
    assert "opencode --model=" in cmd
    assert "openai/gpt-5.5" in cmd
    assert "--format=json" in cmd
    assert "--thinking" in cmd
    assert "--auto" in cmd
    assert cmd.startswith("opencode --model=")
    assert "tee /l.txt" in cmd


def test_opencode_requires_provider_prefixed_model() -> None:
    with pytest.raises(ValueError):
        agents.build_agent_command(
            "opencode", model="gpt-5.5", instruction_path="/i.md", log_path="/l.txt"
        )


def test_claude_command_shape() -> None:
    cmd = agents.build_agent_command(
        "claude-code",
        model="claude-sonnet-4",
        instruction_path="/i.md",
        log_path="/l.txt",
    )
    assert "claude --print --verbose --output-format stream-json" in cmd
    assert "--permission-mode bypassPermissions" in cmd
    assert "--model claude-sonnet-4" in cmd
    assert cmd.startswith("cat /i.md | claude")
    assert "tee /l.txt" in cmd


def test_unknown_backend_rejected() -> None:
    with pytest.raises(ValueError):
        agents.build_agent_command(
            "aider", model="x/y", instruction_path="/i.md", log_path="/l.txt"
        )


def test_missing_model_rejected() -> None:
    with pytest.raises(ValueError):
        agents.build_agent_command(
            "codex", model="", instruction_path="/i.md", log_path="/l.txt"
        )


def test_provider_env_opencode_openai_forwards_present_keys_only() -> None:
    env = agents.provider_env(
        "opencode",
        "openai/gpt-5.5",
        environ={"OPENAI_API_KEY": "sk-x", "UNRELATED": "1"},
    )
    assert env["OPENAI_API_KEY"] == "sk-x"
    assert env["OPENCODE_FAKE_VCS"] == "git"
    assert "UNRELATED" not in env


def test_provider_env_opencode_skips_absent_keys() -> None:
    env = agents.provider_env("opencode", "anthropic/claude", environ={})
    assert "ANTHROPIC_API_KEY" not in env
    assert env["OPENCODE_FAKE_VCS"] == "git"


def test_provider_env_claude_oauth_when_no_api_key() -> None:
    env = agents.provider_env(
        "claude-code",
        "claude-sonnet-4",
        environ={"CLAUDE_CODE_OAUTH_TOKEN": "tok", "ANTHROPIC_BASE_URL": "http://x"},
    )
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok"
    # OAuth path must not forward ANTHROPIC_* overrides.
    assert "ANTHROPIC_BASE_URL" not in env


def test_provider_env_claude_api_key_path() -> None:
    env = agents.provider_env(
        "claude-code",
        "claude-sonnet-4",
        environ={"ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "http://x"},
    )
    assert env["ANTHROPIC_API_KEY"] == "k"
    assert env["ANTHROPIC_BASE_URL"] == "http://x"


def test_provider_env_codex_sets_home_and_forwards_openai_keys_only() -> None:
    env = agents.provider_env(
        "codex",
        "openai/gpt-5.5",
        environ={
            "OPENAI_API_KEY": "sk",
            "OPENAI_BASE_URL": "http://gateway/v1",
            "UNRELATED": "1",
        },
    )
    assert env["CODEX_HOME"] == "/root/.codex"
    assert env["OPENAI_API_KEY"] == "sk"
    assert env["OPENAI_BASE_URL"] == "http://gateway/v1"
    assert "UNRELATED" not in env


def test_cli_version_spec_defaults_latest_and_honors_pin() -> None:
    assert agents.cli_version_spec("codex", environ={}) == "@latest"
    assert agents.cli_version_spec("codex", environ={"CBRUN_CODEX_VERSION": "1.2.3"}) == "@1.2.3"


def test_claude_runs_nonroot() -> None:
    inv = agents.resolve_invocation(
        "claude-code",
        model="claude-sonnet-4",
        instruction_path="/i.md",
        log_path="/l.txt",
    )
    assert inv.run_as == "cbagent"
    assert inv.spec.run_as == "nonroot"
    assert "chown -R cbagent:cbagent" in inv.prepare_workspace


def test_claude_repoints_config_dir_into_writable_home() -> None:
    """CLAUDE_CONFIG_DIR must land under the agent HOME (not the root-owned
    image-baked path) or the Bash tool fails at init with EACCES."""
    inv = agents.resolve_invocation(
        "claude-code",
        model="claude-sonnet-4",
        instruction_path="/i.md",
        log_path="/l.txt",
        # Simulate a deliverable image that bakes a root-owned config dir.
        environ={"CLAUDE_CONFIG_DIR": "/claude-home"},
    )
    assert inv.env["CLAUDE_CONFIG_DIR"] == "/home/cbagent/.claude"
    assert "CLAUDE_CONFIG_DIR" in inv.env_keys
    # The config dir is created and chowned to the agent before solve.
    assert "/home/cbagent/.claude" in inv.prepare_workspace
    assert "chown -R cbagent:cbagent" in inv.prepare_workspace


def test_codex_has_setup_script() -> None:
    inv = agents.resolve_invocation(
        "codex",
        model="openai/gpt-5.5",
        instruction_path="/i.md",
        log_path="/l.txt",
        environ={"OPENAI_API_KEY": "sk-x", "OPENAI_BASE_URL": "http://gw/v1"},
    )
    assert inv.setup_script is not None
    assert "auth.json" in inv.setup_script
    assert "config.toml" in inv.setup_script
    assert inv.env["OPENAI_API_KEY"] == "sk-x"
    assert inv.env["CODEX_HOME"] == "/root/.codex"


def test_provider_env_opencode_anthropic_forwards_base_url() -> None:
    env = agents.provider_env(
        "opencode",
        "anthropic/claude-sonnet-4-6",
        environ={"ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "http://gw/v1"},
    )
    assert env["ANTHROPIC_API_KEY"] == "k"
    assert env["ANTHROPIC_BASE_URL"] == "http://gw/v1"
    assert env["OPENCODE_FAKE_VCS"] == "git"


def test_cli_install_command_is_idempotent_and_uses_pin() -> None:
    cmd = agents.cli_install_command("opencode", environ={"CBRUN_OPENCODE_VERSION": "9.9.9"})
    assert "command -v opencode" in cmd
    assert "npm install -g" in cmd
    assert "opencode-ai@9.9.9" in cmd


def test_cursor_command_shape() -> None:
    cmd = agents.build_agent_command(
        "cursor",
        model="cursor-grok-4.6-high",
        instruction_path="/tmp/cbrun/instruction.md",
        log_path="/logs/agent/agent.txt",
    )
    assert cmd.startswith("cursor-agent -p --force --trust --sandbox disabled")
    assert "--workspace /app" in cmd or "--workspace '/app'" in cmd
    assert "cursor-grok-4.6-high" in cmd
    assert "< /tmp/cbrun/instruction.md" in cmd or "< '/tmp/cbrun/instruction.md'" in cmd
    assert "$(cat" not in cmd
    assert "tee /logs/agent/agent.txt" in cmd


def test_provider_env_cursor_forwards_api_key_only() -> None:
    env = agents.provider_env(
        "cursor",
        "cursor-grok-4.6-high",
        environ={"CURSOR_API_KEY": "cur_sk", "UNRELATED": "1"},
    )
    assert env["CURSOR_API_KEY"] == "cur_sk"
    assert "UNRELATED" not in env


def test_cursor_cli_install_uses_official_script() -> None:
    cmd = agents.cli_install_command("cursor", environ={"CBRUN_CURSOR_VERSION": "1.2.3"})
    assert "cursor.com/install" in cmd
    assert "CURSOR_VERSION=1.2.3" in cmd
    assert "cursor-agent --version" in cmd
