# feature: F14
"""History-migration acceptance tests (migrate info / import / export).

PRD: FP-14. Oracles are Git history blobs (pointer versus ordinary
bytes), local object-store occupancy, attributes on rewritten commits
(tracking line versus excluded-pattern filter form), local versus
remote-tracking ref SHAs, and process success versus non-success.
Message wording, column order, unit spelling, exit-code numbers, and
flag spellings in output are not pinned.
"""

from __future__ import annotations

import os

from _harness import reserve_loopback_port, token, workspace
from _helpers import (
    add_git_remote,
    attrs_blob_at,
    blob_at,
    blob_size_at,
    clean_bytes,
    commit_ordinary_blob,
    commit_tracked_payload,
    decimal_integers,
    default_lfs_store_root,
    disable_lock_verification,
    git_add_unfiltered,
    head_oid,
    info_visible,
    init_bare_git_remote,
    install_local_keeping_process,
    path_without_product_bin,
    pointer_from_clean_stdout,
    pointer_matches_digest_and_size,
    read_ref,
    remove_stored_object,
    require_attrs_not_executable,
    require_excluded_pattern_in_attrs,
    require_git_config_set,
    require_invalid_unlike_success,
    require_lfs_enable_roles,
    require_object_absent,
    require_object_bytes,
    require_put_of,
    require_ref_at,
    require_success,
    require_tracking_pattern_in_attrs,
    require_tree_blob_bytes,
    require_tree_pointer,
    run_migrate,
    set_lfs_endpoint,
    sha256_hex,
    storing_batch_server,
    track_pattern,
    type_report,
    type_report_remainder,
    write_pointer_placeholders_from_index,
)


def _git_ok(ws, argv, **kwargs):
    result = ws.git(argv, **kwargs)
    assert result.returncode == 0, (
        f"git {argv!r} failed (exit {result.returncode}): {result.stderr_text}"
    )
    return result


def _rev_parse(ws, spec: str) -> str:
    result = ws.git(["rev-parse", spec])
    assert result.returncode == 0, (
        f"git rev-parse {spec!r} failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    sha = result.stdout_text.strip()
    assert sha, f"git rev-parse {spec!r} produced no sha"
    return sha


def _letter_payload(ch: str, n: int) -> bytes:
    assert ch.isalpha() and len(ch) == 1
    assert n > 0
    return (ch * n).encode("ascii")


def _attrs_text(ws, commit: str) -> str:
    raw = attrs_blob_at(ws, commit)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            f"attributes blob at {commit} is not UTF-8: {exc}"
        ) from exc


def _info(ws, extra=None, *, via_git: bool = True, env_updates=None):
    argv = ["info", *(extra or ())]
    return run_migrate(
        ws, argv, via_git=via_git, env_updates=env_updates
    )


def _import(ws, extra):
    return run_migrate(ws, ["import", "--yes", *extra])


def _export(ws, extra):
    return run_migrate(ws, ["export", "--yes", *extra])


def _unreachable_git_remote(ws) -> str:
    port = reserve_loopback_port()
    url = f"http://127.0.0.1:{port}/{token()}"
    add_git_remote(ws, "origin", url)
    return url


def _setup_not_pointer(ws, spec: str, data: bytes) -> None:
    observed = blob_at(ws, spec)
    assert observed == data, (
        f"fixture {spec} is not the planted ordinary blob "
        f"(got {len(observed)} bytes, expected {len(data)})"
    )
    assert not pointer_matches_digest_and_size(
        observed, digest=sha256_hex(data), size=len(data)
    ), (
        f"fixture {spec} was already a pointer before migrate"
    )


# ---------------------------------------------------------------------------
# A. Info: count and size fields separately identifiable
# ---------------------------------------------------------------------------


