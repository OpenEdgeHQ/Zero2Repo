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
    require_local_refusal,
    runtime_token,
    suggested_status,
)
from F02_helpers import (
    _event_types,
    _is_need_data,
    connection_side_states,
    encoded_first_line,
    event_is_kind,
    feed_bytes,
    make_eom,
    make_response,
    named_state,
    pull_next,
    require_pulled_event,
    require_remote_refusal,
    require_send_bytes,
    send_event,
    wire_header_value,
)
from F03_helpers import (
    payload_as_bytes,
    pull_kind,
    require_our_state,
    wire_has_header,
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


def paused_pull_token() -> Any:
    """Return the package-root paused non-event result. Missing raises."""
    pkg = package()
    try:
        token = getattr(pkg, "PAUSED")
    except AttributeError as exc:
        raise HarnessError("package root has no paused result") from exc
    print(f"paused_pull_token={token!r}", flush=True)
    return token


def require_pull_paused(result: CallResult) -> Any:
    """Require pull succeeded and returned paused, not an event or need-data.

    A crash is never classified as paused.
    """
    value = require_value(result)
    if any(isinstance(value, typ) for typ in _event_types()):
        raise AssertionError(
            f"pull returned an event {type(value)!r}, not paused"
        )
    if _is_need_data(value):
        raise AssertionError("pull returned need-data, not paused")
    token = paused_pull_token()
    if value is token:
        print("require_pull_paused ok", flush=True)
        return value
    try:
        matched = value == token
    except Exception:
        matched = False
    if not matched:
        raise AssertionError(
            f"pull returned {type(value)!r} {value!r}, not paused"
        )
    print("require_pull_paused ok", flush=True)
    return value


def begin_next_cycle(conn: Any) -> CallResult:
    """Call the public start-next-cycle entry. Failure is not rewritten as success."""
    result = call_method(conn, "start_next_cycle")
    print(
        f"begin_next_cycle exc="
        f"{type(result.exception).__name__ if result.exception else None}",
        flush=True,
    )
    return result


def require_no_error_side(conn: Any) -> None:
    """Require neither side is ERROR. Unreadable states raise."""
    our, their = connection_side_states(conn)
    error = named_state("ERROR")
    if our == error or their == error:
        raise AssertionError(
            f"a side is ERROR; our={our!r} their={their!r}"
        )
    print("require_no_error_side ok", flush=True)


def require_early_cycle_local(result: CallResult, conn: Any) -> BaseException:
    """Require start-next-cycle failed as a local protocol error.

    Start did not leave both sides IDLE. Neither side is ERROR. A probe
    crash is never classified as "start did nothing".
    """
    exc = require_local_refusal(result)
    got_our, got_their = connection_side_states(conn)
    idle = named_state("IDLE")
    if got_our == idle and got_their == idle:
        raise AssertionError(
            "start-next-cycle refused but both sides are IDLE"
        )
    require_no_error_side(conn)
    print(
        f"early_cycle_local our={got_our!r} their={got_their!r}",
        flush=True,
    )
    return exc


def wire_status_code(encoded: bytes) -> int:
    """Read the integer status from the encoded status line. Parse failure raises."""
    line = encoded_first_line(encoded)
    parts = line.split()
    if len(parts) < 2:
        raise HarnessError(
            f"status line {line!r} does not contain a status code"
        )
    try:
        status = int(parts[1])
    except ValueError as exc:
        raise HarnessError(
            f"status line {line!r} has a non-integer status {parts[1]!r}"
        ) from exc
    print(f"wire_status_code={status} line={line!r}", flush=True)
    return status


def encoded_carries_close(encoded: bytes) -> bool:
    """Return whether a parsed header block has a Connection close token.

    Tokens are comma-separated; a token matches when the stripped
    segment equals ``close`` case-insensitively. No Connection header
    after a successful parse is False. Parse failure raises — never
    returns False to mean "could not look".
    """
    if not wire_has_header(encoded, b"connection"):
        print("encoded_carries_close=False (no Connection)", flush=True)
        return False
    raw_value = wire_header_value(encoded, b"connection")
    found_close = False
    for piece in raw_value.split(b","):
        if piece.strip().lower() == b"close":
            found_close = True
    print(f"encoded_carries_close={found_close}", flush=True)
    return found_close


def require_encoded_close(encoded: bytes) -> None:
    """Require the encoded header block contains a close token."""
    if not encoded_carries_close(encoded):
        raise AssertionError(
            "encoded response has no Connection close token"
        )


def require_sides_done(conn: Any) -> None:
    """Require both sides are DONE. Unreadable states raise."""
    our, their = connection_side_states(conn)
    done = named_state("DONE")
    if our != done or their != done:
        raise AssertionError(
            f"expected both sides DONE; our={our!r} their={their!r}"
        )
    print("require_sides_done ok", flush=True)


def send_eom_bytes(conn: Any) -> bytes:
    """Send end-of-message. Success may be empty or a framing trailer.

    A product exception is never classified as empty bytes.
    """
    result = send_event(conn, make_eom())
    if result.exception is not None:
        raise HarnessError(
            "end-of-message send raised "
            f"{type(result.exception).__name__}: {result.exception!r}"
        )
    value = result.value
    if value is None:
        print("send_eom_bytes none", flush=True)
        return b""
    if type(value) is bytes:
        print(f"send_eom_bytes len={len(value)}", flush=True)
        return value
    if isinstance(value, (bytearray, memoryview)):
        raw = bytes(value)
        print(f"send_eom_bytes len={len(raw)}", flush=True)
        return raw
    raise HarnessError(
        f"end-of-message send did not return bytes or none; got {type(value)!r}"
    )


def require_cycle_reset(result: CallResult, conn: Any) -> None:
    """Require start-next-cycle returned and both sides are IDLE.

    Returning without error is not enough: a no-op that leaves both
    sides DONE is not a successful start.
    """
    if result.exception is not None:
        raise AssertionError(
            "start-next-cycle raised "
            f"{type(result.exception).__name__}: {result.exception!r}"
        )
    our, their = connection_side_states(conn)
    idle = named_state("IDLE")
    done = named_state("DONE")
    if our != idle or their != idle:
        raise AssertionError(
            "start-next-cycle returned without error but sides are not "
            f"both IDLE; our={our!r} their={their!r}"
        )
    if our == done or their == done:
        raise AssertionError(
            "start-next-cycle left a side in DONE; "
            f"our={our!r} their={their!r}"
        )
    print("require_cycle_reset both IDLE", flush=True)


def pull_empty_response(conn: Any) -> Any:
    """Pull a response event, then the matching end-of-message (empty body)."""
    response = pull_kind(conn, "response")
    done = pull_kind(conn, "end-of-message")
    print(
        f"pull_empty_response response={type(response).__name__} "
        f"eom={type(done).__name__}",
        flush=True,
    )
    return response


def send_empty_200(server: Any, *, headers: Any = ()) -> bytes:
    """Send a 200 plus end-of-message on *server*; return concatenated bytes."""
    resp = require_send_bytes(
        send_event(server, make_response(200, headers=list(headers)))
    )
    eom = send_eom_bytes(server)
    print(f"send_empty_200 resp_len={len(resp)} eom_len={len(eom)}", flush=True)
    return resp + eom


def generated_host() -> str:
    """A Host that is not the public sample ``a`` or ``example.com``."""
    host = runtime_token() + ".host"
    print(f"generated_host={host!r}", flush=True)
    return host


def generated_target() -> str:
    """A request target that is not a public sample path."""
    target = "/t" + runtime_token()[:8]
    print(f"generated_target={target!r}", flush=True)
    return target
