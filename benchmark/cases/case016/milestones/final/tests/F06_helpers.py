# feature: F06
"""Observation helpers for the /prosecheck command router.

New names for this slice only. Sealed helpers are imported, not copied.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from _harness import HarnessError, mode_flag_path, repo_root
from F01_helpers import (
    HUMANIZED_CODING,
    finding_records,
    findings_from_report,
    hit_count,
    metrics_from_report,
    parse_structured_mapping,
    scan_stdin,
)
from F02_helpers import (
    readable_scores_0_100,
    runtime_token,
    standalone_int_present,
)
from F03_helpers import cleanup_switch
from F04_helpers import (
    archive_mb_cap_present,
    delivered_text,
    named_int_present,
    require_full_scoring,
    require_hook_success,
    standalone_word_present,
    user_prompt,
)
from F05_helpers import (
    ARCHIVE_KB_FIGURES,
    PLAIN_KB,
    CONFIDENCE_WORDS,
    LEVEL_WORDS,
    Measured,
    Standin,
    WINDOW_GROUPED,
    WINDOW_PLAIN,
    measure_text,
    names_window,
    pad_human,
    phrase_for_band,
    prose_above_20_not_40,
    prose_dense,
    prose_for_band,
    prose_none,
    prose_under,
)

PLAIN = "/prosecheck"
NAMED = "/prosecheck:prosecheck"
SUBCOMMANDS: tuple[str, ...] = (
    "lite",
    "full",
    "strict",
    "off",
    "on",
    "status",
    "show",
    "check",
    "doctor",
    "stats",
    "init",
    "help",
)
HELP_LIST: tuple[str, ...] = tuple(word for word in SUBCOMMANDS if word != "help")
PROSE_GLOBS: tuple[str, ...] = (
    "*.md",
    "*.mdx",
    "*.markdown",
    "*.txt",
    "*.rst",
    "*.tex",
    "*.org",
    "*.adoc",
)
CODE_GLOBS: tuple[str, ...] = ("*.py", "*.js", "*.ts", "*.json")
DAY = 24 * 3600
NOT_AUTHOR = "was written by"
# One artifact at a time. A path that carries both a leading @ and quotes
# is at-double or at-single: the @ comes first, then one pair of quotes.
# Quotes that wrap the @ are not a spelling the lines require.
CHECK_PATH_ARTIFACTS: tuple[str, ...] = (
    "bare",
    "double",
    "single",
    "at",
    "at-double",
    "at-single",
)


def _submit_prompt(
    ws,
    prompt: str,
    *,
    session_id: str | None = None,
    transcript_path: str | None = None,
    env_updates: Mapping[str, str | None] | None = None,
    cwd: str | None = None,
):
    """One prompt-submit. Host fields are only how the payload is sent."""
    payload: dict[str, Any] = {"prompt": prompt}
    if session_id is not None:
        payload["session_id"] = session_id
    if transcript_path is not None:
        payload["transcript_path"] = transcript_path
    return ws.invoke_hook(
        "prompt-submit",
        payload=payload,
        env_updates=env_updates,
        cwd=cwd,
    )


def prompt_submission(
    ws,
    prompt: str,
    *,
    session_id: str | None = None,
    transcript_path: str | None = None,
    env_updates: Mapping[str, str | None] | None = None,
    cwd: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """JSON object, if the body is one, and the joined delivery text.

    Empty stdout is silence: no object. A failed exit raises. A body that
    is not a JSON object is not a decision; the joined text is still
    returned so a reminder written as plain text stays observable.
    """
    result = _submit_prompt(
        ws,
        prompt,
        session_id=session_id,
        transcript_path=transcript_path,
        env_updates=env_updates,
        cwd=cwd,
    )
    text = delivered_text(result)
    raw = result.stdout_text
    if raw == "":
        return None, ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None, text
    if isinstance(obj, dict):
        return obj, text
    return None, text


def block_reason(obj: dict[str, Any] | None, joined: str) -> str:
    """Reason of a block decision. That reason is the command reply.

    Joining every string in the body is not this reply. A decision that
    is not a block is not a command reply. Text that is not the reason
    is not the reply the rest of an assertion may read.
    """
    if not isinstance(obj, dict):
        raise AssertionError(
            "command hook did not return a decision object; "
            f"text={joined[:400]!r}"
        )
    decision = obj.get("decision")
    if decision != "block":
        raise AssertionError(
            "command hook did not block the prompt; "
            f"decision={decision!r} text={joined[:400]!r}"
        )
    reason = obj.get("reason")
    if not isinstance(reason, str):
        raise AssertionError(
            "block decision reason is not the command reply; "
            f"text={joined[:400]!r}"
        )
    return reason


def command_reply(
    ws,
    prompt: str,
    *,
    session_id: str | None = None,
    transcript_path: str | None = None,
    env_updates: Mapping[str, str | None] | None = None,
    cwd: str | None = None,
) -> str:
    """Command reply for one command identity.

    The identity is the prompt: either form of a subcommand, a bare
    invocation, an unknown word, check with or without a path, or an
    entire-prompt phrase that stores off. The reply is the reason of a
    block decision. A non-blocking envelope fails. A block whose reason
    is not the text the caller reads fails. Joining every string in the
    body does not satisfy this read. A prompt that is not a command
    stays on ``prompt_submission``.
    """
    obj, joined = prompt_submission(
        ws,
        prompt,
        session_id=session_id,
        transcript_path=transcript_path,
        env_updates=env_updates,
        cwd=cwd,
    )
    return block_reason(obj, joined)


def command_delivery(
    ws,
    prompt: str,
    *,
    session_id: str | None = None,
    transcript_path: str | None = None,
    env_updates: Mapping[str, str | None] | None = None,
    cwd: str | None = None,
) -> str:
    """Joined string values of a prompt that is not a command reply.

    Host fields are only how the payload is sent. This read never looks
    at the decision or the reason. A command reply does not use it. A
    non-zero exit or a non-JSON body on a non-empty reply raises; empty
    stdout is silence.
    """
    result = _submit_prompt(
        ws,
        prompt,
        session_id=session_id,
        transcript_path=transcript_path,
        env_updates=env_updates,
        cwd=cwd,
    )
    text = delivered_text(result)
    raw = result.stdout_text
    if raw == "":
        return ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"prompt-submit reply is not JSON: {exc}; text={raw[:400]!r}"
        ) from exc
    if not isinstance(obj, (dict, list)):
        raise HarnessError(
            "prompt-submit JSON is not an object or array: "
            f"{type(obj).__name__}"
        )
    return text


def delivery_pieces(text: str) -> list[str]:
    """String pieces of a delivery already joined for reading."""
    if text == "":
        return []
    return text.split("\n")


def level_bearing_line(text: str, level: str) -> str:
    """The single line of a joined status delivery that names *level*."""
    if "\n" in level or level not in LEVEL_WORDS:
        raise HarnessError(f"not a stored level: {level!r}")
    lines = [
        line
        for line in text.splitlines()
        if standalone_word_present(line, level)
    ]
    if len(lines) != 1:
        raise HarnessError(
            f"status delivery does not name {level!r} on exactly one line; "
            f"lines={lines!r} text={text[:400]!r}"
        )
    return lines[0]


def assert_one_level_line(observed: tuple[str, str], level: str) -> None:
    """The status report is one line and names only this stored level.

    *observed* is the command reply and the joined delivery. The reply is
    the report. A block decision joined beside that reply is not another
    line of the report. The reply itself must be a single line. The joined
    delivery must still name this level on exactly one line and no other
    stored level.
    """
    if (
        not isinstance(observed, tuple)
        or len(observed) != 2
        or not all(isinstance(part, str) for part in observed)
    ):
        raise HarnessError(
            "status observation must be the command reply and the joined delivery"
        )
    reply, joined = observed
    if "\n" in level or level not in LEVEL_WORDS:
        raise HarnessError(f"not a stored level: {level!r}")
    if len(reply.splitlines()) != 1:
        raise HarnessError(
            f"status report is not one line; reply={reply[:400]!r}"
        )
    level_bearing_line(joined, level)
    present = [word for word in LEVEL_WORDS if standalone_word_present(joined, word)]
    if present != [level]:
        raise HarnessError(
            f"status names {present}, not only {level!r}; text={joined[:400]!r}"
        )
    reply_present = [
        word for word in LEVEL_WORDS if standalone_word_present(reply, word)
    ]
    if reply_present != [level]:
        raise HarnessError(
            f"status report names {reply_present}, not only {level!r}; "
            f"reply={reply[:400]!r}"
        )


def standalone_count(text: str, word: str) -> int:
    if not word:
        raise HarnessError("standalone count has no word")
    pattern = rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])"
    return len(re.findall(pattern, text))


def shows_integer(text: str, value: int) -> bool:
    """Whether *value* is readable as digits, with or without a thousands comma."""
    if standalone_int_present(text, value):
        return True
    grouped = f"{value:,}"
    if grouped == str(value):
        return False
    return grouped in text


def printed_integer_spellings(value: int) -> tuple[str, ...]:
    """Digits of *value*, plus a thousands comma when the quantity needs one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise HarnessError(f"token witness is not an integer: {value!r}")
    plain = str(value)
    grouped = f"{value:,}"
    if grouped == plain:
        return (plain,)
    return (plain, grouped)


def without_printed_integers(text: str, values: Sequence[int]) -> str:
    """Reply after each integer in *values* is removed, comma-grouped or not.

    Removing a raw usage field is not the same operation as removing a total.
    The caller chooses which integers are the totals.
    """
    if not isinstance(text, str):
        raise HarnessError(f"reply is not text: {type(text).__name__}")
    spellings: list[str] = []
    for value in values:
        spellings.extend(printed_integer_spellings(value))
    return strip_tokens(text, spellings)


def require_distinct_token_total(
    total: int,
    raw_fields: Sequence[int],
    turn_count: int,
    *others: int,
) -> int:
    """*total* is an assistant token total no raw usage field also prints.

    It is not a raw usage field, not the turn count, and not the other
    quantity's total. A colliding integer is not used as that witness.
    """
    if isinstance(total, bool) or not isinstance(total, int):
        raise HarnessError(f"token total is not an integer: {total!r}")
    if isinstance(turn_count, bool) or not isinstance(turn_count, int):
        raise HarnessError(f"turn count is not an integer: {turn_count!r}")
    blocked: list[int] = [turn_count]
    for value in list(raw_fields) + list(others):
        if isinstance(value, bool) or not isinstance(value, int):
            raise HarnessError(f"blocked token value is not an integer: {value!r}")
        blocked.append(value)
    if total in blocked:
        raise HarnessError(
            f"token total {total} equals a raw usage field, the turn count, "
            f"or the other total; blocked={blocked}"
        )
    return total


