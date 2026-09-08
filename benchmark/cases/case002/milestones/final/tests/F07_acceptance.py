# feature: F07
"""FP-07: call the finite set of built-in functions.

Assertions follow Full_PRD.original.md FP-07 (L287–L339) together with
the two public entries (L19–L21 / L50), the six JSON types and host
current values (L26 / L61), expression references consumed by map /
sort_by / min_by / max_by (L29 / L240), the finite false-value set
(L30), projections dropping null (L32–L33), value-error failures
without graded wording (L63), and no write-back (L82). Custom
functions and evaluation options are FP-08.
"""

from __future__ import annotations

import math
import uuid

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F01_helpers import (
    assert_search_is_value_error,
    oneshot_search,
    require_search_value,
    require_successful_null,
    sentinel_document,
)
from F02_helpers import (
    assert_compile_syntax_not_empty_or_incomplete,
    assert_search_syntax_not_empty_or_incomplete,
    compile_once_then_search,
)
from F03_helpers import (
    assert_kind_stems_differ,
    require_oneshot_equals,
    require_successful_empty_array,
)
from F04_helpers import json_literal_text, require_unsuccessful_compile_path
from F06_helpers import host_decimal, require_host_false, require_host_true, with_sentinel
from F07_helpers import (
    assert_three_function_kinds_distinct,
    compact_json_text,
    fn_float,
    fn_ident,
    fn_int,
    fn_ordered_floats,
    fn_ordered_strings,
    fn_payload,
    function_kind_texts,
    host_non_json_value,
    host_ordinary_text,
    require_document_field_unchanged,
)
from _harness import HarnessError

UNKNOWN_EXPR = "unknown_function(`1`, `2`)"
ARITY_EXPR = "abs()"
TYPE_EXPR = "abs(str)"
QUOTED_EXPR = '"to_string"(`1.0`)'


def _twelve() -> dict:
    return {
        "foo": -1,
        "zero": 0,
        "numbers": [-1, 3, 4, 5],
        "array": [-1, 3, 4, 5, "a", "100"],
        "strings": ["a", "b", "c"],
        "decimals": [1.01, 1.2, -1.5],
        "str": "Str",
        "false": False,
        "empty_list": [],
        "empty_hash": {},
        "objects": {"foo": "bar", "bar": "baz"},
        "null_key": None,
    }


def _map_people() -> dict:
    return {
        "people": [
            {"a": 10, "b": 1, "c": "z"},
            {"a": 10, "b": 2, "c": None},
            {"a": 10, "b": 3},
            {"a": 10, "b": 4, "c": "z"},
            {"a": 10, "b": 5, "c": None},
            {"a": 10, "b": 6},
            {"a": 10, "b": 7, "c": "z"},
            {"a": 10, "b": 8, "c": None},
            {"a": 10, "b": 9},
        ],
        "empty": [],
    }


def _age_people() -> dict:
    return {
        "people": [
            {"age": 20, "name": "a", "bool": True, "extra": "foo"},
            {"age": 40, "name": "b", "bool": False, "extra": "bar"},
            {"age": 30, "name": "c", "bool": True},
            {"age": 50, "name": "d", "bool": False},
            {"age": 10, "name": 3, "bool": True},
        ]
    }


def _stable_people() -> dict:
    return {"people": [{"age": 10, "order": str(i)} for i in range(1, 12)]}


def _nested_bar_array() -> dict:
    return {
        "array": [
            {"foo": {"bar": "yes1"}},
            {"foo": {"bar": "yes2"}},
            {},
        ]
    }


def _flatten_array() -> dict:
    return {"array": [[1, 2, 3, [4]], [5, 6, 7, [8, 9]]]}


def _require_unary_none_array(value: object) -> list:
    if not isinstance(value, list):
        raise HarnessError(
            f"expected a one-element array holding none, got {type(value).__name__} {value!r}"
        )
    assert len(value) == 1, f"expected length 1, got {value!r}"
    assert value[0] is None, f"expected the sole element to be host none, got {value!r}"
    assert value != [], "unary none array must not be []"
    return value


def _require_zero_not_null(value: object) -> object:
    assert value == 0, f"expected 0, got {value!r}"
    assert value is not None, "0 must not be successful null"
    return value


def _interior_haystack() -> tuple[str, str]:
    left, needle, right = fn_payload(), fn_payload(), fn_payload()
    haystack = left + needle + right
    if haystack.startswith(needle):
        raise HarnessError(f"interior needle is a prefix of {haystack!r}")
    if haystack.endswith(needle):
        raise HarnessError(f"interior needle is a suffix of {haystack!r}")
    if haystack == needle:
        raise HarnessError("interior needle equals the whole haystack")
    if needle not in haystack:
        raise HarnessError(f"needle {needle!r} is not in {haystack!r}")
    return haystack, needle


def _runtime_scientific() -> tuple[str, float]:
    coeff = 2 + (int(uuid.uuid4().hex[:2], 16) % 7)
    exp = 12 + (int(uuid.uuid4().hex[:2], 16) % 8)
    text = f"{coeff}e{exp}"
    if text == "1e21":
        raise HarnessError("runtime scientific string collided with public 1e21")
    value = float(text)
    if value is None:
        raise HarnessError(f"runtime scientific {text!r} parsed as none")
    print(f"runtime_scientific text={text!r} value={value!r}", flush=True)
    return text, value


def _flatten_one(sequence: object) -> list:
    if not isinstance(sequence, list):
        raise HarnessError(f"flatten-one requires a list, got {type(sequence)!r}")
    out: list = []
    for item in sequence:
        if isinstance(item, list):
            out.extend(item)
        else:
            out.append(item)
    return out


def _kind_texts(*extra: str) -> tuple[str, ...]:
    return function_kind_texts(
        UNKNOWN_EXPR,
        ARITY_EXPR,
        TYPE_EXPR,
        "unknown_function",
        "abs",
        *extra,
    )


def _representatives(document: dict) -> tuple[BaseException, BaseException, BaseException]:
    unknown = assert_search_is_value_error(UNKNOWN_EXPR, document)
    arity = assert_search_is_value_error(ARITY_EXPR, document)
    typed = assert_search_is_value_error(TYPE_EXPR, document)
    return unknown, arity, typed


def _refuse_named(expression: str, document: dict, *names: str) -> ValueError:
    baited = with_sentinel(document)
    exc = assert_search_is_value_error(expression, baited)
    return exc


# ---------------------------------------------------------------------------
# A. abs / avg / ceil / floor / sum
# ---------------------------------------------------------------------------


