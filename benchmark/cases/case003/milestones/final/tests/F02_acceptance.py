# feature: F02
"""Built-in schemas and YAML 1.2 type resolution (FP-02).

Assertions stay at the PRD's precision: constructed types and values
the sentences name, schema-switch contrasts on the same bytes, and
refusals that yield no usable document. Exception class names, failure
wording, YAML 1.1 sexagesimal/underscore float magnitudes, and the
sign bit of ``0.`` / ``-0.0`` are not pinned.
"""

from __future__ import annotations

import pytest

from _harness import load, load_all
from _helpers import (
    YAML11_FALSE_WORDS,
    YAML11_TRUE_WORDS,
    bin_int_token,
    core_int_token,
    hex_int_token,
    illegal_sexagesimal_token,
    is_any_finite_number,
    is_bool,
    is_finite_number,
    is_js_null,
    is_nan_number,
    is_neg_inf,
    is_number_not_string,
    is_pos_inf,
    is_string_text,
    json_legal_decimal_token,
    leading_dot_float_token,
    leading_zero_float_token,
    leading_zero_octal_token,
    mapping_get,
    minus_hex_int_token,
    non_bool_word,
    non_float_text,
    non_int_text,
    nonempty_seq_scalar,
    observer_visible_report,
    overflow_float_token,
    oversized_decimal_token,
    plus_decimal_int_token,
    plus_plain_decimal_token,
    plus_zero_o_int_token,
    require_document,
    require_parse_failure,
    require_plain_mapping,
    require_sequence,
    sexagesimal_float_token,
    sexagesimal_int_token,
    signed_underscore_exponent_float_token,
    trailing_dot_token,
    underscore_float_token,
    underscore_int_token,
    unique_token,
    unsigned_exponent_float_token,
    with_core_schema,
    with_failsafe_schema,
    with_json_schema,
    with_yaml11_schema,
    zero_o_int_token,
)

TYPED_SCHEMA_FNS = (with_json_schema, with_core_schema, with_yaml11_schema)

CORE_BOOL_WORDS = (
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("false", False),
    ("False", False),
    ("FALSE", False),
)

CORE_INF_SPELLINGS = (
    (".inf", 1),
    (".Inf", 1),
    (".INF", 1),
    ("-.inf", -1),
    ("-.Inf", -1),
    ("-.INF", -1),
    ("+.inf", 1),
    ("+.Inf", 1),
    ("+.INF", 1),
)

CORE_NAN_SPELLINGS = (".nan", ".NaN", ".NAN")

YAML11_BOOL_CASES = (
    *[(word, True) for word in YAML11_TRUE_WORDS],
    *[(word, False) for word in YAML11_FALSE_WORDS],
)


def _typed_opts():
    return (with_json_schema(), with_core_schema(), with_yaml11_schema())


# ---------------------------------------------------------------------------
# A. Failsafe: plain scalars stay strings; sequences and mappings construct
# ---------------------------------------------------------------------------


def test_failsafe_v_1_is_string():
    doc = require_document(load("v: 1", with_failsafe_schema()))
    value = mapping_get(doc, "v")
    print(f"failsafe v={value!r} type={type(value).__name__}", flush=True)
    assert is_string_text(value, "1"), (
        f"Failsafe v: 1 must be the string 1, not a number; got {value!r}"
    )


def test_failsafe_flag_true_is_string():
    doc = require_document(load("flag: true", with_failsafe_schema()))
    value = mapping_get(doc, "flag")
    print(f"failsafe flag={value!r} type={type(value).__name__}", flush=True)
    assert is_string_text(value, "true"), (
        f"Failsafe flag: true must be the string true; got {value!r}"
    )


def test_failsafe_runtime_plain_stays_string():
    key = unique_token()
    number = core_int_token()
    source = f"{key}: {number}"
    print(f"source={source!r}", flush=True)
    doc = require_document(load(source, with_failsafe_schema()))
    value = mapping_get(doc, key)
    print(f"value={value!r}", flush=True)
    assert is_string_text(value, str(number)), (
        f"Failsafe plain {number} must stay the digit text; got {value!r}"
    )


def test_failsafe_typed_tokens_stay_strings():
    for token in ("True", "~"):
        value = require_document(load(token, with_failsafe_schema()))
        print(f"failsafe token={token!r} value={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"Failsafe {token} must stay that text; got {value!r}"
        )


def test_failsafe_sequence_and_mapping_construct():
    public = require_document(load("- a\n- b", with_failsafe_schema()))
    public_seq = require_sequence(public)
    print(f"public-seq={public_seq!r}", flush=True)
    assert public_seq == ["a", "b"]
    assert is_string_text(public_seq[0], "a")
    assert is_string_text(public_seq[1], "b")

    typed_src = "- 1\n- true"
    core_items = require_sequence(
        require_document(load(typed_src, with_core_schema()))
    )
    print(f"core-typed={core_items!r}", flush=True)
    assert is_number_not_string(core_items[0], 1), (
        f"Core baseline item 1 must be the number 1; got {core_items[0]!r}"
    )
    assert is_bool(core_items[1], True), (
        f"Core baseline item true must be boolean true; got {core_items[1]!r}"
    )
    failsafe_items = require_sequence(
        require_document(load(typed_src, with_failsafe_schema()))
    )
    print(f"failsafe-typed={failsafe_items!r}", flush=True)
    assert is_string_text(failsafe_items[0], "1")
    assert is_string_text(failsafe_items[1], "true")

    first, second = unique_token(), unique_token()
    runtime_src = f"- {first}\n- {second}"
    print(f"runtime-seq={runtime_src!r}", flush=True)
    runtime = require_sequence(
        require_document(load(runtime_src, with_failsafe_schema()))
    )
    assert runtime == [first, second]
    assert is_string_text(runtime[0], first)
    assert is_string_text(runtime[1], second)

    key, word = unique_token(), unique_token()
    mapping_src = f"{key}: {word}"
    print(f"runtime-map={mapping_src!r}", flush=True)
    mapping = require_plain_mapping(
        require_document(load(mapping_src, with_failsafe_schema()))
    )
    assert is_string_text(mapping_get(mapping, key), word)