def usage_field_integers(entries: Sequence[Mapping[str, Any]]) -> tuple[int, ...]:
    """Every output-token and cache-read field planted on *entries*.

    A missing usage object is not an empty field list. Both quantities are
    read from each entry that carries usage.
    """
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise HarnessError("transcript entries are not a sequence")
    found: list[int] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HarnessError(
                f"transcript entry is not an object: {type(entry).__name__}"
            )
        message = entry.get("message")
        if not isinstance(message, Mapping):
            raise HarnessError("transcript entry has no message usage")
        usage = message.get("usage")
        if not isinstance(usage, Mapping):
            raise HarnessError("transcript message has no usage object")
        for key in ("output_tokens", "cache_read_input_tokens"):
            if key not in usage:
                raise HarnessError(f"usage object is missing {key}")
            value = usage[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise HarnessError(
                    f"usage field {key} is not an integer: {value!r}"
                )
            found.append(value)
    if not found:
        raise HarnessError("transcript has no usage fields")
    return tuple(found)


def cut_first_integer(text: str, value: int) -> str:
    return re.sub(rf"(?<!\d){int(value)}(?!\d)", " ", text, count=1)


def no_score_integers(text: str) -> None:
    found = readable_scores_0_100(text)
    if found:
        raise HarnessError(
            f"reply still has a 0-100 integer {found}; text={text[:400]!r}"
        )


def any_integer(text: str) -> bool:
    return re.search(r"\d", text) is not None


def without_named_transcript(text: str, path: str) -> str:
    """Stats reply after the host-named transcript path is removed.

    Digits inside that path are the path, not a turn count or a token
    total. The basename is part of the path the host named. An integer
    that remains is one of those quantities only when it is the
    assistant-turn count, the output-token total, or the cache-read
    input-token total. Any other integer may remain. The stored level
    is not one of those counts: the reply may name it or leave it out.
    """
    if not isinstance(text, str):
        raise HarnessError(f"stats reply is not text: {type(text).__name__}")
    if not isinstance(path, str) or path == "":
        raise HarnessError("named transcript path is empty")
    named = Path(path)
    if named.name in {"", ".", ".."}:
        raise HarnessError(f"named transcript path has no basename: {path!r}")
    return strip_tokens(text, [path, named.name])


def stats_quantities_named(text: str, quantities: Sequence[int]) -> tuple[int, ...]:
    """Which of the three stats quantities *text* still names.

    *quantities* are an assistant-turn count, an output-token total, and
    a cache-read input-token total, each as the integer a readable
    transcript of that session reports. The same integer may stand for
    more than one of them when those counts collide. A whole integer
    that is none of them is not named. Digits glued into a word are not
    a whole integer. The stored level is not a quantity.
    """
    if not isinstance(text, str):
        raise HarnessError(f"stats reply is not text: {type(text).__name__}")
    if isinstance(quantities, (str, bytes)) or not isinstance(quantities, Sequence):
        raise HarnessError("stats quantities are not a sequence")
    wanted: list[int] = []
    for value in quantities:
        if isinstance(value, bool) or not isinstance(value, int):
            raise HarnessError(f"stats quantity is not an integer: {value!r}")
        if value not in wanted:
            wanted.append(value)
    if not wanted:
        raise HarnessError("stats quantities are empty")
    named: list[int] = []
    for number in whole_integers(text):
        if number in wanted and number not in named:
            named.append(number)
    return tuple(named)


def replies_without_named_transcripts(
    left: str,
    right: str,
    paths: Sequence[str],
) -> tuple[str, str]:
    """Both replies after every host-named transcript is removed from each.

    The two replies come from different transcripts. A path printed in
    either reply is that transcript, not which integer is which total.
    Both paths, including each basename, are removed from both replies
    before the replies are compared. One path is not that comparison.
    """
    if not isinstance(left, str) or not isinstance(right, str):
        raise HarnessError(
            "stats replies are not text: "
            f"{type(left).__name__}, {type(right).__name__}"
        )
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence):
        raise HarnessError("named transcripts are not a sequence")
    distinct: list[str] = []
    for path in paths:
        if path not in distinct:
            distinct.append(path)
    if len(distinct) < 2:
        raise HarnessError(
            "both named transcripts have to be removed before the replies "
            "are compared"
        )
    kept_left = left
    kept_right = right
    for path in distinct:
        kept_left = without_named_transcript(kept_left, path)
        kept_right = without_named_transcript(kept_right, path)
    return kept_left, kept_right


def fresh_word() -> str:
    """A word that is not one of the twelve subcommands and not a substring of them."""
    for _ in range(20):
        word = "qw" + runtime_token("z")
        if any(word in cmd or cmd in word for cmd in SUBCOMMANDS):
            continue
        if word.lower() in {"on", "off", "help"}:
            continue
        return word
    raise HarnessError("could not mint a word outside the subcommand list")


def label_hits(text: str) -> dict[str, int]:
    """Hit count per detector label. The detector command is the source."""
    result = scan_stdin(text)
    if result.returncode != 0:
        raise HarnessError(
            "detector did not score the label probe: "
            f"exit={result.returncode} stderr={result.stderr_text[:300]!r}"
        )
    report = parse_structured_mapping(result.stdout_text, source="label hits")
    metrics = metrics_from_report(report)
    findings = findings_from_report(report, metrics)
    hits: dict[str, int] = {}
    for rec in finding_records(findings):
        label = rec.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        hits[label] = hit_count(rec)
    return hits


def many_label_prose() -> Measured:
    """Scored prose with strictly more than eight detector labels."""
    measured = prose_dense()
    if len(measured.labels) > 8:
        return measured
    extra = measured.text + "\n" + measured.text
    again = measure_text(extra)
    if len(again.labels) <= 8:
        raise HarnessError(
            "fixture does not fire more than eight labels; "
            f"dense={len(measured.labels)} doubled={len(again.labels)}"
        )
    return again


def zero_label_prose() -> Measured:
    measured = measure_text(HUMANIZED_CODING)
    if measured.labels:
        measured = measure_text(pad_human(80))
    if measured.labels:
        raise HarnessError(
            "fixture still has detector labels; "
            f"labels={measured.labels!r}"
        )
    return measured


def prose_strictly_between(low: int, high: int) -> Measured:
    """Scored prose whose detector score sits strictly between two others.

    The bounds are scores already measured for other rows of the same
    ledger. A sealed fixture that landed in the open interval is returned.
    A detector failure is not treated as "no such prose."
    """
    if isinstance(low, bool) or isinstance(high, bool):
        raise HarnessError(f"score bounds must be integers, got {low!r} and {high!r}")
    if not isinstance(low, int) or not isinstance(high, int):
        raise HarnessError(f"score bounds must be integers, got {low!r} and {high!r}")
    if low > high:
        low, high = high, low
    if high - low < 2:
        raise HarnessError(
            f"no integer score sits strictly between {low} and {high}"
        )
    builders = (
        prose_above_20_not_40,
        lambda: prose_for_band("mixed"),
        lambda: prose_for_band("clean"),
        lambda: prose_for_band("light tells"),
        prose_none,
        lambda: prose_for_band("pervasive tells"),
        lambda: prose_for_band("heavy tells"),
    )
    seen: list[int] = []
    for build in builders:
        measured = build()
        seen.append(measured.score)
        if low < measured.score < high:
            return measured
    raise HarnessError(
        f"fixture has no detector score strictly between {low} and {high}; saw {seen}"
    )


def high_confidence_prose() -> Measured:
    measured = measure_text(pad_human(320))
    if measured.confidence != "high":
        measured = measure_text(pad_human(480))
    if measured.confidence != "high":
        raise HarnessError(
            f"fixture confidence is {measured.confidence!r}, not high"
        )
    return measured


def prose_with_confidence_reason() -> Measured:
    """Short prose whose detector confidence carries a reason.

    High confidence is the arm with no reason. A sample that comes back
    high, or with an empty reason, is not this fixture.
    """
    measured = prose_under()
    if measured.confidence == "high" or not measured.reason:
        measured = measure_text(pad_human(80))
    if measured.confidence == "high" or not measured.reason:
        raise HarnessError(
            "fixture has no non-high confidence with a reason to require; "
            f"confidence={measured.confidence!r} reason={measured.reason!r}"
        )
    return measured


def check_path_argument(path: Path, artifact: str) -> str:
    """The check argument for one path spelling.

    bare is the path. double and single are one surrounding pair of
    quotes. at is one leading @. at-double and at-single put that @
    before the quotes. Each spelling is separate.
    """
    text = os.fspath(path)
    if artifact == "bare":
        return text
    if artifact == "double":
        return f'"{text}"'
    if artifact == "single":
        return f"'{text}'"
    if artifact == "at":
        return f"@{text}"
    if artifact == "at-double":
        return f'@"{text}"'
    if artifact == "at-single":
        return f"@'{text}'"
    raise HarnessError(f"unknown check path artifact: {artifact!r}")


_MARKER_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]+")
# Characters that only lay out a list; a token made of them is not a marker.
_LAYOUT_CHARS = frozenset("-*•·:|>.,;#=")


def _marker_words(line: str) -> set[str]:
    return set(_MARKER_WORD.findall(line))


def _marker_symbols(line: str) -> set[str]:
    return {
        token
        for token in line.split()
        if not re.search(r"[A-Za-z0-9]", token) and not set(token) <= _LAYOUT_CHARS
    }


def carries_marker(line: str, marker: str) -> bool:
    """Whether *line* carries *marker* as a whole token, not inside a word."""
    if _MARKER_WORD.fullmatch(marker):
        return marker in _marker_words(line)
    return marker in _marker_symbols(line)


def success_marker(healthy: str) -> str:
    """A token that sits on all four healthy check lines and not on the closer.

    The spelling is induced from the healthy delivery. It is not a constant.
    A word is matched as a whole token (``ok`` inside ``notebooks`` is not the
    marker). A marker that is a symbol rather than a word is found the same way.
    """
    lines = [line.strip() for line in healthy.splitlines() if line.strip()]
    if len(lines) < 4:
        raise HarnessError(f"doctor delivery has too few lines: {healthy[:400]!r}")
    closing_indexes = {
        index
        for index, line in enumerate(lines)
        if names_window(line) and named_int_present(line, 512)
    }
    if len(closing_indexes) != 1:
        raise HarnessError(
            "healthy doctor closer is not the one line that names 512 and "
            f"the window; closers={closing_indexes!r} text={healthy[:500]!r}"
        )
    for tokens_of in (_marker_words, _marker_symbols):
        owners: dict[str, set[int]] = {}
        for index, line in enumerate(lines):
            for token in tokens_of(line):
                owners.setdefault(token, set()).add(index)
        candidates = [
            token
            for token, indexes in owners.items()
            if len(indexes) == 4 and not indexes & closing_indexes
        ]
        if candidates:
            candidates.sort(key=lambda token: (-len(token), token))
            return candidates[0]
    raise HarnessError(
        "could not induce a four-line success marker from a healthy "
        f"doctor; text={healthy[:500]!r}"
    )


def lines_with(text: str, marker: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and carries_marker(line, marker)
    ]


def _is_detector_word(word: str) -> bool:
    return word in {"detector", "detectors"}


def _is_presence_word(word: str) -> bool:
    return word in {"present", "found", "exists", "available", "installed"} or word.startswith(
        "present"
    )


def _is_writable_word(word: str) -> bool:
    return word == "writable" or word.startswith("writ")


def states_current_mode_line(line: str, level: str) -> bool:
    """The check names this stored level and no other one.

    The level word anywhere else in the reply is not this line.
    """
    if level not in {"lite", "full", "strict", "off"}:
        raise HarnessError(f"not a stored level: {level!r}")
    if not standalone_word_present(line, level):
        return False
    return not any(
        other != level and standalone_word_present(line, other)
        for other in ("lite", "full", "strict", "off")
    )


def states_detector_present_line(line: str) -> bool:
    """The bundled detector is present.

    The Python-run line also names the detector, so a line that names
    Python is the other check. A denial of presence is not this line.
    """
    words = _help_words(line)
    if "python" in words:
        return False
    if not any(_is_detector_word(word) for word in words):
        return False
    if _negation_on(words, _is_detector_word, span=4) or _negation_on(
        words, _is_presence_word, span=3
    ):
        return False
    return _either_order(words, _is_detector_word, _is_presence_word, span=4)


def holds_aside_from_python_word(line: str, holds) -> bool:
    """Whether *holds* is true, setting the standalone word Python aside.

    A healthy doctor uses checks that return false on any line naming
    Python, so the Python-run line and the detector line stay distinct.
    When Python cannot be launched, that word on a successful line is
    not by itself a reason to drop the line. A line that still fails
    *holds* after the word is removed stays false.
    """
    if holds(line):
        return True
    if "python" not in _help_words(line):
        return False
    without = re.sub(r"(?i)(?<![A-Za-z0-9])python(?![A-Za-z0-9])", " ", line)
    return bool(holds(without))


def states_detector_presence_check(line: str) -> bool:
    """The check that reports whether the bundled detector is present.

    The Python-run line also names the detector, so a line that names
    Python is the other check. A line that affirms presence and a line
    that does not are both this check. Nothing here requires a fixed
    sentence for the detector being absent.
    """
    words = _help_words(line)
    if "python" in words:
        return False
    return any(_is_detector_word(word) for word in words)


def states_python_score_line(line: str) -> bool:
    """Python ran the detector and that run is what this line reports.

    A numeric score is the result that keeps the line successful. The
    line names Python and the detector. The detector-present line does
    not name Python. A denial that Python ran is not this line.
    """
    words = _help_words(line)
    if "python" not in words or not any(_is_detector_word(word) for word in words):
        return False
    if _negation_on(words, lambda word: word == "python", span=4):
        return False
    if _negation_on(words, _is_detector_word, span=4):
        return False
    return True


def _writable_denial_indexes(words: Sequence[str]) -> list[int]:
    """Indexes where this line denies that a write can happen.

    ``not writable`` and ``cannot write`` are the same denial, including
    a contraction left after apostrophes are stripped. ``unwritable`` is
    that denial in one word. An affirmative ``writable`` is not a denial.
    """
    hits: list[int] = []
    for index, word in enumerate(words):
        if word.startswith("unwrit") or word.startswith("nonwrit"):
            hits.append(index)
            continue
        if word == "non" and _find_after(words, index, _is_writable_word, 1) is not None:
            hits.append(index)
            continue
        if not (_denial_negation(word) or word == "cannot"):
            continue
        if _find_after(words, index, _is_writable_word, 4) is not None:
            hits.append(index)
    return hits


def _settings_folder_starts(words: Sequence[str]) -> list[int]:
    """Indexes where the named place ``settings folder`` begins.

    The two words are consecutive. A hyphen is already a space, so
    ``settings-folder`` is the same name. One of folder, settings,
    directory, or dir, alone, is not this name.
    """
    starts: list[int] = []
    for index in range(len(words) - 1):
        if words[index] == "settings" and words[index + 1] in {"folder", "folders"}:
            starts.append(index)
    return starts


