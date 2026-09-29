# feature: F05
"""Acceptance tests for the saved-file guard (FP-05)."""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
from pathlib import Path

from _harness import HarnessError, workspace
from F01_helpers import BAND_RANGES, SCAN_CAP
from F02_helpers import (
    readable_scores_0_100,
    NOTEBOOK_EXT,
    PLAIN_EXTS,
    ZIP_EXTS,
    pad_file_to_size,
    runtime_token,
    standalone_int_present,
    write_notebook,
)
from F05_helpers import (
    fire_pinned,
    pinned_score,
    ARCHIVE_KB_FIGURES,
    BETWEEN_CAPS,
    DECIMAL_512_KB,
    OVER_BOTH_4MB,
    OVER_BOTH_4MB_OTHER,
    OVER_BOTH_512,
    PLAIN_KB,
    assert_private_ledger_snapshot,
    basename_absent,
    basename_mentions,
    changed_config_files,
    config_omits,
    elapsed_call,
    fire_tool,
    fresh_name,
    grouped_int_present,
    guard_connect_observer,
    interpreter_standin,
    measure_path,
    measure_text,
    missing_score_arms,
    names_window,
    nudge_text,
    own_nudge_section,
    phrase_for_band,
    plant_prose,
    prose_above_20_not_40,
    prose_dense,
    prose_exact,
    prose_for_band,
    prose_none,
    prose_under,
    relocated_plugin_root,
    remainder,
    repeat_to,
    require_flagged_envelope,
    require_silent,
    row_around,
    show_text,
    similar_clean,
    states_scored_prefix,
    snapshot_config,
    status_remainder,
    updates_without_interpreters,
)

_SKIP_NAMES = (
    "claude.md",
    "claude.local.md",
    "agents.md",
    "agents.local.md",
    "skill.md",
    "memory.md",
)
_TWENTY = list(PLAIN_EXTS) + list(ZIP_EXTS) + [NOTEBOOK_EXT]


def _sid() -> str:
    return runtime_token("s")


def _without_names(text: str, *names: str) -> str:
    """Drop runtime names before looking for integers.

    A generated file name is hex and can itself contain 512, 4096, or a
    score. Those digits are not what the product reported.
    """
    body = text
    for name in sorted((n for n in names if n), key=len, reverse=True):
        body = body.replace(name, " ")
    return body


def _no_score(text: str, *names: str) -> None:
    """No 0–100 integer outside the file's own name."""
    body = _without_names(text, *names)
    for value in readable_scores_0_100(body):
        assert False, (
            f"show carried a 0-100 integer {value} outside the file name; "
            f"text={text[:300]!r}"
        )


def _kb_figure(text: str) -> tuple[int, ...]:
    # 4,096 is the same integer as 4096, and 4,000 is the same as 4000.
    # Contract: the 4 MB limit is named in kilobytes as 4000 or 4096.
    found = [n for n in ARCHIVE_KB_FIGURES if grouped_int_present(text, n)]
    assert found, (
        f"size skip did not name {ARCHIVE_KB_FIGURES[0]} or {ARCHIVE_KB_FIGURES[1]}; "
        f"text={text[:300]!r}"
    )
    assert not standalone_int_present(text, PLAIN_KB), (
        f"archive size skip named the plain-text cap {PLAIN_KB}; text={text[:300]!r}"
    )
    return tuple(found)


def test_unset_level_uses_full_threshold_not_strict():
    exact, exact_report = pinned_score(40)
    assert exact.confidence != "none"
    dense = prose_dense()
    with workspace() as unset:
        name = fresh_name(".md")
        path = plant_prose(unset, name, exact.text)
        _, nudge = fire_pinned(
            unset, exact_report, tool="Write", session_id=_sid(),
            file_path=str(path), content=exact.text,
        )
        assert nudge == "", "unset level flagged a score of exactly 40"
    with workspace() as strict:
        strict.write_mode_flag("strict")
        name = fresh_name(".md")
        path = plant_prose(strict, name, exact.text)
        _, nudge = fire_pinned(
            strict, exact_report, tool="Write", session_id=_sid(),
            file_path=str(path), content=exact.text,
        )
        require_flagged_envelope(nudge, base=name, measured=exact)
    with workspace() as still:
        # Nothing is stored. Writing full, and the exact-40 arm, do not
        # cover this knob. A flagged file here carries the same envelope.
        assert still.read_mode_flag() is None
        name = fresh_name(".md")
        path = plant_prose(still, name, dense.text)
        measured = measure_path(still, name)
        if (
            measured.score != dense.score
            or measured.score <= 40
            or measured.confidence == "none"
            or len(measured.labels) <= 5
        ):
            raise HarnessError(
                "unset-level fixture is not the dense file scored above 40 "
                f"with more than five labels; path={measured.score} "
                f"probe={dense.score} confidence={measured.confidence!r} "
                f"labels={len(measured.labels)}"
            )
        _, nudge = fire_tool(
            still, "Write", session_id=_sid(), file_path=str(path), content="payload"
        )
        require_flagged_envelope(nudge, base=name, measured=measured)
    # The dense file only has to clear 40, so a higher omitted threshold
    # still under that score keeps the arms above green. Mixed is the band
    # just above 40. The stored-full path already flags this file.
    mixed, mixed_report = pinned_score(41 + secrets.randbelow(20))
    with workspace() as omitted:
        assert omitted.read_mode_flag() is None
        name = fresh_name(".md")
        path = plant_prose(omitted, name, mixed.text)
        assert mixed.band == "mixed" and 40 < mixed.score <= 60
        _, nudge = fire_pinned(
            omitted, mixed_report, tool="Write", session_id=_sid(),
            file_path=str(path), content="payload",
        )
        require_flagged_envelope(nudge, base=name, measured=mixed)


def _level_arm(level: str, text: str, stall: float, *, score: bool) -> None:
    """One workspace, one level. The file and the stall match the other levels."""
    with workspace() as ws:
        ws.write_mode_flag(level)
        name = fresh_name(".md")
        path = plant_prose(ws, name, text)
        with interpreter_standin(ws, sleep_s=stall, forward=True) as stand:
            sid = _sid()
            started = stand.invocations()

            def run():
                return fire_tool(
                    ws,
                    "Write",
                    session_id=sid,
                    file_path=str(path),
                    content="payload",
                    env_updates=stand.env_updates,
                    timeout=stall + (20 if score else 0),
                )

            elapsed, (_, nudge) = elapsed_call(run)
            if score:
                if elapsed + 0.3 < stall:
                    raise HarnessError(
                        f"{level} returned in {elapsed:.2f}s before the {stall:.0f}s stall; "
                        "the stall is not on the detector startup path"
                    )
                assert stand.invocations() > started, f"{level} did not start the detector"
                assert standalone_int_present(show_text(ws, sid), prose_dense().score)
            else:
                assert elapsed < stall, f"{level} waited {elapsed:.2f}s for the detector"
                assert nudge == ""
                assert stand.invocations() == started, f"{level} invoked the detector"


def test_off_and_lite_emit_nothing_and_do_not_score():
    dense = prose_dense()
    stall = 3.0
    _level_arm("full", dense.text, stall, score=True)
    _level_arm("lite", dense.text, stall, score=False)
    _level_arm("off", dense.text, stall, score=False)


