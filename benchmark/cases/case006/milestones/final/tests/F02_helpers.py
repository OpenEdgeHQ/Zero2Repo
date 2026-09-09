# feature: F02
"""F02 helpers. Names here are F02-only.

Sealed F01 already exports ``_word``, ``_greeting``, ``_dispatch``, and
``_leaf``. This module must not redefine those names; ``F01_helpers.py``
is not on disk, so F02 scaffolding uses new names instead of a predecessor
import. ``_run_python_on_sized_tty`` stays here because sealed
``_helpers.run_python_on_tty`` does not set a window size.
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
import uuid
from typing import Any

from optlyn import command

from _harness import DEFAULT_TIMEOUT, RunResult, invoke, workspace

_HELP_PROG = "app"


def _help_ident() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _help_hi() -> str:
    return f"GREET:{uuid.uuid4().hex}:"


def _help_run(cli: Any, args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("prog_name", _HELP_PROG)
    return invoke(cli, args, **kwargs)


def _help_leaf(greeting: str, *, doc: str | None = None, **command_kwargs: Any) -> Any:
    def callback() -> None:
        print(greeting, flush=True)

    callback.__name__ = f"{_help_ident()}_{_help_ident()}"
    if doc is not None:
        callback.__doc__ = doc
    return command(**command_kwargs)(callback)


def _run_python_on_sized_tty(
    code: str, columns: int, *, timeout: float = DEFAULT_TIMEOUT
) -> RunResult:
    """Run *code* on a pty whose window width is *columns*.

    Opening the pty, setting the window size, or starting the child raises.
    A missing pty is not mapped to an 80-column fallback.
    """
    if not code:
        raise ValueError("code must be a non-empty string")
    if columns < 1:
        raise ValueError(f"columns must be a positive width, got {columns!r}")
    python = sys.executable
    if not python:
        raise RuntimeError("sys.executable is empty; cannot spawn an interpreter")
    try:
        master, slave = pty.openpty()
    except OSError as exc:
        raise RuntimeError(f"failed to open a pty: {exc}") from exc

    winsize = struct.pack("HHHH", 24, columns, 0, 0)
    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, winsize)
        fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
    except OSError as exc:
        os.close(master)
        os.close(slave)
        raise RuntimeError(
            f"failed to set pty window size to {columns} columns: {exc}"
        ) from exc

    argv = (python, "-c", code)
    with workspace() as ws:
        env = dict(ws.env)
        env["PYTHONUNBUFFERED"] = "1"
        try:
            proc = subprocess.Popen(
                list(argv),
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=str(ws.path),
                env=env,
                close_fds=True,
            )
        except Exception as exc:
            os.close(master)
            os.close(slave)
            raise RuntimeError(f"failed to start sized-tty child: {exc}") from exc
        os.close(slave)
        chunks: list[bytes] = []
        deadline = time.monotonic() + timeout

        def _read_ready() -> bytes | None:
            try:
                data = os.read(master, 4096)
            except OSError:
                return None
            return data

        try:
            while True:
                if time.monotonic() > deadline:
                    proc.kill()
                    proc.wait()
                    raise RuntimeError("sized-tty child timed out")
                finished = proc.poll() is not None
                wait = 0.05 if finished else 0.2
                ready, _, _ = select.select([master], [], [], wait)
                if ready:
                    data = _read_ready()
                    if not data:
                        break
                    chunks.append(data)
                elif finished:
                    break
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            os.close(master)
        if proc.returncode is None:
            raise RuntimeError("sized-tty child ended without a return code")
        raw = b"".join(chunks)
        return RunResult(
            returncode=proc.returncode,
            stdout=raw,
            stderr=b"",
            argv=argv,
            cwd=str(ws.path),
        )