def _names_settings_folder_near(words: Sequence[str], index: int, before: int, after: int) -> bool:
    """Whether a ``settings folder`` phrase sits in the window around *index*."""
    start = max(0, index - before)
    end = min(len(words), index + 1 + after)
    return any(start <= phrase < end and phrase + 1 < end for phrase in _settings_folder_starts(words))


def states_writable_settings_line(line: str) -> bool:
    """The settings folder is writable.

    The line names that place, the two words settings folder, and says
    the write can happen. A line that only names a directory, or only
    one of those two words, is not this line. The mode, detector, and
    Python lines are the other checks. A denial of the write is not
    this line. The sentence is not fixed.
    """
    words = _help_words(line)
    if "python" in words or any(_is_detector_word(word) for word in words):
        return False
    if not _settings_folder_starts(words):
        return False
    if _writable_denial_indexes(words) or any(
        _names_settings_folder_near(words, index, 0, 4)
        for index, word in enumerate(words)
        if _is_negation(word)
    ):
        return False
    return any(
        _names_settings_folder_near(words, index, 4, 4)
        for index, word in enumerate(words)
        if _is_writable_word(word)
    )


def states_settings_folder_not_writable(line: str) -> bool:
    """The settings folder is not writable.

    The line names that place, the two words settings folder, and denies
    the write. A line that only names a directory, or only one of those
    two words, is not this line. The successful check affirms the write
    and is not this line. The sentence is not fixed.
    """
    words = _help_words(line)
    if not _settings_folder_starts(words):
        return False
    return any(
        _names_settings_folder_near(words, index, 6, 8)
        for index in _writable_denial_indexes(words)
    )


def require_four_healthy_checks(lines: Sequence[str], level: str) -> None:
    """Each of the four success lines is one of the four checks, and each check once.

    Four success markers plus the stored level somewhere else do not pass.
    A line that is not one of these checks does not pass.
    """
    if len(lines) != 4:
        raise HarnessError(
            f"healthy doctor does not have four success lines: {lines!r}"
        )
    checks = (
        ("current mode", lambda line: states_current_mode_line(line, level)),
        ("detector present", states_detector_present_line),
        ("python numeric score", states_python_score_line),
        ("writable settings", states_writable_settings_line),
    )
    for name, pred in checks:
        hits = [line for line in lines if pred(line)]
        if len(hits) != 1:
            raise HarnessError(
                f"healthy doctor does not have exactly one {name} line; "
                f"hits={hits!r} lines={lines!r}"
            )
    for line in lines:
        matched = [name for name, pred in checks if pred(line)]
        if len(matched) != 1:
            raise HarnessError(
                "a healthy success line is not exactly one of the four checks; "
                f"matched={matched!r} line={line!r}"
            )


def require_three_off_success_checks(lines: Sequence[str]) -> None:
    """The three success lines on an off-only doctor are the three non-mode checks.

    Counting the success marker is not enough. Each line is one of: the
    bundled detector is present, Python ran the detector, the settings
    folder is writable. Each of those checks appears once. Three other
    successful lines do not pass. The mode line is not among these lines.
    """
    checks = (
        ("detector present", states_detector_present_line),
        ("python ran the detector", states_python_score_line),
        ("writable settings", states_writable_settings_line),
    )
    assert len(lines) == 3, lines
    for name, pred in checks:
        hits = [line for line in lines if pred(line)]
        assert len(hits) == 1, (name, hits, lines)
    for line in lines:
        matched = [name for name, pred in checks if pred(line)]
        assert len(matched) == 1, (matched, line)


