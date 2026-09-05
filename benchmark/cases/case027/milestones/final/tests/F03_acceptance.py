# feature: F03
"""FP-03: URL Search Params (C++ library and matching C interface)."""

from __future__ import annotations

import pytest

from _helpers import (
    inspect_url,
    run_search_params,
    search_params_probe_has_named_append_success,
    try_search_params_without_linked_library,
    unique_token,
)

BOTH_LANGS = ("c++", "c")

NAMED_THREE = "a=b&c=d&e=f"
NAMED_SORT = "z=b&a=b&z=a&a=a"
KEY_U1F308 = "\U0001f308"
KEY_UFB03 = "\ufb03"
GOOGLE_SEARCH_URL = "https://www.google.com/pathname?query=true"


def _print_snap(label: str, snap, *, language: str) -> None:
    print(
        f"{label} language={language} size={snap.size} "
        f"serial={snap.serialize!r} keys={list(snap.keys)} "
        f"values={list(snap.values)} entries={list(snap.entries)} "
        f"construct_size={snap.construct_size} "
        f"construct_serial={snap.construct_serialize!r}"
    )


def _require_present(snap, key: str, expected: str | None = None):
    assert key in snap.gets, f"lookup for {key!r} was not requested"
    got = snap.gets[key]
    assert got.present, (
        f"get({key!r}) ABSENT; serial={snap.serialize!r} "
        f"stderr={snap.stderr!r}"
    )
    if expected is not None:
        assert got.value == expected, (
            f"get({key!r})={got.value!r} expected {expected!r}; "
            f"serial={snap.serialize!r}"
        )
    return got.value


def _require_absent(snap, key: str) -> None:
    assert key in snap.gets, f"lookup for {key!r} was not requested"
    got = snap.gets[key]
    assert not got.present, (
        f"get({key!r}) PRESENT value={got.value!r}; "
        f"serial={snap.serialize!r} stderr={snap.stderr!r}"
    )
    assert got.value is None


def _require_empty_object(snap, would_be_key: str, *, which: str) -> None:
    assert snap.size == 0, (
        f"{which} size={snap.size} serial={snap.serialize!r} "
        f"stderr={snap.stderr!r}"
    )
    assert snap.serialize == "", (
        f"{which} serial not empty: {snap.serialize!r}"
    )
    _require_absent(snap, would_be_key)
    assert snap.has_keys[would_be_key] is False
    assert snap.get_alls[would_be_key] == ()


def _query_of_length(length: int, key: str, token: str) -> str:
    prefix = f"{key}={token}"
    if length < len(prefix):
        raise ValueError(f"length {length} shorter than {prefix!r}")
    return prefix + ("x" * (length - len(prefix)))


