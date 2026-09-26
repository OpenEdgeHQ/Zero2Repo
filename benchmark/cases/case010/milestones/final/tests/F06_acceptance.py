# feature: F06
"""Text classification (FP-06).

Naive Bayes hard labels and ranked probabilities on the two-example
training; unseen feature names ignored; decision tree on the full
training featuresets; position-wise accuracy on a classifier-plus-gold
list and on two label lists; closed seen-label inventory; empty-of-
training-features still a trained label. Exception types, smoothing
constants, stump names, and empty-query polarity are not pinned.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

from lingora.classify import DecisionTreeClassifier, NaiveBayesClassifier
from lingora.classify import accuracy as classifier_gold_accuracy
from lingora.metrics import accuracy as two_list_accuracy

from _harness import call, workspace
from _helpers import (
    accuracy_number,
    bound_resource_path,
    classified_label,
    label_probability,
    listed_labels,
    require_accuracy_refused,
    require_label_probdist,
    require_trained_classifier,
)

PUBLIC_FEATURE_NAMES = frozenset({"nice", "good", "bad", "mean"})
PUBLIC_LABELS = frozenset({"positive", "negative"})

TWO_THIRDS = 2 / 3
ONE_THIRD = 1 / 3
ONE_HALF = 1 / 2


def _runtime_name(*, forbidden: set[str] | None = None, prefix: str = "x") -> str:
    blocked = set(forbidden or ())
    blocked.update(PUBLIC_FEATURE_NAMES)
    blocked.update(PUBLIC_LABELS)
    while True:
        name = prefix + uuid.uuid4().hex[:10]
        if name not in blocked:
            return name


def _runtime_features(n: int, *, forbidden: set[str] | None = None) -> list[str]:
    names: list[str] = []
    blocked = set(forbidden or ())
    for _ in range(n):
        name = _runtime_name(forbidden=blocked, prefix="feat")
        names.append(name)
        blocked.add(name)
    return names


def _runtime_labels(n: int, *, forbidden: set[str] | None = None) -> list[str]:
    names: list[str] = []
    blocked = set(forbidden or ())
    for _ in range(n):
        name = _runtime_name(forbidden=blocked, prefix="lab")
        names.append(name)
        blocked.add(name)
    return names


@contextmanager
def _empty_resources():
    """In-memory classification does not require packaged models."""
    with workspace() as ws:
        with bound_resource_path(ws, present=False):
            yield ws


def _train2():
    return [
        ({"nice": True, "good": True}, "positive"),
        ({"bad": True, "mean": True}, "negative"),
    ]


def _nice_only():
    return {"nice": True}


def _bad_only():
    return {"bad": True}


def _nice_and_good():
    return {"nice": True, "good": True}


def _bad_and_mean():
    return {"bad": True, "mean": True}


def _train_nb(labeled):
    return require_trained_classifier(
        call(NaiveBayesClassifier.train, list(labeled))
    )


def _train_dt(labeled):
    return require_trained_classifier(
        call(DecisionTreeClassifier.train, list(labeled))
    )


def _probdist(classifier, featureset):
    prob_fn = getattr(classifier, "prob_classify", None)
    if not callable(prob_fn):
        raise AssertionError(
            "classifier has no callable probability-distribution entry: "
            f"{type(classifier).__name__} {classifier!r}"
        )
    return require_label_probdist(call(prob_fn, featureset))


def _assert_strict_rank(dist, winner, loser) -> None:
    p_win = label_probability(dist, winner)
    p_lose = label_probability(dist, loser)
    print(
        f"rank {winner!r}={p_win!r} {loser!r}={p_lose!r}",
        flush=True,
    )
    assert p_win > p_lose, (
        f"probability of {winner!r} ({p_win!r}) is not strictly greater "
        f"than probability of {loser!r} ({p_lose!r})"
    )


def _assert_not_all_zero(dist, labels) -> None:
    probs = []
    for lab in labels:
        p = label_probability(dist, lab)
        probs.append(p)
        print(f"nonzero-check {lab!r}={p!r}", flush=True)
    assert any(p > 0 for p in probs), (
        f"every trained-label probability is zero: {list(zip(labels, probs))!r}"
    )


def _assert_closed_inventory(names, seen) -> None:
    seen_set = set(seen)
    print(f"inventory names={names!r} seen={sorted(seen_set)!r}", flush=True)
    for lab in seen_set:
        assert lab in names, f"listed labels missing trained label {lab!r}: {names!r}"
    for name in names:
        assert name in seen_set, (
            f"listed labels contain {name!r}, which was not a trained label; "
            f"seen={sorted(seen_set)!r}"
        )


# ---------------------------------------------------------------------------
# A. Naive Bayes nice-only / bad-only with ranked probabilities
# ---------------------------------------------------------------------------


def test_naive_bayes_nice_only_positive_bad_only_negative_with_ranked_probs():
    with _empty_resources():
        nb = _train_nb(_train2())
        nice = classified_label(nb, _nice_only())
        print(f"nice-only label={nice!r}", flush=True)
        assert nice == "positive"
        _assert_strict_rank(_probdist(nb, _nice_only()), "positive", "negative")

        bad = classified_label(nb, _bad_only())
        print(f"bad-only label={bad!r}", flush=True)
        assert bad == "negative"
        _assert_strict_rank(_probdist(nb, _bad_only()), "negative", "positive")

        swapped = (
            classified_label(nb, _bad_only()),
            classified_label(nb, _nice_only()),
        )
        print(f"swapped query labels={swapped!r}", flush=True)
        assert swapped == ("negative", "positive")
        assert swapped[0] != swapped[1]


def test_naive_bayes_runtime_features_and_labels_rank_and_swap():
    with _empty_resources():
        f1a, f1b, f2a, f2b = _runtime_features(4)
        lab1, lab2 = _runtime_labels(2)
        labeled = [
            ({f1a: True, f1b: True}, lab1),
            ({f2a: True, f2b: True}, lab2),
        ]
        print(
            f"runtime train feats={f1a!r}/{f1b!r} vs {f2a!r}/{f2b!r} "
            f"labels={lab1!r}/{lab2!r}",
            flush=True,
        )
        nb = _train_nb(labeled)
        q1 = {f1a: True}
        q2 = {f2a: True}
        got1 = classified_label(nb, q1)
        got2 = classified_label(nb, q2)
        print(f"runtime q1={got1!r} q2={got2!r}", flush=True)
        assert got1 == lab1
        assert got2 == lab2
        _assert_strict_rank(_probdist(nb, q1), lab1, lab2)
        _assert_strict_rank(_probdist(nb, q2), lab2, lab1)
        swapped = (classified_label(nb, q2), classified_label(nb, q1))
        print(f"runtime swapped={swapped!r}", flush=True)
        assert swapped == (lab2, lab1)
        assert swapped[0] != swapped[1]


# ---------------------------------------------------------------------------
# B. Unseen feature name is ignored
# ---------------------------------------------------------------------------


def test_naive_bayes_unseen_feature_does_not_flip_or_zero_all_probs():
    with _empty_resources():
        nb = _train_nb(_train2())
        baseline_nice = classified_label(nb, _nice_only())
        baseline_bad = classified_label(nb, _bad_only())
        print(
            f"live baseline nice-only={baseline_nice!r} bad-only={baseline_bad!r}",
            flush=True,
        )
        assert baseline_nice == "positive"
        assert baseline_bad == "negative"

        unseen = _runtime_name(
            forbidden=set(PUBLIC_FEATURE_NAMES),
            prefix="unseen",
        )
        print(f"unseen feature name={unseen!r}", flush=True)
        nice_plus = dict(_nice_only())
        nice_plus[unseen] = True
        bad_plus = dict(_bad_only())
        bad_plus[unseen] = True

        nice_got = classified_label(nb, nice_plus)
        print(f"nice-only+unseen label={nice_got!r}", flush=True)
        assert nice_got == "positive"
        _assert_not_all_zero(
            _probdist(nb, nice_plus),
            ("positive", "negative"),
        )

        bad_got = classified_label(nb, bad_plus)
        print(f"bad-only+unseen label={bad_got!r}", flush=True)
        assert bad_got == "negative"
        _assert_not_all_zero(
            _probdist(nb, bad_plus),
            ("positive", "negative"),
        )


# ---------------------------------------------------------------------------
# C. Decision tree on full training featuresets
# ---------------------------------------------------------------------------


def test_decision_tree_full_training_featuresets_positive_and_negative():
    with _empty_resources():
        dt = _train_dt(_train2())
        pos = classified_label(dt, _nice_and_good())
        neg = classified_label(dt, _bad_and_mean())
        print(f"dt nice-and-good={pos!r} bad-and-mean={neg!r}", flush=True)
        assert pos == "positive"
        assert neg == "negative"
        assert pos != neg


def test_decision_tree_runtime_full_featuresets_follow_training_labels():
    with _empty_resources():
        f1a, f1b, f2a, f2b = _runtime_features(4)
        lab1, lab2 = _runtime_labels(2)
        full1 = {f1a: True, f1b: True}
        full2 = {f2a: True, f2b: True}
        labeled = [(dict(full1), lab1), (dict(full2), lab2)]
        print(
            f"dt runtime full1={full1!r}->{lab1!r} full2={full2!r}->{lab2!r}",
            flush=True,
        )
        dt = _train_dt(labeled)
        got1 = classified_label(dt, full1)
        got2 = classified_label(dt, full2)
        print(f"dt runtime got1={got1!r} got2={got2!r}", flush=True)
        assert got1 == lab1
        assert got2 == lab2
        assert got1 != got2


# ---------------------------------------------------------------------------
# D. Accuracy: classifier+gold and two label lists
# ---------------------------------------------------------------------------


def test_accuracy_classifier_pos_pos_neg_against_pos_neg_neg_is_two_thirds():
    with _empty_resources():
        nb = _train_nb(_train2())
        pred = (
            classified_label(nb, _nice_only()),
            classified_label(nb, _nice_only()),
            classified_label(nb, _bad_only()),
        )
        print(f"classifier predictions={pred!r}", flush=True)
        assert pred == ("positive", "positive", "negative")
        gold = [
            (_nice_only(), "positive"),
            (_nice_only(), "negative"),
            (_bad_only(), "negative"),
        ]
        score = accuracy_number(call(classifier_gold_accuracy, nb, gold))
        print(f"classifier-path accuracy={score!r} expected={TWO_THIRDS!r}", flush=True)
        assert score == TWO_THIRDS


def test_accuracy_classifier_length_four_is_half():
    with _empty_resources():
        nb = _train_nb(_train2())
        pred = (
            classified_label(nb, _nice_only()),
            classified_label(nb, _nice_only()),
            classified_label(nb, _bad_only()),
            classified_label(nb, _bad_only()),
        )
        print(f"length-four predictions={pred!r}", flush=True)
        assert pred == ("positive", "positive", "negative", "negative")
        gold = [
            (_nice_only(), "positive"),
            (_nice_only(), "negative"),
            (_bad_only(), "positive"),
            (_bad_only(), "negative"),
        ]
        score = accuracy_number(call(classifier_gold_accuracy, nb, gold))
        print(f"classifier-path length-four accuracy={score!r}", flush=True)
        assert score == ONE_HALF
        assert score != TWO_THIRDS


def test_accuracy_classifier_same_bag_permutation_is_one_third():
    with _empty_resources():
        nb = _train_nb(_train2())
        pred = (
            classified_label(nb, _nice_only()),
            classified_label(nb, _nice_only()),
            classified_label(nb, _bad_only()),
        )
        print(f"same-bag predictions={pred!r}", flush=True)
        assert pred == ("positive", "positive", "negative")
        gold = [
            (_nice_only(), "positive"),
            (_nice_only(), "negative"),
            (_bad_only(), "positive"),
        ]
        score = accuracy_number(call(classifier_gold_accuracy, nb, gold))
        print(f"classifier-path same-bag accuracy={score!r}", flush=True)
        assert score == ONE_THIRD
        assert score != TWO_THIRDS


def test_accuracy_is_position_fraction_not_label_set_or_bag():
    with _empty_resources():
        predicted = ["positive", "positive", "negative"]
        gold_public = ["positive", "negative", "negative"]
        public = accuracy_number(call(two_list_accuracy, gold_public, predicted))
        print(f"two-list public triples={public!r}", flush=True)
        assert public == TWO_THIRDS

        gold_perm = ["positive", "negative", "positive"]
        permuted = accuracy_number(call(two_list_accuracy, gold_perm, predicted))
        print(f"two-list same-bag permutation={permuted!r}", flush=True)
        assert permuted == ONE_THIRD
        assert public != permuted


def test_accuracy_mismatched_lengths_does_not_succeed():
    with _empty_resources():
        predicted = ["positive", "positive", "negative"]
        gold_public = ["positive", "negative", "negative"]
        baseline = accuracy_number(call(two_list_accuracy, gold_public, predicted))
        print(f"live baseline equal-length accuracy={baseline!r}", flush=True)
        assert baseline == TWO_THIRDS

        lab_a, lab_b = _runtime_labels(2)
        equal = [lab_a, lab_b]
        equal_score = accuracy_number(call(two_list_accuracy, equal, list(equal)))
        print(
            f"runtime equal-length alphabet={lab_a!r}/{lab_b!r} score={equal_score!r}",
            flush=True,
        )
        assert equal_score == 1

        short = [lab_a]
        long = [lab_a, lab_b]
        print(
            f"mismatched lengths {len(short)} vs {len(long)} labels={short!r}/{long!r}",
            flush=True,
        )
        require_accuracy_refused(call(two_list_accuracy, short, long))
        require_accuracy_refused(call(two_list_accuracy, long, short))


def test_accuracy_runtime_lists_match_position_fraction():
    with _empty_resources():
        w1, w2, w3, w4, w5, w6 = _runtime_labels(6)
        left = [w1, w2, w3, w4]
        right = [w1, w5, w3, w6]
        print(f"runtime length-four left={left!r} right={right!r}", flush=True)
        assert len(left) == 4
        assert len(left) != 3
        score = accuracy_number(call(two_list_accuracy, left, right))
        print(f"runtime length-four accuracy={score!r}", flush=True)
        assert score == ONE_HALF
        assert score != TWO_THIRDS


# ---------------------------------------------------------------------------
# E. Closed label inventory and empty-of-training-features query
# ---------------------------------------------------------------------------


def test_naive_bayes_lists_seen_labels_and_not_an_unseen_third():
    with _empty_resources():
        nb = _train_nb(_train2())
        names = listed_labels(nb)
        _assert_closed_inventory(names, PUBLIC_LABELS)


def test_empty_of_training_features_returns_a_trained_label():
    with _empty_resources():
        nb = _train_nb(_train2())
        got = classified_label(nb, {})
        print(f"nb empty-featureset label={got!r}", flush=True)
        assert got in PUBLIC_LABELS


def test_decision_tree_empty_of_training_features_returns_a_trained_label():
    with _empty_resources():
        dt = _train_dt(_train2())
        got = classified_label(dt, {})
        print(f"dt empty-featureset label={got!r}", flush=True)
        assert got in PUBLIC_LABELS


def test_naive_bayes_runtime_label_inventory_and_empty_query():
    with _empty_resources():
        f1a, f1b, f2a, f2b = _runtime_features(4)
        lab1, lab2 = _runtime_labels(2)
        labeled = [
            ({f1a: True, f1b: True}, lab1),
            ({f2a: True, f2b: True}, lab2),
        ]
        print(f"runtime inventory labels={lab1!r}/{lab2!r}", flush=True)
        nb = _train_nb(labeled)
        names = listed_labels(nb)
        _assert_closed_inventory(names, {lab1, lab2})
        got = classified_label(nb, {})
        print(f"runtime empty-featureset label={got!r}", flush=True)
        assert got in {lab1, lab2}
