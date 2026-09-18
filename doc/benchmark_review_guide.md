# Zero2Repo benchmark review guide

This is the published review checklist for the 11 released cases. It replaces
older notes that talked about a golden deliverable tarball and a private
`/opt/cb-cache` host mount. Cases rebuild from `source/recipe.lock.json` plus
the shared `codingbench-base` toolchain image.

## 1. What a case is

Each `benchmark/cases/<id>/` has:

| Path | Visible to the agent? |
|---|---|
| `public/Full_PRD.md` | yes |
| `public/Interface_Contract.md` | yes |
| `public/Hardware_Requirements.md` (optional) | yes |
| `source/manifest.json` | no (runner + `sensitive_terms` + optional `judge_bans`) |
| `source/recipe.lock.json` | no |
| `source/denylist.json` | no (host + judge only; hashes in the `:agent` image) |
| `source/env/resources.json` (optional) | no |
| `milestones/final/` | no (hidden tests) |
| `controls/<name>/` | no (negative-control workspaces) |

### 1.1 Denylist is tracked

`source/denylist.json` is tracked with every case. Isolation keeps hidden
tests and the upstream name out of the solve container; the denylist adds
the second gate: the agent may not install or import the upstream product.
Without it, wrapping `pip install <upstream>` would score 1. Default
`--enforce-denylist` fails closed when the file is missing or empty;
`--no-enforce-denylist` records `denylist_enforced=false`.

### 1.2 Images

`:deliverable` is rebuilt from the lock + public `ubuntu:24.04` toolchain
Dockerfile. If `source/env/resources.json` is present, `recipe_image` fetches
HTTPS objects, checks size and SHA-256, and installs them at the declared
destination. Do not copy from `/opt/cb-cache` unless that file declared the
resource.

## 2. The 11 cases

| Id | Neutral product | Language | Notes for reviewers |
|---|---|---|---|
| case001 | Tomlparse | Python | Must not delegate `loads`/`load` to `tomllib`. Nesting: at least 64 levels succeed; past the interpreter limit is `RecursionError`. |
| case002 | python-envfile | Python | Public API names must not sit in `sensitive_terms`. |
| case003 | ymlcodec | TypeScript | Line clues accept `file:line:` / `file:line:col:` as well as `line N`. |
| case004 | Signtoken | Python | Signatures are checked with independent `hmac.new` / frozen vectors. Weak concat and always-accept live under `controls/`. |
| case005 | httpwire | Python | Pure protocol state machine. `runner.judge_bans` is `socket` + `subprocess`. |
| case006 | Optlyn | Python | File completion must register with real Bash. `pause` treats a stdio PTY as interactive. Result callbacks consume child return values. |
| case007 | Otpkit | Python | Runner / recipe only unless a later review adds oracles. |
| case008 | Hrefparse | C++ | Identifier-boundary leakage: `ada` must not match `adapter`. |
| case009 | Git Orbulk | Go | CoW dedup (F18) needs a CoW filesystem and often privilege. This round does **not** add `judge_profile=cow` or extra caps to every judge container. See `doc/case009_cow_probe.md`. |
| case010 | Lingora | Python | Model data comes from `source/env/resources.json`, not a private cache. |
| case011 | PathSel | Python | Runner / recipe only unless a later review adds oracles. |

Not in this round: case003 S01/S03/S04/S05 wording, case004 codec construction of `{}`.

## 3. Three judging principles

1. **Oracle independent of the candidate.** Prefer stdlib (`hmac`, `tomllib` as
   a reference only inside hidden tests), frozen vectors, or a process the
   product does not control. Do not ask the product to mark its own homework.
2. **Do not assert excluded wording or upstream shape.** Hidden tests may not
   require error class names, help text, or file layout that the contract
   left unpinned or explicitly excluded.
3. **Every oracle fix ships a red control.** Put a workspace under
   `cases/<id>/controls/<name>/` with `expect.json` (`reward: 0` or `1`) and
   `app/`. `python3 tools/run_controls.py --out …` must keep those red.

## 4. Runner hard rules (all cases)

- Unpinned agent CLIs fail formal runs (`CBRUN_ALLOW_UNPINNED_CLI=1` is the hatch).
- Judge-process import bans apply only when the importer is under `/app`.
- `import_ban` may name stdlib roots; image probes skip `sys.stdlib_module_names`.
- `runner.judge_bans` may declare `socket`, `subprocess`, `network`,
  `filesystem_outside_workspace`. Hits fail that test, not the whole harness.
- Leakage uses identifier boundaries. Do not turn the check off.
- `--out` must be a new directory. Trials pause the container, archive `/app`
  and `/logs/agent`, then write `summary.json` atomically. Reward is only 0 or 1
  with verified test counts.
- Image reuse is by input fingerprint; hidden tests cache by deliverable ID.

## 5. Reviewer whitelist (may be added without being “product leakage”)

- `source/denylist.json`
- `source/env/resources.json` and `fetch_resources.py`
- `controls/`
- `recipe.lock.json` install/build commands that match the manifest

## 6. How to rejudge (when a workspace exists)

```bash
python3 doc/rejudge.py --case case004 --workspace path/to/app --out /tmp/rj-new --expect-reward 0
python3 tools/run_controls.py --dry-run
```

Do not reuse an existing `--out`. This round’s automated gate is the unit
suite (`cd benchmark && python3 -m pytest tests -q -m "not slow"`), not a
full rejudge of current submissions.
