# feature: F05
"""Observation helpers for the saved-file guard.

New names for this slice only. Sealed harness, F01, F02, and F04 helpers
are imported, not copied.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from _harness import (
    ENV_PLUGIN_ROOT,
    HarnessError,
    RunResult,
    detector_script,
    file_mode,
    node_executable,
    read_file,
)
import F01_helpers
from F01_helpers import (
    AI_REGISTER,
    BAND_RANGES,
    CONFIDENCE_LABELS,
    SCAN_CAP,
    HUMANIZED_CODING,
    SHORT_FACTUAL,
    SHORT_SLOP,
    SNOW_AND_ROAD,
    band_named_for_score,
    band_of,
    bind_core_metric_paths,
    confidence_of,
    finding_records,
    findings_from_report,
    metrics_from_report,
    neutral_words,
    pad_human,
    parse_structured_mapping,
    reason_of,
    require_success_report,
    scan_path,
    scan_stdin,
    score_of,
    unicode_len,
)
from F02_helpers import (
    NOTEBOOK_EXT,
    ZIP_EXTS,
    _hook_strings,
    runtime_token,
    standalone_int_present,
    write_notebook,
    write_plain,
    write_zip_slop,
)

PRODUCT_NAME = "prosecheck"
WINDOW_PLAIN = 262144
WINDOW_GROUPED = "262,144"
PLAIN_KB = 512
ARCHIVE_KB_FIGURES = (4000, 4096)
LEVEL_WORDS = ("lite", "full", "strict", "off")
CONFIDENCE_WORDS = ("none", "low", "moderate", "high")

# L22 names these as the plugin's hook phrases, one per L98 band.
PHRASE_BY_BAND = {
    "clean": "reads clean",
    "light tells": "reads mostly clean",
    "mixed": "reads with some AI tells",
    "heavy tells": "reads with heavy AI tells",
    "pervasive tells": "reads with pervasive AI tells",
}

# Decimal 512 KB is still within a 1024-based 512 KB. 513 KiB is past both.
DECIMAL_512_KB = 512 * 1000
OVER_BOTH_512 = 513 * 1024
# Past both readings of 512 KB, under both readings of 4 MB.
BETWEEN_CAPS = 600 * 1024
OVER_BOTH_4MB = 4 * 1024 * 1024 + 64 * 1024
OVER_BOTH_4MB_OTHER = 4 * 1024 * 1024 + 256 * 1024

_BOUND = False
_CACHE: dict[str, "Measured"] = {}
# Full reports of the two binding probes (short factual, short slop), kept to
# find every place a report repeats its score, band, or hook phrase.
_BIND_REPORTS: list[dict[str, Any]] = []


@dataclass(frozen=True)
class Measured:
    text: str
    score: int
    band: str
    confidence: str
    reason: str
    labels: tuple[str, ...]


@dataclass
class Standin:
    """Interpreter stand-in planted ahead of every other directory on PATH."""

    root: Path
    log: Path
    env_updates: dict[str, str]

    def invocations(self) -> int:
        try:
            body = self.log.read_text(encoding="utf-8")
        except OSError as exc:
            raise HarnessError(f"cannot read stand-in log {self.log}: {exc}") from exc
        return len([line for line in body.splitlines() if line.strip()])


def bind_guard_metrics() -> None:
    """Bind score, band, and confidence once, on the sealed short probes."""
    global _BOUND
    if _BOUND:
        return
    fact = scan_stdin(SHORT_FACTUAL)
    slop = scan_stdin(SHORT_SLOP)
    if fact.returncode != 0 or slop.returncode != 0:
        raise HarnessError(
            "short factual / slop probes must succeed before the guard is observed; "
            f"factual={fact.returncode} slop={slop.returncode}"
        )
    _, fact_metrics = require_success_report(
        fact, input_chars=unicode_len(SHORT_FACTUAL)
    )
    _, slop_metrics = require_success_report(
        slop, input_chars=unicode_len(SHORT_SLOP)
    )
    none_text = neutral_words(39)
    high_text = pad_human(300)
    none_run = scan_stdin(none_text)
    high_run = scan_stdin(high_text)
    if none_run.returncode != 0 or high_run.returncode != 0:
        raise HarnessError("confidence-binding probes must succeed")
    _, none_metrics = require_success_report(
        none_run, input_chars=unicode_len(none_text)
    )
    _, high_metrics = require_success_report(
        high_run, input_chars=unicode_len(high_text)
    )
    bind_core_metric_paths(
        fact_metrics,
        slop_metrics,
        none_metrics=none_metrics,
        high_conf_metrics=high_metrics,
        scanned_metrics=fact_metrics,
        scanned_chars=unicode_len(SHORT_FACTUAL),
    )
    _BIND_REPORTS[:] = [
        parse_structured_mapping(fact.stdout_text, source="factual probe stdout"),
        parse_structured_mapping(slop.stdout_text, source="slop probe stdout"),
    ]
    _BOUND = True
    print("[F05] bound detector score, band, and confidence", flush=True)


def _from_report(text: str, report: Mapping[str, Any]) -> Measured:
    metrics = metrics_from_report(report)
    findings = findings_from_report(report, metrics)
    score = score_of(metrics, findings=findings)
    band = band_of(metrics)
    confidence = confidence_of(metrics)
    expected_band = band_named_for_score(score)
    if band != expected_band:
        raise HarnessError(
            f"detector band {band!r} is not the band named for score {score} "
            f"({expected_band!r})"
        )
    reason = ""
    if confidence != "high":
        reason = reason_of(metrics)
    labels = tuple(
        dict.fromkeys(
            rec["label"]
            for rec in finding_records(findings)
            if isinstance(rec.get("label"), str) and rec["label"].strip()
        )
    )
    return Measured(
        text=text,
        score=score,
        band=band,
        confidence=confidence,
        reason=reason,
        labels=labels,
    )


def measure_text(text: str) -> Measured:
    bind_guard_metrics()
    result = scan_stdin(text)
    if result.returncode != 0:
        raise HarnessError(
            "detector did not score the probe text: "
            f"exit={result.returncode} stderr={result.stderr_text[:400]!r}"
        )
    require_success_report(result, input_chars=unicode_len(text))
    full = parse_structured_mapping(result.stdout_text, source="detector stdout")
    measured = _from_report(text, full)
    print(
        f"[F05] measured score={measured.score} band={measured.band!r} "
        f"confidence={measured.confidence!r} labels={len(measured.labels)} "
        f"chars={len(text)}",
        flush=True,
    )
    return measured


def measure_path(ws, relpath: str) -> Measured:
    bind_guard_metrics()
    result = scan_path(ws, relpath)
    if result.returncode != 0:
        raise HarnessError(
            f"detector did not score {relpath}: "
            f"exit={result.returncode} stderr={result.stderr_text[:400]!r}"
        )
    full = parse_structured_mapping(
        result.stdout_text, source=f"detector report for {relpath}"
    )
    measured = _from_report("", full)
    print(
        f"[F05] measured path {relpath} score={measured.score} "
        f"band={measured.band!r} confidence={measured.confidence!r} "
        f"labels={len(measured.labels)}",
        flush=True,
    )
    return measured


def phrase_for_band(band: str) -> str:
    phrase = PHRASE_BY_BAND.get(band)
    if phrase is None:
        raise HarnessError(f"no hook phrase for band {band!r}")
    return phrase


def fresh_name(suffix: str) -> str:
    return runtime_token("f") + suffix


def plant_prose(ws, relpath: str, text: str) -> Path:
    ext = Path(relpath).suffix.lower()
    if ext == NOTEBOOK_EXT:
        return write_notebook(ws, relpath, markdown=text)
    if ext in ZIP_EXTS:
        return write_zip_slop(ws, relpath, text)
    return write_plain(ws, relpath, text)


def nudge_text(result: RunResult) -> str:
    """Joined strings of a successful hook envelope.

    Silence is empty standard output and no JSON envelope. A JSON object
    is an envelope even when it holds no text: an empty object, an object
    whose values are only numbers, booleans, or null, and an object whose
    strings are all empty. Those are not silence.

    A non-zero exit, non-JSON stdout, or a JSON value that is not an object
    is an observation failure, not silence.
    """
    if result.returncode != 0:
        raise HarnessError(
            "hook exited non-zero; that is not silence: "
            f"exit={result.returncode} stderr={result.stderr_text[:400]!r} "
            f"stdout={result.stdout_text[:400]!r}"
        )
    raw = result.stdout_text
    if raw == "":
        return ""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"hook stdout is not a JSON envelope: {exc}; text={raw[:400]!r}"
        ) from exc
    if not isinstance(obj, dict):
        raise HarnessError(
            "hook stdout JSON is not an object; a string or array is not "
            f"the envelope: {type(obj).__name__}"
        )
    parts = _hook_strings(result)
    if not any(part != "" for part in parts):
        raise HarnessError(
            "hook printed a JSON envelope with no text; silence is empty "
            f"stdout and no envelope: {raw[:400]!r}"
        )
    return "\n".join(parts)


def require_silent(result: RunResult) -> None:
    text = nudge_text(result)
    assert text == "", f"hook emitted a nudge; text={text[:400]!r}"


def show_text(ws, session_id: str | None = None) -> str:
    payload: dict[str, Any] = {"prompt": "/prosecheck show"}
    if session_id is not None:
        payload["session_id"] = session_id
    result = ws.invoke_hook("prompt-submit", payload=payload)
    text = nudge_text(result)
    if not text.strip():
        raise HarnessError("show returned an empty envelope")
    print(
        f"[F05] show session={session_id!r} chars={len(text)}",
        flush=True,
    )
    return text


def fire_tool(
    ws,
    tool: str,
    *,
    session_id: str | None = None,
    file_path: str | None = None,
    notebook_path: str | None = None,
    content: str | None = None,
    command: str | None = None,
    cwd: str | None = None,
    env_updates: Mapping[str, str | None] | None = None,
    timeout: float | None = None,
    process_cwd: str | None = None,
) -> tuple[RunResult, str]:
    tool_input: dict[str, Any] = {}
    if file_path is not None:
        tool_input["file_path"] = file_path
    if notebook_path is not None:
        tool_input["notebook_path"] = notebook_path
    if content is not None:
        tool_input["content"] = content
    if command is not None:
        tool_input["command"] = command
    payload: dict[str, Any] = {"tool_name": tool, "tool_input": tool_input}
    if session_id is not None:
        payload["session_id"] = session_id
    if cwd is not None:
        payload["cwd"] = cwd
    result = ws.invoke_hook(
        "post-tool-use",
        payload=payload,
        env_updates=env_updates,
        timeout=timeout,
        cwd=process_cwd,
    )
    text = nudge_text(result)
    print(
        f"[F05] {tool} exit={result.returncode} nudge_chars={len(text)} "
        f"session={session_id!r}",
        flush=True,
    )
    return result, text


def labels_in(text: str, labels: Sequence[str]) -> list[str]:
    """Detector labels that occur in *text*, longest first, without double-counting a substring."""
    found: list[str] = []
    occupied: list[tuple[int, int]] = []
    for label in sorted((lab for lab in labels if lab), key=len, reverse=True):
        start = 0
        while True:
            index = text.find(label, start)
            if index < 0:
                break
            end = index + len(label)
            if any(not (end <= lo or index >= hi) for lo, hi in occupied):
                start = index + 1
                continue
            found.append(label)
            occupied.append((index, end))
            break
    return found


def require_flagged_envelope(
    text: str,
    *,
    base: str,
    measured: Measured,
) -> None:
    assert text.strip(), "flagged save emitted an empty envelope"
    assert PRODUCT_NAME in text, (
        f"nudge does not name {PRODUCT_NAME}; text={text[:400]!r}"
    )
    assert base in text, f"nudge does not name {base!r}; text={text[:400]!r}"
    phrase = phrase_for_band(measured.band)
    assert phrase in text, (
        f"nudge does not carry the hook phrase for band {measured.band!r}; "
        f"text={text[:400]!r}"
    )
    assert measured.band in text, (
        f"nudge does not name band {measured.band!r}; text={text[:400]!r}"
    )
    score_view = text.replace(base, " ")
    assert standalone_int_present(score_view, measured.score), (
        f"nudge does not carry score {measured.score} as its own integer; "
        f"text={text[:400]!r}"
    )
    present = labels_in(text, measured.labels)
    assert present, (
        f"nudge carries none of the detector labels {measured.labels!r}; "
        f"text={text[:400]!r}"
    )
    assert len(present) <= 5, (
        f"nudge carries {len(present)} detector labels; the cap is five: {present!r}"
    )
    if len(measured.labels) > 5:
        assert len(present) < len(measured.labels), (
            "detector fired more than five labels and the nudge kept every one"
        )
    # Named facts are not the ask. What remains has to be a request to
    # fix the flagged spans. A pass count and rhythm wording are not
    # required, and neither spelling of that request is pinned.
    _require_correction_request(text, base=base, measured=measured)
    print(
        f"[F05] envelope names {base!r} score={measured.score} "
        f"band={measured.band!r} labels={len(present)}/{len(measured.labels)}",
        flush=True,
    )


# Open readings of "asks for the flagged spans to be fixed".
# "correct the flagged passages" is the same ask. A pass count and the
# word rhythm are not part of either slot, so they neither satisfy it
# nor have to appear.
_REPAIR_WORD = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|correct(?:s|ed|ing|ion|ions)?|"
    r"revis(?:e|es|ed|ing|ion|ions)|rewrit(?:e|es|ing|ten)|"
    r"repair(?:s|ed|ing)?|edit(?:s|ed|ing)?|rework(?:s|ed|ing)?|"
    r"amend(?:s|ed|ing)?|address(?:es|ed|ing)?|"
    r"tidy|tidies|tidied|tidying)\b"
)
_FLAGGED_WRITING = re.compile(
    r"\b(?:spans?|passages?|stretches?|sections?|wordings?|prose|"
    r"sentences?|excerpts?|regions?|clauses?|writing|draft)\b"
)


def _require_correction_request(text: str, *, base: str, measured: Measured) -> None:
    """The leftover, after named facts are gone, has to ask for a fix.

    Product name, base name, score, band, hook phrase, detector labels,
    and the truncation window are not that request. A leftover token that
    does not itself ask for the flagged writing to be changed fails.
    How many passes the ask names, and any rhythm wording, are ignored.
    """
    tokens: list[object] = [
        PRODUCT_NAME,
        base,
        measured.score,
        measured.band,
        phrase_for_band(measured.band),
        *measured.labels,
        *PHRASE_BY_BAND.values(),
        *BAND_RANGES,
        "score",
        "band",
        "flagged",
        "first",
        "only",
        "characters",
        "scored",
        WINDOW_PLAIN,
        WINDOW_GROUPED,
        "262144",
    ]
    lowered = [
        token.lower() if isinstance(token, str) else token for token in tokens
    ]
    left = remainder(text.lower(), lowered)
    assert _REPAIR_WORD.search(left) and _FLAGGED_WRITING.search(left), (
        "leftover text does not ask for the flagged spans to be fixed; "
        f"remainder={left!r} text={text[:400]!r}"
    )


def grouped_int_present(text: str, value: int) -> bool:
    """True when *text* names *value*, including a comma-grouped spelling.

    4096 and 4,096 are one integer, the same way 262144 and 262,144 are.
    A longer integer that only begins with those digits, such as 4,096,000,
    is a different number.
    """
    if standalone_int_present(text, value):
        return True
    grouped = f"{value:,}"
    if "," not in grouped:
        return False
    # The comma is grouping punctuation, not a boundary. Do not start or
    # end in the middle of a longer grouped integer.
    pattern = rf"(?<![\d,]){re.escape(grouped)}(?!\d)(?!,\d)"
    return re.search(pattern, str(text)) is not None


def names_window(text: str) -> bool:
    return standalone_int_present(text, WINDOW_PLAIN) or WINDOW_GROUPED in text


# L230: when the scan is truncated, the extra context states that only the
# first 262,144 characters were scored. The digits alone are not that
# statement. Spellings are not pinned; the same clause as the digits has
# to carry the prefix, the character unit, and a limit or scoring word.
_WINDOW_TOKEN = re.compile(r"(?<!\d)(?:262,144|262144)(?!\d)")
_PREFIX_WORD = re.compile(
    r"(?i)(?<![A-Za-z])(?:first|prefix|initial|leading|opening|beginning)(?![A-Za-z])"
)
_UNIT_WORD = re.compile(
    r"(?i)(?<![A-Za-z])(?:characters?|chars)(?![A-Za-z])"
)
_LIMIT_WORD = re.compile(
    r"(?i)(?<![A-Za-z])(?:only|solely|merely|just|scored|scoring|scores|"
    r"scanned|scanning|coverage|limited|capped|partial|truncated|truncation)"
    r"(?![A-Za-z])"
)


def _clause_around(text: str, start: int, end: int) -> str:
    """The sentence that holds the window digits. A period ends it.

    The comma inside 262,144 is not a boundary. A later sentence, such as
    the fix ask or a fired label, does not supply words for this one.
    """
    left = -1
    for mark in ("\n", ".", "!", "?"):
        found = text.rfind(mark, 0, start)
        if found > left:
            left = found
    right = len(text)
    for mark in ("\n", ".", "!", "?"):
        found = text.find(mark, end)
        if found >= 0 and found < right:
            right = found
    return text[left + 1:right]


def states_scored_prefix(text: str) -> bool:
    """True when *text* states that only the first 262,144 characters were scored.

    A clause that only prints 262144 or 262,144 is false. The bare noun
    "score" next to the integer score is not the scoring word.
    """
    for match in _WINDOW_TOKEN.finditer(text):
        clause = _clause_around(text, match.start(), match.end())
        if (
            _PREFIX_WORD.search(clause)
            and _UNIT_WORD.search(clause)
            and _LIMIT_WORD.search(clause)
        ):
            return True
    return False


def snapshot_config(config_dir: Path) -> dict[str, bytes]:
    try:
        names = list(os.listdir(config_dir))
    except OSError as exc:
        raise HarnessError(f"cannot list config dir {config_dir}: {exc}") from exc
    snap: dict[str, bytes] = {}
    for name in names:
        path = config_dir / name
        try:
            info = path.stat()
        except OSError as exc:
            raise HarnessError(f"cannot stat {path}: {exc}") from exc
        if not stat.S_ISREG(info.st_mode):
            continue
        try:
            snap[name] = path.read_bytes()
        except OSError as exc:
            raise HarnessError(f"cannot read {path}: {exc}") from exc
    return snap


def changed_config_files(config_dir: Path, before: Mapping[str, bytes]) -> list[Path]:
    after = snapshot_config(config_dir)
    changed: list[Path] = []
    for name, blob in after.items():
        if before.get(name) != blob:
            changed.append(config_dir / name)
    return changed


def ledger_file_is_private(path: Path, *, parent: str, marker: str) -> bool:
    """Owner-only, and the body holds neither the parent directory nor the planted marker.

    Stat or read failure raises. A group/other bit, the parent directory, or
    the marker returns False — it is not reported as a missing file.
    """
    mode = file_mode(path)
    text = read_file(path)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return False
    if parent and parent in text:
        return False
    if marker and marker in text:
        return False
    return True


def files_holding_basename(config_dir: Path, base: str) -> list[Path]:
    """Regular files under *config_dir*, at any depth, whose bytes hold *base*.

    A stat or read failure raises. A directory that cannot be walked raises.
    An empty list means no file holds the name.
    """
    needle = base.encode("utf-8")
    found: list[Path] = []
    root = Path(config_dir)
    try:
        walker = os.walk(root)
    except OSError as exc:
        raise HarnessError(f"cannot walk config dir {root}: {exc}") from exc
    for dirpath, _dirnames, filenames in walker:
        for filename in filenames:
            path = Path(dirpath) / filename
            try:
                info = path.lstat()
            except OSError as exc:
                raise HarnessError(f"cannot stat {path}: {exc}") from exc
            if not stat.S_ISREG(info.st_mode):
                continue
            try:
                blob = path.read_bytes()
            except OSError as exc:
                raise HarnessError(f"cannot read {path}: {exc}") from exc
            if needle in blob:
                found.append(path)
    return found


def assert_private_ledger_snapshot(
    config_dir: Path,
    *,
    base: str,
    parent: str,
    marker: str,
) -> list[Path]:
    """Every file that holds this session's base name is owner-only.

    That includes a file in a subdirectory. The body holds neither the
    document text nor the full path. A top-level settings file does not
    have to change.
    """
    holders = files_holding_basename(config_dir, base)
    assert holders, (
        f"no file under the config directory holds the session base name {base!r}"
    )
    for path in holders:
        assert ledger_file_is_private(path, parent=parent, marker=marker), (
            f"record {path} is group/other-readable or holds the "
            "parent directory or the document marker"
        )
    nested = Path(config_dir) / fresh_name(".dir")
    nested.mkdir()
    control = nested / fresh_name(".control")
    control.write_text(base + "\n" + marker + "\n" + parent, encoding="utf-8")
    os.chmod(control, 0o640)
    assert not ledger_file_is_private(control, parent=parent, marker=marker), (
        "privacy observer accepted a group-readable file that contains the marker"
    )
    control.unlink()
    nested.rmdir()
    print(
        f"[F05] {len(holders)} record file(s) holding {base!r} are owner-only",
        flush=True,
    )
    return holders


def _cut_token(text: str, token: str) -> str:
    if not token:
        return text
    if token.isdigit():
        return re.sub(rf"(?<!\d){re.escape(token)}(?!\d)", " ", text)
    if re.fullmatch(r"[A-Za-z][A-Za-z ]*", token):
        return re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", text)
    return text.replace(token, " ")


def remainder(text: str, tokens: Sequence[object]) -> str:
    """Strip named facts, then punctuation, and require a non-empty remainder."""
    ordered = sorted(
        {str(token) for token in tokens if token is not None and str(token) != ""},
        key=len,
        reverse=True,
    )
    out = text
    for token in ordered:
        out = _cut_token(out, token)
    out = re.sub(r"[^\w\s]+", " ", out, flags=re.UNICODE)
    out = re.sub(r"\s+", " ", out).strip()
    if not out:
        raise HarnessError(
            "nothing remained after stripping named facts; "
            f"tokens={ordered[:12]!r} text={text[:400]!r}"
        )
    return out


def own_nudge_section(text: str, name: str, others: Sequence[str]) -> str:
    """The slice that belongs to *name* alone.

    It starts at this name, or at the product-name token that sits after
    the previous other name, and stops at the next other name. Facts that
    sit on a later line, before that next name, stay in the slice. A later
    name does not inherit an earlier name's phrase, score, or band.
    """
    at = text.find(name)
    if at < 0:
        raise HarnessError(f"nudge has no section for {name!r}; text={text[:400]!r}")
    prev_end = 0
    for other in others:
        if not other or other == name:
            continue
        index = 0
        while True:
            found = text.find(other, index)
            if found < 0 or found >= at:
                break
            prev_end = max(prev_end, found + len(other))
            index = found + 1
    next_at = len(text)
    for other in others:
        if not other or other == name:
            continue
        found = text.find(other, at + len(name))
        if found >= 0 and found < next_at:
            next_at = found
    gap = text[prev_end:at]
    mark = gap.rfind(PRODUCT_NAME)
    start = prev_end + mark if mark >= 0 else at
    return text[start:next_at]


def row_around(text: str, name: str, others: Sequence[str]) -> str:
    """The line that names *name*, through the start of the next other name.

    The product name sits before the file name on a nudge line. Starting at
    the file name would drop it from the last line of a joined nudge.
    """
    at = text.find(name)
    if at < 0:
        raise HarnessError(f"show has no row for {name!r}; text={text[:400]!r}")
    line = text.rfind("\n", 0, at)
    start = 0 if line < 0 else line + 1
    end = len(text)
    for other in others:
        if not other or other == name:
            continue
        index = text.find(other, start)
        if index > at and index < end:
            end = index
    return text[start:end]


def status_remainder(
    text: str,
    name: str,
    measured: Measured,
    *,
    session_id: str | None = None,
    directory: str | None = None,
    others: Sequence[str] = (),
) -> str:
    """Ledger row after the facts that are not the flagged bit are gone.

    Score, band, hook phrase, labels, confidence, level, truncation, the
    file name, the session id, and the workspace directory are covariates.
    What remains is the flagged-bit wording.
    """
    row = row_around(text, name, others)
    tokens: list[object] = [
        name,
        *scored_fact_tokens(measured),
        *CONFIDENCE_WORDS,
        WINDOW_PLAIN,
        WINDOW_GROUPED,
        "262144",
        *others,
    ]
    if session_id:
        tokens.append(session_id)
    if directory:
        tokens.append(directory)
        tokens.append(str(Path(directory).name))
    return remainder(row, tokens)


def scored_fact_tokens(measured: Measured, *extra: object) -> list[object]:
    tokens: list[object] = [
        measured.score,
        measured.band,
        phrase_for_band(measured.band),
        measured.reason,
        *measured.labels,
        *BAND_RANGES,
        *LEVEL_WORDS,
        *extra,
    ]
    if measured.score != 20:
        tokens.append(20)
    if measured.score != 40:
        tokens.append(40)
    return tokens


def find_exact(target: int) -> Measured:
    """A scored file at exactly *target*, confidence other than none.

    Pads stay long enough that a short-document floor cannot skip the
    target. A score of 40 also needs a detector label, because the
    strict envelope must name one. The score is whatever the detector
    returns; the search only chooses text.
    """
    seen: list[Measured] = []

    def take(text: str) -> Measured | None:
        measured = measure_text(text)
        seen.append(measured)
        if (
            measured.score == target
            and measured.confidence != "none"
            and measured.confidence in CONFIDENCE_LABELS
            and (measured.labels or target < 40)
        ):
            return measured
        return None

    def climb(text: str, steps: int) -> Measured | None:
        current = text
        for _ in range(steps):
            current += " delve"
            hit = take(current)
            if hit:
                return hit
            if seen[-1].score > target:
                return None
        return None

    bases = [pad_human(n) for n in (180, 260, 340)]
    for base in bases:
        hit = take(base)
        if hit:
            return hit
        if seen[-1].score < target and seen[-1].confidence != "none":
            hit = climb(base, 30)
            if hit:
                return hit

    overs = [
        item
        for item in seen
        if item.score > target and item.confidence != "none"
    ]
    overs.sort(key=lambda item: item.score)
    if overs:
        current = overs[0].text
        for _ in range(16):
            current = current + " " + pad_human(24)
            hit = take(current)
            if hit:
                return hit
            if seen[-1].score < target and seen[-1].confidence != "none":
                hit = climb(current, 16)
                if hit:
                    return hit
                break
    scores = sorted({item.score for item in seen})
    print(f"[F05] exact-{target} missed scores={scores}", flush=True)
    raise HarnessError(
        f"fixture cannot measure a file whose score is exactly {target} "
        f"with confidence other than none; saw scores {scores}"
    )


def prose_exact(target: int) -> Measured:
    key = f"exact:{target}"
    if key not in _CACHE:
        _CACHE[key] = find_exact(target)
        item = _CACHE[key]
        if item.confidence == "none":
            raise HarnessError(
                f"exact score {target} was measured at confidence none"
            )
    return _CACHE[key]


def prose_above_20_not_40() -> Measured:
    """A file scored above 20 and below 40, confidence other than none.

    Exactly 40 is a separate case. This one is the full-level unflagged
    score that strict still flags.
    """
    key = "above20-below40"
    if key in _CACHE:
        return _CACHE[key]
    light = prose_for_band("light tells")
    if 20 < light.score < 40 and light.confidence != "none":
        _CACHE[key] = light
        return light
    for target in (25, 30, 35, 21, 39):
        try:
            item = find_exact(target)
        except HarnessError:
            continue
        if 20 < item.score < 40 and item.confidence != "none":
            _CACHE[key] = item
            return item
    raise HarnessError(
        "fixture cannot measure a file scored above 20 and below 40 "
        "with confidence other than none"
    )


def prose_dense() -> Measured:
    key = "dense"
    if key not in _CACHE:
        chosen: Measured | None = None
        for text in (AI_REGISTER, AI_REGISTER + "\n" + SHORT_SLOP):
            measured = measure_text(text)
            if measured.score > 40 and measured.confidence != "none" and len(measured.labels) > 5:
                chosen = measured
                break
        if chosen is None:
            raise HarnessError(
                "fixture cannot measure a dense file scored above 40 with "
                "more than five detector labels and confidence other than none"
            )
        _CACHE[key] = chosen
    return _CACHE[key]


def prose_for_band(band: str) -> Measured:
    """A scored file whose detector band is exactly *band*.

    Clean may sit at or under 20. The three bands above 40 must be
    flaggable: confidence other than none, and at least one label.
    """
    if band not in BAND_RANGES:
        raise HarnessError(f"unknown band {band!r}")
    key = f"band:{band}"
    if key in _CACHE:
        return _CACHE[key]
    lo, hi = BAND_RANGES[band]
    flagged = lo > 40
    human = pad_human(120)
    slop = AI_REGISTER.strip()
    seen: list[Measured] = []

    def consider(text: str) -> Measured | None:
        measured = measure_text(text)
        seen.append(measured)
        if not lo <= measured.score <= hi:
            return None
        if measured.confidence not in CONFIDENCE_LABELS:
            return None
        if flagged and (measured.confidence == "none" or not measured.labels):
            return None
        if band == "clean" and measured.confidence == "none":
            return None
        return measured

    # Varied punctuation and the humanized sample sit in clean when the
    # padded human paragraphs do not. Stacking catalogue vocabulary on the
    # register sample is what pushes a heavy file into pervasive.
    varied = (
        "The lock opened at six; the tide was already on the wall. "
        "I counted fourteen boats (three of them empty) and wrote the numbers in the margin. "
        "Then the rain started. Not a drizzle, a proper downpour that turned the lane to paste. "
        "We waited. The kettle clicked. Someone swore, quietly, and someone else laughed. "
        "By noon the sky had torn open again, and the road crew was back with the same dented thermos they carry every Thursday. "
    )
    vocab = (
        "Additionally this crucial tapestry is a pivotal vibrant testament underscoring the intricate interplay. "
        "It garners support and bolsters results while fostering growth and showcasing work and emphasizing an enduring enhancement. "
        "Teams leverage tools and utilize methods and facilitate change and encompass a holistic paradigm. "
        "The transformative unprecedented myriad plethora is robust and seamlessly navigates as leaders embark on the journey. "
        "The multifaceted realm elevates teams and empowers residents and unlocks value, capturing the essence of the landscape. "
    )
    probes = [
        varied * 4,
        HUMANIZED_CODING,
        human,
        SHORT_FACTUAL,
        pad_human(40),
        SHORT_SLOP,
        slop,
        slop + "\n" + slop,
        SHORT_SLOP + "\n" + slop,
        slop + "\n" + (vocab * 6),
    ]
    slop_bits = [part for part in re.split(r"(?<=[.!?])\s+", slop) if part.strip()]
    blended = human
    for bit in slop_bits:
        blended = blended + " " + bit
        probes.append(blended)
    for words in (30, 80, 160, 280):
        probes.append(slop + "\n" + pad_human(words))
        probes.append(SHORT_SLOP + "\n" + pad_human(words))

    chosen: Measured | None = None
    for text in probes:
        chosen = consider(text)
        if chosen is not None:
            break
    if chosen is None:
        scores = sorted({item.score for item in seen})
        raise HarnessError(
            f"fixture cannot measure a {band!r} file"
            + (" above the default threshold" if flagged else "")
            + f"; saw scores {scores}"
        )
    _CACHE[key] = chosen
    return chosen


def prose_under() -> Measured:
    key = "under"
    if key not in _CACHE:
        chosen: Measured | None = None
        for text in (
            pad_human(80) + " They delve into the parish records after the flood.",
            pad_human(120),
            SHORT_FACTUAL + " " + pad_human(40),
        ):
            measured = measure_text(text)
            if (
                measured.score <= 40
                and measured.confidence != "none"
                and measured.labels
            ):
                chosen = measured
                break
        if chosen is None:
            raise HarnessError(
                "fixture cannot measure an unflagged file at or under 40 "
                "with a detector label and confidence other than none"
            )
        _CACHE[key] = chosen
    return _CACHE[key]


def prose_none() -> Measured:
    """Under 40 words, two decisive families, score above 40, confidence none."""
    key = "none"
    if key not in _CACHE:
        candidates = (
            "Send the draft to [Your Name] before noon. "
            "See https://example.com/post?utm_source=chatgpt.com for the note.",
            "I hope this helps. As of my last training the lock still opens at dawn.",
            "I hope this helps. As of my last training, see "
            "https://example.com/post?utm_source=chatgpt.com today.",
        )
        chosen: Measured | None = None
        for text in candidates:
            measured = measure_text(text)
            words = len(re.findall(r"\S+", text))
            if (
                words < 40
                and measured.score > 40
                and measured.confidence == "none"
                and measured.labels
            ):
                chosen = measured
                break
        if chosen is None:
            raise HarnessError(
                "fixture cannot measure a below-40-word file scored above 40 "
                "at confidence none"
            )
        _CACHE[key] = chosen
    return _CACHE[key]


def similar_clean(target_chars: int) -> Measured:
    words = max(50, target_chars // 6)
    measured = measure_text(pad_human(words))
    if measured.score > 40 or measured.confidence == "none":
        raise HarnessError(
            "similar-length human prose is not an unflagged scored file: "
            f"score={measured.score} confidence={measured.confidence!r}"
        )
    return measured


def repeat_to(text: str, n: int) -> str:
    if n < 1:
        raise HarnessError("repeat length must be positive")
    unit = text if text else "bridge"
    reps = (n // len(unit)) + 1
    return (unit * reps)[:n]


def _walk_integers(obj: Any) -> list[int]:
    found: list[int] = []

    def walk(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            found.append(value)
            return
        if isinstance(value, Mapping):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(obj)
    return found


def _delete_bound_score(metrics: dict) -> int:
    path = F01_helpers._PATHS.get("score")
    if not path:
        raise HarnessError("score path is not bound; cannot remove the numeric score")
    score = score_of(metrics)
    parent: Any = metrics
    for part in path[:-1]:
        if not isinstance(parent, Mapping) or part not in parent:
            raise HarnessError(f"score path {path!r} is missing from metrics")
        parent = parent[part]
    key = path[-1]
    if not isinstance(parent, dict) or key not in parent:
        raise HarnessError(f"score path {path!r} is missing from metrics")
    held = parent[key]
    if isinstance(held, bool) or held != score:
        raise HarnessError(
            f"bound score path holds {held!r}, not the numeric score {score}"
        )
    del parent[key]
    return score


def _require_structured_without_score(report: Mapping[str, Any]) -> None:
    metrics = metrics_from_report(report)
    findings = findings_from_report(report, metrics)
    if not findings:
        raise HarnessError(
            "structured report lost its findings when the numeric score was removed"
        )
    try:
        still = score_of(metrics, findings=findings)
    except HarnessError:
        return
    raise HarnessError(
        f"numeric score {still} is still on the structured report after removal"
    )


def _plant_nonscore_integer(metrics: dict, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HarnessError(f"leftover must be an integer, got {value!r}")
    path = F01_helpers._PATHS.get("score")
    if not path:
        raise HarnessError("score path is not bound; cannot plant a non-score integer")
    score_key = path[-1]
    key = None
    for candidate in ("n", "leftover", "count_not_score"):
        if candidate != score_key and candidate not in metrics:
            key = candidate
            break
    if key is None:
        raise HarnessError("metrics object has no free key for a non-score integer")
    metrics[key] = value


def _detector_encoding(text: str) -> str:
    """Encoding family of a report the shared reader already accepted.

    The reader tries JSON first, then a Python literal mapping. Replay
    must stay in that same family: a literal report re-serialized as JSON
    is a different encoding than the detector printed.
    """
    stripped = text.strip()
    parsed: Any
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return "literal"
    if isinstance(parsed, dict):
        return "json"
    return "literal"


def _replay_detector_report(report: Mapping[str, Any], encoding: str) -> str:
    """Serialize *report* in the detector's own encoding family."""
    if encoding == "json":
        try:
            text = json.dumps(report, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise HarnessError(
                f"could not replay the detector report as JSON: {exc}"
            ) from exc
    elif encoding == "literal":
        try:
            text = repr(report)
        except (TypeError, ValueError) as exc:
            raise HarnessError(
                f"could not replay the detector report as a Python literal: {exc}"
            ) from exc
    else:
        raise HarnessError(
            f"detector encoding {encoding!r} is not a structured-mapping encoding"
        )
    parse_structured_mapping(text, source="replayed detector report")
    replayed = _detector_encoding(text)
    if replayed != encoding:
        raise HarnessError(
            "replayed detector report changed encoding from "
            f"{encoding!r} to {replayed!r}"
        )
    return text


def _report_paths(obj: Any, prefix: tuple = ()) -> Iterator[tuple[tuple, Any]]:
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            yield from _report_paths(value, prefix + (key,))
    elif isinstance(obj, (list, tuple)):
        for index, value in enumerate(obj):
            yield from _report_paths(value, prefix + (index,))
    else:
        yield prefix, obj


def _mirror_paths(kind: str) -> list[tuple]:
    """Every path in a full detector report that repeats its *kind*.

    *kind* is ``score``, ``band``, or ``phrase``. A path is a copy when it
    holds that report's value on both binding probes (short factual and short
    slop, which differ in score and band), so an unrelated field that only
    happens to share one value is not a copy. The bound metrics path is one of
    them; a report may carry others, for example at the top level.
    """
    bind_guard_metrics()
    if len(_BIND_REPORTS) != 2:
        raise HarnessError("binding reports are unavailable")
    wanted: list[Any] = []
    for report in _BIND_REPORTS:
        metrics = metrics_from_report(report)
        score = score_of(metrics)
        band = band_of(metrics)
        wanted.append(
            {"score": score, "band": band, "phrase": phrase_for_band(band)}[kind]
        )
    if len(set(map(repr, wanted))) < 2:
        raise HarnessError(f"binding probes share one {kind}; cannot tell copies apart")
    paths: list[tuple] = []
    first = dict(_report_paths(_BIND_REPORTS[0]))
    second = dict(_report_paths(_BIND_REPORTS[1]))
    for path, value in first.items():
        if isinstance(value, bool) or type(value) is not type(wanted[0]):
            continue
        if value == wanted[0] and second.get(path) == wanted[1]:
            paths.append(path)
    if kind in ("score", "band") and not paths:
        raise HarnessError(f"no {kind} path repeats the bound {kind} on both probes")
    return paths


def _set_path(obj: Any, path: tuple, value: Any, *, delete: bool = False) -> bool:
    parent = obj
    for part in path[:-1]:
        try:
            parent = parent[part]
        except (KeyError, IndexError, TypeError):
            return False
    key = path[-1]
    try:
        parent[key]
    except (KeyError, IndexError, TypeError):
        return False
    if delete:
        del parent[key]
    else:
        parent[key] = value
    return True


def _delete_score_mirrors(report: dict) -> int:
    """Remove every copy of the numeric score from a full report; return it."""
    metrics = metrics_from_report(report)
    score = score_of(metrics)
    removed = 0
    for path in sorted(_mirror_paths("score"), key=len, reverse=True):
        if _set_path(report, path, None, delete=True):
            removed += 1
    if not removed:
        raise HarnessError("no copy of the numeric score was removed from the report")
    return score


def pinned_score(score: int) -> tuple[Measured, str]:
    """A real detector report whose score is set to *score*, for the guard.

    The report is this detector's own output for the dense sample, in its own
    encoding, with every copy of the score set to *score* and every copy of the
    band (and hook phrase, if the report carries one) set to the band named
    for that score. Confidence and labels stay as the detector reported them.
    The guard reads it through an interpreter stand-in, so its threshold
    behaviour is observed at an exact score without searching for prose that
    lands there.
    """
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
        raise HarnessError(f"pinned score must be an integer 0-100, got {score!r}")
    key = f"pinned:{score}"
    dense = prose_dense()
    result = scan_stdin(dense.text)
    if result.returncode != 0:
        raise HarnessError(
            f"detector did not score the dense sample: exit={result.returncode}"
        )
    report = parse_structured_mapping(result.stdout_text, source="detector stdout")
    encoding = _detector_encoding(result.stdout_text)
    band = band_named_for_score(score)
    pinned = copy.deepcopy(report)
    for kind, value in (("score", score), ("band", band), ("phrase", phrase_for_band(band))):
        for path in _mirror_paths(kind):
            _set_path(pinned, path, value)
    text = _replay_detector_report(pinned, encoding)
    measured = _from_report(dense.text, parse_structured_mapping(text, source=key))
    if measured.score != score or measured.band != band:
        raise HarnessError(
            f"pinned report reads as score={measured.score} band={measured.band!r}, "
            f"not {score} / {band!r}"
        )
    if measured.confidence == "none" or not measured.labels:
        raise HarnessError("dense sample has confidence none or no labels")
    print(f"[F05] pinned score={score} band={band!r} conf={measured.confidence!r}", flush=True)
    return measured, text


def fire_pinned(ws, report_text: str, **fire_kwargs: Any) -> tuple[RunResult, str]:
    """Fire the guard while the interpreter it launches prints *report_text*."""
    with interpreter_standin(ws, stdout=report_text, exit_code=0) as stand:
        started = stand.invocations()
        fire_kwargs.setdefault("timeout", 20)
        outcome = fire_tool(ws, env_updates=stand.env_updates, **fire_kwargs)
        if stand.invocations() <= started:
            raise HarnessError("stand-in was not on the detector path")
    return outcome


def missing_score_arms(leftover: int) -> tuple[str, str, tuple[int, ...]]:
    """A successful detector report with the numeric score removed.

    Both strings are that same report, in the detector's own encoding.
    The second also carries *leftover* on the metrics object, at a key
    that is not the score. The third value is every integer still on
    that second report. Findings stay in place.
    """
    bind_guard_metrics()
    result = scan_stdin(SHORT_SLOP)
    if result.returncode != 0:
        raise HarnessError(
            "detector did not produce a successful report to strip: "
            f"exit={result.returncode} stderr={result.stderr_text[:400]!r}"
        )
    require_success_report(result, input_chars=unicode_len(SHORT_SLOP))
    report = parse_structured_mapping(result.stdout_text, source="detector stdout")
    encoding = _detector_encoding(result.stdout_text)
    bare = copy.deepcopy(report)
    removed = _delete_score_mirrors(bare)
    _require_structured_without_score(bare)
    counted = copy.deepcopy(bare)
    counted_metrics = metrics_from_report(counted)
    _plant_nonscore_integer(counted_metrics, leftover)
    _require_structured_without_score(counted)
    if leftover not in _walk_integers(counted):
        raise HarnessError("planted non-score integer is not on the report")
    leftovers = tuple(dict.fromkeys(_walk_integers(counted)))
    if not leftovers:
        raise HarnessError("report has no leftover integer after the score was removed")
    without_score = _replay_detector_report(bare, encoding)
    with_leftover = _replay_detector_report(counted, encoding)
    replayed_bare = parse_structured_mapping(
        without_score, source="replayed report without a score"
    )
    replayed_counted = parse_structured_mapping(
        with_leftover, source="replayed report with a leftover integer"
    )
    _require_structured_without_score(replayed_bare)
    _require_structured_without_score(replayed_counted)
    if leftover not in _walk_integers(replayed_counted):
        raise HarnessError("replayed report dropped the planted non-score integer")
    print(
        f"[F05] missing-score report removed={removed} leftover={leftover} "
        f"integers={leftovers}",
        flush=True,
    )
    return without_score, with_leftover, leftovers


@contextmanager
def interpreter_standin(
    ws,
    *,
    sleep_s: float | None = None,
    stdout: str | None = None,
    exit_code: int = 0,
    forward: bool = False,
) -> Iterator[Standin]:
    """Plant python / python3 / py ahead of PATH. Prove one probe invocation first."""
    root = Path(tempfile.mkdtemp(prefix="f05-py-"))
    log = root / "invocations.log"
    log.write_text("", encoding="utf-8")
    real = shlex.quote(sys.executable)
    log_q = shlex.quote(str(log))
    lines = [
        "#!/bin/sh",
        f"log={log_q}",
        'if [ -z "$log" ]; then echo "stand-in log unset" >&2; exit 97; fi',
        'echo invoked >> "$log"',
        'if [ "$F05_STUB_PROBE" = "1" ]; then exit 0; fi',
    ]
    if sleep_s is not None:
        lines.append(f"sleep {sleep_s}")
    if forward:
        lines.append(f"exec {real} \"$@\"")
    elif stdout is not None:
        lines.append(f"printf '%s' {shlex.quote(stdout)}")
        lines.append(f"exit {int(exit_code)}")
    else:
        lines.append(f"exit {int(exit_code)}")
    script = "\n".join(lines) + "\n"
    for name in ("python", "python3", "py"):
        path = root / name
        path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
    base = ws.env.get("PATH", os.environ.get("PATH", ""))
    updates = {
        "PATH": str(root) + os.pathsep + base,
        "F05_STUB_LOG": str(log),
    }
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
                "interpreter stand-in did not run under a direct probe: "
                f"exit={probe.returncode} stderr={probe.stderr!r} "
                f"invocations={stand.invocations()}"
            )
        print(
            f"[F05] stand-in probe ok invocations={stand.invocations()} "
            f"sleep={sleep_s} forward={forward} exit={exit_code}",
            flush=True,
        )
        yield stand
    finally:
        shutil.rmtree(root, ignore_errors=True)


