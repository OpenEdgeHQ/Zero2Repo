# feature: F00
"""Shared machinery for driving the product through its public surface.

Suites import from this module (``from _harness import ...``). Importing it
performs no I/O, starts no processes, and opens no sockets. Stream capture,
environment replacement, and cwd changes happen only when a caller invokes
a function or enters a context manager below.

The product is an importable Python library. Authors declare commands with
its public decorators and classes, then invoke the resulting command as a
program. This module is the one canonical way to do that in-process, and
to spawn the same interpreter when a real child process is required
(locale, completion variable, script-as-program).

Surfaces
--------
* In-process program invocation — call the command's public ``main``
  entry with caller-controlled argument tokens, stdin, environment,
  working directory, and context-constructor extras. Standalone mode
  (the default) is the "run as a program" path: usage and abort failures
  become an exit status rather than a raised exception.
* Child interpreter — ``run_python`` / ``run_command`` for observations
  that require a separate process (an ASCII-only environment encoding,
  a completion instruction in the process environment, or a script that
  is started the way an installed console script is started).

The product's own in-process test runner is a feature of the product
(FP-14), not of this harness. Suites that need to exercise that runner
import it from the package's testing submodule. Every other suite should
go through :func:`invoke` so a hollow test-runner cannot collect a pass
for parser, help, or dispatch behaviour.

A product non-zero exit or a raised product exception recorded on
:class:`InvokeResult` is a classified outcome, not a harness failure.
Observation failures this module cannot classify raise :class:`HarnessError`.
"""

from __future__ import annotations

import getpass
import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any, Iterator, Mapping, Sequence
from warnings import WarningMessage

# ---------------------------------------------------------------------------
# Public defaults
# ---------------------------------------------------------------------------

DEFAULT_CHARSET = "utf-8"
DEFAULT_TIMEOUT = 30.0
DEFAULT_PROG_NAME = "cli"

# Isolated child / in-process environments start from this Unicode locale
# so a successful run is distinguishable from the ASCII-encoding abort.
_DEFAULT_LOCALE = "C.UTF-8"

# Substrate keys copied from the caller when building an isolated env.
# Everything else is dropped so an option's environment source cannot be
# filled by an incidental parent variable.
_KEEP_ENV_KEYS = (
    "PATH",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSAFEPATH",
    "PYTHONNOUSERSITE",
    "PYTHONHASHSEED",
    "PYTHONUNBUFFERED",
    "PYTHONWARNINGS",
    "PYTHONDONTWRITEBYTECODE",
    "TMPDIR",
    "TEMP",
    "TMP",
    "TZ",
    "USER",
    "LOGNAME",
    "USERNAME",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TERM",
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
)

# TTY / pager / editor / color side-channels stripped even if kept above.
_ISOLATE_UNSET = (
    "COLUMNS",
    "LINES",
    "PAGER",
    "EDITOR",
    "VISUAL",
    "BROWSER",
    "NO_COLOR",
    "FORCE_COLOR",
    "CLICOLOR",
    "CLICOLOR_FORCE",
    "HTMLPAGER",
    "LESS",
    "MORE",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "DBUS_SESSION_BUS_ADDRESS",
)


# ---------------------------------------------------------------------------
# Errors / result types
# ---------------------------------------------------------------------------


class HarnessError(RuntimeError):
    """Raised when an observation cannot be classified.

    Used for missing substrate, a path that escapes its workspace, a
    command object without a public ``main`` entry, and I/O failures that
    are not a documented product outcome. Never used to mean "the product
    returned a non-zero exit the PRD describes".
    """


