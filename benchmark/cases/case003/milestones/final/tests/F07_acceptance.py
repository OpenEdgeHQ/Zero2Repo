# feature: F07
"""Resource limits for untrusted input (FP-07).

Assertions stay at the PRD's precision: default nesting is finite
(demonstrated by 100000 opening brackets failing under the omitted
knob as a classified parse failure, not an uncaught host overflow),
aliases not counted as depth,
ten nested flow sequences at 20 vs 5, default unlimited aliases,
per-document alias budget, default merge budget 10000, per-call
merge-key work, disabled merge budget, and a classified parse failure
(process ended) rather than an uncaught host crash. Knob spellings,
failure wording, exception classes, and overflow payload phrases are
not pinned.
"""

from __future__ import annotations

import json
from typing import Any

from _harness import load, load_all
from _helpers import (
    core_int_token,
    double_merge_of_same_mapping,
    is_number_not_string,
    mapping_get,
    mapping_key_count,
    merge_chain_yaml,
    merge_parse_options,
    nested_empty_block_sequences,
    nested_empty_flow_mappings,
    nested_empty_flow_sequences,
    nested_mapping_depth,
    nested_sequence_depth,
    nested_sequences_under_mapping,
    observer_visible_report,
    one_key_merges_document,
    opening_brackets,
    recursive_self_alias_sequence,
    require_document,
    require_no_usable_prefix,
    require_parse_failure,
    require_parse_failure_not_host_overflow,
    require_plain_mapping,
    require_sequence,
    same_identity,
    shallow_alias_sequence_document,
    sibling_empty_flow_sequences,
    single_alias_document,
    single_merge_of_mapping,
    two_alias_document,
    two_alias_sequence_document,
    two_docs_merge_two_keys_each,
    two_docs_one_alias_each,
    unique_token,
    with_alias_budget,
    with_merge_budget,
    with_merge_budget_disabled,
    with_merge_on_core,
    with_nesting_limit,
    with_unlimited_alias_budget,
    with_yaml11_schema,
)

ANSWER_42 = "answer: 42"
TEN_NESTED = nested_empty_flow_sequences(10)
TWO_ALIAS_DOC = two_alias_document("base", "a", 1, ["copy", "other"])
THREE_MERGES = one_key_merges_document([("one", 1), ("two", 2), ("three", 3)])
TWO_DOCS_ONE_ALIAS = two_docs_one_alias_each(
    "left", "a", 1, "leftcopy", "right", "b", 2, "rightcopy"
)
TWO_DOCS_TWO_KEYS = two_docs_merge_two_keys_each(
    [("a", 1), ("b", 2)],
    [("c", 3), ("d", 4)],
)

_LARGE_TIMEOUT = 180.0


def _runtime_mid_depth() -> int:
    depth = 6 + (core_int_token() % 13)
    if depth == 10:
        depth = 12
    return depth


def _assert_ten_nested(value: Any) -> None:
    depth = nested_sequence_depth(value)
    want = json.loads(TEN_NESTED)
    print(f"ten-nested depth={depth} matches_json={value == want}", flush=True)
    assert depth == 10, f"ten nested sequences must have depth 10, got {depth}"
    assert value == want, f"ten nested sequences must match JSON structure; got {value!r}"


def _assert_two_alias_identity(doc: Any, anchor: str, alias_names: list[str]) -> None:
    mapping = require_plain_mapping(doc)
    base = mapping_get(mapping, anchor)
    for name in alias_names:
        alias = mapping_get(mapping, name)
        same = same_identity(alias, base)
        print(f"alias {name!r} same_as_anchor={same}", flush=True)
        assert same, f"alias {name!r} must be the same object as {anchor!r}"


def _assert_merged_keys(doc: Any, pairs: list[tuple[str, int]]) -> None:
    mapping = require_plain_mapping(doc)
    count = mapping_key_count(mapping)
    print(f"merged keys={count} expected={len(pairs)}", flush=True)
    assert count == len(pairs), (
        f"merged mapping must have {len(pairs)} keys, got {count}"
    )
    for key, want in pairs:
        got = mapping_get(mapping, key)
        assert is_number_not_string(got, want), (
            f"merged {key!r} must be {want}, got {got!r}"
        )


