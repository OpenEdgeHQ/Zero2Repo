# feature: F02
"""FP-02: select fields with identifiers and dotted subexpressions.

Assertions follow Full_PRD.original.md FP-02 (L118–L145) together with
the value-error / kind-marker rules at L63 and L107. Indexing is
FP-03; wildcards are FP-04. Evaluation options are not supplied.
"""

from __future__ import annotations

import pytest
from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F02_helpers import (
    assert_compile_handled_as_more_specific_syntax,
    assert_compile_shares_foo_syntax_kind,
    assert_field_compile_is_value_error,
    assert_field_search_is_value_error,
    assert_search_handled_as_more_specific_syntax,
    assert_search_shares_foo_syntax_kind,
    compile_once_then_search,
    field_ident,
    field_payload,
    field_sentinel_document,
    join_tokens,
    oneshot_field_search,
    quoted_ident_text,
    quoted_ident_with_runtime_unicode_escape,
    require_field_null,
    require_field_value,
    runtime_dotted_field_key,
    runtime_illegal_escape_expression,
    runtime_interior_underscore_ident,
    runtime_leading_underscore_ident,
    runtime_unquotable_key,
)

_CORRECT_DOC = {"foo": {"bar": {"baz": "correct"}}}
_CORRECT_INNER = {"bar": {"baz": "correct"}}
_CORRECT_BAR = {"baz": "correct"}

_LF_BETWEEN_TOKENS = "foo\n.\nbar\n.baz"
_BROKEN_DOTS = ("foo.", ".foo", "foo..bar", "foo.bar.")
_BETWEEN_TOKEN_GAPS = (" ", "\t", "\r")


def _oneshot_equals(expression: str, document: object, expected: object) -> object:
    value = require_field_value(oneshot_field_search(expression, document))
    print(
        f"oneshot_equals expression={expression!r} value={value!r} expected={expected!r}",
        flush=True,
    )
    assert value == expected, f"{expression!r} yielded {value!r}, expected {expected!r}"
    return value


# ---------------------------------------------------------------------------
# A. Unquoted identifiers select nested fields
# ---------------------------------------------------------------------------


def test_unquoted_foo_chain_yields_nested_layers():
    foo = _oneshot_equals("foo", _CORRECT_DOC, _CORRECT_INNER)
    assert foo != _CORRECT_DOC
    _oneshot_equals("foo.bar", _CORRECT_DOC, _CORRECT_BAR)
    leaf = _oneshot_equals("foo.bar.baz", _CORRECT_DOC, "correct")
    assert leaf != _CORRECT_DOC
    assert leaf != _CORRECT_INNER


def test_unquoted_underscore_and_digit_idents():
    _oneshot_equals("__L", {"__L": True}, True)
    _oneshot_equals("Y_1623", {"Y_1623": True}, True)


def test_runtime_unquoted_chain_yields_payload():
    leading = runtime_leading_underscore_ident()
    interior = runtime_interior_underscore_ident()
    tail = field_ident()
    payload = field_payload()
    document = {leading: {interior: {tail: payload}}}
    expression = f"{leading}.{interior}.{tail}"
    print(
        f"runtime_unquoted leading={leading!r} interior={interior!r} tail={tail!r}",
        flush=True,
    )
    assert leading.startswith("_") and leading != "__L"
    assert "_" in interior[1:] and interior != "Y_1623"
    value = _oneshot_equals(expression, document, payload)
    assert value is not document


def test_compile_then_search_foo_bar_baz():
    value = compile_once_then_search("foo.bar.baz", _CORRECT_DOC)
    assert value == "correct"
    assert value != _CORRECT_DOC


def test_compile_then_search_runtime_unquoted_chain():
    leading = runtime_leading_underscore_ident()
    interior = runtime_interior_underscore_ident()
    tail = field_ident()
    payload = field_payload()
    assert payload != "correct"
    document = {leading: {interior: {tail: payload}}}
    expression = f"{leading}.{interior}.{tail}"
    value = compile_once_then_search(expression, document)
    assert value == payload
    assert value != "correct"


# ---------------------------------------------------------------------------
# B. Whitespace between tokens does not change meaning
# ---------------------------------------------------------------------------