def test_info_count_and_size_fields_separable():
    """Same-type size-only change moves size not count; count change moves the stable integer."""
    ext = token()
    rel = f"file_{token()}.{ext}"
    rel_b = f"more_{token()}.{ext}"
    data_small = _letter_payload("n", 23)
    data_large = _letter_payload("m", 47)
    data_extra = _letter_payload("p", 31)
    strip_size = [ext, rel, data_small.decode("ascii"), data_large.decode("ascii")]

    with workspace() as ws_a:
        ws_a.init_repo()
        commit_ordinary_blob(ws_a, rel, data_small)
        _setup_not_pointer(ws_a, f"HEAD:{rel}", data_small)
        info_a = _info(ws_a)
        visible_a = info_visible(info_a)
        report_a = type_report(visible_a, ext)
        rem_a = type_report_remainder(report_a, strip_size)
        print(f"size-only A report={report_a!r} rem={rem_a!r}")

    with workspace() as ws_b:
        ws_b.init_repo()
        commit_ordinary_blob(ws_b, rel, data_large)
        _setup_not_pointer(ws_b, f"HEAD:{rel}", data_large)
        info_b = _info(ws_b)
        visible_b = info_visible(info_b)
        report_b = type_report(visible_b, ext)
        rem_b = type_report_remainder(report_b, strip_size)
        print(f"size-only B report={report_b!r} rem={rem_b!r}")
        direct = _info(ws_b, via_git=False)
        require_success(direct)
        type_report(info_visible(direct), ext)

    assert rem_a != rem_b, (
        "size-only type reports were equal after stripping extension, "
        f"path, and payload: {rem_a!r}"
    )
    ints_a = set(decimal_integers(rem_a))
    ints_b = set(decimal_integers(rem_b))
    stable = ints_a & ints_b
    print(f"size-only integers A={ints_a!r} B={ints_b!r} S={stable!r}")
    assert stable, (
        "size-only reports had no shared integer after stripping; "
        "no count figure stayed put while size moved"
    )

    strip_count = [
        ext,
        rel,
        rel_b,
        data_small.decode("ascii"),
        data_extra.decode("ascii"),
    ]
    with workspace() as ws_one:
        ws_one.init_repo()
        commit_ordinary_blob(ws_one, rel, data_small)
        info_one = _info(ws_one)
        rem_one = type_report_remainder(
            type_report(info_visible(info_one), ext), strip_count
        )
        print(f"count-one rem={rem_one!r}")

    with workspace() as ws_two:
        ws_two.init_repo()
        commit_ordinary_blob(ws_two, rel, data_small)
        commit_ordinary_blob(ws_two, rel_b, data_extra)
        info_two = _info(ws_two)
        rem_two = type_report_remainder(
            type_report(info_visible(info_two), ext), strip_count
        )
        print(f"count-two rem={rem_two!r}")

    assert rem_one != rem_two, (
        "count-change type reports were equal after stripping: "
        f"{rem_one!r}"
    )
    count_inter = set(decimal_integers(rem_one)) & set(decimal_integers(rem_two))
    print(f"count-arm intersection={count_inter!r}")
    assert not stable.issubset(count_inter), (
        "the integer that stayed put under a size-only change also stayed "
        f"put when the file count changed: S={stable!r} count∩={count_inter!r}"
    )


# ---------------------------------------------------------------------------
# B. Info: follow / ignore / no-follow pointer modes
# ---------------------------------------------------------------------------


