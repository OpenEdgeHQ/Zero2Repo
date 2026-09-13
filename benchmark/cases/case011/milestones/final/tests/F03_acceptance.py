# feature: F03
"""FP-03: index, slice, and one-level flatten of arrays.

Assertions follow Full_PRD.original.md FP-03 (L146–L183) together with
null-is-host-none (L23), string-is-not-an-array (L25), value-error
failure (L63), and the four-part slice as a syntax case (L107).
Wildcards and filters are FP-04. Evaluation options are not supplied.
"""

from __future__ import annotations

import uuid

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F02_helpers import (
    assert_compile_shares_foo_syntax_kind,
    assert_search_shares_foo_syntax_kind,
    compile_once_then_search,
)
from F03_helpers import (
    assert_bracket_compile_is_value_error,
    assert_bracket_kind_markers_match,
    assert_bracket_search_is_value_error,
    assert_step_zero_kind_unlike_syntax,
    bracket_ident,
    bracket_kind_marker,
    bracket_payload,
    bracket_sentinel_document,
    compile_bracket_expression,
    from_end_index,
    host_slice,
    in_range_index,
    oneshot_bracket_search,
    require_bracket_null,
    require_bracket_value,
    require_compile_then_search_step_zero_kind,
    require_oneshot_equals,
    require_step_zero_search_failure,
    require_successful_empty_array,
    search_compiled_bracket,
    slice_text,
)

_INDEX_DOC = {"foo": {"bar": ["zero", "one", "two"]}}
_STRING_INDEX_DOC = {"foo": {"bar": [["one", "two"], ["three", "four"]]}}
_FIELD_AFTER_INDEX_DOC = {
    "foo": [
        {"bar": "one"},
        {"bar": "two"},
        {"bar": "three"},
        {"notbar": "four"},
    ]
}
_SLICE_DOC = {"foo": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}
_SLICE_PROJECTION_DOC = {"foo": [{"a": 1}, {"a": 2}, {"a": 3}]}
_REVERSED_NESTED_DOC = {
    "bar": [{"a": {"b": 1}}, {"a": {"b": 2}}, {"a": {"b": 3}}]
}
_TRIPLE_NESTED_DOC = {
    "foo": [
        [["one", "two"], ["three", "four"]],
        [["five", "six"], ["seven", "eight"]],
        [["nine"], ["ten"]],
    ]
}
_FLATTEN_PROJECTION_DOC = {"foo": [{"bar": "one"}, {"notbar": "x"}]}
_SIX_FIRST = ["one", "three", "five", "seven", "nine", "ten"]
_SIX_INNER = [
    ["one", "two"],
    ["three", "four"],
    ["five", "six"],
    ["seven", "eight"],
    ["nine"],
    ["ten"],
]
_TEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
_PUBLIC_INDEX_PAYLOADS = frozenset({"zero", "one", "two", "three", "four", "x"})

_STEP0_PUBLIC = "foo[8:2:0]"
_FOUR_PUBLIC = "foo[8:2:0:1]"


def _runtime_length(lo: int, hi: int, *, forbidden: int | None = None) -> int:
    span = hi - lo + 1
    if span < 1:
        raise AssertionError(f"empty length range {lo}..{hi}")
    for _ in range(8):
        n = lo + (int(uuid.uuid4().hex[:4], 16) % span)
        if forbidden is None or n != forbidden:
            return n
    raise AssertionError(f"could not pick length in {lo}..{hi} avoiding {forbidden!r}")


def _runtime_int(lo: int, hi: int, *, forbidden: frozenset[int] | None = None) -> int:
    span = hi - lo + 1
    blocked = forbidden or frozenset()
    for _ in range(16):
        n = lo + (int(uuid.uuid4().hex[:4], 16) % span)
        if n not in blocked:
            return n
    raise AssertionError(f"could not pick int in {lo}..{hi} avoiding {blocked!r}")


def _payloads(n: int) -> list[str]:
    items = [bracket_payload() for _ in range(n)]
    for item in items:
        assert item not in _PUBLIC_INDEX_PAYLOADS, item
        assert item not in {"foo", "bar", "baz"}, item
    return items


