# feature: F00
"""Shared machinery for driving the product through its public surfaces.

Suites import from this module (``from _harness import ...``). Importing it
performs no I/O, starts no processes, and opens no sockets. All process,
filesystem, and bind side effects happen only when a caller invokes a
function or enters a context manager below.

The product is a compiled command-line Git extension, not an importable
Python package. Python tests reach it by spawning the recipe-built binary
and, for the Git-extension path, by spawning ``git`` with that binary first
on ``PATH``. This module is the one canonical way to do that.

Surfaces
--------
* Direct binary — ``<root>/bin/git-orbulk …`` with caller-controlled argv,
  stdin, cwd, and env. Plumbing entries (clean, smudge, filter-process,
  pointer, hooks) are driven this way, as is any subcommand.
* Git-extension path — ``git orbulk …``. Git locates the ``git-orbulk``
  executable on ``PATH``; the harness prepends the recipe ``bin/``
  directory so the built binary is the one Git finds.

Missing substrate (no recipe binary, no ``git``) raises
``FileNotFoundError``. A product non-zero exit is a classified outcome on
:class:`RunResult`, not a harness failure. Observation failures this module
cannot classify raise :class:`HarnessError`.
"""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator, Mapping, Sequence

# ---------------------------------------------------------------------------
# Public entry defaults (PRD: one CLI binary, invoked as a Git extension)
# ---------------------------------------------------------------------------

# Recipe ``make`` artifact (Makefile default goal).
BIN_RELPATH = Path("bin") / "git-orbulk"

# Git-extension name: ``git orbulk <subcommand>``. Git locates ``git-orbulk``.
GIT_EXTENSION = "orbulk"

# Environment override for the product binary.
PRODUCT_BIN_ENV = "PRODUCT_BIN"

DEFAULT_TIMEOUT = 60.0

# Identity used only to make Git commits possible in an isolated repo.
# Not a product string.
_GIT_AUTHOR_NAME = "Harness Tester"
_GIT_AUTHOR_EMAIL = "tester@example.test"

# Caller-environment keys that couple a child to the parent Git / editor /
# pager / product / proxy state. Isolated calls unset these unless the
# caller puts them back through *updates*.
_ISOLATE_UNSET = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_COMMON_DIR",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_PREFIX",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_EXEC_PATH",
    "GIT_TEMPLATE_DIR",
    "GIT_TRACE",
    "GIT_TRACE2",
    "GIT_TRACE_PACKET",
    "GIT_TRACE_PERFORMANCE",
    "GIT_TRACE_SETUP",
    "GIT_CURL_VERBOSE",
    "GIT_TRANSFER_TRACE",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_ASKPASS",
    "SSH_ASKPASS",
    "GIT_FLUSH",
    "GIT_EDITOR",
    "GIT_SEQUENCE_EDITOR",
    "GIT_PAGER",
    "GIT_REFLOG_ACTION",
    "GIT_CHERRY_PICK_HELP",
    "GIT_LITERAL_PATHSPECS",
    "GIT_GLOB_PATHSPECS",
    "GIT_NOGLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
    "GIT_LOG_STATS",
    "GIT_PROXY_COMMAND",
    "GIT_HTTP_PROXY_AUTHMETHOD",
    "EDITOR",
    "VISUAL",
    "PAGER",
    "EMAIL",
    "ORBULK_FASTWALK_LIMIT",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
)

# Prefixes stripped in full (test-harness and product env leaks).
_ISOLATE_PREFIXES = (
    "GIT_ORBULK_",
    "ORBULKTEST_",
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
)


# ---------------------------------------------------------------------------
# Errors / result types
# ---------------------------------------------------------------------------