def _assert_docs_len(result: Any, length: int) -> list:
    docs = require_sequence(require_document(result))
    print(f"multidoc len={len(docs)} expected={length}", flush=True)
    assert len(docs) == length, (
        f"multi-document list must have length {length}, got {len(docs)}"
    )
    return docs


# ---------------------------------------------------------------------------
# A. Collection nesting depth
# ---------------------------------------------------------------------------


def test_ten_nested_flow_sequences_ok_at_20_fail_at_5():
    ok = require_document(load(TEN_NESTED, with_nesting_limit(20)))
    _assert_ten_nested(ok)
    require_parse_failure(load(TEN_NESTED, with_nesting_limit(5)))


def test_ten_nested_on_multi_document_entry():
    docs = _assert_docs_len(load_all(TEN_NESTED, with_nesting_limit(20)), 1)
    _assert_ten_nested(docs[0])
    require_no_usable_prefix(load_all(TEN_NESTED, with_nesting_limit(5)))


def test_runtime_nested_sequences_ok_at_20_fail_at_5():
    depth = _runtime_mid_depth()
    source = nested_empty_flow_sequences(depth)
    print(f"runtime nest depth={depth}", flush=True)
    value = require_document(load(source, with_nesting_limit(20)))
    got = nested_sequence_depth(value)
    assert got == depth, f"expected depth {depth}, got {got}"
    assert value == json.loads(source)
    require_parse_failure(load(source, with_nesting_limit(5)))


def test_runtime_nested_mappings_ok_at_20_fail_at_5():
    depth = _runtime_mid_depth()
    source = nested_empty_flow_mappings(depth)
    print(f"runtime mapping nest depth={depth}", flush=True)
    value = require_document(load(source, with_nesting_limit(20)))
    got = nested_mapping_depth(value)
    assert got == depth, f"expected mapping depth {depth}, got {got}"
    require_parse_failure(load(source, with_nesting_limit(5)))


def test_shallow_wide_ok_at_5_against_ten_deep_fail():
    width = 6 + (core_int_token() % 5)
    shallow = sibling_empty_flow_sequences(width)
    print(f"shallow siblings={width}", flush=True)
    require_parse_failure(load(TEN_NESTED, with_nesting_limit(5)))
    value = require_document(load(shallow, with_nesting_limit(5)))
    seq = require_sequence(value)
    print(f"shallow len={len(seq)}", flush=True)
    assert len(seq) == width
    for item in seq:
        assert require_sequence(item) == []


def test_ten_nested_under_mapping_ok_at_20_fail_at_5():
    key = unique_token()
    source = nested_sequences_under_mapping(key, 10)
    print(f"under-mapping key={key!r}", flush=True)
    doc = require_document(load(source, with_nesting_limit(20)))
    _assert_ten_nested(mapping_get(doc, key))
    require_parse_failure(load(source, with_nesting_limit(5)))