def test_info_pointer_modes_follow_ignore_nofollow():
    """Follow reports referenced size; ignore omits pointers; no-follow uses pointer blob size."""
    ext_a = token()
    ext_b = token()
    rel_a = f"ord_{token()}.{ext_a}"
    rel_b = f"ptr_{token()}.{ext_b}"
    data_a = _letter_payload("v", 19)
    data_b = _letter_payload("w", 401)
    digest_b = sha256_hex(data_b)

    with workspace() as ws:
        ws.init_repo()
        commit_ordinary_blob(ws, rel_a, data_a)
        cleaned = clean_bytes(ws, data_b)
        pointer = pointer_from_clean_stdout(
            cleaned, digest=digest_b, size=len(data_b)
        )
        ws.write(rel_b, pointer)
        git_add_unfiltered(ws, rel_b)
        _git_ok(ws, ["commit", "-m", "pointer b"])
        _setup_not_pointer(ws, f"HEAD:{rel_a}", data_a)
        require_tree_pointer(ws, "HEAD", rel_b, digest_b, len(data_b))
        ptr_size = blob_size_at(ws, f"HEAD:{rel_b}")
        print(
            f"planted A size={len(data_a)} B ref={len(data_b)} "
            f"pointer-blob={ptr_size}"
        )
        assert len(data_b) not in (len(data_a), ptr_size)

        strip = [
            ext_a,
            ext_b,
            rel_a,
            rel_b,
            data_a.decode("ascii"),
            data_b.decode("ascii"),
            digest_b,
        ]

        def _mode_obs(extra):
            result = _info(ws, extra)
            visible = info_visible(result)
            named_a = type_report(visible, ext_a)
            rem = type_report_remainder(visible, strip)
            ints = set(decimal_integers(rem))
            return result, visible, named_a, rem, ints

        default = _mode_obs([])
        follow = _mode_obs(["--pointers=follow"])
        ignore = _mode_obs(["--pointers=ignore"])
        nofollow = _mode_obs(["--pointers=no-follow"])

        for label, obs in (("default", default), ("follow", follow)):
            _result, visible, _named, rem, ints = obs
            print(f"{label} rem={rem!r} ints={ints!r}")
            assert len(data_b) in ints, (
                f"{label} did not report the referenced object size "
                f"{len(data_b)} after stripping covariates: {rem!r}"
            )
            assert rem != ignore[3], (
                f"{label} was not distinguishable from ignore after stripping"
            )
            assert rem != nofollow[3], (
                f"{label} was not distinguishable from no-follow after stripping"
            )

        _ig, ig_visible, _ig_a, ig_rem, ig_ints = ignore
        print(f"ignore rem={ig_rem!r} ints={ig_ints!r}")
        assert ext_b not in ig_visible, (
            "ignore still named pointer type B: "
            f"{ig_visible!r}"
        )
        assert len(data_b) not in ig_ints, (
            "ignore still reported the referenced object size"
        )

        _nf, nf_visible, _nf_a, nf_rem, nf_ints = nofollow
        nf_report = type_report(nf_visible, ext_b)
        nf_type_ints = set(decimal_integers(nf_report))
        print(
            f"no-follow B report={nf_report!r} type_ints={nf_type_ints!r} "
            f"ptr_size={ptr_size}"
        )
        assert ptr_size in nf_type_ints, (
            "no-follow type B integers did not include the independent "
            f"pointer-blob size {ptr_size}: {nf_report!r}"
        )
        assert len(data_b) not in nf_type_ints, (
            "no-follow type B still reported the referenced object size "
            f"{len(data_b)}: {nf_report!r}"
        )
        assert ext_b in nf_visible, (
            "no-follow did not name pointer type B"
        )


# ---------------------------------------------------------------------------
# C. Info: selected ref set
# ---------------------------------------------------------------------------


def test_info_selected_ref_set():
    """Default info names the current branch type; include-ref names the other."""
    ext_main = token()
    ext_feat = token()
    rel_main = f"onlym_{token()}.{ext_main}"
    rel_feat = f"onlyf_{token()}.{ext_feat}"
    feat = f"feat_{token()}"
    with workspace() as ws:
        ws.init_repo()
        commit_ordinary_blob(ws, rel_main, _letter_payload("a", 21))
        _git_ok(ws, ["checkout", "-b", feat])
        commit_ordinary_blob(ws, rel_feat, _letter_payload("b", 25))
        _git_ok(ws, ["checkout", "main"])
        default = info_visible(_info(ws))
        print(f"default info={default!r}")
        type_report(default, ext_main)
        assert ext_feat not in default, (
            "default info on main named the other branch's unique extension"
        )
        other = info_visible(_info(ws, [f"--include-ref={feat}"]))
        print(f"include-ref info={other!r}")
        type_report(other, ext_feat)
        everything = info_visible(_info(ws, ["--everything"]))
        print(f"everything info={everything!r}")
        type_report(everything, ext_feat)


# ---------------------------------------------------------------------------
# D. Import + include glob
# ---------------------------------------------------------------------------


