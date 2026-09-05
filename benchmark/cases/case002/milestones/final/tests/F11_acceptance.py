# feature: F11
"""Status and ls-files inspection acceptance tests.

PRD: FP-11. Oracles are which VCS Orbulk paths appear in which listing,
whether the default named-path line distinguishes a full-object
checkout from a pointer checkout after covariate stripping, and
whether JSON named entries independently mark local-store presence.
Message wording, mark characters, JSON keys, and exit-code numbers
are not pinned.
"""

from __future__ import annotations

from _harness import token, workspace
from _helpers import (
    add_git_remote,
    assert_invalid_unlike_success,
    assert_json_strings_include,
    assert_success,
    assert_visible_contains,
    commit_ordinary_blob,
    commit_tracked_payload,
    configure_current_branch_upstream,
    default_lfs_store_root,
    extract_json_listing,
    head_oid,
    index_blob,
    init_bare_git_remote,
    install_local_keeping_process,
    json_named_entry,
    json_named_entry_visible,
    json_strings_include,
    json_walk_keys_and_strings,
    listing_observation_remainder,
    listing_visible,
    listing_without_json_document,
    named_path_listing_line,
    path_without_product_bin,
    prepare_tracked_commit,
    remove_stored_object,
    require_invalid_unlike_success,
    require_object_absent,
    require_object_bytes,
    require_success,
    require_visible_contains,
    require_visible_omits,
    require_working_tree_bytes,
    require_working_tree_pointer,
    run_ls_files,
    run_status,
    runtime_http_url,
    set_remote_tracking,
    sha256_hex,
    strip_listing_covariates,
    track_pattern,
    write_pointer_placeholders_from_index,
)


