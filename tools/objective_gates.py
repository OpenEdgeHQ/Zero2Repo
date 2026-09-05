#!/usr/bin/env python3
"""Language-agnostic objective quality gates for P3 milestone steps.

Python orchestration only performs deterministic checks: sensitive-term scan,
JSON contract set consistency, UTF-8/mojibake detection, and asset cleanliness.
Semantic quality (test fairness, PRD accuracy, etc.) is handled by Stage E harness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from artifact_contracts import (
    FINAL_ACCEPTANCE_DIR_NAME,
    compute_contract_coverage,
    coverage_matrix_core_gaps,
    load_json,
    resolve_step_dirs,
    validate_coverage_matrix,
    validate_test_manifest,
    validate_test_usage,
)
from lint_utils import check_mojibake
from sensitive_terms import IdentityLeakFinding

LeakJudge = Callable[[list[Path], list[str]], list[IdentityLeakFinding]]

# Directory names excluded when scanning or copying release assets (language-agnostic).
ASSET_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "coverage",
    "htmlcov",
    ".eggs",
    "agent_runs",
    "opencode_runs",
})

# Path segment / glob patterns for experimental backup dirs (not canonical milestones).
ASSET_EXPERIMENTAL_DIR_PATTERNS: tuple[str, ...] = (
    "_opencode",
    "_claude-code",
    "prd_opencode",
    "prd_claude-code",
)

# Binary / non-text extensions to skip for mojibake scans (exclusion-based, not language whitelist).
BINARY_SUFFIXES: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".sqlite", ".db",
})

# Egg-info and similar build artifact directory suffixes.
BUILD_ARTIFACT_DIR_SUFFIXES: tuple[str, ...] = (".egg-info",)


def shutil_ignore_patterns(directory: str, names: list[str]) -> set[str]:
    """Return names to ignore for shutil.copytree (Harbor adapter + release copy)."""
    ignored: set[str] = set()
    for name in names:
        if name in ASSET_EXCLUDED_DIR_NAMES:
            ignored.add(name)
            continue
        if any(pat in name for pat in ASSET_EXPERIMENTAL_DIR_PATTERNS):
            ignored.add(name)
            continue
        if any(name.endswith(suffix) for suffix in BUILD_ARTIFACT_DIR_SUFFIXES):
            ignored.add(name)
            continue
        if name.endswith((".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def _path_has_excluded_part(path: Path) -> bool:
    parts = path.parts
    if any(part in ASSET_EXCLUDED_DIR_NAMES for part in parts):
        return True
    for part in parts:
        if any(pat in part for pat in ASSET_EXPERIMENTAL_DIR_PATTERNS):
            return True
        if any(part.endswith(suffix) for suffix in BUILD_ARTIFACT_DIR_SUFFIXES):
            return True
    return False


def is_scannable_text_file(path: Path) -> bool:
    """True if *path* should be scanned for mojibake / sensitive terms (exclusion-based)."""
    if not path.is_file():
        return False
    if _path_has_excluded_part(path):
        return False
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    if path.name in ("opencode.json", ".opencode_prompt.md"):
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except (OSError, UnicodeDecodeError):
        return False


def discover_text_files(root: Path) -> list[Path]:
    """Discover UTF-8-decodable text files under *root* (no language suffix whitelist)."""
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if is_scannable_text_file(path):
            files.append(path)
    return sorted(files)


@dataclass
class ObjectiveIssue:
    severity: str  # "error" | "warning"
    rule: str
    message: str
    path: str = ""


def scan_sensitive_terms(
    paths: list[Path],
    blacklist: list[str],
    *,
    leak_judge: LeakJudge | None,
) -> list[ObjectiveIssue]:
    if leak_judge is None:
        raise ValueError(
            "scan_sensitive_terms requires leak_judge; substring matching is not supported",
        )
    if not blacklist or not paths:
        return []

    scannable = [p for p in paths if p.is_file()]
    if not scannable:
        return []

    try:
        findings = leak_judge(scannable, blacklist)
    except RuntimeError as exc:
        return [ObjectiveIssue(
            "error",
            "identity-leak-judge",
            str(exc),
            str(scannable[0].parent),
        )]

    issues: list[ObjectiveIssue] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        path_key = finding.path or "unknown"
        key = (finding.term, path_key)
        if key in seen:
            continue
        seen.add(key)
        count = sum(
            1 for f in findings if f.term == finding.term and (f.path or "unknown") == path_key
        )
        quote = finding.quote[:120] + ("..." if len(finding.quote) > 120 else "")
        msg = (
            f"Identity leak '{finding.term}' ({count}x): {finding.reason}"
            + (f" — \"{quote}\"" if quote else "")
        )
        issues.append(ObjectiveIssue(
            "error",
            "sensitive-term",
            msg,
            path_key,
        ))
    return issues


# Hidden-test reference patterns that must never appear in agent-visible spec docs.
# These are deterministic, language-agnostic signals of judge-internal leakage — not
# blacklisted upstream identity, but test node ids / internal usage-schema field names.
_TEST_NODE_ID_RE = re.compile(
    r"\b[\w./-]+\.(?:py|c|cc|cpp|h|hpp|t|lua|pl|pm|ts|tsx|js|jsx|rs|go|rb)::[\w.]+"
)
_TEST_FUNC_NODE_RE = re.compile(r"::test_[A-Za-z0-9_]+")
_USAGE_FIELD_RE = re.compile(r"\btest_refs\b|\binterface_dependencies\b")
_TESTS_BLOCK_RE = re.compile(r"\(\s*Tests?\s*:", re.IGNORECASE)


def scan_test_reference_leakage(
    paths: list[Path], test_basenames: set[str]
) -> list[ObjectiveIssue]:
    """Detect hidden-test references leaking into agent-visible documents.

    The PRD and Interface Contract are the exam paper: they must name the public
    interface without revealing the hidden judge's test files, node ids, or the
    internal ``test_usage.json`` schema fields. Matching is intentionally precise
    (file::node forms, ``::test_`` node ids, declared manifest basenames, and the
    ``test_refs`` / ``interface_dependencies`` field names) so ordinary prose such
    as "the tests import ..." is never flagged.
    """
    issues: list[ObjectiveIssue] = []
    basename_res = [
        (b, re.compile(r"(?<![\w./-])" + re.escape(b) + r"(?![\w])"))
        for b in sorted(test_basenames)
        if b
    ]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        seen: set[str] = set()
        for m in _TEST_NODE_ID_RE.findall(text):
            if m not in seen:
                seen.add(m)
                issues.append(ObjectiveIssue(
                    "error", "test-reference-leak",
                    f"hidden-test node id '{m}' leaked into agent-visible document",
                    str(path),
                ))
        for m in _TEST_FUNC_NODE_RE.findall(text):
            key = f"func::{m}"
            if key not in seen:
                seen.add(key)
                issues.append(ObjectiveIssue(
                    "error", "test-reference-leak",
                    f"hidden-test node reference '{m}' leaked into agent-visible document",
                    str(path),
                ))
        for m in _USAGE_FIELD_RE.findall(text):
            key = f"field::{m}"
            if key not in seen:
                seen.add(key)
                issues.append(ObjectiveIssue(
                    "error", "test-reference-leak",
                    f"internal usage-schema field '{m}' named in agent-visible document",
                    str(path),
                ))
        if _TESTS_BLOCK_RE.search(text):
            issues.append(ObjectiveIssue(
                "error", "test-reference-leak",
                "explicit test-reference block '(Tests: ...)' in agent-visible document",
                str(path),
            ))
        for base, rx in basename_res:
            if rx.search(text):
                issues.append(ObjectiveIssue(
                    "error", "test-reference-leak",
                    f"hidden-test file name '{base}' named in agent-visible document",
                    str(path),
                ))
    return issues


def check_contract_coverage(case_dir: Path, final_dir: Path) -> list[ObjectiveIssue]:
    """Report (warning) test_usage symbols not referenced by the Interface Contract.

    Only runs when the Contract already exists (repo-final topology: D -> Contract -> E),
    so the gaps surface in Stage E's objective_gate_report and feed the LLM's
    ``artifact_consistency`` judgement + ``spec_repair`` routing. Warning, not error: the
    plan keeps coverage as a report-to-E signal rather than a hard block.
    """
    contract_path = case_dir / "public" / "Interface_Contract.md"
    usage_path = final_dir / "test_usage.json"
    if not contract_path.is_file() or not usage_path.is_file():
        return []
    usage, _ = load_json(usage_path)
    if not isinstance(usage, dict):
        return []
    try:
        contract_text = contract_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    coverage = compute_contract_coverage(usage, contract_text)
    if not coverage.has_gaps:
        return []

    def _fmt(label: str, missing: list[str], total: int) -> str:
        shown = ", ".join(missing[:20])
        if len(missing) > 20:
            shown += f", ... (+{len(missing) - 20} more)"
        return f"{label}: {len(missing)}/{total} not in Contract -> {shown}"

    parts: list[str] = []
    if coverage.missing_modules:
        parts.append(_fmt("modules", coverage.missing_modules, coverage.total_modules))
    if coverage.missing_names:
        parts.append(_fmt("names", coverage.missing_names, coverage.total_names))
    if coverage.missing_dep_targets:
        parts.append(
            _fmt("interface_dependencies", coverage.missing_dep_targets, coverage.total_deps)
        )
    message = (
        "test_usage symbols absent from Interface Contract (under-specified public "
        "interface; fail artifact_consistency and route spec_repair). " + " | ".join(parts)
    )
    return [ObjectiveIssue("warning", "contract-coverage-gap", message, str(contract_path))]


def check_mojibake_paths(paths: list[Path]) -> list[ObjectiveIssue]:
    issues: list[ObjectiveIssue] = []
    for path in paths:
        for msg in check_mojibake(path):
            issues.append(ObjectiveIssue("error", "mojibake", msg, str(path)))
    return issues


def check_json_contracts(
    step_dir: Path,
    *,
    step_num: int,
    milestones_dir: Path,
    require_test_usage: bool = True,
) -> list[ObjectiveIssue]:
    """Validate schema-level JSON contracts for test_usage through step N."""
    issues: list[ObjectiveIssue] = []

    cumulative_dirs = resolve_step_dirs(milestones_dir, up_to_step=step_num)

    if not cumulative_dirs:
        issues.append(ObjectiveIssue(
            "warning", "no-test-usage", f"No test_usage.json through step {step_num}",
            str(step_dir),
        ))

    if not require_test_usage:
        return issues

    for usage_dir in cumulative_dirs:
        usage_path = usage_dir / "test_usage.json"
        if not usage_path.is_file():
            if require_test_usage:
                issues.append(ObjectiveIssue(
                    "error", "missing-file", f"Missing {usage_path}", str(usage_path),
                ))
            continue
        usage, u_load = load_json(usage_path)
        for li in u_load:
            issues.append(ObjectiveIssue(li.severity, li.rule, li.message, str(usage_path)))
        if usage is not None:
            for ci in validate_test_usage(usage):
                issues.append(ObjectiveIssue(
                    ci.severity, ci.rule, ci.message, str(usage_path),
                ))
    return issues


def is_disallowed_dir_name(name: str) -> bool:
    """True when a directory name must not be committed under a milestone step."""
    if name in ASSET_EXCLUDED_DIR_NAMES:
        return True
    if any(pat in name for pat in ASSET_EXPERIMENTAL_DIR_PATTERNS):
        return True
    return any(name.endswith(suffix) for suffix in BUILD_ARTIFACT_DIR_SUFFIXES)


def check_asset_cleanliness(paths: list[Path]) -> list[ObjectiveIssue]:
    """Flag cache, build artifacts, and experimental backup directories (dirs only)."""
    issues: list[ObjectiveIssue] = []
    seen: set[str] = set()
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_dir():
                continue
            if not is_disallowed_dir_name(path.name):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            issues.append(ObjectiveIssue(
                "error",
                "asset-cleanliness",
                f"Disallowed directory under {root}: {rel}",
                str(path),
            ))
    return issues


def agent_visible_paths(case_dir: Path, step_num: int) -> list[Path]:
    """Paths that may be shown to the benchmark agent (PRD, contracts, not judge tests)."""
    public = case_dir / "public"
    paths: list[Path] = []
    if public.is_dir():
        for sub in ("prd", "interface_contracts"):
            p = public / sub
            if p.is_dir():
                paths.extend(discover_text_files(p))
        legacy = public / "Interface_Contract.md"
        if legacy.is_file() and is_scannable_text_file(legacy):
            paths.append(legacy)
    contract = public / "interface_contracts" / f"step_{step_num}.md"
    if contract.is_file():
        paths.append(contract)
    return paths


def public_scannable_paths(case_dir: Path) -> list[Path]:
    """Every public text file that ships with the benchmark — all must be identity-clean.

    Broader than ``agent_visible_paths`` (which only covered ``prd`` + ``interface_contracts``):
    this returns the whole ``public/`` tree so files like ``Hardware_Requirements.md`` are also
    scanned for blacklisted upstream-identity terms. The internal ``source/manifest.json`` and
    the judge-only ``coverage_matrix.json`` are intentionally NOT public and not scanned here.
    """
    public = case_dir / "public"
    return discover_text_files(public) if public.is_dir() else []


# Coverage-matrix filename (judge-only structured artifact; mirrors generate_milestone_code).
COVERAGE_MATRIX_FILENAME = "coverage_matrix.json"


def _manifest_test_basenames(final_dir: Path) -> set[str]:
    """Test files declared in test_manifest.json, by basename, for test-ref cross-checks."""
    tm_data, _ = load_json(final_dir / "test_manifest.json")
    files = tm_data.get("test_files", []) if isinstance(tm_data, dict) else []
    out: set[str] = set()
    for f in files:
        if isinstance(f, str):
            out.add(Path(f).name)
    return out


def check_coverage_matrix(final_dir: Path) -> list[ObjectiveIssue]:
    """F-gate: the judge-only coverage matrix must exist, be valid, and prove core coverage.

    Beyond schema + core-gap semantics, every core capability's ``test_refs`` must point at a
    test file that is actually declared in ``test_manifest.json`` (a test the harness runs).
    """
    issues: list[ObjectiveIssue] = []
    matrix_path = final_dir / COVERAGE_MATRIX_FILENAME
    matrix, load_issues = load_json(matrix_path)
    if matrix is None:
        for li in load_issues:
            issues.append(ObjectiveIssue("error", li.rule, li.message, str(matrix_path)))
        return issues

    for ci in validate_coverage_matrix(matrix):
        if ci.severity == "error":
            issues.append(ObjectiveIssue("error", ci.rule, ci.message, str(matrix_path)))
    # If the schema is broken, the semantic checks below are unreliable.
    if any(i.severity == "error" for i in issues):
        return issues

    for ci in coverage_matrix_core_gaps(matrix):
        issues.append(ObjectiveIssue(ci.severity, ci.rule, ci.message, str(matrix_path)))

    manifest_files = _manifest_test_basenames(final_dir)
    if manifest_files:
        for entry in matrix.get("capabilities", []) or []:
            if not isinstance(entry, dict) or entry.get("priority") != "core":
                continue
            cap_id = entry.get("capability_id", "<unknown>")
            for ref in entry.get("test_refs", []) or []:
                if not isinstance(ref, str):
                    continue
                # Accept "tests/foo.py::case" or "tests/foo.py" — match by file basename.
                file_part = ref.split("::", 1)[0]
                base = Path(file_part).name
                if base and base not in manifest_files:
                    issues.append(ObjectiveIssue(
                        "error", "test-ref-not-in-manifest",
                        f"core capability '{cap_id}' test_ref '{ref}' is not a test_manifest file",
                        str(matrix_path),
                    ))
    return issues


def check_test_usage_consistency(final_dir: Path) -> list[ObjectiveIssue]:
    """Lightweight test_usage.json consistency gate (no new artifact).

    Schema + presence are already validated below; this adds the "not trivially empty" check —
    a benchmark with no declared imports/names is almost always a broken usage handoff.
    """
    issues: list[ObjectiveIssue] = []
    usage_path = final_dir / "test_usage.json"
    usage, _ = load_json(usage_path)
    if usage is None:
        return issues  # the missing/invalid case is reported by the usage block below
    modules = usage.get("modules") or []
    names = usage.get("names") or []
    if not modules and not names:
        issues.append(ObjectiveIssue(
            "error", "empty-usage",
            "test_usage.json declares no modules and no names (broken usage handoff)",
            str(usage_path),
        ))
    return issues


def check_judge_pass_record(final_dir: Path) -> list[ObjectiveIssue]:
    """Repo-final gate: D must deliver ``run_acceptance.sh`` and sidecar metadata.

    Adaptive: the acceptance script + ``run_acceptance_meta.json`` are always required (D's
    hard-execution entry). ``F_BENCHMARK_RESULTS.json`` is produced later by Stage F, so it is
    only validated structurally when present — its absence at E time is not an error.
    """
    from artifact_contracts import (
        F_BENCHMARK_RESULTS_FILENAME,
        RUN_ACCEPTANCE_META_FILENAME,
        RUN_ACCEPTANCE_SCRIPT_NAME,
        load_f_benchmark_results,
        load_run_acceptance_meta,
    )
    issues: list[ObjectiveIssue] = []
    script = final_dir / RUN_ACCEPTANCE_SCRIPT_NAME
    if not script.is_file():
        issues.append(ObjectiveIssue(
            "error", "missing-acceptance-script",
            f"{RUN_ACCEPTANCE_SCRIPT_NAME} not found (repo-final hard execution entry)",
            str(script),
        ))
    meta_path = final_dir / RUN_ACCEPTANCE_META_FILENAME
    if not meta_path.is_file():
        issues.append(ObjectiveIssue(
            "error", "missing-acceptance-meta",
            f"{RUN_ACCEPTANCE_META_FILENAME} not found (orchestrator metadata for acceptance script)",
            str(meta_path),
        ))
    else:
        _data, meta_issues = load_run_acceptance_meta(final_dir)
        for issue in meta_issues:
            if issue.severity == "error":
                issues.append(ObjectiveIssue(
                    "error", issue.rule, issue.message, str(meta_path),
                ))
    f_results_path = final_dir / F_BENCHMARK_RESULTS_FILENAME
    if f_results_path.is_file():
        _f_data, f_issues = load_f_benchmark_results(final_dir)
        for issue in f_issues:
            if issue.severity == "error":
                issues.append(ObjectiveIssue(
                    "error", issue.rule, issue.message, str(f_results_path),
                ))
    return issues


def judge_visible_paths(case_dir: Path, step_num: int) -> list[Path]:
    """Judge-visible artifacts for the step (tests, manifests — internal audit only)."""
    step_dir = case_dir / "milestones" / f"step_{step_num}"
    roots = [step_dir / "tests", step_dir]
    files: list[Path] = []
    for root in roots:
        files.extend(discover_text_files(root))
    for name in ("test_manifest.json", "test_usage.json", "provenance.json"):
        p = step_dir / name
        if p.is_file():
            files.append(p)
    return sorted(set(files))


def run_objective_gates(
    case_dir: Path,
    step_num: int,
    blacklist: list[str],
    *,
    require_test_usage: bool = True,
    leak_judge: LeakJudge | None = None,
) -> list[ObjectiveIssue]:
    """Run all language-agnostic objective gates for one milestone step."""
    case_dir = Path(case_dir)
    milestones_dir = case_dir / "milestones"
    step_dir = milestones_dir / f"step_{step_num}"

    agent_text = agent_visible_paths(case_dir, step_num)
    judge_text = judge_visible_paths(case_dir, step_num)
    all_text = sorted(set(agent_text) | set(judge_text))

    issues: list[ObjectiveIssue] = []
    issues.extend(scan_sensitive_terms(agent_text, blacklist, leak_judge=leak_judge))
    issues.extend(scan_test_reference_leakage(
        agent_text, _manifest_test_basenames(step_dir),
    ))
    issues.extend(check_mojibake_paths(all_text))
    issues.extend(check_json_contracts(
        step_dir, step_num=step_num, milestones_dir=milestones_dir,
        require_test_usage=require_test_usage,
    ))
    issues.extend(check_asset_cleanliness([step_dir, case_dir / "public"]))
    return issues


# Harness-only cache dirs (runner byte-code / pytest state). Safe to delete before gate
# scans; distinct from build/dist/node_modules which may indicate real deliverable issues.
FINAL_RUNNER_CACHE_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
})


def cleanup_final_runner_caches(root: Path) -> None:
    """Remove harness runner caches under a milestone deliverable before gate scans.

    D/Contract/review stages may execute or import Python tests/modules and leave
    ``__pycache__`` / ``.pytest_cache`` anywhere under ``milestones/final``. These
    are never deliverable defects; strip them immediately before objective gates run.
    """
    root = Path(root)
    if not root.is_dir():
        return
    for cache in list(root.rglob("*")):
        if cache.is_dir() and cache.name in FINAL_RUNNER_CACHE_DIR_NAMES:
            shutil.rmtree(cache, ignore_errors=True)


def run_final_objective_gates(
    case_dir: Path,
    blacklist: list[str],
    *,
    require_test_usage: bool = True,
    leak_judge: LeakJudge | None = None,
) -> list[ObjectiveIssue]:
    """Run language-agnostic objective gates for ``milestones/final`` acceptance."""
    case_dir = Path(case_dir)
    final_dir = case_dir / "milestones" / FINAL_ACCEPTANCE_DIR_NAME
    if not final_dir.is_dir():
        return [ObjectiveIssue(
            "error", "missing-final", "milestones/final directory not found", str(final_dir),
        )]

    # Public scan now covers the WHOLE public/ tree (PRD, contracts, Hardware_Requirements.md,
    # ...), not just prd + interface_contracts — that gap is why Hardware_Requirements.md
    # leakage previously slipped through.
    public_text = public_scannable_paths(case_dir)
    judge_text = list(public_text)
    tests_dir = final_dir / "tests"
    if tests_dir.is_dir():
        judge_text.extend(discover_text_files(tests_dir))
    for name in ("test_manifest.json", "test_usage.json", "review_verdict.json"):
        p = final_dir / name
        if p.is_file() and is_scannable_text_file(p):
            judge_text.append(p)
    all_text = sorted(set(public_text) | set(judge_text))

    issues: list[ObjectiveIssue] = []
    issues.extend(scan_sensitive_terms(public_text, blacklist, leak_judge=leak_judge))
    issues.extend(scan_test_reference_leakage(
        public_text, _manifest_test_basenames(final_dir),
    ))
    issues.extend(check_contract_coverage(case_dir, final_dir))
    issues.extend(check_mojibake_paths(all_text))
    issues.extend(check_coverage_matrix(final_dir))
    issues.extend(check_judge_pass_record(final_dir))
    if require_test_usage:
        issues.extend(check_test_usage_consistency(final_dir))

    tm_path = final_dir / "test_manifest.json"
    tm_data, _ = load_json(tm_path)
    if tm_data is None:
        issues.append(ObjectiveIssue(
            "error", "missing-manifest", "test_manifest.json missing under milestones/final",
            str(tm_path),
        ))
    else:
        for issue in validate_test_manifest(tm_data, final_dir):
            if issue.severity == "error":
                issues.append(ObjectiveIssue(
                    "error", issue.rule, issue.message, str(tm_path),
                ))

    usage_path = final_dir / "test_usage.json"
    if require_test_usage:
        usage_data, _ = load_json(usage_path)
        if usage_data is None:
            issues.append(ObjectiveIssue(
                "error", "missing-usage", "test_usage.json missing under milestones/final",
                str(usage_path),
            ))
        else:
            for issue in validate_test_usage(usage_data):
                if issue.severity == "error":
                    issues.append(ObjectiveIssue(
                        "error", issue.rule, issue.message, str(usage_path),
                    ))

    issues.extend(check_asset_cleanliness([final_dir, case_dir / "public"]))

    manifest_path = case_dir / "source" / "manifest.json"
    manifest_data, _ = load_json(manifest_path)
    if isinstance(manifest_data, dict):
        runner = manifest_data.get("runner")
        if isinstance(runner, dict):
            from runner_command_contract import check_runner_command_context_contract

            for ci in check_runner_command_context_contract(runner):
                issues.append(ObjectiveIssue(
                    ci.severity, ci.rule, ci.message, str(manifest_path),
                ))

    return issues


def run_final_objective_gates_after_cache_cleanup(
    case_dir: Path,
    blacklist: list[str],
    *,
    require_test_usage: bool = True,
    leak_judge: LeakJudge | None = None,
) -> list[ObjectiveIssue]:
    """Run final objective gates after stripping harness runner caches."""
    case_dir = Path(case_dir)
    final_dir = case_dir / "milestones" / FINAL_ACCEPTANCE_DIR_NAME
    cleanup_final_runner_caches(final_dir)
    return run_final_objective_gates(
        case_dir,
        blacklist,
        require_test_usage=require_test_usage,
        leak_judge=leak_judge,
    )


def objective_gates_pass(issues: list[ObjectiveIssue]) -> bool:
    return not any(i.severity == "error" for i in issues)


def format_issues_report(issues: list[ObjectiveIssue]) -> str:
    if not issues:
        return "No objective gate issues."
    lines = []
    for issue in issues:
        loc = f"{issue.path}: " if issue.path else ""
        lines.append(f"[{issue.severity.upper()}] {issue.rule}: {loc}{issue.message}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run language-agnostic objective gates for a step")
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--final", action="store_true",
                        help="Run objective gates for milestones/final acceptance")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    manifest_path = args.case_dir / "source" / "manifest.json"
    blacklist: list[str] = []
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            blacklist = manifest.get("sensitive_terms", []) or []
        except json.JSONDecodeError:
            pass

    from identity_leak_judge import make_leak_judge

    env = dict(os.environ)
    leak_judge = make_leak_judge(env, args.case_dir, scope_label="objective-gates-cli")

    if args.final:
        issues = run_final_objective_gates_after_cache_cleanup(
            args.case_dir, blacklist, leak_judge=leak_judge,
        )
    elif args.step is not None:
        issues = run_objective_gates(
            args.case_dir, args.step, blacklist, leak_judge=leak_judge,
        )
    else:
        print("Specify --step N or --final", file=sys.stderr)
        sys.exit(2)

    if args.json_output:
        print(json.dumps([
            {"severity": i.severity, "rule": i.rule, "message": i.message, "path": i.path}
            for i in issues
        ], indent=2))
    else:
        print(format_issues_report(issues))

    if not objective_gates_pass(issues):
        sys.exit(1)


if __name__ == "__main__":
    main()