@dataclass(frozen=True)
class InvokeResult:
    """Outcome of one in-process command invocation.

    Attributes:
        exit_code: Process-style status. In standalone mode this is the
            ``SystemExit`` code (``None`` treated as 0). In non-standalone
            mode this is 0 when ``main`` returned, or 1 when an exception
            was captured; the callback's return value is in
            ``return_value`` and is not reinterpreted as a status.
        stdout: Raw standard output bytes.
        stderr: Raw standard error bytes.
        output: Stdout and stderr bytes in write order (what a terminal
            user would see if both streams were mixed).
        return_value: Whatever ``main`` returned. ``None`` in standalone
            mode after a ``SystemExit``.
        exception: The exception that ended the invocation, if any
            (including ``SystemExit`` when the status is non-zero).
        exc_info: ``sys.exc_info()`` triple matching ``exception``, or
            ``None``.
        args: Argument tokens passed to ``main``.
        cwd: Working directory used for the call, as a string.
        warnings: Warning records captured for the duration of the call.
            Empty when none were emitted — never ``None``.
    """

    exit_code: int
    stdout: bytes
    stderr: bytes
    output: bytes
    return_value: Any
    exception: BaseException | None
    exc_info: tuple[type[BaseException], BaseException, TracebackType] | None
    args: tuple[str, ...]
    cwd: str
    warnings: tuple[WarningMessage, ...] = field(default_factory=tuple)

    @property
    def stdout_text(self) -> str:
        """Stdout decoded as UTF-8; undecodable bytes are replaced."""
        return self.stdout.decode(DEFAULT_CHARSET, errors="replace").replace(
            "\r\n", "\n"
        )

    @property
    def stderr_text(self) -> str:
        """Stderr decoded as UTF-8; undecodable bytes are replaced."""
        return self.stderr.decode(DEFAULT_CHARSET, errors="replace").replace(
            "\r\n", "\n"
        )

    @property
    def output_text(self) -> str:
        """Mixed stdout+stderr decoded as UTF-8; undecodable bytes replaced."""
        return self.output.decode(DEFAULT_CHARSET, errors="replace").replace(
            "\r\n", "\n"
        )


@dataclass(frozen=True)
class RunResult:
    """Outcome of one subprocess invocation.

    Attributes:
        returncode: Process exit status. The harness does not interpret it.
        stdout: Raw standard output bytes.
        stderr: Raw standard error bytes.
        argv: Exact argument vector that was executed.
        cwd: Working directory used for the process, as a string.
    """

    returncode: int
    stdout: bytes
    stderr: bytes
    argv: tuple[str, ...]
    cwd: str

    @property
    def stdout_text(self) -> str:
        """Stdout decoded as UTF-8; undecodable bytes are replaced."""
        return self.stdout.decode(DEFAULT_CHARSET, errors="replace")

    @property
    def stderr_text(self) -> str:
        """Stderr decoded as UTF-8; undecodable bytes are replaced."""
        return self.stderr.decode(DEFAULT_CHARSET, errors="replace")


