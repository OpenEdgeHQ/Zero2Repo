# feature: F02
"""Observation helpers for identifier and dotted-subexpression selection (FP-02).

New names only. Sealed F01 helpers are imported, not copied. A helper that
cannot classify its input raises; it never returns an empty string or
``None`` to mean "no token" or "lookup failed".
"""

from __future__ import annotations

import json
import string
import uuid
from typing import Any

from _harness import HarnessError
from F01_helpers import (
    assert_compile_is_value_error,
    assert_leftovers_differ,
    assert_search_is_value_error,
    compile_expression,
    require_search_value,
    runtime_ident,
    search_parsed,
)

# Public-oracle tokens this slice must not reuse as process-local names.
_RESERVED = frozenset(
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
        "dot",
        "space",
        "__L",
        "Y_1623",
        "foo.bar",
        "foo bar",
        "foo-bar",
        "1",
    }
)

# JSON string escape letters (and the quote / slash / backslash tokens).
_JSON_ESCAPE_LETTERS = frozenset('"\\/bfnrtu')
_ILLEGAL_ESCAPE_LETTERS = tuple(
    ch for ch in string.ascii_letters if ch not in _JSON_ESCAPE_LETTERS
)

# Public escape-oracle codepoints that a runtime \\u twin must not reuse.
_FORBIDDEN_UNICODE = frozenset({0xCEBB, 0x262F})

_UNQUOTED_BODY = frozenset(string.ascii_letters + string.digits + "_")


def quoted_ident_text(key: str, *, ensure_ascii: bool = True) -> str:
    """Return *key* as a quoted-identifier token (a host JSON string).

    The return value includes the surrounding double quotes. With
    ``ensure_ascii=True``, every non-ASCII code point must appear as a
    ``\\uXXXX`` escape — never as a raw character inside the quotes.
    """
    if not isinstance(key, str):
        raise HarnessError(f"quoted_ident_text requires str key, got {type(key)!r}")
    try:
        text = json.dumps(key, ensure_ascii=ensure_ascii)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"cannot JSON-encode quoted identifier key {key!r}: {exc}") from exc
    if not (len(text) >= 2 and text[0] == '"' and text[-1] == '"'):
        raise HarnessError(
            f"host JSON encoding of {key!r} is not a double-quoted string: {text!r}"
        )
    if ensure_ascii:
        for ch in key:
            if ord(ch) > 127 and r"\u" not in text:
                raise HarnessError(
                    "ensure_ascii=True must emit a \\u escape for non-ASCII "
                    f"in {key!r}; got {text!r}"
                )
    print(f"quoted_ident_text={text!r}", flush=True)
    return text


def join_tokens(*parts: str, gap: str) -> str:
    """Join token spellings with *gap* between each neighbouring pair.

    Empty *parts* or a non-string *gap* is unclassifiable. An empty token
    is rejected rather than silently dropped (that would look like "no
    token was supplied").
    """
    if not parts:
        raise HarnessError("join_tokens requires at least one token")
    if not isinstance(gap, str):
        raise HarnessError(f"join_tokens gap must be str, got {type(gap)!r}")
    tokens: list[str] = []
    for part in parts:
        if not isinstance(part, str):
            raise HarnessError(f"join_tokens tokens must be str, got {type(part)!r}")
        if part == "":
            raise HarnessError("join_tokens tokens must be non-empty")
        tokens.append(part)
    joined = gap.join(tokens)
    print(f"join_tokens gap={gap!r} -> {joined!r}", flush=True)
    return joined


def _require_unquoted_ident(token: str, *, label: str) -> str:
    if not isinstance(token, str) or not token:
        raise HarnessError(f"{label} produced an empty or non-str identifier")
    first = token[0]
    if not (first == "_" or (first.isascii() and first.isalpha())):
        raise HarnessError(f"{label} must start with a Latin letter or '_': {token!r}")
    if any(ch not in _UNQUOTED_BODY for ch in token):
        raise HarnessError(f"{label} is not a legal unquoted identifier: {token!r}")
    if token in _RESERVED:
        raise HarnessError(f"{label} collided with a reserved token: {token}")
    return token


