#!/usr/bin/env python3
"""Trusted pytest entry for the zero2repo judge.

Started with ``python3 -I`` so cwd, PYTHONPATH, and user site cannot supply
the pytest module. Product paths are added only after a workspace-owned
pytest file has been rejected.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _under_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
        return True
    except (OSError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    workspace = Path(os.environ.get("CODING_BENCH_WORKSPACE", "/app"))
    tests_final = Path(os.environ.get("CODING_BENCH_TESTS_FINAL", "/tests/final"))

    import pytest

    pytest_file = Path(getattr(pytest, "__file__", "") or "")
    if not pytest_file.is_file() or _under_workspace(pytest_file, workspace):
        print(
            f"JUDGE ERROR: pytest resolved under the candidate workspace "
            f"({pytest_file})",
            file=sys.stderr,
        )
        return 2

    for raw in os.environ.get("CODING_BENCH_PRODUCT_PATHS", "").split(":"):
        if raw:
            sys.path.insert(0, raw)

    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    cache = Path("/tmp/cb-pytest-cache")
    cache.mkdir(parents=True, exist_ok=True)
    args = [
        f"--rootdir={tests_final}",
        "-c", os.devnull,
        "-o", f"cache_dir={cache}",
        *(argv if argv is not None else sys.argv[1:]),
    ]
    os.chdir(workspace)
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
