# feature: F07
"""Evaluation metrics (FP-07).

Levenshtein edit distance with substitution cost and optional
transpositions; Jaccard distance; two-list accuracy; precision, recall,
and equal-weight f-measure; BLEU of a candidate token list against one
or more reference token lists. Exception types, smoothing-function
values, and un-named gold scores are not pinned.
"""

from __future__ import annotations

import string
import uuid
from contextlib import contextmanager

from lingora.metrics import (
    accuracy as two_list_accuracy,
    edit_distance,
    f_measure,
    jaccard_distance,
    precision,
    recall,
)
from lingora.translate import bleu

from _harness import call, workspace
from _helpers import (
    accuracy_number,
    assert_no_score,
    bound_resource_path,
    require_accuracy_refused,
    require_no_score,
    score_number,
)

ONE_HALF = 1 / 2
TWO_THIRDS = 2 / 3

NAMED_EDIT_STRINGS = frozenset({"rain", "shine", "abc", "ca", "acbdef", "abcdef"})
NAMED_SET_ELEMENTS = frozenset({1, 2, 3, 4})
JOHN_LOVES_MARY = "John loves Mary"
GUIDE_CANDIDATE = (
    "It is a guide to action which ensures that the military "
    "always obeys the commands of the party"
)
POOR_CANDIDATE = (
    "It is to insure the troops forever hearing the activity "
    "guidebook that party direct"
)
GUIDE_REFERENCE_1 = (
    "It is a guide to action that ensures that the military "
    "will forever heed Party commands"
)
GUIDE_REFERENCE_2 = (
    "It is the guiding principle which guarantees the military "
    "forces always being under the command of the Party"
)
GUIDE_REFERENCE_3 = (
    "It is the practical guide for the army always to heed the "
    "directions of the party"
)
PAPINENI_SURFACE = frozenset(
    JOHN_LOVES_MARY.split()
    + GUIDE_CANDIDATE.split()
    + POOR_CANDIDATE.split()
    + GUIDE_REFERENCE_1.split()
    + GUIDE_REFERENCE_2.split()
    + GUIDE_REFERENCE_3.split()
)

UNIGRAM_WEIGHTS = [1]


@contextmanager
def _empty_resources():
    """Metrics are pure functions of caller arguments; no packaged models."""
    with workspace() as ws:
        with bound_resource_path(ws, present=False):
            yield ws


def _runtime_token(*, prefix: str = "t", forbidden: set[str] | None = None) -> str:
    blocked = set(forbidden or ())
    blocked.update(PAPINENI_SURFACE)
    while True:
        name = prefix + uuid.uuid4().hex[:10]
        if name not in blocked:
            return name


def _runtime_tokens(n: int, *, prefix: str = "t", forbidden: set[str] | None = None) -> list[str]:
    tokens: list[str] = []
    blocked = set(forbidden or ())
    for _ in range(n):
        name = _runtime_token(prefix=prefix, forbidden=blocked)
        tokens.append(name)
        blocked.add(name)
    return tokens


def _runtime_elements(n: int, *, prefix: str = "e") -> list[str]:
    return _runtime_tokens(n, prefix=prefix, forbidden={str(x) for x in NAMED_SET_ELEMENTS})


def _whitespace_tokens(text: str) -> list[str]:
    tokens = text.split()
    print(f"whitespace-split {text!r} -> {tokens!r} (n={len(tokens)})", flush=True)
    return tokens


def _runtime_letter_string(length: int, *, forbidden: set[str]) -> str:
    alphabet = list(string.ascii_lowercase)
    while True:
        chars: list[str] = []
        while len(chars) < length:
            ch = alphabet[int(uuid.uuid4().hex[:8], 16) % len(alphabet)]
            if ch not in chars:
                chars.append(ch)
        text = "".join(chars)
        if text not in forbidden:
            return text


def _adjacent_swap(text: str, index: int) -> str:
    chars = list(text)
    chars[index], chars[index + 1] = chars[index + 1], chars[index]
    return "".join(chars)