def test_line_feeds_between_tokens_yield_correct():
    baseline = _oneshot_equals("foo.bar.baz", _CORRECT_DOC, "correct")
    with_feeds = _oneshot_equals(_LF_BETWEEN_TOKENS, _CORRECT_DOC, "correct")
    assert baseline == with_feeds == "correct"


def test_space_tab_cr_between_tokens_same_meaning():
    baseline = _oneshot_equals("foo.bar.baz", _CORRECT_DOC, "correct")
    for gap in _BETWEEN_TOKEN_GAPS:
        expression = join_tokens("foo", ".", "bar", ".", "baz", gap=gap)
        print(f"public_ws_gap={gap!r} expression={expression!r}", flush=True)
        assert gap in expression, (
            f"between-token gap {gap!r} must appear in {expression!r}"
        )
        assert expression != "foo.bar.baz"
        value = _oneshot_equals(expression, _CORRECT_DOC, "correct")
        assert value == baseline


def test_runtime_path_with_whitespace_between_tokens():
    k1 = field_ident()
    k2 = field_ident()
    k3 = field_ident()
    payload = field_payload()
    document = {k1: {k2: {k3: payload}}}
    compact = f"{k1}.{k2}.{k3}"
    compact_value = _oneshot_equals(compact, document, payload)
    for gap in _BETWEEN_TOKEN_GAPS:
        expression = join_tokens(k1, ".", k2, ".", k3, gap=gap)
        print(f"runtime_ws_gap={gap!r} expression={expression!r}", flush=True)
        assert gap in expression, (
            f"between-token gap {gap!r} must appear in {expression!r}"
        )
        assert expression != compact
        value = _oneshot_equals(expression, document, payload)
        assert value == compact_value


# ---------------------------------------------------------------------------
# C. Quoted identifiers name fields an unquoted identifier cannot
# ---------------------------------------------------------------------------


def test_quoted_dotted_key_is_one_field_not_a_walk():
    walk_decoy = field_payload()
    document = {"foo.bar": "dot", "foo": {"bar": walk_decoy}}
    expression = quoted_ident_text("foo.bar")
    value = _oneshot_equals(expression, document, "dot")
    assert value != walk_decoy


def test_runtime_quoted_dotted_key_is_one_field_not_a_walk():
    key, left, right = runtime_dotted_field_key()
    payload = field_payload()
    walk_decoy = field_payload()
    document = {key: payload, left: {right: walk_decoy}}
    expression = quoted_ident_text(key)
    value = _oneshot_equals(expression, document, payload)
    assert value != walk_decoy


def test_quoted_spaced_and_unicode_and_digit_keys():
    digit_array = [field_payload(), field_payload()]
    document = {
        "foo bar": "space",
        "☯": True,
        "foo": {"1": digit_array},
    }
    _oneshot_equals(quoted_ident_text("foo bar"), document, "space")
    yinyang = '"☯"'
    assert "\\u" not in yinyang
    _oneshot_equals(yinyang, document, True)
    selected = _oneshot_equals('foo."1"', document, digit_array)
    assert selected is digit_array or selected == digit_array
    assert_search_shares_foo_syntax_kind("foo.1", document)


def test_quoted_hyphenated_key_selects_hyphenated_field():
    payload = field_payload()
    document = {"foo-bar": payload}
    value = _oneshot_equals(quoted_ident_text("foo-bar"), document, payload)
    assert value == payload
    assert_search_handled_as_more_specific_syntax("foo-bar", document)


def test_quoted_ident_does_not_include_quote_characters_in_the_key():
    quoted_decoy = field_payload()
    document = {"foo.bar": "dot", '"foo.bar"': quoted_decoy}
    value = _oneshot_equals(quoted_ident_text("foo.bar"), document, "dot")
    assert value != quoted_decoy


def test_runtime_quoted_key_unquoted_cannot_name():
    key = runtime_unquotable_key()
    payload = field_payload()
    document = {key: payload}
    expression = quoted_ident_text(key)
    _oneshot_equals(expression, document, payload)