def test_default_nesting_allows_100_rejects_101():
    source = opening_brackets(100000)
    print(
        f"default omitted-knob hostile brackets chars={len(source)}",
        flush=True,
    )
    result = load(source, timeout=_LARGE_TIMEOUT)
    error = require_parse_failure_not_host_overflow(result)
    print(
        f"default hostile ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_default_nesting_allows_100_rejects_101_mappings():
    source = nested_empty_flow_mappings(10)
    value = require_document(load(source, with_nesting_limit(20)))
    got = nested_mapping_depth(value)
    print(f"ten mapping nest at limit 20 depth={got}", flush=True)
    assert got == 10, f"ten nested mappings must have depth 10, got {got}"
    require_parse_failure(load(source, with_nesting_limit(5)))


def test_default_nesting_on_multi_document_entry():
    source = opening_brackets(100000)
    print(
        f"default multidoc hostile brackets chars={len(source)}",
        flush=True,
    )
    result = load_all(source, timeout=_LARGE_TIMEOUT)
    error = require_parse_failure_not_host_overflow(result)
    require_no_usable_prefix(result)
    print(
        f"default multidoc hostile ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_default_nesting_rejects_101_block_sequences():
    source = nested_empty_block_sequences(10)
    ten = require_document(load(source, with_nesting_limit(20)))
    depth = nested_sequence_depth(ten)
    print(f"ten block nest at limit 20 depth={depth}", flush=True)
    assert depth == 10, f"ten nested block sequences must have depth 10, got {depth}"
    require_parse_failure(load(source, with_nesting_limit(5)))


def test_ten_nested_succeeds_under_default():
    _assert_ten_nested(require_document(load(TEN_NESTED, with_nesting_limit(20))))


def test_hundred_thousand_brackets_fail_as_parse_not_overflow():
    source = opening_brackets(100000)
    print(f"hostile brackets chars={len(source)}", flush=True)
    result = load(source, timeout=_LARGE_TIMEOUT)
    error = require_parse_failure_not_host_overflow(result)
    print(
        f"hostile brackets ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_aliases_do_not_count_toward_nesting():
    require_parse_failure(load(TEN_NESTED, with_nesting_limit(5)))
    anchor = unique_token()
    source = shallow_alias_sequence_document(anchor, 10)
    print(f"ten-alias shallow anchor={anchor!r}", flush=True)
    seq = require_sequence(require_document(load(source, with_nesting_limit(5))))
    assert len(seq) == 2
    empty = require_sequence(seq[0])
    aliases = require_sequence(seq[1])
    assert empty == []
    assert len(aliases) == 10
    for item in aliases:
        assert same_identity(item, empty)


def test_recursive_alias_ok_under_tight_nesting():
    require_parse_failure(load(TEN_NESTED, with_nesting_limit(5)))
    anchor = unique_token()
    source = recursive_self_alias_sequence(anchor)
    print(f"recursive nest-tight anchor={anchor!r}", flush=True)
    seq = require_sequence(require_document(load(source, with_nesting_limit(5))))
    assert len(seq) == 1
    assert same_identity(seq[0], seq)


def test_nesting_limit_cross_yields_no_multidoc_prefix():
    key = unique_token()
    number = core_int_token()
    stream = f"{key}: {number}\n---\n{TEN_NESTED}"
    print(f"nest cross first={key!r}", flush=True)
    docs = _assert_docs_len(load_all(stream, with_nesting_limit(20)), 2)
    assert is_number_not_string(mapping_get(docs[0], key), number)
    _assert_ten_nested(docs[1])
    require_no_usable_prefix(load_all(stream, with_nesting_limit(5)))


def test_nesting_limit_does_not_change_core_types():
    doc = require_document(load(ANSWER_42, with_nesting_limit(20)))
    answer = mapping_get(doc, "answer")
    print(f"answer={answer!r}", flush=True)
    assert is_number_not_string(answer, 42)


# ---------------------------------------------------------------------------
# B. Alias budget (per document, default unlimited)
# ---------------------------------------------------------------------------


def test_two_aliases_ok_at_2_fail_at_1():
    doc = require_document(load(TWO_ALIAS_DOC, with_alias_budget(2)))
    _assert_two_alias_identity(doc, "base", ["copy", "other"])
    require_parse_failure(load(TWO_ALIAS_DOC, with_alias_budget(1)))


def test_two_aliases_ok_under_default():
    doc = require_document(load(TWO_ALIAS_DOC))
    _assert_two_alias_identity(doc, "base", ["copy", "other"])


def test_alias_budget_zero_rejects_two_alias_document():
    live = load(TWO_ALIAS_DOC, with_alias_budget(2))
    doc = require_document(live)
    _assert_two_alias_identity(doc, "base", ["copy", "other"])
    failed = load(TWO_ALIAS_DOC, with_alias_budget(0))
    error = require_parse_failure(failed)
    print(
        f"alias-budget-0 live_ok={live.ok!r} failed_ok={failed.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert live.ok is True
    assert failed.ok is False


def test_alias_budget_zero_rejects_single_alias():
    anchor = unique_token()
    key = unique_token()
    alias = unique_token()
    number = core_int_token()
    source = single_alias_document(anchor, key, number, alias)
    print(f"single alias source={source!r}", flush=True)
    doc = require_document(load(source))
    _assert_two_alias_identity(doc, anchor, [alias])
    require_parse_failure(load(source, with_alias_budget(0)))


def test_two_aliases_on_multi_document_entry():
    docs = _assert_docs_len(load_all(TWO_ALIAS_DOC, with_alias_budget(2)), 1)
    _assert_two_alias_identity(docs[0], "base", ["copy", "other"])
    require_no_usable_prefix(load_all(TWO_ALIAS_DOC, with_alias_budget(1)))


def test_two_aliases_default_on_multi_document_entry():
    docs = _assert_docs_len(load_all(TWO_ALIAS_DOC), 1)
    _assert_two_alias_identity(docs[0], "base", ["copy", "other"])


def test_explicit_unlimited_alias_budget():
    require_parse_failure(load(TWO_ALIAS_DOC, with_alias_budget(1)))
    doc = require_document(load(TWO_ALIAS_DOC, with_unlimited_alias_budget()))
    _assert_two_alias_identity(doc, "base", ["copy", "other"])


def test_runtime_many_aliases_unlimited():
    count = 10001 + (core_int_token() % 17)
    anchor = unique_token()
    key = unique_token()
    number = core_int_token()
    names = [f"n{index}" for index in range(count)]
    source = two_alias_document(anchor, key, number, names)
    print(f"many aliases k={count}", flush=True)
    default_doc = require_document(load(source, timeout=_LARGE_TIMEOUT))
    assert mapping_key_count(default_doc) == count + 1
    _assert_two_alias_identity(default_doc, anchor, names[:2])
    assert same_identity(
        mapping_get(default_doc, names[-1]), mapping_get(default_doc, anchor)
    )
    unlimited = require_document(
        load(source, with_unlimited_alias_budget(), timeout=_LARGE_TIMEOUT)
    )
    _assert_two_alias_identity(unlimited, anchor, names[:2])
    require_parse_failure(load(source, with_alias_budget(2), timeout=_LARGE_TIMEOUT))


def test_two_alias_sequence_ok_at_2_fail_at_1_and_0():
    anchor = unique_token()
    key = unique_token()
    number = core_int_token()
    source = two_alias_sequence_document(anchor, key, number)
    print(f"seq two-alias source={source!r}", flush=True)
    seq = require_sequence(require_document(load(source, with_alias_budget(2))))
    assert len(seq) == 2
    base = require_plain_mapping(seq[0])
    aliases = require_sequence(seq[1])
    assert len(aliases) == 2
    assert same_identity(aliases[0], base)
    assert same_identity(aliases[1], base)
    require_parse_failure(load(source, with_alias_budget(1)))
    require_parse_failure(load(source, with_alias_budget(0)))


def test_recursive_alias_rejected_at_budget_zero():
    anchor = unique_token()
    source = recursive_self_alias_sequence(anchor)
    print(f"recursive budget-zero anchor={anchor!r}", flush=True)
    seq = require_sequence(require_document(load(source)))
    assert len(seq) == 1
    assert same_identity(seq[0], seq)
    require_parse_failure(load(source, with_alias_budget(0)))


def test_two_docs_one_alias_each_ok_at_1():
    docs = _assert_docs_len(load_all(TWO_DOCS_ONE_ALIAS, with_alias_budget(1)), 2)
    _assert_two_alias_identity(docs[0], "left", ["leftcopy"])
    _assert_two_alias_identity(docs[1], "right", ["rightcopy"])
    require_no_usable_prefix(load_all(TWO_DOCS_ONE_ALIAS, with_alias_budget(0)))


def test_runtime_two_docs_one_alias_each():
    first_anchor, first_key, first_alias = (
        unique_token(),
        unique_token(),
        unique_token(),
    )
    second_anchor, second_key, second_alias = (
        unique_token(),
        unique_token(),
        unique_token(),
    )
    first_n, second_n = core_int_token(), core_int_token()
    source = two_docs_one_alias_each(
        first_anchor,
        first_key,
        first_n,
        first_alias,
        second_anchor,
        second_key,
        second_n,
        second_alias,
    )
    print(f"runtime two-doc aliases first={first_anchor!r}", flush=True)
    docs = _assert_docs_len(load_all(source, with_alias_budget(1)), 2)
    _assert_two_alias_identity(docs[0], first_anchor, [first_alias])
    _assert_two_alias_identity(docs[1], second_anchor, [second_alias])
    require_no_usable_prefix(load_all(source, with_alias_budget(0)))


def test_alias_limit_cross_yields_no_multidoc_prefix():
    key = unique_token()
    number = core_int_token()
    stream = f"{key}: {number}\n---\n{TWO_ALIAS_DOC}"
    print(f"alias cross first={key!r}", flush=True)
    docs = _assert_docs_len(load_all(stream, with_alias_budget(2)), 2)
    assert is_number_not_string(mapping_get(docs[0], key), number)
    _assert_two_alias_identity(docs[1], "base", ["copy", "other"])
    require_no_usable_prefix(load_all(stream, with_alias_budget(1)))


def test_alias_budget_does_not_change_core_types():
    doc = require_document(load(ANSWER_42, with_alias_budget(2)))
    answer = mapping_get(doc, "answer")
    print(f"answer={answer!r}", flush=True)
    assert is_number_not_string(answer, 42)


# ---------------------------------------------------------------------------
# C. Merge-key budget (per parse call, default 10000)
# ---------------------------------------------------------------------------


def test_three_merged_keys_ok_at_5_fail_at_2():
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(5))
    doc = require_document(load(THREE_MERGES, opts_ok))
    _assert_merged_keys(doc, [("one", 1), ("two", 2), ("three", 3)])
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(2))
    require_parse_failure(load(THREE_MERGES, opts_fail))


def test_three_merged_keys_ok_under_default():
    doc = require_document(load(THREE_MERGES, with_yaml11_schema()))
    _assert_merged_keys(doc, [("one", 1), ("two", 2), ("three", 3)])


def test_default_merge_allows_10000_rejects_10001():
    pairs_ok = [(f"m{index}", index) for index in range(10000)]
    source_ok = one_key_merges_document(pairs_ok)
    print(f"flat merge 10000 chars={len(source_ok)}", flush=True)
    doc = require_document(
        load(source_ok, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    )
    assert mapping_key_count(doc) == 10000
    assert is_number_not_string(mapping_get(doc, "m0"), 0)
    assert is_number_not_string(mapping_get(doc, "m9999"), 9999)
    pairs_over = [(f"m{index}", index) for index in range(10001)]
    source_over = one_key_merges_document(pairs_over)
    print(f"flat merge 10001 chars={len(source_over)}", flush=True)
    require_parse_failure(
        load(source_over, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    )


def test_three_merged_keys_on_multi_document_entry():
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(5))
    docs = _assert_docs_len(load_all(THREE_MERGES, opts_ok), 1)
    _assert_merged_keys(docs[0], [("one", 1), ("two", 2), ("three", 3)])
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(2))
    require_no_usable_prefix(load_all(THREE_MERGES, opts_fail))


def test_default_merge_on_multi_document_entry():
    docs = _assert_docs_len(load_all(THREE_MERGES, with_yaml11_schema()), 1)
    _assert_merged_keys(docs[0], [("one", 1), ("two", 2), ("three", 3)])
    chain = merge_chain_yaml(100000)
    print(f"default merge multidoc chain chars={len(chain)}", flush=True)
    require_no_usable_prefix(
        load_all(chain, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    )


def test_three_merged_keys_on_core_with_merge_tag():
    opts_ok = merge_parse_options(with_merge_on_core(), with_merge_budget(5))
    doc = require_document(load(THREE_MERGES, opts_ok))
    _assert_merged_keys(doc, [("one", 1), ("two", 2), ("three", 3)])
    opts_fail = merge_parse_options(with_merge_on_core(), with_merge_budget(2))
    require_parse_failure(load(THREE_MERGES, opts_fail))


def test_core_without_merge_ignores_merge_budget():
    core_opts = with_merge_budget(1)
    core_doc = require_plain_mapping(require_document(load(THREE_MERGES, core_opts)))
    print(f"core literal keys={list(core_doc.keys())}", flush=True)
    assert "<<" in core_doc, "Core without merge must keep a literal << key"
    yaml11_opts = merge_parse_options(with_yaml11_schema(), with_merge_budget(1))
    require_parse_failure(load(THREE_MERGES, yaml11_opts))


def test_runtime_merged_keys_ok_above_fail_below():
    pairs = [(unique_token(), core_int_token()) for _ in range(4)]
    source = one_key_merges_document(pairs)
    print(f"runtime four-key merges={pairs!r}", flush=True)
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(6))
    doc = require_document(load(source, opts_ok))
    _assert_merged_keys(doc, pairs)
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(3))
    require_parse_failure(load(source, opts_fail))


def test_repeated_merge_source_counts_walked_keys():
    pairs = [(unique_token(), core_int_token()) for _ in range(3)]
    once = single_merge_of_mapping(pairs)
    twice = double_merge_of_same_mapping(pairs)
    opts = merge_parse_options(with_yaml11_schema(), with_merge_budget(5))
    print(f"walked-keys pairs={pairs!r}", flush=True)
    once_seq = require_sequence(require_document(load(once, opts)))
    assert len(once_seq) == 2
    _assert_merged_keys(once_seq[1], pairs)
    require_parse_failure(load(twice, opts))


def test_disabled_merge_budget_allows_150_keys():
    source = merge_chain_yaml(150)
    print(f"disabled 150-key chain chars={len(source)}", flush=True)
    require_parse_failure(
        load(source, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    )
    opts = merge_parse_options(with_yaml11_schema(), with_merge_budget_disabled())
    seq = require_sequence(require_document(load(source, opts, timeout=_LARGE_TIMEOUT)))
    assert len(seq) == 150
    final = require_plain_mapping(seq[-1])
    assert mapping_key_count(final) == 150


def test_runtime_disabled_merge_budget_key_count():
    source = merge_chain_yaml(150)
    print(f"disabled-only 150-key chain chars={len(source)}", flush=True)
    require_parse_failure(
        load(source, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    )
    opts = merge_parse_options(with_yaml11_schema(), with_merge_budget_disabled())
    seq = require_sequence(
        require_document(load(source, opts, timeout=_LARGE_TIMEOUT))
    )
    assert len(seq) == 150
    assert mapping_key_count(seq[-1]) == 150


def test_two_docs_two_keys_each_ok_at_4_fail_at_3():
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(4))
    docs = _assert_docs_len(load_all(TWO_DOCS_TWO_KEYS, opts_ok), 2)
    _assert_merged_keys(docs[0], [("a", 1), ("b", 2)])
    _assert_merged_keys(docs[1], [("c", 3), ("d", 4)])
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(3))
    require_no_usable_prefix(load_all(TWO_DOCS_TWO_KEYS, opts_fail))


def test_runtime_two_docs_shared_merge_budget():
    first = [(unique_token(), core_int_token()), (unique_token(), core_int_token())]
    second = [(unique_token(), core_int_token()), (unique_token(), core_int_token())]
    source = two_docs_merge_two_keys_each(first, second)
    print(f"runtime shared merge first={first!r} second={second!r}", flush=True)
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(4))
    docs = _assert_docs_len(load_all(source, opts_ok), 2)
    _assert_merged_keys(docs[0], first)
    _assert_merged_keys(docs[1], second)
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(3))
    require_no_usable_prefix(load_all(source, opts_fail))


