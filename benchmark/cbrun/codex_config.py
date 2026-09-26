"""Codex ``config.toml`` fragments shared by cbrun and the Harbor adapter.

Codex's built-in ``openai`` provider tries the Responses WebSocket transport
first and cannot be overridden from config. ``openai_base_url`` only re-points
that provider, so behind an OpenAI-compatible HTTPS gateway that does not carry
WSS every turn burns the whole reconnect budget (``Reconnecting... 1/5`` ..
``5/5``, ~15s each) before Codex falls back to HTTPS. The supported way out is a
named custom provider with ``supports_websockets = false``; that is what both
entry points write whenever ``OPENAI_BASE_URL`` is set.
"""

from __future__ import annotations

__all__ = [
    "CODEX_GATEWAY_PROVIDER",
    "CODEX_GATEWAY_WEBSOCKETS_ENV",
    "GATEWAY_MODEL_PROVIDER_LINE",
    "GATEWAY_PROVIDER_TABLE",
    "gateway_websockets_enabled",
]

CODEX_GATEWAY_PROVIDER = "gateway"
# Opt back into WSS for a gateway that is known to carry it.
CODEX_GATEWAY_WEBSOCKETS_ENV = "CBRUN_CODEX_GATEWAY_WEBSOCKETS"

# Top-level key; must be written before any ``[table]`` header.
GATEWAY_MODEL_PROVIDER_LINE = f'model_provider = "{CODEX_GATEWAY_PROVIDER}"\n'

# ``{base_url}`` and ``{websockets}`` are filled by the caller; cbrun leaves
# shell ``${VAR}`` expansions in place so the container resolves them.
GATEWAY_PROVIDER_TABLE = (
    f"[model_providers.{CODEX_GATEWAY_PROVIDER}]\n"
    'name = "OpenAI-compatible gateway"\n'
    'base_url = "{base_url}"\n'
    'env_key = "OPENAI_API_KEY"\n'
    'wire_api = "responses"\n'
    "supports_websockets = {websockets}\n"
)


def gateway_websockets_enabled(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes"}
