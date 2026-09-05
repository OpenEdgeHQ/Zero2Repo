"""OpenCode harness shim for zero2repo Harbor tasks.

Harbor's stock OpenCode agent installs via nvm + GitHub on every trial, which is
fragile in Docker (TLS/timeouts) and redundant when the task image already ships
Node and a global ``opencode`` binary (see ``benchmark/template/environment/Dockerfile``).
"""

from __future__ import annotations

import os
import shlex

from harbor.agents.installed.opencode import OpenCode
from harbor.agents.installed.base import NonZeroAgentExitCodeError, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class CodingBenchOpenCode(OpenCode):
    """Use image-baked or npm-global OpenCode; never require nvm at runtime."""

    def get_version_command(self) -> str | None:
        return "opencode --version"

    async def install(self, environment: BaseEnvironment) -> None:
        version_spec = f"@{self._version}" if self._version else "@latest"
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "if command -v opencode >/dev/null 2>&1; then "
                "  opencode --version; "
                "  exit 0; "
                "fi; "
                "command -v npm >/dev/null 2>&1 || { "
                "echo 'Error: npm not found; rebuild the task image with Node.js' >&2; "
                "exit 1; "
                "}; "
                f"npm i -g opencode-ai{version_spec} && opencode --version"
            ),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        # Reuse parent setup (skills, opencode.json) but invoke the global CLI directly.
        self._instruction = instruction
        escaped_instruction = shlex.quote(instruction)

        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        provider, _ = self.model_name.split("/", 1)
        env: dict[str, str] = {}
        keys: list[str] = []

        if provider == "amazon-bedrock":
            keys.extend(["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"])
        elif provider == "anthropic":
            keys.append("ANTHROPIC_API_KEY")
        elif provider == "azure":
            keys.extend(["AZURE_RESOURCE_NAME", "AZURE_API_KEY"])
        elif provider == "deepseek":
            keys.append("DEEPSEEK_API_KEY")
        elif provider == "github-copilot":
            keys.append("GITHUB_TOKEN")
        elif provider == "google":
            keys.extend(
                [
                    "GEMINI_API_KEY",
                    "GOOGLE_GENERATIVE_AI_API_KEY",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                    "GOOGLE_CLOUD_PROJECT",
                    "GOOGLE_CLOUD_LOCATION",
                    "GOOGLE_GENAI_USE_VERTEXAI",
                    "GOOGLE_API_KEY",
                ]
            )
        elif provider == "groq":
            keys.append("GROQ_API_KEY")
        elif provider == "huggingface":
            keys.append("HF_TOKEN")
        elif provider == "llama":
            keys.append("LLAMA_API_KEY")
        elif provider == "mistral":
            keys.append("MISTRAL_API_KEY")
        elif provider == "openai":
            keys.extend(["OPENAI_API_KEY", "OPENAI_BASE_URL"])
        elif provider == "opencode":
            keys.append("OPENCODE_API_KEY")
        elif provider == "xai":
            keys.append("XAI_API_KEY")
        elif provider == "openrouter":
            keys.append("OPENROUTER_API_KEY")

        for key in keys:
            if key in os.environ:
                env[key] = os.environ[key]

        env["OPENCODE_FAKE_VCS"] = "git"

        skills_command = self._build_register_skills_command()
        if skills_command:
            await self.exec_as_agent(environment, command=skills_command, env=env)

        mcp_command = self._build_register_config_command()
        if mcp_command:
            await self.exec_as_agent(environment, command=mcp_command, env=env)

        cli_flags = self.build_cli_flags()
        cli_flags_arg = (cli_flags + " ") if cli_flags else ""

        await self.exec_as_agent(
            environment,
            command=(
                f"opencode --model={self.model_name} run --format=json {cli_flags_arg}"
                f"--thinking --dangerously-skip-permissions -- {escaped_instruction} "
                "2>&1 </dev/null | stdbuf -oL tee /logs/agent/opencode.txt"
            ),
            env=env,
        )

        if messages := self._error_messages():
            raise NonZeroAgentExitCodeError(
                "OpenCode emitted error event(s): " + "; ".join(messages[:3])
            )