def updates_without_interpreters() -> dict[str, str]:
    root = Path(tempfile.mkdtemp(prefix="f05-nopy-"))
    path = str(root)
    for name in ("python", "python3", "py"):
        found = shutil.which(name, path=path)
        if found:
            raise HarnessError(
                f"{name} is still visible on a path that should lack interpreters: {found}"
            )
    return {"PATH": path}


def relocated_plugin_root() -> tuple[Path, dict[str, str]]:
    """A temp install root whose detector file is the real script, via a symlink."""
    root = Path(tempfile.mkdtemp(prefix="f05-root-"))
    scripts = root / "scripts"
    scripts.mkdir()
    real = detector_script()
    (scripts / "detect.py").symlink_to(real)
    return root, {ENV_PLUGIN_ROOT: str(root)}


def basename_absent(text: str, base: str) -> None:
    assert base not in text, f"{base!r} was recorded; text={text[:400]!r}"


def basename_mentions(text: str, base: str) -> int:
    """How many times *base* is named in a listing already read.

    An empty listing is not zero mentions. Zero is only a non-empty
    listing that does not name *base*.
    """
    if text is None or text == "" or not str(text).strip():
        raise HarnessError(
            "basename count has no listing; an empty read is not zero mentions"
        )
    if not base:
        raise HarnessError("basename count has no name")
    return str(text).count(base)