def test_abs_avg_ceil_floor_sum_named_oracles():
    document = with_sentinel(_twelve())
    abs_foo = require_oneshot_equals("abs(foo)", document, 1)
    abs_lit = require_oneshot_equals("abs(`-24`)", document, 24)
    abs_zero = require_oneshot_equals("abs(zero)", document, 0)
    avg_nums = require_oneshot_equals("avg(numbers)", document, 2.75)
    ceil_pos = require_oneshot_equals("ceil(`1.2`)", document, 2)
    ceil_neg = require_oneshot_equals("ceil(`-1.5`)", document, -1)
    ceil_foo = require_oneshot_equals("ceil(foo)", document, -1)
    ceil_zero = require_oneshot_equals("ceil(zero)", document, 0)
    floor_pos = require_oneshot_equals("floor(`1.2`)", document, 1)
    floor_foo = require_oneshot_equals("floor(foo)", document, -1)
    sum_nums = require_oneshot_equals("sum(numbers)", document, 11)
    sum_proj = require_oneshot_equals("sum(array[].to_number(@))", document, 111)
    assert abs_foo == 1
    assert abs_lit == 24
    assert abs_zero == 0
    assert avg_nums == 2.75
    assert ceil_pos == 2
    assert ceil_neg == -1
    assert ceil_foo == -1
    assert ceil_zero == 0
    assert floor_pos == 1
    assert floor_foo == -1
    assert sum_nums == 11
    assert sum_proj == 111
    print("named abs/avg/ceil/floor/sum", flush=True)


def test_avg_empty_list_is_successful_null_and_sum_empty_is_zero():
    document = with_sentinel(_twelve())
    require_successful_null(oneshot_search("avg(empty_list)", document))
    empty_sum = require_search_value(oneshot_search("sum(`[]`)", document))
    _require_zero_not_null(empty_sum)
    print("avg([]) is successful null; sum([]) is 0", flush=True)


def test_runtime_numeric_builtins():
    negative = fn_int(negative=True)
    positive = fn_int(positive=True)
    floating = fn_float()
    unit = fn_float(in_open_neg_unit=True)
    a = fn_int(positive=True)
    b = fn_int(positive=True)
    while b == a:
        b = fn_int(positive=True)
    f_neg, f_pos, f_float, f_unit, f_pair, f_empty, f_int = (
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
    )
    document = {
        f_neg: negative,
        f_pos: positive,
        f_float: floating,
        f_unit: unit,
        f_pair: [a, b],
        f_empty: [],
        f_int: a,
    }
    require_oneshot_equals(f"abs({f_neg})", document, abs(negative))
    require_oneshot_equals(f"abs({f_pos})", document, positive)
    require_oneshot_equals(f"abs({f_float})", document, abs(floating))
    require_oneshot_equals(f"avg({f_pair})", document, (a + b) / 2)
    require_oneshot_equals(f"ceil({f_float})", document, math.ceil(floating))
    require_oneshot_equals(f"ceil({f_int})", document, a)
    floor_unit = require_search_value(oneshot_search(f"floor({f_unit})", document))
    assert floor_unit == math.floor(unit), f"floor({unit!r}) yielded {floor_unit!r}"
    assert floor_unit != math.trunc(unit), "floor must not truncate toward zero"
    require_oneshot_equals(f"sum({f_pair})", document, a + b)
    empty_sum = require_search_value(oneshot_search(f"sum({f_empty})", document))
    _require_zero_not_null(empty_sum)
    require_successful_null(oneshot_search(f"avg({f_empty})", document))
    print("runtime numeric abs/avg/ceil/floor/sum", flush=True)


def test_compile_then_search_numeric_builtins():
    document = with_sentinel(_twelve())
    assert compile_once_then_search("abs(foo)", document) == 1
    assert compile_once_then_search("avg(empty_list)", document) is None
    _require_zero_not_null(compile_once_then_search("sum(`[]`)", document))
    positive = fn_int(positive=True)
    field = fn_ident()
    assert compile_once_then_search(f"abs({field})", {field: positive}) == positive
    unit = fn_float(in_open_neg_unit=True)
    unit_field = fn_ident()
    assert compile_once_then_search(
        f"floor({unit_field})", {unit_field: unit}
    ) == math.floor(unit)
    print("compile numeric abs/avg/sum/floor", flush=True)


# ---------------------------------------------------------------------------
# B. contains / starts_with / ends_with / length / reverse / join
# ---------------------------------------------------------------------------


def test_contains_starts_with_ends_with_named_oracles():
    document = with_sentinel(_twelve())
    contains_a = require_host_true(
        require_search_value(oneshot_search("contains('abc', 'a')", document))
    )
    contains_d = require_host_false(
        require_search_value(oneshot_search("contains('abc', 'd')", document))
    )
    contains_str = require_host_true(
        require_search_value(oneshot_search("contains(strings, 'a')", document))
    )
    contains_dec = require_host_true(
        require_search_value(oneshot_search("contains(decimals, `1.2`)", document))
    )
    contains_false = require_host_false(
        require_search_value(oneshot_search("contains(decimals, `false`)", document))
    )
    ends_r = require_host_true(
        require_search_value(oneshot_search("ends_with(str, 'r')", document))
    )
    ends_sstr = require_host_false(
        require_search_value(oneshot_search("ends_with(str, 'SStr')", document))
    )
    starts_s = require_host_true(
        require_search_value(oneshot_search("starts_with(str, 'S')", document))
    )
    starts_long = require_host_false(
        require_search_value(oneshot_search("starts_with(str, 'String')", document))
    )
    assert contains_a is True
    assert contains_d is False
    assert contains_str is True
    assert contains_dec is True
    assert contains_false is False
    assert ends_r is True
    assert ends_sstr is False
    assert starts_s is True
    assert starts_long is False
    print("named contains/starts_with/ends_with", flush=True)


def test_length_counts_characters_elements_and_keys():
    document = with_sentinel(_twelve())
    require_oneshot_equals("length('abc')", document, 3)
    check = require_search_value(oneshot_search("length('✓foo')", document))
    assert check == 4, f"length('✓foo') yielded {check!r}, expected 4"
    assert check != 6, "length('✓foo') must not be UTF-8 byte length 6"
    assert check != 3, "length('✓foo') must not drop the check mark"
    require_oneshot_equals("length('')", document, 0)
    require_oneshot_equals("length(array)", document, 6)
    require_oneshot_equals("length(objects)", document, 2)
    twelve = _twelve()
    assert len(twelve) == 12, f"twelve-key document has {len(twelve)} keys"
    require_oneshot_equals("length(@)", twelve, 12)
    print("named length characters/elements/keys", flush=True)


def test_reverse_and_join_named_oracles():
    document = with_sentinel(_twelve())
    before_numbers = list(document["numbers"])
    reversed_nums = require_oneshot_equals("reverse(numbers)", document, [5, 4, 3, -1])
    after_numbers = require_document_field_unchanged(document, "numbers", before_numbers)
    reversed_text = require_oneshot_equals("reverse('hello world')", document, "dlrow olleh")
    reversed_empty = require_successful_empty_array(oneshot_search("reverse(`[]`)", document))
    reversed_blank = require_oneshot_equals("reverse('')", document, "")
    joined_space = require_oneshot_equals("join(', ', strings)", document, "a, b, c")
    joined_comma = require_oneshot_equals("join(',', `[\"a\", \"b\"]`)", document, "a,b")
    joined_empty = require_oneshot_equals("join('|', empty_list)", document, "")
    joined_proj = require_oneshot_equals(
        "join('|', decimals[].to_string(@))", document, "1.01|1.2|-1.5"
    )
    assert reversed_nums == [5, 4, 3, -1]
    assert after_numbers == before_numbers
    assert reversed_text == "dlrow olleh"
    assert reversed_empty == []
    assert reversed_blank == ""
    assert joined_space == "a, b, c"
    assert joined_comma == "a,b"
    assert joined_empty == ""
    assert joined_proj == "1.01|1.2|-1.5"
    print("named reverse/join", flush=True)