def test_score_equal_to_40_is_flagged_only_in_strict():
    exact, exact_report = pinned_score(40)
    assert exact.confidence != "none"
    assert exact.band == "light tells"
    with workspace() as full:
        full.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(full, name, exact.text)
        sid = _sid()
        _, nudge = fire_pinned(
            full, exact_report, tool="Write", session_id=sid,
            file_path=str(path), content=exact.text,
        )
        assert nudge == ""
        full_show = show_text(full, sid)
        assert name in full_show
        assert standalone_int_present(full_show, exact.score)
        full_rem = status_remainder(
            full_show,
            name,
            exact,
            session_id=sid,
            directory=str(full.path),
        )
    with workspace() as strict:
        strict.write_mode_flag("strict")
        path = plant_prose(strict, name, exact.text)
        sid = _sid()
        _, nudge = fire_pinned(
            strict, exact_report, tool="Write", session_id=sid,
            file_path=str(path), content=exact.text,
        )
        require_flagged_envelope(nudge, base=name, measured=exact)
        dense = prose_dense()
        dense_name = fresh_name(".md")
        dense_path = plant_prose(strict, dense_name, dense.text)
        dense_measured = measure_path(strict, dense_name)
        if dense_measured.score <= 40 or dense_measured.confidence == "none":
            raise HarnessError(
                f"strict reference scored {dense_measured.score} "
                f"at {dense_measured.confidence!r}"
            )
        dense_sid = _sid()
        _, dense_nudge = fire_tool(
            strict,
            "Write",
            session_id=dense_sid,
            file_path=str(dense_path),
            content=dense.text,
        )
        require_flagged_envelope(dense_nudge, base=dense_name, measured=dense_measured)
        strict_show = show_text(strict, sid)
        dense_show = show_text(strict, dense_sid)
        strict_rem = status_remainder(
            strict_show,
            name,
            exact,
            session_id=sid,
            directory=str(strict.path),
        )
        dense_rem = status_remainder(
            dense_show,
            dense_name,
            dense_measured,
            session_id=dense_sid,
            directory=str(strict.path),
        )
        assert strict_rem == dense_rem, f"strict-40={strict_rem!r} flagged={dense_rem!r}"
    under = prose_under()
    with workspace() as full:
        full.write_mode_flag("full")
        under_name = fresh_name(".md")
        under_path = plant_prose(full, under_name, under.text)
        under_sid = _sid()
        _, under_nudge = fire_tool(
            full,
            "Write",
            session_id=under_sid,
            file_path=str(under_path),
            content=under.text,
        )
        assert under_nudge == ""
        under_rem = status_remainder(
            show_text(full, under_sid),
            under_name,
            under,
            session_id=under_sid,
            directory=str(full.path),
        )
    print(f"[F05] exact-40 full={full_rem!r} strict={strict_rem!r}", flush=True)
    assert full_rem == under_rem, f"full-40={full_rem!r} under={under_rem!r}"
    assert full_rem != strict_rem


def test_score_equal_to_20_is_not_flagged_in_strict():
    exact, exact_report = pinned_score(20)
    assert exact.confidence != "none"
    for level in ("strict", "full"):
        with workspace() as ws:
            ws.write_mode_flag(level)
            name = fresh_name(".md")
            path = plant_prose(ws, name, exact.text)
            sid = _sid()
            _, nudge = fire_pinned(
                ws, exact_report, tool="Write", session_id=sid,
                file_path=str(path), content=exact.text,
            )
            assert nudge == "", f"{level} flagged a score of exactly 20"
            shown = show_text(ws, sid)
            assert name in shown
            assert standalone_int_present(shown, 20)


def test_score_above_20_and_not_above_40_is_flagged_only_in_strict():
    """Exactly 40 stays on its own test. This score sits strictly between."""
    mid, mid_report = pinned_score(21 + secrets.randbelow(19))
    assert 20 < mid.score < 40
    assert mid.confidence != "none"
    with workspace() as full:
        full.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(full, name, mid.text)
        sid = _sid()
        _, nudge = fire_pinned(
            full, mid_report, tool="Write", session_id=sid,
            file_path=str(path), content=mid.text,
        )
        assert nudge == "", f"full flagged a score of {mid.score}"
        shown = show_text(full, sid)
        assert name in shown
        assert standalone_int_present(shown, mid.score)
    with workspace() as strict:
        strict.write_mode_flag("strict")
        name = fresh_name(".md")
        path = plant_prose(strict, name, mid.text)
        _, nudge = fire_pinned(
            strict, mid_report, tool="Write", session_id=_sid(),
            file_path=str(path), content=mid.text,
        )
        require_flagged_envelope(nudge, base=name, measured=mid)


def test_flagged_write_names_file_phrase_score_band_and_fired_labels():
    dense = prose_dense()
    assert len(dense.labels) > 5
    with workspace() as ws:
        ws.write_mode_flag("full")
        for ext in (".md", ".docx"):
            name = fresh_name(ext)
            path = plant_prose(ws, name, dense.text)
            measured = measure_path(ws, name)
            if measured.score <= 40 or len(measured.labels) <= 5:
                raise HarnessError(
                    f"{ext} fixture is not above 40 with more than five labels"
                )
            _, nudge = fire_tool(
                ws, "Write", session_id=_sid(), file_path=str(path), content="payload"
            )
            require_flagged_envelope(nudge, base=name, measured=measured)


def test_unflagged_eligible_file_emits_nothing_and_is_not_rewritten():
    dense = prose_dense()
    clean = similar_clean(len(dense.text))
    assert clean.score <= 40
    ratio = len(clean.text) / max(len(dense.text), 1)
    assert 0.25 <= ratio <= 4, f"clean length is not the same order as the slop ({ratio})"
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(ws, name, clean.text)
        sid = _sid()
        result, nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(path), content=clean.text
        )
        assert result.returncode == 0
        assert nudge == ""
        shown = show_text(ws, sid)
        assert name in shown
        assert standalone_int_present(shown, clean.score)


def test_confidence_none_is_recorded_unflagged():
    none = prose_none()
    under = prose_under()
    exact, exact_report = pinned_score(40)
    assert none.score > 40 and none.confidence == "none"
    assert under.score <= 40 and under.confidence != "none"
    with workspace() as ws:
        ws.write_mode_flag("full")
        sid = _sid()
        none_name = fresh_name(".md")
        under_name = fresh_name(".md")
        none_path = plant_prose(ws, none_name, none.text)
        under_path = plant_prose(ws, under_name, under.text)
        _, none_nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(none_path), content=none.text
        )
        _, under_nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(under_path), content=under.text
        )
        assert none_nudge == ""
        assert under_nudge == ""
        shown = show_text(ws, sid)
        assert none_name in shown and standalone_int_present(shown, none.score)
        none_rem = status_remainder(
            shown,
            none_name,
            none,
            session_id=sid,
            directory=str(ws.path),
            others=[under_name],
        )
        under_rem = status_remainder(
            shown,
            under_name,
            under,
            session_id=sid,
            directory=str(ws.path),
            others=[none_name],
        )
        print(
            f"[F05] confidence-none row={none_rem!r} under-row={under_rem!r}",
            flush=True,
        )
        assert none_rem == under_rem, f"none={none_rem!r} under={under_rem!r}"
    with workspace() as strict:
        strict.write_mode_flag("strict")
        sid = _sid()
        none_name = fresh_name(".md")
        _, nudge = fire_tool(
            strict,
            "Write",
            session_id=sid,
            file_path=str(plant_prose(strict, none_name, none.text)),
            content=none.text,
        )
        assert nudge == ""
        strict_none_show = show_text(strict, sid)
        assert none_name in strict_none_show
        strict_none_rem = status_remainder(
            strict_none_show,
            none_name,
            none,
            session_id=sid,
            directory=str(strict.path),
        )
        name = fresh_name(".md")
        path = plant_prose(strict, name, exact.text)
        sid40 = _sid()
        _, flagged = fire_pinned(
            strict, exact_report, tool="Write", session_id=sid40,
            file_path=str(path), content=exact.text,
        )
        require_flagged_envelope(flagged, base=name, measured=exact)
        strict_rem = status_remainder(
            show_text(strict, sid40),
            name,
            exact,
            session_id=sid40,
            directory=str(strict.path),
        )
    print(f"[F05] confidence-none vs strict-40 {strict_rem!r}", flush=True)
    assert strict_none_rem == under_rem, (
        f"strict-none={strict_none_rem!r} under={under_rem!r}"
    )
    assert strict_none_rem != strict_rem, (
        f"strict-none={strict_none_rem!r} flagged={strict_rem!r}"
    )


