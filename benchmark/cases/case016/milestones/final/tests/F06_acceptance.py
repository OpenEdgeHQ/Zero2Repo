# feature: F06
"""Acceptance tests for the /prosecheck command router.

Assertions follow the feature's public contract. Host payload keys are
only how a value is sent.
"""

from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from _harness import ENV_PLUGIN_ROOT, HarnessError
from F02_helpers import (
    NOTEBOOK_EXT,
    pad_file_to_size,
    runtime_token,
    window_body,
    write_docx,
    write_notebook,
    write_plain,
    write_pptx,
)
from F04_helpers import (
    BANNED_VOCABULARY,
    has_cleanup_switch_finish,
    has_light_tells,
    hook_connect_observer,
    require_banned_list,
    require_exported_contract_omits_machine_identity,
    require_full_scoring,
    require_hook_success,
    require_lite_omits_scoring,
    require_strict_cleanup,
    require_not_source_code_scope,
    session_start,
    standalone_word_present,
)
from F05_helpers import (
    fire_pinned,
    pinned_score,
    ARCHIVE_KB_FIGURES,
    BETWEEN_CAPS,
    CONFIDENCE_WORDS,
    LEVEL_WORDS,
    OVER_BOTH_4MB,
    OVER_BOTH_4MB_OTHER,
    OVER_BOTH_512,
    files_holding_basename,
    fire_tool,
    interpreter_standin,
    labels_in,
    measure_path,
    measure_text,
    phrase_for_band,
    prose_dense,
    prose_under,
    row_around,
    status_remainder,
)
from F06_helpers import (
    carries_marker,
    CHECK_PATH_ARTIFACTS,
    HELP_LIST,
    NAMED,
    NOT_AUTHOR,
    PLAIN,
    SUBCOMMANDS,
    age_file,
    archive_cap_named,
    assert_one_level_line,
    closing_line,
    doctor_check_lines,
    clear_stored_level,
    block_reason,
    check_path_argument,
    command_registrations,
    command_reply,
    cursor_rule_body,
    invoke_shipped_command,
    prompt_submission,
    cut_first_integer,
    emitted_failure_standin,
    fresh_word,
    help_entry_line,
    help_listed_in_command_slot,
    high_confidence_prose,
    prose_with_confidence_reason,
    indicates_no_patterns_fired,
    kilobyte_figure_in,
    label_hits,
    lines_with,
    many_label_prose,
    names_window,
    no_score_integers,
    node_kept_without_interpreters,
    off_marked_mode_lines,
    off_only_closer_lines,
    prose_strictly_between,
    readable_scores_0_100,
    replies_without_named_transcripts,
    replies_without_typed_words,
    reports_word_as_unknown,
    require_check_summary,
    require_four_healthy_checks,
    require_three_off_success_checks,
    require_scored_row_shows,
    require_size_skip_row,
    require_distinct_token_total,
    require_prose_glob_front_matter,
    require_strict_clean_band_apart,
    shared_phrase,
    shared_sweep_clock,
    stamp_cutoff_offset,
    states_detector_present_line,
    states_detector_presence_check,
    holds_aside_from_python_word,
    states_current_mode_line,
    states_failure_report,
    states_no_report,
    states_python_score_line,
    states_writable_settings_line,
    states_settings_folder_not_writable,
    scope_never_touched,
    shows_integer,
    standalone_count,
    states_character_scrub,
    states_contract_only,
    states_contract_plus_guard,
    states_guard_at_40_is_default,
    states_disable_and_reenable,
    states_guard_word,
    states_health_check,
    states_no_file_scoring,
    states_report_only,
    states_scores_file_without_rewrite,
    states_session_token_and_own_prose,
    states_writes_contract_for_agents,
    stats_quantities_named,
    account_stats_score_reply,
    session_prose_integers,
    stats_reply_without_path_and_totals,
    strip_tokens,
    whole_integers,
    without_named_transcript,
    success_marker,
    window_named,
    without_printed_integers,
    zero_label_prose,
    points_at_on_command,
    points_at_show_command,
    points_at_show_for_partial_or_skipped,
    states_cannot_read,
    states_cannot_read_or_write,
    states_cannot_write,
    states_detector_unavailable,
    states_fix_lines_and_rerun_doctor,
    states_flagged,
    states_no_readable_text,
    states_not_a_file,
    states_over_cap,
    states_not_rescored,
    states_not_scored,
    states_readable_failure_reason,
    states_list_fills_once_deliverable_saved,
    states_nothing_scored_yet,
    states_nothing_wrong_with_install,
    states_saved_files_not_scored_until_on,
    states_on_enables_export,
    states_switched_off,
    states_typed_on_enables_export,
    usage_field_integers,
    states_only_prefix_scored,
    states_post_write_detector,
    states_prose_only_scope,
    states_prose_still_shaped,
    states_python_missing,
    states_python_missing_statement,
    require_contract_section,
    require_outside_text_in_place,
    require_same_rule_bytes,
    states_rule_already_there,
    states_saved_files_not_rescored,
    states_section_already_present,
    states_tool_is_on,
    states_under_threshold,
)

UNDER_BOTH = 400 * 1024
OUTSIDE = (
    "The mill wheel turns after rain. The clerk copies the parish list "
    "by hand and leaves the totals in the margin. Neighbours argue about "
    "the footbridge, then fix the loose plank before dark."
)


def _ask(ws, words="", form=PLAIN, **kwargs):
    """One command identity, read as a block decision's reason.

    *words* empty is the bare invocation. A subcommand, an unknown word,
    or check with or without a path is that word on *form*. Both forms
    share this reader. The text returned is the reason, not every string
    in the body.
    """
    prompt = form if not words else f"{form} {words}"
    return command_reply(ws, prompt, **kwargs)


def _status(ws, form=PLAIN):
    """Command reply and joined delivery for one status read.

    The reply is the report. The joined delivery still carries the stored
    level, including strings that sit beside the reply.
    """
    obj, joined = prompt_submission(ws, f"{form} status")
    return block_reason(obj, joined), joined


def _store(ws, level, form=PLAIN):
    reply = _ask(ws, level, form)
    if level == "on":
        if not standalone_word_present(reply, "on"):
            raise HarnessError(f"on reply does not name on; text={reply[:300]!r}")
        if standalone_count(reply, "full") < 1:
            raise HarnessError(f"on reply does not name full; text={reply[:300]!r}")
    elif not standalone_word_present(reply, level):
        raise HarnessError(
            f"{level} reply does not name that level; text={reply[:300]!r}"
        )
    return reply


def _non_namespaced_command_line(line):
    """A command line in the non-namespaced spelling.

    The namespaced form contains the shorter token as a prefix, so that
    token has to be read after the namespaced form is set aside. Mentioning
    the namespaced form elsewhere on the line does not hide the shorter one.
    """
    return PLAIN in line.replace(NAMED, " ")


def _help_has_list(text):
    for line in text.splitlines():
        if help_listed_in_command_slot(line):
            raise AssertionError("help lists help as its own subcommand")
    for word in HELP_LIST:
        if not standalone_word_present(text, word):
            raise AssertionError(f"help is missing {word}; text={text[:500]!r}")
        lines = [
            line
            for line in text.splitlines()
            if standalone_word_present(line, word) and _non_namespaced_command_line(line)
        ]
        if not lines:
            raise AssertionError(
                f"help does not put {word} on a non-namespaced command line"
            )


def _no_score(reply, *paths):
    """0-100 integers after the path and its base name are gone.

    A generated path can contain digits. Those digits are the path, not a score.
    """
    tokens = []
    for path in paths:
        tokens.append(str(path))
        tokens.append(Path(str(path)).name)
    no_score_integers(strip_tokens(reply, tokens))


def _bytes_same(path, before):
    after = path.read_bytes()
    assert after == before, f"{path.name} bytes changed"
    flipped = bytearray(before)
    if not flipped:
        flipped = bytearray(b"\x00")
    flipped[0] ^= 0x01
    assert bytes(flipped) != before


def _check_facts(text, measured, base):
    phrase = phrase_for_band(measured.band)
    assert base in text
    assert phrase in text
    assert measured.band in text
    assert standalone_word_present(text, measured.confidence)
    assert shows_integer(text, measured.score)
    assert NOT_AUTHOR not in text
    return phrase


def _plant(ws, name, text):
    return write_plain(ws, name, text)


def _save(ws, path, session):
    fire_tool(ws, "Write", session_id=session, file_path=str(path))


def _empty_show(text, absent):
    assert ".docx" in text and ".pdf" in text
    left = strip_tokens(text, [".docx", ".pdf", "docx", "pdf"])
    assert left, f"empty ledger remainder is empty; text={text[:400]!r}"
    assert states_nothing_scored_yet(text)
    assert states_list_fills_once_deliverable_saved(text)
    no_score_integers(text)
    if absent:
        assert absent not in text


def _agents(ws):
    return Path(ws.path) / "AGENTS.md"


def _rule(ws):
    return Path(ws.path) / ".cursor" / "rules" / "prosecheck.mdc"


def _clear_export(ws):
    agents = _agents(ws)
    if agents.is_dir() and not agents.is_symlink():
        shutil.rmtree(agents)
    elif agents.exists() or agents.is_symlink():
        agents.unlink()
    cursor = Path(ws.path) / ".cursor"
    if cursor.is_dir() and not cursor.is_symlink():
        shutil.rmtree(cursor)
    elif cursor.exists() or cursor.is_symlink():
        cursor.unlink()


def _assistant(text, output, cache, mid=None):
    message = {
        "usage": {
            "output_tokens": output,
            "cache_read_input_tokens": cache,
        },
        "content": [{"type": "text", "text": text}],
    }
    if mid is not None:
        message["id"] = mid
    return {"type": "assistant", "message": message}


def _other_row(kind, text, output, cache):
    """A transcript row whose type is not assistant.

    The text sits where an assistant row's text sits. The two usage
    fields are present so a row that is skipped only when usage is
    missing still carries them. The type word has no digits.
    """
    if not isinstance(kind, str) or kind == "" or kind == "assistant":
        raise HarnessError(f"non-assistant row type is not usable: {kind!r}")
    if any(ch.isdigit() for ch in kind):
        raise HarnessError(f"non-assistant row type contains a digit: {kind!r}")
    return {
        "type": kind,
        "message": {
            "usage": {
                "output_tokens": output,
                "cache_read_input_tokens": cache,
            },
            "content": [{"type": "text", "text": text}],
        },
    }


def _write_jsonl(directory, name, entries):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n",
        encoding="utf-8",
    )
    return path


def _prose_slice(text):
    stripped = re.sub(r"```[\s\S]*?```", " ", text)
    if len(stripped) > 40000:
        stripped = stripped[-40000:]
    return stripped.strip()


def _agreed_score(left, right):
    """Score of both entries, when the join does not change the number.

    The specification says both texts are scored. It does not name the
    characters placed between them, so the two arms are usable only when
    a space, a line break, and a blank line all yield one score, and that
    score is not the first entry alone.
    """
    scores = {
        measure_text(sep.join((left, right))).score
        for sep in ("\n\n", "\n", " ")
    }
    if len(scores) != 1:
        raise HarnessError(
            f"joined prose score depends on the separator: {scores}"
        )
    combined = scores.pop()
    only = measure_text(left).score
    if combined == only:
        raise HarnessError("adding the second entry did not move the score")
    return combined


def test_both_forms_show_help_and_cross_read_the_stored_level(isolated_ws):
    ws = isolated_ws
    plain = _ask(ws)
    named = _ask(ws, form=NAMED)
    for text in (plain, named):
        assert standalone_word_present(text, "full")
        _help_has_list(text)
    _store(ws, "strict", NAMED)
    assert_one_level_line(_status(ws, PLAIN), "strict")
    _store(ws, "lite", PLAIN)
    assert_one_level_line(_status(ws, NAMED), "lite")


def test_bare_invocation_names_the_level_after_it_changes(isolated_ws):
    ws = isolated_ws
    before_plain = _ask(ws)
    before_named = _ask(ws, form=NAMED)
    _store(ws, "strict")
    after_plain = _ask(ws)
    after_named = _ask(ws, form=NAMED)
    for before, after in (
        (before_plain, after_plain),
        (before_named, after_named),
    ):
        assert standalone_count(after, "strict") > standalone_count(before, "strict")
        assert standalone_count(before, "full") > standalone_count(after, "full")