# ---------------------------------------------------------------------------
# A. Construct, append, size, get, get-all, has
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_construct_three_pairs_then_append(language: str) -> None:
    snap = run_search_params(
        NAMED_THREE,
        (("append", "g", "h"),),
        language=language,
        lookup_keys=("a", "c", "e", "g"),
    )
    _print_snap("three-then-append", snap, language=language)
    assert snap.construct_size == 3
    assert snap.size == 4
    assert not snap.serialize.startswith("?")
    _require_present(snap, "a", "b")
    _require_present(snap, "c", "d")
    _require_present(snap, "e", "f")
    _require_present(snap, "g", "h")
    assert snap.entries == (("a", "b"), ("c", "d"), ("e", "f"), ("g", "h"))


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_duplicate_key_preserves_both_get_first(language: str) -> None:
    snap = run_search_params(
        "",
        (("append", "k", "first"), ("append", "k", "second")),
        language=language,
        lookup_keys=("k",),
    )
    _print_snap("dup-key", snap, language=language)
    assert snap.size == 2
    _require_present(snap, "k", "first")
    assert snap.get_alls["k"] == ("first", "second")
    assert snap.has_keys["k"] is True
    assert snap.entries == (("k", "first"), ("k", "second"))


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_append_get_and_get_all_order(language: str) -> None:
    key = unique_token()
    val = unique_token()
    v1 = unique_token()
    v2 = unique_token()
    one = run_search_params(
        NAMED_THREE,
        (("append", key, val),),
        language=language,
        lookup_keys=(key,),
    )
    _print_snap("runtime-append", one, language=language)
    assert one.size == 4
    _require_present(one, key, val)

    two = run_search_params(
        "",
        (("append", key, v1), ("append", key, v2)),
        language=language,
        lookup_keys=(key,),
    )
    _print_snap("runtime-get-all", two, language=language)
    _require_present(two, key, v1)
    assert two.get_alls[key] == (v1, v2)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_has_by_key_and_by_key_value(language: str) -> None:
    snap = run_search_params(
        "key1=value1&key1=value2",
        language=language,
        lookup_keys=("key1", "missing"),
        lookup_pairs=(
            ("key1", "value1"),
            ("key1", "value2"),
            ("key1", "other"),
            ("missing", "value1"),
        ),
    )
    _print_snap("has-named", snap, language=language)
    assert snap.has_keys["key1"] is True
    assert snap.has_keys["missing"] is False
    assert snap.has_pairs[("key1", "value1")] is True
    assert snap.has_pairs[("key1", "value2")] is True
    assert snap.has_pairs[("key1", "other")] is False
    assert snap.has_pairs[("missing", "value1")] is False
    assert snap.get_alls["missing"] == ()


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_has_by_key_and_value(language: str) -> None:
    key = unique_token()
    first = unique_token()
    second = unique_token()
    third = unique_token()
    snap = run_search_params(
        "",
        (("append", key, first), ("append", key, second)),
        language=language,
        lookup_keys=(key,),
        lookup_pairs=((key, first), (key, third)),
    )
    _print_snap("runtime-has", snap, language=language)
    assert snap.has_keys[key] is True
    assert snap.has_pairs[(key, first)] is True
    assert snap.has_pairs[(key, third)] is False


# ---------------------------------------------------------------------------
# B. Set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_set_collapses_duplicate_key(language: str) -> None:
    snap = run_search_params(
        "key1=value1&key1=value2",
        (("set", "key1", "hello"),),
        language=language,
        lookup_keys=("key1",),
    )
    _print_snap("set-collapse", snap, language=language)
    assert snap.serialize == "key1=hello"
    assert snap.size == 1
    _require_present(snap, "key1", "hello")
    assert snap.get_alls["key1"] == ("hello",)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_set_preserves_later_other_key(language: str) -> None:
    snap = run_search_params(
        "key1=value1&key1=value2&key2=value1",
        (("set", "key1", "value3"),),
        language=language,
        lookup_keys=("key1", "key2"),
    )
    _print_snap("set-later-other", snap, language=language)
    assert snap.serialize == "key1=value3&key2=value1"
    _require_present(snap, "key1", "value3")
    _require_present(snap, "key2", "value1")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_set_keeps_first_pair_position(language: str) -> None:
    front = run_search_params(
        "key2=keep&key1=value1&key1=value2",
        (("set", "key1", "hello"),),
        language=language,
        lookup_keys=("key1", "key2"),
    )
    _print_snap("set-front-neighbor", front, language=language)
    assert [k for k, _ in front.entries] == ["key2", "key1"]
    assert front.entries[1] == ("key1", "hello")
    assert sum(1 for k, _ in front.entries if k == "key1") == 1
    _require_present(front, "key2", "keep")

    mid = run_search_params(
        "key1=value1&key2=mid&key1=value2",
        (("set", "key1", "hello"),),
        language=language,
        lookup_keys=("key1", "key2"),
    )
    _print_snap("set-sandwich", mid, language=language)
    assert [k for k, _ in mid.entries] == ["key1", "key2"]
    assert mid.entries[0] == ("key1", "hello")
    assert mid.entries[1] == ("key2", "mid")
    assert sum(1 for k, _ in mid.entries if k == "key1") == 1


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_set_collapses_and_keeps_neighbor(language: str) -> None:
    key = unique_token()
    neighbor = unique_token()
    first = unique_token()
    second = unique_token()
    neigh_val = unique_token()
    new_val = unique_token()
    init = f"{key}={first}&{neighbor}={neigh_val}&{key}={second}"
    set_snap = run_search_params(
        init,
        (("set", key, new_val),),
        language=language,
        lookup_keys=(key, neighbor),
    )
    append_snap = run_search_params(
        init,
        (("append", key, new_val),),
        language=language,
        lookup_keys=(key, neighbor),
    )
    _print_snap("runtime-set", set_snap, language=language)
    _print_snap("runtime-append-contrast", append_snap, language=language)
    assert set_snap.get_alls[key] == (new_val,)
    _require_present(set_snap, neighbor, neigh_val)
    set_keys = [k for k, _ in set_snap.entries]
    assert set_keys.index(key) < set_keys.index(neighbor)
    assert append_snap.size > set_snap.size
    assert append_snap.get_alls[key] == (first, second, new_val)