def closing_line(text: str) -> str:
    """The doctor closer, recognised by what it points at, not by a line number."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    capped = [
        line
        for line in lines
        if names_window(line) and named_int_present(line, 512) and "show" in line
    ]
    if len(capped) == 1:
        return capped[0]
    rerun = [
        line
        for line in lines
        if "/prosecheck doctor" in line
    ]
    if len(rerun) == 1:
        return rerun[0]
    opened = [
        line
        for line in lines
        if "on" in line.split()
        and (NAMED in line or (PLAIN in line and "doctor" not in line))
        and not names_window(line)
    ]
    # Prefer the line that carries the typed follow-up and is not a check line
    # already selected as a rerun. Callers that know the form pass that line
    # through the unique match above.
    if len(opened) == 1:
        return opened[0]
    raise HarnessError(f"doctor closer is not recognisable: {text[:500]!r}")


def doctor_check_lines(text: str) -> list[str]:
    """The four-or-so check lines between the title and the closer.

    The title is the first non-empty line and the closer is the last.
    The check lines are the non-empty lines between those two. A line is
    not selected by dropping success markers, so the closer is never one
    of these lines, and neither is the title. A reply with no room for
    both a title and a closer is not a health check.
    """
    if not isinstance(text, str):
        raise HarnessError(f"doctor reply is not text: {text!r}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise HarnessError(
            f"doctor reply has no title and closer; text={text[:400]!r}"
        )
    return lines[1:-1]


def states_no_report(text: str) -> bool:
    """Whether *text* says there was no report.

    A denial sits on report, in either order, with a few words between.
    The sentence is not fixed. A shared pair that never denies a report
    is not this statement.
    """
    words = _help_words(text)
    return _either_order(words, _is_negation, _is_report_word, span=4)


def _is_report_word(word: str) -> bool:
    return word in {"report", "reports"}


def states_failure_report(text: str) -> bool:
    """Whether *text* reports a failure.

    The failure word may be fail, failed, failing, or failure. The
    sentence around it is not fixed. A no-report statement is a different
    report. An exit status, a file name, or an empty remainder is not
    this report.
    """
    return any(_is_failure_word(word) for word in _help_words(text))


def _is_failure_word(word: str) -> bool:
    return word in {"fail", "fails", "failed", "failing", "failure", "failures"}


def shared_phrase(left: str, right: str, blocked: Sequence[str]) -> str:
    """The no-report statement both texts share, absent from *blocked*.

    Any other overlapping run is not that statement. The sentence itself
    is not fixed. No such statement is a failed observation.
    """

    def words(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9]+", text.lower())

    left_words = words(left)
    right_join = " " + " ".join(words(right)) + " "
    blocked_joins = [" " + " ".join(words(text)) + " " for text in blocked]
    best = ""
    for start in range(len(left_words)):
        for end in range(start + 2, min(len(left_words), start + 8) + 1):
            phrase = " ".join(left_words[start:end])
            if not states_no_report(phrase):
                continue
            padded = f" {phrase} "
            if padded not in right_join:
                continue
            if any(padded in block for block in blocked_joins):
                continue
            if len(phrase) > len(best):
                best = phrase
    if not best:
        raise HarnessError(
            "the two arms share no statement that there was no report "
            "which the other replies lack; "
            f"left={left[:240]!r} right={right[:240]!r}"
        )
    return best


def normalised(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def reports_word_as_unknown(text: str, word: str) -> bool:
    """The typed token is reported as unknown, not merely echoed.

    The word ``unknown`` has to sit with that token. Listing the valid
    words beside an echo is not the report. Punctuation around either
    word is not fixed.
    """
    words = _help_words(text)
    token = word.lower()
    if token not in words:
        return False
    for index, item in enumerate(words):
        if item != token:
            continue
        start = max(0, index - 6)
        end = min(len(words), index + 7)
        if any(words[cursor] == "unknown" for cursor in range(start, end)):
            return True
    return False


def replies_without_typed_words(
    left: str, right: str, typed: Sequence[object]
) -> tuple[str, str]:
    """Both command replies after every typed word is removed from each.

    The shared block decision is already set aside: these strings are the
    command replies, not the decision envelope. The typed word on one arm
    and the typed word on the other are both removed from both replies, so
    an operand echo is not a remaining difference. An empty word list is
    not a comparison.
    """
    tokens = [token for token in typed if token is not None and str(token) != ""]
    if len(tokens) < 2:
        raise HarnessError(
            "both typed words have to be removed before the replies are compared"
        )
    return strip_tokens(left, tokens), strip_tokens(right, tokens)


def strip_tokens(text: str, tokens: Sequence[object]) -> str:
    out = text
    ordered = sorted(
        {str(token) for token in tokens if token is not None and str(token) != ""},
        key=len,
        reverse=True,
    )
    for token in ordered:
        if token.isdigit():
            out = re.sub(rf"(?<!\d){re.escape(token)}(?!\d)", " ", out)
        elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]*", token):
            out = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])",
                " ",
                out,
            )
        else:
            out = out.replace(token, " ")
    return normalised(out)


# Group separators join digits into one integer. A thin space and a
# typographic apostrophe are separators the same way a comma, a space,
# an underscore, and an ASCII apostrophe are. A separator that is not
# between digits does not join two numbers.
_GROUP_SEPARATORS = frozenset(" ,_\u2009'\u2019")


def _whole_integer_spans(text: str) -> list[tuple[int, int, int]]:
    """*(value, start, end)* for each standalone whole integer in *text*.

    Digits joined by a group separator are one integer. ``1,720`` is
    1720. A run glued to a letter is not an integer.
    """
    if not isinstance(text, str):
        raise HarnessError(f"stats reply is not text: {type(text).__name__}")
    spans: list[tuple[int, int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        if not text[index].isdigit():
            index += 1
            continue
        if index > 0 and text[index - 1].isalnum():
            while index < length and text[index].isdigit():
                index += 1
            continue
        start = index
        while index < length and text[index].isdigit():
            index += 1
        end = index
        while index < length and text[index] in _GROUP_SEPARATORS:
            cursor = index + 1
            while cursor < length and text[cursor] in _GROUP_SEPARATORS:
                cursor += 1
            if cursor >= length or not text[cursor].isdigit():
                break
            index = cursor
            while index < length and text[index].isdigit():
                index += 1
            end = index
        if end < length and text[end].isalnum():
            continue
        digits = "".join(ch for ch in text[start:end] if ch.isdigit())
        if not digits:
            raise HarnessError(
                f"whole integer has no digits: {text[start:end]!r}"
            )
        spans.append((int(digits), start, end))
    return spans


def whole_integers(text: str) -> list[int]:
    """Every standalone integer in *text*, grouped digits included.

    A comma, space, thin space, underscore, or apostrophe between digits
    joins them. ``1,720`` is one integer outside 0 through 100, not a 1
    and a 720.
    """
    return [value for value, _start, _end in _whole_integer_spans(text)]


def _without_whole_integers(
    text: str,
    values: Sequence[int],
    *,
    limit: int | None = None,
) -> str:
    """Remove whole-integer occurrences of *values*.

    *limit* ``None`` removes every occurrence of each value. A positive
    *limit* removes that many occurrences of each value and leaves a
    later copy in place. Grouped spellings are removed as one span.
    """
    if not isinstance(text, str):
        raise HarnessError(f"stats reply is not text: {type(text).__name__}")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise HarnessError("whole integers to remove are not a sequence")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
    ):
        raise HarnessError(
            f"whole-integer removal limit is not positive: {limit!r}"
        )
    wanted: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise HarnessError(
                f"whole integer to remove is not an integer: {value!r}"
            )
        if value not in wanted:
            wanted.append(value)
    removed = {value: 0 for value in wanted}
    pieces: list[str] = []
    cursor = 0
    for value, start, end in _whole_integer_spans(text):
        if value not in removed:
            continue
        if limit is not None and removed[value] >= limit:
            continue
        removed[value] += 1
        pieces.append(text[cursor:start])
        pieces.append(" ")
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _token_totals_above_100(totals: Sequence[int]) -> list[int]:
    if isinstance(totals, (str, bytes)) or not isinstance(totals, Sequence):
        raise HarnessError("token totals are not a sequence")
    pending = list(totals)
    if not pending:
        raise HarnessError("token totals are empty")
    checked: list[int] = []
    for total in pending:
        if isinstance(total, bool) or not isinstance(total, int):
            raise HarnessError(f"token total is not an integer: {total!r}")
        if total <= 100:
            raise HarnessError(
                f"token total {total} is inside 0 through 100"
            )
        checked.append(total)
    return checked


def stats_reply_without_path_and_totals(
    text: str,
    path: str,
    totals: Sequence[int],
) -> str:
    """Stats reply after the host-named path and each token total are gone.

    Each total is removed as one whole integer, in whatever grouping the
    reply uses. The turn count is still in the text.
    """
    checked = _token_totals_above_100(totals)
    kept = without_named_transcript(text, path)
    return _without_whole_integers(kept, checked)


def account_stats_score_reply(
    text: str,
    path: str,
    totals: Sequence[int],
    level: str,
    turns: int,
) -> str:
    """Path, whole token totals, the level, and one turn occurrence removed.

    A later copy of the turn integer stays, so a session-prose score that
    uses the same integer is still readable. Other integers stay as well.
    """
    if not isinstance(level, str) or level == "" or any(ch.isdigit() for ch in level):
        raise HarnessError(f"current level is not a word: {level!r}")
    if isinstance(turns, bool) or not isinstance(turns, int) or not 0 <= turns <= 100:
        raise HarnessError(f"turn count {turns!r} is outside 0 through 100")
    kept = stats_reply_without_path_and_totals(text, path, totals)
    kept = strip_tokens(kept, [level])
    return _without_whole_integers(kept, [turns], limit=1)


def session_prose_integers(
    text: str,
    path: str,
    totals: Sequence[int],
    level: str,
    turns: int,
) -> list[int]:
    """0-100 integers left after the path, the token totals, the level, and one turn.

    Those integers are what remains of a session-prose score. The turn count
    is not one of them: one occurrence is removed, and a later copy of that
    same integer stays. An empty list is a reply that does not give a
    session-prose score. The list does not say which remaining integer is
    the score, and it does not require a label, a band, or a phrase.
    """
    kept = account_stats_score_reply(text, path, totals, level, turns)
    return [number for number in whole_integers(kept) if 0 <= number <= 100]


def archive_cap_named(text: str) -> bool:
    """The archive cap as the 4 MB quantity.

    Spacing between the digit and MB is not graded. A kilobyte figure
    such as 4000 or 4096 is the size-skip rendering, not this quantity.
    """
    return archive_mb_cap_present(text)


def kilobyte_figure_in(text: str) -> tuple[int, ...]:
    """Kilobyte renderings of the 4 MB cap named in *text*.

    4000, 4096, and both are that cap. The empty tuple is no figure:
    neither integer is present. Naming both is not a rejection. This
    does not pick one integer for an over-cap statement to sit beside.
    A bare integer, with that statement next to none of these
    renderings, is still not the report.
    """
    return tuple(
        figure for figure in ARCHIVE_KB_FIGURES if shows_integer(text, figure)
    )


def star_patterns(text: str) -> list[str]:
    found: list[str] = []
    for raw in re.findall(r"\S*\*\S*", text):
        token = raw.strip("`'\"),]")
        if token:
            found.append(token)
    return found


def prose_glob_of(pattern: str) -> str | None:
    if "{" in pattern or "}" in pattern:
        return None
    for glob in sorted(PROSE_GLOBS, key=len, reverse=True):
        if pattern == glob or pattern.endswith(glob):
            return glob
    return None


def cursor_rule_front_matter(text: str) -> str | None:
    """Interior of the closed leading front-matter block, or None if absent.

    The block opens on the first line and closes on a later line that is
    only the delimiter, the same block the body helper strips. None means
    that block is absent: the file does not open with it, or the opening
    never closes. That absence is the observation, not a failed read.
    Globs written only after the block are not part of this text. An
    empty string is a closed block with no interior.
    """
    if not isinstance(text, str):
        raise HarnessError("cursor rule is not text")
    if not text.startswith("---"):
        return None
    newline = text.find("\n")
    if newline < 0 or text[:newline].strip() != "---":
        return None
    lines = text[newline + 1 :].splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "".join(lines[:index])
    return None


def require_prose_glob_front_matter(text: str) -> None:
    """The front matter is the list that limits the rule to the prose globs.

    That list is the star tokens inside the closed leading block: the
    eight prose globs, and not ``*.py``, ``*.js``, ``*.ts``, or ``*.json``.
    Star tokens collected from the whole file, or from a body that lists
    the prose globs with no front matter, are not this list. A brace is
    not one of the eight. The body is a separate check.
    """
    if not isinstance(text, str) or not text.strip():
        raise HarnessError("cursor rule has no text")
    matter = cursor_rule_front_matter(text)
    assert matter is not None, "cursor rule has no front matter"
    patterns = star_patterns(matter)
    assert len(patterns) == 8, (
        "front matter does not list eight prose globs; "
        f"patterns={patterns!r}"
    )
    found = {prose_glob_of(pattern) for pattern in patterns}
    assert found == set(PROSE_GLOBS), (
        f"front matter glob list is {found!r}, not the prose globs"
    )
    for pattern in patterns:
        assert prose_glob_of(pattern) is not None, pattern
    for code in CODE_GLOBS:
        assert code not in matter, f"front matter includes {code}"


def age_file(path: Path, *, days: float, youth: float = 0.0) -> None:
    """Set mtime to *days* ago, then shift it by *youth* seconds.

    Positive *youth* moves the stamp toward now. Negative *youth* moves it
    further into the past, so an age can sit just past a whole-day boundary.
    It does not assert the file was removed.
    """
    stamp = time.time() - days * DAY + youth
    try:
        os.utime(path, (stamp, stamp))
    except OSError as exc:
        raise HarnessError(f"cannot set mtime on {path}: {exc}") from exc


# Same span the sweep subtracts: 7 * 24 * 3600 * 1000 milliseconds.
SEVEN_DAYS_MS = 7 * 24 * 3600 * 1000


@contextmanager
def shared_sweep_clock() -> Iterator[tuple[int, dict[str, str]]]:
    """One millisecond clock for a ledger stamp and the sweep that reads it.

    The yielded env freezes ``Date.now`` and a no-argument ``Date`` at that
    clock for the hook process. The yielded integer is the same instant, so
    an mtime can be placed at a signed offset from the seven-day cutoff the
    sweep computes. A missing or non-numeric clock fails the preload rather
    than falling through to the wall clock.
    """
    clock_ms = int(time.time() * 1000)
    tmp = Path(tempfile.mkdtemp(prefix="f06-sweep-clock-"))
    preload = tmp / "clock.js"
    preload.write_text(
        "const fixed = Number(process.env.F06_SWEEP_CLOCK_MS);\n"
        "if (!Number.isFinite(fixed)) {\n"
        "  throw new Error('F06_SWEEP_CLOCK_MS is missing');\n"
        "}\n"
        "const NativeDate = Date;\n"
        "function FrozenDate(...args) {\n"
        "  if (args.length === 0) return new NativeDate(fixed);\n"
        "  return new NativeDate(...args);\n"
        "}\n"
        "FrozenDate.now = function () { return fixed; };\n"
        "FrozenDate.parse = NativeDate.parse;\n"
        "FrozenDate.UTC = NativeDate.UTC;\n"
        "FrozenDate.prototype = NativeDate.prototype;\n"
        "global.Date = FrozenDate;\n",
        encoding="utf-8",
    )
    env = {
        "NODE_OPTIONS": f"--require={preload}",
        "F06_SWEEP_CLOCK_MS": str(clock_ms),
    }
    try:
        yield clock_ms, env
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def stamp_cutoff_offset(path: Path, clock_ms: int, offset_ms: int) -> None:
    """Place *path*'s mtime at a signed offset from the seven-day cutoff.

    The cutoff is *clock_ms* minus seven days, the same subtraction the
    sweep performs on this clock. A negative *offset_ms* is younger than
    seven days. Zero is exactly seven days. A positive *offset_ms* is older.
    """
    if not isinstance(offset_ms, int):
        raise HarnessError(f"offset_ms must be an int, got {offset_ms!r}")
    mtime_ms = (clock_ms - SEVEN_DAYS_MS) - offset_ms
    try:
        os.utime(path, ns=(mtime_ms * 1_000_000, mtime_ms * 1_000_000))
    except OSError as exc:
        raise HarnessError(f"cannot set mtime on {path}: {exc}") from exc


def clear_stored_level(ws) -> None:
    """Drop a stored level so the next read is one this document did not set.

    A missing flag is the default level. An earlier document's flag must
    not remain. A failure to remove the flag is not that default.
    """
    flag = mode_flag_path(ws.config_dir)
    try:
        if flag.is_symlink() or flag.exists():
            flag.unlink()
    except OSError as exc:
        raise HarnessError(f"cannot clear stored level at {flag}: {exc}") from exc
    if flag.exists() or flag.is_symlink():
        raise HarnessError(f"stored level still present at {flag}")


def invoke_shipped_command(ws, arguments: str, *, body: str, **kwargs) -> str:
    """Submit one command document's own body to the prompt-submit router.

    The host inserts the user's arguments only into the argument slot
    that body already contains. A body with no slot is submitted
    unchanged, so those arguments are not in the prompt the router sees.
    The document is not spawned: the router only ever sees that prompt.
    """
    if not isinstance(body, str) or body.strip() == "":
        raise HarnessError("shipped command document has no body to submit")
    placeholder = "$ARGUMENTS"
    prompt = body.replace(placeholder, arguments) if placeholder in body else body
    return command_reply(ws, prompt, **kwargs)


def command_registrations(root: Path | None = None) -> list[tuple[Path, str]]:
    """Shipped host-menu command documents, each as its own prompt body.

    After optional host front matter, the file's body is the prompt
    template. A source line that is not that body is not a document.
    No such document is a failed observation, not an empty success.
    """
    base = root if root is not None else repo_root()
    if not base.is_dir():
        raise HarnessError(f"command documents are not under a directory: {base}")
    found: list[tuple[Path, str]] = []
    skip = {".git", "node_modules", "__pycache__", ".pytest_cache"}
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [name for name in dirnames if name not in skip]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            try:
                blob = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                raise HarnessError(f"cannot read {path}: {exc}") from exc
            body = _command_document_body(blob)
            if body is None:
                continue
            found.append((path, body))
    if not found:
        raise HarnessError(
            f"no shipped host-menu command document was found under {base}"
        )
    found.sort(key=lambda item: str(item[0]))
    return found


def _command_document_body(text: str) -> str | None:
    """The prompt template when *text* is a host-menu command document.

    Optional front matter is a leading closed block. The body that
    remains is the template only when that body itself begins with the
    slash command. A later line of a different file is not this body.
    """
    if not isinstance(text, str):
        raise HarnessError("command document is not text")
    body = _without_front_matter(text).strip()
    # The namespaced spelling starts with the shorter command, so it is
    # recognised first. A longer token that merely begins with the
    # command is not the template.
    for command in (NAMED, PLAIN):
        if body == command:
            return body
        if body.startswith(command) and body[len(command)].isspace():
            return body
    return None


def _without_front_matter(text: str) -> str:
    """Text after a leading closed front-matter block.

    The block opens on the first line and closes on a later line that is
    only the delimiter. A rule later in the file is not front matter.
    An unclosed opening is not front matter either: the text stays whole.
    """
    if not text.startswith("---"):
        return text
    newline = text.find("\n")
    if newline < 0 or text[:newline].strip() != "---":
        return text
    lines = text[newline + 1 :].splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.strip() == "---":
            return "".join(lines[index + 1 :])
    return text


def prompt_via_user(ws, prompt: str, **kwargs) -> str:
    """Ordinary or command prompt through the sealed prompt entry when no extra host fields are needed."""
    result, _payload = user_prompt(ws, prompt, **kwargs)
    return delivered_text(result)


def confidence_word(text: str, word: str) -> bool:
    if word not in CONFIDENCE_WORDS:
        raise HarnessError(f"not a confidence word: {word!r}")
    return standalone_word_present(text, word)


def phrase_named(text: str, band: str) -> bool:
    return phrase_for_band(band) in text


def require_scored_row_shows(row: str, measured: Measured, name: str) -> None:
    """A scored row shows the hook phrase, the score, and the band.

    The base name is set aside first. Digits inside that name are the
    name, not the score. The hook phrase for this band, the score, and
    the band name are then required on what remains. Removing those
    three when they happen to be present is not this check. A row that
    is only the base name fails.
    """
    if not isinstance(row, str) or not row.strip():
        raise HarnessError(f"scored row has no text; row={row!r}")
    if not isinstance(name, str) or not name or name not in row:
        raise HarnessError(
            f"scored row does not name {name!r}; row={row[:400]!r}"
        )
    if not isinstance(measured.score, int) or isinstance(measured.score, bool):
        raise HarnessError(f"scored row has no integer score; score={measured.score!r}")
    left = strip_tokens(row, [name])
    phrase = phrase_for_band(measured.band)
    assert phrase in left, (
        f"scored row does not show the hook phrase {phrase!r}; row={row[:400]!r}"
    )
    assert measured.band in left, (
        f"scored row does not show the band {measured.band!r}; row={row[:400]!r}"
    )
    assert shows_integer(left, measured.score), (
        f"scored row does not show the score {measured.score}; row={row[:400]!r}"
    )


def window_named(text: str) -> bool:
    return names_window(text) or shows_integer(text, WINDOW_PLAIN) or WINDOW_GROUPED in text


def _help_words(text: str) -> list[str]:
    """Words of a help clause. Hyphens and apostrophes are not sentence boundaries."""
    folded = (
        text.lower()
        .replace("'", "")
        .replace("\u2019", "")
        .replace("-", " ")
    )
    return re.findall(r"[a-z0-9]+", folded)


def _find_after(words: Sequence[str], index: int, pred, span: int) -> int | None:
    last = min(len(words), index + 1 + span)
    for cursor in range(index + 1, last):
        if pred(words[cursor]):
            return cursor
    return None


def _either_order(words: Sequence[str], left, right, span: int = 4) -> bool:
    for index, word in enumerate(words):
        if left(word) and _find_after(words, index, right, span) is not None:
            return True
        if right(word) and _find_after(words, index, left, span) is not None:
            return True
    return False


def _is_file_word(word: str) -> bool:
    return word in {"file", "files"}


def _is_score_word(word: str) -> bool:
    return word == "score" or word.startswith("scor")


def _is_negation(word: str) -> bool:
    return word in {"no", "not", "without", "never", "dont", "doesnt", "wont"}


# ``_help_words`` deletes apostrophes, so isn't arrives as isnt. Those
# leftovers are negations of the nothing/wrong clause. They are not added
# to ``_is_negation``: the saved-files statement keeps the particles it
# already uses.
_APOSTROPHE_NEGATION = frozenset(
    {
        "aint",
        "arent",
        "cant",
        "couldnt",
        "darent",
        "didnt",
        "hadnt",
        "hasnt",
        "havent",
        "isnt",
        "mightnt",
        "mustnt",
        "neednt",
        "oughtnt",
        "shant",
        "shouldnt",
        "wasnt",
        "werent",
        "wouldnt",
    }
)


def _denial_negation(word: str) -> bool:
    """A negation scoping over the nothing/wrong clause.

    Bare particles and the forms left after apostrophes are stripped both
    count. The check runs on words ``_help_words`` has already folded.
    """
    return _is_negation(word) or word in _APOSTROPHE_NEGATION


def _affirmative_nothing_wrong(words: Sequence[str]) -> bool:
    """Whether some nothing/wrong clause has affirmative polarity.

    The clause is the short span that pairs the two content words, in
    either order. A negation in that interior, or the token immediately
    before the earlier content word, is a denial of the denial. A
    negation outside that clause is not. No pair is not the denial.
    """
    for index, word in enumerate(words):
        if word == "nothing":
            partner = "wrong"
        elif word == "wrong":
            partner = "nothing"
        else:
            continue
        later = _find_after(
            words,
            index,
            lambda item, partner=partner: item == partner,
            3,
        )
        if later is None:
            continue
        if any(_denial_negation(words[cursor]) for cursor in range(index + 1, later)):
            continue
        if index > 0 and _denial_negation(words[index - 1]):
            continue
        return True
    return False


def _negation_on(words: Sequence[str], target, span: int = 4) -> bool:
    """A denial sitting on *target*, not a free-floating 'no' elsewhere on the line."""
    for index, word in enumerate(words):
        if _is_negation(word) and _find_after(words, index, target, span) is not None:
            return True
    return False


def help_entry_line(text: str, command: str) -> str:
    """The one help line that lists *command*.

    ``off`` and ``on`` may share a line. A later use of the word inside a
    description is not another listing. Missing or repeated listings raise.
    """
    if command not in HELP_LIST:
        raise HarnessError(f"not a help-list command: {command!r}")
    hits: list[str] = []
    for raw in text.splitlines():
        if PLAIN not in raw:
            continue
        listed: list[str] = []
        # Each non-namespaced command on the line lists the words right after
        # it (Contract: a line that contains /prosecheck followed by the word;
        # off and on may share one line, as "off | on" or "off | /prosecheck on").
        for occurrence in re.finditer(re.escape(PLAIN) + r"(?![\w:])", raw):
            after = raw[occurrence.end():]
            for word in re.findall(r"[A-Za-z]+", after):
                lowered = word.lower()
                if lowered in HELP_LIST:
                    listed.append(lowered)
                    continue
                break
        if command in listed:
            hits.append(raw)
    if len(hits) != 1:
        raise HarnessError(
            f"help does not list {command} on exactly one line; "
            f"hits={hits!r} text={text[:500]!r}"
        )
    return hits[0]


def help_listed_in_command_slot(line: str) -> bool:
    """True when *line* lists help in the subcommand slot.

    The line starts with the non-namespaced command after optional leading
    whitespace. Command words are the tokens immediately after that prefix,
    the same slot the other subcommands occupy, and they stop when the
    description starts. help in that slot is a listing. A later use of the
    word, including the help command inside a description, is not.
    """
    body = line.lstrip()
    if body.startswith(NAMED) or not body.startswith(PLAIN):
        return False
    rest = body[len(PLAIN) :]
    if rest[:1].isalnum() or rest[:1] == "_":
        return False
    for word in re.findall(r"[A-Za-z]+", rest):
        lowered = word.lower()
        if lowered == "help":
            return True
        if lowered in HELP_LIST:
            continue
        break
    return False


def scope_never_touched(text: str) -> bool:
    """Each of code, commits, config, and chat is in a statement that it is not touched.

    One shared sentence or four separate sentences both count. The wording
    around the denial is not fixed.
    """
    parts = re.split(r"[.\n;!?]+", text)

    def denied(part: str) -> bool:
        if re.search(r"\buntouched\b", part, flags=re.IGNORECASE):
            return True
        words = _help_words(part)
        return _negation_on(
            words,
            lambda word: word == "touch" or word.startswith("touch"),
            span=6,
        )

    for word in ("code", "commits", "config", "chat"):
        if not any(standalone_word_present(part, word) and denied(part) for part in parts):
            return False
    return True


def states_contract_only(text: str) -> bool:
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "contract",
        lambda word: word == "only",
        span=3,
    )


def states_no_file_scoring(text: str) -> bool:
    """File scoring is denied. A bare 'no' next to some other claim does not count."""
    words = _help_words(text)

    def chain(first, second, third) -> bool:
        for index, word in enumerate(words):
            if not first(word):
                continue
            mid = _find_after(words, index, second, 4)
            if mid is None:
                continue
            if _find_after(words, mid, third, 4) is not None:
                return True
        return False

    return (
        chain(_is_negation, _is_file_word, _is_score_word)
        or chain(_is_negation, _is_score_word, _is_file_word)
        or chain(_is_file_word, _is_negation, _is_score_word)
    )


def states_contract_plus_guard(text: str) -> bool:
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "contract",
        lambda word: word in {"guard", "guards"},
        span=4,
    )


def _is_default_word(word: str) -> bool:
    return word == "default" or word.startswith("default")


def _denies_default(word: str) -> bool:
    """A particle that denies the default, including a contraction.

    ``_help_words`` has already dropped apostrophes, so isn't arrives as
    isnt. ``non`` is the prefix of non-default. ``cannot`` denies the
    claim the same way. The sentence is not fixed.
    """
    return _denial_negation(word) or word in {"cannot", "non"}


def states_guard_at_40_is_default(text: str) -> bool:
    """The guard at score 40 is the default.

    Default, the guard, and the score 40 sit in one short span, in any
    order. Parentheses around default are not required. A denial that
    governs default is not this statement. Contract plus guard, and the
    integer 40 on its own, are separate checks. A line that names the
    guard and the score and never says this is the default is not this
    statement.
    """
    words = _help_words(text)
    span = 12
    for index in range(len(words)):
        window = words[index : index + span]
        if "40" not in window or not any(word in {"guard", "guards"} for word in window):
            continue
        forty = window.index("40")
        for cursor, word in enumerate(window):
            if not _is_default_word(word):
                continue
            absolute = index + cursor
            before = words[max(0, absolute - 4) : absolute]
            if any(_denies_default(item) for item in before):
                continue
            lo, hi = sorted((cursor, forty))
            if any(_denies_default(item) for item in window[lo + 1 : hi]):
                continue
            return True
    return False


def states_character_scrub(text: str) -> bool:
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word in {"character", "characters"},
        lambda word: word == "scrub" or word.startswith("scrub"),
        span=3,
    )


def states_guard_word(text: str) -> bool:
    return "guard" in _help_words(text) or "guards" in _help_words(text)


def states_disable_and_reenable(text: str) -> bool:
    words = _help_words(text)
    disables = any(word == "disable" or word.startswith("disabl") for word in words)

    def reenable_at(index: int) -> bool:
        word = words[index]
        if word.startswith("reenabl"):
            return True
        if word != "re":
            return False
        nxt = _find_after(words, index, lambda item: item.startswith("enabl"), 1)
        return nxt is not None

    return disables and any(reenable_at(index) for index in range(len(words)))


def _is_fired_subject(word: str) -> bool:
    return word in {
        "pattern",
        "patterns",
        "tell",
        "tells",
        "label",
        "labels",
        "hit",
        "hits",
    }


def _is_empty_marker(word: str) -> bool:
    if word in {"no", "not", "none", "nothing", "zero", "without", "never"}:
        return True
    return re.fullmatch(r"x?0+", word) is not None


def _is_fired_verb(word: str) -> bool:
    return word in {"fire", "fires", "fired", "firing"}


def indicates_no_patterns_fired(text: str) -> bool:
    """Whether *text* indicates that no patterns fired.

    Word order may vary, and words may sit between the two halves. A
    denial next to patterns, tells, labels, or hits counts, and so does
    a denial that they fired. An unrelated leftover word does not.
    """
    words = _help_words(text)
    return _either_order(
        words, _is_empty_marker, _is_fired_subject, span=4
    ) or _either_order(words, _is_empty_marker, _is_fired_verb, span=4)


def states_report_only(text: str) -> bool:
    """The reply states that the result is a report only.

    Either order counts, and a hyphen is a space. The sentence around
    those two words is not fixed.
    """
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "report",
        lambda word: word == "only",
        span=3,
    )


def require_check_summary(
    text: str,
    measured: Measured,
    base: str,
    *,
    reason: bool,
) -> None:
    """The report-only summary, on whichever form opened the path.

    The base name, the hook phrase, the score, the band, and confidence
    are required. When *reason* is true the detector reason is required
    in the reply. When it is false a reason is not required. The reply
    states that this is a report only.
    """
    if not isinstance(text, str) or not text.strip():
        raise HarnessError(f"check reply is empty; base={base!r}")
    if not isinstance(base, str) or not base:
        raise HarnessError(f"check summary has no base name; base={base!r}")
    phrase = phrase_for_band(measured.band)
    assert base in text, (
        f"check reply missing base name {base!r}; text={text[:400]!r}"
    )
    assert phrase in text, (
        f"check reply missing hook phrase {phrase!r}; text={text[:400]!r}"
    )
    assert measured.band in text, (
        f"check reply missing band {measured.band!r}; text={text[:400]!r}"
    )
    assert standalone_word_present(text, measured.confidence), (
        f"check reply missing confidence {measured.confidence!r}; "
        f"text={text[:400]!r}"
    )
    assert shows_integer(text, measured.score), (
        f"check reply missing score {measured.score}; text={text[:400]!r}"
    )
    assert NOT_AUTHOR not in text
    assert states_report_only(text), text
    if reason:
        if not measured.reason:
            raise HarnessError("reason arm has no detector reason to require")
        assert measured.reason in text, (
            f"check reply missing confidence reason {measured.reason!r}; "
            f"text={text[:400]!r}"
        )


def states_scores_file_without_rewrite(text: str) -> bool:
    words = _help_words(text)
    scores_file = _either_order(words, _is_score_word, _is_file_word, span=3)
    no_rewrite = _negation_on(
        words,
        lambda word: word == "rewrite" or word.startswith("rewrit"),
        span=3,
    )
    return scores_file and no_rewrite


def states_health_check(text: str) -> bool:
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "health",
        lambda word: word in {"check", "checks", "checked", "checking"},
        span=3,
    )


def states_session_token_and_own_prose(text: str) -> bool:
    words = _help_words(text)
    token_use = _either_order(
        words,
        lambda word: word in {"token", "tokens"},
        lambda word: word in {"use", "uses", "usage"},
        span=3,
    ) and _either_order(
        words,
        lambda word: word == "session",
        lambda word: word in {"token", "tokens"},
        span=4,
    )
    prose_at = [index for index, word in enumerate(words) if word == "prose"]
    own_prose = False
    for index in prose_at:
        own_near = (
            _find_after(words, index, lambda word: word == "own", 2) is not None
            or any(words[cursor] == "own" for cursor in range(max(0, index - 2), index))
        )
        score_near = (
            _find_after(words, index, _is_score_word, 4) is not None
            or any(_is_score_word(words[cursor]) for cursor in range(max(0, index - 4), index))
        )
        if own_near and score_near:
            own_prose = True
            break
    return token_use and own_prose


def states_writes_contract_for_agents(text: str) -> bool:
    words = _help_words(text)
    writes = _either_order(
        words,
        lambda word: word in {"write", "writes", "writing", "written", "wrote"}
        or word.startswith("writ"),
        lambda word: word in {"contract", "contracts"},
        span=4,
    )
    others = _either_order(
        words,
        lambda word: word in {"other", "another"},
        lambda word: word in {"agent", "agents"},
        span=2,
    )
    return writes and others


def _window_has(words: Sequence[str], preds, span: int) -> bool:
    """Every predicate matches some word inside one span. Order is free."""
    for index in range(len(words)):
        window = words[index : index + span]
        if window and all(any(pred(word) for word in window) for pred in preds):
            return True
    return False


def _is_over_word(word: str) -> bool:
    return word in {"over", "above", "beyond"} or word.startswith("exceed")


def states_over_cap(text: str, figure: int) -> bool:
    """The file is reported as over that cap, next to the kilobyte figure.

    The figure alone is not that report. The sentence is not fixed: over,
    above, beyond, or exceed may sit a few words either side of the figure.
    """
    needles = [str(int(figure))]
    grouped = f"{int(figure):,}"
    if grouped != needles[0]:
        needles.append(grouped)
    for needle in needles:
        pattern = rf"(?<!\d){re.escape(needle)}(?!\d)"
        for match in re.finditer(pattern, text):
            start = max(0, match.start() - 48)
            end = min(len(text), match.end() + 48)
            if any(_is_over_word(word) for word in _help_words(text[start:end])):
                return True
    return False


def states_not_a_file(text: str) -> bool:
    """The path is reported as not a file. The sentence around that is not fixed.

    A separate denial of a score does not cancel that report. Without a
    score is the absence of a 0-100 integer, checked after the path is
    removed, not a second negation sitting near a score word.
    """
    words = _help_words(text)
    return _window_has(
        words,
        (_is_negation, lambda word: word == "file"),
        span=3,
    )


def _cannot_words(text: str) -> list[str]:
    """Help words with the forms of "cannot" folded to one token.

    can not, could not, couldn't, can't, and unable to all say it cannot.
    """
    words = _help_words(text)
    out: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        nxt = words[index + 1] if index + 1 < len(words) else ""
        if word in {"can", "could"} and nxt == "not":
            out.append("cannot")
            index += 2
            continue
        if word == "unable" and nxt == "to":
            out.append("cannot")
            index += 2
            continue
        if word in {"cant", "couldnt", "unable"}:
            out.append("cannot")
        else:
            out.append(word)
        index += 1
    return out


def states_cannot_read(text: str) -> bool:
    """The path cannot be read. Word order may vary by a couple of words."""
    return _either_order(
        _cannot_words(text),
        lambda word: word == "cannot",
        lambda word: word == "read" or word.startswith("read"),
        span=3,
    )


def states_no_readable_text(text: str) -> bool:
    """There is no readable text. A bare 'empty' is not that report."""
    words = _help_words(text)
    return _window_has(
        words,
        (
            _is_negation,
            lambda word: word == "readable",
            lambda word: word in {"text", "texts"},
        ),
        span=5,
    )


def states_detector_unavailable(text: str) -> bool:
    """The detector is unavailable. Naming Python alone is not that report."""
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word in {"detector", "detectors"},
        lambda word: word == "unavailable" or word.startswith("unavail"),
        span=4,
    )


def _leading_span_word(word: str) -> bool:
    return word == "first" or word == "prefix" or word.startswith("prefix")


def _limitation_word(word: str) -> bool:
    return word == "only" or word == "include" or word.startswith("includ")


def states_only_prefix_scored(text: str) -> bool:
    """The coverage line names the 262,144 window and that only that prefix was included.

    The window digits anchor the line. The prefix is a leading-span word
    on that line (first or prefix). The inclusion is a limitation word
    on that line (only, or include). Digits alone, or digits with only
    one of those two, are not the statement. The verb scored is not
    required. The sentence is not fixed.
    """
    for match in re.finditer(r"(?<!\d)(?:262,144|262144)(?!\d)", text):
        clause = _coverage_clause(text, match.start(), match.end())
        words = _help_words(clause)
        if any(_leading_span_word(word) for word in words) and any(
            _limitation_word(word) for word in words
        ):
            return True
    return False


def _coverage_clause(text: str, start: int, end: int) -> str:
    """The line that holds the window digits. A later line does not supply words."""
    left = text.rfind("\n", 0, start)
    right = text.find("\n", end)
    if right < 0:
        right = len(text)
    return text[left + 1:right]


def _expand_closer_contractions(text: str) -> str:
    """Expand the closer's contractions before it is split into words.

    A straight apostrophe and a typographic apostrophe (U+2019) are the
    same mark. ``n't`` becomes ``not``. ``'s`` after the subject ``it``
    or ``tool`` becomes ``is``. A token with no apostrophe, such as
    ``its``, is left unchanged. Apostrophes are not deleted.
    """
    folded = text.lower().replace("\u2019", "'")
    folded = re.sub(r"n't\b", " not", folded)
    return re.sub(r"\b(it|tool)'s\b", r"\1 is", folded)


def _closer_words(text: str) -> list[str]:
    """Words of the healthy closer, after contractions are expanded.

    Hyphens are spaces. Remaining apostrophes stay as boundaries, so a
    fused token is not created by deleting them.
    """
    folded = _expand_closer_contractions(text).replace("-", " ")
    return re.findall(r"[a-z0-9]+", folded)


def states_tool_is_on(text: str) -> bool:
    """The closer affirms that the tool is on.

    The subject is the noun ``tool``, or the pronoun ``it`` standing for
    that tool. The noun is not required. ``is`` may be its own word, or
    ``'s`` contracted onto that subject. A negation between the subject
    and ``on`` — including ``n't`` expanded to ``not``, and ``not`` after
    a contracted ``is`` — is a denial, not that affirmation. Caps and a
    stray ``on`` are not that affirmation.
    """
    words = _closer_words(text)
    for index, word in enumerate(words):
        if word not in {"tool", "it"}:
            continue
        is_at = _find_after(words, index, lambda item: item == "is", 3)
        if is_at is None:
            continue
        if any(_is_negation(words[cursor]) for cursor in range(index + 1, is_at)):
            continue
        on_at = _find_after(words, is_at, lambda item: item == "on", 2)
        if on_at is None:
            continue
        if any(_is_negation(words[cursor]) for cursor in range(is_at + 1, on_at)):
            continue
        return True
    return False


def points_at_show_command(text: str, form: str) -> bool:
    """The follow-up is the show command in *form*, not a longer word."""
    return standalone_word_present(text, "show") and f"{form} show" in text


def _show_form_word_index(text: str, form: str) -> int | None:
    """Index of ``show`` in the command *form*, in ``_help_words`` order."""
    needle = f"{form} show"
    start = text.find(needle)
    if start < 0:
        return None
    return len(_help_words(text[:start])) + len(_help_words(form))


def points_at_show_for_partial_or_skipped(text: str, form: str) -> bool:
    """The show command in *form* is the pointer for partial or skipped checks.

    Naming that command is not enough. Partial, skipped, and check have to
    sit with it, in either order, a few words apart. The sentence is not
    fixed. The words for and or are not required.
    """
    if not points_at_show_command(text, form):
        return False
    words = _help_words(text)
    index = _show_form_word_index(text, form)
    if index is None or index >= len(words) or words[index] != "show":
        return False
    window = words[max(0, index - 8) : index + 9]
    return _window_has(
        window,
        (
            lambda word: word == "show",
            lambda word: word.startswith("partial"),
            lambda word: word.startswith("skip"),
            lambda word: word.startswith("check"),
        ),
        span=10,
    )


def points_at_on_command(text: str, form: str) -> bool:
    """The follow-up turns the tool on in *form*, not a longer word.

    The command is that form followed by the subcommand on. A line that
    only names the form, or only the word on, is not this follow-up.
    """
    return standalone_word_present(text, "on") and f"{form} on" in text


def states_fix_lines_and_rerun_doctor(text: str) -> bool:
    """Asks for the faulty lines to be fixed and for doctor to be run again."""
    words = _help_words(text)
    fixes = _either_order(
        words,
        lambda word: word == "fix" or word.startswith("fix"),
        lambda word: word in {"line", "lines"},
        span=4,
    )
    again = _either_order(
        words,
        lambda word: word == "doctor",
        lambda word: word == "again",
        span=3,
    )
    return fixes and again


def _states_python_absence(words: Sequence[str]) -> bool:
    """Python is named together with an absence. The sentence is not fixed."""
    for index, word in enumerate(words):
        if word != "python":
            continue
        window = words[max(0, index - 4) : index + 5]
        if any(item == "missing" or item == "absent" or item.startswith("unavail") for item in window):
            return True
        denies = any(
            _is_negation(item) or item == "cannot" or item in _APOSTROPHE_NEGATION
            for item in window
        )
        sought = any(item == "found" or item.startswith("find") for item in window)
        if denies and sought:
            return True
    return False


def states_python_missing(text: str) -> bool:
    """The line says Python is missing.

    Python sits with an absence: missing, or a denial that Python was
    found. The sentence is not fixed. The word Python with no absence
    is not enough.
    """
    return _states_python_absence(_help_words(text))


def states_prose_still_shaped(text: str) -> bool:
    """Prose is still shaped. The sentence around those words is not fixed."""
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "prose",
        lambda word: word == "shaped" or word.startswith("shap"),
        span=4,
    )


def states_nothing_wrong(text: str) -> bool:
    """The closer denies that anything is wrong.

    The denial is one clause: nothing paired with wrong, a few words
    apart, in either order, and only when that clause is affirmative. A
    negation inside the span, or the token immediately before the earlier
    content word, including a contraction left after apostrophes are
    stripped, is not this denial. A later negation outside the clause is
    not either. The noun install is not part of the denial, and the word
    off is not a substitute for the pair.
    """
    return _affirmative_nothing_wrong(_help_words(text))


def states_nothing_wrong_with_install(text: str) -> bool:
    """The closer denies that anything is wrong.

    Same clause as ``states_nothing_wrong``: affirmative polarity of the
    nothing/wrong span. The noun install is not required. The word off
    anywhere, with no such clause, is not this denial.
    """
    return _affirmative_nothing_wrong(_help_words(text))


def states_saved_files_not_scored_until_on(text: str) -> bool:
    """Saved files are not scored.

    A generic denial of file scoring is not this statement, and neither
    is 'not re-scored'. The denial has to name saved files. The word
    until, and on following the denial, are not part of this statement.
    The words may sit a few apart. The sentence is not fixed.
    """
    located = _not_scored_span(text)
    if located is None:
        return False
    neg, scored = located
    words = _help_words(text)
    window = words[max(0, neg - 6) : scored + 1]
    if not any(item == "saved" for item in window):
        return False
    return any(_is_file_word(item) for item in window)


def off_only_closer_lines(text: str) -> list[str]:
    """Off-only closer lines: nothing is wrong, and saved files are not scored.

    The closer is that line. A command token does not select it, and the
    line does not have to be the only one that names a command.
    """
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if states_nothing_wrong_with_install(line) and states_saved_files_not_scored_until_on(
            line
        ):
            found.append(line)
    return found


def off_marked_mode_lines(text: str) -> list[str]:
    """Current-mode checks marked off, other than the off-only closer.

    The stored level names the line. A command token does not, and neither
    does a bracket spelling. The closer also names off, so it is not this
    check. Another line that names a command can stay.
    """
    closers = set(off_only_closer_lines(text))
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line in closers:
            continue
        if states_current_mode_line(line, "off"):
            found.append(line)
    return found


def states_nothing_scored_yet(text: str) -> bool:
    """Nothing has been scored yet. The suffixes alone are not that statement."""
    words = _help_words(text)
    return _window_has(
        words,
        (
            lambda word: word == "nothing",
            _is_score_word,
            lambda word: word == "yet",
        ),
        span=6,
    )


def states_list_fills_once_deliverable_saved(text: str) -> bool:
    """The list fills in once a prose file or a deliverable is saved.

    Word order may vary inside that clause. The sentence is not fixed.
    The ``.docx`` and ``.pdf`` suffixes are a separate check.
    """
    words = _help_words(text)
    return _window_has(
        words,
        (
            lambda word: word == "list",
            lambda word: word == "fill" or word.startswith("fill"),
            lambda word: word == "once",
            lambda word: word == "prose",
            lambda word: word == "file" or word.startswith("file"),
            lambda word: word == "deliverable" or word.startswith("deliver"),
            lambda word: word == "save" or word.startswith("sav"),
        ),
        span=18,
    )


# Words a polarity particle looks through on its way to the claim.
# They are not the claim, and they are not a list of negation spellings.
_CLAIM_SCAFFOLD = frozenset(
    {
        "a",
        "am",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "but",
        "by",
        "file",
        "files",
        "for",
        "had",
        "has",
        "have",
        "if",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "so",
        "that",
        "the",
        "these",
        "this",
        "those",
        "to",
        "was",
        "were",
        "with",
    }
)


def _polarity_particle(word: str) -> bool:
    """A particle that can govern a claim, wherever it sits in the clause.

    Contractions that ``_help_words`` folds by deleting the apostrophe
    are the same particle. ``non`` is that particle as a prefix. This is
    not a catalogue of example sentences.
    """
    return _denial_negation(word) or word == "non"


def _claim_scaffold(word: str) -> bool:
    return word in _CLAIM_SCAFFOLD and not _polarity_particle(word)


def _polarity_clauses(text: str) -> list[str]:
    """Clauses a claim can occupy.

    A sentence boundary, a comma, a colon, a semicolon, or a dash ends
    the clause. A hyphen inside a word does not, so a prefixed particle
    stays with the word it governs.
    """
    parts = re.split(r"[\n;.!?:…,]+|\s+--\s+|\s+-\s+|[—–]", text)
    return [part.strip() for part in parts if part.strip()]


def _claim_spans(words: Sequence[str], predicates: Sequence) -> list[tuple[int, int]]:
    """Spans that hold every part of one claim, in either order.

    The span is the claim, not a fixed distance around one token. One
    part is each index where that part matches. Two parts are each pair.
    """
    if len(predicates) == 1:
        pred = predicates[0]
        return [(index, index) for index, word in enumerate(words) if pred(word)]
    if len(predicates) != 2:
        raise HarnessError("a show claim has one part or two")
    left, right = predicates
    spans: list[tuple[int, int]] = []
    for index, word in enumerate(words):
        if not left(word):
            continue
        for other in range(len(words)):
            if other == index or not right(words[other]):
                continue
            spans.append((min(index, other), max(index, other)))
    return spans


def _negation_scopes_claim(words: Sequence[str], start: int, end: int) -> bool:
    """Whether a polarity particle governs the claim span.

    Inside the span, the particle denies the claim. Before the span, it
    governs the claim when only scaffold sits between them. After the
    span, it governs the claim when it does not attach to some later
    content word. A particle that attaches to a different claim does
    not flip this one.
    """
    for index, word in enumerate(words):
        if not _polarity_particle(word):
            continue
        if start < index < end:
            return True
        if index < start:
            if all(_claim_scaffold(item) for item in words[index + 1 : start]):
                return True
            continue
        if not all(_claim_scaffold(item) for item in words[end + 1 : index]):
            continue
        later = words[index + 1 :]
        if any(
            not _polarity_particle(item) and not _claim_scaffold(item) for item in later
        ):
            continue
        return True
    return False


def _bare_polarity_clause(clause: str) -> bool:
    """A clause that is only a polarity particle aimed at the clause before it."""
    words = _help_words(clause)
    if not words or not any(_polarity_particle(word) for word in words):
        return False
    return all(_polarity_particle(word) or _claim_scaffold(word) for word in words)


def _clause_affirms_claim(
    words: Sequence[str],
    predicates: Sequence,
    *,
    bare_predicate: bool,
) -> bool:
    """Affirmative polarity of one claim inside one clause.

    A span the particle governs is the denial. When *bare_predicate* is
    set, a clause that is only the predicate token is not the claim:
    the token is not an affirmation that the file was flagged.
    """
    for start, end in _claim_spans(words, predicates):
        if _negation_scopes_claim(words, start, end):
            continue
        if bare_predicate:
            extras = [
                word
                for index, word in enumerate(words)
                if not start <= index <= end and not _polarity_particle(word)
            ]
            if not extras:
                continue
        return True
    return False


def _show_claim_affirmative(
    text: str,
    predicates: Sequence,
    *,
    bare_predicate: bool,
) -> bool:
    """Whether *text* affirms one show claim.

    Both show facts use this polarity. The predicates are the parts of
    the claim. A following clause that is only a polarity particle
    denies the claim it follows, so a negation after the claim flips it.
    """
    if not isinstance(text, str):
        raise HarnessError("show claim has no text")
    clauses = _polarity_clauses(text)
    for index, clause in enumerate(clauses):
        if not _clause_affirms_claim(
            _help_words(clause),
            predicates,
            bare_predicate=bare_predicate,
        ):
            continue
        if index + 1 < len(clauses) and _bare_polarity_clause(clauses[index + 1]):
            continue
        return True
    return False


def states_flagged(text: str) -> bool:
    """The clause affirms that the file was flagged.

    One claim, affirmative polarity. A particle that governs that claim
    denies it, before the claim or after it. The word flagged with
    nothing else in the clause is the token, not the affirmation. The
    sentence is not fixed.
    """
    if _show_claim_affirmative(
        text,
        (lambda word: word == "flagged",),
        bare_predicate=True,
    ):
        return True
    # "flagged:" heading the fired labels is the same affirmation; a heading
    # followed only by a denial, a number, or nothing is not.
    clauses = _polarity_clauses(text)
    for index, clause in enumerate(clauses[:-1]):
        if _help_words(clause) != ["flagged"]:
            continue
        following = _help_words(clauses[index + 1])
        content = [
            word
            for word in following
            if re.search(r"[a-z]", word)
            and not _polarity_particle(word)
            and word not in {"none", "nothing", "false", "nil", "null", "n", "a"}
        ]
        if content and not any(_polarity_particle(word) for word in following):
            return True
    return False


def states_under_threshold(text: str) -> bool:
    """The clause affirms that it was under the threshold.

    One claim: the two words in either order, affirmative polarity. A
    denial of that claim is not the affirmation, between the words or
    after them. The word flagged in another claim does not flip this
    one. The sentence is not fixed.
    """
    return _show_claim_affirmative(
        text,
        (
            lambda word: word == "under",
            lambda word: word == "threshold",
        ),
        bare_predicate=False,
    )


def states_not_rescored(text: str) -> bool:
    """The file was not re-scored. A bare 'skipped' is not that statement."""
    words = _help_words(text)
    for index, word in enumerate(words):
        if not _is_negation(word):
            continue
        if index + 1 < len(words) and words[index + 1] == "re":
            if _find_after(words, index + 1, _is_score_word, 2) is not None:
                return True
    return False


def states_saved_files_not_rescored(text: str) -> bool:
    """Saved files are not re-scored.

    A denial of file scoring that never says the files were saved and
    were not re-scored is not this statement. The words may sit a few
    apart. The sentence is not fixed.
    """
    words = _help_words(text)
    for index, word in enumerate(words):
        if not _is_negation(word):
            continue
        if index + 1 >= len(words) or words[index + 1] != "re":
            continue
        scored = _find_after(words, index + 1, _is_score_word, 2)
        if scored is None:
            continue
        window = words[max(0, index - 6) : scored + 1]
        saved = any(item == "saved" for item in window)
        files = any(_is_file_word(item) for item in window)
        if saved and files:
            return True
    return False


def states_python_missing_statement(text: str) -> bool:
    """The report used when Python cannot be launched, as one statement.

    That line names Python together with that absence. Saying Python is
    missing and denying that Python was found are the same report; the
    token missing is not required. The same line states that prose is
    still shaped and that saved files are not re-scored. A faulty Python
    line that does not make all three claims is a different statement.
    The words numeric score are not part of this statement.
    """
    return (
        states_python_missing(text)
        and states_prose_still_shaped(text)
        and states_saved_files_not_rescored(text)
    )


def states_not_scored(text: str) -> bool:
    """The file was not scored. 'not re-scored' is the other row's statement."""
    return _not_scored_span(text) is not None