# ---------------------------------------------------------------------------
# B. JSON implicit null / boolean / integer / float
# ---------------------------------------------------------------------------


def test_json_lowercase_null_only():
    doc = require_document(load("english: null", with_json_schema()))
    value = mapping_get(doc, "english")
    print(f"json null={value!r}", flush=True)
    assert is_js_null(value), f"JSON english: null must be null; got {value!r}"


def test_json_tilde_empty_and_cased_null_stay_strings():
    tilde = mapping_get(
        require_document(load("canonical: ~", with_json_schema())),
        "canonical",
    )
    print(f"json tilde={tilde!r}", flush=True)
    assert is_string_text(tilde, "~"), f"JSON ~ must stay the string ~; got {tilde!r}"

    empty = mapping_get(
        require_document(load("empty:\n", with_json_schema())),
        "empty",
    )
    print(f"json empty={empty!r}", flush=True)
    assert is_string_text(empty, ""), (
        f"JSON empty mapping value must be \"\"; got {empty!r}"
    )

    for token in ("Null", "NULL"):
        value = require_document(load(token, with_json_schema()))
        print(f"json cased-null {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"JSON {token} must stay that string; got {value!r}"
        )


def test_json_explicit_empty_null_is_null():
    implicit = mapping_get(
        require_document(load("english: null", with_json_schema())),
        "english",
    )
    assert is_js_null(implicit), "live baseline: implicit null must be null"
    explicit = require_document(load("!!null", with_json_schema()))
    print(f"json explicit !!null={explicit!r}", flush=True)
    assert is_js_null(explicit), f"JSON empty !!null must be null; got {explicit!r}"


def test_json_only_true_false_are_booleans():
    assert is_bool(require_document(load("true", with_json_schema())), True)
    assert is_bool(require_document(load("false", with_json_schema())), False)
    for word in ("True", "TRUE", "False", "FALSE"):
        value = require_document(load(word, with_json_schema()))
        print(f"json bool-word {word}={value!r}", flush=True)
        assert is_string_text(value, word), (
            f"JSON {word} must stay that string; got {value!r}"
        )


@pytest.mark.parametrize("word", YAML11_TRUE_WORDS + YAML11_FALSE_WORDS)
def test_json_yaml11_words_stay_strings(word: str):
    value = require_document(load(word, with_json_schema()))
    print(f"json yaml11-word {word}={value!r}", flush=True)
    assert is_string_text(value, word), (
        f"JSON {word} must stay that string; got {value!r}"
    )


def test_json_integers_reject_plus_zero_and_bases():
    legal = require_document(load("685230", with_json_schema()))
    print(f"json 685230={legal!r}", flush=True)
    assert is_number_not_string(legal, 685230), (
        f"JSON 685230 must be that number; got {legal!r}"
    )
    for token in ("+685230", "0123", "0b1010", "0o123", "0x1A"):
        value = require_document(load(token, with_json_schema()))
        print(f"json rejected-int {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"JSON {token} must stay that string; got {value!r}"
        )


def test_json_floats_exponents_and_rejected_forms():
    neg_exp = require_document(load("-2E+05", with_json_schema()))
    print(f"json -2E+05={neg_exp!r}", flush=True)
    assert is_finite_number(neg_exp, -2 * (10 ** 5)), (
        f"JSON -2E+05 must be -2 * 10**5; got {neg_exp!r}"
    )
    pos_exp = require_document(load("12e03", with_json_schema()))
    print(f"json 12e03={pos_exp!r}", flush=True)
    assert is_finite_number(pos_exp, 12 * (10 ** 3)), (
        f"JSON 12e03 must be 12 * 10**3; got {pos_exp!r}"
    )
    for token in ("+12.3", ".5", ".inf", ".nan", "01.0"):
        value = require_document(load(token, with_json_schema()))
        print(f"json rejected-float {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"JSON {token} must stay that string; got {value!r}"
        )


def test_json_runtime_decimal_and_rejected_shapes():
    text, number = json_legal_decimal_token()
    print(f"json runtime decimal={text!r}", flush=True)
    got = require_document(load(text, with_json_schema()))
    assert is_number_not_string(got, number), (
        f"JSON {text} must be the number {number}; got {got!r}"
    )

    plus = plus_decimal_int_token()
    print(f"json runtime plus={plus!r}", flush=True)
    assert is_string_text(
        require_document(load(plus, with_json_schema())), plus
    )

    leading_dot = leading_dot_float_token()
    print(f"json runtime leading-dot={leading_dot!r}", flush=True)
    assert is_string_text(
        require_document(load(leading_dot, with_json_schema())), leading_dot
    )

    leading_zero = leading_zero_float_token()
    print(f"json runtime leading-zero-float={leading_zero!r}", flush=True)
    assert is_string_text(
        require_document(load(leading_zero, with_json_schema())), leading_zero
    )