@dataclass
class Workspace:
    """Ephemeral work directory plus the isolated environment bound to it.

    ``path`` is the working directory for invokes. ``home`` is used as
    ``HOME`` (and the XDG roots live under it) so ``~`` expansion and
    application-config lookup cannot see the caller's home. Both trees
    are removed when the allocating context exits.
    """

    path: Path
    home: Path
    env: dict[str, str]

    def resolve(self, relpath: str | Path) -> Path:
        """Return *relpath* resolved under this workspace.

        Raises:
            HarnessError: when the resolved path escapes the workspace.
        """
        base = self.path.resolve()
        target = (base / relpath).resolve()
        if not _is_relative_to(target, base):
            raise HarnessError(f"path {relpath!r} escapes workspace {base}")
        return target

    def write(
        self,
        relpath: str | Path,
        content: str | bytes,
        *,
        encoding: str = DEFAULT_CHARSET,
    ) -> Path:
        """Write *content* under this workspace, creating parents.

        Returns the absolute path written. Raises ``OSError`` on I/O
        failure and :class:`HarnessError` if *relpath* escapes the
        workspace.
        """
        dest = self.resolve(relpath)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            dest.write_bytes(content)
        else:
            dest.write_text(content, encoding=encoding)
        return dest

    def read(self, relpath: str | Path, *, encoding: str = DEFAULT_CHARSET) -> str:
        """Read a UTF-8 text file under this workspace.

        Raises:
            HarnessError: if *relpath* escapes the workspace, or if the
                path exists but is not a regular file.
            FileNotFoundError: if the file does not exist — never returns
                an empty string or ``None`` to mean "missing".
            OSError: on other I/O failures.
        """
        return read_file(self.resolve(relpath), encoding=encoding)

    def read_bytes(self, relpath: str | Path) -> bytes:
        """Read a binary file under this workspace.

        Raises ``FileNotFoundError`` if the file does not exist — never
        returns empty bytes to mean "missing". Raises :class:`HarnessError`
        if the path exists but is not a regular file.
        """
        return read_bytes(self.resolve(relpath))

    def invoke(
        self,
        cli: Any,
        args: Sequence[str] | str | None = None,
        *,
        stdin: str | bytes | None = None,
        env: Mapping[str, str | None] | None = None,
        standalone_mode: bool = True,
        catch_exceptions: bool | None = None,
        echo_stdin: bool = False,
        charset: str = DEFAULT_CHARSET,
        prog_name: str | None = None,
        **extra: Any,
    ) -> InvokeResult:
        """Invoke *cli* with this workspace as cwd and environment.

        *env* values override :attr:`env` (``None`` unsets). Does not
        raise on a product non-zero exit.
        """
        merged = _apply_updates(self.env, env)
        return invoke(
            cli,
            args,
            stdin=stdin,
            env=merged,
            cwd=self.path,
            isolate=False,
            standalone_mode=standalone_mode,
            catch_exceptions=catch_exceptions,
            echo_stdin=echo_stdin,
            charset=charset,
            prog_name=prog_name,
            **extra,
        )

    def run_command(
        self,
        argv: Sequence[str],
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
    ) -> RunResult:
        """Run *argv* with this workspace as cwd and environment.

        Does not raise on a non-zero child exit.
        """
        merged = _apply_updates(self.env, env)
        return run_command(
            argv,
            cwd=cwd if cwd is not None else self.path,
            env=merged,
            stdin=stdin,
            timeout=timeout,
        )

    def run_python(
        self,
        *,
        code: str | None = None,
        argv: Sequence[str] | None = None,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
    ) -> RunResult:
        """Run this process's interpreter with this workspace as cwd/env."""
        merged = _apply_updates(self.env, env)
        return run_python(
            code=code,
            argv=argv,
            cwd=cwd if cwd is not None else self.path,
            env=merged,
            stdin=stdin,
            timeout=timeout,
            isolate=False,
        )


# ---------------------------------------------------------------------------
# Stream helpers (capture only; not a product test-runner)
# ---------------------------------------------------------------------------


class _BytesIOCopy(io.BytesIO):
    """BytesIO that mirrors every write into another buffer."""

    def __init__(self, copy_to: io.BytesIO) -> None:
        super().__init__()
        self.copy_to = copy_to

    def write(self, b: Any) -> int:
        self.copy_to.write(b)
        return super().write(b)

    def flush(self) -> None:
        super().flush()
        self.copy_to.flush()


class _KeepOpenTextIO(io.TextIOWrapper):
    """TextIOWrapper that does not close its underlying buffer."""

    def close(self) -> None:
        try:
            self.flush()
        except Exception:
            pass


class _EchoingStdin:
    """Binary stdin wrapper that copies every read into an output buffer.

    Unknown attributes delegate to the wrapped ``BytesIO`` so this object
    remains a valid buffer for ``TextIOWrapper``.
    """

    def __init__(self, source: io.BytesIO, output: io.BytesIO) -> None:
        self._source = source
        self._output = output

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)

    def read(self, n: int = -1) -> bytes:
        data = self._source.read(n)
        self._output.write(data)
        return data

    def read1(self, n: int = -1) -> bytes:
        data = self._source.read(n)
        self._output.write(data)
        return data

    def readline(self, n: int = -1) -> bytes:
        data = self._source.readline(n)
        self._output.write(data)
        return data

    def readlines(self, hint: int = -1) -> list[bytes]:
        lines = self._source.readlines(hint)
        for line in lines:
            self._output.write(line)
        return lines

    def __iter__(self) -> Iterator[bytes]:
        for line in self._source:
            self._output.write(line)
            yield line


