"""Hidden-gate judging for cbrun.

After the solve phase ends, the runner copies only the candidate ``/app``
tree into a fresh ``:agent`` container (image defaults, no solve env),
injects the cached hidden tests, and runs the Harbor-shared ``final_judge.py``.
Reward is binary; a harness failure is reported as ``judge_error``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .docker_env import Container

__all__ = [
    "JudgeOutcome",
    "FINAL_JUDGE_SRC",
    "LAUNCHER_SRC",
    "run_judge",
    "run_isolated_judge",
    "export_app",
    "import_app",
    "validate_judge_report",
]

# The judge script is shared with the Harbor adapter (single source of truth).
_HARBOR = Path(__file__).resolve().parent.parent / "coding_bench_harbor"
FINAL_JUDGE_SRC = _HARBOR / "final_judge.py"
TEST_COUNTS_SRC = _HARBOR / "test_counts.py"
LAUNCHER_SRC = _HARBOR / "pytest_launcher.py"
NODE_BLOCK_SRC = _HARBOR / "_cb_import_block.cjs"

CONTAINER_TESTS_FINAL = "/tests/final"
CONTAINER_TASK_TOML = "/task.toml"
CONTAINER_JUDGE_PATH = "/tests/final_judge.py"
CONTAINER_LAUNCHER_PATH = "/tests/pytest_launcher.py"
CONTAINER_NODE_BLOCK_PATH = "/tests/_cb_import_block.cjs"
CONTAINER_VERIFIER_DIR = "/logs/verifier"
CONTAINER_APP = "/app"

_PYTHON_BAN_ECOSYSTEMS = frozenset({"pip", "conda", "source"})
_NODE_BAN_ECOSYSTEMS = frozenset({"npm"})


@dataclass
class JudgeOutcome:
    reward: float
    judge_error: str | None
    exit_code: int
    seconds: float
    report: dict = field(default_factory=dict)


def validate_judge_report(report: dict | None) -> tuple[float, str | None]:
    """Return ``(reward, judge_error)`` from a final_judge report.

    Reward must be 0 or 1. A passing reward without verified counts, or
    with failed/error tests, is a harness error and scores 0.
    """
    if not isinstance(report, dict) or not report:
        return 0.0, "final_judge produced no report"
    raw_reward = report.get("reward")
    reward = (
        float(raw_reward)
        if isinstance(raw_reward, (int, float)) and not isinstance(raw_reward, bool)
        else -1.0
    )
    judge_error = report.get("judge_error")
    if judge_error:
        return 0.0, str(judge_error)
    final = report.get("final")
    if reward not in (0.0, 1.0):
        return 0.0, "invalid non-binary reward in judge report"
    if not isinstance(final, dict) or final.get("counts_parsed") is not True or not final.get("total_count"):
        return 0.0, "judge report has no verified test counts"
    if reward == 1.0 and (
        final.get("failed_count", 0) or final.get("error_count", 0) or not final.get("passed_count")
    ):
        return 0.0, "passing reward contradicts test counts"
    return reward, None


def export_app(container: Container, dest: Path) -> Path:
    """Copy ``/app`` files out of *container* onto the host. No env is copied."""
    dest = Path(dest)
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ok = container.cp_from(CONTAINER_APP, dest)
    if not ok:
        raise RuntimeError("could not export candidate /app; refusing to judge an empty replacement")
    workspace = dest / "app"
    return workspace if workspace.is_dir() else dest


def import_app(container: Container, host_app: Path) -> None:
    """Copy a host ``/app`` tree into *container* at ``/app``."""
    container.exec(f"mkdir -p {CONTAINER_APP}")
    host_app = Path(host_app)
    if not host_app.is_dir():
        return
    for child in sorted(host_app.iterdir()):
        container.cp_to(child, f"{CONTAINER_APP}/")
    container.exec(f"chmod -R a+rX {CONTAINER_APP}")


def _import_ban_env(denylist) -> dict[str, str]:
    """Process-level import ban, routed by ecosystem. Never enable both blindly."""
    if denylist is None:
        return {}
    tokens = [str(x).strip() for x in getattr(denylist, "import_ban", ()) if str(x).strip()]
    if not tokens:
        return {}
    eco = str(getattr(denylist, "ecosystem", "") or "").strip().lower()
    env = {"CODING_BENCH_IMPORT_BAN": ",".join(tokens)}
    if eco in _PYTHON_BAN_ECOSYSTEMS:
        return env
    if eco in _NODE_BAN_ECOSYSTEMS:
        env["NODE_OPTIONS"] = f"--require {CONTAINER_NODE_BLOCK_PATH}"
        return env
    return env


def run_judge(
    container: Container,
    *,
    tests_final_dir: Path,
    task_toml: bytes,
    test_timeout_sec: float,
    artifacts_dir: Path,
    denylist=None,
    judge_bans: list[str] | tuple[str, ...] = (),
) -> JudgeOutcome:
    """Inject hidden tests + task.toml, run final_judge, parse the reward."""
    if not (Path(tests_final_dir) / "test_manifest.json").is_file():
        raise RuntimeError(f"hidden tests cache invalid: {tests_final_dir}")
    if not FINAL_JUDGE_SRC.is_file():
        raise RuntimeError(f"final_judge.py not found at {FINAL_JUDGE_SRC}")
    if not LAUNCHER_SRC.is_file():
        raise RuntimeError(f"pytest_launcher.py not found at {LAUNCHER_SRC}")

    container.exec(f"rm -rf {CONTAINER_TESTS_FINAL} && mkdir -p {CONTAINER_TESTS_FINAL}")
    for child in sorted(Path(tests_final_dir).iterdir()):
        container.cp_to(child, f"{CONTAINER_TESTS_FINAL}/")

    container.write_file(CONTAINER_TASK_TOML, task_toml)
    container.cp_to(FINAL_JUDGE_SRC, CONTAINER_JUDGE_PATH)
    container.cp_to(TEST_COUNTS_SRC, "/tests/test_counts.py")
    container.cp_to(LAUNCHER_SRC, CONTAINER_LAUNCHER_PATH)
    ban_env = _import_ban_env(denylist)
    if "NODE_OPTIONS" in ban_env:
        if not NODE_BLOCK_SRC.is_file():
            raise RuntimeError(f"_cb_import_block.cjs not found at {NODE_BLOCK_SRC}")
        container.cp_to(NODE_BLOCK_SRC, CONTAINER_NODE_BLOCK_PATH)
    container.exec(f"mkdir -p {CONTAINER_VERIFIER_DIR}")

    env = {
        "CODING_BENCH_WORKSPACE": CONTAINER_APP,
        "CODING_BENCH_TESTS_FINAL": CONTAINER_TESTS_FINAL,
        "CODING_BENCH_TASK_TOML": CONTAINER_TASK_TOML,
        "CODING_BENCH_VERIFIER_DIR": CONTAINER_VERIFIER_DIR,
        "CODING_BENCH_PYTEST_LAUNCHER": CONTAINER_LAUNCHER_PATH,
        **ban_env,
    }
    bans = [str(x).strip() for x in judge_bans if str(x).strip()]
    if bans:
        env["CODING_BENCH_JUDGE_BANS"] = ",".join(bans)
        if "NODE_OPTIONS" not in env:
            eco = str(getattr(denylist, "ecosystem", "") or "").strip().lower()
            if eco in _NODE_BAN_ECOSYSTEMS:
                if not NODE_BLOCK_SRC.is_file():
                    raise RuntimeError(f"_cb_import_block.cjs not found at {NODE_BLOCK_SRC}")
                container.cp_to(NODE_BLOCK_SRC, CONTAINER_NODE_BLOCK_PATH)
                env["NODE_OPTIONS"] = f"--require {CONTAINER_NODE_BLOCK_PATH}"
    res = container.exec(
        f"PYTHONPATH=/tests python3 {CONTAINER_JUDGE_PATH}",
        env=env,
        timeout_sec=test_timeout_sec,
    )

    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_local = artifacts_dir / "final_report.json"
    got_report = container.cp_from(
        f"{CONTAINER_VERIFIER_DIR}/final_report.json", report_local
    )
    container.cp_from(
        f"{CONTAINER_VERIFIER_DIR}/final_tests.log", artifacts_dir / "final_tests.log"
    )
    (artifacts_dir / "judge.log").write_text(res.tail, encoding="utf-8")

    report: dict = {}
    if got_report and report_local.is_file():
        try:
            report = json.loads(report_local.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}

    if not isinstance(report, dict):
        report = {}
    reward, judge_error = validate_judge_report(report)
    if res.timed_out:
        judge_error = f"judge timed out after {test_timeout_sec}s"
        reward = 0.0
    elif not report:
        judge_error = (
            f"final_judge produced no report (exit {res.exit_code}); "
            f"tail: {res.tail[-800:]}"
        )
        reward = 0.0
    elif res.exit_code and not judge_error:
        judge_error = f"judge process failed (exit {res.exit_code})"
        reward = 0.0

    return JudgeOutcome(
        reward=reward,
        judge_error=judge_error,
        exit_code=res.exit_code,
        seconds=res.seconds,
        report=report,
    )


def run_isolated_judge(
    solve_container: Container,
    *,
    image: str,
    tests_final_dir: Path,
    task_toml: bytes,
    test_timeout_sec: float,
    artifacts_dir: Path,
    workspace_export_dir: Path,
    gpus: str | None = None,
    denylist=None,
    judge_bans: list[str] | tuple[str, ...] = (),
) -> JudgeOutcome:
    """Judge ``/app`` from *solve_container* inside a fresh copy of *image*.

    Only files under ``/app`` cross the boundary. The judge container is
    started from the image default environment (no solve env) and
    ``--network none``.
    """
    host_app = export_app(solve_container, workspace_export_dir)
    judge_container = Container.start(image, gpus=gpus, network="none")
    try:
        import_app(judge_container, host_app)
        return run_judge(
            judge_container,
            tests_final_dir=tests_final_dir,
            task_toml=task_toml,
            test_timeout_sec=test_timeout_sec,
            artifacts_dir=artifacts_dir,
            denylist=denylist,
            judge_bans=judge_bans,
        )
    finally:
        judge_container.remove()
