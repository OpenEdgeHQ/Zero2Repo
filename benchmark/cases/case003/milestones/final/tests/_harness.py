# feature: F00
"""Shared machinery for driving the product through its public surface.

Suites import from this module (``from _harness import ...``). Importing it
performs no I/O, starts no processes, and opens no sockets. Process spawn,
filesystem writes, and environment replacement happen only when a caller
invokes a function or enters a context manager below.

The product is a JavaScript library (parse one document, parse every
document, serialize one value) plus a convenience CLI that applies the
same parse-and-dump behaviour to a file. It is not an importable Python
package. Python tests reach the library by spawning the recipe-provided
Node interpreter against the locally built module, and reach the CLI by
spawning that same interpreter on the recipe-built CLI entry.

Surfaces
--------
* Library call — :func:`load`, :func:`load_all`, :func:`dump`,
  :func:`library_call`. Named public exports run in a fresh Node process
  with caller-controlled options. Schema names and extra tag names are
  resolved against the module's named exports; unknown names are a
  harness failure, not a product refusal.
* Library script — :func:`evaluate`. Caller-supplied JavaScript runs
  with the product module bound as ``lib``. Use this when the call
  needs values the Python side cannot construct (custom tags, a ``Map``
  with object keys, a function, a cycle).
* CLI — :func:`run_cli`. Spawns the convenience binary. Missing CLI is
  a substrate gap.

Each library invocation is a new process, so one call cannot leak
schema, anchors, or global state into another. A product throw is a
classified outcome on :class:`CallResult`, not a harness failure.
Observation failures this module cannot classify raise
:class:`HarnessError`.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

# ---------------------------------------------------------------------------
# Public defaults / env overrides
# ---------------------------------------------------------------------------

DEFAULT_CHARSET = "utf-8"
DEFAULT_TIMEOUT = 60.0

PRODUCT_ROOT_ENV = "PRODUCT_ROOT"
PRODUCT_MODULE_ENV = "PRODUCT_MODULE"
PRODUCT_BIN_ENV = "PRODUCT_BIN"
PRODUCT_NODE_ENV = "PRODUCT_NODE"

# Named built-in schemas (public exports). Pass these as the ``schema``
# option; the driver resolves them on the imported module.
SCHEMA_FAILSAFE = "FAILSAFE_SCHEMA"
SCHEMA_JSON = "JSON_SCHEMA"
SCHEMA_CORE = "CORE_SCHEMA"
SCHEMA_YAML11 = "YAML11_SCHEMA"

# Public parse / dump entries.
ENTRY_LOAD = "load"
ENTRY_LOAD_ALL = "loadAll"
ENTRY_DUMP = "dump"

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
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
)

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
    "NODE_OPTIONS",
    "NODE_PATH",
    "NODE_REPL_HISTORY",
    "npm_config_prefix",
    "npm_config_registry",
    "EDITOR",
    "VISUAL",
    "PAGER",
    "DISPLAY",
    "WAYLAND_DISPLAY",
)


# ---------------------------------------------------------------------------
# Errors / result types
# ---------------------------------------------------------------------------


class HarnessError(RuntimeError):
    """Raised when an observation cannot be classified.

    Used for a missing Node interpreter, a missing built module, a
    driver that did not write a well-formed report, a workspace path
    that escapes its root, a timeout, and I/O failures that are not a
    documented product outcome. Never used to mean "the product refused
    a parse or a dump".
    """


@dataclass(frozen=True)
class MarkInfo:
    """Source-location fields from a product failure report.

    ``line`` and ``column`` are copied as the product emitted them
    (zero-based in this library). ``name`` is the source-path label
    when one was supplied. Missing fields stay ``None`` — never ``""``
    as a stand-in for "the driver could not read the mark".
    """

    name: str | None
    line: int | None
    column: int | None
    position: int | None


@dataclass(frozen=True)
class ErrorInfo:
    """A thrown value captured from the product process.

    Attributes:
        name: ``error.name`` as observed (empty string if the throw
            had no name property).
        message: ``error.message`` as observed.
        reason: ``error.reason`` when present, else ``None``.
        mark: Parsed mark object, or ``None`` when the throw had no
            mark. Absence of a mark is not the same as a mark whose
            name is empty.
        stack: ``error.stack`` when present, else ``None``.
        text: ``String(error)`` as observed.
    """

    name: str
    message: str
    reason: str | None
    mark: MarkInfo | None
    stack: str | None
    text: str


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
class JsObject:
    """A constructed mapping observed from the library.

    ``props`` holds own data properties, including an own
    ``__proto__`` key when the product stored one. ``proto`` is
    ``"object"`` when the prototype is the ordinary object prototype,
    ``"null"`` when the prototype is ``null``, otherwise ``"other"``.
    ``in_keys`` is the list of enumerable keys from a ``for...in``
    walk (includes inherited enumerable names).
    """

    props: dict[str, Any]
    object_id: int
    own_names: tuple[str, ...]
    in_keys: tuple[str, ...]
    proto: str

    def __getitem__(self, key: str) -> Any:
        return self.props[key]

    def __contains__(self, key: object) -> bool:
        return key in self.props

    def get(self, key: str, default: Any = None) -> Any:
        return self.props.get(key, default)

    def keys(self):
        return self.props.keys()

    def items(self):
        return self.props.items()

    def values(self):
        return self.props.values()

    def has_own(self, key: str) -> bool:
        return key in self.own_names

    def visible(self, key: str) -> bool:
        """Whether ``key`` appeared in a ``for...in`` walk."""
        return key in self.in_keys


@dataclass
class JsMap:
    """A constructed ``Map`` observed from the library."""

    entries: list[tuple[Any, Any]]
    object_id: int

    def __len__(self) -> int:
        return len(self.entries)

    def keys(self) -> list[Any]:
        return [key for key, _ in self.entries]

    def values_list(self) -> list[Any]:
        return [value for _, value in self.entries]

    def get(self, key: Any, default: Any = None) -> Any:
        for item_key, item_value in self.entries:
            if item_key == key:
                return item_value
        return default


@dataclass
class JsSet:
    """A constructed ``Set`` observed from the library."""

    items: list[Any]
    object_id: int

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, item: object) -> bool:
        return item in self.items


@dataclass
class JsDate:
    """A constructed date value observed from the library."""

    epoch_ms: float
    iso: str
    object_id: int


@dataclass
class JsBytes:
    """A constructed 8-bit byte array observed from the library."""

    data: bytes
    object_id: int

    def __len__(self) -> int:
        return len(self.data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, (bytes, bytearray)):
            return self.data == bytes(other)
        if isinstance(other, JsBytes):
            return self.data == other.data
        return NotImplemented


@dataclass
class JsFunction:
    """A function value observed from the library (or sent for dump)."""

    name: str


@dataclass
class JsRegexp:
    """A regular-expression value observed or sent for dump."""

    source: str
    flags: str


class JsUndefined:
    """The JavaScript ``undefined`` value."""

    def __repr__(self) -> str:
        return "JsUndefined"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, JsUndefined)


UNDEFINED = JsUndefined()


@dataclass
class CallResult:
    """Outcome of one library invocation.

    Attributes:
        ok: ``True`` when the product returned a value; ``False`` when
            it threw. A driver / substrate failure never produces this
            object — it raises :class:`HarnessError`.
        value: Decoded return value. ``None`` is a legitimate product
            value (an empty document, an explicit null). On failure
            this is ``None`` and :attr:`error` is set.
        error: The thrown value, or ``None`` on success.
        stdout: Raw Node stdout (the product itself writes nothing
            here on the library path; leftover bytes are still kept).
        stderr: Raw Node stderr.
        returncode: Node process exit status. ``0`` is the driver
            completing its report; it is not a product-success signal
            — read :attr:`ok`.
        argv: Argument vector that was executed.
        cwd: Working directory used for the process.
    """

    ok: bool
    value: Any
    error: ErrorInfo | None
    stdout: bytes
    stderr: bytes
    returncode: int
    argv: tuple[str, ...]
    cwd: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def stdout_text(self) -> str:
        return decode_utf8(self.stdout, what="stdout")

    @property
    def stderr_text(self) -> str:
        return decode_utf8(self.stderr, what="stderr")


@dataclass
class Workspace:
    """Ephemeral work directory plus the isolated environment bound to it.

    ``path`` is the working directory for invokes. ``home`` is used as
    ``HOME`` so ``~`` expansion cannot see the caller's home. Both
    trees are removed when the allocating context exits.
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
        """Write *content* under this workspace, creating parents."""
        dest = self.resolve(relpath)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            dest.write_bytes(content)
        else:
            dest.write_text(content, encoding=encoding)
        return dest

    def read(self, relpath: str | Path, *, encoding: str = DEFAULT_CHARSET) -> str:
        """Read a text file under this workspace.

        Raises ``FileNotFoundError`` if the file does not exist — never
        returns an empty string or ``None`` to mean "missing".
        """
        return read_file(self.resolve(relpath), encoding=encoding)

    def read_bytes(self, relpath: str | Path) -> bytes:
        """Read a binary file under this workspace.

        Raises ``FileNotFoundError`` if the file does not exist — never
        returns empty bytes to mean "missing".
        """
        return read_bytes(self.resolve(relpath))

    def load(
        self,
        source: str,
        options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> CallResult:
        """Single-document parse with this workspace as cwd and env."""
        return load(
            source,
            options,
            cwd=self.path,
            env=self.env,
            isolate=False,
            **kwargs,
        )

    def load_all(
        self,
        source: str,
        options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> CallResult:
        """Multi-document parse with this workspace as cwd and env."""
        return load_all(
            source,
            options,
            cwd=self.path,
            env=self.env,
            isolate=False,
            **kwargs,
        )

    def dump(
        self,
        value: Any,
        options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> CallResult:
        """Serialize *value* with this workspace as cwd and env."""
        return dump(
            value,
            options,
            cwd=self.path,
            env=self.env,
            isolate=False,
            **kwargs,
        )

    def evaluate(
        self,
        source: str,
        *,
        timeout: float | None = DEFAULT_TIMEOUT,
        env_updates: Mapping[str, str | None] | None = None,
        root: Path | None = None,
    ) -> CallResult:
        """Run a JavaScript body with this workspace as cwd and env."""
        env = _apply_updates(self.env, env_updates)
        return evaluate(
            source,
            cwd=self.path,
            env=env,
            timeout=timeout,
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
        """Run the convenience CLI with this workspace as cwd and env."""
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
        """Run *argv* with this workspace as cwd and env."""
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


def _read_regular_file(src: Path) -> None:
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


def _read_json_object(path: Path, *, what: str) -> dict[str, Any]:
    """Read a JSON object from *path*.

    Raises:
        FileNotFoundError: if the file does not exist.
        HarnessError: if the path is not a regular file, the bytes are
            not UTF-8, or the document is not a JSON object. Never
            returns ``{}`` to mean "unreadable".
    """
    raw = read_bytes(path)
    try:
        text = raw.decode(DEFAULT_CHARSET)
    except UnicodeDecodeError as exc:
        raise HarnessError(f"{what} is not valid UTF-8 ({exc})") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"{what} is not valid JSON ({exc}); body={text[:500]!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise HarnessError(
            f"{what} must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


# ---------------------------------------------------------------------------
# Paths / discovery
# ---------------------------------------------------------------------------


def repo_root() -> Path:
    """Return the built repository root.

    Tests run with the repository root as the pytest process cwd
    (recipe build artifacts such as the bundled module are available
    there). ``PRODUCT_ROOT`` overrides cwd. Does not search parents.
    """
    override = os.environ.get(PRODUCT_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd().resolve()


def _package_manifest(*, root: Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else repo_root()
    manifest = (base / "package.json").resolve()
    return _read_json_object(manifest, what=f"package manifest {manifest}")


def library_module(*, root: Path | None = None) -> Path:
    """Locate the recipe-built library module (ESM entry).

    Resolution order:
      1. ``PRODUCT_MODULE`` if set.
      2. ``package.json`` ``exports["."].import``, then ``module``.

    Does not fall back to a globally installed copy.

    Raises:
        FileNotFoundError: when no module file exists at a resolved
            path. That is a substrate gap, not a product-behavior
            judgment.
        HarnessError: when the manifest cannot be read or does not
            name an import entry.
    """
    override = os.environ.get(PRODUCT_MODULE_ENV)
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"{PRODUCT_MODULE_ENV} does not point to a file: {path}"
            )
        return path

    base = Path(root) if root is not None else repo_root()
    pkg = _package_manifest(root=base)
    rel: str | None = None
    exports = pkg.get("exports")
    if isinstance(exports, dict):
        dot = exports.get(".")
        if isinstance(dot, dict):
            import_rel = dot.get("import")
            if isinstance(import_rel, str):
                rel = import_rel
        elif isinstance(dot, str):
            rel = dot
    if rel is None:
        module_rel = pkg.get("module")
        if isinstance(module_rel, str):
            rel = module_rel
    if rel is None:
        raise HarnessError(
            f"package manifest at {base / 'package.json'} does not name "
            "an ESM import entry under exports['.'].import or module"
        )
    path = (base / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"recipe-built library module not found at {path}; the "
            "runner build must produce the ESM artifact before tests run"
        )
    return path


def cli_bin(*, root: Path | None = None) -> Path:
    """Locate the recipe-built convenience CLI entry.

    Resolution order:
      1. ``PRODUCT_BIN`` if set.
      2. The sole (or first) path in ``package.json`` ``bin``.

    Raises:
        FileNotFoundError: when the entry is missing.
        HarnessError: when the manifest cannot be read or has no bin.
    """
    override = os.environ.get(PRODUCT_BIN_ENV)
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"{PRODUCT_BIN_ENV} does not point to a file: {path}"
            )
        return path

    base = Path(root) if root is not None else repo_root()
    pkg = _package_manifest(root=base)
    bin_field = pkg.get("bin")
    rel: str | None = None
    if isinstance(bin_field, str):
        rel = bin_field
    elif isinstance(bin_field, dict) and bin_field:
        first = next(iter(bin_field.values()))
        if isinstance(first, str):
            rel = first
    if rel is None:
        raise HarnessError(
            f"package manifest at {base / 'package.json'} does not name a bin entry"
        )
    path = (base / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"convenience CLI not found at {path}"
        )
    return path


def node_bin() -> str:
    """Return the Node interpreter used to load the product.

    Uses ``$PRODUCT_NODE`` when set, otherwise ``node`` on ``PATH``.
    Does not spawn the interpreter. A missing binary is reported when
    a call runs, not here.
    """
    override = os.environ.get(PRODUCT_NODE_ENV)
    if override:
        return override
    return "node"


# ---------------------------------------------------------------------------
# Environment / workspace isolation
# ---------------------------------------------------------------------------


def isolated_environ(
    home: Path | str,
    *,
    updates: Mapping[str, str | None] | None = None,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an environment that does not inherit caller proxy / Node state.

    Starts from a small keep-list of substrate keys taken from *base*
    or ``os.environ``, points ``HOME`` and the XDG dirs at *home*,
    unsets proxy / ``NODE_OPTIONS`` / ``NODE_PATH``, and applies
    *updates* last (``None`` unsets). Does not mutate ``os.environ``.
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

    if updates:
        env = _apply_updates(env, updates)
    return env


@contextmanager
def in_directory(path: str | Path) -> Iterator[Path]:
    """Change the process cwd to *path* and restore it on exit."""
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
) -> Iterator[Workspace]:
    """Allocate an ephemeral work directory and isolated HOME; clean up.

    Yields a :class:`Workspace`. Both directory trees are removed when
    the context exits, including on exception. The product tree is
    never used as the default cwd.
    """
    work = Path(tempfile.mkdtemp(prefix=prefix))
    home = Path(tempfile.mkdtemp(prefix="harness-home-"))
    try:
        env = isolated_environ(home, updates=updates)
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
    """Write *content* to *path*, creating parent directories."""
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
    returns an empty string or ``None`` to mean "missing".
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
    returns empty bytes to mean "missing".
    """
    src = Path(path)
    _read_regular_file(src)
    try:
        return src.read_bytes()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot read {src}: {exc}") from exc


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
    When *cwd* is ``None``, the repository root is used.

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
    """Spawn the convenience CLI via the Node interpreter.

    Does not raise on a non-zero product exit. Raises
    ``FileNotFoundError`` if the CLI entry or Node is missing.
    """
    entry = Path(binary).resolve() if binary is not None else cli_bin(root=root)
    argv = [node_bin(), str(entry), *tuple(str(a) for a in (args or ()))]
    if isolate and env is None:
        with workspace() as ws:
            return run_command(
                argv,
                cwd=cwd if cwd is not None else ws.path,
                env=ws.env,
                stdin=stdin,
                timeout=timeout,
            )
    return run_command(
        argv,
        cwd=cwd,
        env=env,
        stdin=stdin,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Value codec (Python ↔ driver wire format)
# ---------------------------------------------------------------------------


def encode_value(value: Any) -> Any:
    """Encode a Python value as the driver wire format.

    Used to send dump inputs and evaluate bindings. Types the product
    does not accept (a function, a regexp) are tagged so the driver
    reconstructs the corresponding JavaScript value.
    """
    if value is None:
        return {"$type": "null"}
    if isinstance(value, JsUndefined):
        return {"$type": "undefined"}
    if isinstance(value, bool):
        return {"$type": "bool", "value": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"$type": "number", "value": value}
    if isinstance(value, float):
        if math.isnan(value):
            return {"$type": "nan"}
        if math.isinf(value):
            return {"$type": "inf", "sign": -1 if value < 0 else 1}
        if value == 0.0 and math.copysign(1.0, value) < 0:
            return {"$type": "number", "value": 0, "negative_zero": True}
        return {"$type": "number", "value": value}
    if isinstance(value, str):
        return {"$type": "string", "value": value}
    if isinstance(value, (bytes, bytearray)):
        return {"$type": "bytes", "hex": bytes(value).hex()}
    if isinstance(value, JsBytes):
        return {"$type": "bytes", "hex": value.data.hex()}
    if isinstance(value, JsDate):
        return {"$type": "date", "ms": value.epoch_ms}
    if isinstance(value, JsMap):
        return {
            "$type": "map",
            "entries": [
                [encode_value(key), encode_value(item)]
                for key, item in value.entries
            ],
        }
    if isinstance(value, JsSet):
        return {"$type": "set", "values": [encode_value(item) for item in value.items]}
    if isinstance(value, JsFunction):
        return {"$type": "function", "name": value.name}
    if isinstance(value, JsRegexp):
        return {"$type": "regexp", "source": value.source, "flags": value.flags}
    if isinstance(value, JsObject):
        return {
            "$type": "object",
            "props": [[key, encode_value(item)] for key, item in value.props.items()],
        }
    if isinstance(value, dict):
        return {
            "$type": "object",
            "props": [[str(key), encode_value(item)] for key, item in value.items()],
        }
    if isinstance(value, (list, tuple)):
        return {"$type": "array", "items": [encode_value(item) for item in value]}
    raise HarnessError(
        f"cannot encode value of type {type(value).__name__} for the driver"
    )


def _require_type_tag(node: Any, *, path: str) -> str:
    if not isinstance(node, dict):
        raise HarnessError(
            f"encoded value at {path} is not an object: {type(node).__name__}"
        )
    tag = node.get("$type")
    if not isinstance(tag, str) or not tag:
        raise HarnessError(f"encoded value at {path} has no $type tag: {node!r}")
    return tag


def decode_value(node: Any) -> Any:
    """Decode a driver wire value into a Python observation.

    Shared object identities (aliases, cycles) become the same Python
    object. A missing ``$type``, an unknown tag, or a dangling ref
    raises :class:`HarnessError` — never a silent ``None``.
    """
    table: dict[int, Any] = {}

    def walk(item: Any, path: str) -> Any:
        tag = _require_type_tag(item, path=path)
        if tag == "ref":
            oid = item.get("id")
            if not isinstance(oid, int):
                raise HarnessError(f"ref at {path} has no integer id")
            if oid not in table:
                raise HarnessError(f"unknown object id {oid} at {path}")
            return table[oid]
        if tag == "null":
            return None
        if tag == "undefined":
            return UNDEFINED
        if tag == "bool":
            return bool(item["value"])
        if tag == "string":
            return str(item["value"])
        if tag == "number":
            number = item["value"]
            if item.get("negative_zero"):
                return -0.0
            if isinstance(number, int):
                return number
            return float(number)
        if tag == "nan":
            return float("nan")
        if tag == "inf":
            sign = item.get("sign", 1)
            return float("inf") if sign >= 0 else float("-inf")
        if tag == "function":
            return JsFunction(name=str(item.get("name") or ""))
        if tag == "regexp":
            return JsRegexp(
                source=str(item.get("source") or ""),
                flags=str(item.get("flags") or ""),
            )
        if tag == "other":
            return {
                "$unobserved": str(item.get("name") or "unknown"),
                "preview": str(item.get("preview") or ""),
            }

        oid = item.get("id")
        if tag == "array":
            result: list[Any] = []
            if isinstance(oid, int):
                table[oid] = result
            raw_items = item.get("items")
            if not isinstance(raw_items, list):
                raise HarnessError(f"array at {path} has no items list")
            result.extend(
                walk(child, f"{path}[{index}]")
                for index, child in enumerate(raw_items)
            )
            return result
        if tag == "object":
            props: dict[str, Any] = {}
            own_names = tuple(str(n) for n in item.get("own_names") or ())
            in_keys = tuple(str(n) for n in item.get("in_keys") or ())
            proto = str(item.get("proto") or "other")
            obj = JsObject(
                props=props,
                object_id=int(oid) if isinstance(oid, int) else -1,
                own_names=own_names,
                in_keys=in_keys,
                proto=proto,
            )
            if isinstance(oid, int):
                table[oid] = obj
            raw_props = item.get("props")
            if not isinstance(raw_props, list):
                raise HarnessError(f"object at {path} has no props list")
            for index, pair in enumerate(raw_props):
                if not isinstance(pair, list) or len(pair) != 2:
                    raise HarnessError(f"object prop at {path}[{index}] is not a pair")
                key = str(pair[0])
                props[key] = walk(pair[1], f"{path}.{key}")
            if not own_names:
                obj.own_names = tuple(props.keys())
            return obj
        if tag == "map":
            entries: list[tuple[Any, Any]] = []
            js_map = JsMap(
                entries=entries,
                object_id=int(oid) if isinstance(oid, int) else -1,
            )
            if isinstance(oid, int):
                table[oid] = js_map
            raw_entries = item.get("entries")
            if not isinstance(raw_entries, list):
                raise HarnessError(f"map at {path} has no entries list")
            for index, pair in enumerate(raw_entries):
                if not isinstance(pair, list) or len(pair) != 2:
                    raise HarnessError(f"map entry at {path}[{index}] is not a pair")
                entries.append(
                    (
                        walk(pair[0], f"{path}.key[{index}]"),
                        walk(pair[1], f"{path}.val[{index}]"),
                    )
                )
            return js_map
        if tag == "set":
            items: list[Any] = []
            js_set = JsSet(
                items=items,
                object_id=int(oid) if isinstance(oid, int) else -1,
            )
            if isinstance(oid, int):
                table[oid] = js_set
            raw_values = item.get("values")
            if not isinstance(raw_values, list):
                raise HarnessError(f"set at {path} has no values list")
            items.extend(
                walk(child, f"{path}[{index}]")
                for index, child in enumerate(raw_values)
            )
            return js_set
        if tag == "date":
            ms = item.get("ms")
            if not isinstance(ms, (int, float)):
                raise HarnessError(f"date at {path} has no ms")
            iso = str(item.get("iso") or "")
            js_date = JsDate(
                epoch_ms=float(ms),
                iso=iso,
                object_id=int(oid) if isinstance(oid, int) else -1,
            )
            if isinstance(oid, int):
                table[oid] = js_date
            return js_date
        if tag == "bytes":
            hex_text = item.get("hex")
            if not isinstance(hex_text, str):
                raise HarnessError(f"bytes at {path} has no hex")
            try:
                data = bytes.fromhex(hex_text)
            except ValueError as exc:
                raise HarnessError(f"bytes at {path} have invalid hex") from exc
            js_bytes = JsBytes(
                data=data,
                object_id=int(oid) if isinstance(oid, int) else -1,
            )
            if isinstance(oid, int):
                table[oid] = js_bytes
            return js_bytes
        raise HarnessError(f"unknown encoded type {tag!r} at {path}")

    return walk(node, "$")


def _decode_mark(raw: Any) -> MarkInfo | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise HarnessError(f"error mark is not an object: {raw!r}")
    name = raw.get("name")
    line = raw.get("line")
    column = raw.get("column")
    position = raw.get("position")
    return MarkInfo(
        name=str(name) if name is not None else None,
        line=int(line) if isinstance(line, int) else None,
        column=int(column) if isinstance(column, int) else None,
        position=int(position) if isinstance(position, int) else None,
    )


def _decode_error(raw: Any) -> ErrorInfo:
    if not isinstance(raw, dict):
        raise HarnessError(f"error payload is not an object: {raw!r}")
    return ErrorInfo(
        name=str(raw.get("name") or ""),
        message=str(raw.get("message") or ""),
        reason=None if raw.get("reason") is None else str(raw.get("reason")),
        mark=_decode_mark(raw.get("mark")),
        stack=None if raw.get("stack") is None else str(raw.get("stack")),
        text=str(raw.get("text") or ""),
    )


# ---------------------------------------------------------------------------
# Node driver (embedded; written to a temp file at call time)
# ---------------------------------------------------------------------------

_DRIVER_SOURCE = r"""
import { pathToFileURL } from 'node:url'
import { readFileSync, writeFileSync } from 'node:fs'

const moduleUrl = process.env.PRODUCT_MODULE_URL
const requestPath = process.env.HARNESS_REQUEST
const resultPath = process.env.HARNESS_RESULT

function writeReport (report) {
  writeFileSync(resultPath, JSON.stringify(report), 'utf8')
}

function harnessFail (message) {
  writeReport({ status: 'harness_error', message: String(message) })
  process.exit(2)
}

function encodeError (err) {
  if (err === null || typeof err !== 'object') {
    return {
      name: typeof err,
      message: String(err),
      reason: null,
      mark: null,
      stack: null,
      text: String(err)
    }
  }
  const markRaw = err.mark
  let mark = null
  if (markRaw && typeof markRaw === 'object') {
    mark = {
      name: markRaw.name == null ? null : String(markRaw.name),
      line: typeof markRaw.line === 'number' ? markRaw.line : null,
      column: typeof markRaw.column === 'number' ? markRaw.column : null,
      position: typeof markRaw.position === 'number' ? markRaw.position : null
    }
  }
  return {
    name: err.name == null ? '' : String(err.name),
    message: err.message == null ? '' : String(err.message),
    reason: err.reason == null ? null : String(err.reason),
    mark,
    stack: err.stack == null ? null : String(err.stack),
    text: String(err)
  }
}

function encodeValue (value) {
  const seen = new Map()
  let nextId = 1

  function walk (current) {
    if (current === null) return { $type: 'null' }
    if (current === undefined) return { $type: 'undefined' }
    const kind = typeof current
    if (kind === 'boolean') return { $type: 'bool', value: current }
    if (kind === 'string') return { $type: 'string', value: current }
    if (kind === 'number') {
      if (Number.isNaN(current)) return { $type: 'nan' }
      if (current === Infinity) return { $type: 'inf', sign: 1 }
      if (current === -Infinity) return { $type: 'inf', sign: -1 }
      if (Object.is(current, -0)) {
        return { $type: 'number', value: 0, negative_zero: true }
      }
      return { $type: 'number', value: current }
    }
    if (kind === 'bigint') return { $type: 'other', name: 'bigint', preview: String(current) }
    if (kind === 'symbol') return { $type: 'other', name: 'symbol', preview: String(current) }
    if (kind === 'function') {
      return { $type: 'function', name: current.name || '' }
    }
    if (kind !== 'object') {
      return { $type: 'other', name: kind, preview: String(current) }
    }
    if (seen.has(current)) return { $type: 'ref', id: seen.get(current) }
    const id = nextId++
    seen.set(current, id)

    if (current instanceof Date) {
      return { $type: 'date', id, ms: current.getTime(), iso: current.toISOString() }
    }
    if (current instanceof Uint8Array) {
      let hex = ''
      for (let i = 0; i < current.length; i++) {
        hex += current[i].toString(16).padStart(2, '0')
      }
      return { $type: 'bytes', id, hex }
    }
    if (current instanceof RegExp) {
      return { $type: 'regexp', id, source: current.source, flags: current.flags }
    }
    if (current instanceof Map) {
      const entries = []
      for (const [key, item] of current) {
        entries.push([walk(key), walk(item)])
      }
      return { $type: 'map', id, entries }
    }
    if (current instanceof Set) {
      const values = []
      for (const item of current) values.push(walk(item))
      return { $type: 'set', id, values }
    }
    if (Array.isArray(current)) {
      return { $type: 'array', id, items: current.map((item, i) => walk(item)) }
    }

    const ownNames = Object.getOwnPropertyNames(current)
    const inKeys = []
    for (const key in current) inKeys.push(key)
    const protoObj = Object.getPrototypeOf(current)
    let proto = 'other'
    if (protoObj === Object.prototype) proto = 'object'
    else if (protoObj === null) proto = 'null'

    const props = []
    for (const name of ownNames) {
      const desc = Object.getOwnPropertyDescriptor(current, name)
      if (desc && Object.prototype.hasOwnProperty.call(desc, 'value')) {
        props.push([name, walk(desc.value)])
      } else {
        props.push([name, { $type: 'other', name: 'accessor', preview: name }])
      }
    }
    return { $type: 'object', id, props, own_names: ownNames, in_keys: inKeys, proto }
  }

  return walk(value)
}

function hydrate (node, table) {
  if (node === null || typeof node !== 'object' || node.$type == null) {
    throw new Error('encoded value missing $type')
  }
  const tag = node.$type
  if (tag === 'ref') {
    if (!table.has(node.id)) throw new Error('unknown object id ' + node.id)
    return table.get(node.id)
  }
  if (tag === 'null') return null
  if (tag === 'undefined') return undefined
  if (tag === 'bool') return !!node.value
  if (tag === 'string') return String(node.value)
  if (tag === 'number') {
    if (node.negative_zero) return -0
    return node.value
  }
  if (tag === 'nan') return NaN
  if (tag === 'inf') return node.sign < 0 ? -Infinity : Infinity
  if (tag === 'function') {
    const fn = function () {}
    try { Object.defineProperty(fn, 'name', { value: node.name || '' }) } catch (_) {}
    return fn
  }
  if (tag === 'regexp') return new RegExp(node.source || '', node.flags || '')
  if (tag === 'date') {
    const d = new Date(node.ms)
    if (node.id != null) table.set(node.id, d)
    return d
  }
  if (tag === 'bytes') {
    const hex = node.hex || ''
    const out = new Uint8Array(hex.length / 2)
    for (let i = 0; i < out.length; i++) {
      out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16)
    }
    if (node.id != null) table.set(node.id, out)
    return out
  }
  if (tag === 'array') {
    const arr = []
    if (node.id != null) table.set(node.id, arr)
    for (const child of node.items || []) arr.push(hydrate(child, table))
    return arr
  }
  if (tag === 'object') {
    const obj = {}
    if (node.id != null) table.set(node.id, obj)
    for (const pair of node.props || []) {
      Object.defineProperty(obj, pair[0], {
        value: hydrate(pair[1], table),
        enumerable: true,
        writable: true,
        configurable: true
      })
    }
    return obj
  }
  if (tag === 'map') {
    const map = new Map()
    if (node.id != null) table.set(node.id, map)
    for (const pair of node.entries || []) {
      map.set(hydrate(pair[0], table), hydrate(pair[1], table))
    }
    return map
  }
  if (tag === 'set') {
    const set = new Set()
    if (node.id != null) table.set(node.id, set)
    for (const child of node.values || []) set.add(hydrate(child, table))
    return set
  }
  throw new Error('unknown encoded type ' + tag)
}

function resolveExport (lib, name, what) {
  if (!Object.prototype.hasOwnProperty.call(lib, name)) {
    throw Object.assign(new Error(what + ' export not found: ' + name), {
      name: 'HarnessError'
    })
  }
  return lib[name]
}

function buildOptions (lib, options) {
  if (options == null) return undefined
  const opts = { ...options }
  const extraTags = opts.extra_tags
  delete opts.extra_tags
  if (opts.schema != null && typeof opts.schema === 'string') {
    opts.schema = resolveExport(lib, opts.schema, 'schema')
  }
  if (extraTags != null) {
    if (opts.schema == null) {
      throw Object.assign(new Error('schema is required when extra_tags is set'), {
        name: 'HarnessError'
      })
    }
    if (!Array.isArray(extraTags)) {
      throw Object.assign(new Error('extra_tags must be an array of export names'), {
        name: 'HarnessError'
      })
    }
    const tags = extraTags.map((n) => resolveExport(lib, n, 'tag'))
    opts.schema = opts.schema.withTags(...tags)
  }
  return opts
}

if (!moduleUrl || !requestPath || !resultPath) {
  harnessFail('driver env PRODUCT_MODULE_URL / HARNESS_REQUEST / HARNESS_RESULT missing')
}

let request
try {
  request = JSON.parse(readFileSync(requestPath, 'utf8'))
} catch (err) {
  harnessFail('cannot read request: ' + err)
}

let lib
try {
  lib = await import(moduleUrl)
} catch (err) {
  harnessFail('cannot import product module: ' + (err && err.stack ? err.stack : err))
}

try {
  let value
  if (request.op === 'call') {
    const entry = request.entry
    const fn = lib[entry]
    if (typeof fn !== 'function') {
      throw Object.assign(
        new Error('public entry is not a function: ' + String(entry)),
        { name: 'HarnessError' }
      )
    }
    const args = (request.args || []).map((item) => hydrate(item, new Map()))
    const opts = buildOptions(lib, request.options)
    if (opts !== undefined) args.push(opts)
    value = fn(...args)
  } else if (request.op === 'eval') {
    const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
    const body = request.source
    if (typeof body !== 'string') {
      throw Object.assign(new Error('eval source must be a string'), {
        name: 'HarnessError'
      })
    }
    let fn
    try {
      fn = new AsyncFunction('lib', body)
    } catch (err) {
      throw Object.assign(
        new Error('evaluate source is not valid JavaScript: ' + err),
        { name: 'HarnessError' }
      )
    }
    value = await fn(lib)
  } else {
    throw Object.assign(new Error('unknown driver op: ' + String(request.op)), {
      name: 'HarnessError'
    })
  }
  writeReport({ status: 'ok', value: encodeValue(value) })
} catch (err) {
  if (err && err.name === 'HarnessError') {
    harnessFail(err.message)
  }
  writeReport({ status: 'throw', error: encodeError(err) })
}
"""


def _write_driver(directory: Path) -> Path:
    dest = directory / "_product_driver.mjs"
    dest.write_text(_DRIVER_SOURCE.lstrip("\n"), encoding=DEFAULT_CHARSET)
    return dest


def _merge_options(
    options: Mapping[str, Any] | None,
    extra: Mapping[str, Any],
) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    if options:
        merged.update(options)
    for key, value in extra.items():
        if value is not None:
            merged[key] = value
    return merged or None


def _run_driver(
    request: dict[str, Any],
    *,
    cwd: str | Path | None,
    env: Mapping[str, str] | None,
    timeout: float | None,
    root: Path | None,
    isolate: bool,
) -> CallResult:
    module_path = library_module(root=root)
    module_url = module_path.resolve().as_uri()

    def _execute(work: Path, run_env: Mapping[str, str]) -> CallResult:
        driver = _write_driver(work)
        request_path = work / "_request.json"
        result_path = work / "_result.json"
        request_path.write_text(
            json.dumps(request, ensure_ascii=False),
            encoding=DEFAULT_CHARSET,
        )
        child_env = dict(run_env)
        child_env["PRODUCT_MODULE_URL"] = module_url
        child_env["HARNESS_REQUEST"] = str(request_path)
        child_env["HARNESS_RESULT"] = str(result_path)

        proc = run_command(
            [node_bin(), str(driver)],
            cwd=work,
            env=child_env,
            timeout=timeout,
        )
        if not result_path.is_file():
            raise HarnessError(
                "driver wrote no report; "
                f"exit={proc.returncode} "
                f"stderr={_diagnostic_text(proc.stderr)!r} "
                f"stdout={_diagnostic_text(proc.stdout)!r}"
            )
        report = _read_json_object(result_path, what="driver report")
        status = report.get("status")
        if status == "harness_error":
            message = report.get("message")
            raise HarnessError(
                f"driver failed: {message}; "
                f"stderr={_diagnostic_text(proc.stderr)!r}"
            )
        if status == "ok":
            if "value" not in report:
                raise HarnessError("driver ok report has no value field")
            value = decode_value(report["value"])
            return CallResult(
                ok=True,
                value=value,
                error=None,
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                argv=proc.argv,
                cwd=proc.cwd,
                raw=report,
            )
        if status == "throw":
            if "error" not in report:
                raise HarnessError("driver throw report has no error field")
            return CallResult(
                ok=False,
                value=None,
                error=_decode_error(report["error"]),
                stdout=proc.stdout,
                stderr=proc.stderr,
                returncode=proc.returncode,
                argv=proc.argv,
                cwd=proc.cwd,
                raw=report,
            )
        raise HarnessError(
            f"driver report has unclassified status {status!r}: {report!r}"
        )

    if isolate:
        with workspace() as ws:
            run_env = dict(env) if env is not None else ws.env
            return _execute(ws.path, run_env)
    if env is None:
        raise HarnessError("env is required when isolate is False")
    workdir = Path(cwd).resolve() if cwd is not None else repo_root()
    return _execute(workdir, env)


# ---------------------------------------------------------------------------
# Public library entries
# ---------------------------------------------------------------------------


def library_call(
    entry: str,
    args: Sequence[Any] | None = None,
    options: Mapping[str, Any] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    isolate: bool = True,
) -> CallResult:
    """Call a named public export in a fresh Node process.

    *args* are encoded and passed positionally. *options*, when not
    ``None``, is passed as the last argument after schema / extra-tag
    resolution:

    * ``schema`` — a string naming a module export
      (``FAILSAFE_SCHEMA``, ``JSON_SCHEMA``, ``CORE_SCHEMA``,
      ``YAML11_SCHEMA``).
    * ``extra_tags`` — a list of export names attached with
      ``schema.withTags(...)``. Requires ``schema``.

    A missing export, a non-function entry, or a driver failure raises
    :class:`HarnessError`. A throw from the product is
    ``CallResult(ok=False)``.
    """
    if not entry or not isinstance(entry, str):
        raise HarnessError("library entry name must be a non-empty string")
    encoded_args = [encode_value(arg) for arg in (args or ())]
    request: dict[str, Any] = {
        "op": "call",
        "entry": entry,
        "args": encoded_args,
        "options": dict(options) if options else None,
    }
    print(f"[harness] library_call entry={entry!r}", flush=True)
    return _run_driver(
        request,
        cwd=cwd,
        env=env,
        timeout=timeout,
        root=root,
        isolate=isolate,
    )


def evaluate(
    source: str,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    isolate: bool = True,
) -> CallResult:
    """Run *source* as the body of ``async function (lib) { ... }``.

    ``lib`` is the product module namespace. The function's return
    value is the observation. A syntax error in *source* is a harness
    failure. A throw while the body runs is a product outcome.

    One process per call: schema objects and custom tags constructed
    here do not survive into a later call.
    """
    if not isinstance(source, str):
        raise HarnessError("evaluate source must be a string")
    request = {"op": "eval", "source": source}
    print("[harness] evaluate", flush=True)
    return _run_driver(
        request,
        cwd=cwd,
        env=env,
        timeout=timeout,
        root=root,
        isolate=isolate,
    )


def load(
    source: str,
    options: Mapping[str, Any] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    isolate: bool = True,
    **kwargs: Any,
) -> CallResult:
    """Single-document parse entry.

    *kwargs* are merged into *options* (``schema``, ``filename``,
    ``json``, ``maxDepth``, ``maxAliases``, ``maxTotalMergeKeys``,
    ``extra_tags``). Does not raise on a product throw.
    """
    opts = _merge_options(options, kwargs)
    return library_call(
        ENTRY_LOAD,
        [source],
        opts,
        cwd=cwd,
        env=env,
        timeout=timeout,
        root=root,
        isolate=isolate,
    )


def load_all(
    source: str,
    options: Mapping[str, Any] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    isolate: bool = True,
    **kwargs: Any,
) -> CallResult:
    """Multi-document parse entry.

    Same options as :func:`load`. An empty stream is a successful
    empty list when the product says so; this helper does not
    reinterpret that outcome.
    """
    opts = _merge_options(options, kwargs)
    return library_call(
        ENTRY_LOAD_ALL,
        [source],
        opts,
        cwd=cwd,
        env=env,
        timeout=timeout,
        root=root,
        isolate=isolate,
    )


def dump(
    value: Any,
    options: Mapping[str, Any] | None = None,
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = DEFAULT_TIMEOUT,
    root: Path | None = None,
    isolate: bool = True,
    **kwargs: Any,
) -> CallResult:
    """Serialize one JavaScript value.

    *value* is encoded and reconstructed in the product process. Use
    :class:`JsMap`, :class:`JsSet`, :class:`JsDate`, :class:`JsBytes`,
    :data:`UNDEFINED`, or :func:`evaluate` for values a plain Python
    dict/list cannot express (object identity, functions).
    """
    opts = _merge_options(options, kwargs)
    return library_call(
        ENTRY_DUMP,
        [value],
        opts,
        cwd=cwd,
        env=env,
        timeout=timeout,
        root=root,
        isolate=isolate,
    )


# Alias matching the public JavaScript export name.
loadAll = load_all
