# feature: F07
"""Observation helpers for the finite built-in function set (FP-07).

New names only. Sealed F01–F06 helpers are imported, not copied.
A helper that cannot classify its input raises; it never returns
``None``, ``False``, ``[]``, or ``0`` to mean "no function result".
"""

from __future__ import annotations

import json
import math
import uuid
from typing import Any

from _harness import HarnessError
from F01_helpers import (
    failure_record,
    leftover_kind_stem,
    runtime_ident,
    runtime_payload,
)
from F03_helpers import assert_kind_stems_differ

# Public-oracle tokens this slice must not reuse as process-local names.
_BUILTIN_NAMES = frozenset(
    {
        "abs",
        "avg",
        "ceil",
        "contains",
        "ends_with",
        "floor",
        "join",
        "keys",
        "length",
        "map",
        "max",
        "max_by",
        "merge",
        "min",
        "min_by",
        "not_null",
        "reverse",
        "sort",
        "sort_by",
        "starts_with",
        "sum",
        "to_array",
        "to_number",
        "to_string",
        "type",
        "values",
    }
)
_PUBLIC_IDENTS = frozenset(
    {
        "foo",
        "zero",
        "numbers",
        "array",
        "strings",
        "decimals",
        "str",
        "false",
        "empty_list",
        "empty_hash",
        "objects",
        "null_key",
        "people",
        "empty",
        "age",
        "order",
        "name",
        "extra",
        "bool",
        "a",
        "b",
        "c",
        "badkey",
        "unknown_function",
        "unknown_key",
        "all",
        "expressions",
        "are_null",
    }
) | _BUILTIN_NAMES
_PUBLIC_PAYLOADS = frozenset(
    {
        "bar",
        "baz",
        "Str",
        "a",
        "b",
        "c",
        "z",
        "yes1",
        "yes2",
        "hello world",
        "abc",
        "notanumber",
        "1e21",
        "dlrow olleh",
        "foo",
        "SStr",
        "String",
        "true",
        "null",
        "boolean",
        "number",
        "string",
        "object",
        "array",
    }
)
_PUBLIC_NUMBERS = frozenset(
    {
        -24,
        -1.5,
        -1,
        0,
        1,
        1.01,
        1.1,
        1.2,
        2,
        2.75,
        3,
        4,
        5,
        10,
        11,
        20,
        24,
        30,
        40,
        50,
        100,
        111,
    }
)


def fn_ident() -> str:
    """Process-local identifier that is not a published function-oracle token."""
    token = runtime_ident()
    if token in _PUBLIC_IDENTS:
        raise HarnessError(f"fn_ident collided with a reserved token: {token}")
    if token in _BUILTIN_NAMES:
        raise HarnessError(f"fn_ident reused a built-in name: {token}")
    print(f"fn_ident={token!r}", flush=True)
    return token


def fn_payload() -> str:
    """Process-local string payload that is not a published function-oracle token."""
    token = runtime_payload()
    if token in _PUBLIC_PAYLOADS:
        raise HarnessError(f"fn_payload collided with a reserved payload: {token}")
    print(f"fn_payload={token!r}", flush=True)
    return token


def fn_int(*, negative: bool = False, positive: bool = False) -> int:
    """Process-local integer that is not a published function-oracle number.

    ``positive=True`` requires ``n > 0``. ``negative=True`` requires ``n < 0``.
    Both flags together, or a generated value that misses the requested
    sign, is unclassifiable and raises — never a public ``-1`` / ``0`` /
    ``1`` fallback.
    """
    if negative and positive:
        raise HarnessError("fn_int cannot require both negative and positive")
    for _ in range(48):
        magnitude = 13 + (int(uuid.uuid4().hex[:4], 16) % 200)
        n = -magnitude if negative else magnitude
        if type(n) is not int:
            raise HarnessError(f"fn_int produced a non-int: {n!r}")
        if n in _PUBLIC_NUMBERS:
            continue
        if positive and n <= 0:
            raise HarnessError(f"fn_int(positive=True) produced non-positive {n!r}")
        if negative and n >= 0:
            raise HarnessError(f"fn_int(negative=True) produced non-negative {n!r}")
        print(f"fn_int={n}", flush=True)
        return n
    raise HarnessError(
        f"fn_int could not pick an int outside {_PUBLIC_NUMBERS!r}"
    )


