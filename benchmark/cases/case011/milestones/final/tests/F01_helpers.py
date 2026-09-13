# feature: F01
"""Observation helpers for the two public search/compile entries (FP-01).

Helpers classify outcomes of the one-shot search entry, the compile
entry, and a search of a parsed expression. They never return ``None``
or the input document to mean "the call could not be classified".
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from _harness import CallResult, HarnessError, call, call_method, require_value, require_value_error

# Attribute name of the search callable on a successful compile result.
PARSED_SEARCH = "search"

_RESERVED_IDENTS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "other",
        "correct",
        "missing",
        "one",
        "two",
        "three",
        "found",
        "bad",
    }
)


def _search_entry() -> Callable[..., Any]:
    """Return the public one-shot search callable from the package root."""
    from pathsel import search

    if not callable(search):
        raise HarnessError("search entry is not callable")
    return search


def _compile_entry() -> Callable[..., Any]:
    """Return the public compile callable from the package root."""
    from pathsel import compile as compile_entry

    if not callable(compile_entry):
        raise HarnessError("compile entry is not callable")
    return compile_entry


def oneshot_search(expression: str, document: Any) -> CallResult:
    """Search *expression* against *document* through the one-shot entry."""
    if not isinstance(expression, str):
        raise HarnessError(f"oneshot_search requires str expression, got {type(expression)!r}")
    print(f"oneshot expression={expression!r}", flush=True)
    return call(_search_entry(), expression, document)


def compile_expression(expression: str) -> CallResult:
    """Compile *expression* through the compile entry."""
    if not isinstance(expression, str):
        raise HarnessError(
            f"compile_expression requires str expression, got {type(expression)!r}"
        )
    print(f"compile expression={expression!r}", flush=True)
    return call(_compile_entry(), expression)


def search_parsed(parsed: Any, document: Any) -> CallResult:
    """Search a compiled expression against *document* (no new compile)."""
    if parsed is None:
        raise HarnessError("search_parsed has no parsed expression to search")
    print("search_parsed", flush=True)
    return call_method(parsed, PARSED_SEARCH, document)


def require_search_value(result: CallResult) -> Any:
    """Return the value of a successful search or compile.

    A successful host none is returned as ``None``. A captured exception
    is a harness failure, never a silent none.
    """
    value = require_value(result)
    print(f"search_value={value!r}", flush=True)
    return value


def require_search_value_error(result: CallResult) -> ValueError:
    """Return the captured exception when it is a kind of value error.

    Hard-fails if the call returned a value or raised something that is
    not a value error. The exception type and repr go in the message.
    """
    if result.exception is None:
        raise HarnessError(
            "call returned a value; expected a value error "
            f"(value={result.value!r}, type={type(result.value)!r})"
        )
    try:
        exc = require_value_error(result)
    except HarnessError:
        raise
    print(f"value_error={type(exc).__name__}: {exc!r}", flush=True)
    return exc


def assert_successful_null(result: CallResult) -> None:
    """Assert a successful search whose value is the host none."""
    value = require_search_value(result)
    assert result.exception is None, (
        "successful null must have no exception; "
        f"got {type(result.exception).__name__}: {result.exception!r}"
    )
    assert value is None, f"expected successful null, got {value!r}"


def require_successful_null(result: CallResult) -> None:
    """Require a successful search whose value is the host none."""
    assert_successful_null(result)


def assert_search_is_value_error(expression: str, document: Any) -> ValueError:
    """Assert that a one-shot search of *expression* is a value error.

    The call must not return *document* and must not succeed as none.
    """
    result = oneshot_search(expression, document)
    assert result.exception is not None, (
        f"search of {expression!r} must not succeed "
        f"(value={result.value!r})"
    )
    exc = require_search_value_error(result)
    assert result.value is not document, "failed search yielded the document"
    return exc


def refuse_search(expression: str, document: Any) -> ValueError:
    """Require that a one-shot search of *expression* is a value error."""
    return assert_search_is_value_error(expression, document)


def assert_compile_is_value_error(expression: str) -> ValueError:
    """Assert that compile of *expression* is a value error.

    Compile must not return a searchable parsed object.
    """
    result = compile_expression(expression)
    assert result.exception is not None, (
        f"compile of {expression!r} must not succeed "
        f"(value={result.value!r})"
    )
    exc = require_search_value_error(result)
    assert result.value is None, (
        "compile returned a parsed object instead of a value error: "
        f"{result.value!r}"
    )
    return exc


def refuse_compile(expression: str) -> ValueError:
    """Require that compile of *expression* is a value error."""
    return assert_compile_is_value_error(expression)


def failure_record(exc: BaseException) -> str:
    """Collect a failure observation: text plus public scalar attributes.

    Does not record ``type(exc)``, ``__name__``, or the MRO. Unreadable
    attributes raise rather than being skipped as absence.
    """
    if not isinstance(exc, BaseException):
        raise HarnessError(f"failure_record expected an exception; got {type(exc)!r}")
    pieces = [str(exc)]
    try:
        names = dir(exc)
    except Exception as err:
        raise HarnessError(f"cannot list attributes of {exc!r}: {err}") from err
    for name in sorted(names):
        if name.startswith("_"):
            continue
        try:
            value = getattr(exc, name)
        except Exception as err:
            raise HarnessError(
                f"cannot read attribute {name!r} from {type(exc).__name__}: {err}"
            ) from err
        if callable(value):
            continue
        if value is None or isinstance(value, (str, int, float)):
            pieces.append(repr(value))
    record = "\n".join(pieces)
    print(f"failure_record_len={len(record)}", flush=True)
    return record


def leftover_after_strip(record: str, *texts: str) -> str:
    """Remove each non-empty expression text from *record*.

    Empty strings are not stripped: replacing ``''`` would rewrite every
    gap between characters and is not a classified observation.
    """
    if not isinstance(record, str):
        raise HarnessError(f"leftover_after_strip requires str record, got {type(record)!r}")
    leftover = record
    for text in texts:
        if not isinstance(text, str):
            raise HarnessError(
                f"leftover_after_strip texts must be str, got {type(text)!r}"
            )
        if text:
            leftover = leftover.replace(text, "")
    return leftover


def leftover_kind_stem(record: str, *texts: str) -> str:
    """Leftover after stripping *texts*, then length and padding covariates.

    Each expression text is removed both as raw input and as ``repr``
    echo (attributes often store the escaped form). Digits (column or
    length echoes) and remaining whitespace are then dropped so two
    reports of the same failure kind can be compared without requiring
    byte-identical wording around those covariates. The stem is
    whatever is left; this helper does not name a product token.
    """
    leftover = record
    for text in texts:
        if not isinstance(text, str):
            raise HarnessError(
                f"leftover_kind_stem texts must be str, got {type(text)!r}"
            )
        if text:
            leftover = leftover.replace(repr(text), "")
    leftover = leftover_after_strip(leftover, *texts)
    return "".join(ch for ch in leftover if not ch.isdigit() and not ch.isspace())


def assert_leftovers_differ(
    left: BaseException, right: BaseException, *texts: str
) -> None:
    """Assert two value-error leftovers differ after stripping *texts*.

    The contrast is the leftover, not exception class identity.
    """
    left_rec = leftover_after_strip(failure_record(left), *texts)
    right_rec = leftover_after_strip(failure_record(right), *texts)
    print(f"leftover_left={left_rec!r}", flush=True)
    print(f"leftover_right={right_rec!r}", flush=True)
    assert left_rec != right_rec, (
        "failure leftovers are not distinct after stripping "
        f"expression texts {texts!r}: {left_rec!r}"
    )


def kinds_leftover_differ(left: BaseException, right: BaseException, *texts: str) -> None:
    """Require two value-error observations to differ after stripping *texts*."""
    assert_leftovers_differ(left, right, *texts)


def assert_kind_stems_match(
    left: BaseException, right: BaseException, *texts: str
) -> None:
    """Assert two value-error observations are the same failure kind.

    Kind is the leftover stem after stripping *texts* and dropping digit
    and whitespace covariates. Reports need not be byte-identical.
    Exception class identity is not compared.
    """
    left_stem = leftover_kind_stem(failure_record(left), *texts)
    right_stem = leftover_kind_stem(failure_record(right), *texts)
    print(f"kind_stem_left={left_stem!r}", flush=True)
    print(f"kind_stem_right={right_stem!r}", flush=True)
    assert left_stem == right_stem, (
        "failure kind stems differ after stripping expression texts "
        f"{texts!r} and length/padding covariates: "
        f"{left_stem!r} vs {right_stem!r}"
    )


def kinds_leftover_same(left: BaseException, right: BaseException, *texts: str) -> None:
    """Require two value-error observations to be the same failure kind."""
    assert_kind_stems_match(left, right, *texts)


def kind_marker(exc: BaseException) -> type:
    """Caller-visible FP-01 kind marker of a captured value error.

    The marker is the type object of the captured exception. It does not
    vary with the expression text and is not the wording of any report.
    Two failures are the same kind exactly when they share this marker,
    and different kinds when the markers differ. Does not name a
    product exception class, a fixed phrase, or leftover identity after
    stripping.
    """
    if not isinstance(exc, BaseException):
        raise HarnessError(
            f"kind_marker expected an exception; got {type(exc)!r}"
        )
    if not isinstance(exc, ValueError):
        raise HarnessError(
            "kind_marker requires a kind of value error, got "
            f"{type(exc).__name__}: {exc!r}"
        )
    marker = type(exc)
    print(f"kind_marker={marker.__name__}", flush=True)
    return marker


def assert_kind_markers_match(
    left: BaseException, right: BaseException
) -> None:
    """Assert two value errors share the FP-01 kind marker.

    Same kind is exact marker identity. Subclassing is not same-kind:
    a more specific type is a different marker. Does not compare
    leftover report text.
    """
    left_m = kind_marker(left)
    right_m = kind_marker(right)
    print(
        f"kind_marker_match left={left_m.__name__} right={right_m.__name__}",
        flush=True,
    )
    assert left_m is right_m, (
        "failures must share a kind marker that does not vary with "
        "the expression text and is not report wording; "
        f"got {left_m.__name__} vs {right_m.__name__}"
    )


def assert_kind_markers_differ(
    left: BaseException, right: BaseException
) -> None:
    """Assert two value errors present different FP-01 kind markers."""
    left_m = kind_marker(left)
    right_m = kind_marker(right)
    print(
        f"kind_marker_differ left={left_m.__name__} right={right_m.__name__}",
        flush=True,
    )
    assert left_m is not right_m, (
        "kind markers must differ; both are "
        f"{left_m.__name__}"
    )


def _require_value_error_kinds(
    observed: BaseException,
    empty: BaseException,
    incomplete: BaseException,
    syntax: BaseException,
) -> None:
    """Hard-fail unless each argument is a captured kind of value error."""
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


def assert_shares_foo_syntax_kind_not_empty_or_incomplete(
    observed: BaseException,
    empty: BaseException,
    incomplete: BaseException,
    syntax: BaseException,
) -> None:
    """L107 remaining same-way cases: exact marker identity with ``foo.``.

    Same kind is exact marker identity, not a parent-kind test that
    would treat incomplete-expression as sharing ``foo.``'s marker.
    The marker differs from a zero-length expression and from
    unmatched ``(``. Does not compare leftover report text.
    """
    _require_value_error_kinds(observed, empty, incomplete, syntax)
    print(
        "same_way_syntax_kind "
        f"observed={type(observed).__name__} "
        f"empty={type(empty).__name__} "
        f"incomplete={type(incomplete).__name__} "
        f"syntax={type(syntax).__name__}",
        flush=True,
    )
    assert_kind_markers_match(observed, syntax)
    assert_kind_markers_differ(observed, empty)
    assert_kind_markers_differ(observed, incomplete)


def assert_shares_incomplete_kind_not_syntax_or_empty(
    observed: BaseException,
    empty: BaseException,
    incomplete: BaseException,
    syntax: BaseException,
) -> None:
    """Lone ``[``, ``{``, or ``(``: exact marker identity with unmatched ``(``.

    Same kind is exact marker identity with unmatched ``(``. The
    marker differs from ``foo.`` and from a zero-length expression.
    Does not compare leftover report text.
    """
    _require_value_error_kinds(observed, empty, incomplete, syntax)
    print(
        "incomplete_kind "
        f"observed={type(observed).__name__} "
        f"empty={type(empty).__name__} "
        f"incomplete={type(incomplete).__name__} "
        f"syntax={type(syntax).__name__}",
        flush=True,
    )
    assert_kind_markers_match(observed, incomplete)
    assert_kind_markers_differ(observed, empty)
    assert_kind_markers_differ(observed, syntax)


def assert_handled_as_more_specific_syntax_not_foo_marker(
    observed: BaseException,
    empty: BaseException,
    incomplete: BaseException,
    syntax: BaseException,
) -> None:
    """L107 more-specific-form carrier for a syntax refusal that is not ``foo.``.

    *observed* is already a kind of value error. It does not use the
    empty-expression kind of *empty* (a zero-length expression) and
    does not use the incomplete-expression kind of *incomplete*
    (unmatched ``(``). A caller who already handles the syntax kind of
    *syntax* (``foo.`` on the same entry) also handles *observed*,
    including a more specific syntax form. The two syntax forms do
    not share identical kind markers. Does not compare leftover report
    text, does not name a product exception class, and does not pin
    a fixed phrase.
    """
    _require_value_error_kinds(observed, empty, incomplete, syntax)
    empty_kind = type(empty)
    incomplete_kind = type(incomplete)
    syntax_kind = type(syntax)
    print(
        "more_specific_syntax_carrier "
        f"observed={type(observed).__name__} "
        f"empty={empty_kind.__name__} "
        f"incomplete={incomplete_kind.__name__} "
        f"syntax={syntax_kind.__name__}",
        flush=True,
    )
    assert not isinstance(observed, empty_kind), (
        "this more-specific syntax form must not use the empty-expression "
        "kind marker of a zero-length expression; "
        f"got {type(observed).__name__}"
    )
    assert not isinstance(observed, incomplete_kind), (
        "this more-specific syntax form must not use the incomplete-"
        "expression kind marker of unmatched '('; "
        f"got {type(observed).__name__}"
    )
    if not isinstance(observed, syntax_kind):
        raise AssertionError(
            "a caller who already handles the syntax kind of 'foo.' must "
            "also handle this refusal, including a more specific syntax "
            f"form; got {type(observed).__name__}, "
            f"syntax kind is {syntax_kind.__name__}"
        )
    assert_kind_markers_differ(observed, syntax)


def runtime_ident() -> str:
    """Process-local Latin identifier that is not a public oracle token."""
    token = "k" + uuid.uuid4().hex[:12]
    if token in _RESERVED_IDENTS:
        raise HarnessError(f"runtime_ident collided with a reserved token: {token}")
    return token


def runtime_payload() -> str:
    """Process-local string payload that is not a public oracle token."""
    token = "v" + uuid.uuid4().hex
    if token in _RESERVED_IDENTS:
        raise HarnessError(f"runtime_payload collided with a reserved token: {token}")
    return token


def sentinel_document() -> dict[str, str]:
    """Mapping whose key and value are process-local, not public samples."""
    return {runtime_ident(): runtime_payload()}
