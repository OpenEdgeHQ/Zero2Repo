# feature: F05
"""Observation helpers for protocol errors and the incomplete-event limit.

Helpers classify construct / send / pull / mark-failed / start outcomes.
They never return a sentinel to mean the observation could not be
classified. A missing suggested-status integer raises; it is not
rewritten as 400. A failed incomplete-event-limit bind raises; it is
not rewritten as the default limit. A short-body probe that cannot
collect integers raises; it does not return an empty set.
"""

from __future__ import annotations

import re
from typing import Any

from _harness import (
    CallResult,
    HarnessError,
    call,
    call_method,
    require_value,
)
from F01_helpers import (
    package,
    runtime_token,
    suggested_status,
)
from F02_helpers import (
    connection_side_states,
    event_is_kind,
    feed_bytes,
    named_state,
    pull_next,
    require_pulled_event,
    require_remote_refusal,
)
from F03_helpers import (
    payload_as_bytes,
    pull_kind,
    require_our_state,
)


def connection_with_incomplete_limit(role: Any, limit: int) -> Any:
    """Same public connection constructor as ``connection_for``, plus a limit.

    Binding failure raises. Never silently falls back to the default limit.
    """
    pkg = package()
    try:
        ctor = getattr(pkg, "Connection")
    except AttributeError as exc:
        raise HarnessError("package root has no Connection") from exc
    if not callable(ctor):
        raise HarnessError(f"Connection is not callable; got {type(ctor)!r}")
    result = call(ctor, role, limit)
    if result.exception is not None:
        raise HarnessError(
            "constructing a connection with incomplete-event limit "
            f"{limit} failed: {result.exception!r}; cannot fall back to "
            "the default limit"
        )
    conn = require_value(result)
    print(
        f"connection_with_incomplete_limit limit={limit} "
        f"type={type(conn).__name__}",
        flush=True,
    )
    return conn


def mark_send_as_failed(conn: Any) -> CallResult:
    """Call the public mark-send-as-failed entry. Failure is not rewritten."""
    result = call_method(conn, "send_failed")
    print(
        f"mark_send_as_failed exc="
        f"{type(result.exception).__name__ if result.exception else None}",
        flush=True,
    )
    return result


def require_mark_failed(conn: Any) -> CallResult:
    """Require mark-send-as-failed returned and our-state is ERROR.

    A crash is never classified as "already marked".
    """
    result = mark_send_as_failed(conn)
    if result.exception is not None:
        raise HarnessError(
            "mark-send-as-failed raised "
            f"{type(result.exception).__name__}: {result.exception!r}; "
            "cannot treat a crash as a successful mark"
        )
    require_our_state(conn, "ERROR")
    print("require_mark_failed ok", flush=True)
    return result


def require_remote_status(result: CallResult, status: int) -> BaseException:
    """Require a remote protocol error whose suggested status is *status*.

    A missing integer raises inside ``suggested_status``; it is not 400.
    """
    exc = require_remote_refusal(result)
    got = suggested_status(exc)
    if got != status:
        raise AssertionError(
            f"suggested status is {got}, expected {status}"
        )
    print(f"require_remote_status {status} ok", flush=True)
    return exc


def require_our_error_their_not(conn: Any) -> None:
    """Require our-state is ERROR and their-state is not. Unreadable raises."""
    our, their = connection_side_states(conn)
    error = named_state("ERROR")
    if our != error:
        raise AssertionError(
            f"our_state is {our!r}, expected ERROR"
        )
    if their == error:
        raise AssertionError(
            f"their_state is also ERROR; it must not be"
        )
    print("require_our_error_their_not ok", flush=True)


def require_their_error_our_not(conn: Any) -> None:
    """Require their-state is ERROR and our-state is not. Unreadable raises."""
    our, their = connection_side_states(conn)
    error = named_state("ERROR")
    if their != error:
        raise AssertionError(
            f"their_state is {their!r}, expected ERROR"
        )
    if our == error:
        raise AssertionError(
            f"our_state is also ERROR; it must not be"
        )
    print("require_their_error_our_not ok", flush=True)


def require_side_still_error(conn: Any, which: str) -> None:
    """Require *which* ('our' or 'their') is still ERROR, not IDLE or DONE."""
    if which not in ("our", "their"):
        raise HarnessError(f"which must be 'our' or 'their', got {which!r}")
    our, their = connection_side_states(conn)
    side = our if which == "our" else their
    error = named_state("ERROR")
    idle = named_state("IDLE")
    done = named_state("DONE")
    if side != error:
        raise AssertionError(
            f"{which} state is {side!r}, expected ERROR"
        )
    if side == idle:
        raise AssertionError(f"{which} state left ERROR for IDLE")
    if side == done:
        raise AssertionError(f"{which} state left ERROR for DONE")
    print(f"require_side_still_error {which} ok", flush=True)


def require_not_connection_closed_event(value: Any) -> None:
    """Require *value* is not a connection-closed event."""
    if event_is_kind(value, "connection-closed"):
        raise AssertionError(
            "got a connection-closed event; this path is a protocol error"
        )
    print(
        f"require_not_connection_closed_event type="
        f"{type(value).__name__}",
        flush=True,
    )


def feed_empty(conn: Any) -> None:
    """Feed an empty chunk. A product exception is not 'already closed'."""
    result = feed_bytes(conn, b"")
    if result.exception is not None:
        raise HarnessError(
            "empty feed raised "
            f"{type(result.exception).__name__}: {result.exception!r}; "
            "cannot treat a crash as a receive-side close"
        )
    print("feed_empty ok", flush=True)