def require_size_skip_row(row: str, name: str, limits: Sequence[int]) -> tuple[int, ...]:
    """The show row names this class's kilobyte limit and says it was not scored.

    *limits* is the cap this file class records: 512 for plain text, or
    4000 and 4096 for an archive or notebook. The base name is set aside
    first, so digits in that name are not the limit. An archive or
    notebook row passes when it names 4000, when it names 4096, and when
    it names both, and it says the file was not scored. A row that says
    the file was not scored and names neither integer of its own limit
    fails. Naming the other class's limit fails: an archive or notebook
    row that names 512, and a plain-text row that names 4000 or 4096.
    The sentence is not fixed.
    """
    if not isinstance(row, str) or not row.strip():
        raise HarnessError(f"size-skip row has no text; row={row!r}")
    if not isinstance(name, str) or not name or name not in row:
        raise HarnessError(
            f"size-skip row does not name {name!r}; row={row[:400]!r}"
        )
    if isinstance(limits, (str, bytes)) or not isinstance(limits, Sequence):
        raise HarnessError(f"size-skip limits are not a sequence: {limits!r}")
    allowed: list[int] = []
    for limit in limits:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise HarnessError(f"size-skip limit is not an integer: {limit!r}")
        allowed.append(int(limit))
    known = (PLAIN_KB, *ARCHIVE_KB_FIGURES)
    if not allowed or any(limit not in known for limit in allowed):
        raise HarnessError(f"size-skip limits {allowed!r} are not a class cap")
    body = strip_tokens(row, [name])
    if not body:
        raise HarnessError(
            f"size-skip row is only the file name; row={row[:400]!r}"
        )
    named = [limit for limit in allowed if shows_integer(body, limit)]
    assert named, (
        f"size-skip row names no kilobyte figure for {tuple(allowed)}; "
        f"row={row[:400]!r}"
    )
    others = [
        limit
        for limit in known
        if limit not in allowed and shows_integer(body, limit)
    ]
    assert not others, (
        f"size-skip row names the other class limit {others}; "
        f"row={row[:400]!r}"
    )
    assert states_not_scored(body), (
        f"size-skip row does not say the file was not scored; row={row[:400]!r}"
    )
    return tuple(named)


