# feature: F06
"""FP-06: compare values and combine them with and / or / not.

Assertions follow Full_PRD.original.md FP-06 (L256–L283) together with
object / array / number-including-float-and-host-decimal (L24–L26),
boolean-is-not-1-or-0 (L28), the finite false-value set (L30–L31),
value-error failure (L63), and a lone ``=`` as the syntax kind (L107).
Filter collection is FP-04; this feature pins the operators themselves
and the L272 filter uses of ``&&`` / ``||`` / ``!`` / parentheses.
Evaluation options are not supplied.
"""

from __future__ import annotations

from decimal import Decimal

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F01_helpers import (
    assert_search_is_value_error,
    compile_expression,
    oneshot_search,
    require_search_value,
    require_successful_null,
    runtime_payload,
    search_parsed,
    sentinel_document,
)
from F02_helpers import (
    assert_compile_syntax_not_empty_or_incomplete,
    assert_search_syntax_not_empty_or_incomplete,
    compile_once_then_search,
)
from F03_helpers import require_oneshot_equals, require_successful_empty_array
from F04_helpers import json_literal_text, require_unsuccessful_compile_path
from F06_helpers import (
    compare_ident,
    compare_payload,
    host_decimal,
    host_ordered_floats,
    host_ordered_strings,
    require_float_zero,
    require_host_false,
    require_host_true,
    require_int_zero,
    require_oneshot_ordering_null,
    require_ordering_null,
    runtime_int,
    runtime_mixed_order_document,
    with_sentinel,
)

