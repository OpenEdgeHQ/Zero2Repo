# feature: F08
"""FP-08: evaluation options for constructed objects and custom functions.

Assertions follow Full_PRD.original.md FP-08 (L343–L364) together with
the two public search entries (L9 / L19–L21 / L33 / L51), numbers as
integers or floats and booleans not numbers (L26), host non-JSON current
values (L61), value-error failures without graded wording (L63), no
write-back (L82), and the three distinguishable function-call failure
kinds (L291 / L329–L334). Options attach to search, not to compile.
"""

from __future__ import annotations

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F01_helpers import (
    assert_search_is_value_error,
    compile_expression,
    oneshot_search,
    require_search_value,
    require_search_value_error,
    require_successful_null,
    search_parsed,
)
from F03_helpers import assert_kind_stems_differ, require_oneshot_equals
from F04_helpers import json_literal_text
from F06_helpers import with_sentinel
from F07_helpers import (
    assert_three_function_kinds_distinct,
    fn_float,
    fn_ident,
    fn_int,
    fn_payload,
    function_kind_texts,
    host_non_json_value,
)
from F08_helpers import (
    assert_parsed_search_with_options_is_value_error,
    assert_search_with_options_is_value_error,
    compile_once_then_search_with_options,
    empty_evaluation_options,
    extending_binary_number_provider,
    extending_null_tolerant_length_provider,
    extending_two_number_function_provider,
    oneshot_search_with_options,
    options_with_mapping_and_provider,
    options_with_mapping_type,
    options_with_provider,
    order_preserving_mapping_type,
    process_local_function_name,
    require_host_ordinary_mapping,
    require_mapping_of_type,
    require_oneshot_with_options_equals,
    search_parsed_with_options,
)

PUBLIC_MAPPING_DOC = {"c": "c", "b": "b", "a": "a", "d": "d"}
PUBLIC_STAR = "{a: a, b: b, c: c}.*"
PUBLIC_HASH = "{a: a, b: b, c: c}"
PUBLIC_STAR_VALUES = ["a", "b", "c"]
CUSTOM_ADD = "custom_add(`1`, `2`)"
CUSTOM_ADD_ONE = "custom_add(`1`)"
CUSTOM_ADD_THREE = "custom_add(`1`, `2`, `3`)"
CUSTOM_ADD_STR = "custom_add('x', `2`)"
CUSTOM_ADD_STR_SLOT2 = "custom_add(`1`, 'x')"
CUSTOM_ADD_BOOL = "custom_add(`true`, `2`)"
MY_SUBTRACT = "my_subtract(`10`, `3`)"
LENGTH_ONE_TWO = "length(`[1, 2]`)"


def _public_mapping_document() -> dict:
    return dict(PUBLIC_MAPPING_DOC)


def _public_length_document() -> dict:
    return {"a": {"b": [1, 2, 3]}}


def _binary_provider():
    return extending_binary_number_provider("custom_add", "my_subtract")


def _binary_options():
    return options_with_provider(_binary_provider())


# ---------------------------------------------------------------------------
# A. mapping type on every multiselect hash; merge stays host ordinary
# ---------------------------------------------------------------------------


def test_no_options_multiselect_hash_is_host_ordinary_mapping():
    document = {"a": "a", "b": "b"}
    value = require_search_value(oneshot_search("{a: a}", document))
    require_host_ordinary_mapping(value)
    assert value is not document, (
        f"no-options hash returned the input document: {value!r}"
    )
    assert "b" not in value, (
        f"no-options hash kept document field b: {value!r}"
    )
    assert value["a"] == "a", f"no-options hash field a: {value!r}"
    assert value == {"a": "a"}, (
        f"no-options hash must be {{a: a}}, not the input document; got {value!r}"
    )
    print("no-options multiselect hash is host ordinary mapping {a: a}", flush=True)


