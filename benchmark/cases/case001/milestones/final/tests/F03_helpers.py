# feature: F03
"""Observation helpers for binary-file parse of TOML (FP-03).

Helpers classify outcomes of the public binary-file parse entry. They never
return an empty mapping or ``None`` to mean "the call could not be classified".
"""

from __future__ import annotations

from typing import Any, Callable

from _harness import CallResult, HarnessError, as_bytes, call
from F01_helpers import decode_error_type, is_mapping

_LAX_ASSIGN = b" = 10001\n"
_HIGH_BYTE_MIN = 0xA0
_HIGH_BYTE_SPAN = 0x100 - _HIGH_BYTE_MIN


def binary_parse_entry() -> Callable[..., Any]:
    """Return the public binary-file parse callable from the package root.

    The product is imported here, not at module import time, so this helper
    module still loads when the product is absent from ``sys.path``.
    """
    from tomlparse import load

    if not callable(load):
        raise HarnessError("binary-file parse entry is not callable")
    return load


def parse_binary(fp: Any) -> CallResult:
    """Parse an already-open file object through the public binary-file entry.

    *fp* must already be an open file object. Harness failures (timeout,
    isolation) propagate. A product exception is a classified
    ``CallResult``, not a sentinel mapping.
    """
    if not hasattr(fp, "read"):
        raise HarnessError(
            f"parse_binary requires an open file object, got {type(fp)!r}"
        )
    return call(binary_parse_entry(), fp)


def require_type_error(result: CallResult) -> TypeError:
    """Require a type error that is not a decode error, and no mapping.

    Unclassified exceptions (including AttributeError, decode error, and
    recursion error) raise :class:`HarnessError` rather than being treated
    as the documented type error.
    """
    if result.exception is None:
        raise AssertionError(
            f"parse succeeded with {result.value!r}; expected a type error"
        )
    exc = result.exception
    decode_type = decode_error_type()
    if isinstance(exc, decode_type):
        raise AssertionError(
            f"got decode error; expected a type error: {exc!r}"
        )
    if isinstance(exc, RecursionError):
        raise HarnessError(
            f"expected type error, got recursion error: {exc!r}"
        )
    if isinstance(exc, AttributeError):
        raise HarnessError(
            f"expected type error, got AttributeError: {exc!r}"
        )
    if not isinstance(exc, TypeError):
        raise HarnessError(
            f"unclassified exception {type(exc).__name__}: {exc!r}"
        )
    if result.value is not None and is_mapping(result.value):
        raise AssertionError(
            f"type error still yielded a document mapping: {result.value!r}"
        )
    return exc


def require_unsuccessful(result: CallResult) -> CallResult:
    """Require that the call is not a successful parse and yields no mapping.

    Success is ``exception is None`` and ``value`` is a document mapping.
    That conjunction being true is an AssertionError. Returning ``None``
    without an exception is unsuccessful at this precision. Does not
    require an exception object, a decode error, or a TypeError.
    """
    has_mapping = False
    if result.value is not None:
        has_mapping = is_mapping(result.value)
    succeeded = result.exception is None and has_mapping
    if succeeded:
        raise AssertionError(
            f"call succeeded with a document mapping: {result.value!r}"
        )
    if has_mapping:
        raise AssertionError(
            f"call yielded a document mapping: {result.value!r}"
        )
    kind = type(result.exception).__name__ if result.exception else None
    print(
        f"unsuccessful exception={kind} value={result.value!r}",
        flush=True,
    )
    return result


def utf8_source(text: str) -> bytes:
    """Encode *text* as UTF-8 bytes. Input construction, not a parse oracle."""
    if not isinstance(text, str):
        raise HarnessError(f"utf8_source requires str, got {type(text)!r}")
    return as_bytes(text)


def lax_success_invalid_utf8(*, key_prefix: str, kind: str) -> bytes:
    """Build invalid-UTF-8 bytes whose latin-1 decoding is valid TOML.

    ``kind="high_byte"``: a quoted key contains one byte in ``0xA0–0xFF``.
    ``kind="incomplete_c3"``: a quoted key contains a lone ``0xC3``.
    The remainder is an ASCII assignment. Does not latin-1-decode the
    payload into an expected mapping.
    """
    if not isinstance(key_prefix, str) or not key_prefix:
        raise HarnessError("key_prefix must be a non-empty str")
    try:
        prefix_b = key_prefix.encode("ascii")
    except UnicodeEncodeError as exc:
        raise HarnessError(
            f"key_prefix must be ASCII, got {key_prefix!r}"
        ) from exc
    if kind == "high_byte":
        high = _HIGH_BYTE_MIN + (sum(prefix_b) % _HIGH_BYTE_SPAN)
        payload = b'"' + prefix_b + bytes([high]) + b'"' + _LAX_ASSIGN
    elif kind == "incomplete_c3":
        payload = b'"' + prefix_b + b"\xc3" + b'"' + _LAX_ASSIGN
    else:
        raise HarnessError(
            f"kind must be 'high_byte' or 'incomplete_c3', got {kind!r}"
        )
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        raise HarnessError(
            f"lax_success_invalid_utf8 kind={kind!r} produced valid UTF-8"
        )
    return payload
