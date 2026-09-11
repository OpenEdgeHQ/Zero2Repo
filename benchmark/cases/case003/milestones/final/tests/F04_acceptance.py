# feature: F04
"""YAML 1.1 types and merge keys (FP-04).

Assertions stay at the PRD's precision: constructed types and values
the sentences name, schema-switch contrasts, dump tag presence or
absence, and refusals that yield no usable document. Exception class
names, failure wording, timestamp dump spelling, and the Core form of
a closed YAML 1.1 type are not pinned.
"""

from __future__ import annotations

import uuid

from _harness import JsDate, JsMap, JsObject, JsSet, dump, load, load_all
from _helpers import (
    b64_decode_stripped,
    b64_of,
    binary_scalar_yaml,
    bytes_payload,
    core_type_absent,
    defaults_development_yaml,
    distinct_core_ints,
    dump_then_load,
    is_js_bytes,
    is_js_date,
    is_js_set,
    is_number_not_string,
    is_string_text,
    map_get,
    map_size,
    mapping_get,
    observer_visible_report,
    omap_mapping_yaml,
    require_document,
    require_js_bytes,
    require_js_date,
    require_js_set,
    require_parse_failure,
    require_plain_mapping,
    require_real_map,
    require_sequence,
    require_yaml_text,
    sequence_merge_yaml,
    set_explicit_item_yaml,
    set_member_texts,
    several_merge_keys_yaml,
    unique_token,
    utc_epoch_ms,
    with_core_schema,
    with_merge_on_core,
    with_yaml11_real_map,
    with_yaml11_schema,
)

NAMED_TS_CANONICAL = "2001-12-15T02:59:43.1Z"
NAMED_TS_LOWER_T = "2001-12-14t21:59:43.10-05:00"
NAMED_TS_SPACE_SHORT = "2001-12-14 21:59:43.10 -5"
NAMED_TS_ONE_DIGIT_HOUR = "2001-12-15 2:59:43.10"
NAMED_TS_DATE_ONLY = "2002-12-14"
NAMED_ONE_DIGIT_MONTH = "2002-1-1"

NAMED_TEAMS = ("Boston Red Sox", "Detroit Tigers", "New York Yankees")
NAMED_TEAMS_YAML = (
    "!!set { Boston Red Sox, Detroit Tigers, New York Yankees }\n"
)
NAMED_OMAP_YAML = "!!omap [ one: 1, two: 2, three: 3 ]\n"
NAMED_PAIRS_YAML = "!!pairs [ meeting: with team, meeting: with boss ]\n"
NAMED_PAIRS_COMPLEX = "!!pairs [ ? [ foo, bar ] : baz ]\n"
NAMED_SET_NON_NULL = "!!set\n? key\n: not null\n"
PUBLIC_OMAP_ON_MAPPING = "!!omap\nfoo: bar\nbaz: bat\n"
PUBLIC_OMAP_SCALAR_ITEM = "!!omap\n- foo: bar\n- baz\n"
PUBLIC_OMAP_MULTIKEY = "!!omap\n- foo: bar\n- baz: bar\n  bar: bar\n"
PUBLIC_OMAP_DUP = "!!omap\n- a: 1\n- a: 2\n"
PUBLIC_PAIRS_SCALAR_ITEM = "!!pairs\n- foo: bar\n- baz\n"
PUBLIC_PAIRS_MULTIKEY = "!!pairs\n- foo: bar\n- baz: bar\n  bar: bar\n"
PUBLIC_MERGE_SET = "!!set\n<<: { a: 1 }\n"
PUBLIC_SCALAR_MERGE = "foo: bar\n<<: baz\n"
PUBLIC_SEQ_SCALAR_MERGE = "foo: bar\n<<: [x: 1, y: 2, z, t: 4]\n"

NAMED_IMPOSSIBLE = (
    "2023-02-30",
    "2023-01-01 24:00:00",
    "2023-01-01 00:60:00",
    "2023-01-01 00:00:00 +24",
    "2023-01-01 00:00:00 +1:60",
)

EMPTY_BINARY = "!!binary\n"
EMPTY_TIMESTAMP = "!!timestamp\n"
EMPTY_SET = "!!set\n"
EMPTY_OMAP = "!!omap\n"
EMPTY_PAIRS = "!!pairs\n"


def _canonical_ms() -> int:
    return utc_epoch_ms(2001, 12, 15, 2, 59, 43, 100)


def _date_only_ms() -> int:
    return utc_epoch_ms(2002, 12, 14)


def _named_timestamp_cases() -> list[tuple[str, int]]:
    return [
        (NAMED_TS_CANONICAL, utc_epoch_ms(2001, 12, 15, 2, 59, 43, 100)),
        (NAMED_TS_LOWER_T, utc_epoch_ms(2001, 12, 14, 21, 59, 43, 100, tz_hours=-5)),
        (NAMED_TS_SPACE_SHORT, utc_epoch_ms(2001, 12, 14, 21, 59, 43, 100, tz_hours=-5)),
        (NAMED_TS_ONE_DIGIT_HOUR, utc_epoch_ms(2001, 12, 15, 2, 59, 43, 100)),
        (NAMED_TS_DATE_ONLY, utc_epoch_ms(2002, 12, 14)),
    ]


def _assert_epoch(value, expected_ms: int, *, what: str) -> None:
    observed = require_js_date(value)
    print(f"{what} epoch_ms={observed.epoch_ms} expected={expected_ms}", flush=True)
    assert observed.epoch_ms == expected_ms, (
        f"{what} must be UTC ms {expected_ms}, got {observed.epoch_ms}"
    )