def test_namespaced_form_covers_every_subcommand(isolated_ws):
    ws = isolated_ws
    _help_has_list(_ask(ws, "help", NAMED))
    healthy = _ask(ws, "doctor", NAMED)
    assert len(lines_with(healthy, success_marker(healthy))) == 4
    measured = zero_label_prose()
    path = _plant(ws, fresh_word() + ".md", measured.text)
    checked = _ask(ws, f"check {path}", NAMED)
    assert path.name in checked
    assert shows_integer(checked, measured.score)
    _empty_show(_ask(ws, "show", NAMED), "")
    _store(ws, "strict")
    transcript = _write_jsonl(
        Path(ws.path),
        "named.jsonl",
        [_assistant(OUTSIDE, 410, 820)],
    )
    stats = _ask(ws, "stats", NAMED, transcript_path=str(transcript))
    assert shows_integer(stats, 410) and shows_integer(stats, 820)
    assert standalone_word_present(stats, "strict")
    _store(ws, "lite", NAMED)
    assert_one_level_line(_status(ws, NAMED), "lite")
    _store(ws, "full", NAMED)
    assert_one_level_line(_status(ws), "full")
    off_reply = _store(ws, "off", NAMED)
    assert off_reply.strip()
    assert_one_level_line(_status(ws, NAMED), "off")
    _store(ws, "on", NAMED)
    assert_one_level_line(_status(ws, NAMED), "full")
    _clear_export(ws)
    _ask(ws, "init", NAMED, cwd=str(ws.path))
    assert _agents(ws).is_file()
    assert _rule(ws).is_file()


def test_command_still_replies_when_ordinary_prompts_go_silent(isolated_ws):
    ws = isolated_ws
    ordinary = "Please keep the parish notes."
    full_reason = _ask(ws, "full")
    assert standalone_word_present(full_reason, "full")
    reminded_obj, reminded = prompt_submission(ws, ordinary)
    assert reminded_obj is None or reminded_obj.get("decision") != "block"
    assert standalone_word_present(reminded, "full")
    off_reason = _ask(ws, "off")
    assert off_reason.strip()
    assert standalone_word_present(off_reason, "off")
    silent_obj, silent = prompt_submission(ws, ordinary)
    assert silent == ""
    assert silent_obj is None


def test_level_verbs_store_and_status_is_one_line(isolated_ws):
    ws = isolated_ws
    assert_one_level_line(_status(ws), "full")
    for level in ("lite", "full", "strict", "off"):
        _store(ws, level)
        assert_one_level_line(_status(ws), level)
    _store(ws, "full", NAMED)
    assert_one_level_line(_status(ws), "full")
    _store(ws, "off", NAMED)
    assert_one_level_line(_status(ws), "off")


def test_on_stores_full_and_confirms_both_words(isolated_ws):
    ws = isolated_ws
    _store(ws, "off")
    on_reply = _store(ws, "on")
    _store(ws, "full")
    assert standalone_count(on_reply, "full") >= 1
    assert_one_level_line(_status(ws), "full")
    _store(ws, "off")
    named_on = _store(ws, "on", NAMED)
    assert standalone_word_present(named_on, "on")
    assert standalone_count(named_on, "full") >= 1
    assert_one_level_line(_status(ws), "full")


def test_entire_prompt_stop_phrases_store_off(isolated_ws):
    ws = isolated_ws
    for phrase in ("stop prosecheck", "prosecheck off"):
        _store(ws, "full")
        phrase_reason = command_reply(ws, phrase)
        assert phrase_reason.strip()
        assert standalone_word_present(phrase_reason, "off")
        assert_one_level_line(_status(ws), "off")
        for built in (
            f"{fresh_word()} {phrase}",
            f"{phrase} {fresh_word()}",
        ):
            _store(ws, "full")
            built_obj, reply = prompt_submission(ws, built)
            assert built_obj is None or built_obj.get("decision") != "block"
            assert_one_level_line(_status(ws), "full")
            assert standalone_word_present(reply, "full")


def test_unknown_word_lists_the_valid_commands_and_keeps_the_level(isolated_ws):
    ws = isolated_ws
    _store(ws, "strict")
    for form in (PLAIN, NAMED):
        word = fresh_word()
        reply = _ask(ws, word, form)
        assert word in reply
        for sub in SUBCOMMANDS:
            assert standalone_word_present(reply, sub)
        assert word in strip_tokens(reply, SUBCOMMANDS)
        assert reports_word_as_unknown(reply, word), reply
        assert_one_level_line(_status(ws), "strict")


def test_help_lists_every_subcommand_except_itself(isolated_ws):
    ws = isolated_ws
    for form in (PLAIN, NAMED):
        _help_has_list(_ask(ws, "help", form))


def test_help_names_the_live_level_by_count(isolated_ws):
    ws = isolated_ws
    before = _ask(ws, "help")
    _store(ws, "strict")
    after = _ask(ws, "help")
    assert standalone_count(after, "strict") > standalone_count(before, "strict")
    assert standalone_count(before, "full") > standalone_count(after, "full")


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
def test_help_names_the_threshold_integers_and_the_export_path(isolated_ws, form):
    ws = isolated_ws
    text = _ask(ws, "help", form)
    for word in ("code", "commits", "config", "chat"):
        assert standalone_word_present(text, word)
    assert scope_never_touched(text), text[:500]
    assert "prosecheck this" in text
    assert "humanize this" in text

    def line_with(command):
        hits = [line for line in text.splitlines() if f"{PLAIN} {command}" in line]
        if len(hits) != 1:
            raise HarnessError(f"help has no single {command} line; text={text[:500]!r}")
        return hits[0]

    full_line = line_with("full")
    strict_line = line_with("strict")
    lite_line = line_with("lite")
    init_line = line_with("init")
    assert shows_integer(full_line, 40)
    assert shows_integer(strict_line, 20)
    assert not shows_integer(lite_line, 40)
    assert not shows_integer(lite_line, 20)
    assert "AGENTS.md" in init_line

    # Each remaining clause has to be visible on its own line. Separators,
    # order, and extra words may change; the line still has to state it.
    assert states_contract_only(lite_line), lite_line
    assert states_no_file_scoring(lite_line), lite_line
    assert states_contract_plus_guard(full_line), full_line
    assert states_guard_at_40_is_default(full_line), full_line
    assert states_guard_word(strict_line), strict_line
    assert states_character_scrub(strict_line), strict_line
    off_line = help_entry_line(text, "off")
    on_line = help_entry_line(text, "on")
    switch = off_line if off_line == on_line else f"{off_line}\n{on_line}"
    assert states_disable_and_reenable(switch), switch
    check_line = line_with("check")
    assert states_scores_file_without_rewrite(check_line), check_line
    doctor_line = line_with("doctor")
    assert states_health_check(doctor_line), doctor_line
    stats_line = line_with("stats")
    assert states_session_token_and_own_prose(stats_line), stats_line
    assert states_writes_contract_for_agents(init_line), init_line


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
def test_check_report_matches_the_detector_and_does_not_rewrite(isolated_ws, form):
    ws = isolated_ws
    measured = prose_with_confidence_reason()
    path = _plant(ws, fresh_word() + ".md", measured.text)
    before = path.read_bytes()
    reply = _ask(ws, f"check {check_path_argument(path, 'bare')}", form)
    require_check_summary(reply, measured, path.name, reason=True)
    again = _ask(ws, f"check {path}", form)
    require_check_summary(again, measured, path.name, reason=True)
    _bytes_same(path, before)
    high = high_confidence_prose()
    if high.reason:
        raise HarnessError(
            f"no-reason fixture still carries a reason: {high.reason!r}"
        )
    high_path = _plant(ws, fresh_word() + ".md", high.text)
    high_before = high_path.read_bytes()
    high_reply = _ask(ws, f"check {high_path}", form)
    require_check_summary(high_reply, high, high_path.name, reason=False)
    _bytes_same(high_path, high_before)


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
def test_check_prints_between_one_and_eight_labels_with_hit_counts(isolated_ws, form):
    ws = isolated_ws
    measured = many_label_prose()
    if len(measured.labels) <= 8:
        raise HarnessError("label-cap fixture does not exceed eight labels")
    path = _plant(ws, fresh_word() + ".md", measured.text)
    reply = _ask(ws, f"check {path}", form)
    printed = labels_in(reply, measured.labels)
    assert 1 <= len(printed) <= 8
    hits = label_hits(measured.text)
    kept = cut_first_integer(reply, measured.score)
    for label in printed:
        assert shows_integer(kept, hits[label])


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
def test_check_without_findings_has_a_visible_indication(isolated_ws, form):
    ws = isolated_ws
    dense = many_label_prose()
    quiet = zero_label_prose()
    path = _plant(ws, fresh_word() + ".md", quiet.text)
    reply = _ask(ws, f"check {path}", form)
    _check_facts(reply, quiet, path.name)
    left = strip_tokens(
        cut_first_integer(reply, quiet.score),
        [
            path.name,
            str(path),
            phrase_for_band(quiet.band),
            quiet.band,
            quiet.confidence,
            quiet.reason,
            *quiet.labels,
        ],
    )
    assert indicates_no_patterns_fired(left), left
    for label in dense.labels:
        assert label not in reply


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
@pytest.mark.parametrize("artifact", CHECK_PATH_ARTIFACTS)
def test_check_strips_surrounding_quotes_and_a_leading_at(
    isolated_ws, form, artifact
):
    ws = isolated_ws
    measured = prose_with_confidence_reason()
    path = _plant(ws, fresh_word() + ".md", measured.text)
    reply = _ask(ws, f"check {check_path_argument(path, artifact)}", form)
    require_check_summary(reply, measured, path.name, reason=True)


def test_check_asks_for_a_path(isolated_ws):
    ws = isolated_ws
    _store(ws, "strict")
    word = fresh_word()
    unknown_obj, unknown_joined = prompt_submission(ws, f"{PLAIN} {word}")
    asked_obj, asked_joined = prompt_submission(ws, f"{PLAIN} check")
    # The block decision is shared. A decision that is not a block is not
    # a different command reply. The reply is the reason, with that
    # decision set aside.
    unknown = block_reason(unknown_obj, unknown_joined)
    asked = block_reason(asked_obj, asked_joined)
    assert asked.strip()
    no_score_integers(asked)
    no_score_integers(asked_joined)
    # Soliciting a path is not scored. The typed word (the fresh word on
    # one side, check on the other) is removed from both replies, so an
    # operand echo is not a difference.
    asked_rest, unknown_rest = replies_without_typed_words(
        asked, unknown, [word, "check"]
    )
    assert asked_rest != unknown_rest


def test_check_not_a_file_unreadable_and_pdf_rtf_differ(isolated_ws):
    ws = isolated_ws
    folder = Path(ws.path) / fresh_word()
    folder.mkdir()
    missing = Path(ws.path) / (fresh_word() + ".md")
    pdf = write_plain(ws, fresh_word() + ".pdf", b"%PDF-1.1\n")
    rtf = write_plain(ws, fresh_word() + ".rtf", b"{\\rtf1 hi}")
    empty = _plant(ws, fresh_word() + ".md", "")
    before = {path: path.read_bytes() for path in (pdf, rtf, empty)}
    directory = _ask(ws, f"check {folder}")
    absent = _ask(ws, f"check {missing}")
    pdf_reply = _ask(ws, f"check {pdf}")
    rtf_reply = _ask(ws, f"check {rtf}")
    _ask(ws, f"check {empty}")
    for reply, path in (
        (directory, folder),
        (absent, missing),
        (pdf_reply, pdf),
        (rtf_reply, rtf),
    ):
        _no_score(reply, path)
    assert str(missing) in absent

    def rest(reply, *tokens):
        left = strip_tokens(reply, tokens)
        assert left, reply[:300]
        return left

    directory_rest = rest(directory, str(folder), folder.name)
    absent_rest = rest(absent, str(missing), missing.name)
    pdf_rest = rest(pdf_reply, str(pdf), pdf.name)
    rtf_rest = rest(rtf_reply, str(rtf), rtf.name)
    assert directory_rest != absent_rest
    assert directory_rest != pdf_rest
    assert pdf_rest == rtf_rest
    assert pdf_rest != absent_rest
    assert states_not_a_file(directory)
    assert states_cannot_read(absent)
    assert states_no_readable_text(pdf_reply)
    assert states_no_readable_text(rtf_reply)
    for path, blob in before.items():
        _bytes_same(path, blob)


