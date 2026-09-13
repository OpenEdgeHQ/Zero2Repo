# Running and maintaining a reliable case pipeline

Pipeline completion and candidate correctness are separate outcomes. A submitted
implementation that fails tests has `pipeline_status="evaluated"` and reward 0.
The solver's actual termination remains in `terminal_status` and `agent_exit_code`.
A missing submit has `pipeline_status="not_submitted"`; a policy rejection has
`"rejected"`; setup, environment, judge or artifact failures have `"error"`.

## Check a release without a model

From `benchmark/`, after installing the runner:

```bash
cbrun --all --preflight
CBRUN_CODEX_VERSION=0.153.4 cbrun --all --preflight --check-images
cbrun --all --agent-spec configs/agents/submission-smoke.json --model offline/no-model
```

The first command validates every discovered case's public gate, manifest,
recipe alignment, test paths, shell commands and staging. The second builds
content-versioned images and verifies their toolchains, exact public documents,
empty solve workspaces and judge profiles. The third submits an empty workspace
to each actual hidden suite: every case must produce a recorded failed evaluation
with reward 0. These are offline controls, not model benchmark scores.

For repeated runs, `--out` must name a new directory. If omitted, a unique UTC
timestamp and suffix are used. Existing results are never overwritten.

## Monitor results and failure paths

- `summary.json` is written atomically after each trial. `complete=false` means
  the matrix is still running or was interrupted. Each active trial also writes
  `trial.json` as it changes phase.
- A normal batch exits 0 only when every selected trial was evaluated and its
  artifacts were retained, irrespective of reward. It exits 1 for incomplete or
  infrastructure-failed evaluations, 2 for invalid CLI/output selection, and 130
  when interrupted. Inspect solver termination separately: a submitted candidate
  can still be evaluated after a solver crash or timeout.
- `failed_phase`, `error`, `judge_error` and `artifact_errors` identify failures.
  `judge_result.json` records normalized judge termination, including when the
  judge could not create its usual report.
- `/app` and available agent logs are archived before container teardown on both
  submitted and unsubmitted attempts. Setup and solver errors are not replaced
  by empty candidate evaluations. Inspect `workspace/`, `container_logs/`,
  `agent*.log`, `image_build.log`, and the judge artifacts. Candidate processes
  are frozen before copying so detached jobs cannot mutate a snapshot. Test
  output is streamed to disk and retained even if the judge times out.
- Start/end times, limits, repository commit/status, source hashes, image IDs,
  selected platform, actual CLI version and input/test hashes accompany trials.
  Model settings record an explicit reasoning choice or `cli-default`; that
  label does not claim to know a model's implicit default.

Case or runner changes during a trial are rejected before grading. Run against a
stable checkout; use a separate worktree for edits while trials are active.

The shared shell uses `pipefail`, so `tee` cannot hide a solver's exit code.
Server-side timeouts stop container processes; the fallback timeout handler
accepts both byte and text output. A process-group watchdog works for custom
AgentSpecs without requiring a specific command or log filename.

## Image and test-cache identity

Build tags include content fingerprints. Base identities include the public
parent image, platform and Dockerfile. Environment identities include the base,
install command and environment assets. Deliverables include current case data.
Agent identities include the deliverable, CLI installer, platform and shim assets.
Changed inputs select new tags; legacy unverified tags are not silently reused.

Tests are cached under the immutable deliverable ID, with checksums and a lock
for extraction. Corrupt caches are re-extracted. Their checksums are verified
again before judging. Trials start containers by a frozen runnable image ID;
the selected platform manifest identity is also retained for Docker engines that
distinguish multi-platform indexes from their platform manifests.

`--force-image` rebuilds case images even when the inputs match. It does not mean
refreshing every unpinned upstream package automatically. Pin CLI versions with
`CBRUN_CODEX_VERSION`, `CBRUN_OPENCODE_VERSION`, etc. An `@latest` CLI request emits
a warning; its actual installed version is recorded at runtime.

## Platforms and special environments

The bundled base uses Linux x86_64 binaries. `linux/amd64` is the default on Intel
and Apple Silicon hosts; Docker provides the corresponding execution environment.
`--platform` / `CBRUN_PLATFORM` selects and verifies the platform consistently.
A custom ARM base and compatible install recipes are required for `linux/arm64`.
Changing only the Ubuntu tag does not convert x86_64 toolchains to ARM.

Case009 declares `judge_profile="cow"`. The runner initializes a private btrfs
loopback filesystem in a network-isolated judge container, checks real `FICLONE`,
removes its device nodes and drops `SYS_ADMIN`/`MKNOD` from test processes. The
initialization needs Docker to allow those explicitly scoped capabilities and
loop-device cgroup access. No host folders, physical block devices or Docker
socket are mounted. This readiness check runs before a live solver is started.
Unsupported hosts fail as an environment error. The solve container retains
the standard profile.

Case010 installs seven model-data archives from a pinned public data revision.
`source/env/resources.json` records URLs, sizes, SHA-256 values and source/license
metadata; the installer verifies them before safe extraction. A private local
`lingora-models` cache is no longer required. Data notices are preserved in the
image. This is a reproducible public recipe, not a claim of byte equality with
an unavailable internal historical bundle.

## Adding a case

1. Add a directory containing `source/manifest.json`, a matching
   `source/recipe.lock.json`, the public PRD/Contract, and the final test manifest
   and files. Discovery is automatic; no case ID list in the runner or CI needs
   updating.
2. Keep install/build commands aligned in both manifests. Install declares
   environment dependencies; the agent performs the candidate build and leaves
   outputs under `/app`. The fresh judge intentionally does not rebuild it.
3. Add short `runner.environment_checks` for toolchain and data readiness. Each
   entry has `name`, `command`, optional `phase` (`solve`, `judge`, `both`) and
   `timeout_sec` (at most 300). They run against an empty candidate workspace.
   Candidate APIs belong in post-build probes, not these environment checks.
4. List genuine source identities in `sensitive_terms`, excluding required public
   names. Matching uses identifier boundaries and preserves qualified-name/URL
   punctuation. Both real identities and accidental public-name conflicts are
   covered by the release preflight.
5. Supply an accurate `source/denylist.json` when anti-reuse enforcement is
   required. Its state is explicit (`unavailable`, `disabled`, `pending`,
   `passed`, or `failed`); missing policy is never represented as a clean scan.
   `--preflight --require-denylist` makes that release requirement mandatory.
6. Run all three checks above, then validate a known usable candidate against the
   real suite. The empty-submission control proves rejection and result wiring;
   it does not prove full correctness or that an ideal implementation can pass.

CI runs the unit/release checks on Linux and macOS, and Docker lifecycle,
environment and real-judge controls on Linux without model credentials. The
case-specific quality of test assertions remains a separate review concern.

## Codex gateways and reasoning settings

`OPENAI_BASE_URL` selects a named Responses provider using environment-key
authentication. The config is written afresh inside the trial's Codex home;
repeated setup remains valid TOML. Credentials are written as JSON with mode
0600 and are excluded from reported configuration values.

Set `CBRUN_CODEX_REASONING_EFFORT` to an effort supported by the selected model
and CLI to make that choice explicit. If absent, the CLI decides and the record
says `cli-default`. Official references: [custom providers](https://learn.chatgpt.com/docs/config-file/config-advanced#custom-model-providers)
and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
