# feature: F03
"""Observation helpers for index, slice, and one-level flatten (FP-03).

New names only. Sealed F01 / F02 helpers are imported, not copied.
A helper that cannot classify its input raises; it never returns ``[]``
or ``None`` to mean "could not slice" or "flatten failed".
"""

from __future__ import annotations

import uuid
from typing import Any

from _harness import CallResult, HarnessError
from F01_helpers import (
    failure_record,
    leftover_kind_stem,
    oneshot_search,
    require_search_value,
    require_search_value_error,
    search_parsed,
    compile_expression,
)


def require_oneshot_equals(expression: str, document: object, expected: object) -> object:
    """Search *expression* once and require the value to equal *expected*.

    A new F03 name: F02 sealed ``_oneshot_equals`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    value = require_search_value(oneshot_search(expression, document))
    print(
        f"oneshot_equals expression={expression!r} value={value!r} expected={expected!r}",
        flush=True,
    )
    assert value == expected, f"{expression!r} yielded {value!r}, expected {expected!r}"
    return value


def host_slice(sequence: Any, start: Any, stop: Any, step: Any) -> list:
    """Apply the host slice rules to a list and return a new list.

    *sequence* must be a ``list``. A step of ``0``, a string, a mapping,
    or any other non-list is unclassifiable and raises — never a
    character slice or ``[]`` standing in for "could not slice".
    """
    if isinstance(sequence, (str, dict)):
        raise HarnessError(
            f"host_slice refuses a non-list current value: {type(sequence)!r}"
        )
    if not isinstance(sequence, list):
        raise HarnessError(
            f"host_slice requires a list, got {type(sequence)!r}"
        )
    start_b = _slice_bound(start, label="start")
    stop_b = _slice_bound(stop, label="stop")
    if step == 0:
        raise HarnessError("host_slice refuses a step of 0")
    if step is None:
        sliced = sequence[start_b:stop_b]
    else:
        if type(step) is not int:
            raise HarnessError(f"host_slice step must be int or None, got {type(step)!r}")
        sliced = sequence[start_b:stop_b:step]
    if not isinstance(sliced, list):
        raise HarnessError(
            f"host slice of a list must yield a list, got {type(sliced)!r}"
        )
    result = list(sliced)
    print(
        f"host_slice start={start_b!r} stop={stop_b!r} step={step!r} -> {result!r}",
        flush=True,
    )
    return result


def slice_text(start: Any, stop: Any, step: Any) -> str:
    """Render an optional three-part slice as ``[...]`` text.

    A step of ``0`` is refused: a successful expression must not carry
    a zero step. Public oracles are written as the PRD spells them and
    do not go through this helper.
    """
    if step == 0:
        raise HarnessError("slice_text refuses a step of 0")
    start_s = _bound_text(start, label="start")
    stop_s = _bound_text(stop, label="stop")
    if step is None:
        text = f"[{start_s}:{stop_s}]"
    else:
        if type(step) is not int:
            raise HarnessError(f"slice_text step must be int or None, got {type(step)!r}")
        text = f"[{start_s}:{stop_s}:{step}]"
    print(f"slice_text={text!r}", flush=True)
    return text


def in_range_index(length: int) -> int:
    """Process-local index in ``[0, length)``.

    When *length* is greater than 1 the index is never ``0``, so a stub
    that only implements the first element cannot hide behind entropy.
    """
    if type(length) is not int:
        raise HarnessError(f"in_range_index requires int length, got {type(length)!r}")
    if length < 1:
        raise HarnessError(f"in_range_index requires length >= 1, got {length!r}")
    if length == 1:
        return 0
    idx = 1 + (int(uuid.uuid4().hex[:8], 16) % (length - 1))
    if idx <= 0 or idx >= length:
        raise HarnessError(f"in_range_index produced {idx!r} outside [1, {length})")
    print(f"in_range_index length={length} -> {idx}", flush=True)
    return idx


def from_end_index(length: int) -> int:
    """Process-local ``k`` in ``[2, length]`` so ``[-k]`` is not the last item."""
    if type(length) is not int:
        raise HarnessError(f"from_end_index requires int length, got {type(length)!r}")
    if length < 3:
        raise HarnessError(f"from_end_index requires length >= 3, got {length!r}")
    k = 2 + (int(uuid.uuid4().hex[:8], 16) % (length - 1))
    if k < 2 or k > length:
        raise HarnessError(f"from_end_index produced {k!r} outside [2, {length}]")
    position = length - k
    if position == length - 1:
        raise HarnessError(f"from_end_index k={k} still names the last element")
    print(f"from_end_index length={length} k={k} position={position}", flush=True)
    return k


def assert_kind_stems_differ(
    left: BaseException, right: BaseException, *texts: str
) -> None:
    """Assert two value-error kind stems differ after stripping *texts*.

    Kind is ``leftover_kind_stem`` (expression texts, then digits and
    whitespace). When one expression is a prefix of the other, the
    caller must put the longer text first. Does not compare exception
    class identity.
    """
    left_stem = leftover_kind_stem(failure_record(left), *texts)
    right_stem = leftover_kind_stem(failure_record(right), *texts)
    print(f"kind_stem_left={left_stem!r}", flush=True)
    print(f"kind_stem_right={right_stem!r}", flush=True)
    assert left_stem != right_stem, (
        "failure kind stems are not distinct after stripping "
        f"{texts!r} and length/padding covariates: {left_stem!r}"
    )


def require_step_zero_search_failure(expression: str, document: Any) -> ValueError:
    """One-shot search of a step-0 slice must be a value error.

    The call must not succeed as ``[]``, as host none, or by yielding
    *document*. Unclassifiable outcomes raise.
    """
    if not isinstance(expression, str):
        raise HarnessError(
            f"require_step_zero_search_failure requires str expression, "
            f"got {type(expression)!r}"
        )
    result = oneshot_search(expression, document)
    if result.exception is None:
        raise HarnessError(
            f"step-0 search of {expression!r} succeeded "
            f"(value={result.value!r}); expected a value error, not a "
            "successful empty array, successful null, or the document"
        )
    if result.value is document:
        raise HarnessError(
            f"step-0 search of {expression!r} yielded the input document"
        )
    exc = require_search_value_error(result)
    print(f"step_zero_failure expression={expression!r}", flush=True)
    return exc


def require_successful_empty_array(result: CallResult) -> list:
    """Return the value of a successful search that yielded ``[]``.

    Successful host none is a different outcome and raises. A captured
    exception is a harness failure, never ``[]``.
    """
    value = require_search_value(result)
    if result.exception is not None:
        raise HarnessError(
            "successful empty array must have no exception; "
            f"got {type(result.exception).__name__}: {result.exception!r}"
        )
    if value is None:
        raise HarnessError("expected a successful empty array; got successful null")
    if value != []:
        raise HarnessError(f"expected a successful empty array; got {value!r}")
    print("successful_empty_array=[]", flush=True)
    return value


def require_step_zero_compile_path_failure(
    expression: str, document: Any
) -> ValueError:
    """Refuse a step-0 slice on the compile-then-search path.

    Compile may itself be a value error (a legal shape). If compile
    returns a searchable object, searching that object must be a value
    error and must not succeed as ``[]``.
    """
    if not isinstance(expression, str):
        raise HarnessError(
            f"require_step_zero_compile_path_failure requires str, "
            f"got {type(expression)!r}"
        )
    compiled = compile_expression(expression)
    if compiled.exception is not None:
        exc = require_search_value_error(compiled)
        print(f"step_zero_compile_refused expression={expression!r}", flush=True)
        return exc
    parsed = require_search_value(compiled)
    searched = search_parsed(parsed, document)
    if searched.exception is None:
        raise HarnessError(
            f"search of compiled {expression!r} succeeded "
            f"(value={searched.value!r}); step 0 must not yield []"
        )
    exc = require_search_value_error(searched)
    print(f"step_zero_compiled_search_failed expression={expression!r}", flush=True)
    return exc


def _slice_bound(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise HarnessError(f"host_slice {label} must be int or None, got {type(value)!r}")
    return value


def _bound_text(value: Any, *, label: str) -> str:
    if value is None:
        return ""
    if type(value) is not int:
        raise HarnessError(f"slice_text {label} must be int or None, got {type(value)!r}")
    return str(value)