def _strip_payload_text(text: str, payload: bytes) -> str:
    cleaned = text
    if payload:
        try:
            letters = payload.decode("ascii")
        except UnicodeDecodeError:
            letters = ""
        if letters:
            cleaned = cleaned.replace(letters, "")
        cleaned = cleaned.replace(repr(payload), "")
        cleaned = cleaned.replace(str(payload), "")
        cleaned = cleaned.replace(payload.hex(), "")
    return cleaned


def short_body_quantities(exc: BaseException, *, strip: bytes) -> frozenset[int]:
    """Collect integers from a short-body failure after stripping *strip*.

    Probe failure raises. An empty set is never returned to mean
    "could not look". Suggested status 400 may appear in the set.
    """
    if not isinstance(exc, BaseException):
        raise HarnessError(
            f"short_body_quantities expected an exception; got {type(exc)!r}"
        )
    found: set[int] = set()

    def _add(value: Any) -> None:
        if type(value) is int:
            found.add(value)

    try:
        mapping = getattr(exc, "__dict__", None)
        if isinstance(mapping, dict):
            for value in mapping.values():
                _add(value)
    except Exception as probe_exc:
        raise HarnessError(
            f"cannot read short-body exception fields: {probe_exc}"
        ) from probe_exc

    try:
        names = dir(exc)
    except Exception as probe_exc:
        raise HarnessError(
            f"cannot list short-body exception attributes: {probe_exc}"
        ) from probe_exc
    for name in names:
        if name.startswith("_"):
            continue
        try:
            value = getattr(exc, name)
        except Exception:
            continue
        if callable(value):
            continue
        _add(value)

    try:
        report = str(exc)
    except Exception as probe_exc:
        raise HarnessError(
            f"cannot read short-body exception report: {probe_exc}"
        ) from probe_exc
    try:
        report_repr = repr(exc)
    except Exception as probe_exc:
        raise HarnessError(
            f"cannot read short-body exception repr: {probe_exc}"
        ) from probe_exc

    cleaned = _strip_payload_text(report + " " + report_repr, strip)
    try:
        args = getattr(exc, "args", ())
    except Exception as probe_exc:
        raise HarnessError(
            f"cannot read short-body exception args: {probe_exc}"
        ) from probe_exc
    pieces = [cleaned]
    if isinstance(args, tuple):
        for item in args:
            if isinstance(item, str):
                pieces.append(_strip_payload_text(item, strip))
            elif type(item) is int:
                found.add(item)
    text = " ".join(pieces)
    for match in re.finditer(r"-?\d+", text):
        found.add(int(match.group(0)))

    if not found:
        raise HarnessError(
            "short-body failure has no readable integers after stripping "
            f"payload {strip!r}: {exc!r}"
        )
    print(f"short_body_quantities={sorted(found)} strip={strip!r}", flush=True)
    return frozenset(found)


def require_short_body_pair(
    exc: BaseException,
    received: int,
    expected: int,
    *,
    payload: bytes,
) -> frozenset[int]:
    """Require the stripped integer set contains *received* and *expected*."""
    nums = short_body_quantities(exc, strip=payload)
    if received not in nums or expected not in nums:
        raise AssertionError(
            f"short-body integers {sorted(nums)} do not contain both "
            f"{received} and {expected} after stripping {payload!r}"
        )
    print(
        f"require_short_body_pair received={received} expected={expected}",
        flush=True,
    )
    return nums


def public_gibberish_block() -> bytes:
    """The public unparseable ``gibberish`` line plus a blank line."""
    block = b"gibberish\r\n\r\n"
    print(f"public_gibberish_block len={len(block)}", flush=True)
    return block


def public_big_header_unfinished() -> bytes:
    """The public ``GET / HTTP/1.0`` + ``Big`` 4000-``a`` header, still unfinished."""
    block = b"GET / HTTP/1.0\r\nBig: " + (b"a" * 4000)
    print(f"public_big_header_unfinished len={len(block)}", flush=True)
    return block


def public_big_header_block() -> bytes:
    """The public ``GET / HTTP/1.0`` + ``Big`` 4000-``a`` header + terminator."""
    block = public_big_header_unfinished() + b"\r\n\r\n"
    print(f"public_big_header_block len={len(block)}", flush=True)
    return block


def concatenated_body_until_eom(conn: Any) -> bytes:
    """Pull data events until end-of-message; return concatenated payloads.

    Need-data, a remote refusal, or a non-data/non-eom event raises.
    """
    chunks: list[bytes] = []
    for _ in range(64):
        result = pull_next(conn)
        event = require_pulled_event(result)
        if event_is_kind(event, "end-of-message"):
            body = b"".join(chunks)
            print(f"concatenated_body_until_eom len={len(body)}", flush=True)
            return body
        if event_is_kind(event, "data"):
            chunks.append(payload_as_bytes(event))
            continue
        raise AssertionError(
            "expected data or end-of-message, got "
            f"{type(event).__name__} {event!r}"
        )
    raise AssertionError("never pulled end-of-message after data events")


def pull_request_then_eom(conn: Any) -> Any:
    """Pull a request event then its end-of-message. Missing either raises."""
    request = pull_kind(conn, "request")
    pull_kind(conn, "end-of-message")
    print(
        f"pull_request_then_eom type={type(request).__name__}",
        flush=True,
    )
    return request


def runtime_unparseable_block() -> bytes:
    """An unparseable line plus a blank line that is not the public gibberish."""
    token = runtime_token()
    if token.lower() == "gibberish":
        token = token + "z"
    block = token.encode("ascii") + b"\n\n"
    print(f"runtime_unparseable_block={block!r}", flush=True)
    return block
