# feature: F01
"""Observation helpers for the detector-command report (FP-01).

Every public observation goes through ``_harness.invoke``. Helpers locate
score, band, confidence, and character-layer counts by structure and
contrast, never by this checkout's metric key spellings.
"""

from __future__ import annotations

import ast
import json
import re
import socket
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Sequence

from _harness import (
    HarnessError,
    RunResult,
    invoke,
    workspace,
)

# ---------------------------------------------------------------------------
# Catalogue titles (PRD L100) and named splits (L96, L99, L102, L104)
# ---------------------------------------------------------------------------

CATALOGUE_TITLES: dict[int, str] = {
    1: "AI vocabulary",
    2: "model-dialect vocabulary",
    3: "promotional language",
    4: "hyphenated word-pair overuse",
    5: '"simple yet X" cliché',
    6: "stacked adjective chains",
    7: "rule of three overuse",
    8: "synonym cycling",
    9: "generic character naming in fiction",
    10: "significance inflation",
    11: "notability name-dropping",
    12: "vague attributions",
    13: "article-titles-as-proper-nouns",
    14: "conservation / ecosystem padding",
    15: "false ranges",
    16: "superficial -ing tail clauses",
    17: "negative parallelisms and tailing negations",
    18: '"Not X, just Y" / "No X, just Y"',
    19: "filler phrases",
    20: "empty pivot phrases",
    21: "outcome speculation tails",
    22: "persuasive authority tropes",
    23: "editorial interjections",
    24: "self-thoroughness phrases",
    25: "question-answer rhetorical pattern",
    26: '"concrete evidence" defense phrase',
    27: "compulsive intro hooks",
    28: "meandering intro",
    29: "prompt echo",
    30: "diff-anchored writing",
    31: "signposting and announcements",
    32: "cataloguing lead-ins",
    33: "inline-header vertical lists",
    34: "mid-essay bullet injection",
    35: "fragmented headers",
    36: "formulaic challenges sections",
    37: "transition cluster overuse",
    38: "compulsive conclusion phrases",
    39: "generic positive conclusions",
    40: "sentence-length monotony",
    41: "mechanical sentence-length alternation",
    42: "opener repetition",
    43: "avoidance of fragments and run-ons",
    44: "uniform paragraph length",
    45: "identical paragraph structure",
    46: "semicolon and parenthesis underuse",
    47: "chatbot artifacts",
    48: "sycophantic / servile tone",
    49: "RLHF / helpful-assistant register",
    50: "knowledge-cutoff disclaimers",
    51: "copula avoidance",
    52: "passive voice and subjectless fragments",
    53: "two-way passive-voice drift",
    54: "excessive hedging",
    55: "contraction absence",
    56: "boldface overuse",
    57: "emojis",
    58: "em-dash overuse",
    59: "title case in headings",
    60: "curly quotation marks",
    61: "hyphen-for-en-dash in numeric ranges",
    62: "invisible / zero-width characters",
    63: "placeholder / Mad-Libs text",
    64: "chatbot reference-markup leak",
    65: "AI tracking params",
    66: "homoglyph / mixed-script confusables",
    67: "non-standard spaces",
    68: "trailing / stray whitespace",
    69: "canonical marketing-slop phrases",
    70: "decorative horizontal rules",
    71: "degenerate repetition",
}

# Extra recognizers taken from the same PRD sentences that name the number
# (L99 parentheticals, L108 constructable names). Not product key spellings.
_CATALOGUE_ALIASES: dict[int, tuple[str, ...]] = {
    3: ("promotional language", "imperative marketing"),
    4: ("hyphenated cliché pairs", "hyphenated cliché", "hyphenated cliche"),
    5: ("simple yet X cliché", "simple yet"),
    13: ("article-title-as-proper-noun", "article-titles-as-proper-nouns"),
    15: ("false range", "false ranges"),
    16: ("superficial -ing tail clauses", "ing tail"),
    17: (
        "negative parallelism",
        "tailing negation",
        "tailing-negation",
        "negative parallelisms and tailing negations",
    ),
    18: ("Not X, just Y", "No X, just Y", "not x just y", "not x just y framing"),
    20: ("empty pivot phrase", "empty pivot phrases"),
    21: ("outcome speculation tail", "outcome-speculation tails"),
    22: ("persuasive authority tropes", "persuasive authority trope"),
    26: ("concrete evidence", "concrete-evidence"),
    27: ("compulsive intro hook", "compulsive intro hooks"),
    31: ("signposting and announcements", "signposting"),
    32: (
        "cataloguing lead-in",
        "cataloguing pivot",
        "cataloguing lead-ins",
        "definitional metaphor",
    ),
    33: ("inline-header vertical lists", "inline-header list", "inline-header"),
    36: ("formulaic challenges sections", "faux-insight"),
    37: ("transition cluster overuse", "colon reveal"),
    38: ("compulsive conclusion phrases", "compulsive conclusion phrase"),
    39: ("generic positive conclusion", "generic positive conclusions"),
    41: ("mechanical sentence-length alternation", "mechanical alternation"),
    47: ("chatbot artifacts", "chat residue"),
    48: ("sycophantic tone", "sycophantic / servile tone"),
    50: ("knowledge-cutoff disclaimer", "knowledge-cutoff disclaimers", "privacy filler"),
    54: ("hedge stacking", "excessive hedging"),
    55: ("contraction absence",),
    58: ("em-dash overuse",),
    60: ("curly quotation marks", "curly quotes"),
    61: ("hyphen-for-en-dash in numeric ranges", "hyphen-for-en-dash"),
    62: ("invisible / zero-width characters", "invisible character"),
    63: ("placeholder / Mad-Libs text", "placeholder text"),
    64: ("chatbot reference-markup leak",),
    65: ("AI tracking params",),
    66: ("homoglyph / mixed-script confusables", "mixed-script"),
    67: ("non-standard spaces",),
    68: ("trailing / stray whitespace", "trailing whitespace"),
    69: ("canonical marketing-slop phrases", "canonical marketing-slop phrase"),
}

NO_DETECTOR: frozenset[int] = frozenset({7, 9, 28, 29, 43, 45, 49, 52, 53})
WRITING_ADVICE: frozenset[int] = frozenset(
    {4, 19, 22, 41, 42, 46, 54, 55, 58, 60, 61, 68}
)
DECISIVE: frozenset[int] = frozenset({62, 63, 64, 65, 66, 13, 47, 50, 48})
RHYTHM_CLASS: frozenset[int] = frozenset({40, 41, 44, 55})
# L104 score-moving rhythm carrier. 41 and 55 are advice (weight zero).
RHYTHM_SCORE_MOVING: frozenset[int] = frozenset({40, 44})
BAND_RANGES: dict[str, tuple[int, int]] = {
    "clean": (0, 20),
    "light tells": (21, 40),
    "mixed": (41, 60),
    "heavy tells": (61, 80),
    "pervasive tells": (81, 100),
}
CONFIDENCE_LABELS: frozenset[str] = frozenset({"none", "low", "moderate", "high"})
SCAN_CAP = 262144

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "to",
        "for",
        "with",
        "as",
        "is",
        "it",
        "at",
        "by",
        "from",
    }
)

# Paths into a metrics object, bound by contrast (never hardcoded spellings).
_PATHS: dict[str, tuple] = {}
# Two-valued longer-than-window tokens, bound with the window-mark path.
_WINDOW_TOKENS: dict[str, Any] = {}
# Slots whose module-setup binding failed, with the reason. A test that reads
# such a slot fails with that reason; a test that never reads it is unaffected.
_BIND_FAILURES: dict[str, str] = {}
# Members of one finding object, bound by a known-multiplicity contrast.
_FINDING_KEYS: dict[str, Any] = {}

CORE_SLOTS: tuple[str, ...] = ("score", "band", "confidence", "scanned")


def _clear_bind_failures(*slots: str) -> None:
    for slot in slots:
        _BIND_FAILURES.pop(slot, None)


def _require_not_failed(*slots: str) -> None:
    """Fail the calling test when a slot it reads could not be bound.

    Raised inside the test body, so the test is reported as failed, never
    as passed, skipped, or a module-wide setup error.
    """
    for slot in slots:
        if slot in _BIND_FAILURES:
            raise HarnessError(
                f"{slot} could not be located at module setup: {_BIND_FAILURES[slot]}"
            )


@contextmanager
def binding(*slots: str) -> Iterator[None]:
    """Run one module-setup binding step for *slots*.

    A failure is recorded against those slots (and their stale bindings are
    dropped) instead of erroring every test in the module. Every helper that
    reads a failed slot then raises, so each dependent test fails.
    """
    _clear_bind_failures(*slots)
    try:
        yield
    except Exception as exc:  # noqa: BLE001 - recorded, re-raised per reader
        reason = f"{type(exc).__name__}: {exc}"
        for slot in slots:
            _PATHS.pop(slot, None)
            _BIND_FAILURES[slot] = reason
        if "window_mark" in slots:
            _WINDOW_TOKENS.clear()
        print(f"[bind] {slots!r} not bound: {reason[:600]}", flush=True)


# ---------------------------------------------------------------------------
# PRD-quoted probes plus runtime twins (anti-memorization)
# ---------------------------------------------------------------------------

SHORT_FACTUAL = (
    "Balsa is a fast-growing tree native to Central and South America. Its wood is "
    "light because the cells are large and thin-walled. A cubic metre of dried balsa "
    "weighs about 160 kilograms, roughly a fifth of oak."
)

SHORT_FACTUAL_TWIN = (
    "Oak is a slow-growing tree native to temperate northern forests. Its wood is "
    "dense because the cells are small and thick-walled. A cubic metre of dried oak "
    "weighs about eight hundred kilograms, far more than balsa."
)

SHORT_SLOP = (
    "In today's fast-paced world, leveraging cutting-edge solutions is essential. By "
    "fostering collaboration and driving innovation, teams unlock unprecedented value. "
    "Ultimately, the possibilities are endless."
)

SHORT_SLOP_TWIN = (
    "In this shifting digital landscape, showcasing robust solutions is essential. By "
    "fostering collaboration and elevating innovation, teams unlock unprecedented value. "
    "Ultimately, the possibilities are endless."
)

HUMANIZED_CODING = """\
AI coding assistants can make you faster at the boring parts. Not everything. Definitely not architecture.

They're great at boilerplate: config files, test scaffolding, repetitive refactors. They're also great at sounding right while being wrong. I've accepted suggestions that compiled, passed lint, and still missed the point because I stopped paying attention.

People I talk to land in two camps. Some use it like autocomplete for chores and review every line. Others disable it after it keeps suggesting patterns they don't want.
"""

AI_REGISTER = """\
Certainly! Below is an overview of the topic. Great question, by the way.

Urban beekeeping stands as a compelling testament to the transformative power of community stewardship, marking a pivotal chapter in how cities reimagine their relationship with the natural world. Across today's rapidly shifting urban landscape, these vibrant rooftop apiaries are reshaping how residents cultivate, harvest, and connect, underscoring their crucial role in a robust local food ecosystem.

At its core, the appeal is multifaceted: fostering biodiversity, empowering neighbourhoods, and unlocking a deeper appreciation of pollinators. It is not merely a hobby; it is a movement that leverages small spaces for outsized impact.

While specific details are limited based on available information, it could potentially possibly be argued that such initiatives might have some measurable benefit. Despite challenges typical of emerging practices, the community continues to thrive. In order to fully realize this potential, participants must align with established best practices.

In conclusion, the outlook is bright. Exciting times lie ahead as we delve deeper into this rewarding journey. Let me know if you would like me to expand on any section!
"""

