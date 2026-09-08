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

from F01_helpers import (
    assert_compile_is_value_error,
    assert_kind_stems_match,
    assert_search_is_value_error,
    compile_expression,
    failure_record,
    leftover_kind_stem,
    oneshot_search,
    require_search_value,
    require_successful_null,
    runtime_ident,
    runtime_payload,
    search_parsed,
    sentinel_document,
)
from F02_helpers import (
    assert_compile_syntax_not_empty_or_incomplete,
    assert_search_syntax_not_empty_or_incomplete,
    compile_once_then_search,
)
from F03_helpers import (
    assert_kind_stems_differ,
    from_end_index,
    host_slice,
    in_range_index,
    require_oneshot_equals,
    require_step_zero_compile_path_failure,
    require_step_zero_search_failure,
    require_successful_empty_array,
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
_STEP0_FOUR_TEXTS = (_FOUR_PUBLIC, _STEP0_PUBLIC)


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
    items = [runtime_payload() for _ in range(n)]
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
    root = runtime_ident()
    document = {root: items, "bait": runtime_payload()}
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
    root = runtime_ident()
    document = {root: items}
    i = in_range_index(n)
    pos = compile_once_then_search(f"{root}[{i}]", document)
    assert pos == items[i]
    assert pos not in _PUBLIC_INDEX_PAYLOADS
    k = from_end_index(n)
    parsed = require_search_value(compile_expression(f"{root}[-{k}]"))
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
    print(f"compile_runtime_neg k={k} first={first!r} second={second!r}", flush=True)
    assert first == second == items[n - k]
    assert first != items[-1]


# ---------------------------------------------------------------------------
# B. Out-of-range and non-array index are successful null; a field is not
# ---------------------------------------------------------------------------


def test_out_of_range_index_is_successful_null():
    require_oneshot_equals("foo.bar[0]", _INDEX_DOC, "zero")
    require_oneshot_equals("foo.bar[-1]", _INDEX_DOC, "two")
    require_successful_null(oneshot_search("foo.bar[3]", _INDEX_DOC))
    require_successful_null(oneshot_search("foo.bar[-4]", _INDEX_DOC))
    high = require_search_value(oneshot_search("foo.bar[3]", _INDEX_DOC))
    low = require_search_value(oneshot_search("foo.bar[-4]", _INDEX_DOC))
    assert high is None
    assert low is None
    assert high != "zero"
    assert low != "two"


def test_index_on_object_is_successful_null():
    document = {"foo": {"bar": 1}}
    mapping = require_oneshot_equals("foo", document, {"bar": 1})
    assert mapping == {"bar": 1}
    require_oneshot_equals("foo.bar", document, 1)
    require_successful_null(oneshot_search("foo[0]", document))
    observed = require_search_value(oneshot_search("foo[0]", document))
    assert observed is None
    assert observed != document["foo"]


def test_index_on_string_is_successful_null():
    baseline = require_oneshot_equals("foo.bar[0][0]", _STRING_INDEX_DOC, "one")
    assert baseline == "one"
    require_successful_null(oneshot_search("foo.bar[0][0][0]", _STRING_INDEX_DOC))
    observed = require_search_value(oneshot_search("foo.bar[0][0][0]", _STRING_INDEX_DOC))
    assert observed is None
    assert observed != "o"
    assert observed != "one"


def test_index_then_field_unlike_field_on_array():
    require_oneshot_equals("foo[0].bar", _FIELD_AFTER_INDEX_DOC, "one")
    require_oneshot_equals("foo[3].notbar", _FIELD_AFTER_INDEX_DOC, "four")
    require_successful_null(oneshot_search("foo[3].bar", _FIELD_AFTER_INDEX_DOC))
    require_successful_null(oneshot_search("foo.bar", _FIELD_AFTER_INDEX_DOC))
    projected = require_search_value(oneshot_search("foo.bar", _FIELD_AFTER_INDEX_DOC))
    print(f"field_on_array={projected!r}", flush=True)
    assert projected is None
    assert projected != ["one", "two", "three"]


def test_runtime_out_of_range_and_non_array_index_are_successful_null():
    n = _runtime_length(4, 8, forbidden=3)
    items = _payloads(n)
    root = runtime_ident()
    array_doc = {root: items}
    last = require_oneshot_equals(f"{root}[{n - 1}]", array_doc, items[-1])
    assert last == require_oneshot_equals(f"{root}[-1]", array_doc, items[-1])
    require_successful_null(oneshot_search(f"{root}[{n}]", array_doc))
    require_successful_null(oneshot_search(f"{root}[-{n + 1}]", array_doc))

    payload = runtime_payload()
    string_doc = {root: payload}
    require_successful_null(oneshot_search(f"{root}[0]", string_doc))
    mapping = {runtime_ident(): runtime_payload()}
    mapping_doc = {root: mapping}
    require_successful_null(oneshot_search(f"{root}[0]", mapping_doc))
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
    empty = require_successful_empty_array(oneshot_search("foo[10:-20]", _SLICE_DOC))
    assert empty == []
    assert empty is not None
    result = oneshot_search("foo[10:-20]", _SLICE_DOC)
    assert result.exception is None


def test_runtime_slice_follows_host_slice_rules():
    n = _runtime_length(5, 8)
    items = _payloads(n)
    root = runtime_ident()
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
    root = runtime_ident()
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
    empty = require_successful_empty_array(oneshot_search("foo[:2].b", _SLICE_PROJECTION_DOC))
    assert empty == []
    assert empty != [None, None]
    assert empty is not None


def test_reversed_slice_then_nested_field():
    value = require_oneshot_equals("bar[::-1].a.b", _REVERSED_NESTED_DOC, [3, 2, 1])
    assert value == [3, 2, 1]
    assert value != [1, 2, 3]
    assert value != _REVERSED_NESTED_DOC


def test_slice_on_non_array_is_successful_null():
    object_doc = {"bar": {"baz": 1}}
    require_successful_null(oneshot_search("bar[0:10]", object_doc))
    observed = require_search_value(oneshot_search("bar[0:10]", object_doc))
    assert observed is None
    assert observed != {"baz": 1}
    assert observed != []
    number_doc = {"baz": 50}
    require_successful_null(oneshot_search("baz[:2].a", number_doc))
    numbered = require_search_value(oneshot_search("baz[:2].a", number_doc))
    assert numbered is None


def test_slice_as_whole_expression_on_array_document():
    document = [{"a": 1}, {"a": 2}, {"a": 3}]
    value = require_oneshot_equals("[:2].a", document, [1, 2])
    assert value == [1, 2]
    assert value != document


def test_runtime_slice_projection_and_non_array_null():
    root = runtime_ident()
    field = runtime_ident()
    missing = runtime_ident()
    p1 = runtime_payload()
    p2 = runtime_payload()
    assert field not in {"a", "b"}
    assert missing != field
    mappings = [{field: p1}, {field: p2}, {runtime_ident(): runtime_payload()}]
    document = {root: mappings}
    projected = require_oneshot_equals(f"{root}[:2].{field}", document, [p1, p2])
    assert projected == [p1, p2]
    empty = require_successful_empty_array(
        oneshot_search(f"{root}[:2].{missing}", document)
    )
    assert empty == []

    n = _runtime_length(3, 6)
    items = [{field: runtime_payload()} for _ in range(n)]
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
    require_successful_null(oneshot_search(slice_expr, {root: {runtime_ident(): 1}}))
    require_successful_null(oneshot_search(slice_expr, {root: 50}))
    text = runtime_payload()
    require_successful_null(oneshot_search(slice_expr, {root: text}))
    as_chars = require_search_value(oneshot_search(slice_expr, {root: text}))
    assert as_chars is None
    assert as_chars != list(text)


def test_compile_then_search_slice_projection():
    public = compile_once_then_search("foo[:2].a", _SLICE_PROJECTION_DOC)
    assert public == [1, 2]
    root = runtime_ident()
    field = runtime_ident()
    p1 = runtime_payload()
    p2 = runtime_payload()
    document = {root: [{field: p1}, {field: p2}, {runtime_ident(): runtime_payload()}]}
    parsed = require_search_value(compile_expression(f"{root}[:2].{field}"))
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
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
    document = {"type": "object"}
    require_successful_null(oneshot_search("[]", document))
    observed = require_search_value(oneshot_search("[]", document))
    assert observed is None
    assert observed != document
    assert observed != []


def test_flatten_on_string_is_successful_null():
    text = runtime_payload()
    require_successful_null(oneshot_search("[]", text))
    observed = require_search_value(oneshot_search("[]", text))
    assert observed is None
    assert observed != list(text)
    p1 = runtime_payload()
    p2 = runtime_payload()
    p3 = runtime_payload()
    live = require_oneshot_equals("[]", [[p1, p2], [p3]], [p1, p2, p3])
    assert live == [p1, p2, p3]


def test_runtime_flatten_keeps_non_array_and_is_one_level():
    root = runtime_ident()
    p1, p2, scalar, p3 = _payloads(4)
    document = {root: [[p1, p2], scalar, [p3]]}
    spliced = require_oneshot_equals(f"{root}[]", document, [p1, p2, scalar, p3])
    assert spliced == [p1, p2, scalar, p3]
    assert scalar in spliced
    inner = runtime_payload()
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
    root = runtime_ident()
    p1, p2, scalar, p3 = _payloads(4)
    document = {root: [[p1, p2], scalar, [p3]]}
    expected = [p1, p2, scalar, p3]
    parsed = require_search_value(compile_expression(f"{root}[]"))
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
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
        oneshot_search("foo[][0][0]", _TRIPLE_NESTED_DOC)
    )
    print(f"flatten_then_index_string={empty!r} six={six!r}", flush=True)
    assert empty == []
    assert empty != "one"
    assert empty != ["one"]


