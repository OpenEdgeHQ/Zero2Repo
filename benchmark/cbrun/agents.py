"""Agent backend command templates and provider env for cbrun.

Built-in backends are defined as :class:`~cbrun.agent_spec.AgentSpec` records.
This module keeps the historical function names used by tests and Harbor-adjacent
code; new code should prefer :func:`cbrun.agent_spec.resolve_agent`.
"""

from __future__ import annotations

import os
import shlex

from .agent_spec import (
    BACKENDS,
    AgentInvocation,
    builtin_spec,
    resolve_agent,
)

__all__ = [
    "BACKENDS",
    "AgentInvocation",
    "build_agent_command",
    "provider_env",
    "cli_version_spec",
    "cli_install_command",
    "resolve_invocation",
]

# CLI npm packages. Versions default to "@latest" (matching the released task
# image) but SHOULD be pinned for reproducible benchmark results via the env
# vars below; cbrun warns when they are unpinned.
_CLI_PACKAGES = {
    "codex": ("@openai/codex", "CBRUN_CODEX_VERSION"),
    "opencode": ("opencode-ai", "CBRUN_OPENCODE_VERSION"),
    "claude-code": ("@anthropic-ai/claude-code", "CBRUN_CLAUDE_VERSION"),
}
_CLI_BINS = {
    "codex": "codex",
    "opencode": "opencode",
    "claude-code": "claude",
    "cursor": "cursor-agent",
}
_CURSOR_INSTALL_URL = "https://cursor.com/install"
_CURSOR_VERSION_ENV = "CBRUN_CURSOR_VERSION"


def cli_version_spec(backend: str, environ: dict[str, str] | None = None) -> str:
    """Return the version pin suffix used by the backend installer."""
    _require_backend(backend)
    environ = os.environ if environ is None else environ
    if backend == "cursor":
        pinned = (environ.get(_CURSOR_VERSION_ENV, "") or "").strip()
        return pinned or "latest"
    _pkg, env_key = _CLI_PACKAGES[backend]
    pinned = (environ.get(env_key, "") or "").strip()
    return f"@{pinned}" if pinned else "@latest"


def _cursor_install_command(environ: dict[str, str] | None) -> str:
    environ = os.environ if environ is None else environ
    pinned = (environ.get(_CURSOR_VERSION_ENV, "") or "").strip()
    version_export = f"export CURSOR_VERSION={shlex.quote(pinned)}; " if pinned else ""
    return (
        "set -eu; "
        "if command -v cursor-agent >/dev/null 2>&1; then cursor-agent --version; exit 0; fi; "
        "if command -v agent >/dev/null 2>&1; then "
        "  ln -sfn \"$(command -v agent)\" /usr/local/bin/cursor-agent; "
        "  cursor-agent --version; exit 0; "
        "fi; "
        "command -v curl >/dev/null 2>&1 || { "
        "  if command -v apt-get >/dev/null 2>&1; then "
        "    apt-get update && apt-get install -y --no-install-recommends curl ca-certificates; "
        "  elif command -v apk >/dev/null 2>&1; then apk add --no-cache curl; "
        "  else echo 'cbrun: curl required to install Cursor CLI' >&2; exit 1; fi; "
        "}; "
        f"{version_export}"
        f"curl -fsSL {_CURSOR_INSTALL_URL} | bash; "
        "if [ -x \"$HOME/.local/bin/agent\" ]; then "
        "  ln -sfn \"$HOME/.local/bin/agent\" /usr/local/bin/agent; "
        "  ln -sfn \"$HOME/.local/bin/agent\" /usr/local/bin/cursor-agent; "
        "elif [ -x \"$HOME/.local/bin/cursor-agent\" ]; then "
        "  ln -sfn \"$HOME/.local/bin/cursor-agent\" /usr/local/bin/cursor-agent; "
        "  ln -sfn \"$HOME/.local/bin/cursor-agent\" /usr/local/bin/agent; "
        "fi; "
        "command -v cursor-agent >/dev/null 2>&1 || { "
        "echo 'cbrun: Cursor CLI install did not produce cursor-agent' >&2; exit 1; }; "
        "cursor-agent --version"
    )


def cli_install_command(backend: str, environ: dict[str, str] | None = None) -> str:
    """Idempotent in-container install command for a backend's CLI."""
    _require_backend(backend)
    if backend == "cursor":
        return _cursor_install_command(environ)
    pkg, _env_key = _CLI_PACKAGES[backend]
    spec = cli_version_spec(backend, environ)
    bin_name = _CLI_BINS[backend]
    return (
        "set -eu; "
        f"if command -v {bin_name} >/dev/null 2>&1; then {bin_name} --version; exit 0; fi; "
        "command -v npm >/dev/null 2>&1 || { "
        "echo 'cbrun: npm not found in agent image' >&2; exit 1; }; "
        f"npm install -g {shlex.quote(pkg + spec)} && {bin_name} --version"
    )


def resolve_invocation(
    backend: str,
    *,
    model: str,
    instruction_path: str,
    log_path: str,
    environ: dict[str, str] | None = None,
    model_prefix: str | None = None,
) -> AgentInvocation:
    """Resolve a built-in backend to a full :class:`AgentInvocation`."""
    spec = builtin_spec(backend)
    if model_prefix is not None:
        from dataclasses import replace

        if model_prefix not in ("keep", "strip"):
            raise ValueError("model_prefix must be 'keep' or 'strip'")
        spec = replace(spec, model_prefix=model_prefix)  # type: ignore[arg-type]
    return resolve_agent(
        spec=spec,
        model=model,
        instruction_path=instruction_path,
        log_path=log_path,
        environ=environ,
    )


def build_agent_command(
    backend: str,
    *,
    model: str,
    instruction_path: str,
    log_path: str,
    workdir: str = "/app",
    codex_profile: str = "",
    preserve_model_provider_prefix: bool = False,
) -> str:
    """Build the in-container shell command that runs one solve."""
    del workdir, codex_profile  # workdir is fixed /app; profiles are user-owned
    prefix = "keep" if preserve_model_provider_prefix else None
    inv = resolve_invocation(
        backend,
        model=model,
        instruction_path=instruction_path,
        log_path=log_path,
        model_prefix=prefix,
    )
    return inv.command


def provider_env(
    backend: str,
    model: str,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    """Select auth/provider env vars to forward into the container."""
    inv = resolve_invocation(
        backend,
        model=model,
        instruction_path="/tmp/unused",
        log_path="/tmp/unused.log",
        environ=environ,
    )
    return inv.env


def _require_backend(backend: str) -> None:
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; choose from {BACKENDS}")