def runtime_leading_underscore_ident() -> str:
    """Process-local unquoted identifier that starts with ``_`` and is not ``__L``."""
    token = "_" + uuid.uuid4().hex[:12]
    if token == "__L":
        raise HarnessError("runtime leading-underscore ident collided with __L")
    if not token.startswith("_"):
        raise HarnessError(f"runtime leading-underscore ident does not start with '_': {token!r}")
    return _require_unquoted_ident(token, label="runtime_leading_underscore_ident")


def runtime_interior_underscore_ident() -> str:
    """Process-local unquoted identifier whose body contains ``_``, not ``Y_1623``."""
    token = "p_" + uuid.uuid4().hex[:10]
    if token == "Y_1623":
        raise HarnessError("runtime interior-underscore ident collided with Y_1623")
    if not (token[0].isascii() and token[0].isalpha()):
        raise HarnessError(
            f"runtime interior-underscore ident must start with a Latin letter: {token!r}"
        )
    if "_" not in token[1:]:
        raise HarnessError(
            f"runtime interior-underscore ident must contain '_' in the body: {token!r}"
        )
    return _require_unquoted_ident(token, label="runtime_interior_underscore_ident")


def quoted_ident_with_runtime_unicode_escape() -> tuple[str, str]:
    """Return ``(expression, decoded_key)`` for a process-local ``\\u`` escape.

    *expression* is ASCII JSON (``ensure_ascii=True``) and must contain
    ``\\u`` plus four hex digits of a BMP code point that is not U+CEBB
    and not U+262F. Missing ``\\u`` is a harness failure, not a fallback
    to a raw Unicode character.
    """
    n = int(uuid.uuid4().hex[:4], 16)
    codepoint = 0x4E00 + (n % 0x2000)
    if codepoint in _FORBIDDEN_UNICODE:
        codepoint = 0x4E00 + ((n + 17) % 0x2000)
    if codepoint in _FORBIDDEN_UNICODE:
        raise HarnessError(f"runtime unicode escape reused a public code point: {codepoint:#06x}")
    if codepoint > 0xFFFF:
        raise HarnessError(f"runtime unicode escape is not BMP: {codepoint:#x}")
    decoded_key = chr(codepoint)
    expression = quoted_ident_text(decoded_key, ensure_ascii=True)
    if r"\u" not in expression:
        raise HarnessError(
            "runtime unicode-escape expression must contain \\u and four hex "
            f"digits; got {expression!r}"
        )
    hex4 = f"{codepoint:04x}"
    if hex4 not in expression.lower():
        raise HarnessError(
            f"runtime unicode-escape expression {expression!r} does not "
            f"contain the four hex digits of U+{hex4.upper()}"
        )
    print(
        f"runtime_unicode_escape expr={expression!r} key={decoded_key!r} "
        f"u+{hex4}",
        flush=True,
    )
    return expression, decoded_key


def runtime_illegal_escape_letter() -> str:
    """ASCII letter that is not a JSON string-escape letter, chosen per process."""
    if not _ILLEGAL_ESCAPE_LETTERS:
        raise HarnessError("no ASCII letters remain outside the JSON escape set")
    idx = int(uuid.uuid4().hex[:2], 16) % len(_ILLEGAL_ESCAPE_LETTERS)
    letter = _ILLEGAL_ESCAPE_LETTERS[idx]
    if letter in _JSON_ESCAPE_LETTERS:
        raise HarnessError(f"illegal-escape letter {letter!r} is a JSON escape letter")
    if len(letter) != 1 or not letter.isascii() or not letter.isalpha():
        raise HarnessError(f"illegal-escape letter is not a single ASCII letter: {letter!r}")
    print(f"illegal_escape_letter={letter!r}", flush=True)
    return letter


