"""Unit tests for cbrun AgentSpec loading, rendering and lifecycle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun import agent_spec  # noqa: E402


def test_builtin_specs_are_stable() -> None:
    for name in agent_spec.BACKENDS:
        spec = agent_spec.builtin_spec(name)
        assert spec.name == name
        assert spec.command
        assert spec.spec_hash()


def test_load_agent_spec_from_json(tmp_path: Path) -> None:
    path = tmp_path / "echo-agent.json"
    path.write_text(
        json.dumps(
            {
                "name": "echo-agent",
                "env_passthrough": ["MY_TOKEN"],
                "run_as": "root",
                "model_prefix": "keep",
                "setup_script": "echo setup > /logs/agent/agent_setup.log",
                "command": "echo hello {model} > {workdir_quoted}/smoke_probe.txt",
            }
        ),
        encoding="utf-8",
    )
    spec = agent_spec.load_agent_spec(path)
    assert spec.name == "echo-agent"
    assert spec.env_passthrough == ("MY_TOKEN",)


def test_resolve_agent_renders_placeholders() -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        instruction_path="/tmp/instr.md",
        log_path="/logs/agent/agent.txt",
    )
    assert "/tmp/instr.md" in inv.command or "/tmp/instr" in inv.command
    assert "openai/gpt-4o-mini" in inv.command
    assert inv.run_as is None


def test_model_prefix_strip() -> None:
    from dataclasses import replace

    spec = replace(agent_spec.builtin_spec("codex"), model_prefix="strip")
    inv = agent_spec.resolve_agent(spec=spec, model="openai/gpt-4o-mini")
    assert inv.resolved_model == "gpt-4o-mini"


def test_env_passthrough_only_forwards_present_keys() -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={"OPENAI_API_KEY": "secret", "OTHER": "x"},
    )
    assert "OPENAI_API_KEY" in inv.env
    assert "OTHER" not in env_keys if (env_keys := inv.env_keys) else False
    assert "OPENAI_API_KEY" in inv.env_keys


def test_resolve_agent_rejects_both_backend_and_spec_path(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text('{"name":"x","command":"true"}', encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        agent_spec.resolve_agent(
            backend="codex",
            agent_spec_path=path,
            model="openai/x",
        )


def test_invalid_run_as_rejected() -> None:
    with pytest.raises(ValueError, match="run_as"):
        agent_spec.AgentSpec.from_dict({"name": "x", "command": "true", "run_as": "admin"})


def test_prepare_workspace_nonroot_chowns_app() -> None:
    inv = agent_spec.resolve_agent(backend="claude-code", model="claude-sonnet-4")
    assert "cbagent" in inv.prepare_workspace
    assert "/app" in inv.prepare_workspace
