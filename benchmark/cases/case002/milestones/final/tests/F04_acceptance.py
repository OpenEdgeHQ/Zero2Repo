# feature: F04
"""Track and untrack pattern acceptance tests.

PRD: FP-04. Assertions stay at the PRD's precision: attributes append and
untrack of lfs-enable lines, listing of tracked vs excluded patterns, JSON
listing without pattern arguments, literal-filename vs glob, lockable /
not-lockable, dirty-index without rewriting attributes, dry-run vs verbose,
and outside-repository / missing-binary failure. Banner wording, JSON field
names, ``-text`` spelling, glob-escape strings, and exit-code numbers are
not pinned.
"""

from __future__ import annotations

import time

from _harness import token, workspace
from _helpers import (
    commit_ordinary_blob,
    compare_class_observation,
    extract_json_listing,
    gitattributes_bytes_or_missing,
    git_check_attr,
    json_walk_keys_and_strings,
    listing_visible,
    path_without_product_bin,
    porcelain_paths,
    configure_lfs_clean_filter,
    read_gitattributes,
    require_gitattributes_absent,
    require_invalid_unlike_success,
    require_lfs_enable_roles,
    require_lockable_set,
    require_lockable_unset,
    require_pattern_text_in_attributes,
    require_success,
    require_text_conversion_disabled,
    require_visible_contains,
    require_visible_omits,
    run_track,
    run_untrack,
    head_oid,
    write_excluded_filter_line,
)


def _glob(ext: str) -> str:
    return f"*.{ext}"


def _matching_rel(ext: str) -> str:
    return f"payload_{token()}.{ext}"


