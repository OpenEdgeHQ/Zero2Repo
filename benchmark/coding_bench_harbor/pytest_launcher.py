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


def _import_ban_roots() -> list[str]:
    raw = os.environ.get("CODING_BENCH_IMPORT_BAN", "") or ""
    roots: list[str] = []
    seen: set[str] = set()
    for part in raw.replace("\n", ",").replace(":", ",").split(","):
        name = part.strip().rstrip("/")
        if not name or name in seen:
            continue
        seen.add(name)
        roots.append(name)
    return roots


def _importer_under_workspace(workspace: Path) -> bool:
    frame = sys._getframe(1)
    here = Path(__file__).resolve()
    while frame is not None:
        filename = frame.f_code.co_filename
        frame = frame.f_back
        if not filename or filename.startswith("<"):
            continue
        try:
            path = Path(filename).resolve()
        except OSError:
            continue
        if path == here:
            continue
        if _under_workspace(path, workspace):
            return True
    return False


class _WorkspaceImportBan:
    """Block banned roots only when the importer lives in the candidate tree.

    Hidden tests under ``/tests/final`` may still import the root.
    """

    def __init__(self, banned: list[str], workspace: Path) -> None:
        self.banned = {name.split(".", 1)[0] for name in banned if name}
        self.workspace = workspace

    def find_spec(self, fullname, path, target=None):  # noqa: ANN001
        del path, target
        root = str(fullname).split(".", 1)[0]
        if root not in self.banned:
            return None
        if _importer_under_workspace(self.workspace):
            raise ImportError(
                f"CODING_BENCH_IMPORT_BAN: workspace import of {fullname!r} "
                "is not allowed"
            )
        return None


def _install_import_ban(workspace: Path) -> None:
    banned = _import_ban_roots()
    if not banned:
        return
    sys.meta_path.insert(0, _WorkspaceImportBan(banned, workspace))


def _side_effect_bans() -> set[str]:
    raw = os.environ.get("CODING_BENCH_JUDGE_BANS", "") or ""
    return {part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()}


def _install_side_effect_ban(workspace: Path) -> None:
    """Block declared side effects when the caller lives in the candidate tree."""
    bans = _side_effect_bans()
    if not bans:
        return
    busy = False

    def _hook(event: str, args: tuple) -> None:  # noqa: ARG001
        nonlocal busy
        if busy:
            return
        busy = True
        try:
            _side_effect_hook(event, args, workspace, bans)
        finally:
            busy = False

    sys.addaudithook(_hook)


def _side_effect_hook(event: str, args: tuple, workspace: Path, bans: set[str]) -> None:
    if not _importer_under_workspace(workspace):
        return
    if "socket" in bans and event.startswith("socket."):
        raise RuntimeError("CODING_BENCH_JUDGE_BANS: workspace socket use is not allowed")
    if "network" in bans and event.startswith("socket."):
        raise RuntimeError("CODING_BENCH_JUDGE_BANS: workspace network use is not allowed")
    if "subprocess" in bans and event in {"subprocess.Popen", "os.system"}:
        raise RuntimeError("CODING_BENCH_JUDGE_BANS: workspace subprocess use is not allowed")
    if "filesystem_outside_workspace" in bans and event == "open":
        path, mode = (args + ("",))[:2]
        text = str(path)
        if any(flag in str(mode) for flag in ("w", "a", "x", "+")):
            try:
                resolved = Path(text).resolve()
            except OSError:
                return
            if not _under_workspace(resolved, workspace):
                raise RuntimeError(
                    "CODING_BENCH_JUDGE_BANS: workspace write outside /app is not allowed"
                )


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

    _install_import_ban(workspace)
    _install_side_effect_ban(workspace)

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
