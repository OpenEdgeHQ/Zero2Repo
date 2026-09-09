# feature: F05
"""Observation helpers for the optional float converter (FP-05).

Classifiers raise when an outcome cannot be typed. They never return
``None`` to mean "not a decimal infinity" or treat a harness failure as
an empty document mapping.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from _harness import CallResult, HarnessError, call
from F01_helpers import decode_error_type, is_mapping, string_parse_entry
from F03_helpers import binary_parse_entry

decimal_from_text = Decimal


def parse_text_converted(text: str, converter: Callable[..., Any]) -> CallResult:
    """Parse *text* through the public string-parse entry with a converter.

    The converter is forwarded as the public keyword on that entry. Harness
    failures propagate. A product exception is a classified ``CallResult``.
    """
    if not isinstance(text, str):
        raise HarnessError(
            f"parse_text_converted requires str, got {type(text)!r}"
        )
    return call(string_parse_entry(), text, parse_float=converter)


def parse_binary_converted(fp: Any, converter: Callable[..., Any]) -> CallResult:
    """Parse an open file object through the binary-file entry with a converter.

    *fp* must already be a readable file object. Harness failures propagate.
    """
    if not hasattr(fp, "read"):
        raise HarnessError(
            f"parse_binary_converted requires an open file object, got "
            f"{type(fp)!r}"
        )
    return call(binary_parse_entry(), fp, parse_float=converter)


def require_decimal(obj: Any) -> Decimal:
    """Assert *obj* is a standard-library decimal and not a float."""
    if isinstance(obj, float):
        raise AssertionError(f"expected a decimal, got float {obj!r}")
    if not isinstance(obj, Decimal):
        raise AssertionError(
            f"expected a decimal, got {type(obj)!r}: {obj!r}"
        )
    return obj


def require_decimal_equal(obj: Any, spelling: str) -> Decimal:
    """Assert *obj* is a decimal equal to ``Decimal(spelling)``.

    *spelling* is the numeric characters from the source document.
    Construction failure of ``Decimal(spelling)`` is a harness failure.
    """
    if not isinstance(spelling, str):
        raise HarnessError(
            f"require_decimal_equal spelling must be str, got {type(spelling)!r}"
        )
    try:
        expected = Decimal(spelling)
    except (InvalidOperation, ValueError) as exc:
        raise HarnessError(
            f"cannot construct Decimal from spelling {spelling!r}: {exc}"
        ) from exc
    dec = require_decimal(obj)
    if dec != expected:
        raise AssertionError(
            f"expected decimal of characters {spelling!r} ({expected!r}), "
            f"got {dec!r}"
        )
    return dec


def require_decimal_inf(obj: Any, *, negative: bool) -> Decimal:
    """Assert *obj* is a decimal infinity of the named sign."""
    dec = require_decimal(obj)
    if not dec.is_infinite():
        raise AssertionError(f"expected a decimal infinity, got {dec!r}")
    if negative:
        if not (dec < 0):
            raise AssertionError(f"expected negative decimal infinity, got {dec!r}")
    elif not (dec > 0):
        raise AssertionError(f"expected positive decimal infinity, got {dec!r}")
    return dec


def require_decimal_nan(obj: Any) -> Decimal:
    """Assert *obj* is a decimal NaN. Sign bit is not observed."""
    dec = require_decimal(obj)
    if not dec.is_nan():
        raise AssertionError(f"expected a decimal NaN, got {dec!r}")
    return dec


def require_illegal_converter_failure(result: CallResult) -> ValueError:
    """Require a value error that is not a decode error, and no mapping.

    Unclassified exceptions (AttributeError, OSError, RecursionError, and
    any type that is not a value error) raise :class:`HarnessError`. A
    decode error or a type error is the wrong product kind and fails the
    assertion — it is not recast as a legal converter refusal.
    """
    if result.exception is None:
        raise AssertionError(
            f"parse succeeded with {result.value!r}; expected a value error "
            "from an illegal converter result"
        )
    exc = result.exception
    decode_type = decode_error_type()
    if isinstance(exc, decode_type):
        raise AssertionError(
            f"illegal converter was a decode error, not a value error: {exc!r}"
        )
    if isinstance(exc, TypeError):
        raise AssertionError(
            f"illegal converter was a type error, not a value error: {exc!r}"
        )
    if isinstance(exc, RecursionError):
        raise HarnessError(
            f"expected value error, got recursion error: {exc!r}"
        )
    if isinstance(exc, (AttributeError, OSError)):
        raise HarnessError(
            f"unclassified exception {type(exc).__name__}: {exc!r}"
        )
    if not isinstance(exc, ValueError):
        raise HarnessError(
            f"unclassified exception {type(exc).__name__}: {exc!r}"
        )
    if result.value is not None and is_mapping(result.value):
        raise AssertionError(
            f"illegal converter still yielded a document mapping: "
            f"{result.value!r}"
        )
    return exc


def always_returns(payload: Any) -> Callable[[Any], Any]:
    """Return a converter that ignores the token and yields *payload*."""

    def _ignore_token(_token: Any) -> Any:
        return payload

    return _ignore_token


def recording_converter(
    inner: Callable[..., Any],
) -> tuple[Callable[..., Any], list[Any]]:
    """Return ``(wrapper, recorded)``. *wrapper* appends then calls *inner*."""
    recorded: list[Any] = []

    def wrapper(token: Any) -> Any:
        recorded.append(token)
        return inner(token)

    return wrapper, recorded
