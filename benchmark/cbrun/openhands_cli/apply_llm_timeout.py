"""Patch the OpenHands CLI inside an agent image.

The CLI constructs its LLM with the library default HTTP timeout of 300s and
does not read an environment override. LiteLLM then lets the OpenAI client
retry that wait twice with no log line. Thinking models often stay silent
longer than 300s, so each long turn becomes about 15 minutes of timeouts.

This build step:
- honors LLM_TIMEOUT (seconds) on the LLM object, including the condenser copy
- disables those silent inner retries so one configured timeout is one wait
"""

from __future__ import annotations

from pathlib import Path

SITE = Path(
    "/root/.local/share/uv/tools/openhands/lib/python3.12/site-packages"
)
AGENT_STORE = SITE / "openhands_cli/stores/agent_store.py"
LLM_PY = SITE / "openhands/sdk/llm/llm.py"

_LLM_BLOCK = """\
        llm = LLM(
            model=overrides.model,
            api_key=overrides.api_key.get_secret_value(),
            base_url=overrides.base_url,
            usage_id="agent",
        )
"""

_LLM_BLOCK_PATCHED = """\
        llm_kwargs = {
            "model": overrides.model,
            "api_key": overrides.api_key.get_secret_value(),
            "base_url": overrides.base_url,
            "usage_id": "agent",
        }
        timeout_raw = (os.environ.get("LLM_TIMEOUT") or "").strip()
        if timeout_raw:
            llm_kwargs["timeout"] = int(timeout_raw)
        llm = LLM(**llm_kwargs)
"""


def patch_agent_store(text: str) -> str:
    if _LLM_BLOCK_PATCHED in text:
        return text
    if _LLM_BLOCK not in text:
        raise SystemExit("openhands agent_store LLM() block not found")
    return text.replace(_LLM_BLOCK, _LLM_BLOCK_PATCHED, 1)


def patch_llm_transport(text: str) -> str:
    """One HTTP timeout per OpenHands attempt; OpenHands still retries itself."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    sites = 0
    for index, line in enumerate(lines):
        out.append(line)
        if line.strip() != "timeout=self.timeout,":
            continue
        sites += 1
        indent = line[: len(line) - len(line.lstrip())]
        follower = lines[index + 1] if index + 1 < len(lines) else ""
        if follower.strip() == "max_retries=0,":
            continue
        out.append(f"{indent}max_retries=0,\n")
    if sites != 2:
        raise SystemExit(f"expected 2 litellm timeout=self.timeout sites, found {sites}")
    return "".join(out)


def main() -> None:
    AGENT_STORE.write_text(
        patch_agent_store(AGENT_STORE.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    LLM_PY.write_text(
        patch_llm_transport(LLM_PY.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