# ---------------------------------------------------------------------------
# C. Remove
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_remove_by_key_then_by_key_and_value(language: str) -> None:
    after_key = run_search_params(
        "key1=value1&key1=value2&key2=value2",
        (("remove", "key2"),),
        language=language,
        lookup_keys=("key1", "key2"),
    )
    _print_snap("remove-by-key", after_key, language=language)
    assert after_key.serialize == "key1=value1&key1=value2"
    assert after_key.has_keys["key2"] is False
    assert after_key.get_alls["key1"] == ("value1", "value2")

    after_val = run_search_params(
        "key1=value1&key1=value2&key2=value2",
        (("remove", "key2"), ("remove-value", "key1", "value2")),
        language=language,
        lookup_keys=("key1",),
    )
    _print_snap("remove-by-value", after_val, language=language)
    assert after_val.serialize == "key1=value1"
    _require_present(after_val, "key1", "value1")
    assert after_val.get_alls["key1"] == ("value1",)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_remove_by_key_deletes_every_pair(language: str) -> None:
    other = unique_token()
    other_val = unique_token()
    snap = run_search_params(
        f"dup=one&{other}={other_val}&dup=two",
        (("remove", "dup"),),
        language=language,
        lookup_keys=("dup", other),
    )
    _print_snap("remove-every-pair", snap, language=language)
    assert snap.has_keys["dup"] is False
    assert snap.get_alls["dup"] == ()
    _require_absent(snap, "dup")
    _require_present(snap, other, other_val)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_remove_by_value_leaves_other_duplicate(language: str) -> None:
    key = unique_token()
    token_a = unique_token()
    token_b = unique_token()
    snap = run_search_params(
        "",
        (
            ("append", key, token_a),
            ("append", key, token_b),
            ("remove-value", key, token_a),
        ),
        language=language,
        lookup_keys=(key,),
        lookup_pairs=((key, token_a), (key, token_b)),
    )
    _print_snap("runtime-remove-value", snap, language=language)
    assert snap.get_alls[key] == (token_b,)
    assert snap.has_pairs[(key, token_a)] is False
    assert snap.has_pairs[(key, token_b)] is True


