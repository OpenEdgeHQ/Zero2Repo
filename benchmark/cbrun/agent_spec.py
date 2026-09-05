"""Declarative agent specifications for cbrun.

Users bring their own credentials and may supply a local AgentSpec file
(``.json`` or ``.yaml`` when PyYAML is installed). Built-in backends
(``codex``, ``opencode``, ``claude-code``, ``cursor``) are predefined specs.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .agent_hooks import claude_code_env, opencode_env

__all__ = [
    "AGENT_USER",
    "AGENT_USER_HOME",
    "CONTAINER_WORKDIR",
    "AgentInvocation",
    "AgentSpec",
    "BACKENDS",
    "builtin_spec",
    "load_agent_spec",
    "resolve_agent",
]

BACKENDS = ("codex", "opencode", "claude-code", "cursor")

AGENT_USER = "cbagent"
AGENT_USER_HOME = "/home/cbagent"
# Claude Code stores its session/config under CLAUDE_CONFIG_DIR. Some
# published images pin this to a root-owned path (``/claude-home``)
# that a non-root solve agent cannot write, which
# breaks the Bash tool at init (it mkdir's ``$CLAUDE_CONFIG_DIR/session-env``).
# cbrun therefore repoints it into the agent's own writable HOME.
AGENT_CLAUDE_CONFIG_DIRNAME = ".claude"
CONTAINER_WORKDIR = "/app"
CONTAINER_INSTRUCTION_PATH = "/tmp/cbrun/instruction.md"
CONTAINER_AGENT_LOG = "/logs/agent/agent.txt"
CONTAINER_AGENT_SETUP_LOG = "/logs/agent/agent_setup.log"

RunAs = Literal["root", "nonroot"]
ModelPrefix = Literal["keep", "strip"]

_HOOKS: dict[str, Any] = {
    "cbrun.agent_hooks:claude_code_env": claude_code_env,
    "cbrun.agent_hooks:opencode_env": opencode_env,
}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    command: str
    env_passthrough: tuple[str, ...] = ()
    setup_script: str | None = None
    install_script: str | None = None
    run_as: RunAs = "root"
    model_prefix: ModelPrefix = "keep"
    home: str | None = None
    setup_timeout_sec: float = 120.0
    python_hook: str | None = None

    def spec_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "env_passthrough": list(self.env_passthrough),
            "setup_script": self.setup_script,
            "install_script": self.install_script,
            "run_as": self.run_as,
            "model_prefix": self.model_prefix,
            "home": self.home,
            "setup_timeout_sec": self.setup_timeout_sec,
            "python_hook": self.python_hook,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        name = str(data.get("name") or "").strip()
        command = str(data.get("command") or "").strip()
        if not name:
            raise ValueError("AgentSpec requires 'name'")
        if not command:
            raise ValueError(f"AgentSpec {name!r} requires 'command'")
        run_as = str(data.get("run_as") or "root").strip()
        if run_as not in ("root", "nonroot"):
            raise ValueError(f"AgentSpec {name!r}: run_as must be 'root' or 'nonroot'")
        model_prefix = str(data.get("model_prefix") or "keep").strip()
        if model_prefix not in ("keep", "strip"):
            raise ValueError(f"AgentSpec {name!r}: model_prefix must be 'keep' or 'strip'")
        passthrough = data.get("env_passthrough") or []
        if not isinstance(passthrough, list):
            raise ValueError(f"AgentSpec {name!r}: env_passthrough must be a list")
        return cls(
            name=name,
            command=command,
            env_passthrough=tuple(str(k) for k in passthrough),
            setup_script=_optional_str(data.get("setup_script")),
            install_script=_optional_str(data.get("install_script")),
            run_as=run_as,  # type: ignore[arg-type]
            model_prefix=model_prefix,  # type: ignore[arg-type]
            home=_optional_str(data.get("home")),
            setup_timeout_sec=float(data.get("setup_timeout_sec") or 120.0),
            python_hook=_optional_str(data.get("python_hook")),
        )


@dataclass(frozen=True)
class AgentInvocation:
    """Fully-resolved agent invocation for one solve phase."""

    spec: AgentSpec
    model: str
    resolved_model: str
    command: str
    env: dict[str, str]
    env_keys: tuple[str, ...]
    setup_script: str | None
    install_script: str | None
    prepare_workspace: str
    run_as: str | None  # docker exec -u value; None => root
    home: str
    setup_timeout_sec: float
    spec_hash: str = field(repr=False, default="")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_spec_file(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"agent spec not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:
            raise RuntimeError(
                f"PyYAML is required to load {path.name}; use a .json spec or "
                "pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"agent spec must be a mapping: {path}")
    return data


def load_agent_spec(path: Path | str) -> AgentSpec:
    """Load an AgentSpec from a local trusted file (JSON or YAML)."""
    return AgentSpec.from_dict(_load_spec_file(Path(path)))


def builtin_spec(name: str) -> AgentSpec:
    if name not in BACKENDS:
        raise ValueError(f"unknown built-in backend {name!r}; choose from {BACKENDS}")
    return _BUILTIN_SPECS[name]


def resolve_agent(
    *,
    backend: str | None = None,
    agent_spec_path: Path | str | None = None,
    spec: AgentSpec | None = None,
    model: str,
    instruction_path: str = CONTAINER_INSTRUCTION_PATH,
    log_path: str = CONTAINER_AGENT_LOG,
    environ: dict[str, str] | None = None,
) -> AgentInvocation:
    if sum(x is not None for x in (backend, agent_spec_path, spec)) != 1:
        raise ValueError("pass exactly one of backend=, agent_spec_path=, or spec=")
    if spec is not None:
        resolved_spec = spec
    elif agent_spec_path is not None:
        resolved_spec = load_agent_spec(agent_spec_path)
    else:
        resolved_spec = builtin_spec(backend)  # type: ignore[arg-type]

    if not model:
        raise ValueError("model is required")
    if resolved_spec.name == "opencode" and "/" not in model:
        raise ValueError(
            "opencode model must be in 'provider/model' form, got " + repr(model)
        )

    environ = os.environ if environ is None else environ
    env, env_keys = _resolve_env(resolved_spec, model=model, environ=environ)
    resolved_model = _resolve_model(resolved_spec, model)
    ctx = {
        "model": resolved_model,
        "model_quoted": shlex.quote(resolved_model),
        "raw_model": model,
        "instruction": instruction_path,
        "instruction_quoted": shlex.quote(instruction_path),
        "log": log_path,
        "log_quoted": shlex.quote(log_path),
        "workdir": CONTAINER_WORKDIR,
        "workdir_quoted": shlex.quote(CONTAINER_WORKDIR),
        "home": _home_for(resolved_spec),
    }
    command = _render_template(resolved_spec.command, ctx)
    setup = _render_optional(resolved_spec.setup_script, ctx)
    install = resolved_spec.install_script
    prepare = _prepare_workspace_script(resolved_spec)
    run_as = AGENT_USER if resolved_spec.run_as == "nonroot" else None
    return AgentInvocation(
        spec=resolved_spec,
        model=model,
        resolved_model=resolved_model,
        command=command,
        env=env,
        env_keys=env_keys,
        setup_script=setup,
        install_script=install,
        prepare_workspace=prepare,
        run_as=run_as,
        home=_home_for(resolved_spec),
        setup_timeout_sec=resolved_spec.setup_timeout_sec,
        spec_hash=resolved_spec.spec_hash(),
    )


def _home_for(spec: AgentSpec) -> str:
    if spec.home:
        return spec.home
    if spec.run_as == "nonroot":
        return AGENT_USER_HOME
    if spec.name == "codex":
        return "/root/.codex"
    return "/root"


def _resolve_model(spec: AgentSpec, model: str) -> str:
    if spec.model_prefix == "strip" and "/" in model:
        return model.split("/")[-1]
    return model


def _resolve_env(
    spec: AgentSpec,
    *,
    model: str,
    environ: dict[str, str],
) -> tuple[dict[str, str], tuple[str, ...]]:
    out: dict[str, str] = {}
    keys: list[str] = []
    for key in spec.env_passthrough:
        if environ.get(key):
            out[key] = environ[key]
            keys.append(key)
    if spec.python_hook:
        hook = _load_hook(spec.python_hook)
        extra = hook(model=model, environ=environ, spec=spec)
        for key, value in extra.items():
            if value:
                out[key] = value
                if key not in keys:
                    keys.append(key)
    if spec.name == "codex":
        out.setdefault("CODEX_HOME", _home_for(spec))
        if "CODEX_HOME" not in keys:
            keys.append("CODEX_HOME")
    if spec.name == "claude-code" and spec.run_as == "nonroot":
        # Override any image-baked (root-owned) CLAUDE_CONFIG_DIR with a path the
        # non-root agent can write, so the Bash tool can create its session dir.
        out["CLAUDE_CONFIG_DIR"] = _claude_config_dir(spec)
        if "CLAUDE_CONFIG_DIR" not in keys:
            keys.append("CLAUDE_CONFIG_DIR")
    if spec.run_as == "nonroot":
        home = _home_for(spec)
        out.setdefault("HOME", home)
        if "HOME" not in keys:
            keys.append("HOME")
    return out, tuple(keys)


def _load_hook(path: str):
    if path in _HOOKS:
        return _HOOKS[path]
    module_name, _, attr = path.partition(":")
    if not attr:
        raise ValueError(f"invalid python_hook (expected module:callable): {path!r}")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise ValueError(f"python_hook {path!r} is not callable")
    return fn


def _render_optional(template: str | None, ctx: dict[str, str]) -> str | None:
    if not template:
        return None
    return _render_template(template, ctx)


def _render_template(template: str, ctx: dict[str, str]) -> str:
    """Substitute ``{key}`` placeholders without interpreting other braces."""
    out = template
    for key, value in ctx.items():
        out = out.replace("{" + key + "}", value)
    return out


def _prepare_workspace_script(spec: AgentSpec) -> str:
    workdir = CONTAINER_WORKDIR
    if spec.run_as == "nonroot":
        home = _home_for(spec)
        paths = [workdir, home, "/tmp/cbrun", "/logs/agent"]
        if spec.name == "claude-code":
            # Ensure the repointed CLAUDE_CONFIG_DIR exists and is agent-owned so
            # Claude Code's Bash tool can initialize its session directory.
            paths.append(_claude_config_dir(spec))
        quoted = " ".join(shlex.quote(p) for p in paths)
        return (
            f"set -eu; "
            f"mkdir -p {quoted}; "
            f"chown -R {AGENT_USER}:{AGENT_USER} {quoted}"
        )
    return f"set -eu; mkdir -p {shlex.quote(workdir)} /logs/agent"


def _claude_config_dir(spec: AgentSpec) -> str:
    """Writable CLAUDE_CONFIG_DIR under the agent HOME (posix join)."""
    home = _home_for(spec).rstrip("/")
    return f"{home}/{AGENT_CLAUDE_CONFIG_DIRNAME}"


_CODEX_SETUP = """set -eu
mkdir -p "$CODEX_HOME"
if [ -n "${OPENAI_API_KEY:-}" ]; then
  printf '%s\\n' "{\\"OPENAI_API_KEY\\": \\"${OPENAI_API_KEY}\\"}" > "$CODEX_HOME/auth.json"