def _read_hidden_from_stdin(prompt: str = "") -> str:
    """Stand-in for ``getpass.getpass`` that reads the harness stdin.

    A real ``getpass`` opens ``/dev/tty`` and would hang or leak keystrokes
    into the host terminal. This helper is isolation, not a product patch:
    it does not touch the library under test. Hidden input is not echoed.
    An exhausted stdin raises ``EOFError`` — the same class ``getpass``
    and ``input`` raise — so the product can classify it as abort.
    """
    stream = sys.stderr
    stream.write(prompt)
    stream.flush()
    line = sys.stdin.readline()
    if line == "":
        raise EOFError("EOF when reading hidden input")
    return line.rstrip("\r\n")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _apply_updates(
    env: Mapping[str, str],
    updates: Mapping[str, str | None] | None,
) -> dict[str, str]:
    merged = dict(env)
    if updates:
        for key, value in updates.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = str(value)
    return merged


def _normalize_args(args: Sequence[str] | str | None) -> tuple[str, ...]:
    if args is None:
        return ()
    if isinstance(args, str):
        return tuple(shlex.split(args))
    return tuple(str(a) for a in args)


def _read_regular_file(src: Path) -> None:
    """Raise a classified error when *src* is missing or not a regular file."""
    try:
        if not src.exists():
            raise FileNotFoundError(f"file does not exist: {src}")
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
    except FileNotFoundError:
        raise
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat {src}: {exc}") from exc


def _exit_code_from_system_exit(exc: SystemExit) -> int:
    code = exc.code
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    sys.stdout.write(str(code))
    sys.stdout.write("\n")
    return 1


def _require_main(cli: Any) -> Any:
    main = getattr(cli, "main", None)
    if not callable(main):
        raise HarnessError(
            "invoke target has no callable public main entry; "
            f"got {type(cli)!r}"
        )
    return main


