"""Trial result schema, summary aggregation and reward-matrix rendering."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .limits import TerminalStatus
from .state import atomic_json

__all__ = ["TrialResult", "write_summary", "format_reward_matrix"]


@dataclass
class TrialResult:
    """Outcome of a single (case, backend, model) trial."""

    case_id: str
    backend: str
    model: str
    reward: float
    terminal_status: str  # TerminalStatus value
    judge_error: str | None = None
    agent_exit_code: int | None = None
    judge_exit_code: int | None = None
    solve_seconds: float | None = None
    judge_seconds: float | None = None
    deliverable_image: str | None = None
    agent_image: str | None = None
    agent_spec_name: str | None = None
    agent_spec_hash: str | None = None
    resolved_model: str | None = None
    run_as: str | None = None
    model_prefix: str | None = None
    env_keys: list[str] = field(default_factory=list)
    setup_ok: bool | None = None
    cli_version: str | None = None
    logs: dict[str, str] = field(default_factory=dict)
    # Reserved for multi-step pipelines; single-final fills passed_steps=[1].
    passed_steps: list[int] = field(default_factory=list)
    failed_step: int | None = None
    error: str | None = None
    denylist_violation: str | None = None
    denylist_warnings: list[str] = field(default_factory=list)
    denylist_fix_attempts: int = 0
    denylist_enforced: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    agent_image_id: str | None = None
    deliverable_image_id: str | None = None
    platform: str | None = None
    test_files: dict[str, str] = field(default_factory=dict)
    test_count: int | None = None
    failed_tests: list[str] = field(default_factory=list)
    artifact_errors: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    reasoning_effort: str | None = None
    judge_timeout_sec: float | None = None
    agent_timeout_sec: float | None = None
    host_arch: str | None = None
    emulated: bool | None = None
    infra_signals: dict[str, int] = field(default_factory=dict)
    run_valid: bool = True
    invalid_reason: str | None = None
    substrates_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def passed(self) -> bool:
        return self.reward >= 1.0


def write_summary(results: list[TrialResult], out_dir: Path) -> Path:
    """Write ``summary.json`` and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "trials": [r.to_dict() for r in results],
        "aggregate": _aggregate(results),
    }
    path = out_dir / "summary.json"
    atomic_json(path, payload)
    return path


def _aggregate(results: list[TrialResult]) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    by_status: dict[str, int] = {}
    for status in TerminalStatus:
        by_status[status.value] = sum(1 for r in results if r.terminal_status == status.value)
    judge_errors = sum(1 for r in results if r.judge_error)
    invalid = [r for r in results if not r.run_valid]
    valid = [r for r in results if r.run_valid]
    return {
        "total": total,
        "passed": passed,
        "reward_mean": (sum(r.reward for r in results) / total) if total else 0.0,
        "reward_mean_valid": (sum(r.reward for r in valid) / len(valid)) if valid else 0.0,
        "terminal_status": by_status,
        "judge_errors": judge_errors,
        "invalid_runs": len(invalid),
        "emulated_trials": sum(1 for r in results if r.emulated),
    }


def format_reward_matrix(results: list[TrialResult]) -> str:
    """Render a compact case x backend reward matrix as text."""
    if not results:
        return "(no trials)"
    cases = sorted({r.case_id for r in results})
    backends = sorted({r.backend for r in results})
    cell: dict[tuple[str, str], TrialResult] = {(r.case_id, r.backend): r for r in results}

    col_w = max(12, max(len(b) for b in backends))
    case_w = max(len("case"), max(len(c) for c in cases))
    header = "case".ljust(case_w) + "  " + "  ".join(b.ljust(col_w) for b in backends)
    lines = [header, "-" * len(header)]
    for c in cases:
        row = [c.ljust(case_w)]
        for b in backends:
            r = cell.get((c, b))
            if r is None:
                token = "-"
            else:
                if not r.run_valid:
                    signal = (r.invalid_reason or "infra").split(":", 1)[-1]
                    token = f"INFRA({signal})"
                elif r.judge_error:
                    token = "JUDGE_ERR"
                else:
                    mark = "PASS" if r.passed else "FAIL"
                    token = f"{mark}({r.terminal_status})"
            row.append(token.ljust(col_w))
        lines.append("  ".join(row))
    return "\n".join(lines)