def config_omits(paths: Sequence[Path], base: str) -> None:
    for path in paths:
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise HarnessError(f"cannot read {path}: {exc}") from exc
        assert base.encode("utf-8") not in blob, (
            f"{base!r} was written into config file {path.name}"
        )


def elapsed_call(fn):
    start = time.monotonic()
    value = fn()
    return time.monotonic() - start, value


_CHILD_SITES = '''\
import os
import socket

_log = os.environ.get("_F05_CONNECT_LOG", "")

def _rec(kind, dest):
    if not _log:
        return
    try:
        with open(_log, "a", encoding="utf-8") as handle:
            handle.write(kind + " " + str(dest) + "\\n")
    except OSError:
        pass

_rec("child-start", os.getpid())
_socket_connect = socket.socket.connect

def _connect(self, address):
    _rec("connect", address)
    return _socket_connect(self, address)

socket.socket.connect = _connect
_create_connection = socket.create_connection

def _creating(*args, **kwargs):
    _rec("create_connection", args[0] if args else "")
    return _create_connection(*args, **kwargs)

socket.create_connection = _creating
'''

_NODE_PRELOAD = r"""
"use strict";
const fs = require("fs");
const logp = process.env._F05_CONNECT_LOG;
function rec(kind, dest) {
  if (!logp) return;
  try { fs.appendFileSync(logp, kind + " " + String(dest) + "\n"); } catch (e) {}
}
function wrap(obj, name) {
  if (!obj || typeof obj[name] !== "function") return;
  const orig = obj[name];
  obj[name] = function (...args) {
    rec(name, args[0] && (args[0].host || args[0].hostname || args[0].path || args[0]));
    return orig.apply(this, args);
  };
}
try {
  const net = require("net");
  wrap(net.Socket.prototype, "connect");
  wrap(net, "connect");
  wrap(net, "createConnection");
} catch (e) {}
try {
  const http = require("http");
  wrap(http, "request");
  wrap(http, "get");
} catch (e) {}
try {
  const https = require("https");
  wrap(https, "request");
  wrap(https, "get");
} catch (e) {}
"""