_NOT_SCORED_SCAFFOLD = frozenset(
    {
        "a",
        "an",
        "and",
        "been",
        "file",
        "files",
        "for",
        "had",
        "has",
        "have",
        "is",
        "it",
        "of",
        "or",
        "the",
        "this",
        "to",
        "was",
        "were",
    }
)


def _not_scored_span(text: str) -> tuple[int, int] | None:
    """Indexes of the negation and the score word in a not-scored statement."""
    words = _help_words(text)
    for index, word in enumerate(words):
        if not _is_negation(word):
            continue
        nxt = _find_after(words, index, _is_score_word, 2)
        if nxt is None:
            continue
        if "re" in words[index + 1 : nxt]:
            continue
        return index, nxt
    return None


def states_readable_failure_reason(text: str) -> bool:
    """The not-scored statement is followed by a reason a person can read.

    The path is already gone. The reason's sentence is not fixed: any
    leftover word that is not the statement itself counts. A row that only
    says the file was not scored leaves nothing.
    """
    span = _not_scored_span(text)
    if span is None:
        return False
    words = _help_words(text)
    start, end = span
    rest = [
        word
        for index, word in enumerate(words)
        if index not in {start, end} and word not in _NOT_SCORED_SCAFFOLD
    ]
    return any(re.fullmatch(r"[a-z]{3,}", word) for word in rest)


