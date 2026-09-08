# feature: F05
"""Observation helpers for constructors, pipe, current value, and literals (FP-05).

New names only. Sealed F01–F04 helpers are imported, not copied.
A helper that cannot classify its input raises; it never returns
``None``, ``{}``, or ``[]`` to mean "no constructed result".
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from _harness import CallResult, HarnessError
from F01_helpers import require_search_value, runtime_ident, runtime_payload
from F04_helpers import json_literal_text

# Public-oracle tokens this slice must not reuse as process-local idents/payloads.
# F04 sealed ``_fresh_ident`` / ``_fresh_payload`` as locals and did not export
# them, so this slice uses the F05-only names ``local_ident`` / ``local_payload``.
_PUBLIC_IDENTS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "qux",
        "one",
        "two",
        "subkey",
        "includeme",
        "noexist",
        "nokey",
        "badkey",
        "a",
        "b",
        "nested",
        "first",
        "second",
        "common",
        "other",
        "name",
        "alias",
        "source",
        "missing",
        "keep",
        "inner",
        "field",
    }
)
_PUBLIC_PAYLOADS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "qux",
        "one",
        "two",
        "subkey",
        "first",
        "second",
        "common",
        "a",
        "b",
        "Φ",
        "foo.bar",
    }
)

# Public-oracle tokens this slice must not reuse as process-local fragments.
_PUBLIC_FRAGMENTS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "qux",
        "one",
        "two",
        "subkey",
        "includeme",
        "noexist",
        "nokey",
        "badkey",
        "a",
        "b",
        "nested",
        "first",
        "second",
        "common",
        "other",
        "foo.bar",
        "Φ",
    }
)

# Φ (U+03A6) is the public Unicode-escape oracle; a runtime twin must not reuse it.
_PUBLIC_UNICODE_CODEPOINTS = frozenset({0x03A6})

_FORBIDDEN_IN_BACKTICK_FRAGMENT = frozenset({'"', "\\", "`"})


def local_ident() -> str:
    """Process-local identifier that is not a published F05 oracle token.

    A new F05 name: F04 sealed ``_fresh_ident`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    token = runtime_ident()
    assert token not in _PUBLIC_IDENTS, token
    return token


def local_payload() -> str:
    """Process-local payload that is not a published F05 oracle token.

    A new F05 name: F04 sealed ``_fresh_payload`` as a local and did not
    export it, so this slice must not reuse that name.
    """
    token = runtime_payload()
    assert token not in _PUBLIC_PAYLOADS, token
    return token


def require_mapping(observed: Any) -> Mapping:
    """Require *observed* is a mapping.

    Host none, a list, a string, or any other non-mapping raises — never
    ``{}`` standing in for "could not build a hash".
    """
    if observed is None:
        raise HarnessError("expected a mapping; got successful null")
    if isinstance(observed, (str, list)):
        raise HarnessError(
            f"expected a mapping; got {type(observed).__name__} {observed!r}"
        )
    if not isinstance(observed, Mapping):
        raise HarnessError(
            f"expected a mapping; got {type(observed).__name__} {observed!r}"
        )
    print(f"mapping_keys={list(observed.keys())!r}", flush=True)
    return observed


def require_constructed_list(observed: Any) -> list:
    """Require *observed* is a list.

    Host none, a mapping, or a string raises — never ``[]`` standing in
    for "could not build a list".
    """
    if observed is None:
        raise HarnessError("expected a list; got successful null")
    if isinstance(observed, (str, dict)):
        raise HarnessError(
            f"expected a list; got {type(observed).__name__} {observed!r}"
        )
    if not isinstance(observed, list):
        raise HarnessError(
            f"expected a list; got {type(observed).__name__} {observed!r}"
        )
    print(f"constructed_list_len={len(observed)}", flush=True)
    return observed


def escaped_backtick_string_literal(left: str, right: str) -> str:
    """Return a backtick JSON string whose interior is *left*, backtick, *right*.

    The backtick inside the JSON string is escaped with a backslash
    (L238). Fragments must be non-empty and must not contain a double
    quote, a backslash, or a backtick — those would make the spelling
    unclassifiable. Does not go through ``json_literal_text``
    (``json.dumps`` does not emit ``\\```).
    """
    if not isinstance(left, str) or not isinstance(right, str):
        raise HarnessError(
            "escaped_backtick_string_literal fragments must be str, "
            f"got {type(left)!r} / {type(right)!r}"
        )
    if not left or not right:
        raise HarnessError("escaped_backtick_string_literal fragments must be non-empty")
    for label, fragment in (("left", left), ("right", right)):
        if fragment in _PUBLIC_FRAGMENTS:
            raise HarnessError(
                f"escaped_backtick_string_literal {label} reused a public "
                f"fragment: {fragment!r}"
            )
        for ch in _FORBIDDEN_IN_BACKTICK_FRAGMENT:
            if ch in fragment:
                raise HarnessError(
                    f"escaped_backtick_string_literal {label} contains "
                    f"{ch!r}: {fragment!r}"
                )
    text = f'`"{left}\\`{right}"`'
    if "\\`" not in text:
        raise HarnessError(
            f"escaped backtick literal {text!r} does not contain a "
            "backslash-escaped backtick"
        )
    print(f"escaped_backtick_literal={text!r}", flush=True)
    return text


def runtime_json_unicode_string_literal() -> tuple[str, str]:
    """Return ``(expression, decoded_char)`` for a process-local ``\\uXXXX``.

    *expression* is a backtick JSON string whose interior is an ASCII
    ``\\u`` escape of a BMP code point that is not U+03A6. Missing
    ``\\u`` is a harness failure, not a fallback to a raw character.
    """
    n = int(uuid.uuid4().hex[:4], 16)
    codepoint = 0x4E00 + (n % 0x2000)
    if codepoint in _PUBLIC_UNICODE_CODEPOINTS:
        codepoint = 0x4E00 + ((n + 17) % 0x2000)
    if codepoint in _PUBLIC_UNICODE_CODEPOINTS:
        raise HarnessError(
            f"runtime JSON unicode escape reused U+03A6: {codepoint:#06x}"
        )
    if codepoint > 0xFFFF:
        raise HarnessError(f"runtime JSON unicode escape is not BMP: {codepoint:#x}")
    decoded = chr(codepoint)
    hex4 = f"{codepoint:04x}"
    expression = f'`"\\u{hex4}"`'
    if r"\u" not in expression:
        raise HarnessError(
            "runtime JSON unicode-escape expression must contain \\u and "
            f"four hex digits; got {expression!r}"
        )
    if hex4 not in expression.lower():
        raise HarnessError(
            f"runtime JSON unicode-escape expression {expression!r} does "
            f"not contain the four hex digits of U+{hex4.upper()}"
        )
    print(
        f"runtime_json_unicode expr={expression!r} char={decoded!r} u+{hex4}",
        flush=True,
    )
    return expression, decoded


def unclosed_json_literal_text(value: Any) -> str:
    """Return a backtick JSON literal that is missing its closing backtick.

    Built from the sealed closed form so the interior is the same JSON
    encoding; stripping a closer that is not present raises.
    """
    closed = json_literal_text(value)
    if not isinstance(closed, str) or len(closed) < 2:
        raise HarnessError(
            f"closed JSON literal is too short to strip a closer: {closed!r}"
        )
    if not (closed[0] == "`" and closed[-1] == "`"):
        raise HarnessError(
            f"closed JSON literal is not wrapped in backticks: {closed!r}"
        )
    unclosed = closed[:-1]
    if unclosed.endswith("`"):
        raise HarnessError(
            f"unclosed JSON literal still ends with a backtick: {unclosed!r}"
        )
    print(f"unclosed_json_literal={unclosed!r}", flush=True)
    return unclosed


def raw_string_text(body: str) -> str:
    """Wrap *body* as a raw-string literal.

    *body* must not contain a single quote — a quote-escape form is
    written at the call site so the backslash-then-quote spelling stays
    visible. An empty body is unclassifiable (it would look like no
    text was supplied).
    """
    if not isinstance(body, str):
        raise HarnessError(f"raw_string_text requires str body, got {type(body)!r}")
    if body == "":
        raise HarnessError("raw_string_text body must be non-empty")
    if "'" in body:
        raise HarnessError(
            "raw_string_text body must not contain a single quote; "
            f"got {body!r}"
        )
    text = f"'{body}'"
    print(f"raw_string_text={text!r}", flush=True)
    return text


def require_deferred_reference(
    result: CallResult,
    *,
    document: Any,
    immediates: Any,
) -> Any:
    """Require a successful expression-reference result that is not immediate.

    Success (L240) that is not host none (L61), not the document
    contents, and not any of *immediates* (the values an immediate
    evaluation of the wrapped expression would have produced). Does not
    pin a type name, class, or repr.
    """
    if not isinstance(immediates, (list, tuple)):
        raise HarnessError(
            "require_deferred_reference immediates must be a list or tuple, "
            f"got {type(immediates)!r}"
        )
    if result.exception is not None:
        raise HarnessError(
            "expression reference must succeed; got "
            f"{type(result.exception).__name__}: {result.exception!r}"
        )
    value = require_search_value(result)
    if value is None:
        raise HarnessError("expression reference succeeded as null")
    if value == document:
        raise HarnessError("expression reference yielded the document contents")
    for immediate in immediates:
        if value == immediate:
            raise HarnessError(
                "expression reference evaluated immediately to "
                f"{immediate!r}"
            )
    print(f"deferred_reference_ok type={type(value).__name__}", flush=True)
    return value


__all__ = (
    "local_ident",
    "local_payload",
    "escaped_backtick_string_literal",
    "raw_string_text",
    "require_constructed_list",
    "require_deferred_reference",
    "require_mapping",
    "runtime_json_unicode_string_literal",
    "unclosed_json_literal_text",
)