# ---------------------------------------------------------------------------
# A. Zero-based and from-the-end indices select one element
# ---------------------------------------------------------------------------


def test_zero_based_indices_select_named_elements():
    zero = require_oneshot_equals("foo.bar[0]", _INDEX_DOC, "zero")
    one = require_oneshot_equals("foo.bar[1]", _INDEX_DOC, "one")
    two = require_oneshot_equals("foo.bar[2]", _INDEX_DOC, "two")
    assert zero != _INDEX_DOC
    assert one != ["zero", "one", "two"]
    assert two != _INDEX_DOC["foo"]


def test_negative_indices_count_from_the_end():
    last = require_oneshot_equals("foo.bar[-1]", _INDEX_DOC, "two")
    mid = require_oneshot_equals("foo.bar[-2]", _INDEX_DOC, "one")
    first = require_oneshot_equals("foo.bar[-3]", _INDEX_DOC, "zero")
    assert last == "two"
    assert mid == "one"
    assert first == "zero"
    assert last != _INDEX_DOC
    assert mid != ["zero", "one", "two"]
    assert first != _INDEX_DOC["foo"]
    assert last != first


def test_runtime_index_selects_written_element():
    n = _runtime_length(4, 7, forbidden=3)
    items = _payloads(n)
    root = bracket_ident()
    document = {root: items, "bait": bracket_payload()}
    i = in_range_index(n)
    selected = require_oneshot_equals(f"{root}[{i}]", document, items[i])
    assert selected != items
    assert selected is not document
    last = require_oneshot_equals(f"{root}[-1]", document, items[-1])
    assert last == items[n - 1]
    assert last != items[0]
    k = from_end_index(n)
    from_end = require_oneshot_equals(f"{root}[-{k}]", document, items[n - k])
    print(f"runtime_from_end k={k} value={from_end!r} last={items[-1]!r}", flush=True)
    assert from_end != items[-1]
    assert from_end == items[n - k]


def test_compile_then_search_public_index():
    value = compile_once_then_search("foo.bar[0]", _INDEX_DOC)
    assert value == "zero"
    assert value != _INDEX_DOC


def test_compile_then_search_runtime_index():
    n = _runtime_length(4, 7, forbidden=3)
    items = _payloads(n)
    root = bracket_ident()
    document = {root: items}
    i = in_range_index(n)
    pos = compile_once_then_search(f"{root}[{i}]", document)
    assert pos == items[i]
    assert pos not in _PUBLIC_INDEX_PAYLOADS
    k = from_end_index(n)
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[-{k}]"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_runtime_neg k={k} first={first!r} second={second!r}", flush=True)
    assert first == second == items[n - k]
    assert first != items[-1]


# ---------------------------------------------------------------------------
# B. Out-of-range and non-array index are successful null; a field is not
# ---------------------------------------------------------------------------


def test_out_of_range_index_is_successful_null():
    require_oneshot_equals("foo.bar[0]", _INDEX_DOC, "zero")
    require_oneshot_equals("foo.bar[-1]", _INDEX_DOC, "two")
    require_bracket_null(oneshot_bracket_search("foo.bar[3]", _INDEX_DOC))
    require_bracket_null(oneshot_bracket_search("foo.bar[-4]", _INDEX_DOC))
    high = require_bracket_value(oneshot_bracket_search("foo.bar[3]", _INDEX_DOC))
    low = require_bracket_value(oneshot_bracket_search("foo.bar[-4]", _INDEX_DOC))
    assert high is None
    assert low is None
    assert high != "zero"
    assert low != "two"


def test_index_on_object_is_successful_null():
    document = {"foo": {"bar": 1}}
    mapping = require_oneshot_equals("foo", document, {"bar": 1})
    assert mapping == {"bar": 1}
    require_oneshot_equals("foo.bar", document, 1)
    require_bracket_null(oneshot_bracket_search("foo[0]", document))
    observed = require_bracket_value(oneshot_bracket_search("foo[0]", document))
    assert observed is None
    assert observed != document["foo"]