def test_runtime_flatten_projection():
    root = runtime_ident()
    field = runtime_ident()
    payload = runtime_payload()
    other = runtime_payload()
    assert field != "bar"
    mappings = [{field: payload}, {runtime_ident(): other}]
    projected = require_oneshot_equals(f"{root}[].{field}", {root: mappings}, [payload])
    assert projected == [payload]
    assert projected != [payload, None]
    s1 = runtime_payload()
    s2 = runtime_payload()
    string_arrays = {root: [[s1], [s2]]}
    spliced = require_oneshot_equals(f"{root}[]", string_arrays, [s1, s2])
    assert spliced == [s1, s2]
    empty = require_successful_empty_array(
        oneshot_search(f"{root}[][0][0]", string_arrays)
    )
    print(f"runtime_flatten_idx empty={empty!r} spliced={spliced!r}", flush=True)
    assert empty == []
    assert empty is not None
    # Collect-then-index of [][0][0] would take s1 then index the string → null.


def test_compile_then_search_flatten_projection():
    public = compile_once_then_search("foo[].bar", _FLATTEN_PROJECTION_DOC)
    assert public == ["one"]
    root = runtime_ident()
    field = runtime_ident()
    payload = runtime_payload()
    document = {root: [{field: payload}, {runtime_ident(): runtime_payload()}]}
    parsed = require_search_value(compile_expression(f"{root}[].{field}"))
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
    print(f"compile_flatten_proj first={first!r} second={second!r}", flush=True)
    assert first == second == [payload]
    assert first != ["one"]


