# feature: F00
"""Shared machinery for driving the product through its public surface.

Suites import from this module (``from _harness import ...``). Importing it
performs no I/O, starts no processes, and opens no sockets. Compilation,
process spawn, filesystem writes, and environment replacement happen only
when a caller invokes a function or enters a context manager below.

The product is an embeddable C++20 library with a matching C interface,
not an importable Python package. A convenience CLI may also be present
when tools were built; it is the same parse-and-inspect surface, not a
separate product. Python tests reach the library by compiling a short C
or C++ probe against the recipe-built archive (or shared object) and
running that probe as a child process.

Surfaces
--------
* Library probe — :func:`invoke` / :func:`compile_probe`. Caller supplies
  source that includes the public headers and links the recipe-built
  library. Stdin, argv, cwd, and environment of the resulting binary are
  caller-controlled. Each probe is a fresh process, so a process-wide
  length cap set inside one probe cannot leak into another.
* CLI — :func:`run_cli`. Spawns the recipe-built convenience binary when
  it exists. Missing CLI is a substrate gap (the default recipe does not
  build tools), reported as :class:`FileNotFoundError`, never as a
  classified product refusal.

Missing substrate (no public header, no built library, no compiler)
raises :class:`FileNotFoundError` or :class:`HarnessError`. A product
non-zero exit recorded on :class:`RunResult` is a classified outcome,
not a harness failure. Observation failures this module cannot classify
raise :class:`HarnessError`.
"""

from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping, Sequence

# ---------------------------------------------------------------------------
# Public defaults / recipe artifact names
# ---------------------------------------------------------------------------

DEFAULT_CHARSET = "utf-8"
DEFAULT_TIMEOUT = 30.0
DEFAULT_CXX_STD = "c++20"

# Public headers shipped by the library (relative to include_dir()).
CXX_HEADER = "hrefparse.h"
C_HEADER = "hrefparse_c.h"

# CMake target name / lib prefix. Archive is libhrefparse.a; shared is libhrefparse.so.
LIBRARY_STEM = "hrefparse"

# Environment overrides (absolute paths). Never fall back to PATH for the
# library or CLI — a system-installed copy would hide a recipe shortfall.
PRODUCT_ROOT_ENV = "PRODUCT_ROOT"
PRODUCT_LIB_ENV = "PRODUCT_LIB"
PRODUCT_INCLUDE_ENV = "PRODUCT_INCLUDE"
PRODUCT_BIN_ENV = "PRODUCT_BIN"
CXX_ENV = "CXX"

# Convenience CLI relative to the repository root. Absent unless tools
# were enabled at configure time.
_CLI_RELPATHS = (
    Path("build") / "tools" / "cli" / "hrefparsec",
    Path("build") / "hrefparsec",
)

# Known CMake output locations for the library target, relative to root.
_LIB_RELPATHS = (
    Path("build") / "src" / f"lib{LIBRARY_STEM}.a",
    Path("build") / "src" / f"lib{LIBRARY_STEM}.so",
    Path("build") / f"lib{LIBRARY_STEM}.a",
    Path("build") / f"lib{LIBRARY_STEM}.so",
    Path("build") / "lib" / f"lib{LIBRARY_STEM}.a",
    Path("build") / "lib" / f"lib{LIBRARY_STEM}.so",
)

# Recipe testing builds expose the standard-library regex provider as a
# public compile definition on the library target. Probes that compile
# against that build need the same define to see the provider type.
_DEFAULT_CXX_DEFINES = ("HREFPARSE_USE_UNSAFE_STD_REGEX_PROVIDER",)

# Keys stripped so a child does not inherit the caller's locale / proxy /
# build-tree side channels unless the caller puts them back.
_ISOLATE_UNSET = (
    "COLUMNS",
    "LINES",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
    "FTP_PROXY",
    "ftp_proxy",
)

_KEEP_ENV_KEYS = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "USERNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "TZ",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "TERM",
    "LD_LIBRARY_PATH",
    "LIBRARY_PATH",
    "CPATH",
    "CPLUS_INCLUDE_PATH",
    "C_INCLUDE_PATH",
    "CC",
    "CXX",
    "COMPILER_PATH",
)


# ---------------------------------------------------------------------------
# Errors / result types
# ---------------------------------------------------------------------------


class HarnessError(RuntimeError):
    """Raised when an observation cannot be classified.

    Used for a missing compiler, a probe that failed to compile or link,
    a workspace path that escapes its root, a timeout, and I/O failures
    that are not a documented product outcome. Never used to mean "the
    product returned a non-zero exit the PRD describes".
    """


