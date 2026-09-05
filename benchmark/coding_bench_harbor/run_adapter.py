"""CLI: build Harbor tasks from zero2repo cases.

Examples
--------
Build one case:

    zero2repo-harbor --case-id case027

Build every case under the cases root into a dataset directory:

    zero2repo-harbor --all --force

``coding-bench-harbor`` remains an alias for the same entry point.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adapter import AdapterError, build_task, iter_benchmark_case_dirs

# benchmark/ lives next to cases/ in the repo; default to the sibling directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _default_cases_root() -> Path:
    bench_cases = _REPO_ROOT / "benchmark" / "cases"
    if bench_cases.is_dir():
        return bench_cases
    return _REPO_ROOT / "cases"


_DEFAULT_CASES_ROOT = _default_cases_root()
_DEFAULT_OUT = Path(__file__).resolve().parent.parent / "output"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="zero2repo-harbor",
        description="Convert zero2repo cases into Harbor (terminal-bench 2.0) tasks.",
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--case-id", help="Single case id to build (directory name under --cases-root).")
    selection.add_argument(
        "--all",
        action="store_true",
        help="Build every case under --cases-root that has source/manifest.json.",
    )

    parser.add_argument("--cases-root", type=Path, default=_DEFAULT_CASES_ROOT, help=f"Directory holding case folders (default: {_DEFAULT_CASES_ROOT}).")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help=f"Output dataset directory (default: {_DEFAULT_OUT}).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing task directories.")
    parser.add_argument("--allow-leakage", action="store_true", help="Warn instead of failing when the PRD contains blacklisted terms.")
    parser.add_argument("--difficulty", default="medium", help="Difficulty label written to task.toml metadata.")
    parser.add_argument("--agent-timeout-sec", type=float, default=7200.0)
    parser.add_argument("--verifier-timeout-sec", type=float, default=600.0)
    return parser.parse_args(argv)


def _iter_case_dirs(cases_root: Path, case_id: str | None, build_all: bool) -> list[Path]:
    if not cases_root.is_dir():
        raise AdapterError(f"Cases root not found: {cases_root}")
    if build_all:
        dirs = iter_benchmark_case_dirs(cases_root)
        if not dirs:
            raise AdapterError(f"No cases with source/manifest.json under {cases_root}")
        return dirs
    case_dir = cases_root / case_id
    if not case_dir.is_dir():
        raise AdapterError(f"Case not found: {case_dir}")
    return [case_dir]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    try:
        case_dirs = _iter_case_dirs(args.cases_root, args.case_id, args.all)
    except AdapterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not case_dirs:
        print(f"error: no cases found under {args.cases_root}", file=sys.stderr)
        return 2

    failures = 0
    for case_dir in case_dirs:
        try:
            task_dir = build_task(
                case_dir,
                args.out,
                allow_leakage=args.allow_leakage,
                force=args.force,
                difficulty=args.difficulty,
                agent_timeout_sec=args.agent_timeout_sec,
                verifier_timeout_sec=args.verifier_timeout_sec,
            )
            print(f"built {case_dir.name} -> {task_dir}")
        except AdapterError as exc:
            failures += 1
            print(f"FAILED {case_dir.name}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