def test_runtime_string_and_array_builtins():
    haystack, needle = _interior_haystack()
    decoy = fn_payload()
    member = fn_payload()
    absent = fn_payload()
    while absent in {decoy, member}:
        absent = fn_payload()
    ascii_part = fn_payload()
    unicode_text = "λ" + ascii_part
    if "✓" in unicode_text:
        raise HarnessError("runtime unicode length reused public ✓foo")
    k1, k2 = fn_ident(), fn_ident()
    v1, v2 = fn_payload(), fn_payload()
    items = [fn_int(positive=True), fn_int(negative=True), fn_int(positive=True)]
    text = fn_payload()
    sep = fn_payload()
    parts = [fn_payload(), fn_payload()]
    (
        f_hay,
        f_arr,
        f_uni,
        f_obj,
        f_seq,
        f_text,
        f_join,
    ) = (
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
    )
    document = {
        f_hay: haystack,
        f_arr: [decoy, member],
        f_uni: unicode_text,
        f_obj: {k1: v1, k2: v2},
        f_seq: list(items),
        f_text: text,
        f_join: list(parts),
    }
    has_needle = require_host_true(
        require_search_value(
            oneshot_search(f"contains({f_hay}, {json_literal_text(needle)})", document)
        )
    )
    has_member = require_host_true(
        require_search_value(
            oneshot_search(f"contains({f_arr}, {json_literal_text(member)})", document)
        )
    )
    has_absent = require_host_false(
        require_search_value(
            oneshot_search(f"contains({f_arr}, {json_literal_text(absent)})", document)
        )
    )
    starts_interior = require_host_false(
        require_search_value(
            oneshot_search(f"starts_with({f_hay}, {json_literal_text(needle)})", document)
        )
    )
    ends_interior = require_host_false(
        require_search_value(
            oneshot_search(f"ends_with({f_hay}, {json_literal_text(needle)})", document)
        )
    )
    uni_len = require_oneshot_equals(f"length({f_uni})", document, len(unicode_text))
    obj_len = require_oneshot_equals(f"length({f_obj})", document, 2)
    arr_len = require_oneshot_equals(f"length({f_arr})", document, 2)
    joined = require_oneshot_equals(
        f"join({json_literal_text(sep)}, {f_join})", document, sep.join(parts)
    )
    before_seq = list(items)
    reversed_seq = require_oneshot_equals(
        f"reverse({f_seq})", document, list(reversed(items))
    )
    after_seq = require_document_field_unchanged(document, f_seq, before_seq)
    before_text = text
    reversed_text = require_oneshot_equals(f"reverse({f_text})", document, text[::-1])
    after_text = require_document_field_unchanged(document, f_text, before_text)
    assert has_needle is True
    assert has_member is True
    assert has_absent is False
    assert starts_interior is False
    assert ends_interior is False
    assert uni_len == len(unicode_text)
    assert obj_len == 2
    assert arr_len == 2
    assert joined == sep.join(parts)
    assert reversed_seq == list(reversed(items))
    assert after_seq == before_seq
    assert reversed_text == text[::-1]
    assert after_text == before_text
    print("runtime contains/length/join/reverse", flush=True)


def test_compile_then_search_string_and_array_builtins():
    document = with_sentinel(_twelve())
    assert compile_once_then_search("length('✓foo')", document) == 4
    assert compile_once_then_search("join(', ', strings)", document) == "a, b, c"
    require_host_true(compile_once_then_search("contains('abc', 'a')", document))
    haystack, needle = _interior_haystack()
    field = fn_ident()
    require_host_true(
        compile_once_then_search(
            f"contains({field}, {json_literal_text(needle)})", {field: haystack}
        )
    )
    k1, k2 = fn_ident(), fn_ident()
    obj_field = fn_ident()
    assert compile_once_then_search(
        f"length({obj_field})", {obj_field: {k1: fn_payload(), k2: fn_payload()}}
    ) == 2
    print("compile length/join/contains", flush=True)


# ---------------------------------------------------------------------------
# C. keys / values / type / to_array / to_string / to_number
# ---------------------------------------------------------------------------


def test_keys_values_and_type_named_oracles():
    document = with_sentinel(_twelve())
    empty_keys = require_successful_empty_array(oneshot_search("keys(empty_hash)", document))
    object_keys = require_oneshot_equals("sort(keys(objects))", document, ["bar", "foo"])
    object_values = require_oneshot_equals(
        "sort(values(objects))", document, ["bar", "baz"]
    )
    type_str = require_oneshot_equals("type('abc')", document, "string")
    type_float = require_oneshot_equals("type(`1.0`)", document, "number")
    type_int = require_oneshot_equals("type(`2`)", document, "number")
    type_true = require_oneshot_equals("type(`true`)", document, "boolean")
    type_false = require_oneshot_equals("type(`false`)", document, "boolean")
    type_null = require_oneshot_equals("type(`null`)", document, "null")
    type_arr = require_oneshot_equals("type(`[0]`)", document, "array")
    type_obj = require_oneshot_equals("type(`{\"a\": \"b\"}`)", document, "object")
    assert empty_keys == []
    assert object_keys == ["bar", "foo"]
    assert object_values == ["bar", "baz"]
    assert type_str == "string"
    assert type_float == "number"
    assert type_int == "number"
    assert type_true == "boolean"
    assert type_false == "boolean"
    assert type_null == "null"
    assert type_arr == "array"
    assert type_obj == "object"
    print("named keys/values/type", flush=True)


def test_to_array_to_string_to_number_named_oracles():
    document = with_sentinel(_twelve())
    require_oneshot_equals("to_array('foo')", document, ["foo"])
    require_oneshot_equals("to_array(`[1, 2, 3]`)", document, [1, 2, 3])
    wrapped_false = require_search_value(oneshot_search("to_array(false)", document))
    assert wrapped_false == [False], f"to_array(false) yielded {wrapped_false!r}"
    require_host_false(wrapped_false[0])
    _require_unary_none_array(require_search_value(oneshot_search("to_array(`null`)", document)))
    _require_unary_none_array(require_search_value(oneshot_search("to_array(null_key)", document)))
    require_oneshot_equals("to_string(`1.2`)", document, "1.2")
    compact = require_search_value(oneshot_search("to_string(`[0, 1]`)", document))
    assert compact == "[0,1]", f"to_string(`[0, 1]`) yielded {compact!r}"
    assert compact != "[0, 1]", "compact JSON must not include extra spaces"
    require_oneshot_equals("to_string(`true`)", document, "true")
    require_oneshot_equals("to_string(`null`)", document, "null")
    require_oneshot_equals("to_string(null_key)", document, "null")
    four = require_search_value(oneshot_search("to_number('4')", document))
    assert four == 4 and type(four) is int, f"to_number('4') yielded {four!r}"
    require_oneshot_equals("to_number('1.1')", document, 1.1)
    sci = require_search_value(oneshot_search("to_number('1e21')", document))
    assert sci == 1e21, f"to_number('1e21') yielded {sci!r}"
    assert sci is not None, "to_number('1e21') must not be null"
    print("named to_array/to_string/to_number", flush=True)