def test_track_appends_glob_text_not_expanded_filenames(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    matching = _matching_rel(ext)
    isolated_ws.write(matching, f"blob-{token()}\n")
    result = run_track(isolated_ws, [pattern])
    require_success(result)
    attrs = require_pattern_text_in_attributes(isolated_ws, pattern)
    print(f"pattern={pattern!r} matching={matching!r} attrs={attrs!r}")
    assert matching not in attrs, (
        "track wrote an expanded matching filename instead of the glob text"
    )
    require_lfs_enable_roles(isolated_ws, matching)


def test_track_multiple_patterns_in_one_invocation(isolated_ws):
    isolated_ws.init_repo()
    ext_a, ext_b = token(), token()
    pattern_a, pattern_b = _glob(ext_a), _glob(ext_b)
    rel_a, rel_b = _matching_rel(ext_a), _matching_rel(ext_b)
    isolated_ws.write(rel_a, "a\n")
    isolated_ws.write(rel_b, "b\n")
    result = run_track(isolated_ws, [pattern_a, pattern_b])
    require_success(result)
    attrs = read_gitattributes(isolated_ws)
    print(f"one-invocation attrs={attrs!r}")
    assert pattern_a in attrs and pattern_b in attrs
    require_lfs_enable_roles(isolated_ws, rel_a)
    require_lfs_enable_roles(isolated_ws, rel_b)


def test_later_track_appends_without_dropping_prior_lfs_glob(isolated_ws):
    isolated_ws.init_repo()
    ext_p, ext_q = token(), token()
    pattern_p, pattern_q = _glob(ext_p), _glob(ext_q)
    rel_p, rel_q = _matching_rel(ext_p), _matching_rel(ext_q)
    isolated_ws.write(rel_p, "p\n")
    isolated_ws.write(rel_q, "q\n")
    first = run_track(isolated_ws, [pattern_p])
    require_success(first)
    require_pattern_text_in_attributes(isolated_ws, pattern_p)
    second = run_track(isolated_ws, [pattern_q])
    require_success(second)
    attrs = read_gitattributes(isolated_ws)
    print(f"after-second-track attrs={attrs!r}")
    assert pattern_p in attrs, "later track dropped the earlier lfs glob"
    assert pattern_q in attrs
    require_lfs_enable_roles(isolated_ws, rel_p)
    require_lfs_enable_roles(isolated_ws, rel_q)


def test_track_writes_four_roles_filter_diff_merge_lfs_text_disabled(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    isolated_ws.write(rel, "roles\n")
    before_text = git_check_attr(isolated_ws, rel, ["text"])
    print(f"before-track text={before_text!r}")
    require_success(run_track(isolated_ws, [pattern]))
    values = require_lfs_enable_roles(isolated_ws, rel)
    text_disabled = require_text_conversion_disabled(isolated_ws, rel)
    require_lockable_unset(isolated_ws, rel)
    lockable = git_check_attr(isolated_ws, rel, ["lockable"])
    print(
        f"four-roles={values!r} text_disabled={text_disabled!r} "
        f"lockable={lockable!r}"
    )
    assert values["filter"] == "lfs", (
        f"filter role is {values['filter']!r}, not lfs"
    )
    assert values["diff"] == "lfs", (
        f"diff role is {values['diff']!r}, not lfs"
    )
    assert values["merge"] == "lfs", (
        f"merge role is {values['merge']!r}, not lfs"
    )
    assert before_text["text"] != text_disabled["text"], (
        "Git text conversion was already in the post-track state before "
        "the tracking line was written; the line did not disable conversion"
    )
    assert lockable["lockable"] in ("unspecified", "unset"), (
        "ordinary track marked the path lockable: "
        f"{lockable['lockable']!r}"
    )


def test_track_preserves_unrelated_attribute_lines(isolated_ws):
    isolated_ws.init_repo()
    note = f"note_{token()}"
    diff_driver = f"drv_{token()}"
    isolated_ws.write(
        ".gitattributes",
        f"# {note}\n*.txt diff={diff_driver}\n",
    )
    ext = token()
    pattern = _glob(ext)
    require_success(run_track(isolated_ws, [pattern]))
    attrs = read_gitattributes(isolated_ws)
    print(f"preserved attrs={attrs!r}")
    assert note in attrs, "track replaced the file and dropped the unrelated comment"
    assert diff_driver in attrs, "track dropped the unrelated non-lfs attribute line"
    assert pattern in attrs


def test_track_does_not_create_git_commit(isolated_ws):
    isolated_ws.init_repo()
    commit_ordinary_blob(isolated_ws, f"seed_{token()}.txt", "seed\n")
    before = head_oid(isolated_ws)
    ext = token()
    pattern = _glob(ext)
    require_success(run_track(isolated_ws, [pattern]))
    after = head_oid(isolated_ws)
    dirty = porcelain_paths(isolated_ws)
    print(f"head_before={before} head_after={after} porcelain={dirty!r}")
    assert after == before, "track created a Git commit"
    assert ".gitattributes" in dirty, (
        "track wrote attributes but git status does not show .gitattributes "
        "as an uncommitted change"
    )


def test_track_via_direct_binary_writes_attributes(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    isolated_ws.write(rel, "direct\n")
    result = run_track(isolated_ws, [pattern], via_git=False)
    require_success(result)
    attrs = require_pattern_text_in_attributes(isolated_ws, pattern)
    values = require_lfs_enable_roles(isolated_ws, rel)
    text_disabled = require_text_conversion_disabled(isolated_ws, rel)
    print(
        f"direct-binary roles={values!r} text_disabled={text_disabled!r} "
        f"attrs={attrs!r}"
    )
    assert pattern in attrs, (
        "direct-binary track did not record the given pattern text in attributes"
    )
    assert values["filter"] == "lfs", (
        f"direct-binary filter role is {values['filter']!r}, not lfs"
    )
    assert values["diff"] == "lfs", (
        f"direct-binary diff role is {values['diff']!r}, not lfs"
    )
    assert values["merge"] == "lfs", (
        f"direct-binary merge role is {values['merge']!r}, not lfs"
    )


def test_track_without_patterns_lists_tracked_pattern(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    before = run_track(isolated_ws, [])
    require_success(before)
    require_visible_omits(before, pattern)
    before_text = listing_visible(before)
    require_success(run_track(isolated_ws, [pattern]))
    listed = run_track(isolated_ws, [])
    require_success(listed)
    text = require_visible_contains(listed, pattern)
    print(f"before={before_text!r} listing={text!r}")
    assert pattern not in before_text, (
        "pre-track listing already named the not-yet-tracked pattern"
    )
    assert pattern in text, (
        "track-with-no-patterns listing did not name the tracked pattern"
    )


def test_default_listing_surfaces_excluded_pattern_distinct_from_tracked(isolated_ws):
    isolated_ws.init_repo()
    tracked_ext = token()
    tracked = _glob(tracked_ext)
    excluded_neg = f"*.exneg_{token()}"
    excluded_unset = f"*.exunset_{token()}"
    require_success(run_track(isolated_ws, [tracked]))
    write_excluded_filter_line(isolated_ws, excluded_neg, form="negate")
    write_excluded_filter_line(isolated_ws, excluded_unset, form="unset")
    listed = run_track(isolated_ws, [])
    require_success(listed)
    text = listing_visible(listed)
    print(f"default-listing={text!r}")
    assert tracked in text
    assert excluded_neg in text, "default listing omitted the negated excluded pattern"
    assert excluded_unset in text, "default listing omitted the unset excluded pattern"
    remainder = text.replace(tracked, "")
    assert excluded_neg in remainder and excluded_unset in remainder, (
        "excluded pattern text was only an echo of the tracked glob"
    )


def test_avoid_excluded_listing_omits_excluded_keeps_tracked(isolated_ws):
    isolated_ws.init_repo()
    tracked = _glob(token())
    excluded = f"*.ex_{token()}"
    require_success(run_track(isolated_ws, [tracked]))
    write_excluded_filter_line(isolated_ws, excluded, form="negate")
    default = run_track(isolated_ws, [])
    require_success(default)
    default_text = listing_visible(default)
    assert tracked in default_text and excluded in default_text, (
        "live baseline: default listing must include both tracked and excluded"
    )
    avoided = run_track(isolated_ws, ["--no-excluded"])
    require_success(avoided)
    avoided_text = listing_visible(avoided)
    print(f"default={default_text!r}\navoided={avoided_text!r}")
    assert tracked in avoided_text
    assert excluded not in avoided_text, (
        "avoid-excluded listing still named the excluded pattern"
    )
    assert default_text != avoided_text, (
        "avoid-excluded listing was not distinguishable from the default listing"
    )


def test_json_listing_is_machine_readable_and_names_tracked_pattern(isolated_ws):
    isolated_ws.init_repo()
    pattern = _glob(token())
    require_success(run_track(isolated_ws, [pattern]))
    result = run_track(isolated_ws, ["--json"])
    require_success(result)
    parsed = extract_json_listing(result)
    walked = json_walk_keys_and_strings(parsed)
    print(f"json_walked={walked!r} visible={listing_visible(result)!r}")
    assert any(pattern == item or pattern in item for item in walked), (
        "extracted JSON listing did not name the tracked pattern in a key "
        f"or string value: parsed={parsed!r}"
    )


def test_json_listing_combined_with_pattern_arguments_is_invalid(isolated_ws):
    isolated_ws.init_repo()
    tracked = _glob(token())
    require_success(run_track(isolated_ws, [tracked]))
    clean = run_track(isolated_ws, ["--json"])
    require_success(clean)
    extract_json_listing(clean)
    before = gitattributes_bytes_or_missing(isolated_ws)
    extra = _glob(token())
    dirty = run_track(isolated_ws, ["--json", extra])
    print(f"json+pattern exit={dirty.returncode} visible={listing_visible(dirty)!r}")
    require_invalid_unlike_success(clean, dirty)
    after = gitattributes_bytes_or_missing(isolated_ws)
    assert after == before, (
        "invalid json+pattern listing wrote attributes "
        f"before={before!r} after={after!r}"
    )


def test_filename_mode_escapes_glob_metacharacters_vs_glob_track():
    suffix = token()
    exact = f"star*{suffix}.bin"
    decoy = f"starX{suffix}.bin"
    argv = [exact]
    with workspace() as glob_ws:
        glob_ws.init_repo()
        glob_ws.write(exact, "exact-glob\n")
        glob_ws.write(decoy, "decoy-glob\n")
        require_success(run_track(glob_ws, argv))
        glob_decoy = git_check_attr(glob_ws, decoy, ["filter"])["filter"]
        glob_exact = git_check_attr(glob_ws, exact, ["filter"])["filter"]
    with workspace() as literal_ws:
        literal_ws.init_repo()
        literal_ws.write(exact, "exact-literal\n")
        literal_ws.write(decoy, "decoy-literal\n")
        require_success(run_track(literal_ws, ["--filename", *argv]))
        lit_decoy = git_check_attr(literal_ws, decoy, ["filter"])["filter"]
        lit_exact = git_check_attr(literal_ws, exact, ["filter"])["filter"]
    print(
        f"glob decoy={glob_decoy!r} exact={glob_exact!r}; "
        f"literal decoy={lit_decoy!r} exact={lit_exact!r}"
    )
    assert glob_decoy == "lfs", (
        "glob track did not treat the decoy as matching (live baseline)"
    )
    assert lit_decoy != "lfs", (
        "filename mode still applied the glob to the decoy path"
    )
    assert lit_exact == "lfs", (
        "filename mode did not enable lfs on the exact literal filename"
    )


def test_lockable_marks_paths_in_attributes():
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    with workspace() as ordinary:
        ordinary.init_repo()
        ordinary.write(rel, "ord\n")
        require_success(run_track(ordinary, [pattern]))
        require_lfs_enable_roles(ordinary, rel)
        require_lockable_unset(ordinary, rel)
        ordinary_lockable = git_check_attr(ordinary, rel, ["lockable"])
        assert ordinary_lockable["lockable"] in ("unspecified", "unset"), (
            "ordinary track marked the path lockable without --lockable: "
            f"{ordinary_lockable['lockable']!r}"
        )
    with workspace() as lockable:
        lockable.init_repo()
        lockable.write(rel, "lock\n")
        require_success(run_track(lockable, ["--lockable", pattern]))
        roles = require_lfs_enable_roles(lockable, rel)
        lockable_vals = require_lockable_set(lockable, rel)
        attrs = read_gitattributes(lockable)
        print(f"lockable attrs={attrs!r} roles={roles!r}")
        assert lockable_vals["lockable"] == "set", (
            "lockable track did not mark the path lockable in attributes: "
            f"{lockable_vals['lockable']!r}"
        )
        assert roles["filter"] == "lfs", (
            "lockable track dropped the lfs filter role: "
            f"{roles['filter']!r}"
        )


def test_not_lockable_clears_lockable_keeps_lfs_filter(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    isolated_ws.write(rel, "nl\n")
    require_success(run_track(isolated_ws, ["--lockable", pattern]))
    require_lockable_set(isolated_ws, rel)
    require_success(run_track(isolated_ws, ["--not-lockable", pattern]))
    require_lfs_enable_roles(isolated_ws, rel)
    require_lockable_unset(isolated_ws, rel)
    print(f"after-not-lockable={git_check_attr(isolated_ws, rel, ['filter', 'lockable'])!r}")


def test_no_modify_attrs_dirties_index_without_rewriting_attributes():
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    payload = f"ordinary-{token()}\n"
    with workspace() as writer:
        writer.init_repo()
        require_gitattributes_absent(writer)
        require_success(run_track(writer, [pattern]))
        written_attrs = gitattributes_bytes_or_missing(writer)
        assert written_attrs is not None
        require_pattern_text_in_attributes(writer, pattern)
        print(f"ordinary-track wrote attrs for {pattern!r}")
    with workspace() as dirtying:
        dirtying.init_repo()
        dirtying.write(rel, payload)
        added_blob = dirtying.git(["add", "--", rel])
        assert added_blob.returncode == 0, added_blob.stderr_text
        time.sleep(1.1)
        committed_blob = dirtying.git(["commit", "-m", f"add {rel}"])
        assert committed_blob.returncode == 0, committed_blob.stderr_text
        configure_lfs_clean_filter(dirtying)
        assert porcelain_paths(dirtying) == [], (
            "worktree must be clean after committing the ordinary blob"
        )
        # Setup fixture: enable-line bytes produced by a real track in the
        # contrast workspace. Not an oracle that this arm's track wrote them,
        # and not a hand-typed filter=lfs template.
        dirtying.write(".gitattributes", written_attrs)
        added_attrs = dirtying.git(["add", "--", ".gitattributes"])
        assert added_attrs.returncode == 0, added_attrs.stderr_text
        committed_attrs = dirtying.git(["commit", "-m", "attrs"])
        assert committed_attrs.returncode == 0, committed_attrs.stderr_text
        before_attrs = gitattributes_bytes_or_missing(dirtying)
        assert before_attrs == written_attrs
        before_porcelain = porcelain_paths(dirtying)
        assert before_porcelain == [], (
            "live baseline must be a clean worktree before --no-modify-attrs, "
            f"got {before_porcelain!r}"
        )
        time.sleep(1.1)
        result = run_track(dirtying, ["--no-modify-attrs", pattern])
        require_success(result)
        after_attrs = gitattributes_bytes_or_missing(dirtying)
        after_porcelain = porcelain_paths(dirtying)
        print(
            f"before_attrs={before_attrs!r} after_attrs={after_attrs!r} "
            f"porcelain={after_porcelain!r}"
        )
        assert after_attrs == before_attrs, (
            "--no-modify-attrs rewrote attributes"
        )
        assert rel in after_porcelain, (
            "--no-modify-attrs did not dirty the previously Git-tracked file"
        )


def test_dry_run_reports_intended_change_without_mutating_attributes():
    ext = token()
    pattern = _glob(ext)
    with workspace() as writer:
        writer.init_repo()
        require_gitattributes_absent(writer)
        require_success(run_track(writer, [pattern]))
        require_pattern_text_in_attributes(writer, pattern)
    with workspace() as dry:
        dry.init_repo()
        require_gitattributes_absent(dry)
        result = run_track(dry, ["--dry-run", pattern])
        require_success(result)
        require_gitattributes_absent(dry)
        visible = require_visible_contains(result, pattern)
        after = gitattributes_bytes_or_missing(dry)
        print(f"dry-run visible={visible!r} after={after!r}")
        assert after is None, (
            "dry-run mutated attributes on disk: "
            f"{after!r}"
        )
        assert pattern in visible, (
            "dry-run did not report the intended pattern change"
        )


def test_verbose_still_writes_attributes_unlike_dry_run():
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    with workspace() as dry:
        dry.init_repo()
        dry.write(rel, "dry\n")
        require_success(run_track(dry, ["--dry-run", pattern]))
        require_gitattributes_absent(dry)
        assert gitattributes_bytes_or_missing(dry) is None, (
            "dry-run arm wrote attributes; verbose contrast has no live baseline"
        )
    with workspace() as verbose:
        verbose.init_repo()
        verbose.write(rel, "verbose\n")
        require_success(run_track(verbose, ["--verbose", pattern]))
        attrs = require_pattern_text_in_attributes(verbose, pattern)
        values = require_lfs_enable_roles(verbose, rel)
        print(f"verbose attrs={attrs!r} roles={values!r}")
        assert pattern in attrs, (
            "verbose track did not write the pattern into attributes "
            "(unlike dry-run, verbose must still mutate)"
        )
        assert values["filter"] == "lfs", (
            f"verbose track filter role is {values['filter']!r}, not lfs"
        )
        assert values["diff"] == "lfs", (
            f"verbose track diff role is {values['diff']!r}, not lfs"
        )
        assert values["merge"] == "lfs", (
            f"verbose track merge role is {values['merge']!r}, not lfs"
        )


def test_verbose_report_differs_when_matching_git_tracked_files_exist():
    ext = token()
    pattern = _glob(ext)
    rel = f"touched_{token()}.{ext}"
    payload = f"tracked-{token()}\n"
    with workspace() as quiet:
        quiet.init_repo()
        commit_ordinary_blob(quiet, rel, payload)
        quiet_run = run_track(quiet, [pattern])
        require_success(quiet_run)
        require_lfs_enable_roles(quiet, rel)
        quiet_text = listing_visible(quiet_run)
    with workspace() as verbose:
        verbose.init_repo()
        commit_ordinary_blob(verbose, rel, payload)
        verbose_run = run_track(verbose, ["--verbose", pattern])
        require_success(verbose_run)
        require_lfs_enable_roles(verbose, rel)
        verbose_text = listing_visible(verbose_run)
    print(f"quiet={quiet_text!r}\nverbose={verbose_text!r}")
    assert rel in verbose_text, (
        "verbose report did not name the matching previously Git-tracked file"
    )
    quiet_obs = compare_class_observation(
        quiet_run,
        strip_tokens=[
            str(quiet.path),
            str(quiet.path.resolve()),
            str(quiet.home),
        ],
    )
    verbose_obs = compare_class_observation(
        verbose_run,
        strip_tokens=[
            str(verbose.path),
            str(verbose.path.resolve()),
            str(verbose.home),
        ],
    )
    print(f"quiet_obs={quiet_obs!r} verbose_obs={verbose_obs!r}")
    assert quiet_obs != verbose_obs, (
        "verbose report was not distinguishable from the same track without "
        "verbose after stripping workspace-path covariates"
    )


def test_untrack_removes_matching_lfs_enable_lines_keeps_other_tracked(isolated_ws):
    isolated_ws.init_repo()
    ext_p, ext_q = token(), token()
    pattern_p, pattern_q = _glob(ext_p), _glob(ext_q)
    rel_p, rel_q = _matching_rel(ext_p), _matching_rel(ext_q)
    isolated_ws.write(rel_p, "p\n")
    isolated_ws.write(rel_q, "q\n")
    require_success(run_track(isolated_ws, [pattern_p, pattern_q]))
    require_lfs_enable_roles(isolated_ws, rel_p)
    require_lfs_enable_roles(isolated_ws, rel_q)
    require_success(run_untrack(isolated_ws, [pattern_p]))
    filter_p = git_check_attr(isolated_ws, rel_p, ["filter"])["filter"]
    print(f"after untrack P filter={filter_p!r}")
    assert filter_p != "lfs", "untrack left P enabled for the lfs filter"
    require_lfs_enable_roles(isolated_ws, rel_q)
    listed = run_track(isolated_ws, [])
    require_success(listed)
    text = listing_visible(listed)
    assert pattern_p not in text, "listing still named the untracked pattern"
    assert pattern_q in text


def test_untrack_does_not_write_excluded_pattern_lines(isolated_ws):
    isolated_ws.init_repo()
    note = f"keep_{token()}"
    isolated_ws.write(".gitattributes", f"# {note}\n")
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    isolated_ws.write(rel, "x\n")
    require_success(run_track(isolated_ws, [pattern]))
    require_lfs_enable_roles(isolated_ws, rel)
    require_success(run_untrack(isolated_ws, [pattern]))
    attrs = read_gitattributes(isolated_ws)
    print(f"after-untrack attrs={attrs!r}")
    assert note in attrs, (
        "untrack dropped the unrelated non-lfs line"
    )
    filter_val = git_check_attr(isolated_ws, rel, ["filter"])["filter"]
    print(f"after-untrack filter={filter_val!r}")
    assert filter_val != "lfs", (
        "untrack left the matching lfs-enable line in place"
    )
    for line in attrs.splitlines():
        fields = line.split()
        if pattern not in line:
            continue
        assert "-filter" not in fields, (
            "untrack wrote a Git negation excluded-filter line"
        )
        assert "filter=" not in fields, (
            "untrack wrote a Git unset excluded-filter line"
        )
    excluded = f"*.seen_{token()}"
    write_excluded_filter_line(isolated_ws, excluded, form="negate")
    listed = run_track(isolated_ws, [])
    require_success(listed)
    require_visible_contains(listed, excluded)


def test_untrack_does_not_create_git_commit(isolated_ws):
    isolated_ws.init_repo()
    ext = token()
    pattern = _glob(ext)
    rel = _matching_rel(ext)
    isolated_ws.write(rel, "x\n")
    require_success(run_track(isolated_ws, [pattern]))
    require_lfs_enable_roles(isolated_ws, rel)
    added = isolated_ws.git(["add", "--", ".gitattributes"])
    assert added.returncode == 0, (
        f"git add .gitattributes failed (exit {added.returncode}): "
        f"{added.stderr_text}"
    )
    committed = isolated_ws.git(["commit", "-m", f"attrs {pattern}"])
    assert committed.returncode == 0, (
        f"git commit attributes failed (exit {committed.returncode}): "
        f"{committed.stderr_text}"
    )
    before = head_oid(isolated_ws)
    require_success(run_untrack(isolated_ws, [pattern]))
    after = head_oid(isolated_ws)
    filter_val = git_check_attr(isolated_ws, rel, ["filter"])["filter"]
    dirty = porcelain_paths(isolated_ws)
    print(
        f"untrack head_before={before} head_after={after} "
        f"filter={filter_val!r} porcelain={dirty!r}"
    )
    assert after == before, "untrack created a Git commit"
    assert filter_val != "lfs", (
        "untrack did not remove the matching lfs-enable line"
    )
    assert ".gitattributes" in dirty, (
        "untrack left no uncommitted attribute change; HEAD-unchanged "
        "alone is not proof that untrack mutated attributes"
    )


def test_track_outside_repository_fails():
    pattern = _glob(token())
    with workspace() as inside:
        inside.init_repo()
        clean = run_track(inside, [pattern])
        require_success(clean)
        require_pattern_text_in_attributes(inside, pattern)
    with workspace() as outside:
        dirty = run_track(outside, [pattern])
        print(
            f"outside-track exit={dirty.returncode} "
            f"visible={listing_visible(dirty)!r}"
        )
        assert dirty.returncode != 0, (
            "track outside a repository succeeded; "
            f"stdout={dirty.stdout_text!r} stderr={dirty.stderr_text!r}"
        )
        assert (dirty.returncode, dirty.stdout, dirty.stderr) != (
            clean.returncode,
            clean.stdout,
            clean.stderr,
        ), "outside-repo track was not distinguishable from in-repo success"
        require_gitattributes_absent(outside)


def test_untrack_outside_repository_fails():
    pattern = _glob(token())
    with workspace() as inside:
        inside.init_repo()
        require_success(run_track(inside, [pattern]))
        clean = run_untrack(inside, [pattern])
        require_success(clean)
    with workspace() as outside:
        dirty = run_untrack(outside, [pattern])
        print(
            f"outside-untrack exit={dirty.returncode} "
            f"visible={listing_visible(dirty)!r}"
        )
        assert dirty.returncode != 0, (
            "untrack outside a repository succeeded; "
            f"stdout={dirty.stdout_text!r} stderr={dirty.stderr_text!r}"
        )
        assert (dirty.returncode, dirty.stdout, dirty.stderr) != (
            clean.returncode,
            clean.stdout,
            clean.stderr,
        ), "outside-repo untrack was not distinguishable from in-repo success"
        require_gitattributes_absent(outside)


def test_track_fails_when_binary_removed_from_path(isolated_ws, product_binary):
    isolated_ws.init_repo()
    pattern = _glob(token())
    present = run_track(isolated_ws, [pattern])
    require_success(present)
    require_pattern_text_in_attributes(isolated_ws, pattern)
    hidden_path = path_without_product_bin(isolated_ws.env)
    print(f"product_binary={product_binary} hidden_path={hidden_path!r}")
    missing = isolated_ws.invoke_via_git(
        ["track", _glob(token())],
        env_updates={"PATH": hidden_path},
    )
    print(
        f"absent-binary exit={missing.returncode} "
        f"stderr={missing.stderr_text!r}"
    )
    assert missing.returncode != 0, (
        "git orbulk track succeeded after the product binary was removed from PATH"
    )