def _rel(ws, path):
    return str(Path(path).relative_to(ws.path))


def test_check_over_cap_names_kilobytes_and_no_score(isolated_ws):
    ws = isolated_ws
    prose = zero_label_prose()

    def plain_pair(suffix):
        under = _plant(ws, fresh_word() + suffix, prose.text)
        pad_file_to_size(under, UNDER_BOTH)
        under_reply = _ask(ws, f"check {under}")
        assert shows_integer(under_reply, measure_path(ws, _rel(ws, under)).score)
        over = _plant(ws, fresh_word() + suffix, prose.text)
        pad_file_to_size(over, OVER_BOTH_512)
        before = over.read_bytes()
        over_reply = _ask(ws, f"check {over}")
        assert shows_integer(over_reply, 512)
        assert states_over_cap(over_reply, 512)
        _no_score(over_reply, over)
        _bytes_same(over, before)

    plain_pair(".md")
    plain_pair(".txt")
    between = write_docx(ws, fresh_word() + ".docx", prose.text)
    pad_file_to_size(between, BETWEEN_CAPS)
    between_reply = _ask(ws, f"check {between}")
    assert between.name in between_reply
    assert shows_integer(between_reply, measure_path(ws, _rel(ws, between)).score)
    notebook = write_notebook(ws, fresh_word() + NOTEBOOK_EXT, markdown=prose.text)
    pad_file_to_size(notebook, BETWEEN_CAPS)
    notebook_reply = _ask(ws, f"check {notebook}")
    assert notebook.name in notebook_reply
    assert shows_integer(notebook_reply, measure_path(ws, _rel(ws, notebook)).score)

    for suffix, size in (
        (".docx", OVER_BOTH_4MB),
        (".docx", OVER_BOTH_4MB_OTHER),
        (".pptx", OVER_BOTH_4MB),
        (NOTEBOOK_EXT, OVER_BOTH_4MB),
    ):
        if suffix == NOTEBOOK_EXT:
            path = write_notebook(ws, fresh_word() + suffix, markdown=prose.text)
        elif suffix == ".pptx":
            path = write_pptx(ws, fresh_word() + suffix, prose.text)
        else:
            path = write_docx(ws, fresh_word() + suffix, prose.text)
        pad_file_to_size(path, size)
        reply = _ask(ws, f"check {path}")
        _no_score(reply, path)
        figures = kilobyte_figure_in(reply)
        assert figures, (
            f"reply does not name the 4 MB cap in kilobytes; reply={reply[:400]!r}"
        )
        assert any(states_over_cap(reply, figure) for figure in figures), (
            f"reply does not report the file as over that cap; "
            f"figures={figures!r} reply={reply[:400]!r}"
        )


def test_check_python_missing_names_no_score(isolated_ws):
    ws = isolated_ws
    path = _plant(ws, fresh_word() + ".md", zero_label_prose().text)
    before = path.read_bytes()
    missing_py = _ask(ws, f"check {path}", env_updates=node_kept_without_interpreters())
    _no_score(missing_py, path)
    assert states_detector_unavailable(missing_py)
    _bytes_same(path, before)
    unreadable = _ask(ws, f"check {Path(ws.path) / (fresh_word() + '.md')}")
    py_rest = strip_tokens(missing_py, [str(path), path.name])
    assert py_rest not in unreadable


def test_check_names_the_file_only_for_no_output_and_stated_failure(isolated_ws):
    ws = isolated_ws
    path = _plant(ws, fresh_word() + ".md", zero_label_prose().text)
    before = path.read_bytes()
    mark = fresh_word()
    failure = fresh_word()
    with interpreter_standin(ws, stdout=None, exit_code=0) as quiet:
        no_output = _ask(ws, f"check {path}", env_updates=quiet.env_updates)
    with interpreter_standin(ws, stdout=None, exit_code=211) as quiet_fail:
        silent = _ask(ws, f"check {path}", env_updates=quiet_fail.env_updates)
    with interpreter_standin(ws, stdout=f"note {mark}\n", exit_code=0) as junk:
        not_report = _ask(ws, f"check {path}", env_updates=junk.env_updates)
    with emitted_failure_standin(ws, failure) as failed:
        stated = _ask(ws, f"check {path}", env_updates=failed.env_updates)
    missing_py = _ask(ws, f"check {path}", env_updates=node_kept_without_interpreters())
    unreadable = _ask(ws, f"check {Path(ws.path) / 'gone.md'}")
    for reply in (no_output, silent, not_report, stated, missing_py):
        _no_score(strip_tokens(reply, [failure, mark]), path)
    assert path.name in no_output
    assert failure not in no_output
    assert path.name in silent
    assert failure not in silent
    # The file name is not the failure report. The exit status is not
    # required, so it is not what this arm looks for.
    silent_left = strip_tokens(silent, [path.name, str(path)])
    assert states_failure_report(silent_left)
    assert not states_no_report(silent)
    assert path.name not in not_report
    assert failure not in not_report
    assert path.name in stated
    assert failure in stated
    phrase = shared_phrase(
        strip_tokens(no_output, [path.name, str(path), mark, failure]),
        strip_tokens(not_report, [path.name, str(path), mark, failure]),
        [missing_py, unreadable],
    )
    assert states_no_report(phrase)
    assert not states_no_report(missing_py)
    assert not states_no_report(unreadable)
    _bytes_same(path, before)


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
def test_check_names_the_window_only_when_truncated(isolated_ws, form):
    ws = isolated_ws
    exact = write_docx(ws, fresh_word() + ".docx", window_body(262144))
    longer = write_docx(ws, fresh_word() + ".docx", window_body(262145))
    assert exact.stat().st_size < 4 * 1024 * 1024
    assert longer.stat().st_size < 4 * 1024 * 1024
    exact_reply = _ask(ws, f"check {exact}", form)
    longer_reply = _ask(ws, f"check {longer}", form)
    assert readable_scores_0_100(exact_reply)
    assert readable_scores_0_100(longer_reply)
    assert not window_named(exact_reply)
    assert window_named(longer_reply)
    assert not states_only_prefix_scored(exact_reply)
    assert states_only_prefix_scored(longer_reply)


def _mode_lines(text, marker):
    return lines_with(text, marker)


_TOOL_SUBJECTS = ("tool", "it")
_IS_FORMS = ("separate", "contracted")
_POLARITIES = ("affirmative", "negated")
_CONTRACTION_MARKS = ("'", "\u2019")
# The live affirmation, so a varied phrase can take its place. One
# intervening word is allowed, matching the closer check. A negation in
# that spot is a denial and is not this span.
_AFFIRMATION_SPAN = re.compile(
    r"(?i)\b(?:the\s+)?"
    r"(?:it|tool)"
    r"(?:['\u2019]s|\s+is)"
    r"(?:\s+(?!not\b|no\b|never\b|without\b|dont\b|doesnt\b|wont\b)\w+)?"
    r"\s+on\b"
)


def _tool_state_phrases(subject, is_form, polarity):
    """Affirmations or denials built from the four closer dimensions.

    The phrases are the dimension, not a fixed sentence list. ``tool`` is
    the noun. ``it`` is the pronoun whose antecedent is the tool.
    """
    if subject not in _TOOL_SUBJECTS or is_form not in _IS_FORMS:
        raise AssertionError((subject, is_form, polarity))
    if polarity not in _POLARITIES:
        raise AssertionError((subject, is_form, polarity))
    head = "the tool" if subject == "tool" else "it"
    if is_form == "separate" and polarity == "affirmative":
        return (f"{head} is on",)
    if is_form == "separate" and polarity == "negated":
        return (
            f"{head} is not on",
            *(f"{head} isn{mark}t on" for mark in _CONTRACTION_MARKS),
        )
    if is_form == "contracted" and polarity == "affirmative":
        return tuple(f"{head}{mark}s on" for mark in _CONTRACTION_MARKS)
    return tuple(f"{head}{mark}s not on" for mark in _CONTRACTION_MARKS)


def _with_tool_state(closer, phrase):
    """The same closer, with its affirmation replaced by *phrase*.

    Caps, the window, and the show pointer stay. The live closer has to
    contain an affirmation this can replace.
    """
    if _AFFIRMATION_SPAN.search(closer) is None:
        raise AssertionError(
            f"healthy closer has no affirmation to vary; closer={closer!r}"
        )
    return _AFFIRMATION_SPAN.sub(lambda _match: phrase, closer)


@pytest.mark.parametrize("form", (PLAIN, NAMED), ids=("plain", "named"))
@pytest.mark.parametrize("subject", _TOOL_SUBJECTS, ids=("noun", "pronoun"))
@pytest.mark.parametrize("is_form", _IS_FORMS, ids=("separate", "contracted"))
@pytest.mark.parametrize("polarity", _POLARITIES, ids=("affirmative", "negated"))
def test_doctor_healthy_on_install_shows_four_successes_and_the_caps(
    isolated_ws, form, subject, is_form, polarity
):
    ws = isolated_ws
    levels = ("lite", "full", "strict") if form == PLAIN else ("full",)
    closers = []
    for level in levels:
        _store(ws, level)
        reply = _ask(ws, "doctor", form)
        marker = success_marker(reply)
        check_lines = _mode_lines(reply, marker)
        assert len(check_lines) == 4
        require_four_healthy_checks(check_lines, level)
        if form == PLAIN:
            assert standalone_word_present(reply, level)
        closer = closing_line(reply)
        assert shows_integer(closer, 512)
        assert archive_cap_named(closer)
        assert window_named(closer)
        assert points_at_show_command(closer, form)
        assert points_at_show_for_partial_or_skipped(closer, form)
        assert states_tool_is_on(closer)
        for phrase in _tool_state_phrases(subject, is_form, polarity):
            varied = _with_tool_state(closer, phrase)
            assert shows_integer(varied, 512), phrase
            assert archive_cap_named(varied), phrase
            assert window_named(varied), phrase
            assert points_at_show_command(varied, form), phrase
            assert points_at_show_for_partial_or_skipped(varied, form), phrase
            if polarity == "affirmative":
                assert states_tool_is_on(varied), phrase
            else:
                assert not states_tool_is_on(varied), phrase
        if subject == "it" and is_form == "contracted":
            bare = _with_tool_state(closer, "its on")
            assert shows_integer(bare, 512)
            assert archive_cap_named(bare)
            assert window_named(bare)
            assert points_at_show_command(bare, form)
            assert points_at_show_for_partial_or_skipped(bare, form)
            assert not states_tool_is_on(bare)
        left = strip_tokens(
            closer,
            [PLAIN, NAMED, "show", 512, 4000, 4096, 262144, "262,144"],
        )
        assert left
        closers.append(left)