def test_to_number_null_cases_are_successful_null():
    document = with_sentinel(_twelve())
    expressions = (
        "to_number('notanumber')",
        "to_number(`false`)",
        "to_number(`null`)",
        "to_number(`[0]`)",
        "to_number(`{\"foo\": 0}`)",
    )
    seen = 0
    for expression in expressions:
        result = oneshot_search(expression, document)
        require_successful_null(result)
        assert result.exception is None, (
            f"{expression!r} must succeed as null; "
            f"got {type(result.exception).__name__}: {result.exception!r}"
        )
        assert result.value is None, (
            f"{expression!r} yielded {result.value!r}, expected successful null"
        )
        seen += 1
    assert seen == 5
    print("to_number null cases are successful null", flush=True)


def test_zero_equals_false_inside_function_argument_is_false():
    document = with_sentinel(_twelve())
    named = require_search_value(oneshot_search("to_array(`0` == `false`)", document))
    assert named == [False], f"to_array(`0` == `false`) yielded {named!r}"
    require_host_false(named[0])
    z, f = fn_ident(), fn_ident()
    runtime = require_search_value(oneshot_search(f"to_array({z} == {f})", {z: 0, f: False}))
    assert runtime == [False], f"runtime 0==false inside to_array yielded {runtime!r}"
    require_host_false(runtime[0])
    print("0 == false inside a function argument is false", flush=True)


def test_runtime_conversion_builtins():
    root, k1, k2 = fn_ident(), fn_ident(), fn_ident()
    v1, v2 = fn_payload(), fn_payload()
    payload = fn_payload()
    n = fn_int(positive=True)
    frac_whole = fn_int(positive=True)
    frac = 13 + (int(uuid.uuid4().hex[:2], 16) % 80)
    frac_text = f"{frac_whole}.{frac}"
    sci_text, sci_value = _runtime_scientific()
    non_number = fn_payload()
    f_str, f_num, f_bool, f_arr, f_obj, f_null, f_wrap, f_ident, f_sci = (
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
        fn_ident(),
    )
    obj = {k1: v1, k2: v2}
    arr = [payload, n]
    document = {
        root: obj,
        f_str: payload,
        f_num: n,
        f_bool: True,
        f_arr: list(arr),
        f_obj: dict(obj),
        f_null: None,
        f_wrap: payload,
        f_ident: list(arr),
        f_sci: n,
    }
    require_oneshot_equals(f"sort(keys({root}))", document, sorted([k1, k2]))
    require_oneshot_equals(f"sort(values({root}))", document, sorted([v1, v2]))
    require_oneshot_equals(f"type({f_str})", document, "string")
    require_oneshot_equals(f"type({f_num})", document, "number")
    require_oneshot_equals(f"type({f_bool})", document, "boolean")
    require_oneshot_equals(f"type({f_arr})", document, "array")
    require_oneshot_equals(f"type({f_obj})", document, "object")
    require_oneshot_equals(f"type({f_null})", document, "null")
    require_oneshot_equals(f"to_array({f_wrap})", document, [payload])
    require_oneshot_equals(f"to_array({f_ident})", document, arr)
    _require_unary_none_array(
        require_search_value(oneshot_search(f"to_array({f_null})", document))
    )
    require_oneshot_equals(f"to_string({f_str})", document, payload)
    require_oneshot_equals(f"to_string({f_arr})", document, compact_json_text(arr))
    require_oneshot_equals(f"to_string({f_obj})", document, compact_json_text(obj))
    as_number = require_search_value(oneshot_search(f"to_number({f_num})", document))
    assert as_number == n and as_number is not None
    int_from_text = require_search_value(
        oneshot_search(f"to_number('{n}')", sentinel_document())
    )
    assert int_from_text == n and type(int_from_text) is int
    require_oneshot_equals(
        f"to_number('{frac_text}')", sentinel_document(), float(frac_text)
    )
    require_oneshot_equals(f"to_number('{sci_text}')", sentinel_document(), sci_value)
    require_successful_null(oneshot_search(f"to_number('{non_number}')", sentinel_document()))
    print("runtime keys/type/to_array/to_string/to_number", flush=True)


def test_compile_then_search_conversion_builtins():
    document = with_sentinel(_twelve())
    assert compile_once_then_search("type(`true`)", document) == "boolean"
    assert compile_once_then_search("to_string(`[0, 1]`)", document) == "[0,1]"
    assert compile_once_then_search("to_string(`true`)", document) == "true"
    assert compile_once_then_search("to_number('1e21')", document) == 1e21
    assert compile_once_then_search("to_number('notanumber')", document) is None
    n = fn_int(positive=True)
    field = fn_ident()
    assert compile_once_then_search(f"to_number({field})", {field: n}) == n
    k, v = fn_ident(), fn_payload()
    obj_field = fn_ident()
    obj = {k: v}
    assert compile_once_then_search(
        f"to_string({obj_field})", {obj_field: obj}
    ) == compact_json_text(obj)
    _require_unary_none_array(compile_once_then_search("to_array(`null`)", document))
    print("compile type/to_string/to_number/to_array", flush=True)


# ---------------------------------------------------------------------------
# D. max / min / sort
# ---------------------------------------------------------------------------


def test_max_min_sort_named_oracles():
    document = with_sentinel(_twelve())
    max_nums = require_oneshot_equals("max(numbers)", document, 5)
    max_decs = require_oneshot_equals("max(decimals)", document, 1.2)
    max_strs = require_oneshot_equals("max(strings)", document, "c")
    min_nums = require_oneshot_equals("min(numbers)", document, -1)
    min_strs = require_oneshot_equals("min(strings)", document, "a")
    before = list(document["numbers"])
    sorted_nums = require_oneshot_equals("sort(numbers)", document, [-1, 3, 4, 5])
    after = require_document_field_unchanged(document, "numbers", before)
    sorted_strs = require_oneshot_equals("sort(strings)", document, ["a", "b", "c"])
    sorted_decs = require_oneshot_equals("sort(decimals)", document, [-1.5, 1.01, 1.2])
    assert max_nums == 5
    assert max_decs == 1.2
    assert max_strs == "c"
    assert min_nums == -1
    assert min_strs == "a"
    assert sorted_nums == [-1, 3, 4, 5]
    assert after == before
    assert sorted_strs == ["a", "b", "c"]
    assert sorted_decs == [-1.5, 1.01, 1.2]
    print("named max/min/sort", flush=True)


