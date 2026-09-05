#!/usr/bin/env python3
"""Local smoke test for cbrun built-in agents (no benchmark source edits).

Uses the same :agent image, setup/solve lifecycle, and judge wiring as cbrun,
but with a minimal instruction and short timeout. Loads credentials from
``local_agents/<backend>.env`` (gitignored on your machine).

Example::

    cd benchmark
    python local_agents/smoke.py --backend codex
    python local_agents/smoke.py --all
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.agent_spec import (  # noqa: E402
    CONTAINER_AGENT_LOG,
    CONTAINER_INSTRUCTION_PATH,
    CONTAINER_WORKDIR,
    resolve_agent,
)
from cbrun.assets import load_case  # noqa: E402
from cbrun.denylist import GITHUB_BLOCK_HOSTS  # noqa: E402
from cbrun.docker_env import Container, docker_available  # noqa: E402
from cbrun.images import ensure_agent_image  # noqa: E402
from cbrun.isolation import synthesize_task_toml  # noqa: E402
from cbrun.judge import run_isolated_judge  # noqa: E402
from cbrun.run_case import _run_agent_setup  # noqa: E402
from cbrun.steps import discover_steps  # noqa: E402

LOCAL_AGENTS = Path(__file__).resolve().parent
BACKENDS = ("codex", "opencode", "claude-code", "cursor")
SMOKE_CASE = "case001"
SMOKE_INSTRUCTION = (
    "Smoke test only. Create the file /app/smoke_probe.txt whose entire content "
    "is exactly AGENT_OK (no quotes, no extra lines). Do not modify any other "
    "files. Reply briefly when done."
)
PROBE_PATH = f"{CONTAINER_WORKDIR}/smoke_probe.txt"
AGENT_TIMEOUT_SEC = 600.0
STALL_WINDOW_SEC = 300.0
JUDGE_TIMEOUT_SEC = 300.0


def _case_dir(case_id: str, cases_root: Path | None = None) -> Path:
    roots: list[Path] = []
    if cases_root is not None:
        roots.append(Path(cases_root))
    roots.append(BENCHMARK_ROOT / "cases")
    for root in roots:
        candidate = Path(root) / case_id
        if (candidate / "source" / "manifest.json").is_file():
            return candidate
    raise FileNotFoundError(f"case not found: {case_id}")


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(
            f"missing {path.name}; copy {path.name}.example and fill in credentials"
        )
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            out[key] = value
    return out


def _apply_env(env_file: dict[str, str]) -> str:
    model = (env_file.get("MODEL") or "").strip()
    if not model:
        raise ValueError("MODEL must be set in env file")
    for key, value in env_file.items():
        if key == "MODEL" or not value:
            continue
        os.environ[key] = value
    return model


def _secret_values(env_file: dict[str, str]) -> list[str]:
    skip = {"MODEL"}
    return [v for k, v in env_file.items() if k not in skip and len(v) >= 8]


def _smoke_judge_ok(outcome) -> tuple[bool, str]:
    """Smoke-only /app must go through isolated judge but must not score 1.

    A collection/count gate error is expected: the probe file is not the
    product, so the frozen hidden suite cannot execute.
    """
    if outcome.reward == 1.0:
        return False, "smoke-only /app scored reward=1"
    err = (outcome.judge_error or "").lower()
    if not err:
        return True, f"judge ran reward={outcome.reward}"
    expected = (
        "parseable executed-test summary" in err
        or "expected_test_count" in err
        or "executed test count" in err
    )
    if expected:
        return True, f"judge fail-closed on smoke-only /app ({outcome.judge_error})"
    return False, f"judge harness: {outcome.judge_error}"


def _logs_contain_secrets(text: str, secrets: list[str]) -> list[str]:
    hits = []
    for secret in secrets:
        if secret in text:
            hits.append(secret[:4] + "…")
    return hits


def _maybe_copy_opencode_config(container: Container) -> None:
    cfg = LOCAL_AGENTS / "opencode.json"
    if not cfg.is_file():
        return
    container.exec("mkdir -p /root/.config/opencode", timeout_sec=10.0)
    container.write_file("/root/.config/opencode/opencode.json", cfg.read_bytes())


def run_smoke(
    backend: str,
    *,
    cache_root: Path,
    out_root: Path,
    case_id: str = SMOKE_CASE,
    cases_root: Path | None = None,
) -> int:
    env_path = LOCAL_AGENTS / f"{backend}.env"
    env_file = _load_env_file(env_path)
    model = _apply_env(env_file)
    secrets = _secret_values(env_file)

    print(f"[smoke] backend={backend} model={model} case={case_id}", flush=True)

    case_dir = _case_dir(case_id, cases_root)
    case = load_case(case_dir)
    step = discover_steps(case)[0]
    image = ensure_agent_image(case_id, cache_root=cache_root, case_dir=case_dir)
    invocation = resolve_agent(backend=backend, model=model, environ=os.environ)

    out_dir = out_root / backend
    out_dir.mkdir(parents=True, exist_ok=True)

    container = Container.start(
        image.agent_image,
        gpus=case.docker_gpus or None,
        network="host",
        block_hosts=GITHUB_BLOCK_HOSTS,
    )
    ok = True
    try:
        if backend == "opencode":
            _maybe_copy_opencode_config(container)

        container.write_file(CONTAINER_INSTRUCTION_PATH, SMOKE_INSTRUCTION.encode("utf-8"))
        if invocation.run_as:
            container.exec(
                f"chown {invocation.run_as} {CONTAINER_INSTRUCTION_PATH}",
                timeout_sec=10.0,
            )
        setup_out = _run_agent_setup(container, invocation, out_dir=out_dir)
        if setup_out is not None and setup_out.exit_code != 0:
            print(f"  FAIL setup exit={setup_out.exit_code}", flush=True)
            print(setup_out.tail or "", flush=True)
            return 1

        container.exec("mkdir -p /logs/agent", timeout_sec=10.0)

        solve = container.exec_solve(
            invocation.command,
            workdir=CONTAINER_WORKDIR,
            env=invocation.env,
            wall_timeout_sec=AGENT_TIMEOUT_SEC,
            stall_window_sec=STALL_WINDOW_SEC,
            log_path=out_dir / "agent.log",
            stall_marker=CONTAINER_AGENT_LOG,
            user=invocation.run_as,
        )
        agent_log = (out_dir / "agent.log").read_text(encoding="utf-8", errors="replace")
        setup_log_path = out_dir / "agent_setup.log"
        setup_log = (
            setup_log_path.read_text(encoding="utf-8", errors="replace")
            if setup_log_path.is_file()
            else ""
        )

        leaked = _logs_contain_secrets(agent_log + setup_log, secrets)
        if leaked:
            print(f"  FAIL secret(s) found in logs: {leaked}", flush=True)
            ok = False
        else:
            print("  OK   logs contain no literal secrets", flush=True)

        probe = container.exec(f"cat {PROBE_PATH}", timeout_sec=10.0, user=invocation.run_as)
        if probe.exit_code != 0 or "AGENT_OK" not in (probe.tail or ""):
            print(f"  FAIL smoke_probe missing or wrong (exit={probe.exit_code})", flush=True)
            ok = False
        else:
            print("  OK   /app/smoke_probe.txt contains AGENT_OK", flush=True)

        if solve.exit_code != 0 and not solve.timed_out:
            print(f"  WARN agent exit={solve.exit_code} (probe may still pass)", flush=True)
        elif solve.timed_out:
            print("  FAIL agent timed out", flush=True)
            ok = False

        t0 = time.monotonic()
        outcome = run_isolated_judge(
            container,
            image=image.agent_image,
            tests_final_dir=image.tests_cache_dir / "final",
            task_toml=synthesize_task_toml(case, step),
            test_timeout_sec=JUDGE_TIMEOUT_SEC,
            artifacts_dir=out_dir,
            workspace_export_dir=out_dir / "judge_workspace",
            gpus=case.docker_gpus or None,
        )
        judge_sec = round(time.monotonic() - t0, 1)
        judge_ok, judge_msg = _smoke_judge_ok(outcome)
        print(f"  {'OK' if judge_ok else 'FAIL'}   {judge_msg} ({judge_sec}s)", flush=True)
        if not judge_ok:
            ok = False
    finally:
        container.remove()

    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test cbrun agents locally.")
    parser.add_argument(
        "backend",
        nargs="?",
        choices=[*BACKENDS, "all"],
        default="all",
        help="Backend to test (default: all).",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=BENCHMARK_ROOT / ".cbrun_cache",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=LOCAL_AGENTS / "output",
    )
    parser.add_argument(
        "--case",
        default=SMOKE_CASE,
        help=f"Case id whose :agent image to smoke (default: {SMOKE_CASE}).",
    )
    parser.add_argument("--cases-root", type=Path)
    args = parser.parse_args(argv)

    if not docker_available():
        print("error: docker unavailable", file=sys.stderr)
        return 2

    targets = BACKENDS if args.backend == "all" else (args.backend,)
    rc = 0
    for backend in targets:
        try:
            code = run_smoke(
                backend,
                cache_root=args.cache_root,
                out_root=args.out,
                case_id=args.case,
                cases_root=args.cases_root,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[smoke] {backend}: ERROR {type(exc).__name__}: {exc}", flush=True)
            code = 1
        rc = rc or code
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