@dataclass(frozen=True)
class RunResult:
    """Outcome of one subprocess invocation.

    Attributes:
        returncode: Process exit status. ``0`` is POSIX success; the
            harness does not interpret any other code.
        stdout: Raw standard output bytes (no decoding applied).
        stderr: Raw standard error bytes (no decoding applied).
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
        """Stdout decoded as UTF-8.

        Raises:
            HarnessError: if stdout is not valid UTF-8. Never replaces
                undecodable bytes — replacement would turn a decode
                failure into a legitimate-looking string.
        """
        return decode_utf8(self.stdout, what="stdout")

    @property
    def stderr_text(self) -> str:
        """Stderr decoded as UTF-8.

        Raises:
            HarnessError: if stderr is not valid UTF-8.
        """
        return decode_utf8(self.stderr, what="stderr")


@dataclass
class Workspace:
    """Ephemeral work directory plus the isolated environment bound to it.

    ``path`` is the working directory for invokes. ``home`` is used as
    ``HOME`` (and the XDG roots live under it) so ``~`` expansion cannot
    see the caller's home. Both trees are removed when the allocating
    context exits.
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
        """Read a text file under this workspace.

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

    def compile_probe(
        self,
        source: str | bytes,
        *,
        language: str = "c++",
        extra_args: Sequence[str] | None = None,
        output: str | Path = "probe",
        root: Path | None = None,
    ) -> Path:
        """Compile *source* into this workspace and return the binary path."""
        return compile_probe(
            source,
            language=language,
            extra_args=extra_args,
            output=self.resolve(output),
            root=root,
        )

    def invoke(
        self,
        source: str | bytes,
        args: Sequence[str] | None = None,
        *,
        language: str = "c++",
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        extra_args: Sequence[str] | None = None,
        root: Path | None = None,
    ) -> RunResult:
        """Compile *source* and run it with this workspace as cwd and env.

        Does not raise on a non-zero product exit.
        """
        env = _apply_updates(self.env, env_updates)
        return invoke(
            source,
            args,
            language=language,
            cwd=self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
            extra_args=extra_args,
            root=root,
            isolate=False,
        )

    def run_cli(
        self,
        args: Sequence[str] | None = None,
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        root: Path | None = None,
        binary: str | Path | None = None,
    ) -> RunResult:
        """Run the convenience CLI with this workspace as cwd and env.

        Does not raise on a non-zero product exit. Raises
        ``FileNotFoundError`` if the CLI binary is not in the recipe
        build.
        """
        env = _apply_updates(self.env, env_updates)
        return run_cli(
            args,
            cwd=self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
            root=root,
            binary=binary,
            isolate=False,
        )

    def run_command(
        self,
        argv: Sequence[str],
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
    ) -> RunResult:
        """Run *argv* with this workspace as cwd and env.

        Does not raise on a non-zero child exit.
        """
        env = _apply_updates(self.env, env_updates)
        return run_command(
            argv,
            cwd=cwd if cwd is not None else self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
        )


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


def _normalize_args(args: Sequence[str] | None) -> tuple[str, ...]:
    if args is None:
        return ()
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


def _as_bytes(data: str | bytes, *, encoding: str = DEFAULT_CHARSET) -> bytes:
    if isinstance(data, bytes):
        return data
    return data.encode(encoding)


def decode_utf8(data: bytes, *, what: str = "bytes") -> str:
    """Decode *data* as UTF-8.

    Raises:
        HarnessError: if *data* is not valid UTF-8. Never returns a
            replacement-character string that could be mistaken for a
            successful decode.
    """
    try:
        return data.decode(DEFAULT_CHARSET)
    except UnicodeDecodeError as exc:
        raise HarnessError(
            f"{what} is not valid UTF-8 ({exc}); inspect the raw bytes"
        ) from exc


def _diagnostic_text(data: bytes) -> str:
    """Decode for harness logs only; replacement is not a test observation."""
    return data.decode(DEFAULT_CHARSET, errors="replace")


def _normalize_language(language: str) -> str:
    key = language.strip().lower()
    if key in ("c++", "cpp", "cxx", "cc"):
        return "c++"
    if key == "c":
        return "c"
    raise ValueError(f"unsupported probe language: {language!r} (use 'c++' or 'c')")


# ---------------------------------------------------------------------------
# Paths / discovery
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Return the built repository root.

    Tests run with the repository root as the pytest process cwd (recipe
    build artifacts such as ``build/src/libhrefparse.a`` are available there).
    ``PRODUCT_ROOT`` overrides cwd. Does not search parents.
    """
    override = os.environ.get(PRODUCT_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def include_dir(*, root: Path | None = None) -> Path:
    """Return the public include directory.

    Resolution order:
      1. ``PRODUCT_INCLUDE`` if set.
      2. ``<root>/include`` containing the C++ public header.

    Raises:
        FileNotFoundError: when the directory or public header is missing.
            That is a substrate gap, not a product-behavior judgment.
    """
    override = os.environ.get(PRODUCT_INCLUDE_ENV)
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_file():
            path = path.parent
        header = path / CXX_HEADER
        if not header.is_file():
            raise FileNotFoundError(
                f"{PRODUCT_INCLUDE_ENV} does not contain {CXX_HEADER}: {path}"
            )
        return path

    base = root if root is not None else repo_root()
    path = (Path(base) / "include").resolve()
    header = path / CXX_HEADER
    if not header.is_file():
        raise FileNotFoundError(
            f"public header not found at {header}; the repository include "
            "tree must be present before tests run"
        )
    return path


def library_file(*, root: Path | None = None) -> Path:
    """Locate the recipe-built library archive or shared object.

    Resolution order:
      1. ``PRODUCT_LIB`` if set.
      2. Known CMake output paths under ``<root>/build``.

    Does not fall back to a system-installed library.

    Raises:
        FileNotFoundError: when no library file exists at a resolved path.
    """
    override = os.environ.get(PRODUCT_LIB_ENV)
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"{PRODUCT_LIB_ENV} does not point to a file: {path}"
            )
        return path

    base = Path(root) if root is not None else repo_root()
    searched: list[str] = []
    for rel in _LIB_RELPATHS:
        path = (base / rel).resolve()
        searched.append(str(path))
        if path.is_file():
            return path

    src_dir = (base / "build" / "src").resolve()
    if src_dir.is_dir():
        try:
            matches = sorted(
                p
                for p in src_dir.iterdir()
                if p.is_file()
                and (
                    p.name == f"lib{LIBRARY_STEM}.a"
                    or p.name.startswith(f"lib{LIBRARY_STEM}.so")
                )
            )
        except OSError as exc:
            raise HarnessError(f"cannot list {src_dir}: {exc}") from exc
        if matches:
            return matches[0].resolve()

    raise FileNotFoundError(
        "recipe-built library not found; searched "
        + ", ".join(searched)
        + ". The runner build must produce the library before tests run."
    )