def test_empty_list_max_min_null_and_sort_empty_array():
    document = with_sentinel(_twelve())
    max_empty = oneshot_search("max(empty_list)", document)
    require_successful_null(max_empty)
    min_empty = oneshot_search("min(empty_list)", document)
    require_successful_null(min_empty)
    sorted_empty = require_successful_empty_array(
        oneshot_search("sort(empty_list)", document)
    )
    assert max_empty.exception is None
    assert max_empty.value is None
    assert min_empty.exception is None
    assert min_empty.value is None
    assert sorted_empty == []
    print("empty-list max/min null; sort is []", flush=True)


def test_runtime_max_min_sort():
    lesser_f, greater_f = fn_ordered_floats()
    mid = fn_int(positive=True)
    nums = [greater_f, lesser_f, float(mid)]
    f_nums = fn_ident()
    document = {f_nums: list(nums)}
    before = list(nums)
    max_nums = require_oneshot_equals(f"max({f_nums})", document, max(nums))
    min_nums = require_oneshot_equals(f"min({f_nums})", document, min(nums))
    sorted_nums = require_oneshot_equals(f"sort({f_nums})", document, sorted(nums))
    after = require_document_field_unchanged(document, f_nums, before)
    lesser_s, greater_s = fn_ordered_strings()
    f_str = fn_ident()
    strings = [greater_s, lesser_s]
    max_str = require_oneshot_equals(f"max({f_str})", {f_str: strings}, greater_s)
    min_str = require_oneshot_equals(f"min({f_str})", {f_str: strings}, lesser_s)
    sorted_str = require_oneshot_equals(
        f"sort({f_str})", {f_str: strings}, [lesser_s, greater_s]
    )
    empty = fn_ident()
    empty_doc = {empty: []}
    max_empty = oneshot_search(f"max({empty})", empty_doc)
    require_successful_null(max_empty)
    min_empty = oneshot_search(f"min({empty})", empty_doc)
    require_successful_null(min_empty)
    sorted_empty = require_successful_empty_array(
        oneshot_search(f"sort({empty})", empty_doc)
    )
    assert max_nums == max(nums)
    assert min_nums == min(nums)
    assert sorted_nums == sorted(nums)
    assert after == before
    assert max_str == greater_s
    assert min_str == lesser_s
    assert sorted_str == [lesser_s, greater_s]
    assert max_empty.exception is None
    assert max_empty.value is None
    assert min_empty.exception is None
    assert min_empty.value is None
    assert sorted_empty == []
    print("runtime max/min/sort numbers and descending strings", flush=True)


def test_compile_then_search_max_min_sort():
    document = with_sentinel(_twelve())
    assert compile_once_then_search("max(numbers)", document) == 5
    assert compile_once_then_search("min(empty_list)", document) is None
    assert compile_once_then_search("sort(decimals)", document) == [-1.5, 1.01, 1.2]
    lesser, greater = fn_ordered_strings()
    field = fn_ident()
    strings = [greater, lesser]
    assert compile_once_then_search(f"max({field})", {field: strings}) == greater
    assert compile_once_then_search(f"min({field})", {field: strings}) == lesser
    print("compile max/min/sort", flush=True)


# ---------------------------------------------------------------------------
# E. merge / not_null
# ---------------------------------------------------------------------------


def test_merge_later_key_wins():
    document = with_sentinel(_twelve())
    two_keys = require_oneshot_equals(
        'merge(`{"a": 1}`, `{"b": 2}`)', document, {"a": 1, "b": 2}
    )
    later_wins = require_oneshot_equals(
        'merge(`{"a": 1}`, `{"a": 2}`)', document, {"a": 2}
    )
    empty = require_oneshot_equals("merge(`{}`)", document, {})
    three = require_oneshot_equals(
        'merge(`{"a": 1}`, `{"b": 2}`, `{"a": 3}`)', document, {"a": 3, "b": 2}
    )
    assert two_keys == {"a": 1, "b": 2}
    assert later_wins == {"a": 2}
    assert empty == {}
    assert three == {"a": 3, "b": 2}
    print("named merge later key wins", flush=True)


def test_not_null_first_non_null_empty_list_is_not_null():
    document = with_sentinel(_twelve())
    require_oneshot_equals("not_null(unknown_key, str)", document, "Str")
    require_oneshot_equals(
        "not_null(unknown_key, foo.bar, empty_list, str)", document, []
    )
    require_successful_null(oneshot_search("not_null(all, expressions, are_null)", document))
    require_host_false(
        require_search_value(oneshot_search("not_null(unknown_key, false)", document))
    )
    zero = require_search_value(oneshot_search("not_null(zero)", document))
    assert zero == 0 and zero is not None
    print("named not_null first non-null / [] / false / 0", flush=True)


def test_runtime_merge_and_not_null():
    shared, extra_a, extra_b = fn_ident(), fn_ident(), fn_ident()
    bait, last, va, vb = fn_payload(), fn_payload(), fn_payload(), fn_payload()
    f1, f2, f3 = fn_ident(), fn_ident(), fn_ident()
    obj1 = {shared: bait, extra_a: va}
    obj2 = {extra_b: vb}
    obj3 = {shared: last}
    document = {f1: dict(obj1), f2: dict(obj2), f3: dict(obj3)}
    before = dict(obj1)
    merged = require_search_value(oneshot_search(f"merge({f1}, {f2}, {f3})", document))
    assert merged == {shared: last, extra_a: va, extra_b: vb}, merged
    assert bait not in merged.values()
    require_document_field_unchanged(document, f1, before)
    missing, empty_f, bait_f = fn_ident(), fn_ident(), fn_ident()
    bait_payload = fn_payload()
    not_null_doc = {empty_f: [], bait_f: bait_payload}
    require_oneshot_equals(
        f"not_null({missing}, {empty_f}, {bait_f})", not_null_doc, []
    )
    false_f = fn_ident()
    require_host_false(
        require_search_value(
            oneshot_search(f"not_null({missing}, {false_f})", {false_f: False})
        )
    )
    zero_f = fn_ident()
    zero = require_search_value(
        oneshot_search(f"not_null({missing}, {zero_f})", {zero_f: 0})
    )
    assert zero == 0 and zero is not None
    require_successful_null(
        oneshot_search(f"not_null({fn_ident()}, {fn_ident()})", sentinel_document())
    )
    print("runtime merge three objects / not_null [] false 0", flush=True)


def test_compile_then_search_merge_and_not_null():
    document = with_sentinel(_twelve())
    assert compile_once_then_search('merge(`{"a": 1}`, `{"a": 2}`)', document) == {"a": 2}
    assert compile_once_then_search(
        'merge(`{"a": 1}`, `{"b": 2}`, `{"a": 3}`)', document
    ) == {"a": 3, "b": 2}
    assert compile_once_then_search("not_null(unknown_key, str)", document) == "Str"
    require_host_false(
        compile_once_then_search("not_null(unknown_key, false)", document)
    )
    assert compile_once_then_search("not_null(all, expressions, are_null)", document) is None
    shared, extra = fn_ident(), fn_ident()
    last, other = fn_payload(), fn_payload()
    f1, f2, f3 = fn_ident(), fn_ident(), fn_ident()
    runtime_doc = {
        f1: {shared: fn_payload(), extra: other},
        f2: {extra: other},
        f3: {shared: last},
    }
    assert compile_once_then_search(f"merge({f1}, {f2}, {f3})", runtime_doc)[shared] == last
    print("compile merge/not_null", flush=True)