# ---------------------------------------------------------------------------
# Paths / discovery
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Return the built repository root.

    Tests run with the repository root as the pytest process cwd. Returns
    ``Path.cwd()`` resolved; does not search the filesystem.
    """
    return Path.cwd().resolve()


def product_src_dir(*, root: Path | None = None) -> Path:
    """Return the importable ``src`` directory of the built repository.

    Raises:
        FileNotFoundError: when ``<root>/src`` is not a directory. That is
            a substrate gap, not a product-behavior judgment.
    """
    base = root if root is not None else repo_root()
    src = (Path(base) / "src").resolve()
    if not src.is_dir():
        raise FileNotFoundError(
            f"product src directory not found at {src}; "
            "the runner must expose the package on PYTHONPATH=src"
        )
    return src


# ---------------------------------------------------------------------------
# Environment / workspace isolation
# ---------------------------------------------------------------------------


def isolated_environ(
    home: Path | str,
    *,
    updates: Mapping[str, str | None] | None = None,
    base: Mapping[str, str] | None = None,
    root: Path | None = None,
) -> dict[str, str]:
    """Build an environment that does not inherit the caller's extras.

    Copies a whitelist of substrate keys from *base* (or ``os.environ``),
    points ``HOME`` and the XDG dirs at *home*, prepends the product
    ``src/`` directory to ``PYTHONPATH``, unsets pager/editor/color
    side-channels, sets a Unicode locale, and applies *updates* last
    (``None`` unsets). Does not mutate ``os.environ``.

    Returns a new ``dict``.
    """
    home_path = Path(home).resolve()
    cfg_dir = home_path / ".config"
    cache_dir = home_path / ".cache"
    data_dir = home_path / ".local" / "share"
    state_dir = home_path / ".local" / "state"
    for directory in (home_path, cfg_dir, cache_dir, data_dir, state_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source = base if base is not None else os.environ
    env: dict[str, str] = {}
    for key in _KEEP_ENV_KEYS:
        value = source.get(key)
        if value is not None:
            env[key] = value
    for key in _ISOLATE_UNSET:
        env.pop(key, None)

    try:
        src = product_src_dir(root=root)
    except FileNotFoundError:
        src = None
    if src is not None:
        existing = env.get("PYTHONPATH", "")
        parts = [str(src)]
        if existing:
            parts.extend(
                part
                for part in existing.split(os.pathsep)
                if part and part != str(src)
            )
        env["PYTHONPATH"] = os.pathsep.join(parts)

    env["HOME"] = str(home_path)
    env["XDG_CONFIG_HOME"] = str(cfg_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env["XDG_STATE_HOME"] = str(state_dir)
    env.setdefault("LANG", _DEFAULT_LOCALE)
    env.setdefault("LC_ALL", _DEFAULT_LOCALE)
    env.setdefault("TERM", "dumb")

    if updates:
        env = _apply_updates(env, updates)
    return env


@contextmanager
def in_directory(path: str | Path) -> Iterator[Path]:
    """Change the process cwd to *path* and restore it on exit.

    Restores the previous cwd even if the block raises. Does not create
    or delete *path*.
    """
    dest = Path(path).resolve()
    if not dest.is_dir():
        raise HarnessError(f"in_directory target is not a directory: {dest}")
    previous = Path.cwd()
    os.chdir(dest)
    try:
        yield dest
    finally:
        os.chdir(previous)


@contextmanager
def _push_environ(new_env: Mapping[str, str]) -> Iterator[None]:
    """Replace ``os.environ`` with *new_env* and restore it on exit."""
    old = os.environ.copy()
    os.environ.clear()
    os.environ.update(new_env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old)


@contextmanager
def isolated_filesystem(
    path: str | Path | None = None,
    *,
    prefix: str = "harness-fs-",
) -> Iterator[Path]:
    """Temporarily ``chdir`` into an empty directory.

    When *path* is omitted, a new directory is created and removed on
    exit (including on exception). A caller-supplied *path* is created
    if missing and is left in place.
    """
    if path is None:
        dest = Path(tempfile.mkdtemp(prefix=prefix))
        remove = True
    else:
        dest = Path(path)
        dest.mkdir(parents=True, exist_ok=True)
        dest = dest.resolve()
        if not dest.is_dir():
            raise HarnessError(f"isolated_filesystem target is not a directory: {dest}")
        remove = False
    try:
        with in_directory(dest):
            yield dest
    finally:
        if remove:
            shutil.rmtree(dest, ignore_errors=True)


@contextmanager
def workspace(
    *,
    updates: Mapping[str, str | None] | None = None,
    prefix: str = "harness-ws-",
    root: Path | None = None,
) -> Iterator[Workspace]:
    """Allocate an ephemeral work directory and isolated HOME; clean up.

    Yields a :class:`Workspace`. Both directory trees are removed when
    the context exits, including on exception. The product tree is never
    used as the default cwd.
    """
    work = Path(tempfile.mkdtemp(prefix=prefix))
    home = Path(tempfile.mkdtemp(prefix="harness-home-"))
    try:
        env = isolated_environ(home, updates=updates, root=root)
        yield Workspace(path=work, home=home, env=env)
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


def write_file(
    path: str | Path,
    content: str | bytes,
    *,
    encoding: str = DEFAULT_CHARSET,
) -> Path:
    """Write *content* to *path*, creating parent directories.

    Returns the resolved path. Raises ``OSError`` on I/O failure.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        dest.write_bytes(content)
    else:
        dest.write_text(content, encoding=encoding)
    return dest.resolve()


