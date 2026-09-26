# feature: F04
"""FP-04: list/object wildcards and filter projections.

Assertions follow Full_PRD.original.md FP-04 (L184–L222) together with
null-is-host-none (L23), boolean-is-not-1-or-0 (L28), truthiness and
dropped projected nulls (L30–L32), value-error failure (L63), and the
syntax list at L107 (which names ``foo[*]bar`` and does not name ``.*``).
Flatten and slices are FP-03. Comparators inside a filter are the
operators of FP-06; this feature pins the collection rule. Evaluation
options are not supplied.
"""

from __future__ import annotations

import uuid

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F02_helpers import (
    compile_once_then_search,
)
from F03_helpers import (
    assert_bracket_search_is_value_error,
    bracket_ident,
    bracket_payload,
    bracket_sentinel_document,
    compile_bracket_expression,
    in_range_index,
    oneshot_bracket_search,
    require_bracket_null,
    require_bracket_value,
    require_oneshot_equals,
    require_successful_empty_array,
    search_compiled_bracket,
)
from F04_helpers import (
    assert_compile_is_syntax_kind_not_empty_or_incomplete,
    assert_search_is_syntax_kind_not_empty_or_incomplete,
    json_literal_text,
    require_array_multiset,
    require_one_combined_value,
    require_unsuccessful_compile_path,
)

_PUBLIC_IDENTS = frozenset(
    {
        "foo",
        "bar",
        "baz",
        "one",
        "two",
        "three",
        "four",
        "val",
        "age",
        "name",
        "key",
        "first",
        "last",
        "kind",
        "notbar",
        "notbaz",
        "string",
        "top",
        "other",
        "nomatch",
    }
)
_PUBLIC_PAYLOADS = frozenset(
    {
        "one",
        "two",
        "three",
        "four",
        "val",
        "foo",
        "bar",
        "baz",
        "a",
        "b",
        "c",
        "string",
        "basic",
        "intermediate",
        "advanced",
        "expert",
    }
)
_PUBLIC_NUMBERS = frozenset({20, 25, 30})

_LIST_WILDCARD_ARRAY = [
    {"bar": "one"},
    {"bar": "two"},
    {"bar": "three"},
    {"notbar": "four"},
]
_LIST_WILDCARD_DOC = {"foo": list(_LIST_WILDCARD_ARRAY)}
_NESTED_KIND_DOC = {
    "foo": [
        {"bar": [{"kind": "basic"}, {"kind": "intermediate"}]},
        {"bar": [{"kind": "advanced"}, {"kind": "expert"}]},
        {"bar": "string"},
    ]
}
_NESTED_KIND_RESULT = [["basic", "intermediate"], ["advanced", "expert"]]
_INDEX_AFTER_DOC = {"foo": [["one", "two"], ["three", "four"], ["five"]]}
_OBJECT_WILDCARD_DOC = {
    "foo": {
        "bar": {"baz": "val"},
        "other": {"baz": "val"},
        "other2": {"baz": "val"},
        "other3": {"notbaz": ["a", "b", "c"]},
        "other4": {"notbaz": ["a", "b", "c"]},
    }
}
_STAR_BAR_DOC = {
    "foo": {"bar": "one"},
    "other": {"bar": "one"},
    "nomatch": {"notbar": "three"},
}
_TOP_DOC = {
    "top1": {"sub1": {"foo": "one"}},
    "top2": {"sub1": {"foo": "one"}},
}
_AGE_TRUTH_DOC = {"foo": [{"age": 0}, {"age": None}]}
_NAME_DOC = {"foo": [{"name": "a"}, {"name": "b"}]}
_FIRST_LAST_DOC = {
    "foo": [
        {"first": "foo", "last": "bar"},
        {"first": "foo", "last": "foo"},
        {"first": "foo", "last": "baz"},
    ]
}
_AGE_CMP_DOC = {"foo": [{"age": 20}, {"age": 25}, {"age": 30}]}
_SUBEXPR_DOC = {"foo": [{"top": {"name": "a"}}, {"top": {"name": "b"}}]}
_JSON_OBJECT_DOC = {
    "foo": [
        {"top": {"first": "foo", "last": "bar"}},
        {"top": {"first": "foo", "last": "other"}},
    ]
}
_KEY_EQ_DOC = {
    "foo": [
        {"key": True},
        {"key": False},
        {"key": 0},
        {"key": 1},
        {"key": [0]},
        {"key": {"bar": [0]}},
        {"key": None},
        {"key": [1]},
        {"key": {"a": 2}},
    ]
}
_FILTER_ON_OBJECT_DOC = {"foo": {"age": 1}}


def _fresh_ident() -> str:
    token = bracket_ident()
    assert token not in _PUBLIC_IDENTS, token
    return token


def _fresh_payload() -> str:
    token = bracket_payload()
    assert token not in _PUBLIC_PAYLOADS, token
    return token


def _fresh_int(lo: int, hi: int, *, extra: frozenset[int] | None = None) -> int:
    blocked = set(_PUBLIC_NUMBERS)
    if extra:
        blocked.update(extra)
    span = hi - lo + 1
    if span < 1:
        raise AssertionError(f"empty int range {lo}..{hi}")
    for _ in range(24):
        n = lo + (int(uuid.uuid4().hex[:4], 16) % span)
        if n not in blocked:
            return n
    raise AssertionError(f"could not pick int in {lo}..{hi} avoiding {blocked!r}")


