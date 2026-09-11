# feature: F06
"""Custom tags (FP-06).

Assertions stay at the PRD's precision: attach a tag then parse or dump,
caller-defined values vs plain scalars/collections, dump-then-parse of
the represented text, exact name over prefix, prefix catch-alls that
remember the original name, schema create/attach refusals, replacement
by name+kind+prefix-flag, and converting-tag recursive-alias failure
against a live default-sequence baseline on the same attached schema.
Class names, prototypes, flow vs block, quote style, and failure wording
are not pinned.
"""

from __future__ import annotations

from _harness import (
    SCHEMA_CORE,
    SCHEMA_FAILSAFE,
    SCHEMA_JSON,
    SCHEMA_YAML11,
    load,
)
from _helpers import (
    attempt_schema_attach,
    attempt_schema_create,
    core_int_token,
    distinct_core_ints,
    dump_never_parsed_with_attached_tags,
    dump_parse_never_parsed_with_attached_tags,
    dump_with_attached_tags,
    explicit_local_tag_present,
    is_bool,
    is_number_not_string,
    is_string_text,
    mapping_get,
    mapping_pairs_spec,
    mapping_remember_spec,
    mapping_space_spec,
    non_bool_word,
    observer_visible_report,
    parse_dump_parse_with_attached_tags,
    parse_then_dump_with_attached_tags,
    parse_with_attached_tags,
    parse_with_sequential_attach,
    require_caller_mapping,
    require_document,
    require_explicit_local_tag,
    require_js_set,
    require_no_explicit_local_tag,
    require_parse_failure,
    require_plain_mapping,
    require_remembered,
    require_schema_unusable,
    require_sequence,
    require_yaml_text,
    same_identity,
    scalar_int_object_spec,
    scalar_remember_spec,
    scalar_stamp_spec,
    scalar_text_spec,
    sequence_frozen_point_spec,
    sequence_remember_spec,
    sequence_stamp_spec,
    sequence_xyz_spec,
    unique_local_tag,
    unique_token,
    value_holds_numbers,
)

TAG2 = "!tag2"
POINT = "!point"
SPACE = "!space"
INCLUDE = "!Include"
FOO = "!foo"
FOO2 = "!foo2"
BAR = "!bar"
UNKNOWN_SCALAR = "!unknown_scalar_tag"
UNKNOWN_SEQUENCE = "!unknown_sequence_tag"
UNKNOWN_MAPPING = "!unknown_mapping_tag"

TAG2_FIELD = "amount"
TAG2_SPEC = scalar_int_object_spec(TAG2, field=TAG2_FIELD)
POINT_SPEC = sequence_xyz_spec(POINT)
SPACE_SPEC = mapping_space_spec(SPACE)
FROZEN_POINT_SPEC = sequence_frozen_point_spec(POINT, arity=2)
REMEMBER_SPECS = [
    scalar_remember_spec("!"),
    sequence_remember_spec("!"),
    mapping_remember_spec("!"),
]

TAG2_TEN = "!tag2 10"
TAG2_TEN_BLOCK = "!tag2\n  10"
POINT_TRIPLE = "!point [10, 43, 23]"
POINT_PAIR = "!point [10, 20]"
POINT_ONE = "!point [10]"
RECURSIVE_DEFAULT = "&a [*a]"
RECURSIVE_POINT = "&point !point [*point]"
INCLUDE_SCALAR = "!Include foobar"
INCLUDE_MAPPING = "!Include\n  location: foobar"
UNKNOWN_SCALAR_DOC = "!unknown_scalar_tag foo bar"
UNKNOWN_SEQUENCE_DOC = "!unknown_sequence_tag [1, 2, 3]"
UNKNOWN_MAPPING_DOC = "!unknown_mapping_tag { foo: 1, bar: 2 }"
SPACE_PUBLIC = (
    "!space\n"
    "  height: 1000\n"
    "  width: 1000\n"
    "  points: []\n"
)
SPACE_WITH_POINT = (
    "!space\n"
    "  height: 1000\n"
    "  width: 1000\n"
    "  points:\n"
    "    - !point [10, 43, 23]\n"
)
POINT_ALIAS_DOC = (
    "point: &point !point [10, 20]\n"
    "samePoint: *point\n"
)
PLAIN_SPACE = {"height": 1000, "width": 1000, "points": []}


def _stamp_texts(value):
    obj = require_caller_mapping(value)
    return [item for item in obj.values() if isinstance(item, str)]


def _stamps_after_strip(value, *covariates):
    leftover = []
    for text in _stamp_texts(value):
        for cov in covariates:
            text = text.replace(str(cov), "")
        leftover.append(text)
    return leftover


def _has_stamp(value, stamp):
    texts = _stamp_texts(value)
    print(f"stamps={texts!r} want={stamp!r}", flush=True)
    return stamp in texts


def _unsorted_triple():
    nums = distinct_core_ints(3)
    if nums[0] < nums[1] < nums[2]:
        nums = [nums[2], nums[0], nums[1]]
    print(f"unsorted_triple={nums!r}", flush=True)
    return nums


def _int_payload(field, value):
    return {"field": field, "value": value}


def _xyz_payload(x, y, z):
    return {"x": x, "y": y, "z": z}


def _space_block(tag, height, width, points_yaml):
    return (
        f"{tag}\n"
        f"  height: {height}\n"
        f"  width: {width}\n"
        f"  points:\n{points_yaml}\n"
    )


# ---------------------------------------------------------------------------
# A. Scalar custom tag
# ---------------------------------------------------------------------------


def test_tag2_absent_core_refuses():
    for source in (TAG2_TEN, TAG2_TEN_BLOCK):
        print(f"absent source={source!r}", flush=True)
        failed = load(source)
        error = require_parse_failure(failed)
        print(
            f"absent ok={failed.ok!r} report={observer_visible_report(error)!r}",
            flush=True,
        )
        assert failed.ok is False