def test_each_of_the_twenty_formats_nudges_with_the_flagged_envelope():
    dense = prose_dense()
    assert len(_TWENTY) == 20
    with workspace() as ws:
        ws.write_mode_flag("full")
        for ext in _TWENTY:
            name = fresh_name(ext)
            path = plant_prose(ws, name, dense.text)
            measured = measure_path(ws, name)
            if measured.score <= 40 or measured.confidence == "none":
                raise HarnessError(
                    f"{ext} scored {measured.score} at confidence {measured.confidence!r}"
                )
            _, nudge = fire_tool(
                ws, "Write", session_id=_sid(), file_path=str(path), content="payload"
            )
            require_flagged_envelope(nudge, base=name, measured=measured)
            print(f"[F05] format {ext} nudged score={measured.score}", flush=True)


def test_other_extensions_are_not_scored_or_handed_to_the_detector():
    dense = prose_dense()
    other = secrets.choice([".csv", ".log", ".html", ".xml", ".yaml"])
    assert other not in _TWENTY and other not in {".py", ".js"}
    with workspace() as ws:
        ws.write_mode_flag("full")
        other_name = fresh_name(other)
        other_path = plant_prose(ws, other_name, dense.text)
        _, nudge = fire_tool(
            ws, "Write", session_id=_sid(), file_path=str(other_path), content=dense.text
        )
        assert nudge == ""
    with workspace() as ws:
        ws.write_mode_flag("full")
        md_name = fresh_name(".md")
        md_path = plant_prose(ws, md_name, dense.text)
        measured = measure_path(ws, md_name)
        _, nudge = fire_tool(
            ws, "Write", session_id=_sid(), file_path=str(md_path), content="payload"
        )
        require_flagged_envelope(nudge, base=md_name, measured=measured)
    stall = 3.0
    with workspace() as ws:
        ws.write_mode_flag("full")
        with interpreter_standin(ws, sleep_s=stall, forward=True) as stand:
            for ext in (".py", ".js"):
                name = fresh_name(ext)
                path = plant_prose(ws, name, dense.text)
                sid = _sid()
                started = stand.invocations()

                def run(path=path, sid=sid):
                    return fire_tool(
                        ws,
                        "Write",
                        session_id=sid,
                        file_path=str(path),
                        content=dense.text,
                        env_updates=stand.env_updates,
                        timeout=stall,
                    )

                took, (_, nudge) = elapsed_call(run)
                assert took < stall
                assert nudge == ""
                assert stand.invocations() == started
            md_name = fresh_name(".md")
            md_path = plant_prose(ws, md_name, dense.text)
            try:
                fire_tool(
                    ws,
                    "Write",
                    session_id=_sid(),
                    file_path=str(md_path),
                    content="payload",
                    env_updates=stand.env_updates,
                    timeout=stall * 0.5,
                )
            except subprocess.TimeoutExpired:
                print("[F05] markdown score was not available before the stall", flush=True)
            else:
                raise HarnessError(
                    "markdown scoring returned before the stall ended; "
                    "the stall is not on the detector startup path"
                )


def _notebook_pair(ws, dense_text: str, *, code_first: bool) -> None:
    md_name = fresh_name(".ipynb")
    md_path = write_notebook(ws, md_name, markdown=dense_text)
    measured = measure_path(ws, md_name)
    if measured.score <= 40:
        raise HarnessError(f"markdown notebook scored {measured.score}")
    code_name = fresh_name(".ipynb")
    code_path = write_notebook(ws, code_name, code_source=dense_text)

    def nudge_markdown():
        _, nudge = fire_tool(
            ws,
            "NotebookEdit",
            session_id=_sid(),
            notebook_path=str(md_path),
            content="payload",
        )
        require_flagged_envelope(nudge, base=md_name, measured=measured)

    def silence_code():
        code_sid = _sid()
        _, nudge = fire_tool(
            ws,
            "NotebookEdit",
            session_id=code_sid,
            notebook_path=str(code_path),
            content="payload",
        )
        assert nudge == ""
        code_show = show_text(ws, code_sid)
        assert not standalone_int_present(
            _without_names(code_show, code_name), measured.score
        )

    if code_first:
        silence_code()
        nudge_markdown()
    else:
        nudge_markdown()
        silence_code()


def test_notebook_edit_scores_markdown_cells_only():
    dense = prose_dense()
    for code_first in (True, False):
        with workspace() as ws:
            ws.write_mode_flag("full")
            _notebook_pair(ws, dense.text, code_first=code_first)


def test_pdf_and_rtf_differ_from_a_failed_check():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        for ext in (".pdf", ".rtf"):
            name = fresh_name(ext)
            path = plant_prose(ws, name, "not a real binary document")
            sid = _sid()
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content="payload"
            )
            assert nudge == ""
            shown = show_text(ws, sid)
            assert name in shown
            _no_score(shown, name)
            missing = fresh_name(".md")
            miss_sid = _sid()
            _, miss_nudge = fire_tool(
                ws,
                "Write",
                session_id=miss_sid,
                file_path=str(ws.path / missing),
                content="payload",
            )
            assert miss_nudge == ""
            miss_show = show_text(ws, miss_sid)
            assert missing in miss_show
            binary_body = _without_names(shown, name, sid).lower()
            failed_body = _without_names(miss_show, missing, miss_sid).lower()
            assert "not re-scored" in binary_body, (
                f"{ext} listing is not the not-re-scored row; text={binary_body[:300]!r}"
            )
            assert "not scored" in failed_body and "not re-scored" not in failed_body, (
                f"missing path is not the not-scored row; text={failed_body[:300]!r}"
            )
        live = fresh_name(".md")
        live_path = plant_prose(ws, live, dense.text)
        measured = measure_path(ws, live)
        _, nudge = fire_tool(
            ws, "Write", session_id=_sid(), file_path=str(live_path), content="payload"
        )
        require_flagged_envelope(nudge, base=live, measured=measured)


def test_instruction_names_any_case_are_skipped_and_not_recorded():
    dense = prose_dense()
    names = (
        "CLAUDE.md",
        "Claude.Local.md",
        "AGENTS.md",
        "Agents.Local.md",
        "SKILL.md",
        "Memory.md",
    )
    with workspace() as ws:
        ws.write_mode_flag("full")
        sid = _sid()
        live = fresh_name(".md")
        live_path = plant_prose(ws, live, dense.text)
        measured = measure_path(ws, live)
        if measured.score <= 40 or measured.confidence == "none":
            raise HarnessError(f"ordinary prose scored {measured.score}")
        _, nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(live_path), content="payload"
        )
        require_flagged_envelope(nudge, base=live, measured=measured)
        assert live in show_text(ws, sid)
        for name in names:
            path = plant_prose(ws, name, dense.text)
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content=dense.text
            )
            assert nudge == ""


def test_instruction_stems_without_prose_extension_are_absent():
    stems = (
        "claude",
        "claude.local",
        "agents",
        "agents.local",
        "skill",
        "memory",
    )
    pdf_names = [stem + ".pdf" for stem in stems]
    rtf_names = [stem + ".rtf" for stem in stems]
    skipped = pdf_names + rtf_names
    with workspace() as ws:
        ws.write_mode_flag("full")
        sid = _sid()

        def save(name: str, body: str) -> None:
            path = plant_prose(ws, name, body)
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content="payload"
            )
            assert nudge == ""

        first = fresh_name(".pdf")
        save(first, "ordinary pdf")
        for name in pdf_names:
            save(name, "binary stem")
        middle = fresh_name(".pdf")
        save(middle, "ordinary pdf")
        for name in rtf_names:
            save(name, "binary stem")
        last = fresh_name(".pdf")
        save(last, "ordinary pdf")
        assert {first, middle, last}.isdisjoint(skipped)
        shown = show_text(ws, sid)
        assert first in shown and middle in shown and last in shown
        for name in skipped:
            basename_absent(shown, name)


def test_prose_stem_other_than_agents_txt_is_scored():
    dense = prose_dense()
    banned = set(_SKIP_NAMES) | {"agents.txt"}
    choices = [
        stem + ext
        for stem in ("claude", "skill", "memory", "agents", "claude.local")
        for ext in PLAIN_EXTS
        if stem + ext not in banned
    ]
    name = secrets.choice(choices)
    with workspace() as ws:
        ws.write_mode_flag("full")
        for leaf in (name, "agents.txt"):
            path = plant_prose(ws, leaf, dense.text)
            measured = measure_path(ws, leaf)
            if measured.score <= 40:
                raise HarnessError(f"{leaf} scored {measured.score}")
            _, nudge = fire_tool(
                ws, "Write", session_id=_sid(), file_path=str(path), content="payload"
            )
            require_flagged_envelope(nudge, base=leaf, measured=measured)