def _has_key(mapping, key: str) -> bool:
    return key in require_plain_mapping(mapping)


def _plain_props(item):
    if isinstance(item, JsMap):
        return None
    if isinstance(item, dict):
        return item
    if isinstance(item, JsObject):
        return item.props
    return None


def _looks_like_named_omap(value) -> bool:
    if not isinstance(value, list) or len(value) != 3:
        return False
    expected = (("one", 1), ("two", 2), ("three", 3))
    for item, (key, number) in zip(value, expected):
        mapping = _plain_props(item)
        if mapping is None:
            return False
        if list(mapping.keys()) != [key]:
            return False
        if not is_number_not_string(mapping.get(key), number):
            return False
    return True


def _looks_like_named_pairs(value) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    expected = (("meeting", "with team"), ("meeting", "with boss"))
    for item, (key, text) in zip(value, expected):
        if not isinstance(item, list) or len(item) != 2:
            return False
        if not is_string_text(item[0], key) or not is_string_text(item[1], text):
            return False
    return True


def _runtime_one_digit_month() -> str:
    n = uuid.uuid4().int
    year = 2010 + (n % 14)
    month = 1 + ((n >> 8) % 9)
    day = 1 + ((n >> 16) % 27)
    if year == 2002 and month == 1 and day == 1:
        day = 2
    return f"{year}-{month}-{day}"


def _runtime_impossible_day() -> str:
    year = 2011 + (uuid.uuid4().int % 10)
    return f"{year}-04-31"


def _runtime_named_shape() -> tuple[str, int]:
    n = uuid.uuid4().int
    year = 2014 + (n % 7)
    month = 3 + ((n >> 4) % 8)
    day = 2 + ((n >> 8) % 26)
    hour = 3 + ((n >> 16) % 8)
    minute = 4 + ((n >> 20) % 50)
    second = 5 + ((n >> 24) % 50)
    tenths = 2 + ((n >> 28) % 7)
    tz_hours = 2 + ((n >> 32) % 6)
    if year == 2001 and month == 12 and day in (14, 15):
        day = 16
    if year == 2002 and month == 12 and day == 14:
        day = 15
    text = (
        f"{year}-{month:02d}-{day:02d}t{hour:02d}:{minute:02d}:"
        f"{second:02d}.{tenths}0+{tz_hours:02d}:00"
    )
    expected = utc_epoch_ms(
        year, month, day, hour, minute, second, tenths * 100, tz_hours=tz_hours
    )
    return text, expected


def _assert_single_key_object(item, key: str, number: int) -> None:
    mapping = require_plain_mapping(item)
    assert not isinstance(item, JsMap), f"omap item must be a plain object, got Map"
    assert list(mapping.keys()) == [key], f"omap item keys={list(mapping.keys())!r}"
    assert is_number_not_string(mapping_get(mapping, key), number), (
        f"omap[{key!r}] must be number {number}, got {mapping_get(mapping, key)!r}"
    )


# ---------------------------------------------------------------------------
# A. !!binary
# ---------------------------------------------------------------------------


def test_yaml11_binary_runtime_bytes():
    payload = bytes_payload()
    b64 = b64_of(payload)
    source = binary_scalar_yaml(b64)
    print(f"source={source!r} payload_len={len(payload)}", flush=True)
    value = require_js_bytes(require_document(load(source, with_yaml11_schema())))
    print(f"bytes={value.data!r}", flush=True)
    assert value.data == payload, f"decoded bytes {value.data!r} != {payload!r}"
    assert value.data != b64.encode("ascii"), "result must be bytes, not Base64 text"


def test_yaml11_binary_ignores_whitespace():
    payload = bytes_payload()
    b64 = b64_of(payload)
    source = binary_scalar_yaml(b64, insert_whitespace=" \t\n ")
    expected = b64_decode_stripped(source.split('"', 2)[1])
    print(f"source={source!r} expected={expected!r}", flush=True)
    value = require_js_bytes(require_document(load(source, with_yaml11_schema())))
    assert value.data == expected, f"whitespace Base64 {value.data!r} != {expected!r}"
    assert expected == payload


def test_yaml11_binary_dump_round_trip():
    payload = bytes_payload()
    dumped = dump(payload, with_yaml11_schema())
    text = require_yaml_text(dumped)
    print(f"dump={text!r}", flush=True)
    assert "!!binary" in text, f"dump must write !!binary; got {text!r}"
    restored = require_js_bytes(
        require_document(load(text, with_yaml11_schema()))
    )
    assert restored.data == payload, f"round-trip {restored.data!r} != {payload!r}"


def test_yaml11_empty_binary_is_empty_bytes():
    value = require_js_bytes(
        require_document(load(EMPTY_BINARY, with_yaml11_schema()))
    )
    print(f"empty binary len={len(value.data)}", flush=True)
    assert len(value.data) == 0, f"empty !!binary must be length 0, got {value.data!r}"


def test_yaml11_empty_binary_dump_round_trip():
    parsed = require_js_bytes(
        require_document(load(EMPTY_BINARY, with_yaml11_schema()))
    )
    assert len(parsed.data) == 0
    dumped = dump(b"", with_yaml11_schema())
    text = require_yaml_text(dumped)
    print(f"empty dump={text!r}", flush=True)
    assert "!!binary" in text, f"empty bytes dump must write !!binary; got {text!r}"
    restored = require_js_bytes(
        require_document(load(text, with_yaml11_schema()))
    )
    assert len(restored.data) == 0, f"empty dump-then-parse {restored.data!r}"


