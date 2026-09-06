# cbrun — zero2repo Solver Benchmark Runner

`cbrun` is a Harbor-independent benchmark runner for [zero2repo bench](https://bench.zero2repo.ai/)
(formerly CodingBench). It evaluates an autonomous coding agent by giving it
only the public task specification and letting it build the project from
scratch, then scoring the result against hidden acceptance tests.

## Task model (solver-only)

The agent's job is to **write the implementation**. The test code is a hidden
benchmark asset, never an agent output.

* **Input** the agent sees: the PRD (`/environment/prd/Full_PRD.md`) and the
  Interface Contract (`/environment/Interface_Contract.md`), both also embedded
  in the instruction prompt, plus the case `build_command` (when non-empty)
  as the Build contract. The agent's workspace `/app` starts empty.
* **Output** the agent produces: the implementation in `/app`. When the case
  has a `build_command`, leave the outputs that command would produce; the
  judge does not rebuild.
* **Scoring**: after a valid submit file is present, the runner copies only
  `/app` into a fresh judge container and injects the hidden suite. The judge
  does **not** execute `install_command` or `build_command`. Reward is 1
  only after the suite is collected and executed and every test passes. CLI
  exit 0 alone is not a submit and not a pass.

The guiding invariant is *information completeness*: the provided environment
(empty `/app` + PRD + Interface Contract + the declared `build_command` when
present) must be theoretically sufficient for an ideal agent to pass the hidden
tests. The runner must show `build_command` to the agent; it is public text and
must not contain recipe-only flags that only the original repository understands.
If that command still cannot imply a path the hidden harness hard-codes, that is
a **case spec defect** — fix the case, never patch a per-case path into the
runner.

## Fairness: visible checks vs hidden gates

* **Visible / dev checks**: the agent may write and run its own tests and any
  public sample checks as many times as it wants and read their full output. A
  real develop → test → debug loop is expected.
* **Hidden gates**: the hidden acceptance tests are *physically absent* from the
  solve container. cbrun derives a per-case `:agent` image from the published
  `:deliverable` image and removes `/tests/final` in a new image layer (the
  tests are extracted to a host-side cache first). They are re-injected only for
  the judge phase, and judge output is not fed back to the agent.

## Free development, time-limited

There is **no** limit on steps, turns, edits or cost. The only hard ceilings are
wall-clock budgets:

* `max_agent_timeout_sec` — solve phase. Final-stage cases use a uniform **2h**
  (`7200s`).
* `max_test_timeout_sec` — judge phase. Default **10min** (`600s`), per-case
  overridable.
* `--timeout-multiplier` scales both wall clocks (mirrors Terminal-Bench's
  `global_timeout_multiplier`).

A conservative stall watchdog stops a wedged CLI when both stdout and `/app`
stay quiet, without treating a long compile or a long model turn as a hang.

## Termination and submit

The agent submits by writing `/logs/agent/submit` with the single line
`CODINGBENCH_SUBMIT`. Ending the CLI session is **not** a submission. The
isolated judge runs only after that file is valid **and** the denylist scan
is clean. Missing submit or an unfixed denylist hit scores `reward=0` and
does not run hidden tests.

The solve terminal status is recorded as one of:

* `completed` — valid submit file and the CLI exited 0.
* `timeout` — the wall clock was hit.
* `error` — stall-killed, a non-zero CLI exit, setup failure, or no submit.

## Built-in backends

Four backends ship as built-in **AgentSpec** records:

| Backend | CLI | Notes |
|---------|-----|-------|
| `codex` | `@openai/codex` | Writes `~/.codex/auth.json` + `config.toml` from `OPENAI_*` env before solve. Default `model_prefix=keep` for OpenAI-compatible gateways. |
| `opencode` | `opencode-ai` | Forwards provider env based on `provider/model` id. |
| `claude-code` | `@anthropic-ai/claude-code` | Runs as non-root user `cbagent` with `bypassPermissions` (Claude Code rejects root). Judge still runs as root. |
| `cursor` | Cursor CLI (`cursor-agent`) | Forwards `CURSOR_API_KEY`. Installed from the official Cursor install script into the `:agent` image. |

Auth/provider env is selected centrally and forwarded into the container; only
**present** keys are injected (key names are recorded in results, never values).
CLI versions default to latest but should be pinned for reproducibility via
`CBRUN_CODEX_VERSION` / `CBRUN_OPENCODE_VERSION` / `CBRUN_CLAUDE_VERSION` /
`CBRUN_CURSOR_VERSION`.

### Codex + OpenAI-compatible gateway

Point standard env vars at any OpenAI-compatible endpoint:

```bash
export OPENAI_API_KEY=your-key
export OPENAI_BASE_URL=https://your-gateway.example/v1
cbrun --case case002 --backend codex --model openai/gpt-4o-mini
```

cbrun writes `openai_base_url` into `~/.codex/config.toml` during setup. Use
`model_prefix: strip` in a custom spec if your Codex install expects leaf model
names only.

### Claude Code non-root contract

* Agent deliverables **must** land in `/app` (hard contract; not overridable).
* Solve runs as `cbagent`; judge reads `/app` as root.
* Agent HOME (`/home/cbagent`) holds CLI caches only; it is not scored.

## Bring your own agent

Pass a local **AgentSpec** file instead of `--backend`:

```bash
cbrun --case case002 --agent-spec ./my-agent.json --model my/model
```

Example `my-agent.json`:

```json
{
  "name": "my-agent",
  "env_passthrough": ["MY_API_KEY"],
  "setup_script": "mkdir -p \"$HOME/.myagent\" && echo ok > \"$HOME/.myagent/ready\"",
  "command": "my-cli --model {model_quoted} --workdir {workdir_quoted} \"$(cat {instruction_quoted})\" 2>&1 | tee {log_quoted}",
  "run_as": "root",
  "model_prefix": "keep",
  "setup_timeout_sec": 120
}
```

### AgentSpec fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Identifier recorded in results. |
| `command` | yes | Shell command template for the solve phase. Workdir is always `/app`. |
| `env_passthrough` | no | Env var names to forward when present on the host. |
| `setup_script` | no | Shell run before solve (auth files, config). Do **not** use `set -x`. |
| `install_script` | no | Optional CLI install when not baked into the `:agent` image. |
| `run_as` | no | `root` (default) or `nonroot` (`cbagent` via `docker exec -u`). |
| `model_prefix` | no | `keep` (default) or `strip` the `provider/` prefix from `--model`. |
| `home` | no | Writable HOME/config directory (defaults by `run_as`). |
| `setup_timeout_sec` | no | Setup phase timeout (default 120s). |
| `python_hook` | no | Built-in hooks only (`cbrun.agent_hooks:*`); custom specs should use declarative fields. |

Placeholders in `command` / `setup_script`: `{model}`, `{model_quoted}`,
`{instruction_quoted}`, `{log_quoted}`, `{workdir}` (`/app`), `{workdir_quoted}`,
`{home}`.

### Security boundaries

* AgentSpec files are **local trusted configuration**. They can execute shell
  (`setup_script`, `install_script`, `command`). Do not run specs from untrusted
  sources.
* Specs are loaded from `--agent-spec PATH` only; cbrun does **not** fetch and
  execute remote spec URLs.
* The solve container never mounts the Docker socket.
* Hidden tests are absent during solve; logs must not contain secret values.

### Network policy and upstream denylist

* During **solve**, GitHub hostnames are blocked via container `/etc/hosts`
  (`--add-host …:0.0.0.0`). Model API calls and PyPI/npm remain reachable.
  Disable with `--no-block-github`.
* Each case may ship `source/denylist.json` listing upstream package/module
  names for the target product. pip/conda install shims in the `:agent` image
  reject those packages inline (warning only, no scoring).
* After a valid submit, cbrun statically scans `/app` for real
  import/require/use of banned tokens (docstrings and string literals do not
  count). If found, the agent gets one fix retry (`--denylist-fix-retries`,
  default 1) and must write the submit file again; if violations remain, the
  trial scores `reward=0` without judging. Disable with
  `--no-enforce-denylist`.

## Step mode (architecture only)

cbrun currently treats each case as a single final acceptance suite. It
normalizes that shape into one step and exposes `steps.discover_steps` so
multi-step support can be added later. Multi-step development orchestration is
**not** implemented yet.

## Usage

```bash
# Rebuild :deliverable from recipe.lock + shared base (no model needed)
cbrun --case case001 --build-images

# One case, one backend
cbrun --case case001 --backend codex --model openai/gpt-5.5

# Several backends, reward matrix
cbrun --case case002 \
  --backend codex --backend opencode --backend claude-code --backend cursor \
  --model openai/gpt-5.5

# Custom agent spec
cbrun --case case002 --agent-spec ./agents/echo.json --model dummy/model

# Every case under the cases root
cbrun --all --backend codex --model openai/gpt-5.5
```

Outputs go to `--out` (default `benchmark/output/cbrun/`): per-trial `agent.log`,
`agent_setup.log` (when setup runs), `judge.log`, `final_report.json`,
`final_tests.log` (when the judge ran), plus an aggregate `summary.json` and a
printed reward matrix.

Each trial records reproducibility metadata: agent spec name/hash, resolved model,
`run_as`, `model_prefix`, setup status, forwarded env **key** list, and CLI
version when available.

## Pipeline (per trial)

1. If `:deliverable` is missing, rebuild it from the shared `codingbench-base/*`
   image plus `source/recipe.lock.json` (install toolchain, copy public specs and
   hidden tests, leave `/app` empty). Then derive/reuse the `:agent` image
   (extract hidden tests to host cache, install pinned CLIs, create `cbagent`
   user, `rm -rf /tests/final`). Idempotent.
2. Start a GT-free container (`--gpus` only when the case needs it, host network
   for model APIs, **never** the Docker socket).
3. Inject the instruction; **setup** agent auth/config; **chown** `/app` (+ HOME
   for non-root agents); run the agent in `/app` under the wall clock + stall
   watchdog, tee'ing output to `agent.log`.
4. After the CLI stops, require a valid `/logs/agent/submit`; otherwise mark
   the attempt failed and skip hidden tests. Ensure no agent process lingers.
5. When submit is valid and denylist is clean: re-inject hidden tests + a
   synthesized `/task.toml`, run the shared `final_judge.py` as root, parse
   the binary reward (distinguishing `judge_error`).

## Reused components

* `coding_bench_harbor.adapter`: case discovery, `CaseAssets`, the from-scratch
  `_INSTRUCTION_PREAMBLE`, `build_contract_notes`, runner normalization.
* `coding_bench_harbor.final_judge`: the scoring engine (single source of truth,
  shared with the Harbor adapter).

## Tests

* Fast unit tests (no Docker): `tests/test_cbrun_agents.py`,
  `tests/test_cbrun_agent_spec.py`, `tests/test_cbrun_core.py`,
  `tests/test_cbrun_wiring.py`.
* Docker-gated integration (`@pytest.mark.slow`,
  `tests/test_cbrun_docker.py`): oracle sanity (GT → reward 1), fairness
  invariant (`:agent` image has no `/tests/final`, CLIs present, `cbagent`
  user exists, Codex setup writes config). They skip automatically when Docker
  or the required images are unavailable.
* **Local agent smoke** (your credentials, no source edits):
  [`../local_agents/README.md`](../local_agents/README.md) — copy `*.env.example`,
  run `./local_agents/run_smoke.sh`.
