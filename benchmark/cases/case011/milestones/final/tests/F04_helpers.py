# feature: F04
"""Observation helpers for list/object wildcards and filter projections (FP-04).

New names only. Sealed F02 / F03 helpers are imported, not copied.
A predecessor that is not sealed on this walk is not imported.
A helper that cannot classify its input raises; it never returns ``[]``
or ``None`` to mean "no projection" or "no filter result".
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from _harness import HarnessError
from F02_helpers import (
    assert_compile_shares_foo_syntax_kind,
    assert_search_shares_foo_syntax_kind,
)
from F03_helpers import (
    compile_bracket_expression,
    require_bracket_value,
    require_bracket_value_error,
    search_compiled_bracket,
)


def json_literal_text(value: Any) -> str:
    """Render *value* as a backtick JSON literal (host ``json.dumps``, ASCII).

    Public oracles use the PRD's own literal spelling and do not go
    through this helper. Encoding failure raises — never a bare token
    or an empty string standing in for "could not encode".
    """
    try:
        encoded = json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError) as exc:
        raise HarnessError(
            f"cannot JSON-encode literal {value!r}: {exc}"
        ) from exc
    if not isinstance(encoded, str) or encoded == "":
        raise HarnessError(
            f"JSON encoding of {value!r} is not a non-empty string: {encoded!r}"
        )
    text = f"`{encoded}`"
    print(f"json_literal_text={text!r}", flush=True)
    return text


def _freeze_multiset_item(value: Any) -> Any:
    """Stable tag for one array element so True and 1 do not collapse."""
    if value is None:
        return ("null", None)
    if type(value) is bool:
        return ("boolean", value)
    if type(value) is int:
        return ("number", value)
    if type(value) is float:
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, dict):
        return (
            "object",
            tuple(
                sorted((key, _freeze_multiset_item(item)) for key, item in value.items())
            ),
        )
    if isinstance(value, list):
        return ("array", tuple(_freeze_multiset_item(item) for item in value))
    raise HarnessError(
        f"require_array_multiset cannot classify element type {type(value)!r}"
    )


def require_array_multiset(observed: Any, items: Any) -> list:
    """Require *observed* is a list equal to *items* as a multiset.

    Used only for object-wildcard runtime arms (order is unspecified).
    A non-list — including host none, a mapping, or a string — raises.
    A different multiset is an assertion failure, not a sentinel.
    """
    if observed is None or isinstance(observed, (str, dict)):
        raise HarnessError(
            "require_array_multiset requires a list; "
            f"got {type(observed).__name__} {observed!r}"
        )
    if not isinstance(observed, list):
        raise HarnessError(
            f"require_array_multiset requires a list, got {type(observed)!r}"
        )
    if not isinstance(items, (list, tuple)):
        raise HarnessError(
            f"require_array_multiset items must be a list or tuple, "
            f"got {type(items)!r}"
        )
    left = Counter(_freeze_multiset_item(item) for item in observed)
    right = Counter(_freeze_multiset_item(item) for item in items)
    print(
        f"array_multiset observed={observed!r} expected_items={list(items)!r}",
        flush=True,
    )
    assert left == right, (
        f"array as a multiset was {observed!r}, expected the same members "
        f"as {list(items)!r}"
    )
    return observed


def require_one_combined_value(observed: Any, projected: Any) -> Any:
    """Require *observed* is one combined value, not a per-element array.

    L208: and/or after a list wildcard combines the whole projected
    array, not each element. This feature does not fix the combined
    value (operand-return is FP-06). A per-element result is a list of
    the same length as *projected* that is not *projected* itself. The
    projection used as a single operand is one combined value. A
    non-list — including a single boolean — is one combined value.
    *projected* must be a list; otherwise this helper has no answer
    and raises.
    """
    if not isinstance(projected, list):
        raise HarnessError(
            "require_one_combined_value requires a projected list, "
            f"got {type(projected).__name__} {projected!r}"
        )
    print(
        f"one_combined_value observed={observed!r} projected={projected!r}",
        flush=True,
    )
    if observed == projected:
        return observed
    if isinstance(observed, list) and len(observed) == len(projected):
        assert False, (
            f"and/or after a list wildcard combined per element "
            f"({observed!r}); expected one combined value, not a "
            f"per-element array of length {len(projected)}"
        )
    return observed


def assert_search_is_syntax_kind_not_empty_or_incomplete(
    expression: str, document: Any
) -> ValueError:
    """L212: search of an ungrammatical wildcard continuation.

    Value error that shares the syntax kind marker of ``foo.`` and
    does not share the empty-expression kind of a zero-length
    expression or the incomplete-expression kind of unmatched ``(``.
    Does not compare leftover report text.
    """
    observed = assert_search_shares_foo_syntax_kind(expression, document)
    print(
        f"search_syntax_kind_wildcard expression={expression!r}",
        flush=True,
    )
    return observed


def assert_compile_is_syntax_kind_not_empty_or_incomplete(
    expression: str,
) -> ValueError:
    """L212: compile of an ungrammatical wildcard continuation.

    Value error that shares the syntax kind marker of compile of
    ``foo.`` and does not share the empty-expression kind of compile
    of a zero-length expression or the incomplete-expression kind of
    compile of unmatched ``(``. Does not compare leftover report text.
    """
    observed = assert_compile_shares_foo_syntax_kind(expression)
    print(
        f"compile_syntax_kind_wildcard expression={expression!r}",
        flush=True,
    )
    return observed


def require_unsuccessful_compile_path(expression: str, document: Any) -> ValueError:
    """Refuse *expression* on the compile-then-search path (L213 / L214).

    Compile itself being a value error is a legal shape. If compile
    returns a searchable object, searching that object must be a value
    error and must not succeed as host none, as ``[]``, or by yielding
    *document*. A non-searchable compile result raises.
    """
    if not isinstance(expression, str):
        raise HarnessError(
            "require_unsuccessful_compile_path requires str expression, "
            f"got {type(expression)!r}"
        )
    compiled = compile_bracket_expression(expression)
    if compiled.exception is not None:
        exc = require_bracket_value_error(compiled)
        if compiled.value is document:
            raise HarnessError(
                f"compile of {expression!r} yielded the input document"
            )
        print(
            f"unsuccessful_compile_refused expression={expression!r}",
            flush=True,
        )
        return exc
    parsed = require_bracket_value(compiled)
    if parsed is document:
        raise HarnessError(
            f"compile of {expression!r} returned the input document"
        )
    searched = search_compiled_bracket(parsed, document)
    if searched.exception is None:
        raise HarnessError(
            f"search of compiled {expression!r} succeeded "
            f"(value={searched.value!r}); expected a value error, not "
            "successful null, a successful empty array, or the document"
        )
    if searched.value is document:
        raise HarnessError(
            f"compiled search of {expression!r} yielded the input document"
        )
    exc = require_bracket_value_error(searched)
    print(
        f"unsuccessful_compiled_search_failed expression={expression!r}",
        flush=True,
    )
    return exc


__all__ = (
    "assert_compile_is_syntax_kind_not_empty_or_incomplete",
    "assert_search_is_syntax_kind_not_empty_or_incomplete",
    "json_literal_text",
    "require_array_multiset",
    "require_one_combined_value",
    "require_unsuccessful_compile_path",
)