def test_import_rewrites_blobs_and_tracking_on_all_rewritten_commits():
    """Import rewrites matching blobs on every rewritten commit, not unmatched paths."""
    ext = token()
    pattern = f"*.{ext}"
    unmatched = f"u_{token()}.dat"
    matched = f"m_{token()}.{ext}"
    u_data = _letter_payload("u", 27)
    m_data = _letter_payload("k", 33)
    digest = sha256_hex(m_data)
    with workspace() as ws:
        ws.init_repo()
        install_local_keeping_process(ws)
        commit_ordinary_blob(ws, unmatched, u_data)
        old_c0 = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{unmatched}", u_data)
        commit_ordinary_blob(ws, matched, m_data)
        old_c1 = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{matched}", m_data)
        _setup_not_pointer(ws, f"HEAD:{unmatched}", u_data)
        result = _import(ws, [f"--include={pattern}"])
        print(f"import exit={result.returncode} old_c0={old_c0} old_c1={old_c1}")
        require_success(result)
        new_head = head_oid(ws)
        assert new_head != old_c1, (
            "import left HEAD unchanged; history was not rewritten"
        )
        new_c0 = _rev_parse(ws, "HEAD~1")
        require_tree_pointer(ws, new_head, matched, digest, len(m_data))
        require_object_bytes(default_lfs_store_root(ws), digest, m_data)
        require_tree_blob_bytes(ws, new_head, unmatched, u_data)
        require_tree_blob_bytes(ws, new_c0, unmatched, u_data)
        require_tracking_pattern_in_attrs(_attrs_text(ws, new_head), pattern)
        require_tracking_pattern_in_attrs(_attrs_text(ws, new_c0), pattern)
        require_attrs_not_executable(ws, new_head)
        require_attrs_not_executable(ws, new_c0)
        require_lfs_enable_roles(ws, matched)


# ---------------------------------------------------------------------------
# E. Import fixup
# ---------------------------------------------------------------------------


def test_import_fixup_converts_only_already_attributed_files():
    """Fixup converts attributed blobs only; a live include baseline converts the other type."""
    ext = token()
    other = token()
    pattern = f"*.{ext}"
    rel = f"need_{token()}.{ext}"
    rel_other = f"skip_{token()}.{other}"
    data = _letter_payload("f", 29)
    data_other = _letter_payload("g", 35)
    digest = sha256_hex(data)

    def _plant(ws):
        ws.init_repo()
        install_local_keeping_process(ws)
        track_pattern(ws, pattern)
        _git_ok(ws, ["add", "--", ".gitattributes"])
        _git_ok(ws, ["commit", "-m", "attrs"])
        ws.write(rel, data)
        git_add_unfiltered(ws, rel)
        ws.write(rel_other, data_other)
        _git_ok(ws, ["add", "--", rel_other])
        _git_ok(ws, ["commit", "-m", "blobs"])
        _setup_not_pointer(ws, f"HEAD:{rel}", data)
        _setup_not_pointer(ws, f"HEAD:{rel_other}", data_other)
        return head_oid(ws)

    with workspace() as live:
        _plant(live)
        baseline = _import(live, [f"--include=*.{other}"])
        print(f"fixup live-include exit={baseline.returncode}")
        require_success(baseline)
        require_tree_pointer(
            live, "HEAD", rel_other, sha256_hex(data_other), len(data_other)
        )

    with workspace() as ws:
        old = _plant(ws)
        result = _import(ws, ["--fixup"])
        print(f"fixup exit={result.returncode}")
        require_success(result)
        new_head = head_oid(ws)
        assert new_head != old
        require_tree_pointer(ws, new_head, rel, digest, len(data))
        require_object_bytes(default_lfs_store_root(ws), digest, data)
        require_tree_blob_bytes(ws, new_head, rel_other, data_other)
        attrs = _attrs_text(ws, new_head)
        require_tracking_pattern_in_attrs(attrs, pattern)
        other_pat = f"*.{other}"
        tracked_other = True
        try:
            require_tracking_pattern_in_attrs(attrs, other_pat)
        except AssertionError:
            tracked_other = False
        assert not tracked_other, (
            f"fixup added a tracking line for {other_pat!r}: {attrs!r}"
        )


# ---------------------------------------------------------------------------
# F. No-rewrite import
# ---------------------------------------------------------------------------


