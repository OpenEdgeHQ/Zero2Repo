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
from F04_helpers import merge_on_schemas
from _helpers import (
    b64_decode_stripped,
    b64_of,
    binary_scalar_yaml,
    bytes_payload,
    core_int_token,
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
NAMED_OMAP_TWO_YAML = "!!omap [ one: 1, two: 2 ]\n"
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
# Frozen L181 several-merge document. Quotes around y are load-bearing
# under YAML 1.1 (FP-02 treats unquoted y as boolean true). Do not
# assemble this row with several_merge_keys_yaml (that helper emits
# unquoted y).
PUBLIC_SEVERAL_MERGE = "<<: {x: 1, 'y': 2}\nfoo: bar\n<<: {z: 3, t: 4}\n"

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


def _runtime_impossible_wall(
    *, hour: str, minute: str, offset: str | None = None
) -> str:
    n = uuid.uuid4().int
    year = 2011 + (n % 10)
    month = 3 + ((n >> 8) % 8)
    day = 2 + ((n >> 16) % 26)
    if year == 2023 and month == 1 and day == 1:
        day = 2
    wall = f"{year}-{month:02d}-{day:02d} {hour}:{minute}:00"
    if offset is None:
        return wall
    return f"{wall} {offset}"


def _off_public_calendar() -> tuple[int, int, int, int, int, int, int, int]:
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
    return year, month, day, hour, minute, second, tenths, tz_hours


def _runtime_named_shapes() -> list[tuple[str, int]]:
    year, month, day, hour, minute, second, tenths, tz_hours = _off_public_calendar()
    ms_frac = tenths * 100
    z_text = (
        f"{year}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}.{tenths}Z"
    )
    z_ms = utc_epoch_ms(year, month, day, hour, minute, second, ms_frac)
    lt_text = (
        f"{year}-{month:02d}-{day:02d}t{hour:02d}:{minute:02d}:"
        f"{second:02d}.{tenths}0+{tz_hours:02d}:00"
    )
    lt_ms = utc_epoch_ms(
        year, month, day, hour, minute, second, ms_frac, tz_hours=tz_hours
    )
    sp_text = (
        f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:"
        f"{second:02d}.{tenths}0 -{tz_hours}"
    )
    sp_ms = utc_epoch_ms(
        year, month, day, hour, minute, second, ms_frac, tz_hours=-tz_hours
    )
    nz_hour = hour if hour < 10 else 9
    nz_text = (
        f"{year}-{month:02d}-{day:02d} {nz_hour}:{minute:02d}:"
        f"{second:02d}.{tenths}0"
    )
    nz_ms = utc_epoch_ms(year, month, day, nz_hour, minute, second, ms_frac)
    date_text = f"{year}-{month:02d}-{day:02d}"
    date_ms = utc_epoch_ms(year, month, day)
    return [
        (z_text, z_ms),
        (lt_text, lt_ms),
        (sp_text, sp_ms),
        (nz_text, nz_ms),
        (date_text, date_ms),
    ]


def _runtime_named_shape() -> tuple[str, int]:
    """Lowercase-t form with a positive HH:MM offset (not a public minus)."""
    return _runtime_named_shapes()[1]


def _runtime_date_only_midnight() -> tuple[str, int]:
    """Two-digit date-only midnight (a different named spelling than lowercase-t)."""
    return _runtime_named_shapes()[4]


def _runtime_omap_source(count: int) -> tuple[str, list[str], list[int]]:
    keys = [unique_token() for _ in range(count)]
    numbers = distinct_core_ints(count)
    inner = ", ".join(f"{key}: {number}" for key, number in zip(keys, numbers))
    return f"!!omap [ {inner} ]\n", keys, numbers


def _runtime_one_pair_source() -> tuple[str, str, str]:
    key, value = unique_token(), unique_token()
    return f"!!pairs [ {key}: {value} ]\n", key, value


def _runtime_set_source() -> tuple[str, str, str]:
    left, right = unique_token(), unique_token()
    return f"!!set {{ {left}, {right} }}\n", left, right


def _looks_like_named_omap_two(value) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    expected = (("one", 1), ("two", 2))
    for item, (key, number) in zip(value, expected):
        mapping = _plain_props(item)
        if mapping is None:
            return False
        if list(mapping.keys()) != [key]:
            return False
        if not is_number_not_string(mapping.get(key), number):
            return False
    return True


def _omap_of(keys: list[str], numbers: list[int]):
    def pred(value) -> bool:
        if not isinstance(value, list) or len(value) != len(keys):
            return False
        for item, key, number in zip(value, keys, numbers):
            mapping = _plain_props(item)
            if mapping is None:
                return False
            if list(mapping.keys()) != [key]:
                return False
            if not is_number_not_string(mapping.get(key), number):
                return False
        return True

    return pred


def _pairs_of(pairs: list[tuple[str, str]]):
    def pred(value) -> bool:
        if not isinstance(value, list) or len(value) != len(pairs):
            return False
        for item, (key, text) in zip(value, pairs):
            if not isinstance(item, list) or len(item) != 2:
                return False
            if not is_string_text(item[0], key) or not is_string_text(item[1], text):
                return False
        return True

    return pred


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
    payload = bytes_payload()
    live = binary_scalar_yaml(b64_of(payload))
    decoded = require_js_bytes(
        require_document(load(live, with_yaml11_schema()))
    )
    print(f"live binary len={len(decoded.data)}", flush=True)
    assert decoded.data == payload, (
        f"valid !!binary must decode to the payload before invalid Base64 is refused; "
        f"got {decoded.data!r}"
    )

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
    ts_text, expected_ms = _runtime_named_shape()
    payload = bytes_payload()
    source = (
        "---\n"
        f"{ts_text}\n"
        "---\n"
        f"{binary_scalar_yaml(b64_of(payload))}"
    )
    print(f"multi source={source!r}", flush=True)
    docs = require_sequence(
        require_document(load_all(source, with_yaml11_schema()))
    )
    assert len(docs) == 2, f"expected 2 documents, got {len(docs)}"
    _assert_epoch(docs[0], expected_ms, what="multi-doc first timestamp")
    assert not isinstance(docs[0], str), (
        "first document must be a date, not a Core string"
    )
    assert require_js_bytes(docs[1]).data == payload


def test_yaml11_binary_as_sequence_item():
    payload = bytes_payload()
    source = f"- {binary_scalar_yaml(b64_of(payload)).rstrip()}\n"
    print(f"sequence-item binary source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 1, f"expected one sequence item, got {len(doc)}"
    assert require_js_bytes(doc[0]).data == payload


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
    for text, expected in _runtime_named_shapes():
        print(f"runtime shape={text!r} expected={expected}", flush=True)
        value = require_document(load(text, with_yaml11_schema()))
        _assert_epoch(value, expected, what=f"runtime named shape {text!r}")
        assert not isinstance(value, str), f"{text!r} must be a date, not a string"


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
    extras = (
        _runtime_impossible_day(),
        _runtime_impossible_wall(hour="24", minute="00"),
        _runtime_impossible_wall(hour="00", minute="60"),
        _runtime_impossible_wall(
            hour="00",
            minute="00",
            offset="+24" if uuid.uuid4().int % 2 else "+1:60",
        ),
    )
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
    runtime_text, runtime_ms = _runtime_named_shape()
    yaml11_runtime = require_document(load(runtime_text, with_yaml11_schema()))
    _assert_epoch(yaml11_runtime, runtime_ms, what="yaml11 runtime timestamp baseline")
    core_type_absent(load(runtime_text, with_core_schema()), is_js_date)
    date_text, date_ms = _runtime_date_only_midnight()
    yaml11_date = require_document(load(date_text, with_yaml11_schema()))
    _assert_epoch(yaml11_date, date_ms, what="yaml11 date-only midnight baseline")
    assert not isinstance(yaml11_date, str), (
        "date-only midnight must be a date on YAML 1.1, not a string"
    )
    core_type_absent(load(date_text, with_core_schema()), is_js_date)


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
    int_key = unique_token()
    n = core_int_token()
    int_src = f"!!set\n? {int_key}\n: {n}\n"
    print(f"runtime Core-int non-null source={int_src!r}", flush=True)
    int_err = require_parse_failure(load(int_src, with_yaml11_schema()))
    print(
        f"runtime Core-int non-null report={observer_visible_report(int_err)}",
        flush=True,
    )


def test_core_set_is_not_a_set():
    yaml11 = require_js_set(
        require_document(load(NAMED_TEAMS_YAML, with_yaml11_schema()))
    )
    assert set_member_texts(yaml11) == set(NAMED_TEAMS)
    core_type_absent(load(NAMED_TEAMS_YAML, with_core_schema()), is_js_set)
    runtime_src, left, right = _runtime_set_source()
    yaml11_runtime = set_member_texts(
        require_document(load(runtime_src, with_yaml11_schema()))
    )
    assert yaml11_runtime == {left, right}
    core_type_absent(load(runtime_src, with_core_schema()), is_js_set)


def test_yaml11_set_on_multi_document():
    source, left, right = _runtime_set_source()
    print(f"load_all set source={source!r}", flush=True)
    docs = require_sequence(
        require_document(load_all(source, with_yaml11_schema()))
    )
    assert len(docs) == 1, f"one-document load_all must have length 1, got {len(docs)}"
    members = set_member_texts(docs[0])
    print(f"load_all set members={members!r}", flush=True)
    assert members == {left, right}, f"load_all set {members!r}"


def test_yaml11_set_as_sequence_item():
    left, right = unique_token(), unique_token()
    source = f"- !!set {{ {left}, {right} }}\n"
    print(f"sequence-item set source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 1, f"expected one sequence item, got {len(doc)}"
    members = set_member_texts(doc[0])
    assert members == {left, right}, f"sequence-item set {members!r}"


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


def test_yaml11_omap_named_two_items():
    doc = require_sequence(
        require_document(load(NAMED_OMAP_TWO_YAML, with_yaml11_schema()))
    )
    print(f"named two-item omap={doc!r}", flush=True)
    assert len(doc) == 2, f"L191 two-item omap must have length 2, got {len(doc)}"
    assert _looks_like_named_omap_two(doc), f"named two-item omap {doc!r}"
    for item, key, number in zip(doc, ("one", "two"), (1, 2)):
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


def test_yaml11_omap_runtime_two_items():
    source, keys, values = _runtime_omap_source(2)
    print(f"runtime two-item omap source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 2, f"runtime two-item omap must have length 2, got {len(doc)}"
    assert _omap_of(keys, values)(doc), f"runtime two-item omap {doc!r}"
    for item, key, number in zip(doc, keys, values):
        _assert_single_key_object(item, key, number)


def test_yaml11_omap_runtime_one_item():
    source, keys, values = _runtime_omap_source(1)
    print(f"runtime one-item omap source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 1, f"runtime one-item omap must have length 1, got {len(doc)}"
    assert _omap_of(keys, values)(doc), f"runtime one-item omap {doc!r}"
    _assert_single_key_object(doc[0], keys[0], values[0])


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
    live_source, live_keys, live_values = _runtime_omap_source(2)
    live = require_sequence(
        require_document(load(live_source, with_yaml11_schema()))
    )
    print(f"live omap source={live_source!r}", flush=True)
    assert len(live) == 2, f"valid !!omap sequence must construct before bad items fail, got {live!r}"
    for item, key, number in zip(live, live_keys, live_values):
        _assert_single_key_object(item, key, number)

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

    two_src, two_keys, two_nums = _runtime_omap_source(2)
    default_two = require_sequence(
        require_document(load(two_src, with_yaml11_schema()))
    )
    assert len(default_two) == 2
    for item, key, number in zip(default_two, two_keys, two_nums):
        _assert_single_key_object(item, key, number)

    real_two = require_sequence(
        require_document(load(two_src, with_yaml11_real_map()))
    )
    print(
        f"real-map two-item omap types={[type(item).__name__ for item in real_two]}",
        flush=True,
    )
    assert len(real_two) == 2, (
        f"runtime two-item real-map omap must have length 2, got {len(real_two)}"
    )
    for item, key, number in zip(real_two, two_keys, two_nums):
        mapping = require_real_map(item)
        assert map_size(mapping) == 1
        assert is_number_not_string(map_get(mapping, key), number)


def test_core_omap_is_not_yaml11_omap():
    yaml11 = require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    assert _looks_like_named_omap(yaml11)
    core_type_absent(load(NAMED_OMAP_YAML, with_core_schema()), _looks_like_named_omap)
    runtime_src, keys, numbers = _runtime_omap_source(3)
    yaml11_runtime = require_document(load(runtime_src, with_yaml11_schema()))
    assert _omap_of(keys, numbers)(yaml11_runtime)
    core_type_absent(load(runtime_src, with_core_schema()), _omap_of(keys, numbers))


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


def test_yaml11_pairs_runtime_three_items():
    keys = [unique_token() for _ in range(3)]
    values = [unique_token() for _ in range(3)]
    source = (
        f"!!pairs [ {keys[0]}: {values[0]}, {keys[1]}: {values[1]}, "
        f"{keys[2]}: {values[2]} ]\n"
    )
    print(f"runtime three-pair source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 3, f"runtime three-pair must have length 3, got {len(doc)}"
    expected = list(zip(keys, values))
    assert _pairs_of(expected)(doc), f"runtime three-pair {doc!r}"
    for item, key, text in zip(doc, keys, values):
        pair = require_sequence(item)
        assert len(pair) == 2
        assert is_string_text(pair[0], key) and is_string_text(pair[1], text)


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

    key, value = unique_token(), unique_token()
    runtime_src = f"!!pairs [ {key}: {value} ]\n"
    runtime_parsed = require_sequence(
        require_document(load(runtime_src, with_yaml11_schema()))
    )
    print(f"constructed runtime pairs={runtime_parsed!r}", flush=True)
    assert len(runtime_parsed) == 1
    runtime_pair = require_sequence(runtime_parsed[0])
    assert len(runtime_pair) == 2
    assert is_string_text(runtime_pair[0], key) and is_string_text(
        runtime_pair[1], value
    )
    runtime_text = require_yaml_text(dump(runtime_parsed, with_yaml11_schema()))
    print(f"runtime pairs dump={runtime_text!r}", flush=True)
    assert "!!pairs" not in runtime_text, (
        f"runtime pairs dump must not write !!pairs; got {runtime_text!r}"
    )
    assert "!!omap" not in runtime_text, (
        f"runtime pairs dump must not write !!omap; got {runtime_text!r}"
    )
    runtime_restored = require_sequence(
        require_document(load(runtime_text, with_yaml11_schema()))
    )
    print(f"runtime pairs dump-then-load={runtime_restored!r}", flush=True)


def test_core_pairs_is_not_yaml11_pairs():
    yaml11 = require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    assert _looks_like_named_pairs(yaml11)
    core_type_absent(load(NAMED_PAIRS_YAML, with_core_schema()), _looks_like_named_pairs)
    runtime_src, key, value = _runtime_one_pair_source()
    yaml11_runtime = require_document(load(runtime_src, with_yaml11_schema()))
    assert _pairs_of([(key, value)])(yaml11_runtime)
    core_type_absent(
        load(runtime_src, with_core_schema()), _pairs_of([(key, value)])
    )


def test_yaml11_pairs_runtime_block_sequence():
    key, value = unique_token(), unique_token()
    source = f"!!pairs\n- {key}: {value}\n"
    print(f"block one-pair source={source!r}", flush=True)
    doc = require_sequence(
        require_document(load(source, with_yaml11_schema()))
    )
    assert len(doc) == 1, f"block one-pair must have length 1, got {len(doc)}"
    pair = require_sequence(doc[0])
    assert len(pair) == 2
    assert is_string_text(pair[0], key) and is_string_text(pair[1], value)


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
    yaml11_set = require_js_set(
        require_document(load(NAMED_TEAMS_YAML, with_yaml11_schema()))
    )
    assert set_member_texts(yaml11_set) == set(NAMED_TEAMS)
    yaml11_omap = require_document(load(NAMED_OMAP_YAML, with_yaml11_schema()))
    assert _looks_like_named_omap(yaml11_omap)
    yaml11_pairs = require_document(load(NAMED_PAIRS_YAML, with_yaml11_schema()))
    assert _looks_like_named_pairs(yaml11_pairs)
    core_type_absent(load(NAMED_TS_CANONICAL, with_merge_on_core()), is_js_date)
    core_type_absent(load(binary_src, with_merge_on_core()), is_js_bytes)
    core_type_absent(load(NAMED_TEAMS_YAML, with_merge_on_core()), is_js_set)
    core_type_absent(
        load(NAMED_OMAP_YAML, with_merge_on_core()), _looks_like_named_omap
    )
    core_type_absent(
        load(NAMED_PAIRS_YAML, with_merge_on_core()), _looks_like_named_pairs
    )
    runtime_ts, runtime_ms = _runtime_named_shape()
    yaml11_runtime_ts = require_document(load(runtime_ts, with_yaml11_schema()))
    _assert_epoch(yaml11_runtime_ts, runtime_ms, what="yaml11 runtime timestamp baseline")
    runtime_set_src, set_left, set_right = _runtime_set_source()
    yaml11_runtime_set = set_member_texts(
        require_document(load(runtime_set_src, with_yaml11_schema()))
    )
    assert yaml11_runtime_set == {set_left, set_right}
    runtime_omap_src, omap_keys, omap_nums = _runtime_omap_source(3)
    yaml11_runtime_omap = require_document(
        load(runtime_omap_src, with_yaml11_schema())
    )
    assert _omap_of(omap_keys, omap_nums)(yaml11_runtime_omap)
    runtime_pairs_src, pair_key, pair_val = _runtime_one_pair_source()
    yaml11_runtime_pairs = require_document(
        load(runtime_pairs_src, with_yaml11_schema())
    )
    assert _pairs_of([(pair_key, pair_val)])(yaml11_runtime_pairs)
    core_type_absent(load(runtime_ts, with_merge_on_core()), is_js_date)
    core_type_absent(load(runtime_set_src, with_merge_on_core()), is_js_set)
    core_type_absent(
        load(runtime_omap_src, with_merge_on_core()), _omap_of(omap_keys, omap_nums)
    )
    core_type_absent(
        load(runtime_pairs_src, with_merge_on_core()), _pairs_of([(pair_key, pair_val)])
    )


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


def test_merge_runtime_alias_unique_keys():
    anchor = unique_token()
    parent = unique_token()
    key_a, key_b, key_c = unique_token(), unique_token(), unique_token()
    val_a, val_b, val_c = unique_token(), unique_token(), unique_token()
    source = (
        f"{anchor}: &{anchor}\n"
        f"  {key_a}: {val_a}\n"
        f"  {key_b}: {val_b}\n"
        f"{parent}:\n"
        f"  <<: *{anchor}\n"
        f"  {key_c}: {val_c}\n"
    )
    print(f"unique-key alias source={source!r}", flush=True)
    core = require_plain_mapping(
        require_document(load(source, with_core_schema()))
    )
    core_parent = require_plain_mapping(mapping_get(core, parent))
    assert _has_key(core_parent, "<<"), "Core without merge must keep a << property"
    defaults = mapping_get(core_parent, "<<")
    assert is_string_text(mapping_get(defaults, key_a), val_a)
    assert is_string_text(mapping_get(defaults, key_b), val_b)
    assert is_string_text(mapping_get(core_parent, key_c), val_c)
    assert not _has_key(core_parent, key_a), "Core must not copy the first unique key"
    assert not _has_key(core_parent, key_b), "Core must not copy the second unique key"
    for options, label in merge_on_schemas():
        print(f"unique-key alias schema={label}", flush=True)
        merged = require_plain_mapping(
            require_document(load(source, options))
        )
        merged_parent = require_plain_mapping(mapping_get(merged, parent))
        assert is_string_text(mapping_get(merged_parent, key_a), val_a)
        assert is_string_text(mapping_get(merged_parent, key_b), val_b)
        assert is_string_text(mapping_get(merged_parent, key_c), val_c)
        assert not _has_key(merged_parent, "<<"), "merged parent must not keep <<"


def test_core_without_merge_inline_mapping():
    key_a, key_b = unique_token(), unique_token()
    n1, n2 = distinct_core_ints(2)
    source = f"<<: {{ {key_a}: {n1}, {key_b}: {n2} }}\n"
    print(f"inline mapping << source={source!r}", flush=True)
    yaml11 = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(yaml11, key_a), n1)
    assert is_number_not_string(mapping_get(yaml11, key_b), n2)
    assert not _has_key(yaml11, "<<"), "YAML 1.1 inline merge must drop <<"
    core = require_plain_mapping(
        require_document(load(source, with_core_schema()))
    )
    assert _has_key(core, "<<"), "Core without merge must keep a << property"
    assert not _has_key(core, key_a), "Core must not own the first inline key"
    assert not _has_key(core, key_b), "Core must not own the second inline key"
    kept = require_plain_mapping(mapping_get(core, "<<"))
    assert is_number_not_string(mapping_get(kept, key_a), n1)
    assert is_number_not_string(mapping_get(kept, key_b), n2)


def test_several_merge_keys_all_apply():
    print(f"several public={PUBLIC_SEVERAL_MERGE!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"several public schema={label}", flush=True)
        doc = require_plain_mapping(
            require_document(load(PUBLIC_SEVERAL_MERGE, options))
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
    for options, label in merge_on_schemas():
        print(f"several runtime schema={label}", flush=True)
        runtime_doc = require_plain_mapping(
            require_document(load(runtime, options))
        )
        assert is_number_not_string(mapping_get(runtime_doc, keys[0]), values[0])
        assert is_number_not_string(mapping_get(runtime_doc, keys[1]), values[1])
        assert is_string_text(mapping_get(runtime_doc, keys[2]), middle)
        assert is_number_not_string(mapping_get(runtime_doc, keys[3]), values[2])
        assert is_number_not_string(mapping_get(runtime_doc, keys[4]), values[3])


def test_several_merge_keys_third_applies():
    keys = [unique_token() for _ in range(6)]
    values = distinct_core_ints(5)
    middle = unique_token()
    source = (
        f"<<: {{ {keys[0]}: {values[0]}, {keys[1]}: {values[1]} }}\n"
        f"{keys[2]}: {middle}\n"
        f"<<: {{ {keys[3]}: {values[2]}, {keys[4]}: {values[3]} }}\n"
        f"<<: {{ {keys[5]}: {values[4]} }}\n"
    )
    print(f"third << source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"third << schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, keys[0]), values[0])
        assert is_number_not_string(mapping_get(doc, keys[1]), values[1])
        assert is_string_text(mapping_get(doc, keys[2]), middle)
        assert is_number_not_string(mapping_get(doc, keys[3]), values[2])
        assert is_number_not_string(mapping_get(doc, keys[4]), values[3])
        assert is_number_not_string(mapping_get(doc, keys[5]), values[4])


def test_merge_runtime_three_key_source():
    keys = [unique_token() for _ in range(3)]
    values = distinct_core_ints(3)
    source = (
        f"<<: {{ {keys[0]}: {values[0]}, {keys[1]}: {values[1]}, "
        f"{keys[2]}: {values[2]} }}\n"
    )
    print(f"three-key source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"three-key source schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, keys[0]), values[0])
        assert is_number_not_string(mapping_get(doc, keys[1]), values[1])
        assert is_number_not_string(mapping_get(doc, keys[2]), values[2])
        assert not _has_key(doc, "<<")


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
    for options, label in merge_on_schemas():
        print(f"runtime explicit schema={label}", flush=True)
        runtime_doc = require_plain_mapping(
            require_document(load(runtime, options))
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
    for options, label in merge_on_schemas():
        print(f"runtime explicit before schema={label}", flush=True)
        runtime_doc = require_plain_mapping(
            require_document(load(runtime, options))
        )
        assert is_number_not_string(mapping_get(runtime_doc, key), n2)


def test_explicit_pair_overrides_mapping_shaped_merge():
    key = unique_token()
    extra = unique_token()
    n1, n2, n3 = distinct_core_ints(3)
    baseline = f"<<: {{ {key}: {n1}, {extra}: {n3} }}\n"
    print(f"mapping-shaped baseline={baseline!r}", flush=True)
    base_doc = require_plain_mapping(
        require_document(load(baseline, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(base_doc, key), n1)
    assert is_number_not_string(mapping_get(base_doc, extra), n3)

    source = f"<<: {{ {key}: {n1}, {extra}: {n3} }}\n{key}: {n2}\n"
    print(f"mapping-shaped override={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"mapping-shaped override schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, key), n2)
        assert is_number_not_string(mapping_get(doc, extra), n3)
        assert not _has_key(doc, "<<")


def test_explicit_pair_before_mapping_shaped_merge():
    key = unique_token()
    extra = unique_token()
    n1, n2, n3 = distinct_core_ints(3)
    after = f"<<: {{ {key}: {n1}, {extra}: {n3} }}\n{key}: {n2}\n"
    after_doc = require_plain_mapping(
        require_document(load(after, with_yaml11_schema()))
    )
    assert is_number_not_string(mapping_get(after_doc, key), n2)
    assert is_number_not_string(mapping_get(after_doc, extra), n3)

    source = f"{key}: {n2}\n<<: {{ {key}: {n1}, {extra}: {n3} }}\n"
    print(f"mapping-shaped explicit before={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"mapping-shaped explicit before schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, key), n2)
        assert is_number_not_string(mapping_get(doc, extra), n3)
        assert not _has_key(doc, "<<")


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
    for options, label in merge_on_schemas():
        print(f"later unique schema={label}", flush=True)
        doc = require_plain_mapping(
            require_document(load(source, options))
        )
        assert is_number_not_string(mapping_get(doc, key_a), n1)
        assert is_number_not_string(mapping_get(doc, key_b), n3)


def test_merge_sequence_one_mapping():
    key = unique_token()
    n1 = core_int_token()
    source = f"<<: [ {{ {key}: {n1} }} ]\n"
    print(f"one-item sequence source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"one-item sequence schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, key), n1)
        assert not _has_key(doc, "<<")


def test_merge_sequence_three_mappings():
    keys = [unique_token() for _ in range(3)]
    values = distinct_core_ints(3)
    source = (
        f"<<: [ {{ {keys[0]}: {values[0]} }}, "
        f"{{ {keys[1]}: {values[1]} }}, "
        f"{{ {keys[2]}: {values[2]} }} ]\n"
    )
    print(f"three-item unique source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"three-item unique schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, keys[0]), values[0])
        assert is_number_not_string(mapping_get(doc, keys[1]), values[1])
        assert is_number_not_string(mapping_get(doc, keys[2]), values[2])


def test_merge_sequence_three_first_wins_overlap():
    key_a, key_b = unique_token(), unique_token()
    n1, n2, n3 = distinct_core_ints(3)
    source = (
        f"<<: [ {{ {key_a}: {n1} }}, "
        f"{{ {key_b}: {n2} }}, "
        f"{{ {key_a}: {n3} }} ]\n"
    )
    print(f"three-item overlap source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"three-item overlap schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        assert is_number_not_string(mapping_get(doc, key_a), n1)
        assert is_number_not_string(mapping_get(doc, key_b), n2)


def test_merge_nested_mapping_not_named_development():
    outer = unique_token()
    key_a, key_b = unique_token(), unique_token()
    n1, n2 = distinct_core_ints(2)
    source = f"{outer}: {{ <<: {{ {key_a}: {n1} }}, {key_b}: {n2} }}\n"
    print(f"nested-not-development source={source!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"nested-not-development schema={label}", flush=True)
        doc = require_plain_mapping(require_document(load(source, options)))
        nested = require_plain_mapping(mapping_get(doc, outer))
        assert is_number_not_string(mapping_get(nested, key_a), n1)
        assert is_number_not_string(mapping_get(nested, key_b), n2)
        assert not _has_key(nested, "<<")


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
    live_source = defaults_development_yaml(
        "postgres", "localhost", "app_development"
    )
    for options, label in merge_on_schemas():
        print(f"live merge schema={label}", flush=True)
        live = require_plain_mapping(
            require_document(load(live_source, options))
        )
        _assert_applied_merge(
            mapping_get(live, "development"),
            "postgres",
            "localhost",
            "app_development",
        )

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
    for options, label in merge_on_schemas():
        print(f"runtime scalar schema={label}", flush=True)
        runtime_scalar_result = load(runtime_scalar, options)
        runtime_scalar_err = require_parse_failure(runtime_scalar_result)
        print(
            f"runtime scalar ok={runtime_scalar_result.ok!r} "
            f"schema={label} "
            f"report={observer_visible_report(runtime_scalar_err)}",
            flush=True,
        )
        assert runtime_scalar_result.ok is False, (
            "a runtime scalar merge source must fail and yield no document"
        )

    runtime_seq = f"keep: 1\n<<: [{{ x: 1 }}, {word}]\n"
    print(f"runtime seq scalar merge={runtime_seq!r}", flush=True)
    for options, label in merge_on_schemas():
        print(f"runtime seq scalar schema={label}", flush=True)
        runtime_seq_result = load(runtime_seq, options)
        runtime_seq_err = require_parse_failure(runtime_seq_result)
        print(
            f"runtime seq scalar ok={runtime_seq_result.ok!r} "
            f"schema={label} "
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


def test_yaml11_nested_runtime_types_as_mapping_values():
    ts_text, expected_ms = _runtime_named_shape()
    omap_src, omap_keys, omap_nums = _runtime_omap_source(3)
    pairs_src, pair_key, pair_val = _runtime_one_pair_source()
    source = (
        f"when: {ts_text}\n"
        f"ordered: {omap_src}"
        f"paired: {pairs_src}"
    )
    print(f"nested runtime source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(source, with_yaml11_schema()))
    )
    _assert_epoch(mapping_get(doc, "when"), expected_ms, what="nested runtime timestamp")
    ordered = require_sequence(mapping_get(doc, "ordered"))
    assert len(ordered) == 3
    for item, key, number in zip(ordered, omap_keys, omap_nums):
        _assert_single_key_object(item, key, number)
    paired = require_sequence(mapping_get(doc, "paired"))
    assert _pairs_of([(pair_key, pair_val)])(paired), f"nested runtime pairs {paired!r}"


def test_yaml11_nested_typed_values_dump_round_trip():
    payload = bytes_payload()
    left, right = unique_token(), unique_token()
    ms = utc_epoch_ms(2016, 7, 4, 13, 21, 8, 250)
    dumped = dump(
        {
            "bin": payload,
            "members": JsSet(items=[left, right], object_id=-1),
            "when": JsDate(epoch_ms=float(ms), iso="", object_id=-1),
        },
        with_yaml11_schema(),
    )
    text = require_yaml_text(dumped)
    print(f"nested dump={text!r}", flush=True)
    doc = require_plain_mapping(
        require_document(load(text, with_yaml11_schema()))
    )
    assert require_js_bytes(mapping_get(doc, "bin")).data == payload
    assert set_member_texts(mapping_get(doc, "members")) == {left, right}
    _assert_epoch(mapping_get(doc, "when"), ms, what="nested dumped date")


def test_yaml11_lone_nested_typed_value_dump_round_trip():
    payload = bytes_payload()
    bin_key = unique_token()
    bin_text = require_yaml_text(dump({bin_key: payload}, with_yaml11_schema()))
    print(f"lone nested bytes dump={bin_text!r}", flush=True)
    bin_doc = require_plain_mapping(
        require_document(load(bin_text, with_yaml11_schema()))
    )
    assert require_js_bytes(mapping_get(bin_doc, bin_key)).data == payload

    left, right = unique_token(), unique_token()
    set_key = unique_token()
    set_text = require_yaml_text(
        dump(
            {set_key: JsSet(items=[left, right], object_id=-1)},
            with_yaml11_schema(),
        )
    )
    print(f"lone nested set dump={set_text!r}", flush=True)
    set_doc = require_plain_mapping(
        require_document(load(set_text, with_yaml11_schema()))
    )
    assert set_member_texts(mapping_get(set_doc, set_key)) == {left, right}

    ms = utc_epoch_ms(2016, 7, 4, 13, 21, 8, 250)
    date_key = unique_token()
    date_text = require_yaml_text(
        dump(
            {date_key: JsDate(epoch_ms=float(ms), iso="", object_id=-1)},
            with_yaml11_schema(),
        )
    )
    print(f"lone nested date dump={date_text!r}", flush=True)
    date_doc = require_plain_mapping(
        require_document(load(date_text, with_yaml11_schema()))
    )
    _assert_epoch(mapping_get(date_doc, date_key), ms, what="lone nested dumped date")
