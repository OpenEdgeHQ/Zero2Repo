"""Single-trial orchestration for cbrun.

A trial: derive/reuse the ``:agent`` image, start a GT-free container (GPU +
host network only as needed, never the Docker socket), inject the instruction,
let the agent develop freely under a wall-clock limit, require an explicit
submit file, then copy only ``/app`` into a fresh ``:agent`` container and
judge. Missing submit is a failed attempt and skips the hidden tests.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from coding_bench_harbor._leakage import scan_leakage

from .agent_spec import (
    CONTAINER_AGENT_LOG,
    CONTAINER_INSTRUCTION_PATH,
    CONTAINER_WORKDIR,
    AgentInvocation,
    resolve_agent,
)
from .assets import AdapterError, CaseSpec, load_case
from .denylist import (
    DEFAULT_FIX_RETRIES,
    GITHUB_BLOCK_HOSTS,
    ScanResult,
    build_fix_instruction,
    load_denylist,
    scan_installed_warnings,
    scan_workspace_imports,
)
from .docker_env import Container, ExecResult
from .images import AgentImage, ensure_agent_image
from .instruction import build_instruction
from .isolation import synthesize_task_toml
from .judge import run_isolated_judge
from .limits import Limits, TerminalStatus, classify_terminal, resolve_limits
from .results import TrialResult
from .steps import Step, discover_steps
from .submit import CONTAINER_SUBMIT_PATH, NO_SUBMIT_ERROR, is_valid_submit

__all__ = ["run_trial"]


_CLI_BIN = {
    "codex": "codex",
    "opencode": "opencode",
    "claude-code": "claude",
    "cursor": "cursor-agent",
}


def _probe_cli_version(container: Container, spec_name: str) -> str | None:
    bin_name = _CLI_BIN.get(spec_name)
    if not bin_name:
        return None
    probe = container.exec(f"command -v {bin_name} >/dev/null && {bin_name} --version", timeout_sec=30.0)
    if probe.exit_code != 0:
        return None
    return (probe.tail or "").strip() or None


def _check_public_leakage(case: CaseSpec, *, allow_leakage: bool) -> None:
    """Fail fast when public PRD/Contract/build_command contain sensitive terms."""
    full_text = f"{case.prd_text}\n{case.contract_text}\n{case.build_command}"
    hits = scan_leakage(full_text, case.sensitive_terms)
    if not hits or allow_leakage:
        return
    summary = ", ".join(f"{hit.term} (x{hit.occurrences})" for hit in hits)
    raise AdapterError(
        f"Case '{case.case_id}' leaks source-identity terms: {summary}. "
        "Sanitize public/ documents or pass --allow-leakage to override."
    )


def run_trial(
    case_dir: Path | str,
    *,
    backend: str | None = None,
    agent_spec_path: Path | str | None = None,
    model: str,
    out_dir: Path,
    cache_root: Path,
    limits: Limits | None = None,
    timeout_multiplier: float = 1.0,
    force_image: bool = False,
    allow_leakage: bool = False,
    enforce_denylist: bool = True,
    denylist_fix_retries: int = DEFAULT_FIX_RETRIES,
    block_github: bool = True,
) -> TrialResult:
    """Run one (case, backend/spec, model) trial and return its result."""
    case_dir = Path(case_dir)
    case = load_case(case_dir)
    _check_public_leakage(case, allow_leakage=allow_leakage)
    steps = discover_steps(case)
    limits = limits or resolve_limits(multiplier=timeout_multiplier)
    denylist = load_denylist(case_dir) if enforce_denylist else None

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    image = ensure_agent_image(
        case.case_id,
        cache_root=Path(cache_root),
        case_dir=case_dir,
        force=force_image,
        backend=backend,
    )

    gpus = case.docker_gpus or None
    invocation = resolve_agent(
        backend=backend,
        agent_spec_path=agent_spec_path,
        model=model,
        instruction_path=CONTAINER_INSTRUCTION_PATH,
        log_path=CONTAINER_AGENT_LOG,
    )
    resolved_backend = invocation.spec.name

    result = TrialResult(
        case_id=case.case_id,
        backend=resolved_backend,
        model=model,
        reward=0.0,
        terminal_status=TerminalStatus.ERROR.value,
        deliverable_image=image.deliverable_image,
        agent_image=image.agent_image,
        agent_spec_name=invocation.spec.name,
        agent_spec_hash=invocation.spec_hash,
        resolved_model=invocation.resolved_model,
        run_as=invocation.run_as or "root",
        model_prefix=invocation.spec.model_prefix,
        env_keys=list(invocation.env_keys),
    )

    block_hosts = GITHUB_BLOCK_HOSTS if block_github else None
    container = Container.start(
        image.agent_image,
        gpus=gpus,
        network="host",
        block_hosts=block_hosts,
    )
    try:
        result.cli_version = _probe_cli_version(container, invocation.spec.name)
        passed_steps: list[int] = []
        for step in steps:
            step_outcome = _run_step(
                container,
                case=case,
                case_dir=case_dir,
                step=step,
                image=image,
                invocation=invocation,
                limits=limits,
                out_dir=out_dir,
                result=result,
                denylist=denylist,
                denylist_fix_retries=denylist_fix_retries,
            )
            if step_outcome:
                passed_steps.append(step.index)
            else:
                result.failed_step = step.index
                break
        result.passed_steps = passed_steps
    finally:
        container.remove()

    return result


def _run_agent_setup(
    container: Container,
    invocation: AgentInvocation,
    *,
    out_dir: Path,
) -> ExecResult | None:
    container.exec(invocation.prepare_workspace, timeout_sec=60.0)

    if invocation.install_script:
        install = container.exec(
            invocation.install_script,
            workdir=CONTAINER_WORKDIR,
            env=invocation.env,
            timeout_sec=300.0,
            user=invocation.run_as,
        )
        if install.exit_code != 0:
            return install

    if not invocation.setup_script:
        container.exec("mkdir -p /logs/agent", timeout_sec=10.0)
        return None

    container.exec("mkdir -p /logs/agent", timeout_sec=10.0)
    setup = container.exec(
        invocation.setup_script,
        workdir=CONTAINER_WORKDIR,
        env=invocation.env,
        timeout_sec=invocation.setup_timeout_sec,
        user=invocation.run_as,
    )
    setup_log = out_dir / "agent_setup.log"
    setup_log.write_text(setup.tail or "", encoding="utf-8")
    return setup


def _list_installed_packages(container: Container) -> list[str]:
    packages: list[str] = []
    pip_res = container.exec("pip list --format=freeze 2>/dev/null || true", timeout_sec=60.0)
    for line in (pip_res.tail or "").splitlines():
        name = line.split("==", 1)[0].strip()
        if name:
            packages.append(name)
    conda_res = container.exec(
        "command -v conda >/dev/null 2>&1 && conda list --json || true",
        timeout_sec=120.0,
    )
    if conda_res.exit_code == 0 and (conda_res.tail or "").strip().startswith("["):
        try:
            entries = json.loads(conda_res.tail or "[]")
            for entry in entries:
                name = str(entry.get("name") or "").strip()
                if name:
                    packages.append(name)
        except json.JSONDecodeError:
            pass
    return packages


def _copy_workspace(container: Container, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ok = container.cp_from(CONTAINER_WORKDIR, dest)
    if not ok:
        raise RuntimeError(f"failed to copy workspace from container {CONTAINER_WORKDIR}")
    workspace = dest / "app"
    return workspace if workspace.is_dir() else dest


def _scan_denylist(
    container: Container,
    *,
    case_dir: Path,
    spec,
    scratch: Path,
) -> ScanResult:
    workspace = _copy_workspace(container, scratch / "workspace")
    import_hits = scan_workspace_imports(workspace, spec)
    installed = _list_installed_packages(container)
    host_spec = load_denylist(case_dir)
    if host_spec is None:
        return ScanResult(import_hits=import_hits)
    warnings = scan_installed_warnings(installed, host_spec)
    return ScanResult(import_hits=import_hits, installed_warnings=warnings)


def _write_scan_report(out_dir: Path, scan: ScanResult, *, label: str) -> None:
    payload = {
        "label": label,
        "import_hits": [hit.__dict__ for hit in scan.import_hits],
        "installed_warnings": [hit.__dict__ for hit in scan.installed_warnings],
    }
    (out_dir / f"denylist_scan_{label}.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _run_solve(
    container: Container,
    invocation: AgentInvocation,
    *,
    limits: Limits,
    out_dir: Path,
    log_name: str,
    wall_timeout_sec: float | None = None,
) -> ExecResult:
    log_path = out_dir / log_name
    return container.exec_solve(
        invocation.command,
        workdir=CONTAINER_WORKDIR,
        env=invocation.env,
        wall_timeout_sec=wall_timeout_sec or limits.max_agent_timeout_sec,
        stall_window_sec=limits.stall_window_sec,
        log_path=log_path,
        stall_marker=CONTAINER_AGENT_LOG,
        activity_path=CONTAINER_WORKDIR,
        user=invocation.run_as,
    )


def _read_submit_text(container: Container) -> str | None:
    res = container.exec(f"test -f {CONTAINER_SUBMIT_PATH} && cat {CONTAINER_SUBMIT_PATH}")
    if res.exit_code != 0:
        return None
    return res.tail


def _clear_submit(container: Container) -> None:
    container.exec(f"rm -f {CONTAINER_SUBMIT_PATH}", timeout_sec=10.0)


def _record_submit_outcome(
    container: Container,
    result: TrialResult,
    *,
    solve: ExecResult,
    solve_start: float,
) -> bool:
    """Apply terminal status from this CLI + submit file. False means stop (no judge)."""
    submitted = is_valid_submit(_read_submit_text(container))
    result.terminal_status = classify_terminal(
        exit_code=solve.exit_code,
        timed_out=solve.timed_out,
        stall_killed=solve.stall_killed,
        submitted=submitted,
    ).value
    result.solve_seconds = round(time.monotonic() - solve_start, 2)
    if submitted:
        return True
    result.reward = 0.0
    result.error = NO_SUBMIT_ERROR
    return False


def _inject_instruction(
    container: Container,
    instruction: str,
    invocation: AgentInvocation,
) -> None:
    container.write_file(CONTAINER_INSTRUCTION_PATH, instruction.encode("utf-8"))
    if invocation.run_as:
        container.exec(
            f"chown {invocation.run_as} {CONTAINER_INSTRUCTION_PATH}",
            timeout_sec=10.0,
        )


def _run_step(
    container: Container,
    *,
    case: CaseSpec,
    case_dir: Path,
    step: Step,
    image: AgentImage,
    invocation: AgentInvocation,
    limits: Limits,
    out_dir: Path,
    result: TrialResult,
    denylist,
    denylist_fix_retries: int,
) -> bool:
    """Run the solve+judge for one step; return True iff its gate passed."""
    base_instruction = build_instruction(
        step.prd_text,
        step.contract_text,
        hardware_text=case.hardware_text,
        build_command=case.build_command,
        workdir=case.workdir,
    )
    _inject_instruction(container, base_instruction, invocation)

    setup_outcome = _run_agent_setup(container, invocation, out_dir=out_dir)
    result.setup_ok = setup_outcome is None or setup_outcome.exit_code == 0
    setup_log = out_dir / "agent_setup.log"
    if setup_log.is_file():
        result.logs["agent_setup_log"] = str(setup_log)
    if setup_outcome is not None and setup_outcome.exit_code != 0:
        result.terminal_status = TerminalStatus.ERROR.value
        result.error = f"agent setup failed (exit {setup_outcome.exit_code})"
        result.logs["agent_log"] = str(out_dir / "agent.log")
        result.reward = 0.0
        return False

    solve_start = time.monotonic()
    solve = _run_solve(container, invocation, limits=limits, out_dir=out_dir, log_name="agent.log")
    result.agent_exit_code = solve.exit_code
    result.logs["agent_log"] = str(out_dir / "agent.log")
    if not _record_submit_outcome(container, result, solve=solve, solve_start=solve_start):
        return False

    if denylist is not None and denylist.enabled:
        scratch = out_dir / "denylist_scratch"
        retries_left = denylist_fix_retries
        while True:
            scan = _scan_denylist(container, case_dir=case_dir, spec=denylist, scratch=scratch)
            _write_scan_report(out_dir, scan, label="initial" if retries_left == denylist_fix_retries else "rescan")
            result.denylist_warnings = [
                f"installed:{hit.package}" for hit in scan.installed_warnings
            ]
            if not scan.has_hard_violation:
                break
            if retries_left <= 0:
                summary = "; ".join(
                    f"{hit.token}@{hit.path}:{hit.line}" for hit in scan.import_hits[:5]
                )
                result.denylist_violation = (
                    f"upstream import/symbol still present after {denylist_fix_retries} fix attempt(s): {summary}"
                )
                result.reward = 0.0
                result.terminal_status = TerminalStatus.ERROR.value
                result.error = result.denylist_violation
                result.logs["denylist_scan"] = str(out_dir / "denylist_scan_rescan.json")
                result.solve_seconds = round(time.monotonic() - solve_start, 2)
                return False
            fix_instruction = build_fix_instruction(base_instruction, scan.import_hits)
            _inject_instruction(container, fix_instruction, invocation)
            elapsed = time.monotonic() - solve_start
            remaining = limits.max_agent_timeout_sec - elapsed
            if remaining < 60:
                result.denylist_violation = (
                    "upstream import/symbol detected but insufficient wall-clock budget for fix retry"
                )
                result.reward = 0.0
                result.terminal_status = TerminalStatus.ERROR.value
                result.error = result.denylist_violation
                result.solve_seconds = round(time.monotonic() - solve_start, 2)
                return False
            _clear_submit(container)
            fix_solve = _run_solve(
                container,
                invocation,
                limits=limits,
                out_dir=out_dir,
                log_name="agent_fix.log",
                wall_timeout_sec=remaining,
            )
            result.denylist_fix_attempts += 1
            retries_left -= 1
            result.logs["agent_fix_log"] = str(out_dir / "agent_fix.log")
            result.agent_exit_code = fix_solve.exit_code
            if not _record_submit_outcome(
                container, result, solve=fix_solve, solve_start=solve_start
            ):
                return False

    task_toml = synthesize_task_toml(case, step)
    outcome = run_isolated_judge(
        container,
        image=image.agent_image,
        tests_final_dir=image.tests_cache_dir / "final",
        task_toml=task_toml,
        test_timeout_sec=limits.max_test_timeout_sec,
        artifacts_dir=out_dir,
        workspace_export_dir=out_dir / "judge_workspace",
        gpus=case.docker_gpus or None,
    )
    result.reward = outcome.reward
    result.judge_error = outcome.judge_error
    result.judge_exit_code = outcome.exit_code
    result.judge_seconds = round(outcome.seconds, 2)
    result.logs["judge_report"] = str(out_dir / "final_report.json")
    result.logs["judge_log"] = str(out_dir / "judge.log")
    tests_log = out_dir / "final_tests.log"
    if tests_log.is_file():
        result.logs["final_tests_log"] = str(tests_log)

    return outcome.reward >= 1.0 and not outcome.judge_error