def test_import_no_rewrite_new_commit_ignores_rewrite_options():
    """No-rewrite adds a commit for listed files and ignores include / everything."""
    ext = token()
    pattern = f"*.{ext}"
    keep = f"keep_{token()}.{ext}"
    other = f"other_{token()}.{ext}"
    keep_data = _letter_payload("k", 37)
    other_data = _letter_payload("o", 41)
    feat = f"feat_{token()}"
    with workspace() as ws:
        ws.init_repo()
        install_local_keeping_process(ws)
        track_pattern(ws, pattern)
        _git_ok(ws, ["add", "--", ".gitattributes"])
        _git_ok(ws, ["commit", "-m", "attrs"])
        ws.write(keep, keep_data)
        git_add_unfiltered(ws, keep)
        ws.write(other, other_data)
        git_add_unfiltered(ws, other)
        _git_ok(ws, ["commit", "-m", "blobs"])
        _git_ok(ws, ["branch", feat])
        feat_before = read_ref(ws, feat)
        old = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{keep}", keep_data)
        _setup_not_pointer(ws, f"HEAD:{other}", other_data)
        result = _import(
            ws,
            [
                "--no-rewrite",
                f"--include={pattern}",
                "--everything",
                f"--include-ref={feat}",
                keep,
            ],
        )
        print(f"no-rewrite exit={result.returncode} old={old}")
        require_success(result)
        new_head = head_oid(ws)
        assert new_head != old
        assert _rev_parse(ws, "HEAD~1") == old, (
            "no-rewrite rewrote prior history; parent is not the old HEAD"
        )
        require_tree_blob_bytes(ws, old, keep, keep_data)
        require_tree_pointer(
            ws, new_head, keep, sha256_hex(keep_data), len(keep_data)
        )
        require_object_bytes(
            default_lfs_store_root(ws), sha256_hex(keep_data), keep_data
        )
        require_tree_blob_bytes(ws, new_head, other, other_data)
        require_ref_at(ws, feat, feat_before)


# ---------------------------------------------------------------------------
# G. Export
# ---------------------------------------------------------------------------


def test_export_restores_blobs_and_writes_excluded_patterns():
    """Export restores included pointers on rewritten history, including empty ancestors."""
    ext = token()
    other = token()
    pattern = f"*.{ext}"
    unmatched = f"u_{token()}.dat"
    rel = f"ex_{token()}.{ext}"
    rel_other = f"keep_{token()}.{other}"
    u_data = _letter_payload("u", 22)
    data = _letter_payload("e", 39)
    data_other = _letter_payload("t", 43)
    with workspace() as ws:
        ws.init_repo()
        install_local_keeping_process(ws)
        commit_ordinary_blob(ws, unmatched, u_data)
        old_c0 = head_oid(ws)
        track_pattern(ws, pattern)
        track_pattern(ws, f"*.{other}")
        ws.write(rel, data)
        ws.write(rel_other, data_other)
        digest = sha256_hex(data)
        digest_other = sha256_hex(data_other)
        _git_ok(ws, ["add", "--", rel, rel_other, ".gitattributes"])
        _git_ok(ws, ["commit", "-m", "pointers"])
        old_c1 = head_oid(ws)
        require_tree_pointer(ws, old_c1, rel, digest, len(data))
        require_tree_pointer(
            ws, old_c1, rel_other, digest_other, len(data_other)
        )
        result = _export(ws, [f"--include={pattern}"])
        print(f"export exit={result.returncode} old_c1={old_c1}")
        require_success(result)
        new_head = head_oid(ws)
        assert new_head != old_c1
        parent = _rev_parse(ws, "HEAD~1")
        assert parent != old_c1, (
            "export stacked a new commit on the unre-written pointer commit"
        )
        require_tree_blob_bytes(ws, new_head, rel, data)
        require_tree_pointer(
            ws, new_head, rel_other, digest_other, len(data_other)
        )
        require_tree_blob_bytes(ws, new_head, unmatched, u_data)
        require_tree_blob_bytes(ws, parent, unmatched, u_data)
        attrs_head = _attrs_text(ws, new_head)
        attrs_c0 = _attrs_text(ws, parent)
        require_excluded_pattern_in_attrs(attrs_head, pattern)
        require_excluded_pattern_in_attrs(attrs_c0, pattern)
        require_attrs_not_executable(ws, new_head)
        print(f"export parent={parent} old_c0={old_c0}")


# ---------------------------------------------------------------------------
# H. Export requires include
# ---------------------------------------------------------------------------