# ---------------------------------------------------------------------------
# F. map keeps nulls
# ---------------------------------------------------------------------------


def test_map_keeps_nulls_unlike_a_projection():
    document = with_sentinel(_map_people())
    nines = require_search_value(oneshot_search("map(&a, people)", document))
    assert nines == [10, 10, 10, 10, 10, 10, 10, 10, 10], nines
    mapped = require_search_value(oneshot_search("map(&c, people)", document))
    assert mapped == ["z", None, None, "z", None, None, "z", None, None], mapped
    assert len(mapped) == 9
    projected = require_search_value(oneshot_search("people[].c", document))
    assert projected != mapped, "map must not drop nulls the way a projection does"
    assert len(projected) < 9
    assert None not in projected
    require_successful_empty_array(oneshot_search("map(&foo, empty)", document))
    print("map keeps nulls; projection drops them", flush=True)


def test_map_nested_path_and_flatten_reference():
    nested = with_sentinel(_nested_bar_array())
    nested_mapped = require_oneshot_equals(
        "map(&foo.bar, array)", nested, ["yes1", "yes2", None]
    )
    flat = with_sentinel(_flatten_array())
    flattened = require_oneshot_equals(
        "map(&[], array)", flat, [[1, 2, 3, 4], [5, 6, 7, 8, 9]]
    )
    assert nested_mapped == ["yes1", "yes2", None]
    assert flattened == [[1, 2, 3, 4], [5, 6, 7, 8, 9]]
    print("named map nested path and flatten", flush=True)


def test_runtime_map_preserves_length_and_nulls():
    field, nested_f, nested_g, root = fn_ident(), fn_ident(), fn_ident(), fn_ident()
    payload = fn_payload()
    hit = {field: payload}
    miss = {}
    document = {root: [hit, miss, {field: payload}]}
    mapped = require_search_value(oneshot_search(f"map(&{field}, {root})", document))
    assert mapped == [payload, None, payload], mapped
    assert len(mapped) == 3
    nest_hit = {nested_f: {nested_g: payload}}
    nest_miss_g = {nested_f: {}}
    nest_miss_f = {}
    nest_root = fn_ident()
    nest_doc = {nest_root: [nest_hit, nest_miss_g, nest_miss_f]}
    nested = require_search_value(
        oneshot_search(f"map(&{nested_f}.{nested_g}, {nest_root})", nest_doc)
    )
    assert nested == [payload, None, None], nested
    assert len(nested) == 3
    inner_a = [fn_int(positive=True), [fn_int(positive=True), fn_int(negative=True)]]
    inner_b = [fn_payload(), [fn_payload()]]
    flat_root = fn_ident()
    flat_doc = {flat_root: [list(inner_a), list(inner_b)]}
    flattened = require_search_value(oneshot_search(f"map(&[], {flat_root})", flat_doc))
    assert flattened == [_flatten_one(inner_a), _flatten_one(inner_b)], flattened
    print("runtime map length/nulls/nested/flatten", flush=True)


def test_compile_then_search_map():
    document = with_sentinel(_map_people())
    mapped = compile_once_then_search("map(&c, people)", document)
    assert mapped == ["z", None, None, "z", None, None, "z", None, None]
    nested = compile_once_then_search("map(&foo.bar, array)", _nested_bar_array())
    assert nested == ["yes1", "yes2", None]
    field, inner, root = fn_ident(), fn_ident(), fn_ident()
    payload = fn_payload()
    runtime = compile_once_then_search(
        f"map(&{field}.{inner}, {root})",
        {root: [{field: {inner: payload}}, {field: {}}]},
    )
    assert runtime == [payload, None]
    a, b = fn_int(positive=True), fn_int(negative=True)
    flat_root = fn_ident()
    flattened = compile_once_then_search(
        f"map(&[], {flat_root})", {flat_root: [[a, [b]], [[a]]]}
    )
    assert flattened == [[a, b], [a]]
    print("compile map nulls/nested/flatten", flush=True)


# ---------------------------------------------------------------------------
# G. sort_by / max_by / min_by
# ---------------------------------------------------------------------------


def test_sort_by_is_stable_on_equal_keys():
    document = with_sentinel(_stable_people())
    before = [dict(item) for item in document["people"]]
    observed = require_search_value(oneshot_search("sort_by(people, &age)", document))
    assert observed == before, f"stable sort permuted equal keys: {observed!r}"
    require_document_field_unchanged(document, "people", before)
    print("sort_by is stable on eleven equal ages", flush=True)


def test_sort_by_orders_by_age_and_empty_is_empty_array():
    document = with_sentinel(_age_people())
    ordered = require_search_value(oneshot_search("sort_by(people, &age)", document))
    assert [item["age"] for item in ordered] == [10, 20, 30, 40, 50], ordered
    require_oneshot_equals("sort_by(people, &age)[].name", document, [3, "a", "c", "b", "d"])
    require_successful_empty_array(oneshot_search("sort_by(`[]`, &age)", document))
    print("sort_by orders by age; empty is []", flush=True)


def test_max_by_min_by_return_element_or_null_on_empty():
    document = with_sentinel(_age_people())
    greatest = require_search_value(oneshot_search("max_by(people, &age)", document))
    assert greatest["age"] == 50, greatest
    assert greatest == {"age": 50, "name": "d", "bool": False}, greatest
    least = require_search_value(oneshot_search("min_by(people, &age)", document))
    assert least["age"] == 10, least
    assert least["name"] == 3, least
    require_successful_null(oneshot_search("max_by(`[]`, &age)", document))
    require_successful_null(oneshot_search("min_by(`[]`, &age)", document))
    print("max_by/min_by return the element or null on []", flush=True)


