"""Codex CLI harness shim for zero2repo Harbor tasks.

Harbor's stock Codex agent can install Codex via nvm for every trial. zero2repo
task images already ship Node, so this shim prefers an image-baked Codex CLI,
uses a named Codex profile, and falls back to ``npm install -g @openai/codex``
only when needed.
"""

from __future__ import annotations

import json
import os
import shlex

from harbor.agents.installed.base import with_prompt_template
from harbor.agents.installed.codex import Codex
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class CodingBenchCodex(Codex):
    """Use image-baked or npm-global Codex CLI with ``codex --profile lb``."""

    def __init__(
        self,
        *args,
        codex_command: str | None = None,
        codex_profile: str | None = None,
        preserve_model_provider_prefix: bool = False,
        **kwargs,
    ) -> None:
        self.codex_command = codex_command or os.environ.get("CODEX_CLI_BIN", "codex")
        self.codex_profile = (
            codex_profile
            if codex_profile is not None
            else os.environ.get("CODEX_PROFILE", "")
        )
        self.preserve_model_provider_prefix = preserve_model_provider_prefix
        super().__init__(*args, **kwargs)

    def _codex_bin(self) -> str:
        return shlex.quote(self.codex_command)

    def _profile_arg(self) -> str:
        if not self.codex_profile:
            return ""
        return f"--profile {shlex.quote(self.codex_profile)} "

    def get_version_command(self) -> str | None:
        return f"{self._codex_bin()} {self._profile_arg()}--version"

    def _model_for_codex(self) -> str:
        if not self.model_name:
            raise ValueError("Model name is required")
        if self.preserve_model_provider_prefix:
            return self.model_name
        return self.model_name.split("/")[-1]

    async def install(self, environment: BaseEnvironment) -> None:
        version_spec = f"@{self._version}" if self._version else "@latest"
        codex_bin = self._codex_bin()

        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"if command -v {codex_bin} >/dev/null 2>&1; then "
                f"  {codex_bin} --version; exit 0; "
                "fi; "
                "if command -v codex >/dev/null 2>&1; then "
                "  codex --version; exit 0; "
                "fi; "
                "command -v npm >/dev/null 2>&1 || { "
                "echo 'Error: npm not found; rebuild the task image with Node.js' >&2; "
                "exit 1; "
                "}; "
                f"npm install -g @openai/codex{version_spec} && codex --version"
            ),
        )

        await self.exec_as_root(
            environment,
            command=(
                "set -euo pipefail; "
                "CODEX_PATH=\"$(command -v codex 2>/dev/null || true)\"; "
                "if [ -n \"$CODEX_PATH\" ]; then "
                "  ln -sf \"$CODEX_PATH\" /usr/local/bin/codex; "
                "fi"
            ),
        )

    def _build_codex_exec_command(self, instruction: str, cli_flags_arg: str) -> str:
        escaped_instruction = shlex.quote(instruction)
        if not self.model_name:
            raise ValueError("Model name is required")

        model = shlex.quote(self._model_for_codex())
        return (
            f"{self._codex_bin()} exec "
            f"{self._profile_arg()}"
            "--dangerously-bypass-approvals-and-sandbox "
            "--skip-git-repo-check "
            "--cd /app "
            f"--model {model} "
            "--json "
            "--enable unified_exec "
            f"{cli_flags_arg}"
            "-- "
            f"{escaped_instruction} "
            f"2>&1 </dev/null | stdbuf -oL tee "
            f"{EnvironmentPaths.agent_dir / self._OUTPUT_FILENAME}"
        )

    def _build_profile_config(self) -> str:
        if not self.model_name:
            raise ValueError("Model name is required")

        model = self._model_for_codex()
        return f"model = {json.dumps(model)}\n"

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        if not self.model_name:
            raise ValueError("Model name is required")

        cli_flags = self.build_cli_flags()
        cli_flags_arg = (cli_flags + " ") if cli_flags else ""

        auth_json_path = self._resolve_auth_json_path()
        remote_codex_home = self._REMOTE_CODEX_HOME.as_posix()
        remote_secrets_dir = self._REMOTE_CODEX_SECRETS_DIR.as_posix()
        remote_auth_path = (self._REMOTE_CODEX_SECRETS_DIR / "auth.json").as_posix()

        env: dict[str, str] = {
            "CODEX_HOME": remote_codex_home,
        }

        await self.exec_as_agent(
            environment,
            command=(
                f'mkdir -p "$CODEX_HOME" {shlex.quote(remote_secrets_dir)} '
                f"{shlex.quote(EnvironmentPaths.agent_dir.as_posix())}"
            ),
            env=env,
        )

        if auth_json_path:
            self.logger.debug("Codex auth: using auth.json from %s", auth_json_path)
            await environment.upload_file(auth_json_path, remote_auth_path)
            if environment.default_user is not None:
                await self.exec_as_root(
                    environment,
                    command=f"chown {environment.default_user} {remote_auth_path}",
                )
            setup_command = (
                f'ln -sf {shlex.quote(remote_auth_path)} "$CODEX_HOME/auth.json"\n'
            )
        else:
            self.logger.debug("Codex auth: using OPENAI_API_KEY")
            env["OPENAI_API_KEY"] = self._get_env("OPENAI_API_KEY") or ""
            setup_command = (
                f"cat >{shlex.quote(remote_auth_path)} <<EOF\n"
                '{\n  "OPENAI_API_KEY": "${OPENAI_API_KEY}"\n}\nEOF\n'
                f"ln -sf {shlex.quote(remote_auth_path)} "
                '"$CODEX_HOME/auth.json"\n'
            )

        if openai_base_url := self._get_env("OPENAI_BASE_URL"):
            env["OPENAI_BASE_URL"] = openai_base_url
            setup_command += (
                '\ncat >>"$CODEX_HOME/config.toml" <<TOML\n'
                'openai_base_url = "${OPENAI_BASE_URL}"\n'
                "TOML\n"
            )

        if self.codex_profile:
            profile_file = shlex.quote(f"{remote_codex_home}/{self.codex_profile}.config.toml")
            profile_config = shlex.quote(self._build_profile_config())
            setup_command += (
                f"\nprintf '%s' {profile_config} > {profile_file}\n"
            )

        skills_command = self._build_register_skills_command()
        if skills_command:
            setup_command += f"\n{skills_command}"

        mcp_command = self._build_register_mcp_servers_command()
        if mcp_command:
            setup_command += f"\n{mcp_command}"

        if setup_command.strip():
            await self.exec_as_agent(environment, command=setup_command, env=env)

        try:
            await self.exec_as_agent(
                environment,
                command=self._build_codex_exec_command(instruction, cli_flags_arg),
                env=env,
            )
        finally:
            try:
                await self.exec_as_agent(
                    environment,
                    command=(
                        f"mkdir -p {EnvironmentPaths.agent_dir.as_posix()}\n"
                        'if [ -d "$CODEX_HOME/sessions" ]; then\n'
                        f"  rm -rf "
                        f"{(EnvironmentPaths.agent_dir / 'sessions').as_posix()}\n"
                        f'  cp -R "$CODEX_HOME/sessions" '
                        f"{(EnvironmentPaths.agent_dir / 'sessions').as_posix()}\n"
                        "fi"
                    ),
                    env=env,
                )
            except Exception:
                pass
            try:
                await self.exec_as_agent(
                    environment,
                    command=f'rm -rf {shlex.quote(remote_secrets_dir)} "$CODEX_HOME"',
                    env=env,
                )
            except Exception:
                pass