# ---------------------------------------------------------------------------
# C. Core (the parse default)
# ---------------------------------------------------------------------------


def test_core_implicit_nulls():
    empty = mapping_get(
        require_document(load("empty:\n", with_core_schema())),
        "empty",
    )
    print(f"core empty={empty!r}", flush=True)
    assert is_js_null(empty), f"Core empty scalar must be null; got {empty!r}"
    for token in ("~", "null", "Null", "NULL"):
        value = require_document(load(token, with_core_schema()))
        print(f"core null {token}={value!r}", flush=True)
        assert is_js_null(value), f"Core {token} must be null; got {value!r}"


@pytest.mark.parametrize("word,expected", CORE_BOOL_WORDS)
def test_core_implicit_booleans(word: str, expected: bool):
    value = require_document(load(word, with_core_schema()))
    print(f"core bool {word}={value!r}", flush=True)
    assert is_bool(value, expected), (
        f"Core {word} must be boolean {expected}; got {value!r}"
    )


@pytest.mark.parametrize("word", YAML11_TRUE_WORDS + YAML11_FALSE_WORDS)
def test_core_yaml11_words_stay_strings(word: str):
    value = require_document(load(word, with_core_schema()))
    print(f"core yaml11-word {word}={value!r}", flush=True)
    assert is_string_text(value, word), (
        f"Core {word} must stay that string; got {value!r}"
    )


def test_core_implicit_integers():
    plus = require_document(load("+685230", with_core_schema()))
    print(f"core +685230={plus!r}", flush=True)
    assert is_number_not_string(plus, 685230)

    leading_zero = require_document(load("0123", with_core_schema()))
    print(f"core 0123={leading_zero!r}", flush=True)
    assert is_number_not_string(leading_zero, 123), (
        f"Core 0123 must be decimal 123, not 83; got {leading_zero!r}"
    )

    octal = require_document(load("0o123", with_core_schema()))
    print(f"core 0o123={octal!r}", flush=True)
    assert is_number_not_string(octal, 83)

    hexa = require_document(load("0x1A", with_core_schema()))
    print(f"core 0x1A={hexa!r}", flush=True)
    assert is_number_not_string(hexa, 26)

    for token in ("0b1010", "+0o123", "-0x1A", "1_000", "1:23"):
        value = require_document(load(token, with_core_schema()))
        print(f"core stay-string {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"Core {token} must stay that string; got {value!r}"
        )


def test_core_runtime_octal_and_hex():
    oct_text, oct_value = zero_o_int_token()
    print(f"core runtime 0o={oct_text!r} expect={oct_value}", flush=True)
    got_oct = require_document(load(oct_text, with_core_schema()))
    assert is_number_not_string(got_oct, oct_value), (
        f"Core {oct_text} must be {oct_value}; got {got_oct!r}"
    )

    hex_text, hex_value = hex_int_token()
    print(f"core runtime 0x={hex_text!r} expect={hex_value}", flush=True)
    got_hex = require_document(load(hex_text, with_core_schema()))
    assert is_number_not_string(got_hex, hex_value), (
        f"Core {hex_text} must be {hex_value}; got {got_hex!r}"
    )


def test_core_runtime_stay_string_notations():
    cases = [
        bin_int_token()[0],
        plus_zero_o_int_token()[0],
        minus_hex_int_token()[0],
        underscore_int_token()[0],
        sexagesimal_int_token()[0],
    ]
    for token in cases:
        value = require_document(load(token, with_core_schema()))
        print(f"core runtime stay-string {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"Core {token} must stay that string; got {value!r}"
        )


def test_core_explicit_int_signed_forms():
    public_plus = require_document(load("!!int +0o123", with_core_schema()))
    print(f"core !!int +0o123={public_plus!r}", flush=True)
    assert is_number_not_string(public_plus, 83)

    public_minus = require_document(load("!!int -0x1A", with_core_schema()))
    print(f"core !!int -0x1A={public_minus!r}", flush=True)
    assert is_number_not_string(public_minus, -26)

    plus_text, plus_value = plus_zero_o_int_token()
    print(f"core runtime !!int {plus_text} expect={plus_value}", flush=True)
    got_plus = require_document(load(f"!!int {plus_text}", with_core_schema()))
    assert is_number_not_string(got_plus, plus_value)

    minus_text, minus_value = minus_hex_int_token()
    print(f"core runtime !!int {minus_text} expect={minus_value}", flush=True)
    got_minus = require_document(load(f"!!int {minus_text}", with_core_schema()))
    assert is_number_not_string(got_minus, minus_value)