def test_doctor_does_not_pass_without_running_the_detector(isolated_ws):
    ws = isolated_ws
    _store(ws, "full")
    with interpreter_standin(ws, sleep_s=0.05, forward=True) as stand:
        before = stand.invocations()
        healthy = _ask(ws, "doctor", env_updates=stand.env_updates)
        assert stand.invocations() > before
        mid = stand.invocations()
        probe_env = dict(os.environ)
        probe_env.update(stand.env_updates)
        probe_env["F05_STUB_PROBE"] = "1"
        subprocess.run(
            [str(stand.root / "python3"), "-c", "import sys"],
            env=probe_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        assert stand.invocations() > mid
    marker = success_marker(healthy)
    healthy_lines = _mode_lines(healthy, marker)
    assert len(healthy_lines) == 4
    require_four_healthy_checks(healthy_lines, "full")
    healthy_left = strip_tokens(
        closing_line(healthy),
        [PLAIN, NAMED, "show", 512, 4000, 4096, 262144, "262,144"],
    )
    with interpreter_standin(ws, stdout="not a score\n", exit_code=0) as stand:
        before_fault = stand.invocations()
        faulty = _ask(ws, "doctor", NAMED, env_updates=stand.env_updates)
        assert stand.invocations() > before_fault
    kept = _mode_lines(faulty, marker)
    assert len(kept) < 4
    assert any(states_current_mode_line(line, "full") for line in kept)
    assert any(states_detector_present_line(line) for line in kept)
    assert any(states_writable_settings_line(line) for line in kept)
    assert not any(states_python_score_line(line) for line in kept)
    closer = closing_line(faulty)
    assert "/prosecheck doctor" in closer
    assert states_fix_lines_and_rerun_doctor(closer)
    fault_left = strip_tokens(closer, ["/prosecheck doctor"])
    assert fault_left
    assert fault_left != healthy_left
    # Title is the first non-empty line, closer the last. The Python-run
    # check is one of the lines between them, not whichever leftover line
    # happens to contain the word Python.
    checks = doctor_check_lines(faulty)
    assert len(checks) == 4
    success_checks = [line for line in checks if carries_marker(line, marker)]
    fault_checks = [line for line in checks if not carries_marker(line, marker)]
    assert len(success_checks) == 3
    assert len(fault_checks) == 1
    success_kinds = (
        ("current mode", lambda line: states_current_mode_line(line, "full")),
        ("detector present", states_detector_present_line),
        ("writable settings", states_writable_settings_line),
    )
    for name, pred in success_kinds:
        hits = [line for line in success_checks if pred(line)]
        assert len(hits) == 1, (name, hits, success_checks)
    for line in success_checks:
        matched = [name for name, pred in success_kinds if pred(line)]
        assert len(matched) == 1, (matched, line)
    assert not any(states_python_score_line(line) for line in success_checks)
    python_run = fault_checks[0]
    assert standalone_word_present(python_run, "python")
    assert not states_python_missing_statement(python_run)


def test_doctor_python_missing_keeps_the_detector_line(isolated_ws):
    ws = isolated_ws
    _store(ws, "full")
    healthy = _ask(ws, "doctor")
    marker = success_marker(healthy)
    missing = _ask(ws, "doctor", env_updates=node_kept_without_interpreters())
    absence_lines = [
        line.strip()
        for line in missing.splitlines()
        if line.strip() and not carries_marker(line, marker) and states_python_missing(line)
    ]
    assert absence_lines
    python_lines = [
        line
        for line in absence_lines
        if states_prose_still_shaped(line) and states_saved_files_not_rescored(line)
    ]
    assert python_lines
    for line in python_lines:
        assert states_python_missing(line)
        assert states_prose_still_shaped(line)
        assert states_saved_files_not_rescored(line)
    kept = [
        line.strip()
        for line in missing.splitlines()
        if line.strip() and carries_marker(line, marker)
    ]
    assert kept
    detector_lines = [
        line
        for line in kept
        if holds_aside_from_python_word(line, states_detector_present_line)
    ]
    assert detector_lines
    assert not any(states_python_missing(line) for line in detector_lines)
    assert not any(states_saved_files_not_rescored(line) for line in detector_lines)
    assert any(states_current_mode_line(line, "full") for line in kept)
    assert any(
        holds_aside_from_python_word(line, states_writable_settings_line)
        for line in kept
    )
    for selected in python_lines:
        python_rest = strip_tokens(selected, [marker])
        for line in kept:
            assert python_rest not in line
    root = Path(tempfile.mkdtemp(prefix="f06-detect-"))
    try:
        (root / "scripts").mkdir()
        moved = _ask(ws, "doctor", env_updates={ENV_PLUGIN_ROOT: str(root)})
    finally:
        os.rmdir(root / "scripts")
        root.rmdir()
    missing_kept = _mode_lines(missing, marker)
    moved_kept = _mode_lines(moved, marker)
    assert len(moved_kept) < len(missing_kept)
    assert any(
        holds_aside_from_python_word(line, states_detector_present_line)
        for line in missing_kept
    )
    assert not any(states_detector_present_line(line) for line in moved_kept)
    moved_closer = closing_line(moved)
    detector_checks = [
        line.strip()
        for line in moved.splitlines()
        if line.strip()
        and line.strip() != moved_closer
        and states_detector_presence_check(line)
    ]
    assert detector_checks
    assert all(not carries_marker(line, marker) for line in detector_checks)
    assert not any(states_detector_present_line(line) for line in detector_checks)
    assert "/prosecheck doctor" in moved_closer
    assert states_fix_lines_and_rerun_doctor(moved_closer)


def _try_create(directory: Path) -> bool:
    """Whether this process can create a file in *directory*.

    A successful create is removed. A permission error is the blocked
    result. Any other failure is not treated as blocked.
    """
    probe = directory / ("probe-" + fresh_word())
    try:
        probe.write_text("x", encoding="utf-8")
    except PermissionError:
        return False
    except OSError as exc:
        raise HarnessError(
            f"settings directory probe failed: {exc}"
        ) from exc
    probe.unlink()
    return True


# prctl securebits. NOROOT stops a root exec from regaining every
# capability, so a mode bit applies to the hook the same way it applies
# to an unprivileged process. The bit is restored after the window.
_PR_GET_SECUREBITS = 27
_PR_SET_SECUREBITS = 28
_SECBIT_NOROOT = 1
_SAVED_SECUREBITS: int | None = None


def _prctl(option: int, arg2: int = 0) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    rc = libc.prctl(option, arg2, 0, 0, 0)
    if rc < 0:
        err = ctypes.get_errno()
        raise HarnessError(f"prctl {option} failed: errno={err}")
    return int(rc)


def _hold_root_mode_bits() -> None:
    """Make hook children honor directory mode bits even when uid is 0."""
    global _SAVED_SECUREBITS
    if _SAVED_SECUREBITS is not None:
        raise HarnessError("root mode-bit window is already open")
    current = _prctl(_PR_GET_SECUREBITS)
    if current & _SECBIT_NOROOT:
        _SAVED_SECUREBITS = current
        return
    _prctl(_PR_SET_SECUREBITS, current | _SECBIT_NOROOT)
    _SAVED_SECUREBITS = current


def _release_root_mode_bits() -> None:
    global _SAVED_SECUREBITS
    saved = _SAVED_SECUREBITS
    _SAVED_SECUREBITS = None
    if saved is None:
        return
    _prctl(_PR_SET_SECUREBITS, saved)


def _grant_other_access(root: Path) -> list[tuple[Path, int]]:
    """Let a process without override read *root* and the directories above it.

    The product tree may be private to another uid. Mode bits on the
    settings folder still decide whether that folder is writable. The
    returned modes are what the tree had before this grant.
    """
    changed: list[tuple[Path, int]] = []

    def widen(path: Path, extra: int) -> None:
        if path.is_symlink():
            return
        mode = path.stat().st_mode & 0o777
        if mode & extra == extra:
            return
        changed.append((path, mode))
        os.chmod(path, mode | extra)

    current = root.resolve()
    ancestors: list[Path] = []
    while True:
        ancestors.append(current)
        if current == current.parent:
            break
        current = current.parent
    for path in reversed(ancestors):
        widen(path, 0o005)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath)
        widen(base, 0o005)
        for name in dirnames:
            path = base / name
            if not path.is_symlink():
                widen(path, 0o005)
        for name in filenames:
            path = base / name
            if not path.is_symlink():
                widen(path, 0o004)
    return changed


