# feature: F05
"""Grammar-based parsing and constituent trees (FP-05).

Chart-parser exhaustive counts on the fourteen-production grammar;
shift-reduce only on the unambiguous five-token sentence. Generation
distinguishes a quoted empty string from an empty production. Tree
comparison is recursive labels-and-children. Exception types, message
wording, bracket golden strings, and ASCII drawing are not pinned.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

from lingora.grammar import CFG
from lingora.parse import ChartParser, ShiftReduceParser
from lingora.parse.generate import generate
from lingora.tree import Tree

from _harness import call, workspace
from _helpers import (
    assert_constituent_covers,
    assert_tree_refused,
    bound_resource_path,
    constituent_child_at,
    constituent_leaves,
    generated_of,
    grammar_productions,
    grammar_start_symbol,
    grammar_terminals,
    immediate_dominator_label,
    node_label,
    parsed_with,
    pretty_printed_tree,
    require_grammar,
    require_parse_refused,
    require_parse_trees,
    require_tree,
    require_tree_refused,
    text_has_ordered_subsequence,
    tree_child_count,
)

FOURTEEN_PRODUCTIONS = """
S -> NP VP
PP -> P NP
NP -> Det N | NP PP
VP -> V NP | VP PP
Det -> 'a' | 'the'
N -> 'dog' | 'cat'
V -> 'chased' | 'sat'
P -> 'on' | 'in'
"""

N_DET_PRODUCTIONS = """
S -> NP VP
PP -> P NP
NP -> N Det | NP PP
VP -> V NP | VP PP
Det -> 'a' | 'the'
N -> 'dog' | 'cat'
V -> 'chased' | 'sat'
P -> 'on' | 'in'
"""

FIVE_TOKENS = ["the", "cat", "chased", "the", "dog"]
RUG_TOKENS = ["the", "cat", "chased", "the", "dog", "on", "the", "rug"]
COVERED_UNGRAMMATICAL = ["dog", "cat", "the"]
UNICORN_TOKENS = ["the", "unicorn", "chased", "the", "dog"]

BRACKETED_S_I_SAW_HIM = "(S (NP I) (VP (V saw) (NP him)))"
PUBLIC_LABEL_ORDER = ["S", "NP", "VP", "V", "NP"]
PUBLIC_LEAF_ORDER = ["I", "saw", "him"]
PUBLIC_LABELS = {"S", "NP", "VP", "PP", "Det", "N", "V", "P", "A", "B", "X"}
PUBLIC_TOKENS = {
    "the",
    "cat",
    "chased",
    "dog",
    "on",
    "rug",
    "a",
    "sat",
    "in",
    "I",
    "saw",
    "him",
    "unicorn",
    "b",
}


def _runtime_token(*, forbidden: set[str] | None = None) -> str:
    blocked = set(forbidden or ())
    blocked.update(PUBLIC_TOKENS)
    while True:
        tok = "w" + uuid.uuid4().hex[:8]
        if tok not in blocked:
            return tok


def _runtime_symbol(*, forbidden: set[str] | None = None) -> str:
    blocked = set(forbidden or ())
    blocked.update(PUBLIC_LABELS)
    while True:
        lab = "Z" + uuid.uuid4().hex[:6].upper()
        if lab not in blocked:
            return lab


@contextmanager
def _empty_resources():
    """Grammar-based parsing does not require packaged models."""
    with workspace() as ws:
        with bound_resource_path(ws, present=False):
            yield ws


def _read_cfg(text: str):
    return require_grammar(call(CFG.fromstring, text))


def _parse_call(parser_cls, grammar, tokens):
    constructed = call(parser_cls, grammar)
    if constructed.exception is not None:
        return constructed
    inst = constructed.value
    parse_fn = getattr(inst, "parse", None)
    if not callable(parse_fn):
        return constructed
    return call(parse_fn, list(tokens))


def _tree_from_bracketed(text: str):
    return require_tree(call(Tree.fromstring, text))


def _tree_from_children(label: str, children):
    return require_tree(call(Tree, label, children))


def _s_i_saw_him_constructed():
    np_i = _tree_from_children("NP", ["I"])
    v_saw = _tree_from_children("V", ["saw"])
    np_him = _tree_from_children("NP", ["him"])
    vp = _tree_from_children("VP", [v_saw, np_him])
    return _tree_from_children("S", [np_i, vp])


def _fourteen_skeleton(*, det: str, n_subj: str, n_obj: str, verb: str, prep: str) -> str:
    return (
        "S -> NP VP\n"
        "PP -> P NP\n"
        "NP -> Det N | NP PP\n"
        "VP -> V NP | VP PP\n"
        f"Det -> 'a' | '{det}'\n"
        f"N -> '{n_subj}' | '{n_obj}'\n"
        f"V -> '{verb}' | 'sat'\n"
        f"P -> '{prep}' | 'in'\n"
    )


def _assert_five_token_covers(tree, tokens: list[str], *, start: str = "S") -> None:
    print(
        f"five-token root={node_label(tree)!r} leaves={constituent_leaves(tree)!r}",
        flush=True,
    )
    assert node_label(tree) == start
    assert constituent_leaves(tree) == list(tokens)
    assert_constituent_covers(tree, "NP", tokens[:2])
    assert_constituent_covers(tree, "VP", tokens[2:])
    assert_constituent_covers(tree, "V", [tokens[2]])
    assert_constituent_covers(tree, "NP", tokens[3:])


def _pp_kinds(trees, tokens: list[str]) -> tuple[int | None, int | None]:
    pp_span = tokens[5:]
    object_pp = tokens[3:]
    verb_object_pp = tokens[2:]
    np_at = None
    vp_at = None
    for index, tree in enumerate(trees):
        leaves = constituent_leaves(tree)
        print(f"rug tree {index} leaves={leaves!r}", flush=True)
        assert leaves == list(tokens)
        parent = immediate_dominator_label(tree, "PP", pp_span)
        if parent == "NP":
            assert_constituent_covers(tree, "NP", object_pp)
            np_at = index
        elif parent == "VP":
            assert_constituent_covers(tree, "VP", verb_object_pp)
            vp_at = index
    return np_at, vp_at


def _quoted_empty_grammar(a: str, b: str) -> str:
    return f"S -> A B\nA -> '{a}'\nB -> '{b}' | ''\n"


def _empty_production_grammar(a: str, b: str) -> str:
    return f"S -> A B\nA -> '{a}'\nB -> '{b}'\nB ->\n"


def _as_tuple_set(sentences: list[list[str]]) -> set[tuple[str, ...]]:
    return {tuple(sent) for sent in sentences}


# ---------------------------------------------------------------------------
# A. CFG reader: start S, fourteen productions, named terminals
# ---------------------------------------------------------------------------


def test_fourteen_production_grammar_start_s_and_named_terminals():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
    start = grammar_start_symbol(grammar)
    prods = grammar_productions(grammar)
    terms = grammar_terminals(grammar)
    print(
        f"fourteen start={start!r} n_prods={len(prods)} terminals={sorted(terms)!r}",
        flush=True,
    )
    assert start == "S"
    assert len(prods) == 14
    for tok in ("the", "cat", "chased", "dog"):
        assert tok in terms


def test_cfg_reader_runtime_start_count_and_terminals_follow_caller():
    start = _runtime_symbol()
    left = _runtime_symbol(forbidden={start})
    right = _runtime_symbol(forbidden={start, left})
    w1 = _runtime_token()
    w2 = _runtime_token(forbidden={w1})
    text = f"{start} -> {left} {right}\n{left} -> '{w1}'\n{right} -> '{w2}'\n"
    print(f"runtime cfg start={start!r} terminals={[w1, w2]!r}", flush=True)
    with _empty_resources():
        grammar = _read_cfg(text)
    got_start = grammar_start_symbol(grammar)
    prods = grammar_productions(grammar)
    terms = grammar_terminals(grammar)
    assert got_start == start
    assert got_start != "S"
    assert len(prods) == 3
    assert len(prods) != 14
    assert w1 in terms
    assert w2 in terms
    assert "the" not in terms
    assert "cat" not in terms


# ---------------------------------------------------------------------------
# B. Chart: five-token sentence is exactly one S tree
# ---------------------------------------------------------------------------


def test_chart_five_token_sentence_exactly_one_s_tree():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
        trees = parsed_with(ChartParser, grammar, FIVE_TOKENS)
    print(f"chart five-token n={len(trees)}", flush=True)
    assert len(trees) == 1
    _assert_five_token_covers(trees[0], FIVE_TOKENS)


def test_chart_runtime_five_token_sentence_exactly_one_tree():
    det = _runtime_token()
    n_subj = _runtime_token(forbidden={det})
    n_obj = _runtime_token(forbidden={det, n_subj})
    verb = _runtime_token(forbidden={det, n_subj, n_obj})
    prep = _runtime_token(forbidden={det, n_subj, n_obj, verb})
    tokens = [det, n_subj, verb, det, n_obj]
    text = _fourteen_skeleton(
        det=det, n_subj=n_subj, n_obj=n_obj, verb=verb, prep=prep
    )
    print(f"runtime five-token {tokens!r}", flush=True)
    with _empty_resources():
        grammar = _read_cfg(text)
        trees = parsed_with(ChartParser, grammar, tokens)
    assert len(trees) == 1
    _assert_five_token_covers(trees[0], tokens, start=grammar_start_symbol(grammar))


# ---------------------------------------------------------------------------
# C. Chart: rug sentence, PP attachment NP vs VP
# ---------------------------------------------------------------------------


def test_chart_rug_sentence_two_pp_attachments():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS + "\nN -> 'rug'\n")
        trees = parsed_with(ChartParser, grammar, RUG_TOKENS)
    print(f"chart rug n={len(trees)}", flush=True)
    assert len(trees) > 1
    np_at, vp_at = _pp_kinds(trees, RUG_TOKENS)
    assert np_at is not None
    assert vp_at is not None
    assert np_at != vp_at


def test_chart_runtime_pp_attachment_ambiguity():
    det = _runtime_token()
    n_subj = _runtime_token(forbidden={det})
    n_obj = _runtime_token(forbidden={det, n_subj})
    verb = _runtime_token(forbidden={det, n_subj, n_obj})
    prep = _runtime_token(forbidden={det, n_subj, n_obj, verb})
    n_pp = _runtime_token(forbidden={det, n_subj, n_obj, verb, prep})
    tokens = [det, n_subj, verb, det, n_obj, prep, det, n_pp]
    text = _fourteen_skeleton(
        det=det, n_subj=n_subj, n_obj=n_obj, verb=verb, prep=prep
    ) + f"N -> '{n_pp}'\n"
    print(f"runtime rug tokens={tokens!r}", flush=True)
    with _empty_resources():
        grammar = _read_cfg(text)
        trees = parsed_with(ChartParser, grammar, tokens)
    assert len(trees) > 1
    np_at, vp_at = _pp_kinds(trees, tokens)
    assert np_at is not None
    assert vp_at is not None
    assert np_at != vp_at


# ---------------------------------------------------------------------------
# D. Empty parse set vs uncovered-token refusal vs empty token list
# ---------------------------------------------------------------------------


def test_chart_ungrammatical_covered_tokens_empty_parse_set():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
        trees = parsed_with(ChartParser, grammar, COVERED_UNGRAMMATICAL)
    print(f"dog-cat-the n={len(trees)}", flush=True)
    assert trees == []


def test_chart_empty_token_list_empty_parse_set():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
        trees = parsed_with(ChartParser, grammar, [])
    print(f"empty-tokens n={len(trees)}", flush=True)
    assert trees == []


def test_chart_uncovered_token_is_refused_not_empty_set():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
        empty = parsed_with(ChartParser, grammar, COVERED_UNGRAMMATICAL)
        refused = _parse_call(ChartParser, grammar, UNICORN_TOKENS)
    print(f"covered-ungrammatical n={len(empty)}", flush=True)
    assert empty == []
    require_parse_refused(refused)


def test_chart_runtime_uncovered_vs_covered_ungrammatical():
    det = _runtime_token()
    n_subj = _runtime_token(forbidden={det})
    n_obj = _runtime_token(forbidden={det, n_subj})
    verb = _runtime_token(forbidden={det, n_subj, n_obj})
    prep = _runtime_token(forbidden={det, n_subj, n_obj, verb})
    text = _fourteen_skeleton(
        det=det, n_subj=n_subj, n_obj=n_obj, verb=verb, prep=prep
    )
    legal = [det, n_subj, verb, det, n_obj]
    covered_bad = [n_subj, det, verb, det, n_obj]
    nonce = _runtime_token(forbidden={det, n_subj, n_obj, verb, prep})
    uncovered = [det, n_subj, nonce, det, n_obj]
    print(
        f"runtime covered-bad={covered_bad!r} uncovered={uncovered!r}",
        flush=True,
    )
    with _empty_resources():
        grammar = _read_cfg(text)
        ok = parsed_with(ChartParser, grammar, legal)
        empty = parsed_with(ChartParser, grammar, covered_bad)
        refused = _parse_call(ChartParser, grammar, uncovered)
    assert len(ok) == 1
    assert empty == []
    require_parse_refused(refused)


# ---------------------------------------------------------------------------
# E. Shift-reduce: same covering as chart on the five-token sentence
# ---------------------------------------------------------------------------


def test_shift_reduce_five_token_same_shape_as_chart():
    with _empty_resources():
        grammar = _read_cfg(FOURTEEN_PRODUCTIONS)
        trees = parsed_with(ShiftReduceParser, grammar, FIVE_TOKENS)
    print(f"sr five-token n={len(trees)}", flush=True)
    assert len(trees) == 1
    _assert_five_token_covers(trees[0], FIVE_TOKENS)


def test_shift_reduce_runtime_five_token_same_covering():
    det = _runtime_token()
    n_subj = _runtime_token(forbidden={det})
    n_obj = _runtime_token(forbidden={det, n_subj})
    verb = _runtime_token(forbidden={det, n_subj, n_obj})
    prep = _runtime_token(forbidden={det, n_subj, n_obj, verb})
    tokens = [det, n_subj, verb, det, n_obj]
    text = _fourteen_skeleton(
        det=det, n_subj=n_subj, n_obj=n_obj, verb=verb, prep=prep
    )
    print(f"runtime sr tokens={tokens!r}", flush=True)
    with _empty_resources():
        grammar = _read_cfg(text)
        chart_trees = parsed_with(ChartParser, grammar, tokens)
        sr_trees = parsed_with(ShiftReduceParser, grammar, tokens)
    assert len(chart_trees) == 1
    assert len(sr_trees) == 1
    start = grammar_start_symbol(grammar)
    _assert_five_token_covers(chart_trees[0], tokens, start=start)
    _assert_five_token_covers(sr_trees[0], tokens, start=start)


# ---------------------------------------------------------------------------
# F. Parser consults the caller grammar
# ---------------------------------------------------------------------------


def test_chart_consults_caller_grammar_swapped_terminals_same_length():
    x = _runtime_token()
    y = _runtime_token(forbidden={x})
    g1_text = f"S -> A B\nA -> '{x}'\nB -> '{y}'\n"
    g2_text = f"S -> A B\nA -> '{y}'\nB -> '{x}'\n"
    tokens = [x, y]
    print(f"swapped terminals tokens={tokens!r}", flush=True)
    with _empty_resources():
        g1 = _read_cfg(g1_text)
        g2 = _read_cfg(g2_text)
        trees1 = parsed_with(ChartParser, g1, tokens)
        trees2 = parsed_with(ChartParser, g2, tokens)
    print(f"G1 n={len(trees1)} G2 n={len(trees2)}", flush=True)
    assert len(trees1) == 1
    assert constituent_leaves(trees1[0]) == tokens
    assert trees2 == []


def test_chart_same_five_tokens_np_n_det_empty_set():
    with _empty_resources():
        ok_g = _read_cfg(FOURTEEN_PRODUCTIONS)
        bad_g = _read_cfg(N_DET_PRODUCTIONS)
        ok = parsed_with(ChartParser, ok_g, FIVE_TOKENS)
        empty = parsed_with(ChartParser, bad_g, FIVE_TOKENS)
    print(f"NP->Det N n={len(ok)} NP->N Det n={len(empty)}", flush=True)
    assert len(ok) == 1
    assert empty == []


# ---------------------------------------------------------------------------
# G. String generation: quoted empty string vs empty production
# ---------------------------------------------------------------------------


def test_generate_quoted_empty_string_is_a_then_empty_token():
    with _empty_resources():
        grammar = _read_cfg(_quoted_empty_grammar("a", "b"))
        sentences = generated_of(generate, grammar, n=20)
    got = _as_tuple_set(sentences)
    print(f"quoted-empty generated={sorted(got)!r}", flush=True)
    assert ("a", "b") in got
    assert ("a", "") in got


def test_generate_empty_production_is_one_token_a():
    with _empty_resources():
        grammar = _read_cfg(_empty_production_grammar("a", "b"))
        sentences = generated_of(generate, grammar, n=20)
    got = _as_tuple_set(sentences)
    print(f"empty-production generated={sorted(got)!r}", flush=True)
    assert ("a", "b") in got
    assert ("a",) in got
    assert ("a", "") not in got


def test_generate_runtime_quoted_empty_vs_empty_production():
    a = _runtime_token()
    b = _runtime_token(forbidden={a})
    print(f"runtime generate a={a!r} b={b!r}", flush=True)
    with _empty_resources():
        quoted = _read_cfg(_quoted_empty_grammar(a, b))
        empty_prod = _read_cfg(_empty_production_grammar(a, b))
        quoted_sents = generated_of(generate, quoted, n=20)
        empty_sents = generated_of(generate, empty_prod, n=20)
    quoted_set = _as_tuple_set(quoted_sents)
    empty_set = _as_tuple_set(empty_sents)
    print(f"quoted={sorted(quoted_set)!r} empty-prod={sorted(empty_set)!r}", flush=True)
    assert (a, b) in quoted_set
    assert (a, "") in quoted_set
    assert (a, b) in empty_set
    assert (a,) in empty_set
    assert (a, "") not in empty_set
    assert quoted_set != empty_set


# ---------------------------------------------------------------------------
# H. Constituent trees: bracketed text, pretty-print, equality, length
# ---------------------------------------------------------------------------


def test_bracketed_tree_equals_constructed_s_i_saw_him():
    with _empty_resources():
        from_text = _tree_from_bracketed(BRACKETED_S_I_SAW_HIM)
        from_kids = _s_i_saw_him_constructed()
    print(
        f"bracketed==constructed {from_text == from_kids}",
        flush=True,
    )
    assert from_text == from_kids


def test_pretty_print_shows_labels_and_leaves_in_order():
    with _empty_resources():
        tree = _tree_from_bracketed(BRACKETED_S_I_SAW_HIM)
        text = pretty_printed_tree(tree)
    print(f"pretty-print text={text!r}", flush=True)
    assert text_has_ordered_subsequence(text, PUBLIC_LABEL_ORDER)
    assert text_has_ordered_subsequence(text, PUBLIC_LEAF_ORDER)


def test_changing_inner_np_label_to_x_breaks_equality_and_pretty_print():
    with _empty_resources():
        original = _tree_from_bracketed(BRACKETED_S_I_SAW_HIM)
        inner_x = _tree_from_children("X", ["him"])
        v_saw = _tree_from_children("V", ["saw"])
        vp = _tree_from_children("VP", [v_saw, inner_x])
        np_i = _tree_from_children("NP", ["I"])
        changed = _tree_from_children("S", [np_i, vp])
        text = pretty_printed_tree(changed)
    print(
        f"changed equal={original == changed} pretty={text!r}",
        flush=True,
    )
    assert original != changed
    assert text_has_ordered_subsequence(text, ["S", "NP", "VP", "V", "X"])
    assert not text_has_ordered_subsequence(text, ["S", "NP", "VP", "V", "NP"])
    assert text_has_ordered_subsequence(text, ["S", "NP", "VP"])


def test_trees_equal_iff_labels_and_children_match():
    with _empty_resources():
        left = _s_i_saw_him_constructed()
        right = _s_i_saw_him_constructed()
        other_leaf = _runtime_token()
        np_i = _tree_from_children("NP", ["I"])
        v_saw = _tree_from_children("V", ["saw"])
        np_other = _tree_from_children("NP", [other_leaf])
        vp = _tree_from_children("VP", [v_saw, np_other])
        leaf_changed = _tree_from_children("S", [np_i, vp])
        a = _runtime_symbol()
        b = _runtime_symbol(forbidden={a})
        c = _runtime_symbol(forbidden={a, b})
        x = _runtime_token()
        y = _runtime_token(forbidden={x})
        wrapper = _tree_from_children(
            a,
            [_tree_from_children(b, [_tree_from_children(c, [x]), y])],
        )
        siblings = _tree_from_children(
            a,
            [_tree_from_children(b, [x]), _tree_from_children(c, [y])],
        )
    print(
        f"same-structure equal={left == right} "
        f"leaf-changed equal={left == leaf_changed} "
        f"wrapper-vs-siblings equal={wrapper == siblings}",
        flush=True,
    )
    assert left == right
    assert left != leaf_changed
    assert wrapper != siblings
    assert constituent_leaves(wrapper) == [x, y]
    assert constituent_leaves(siblings) == [x, y]


def test_tree_length_is_immediate_child_count():
    n = 4
    leaves = [_runtime_token() for _ in range(n)]
    label = _runtime_symbol()
    with _empty_resources():
        s_tree = _s_i_saw_him_constructed()
        flat = _tree_from_children(label, leaves)
        empty = _tree_from_children(label, [])
    print(
        f"S children={tree_child_count(s_tree)} "
        f"flat n={n} children={tree_child_count(flat)} "
        f"empty children={tree_child_count(empty)}",
        flush=True,
    )
    assert tree_child_count(s_tree) == 2
    assert n != 2
    assert tree_child_count(flat) == n
    assert tree_child_count(empty) == 0


def test_s_i_saw_him_leaves_in_order():
    with _empty_resources():
        tree = _tree_from_bracketed(BRACKETED_S_I_SAW_HIM)
    leaves = constituent_leaves(tree)
    print(f"S-I-saw-him leaves={leaves!r}", flush=True)
    assert leaves == PUBLIC_LEAF_ORDER


def test_children_by_position_np_then_vp():
    with _empty_resources():
        tree = _tree_from_bracketed(BRACKETED_S_I_SAW_HIM)
        child0 = constituent_child_at(tree, 0)
        child1 = constituent_child_at(tree, 1)
    print(
        f"pos0 label={node_label(child0)!r} leaves={constituent_leaves(child0)!r} "
        f"pos1 label={node_label(child1)!r}",
        flush=True,
    )
    assert node_label(child0) == "NP"
    assert constituent_leaves(child0) == ["I"]
    assert node_label(child1) == "VP"


def test_runtime_bracketed_tree_equals_constructed():
    s = _runtime_symbol()
    np_lab = _runtime_symbol(forbidden={s})
    vp_lab = _runtime_symbol(forbidden={s, np_lab})
    v_lab = _runtime_symbol(forbidden={s, np_lab, vp_lab})
    inner = _runtime_symbol(forbidden={s, np_lab, vp_lab, v_lab})
    leaf0 = _runtime_token()
    leaf1 = _runtime_token(forbidden={leaf0})
    leaf2 = _runtime_token(forbidden={leaf0, leaf1})
    bracketed = (
        f"({s} ({np_lab} {leaf0}) "
        f"({vp_lab} ({v_lab} {leaf1}) ({inner} {leaf2})))"
    )
    print(f"runtime bracketed={bracketed}", flush=True)
    with _empty_resources():
        from_text = _tree_from_bracketed(bracketed)
        from_kids = _tree_from_children(
            s,
            [
                _tree_from_children(np_lab, [leaf0]),
                _tree_from_children(
                    vp_lab,
                    [
                        _tree_from_children(v_lab, [leaf1]),
                        _tree_from_children(inner, [leaf2]),
                    ],
                ),
            ],
        )
        relabelled = _tree_from_children(
            s,
            [
                _tree_from_children(np_lab, [leaf0]),
                _tree_from_children(
                    vp_lab,
                    [
                        _tree_from_children(v_lab, [leaf1]),
                        _tree_from_children(_runtime_symbol(forbidden={s, np_lab, vp_lab, v_lab, inner}), [leaf2]),
                    ],
                ),
            ],
        )
    assert from_text == from_kids
    assert from_text != relabelled


def test_runtime_pretty_print_and_children_by_position():
    s = _runtime_symbol()
    left_lab = _runtime_symbol(forbidden={s})
    right_lab = _runtime_symbol(forbidden={s, left_lab})
    inner_lab = _runtime_symbol(forbidden={s, left_lab, right_lab})
    repl = _runtime_symbol(forbidden={s, left_lab, right_lab, inner_lab})
    leaf0 = _runtime_token()
    leaf1 = _runtime_token(forbidden={leaf0})
    with _empty_resources():
        left = _tree_from_children(left_lab, [leaf0])
        inner = _tree_from_children(inner_lab, [leaf1])
        right = _tree_from_children(right_lab, [inner])
        tree = _tree_from_children(s, [left, right])
        text = pretty_printed_tree(tree)
        replaced_inner = _tree_from_children(repl, [leaf1])
        replaced_right = _tree_from_children(right_lab, [replaced_inner])
        replaced = _tree_from_children(s, [left, replaced_right])
        replaced_text = pretty_printed_tree(replaced)
        child0 = constituent_child_at(tree, 0)
        child1 = constituent_child_at(tree, 1)
    print(
        f"runtime pretty={text!r} replaced={replaced_text!r}",
        flush=True,
    )
    assert text_has_ordered_subsequence(text, [s, left_lab, right_lab, inner_lab])
    assert text_has_ordered_subsequence(text, [leaf0, leaf1])
    assert text_has_ordered_subsequence(
        replaced_text, [s, left_lab, right_lab, repl]
    )
    assert not text_has_ordered_subsequence(
        replaced_text, [s, left_lab, right_lab, inner_lab]
    )
    assert node_label(child0) == left_lab
    assert constituent_leaves(child0) == [leaf0]
    assert node_label(child1) == right_lab


# ---------------------------------------------------------------------------
# I. Tree construction refusals vs empty-child success
# ---------------------------------------------------------------------------


def test_tree_rejects_string_as_child_list():
    label = _runtime_symbol()
    with _empty_resources():
        refused = call(Tree, label, "not-children")
    classified = assert_tree_refused(refused)
    print(
        f"string-as-children label={label!r} "
        f"exc={classified.exception!r} value={classified.value!r}",
        flush=True,
    )


def test_tree_rejects_missing_child_list():
    label = _runtime_symbol()
    with _empty_resources():
        refused = call(Tree, label)
    classified = assert_tree_refused(refused)
    print(
        f"missing-child-list label={label!r} "
        f"exc={classified.exception!r} value={classified.value!r}",
        flush=True,
    )


def test_tree_empty_child_list_succeeds_and_differs_from_refusals():
    label = _runtime_symbol()
    with _empty_resources():
        empty = require_tree(call(Tree, label, []))
        string_refused = call(Tree, label, "not-children")
        missing_refused = call(Tree, label)
    print(
        f"empty-child label={node_label(empty)!r} "
        f"n={tree_child_count(empty)} leaves={constituent_leaves(empty)!r}",
        flush=True,
    )
    assert node_label(empty) == label
    assert tree_child_count(empty) == 0
    assert constituent_leaves(empty) == []
    require_tree_refused(string_refused)
    require_tree_refused(missing_refused)