def test_order_preserving_mapping_type_projects_declaration_order():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    document = _public_mapping_document()
    require_oneshot_with_options_equals(
        PUBLIC_STAR, document, options, PUBLIC_STAR_VALUES
    )
    constructed = require_search_value(
        oneshot_search_with_options(PUBLIC_HASH, document, options)
    )
    require_mapping_of_type(constructed, mapping_type)
    assert list(constructed.keys()) == ["a", "b", "c"], constructed
    assert list(constructed.values()) == ["a", "b", "c"], constructed
    print("order-preserving mapping type projects declaration order", flush=True)


def test_constructed_hash_is_exactly_the_supplied_mapping_type():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    document = _public_mapping_document()
    value = require_search_value(
        oneshot_search_with_options(PUBLIC_HASH, document, options)
    )
    require_mapping_of_type(value, mapping_type)
    assert type(value) is mapping_type, (
        f"constructed hash type is {type(value)!r}, "
        f"not the supplied mapping type {mapping_type!r}"
    )
    assert type(value) is not type({}), (
        f"constructed hash used the host ordinary mapping: {type(value)!r}"
    )
    assert value is not document, (
        f"constructed hash returned the input document: {value!r}"
    )
    assert list(value.keys()) == ["a", "b", "c"], value
    assert list(value.values()) == ["a", "b", "c"], value
    print("constructed hash is exactly the supplied mapping type", flush=True)


def test_merge_ignores_supplied_mapping_type():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    named = require_search_value(
        oneshot_search_with_options(
            'merge(`{"a": 1}`, `{"b": 2}`)', with_sentinel({}), options
        )
    )
    require_host_ordinary_mapping(named)
    assert named == {"a": 1, "b": 2}, named
    assert type(named) is not mapping_type, type(named)

    left_key = fn_ident()
    right_key = fn_ident()
    left_payload = fn_int()
    right_payload = fn_int()
    document = {left_key: left_payload, right_key: right_payload}
    expr = f"merge({{{left_key}: {left_key}}}, {{{right_key}: {right_key}}})"
    merged = require_search_value(
        oneshot_search_with_options(expr, document, options)
    )
    require_host_ordinary_mapping(merged)
    assert type(merged) is not mapping_type, type(merged)
    assert merged[left_key] == left_payload, merged
    assert merged[right_key] == right_payload, merged
    print("merge ignores supplied mapping type", flush=True)


def test_nested_multiselect_hash_uses_supplied_type_on_every_hash():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    inner = fn_ident()
    payload = fn_payload()
    document = {inner: payload}
    value = require_search_value(
        oneshot_search_with_options(
            f"{{outer: {{{inner}: {inner}}}}}", document, options
        )
    )
    require_mapping_of_type(value, mapping_type)
    require_mapping_of_type(value["outer"], mapping_type)
    assert value["outer"][inner] == payload, value
    print("nested multiselect hash uses supplied type on every hash", flush=True)


def test_runtime_declaration_order_and_type():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    bait = fn_ident()
    k1, k2, k3 = fn_ident(), fn_ident(), fn_ident()
    v1, v2, v3 = fn_payload(), fn_payload(), fn_payload()
    bait_val = fn_payload()
    document = {bait: bait_val, k3: v3, k2: v2, k1: v1}
    star = f"{{{k1}: {k1}, {k2}: {k2}, {k3}: {k3}}}.*"
    hash_expr = f"{{{k1}: {k1}, {k2}: {k2}, {k3}: {k3}}}"
    projected = require_search_value(
        oneshot_search_with_options(star, document, options)
    )
    assert projected == [v1, v2, v3], projected
    assert projected != [v3, v2, v1], projected
    constructed = require_search_value(
        oneshot_search_with_options(hash_expr, document, options)
    )
    require_mapping_of_type(constructed, mapping_type)
    assert list(constructed.keys()) == [k1, k2, k3], constructed
    print("runtime declaration order and type", flush=True)