def _child_cannot_create(directory: Path) -> bool:
    """A fresh child cannot create a file in *directory*.

    The child is the same kind of exec the hook will be. A child that
    still creates the file means the folder is writable for the product.
    """
    probe = directory / ("probe-" + fresh_word())
    script = (
        "import pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text('x', encoding='utf-8')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(probe)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    created = probe.exists()
    if created:
        probe.unlink()
    if completed.returncode < 0:
        raise HarnessError(
            "settings probe was killed: "
            f"signal={-completed.returncode} stderr={completed.stderr[:200]!r}"
        )
    return not created and completed.returncode != 0


@contextmanager
def _settings_unwritable(ws):
    """The settings folder is not writable for the doctor process.

    A mode bit is enough when this process is not privileged. A privileged
    process still creates files in a mode-555 directory, and a root exec
    would too, so hook children are started without that override for the
    window. Afterwards this process can create a file there again.
    """
    config = Path(ws.config_dir)
    os.chmod(config, 0o555)
    limited = False
    opened: list[tuple[Path, int]] = []
    try:
        if _try_create(config):
            opened = _grant_other_access(Path(ws.root))
            _hold_root_mode_bits()
            limited = True
            if not _child_cannot_create(config):
                raise HarnessError("settings directory stayed writable")
        elif not _child_cannot_create(config):
            raise HarnessError("settings directory stayed writable")
        yield
    finally:
        if limited:
            _release_root_mode_bits()
        for path, mode in reversed(opened):
            if path.exists() or path.is_symlink():
                os.chmod(path, mode)
        os.chmod(config, 0o755)
        probe = config / ("probe-" + fresh_word())
        probe.write_text("x", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "x":
            raise HarnessError(
                "settings directory did not accept a write after restore"
            )
        probe.unlink()


def test_doctor_off_mode_and_faults_use_the_stated_spellings(isolated_ws):
    ws = isolated_ws
    _store(ws, "full")
    healthy = _ask(ws, "doctor")
    marker = success_marker(healthy)
    healthy_left = strip_tokens(
        closing_line(healthy),
        [PLAIN, NAMED, "show", "on", 512, 4000, 4096, 262144, "262,144"],
    )
    _store(ws, "off")
    with interpreter_standin(ws, sleep_s=0.05, forward=True) as stand:
        before = stand.invocations()
        named_off = _ask(ws, "doctor", NAMED, env_updates=stand.env_updates)
        assert stand.invocations() > before
    named_success = _mode_lines(named_off, marker)
    assert len(named_success) == 3
    require_three_off_success_checks(named_success)
    off_closer = off_only_closer_lines(named_off)
    assert off_closer, named_off
    for closer in off_closer:
        assert standalone_word_present(closer, "on")
        assert points_at_on_command(closer, NAMED), closer
        assert states_nothing_wrong_with_install(closer), closer
        assert states_saved_files_not_scored_until_on(closer), closer
        off_left = strip_tokens(
            closer,
            [PLAIN, NAMED, "show", "on", 512, 4000, 4096, 262144, "262,144"],
        )
        assert off_left
        assert off_left != healthy_left
    mode_line = off_marked_mode_lines(named_off)
    assert mode_line, named_off
    for line in mode_line:
        assert standalone_word_present(line, "off")
        assert standalone_word_present(line, "on")
        assert points_at_on_command(line, PLAIN), line
    with interpreter_standin(ws, sleep_s=0.05, forward=True) as stand:
        before = stand.invocations()
        plain_off = _ask(ws, "doctor", env_updates=stand.env_updates)
        assert stand.invocations() > before
    plain_success = _mode_lines(plain_off, marker)
    assert len(plain_success) == 3
    require_three_off_success_checks(plain_success)
    plain_closer = off_only_closer_lines(plain_off)
    assert plain_closer, plain_off
    for closer in plain_closer:
        assert states_nothing_wrong_with_install(closer), closer
        assert states_saved_files_not_scored_until_on(closer), closer
        assert points_at_on_command(closer, PLAIN), closer
    plain_mode = off_marked_mode_lines(plain_off)
    assert plain_mode, plain_off
    for line in plain_mode:
        assert standalone_word_present(line, "off")
        assert standalone_word_present(line, "on")
        assert points_at_on_command(line, PLAIN), line
    with _settings_unwritable(ws):
        both = _ask(ws, "doctor", NAMED)
    both_closer = closing_line(both)
    assert "/prosecheck doctor" in both_closer
    assert states_fix_lines_and_rerun_doctor(both_closer)
    assert not states_nothing_wrong_with_install(both_closer)
    assert all(both_closer != closer for closer in off_closer)
    _store(ws, "full")
    with _settings_unwritable(ws):
        settings = _ask(ws, "doctor")
    settings_kept = _mode_lines(settings, marker)
    assert len(settings_kept) == 3
    assert any(states_current_mode_line(line, "full") for line in settings_kept)
    assert any(states_detector_present_line(line) for line in settings_kept)
    assert any(states_python_score_line(line) for line in settings_kept)
    assert not any(states_writable_settings_line(line) for line in settings_kept)
    settings_faults = [
        line.strip()
        for line in settings.splitlines()
        if line.strip()
        and not carries_marker(line, marker)
        and states_settings_folder_not_writable(line)
        and not states_fix_lines_and_rerun_doctor(line)
    ]
    assert settings_faults, settings
    python_missing = [
        line.strip()
        for line in _ask(
            ws, "doctor", env_updates=node_kept_without_interpreters()
        ).splitlines()
        if line.strip()
        and not carries_marker(line, marker)
        and standalone_word_present(line, "Python")
    ][0]
    for fault in settings_faults:
        assert not carries_marker(fault, marker)
        assert states_settings_folder_not_writable(fault), fault
        assert not states_writable_settings_line(fault)
        assert not standalone_word_present(fault, "Python")
        assert strip_tokens(fault, [marker]) != strip_tokens(
            python_missing, [marker]
        )
    settings_closer = closing_line(settings)
    assert "/prosecheck doctor" in settings_closer
    assert states_fix_lines_and_rerun_doctor(settings_closer)


def test_show_empty_ledger_names_the_deliverable_suffixes(isolated_ws):
    ws = isolated_ws
    session = runtime_token("s")
    absent = fresh_word() + ".md"
    empty = _ask(ws, "show", session_id=session)
    _empty_show(empty, absent)
    measured = prose_dense()
    path = _plant(ws, fresh_word() + ".md", measured.text)
    _save(ws, path, session)
    shown = _ask(ws, "show", session_id=session)
    assert path.name in shown
    assert shows_integer(shown, measured.score)
    assert measured.band in shown
    assert phrase_for_band(measured.band) in shown
    assert NOT_AUTHOR not in shown


def test_show_lists_newest_first_against_name_and_score_order(isolated_ws):
    ws = isolated_ws
    session = runtime_token("s")
    older_text = prose_dense()
    newer_text = prose_under()
    assert newer_text.score < older_text.score
    assert older_text.score - newer_text.score >= 2
    # The third row's score sits strictly between the other two. The guard
    # reads it from this detector's own report with the score set there.
    newest_text, newest_report = pinned_score(
        newer_text.score + 1 + secrets.randbelow(older_text.score - newer_text.score - 1)
    )
    assert newer_text.score < newest_text.score < older_text.score
    older = _plant(ws, "a" + fresh_word() + ".md", older_text.text)
    newer = _plant(ws, "z" + fresh_word() + ".md", newer_text.text)
    newest = _plant(ws, "m" + fresh_word() + ".md", newest_text.text)
    assert newer.name > older.name
    assert older.name < newest.name < newer.name
    recency = (newest.name, newer.name, older.name)
    by_name = tuple(sorted((older.name, newer.name, newest.name)))
    by_score = tuple(
        name
        for _score, name in sorted(
            (
                (older_text.score, older.name),
                (newer_text.score, newer.name),
                (newest_text.score, newest.name),
            )
        )
    )
    assert recency not in {
        by_name,
        tuple(reversed(by_name)),
        by_score,
        tuple(reversed(by_score)),
    }
    _save(ws, older, session)
    _save(ws, newer, session)
    fire_pinned(ws, newest_report, tool="Write", session_id=session, file_path=str(newest))
    for form in (PLAIN, NAMED):
        shown = _ask(ws, "show", form, session_id=session)
        assert older.name in shown and newer.name in shown and newest.name in shown
        assert shown.find(newest.name) < shown.find(newer.name)
        assert shown.find(newer.name) < shown.find(older.name)


def _row_rest(text, name, measured, others):
    base = status_remainder(text, name, measured, others=others)
    hits = label_hits(measured.text)
    return strip_tokens(base, [hits[label] for label in measured.labels if label in hits])


def test_show_flagged_bit_only_when_the_row_has_labels(isolated_ws):
    ws = isolated_ws
    session = runtime_token("s")
    flagged = prose_dense()
    under = prose_under()
    quiet = zero_label_prose()
    if len(flagged.labels) <= 5:
        raise HarnessError("show label-cap fixture does not exceed five labels")
    flagged_path = _plant(ws, fresh_word() + ".md", flagged.text)
    under_path = _plant(ws, fresh_word() + ".md", under.text)
    quiet_path = _plant(ws, fresh_word() + ".md", quiet.text)
    exact = write_docx(ws, fresh_word() + ".docx", window_body(262144))
    longer = write_docx(ws, fresh_word() + ".docx", window_body(262145))
    for path in (flagged_path, under_path, quiet_path, exact, longer):
        _save(ws, path, session)
    shown = _ask(ws, "show", session_id=session)
    names = [flagged_path.name, under_path.name, quiet_path.name]
    flagged_rest = _row_rest(shown, flagged_path.name, flagged, names)
    under_rest = _row_rest(shown, under_path.name, under, names)
    assert flagged_rest and under_rest
    assert flagged_rest != under_rest
    flagged_row = row_around(shown, flagged_path.name, names)
    under_row = row_around(shown, under_path.name, names)
    assert states_flagged(flagged_row)
    assert not states_under_threshold(flagged_row)
    assert states_under_threshold(under_row)
    printed = labels_in(row_around(shown, flagged_path.name, names), flagged.labels)
    assert 1 <= len(printed) <= 5
    quiet_row = row_around(shown, quiet_path.name, names)
    require_scored_row_shows(quiet_row, quiet, quiet_path.name)
    quiet_rest = strip_tokens(
        quiet_row,
        [
            quiet_path.name,
            quiet.score,
            quiet.band,
            phrase_for_band(quiet.band),
            quiet.reason,
            *quiet.labels,
            *CONFIDENCE_WORDS,
            *LEVEL_WORDS,
            262144,
            "262,144",
        ],
    )
    assert flagged_rest not in quiet_rest
    assert under_rest not in quiet_rest
    assert not states_flagged(quiet_row)
    assert not states_under_threshold(quiet_row)
    exact_row = row_around(shown, exact.name, [exact.name, longer.name])
    longer_row = row_around(shown, longer.name, [exact.name, longer.name])
    assert not window_named(exact_row)
    assert window_named(longer_row)
    assert not states_only_prefix_scored(exact_row)
    assert states_only_prefix_scored(longer_row)


def test_show_size_binary_and_failed_rows_differ(isolated_ws):
    ws = isolated_ws
    session = runtime_token("s")
    scored = prose_under()
    scored_path = _plant(ws, fresh_word() + ".md", scored.text)
    sized = _plant(ws, fresh_word() + ".md", "note")
    pad_file_to_size(sized, OVER_BOTH_512)
    archive = write_notebook(ws, fresh_word() + NOTEBOOK_EXT, markdown="note")
    pad_file_to_size(archive, OVER_BOTH_4MB)
    binary = write_plain(ws, fresh_word() + ".pdf", b"%PDF-1.1\n")
    missing = Path(ws.path) / (fresh_word() + ".md")
    names = [
        scored_path.name,
        sized.name,
        archive.name,
        binary.name,
        missing.name,
    ]
    for path in (scored_path, sized, archive, binary, missing):
        _save(ws, path, session)
    shown = _ask(ws, "show", session_id=session)
    assert sized.name in shown
    assert archive.name in shown
    size_row = row_around(shown, sized.name, names)
    assert shows_integer(size_row, 512)
    assert states_not_scored(size_row)
    _no_score(size_row, sized)
    require_size_skip_row(size_row, sized.name, (512,))
    archive_row = row_around(shown, archive.name, names)
    require_size_skip_row(archive_row, archive.name, ARCHIVE_KB_FIGURES)
    _no_score(archive_row, archive)
    binary_row = row_around(shown, binary.name, names)
    failed_row = row_around(shown, missing.name, names)
    _no_score(binary_row, binary)
    _no_score(failed_row, missing)
    size_rest = strip_tokens(size_row, [sized.name, 512, str(sized)])
    binary_rest = strip_tokens(binary_row, [binary.name, str(binary)])
    failed_rest = strip_tokens(failed_row, [missing.name, str(missing)])
    assert size_rest and binary_rest and failed_rest
    assert size_rest != strip_tokens(
        row_around(shown, scored_path.name, [scored_path.name, sized.name]),
        [scored_path.name, scored.score, scored.band, phrase_for_band(scored.band)],
    )
    assert binary_rest != size_rest
    assert failed_rest != size_rest
    assert failed_rest != binary_rest
    assert states_not_rescored(binary_row)
    assert states_not_scored(failed_row)
    assert states_readable_failure_reason(failed_rest)
    assert strip_tokens(failed_row, [missing.name, str(missing)])


def test_show_omits_parent_path_and_body(isolated_ws):
    ws = isolated_ws
    session = runtime_token("s")
    parent_token = "parent" + fresh_word()
    body_token = "body" + fresh_word()
    folder = Path(ws.path) / parent_token
    folder.mkdir()
    path = write_plain(ws, f"{parent_token}/note.md", prose_under().text + " " + body_token)
    _save(ws, path, session)
    shown = _ask(ws, "show", session_id=session)
    assert "note.md" in shown
    assert parent_token not in shown
    assert body_token not in shown


def test_show_sessions_do_not_mix(isolated_ws):
    ws = isolated_ws
    first = runtime_token("a")
    second = runtime_token("b")
    path_a = _plant(ws, fresh_word() + ".md", prose_under().text)
    path_b = _plant(ws, fresh_word() + ".md", prose_dense().text)
    _save(ws, path_a, first)
    _save(ws, path_b, second)
    for form in (PLAIN, NAMED):
        shown_a = _ask(ws, "show", form, session_id=first)
        shown_b = _ask(ws, "show", form, session_id=second)
        assert path_a.name in shown_a and path_b.name not in shown_a
        assert path_b.name in shown_b and path_a.name not in shown_b


def test_show_omits_a_ledger_only_when_older_than_seven_days(isolated_ws):
    ws = isolated_ws
    day_ms = 24 * 3600 * 1000

    def shown_after_later_session(offset_ms):
        session = runtime_token("s")
        path = _plant(ws, fresh_word() + ".md", prose_under().text)
        _save(ws, path, session)
        ledgers = files_holding_basename(ws.config_dir, path.name)
        if len(ledgers) != 1:
            raise HarnessError(f"expected one ledger holding {path.name}, found {ledgers}")
        # The later session (its start and the show that follows) runs on one
        # clock, so the ledger's age is the same offset for every hook of that
        # session, whichever of them sweeps.
        with shared_sweep_clock() as (clock_ms, env):
            stamp_cutoff_offset(ledgers[0], clock_ms, offset_ms)
            require_hook_success(session_start(ws, env_updates=env))
            shown = _ask(ws, "show", session_id=session, env_updates=env)
        return path.name, shown

    # Signed offset from the seven-day cutoff on the sweep's clock.
    # Negative is younger, zero is exactly seven days, positive is older.
    # More than seven days is not listed by the later session.
    older_name, older_shown = shown_after_later_session(day_ms)
    assert older_name not in older_shown
    _empty_show(older_shown, older_name)
    just_past_name, just_past_shown = shown_after_later_session(1000)
    assert just_past_name not in just_past_shown
    _empty_show(just_past_shown, just_past_name)
    # Not more than seven days, including exactly seven days, stays listed.
    younger_name, younger_shown = shown_after_later_session(-day_ms)
    assert younger_name in younger_shown
    exact_name, exact_shown = shown_after_later_session(0)
    assert exact_name in exact_shown


def test_init_exports_a_portable_contract_and_a_prose_rule(isolated_ws):
    ws = isolated_ws
    outside = "Parish mill wheel stays in the margin."
    for word in BANNED_VOCABULARY:
        if standalone_word_present(outside, word):
            raise HarnessError("outside text collides with a banned word")
    _agents(ws).write_text(outside + "\n", encoding="utf-8")
    _store(ws, "full")
    _ask(ws, "init", cwd=str(ws.path))
    agents = _agents(ws).read_text(encoding="utf-8")
    rule = _rule(ws).read_text(encoding="utf-8")
    assert outside in agents
    require_exported_contract_omits_machine_identity(agents)
    body = cursor_rule_body(rule)
    assert states_prose_only_scope(body), body[:500]
    require_banned_list(body)
    require_not_source_code_scope(body)
    require_not_source_code_scope(rule)
    require_prose_glob_front_matter(rule)
    assert shows_integer(agents, 40)
    require_full_scoring(agents)
    require_not_source_code_scope(agents)
    assert not shows_integer(rule, 40)
    assert not has_light_tells(rule)
    # The shipped rule does not tell the agent to run the detector after
    # a write. A denial of that step, and the two halves in different
    # statements, do not carry it. One statement that does tell the agent
    # to run the detector after a write does carry it. That statement is
    # not this checkout's command.
    assert not states_post_write_detector(rule)
    for extra in (
        "Do not run the detector after writing.",
        "Not to run the detector after writing.",
        "After writing a prose file, do not run the detector.",
        "After writing, the detector is not required.",
        "Never detect the file after you write it.",
        "After writing a prose file, vary the sentence length.\n"
        "The detector is a separate program.",
    ):
        assert not states_post_write_detector(rule + "\n" + extra + "\n"), extra
    for extra in (
        "After writing a prose file, run the detector on that file.",
        "Run detection after you write the file.",
        "After you write, detect the prose file.",
        "After writing, run the detector, not a second tool.",
        "After writing, run the detector and do not announce a score.",
    ):
        assert states_post_write_detector(rule + "\n" + extra + "\n"), extra
    assert not has_cleanup_switch_finish(agents)
    _clear_export(ws)
    _ask(ws, "init", NAMED, cwd=str(ws.path))
    named_agents = _agents(ws).read_text(encoding="utf-8")
    require_exported_contract_omits_machine_identity(named_agents)
    require_not_source_code_scope(named_agents)


def _export_at(ws, level, env=None):
    _store(ws, level)
    _clear_export(ws)
    _ask(ws, "init", cwd=str(ws.path), env_updates=env)
    return _agents(ws).read_text(encoding="utf-8")


def test_init_lite_omits_detector_resolution(isolated_ws):
    ws = isolated_ws
    lite = _export_at(ws, "lite")
    full_unset = _export_at(ws, "full", {ENV_PLUGIN_ROOT: None})
    strict_unset = _export_at(ws, "strict", {ENV_PLUGIN_ROOT: None})
    full_set = _export_at(ws, "full")
    strict_set = _export_at(ws, "strict")
    for text in (lite, full_unset, strict_unset, full_set, strict_set):
        require_exported_contract_omits_machine_identity(text)
    assert not standalone_word_present(lite, "skills")
    assert not standalone_word_present(lite, "plugins")
    assert not standalone_word_present(lite, ENV_PLUGIN_ROOT)
    assert not shows_integer(lite, 40)
    assert not has_light_tells(lite)
    assert not has_cleanup_switch_finish(lite)
    require_lite_omits_scoring(lite, full_unset)
    require_lite_omits_scoring(lite, full_set)

    def extra(full_text):
        shared = [
            word
            for word in set(re.findall(r"[A-Za-z0-9]+", lite))
            if word.lower() in full_text.lower()
        ]
        return strip_tokens(full_text, shared)

    def names_plugin_root(text):
        left = extra(text)
        assert left
        assert standalone_word_present(left, ENV_PLUGIN_ROOT)
        # The skills/plugins sentence is not this arm. Stripping it must
        # still leave the host plugin-root variable.
        named = strip_tokens(left, ["skills", "plugins"])
        assert standalone_word_present(named, ENV_PLUGIN_ROOT)
        return named

    def names_installed_location(text):
        left = extra(text)
        assert left
        assert standalone_word_present(left, "skills")
        assert standalone_word_present(left, "plugins")
        # Naming the variable is not this arm. Stripping it must still
        # leave the installed skills and plugins location.
        located = strip_tokens(left, [ENV_PLUGIN_ROOT])
        assert standalone_word_present(located, "skills")
        assert standalone_word_present(located, "plugins")
        return located

    set_paragraphs = (
        names_plugin_root(full_set),
        names_plugin_root(strict_set),
    )
    unset_paragraphs = (
        names_installed_location(full_unset),
        names_installed_location(strict_unset),
    )
    for set_paragraph, unset_paragraph in zip(set_paragraphs, unset_paragraphs):
        assert set_paragraph != unset_paragraph
    assert has_cleanup_switch_finish(strict_unset)
    assert not has_cleanup_switch_finish(full_unset)
    assert has_cleanup_switch_finish(strict_set)
    assert not has_cleanup_switch_finish(full_set)
    require_full_scoring(full_unset)
    require_full_scoring(full_set)
    require_strict_cleanup(strict_unset, full_unset)
    require_strict_cleanup(strict_set, full_set)
    require_strict_clean_band_apart(strict_unset, lite)
    require_strict_clean_band_apart(strict_set, lite)


def test_init_second_time_does_not_duplicate_or_overwrite(isolated_ws):
    ws = isolated_ws
    outside = "Parish mill wheel stays in the margin."
    outside_text = outside + "\n"
    _agents(ws).write_text(outside_text, encoding="utf-8")
    _store(ws, "full")
    _ask(ws, "init", cwd=str(ws.path))
    rule_bytes = _rule(ws).read_bytes()
    first_body = _agents(ws).read_text(encoding="utf-8")
    delve_after_first = standalone_count(first_body, "delve")
    assert delve_after_first >= 1
    require_outside_text_in_place(first_body, outside_text)

    def section_left_once():
        body = _agents(ws).read_text(encoding="utf-8")
        assert outside in body
        require_outside_text_in_place(body, outside_text)
        assert standalone_count(body, "delve") == delve_after_first
        require_contract_section(body, word="delve", count=delve_after_first)
        return body

    for _ in range(2):
        reply = _ask(ws, "init", cwd=str(ws.path))
        section_left_once()
        assert _rule(ws).read_bytes() == rule_bytes
        assert states_section_already_present(reply)
        assert states_rule_already_there(reply)

    def prepare_split(drop):
        _clear_export(ws)
        _agents(ws).write_text(outside_text, encoding="utf-8")
        _ask(ws, "init", cwd=str(ws.path))
        drop()
        return _ask(ws, "init", cwd=str(ws.path))

    def drop_rule():
        target = _rule(ws)
        target.unlink()
        assert not target.exists()

    def drop_agents():
        target = _agents(ws)
        target.unlink()
        assert not target.exists()

    for _ in range(2):
        reply = prepare_split(drop_rule)
        marker_body = section_left_once()
        assert outside in marker_body
        require_contract_section(marker_body, word="delve", count=delve_after_first)
        require_same_rule_bytes(_rule(ws), rule_bytes)
        require_prose_glob_front_matter(_rule(ws).read_text(encoding="utf-8"))
        assert states_section_already_present(reply)
    for _ in range(2):
        reply = prepare_split(drop_agents)
        rewritten = _agents(ws).read_text(encoding="utf-8")
        require_contract_section(
            rewritten,
            word="delve",
            count=delve_after_first,
        )
        require_same_rule_bytes(_rule(ws), rule_bytes)
        assert states_rule_already_there(reply)
    _clear_export(ws)
    _agents(ws).write_text(outside_text, encoding="utf-8")
    _ask(ws, "init", cwd=str(ws.path))
    kept = _rule(ws).read_bytes()
    _agents(ws).unlink()
    assert not _agents(ws).exists()
    again = _ask(ws, "init", cwd=str(ws.path))
    assert states_rule_already_there(again)
    assert _rule(ws).read_bytes() == kept
    require_contract_section(
        _agents(ws).read_text(encoding="utf-8"),
        word="delve",
        count=delve_after_first,
    )


def test_init_off_writes_nothing_and_echoes_the_typed_form(isolated_ws):
    ws = isolated_ws
    _store(ws, "off")
    plain = _ask(ws, "init", cwd=str(ws.path))
    assert not _agents(ws).exists()
    assert not _rule(ws).exists()
    assert plain.strip()
    assert standalone_word_present(plain, "off")
    assert states_switched_off(plain)
    assert states_on_enables_export(plain)
    assert states_typed_on_enables_export(plain, PLAIN)
    assert standalone_word_present(strip_tokens(plain, [PLAIN]), "off")
    _store(ws, "full")
    _clear_export(ws)
    _ask(ws, "init", cwd=str(ws.path))
    agents_bytes = _agents(ws).read_bytes()
    rule_bytes = _rule(ws).read_bytes()
    _store(ws, "off")
    named = _ask(ws, "init", NAMED, cwd=str(ws.path))
    assert _agents(ws).read_bytes() == agents_bytes
    assert _rule(ws).read_bytes() == rule_bytes
    assert NAMED in named
    assert states_switched_off(named)
    assert states_on_enables_export(named)
    assert states_typed_on_enables_export(named, NAMED)
    assert standalone_word_present(strip_tokens(named, [NAMED, PLAIN]), "off")


# Opens that mean this path is not a file the process can use. Anything
# else (a full disk, a killed probe) is not "blocked".
_BLOCKED_OPEN = frozenset(
    {
        errno.EACCES,
        errno.EPERM,
        errno.ENOENT,
        errno.ENOTDIR,
        errno.EISDIR,
        errno.EROFS,
    }
)


def _owner_can_open(path: Path, kind: str) -> bool:
    """Whether this process can read or write *path*.

    A write that creates a missing path is removed. Opening an existing
    file for write does not change its bytes. A permission or path error
    is the blocked result. Any other failure is not treated as blocked.
    """
    try:
        if kind == "read":
            path.read_bytes()
            return True
        if path.exists():
            fd = os.open(path, os.O_WRONLY)
            os.close(fd)
            return True
        path.write_text("x", encoding="utf-8")
    except OSError as exc:
        if exc.errno in _BLOCKED_OPEN:
            return False
        raise HarnessError(
            f"init target probe failed for {path}: {exc}"
        ) from exc
    path.unlink()
    return True


def _child_can_open(path: Path, kind: str) -> bool:
    """A fresh child can read or write *path*.

    The child is the same kind of exec the hook will be. A child that
    still opens the path means the hook can too. A write that creates a
    missing path is removed. A killed child is not a permission result.
    """
    existed = path.exists()
    script = (
        "import errno, os, pathlib, sys\n"
        "path = pathlib.Path(sys.argv[1])\n"
        "kind = sys.argv[2]\n"
        "blocked = {errno.EACCES, errno.EPERM, errno.ENOENT, errno.ENOTDIR, errno.EISDIR, errno.EROFS}\n"
        "try:\n"
        "    if kind == 'read':\n"
        "        path.read_bytes()\n"
        "    elif path.exists():\n"
        "        fd = os.open(path, os.O_WRONLY)\n"
        "        os.close(fd)\n"
        "    else:\n"
        "        path.write_text('x', encoding='utf-8')\n"
        "except OSError as exc:\n"
        "    if exc.errno in blocked:\n"
        "        sys.exit(1)\n"
        "    sys.stderr.write(repr(exc))\n"
        "    sys.exit(2)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script, str(path), kind],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
        check=False,
    )
    created = (not existed) and path.exists()
    if created:
        path.unlink()
    if completed.returncode < 0:
        raise HarnessError(
            "init target probe was killed: "
            f"signal={-completed.returncode} stderr={completed.stderr[:200]!r}"
        )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise HarnessError(
        "init target probe failed: "
        f"code={completed.returncode} stderr={completed.stderr[:200]!r}"
    )


@contextmanager
def _init_target_blocked(path: Path, *, read: bool = False, write: bool = False):
    """*path* is one a hook child cannot read or cannot write.

    A mode bit this process can still use is not that target. When the
    owner can still open the file, hook children are started without the
    override that ignores mode bits, and the child probe is what decides.
    The hook has to run inside this window.
    """
    if not read and not write:
        raise HarnessError(f"init target {path} names no blocked open")
    limited = False
    try:
        owner_slips = (read and _owner_can_open(path, "read")) or (
            write and _owner_can_open(path, "write")
        )
        if owner_slips:
            _hold_root_mode_bits()
            limited = True
        if read and _child_can_open(path, "read"):
            raise HarnessError(f"{path} stayed readable for a hook child")
        if write and _child_can_open(path, "write"):
            raise HarnessError(f"{path} stayed writable for a hook child")
        yield
    finally:
        if limited:
            _release_root_mode_bits()


def test_init_reports_when_it_cannot_write(isolated_ws):
    ws = isolated_ws
    _store(ws, "full")
    success = _ask(ws, "init", cwd=str(ws.path))
    assert _agents(ws).is_file() and _rule(ws).is_file()
    _clear_export(ws)
    agents = _agents(ws)
    agents.write_text("keep\n", encoding="utf-8")
    os.chmod(agents, 0)
    try:
        with _init_target_blocked(agents, read=True, write=True):
            reply = _ask(ws, "init", cwd=str(ws.path))
    finally:
        os.chmod(agents, 0o644)
    assert success not in reply
    assert states_cannot_read_or_write(reply)
    assert "delve" not in agents.read_text(encoding="utf-8")
    _clear_export(ws)
    agents.write_text("keep\n", encoding="utf-8")
    os.chmod(agents, 0o444)
    try:
        with _init_target_blocked(agents, write=True):
            reply = _ask(ws, "init", cwd=str(ws.path))
    finally:
        os.chmod(agents, 0o644)
    assert success not in reply
    assert states_cannot_write(reply)
    assert agents.read_text(encoding="utf-8") == "keep\n"
    _clear_export(ws)
    cursor = Path(ws.path) / ".cursor"
    cursor.write_text("not a directory\n", encoding="utf-8")
    rule = _rule(ws)
    with _init_target_blocked(rule, write=True):
        reply = _ask(ws, "init", cwd=str(ws.path))
    assert success not in reply
    assert states_cannot_write(reply)
    assert not rule.exists()


def test_stats_prefers_the_named_transcript_else_the_newest(isolated_ws):
    ws = isolated_ws
    _store(ws, "strict")
    named = _write_jsonl(
        Path(ws.path),
        "named.jsonl",
        [_assistant(OUTSIDE, 410, 820)],
    )
    projects = Path(ws.config_dir) / "projects" / runtime_token("p")
    older = _write_jsonl(projects, "old.jsonl", [_assistant(OUTSIDE, 510, 910)])
    # znew sorts after old, so the first name in the folder is the older file.
    newer = _write_jsonl(projects, "znew.jsonl", [_assistant(OUTSIDE, 610, 710)])
    age_file(older, days=1)
    listed = sorted(path.name for path in projects.glob("*.jsonl"))
    assert listed and listed[0] == older.name
    assert newer.name in listed and newer.name != listed[0]
    assert newer.stat().st_mtime > older.stat().st_mtime
    reply = _ask(ws, "stats", transcript_path=str(named))
    named_again = _ask(ws, "stats", NAMED, transcript_path=str(named))
    for text in (reply, named_again):
        assert shows_integer(text, 410) and shows_integer(text, 820)
        assert not shows_integer(text, 610)
        assert not shows_integer(text, 510)
        assert standalone_word_present(text, "strict")
        assert shows_integer(text, 1)
    _store(ws, "lite")
    unnamed = _ask(ws, "stats")
    assert shows_integer(unnamed, 610) and shows_integer(unnamed, 710)
    assert not shows_integer(unnamed, 510)
    assert not shows_integer(unnamed, 410)
    assert standalone_word_present(unnamed, "lite")


def test_stats_counts_assistant_turns_and_keeps_the_two_token_fields_distinct(isolated_ws):
    ws = isolated_ws
    _store(ws, "strict")
    # Several assistant entries, and one non-assistant entry.
    # Cache parts still sum to 1660. Output parts sum to a total that is
    # not the second assistant entry's cache-read field.
    quantities = (
        {
            "name": "output",
            "several": (251, 263),
            "excluded": 990,
            "shared_once": 450,
            "unidentified": 120,
        },
        {
            "name": "cache_read",
            "several": (820, 840),
            "excluded": 980,
            "shared_once": 860,
            "unidentified": 140,
        },
    )
    if len(quantities) != 2:
        raise HarnessError("stats has two token quantities")
    output_row, cache_row = quantities
    mixed_entries = [
        _assistant(
            "The clerk lists the mill fees.",
            output_row["several"][0],
            cache_row["several"][0],
        ),
        _assistant(
            "The clerk lists the bridge fees.",
            output_row["several"][1],
            cache_row["several"][1],
        ),
        {
            "type": "user",
            "message": {
                "usage": {
                    "output_tokens": output_row["excluded"],
                    "cache_read_input_tokens": cache_row["excluded"],
                },
                "content": [{"type": "text", "text": "ignore this usage"}],
            },
        },
    ]
    # Shared message id, plus one assistant entry with no identifier.
    # One copy is the shared entry once plus the unidentified entry, so the
    # total is not either entry's own integer. Counting the shared id again
    # is the doubled total.
    shared_entries = [
        _assistant(
            "The clerk lists the mill fees.",
            output_row["shared_once"],
            cache_row["shared_once"],
            mid="same",
        ),
        _assistant(
            "The clerk lists the bridge fees.",
            output_row["shared_once"],
            cache_row["shared_once"],
            mid="same",
        ),
        _assistant(
            "The clerk lists the gate fees.",
            output_row["unidentified"],
            cache_row["unidentified"],
        ),
    ]
    mixed = _write_jsonl(Path(ws.path), "mixed.jsonl", mixed_entries)
    shared_tokens = _write_jsonl(
        Path(ws.path), "shared-tokens.jsonl", shared_entries
    )
    reply = _ask(ws, "stats", transcript_path=str(mixed))
    shared_token_reply = _ask(ws, "stats", transcript_path=str(shared_tokens))
    assistant_turns = 2
    shared_turns = 2
    duplicated_turns = 3
    assert shows_integer(reply, assistant_turns)
    assert shows_integer(shared_token_reply, shared_turns)
    assert not shows_integer(shared_token_reply, duplicated_turns), shared_token_reply
    mixed_raw = usage_field_integers(mixed_entries)
    shared_raw = usage_field_integers(shared_entries)
    witnessed = []
    for row in quantities:
        correct = sum(row["several"])
        absorbed = correct + row["excluded"]
        one_copy = row["shared_once"] + row["unidentified"]
        doubled = (row["shared_once"] * 2) + row["unidentified"]
        witnessed.append(
            {
                "name": row["name"],
                "excluded": row["excluded"],
                "correct": correct,
                "absorbed": absorbed,
                "one_copy": one_copy,
                "doubled": doubled,
            }
        )
    for index, item in enumerate(witnessed):
        other = witnessed[1 - index]
        other_totals = (
            other["correct"],
            other["absorbed"],
            other["one_copy"],
            other["doubled"],
        )
        raw_fields = mixed_raw + shared_raw
        turns = (assistant_turns, shared_turns, duplicated_turns)
        correct = require_distinct_token_total(
            item["correct"],
            raw_fields,
            assistant_turns,
            *other_totals,
            item["absorbed"],
            item["one_copy"],
            item["doubled"],
            *turns,
        )
        absorbed = require_distinct_token_total(
            item["absorbed"],
            raw_fields,
            assistant_turns,
            *other_totals,
            item["correct"],
            item["one_copy"],
            item["doubled"],
            *turns,
        )
        one_copy = require_distinct_token_total(
            item["one_copy"],
            raw_fields,
            shared_turns,
            *other_totals,
            item["correct"],
            item["absorbed"],
            item["doubled"],
            *turns,
        )
        doubled = require_distinct_token_total(
            item["doubled"],
            raw_fields,
            shared_turns,
            *other_totals,
            item["correct"],
            item["absorbed"],
            item["one_copy"],
            *turns,
        )
        # Several assistant entries: the total is present, and a raw field
        # that prints the same integer does not satisfy it.
        assert shows_integer(reply, correct), (item["name"], reply)
        without_raw = without_printed_integers(reply, mixed_raw)
        assert shows_integer(without_raw, correct), (item["name"], without_raw)
        # Non-assistant usage stays outside the total. The absorbed total
        # is the assistant total plus that quantity. Removing the assistant
        # total, not a raw field, is what accounts for it.
        assert not shows_integer(reply, absorbed), (item["name"], reply)
        assert not shows_integer(reply, item["excluded"]), (item["name"], reply)
        accounted = without_printed_integers(
            reply, [item["correct"], other["correct"]]
        )
        assert not shows_integer(accounted, item["excluded"]), (
            item["name"],
            accounted,
        )
        # Shared identifier: one copy of this quantity. The doubled copy
        # fails while each entry's own integer is left in the reply.
        assert shows_integer(shared_token_reply, one_copy), (
            item["name"],
            shared_token_reply,
        )
        assert not shows_integer(shared_token_reply, doubled), (
            item["name"],
            shared_token_reply,
        )
    left = (OUTSIDE + " ") * 2
    right = "It is crucial to delve into the tapestry. " * 4
    combined = _agreed_score(left, right)
    shared = _write_jsonl(
        Path(ws.path),
        "shared.jsonl",
        [
            _assistant(left, 450, 860, mid="same"),
            _assistant(right, 450, 860, mid="same"),
        ],
    )
    shared_reply = _ask(ws, "stats", transcript_path=str(shared))
    assert shows_integer(shared_reply, 1)
    assert shows_integer(shared_reply, combined)
    first = _write_jsonl(
        Path(ws.path),
        "swap-a.jsonl",
        [_assistant(OUTSIDE, 410, 820)],
    )
    second = _write_jsonl(
        Path(ws.path),
        "swap-b.jsonl",
        [_assistant(OUTSIDE, 820, 410)],
    )
    left_reply = _ask(ws, "stats", transcript_path=str(first))
    right_reply = _ask(ws, "stats", transcript_path=str(second))
    for text in (left_reply, right_reply):
        assert shows_integer(text, 410)
        assert shows_integer(text, 820)
    # Each reply is read from a different file. The file name is not the
    # exchange of the two totals.
    left_kept, right_kept = replies_without_named_transcripts(
        left_reply,
        right_reply,
        [str(first), str(second)],
    )
    assert left_kept != right_kept, (left_kept, right_kept)
    for text in (left_kept, right_kept):
        assert shows_integer(text, 410)
        assert shows_integer(text, 820)


def test_stats_scores_only_the_trimmed_unfenced_tail(isolated_ws):
    ws = isolated_ws
    level = "strict"
    _store(ws, level)
    # One assistant entry. The turn count stays inside 0 through 100.
    # Both token totals sit above 100, so neither is a score, and each is
    # large enough that a grouped spelling is one integer.
    turns = 1
    output_total = 1720
    cache_total = 3450
    totals = (output_total, cache_total)
    if not 0 <= turns <= 100:
        raise HarnessError("turn count has to stay inside 0 through 100")
    if output_total <= 100 or cache_total <= 100 or output_total == cache_total:
        raise HarnessError("token totals have to sit above 100 and differ")
    if output_total == turns or cache_total == turns:
        raise HarnessError("a token total must not be the turn count")
    outside = (OUTSIDE + " ") * 2
    assert len(outside) > 200
    inside = prose_dense().text
    fenced = outside + "\n```\n" + inside + "\n```\n"
    expected = measure_text(_prose_slice(fenced)).score
    included = measure_text(outside + "\n" + inside).score
    assert expected != included
    for variant in (outside, outside + " ", outside + "\n"):
        if measure_text(variant).score != measure_text(outside).score:
            raise HarnessError("a trailing space changes the outside score")
    fenced_path = _write_jsonl(
        Path(ws.path),
        "fenced.jsonl",
        [_assistant(fenced, output_total, cache_total)],
    )
    fenced_reply = _ask(ws, "stats", transcript_path=str(fenced_path))
    # One turn occurrence is accounted for. A score equal to that integer
    # still has to remain. Other 0-100 integers may remain.
    fenced_left = account_stats_score_reply(
        fenced_reply, str(fenced_path), totals, level, turns
    )
    assert expected in whole_integers(fenced_left), (
        expected,
        whole_integers(fenced_left),
        fenced_left,
    )
    body = window_body(200)
    padded = "\n\n" + body + "\n\n"
    assert len(padded) > 200 and len(padded.strip()) == 200
    short = _write_jsonl(
        Path(ws.path),
        "short.jsonl",
        [_assistant(padded, output_total, cache_total)],
    )
    short_reply = _ask(ws, "stats", transcript_path=str(short))
    # Path and token totals come out first, as whole integers. The turn
    # count is still in the reply: it accounts for exactly one 0-100
    # integer, and any other 0-100 integer is a session-prose score.
    short_left = stats_reply_without_path_and_totals(
        short_reply, str(short), totals
    )
    assert standalone_word_present(short_left, level), short_left
    short_scores = [n for n in whole_integers(short_left) if 0 <= n <= 100]
    assert short_scores.count(turns) == 1, (turns, short_scores, short_left)
    assert not [n for n in short_scores if n != turns], (
        short_scores,
        short_left,
    )
    longer_body = body + "x"
    assert len(longer_body.strip()) == 201
    long = _write_jsonl(
        Path(ws.path),
        "long.jsonl",
        [_assistant(longer_body, output_total, cache_total)],
    )
    long_reply = _ask(ws, "stats", transcript_path=str(long))
    long_score = measure_text(_prose_slice(longer_body)).score
    long_left = account_stats_score_reply(
        long_reply, str(long), totals, level, turns
    )
    assert long_score in whole_integers(long_left), (
        long_score,
        whole_integers(long_left),
        long_left,
    )
    suffix = ("The mill wheel turns after the rain. " * 2000)[:40000]
    assert len(suffix) == 40000
    prefix = prose_dense().text
    assert measure_text(suffix).score != measure_text(prefix + suffix).score
    tail = _write_jsonl(
        Path(ws.path),
        "tail.jsonl",
        [_assistant(prefix + suffix, output_total, cache_total)],
    )
    tail_reply = _ask(ws, "stats", transcript_path=str(tail))
    tail_score = measure_text(suffix).score
    tail_left = account_stats_score_reply(
        tail_reply, str(tail), totals, level, turns
    )
    assert tail_score in whole_integers(tail_left), (
        tail_score,
        whole_integers(tail_left),
        tail_left,
    )


def test_stats_non_assistant_text_does_not_move_the_session_prose_score(isolated_ws):
    ws = isolated_ws
    level = "strict"
    _store(ws, level)
    # One assistant turn. Both token totals sit above 100, so neither is a
    # score, and each is distinct from the turn count and from the usage on
    # the non-assistant row.
    turns = 1
    output_total = 1720
    cache_total = 3450
    excluded_output = 990
    excluded_cache = 980
    totals = (output_total, cache_total)
    if not 0 <= turns <= 100:
        raise HarnessError("turn count has to stay inside 0 through 100")
    blocked = {
        turns,
        output_total,
        cache_total,
        excluded_output,
        excluded_cache,
        output_total + excluded_output,
        cache_total + excluded_cache,
    }
    if len(blocked) != 7:
        raise HarnessError("stats witnesses have to be seven different integers")
    if output_total <= 100 or cache_total <= 100:
        raise HarnessError("token totals have to sit above 100")
    if excluded_output <= 100 or excluded_cache <= 100:
        raise HarnessError("excluded usage has to sit above 100")
    kind = "note" + "".join(ch for ch in fresh_word() if ch.isalpha())
    short = window_body(180)
    carried = prose_dense().text.strip()
    base = (OUTSIDE + " ") * 2
    if "```" in short or "```" in carried or "```" in base:
        raise HarnessError("stats prose fixtures must not contain a code fence")
    if not 100 < len(_prose_slice(short)) <= 200:
        raise HarnessError("short assistant text has to sit below the 200-character threshold")
    if len(_prose_slice(carried)) <= 200 or len(_prose_slice(base)) <= 200:
        raise HarnessError("the long texts have to clear 200 characters")
    if len(_prose_slice(short + "\n\n" + carried)) <= 200:
        raise HarnessError("adding the long text has to clear 200 characters")
    # Including the carried text moves the slice's score for every join the
    # page leaves open. The product reply is not required to show that number.
    base_score = measure_text(_prose_slice(base)).score
    joined_scores = {
        measure_text(_prose_slice(sep.join((base, carried)))).score
        for sep in ("\n\n", "\n", " ")
    }
    if base_score in joined_scores or turns in joined_scores or base_score == turns:
        raise HarnessError(
            "adding the carried text has to move the score off the assistant "
            f"slice and off the turn count; base={base_score} joined={joined_scores}"
        )

    def no_score(reply, path):
        assert shows_integer(reply, output_total), reply
        assert shows_integer(reply, cache_total), reply
        left = stats_reply_without_path_and_totals(reply, str(path), totals)
        assert standalone_word_present(left, level), left
        scores = [n for n in whole_integers(left) if 0 <= n <= 100]
        assert scores.count(turns) == 1, (turns, scores, left)
        assert not [n for n in scores if n != turns], (scores, left)
        assert session_prose_integers(reply, str(path), totals, level, turns) == []

    # The two transcripts differ only in the non-assistant row's text.
    # An empty row is the arm without that text.
    below = _write_jsonl(
        Path(ws.path),
        "below.jsonl",
        [
            _assistant(short, output_total, cache_total),
            _other_row(kind, "", excluded_output, excluded_cache),
        ],
    )
    with_carried = _write_jsonl(
        Path(ws.path),
        "carried.jsonl",
        [
            _assistant(short, output_total, cache_total),
            _other_row(kind, carried, excluded_output, excluded_cache),
        ],
    )
    below_reply = _ask(ws, "stats", transcript_path=str(below))
    carried_reply = _ask(ws, "stats", transcript_path=str(with_carried))
    no_score(below_reply, below)
    no_score(carried_reply, with_carried)
    for reply, path in ((below_reply, below), (carried_reply, with_carried)):
        left = without_named_transcript(reply, str(path))
        assert not shows_integer(left, excluded_output), left
        assert not shows_integer(left, excluded_cache), left
        assert not shows_integer(left, output_total + excluded_output), left
        assert not shows_integer(left, cache_total + excluded_cache), left
    # The same long text, written as the assistant row, does produce a score.
    # That score is present. Its value is not required.
    as_assistant = _write_jsonl(
        Path(ws.path),
        "as-assistant.jsonl",
        [_assistant(carried, output_total, cache_total)],
    )
    assistant_reply = _ask(ws, "stats", transcript_path=str(as_assistant))
    assert shows_integer(assistant_reply, output_total), assistant_reply
    assert shows_integer(assistant_reply, cache_total), assistant_reply
    assistant_scores = session_prose_integers(
        assistant_reply, str(as_assistant), totals, level, turns
    )
    assert assistant_scores, assistant_reply
    # Already over the threshold: the two transcripts differ only in the
    # non-assistant row's text. An empty row is the arm without that text.
    scoring = _write_jsonl(
        Path(ws.path),
        "scoring.jsonl",
        [
            _assistant(base, output_total, cache_total),
            _other_row(kind, "", excluded_output, excluded_cache),
        ],
    )
    scoring_with = _write_jsonl(
        Path(ws.path),
        "scoring-with.jsonl",
        [
            _assistant(base, output_total, cache_total),
            _other_row(kind, carried, excluded_output, excluded_cache),
        ],
    )
    scoring_reply = _ask(ws, "stats", transcript_path=str(scoring))
    scoring_with_reply = _ask(ws, "stats", transcript_path=str(scoring_with))
    scoring_scores = session_prose_integers(
        scoring_reply, str(scoring), totals, level, turns
    )
    scoring_with_scores = session_prose_integers(
        scoring_with_reply, str(scoring_with), totals, level, turns
    )
    assert scoring_scores, scoring_reply
    assert scoring_scores == scoring_with_scores, (
        scoring_scores,
        scoring_with_scores,
        scoring_reply,
        scoring_with_reply,
    )
    with_left = without_named_transcript(scoring_with_reply, str(scoring_with))
    assert shows_integer(with_left, turns), with_left
    assert shows_integer(with_left, output_total), with_left
    assert shows_integer(with_left, cache_total), with_left
    assert not shows_integer(with_left, excluded_output), with_left
    assert not shows_integer(with_left, excluded_cache), with_left


def test_stats_missing_transcript_has_no_counts(isolated_ws):
    ws = isolated_ws
    level = "strict"
    _store(ws, level)
    # Two assistant entries, short enough that no session-prose score is
    # printed. The turn count and the two token totals are distinct from
    # each other and from 1, so an incidental 1 is none of them.
    turns = 2
    output_total = 1720
    cache_total = 3450
    if len({turns, output_total, cache_total, 0, 1}) != 5:
        raise HarnessError(
            "the turn count, the two token totals, zero, and an incidental "
            "1 have to be five different integers"
        )
    readable = _write_jsonl(
        Path(ws.path),
        "readable.jsonl",
        [
            _assistant(
                "The clerk lists the mill fees.",
                output_total // 2,
                cache_total // 2,
            ),
            _assistant(
                "The clerk lists the bridge fees.",
                output_total // 2,
                cache_total // 2,
            ),
        ],
    )
    readable_reply = _ask(ws, "stats", transcript_path=str(readable))
    readable_left = without_named_transcript(readable_reply, str(readable))
    readable_named = stats_quantities_named(
        readable_left, (turns, output_total, cache_total)
    )
    assert set(readable_named) == {turns, output_total, cache_total}, (
        readable_named,
        readable_left,
    )
    # A readable transcript with no assistant entry still names the three
    # quantities, and each of them is 0. That 0 is those quantities.
    empty = _write_jsonl(
        Path(ws.path),
        "empty.jsonl",
        [
            {
                "type": "user",
                "message": {
                    "content": [{"type": "text", "text": "The clerk asks the fee."}],
                },
            }
        ],
    )
    empty_reply = _ask(ws, "stats", transcript_path=str(empty))
    empty_left = without_named_transcript(empty_reply, str(empty))
    assert stats_quantities_named(empty_left, (0,)) == (0,), empty_left
    assert not stats_quantities_named(
        empty_left, (turns, output_total, cache_total)
    ), empty_left
    name = fresh_word()
    if not re.search(r"\d", name):
        name += "7"
    missing = Path(ws.path) / (name + ".jsonl")
    reply = _ask(ws, "stats", transcript_path=str(missing))
    assert reply.strip()
    # Path digits are not a turn count or a token total. The stored level
    # is not required. After the path is removed, naming the turn count
    # or either token total fails. Naming none of those three passes,
    # including when some other integer remains, and whether or not the
    # reply names the level.
    left = without_named_transcript(reply, str(missing))
    quantities = (turns, output_total, cache_total, 0)
    assert not stats_quantities_named(left, quantities), (left, quantities)
    incidental = without_named_transcript(
        f"looked in 1 place {missing}", str(missing)
    )
    assert whole_integers(incidental) == [1], incidental
    assert not stats_quantities_named(incidental, quantities), incidental
    named_level = without_named_transcript(
        f"{level} looked in 1 place {missing}", str(missing)
    )
    assert not stats_quantities_named(named_level, quantities), named_level
    for quantity in quantities:
        named = without_named_transcript(
            f"quantity {quantity} {missing}", str(missing)
        )
        assert quantity in stats_quantities_named(named, quantities), (
            quantity,
            named,
        )


def test_shipped_command_file_forwards_arguments(isolated_ws):
    ws = isolated_ws
    found = command_registrations()
    assert found
    for _path, body in found:
        # The candidate is this document's own body. The next token is
        # the argument slot, not one of the twelve subcommands written
        # into the template.
        rest = body[len(PLAIN) :].strip()
        assert rest
        slot = rest.split()[0]
        assert slot not in SUBCOMMANDS
        clear_stored_level(ws)
        assert_one_level_line(_status(ws), "full")
        invoke_shipped_command(ws, "strict", body=body)
        assert_one_level_line(_status(ws), "strict")
        word = fresh_word()
        reply = invoke_shipped_command(ws, word, body=body)
        assert word in reply
        assert reports_word_as_unknown(reply, word), reply
        assert word in strip_tokens(reply, SUBCOMMANDS)
        assert_one_level_line(_status(ws), "strict")


def test_commands_open_no_socket(isolated_ws):
    ws = isolated_ws
    path = _plant(ws, fresh_word() + ".md", zero_label_prose().text)
    transcript = _write_jsonl(
        Path(ws.path),
        "net.jsonl",
        [_assistant(OUTSIDE, 410, 820)],
    )
    with hook_connect_observer() as observer:
        env = observer.env_updates
        _ask(ws, f"check {path}", env_updates=env)
        _ask(ws, "doctor", env_updates=env)
        _ask(ws, "stats", env_updates=env, transcript_path=str(transcript))
        _clear_export(ws)
        _ask(ws, "init", cwd=str(ws.path), env_updates=env)
        assert observer.n_connects == 0
        observer.fire_positive_control("127.0.0.1", 9)