def test_core_implicit_floats_and_specials():
    half = require_document(load(".5", with_core_schema()))
    print(f"core .5={half!r}", flush=True)
    assert is_finite_number(half, 0.5)

    trailing = require_document(load("12.", with_core_schema()))
    print(f"core 12.={trailing!r}", flush=True)
    assert is_finite_number(trailing, 12)

    plus_a_text, plus_a_value = plus_plain_decimal_token()
    print(f"core plus-decimal {plus_a_text}={plus_a_value}", flush=True)
    assert is_finite_number(
        require_document(load(plus_a_text, with_core_schema())),
        plus_a_value,
    )
    plus_b_text, plus_b_value = plus_plain_decimal_token()
    print(f"core plus-decimal-2 {plus_b_text}={plus_b_value}", flush=True)
    assert is_finite_number(
        require_document(load(plus_b_text, with_core_schema())),
        plus_b_value,
    )

    trail_text, trail_value = trailing_dot_token()
    print(f"core runtime trailing-dot {trail_text}={trail_value}", flush=True)
    assert is_finite_number(
        require_document(load(trail_text, with_core_schema())),
        trail_value,
    )

    for spelling, sign in CORE_INF_SPELLINGS:
        value = require_document(load(spelling, with_core_schema()))
        print(f"core inf {spelling}={value!r}", flush=True)
        if sign > 0:
            assert is_pos_inf(value), f"Core {spelling} must be +inf; got {value!r}"
        else:
            assert is_neg_inf(value), f"Core {spelling} must be -inf; got {value!r}"

    for spelling in CORE_NAN_SPELLINGS:
        value = require_document(load(spelling, with_core_schema()))
        print(f"core nan {spelling}={value!r}", flush=True)
        assert is_nan_number(value), f"Core {spelling} must be NaN; got {value!r}"

    underscored = require_document(load("1_000.0", with_core_schema()))
    print(f"core 1_000.0={underscored!r}", flush=True)
    assert is_string_text(underscored, "1_000.0")

    runtime_us = underscore_float_token()
    print(f"core runtime underscored-float={runtime_us!r}", flush=True)
    assert is_string_text(
        require_document(load(runtime_us, with_core_schema())), runtime_us
    )

    lone_dot = require_document(load(".", with_core_schema()))
    print(f"core lone-dot={lone_dot!r}", flush=True)
    assert is_string_text(lone_dot, ".")


def test_core_overflow_1e999_string_then_explicit_fails():
    implicit = require_document(load("1e999", with_core_schema()))
    print(f"core implicit 1e999={implicit!r}", flush=True)
    assert is_string_text(implicit, "1e999"), (
        f"Core implicit 1e999 must stay that string; got {implicit!r}"
    )
    require_parse_failure(load("!!float 1e999", with_core_schema()))


def test_core_runtime_overflow_string_then_explicit_fails():
    token = overflow_float_token()
    print(f"core runtime overflow={token!r}", flush=True)
    implicit = require_document(load(token, with_core_schema()))
    assert is_string_text(implicit, token), (
        f"Core implicit {token} must stay that string; got {implicit!r}"
    )
    require_parse_failure(load(f"!!float {token}", with_core_schema()))


def test_default_schema_is_core_both_entries():
    mapping = require_plain_mapping(require_document(load("v: 1")))
    assert is_number_not_string(mapping_get(mapping, "v"), 1)

    assert is_bool(require_document(load("True")), True)
    assert is_string_text(require_document(load("yes")), "yes")
    assert is_number_not_string(require_document(load("0o123")), 83)
    omitted_0123 = require_document(load("0123"))
    print(f"omitted 0123={omitted_0123!r}", flush=True)
    assert is_number_not_string(omitted_0123, 123), (
        f"omitted-schema 0123 must be decimal 123; got {omitted_0123!r}"
    )

    happy = require_document(load_all("1\n---\ntrue\n"))
    print(f"omitted multi 1/true={happy!r}", flush=True)
    happy_list = require_sequence(happy)
    assert len(happy_list) == 2
    assert is_number_not_string(happy_list[0], 1)
    assert is_bool(happy_list[1], True)

    discriminating = require_document(load_all("True\n---\n0123\n"))
    print(f"omitted multi True/0123={discriminating!r}", flush=True)
    pair = require_sequence(discriminating)
    assert len(pair) == 2
    assert is_bool(pair[0], True), (
        f"omitted multi True must be boolean true (not JSON); got {pair[0]!r}"
    )
    assert is_number_not_string(pair[1], 123), (
        f"omitted multi 0123 must be 123 (not YAML 1.1 octal); got {pair[1]!r}"
    )


def test_explicit_core_matches_omitted_schema():
    public_omitted = mapping_get(require_document(load("v: 1")), "v")
    public_core = mapping_get(
        require_document(load("v: 1", with_core_schema())), "v"
    )
    print(f"v:1 omitted={public_omitted!r} core={public_core!r}", flush=True)
    assert is_number_not_string(public_omitted, 1)
    assert public_omitted == public_core

    key = unique_token()
    number = core_int_token()
    source = f"{key}: {number}"
    omitted = mapping_get(require_document(load(source)), key)
    explicit = mapping_get(
        require_document(load(source, with_core_schema())), key
    )
    print(f"runtime omitted={omitted!r} core={explicit!r}", flush=True)
    assert is_number_not_string(omitted, number)
    assert omitted == explicit

    omitted_0123 = require_document(load("0123"))
    explicit_0123 = require_document(load("0123", with_core_schema()))
    print(f"0123 omitted={omitted_0123!r} core={explicit_0123!r}", flush=True)
    assert is_number_not_string(omitted_0123, 123)
    assert omitted_0123 == explicit_0123