def test_index_on_string_is_successful_null():
    baseline = require_oneshot_equals("foo.bar[0][0]", _STRING_INDEX_DOC, "one")
    assert baseline == "one"
    require_bracket_null(oneshot_bracket_search("foo.bar[0][0][0]", _STRING_INDEX_DOC))
    observed = require_bracket_value(oneshot_bracket_search("foo.bar[0][0][0]", _STRING_INDEX_DOC))
    assert observed is None
    assert observed != "o"
    assert observed != "one"


def test_index_then_field_unlike_field_on_array():
    require_oneshot_equals("foo[0].bar", _FIELD_AFTER_INDEX_DOC, "one")
    require_oneshot_equals("foo[3].notbar", _FIELD_AFTER_INDEX_DOC, "four")
    require_bracket_null(oneshot_bracket_search("foo[3].bar", _FIELD_AFTER_INDEX_DOC))
    require_bracket_null(oneshot_bracket_search("foo.bar", _FIELD_AFTER_INDEX_DOC))
    projected = require_bracket_value(oneshot_bracket_search("foo.bar", _FIELD_AFTER_INDEX_DOC))
    print(f"field_on_array={projected!r}", flush=True)
    assert projected is None
    assert projected != ["one", "two", "three"]


def test_runtime_out_of_range_and_non_array_index_are_successful_null():
    n = _runtime_length(4, 8, forbidden=3)
    items = _payloads(n)
    root = bracket_ident()
    array_doc = {root: items}
    last = require_oneshot_equals(f"{root}[{n - 1}]", array_doc, items[-1])
    assert last == require_oneshot_equals(f"{root}[-1]", array_doc, items[-1])
    require_bracket_null(oneshot_bracket_search(f"{root}[{n}]", array_doc))
    require_bracket_null(oneshot_bracket_search(f"{root}[-{n + 1}]", array_doc))

    payload = bracket_payload()
    string_doc = {root: payload}
    require_bracket_null(oneshot_bracket_search(f"{root}[0]", string_doc))
    mapping = {bracket_ident(): bracket_payload()}
    mapping_doc = {root: mapping}
    require_bracket_null(oneshot_bracket_search(f"{root}[0]", mapping_doc))
    live = require_oneshot_equals(f"{root}[0]", {root: [payload]}, payload)
    assert live == payload
    assert live is not None


# ---------------------------------------------------------------------------
# C. Slice selects a sub-array using host slice rules
# ---------------------------------------------------------------------------


def test_full_slice_omitted_parts_yield_ten_numbers():
    for expression in ("foo[0:10]", "foo[:]", "foo[::]", "foo[0:10:1]"):
        value = require_oneshot_equals(expression, _SLICE_DOC, _TEN)
        assert value == _TEN
        assert value != _SLICE_DOC


def test_named_forward_and_stepped_slices():
    mid = require_oneshot_equals("foo[1:9]", _SLICE_DOC, [1, 2, 3, 4, 5, 6, 7, 8])
    stepped = require_oneshot_equals("foo[0:10:2]", _SLICE_DOC, [0, 2, 4, 6, 8])
    tail = require_oneshot_equals("foo[5:]", _SLICE_DOC, [5, 6, 7, 8, 9])
    assert mid == [1, 2, 3, 4, 5, 6, 7, 8]
    assert stepped == [0, 2, 4, 6, 8]
    assert tail == [5, 6, 7, 8, 9]
    assert mid != _TEN
    assert stepped != _TEN
    assert tail != _TEN
    assert mid != _SLICE_DOC
    assert mid != stepped
    assert stepped != tail