def test_paths_under_vendor_git_and_memory_are_skipped():
    dense = prose_dense()
    skipped = []
    for folder in ("node_modules", ".git", "memory"):
        for ext in (".md", ".docx"):
            skipped.append(f"{folder}/{fresh_name(ext)}")
        skipped.append(f"{folder}/nested/{fresh_name('.md')}")
    skipped.append(f"node_modules/nested/{fresh_name('.docx')}")
    for rel in skipped:
        with workspace() as ws:
            ws.write_mode_flag("full")
            path = plant_prose(ws, rel, dense.text)
            _, nudge = fire_tool(
                ws, "Write", session_id=_sid(), file_path=str(path), content=dense.text
            )
            assert nudge == "", rel
    with workspace() as ws:
        ws.write_mode_flag("full")
        live = fresh_name(".md")
        live_path = plant_prose(ws, live, dense.text)
        measured = measure_path(ws, live)
        _, nudge = fire_tool(
            ws, "Write", session_id=_sid(), file_path=str(live_path), content="payload"
        )
        require_flagged_envelope(nudge, base=live, measured=measured)


def test_files_inside_the_plugin_install_tree_are_skipped():
    dense = prose_dense()
    root, env = relocated_plugin_root()
    try:
        with workspace() as outside:
            outside.write_mode_flag("full")
            live = fresh_name(".md")
            live_path = plant_prose(outside, live, dense.text)
            measured = measure_path(outside, live)
            _, nudge = fire_tool(
                outside,
                "Write",
                session_id=_sid(),
                file_path=str(live_path),
                content="payload",
                env_updates=env,
            )
            require_flagged_envelope(nudge, base=live, measured=measured)
        with workspace() as inside_ws:
            inside_ws.write_mode_flag("full")
            inside = root / fresh_name(".md")
            inside.write_text(dense.text, encoding="utf-8")
            _, nudge = fire_tool(
                inside_ws,
                "Write",
                session_id=_sid(),
                file_path=str(inside),
                content=dense.text,
                env_updates=env,
            )
            assert nudge == ""
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_write_edit_and_multiedit_score_the_file_on_disk():
    disk = prose_dense()
    clean = prose_under()
    assert disk.score != clean.score
    with workspace() as ws:
        ws.write_mode_flag("full")
        for tool in ("Write", "Edit", "MultiEdit"):
            name = fresh_name(".md")
            path = plant_prose(ws, name, disk.text)
            _, nudge = fire_tool(
                ws,
                tool,
                session_id=_sid(),
                file_path=str(path),
                content=clean.text,
            )
            require_flagged_envelope(nudge, base=name, measured=disk)
            assert not standalone_int_present(
                _without_names(nudge, name), clean.score
            ), f"{tool} reported the payload score {clean.score}"


def test_notebook_edit_ignores_a_file_path_field():
    """NotebookEdit scores a payload that names the notebook path.

    Whether a payload that carries a file path and no notebook path is
    scored or ignored is the implementer's and is not scored. That arm
    still exits successfully: a non-zero exit fails the host. It does
    not demand an empty nudge or an absent ledger row. The arm that
    names the notebook path prints the envelope. Each call is the only
    call in its workspace.
    """
    dense = prose_dense()
    with workspace() as via_file:
        via_file.write_mode_flag("full")
        name = fresh_name(".ipynb")
        path = write_notebook(via_file, name, markdown=dense.text)
        result, _nudge = fire_tool(
            via_file,
            "NotebookEdit",
            session_id=_sid(),
            file_path=str(path),
            content=dense.text,
        )
        assert result.returncode == 0
    with workspace() as via_notebook:
        via_notebook.write_mode_flag("full")
        name = fresh_name(".ipynb")
        path = write_notebook(via_notebook, name, markdown=dense.text)
        measured = measure_path(via_notebook, name)
        if measured.score <= 40:
            raise HarnessError(f"notebook scored {measured.score}")
        result, nudge = fire_tool(
            via_notebook,
            "NotebookEdit",
            session_id=_sid(),
            notebook_path=str(path),
            content="payload",
        )
        assert result.returncode == 0
        require_flagged_envelope(nudge, base=name, measured=measured)


def test_apply_patch_add_update_and_move_lines_name_paths():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        for verb in ("Add File", "Update File", "Move to"):
            name = fresh_name(".md")
            path = plant_prose(ws, name, dense.text)
            measured = measure_path(ws, name)
            command = f"*** {verb}: {path}\n"
            _, nudge = fire_tool(
                ws, "apply_patch", session_id=_sid(), command=command
            )
            require_flagged_envelope(nudge, base=name, measured=measured)
            # The path is whatever remains after the colon. Spaces around
            # that remainder, past the single space above, still name it.
            spaced = fresh_name(".md")
            spaced_path = plant_prose(ws, spaced, dense.text)
            spaced_measured = measure_path(ws, spaced)
            padded = f"*** {verb}:  {spaced_path} \n"
            remainder = padded.split(":", 1)[1].removesuffix("\n")
            assert remainder != f" {spaced_path}"
            assert remainder.strip() == str(spaced_path)
            _, padded_nudge = fire_tool(
                ws, "apply_patch", session_id=_sid(), command=padded
            )
            require_flagged_envelope(
                padded_nudge, base=spaced, measured=spaced_measured
            )


def test_apply_patch_lines_that_do_not_begin_with_the_prefix_name_no_path():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        live = fresh_name(".md")
        live_path = plant_prose(ws, live, dense.text)
        measured = measure_path(ws, live)
        result, nudge = fire_tool(
            ws,
            "apply_patch",
            session_id=_sid(),
            command=f"*** Update File: {live_path}\n",
        )
        assert result.returncode == 0
        require_flagged_envelope(nudge, base=live, measured=measured)
    for command in (
        "***Update File: {path}\n",
        "*** Delete File: {path}\n",
        "Update File: {path}\n",
    ):
        with workspace() as ws:
            ws.write_mode_flag("full")
            name = fresh_name(".md")
            path = plant_prose(ws, name, dense.text)
            sid = _sid()
            result, nudge = fire_tool(
                ws,
                "apply_patch",
                session_id=sid,
                command=command.format(path=path),
            )
            assert result.returncode == 0
            assert nudge == ""
            basename_absent(show_text(ws, sid), name)


def test_relative_path_resolves_against_the_payload_working_directory():
    dense = prose_dense()
    clean = prose_under()
    assert dense.score != clean.score
    root, env = relocated_plugin_root()
    try:
        with workspace() as ws:
            ws.write_mode_flag("full")
            decoy = ws.path / "decoy"
            work = ws.path / "work"
            decoy.mkdir()
            work.mkdir()
            for tool, command in (
                ("Write", None),
                ("apply_patch", True),
            ):
                name = fresh_name(".md")
                assert name != "draft.md"
                (decoy / name).write_text(clean.text, encoding="utf-8")
                (work / name).write_text(dense.text, encoding="utf-8")
                (root / name).write_text(clean.text, encoding="utf-8")
                on_disk = measure_text((work / name).read_text(encoding="utf-8"))
                payload_command = f"*** Update File: {name}\n" if command else None
                sid = _sid()
                _, nudge = fire_tool(
                    ws,
                    tool,
                    session_id=sid,
                    file_path=None if command else name,
                    content=None if command else clean.text,
                    command=payload_command,
                    cwd=str(work),
                    process_cwd=str(decoy),
                    env_updates=env,
                )
                print(
                    f"[F05] relative {tool} nudge={nudge[:400]!r}",
                    flush=True,
                )
                require_flagged_envelope(nudge, base=name, measured=on_disk)
                assert not standalone_int_present(
                    _without_names(nudge, name), clean.score
                ), f"{tool} reported the other file's score {clean.score}"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_apply_patch_concatenates_only_flagged_files():
    dense = prose_dense()
    clean = prose_under()
    assert clean.score <= 40
    with workspace() as ws:
        ws.write_mode_flag("full")
        slop_name = fresh_name(".md")
        clean_name = fresh_name(".md")
        slop_path = plant_prose(ws, slop_name, dense.text)
        clean_path = plant_prose(ws, clean_name, clean.text)
        slop_measured = measure_path(ws, slop_name)
        clean_measured = measure_path(ws, clean_name)
        sid = _sid()
        command = f"*** Update File: {slop_path}\n*** Update File: {clean_path}\n"
        _, nudge = fire_tool(ws, "apply_patch", session_id=sid, command=command)
        require_flagged_envelope(nudge, base=slop_name, measured=slop_measured)
        assert clean_name not in nudge
        shown = show_text(ws, sid)
        assert slop_name in shown and clean_name in shown
        assert standalone_int_present(shown, clean_measured.score)


