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
    assert "$(cat" not in inv.command
    assert "< /tmp/instr.md" in inv.command
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


def test_codex_reasoning_effort_written_into_setup() -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={"CBRUN_CODEX_REASONING_EFFORT": "medium"},
    )
    assert "CBRUN_CODEX_REASONING_EFFORT" in inv.env_keys
    assert inv.env["CBRUN_CODEX_REASONING_EFFORT"] == "medium"
    assert "model_reasoning_effort" in (inv.setup_script or "")
    assert "auth.json" not in (inv.setup_script or "").split("cat")[-1]


def test_codex_reasoning_effort_omitted_when_unset() -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={"OPENAI_API_KEY": "secret"},
    )
    assert "CBRUN_CODEX_REASONING_EFFORT" not in inv.env
    assert "model_reasoning_effort" in (inv.setup_script or "")


def _run_codex_setup(inv: agent_spec.AgentInvocation, codex_home: Path, **extra: str) -> dict:
    import subprocess
    import tomllib

    env = dict(inv.env, CODEX_HOME=str(codex_home), **extra)
    proc = subprocess.run(
        ["bash", "-c", inv.setup_script or "true"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "sk-secret" not in proc.stdout, "setup must not echo auth.json"
    cfg_path = codex_home / "config.toml"
    return tomllib.loads(cfg_path.read_text()) if cfg_path.exists() else {}


def test_codex_gateway_writes_https_only_named_provider(tmp_path: Path) -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={
            "OPENAI_API_KEY": "sk-secret",
            "OPENAI_BASE_URL": "https://gw.example/v1",
            "CBRUN_CODEX_REASONING_EFFORT": "medium",
        },
    )
    cfg = _run_codex_setup(inv, tmp_path / "a")
    assert "openai_base_url" not in cfg
    assert cfg["model_provider"] == "gateway"
    # Top-level keys must not be swallowed by the provider table.
    assert cfg["model_reasoning_effort"] == "medium"
    provider = cfg["model_providers"]["gateway"]
    assert provider["base_url"] == "https://gw.example/v1"
    assert provider["env_key"] == "OPENAI_API_KEY"
    assert provider["wire_api"] == "responses"
    assert provider["supports_websockets"] is False

    ws = _run_codex_setup(inv, tmp_path / "b", CBRUN_CODEX_GATEWAY_WEBSOCKETS="1")
    assert ws["model_providers"]["gateway"]["supports_websockets"] is True
    assert "CBRUN_CODEX_GATEWAY_WEBSOCKETS" in agent_spec.builtin_spec("codex").env_passthrough


def test_codex_without_gateway_keeps_builtin_provider(tmp_path: Path) -> None:
    inv = agent_spec.resolve_agent(
        backend="codex",
        model="openai/gpt-4o-mini",
        environ={"OPENAI_API_KEY": "sk-secret"},
    )
    cfg = _run_codex_setup(inv, tmp_path)
    assert "model_provider" not in cfg
    assert "model_providers" not in cfg
    assert (tmp_path / "auth.json").exists()


def test_codex_reasoning_effort_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="CBRUN_CODEX_REASONING_EFFORT"):
        agent_spec.resolve_agent(
            backend="codex",
            model="openai/gpt-4o-mini",
            environ={"CBRUN_CODEX_REASONING_EFFORT": "turbo"},
        )


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
    spec = agent_spec.AgentSpec(name="custom", command="true", run_as="nonroot")
    inv = agent_spec.resolve_agent(spec=spec, model="m")
    assert "cbagent" in inv.prepare_workspace
    assert "/app" in inv.prepare_workspace