def test_compile_then_search_uses_same_mapping_options():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    document = _public_mapping_document()
    compiled_star = compile_once_then_search_with_options(
        PUBLIC_STAR, document, options
    )
    assert compiled_star == PUBLIC_STAR_VALUES, compiled_star
    compiled_hash = compile_once_then_search_with_options(
        PUBLIC_HASH, document, options
    )
    require_mapping_of_type(compiled_hash, mapping_type)
    assert list(compiled_hash.keys()) == ["a", "b", "c"], compiled_hash

    bait = fn_ident()
    k1, k2, k3 = fn_ident(), fn_ident(), fn_ident()
    v1, v2, v3 = fn_payload(), fn_payload(), fn_payload()
    runtime_doc = {bait: fn_payload(), k3: v3, k2: v2, k1: v1}
    parsed = require_search_value(
        compile_expression(f"{{{k1}: {k1}, {k2}: {k2}, {k3}: {k3}}}")
    )
    runtime_hash = require_search_value(
        search_parsed_with_options(parsed, runtime_doc, options)
    )
    require_mapping_of_type(runtime_hash, mapping_type)
    parsed_star = require_search_value(
        compile_expression(f"{{{k1}: {k1}, {k2}: {k2}, {k3}: {k3}}}.*")
    )
    runtime_star = require_search_value(
        search_parsed_with_options(parsed_star, runtime_doc, options)
    )
    assert runtime_star == [v1, v2, v3], runtime_star
    print("compile-then-search uses the same mapping options", flush=True)


def test_compile_then_search_merge_is_host_ordinary_mapping():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    left_key = fn_ident()
    right_key = fn_ident()
    left_payload = fn_int()
    right_payload = fn_int()
    document = {left_key: left_payload, right_key: right_payload}
    expr = f"merge({{{left_key}: {left_key}}}, {{{right_key}: {right_key}}})"
    merged = compile_once_then_search_with_options(expr, document, options)
    require_host_ordinary_mapping(merged)
    assert type(merged) is not mapping_type, type(merged)
    assert merged[left_key] == left_payload, merged
    assert merged[right_key] == right_payload, merged
    print("compile-then-search merge is host ordinary mapping", flush=True)


def test_mapping_type_does_not_leak_to_later_no_options_search():
    mapping_type = order_preserving_mapping_type()
    options = options_with_mapping_type(mapping_type)
    key = fn_ident()
    payload = fn_payload()
    document = {key: payload}
    expr = f"{{{key}: {key}}}"
    supplied = require_search_value(
        oneshot_search_with_options(expr, document, options)
    )
    require_mapping_of_type(supplied, mapping_type)
    later = require_search_value(oneshot_search(expr, document))
    require_host_ordinary_mapping(later)
    assert later[key] == payload, later
    print("mapping type does not leak to a later no-options search", flush=True)


def test_options_object_carries_mapping_type_and_provider_together():
    mapping_type = order_preserving_mapping_type()
    provider = _binary_provider()
    options = options_with_mapping_and_provider(mapping_type, provider)
    combined = require_search_value(
        oneshot_search_with_options(
            "{sum: custom_add(`1`, `2`)}", with_sentinel({}), options
        )
    )
    require_mapping_of_type(combined, mapping_type)
    assert combined["sum"] == 3, combined
    require_oneshot_with_options_equals(
        PUBLIC_STAR, _public_mapping_document(), options, PUBLIC_STAR_VALUES
    )
    print("one options object carries mapping type and provider together", flush=True)


# ---------------------------------------------------------------------------
# B. custom_add is 3; my_subtract is 7
# ---------------------------------------------------------------------------


def test_custom_add_and_my_subtract_named_oracles():
    document = with_sentinel({})
    no_opts = assert_search_is_value_error(CUSTOM_ADD, document)
    empty_opts = assert_search_with_options_is_value_error(
        CUSTOM_ADD, document, empty_evaluation_options()
    )
    options = _binary_options()
    require_oneshot_with_options_equals(CUSTOM_ADD, document, options, 3)
    require_oneshot_with_options_equals(MY_SUBTRACT, document, options, 7)
    added = require_search_value(
        oneshot_search_with_options(CUSTOM_ADD, document, options)
    )
    assert added is not document, added
    assert no_opts is not None
    assert empty_opts is not None
    print("custom_add is 3 and my_subtract is 7", flush=True)