def test_duplicate_patch_path_is_one_scored_row():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(ws, name, dense.text)
        measured = measure_path(ws, name)
        if measured.score <= 40 or measured.confidence == "none":
            raise HarnessError(f"patch fixture scored {measured.score}")
        sid = _sid()
        _, once = fire_tool(
            ws, "apply_patch", session_id=sid, command=f"*** Update File: {path}\n"
        )
        require_flagged_envelope(once, base=name, measured=measured)
        shown_once = show_text(ws, sid)
        assert name in shown_once
        assert standalone_int_present(shown_once, measured.score)
        once_nudge = basename_mentions(once, name)
        once_show = basename_mentions(shown_once, name)

        # Seventeen lines, sixteen distinct paths. The repeated path is
        # the first two lines, so it sits inside a sixteen-line cap. The
        # sixteenth distinct path is the seventeenth line. A line cap
        # drops that path; a second row for the repeat spends a slot
        # that one distinct path does not spend.
        others = []
        for _ in range(15):
            other = fresh_name(".md")
            others.append((other, plant_prose(ws, other, dense.text)))
        last_name, last_path = others[14]
        head = [path, path] + [item_path for _, item_path in others[:14]]
        assert len(head) == 16
        first_sixteen = {name} | {other for other, _ in others[:14]}
        assert last_name not in first_sixteen
        assert len(first_sixteen) == 15
        command = "".join(f"*** Update File: {item}\n" for item in head)
        command += f"*** Update File: {last_path}\n"
        distinct = [name] + [other for other, _ in others]
        assert len(set(distinct)) == 16
        dsid = _sid()
        _, nudge = fire_tool(
            ws, "apply_patch", session_id=dsid, command=command
        )
        _patch_sections(nudge, distinct, measured)
        assert basename_mentions(nudge, name) == once_nudge, (
            "naming the same path twice concatenated a second nudge for it"
        )
        shown = show_text(ws, dsid)
        assert standalone_int_present(shown, measured.score)
        assert basename_mentions(shown, name) == once_show, (
            "naming the same path twice recorded a second scored row"
        )
        assert all(other in shown for other, _ in others)


def _patch_sections(nudge: str, names: list[str], measured) -> None:
    for name in names:
        section = own_nudge_section(
            nudge, name, [other for other in names if other != name]
        )
        require_flagged_envelope(section, base=name, measured=measured)


def test_apply_patch_scores_at_most_sixteen_distinct_paths():
    dense = prose_dense()
    clean = prose_under()
    with workspace() as ws:
        ws.write_mode_flag("full")
        flagged = []
        for _ in range(17):
            name = fresh_name(".md")
            path = plant_prose(ws, name, dense.text)
            flagged.append((name, path))
        measured = measure_path(ws, flagged[0][0])
        if measured.score <= 40 or measured.confidence == "none":
            raise HarnessError(f"patch fixture scored {measured.score}")
        sixteen = "\n".join(f"*** Update File: {path}" for _, path in flagged[:16]) + "\n"
        _, nudge = fire_tool(ws, "apply_patch", session_id=_sid(), command=sixteen)
        _patch_sections(nudge, [name for name, _path in flagged[:16]], measured)
        sid = _sid()
        seventeen = "\n".join(f"*** Update File: {path}" for _, path in flagged) + "\n"
        _, nudge = fire_tool(ws, "apply_patch", session_id=sid, command=seventeen)
        in_nudge = [name for name, _path in flagged if name in nudge]
        omitted = [name for name, _path in flagged if name not in nudge]
        assert len(in_nudge) == 16 and len(omitted) == 1
        _patch_sections(nudge, in_nudge, measured)
        shown = show_text(ws, sid)
        assert omitted[0] not in shown
        assert all(name in shown for name in in_nudge)
        quiet = []
        for _ in range(17):
            name = fresh_name(".md")
            path = plant_prose(ws, name, clean.text)
            quiet.append((name, path))
        body = "\n".join(f"*** Update File: {path}" for _, path in quiet) + "\n"
        qsid = _sid()
        _, nudge = fire_tool(ws, "apply_patch", session_id=qsid, command=body)
        assert nudge == ""
        qshow = show_text(ws, qsid)
        quiet_show = [name for name, _path in quiet if name in qshow]
        assert len(quiet_show) == 16
        assert standalone_int_present(qshow, clean.score)


def test_show_holds_fired_labels_base_name_and_not_the_body():
    dense = prose_dense()
    marker = runtime_token("mark")
    text = dense.text + "\n" + marker
    measured = measure_text(text)
    if measured.score <= 40 or not measured.labels:
        raise HarnessError("marked dense prose was not a flagged labeled file")
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(ws, name, text)
        before = snapshot_config(ws.config_dir)
        sid = _sid()
        _, nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(path), content=text
        )
        require_flagged_envelope(nudge, base=name, measured=measured)
        shown = show_text(ws, sid)
        assert name in shown
        assert standalone_int_present(shown, measured.score)
        assert measured.band in shown
        present = [label for label in measured.labels if label in shown]
        assert present
        assert len(present) <= 5
        if len(measured.labels) > 5:
            assert len(present) < len(measured.labels)
        assert marker not in shown
        config_omits(changed_config_files(ws.config_dir, before), marker)
        config_omits(changed_config_files(ws.config_dir, before), str(path.parent))


def test_ledger_keeps_at_most_the_newest_twenty():
    clean = prose_under()
    with workspace() as ws:
        ws.write_mode_flag("full")
        sid = _sid()
        names = []
        for _ in range(21):
            name = fresh_name(".md")
            path = plant_prose(ws, name, clean.text)
            fire_tool(ws, "Write", session_id=sid, file_path=str(path), content=clean.text)
            names.append(name)
        shown = show_text(ws, sid)
        assert names[-1] in shown
        assert names[0] not in shown
        assert sum(1 for name in names if name in shown) == 20


def test_ledger_is_per_session_id():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        left = _sid()
        right = _sid()
        left_name = fresh_name(".md")
        right_name = fresh_name(".md")
        fire_tool(
            ws,
            "Write",
            session_id=left,
            file_path=str(plant_prose(ws, left_name, dense.text)),
            content="payload",
        )
        fire_tool(
            ws,
            "Write",
            session_id=right,
            file_path=str(plant_prose(ws, right_name, dense.text)),
            content="payload",
        )
        left_show = show_text(ws, left)
        right_show = show_text(ws, right)
        assert left_name in left_show and right_name not in left_show
        assert right_name in right_show and left_name not in right_show


def test_saved_ledger_files_are_owner_only_without_a_fixed_prefix():
    dense = prose_dense()
    marker = runtime_token("mark")
    text = dense.text + "\n" + marker
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(ws, name, text)
        sid = _sid()
        fire_tool(ws, "Write", session_id=sid, file_path=str(path), content=text)
        assert name in show_text(ws, sid)
        assert_private_ledger_snapshot(
            ws.config_dir, base=name, parent=str(path.parent), marker=marker
        )


