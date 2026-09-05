# feature: F03
"""Mapping containers and key policies (FP-03).

Assertions stay at the PRD's precision: default plain-object maps and
stringified scalar keys, own ``__proto__`` without prototype pollution,
default rejection of sequence/mapping keys, real-map ``Map`` keys and
dump-then-parse, legacy stringified sequence keys, mapping keys stored
as the ordinary JavaScript object rendering, and nested-array refusal.
Exception class names, failure wording, and dump layout are not pinned.
"""

from __future__ import annotations

import pytest

from _harness import JsMap, dump, load
from _helpers import (
    alias_nested_array_key_yaml,
    core_int_token,
    dump_then_load,
    explicit_mapping_key_yaml,
    explicit_nested_array_key_yaml,
    explicit_scalar_key_yaml,
    explicit_sequence_key_containing_nested_yaml,
    explicit_sequence_key_yaml,
    is_bool,
    is_inherited_visible,
    is_number_not_string,
    is_string_text,
    map_get,
    map_size,
    mapping_get,
    observer_visible_report,
    ordinary_js_object_rendering,
    require_document,
    require_ordinary_object_prototype,
    require_own_data_property,
    require_parse_failure,
    require_plain_mapping,
    require_real_map,
    require_sequence,
    require_yaml_text,
    unique_token,
    with_core_schema,
    with_failsafe_schema,
    with_json_schema,
    with_legacy_map_schema,
    with_real_map_on_failsafe,
    with_real_map_on_json,
    with_real_map_schema,
    with_yaml11_schema,
)

CLARK_THREE = "Clark: Evans\nBrian: Ingerson\nOren: Ben-Kiki\n"
CLARK_ONE = "Clark: Evans\n"
FOO_BAR_BAZ = "? - foo\n  - bar\n: baz\n"
MAPPING_KEY_A1 = "? { a: 1 }\n: value\n"
PROTO_POLLUTED = "{ __proto__: { polluted: true } }\n"
ONE_AND_STR_ONE = '1: num\n"1": str\n'
TILDE_NULL_KEY = "~: null key\n"
ONE_NUM = "1: num\n"
NESTED_FOO_BAR = "wrapper:\n  ? - foo\n    - bar\n  : baz\n"
EXPLICIT_MAP_CLARK = "!!map\n  Clark: Evans\n"

_SCHEMA_FNS = (
    with_failsafe_schema,
    with_json_schema,
    with_core_schema,
    with_yaml11_schema,
)
_SCHEMA_IDS = ("failsafe", "json", "core", "yaml11")


def _assert_three_name_pairs(doc) -> None:
    require_plain_mapping(doc)
    assert is_string_text(mapping_get(doc, "Clark"), "Evans")
    assert is_string_text(mapping_get(doc, "Brian"), "Ingerson")
    assert is_string_text(mapping_get(doc, "Oren"), "Ben-Kiki")


def _assert_own_accessor_not_inherited(doc, payload: str):
    require_plain_mapping(doc)
    require_ordinary_object_prototype(doc)
    inner = require_own_data_property(doc, "__proto__")
    print(
        f"own_names={list(doc.own_names)!r} in_keys={list(doc.in_keys)!r} "
        f"proto={doc.proto!r}",
        flush=True,
    )
    assert payload not in doc.own_names, (
        f"{payload!r} must not be an own name of the root; "
        f"own={list(doc.own_names)!r}"
    )
    assert not is_inherited_visible(doc, payload), (
        f"{payload!r} must not be visible via for-in on the root; "
        f"in_keys={list(doc.in_keys)!r}"
    )
    return inner


def _js_map(entries: list) -> JsMap:
    return JsMap(entries=entries, object_id=0)


# ---------------------------------------------------------------------------
# A. Default plain-object map: string properties, scalar keys stringified
# ---------------------------------------------------------------------------


