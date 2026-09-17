#!/usr/bin/env python3
"""Batch-rejudge every ``cases/<case>/controls/<name>/`` workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1] / "benchmark"
sys.path.insert(0, str(BENCHMARK_ROOT))

from cbrun.rejudge import iter_controls, main as rejudge_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rejudge negative-control workspaces.")
    parser.add_argument("--cases-root", type=Path, default=BENCHMARK_ROOT / "cases")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, default=BENCHMARK_ROOT / ".cbrun_cache")
    parser.add_argument("--dry-run", action="store_true", help="List controls only.")
    parser.add_argument(
        "--image",
        default=None,
        help="Passed through to rejudge; must be given with --tests-dir.",
    )
    parser.add_argument(
        "--tests-dir",
        type=Path,
        default=None,
        help="Passed through to rejudge; must be given with --image.",
    )
    args = parser.parse_args(argv)

    if args.out.exists() and not args.dry_run:
        print(f"error: output directory already exists: {args.out}", flush=True)
        return 2
    if not args.dry_run:
        args.out.mkdir(parents=True, exist_ok=False)

    rows = []
    failed = 0
    for case_id, name, control_dir, expect in iter_controls(args.cases_root):
        workspace = control_dir / "app"
        row = {
            "case_id": case_id,
            "control": name,
            "expect_reward": expect,
            "workspace": str(workspace if workspace.is_dir() else control_dir),
        }
        if args.dry_run:
            row["status"] = "listed"
            rows.append(row)
            print(f"{case_id}/{name} expect={expect}")
            continue
        if not workspace.is_dir():
            row["status"] = "skipped_missing_app"
            rows.append(row)
            print(f"{case_id}/{name}: skip (no app/)")
            continue
        dest = args.out / case_id / name
        argv = [
            "--case",
            case_id,
            "--workspace",
            str(workspace),
            "--cases-root",
            str(args.cases_root),
            "--out",
            str(dest),
            "--cache-root",
            str(args.cache_root),
            "--expect-reward",
            str(int(expect)),
        ]
        if args.image is not None:
            argv.extend(["--image", args.image])
        if args.tests_dir is not None:
            argv.extend(["--tests-dir", str(args.tests_dir)])
        code = rejudge_main(argv)
        row["status"] = "ok" if code == 0 else "fail"
        row["exit_code"] = code
        if code != 0:
            failed += 1
        rows.append(row)
        print(f"{case_id}/{name}: {row['status']}")

    if not args.dry_run:
        (args.out / "controls_summary.json").write_text(
            json.dumps({"failed": failed, "rows": rows}, indent=2) + "\n",
            encoding="utf-8",
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
