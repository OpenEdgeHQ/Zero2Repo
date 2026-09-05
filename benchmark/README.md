# zero2repo — Benchmark Harness

Standalone evaluation layer for [zero2repo bench](https://bench.zero2repo.ai/)
cases (formerly CodingBench).

- **Input:** public PRD + Interface Contract (+ optional Hardware Requirements)
- **Workspace:** empty `/app` for the agent to implement from scratch
- **Judge:** hidden acceptance suite; binary reward `1.0` / `0.0`

## Runners

| Runner | When to use |
|--------|-------------|
| **`cbrun`** | Recommended standalone runner. See [`cbrun/README.md`](cbrun/README.md). |
| **Harbor adapter** | Optional path on [Harbor](https://github.com/laude-institute/harbor). |

Cases are discovered from `cases/<case_id>/source/manifest.json`.
`zero2repo-harbor --all` builds every case under the cases root that has a
manifest. `coding-bench-harbor` is an alias.

## Install

```bash
cd benchmark
pip install -e .
# Optional:
pip install -e ".[harbor]"
```

## cbrun (recommended)

```bash
cd local_agents
cp codex.env.example codex.env   # fill API key + MODEL
cd ..
./local_agents/run_smoke.sh codex

set -a && source local_agents/codex.env && set +a
cbrun --case case001 --backend codex --model "$MODEL"
```

Supported backends: `codex`, `opencode`, `claude-code`, `cursor`.

## Harbor adapter

```bash
zero2repo-harbor --case-id case001 --force
# or
zero2repo-harbor --all --force
```

Tasks are written to `benchmark/output/<case_id>/`.

Agent configs (edit model / env first):

```bash
export OPENAI_API_KEY=...
harbor run --config configs/agents/codex.yaml
# harbor run --config configs/agents/opencode.yaml
# harbor run --config configs/agents/claude-code.yaml
```

The adapter refuses to build if the public spec still contains blacklisted terms
from `source/manifest.json` (`sensitive_terms`). Pass `--allow-leakage` to
downgrade that to a warning.

## Case → Harbor task mapping

| Case asset | Harbor task path | Visible to agent? |
|------------|------------------|-------------------|
| `public/Full_PRD.md` | `instruction.md` + `environment/prd/Full_PRD.md` | yes |
| `public/Interface_Contract.md` | `instruction.md` + `environment/Interface_Contract.md` | yes |
| `public/Hardware_Requirements.md` | `environment/Hardware_Requirements.md` | yes |
| `milestones/final/` acceptance | `tests/final/` | no (judge only) |

After the agent exits, `final_judge.py` runs `run_acceptance.sh` when present,
otherwise the command from `test_manifest.json`, and writes
`reward.{txt,json}` + `final_report.json`.

## Offline judge (no Docker)

```bash
zero2repo-harbor --case-id case001 --force
# Point FINAL_WORKSPACE at a workspace mirroring /app, then invoke final_judge
# as documented in coding_bench_harbor/final_judge.py.
```

## More

- [`cbrun/README.md`](cbrun/README.md) — images, limits, artifacts
- [`local_agents/README.md`](local_agents/README.md) — env templates & smoke tests
- Root [`README.md`](../README.md) — product overview & quick start