# ---------------------------------------------------------------------------
# D. YAML 1.1 implicit boolean / integer / float
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word,expected", CORE_BOOL_WORDS)
def test_yaml11_core_booleans_still_resolve(word: str, expected: bool):
    value = require_document(load(word, with_yaml11_schema()))
    print(f"yaml11 core-bool {word}={value!r}", flush=True)
    assert is_bool(value, expected), (
        f"YAML 1.1 {word} must still be boolean {expected}; got {value!r}"
    )


@pytest.mark.parametrize("word,expected", YAML11_BOOL_CASES)
def test_yaml11_extra_boolean_words(word: str, expected: bool):
    value = require_document(load(word, with_yaml11_schema()))
    print(f"yaml11 extra-bool {word}={value!r}", flush=True)
    assert is_bool(value, expected), (
        f"YAML 1.1 {word} must be boolean {expected}; got {value!r}"
    )


def test_yaml11_implicit_integers():
    cases = (
        ("0123", 83),
        ("0b1010", 10),
        ("0x1A", 26),
        ("1_000", 1000),
        ("1:23", 83),
    )
    for token, expected in cases:
        value = require_document(load(token, with_yaml11_schema()))
        print(f"yaml11 int {token}={value!r}", flush=True)
        assert is_number_not_string(value, expected), (
            f"YAML 1.1 {token} must be {expected}; got {value!r}"
        )

    bin_text, bin_value = bin_int_token()
    print(f"yaml11 runtime 0b={bin_text!r} expect={bin_value}", flush=True)
    assert is_number_not_string(
        require_document(load(bin_text, with_yaml11_schema())), bin_value
    )

    hex_text, hex_value = hex_int_token()
    print(f"yaml11 runtime 0x={hex_text!r} expect={hex_value}", flush=True)
    assert is_number_not_string(
        require_document(load(hex_text, with_yaml11_schema())), hex_value
    )

    lead_text, _decimal, octal = leading_zero_octal_token()
    print(f"yaml11 runtime lead0={lead_text!r} expect={octal}", flush=True)
    assert is_number_not_string(
        require_document(load(lead_text, with_yaml11_schema())), octal
    )


def test_yaml11_rejected_integer_forms():
    for token in ("0o123", "09", "1:99"):
        value = require_document(load(token, with_yaml11_schema()))
        print(f"yaml11 rejected {token}={value!r}", flush=True)
        assert is_string_text(value, token), (
            f"YAML 1.1 {token} must stay that string; got {value!r}"
        )

    zero_o, _ = zero_o_int_token()
    print(f"yaml11 runtime 0o stay-string={zero_o!r}", flush=True)
    assert is_string_text(
        require_document(load(zero_o, with_yaml11_schema())), zero_o
    )

    illegal = illegal_sexagesimal_token()
    print(f"yaml11 runtime illegal sexagesimal={illegal!r}", flush=True)
    assert is_string_text(
        require_document(load(illegal, with_yaml11_schema())), illegal
    )


def test_yaml11_explicit_zero_o_int_fails():
    implicit = require_document(load("0o123", with_yaml11_schema()))
    print(f"yaml11 implicit 0o123={implicit!r}", flush=True)
    assert is_string_text(implicit, "0o123"), (
        "live baseline: YAML 1.1 implicit 0o123 must stay a string"
    )
    require_parse_failure(load("!!int 0o123", with_yaml11_schema()))

    token, _ = zero_o_int_token()
    runtime_implicit = require_document(load(token, with_yaml11_schema()))
    print(f"yaml11 runtime implicit {token}={runtime_implicit!r}", flush=True)
    assert is_string_text(runtime_implicit, token)
    require_parse_failure(load(f"!!int {token}", with_yaml11_schema()))


def test_yaml11_floats_underscore_sexagesimal_signed_exponent():
    sexagesimal = require_document(load("190:20:30.15", with_yaml11_schema()))
    print(
        f"yaml11 190:20:30.15 type={type(sexagesimal).__name__} value={sexagesimal!r}",
        flush=True,
    )
    assert not isinstance(sexagesimal, str), (
        "YAML 1.1 190:20:30.15 must be a float, not a string"
    )
    assert is_any_finite_number(sexagesimal), (
        f"YAML 1.1 190:20:30.15 must be a finite number; got {sexagesimal!r}"
    )

    underscored = require_document(load("685.230_15e+03", with_yaml11_schema()))
    print(
        f"yaml11 685.230_15e+03 type={type(underscored).__name__} value={underscored!r}",
        flush=True,
    )
    assert not isinstance(underscored, str)
    assert is_any_finite_number(underscored), (
        f"YAML 1.1 685.230_15e+03 must be a finite number; got {underscored!r}"
    )

    unsigned = require_document(load("685.23015e03", with_yaml11_schema()))
    print(f"yaml11 685.23015e03={unsigned!r}", flush=True)
    assert is_string_text(unsigned, "685.23015e03"), (
        f"YAML 1.1 unsigned-exponent form must stay a string; got {unsigned!r}"
    )


def test_yaml11_runtime_underscore_and_sexagesimal():
    us_text, us_value = underscore_int_token()
    print(f"yaml11 runtime underscore={us_text!r} expect={us_value}", flush=True)
    assert is_number_not_string(
        require_document(load(us_text, with_yaml11_schema())), us_value
    )

    sex_text, sex_value = sexagesimal_int_token()
    print(f"yaml11 runtime sexagesimal={sex_text!r} expect={sex_value}", flush=True)
    assert is_number_not_string(
        require_document(load(sex_text, with_yaml11_schema())), sex_value
    )