def test_default_clark_evans_plain_object():
    result = load(CLARK_THREE)
    doc = require_document(result)
    print(f"default clark type={type(doc).__name__}", flush=True)
    _assert_three_name_pairs(doc)


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_map_is_plain_object_on_every_schema(schema_fn):
    opts = schema_fn()
    doc = require_document(load(CLARK_THREE, opts))
    print(f"schema={opts!r} type={type(doc).__name__}", flush=True)
    _assert_three_name_pairs(doc)


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_runtime_pair_is_plain_object_on_every_schema(schema_fn):
    key = unique_token()
    value = unique_token()
    source = f"{key}: {value}\n"
    opts = schema_fn()
    print(f"schema={opts!r} source={source!r}", flush=True)
    doc = require_document(load(source, opts))
    require_plain_mapping(doc)
    assert is_string_text(mapping_get(doc, key), value)


def test_default_tilde_key_stores_null_property():
    doc = require_document(load(TILDE_NULL_KEY))
    require_plain_mapping(doc)
    print(f"tilde keys={list(doc.keys())!r}", flush=True)
    assert is_string_text(mapping_get(doc, "null"), "null key")


def test_default_numeric_key_is_string_one():
    doc = require_document(load(ONE_NUM))
    require_plain_mapping(doc)
    print(f"numeric-key keys={list(doc.keys())!r}", flush=True)
    assert is_string_text(mapping_get(doc, "1"), "num")


def test_default_runtime_numeric_key_is_string():
    number = core_int_token()
    word = unique_token()
    source = f"{number}: {word}\n"
    print(f"source={source!r}", flush=True)
    doc = require_document(load(source))
    require_plain_mapping(doc)
    name = str(number)
    print(f"keys={list(doc.keys())!r}", flush=True)
    assert is_string_text(mapping_get(doc, name), word)


# ---------------------------------------------------------------------------
# B. Prototype-accessor key is own data; ordinary prototype is kept
# ---------------------------------------------------------------------------


def test_default_proto_key_is_own_data_not_pollution():
    doc = require_document(load(PROTO_POLLUTED))
    inner = _assert_own_accessor_not_inherited(doc, "polluted")
    inner_map = require_plain_mapping(inner)
    assert is_bool(mapping_get(inner_map, "polluted"), True)


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_proto_key_is_own_data_on_every_schema(schema_fn):
    opts = schema_fn()
    doc = require_document(load(PROTO_POLLUTED, opts))
    print(f"schema={opts!r}", flush=True)
    inner = _assert_own_accessor_not_inherited(doc, "polluted")
    inner_map = require_plain_mapping(inner)
    payload = mapping_get(inner_map, "polluted")
    print(f"inner polluted={payload!r} type={type(payload).__name__}", flush=True)
    if schema_fn is not with_failsafe_schema:
        assert is_bool(payload, True), (
            f"typed schema must store boolean true; got {payload!r}"
        )


def test_default_proto_key_runtime_payload_not_inherited():
    payload = unique_token()
    source = "{ __proto__: { " + payload + ": true } }\n"
    print(f"source={source!r}", flush=True)
    doc = require_document(load(source))
    inner = _assert_own_accessor_not_inherited(doc, payload)
    inner_map = require_plain_mapping(inner)
    assert is_bool(mapping_get(inner_map, payload), True)


def test_default_proto_scalar_value_is_own_data():
    word = unique_token()
    source = f'"__proto__": {word}\n'
    print(f"source={source!r}", flush=True)
    doc = require_document(load(source))
    require_plain_mapping(doc)
    require_ordinary_object_prototype(doc)
    value = require_own_data_property(doc, "__proto__")
    print(f"scalar proto value={value!r}", flush=True)
    assert is_string_text(value, word)


# ---------------------------------------------------------------------------
# C. Default map rejects sequence keys and mapping keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_explicit_scalar_key_succeeds_on_every_schema(schema_fn):
    key = unique_token()
    value = unique_token()
    source = explicit_scalar_key_yaml(key, value)
    opts = schema_fn()
    print(f"schema={opts!r} source={source!r}", flush=True)
    doc = require_document(load(source, opts))
    require_plain_mapping(doc)
    assert is_string_text(mapping_get(doc, key), value)