def _payload(n: int) -> bytes:
    stamp = token().encode("ascii")
    body = b"blob-" + stamp + b"\n"
    if len(body) >= n:
        return (stamp * ((n // len(stamp)) + 1))[:n]
    return body + (b"x" * (n - len(body)))


def _rel(prefix: str) -> str:
    return f"{prefix}_{token()}.bin"


def _txt() -> str:
    return f"ord_{token()}.txt"


def _git_ok(ws, argv, **kwargs):
    result = ws.git(argv, **kwargs)
    assert result.returncode == 0, (
        f"git {argv!r} failed (exit {result.returncode}): {result.stderr_text}"
    )
    return result


def _branch_name(ws) -> str:
    result = ws.git(["rev-parse", "--abbrev-ref", "HEAD"])
    assert result.returncode == 0, (
        "git rev-parse --abbrev-ref HEAD failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    name = result.stdout_text.strip()
    assert name and name != "HEAD", f"not on a named branch: {name!r}"
    return name


def _assert_distinct(*paths: str) -> tuple[str, ...]:
    for index, left in enumerate(paths):
        assert left, "path token is empty"
        for other in paths[index + 1 :]:
            assert left not in other and other not in left, (
                f"path tokens overlap: {left!r} {other!r}"
            )
    return paths


def _init_tracked(ws) -> None:
    ws.init_repo()
    install_local_keeping_process(ws)
    track_pattern(ws, "*.bin")


def _prepare(ws, rel: str, data: bytes) -> str:
    ws.init_repo()
    return prepare_tracked_commit(ws, rel, data)


def _abs(ws, rel: str) -> str:
    return str(ws.resolve(rel))


def _oid_prefix_tokens(oid: str) -> list[str]:
    tokens = [oid]
    for length in range(7, min(len(oid), 16) + 1):
        tokens.append(oid[:length])
    return tokens


def _strip_path_oid_payload(
    text: str,
    *,
    path: str,
    oid: str,
    payload: bytes,
    extra: list[str] | None = None,
) -> str:
    tokens = [path, payload.decode("utf-8"), *_oid_prefix_tokens(oid)]
    if extra:
        tokens.extend(extra)
    return strip_listing_covariates(text, tokens)


def _remainder_line(
    line: str,
    *,
    paths: list[str],
    oids: list[str],
    blobs: list[bytes],
    pointers: list[bytes],
    sizes: list[int],
    abs_paths: list[str],
) -> str:
    rem = listing_observation_remainder(
        line,
        paths=paths,
        oids=oids,
        worktree_blobs=blobs,
        pointers=pointers,
        sizes=sizes,
        abs_paths=abs_paths,
    )
    print(f"listing_remainder={rem!r} line={line!r}")
    return rem


def _json_entry_remainder(
    parsed: object,
    path: str,
    *,
    oids: list[str],
    blobs: list[bytes],
    pointers: list[bytes],
    sizes: list[int],
    abs_paths: list[str],
) -> str:
    entry = json_named_entry(parsed, path)
    visible = json_named_entry_visible(entry)
    rem = listing_observation_remainder(
        visible,
        paths=[path],
        oids=oids,
        worktree_blobs=blobs,
        pointers=pointers,
        sizes=sizes,
        abs_paths=abs_paths,
    )
    print(f"json_entry_remainder path={path!r} rem={rem!r} visible={visible!r}")
    return rem


def _plant_token_remote(ws, *, at_sha: str) -> tuple[str, str]:
    remote = f"rmt_{token()}"
    bare = init_bare_git_remote(ws, f"bare_{token()}")
    add_git_remote(ws, remote, str(bare))
    branch = configure_current_branch_upstream(ws, remote)
    set_remote_tracking(ws, remote, branch, at_sha)
    return remote, branch


def _plant_origin_at_head(ws, branch: str) -> None:
    add_git_remote(ws, "origin", runtime_http_url("orig"))
    set_remote_tracking(ws, "origin", branch, head_oid(ws))


def _build_ahead_unpushed(ws) -> dict[str, str]:
    """Current ref is ahead of a token-named remote-tracking ref.

    History: A at the tracking tip; then B (Orbulk), E (ordinary Git), Y
    (LFS, later deleted). A second branch holds C, unreachable from
    current HEAD. Origin's tracking ref is planted at current HEAD.
    """
    _init_tracked(ws)
    path_a, path_b, path_y, path_c = _assert_distinct(
        _rel("a"), _rel("b"), _rel("y"), _rel("c")
    )
    path_e = _txt()
    oid_a = commit_tracked_payload(ws, path_a, _payload(81))
    sha_a = head_oid(ws)
    remote, branch = _plant_token_remote(ws, at_sha=sha_a)
    oid_b = commit_tracked_payload(ws, path_b, _payload(221))
    commit_ordinary_blob(ws, path_e, f"plain-{token()}\n")
    oid_y = commit_tracked_payload(ws, path_y, _payload(361))
    _git_ok(ws, ["rm", "--", path_y])
    _git_ok(ws, ["commit", "-m", f"drop {path_y}"])
    other = f"br_{token()}"
    _git_ok(ws, ["checkout", "-b", other])
    oid_c = commit_tracked_payload(ws, path_c, _payload(481))
    _git_ok(ws, ["checkout", branch])
    _plant_origin_at_head(ws, branch)
    return {
        "path_a": path_a,
        "path_b": path_b,
        "path_c": path_c,
        "path_e": path_e,
        "path_y": path_y,
        "oid_a": oid_a,
        "oid_b": oid_b,
        "oid_c": oid_c,
        "oid_y": oid_y,
        "branch": branch,
        "remote": remote,
        "other": other,
    }


def _build_caught_up(ws) -> dict[str, str]:
    info = _build_ahead_unpushed(ws)
    set_remote_tracking(
        ws, info["remote"], info["branch"], head_oid(ws)
    )
    return info


def _stage_lfs(ws, rel: str, data: bytes) -> str:
    ws.write(rel, data)
    digest = sha256_hex(data)
    _git_ok(ws, ["add", "--", rel])
    return digest


# ---------------------------------------------------------------------------
# A. Unpushed default human status
# ---------------------------------------------------------------------------


def test_status_unpushed_lists_current_ref_lfs_minus_tracking():
    """Default human status lists B and Y; omits A, C, and ordinary E."""
    with workspace() as ws:
        info = _build_ahead_unpushed(ws)
        result = run_status(ws)
        require_success(result)
        print(f"unpushed_human={listing_visible(result)!r}")
        require_visible_contains(result, info["path_b"])
        require_visible_contains(result, info["path_y"])
        require_visible_omits(result, info["path_a"])
        require_visible_omits(result, info["path_c"])
        require_visible_omits(result, info["path_e"])


def test_status_caught_up_tracking_omits_unpushed_paths():
    """Caught-up tracking omits B and Y only after a lagging listing.

    Live baseline: while the current branch's remote-tracking ref still
    lags HEAD, default human status names those LFS paths. The caught-up
    arm then requires the same paths absent. Exit-0 plus never-named is
    not enough.
    """
    with workspace() as lagging:
        info = _build_ahead_unpushed(lagging)
        baseline = run_status(lagging)
        require_success(baseline)
        print(f"lagging_human={listing_visible(baseline)!r}")
        require_visible_contains(baseline, info["path_b"])
        require_visible_contains(baseline, info["path_y"])
    with workspace() as caught:
        info = _build_caught_up(caught)
        result = run_status(caught)
        require_success(result)
        print(f"caught_up_human={listing_visible(result)!r}")
        require_visible_omits(result, info["path_b"])
        require_visible_omits(result, info["path_y"])


def test_status_porcelain_and_json_omit_unpushed():
    """Scripting modes cover index/worktree only, not the unpushed set."""
    with workspace() as ws:
        info = _build_ahead_unpushed(ws)
        human = run_status(ws)
        require_success(human)
        require_visible_contains(human, info["path_b"])
        print(f"human_baseline_b={info['path_b']!r}")
        porc = run_status(ws, ["--porcelain"])
        require_success(porc)
        print(f"porcelain_unpushed={listing_visible(porc)!r}")
        require_visible_omits(porc, info["path_b"])
        require_visible_omits(porc, info["path_y"])
        js = run_status(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        print(f"json_unpushed={parsed!r}")
        walked = json_walk_keys_and_strings(parsed)
        assert info["path_b"] not in walked, (
            f"JSON status listed unpushed path {info['path_b']!r}: {walked!r}"
        )
        assert info["path_y"] not in walked, (
            f"JSON status listed unpushed path {info['path_y']!r}: {walked!r}"
        )


def test_status_one_call_lists_unpushed_and_index_together():
    """One human status names unpushed B and staged D; scripts name only D."""
    with workspace() as ws:
        _init_tracked(ws)
        path_a, path_b, path_d = _assert_distinct(_rel("a"), _rel("b"), _rel("d"))
        commit_tracked_payload(ws, path_a, _payload(81))
        sha_a = head_oid(ws)
        _plant_token_remote(ws, at_sha=sha_a)
        commit_tracked_payload(ws, path_b, _payload(221))
        _stage_lfs(ws, path_d, _payload(361))
        require_working_tree_bytes(ws, path_d, ws.read_bytes(path_d))
        human = run_status(ws)
        require_success(human)
        print(f"human_b_and_d={listing_visible(human)!r}")
        require_visible_contains(human, path_b)
        require_visible_contains(human, path_d)
        porc = run_status(ws, ["--porcelain"])
        require_success(porc)
        print(f"porcelain_d_not_b={listing_visible(porc)!r}")
        require_visible_contains(porc, path_d)
        require_visible_omits(porc, path_b)
        js = run_status(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        print(f"json_d_not_b={parsed!r}")
        json_strings_include(parsed, path_d)
        walked = json_walk_keys_and_strings(parsed)
        assert path_b not in walked, (
            f"JSON status listed unpushed path {path_b!r}: {walked!r}"
        )


def test_status_direct_binary_names_index_path():
    """Direct binary status names a staged LFS path."""
    with workspace() as ws:
        _init_tracked(ws)
        rel = _rel("d")
        data = _payload(221)
        commit_ordinary_blob(ws, _txt(), f"keep-{token()}\n")
        _stage_lfs(ws, rel, data)
        result = ws.invoke(["status"])
        assert_success(result)
        print(f"direct_status={listing_visible(result)!r}")
        assert_visible_contains(result, rel)


# ---------------------------------------------------------------------------
# B. Bare failure and PATH negative control
# ---------------------------------------------------------------------------


def test_status_fails_in_bare_repository():
    """Status in a bare repository is non-success; a work tree succeeds."""
    with workspace() as wt:
        wt.init_repo()
        commit_ordinary_blob(wt, _txt(), f"keep-{token()}\n")
        ok = run_status(wt)
        print(f"worktree_status_exit={ok.returncode}")
        assert_success(ok)
    with workspace() as bare_ws:
        dest = init_bare_git_remote(bare_ws, f"bare_{token()}")
        dirty = run_status(bare_ws, cwd=dest)
        print(f"bare_status_exit={dirty.returncode}")
        assert_invalid_unlike_success(ok, dirty)


def test_status_and_ls_files_fail_when_binary_absent_from_path():
    """PATH without the product binary makes status and ls-files fail."""
    with workspace() as present:
        _init_tracked(present)
        rel = _rel("p")
        prepare_tracked_commit(present, rel, _payload(221))
        ok_status = run_status(present)
        ok_ls = run_ls_files(present)
        require_success(ok_status)
        require_success(ok_ls)
    with workspace() as missing:
        _init_tracked(missing)
        rel = _rel("p")
        prepare_tracked_commit(missing, rel, _payload(221))
        hidden = path_without_product_bin(missing.env)
        env = {"PATH": hidden}
        status_f = run_status(missing, env_updates=env)
        ls_f = run_ls_files(missing, env_updates=env)
        print(
            f"absent status={status_f.returncode} ls-files={ls_f.returncode}"
        )
        assert status_f.returncode != 0, (
            "status succeeded with the product binary removed from PATH"
        )
        assert ls_f.returncode != 0, (
            "ls-files succeeded with the product binary removed from PATH"
        )


# ---------------------------------------------------------------------------
# C. Index/HEAD, working-tree/index, porcelain over JSON
# ---------------------------------------------------------------------------


def test_status_lists_index_head_lfs_path_in_all_modes():
    """A staged uncommitted LFS path is named in human, porcelain, and JSON."""
    with workspace() as ws:
        _init_tracked(ws)
        commit_ordinary_blob(ws, _txt(), f"keep-{token()}\n")
        rel = _rel("st")
        _stage_lfs(ws, rel, _payload(221))
        human = run_status(ws)
        assert_success(human)
        print(f"human_staged={listing_visible(human)!r}")
        assert_visible_contains(human, rel)
        porc = run_status(ws, ["--porcelain"])
        assert_success(porc)
        print(f"porcelain_staged={listing_visible(porc)!r}")
        assert_visible_contains(porc, rel)
        js = run_status(ws, ["--json"])
        assert_success(js)
        parsed = extract_json_listing(js)
        print(f"json_staged={parsed!r}")
        assert_json_strings_include(parsed, rel)


def test_status_lists_worktree_index_lfs_path_in_all_modes():
    """An unstaged working-tree LFS edit is named in all three modes."""
    with workspace() as ws:
        rel = _rel("wt")
        _prepare(ws, rel, _payload(221))
        ws.write(rel, _payload(361))
        human = run_status(ws)
        assert_success(human)
        print(f"human_unstaged={listing_visible(human)!r}")
        assert_visible_contains(human, rel)
        porc = run_status(ws, ["--porcelain"])
        assert_success(porc)
        print(f"porcelain_unstaged={listing_visible(porc)!r}")
        assert_visible_contains(porc, rel)
        js = run_status(ws, ["--json"])
        assert_success(js)
        parsed = extract_json_listing(js)
        print(f"json_unstaged={parsed!r}")
        assert_json_strings_include(parsed, rel)


def test_status_omits_ordinary_git_paths():
    """Ordinary Git index diffs are named by human and porcelain; JSON omits them."""
    with workspace() as ws:
        _init_tracked(ws)
        commit_ordinary_blob(ws, _txt(), f"keep-{token()}\n")
        rel = _rel("st")
        _stage_lfs(ws, rel, _payload(221))
        ordinary = _txt()
        ws.write(ordinary, f"plain-{token()}\n")
        _git_ok(ws, ["add", "--", ordinary])
        human = run_status(ws)
        require_success(human)
        print(f"human_ordinary={listing_visible(human)!r}")
        require_visible_contains(human, rel)
        require_visible_contains(human, ordinary)
        porc = run_status(ws, ["--porcelain"])
        require_success(porc)
        print(f"porcelain_ordinary={listing_visible(porc)!r}")
        require_visible_contains(porc, rel)
        require_visible_contains(porc, ordinary)
        js = run_status(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        print(f"json_ordinary={parsed!r}")
        json_strings_include(parsed, rel)
        walked = json_walk_keys_and_strings(parsed)
        assert ordinary not in walked, (
            f"JSON status listed ordinary Git path {ordinary!r}: {walked!r}"
        )


def test_status_names_ordinary_git_worktree_index_paths():
    """Ordinary Git working-tree/index diffs: human and porcelain name them; JSON does not."""
    with workspace() as ws:
        rel = _rel("wt")
        _prepare(ws, rel, _payload(221))
        ordinary = _txt()
        commit_ordinary_blob(ws, ordinary, f"keep-{token()}\n")
        rel, ordinary = _assert_distinct(rel, ordinary)
        ws.write(rel, _payload(361))
        ws.write(ordinary, f"plain-{token()}\n")
        human = run_status(ws)
        require_success(human)
        print(f"human_wt_ordinary={listing_visible(human)!r}")
        require_visible_contains(human, rel)
        require_visible_contains(human, ordinary)
        porc = run_status(ws, ["--porcelain"])
        require_success(porc)
        print(f"porcelain_wt_ordinary={listing_visible(porc)!r}")
        require_visible_contains(porc, rel)
        require_visible_contains(porc, ordinary)
        js = run_status(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        print(f"json_wt_ordinary={parsed!r}")
        json_strings_include(parsed, rel)
        walked = json_walk_keys_and_strings(parsed)
        assert ordinary not in walked, (
            f"JSON status listed ordinary Git path {ordinary!r}: {walked!r}"
        )


def test_status_porcelain_overrides_json():
    """Combined porcelain+JSON matches porcelain after path strip, unlike JSON."""
    with workspace() as ws:
        _init_tracked(ws)
        commit_ordinary_blob(ws, _txt(), f"keep-{token()}\n")
        rel = _rel("st")
        _stage_lfs(ws, rel, _payload(221))
        js = run_status(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        json_strings_include(parsed, rel)
        json_rem = strip_listing_covariates(
            listing_visible(js), [rel, _abs(ws, rel)]
        )
        print(f"json_only_rem={json_rem!r}")
        porc = run_status(ws, ["--porcelain"])
        require_success(porc)
        require_visible_contains(porc, rel)
        porc_rem = strip_listing_covariates(
            listing_visible(porc), [rel, _abs(ws, rel)]
        )
        print(f"porcelain_only_rem={porc_rem!r}")
        combo = run_status(ws, ["--porcelain", "--json"])
        require_success(combo)
        require_visible_contains(combo, rel)
        combo_rem = strip_listing_covariates(
            listing_visible(combo), [rel, _abs(ws, rel)]
        )
        print(f"porcelain_json_rem={combo_rem!r}")
        assert combo_rem == porc_rem, (
            "porcelain+JSON remainder after stripping the path was not "
            f"the porcelain remainder: {combo_rem!r} vs {porc_rem!r}"
        )
        assert combo_rem != json_rem, (
            "porcelain+JSON remainder was not distinguishable from JSON "
            f"after stripping the path: {combo_rem!r}"
        )


# ---------------------------------------------------------------------------
# D. No-ref includes index; explicit current branch is the tree
# ---------------------------------------------------------------------------


def test_ls_files_no_ref_prefers_index_oid():
    """No-ref ls-files names the path with the index oid, not the tree oid."""
    with workspace() as ws:
        tree_data = _payload(221)
        index_data = _payload(361)
        rel = _rel("ix")
        tree_oid = _prepare(ws, rel, tree_data)
        index_oid = _stage_lfs(ws, rel, index_data)
        assert tree_oid != index_oid
        result = run_ls_files(ws, ["--long"])
        require_success(result)
        text = listing_visible(result)
        print(f"no_ref_long={text!r} index={index_oid} tree={tree_oid}")
        require_visible_contains(result, rel)
        assert index_oid in text, (
            f"no-ref listing does not carry the index object id {index_oid}: "
            f"{text!r}"
        )
        assert tree_oid not in text, (
            f"no-ref listing still carries the tree object id {tree_oid}: "
            f"{text!r}"
        )


def test_ls_files_explicit_current_branch_ignores_index():
    """Explicit current branch name lists the tree oid, not the index oid."""
    with workspace() as ws:
        tree_data = _payload(221)
        index_data = _payload(361)
        rel = _rel("ix")
        tree_oid = _prepare(ws, rel, tree_data)
        index_oid = _stage_lfs(ws, rel, index_data)
        branch = _branch_name(ws)
        result = run_ls_files(ws, ["--long", branch])
        require_success(result)
        text = listing_visible(result)
        print(
            f"explicit_branch_long={text!r} branch={branch!r} "
            f"tree={tree_oid} index={index_oid}"
        )
        require_visible_contains(result, rel)
        assert tree_oid in text, (
            f"explicit-branch listing does not carry the tree object id "
            f"{tree_oid}: {text!r}"
        )
        assert index_oid not in text, (
            f"explicit-branch listing carries the index object id "
            f"{index_oid}: {text!r}"
        )


def test_ls_files_index_only_path_absent_from_explicit_branch():
    """A path only in the index is listed with no ref and omitted at the branch."""
    with workspace() as ws:
        _init_tracked(ws)
        tree_rel = _rel("tr")
        prepare_tracked_commit(ws, tree_rel, _payload(221))
        only = _rel("only")
        _stage_lfs(ws, only, _payload(361))
        listed = run_ls_files(ws)
        require_success(listed)
        require_visible_contains(listed, only)
        print(f"no_ref_index_only={listing_visible(listed)!r}")
        branch = _branch_name(ws)
        explicit = run_ls_files(ws, [branch])
        require_success(explicit)
        print(f"explicit_omits_index_only={listing_visible(explicit)!r}")
        require_visible_omits(explicit, only)
        require_visible_contains(explicit, tree_rel)


# ---------------------------------------------------------------------------
# E. Two-ref: modifications listed, deletions omitted
# ---------------------------------------------------------------------------


def test_ls_files_two_ref_lists_modification_omits_unchanged_and_deleted():
    """Two-ref listing names the modified path, not the unchanged or deleted."""
    with workspace() as ws:
        _init_tracked(ws)
        path_b, path_c, path_d = _assert_distinct(_rel("b"), _rel("c"), _rel("d"))
        commit_tracked_payload(ws, path_b, _payload(81))
        commit_tracked_payload(ws, path_c, _payload(221))
        commit_tracked_payload(ws, path_d, _payload(361))
        old_ref = f"old_{token()}"
        _git_ok(ws, ["tag", old_ref])
        commit_tracked_payload(ws, path_c, _payload(481))
        _git_ok(ws, ["rm", "--", path_d])
        _git_ok(ws, ["commit", "-m", f"drop {path_d}"])
        new_ref = f"new_{token()}"
        _git_ok(ws, ["tag", new_ref])
        two = run_ls_files(ws, [old_ref, new_ref])
        require_success(two)
        print(f"two_ref={listing_visible(two)!r} old={old_ref} new={new_ref}")
        require_visible_contains(two, path_c)
        require_visible_omits(two, path_b)
        require_visible_omits(two, path_d)
        side_b = run_ls_files(ws, [new_ref])
        require_success(side_b)
        require_visible_contains(side_b, path_b)
        print(f"single_new_has_b={listing_visible(side_b)!r}")
        side_d = run_ls_files(ws, [old_ref])
        require_success(side_d)
        require_visible_contains(side_d, path_d)
        print(f"single_old_has_d={listing_visible(side_d)!r}")


# ---------------------------------------------------------------------------
# F. Default-line checkout indication
# ---------------------------------------------------------------------------


def _checkout_pair(ws) -> dict[str, object]:
    path_p, path_q = _assert_distinct(_rel("p"), _rel("q"))
    data_p = _payload(221)
    data_q = _payload(361)
    _init_tracked(ws)
    commit_tracked_payload(ws, path_p, data_p)
    commit_tracked_payload(ws, path_q, data_q)
    require_working_tree_bytes(ws, path_p, data_p)
    write_pointer_placeholders_from_index(ws, [path_q])
    pointer_q = index_blob(ws, path_q)
    require_working_tree_pointer(
        ws, path_q, digest=sha256_hex(data_q), size=len(data_q)
    )
    require_working_tree_bytes(ws, path_p, data_p)
    oid_p = sha256_hex(data_p)
    oid_q = sha256_hex(data_q)
    return {
        "path_p": path_p,
        "path_q": path_q,
        "data_p": data_p,
        "data_q": data_q,
        "pointer_q": pointer_q,
        "oid_p": oid_p,
        "oid_q": oid_q,
        "sizes": [len(data_p), len(data_q), len(pointer_q)],
    }


def _checkout_remainders(ws, info: dict[str, object], result) -> tuple[str, str]:
    path_p = str(info["path_p"])
    path_q = str(info["path_q"])
    require_visible_contains(result, path_p)
    require_visible_contains(result, path_q)
    text = listing_visible(result)
    line_p = named_path_listing_line(text, path_p, other_paths=[path_q])
    line_q = named_path_listing_line(text, path_q, other_paths=[path_p])
    kwargs = dict(
        paths=[path_p, path_q],
        oids=[str(info["oid_p"]), str(info["oid_q"])],
        blobs=[bytes(info["data_p"]), bytes(info["data_q"]), bytes(info["pointer_q"])],
        pointers=[bytes(info["pointer_q"])],
        sizes=list(info["sizes"]),
        abs_paths=[_abs(ws, path_p), _abs(ws, path_q), str(ws.path.resolve())],
    )
    rem_p = _remainder_line(line_p, **kwargs)
    rem_q = _remainder_line(line_q, **kwargs)
    return rem_p, rem_q


def test_ls_files_default_line_checkout_indication_per_entry():
    """One listing distinguishes full-object P from pointer Q after stripping."""
    with workspace() as ws:
        info = _checkout_pair(ws)
        first = run_ls_files(ws)
        require_success(first)
        rem_p1, rem_q1 = _checkout_remainders(ws, info, first)
        assert rem_p1 != rem_q1, (
            "after stripping path, oid, size, and content dumps, the "
            "full-object and pointer named-path lines were not "
            f"distinguishable: {rem_p1!r} vs {rem_q1!r}"
        )
        assert rem_p1.strip() and rem_q1.strip(), (
            "checkout indication vanished after covariate stripping: "
            f"P={rem_p1!r} Q={rem_q1!r}"
        )
        second = run_ls_files(ws)
        require_success(second)
        rem_p2, rem_q2 = _checkout_remainders(ws, info, second)
        assert rem_p1 == rem_p2, (
            "full-object checkout remainder was not stable: "
            f"{rem_p1!r} vs {rem_p2!r}"
        )
        assert rem_q1 == rem_q2, (
            "pointer checkout remainder was not stable: "
            f"{rem_q1!r} vs {rem_q2!r}"
        )


def test_ls_files_checkout_indication_shared_across_store_presence():
    """Holding the working tree fixed, store presence does not flip the mark."""
    with workspace() as present:
        info_p = _checkout_pair(present)
        store = default_lfs_store_root(present)
        require_object_bytes(store, str(info_p["oid_p"]), bytes(info_p["data_p"]))
        require_object_bytes(store, str(info_p["oid_q"]), bytes(info_p["data_q"]))
        listed = run_ls_files(present)
        require_success(listed)
        rem_pp, rem_pq = _checkout_remainders(present, info_p, listed)
        assert rem_pp != rem_pq
    with workspace() as missing:
        info_m = _checkout_pair(missing)
        store = default_lfs_store_root(missing)
        require_object_bytes(store, str(info_m["oid_p"]), bytes(info_m["data_p"]))
        require_object_bytes(store, str(info_m["oid_q"]), bytes(info_m["data_q"]))
        remove_stored_object(missing, str(info_m["oid_p"]))
        remove_stored_object(missing, str(info_m["oid_q"]))
        require_object_absent(store, str(info_m["oid_p"]))
        require_object_absent(store, str(info_m["oid_q"]))
        require_working_tree_bytes(missing, str(info_m["path_p"]), bytes(info_m["data_p"]))
        require_working_tree_pointer(
            missing,
            str(info_m["path_q"]),
            digest=str(info_m["oid_q"]),
            size=len(bytes(info_m["data_q"])),
        )
        listed = run_ls_files(missing)
        require_success(listed)
        rem_mp, rem_mq = _checkout_remainders(missing, info_m, listed)
        assert rem_mp != rem_mq, (
            "store-missing arm lost the per-entry checkout contrast: "
            f"{rem_mp!r} vs {rem_mq!r}"
        )
        assert rem_pp == rem_mp, (
            "full-object checkout remainder flipped with local-store "
            f"presence: present={rem_pp!r} missing={rem_mp!r}"
        )
        assert rem_pq == rem_mq, (
            "pointer checkout remainder flipped with local-store "
            f"presence: present={rem_pq!r} missing={rem_mq!r}"
        )


# ---------------------------------------------------------------------------
# G. JSON local-store presence on the named entry
# ---------------------------------------------------------------------------


def _json_store_remainders(
    ws,
    path_p: str,
    path_q: str,
    oid_p: str,
    oid_q: str,
    blobs: list[bytes],
    pointers: list[bytes],
    sizes: list[int],
    extra: list[str] | None = None,
) -> tuple[str, str]:
    argv = ["--json", *(extra or [])]
    result = run_ls_files(ws, argv)
    require_success(result)
    parsed = extract_json_listing(result)
    json_strings_include(parsed, path_p)
    json_strings_include(parsed, path_q)
    print(f"json_listing={parsed!r}")
    rem_p = _json_entry_remainder(
        parsed,
        path_p,
        oids=[oid_p, oid_q],
        blobs=blobs,
        pointers=pointers,
        sizes=sizes,
        abs_paths=[_abs(ws, path_p), _abs(ws, path_q), str(ws.path.resolve())],
    )
    rem_q = _json_entry_remainder(
        parsed,
        path_q,
        oids=[oid_p, oid_q],
        blobs=blobs,
        pointers=pointers,
        sizes=sizes,
        abs_paths=[_abs(ws, path_p), _abs(ws, path_q), str(ws.path.resolve())],
    )
    return rem_p, rem_q


def test_ls_files_json_store_presence_pointer_worktree():
    """JSON named entries differ by store presence when both files are pointers."""
    with workspace() as ws:
        path_p, path_q = _assert_distinct(_rel("p"), _rel("q"))
        data_p = _payload(221)
        data_q = _payload(361)
        _init_tracked(ws)
        oid_p = commit_tracked_payload(ws, path_p, data_p)
        oid_q = commit_tracked_payload(ws, path_q, data_q)
        pointers = write_pointer_placeholders_from_index(ws, [path_p, path_q])
        require_working_tree_pointer(ws, path_p, digest=oid_p, size=len(data_p))
        require_working_tree_pointer(ws, path_q, digest=oid_q, size=len(data_q))
        store = default_lfs_store_root(ws)
        require_object_bytes(store, oid_p, data_p)
        require_object_bytes(store, oid_q, data_q)
        remove_stored_object(ws, oid_q)
        require_object_absent(store, oid_q)
        rem_p, rem_q = _json_store_remainders(
            ws,
            path_p,
            path_q,
            oid_p,
            oid_q,
            blobs=[data_p, data_q, pointers[path_p], pointers[path_q]],
            pointers=[pointers[path_p], pointers[path_q]],
            sizes=[
                len(data_p),
                len(data_q),
                len(pointers[path_p]),
                len(pointers[path_q]),
            ],
        )
        assert rem_p != rem_q, (
            "JSON named entries did not distinguish local-store presence "
            f"on pointer worktrees: {rem_p!r} vs {rem_q!r}"
        )


def test_ls_files_json_store_presence_full_object_worktree():
    """JSON named entries differ by store presence when both files are full objects."""
    with workspace() as full:
        path_p, path_q = _assert_distinct(_rel("p"), _rel("q"))
        data_p = _payload(221)
        data_q = _payload(361)
        _init_tracked(full)
        oid_p = commit_tracked_payload(full, path_p, data_p)
        oid_q = commit_tracked_payload(full, path_q, data_q)
        require_working_tree_bytes(full, path_p, data_p)
        require_working_tree_bytes(full, path_q, data_q)
        store = default_lfs_store_root(full)
        require_object_bytes(store, oid_p, data_p)
        require_object_bytes(store, oid_q, data_q)
        remove_stored_object(full, oid_q)
        require_object_absent(store, oid_q)
        branch = _branch_name(full)
        rem_p, rem_q = _json_store_remainders(
            full,
            path_p,
            path_q,
            oid_p,
            oid_q,
            blobs=[data_p, data_q],
            pointers=[],
            sizes=[len(data_p), len(data_q)],
            extra=[branch],
        )
        print(
            "full_object_named_entries "
            f"store_present={rem_p!r} store_missing={rem_q!r}"
        )
        assert rem_p != rem_q, (
            "JSON named entries did not distinguish local-store presence "
            "when the working-tree files are the full object: "
            f"store_present={rem_p!r} store_missing={rem_q!r}"
        )
    with workspace() as ptr:
        path_p, path_q = _assert_distinct(_rel("p"), _rel("q"))
        data_p = _payload(221)
        data_q = _payload(361)
        _init_tracked(ptr)
        oid_p = commit_tracked_payload(ptr, path_p, data_p)
        oid_q = commit_tracked_payload(ptr, path_q, data_q)
        pointers = write_pointer_placeholders_from_index(ptr, [path_p, path_q])
        require_working_tree_pointer(ptr, path_p, digest=oid_p, size=len(data_p))
        require_working_tree_pointer(ptr, path_q, digest=oid_q, size=len(data_q))
        store = default_lfs_store_root(ptr)
        require_object_bytes(store, oid_p, data_p)
        require_object_bytes(store, oid_q, data_q)
        remove_stored_object(ptr, oid_q)
        require_object_absent(store, oid_q)
        rem_p, rem_q = _json_store_remainders(
            ptr,
            path_p,
            path_q,
            oid_p,
            oid_q,
            blobs=[data_p, data_q, pointers[path_p], pointers[path_q]],
            pointers=[pointers[path_p], pointers[path_q]],
            sizes=[
                len(data_p),
                len(data_q),
                len(pointers[path_p]),
                len(pointers[path_q]),
            ],
        )
        assert rem_p != rem_q, (
            "JSON named entries did not distinguish local-store presence "
            f"on pointer worktrees: {rem_p!r} vs {rem_q!r}"
        )


# ---------------------------------------------------------------------------
# H. Filtering and output options
# ---------------------------------------------------------------------------


def test_ls_files_long_includes_full_oid():
    """--long listing carries the independently computed full object id."""
    with workspace() as ws:
        rel = _rel("lg")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        result = run_ls_files(ws, ["--long"])
        require_success(result)
        text = listing_visible(result)
        print(f"long_listing={text!r} oid={oid}")
        require_visible_contains(result, rel)
        assert oid in text, (
            f"--long listing does not carry the full object id {oid}: {text!r}"
        )


def test_ls_files_size_has_visible_effect_and_follows_byte_length():
    """--size is distinguishable from default and follows object byte length."""
    with workspace() as ws:
        rel = _rel("sz")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        base = run_ls_files(ws)
        require_success(base)
        require_visible_contains(base, rel)
        print(f"size_default={listing_visible(base)!r}")
        sized = run_ls_files(ws, ["--size"])
        require_success(sized)
        require_visible_contains(sized, rel)
        print(f"size_flag={listing_visible(sized)!r}")
        extra = [_abs(ws, rel)]
        def_rem = _strip_path_oid_payload(
            listing_visible(base), path=rel, oid=oid, payload=data, extra=extra
        )
        size_rem = _strip_path_oid_payload(
            listing_visible(sized), path=rel, oid=oid, payload=data, extra=extra
        )
        print(f"size_vs_default def={def_rem!r} size={size_rem!r}")
        assert def_rem != size_rem, (
            "--size remainder after stripping path/oid was not "
            "distinguishable from the default listing"
        )
    with workspace() as small_ws:
        rel_s = _rel("sz")
        data_s = _payload(81)
        oid_s = _prepare(small_ws, rel_s, data_s)
        small = run_ls_files(small_ws, ["--size"])
        require_success(small)
        small_rem = _strip_path_oid_payload(
            listing_visible(small),
            path=rel_s,
            oid=oid_s,
            payload=data_s,
            extra=[_abs(small_ws, rel_s)],
        )
        print(f"size_small={small_rem!r}")
    with workspace() as big_ws:
        rel_b = _rel("sz")
        data_b = _payload(481)
        oid_b = _prepare(big_ws, rel_b, data_b)
        big = run_ls_files(big_ws, ["--size"])
        require_success(big)
        big_rem = _strip_path_oid_payload(
            listing_visible(big),
            path=rel_b,
            oid=oid_b,
            payload=data_b,
            extra=[_abs(big_ws, rel_b)],
        )
        print(f"size_big={big_rem!r}")
        assert small_rem != big_rem, (
            "--size remainders for two object byte lengths were not "
            f"distinguishable after stripping path/oid/payload: "
            f"{small_rem!r} vs {big_rem!r}"
        )


def test_ls_files_name_only_is_distinguishable():
    """--name-only names the path and is hard-distinguishable from default."""
    with workspace() as ws:
        rel = _rel("nm")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        base = run_ls_files(ws)
        require_success(base)
        require_visible_contains(base, rel)
        print(f"nameonly_default={listing_visible(base)!r}")
        named = run_ls_files(ws, ["--name-only"])
        require_success(named)
        require_visible_contains(named, rel)
        print(f"nameonly_flag={listing_visible(named)!r}")
        def_rem = strip_listing_covariates(listing_visible(base), [rel])
        name_rem = strip_listing_covariates(
            listing_visible(named), [rel, _abs(ws, rel)]
        )
        oid_in_default = oid in def_rem
        oid_in_name = oid in name_rem
        print(
            f"nameonly rem_def={def_rem!r} rem_name={name_rem!r} "
            f"oid_in_default={oid_in_default} oid_in_name={oid_in_name}"
        )
        distinguishable = def_rem != name_rem or (
            oid_in_default and not oid_in_name
        )
        assert distinguishable, (
            "--name-only was not distinguishable from the default listing "
            "after stripping the path, and the full object id was not "
            "present only on the default arm"
        )


def test_ls_files_include_exclude_and_untracked_include_is_not_echo():
    """Include/exclude select LFS paths; include of an untracked path is not echo."""
    with workspace() as ws:
        path_p, path_q = _assert_distinct(_rel("p"), _rel("q"))
        path_r = _rel("r")
        _assert_distinct(path_p, path_q, path_r)
        _init_tracked(ws)
        commit_tracked_payload(ws, path_p, _payload(221))
        commit_tracked_payload(ws, path_q, _payload(361))
        included = run_ls_files(ws, [f"--include={path_p}"])
        require_success(included)
        print(f"include_p={listing_visible(included)!r}")
        require_visible_contains(included, path_p)
        require_visible_omits(included, path_q)
        excluded = run_ls_files(ws, [f"--exclude={path_p}"])
        require_success(excluded)
        print(f"exclude_p={listing_visible(excluded)!r}")
        require_visible_contains(excluded, path_q)
        require_visible_omits(excluded, path_p)
        echo = run_ls_files(ws, [f"--include={path_r}"])
        require_success(echo)
        print(f"include_r={listing_visible(echo)!r}")
        rem_p = strip_listing_covariates(
            listing_visible(included),
            [path_p, path_q, path_r, _abs(ws, path_p), str(ws.path.resolve())],
        )
        rem_r = strip_listing_covariates(
            listing_visible(echo),
            [path_p, path_q, path_r, _abs(ws, path_r), str(ws.path.resolve())],
        )
        print(f"include_echo rem_p={rem_p!r} rem_r={rem_r!r}")
        assert rem_p != rem_r, (
            "--include of a never-tracked path was not distinguishable "
            "from a matching include after stripping filter words"
        )


def test_ls_files_all_sees_other_branch_object_current_deleted_does_not():
    """--all lists an other-branch-only object; current --deleted does not."""
    with workspace() as ws:
        _init_tracked(ws)
        path_m, path_c, path_y = _assert_distinct(_rel("m"), _rel("c"), _rel("y"))
        commit_tracked_payload(ws, path_m, _payload(81))
        main = _branch_name(ws)
        other = f"br_{token()}"
        _git_ok(ws, ["checkout", "-b", other])
        commit_tracked_payload(ws, path_c, _payload(221))
        _git_ok(ws, ["checkout", main])
        commit_tracked_payload(ws, path_y, _payload(361))
        _git_ok(ws, ["rm", "--", path_y])
        _git_ok(ws, ["commit", "-m", f"drop {path_y}"])
        default = run_ls_files(ws)
        require_success(default)
        require_visible_contains(default, path_m)
        require_visible_omits(default, path_c)
        print(f"default_current={listing_visible(default)!r}")
        deleted = run_ls_files(ws, ["--deleted"])
        require_success(deleted)
        require_visible_contains(deleted, path_y)
        require_visible_omits(deleted, path_c)
        print(f"deleted_current={listing_visible(deleted)!r}")
        all_hist = run_ls_files(ws, ["--all"])
        require_success(all_hist)
        print(f"all_history={listing_visible(all_hist)!r}")
        require_visible_contains(all_hist, path_c)
        require_visible_contains(all_hist, path_m)


def test_ls_files_deleted_lists_current_history_deletion():
    """Include-deleted listing names a path deleted on the current ref."""
    with workspace() as ws:
        rel = _rel("del")
        _prepare(ws, rel, _payload(221))
        _git_ok(ws, ["rm", "--", rel])
        _git_ok(ws, ["commit", "-m", f"drop {rel}"])
        default = run_ls_files(ws)
        require_success(default)
        require_visible_omits(default, rel)
        print(f"deleted_default={listing_visible(default)!r}")
        deleted = run_ls_files(ws, ["--deleted"])
        require_success(deleted)
        print(f"deleted_flag={listing_visible(deleted)!r}")
        require_visible_contains(deleted, rel)


def test_ls_files_debug_overrides_json():
    """debug+JSON is the debug format, distinguishable from JSON-only."""
    with workspace() as ws:
        rel = _rel("db")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        extra = [_abs(ws, rel), str(ws.path.resolve())]
        js = run_ls_files(ws, ["--json"])
        require_success(js)
        parsed = extract_json_listing(js)
        json_strings_include(parsed, rel)
        print(f"json_only={parsed!r}")
        debug = run_ls_files(ws, ["--debug"])
        require_success(debug)
        require_visible_contains(debug, rel)
        print(f"debug_only={listing_visible(debug)!r}")
        default = run_ls_files(ws)
        require_success(default)
        require_visible_contains(default, rel)
        print(f"default_named={listing_visible(default)!r}")
        combo = run_ls_files(ws, ["--debug", "--json"])
        require_success(combo)
        require_visible_contains(combo, rel)
        print(f"debug_json_visible={listing_visible(combo)!r}")
        kwargs = dict(
            paths=[rel],
            oids=[oid],
            worktree_blobs=[data],
            pointers=[],
            sizes=[len(data)],
            abs_paths=extra,
        )
        json_rem = listing_observation_remainder(listing_visible(js), **kwargs)
        debug_rem = listing_observation_remainder(
            listing_visible(debug), **kwargs
        )
        default_rem = listing_observation_remainder(
            listing_visible(default), **kwargs
        )
        combo_rem = listing_observation_remainder(
            listing_visible(combo), **kwargs
        )
        combo_core = listing_without_json_document(combo)
        core_rem = listing_observation_remainder(combo_core, **kwargs)
        print(
            f"json_rem={json_rem!r} debug_rem={debug_rem!r} "
            f"default_rem={default_rem!r} combo_rem={combo_rem!r} "
            f"combo_core_rem={core_rem!r} combo_core={combo_core!r}"
        )
        assert debug_rem != json_rem, (
            "debug-only remainder was not distinguishable from JSON-only "
            f"after covariate stripping: {debug_rem!r}"
        )
        assert debug_rem != default_rem, (
            "debug-only remainder was not distinguishable from the default "
            f"named-path listing after covariate stripping: {debug_rem!r}"
        )
        assert combo_rem != json_rem, (
            "debug+JSON remainder was not distinguishable from JSON-only "
            f"after covariate stripping: {combo_rem!r}"
        )
        assert combo_rem != default_rem, (
            "debug+JSON remainder was the default named-path listing, "
            f"not the debug format: {combo_rem!r}"
        )
        assert core_rem == debug_rem, (
            "debug+JSON with any JSON document excised was not the debug "
            f"format after covariate stripping: {core_rem!r} vs {debug_rem!r}"
        )


def test_ls_files_json_ignores_long_size_name_only():
    """Under JSON, long/size/name-only do not change the listing."""
    with workspace() as ws:
        rel = _rel("js")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        extra = [_abs(ws, rel)]
        default = run_ls_files(ws)
        require_success(default)
        require_visible_contains(default, rel)
        default_text = listing_visible(default)
        print(f"json_ignore_default={default_text!r}")

        long_only = run_ls_files(ws, ["--long"])
        require_success(long_only)
        require_visible_contains(long_only, rel)
        long_text = listing_visible(long_only)
        print(f"json_ignore_long={long_text!r} oid={oid}")
        assert oid in long_text, (
            f"--long listing does not carry the full object id {oid}: "
            f"{long_text!r}"
        )
        assert long_text != default_text, (
            "--long listing was not distinguishable from the default "
            "listing; cannot measure that JSON makes --long have no effect"
        )

        sized = run_ls_files(ws, ["--size"])
        require_success(sized)
        require_visible_contains(sized, rel)
        print(f"json_ignore_size={listing_visible(sized)!r}")
        def_rem = _strip_path_oid_payload(
            default_text, path=rel, oid=oid, payload=data, extra=extra
        )
        size_rem = _strip_path_oid_payload(
            listing_visible(sized),
            path=rel,
            oid=oid,
            payload=data,
            extra=extra,
        )
        print(f"json_ignore_size_vs_default def={def_rem!r} size={size_rem!r}")
        assert def_rem != size_rem, (
            "--size remainder after stripping path/oid was not "
            "distinguishable from the default listing; cannot measure "
            "that JSON makes --size have no effect"
        )

        named = run_ls_files(ws, ["--name-only"])
        require_success(named)
        require_visible_contains(named, rel)
        print(f"json_ignore_nameonly={listing_visible(named)!r}")
        def_name_rem = strip_listing_covariates(default_text, [rel])
        name_rem = strip_listing_covariates(
            listing_visible(named), [rel, _abs(ws, rel)]
        )
        oid_in_default = oid in def_name_rem
        oid_in_name = oid in name_rem
        print(
            f"json_ignore_nameonly rem_def={def_name_rem!r} "
            f"rem_name={name_rem!r} oid_in_default={oid_in_default} "
            f"oid_in_name={oid_in_name}"
        )
        distinguishable = def_name_rem != name_rem or (
            oid_in_default and not oid_in_name
        )
        assert distinguishable, (
            "--name-only was not distinguishable from the default listing "
            "after stripping the path, and the full object id was not "
            "present only on the default arm; cannot measure that JSON "
            "makes --name-only have no effect"
        )

        base = run_ls_files(ws, ["--json"])
        require_success(base)
        parsed_base = extract_json_listing(base)
        json_strings_include(parsed_base, rel)
        extra_tokens = [rel, oid, data.decode("utf-8"), _abs(ws, rel)]
        base_rem = strip_listing_covariates(listing_visible(base), extra_tokens)
        print(f"json_base_rem={base_rem!r}")
        for flag in (["--long"], ["--size"], ["--name-only"]):
            result = run_ls_files(ws, ["--json", *flag])
            require_success(result)
            parsed = extract_json_listing(result)
            print(f"json_plus_{flag}={parsed!r}")
            assert parsed == parsed_base, (
                f"JSON listing with {flag} was not equal as JSON to "
                f"--json alone: {parsed!r} vs {parsed_base!r}"
            )
            rem = strip_listing_covariates(listing_visible(result), extra_tokens)
            assert rem == base_rem, (
                f"caller-visible JSON with {flag} differed after "
                f"stripping path/oid: {rem!r} vs {base_rem!r}"
            )


def test_ls_files_direct_binary_names_current_tree_path():
    """Direct binary ls-files names a known current-tree LFS path."""
    with workspace() as ws:
        rel = _rel("bin")
        _prepare(ws, rel, _payload(221))
        result = ws.invoke(["ls-files"])
        assert_success(result)
        print(f"direct_ls_files={listing_visible(result)!r}")
        assert_visible_contains(result, rel)


# ---------------------------------------------------------------------------
# I. Invalid combinations and invalid refs
# ---------------------------------------------------------------------------


def test_ls_files_all_with_explicit_ref_is_invalid():
    """Entire-history listing cannot be combined with an explicit ref."""
    with workspace() as ok_ws:
        rel = _rel("al")
        _prepare(ok_ws, rel, _payload(221))
        main = _branch_name(ok_ws)
        other = f"br_{token()}"
        _git_ok(ok_ws, ["checkout", "-b", other])
        commit_tracked_payload(ok_ws, _rel("c"), _payload(361))
        _git_ok(ok_ws, ["checkout", main])
        ok = run_ls_files(ok_ws, ["--all"])
        require_success(ok)
        require_visible_contains(ok, rel)
        print(f"all_ok={listing_visible(ok)!r}")
        dirty = run_ls_files(ok_ws, ["--all", main])
        print(f"all_plus_ref_exit={dirty.returncode}")
        require_invalid_unlike_success(ok, dirty)


def test_ls_files_deleted_with_two_refs_is_invalid():
    """Include-deleted cannot combine with two refs; one non-current ref works."""
    with workspace() as ok_ws:
        _init_tracked(ok_ws)
        path_main = _rel("m")
        prepare_tracked_commit(ok_ws, path_main, _payload(81))
        main = _branch_name(ok_ws)
        other = f"br_{token()}"
        path_z = _rel("z")
        _git_ok(ok_ws, ["checkout", "-b", other])
        commit_tracked_payload(ok_ws, path_z, _payload(221))
        _git_ok(ok_ws, ["rm", "--", path_z])
        _git_ok(ok_ws, ["commit", "-m", f"drop {path_z}"])
        _git_ok(ok_ws, ["checkout", main])
        ok = run_ls_files(ok_ws, ["--deleted", other])
        require_success(ok)
        print(f"deleted_other={listing_visible(ok)!r}")
        require_visible_contains(ok, path_z)
    with workspace() as dirty_ws:
        _init_tracked(dirty_ws)
        path_main = _rel("m")
        prepare_tracked_commit(dirty_ws, path_main, _payload(81))
        main = _branch_name(dirty_ws)
        other = f"br_{token()}"
        path_z = _rel("z")
        _git_ok(dirty_ws, ["checkout", "-b", other])
        commit_tracked_payload(dirty_ws, path_z, _payload(221))
        _git_ok(dirty_ws, ["rm", "--", path_z])
        _git_ok(dirty_ws, ["commit", "-m", f"drop {path_z}"])
        _git_ok(dirty_ws, ["checkout", main])
        dirty = run_ls_files(dirty_ws, ["--deleted", other, main])
        print(f"deleted_two_refs_exit={dirty.returncode}")
        require_invalid_unlike_success(ok, dirty)


def test_ls_files_long_with_current_branch_succeeds():
    """Other options plus one explicit current-branch ref still succeed."""
    with workspace() as ws:
        rel = _rel("lg")
        data = _payload(221)
        oid = _prepare(ws, rel, data)
        branch = _branch_name(ws)
        result = run_ls_files(ws, ["--long", branch])
        require_success(result)
        text = listing_visible(result)
        print(f"long_branch={text!r} branch={branch!r} oid={oid}")
        require_visible_contains(result, rel)
        assert oid in text, (
            f"--long plus current branch did not carry the full object id "
            f"{oid}: {text!r}"
        )


def test_ls_files_invalid_ref_fails():
    """An invalid ref is non-success relative to a legal ref that lists a path."""
    with workspace() as ok_ws:
        rel = _rel("rf")
        _prepare(ok_ws, rel, _payload(221))
        branch = _branch_name(ok_ws)
        ok = run_ls_files(ok_ws, [branch])
        require_success(ok)
        require_visible_contains(ok, rel)
        print(f"valid_ref={listing_visible(ok)!r}")
    with workspace() as dirty_ws:
        rel = _rel("rf")
        _prepare(dirty_ws, rel, _payload(221))
        missing = f"missing_{token()}"
        dirty = run_ls_files(dirty_ws, [missing])
        print(f"invalid_ref_exit={dirty.returncode} ref={missing!r}")
        require_invalid_unlike_success(ok, dirty)