def test_yaml11_runtime_float_classes():
    sex = sexagesimal_float_token()
    sex_value = require_document(load(sex, with_yaml11_schema()))
    print(f"yaml11 runtime sex-float {sex}={sex_value!r}", flush=True)
    assert not isinstance(sex_value, str), (
        f"YAML 1.1 {sex} must be a float, not a string"
    )
    assert is_any_finite_number(sex_value), (
        f"YAML 1.1 {sex} must be a finite number; got {sex_value!r}"
    )

    signed = signed_underscore_exponent_float_token()
    signed_value = require_document(load(signed, with_yaml11_schema()))
    print(f"yaml11 runtime signed-us-float {signed}={signed_value!r}", flush=True)
    assert not isinstance(signed_value, str)
    assert is_any_finite_number(signed_value), (
        f"YAML 1.1 {signed} must be a finite number; got {signed_value!r}"
    )

    unsigned = unsigned_exponent_float_token()
    unsigned_value = require_document(load(unsigned, with_yaml11_schema()))
    print(f"yaml11 runtime unsigned-exp {unsigned}={unsigned_value!r}", flush=True)
    assert is_string_text(unsigned_value, unsigned), (
        f"YAML 1.1 {unsigned} must stay that string; got {unsigned_value!r}"
    )


# ---------------------------------------------------------------------------
# E. Switching schema is the only switch
# ---------------------------------------------------------------------------


def test_schema_switch_v_1():
    core = mapping_get(
        require_document(load("v: 1", with_core_schema())), "v"
    )
    print(f"switch v:1 core={core!r}", flush=True)
    assert is_number_not_string(core, 1), "live baseline: Core v: 1 is the number 1"

    omitted = mapping_get(require_document(load("v: 1")), "v")
    assert is_number_not_string(omitted, 1)

    failsafe = mapping_get(
        require_document(load("v: 1", with_failsafe_schema())), "v"
    )
    print(f"switch v:1 failsafe={failsafe!r}", flush=True)
    assert is_string_text(failsafe, "1")


def test_schema_switch_yes_and_on():
    for word in ("yes", "on"):
        yaml11 = require_document(load(word, with_yaml11_schema()))
        print(f"switch {word} yaml11={yaml11!r}", flush=True)
        assert is_bool(yaml11, True), (
            f"live baseline: YAML 1.1 {word} must be boolean true"
        )
        core = require_document(load(word, with_core_schema()))
        print(f"switch {word} core={core!r}", flush=True)
        assert is_string_text(core, word), (
            f"Core {word} must stay that string; got {core!r}"
        )


def test_schema_switch_0123_three_ways():
    token = "0123"
    json_v = require_document(load(token, with_json_schema()))
    core_v = require_document(load(token, with_core_schema()))
    yaml11_v = require_document(load(token, with_yaml11_schema()))
    print(f"0123 json={json_v!r} core={core_v!r} yaml11={yaml11_v!r}", flush=True)
    assert is_string_text(json_v, "0123")
    assert is_number_not_string(core_v, 123)
    assert is_number_not_string(yaml11_v, 83)
    assert json_v != core_v
    assert core_v != yaml11_v
    assert json_v != yaml11_v


def test_schema_switch_runtime_leading_zero():
    token, decimal, octal = leading_zero_octal_token()
    print(f"runtime lead0={token!r} dec={decimal} oct={octal}", flush=True)
    json_v = require_document(load(token, with_json_schema()))
    core_v = require_document(load(token, with_core_schema()))
    yaml11_v = require_document(load(token, with_yaml11_schema()))
    assert is_string_text(json_v, token)
    assert is_number_not_string(core_v, decimal)
    assert is_number_not_string(yaml11_v, octal)
    assert core_v != yaml11_v


def test_schema_switch_zero_o_prefix():
    core = require_document(load("0o123", with_core_schema()))
    print(f"0o123 core={core!r}", flush=True)
    assert is_number_not_string(core, 83)
    yaml11 = require_document(load("0o123", with_yaml11_schema()))
    print(f"0o123 yaml11={yaml11!r}", flush=True)
    assert is_string_text(yaml11, "0o123")


def test_schema_switch_runtime_zero_o_underscore_sexagesimal():
    oct_text, oct_value = zero_o_int_token()
    print(f"runtime 0o={oct_text!r} expect={oct_value}", flush=True)
    assert is_number_not_string(
        require_document(load(oct_text, with_core_schema())), oct_value
    )
    assert is_string_text(
        require_document(load(oct_text, with_yaml11_schema())), oct_text
    )

    us_text, us_value = underscore_int_token()
    print(f"runtime underscore={us_text!r} expect={us_value}", flush=True)
    assert is_number_not_string(
        require_document(load(us_text, with_yaml11_schema())), us_value
    )
    assert is_string_text(
        require_document(load(us_text, with_core_schema())), us_text
    )

    sex_text, sex_value = sexagesimal_int_token()
    print(f"runtime a:b={sex_text!r} expect={sex_value}", flush=True)
    assert is_number_not_string(
        require_document(load(sex_text, with_yaml11_schema())), sex_value
    )
    assert is_string_text(
        require_document(load(sex_text, with_core_schema())), sex_text
    )