def runtime_illegal_escape_expression() -> str:
    """Quoted identifier whose interior has a process-local illegal JSON escape."""
    letter = runtime_illegal_escape_letter()
    fragment = runtime_ident()
    expression = f'"{fragment}\\{letter}"'
    needle = "\\" + letter
    if needle not in expression:
        raise HarnessError(
            f"illegal-escape expression {expression!r} lacks \\{letter}"
        )
    print(f"illegal_escape_expression={expression!r}", flush=True)
    return expression


def runtime_dotted_field_key() -> tuple[str, str, str]:
    """Return ``(key, left, right)`` where *key* is ``left.right``.

    Neither side is a public-oracle token. The key itself contains a dot.
    """
    left = runtime_ident()
    right = runtime_ident()
    if left in _RESERVED or right in _RESERVED:
        raise HarnessError(f"dotted-field side collided with a reserved token: {left!r}/{right!r}")
    if left in {"foo", "bar"} or right in {"foo", "bar"}:
        raise HarnessError(f"dotted-field side reused foo/bar: {left!r}/{right!r}")
    key = f"{left}.{right}"
    if "." not in key:
        raise HarnessError(f"runtime dotted field key must contain a dot: {key!r}")
    print(f"runtime_dotted_key={key!r}", flush=True)
    return key, left, right


def runtime_unquotable_key() -> str:
    """A key an unquoted identifier cannot name, and that is not a dotted key.

    Shape is process-chosen among: a space, a hyphenated token, or a
    digit-leading name. Public ``foo bar`` / ``foo-bar`` / ``1`` are refused.
    """
    kinds = (
        lambda: f"{runtime_ident()} {runtime_ident()}",
        lambda: f"{runtime_ident()}-{runtime_ident()}",
        lambda: f"7{runtime_ident()}",
    )
    idx = int(uuid.uuid4().hex[:2], 16) % len(kinds)
    key = kinds[idx]()
    if key in {"foo bar", "foo-bar", "1", "foo.bar"}:
        raise HarnessError(f"unquotable key collided with a public sample: {key!r}")
    if "." in key:
        raise HarnessError(f"unquotable key must not be a dotted key: {key!r}")
    if key in _RESERVED:
        raise HarnessError(f"unquotable key collided with a reserved token: {key!r}")
    print(f"runtime_unquotable_key={key!r}", flush=True)
    return key


def compile_once_then_search(expression: str, document: Any) -> Any:
    """Compile *expression* once and search the same parsed object twice.

    The second search must use the object already in hand — a new compile
    is not performed. The two searches must agree.
    """
    parsed = require_search_value(compile_expression(expression))
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
    print(
        f"compile_once expression={expression!r} first={first!r} second={second!r}",
        flush=True,
    )
    assert first == second, (
        "second search of the same parsed expression disagreed with the first "
        f"({first!r} vs {second!r}); a new compile must not be required"
    )
    return first


def assert_search_syntax_not_empty_or_incomplete(
    expression: str, document: Any
) -> ValueError:
    """Search *expression* is a value error whose leftover is not empty or '('."""
    observed = assert_search_is_value_error(expression, document)
    empty = assert_search_is_value_error("", document)
    incomplete = assert_search_is_value_error("(", document)
    assert_leftovers_differ(observed, empty, expression, "")
    assert_leftovers_differ(observed, incomplete, expression, "(")
    return observed


def assert_compile_syntax_not_empty_or_incomplete(expression: str) -> ValueError:
    """Compile *expression* is a value error whose leftover is not empty or '('."""
    observed = assert_compile_is_value_error(expression)
    empty = assert_compile_is_value_error("")
    incomplete = assert_compile_is_value_error("(")
    assert_leftovers_differ(observed, empty, expression, "")
    assert_leftovers_differ(observed, incomplete, expression, "(")
    return observed