def fn_float(*, in_open_neg_unit: bool = False) -> float:
    """Process-local non-integer float that is not a published oracle number.

    With ``in_open_neg_unit=True`` the value is in ``(-1, 0)``. A value
    that is an integer, outside that interval, or equal to a public
    sample raises — never a substitute where ``trunc`` equals ``floor``.
    """
    if in_open_neg_unit:
        for _ in range(48):
            numer = 1 + (int(uuid.uuid4().hex[:4], 16) % 1000)
            value = -float(numer) / 1001.0
            if type(value) is not float:
                raise HarnessError(f"fn_float produced a non-float: {value!r}")
            if value in _PUBLIC_NUMBERS:
                continue
            if not (-1.0 < value < 0.0):
                raise HarnessError(
                    f"fn_float(in_open_neg_unit=True) not in (-1, 0): {value!r}"
                )
            if value == int(value):
                raise HarnessError(
                    f"fn_float(in_open_neg_unit=True) is an integer: {value!r}"
                )
            if math.floor(value) == math.trunc(value):
                raise HarnessError(
                    f"fn_float(in_open_neg_unit=True) has floor==trunc: {value!r}"
                )
            print(f"fn_float_open_neg_unit={value!r}", flush=True)
            return value
        raise HarnessError("fn_float could not pick a value in (-1, 0)")
    for _ in range(48):
        whole = 13 + (int(uuid.uuid4().hex[:4], 16) % 200)
        frac = (1 + (int(uuid.uuid4().hex[:4], 16) % 900)) / 1000.0
        value = float(whole) + float(frac)
        if type(value) is not float:
            raise HarnessError(f"fn_float produced a non-float: {value!r}")
        if value in _PUBLIC_NUMBERS:
            continue
        if value == int(value):
            raise HarnessError(f"fn_float produced an integer-valued float: {value!r}")
        print(f"fn_float={value!r}", flush=True)
        return value
    raise HarnessError(
        f"fn_float could not pick a non-integer float outside {_PUBLIC_NUMBERS!r}"
    )


def fn_ordered_strings() -> tuple[str, str]:
    """Two distinct process-local strings ordered by the host ``<``.

    Returns ``(lesser, greater)``. Equal strings, a public token, or a
    pair the host cannot order raise.
    """
    left = fn_payload()
    right = fn_payload()
    if left in _PUBLIC_PAYLOADS or right in _PUBLIC_PAYLOADS:
        raise HarnessError(
            f"fn_ordered_strings reused a public token: {left!r}/{right!r}"
        )
    if left == right:
        raise HarnessError(f"fn_ordered_strings produced equal strings: {left!r}")
    if left < right:
        print(
            f"fn_ordered_strings lesser={left!r} greater={right!r}",
            flush=True,
        )
        return left, right
    if right < left:
        print(
            f"fn_ordered_strings lesser={right!r} greater={left!r}",
            flush=True,
        )
        return right, left
    raise HarnessError(
        f"fn_ordered_strings cannot classify {left!r} vs {right!r} under host <"
    )


def fn_ordered_floats() -> tuple[float, float]:
    """Two distinct process-local floats ordered by the host ``<``.

    Returns ``(lesser, greater)``. A public sample, equal floats, or a
    pair the host cannot order raise.
    """
    left = fn_float()
    right = fn_float()
    if left == right:
        raise HarnessError(f"fn_ordered_floats produced equal floats: {left!r}")
    if left < right:
        print(
            f"fn_ordered_floats lesser={left!r} greater={right!r}",
            flush=True,
        )
        return left, right
    if right < left:
        print(
            f"fn_ordered_floats lesser={right!r} greater={left!r}",
            flush=True,
        )
        return right, left
    raise HarnessError(
        f"fn_ordered_floats cannot classify {left!r} vs {right!r} under host <"
    )


def compact_json_text(value: Any) -> str:
    """Host compact JSON text: ``json.dumps(..., separators=(',', ':'))``.

    Encoding failure raises. An empty string is unclassifiable — never
    returned as a stand-in for "could not encode".
    """
    try:
        text = json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"cannot compact-JSON-encode {value!r}: {exc}") from exc
    if not isinstance(text, str) or text == "":
        raise HarnessError(
            f"compact JSON of {value!r} is not a non-empty string: {text!r}"
        )
    print(f"compact_json_text={text!r}", flush=True)
    return text


def host_ordinary_text(value: Any) -> str:
    """Host ordinary text conversion: ``str(value)``.

    A result that is not a non-empty ``str`` raises.
    """
    try:
        text = str(value)
    except Exception as exc:
        raise HarnessError(f"host str() failed for {value!r}: {exc}") from exc
    if not isinstance(text, str) or text == "":
        raise HarnessError(
            f"host ordinary text of {value!r} is not a non-empty str: {text!r}"
        )
    print(f"host_ordinary_text={text!r}", flush=True)
    return text