def test_export_requires_include_pathspec():
    """Export without include is invalid relative to a successful include export."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"need_{token()}.{ext}"
    data = _letter_payload("h", 28)
    with workspace() as live:
        live.init_repo()
        install_local_keeping_process(live)
        track_pattern(live, pattern)
        digest = commit_tracked_payload(live, rel, data)
        clean = _export(live, [f"--include={pattern}"])
        print(f"export-with-include exit={clean.returncode}")
        require_success(clean)
        require_tree_blob_bytes(live, "HEAD", rel, data)
    with workspace() as dirty:
        dirty.init_repo()
        install_local_keeping_process(dirty)
        track_pattern(dirty, pattern)
        digest = commit_tracked_payload(dirty, rel, data)
        old = head_oid(dirty)
        missing = _export(dirty, [])
        print(f"export-without-include exit={missing.returncode}")
        require_invalid_unlike_success(clean, missing)
        require_tree_pointer(dirty, "HEAD", rel, digest, len(data))
        assert head_oid(dirty) == old, (
            "export without include rewrote history"
        )


# ---------------------------------------------------------------------------
# I. Export fetches missing objects from origin
# ---------------------------------------------------------------------------


def test_export_fetches_missing_objects_from_origin():
    """Export restores payload from origin when the local object is gone."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"fetch_{token()}.{ext}"
    data = _letter_payload("i", 45)
    digest = sha256_hex(data)

    with storing_batch_server() as svc:
        with workspace() as ws:
            ws.init_repo()
            bare = init_bare_git_remote(ws, f"bare_{token()}")
            add_git_remote(ws, "origin", str(bare))
            set_lfs_endpoint(ws, svc.url)
            # migrate export resolves the download endpoint from the named
            # remote, not from the global lfs.url override used by push.
            require_git_config_set(
                ws, "remote.origin.lfsurl", svc.url, local=True
            )
            disable_lock_verification(ws)
            install_local_keeping_process(ws)
            track_pattern(ws, pattern)
            planted = commit_tracked_payload(ws, rel, data)
            assert planted == digest
            require_tree_pointer(ws, "HEAD", rel, digest, len(data))
            pushed = ws.git(["push", "-u", "origin", "main"])
            print(f"seed push exit={pushed.returncode}")
            require_success(pushed)
            require_put_of(svc.records, data)
            remove_stored_object(ws, digest)
            require_object_absent(default_lfs_store_root(ws), digest)
            # Working-tree payload would let export rebuild the object
            # without contacting origin. Leave only the index pointer.
            write_pointer_placeholders_from_index(ws, [rel])
            require_object_absent(default_lfs_store_root(ws), digest)
            result = _export(
                ws, [f"--include={pattern}", "--include-ref=main"]
            )
            print(
                f"export-from-origin exit={result.returncode} "
                f"stderr={result.stderr_text!r}"
            )
            require_success(result)
            require_tree_blob_bytes(ws, "HEAD", rel, data)

    with workspace() as missing:
        missing.init_repo()
        install_local_keeping_process(missing)
        track_pattern(missing, pattern)
        planted = commit_tracked_payload(missing, rel, data)
        remove_stored_object(missing, planted)
        require_object_absent(default_lfs_store_root(missing), planted)
        write_pointer_placeholders_from_index(missing, [rel])
        require_object_absent(default_lfs_store_root(missing), planted)
        result = _export(missing, [f"--include={pattern}"])
        print(f"export-no-endpoint exit={result.returncode}")
        require_tree_pointer(missing, "HEAD", rel, planted, len(data))


# ---------------------------------------------------------------------------
# J. Default unpushed set; include/exclude-ref; everything; local refs only
# ---------------------------------------------------------------------------


