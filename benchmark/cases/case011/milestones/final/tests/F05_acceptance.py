# feature: F05
"""FP-05: construct results, pipe, current value, and literals.

Assertions follow Full_PRD.original.md FP-05 (L224–L254) together with
current value / pipe (L22), null-is-host-none (L23 / L62), boolean-is-not
1-or-0 (L28), expression-reference as a deferred subexpression (L29 / L61),
value-error failure (L63), and unclosed backtick / raw string as the
L244 / L107 syntax kind (a caller who handles ``foo.`` also handles
the refusal, including a more specific syntax form). Functions that
consume expression references are FP-07.
Comparators and logic are FP-06. Evaluation options are not supplied.
"""

from __future__ import annotations

from pathsel import compile, search  # noqa: F401 — public search/compile surface

from F02_helpers import (
    compile_once_then_search,
    quoted_ident_text,
    runtime_dotted_field_key,
    runtime_unquotable_key,
)
from F03_helpers import (
    assert_bracket_search_is_value_error,
    bracket_sentinel_document,
    compile_bracket_expression,
    in_range_index,
    oneshot_bracket_search,
    require_bracket_null,
    require_bracket_value,
    require_oneshot_equals,
    search_compiled_bracket,
)
from F04_helpers import (
    json_literal_text,
    require_array_multiset,
    require_unsuccessful_compile_path,
)
from F05_helpers import (
    assert_unclosed_compile_is_syntax_kind,
    assert_unclosed_search_is_syntax_kind,
    local_ident,
    local_payload,
    escaped_backtick_string_literal,
    raw_string_text,
    require_constructed_list,
    require_deferred_reference,
    require_mapping,
    runtime_json_unicode_string_literal,
    unclosed_json_literal_text,
)

_PUBLIC_NUMBERS = frozenset(range(10))

_PHI = "\u03a6"

_HASH_DOC = {"foo": {"bar": "bar", "baz": "baz", "qux": "qux"}}
_QUOTED_TOP_DOC = {"baz": 2, 'qux"': 3}
_WILDCARD_HASH_DOC = {
    "foo": {
        "nested": {
            "one": {"a": "first", "b": "second", "c": "third"},
            "two": {"a": "first", "b": "second", "c": "third"},
            "three": {"a": "first", "b": "second", "c": "third"},
        }
    }
}
_LIST_DOC = {
    "foo": {
        "includeme": True,
        "bar": {
            "baz": [
                {"common": "first"},
                {"common": "second"},
            ]
        },
    }
}
_TOP_LIST_DOC = {"bar": 1, "baz": 2}
_PIPE_DOC = {"foo": {"bar": {"baz": "one"}, "other": {"baz": "two"}}}
_PIPE_STOP_DOC = {
    "foo": {
        "x": {"baz": "subkey"},
        "y": {"baz": "subkey"},
        "z": {"baz": "subkey"},
    }
}
_AT_DOC = {
    "foo": [{"name": "a"}, {"name": "b"}],
    "bar": {"baz": "qux"},
}
_LIST_ORACLE = [True, ["first", "second"]]


def _baited(document: dict) -> dict:
    baited = dict(document)
    baited.update(bracket_sentinel_document())
    return baited


def _require_null_field(mapping: object, key: str) -> None:
    require_mapping(mapping)
    assert key in mapping, f"missing-field key {key!r} was omitted: {mapping!r}"
    assert mapping[key] is None, (
        f"missing-field key {key!r} stored {mapping[key]!r}, not null"
    )


# ---------------------------------------------------------------------------
# A. Multiselect hash: written keys remain; missing stores null; null current
# ---------------------------------------------------------------------------


def test_multiselect_hash_builds_named_pairs():
    one = require_oneshot_equals("foo.{bar: bar}", _HASH_DOC, {"bar": "bar"})
    require_mapping(one)
    assert one == {"bar": "bar"}
    assert one != _HASH_DOC["foo"]
    assert one is not _HASH_DOC
    two = require_oneshot_equals(
        "foo.{bar: bar, baz: baz}", _HASH_DOC, {"bar": "bar", "baz": "baz"}
    )
    require_mapping(two)
    assert two == {"bar": "bar", "baz": "baz"}
    assert "qux" not in two
    assert two != _HASH_DOC["foo"]
    print(f"hash_pairs one={one!r} two={two!r}", flush=True)


def test_multiselect_hash_stores_null_for_missing_field():
    observed = require_oneshot_equals(
        "foo.{bar: bar, noexist: noexist}",
        _HASH_DOC,
        {"bar": "bar", "noexist": None},
    )
    require_mapping(observed)
    _require_null_field(observed, "noexist")
    assert observed["bar"] == "bar"
    assert list(observed.keys()) != ["bar"]
    print(f"hash_missing={observed!r}", flush=True)


def test_multiselect_hash_on_null_current_value_is_null():
    live = require_oneshot_equals(
        "foo.{nokey: nokey}", _HASH_DOC, {"nokey": None}
    )
    require_mapping(live)
    _require_null_field(live, "nokey")
    require_bracket_null(oneshot_bracket_search("foo.badkey.{nokey: nokey}", _HASH_DOC))
    on_null = require_bracket_value(
        oneshot_bracket_search("foo.badkey.{nokey: nokey}", _HASH_DOC)
    )
    print(f"hash_null_current live={live!r} on_null={on_null!r}", flush=True)
    assert on_null is None
    assert on_null != {"nokey": None}
    assert on_null != {}
    assert on_null != live