def states_section_already_present(text: str) -> bool:
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "already",
        lambda word: word == "present",
        span=3,
    )


def states_rule_already_there(text: str) -> bool:
    """The rule is already there. 'already' next to the rule is that report.

    The rule may be named as the rule or by its path under .cursor/rules.
    Both words sit on one line, so an 'already' said about AGENTS.md on
    another line is not this report.
    """
    return any(
        _either_order(
            _help_words(line),
            lambda word: word in {"rule", "rules"},
            lambda word: word == "already",
            span=4,
        )
        for line in text.splitlines()
    )


def require_outside_text_in_place(text: str, outside: str) -> None:
    """Text that already sat outside the contract section is still those bytes.

    *outside* is the text that was in the file before init, including the
    newline the caller wrote. The export must still begin with that text:
    the section is appended, and the earlier bytes stay where they were.
    An empty export, or outside text with no bytes, is a failure to
    observe, not an unchanged file.
    """
    if not isinstance(outside, str) or outside == "":
        raise HarnessError("outside text has no bytes")
    if not isinstance(text, str) or text == "":
        raise HarnessError("export has no text to compare with the outside bytes")
    try:
        outside_bytes = outside.encode("utf-8")
        text_bytes = text.encode("utf-8")
    except UnicodeError as exc:
        raise HarnessError(f"export text is not utf-8: {exc}") from exc
    assert text_bytes.startswith(outside_bytes), (
        "text outside the contract section is not the original bytes"
    )


def require_same_rule_bytes(path: Path, shipped: bytes) -> None:
    """The Cursor rule file is the shipped copy init already wrote.

    A missing path is a failure, not an unchanged rule. Bytes that differ
    from that copy are a different file. An unreadable path is a failure
    too: the helper has no bytes to compare.
    """
    if not isinstance(shipped, (bytes, bytearray)) or not bytes(shipped):
        raise HarnessError("shipped cursor rule has no bytes")
    if not path.is_file():
        raise HarnessError(f"cursor rule was not written: {path}")
    try:
        found = path.read_bytes()
    except OSError as exc:
        raise HarnessError(f"cursor rule could not be read: {path}: {exc}") from exc
    assert found == bytes(shipped)


def require_contract_section(text: str, *, word: str, count: int) -> None:
    """One copy of the full-level writing contract.

    The banned-vocabulary list, the score-40 target, and clean or light
    tells are that contract. *count* is how many times *word* stood alone
    in the first export, and *word* is one that export actually contained.
    A missing contract has a lower count. A second copy of the section
    has a higher count. An empty file is not the contract.
    """
    if count < 1:
        raise HarnessError("first export did not contain the contract word")
    if not word or not str(text).strip():
        raise HarnessError("contract section check has no export text")
    require_full_scoring(text)
    found = standalone_count(text, word)
    assert found == count, (
        f"contract section count for {word!r} is {found}, first export had {count}"
    )