def cli_bin(*, root: Path | None = None) -> Path:
    """Locate the recipe-built convenience CLI and return its path.

    Resolution order:
      1. ``PRODUCT_BIN`` if set.
      2. Known CMake output paths under ``<root>/build``.

    Raises:
        FileNotFoundError: when the binary is missing. The default recipe
            does not enable tools, so this is a substrate / recipe gap
            unless the caller built the CLI.
    """
    override = os.environ.get(PRODUCT_BIN_ENV)
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"{PRODUCT_BIN_ENV} does not point to a file: {path}"
            )
        if not os.access(path, os.X_OK):
            raise FileNotFoundError(f"{PRODUCT_BIN_ENV} is not executable: {path}")
        return path

    base = Path(root) if root is not None else repo_root()
    searched: list[str] = []
    for rel in _CLI_RELPATHS:
        path = (base / rel).resolve()
        searched.append(str(path))
        if path.is_file() and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError(
        "convenience CLI not found; searched "
        + ", ".join(searched)
        + ". The default recipe does not build tools."
    )


def cxx_compiler() -> str:
    """Return the C++ compiler used to link probes.

    Uses ``$CXX`` when set, otherwise ``c++``. Does not spawn the
    compiler. A missing binary is reported when :func:`compile_probe`
    runs, not here.
    """
    override = os.environ.get(CXX_ENV)
    if override:
        return override
    return "c++"