def test_tag2_constructs_caller_object():
    for source in (TAG2_TEN, TAG2_TEN_BLOCK):
        print(f"tag2 source={source!r}", flush=True)
        absent = load(source)
        error = require_parse_failure(absent)
        print(
            f"tag2 absent ok={absent.ok!r} "
            f"report={observer_visible_report(error)!r}",
            flush=True,
        )
        assert absent.ok is False
        doc = require_document(
            parse_with_attached_tags(source, [TAG2_SPEC], base=SCHEMA_CORE)
        )
        print(f"tag2 value={doc!r}", flush=True)
        assert not is_number_not_string(doc, 10), (
            f"tagged scalar must not be the bare number 10; got {doc!r}"
        )
        assert not is_string_text(doc, "10"), (
            f"tagged scalar must not be the text 10; got {doc!r}"
        )
        obj = require_caller_mapping(doc)
        assert value_holds_numbers(obj, [10]), (
            f"tagged scalar must hold integer 10 on a caller object; got {obj!r}"
        )


def test_tag2_dump_writes_tag():
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(TAG2_TEN, [TAG2_SPEC], base=SCHEMA_CORE)
    )
    print(f"tag2 dump={text!r}", flush=True)
    require_explicit_local_tag(text, TAG2)
    restored = require_document(
        parse_dump_parse_with_attached_tags(TAG2_TEN, [TAG2_SPEC], base=SCHEMA_CORE)
    )
    obj = require_caller_mapping(restored)
    assert value_holds_numbers(obj, [10]), (
        f"dump-then-parse must still hold 10; got {obj!r}"
    )


def test_tag2_dump_plain_number_has_no_tag():
    tagged = require_yaml_text(
        parse_then_dump_with_attached_tags(TAG2_TEN, [TAG2_SPEC], base=SCHEMA_CORE)
    )
    require_explicit_local_tag(tagged, TAG2)
    assert explicit_local_tag_present(tagged, TAG2)
    plain = require_yaml_text(
        dump_with_attached_tags(10, [TAG2_SPEC], base=SCHEMA_CORE)
    )
    print(f"plain-10 dump={plain!r}", flush=True)
    require_no_explicit_local_tag(plain, TAG2)
    assert not explicit_local_tag_present(plain, TAG2)


def test_tag2_dump_never_parsed_object():
    payload = _int_payload(TAG2_FIELD, 10)
    text = require_yaml_text(
        dump_never_parsed_with_attached_tags(
            "int_object", payload, [TAG2_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"never-parsed tag2 dump={text!r}", flush=True)
    require_explicit_local_tag(text, TAG2)
    restored = require_document(
        dump_parse_never_parsed_with_attached_tags(
            "int_object", payload, [TAG2_SPEC], base=SCHEMA_CORE
        )
    )
    obj = require_caller_mapping(restored)
    assert value_holds_numbers(obj, [10]), (
        f"never-parsed dump-then-parse must hold 10; got {obj!r}"
    )


def test_runtime_scalar_tag_round_trip():
    handle = unique_local_tag()
    field = unique_token()
    number = core_int_token()
    spec = scalar_int_object_spec(handle, field=field)
    source = f"{handle} {number}"
    print(f"runtime scalar source={source!r}", flush=True)
    require_parse_failure(load(source))
    obj = require_caller_mapping(
        require_document(parse_with_attached_tags(source, [spec], base=SCHEMA_CORE))
    )
    assert value_holds_numbers(obj, [number]), (
        f"runtime tagged scalar must hold {number}; got {obj!r}"
    )
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(source, [spec], base=SCHEMA_CORE)
    )
    require_explicit_local_tag(text, handle)
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(source, [spec], base=SCHEMA_CORE)
        )
    )
    assert value_holds_numbers(restored, [number])
    plain = require_yaml_text(
        dump_with_attached_tags(number, [spec], base=SCHEMA_CORE)
    )
    require_no_explicit_local_tag(plain, handle)
    payload = _int_payload(field, number)
    never_text = require_yaml_text(
        dump_never_parsed_with_attached_tags(
            "int_object", payload, [spec], base=SCHEMA_CORE
        )
    )
    require_explicit_local_tag(never_text, handle)
    never_restored = require_caller_mapping(
        require_document(
            dump_parse_never_parsed_with_attached_tags(
                "int_object", payload, [spec], base=SCHEMA_CORE
            )
        )
    )
    assert value_holds_numbers(never_restored, [number])


# ---------------------------------------------------------------------------
# B. Sequence custom tag
# ---------------------------------------------------------------------------