def states_on_enables_export(text: str) -> bool:
    """On enables export. The word off alone is not that statement."""
    words = _help_words(text)
    return _window_has(
        words,
        (
            lambda word: word == "on",
            lambda word: word == "enable" or word.startswith("enabl"),
            lambda word: word == "export" or word.startswith("export"),
        ),
        span=5,
    )


def states_switched_off(text: str) -> bool:
    """The reply says it is switched off.

    Switched and off sit together. The word off alone is not that
    statement, and neither is a longer word that merely begins with
    switched. The sentence is not fixed.
    """
    words = _help_words(text)
    return _either_order(
        words,
        lambda word: word == "switched",
        lambda word: word == "off",
        span=3,
    )


def _on_command_indexes(text: str, form: str) -> list[int]:
    """Word indexes of ``on`` in the command *form* followed by that subcommand.

    A longer word glued to on, and a namespaced token that is not this
    command, are not indexes. The form is the spelling the user typed.
    """
    needle = f"{form} on"
    words = _help_words(text)
    found: list[int] = []
    start = 0
    while start <= len(text):
        at = text.find(needle, start)
        if at < 0:
            break
        end = at + len(needle)
        if end < len(text) and (text[end].isalnum() or text[end] == "_"):
            start = at + 1
            continue
        if at > 0 and (text[at - 1].isalnum() or text[at - 1] == "_"):
            start = at + 1
            continue
        index = len(_help_words(text[:end])) - 1
        if 0 <= index < len(words) and words[index] == "on":
            found.append(index)
        start = at + 1
    return found


def states_typed_on_enables_export(text: str, form: str) -> bool:
    """The follow-up that on enables export is the on command in *form*.

    That command is *form* followed by the subcommand on. Enable and
    export sit with that on inside one span of five words, in any order.
    Words on, enable, and export in one window, with the command missing,
    are not this follow-up. A namespaced token in some other clause is
    not this command, and neither is that token followed by on when the
    enable and export words sit with a different on. The sentence is not
    fixed.
    """
    words = _help_words(text)
    for index in _on_command_indexes(text, form):
        start_min = max(0, index - 4)
        for start in range(start_min, index + 1):
            window = words[start : start + 5]
            if index >= start + len(window):
                continue
            enabled = any(
                word == "enable" or word.startswith("enabl") for word in window
            )
            exported = any(
                word == "export" or word.startswith("export") for word in window
            )
            if enabled and exported:
                return True
    return False


def states_cannot_write(text: str) -> bool:
    """The refusal says it cannot write. An empty reply is not that report."""
    return _either_order(
        _cannot_words(text),
        lambda word: word == "cannot",
        lambda word: word == "write" or word.startswith("writ"),
        span=3,
    )


def states_cannot_read_or_write(text: str) -> bool:
    """A read or write refusal says it cannot. Silence is not that report."""
    return states_cannot_write(text) or states_cannot_read(text)


def cursor_rule_body(text: str) -> str:
    """The Cursor rule after a closed front-matter block.

    A file with no front matter is all body. Front matter that does not
    close, or that leaves no body, is not an observation.
    """
    if not isinstance(text, str) or not text.strip():
        raise HarnessError("cursor rule has no text")
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3 or not parts[2].strip():
        raise HarnessError("cursor rule front matter does not leave a body")
    return parts[2]


def states_prose_only_scope(text: str) -> bool:
    """The writing contract's prose-only scope: prose deliverables only.

    The three words may sit a few apart, in any order. A body that never
    states that scope is not a match, and neither is a denial that the
    contract applies to source code.
    """
    words = _help_words(text)
    return _window_has(
        words,
        (
            lambda word: word == "prose",
            lambda word: word == "deliverable" or word.startswith("deliverable"),
            lambda word: word == "only",
        ),
        span=6,
    )


def require_strict_clean_band_apart(strict_text: str, lite_text: str) -> None:
    """Strict names the ``clean`` band apart from the cleanup-switch spelling.

    The switch spelling is removed first, so a ``clean`` that exists only
    inside that spelling is not the band. The lite export is the live
    baseline that omits the post-write targets: a ``clean`` whose nearby
    words already appear there is that shared contract, not the strict
    target. At least one ``clean`` on strict must sit in words the lite
    export does not.
    """
    if not str(strict_text).strip() or not str(lite_text).strip():
        raise HarnessError("strict clean-band check has no export text")
    flag = cleanup_switch()
    if not isinstance(flag, str) or not flag.strip():
        raise HarnessError("usage did not name a cleanup switch")
    strict_left = re.sub(re.escape(flag), " ", str(strict_text), flags=re.IGNORECASE)
    lite_left = re.sub(re.escape(flag), " ", str(lite_text), flags=re.IGNORECASE)
    strict_words = _help_words(strict_left)
    lite_blob = " ".join(_help_words(lite_left))
    if not strict_words or not lite_blob:
        raise HarnessError("strict clean-band check could not read export words")
    radius = 4
    apart = False
    for index, word in enumerate(strict_words):
        if word != "clean":
            continue
        lo = max(0, index - radius)
        hi = min(len(strict_words), index + radius + 1)
        window = " ".join(strict_words[lo:hi])
        if window not in lite_blob:
            apart = True
            break
    assert apart, (
        "strict contract does not name the clean band apart from the "
        "cleanup switch and the lite export"
    )


# Words that may sit between a negation and the detector without taking
# the negation for themselves. A content word in that gap is a different
# claim. The command that runs the detector is not in this list.
_DETECTOR_DENIAL_GAP = frozenset(
    {
        "a",
        "an",
        "any",
        "bundled",
        "call",
        "calling",
        "calls",
        "even",
        "ever",
        "execute",
        "executes",
        "executing",
        "file",
        "files",
        "for",
        "in",
        "invoke",
        "invokes",
        "invoking",
        "it",
        "its",
        "just",
        "of",
        "on",
        "please",
        "prose",
        "ran",
        "run",
        "running",
        "runs",
        "that",
        "the",
        "this",
        "to",
        "use",
        "uses",
        "using",
        "we",
        "you",
        "your",
    }
)
_DETECTOR_COPULA = frozenset(
    {
        "are",
        "be",
        "been",
        "can",
        "could",
        "is",
        "may",
        "must",
        "shall",
        "should",
        "was",
        "were",
        "will",
        "would",
    }
)
_DETECTOR_OBLIGATION = frozenset(
    {
        "allowed",
        "called",
        "invoked",
        "necessary",
        "needed",
        "ran",
        "required",
        "requirement",
        "run",
        "running",
        "used",
    }
)


def _period_ends_statement(text: str, index: int) -> bool:
    """A period that ends a statement, not a dot inside a token.

    ``detect.py`` and ``.md`` keep their dots. A period followed by a
    space, or sitting at the end of the text, ends the statement.
    """
    if index + 1 < len(text) and not text[index + 1].isspace():
        return False
    return index > 0 and text[index - 1].isalnum()


def _rule_statements(text: str) -> list[str]:
    """Statements of a rule body. A newline or a sentence end splits them.

    A colon stays inside the statement, so a command written after a
    colon is still the same instruction. An empty piece is not a statement.
    """
    parts: list[str] = []
    buf: list[str] = []
    for index, ch in enumerate(text):
        if ch in "\n;!?":
            parts.append("".join(buf))
            buf = []
            continue
        if ch == "." and _period_ends_statement(text, index):
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return [part for part in parts if part.strip()]


def _is_detect_word(word: str) -> bool:
    return word.startswith("detect")


def _is_write_word(word: str) -> bool:
    return word.startswith("writ")


def _step_denial_word(word: str) -> bool:
    return _denial_negation(word) or word == "cannot"


def _negation_scopes_detector(words: Sequence[str], index: int) -> bool:
    """A negation in front of the detector word governs that word.

    The gap may hold only the short scaffolding of the instruction.
    A negation that sits on a different claim in the same statement,
    with a content word between, does not govern the detector.
    """
    start = max(0, index - 8)
    for cursor in range(index - 1, start - 1, -1):
        word = words[cursor]
        if _step_denial_word(word):
            return True
        if word not in _DETECTOR_DENIAL_GAP:
            return False
    return False


def _detector_claim_denied_after(words: Sequence[str], index: int) -> bool:
    """A negation after the detector word flips that claim.

    ``the detector is not required`` denies the step. ``the detector,
    not a second tool`` names something else and does not.
    """
    last = min(len(words), index + 8)
    for cursor in range(index + 1, last):
        if not _step_denial_word(words[cursor]):
            continue
        before = words[cursor - 1]
        after = words[cursor + 1 : cursor + 4]
        if before in _DETECTOR_COPULA:
            return True
        if any(
            item in _DETECTOR_OBLIGATION
            or item.startswith("requir")
            or item.startswith("need")
            for item in after
        ):
            return True
    return False


def _statement_runs_detector_after_write(words: Sequence[str]) -> bool:
    """One statement tells the agent to run the detector after a write.

    ``after`` sits within three words of a write-word, and a detector
    word in this same statement is not denied. The command spelling is
    not fixed. A denial of the step is not this statement.
    """
    if not _either_order(
        words,
        lambda word: word == "after",
        _is_write_word,
        span=3,
    ):
        return False
    for index, word in enumerate(words):
        if not _is_detect_word(word):
            continue
        if _negation_scopes_detector(words, index):
            continue
        if _detector_claim_denied_after(words, index):
            continue
        return True
    return False


def states_post_write_detector(text: str) -> bool:
    """Whether *text* carries the post-write detector step.

    The step is one statement that tells the agent to run the detector
    after a write. A denial of that step does not carry it. A write word
    and a detector word that are not that one statement do not carry it.
    The sentence is not fixed, and the command that runs the detector is
    not fixed. A banned-word list with no such step is not this statement.
    The Cursor rule must omit the step. The exported contract is not
    required to contain it: that host-followable sentence is narrative of
    the post-write scoring extra, not a required stem.
    """
    if not isinstance(text, str):
        raise HarnessError("post-write detector check has no rule text")
    return any(
        _statement_runs_detector_after_write(_help_words(statement))
        for statement in _rule_statements(text)
    )


def node_kept_without_interpreters() -> dict[str, str]:
    """A PATH with no Python, and a node symlink so the hook can still start.

    The sealed no-interpreter path is empty. The hook process is started
    by name, so node has to remain visible or the probe cannot run.
    """
    from F05_helpers import updates_without_interpreters

    updates = updates_without_interpreters()
    node = shutil.which("node")
    if not node:
        raise HarnessError("node is not on PATH before the no-python arm")
    link = Path(updates["PATH"]) / "node"
    link.symlink_to(node)
    if shutil.which("python3", path=updates["PATH"]) or shutil.which(
        "python", path=updates["PATH"]
    ):
        raise HarnessError("python is still visible after interpreters were removed")
    return updates


@contextmanager
def emitted_failure_standin(ws, text: str) -> Iterator[Standin]:
    """Plant interpreters that emit *text* and then exit non-zero.

    The failure is that text. An empty body is not this case, and the
    exit status is not the failure. A probe that does not run raises.
    """
    if text is None or not str(text).strip():
        raise HarnessError("a stated failure has no text the detector emitted")
    root = Path(tempfile.mkdtemp(prefix="f06-fail-"))
    log = root / "invocations.log"
    log.write_text("", encoding="utf-8")
    script = "\n".join(
        [
            "#!/bin/sh",
            f"log={shlex.quote(str(log))}",
            'if [ -z "$log" ]; then echo "stand-in log unset" >&2; exit 97; fi',
            'echo invoked >> "$log"',
            'if [ "$F05_STUB_PROBE" = "1" ]; then exit 0; fi',
            f"printf '%s\\n' {shlex.quote(str(text))} >&2",
            "exit 1",
        ]
    ) + "\n"
    for name in ("python", "python3", "py"):
        path = root / name
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
    base = ws.env.get("PATH", os.environ.get("PATH", ""))
    updates = {"PATH": str(root) + os.pathsep + base}
    stand = Standin(root=root, log=log, env_updates=updates)
    probe_env = dict(os.environ)
    probe_env.update(updates)
    probe_env["F05_STUB_PROBE"] = "1"
    probe = subprocess.run(
        [str(root / "python3"), "-c", "print('probe')"],
        env=probe_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    try:
        if probe.returncode != 0 or stand.invocations() < 1:
            raise HarnessError(
                "emitted-failure stand-in did not run under a direct probe: "
                f"exit={probe.returncode} stderr={probe.stderr!r} "
                f"invocations={stand.invocations()}"
            )
        yield stand
    finally:
        shutil.rmtree(root, ignore_errors=True)