OPENER_BLOCK = (
    "The system handles authentication. The system caches sessions for one "
    "hour after each successful login at the east quay office near the lock. "
    "The system rotates keys daily."
)

HEDGE_STACK = "The policy could possibly affect outcomes somewhat."

# Writing-advice probes (L19 / L99). Phrases are the named pattern kinds, not
# product key spellings.
HYPHENATED_CLICHE_PAIRS = (
    "The lock used cutting-edge hardware and a state-of-the-art gate."
)
FILLER_PHRASES = (
    "Due to the fact that the lock opened at dawn, crews stood by in order to pass the barges."
)
AUTHORITY_TROPES = (
    "At the end of the day the lock still opens and the bottom line is the gates meet the sill."
)
EM_DASH_OVERUSE = (
    "The lock — rebuilt after the flood — still opens at dawn — even in frost."
)
CURLY_QUOTES = (
    "The keeper said “the lock opened at dawn after the flood.”"
)
HYPHEN_NUMERIC_RANGE = (
    "The survey covers 2010-2015 along the eastern wall of the lock."
)
PARALLELISM_FORM_17 = (
    "The lock is not only a gate but also a measuring pond on the river."
)
# L108 / L126 named parallelism-form 17 fire. Distinct from catalogue 18.
RESIN_PARALLELISM_17 = (
    "It's not just about the resin holding the fibres in place; it's about "
    "how the laminate fails under load"
)
# Same prose with the parallelism phrasing removed (L108 / L126 score oracle).
RESIN_WITHOUT_PARALLELISM = (
    "The resin holding the fibres in place. How the laminate fails under load."
)
TAILING_NEGATION_17 = (
    "The joint is tight, no wasted motion in the crew's work."
)
# Same prose with the named comma-plus-"no wasted motion" tail removed (L108).
TAILING_NEGATION_WITHOUT = (
    "The joint is tight in the crew's work."
)
# Isolated AI-vocabulary in ordinary prose (L101). Short enough that adding
# the named chatbot-artifact probe takes the two-family floor of 25; the
# isolated integer itself is at most 40, not capped below 25.
ISOLATED_DELVE = (
    "They delve into the old parish records after the flood receded."
)
# L104 / L126 named three-sentence snow-and-road rhythm-only document.
SNOW_AND_ROAD = (
    "Snow covered the high passes. Trucks waited below the ridge. "
    "Crews cleared the road slowly."
)
CONTRACTABLE_OPINION = (
    "I am certain I have seen the lock and I will not pretend I cannot tell. "
    "I do not know the year and I am ready because I have time and I will wait and I cannot rush."
)
CONTRACTED_OPINION = (
    "I'm certain I've seen the lock and I won't pretend I can't tell. "
    "I don't know the year and I'm ready because I've time and I'll wait and I can't rush."
)
# L108 constructable fires: comma plus underscoring (16); TAG-block (62).
UNDERSCOPING_16 = "The beam sits true, underscoring the old scarf joint."
# Unicode TAG block (U+E0000–U+E007F) inside English prose. Not a product key.
TAG_BLOCK_62 = (
    "Hidden" + chr(0xE0041) + chr(0xE0049) + "word in English prose near the lock."
)
NOT_JUST_18 = (
    "It's not just a hobby, it's a craft. No fluff, just results on the quay."
)

PLACEHOLDER = "[Your Name]"
PLACEHOLDER_TWIN = "[INSERT EMAIL]"
TRACKING_URL = "https://example.com/post?utm_source=chatgpt.com"
TRACKING_URL_PERIOD = "https://x.com/a?utm_source=chatgpt.com."
TRACKING_URL_TWIN = "https://docs.example.net/note?utm_source=chatgpt.com"
TRACKING_OTHER_DOMAIN = "https://x.com/a?utm_source=chatgpt.com.au"

VOCAB_STACK = "delve tapestry pivotal showcase seamless"
# L108 named AI-vocabulary fire. One family; not a one-family integer cap
# below 25 and not a vocab-only exit from clean / light tells.
STACKED_VOCAB_FIRE = "They delve tapestry pivotal showcase seamless in one line."


# ---------------------------------------------------------------------------
# Structure walking
# ---------------------------------------------------------------------------


def _walk(obj: Any) -> Iterator[Any]:
    yield obj
    if isinstance(obj, Mapping):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            yield from _walk(value)


def _int_paths(obj: Any, prefix: tuple = ()) -> Iterator[tuple[tuple, int]]:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int):
        yield prefix, obj
        return
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _int_paths(value, prefix + (key,))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            yield from _int_paths(value, prefix + (index,))


def _str_paths(obj: Any, prefix: tuple = ()) -> Iterator[tuple[tuple, str]]:
    if isinstance(obj, str):
        yield prefix, obj
        return
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _str_paths(value, prefix + (key,))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            yield from _str_paths(value, prefix + (index,))