def test_named_reverse_and_negative_bound_slices():
    reversed_all = require_oneshot_equals(
        "foo[::-1]", _SLICE_DOC, [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    )
    stepped_back = require_oneshot_equals("foo[8:2:-2]", _SLICE_DOC, [8, 6, 4])
    neg_bound = require_oneshot_equals("foo[-4:-1]", _SLICE_DOC, [6, 7, 8])
    assert reversed_all == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert stepped_back == [8, 6, 4]
    assert neg_bound == [6, 7, 8]
    assert reversed_all != _TEN
    assert stepped_back != _TEN
    assert neg_bound != _TEN
    assert reversed_all != _SLICE_DOC
    assert stepped_back != reversed_all
    assert neg_bound != stepped_back


def test_out_of_range_slice_is_successful_empty_array():
    live = require_oneshot_equals("foo[:]", _SLICE_DOC, _TEN)
    assert live == _TEN
    assert live != []
    empty = require_successful_empty_array(oneshot_bracket_search("foo[10:-20]", _SLICE_DOC))
    assert empty == []
    assert empty is not None
    result = oneshot_bracket_search("foo[10:-20]", _SLICE_DOC)
    assert result.exception is None
    print(f"out_of_range_slice live={live!r} empty={empty!r}", flush=True)


def test_runtime_slice_follows_host_slice_rules():
    n = _runtime_length(5, 8)
    items = _payloads(n)
    root = bracket_ident()
    document = {root: items}
    forward = (1, None, 2)
    reverse = (-2, 0, -1)
    assert forward != (1, 9, None)
    assert forward != (0, 10, 2)
    assert reverse != (8, 2, -2)
    assert reverse != (-4, -1, None)
    for start, stop, step in (forward, reverse):
        expression = f"{root}{slice_text(start, stop, step)}"
        expected = host_slice(items, start, stop, step)
        value = require_oneshot_equals(expression, document, expected)
        print(
            f"runtime_slice {expression} expected={expected!r} value={value!r}",
            flush=True,
        )
        assert value != [1, 2, 3, 4, 5, 6, 7, 8]
        assert value != _TEN


def test_compile_then_search_public_slice():
    value = compile_once_then_search("foo[1:9]", _SLICE_DOC)
    assert value == [1, 2, 3, 4, 5, 6, 7, 8]


def test_compile_then_search_runtime_slice():
    n = _runtime_length(5, 8)
    items = _payloads(n)
    root = bracket_ident()
    document = {root: items}
    start, stop, step = 1, None, 2
    expression = f"{root}{slice_text(start, stop, step)}"
    expected = host_slice(items, start, stop, step)
    value = compile_once_then_search(expression, document)
    assert value == expected
    assert value != [1, 2, 3, 4, 5, 6, 7, 8]


# ---------------------------------------------------------------------------
# D. A slice is a projection; a slice of a non-array is null
# ---------------------------------------------------------------------------


def test_slice_then_field_is_projection_dropping_nulls():
    collected = require_oneshot_equals("foo[:2]", _SLICE_PROJECTION_DOC, [{"a": 1}, {"a": 2}])
    assert collected == [{"a": 1}, {"a": 2}]
    projected = require_oneshot_equals("foo[:2].a", _SLICE_PROJECTION_DOC, [1, 2])
    assert projected == [1, 2]
    empty = require_successful_empty_array(oneshot_bracket_search("foo[:2].b", _SLICE_PROJECTION_DOC))
    assert empty == []
    assert empty != [None, None]
    assert empty is not None


def test_reversed_slice_then_nested_field():
    value = require_oneshot_equals("bar[::-1].a.b", _REVERSED_NESTED_DOC, [3, 2, 1])
    assert value == [3, 2, 1]
    assert value != [1, 2, 3]
    assert value != _REVERSED_NESTED_DOC


def test_slice_on_non_array_is_successful_null():
    live = require_oneshot_equals("foo[1:9]", _SLICE_DOC, [1, 2, 3, 4, 5, 6, 7, 8])
    assert live == [1, 2, 3, 4, 5, 6, 7, 8]
    assert live != []
    object_doc = {"bar": {"baz": 1}}
    require_bracket_null(oneshot_bracket_search("bar[0:10]", object_doc))
    observed = require_bracket_value(oneshot_bracket_search("bar[0:10]", object_doc))
    assert observed is None
    assert observed != {"baz": 1}
    assert observed != []
    number_doc = {"baz": 50}
    require_bracket_null(oneshot_bracket_search("baz[:2].a", number_doc))
    numbered = require_bracket_value(oneshot_bracket_search("baz[:2].a", number_doc))
    assert numbered is None
    assert numbered != []
    assert numbered != list("50")
    print(
        f"slice_non_array live={live!r} object={observed!r} number={numbered!r}",
        flush=True,
    )


def test_slice_as_whole_expression_on_array_document():
    document = [{"a": 1}, {"a": 2}, {"a": 3}]
    value = require_oneshot_equals("[:2].a", document, [1, 2])
    assert value == [1, 2]
    assert value != document


def test_runtime_slice_projection_and_non_array_null():
    root = bracket_ident()
    field = bracket_ident()
    missing = bracket_ident()
    p1 = bracket_payload()
    p2 = bracket_payload()
    assert field not in {"a", "b"}
    assert missing != field
    mappings = [{field: p1}, {field: p2}, {bracket_ident(): bracket_payload()}]
    document = {root: mappings}
    projected = require_oneshot_equals(f"{root}[:2].{field}", document, [p1, p2])
    assert projected == [p1, p2]
    empty = require_successful_empty_array(
        oneshot_bracket_search(f"{root}[:2].{missing}", document)
    )
    assert empty == []

    n = _runtime_length(3, 6)
    items = [{field: bracket_payload()} for _ in range(n)]
    take = 1
    if n > 2:
        choices = [i for i in range(1, n) if i != 2]
        take = choices[int(uuid.uuid4().hex[:4], 16) % len(choices)]
    assert not (take == 2 and field == "a")
    whole_doc = items
    expected = [row[field] for row in items[:take]]
    whole = require_oneshot_equals(f"[:{take}].{field}", whole_doc, expected)
    print(f"runtime_whole_slice n={take} value={whole!r}", flush=True)
    assert whole != [1, 2]

    start, stop, step = 1, None, 2
    slice_expr = f"{root}{slice_text(start, stop, step)}"
    array_items = _payloads(_runtime_length(5, 8))
    live = require_oneshot_equals(
        slice_expr, {root: array_items}, host_slice(array_items, start, stop, step)
    )
    assert live != []
    require_bracket_null(oneshot_bracket_search(slice_expr, {root: {bracket_ident(): 1}}))
    require_bracket_null(oneshot_bracket_search(slice_expr, {root: 50}))
    text = bracket_payload()
    require_bracket_null(oneshot_bracket_search(slice_expr, {root: text}))
    as_chars = require_bracket_value(oneshot_bracket_search(slice_expr, {root: text}))
    assert as_chars is None
    assert as_chars != list(text)


def test_compile_then_search_slice_projection():
    public = compile_once_then_search("foo[:2].a", _SLICE_PROJECTION_DOC)
    assert public == [1, 2]
    root = bracket_ident()
    field = bracket_ident()
    p1 = bracket_payload()
    p2 = bracket_payload()
    document = {root: [{field: p1}, {field: p2}, {bracket_ident(): bracket_payload()}]}
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[:2].{field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_slice_proj first={first!r} second={second!r}", flush=True)
    assert first == second == [p1, p2]
    assert first != [1, 2]


# ---------------------------------------------------------------------------
# E. Flatten splices one level; a non-array current value is null
# ---------------------------------------------------------------------------


def test_flatten_splices_one_level_on_triple_nested():
    value = require_oneshot_equals("foo[]", _TRIPLE_NESTED_DOC, _SIX_INNER)
    assert value == _SIX_INNER
    assert value != _SIX_FIRST
    assert len(value) == 6


def test_flatten_then_index_zero_is_six_first_elements():
    value = require_oneshot_equals("foo[][0]", _TRIPLE_NESTED_DOC, _SIX_FIRST)
    assert value == _SIX_FIRST
    assert value != _SIX_INNER
    assert value != _TRIPLE_NESTED_DOC
    assert len(value) == 6


def test_flatten_on_object_is_successful_null():
    live = require_oneshot_equals("foo[]", _TRIPLE_NESTED_DOC, _SIX_INNER)
    assert live == _SIX_INNER
    assert live != []
    document = {"type": "object"}
    require_bracket_null(oneshot_bracket_search("[]", document))
    observed = require_bracket_value(oneshot_bracket_search("[]", document))
    assert observed is None
    assert observed != document
    assert observed != []
    print(f"flatten_on_object live={live!r} null={observed!r}", flush=True)


def test_flatten_on_string_is_successful_null():
    text = bracket_payload()
    require_bracket_null(oneshot_bracket_search("[]", text))
    observed = require_bracket_value(oneshot_bracket_search("[]", text))
    assert observed is None
    assert observed != list(text)
    p1 = bracket_payload()
    p2 = bracket_payload()
    p3 = bracket_payload()
    live = require_oneshot_equals("[]", [[p1, p2], [p3]], [p1, p2, p3])
    assert live == [p1, p2, p3]


def test_runtime_flatten_keeps_non_array_and_is_one_level():
    root = bracket_ident()
    p1, p2, scalar, p3 = _payloads(4)
    document = {root: [[p1, p2], scalar, [p3]]}
    spliced = require_oneshot_equals(f"{root}[]", document, [p1, p2, scalar, p3])
    assert spliced == [p1, p2, scalar, p3]
    assert scalar in spliced
    inner = bracket_payload()
    one_level = require_oneshot_equals("[]", [[[inner]]], [[inner]])
    print(f"one_level_flatten={one_level!r} inner={inner!r}", flush=True)
    assert one_level == [[inner]]
    assert one_level != [inner]


def test_flatten_as_whole_expression_on_array_document():
    p1, p2, p3 = _payloads(3)
    document = [[p1], [p2, p3]]
    value = require_oneshot_equals("[]", document, [p1, p2, p3])
    assert value == [p1, p2, p3]
    assert value != document


def test_compile_then_search_public_flatten():
    value = compile_once_then_search("foo[]", _TRIPLE_NESTED_DOC)
    assert value == _SIX_INNER
    assert value != _SIX_FIRST


def test_compile_then_search_runtime_flatten():
    root = bracket_ident()
    p1, p2, scalar, p3 = _payloads(4)
    document = {root: [[p1, p2], scalar, [p3]]}
    expected = [p1, p2, scalar, p3]
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[]"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_flatten first={first!r} second={second!r}", flush=True)
    assert first == second == expected
    assert first != _SIX_INNER


# ---------------------------------------------------------------------------
# F. Flatten is a projection
# ---------------------------------------------------------------------------


def test_flatten_then_field_is_projection_dropping_nulls():
    value = require_oneshot_equals("foo[].bar", _FLATTEN_PROJECTION_DOC, ["one"])
    assert value == ["one"]
    assert value != ["one", None]
    assert value is not None


def test_flatten_then_index_on_string_drops_nulls_to_empty_array():
    six = require_oneshot_equals("foo[][0]", _TRIPLE_NESTED_DOC, _SIX_FIRST)
    assert six == _SIX_FIRST
    empty = require_successful_empty_array(
        oneshot_bracket_search("foo[][0][0]", _TRIPLE_NESTED_DOC)
    )
    print(f"flatten_then_index_string={empty!r} six={six!r}", flush=True)
    assert empty == []
    assert empty != "one"
    assert empty != ["one"]


def test_runtime_flatten_projection():
    root = bracket_ident()
    field = bracket_ident()
    payload = bracket_payload()
    other = bracket_payload()
    assert field != "bar"
    mappings = [{field: payload}, {bracket_ident(): other}]
    projected = require_oneshot_equals(f"{root}[].{field}", {root: mappings}, [payload])
    assert projected == [payload]
    assert projected != [payload, None]
    s1 = bracket_payload()
    s2 = bracket_payload()
    string_arrays = {root: [[s1], [s2]]}
    spliced = require_oneshot_equals(f"{root}[]", string_arrays, [s1, s2])
    assert spliced == [s1, s2]
    empty = require_successful_empty_array(
        oneshot_bracket_search(f"{root}[][0][0]", string_arrays)
    )
    print(f"runtime_flatten_idx empty={empty!r} spliced={spliced!r}", flush=True)
    assert empty == []
    assert empty is not None
    # Collect-then-index of [][0][0] would take s1 then index the string → null.


def test_compile_then_search_flatten_projection():
    public = compile_once_then_search("foo[].bar", _FLATTEN_PROJECTION_DOC)
    assert public == ["one"]
    root = bracket_ident()
    field = bracket_ident()
    payload = bracket_payload()
    document = {root: [{field: payload}, {bracket_ident(): bracket_payload()}]}
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[].{field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_flatten_proj first={first!r} second={second!r}", flush=True)
    assert first == second == [payload]
    assert first != ["one"]


# ---------------------------------------------------------------------------
# G. Step 0 does not succeed and is not syntax and not []
# ---------------------------------------------------------------------------


def test_zero_step_slice_is_value_error_not_empty_array_or_syntax():
    empty = require_successful_empty_array(oneshot_bracket_search("foo[10:-20]", _SLICE_DOC))
    assert empty == []
    baited = dict(_SLICE_DOC)
    baited.update(bracket_sentinel_document())
    step0 = require_step_zero_search_failure(_STEP0_PUBLIC, baited)
    four = assert_bracket_search_is_value_error(_FOUR_PUBLIC, baited)
    syntax = assert_bracket_search_is_value_error("foo.", baited)
    print(
        f"public_step0_kind={bracket_kind_marker(step0).__name__} "
        f"public_four_kind={bracket_kind_marker(four).__name__} "
        f"foo_syntax_kind={bracket_kind_marker(syntax).__name__}",
        flush=True,
    )
    assert_step_zero_kind_unlike_syntax(step0, four, syntax)


def test_runtime_zero_step_slice_is_value_error_not_syntax():
    root = bracket_ident()
    s = _runtime_int(0, 12, forbidden=frozenset({8}))
    t = _runtime_int(0, 12, forbidden=frozenset({2}))
    assert s != 8 and t != 2
    step_expr = f"{root}[{s}:{t}:0]"
    four_expr = f"{root}[{s}:{t}:0:1]"
    document = {root: _TEN}
    empty = require_successful_empty_array(
        oneshot_bracket_search(f"{root}[10:-20]", document)
    )
    assert empty == []
    step0 = require_step_zero_search_failure(step_expr, document)
    four = assert_bracket_search_is_value_error(four_expr, document)
    syntax = assert_bracket_search_is_value_error("foo.", document)
    pub_step = require_step_zero_search_failure(_STEP0_PUBLIC, _SLICE_DOC)
    pub_four = assert_bracket_search_is_value_error(_FOUR_PUBLIC, _SLICE_DOC)
    print(
        f"cross_step pub={bracket_kind_marker(pub_step).__name__} "
        f"rt={bracket_kind_marker(step0).__name__} "
        f"pub_four={bracket_kind_marker(pub_four).__name__} "
        f"rt_four={bracket_kind_marker(four).__name__} "
        f"foo_syntax={bracket_kind_marker(syntax).__name__}",
        flush=True,
    )
    assert_bracket_kind_markers_match(pub_step, step0)
    assert_bracket_kind_markers_match(pub_four, four)
    assert_step_zero_kind_unlike_syntax(step0, four, syntax)
    assert_step_zero_kind_unlike_syntax(pub_step, pub_four, syntax)


def test_compile_then_search_zero_step_is_value_error_not_empty():
    oneshot = require_step_zero_search_failure(_STEP0_PUBLIC, _SLICE_DOC)
    four = assert_bracket_search_is_value_error(_FOUR_PUBLIC, _SLICE_DOC)
    syntax = assert_bracket_search_is_value_error("foo.", _SLICE_DOC)
    compiled = compile_bracket_expression(_STEP0_PUBLIC)
    print(f"compile_step0_shape exception={compiled.exception!r}", flush=True)
    compiled_exc = require_compile_then_search_step_zero_kind(
        _STEP0_PUBLIC,
        _SLICE_DOC,
        canonical_step0=oneshot,
        four_part=four,
        foo_syntax=syntax,
    )
    print(
        f"compile_then_search_step0_kind={bracket_kind_marker(compiled_exc).__name__}",
        flush=True,
    )
    root = bracket_ident()
    s = _runtime_int(0, 12, forbidden=frozenset({8}))
    t = _runtime_int(0, 12, forbidden=frozenset({2}))
    rt_expr = f"{root}[{s}:{t}:0]"
    rt_doc = {root: _TEN}
    rt_oneshot = require_step_zero_search_failure(rt_expr, rt_doc)
    assert_bracket_kind_markers_match(oneshot, rt_oneshot)
    rt_compiled = compile_bracket_expression(rt_expr)
    print(f"compile_rt_step0_shape exception={rt_compiled.exception!r}", flush=True)
    rt_compiled_exc = require_compile_then_search_step_zero_kind(
        rt_expr,
        rt_doc,
        canonical_step0=oneshot,
        four_part=four,
        foo_syntax=syntax,
    )
    print(
        f"compile_then_search_rt_step0_kind={bracket_kind_marker(rt_compiled_exc).__name__}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# H. Four-part slice is syntax; identifier and ampersand slices fail
# ---------------------------------------------------------------------------


def test_four_part_slice_is_syntax_value_error():
    document = bracket_sentinel_document()
    assert_search_shares_foo_syntax_kind(_FOUR_PUBLIC, document)
    assert_search_shares_foo_syntax_kind(_FOUR_PUBLIC, _SLICE_DOC)


def test_runtime_four_part_slice_is_syntax_value_error():
    root = bracket_ident()
    a = _runtime_int(1, 9)
    b = _runtime_int(1, 9)
    c = _runtime_int(1, 9)
    d = _runtime_int(1, 9)
    expression = f"{root}[{a}:{b}:{c}:{d}]"
    document = {root: _TEN}
    assert_search_shares_foo_syntax_kind(expression, document)
    assert_search_shares_foo_syntax_kind(expression, bracket_sentinel_document())


def test_identifier_in_slice_does_not_succeed():
    planted = 9
    bait = host_slice(_TEN, 2, planted, 3)
    assert bait != []
    document = {"foo": list(_TEN), "a": planted}
    observed = assert_bracket_search_is_value_error("foo[2:a:3]", document)
    result = oneshot_bracket_search("foo[2:a:3]", document)
    print(f"ident_in_slice bait={bait!r} exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document
    assert result.value != bait
    assert result.value is not None or result.exception is not None

    root = bracket_ident()
    ident = bracket_ident()
    assert ident != "a"
    items = _payloads(7)
    bound = 6
    runtime_bait = host_slice(items, 2, bound, 3)
    assert runtime_bait != []
    runtime_doc = {root: items, ident: bound}
    expression = f"{root}[2:{ident}:3]"
    runtime_exc = assert_bracket_search_is_value_error(expression, runtime_doc)
    runtime_result = oneshot_bracket_search(expression, runtime_doc)
    print(f"bracket_ident_slice bait={runtime_bait!r} exc={runtime_exc!r}", flush=True)
    assert runtime_result.exception is not None
    assert runtime_result.value != runtime_bait
    assert runtime_result.value is not runtime_doc


def test_ampersand_in_slice_does_not_succeed():
    document = bracket_sentinel_document()
    observed = assert_bracket_search_is_value_error("foo[8:2&]", document)
    result = oneshot_bracket_search("foo[8:2&]", document)
    print(f"ampersand_slice exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document

    root = bracket_ident()
    p = _runtime_int(0, 15, forbidden=frozenset({8}))
    q = _runtime_int(0, 15, forbidden=frozenset({2}))
    assert p != 8 and q != 2
    expression = f"{root}[{p}:{q}&]"
    runtime_doc = {root: _TEN}
    runtime_exc = assert_bracket_search_is_value_error(expression, runtime_doc)
    runtime_result = oneshot_bracket_search(expression, runtime_doc)
    print(f"runtime_ampersand {expression} exc={runtime_exc!r}", flush=True)
    assert runtime_result.exception is not None
    assert runtime_result.value is not runtime_doc
    assert runtime_result.value != []


def test_compile_refuses_four_part_and_malformed_slices():
    assert_compile_shares_foo_syntax_kind(_FOUR_PUBLIC)
    root = bracket_ident()
    a = _runtime_int(1, 9)
    b = _runtime_int(1, 9)
    c = _runtime_int(1, 9)
    d = _runtime_int(1, 9)
    assert_compile_shares_foo_syntax_kind(f"{root}[{a}:{b}:{c}:{d}]")
    assert_bracket_compile_is_value_error("foo[2:a:3]")
    ident = bracket_ident()
    assert_bracket_compile_is_value_error(f"{root}[2:{ident}:3]")
    assert_bracket_compile_is_value_error("foo[8:2&]")
    p = _runtime_int(0, 15, forbidden=frozenset({8}))
    q = _runtime_int(0, 15, forbidden=frozenset({2}))
    assert_bracket_compile_is_value_error(f"{root}[{p}:{q}&]")