def test_point_absent_core_refuses():
    print(f"absent point={POINT_TRIPLE!r}", flush=True)
    failed = load(POINT_TRIPLE)
    error = require_parse_failure(failed)
    print(
        f"absent point ok={failed.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert failed.ok is False


def test_point_three_coordinates():
    doc = require_document(
        parse_with_attached_tags(POINT_TRIPLE, [POINT_SPEC], base=SCHEMA_CORE)
    )
    obj = require_caller_mapping(doc)
    print(f"point={obj!r}", flush=True)
    assert is_number_not_string(mapping_get(obj, "x"), 10)
    assert is_number_not_string(mapping_get(obj, "y"), 43)
    assert is_number_not_string(mapping_get(obj, "z"), 23)


def test_point_items_keep_order():
    x, y, z = _unsorted_triple()
    source = f"{POINT} [{x}, {y}, {z}]"
    print(f"order source={source!r}", flush=True)
    obj = require_caller_mapping(
        require_document(
            parse_with_attached_tags(source, [POINT_SPEC], base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(obj, "x"), x)
    assert is_number_not_string(mapping_get(obj, "y"), y)
    assert is_number_not_string(mapping_get(obj, "z"), z)
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(source, [POINT_SPEC], base=SCHEMA_CORE)
    )
    require_explicit_local_tag(text, POINT)
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(source, [POINT_SPEC], base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(restored, "x"), x)
    assert is_number_not_string(mapping_get(restored, "y"), y)
    assert is_number_not_string(mapping_get(restored, "z"), z)


def test_point_dump_writes_tagged_sequence():
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(
            POINT_TRIPLE, [POINT_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"point dump={text!r}", flush=True)
    require_explicit_local_tag(text, POINT)
    assert "10" in text and "43" in text and "23" in text, (
        f"dump must carry the three coordinates; got {text!r}"
    )
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(
                POINT_TRIPLE, [POINT_SPEC], base=SCHEMA_CORE
            )
        )
    )
    assert is_number_not_string(mapping_get(restored, "x"), 10)
    assert is_number_not_string(mapping_get(restored, "y"), 43)
    assert is_number_not_string(mapping_get(restored, "z"), 23)


def test_plain_triple_dump_has_no_point_tag():
    tagged = require_yaml_text(
        parse_then_dump_with_attached_tags(
            POINT_TRIPLE, [POINT_SPEC], base=SCHEMA_CORE
        )
    )
    require_explicit_local_tag(tagged, POINT)
    assert explicit_local_tag_present(tagged, POINT)
    plain = require_yaml_text(
        dump_with_attached_tags([10, 43, 23], [POINT_SPEC], base=SCHEMA_CORE)
    )
    print(f"plain triple dump={plain!r}", flush=True)
    require_no_explicit_local_tag(plain, POINT)
    assert not explicit_local_tag_present(plain, POINT)


def test_point_dump_never_parsed():
    payload = _xyz_payload(10, 43, 23)
    text = require_yaml_text(
        dump_never_parsed_with_attached_tags(
            "xyz_point", payload, [POINT_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"never-parsed point dump={text!r}", flush=True)
    require_explicit_local_tag(text, POINT)
    restored = require_caller_mapping(
        require_document(
            dump_parse_never_parsed_with_attached_tags(
                "xyz_point", payload, [POINT_SPEC], base=SCHEMA_CORE
            )
        )
    )
    assert is_number_not_string(mapping_get(restored, "x"), 10)
    assert is_number_not_string(mapping_get(restored, "y"), 43)
    assert is_number_not_string(mapping_get(restored, "z"), 23)


def test_converting_point_holds_two_numbers():
    doc = require_document(
        parse_with_attached_tags(
            POINT_PAIR, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"converting point={doc!r}", flush=True)
    assert value_holds_numbers(doc, [10, 20]), (
        f"converting point must make 10 and 20 observable; got {doc!r}"
    )


def test_converting_point_alias_same_identity():
    doc = require_plain_mapping(
        require_document(
            parse_with_attached_tags(
                POINT_ALIAS_DOC, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
            )
        )
    )
    point = mapping_get(doc, "point")
    same = mapping_get(doc, "samePoint")
    print(f"point={point!r} same={same!r}", flush=True)
    assert same_identity(point, same), (
        "alias must refer to the same converted point, not a copy"
    )
    assert value_holds_numbers(point, [10, 20])


def test_runtime_converting_point_alias():
    handle = unique_local_tag()
    spec = sequence_frozen_point_spec(handle, arity=2)
    left, right = distinct_core_ints(2)
    source = (
        f"point: &point {handle} [{left}, {right}]\n"
        f"samePoint: *point\n"
    )
    print(f"runtime converting source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(parse_with_attached_tags(source, [spec], base=SCHEMA_CORE))
    )
    point = mapping_get(doc, "point")
    same = mapping_get(doc, "samePoint")
    assert same_identity(point, same)
    assert value_holds_numbers(point, [left, right])


# ---------------------------------------------------------------------------
# C. Mapping custom tag
# ---------------------------------------------------------------------------


def test_space_absent_core_refuses():
    print(f"absent space={SPACE_PUBLIC!r}", flush=True)
    failed = load(SPACE_PUBLIC)
    error = require_parse_failure(failed)
    print(
        f"absent space ok={failed.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert failed.ok is False


def test_space_constructs_from_named_keys():
    doc = require_caller_mapping(
        require_document(
            parse_with_attached_tags(SPACE_PUBLIC, [SPACE_SPEC], base=SCHEMA_CORE)
        )
    )
    print(f"space={doc!r}", flush=True)
    assert is_number_not_string(mapping_get(doc, "height"), 1000)
    assert is_number_not_string(mapping_get(doc, "width"), 1000)
    require_sequence(mapping_get(doc, "points"))


def test_space_dump_then_parse_keeps_tag():
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(
            SPACE_PUBLIC, [SPACE_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"space dump={text!r}", flush=True)
    require_explicit_local_tag(text, SPACE)
    assert "height" in text and "width" in text and "points" in text, (
        f"dump must write the named keys; got {text!r}"
    )
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(
                SPACE_PUBLIC, [SPACE_SPEC], base=SCHEMA_CORE
            )
        )
    )
    assert is_number_not_string(mapping_get(restored, "height"), 1000)
    assert is_number_not_string(mapping_get(restored, "width"), 1000)
    require_sequence(mapping_get(restored, "points"))
    again = require_yaml_text(
        parse_then_dump_with_attached_tags(
            SPACE_PUBLIC, [SPACE_SPEC], base=SCHEMA_CORE
        )
    )
    require_explicit_local_tag(again, SPACE)


def test_plain_mapping_dump_has_no_space_tag():
    tagged = require_yaml_text(
        parse_then_dump_with_attached_tags(
            SPACE_PUBLIC, [SPACE_SPEC], base=SCHEMA_CORE
        )
    )
    require_explicit_local_tag(tagged, SPACE)
    assert explicit_local_tag_present(tagged, SPACE)
    plain = require_yaml_text(
        dump_with_attached_tags(PLAIN_SPACE, [SPACE_SPEC], base=SCHEMA_CORE)
    )
    print(f"plain space-shaped dump={plain!r}", flush=True)
    require_no_explicit_local_tag(plain, SPACE)
    assert not explicit_local_tag_present(plain, SPACE)


def test_space_dump_never_parsed():
    payload = {"height": 1000, "width": 1000, "points": []}
    text = require_yaml_text(
        dump_never_parsed_with_attached_tags(
            "space", payload, [SPACE_SPEC], base=SCHEMA_CORE
        )
    )
    print(f"never-parsed space dump={text!r}", flush=True)
    require_explicit_local_tag(text, SPACE)
    restored = require_caller_mapping(
        require_document(
            dump_parse_never_parsed_with_attached_tags(
                "space", payload, [SPACE_SPEC], base=SCHEMA_CORE
            )
        )
    )
    assert is_number_not_string(mapping_get(restored, "height"), 1000)
    assert is_number_not_string(mapping_get(restored, "width"), 1000)
    require_sequence(mapping_get(restored, "points"))


def test_runtime_space_values():
    height, width = distinct_core_ints(2)
    items = distinct_core_ints(2)
    source = (
        f"{SPACE}\n"
        f"  height: {height}\n"
        f"  width: {width}\n"
        f"  points: [{items[0]}, {items[1]}]\n"
    )
    print(f"runtime space source={source!r}", flush=True)
    doc = require_caller_mapping(
        require_document(
            parse_with_attached_tags(source, [SPACE_SPEC], base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(doc, "height"), height)
    assert is_number_not_string(mapping_get(doc, "width"), width)
    pts = require_sequence(mapping_get(doc, "points"))
    assert value_holds_numbers(pts, items)
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(source, [SPACE_SPEC], base=SCHEMA_CORE)
    )
    require_explicit_local_tag(text, SPACE)
    assert "height" in text and "width" in text and "points" in text
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(source, [SPACE_SPEC], base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(restored, "height"), height)
    assert is_number_not_string(mapping_get(restored, "width"), width)
    assert value_holds_numbers(require_sequence(mapping_get(restored, "points")), items)


def test_space_containing_point_round_trip():
    specs = [POINT_SPEC, SPACE_SPEC]
    doc = require_caller_mapping(
        require_document(
            parse_with_attached_tags(SPACE_WITH_POINT, specs, base=SCHEMA_CORE)
        )
    )
    print(f"nested space={doc!r}", flush=True)
    assert is_number_not_string(mapping_get(doc, "height"), 1000)
    points = require_sequence(mapping_get(doc, "points"))
    assert len(points) >= 1, f"points must contain the nested point; got {points!r}"
    nested = require_caller_mapping(points[0])
    assert is_number_not_string(mapping_get(nested, "x"), 10)
    assert is_number_not_string(mapping_get(nested, "y"), 43)
    assert is_number_not_string(mapping_get(nested, "z"), 23)
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(SPACE_WITH_POINT, specs, base=SCHEMA_CORE)
    )
    require_explicit_local_tag(text, SPACE)
    require_explicit_local_tag(text, POINT)
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(
                SPACE_WITH_POINT, specs, base=SCHEMA_CORE
            )
        )
    )
    restored_point = require_caller_mapping(
        require_sequence(mapping_get(restored, "points"))[0]
    )
    assert is_number_not_string(mapping_get(restored_point, "x"), 10)
    assert is_number_not_string(mapping_get(restored_point, "y"), 43)
    assert is_number_not_string(mapping_get(restored_point, "z"), 23)


def test_runtime_space_containing_point_round_trip():
    specs = [POINT_SPEC, SPACE_SPEC]
    height, width = distinct_core_ints(2)
    x, y, z = _unsorted_triple()
    source = _space_block(
        SPACE, height, width, f"    - {POINT} [{x}, {y}, {z}]"
    )
    print(f"runtime nested source={source!r}", flush=True)
    doc = require_caller_mapping(
        require_document(parse_with_attached_tags(source, specs, base=SCHEMA_CORE))
    )
    assert is_number_not_string(mapping_get(doc, "height"), height)
    assert is_number_not_string(mapping_get(doc, "width"), width)
    nested = require_caller_mapping(require_sequence(mapping_get(doc, "points"))[0])
    assert is_number_not_string(mapping_get(nested, "x"), x)
    assert is_number_not_string(mapping_get(nested, "y"), y)
    assert is_number_not_string(mapping_get(nested, "z"), z)
    text = require_yaml_text(
        parse_then_dump_with_attached_tags(source, specs, base=SCHEMA_CORE)
    )
    require_explicit_local_tag(text, SPACE)
    require_explicit_local_tag(text, POINT)
    restored = require_caller_mapping(
        require_document(
            parse_dump_parse_with_attached_tags(source, specs, base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(restored, "height"), height)
    assert is_number_not_string(mapping_get(restored, "width"), width)
    restored_point = require_caller_mapping(
        require_sequence(mapping_get(restored, "points"))[0]
    )
    assert is_number_not_string(mapping_get(restored_point, "x"), x)
    assert is_number_not_string(mapping_get(restored_point, "y"), y)
    assert is_number_not_string(mapping_get(restored_point, "z"), z)


# ---------------------------------------------------------------------------
# D. Same name, two kinds; exact name wins over prefix
# ---------------------------------------------------------------------------


def test_include_scalar_and_mapping_are_distinct():
    specs = [scalar_text_spec(INCLUDE), mapping_pairs_spec(INCLUDE)]
    scalar = require_document(
        parse_with_attached_tags(INCLUDE_SCALAR, specs, base=SCHEMA_CORE)
    )
    mapping = require_caller_mapping(
        require_document(
            parse_with_attached_tags(INCLUDE_MAPPING, specs, base=SCHEMA_CORE)
        )
    )
    print(f"include scalar={scalar!r} mapping={mapping!r}", flush=True)
    assert is_string_text(scalar, "foobar")
    assert is_string_text(mapping_get(mapping, "location"), "foobar")
    scalar_marks = ["foobar".replace("foobar", "")]
    mapping_keys = list(require_plain_mapping(mapping).keys())
    print(f"after strip scalar={scalar_marks!r} keys={mapping_keys!r}", flush=True)
    assert "location" in mapping_keys
    assert not is_string_text(mapping, "foobar")
    assert scalar != mapping


def test_runtime_same_name_two_kinds():
    handle = unique_local_tag()
    word = unique_token()
    key = unique_token()
    specs = [scalar_text_spec(handle), mapping_pairs_spec(handle)]
    scalar_src = f"{handle} {word}"
    mapping_src = f"{handle}\n  {key}: {word}\n"
    print(f"runtime kinds scalar={scalar_src!r} mapping={mapping_src!r}", flush=True)
    scalar = require_document(
        parse_with_attached_tags(scalar_src, specs, base=SCHEMA_CORE)
    )
    mapping = require_caller_mapping(
        require_document(
            parse_with_attached_tags(mapping_src, specs, base=SCHEMA_CORE)
        )
    )
    assert is_string_text(scalar, word)
    assert is_string_text(mapping_get(mapping, key), word)
    assert key in list(require_plain_mapping(mapping).keys())
    assert not is_string_text(mapping, word)
    assert scalar != mapping


def test_exact_foo_wins_over_prefixes():
    exact = unique_token()
    foo_prefix = unique_token()
    bang = unique_token()
    assert len({exact, foo_prefix, bang}) == 3
    specs = [
        scalar_stamp_spec(FOO, foo_prefix, prefix=True),
        scalar_stamp_spec("!", bang, prefix=True),
        scalar_stamp_spec(FOO, exact),
    ]
    foo = require_document(
        parse_with_attached_tags("!foo 1", specs, base=SCHEMA_CORE)
    )
    foo2 = require_document(
        parse_with_attached_tags("!foo2 2", specs, base=SCHEMA_CORE)
    )
    bar = require_document(
        parse_with_attached_tags("!bar 3", specs, base=SCHEMA_CORE)
    )
    print(f"foo={foo!r} foo2={foo2!r} bar={bar!r}", flush=True)
    assert _has_stamp(foo, exact) and not _has_stamp(foo, foo_prefix)
    assert _has_stamp(foo2, foo_prefix) and not _has_stamp(foo2, exact)
    assert _has_stamp(bar, bang) and not _has_stamp(bar, exact)
    cov = (FOO, FOO2, BAR, "1", "2", "3")
    marks = [
        tuple(_stamps_after_strip(foo, *cov)),
        tuple(_stamps_after_strip(foo2, *cov)),
        tuple(_stamps_after_strip(bar, *cov)),
    ]
    print(f"stripped stamp marks={marks!r}", flush=True)
    assert marks[0] != marks[1] and marks[0] != marks[2] and marks[1] != marks[2]


def test_runtime_exact_wins_over_prefixes():
    word_a = unique_token()
    exact_name = "!" + word_a
    other = unique_local_tag()
    exact_stamp = unique_token()
    prefix_stamp = unique_token()
    bang_stamp = unique_token()
    assert len({exact_stamp, prefix_stamp, bang_stamp}) == 3
    specs = [
        scalar_stamp_spec(exact_name, prefix_stamp, prefix=True),
        scalar_stamp_spec("!", bang_stamp, prefix=True),
        scalar_stamp_spec(exact_name, exact_stamp),
    ]
    n1, n2, n3 = distinct_core_ints(3)
    suffix = unique_token()
    prefixed = exact_name + suffix
    exact_src = f"{exact_name} {n1}"
    prefix_src = f"{prefixed} {n2}"
    bang_src = f"{other} {n3}"
    print(
        f"runtime exact={exact_src!r} prefix={prefix_src!r} bang={bang_src!r}",
        flush=True,
    )
    exact_doc = require_document(
        parse_with_attached_tags(exact_src, specs, base=SCHEMA_CORE)
    )
    prefix_doc = require_document(
        parse_with_attached_tags(prefix_src, specs, base=SCHEMA_CORE)
    )
    bang_doc = require_document(
        parse_with_attached_tags(bang_src, specs, base=SCHEMA_CORE)
    )
    assert _has_stamp(exact_doc, exact_stamp)
    assert _has_stamp(prefix_doc, prefix_stamp)
    assert _has_stamp(bang_doc, bang_stamp)
    cov = (exact_name, prefixed, other, str(n1), str(n2), str(n3), word_a)
    marks = [
        tuple(_stamps_after_strip(exact_doc, *cov)),
        tuple(_stamps_after_strip(prefix_doc, *cov)),
        tuple(_stamps_after_strip(bang_doc, *cov)),
    ]
    print(f"runtime stripped marks={marks!r}", flush=True)
    assert marks[0] != marks[1] and marks[0] != marks[2] and marks[1] != marks[2]


# ---------------------------------------------------------------------------
# E. Prefix matching accepts unknown tags
# ---------------------------------------------------------------------------


def test_unknown_local_tags_fail_without_prefix():
    for source in (UNKNOWN_SCALAR_DOC, UNKNOWN_SEQUENCE_DOC, UNKNOWN_MAPPING_DOC):
        print(f"unknown absent source={source!r}", flush=True)
        failed = load(source)
        error = require_parse_failure(failed)
        print(
            f"unknown absent ok={failed.ok!r} "
            f"report={observer_visible_report(error)!r}",
            flush=True,
        )
        assert failed.ok is False


def test_prefix_bang_accepts_unknown_kinds():
    scalar = require_document(
        parse_with_attached_tags(
            UNKNOWN_SCALAR_DOC, REMEMBER_SPECS, base=SCHEMA_CORE
        )
    )
    sequence = require_document(
        parse_with_attached_tags(
            UNKNOWN_SEQUENCE_DOC, REMEMBER_SPECS, base=SCHEMA_CORE
        )
    )
    mapping = require_document(
        parse_with_attached_tags(
            UNKNOWN_MAPPING_DOC, REMEMBER_SPECS, base=SCHEMA_CORE
        )
    )
    print(
        f"unknown scalar={scalar!r} seq={sequence!r} map={mapping!r}",
        flush=True,
    )
    require_remembered(scalar, UNKNOWN_SCALAR, "foo bar")
    require_remembered(sequence, UNKNOWN_SEQUENCE, [1, 2, 3])
    require_remembered(mapping, UNKNOWN_MAPPING, {"foo": 1, "bar": 2})
    assert scalar != sequence
    assert scalar != mapping
    assert sequence != mapping


def test_prefix_bang_dump_writes_same_names():
    for source, handle, content in (
        (UNKNOWN_SCALAR_DOC, UNKNOWN_SCALAR, "foo bar"),
        (UNKNOWN_SEQUENCE_DOC, UNKNOWN_SEQUENCE, [1, 2, 3]),
        (UNKNOWN_MAPPING_DOC, UNKNOWN_MAPPING, {"foo": 1, "bar": 2}),
    ):
        text = require_yaml_text(
            parse_then_dump_with_attached_tags(
                source, REMEMBER_SPECS, base=SCHEMA_CORE
            )
        )
        print(f"unknown dump handle={handle!r} text={text!r}", flush=True)
        require_explicit_local_tag(text, handle)
        assert explicit_local_tag_present(text, handle)
        restored = require_document(
            parse_dump_parse_with_attached_tags(
                source, REMEMBER_SPECS, base=SCHEMA_CORE
            )
        )
        require_remembered(restored, handle, content)


def test_runtime_unknown_tags_round_trip():
    scalar_name = unique_local_tag()
    seq_name = unique_local_tag()
    map_name = unique_local_tag()
    word = unique_token()
    n1, n2, n3 = distinct_core_ints(3)
    key_a = unique_token()
    key_b = unique_token()
    scalar_src = f"{scalar_name} {word}"
    seq_src = f"{seq_name} [{n1}, {n2}, {n3}]"
    map_src = f"{map_name} {{ {key_a}: {n1}, {key_b}: {n2} }}"
    for source in (scalar_src, seq_src, map_src):
        print(f"runtime unknown absent={source!r}", flush=True)
        failed = load(source)
        error = require_parse_failure(failed)
        print(
            f"runtime unknown absent ok={failed.ok!r} "
            f"report={observer_visible_report(error)!r}",
            flush=True,
        )
        assert failed.ok is False
    cases = (
        (scalar_src, scalar_name, word),
        (seq_src, seq_name, [n1, n2, n3]),
        (map_src, map_name, {key_a: n1, key_b: n2}),
    )
    for source, handle, content in cases:
        doc = require_document(
            parse_with_attached_tags(source, REMEMBER_SPECS, base=SCHEMA_CORE)
        )
        require_remembered(doc, handle, content)
        text = require_yaml_text(
            parse_then_dump_with_attached_tags(
                source, REMEMBER_SPECS, base=SCHEMA_CORE
            )
        )
        require_explicit_local_tag(text, handle)
        assert explicit_local_tag_present(text, handle)
        restored = require_document(
            parse_dump_parse_with_attached_tags(
                source, REMEMBER_SPECS, base=SCHEMA_CORE
            )
        )
        require_remembered(restored, handle, content)


# ---------------------------------------------------------------------------
# F. Schema must keep !!str; implicit+prefix cannot attach
# ---------------------------------------------------------------------------


def test_schema_without_str_cannot_be_obtained():
    result = attempt_schema_create([])
    error = require_schema_unusable(result)
    print(
        f"empty-create ok={result.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_schema_nonempty_without_str_cannot_be_obtained():
    harmless = scalar_text_spec(unique_local_tag())
    result = attempt_schema_create([harmless])
    error = require_schema_unusable(result)
    print(
        f"nonempty-no-str ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_implicit_prefix_scalar_cannot_attach():
    handle = unique_local_tag()
    stamp = unique_token()
    bad = scalar_stamp_spec(handle, stamp, prefix=True, implicit=True)
    result = attempt_schema_attach([bad], base=SCHEMA_CORE)
    error = require_schema_unusable(result)
    print(
        f"implicit-prefix ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_nonimplicit_prefix_scalar_can_attach():
    handle = unique_local_tag()
    stamp = unique_token()
    good = scalar_stamp_spec(handle, stamp, prefix=True, implicit=False)
    attached = attempt_schema_attach([good], base=SCHEMA_CORE)
    assert attached.ok, (
        f"non-implicit prefix scalar must attach; report="
        f"{attached.error!r}"
    )
    suffix = unique_token()
    number = core_int_token()
    source = f"{handle}{suffix} {number}"
    print(f"legal prefix source={source!r}", flush=True)
    doc = require_document(
        parse_with_attached_tags(source, [good], base=SCHEMA_CORE)
    )
    assert _has_stamp(doc, stamp)


def test_attach_preserves_str_on_four_builtins():
    handle = unique_local_tag()
    field = unique_token()
    spec = scalar_int_object_spec(handle, field=field)
    number = core_int_token()
    for base in (SCHEMA_FAILSAFE, SCHEMA_JSON, SCHEMA_CORE, SCHEMA_YAML11):
        word = non_bool_word()
        source = f"live: {handle} {number}\nplain: {word}\n"
        print(
            f"str-preserve base={base} word={word!r} tagged={handle} {number}",
            flush=True,
        )
        doc = require_plain_mapping(
            require_document(parse_with_attached_tags(source, [spec], base=base))
        )
        live = require_caller_mapping(mapping_get(doc, "live"))
        assert value_holds_numbers(live, [number]), (
            f"{base} must resolve the attached tag; got {live!r}"
        )
        assert is_string_text(mapping_get(doc, "plain"), word), (
            f"{base} must still construct the word as a string; got {doc!r}"
        )
        root = require_document(
            parse_with_attached_tags(word, [spec], base=base)
        )
        assert is_string_text(root, word), (
            f"{base} must still construct the word as a string; got {root!r}"
        )


def test_custom_scalar_works_on_failsafe_json_yaml11():
    handle = unique_local_tag()
    field = unique_token()
    number = core_int_token()
    spec = scalar_int_object_spec(handle, field=field)
    source = f"{handle} {number}"
    for base in (SCHEMA_FAILSAFE, SCHEMA_JSON, SCHEMA_YAML11):
        print(f"custom scalar base={base} source={source!r}", flush=True)
        obj = require_caller_mapping(
            require_document(parse_with_attached_tags(source, [spec], base=base))
        )
        assert value_holds_numbers(obj, [number])
        text = require_yaml_text(
            parse_then_dump_with_attached_tags(source, [spec], base=base)
        )
        require_explicit_local_tag(text, handle)
        restored = require_caller_mapping(
            require_document(
                parse_dump_parse_with_attached_tags(source, [spec], base=base)
            )
        )
        assert value_holds_numbers(restored, [number])


def test_attach_to_already_extended_schema():
    groups = [[TAG2_SPEC], [POINT_SPEC]]
    tag2 = require_caller_mapping(
        require_document(
            parse_with_sequential_attach(TAG2_TEN, groups, base=SCHEMA_CORE)
        )
    )
    assert value_holds_numbers(tag2, [10])
    point = require_caller_mapping(
        require_document(
            parse_with_sequential_attach(POINT_TRIPLE, groups, base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(point, "x"), 10)
    word = non_bool_word()
    text = require_document(
        parse_with_sequential_attach(word, groups, base=SCHEMA_CORE)
    )
    assert is_string_text(text, word)


# ---------------------------------------------------------------------------
# G. Built-in tags remain; same name+kind+flag replaces
# ---------------------------------------------------------------------------


def test_core_builtins_remain_after_custom_tag():
    source = f"live: {TAG2_TEN}\nanswer: 42\nflag: true\n"
    print(f"core remain source={source!r}", flush=True)
    mapping = require_plain_mapping(
        require_document(
            parse_with_attached_tags(source, [TAG2_SPEC], base=SCHEMA_CORE)
        )
    )
    live = require_caller_mapping(mapping_get(mapping, "live"))
    assert value_holds_numbers(live, [10]), (
        f"attached !tag2 must be live on Core; got {live!r}"
    )
    assert is_number_not_string(mapping_get(mapping, "answer"), 42)
    flag = mapping_get(mapping, "flag")
    print(f"core true after custom={flag!r}", flush=True)
    assert is_bool(flag, True)
    answer_only = require_plain_mapping(
        require_document(
            parse_with_attached_tags("answer: 42", [TAG2_SPEC], base=SCHEMA_CORE)
        )
    )
    assert is_number_not_string(mapping_get(answer_only, "answer"), 42)
    root_true = require_document(
        parse_with_attached_tags("true", [TAG2_SPEC], base=SCHEMA_CORE)
    )
    assert is_bool(root_true, True)


def test_yaml11_builtins_remain_after_custom_tag():
    handle = unique_local_tag()
    field = unique_token()
    spec = scalar_int_object_spec(handle, field=field)
    number = core_int_token()
    word = unique_token()
    source = (
        f"live: {handle} {number}\n"
        f"flag: yes\n"
        f"items: !!set {{ {word} }}\n"
    )
    print(f"yaml11 remain source={source!r}", flush=True)
    doc = require_plain_mapping(
        require_document(
            parse_with_attached_tags(source, [spec], base=SCHEMA_YAML11)
        )
    )
    live = require_caller_mapping(mapping_get(doc, "live"))
    assert value_holds_numbers(live, [number]), (
        f"attached tag must be live on YAML 1.1; got {live!r}"
    )
    flag = mapping_get(doc, "flag")
    print(f"yaml11 yes after custom={flag!r}", flush=True)
    assert is_bool(flag, True)
    observed = require_js_set(mapping_get(doc, "items"))
    assert word in observed, f"!!set must still hold {word!r}; got {observed!r}"
    root_yes = require_document(
        parse_with_attached_tags("yes", [spec], base=SCHEMA_YAML11)
    )
    assert is_bool(root_yes, True)
    set_only = require_js_set(
        require_document(
            parse_with_attached_tags(
                f"!!set {{ {word} }}\n", [spec], base=SCHEMA_YAML11
            )
        )
    )
    assert word in set_only, f"!!set must still hold {word!r}; got {set_only!r}"


def test_failsafe_and_json_builtins_remain():
    handle = unique_local_tag()
    field = unique_token()
    spec = scalar_int_object_spec(handle, field=field)
    number = core_int_token()
    failsafe_src = f"live: {handle} {number}\nnum: 42\n"
    print(f"failsafe remain source={failsafe_src!r}", flush=True)
    failsafe = require_plain_mapping(
        require_document(
            parse_with_attached_tags(failsafe_src, [spec], base=SCHEMA_FAILSAFE)
        )
    )
    failsafe_live = require_caller_mapping(mapping_get(failsafe, "live"))
    assert value_holds_numbers(failsafe_live, [number]), (
        f"attached tag must be live on Failsafe; got {failsafe_live!r}"
    )
    got42 = mapping_get(failsafe, "num")
    print(f"failsafe 42 after custom={got42!r}", flush=True)
    assert is_string_text(got42, "42")
    json_src = f"live: {handle} {number}\nflag: true\nword: yes\n"
    print(f"json remain source={json_src!r}", flush=True)
    json_doc = require_plain_mapping(
        require_document(
            parse_with_attached_tags(json_src, [spec], base=SCHEMA_JSON)
        )
    )
    json_live = require_caller_mapping(mapping_get(json_doc, "live"))
    assert value_holds_numbers(json_live, [number]), (
        f"attached tag must be live on JSON; got {json_live!r}"
    )
    json_true = mapping_get(json_doc, "flag")
    json_yes = mapping_get(json_doc, "word")
    assert is_bool(json_true, True)
    assert is_string_text(json_yes, "yes")
    failsafe_root = require_document(
        parse_with_attached_tags("42", [spec], base=SCHEMA_FAILSAFE)
    )
    assert is_string_text(failsafe_root, "42")
    json_true_root = require_document(
        parse_with_attached_tags("true", [spec], base=SCHEMA_JSON)
    )
    json_yes_root = require_document(
        parse_with_attached_tags("yes", [spec], base=SCHEMA_JSON)
    )
    assert is_bool(json_true_root, True)
    assert is_string_text(json_yes_root, "yes")


def test_same_name_kind_prefix_flag_replaces():
    stamp_a = unique_token()
    stamp_b = unique_token()
    first = scalar_stamp_spec(TAG2, stamp_a)
    second = scalar_stamp_spec(TAG2, stamp_b)
    only_first = require_document(
        parse_with_attached_tags(TAG2_TEN, [first], base=SCHEMA_CORE)
    )
    assert _has_stamp(only_first, stamp_a)
    assert not _has_stamp(only_first, stamp_b)
    replaced = require_document(
        parse_with_sequential_attach(TAG2_TEN, [[first], [second]], base=SCHEMA_CORE)
    )
    print(f"replaced stamps first={_stamp_texts(only_first)!r} "
          f"second={_stamp_texts(replaced)!r}", flush=True)
    assert _has_stamp(replaced, stamp_b)
    assert not _has_stamp(replaced, stamp_a)


def test_prefix_same_flag_replaces():
    prefix = unique_local_tag()
    suffix = unique_token()
    handle = prefix + suffix
    number = core_int_token()
    source = f"{handle} {number}"
    stamp_a = unique_token()
    stamp_b = unique_token()
    first = scalar_stamp_spec(prefix, stamp_a, prefix=True)
    second = scalar_stamp_spec(prefix, stamp_b, prefix=True)
    print(f"prefix replace source={source!r}", flush=True)
    only_first = require_document(
        parse_with_attached_tags(source, [first], base=SCHEMA_CORE)
    )
    assert _has_stamp(only_first, stamp_a)
    replaced = require_document(
        parse_with_sequential_attach(source, [[first], [second]], base=SCHEMA_CORE)
    )
    assert _has_stamp(replaced, stamp_b)
    assert not _has_stamp(replaced, stamp_a)


def test_sequence_same_name_kind_flag_replaces():
    handle = unique_local_tag()
    stamp_a = unique_token()
    stamp_b = unique_token()
    left, right = distinct_core_ints(2)
    source = f"{handle} [{left}, {right}]"
    first = sequence_stamp_spec(handle, stamp_a)
    second = sequence_stamp_spec(handle, stamp_b)
    print(f"sequence replace source={source!r}", flush=True)
    only_first = require_document(
        parse_with_attached_tags(source, [first], base=SCHEMA_CORE)
    )
    assert _has_stamp(only_first, stamp_a)
    replaced = require_document(
        parse_with_sequential_attach(source, [[first], [second]], base=SCHEMA_CORE)
    )
    assert _has_stamp(replaced, stamp_b)
    assert not _has_stamp(replaced, stamp_a)


def test_replacement_does_not_drop_other_prefix():
    exact_a = unique_token()
    exact_b = unique_token()
    prefix_stamp = unique_token()
    first_exact = scalar_stamp_spec(FOO, exact_a)
    prefix = scalar_stamp_spec(FOO, prefix_stamp, prefix=True)
    second_exact = scalar_stamp_spec(FOO, exact_b)
    baseline_foo2 = require_document(
        parse_with_attached_tags("!foo2 2", [prefix, first_exact], base=SCHEMA_CORE)
    )
    assert _has_stamp(baseline_foo2, prefix_stamp)
    replaced_exact = require_document(
        parse_with_sequential_attach(
            "!foo 1",
            [[prefix, first_exact], [second_exact]],
            base=SCHEMA_CORE,
        )
    )
    assert _has_stamp(replaced_exact, exact_b)
    assert not _has_stamp(replaced_exact, exact_a)
    still_prefix = require_document(
        parse_with_sequential_attach(
            "!foo2 2",
            [[prefix, first_exact], [second_exact]],
            base=SCHEMA_CORE,
        )
    )
    print(f"prefix after exact replace={_stamp_texts(still_prefix)!r}", flush=True)
    assert _has_stamp(still_prefix, prefix_stamp)


def test_runtime_tag_replacement():
    handle = unique_local_tag()
    stamp_a = unique_token()
    stamp_b = unique_token()
    number = core_int_token()
    source = f"{handle} {number}"
    first = scalar_stamp_spec(handle, stamp_a)
    second = scalar_stamp_spec(handle, stamp_b)
    print(f"runtime replace source={source!r}", flush=True)
    only_first = require_document(
        parse_with_attached_tags(source, [first], base=SCHEMA_CORE)
    )
    assert _has_stamp(only_first, stamp_a)
    replaced = require_document(
        parse_with_sequential_attach(source, [[first], [second]], base=SCHEMA_CORE)
    )
    assert _has_stamp(replaced, stamp_b)
    assert not _has_stamp(replaced, stamp_a)


# ---------------------------------------------------------------------------
# H. Converting recursive alias fails; default recursive still succeeds
# ---------------------------------------------------------------------------


def test_default_recursive_sequence_still_succeeds():
    live = require_document(
        parse_with_attached_tags(
            POINT_PAIR, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
        )
    )
    assert value_holds_numbers(live, [10, 20]), (
        "converting tag must be attached before the default-recursive arm"
    )
    seq = require_sequence(
        require_document(
            parse_with_attached_tags(
                RECURSIVE_DEFAULT, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
            )
        )
    )
    print(f"default recursive len={len(seq)}", flush=True)
    assert len(seq) == 1, f"default recursive sequence must have one item; {seq!r}"
    assert same_identity(seq, seq[0]), (
        "default recursive item must be the sequence itself"
    )


def test_converting_point_recursive_alias_fails():
    live = require_document(
        parse_with_attached_tags(
            POINT_PAIR, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
        )
    )
    assert value_holds_numbers(live, [10, 20])
    print(f"converting recursive source={RECURSIVE_POINT!r}", flush=True)
    require_parse_failure(
        parse_with_attached_tags(
            RECURSIVE_POINT, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
        )
    )


def test_point_refuses_one_coordinate():
    live = require_document(
        parse_with_attached_tags(
            POINT_PAIR, [FROZEN_POINT_SPEC], base=SCHEMA_CORE
        )
    )
    assert value_holds_numbers(live, [10, 20]), (
        "two-coordinate parse must succeed before the one-item refusal"
    )
    print(f"one coordinate source={POINT_ONE!r}", flush=True)
    require_parse_failure(
        parse_with_attached_tags(POINT_ONE, [FROZEN_POINT_SPEC], base=SCHEMA_CORE)
    )


def test_runtime_tag_refuses_wrong_arity():
    handle = unique_local_tag()
    spec = sequence_frozen_point_spec(handle, arity=2)
    left, right = distinct_core_ints(2)
    ok_src = f"{handle} [{left}, {right}]"
    bad_src = f"{handle} [{left}]"
    print(f"runtime arity ok={ok_src!r} bad={bad_src!r}", flush=True)
    live = require_document(
        parse_with_attached_tags(ok_src, [spec], base=SCHEMA_CORE)
    )
    assert value_holds_numbers(live, [left, right])
    require_parse_failure(parse_with_attached_tags(bad_src, [spec], base=SCHEMA_CORE))


def test_runtime_converting_recursive_alias_fails():
    handle = unique_local_tag()
    anchor = unique_token()
    spec = sequence_frozen_point_spec(handle, arity=2)
    left, right = distinct_core_ints(2)
    live_src = f"{handle} [{left}, {right}]"
    plain = f"&{anchor} [*{anchor}]"
    tagged = f"&{anchor} {handle} [*{anchor}]"
    print(f"runtime recursive plain={plain!r} tagged={tagged!r}", flush=True)
    live = require_document(
        parse_with_attached_tags(live_src, [spec], base=SCHEMA_CORE)
    )
    assert value_holds_numbers(live, [left, right])
    seq = require_sequence(
        require_document(parse_with_attached_tags(plain, [spec], base=SCHEMA_CORE))
    )
    assert same_identity(seq, seq[0])
    require_parse_failure(parse_with_attached_tags(tagged, [spec], base=SCHEMA_CORE))