def test_plain_text_over_512_kb_names_512():
    dense = prose_dense()
    prefix = repeat_to(dense.text, SCAN_CAP)
    scored = measure_text(prefix)
    if scored.score <= 40:
        raise HarnessError(f"windowed slop scored {scored.score}")
    under = prefix + (" " * (DECIMAL_512_KB - len(prefix)))
    assert len(under.encode("utf-8")) == DECIMAL_512_KB
    over = prefix + (" " * (OVER_BOTH_512 - len(prefix)))
    assert len(over.encode("utf-8")) == OVER_BOTH_512
    with workspace() as ws:
        ws.write_mode_flag("full")
        ok_name = fresh_name(".md")
        ok_path = plant_prose(ws, ok_name, under)
        _, nudge = fire_tool(
            ws, "Write", session_id=_sid(), file_path=str(ok_path), content="payload"
        )
        require_flagged_envelope(nudge, base=ok_name, measured=scored)
        for ext in (".md", ".txt"):
            name = fresh_name(ext)
            path = plant_prose(ws, name, over)
            sid = _sid()
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content="payload"
            )
            assert nudge == ""
            shown = show_text(ws, sid)
            assert name in shown
            body = _without_names(shown, name)
            assert "not scored" in body.lower()
            assert standalone_int_present(body, PLAIN_KB)
            assert not standalone_int_present(body, scored.score)


def test_zip_between_the_caps_is_still_scored():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        for ext in (".docx", ".ipynb"):
            name = fresh_name(ext)
            path = plant_prose(ws, name, dense.text)
            pad_file_to_size(path, BETWEEN_CAPS)
            measured = measure_path(ws, name)
            if measured.score <= 40:
                raise HarnessError(f"{ext} between the caps scored {measured.score}")
            _, nudge = fire_tool(
                ws, "Write", session_id=_sid(), file_path=str(path), content="payload"
            )
            require_flagged_envelope(nudge, base=name, measured=measured)


def test_archive_and_notebook_over_4_mb_share_a_kilobyte_figure():
    dense = prose_dense()
    scored = measure_text(dense.text)
    specs = (
        (".docx", OVER_BOTH_4MB),
        (".docx", OVER_BOTH_4MB_OTHER),
        (".epub", OVER_BOTH_4MB),
        (".ipynb", OVER_BOTH_4MB),
    )
    figures = []
    sizes = []
    with workspace() as ws:
        ws.write_mode_flag("full")
        for ext, size in specs:
            name = fresh_name(ext)
            path = plant_prose(ws, name, dense.text)
            pad_file_to_size(path, size)
            sizes.append(path.stat().st_size)
            sid = _sid()
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content="payload"
            )
            assert nudge == ""
            shown = show_text(ws, sid)
            assert name in shown
            body = _without_names(shown, name, sid)
            print(f"[F05] over4 {ext} size={path.stat().st_size} show={body[:300]!r}", flush=True)
            assert "not scored" in body.lower(), (
                f"{ext} size skip was not reported as not scored; text={body[:300]!r}"
            )
            assert not standalone_int_present(body, scored.score), (
                f"{ext} size skip still carried the detector score {scored.score}"
            )
            figures.append(_kb_figure(body))
    assert len(set(sizes[:2])) == 2
    assert len(set(figures)) == 1


def test_truncated_extracted_prose_names_the_262144_window():
    dense = prose_dense()
    exact = repeat_to(dense.text, SCAN_CAP)
    over = repeat_to(dense.text, SCAN_CAP + 1)
    with workspace() as ws:
        ws.write_mode_flag("full")
        arms = {}
        for label, text in (("exact", exact), ("over", over)):
            name = fresh_name(".docx")
            path = plant_prose(ws, name, text)
            size = path.stat().st_size
            if size >= SCAN_CAP // 4 or size >= 4 * 1000 * 1000:
                raise HarnessError(f"{label} docx is {size} bytes; not a small archive")
            measured = measure_path(ws, name)
            if measured.score <= 40:
                raise HarnessError(f"{label} docx scored {measured.score}")
            sid = _sid()
            _, nudge = fire_tool(
                ws, "Write", session_id=sid, file_path=str(path), content="payload"
            )
            shown = show_text(ws, sid)
            arms[label] = (name, nudge, shown, measured)
        exact_name, exact_nudge, exact_show, exact_measured = arms["exact"]
        over_name, over_nudge, over_show, over_measured = arms["over"]
        require_flagged_envelope(exact_nudge, base=exact_name, measured=exact_measured)
        require_flagged_envelope(over_nudge, base=over_name, measured=over_measured)
    # L230 requires the scored-prefix statement only when the scan was
    # truncated. Naming the window size on a scan that fits is allowed.
    assert not states_scored_prefix(exact_nudge), (
        "exact-window extra context states that only a 262,144-character "
        f"prefix was scored; text={exact_nudge[:500]!r}"
    )
    assert not names_window(exact_show)
    assert names_window(over_nudge)
    assert states_scored_prefix(over_nudge), (
        "over-window extra context prints the window digits but does not "
        "state that only the first 262,144 characters were scored; "
        f"text={over_nudge[:500]!r}"
    )
    assert names_window(over_show)
    exact_row = row_around(exact_show, exact_name, [])
    over_row = row_around(over_show, over_name, [])
    assert not names_window(exact_row)
    assert names_window(over_row)


def _node_on_stripped_path(updates: dict[str, str]) -> dict[str, str]:
    node = shutil.which("node")
    if not node:
        raise HarnessError("node is not on PATH before the no-python arm")
    Path(updates["PATH"], "node").symlink_to(node)
    return updates


def _failed_show(ws, name: str, path: str, sid: str, *extra: object) -> tuple[str, str]:
    shown = show_text(ws, sid)
    assert name in shown, f"failed save {name!r} was not recorded"
    row = row_around(shown, name, [])
    rem = remainder(row, [name, path, sid, *extra])
    print(f"[F05] failure {name} remainder={rem!r}", flush=True)
    return shown, rem


def _detector_failure(
    ws,
    stand_kwargs: dict,
    *,
    timeout: float,
) -> tuple[str, str]:
    name = fresh_name(".md")
    path = plant_prose(ws, name, "eligible prose that the stand-in will not score\n")
    sid = _sid()
    with interpreter_standin(ws, **stand_kwargs) as stand:
        started = stand.invocations()
        try:
            result, nudge = fire_tool(
                ws,
                "Write",
                session_id=sid,
                file_path=str(path),
                content="payload",
                env_updates=stand.env_updates,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                "detector stand-in hung the host; a failure must return"
            ) from exc
        assert stand.invocations() > started, "stand-in was not on the detector path"
    assert result.returncode == 0
    assert nudge == ""
    return _failed_show(ws, name, str(path), sid)


def test_five_failure_reasons_stay_distinguishable():
    sentence = "the detector wrote a sentence and nothing else"
    without_score, _with_leftover, _leftovers = missing_score_arms(2)
    with workspace() as ws:
        ws.write_mode_flag("full")
        _, no_python = _no_python_reason(ws)
        _, plain = _detector_failure(
            ws, {"stdout": sentence, "exit_code": 0}, timeout=20
        )
        _, missing = _detector_failure(
            ws, {"stdout": without_score, "exit_code": 0}, timeout=20
        )
        _, timed = _detector_failure(
            ws, {"sleep_s": 30, "forward": True}, timeout=20
        )
        missing_path = fresh_name(".md")
        miss_sid = _sid()
        miss_abs = str(ws.path / missing_path)
        result, nudge = fire_tool(
            ws,
            "Write",
            session_id=miss_sid,
            file_path=miss_abs,
            content="payload",
        )
        assert result.returncode == 0 and nudge == ""
        _, absent = _failed_show(ws, missing_path, miss_abs, miss_sid)
        _, empty = _detector_failure(ws, {"stdout": "", "exit_code": 0}, timeout=20)
        _, crashed = _detector_failure(ws, {"exit_code": 1}, timeout=20)
    print(
        f"[F05] class5 absent={absent!r} empty={empty!r} crashed={crashed!r}",
        flush=True,
    )
    # An empty result shares its reason with an exit that yields no usable
    # result. Whether a missing path uses that reason is not scored.
    assert empty == crashed, (
        f"empty result and a non-zero exit did not share one reason: "
        f"empty={empty!r} crashed={crashed!r}"
    )
    distinct = (no_python, plain, missing, timed, empty)
    for left in range(len(distinct)):
        for right in range(left + 1, len(distinct)):
            assert distinct[left] != distinct[right], (
                f"failure reasons collapsed: {distinct[left]!r} vs {distinct[right]!r}"
            )


