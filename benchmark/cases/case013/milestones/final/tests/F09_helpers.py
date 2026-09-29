# feature: F09
"""Observation helpers for the membundle mcp JSON-RPC server (FP-09).

Helpers raise ``HarnessError`` when a query cannot be classified, and
``AssertionError`` when a classified observation misses a carrier the
tests require. They never return ``None`` / ``{}`` / ``""`` / ``[]`` / ``0``
to mean "could not look".
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
from pathlib import Path
from typing import Any, NoReturn

from _harness import (
    HarnessError,
    McpBatchResult,
    Workspace,
    encode_rpc_line,
    rpc_request,
)
from F03_helpers import (
    mcp_is_protocol_error,
    mcp_is_tool_error,
    mcp_payload_and_text,
    mcp_reply_for_id,
    record_string_values,
)
from F04_helpers import (
    McpSearchOutcome,
    identity_in_records,
    require_mcp_search_success,
)
from F08_helpers import McpValidateOutcome

SIX_TOOL_NAMES = frozenset(
    {
        "membundle_search",
        "membundle_show",
        "membundle_create",
        "membundle_update",
        "membundle_relate",
        "membundle_validate",
    }
)

_MEMBUNDLE_TOOL_IDENT = re.compile(r"^membundle_[A-Za-z][A-Za-z0-9_]*$")
_WHITESPACE = re.compile(r"\s+")

# Recipe artifact name. The binary is built in a writable copy, not the judge cwd.
_BIN_REL = Path("bin") / "membundle"
_BUILD_LOCK = threading.Lock()
_BUILD_DONE = False
_BUILT_BIN: Path | None = None
_NEVER_STARTED = (
    "the server was never started; MCP results are missing"
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
    print(f"[F09] GOFLAGS=-buildvcs=false make build cwd={root}", flush=True)
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
        print(f"[F09] make build could not start: {exc}", flush=True)
        return False
    print(f"[F09] make build exit={completed.returncode}", flush=True)
    if completed.returncode != 0:
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        print(
            f"[F09] make build stdout={stdout[-2000:]!r} "
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
            print(f"[F09] resolved built binary={_BUILT_BIN!r}", flush=True)
        return _BUILT_BIN


def resolve_mcp_binary() -> Path:
    """Single resolver for every F09 ``membundle mcp`` start.

    When the pytest cwd contains the product sources, copies those sources
    to a writable directory, runs ``GOFLAGS=-buildvcs=false make build``
    there, and returns only that ``bin/membundle``. When that executable
    is absent, fails the test. Does not return an empty transcript, a
    synthetic JSON-RPC error, or a synthetic tool result: those are MCP
    outcomes, and an empty workspace would then look like a protocol
    failure or a tool error.
    """
    binary = _workdir_membundle()
    # TEST-FIX((none)): upstream Makefile:78 shows go build opens bin/membundle in the working directory and fails with "open bin/membundle: read-only file system" when that directory cannot accept the write, so the MCP server never starts and its results are missing.
    assert binary is not None, _NEVER_STARTED
    return binary


def _raise_if_mcp_binary_missing(binary: Path, exc: FileNotFoundError) -> NoReturn:
    """Turn a vanished workdir binary into the never-started assertion."""
    if binary.is_file() and os.access(binary, os.X_OK):
        raise exc
    # TEST-FIX(F09): upstream _harness.py:620 shows FileNotFoundError before any JSON-RPC line when bin/membundle is absent; Makefile:78 writes that binary only after GOFLAGS=-buildvcs=false make build.
    raise AssertionError(_NEVER_STARTED) from None


def initialize_request(request_id: int | str = 1) -> dict[str, Any]:
    """JSON-RPC initialize request. Client params are not scored."""
    return rpc_request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "f09-suite", "version": "0"},
        },
        id=request_id,
    )


def mcp_script(
    ws: Workspace,
    extra_lines: Sequence[str | Mapping[str, Any]] = (),
    *,
    args: Sequence[str] | None = None,
    env_updates: dict[str, str | None] | None = None,
    cwd: str | Path | None = None,
    initialize_id: int | str = 1,
) -> McpBatchResult:
    """Initialize then *extra_lines* through ``membundle mcp`` (stdin closed)."""
    lines: list[str | Mapping[str, Any]] = [
        initialize_request(initialize_id),
        *list(extra_lines),
    ]
    print(
        f"[F09] mcp_script lines={len(lines)} args={args!r} cwd={cwd!r}",
        flush=True,
    )
    binary = resolve_mcp_binary()
    try:
        return ws.mcp_batch(
            lines, args=args, env_updates=env_updates, cwd=cwd, binary=binary
        )
    except FileNotFoundError as exc:
        _raise_if_mcp_binary_missing(binary, exc)


def tools_call_request(
    name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    request_id: int | str = 10,
) -> dict[str, Any]:
    """``tools/call`` with object params (name + arguments object)."""
    params: dict[str, Any] = {"name": name, "arguments": dict(arguments or {})}
    return rpc_request("tools/call", params, id=request_id)


def tools_call_params_line(
    *,
    request_id: int | str,
    shape: str,
) -> str:
    """Raw JSON-RPC line whose ``params`` is an array, a string, or omitted."""
    message: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
    }
    if shape == "array":
        message["params"] = []
    elif shape == "string":
        message["params"] = "not-an-object"
    elif shape == "omitted":
        pass
    else:
        raise HarnessError(f"unknown tools/call params shape {shape!r}")
    return encode_rpc_line(message)


def require_rpc_error_code(reply: Mapping[str, Any], code: int) -> Mapping[str, Any]:
    """Reply is a JSON-RPC error object whose numeric code equals *code*."""
    if not mcp_is_protocol_error(reply):
        raise AssertionError(
            f"reply is not a JSON-RPC error object (wanted code {code}); "
            f"reply={reply!r}"
        )
    error = reply.get("error")
    if not isinstance(error, Mapping):
        raise HarnessError(
            f"JSON-RPC error is not an object; cannot read a code: {reply!r}"
        )
    raw = error.get("code")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise HarnessError(
            f"JSON-RPC error has no numeric code; cannot classify: {reply!r}"
        )
    observed = int(raw)
    print(f"[F09] rpc error code={observed} wanted={code}", flush=True)
    assert observed == int(code), (
        f"JSON-RPC error code is {observed}, expected {int(code)}; "
        f"reply={reply!r}"
    )
    return error


def require_some_rpc_error_code(batch: McpBatchResult, code: int) -> dict[str, Any]:
    """Some stdout message is a JSON-RPC error with numeric *code*. Raise if none."""
    matches: list[dict[str, Any]] = []
    for message in batch.messages:
        if not isinstance(message, dict):
            raise HarnessError(
                f"MCP stdout line is not an object: {message!r}"
            )
        if not mcp_is_protocol_error(message):
            continue
        error = message.get("error")
        if not isinstance(error, Mapping):
            raise HarnessError(
                f"JSON-RPC error is not an object; cannot read a code: "
                f"{message!r}"
            )
        raw = error.get("code")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise HarnessError(
                f"JSON-RPC error has no numeric code; cannot classify: "
                f"{message!r}"
            )
        if int(raw) == int(code):
            matches.append(message)
    print(
        f"[F09] messages_with_code_{code}={len(matches)} total={len(batch.messages)}",
        flush=True,
    )
    if not matches:
        raise AssertionError(
            f"no stdout JSON-RPC error with code {int(code)}; "
            f"messages={batch.messages!r}"
        )
    return matches[0]


def require_initialize_handshake(reply: Mapping[str, Any]) -> Any:
    """Initialize is a result whose walked strings include the frozen literals."""
    if mcp_is_protocol_error(reply):
        raise AssertionError(
            "initialize replied with a JSON-RPC error object; "
            f"reply={reply!r}"
        )
    result = reply.get("result")
    if result is None:
        raise HarnessError(
            f"initialize reply has no result to walk: {reply!r}"
        )
    values = record_string_values(result)
    print(
        f"[F09] initialize strings contain protocol="
        f"{'2024-11-05' in values} identity="
        f"{'membundle-agent-memory' in values}",
        flush=True,
    )
    assert "2024-11-05" in values, (
        "initialize result does not contain protocol version 2024-11-05 as a "
        f"string value; values={sorted(values)!r}"
    )
    assert "membundle-agent-memory" in values, (
        "initialize result does not contain server identity membundle-agent-memory "
        f"as a string value; values={sorted(values)!r}"
    )
    assert_initialize_advertises_tools_resources_prompts(result)
    return result


def assert_initialize_advertises_tools_resources_prompts(result: Any) -> None:
    """Initialize result advertises tools, resources, and prompts (L271).

    Walked leaves include object keys, so a capabilities object whose keys
    are those three names counts. Do not require a listChanged field or a
    nested schema.
    """
    leaves = walk_json_leaves(result)
    missing = [
        name for name in ("tools", "resources", "prompts") if name not in leaves
    ]
    print(
        f"[F09] initialize advertises tools/resources/prompts missing={missing!r}",
        flush=True,
    )
    assert not missing, (
        "initialize result does not advertise capabilities "
        f"{missing!r}; walked leaves={sorted(leaves, key=str)!r}"
    )


def walk_json_leaves(obj: Any) -> frozenset[Any]:
    """Strings, numbers, and booleans from values and object keys.

    Raises on an unclassified Python value. JSON null contributes nothing.
    """
    collected: set[Any] = set()

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            collected.add(value)
            return
        if isinstance(value, bool):
            collected.add(value)
            return
        if isinstance(value, (int, float)):
            collected.add(value)
            return
        if value is None:
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise HarnessError(
                        f"JSON object key is not a string: {key!r}"
                    )
                collected.add(key)
                _walk(item)
            return
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                _walk(item)
            return
        raise HarnessError(
            f"value is not a walkable JSON leaf container: {type(value).__name__}"
        )

    _walk(obj)
    return frozenset(collected)


def require_empty_ping(reply: Mapping[str, Any]) -> Any:
    """Ping is a JSON-RPC success with a present result whose leftover leaf set is empty.

    A reply that only echoes the request id (no result member) is not an
    empty result. JSON null and a JSON object with no leftover string,
    number, or boolean leaves (values and keys) are both empty encodings;
    do not pin one.
    """
    if mcp_is_protocol_error(reply):
        raise AssertionError(
            f"ping replied with a JSON-RPC error object; reply={reply!r}"
        )
    if "result" not in reply:
        raise AssertionError(
            "ping reply has no present result member; echoing the request "
            f"id alone is not an empty result; reply={reply!r}"
        )
    result = reply.get("result")
    leaves = walk_json_leaves(result)
    print(f"[F09] ping leftover leaves={sorted(leaves, key=str)!r}", flush=True)
    assert not leaves, (
        "ping result leftover set after walking strings, numbers, and "
        f"booleans (values and keys) is not empty; leaves={sorted(leaves, key=str)!r} "
        f"reply={reply!r}"
    )
    return result


def listed_tool_names(result: Any) -> frozenset[str]:
    """Tool identities listed on a ``tools/list`` success result.

    Exact ``membundle_*`` string values (not keys, not substrings of a description)
    are the listed identities. An extra mutation identity fails. An array of
    tool objects whose length is not six fails "exactly six".
    """
    if result is None:
        raise HarnessError("tools/list result is missing; cannot list tools")
    values = record_string_values(result)
    names = {value for value in values if value in SIX_TOOL_NAMES}
    extra = {
        value
        for value in values
        if isinstance(value, str)
        and _MEMBUNDLE_TOOL_IDENT.match(value)
        and value not in SIX_TOOL_NAMES
    }
    listing_lengths: list[int] = []

    def _direct_six(obj: Mapping[str, Any]) -> bool:
        return any(
            isinstance(value, str) and value in SIX_TOOL_NAMES
            for value in obj.values()
        )

    def _walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                _walk(item)
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            if value and all(isinstance(item, Mapping) for item in value):
                if any(_direct_six(item) for item in value):
                    listing_lengths.append(len(value))
            for item in value:
                _walk(item)
            return
        if value is None or isinstance(value, (str, bool, int, float)):
            return
        raise HarnessError(
            f"tools/list result is not walkable JSON: {type(value).__name__}"
        )

    _walk(result)
    print(
        f"[F09] listed tools={sorted(names)} extras={sorted(extra)} "
        f"array_lengths={listing_lengths}",
        flush=True,
    )
    if extra:
        raise AssertionError(
            "tools/list includes additional memory-mutation tool identities "
            f"{sorted(extra)!r}; listed={sorted(names)!r}"
        )
    if listing_lengths and any(length != 6 for length in listing_lengths):
        raise AssertionError(
            "tools/list array of tool objects is not exactly six long; "
            f"lengths={listing_lengths!r} names={sorted(names)!r}"
        )
    return frozenset(names)


def assert_json_arrays_empty(result: Any) -> list[int]:
    """Success result contains a JSON array of length 0, and every reachable JSON array has length 0.

    A protocol error is not an empty collection. An empty object, a null
    member, or a non-array result with no nested array is not an empty
    collection (L271). Do not pin a key name.
    """
    if isinstance(result, Mapping) and mcp_is_protocol_error(result):
        raise AssertionError(
            "protocol error is not an empty collection; "
            f"reply={result!r}"
        )
    lengths: list[int] = []

    def _walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for item in value.values():
                _walk(item)
            return
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            lengths.append(len(value))
            for item in value:
                _walk(item)
            return
        if value is None or isinstance(value, (str, bool, int, float)):
            return
        raise HarnessError(
            f"collection result is not walkable JSON: {type(value).__name__}"
        )

    _walk(result)
    print(f"[F09] reachable array lengths={lengths}", flush=True)
    if not lengths:
        raise AssertionError(
            "success result contains no JSON array collection of length 0; "
            "an empty object, a null member, or a non-array result is not "
            "an empty collection; "
            f"result={result!r}"
        )
    if any(length != 0 for length in lengths):
        raise AssertionError(
            "a reachable JSON array is not empty; "
            f"lengths={lengths!r} result={result!r}"
        )
    return lengths


def assert_request_reply_count(
    batch: McpBatchResult,
    request_ids: Sequence[int | str],
) -> None:
    """Stdout message count equals the request ids; each id has a reply."""
    wanted = list(request_ids)
    print(
        f"[F09] messages={len(batch.messages)} request_ids={wanted!r}",
        flush=True,
    )
    assert len(batch.messages) == len(wanted), (
        "stdout JSON-RPC message count does not equal the number of requests "
        f"that carried an id; messages={len(batch.messages)} ids={wanted!r} "
        f"payload={batch.messages!r}"
    )
    seen: list[Any] = []
    for message in batch.messages:
        if not isinstance(message, dict):
            raise HarnessError(
                f"MCP stdout line is not an object: {message!r}"
            )
        seen.append(message.get("id"))
    for request_id in wanted:
        mcp_reply_for_id(batch, request_id)


def require_tool_error_not_protocol(reply: Mapping[str, Any]) -> tuple[Any, str]:
    """Tool-error channel: MCP tool error, not a JSON-RPC protocol error."""
    if mcp_is_protocol_error(reply):
        raise AssertionError(
            "failure used a JSON-RPC protocol error instead of the MCP "
            f"tool-error channel; reply={reply!r}"
        )
    assert mcp_is_tool_error(reply), (
        "reply is not marked as a tool error; a JSON-RPC success (including "
        f"an empty result) is not this class; reply={reply!r}"
    )
    return mcp_payload_and_text(reply)


def require_tool_success(reply: Mapping[str, Any]) -> tuple[Any, str]:
    """tools/call JSON-RPC result that is not a tool error and not a protocol error."""
    if mcp_is_protocol_error(reply):
        raise AssertionError(
            f"tools/call returned a JSON-RPC protocol error; reply={reply!r}"
        )
    if mcp_is_tool_error(reply):
        raise AssertionError(
            f"tools/call marked a tool error on a success path; reply={reply!r}"
        )
    if "result" not in reply:
        raise HarnessError(
            f"tools/call success reply has no result member: {reply!r}"
        )
    return mcp_payload_and_text(reply)


def tool_error_remainder(
    reply: Mapping[str, Any],
    strip_tokens: Sequence[str],
) -> str:
    """Tool-error payload/text after stripping named covariates. Raises if not."""
    _payload, text = require_tool_error_not_protocol(reply)
    if not isinstance(text, str):
        raise HarnessError(
            f"tool-error text is not a string; cannot strip: {text!r}"
        )
    remainder = text
    ordered = sorted({tok for tok in strip_tokens if tok}, key=len, reverse=True)
    for tok in ordered:
        remainder = remainder.replace(tok, "")
        escaped = json.dumps(tok)
        if len(escaped) >= 2 and escaped[0] == '"' and escaped[-1] == '"':
            inner = escaped[1:-1]
            if inner:
                remainder = remainder.replace(inner, "")
    remainder = _WHITESPACE.sub(" ", remainder).strip()
    print(f"[F09] tool-error remainder={remainder!r}", flush=True)
    return remainder


def assert_outside_root_remainder_distinct(
    outside_reply: Mapping[str, Any],
    unknown_reply: Mapping[str, Any],
    missing_reply: Mapping[str, Any],
    strip_tokens: Sequence[str],
) -> None:
    """After strip, outside-root remainder differs from unknown-tool and load-failure."""
    outside = tool_error_remainder(outside_reply, strip_tokens)
    unknown = tool_error_remainder(unknown_reply, strip_tokens)
    missing = tool_error_remainder(missing_reply, strip_tokens)
    assert outside != unknown, (
        "outside-root tool-error remainder matches the unknown-tool remainder "
        f"after stripping covariates; remainder={outside!r}"
    )
    assert outside != missing, (
        "outside-root tool-error remainder matches the missing-inside-root "
        f"remainder after stripping covariates; remainder={outside!r}"
    )


def batch_blob(batch: McpBatchResult) -> str:
    """Concatenated JSON of every stdout message plus decoded stdout. Raises on bad UTF-8."""
    chunks: list[str] = [batch.stdout_text]
    for message in batch.messages:
        try:
            chunks.append(json.dumps(message, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise HarnessError(
                f"cannot serialize MCP stdout message: {exc}; message={message!r}"
            ) from exc
    return "\n".join(chunks)


def assert_token_absent_from_batch(batch: McpBatchResult, token: str) -> None:
    """*token* does not appear in any stdout JSON-RPC message."""
    if not token:
        raise HarnessError("token is empty; cannot assert absence from the transcript")
    blob = batch_blob(batch)
    print(
        f"[F09] token {token!r} absent from transcript={token not in blob}",
        flush=True,
    )
    assert token not in blob, (
        f"stdout transcript contains token {token!r} that must be unread; "
        f"blob={blob!r}"
    )


def assert_token_present_in_text(text: str, token: str) -> None:
    """*token* appears in *text*. Empty text is a classified miss, not a lookup failure."""
    if not token:
        raise HarnessError("token is empty; cannot assert presence")
    if not isinstance(text, str):
        raise HarnessError(f"presence text is not a string: {text!r}")
    assert token in text, (
        f"success payload does not contain token {token!r}; text={text!r}"
    )


def classify_search(batch: McpBatchResult, request_id: int | str) -> McpSearchOutcome:
    """Wrap a ``tools/call`` membundle_search reply as the sealed F04 search outcome."""
    reply = mcp_reply_for_id(batch, request_id)
    payload, report_text = mcp_payload_and_text(reply)
    return McpSearchOutcome(
        batch=batch, reply=reply, payload=payload, report_text=report_text
    )


def require_search_hits_identity(
    batch: McpBatchResult, request_id: int | str, identity: str
) -> list[Any]:
    """Classified membundle_search hit list whose records carry *identity*."""
    records = require_mcp_search_success(classify_search(batch, request_id))
    print(
        f"[F09] search identity {identity!r} in_records="
        f"{identity_in_records(records, identity)}",
        flush=True,
    )
    assert identity_in_records(records, identity), (
        "membundle_search success hit list has no record carrying the seeded "
        f"identity {identity!r}; records={records!r}"
    )
    return records


def classify_validate(
    batch: McpBatchResult, request_id: int | str
) -> McpValidateOutcome:
    """Wrap a ``tools/call`` membundle_validate reply as the sealed F08 validate outcome."""
    reply = mcp_reply_for_id(batch, request_id)
    payload, report_text = mcp_payload_and_text(reply)
    return McpValidateOutcome(
        batch=batch, reply=reply, payload=payload, report_text=report_text
    )


def path_covariates(*paths: str | Path) -> list[str]:
    """Path spellings to strip from tool-error remainders."""
    tokens: list[str] = []
    for raw in paths:
        if raw is None:
            continue
        text = str(raw)
        if not text:
            continue
        tokens.append(text)
        posix = text.replace("\\", "/")
        tokens.append(posix)
        tokens.append(posix.rstrip("/"))
        name = Path(text).name
        if name:
            tokens.append(name)
        try:
            resolved = str(Path(text).resolve())
        except OSError:
            resolved = text
        tokens.append(resolved)
        tokens.append(resolved.replace("\\", "/"))
    return tokens