def _edit(
    left: str,
    right: str,
    *,
    substitution_cost: int,
    transpositions: bool,
    what: str,
) -> float:
    print(
        f"edit {left!r} vs {right!r} cost={substitution_cost} "
        f"transpositions={transpositions}",
        flush=True,
    )
    return score_number(
        call(
            edit_distance,
            left,
            right,
            substitution_cost=substitution_cost,
            transpositions=transpositions,
        ),
        what=what,
    )


# ---------------------------------------------------------------------------
# A. Edit distance
# ---------------------------------------------------------------------------


def test_edit_distance_rain_shine_substitution_cost_one_is_three_cost_two_is_five():
    with _empty_resources():
        cost_one = _edit(
            "rain",
            "shine",
            substitution_cost=1,
            transpositions=False,
            what="edit rain/shine cost 1",
        )
        print(f"rain/shine cost-1={cost_one!r}", flush=True)
        assert cost_one == 3

        cost_two = _edit(
            "rain",
            "shine",
            substitution_cost=2,
            transpositions=False,
            what="edit rain/shine cost 2",
        )
        print(f"rain/shine cost-2={cost_two!r}", flush=True)
        assert cost_two == 5
        assert cost_one != cost_two


def test_edit_distance_abc_ca_transpositions_off_three_on_two():
    with _empty_resources():
        off = _edit(
            "abc",
            "ca",
            substitution_cost=1,
            transpositions=False,
            what="edit abc/ca transpositions off",
        )
        print(f"abc/ca transpositions-off={off!r}", flush=True)
        assert off == 3

        on = _edit(
            "abc",
            "ca",
            substitution_cost=1,
            transpositions=True,
            what="edit abc/ca transpositions on",
        )
        print(f"abc/ca transpositions-on={on!r}", flush=True)
        assert on == 2
        assert off != on


def test_edit_distance_acbdef_abcdef_transpositions_off_two_on_one():
    with _empty_resources():
        off = _edit(
            "acbdef",
            "abcdef",
            substitution_cost=1,
            transpositions=False,
            what="edit acbdef/abcdef transpositions off",
        )
        print(f"acbdef/abcdef transpositions-off={off!r}", flush=True)
        assert off == 2

        on = _edit(
            "acbdef",
            "abcdef",
            substitution_cost=1,
            transpositions=True,
            what="edit acbdef/abcdef transpositions on",
        )
        print(f"acbdef/abcdef transpositions-on={on!r}", flush=True)
        assert on == 1
        assert off != on


def test_edit_distance_runtime_adjacent_transposition_off_two_on_one():
    with _empty_resources():
        forbidden = set(NAMED_EDIT_STRINGS)
        while True:
            base = _runtime_letter_string(6, forbidden=forbidden)
            index = int(uuid.uuid4().hex[:8], 16) % 5
            swapped = _adjacent_swap(base, index)
            if swapped not in forbidden and swapped != base:
                break
            forbidden.add(base)
        print(
            f"runtime adjacent-swap base={base!r} swapped={swapped!r} index={index}",
            flush=True,
        )
        assert len(base) == 6
        assert len(swapped) == 6
        assert base != swapped
        assert base not in NAMED_EDIT_STRINGS
        assert swapped not in NAMED_EDIT_STRINGS

        off = _edit(
            swapped,
            base,
            substitution_cost=1,
            transpositions=False,
            what="edit runtime adjacent transpositions off",
        )
        print(f"runtime adjacent transpositions-off={off!r}", flush=True)
        assert off == 2

        on = _edit(
            swapped,
            base,
            substitution_cost=1,
            transpositions=True,
            what="edit runtime adjacent transpositions on",
        )
        print(f"runtime adjacent transpositions-on={on!r}", flush=True)
        assert on == 1
        assert off != on