def test_runtime_multiselect_hash_missing_field_and_null_current():
    root = local_ident()
    k1, k2 = local_ident(), local_ident()
    missing = local_ident()
    bad = local_ident()
    alias, source = local_ident(), local_ident()
    assert alias != source
    p1, p2, source_payload = local_payload(), local_payload(), local_payload()
    alias_decoy = local_payload()
    inner = {k1: p1, k2: p2, source: source_payload}
    document = {root: inner, alias: alias_decoy}

    two = require_oneshot_equals(
        f"{root}.{{{k1}: {k1}, {k2}: {k2}}}", document, {k1: p1, k2: p2}
    )
    require_mapping(two)
    assert two == {k1: p1, k2: p2}
    assert two != inner

    stored = require_oneshot_equals(
        f"{root}.{{{k1}: {k1}, {missing}: {missing}}}",
        document,
        {k1: p1, missing: None},
    )
    require_mapping(stored)
    _require_null_field(stored, missing)
    assert stored[k1] == p1

    aliased = require_oneshot_equals(
        f"{root}.{{{alias}: {source}}}", document, {alias: source_payload}
    )
    require_mapping(aliased)
    assert alias in aliased
    assert aliased[alias] == source_payload
    assert aliased[alias] is not None
    assert aliased != {alias: None}
    assert aliased != {source: source_payload}
    assert aliased[alias] != alias_decoy

    require_bracket_null(
        oneshot_bracket_search(f"{root}.{bad}.{{{k1}: {k1}}}", document)
    )
    on_null = require_bracket_value(
        oneshot_bracket_search(f"{root}.{bad}.{{{k1}: {k1}}}", document)
    )
    live = require_oneshot_equals(
        f"{root}.{{{k1}: {k1}}}", document, {k1: p1}
    )
    require_mapping(live)
    print(
        f"runtime_hash two={two!r} stored={stored!r} aliased={aliased!r} "
        f"on_null={on_null!r} live={live!r}",
        flush=True,
    )
    assert on_null is None
    assert on_null != {k1: None}
    assert on_null != {}
    assert live == {k1: p1}


def test_compile_then_search_multiselect_hash():
    public = compile_once_then_search(
        "foo.{bar: bar, baz: baz}", _HASH_DOC
    )
    require_mapping(public)
    assert public == {"bar": "bar", "baz": "baz"}

    root = local_ident()
    k1, missing = local_ident(), local_ident()
    alias, source = local_ident(), local_ident()
    bad = local_ident()
    p1, source_payload = local_payload(), local_payload()
    document = {root: {k1: p1, source: source_payload}}

    parsed_missing = require_bracket_value(
        compile_bracket_expression(f"{root}.{{{k1}: {k1}, {missing}: {missing}}}")
    )
    first_missing = require_bracket_value(search_compiled_bracket(parsed_missing, document))
    second_missing = require_bracket_value(search_compiled_bracket(parsed_missing, document))
    require_mapping(first_missing)
    _require_null_field(first_missing, missing)
    assert first_missing == second_missing == {k1: p1, missing: None}

    parsed_alias = require_bracket_value(
        compile_bracket_expression(f"{root}.{{{alias}: {source}}}")
    )
    first_alias = require_bracket_value(search_compiled_bracket(parsed_alias, document))
    second_alias = require_bracket_value(search_compiled_bracket(parsed_alias, document))
    require_mapping(first_alias)
    assert first_alias == second_alias == {alias: source_payload}

    parsed_null = require_bracket_value(
        compile_bracket_expression(f"{root}.{bad}.{{{k1}: {k1}}}")
    )
    first_null = require_bracket_value(search_compiled_bracket(parsed_null, document))
    second_null = require_bracket_value(search_compiled_bracket(parsed_null, document))
    print(
        f"compile_hash public={public!r} missing={first_missing!r} "
        f"alias={first_alias!r} on_null={first_null!r}",
        flush=True,
    )
    assert first_null is second_null is None
    assert first_null != {k1: None}


# ---------------------------------------------------------------------------
# B. Quoted hash keys; one mapping per object-wildcard value
# ---------------------------------------------------------------------------


def test_multiselect_hash_quoted_dotted_key():
    observed = require_oneshot_equals(
        'foo.{"foo.bar": bar}', _HASH_DOC, {"foo.bar": "bar"}
    )
    require_mapping(observed)
    assert "foo.bar" in observed
    assert observed["foo.bar"] == "bar"
    assert observed != "bar"
    assert observed is not None
    print(f"quoted_dotted={observed!r}", flush=True)


def test_top_level_quoted_hash_keys_with_embedded_quote():
    observed = require_oneshot_equals(
        '{"baz": baz, "qux\\"": "qux\\""}',
        _QUOTED_TOP_DOC,
        {"baz": 2, 'qux"': 3},
    )
    require_mapping(observed)
    assert observed["baz"] == 2
    assert 'qux"' in observed
    assert observed['qux"'] == 3
    print(f"quoted_embedded={observed!r}", flush=True)


def test_multiselect_hash_after_object_wildcard():
    observed = require_bracket_value(
        oneshot_bracket_search("foo.nested.*.{a: a, b: b}", _WILDCARD_HASH_DOC)
    )
    require_constructed_list(observed)
    assert len(observed) == 3
    for item in observed:
        require_mapping(item)
        assert item == {"a": "first", "b": "second"}
        assert "c" not in item
    print(f"wildcard_hash={observed!r}", flush=True)


def test_runtime_quoted_hash_key_and_wildcard_hash():
    key, left, right = runtime_dotted_field_key()
    assert key != "foo.bar"
    assert right != ""
    source = local_ident()
    assert source != right
    payload, decoy = local_payload(), local_payload()
    root = local_ident()
    obj = {source: payload, right: decoy}
    document = {root: obj}
    quoted = quoted_ident_text(key)
    dotted = require_oneshot_equals(
        f"{root}.{{{quoted}: {source}}}", document, {key: payload}
    )
    require_mapping(dotted)
    assert list(dotted.keys()) == [key]
    assert dotted[key] == payload
    assert dotted[key] != decoy
    assert dotted != decoy
    print(f"runtime_dotted_key={key!r} left={left!r} right={right!r}", flush=True)

    unquotable = runtime_unquotable_key()
    uq_source = local_ident()
    uq_payload = local_payload()
    uq_root = local_ident()
    uq_doc = {uq_root: {uq_source: uq_payload}}
    uq_quoted = quoted_ident_text(unquotable)
    uq = require_oneshot_equals(
        f"{uq_root}.{{{uq_quoted}: {uq_source}}}",
        uq_doc,
        {unquotable: uq_payload},
    )
    require_mapping(uq)
    assert unquotable in uq
    assert uq[unquotable] == uq_payload

    inner = local_ident()
    extra = local_ident()
    assert extra not in {"a", "b"}
    triples = []
    values = {}
    for _ in range(3):
        name = local_ident()
        a_p, b_p, extra_p = local_payload(), local_payload(), local_payload()
        triples.append({"a": a_p, "b": b_p})
        values[name] = {"a": a_p, "b": b_p, extra: extra_p}
    wild_root = local_ident()
    wild_doc = {wild_root: {inner: values}}
    wild = require_bracket_value(
        oneshot_bracket_search(f"{wild_root}.{inner}.*.{{a: a, b: b}}", wild_doc)
    )
    require_constructed_list(wild)
    require_array_multiset(wild, triples)
    assert len(wild) == 3
    for item in wild:
        require_mapping(item)
        assert set(item.keys()) == {"a", "b"}
        assert extra not in item
    print(f"runtime_wildcard_hash={wild!r}", flush=True)