def test_core_rejects_yaml11_notations():
    stay = {
        "1:23": "1:23",
        "1_000": "1_000",
        "yes": "yes",
        "on": "on",
    }
    for token, text in stay.items():
        value = require_document(load(token, with_core_schema()))
        print(f"core rejects-yaml11 {token}={value!r}", flush=True)
        assert is_string_text(value, text), (
            f"Core {token} must stay a string; got {value!r}"
        )
    leading_zero = require_document(load("0123", with_core_schema()))
    print(f"core 0123 not octal={leading_zero!r}", flush=True)
    assert is_number_not_string(leading_zero, 123), (
        f"Core 0123 must be decimal 123, not octal 83; got {leading_zero!r}"
    )
    assert not is_number_not_string(leading_zero, 83)


def test_schema_switch_tilde_and_True():
    json_tilde = require_document(load("~", with_json_schema()))
    print(f"~ json={json_tilde!r}", flush=True)
    assert is_string_text(json_tilde, "~")
    core_tilde = require_document(load("~", with_core_schema()))
    print(f"~ core={core_tilde!r}", flush=True)
    assert is_js_null(core_tilde)

    json_true = require_document(load("True", with_json_schema()))
    print(f"True json={json_true!r}", flush=True)
    assert is_string_text(json_true, "True")
    core_true = require_document(load("True", with_core_schema()))
    print(f"True core={core_true!r}", flush=True)
    assert is_bool(core_true, True)


# ---------------------------------------------------------------------------
# F. Shared forms across the three typed schemas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_fn", TYPED_SCHEMA_FNS, ids=["json", "core", "yaml11"])
def test_shared_decimals_across_typed_schemas(schema_fn):
    opts = schema_fn()
    for token, expected in (("685230", 685230), ("-685230", -685230), ("0", 0)):
        value = require_document(load(token, opts))
        print(f"shared dec {token}={value!r}", flush=True)
        assert is_number_not_string(value, expected), (
            f"{token} must be {expected} on this typed schema; got {value!r}"
        )


def test_shared_explicit_ints_across_typed_schemas():
    public = (
        ("!!int +685230", 685230),
        ("!!int 0b1010", 10),
        ("!!int 0x1A", 26),
    )
    bin_text, bin_value = bin_int_token()
    hex_text, hex_value = hex_int_token()
    print(f"shared runtime !!int {bin_text}={bin_value} {hex_text}={hex_value}", flush=True)
    for opts in _typed_opts():
        for source, expected in public:
            value = require_document(load(source, opts))
            print(f"shared explicit {source}={value!r}", flush=True)
            assert is_number_not_string(value, expected)
        got_bin = require_document(load(f"!!int {bin_text}", opts))
        assert is_number_not_string(got_bin, bin_value)
        got_hex = require_document(load(f"!!int {hex_text}", opts))
        assert is_number_not_string(got_hex, hex_value)


@pytest.mark.parametrize("schema_fn", TYPED_SCHEMA_FNS, ids=["json", "core", "yaml11"])
def test_shared_685230_15_forms_across_typed_schemas(schema_fn):
    opts = schema_fn()
    forms = ("6.8523015e+5", "685.23015e+03", "685230.15")
    values = [require_document(load(form, opts)) for form in forms]
    print(f"shared 685230.15 values={values!r}", flush=True)
    for form, value in zip(forms, values):
        assert is_finite_number(value, 685230.15), (
            f"{form} must be the float 685230.15; got {value!r}"
        )
    assert values[0] == values[1] == values[2]


def test_shared_zero_forms_and_minus_one():
    for token in ("0.", "-0.0"):
        observed = []
        for opts in _typed_opts():
            value = require_document(load(token, opts))
            print(f"shared {token}={value!r}", flush=True)
            assert not isinstance(value, (str, bool)), (
                f"{token} must be a number, not a string; got {value!r}"
            )
            assert is_finite_number(value, 0), (
                f"{token} must be a finite zero on this schema; got {value!r}"
            )
            observed.append(value)
        assert observed[0] == observed[1] == observed[2], (
            f"{token} must construct the same value on JSON, Core, and YAML 1.1; "
            f"got {observed!r}"
        )

    for opts in _typed_opts():
        minus = require_document(load("-1.0", opts))
        print(f"shared -1.0={minus!r}", flush=True)
        assert is_finite_number(minus, -1), (
            f"-1.0 must be the signed float -1; got {minus!r}"
        )


@pytest.mark.parametrize("schema_fn", TYPED_SCHEMA_FNS, ids=["json", "core", "yaml11"])
def test_shared_explicit_float_specials(schema_fn):
    opts = schema_fn()
    pos = require_document(load("!!float .inf", opts))
    print(f"shared !!float .inf={pos!r}", flush=True)
    assert is_pos_inf(pos)
    neg = require_document(load("!!float -.Inf", opts))
    print(f"shared !!float -.Inf={neg!r}", flush=True)
    assert is_neg_inf(neg)
    nan = require_document(load("!!float .NaN", opts))
    print(f"shared !!float .NaN={nan!r}", flush=True)
    assert is_nan_number(nan)
    plus = require_document(load("!!float +12.3", opts))
    print(f"shared !!float +12.3={plus!r}", flush=True)
    assert is_finite_number(plus, 12.3)
    half = require_document(load("!!float .5", opts))
    print(f"shared !!float .5={half!r}", flush=True)
    assert is_finite_number(half, 0.5)