# ---------------------------------------------------------------------------
# D. Sort
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_sort_stable_ascii_named_order(language: str) -> None:
    before = run_search_params(NAMED_SORT, language=language)
    after = run_search_params(
        NAMED_SORT, (("sort",),), language=language
    )
    _print_snap("sort-before", before, language=language)
    _print_snap("sort-after", after, language=language)
    assert before.keys == ("z", "a", "z", "a")
    assert before.values == ("b", "b", "a", "a")
    assert after.keys == ("a", "a", "z", "z")
    assert after.values == ("b", "a", "b", "a")
    assert after.entries == (("a", "b"), ("a", "a"), ("z", "b"), ("z", "a"))
    assert before.entries != after.entries


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_sort_utf16_named_code_points(language: str) -> None:
    rainbow_first = f"{KEY_U1F308}=x&{KEY_UFB03}=y"
    ligature_first = f"{KEY_UFB03}=y&{KEY_U1F308}=x"
    for init in (rainbow_first, ligature_first):
        snap = run_search_params(
            init, (("sort",),), language=language
        )
        _print_snap(f"utf16-sort init={init!r}", snap, language=language)
        assert snap.keys[0] == KEY_U1F308, (
            f"U+1F308 must sort before U+FB03; keys={list(snap.keys)}"
        )
        assert snap.keys[1] == KEY_UFB03
        assert snap.keys == (KEY_U1F308, KEY_UFB03)


# ---------------------------------------------------------------------------
# E. Serialize
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_serialize_no_leading_question_mark(language: str) -> None:
    snap = run_search_params(
        "?a=b", language=language, lookup_keys=("a", "?a")
    )
    _print_snap("no-leading-q", snap, language=language)
    assert snap.serialize == "a=b"
    assert not snap.serialize.startswith("?")
    _require_present(snap, "a", "b")
    _require_absent(snap, "?a")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_serialize_space_as_plus_get_keeps_space(language: str) -> None:
    snap = run_search_params(
        "",
        (("append", "a", "b c"),),
        language=language,
        lookup_keys=("a",),
    )
    _print_snap("space-plus", snap, language=language)
    assert snap.serialize == "a=b+c"
    _require_present(snap, "a", "b c")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_serialize_plus_percent2b(language: str) -> None:
    snap = run_search_params(
        "",
        (("append", "a", "b+c"),),
        language=language,
        lookup_keys=("a",),
    )
    _print_snap("plus-percent", snap, language=language)
    assert "%2B" in snap.serialize
    _require_present(snap, "a", "b+c")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_serialize_ampersand_in_key_and_value(language: str) -> None:
    key_amp = run_search_params(
        "",
        (("append", "a&b", "c"),),
        language=language,
        lookup_keys=("a&b",),
    )
    val_amp = run_search_params(
        "",
        (("append", "a", "b&c"),),
        language=language,
        lookup_keys=("a",),
    )
    _print_snap("amp-key", key_amp, language=language)
    _print_snap("amp-val", val_amp, language=language)
    assert "%26" in key_amp.serialize
    assert "%26" in val_amp.serialize
    _require_present(key_amp, "a&b", "c")
    _require_present(val_amp, "a", "b&c")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_serialize_empty_value_and_empty_key(language: str) -> None:
    empty_val = run_search_params(
        "",
        (("append", "a", ""),),
        language=language,
        lookup_keys=("a",),
    )
    empty_key = run_search_params(
        "",
        (("append", "a", ""), ("append", "", ""), ("append", "", "b")),
        language=language,
        lookup_keys=("a", ""),
    )
    _print_snap("empty-value", empty_val, language=language)
    _print_snap("empty-key", empty_key, language=language)
    assert "a=" in empty_val.serialize
    _require_present(empty_val, "a", "")
    assert empty_key.serialize == "a=&=&=b"
    _require_present(empty_key, "a", "")
    _require_present(empty_key, "", "")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_non_ascii_value_round_trip(language: str) -> None:
    snap = run_search_params(
        "",
        (("append", "a", "é"),),
        language=language,
        lookup_keys=("a",),
    )
    _print_snap("e-acute", snap, language=language)
    assert "%C3%A9" in snap.serialize
    _require_present(snap, "a", "é")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_space_and_plus_in_value(language: str) -> None:
    left = unique_token()
    right = unique_token()
    space_val = f"{left} {right}"
    plus_tok = unique_token()
    plus_val = f"{plus_tok}+z"
    space = run_search_params(
        "",
        (("append", "a", space_val),),
        language=language,
        lookup_keys=("a",),
    )
    plus = run_search_params(
        "",
        (("append", "a", plus_val),),
        language=language,
        lookup_keys=("a",),
    )
    _print_snap("runtime-space", space, language=language)
    _print_snap("runtime-plus", plus, language=language)
    assert left in space.serialize and right in space.serialize
    assert "+" in space.serialize
    assert "%20" not in space.serialize
    _require_present(space, "a", space_val)
    assert "%2B" in plus.serialize
    assert plus_tok in plus.serialize
    _require_present(plus, "a", plus_val)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_runtime_ampersand_and_e_acute(language: str) -> None:
    tok = unique_token()
    key_amp = f"{tok}&"
    val_amp = f"{tok}&"
    left = unique_token()
    right = unique_token()
    e_val = f"{left}é{right}"
    as_key = run_search_params(
        "",
        (("append", key_amp, "v"),),
        language=language,
        lookup_keys=(key_amp,),
    )
    as_val = run_search_params(
        "",
        (("append", "k", val_amp),),
        language=language,
        lookup_keys=("k",),
    )
    e_snap = run_search_params(
        "",
        (("append", "k", e_val),),
        language=language,
        lookup_keys=("k",),
    )
    _print_snap("runtime-amp-key", as_key, language=language)
    _print_snap("runtime-amp-val", as_val, language=language)
    _print_snap("runtime-e-acute", e_snap, language=language)
    assert "%26" in as_key.serialize and tok in as_key.serialize
    _require_present(as_key, key_amp, "v")
    assert "&" in key_amp
    assert "%26" in as_val.serialize and tok in as_val.serialize
    _require_present(as_val, "k", val_amp)
    assert "&" in as_val.gets["k"].value
    assert "%C3%A9" in e_snap.serialize
    assert left in e_snap.serialize and right in e_snap.serialize
    _require_present(e_snap, "k", e_val)