def test_migrate_default_unpushed_and_local_refs_only():
    """Default import rewrites only unpushed commits; origin and its tracking stay put."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"p_{token()}.{ext}"
    p0 = _letter_payload("a", 26)
    p1 = _letter_payload("b", 34)
    with workspace() as ws:
        ws.init_repo()
        install_local_keeping_process(ws)
        commit_ordinary_blob(ws, rel, p0)
        c0 = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{rel}", p0)
        bare = init_bare_git_remote(ws, f"bare_{token()}")
        add_git_remote(ws, "origin", str(bare))
        pushed = ws.git(["push", "-u", "origin", "main"])
        require_success(pushed)
        require_ref_at(ws, "refs/remotes/origin/main", c0)
        require_ref_at(ws, "refs/heads/main", c0, cwd=bare)
        ws.write(rel, p1)
        _git_ok(ws, ["add", "--", rel])
        _git_ok(ws, ["commit", "-m", "c1"])
        c1 = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{rel}", p1)
        result = _import(ws, [f"--include={pattern}"])
        print(f"default-unpushed exit={result.returncode} c0={c0} c1={c1}")
        require_success(result)
        new_head = head_oid(ws)
        assert new_head != c1
        parent = _rev_parse(ws, "HEAD~1")
        assert parent == c0, (
            "default import rewrote a commit already on origin; "
            f"parent={parent} c0={c0}"
        )
        require_tree_blob_bytes(ws, parent, rel, p0)
        require_tree_pointer(ws, new_head, rel, sha256_hex(p1), len(p1))
        require_object_bytes(default_lfs_store_root(ws), sha256_hex(p1), p1)
        require_ref_at(ws, "refs/remotes/origin/main", c0)
        require_ref_at(ws, "refs/heads/main", c0, cwd=bare)


def test_migrate_include_exclude_ref_and_everything():
    """include-ref / exclude-ref / everything rewrite trees, not just SHAs."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"r_{token()}.{ext}"
    data_main = _letter_payload("c", 24)
    data_feat = _letter_payload("d", 36)
    feat = f"feat_{token()}"

    def _two_branch(ws, *, with_origin: bool = False):
        ws.init_repo()
        install_local_keeping_process(ws)
        # Shared ancestor must not be either tip: include-ref rewrites
        # ancestors, and every local ref pointing at a rewritten commit
        # is moved. Matching bytes live only on unique tip commits.
        commit_ordinary_blob(ws, f"base_{token()}", _letter_payload("z", 11))
        _git_ok(ws, ["checkout", "-b", feat])
        commit_ordinary_blob(ws, rel, data_feat)
        feat_sha = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{rel}", data_feat)
        _git_ok(ws, ["checkout", "main"])
        commit_ordinary_blob(ws, rel, data_main)
        main_sha = head_oid(ws)
        _setup_not_pointer(ws, f"HEAD:{rel}", data_main)
        bare = None
        if with_origin:
            bare = init_bare_git_remote(ws, f"bare_{token()}")
            add_git_remote(ws, "origin", str(bare))
            pushed = ws.git(["push", "-u", "origin", "main"])
            require_success(pushed)
        return main_sha, feat_sha, bare

    with workspace() as ws:
        main_sha, feat_sha, _bare = _two_branch(ws)
        result = _import(
            ws, [f"--include={pattern}", f"--include-ref={feat}"]
        )
        print(f"include-ref exit={result.returncode}")
        require_success(result)
        require_tree_pointer(
            ws, feat, rel, sha256_hex(data_feat), len(data_feat)
        )
        require_tree_blob_bytes(ws, "main", rel, data_main)
        require_ref_at(ws, "refs/heads/main", main_sha)

    with workspace() as ws:
        main_sha, feat_sha, _bare = _two_branch(ws)
        result = _import(
            ws,
            [
                f"--include={pattern}",
                "--include-ref=main",
                f"--include-ref={feat}",
                f"--exclude-ref={feat}",
            ],
        )
        print(f"exclude-ref exit={result.returncode}")
        require_success(result)
        require_tree_pointer(
            ws, "main", rel, sha256_hex(data_main), len(data_main)
        )
        require_tree_blob_bytes(ws, feat, rel, data_feat)
        require_ref_at(ws, feat, feat_sha)

    with workspace() as ws:
        main_sha, feat_sha, bare = _two_branch(ws, with_origin=True)
        origin_sha = read_ref(ws, "refs/remotes/origin/main")
        result = _import(ws, [f"--include={pattern}", "--everything"])
        print(f"everything exit={result.returncode}")
        require_success(result)
        require_tree_pointer(
            ws, "main", rel, sha256_hex(data_main), len(data_main)
        )
        require_tree_pointer(
            ws, feat, rel, sha256_hex(data_feat), len(data_feat)
        )
        require_ref_at(ws, "refs/remotes/origin/main", origin_sha)
        require_tree_blob_bytes(
            ws, "refs/remotes/origin/main", rel, data_main
        )
        require_ref_at(ws, "refs/heads/main", origin_sha, cwd=bare)