_EQ_DOC = {"one": 1, "two": 2}
_STRING_DOC = {"a": "2016", "b": "2017"}
_MIXED_DOC = {
    "one": 1,
    "emptylist": [],
    "boolvalue": False,
    "emptyobj": {},
    "True": True,
    "False": False,
}
_DECIMAL_DOC = [{"a": Decimal("3")}]
_OR_DOC = {"outer": {"foo": "foo", "bar": "bar", "baz": "baz"}}
_OR_FALSE_DOC = {
    "outer": {
        "foo": "foo",
        "bool": False,
        "empty_list": [],
        "empty_string": "",
    }
}
_ZERO_DOC = {"Zero": 0, "ZeroFloat": 0.0, "Number": 5}
_AND_DOC = {"True": True, "False": False, "Number": 5, "EmptyList": []}
_LOGIC_DOC = {
    "True": True,
    "False": False,
    "Number": 5,
    "EmptyList": [],
    "Zero": 0,
    "ZeroFloat": 0.0,
}
_BIND_DOC = {"Number": 5, "True": True, "False": False}
_CMP_LOGIC_DOC = {"one": 1, "two": 2, "three": 3}
_FILTER_AND_DOC = {"foo": [{"a": 1, "b": 2}, {"a": 1, "b": 3}]}
_FILTER_OR_DOC = {"foo": [{"name": "a"}, {"name": "b"}]}
_FILTER_BIND_DOC = {"foo": [{"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 4}]}


def _distinct_ints() -> tuple[int, int]:
    left = runtime_int()
    right = runtime_int()
    for _ in range(32):
        if left != right:
            break
        right = runtime_int()
    assert left != right
    return left, right


def _require_kept_mappings(observed: object, expected: list) -> list:
    assert isinstance(observed, list), f"expected a kept array, got {observed!r}"
    assert observed == expected, f"kept {observed!r}, expected {expected!r}"
    return observed


# ---------------------------------------------------------------------------
# A. == / != is JSON-value equality; 0 is not false, 1 is not true
# ---------------------------------------------------------------------------


def test_equality_named_fields_and_negation():
    document = with_sentinel(_EQ_DOC)
    same = require_host_true(require_search_value(oneshot_search("one == one", document)))
    unequal = require_host_false(require_search_value(oneshot_search("one == two", document)))
    negated = require_host_true(require_search_value(oneshot_search("one != two", document)))
    same_negated = require_host_false(
        require_search_value(oneshot_search("one != one", document))
    )
    assert same is True
    assert unequal is False
    assert negated is True
    assert same_negated is False
    assert same is not unequal
    assert negated is not same_negated
    print("named_equality one==one / one==two / !=", flush=True)


def test_number_one_is_not_true_and_zero_is_not_false():
    document = sentinel_document()
    one_is_true = require_host_false(
        require_search_value(oneshot_search("`1` == `true`", document))
    )
    zero_is_false = require_host_false(
        require_search_value(oneshot_search("`0` == `false`", document))
    )
    one_eq_one = require_host_true(
        require_search_value(oneshot_search("`1` == `1`", document))
    )
    zero_eq_zero = require_host_true(
        require_search_value(oneshot_search("`0` == `0`", document))
    )
    assert one_is_true is False
    assert zero_is_false is False
    assert one_eq_one is True
    assert zero_eq_zero is True
    assert one_is_true is not one_eq_one
    assert zero_is_false is not zero_eq_zero
    print("literal_eq 1!=true 0!=false same-number-still-equal", flush=True)


def test_runtime_equality_is_json_value():
    a, b = compare_ident(), compare_ident()
    n, other = _distinct_ints()
    scalars = {a: n, b: other}
    require_host_true(require_search_value(oneshot_search(f"{a} == {a}", scalars)))
    require_host_false(require_search_value(oneshot_search(f"{a} == {b}", scalars)))
    require_host_true(require_search_value(oneshot_search(f"{a} != {b}", scalars)))

    z, f, o, t, zf = (
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
    )
    typed = {z: 0, f: False, o: 1, t: True, zf: 0.0}
    require_host_false(require_search_value(oneshot_search(f"{z} == {f}", typed)))
    require_host_true(require_search_value(oneshot_search(f"{z} != {f}", typed)))
    require_host_true(require_search_value(oneshot_search(f"{z} == {z}", typed)))
    require_host_false(require_search_value(oneshot_search(f"{o} == {t}", typed)))
    require_host_true(require_search_value(oneshot_search(f"{o} != {t}", typed)))
    require_host_false(require_search_value(oneshot_search(f"{zf} == {f}", typed)))
    require_host_true(require_search_value(oneshot_search(f"{zf} != {f}", typed)))

    left, right, extra = compare_ident(), compare_ident(), compare_ident()
    key = compare_ident()
    payload = compare_payload()
    extra_key = compare_ident()
    extra_payload = compare_payload()
    same_maps = {
        left: {key: payload},
        right: {key: payload},
        extra: {key: payload, extra_key: extra_payload},
    }
    require_host_true(
        require_search_value(oneshot_search(f"{left} == {right}", same_maps))
    )
    require_host_false(
        require_search_value(oneshot_search(f"{left} == {extra}", same_maps))
    )

    p1, p2 = compare_payload(), compare_payload()
    assert p1 != p2
    same_key_maps = {left: {key: p1}, right: {key: p2}}
    require_host_false(
        require_search_value(oneshot_search(f"{left} == {right}", same_key_maps))
    )

    e1, e2 = _distinct_ints()
    left_arr = [e1, e2]
    right_arr = [e1, e2]
    extra_arr = [e1, e2, runtime_int()]
    assert left_arr is not right_arr
    arrays = {left: left_arr, right: right_arr, extra: extra_arr}
    require_host_true(require_search_value(oneshot_search(f"{left} == {right}", arrays)))
    require_host_false(
        require_search_value(oneshot_search(f"{left} == {extra}", arrays))
    )

    n = runtime_int()
    require_host_false(
        require_search_value(
            oneshot_search(f"{json_literal_text(n)} == '{n}'", sentinel_document())
        )
    )
    print("runtime_json_eq scalars maps arrays number-vs-string", flush=True)


def test_compile_then_search_equality():
    require_host_true(compile_once_then_search("one == one", _EQ_DOC))
    require_host_false(compile_once_then_search("`0` == `false`", sentinel_document()))

    a, b = compare_ident(), compare_ident()
    n = runtime_int()
    require_host_true(compile_once_then_search(f"{a} == {b}", {a: n, b: n}))

    z, f = compare_ident(), compare_ident()
    require_host_false(compile_once_then_search(f"{z} == {f}", {z: 0, f: False}))

    left, right = compare_ident(), compare_ident()
    e1, e2 = _distinct_ints()
    left_arr = [e1, e2]
    right_arr = [e1, e2]
    assert left_arr is not right_arr
    require_host_true(
        compile_once_then_search(f"{left} == {right}", {left: left_arr, right: right_arr})
    )
    print("compile_equality public and runtime", flush=True)


# ---------------------------------------------------------------------------
# B. Order two numbers or two strings; mixed in-scope types are successful null
# ---------------------------------------------------------------------------


def test_numeric_ordering_four_operators():
    document = with_sentinel(_EQ_DOC)
    lesser_lt = require_host_true(
        require_search_value(oneshot_search("one < two", document))
    )
    lesser_le = require_host_true(
        require_search_value(oneshot_search("one <= two", document))
    )
    lesser_gt = require_host_false(
        require_search_value(oneshot_search("one > two", document))
    )
    lesser_ge = require_host_false(
        require_search_value(oneshot_search("one >= two", document))
    )
    greater_gt = require_host_true(
        require_search_value(oneshot_search("two > one", document))
    )
    greater_le = require_host_false(
        require_search_value(oneshot_search("two <= one", document))
    )
    assert lesser_lt is True
    assert lesser_le is True
    assert lesser_gt is False
    assert lesser_ge is False
    assert greater_gt is True
    assert greater_le is False
    assert lesser_lt is not lesser_gt
    assert greater_gt is not greater_le
    print("numeric_order 1/2 and swapped two>one / two<=one", flush=True)


def test_string_fields_compare_in_host_unicode_order():
    document = with_sentinel(_STRING_DOC)
    assert isinstance(document["a"], str) and isinstance(document["b"], str)
    require_host_true(require_search_value(oneshot_search("a < b", document)))
    print("string_order a=2016 < b=2017", flush=True)


def test_host_decimal_participates_as_number():
    observed = require_search_value(oneshot_search("[?a >= `1`].a", _DECIMAL_DOC))
    assert isinstance(observed, list), f"expected a kept array, got {observed!r}"
    assert len(observed) == 1, f"expected one kept decimal, got {observed!r}"
    kept = observed[0]
    assert type(kept) is Decimal, (
        f"kept element is {type(kept).__name__} {kept!r}, not Decimal"
    )
    assert kept == Decimal("3")
    assert kept != 3 or type(kept) is Decimal
    assert type(kept) is not int
    assert type(kept) is not float
    print(f"host_decimal_public kept={kept!r}", flush=True)


def test_mixed_type_ordering_is_successful_null():
    document = with_sentinel(_MIXED_DOC)
    array_vs_number = oneshot_search("emptylist < one", document)
    require_ordering_null(array_vs_number)
    array_vs_bool = oneshot_search("emptylist < boolvalue", document)
    require_ordering_null(array_vs_bool)
    number_vs_bool = oneshot_search("one < boolvalue", document)
    require_ordering_null(number_vs_bool)
    object_vs_number = oneshot_search("emptyobj < one", document)
    require_ordering_null(object_vs_number)
    missing_vs_number = oneshot_search("missing < one", document)
    require_ordering_null(missing_vs_number)
    number_vs_missing = oneshot_search("one < missing", document)
    require_ordering_null(number_vs_missing)
    bool_vs_bool = oneshot_search("True < False", document)
    require_ordering_null(bool_vs_bool)
    array_ge_number = oneshot_search("emptylist >= one", document)
    require_ordering_null(array_ge_number)
    number_ge_bool = oneshot_search("one >= boolvalue", document)
    require_ordering_null(number_ge_bool)
    for result in (
        array_vs_number,
        array_vs_bool,
        number_vs_bool,
        object_vs_number,
        missing_vs_number,
        number_vs_missing,
        bool_vs_bool,
        array_ge_number,
        number_ge_bool,
    ):
        assert result.exception is None, (
            "mixed-type ordering must succeed as null; "
            f"got {result.exception!r}"
        )
        assert result.value is None, (
            f"mixed-type ordering must be successful null, got {result.value!r}"
        )
        assert result.value is not False
        assert result.value is not True
    print("mixed_order named nulls plus object/null/boolean/>=", flush=True)


def test_runtime_ordering_numbers_strings_and_decimal():
    m_key, n_key = compare_ident(), compare_ident()
    lesser, greater = _distinct_ints()
    if lesser > greater:
        lesser, greater = greater, lesser
    numbers = {m_key: lesser, n_key: greater}
    require_host_true(
        require_search_value(oneshot_search(f"{m_key} < {n_key}", numbers))
    )
    require_host_true(
        require_search_value(oneshot_search(f"{m_key} <= {n_key}", numbers))
    )
    require_host_false(
        require_search_value(oneshot_search(f"{m_key} > {n_key}", numbers))
    )
    require_host_false(
        require_search_value(oneshot_search(f"{m_key} >= {n_key}", numbers))
    )
    require_host_true(
        require_search_value(oneshot_search(f"{n_key} > {m_key}", numbers))
    )
    require_host_false(
        require_search_value(oneshot_search(f"{n_key} <= {m_key}", numbers))
    )

    s1, s2 = compare_ident(), compare_ident()
    low_s, high_s = host_ordered_strings()
    strings = {s1: low_s, s2: high_s}
    require_host_true(require_search_value(oneshot_search(f"{s1} < {s2}", strings)))
    require_host_false(require_search_value(oneshot_search(f"{s2} < {s1}", strings)))
    require_host_true(require_search_value(oneshot_search(f"{s1} <= {s2}", strings)))
    require_host_false(require_search_value(oneshot_search(f"{s1} >= {s2}", strings)))
    require_host_true(require_search_value(oneshot_search(f"{s2} > {s1}", strings)))
    require_host_false(require_search_value(oneshot_search(f"{s2} <= {s1}", strings)))

    f1, f2 = compare_ident(), compare_ident()
    low_f, high_f = host_ordered_floats()
    floats = {f1: low_f, f2: high_f}
    require_host_true(require_search_value(oneshot_search(f"{f1} < {f2}", floats)))
    require_host_true(require_search_value(oneshot_search(f"{f2} > {f1}", floats)))
    require_host_false(require_search_value(oneshot_search(f"{f2} <= {f1}", floats)))

    field = compare_ident()
    kept = host_decimal()
    assert kept >= 1
    frac = 11 + (int.from_bytes(runtime_payload()[:2].encode("ascii"), "little") % 80)
    dropped = Decimal(f"0.{frac:02d}")
    assert dropped < 1
    assert dropped != 0
    document = [{field: kept}, {field: dropped}]
    observed = require_search_value(
        oneshot_search(f"[?{field} >= `1`].{field}", document)
    )
    assert isinstance(observed, list), f"expected a kept array, got {observed!r}"
    assert observed == [kept], f"decimal filter kept {observed!r}, expected {[kept]!r}"
    assert type(observed[0]) is Decimal
    assert dropped not in observed

    # L264 / L278: array / object / boolean / null vs a number or string
    # is successful null, not false. Published emptylist / one / boolvalue
    # spellings can be memorized; process-local keys must still yield null.
    # Number-versus-string is not asserted (the amended PRD leaves that
    # pair without a carrier).
    roles, mixed = runtime_mixed_order_document()
    array_k, obj_k, bool_k, null_k, num_k, str_k = (
        roles["array"],
        roles["object"],
        roles["boolean"],
        roles["null"],
        roles["number"],
        roles["string"],
    )
    require_oneshot_ordering_null(f"{array_k} < {num_k}", mixed)
    require_oneshot_ordering_null(f"{obj_k} < {num_k}", mixed)
    require_oneshot_ordering_null(f"{num_k} < {bool_k}", mixed)
    require_oneshot_ordering_null(f"{null_k} < {num_k}", mixed)
    require_oneshot_ordering_null(f"{num_k} < {null_k}", mixed)
    require_oneshot_ordering_null(f"{array_k} >= {num_k}", mixed)
    require_oneshot_ordering_null(f"{array_k} < {str_k}", mixed)
    absent = compare_ident()
    assert absent not in mixed
    require_oneshot_ordering_null(f"{absent} < {num_k}", mixed)
    print(
        f"runtime_order ints={lesser}/{greater} strings floats decimal={kept!r} "
        "mixed-type-null",
        flush=True,
    )


def test_compile_then_search_ordering():
    require_host_true(compile_once_then_search("one < two", _EQ_DOC))
    require_host_true(compile_once_then_search("two > one", _EQ_DOC))
    require_host_true(compile_once_then_search("a < b", _STRING_DOC))
    parsed_mixed = require_search_value(compile_expression("emptylist < one"))
    require_ordering_null(search_parsed(parsed_mixed, _MIXED_DOC))
    require_ordering_null(search_parsed(parsed_mixed, _MIXED_DOC))

    field = compare_ident()
    kept = host_decimal()
    parsed = require_search_value(compile_expression(f"[?{field} >= `1`].{field}"))
    first = require_search_value(search_parsed(parsed, [{field: kept}]))
    second = require_search_value(search_parsed(parsed, [{field: kept}]))
    assert first == second == [kept]
    assert type(first[0]) is Decimal
    print("compile_ordering < > string mixed decimal", flush=True)


# ---------------------------------------------------------------------------
# C. || returns the first true operand; 0 and 0.0 are true
# ---------------------------------------------------------------------------


def test_or_returns_first_true_operand():
    document = with_sentinel(_OR_DOC)
    first = require_oneshot_equals("outer.foo || outer.bar", document, "foo")
    recovered = require_oneshot_equals("outer.bad || outer.foo", document, "foo")
    both_missing = oneshot_search("outer.bad || outer.alsobad", document)
    require_successful_null(both_missing)
    assert first == "foo"
    assert recovered == "foo"
    assert first == recovered
    assert both_missing.exception is None
    assert both_missing.value is None
    assert first != both_missing.value
    print("or_first_true foo / recovered-foo / both-missing-null", flush=True)


def test_or_spaces_optional():
    document = with_sentinel(_OR_DOC)
    spaced = require_oneshot_equals("outer.foo || outer.bar", document, "foo")
    compact = require_oneshot_equals("outer.foo||outer.bar", document, "foo")
    assert spaced == compact == "foo"
    print("or_spaces compact==spaced", flush=True)


def test_or_skips_false_values_including_zero_as_true():
    skipped = require_oneshot_equals(
        "outer.empty_string || outer.foo", _OR_FALSE_DOC, "foo"
    )
    chained = require_oneshot_equals(
        "outer.nokey || outer.bool || outer.empty_list || "
        "outer.empty_string || outer.foo",
        _OR_FALSE_DOC,
        "foo",
    )
    assert skipped == chained == "foo"
    zero = require_search_value(oneshot_search("Zero || Number", _ZERO_DOC))
    require_int_zero(zero)
    zf = require_search_value(oneshot_search("ZeroFloat || Number", _ZERO_DOC))
    require_float_zero(zf)
    print(f"or_false_skip zero={zero!r} zerofloat={zf!r}", flush=True)


def test_runtime_or_operands_and_empty_object():
    first, second = compare_ident(), compare_ident()
    payload = compare_payload()
    bait = compare_payload()
    assert payload != bait
    taken = require_oneshot_equals(
        f"{first} || {second}", {first: payload, second: bait}, payload
    )
    assert taken == payload
    assert taken != bait

    empty_obj, empty_list, empty_str, none_k, false_k = (
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
    )
    document = {
        empty_obj: {},
        empty_list: [],
        empty_str: "",
        none_k: None,
        false_k: False,
        second: payload,
    }
    from_empty_obj = require_oneshot_equals(
        f"{empty_obj} || {second}", document, payload
    )
    assert from_empty_obj == payload
    assert from_empty_obj != {}
    require_oneshot_equals(f"{empty_list} || {second}", document, payload)
    require_oneshot_equals(f"{empty_str} || {second}", document, payload)
    require_oneshot_equals(f"{none_k} || {second}", document, payload)
    require_oneshot_equals(f"{false_k} || {second}", document, payload)

    # L30 / L267: 0 and 0.0 are true values, not members of the false-value
    # set. A published Zero || Number table can be memorized; process-local
    # keys holding those numbers must still return the number, not the bait.
    zero_k, zf_k = compare_ident(), compare_ident()
    from_zero = require_int_zero(
        require_search_value(
            oneshot_search(f"{zero_k} || {second}", {zero_k: 0, second: payload})
        )
    )
    assert from_zero != payload
    from_zf = require_float_zero(
        require_search_value(
            oneshot_search(f"{zf_k} || {second}", {zf_k: 0.0, second: payload})
        )
    )
    assert from_zf != payload
    print(
        f"runtime_or payload={payload!r} int_zero={from_zero!r} float_zero={from_zf!r}",
        flush=True,
    )


def test_compile_then_search_or():
    compiled_or = compile_once_then_search("outer.foo || outer.bar", _OR_DOC)
    assert compiled_or == "foo"
    zero = compile_once_then_search("Zero || Number", _ZERO_DOC)
    require_int_zero(zero)

    empty_obj, payload_k = compare_ident(), compare_ident()
    payload = compare_payload()
    compiled_empty = compile_once_then_search(
        f"{empty_obj} || {payload_k}", {empty_obj: {}, payload_k: payload}
    )
    assert compiled_empty == payload
    print("compile_or foo / int-zero / empty-object", flush=True)


# ---------------------------------------------------------------------------
# D. && returns the first false operand; 0 and 0.0 are not false
# ---------------------------------------------------------------------------


def test_and_returns_first_false_operand():
    document = with_sentinel(_AND_DOC)
    true_and_false = require_host_false(
        require_search_value(oneshot_search("True && False", document))
    )
    true_and_true = require_host_true(
        require_search_value(oneshot_search("True && True", document))
    )
    true_and_number = require_oneshot_equals("True && Number", document, 5)
    number_and_true = require_host_true(
        require_search_value(oneshot_search("Number && True", document))
    )
    number_and_empty = require_oneshot_equals("Number && EmptyList", document, [])
    empty_and_true = require_oneshot_equals("EmptyList && True", document, [])
    zeros = with_sentinel(_ZERO_DOC)
    zero_and_number = require_oneshot_equals("Zero && Number", zeros, 5)
    zerofloat_and_number = require_oneshot_equals("ZeroFloat && Number", zeros, 5)
    assert true_and_false is False
    assert true_and_true is True
    assert true_and_number == 5
    assert number_and_true is True
    assert number_and_empty == []
    assert empty_and_true == []
    assert zero_and_number == 5
    assert zerofloat_and_number == 5
    assert true_and_number != true_and_false
    assert zero_and_number != 0
    assert zerofloat_and_number != 0.0
    assert empty_and_true != true_and_true
    print("and_operands named plus Zero/ZeroFloat && Number -> 5", flush=True)


def test_runtime_and_operands():
    first, second = compare_ident(), compare_ident()
    payload = compare_payload()
    truthy_int = runtime_int()
    truthy_str = compare_payload()
    require_oneshot_equals(
        f"{first} && {second}", {first: truthy_int, second: payload}, payload
    )
    require_oneshot_equals(
        f"{first} && {second}", {first: truthy_str, second: payload}, payload
    )
    zero_and = require_oneshot_equals(
        f"{first} && {second}", {first: 0, second: payload}, payload
    )
    assert zero_and == payload
    assert zero_and != 0
    zf_and = require_oneshot_equals(
        f"{first} && {second}", {first: 0.0, second: payload}, payload
    )
    assert zf_and == payload
    assert zf_and != 0.0

    empty_obj = require_oneshot_equals(
        f"{first} && {second}", {first: {}, second: payload}, {}
    )
    assert empty_obj == {}
    assert empty_obj != []
    empty_str = require_oneshot_equals(
        f"{first} && {second}", {first: "", second: payload}, ""
    )
    assert empty_str == ""
    assert empty_str != []
    require_oneshot_equals(f"{first} && {second}", {first: [], second: payload}, [])
    require_host_false(
        require_search_value(
            oneshot_search(f"{first} && {second}", {first: False, second: payload})
        )
    )
    require_successful_null(
        oneshot_search(f"{first} && {second}", {first: None, second: payload})
    )
    print(f"runtime_and first-false-kept payload={payload!r}", flush=True)


def test_compile_then_search_and():
    assert compile_once_then_search("True && Number", _AND_DOC) == 5
    assert compile_once_then_search("EmptyList && True", _AND_DOC) == []
    assert compile_once_then_search("Zero && Number", _ZERO_DOC) == 5
    empty, payload_k = compare_ident(), compare_ident()
    compiled = compile_once_then_search(
        f"{empty} && {payload_k}", {empty: {}, payload_k: compare_payload()}
    )
    assert compiled == {}
    assert compiled != []
    print("compile_and Number / EmptyList / Zero / empty-object", flush=True)


# ---------------------------------------------------------------------------
# E. ! inverts truthiness; !Zero is false, !!Zero is true
# ---------------------------------------------------------------------------


def test_not_inverts_truthiness_including_zero():
    document = with_sentinel(_LOGIC_DOC)
    not_true = require_host_false(require_search_value(oneshot_search("!True", document)))
    not_false = require_host_true(require_search_value(oneshot_search("!False", document)))
    not_number = require_host_false(
        require_search_value(oneshot_search("!Number", document))
    )
    not_empty = require_host_true(
        require_search_value(oneshot_search("!EmptyList", document))
    )
    not_zero = require_host_false(require_search_value(oneshot_search("!Zero", document)))
    not_not_zero = require_host_true(
        require_search_value(oneshot_search("!!Zero", document))
    )
    assert not_true is False
    assert not_false is True
    assert not_number is False
    assert not_empty is True
    assert not_zero is False
    assert not_not_zero is True
    assert not_zero is not not_not_zero
    assert not_empty is not not_number
    print("not_truthiness !Zero is false !!Zero is true", flush=True)


def test_runtime_not_false_value_set():
    truthy_k, empty_list, empty_obj, empty_str, zf = (
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
    )
    document = {
        truthy_k: compare_payload(),
        empty_list: [],
        empty_obj: {},
        empty_str: "",
        zf: 0.0,
    }
    not_truthy = require_host_false(
        require_search_value(oneshot_search(f"!{truthy_k}", document))
    )
    not_empty_list = require_host_true(
        require_search_value(oneshot_search(f"!{empty_list}", document))
    )
    not_empty_obj = require_host_true(
        require_search_value(oneshot_search(f"!{empty_obj}", document))
    )
    not_empty_str = require_host_true(
        require_search_value(oneshot_search(f"!{empty_str}", document))
    )
    not_zero_float = require_host_false(
        require_search_value(oneshot_search(f"!{zf}", document))
    )
    assert not_truthy is False
    assert not_empty_list is True
    assert not_empty_obj is True
    assert not_empty_str is True
    assert not_zero_float is False
    assert not_empty_obj is not not_zero_float
    assert not_empty_str is not not_truthy
    print("runtime_not empty-object/string/list and 0.0", flush=True)


def test_compile_then_search_not():
    compiled_not_zero = require_host_false(compile_once_then_search("!Zero", _LOGIC_DOC))
    compiled_not_not_zero = require_host_true(
        compile_once_then_search("!!Zero", _LOGIC_DOC)
    )
    empty = compare_ident()
    compiled_empty = require_host_true(
        compile_once_then_search(f"!{empty}", {empty: {}})
    )
    assert compiled_not_zero is False
    assert compiled_not_not_zero is True
    assert compiled_empty is True
    assert compiled_not_zero is not compiled_not_not_zero
    assert compiled_empty is not compiled_not_zero
    print("compile_not !Zero !!Zero !empty-object", flush=True)


# ---------------------------------------------------------------------------
# F. Parentheses group; && binds tighter than ||
# ---------------------------------------------------------------------------


def test_and_binds_tighter_than_or():
    document = with_sentinel(_BIND_DOC)
    unbound = require_oneshot_equals("Number || True && False", document, 5)
    bound = require_host_false(
        require_search_value(oneshot_search("(Number || True) && False", document))
    )
    assert unbound == 5
    assert bound is False
    assert unbound != bound
    print("binding Number || True && False is 5", flush=True)


def test_parentheses_override_binding():
    document = with_sentinel(_BIND_DOC)
    require_oneshot_equals("Number || (True && False)", document, 5)
    require_host_true(
        require_search_value(oneshot_search("!(True && False)", document))
    )
    grouped = require_search_value(oneshot_search("(Number || True) && False", document))
    require_host_false(grouped)
    ungrouped = require_search_value(oneshot_search("Number || True && False", document))
    assert ungrouped == 5
    assert grouped is not ungrouped
    print("parens override and !(True && False)", flush=True)


def test_comparators_with_and_or():
    document = with_sentinel(_CMP_LOGIC_DOC)
    both = require_host_true(
        require_search_value(oneshot_search("one < two && three > one", document))
    )
    neither = require_host_false(
        require_search_value(oneshot_search("two < one || three < one", document))
    )
    assert both is True
    assert neither is False
    assert both is not neither
    print("comparators_with_logic one<two && three>one", flush=True)


def test_runtime_binding_and_parentheses():
    n_k, t_k, f_k = compare_ident(), compare_ident(), compare_ident()
    n = runtime_int()
    document = {n_k: n, t_k: True, f_k: False}
    unbound = require_search_value(
        oneshot_search(f"{n_k} || {t_k} && {f_k}", document)
    )
    assert unbound == n
    assert unbound is not False
    bound = require_search_value(
        oneshot_search(f"({n_k} || {t_k}) && {f_k}", document)
    )
    require_host_false(bound)
    assert unbound != bound
    print(f"runtime_binding n={n!r} unbound={unbound!r} bound={bound!r}", flush=True)


def test_compile_then_search_binding():
    assert compile_once_then_search("Number || True && False", _BIND_DOC) == 5
    require_host_false(
        compile_once_then_search("(Number || True) && False", _BIND_DOC)
    )
    n_k, t_k, f_k = compare_ident(), compare_ident(), compare_ident()
    n = runtime_int()
    document = {n_k: n, t_k: True, f_k: False}
    parsed_unbound = require_search_value(
        compile_expression(f"{n_k} || {t_k} && {f_k}")
    )
    first = require_search_value(search_parsed(parsed_unbound, document))
    second = require_search_value(search_parsed(parsed_unbound, document))
    assert first == second == n
    parsed_bound = require_search_value(
        compile_expression(f"({n_k} || {t_k}) && {f_k}")
    )
    bound_first = require_search_value(search_parsed(parsed_bound, document))
    bound_second = require_search_value(search_parsed(parsed_bound, document))
    require_host_false(bound_first)
    require_host_false(bound_second)
    print("compile_binding public and runtime parens", flush=True)


# ---------------------------------------------------------------------------
# G. Lone =, lone &, dangling || do not succeed
# ---------------------------------------------------------------------------


def test_lone_equals_is_syntax_unlike_equality():
    document = with_sentinel(_EQ_DOC)
    require_host_true(require_search_value(oneshot_search("one == one", document)))
    assert_search_syntax_not_empty_or_incomplete("=", document)
    assert_search_is_value_error("one = one", document)
    assert_search_is_value_error("one = two", document)
    print("lone_equals syntax; one = one is value error", flush=True)


def test_single_ampersand_is_not_and_or_expression_reference():
    document = with_sentinel(_AND_DOC)
    require_host_false(require_search_value(oneshot_search("True && False", document)))
    ref = oneshot_search("&foo", document)
    assert ref.exception is None, (
        f"expression reference &foo must succeed; got {ref.exception!r}"
    )
    assert ref.value is not document
    print(f"ampersand_ref_ok type={type(ref.value).__name__}", flush=True)
    assert_search_is_value_error("foo & bar", document)
    print("single_ampersand refused; && and &foo succeed", flush=True)


def test_dangling_or_does_not_succeed():
    document = with_sentinel(_OR_DOC)
    require_oneshot_equals("outer.foo || outer.bar", document, "foo")
    assert_search_is_value_error("foo ||", document)
    print("dangling_or refused; complete || succeeds", flush=True)


def test_runtime_equals_ampersand_and_dangling_or_failures():
    a, b, root, other = (
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
    )
    n = runtime_int()
    payload = compare_payload()
    document = {a: n, b: n, root: payload, other: compare_payload()}
    require_host_true(require_search_value(oneshot_search(f"{a} == {a}", document)))
    assert_search_is_value_error(f"{a} = {a}", document)
    require_host_false(
        require_search_value(
            oneshot_search(f"{a} && {b}", {a: True, b: False, **sentinel_document()})
        )
    )
    ref = oneshot_search(f"&{a}", document)
    assert ref.exception is None, (
        f"runtime expression reference &{a} must succeed; got {ref.exception!r}"
    )
    assert_search_is_value_error(f"{a} & {b}", document)
    require_oneshot_equals(f"{root} || {other}", document, payload)
    assert_search_is_value_error(f"{root} ||", document)
    print("runtime_failures = / & / dangling ||", flush=True)


def test_compile_path_comparator_and_logic_failures():
    document = sentinel_document()
    assert_compile_syntax_not_empty_or_incomplete("=")
    require_unsuccessful_compile_path("one = one", document)
    require_unsuccessful_compile_path("foo & bar", document)
    require_unsuccessful_compile_path("foo ||", document)
    print("compile_path = / one = one / foo & bar / foo ||", flush=True)


# ---------------------------------------------------------------------------
# H. Same operators inside a filter; && still tighter; ! on both entries
# ---------------------------------------------------------------------------


def test_filter_and_keeps_one_mapping():
    observed = require_search_value(
        oneshot_search("foo[?a == `1` && b == `2`]", _FILTER_AND_DOC)
    )
    _require_kept_mappings(observed, [{"a": 1, "b": 2}])
    assert observed != _FILTER_AND_DOC["foo"]
    assert observed != []
    print(f"filter_and kept={observed!r}", flush=True)


def test_filter_or_keeps_both_names():
    observed = require_search_value(
        oneshot_search("foo[?name == 'a' || name == 'b']", _FILTER_OR_DOC)
    )
    _require_kept_mappings(observed, [{"name": "a"}, {"name": "b"}])
    print(f"filter_or kept={observed!r}", flush=True)


def test_filter_and_binds_tighter_than_or_and_not():
    unbound = require_search_value(
        oneshot_search("foo[?a == `1` || b == `2` && c == `5`]", _FILTER_BIND_DOC)
    )
    _require_kept_mappings(unbound, [{"a": 1, "b": 2, "c": 3}])
    paren = oneshot_search(
        "foo[?(a == `1` || b == `2`) && c == `5`]", _FILTER_BIND_DOC
    )
    require_successful_empty_array(paren)
    negated = require_search_value(
        oneshot_search("foo[?!(a == `1` || b == `2`)]", _FILTER_BIND_DOC)
    )
    _require_kept_mappings(negated, [{"a": 3, "b": 4}])
    print(
        f"filter_bind unbound={unbound!r} paren=[] negated={negated!r}",
        flush=True,
    )


def test_runtime_filter_logic_and_parentheses():
    root, f1, f2, f3 = (
        compare_ident(),
        compare_ident(),
        compare_ident(),
        compare_ident(),
    )
    n1, n2 = _distinct_ints()
    n3 = runtime_int()
    while n3 in {n1, n2}:
        n3 = runtime_int()
    threshold = runtime_int()
    while threshold in {n1, n2, n3}:
        threshold = runtime_int()
    hit = {f1: n1, f2: n2}
    miss = {f1: n1, f2: n3}
    document = {root: [hit, miss]}
    kept = require_search_value(
        oneshot_search(
            f"{root}[?{f1} == {json_literal_text(n1)} && "
            f"{f2} == {json_literal_text(n2)}]",
            document,
        )
    )
    _require_kept_mappings(kept, [hit])
    assert miss not in kept

    # L272: a filter || keeps every mapping that matches either side.
    # The published name == 'a' || name == 'b' table can be memorized.
    # Live baseline: the left-hand comparator alone keeps only the
    # left-hand mapping. Adding || right must keep both — an
    # implementation that ignores the second operand of || stays on
    # the left-only set.
    left_val, right_val = _distinct_ints()
    name_f = compare_ident()
    left_hit = {name_f: left_val}
    right_hit = {name_f: right_val}
    or_doc = {root: [left_hit, right_hit]}
    left_only = require_search_value(
        oneshot_search(
            f"{root}[?{name_f} == {json_literal_text(left_val)}]",
            or_doc,
        )
    )
    _require_kept_mappings(left_only, [left_hit])
    assert right_hit not in left_only
    both = require_search_value(
        oneshot_search(
            f"{root}[?{name_f} == {json_literal_text(left_val)} || "
            f"{name_f} == {json_literal_text(right_val)}]",
            or_doc,
        )
    )
    _require_kept_mappings(both, [left_hit, right_hit])
    assert left_hit in both and right_hit in both
    assert both != left_only

    first = {f1: n1, f2: n2, f3: n3}
    other = {f1: n3, f2: n3, f3: n3}
    bind_doc = {root: [first, other]}
    unbound = require_search_value(
        oneshot_search(
            f"{root}[?{f1} == {json_literal_text(n1)} || "
            f"{f2} == {json_literal_text(n2)} && "
            f"{f3} == {json_literal_text(threshold)}]",
            bind_doc,
        )
    )
    _require_kept_mappings(unbound, [first])
    paren = oneshot_search(
        f"{root}[?({f1} == {json_literal_text(n1)} || "
        f"{f2} == {json_literal_text(n2)}) && "
        f"{f3} == {json_literal_text(threshold)}]",
        bind_doc,
    )
    require_successful_empty_array(paren)
    negated = require_search_value(
        oneshot_search(
            f"{root}[?!({f1} == {json_literal_text(n1)} || "
            f"{f2} == {json_literal_text(n2)})]",
            bind_doc,
        )
    )
    _require_kept_mappings(negated, [other])
    assert first not in negated
    print(
        f"runtime_filter and={kept!r} or_both={both!r} "
        f"unbound={unbound!r} negated={negated!r}",
        flush=True,
    )


def test_compile_then_search_filter_logic():
    and_kept = compile_once_then_search(
        "foo[?a == `1` && b == `2`]", _FILTER_AND_DOC
    )
    _require_kept_mappings(and_kept, [{"a": 1, "b": 2}])
    unbound = compile_once_then_search(
        "foo[?a == `1` || b == `2` && c == `5`]", _FILTER_BIND_DOC
    )
    _require_kept_mappings(unbound, [{"a": 1, "b": 2, "c": 3}])
    parsed_paren = require_search_value(
        compile_expression("foo[?(a == `1` || b == `2`) && c == `5`]")
    )
    first_paren = search_parsed(parsed_paren, _FILTER_BIND_DOC)
    second_paren = search_parsed(parsed_paren, _FILTER_BIND_DOC)
    require_successful_empty_array(first_paren)
    require_successful_empty_array(second_paren)
    negated = compile_once_then_search(
        "foo[?!(a == `1` || b == `2`)]", _FILTER_BIND_DOC
    )
    _require_kept_mappings(negated, [{"a": 3, "b": 4}])

    root, f1, f2 = compare_ident(), compare_ident(), compare_ident()
    n1, n2 = _distinct_ints()
    hit = {f1: n1, f2: n2}
    miss = {f1: n1, f2: runtime_int()}
    document = {root: [hit, miss]}
    parsed = require_search_value(
        compile_expression(
            f"{root}[?{f1} == {json_literal_text(n1)} && "
            f"{f2} == {json_literal_text(n2)}]"
        )
    )
    first = require_search_value(search_parsed(parsed, document))
    second = require_search_value(search_parsed(parsed, document))
    assert first == second
    _require_kept_mappings(first, [hit])
    print("compile_filter && / unbound ||&& / paren [] / ! / runtime &&", flush=True)