def test_runtime_sort_by_max_by_min_by():
    age_k, order_k, root = fn_ident(), fn_ident(), fn_ident()
    shared = fn_int(positive=True)
    orders = [fn_payload() for _ in range(5)]
    assert len(set(orders)) == 5
    people = [{age_k: shared, order_k: item} for item in orders]
    document = {root: [dict(item) for item in people]}
    before = [dict(item) for item in people]
    stable = require_search_value(oneshot_search(f"sort_by({root}, &{age_k})", document))
    assert [item[order_k] for item in stable] == orders, stable
    require_document_field_unchanged(document, root, before)
    used: set[int] = set()
    numeric: list[dict] = []
    for _ in range(4):
        n = fn_int(positive=True)
        while n in used:
            n = fn_int(positive=True)
        used.add(n)
        numeric.append({age_k: n, order_k: fn_payload()})
    num_root = fn_ident()
    num_doc = {num_root: [dict(item) for item in numeric]}
    expected = sorted((dict(item) for item in numeric), key=lambda item: item[age_k])
    ordered = require_search_value(oneshot_search(f"sort_by({num_root}, &{age_k})", num_doc))
    assert ordered == expected, ordered
    greatest = require_search_value(oneshot_search(f"max_by({num_root}, &{age_k})", num_doc))
    least = require_search_value(oneshot_search(f"min_by({num_root}, &{age_k})", num_doc))
    assert greatest == max(numeric, key=lambda item: item[age_k])
    assert least == min(numeric, key=lambda item: item[age_k])
    assert greatest != greatest[age_k]
    assert least != least[age_k]
    lesser, greater = fn_ordered_strings()
    str_k, str_root = fn_ident(), fn_ident()
    first = {str_k: greater, order_k: fn_payload()}
    second = {str_k: lesser, order_k: fn_payload()}
    str_doc = {str_root: [dict(first), dict(second)]}
    str_ordered = require_search_value(
        oneshot_search(f"sort_by({str_root}, &{str_k})", str_doc)
    )
    assert [item[str_k] for item in str_ordered] == [lesser, greater], str_ordered
    empty_root = fn_ident()
    empty_doc = {empty_root: []}
    require_successful_empty_array(
        oneshot_search(f"sort_by({empty_root}, &{age_k})", empty_doc)
    )
    require_successful_null(oneshot_search(f"max_by({empty_root}, &{age_k})", empty_doc))
    require_successful_null(oneshot_search(f"min_by({empty_root}, &{age_k})", empty_doc))
    print("runtime sort_by stable / numeric / string; max_by/min_by element", flush=True)


def test_compile_then_search_by_functions():
    stable = compile_once_then_search("sort_by(people, &age)", _stable_people())
    assert [item["order"] for item in stable] == [str(i) for i in range(1, 12)]
    names = compile_once_then_search("sort_by(people, &age)[].name", _age_people())
    assert names == [3, "a", "c", "b", "d"]
    greatest = compile_once_then_search("max_by(people, &age)", _age_people())
    assert greatest["age"] == 50
    assert compile_once_then_search("min_by(`[]`, &age)", _age_people()) is None
    age_k, order_k, root = fn_ident(), fn_ident(), fn_ident()
    shared = fn_int(positive=True)
    orders = [fn_payload(), fn_payload(), fn_payload(), fn_payload()]
    people = [{age_k: shared, order_k: item} for item in orders]
    compiled = compile_once_then_search(
        f"sort_by({root}, &{age_k})", {root: [dict(item) for item in people]}
    )
    assert [item[order_k] for item in compiled] == orders
    print("compile sort_by/max_by/min_by", flush=True)


# ---------------------------------------------------------------------------
# H. projection feeds a function
# ---------------------------------------------------------------------------


def test_projection_feeds_to_string_and_to_number():
    document = with_sentinel(_twelve())
    require_oneshot_equals("numbers[].to_string(@)", document, ["-1", "3", "4", "5"])
    converted = require_search_value(oneshot_search("array[].to_number(@)", document))
    assert converted == [-1, 3, 4, 5, 100], converted
    assert "a" not in converted
    assert 100 in converted
    assert len(converted) == 5
    assert len(converted) != 6
    print("projection feeds to_string / to_number", flush=True)


def test_runtime_projection_feeds_function():
    root = fn_ident()
    nums = [fn_int(negative=True), fn_int(positive=True), fn_float()]
    document = {root: list(nums)}
    texts = require_search_value(oneshot_search(f"{root}[].to_string(@)", document))
    assert texts == [compact_json_text(item) for item in nums], texts
    assert len(texts) == len(nums)
    n = fn_int(positive=True)
    parsed = fn_int(positive=True)
    while parsed == n:
        parsed = fn_int(positive=True)
    bad = fn_payload()
    mix_root = fn_ident()
    mixed = require_search_value(
        oneshot_search(f"{mix_root}[].to_number(@)", {mix_root: [n, str(parsed), bad]})
    )
    assert n in mixed
    assert parsed in mixed
    assert bad not in mixed
    assert None not in mixed
    assert len(mixed) == 2
    print("runtime projection feeds to_string / mixed to_number", flush=True)


def test_compile_then_search_projection_fed_function():
    document = with_sentinel(_twelve())
    assert compile_once_then_search("array[].to_number(@)", document) == [
        -1,
        3,
        4,
        5,
        100,
    ]
    n = fn_int(positive=True)
    parsed = fn_int(positive=True)
    while parsed == n:
        parsed = fn_int(positive=True)
    bad = fn_payload()
    root = fn_ident()
    compiled = compile_once_then_search(
        f"{root}[].to_number(@)", {root: [n, str(parsed), bad]}
    )
    assert compiled == [n, parsed]
    print("compile projection-fed to_number", flush=True)


# ---------------------------------------------------------------------------
# I. three function-call failure kinds, quoted name, host non-JSON
# ---------------------------------------------------------------------------


def test_unknown_arity_type_failures_are_distinguishable_from_successful_null():
    document = with_sentinel(_twelve())
    unknown, arity, typed = _representatives(document)
    texts = _kind_texts()
    assert_three_function_kinds_distinct(unknown, arity, typed, *texts)
    require_successful_null(oneshot_search("avg(empty_list)", document))
    require_successful_null(oneshot_search("max(empty_list)", document))
    require_successful_null(oneshot_search("to_number('notanumber')", document))
    print("three function kinds distinct from successful null", flush=True)


