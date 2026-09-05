# Local agent configuration (cbrun smoke tests)

This directory holds **local-only** credentials and model choices for testing the
built-in cbrun backends (`codex`, `opencode`, `claude-code`, `cursor`) without
modifying benchmark source code.

## Quick start

1. Copy the example env files and fill in your credentials:

```bash
cd benchmark/local_agents
cp codex.env.example codex.env
cp opencode.env.example opencode.env
cp claude-code.env.example claude-code.env
cp cursor.env.example cursor.env
# edit each *.env — keys stay on your machine (gitignored)
```

2. Ensure a case `:deliverable` image exists (CPU-only smoke default is `case027`):

```bash
docker images codingbench-benchmark/case027:deliverable
# If missing, pull or build the case :deliverable image first.
```

3. Run smoke tests (container-only; does **not** run a full 2h solve):

```bash
cd benchmark
./local_agents/run_smoke.sh              # all backends
./local_agents/run_smoke.sh codex        # one backend
./local_agents/run_smoke.sh claude-code
```

Or directly:

```bash
cd benchmark
python local_agents/smoke.py --backend codex
python local_agents/smoke.py --all
```

## What smoke checks

For each backend the script verifies the **same container path cbrun uses**:

1. Derive/reuse the `:agent` image for `case027`.
2. Run agent **setup** (Codex writes `auth.json` / `config.toml`; Claude runs as `cbagent`).
3. Ask the model to create `/app/smoke_probe.txt` with content `AGENT_OK`.
4. Confirm the probe file exists and the agent CLI produced output.
5. Confirm **judge harness starts** (reward may be 0 — empty `/app` is expected to fail tests).
6. Confirm logs do not contain literal secret values from your env files.

This is a **connectivity / wiring** check, not a full benchmark trial. For a real
case run:

```bash
cd benchmark
set -a && source local_agents/codex.env && set +a
cbrun --case case027 --backend codex --model "$MODEL"
```

Repeat with the other env files and `--backend opencode` / `--backend claude-code`
/ `--backend cursor`.

## Env file format

Each `*.env` is a shell snippet (`export KEY=value`). Required keys:

| File | Typical exports |
|------|-----------------|
| `codex.env` | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `MODEL` |
| `opencode.env` | `ANTHROPIC_API_KEY`, optional `ANTHROPIC_BASE_URL`, `MODEL` |
| `claude-code.env` | `CLAUDE_CODE_OAUTH_TOKEN` **or** `ANTHROPIC_API_KEY`, `MODEL` |
| `cursor.env` | `CURSOR_API_KEY`, `MODEL` |

`MODEL` must match the backend:

- **codex / opencode**: `provider/model`, e.g. `openai/gpt-4o-mini`
- **claude-code**: leaf or full id per your CLI, e.g. `claude-sonnet-4`
- **cursor**: the model id your Cursor CLI expects

## Optional OpenCode config

If you use a custom `opencode.json` (providers, models), place it at
`local_agents/opencode.json` (gitignored). The smoke script copies it to
`/root/.config/opencode/opencode.json` inside the container before solve.
cbrun itself still uses env passthrough only; this copy is a **local smoke helper**.

## Security

- Files here can contain API keys. They are listed in `benchmark/.gitignore`.
- Do not commit `*.env` or `opencode.json`.
- Smoke logs are written under `local_agents/output/` (also gitignored).