def _strace_follows_children(strace: str, node: str, probe_log: Path) -> bool:
    probe = subprocess.run(
        [
            strace,
            "-f",
            "-qq",
            "-e",
            "trace=connect",
            "-o",
            str(probe_log),
            node,
            "-e",
            "process.exit(0)",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
        check=False,
    )
    return probe.returncode == 0


@contextmanager
def guard_connect_observer() -> Iterator[Any]:
    """Count connects from the hook and from the detector child.

    A Python child is visible because its startup imports a socket wrapper.
    When strace can follow forks, its connect trace is counted too. If a
    detector-style child connect is not visible, this raises instead of
    reporting zero.
    """
    tmp = Path(tempfile.mkdtemp(prefix="f05-net-"))
    log = tmp / "connects.log"
    log.write_text("", encoding="utf-8")
    (tmp / "sitecustomize.py").write_text(_CHILD_SITES, encoding="utf-8")
    preload = tmp / "preload.js"
    preload.write_text(_NODE_PRELOAD, encoding="utf-8")
    try:
        real_node = node_executable()
    except FileNotFoundError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HarnessError(f"cannot observe hook connects: {exc}") from exc

    strace = shutil.which("strace")
    strace_dir = tmp / "strace"
    strace_dir.mkdir()
    use_strace = False
    if strace:
        try:
            use_strace = _strace_follows_children(strace, real_node, tmp / "probe.log")
        except (OSError, subprocess.TimeoutExpired):
            use_strace = False
    wrapper = tmp / "node"
    if use_strace:
        wrapper.write_text(
            "#!/bin/sh\n"
            f"dir={shlex.quote(str(strace_dir))}\n"
            'n=0\n'
            'while [ -e "$dir/call.$n" ]; do n=$((n+1)); done\n'
            f"exec {shlex.quote(strace)} -f -qq -e trace=connect "
            '-o "$dir/call.$n" '
            f"{shlex.quote(real_node)} \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        node_path = f"{tmp}{os.pathsep}{os.environ.get('PATH', '')}"
    else:
        node_path = os.environ.get("PATH", "")

    base_pythonpath = os.environ.get("PYTHONPATH", "")
    pythonpath = str(tmp) if not base_pythonpath else str(tmp) + os.pathsep + base_pythonpath
    env_updates = {
        "PATH": node_path,
        "PYTHONPATH": pythonpath,
        "NODE_OPTIONS": f"--require={preload}",
        "_F05_CONNECT_LOG": str(log),
    }

    def _log_text() -> str:
        try:
            return log.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise HarnessError(
                f"connect observer cannot read its log: {exc}"
            ) from exc

    def _strace_inet() -> int:
        if not use_strace:
            return 0
        total = 0
        try:
            names = list(strace_dir.iterdir())
        except OSError as exc:
            raise HarnessError(
                f"connect observer cannot list strace logs: {exc}"
            ) from exc
        for path in names:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                raise HarnessError(
                    f"connect observer cannot read {path.name}: {exc}"
                ) from exc
            total += sum(
                1
                for line in text.splitlines()
                if "AF_INET" in line or "AF_INET6" in line
            )
        return total

    class Observer:
        def __init__(self) -> None:
            # Class-body assignment does not close over the function local.
            self.env_updates = env_updates

        @property
        def n_connects(self) -> int:
            body = _log_text()
            logged = sum(
                1
                for line in body.splitlines()
                if line.startswith("connect ") or line.startswith("create_connection ")
                or line.startswith("request ") or line.startswith("get ")
            )
            return logged + _strace_inet()

        @property
        def child_starts(self) -> int:
            body = _log_text()
            return sum(1 for line in body.splitlines() if line.startswith("child-start "))

        def prove_child_visible(self) -> None:
            """A Python child that connects must move the count. Blind is a failure."""
            before = self.n_connects
            starts = self.child_starts
            env = dict(os.environ)
            env.update(self.env_updates)
            child = (
                "import socket\n"
                "s = socket.socket()\n"
                "s.settimeout(0.4)\n"
                "try:\n"
                "    s.connect(('127.0.0.1', 9))\n"
                "except OSError:\n"
                "    pass\n"
            )
            launch = (
                "require('child_process').spawnSync("
                f"{json.dumps(sys.executable)}, ['-c', {json.dumps(child)}], "
                "{env: process.env, timeout: 4000});"
            )
            completed = subprocess.run(
                [real_node, "-e", launch],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=8,
                check=False,
            )
            if self.child_starts <= starts or self.n_connects <= before:
                raise HarnessError(
                    "connect observer cannot see a detector-style child; "
                    "refusing to report a zero connect count. "
                    f"exit={completed.returncode} "
                    f"stderr={completed.stderr[:300]!r} "
                    f"starts={self.child_starts} connects={self.n_connects}"
                )

    observer = Observer()
    try:
        observer.prove_child_visible()
        yield observer
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


__all__ = [
    "ARCHIVE_KB_FIGURES",
    "BETWEEN_CAPS",
    "DECIMAL_512_KB",
    "Measured",
    "OVER_BOTH_4MB",
    "OVER_BOTH_4MB_OTHER",
    "OVER_BOTH_512",
    "PLAIN_KB",
    "PRODUCT_NAME",
    "Standin",
    "WINDOW_GROUPED",
    "WINDOW_PLAIN",
    "assert_private_ledger_snapshot",
    "basename_absent",
    "basename_mentions",
    "changed_config_files",
    "config_omits",
    "elapsed_call",
    "find_exact",
    "fire_tool",
    "fresh_name",
    "grouped_int_present",
    "guard_connect_observer",
    "interpreter_standin",
    "labels_in",
    "ledger_file_is_private",
    "measure_path",
    "measure_text",
    "missing_score_arms",
    "pinned_score",
    "fire_pinned",
    "names_window",
    "nudge_text",
    "phrase_for_band",
    "plant_prose",
    "prose_dense",
    "prose_exact",
    "prose_for_band",
    "prose_none",
    "prose_under",
    "relocated_plugin_root",
    "remainder",
    "repeat_to",
    "require_flagged_envelope",
    "require_silent",
    "row_around",
    "scored_fact_tokens",
    "show_text",
    "states_scored_prefix",
    "similar_clean",
    "status_remainder",
    "snapshot_config",
    "standalone_int_present",
    "updates_without_interpreters",
]