def test_oversized_integer_stays_string():
    token = oversized_decimal_token()
    print(f"oversized digits={len(token)} head={token[:16]!r}", flush=True)
    observed = []
    for opts in _typed_opts():
        value = require_document(load(token, opts))
        print(f"oversized type={type(value).__name__}", flush=True)
        assert is_string_text(value, token), (
            f"an integer that does not fit in a JavaScript number must stay "
            f"the digit text; got {value!r}"
        )
        observed.append(value)
    assert observed[0] == observed[1] == observed[2] == token


# ---------------------------------------------------------------------------
# G. Explicit tags: empty nodes, unresolvable text, implicit decoupling
# ---------------------------------------------------------------------------


def test_empty_explicit_str_seq_map():
    empty_str = require_document(load("!!str"))
    print(f"empty !!str={empty_str!r}", flush=True)
    assert is_string_text(empty_str, "")

    empty_seq = require_sequence(require_document(load("!!seq")))
    print(f"empty !!seq={empty_seq!r}", flush=True)
    assert empty_seq == []

    empty_map = require_plain_mapping(require_document(load("!!map")))
    print(f"empty !!map keys={list(empty_map.keys())!r}", flush=True)
    assert list(empty_map.keys()) == []

    failsafe_str = require_document(load("!!str", with_failsafe_schema()))
    print(f"failsafe empty !!str={failsafe_str!r}", flush=True)
    assert is_string_text(failsafe_str, "")


def test_explicit_seq_on_nonempty_scalar_fails():
    failed = load("!!seq foo")
    error = require_parse_failure(failed)
    print(
        f"!!seq foo ok={failed.ok!r} report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert failed.ok is False, (
        "explicit !!seq on a nonempty scalar must fail and yield no document"
    )

    other = nonempty_seq_scalar()
    print(f"runtime !!seq {other!r}", flush=True)
    runtime = load(f"!!seq {other}")
    runtime_error = require_parse_failure(runtime)
    print(
        f"runtime !!seq ok={runtime.ok!r} "
        f"report={observer_visible_report(runtime_error)!r}",
        flush=True,
    )
    assert runtime.ok is False, (
        f"explicit !!seq on nonempty {other!r} must fail and yield no document"
    )


@pytest.mark.parametrize("schema_fn", TYPED_SCHEMA_FNS, ids=["json", "core", "yaml11"])
def test_unresolvable_explicit_tags_fail_typed_schemas(schema_fn):
    opts = schema_fn()
    for source in ("!!bool garbage", "!!int 1.5", "!!float abc"):
        print(f"unresolvable {source}", flush=True)
        require_parse_failure(load(source, opts))

    bool_word = non_bool_word()
    int_text = non_int_text()
    float_text = non_float_text()
    print(
        f"runtime garbage bool={bool_word!r} int={int_text!r} float={float_text!r}",
        flush=True,
    )
    require_parse_failure(load(f"!!bool {bool_word}", opts))
    require_parse_failure(load(f"!!int {int_text}", opts))
    require_parse_failure(load(f"!!float {float_text}", opts))

    success_int = require_document(load("!!int 0b1010", opts))
    assert is_number_not_string(success_int, 10)
    success_bool = require_document(load("true", opts))
    assert is_bool(success_bool, True)


@pytest.mark.parametrize("schema_fn", TYPED_SCHEMA_FNS, ids=["json", "core", "yaml11"])
def test_empty_explicit_bool_int_float_fail(schema_fn):
    opts = schema_fn()
    for source in ("!!bool", "!!int", "!!float"):
        print(f"empty explicit {source}", flush=True)
        failed = load(source, opts)
        error = require_parse_failure(failed)
        print(
            f"empty {source} ok={failed.ok!r} "
            f"report={observer_visible_report(error)!r}",
            flush=True,
        )
        assert failed.ok is False, (
            f"empty explicit {source} must fail and yield no document"
        )


# ---------------------------------------------------------------------------
# H. Schema selection applies to every document of a multi-document parse
# ---------------------------------------------------------------------------


def test_failsafe_applies_to_every_multi_document():
    docs = require_sequence(
        require_document(load_all("1\n---\ntrue\n", with_failsafe_schema()))
    )
    print(f"failsafe multi={docs!r}", flush=True)
    assert len(docs) == 2
    assert is_string_text(docs[0], "1"), (
        f"Failsafe first document must stay string 1; got {docs[0]!r}"
    )
    assert is_string_text(docs[1], "true"), (
        f"Failsafe second document must stay string true; got {docs[1]!r}"
    )


def test_json_applies_to_every_multi_document():
    docs = require_sequence(
        require_document(load_all("null\n---\nTrue\n", with_json_schema()))
    )
    print(f"json multi={docs!r}", flush=True)
    assert len(docs) == 2
    assert is_js_null(docs[0]), f"JSON first document must be null; got {docs[0]!r}"
    assert is_string_text(docs[1], "True"), (
        f"JSON second document must stay string True; got {docs[1]!r}"
    )


def test_yaml11_applies_to_every_multi_document():
    docs = require_sequence(
        require_document(load_all("yes\n---\n0123\n", with_yaml11_schema()))
    )
    print(f"yaml11 multi={docs!r}", flush=True)
    assert len(docs) == 2
    assert is_bool(docs[0], True), (
        f"YAML 1.1 first document must be boolean true; got {docs[0]!r}"
    )
    assert is_number_not_string(docs[1], 83), (
        f"YAML 1.1 second document must be octal 83; got {docs[1]!r}"
    )