def test_named_arity_and_type_examples_are_distinct_from_other_kinds():
    twelve = with_sentinel(_twelve())
    people = with_sentinel(_age_people())
    map_doc = with_sentinel(_map_people())
    unknown, arity, typed = _representatives(twelve)
    require_oneshot_equals("abs(foo)", twelve, 1)
    require_oneshot_equals("not_null(str)", twelve, "Str")
    require_search_value(oneshot_search("sort_by(people, &age)", people))
    require_successful_null(oneshot_search("avg(empty_list)", twelve))
    require_host_true(require_search_value(oneshot_search("starts_with(str, 'S')", twelve)))

    arity_rows = (
        ("abs(`1`, `2`)", twelve, ("abs",)),
        ("abs()", twelve, ("abs",)),
        ("length(@, @)", twelve, ("length",)),
        ("not_null()", twelve, ("not_null",)),
        ("sort_by(people)", people, ("sort_by", "people")),
    )
    for expression, document, names in arity_rows:
        exc = _refuse_named(expression, document, *names)
        texts = function_kind_texts(
            expression, UNKNOWN_EXPR, TYPE_EXPR, "unknown_function", "abs", *names
        )
        assert_kind_stems_differ(exc, unknown, *texts)
        assert_kind_stems_differ(exc, typed, *texts)
        print(f"arity {expression!r} distinct from unknown/type", flush=True)

    type_rows = (
        ("abs(str)", twelve, ("abs", "str")),
        ("abs(`false`)", twelve, ("abs",)),
        ("avg(array)", twelve, ("avg", "array")),
        ("avg('abc')", twelve, ("avg",)),
        ("avg(foo)", twelve, ("avg", "foo")),
        ("length(`false`)", twelve, ("length",)),
        ("length(foo)", twelve, ("length", "foo")),
        ('join(\',\', `["a", 0]`)', twelve, ("join",)),
        ("join(`2`, strings)", twelve, ("join", "strings")),
        ("max(array)", twelve, ("max", "array")),
        ("sort(array)", twelve, ("sort", "array")),
        ("keys(foo)", twelve, ("keys", "foo")),
        ("map(&a, badkey)", map_doc, ("map", "badkey")),
        ("sort_by(people, name)", people, ("sort_by", "people", "name")),
        ("sort_by(people, &bool)", people, ("sort_by", "people", "bool")),
        ("sort_by(people, &extra)", people, ("sort_by", "people", "extra")),
        ("max_by(people, &bool)", people, ("max_by", "people", "bool")),
        ("min_by(people, &extra)", people, ("min_by", "people", "extra")),
        ("starts_with(str, `0`)", twelve, ("starts_with", "str")),
        ("ends_with(str, `0`)", twelve, ("ends_with", "str")),
    )
    for expression, document, names in type_rows:
        exc = _refuse_named(expression, document, *names)
        texts = function_kind_texts(
            expression, UNKNOWN_EXPR, ARITY_EXPR, "unknown_function", "abs", *names
        )
        assert_kind_stems_differ(exc, unknown, *texts)
        assert_kind_stems_differ(exc, arity, *texts)
        print(f"type {expression!r} distinct from unknown/arity", flush=True)


def test_quoted_identifier_is_not_a_function_name():
    document = with_sentinel(_twelve())
    unknown, arity, typed = _representatives(document)
    require_oneshot_equals("to_string(`1.0`)", document, "1.0")
    quoted = assert_search_syntax_not_empty_or_incomplete(QUOTED_EXPR, document)
    texts = function_kind_texts(
        QUOTED_EXPR,
        UNKNOWN_EXPR,
        ARITY_EXPR,
        TYPE_EXPR,
        "unknown_function",
        "abs",
        "to_string",
    )
    assert_kind_stems_differ(quoted, unknown, *texts)
    assert_kind_stems_differ(quoted, arity, *texts)
    assert_kind_stems_differ(quoted, typed, *texts)
    assert_compile_syntax_not_empty_or_incomplete(QUOTED_EXPR)
    print("quoted identifier is syntax, not a function name", flush=True)


def test_host_non_json_current_value_and_to_string_conversion():
    field = fn_ident()
    payload = fn_payload()
    obj = host_non_json_value(payload)
    document = with_sentinel({field: obj})
    current = require_search_value(oneshot_search(field, document))
    assert current is obj, f"host current value was not accepted: {current!r}"
    unknown, arity, _typed = _representatives(with_sentinel(_twelve()))
    abs_expr = f"abs({field})"
    abs_exc = assert_search_is_value_error(abs_expr, document)
    texts = function_kind_texts(
        abs_expr, UNKNOWN_EXPR, ARITY_EXPR, "unknown_function", "abs", field
    )
    assert_kind_stems_differ(abs_exc, unknown, *texts)
    assert_kind_stems_differ(abs_exc, arity, *texts)
    converted = require_search_value(oneshot_search(f"to_string({field})", document))
    quoted = compact_json_text(host_ordinary_text(obj))
    assert converted == quoted, (
        f"to_string of host non-JSON must be compact JSON string encoding "
        f"(quoted) of host ordinary text, got {converted!r} expected {quoted!r}"
    )
    print("host non-JSON current value / abs type / to_string quoted host text", flush=True)


def test_host_decimal_refused_as_invalid_type_by_number_function():
    field = fn_ident()
    value = host_decimal()
    document = with_sentinel({field: value})
    require_oneshot_equals("abs(foo)", with_sentinel(_twelve()), 1)
    unknown, arity, _typed = _representatives(with_sentinel(_twelve()))
    abs_expr = f"abs({field})"
    abs_exc = assert_search_is_value_error(abs_expr, document)
    texts = function_kind_texts(
        abs_expr, UNKNOWN_EXPR, ARITY_EXPR, "unknown_function", "abs", field
    )
    assert_kind_stems_differ(abs_exc, unknown, *texts)
    assert_kind_stems_differ(abs_exc, arity, *texts)
    print("host decimal refused as invalid-type by number-requiring function", flush=True)


def test_runtime_unknown_function_is_distinct_from_arity_and_type():
    name = fn_ident()
    document = with_sentinel(_twelve())
    unknown_runtime = assert_search_is_value_error(f"{name}(`1`, `2`)", document)
    arity = assert_search_is_value_error(ARITY_EXPR, document)
    typed = assert_search_is_value_error(TYPE_EXPR, document)
    texts = function_kind_texts(
        f"{name}(`1`, `2`)", ARITY_EXPR, TYPE_EXPR, name, "abs"
    )
    assert_kind_stems_differ(unknown_runtime, arity, *texts)
    assert_kind_stems_differ(unknown_runtime, typed, *texts)
    print("runtime unknown function distinct from arity/type", flush=True)


def test_compile_path_function_failures():
    twelve = with_sentinel(_twelve())
    people = with_sentinel(_age_people())
    require_unsuccessful_compile_path(UNKNOWN_EXPR, twelve)
    require_unsuccessful_compile_path(ARITY_EXPR, twelve)
    require_unsuccessful_compile_path(TYPE_EXPR, twelve)
    require_unsuccessful_compile_path("sort_by(people)", people)
    require_unsuccessful_compile_path("sort_by(people, name)", people)
    assert_compile_syntax_not_empty_or_incomplete(QUOTED_EXPR)
    assert compile_once_then_search("abs(foo)", twelve) == 1
    field = fn_ident()
    payload = fn_payload()
    obj = host_non_json_value(payload)
    host_doc = {field: obj}
    quoted = compact_json_text(host_ordinary_text(obj))
    compiled_text = compile_once_then_search(f"to_string({field})", host_doc)
    assert compiled_text == quoted, (
        f"compile-then-search to_string of host non-JSON must be compact "
        f"JSON string encoding (quoted) of host ordinary text, "
        f"got {compiled_text!r} expected {quoted!r}"
    )
    host_abs = require_unsuccessful_compile_path(f"abs({field})", host_doc)
    unknown = assert_search_is_value_error(UNKNOWN_EXPR, twelve)
    arity = assert_search_is_value_error(ARITY_EXPR, twelve)
    texts = function_kind_texts(
        f"abs({field})", UNKNOWN_EXPR, ARITY_EXPR, "unknown_function", "abs", field
    )
    assert_kind_stems_differ(host_abs, unknown, *texts)
    assert_kind_stems_differ(host_abs, arity, *texts)
    print("compile-path function failures and host conversion", flush=True)