def test_edit_distance_identity_and_empty_is_zero():
    with _empty_resources():
        rain_self = _edit(
            "rain",
            "rain",
            substitution_cost=1,
            transpositions=False,
            what="edit rain vs itself",
        )
        print(f"rain vs rain={rain_self!r}", flush=True)
        assert rain_self == 0

        runtime = _runtime_token(prefix="id")
        print(f"runtime identity string={runtime!r}", flush=True)
        assert runtime
        runtime_self = _edit(
            runtime,
            runtime,
            substitution_cost=1,
            transpositions=False,
            what="edit runtime vs itself",
        )
        print(f"runtime vs itself={runtime_self!r}", flush=True)
        assert runtime_self == 0

        empty = _edit(
            "",
            "",
            substitution_cost=1,
            transpositions=False,
            what="edit two empty strings",
        )
        print(f"empty vs empty={empty!r}", flush=True)
        assert empty == 0


def test_edit_distance_rain_shine_is_symmetric():
    with _empty_resources():
        forward = _edit(
            "rain",
            "shine",
            substitution_cost=1,
            transpositions=False,
            what="edit rain then shine",
        )
        backward = _edit(
            "shine",
            "rain",
            substitution_cost=1,
            transpositions=False,
            what="edit shine then rain",
        )
        print(f"rain/shine={forward!r} shine/rain={backward!r}", flush=True)
        assert forward == 3
        assert backward == 3
        assert forward == backward


# ---------------------------------------------------------------------------
# B. Jaccard distance
# ---------------------------------------------------------------------------


def test_jaccard_identical_sets_are_zero():
    with _empty_resources():
        named = {1, 2, 3}
        named_score = score_number(
            call(jaccard_distance, named, set(named)),
            what="jaccard {1,2,3} vs itself",
        )
        print(f"jaccard named identical={named_score!r}", flush=True)
        assert named_score == 0

        elems = _runtime_elements(3)
        runtime = set(elems)
        print(f"runtime identical set={runtime!r}", flush=True)
        runtime_score = score_number(
            call(jaccard_distance, runtime, set(runtime)),
            what="jaccard runtime set vs itself",
        )
        print(f"jaccard runtime identical={runtime_score!r}", flush=True)
        assert runtime_score == 0


def test_jaccard_disjoint_nonempty_sets_are_one():
    with _empty_resources():
        elems = _runtime_elements(4)
        left = {elems[0], elems[1]}
        right = {elems[2], elems[3]}
        print(f"runtime disjoint {left!r} vs {right!r}", flush=True)
        assert left and right
        assert left.isdisjoint(right)
        score = score_number(
            call(jaccard_distance, left, right),
            what="jaccard runtime disjoint",
        )
        print(f"jaccard runtime disjoint={score!r}", flush=True)
        assert score == 1


def test_jaccard_one_two_three_versus_two_three_four_is_one_half():
    with _empty_resources():
        left = {1, 2, 3}
        right = {2, 3, 4}
        score = score_number(
            call(jaccard_distance, left, right),
            what="jaccard {1,2,3} vs {2,3,4}",
        )
        print(f"jaccard named overlapping={score!r}", flush=True)
        assert score == ONE_HALF
        assert score != 1
        assert score != 0


def test_jaccard_runtime_two_of_four_overlap_is_one_half():
    with _empty_resources():
        a, b, c, d = _runtime_elements(4)
        left = {a, b, c}
        right = {b, c, d}
        print(f"runtime two-of-four {left!r} vs {right!r}", flush=True)
        score = score_number(
            call(jaccard_distance, left, right),
            what="jaccard runtime two-of-four",
        )
        print(f"jaccard runtime two-of-four={score!r}", flush=True)
        assert score == ONE_HALF


# ---------------------------------------------------------------------------
# C. Two-list accuracy
# ---------------------------------------------------------------------------


def test_accuracy_one_two_three_versus_one_two_four_is_two_thirds():
    with _empty_resources():
        score = accuracy_number(call(two_list_accuracy, [1, 2, 3], [1, 2, 4]))
        print(f"accuracy [1,2,3] vs [1,2,4]={score!r}", flush=True)
        assert score == TWO_THIRDS