# ---------------------------------------------------------------------------
# K. Skip-fetch versus unreachable remote
# ---------------------------------------------------------------------------


def test_skip_fetch_allows_import_when_remote_unreachable():
    """Unreachable origin fails default import before rewrite; skip-fetch succeeds."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"s_{token()}.{ext}"
    data = _letter_payload("s", 32)
    digest = sha256_hex(data)

    def _plant(ws):
        ws.init_repo()
        install_local_keeping_process(ws)
        commit_ordinary_blob(ws, rel, data)
        _setup_not_pointer(ws, f"HEAD:{rel}", data)
        _unreachable_git_remote(ws)
        return head_oid(ws)

    with workspace() as blocked:
        old = _plant(blocked)
        result = _import(blocked, [f"--include={pattern}"])
        print(f"no-skip-fetch exit={result.returncode}")
        assert result.returncode != 0, (
            "import succeeded against an unreachable remote without skip-fetch"
        )
        assert head_oid(blocked) == old, (
            "import without skip-fetch rewrote history after a fetch failure"
        )
        require_tree_blob_bytes(blocked, "HEAD", rel, data)
        require_object_absent(default_lfs_store_root(blocked), digest)

    with workspace() as allowed:
        old = _plant(allowed)
        result = _import(
            allowed, [f"--include={pattern}", "--skip-fetch"]
        )
        print(f"skip-fetch exit={result.returncode}")
        require_success(result)
        assert head_oid(allowed) != old
        require_tree_pointer(allowed, "HEAD", rel, digest, len(data))
        require_object_bytes(default_lfs_store_root(allowed), digest, data)


# ---------------------------------------------------------------------------
# L. Symlink .gitattributes
# ---------------------------------------------------------------------------


def test_migrate_refuses_symlink_gitattributes():
    """Migrate refuses when .gitattributes is a symlink; a regular file import succeeds."""
    ext = token()
    pattern = f"*.{ext}"
    rel = f"l_{token()}.{ext}"
    data = _letter_payload("l", 30)

    with workspace() as live:
        live.init_repo()
        install_local_keeping_process(live)
        live.write(".gitattributes", "\n")
        _git_ok(live, ["add", "--", ".gitattributes"])
        _git_ok(live, ["commit", "-m", "attrs"])
        commit_ordinary_blob(live, rel, data)
        clean = _import(live, [f"--include={pattern}"])
        print(f"regular-attrs import exit={clean.returncode}")
        require_success(clean)

    with workspace() as ws:
        ws.init_repo()
        install_local_keeping_process(ws)
        target = f"ga_{token()}"
        ws.write(target, "\n")
        os.symlink(target, ws.resolve(".gitattributes"))
        _git_ok(ws, ["add", "--", target, ".gitattributes"])
        _git_ok(ws, ["commit", "-m", "symlink attrs"])
        commit_ordinary_blob(ws, rel, data)
        old = head_oid(ws)
        dirty = _import(ws, [f"--include={pattern}"])
        print(f"symlink-attrs import exit={dirty.returncode}")
        require_invalid_unlike_success(clean, dirty)
        assert head_oid(ws) == old
        require_tree_blob_bytes(ws, "HEAD", rel, data)
        info = _info(ws)
        assert info.returncode != 0, (
            "info succeeded when .gitattributes was a symbolic link"
        )
        assert head_oid(ws) == old


# ---------------------------------------------------------------------------
# M. PATH negative control
# ---------------------------------------------------------------------------


def test_migrate_fails_without_product_on_path():
    """Migrate info without the product on PATH is non-success; with PATH it succeeds."""
    ext = token()
    rel = f"p_{token()}.{ext}"
    with workspace() as ws:
        ws.init_repo()
        commit_ordinary_blob(ws, rel, _letter_payload("z", 18))
        blocked = _info(
            ws, env_updates={"PATH": path_without_product_bin(ws.env)}
        )
        print(f"PATH-blocked info exit={blocked.returncode}")
        assert blocked.returncode != 0, (
            "migrate info succeeded after the product was removed from PATH"
        )
        require_success(_info(ws))
        type_report(info_visible(_info(ws)), ext)