def test_runtime_quoted_chain_selects_nested_unquotable_fields():
    k1 = runtime_unquotable_key()
    k2 = runtime_unquotable_key()
    assert k1 != k2
    payload = field_payload()
    walk_decoy = field_payload()
    concat_decoy = field_payload()
    outer = field_ident()
    document = {
        k1: {k2: payload},
        f"{k1}.{k2}": concat_decoy,
        outer: {field_ident(): walk_decoy},
    }
    expression = f"{quoted_ident_text(k1)}.{quoted_ident_text(k2)}"
    value = _oneshot_equals(expression, document, payload)
    assert value != walk_decoy
    assert value != concat_decoy


def test_compile_then_search_quoted_dotted_key():
    walk_decoy = field_payload()
    document = {"foo.bar": "dot", "foo": {"bar": walk_decoy}}
    value = compile_once_then_search(quoted_ident_text("foo.bar"), document)
    assert value == "dot"
    assert value != walk_decoy


def test_compile_then_search_runtime_quoted_key():
    key, left, right = runtime_dotted_field_key()
    payload = field_payload()
    assert payload != "dot"
    walk_decoy = field_payload()
    document = {key: payload, left: {right: walk_decoy}}
    value = compile_once_then_search(quoted_ident_text(key), document)
    assert value == payload
    assert value != "dot"
    assert value != walk_decoy


# ---------------------------------------------------------------------------
# D. Quoted identifiers interpret JSON string escapes
# ---------------------------------------------------------------------------


def test_quoted_newline_escape_selects_lf_key_not_backslash_n():
    lf_payload = field_payload()
    decoy_payload = field_payload()
    document = {"foo\nbar": lf_payload, "foo\\nbar": decoy_payload}
    expression = quoted_ident_text("foo\nbar")
    assert "\\n" in expression
    value = _oneshot_equals(expression, document, lf_payload)
    assert value != decoy_payload


def test_quoted_tab_unicode_and_embedded_quote_escapes():
    tab_payload = field_payload()
    tab_decoy = field_payload()
    quote_payload = field_payload()
    tab_key = "\tF\uCebb"
    tab_expr = '"\\tF\\uCebb"'
    document = {
        tab_key: tab_payload,
        "\\tF\\uCebb": tab_decoy,
        'foo"bar': quote_payload,
    }
    tab_value = _oneshot_equals(tab_expr, document, tab_payload)
    assert tab_value != tab_decoy
    quote_expr = quoted_ident_text('foo"bar')
    _oneshot_equals(quote_expr, document, quote_payload)


def test_runtime_quoted_json_string_selects_decoded_key():
    expression, decoded = quoted_ident_with_runtime_unicode_escape()
    assert r"\u" in expression
    payload = field_payload()
    decoy_payload = field_payload()
    literal_escape = expression[1:-1]
    document = {decoded: payload, literal_escape: decoy_payload}
    value = _oneshot_equals(expression, document, payload)
    assert value != decoy_payload


# ---------------------------------------------------------------------------
# E. A field on a non-object is successful null, not a projection
# ---------------------------------------------------------------------------


def test_field_on_array_of_objects_is_null_not_projection():
    baseline = _oneshot_equals("foo.bar", {"foo": {"bar": "one"}}, "one")
    assert baseline == "one"
    array_doc = {"foo": [{"bar": "one"}, {"bar": "two"}]}
    require_field_null(oneshot_field_search("foo.bar", array_doc))
    observed = require_field_value(oneshot_field_search("foo.bar", array_doc))
    print(f"array_field_value={observed!r}", flush=True)
    assert observed is None
    assert observed != ["one", "two"]
    assert observed != ["one"]


def test_field_on_non_object_leaf_is_successful_null():
    baseline = _oneshot_equals("foo.bar", {"foo": {"bar": "one"}}, "one")
    assert baseline == "one"
    require_field_null(oneshot_field_search("foo.bar", {"foo": "not-an-object"}))
    require_field_null(oneshot_field_search("foo.bar", {"foo": 7}))