def test_merge_limit_cross_yields_no_multidoc_prefix():
    key = unique_token()
    number = core_int_token()
    stream = f"{key}: {number}\n---\n{THREE_MERGES}"
    print(f"merge cross first={key!r}", flush=True)
    opts_ok = merge_parse_options(with_yaml11_schema(), with_merge_budget(5))
    docs = _assert_docs_len(load_all(stream, opts_ok), 2)
    assert is_number_not_string(mapping_get(docs[0], key), number)
    _assert_merged_keys(docs[1], [("one", 1), ("two", 2), ("three", 3)])
    opts_fail = merge_parse_options(with_yaml11_schema(), with_merge_budget(2))
    require_no_usable_prefix(load_all(stream, opts_fail))


def test_hundred_thousand_merge_steps_fail_under_default():
    source = merge_chain_yaml(100000)
    print(f"default 100000-step chain chars={len(source)}", flush=True)
    result = load(source, with_yaml11_schema(), timeout=_LARGE_TIMEOUT)
    error = require_parse_failure_not_host_overflow(result)
    print(
        f"merge-100000 ok={result.ok!r} "
        f"report={observer_visible_report(error)!r}",
        flush=True,
    )
    assert result.ok is False


def test_merge_budget_does_not_change_type_resolution():
    opts = merge_parse_options(with_yaml11_schema(), with_merge_budget(5))
    doc = require_document(load(ANSWER_42, opts))
    answer = mapping_get(doc, "answer")
    print(f"answer={answer!r}", flush=True)
    assert is_number_not_string(answer, 42)