def _no_python_reason(ws) -> tuple[str, str]:
    updates = _node_on_stripped_path(updates_without_interpreters())
    name = fresh_name(".md")
    path = plant_prose(ws, name, "eligible prose with no interpreter\n")
    sid = _sid()
    result, nudge = fire_tool(
        ws,
        "Write",
        session_id=sid,
        file_path=str(path),
        content="payload",
        env_updates=updates,
        timeout=20,
    )
    assert result.returncode == 0
    assert nudge == ""
    return _failed_show(ws, name, str(path), sid)


def test_missing_score_is_not_any_integer():
    planted = 2
    sentence = "the detector wrote a sentence and nothing else"
    without_score, with_leftover, leftovers = missing_score_arms(planted)
    assert planted in leftovers
    with workspace() as ws:
        ws.write_mode_flag("full")
        _, plain = _detector_failure(
            ws, {"stdout": sentence, "exit_code": 0}, timeout=20
        )
        bare_name = fresh_name(".md")
        bare_path = plant_prose(ws, bare_name, "eligible prose\n")
        bare_sid = _sid()
        with interpreter_standin(ws, stdout=without_score, exit_code=0) as stand:
            started = stand.invocations()
            result, nudge = fire_tool(
                ws,
                "Write",
                session_id=bare_sid,
                file_path=str(bare_path),
                content="payload",
                env_updates=stand.env_updates,
                timeout=20,
            )
            assert stand.invocations() > started, "stand-in was not on the detector path"
        assert result.returncode == 0 and nudge == ""
        _, bare = _failed_show(ws, bare_name, str(bare_path), bare_sid, planted)
        count_name = fresh_name(".md")
        count_path = plant_prose(ws, count_name, "eligible prose\n")
        count_sid = _sid()
        with interpreter_standin(ws, stdout=with_leftover, exit_code=0) as stand:
            started = stand.invocations()
            result, nudge = fire_tool(
                ws,
                "Write",
                session_id=count_sid,
                file_path=str(count_path),
                content="payload",
                env_updates=stand.env_updates,
                timeout=20,
            )
            assert stand.invocations() > started, "stand-in was not on the detector path"
        assert result.returncode == 0 and nudge == ""
        shown, counted = _failed_show(
            ws, count_name, str(count_path), count_sid, planted
        )
        body = _without_names(shown, count_name, str(count_path), count_sid)
        assert not standalone_int_present(body, planted), (
            f"the planted count {planted} was recorded as the file score; "
            f"text={shown[:400]!r}"
        )
        for value in leftovers:
            assert not standalone_int_present(body, value), (
                f"leftover integer {value} was recorded as the file score; "
                f"text={shown[:400]!r}"
            )
    print(f"[F05] missing-score bare={bare!r} counted={counted!r}", flush=True)
    assert bare == counted
    assert bare != plain


def test_empty_result_shares_its_reason_with_unreadable():
    sentence = "the detector wrote a sentence and nothing else"
    with workspace() as ws:
        ws.write_mode_flag("full")
        _, plain = _detector_failure(
            ws, {"stdout": sentence, "exit_code": 0}, timeout=20
        )
        missing = fresh_name(".md")
        miss_sid = _sid()
        miss_abs = str(ws.path / missing)
        result, nudge = fire_tool(
            ws, "Write", session_id=miss_sid, file_path=miss_abs, content="payload"
        )
        assert result.returncode == 0 and nudge == ""
        _, absent = _failed_show(ws, missing, miss_abs, miss_sid)
        _, empty = _detector_failure(ws, {"stdout": "", "exit_code": 0}, timeout=20)
        _, crashed = _detector_failure(ws, {"exit_code": 1}, timeout=20)
    print(
        f"[F05] unreadable absent={absent!r} empty={empty!r} crashed={crashed!r} "
        f"plain={plain!r}",
        flush=True,
    )
    # The missing path is recorded above. Its reason is not compared to
    # the empty result: that choice is the implementer's.
    assert empty == crashed, (
        f"empty result and a non-zero exit did not share one reason: "
        f"empty={empty!r} crashed={crashed!r}"
    )
    assert empty != plain, (
        f"empty result collapsed into the unusable report: "
        f"empty={empty!r} plain={plain!r}"
    )
    assert crashed != plain, (
        f"non-zero exit collapsed into the unusable report: "
        f"crashed={crashed!r} plain={plain!r}"
    )


