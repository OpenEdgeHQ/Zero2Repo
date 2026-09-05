# <img src="icon.svg" width="36" height="36" alt="" valign="middle"> Zero2Repo

Formerly CodingBench. Same exam. Clearer name.
[bench.zero2repo.ai](https://bench.zero2repo.ai/)

Zero2Repo evaluates coding agents on **repo-scale, from-scratch** tasks.

The agent receives a product spec and an empty workspace, implements the project
in a real shell environment, and is scored by **hidden, deterministic acceptance
tests** (binary reward: `1.0` / `0.0`). No LLM-as-judge.

This repository ships:

- **6 released cases** under `benchmark/cases/`, spanning Python, Go, C++,
  and TypeScript/JavaScript
- The **`cbrun`** harness (recommended)
- An optional **Harbor** adapter

---

## Why Zero2Repo

Most coding benchmarks either hand the agent an existing repository and ask for a
patch (SWE-bench, Terminal-Bench), or ask for a single function in an isolated
sandbox (HumanEval, MBPP). Neither measures the workflow that real users lean on
most: **give an agent a requirements document and let it build the whole project
from nothing.**

Zero2Repo targets exactly that gap. Every case asks the agent to:

1. **Read a full natural-language spec** and recover module boundaries, data
   flow, behavioral constraints and a public interface contract.
2. **Work multi-turn in a real CLI harness** (Codex, Claude Code, OpenCode,
   Cursor): plan, implement, self-test, debug, iterate.
3. **Deliver a working repository from an empty directory** — directory layout,
   dependencies, build configuration, the lot.

Scoring is outcome-based: a hidden acceptance suite checks public behavior
against the spec in a reproducible Docker environment. No partial credit for
code that "looks right", and no LLM in the loop deciding the score.

---

## What makes the data different

### Real repositories, not LLM-synthesized tasks

Each case is derived from a **real, actively maintained open-source project**
pinned at a fixed commit. The PRD is a reverse-engineered abstraction of what
that project actually does; the acceptance tests are grounded in the project's
real, runnable behavior; the environment is a real `install` / `build`
toolchain. Language models help read code, draft text and run commands during
authoring, but they never invent the task, the behavior or the ground truth.
Every requirement traces back to something that exists and runs.

This is why case difficulty tracks real engineering rather than a hand-shrunk
puzzle — and why the cases are hard to memorize: public specs are neutralized so
the agent cannot simply recall the upstream repository.

### Language-agnostic by construction

The authoring process makes no assumptions about language, build system or test
framework. This release covers C++, Go, Python, and TypeScript/JavaScript.
New ecosystems are a matter of adding seed repositories, not rewriting the
harness.

### Fully automated, so it scales

Cases are produced by an **automated, evidence-gated authoring process** rather
than hand-written one at a time. Every generated artifact must pass deterministic
checks against real code and real tests before release; anything that cannot be
verified stays in draft. Case count scales with compute, not with headcount.

### One source, three kinds of assets

The same authored case yields, from a single run:

- a **benchmark package** — public PRD + interface contract + hidden acceptance
  suite + reproducible environment (what this repository ships);
- **SFT trajectories** — step-wise development traces with real test feedback;
- **RL environments** — the same containerized task with a deterministic,
  verifiable reward.

Because all three come from the same real-world distribution, models can be
trained and evaluated on data that shares one origin instead of "train on one
distribution, test on another".

---

## Quick start

### Requirements

- Python 3.10+
- Docker (for full agent trials)
- An agent CLI API key (Codex / OpenCode / Claude Code / Cursor)

### Install

```bash
git clone https://github.com/OpenEdgeHQ/Zero2Repo.git
cd Zero2Repo

# vendor dependency used by cost reporting
git submodule update --init --recursive 2>/dev/null || true

cd benchmark
pip install -e .
```

### Configure an agent

```bash
cd benchmark/local_agents
cp codex.env.example codex.env          # set OPENAI_API_KEY / MODEL
# or: cp opencode.env.example opencode.env
# or: cp claude-code.env.example claude-code.env
# or: cp cursor.env.example cursor.env
```

### Smoke-test the container wiring

```bash
cd benchmark
./local_agents/run_smoke.sh codex
```

### Run one case

```bash
cd benchmark
set -a && source local_agents/codex.env && set +a
cbrun --case case027 --backend codex --model "$MODEL"
```

Results land under `benchmark/output/` (reward, logs, trajectories).

---

## What the agent sees

During the solve phase the container looks like:

```text
/environment/prd/Full_PRD.md
/environment/Interface_Contract.md
/environment/Hardware_Requirements.md   # when present
/app/                                   # empty workspace — implement here
```

Hidden acceptance tests are **not** present while the agent works. The agent
submits by writing an explicit submit file; after a valid submit the harness
copies `/app` into a fresh container, injects the hidden suite and runs the
judge. Ending the CLI session is not a submission.

Scoring is black-box: only the hidden suite decides the reward.

---

## Case layout

Each case under `benchmark/cases/<case_id>/` contains:

| Path | Role |
|------|------|
| `public/Full_PRD.md` | Product requirements (visible) |
| `public/Interface_Contract.md` | Public API / CLI contract (visible) |
| `public/Hardware_Requirements.md` | Optional hardware constraints (visible) |
| `source/manifest.json` | Runner metadata for the harness |
| `milestones/final/tests/` | Hidden acceptance tests |
| `milestones/final/test_manifest.json` | Test inventory / command template |
| `milestones/final/run_acceptance.sh` | Authoritative judge entrypoint (when present) |

List released cases:

```bash
ls benchmark/cases
```

---

## Harbor adapter (optional)

```bash
cd benchmark
pip install -e ".[harbor]"

# Build Harbor tasks for the released suite
zero2repo-harbor --all --force

# Example agent run (edit model/env in the YAML first)
harbor run --config configs/agents/codex.yaml
```

`coding-bench-harbor` remains an alias for the same CLI.

---

## Docs

| Doc | Contents |
|-----|----------|
| [`benchmark/README.md`](benchmark/README.md) | Harness details, Harbor mapping, offline judge |
| [`benchmark/cbrun/README.md`](benchmark/cbrun/README.md) | `cbrun` flags, images, limits |
| [`benchmark/local_agents/README.md`](benchmark/local_agents/README.md) | Agent env templates and smoke tests |

---

## License

See repository license terms. Bring your own model provider credentials; this
repo does not bundle API keys or third-party proxies.