def _require_single_kept_field(observed: object, field: str, expected: object) -> list:
    """Require a one-element array whose mapping field has the JSON type of *expected*.

    Host ``==`` treats True as 1 and False as 0; L28 / L207 require the
    boolean and the number to stay distinct.
    """
    assert isinstance(observed, list), f"expected a kept array, got {observed!r}"
    assert len(observed) == 1, f"expected one kept mapping, got {observed!r}"
    item = observed[0]
    assert isinstance(item, dict), f"kept element is not a mapping: {item!r}"
    assert list(item.keys()) == [field], f"kept keys {list(item.keys())!r} != [{field!r}]"
    actual = item[field]
    assert type(actual) is type(expected), (
        f"kept {field!r} is {type(actual).__name__} {actual!r}, "
        f"expected {type(expected).__name__} {expected!r}"
    )
    assert actual == expected
    print(
        f"kept_field {field!r} type={type(actual).__name__} value={actual!r}",
        flush=True,
    )
    return observed


# ---------------------------------------------------------------------------
# A. List wildcard projects and drops right-hand nulls
# ---------------------------------------------------------------------------


def test_list_wildcard_projects_named_field_and_drops_nulls():
    bars = require_oneshot_equals(
        "foo[*].bar", _LIST_WILDCARD_DOC, ["one", "two", "three"]
    )
    assert bars == ["one", "two", "three"]
    assert bars != ["one", "two", "three", None]
    assert bars is not _LIST_WILDCARD_DOC
    notbars = require_oneshot_equals("foo[*].notbar", _LIST_WILDCARD_DOC, ["four"])
    assert notbars == ["four"]
    assert len(notbars) == 1
    require_bracket_null(oneshot_bracket_search("foo.bar", _LIST_WILDCARD_DOC))
    field = require_bracket_value(oneshot_bracket_search("foo.bar", _LIST_WILDCARD_DOC))
    print(f"field_on_array={field!r} bars={bars!r}", flush=True)
    assert field is None
    assert field != bars


def test_list_wildcard_as_whole_expression_on_array_document():
    whole = require_oneshot_equals("[*]", _LIST_WILDCARD_ARRAY, _LIST_WILDCARD_ARRAY)
    assert whole == _LIST_WILDCARD_ARRAY
    bars = require_oneshot_equals(
        "[*].bar", _LIST_WILDCARD_ARRAY, ["one", "two", "three"]
    )
    assert bars == ["one", "two", "three"]
    assert bars != whole


def test_runtime_list_wildcard_drops_missing_field():
    root = _fresh_ident()
    field = _fresh_ident()
    missing = _fresh_ident()
    assert field != missing
    p1, p2, p3, extra = (
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
    )
    mappings = [
        {field: p1},
        {field: p2},
        {missing: extra},
        {field: p3},
    ]
    document = {root: mappings}
    projected = require_oneshot_equals(
        f"{root}[*].{field}", document, [p1, p2, p3]
    )
    assert projected == [p1, p2, p3]
    assert None not in projected
    only_missing = require_oneshot_equals(
        f"{root}[*].{missing}", document, [extra]
    )
    assert only_missing == [extra]
    assert len(only_missing) == 1
    whole = require_oneshot_equals(f"[*].{field}", mappings, [p1, p2, p3])
    assert whole == [p1, p2, p3]
    print(f"runtime_list_wildcard projected={projected!r}", flush=True)