def test_no_path_directory_and_other_non_file_record_nothing():
    with workspace() as ws:
        ws.write_mode_flag("full")
        empty_sid = _sid()
        before_show = show_text(ws, empty_sid)
        result, nudge = fire_tool(ws, "Write", session_id=empty_sid, content="payload")
        assert result.returncode == 0 and nudge == ""
        assert show_text(ws, empty_sid) == before_show

        sid = _sid()
        missing = fresh_name(".md")
        result, nudge = fire_tool(
            ws,
            "Write",
            session_id=sid,
            file_path=str(ws.path / missing),
            content="payload",
        )
        assert result.returncode == 0 and nudge == ""
        assert missing in show_text(ws, sid)

        folder = ws.path / fresh_name(".md")
        folder.mkdir()
        try:
            result, nudge = fire_tool(
                ws,
                "Write",
                session_id=sid,
                file_path=str(folder),
                content="payload",
                timeout=5,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssertionError("a directory path hung the hook") from exc
        assert result.returncode == 0 and nudge == ""
        listed = show_text(ws, sid)
        basename_absent(listed, folder.name)
        assert missing in listed

        later = fresh_name(".md")
        result, nudge = fire_tool(
            ws,
            "Write",
            session_id=sid,
            file_path=str(ws.path / later),
            content="payload",
        )
        assert result.returncode == 0 and nudge == ""
        listed = show_text(ws, sid)
        assert later in listed
        basename_absent(listed, folder.name)

        fifo = ws.path / fresh_name(".txt")
        os.mkfifo(fifo)
        try:
            result, nudge = fire_tool(
                ws,
                "Write",
                session_id=sid,
                file_path=str(fifo),
                content="payload",
                timeout=5,
            )
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(
                "a fifo path hung the hook; the spec is to ignore it"
            ) from exc
        assert result.returncode == 0 and nudge == ""
        listed = show_text(ws, sid)
        basename_absent(listed, fifo.name)
        assert later in listed

        after_fifo = fresh_name(".md")
        result, nudge = fire_tool(
            ws,
            "Write",
            session_id=sid,
            file_path=str(ws.path / after_fifo),
            content="payload",
        )
        assert result.returncode == 0 and nudge == ""
        listed = show_text(ws, sid)
        assert after_fifo in listed
        basename_absent(listed, folder.name)
        basename_absent(listed, fifo.name)


def test_malformed_input_exits_successfully_without_a_nudge():
    dense = prose_dense()
    with workspace() as flagged:
        flagged.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(flagged, name, dense.text)
        measured = measure_path(flagged, name)
        _, nudge = fire_tool(
            flagged, "Write", session_id=_sid(), file_path=str(path), content="payload"
        )
        require_flagged_envelope(nudge, base=name, measured=measured)
    with workspace() as broken:
        broken.write_mode_flag("full")
        result = broken.invoke_hook("post-tool-use", stdin=b"{", timeout=10)
        assert result.returncode == 0
        assert nudge_text(result) == ""


def _budget_arm(
    ext: str,
    sleep_s: float,
    *,
    scored: bool,
    hook_timeout: float,
    min_elapsed: float,
    max_elapsed: float | None,
) -> str | None:
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(ext)
        path = plant_prose(ws, name, dense.text)
        measured = measure_path(ws, name)
        if measured.score <= 40 or measured.confidence == "none":
            raise HarnessError(
                f"{ext} budget fixture scored {measured.score} "
                f"at confidence {measured.confidence!r}"
            )
        sid = _sid()
        with interpreter_standin(ws, sleep_s=sleep_s, forward=True) as stand:
            def run():
                if ext == NOTEBOOK_EXT:
                    return fire_tool(
                        ws,
                        "NotebookEdit",
                        session_id=sid,
                        notebook_path=str(path),
                        content="payload",
                        env_updates=stand.env_updates,
                        timeout=hook_timeout,
                    )
                return fire_tool(
                    ws,
                    "Write",
                    session_id=sid,
                    file_path=str(path),
                    content="payload",
                    env_updates=stand.env_updates,
                    timeout=hook_timeout,
                )

            try:
                elapsed, (result, nudge) = elapsed_call(run)
            except subprocess.TimeoutExpired as exc:
                raise AssertionError(
                    f"{ext} sleep {sleep_s}s hung the host"
                ) from exc
            assert stand.invocations() >= 2
        shown = show_text(ws, sid)
        print(
            f"[F05] budget {ext} sleep={sleep_s} elapsed={elapsed:.2f} "
            f"scored_arm={scored} exit={result.returncode}",
            flush=True,
        )
        assert elapsed + 0.05 >= min_elapsed, (
            f"{ext} sleep {sleep_s}s returned in {elapsed:.2f}s"
        )
        if max_elapsed is not None:
            assert elapsed <= max_elapsed, (
                f"{ext} sleep {sleep_s}s took {elapsed:.2f}s"
            )
        body = _without_names(shown, name)
        if scored:
            require_flagged_envelope(nudge, base=name, measured=measured)
            assert standalone_int_present(body, measured.score)
            return None
        assert result.returncode == 0
        assert nudge == ""
        assert name in shown
        assert not standalone_int_present(body, measured.score)
        row = row_around(shown, name, [])
        return remainder(row, [name, str(path), sid, measured.score])


def test_detector_budgets_are_8s_plain_and_15s_archive():
    _budget_arm(".md", 7, scored=True, hook_timeout=20, min_elapsed=6.5, max_elapsed=None)
    _budget_arm(".txt", 7, scored=True, hook_timeout=20, min_elapsed=6.5, max_elapsed=None)
    reasons = [
        _budget_arm(
            ".md", 9, scored=False, hook_timeout=20, min_elapsed=5, max_elapsed=8.9
        ),
        _budget_arm(
            ".txt", 9, scored=False, hook_timeout=20, min_elapsed=5, max_elapsed=8.9
        ),
    ]
    _budget_arm(
        ".docx", 14, scored=True, hook_timeout=40, min_elapsed=13, max_elapsed=None
    )
    _budget_arm(
        ".epub", 14, scored=True, hook_timeout=40, min_elapsed=13, max_elapsed=None
    )
    reasons.append(
        _budget_arm(
            ".docx", 16, scored=False, hook_timeout=40, min_elapsed=12, max_elapsed=15.8
        )
    )
    reasons.append(
        _budget_arm(
            ".epub", 16, scored=False, hook_timeout=40, min_elapsed=12, max_elapsed=15.8
        )
    )
    reasons.append(
        _budget_arm(
            ".docx", 60, scored=False, hook_timeout=30, min_elapsed=12, max_elapsed=29
        )
    )
    _budget_arm(
        ".ipynb", 14, scored=True, hook_timeout=40, min_elapsed=13, max_elapsed=None
    )
    reasons.append(
        _budget_arm(
            ".ipynb", 16, scored=False, hook_timeout=40, min_elapsed=12, max_elapsed=15.8
        )
    )
    others = _other_four_failure_reasons()
    print(f"[F05] timeout reasons={reasons!r} others={others!r}", flush=True)
    assert all(reasons)
    # A readable timeout reason may name the cap that expired, so the
    # 8-second rows and the 15-second rows need not be one string.
    for reason in reasons:
        for other in others:
            assert reason != other, (
                f"timeout reason collapsed into another failure: "
                f"timeout={reason!r} other={other!r}"
            )


def _other_four_failure_reasons() -> tuple[str, str, str, str]:
    """The four failure reasons that are not a detector timeout.

    Same arms as the five-reason contrast: missing interpreter, text that
    is not a structured report, a structured report with no numeric score,
    and a detector that produces no output. An empty result shares that
    last reason with an exit that yields no usable result.
    """
    sentence = "the detector wrote a sentence and nothing else"
    with workspace() as ws:
        ws.write_mode_flag("full")
        _, no_python = _no_python_reason(ws)
        _, plain = _detector_failure(
            ws, {"stdout": sentence, "exit_code": 0}, timeout=20
        )
        _, missing = _detector_failure(
            ws,
            {"stdout": '{"status":"ok","kind":"ready"}', "exit_code": 0},
            timeout=20,
        )
        _, empty = _detector_failure(ws, {"stdout": "", "exit_code": 0}, timeout=20)
    return no_python, plain, missing, empty


def test_guard_opens_no_socket():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        name = fresh_name(".md")
        path = plant_prose(ws, name, dense.text)
        measured = measure_path(ws, name)
        with guard_connect_observer() as observer:
            before = observer.n_connects
            starts = observer.child_starts
            _, nudge = fire_tool(
                ws,
                "Write",
                session_id=_sid(),
                file_path=str(path),
                content="payload",
                env_updates=observer.env_updates,
            )
            require_flagged_envelope(nudge, base=name, measured=measured)
            if observer.child_starts <= starts:
                raise AssertionError(
                    "observer did not see the detector child; "
                    "a zero connect count would be blind"
                )
            after = observer.n_connects
            print(f"[F05] hook connects={after - before}", flush=True)
            assert after == before


def test_hook_phrases_for_the_other_four_bands():
    """Clean is a ledger band, not a nudge. Mixed, heavy, and pervasive phrases stay on the nudge. Light tells stays on the score-40 test."""
    phrases = {
        "mixed": "reads with some AI tells",
        "heavy tells": "reads with heavy AI tells",
        "pervasive tells": "reads with pervasive AI tells",
    }
    with workspace() as ws:
        ws.write_mode_flag("full")
        clean, clean_report = pinned_score(secrets.randbelow(21))
        assert clean.score <= 20
        assert clean.band == "clean"
        name = fresh_name(".md")
        path = plant_prose(ws, name, clean.text)
        sid = _sid()
        _, nudge = fire_pinned(
            ws, clean_report, tool="Write", session_id=sid,
            file_path=str(path), content=clean.text,
        )
        assert nudge == ""
        row = row_around(show_text(ws, sid), name, [])
        assert clean.band in row
        for band in ("mixed", "heavy tells", "pervasive tells"):
            lo, hi = BAND_RANGES[band]
            measured, report = pinned_score(lo + secrets.randbelow(hi - lo + 1))
            assert phrase_for_band(band) == phrases[band]
            assert measured.band == band
            name = fresh_name(".md")
            path = plant_prose(ws, name, measured.text)
            _, nudge = fire_pinned(
                ws, report, tool="Write", session_id=_sid(),
                file_path=str(path), content="payload",
            )
            require_flagged_envelope(nudge, base=name, measured=measured)
            assert phrases[band] in nudge


def test_shell_command_write_is_not_seen():
    dense = prose_dense()
    with workspace() as ws:
        ws.write_mode_flag("full")
        shell_name = fresh_name(".md")
        shell_path = ws.path / shell_name
        completed = subprocess.run(
            ["sh", "-c", 'cat > "$1"', "sh", str(shell_path)],
            input=dense.text.encode("utf-8"),
            check=False,
        )
        assert completed.returncode == 0 and shell_path.is_file()
        sid = _sid()
        assert shell_name not in show_text(ws, sid)
        live = fresh_name(".md")
        live_path = plant_prose(ws, live, dense.text)
        measured = measure_path(ws, live)
        _, nudge = fire_tool(
            ws, "Write", session_id=sid, file_path=str(live_path), content="payload"
        )
        require_flagged_envelope(nudge, base=live, measured=measured)
        assert shell_name not in nudge
        shown = show_text(ws, sid)
        assert live in shown
        assert shell_name not in shown