def test_yaml11_binary_rejects_invalid_base64():
    samples = (
        '!!binary "@@@@"\n',
        '!!binary "AAA"\n',
        f'!!binary "{unique_token()[:4]}!!!!"\n',
        '!!binary "AAAAA"\n',
    )
    for source in samples:
        print(f"invalid binary source={source!r}", flush=True)
        failed = load(source, with_yaml11_schema())
        error = require_parse_failure(failed)
        print(
            f"invalid binary ok={failed.ok!r} "
            f"report={observer_visible_report(error)}",
            flush=True,
        )
        assert failed.ok is False, (
            "invalid Base64 must fail and yield no document"
        )


def test_core_binary_is_not_byte_array():
    payload = bytes_payload()
    source = binary_scalar_yaml(b64_of(payload))
    yaml11 = require_js_bytes(
        require_document(load(source, with_yaml11_schema()))
    )
    assert yaml11.data == payload
    core_type_absent(load(source, with_core_schema()), is_js_bytes)


def test_yaml11_binary_on_multi_document():
    payload = bytes_payload()
    source = (
        "---\n"
        f"{binary_scalar_yaml(b64_of(payload))}"
        "---\n"
        f"{NAMED_TS_CANONICAL}\n"
    )
    print(f"multi source={source!r}", flush=True)
    docs = require_sequence(
        require_document(load_all(source, with_yaml11_schema()))
    )
    assert len(docs) == 2, f"expected 2 documents, got {len(docs)}"
    assert require_js_bytes(docs[0]).data == payload
    _assert_epoch(docs[1], _canonical_ms(), what="multi-doc timestamp")


# ---------------------------------------------------------------------------
# B. !!timestamp
# ---------------------------------------------------------------------------


def test_yaml11_named_timestamps_are_utc_instants():
    for text, expected in _named_timestamp_cases():
        print(f"named timestamp {text!r} expected={expected}", flush=True)
        value = require_document(load(text, with_yaml11_schema()))
        _assert_epoch(value, expected, what=text)
        assert not isinstance(value, str), f"{text!r} must be a date, not a string"


def test_yaml11_timestamp_runtime_named_shape():
    text, expected = _runtime_named_shape()
    print(f"runtime shape={text!r} expected={expected}", flush=True)
    value = require_document(load(text, with_yaml11_schema()))
    _assert_epoch(value, expected, what="runtime named shape")


def test_yaml11_explicit_named_timestamp():
    # L179 names the calendar strings as implicit constructors. Explicit
    # !!timestamp is promised only for an empty node (fails) and for
    # impossible calendar values (fail). Tagging a valid implicit form
    # with !!timestamp is not a promised constructor.
    for text, expected in _named_timestamp_cases():
        print(f"implicit constructor {text!r} expected={expected}", flush=True)
        value = require_document(load(text, with_yaml11_schema()))
        _assert_epoch(value, expected, what=text)
        assert not isinstance(value, str), f"{text!r} must be a date, not a string"

    empty_err = require_parse_failure(load(EMPTY_TIMESTAMP, with_yaml11_schema()))
    print(f"empty explicit report={observer_visible_report(empty_err)}", flush=True)

    extras = (_runtime_impossible_day(),)
    for text in NAMED_IMPOSSIBLE + extras:
        explicit_src = f"!!timestamp {text}\n"
        print(f"impossible explicit={explicit_src!r}", flush=True)
        error = require_parse_failure(load(explicit_src, with_yaml11_schema()))
        print(f"report={observer_visible_report(error)}", flush=True)


def test_yaml11_one_digit_month_stays_string():
    baseline = require_document(load(NAMED_TS_DATE_ONLY, with_yaml11_schema()))
    _assert_epoch(baseline, _date_only_ms(), what="two-digit month baseline")

    public = require_document(load(NAMED_ONE_DIGIT_MONTH, with_yaml11_schema()))
    print(f"public one-digit={public!r}", flush=True)
    assert is_string_text(public, NAMED_ONE_DIGIT_MONTH), (
        f"{NAMED_ONE_DIGIT_MONTH!r} must stay that string, got {public!r}"
    )
    assert not is_js_date(public)

    runtime = _runtime_one_digit_month()
    print(f"runtime one-digit={runtime!r}", flush=True)
    value = require_document(load(runtime, with_yaml11_schema()))
    assert is_string_text(value, runtime), (
        f"{runtime!r} must stay that string, got {value!r}"
    )
    assert not is_js_date(value)


def test_yaml11_impossible_calendar_implicit_string_explicit_fails():
    extras = (_runtime_impossible_day(),)
    for text in NAMED_IMPOSSIBLE + extras:
        print(f"impossible implicit={text!r}", flush=True)
        implicit = require_document(load(text, with_yaml11_schema()))
        assert is_string_text(implicit, text), (
            f"implicit {text!r} must stay that string, got {implicit!r}"
        )
        assert not is_js_date(implicit)
        explicit_src = f"!!timestamp {text}\n"
        print(f"impossible explicit={explicit_src!r}", flush=True)
        error = require_parse_failure(load(explicit_src, with_yaml11_schema()))
        print(f"report={observer_visible_report(error)}", flush=True)


def test_yaml11_timestamp_dump_round_trip():
    parsed = require_js_date(
        require_document(load(NAMED_TS_CANONICAL, with_yaml11_schema()))
    )
    assert parsed.epoch_ms == _canonical_ms()
    restored = require_js_date(
        require_document(dump_then_load(parsed, with_yaml11_schema()))
    )
    print(f"named dump-then-load ms={restored.epoch_ms}", flush=True)
    assert restored.epoch_ms == _canonical_ms()