def read_file(path: str | Path, *, encoding: str = DEFAULT_CHARSET) -> str:
    """Read *path* as text.

    Raises ``FileNotFoundError`` if the file does not exist — never
    returns an empty string or ``None`` to mean "missing". Raises
    :class:`HarnessError` if the path exists but is not a regular file,
    or on an ``OSError`` other than classified absence.
    """
    src = Path(path)
    _read_regular_file(src)
    try:
        return src.read_text(encoding=encoding)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot read {src}: {exc}") from exc


def read_bytes(path: str | Path) -> bytes:
    """Read *path* as bytes.

    Raises ``FileNotFoundError`` if the file does not exist — never
    returns empty bytes to mean "missing". Raises :class:`HarnessError`
    if the path exists but is not a regular file, or on an ``OSError``
    other than classified absence.
    """
    src = Path(path)
    _read_regular_file(src)
    try:
        return src.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot read {src}: {exc}") from exc


def path_is_file(path: str | Path) -> bool:
    """Return whether *path* is an existing regular file.

    ``False`` means the path is absent or is not a regular file. Raises
    :class:`HarnessError` on an ``OSError`` other than a classified
    absence — never treats a permission or I/O failure as "not a file".
    """
    src = Path(path)
    try:
        return src.is_file()
    except OSError as exc:
        raise HarnessError(f"cannot stat {src}: {exc}") from exc


# ---------------------------------------------------------------------------
# In-process invocation
# ---------------------------------------------------------------------------


def _open_text(
    buffer: Any,
    *,
    charset: str,
    errors: str | None = None,
) -> _KeepOpenTextIO:
    kwargs: dict[str, Any] = {
        "encoding": charset,
        "line_buffering": True,
        "write_through": True,
    }
    if errors is not None:
        kwargs["errors"] = errors
    return _KeepOpenTextIO(buffer, **kwargs)


def _invoke_in_process(
    cli: Any,
    args: tuple[str, ...],
    *,
    stdin: str | bytes | None,
    env: Mapping[str, str],
    cwd: Path,
    standalone_mode: bool,
    catch_exceptions: bool,
    echo_stdin: bool,
    charset: str,
    prog_name: str,
    extra: dict[str, Any],
) -> InvokeResult:
    main = _require_main(cli)
    mixed = io.BytesIO()
    stdout_buf = _BytesIOCopy(mixed)
    stderr_buf = _BytesIOCopy(mixed)
    if stdin is None:
        input_bytes = b""
    elif isinstance(stdin, str):
        input_bytes = stdin.encode(charset)
    else:
        input_bytes = stdin
    raw_in: Any = io.BytesIO(input_bytes)
    if echo_stdin:
        raw_in = _EchoingStdin(raw_in, stdout_buf)

    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    old_argv = sys.argv
    old_getpass = getpass.getpass

    return_value: Any = None
    exception: BaseException | None = None
    exc_info: tuple[type[BaseException], BaseException, TracebackType] | None = None
    exit_code = 0
    captured: list[WarningMessage] = []

    # Diagnostics must use the caller's streams, never the captured ones.
    print(
        f"[harness] invoke prog={prog_name!r} args={list(args)!r} "
        f"standalone={standalone_mode} cwd={str(cwd)!r}",
        flush=True,
    )

    try:
        sys.stdin = _open_text(raw_in, charset=charset)
        sys.stdout = _open_text(stdout_buf, charset=charset)
        sys.stderr = _open_text(
            stderr_buf,
            charset=charset,
            errors="backslashreplace",
        )
        sys.argv = [prog_name, *args]
        getpass.getpass = _read_hidden_from_stdin
        with _push_environ(env), in_directory(cwd):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                try:
                    return_value = main(
                        args=list(args),
                        prog_name=prog_name,
                        standalone_mode=standalone_mode,
                        **extra,
                    )
                except SystemExit as exc:
                    exception = exc
                    info = sys.exc_info()
                    if (
                        info[0] is not None
                        and info[1] is not None
                        and info[2] is not None
                    ):
                        exc_info = (info[0], info[1], info[2])
                    exit_code = _exit_code_from_system_exit(exc)
                    if exit_code == 0:
                        exception = None
                        exc_info = None
                except Exception as exc:
                    if not catch_exceptions:
                        raise
                    exception = exc
                    info = sys.exc_info()
                    if (
                        info[0] is not None
                        and info[1] is not None
                        and info[2] is not None
                    ):
                        exc_info = (info[0], info[1], info[2])
                    exit_code = 1
                finally:
                    try:
                        sys.stdout.flush()
                    except Exception:
                        pass
                    try:
                        sys.stderr.flush()
                    except Exception:
                        pass
    finally:
        getpass.getpass = old_getpass
        sys.argv = old_argv
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    stdout_bytes = stdout_buf.getvalue()
    stderr_bytes = stderr_buf.getvalue()
    output_bytes = mixed.getvalue()
    result = InvokeResult(
        exit_code=exit_code,
        stdout=stdout_bytes,
        stderr=stderr_bytes,
        output=output_bytes,
        return_value=return_value,
        exception=exception,
        exc_info=exc_info,
        args=args,
        cwd=str(cwd),
        warnings=tuple(captured),
    )
    print(
        f"[harness] exit={result.exit_code} "
        f"stdout_len={len(result.stdout)} stderr_len={len(result.stderr)} "
        f"exception={type(result.exception).__name__ if result.exception else None}",
        flush=True,
    )
    if result.exit_code != 0 and 0 < len(result.stderr) <= 2000:
        print(f"[harness] stderr={result.stderr_text!r}", flush=True)
    return result