def test_compile_then_search_list_wildcard_projection():
    public = compile_once_then_search("foo[*].bar", _LIST_WILDCARD_DOC)
    assert public == ["one", "two", "three"]
    root = _fresh_ident()
    field = _fresh_ident()
    p1, p2, p3 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    document = {root: [{field: p1}, {field: p2}, {_fresh_ident(): _fresh_payload()}, {field: p3}]}
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[*].{field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_list_wildcard first={first!r} second={second!r}", flush=True)
    assert first == second == [p1, p2, p3]
    assert first != public


# ---------------------------------------------------------------------------
# B. Nested list wildcard, index after wildcard; missing/non-array is null
# ---------------------------------------------------------------------------


def test_nested_list_wildcard_drops_string_parent():
    nested = require_oneshot_equals(
        "foo[*].bar[*].kind", _NESTED_KIND_DOC, _NESTED_KIND_RESULT
    )
    assert nested == _NESTED_KIND_RESULT
    assert len(nested) == 2
    assert None not in nested
    assert "string" not in nested
    flat = [item for group in nested for item in group]
    assert "string" not in flat


def test_index_after_list_wildcard():
    first = require_oneshot_equals(
        "foo[*][0]", _INDEX_AFTER_DOC, ["one", "three", "five"]
    )
    second = require_oneshot_equals("foo[*][1]", _INDEX_AFTER_DOC, ["two", "four"])
    empty = require_successful_empty_array(oneshot_bracket_search("foo[*][2]", _INDEX_AFTER_DOC))
    print(f"index_after first={first!r} second={second!r} empty={empty!r}", flush=True)
    assert first == ["one", "three", "five"]
    assert second == ["two", "four"]
    assert empty == []
    assert empty is not None
    assert empty != first


def test_list_wildcard_on_missing_or_non_array_is_successful_null():
    live = require_oneshot_equals(
        "foo[*].bar", _LIST_WILDCARD_DOC, ["one", "two", "three"]
    )
    assert live == ["one", "two", "three"]
    require_bracket_null(oneshot_bracket_search("bar[*]", _LIST_WILDCARD_DOC))
    missing = require_bracket_value(oneshot_bracket_search("bar[*]", _LIST_WILDCARD_DOC))
    assert missing is None
    assert missing != []
    for document, label in (
        ({"foo": {"bar": 1}}, "object"),
        ({"foo": "string"}, "string"),
        ({"foo": 23}, "number"),
        ({"foo": None}, "null"),
    ):
        require_bracket_null(oneshot_bracket_search("foo[*]", document))
        observed = require_bracket_value(oneshot_bracket_search("foo[*]", document))
        print(f"non_array_list_wildcard {label}={observed!r}", flush=True)
        assert observed is None
        assert observed != []


def test_runtime_nested_wildcard_and_index_after_wildcard():
    root = _fresh_ident()
    inner = _fresh_ident()
    kind = _fresh_ident()
    p1, p2, p3, p4 = (
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
    )
    string_parent = "not-a-list"
    mappings = [
        {inner: string_parent},
        {inner: [{kind: p1}, {kind: p2}]},
        {inner: [{kind: p3}, {kind: p4}]},
    ]
    assert not isinstance(mappings[0][inner], list)
    document = {root: mappings}
    nested = require_oneshot_equals(
        f"{root}[*].{inner}[*].{kind}", document, [[p1, p2], [p3, p4]]
    )
    assert nested == [[p1, p2], [p3, p4]]
    assert len(nested) == 2
    assert string_parent not in nested

    a0, a1, a2 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    b0 = _fresh_payload()
    c0, c1 = _fresh_payload(), _fresh_payload()
    arrays = [[a0, a1, a2], [b0], [c0, c1]]
    i = in_range_index(3)
    expected = [row[i] for row in arrays if i < len(row)]
    indexed = require_oneshot_equals(f"{root}[*][{i}]", {root: arrays}, expected)
    print(f"runtime_index_after i={i} indexed={indexed!r}", flush=True)
    assert indexed == expected
    if i != 0:
        assert indexed != [a0, b0, c0]

    present = _fresh_ident()
    items = [_fresh_payload(), _fresh_payload()]
    require_bracket_null(oneshot_bracket_search(f"{root}[*]", {present: items}))
    require_bracket_null(oneshot_bracket_search(f"{root}[*]", {root: "text"}))
    require_bracket_null(oneshot_bracket_search(f"{root}[*]", {root: {inner: items}}))
    require_bracket_null(oneshot_bracket_search(f"{root}[*]", {root: 9}))
    live = require_oneshot_equals(f"{root}[*]", {root: items}, items)
    assert live == items


def test_compile_then_search_nested_wildcard_and_index_after():
    public_nested = compile_once_then_search(
        "foo[*].bar[*].kind", _NESTED_KIND_DOC
    )
    assert public_nested == _NESTED_KIND_RESULT
    root = _fresh_ident()
    inner = _fresh_ident()
    kind = _fresh_ident()
    p1, p2, p3, p4 = (
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
        _fresh_payload(),
    )
    mappings = [
        {inner: [{kind: p1}, {kind: p2}]},
        {inner: "middle-string"},
        {inner: [{kind: p3}, {kind: p4}]},
    ]
    parsed_nested = require_bracket_value(
        compile_bracket_expression(f"{root}[*].{inner}[*].{kind}")
    )
    first_nested = require_bracket_value(search_compiled_bracket(parsed_nested, {root: mappings}))
    second_nested = require_bracket_value(search_compiled_bracket(parsed_nested, {root: mappings}))
    print(f"compile_nested first={first_nested!r}", flush=True)
    assert first_nested == second_nested == [[p1, p2], [p3, p4]]

    public_index = compile_once_then_search("foo[*][0]", _INDEX_AFTER_DOC)
    assert public_index == ["one", "three", "five"]
    a0, a1, a2 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    b0 = _fresh_payload()
    c0, c1 = _fresh_payload(), _fresh_payload()
    arrays = [[a0, a1, a2], [b0], [c0, c1]]
    i = in_range_index(3)
    expected = [row[i] for row in arrays if i < len(row)]
    parsed_index = require_bracket_value(compile_bracket_expression(f"{root}[*][{i}]"))
    first_index = require_bracket_value(search_compiled_bracket(parsed_index, {root: arrays}))
    second_index = require_bracket_value(search_compiled_bracket(parsed_index, {root: arrays}))
    print(f"compile_index_after i={i} first={first_index!r}", flush=True)
    assert first_index == second_index == expected


# ---------------------------------------------------------------------------
# C. Object wildcard projects values, not keys
# ---------------------------------------------------------------------------


def test_object_wildcard_projects_values_not_keys():
    bazs = require_oneshot_equals(
        "foo.*.baz", _OBJECT_WILDCARD_DOC, ["val", "val", "val"]
    )
    assert bazs == ["val", "val", "val"]
    assert "bar" not in bazs
    assert "other" not in bazs
    notbaz = require_oneshot_equals(
        "foo.*.notbaz", _OBJECT_WILDCARD_DOC, [["a", "b", "c"], ["a", "b", "c"]]
    )
    assert notbaz == [["a", "b", "c"], ["a", "b", "c"]]
    firsts = require_oneshot_equals(
        "foo.*.notbaz[0]", _OBJECT_WILDCARD_DOC, ["a", "a"]
    )
    assert firsts == ["a", "a"]


def test_object_wildcard_skips_values_without_field():
    bars = require_oneshot_equals("*.bar", _STAR_BAR_DOC, ["one", "one"])
    assert bars == ["one", "one"]
    assert "three" not in bars
    assert "nomatch" not in bars
    assert "foo" not in bars


def test_object_wildcard_as_whole_expression_and_flatten_after():
    tops = require_oneshot_equals(
        "*",
        _TOP_DOC,
        [{"sub1": {"foo": "one"}}, {"sub1": {"foo": "one"}}],
    )
    assert tops == [{"sub1": {"foo": "one"}}, {"sub1": {"foo": "one"}}]
    flattened = require_oneshot_equals("*.*.foo[]", _TOP_DOC, ["one", "one"])
    assert flattened == ["one", "one"]
    assert flattened != tops


def test_object_wildcard_on_non_object_is_successful_null():
    live = require_oneshot_equals("hash.*", {"hash": {"foo": "val", "bar": "val"}}, ["val", "val"])
    assert live == ["val", "val"]
    for document, label in (
        ({"foo": [1, 2, 3]}, "array"),
        ({"foo": "string"}, "string"),
        ({"foo": 23}, "number"),
        ({"foo": None}, "null"),
    ):
        require_bracket_null(oneshot_bracket_search("foo.*", document))
        observed = require_bracket_value(oneshot_bracket_search("foo.*", document))
        print(f"non_object_wildcard {label}={observed!r}", flush=True)
        assert observed is None
        assert observed != []
        if document["foo"] is not None:
            assert observed != document["foo"]


def test_list_versus_object_wildcard_require_matching_kind():
    p1, p2 = _fresh_payload(), _fresh_payload()
    k1, k2 = _fresh_ident(), _fresh_ident()
    obj = {k1: p1, k2: p2}
    arr = [p1, p2]
    require_bracket_null(oneshot_bracket_search("[*]", obj))
    star_on_obj = require_bracket_value(oneshot_bracket_search("*", obj))
    require_array_multiset(star_on_obj, [p1, p2])
    require_bracket_null(oneshot_bracket_search("*", arr))
    list_on_arr = require_oneshot_equals("[*]", arr, [p1, p2])
    print(
        f"kind_contrast star_on_obj={star_on_obj!r} list_on_arr={list_on_arr!r}",
        flush=True,
    )
    assert list_on_arr == [p1, p2]
    assert require_bracket_value(oneshot_bracket_search("[*]", obj)) is None
    assert require_bracket_value(oneshot_bracket_search("*", arr)) is None


def test_runtime_object_wildcard_is_values_multiset():
    root = _fresh_ident()
    field = _fresh_ident()
    other = _fresh_ident()
    p1, p2, bait = _fresh_payload(), _fresh_payload(), _fresh_payload()
    inner = {
        _fresh_ident(): {field: p1},
        _fresh_ident(): {field: p2},
        _fresh_ident(): {other: bait},
    }
    document = {root: inner}
    projected = require_bracket_value(oneshot_bracket_search(f"{root}.*.{field}", document))
    require_array_multiset(projected, [p1, p2])
    assert bait not in projected
    assert root not in projected
    whole = require_bracket_value(oneshot_bracket_search(f"*.{field}", inner))
    require_array_multiset(whole, [p1, p2])
    print(f"runtime_object_wildcard projected={projected!r}", flush=True)

    require_bracket_null(oneshot_bracket_search(f"{root}.*", {root: [p1, p2]}))
    require_bracket_null(oneshot_bracket_search(f"{root}.*", {root: p1}))
    live_obj = {_fresh_ident(): p1, _fresh_ident(): p2}
    live = require_bracket_value(oneshot_bracket_search(f"{root}.*", {root: live_obj}))
    require_array_multiset(live, [p1, p2])


def test_runtime_nested_object_wildcard_projects_values():
    field = _fresh_ident()
    p1, p2 = _fresh_payload(), _fresh_payload()
    assert {p1, p2} != {"one"}
    document = {
        _fresh_ident(): {
            _fresh_ident(): {field: p1},
            _fresh_ident(): {_fresh_ident(): _fresh_payload()},
        },
        _fresh_ident(): {
            _fresh_ident(): {field: p2},
            _fresh_ident(): {_fresh_ident(): _fresh_payload()},
        },
    }
    nested = require_bracket_value(oneshot_bracket_search(f"*.*.{field}", document))
    require_array_multiset(nested, [[p1], [p2]])
    print(f"runtime_nested_object_wildcard nested={nested!r}", flush=True)
    assert "one" not in nested


def test_compile_then_search_object_wildcard_projection():
    public = compile_once_then_search("foo.*.baz", _OBJECT_WILDCARD_DOC)
    assert public == ["val", "val", "val"]
    root = _fresh_ident()
    field = _fresh_ident()
    p1, p2 = _fresh_payload(), _fresh_payload()
    inner = {
        _fresh_ident(): {field: p1},
        _fresh_ident(): {field: p2},
        _fresh_ident(): {_fresh_ident(): _fresh_payload()},
    }
    parsed = require_bracket_value(compile_bracket_expression(f"{root}.*.{field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, {root: inner}))
    second = require_bracket_value(search_compiled_bracket(parsed, {root: inner}))
    print(f"compile_object_wildcard first={first!r} second={second!r}", flush=True)
    require_array_multiset(first, [p1, p2])
    require_array_multiset(second, [p1, p2])
    assert first != public


# ---------------------------------------------------------------------------
# D. Filter keeps true-value elements; following selector is a projection
# ---------------------------------------------------------------------------


def test_filter_field_truthiness_keeps_zero_drops_null():
    kept = require_oneshot_equals("foo[?age]", _AGE_TRUTH_DOC, [{"age": 0}])
    assert kept == [{"age": 0}]
    assert {"age": None} not in kept
    assert len(kept) == 1


def test_filter_named_equality_and_field_to_field():
    named = require_oneshot_equals("foo[?name == 'a']", _NAME_DOC, [{"name": "a"}])
    assert named == [{"name": "a"}]
    assert {"name": "b"} not in named
    matched = require_oneshot_equals(
        "foo[?first == last]",
        _FIRST_LAST_DOC,
        [{"first": "foo", "last": "foo"}],
    )
    assert matched == [{"first": "foo", "last": "foo"}]
    projected = require_oneshot_equals(
        "foo[?first == last].first", _FIRST_LAST_DOC, ["foo"]
    )
    assert projected == ["foo"]
    assert projected != "foo"


def test_filter_named_age_comparators_and_empty_when_none_match():
    gt = require_oneshot_equals("foo[?age > `25`]", _AGE_CMP_DOC, [{"age": 30}])
    ge = require_oneshot_equals(
        "foo[?age >= `25`]", _AGE_CMP_DOC, [{"age": 25}, {"age": 30}]
    )
    lt = require_oneshot_equals("foo[?age < `25`]", _AGE_CMP_DOC, [{"age": 20}])
    eq = require_oneshot_equals("foo[?age == `20`]", _AGE_CMP_DOC, [{"age": 20}])
    ne = require_oneshot_equals(
        "foo[?age != `20`]", _AGE_CMP_DOC, [{"age": 25}, {"age": 30}]
    )
    empty = require_successful_empty_array(
        oneshot_bracket_search("foo[?age > `30`]", _AGE_CMP_DOC)
    )
    print(
        f"age_cmp gt={gt!r} ge={ge!r} lt={lt!r} eq={eq!r} ne={ne!r} empty={empty!r}",
        flush=True,
    )
    assert gt == [{"age": 30}]
    assert ge == [{"age": 25}, {"age": 30}]
    assert lt == [{"age": 20}]
    assert eq == [{"age": 20}]
    assert ne == [{"age": 25}, {"age": 30}]
    assert empty == []
    assert empty is not None


def test_filter_subexpression_and_json_object_literal():
    sub = require_oneshot_equals(
        "foo[?top.name == 'a']", _SUBEXPR_DOC, [{"top": {"name": "a"}}]
    )
    assert sub == [{"top": {"name": "a"}}]
    assert {"top": {"name": "b"}} not in sub
    matched = require_oneshot_equals(
        'foo[?top == `{"first": "foo", "last": "bar"}`]',
        _JSON_OBJECT_DOC,
        [{"top": {"first": "foo", "last": "bar"}}],
    )
    assert matched == [{"top": {"first": "foo", "last": "bar"}}]
    assert {"top": {"first": "foo", "last": "other"}} not in matched


def test_runtime_filter_truthiness_comparators_and_following_projection():
    root = _fresh_ident()
    field = _fresh_ident()
    nonzero = _fresh_int(2, 19)
    mappings = [
        {field: None},
        {field: 0},
        {field: nonzero},
    ]
    assert mappings[0][field] is None
    kept = require_oneshot_equals(
        f"{root}[?{field}]",
        {root: mappings},
        [{field: 0}, {field: nonzero}],
    )
    assert kept == [{field: 0}, {field: nonzero}]
    assert {field: None} not in kept
    assert kept[0] != kept[1]

    lo = _fresh_int(1, 12)
    mid = _fresh_int(13, 24, extra=frozenset({lo}))
    hi = _fresh_int(31, 70, extra=frozenset({lo, mid}))
    assert lo < mid < hi
    t = mid
    cmp_field = _fresh_ident()
    cmp_maps = [{cmp_field: lo}, {cmp_field: hi}, {cmp_field: mid}]
    expected_gt = [item for item in cmp_maps if item[cmp_field] > t]
    assert expected_gt == [{cmp_field: hi}]
    gt = require_oneshot_equals(
        f"{root}[?{cmp_field} > {json_literal_text(t)}]",
        {root: cmp_maps},
        expected_gt,
    )
    assert gt == expected_gt
    none_t = hi + 8
    if none_t in _PUBLIC_NUMBERS:
        none_t = hi + 13
    empty = require_successful_empty_array(
        oneshot_bracket_search(
            f"{root}[?{cmp_field} > {json_literal_text(none_t)}]",
            {root: cmp_maps},
        )
    )
    assert empty == []

    flag = _fresh_ident()
    payload_field = _fresh_ident()
    p1, p2, bait = _fresh_payload(), _fresh_payload(), _fresh_payload()
    two_kept = [
        {flag: None, payload_field: bait},
        {flag: 0, payload_field: p1},
        {flag: nonzero, payload_field: p2},
    ]
    projected = require_oneshot_equals(
        f"{root}[?{flag}].{payload_field}", {root: two_kept}, [p1, p2]
    )
    assert projected == [p1, p2]
    assert bait not in projected
    one_missing = [
        {flag: None, payload_field: bait},
        {flag: 0},
        {flag: nonzero, payload_field: p2},
    ]
    dropped = require_oneshot_equals(
        f"{root}[?{flag}].{payload_field}", {root: one_missing}, [p2]
    )
    assert dropped == [p2]
    assert len(dropped) == 1

    f1, f2 = _fresh_ident(), _fresh_ident()
    same = _fresh_payload()
    d1, d2 = _fresh_payload(), _fresh_payload()
    pair_maps = [
        {f1: d1, f2: d2},
        {f1: same, f2: same},
        {f1: same, f2: d1},
    ]
    paired = require_oneshot_equals(
        f"{root}[?{f1} == {f2}]",
        {root: pair_maps},
        [{f1: same, f2: same}],
    )
    assert paired == [{f1: same, f2: same}]

    outer, inner = _fresh_ident(), _fresh_ident()
    hit, miss = _fresh_payload(), _fresh_payload()
    sub_maps = [{outer: {inner: hit}}, {outer: {inner: miss}}]
    sub = require_oneshot_equals(
        f"{root}[?{outer}.{inner} == '{hit}']",
        {root: sub_maps},
        [{outer: {inner: hit}}],
    )
    assert sub == [{outer: {inner: hit}}]

    top = _fresh_ident()
    k1, k2 = _fresh_ident(), _fresh_ident()
    v1, v2, v3 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    match = {k1: v1, k2: v2}
    bait_obj = {k1: v1, k2: v3}
    literal = json_literal_text(match)
    obj_maps = [{top: match}, {top: bait_obj}]
    obj_kept = require_oneshot_equals(
        f"{root}[?{top} == {literal}]",
        {root: obj_maps},
        [{top: match}],
    )
    assert obj_kept == [{top: match}]
    print(f"runtime_filter paired={paired!r} projected={projected!r}", flush=True)


def test_compile_then_search_filter_projection():
    public = compile_once_then_search(
        "foo[?first == last].first", _FIRST_LAST_DOC
    )
    assert public == ["foo"]
    root = _fresh_ident()
    flag = _fresh_ident()
    field = _fresh_ident()
    p1, p2, bait = _fresh_payload(), _fresh_payload(), _fresh_payload()
    nonzero = _fresh_int(2, 19)
    mappings = [
        {flag: None, field: bait},
        {flag: 0, field: p1},
        {flag: nonzero, field: p2},
    ]
    parsed = require_bracket_value(compile_bracket_expression(f"{root}[?{flag}].{field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, {root: mappings}))
    second = require_bracket_value(search_compiled_bracket(parsed, {root: mappings}))
    print(f"compile_filter_proj first={first!r} second={second!r}", flush=True)
    assert first == second == [p1, p2]
    assert bait not in first
    assert first != public


# ---------------------------------------------------------------------------
# E. Filter equality is JSON-value equality
# ---------------------------------------------------------------------------


def test_filter_equality_is_json_value_not_truthiness():
    truthy = require_bracket_value(oneshot_bracket_search("foo[?key == `true`]", _KEY_EQ_DOC))
    _require_single_kept_field(truthy, "key", True)
    falsey = require_bracket_value(oneshot_bracket_search("foo[?key == `false`]", _KEY_EQ_DOC))
    _require_single_kept_field(falsey, "key", False)
    zero = require_bracket_value(oneshot_bracket_search("foo[?key == `0`]", _KEY_EQ_DOC))
    _require_single_kept_field(zero, "key", 0)
    one = require_bracket_value(oneshot_bracket_search("foo[?key == `1`]", _KEY_EQ_DOC))
    _require_single_kept_field(one, "key", 1)
    print(
        f"json_eq true={truthy!r} false={falsey!r} zero={zero!r} one={one!r}",
        flush=True,
    )


def test_runtime_filter_equality_does_not_confuse_zero_or_one_with_booleans():
    root = _fresh_ident()
    field = _fresh_ident()
    assert field != "key"
    mappings = [
        {field: True},
        {field: False},
        {field: 0},
        {field: 1},
        {field: None},
    ]
    document = {root: mappings}
    truthy = require_bracket_value(
        oneshot_bracket_search(f"{root}[?{field} == `true`]", document)
    )
    _require_single_kept_field(truthy, field, True)
    zero = require_bracket_value(
        oneshot_bracket_search(f"{root}[?{field} == `0`]", document)
    )
    _require_single_kept_field(zero, field, 0)
    print(f"runtime_json_eq true={truthy!r} zero={zero!r}", flush=True)


def test_compile_then_search_filter_json_value_equality():
    parsed = require_bracket_value(compile_bracket_expression("foo[?key == `true`]"))
    first = require_bracket_value(search_compiled_bracket(parsed, _KEY_EQ_DOC))
    second = require_bracket_value(search_compiled_bracket(parsed, _KEY_EQ_DOC))
    print(f"compile_json_eq first={first!r} second={second!r}", flush=True)
    assert first == second
    _require_single_kept_field(first, "key", True)
    _require_single_kept_field(second, "key", True)


# ---------------------------------------------------------------------------
# F. Comparison after a list wildcard is whole-array
# ---------------------------------------------------------------------------


def test_comparison_after_list_wildcard_is_whole_array():
    baseline = require_oneshot_equals(
        "foo[*].bar", _LIST_WILDCARD_DOC, ["one", "two", "three"]
    )
    assert baseline == ["one", "two", "three"]
    whole = require_oneshot_equals(
        'foo[*].bar == `["one", "two", "three"]`', _LIST_WILDCARD_DOC, True
    )
    assert whole is True
    single = require_oneshot_equals(
        "foo[*].bar == 'one'", _LIST_WILDCARD_DOC, False
    )
    print(f"whole_array_cmp whole={whole!r} single={single!r}", flush=True)
    assert single is False
    assert single != [False, False, False]


def test_runtime_comparison_after_list_wildcard_is_whole_array():
    root = _fresh_ident()
    field = _fresh_ident()
    p1, p2, p3 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    mappings = [{field: p1}, {field: p2}, {field: p3}]
    document = {root: mappings}
    projected = require_oneshot_equals(
        f"{root}[*].{field}", document, [p1, p2, p3]
    )
    assert projected == [p1, p2, p3]
    same = require_oneshot_equals(
        f"{root}[*].{field} == {json_literal_text([p1, p2, p3])}",
        document,
        True,
    )
    assert same is True
    as_string = require_oneshot_equals(
        f"{root}[*].{field} == '{p1}'", document, False
    )
    assert as_string is False
    swapped = require_oneshot_equals(
        f"{root}[*].{field} == {json_literal_text([p1, p3, p2])}",
        document,
        False,
    )
    print(
        f"runtime_whole_cmp same={same!r} as_string={as_string!r} swapped={swapped!r}",
        flush=True,
    )
    assert swapped is False
    assert swapped != [False, False, False]


def test_compile_then_search_whole_array_comparison():
    public = compile_once_then_search(
        'foo[*].bar == `["one", "two", "three"]`', _LIST_WILDCARD_DOC
    )
    assert public is True
    root = _fresh_ident()
    field = _fresh_ident()
    p1, p2, p3 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    document = {root: [{field: p1}, {field: p2}, {field: p3}]}
    parsed = require_bracket_value(
        compile_bracket_expression(
            f"{root}[*].{field} == {json_literal_text([p1, p2, p3])}"
        )
    )
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    assert first is second is True
    parsed_str = require_bracket_value(
        compile_bracket_expression(f"{root}[*].{field} == '{p1}'")
    )
    as_string = require_bracket_value(search_compiled_bracket(parsed_str, document))
    assert as_string is False
    parsed_swap = require_bracket_value(
        compile_bracket_expression(
            f"{root}[*].{field} == {json_literal_text([p1, p3, p2])}"
        )
    )
    swapped = require_bracket_value(search_compiled_bracket(parsed_swap, document))
    print(
        f"compile_whole_cmp first={first!r} as_string={as_string!r} swapped={swapped!r}",
        flush=True,
    )
    assert swapped is False


def test_and_or_after_list_wildcard_combines_whole_array():
    """L208: and/or after a list wildcard combines the whole projected array."""
    baseline = require_oneshot_equals(
        "foo[*].bar", _LIST_WILDCARD_DOC, ["one", "two", "three"]
    )
    assert baseline == ["one", "two", "three"]

    # L208 requires one combined value, not a per-element array. It
    # does not fix that value (operand-return is FP-06).
    combined_and = require_bracket_value(
        oneshot_bracket_search("foo[*].bar && `true`", _LIST_WILDCARD_DOC)
    )
    print(f"whole_array_and combined={combined_and!r}", flush=True)
    require_one_combined_value(combined_and, baseline)
    assert combined_and != [True, True, True]

    combined_or = require_bracket_value(
        oneshot_bracket_search("foo[*].bar || `false`", _LIST_WILDCARD_DOC)
    )
    print(f"whole_array_or combined={combined_or!r}", flush=True)
    require_one_combined_value(combined_or, baseline)
    assert combined_or != [True, True, True]
    assert combined_or != [False, False, False]


def test_runtime_and_or_after_list_wildcard_combines_whole_array():
    root = _fresh_ident()
    field = _fresh_ident()
    p1, p2, p3 = _fresh_payload(), _fresh_payload(), _fresh_payload()
    mappings = [{field: p1}, {field: p2}, {field: p3}]
    document = {root: mappings}
    projected = require_oneshot_equals(
        f"{root}[*].{field}", document, [p1, p2, p3]
    )
    assert projected == [p1, p2, p3]
    combined_and = require_bracket_value(
        oneshot_bracket_search(f"{root}[*].{field} && `true`", document)
    )
    require_one_combined_value(combined_and, projected)
    assert combined_and != [True, True, True]
    combined_or = require_bracket_value(
        oneshot_bracket_search(f"{root}[*].{field} || `false`", document)
    )
    print(
        f"runtime_whole_and_or and={combined_and!r} or={combined_or!r}",
        flush=True,
    )
    require_one_combined_value(combined_or, projected)
    assert combined_or != [True, True, True]
    assert combined_or != [False, False, False]


# ---------------------------------------------------------------------------
# G. Filter on a non-array is successful null; ill-formed predicate fails
# ---------------------------------------------------------------------------


def test_filter_on_non_array_is_successful_null():
    live = require_oneshot_equals("foo[?age]", _AGE_TRUTH_DOC, [{"age": 0}])
    assert live == [{"age": 0}]
    require_bracket_null(oneshot_bracket_search("foo[?age]", _FILTER_ON_OBJECT_DOC))
    on_object = require_bracket_value(
        oneshot_bracket_search("foo[?age]", _FILTER_ON_OBJECT_DOC)
    )
    print(f"filter_on_object={on_object!r}", flush=True)
    assert on_object is None
    assert on_object != [{"age": 1}]
    assert on_object != [1]
    assert on_object != []
    require_bracket_null(oneshot_bracket_search("bar[?age]", _AGE_TRUTH_DOC))
    missing = require_bracket_value(oneshot_bracket_search("bar[?age]", _AGE_TRUTH_DOC))
    assert missing is None
    assert missing != []


def test_runtime_filter_on_non_array_is_successful_null():
    root = _fresh_ident()
    field = _fresh_ident()
    require_bracket_null(
        oneshot_bracket_search(f"{root}[?{field}]", {root: {field: 1}})
    )
    require_bracket_null(oneshot_bracket_search(f"{root}[?{field}]", {root: "text"}))
    require_bracket_null(oneshot_bracket_search(f"{root}[?{field}]", {root: 7}))
    live_maps = [{field: None}, {field: 0}, {field: None}]
    live = require_oneshot_equals(
        f"{root}[?{field}]", {root: live_maps}, [{field: 0}]
    )
    print(f"runtime_filter_non_array live={live!r}", flush=True)
    assert live == [{field: 0}]
    assert len(live) == 1


def test_ill_formed_filter_predicate_is_value_error():
    live = require_oneshot_equals("foo[?name == 'a']", _NAME_DOC, [{"name": "a"}])
    assert live == [{"name": "a"}]
    baited = dict(_NAME_DOC)
    baited.update(bracket_sentinel_document())
    observed = assert_bracket_search_is_value_error("foo[?name = 'a']", baited)
    result = oneshot_bracket_search("foo[?name = 'a']", baited)
    print(f"ill_formed_filter exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not baited
    assert result.value != []
    assert result.value != [{"name": "a"}]

    root = _fresh_ident()
    field = _fresh_ident()
    payload = _fresh_payload()
    document = {root: [{field: payload}, {field: _fresh_payload()}]}
    document.update(bracket_sentinel_document())
    good = require_oneshot_equals(
        f"{root}[?{field} == '{payload}']",
        document,
        [{field: payload}],
    )
    assert good == [{field: payload}]
    bad_expr = f"{root}[?{field} = '{payload}']"
    runtime_exc = assert_bracket_search_is_value_error(bad_expr, document)
    runtime_result = oneshot_bracket_search(bad_expr, document)
    print(f"runtime_ill_formed exc={runtime_exc!r}", flush=True)
    assert runtime_result.exception is not None
    assert runtime_result.value is not document
    assert runtime_result.value != []
    assert runtime_result.value != good


def test_compile_path_ill_formed_filter_predicate_does_not_succeed():
    baited = dict(_NAME_DOC)
    baited.update(bracket_sentinel_document())
    require_unsuccessful_compile_path("foo[?name = 'a']", baited)
    root = _fresh_ident()
    field = _fresh_ident()
    payload = _fresh_payload()
    document = {root: [{field: payload}]}
    document.update(bracket_sentinel_document())
    require_unsuccessful_compile_path(f"{root}[?{field} = '{payload}']", document)


# ---------------------------------------------------------------------------
# H. Wildcard continuation must be grammatical; glued stars fail
# ---------------------------------------------------------------------------


def test_wildcard_without_grammatical_continuation_is_syntax():
    live = require_oneshot_equals(
        "foo[*].bar", _LIST_WILDCARD_DOC, ["one", "two", "three"]
    )
    assert live == ["one", "two", "three"]
    document = dict(_LIST_WILDCARD_DOC)
    document.update(bracket_sentinel_document())
    assert_search_is_syntax_kind_not_empty_or_incomplete("foo[*]bar", document)
    assert_search_is_syntax_kind_not_empty_or_incomplete("foo[*]*", document)


def test_runtime_wildcard_without_continuation_is_syntax():
    root = _fresh_ident()
    ident = _fresh_ident()
    field = _fresh_ident()
    payload = _fresh_payload()
    document = {root: [{field: payload}]}
    document.update(bracket_sentinel_document())
    live = require_oneshot_equals(f"{root}[*].{field}", document, [payload])
    assert live == [payload]
    assert_search_is_syntax_kind_not_empty_or_incomplete(
        f"{root}[*]{ident}", document
    )
    assert_search_is_syntax_kind_not_empty_or_incomplete(f"{root}[*]*", document)


def test_leading_dot_star_does_not_succeed_unlike_object_wildcard():
    p1, p2 = _fresh_payload(), _fresh_payload()
    k1, k2 = _fresh_ident(), _fresh_ident()
    document = {k1: p1, k2: p2}
    document.update(bracket_sentinel_document())
    live = require_bracket_value(oneshot_bracket_search("*", document))
    require_array_multiset(live, list(document.values()))
    observed = assert_bracket_search_is_value_error(".*", document)
    result = oneshot_bracket_search(".*", document)
    print(f"leading_dot_star exc={observed!r} live={live!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document
    assert result.value is not None or result.exception is not None
    assert result.value != live


def test_star_glued_to_ident_or_digit_does_not_succeed():
    p1, p2 = _fresh_payload(), _fresh_payload()
    document = {"a": p1, "b": p2}
    document.update(bracket_sentinel_document())
    live = require_bracket_value(oneshot_bracket_search("*", document))
    require_array_multiset(live, list(document.values()))
    for expression in ("*foo", "*0"):
        observed = assert_bracket_search_is_value_error(expression, document)
        result = oneshot_bracket_search(expression, document)
        print(f"glued_star {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not document
        assert result.value != live

    ident = _fresh_ident()
    assert ident != "foo"
    digit = _fresh_int(1, 9, extra=frozenset({0}))
    runtime_doc = {_fresh_ident(): p1, _fresh_ident(): p2}
    runtime_doc.update(bracket_sentinel_document())
    runtime_live = require_bracket_value(oneshot_bracket_search("*", runtime_doc))
    require_array_multiset(runtime_live, list(runtime_doc.values()))
    for expression in (f"*{ident}", f"*{digit}"):
        observed = assert_bracket_search_is_value_error(expression, runtime_doc)
        result = oneshot_bracket_search(expression, runtime_doc)
        print(f"runtime_glued_star {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not runtime_doc
        assert result.value != runtime_live


def test_compile_refuses_illegal_wildcard_continuations():
    assert_compile_is_syntax_kind_not_empty_or_incomplete("foo[*]bar")
    assert_compile_is_syntax_kind_not_empty_or_incomplete("foo[*]*")
    root = _fresh_ident()
    ident = _fresh_ident()
    assert_compile_is_syntax_kind_not_empty_or_incomplete(f"{root}[*]{ident}")
    assert_compile_is_syntax_kind_not_empty_or_incomplete(f"{root}[*]*")

    document = {"a": _fresh_payload(), "b": _fresh_payload()}
    document.update(bracket_sentinel_document())
    require_unsuccessful_compile_path(".*", document)
    require_unsuccessful_compile_path("*foo", document)
    require_unsuccessful_compile_path("*0", document)
    runtime_ident_token = _fresh_ident()
    digit = _fresh_int(1, 9, extra=frozenset({0}))
    require_unsuccessful_compile_path(f"*{runtime_ident_token}", document)
    require_unsuccessful_compile_path(f"*{digit}", document)
