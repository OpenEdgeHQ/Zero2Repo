"""Claude Code harness shim for zero2repo Harbor tasks.

On Debian-based task images we prefer ``npm install -g`` (Node is already in the
image) instead of downloading ``claude.ai/install.sh`` on every trial.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from harbor.agents.installed.base import with_prompt_template
from harbor.agents.installed.claude_code import ClaudeCode
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


def _claude_oauth_access_token_from_credentials(credentials_path: Path) -> str | None:
    """Read Max OAuth access token from Claude Code credentials (host-side)."""
    if not credentials_path.is_file():
        return None
    try:
        data = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    oauth = data.get("claudeAiOauth")
    if not isinstance(oauth, dict):
        return None
    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token.strip():
        return None
    return token.strip()


class CodingBenchClaudeCode(ClaudeCode):
    """Use image-baked or npm-global Claude Code when available."""

    _PATH_PREFIX = 'export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"; '

    def get_version_command(self) -> str | None:
        return f"{self._PATH_PREFIX} claude --version"

    async def install(self, environment: BaseEnvironment) -> None:
        version_suffix = f"@{self._version}" if self._version else ""
        npm_pkg = f"@anthropic-ai/claude-code{version_suffix}"
        install_sh_flag = f" {self._version}" if self._version else ""

        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                + self._PATH_PREFIX
                + "if command -v claude >/dev/null 2>&1; then "
                "  claude --version; exit 0; fi; "
                "if command -v npm >/dev/null 2>&1; then "
                f"  npm install -g {npm_pkg}; "
                + self._PATH_PREFIX
                + "  claude --version; exit 0; fi; "
                "if command -v apk >/dev/null 2>&1; then "
                f"  apk add --no-cache curl bash nodejs npm && npm install -g {npm_pkg}; "
                + self._PATH_PREFIX
                + "  claude --version; exit 0; fi; "
                "command -v curl >/dev/null 2>&1 || { "
                "echo 'Error: curl required to install Claude Code' >&2; exit 1; }; "
                f"curl -fsSL https://claude.ai/install.sh | bash -s --{install_sh_flag}; "
                + self._PATH_PREFIX
                + "claude --version"
            ),
        )

    async def _seed_host_claude_credentials(self, environment: BaseEnvironment) -> None:
        """Copy bind-mounted Claude config into Harbor's CLAUDE_CONFIG_DIR before run."""
        await self.exec_as_agent(
            environment,
            command=(
                self._PATH_PREFIX
                + "mkdir -p /logs/agent/sessions && "
                + "if [ -d /root/.claude ]; then "
                "  cp -a /root/.claude/. /logs/agent/sessions/ 2>/dev/null || true; "
                "fi && "
                + "if [ -f /root/.claude.json ] && [ ! -f /logs/agent/sessions/.claude.json ]; then "
                "  cp /root/.claude.json /logs/agent/sessions/.claude.json; "
                "fi"
            ),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        await self._seed_host_claude_credentials(environment)
        use_api_key = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        saved: dict[str, str | None] = {}
        oauth_saved: str | None = None
        oauth_injected = False
        if not use_api_key:
            # Host ANTHROPIC_* vars (e.g. a third-party gateway) would override Max
            # OAuth inside the container; strip them so subscription OAuth is used.
            saved = {
                k: os.environ.pop(k, None)
                for k in (
                    "ANTHROPIC_API_KEY",
                    "ANTHROPIC_BASE_URL",
                    "ANTHROPIC_AUTH_TOKEN",
                )
            }
            oauth_saved = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
            if not (oauth_saved and oauth_saved.strip()):
                token = _claude_oauth_access_token_from_credentials(
                    Path.home() / ".claude" / ".credentials.json"
                )
                if token:
                    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
                    oauth_injected = True
        try:
            await super().run(instruction, environment, context)
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value
            if oauth_injected:
                if oauth_saved is None:
                    os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
                else:
                    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_saved