def invoke(
    cli: Any,
    args: Sequence[str] | str | None = None,
    *,
    stdin: str | bytes | None = None,
    env: Mapping[str, str | None] | None = None,
    cwd: str | Path | None = None,
    isolate: bool = True,
    standalone_mode: bool = True,
    catch_exceptions: bool | None = None,
    echo_stdin: bool = False,
    charset: str = DEFAULT_CHARSET,
    prog_name: str | None = None,
    **extra: Any,
) -> InvokeResult:
    """Invoke a command through its public ``main`` entry.

    This is the canonical in-process path: argument tokens, stdin, and
    environment are those of a program invocation. Extra keywords are
    forwarded to ``main`` (and from there to the invocation-context
    constructor — terminal width, color, default map, and similar).

    When *isolate* is true (the default) the call runs in a fresh
    :func:`workspace` so it cannot see the caller's cwd, HOME, or
    incidental environment variables. Pass ``isolate=False`` (and
    optionally *cwd* / *env*) to inherit the caller's process state, or
    to reuse a :class:`Workspace`. *env* is a complete mapping when
    supplied with ``isolate=False``; with ``isolate=True`` it is applied
    as updates on the isolated environment (``None`` unsets).

    *catch_exceptions* defaults to true in standalone mode (a crash
    becomes ``exit_code == 1`` on the result) and false otherwise
    (integrator-mode failures propagate). A ``SystemExit`` is always
    recorded as ``exit_code``, never raised out of this function.

    Returns an :class:`InvokeResult`. Does not raise on a non-zero
    product exit.
    """
    tokens = _normalize_args(args)
    if catch_exceptions is None:
        catch_exceptions = bool(standalone_mode)
    if prog_name is None:
        name = getattr(cli, "name", None)
        prog_name = name if isinstance(name, str) and name else DEFAULT_PROG_NAME

    def _run(child_cwd: Path, child_env: Mapping[str, str]) -> InvokeResult:
        return _invoke_in_process(
            cli,
            tokens,
            stdin=stdin,
            env=child_env,
            cwd=child_cwd,
            standalone_mode=standalone_mode,
            catch_exceptions=catch_exceptions,
            echo_stdin=echo_stdin,
            charset=charset,
            prog_name=prog_name,
            extra=dict(extra),
        )

    if isolate:
        with workspace(updates=env) as ws:
            work = Path(cwd).resolve() if cwd is not None else ws.path
            return _run(work, ws.env)

    if env is not None:
        child_env = {k: v for k, v in env.items() if v is not None}
    else:
        child_env = dict(os.environ)
    work = Path(cwd).resolve() if cwd is not None else Path.cwd()
    if not work.is_dir():
        raise HarnessError(f"invoke cwd is not a directory: {work}")
    return _run(work, child_env)