# ---------------------------------------------------------------------------
# G. Step 0 does not succeed and is not syntax and not []
# ---------------------------------------------------------------------------


def test_zero_step_slice_is_value_error_not_empty_array_or_syntax():
    empty = require_successful_empty_array(oneshot_search("foo[10:-20]", _SLICE_DOC))
    assert empty == []
    baited = dict(_SLICE_DOC)
    baited.update(sentinel_document())
    step0 = require_step_zero_search_failure(_STEP0_PUBLIC, baited)
    four = assert_search_is_value_error(_FOUR_PUBLIC, baited)
    assert_kind_stems_differ(step0, four, *_STEP0_FOUR_TEXTS)
    step_stem = leftover_kind_stem(failure_record(step0), *_STEP0_FOUR_TEXTS)
    four_stem = leftover_kind_stem(failure_record(four), *_STEP0_FOUR_TEXTS)
    print(f"public_step0_stem={step_stem!r} public_four_stem={four_stem!r}", flush=True)
    assert step_stem != four_stem


def test_runtime_zero_step_slice_is_value_error_not_syntax():
    from F01_helpers import failure_record

    root = runtime_ident()
    s = _runtime_int(0, 12, forbidden=frozenset({8}))
    t = _runtime_int(0, 12, forbidden=frozenset({2}))
    assert s != 8 and t != 2
    step_expr = f"{root}[{s}:{t}:0]"
    four_expr = f"{root}[{s}:{t}:0:1]"
    document = {root: _TEN}
    empty = require_successful_empty_array(
        oneshot_search(f"{root}[10:-20]", document)
    )
    assert empty == []
    step0 = require_step_zero_search_failure(step_expr, document)
    four = assert_search_is_value_error(four_expr, document)
    texts = (four_expr, step_expr)
    assert_kind_stems_differ(step0, four, *texts)

    pub_step = require_step_zero_search_failure(_STEP0_PUBLIC, _SLICE_DOC)
    pub_four = assert_search_is_value_error(_FOUR_PUBLIC, _SLICE_DOC)
    pub_step_stem = leftover_kind_stem(failure_record(pub_step), *_STEP0_FOUR_TEXTS)
    rt_step_stem = leftover_kind_stem(failure_record(step0), *texts)
    pub_four_stem = leftover_kind_stem(failure_record(pub_four), *_STEP0_FOUR_TEXTS)
    rt_four_stem = leftover_kind_stem(failure_record(four), *texts)
    print(
        f"cross_step pub={pub_step_stem!r} rt={rt_step_stem!r} "
        f"pub_four={pub_four_stem!r} rt_four={rt_four_stem!r}",
        flush=True,
    )
    assert pub_step_stem == rt_step_stem, (
        "step-0 kind stem is not stable across the public and runtime pair: "
        f"{pub_step_stem!r} vs {rt_step_stem!r}"
    )
    assert pub_four_stem == rt_four_stem, (
        "four-part kind stem is not stable across the public and runtime pair: "
        f"{pub_four_stem!r} vs {rt_four_stem!r}"
    )
    assert pub_step_stem != pub_four_stem
    assert_kind_stems_match(pub_step, step0, *_STEP0_FOUR_TEXTS, *texts)