# ---------------------------------------------------------------------------
# F. Iterators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_iterators_walk_current_list_in_order(language: str) -> None:
    snap = run_search_params(
        NAMED_THREE,
        (("append", "g", "h"),),
        language=language,
    )
    _print_snap("iter-order", snap, language=language)
    assert snap.keys == ("a", "c", "e", "g")
    assert snap.values == ("b", "d", "f", "h")
    assert snap.entries == (("a", "b"), ("c", "d"), ("e", "f"), ("g", "h"))
    assert len(snap.keys) == snap.size


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_iterators_repeat_duplicate_keys(language: str) -> None:
    key = unique_token()
    v1 = unique_token()
    v2 = unique_token()
    snap = run_search_params(
        NAMED_THREE,
        (("append", key, v1), ("append", key, v2)),
        language=language,
        lookup_keys=(key,),
    )
    collapsed = run_search_params(
        NAMED_THREE,
        (("append", key, v1), ("append", key, v2), ("set", key, v1)),
        language=language,
        lookup_keys=(key,),
    )
    _print_snap("iter-dup", snap, language=language)
    _print_snap("iter-after-set", collapsed, language=language)
    assert snap.keys.count(key) == len(snap.get_alls[key])
    assert snap.keys.count(key) == 2
    assert snap.get_alls[key] == (v1, v2)
    assert snap.values[-2:] == (v1, v2)
    assert snap.entries[-2:] == ((key, v1), (key, v2))
    assert collapsed.keys.count(key) == 1
    assert collapsed.get_alls[key] == (v1,)