def test_accuracy_list_against_itself_is_one():
    with _empty_resources():
        named = accuracy_number(call(two_list_accuracy, [1, 2, 3], [1, 2, 3]))
        print(f"accuracy named triple vs itself={named!r}", flush=True)
        assert named == 1

        runtime = _runtime_elements(4)
        print(f"runtime self list n={len(runtime)} {runtime!r}", flush=True)
        assert len(runtime) != 3
        runtime_score = accuracy_number(call(two_list_accuracy, runtime, list(runtime)))
        print(f"accuracy runtime vs itself={runtime_score!r}", flush=True)
        assert runtime_score == 1


def test_accuracy_permutation_is_neither_one_nor_two_thirds():
    with _empty_resources():
        a, b, c = _runtime_elements(3)
        original = [a, b, c]
        self_score = accuracy_number(call(two_list_accuracy, original, list(original)))
        print(f"permutation live baseline self={self_score!r} list={original!r}", flush=True)
        assert self_score == 1

        permuted = [b, c, a]
        print(f"non-identity permutation {original!r} vs {permuted!r}", flush=True)
        assert permuted != original
        assert set(permuted) == set(original)
        score = accuracy_number(call(two_list_accuracy, original, permuted))
        print(f"accuracy permutation={score!r}", flush=True)
        assert score != 1


def test_accuracy_mismatched_lengths_does_not_succeed():
    with _empty_resources():
        baseline = accuracy_number(call(two_list_accuracy, [1, 2, 3], [1, 2, 4]))
        print(f"live baseline equal-length accuracy={baseline!r}", flush=True)
        assert baseline == TWO_THIRDS

        x, y = _runtime_elements(2)
        short = [x]
        long = [x, y]
        print(f"mismatched lengths {short!r} vs {long!r}", flush=True)
        require_accuracy_refused(call(two_list_accuracy, short, long))
        require_accuracy_refused(call(two_list_accuracy, long, short))


# ---------------------------------------------------------------------------
# D. Precision, recall, equal-weight f-measure
# ---------------------------------------------------------------------------


def test_precision_recall_fmeasure_named_sets_are_two_thirds():
    with _empty_resources():
        reference = {1, 2, 3}
        test = {2, 3, 4}
        prec = score_number(
            call(precision, reference, test),
            what="precision {1,2,3} vs {2,3,4}",
        )
        rec = score_number(
            call(recall, reference, test),
            what="recall {1,2,3} vs {2,3,4}",
        )
        fmeas = score_number(
            call(f_measure, reference, test),
            what="f-measure {1,2,3} vs {2,3,4}",
        )
        print(f"named precision={prec!r} recall={rec!r} f-measure={fmeas!r}", flush=True)
        assert prec == TWO_THIRDS
        assert rec == TWO_THIRDS
        assert fmeas == TWO_THIRDS


def test_precision_recall_runtime_two_of_three_cousin_is_two_thirds():
    with _empty_resources():
        a, b, c, d = _runtime_elements(4)
        reference = {a, b, c}
        test = {b, c, d}
        print(f"runtime two-of-three reference={reference!r} test={test!r}", flush=True)
        prec = score_number(
            call(precision, reference, test),
            what="precision runtime two-of-three",
        )
        rec = score_number(
            call(recall, reference, test),
            what="recall runtime two-of-three",
        )
        print(f"runtime two-of-three precision={prec!r} recall={rec!r}", flush=True)
        assert prec == TWO_THIRDS
        assert rec == TWO_THIRDS


