# feature: F06
"""Observation helpers for comparators and and/or/not (FP-06).

New names only. Sealed F02–F05 helpers are imported, not copied.
A predecessor that is not sealed on this walk is not imported.
A helper that cannot classify its input raises; it never returns
``None``, ``False``, or ``[]`` to mean "no comparison" or "no operand".
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from _harness import CallResult, HarnessError
from F03_helpers import (
    bracket_ident,
    bracket_payload,
    bracket_sentinel_document,
    oneshot_bracket_search,
    require_bracket_value,
)

# Public-oracle tokens this slice must not reuse as process-local idents/payloads.
# F04 sealed ``_fresh_ident`` / ``_fresh_payload`` / ``_fresh_int`` as locals
# and did not export them; F05 sealed ``_baited`` the same way. This slice
# uses the F06-only names ``compare_ident`` / ``compare_payload`` /
# ``runtime_int`` / ``with_sentinel``.
_PUBLIC_IDENTS = frozenset(
    {
        "one",
        "two",
        "three",
        "foo",
        "bar",
        "baz",
        "outer",
        "True",
        "False",
        "Number",
        "EmptyList",
        "Zero",
        "ZeroFloat",
        "emptylist",
        "boolvalue",
        "a",
        "b",
        "c",
        "name",
        "emptyobj",
        "missing",
        "empty_list",
        "empty_string",
        "bool",
        "bad",
        "alsobad",
        "nokey",
    }
)
_PUBLIC_PAYLOADS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "one",
        "two",
        "three",
        "a",
        "b",
        "c",
        "name",
        "2016",
        "2017",
    }
)
_PUBLIC_INTS = frozenset({0, 1, 2, 3, 5})
_PUBLIC_FLOATS = frozenset({0.0, 1.0, 2.0, 3.0, 5.0})
_PUBLIC_DECIMALS = frozenset(
    {Decimal("0"), Decimal("1"), Decimal("2"), Decimal("3"), Decimal("5")}
)
_PUBLIC_STRINGS = frozenset(
    {
        "2016",
        "2017",
        "foo",
        "bar",
        "baz",
        "one",
        "two",
        "three",
        "a",
        "b",
        "c",
        "name",
    }
)


def assert_handled_with_foo_syntax_not_empty_or_incomplete(
    observed: BaseException,
    empty: BaseException,
    incomplete: BaseException,
    syntax: BaseException,
) -> None:
    """L276 carrier for a lone ``=`` on one public entry.

    One branch. *observed* is already a kind of value error. It does
    not use the empty-expression kind of *empty* (a zero-length
    expression) and does not use the incomplete-expression kind of
    *incomplete* (unmatched ``(``). A caller who already handles the
    syntax kind of *syntax* (``foo.`` on the same entry) also handles
    *observed*, including a more specific syntax form. Does not
    compare leftover report text, does not require identical kind
    markers with ``foo.``, and does not name a product exception
    class or a fixed phrase.
    """
    for label, exc in (
        ("observed", observed),
        ("empty", empty),
        ("incomplete", incomplete),
        ("syntax", syntax),
    ):
        if not isinstance(exc, BaseException):
            raise HarnessError(
                f"{label} must be a captured failure, got {type(exc)!r}"
            )
        if not isinstance(exc, ValueError):
            raise HarnessError(
                f"{label} must be a kind of value error, got "
                f"{type(exc).__name__}: {exc!r}"
            )
    empty_kind = type(empty)
    incomplete_kind = type(incomplete)
    syntax_kind = type(syntax)
    print(
        "lone_equals_carrier "
        f"observed={type(observed).__name__} "
        f"empty={empty_kind.__name__} "
        f"incomplete={incomplete_kind.__name__} "
        f"syntax={syntax_kind.__name__}",
        flush=True,
    )
    assert not isinstance(observed, empty_kind), (
        "lone '=' must not use the empty-expression kind marker of a "
        f"zero-length expression; got {type(observed).__name__}"
    )
    assert not isinstance(observed, incomplete_kind), (
        "lone '=' must not use the incomplete-expression kind marker "
        f"of unmatched '('; got {type(observed).__name__}"
    )
    assert isinstance(observed, syntax_kind), (
        "a caller who already handles the syntax kind of 'foo.' must "
        "also handle the lone '=' refusal, including a more specific "
        f"syntax form; got {type(observed).__name__}, "
        f"syntax kind is {syntax_kind.__name__}"
    )


def require_host_true(value: Any) -> bool:
    """Require *value* is the host boolean true, not the number 1.

    A non-boolean — including ``1``, a successful null, or a mapping —
    is unclassifiable and raises. A boolean that is not true is an
    assertion failure.
    """
    if type(value) is not bool:
        raise HarnessError(
            f"expected a host boolean, got {type(value).__name__} {value!r}"
        )
    print(f"host_true={value!r}", flush=True)
    assert value is True, f"expected host True, got {value!r}"
    return value


def require_host_false(value: Any) -> bool:
    """Require *value* is the host boolean false, not the number 0.

    A non-boolean — including ``0``, a successful null, or a mapping —
    is unclassifiable and raises. A boolean that is not false is an
    assertion failure.
    """
    if type(value) is not bool:
        raise HarnessError(
            f"expected a host boolean, got {type(value).__name__} {value!r}"
        )
    print(f"host_false={value!r}", flush=True)
    assert value is False, f"expected host False, got {value!r}"
    return value


def require_int_zero(value: Any) -> int:
    """Require *value* is the host integer 0, not host false and not 0.0.

    L30 / L267: the number 0 is a true value. An or whose first side is
    that integer must return the integer itself. A boolean, a float, or
    the second operand is a classified wrong answer — asserted, not
    swallowed as an unclassified lookup.
    """
    print(f"int_zero={value!r}", flush=True)
    assert type(value) is int, (
        f"expected host int 0, got {type(value).__name__} {value!r}"
    )
    assert value == 0, f"expected 0, got {value!r}"
    assert value is not False, "int 0 must not be host False"
    return value


def require_float_zero(value: Any) -> float:
    """Require *value* is the host float 0.0, not host false and not 0.

    L30 / L267: the number 0.0 is a true value. An or whose first side
    is that float must return the float itself. A boolean, an int, or
    the second operand is a classified wrong answer — asserted, not
    swallowed as an unclassified lookup.
    """
    print(f"float_zero={value!r}", flush=True)
    assert type(value) is float, (
        f"expected host float 0.0, got {type(value).__name__} {value!r}"
    )
    assert value == 0.0, f"expected 0.0, got {value!r}"
    assert value is not False, "float 0.0 must not be host False"
    return value


def require_ordering_null(result: CallResult) -> None:
    """Require a successful ordering comparison whose value is host none.

    Mixed-type ordering (L264 / L278) is success with null, not a
    boolean and not a failure. Returning false, true, or raising is
    not this outcome. A captured exception raises rather than being
    recorded as null.
    """
    if result.exception is not None:
        raise HarnessError(
            "ordering comparison must succeed as null; got "
            f"{type(result.exception).__name__}: {result.exception!r}"
        )
    value = require_bracket_value(result)
    print(f"ordering_null={value!r}", flush=True)
    assert value is None, f"expected successful null, got {value!r}"
    assert value is not False, "mixed-type ordering yielded False, not null"
    assert value is not True, "mixed-type ordering yielded True, not null"


def require_oneshot_ordering_null(expression: str, document: Any) -> None:
    """One-shot *expression* must succeed as host none, not a boolean.

    Mixed-type ordering (L264 / L278) is success with null. A captured
    exception raises rather than being recorded as null. Host false or
    true is a classified wrong answer.
    """
    require_ordering_null(oneshot_bracket_search(expression, document))


def runtime_mixed_order_document() -> tuple[dict[str, str], dict[str, Any]]:
    """Process-local mixed-type sides for ordering (L264 / L278).

    Returns ``(roles, document)``. *roles* maps ``array``, ``object``,
    ``boolean``, ``null``, ``number``, and ``string`` to process-local
    field names. *document* holds those fields: empty array, empty
    object, host false, host none, a non-published integer, and a
    non-published string. Number-versus-string is not a role pair this
    helper licenses — L264 requires at least one array, object,
    boolean, or null side.
    """
    roles = {
        "array": compare_ident(),
        "object": compare_ident(),
        "boolean": compare_ident(),
        "null": compare_ident(),
        "number": compare_ident(),
        "string": compare_ident(),
    }
    if len(set(roles.values())) != 6:
        raise HarnessError(
            f"runtime_mixed_order_document collided field names: {roles!r}"
        )
    number = runtime_int()
    text = compare_payload()
    document = {
        roles["array"]: [],
        roles["object"]: {},
        roles["boolean"]: False,
        roles["null"]: None,
        roles["number"]: number,
        roles["string"]: text,
    }
    print(
        "runtime_mixed_order_document "
        f"number={number!r} string={text!r} roles={roles!r}",
        flush=True,
    )
    return roles, document


def compare_ident() -> str:
    """Process-local identifier that is not a published F06 oracle token.

    A new F06 name: F04 sealed ``_fresh_ident`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    token = bracket_ident()
    assert token not in _PUBLIC_IDENTS, token
    return token


def compare_payload() -> str:
    """Process-local payload that is not a published F06 oracle token.

    A new F06 name: F04 sealed ``_fresh_payload`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    token = bracket_payload()
    assert token not in _PUBLIC_PAYLOADS, token
    return token


def with_sentinel(document: dict) -> dict:
    """Copy *document* and overlay a process-local sentinel pair.

    A new F06 name: F05 sealed ``_baited`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    overlaid = dict(document)
    overlaid.update(bracket_sentinel_document())
    return overlaid


def runtime_int() -> int:
    """Process-local integer that is not a published F06 oracle number.

    A new F06 name: F04 sealed ``_fresh_int`` as a local and did not
    export it, so this slice must not reuse that name. Refuses 0, 1,
    2, 3, and 5. Unclassifiable generation raises rather than falling
    back to a public sample.
    """
    for _ in range(32):
        n = 7 + (int(uuid.uuid4().hex[:4], 16) % 90)
        if type(n) is not int:
            raise HarnessError(f"runtime_int produced a non-int: {n!r}")
        if n not in _PUBLIC_INTS:
            print(f"runtime_int={n}", flush=True)
            return n
    raise HarnessError(
        f"runtime_int could not pick an int outside {_PUBLIC_INTS!r}"
    )


def runtime_int_except(*forbidden: int) -> int:
    """Process-local integer that is not any of *forbidden*.

    ``runtime_int`` already refuses the published 0 / 1 / 2 / 3 / 5.
    This name additionally refuses the caller's already-drawn values so
    a later filter discriminator cannot collide with a kept field and
    keep both mappings (L272). Unclassifiable generation raises rather
    than returning a colliding integer.
    """
    banned = set(forbidden)
    for _ in range(32):
        n = runtime_int()
        if n not in banned:
            print(f"runtime_int_except={n} banned={banned!r}", flush=True)
            return n
    raise HarnessError(
        f"runtime_int_except could not pick an int outside {banned!r}"
    )


def host_ordered_strings() -> tuple[str, str]:
    """Two distinct process-local strings ordered by the host ``<``.

    Returns ``(lesser, greater)``. Equal strings, or a pair the host
    cannot order, raise — never a public ``2016`` / ``2017`` fallback.
    """
    left = bracket_payload()
    right = bracket_payload()
    if left in _PUBLIC_STRINGS or right in _PUBLIC_STRINGS:
        raise HarnessError(
            f"host_ordered_strings reused a public token: {left!r}/{right!r}"
        )
    if left == right:
        raise HarnessError(
            f"host_ordered_strings produced equal strings: {left!r}"
        )
    if left < right:
        print(
            f"host_ordered_strings lesser={left!r} greater={right!r}",
            flush=True,
        )
        return left, right
    if right < left:
        print(
            f"host_ordered_strings lesser={right!r} greater={left!r}",
            flush=True,
        )
        return right, left
    raise HarnessError(
        f"host_ordered_strings cannot classify {left!r} vs {right!r} "
        "under host <"
    )


def host_ordered_floats() -> tuple[float, float]:
    """Two distinct process-local floats ordered by the host ``<``.

    Neither value is a published 0.0 / 1 / 2 / 3 / 5. Equal floats, or
    a pair the host cannot order, raise.
    """
    chosen: list[float] = []
    for _ in range(48):
        whole = 11 + (int(uuid.uuid4().hex[:4], 16) % 900)
        frac = (int(uuid.uuid4().hex[:4], 16) + 1) / 65536.0
        value = float(whole) + float(frac)
        if type(value) is not float:
            raise HarnessError(f"host_ordered_floats produced a non-float: {value!r}")
        if value in _PUBLIC_FLOATS:
            continue
        if any(value == existing for existing in chosen):
            continue
        chosen.append(value)
        if len(chosen) == 2:
            break
    if len(chosen) != 2:
        raise HarnessError("host_ordered_floats could not pick two distinct floats")
    left, right = chosen
    if left < right:
        print(
            f"host_ordered_floats lesser={left!r} greater={right!r}",
            flush=True,
        )
        return left, right
    if right < left:
        print(
            f"host_ordered_floats lesser={right!r} greater={left!r}",
            flush=True,
        )
        return right, left
    raise HarnessError(
        f"host_ordered_floats cannot classify {left!r} vs {right!r} "
        "under host <"
    )


def host_decimal() -> Decimal:
    """Process-local host decimal that is not the published decimal 3.

    The value is greater than 1 so a ``>= `1``` filter keeps it. Public
    0 / 1 / 2 / 3 / 5 are refused rather than used as a fallback.
    """
    for _ in range(32):
        whole = 7 + (int(uuid.uuid4().hex[:3], 16) % 50)
        frac = 10 + (int(uuid.uuid4().hex[:2], 16) % 90)
        text = f"{whole}.{frac}"
        value = Decimal(text)
        if value in _PUBLIC_DECIMALS:
            continue
        if value <= 1:
            raise HarnessError(f"host_decimal must be greater than 1, got {value!r}")
        print(f"host_decimal={value!r}", flush=True)
        return value
    raise HarnessError(
        f"host_decimal could not pick a Decimal outside {_PUBLIC_DECIMALS!r}"
    )


__all__ = (
    "assert_handled_with_foo_syntax_not_empty_or_incomplete",
    "compare_ident",
    "compare_payload",
    "host_decimal",
    "host_ordered_floats",
    "host_ordered_strings",
    "require_float_zero",
    "require_host_false",
    "require_host_true",
    "require_int_zero",
    "require_oneshot_ordering_null",
    "require_ordering_null",
    "runtime_int",
    "runtime_int_except",
    "runtime_mixed_order_document",
    "with_sentinel",
)