fi
if [ -n "${OPENAI_BASE_URL:-}" ]; then
  printf '%s\\n' "openai_base_url = \\"${OPENAI_BASE_URL}\\"" >> "$CODEX_HOME/config.toml"
fi
"""

_BUILTIN_SPECS: dict[str, AgentSpec] = {
    "codex": AgentSpec(
        name="codex",
        env_passthrough=("OPENAI_API_KEY", "OPENAI_BASE_URL"),
        setup_script=_CODEX_SETUP,
        run_as="root",
        model_prefix="keep",
        home="/root/.codex",
        command=(
            "codex exec "
            "--dangerously-bypass-approvals-and-sandbox "
            "--skip-git-repo-check "
            "--cd {workdir_quoted} "
            "--model {model_quoted} "
            "--json "
            "--enable unified_exec "
            '-- "$(cat {instruction_quoted})" '
            "2>&1 </dev/null | stdbuf -oL tee {log_quoted}"
        ),
    ),
    "opencode": AgentSpec(
        name="opencode",
        env_passthrough=(),
        python_hook="cbrun.agent_hooks:opencode_env",
        run_as="root",
        model_prefix="keep",
        command=(
            "opencode --model={model_quoted} run "
            "--format=json --thinking --auto "
            "-- $(cat {instruction_quoted}) "
            "2>&1 | stdbuf -oL tee {log_quoted}"
        ),
    ),
    "claude-code": AgentSpec(
        name="claude-code",
        env_passthrough=(),
        python_hook="cbrun.agent_hooks:claude_code_env",
        run_as="nonroot",
        model_prefix="keep",
        home=AGENT_USER_HOME,
        command=(
            "cat {instruction_quoted} | claude --print --verbose --output-format stream-json "
            "--permission-mode bypassPermissions "
            "--model {model_quoted} "
            "2>&1 | stdbuf -oL tee {log_quoted}"
        ),
    ),
    "cursor": AgentSpec(
        name="cursor",
        env_passthrough=("CURSOR_API_KEY",),
        run_as="root",
        model_prefix="keep",
        home="/root",
        command=(
            "cursor-agent -p --force --trust --sandbox disabled "
            "--model {model_quoted} --workspace {workdir_quoted} "
            "--output-format text "
            "< {instruction_quoted} "
            "2>&1 | stdbuf -oL tee {log_quoted}"
        ),
    ),
}