def test_precision_recall_unequal_sizes_differ_from_two_thirds_and_each_other():
    with _empty_resources():
        a, b, c, d = _runtime_elements(4)
        reference = {a, b, c}
        test = {a, d}
        print(f"unequal-size reference={reference!r} test={test!r}", flush=True)
        assert len(reference) != len(test)
        prec = score_number(
            call(precision, reference, test),
            what="precision unequal-size overlap",
        )
        rec = score_number(
            call(recall, reference, test),
            what="recall unequal-size overlap",
        )
        fmeas = score_number(
            call(f_measure, reference, test),
            what="f-measure unequal-size overlap",
        )
        print(
            f"unequal-size precision={prec!r} recall={rec!r} f-measure={fmeas!r}",
            flush=True,
        )
        assert prec != TWO_THIRDS
        assert prec != 0
        assert prec != 1
        assert rec != TWO_THIRDS
        assert rec != 0
        assert rec != 1
        assert prec != rec
        assert fmeas != TWO_THIRDS


def test_empty_test_precision_is_absent_not_zero():
    with _empty_resources():
        reference = set(_runtime_elements(3))
        empty_test: set[str] = set()
        print(f"empty-test precision reference={reference!r}", flush=True)
        require_no_score(
            call(precision, reference, empty_test),
            what="precision nonempty vs empty test",
        )

        left, right = set(_runtime_elements(2)), set(_runtime_elements(2))
        print(f"disjoint f-measure contrast {left!r} vs {right!r}", flush=True)
        assert left and right
        assert left.isdisjoint(right)
        disjoint_f = score_number(
            call(f_measure, left, right),
            what="f-measure nonempty disjoint contrast",
        )
        print(f"nonempty disjoint f-measure={disjoint_f!r}", flush=True)
        assert disjoint_f == 0


def test_empty_reference_recall_is_absent():
    with _empty_resources():
        named_ref = {1, 2, 3}
        named_test = {2, 3, 4}
        baseline = score_number(
            call(recall, named_ref, named_test),
            what="recall nonempty baseline",
        )
        print(f"live baseline nonempty recall={baseline!r}", flush=True)
        assert baseline == TWO_THIRDS

        empty_reference: set[str] = set()
        test = set(_runtime_elements(3))
        print(f"empty-reference recall test={test!r}", flush=True)
        assert_no_score(
            call(recall, empty_reference, test),
            what="recall empty reference vs nonempty test",
        )


def test_fmeasure_absent_when_either_side_empty():
    with _empty_resources():
        left, right = set(_runtime_elements(2)), set(_runtime_elements(2))
        print(f"nonempty disjoint f-measure contrast {left!r} vs {right!r}", flush=True)
        assert left and right
        assert left.isdisjoint(right)
        disjoint_f = score_number(
            call(f_measure, left, right),
            what="f-measure nonempty disjoint contrast",
        )
        print(f"nonempty disjoint f-measure={disjoint_f!r}", flush=True)
        assert disjoint_f == 0

        nonempty = set(_runtime_elements(3))
        empty: set[str] = set()
        print(f"f-measure empty test, nonempty={nonempty!r}", flush=True)
        assert_no_score(
            call(f_measure, nonempty, empty),
            what="f-measure nonempty vs empty test",
        )
        print(f"f-measure empty reference, nonempty={nonempty!r}", flush=True)
        assert_no_score(
            call(f_measure, empty, nonempty),
            what="f-measure empty reference vs nonempty",
        )


def test_fmeasure_nonempty_disjoint_is_zero():
    with _empty_resources():
        left = set(_runtime_elements(2))
        right = set(_runtime_elements(2))
        print(f"runtime nonempty disjoint f-measure {left!r} vs {right!r}", flush=True)
        assert left and right
        assert left.isdisjoint(right)
        score = score_number(
            call(f_measure, left, right),
            what="f-measure runtime nonempty disjoint",
        )
        print(f"runtime nonempty disjoint f-measure={score!r}", flush=True)
        assert score == 0