def test_runtime_binary_custom_functions():
    add_name = process_local_function_name()
    sub_name = process_local_function_name()
    provider = extending_binary_number_provider(add_name, sub_name)
    options = options_with_provider(provider)
    left_key = fn_ident()
    right_key = fn_ident()
    left = fn_int()
    right = fn_int()
    document = with_sentinel({left_key: left, right_key: right})
    add_expr = f"{add_name}({left_key}, {right_key})"
    sub_expr = f"{sub_name}({left_key}, {right_key})"
    added = require_oneshot_with_options_equals(
        add_expr, document, options, left + right
    )
    subtracted = require_oneshot_with_options_equals(
        sub_expr, document, options, left - right
    )
    assert added == left + right, added
    assert subtracted == left - right, subtracted
    assert added is not document, added
    assert subtracted is not document, subtracted

    f_left = fn_float()
    f_right = fn_float()
    float_doc = with_sentinel({left_key: f_left, right_key: f_right})
    float_sum = require_oneshot_with_options_equals(
        add_expr, float_doc, options, f_left + f_right
    )
    assert float_sum == f_left + f_right, float_sum
    print("runtime binary custom functions on integer and float fields", flush=True)


def test_compile_then_search_custom_add_with_options():
    options = _binary_options()
    document = with_sentinel({})
    compiled = compile_once_then_search_with_options(CUSTOM_ADD, document, options)
    assert compiled == 3, compiled

    add_name = process_local_function_name()
    sub_name = process_local_function_name()
    local_options = options_with_provider(
        extending_binary_number_provider(add_name, sub_name)
    )
    left_key = fn_ident()
    right_key = fn_ident()
    left = fn_int()
    right = fn_int()
    runtime_doc = with_sentinel({left_key: left, right_key: right})
    expr = f"{add_name}({left_key}, {right_key})"
    compiled_runtime = compile_once_then_search_with_options(
        expr, runtime_doc, local_options
    )
    oneshot = require_search_value(
        oneshot_search_with_options(expr, runtime_doc, local_options)
    )
    assert compiled_runtime == oneshot, (compiled_runtime, oneshot)
    assert compiled_runtime == left + right, compiled_runtime
    print("compile-then-search custom_add with options", flush=True)