class HarnessError(RuntimeError):
    """Raised when an observation cannot be classified.

    Used for missing substrate, a git-config probe that fails for a reason
    other than "unset", a workspace path that escapes its root, and bind
    failures. Never used to mean "the product returned a non-zero exit the
    PRD describes".
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
        """Stdout decoded as UTF-8 with replacement for undecodable bytes."""
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def stderr_text(self) -> str:
        """Stderr decoded as UTF-8 with replacement for undecodable bytes."""
        return self.stderr.decode("utf-8", errors="replace")


@dataclass
class HttpService:
    """A loopback HTTP server started by :func:`loopback_http`.

    ``host`` / ``port`` / ``url`` are the bound address. ``httpd`` is the
    live server; callers must not start a second serve loop on it. The
    allocating context stops the server on exit.
    """

    host: str
    port: int
    url: str
    httpd: ThreadingHTTPServer
    _thread: threading.Thread = field(repr=False, compare=False)


@dataclass
class Workspace:
    """Ephemeral work directory plus the isolated environment bound to it.

    ``path`` is the working directory for invokes. ``home`` is used as
    ``HOME`` (and the XDG roots live under it) so ``~`` expansion and
    global Git config cannot see the caller's home. Both trees are
    removed when the allocating context exits.
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
        encoding: str = "utf-8",
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

    def read(self, relpath: str | Path, *, encoding: str = "utf-8") -> str:
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
        args: Sequence[str] | None = None,
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
        root: Path | None = None,
        binary: str | Path | None = None,
    ) -> RunResult:
        """Run the product binary with this workspace as cwd and env.

        *env_updates* are applied on a copy of :attr:`env` (``None``
        unsets). Does not raise on a non-zero product exit.
        """
        env = _apply_updates(self.env, env_updates)
        return invoke(
            args,
            cwd=cwd if cwd is not None else self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
            root=root,
            binary=binary,
            isolate=False,
        )

    def invoke_via_git(
        self,
        args: Sequence[str] | None = None,
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
        root: Path | None = None,
        git: str | Path | None = None,
    ) -> RunResult:
        """Run ``git orbulk …`` with this workspace as cwd and env.

        Does not raise on a non-zero product or Git exit.
        """
        env = _apply_updates(self.env, env_updates)
        return invoke_via_git(
            args,
            cwd=cwd if cwd is not None else self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
            root=root,
            git=git,
            isolate=False,
        )

    def git(
        self,
        args: Sequence[str],
        *,
        stdin: bytes | str | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        cwd: str | Path | None = None,
        git: str | Path | None = None,
    ) -> RunResult:
        """Run ``git`` with this workspace as cwd and env.

        Does not raise on a non-zero Git exit. Use :meth:`init_repo` /
        :meth:`git_config_get` when the caller needs classified substrate
        outcomes rather than a raw status.
        """
        env = _apply_updates(self.env, env_updates)
        return run_git(
            args,
            cwd=cwd if cwd is not None else self.path,
            env=env,
            stdin=stdin,
            timeout=timeout,
            git=git,
            isolate=False,
        )

    def init_repo(
        self,
        relpath: str | Path = ".",
        *,
        branch: str = "main",
        git: str | Path | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> Path:
        """Create a Git repository under this workspace and return its path.

        Runs ``git init -b <branch>`` and writes a local committer identity
        so later ``git commit`` calls can succeed. Does not install the
        product, write attributes, or add remotes.

        Raises:
            HarnessError: if init or the identity writes fail. Those are
                substrate failures, not product-behavior judgments.
        """
        dest = self.resolve(relpath)
        dest.mkdir(parents=True, exist_ok=True)
        result = run_git(
            ["init", "-b", branch, str(dest)],
            cwd=dest,
            env=self.env,
            timeout=timeout,
            git=git,
            isolate=False,
        )
        if result.returncode != 0:
            raise HarnessError(
                "git init failed "
                f"(exit {result.returncode}): {result.stderr_text}"
            )
        for key, value in (
            ("user.name", _GIT_AUTHOR_NAME),
            ("user.email", _GIT_AUTHOR_EMAIL),
            ("init.defaultBranch", branch),
        ):
            written = git_config_set(
                key,
                value,
                cwd=dest,
                env=self.env,
                local=True,
                git=git,
                timeout=timeout,
            )
            if written.returncode != 0:
                raise HarnessError(
                    f"git config {key!r} failed "
                    f"(exit {written.returncode}): {written.stderr_text}"
                )
        return dest

    def git_config_get(
        self,
        key: str,
        *,
        local: bool = False,
        global_: bool = False,
        file: str | Path | None = None,
        cwd: str | Path | None = None,
        git: str | Path | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> str | None:
        """Read a Git config value in this workspace.

        See :func:`git_config_get`.
        """
        return git_config_get(
            key,
            cwd=cwd if cwd is not None else self.path,
            env=self.env,
            local=local,
            global_=global_,
            file=file,
            git=git,
            timeout=timeout,
        )

    def git_config_set(
        self,
        key: str,
        value: str,
        *,
        local: bool = False,
        global_: bool = False,
        file: str | Path | None = None,
        cwd: str | Path | None = None,
        git: str | Path | None = None,
        timeout: float | None = DEFAULT_TIMEOUT,
    ) -> RunResult:
        """Write a Git config value in this workspace.

        See :func:`git_config_set`.
        """
        return git_config_set(
            key,
            value,
            cwd=cwd if cwd is not None else self.path,
            env=self.env,
            local=local,
            global_=global_,
            file=file,
            git=git,
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


def token(nbytes: int = 6) -> str:
    """Return a fresh lowercase hex token for runtime-unique fixtures.

    Uses :func:`secrets.token_hex`. Does not contact the product.
    """
    if nbytes < 1:
        raise ValueError("nbytes must be >= 1")
    return secrets.token_hex(nbytes)


# ---------------------------------------------------------------------------
# Paths / discovery
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Return the built repository root.

    Tests run with the repository root as the pytest process cwd (recipe
    build artifacts such as ``bin/git-orbulk`` are available there). Returns
    ``Path.cwd()`` resolved; does not search the filesystem.
    """
    return Path.cwd().resolve()


def _require_executable(path: Path, *, origin: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"{origin} does not point to a file: {path}")
    if not os.access(path, os.X_OK):
        raise FileNotFoundError(f"{origin} is not executable: {path}")
    return path.resolve()


def product_bin(*, root: Path | None = None) -> Path:
    """Locate the recipe-built product binary and return its absolute path.

    Resolution order:
      1. ``PRODUCT_BIN`` environment variable, if set.
      2. ``<root>/bin/git-orbulk`` (Makefile default goal).

    Does not fall back to ``PATH``. A system-installed binary would hide a
    recipe-build shortfall.

    Raises:
        FileNotFoundError: when no executable exists at the resolved path.
            That is a substrate gap, not a product-behavior judgment.
    """
    override = os.environ.get(PRODUCT_BIN_ENV)
    if override:
        return _require_executable(
            Path(override).expanduser(), origin=PRODUCT_BIN_ENV
        )

    base = root if root is not None else repo_root()
    path = (Path(base) / BIN_RELPATH).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"product binary not found at {path}; "
            "the runner build must produce bin/git-orbulk before tests run"
        )
    if not os.access(path, os.X_OK):
        raise FileNotFoundError(f"product binary is not executable: {path}")
    return path


def product_bin_dir(*, root: Path | None = None) -> Path:
    """Return the directory that must precede ``PATH`` so Git finds the binary.

    Uses the parent of :func:`product_bin` when that file exists; otherwise
    ``<root>/bin`` so an isolated environment can still be built before a
    caller attempts an invoke.
    """
    override = os.environ.get(PRODUCT_BIN_ENV)
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path.resolve().parent
        return path.resolve() if path.suffix == "" else path.parent.resolve()
    base = root if root is not None else repo_root()
    return (Path(base) / BIN_RELPATH.parent).resolve()


def git_executable(*, env: Mapping[str, str] | None = None) -> str:
    """Locate the ``git`` binary used as the Git-extension substrate.

    Returns:
        Absolute path to the executable, as a string.

    Raises:
        FileNotFoundError: when ``git`` is not on ``PATH``. That is a
            substrate gap, not a product-behavior judgment.
    """
    search_path = (env or os.environ).get("PATH")
    found = shutil.which("git", path=search_path)
    if found is None:
        raise FileNotFoundError(
            "git executable not found on PATH; the product is a Git "
            "extension and requires a real Git installation"
        )
    return found


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
    """Build an environment that does not inherit the caller's Git/home state.

    Copies *base* (or ``os.environ``), points ``HOME`` and the XDG dirs at
    *home*, prepends the product ``bin/`` directory to ``PATH``, unsets the
    Git / editor / product keys that would couple a child to the parent,
    sets ``GIT_CONFIG_NOSYSTEM=1`` and ``GIT_TERMINAL_PROMPT=0``, and
    applies *updates* last (``None`` unsets). Does not mutate ``os.environ``.

    Returns a new ``dict``.
    """
    home_path = Path(home).resolve()
    cfg_dir = home_path / ".config"
    cache_dir = home_path / ".cache"
    data_dir = home_path / ".local" / "share"
    gitconfig = home_path / ".gitconfig"
    for directory in (home_path, cfg_dir, cache_dir, data_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if not gitconfig.exists():
        gitconfig.write_text("", encoding="utf-8")

    env = dict(base) if base is not None else dict(os.environ)
    for key in _ISOLATE_UNSET:
        env.pop(key, None)
    for key in list(env):
        if key.startswith(_ISOLATE_PREFIXES):
            env.pop(key, None)

    bin_dir = str(product_bin_dir(root=root))
    path_entries = [bin_dir]
    existing_path = env.get("PATH", "")
    if existing_path:
        path_entries.extend(
            part for part in existing_path.split(os.pathsep) if part and part != bin_dir
        )
    env["PATH"] = os.pathsep.join(path_entries)

    env["HOME"] = str(home_path)
    env["XDG_CONFIG_HOME"] = str(cfg_dir)
    env["XDG_CACHE_HOME"] = str(cache_dir)
    env["XDG_DATA_HOME"] = str(data_dir)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = _GIT_AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = _GIT_AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = _GIT_AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = _GIT_AUTHOR_EMAIL
    env.setdefault("LANG", "C.UTF-8")
    env.setdefault("LC_ALL", "C.UTF-8")

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
    encoding: str = "utf-8",
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


def read_file(path: str | Path, *, encoding: str = "utf-8") -> str:
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
        input_bytes = stdin.encode("utf-8")
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


def invoke(
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
    """Invoke the product binary as ``git-orbulk *args``.

    When *binary* is omitted, uses :func:`product_bin`. When *isolate* is
    true (the default) and *cwd* / *env* are omitted, the process runs in
    a fresh :func:`workspace` so it cannot see the caller's cwd or HOME.
    Pass ``isolate=False`` (and optionally *cwd* / *env*) to inherit the
    caller's process state, or to reuse a :class:`Workspace`.

    Returns a :class:`RunResult`. Does not raise on a non-zero product
    exit — that status is the observation.
    """
    exe = Path(binary) if binary is not None else product_bin(root=root)
    argv = [str(exe), *_normalize_args(args)]

    if cwd is not None or env is not None or not isolate:
        return run_command(
            argv, cwd=cwd, env=env, stdin=stdin, timeout=timeout
        )

    with workspace(root=root) as ws:
        return run_command(
            argv, cwd=ws.path, env=ws.env, stdin=stdin, timeout=timeout
        )


def invoke_via_git(
    args: Sequence[str] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    git: str | Path | None = None,
    isolate: bool = True,
) -> RunResult:
    """Invoke the product as a Git extension: ``git orbulk *args``.

    Git locates ``git-orbulk`` on ``PATH``. Isolated calls prepend the recipe
    ``bin/`` directory so the built binary is the one Git finds. When
    *isolate* is true (the default) and *cwd* / *env* are omitted, the
    process runs in a fresh :func:`workspace`.

    Returns a :class:`RunResult`. Does not raise on a non-zero exit.
    """

    def _run(child_cwd: str | Path | None, child_env: Mapping[str, str] | None) -> RunResult:
        git_exe = str(git) if git is not None else git_executable(env=child_env)
        argv = [git_exe, GIT_EXTENSION, *_normalize_args(args)]
        return run_command(
            argv, cwd=child_cwd, env=child_env, stdin=stdin, timeout=timeout
        )

    if cwd is not None or env is not None or not isolate:
        return _run(cwd, env)

    with workspace(root=root) as ws:
        return _run(ws.path, ws.env)


def run_git(
    args: Sequence[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | str | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    git: str | Path | None = None,
    isolate: bool = True,
    root: Path | None = None,
) -> RunResult:
    """Run ``git *args`` as substrate, not as the product.

    Isolated calls use a fresh :func:`workspace` so Git config and
    discovery cannot see the caller's home. Does not raise on a non-zero
    Git exit — callers that need a classified substrate outcome (init,
    config lookup) use the helpers that wrap this.
    """
    tokens = _normalize_args(args)
    if not tokens:
        raise ValueError("git argv must include a subcommand")

    def _run(child_cwd: str | Path | None, child_env: Mapping[str, str] | None) -> RunResult:
        git_exe = str(git) if git is not None else git_executable(env=child_env)
        return run_command(
            [git_exe, *tokens],
            cwd=child_cwd,
            env=child_env,
            stdin=stdin,
            timeout=timeout,
        )

    if cwd is not None or env is not None or not isolate:
        return _run(cwd, env)

    with workspace(root=root) as ws:
        return _run(ws.path, ws.env)


def git_config_get(
    key: str,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    local: bool = False,
    global_: bool = False,
    file: str | Path | None = None,
    git: str | Path | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> str | None:
    """Read one Git configuration value.

    Uses ``git config --get``. Git documents exit status 0 as "a value
    was found" and 1 as "not found". This helper maps those two statuses
    and hard-fails every other outcome:

    * ``0`` — return the value with a single trailing newline stripped.
      An empty string is a found empty value, not absence.
    * ``1`` — return ``None`` (the key is unset in the queried file).
    * any other status, or a launch failure — raise :class:`HarnessError`
      with Git's stderr. Never returns ``None`` to mean "the probe crashed".
    """
    argv: list[str] = ["config"]
    if file is not None:
        argv.extend(["--file", str(file)])
    elif local:
        argv.append("--local")
    elif global_:
        argv.append("--global")
    argv.extend(["--get", key])
    result = run_git(
        argv,
        cwd=cwd,
        env=env,
        git=git,
        timeout=timeout,
        isolate=False,
    )
    if result.returncode == 0:
        text = result.stdout_text
        if text.endswith("\n"):
            text = text[:-1]
        return text
    if result.returncode == 1:
        return None
    raise HarnessError(
        f"git config --get {key!r} failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )


def git_config_set(
    key: str,
    value: str,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    local: bool = False,
    global_: bool = False,
    file: str | Path | None = None,
    git: str | Path | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
) -> RunResult:
    """Write one Git configuration value via ``git config``.

    Returns the :class:`RunResult`. Does not raise on a non-zero Git
    exit — the caller decides whether a failed write is a substrate
    problem. :meth:`Workspace.init_repo` is the helper that treats a
    failed identity write as unclassified.
    """
    argv: list[str] = ["config"]
    if file is not None:
        argv.extend(["--file", str(file)])
    elif local:
        argv.append("--local")
    elif global_:
        argv.append("--global")
    argv.extend([key, value])
    return run_git(
        argv,
        cwd=cwd,
        env=env,
        git=git,
        timeout=timeout,
        isolate=False,
    )


# ---------------------------------------------------------------------------
# Loopback HTTP lifecycle (optional; the product is a client)
# ---------------------------------------------------------------------------


@contextmanager
def loopback_http(
    handler: type[BaseHTTPRequestHandler],
    *,
    host: str = "127.0.0.1",
) -> Iterator[HttpService]:
    """Bind a loopback HTTP server with *handler* and stop it on exit.

    Listens on ``host`` port 0 (ephemeral). Yields an :class:`HttpService`
    whose ``url`` is ``http://<host>:<port>``. The serve loop runs in a
    daemon thread. Shutdown runs even if the body raises.

    Raises:
        HarnessError: if the bind fails. Does not interpret HTTP responses
            — that is the caller's observation of whatever handler they
            supplied.
    """
    try:
        httpd = ThreadingHTTPServer((host, 0), handler)
    except OSError as exc:
        raise HarnessError(f"cannot bind loopback HTTP on {host}: {exc}") from exc
    bound_host, bound_port = httpd.server_address[:2]
    thread = threading.Thread(
        target=httpd.serve_forever,
        name="harness-loopback-http",
        daemon=True,
    )
    thread.start()
    service = HttpService(
        host=str(bound_host),
        port=int(bound_port),
        url=f"http://{bound_host}:{bound_port}",
        httpd=httpd,
        _thread=thread,
    )
    print(
        f"[harness] loopback http url={service.url}",
        flush=True,
    )
    try:
        yield service
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5.0)


def reserve_loopback_port(*, host: str = "127.0.0.1") -> int:
    """Bind an ephemeral loopback port, close it, and return the port number.

    The port is free at the moment this returns; a later bind can still
    race. Prefer :func:`loopback_http` when a live listener is needed.

    Raises:
        HarnessError: if the bind fails.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, 0))
            port = int(sock.getsockname()[1])
    except OSError as exc:
        raise HarnessError(
            f"cannot reserve loopback port on {host}: {exc}"
        ) from exc
    if port <= 0:
        raise HarnessError(f"loopback bind returned a non-positive port: {port}")
    return port