def host_non_json_value(payload: str) -> Any:
    """A host object that is not a JSON type; ``str`` yields *payload*.

    *payload* must be a non-empty process-local string. ``Decimal`` is
    refused: L26 treats host decimals as numbers.
    """
    if not isinstance(payload, str) or payload == "":
        raise HarnessError(
            f"host_non_json_value requires a non-empty str payload, got {payload!r}"
        )
    if payload in _PUBLIC_PAYLOADS:
        raise HarnessError(
            f"host_non_json_value reused a public payload: {payload!r}"
        )

    class _HostCurrent:
        def __str__(self) -> str:
            return payload

        def __repr__(self) -> str:
            return f"HostCurrent({payload!r})"

    obj = _HostCurrent()
    print(f"host_non_json_value payload={payload!r}", flush=True)
    return obj


def function_kind_texts(*tokens: str) -> tuple[str, ...]:
    """Collect expression texts and function-name identifiers to strip.

    Names are covariates: leftover comparison must drop them or three
    failures look distinct only because the identifiers differ. Empty
    tokens raise rather than being silently dropped.
    """
    collected: list[str] = []
    for token in tokens:
        if not isinstance(token, str):
            raise HarnessError(
                f"function_kind_texts tokens must be str, got {type(token)!r}"
            )
        if token == "":
            raise HarnessError("function_kind_texts refuses an empty token")
        collected.append(token)
    if len(collected) < 2:
        raise HarnessError(
            "function_kind_texts needs at least an expression and a function name"
        )
    print(f"function_kind_texts n={len(collected)}", flush=True)
    return tuple(collected)


def assert_three_function_kinds_distinct(
    unknown: BaseException,
    arity: BaseException,
    typed: BaseException,
    *texts: str,
) -> None:
    """Require unknown / arity / type leftovers pairwise differ.

    Kind is ``leftover_kind_stem`` after stripping *texts* (expressions
    and function names) then digits and whitespace. Same-kind examples
    are not compared to each other. Unclassifiable (two stems equal)
    raises — never a pass for "no visible difference".
    """
    for label, exc in (
        ("unknown", unknown),
        ("arity", arity),
        ("typed", typed),
    ):
        if not isinstance(exc, BaseException):
            raise HarnessError(
                f"assert_three_function_kinds_distinct {label} is not an "
                f"exception: {type(exc)!r}"
            )
    unknown_stem = leftover_kind_stem(failure_record(unknown), *texts)
    arity_stem = leftover_kind_stem(failure_record(arity), *texts)
    typed_stem = leftover_kind_stem(failure_record(typed), *texts)
    print(f"kind_stem_unknown={unknown_stem!r}", flush=True)
    print(f"kind_stem_arity={arity_stem!r}", flush=True)
    print(f"kind_stem_typed={typed_stem!r}", flush=True)
    if unknown_stem == arity_stem or unknown_stem == typed_stem or arity_stem == typed_stem:
        raise HarnessError(
            "cannot classify unknown-function / invalid-arity / invalid-type "
            f"as distinct after stripping {texts!r}: "
            f"unknown={unknown_stem!r} arity={arity_stem!r} typed={typed_stem!r}"
        )
    assert_kind_stems_differ(unknown, arity, *texts)
    assert_kind_stems_differ(unknown, typed, *texts)
    assert_kind_stems_differ(arity, typed, *texts)


def require_document_field_unchanged(document: Any, key: str, before: Any) -> Any:
    """Require ``document[key] == before`` after a search (no write-back).

    A missing key, a non-mapping document, or an unreadable field raises
    — never treated as "unchanged". *before* must be a snapshot, not the
    live field object.
    """
    if not isinstance(key, str) or key == "":
        raise HarnessError(
            f"require_document_field_unchanged key must be a non-empty str, "
            f"got {key!r}"
        )
    if not isinstance(document, dict):
        raise HarnessError(
            f"require_document_field_unchanged requires a mapping document, "
            f"got {type(document)!r}"
        )
    try:
        present = key in document
    except Exception as exc:
        raise HarnessError(
            f"cannot probe document key {key!r}: {exc}"
        ) from exc
    if not present:
        raise HarnessError(
            f"document is missing key {key!r}; cannot observe write-back"
        )
    try:
        after = document[key]
    except Exception as exc:
        raise HarnessError(f"cannot read document[{key!r}]: {exc}") from exc
    print(
        f"document_field key={key!r} before={before!r} after={after!r}",
        flush=True,
    )
    assert after == before, (
        f"document[{key!r}] was rewritten: {after!r} vs snapshot {before!r}"
    )
    return after


__all__ = (
    "assert_three_function_kinds_distinct",
    "compact_json_text",
    "fn_float",
    "fn_ident",
    "fn_int",
    "fn_ordered_floats",
    "fn_ordered_strings",
    "fn_payload",
    "function_kind_texts",
    "host_non_json_value",
    "host_ordinary_text",
    "require_document_field_unchanged",
)