def test_same_parsed_expression_without_options_does_not_see_custom_add():
    options = _binary_options()
    document = with_sentinel({})
    parsed = require_search_value(compile_expression(CUSTOM_ADD))
    with_opts = require_search_value(
        search_parsed_with_options(parsed, document, options)
    )
    assert with_opts == 3, with_opts
    failed = search_parsed(parsed, document)
    assert failed.exception is not None, (
        f"same parsed custom_add without options succeeded "
        f"(value={failed.value!r})"
    )
    exc = require_search_value_error(failed)
    assert failed.value is not document
    assert exc is not None
    print(
        f"same parsed expression without options rejects custom_add "
        f"after live baseline {with_opts!r}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# C. extending provider still implements length
# ---------------------------------------------------------------------------


def test_extending_provider_still_has_length():
    options = _binary_options()
    document = with_sentinel({})
    length_value = require_oneshot_with_options_equals(
        LENGTH_ONE_TWO, document, options, 2
    )
    assert length_value == 2, length_value
    assert length_value is not document, length_value
    print("extending provider still has length(`[1, 2]`) == 2", flush=True)


def test_runtime_length_on_extending_provider():
    options = _binary_options()
    field = fn_ident()
    items = [fn_payload() for _ in range(4)]
    document = with_sentinel({field: items})
    expr = f"length({field})"
    length_value = require_oneshot_with_options_equals(
        expr, document, options, len(items)
    )
    assert length_value == len(items), length_value
    assert length_value is not document, length_value
    print("runtime length on extending provider equals host len", flush=True)


def test_compile_then_search_length_on_extending_provider():
    options = _binary_options()
    compiled = compile_once_then_search_with_options(
        LENGTH_ONE_TWO, with_sentinel({}), options
    )
    assert compiled == 2, compiled
    field = fn_ident()
    items = [fn_int(), fn_int(), fn_payload()]
    document = with_sentinel({field: items})
    expr = f"length({field})"
    compiled_runtime = compile_once_then_search_with_options(
        expr, document, options
    )
    oneshot = require_search_value(
        oneshot_search_with_options(expr, document, options)
    )
    assert compiled_runtime == oneshot, (compiled_runtime, oneshot)
    assert compiled_runtime == len(items), compiled_runtime
    print("compile-then-search length on extending provider", flush=True)


# ---------------------------------------------------------------------------
# D. isolation: later no-options / other provider / empty options
# ---------------------------------------------------------------------------


def test_later_no_options_search_keeps_length_and_rejects_custom_add():
    options = _binary_options()
    document = with_sentinel({})
    require_oneshot_with_options_equals(CUSTOM_ADD, document, options, 3)
    require_oneshot_equals(LENGTH_ONE_TWO, document, 2)
    field = fn_ident()
    items = [fn_payload(), fn_payload(), fn_payload()]
    runtime_doc = with_sentinel({field: items})
    require_oneshot_equals(f"length({field})", runtime_doc, len(items))
    add_exc = assert_search_is_value_error(CUSTOM_ADD, document)
    sub_exc = assert_search_is_value_error(MY_SUBTRACT, document)
    arity_exc = assert_search_with_options_is_value_error(
        CUSTOM_ADD_ONE, document, options
    )
    typed_exc = assert_search_with_options_is_value_error(
        CUSTOM_ADD_STR, document, options
    )
    texts = function_kind_texts(
        CUSTOM_ADD,
        CUSTOM_ADD_ONE,
        CUSTOM_ADD_STR,
        MY_SUBTRACT,
        "custom_add",
        "my_subtract",
        "x",
    )
    assert_three_function_kinds_distinct(add_exc, arity_exc, typed_exc, *texts)
    assert sub_exc is not None
    print(
        f"later no-options keeps length and rejects custom_add "
        f"as unknown-function kind texts={texts!r}",
        flush=True,
    )


def test_custom_function_on_one_provider_is_absent_from_another():
    add_name = process_local_function_name()
    sub_name = process_local_function_name()
    provider_a = extending_two_number_function_provider(add_name)
    provider_b = extending_two_number_function_provider(sub_name, subtract=True)
    opts_a = options_with_provider(provider_a)
    opts_b = options_with_provider(provider_b)
    left = fn_int()
    right = fn_int()
    document = with_sentinel({})
    add_expr = f"{add_name}({json_literal_text(left)}, {json_literal_text(right)})"
    sub_expr = f"{sub_name}({json_literal_text(left)}, {json_literal_text(right)})"
    require_oneshot_with_options_equals(add_expr, document, opts_a, left + right)
    require_oneshot_with_options_equals(sub_expr, document, opts_b, left - right)
    missing_on_b = assert_search_with_options_is_value_error(
        add_expr, document, opts_b
    )
    missing_on_a = assert_search_with_options_is_value_error(
        sub_expr, document, opts_a
    )
    missing_empty = assert_search_with_options_is_value_error(
        sub_expr, document, empty_evaluation_options()
    )
    missing_none = assert_search_is_value_error(sub_expr, document)
    assert missing_on_b is not None
    assert missing_on_a is not None
    assert missing_empty is not None
    assert missing_none is not None
    print("custom function on one provider is absent from another", flush=True)


def test_options_without_provider_do_not_create_custom_add():
    document = with_sentinel({})
    options = _binary_options()
    require_oneshot_with_options_equals(CUSTOM_ADD, document, options, 3)
    empty_exc = assert_search_with_options_is_value_error(
        CUSTOM_ADD, document, empty_evaluation_options()
    )
    mapping_only = options_with_mapping_type(order_preserving_mapping_type())
    mapping_exc = assert_search_with_options_is_value_error(
        CUSTOM_ADD, document, mapping_only
    )
    none_exc = assert_search_is_value_error(CUSTOM_ADD, document)
    assert empty_exc is not None
    assert mapping_exc is not None
    assert none_exc is not None
    print("options without a provider do not create custom_add", flush=True)


# ---------------------------------------------------------------------------
# E. custom length: null -> 0, otherwise host len; string is accepted
# ---------------------------------------------------------------------------


def test_custom_length_maps_null_to_zero_and_array_to_host_len():
    name = process_local_function_name()
    options = options_with_provider(extending_null_tolerant_length_provider(name))
    document = with_sentinel(_public_length_document())
    require_oneshot_with_options_equals(f"{name}(a.b)", document, options, 3)
    zero = require_search_value(
        oneshot_search_with_options(f"{name}(a.c)", document, options)
    )
    assert zero == 0, zero
    assert zero is not None
    typed = assert_search_with_options_is_value_error(
        f"{name}(`true`)", document, options
    )
    typed_num = assert_search_with_options_is_value_error(
        f"{name}(`1`)", document, options
    )
    assert typed is not None
    assert typed_num is not None
    print("custom length maps null to 0 and array to host len", flush=True)


def test_runtime_custom_length_array_object_missing_and_string():
    name = process_local_function_name()
    options = options_with_provider(extending_null_tolerant_length_provider(name))
    arr_key = fn_ident()
    obj_key = fn_ident()
    str_key = fn_ident()
    missing = fn_ident()
    items = [fn_payload(), fn_payload()]
    obj = {fn_ident(): fn_payload(), fn_ident(): fn_payload(), fn_ident(): fn_payload()}
    text = fn_payload()
    document = with_sentinel({arr_key: items, obj_key: obj, str_key: text})
    array_len = require_oneshot_with_options_equals(
        f"{name}({arr_key})", document, options, len(items)
    )
    object_len = require_oneshot_with_options_equals(
        f"{name}({obj_key})", document, options, len(obj)
    )
    string_len = require_oneshot_with_options_equals(
        f"{name}({str_key})", document, options, len(text)
    )
    missing_len = require_oneshot_with_options_equals(
        f"{name}({missing})", document, options, 0
    )
    assert array_len == len(items), array_len
    assert object_len == len(obj), object_len
    assert string_len == len(text), string_len
    assert missing_len == 0, missing_len
    assert missing_len is not None
    print("runtime custom length on array, object, string, missing", flush=True)


def test_compile_then_search_custom_length():
    name = process_local_function_name()
    options = options_with_provider(extending_null_tolerant_length_provider(name))
    document = with_sentinel(_public_length_document())
    compiled_three = compile_once_then_search_with_options(
        f"{name}(a.b)", document, options
    )
    compiled_zero = compile_once_then_search_with_options(
        f"{name}(a.c)", document, options
    )
    assert compiled_three == 3, compiled_three
    assert compiled_zero == 0, compiled_zero
    field = fn_ident()
    items = [fn_int(), fn_payload(), fn_payload(), fn_int()]
    runtime_doc = with_sentinel({field: items})
    expr = f"{name}({field})"
    compiled_runtime = compile_once_then_search_with_options(
        expr, runtime_doc, options
    )
    oneshot = require_search_value(
        oneshot_search_with_options(expr, runtime_doc, options)
    )
    assert compiled_runtime == oneshot, (compiled_runtime, oneshot)
    assert compiled_runtime == len(items), compiled_runtime
    print("compile-then-search custom length", flush=True)


# ---------------------------------------------------------------------------
# F. unknown / arity / type; host non-JSON; compile-path failures
# ---------------------------------------------------------------------------


def test_custom_unknown_arity_type_failures_are_distinguishable():
    options = _binary_options()
    document = with_sentinel({})
    unknown_name = process_local_function_name()
    unknown_expr = f"{unknown_name}(`1`, `2`)"
    unknown = assert_search_with_options_is_value_error(
        unknown_expr, document, options
    )
    arity_low = assert_search_with_options_is_value_error(
        CUSTOM_ADD_ONE, document, options
    )
    arity_high = assert_search_with_options_is_value_error(
        CUSTOM_ADD_THREE, document, options
    )
    typed = assert_search_with_options_is_value_error(
        CUSTOM_ADD_STR, document, options
    )
    typed_slot2 = assert_search_with_options_is_value_error(
        CUSTOM_ADD_STR_SLOT2, document, options
    )
    typed_bool = assert_search_with_options_is_value_error(
        CUSTOM_ADD_BOOL, document, options
    )
    texts = function_kind_texts(
        unknown_expr,
        CUSTOM_ADD_ONE,
        CUSTOM_ADD_THREE,
        CUSTOM_ADD_STR,
        CUSTOM_ADD_STR_SLOT2,
        CUSTOM_ADD_BOOL,
        unknown_name,
        "custom_add",
        "x",
        "true",
    )
    assert_three_function_kinds_distinct(unknown, arity_low, typed, *texts)
    extra_arity = function_kind_texts(
        CUSTOM_ADD_THREE, unknown_expr, CUSTOM_ADD_STR, unknown_name, "custom_add"
    )
    assert_kind_stems_differ(arity_high, unknown, *extra_arity)
    assert_kind_stems_differ(arity_high, typed, *extra_arity)
    bool_texts = function_kind_texts(
        CUSTOM_ADD_BOOL, unknown_expr, CUSTOM_ADD_ONE, unknown_name, "custom_add", "true"
    )
    assert_kind_stems_differ(typed_bool, unknown, *bool_texts)
    assert_kind_stems_differ(typed_bool, arity_low, *bool_texts)
    slot2_texts = function_kind_texts(
        CUSTOM_ADD_STR_SLOT2,
        unknown_expr,
        CUSTOM_ADD_ONE,
        unknown_name,
        "custom_add",
        "x",
    )
    assert_kind_stems_differ(typed_slot2, unknown, *slot2_texts)
    assert_kind_stems_differ(typed_slot2, arity_low, *slot2_texts)
    require_successful_null(oneshot_search("missing", {}))
    print("custom unknown / arity / type failures are distinguishable", flush=True)


def test_compile_then_search_custom_unknown_arity_type_failures():
    options = _binary_options()
    document = with_sentinel({})
    unknown_name = process_local_function_name()
    unknown_expr = f"{unknown_name}(`1`, `2`)"
    unknown_parsed = require_search_value(compile_expression(unknown_expr))
    arity_parsed = require_search_value(compile_expression(CUSTOM_ADD_ONE))
    typed_parsed = require_search_value(compile_expression(CUSTOM_ADD_STR))
    unknown = assert_parsed_search_with_options_is_value_error(
        unknown_parsed, document, options
    )
    arity = assert_parsed_search_with_options_is_value_error(
        arity_parsed, document, options
    )
    typed = assert_parsed_search_with_options_is_value_error(
        typed_parsed, document, options
    )
    texts = function_kind_texts(
        unknown_expr,
        CUSTOM_ADD_ONE,
        CUSTOM_ADD_STR,
        unknown_name,
        "custom_add",
        "x",
    )
    assert_three_function_kinds_distinct(unknown, arity, typed, *texts)
    print("compile-then-search custom unknown / arity / type failures", flush=True)


def test_host_non_json_refused_by_custom_json_typed_function():
    name = process_local_function_name()
    options = options_with_provider(extending_null_tolerant_length_provider(name))
    field = fn_ident()
    payload = fn_payload()
    obj = host_non_json_value(payload)
    document = with_sentinel({field: obj})
    require_successful_null(oneshot_search("missing", obj))
    expr = f"{name}({field})"
    typed = assert_search_with_options_is_value_error(expr, document, options)
    unknown_name = process_local_function_name()
    unknown_expr = f"{unknown_name}({field})"
    unknown = assert_search_with_options_is_value_error(
        unknown_expr, document, options
    )
    arity_expr = f"{name}({field}, {field})"
    arity = assert_search_with_options_is_value_error(arity_expr, document, options)
    texts = function_kind_texts(
        expr, unknown_expr, arity_expr, name, unknown_name, field
    )
    assert_three_function_kinds_distinct(unknown, arity, typed, *texts)
    print("host non-JSON refused by custom JSON-typed function", flush=True)
