"""Rejudge a host workspace against a case image. No agent run.

Used by ``doc/rejudge.py`` and ``tools/run_controls.py``. Docker is only
required when actually scoring a workspace; reward comparison is pure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assets import load_case
from .denylist import require_denylist
from .docker_env import Container
from .images import ensure_agent_image
from .isolation import synthesize_task_toml
from .judge import import_app, run_judge
from .limits import DEFAULT_TEST_TIMEOUT_SEC
from .steps import discover_steps

__all__ = ["parse_expect_reward", "reward_matches", "iter_controls", "main"]


def parse_expect_reward(value: str | int | float | None) -> float | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if text not in {"0", "1", "0.0", "1.0"}:
        raise ValueError(f"--expect-reward must be 0 or 1, got {value!r}")
    return float(int(float(text)))


def reward_matches(actual: float, expect: float | None) -> bool:
    if expect is None:
        return True
    return float(actual) == float(expect)


def iter_controls(cases_root: Path | str):
    """Yield ``(case_id, control_name, control_dir, expect_reward)``."""
    root = Path(cases_root)
    if not root.is_dir():
        return
    for case_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        controls = case_dir / "controls"
        if not controls.is_dir():
            continue
        for control in sorted(p for p in controls.iterdir() if p.is_dir()):
            expect_path = control / "expect.json"
            expect = 0.0
            if expect_path.is_file():
                payload = json.loads(expect_path.read_text(encoding="utf-8"))
                expect = parse_expect_reward(payload.get("reward"))
                if expect is None:
                    expect = 0.0
            yield case_dir.name, control.name, control, expect


def _workspace_dir(control_or_app: Path) -> Path:
    app = control_or_app / "app"
    return app if app.is_dir() else control_or_app


def rejudge_workspace(
    *,
    case_dir: Path,
    workspace: Path,
    out_dir: Path,
    cache_root: Path,
    test_timeout_sec: float = DEFAULT_TEST_TIMEOUT_SEC,
    force_image: bool = False,
    enforce_denylist: bool = True,
    image: str | None = None,
    tests_dir: Path | None = None,
) -> float:
    case = load_case(case_dir)
    # Same import ban as a real trial; otherwise a control that delegates to
    # a banned module would be judged more leniently than an agent run.
    denylist = require_denylist(case_dir) if enforce_denylist else None
    if image is None:
        resolved = ensure_agent_image(
            case.case_id,
            case_dir=case_dir,
            cache_root=cache_root,
            force=force_image,
            enforce_denylist=enforce_denylist,
        )
        agent_image = resolved.agent_image
        tests_final_dir = resolved.tests_cache_dir / "final"
    else:
        agent_image = image
        tests_final_dir = Path(tests_dir)
    step = discover_steps(case)[0]
    task_toml = synthesize_task_toml(case, step)
    out_dir.mkdir(parents=True, exist_ok=True)
    container = Container.start(agent_image, network="none")
    try:
        import_app(container, _workspace_dir(workspace))
        outcome = run_judge(
            container,
            tests_final_dir=tests_final_dir,
            task_toml=task_toml,
            test_timeout_sec=test_timeout_sec,
            artifacts_dir=out_dir,
            denylist=denylist,
            judge_bans=case.judge_bans,
        )
    finally:
        container.remove()
    (out_dir / "rejudge.json").write_text(
        json.dumps(
            {"reward": outcome.reward, "judge_error": outcome.judge_error},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if outcome.judge_error:
        raise RuntimeError(outcome.judge_error)
    return float(outcome.reward)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rejudge a workspace against hidden tests.")
    parser.add_argument("--case", required=True, help="Case id under --cases-root.")
    parser.add_argument("--workspace", type=Path, required=True, help="Host /app tree or control dir.")
    parser.add_argument("--cases-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, default=None)
    parser.add_argument("--expect-reward", default=None, help="Require reward 0 or 1.")
    parser.add_argument("--test-timeout-sec", type=float, default=DEFAULT_TEST_TIMEOUT_SEC)
    parser.add_argument("--force-image", action="store_true")
    parser.add_argument(
        "--enforce-denylist",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Use this image instead of building an agent image from the deliverable.",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=None,
        help="Host milestones/final directory copied into the container as /tests/final.",
    )
    args = parser.parse_args(argv)

    expect = parse_expect_reward(args.expect_reward)
    repo = Path(__file__).resolve().parent.parent
    cases_root = args.cases_root or repo / "cases"
    cache_root = args.cache_root or repo / ".cbrun_cache"
    case_dir = cases_root / args.case
    if not (case_dir / "source" / "manifest.json").is_file():
        print(f"error: case not found: {case_dir}", flush=True)
        return 2
    if args.out.exists():
        print(f"error: output directory already exists: {args.out}", flush=True)
        return 2
    if (args.image is None) != (args.tests_dir is None):
        print("error: --image and --tests-dir must be given together", flush=True)
        return 2
    if args.tests_dir is not None and not (args.tests_dir / "test_manifest.json").is_file():
        print(f"error: tests dir missing test_manifest.json: {args.tests_dir}", flush=True)
        return 2
    try:
        reward = rejudge_workspace(
            case_dir=case_dir,
            workspace=args.workspace,
            out_dir=args.out,
            cache_root=cache_root,
            test_timeout_sec=args.test_timeout_sec,
            force_image=args.force_image,
            enforce_denylist=args.enforce_denylist,
            image=args.image,
            tests_dir=args.tests_dir,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", flush=True)
        return 2
    print(f"reward={reward}")
    if not reward_matches(reward, expect):
        print(f"error: expected reward {expect}, got {reward}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