# ---------------------------------------------------------------------------
# G. Reset, length cap, missing vs empty, no '=', leading '?'
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_reset_replaces_list(language: str) -> None:
    named = run_search_params(
        "a=b",
        (("reset", "c=d&e=f"),),
        language=language,
        lookup_keys=("a", "c"),
    )
    _print_snap("reset-named", named, language=language)
    _require_present(named, "c", "d")
    _require_absent(named, "a")
    assert named.size == 2

    tok_key = unique_token()
    tok_val = unique_token()
    runtime = run_search_params(
        "old=gone",
        (("reset", f"{tok_key}={tok_val}"),),
        language=language,
        lookup_keys=("old", tok_key),
    )
    _print_snap("reset-runtime", runtime, language=language)
    _require_present(runtime, tok_key, tok_val)
    _require_absent(runtime, "old")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_overlength_construct_leaves_empty(language: str) -> None:
    key = unique_token()
    token = unique_token()
    query = _query_of_length(40, key, token)
    assert "?" not in query
    live_cap = len(query) + 8
    over_cap = len(query) - 5
    assert over_cap < len(query) < live_cap

    live = run_search_params(
        query,
        language=language,
        max_length=live_cap,
        lookup_keys=(key,),
    )
    empty = run_search_params(
        query,
        language=language,
        max_length=over_cap,
        lookup_keys=(key,),
    )
    _print_snap("overlength-live", live, language=language)
    _print_snap("overlength-empty", empty, language=language)
    assert live.size > 0
    _require_present(live, key, token + ("x" * (40 - len(f"{key}={token}"))))
    _require_empty_object(empty, key, which="over-length construct")

    eq_cap = 36
    eq_query = _query_of_length(eq_cap, key, token)
    plus_query = _query_of_length(eq_cap + 1, key, token)
    at_cap = run_search_params(
        eq_query,
        language=language,
        max_length=eq_cap,
        lookup_keys=(key,),
    )
    over_by_one = run_search_params(
        plus_query,
        language=language,
        max_length=eq_cap,
        lookup_keys=(key,),
    )
    _print_snap("eq-cap", at_cap, language=language)
    _print_snap("cap-plus-one", over_by_one, language=language)
    assert at_cap.size > 0
    _require_present(at_cap, key)
    _require_empty_object(over_by_one, key, which="cap+1 construct")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_overlength_reset_clears_existing(language: str) -> None:
    key = "k"
    token = unique_token()
    short = f"{key}={token}"
    cap = len(short) + 4
    long_q = _query_of_length(cap + 8, "z", unique_token())
    assert "?" not in long_q
    snap = run_search_params(
        short,
        (("reset", long_q),),
        language=language,
        max_length=cap,
        lookup_keys=(key,),
    )
    _print_snap("overlength-reset", snap, language=language)
    assert snap.construct_size > 0
    _require_present_construct = snap.construct_gets[key]
    assert _require_present_construct.present
    _require_empty_object(snap, key, which="over-length reset")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_append_set_not_length_capped(language: str) -> None:
    old_key = "k"
    old_tok = unique_token()
    prefix = f"{old_key}={old_tok}"
    cap = len(prefix)
    long_init = _query_of_length(cap + 10, old_key, old_tok)
    new_key = unique_token()
    new_val = unique_token() * 4
    set_val = unique_token() * 4
    empty_construct = run_search_params(
        long_init,
        language=language,
        max_length=cap,
        lookup_keys=(old_key,),
    )
    appended = run_search_params(
        long_init,
        (("append", new_key, new_val),),
        language=language,
        max_length=cap,
        lookup_keys=(old_key, new_key),
    )
    mutated = run_search_params(
        long_init,
        (("append", new_key, new_val), ("set", new_key, set_val)),
        language=language,
        max_length=cap,
        lookup_keys=(old_key, new_key),
    )
    _print_snap("cap-construct-empty", empty_construct, language=language)
    _print_snap("cap-append", appended, language=language)
    _print_snap("cap-append-set", mutated, language=language)
    _require_empty_object(
        empty_construct, old_key, which="same-cap over-length construct"
    )
    assert appended.construct_size == 0
    assert not appended.construct_gets[old_key].present
    assert appended.size == 1
    _require_present(appended, new_key, new_val)
    _require_absent(appended, old_key)
    assert mutated.construct_size == 0
    assert not mutated.construct_gets[old_key].present
    assert mutated.size == 1
    _require_present(mutated, new_key, set_val)
    _require_absent(mutated, old_key)


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_missing_key_distinguishable_from_empty_value(language: str) -> None:
    snap = run_search_params(
        "",
        (("append", "k", ""),),
        language=language,
        lookup_keys=("k", "missing"),
    )
    _print_snap("absent-vs-empty", snap, language=language)
    present = snap.gets["k"]
    missing = snap.gets["missing"]
    assert present.present
    assert present.value == ""
    assert not missing.present
    assert missing.value is None
    assert present != missing
    assert snap.has_keys["k"] is True
    assert snap.has_keys["missing"] is False
    assert snap.get_alls["missing"] == ()


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_key_without_equals_has_empty_value(language: str) -> None:
    named = run_search_params(
        "bbb&bb",
        language=language,
        lookup_keys=("bbb", "bb"),
    )
    t1 = unique_token()
    t2 = unique_token()
    runtime = run_search_params(
        f"{t1}&{t2}",
        language=language,
        lookup_keys=(t1, t2),
    )
    _print_snap("no-eq-named", named, language=language)
    _print_snap("no-eq-runtime", runtime, language=language)
    _require_present(named, "bbb", "")
    _require_present(named, "bb", "")
    _require_present(runtime, t1, "")
    _require_present(runtime, t2, "")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_leading_question_mark_not_part_of_key(language: str) -> None:
    snap = run_search_params(
        "?a=b",
        language=language,
        lookup_keys=("a", "?a"),
    )
    _print_snap("leading-q-key", snap, language=language)
    _require_present(snap, "a", "b")
    _require_absent(snap, "?a")
    assert "?" not in snap.serialize