def test_runtime_field_on_non_object_is_successful_null():
    root = field_ident()
    field = field_ident()
    p1 = field_payload()
    p2 = field_payload()
    live = field_payload()
    expression = f"{root}.{field}"
    baseline = _oneshot_equals(expression, {root: {field: live}}, live)
    assert baseline == live
    array_doc = {root: [{field: p1}, {field: p2}]}
    require_field_null(oneshot_field_search(expression, array_doc))
    observed = require_field_value(oneshot_field_search(expression, array_doc))
    print(f"runtime_array_field={observed!r} bait={[p1, p2]!r}", flush=True)
    assert observed is None
    assert observed != [p1, p2]
    require_field_null(oneshot_field_search(expression, {root: "leaf-string"}))
    require_field_null(oneshot_field_search(expression, {root: 11}))


# ---------------------------------------------------------------------------
# F. Illegal unquoted forms are value errors; illegal escape has no kind bucket
# ---------------------------------------------------------------------------


def test_bare_number_after_dot_is_syntax_unlike_quoted_digit():
    digit_array = [field_payload()]
    document = {"foo": {"1": digit_array}}
    selected = _oneshot_equals('foo."1"', document, digit_array)
    assert selected == digit_array
    assert_search_shares_foo_syntax_kind("foo.1", document)
    assert_search_shares_foo_syntax_kind("foo.-11", document)
    assert_compile_shares_foo_syntax_kind("foo.1")
    assert_compile_shares_foo_syntax_kind("foo.-11")


def test_unquoted_hyphen_is_syntax_unlike_quoted_hyphen():
    payload = field_payload()
    document = {"foo-bar": payload}
    _oneshot_equals(quoted_ident_text("foo-bar"), document, payload)
    assert_search_handled_as_more_specific_syntax("foo-bar", document)
    assert_compile_handled_as_more_specific_syntax("foo-bar")


@pytest.mark.parametrize("expression", _BROKEN_DOTS, ids=repr)
def test_broken_dot_forms_are_syntax_value_errors(expression: str):
    document = field_sentinel_document()
    assert_search_shares_foo_syntax_kind(expression, document)


def test_unclosed_quote_is_syntax_value_error():
    fragment = field_ident()
    expression = f'"{fragment}'
    document = field_sentinel_document()
    assert_search_handled_as_more_specific_syntax(expression, document)


def test_illegal_escape_in_quoted_ident_is_value_error():
    expression = runtime_illegal_escape_expression()
    document = field_sentinel_document()
    observed = assert_field_search_is_value_error(expression, document)
    print(f"illegal_escape_exc={observed!r}", flush=True)
    result = oneshot_field_search(expression, document)
    assert result.exception is not None
    assert result.value is not document
    assert result.value is not None or result.exception is not None


def test_compile_refuses_trailing_dot_and_unclosed_quote():
    assert_compile_shares_foo_syntax_kind("foo.bar.")
    fragment = field_ident()
    assert_compile_handled_as_more_specific_syntax(f'"{fragment}')


def test_compile_refuses_illegal_escape():
    expression = runtime_illegal_escape_expression()
    observed = assert_field_compile_is_value_error(expression)
    print(f"compile_illegal_escape={observed!r}", flush=True)
    compiled = assert_field_compile_is_value_error(expression)
    assert compiled is not None


# ---------------------------------------------------------------------------
# G. A missing field is successful null, not a failure
# ---------------------------------------------------------------------------


def test_missing_field_and_missing_chain_are_successful_null():
    document = {"foo": {"bar": 1}}
    baseline = _oneshot_equals("foo.bar", document, 1)
    assert baseline == 1
    require_field_null(oneshot_field_search("foo.bad", document))
    require_field_null(oneshot_field_search("bad.morebad.morebad", document))


def test_runtime_missing_segment_is_successful_null():
    k1 = field_ident()
    k2 = field_ident()
    payload = field_payload()
    expression = f"{k1}.{k2}"
    _oneshot_equals(expression, {k1: {k2: payload}}, payload)
    require_field_null(oneshot_field_search(expression, {k1: {field_ident(): field_payload()}}))


def test_runtime_missing_quoted_field_is_successful_null():
    key = runtime_unquotable_key()
    payload = field_payload()
    expression = quoted_ident_text(key)
    _oneshot_equals(expression, {key: payload}, payload)
    missing = {field_ident(): field_payload()}
    result = oneshot_field_search(expression, missing)
    require_field_null(result)
    assert result.exception is None