def _is_shared_library(path: Path) -> bool:
    name = path.name
    return name.endswith(".so") or ".so." in name


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
    """Build an environment that does not inherit the caller's home/proxy state.

    Starts from a small keep-list of substrate keys (PATH, locale, compiler,
    loader) taken from *base* or ``os.environ``, points ``HOME`` and the
    XDG dirs at *home*, unsets proxy / TTY keys, and applies *updates*
    last (``None`` unsets). When the recipe library is shared, prepends
    its directory to ``LD_LIBRARY_PATH``. Does not mutate ``os.environ``.

    Returns a new ``dict``.
    """
    home_path = Path(home).resolve()
    cfg_dir = home_path / ".config"
    cache_dir = home_path / ".cache"
    data_dir = home_path / ".local" / "share"
    for directory in (home_path, cfg_dir, cache_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source = base if base is not None else os.environ
    env: dict[str, str] = {}
    for key in _KEEP_ENV_KEYS:
        value = source.get(key)
        if value is not None:
            env[key] = value
    for key in _ISOLATE_UNSET:
        env.pop(key, None)

    env["HOME"] = str(home_path)
    env["XDG_CONFIG_HOME"] = str(cfg_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")
    env["TMPDIR"] = str(home_path / "tmp")
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)

    try:
        lib = library_file(root=root)
    except FileNotFoundError:
        lib = None
    if lib is not None and _is_shared_library(lib):
        libdir = str(lib.parent)
        existing = env.get("LD_LIBRARY_PATH", "")
        parts = [libdir]
        if existing:
            parts.extend(
                part for part in existing.split(os.pathsep) if part and part != libdir
            )
        env["LD_LIBRARY_PATH"] = os.pathsep.join(parts)

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
# Process invocation
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
    When *cwd* is ``None``, the current process cwd is used.

    Raises:
        FileNotFoundError: if the executable cannot be found.
        HarnessError: on timeout or an OSError other than classified
            absence. Does not interpret the exit status.
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
    try:
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
    except FileNotFoundError:
        raise
    except subprocess.TimeoutExpired as exc:
        raise HarnessError(
            f"command timed out after {timeout}s: {list(argv)!r}"
        ) from exc
    except OSError as exc:
        raise HarnessError(f"failed to execute {argv[0]!r}: {exc}") from exc

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
        print(f"[harness] stderr={_diagnostic_text(result.stderr)!r}", flush=True)
    return result


# ---------------------------------------------------------------------------
# Library probes (canonical public entry)
# ---------------------------------------------------------------------------

_PROBE_CACHE: Path | None = None


def _probe_cache_dir() -> Path:
    """Return a process-lifetime directory for compiled probes.

    Created on first compile, not at import. Removed at interpreter exit.
    """
    global _PROBE_CACHE
    if _PROBE_CACHE is None:
        _PROBE_CACHE = Path(tempfile.mkdtemp(prefix="libprobe-"))
        atexit.register(shutil.rmtree, _PROBE_CACHE, True)
    return _PROBE_CACHE


def _compile_argv(
    source_path: Path,
    output: Path,
    *,
    language: str,
    include: Path,
    lib: Path,
    extra_args: Sequence[str],
) -> list[str]:
    compiler = cxx_compiler()
    argv = [
        compiler,
        f"-std={DEFAULT_CXX_STD}",
        f"-I{include}",
    ]
    if language == "c++":
        for define in _DEFAULT_CXX_DEFINES:
            argv.append(f"-D{define}")
    argv.extend(str(a) for a in extra_args)
    argv.extend([str(source_path), str(lib), "-o", str(output)])
    if os.name != "nt":
        argv.append("-pthread")
    return argv


def compile_probe(
    source: str | bytes,
    *,
    language: str = "c++",
    extra_args: Sequence[str] | None = None,
    output: str | Path | None = None,
    root: Path | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> Path:
    """Compile *source* against the recipe-built library and return the binary.

    *language* is ``c++`` (public C++ headers) or ``c`` (C interface
    header). Extra compiler/linker tokens go in *extra_args*. When
    *output* is omitted, the binary is written to a process-lifetime
    cache keyed by source, language, flags, and library identity.

    This is compile-and-link of a caller-supplied probe, not a product
    rebuild: it does not run cmake, ninja, make, or fetch.

    Raises:
        FileNotFoundError: missing header, library, or compiler.
        HarnessError: compiler non-zero exit, timeout, or I/O failure.
            Compiler stderr is included in the message. A compile failure
            is never returned as a :class:`RunResult`.
    """
    lang = _normalize_language(language)
    extra = tuple(str(a) for a in extra_args) if extra_args else ()
    base = root if root is not None else repo_root()
    include = include_dir(root=base)
    lib = library_file(root=base)
    src_bytes = _as_bytes(source)

    if output is None:
        try:
            st = lib.stat()
        except OSError as exc:
            raise HarnessError(f"cannot stat library {lib}: {exc}") from exc
        digest = hashlib.sha256()
        digest.update(src_bytes)
        digest.update(b"\0")
        digest.update(lang.encode())
        digest.update(b"\0")
        digest.update(str(lib).encode())
        digest.update(b"\0")
        digest.update(str(st.st_mtime_ns).encode())
        digest.update(b"\0")
        digest.update(str(st.st_size).encode())
        digest.update(b"\0")
        digest.update(b"\0".join(a.encode() for a in extra))
        digest.update(b"\0")
        digest.update(cxx_compiler().encode())
        out_path = _probe_cache_dir() / f"probe-{digest.hexdigest()[:20]}"
        if out_path.is_file() and os.access(out_path, os.X_OK):
            print(f"[harness] reuse probe {out_path}", flush=True)
            return out_path
    else:
        out_path = Path(output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

    suffix = ".cpp" if lang == "c++" else ".c"
    work = Path(tempfile.mkdtemp(prefix="libprobe-src-"))
    try:
        source_path = work / f"probe{suffix}"
        source_path.write_bytes(src_bytes)
        argv = _compile_argv(
            source_path,
            out_path,
            language=lang,
            include=include,
            lib=lib,
            extra_args=extra,
        )
        print(f"[harness] compile argv={argv!r}", flush=True)
        try:
            completed = subprocess.run(
                argv,
                cwd=str(work),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"C++ compiler {cxx_compiler()!r} not found; a C++20 "
                "toolchain is required to link probes against the library"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HarnessError(
                f"compile timed out after {timeout}s: {argv!r}"
            ) from exc
        except OSError as exc:
            raise HarnessError(f"failed to spawn compiler: {exc}") from exc
        if completed.returncode != 0:
            err = _diagnostic_text((completed.stderr or b"") + (completed.stdout or b""))
            raise HarnessError(
                f"probe failed to compile or link (exit {completed.returncode}): {err}"
            )
        if not out_path.is_file():
            raise HarnessError(f"compiler exited 0 but produced no binary at {out_path}")
        out_path.chmod(out_path.stat().st_mode | 0o111)
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)


def invoke(
    source: str | bytes,
    args: Sequence[str] | None = None,
    *,
    language: str = "c++",
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    extra_args: Sequence[str] | None = None,
    root: Path | None = None,
    isolate: bool = True,
) -> RunResult:
    """Compile *source* against the library and run the resulting binary.

    This is the canonical way to reach the product. The probe is a child
    process: a process-wide length cap, and any other global library
    state, cannot leak into the pytest process or a later probe.

    When *isolate* is true (the default) and *cwd* / *env* are omitted,
    the process runs in a fresh :func:`workspace` so it cannot see the
    caller's cwd or HOME. Pass ``isolate=False`` (and optionally *cwd* /
    *env*) to inherit the caller's process state, or to reuse a
    :class:`Workspace`.

    Returns a :class:`RunResult`. Does not raise on a non-zero product
    exit — that status is the observation. Compile/link failures raise
    :class:`HarnessError` before the probe is started.
    """
    binary = compile_probe(
        source,
        language=language,
        extra_args=extra_args,
        root=root,
        timeout=timeout,
    )
    argv = [str(binary), *_normalize_args(args)]

    if cwd is not None or env is not None or not isolate:
        run_env = dict(env) if env is not None else None
        if run_env is not None:
            try:
                lib = library_file(root=root)
            except FileNotFoundError:
                lib = None
            if lib is not None and _is_shared_library(lib):
                libdir = str(lib.parent)
                existing = run_env.get("LD_LIBRARY_PATH", "")
                if libdir not in existing.split(os.pathsep):
                    run_env["LD_LIBRARY_PATH"] = (
                        libdir if not existing else libdir + os.pathsep + existing
                    )
        return run_command(
            argv,
            cwd=cwd,
            env=run_env,
            stdin=stdin,
            timeout=timeout,
        )

    with workspace(root=root) as ws:
        return run_command(
            argv,
            cwd=ws.path,
            env=ws.env,
            stdin=stdin,
            timeout=timeout,
        )


def run_cli(
    args: Sequence[str] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    binary: str | Path | None = None,
    isolate: bool = True,
) -> RunResult:
    """Invoke the convenience CLI as ``<cli> *args``.

    When *binary* is omitted, uses :func:`cli_bin`. Isolation rules match
    :func:`invoke`. Does not raise on a non-zero product exit.

    Raises:
        FileNotFoundError: if the CLI was not built.
    """
    exe = Path(binary) if binary is not None else cli_bin(root=root)
    argv = [str(exe), *_normalize_args(args)]

    if cwd is not None or env is not None or not isolate:
        return run_command(
            argv,
            cwd=cwd,
            env=env,
            stdin=stdin,
            timeout=timeout,
        )

    with workspace(root=root) as ws:
        return run_command(
            argv,
            cwd=ws.path,
            env=ws.env,
            stdin=stdin,
            timeout=timeout,
        )