# ---------------------------------------------------------------------------
# H. Feed a URL search component
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_construct_from_url_search_component(language: str) -> None:
    inspected = inspect_url(GOOGLE_SEARCH_URL, language=language)
    print(
        f"url-search language={language} search={inspected.search!r}"
    )
    snap = run_search_params(
        inspected.search,
        language=language,
        lookup_keys=("query", "?query"),
    )
    _print_snap("from-url-search", snap, language=language)
    _require_present(snap, "query", "true")
    _require_absent(snap, "?query")


@pytest.mark.parametrize("language", BOTH_LANGS)
def test_construct_from_url_search_runtime_token(language: str) -> None:
    key = unique_token()
    val = unique_token()
    url = f"https://www.example.com/p?{key}={val}"
    inspected = inspect_url(url, language=language)
    print(
        f"runtime-url-search language={language} search={inspected.search!r} "
        f"key={key} val={val}"
    )
    snap = run_search_params(
        inspected.search,
        language=language,
        lookup_keys=(key,),
    )
    _print_snap("from-url-search-token", snap, language=language)
    _require_present(snap, key, val)


# ---------------------------------------------------------------------------
# I. Negative control (C++ only)
# ---------------------------------------------------------------------------


def test_search_params_fail_when_library_absent_from_link_path() -> None:
    baseline = run_search_params(
        NAMED_THREE,
        (("append", "g", "h"),),
        lookup_keys=("g",),
    )
    _print_snap("unlink-baseline", baseline, language="c++")
    assert baseline.size == 4
    _require_present(baseline, "g", "h")
    kind, result = try_search_params_without_linked_library()
    print(f"absent-library kind={kind}")
    assert result is not None
    if kind == "link_failed":
        assert result.returncode != 0
        print(f"link stderr={result.stderr_text[:800]!r}")
        return
    produced = search_params_probe_has_named_append_success(result)
    assert not produced, (
        "search-params without the recipe library still produced "
        "get g==h and size 4"
    )