# ---------------------------------------------------------------------------
# Subprocess invocation
# ---------------------------------------------------------------------------


def run_command(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> RunResult:
    """Run an arbitrary argv and capture exit status plus stdout/stderr.

    *stdin* may be ``str`` (encoded as UTF-8) or ``bytes``. ``None`` is
    treated as empty stdin (EOF), not as inheriting the caller's stream.
    When *env* is ``None``, the current process environment is inherited.
    When *cwd* is ``None``, the current process cwd is used. Raises
    ``FileNotFoundError`` if the executable cannot be found; raises
    ``subprocess.TimeoutExpired`` on timeout. Does not interpret the
    exit status.
    """
    if not argv:
        raise ValueError("argv must be non-empty")
    workdir = str(Path(cwd).resolve()) if cwd is not None else str(repo_root())
    if stdin is None:
        input_bytes: bytes = b""
    elif isinstance(stdin, str):
        input_bytes = stdin.encode(DEFAULT_CHARSET)
    else:
        input_bytes = stdin

    print(
        f"[harness] run cwd={workdir!r} argv={list(argv)!r}",
        flush=True,
    )
    completed = subprocess.run(
        list(argv),
        cwd=workdir,
        env=dict(env) if env is not None else None,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    result = RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout or b"",
        stderr=completed.stderr or b"",
        argv=tuple(str(a) for a in argv),
        cwd=workdir,
    )
    print(
        f"[harness] exit={result.returncode} "
        f"stdout_len={len(result.stdout)} stderr_len={len(result.stderr)}",
        flush=True,
    )
    if result.returncode != 0 and 0 < len(result.stderr) <= 2000:
        print(f"[harness] stderr={result.stderr_text!r}", flush=True)
    return result


def run_python(
    *,
    code: str | None = None,
    argv: Sequence[str] | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    isolate: bool = True,
    root: Path | None = None,
) -> RunResult:
    """Run this process's interpreter as a child.

    *code* is passed as ``python -c <code>``. *argv* are extra arguments
    after ``-c`` (or, when *code* is omitted, the arguments after the
    interpreter — for example ``['-m', 'pkg']``). At least one of *code*
    or *argv* must be supplied.

    When *isolate* is true (the default) and *cwd* / *env* are omitted,
    the child runs in a fresh :func:`workspace` with the product ``src/``
    on ``PYTHONPATH``. Does not raise on a non-zero child exit.
    """
    if code is None and not argv:
        raise ValueError("run_python requires code= or a non-empty argv")

    python = sys.executable
    if not python:
        raise HarnessError("sys.executable is empty; cannot spawn an interpreter")
    child_argv: list[str] = [python]
    if code is not None:
        child_argv.extend(["-c", code])
    if argv:
        child_argv.extend(str(a) for a in argv)

    if cwd is not None or env is not None or not isolate:
        return run_command(
            child_argv, cwd=cwd, env=env, stdin=stdin, timeout=timeout
        )

    with workspace(root=root) as ws:
        return run_command(
            child_argv,
            cwd=ws.path,
            env=ws.env,
            stdin=stdin,
            timeout=timeout,
        )


__all__ = (
    "DEFAULT_CHARSET",
    "DEFAULT_PROG_NAME",
    "DEFAULT_TIMEOUT",
    "HarnessError",
    "InvokeResult",
    "RunResult",
    "Workspace",
    "in_directory",
    "invoke",
    "isolated_environ",
    "isolated_filesystem",
    "path_is_file",
    "product_src_dir",
    "read_bytes",
    "read_file",
    "repo_root",
    "run_command",
    "run_python",
    "workspace",
    "write_file",
)