def test_compile_then_search_quoted_key_and_wildcard_hash():
    public = compile_once_then_search('foo.{"foo.bar": bar}', _HASH_DOC)
    require_mapping(public)
    assert public == {"foo.bar": "bar"}

    key, _left, right = runtime_dotted_field_key()
    source = local_ident()
    assert source != right
    payload, decoy = local_payload(), local_payload()
    root = local_ident()
    document = {root: {source: payload, right: decoy}}
    quoted = quoted_ident_text(key)
    parsed = require_bracket_value(
        compile_bracket_expression(f"{root}.{{{quoted}: {source}}}")
    )
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    require_mapping(first)
    assert first == second == {key: payload}
    assert first[key] != decoy

    inner = local_ident()
    extra = local_ident()
    triples = []
    values = {}
    for _ in range(3):
        name = local_ident()
        a_p, b_p, extra_p = local_payload(), local_payload(), local_payload()
        triples.append({"a": a_p, "b": b_p})
        values[name] = {"a": a_p, "b": b_p, extra: extra_p}
    wild_root = local_ident()
    wild_doc = {wild_root: {inner: values}}
    parsed_wild = require_bracket_value(
        compile_bracket_expression(f"{wild_root}.{inner}.*.{{a: a, b: b}}")
    )
    first_wild = require_bracket_value(search_compiled_bracket(parsed_wild, wild_doc))
    second_wild = require_bracket_value(search_compiled_bracket(parsed_wild, wild_doc))
    require_constructed_list(first_wild)
    require_array_multiset(first_wild, triples)
    require_array_multiset(second_wild, triples)
    print(
        f"compile_quoted public={public!r} dotted={first!r} wild={first_wild!r}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# C. Multiselect list: after a dot or as a top-level constructor
# ---------------------------------------------------------------------------


def test_multiselect_list_named_oracle():
    observed = require_oneshot_equals(
        "foo.[includeme, bar.baz[*].common]", _LIST_DOC, _LIST_ORACLE
    )
    require_constructed_list(observed)
    assert observed == [True, ["first", "second"]]
    assert observed[0] is True
    assert observed[0] is not 1
    assert observed != _LIST_DOC["foo"]
    print(f"list_oracle={observed!r}", flush=True)


def test_multiselect_list_on_null_current_value_is_null():
    live = require_oneshot_equals(
        "foo.[includeme, bar.baz[*].common]", _LIST_DOC, _LIST_ORACLE
    )
    require_constructed_list(live)
    require_bracket_null(
        oneshot_bracket_search("foo.badkey.[includeme, other]", _LIST_DOC)
    )
    on_null = require_bracket_value(
        oneshot_bracket_search("foo.badkey.[includeme, other]", _LIST_DOC)
    )
    print(f"list_null_current live={live!r} on_null={on_null!r}", flush=True)
    assert on_null is None
    assert on_null != []
    assert on_null != [None, None]
    assert on_null != live


def test_top_level_multiselect_list():
    observed = require_oneshot_equals("[bar, baz]", _TOP_LIST_DOC, [1, 2])
    require_constructed_list(observed)
    assert observed == [1, 2]
    assert observed != _TOP_LIST_DOC
    print(f"top_list={observed!r}", flush=True)


def test_runtime_multiselect_list_and_null_current():
    root = local_ident()
    keep, inner, field, common, bad = (
        local_ident(),
        local_ident(),
        local_ident(),
        local_ident(),
        local_ident(),
    )
    keep_payload = local_payload()
    c1, c2 = local_payload(), local_payload()
    document = {
        root: {
            keep: keep_payload,
            inner: {field: [{common: c1}, {common: c2}]},
        }
    }
    pair = require_oneshot_equals(
        f"{root}.[{keep}, {inner}.{field}[*].{common}]",
        document,
        [keep_payload, [c1, c2]],
    )
    require_constructed_list(pair)
    assert pair == [keep_payload, [c1, c2]]

    require_bracket_null(
        oneshot_bracket_search(f"{root}.{bad}.[{keep}, {local_ident()}]", document)
    )
    on_null = require_bracket_value(
        oneshot_bracket_search(f"{root}.{bad}.[{keep}, {local_ident()}]", document)
    )
    assert on_null is None
    assert on_null != []
    assert on_null != [None, None]

    k1, k2, k3 = local_ident(), local_ident(), local_ident()
    p1, p2, p3 = local_payload(), local_payload(), local_payload()
    top = {k1: p1, k2: p2, k3: p3}
    two = require_oneshot_equals(f"[{k1}, {k2}]", top, [p1, p2])
    require_constructed_list(two)
    three = require_oneshot_equals(f"[{k1}, {k2}, {k3}]", top, [p1, p2, p3])
    require_constructed_list(three)
    print(
        f"runtime_list pair={pair!r} two={two!r} three={three!r} on_null={on_null!r}",
        flush=True,
    )
    assert three == [p1, p2, p3]
    assert len(three) == 3
    assert three != two


def test_compile_then_search_multiselect_list():
    public = compile_once_then_search(
        "foo.[includeme, bar.baz[*].common]", _LIST_DOC
    )
    require_constructed_list(public)
    assert public == _LIST_ORACLE
    assert public[0] is True

    root = local_ident()
    keep, inner, field, common, bad = (
        local_ident(),
        local_ident(),
        local_ident(),
        local_ident(),
        local_ident(),
    )
    keep_payload = local_payload()
    c1, c2 = local_payload(), local_payload()
    document = {
        root: {
            keep: keep_payload,
            inner: {field: [{common: c1}, {common: c2}]},
        }
    }
    parsed = require_bracket_value(
        compile_bracket_expression(f"{root}.[{keep}, {inner}.{field}[*].{common}]")
    )
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    require_constructed_list(first)
    assert first == second == [keep_payload, [c1, c2]]

    k1, k2, k3 = local_ident(), local_ident(), local_ident()
    p1, p2, p3 = local_payload(), local_payload(), local_payload()
    top = {k1: p1, k2: p2, k3: p3}
    parsed_three = require_bracket_value(compile_bracket_expression(f"[{k1}, {k2}, {k3}]"))
    first_three = require_bracket_value(search_compiled_bracket(parsed_three, top))
    second_three = require_bracket_value(search_compiled_bracket(parsed_three, top))
    require_constructed_list(first_three)
    assert first_three == second_three == [p1, p2, p3]

    parsed_null = require_bracket_value(
        compile_bracket_expression(f"{root}.{bad}.[{keep}, {local_ident()}]")
    )
    first_null = require_bracket_value(search_compiled_bracket(parsed_null, document))
    second_null = require_bracket_value(search_compiled_bracket(parsed_null, document))
    print(
        f"compile_list public={public!r} pair={first!r} three={first_three!r} "
        f"on_null={first_null!r}",
        flush=True,
    )
    assert first_null is second_null is None
    assert first_null != []


# ---------------------------------------------------------------------------
# D. Pipe evaluates left then right; spaces optional; pipe stops a projection
# ---------------------------------------------------------------------------


def test_pipe_evaluates_left_then_right():
    mid = require_oneshot_equals("foo | bar", _PIPE_DOC, {"baz": "one"})
    require_mapping(mid)
    assert mid == {"baz": "one"}
    assert mid != {"baz": "two"}
    tail = require_oneshot_equals("foo | bar | baz", _PIPE_DOC, "one")
    print(f"pipe_chain mid={mid!r} tail={tail!r}", flush=True)
    assert tail == "one"
    assert tail != "two"


def test_pipe_spaces_optional():
    spaced = require_oneshot_equals("foo | bar | baz", _PIPE_DOC, "one")
    compact = require_oneshot_equals("foo|bar| baz", _PIPE_DOC, "one")
    print(f"pipe_spaces spaced={spaced!r} compact={compact!r}", flush=True)
    assert spaced == compact == "one"


def test_pipe_stops_projection_indexes_whole_array():
    projected = require_bracket_value(oneshot_bracket_search("foo.*.baz", _PIPE_STOP_DOC))
    require_constructed_list(projected)
    require_array_multiset(projected, ["subkey", "subkey", "subkey"])
    assert len(projected) == 3
    indexed = require_oneshot_equals("foo.*.baz | [0]", _PIPE_STOP_DOC, "subkey")
    print(f"pipe_stop projected={projected!r} indexed={indexed!r}", flush=True)
    assert indexed == "subkey"
    assert indexed is not None
    assert indexed != []
    assert indexed != projected


def test_runtime_pipe_chain_and_stops_projection():
    k1, k2, k3 = local_ident(), local_ident(), local_ident()
    payload = local_payload()
    chain_doc = {k1: {k2: {k3: payload}}}
    chained = require_oneshot_equals(f"{k1} | {k2} | {k3}", chain_doc, payload)
    compact = require_oneshot_equals(f"{k1}|{k2}| {k3}", chain_doc, payload)
    assert chained == compact == payload

    root, field = local_ident(), local_ident()
    payloads = [local_payload(), local_payload(), local_payload()]
    names = [local_ident(), local_ident(), local_ident()]
    stop_doc = {root: {name: {field: payloads[i]} for i, name in enumerate(names)}}
    projected = require_bracket_value(
        oneshot_bracket_search(f"{root}.*.{field}", stop_doc)
    )
    require_constructed_list(projected)
    require_array_multiset(projected, payloads)
    i = in_range_index(len(payloads))
    indexed = require_oneshot_equals(
        f"{root}.*.{field} | [{i}]", stop_doc, projected[i]
    )
    print(f"runtime_pipe_stop i={i} indexed={indexed!r}", flush=True)
    assert indexed == projected[i]
    assert indexed in payloads
    assert indexed is not None
    assert indexed != projected
    if i != 0:
        assert indexed != projected[0]

    extra = local_ident()
    extra_payload = local_payload()
    ctor_root, ctor_k = local_ident(), local_ident()
    ctor_payload = local_payload()
    ctor_doc = {ctor_root: {ctor_k: ctor_payload, extra: extra_payload}}
    constructed = require_oneshot_equals(
        f"{ctor_root} | {{{ctor_k}: {ctor_k}}}",
        ctor_doc,
        {ctor_k: ctor_payload},
    )
    require_mapping(constructed)
    assert constructed == {ctor_k: ctor_payload}
    assert extra not in constructed
    assert constructed != ctor_doc[ctor_root]
    assert constructed != ctor_payload
    print(f"runtime_pipe_ctor={constructed!r}", flush=True)


def test_compile_then_search_pipe_stops_projection():
    public_chain = compile_once_then_search("foo | bar | baz", _PIPE_DOC)
    assert public_chain == "one"
    public_stop = compile_once_then_search("foo.*.baz | [0]", _PIPE_STOP_DOC)
    assert public_stop == "subkey"

    root, field = local_ident(), local_ident()
    payloads = [local_payload(), local_payload(), local_payload()]
    names = [local_ident(), local_ident(), local_ident()]
    stop_doc = {root: {name: {field: payloads[i]} for i, name in enumerate(names)}}
    projected = require_bracket_value(
        oneshot_bracket_search(f"{root}.*.{field}", stop_doc)
    )
    require_constructed_list(projected)
    i = in_range_index(len(payloads))
    parsed = require_bracket_value(
        compile_bracket_expression(f"{root}.*.{field} | [{i}]")
    )
    first = require_bracket_value(search_compiled_bracket(parsed, stop_doc))
    second = require_bracket_value(search_compiled_bracket(parsed, stop_doc))
    assert first == second == projected[i]

    extra = local_ident()
    ctor_root, ctor_k = local_ident(), local_ident()
    ctor_payload, extra_payload = local_payload(), local_payload()
    ctor_doc = {ctor_root: {ctor_k: ctor_payload, extra: extra_payload}}
    parsed_ctor = require_bracket_value(
        compile_bracket_expression(f"{ctor_root} | {{{ctor_k}: {ctor_k}}}")
    )
    first_ctor = require_bracket_value(search_compiled_bracket(parsed_ctor, ctor_doc))
    second_ctor = require_bracket_value(search_compiled_bracket(parsed_ctor, ctor_doc))
    require_mapping(first_ctor)
    print(
        f"compile_pipe chain={public_chain!r} stop={first!r} ctor={first_ctor!r}",
        flush=True,
    )
    assert first_ctor == second_ctor == {ctor_k: ctor_payload}
    assert extra not in first_ctor


# ---------------------------------------------------------------------------
# E. `@` is the current value being searched
# ---------------------------------------------------------------------------


def test_current_value_token_is_the_document():
    observed = require_oneshot_equals("@", _AT_DOC, _AT_DOC)
    require_mapping(observed)
    assert observed == _AT_DOC
    print(f"at_document={observed!r}", flush=True)


def test_current_value_selects_bar_and_first_foo():
    bar = require_oneshot_equals("@.bar", _AT_DOC, {"baz": "qux"})
    require_mapping(bar)
    assert bar == {"baz": "qux"}
    field = require_oneshot_equals("bar", _AT_DOC, {"baz": "qux"})
    assert bar == field
    first = require_oneshot_equals("@.foo[0]", _AT_DOC, {"name": "a"})
    require_mapping(first)
    print(f"at_select bar={bar!r} first={first!r}", flush=True)
    assert first == {"name": "a"}


def test_pipe_then_at_is_left_hand_result():
    whole = require_oneshot_equals("@", _AT_DOC, _AT_DOC)
    require_mapping(whole)
    piped = require_oneshot_equals("foo | @", _AT_DOC, _AT_DOC["foo"])
    require_constructed_list(piped)
    print(f"pipe_at whole={whole!r} piped={piped!r}", flush=True)
    assert piped == _AT_DOC["foo"]
    assert piped != whole
    assert piped != _AT_DOC


def test_runtime_current_value_and_pipe_at():
    field = local_ident()
    root = local_ident()
    outer_payload, root_payload = local_payload(), local_payload()
    extra = local_ident()
    extra_payload = local_payload()
    root_obj = {field: root_payload, extra: extra_payload}
    document = {field: outer_payload, root: root_obj}
    whole = require_oneshot_equals("@", document, document)
    require_mapping(whole)
    assert whole == document
    outer = require_oneshot_equals(f"@.{field}", document, outer_payload)
    assert outer == outer_payload
    piped_at = require_oneshot_equals(f"{root} | @", document, root_obj)
    require_mapping(piped_at)
    assert piped_at == root_obj
    assert piped_at != document
    piped_field = require_oneshot_equals(
        f"{root} | @.{field}", document, root_payload
    )
    print(
        f"runtime_at outer={outer!r} piped_at={piped_at!r} "
        f"piped_field={piped_field!r}",
        flush=True,
    )
    assert piped_field == root_payload
    assert piped_field != outer_payload
    assert piped_field is not None


def test_compile_then_search_current_value():
    public = compile_once_then_search("@", _AT_DOC)
    require_mapping(public)
    assert public == _AT_DOC

    field = local_ident()
    root = local_ident()
    outer_payload, root_payload = local_payload(), local_payload()
    extra = local_ident()
    root_obj = {field: root_payload, extra: local_payload()}
    document = {field: outer_payload, root: root_obj}

    parsed_at = require_bracket_value(compile_bracket_expression(f"{root} | @"))
    first_at = require_bracket_value(search_compiled_bracket(parsed_at, document))
    second_at = require_bracket_value(search_compiled_bracket(parsed_at, document))
    require_mapping(first_at)
    assert first_at == second_at == root_obj
    assert first_at != document

    parsed_field = require_bracket_value(
        compile_bracket_expression(f"{root} | @.{field}")
    )
    first_field = require_bracket_value(search_compiled_bracket(parsed_field, document))
    second_field = require_bracket_value(search_compiled_bracket(parsed_field, document))
    print(
        f"compile_at public={public!r} piped={first_at!r} field={first_field!r}",
        flush=True,
    )
    assert first_field == second_field == root_payload
    assert first_field != outer_payload


# ---------------------------------------------------------------------------
# F. Backtick JSON literals are independent of the document
# ---------------------------------------------------------------------------


def test_json_literals_named_scalars_array_and_object():
    document = bracket_sentinel_document()
    foo = require_oneshot_equals('`"foo"`', document, "foo")
    assert foo == "foo"
    array = require_oneshot_equals("`[1, 2, 3]`", document, [1, 2, 3])
    require_constructed_list(array)
    obj = require_oneshot_equals('`{"a": "b"}`', document, {"a": "b"})
    require_mapping(obj)
    truth = require_oneshot_equals("`true`", document, True)
    assert truth is True
    assert truth is not 1
    falsehood = require_oneshot_equals("`false`", document, False)
    assert falsehood is False
    assert falsehood is not 0
    require_bracket_null(oneshot_bracket_search("`null`", document))
    nothing = require_bracket_value(oneshot_bracket_search("`null`", document))
    print(
        f"json_scalars foo={foo!r} array={array!r} obj={obj!r} "
        f"true={truth!r} false={falsehood!r} null={nothing!r}",
        flush=True,
    )
    assert nothing is None


def test_json_digit_literals_zero_through_nine():
    document = bracket_sentinel_document()
    for digit in range(10):
        value = require_oneshot_equals(f"`{digit}`", document, digit)
        assert value == digit
        assert type(value) is int
        assert value is not True
        assert value is not False
        print(f"json_digit {digit}={value!r}", flush=True)


def test_json_literal_starts_subexpression():
    document = bracket_sentinel_document()
    field = require_oneshot_equals('`{"a": "b"}`.a', document, "b")
    indexed = require_oneshot_equals("`[0, 1, 2]`[1]", document, 1)
    print(f"json_subexpr field={field!r} indexed={indexed!r}", flush=True)
    assert field == "b"
    assert indexed == 1
    assert type(indexed) is int


def test_json_literal_whitespace_unicode_and_escaped_backtick():
    document = bracket_sentinel_document()
    leading = require_oneshot_equals('`  {"foo": true}`', document, {"foo": True})
    require_mapping(leading)
    assert leading["foo"] is True
    trailing = require_oneshot_equals('`{"foo": true}   `', document, {"foo": True})
    require_mapping(trailing)
    assert trailing["foo"] is True
    phi = require_oneshot_equals('`"\\u03a6"`', document, _PHI)
    assert phi == _PHI
    assert phi != "\\u03a6"
    assert len(phi) == 1
    escaped = require_oneshot_equals('`"foo\\`bar"`', document, "foo`bar")
    print(
        f"json_ws_unicode leading={leading!r} trailing={trailing!r} "
        f"phi={phi!r} escaped={escaped!r}",
        flush=True,
    )
    assert escaped == "foo`bar"
    assert "`" in escaped


def test_json_literal_is_independent_of_document():
    key, payload = local_ident(), local_payload()
    literal = json_literal_text({key: payload})
    first_doc = bracket_sentinel_document()
    second_doc = bracket_sentinel_document()
    assert first_doc != second_doc
    first = require_oneshot_equals(literal, first_doc, {key: payload})
    second = require_oneshot_equals(literal, second_doc, {key: payload})
    require_mapping(first)
    print(f"json_independent first={first!r} second={second!r}", flush=True)
    assert first == second == {key: payload}
    assert first != first_doc
    assert second != second_doc


def test_runtime_json_literal_unicode_and_subexpression():
    document = bracket_sentinel_document()
    expr, decoded = runtime_json_unicode_string_literal()
    assert decoded != _PHI
    unicode_value = require_oneshot_equals(expr, document, decoded)
    assert unicode_value == decoded
    assert unicode_value != _PHI
    assert len(unicode_value) == 1

    left, right = local_ident(), local_ident()
    escaped_expr = escaped_backtick_string_literal(left, right)
    escaped = require_oneshot_equals(escaped_expr, document, f"{left}`{right}")
    assert escaped == f"{left}`{right}"
    assert "`" in escaped
    assert escaped != f"{left}{right}"

    obj_key, obj_field, obj_payload = (
        local_ident(),
        local_ident(),
        local_payload(),
    )
    obj_lit = json_literal_text({obj_field: obj_payload})
    field_value = require_oneshot_equals(
        f"{obj_lit}.{obj_field}", document, obj_payload
    )
    assert field_value == obj_payload

    items = [local_payload(), local_payload(), local_payload()]
    i = in_range_index(len(items))
    array_lit = json_literal_text(items)
    indexed = require_oneshot_equals(f"{array_lit}[{i}]", document, items[i])
    print(
        f"runtime_json unicode={unicode_value!r} escaped={escaped!r} "
        f"field={field_value!r} i={i} indexed={indexed!r}",
        flush=True,
    )
    assert indexed == items[i]
    if i != 0:
        assert indexed != items[0]


def test_compile_then_search_json_literal_subexpression():
    document = bracket_sentinel_document()
    public_field = compile_once_then_search('`{"a": "b"}`.a', document)
    assert public_field == "b"
    public_index = compile_once_then_search("`[0, 1, 2]`[1]", document)
    assert public_index == 1

    obj_field, obj_payload = local_ident(), local_payload()
    obj_lit = json_literal_text({obj_field: obj_payload})
    parsed = require_bracket_value(compile_bracket_expression(f"{obj_lit}.{obj_field}"))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    assert first == second == obj_payload

    items = [local_payload(), local_payload(), local_payload()]
    i = in_range_index(len(items))
    array_lit = json_literal_text(items)
    parsed_idx = require_bracket_value(compile_bracket_expression(f"{array_lit}[{i}]"))
    first_idx = require_bracket_value(search_compiled_bracket(parsed_idx, document))
    second_idx = require_bracket_value(search_compiled_bracket(parsed_idx, document))
    print(
        f"compile_json field={first!r} i={i} indexed={first_idx!r}",
        flush=True,
    )
    assert first_idx == second_idx == items[i]
    if i != 0:
        assert first_idx != items[0]


# ---------------------------------------------------------------------------
# G. Raw strings: text between single quotes, no JSON escapes
# ---------------------------------------------------------------------------


def test_raw_string_named_oracles_and_zero_is_text():
    document = bracket_sentinel_document()
    foo = require_oneshot_equals("'foo'", document, "foo")
    spaced = require_oneshot_equals("'  foo  '", document, "  foo  ")
    assert spaced == "  foo  "
    assert spaced != "foo"
    raw_zero = require_oneshot_equals("'0'", document, "0")
    json_zero = require_oneshot_equals("`0`", document, 0)
    print(
        f"raw_named foo={foo!r} spaced={spaced!r} raw0={raw_zero!r} "
        f"json0={json_zero!r}",
        flush=True,
    )
    assert raw_zero == "0"
    assert type(raw_zero) is str
    assert json_zero == 0
    assert type(json_zero) is int
    assert raw_zero != json_zero


def test_raw_string_does_not_interpret_unicode_escape():
    document = bracket_sentinel_document()
    raw = require_oneshot_equals("'\\u03a6'", document, "\\u03a6")
    json_phi = require_oneshot_equals('`"\\u03a6"`', document, _PHI)
    print(f"raw_unicode raw={raw!r} json={json_phi!r}", flush=True)
    assert raw == "\\u03a6"
    assert len(raw) == 6
    assert raw != _PHI
    assert json_phi == _PHI


def test_raw_string_quote_and_backslash():
    document = bracket_sentinel_document()
    quoted = require_oneshot_equals("'foo\\'bar'", document, "foo'bar")
    letter = require_oneshot_equals("'\\z'", document, "\\z")
    doubled = require_oneshot_equals("'\\\\'", document, "\\\\")
    print(
        f"raw_escapes quoted={quoted!r} letter={letter!r} doubled={doubled!r}",
        flush=True,
    )
    assert quoted == "foo'bar"
    assert letter == "\\z"
    assert doubled == "\\\\"
    assert len(doubled) == 2


def test_runtime_raw_string():
    document = bracket_sentinel_document()
    payload = local_payload()
    assert "'" not in payload
    plain = require_oneshot_equals(raw_string_text(payload), document, payload)
    assert plain == payload

    left, right = local_ident(), local_ident()
    body = f" {left}\\{right} "
    assert not body[body.index("\\") + 1 :].startswith("'")
    kept = require_oneshot_equals(raw_string_text(body), document, body)
    print(f"runtime_raw kept={kept!r}", flush=True)
    assert kept == body
    assert kept.startswith(" ")
    assert kept.endswith(" ")
    assert "\\" in kept
    assert kept != f" {left}{right} "
    assert kept != body.strip()

    hex4 = f"{(0x4E00 + (int(local_ident()[-4:], 16) % 0x2000)):04x}"
    assert hex4.lower() != "03a6"
    escape_text = f"\\u{hex4}"
    raw_u = require_oneshot_equals(f"'\\u{hex4}'", document, escape_text)
    assert raw_u == escape_text
    assert raw_u != chr(int(hex4, 16))
    assert raw_u != _PHI

    qleft, qright = local_ident(), local_ident()
    quoted = require_oneshot_equals(
        f"'{qleft}\\'{qright}'", document, f"{qleft}'{qright}"
    )
    assert quoted == f"{qleft}'{qright}"


def test_compile_then_search_raw_string():
    document = bracket_sentinel_document()
    public = compile_once_then_search("'\\u03a6'", document)
    assert public == "\\u03a6"
    assert public != _PHI

    left, right = local_ident(), local_ident()
    body = f" {left}\\{right} "
    parsed = require_bracket_value(compile_bracket_expression(raw_string_text(body)))
    first = require_bracket_value(search_compiled_bracket(parsed, document))
    second = require_bracket_value(search_compiled_bracket(parsed, document))
    print(f"compile_raw first={first!r}", flush=True)
    assert first == second == body
    assert "\\" in first
    assert first.startswith(" ")
    assert first.endswith(" ")


# ---------------------------------------------------------------------------
# H. Expression reference: `&` plus an expression, not evaluated immediately
# ---------------------------------------------------------------------------


def test_expression_reference_is_not_evaluated_immediately():
    live = require_oneshot_equals("foo", _HASH_DOC, {"bar": "bar", "baz": "baz", "qux": "qux"})
    require_mapping(live)
    result = oneshot_bracket_search("&foo", _HASH_DOC)
    deferred = require_deferred_reference(
        result, document=_HASH_DOC, immediates=(live, "bar")
    )
    print(f"expr_ref live={live!r} deferred_type={type(deferred).__name__}", flush=True)
    assert result.exception is None
    assert deferred is not None


def test_runtime_expression_reference_is_deferred():
    field, other, root, nested = (
        local_ident(),
        local_ident(),
        local_ident(),
        local_ident(),
    )
    payload, other_payload, nested_payload = (
        local_payload(),
        local_payload(),
        local_payload(),
    )
    document = {
        field: payload,
        other: other_payload,
        root: {nested: nested_payload},
    }
    live = require_oneshot_equals(field, document, payload)
    assert live == payload
    deferred = require_deferred_reference(
        oneshot_bracket_search(f"&{field}", document),
        document=document,
        immediates=(payload,),
    )
    other_deferred = require_deferred_reference(
        oneshot_bracket_search(f"&{other}", document),
        document=document,
        immediates=(other_payload,),
    )
    nested_live = require_oneshot_equals(
        f"{root}.{nested}", document, nested_payload
    )
    path_deferred = require_deferred_reference(
        oneshot_bracket_search(f"&{root}.{nested}", document),
        document=document,
        immediates=(nested_payload, nested_live),
    )
    print(
        f"runtime_expr_ref types={[type(deferred).__name__, type(other_deferred).__name__, type(path_deferred).__name__]}",
        flush=True,
    )
    assert deferred is not None
    assert other_deferred is not None
    assert path_deferred is not None


def test_compile_then_search_expression_reference_is_deferred():
    field, root, nested = local_ident(), local_ident(), local_ident()
    payload, nested_payload = local_payload(), local_payload()
    document = {field: payload, root: {nested: nested_payload}}

    parsed = require_bracket_value(compile_bracket_expression(f"&{field}"))
    first = require_deferred_reference(
        search_compiled_bracket(parsed, document),
        document=document,
        immediates=(payload,),
    )
    second = require_deferred_reference(
        search_compiled_bracket(parsed, document),
        document=document,
        immediates=(payload,),
    )
    parsed_path = require_bracket_value(compile_bracket_expression(f"&{root}.{nested}"))
    first_path = require_deferred_reference(
        search_compiled_bracket(parsed_path, document),
        document=document,
        immediates=(nested_payload,),
    )
    second_path = require_deferred_reference(
        search_compiled_bracket(parsed_path, document),
        document=document,
        immediates=(nested_payload,),
    )
    print(
        f"compile_expr_ref types={[type(first).__name__, type(second).__name__, type(first_path).__name__, type(second_path).__name__]}",
        flush=True,
    )
    assert first is not None
    assert second is not None
    assert first_path is not None
    assert second_path is not None


# ---------------------------------------------------------------------------
# I. Named constructor / literal / pipe failures
# ---------------------------------------------------------------------------


def test_backtick_foo_quote_bar_does_not_succeed():
    document = _baited({"unused": local_payload()})
    live = require_oneshot_equals('`"foo"`', document, "foo")
    assert live == "foo"
    observed = assert_bracket_search_is_value_error('`foo"bar`', document)
    result = oneshot_bracket_search('`foo"bar`', document)
    print(f"foo_quote_bar exc={observed!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document
    assert result.value is not None or result.exception is not None
    assert result.value != live


def test_unclosed_backtick_and_raw_string_are_syntax():
    document = _baited({"unused": local_payload()})
    live_json = require_oneshot_equals('`"foo"`', document, "foo")
    live_raw = require_oneshot_equals("'foo'", document, "foo")
    assert live_json == "foo"
    assert live_raw == "foo"
    assert_unclosed_search_is_syntax_kind('`"foo"`'[:-1], document)
    assert_unclosed_search_is_syntax_kind("'foo", document)


def test_literal_after_dot_does_not_succeed():
    document = _baited(_HASH_DOC)
    live = require_oneshot_equals("foo.bar", document, "bar")
    observed = assert_bracket_search_is_value_error('foo.`"bar"`', document)
    result = oneshot_bracket_search('foo.`"bar"`', document)
    print(f"literal_after_dot exc={observed!r} live={live!r}", flush=True)
    assert result.exception is not None
    assert result.value is not document
    assert result.value != live
    assert result.value != "bar"


def test_unclosed_or_trailing_comma_multiselect_does_not_succeed():
    document = _baited(_HASH_DOC)
    live_hash = require_oneshot_equals(
        "foo.{bar: bar, baz: baz}", document, {"bar": "bar", "baz": "baz"}
    )
    live_list = require_oneshot_equals(
        "foo.[includeme, bar.baz[*].common]",
        _baited(_LIST_DOC),
        _LIST_ORACLE,
    )
    require_mapping(live_hash)
    require_constructed_list(live_list)
    list_doc = _baited(_LIST_DOC)
    for expression, doc in (
        ("foo.{bar: bar", document),
        ("foo.[includeme", list_doc),
        ("foo.{bar: bar,}", document),
        ("foo.[includeme,]", list_doc),
    ):
        observed = assert_bracket_search_is_value_error(expression, doc)
        result = oneshot_bracket_search(expression, doc)
        print(f"unclosed_multiselect {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not doc
        assert result.value != {}
        assert result.value != []
        assert result.value != live_hash
        assert result.value != live_list


def test_pipe_with_missing_side_does_not_succeed():
    document = _baited(_PIPE_DOC)
    live = require_oneshot_equals("foo | bar", document, {"baz": "one"})
    require_mapping(live)
    for expression in ("foo |", "| foo"):
        observed = assert_bracket_search_is_value_error(expression, document)
        result = oneshot_bracket_search(expression, document)
        print(f"missing_pipe_side {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not document
        assert result.value != live
        assert result.value is not None or result.exception is not None


def test_runtime_constructor_literal_and_pipe_failures():
    ident, other = local_ident(), local_ident()
    payload = local_payload()
    root, field = local_ident(), local_ident()
    document = _baited({root: {field: payload}})

    live_json = require_oneshot_equals('`"foo"`', document, "foo")
    assert live_json == "foo"
    quoted = assert_bracket_search_is_value_error(f'`{ident}"{other}`', document)
    quoted_result = oneshot_bracket_search(f'`{ident}"{other}`', document)
    print(f"runtime_foo_quote_bar exc={quoted!r}", flush=True)
    assert quoted_result.exception is not None
    assert quoted_result.value is not document

    unclosed_json = unclosed_json_literal_text({ident: payload})
    assert_unclosed_search_is_syntax_kind(unclosed_json, document)
    assert_unclosed_search_is_syntax_kind(f"'{payload}", document)

    live_field = require_oneshot_equals(f"{root}.{field}", document, payload)
    after_dot = f"{root}.{json_literal_text(payload)}"
    after = assert_bracket_search_is_value_error(after_dot, document)
    after_result = oneshot_bracket_search(after_dot, document)
    print(f"runtime_literal_after_dot exc={after!r} live={live_field!r}", flush=True)
    assert after_result.exception is not None
    assert after_result.value is not document
    assert after_result.value != live_field

    live_hash = require_oneshot_equals(
        f"{root}.{{{field}: {field}}}", document, {field: payload}
    )
    require_mapping(live_hash)
    for expression in (
        f"{root}.{{{field}: {field}",
        f"{root}.[{field}",
        f"{root}.{{{field}: {field},}}",
        f"{root}.[{field},]",
    ):
        observed = assert_bracket_search_is_value_error(expression, document)
        result = oneshot_bracket_search(expression, document)
        print(f"runtime_unclosed_ms {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not document
        assert result.value != {}
        assert result.value != []
        assert result.value != live_hash

    live_pipe = require_oneshot_equals(f"{root} | {field}", document, payload)
    for expression in (f"{root} |", f"| {root}"):
        observed = assert_bracket_search_is_value_error(expression, document)
        result = oneshot_bracket_search(expression, document)
        print(f"runtime_missing_pipe {expression!r} exc={observed!r}", flush=True)
        assert result.exception is not None
        assert result.value is not document
        assert result.value != live_pipe


def test_compile_path_constructor_literal_and_pipe_failures():
    ident, other = local_ident(), local_ident()
    payload = local_payload()
    root, field = local_ident(), local_ident()
    document = _baited({root: {field: payload}})

    assert_unclosed_compile_is_syntax_kind('`"foo"`'[:-1])
    assert_unclosed_compile_is_syntax_kind("'foo")
    assert_unclosed_compile_is_syntax_kind(unclosed_json_literal_text({ident: payload}))
    assert_unclosed_compile_is_syntax_kind(f"'{payload}")

    require_unsuccessful_compile_path('`foo"bar`', document)
    require_unsuccessful_compile_path(f'`{ident}"{other}`', document)
    require_unsuccessful_compile_path('foo.`"bar"`', _baited(_HASH_DOC))
    require_unsuccessful_compile_path(
        f"{root}.{json_literal_text(payload)}", document
    )
    require_unsuccessful_compile_path("foo.{bar: bar", _baited(_HASH_DOC))
    require_unsuccessful_compile_path("foo.[includeme", _baited(_LIST_DOC))
    require_unsuccessful_compile_path("foo.{bar: bar,}", _baited(_HASH_DOC))
    require_unsuccessful_compile_path("foo.[includeme,]", _baited(_LIST_DOC))
    require_unsuccessful_compile_path(f"{root}.{{{field}: {field}", document)
    require_unsuccessful_compile_path(f"{root}.[{field},]", document)
    require_unsuccessful_compile_path("foo |", _baited(_PIPE_DOC))
    require_unsuccessful_compile_path("| foo", _baited(_PIPE_DOC))
    require_unsuccessful_compile_path(f"{root} |", document)
    require_unsuccessful_compile_path(f"| {root}", document)
    print("compile_path_failures_ok", flush=True)