def test_default_rejects_sequence_key():
    result = load(FOO_BAR_BAZ)
    error = require_parse_failure(result)
    print(
        f"seq-key ok={result.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_default_rejects_mapping_key():
    result = load(MAPPING_KEY_A1)
    error = require_parse_failure(result)
    print(
        f"map-key ok={result.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_rejects_sequence_key_on_every_schema(schema_fn):
    opts = schema_fn()
    result = load(FOO_BAR_BAZ, opts)
    error = require_parse_failure(result)
    print(
        f"schema={opts!r} seq-key ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_rejects_mapping_key_on_every_schema(schema_fn):
    opts = schema_fn()
    result = load(MAPPING_KEY_A1, opts)
    error = require_parse_failure(result)
    print(
        f"schema={opts!r} map-key ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


@pytest.mark.parametrize("schema_fn", _SCHEMA_FNS, ids=_SCHEMA_IDS)
def test_default_rejects_runtime_complex_keys(schema_fn):
    opts = schema_fn()
    w1, w2, val = unique_token(), unique_token(), unique_token()
    seq_src = explicit_sequence_key_yaml([w1, w2], val)
    seq_result = load(seq_src, opts)
    seq_error = require_parse_failure(seq_result)
    print(
        f"schema={opts!r} runtime-seq={seq_src!r} ok={seq_result.ok!r} "
        f"report={observer_visible_report(seq_error)!r}",
        flush=True,
    )
    assert seq_result.ok is False

    mk, mv, outer = unique_token(), unique_token(), unique_token()
    map_src = explicit_mapping_key_yaml([(mk, mv)], outer)
    map_result = load(map_src, opts)
    map_error = require_parse_failure(map_result)
    print(
        f"schema={opts!r} runtime-map={map_src!r} ok={map_result.ok!r} "
        f"report={observer_visible_report(map_error)!r}",
        flush=True,
    )
    assert map_result.ok is False


def test_default_rejects_one_item_sequence_key():
    word = unique_token()
    val = unique_token()
    source = explicit_sequence_key_yaml([word], val)
    result = load(source)
    error = require_parse_failure(result)
    print(
        f"one-item seq={source!r} ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_default_rejects_nested_sequence_key():
    result = load(NESTED_FOO_BAR)
    error = require_parse_failure(result)
    print(
        f"nested seq-key={NESTED_FOO_BAR!r} ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


# ---------------------------------------------------------------------------
# D. Real-map replacement: Map, distinct number/string keys, complex keys
# ---------------------------------------------------------------------------


def test_real_map_clark_evans_is_map():
    baseline = require_document(load(CLARK_ONE))
    require_plain_mapping(baseline)
    assert is_string_text(mapping_get(baseline, "Clark"), "Evans")

    opts = with_real_map_schema()
    doc = require_document(load(CLARK_ONE, opts))
    print(f"real-map clark type={type(doc).__name__}", flush=True)
    real = require_real_map(doc)
    assert is_string_text(map_get(real, "Clark"), "Evans")


def test_real_map_numeric_and_string_one_are_distinct():
    # Each form alone is a string property under the default map. The
    # combined document is not a default-map success: after
    # stringification the two keys collide, and duplicate keys are
    # refused (FP-01). FP-03 does not name that combined default parse.
    numeric = require_plain_mapping(require_document(load(ONE_NUM)))
    print(f"default 1: num keys={list(numeric.keys())!r}", flush=True)
    assert is_string_text(mapping_get(numeric, "1"), "num")
    quoted = require_plain_mapping(require_document(load('"1": str\n')))
    print(f"default \"1\": str keys={list(quoted.keys())!r}", flush=True)
    assert is_string_text(mapping_get(quoted, "1"), "str")

    real = require_real_map(
        require_document(load(ONE_AND_STR_ONE, with_real_map_schema()))
    )
    print(f"real-map size={map_size(real)}", flush=True)
    assert map_size(real) == 2
    assert is_string_text(map_get(real, 1), "num")
    assert is_string_text(map_get(real, "1"), "str")


def test_real_map_runtime_number_and_string_distinct():
    number = core_int_token()
    word_num = unique_token()
    word_str = unique_token()
    source = f"{number}: {word_num}\n\"{number}\": {word_str}\n"
    print(f"source={source!r}", flush=True)
    real = require_real_map(
        require_document(load(source, with_real_map_schema()))
    )
    print(f"runtime size={map_size(real)}", flush=True)
    assert map_size(real) == 2
    assert is_string_text(map_get(real, number), word_num)
    assert is_string_text(map_get(real, str(number)), word_str)


def test_real_map_array_and_map_keys_round_trip():
    source = _js_map(
        [
            ([1, 2], "arr"),
            (_js_map([("x", 1)]), "obj"),
        ]
    )
    opts = with_real_map_schema()
    dumped = dump(source, opts)
    text = require_yaml_text(dumped)
    print(f"public complex dump chars={len(text)}", flush=True)
    result = dump_then_load(source, opts)
    real = require_real_map(require_document(result))
    assert is_string_text(map_get(real, [1, 2]), "arr")
    obj_key = _js_map([("x", 1)])
    assert is_string_text(map_get(real, obj_key), "obj")
    found = None
    for key, _value in real.entries:
        if isinstance(key, JsMap):
            found = key
            break
    assert found is not None, "array/map round-trip lost the Map key"
    assert is_number_not_string(map_get(found, "x"), 1)


def test_real_map_runtime_complex_keys_round_trip():
    w1, w2, arr_val = unique_token(), unique_token(), unique_token()
    mk, mv, obj_val = unique_token(), unique_token(), unique_token()
    source = _js_map(
        [
            ([w1, w2], arr_val),
            (_js_map([(mk, mv)]), obj_val),
        ]
    )
    opts = with_real_map_schema()
    real = require_real_map(require_document(dump_then_load(source, opts)))
    print(f"runtime complex size={map_size(real)}", flush=True)
    assert is_string_text(map_get(real, [w1, w2]), arr_val)
    assert is_string_text(map_get(real, _js_map([(mk, mv)])), obj_val)
    found = None
    for key, _value in real.entries:
        if isinstance(key, JsMap):
            found = key
            break
    assert found is not None, "runtime Map key did not survive dump-then-parse"
    assert is_string_text(map_get(found, mk), mv)


def test_real_map_parses_yaml_sequence_and_mapping_keys():
    w1, w2, seq_val = unique_token(), unique_token(), unique_token()
    seq_src = explicit_sequence_key_yaml([w1, w2], seq_val)
    print(f"yaml seq-key={seq_src!r}", flush=True)
    seq_real = require_real_map(
        require_document(load(seq_src, with_real_map_schema()))
    )
    assert is_string_text(map_get(seq_real, [w1, w2]), seq_val)

    mk, mv, outer = unique_token(), unique_token(), unique_token()
    map_src = explicit_mapping_key_yaml([(mk, mv)], outer)
    print(f"yaml map-key={map_src!r}", flush=True)
    map_real = require_real_map(
        require_document(load(map_src, with_real_map_schema()))
    )
    found = None
    for key, value in map_real.entries:
        print(f"yaml map-key entry type={type(key).__name__}", flush=True)
        if isinstance(key, JsMap):
            found = key
            assert is_string_text(value, outer)
            break
        assert False, (
            f"YAML mapping key must be a Map, got {type(key).__name__}"
        )
    assert found is not None
    assert is_string_text(map_get(found, mk), mv)
    assert is_string_text(map_get(map_real, found), outer)


def test_real_map_dump_plain_object_parses_as_map():
    opts = with_real_map_schema()
    dumped = dump({"a": 1, "b": 2}, opts)
    text = require_yaml_text(dumped)
    print(f"plain-object dump chars={len(text)}", flush=True)
    real = require_real_map(require_document(dump_then_load({"a": 1, "b": 2}, opts)))
    assert is_number_not_string(map_get(real, "a"), 1)
    assert is_number_not_string(map_get(real, "b"), 2)


def test_real_map_dump_runtime_plain_object_parses_as_map():
    k1, k2 = unique_token(), unique_token()
    v1, v2 = unique_token(), unique_token()
    opts = with_real_map_schema()
    real = require_real_map(
        require_document(dump_then_load({k1: v1, k2: v2}, opts))
    )
    print(f"runtime dump-parse size={map_size(real)}", flush=True)
    assert is_string_text(map_get(real, k1), v1)
    assert is_string_text(map_get(real, k2), v2)


def test_real_map_explicit_map_tag_is_map():
    doc = require_document(load(EXPLICIT_MAP_CLARK, with_real_map_schema()))
    print(f"explicit !!map type={type(doc).__name__}", flush=True)
    real = require_real_map(doc)
    assert is_string_text(map_get(real, "Clark"), "Evans")


def test_real_map_explicit_map_tag_runtime_pair_is_map():
    key = unique_token()
    value = unique_token()
    source = f"!!map\n  {key}: {value}\n"
    print(f"explicit !!map runtime={source!r}", flush=True)
    real = require_real_map(
        require_document(load(source, with_real_map_schema()))
    )
    assert is_string_text(map_get(real, key), value)


def test_real_map_replaces_default_on_failsafe():
    baseline = require_document(load(CLARK_ONE, with_failsafe_schema()))
    require_plain_mapping(baseline)
    assert is_string_text(mapping_get(baseline, "Clark"), "Evans")

    real = require_real_map(
        require_document(load(CLARK_ONE, with_real_map_on_failsafe()))
    )
    print(f"failsafe real-map type={type(real).__name__}", flush=True)
    assert is_string_text(map_get(real, "Clark"), "Evans")


def test_real_map_failsafe_runtime_pair_is_map():
    key = unique_token()
    value = unique_token()
    source = f"{key}: {value}\n"
    print(f"failsafe runtime={source!r}", flush=True)
    baseline = require_document(load(source, with_failsafe_schema()))
    require_plain_mapping(baseline)
    assert is_string_text(mapping_get(baseline, key), value)

    real = require_real_map(
        require_document(load(source, with_real_map_on_failsafe()))
    )
    assert is_string_text(map_get(real, key), value)


def test_real_map_json_numeric_and_string_one_are_distinct():
    real = require_real_map(
        require_document(load(ONE_AND_STR_ONE, with_real_map_on_json()))
    )
    print(f"json real-map size={map_size(real)}", flush=True)
    assert map_size(real) == 2
    assert is_string_text(map_get(real, 1), "num")
    assert is_string_text(map_get(real, "1"), "str")


def test_real_map_nested_mapping_is_map():
    outer = unique_token()
    inner = unique_token()
    value = unique_token()
    source = f"{outer}:\n  {inner}: {value}\n"
    print(f"nested mapping={source!r}", flush=True)

    baseline = require_document(load(source))
    base_map = require_plain_mapping(baseline)
    inner_obj = require_plain_mapping(mapping_get(base_map, outer))
    assert is_string_text(mapping_get(inner_obj, inner), value)

    real = require_real_map(
        require_document(load(source, with_real_map_schema()))
    )
    inner_map = require_real_map(map_get(real, outer))
    assert is_string_text(map_get(inner_map, inner), value)


# ---------------------------------------------------------------------------
# E. Legacy-map replacement: stringify keys, keep __proto__, reject nested
# ---------------------------------------------------------------------------


def test_legacy_stringifies_foo_bar_sequence_key():
    require_parse_failure(load(FOO_BAR_BAZ))
    doc = require_document(load(FOO_BAR_BAZ, with_legacy_map_schema()))
    require_plain_mapping(doc)
    print(f"legacy foo,bar keys={list(doc.keys())!r}", flush=True)
    assert is_string_text(mapping_get(doc, "foo,bar"), "baz")


def test_legacy_runtime_sequence_key_is_comma_joined():
    w1, w2, val = unique_token(), unique_token(), unique_token()
    source = explicit_sequence_key_yaml([w1, w2], val)
    print(f"runtime seq-key={source!r}", flush=True)
    require_parse_failure(load(source))
    doc = require_document(load(source, with_legacy_map_schema()))
    require_plain_mapping(doc)
    name = f"{w1},{w2}"
    print(f"joined={name!r} keys={list(doc.keys())!r}", flush=True)
    assert is_string_text(mapping_get(doc, name), val)


def test_legacy_nested_foo_bar_is_comma_joined():
    require_parse_failure(load(NESTED_FOO_BAR))
    doc = require_document(load(NESTED_FOO_BAR, with_legacy_map_schema()))
    wrapper = require_plain_mapping(mapping_get(require_plain_mapping(doc), "wrapper"))
    print(f"nested legacy keys={list(wrapper.keys())!r}", flush=True)
    assert is_string_text(mapping_get(wrapper, "foo,bar"), "baz")


def test_legacy_accepts_mapping_key_as_string_property():
    require_parse_failure(load(MAPPING_KEY_A1))
    doc = require_document(load(MAPPING_KEY_A1, with_legacy_map_schema()))
    mapping = require_plain_mapping(doc)
    print(f"legacy mapping-key keys={list(mapping.keys())!r}", flush=True)
    found = None
    for key in mapping.keys():
        assert isinstance(key, str), (
            f"legacy mapping key must become a string property, got {key!r}"
        )
        if is_string_text(mapping_get(mapping, key), "value"):
            found = key
            break
    assert found is not None, (
        f"value not stored under a string property; keys={list(mapping.keys())!r}"
    )
    rendered = ordinary_js_object_rendering()
    print(f"ordinary rendering={rendered!r} stored={found!r}", flush=True)
    assert is_string_text(found, rendered)
    assert is_string_text(mapping_get(mapping, rendered), "value")


def test_legacy_runtime_mapping_key_is_ordinary_object_rendering():
    mk, mv, outer = unique_token(), unique_token(), unique_token()
    source = explicit_mapping_key_yaml([(mk, mv)], outer)
    print(f"runtime mapping-key={source!r}", flush=True)
    require_parse_failure(load(source))
    doc = require_document(load(source, with_legacy_map_schema()))
    mapping = require_plain_mapping(doc)
    rendered = ordinary_js_object_rendering()
    print(
        f"runtime keys={list(mapping.keys())!r} rendering={rendered!r}",
        flush=True,
    )
    assert is_string_text(mapping_get(mapping, rendered), outer)


def test_legacy_proto_key_is_own_data():
    doc = require_document(load(PROTO_POLLUTED, with_legacy_map_schema()))
    inner = _assert_own_accessor_not_inherited(doc, "polluted")
    inner_map = require_plain_mapping(inner)
    assert is_bool(mapping_get(inner_map, "polluted"), True)


def test_legacy_proto_key_runtime_payload_is_own_data():
    payload = unique_token()
    source = "{ __proto__: { " + payload + ": true } }\n"
    print(f"legacy runtime proto={source!r}", flush=True)
    doc = require_document(load(source, with_legacy_map_schema()))
    inner = _assert_own_accessor_not_inherited(doc, payload)
    inner_map = require_plain_mapping(inner)
    assert is_bool(mapping_get(inner_map, payload), True)


def test_legacy_nested_array_value_succeeds():
    word = unique_token()
    source = f"holder:\n  - - {word}\n"
    print(f"nested-array value={source!r}", flush=True)
    opts = with_legacy_map_schema()
    doc = require_document(load(source, opts))
    holder = require_sequence(mapping_get(require_plain_mapping(doc), "holder"))
    inner = require_sequence(holder[0])
    print(f"holder={holder!r}", flush=True)
    assert is_string_text(inner[0], word)

    # L162 refuses a nested array *inside a key*. The value arm above is
    # the live baseline: the same nested array in value position must
    # remain a sequence-of-sequence. The key arm differs only in that
    # position — an implementation that stringifies nested-array keys
    # stays green on the value arm alone.
    key_src = explicit_nested_array_key_yaml(word)
    print(f"same nested-array as key={key_src!r}", flush=True)
    key_result = load(key_src, opts)
    key_error = require_parse_failure(key_result)
    print(
        f"nested-array key ok={key_result.ok!r} "
        f"report={observer_visible_report(key_error)!r}",
        flush=True,
    )
    assert key_result.ok is False


def test_legacy_alias_of_non_nested_value_succeeds():
    word = unique_token()
    source = f"holder: &a {word}\ncopy: *a\n"
    print(f"non-nested alias={source!r}", flush=True)
    opts = with_legacy_map_schema()
    doc = require_document(load(source, opts))
    mapping = require_plain_mapping(doc)
    assert is_string_text(mapping_get(mapping, "holder"), word)
    assert is_string_text(mapping_get(mapping, "copy"), word)

    # L162 says the same nested-array key delivered through an alias
    # also fails. The scalar-alias arm above is the live baseline:
    # alias delivery itself must work. The key arm uses that same
    # word as a nested-array key via alias — an implementation that
    # stringifies alias-delivered nested-array keys stays green on
    # the scalar-alias arm alone.
    aliased = alias_nested_array_key_yaml(word)
    print(f"same word as alias nested-array key={aliased!r}", flush=True)
    aliased_result = load(aliased, opts)
    aliased_error = require_parse_failure(aliased_result)
    print(
        f"alias nested-array key ok={aliased_result.ok!r} "
        f"report={observer_visible_report(aliased_error)!r}",
        flush=True,
    )
    assert aliased_result.ok is False


def test_legacy_rejects_nested_array_key():
    source = explicit_nested_array_key_yaml("nested")
    result = load(source, with_legacy_map_schema())
    error = require_parse_failure(result)
    print(
        f"nested-array key={source!r} ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_legacy_rejects_nested_array_key_via_alias():
    source = alias_nested_array_key_yaml("nested")
    result = load(source, with_legacy_map_schema())
    error = require_parse_failure(result)
    print(
        f"alias nested-array key={source!r} ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_legacy_rejects_runtime_nested_array_key_and_alias():
    word = unique_token()
    explicit = explicit_nested_array_key_yaml(word)
    explicit_result = load(explicit, with_legacy_map_schema())
    explicit_error = require_parse_failure(explicit_result)
    print(
        f"runtime nested-array key={explicit!r} ok={explicit_result.ok!r} "
        f"report={observer_visible_report(explicit_error)!r}",
        flush=True,
    )
    assert explicit_result.ok is False
    aliased = alias_nested_array_key_yaml(word)
    aliased_result = load(aliased, with_legacy_map_schema())
    aliased_error = require_parse_failure(aliased_result)
    print(
        f"runtime alias nested-array key={aliased!r} ok={aliased_result.ok!r} "
        f"report={observer_visible_report(aliased_error)!r}",
        flush=True,
    )
    assert aliased_result.ok is False


def test_legacy_rejects_sequence_key_containing_nested_array():
    word = unique_token()
    nested = unique_token()
    source = explicit_sequence_key_containing_nested_yaml(word, nested)
    result = load(source, with_legacy_map_schema())
    error = require_parse_failure(result)
    print(
        f"seq-with-nested={source!r} ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False