def test_compile_then_search_zero_step_is_value_error_not_empty():
    require_step_zero_compile_path_failure(_STEP0_PUBLIC, _SLICE_DOC)
    root = runtime_ident()
    s = _runtime_int(0, 12, forbidden=frozenset({8}))
    t = _runtime_int(0, 12, forbidden=frozenset({2}))
    require_step_zero_compile_path_failure(f"{root}[{s}:{t}:0]", {root: _TEN})


# ---------------------------------------------------------------------------
# H. Four-part slice is syntax; identifier and ampersand slices fail
# ---------------------------------------------------------------------------


def test_four_part_slice_is_syntax_value_error():
    document = sentinel_document()
    assert_search_syntax_not_empty_or_incomplete(_FOUR_PUBLIC, document)
    assert_search_syntax_not_empty_or_incomplete(_FOUR_PUBLIC, _SLICE_DOC)


def test_runtime_four_part_slice_is_syntax_value_error():
    root = runtime_ident()
    a = _runtime_int(1, 9)
    b = _runtime_int(1, 9)
    c = _runtime_int(1, 9)
    d = _runtime_int(1, 9)
    expression = f"{root}[{a}:{b}:{c}:{d}]"
    document = {root: _TEN}
    assert_search_syntax_not_empty_or_incomplete(expression, document)
    assert_search_syntax_not_empty_or_incomplete(expression, sentinel_document())


def test_identifier_in_slice_does_not_succeed():
    planted = 9
    bait = host_slice(_TEN, 2, planted, 3)
    assert bait != []
    document = {"foo": list(_TEN), "a": planted}
    observed = assert_search_is_value_error("foo[2:a:3]", document)
    result = oneshot_search("foo[2:a:3]", document)
    print(f"ident_in_slice bait={bait!r} exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document
    assert result.value != bait
    assert result.value is not None or result.exception is not None

    root = runtime_ident()
    ident = runtime_ident()
    assert ident != "a"
    items = _payloads(7)
    bound = 6
    runtime_bait = host_slice(items, 2, bound, 3)
    assert runtime_bait != []
    runtime_doc = {root: items, ident: bound}
    expression = f"{root}[2:{ident}:3]"
    runtime_exc = assert_search_is_value_error(expression, runtime_doc)
    runtime_result = oneshot_search(expression, runtime_doc)
    print(f"runtime_ident_slice bait={runtime_bait!r} exc={runtime_exc!r}", flush=True)
    assert runtime_result.exception is not None
    assert runtime_result.value != runtime_bait
    assert runtime_result.value is not runtime_doc


def test_ampersand_in_slice_does_not_succeed():
    document = sentinel_document()
    observed = assert_search_is_value_error("foo[8:2&]", document)
    result = oneshot_search("foo[8:2&]", document)
    print(f"ampersand_slice exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document

    root = runtime_ident()
    p = _runtime_int(0, 15, forbidden=frozenset({8}))
    q = _runtime_int(0, 15, forbidden=frozenset({2}))
    assert p != 8 and q != 2
    expression = f"{root}[{p}:{q}&]"
    runtime_doc = {root: _TEN}
    runtime_exc = assert_search_is_value_error(expression, runtime_doc)
    runtime_result = oneshot_search(expression, runtime_doc)
    print(f"runtime_ampersand {expression} exc={runtime_exc!r}", flush=True)
    assert runtime_result.exception is not None
    assert runtime_result.value is not runtime_doc
    assert runtime_result.value != []


def test_compile_refuses_four_part_and_malformed_slices():
    assert_compile_syntax_not_empty_or_incomplete(_FOUR_PUBLIC)
    root = runtime_ident()
    a = _runtime_int(1, 9)
    b = _runtime_int(1, 9)
    c = _runtime_int(1, 9)
    d = _runtime_int(1, 9)
    assert_compile_syntax_not_empty_or_incomplete(f"{root}[{a}:{b}:{c}:{d}]")
    assert_compile_is_value_error("foo[2:a:3]")
    ident = runtime_ident()
    assert_compile_is_value_error(f"{root}[2:{ident}:3]")
    assert_compile_is_value_error("foo[8:2&]")
    p = _runtime_int(0, 15, forbidden=frozenset({8}))
    q = _runtime_int(0, 15, forbidden=frozenset({2}))
    assert_compile_is_value_error(f"{root}[{p}:{q}&]")
