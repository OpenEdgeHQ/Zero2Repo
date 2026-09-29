# feature: F08
"""Observation helpers for the membundle validate command and membundle_validate tool (FP-08).

Helpers raise ``HarnessError`` when a query cannot be classified, and
``AssertionError`` when a classified observation misses a carrier the
tests require. They never return ``None`` / ``{}`` / ``""`` / ``[]`` /
``0`` to mean "could not look".
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn

from _harness import (
    HarnessError,
    McpBatchResult,
    RunResult,
    Workspace,
    json_stdout,
    parse_json,
    path_is_dir,
    rpc_request,
)
from F01_helpers import (
    combined_report,
    report_remainder_after_stripping_paths,
    strip_generated_covariates,
    unique_leaf,
)
from F03_helpers import (
    INDEX_MARKDOWN,
    _normalized_remainder,
    mcp_is_protocol_error,
    mcp_is_tool_error,
    mcp_payload_and_text,
    mcp_reply_for_id,
    path_tokens_for,
    record_string_values,
    unique_tokens,
)
from F05_helpers import SEED_LOG_DATE

_WRAP_PUNCT = re.compile(r"[\"'`\[\]\(\)\{\}<>*_.,:;]+")
_WHITESPACE = re.compile(r"\s+")

PASSING_AGENTS_TEXT = (
    "# 0. Domain Codex\n"
    "FORMAT: diagrams => ASSERT(syntax == mermaid)\n"
    "\n"
    "<!-- BEGIN MEMBUNDLE AGENT MEMORY -->\n"
    "MUST keep working memory in this block.\n"
    "<!-- END MEMBUNDLE AGENT MEMORY -->\n"
)
SSOT_LINKS = (
    ("CLAUDE.md", "AGENTS.md"),
    (".cursorrules", "AGENTS.md"),
    (".windsurfrules", "AGENTS.md"),
    (".github/copilot-instructions.md", "../AGENTS.md"),
)

# Recipe artifact name. The binary is built in a writable copy, not the judge cwd.
_BIN_REL = Path("bin") / "membundle"
_BUILD_LOCK = threading.Lock()
_BUILD_DONE = False
_BUILT_BIN: Path | None = None
_NEVER_EXECUTED = (
    "the call was never executed; validate results are missing"
)


def _workdir_has_product_sources(root: Path) -> bool:
    """True when *root* is a product tree whose Makefile writes ``bin/membundle``."""
    makefile = root / "Makefile"
    if not makefile.is_file() or not (root / "go.mod").is_file():
        return False
    text = makefile.read_text(encoding="utf-8")
    return "bin/membundle" in text


def _stage_writable_sources(root: Path) -> Path:
    """Copy *root* to a writable directory, excluding any existing binary.

    The judge cwd may be a read-only filesystem. ``make build`` must not
    run there, and a binary already present under that cwd must not be
    reused.
    """
    stage = Path(tempfile.mkdtemp(prefix="membundle-build-"))
    shutil.copytree(
        root,
        stage,
        symlinks=True,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "bin"),
    )
    # copytree preserves a read-only source mode, including on the stage
    # root, which then rejects mkdir bin. The copy itself must be writable.
    for dirpath, _dirnames, filenames in os.walk(stage):
        os.chmod(dirpath, os.stat(dirpath).st_mode | 0o700)
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            os.chmod(path, path.stat().st_mode | 0o600)
    prebuilt = stage / _BIN_REL
    if prebuilt.is_symlink() or prebuilt.exists():
        prebuilt.unlink()
    return stage


def _run_product_build(root: Path) -> bool:
    """Run ``GOFLAGS=-buildvcs=false make build`` in a writable source copy.

    *root* is not the judge cwd. Returns True only when ``make`` exits 0.
    A non-zero exit is logged and is not the test result. ``make`` itself
    missing is not a successful build. Does not search ``PATH`` or honor
    ``PRODUCT_BIN``.
    """
    env = dict(os.environ)
    env.pop("PRODUCT_BIN", None)
    env["GOFLAGS"] = "-buildvcs=false"
    print(f"[F08] GOFLAGS=-buildvcs=false make build cwd={root}", flush=True)
    try:
        completed = subprocess.run(
            ["make", "build"],
            cwd=str(root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        print(f"[F08] make build could not start: {exc}", flush=True)
        return False
    print(f"[F08] make build exit={completed.returncode}", flush=True)
    if completed.returncode != 0:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        print(
            f"[F08] make build stdout={stdout[-2000:]!r} "
            f"stderr={stderr[-2000:]!r}",
            flush=True,
        )
        return False
    return True


def _workdir_membundle() -> Path | None:
    """Return the ``bin/membundle`` this build just produced.

    When the pytest cwd contains the product sources, copies them to a
    writable directory and runs ``GOFLAGS=-buildvcs=false make build``
    there. Does not search ``PATH``, does not honor ``PRODUCT_BIN``, does
    not build in the judge cwd, and does not use a binary this build did
    not just produce. An empty cwd, or a build that does not produce an
    executable, returns None so the caller fails because the command
    results are missing.
    """
    global _BUILD_DONE, _BUILT_BIN
    with _BUILD_LOCK:
        if not _BUILD_DONE:
            root = Path.cwd().resolve()
            built: Path | None = None
            if _workdir_has_product_sources(root):
                stage = _stage_writable_sources(root)
                if _run_product_build(stage):
                    candidate = stage / _BIN_REL
                    resolved = candidate.resolve()
                    if (
                        candidate.is_file()
                        and os.access(candidate, os.X_OK)
                        and resolved.is_relative_to(stage.resolve())
                    ):
                        built = resolved
            _BUILT_BIN = built
            _BUILD_DONE = True
            print(f"[F08] resolved built binary={_BUILT_BIN!r}", flush=True)
        return _BUILT_BIN


def resolve_validate_binary() -> Path:
    """Single resolver for every F08 validate-command and validate-tool call.

    When the pytest cwd contains the product sources, copies those sources
    to a writable directory, runs ``GOFLAGS=-buildvcs=false make build``
    there, and returns only that ``bin/membundle``. When that executable
    is absent, fails the test. Does not return a synthetic status 0, 1,
    or 2 or a synthetic tool error: those are validate outcomes, and an
    empty workspace would then look like a failed gate or a load failure.
    """
    binary = _workdir_membundle()
    # TEST-FIX((none)): upstream Makefile:78 shows go build opens bin/membundle in the working directory and fails with "open bin/membundle: read-only file system" when that directory cannot accept the write, so validate never runs and its results are missing.
    assert binary is not None, _NEVER_EXECUTED
    return binary


def _raise_if_validate_binary_missing(binary: Path, exc: FileNotFoundError) -> NoReturn:
    """Turn a vanished workdir binary into the never-executed assertion."""
    if binary.is_file() and os.access(binary, os.X_OK):
        raise exc
    # TEST-FIX(F08): upstream _harness.py:620 shows FileNotFoundError before validate when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    raise AssertionError(_NEVER_EXECUTED) from None


@dataclass(frozen=True)
class McpValidateOutcome:
    """Classified JSON-RPC reply to one membundle_validate tools/call.

    A missing reply for the requested id raises ``HarnessError`` before
    this object is built. None of the fields is a sentinel for "no reply".
    """

    batch: McpBatchResult
    reply: dict[str, Any]
    payload: Any
    report_text: str


def utc_yesterday() -> str:
    """Yesterday's UTC calendar date as ISO 8601 ``YYYY-MM-DD``."""
    return (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()


def utc_tomorrow() -> str:
    """Tomorrow's UTC calendar date as ISO 8601 ``YYYY-MM-DD``."""
    return (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if text == "" or text != text.strip() or any(ch in text for ch in ":#{}[]&*!%@,?'\"\n"):
        return json.dumps(text)
    return text


def _emit_yaml(lines: list[str], key: str, value: Any, indent: int = 0) -> None:
    pad = "  " * indent
    if isinstance(value, Mapping):
        lines.append(f"{pad}{key}:")
        if not value:
            return
        for nested_key, nested in value.items():
            _emit_yaml(lines, str(nested_key), nested, indent + 1)
        return
    if isinstance(value, list):
        lines.append(f"{pad}{key}:")
        if not value:
            return
        for item in value:
            if isinstance(item, Mapping):
                first = True
                for nested_key, nested in item.items():
                    rendered = _yaml_scalar(nested) if not isinstance(nested, (Mapping, list)) else None
                    if first:
                        if rendered is not None:
                            lines.append(f"{pad}  - {nested_key}: {rendered}")
                        else:
                            lines.append(f"{pad}  - {nested_key}:")
                            if isinstance(nested, Mapping):
                                for inner_k, inner_v in nested.items():
                                    _emit_yaml(lines, str(inner_k), inner_v, indent + 3)
                        first = False
                    else:
                        if rendered is not None:
                            lines.append(f"{pad}    {nested_key}: {rendered}")
                        else:
                            _emit_yaml(lines, str(nested_key), nested, indent + 2)
            else:
                lines.append(f"{pad}  - {_yaml_scalar(item)}")
        return
    lines.append(f"{pad}{key}: {_yaml_scalar(value)}")


def render_membundle_markdown(*, body: str, frontmatter: Mapping[str, Any] | None) -> str:
    """Render a concept file the test writes. Does not call the product."""
    body_text = body if body.endswith("\n") else f"{body}\n"
    if frontmatter is None:
        return body_text
    lines = ["---"]
    for key, value in frontmatter.items():
        _emit_yaml(lines, str(key), value, 0)
    lines.append("---")
    return "\n".join(lines) + "\n" + body_text


def render_index_markdown(
    *,
    membundle_version: str | None = "0.2",
    listings: Sequence[tuple[str, str, str]] = (),
    extra_body: str = "",
) -> str:
    """Root index the test writes. ``membundle_version is None`` omits the declaration."""
    chunks: list[str] = []
    if membundle_version is not None:
        chunks.append("---")
        chunks.append(f"membundle_version: {membundle_version}")
        chunks.append("---")
        chunks.append("")
    chunks.append("# Bundle")
    chunks.append("")
    for title, href, description in listings:
        chunks.append(f"- [{title}]({href}) - {description}")
    if listings:
        chunks.append("")
    if extra_body:
        chunks.append(extra_body if extra_body.endswith("\n") else extra_body + "\n")
    return "\n".join(chunks) if chunks[-1].endswith("\n") else "\n".join(chunks) + "\n"


def default_validatable_log(log_date: str = SEED_LOG_DATE) -> str:
    """Two-hash ISO log heading that is not today (L46 / L236)."""
    return f"## {log_date}\n\n- seed\n"


def seed_validatable_bundle(
    ws: Workspace,
    rel: str | Path,
    concepts: Sequence[Mapping[str, Any]] = (),
    *,
    membundle_version: str | None = "0.2",
    log_date: str = SEED_LOG_DATE,
    log_markdown: str | None = None,
    index_markdown: str | None = None,
    listings: Sequence[tuple[str, str, str]] = (),
    agents: str | None = None,
) -> Path:
    """Write a loadable bundle. Does not call the product.

    Each concept mapping uses ``identity``, optional ``frontmatter`` (``None``
    means no YAML fences), ``body``, and optional ``raw`` to plant exact bytes.
    """
    root = ws.resolve(rel) if str(rel) not in ("", ".") else ws.path
    root.mkdir(parents=True, exist_ok=True)
    if index_markdown is not None:
        index_text = index_markdown
    elif membundle_version == "0.2" and not listings:
        index_text = INDEX_MARKDOWN
    else:
        index_text = render_index_markdown(membundle_version=membundle_version, listings=listings)
    (root / "index.md").write_text(index_text, encoding="utf-8")
    log_text = log_markdown if log_markdown is not None else default_validatable_log(log_date)
    (root / "log.md").write_text(log_text, encoding="utf-8")
    if agents is not None:
        (root / "AGENTS.md").write_text(agents, encoding="utf-8")
    for spec in concepts:
        identity = str(spec["identity"])
        if not identity or identity.startswith("/") or ".." in Path(identity).parts:
            raise HarnessError(f"refusing to write escaping identity {identity!r}")
        dest = root / f"{identity}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if "raw" in spec and spec["raw"] is not None:
            dest.write_text(str(spec["raw"]), encoding="utf-8")
            continue
        dest.write_text(
            render_membundle_markdown(
                body=str(spec.get("body", "body\n")),
                frontmatter=spec.get("frontmatter"),
            ),
            encoding="utf-8",
        )
    print(
        f"[F08] seeded validatable bundle {root} concepts={len(concepts)} "
        f"version={membundle_version!r}",
        flush=True,
    )
    return root


def fact_concept(
    identity: str,
    *,
    body: str = "body\n",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Type Fact with no other required fields (L256)."""
    frontmatter: dict[str, Any] = {"type": "Fact"}
    if extra:
        frontmatter.update(dict(extra))
    return {"identity": identity, "frontmatter": frontmatter, "body": body}


def run_validate(
    ws: Workspace,
    bundle: str | Path | None = None,
    *,
    strict: bool = False,
    stale: bool = False,
    drift: bool = False,
    agents: bool = False,
    structured: bool = False,
    extra_args: Sequence[str] = (),
    env_updates: dict[str, str | None] | None = None,
    cwd: str | Path | None = None,
) -> RunResult:
    """Invoke ``membundle validate`` with optional bundle path and caller options."""
    args: list[str] = ["validate"]
    if bundle is not None:
        args.append(str(bundle))
    if strict:
        args.append("--strict")
    if stale:
        args.append("--stale")
    if drift:
        args.append("--drift")
    if agents:
        args.append("--agents")
    if structured:
        args.append("--json")
    args.extend(str(a) for a in extra_args)
    print(
        f"[F08] validate argv={args!r} cwd={cwd!r} structured={structured}",
        flush=True,
    )
    binary = resolve_validate_binary()
    try:
        return ws.invoke(
            args, env_updates=env_updates, cwd=cwd, binary=binary
        )
    except FileNotFoundError as exc:
        _raise_if_validate_binary_missing(binary, exc)


def run_validate_structured(
    ws: Workspace,
    bundle: str | Path | None = None,
    **kwargs: Any,
) -> tuple[RunResult, Any]:
    """CLI ``--json`` validate. Raises if stdout is not parseable JSON."""
    kwargs.pop("structured", None)
    result = run_validate(ws, bundle, structured=True, **kwargs)
    payload = json_stdout(result, what="validate --json stdout")
    print(f"[F08] structured payload type={type(payload).__name__}", flush=True)
    return result, payload


def mcp_membundle_validate(
    ws: Workspace,
    arguments: Mapping[str, Any],
    *,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
    env_updates: dict[str, str | None] | None = None,
) -> McpValidateOutcome:
    """One ``membundle_validate`` tools/call. A missing reply for *request_id* raises."""
    lines = [
        rpc_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "f08-suite", "version": "0"},
            },
            id=1,
        ),
        rpc_request(
            "tools/call",
            {"name": "membundle_validate", "arguments": dict(arguments)},
            id=request_id,
        ),
    ]
    print(
        f"[F08] mcp membundle_validate arguments={dict(arguments)!r} id={request_id!r}",
        flush=True,
    )
    binary = resolve_validate_binary()
    try:
        batch = ws.mcp_batch(
            lines, cwd=cwd, env_updates=env_updates, binary=binary
        )
    except FileNotFoundError as exc:
        _raise_if_validate_binary_missing(binary, exc)
    reply = mcp_reply_for_id(batch, request_id)
    payload, report_text = mcp_payload_and_text(reply)
    print(
        f"[F08] mcp reply protocol_error={mcp_is_protocol_error(reply)} "
        f"tool_error={mcp_is_tool_error(reply)} text={report_text!r}",
        flush=True,
    )
    return McpValidateOutcome(
        batch=batch, reply=reply, payload=payload, report_text=report_text
    )


def mcp_validate(
    ws: Workspace,
    bundle: str | Path | None = None,
    *,
    strict: bool | None = None,
    stale: bool | None = None,
    request_id: int | str = 10,
    cwd: str | Path | None = None,
    env_updates: dict[str, str | None] | None = None,
) -> McpValidateOutcome:
    """membundle_validate with optional bundle / strict / stale. Omit keys left unset."""
    arguments: dict[str, Any] = {}
    if bundle is not None:
        arguments["bundle"] = str(bundle)
    if strict is not None:
        arguments["strict"] = bool(strict)
    if stale is not None:
        arguments["stale"] = bool(stale)
    return mcp_membundle_validate(
        ws, arguments, request_id=request_id, cwd=cwd, env_updates=env_updates
    )


def require_cli_status_0(result: RunResult) -> str:
    """CLI success carrier: POSIX status 0."""
    report = combined_report(result)
    print(f"[F08] status-0 exit={result.returncode} report_len={len(report)}", flush=True)
    assert result.returncode == 0, (
        f"validate did not end with status 0 (exit {result.returncode}); "
        f"report={report!r}"
    )
    return report


def require_cli_status_1(result: RunResult) -> str:
    """CLI non-conformance or failed producer gate: POSIX status 1."""
    report = combined_report(result)
    print(f"[F08] status-1 exit={result.returncode} report_len={len(report)}", flush=True)
    assert result.returncode == 1, (
        f"validate did not end with status 1 (exit {result.returncode}); "
        f"report={report!r}"
    )
    return report


def require_cli_status_2(result: RunResult) -> str:
    """CLI load failure: POSIX status 2."""
    report = combined_report(result)
    print(f"[F08] status-2 exit={result.returncode} report_len={len(report)}", flush=True)
    assert result.returncode == 2, (
        f"validate did not end with status 2 (exit {result.returncode}); "
        f"report={report!r}"
    )
    return report


def _walk_values(obj: Any, *, want: type) -> list[Any]:
    found: list[Any] = []

    def _walk(value: Any) -> None:
        if isinstance(value, bool):
            if want is bool:
                found.append(value)
            return
        if isinstance(value, (int, float)):
            if want is not bool:
                found.append(value)
            return
        if isinstance(value, str):
            return
        if isinstance(value, Mapping):
            for item in value.values():
                _walk(item)
            return
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                _walk(item)
            return
        if value is None:
            return
        raise HarnessError(
            f"structured report is not a walkable JSON value: {type(value).__name__}"
        )

    _walk(obj)
    return found


def walk_booleans(obj: Any) -> list[bool]:
    """Every boolean value in a structured report. Raises if none exist."""
    found = [bool(v) for v in _walk_values(obj, want=bool)]
    print(f"[F08] walked booleans={found!r}", flush=True)
    if not found:
        raise HarnessError(
            f"structured validate report has no boolean values; payload={obj!r}"
        )
    return found


def walk_numbers(obj: Any) -> list[float]:
    """Every numeric (non-bool) value in a structured report. Raises if none exist."""
    found = [float(v) for v in _walk_values(obj, want=int)]
    print(f"[F08] walked numbers={found!r}", flush=True)
    if not found:
        raise HarnessError(
            f"structured validate report has no numeric values; payload={obj!r}"
        )
    return found


def _sorted_desc(nums: Sequence[float]) -> list[float]:
    return sorted((float(n) for n in nums), reverse=True)


def assert_numbers_later_greater(earlier: Any, later: Any) -> None:
    """Relative order: later arm's walked numbers exceed the earlier arm's."""
    left = _sorted_desc(walk_numbers(earlier))
    right = _sorted_desc(walk_numbers(later))
    width = max(len(left), len(right))
    left = left + [0.0] * (width - len(left))
    right = right + [0.0] * (width - len(right))
    print(f"[F08] number order earlier={left!r} later={right!r}", flush=True)
    assert right > left, (
        "later-count arm's walked numbers are not greater than the earlier "
        f"arm's (relative order); earlier={left!r} later={right!r}"
    )


def assert_numbers_not_greater(baseline: Any, other: Any) -> None:
    """Adding a reserved/non-concept file must not make any walked integer greater."""
    left = _sorted_desc(walk_numbers(baseline))
    right = _sorted_desc(walk_numbers(other))
    width = max(len(left), len(right))
    left = left + [0.0] * (width - len(left))
    right = right + [0.0] * (width - len(right))
    print(f"[F08] number not-greater baseline={left!r} other={right!r}", flush=True)
    assert right <= left, (
        "walked integers increased after adding a reserved or skipped file; "
        f"baseline={left!r} other={right!r}"
    )


def _is_mcp_envelope(obj: Any) -> bool:
    """True when *obj* is a tools/call result wrapper, not a validate report."""
    return isinstance(obj, Mapping) and "content" in obj


def assert_both_pass(obj: Any) -> list[bool]:
    """Conformant gate-pass: at least two walked booleans, all true.

    A single envelope flag such as MCP ``isError`` is not this pair.
    """
    flags = walk_booleans(obj)
    assert len(flags) >= 2 and all(flags), (
        "expected both-pass (every walked boolean true, at least the two "
        "conformance/gate properties); "
        f"booleans={flags!r} payload={obj!r}"
    )
    return flags


def assert_conformant_gate_fail(obj: Any) -> list[bool]:
    """Conformant but failed producer gate: mixed true and false booleans."""
    flags = walk_booleans(obj)
    has_true = any(flags)
    has_false = any(not flag for flag in flags)
    assert has_true and has_false, (
        "expected mixed booleans (a true remains and a false remains) for a "
        f"conformant gate-fail; booleans={flags!r} payload={obj!r}"
    )
    return flags


def assert_nonconformant(obj: Any) -> list[bool]:
    """Hard non-conformance: not the mixed conformant-gate-fail pattern."""
    flags = walk_booleans(obj)
    mixed = any(flags) and any(not flag for flag in flags)
    assert not mixed, (
        "non-conformant report uses the mixed true/false pattern of a "
        f"conformant gate-fail; booleans={flags!r} payload={obj!r}"
    )
    assert not any(flags), (
        "non-conformant report still has a true boolean (both-pass or extra "
        f"ok bit); booleans={flags!r} payload={obj!r}"
    )
    return flags


def observation_blob(obj: Any) -> str:
    """Text a listing assertion can search: report string or JSON encoding."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, RunResult):
        return combined_report(obj)
    if isinstance(obj, McpValidateOutcome):
        return obj.report_text
    try:
        return json.dumps(obj)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"cannot encode observation as text: {exc}") from exc


def assert_identity_listed(obs: Any, identity: str) -> None:
    """The concept identity (path without ``.md``) appears in the report."""
    if not identity:
        raise HarnessError("identity is empty; cannot assert it is listed")
    blob = observation_blob(obs)
    print(f"[F08] identity listed? {identity!r} in blob_len={len(blob)}", flush=True)
    if isinstance(obs, (dict, list)):
        values = record_string_values(obs)
        if identity in values:
            return
    assert identity in blob, (
        f"report does not list concept identity {identity!r}: {blob!r}"
    )


def assert_identity_not_listed(obs: Any, identity: str) -> None:
    """The concept identity is absent after the same listing observation."""
    if not identity:
        raise HarnessError("identity is empty; cannot assert it is unlisted")
    blob = observation_blob(obs)
    if isinstance(obs, (dict, list)):
        values = record_string_values(obs)
        assert identity not in values, (
            f"structured report lists identity {identity!r} as a string value; "
            f"values={sorted(values)!r}"
        )
    assert identity not in blob, (
        f"report lists identity {identity!r} that should be unlisted: {blob!r}"
    )


def assert_absent_from_loaded_concept_set(
    payload: Any,
    identity: str,
    *,
    markdown_only: Any,
) -> None:
    """A skipped file is not in the loaded concept set (L51).

    The validate report names identities and a concept count (L232), not
    concept bodies. Identity is not listed, and walked numbers are not
    greater than a markdown-only twin. Does not require a body token to
    be absent from the report.
    """
    if not identity:
        raise HarnessError("identity is empty; cannot assert it is absent")
    print(
        f"[F08] absent from loaded concept set identity={identity!r}",
        flush=True,
    )
    assert_identity_not_listed(payload, identity)
    assert_numbers_not_greater(markdown_only, payload)


def assert_identity_absent_from_string_values(payload: Any, identity: str) -> None:
    """Identity is not an exact walked string value in a structured report.

    Does not require the identity to be omitted from every concatenated blob
    (L232 may still name paths that contain a reserved basename).
    """
    if not identity:
        raise HarnessError("identity is empty; cannot assert it is absent")
    if not isinstance(payload, (dict, list)):
        raise HarnessError(
            "reserved-identity check requires a structured payload, got "
            f"{type(payload).__name__}"
        )
    values = record_string_values(payload)
    print(
        f"[F08] identity absent from string values? {identity!r} "
        f"n={len(values)}",
        flush=True,
    )
    assert identity not in values, (
        f"structured report lists identity {identity!r} as a string value; "
        f"values={sorted(values)!r}"
    )


def assert_report_includes_path_token(payload: Any, token: str) -> None:
    """Some walked string value contains the bundle-path token (L232).

    Does not pin a JSON key or require the caller argv spelling to match
    bytes; an absolute or relative rendering that names this bundle is enough.
    """
    if not token:
        raise HarnessError("bundle path token is empty")
    if not isinstance(payload, (dict, list)):
        raise HarnessError(
            "bundle-path check requires a structured payload, got "
            f"{type(payload).__name__}"
        )
    values = record_string_values(payload)
    print(
        f"[F08] bundle path token {token!r} in {len(values)} string values",
        flush=True,
    )
    assert any(token in value for value in values), (
        f"structured validate report does not include bundle path token "
        f"{token!r}; string values={sorted(values)!r}"
    )


def assert_string_values_differ_after_strip(
    left: Any,
    right: Any,
    *,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> None:
    """Walked string values differ after stripping paths and fixture scalars.

    Holds an implementation to L232 hard-error / warning report fields
    without pinning key names or message wording.
    """
    if not isinstance(left, (dict, list)) or not isinstance(right, (dict, list)):
        raise HarnessError(
            "string-value contrast requires structured payloads, got "
            f"{type(left).__name__} and {type(right).__name__}"
        )

    def _remainders(obj: Any) -> set[str]:
        found: set[str] = set()
        for value in record_string_values(obj):
            rem = report_remainder(
                value, path_tokens=path_tokens, extra_tokens=extra_tokens
            )
            if rem:
                found.add(rem)
        return found

    left_rem = _remainders(left)
    right_rem = _remainders(right)
    print(
        f"[F08] string-value remainders left={sorted(left_rem)!r} "
        f"right={sorted(right_rem)!r}",
        flush=True,
    )
    assert left_rem != right_rem, (
        "structured string values do not differ after stripping paths and "
        f"fixture scalars; remainder={sorted(left_rem)!r}"
    )


def assert_href_listed(obs: Any, href: str) -> None:
    """The missing / reserved href remains in the report."""
    if not href:
        raise HarnessError("href is empty; cannot assert it is listed")
    blob = observation_blob(obs)
    print(f"[F08] href listed? {href!r} in blob_len={len(blob)}", flush=True)
    assert href in blob, (
        f"report does not list href {href!r}: {blob!r}"
    )


def assert_href_not_listed(obs: Any, href: str) -> None:
    """The href is absent from the report."""
    if not href:
        raise HarnessError("href is empty; cannot assert it is unlisted")
    blob = observation_blob(obs)
    assert href not in blob, (
        f"report lists href {href!r} that should not be a broken link: {blob!r}"
    )


def strip_tokens_from(text: str, tokens: Sequence[str]) -> str:
    """Remove fixture scalars from *text*, longest first. Empty text is allowed."""
    remainder = text
    ordered = sorted({tok for tok in tokens if tok}, key=len, reverse=True)
    for tok in ordered:
        remainder = remainder.replace(tok, "")
    return remainder


def report_remainder(
    report: str,
    *,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> str:
    """Strip paths, fixture scalars, dates, wrapping punctuation; collapse space."""
    if not isinstance(report, str):
        raise HarnessError(f"report remainder requires a string, got {type(report)!r}")
    text = strip_tokens_from(report, extra_tokens)
    text = strip_generated_covariates(text)
    text = report_remainder_after_stripping_paths(text, path_tokens)
    text = _WRAP_PUNCT.sub("", text)
    return _normalized_remainder(text)


def assert_report_differs_after_strip(
    left: str,
    right: str,
    *,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> None:
    """After stripping identities/paths/dates/scalars, a stable difference remains."""
    left_rem = report_remainder(
        left, path_tokens=path_tokens, extra_tokens=extra_tokens
    )
    right_rem = report_remainder(
        right, path_tokens=path_tokens, extra_tokens=extra_tokens
    )
    print(
        f"[F08] remainder left={left_rem!r} right={right_rem!r}",
        flush=True,
    )
    assert left_rem != right_rem, (
        "reports do not differ after stripping paths, dates, and fixture "
        f"scalars; remainder={left_rem!r}"
    )


def assert_warning_absent_after_strip(
    actual: str,
    baseline: str,
    *,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> None:
    """Negative arm: stripped remainder matches a no-warning baseline.

    Status 0 is not treated as proof the warning is absent.
    """
    actual_rem = report_remainder(
        actual, path_tokens=path_tokens, extra_tokens=extra_tokens
    )
    baseline_rem = report_remainder(
        baseline, path_tokens=path_tokens, extra_tokens=extra_tokens
    )
    print(
        f"[F08] warning-absent actual={actual_rem!r} baseline={baseline_rem!r}",
        flush=True,
    )
    assert actual_rem == baseline_rem, (
        "stripped remainder does not match the no-warning baseline; "
        f"actual={actual_rem!r} baseline={baseline_rem!r}"
    )


def require_warning_class(
    defective: RunResult,
    repaired: RunResult,
    *,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> None:
    """Advisory warning: both arms status 0; stripped reports differ."""
    require_cli_status_0(defective)
    require_cli_status_0(repaired)
    assert_report_differs_after_strip(
        combined_report(defective),
        combined_report(repaired),
        path_tokens=path_tokens,
        extra_tokens=extra_tokens,
    )


def require_gate_finding_class(
    without_strict: RunResult,
    with_strict: RunResult,
    repaired_strict: RunResult,
    *,
    structured_strict: Any | None = None,
    path_tokens: Sequence[str] = (),
    extra_tokens: Sequence[str] = (),
) -> None:
    """Gate finding on declared 0.2: appears without strict (status 0);
    ``--strict`` is status 1 mixed; repaired ``--strict`` is status 0.
    """
    require_cli_status_0(without_strict)
    require_cli_status_1(with_strict)
    require_cli_status_0(repaired_strict)
    if structured_strict is not None:
        assert_conformant_gate_fail(structured_strict)
    defective_report = combined_report(with_strict)
    repaired_report = combined_report(repaired_strict)
    assert_report_differs_after_strip(
        defective_report,
        repaired_report,
        path_tokens=path_tokens,
        extra_tokens=extra_tokens,
    )
    assert_report_differs_after_strip(
        combined_report(without_strict),
        repaired_report,
        path_tokens=path_tokens,
        extra_tokens=extra_tokens,
    )


def require_hard_error_class(
    defective: RunResult,
    repaired: RunResult,
    *,
    structured_defective: Any | None = None,
) -> None:
    """Hard error without promoting modes: status 1, not mixed; repaired status 0."""
    require_cli_status_1(defective)
    require_cli_status_0(repaired)
    if structured_defective is not None:
        assert_nonconformant(structured_defective)


def _parse_validate_report_text(text: str, *, reply: Mapping[str, Any]) -> Any:
    stripped = text.strip()
    if not stripped:
        raise HarnessError(
            f"MCP validate reply has no walkable payload; reply={reply!r}"
        )
    try:
        parsed = parse_json(stripped, what="mcp validate report")
    except HarnessError as exc:
        raise HarnessError(
            "MCP validate reply is not a walkable report payload; "
            f"reply={reply!r} text={text!r}"
        ) from exc
    if not isinstance(parsed, (dict, list)):
        raise HarnessError(
            "MCP validate reply parsed but is not an object/array report; "
            f"payload={parsed!r}"
        )
    if _is_mcp_envelope(parsed):
        raise HarnessError(
            "MCP validate reply is the tools/call envelope, not a validate "
            f"report; payload={parsed!r}"
        )
    return parsed


def _mcp_report_payload(outcome: McpValidateOutcome) -> Any:
    payload = outcome.payload
    if isinstance(payload, (dict, list)) and not _is_mcp_envelope(payload):
        return payload
    return _parse_validate_report_text(
        outcome.report_text, reply=outcome.reply
    )


def require_mcp_validate_report(outcome: McpValidateOutcome) -> Any:
    """Present-bundle MCP carrier: a report payload, not a protocol error.

    A tool-error flag is allowed when the payload still carries the report
    (L230 returns a report). A protocol error is not a report.
    """
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            "membundle_validate returned a JSON-RPC protocol error instead of a "
            f"validate report; reply={outcome.reply!r}"
        )
    payload = _mcp_report_payload(outcome)
    walk_booleans(payload)
    print(
        f"[F08] mcp report tool_error={mcp_is_tool_error(outcome.reply)}",
        flush=True,
    )
    return payload


def require_mcp_validate_tool_error(outcome: McpValidateOutcome) -> str:
    """Named-bundle load failure: not a protocol error and not a validate report.

    A walkable both-pass, mixed conformant-gate-fail, or all-false
    nonconformant payload is a present-bundle report of another class, not
    this failure. A JSON-RPC protocol error is not this failure. Empty tool
    text is not a classified load failure. Does not require MCP ``isError``
    wrapping (history #10 / FP-09). Pair with a present-bundle twin that is
    both-pass.
    """
    print(
        f"[F08] mcp named-bundle load-failure protocol_error="
        f"{mcp_is_protocol_error(outcome.reply)} "
        f"tool_error={mcp_is_tool_error(outcome.reply)}",
        flush=True,
    )
    if mcp_is_protocol_error(outcome.reply):
        raise AssertionError(
            "membundle_validate named-bundle load failure returned a JSON-RPC "
            "protocol error instead of a tool-level load failure; "
            f"reply={outcome.reply!r}"
        )
    result = outcome.reply.get("result")
    if not isinstance(result, Mapping):
        raise AssertionError(
            "membundle_validate named-bundle load failure is not a tools/call "
            f"result; reply={outcome.reply!r}"
        )
    try:
        payload = _mcp_report_payload(outcome)
        flags = walk_booleans(payload)
    except HarnessError as exc:
        if not (outcome.report_text or "").strip():
            raise AssertionError(
                "membundle_validate named-bundle load failure produced empty "
                "tool text; that is not a classified load failure; "
                f"reply={outcome.reply!r}"
            ) from exc
        print(
            f"[F08] mcp named-bundle load failure text={outcome.report_text!r}",
            flush=True,
        )
        return outcome.report_text
    raise AssertionError(
        "membundle_validate named-bundle load failure returned a walkable "
        "validate report of another class (both-pass, mixed gate-fail, or "
        "all-false nonconformant); "
        f"booleans={flags!r} payload={payload!r}"
    )


def assert_mcp_validate_not_both_pass(outcome: McpValidateOutcome) -> None:
    """Named-bundle load failure. Delegates to ``require_mcp_validate_tool_error``."""
    require_mcp_validate_tool_error(outcome)


def require_mcp_validate_both_pass(outcome: McpValidateOutcome) -> Any:
    """Present-bundle MCP carrier: walkable report whose booleans are both-pass."""
    payload = require_mcp_validate_report(outcome)
    assert_both_pass(payload)
    return payload


def assert_requested_structured_validate_is_machine_readable(result: RunResult) -> Any:
    """L230 optional structured output: requested validate is machine-readable.

    Does not pin JSON keys, field names, or human-mode stream split.
    """
    payload = json_stdout(result, what="requested structured validate")
    if not isinstance(payload, (dict, list)):
        raise AssertionError(
            "requested structured validate is not machine-readable JSON "
            f"(object or array); payload={payload!r}"
        )
    print(
        f"[F08] structured output type={type(payload).__name__}",
        flush=True,
    )
    return payload


def plant_ssot_links(root: str | Path, *, omit: str | None = None, regular: str | None = None) -> None:
    """Create the four L69 SSoT mappings under *root*. Does not call the product."""
    base = Path(root)
    if not path_is_dir(base):
        raise HarnessError(f"cannot plant SSoT links; not a directory: {base}")
    for rel, target in SSOT_LINKS:
        dest = base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if omit is not None and rel == omit:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            continue
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        if regular is not None and rel == regular:
            dest.write_text("not-a-symlink\n", encoding="utf-8")
            continue
        os.symlink(target, dest)
    print(f"[F08] planted SSoT links under {base} omit={omit!r} regular={regular!r}", flush=True)


def unique_id(prefix: str = "id") -> str:
    """Runtime-unique concept identity leaf."""
    return unique_leaf(prefix)


def seed_fact_identities(
    ws: Workspace,
    rel: str | Path,
    identities: Sequence[str],
    **kwargs: Any,
) -> Path:
    """Seed a validatable bundle whose concepts are type-Fact only."""
    concepts = [fact_concept(ident) for ident in identities]
    return seed_validatable_bundle(ws, rel, concepts, **kwargs)


def require_at_warning_pair(
    ws: Workspace,
    ident: str,
    bad_extra: Mapping[str, Any],
    good_extra: Mapping[str, Any],
) -> None:
    """Present generated/verified ``at`` defect vs repaired twin under ``--strict``.

    The helper itself asserts: both arms are status 0, and stripped reports
    differ after identities, actor strings, timestamps, and unparseable
    scalars are removed. Callers that only invoke this name are still a
    check under the one-hop audit.
    """
    rel_bad, rel_ok = unique_tokens("bd", "ok")
    seed_validatable_bundle(ws, rel_bad, [fact_concept(ident, extra=dict(bad_extra))])
    seed_validatable_bundle(ws, rel_ok, [fact_concept(ident, extra=dict(good_extra))])
    defective = run_validate(ws, rel_bad, strict=True)
    repaired = run_validate(ws, rel_ok, strict=True)
    extra = [
        ident,
        "agent/cli",
        "human:alice",
        "not-a-timestamp",
        "2020-06-15T12:00:00Z",
        "2020-06-16T12:00:00Z",
    ]
    tokens = path_tokens_for(ws.path, rel_bad, rel_ok)
    require_warning_class(defective, repaired, path_tokens=tokens, extra_tokens=extra)
    assert defective.returncode == 0, (
        f"defective .at arm did not stay status 0 (exit {defective.returncode})"
    )
    assert repaired.returncode == 0, (
        f"repaired .at arm did not stay status 0 (exit {repaired.returncode})"
    )
    assert_report_differs_after_strip(
        combined_report(defective),
        combined_report(repaired),
        path_tokens=tokens,
        extra_tokens=extra,
    )


def require_gate_finding_pair(
    ws: Workspace,
    ident: str,
    bad_extra: Mapping[str, Any],
    good_extra: Mapping[str, Any],
    *,
    body: str = "body\n",
) -> Any:
    """Declared-0.2 gate finding vs repaired twin. Returns the strict structured payload."""
    rel_bad, rel_ok = unique_tokens("bd", "ok")
    seed_validatable_bundle(
        ws, rel_bad, [fact_concept(ident, body=body, extra=dict(bad_extra))]
    )
    seed_validatable_bundle(
        ws, rel_ok, [fact_concept(ident, body=body, extra=dict(good_extra))]
    )
    without = run_validate(ws, rel_bad)
    with_strict, strict_payload = run_validate_structured(ws, rel_bad, strict=True)
    repaired, _repaired_payload = run_validate_structured(ws, rel_ok, strict=True)
    tokens = path_tokens_for(ws.path, rel_bad, rel_ok)
    require_gate_finding_class(
        without,
        with_strict,
        repaired,
        structured_strict=strict_payload,
        path_tokens=tokens,
        extra_tokens=[ident],
    )
    return strict_payload


def seed_drift_bundle(
    ws: Workspace,
    rel: str | Path,
    ident: str,
    title: str,
    description: str,
    listing_desc: str,
    extra: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Path:
    """Single-concept 0.2 bundle with a root-index listing for the drift audit."""
    fm: dict[str, Any] = {"description": description, "title": title}
    if extra:
        fm.update(dict(extra))
    return seed_validatable_bundle(
        ws,
        rel,
        [fact_concept(ident, extra=fm)],
        listings=[(title, f"{ident}.md", listing_desc)],
        **kwargs,
    )