def _get_path(obj: Any, path: tuple) -> Any:
    cur = obj
    for part in path:
        try:
            cur = cur[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise HarnessError(f"metrics path {path!r} missing: {exc}") from exc
    return cur


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("'", "'").replace("'", "'")
    text = re.sub(r'["“”/_,:;!.?()\[\]{}]', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        tok
        for tok in _norm(text).split()
        if tok and tok not in _STOP and len(tok) > 1
    )


def catalogue_of(label: str) -> int | None:
    """Map a finding label to a catalogue number, or None if unrecognized."""
    if not isinstance(label, str) or not label.strip():
        return None
    nlab = _norm(label)
    ltoks = set(_tokens(label))
    hits: list[int] = []
    for number, title in CATALOGUE_TITLES.items():
        names = (title,) + _CATALOGUE_ALIASES.get(number, ())
        for name in names:
            nname = _norm(name)
            if not nname:
                continue
            if nlab == nname or nname in nlab or nlab in nname:
                hits.append(number)
                break
            ntoks = set(_tokens(name))
            if not ntoks or not ltoks:
                continue
            # Distinctive overlap: the shorter token set is covered by the longer.
            shorter, longer = (ntoks, ltoks) if len(ntoks) <= len(ltoks) else (ltoks, ntoks)
            if shorter <= longer and any(len(t) >= 4 for t in shorter):
                hits.append(number)
                break
    uniq = list(dict.fromkeys(hits))
    if len(uniq) == 1:
        return uniq[0]
    if not uniq:
        return None
    # Prefer the longest-title match when several numbers overlap.
    uniq.sort(key=lambda n: len(_norm(CATALOGUE_TITLES[n])), reverse=True)
    return uniq[0]


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


def _finding_entries(findings: Any) -> list[Any]:
    if isinstance(findings, Mapping):
        return list(findings.values())
    if isinstance(findings, list):
        return list(findings)
    raise HarnessError(
        f"findings are {type(findings).__name__}, not an object or list"
    )


def _finding_label(item: Any) -> str:
    if not isinstance(item, Mapping):
        raise HarnessError(f"finding is {type(item).__name__}, not an object")
    strings = [v for v in item.values() if isinstance(v, str)]
    mapped = [s for s in strings if catalogue_of(s) is not None]
    if len(mapped) == 1:
        label = mapped[0]
    elif len(strings) == 1:
        label = strings[0]
    elif mapped:
        label = mapped[0]
    else:
        raise HarnessError(f"finding has no human-readable label: {item!r}")
    if catalogue_of(label) is None:
        raise HarnessError(
            f"unrecognized finding label {label!r}; not a catalogue title"
        )
    return label


def _positive_int_keys(item: Mapping[str, Any]) -> dict[Any, int]:
    return {
        key: value
        for key, value in item.items()
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1
    }


def _str_list_keys(item: Mapping[str, Any]) -> dict[Any, list]:
    return {
        key: value
        for key, value in item.items()
        if isinstance(value, list) and all(isinstance(x, str) for x in value)
    }


# L101: “delve” plus “tapestry” are two hits of AI vocabulary (1). L108: the
# five-word stack fires the same family. More listed words, more hits.
_HIT_ARM_FEW = "They delve into the tapestry of the old parish records."
_HIT_ARM_MANY = (
    "They delve into the tapestry, a pivotal showcase of seamless parish records."
)
_HIT_ARM_FEW_HITS = 2
_HIT_ARM_MANY_HITS = 5


def _vocabulary_finding(text: str) -> Mapping[str, Any]:
    result = scan_stdin(text)
    if result.returncode != 0:
        raise HarnessError(
            f"hit-count probe failed: exit={result.returncode} "
            f"stderr={result.stderr_text[:300]!r}"
        )
    report = structured_report(result)
    metrics = metrics_from_report(report)
    matched = [
        item
        for item in _finding_entries(findings_from_report(report, metrics))
        if isinstance(item, Mapping) and catalogue_of(_finding_label(item)) == 1
    ]
    if len(matched) != 1:
        raise HarnessError(
            f"hit-count probe did not fire exactly one AI-vocabulary finding; "
            f"text={text!r} matched={matched!r}"
        )
    return matched[0]


def _bind_finding_keys() -> None:
    """Locate the hit-count member (and, if needed, the sample list) of a finding.

    Two AI-vocabulary probes differ only in how many listed words they hold.
    The hit count is the integer member that grows with that multiplicity; a
    catalogue number, a weight, or any other constant member does not.
    Encoding stays open: no member name is required.
    """
    if "hit" in _FINDING_KEYS:
        return
    if "error" in _FINDING_KEYS:
        raise HarnessError(_FINDING_KEYS["error"])
    try:
        few = _vocabulary_finding(_HIT_ARM_FEW)
        many = _vocabulary_finding(_HIT_ARM_MANY)
        few_ints = _positive_int_keys(few)
        many_ints = _positive_int_keys(many)
        grew = [k for k, v in many_ints.items() if k in few_ints and v > few_ints[k]]
        if len(grew) > 1:
            exact = [
                k
                for k in grew
                if few_ints[k] == _HIT_ARM_FEW_HITS and many_ints[k] == _HIT_ARM_MANY_HITS
            ]
            if exact:
                grew = exact
        if len(grew) > 1 and len({(few_ints[k], many_ints[k]) for k in grew}) == 1:
            grew = grew[:1]
        if len(grew) != 1:
            raise HarnessError(
                "cannot locate the finding hit count by contrast: members that grew "
                f"from {_HIT_ARM_FEW_HITS} to {_HIT_ARM_MANY_HITS} listed words: "
                f"{grew!r}; few={few!r} many={many!r}"
            )
        few_lists = _str_list_keys(few)
        many_lists = _str_list_keys(many)
        drawn = [
            k
            for k in many_lists
            if k in few_lists
            and many_lists[k] != few_lists[k]
            and all(
                set(_tokens(s)) & set(_tokens(_HIT_ARM_FEW)) for s in few_lists[k] if s.strip()
            )
            and all(
                set(_tokens(s)) & set(_tokens(_HIT_ARM_MANY)) for s in many_lists[k] if s.strip()
            )
        ]
        _FINDING_KEYS["hit"] = grew[0]
        if len(drawn) == 1:
            _FINDING_KEYS["samples"] = drawn[0]
        print(
            f"[F01] bound finding hit member={grew[0]!r} "
            f"sample member={_FINDING_KEYS.get('samples')!r}",
            flush=True,
        )
    except HarnessError as exc:
        _FINDING_KEYS["error"] = str(exc)
        raise


def _as_finding(item: Any) -> dict[str, Any]:
    label = _finding_label(item)
    str_lists = _str_list_keys(item)
    if len(str_lists) > 1:
        _bind_finding_keys()
        key = _FINDING_KEYS.get("samples")
        if key is None or key not in str_lists:
            raise HarnessError(
                f"finding has several string lists and none is bound as samples: {item!r}"
            )
        samples = str_lists[key]
    else:
        samples = next(iter(str_lists.values())) if str_lists else []
    if len(samples) > 3:
        raise HarnessError(
            f"sample list length {len(samples)} exceeds the cap of 3: {samples!r}"
        )
    positive = _positive_int_keys(item)
    if not positive:
        raise HarnessError(f"finding has no positive hit count: {item!r}")
    # The hit count is always the member bound by the multiplicity contrast,
    # so a lone catalogue number or weight is never read as a hit count.
    _bind_finding_keys()
    key = _FINDING_KEYS["hit"]
    if key not in positive:
        raise HarnessError(
            f"finding has no positive hit count at the bound member {key!r}: {item!r}"
        )
    hit = positive[key]
    return {"label": label, "hit": hit, "samples": samples, "raw": item}


def hit_count(finding: Any) -> int:
    if isinstance(finding, Mapping) and "hit" in finding and "raw" in finding:
        return int(finding["hit"])
    return int(_as_finding(finding)["hit"])


def sample_list(finding: Any) -> list[str]:
    if isinstance(finding, Mapping) and "samples" in finding and "raw" in finding:
        samples = finding["samples"]
        if not isinstance(samples, list) or len(samples) > 3:
            raise HarnessError(f"bad sample list: {samples!r}")
        return list(samples)
    return list(_as_finding(finding)["samples"])


def samples_drawn_from(samples: Sequence[str], text: str) -> None:
    """Each non-empty sample shares a content token with *text* after stripping
    ellipsis/punctuation. Not a contiguous-substring pin. An empty list is
    within the 'up to three' cap and is not a failure.
    """
    if not samples:
        return
    folded_tokens = set(_tokens(text))
    for sample in samples:
        assert isinstance(sample, str) and sample.strip(), f"sample is empty: {sample!r}"
        cleaned = sample.replace("\u2026", " ").replace("...", " ")
        toks = _tokens(cleaned)
        assert toks, (
            f"sample has no content tokens after stripping ellipsis/punctuation: {sample!r}"
        )
        assert any(tok in folded_tokens for tok in toks), (
            f"sample {sample!r} has no content token in the scanned text"
        )


def catalogue_numbers(findings: Any) -> set[int]:
    numbers: set[int] = set()
    for item in _finding_entries(findings):
        rec = _as_finding(item)
        number = catalogue_of(rec["label"])
        if number is None:
            raise HarnessError(f"unrecognized finding label {rec['label']!r}")
        numbers.add(number)
    return numbers


def _records(findings: Any) -> list[dict[str, Any]]:
    return [_as_finding(item) for item in _finding_entries(findings)]


def require_finding(findings: Any, number: int) -> dict[str, Any]:
    matched = [rec for rec in _records(findings) if catalogue_of(rec["label"]) == number]
    assert matched, (
        f"catalogue {number} ({CATALOGUE_TITLES[number]}) did not fire; "
        f"present={sorted(catalogue_numbers(findings))}"
    )
    return matched[0]


def require_absent_finding(findings: Any, number: int) -> None:
    matched = [rec for rec in _records(findings) if catalogue_of(rec["label"]) == number]
    assert not matched, (
        f"catalogue {number} ({CATALOGUE_TITLES[number]}) fired unexpectedly: "
        f"{matched[0]['label']!r}"
    )


def finding_records(findings: Any) -> list[dict[str, Any]]:
    """Public wrapper over finding records (label / hit / samples)."""
    return _records(findings)


def is_parallelism_form_17(label: str) -> bool:
    """True when *label* is the parallelism form of catalogue 17 (L99).

    L99 names that form as negative parallelism (writing advice). The
    tailing-negation form is a distinct label. A combined title that
    names both forms is not this form alone. Do not pin a sentence.
    """
    nlab = _norm(label)
    if not nlab:
        return False
    if "tailing" in nlab:
        return False
    if "negative parallelism" in nlab:
        return True
    if "negative parallelisms" in nlab and "tailing" not in nlab:
        return True
    return False


def score_moving_numbers(findings: Any) -> set[int]:
    """Catalogue numbers outside the twelve writing-advice numbers (L99).

    Catalogue 17 is not classified by label wording. Its two forms are
    told apart by which named input produced the finding and by whether
    the score moved.
    """
    return catalogue_numbers(findings) - WRITING_ADVICE


# ---------------------------------------------------------------------------
# Metrics: locate by type, range, and contrast
# ---------------------------------------------------------------------------


def band_of(metrics: Mapping[str, Any]) -> str:
    _require_not_failed("band")
    path = _PATHS.get("band")
    if path is not None:
        value = _get_path(metrics, path)
        if value not in BAND_RANGES:
            raise HarnessError(f"bound band path is not a band name: {value!r}")
        return str(value)
    found = [
        value
        for value in _walk(metrics)
        if isinstance(value, str) and value in BAND_RANGES
    ]
    uniq = list(dict.fromkeys(found))
    if len(uniq) != 1:
        raise HarnessError(f"band name not unique in metrics: {uniq!r}")
    return uniq[0]


def confidence_of(metrics: Mapping[str, Any]) -> str:
    _require_not_failed("confidence")
    path = _PATHS.get("confidence")
    if path is not None:
        value = _get_path(metrics, path)
        if value not in CONFIDENCE_LABELS:
            raise HarnessError(f"bound confidence path is not a label: {value!r}")
        return str(value)
    found = [
        value
        for value in _walk(metrics)
        if isinstance(value, str) and value in CONFIDENCE_LABELS
    ]
    uniq = list(dict.fromkeys(found))
    if len(uniq) != 1:
        raise HarnessError(f"confidence label not unique in metrics: {uniq!r}")
    return uniq[0]


def reason_of(metrics: Mapping[str, Any]) -> str:
    """Readable reason when confidence is not high. Do not pin wording."""
    conf = confidence_of(metrics)
    strings = [
        value
        for value in _walk(metrics)
        if isinstance(value, str)
        and value not in BAND_RANGES
        and value not in CONFIDENCE_LABELS
        and value.strip()
    ]
    if conf == "high":
        return strings[0] if strings else ""
    nonempty = [s for s in strings if s.strip()]
    if not nonempty:
        raise HarnessError(
            f"confidence {conf!r} has no readable reason in metrics"
        )
    return nonempty[0]


def scanned_of(metrics: Mapping[str, Any], *, chars: int | None = None) -> int:
    _require_not_failed("scanned")
    path = _PATHS.get("scanned")
    if path is not None:
        value = _get_path(metrics, path)
        if not isinstance(value, int) or isinstance(value, bool):
            raise HarnessError(f"bound scanned path is not an integer: {value!r}")
        if value > SCAN_CAP:
            raise HarnessError(f"scanned {value} exceeds the 262,144 cap")
        return value
    if chars is not None:
        expected = min(chars, SCAN_CAP)
        matches = [v for _, v in _int_paths(metrics) if v == expected]
        if not matches:
            raise HarnessError(
                f"metrics have no scanned count equal to {expected}"
            )
        return expected
    capped = [v for _, v in _int_paths(metrics) if v == SCAN_CAP]
    if capped:
        return SCAN_CAP
    raise HarnessError(
        "cannot locate scanned count without an input length or a bound path"
    )


def score_of(
    metrics: Mapping[str, Any],
    *,
    findings: Any | None = None,
) -> int:
    _require_not_failed("score")
    path = _PATHS.get("score")
    if path is not None:
        value = _get_path(metrics, path)
        if not isinstance(value, int) or isinstance(value, bool):
            raise HarnessError(f"bound score path is not an integer: {value!r}")
        if not 0 <= value <= 100:
            raise HarnessError(f"score {value} is outside 0–100")
        return value
    band = band_of(metrics)
    lo, hi = BAND_RANGES[band]
    excluded: set[int] = set()
    if findings is not None:
        excluded.add(len(_finding_entries(findings)))
        for rec in _records(findings):
            excluded.add(rec["hit"])
    candidates = []
    for _, value in _int_paths(metrics):
        if lo <= value <= hi and value not in excluded:
            candidates.append(value)
    uniq = set(candidates)
    if len(uniq) == 1:
        return next(iter(uniq))
    if not uniq and findings is not None:
        # Score may equal the finding count (both zero on a clean document).
        retry = [
            v for _, v in _int_paths(metrics) if lo <= v <= hi
        ]
        if set(retry) == {len(_finding_entries(findings))}:
            return len(_finding_entries(findings))
    raise HarnessError(
        f"cannot uniquely identify the 0–100 score in band {band!r}; "
        f"candidates={sorted(uniq)}"
    )


def finding_count_of(metrics: Mapping[str, Any], findings: Any) -> int:
    n = len(_finding_entries(findings))
    matches = [v for _, v in _int_paths(metrics) if v == n]
    if not matches:
        raise HarnessError(
            f"metrics have no fired-finding count equal to {n}"
        )
    return n


def assert_band_agrees_with_score(
    metrics: Mapping[str, Any], *, findings: Any | None = None
) -> None:
    band = band_of(metrics)
    score = score_of(metrics, findings=findings)
    lo, hi = BAND_RANGES[band]
    assert lo <= score <= hi, (
        f"band {band!r} does not contain score {score} (range {lo}–{hi})"
    )


def _bind_changed_int(
    slot: str,
    baseline: Mapping[str, Any],
    extra: Mapping[str, Any],
    *,
    exclude_values: Sequence[int] = (),
) -> None:
    """Bind the integer metric that counts the marks the extra arm adds.

    The two arms carry the same prose; only the extra arm holds the marks
    (L97 character layer). That count is 0 on the baseline, which has none of
    those marks, and positive on the extra arm. A word, sentence, or length
    tally is never 0 on non-empty prose, so a mark that also changes how
    words split cannot be taken for the count.
    """
    base = dict(_int_paths(baseline))
    nxt = dict(_int_paths(extra))
    skip = set(exclude_values)
    skip_paths = {
        _PATHS[name]
        for name in ("score", "scanned", "band", "confidence", "window_mark",
                     "invisible", "space", "mixed")
        if name in _PATHS and name != slot
    }
    moved: list[tuple] = []
    for path, extra_val in nxt.items():
        if path in skip_paths:
            continue
        base_val = base.get(path, 0)
        if not isinstance(extra_val, int) or isinstance(extra_val, bool):
            continue
        if extra_val in skip:
            continue
        if isinstance(base_val, bool) or base_val != 0:
            continue
        if extra_val > base_val:
            moved.append(path)
    uniq = list(dict.fromkeys(moved))
    if len(uniq) != 1:
        extra_vals = {nxt[path] for path in uniq}
        # Inserted marks can be counted on more than one integer field
        # (for example an in-word zero-width run). Same extra value is
        # still a unique observation of that count.
        if len(uniq) > 1 and len(extra_vals) == 1:
            uniq = [uniq[0]]
        else:
            raise HarnessError(
                f"cannot uniquely locate {slot} count by contrast; movers={uniq!r}"
            )
    _PATHS[slot] = uniq[0]
    _clear_bind_failures(slot)


def _count_from_path(slot: str, metrics: Mapping[str, Any]) -> int:
    _require_not_failed(slot)
    path = _PATHS.get(slot)
    if path is None:
        raise HarnessError(
            f"{slot} count is not bound; run the named contrast first"
        )
    value = _get_path(metrics, path)
    if not isinstance(value, int) or isinstance(value, bool):
        raise HarnessError(f"{slot} count is not an integer: {value!r}")
    return value


def invisible_count_of(metrics: Mapping[str, Any]) -> int:
    return _count_from_path("invisible", metrics)


def nonstandard_space_count_of(metrics: Mapping[str, Any]) -> int:
    return _count_from_path("space", metrics)


def mixed_script_count_of(metrics: Mapping[str, Any]) -> int:
    return _count_from_path("mixed", metrics)


def require_character_layer_counts(
    metrics: Mapping[str, Any],
) -> tuple[int, int, int]:
    """L97: metrics include the three character-layer counts.

    Counts are read from paths bound by the named K/J/I contrasts, not
    from this checkout's key names. Presence as integers is the pin;
    values are not compared across arms here (no sibling-count equality).
    """
    invisible = invisible_count_of(metrics)
    space = nonstandard_space_count_of(metrics)
    mixed = mixed_script_count_of(metrics)
    return invisible, space, mixed


def bind_invisible_count(
    baseline_metrics: Mapping[str, Any], extra_metrics: Mapping[str, Any]
) -> None:
    _bind_changed_int(
        "invisible",
        baseline_metrics,
        extra_metrics,
        exclude_values=_exclude_score_scanned(baseline_metrics, extra_metrics),
    )


def bind_nonstandard_space_count(
    baseline_metrics: Mapping[str, Any], extra_metrics: Mapping[str, Any]
) -> None:
    _bind_changed_int(
        "space",
        baseline_metrics,
        extra_metrics,
        exclude_values=_exclude_score_scanned(baseline_metrics, extra_metrics),
    )


def bind_mixed_script_count(
    baseline_metrics: Mapping[str, Any], extra_metrics: Mapping[str, Any]
) -> None:
    _bind_changed_int(
        "mixed",
        baseline_metrics,
        extra_metrics,
        exclude_values=_exclude_score_scanned(baseline_metrics, extra_metrics),
    )


def _exclude_score_scanned(
    baseline: Mapping[str, Any], extra: Mapping[str, Any]
) -> list[int]:
    out: list[int] = []
    for blob in (baseline, extra):
        # A bound score / scanned path is skipped by path; its value is only
        # excluded while the path is unknown.
        if "score" not in _PATHS:
            try:
                out.append(score_of(blob))
            except HarnessError:
                pass
        # Finding counts on these arms are small; character-layer tests insert
        # enough marks that the named count is larger than this band.
        out.extend(range(0, 4))
    return [n for n in out if n >= 0]


def _same_values(paths: Sequence[tuple], *blobs: Mapping[str, Any]) -> bool:
    """True when every path holds the same value in each of *blobs*."""
    for blob in blobs:
        try:
            values = {repr(_get_path(blob, path)) for path in paths}
        except HarnessError:
            return False
        if len(values) != 1:
            return False
    return True


def _band_strings(metrics: Mapping[str, Any]) -> set[str]:
    return {v for v in _walk(metrics) if isinstance(v, str) and v in BAND_RANGES}


def bind_core_metric_paths(
    low_metrics: Mapping[str, Any],
    high_metrics: Mapping[str, Any],
    *,
    none_metrics: Mapping[str, Any] | None = None,
    high_conf_metrics: Mapping[str, Any] | None = None,
    scanned_metrics: Mapping[str, Any] | None = None,
    scanned_chars: int | None = None,
    scanned_over_metrics: Mapping[str, Any] | None = None,
) -> None:
    """Locate score / band / confidence / scanned by PRD-named contrasts.

    A metric repeated under a second spelling (the same value in every arm)
    is one observation, not an ambiguity. Encoding stays open.
    """
    low_ints = dict(_int_paths(low_metrics))
    high_ints = dict(_int_paths(high_metrics))
    score_hits = []
    for path, high_val in high_ints.items():
        low_val = low_ints.get(path)
        if (
            isinstance(low_val, int)
            and isinstance(high_val, int)
            and not isinstance(low_val, bool)
            and 0 <= low_val <= 100
            and 0 <= high_val <= 100
            and high_val >= low_val + 20
        ):
            score_hits.append(path)
    if len(score_hits) > 1:
        # L98: the score sits inside the range of the band the same report names.
        in_band = []
        for path in score_hits:
            ok = True
            for blob, ints in ((low_metrics, low_ints), (high_metrics, high_ints)):
                bands = _band_strings(blob)
                if len(bands) != 1:
                    ok = False
                    break
                lo, hi = BAND_RANGES[next(iter(bands))]
                if not lo <= ints[path] <= hi:
                    ok = False
                    break
            if ok:
                in_band.append(path)
        if in_band:
            score_hits = in_band
    if len(score_hits) > 1 and _same_values(score_hits, low_metrics, high_metrics):
        score_hits = score_hits[:1]
    if len(score_hits) != 1:
        raise HarnessError(
            f"cannot uniquely locate the point score by the 20-point gap; "
            f"paths={score_hits!r}"
        )
    _PATHS["score"] = score_hits[0]

    low_band = band_of(low_metrics)
    # band_of without a path uses uniqueness; bind the path that differs.
    low_strs = dict(_str_paths(low_metrics))
    high_strs = dict(_str_paths(high_metrics))
    band_hits = []
    for path, high_val in high_strs.items():
        low_val = low_strs.get(path)
        if (
            low_val in BAND_RANGES
            and high_val in BAND_RANGES
            and low_val != high_val
        ):
            band_hits.append(path)
    if len(band_hits) > 1 and _same_values(band_hits, low_metrics, high_metrics):
        band_hits = band_hits[:1]
    if len(band_hits) != 1:
        # Same-band gap is allowed to leave a unique band string path.
        same = [
            path
            for path, val in high_strs.items()
            if val in BAND_RANGES and low_strs.get(path) in BAND_RANGES
        ]
        if len(same) > 1 and _same_values(same, low_metrics, high_metrics):
            same = same[:1]
        if len(same) == 1:
            band_hits = same
        else:
            raise HarnessError(f"cannot uniquely locate the band path: {band_hits!r}")
    _PATHS["band"] = band_hits[0]
    if low_band not in ("clean", "light tells"):
        raise HarnessError(f"factual arm band {low_band!r} is not clean/light tells")

    if none_metrics is not None and high_conf_metrics is not None:
        none_strs = dict(_str_paths(none_metrics))
        highc_strs = dict(_str_paths(high_conf_metrics))
        conf_hits = []
        for path, high_val in highc_strs.items():
            low_val = none_strs.get(path)
            if low_val == "none" and high_val == "high":
                conf_hits.append(path)
        if len(conf_hits) > 1 and _same_values(
            conf_hits, none_metrics, high_conf_metrics, low_metrics, high_metrics
        ):
            conf_hits = conf_hits[:1]
        if len(conf_hits) != 1:
            raise HarnessError(
                f"cannot uniquely locate confidence (none vs high): {conf_hits!r}"
            )
        _PATHS["confidence"] = conf_hits[0]

    if scanned_metrics is not None and scanned_chars is not None:
        expected = min(scanned_chars, SCAN_CAP)
        hits = [p for p, v in _int_paths(scanned_metrics) if v == expected]
        if len(hits) > 1 and scanned_over_metrics is not None:
            # L97 / L120: the scanned count is capped at 262,144 on an
            # over-window file; an uncapped length is not that count.
            over = dict(_int_paths(scanned_over_metrics))
            hits = [p for p in hits if over.get(p) == SCAN_CAP]
            if len(hits) > 1 and _same_values(hits, scanned_over_metrics):
                hits = hits[:1]
        if len(hits) > 1 and scanned_over_metrics is None:
            # Without an over-window arm the capped count cannot be told from
            # an uncapped length; scanned_of() then checks by value.
            _PATHS.pop("scanned", None)
            print(
                f"[F01] scanned count left unbound; candidates={hits!r}",
                flush=True,
            )
        elif len(hits) != 1:
            raise HarnessError(
                f"cannot uniquely locate scanned count {expected}: {hits!r}"
            )
        else:
            _PATHS["scanned"] = hits[0]
    _clear_bind_failures(*CORE_SLOTS)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _consider_bounds(lo: Any, hi: Any, score: int) -> tuple[float, float] | None:
    if not _is_number(lo) or not _is_number(hi):
        return None
    a, b = (float(lo), float(hi)) if lo <= hi else (float(hi), float(lo))
    if a <= score <= b:
        return (a, b)
    return None


def interval_pair(metrics: Mapping[str, Any], score: int) -> tuple[float, float] | None:
    """Return normalized low/high bounds that contain *score*, or None if omitted.

    The PRD names a low/high interval on the score, not a two-element sequence.
    Named numeric bounds are an interval. A nested mapping of two numbers is an
    interval. A numeric sequence is one encoding among those, not the required
    product shape. The returned 2-tuple is this helper's observation, not a pin
    on how the product spells the bounds.
    """
    named: list[tuple[float, float]] = []
    other: list[tuple[float, float]] = []
    bound_tokens_low = ("low", "min", "start", "lower", "lo")
    bound_tokens_high = ("high", "max", "end", "upper", "hi")

    def add(dest: list, pair: tuple[float, float] | None) -> None:
        if pair is not None:
            dest.append(pair)

    for value in _walk(metrics):
        if isinstance(value, Mapping):
            nums = {
                str(k): v
                for k, v in value.items()
                if _is_number(v)
            }
            lows = [
                v
                for k, v in nums.items()
                if any(tok in k.lower() for tok in bound_tokens_low)
            ]
            highs = [
                v
                for k, v in nums.items()
                if any(tok in k.lower() for tok in bound_tokens_high)
            ]
            for lo in lows:
                for hi in highs:
                    add(named, _consider_bounds(lo, hi, score))
            if not lows and not highs and len(nums) == 2:
                a, b = list(nums.values())
                add(other, _consider_bounds(a, b, score))
        if isinstance(value, (list, tuple)):
            nums_seq = [x for x in value if _is_number(x)]
            if len(nums_seq) >= 2:
                add(other, _consider_bounds(min(nums_seq), max(nums_seq), score))
    for group in (named, other):
        uniq = list(dict.fromkeys(group))
        if not uniq:
            continue
        if len(uniq) == 1:
            return uniq[0]
        uniq.sort(key=lambda p: (p[1] - p[0], p[0], p[1]))
        return uniq[0]
    return None


def interval_present(metrics: Mapping[str, Any], score: int) -> bool:
    """True when metrics carry a low/high interval containing *score*."""
    return interval_pair(metrics, score) is not None


def _yesno_value(value: Any) -> bool | None:
    """Interpret a truncated / yes-no mark. Encoding is open (L97, L120).

    A JSON/Python boolean counts. So does a string or other structured
    yes/no. Do not require this checkout's ``true``/``false`` spelling.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        n = value.strip().lower()
        if n in {"true", "yes", "on", "y", "1"}:
            return True
        if n in {"false", "no", "off", "n", "0"}:
            return False
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
    return None


def _yesno_paths(obj: Any, prefix: tuple = ()) -> Iterator[tuple[tuple, bool]]:
    yn = _yesno_value(obj)
    if yn is not None and not isinstance(obj, (Mapping, list, tuple)):
        yield prefix, yn
        return
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _yesno_paths(value, prefix + (key,))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            yield from _yesno_paths(value, prefix + (index,))


def bind_truncated_mark(
    at_metrics: Mapping[str, Any], over_metrics: Mapping[str, Any]
) -> None:
    """Locate the truncated mark by at-cap vs one-past contrast. Do not pin a key.

    The mark may be a boolean, a string, or another structured yes/no.
    """
    skip_paths = {
        _PATHS[name]
        for name in ("score", "scanned", "band", "confidence")
        if name in _PATHS
    }
    at_marks = {
        path: val
        for path, val in _yesno_paths(at_metrics)
        if path not in skip_paths
    }
    over_marks = {
        path: val
        for path, val in _yesno_paths(over_metrics)
        if path not in skip_paths
    }
    moved: list[tuple] = []
    for path, over_val in over_marks.items():
        at_val = at_marks.get(path, False)
        if over_val is True and at_val is not True:
            moved.append(path)
    uniq = list(dict.fromkeys(moved))
    if len(uniq) == 1:
        _PATHS["truncated"] = uniq[0]
        return
    if len(uniq) > 1:
        extra_vals = {over_marks[path] for path in uniq}
        if extra_vals == {True}:
            _PATHS["truncated"] = uniq[0]
            return
    at_rest = truncated_remainder(at_metrics)
    over_rest = truncated_remainder(over_metrics)
    if at_rest == over_rest:
        raise HarnessError(
            "metrics have no truncated mark when extracted prose exceeds 262,144"
        )
    _PATHS["truncated"] = ("__remainder__",)


def truncated_of(metrics: Mapping[str, Any]) -> bool:
    """Whether the bound truncated mark reads as yes (over-window) or no (at-cap).

    Encoding is open: boolean, string, or other structured yes/no. Not a
    JSON/Python-boolean pin.
    """
    path = _PATHS.get("truncated")
    if path is None:
        raise HarnessError(
            "truncated mark is not bound; run the at-cap vs one-past contrast first"
        )
    if path == ("__remainder__",):
        raise HarnessError(
            "truncated mark was bound only as a remainder; compare remainders instead"
        )
    value = _get_path(metrics, path)
    yn = _yesno_value(value)
    if yn is None:
        raise HarnessError(f"truncated mark is not a yes/no flag: {value!r}")
    return yn


def _scalar_paths(obj: Any, prefix: tuple = ()) -> Iterator[tuple[tuple, Any]]:
    """Leaf scalar paths. Mappings and sequences are walked, not yielded."""
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _scalar_paths(value, prefix + (key,))
        return
    if isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            yield from _scalar_paths(value, prefix + (index,))
        return
    yield prefix, obj


def _is_two_class_token(value: Any) -> bool:
    """True when *value* can be one side of a two-valued mark (L97).

    Booleans, yes/no-shaped strings, and 0/1 flags count. Growing leftover
    lengths and other unconstrained numbers do not.
    """
    if isinstance(value, bool):
        return True
    if isinstance(value, str) and value.strip():
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return value in (0, 1)
    return False


def bind_window_mark(
    at_metrics: Mapping[str, Any],
    over_metrics: Mapping[str, Any],
    extra_over_metrics: Mapping[str, Any],
    not_longer_metrics: Mapping[str, Any],
) -> None:
    """Locate the two-valued longer-than-window indication (L97 / L120 / L126).

    At-cap carries the “not longer” token; one character past carries the
    “longer” token. A second over-window file (different leftover length)
    must share that “longer” token, and a short file must share the
    “not longer” token. That is input-independence, not leftover inequality
    of other metrics, and not a required field name.
    """
    skip_paths = {
        _PATHS[name]
        for name in (
            "score",
            "scanned",
            "band",
            "confidence",
            "invisible",
            "space",
            "mixed",
        )
        if name in _PATHS
    }
    at_vals = {p: v for p, v in _scalar_paths(at_metrics) if p not in skip_paths}
    over_vals = {p: v for p, v in _scalar_paths(over_metrics) if p not in skip_paths}
    extra_vals = {
        p: v for p, v in _scalar_paths(extra_over_metrics) if p not in skip_paths
    }
    short_vals = {
        p: v for p, v in _scalar_paths(not_longer_metrics) if p not in skip_paths
    }
    candidates: list[tuple] = []
    for path, over_val in over_vals.items():
        if path not in at_vals or path not in extra_vals or path not in short_vals:
            continue
        at_val = at_vals[path]
        extra_val = extra_vals[path]
        short_val = short_vals[path]
        if at_val == over_val:
            continue
        # Leftover-length (0 vs 1 vs 2) is not two-valued.
        if extra_val != over_val:
            continue
        if short_val != at_val:
            continue
        distinct = [at_val, over_val]
        if extra_val not in distinct or short_val not in distinct:
            continue
        if extra_val == at_val or short_val == over_val:
            continue
        if not _is_two_class_token(at_val) or not _is_two_class_token(over_val):
            continue
        if not _is_two_class_token(extra_val) or not _is_two_class_token(short_val):
            continue
        candidates.append(path)
    uniq = list(dict.fromkeys(candidates))
    if not uniq:
        raise HarnessError(
            "metrics have no two-valued longer-than-window indication; "
            "leftover inequality of other metrics is not that mark"
        )
    path = uniq[0]
    _PATHS["window_mark"] = path
    _WINDOW_TOKENS["not_longer"] = at_vals[path]
    _WINDOW_TOKENS["longer"] = over_vals[path]
    _clear_bind_failures("window_mark")
    print(
        f"[F01] bound two-valued window mark path={path!r} "
        f"not_longer={at_vals[path]!r} longer={over_vals[path]!r} "
        f"n_candidates={len(uniq)}",
        flush=True,
    )


def window_mark_of(metrics: Mapping[str, Any]) -> Any:
    """Raw two-valued longer-than-window token. Encoding is open."""
    _require_not_failed("window_mark")
    path = _PATHS.get("window_mark")
    if path is None:
        raise HarnessError(
            "window mark is not bound; run the at-cap vs over-window contrast first"
        )
    return _get_path(metrics, path)


def window_is_longer(metrics: Mapping[str, Any]) -> bool:
    """True when *metrics* carry the bound “longer than window” token."""
    if "longer" not in _WINDOW_TOKENS:
        raise HarnessError("window mark tokens are not bound")
    return window_mark_of(metrics) == _WINDOW_TOKENS["longer"]


def window_is_not_longer(metrics: Mapping[str, Any]) -> bool:
    """True when *metrics* carry the bound “not longer than window” token."""
    if "not_longer" not in _WINDOW_TOKENS:
        raise HarnessError("window mark tokens are not bound")
    return window_mark_of(metrics) == _WINDOW_TOKENS["not_longer"]


def truncated_remainder(metrics: Mapping[str, Any]) -> Any:
    """Metrics with score, band, confidence, and scanned stripped (form-open)."""
    drop_paths = [
        _PATHS[name]
        for name in ("score", "band", "confidence", "scanned")
        if name in _PATHS
    ]
    drop_vals: list[Any] = []
    try:
        drop_vals.append(score_of(metrics))
    except HarnessError:
        pass
    try:
        drop_vals.append(band_of(metrics))
    except HarnessError:
        pass
    try:
        drop_vals.append(confidence_of(metrics))
    except HarnessError:
        pass
    try:
        drop_vals.append(scanned_of(metrics))
    except HarnessError:
        pass

    def strip(obj: Any, path: tuple = ()) -> Any:
        if path in drop_paths:
            return None
        if obj in drop_vals and not isinstance(obj, (list, dict)):
            return None
        if isinstance(obj, Mapping):
            return {k: strip(v, path + (k,)) for k, v in obj.items()}
        if isinstance(obj, list):
            return [strip(v, path + (i,)) for i, v in enumerate(obj)]
        return obj

    return strip(metrics)


def interval_omission_remainder(
    metrics: Mapping[str, Any], score: int | None = None
) -> Any:
    """Strip scanned / score / band / confidence and the interval pair.

    Leftover is the form-open too-few-sentences statement versus the
    present-interval statement. Do not search for the letters of 'sentence'.
    """
    rest = truncated_remainder(metrics)
    pair = interval_pair(metrics, score) if score is not None else None
    drop_nums: set[float] = set(pair) if pair is not None else set()

    def strip_pair(obj: Any) -> Any:
        if pair is not None and isinstance(obj, (list, tuple)):
            nums = [x for x in obj if _is_number(x)]
            if len(nums) >= 2:
                lo, hi = min(nums), max(nums)
                if (float(lo), float(hi)) == pair:
                    return None
        if _is_number(obj) and obj in drop_nums:
            return None
        if isinstance(obj, Mapping):
            return {k: strip_pair(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [strip_pair(v) for v in obj]
        return obj

    return strip_pair(rest)


def _string_states_too_few_sentences(text: str) -> bool:
    """True when *text* states that there are too few sentences (L111).

    Wording is open: do not pin this checkout's note. The statement's
    content is a scarcity of sentences, not any leftover string.
    """
    n = _norm(text)
    if not n:
        return False
    toks = set(n.split())
    scarcity = bool(
        toks
        & {
            "few",
            "fewer",
            "insufficient",
            "least",
            "short",
            "enough",
            "under",
        }
    ) or ("too few" in n) or ("not enough" in n) or ("less than" in n)
    unit = "sentence" in n
    return scarcity and unit


def _metrics_state_too_few_sentences(metrics: Mapping[str, Any]) -> bool:
    """True when metrics state there are too few sentences.

    Form is open: a readable string, or a nested structured mark
    (boolean, key spelling, serialized object) that carries that
    statement. A leftover inequality against other arms is not this
    statement. Interval-omitted (null bounds) is not this statement
    either.
    """
    skip = set(BAND_RANGES) | set(CONFIDENCE_LABELS)
    for value in _walk(metrics):
        if isinstance(value, str) and value.strip() and value not in skip:
            if _string_states_too_few_sentences(value):
                return True
    try:
        blob = json.dumps(metrics, default=str)
    except (TypeError, ValueError):
        blob = str(metrics)
    if _string_states_too_few_sentences(blob):
        return True

    def walk_kv(obj: Any) -> bool:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                joined = f"{key} {value}"
                if _string_states_too_few_sentences(joined):
                    return True
                if walk_kv(value):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if walk_kv(item):
                    return True
        return False

    return walk_kv(metrics)


def too_few_sentences_stated(metrics: Mapping[str, Any]) -> None:
    """L111: when the interval is omitted, metrics state there are too few sentences.

    Assert the statement on the omitted-interval arm. Do not treat a
    leftover-string inequality against the switch-off or ≥4-sentence
    arms as that statement. Encoding of the statement is open (string
    or other structured mark).
    """
    stated = _metrics_state_too_few_sentences(metrics)
    assert stated, (
        "metrics do not state that there are too few sentences when the "
        "interval is omitted"
    )
    print("[F01] omitted-interval arm states too few sentences", flush=True)


def advice_does_not_move_score(base: str, extra: str, number: int) -> set[int]:
    """Extra arm reports writing-advice *number* and does not move the score.

    *number* must appear on the extra arm (positive carrier). Score-moving
    families stay equal to the base, and the point score is unchanged.
    Returns the writing-advice numbers that fired on the extra arm.
    """
    b_f, b_m = require_success_report(scan_stdin(base), input_chars=unicode_len(base))
    e_f, e_m = require_success_report(scan_stdin(extra), input_chars=unicode_len(extra))
    require_finding(e_f, number)
    present = sorted(catalogue_numbers(e_f))
    print(
        f"[F01] advice {number} extra fired={present}",
        flush=True,
    )
    moving_b = score_moving_numbers(b_f)
    moving_e = score_moving_numbers(e_f)
    print(
        f"[F01] advice {number} moving_b={sorted(moving_b)} moving_e={sorted(moving_e)}",
        flush=True,
    )
    assert moving_b == moving_e, (
        f"writing-advice {number} changed the score-moving family set: "
        f"{sorted(moving_b)} -> {sorted(moving_e)}"
    )
    b_score = score_of(b_m, findings=b_f)
    e_score = score_of(e_m, findings=e_f)
    assert b_score == e_score, (
        f"writing-advice {number} moved the score from {b_score} to {e_score}"
    )
    return catalogue_numbers(e_f) & WRITING_ADVICE


def hold_parallelism_form_17_as_advice(findings: Any) -> bool:
    """Parallelism form of catalogue 17 is writing advice (L99).

    The form is identified by the finding label (negative parallelism,
    not tailing negation). This does not pin a sentence as the fire.
    When that form is present and no tailing-form 17 finding is also
    present, it must not be treated as score-moving. Returns True when
    the parallelism form was among *findings*.
    """
    recs = [
        rec
        for rec in finding_records(findings)
        if is_parallelism_form_17(rec["label"])
    ]
    if not recs:
        return False
    moving = score_moving_numbers(findings)
    tailing = [
        rec
        for rec in finding_records(findings)
        if catalogue_of(rec["label"]) == 17 and not is_parallelism_form_17(rec["label"])
    ]
    print(
        f"[F01] parallelism-form 17 labels={[rec['label'] for rec in recs]!r} "
        f"moving={sorted(moving)} tailing_also={bool(tailing)}",
        flush=True,
    )
    if 17 in moving and not tailing:
        raise AssertionError("parallelism form of 17 is treated as score-moving")
    return True


def writing_advice_findings_do_not_move_score(
    findings: Any, metrics: Mapping[str, Any], *, base_score: int, base_moving: set[int]
) -> set[int]:
    """Writing-advice findings appear and count for nothing (L19, L99).

    Every fired writing-advice number is excluded from the score-moving
    set. If the extra arm added no score-moving family, the point score
    is unchanged. Does not pin which listed number must fire.
    """
    advice = catalogue_numbers(findings) & WRITING_ADVICE
    moving = score_moving_numbers(findings)
    extra_moving = moving - base_moving
    if extra_moving:
        raise AssertionError(
            f"writing-advice extra added score-moving families {sorted(extra_moving)}"
        )
    score = score_of(metrics, findings=findings)
    if score != base_score:
        raise AssertionError(
            f"writing-advice findings moved the score from {base_score} to {score}"
        )
    for rec in finding_records(findings):
        number = catalogue_of(rec["label"])
        if number in WRITING_ADVICE and number in moving:
            raise AssertionError(
                f"writing-advice {number} is treated as score-moving"
            )
    return advice


def hold_advice_if_present(base: str, extra: str) -> set[int]:
    """L19 / L99: leftover writing-advice numbers, when they fire, do not move the score.

    Not a must-fire table: *extra* may use an L99-named kind without
    requiring that catalogue number. Observation is the point score, not
    set-membership in ``score_moving_numbers`` (that set already excludes
    the twelve). If *extra* added a score-moving family, the arm is
    skipped rather than pinned as that family's fire.
    """
    b_f, b_m = require_success_report(scan_stdin(base), input_chars=unicode_len(base))
    e_f, e_m = require_success_report(scan_stdin(extra), input_chars=unicode_len(extra))
    extra_moving = score_moving_numbers(e_f) - score_moving_numbers(b_f)
    advice = catalogue_numbers(e_f) & WRITING_ADVICE
    present = sorted(catalogue_numbers(e_f))
    print(
        f"[F01] advice-if-present fired={present} extra_moving={sorted(extra_moving)}",
        flush=True,
    )
    if extra_moving:
        return set()
    b_score = score_of(b_m, findings=b_f)
    e_score = score_of(e_m, findings=e_f)
    if b_score != e_score:
        raise AssertionError(
            f"writing-advice extra moved the score from {b_score} to {e_score} "
            f"with no added score-moving family; advice={sorted(advice)}"
        )
    return advice


# ---------------------------------------------------------------------------
# Success / failure carriers
# ---------------------------------------------------------------------------


def parse_structured_mapping(text: str, *, source: str) -> dict[str, Any]:
    """Read *text* as a structured mapping. Encoding is the implementer's.

    Raises :class:`HarnessError` if *text* is empty or is not a mapping.
    Never returns ``{}`` to mean the parse failed.
    """
    stripped = text.strip()
    if not stripped:
        raise HarnessError(f"{source} is empty; expected a structured record")
    candidates: list[Any] = []
    try:
        candidates.append(json.loads(stripped))
    except json.JSONDecodeError:
        pass
    try:
        candidates.append(ast.literal_eval(stripped))
    except (ValueError, SyntaxError, MemoryError):
        pass
    for obj in candidates:
        if isinstance(obj, dict):
            return obj
    excerpt = stripped if len(stripped) <= 500 else stripped[:500] + "…"
    raise HarnessError(
        f"{source} is not a structured object; text={excerpt!r}"
    )


def _has_band_or_confidence(obj: Mapping[str, Any]) -> bool:
    for value in _walk(obj):
        if isinstance(value, str) and value in BAND_RANGES:
            return True
        if isinstance(value, str) and value in CONFIDENCE_LABELS:
            return True
    return False


def _is_finding_like(item: Any) -> bool:
    if not isinstance(item, Mapping):
        return False
    strings = [v for v in item.values() if isinstance(v, str)]
    if any(catalogue_of(s) is not None for s in strings):
        return True
    lists = [v for v in item.values() if isinstance(v, list)]
    ints = [v for v in item.values() if _is_number(v) and int(v) == v]
    str_lists = [lst for lst in lists if lst and all(isinstance(x, str) for x in lst)]
    return bool(str_lists) and bool(ints)


def metrics_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Locate the metrics object by band/confidence content, not by a key spelling."""
    if not isinstance(report, Mapping):
        raise HarnessError(
            f"structured report is {type(report).__name__}, not an object"
        )
    nested = [v for v in report.values() if isinstance(v, Mapping)]
    with_labels = [m for m in nested if _has_band_or_confidence(m)]
    if len(with_labels) == 1:
        return with_labels[0]
    if _has_band_or_confidence(report) and not with_labels:
        return dict(report)
    if len(with_labels) > 1:
        # Prefer the nested mapping that is not itself a finding.
        not_findings = [m for m in with_labels if not _is_finding_like(m)]
        if len(not_findings) == 1:
            return not_findings[0]
        raise HarnessError("structured report has several metrics objects")
    if len(nested) == 1:
        return nested[0]
    raise HarnessError("structured report has no metrics object")


def findings_from_report(report: Mapping[str, Any], metrics: Mapping[str, Any]) -> Any:
    """Locate finding entries by catalogue labels, not by a key-prefix rule."""
    if not isinstance(report, Mapping):
        raise HarnessError(
            f"structured report is {type(report).__name__}, not an object"
        )
    entries: dict[str, Any] = {}
    for key, value in report.items():
        if value is metrics:
            continue
        if isinstance(value, Mapping) and value == metrics and not _is_finding_like(value):
            continue
        if _is_finding_like(value):
            entries[str(key)] = value
            continue
        if isinstance(value, list) and value and all(_is_finding_like(x) for x in value):
            for index, item in enumerate(value):
                entries[f"{key}:{index}"] = item
    return entries


def structured_report(result: RunResult) -> dict[str, Any]:
    """Parse detector stdout as a structured report (findings plus metrics)."""
    try:
        return parse_structured_mapping(result.stdout_text, source="detector stdout")
    except HarnessError as exc:
        raise HarnessError(
            f"{exc}; exit={result.returncode}; stderr={result.stderr_text!r}"
        ) from exc


def structured_error_mapping(result: RunResult) -> dict[str, Any]:
    """The error stream as a structured mapping (L115–L117).

    A nonempty unstructured line is not this carrier. Do not require
    JSON or a field named ``error``: any structured mapping counts.
    Raises ``AssertionError`` so a missing structure fails the test,
    not the harness.
    """
    text = result.stderr_text
    assert text.strip(), (
        f"error stream is empty; expected a structured error; "
        f"exit={result.returncode}; stdout={result.stdout_text!r}"
    )
    try:
        obj = parse_structured_mapping(text, source="detector stderr")
        parse_err = None
    except HarnessError as exc:
        obj = None
        parse_err = exc
    assert parse_err is None, f"error stream is not a structured error: {parse_err}"
    assert isinstance(obj, dict), (
        f"error stream is not a structured mapping: {type(obj).__name__}"
    )
    return obj


def failure_record(result: RunResult) -> str:
    """Return the structured error-stream record.

    L115–L117 require a structured error on the error stream. A nonempty
    unstructured line is not that record. Do not require JSON or a field
    named ``error``: any structured mapping is the carrier.
    """
    obj = structured_error_mapping(result)
    parts: list[str] = []
    for value in _walk(obj):
        if isinstance(value, str) and value.strip():
            parts.append(value)
    if parts:
        return " ".join(parts)
    return str(obj)


def error_points_toward_help(record: str, usage: str) -> None:
    """Unknown-option errors point at help (L117). Do not require the letters 'help'.

    Usage is not required to list ``--help`` / ``-h`` (L118 names cleanup,
    interval, the double-dash, and the file operand). If usage happens to
    name a help request and the error echoes it, that is one carrier; the
    fallback is token overlap with the usage message.
    """
    tokens: tuple[str, ...] = ()
    try:
        tokens = help_requests_from_usage(usage)
    except HarnessError:
        tokens = ()
    rec_toks = set(_tokens(record))
    use_toks = set(_tokens(usage))
    overlap = {t for t in (rec_toks & use_toks) - _STOP if len(t) >= 4}
    echoed = any(token and token in record for token in tokens)
    assert echoed or overlap, (
        "unknown-option structured error does not point at help / usage"
    )


def _looks_like_frames(text: str) -> bool:
    """True when the stream carries a multi-frame dump. Do not search 'Traceback'."""
    lines = text.splitlines()
    frameish = 0
    for line in lines:
        if re.match(r"\s+File\s+", line):
            frameish += 1
        elif re.match(r"\s+at\s+\S+", line):
            frameish += 1
        elif re.match(r"\s+\^+\s*$", line):
            frameish += 1
    return frameish >= 2


def require_no_traceback(result: RunResult) -> None:
    """The entire error stream must not be a traceback / multi-frame dump."""
    text = result.stderr_text
    stripped = text.strip()
    obj: Any = None
    if stripped:
        try:
            obj = parse_structured_mapping(stripped, source="detector stderr")
        except HarnessError:
            obj = None
        if isinstance(obj, dict):
            assert not _looks_like_frames(text), (
                f"error stream mixes a dump with a structured object: {text!r}"
            )
            return
    assert not _looks_like_frames(text), (
        f"error stream is a multi-frame dump: {text!r}"
    )


def require_success_report(
    result: RunResult, *, input_chars: int | None = None
) -> tuple[Any, dict[str, Any]]:
    assert result.returncode == 0, (
        f"expected success, got exit {result.returncode}; "
        f"stderr={result.stderr_text!r}"
    )
    report = structured_report(result)
    metrics = metrics_from_report(report)
    findings = findings_from_report(report, metrics)
    band = band_of(metrics)
    conf = confidence_of(metrics)
    if conf != "high":
        reason = reason_of(metrics)
        assert str(reason).strip(), "non-high confidence has an empty reason"
    scanned = scanned_of(metrics, chars=input_chars)
    if scanned > SCAN_CAP:
        raise HarnessError(f"scanned {scanned} exceeds the cap")
    finding_count_of(metrics, findings)
    score: int | None = None
    if "score" in _PATHS:
        score = score_of(metrics, findings=findings)
        assert_band_agrees_with_score(metrics, findings=findings)
    # L97: once the three character-layer counts are located by contrast,
    # every later success report must still include them.
    if {"invisible", "space", "mixed"} <= set(_PATHS):
        require_character_layer_counts(metrics)
    print(
        f"[F01] success score={score} band={band!r} confidence={conf!r} "
        f"scanned={scanned} n_findings={len(_finding_entries(findings))}",
        flush=True,
    )
    assert findings is not None
    assert metrics is not None
    return findings, metrics


def require_structured_failure(result: RunResult) -> str:
    assert result.returncode != 0, (
        f"expected failing status, got success; stdout={result.stdout_text!r}"
    )
    require_no_traceback(result)
    err = failure_record(result)
    if result.stdout.strip():
        printed_success = True
        try:
            structured_report(result)
        except HarnessError:
            printed_success = False
        assert not printed_success, (
            "failure printed a structured success report on stdout"
        )
    print(
        f"[F01] failure exit={result.returncode} error={err!r}",
        flush=True,
    )
    return err


def strip_error_covariates(record: str, *tokens: str) -> str:
    text = record
    for token in tokens:
        if not token:
            continue
        text = text.replace(token, "")
        text = text.replace(json.dumps(token)[1:-1], "")
    return re.sub(r"\s+", " ", text).strip()


def strip_paths_from_stderr(text: str, *paths: str) -> str:
    out = text
    for path in paths:
        if not path:
            continue
        out = out.replace(path, "")
        out = out.replace(str(path).replace("\\", "/"), "")
    return re.sub(r"\s+", " ", out).strip()


def empty_input_identity(
    empty_records: Sequence[str], contrast_records: Sequence[str]
) -> None:
    """Structured errors identify empty input as a kind (L115). Wording open.

    Do not require the letters 'empty input', JSON, or a field named error.
    The N arms share one remaining kind after stripping paths; that kind
    differs from other named failure kinds (unknown option, unreadable path).
    """
    empties = [re.sub(r"\s+", " ", rec).strip() for rec in empty_records]
    assert all(empties), (
        "structured error does not identify empty input (empty remainder)"
    )
    kinds = set(empties)
    assert len(kinds) == 1, (
        f"empty-input arms do not share one identifying kind: {sorted(kinds)!r}"
    )
    kind = empties[0]
    for other in contrast_records:
        other_n = re.sub(r"\s+", " ", other).strip()
        assert other_n != kind, (
            "empty-input structured error is not distinct from another "
            "failure kind"
        )


def require_stdout_utf8(result: RunResult) -> str:
    """Standard output uses UTF-8 (L122). A decode failure is a failed assertion."""
    try:
        decoded = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        decoded = None
        decode_err = exc
    else:
        decode_err = None
    assert decoded is not None, f"standard output is not UTF-8: {decode_err}"
    return decoded


# ---------------------------------------------------------------------------
# Invoke wrappers
# ---------------------------------------------------------------------------


def scan_stdin(
    text: str | bytes, extra_args: Sequence[str] = ()
) -> RunResult:
    with workspace() as ws:
        return ws.invoke(list(extra_args), stdin=text)


def scan_path(
    ws, relpath: str, extra_args: Sequence[str] = ()
) -> RunResult:
    dest = ws.resolve(relpath)
    return ws.invoke([*list(extra_args), str(dest)])


def unicode_len(text: str) -> int:
    return len(text)


# ---------------------------------------------------------------------------
# Usage / switches (discover, do not freeze argv spellings)
# ---------------------------------------------------------------------------


def looks_like_usage_text(text: str) -> bool:
    """Bootstrap discovery only. Not the L118 usage-message assertion."""
    low = text.lower()
    return "usage" in low or "--" in text


def fold_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def padding_of_length(n: int, unit: str = "bridge ") -> str:
    if n < 1:
        raise ValueError("n must be positive")
    text = (unit * (n // len(unit) + 1))[:n]
    if len(text) != n:
        raise HarnessError(f"could not build a pad of length {n}")
    return text


def _looks_like_usage(text: str) -> bool:
    return looks_like_usage_text(text)


def usage_from_help() -> str:
    errors: list[str] = []
    for token in ("--help", "-h", "-?", "help", "--usage"):
        result = invoke([token])
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout_text
            if _looks_like_usage(text):
                print(f"[F01] usage via bootstrap token {token!r}", flush=True)
                return text
        errors.append(
            f"{token!r} exit={result.returncode} stdout={result.stdout_text[:200]!r}"
        )
    raise HarnessError(
        "could not obtain a usage message; tried help-shaped argv: "
        + "; ".join(errors)
    )


def help_requests_from_usage(usage: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in re.finditer(r"(--h(?:elp)?)\b", usage, re.I):
        found.append(match.group(1))
    if re.search(r"(?<![\w-])-h(?![\w-])", usage):
        found.append("-h")
    uniq = tuple(dict.fromkeys(found))
    if not uniq:
        raise HarnessError("usage does not name a help request")
    return uniq


def _usage_line_flags(line: str) -> list[str]:
    flags = re.findall(r"--[A-Za-z][\w-]*", line)
    return [f for f in flags if f.lower() not in {"--help"}]


def _talks_interval_or_resample(text: str) -> bool:
    low = text.lower()
    return "interval" in low or "resample" in low


def _strip_usage_flags(line: str) -> str:
    return re.sub(r"--[A-Za-z][\w-]*", " ", line)


def _is_usage_synopsis_line(line: str) -> bool:
    return line.strip().lower().startswith("usage")


def switch_from_usage(usage: str, talks, concept: str) -> str:
    """Discover one optional switch from the usage message (Contract: discovered
    from usage, not from a required flag spelling).

    A usage line whose description talks about *concept* associates the
    switches on that line. Several switches on one such line are aliases of
    one switch (for example a long name and a synonym), so any of them is that
    switch; the first one is returned. Switches whose own spelling talks about
    the concept are preferred on that line. Lines that associate different,
    unrelated switches are still an ambiguity.
    """
    groups: list[list[str]] = []
    for line in usage.splitlines():
        if _is_usage_synopsis_line(line):
            continue
        flags = _usage_line_flags(line)
        if not flags:
            continue
        remainder = _strip_usage_flags(line)
        named = [f for f in flags if talks(f)]
        if talks(remainder):
            groups.append(named or flags)
        elif named:
            groups.append(named)
    merged: list[list[str]] = []
    for group in groups:
        for existing in merged:
            if set(existing) & set(group):
                existing.extend(f for f in group if f not in existing)
                break
        else:
            merged.append(list(dict.fromkeys(group)))
    if len(merged) == 1:
        return merged[0][0]
    if len(merged) > 1:
        raise HarnessError(
            f"usage associates several unrelated {concept} switches: {merged!r}"
        )
    # Synopsis-only fallback: tokens whose own spelling talks about the
    # concept. Several such tokens in one synopsis are alternatives of one
    # switch. Neighbouring synopsis flags are not associated.
    for line in usage.splitlines():
        if not _is_usage_synopsis_line(line):
            continue
        named = [f for f in _usage_line_flags(line) if talks(f)]
        if named:
            return named[0]
    raise HarnessError(f"usage does not name a {concept} switch")


def interval_flag_from_usage(usage: str) -> str:
    """Discover the resampled-interval switch from usage (L91, L111, L118).

    Association is the description that talks about an interval or
    resample, not a required ``--ci`` spelling, and not every flag on
    the same synopsis line as a token that happens to contain
    ``resample``.
    """
    return switch_from_usage(usage, _talks_interval_or_resample, "interval / resample")


def usage_names_end_of_options_double_dash(usage: str) -> None:
    """Usage names the double-dash that stops option parsing (L118).

    A help switch such as ``--help`` or ``-h`` is not that name: those
    tokens contain dashes but do not document end-of-options.
    """
    assert re.search(r"(?<![\w-])--(?![\w-])", usage), (
        "usage does not name the double-dash that stops option parsing"
    )


def usage_names_concepts(usage: str) -> None:
    low = usage.lower()
    assert "clean" in low or "scrub" in low, (
        "usage does not name a cleanup / scrub switch"
    )
    assert "interval" in low or "resample" in low, (
        "usage does not name an interval / resample switch"
    )
    usage_names_end_of_options_double_dash(usage)


_OPTION_PLACEHOLDERS = frozenset(
    {
        "options",
        "option",
        "opts",
        "opt",
        "flags",
        "flag",
        "switches",
        "switch",
        "args",
        "arguments",
    }
)

# L118 names the single-file operand, not the letters 'file'. A path or
# document placeholder is that operand. The word 'operand' itself is not,
# and neither is the word 'input' (including inside 'standard input').
_FILE_OPERAND_MARKS = frozenset(
    {
        "file",
        "files",
        "path",
        "paths",
        "document",
        "documents",
        "filename",
        "filepath",
    }
)


def usage_names_single_file_operand(usage: str) -> None:
    """Usage names the single-file operand. Do not require the word 'file'.

    Only the usage synopsis is searched. An ``[options]`` / ``<options>``
    placeholder is not that operand. The word ``input`` — including
    inside ``standard input`` / ``stdin`` — is not that operand. The
    word ``operand`` is not that operand. A sentence that only mentions
    standard input, a path, or a document is not that operand. A
    two-token usage line (command name plus any extra word) is not the
    operand unless that leftover token, after options are stripped, is
    a file / path / document name.
    """

    def _is_file_operand_name(name: str) -> bool:
        low = name.lower().replace("_", "").replace("-", "")
        if not low or low in _OPTION_PLACEHOLDERS:
            return False
        if low in {"input", "operand", "operands"}:
            return False
        return low in _FILE_OPERAND_MARKS

    syn_lines: list[str] = []
    for line in usage.splitlines() or [usage]:
        stripped = line.strip()
        if not stripped:
            if syn_lines:
                break
            continue
        if stripped.lower().startswith("usage"):
            syn_lines.append(stripped)
            continue
        if not syn_lines:
            syn_lines.append(stripped)
        break
    assert syn_lines, "usage does not name the single-file operand"
    syn = " ".join(syn_lines)
    syn = re.sub(r"standard[\s-]+input", " ", syn, flags=re.I)
    syn = re.sub(r"\bstdin\b", " ", syn, flags=re.I)

    placeholders = re.findall(r"[\[<]([A-Za-z][-A-Za-z0-9_]*)[\]>]", syn)
    named = any(_is_file_operand_name(name) for name in placeholders)

    # Drop "usage: command" then option groups/tokens. Leftover must be
    # the operand name, not a prose sentence that happens to contain
    # "path" / "document" / "input". An [options] placeholder is not
    # the file operand. A leftover word that is only "input" is not.
    work = re.sub(r"^usage\s*:?\s*\S+\s*", " ", syn, flags=re.I)
    work = re.sub(r"\[[^\]]*\]", " ", work)
    work = re.sub(r"<[^>]*>", " ", work)
    work = re.sub(r"--[A-Za-z][\w-]*", " ", work)
    work = re.sub(r"(?<![\w-])--(?![\w-])", " ", work)
    work = re.sub(r"(?<![\w-])-\w+", " ", work)
    skip = {"or", "and"} | _OPTION_PLACEHOLDERS
    leftover = [
        tok
        for tok in re.findall(r"[A-Za-z][-A-Za-z0-9_]*", work)
        if tok.lower() not in skip
    ]
    file_toks = [tok for tok in leftover if _is_file_operand_name(tok)]
    other = [tok for tok in leftover if not _is_file_operand_name(tok)]
    if file_toks and not other:
        named = True
    assert named, "usage does not name the single-file operand"


def require_usage_message(text: str) -> None:
    """*text* is an actual usage message (L118), not the letters 'usage' or a '--' substring.

    Names the cleanup switch, the interval switch, the end-of-options
    double-dash, and the single-file operand.
    """
    assert str(text).strip(), "usage message is empty"
    usage_names_concepts(text)
    usage_names_single_file_operand(text)


def stderr_states_one_file_at_a_time(remainder: str) -> None:
    """After paths are stripped, *remainder* still states the one-file limit (L119).

    Wording is open: do not require this checkout's sentence. A generic nonempty
    leftover is not that statement. The statement is recognizable as a
    one/only/single-file (or operand/path/document) limit.
    """
    low = re.sub(r"\s+", " ", remainder).strip().lower()
    assert low, (
        "error stream does not state that only one file at a time is supported"
    )
    has_one = bool(re.search(r"\b(only|single|one)\b", low))
    has_file = bool(
        re.search(r"\b(file|files|operand|operands|path|document)\b", low)
    )
    assert has_one and has_file, (
        "error stream does not state that only one file at a time is supported"
    )


def band_named_for_score(score: int) -> str:
    """The unique L98 band whose range contains *score*."""
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise HarnessError(f"score {score!r} is outside 0–100")
    matches = [
        name for name, (lo, hi) in BAND_RANGES.items() if lo <= score <= hi
    ]
    assert len(matches) == 1, (
        f"score {score} is not in exactly one of the five L98 band ranges: "
        f"{matches!r}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# Padding / twins
# ---------------------------------------------------------------------------


def neutral_words(n: int, token: str = "bridge") -> str:
    if n < 1:
        raise ValueError("n must be positive")
    return " ".join([token] * n)


def pad_human(n_words: int) -> str:
    """Varied factual sentences so length is not a memorized blob.

    Every sentence is indexed in several tokens so six-word spans do not
    repeat (degenerate repetition is a score-moving family). Lengths stay
    uneven so the pad is not a rhythm-class carrier.
    """
    templates = (
        "Tally{i} notes mason{i} measured pier{i}.",
        "On day{i} the mason at kiln{i} pointed chamber{i} with lime after the spring flood receded along the east wall.",
        "Beam{i} still sits true beside mark{i}.",
        "A clerk at desk{i} listed every stone from quay{i} beside lock{i} after winter storms stripped the moss from the inner face.",
        "Oak post{i} holds the walkway.",
        "Lime coat{i} remains on the inner face of chamber{i} near gate{i} where the gates meet the sill.",
        "Barges at berth{i} waited below ridge{i} until lock{i} opened at dawn for the survey.",
    )
    sentences: list[str] = []
    words: list[str] = []
    i = 1
    while len(words) < n_words:
        sentence = templates[(i - 1) % len(templates)].format(i=i)
        sentences.append(sentence)
        words.extend(re.findall(r"[\w'-]+", sentence))
        i += 1
    return " ".join(sentences)


def runtime_twin(kind: str) -> str:
    if kind == "factual":
        return SHORT_FACTUAL_TWIN
    if kind == "slop":
        return SHORT_SLOP_TWIN
    if kind == "placeholder":
        return (
            f"Please send the draft to {PLACEHOLDER_TWIN} before noon. "
            f"See {TRACKING_URL_TWIN} for the rest."
        )
    if kind == "cafe":
        return "The naïve résumé sat on the oak desk beside a brass lamp."
    raise HarnessError(f"unknown twin kind {kind!r}")


def zw_split(word: str, mark: str | None = None) -> str:
    """Split *word* with one in-word zero-width character. Do not pin the codepoint."""
    if len(word) < 2:
        raise ValueError("word too short to split")
    if mark is None:
        mark = "\u200b"
    mid = len(word) // 2
    return word[:mid] + mark + word[mid:]


def latin_homoglyph(word: str, cyrillic: str = "\u0430") -> str:
    """Replace one Latin letter with a lookalike that folds back to that letter."""
    fold = {
        "\u0430": "a",
        "\u043e": "o",
        "\u03bf": "o",
        "\u0435": "e",
        "\u0441": "c",
        "\u0455": "s",
        "\u0440": "p",
        "\u0445": "x",
        "\u0443": "y",
        "\u0456": "i",
        "\u04bb": "h",
    }
    target = fold.get(cyrillic, "a")
    for index, ch in enumerate(word):
        if ch.lower() == target:
            return word[:index] + cyrillic + word[index + 1 :]
    for index, ch in enumerate(word):
        if "a" <= ch.lower() <= "z" and ord(ch) < 128:
            return word[:index] + cyrillic + word[index + 1 :]
    return cyrillic + word[1:]


_LOOKALIKE_FOLD = {
    "\u0430": "a",
    "\u043e": "o",
    "\u03bf": "o",
    "\u0435": "e",
    "\u0441": "c",
    "\u0455": "s",
    "\u0440": "p",
    "\u0445": "x",
    "\u0443": "y",
    "\u0456": "i",
    "\u04bb": "h",
}


def fold_lookalikes(text: str) -> str:
    """*text* with every planted lookalike letter replaced by its Latin letter."""
    return "".join(_LOOKALIKE_FOLD.get(ch, ch) for ch in text)


# Contrast arms for the three L97 character-layer counts. Each pair is the
# same prose; only the second arm carries the marks being counted.
NBSP_PROBE = (
    "Two\u00a0words sit on the\u00a0page near the\u00a0lock by the\u00a0weir "
    "at\u00a0dawn."
)


def zero_width_arms() -> tuple[str, str]:
    return SHORT_FACTUAL, SHORT_FACTUAL[:40] + "\u200b" * 5 + SHORT_FACTUAL[40:]


def nonstandard_space_arms() -> tuple[str, str]:
    return NBSP_PROBE.replace("\u00a0", " "), NBSP_PROBE


def lookalike_arms() -> tuple[str, str]:
    mixed = (
        f"They {latin_homoglyph('showcase')} the "
        f"{latin_homoglyph('seamless', chr(0x043e))} "
        f"{latin_homoglyph('tapestry', chr(0x0435))} "
        f"{latin_homoglyph('pivotal', chr(0x0430))} "
        f"{latin_homoglyph('robust', chr(0x043e))} latch."
    )
    return fold_lookalikes(mixed), mixed


def bind_character_layer_slot(slot: str) -> None:
    """Bind one L97 character-layer count from its property-only contrast."""
    arms = {
        "invisible": (zero_width_arms, bind_invisible_count),
        "space": (nonstandard_space_arms, bind_nonstandard_space_count),
        "mixed": (lookalike_arms, bind_mixed_script_count),
    }
    if slot not in arms:
        raise HarnessError(f"unknown character-layer slot {slot!r}")
    build, bind = arms[slot]
    plain, marked = build()
    _pf, plain_m = require_success_report(
        scan_stdin(plain), input_chars=unicode_len(plain)
    )
    _mf, marked_m = require_success_report(
        scan_stdin(marked), input_chars=unicode_len(marked)
    )
    bind(plain_m, marked_m)


def rhythm_uniform_paragraphs(paragraphs: int = 8, words: int = 10) -> str:
    """Equal-length factual paragraphs (rhythm class: uniform paragraph length)."""
    if paragraphs < 2:
        raise ValueError("need at least two paragraphs")
    subjects = [
        "Iron beams",
        "Stone piers",
        "Oak planks",
        "Brick walls",
        "Clay tiles",
        "Lead joints",
        "Pine posts",
        "Slate slabs",
        "Lime coats",
        "Sand beds",
        "Ash rails",
        "Elm gates",
    ]
    # "Iron beams hold the old deck up still now." is 9 words; pad to *words*.
    base_tail = "hold the old deck up still now"
    extra = max(0, words - 9)
    pad = " " + " ".join(f"mark{j}" for j in range(extra)) if extra else ""
    parts = []
    for i in range(paragraphs):
        line = f"{subjects[i % len(subjects)]} {base_tail}{pad}.".strip()
        parts.append(line)
    return "\n\n".join(parts)


def rhythm_alternating_cadence(pairs: int = 6) -> str:
    """Short then long factual sentences (writing-advice: mechanical alternation)."""
    if pairs < 3:
        raise ValueError("need at least three short/long pairs")
    bits: list[str] = []
    for i in range(pairs):
        bits.append(f"Iron post{i} holds.")
        bits.append(
            f"The masonry along quay{i} still faces west after the spring flood "
            f"receded from the inner chamber wall beside lock{i}."
        )
    return " ".join(bits)


def rhythm_only_candidate_texts() -> tuple[str, ...]:
    """Documents that may exhibit L104 rhythm-only evidence.

    Sentence-length monotony, mechanical alternation, uniform paragraph
    length, and contraction absence are the named kinds. L104 does not
    give a constructable fire for 40, 41, 44, or 55, so these texts are
    not a must-fire table for even-length, equal-length, short-then-long,
    or contraction-absence pads. Length and paragraph count vary so a
    detector that uses a different rhythm trigger still counts. The
    caller keeps the cap when rhythm-class evidence is actually present
    and is the only score-moving evidence.
    """
    texts: list[str] = []
    for count, words in (
        (6, 7),
        (8, 7),
        (10, 8),
        (12, 9),
        (16, 6),
        (20, 11),
        (8, 12),
        (14, 5),
    ):
        texts.append(rhythm_monotony_document(sentences=count, words=words))
    for count, words in ((4, 10), (6, 8), (8, 12), (12, 9), (5, 15)):
        texts.append(rhythm_uniform_paragraphs(count, words=words))
    for count in (4, 6, 10, 8):
        texts.append(rhythm_alternating_cadence(count))
    texts.append(CONTRACTABLE_OPINION)
    texts.append(
        "Iron beams hold. Stone piers hold. Oak planks hold. Brick walls hold. "
        "Clay tiles hold. Lead joints hold. Pine posts hold. Slate slabs hold."
    )
    return tuple(texts)


def rhythm_monotony_document(sentences: int = 8, words: int = 7) -> str:
    """Even-length factual sentences (rhythm class: sentence-length monotony)."""
    subjects = [
        "Iron beams",
        "Stone piers",
        "Oak planks",
        "Brick walls",
        "Clay tiles",
        "Lead joints",
        "Pine posts",
        "Slate slabs",
        "Lime coats",
        "Sand beds",
    ]
    tail = "hold the old deck up."
    # "Iron beams hold the old deck up." → 7 words
    parts = []
    for i in range(sentences):
        subj = subjects[i % len(subjects)]
        extra = "" if words <= 7 else " still"
        line = f"{subj}{extra} {tail}".strip()
        parts.append(line)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Network observer
# ---------------------------------------------------------------------------


@contextmanager
def proxy_sink() -> Iterator[Any]:
    connections: list[float] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(32)
    sock.settimeout(0.2)
    port = sock.getsockname()[1]
    stop = threading.Event()

    def _accept() -> None:
        while not stop.is_set():
            try:
                client, _addr = sock.accept()
                connections.append(time.time())
                try:
                    client.close()
                except OSError:
                    pass
            except socket.timeout:
                continue
            except OSError:
                break

    thread = threading.Thread(target=_accept, daemon=True)
    thread.start()

    class Sink:
        url = f"http://127.0.0.1:{port}"
        hostport = f"127.0.0.1:{port}"

        @property
        def n_connections(self) -> int:
            return len(connections)

        def fire_positive_control(self) -> None:
            before = len(connections)
            probe = socket.create_connection(("127.0.0.1", port), timeout=2)
            probe.close()
            deadline = time.time() + 2.0
            while time.time() < deadline and len(connections) <= before:
                time.sleep(0.05)
            if len(connections) <= before:
                raise HarnessError(
                    "proxy sink observed no connect from the positive control"
                )

    try:
        yield Sink()
    finally:
        stop.set()
        try:
            sock.close()
        except OSError:
            pass
        thread.join(timeout=1.0)