def test_yaml11_runtime_date_dump_round_trip():
    ms = utc_epoch_ms(2016, 7, 4, 13, 21, 8, 250)
    constructed = JsDate(epoch_ms=float(ms), iso="", object_id=-1)
    restored = require_js_date(
        require_document(dump_then_load(constructed, with_yaml11_schema()))
    )
    print(f"runtime dump-then-load ms={restored.epoch_ms} expected={ms}", flush=True)
    assert restored.epoch_ms == ms, (
        f"runtime date dump-then-parse {restored.epoch_ms} != {ms}"
    )


def test_yaml11_empty_timestamp_fails():
    empty_bin = require_js_bytes(
        require_document(load(EMPTY_BINARY, with_yaml11_schema()))
    )
    assert len(empty_bin.data) == 0
    error = require_parse_failure(load(EMPTY_TIMESTAMP, with_yaml11_schema()))
    print(f"empty timestamp report={observer_visible_report(error)}", flush=True)


def test_core_named_timestamp_is_not_a_date():
    yaml11 = require_document(load(NAMED_TS_CANONICAL, with_yaml11_schema()))
    _assert_epoch(yaml11, _canonical_ms(), what="yaml11 baseline")
    core_type_absent(load(NAMED_TS_CANONICAL, with_core_schema()), is_js_date)


# ---------------------------------------------------------------------------
# C. !!set
# ---------------------------------------------------------------------------


def test_yaml11_set_named_teams():
    value = require_js_set(
        require_document(load(NAMED_TEAMS_YAML, with_yaml11_schema()))
    )
    members = set_member_texts(value)
    print(f"named teams={members!r}", flush=True)
    assert members == set(NAMED_TEAMS), f"set members {members!r} != {NAMED_TEAMS!r}"


def test_yaml11_set_runtime_members():
    left, right = unique_token(), unique_token()
    source = f"!!set {{ {left}, {right} }}\n"
    print(f"runtime set source={source!r}", flush=True)
    members = set_member_texts(
        require_document(load(source, with_yaml11_schema()))
    )
    assert members == {left, right}, f"runtime set {members!r}"


def test_yaml11_set_dump_has_tag_and_round_trip():
    public = JsSet(items=list(NAMED_TEAMS), object_id=-1)
    public_text = require_yaml_text(dump(public, with_yaml11_schema()))
    print(f"public set dump={public_text!r}", flush=True)
    assert "!!set" in public_text, f"dump must write !!set; got {public_text!r}"
    public_back = set_member_texts(
        require_document(load(public_text, with_yaml11_schema()))
    )
    assert public_back == set(NAMED_TEAMS)

    left, right = unique_token(), unique_token()
    runtime = JsSet(items=[left, right], object_id=-1)
    runtime_text = require_yaml_text(dump(runtime, with_yaml11_schema()))
    print(f"runtime set dump={runtime_text!r}", flush=True)
    assert "!!set" in runtime_text
    runtime_back = set_member_texts(
        require_document(load(runtime_text, with_yaml11_schema()))
    )
    assert runtime_back == {left, right}


def test_yaml11_empty_set():
    value = require_js_set(
        require_document(load(EMPTY_SET, with_yaml11_schema()))
    )
    print(f"empty set size={len(value)}", flush=True)
    assert len(value) == 0, f"empty !!set must have size 0, got {value!r}"


def test_yaml11_empty_set_dump_round_trip():
    empty = JsSet(items=[], object_id=-1)
    text = require_yaml_text(dump(empty, with_yaml11_schema()))
    print(f"empty set dump={text!r}", flush=True)
    assert "!!set" in text, f"empty Set dump must write !!set; got {text!r}"
    restored = require_js_set(
        require_document(load(text, with_yaml11_schema()))
    )
    assert len(restored) == 0


def test_yaml11_set_explicit_key_null_succeeds():
    word = unique_token()
    source = set_explicit_item_yaml(word)
    print(f"set ?-null source={source!r}", flush=True)
    members = set_member_texts(
        require_document(load(source, with_yaml11_schema()))
    )
    assert members == {word}, f"?-null set {members!r}"


def test_yaml11_set_rejects_non_null_item():
    word = unique_token()
    live = set_explicit_item_yaml(word)
    assert set_member_texts(
        require_document(load(live, with_yaml11_schema()))
    ) == {word}

    public_err = require_parse_failure(
        load(NAMED_SET_NON_NULL, with_yaml11_schema())
    )
    print(f"public non-null report={observer_visible_report(public_err)}", flush=True)
    runtime = set_explicit_item_yaml(unique_token(), unique_token())
    print(f"runtime non-null source={runtime!r}", flush=True)
    runtime_err = require_parse_failure(load(runtime, with_yaml11_schema()))
    print(f"runtime non-null report={observer_visible_report(runtime_err)}", flush=True)


def test_core_set_is_not_a_set():
    yaml11 = require_js_set(
        require_document(load(NAMED_TEAMS_YAML, with_yaml11_schema()))
    )
    assert set_member_texts(yaml11) == set(NAMED_TEAMS)
    core_type_absent(load(NAMED_TEAMS_YAML, with_core_schema()), is_js_set)


# ---------------------------------------------------------------------------
# D. !!omap
# ---------------------------------------------------------------------------


def test_yaml11_omap_named_numbers():
    doc = require_sequence(
        require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    )
    print(f"named omap len={len(doc)}", flush=True)
    assert len(doc) == 3
    for item, key, number in zip(doc, ("one", "two", "three"), (1, 2, 3)):
        _assert_single_key_object(item, key, number)