def test_precision_recall_refuse_lists_and_other_non_sets():
    with _empty_resources():
        reference = {1, 2, 3}
        test = {2, 3, 4}
        baseline_p = score_number(
            call(precision, reference, test),
            what="precision set baseline",
        )
        baseline_r = score_number(
            call(recall, reference, test),
            what="recall set baseline",
        )
        print(f"set baseline precision={baseline_p!r} recall={baseline_r!r}", flush=True)
        assert baseline_p == TWO_THIRDS
        assert baseline_r == TWO_THIRDS

        listed_ref = [1, 2, 3]
        listed_test = [2, 3, 4]
        print(f"list precision/recall {listed_ref!r} vs {listed_test!r}", flush=True)
        require_no_score(
            call(precision, listed_ref, listed_test),
            what="precision on lists",
        )
        require_no_score(
            call(recall, listed_ref, listed_test),
            what="recall on lists",
        )

        tup_ref = (1, 2, 3)
        tup_test = (2, 3, 4)
        print(f"tuple precision {tup_ref!r} vs {tup_test!r}", flush=True)
        require_no_score(
            call(precision, tup_ref, tup_test),
            what="precision on tuples",
        )


# ---------------------------------------------------------------------------
# E. BLEU
# ---------------------------------------------------------------------------


def test_unigram_bleu_no_overlap_is_zero_identity_is_one():
    with _empty_resources():
        candidate = _whitespace_tokens(JOHN_LOVES_MARY)
        assert len(candidate) > 1
        assert len(candidate) == 3

        forbidden = set(candidate)
        reference = _runtime_tokens(3, prefix="uref", forbidden=forbidden)
        print(f"unigram no-overlap reference={reference!r}", flush=True)
        assert set(candidate).isdisjoint(set(reference))
        no_overlap = score_number(
            call(bleu, [reference], candidate, weights=UNIGRAM_WEIGHTS),
            what="unigram BLEU no overlap",
        )
        print(f"unigram no-overlap={no_overlap!r}", flush=True)
        assert no_overlap == 0

        identity = score_number(
            call(bleu, [list(candidate)], candidate, weights=UNIGRAM_WEIGHTS),
            what="unigram BLEU John loves Mary identity",
        )
        print(f"unigram identity John loves Mary={identity!r}", flush=True)
        assert identity == 1

        two = _runtime_tokens(2, prefix="u2")
        print(f"unigram two-token identity pair={two!r}", flush=True)
        two_id = score_number(
            call(bleu, [list(two)], two, weights=UNIGRAM_WEIGHTS),
            what="unigram BLEU two-token identity",
        )
        print(f"unigram two-token identity={two_id!r}", flush=True)
        assert two_id == 1


def test_default_four_weight_unsmoothed_two_token_identity_is_zero_to_four_decimals():
    with _empty_resources():
        pair = _runtime_tokens(2, prefix="b2")
        print(f"two-token identity pair={pair!r}", flush=True)
        assert len(pair) == 2

        unigram = score_number(
            call(bleu, [list(pair)], pair, weights=UNIGRAM_WEIGHTS),
            what="unigram BLEU two-token identity live baseline",
        )
        print(f"unigram two-token identity={unigram!r}", flush=True)
        assert unigram == 1

        default = score_number(
            call(bleu, [list(pair)], pair),
            what="default four-weight unsmoothed two-token identity",
        )
        print(f"default four-weight two-token identity={default!r}", flush=True)
        assert round(default, 4) == 0
        assert unigram != default


def test_bleu_guide_to_action_beats_insure_the_troops():
    with _empty_resources():
        guide = _whitespace_tokens(GUIDE_CANDIDATE)
        poor = _whitespace_tokens(POOR_CANDIDATE)
        references = [
            _whitespace_tokens(GUIDE_REFERENCE_1),
            _whitespace_tokens(GUIDE_REFERENCE_2),
            _whitespace_tokens(GUIDE_REFERENCE_3),
        ]
        assert len(guide) > 1
        assert len(poor) > 1
        for ref in references:
            assert len(ref) > 1

        guide_score = score_number(
            call(bleu, references, guide),
            what="BLEU guide-to-action candidate",
        )
        poor_score = score_number(
            call(bleu, references, poor),
            what="BLEU insure-the-troops candidate",
        )
        print(
            f"guide={guide_score!r} poor={poor_score!r}",
            flush=True,
        )
        assert 0 < guide_score < 1
        assert guide_score > poor_score