def test_yaml11_omap_runtime_items():
    keys = [unique_token(), unique_token(), unique_token()]
    values = distinct_core_ints(3)
    lines = ["!!omap"]
    for key, number in zip(keys, values):
        lines.append(f"- {key}: {number}")
    source = "\n".join(lines) + "\n"
    print(f"runtime omap source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 3
    for item, key, number in zip(doc, keys, values):
        _assert_single_key_object(item, key, number)


def test_yaml11_empty_omap():
    doc = require_sequence(
        require_document(load(EMPTY_OMAP, with_yaml11_schema()))
    )
    print(f"empty omap={doc!r}", flush=True)
    assert doc == [], f"empty !!omap must be [], got {doc!r}"


def test_yaml11_omap_on_mapping_fails():
    live = require_sequence(
        require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    )
    assert len(live) == 3
    public_err = require_parse_failure(
        load(PUBLIC_OMAP_ON_MAPPING, with_yaml11_schema())
    )
    print(f"public omap-map report={observer_visible_report(public_err)}", flush=True)
    runtime = omap_mapping_yaml(((unique_token(), unique_token()),))
    print(f"runtime omap-map source={runtime!r}", flush=True)
    runtime_err = require_parse_failure(load(runtime, with_yaml11_schema()))
    print(f"runtime omap-map report={observer_visible_report(runtime_err)}", flush=True)


def test_yaml11_omap_rejects_bad_items():
    dup_key = unique_token()
    runtime_sources = (
        f"!!omap\n- {unique_token()}\n",
        f"!!omap\n- {unique_token()}: 1\n  {unique_token()}: 2\n",
        f"!!omap\n- {dup_key}: 1\n- {dup_key}: 2\n",
    )
    for source in (PUBLIC_OMAP_SCALAR_ITEM, PUBLIC_OMAP_MULTIKEY, PUBLIC_OMAP_DUP) + runtime_sources:
        print(f"bad omap source={source!r}", flush=True)
        failed = load(source, with_yaml11_schema())
        error = require_parse_failure(failed)
        print(
            f"bad omap ok={failed.ok!r} "
            f"report={observer_visible_report(error)}",
            flush=True,
        )
        assert failed.ok is False, (
            "a scalar, multi-key, or repeated-key !!omap item must fail "
            "and yield no document"
        )


def test_yaml11_omap_dump_is_plain_sequence():
    parsed = require_sequence(
        require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    )
    text = require_yaml_text(dump(parsed, with_yaml11_schema()))
    print(f"omap dump={text!r}", flush=True)
    assert "!!omap" not in text, f"omap dump must not write !!omap; got {text!r}"
    restored = require_sequence(
        require_document(load(text, with_yaml11_schema()))
    )
    assert len(restored) == 3
    for item, key, number in zip(restored, ("one", "two", "three"), (1, 2, 3)):
        _assert_single_key_object(item, key, number)

    keys = [unique_token(), unique_token(), unique_token()]
    values = distinct_core_ints(3)
    lines = ["!!omap"]
    for key, number in zip(keys, values):
        lines.append(f"- {key}: {number}")
    runtime = require_sequence(
        require_document(load("\n".join(lines) + "\n", with_yaml11_schema()))
    )
    runtime_text = require_yaml_text(dump(runtime, with_yaml11_schema()))
    print(f"runtime omap dump={runtime_text!r}", flush=True)
    assert "!!omap" not in runtime_text
    runtime_back = require_sequence(
        require_document(load(runtime_text, with_yaml11_schema()))
    )
    assert len(runtime_back) == 3
    for item, key, number in zip(runtime_back, keys, values):
        _assert_single_key_object(item, key, number)


def test_yaml11_omap_real_map_items_are_maps():
    default = require_sequence(
        require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    )
    assert len(default) == 3
    for item in default:
        require_plain_mapping(item)
        assert not isinstance(item, JsMap)

    real = require_sequence(
        require_document(load(NAMED_OMAP_YAML, with_yaml11_real_map()))
    )
    print(f"real-map omap types={[type(item).__name__ for item in real]}", flush=True)
    assert len(real) == 3
    for item, key, number in zip(real, ("one", "two", "three"), (1, 2, 3)):
        mapping = require_real_map(item)
        assert map_size(mapping) == 1
        assert is_number_not_string(map_get(mapping, key), number)

    keys = [unique_token(), unique_token(), unique_token()]
    values = distinct_core_ints(3)
    lines = ["!!omap"]
    for key, number in zip(keys, values):
        lines.append(f"- {key}: {number}")
    source = "\n".join(lines) + "\n"
    runtime = require_sequence(
        require_document(load(source, with_yaml11_real_map()))
    )
    assert len(runtime) == 3
    for item, key, number in zip(runtime, keys, values):
        mapping = require_real_map(item)
        assert map_size(mapping) == 1
        assert is_number_not_string(map_get(mapping, key), number)


def test_core_omap_is_not_yaml11_omap():
    yaml11 = require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    assert _looks_like_named_omap(yaml11)
    core_type_absent(load(NAMED_OMAP_YAML, with_core_schema()), _looks_like_named_omap)


# ---------------------------------------------------------------------------
# E. !!pairs
# ---------------------------------------------------------------------------


def test_yaml11_pairs_named_meetings():
    doc = require_sequence(
        require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    )
    print(f"named pairs={doc!r}", flush=True)
    assert _looks_like_named_pairs(doc), f"named pairs {doc!r}"


def test_yaml11_pairs_runtime_scalar_pairs():
    key, value = unique_token(), unique_token()
    one = f"!!pairs [ {key}: {value} ]\n"
    print(f"one pair source={one!r}", flush=True)
    one_doc = require_sequence(
        require_document(load(one, with_yaml11_schema()))
    )
    assert len(one_doc) == 1
    pair = require_sequence(one_doc[0])
    assert len(pair) == 2
    assert is_string_text(pair[0], key) and is_string_text(pair[1], value)

    shared = unique_token()
    first, second = unique_token(), unique_token()
    two = f"!!pairs [ {shared}: {first}, {shared}: {second} ]\n"
    print(f"dup pair source={two!r}", flush=True)
    two_doc = require_sequence(
        require_document(load(two, with_yaml11_schema()))
    )
    assert len(two_doc) == 2, f"duplicate keys must keep two pairs, got {two_doc!r}"
    p0, p1 = require_sequence(two_doc[0]), require_sequence(two_doc[1])
    assert is_string_text(p0[0], shared) and is_string_text(p0[1], first)
    assert is_string_text(p1[0], shared) and is_string_text(p1[1], second)


def test_yaml11_empty_pairs():
    doc = require_sequence(
        require_document(load(EMPTY_PAIRS, with_yaml11_schema()))
    )
    print(f"empty pairs={doc!r}", flush=True)
    assert doc == [], f"empty !!pairs must be [], got {doc!r}"


def test_yaml11_pairs_rejects_scalar_and_multikey_items():
    live = require_sequence(
        require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    )
    assert _looks_like_named_pairs(live)
    sources = (
        PUBLIC_PAIRS_SCALAR_ITEM,
        PUBLIC_PAIRS_MULTIKEY,
        f"!!pairs\n- {unique_token()}\n",
        f"!!pairs\n- {unique_token()}: a\n  {unique_token()}: b\n",
    )
    for source in sources:
        print(f"bad pairs source={source!r}", flush=True)
        error = require_parse_failure(load(source, with_yaml11_schema()))
        print(f"report={observer_visible_report(error)}", flush=True)


def test_yaml11_pairs_default_rejects_complex_key():
    live = require_sequence(
        require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    )
    assert _looks_like_named_pairs(live)
    error = require_parse_failure(
        load(NAMED_PAIRS_COMPLEX, with_yaml11_schema())
    )
    print(f"complex key default report={observer_visible_report(error)}", flush=True)


def test_yaml11_pairs_real_map_preserves_complex_key():
    error = require_parse_failure(
        load(NAMED_PAIRS_COMPLEX, with_yaml11_schema())
    )
    print(f"default contrast report={observer_visible_report(error)}", flush=True)
    doc = require_sequence(
        require_document(load(NAMED_PAIRS_COMPLEX, with_yaml11_real_map()))
    )
    print(f"real-map pairs={doc!r}", flush=True)
    assert len(doc) == 1
    pair = require_sequence(doc[0])
    assert len(pair) == 2
    key = require_sequence(pair[0])
    assert len(key) == 2
    assert is_string_text(key[0], "foo") and is_string_text(key[1], "bar")
    assert is_string_text(pair[1], "baz")


def test_yaml11_pairs_runtime_complex_key():
    left, right, value = unique_token(), unique_token(), unique_token()
    source = f"!!pairs [ ? [ {left}, {right} ] : {value} ]\n"
    print(f"runtime complex source={source!r}", flush=True)
    default_err = require_parse_failure(load(source, with_yaml11_schema()))
    print(f"default report={observer_visible_report(default_err)}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_real_map()))
    )
    assert len(doc) == 1
    pair = require_sequence(doc[0])
    key = require_sequence(pair[0])
    assert is_string_text(key[0], left) and is_string_text(key[1], right)
    assert is_string_text(pair[1], value)


def test_yaml11_pairs_dump_is_not_pairs_node():
    parsed = require_sequence(
        require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    )
    print(f"constructed pairs={parsed!r}", flush=True)
    assert _looks_like_named_pairs(parsed), (
        "dump path requires a constructed pairs value "
        f"(array of two-element arrays); got {parsed!r}"
    )
    text = require_yaml_text(dump(parsed, with_yaml11_schema()))
    print(f"pairs dump={text!r}", flush=True)
    assert "!!pairs" not in text, f"pairs dump must not write !!pairs; got {text!r}"
    restored = require_sequence(
        require_document(load(text, with_yaml11_schema()))
    )
    print(f"pairs dump-then-load={restored!r}", flush=True)


def test_core_pairs_is_not_yaml11_pairs():
    yaml11 = require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    assert _looks_like_named_pairs(yaml11)
    core_type_absent(load(NAMED_PAIRS_YAML, with_core_schema()), _looks_like_named_pairs)


# ---------------------------------------------------------------------------
# F. Merge keys
# ---------------------------------------------------------------------------


def _assert_literal_merge(dev, adapter: str, host: str, database: str) -> None:
    require_plain_mapping(dev)
    assert _has_key(dev, "<<"), "Core without merge must keep a << property"
    defaults = mapping_get(dev, "<<")
    assert is_string_text(mapping_get(defaults, "adapter"), adapter)
    assert is_string_text(mapping_get(defaults, "host"), host)
    assert is_string_text(mapping_get(dev, "database"), database)
    assert not _has_key(dev, "adapter"), "development must not own adapter"
    assert not _has_key(dev, "host"), "development must not own host"


def _assert_applied_merge(dev, adapter: str, host: str, database: str) -> None:
    require_plain_mapping(dev)
    assert is_string_text(mapping_get(dev, "adapter"), adapter)
    assert is_string_text(mapping_get(dev, "host"), host)
    assert is_string_text(mapping_get(dev, "database"), database)
    assert not _has_key(dev, "<<"), "merged development must not keep <<"


def test_core_without_merge_keeps_literal_key():
    source = defaults_development_yaml("postgres", "localhost", "app_development")
    print(f"core no-merge source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(source, with_core_schema()))
    )
    _assert_literal_merge(
        mapping_get(doc, "development"),
        "postgres",
        "localhost",
        "app_development",
    )


def test_yaml11_applies_merge():
    source = defaults_development_yaml("postgres", "localhost", "app_development")
    doc = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    _assert_applied_merge(
        mapping_get(doc, "development"),
        "postgres",
        "localhost",
        "app_development",
    )


def test_core_with_merge_tag_applies_merge():
    source = defaults_development_yaml("postgres", "localhost", "app_development")
    core = require_plain_mapping(
        require_document(load(source, with_core_schema()))
    )
    _assert_literal_merge(
        mapping_get(core, "development"),
        "postgres",
        "localhost",
        "app_development",
    )
    merged = require_plain_mapping(
        require_document(load(source, with_merge_on_core()))
    )
    _assert_applied_merge(
        mapping_get(merged, "development"),
        "postgres",
        "localhost",
        "app_development",
    )


def test_core_with_merge_keeps_core_types():
    source = defaults_development_yaml("postgres", "localhost", "app_development")
    merged = require_plain_mapping(
        require_document(load(source, with_merge_on_core()))
    )
    _assert_applied_merge(
        mapping_get(merged, "development"),
        "postgres",
        "localhost",
        "app_development",
    )
    yaml11_ts = require_document(load(NAMED_TS_CANONICAL, with_yaml11_schema()))
    _assert_epoch(yaml11_ts, _canonical_ms(), what="yaml11 timestamp baseline")
    payload = bytes_payload()
    binary_src = binary_scalar_yaml(b64_of(payload))
    yaml11_bin = require_js_bytes(
        require_document(load(binary_src, with_yaml11_schema()))
    )
    assert yaml11_bin.data == payload
    core_type_absent(load(NAMED_TS_CANONICAL, with_merge_on_core()), is_js_date)
    core_type_absent(load(binary_src, with_merge_on_core()), is_js_bytes)


def test_merge_runtime_defaults_development():
    adapter, host, database = unique_token(), unique_token(), unique_token()
    source = defaults_development_yaml(adapter, host, database)
    print(f"runtime merge source={source!r}", flush=True)
    core = require_plain_mapping(
        require_document(load(source, with_core_schema()))
    )
    _assert_literal_merge(mapping_get(core, "development"), adapter, host, database)
    yaml11 = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    _assert_applied_merge(mapping_get(yaml11, "development"), adapter, host, database)
    tagged = require_plain_mapping(
        require_document(load(source, with_merge_on_core()))
    )
    _assert_applied_merge(mapping_get(tagged, "development"), adapter, host, database)


def test_several_merge_keys_all_apply():
    public = several_merge_keys_yaml({"x": 1, "y": 2}, "foo", "bar", {"z": 3, "t": 4})
    print(f"several public={public!r}", flush=True)
    # `y` is a YAML 1.1 boolean word; the PRD names the key `y`, which is
    # the Core+merge reading of this exact document (L183).
    doc = require_plain_mapping(
        require_document(load(public, with_merge_on_core()))
    )
    assert is_number_not_string(mapping_get(doc, "x"), 1)
    assert is_number_not_string(mapping_get(doc, "y"), 2)
    assert is_string_text(mapping_get(doc, "foo"), "bar")
    assert is_number_not_string(mapping_get(doc, "z"), 3)
    assert is_number_not_string(mapping_get(doc, "t"), 4)

    keys = [unique_token() for _ in range(5)]
    values = distinct_core_ints(4)
    middle = unique_token()
    runtime = several_merge_keys_yaml(
        {keys[0]: values[0], keys[1]: values[1]},
        keys[2],
        middle,
        {keys[3]: values[2], keys[4]: values[3]},
    )
    print(f"several runtime={runtime!r}", flush=True)
    runtime_doc = require_plain_mapping(
        require_document(load(runtime, with_merge_on_core()))
    )
    assert is_number_not_string(mapping_get(runtime_doc, keys[0]), values[0])
    assert is_number_not_string(mapping_get(runtime_doc, keys[1]), values[1])
    assert is_string_text(mapping_get(runtime_doc, keys[2]), middle)
    assert is_number_not_string(mapping_get(runtime_doc, keys[3]), values[2])
    assert is_number_not_string(mapping_get(runtime_doc, keys[4]), values[3])


def test_explicit_pair_overrides_merged_pair():
    baseline = sequence_merge_yaml({"r": 10}, {"x": 0})
    base_doc = require_plain_mapping(
        require_document(load(baseline, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(base_doc, "x"), 0)
    assert is_number_not_string(mapping_get(base_doc, "r"), 10)

    public = sequence_merge_yaml({"r": 10}, {"x": 0}, explicit={"x": 1})
    print(f"explicit after={public!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(public, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(doc, "x"), 1)
    assert is_number_not_string(mapping_get(doc, "r"), 10)

    key = unique_token()
    n1, n2 = distinct_core_ints(2)
    runtime = sequence_merge_yaml({key: n1}, {"r": n1}, explicit={key: n2})
    print(f"runtime explicit={runtime!r}", flush=True)
    runtime_doc = require_plain_mapping(
        require_document(load(runtime, with_merge_on_core()))
    )
    assert is_number_not_string(mapping_get(runtime_doc, key), n2)


def test_explicit_pair_before_merge_still_wins():
    after = sequence_merge_yaml({"r": 10}, {"x": 0}, explicit={"x": 1})
    after_doc = require_plain_mapping(
        require_document(load(after, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(after_doc, "x"), 1)
    assert is_number_not_string(mapping_get(after_doc, "r"), 10)

    before = sequence_merge_yaml(
        {"r": 10}, {"x": 0}, explicit={"x": 1}, explicit_before=True
    )
    print(f"explicit before={before!r}", flush=True)
    before_doc = require_plain_mapping(
        require_document(load(before, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(before_doc, "x"), 1)
    assert is_number_not_string(mapping_get(before_doc, "r"), 10)

    key = unique_token()
    n1, n2 = distinct_core_ints(2)
    runtime = sequence_merge_yaml(
        {key: n1}, {"r": n1}, explicit={key: n2}, explicit_before=True
    )
    print(f"runtime explicit before={runtime!r}", flush=True)
    runtime_doc = require_plain_mapping(
        require_document(load(runtime, with_merge_on_core()))
    )
    assert is_number_not_string(mapping_get(runtime_doc, key), n2)


def test_merge_sequence_keeps_earlier_key():
    source = sequence_merge_yaml({"r": 10}, {"r": 1})
    print(f"earlier key source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(doc, "r"), 10)


def test_merge_sequence_copies_later_unique_key():
    key_a, key_b = unique_token(), unique_token()
    n1, n2, n3 = distinct_core_ints(3)
    source = sequence_merge_yaml({key_a: n1}, {key_a: n2, key_b: n3})
    print(f"later unique source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(source, with_merge_on_core()))
    )
    assert is_number_not_string(mapping_get(doc, key_a), n1)
    assert is_number_not_string(mapping_get(doc, key_b), n3)


def test_merge_into_set_rejects_non_null():
    live_word = unique_token()
    live = require_js_set(
        require_document(
            load(f"!!set {{ {live_word} }}\n", with_yaml11_schema())
        )
    )
    assert set_member_texts(live) == {live_word}
    public_err = require_parse_failure(
        load(PUBLIC_MERGE_SET, with_yaml11_schema())
    )
    print(f"set merge public={observer_visible_report(public_err)}", flush=True)
    runtime_key, runtime_val = unique_token(), unique_token()
    runtime = f"!!set\n<<: {{ {runtime_key}: {runtime_val} }}\n"
    print(f"set merge runtime={runtime!r}", flush=True)
    runtime_err = require_parse_failure(load(runtime, with_yaml11_schema()))
    print(f"set merge runtime report={observer_visible_report(runtime_err)}", flush=True)


def test_merge_rejects_scalar_source():
    public_scalar = load(PUBLIC_SCALAR_MERGE, with_yaml11_schema())
    public_scalar_err = require_parse_failure(public_scalar)
    print(
        f"scalar merge ok={public_scalar.ok!r} "
        f"report={observer_visible_report(public_scalar_err)}",
        flush=True,
    )
    assert public_scalar.ok is False, (
        "a scalar merge source must fail and yield no document"
    )

    public_seq = load(PUBLIC_SEQ_SCALAR_MERGE, with_yaml11_schema())
    public_seq_err = require_parse_failure(public_seq)
    print(
        f"seq scalar merge ok={public_seq.ok!r} "
        f"report={observer_visible_report(public_seq_err)}",
        flush=True,
    )
    assert public_seq.ok is False, (
        "a merge sequence that contains a scalar must fail and yield no document"
    )

    word = unique_token()
    runtime_scalar = f"keep: 1\n<<: {word}\n"
    print(f"runtime scalar merge={runtime_scalar!r}", flush=True)
    runtime_scalar_result = load(runtime_scalar, with_merge_on_core())
    runtime_scalar_err = require_parse_failure(runtime_scalar_result)
    print(
        f"runtime scalar ok={runtime_scalar_result.ok!r} "
        f"report={observer_visible_report(runtime_scalar_err)}",
        flush=True,
    )
    assert runtime_scalar_result.ok is False, (
        "a runtime scalar merge source must fail and yield no document"
    )

    runtime_seq = f"keep: 1\n<<: [{{ x: 1 }}, {word}]\n"
    print(f"runtime seq scalar merge={runtime_seq!r}", flush=True)
    runtime_seq_result = load(runtime_seq, with_merge_on_core())
    runtime_seq_err = require_parse_failure(runtime_seq_result)
    print(
        f"runtime seq scalar ok={runtime_seq_result.ok!r} "
        f"report={observer_visible_report(runtime_seq_err)}",
        flush=True,
    )
    assert runtime_seq_result.ok is False, (
        "a runtime merge sequence that contains a scalar must fail "
        "and yield no document"
    )


# ---------------------------------------------------------------------------
# G. Nested nodes
# ---------------------------------------------------------------------------


def test_yaml11_nested_types_as_mapping_values():
    payload = bytes_payload()
    word = unique_token()
    source = (
        f"bin: {binary_scalar_yaml(b64_of(payload)).rstrip()}\n"
        f"ts: {NAMED_TS_CANONICAL}\n"
        f"members: !!set {{ {word} }}\n"
        f"ordered: {NAMED_OMAP_YAML}"
        f"paired: {NAMED_PAIRS_YAML}"
    )
    print(f"nested source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    assert require_js_bytes(mapping_get(doc, "bin")).data == payload
    _assert_epoch(mapping_get(doc, "ts"), _canonical_ms(), what="nested timestamp")
    assert set_member_texts(mapping_get(doc, "members")) == {word}
    ordered = require_sequence(mapping_get(doc, "ordered"))
    assert len(ordered) == 3
    for item, key, number in zip(ordered, ("one", "two", "three"), (1, 2, 3)):
        _assert_single_key_object(item, key, number)
    assert _looks_like_named_pairs(mapping_get(doc, "paired"))
