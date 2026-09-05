# feature: F08
"""Fetch, pull, checkout, and clone porcelain acceptance tests.

PRD: FP-08. Assertions stay at the PRD's precision: store vs working-tree
bytes, glob restriction, include/exclude, recent vs all-mode, stdin refs,
prune/refetch/dry-run, JSON transfer-plan contrast at fixed occupancy,
clone batch accounting plus GET of action paths, and distinguished
non-success outcomes. Message wording, exit-code numbers, JSON keys,
and flag spellings in output are not pinned.
"""

from __future__ import annotations

from pathlib import Path

from _harness import reserve_loopback_port, token, workspace
from _helpers import (
    HOOK_TYPES,
    assert_gets_of_action_paths,
    assert_invalid_unlike_success,
    assert_json_plan_stable_unlike,
    assert_no_contact_of,
    assert_object_absent,
    assert_object_bytes,
    assert_working_tree_bytes,
    assert_working_tree_pointer,
    commit_tracked_payload,
    configure_fetch_exclude,
    configure_fetch_include,
    configure_recentness,
    configure_unreachable_endpoint,
    conforming_batch_server,
    default_lfs_store_root,
    default_lfs_store_root_at,
    git_dir_at,
    index_blob,
    path_without_product_bin,
    point_lfs_at,
    prepare_tracked_commit,
    read_git_orbulk_hook_bodies_at,
    recording_api_server,
    remove_stored_object,
    require_download_batch_accounts_for_oids,
    require_gets_of_action_paths,
    require_git_repository_at,
    require_object_absent,
    require_object_bytes,
    require_success,
    require_working_tree_bytes,
    require_working_tree_pointer,
    run_track,
    sha256_hex,
    sharded_object_rel,
    snapshot_working_tree,
    write_pointer_placeholders_from_index,
)


def _payload() -> bytes:
    return f"blob-{token()}\n".encode("utf-8")


def _tracked_rel(prefix: str = "payload") -> str:
    return f"{prefix}_{token()}.bin"


def _two_tracked_paths() -> tuple[str, str]:
    return f"keep_{token()}.bin", f"skip_{token()}.bin"


def _three_tracked_paths() -> tuple[str, str, str]:
    return (
        f"aaa_{token()}.bin",
        f"keep_{token()}.bin",
        f"zzz_{token()}.bin",
    )


def _setup_tracked(ws, svc, items: list[tuple[str, bytes]]) -> list[str]:
    ws.init_repo()
    point_lfs_at(ws, svc.url)
    digests: list[str] = []
    for index, (rel, data) in enumerate(items):
        if index == 0:
            digests.append(prepare_tracked_commit(ws, rel, data))
        else:
            digests.append(commit_tracked_payload(ws, rel, data))
    return digests


def _wipe_store(ws, digests: list[str]) -> None:
    store = default_lfs_store_root(ws)
    for digest in digests:
        remove_stored_object(ws, digest)
        require_object_absent(store, digest)


def _plant(ws, rels: list[str]) -> dict[str, bytes]:
    return write_pointer_placeholders_from_index(ws, rels)


def _records_since(svc, start: int) -> list:
    return svc.records[start:]


def _checkout_other_unique(
    ws, rel_keep: str, rel_other: str, data_other: bytes
) -> tuple[str, str]:
    """Create a sibling branch that has *rel_other* and not *rel_keep*."""
    branch = f"br_{token()}"
    created = ws.git(["checkout", "-b", branch])
    assert created.returncode == 0, (
        f"git checkout -b {branch} failed: {created.stderr_text}"
    )
    removed = ws.git(["rm", "--", rel_keep])
    assert removed.returncode == 0, (
        f"git rm {rel_keep!r} failed: {removed.stderr_text}"
    )
    digest = commit_tracked_payload(ws, rel_other, data_other)
    back = ws.git(["checkout", "main"])
    assert back.returncode == 0, (
        f"git checkout main failed: {back.stderr_text}"
    )
    return branch, digest


def _commit_dated(ws, rel: str, data: bytes, when: str) -> str:
    ws.write(rel, data)
    digest = sha256_hex(data)
    added = ws.git(["add", "--", rel])
    assert added.returncode == 0, added.stderr_text
    committed = ws.git(
        ["commit", "-m", f"dated {rel}"],
        env_updates={
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
        },
    )
    assert committed.returncode == 0, committed.stderr_text
    return digest


def _implant_unreferenced(ws, content: bytes) -> str:
    digest = sha256_hex(content)
    store = default_lfs_store_root(ws)
    path = store / sharded_object_rel(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    require_object_bytes(store, digest, content)
    return digest


def _implant_object_at(ws, cwd, digest: str, content: bytes) -> Path:
    """Setup: write *content* into the local store of the repository at *cwd*."""
    store = default_lfs_store_root_at(ws, cwd)
    path = store / sharded_object_rel(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    require_object_bytes(store, digest, content)
    return path


def _store_occupancy(store: Path) -> dict[str, bytes]:
    """Snapshot regular files under a local object-store root."""
    root = Path(store)
    found: dict[str, bytes] = {}
    try:
        exists = root.exists()
    except OSError as exc:
        raise AssertionError(f"cannot stat store {root}: {exc}") from exc
    if not exists:
        return found
    for path in sorted(root.rglob("*")):
        try:
            is_file = path.is_file()
        except OSError as exc:
            raise AssertionError(f"cannot stat store path {path}: {exc}") from exc
        if not is_file:
            continue
        try:
            found[str(path.relative_to(root))] = path.read_bytes()
        except OSError as exc:
            raise AssertionError(f"cannot read store path {path}: {exc}") from exc
    return found


def _install_global_filters(ws) -> None:
    require_success(ws.invoke_via_git(["install", "--skip-repo"]))


def _empty_clone_template(ws) -> Path:
    """A clone template whose hooks directory does not name VCS Orbulk.

    Includes a description file so Git treats the directory as a real
    template and does not fall back to the default template set.
    """
    tmpl = ws.resolve(f"tmpl_{token()}")
    (tmpl / "hooks").mkdir(parents=True)
    (tmpl / "description").write_text("empty-template\n", encoding="utf-8")
    return tmpl


def _clear_repo_hook_files(ws, cwd) -> None:
    """Setup: remove hook files so a later clone cannot inherit them."""
    hooks = git_dir_at(ws, cwd) / "hooks"
    for hook_type in HOOK_TYPES:
        path = hooks / hook_type
        try:
            is_file = path.is_file()
        except OSError as exc:
            raise AssertionError(f"cannot stat hook {path}: {exc}") from exc
        if not is_file:
            continue
        try:
            path.unlink()
        except OSError as exc:
            raise AssertionError(f"cannot clear hook {path}: {exc}") from exc


def _prepare_clone_source(
    ws,
    src_rel: str,
    url: str,
    items: list[tuple[str, bytes]],
    *,
    extra_lfsconfig: dict[str, str] | None = None,
):
    src = ws.init_repo(src_rel)
    require_success(
        ws.invoke_via_git(["install", "--local", "--skip-repo"], cwd=src)
    )
    written = ws.git_config_set(
        "lfs.url", url, file=".lfsconfig", cwd=src
    )
    assert written.returncode == 0, (
        f"writing lfs.url into .lfsconfig failed: {written.stderr_text}"
    )
    if extra_lfsconfig:
        for key, value in extra_lfsconfig.items():
            extra = ws.git_config_set(key, value, file=".lfsconfig", cwd=src)
            assert extra.returncode == 0, extra.stderr_text
    added = ws.git(["add", "--", ".lfsconfig"], cwd=src)
    assert added.returncode == 0, added.stderr_text
    committed = ws.git(["commit", "-m", "lfsconfig"], cwd=src)
    assert committed.returncode == 0, committed.stderr_text
    suffix = Path(items[0][0]).suffix
    assert suffix, f"clone source path has no suffix: {items[0][0]!r}"
    require_success(run_track(ws, [f"*{suffix}"], cwd=src))
    digests: list[str] = []
    for rel, data in items:
        ws.write(f"{src_rel}/{rel}", data)
        digest = sha256_hex(data)
        to_add = [rel]
        try:
            ws.read_bytes(f"{src_rel}/.gitattributes")
            to_add.append(".gitattributes")
        except FileNotFoundError:
            pass
        added = ws.git(["add", "--", *to_add], cwd=src)
        assert added.returncode == 0, added.stderr_text
        committed = ws.git(["commit", "-m", f"add {rel}"], cwd=src)
        assert committed.returncode == 0, committed.stderr_text
        digests.append(digest)
    # Track installs repository hooks as a side effect. A later local clone
    # must not inherit those files, or dest-hook observations would measure
    # the source rather than clone's own install-or-skip choice.
    _clear_repo_hook_files(ws, src)
    return src, digests


def _head_oid_at(ws, cwd) -> str:
    result = ws.git(["rev-parse", "HEAD"], cwd=cwd)
    assert result.returncode == 0, (
        f"git rev-parse HEAD failed cwd={cwd}: {result.stderr_text}"
    )
    oid = result.stdout_text.strip()
    assert oid, "git rev-parse HEAD produced no oid"
    return oid


# ---------------------------------------------------------------------------
# A. Fetch: store only, omitted remote/refs
# ---------------------------------------------------------------------------


def test_fetch_populates_store_without_changing_working_tree():
    """Fetch writes the local store and leaves working-tree bytes unchanged."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc, [(rel, payload)])[0]
            _wipe_store(ws, [digest])
            planted = _plant(ws, [rel])
            result = ws.invoke_via_git(["fetch"])
            print(f"fetch exit={result.returncode} digest={digest}")
            require_success(result)
            require_object_bytes(default_lfs_store_root(ws), digest, payload)
            after = snapshot_working_tree(ws, [rel])
            assert after[rel] == planted[rel], (
                "fetch changed working-tree bytes"
            )


def test_fetch_omitted_refs_uses_current_checkout_not_other_branch():
    """Omitting refs fetches the current checkout, not another branch."""
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("oth")
    data_a = _payload()
    data_b = _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as ws:
            digest_a = _setup_tracked(ws, svc, [(rel_a, data_a)])[0]
            branch, digest_b = _checkout_other_unique(
                ws, rel_a, rel_b, data_b
            )
            print(f"other_branch={branch} a={digest_a} b={digest_b}")
            _wipe_store(ws, [digest_a, digest_b])
            _plant(ws, [rel_a])
            result = ws.invoke_via_git(["fetch"])
            require_success(result)
            store = default_lfs_store_root(ws)
            require_object_bytes(store, digest_a, data_a)
            require_object_absent(store, digest_b)


def test_explicit_ref_fetches_that_ref_unlike_current_only():
    """Naming a ref fetches that ref; omitting refs does not."""
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("oth")
    data_a = _payload()
    data_b = _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as omitted:
            digest_a = _setup_tracked(omitted, svc, [(rel_a, data_a)])[0]
            branch, digest_b = _checkout_other_unique(
                omitted, rel_a, rel_b, data_b
            )
            _wipe_store(omitted, [digest_a, digest_b])
            _plant(omitted, [rel_a])
            omit_run = omitted.invoke_via_git(["fetch"])
            require_success(omit_run)
            require_object_absent(default_lfs_store_root(omitted), digest_b)
        with workspace() as named:
            _setup_tracked(named, svc, [(rel_a, data_a)])
            branch, digest_b = _checkout_other_unique(
                named, rel_a, rel_b, data_b
            )
            _wipe_store(named, [sha256_hex(data_a), digest_b])
            _plant(named, [rel_a])
            named_run = named.invoke_via_git(["fetch", "origin", branch])
            print(
                f"omit exit={omit_run.returncode} "
                f"named exit={named_run.returncode} ref={branch}"
            )
            require_success(named_run)
            require_object_bytes(
                default_lfs_store_root(named), digest_b, data_b
            )


def test_direct_binary_fetch_same_store_and_worktree_invariant():
    """Direct binary fetch writes the store and leaves the working tree."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc, [(rel, payload)])[0]
            _wipe_store(ws, [digest])
            planted = _plant(ws, [rel])
            result = ws.invoke(["fetch"])
            print(f"direct fetch exit={result.returncode}")
            require_success(result)
            require_object_bytes(default_lfs_store_root(ws), digest, payload)
            after = snapshot_working_tree(ws, [rel])
            assert after[rel] == planted[rel], (
                "direct binary fetch changed working-tree bytes"
            )


# ---------------------------------------------------------------------------
# B. Include / exclude (fetch CLI overrides config; pull both options)
# ---------------------------------------------------------------------------


def test_config_include_fetches_only_matching_path():
    """Configured include fetches only the matching path."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as ws:
            digests = _setup_tracked(
                ws, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_include(ws, keep)
            _wipe_store(ws, digests)
            _plant(ws, [keep, skip])
            require_success(ws.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(ws)
            assert_object_bytes(store, digests[0], data_keep)
            assert_object_absent(store, digests[1])


def test_cli_include_overrides_config_include():
    """CLI include replaces configured include."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as configured:
            digests = _setup_tracked(
                configured, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_include(configured, keep)
            _wipe_store(configured, digests)
            _plant(configured, [keep, skip])
            require_success(configured.invoke_via_git(["fetch"]))
            store_c = default_lfs_store_root(configured)
            assert_object_bytes(store_c, digests[0], data_keep)
            assert_object_absent(store_c, digests[1])
        with workspace() as overridden:
            digests = _setup_tracked(
                overridden, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_include(overridden, keep)
            _wipe_store(overridden, digests)
            _plant(overridden, [keep, skip])
            require_success(
                overridden.invoke_via_git(["fetch", "--include", skip])
            )
            store_o = default_lfs_store_root(overridden)
            print(f"cli include skip={skip!r} keep={keep!r}")
            assert_object_bytes(store_o, digests[1], data_skip)
            assert_object_absent(store_o, digests[0])


def test_config_exclude_skips_matching_path():
    """Configured exclude skips the matching path."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as ws:
            digests = _setup_tracked(
                ws, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(ws, skip)
            _wipe_store(ws, digests)
            _plant(ws, [keep, skip])
            require_success(ws.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(ws)
            assert_object_bytes(store, digests[0], data_keep)
            assert_object_absent(store, digests[1])


def test_cli_exclude_overrides_config_exclude():
    """CLI exclude replaces configured exclude."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as configured:
            digests = _setup_tracked(
                configured, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(configured, skip)
            _wipe_store(configured, digests)
            _plant(configured, [keep, skip])
            require_success(configured.invoke_via_git(["fetch"]))
            assert_object_absent(default_lfs_store_root(configured), digests[1])
        with workspace() as overridden:
            digests = _setup_tracked(
                overridden, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(overridden, skip)
            _wipe_store(overridden, digests)
            _plant(overridden, [keep, skip])
            require_success(
                overridden.invoke_via_git(["fetch", "--exclude", keep])
            )
            store = default_lfs_store_root(overridden)
            print(f"cli exclude keep={keep!r}")
            assert_object_absent(store, digests[0])
            assert_object_bytes(store, digests[1], data_skip)


def test_pull_include_fetches_and_checkouts_only_matching_path():
    """Pull include materializes only the matching path."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as baseline:
            digests = _setup_tracked(
                baseline, svc, [(keep, data_keep), (skip, data_skip)]
            )
            _wipe_store(baseline, digests)
            _plant(baseline, [keep, skip])
            require_success(baseline.invoke_via_git(["pull"]))
            assert_working_tree_bytes(baseline, keep, data_keep)
            assert_working_tree_bytes(baseline, skip, data_skip)
        with workspace() as limited:
            digests = _setup_tracked(
                limited, svc, [(keep, data_keep), (skip, data_skip)]
            )
            _wipe_store(limited, digests)
            _plant(limited, [keep, skip])
            require_success(
                limited.invoke_via_git(["pull", "--include", keep])
            )
            print(f"pull include keep={keep!r} skip={skip!r}")
            assert_working_tree_bytes(limited, keep, data_keep)
            assert_working_tree_pointer(
                limited, skip, digest=digests[1], size=len(data_skip)
            )
            assert_object_absent(default_lfs_store_root(limited), digests[1])


def test_pull_exclude_skips_matching_path():
    """Pull exclude leaves the excluded path as a pointer and unfetched."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as baseline:
            digests = _setup_tracked(
                baseline, svc, [(keep, data_keep), (skip, data_skip)]
            )
            _wipe_store(baseline, digests)
            _plant(baseline, [keep, skip])
            require_success(baseline.invoke_via_git(["pull"]))
            assert_working_tree_bytes(baseline, skip, data_skip)
        with workspace() as limited:
            digests = _setup_tracked(
                limited, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(limited, skip)
            _wipe_store(limited, digests)
            _plant(limited, [keep, skip])
            require_success(limited.invoke_via_git(["pull"]))
            print(f"pull exclude skip={skip!r}")
            assert_working_tree_bytes(limited, keep, data_keep)
            assert_working_tree_pointer(
                limited, skip, digest=digests[1], size=len(data_skip)
            )
            assert_object_absent(default_lfs_store_root(limited), digests[1])


# ---------------------------------------------------------------------------
# C. Recent vs default vs all-mode
# ---------------------------------------------------------------------------


def _setup_recent_layout(ws, svc, data_a, data_b, data_c):
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("rec")
    rel_c = _tracked_rel("old")
    digest_a = _setup_tracked(ws, svc, [(rel_a, data_a)])[0]
    branch_b, digest_b = _checkout_other_unique(ws, rel_a, rel_b, data_b)
    branch_c = f"old_{token()}"
    created = ws.git(["checkout", "-b", branch_c])
    assert created.returncode == 0, created.stderr_text
    removed = ws.git(["rm", "--", rel_a])
    assert removed.returncode == 0, removed.stderr_text
    digest_c = _commit_dated(
        ws, rel_c, data_c, "2020-01-15T12:00:00 +0000"
    )
    back = ws.git(["checkout", "main"])
    assert back.returncode == 0, back.stderr_text
    configure_recentness(ws, ref_days=7)
    _wipe_store(ws, [digest_a, digest_b, digest_c])
    _plant(ws, [rel_a])
    return {
        "rel_a": rel_a,
        "branch_b": branch_b,
        "branch_c": branch_c,
        "digest_a": digest_a,
        "digest_b": digest_b,
        "digest_c": digest_c,
        "data_a": data_a,
        "data_b": data_b,
        "data_c": data_c,
    }


def test_recent_fetch_includes_other_recent_branch_unlike_default():
    """Recent fetch includes another recent branch that default omits."""
    data_a, data_b, data_c = _payload(), _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b, data_c]
    ) as svc:
        with workspace() as default:
            layout = _setup_recent_layout(default, svc, data_a, data_b, data_c)
            require_success(default.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(default)
            require_object_bytes(store, layout["digest_a"], data_a)
            require_object_absent(store, layout["digest_b"])
            require_object_absent(store, layout["digest_c"])
        with workspace() as recent:
            layout = _setup_recent_layout(recent, svc, data_a, data_b, data_c)
            require_success(recent.invoke_via_git(["fetch", "--recent"]))
            store = default_lfs_store_root(recent)
            print(
                f"recent branch={layout['branch_b']} "
                f"old={layout['branch_c']}"
            )
            require_object_bytes(store, layout["digest_a"], data_a)
            require_object_bytes(store, layout["digest_b"], data_b)
            require_object_absent(store, layout["digest_c"])


def test_recent_fetch_omits_outside_window_unlike_all_mode():
    """Recent omits an out-of-window ref that no-ref all-mode fetches."""
    data_a, data_b, data_c = _payload(), _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b, data_c]
    ) as svc:
        with workspace() as recent:
            layout = _setup_recent_layout(recent, svc, data_a, data_b, data_c)
            require_success(recent.invoke_via_git(["fetch", "--recent"]))
            require_object_absent(
                default_lfs_store_root(recent), layout["digest_c"]
            )
        with workspace() as all_mode:
            layout = _setup_recent_layout(
                all_mode, svc, data_a, data_b, data_c
            )
            require_success(all_mode.invoke_via_git(["fetch", "--all"]))
            print(f"all-mode fetched old={layout['branch_c']}")
            require_object_bytes(
                default_lfs_store_root(all_mode),
                layout["digest_c"],
                data_c,
            )


# ---------------------------------------------------------------------------
# D. All-mode history / all refs / ignore configured filters / illegal combos
# ---------------------------------------------------------------------------


def test_all_mode_fetches_objects_reachable_from_history_unlike_current_tree():
    """All-mode with a given ref fetches history, not only the current tree."""
    rel = _tracked_rel()
    data_old, data_new = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_old, data_new]
    ) as svc:
        with workspace() as current:
            digest_old = _setup_tracked(current, svc, [(rel, data_old)])[0]
            digest_new = commit_tracked_payload(current, rel, data_new)
            _wipe_store(current, [digest_old, digest_new])
            _plant(current, [rel])
            require_success(current.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(current)
            assert_object_bytes(store, digest_new, data_new)
            assert_object_absent(store, digest_old)
        with workspace() as all_mode:
            digest_old = _setup_tracked(all_mode, svc, [(rel, data_old)])[0]
            digest_new = commit_tracked_payload(all_mode, rel, data_new)
            _wipe_store(all_mode, [digest_old, digest_new])
            _plant(all_mode, [rel])
            require_success(
                all_mode.invoke_via_git(["fetch", "--all", "origin", "main"])
            )
            store = default_lfs_store_root(all_mode)
            print(f"history old={digest_old} new={digest_new}")
            assert_object_bytes(store, digest_new, data_new)
            assert_object_bytes(store, digest_old, data_old)


def test_all_mode_without_refs_fetches_all_refs_unlike_given_ref():
    """No-ref all-mode fetches another ref's history; given-ref does not."""
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("hist")
    rel_d = _tracked_rel("tip")
    data_a, data_b, data_d = _payload(), _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b, data_d]
    ) as svc:
        def _layout(ws):
            digest_a = _setup_tracked(ws, svc, [(rel_a, data_a)])[0]
            branch = f"hist_{token()}"
            created = ws.git(["checkout", "-b", branch])
            assert created.returncode == 0, created.stderr_text
            removed = ws.git(["rm", "--", rel_a])
            assert removed.returncode == 0, removed.stderr_text
            digest_b = commit_tracked_payload(ws, rel_b, data_b)
            digest_d = commit_tracked_payload(ws, rel_d, data_d)
            deleted = ws.git(["rm", "--", rel_b])
            assert deleted.returncode == 0, deleted.stderr_text
            successor = ws.git(["commit", "-m", "drop hist object"])
            assert successor.returncode == 0, successor.stderr_text
            back = ws.git(["checkout", "main"])
            assert back.returncode == 0, back.stderr_text
            _wipe_store(ws, [digest_a, digest_b, digest_d])
            _plant(ws, [rel_a])
            return digest_a, digest_b, digest_d, branch

        with workspace() as given:
            digest_a, digest_b, _, branch = _layout(given)
            require_success(
                given.invoke_via_git(["fetch", "--all", "origin", "main"])
            )
            store = default_lfs_store_root(given)
            assert_object_bytes(store, digest_a, data_a)
            assert_object_absent(store, digest_b)
        with workspace() as none:
            digest_a, digest_b, _, branch = _layout(none)
            require_success(none.invoke_via_git(["fetch", "--all", "origin"]))
            store = default_lfs_store_root(none)
            print(f"no-ref all-mode hist_branch={branch}")
            assert_object_bytes(store, digest_a, data_a)
            assert_object_bytes(store, digest_b, data_b)


def test_all_mode_ignores_exclude_filters():
    """All-mode fetches a path that configured exclude would skip."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as filtered:
            digests = _setup_tracked(
                filtered, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(filtered, skip)
            _wipe_store(filtered, digests)
            _plant(filtered, [keep, skip])
            require_success(filtered.invoke_via_git(["fetch"]))
            assert_object_absent(
                default_lfs_store_root(filtered), digests[1]
            )
        with workspace() as all_mode:
            digests = _setup_tracked(
                all_mode, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_exclude(all_mode, skip)
            _wipe_store(all_mode, digests)
            _plant(all_mode, [keep, skip])
            require_success(all_mode.invoke_via_git(["fetch", "--all"]))
            print(f"all-mode include-exclude skip={skip!r}")
            assert_object_bytes(
                default_lfs_store_root(all_mode), digests[1], data_skip
            )


def test_all_mode_ignores_include_filters():
    """All-mode fetches a path that configured include would omit."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as filtered:
            digests = _setup_tracked(
                filtered, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_include(filtered, keep)
            _wipe_store(filtered, digests)
            _plant(filtered, [keep, skip])
            require_success(filtered.invoke_via_git(["fetch"]))
            assert_object_absent(
                default_lfs_store_root(filtered), digests[1]
            )
        with workspace() as all_mode:
            digests = _setup_tracked(
                all_mode, svc, [(keep, data_keep), (skip, data_skip)]
            )
            configure_fetch_include(all_mode, keep)
            _wipe_store(all_mode, digests)
            _plant(all_mode, [keep, skip])
            require_success(all_mode.invoke_via_git(["fetch", "--all"]))
            assert_object_bytes(
                default_lfs_store_root(all_mode), digests[1], data_skip
            )


def test_all_mode_rejected_with_recent_or_include_exclude_flags():
    """All-mode combined with recent or include/exclude flags is invalid."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as clean:
            digest = _setup_tracked(clean, svc, [(rel, payload)])[0]
            _wipe_store(clean, [digest])
            _plant(clean, [rel])
            ok = clean.invoke_via_git(["fetch", "--all"])
            require_success(ok)
            assert_object_bytes(
                default_lfs_store_root(clean), digest, payload
            )
        combos = (
            ["fetch", "--all", "--recent"],
            ["fetch", "--all", "--include", rel],
            ["fetch", "--all", "--exclude", rel],
        )
        for argv in combos:
            with workspace() as dirty:
                digest = _setup_tracked(dirty, svc, [(rel, payload)])[0]
                _wipe_store(dirty, [digest])
                _plant(dirty, [rel])
                failed = dirty.invoke_via_git(argv)
                print(f"illegal {argv} exit={failed.returncode}")
                assert_invalid_unlike_success(ok, failed)
                assert_object_absent(default_lfs_store_root(dirty), digest)


# ---------------------------------------------------------------------------
# E. Stdin, prune, refetch, dry-run, JSON plan
# ---------------------------------------------------------------------------


def test_fetch_refs_from_stdin_select_listed_ref():
    """Non-empty stdin selects the listed ref in place of the default."""
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("oth")
    data_a, data_b = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as other:
            digest_a = _setup_tracked(other, svc, [(rel_a, data_a)])[0]
            branch, digest_b = _checkout_other_unique(
                other, rel_a, rel_b, data_b
            )
            _wipe_store(other, [digest_a, digest_b])
            _plant(other, [rel_a])
            listed_other = other.invoke_via_git(
                ["fetch", "--stdin"],
                stdin=f"{branch}\n".encode("utf-8"),
            )
            require_success(listed_other)
            store = default_lfs_store_root(other)
            require_object_bytes(store, digest_b, data_b)
            require_object_absent(store, digest_a)
        with workspace() as current:
            digest_a = _setup_tracked(current, svc, [(rel_a, data_a)])[0]
            branch, digest_b = _checkout_other_unique(
                current, rel_a, rel_b, data_b
            )
            _wipe_store(current, [digest_a, digest_b])
            _plant(current, [rel_a])
            listed_cur = current.invoke_via_git(
                ["fetch", "--stdin"],
                stdin=b"main\n",
            )
            print(
                f"stdin other={branch} exit={listed_other.returncode} "
                f"stdin main exit={listed_cur.returncode}"
            )
            require_success(listed_cur)
            store = default_lfs_store_root(current)
            require_object_bytes(store, digest_a, data_a)
            require_object_absent(store, digest_b)


def test_fetch_prune_deletes_unreferenced_local_object_unlike_fetch_alone():
    """Prune-after-fetch deletes an unreferenced object; fetch alone does not."""
    rel = _tracked_rel()
    payload = _payload()
    junk = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as kept:
            digest = _setup_tracked(kept, svc, [(rel, payload)])[0]
            _wipe_store(kept, [digest])
            extra = _implant_unreferenced(kept, junk)
            _plant(kept, [rel])
            require_success(kept.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(kept)
            assert_object_bytes(store, extra, junk)
            assert_object_bytes(store, digest, payload)
        with workspace() as pruned:
            digest = _setup_tracked(pruned, svc, [(rel, payload)])[0]
            _wipe_store(pruned, [digest])
            extra = _implant_unreferenced(pruned, junk)
            _plant(pruned, [rel])
            require_success(pruned.invoke_via_git(["fetch", "--prune"]))
            store = default_lfs_store_root(pruned)
            print(f"prune extra={extra} payload={digest}")
            assert_object_absent(store, extra)
            assert_object_bytes(store, digest, payload)


def test_refetch_downloads_already_local_object_unlike_default():
    """Refetch GETs an already-local object; default fetch does not."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as missing:
            digest = _setup_tracked(missing, svc, [(rel, payload)])[0]
            _wipe_store(missing, [digest])
            _plant(missing, [rel])
            start = len(svc.records)
            require_success(missing.invoke_via_git(["fetch"]))
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )
        with workspace() as default:
            digest = _setup_tracked(default, svc, [(rel, payload)])[0]
            assert_object_bytes(
                default_lfs_store_root(default), digest, payload
            )
            start = len(svc.records)
            require_success(default.invoke_via_git(["fetch"]))
            assert_no_contact_of(
                _records_since(svc, start), svc.action_path(digest)
            )
        with workspace() as refetch:
            digest = _setup_tracked(refetch, svc, [(rel, payload)])[0]
            assert_object_bytes(
                default_lfs_store_root(refetch), digest, payload
            )
            start = len(svc.records)
            require_success(refetch.invoke_via_git(["fetch", "--refetch"]))
            print(f"refetch digest={digest}")
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )


def test_dry_run_does_not_transfer_unlike_live_fetch():
    """Dry-run does not GET or populate the store; live fetch does."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as live:
            digest = _setup_tracked(live, svc, [(rel, payload)])[0]
            _wipe_store(live, [digest])
            _plant(live, [rel])
            start = len(svc.records)
            require_success(live.invoke_via_git(["fetch"]))
            assert_object_bytes(default_lfs_store_root(live), digest, payload)
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )
        with workspace() as dry:
            digest = _setup_tracked(dry, svc, [(rel, payload)])[0]
            _wipe_store(dry, [digest])
            _plant(dry, [rel])
            start = len(svc.records)
            require_success(dry.invoke_via_git(["fetch", "--dry-run"]))
            print(f"dry-run exit=0 digest={digest}")
            assert_object_absent(default_lfs_store_root(dry), digest)
            assert_no_contact_of(
                _records_since(svc, start), svc.action_path(digest)
            )


def test_json_transfer_plan_distinguishes_refetch_from_default_at_same_occupancy():
    """JSON plans differ for refetch vs default when occupancy is the same."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as live:
            digest = _setup_tracked(live, svc, [(rel, payload)])[0]
            _wipe_store(live, [digest])
            _plant(live, [rel])
            start = len(svc.records)
            require_success(live.invoke_via_git(["fetch"]))
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )
        with workspace() as planned:
            digest = _setup_tracked(planned, svc, [(rel, payload)])[0]
            assert_object_bytes(
                default_lfs_store_root(planned), digest, payload
            )
            default_a = planned.invoke_via_git(
                ["fetch", "--json", "--dry-run"]
            )
            default_b = planned.invoke_via_git(
                ["fetch", "--json", "--dry-run"]
            )
            refetch_run = planned.invoke_via_git(
                ["fetch", "--json", "--dry-run", "--refetch"]
            )
            plan_default, plan_refetch = assert_json_plan_stable_unlike(
                default_a, default_b, refetch_run
            )
            print(
                f"json default plan={plan_default!r} "
                f"refetch plan={plan_refetch!r}"
            )


def test_json_transfer_plan_distinguishes_excluded_from_would_transfer_at_same_occupancy():
    """JSON plans differ for exclude vs would-transfer when both stores are empty."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as live:
            digest = _setup_tracked(live, svc, [(rel, payload)])[0]
            _wipe_store(live, [digest])
            _plant(live, [rel])
            start = len(svc.records)
            require_success(live.invoke_via_git(["fetch"]))
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )
        with workspace() as planned:
            digest = _setup_tracked(planned, svc, [(rel, payload)])[0]
            _wipe_store(planned, [digest])
            _plant(planned, [rel])
            would_a = planned.invoke_via_git(["fetch", "--json", "--dry-run"])
            would_b = planned.invoke_via_git(["fetch", "--json", "--dry-run"])
            configure_fetch_exclude(planned, rel)
            excluded_run = planned.invoke_via_git(
                ["fetch", "--json", "--dry-run"]
            )
            plan_would, plan_ex = assert_json_plan_stable_unlike(
                would_a, would_b, excluded_run
            )
            print(
                f"json would plan={plan_would!r} excluded plan={plan_ex!r}"
            )


# ---------------------------------------------------------------------------
# F. Checkout
# ---------------------------------------------------------------------------


def test_checkout_replaces_pointer_placeholder_from_local_store_without_download():
    """Checkout replaces a pointer from the local store and does not GET."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc, [(rel, payload)])[0]
            assert_object_bytes(default_lfs_store_root(ws), digest, payload)
            _plant(ws, [rel])
            assert_working_tree_pointer(
                ws, rel, digest=digest, size=len(payload)
            )
            start = len(svc.records)
            require_success(ws.invoke_via_git(["checkout"]))
            assert_working_tree_bytes(ws, rel, payload)
            assert_no_contact_of(
                _records_since(svc, start), svc.action_path(digest)
            )


def test_checkout_materializes_missing_file_from_local_store():
    """Checkout creates a missing working-tree file from the local store."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc, [(rel, payload)])[0]
            assert_object_bytes(default_lfs_store_root(ws), digest, payload)
            ws.resolve(rel).unlink()
            require_success(ws.invoke_via_git(["checkout"]))
            print(f"checkout missing {rel!r}")
            assert_working_tree_bytes(ws, rel, payload)


def test_checkout_does_not_download_when_object_absent_unlike_pull():
    """Checkout does not download; pull against the same endpoint does."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as checked:
            digest = _setup_tracked(checked, svc, [(rel, payload)])[0]
            _wipe_store(checked, [digest])
            _plant(checked, [rel])
            start = len(svc.records)
            require_success(checked.invoke_via_git(["checkout"]))
            recs = _records_since(svc, start)
            assert_object_absent(default_lfs_store_root(checked), digest)
            assert_working_tree_pointer(
                checked, rel, digest=digest, size=len(payload)
            )
            assert_no_contact_of(recs, svc.action_path(digest))
        with workspace() as pulled:
            digest = _setup_tracked(pulled, svc, [(rel, payload)])[0]
            _wipe_store(pulled, [digest])
            _plant(pulled, [rel])
            start = len(svc.records)
            require_success(pulled.invoke_via_git(["pull"]))
            print("pull materialized unlike checkout")
            assert_gets_of_action_paths(
                _records_since(svc, start), [svc.action_path(digest)]
            )
            assert_working_tree_bytes(pulled, rel, payload)


def test_checkout_glob_restricts_which_paths_are_updated():
    """A glob that is not an exact path updates only the matching middle path."""
    first, middle, last = _three_tracked_paths()
    data_a, data_b, data_c = _payload(), _payload(), _payload()
    pattern = "keep_*.bin"
    assert pattern != first and pattern != middle and pattern != last
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b, data_c]
    ) as svc:
        with workspace() as ws:
            digests = _setup_tracked(
                ws,
                svc,
                [(first, data_a), (middle, data_b), (last, data_c)],
            )
            _plant(ws, [first, middle, last])
            require_success(ws.invoke_via_git(["checkout", pattern]))
            print(f"glob {pattern!r} middle={middle!r}")
            require_working_tree_pointer(
                ws, first, digest=digests[0], size=len(data_a)
            )
            require_working_tree_bytes(ws, middle, data_b)
            require_working_tree_pointer(
                ws, last, digest=digests[2], size=len(data_c)
            )


def test_checkout_does_not_overwrite_modified_working_tree_file():
    """Checkout leaves modified working-tree bytes alone."""
    placeholder = _tracked_rel("keep")
    modified = _tracked_rel("dirty")
    data_keep, data_mod = _payload(), _payload()
    dirty = f"dirty-{token()}\n".encode("utf-8")
    assert dirty != data_mod
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_mod]
    ) as svc:
        with workspace() as ws:
            digests = _setup_tracked(
                ws, svc, [(placeholder, data_keep), (modified, data_mod)]
            )
            _plant(ws, [placeholder, modified])
            pointer_mod = index_blob(ws, modified)
            assert dirty != pointer_mod
            ws.write(modified, dirty)
            require_success(ws.invoke_via_git(["checkout"]))
            print(f"dirty left in place {modified!r}")
            require_working_tree_bytes(ws, placeholder, data_keep)
            require_working_tree_bytes(ws, modified, dirty)
            assert digests[1] == sha256_hex(data_mod)


def test_checkout_extracts_merge_conflict_stages_to_separate_files():
    """Checkout can extract base/ours/theirs stages to separate files."""
    rel = _tracked_rel()
    data_base, data_ours, data_theirs = _payload(), _payload(), _payload()
    out_base = f"base_{token()}"
    out_ours = f"ours_{token()}"
    out_theirs = f"theirs_{token()}"
    with conforming_batch_server(
        mode="download", payloads=[data_base, data_ours, data_theirs]
    ) as svc:
        with workspace() as ws:
            _setup_tracked(ws, svc, [(rel, data_base)])
            branch = f"th_{token()}"
            created = ws.git(["checkout", "-b", branch])
            assert created.returncode == 0, created.stderr_text
            commit_tracked_payload(ws, rel, data_theirs)
            back = ws.git(["checkout", "main"])
            assert back.returncode == 0, back.stderr_text
            commit_tracked_payload(ws, rel, data_ours)
            merged = ws.git(["merge", branch])
            assert merged.returncode != 0, (
                "expected a merge conflict, merge succeeded"
            )
            stages = ws.git(["ls-files", "-u", "--", rel])
            assert stages.returncode == 0, stages.stderr_text
            assert stages.stdout_text.strip(), (
                f"merge left no unmerged stages for {rel!r}"
            )
            require_success(
                ws.invoke_via_git(
                    ["checkout", "--to", out_base, "--base", rel]
                )
            )
            require_success(
                ws.invoke_via_git(
                    ["checkout", "--to", out_ours, "--ours", rel]
                )
            )
            require_success(
                ws.invoke_via_git(
                    ["checkout", "--to", out_theirs, "--theirs", rel]
                )
            )
            print(f"conflict extracts {out_base} {out_ours} {out_theirs}")
            require_working_tree_bytes(ws, out_base, data_base)
            require_working_tree_bytes(ws, out_ours, data_ours)
            require_working_tree_bytes(ws, out_theirs, data_theirs)


def test_checkout_in_bare_repository_has_no_effect():
    """Bare checkout has no effect after a live non-bare materialization."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc, [(rel, payload)])[0]
            require_object_bytes(default_lfs_store_root(ws), digest, payload)
            _plant(ws, [rel])
            require_working_tree_pointer(
                ws, rel, digest=digest, size=len(payload)
            )
            require_success(ws.invoke_via_git(["checkout"]))
            print(f"non-bare checkout materialized {rel!r}")
            require_working_tree_bytes(ws, rel, payload)
            require_object_bytes(default_lfs_store_root(ws), digest, payload)
            bare_rel = f"bare_{token()}.git"
            cloned = ws.git(["clone", "--bare", ".", bare_rel])
            assert cloned.returncode == 0, cloned.stderr_text
            bare = ws.resolve(bare_rel)
            _implant_object_at(ws, bare, digest, payload)
            store = default_lfs_store_root_at(ws, bare)
            occupancy_before = _store_occupancy(store)
            require_object_bytes(store, digest, payload)
            payload_path = bare / rel
            assert not payload_path.exists(), (
                "tracked path already present on the bare clone before checkout"
            )
            result = ws.invoke_via_git(["checkout"], cwd=bare)
            print(f"bare checkout exit={result.returncode}")
            assert not payload_path.exists(), (
                "bare checkout materialized the tracked path"
            )
            occupancy_after = _store_occupancy(store)
            require_object_bytes(store, digest, payload)
            assert occupancy_after == occupancy_before, (
                "bare checkout changed local store occupancy"
            )


# ---------------------------------------------------------------------------
# G. Pull = fetch + checkout for the current ref
# ---------------------------------------------------------------------------


def test_pull_fetches_current_ref_and_checkouts_unlike_fetch_alone():
    """Pull populates the store and working tree; fetch leaves pointers."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as fetched:
            digest = _setup_tracked(fetched, svc, [(rel, payload)])[0]
            _wipe_store(fetched, [digest])
            planted = _plant(fetched, [rel])
            require_success(fetched.invoke_via_git(["fetch"]))
            require_object_bytes(
                default_lfs_store_root(fetched), digest, payload
            )
            after = snapshot_working_tree(fetched, [rel])
            assert after[rel] == planted[rel]
        with workspace() as pulled:
            digest = _setup_tracked(pulled, svc, [(rel, payload)])[0]
            _wipe_store(pulled, [digest])
            _plant(pulled, [rel])
            require_success(pulled.invoke_via_git(["pull"]))
            print("pull materialized working tree")
            require_object_bytes(
                default_lfs_store_root(pulled), digest, payload
            )
            require_working_tree_bytes(pulled, rel, payload)


def test_pull_does_not_fetch_other_branch_only_object():
    """Pull fetches the current ref, not another branch's unique object."""
    rel_a = _tracked_rel("cur")
    rel_b = _tracked_rel("oth")
    data_a, data_b = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as ws:
            digest_a = _setup_tracked(ws, svc, [(rel_a, data_a)])[0]
            branch, digest_b = _checkout_other_unique(
                ws, rel_a, rel_b, data_b
            )
            _wipe_store(ws, [digest_a, digest_b])
            _plant(ws, [rel_a])
            require_success(ws.invoke_via_git(["pull"]))
            print(f"pull omitted {branch}")
            store = default_lfs_store_root(ws)
            require_object_bytes(store, digest_a, data_a)
            require_object_absent(store, digest_b)
            require_working_tree_bytes(ws, rel_a, data_a)


# ---------------------------------------------------------------------------
# H. Unreachable / auth failure
# ---------------------------------------------------------------------------


def test_fetch_unreachable_endpoint_fails_and_does_not_populate_store():
    """Fetch against an unreachable endpoint fails and leaves the store empty."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            digest = _setup_tracked(ok, svc, [(rel, payload)])[0]
            _wipe_store(ok, [digest])
            _plant(ok, [rel])
            require_success(ok.invoke_via_git(["fetch"]))
            require_object_bytes(default_lfs_store_root(ok), digest, payload)
        with workspace() as failed:
            failed.init_repo()
            digest = prepare_tracked_commit(failed, rel, payload)
            configure_unreachable_endpoint(failed)
            _wipe_store(failed, [digest])
            planted = _plant(failed, [rel])
            result = failed.invoke_via_git(["fetch"])
            print(f"unreachable fetch exit={result.returncode}")
            assert result.returncode != 0
            require_object_absent(default_lfs_store_root(failed), digest)
            after = snapshot_working_tree(failed, [rel])
            assert after[rel] == planted[rel]


def test_pull_unreachable_endpoint_fails_and_does_not_materialize():
    """Pull against an unreachable endpoint fails and leaves pointers."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            digest = _setup_tracked(ok, svc, [(rel, payload)])[0]
            _wipe_store(ok, [digest])
            _plant(ok, [rel])
            require_success(ok.invoke_via_git(["pull"]))
            require_working_tree_bytes(ok, rel, payload)
        with workspace() as failed:
            failed.init_repo()
            digest = prepare_tracked_commit(failed, rel, payload)
            configure_unreachable_endpoint(failed)
            _wipe_store(failed, [digest])
            _plant(failed, [rel])
            result = failed.invoke_via_git(["pull"])
            print(f"unreachable pull exit={result.returncode}")
            assert result.returncode != 0
            require_working_tree_pointer(
                failed, rel, digest=digest, size=len(payload)
            )


def test_fetch_auth_failure_fails_unlike_accepted_endpoint():
    """Fetch fails when the endpoint rejects credentials."""
    rel = _tracked_rel()
    payload = _payload()
    user, password = f"u_{token()}", f"p_{token()}"
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            digest = _setup_tracked(ok, svc, [(rel, payload)])[0]
            _wipe_store(ok, [digest])
            _plant(ok, [rel])
            require_success(ok.invoke_via_git(["fetch"]))
            require_object_bytes(default_lfs_store_root(ok), digest, payload)
    with recording_api_server(
        accepted_user=user, accepted_password=password
    ) as (url, _records):
        with workspace() as failed:
            failed.init_repo()
            point_lfs_at(failed, url)
            digest = prepare_tracked_commit(failed, rel, payload)
            _wipe_store(failed, [digest])
            _plant(failed, [rel])
            result = failed.invoke_via_git(["fetch"])
            print(f"auth fetch exit={result.returncode}")
            assert result.returncode != 0
            require_object_absent(default_lfs_store_root(failed), digest)


def test_pull_auth_failure_fails_unlike_accepted_endpoint():
    """Pull fails when the endpoint rejects credentials."""
    rel = _tracked_rel()
    payload = _payload()
    user, password = f"u_{token()}", f"p_{token()}"
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            digest = _setup_tracked(ok, svc, [(rel, payload)])[0]
            _wipe_store(ok, [digest])
            _plant(ok, [rel])
            require_success(ok.invoke_via_git(["pull"]))
            require_working_tree_bytes(ok, rel, payload)
    with recording_api_server(
        accepted_user=user, accepted_password=password
    ) as (url, _records):
        with workspace() as failed:
            failed.init_repo()
            point_lfs_at(failed, url)
            digest = prepare_tracked_commit(failed, rel, payload)
            _wipe_store(failed, [digest])
            _plant(failed, [rel])
            result = failed.invoke_via_git(["pull"])
            print(f"auth pull exit={result.returncode}")
            assert result.returncode != 0
            require_working_tree_pointer(
                failed, rel, digest=digest, size=len(payload)
            )


# ---------------------------------------------------------------------------
# I. Clone
# ---------------------------------------------------------------------------


def test_clone_batch_downloads_and_materializes_tracked_files():
    """Clone batch-downloads both objects and materializes working-tree files."""
    keep, other = _two_tracked_paths()
    data_a, data_b = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as ws:
            _install_global_filters(ws)
            src_rel = f"src_{token()}"
            src, digests = _prepare_clone_source(
                ws, src_rel, svc.url, [(keep, data_a), (other, data_b)]
            )
            dst_rel = f"dst_{token()}"
            start = len(svc.records)
            result = ws.invoke_via_git(["clone", str(src), dst_rel])
            print(f"clone exit={result.returncode} dst={dst_rel}")
            require_success(result)
            dst = ws.resolve(dst_rel)
            require_git_repository_at(ws, dst)
            assert _head_oid_at(ws, src) == _head_oid_at(ws, dst)
            recs = _records_since(svc, start)
            require_download_batch_accounts_for_oids(recs, digests)
            require_gets_of_action_paths(
                recs,
                [svc.action_path(digests[0]), svc.action_path(digests[1])],
            )
            require_working_tree_bytes(ws, keep, data_a, cwd=dst)
            require_working_tree_bytes(ws, other, data_b, cwd=dst)
            store = default_lfs_store_root_at(ws, dst)
            require_object_bytes(store, digests[0], data_a)
            require_object_bytes(store, digests[1], data_b)


def test_clone_installs_repository_hooks():
    """A clone that does not skip hooks installs the four VCS Orbulk hooks."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ws:
            _install_global_filters(ws)
            src_rel = f"src_{token()}"
            src, _digests = _prepare_clone_source(
                ws, src_rel, svc.url, [(rel, payload)]
            )
            dst_rel = f"dst_{token()}"
            tmpl = _empty_clone_template(ws)
            require_success(
                ws.invoke_via_git(
                    ["clone", "--template", str(tmpl), str(src), dst_rel]
                )
            )
            bodies = read_git_orbulk_hook_bodies_at(ws, ws.resolve(dst_rel))
            print(f"clone hooks={list(bodies)}")
            assert len(bodies) == 4


def test_clone_include_applies_to_download_phase():
    """Clone include materializes only the matching path."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as baseline:
            _install_global_filters(baseline)
            src, _d = _prepare_clone_source(
                baseline,
                f"src_{token()}",
                svc.url,
                [(keep, data_keep), (skip, data_skip)],
            )
            dst_rel = f"dst_{token()}"
            require_success(
                baseline.invoke_via_git(["clone", str(src), dst_rel])
            )
            dst = baseline.resolve(dst_rel)
            require_working_tree_bytes(baseline, keep, data_keep, cwd=dst)
            require_working_tree_bytes(baseline, skip, data_skip, cwd=dst)
        with workspace() as limited:
            _install_global_filters(limited)
            src, digests = _prepare_clone_source(
                limited,
                f"src_{token()}",
                svc.url,
                [(keep, data_keep), (skip, data_skip)],
            )
            dst_rel = f"dst_{token()}"
            require_success(
                limited.invoke_via_git(
                    ["clone", "--include", keep, str(src), dst_rel]
                )
            )
            dst = limited.resolve(dst_rel)
            print(f"clone include keep={keep!r}")
            require_working_tree_bytes(limited, keep, data_keep, cwd=dst)
            require_working_tree_pointer(
                limited,
                skip,
                digest=digests[1],
                size=len(data_skip),
                cwd=dst,
            )
            require_object_absent(
                default_lfs_store_root_at(limited, dst), digests[1]
            )


def test_clone_exclude_applies_to_download_phase():
    """Clone exclude skips the excluded path during the download phase."""
    keep, skip = _two_tracked_paths()
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as svc:
        with workspace() as baseline:
            _install_global_filters(baseline)
            src, _d = _prepare_clone_source(
                baseline,
                f"src_{token()}",
                svc.url,
                [(keep, data_keep), (skip, data_skip)],
            )
            dst_rel = f"dst_{token()}"
            require_success(
                baseline.invoke_via_git(["clone", str(src), dst_rel])
            )
            require_working_tree_bytes(
                baseline, skip, data_skip, cwd=baseline.resolve(dst_rel)
            )
        with workspace() as limited:
            _install_global_filters(limited)
            src, digests = _prepare_clone_source(
                limited,
                f"src_{token()}",
                svc.url,
                [(keep, data_keep), (skip, data_skip)],
                extra_lfsconfig={"lfs.fetchexclude": skip},
            )
            dst_rel = f"dst_{token()}"
            require_success(
                limited.invoke_via_git(["clone", str(src), dst_rel])
            )
            dst = limited.resolve(dst_rel)
            print(f"clone exclude skip={skip!r}")
            require_working_tree_bytes(limited, keep, data_keep, cwd=dst)
            require_working_tree_pointer(
                limited,
                skip,
                digest=digests[1],
                size=len(data_skip),
                cwd=dst,
            )
            require_object_absent(
                default_lfs_store_root_at(limited, dst), digests[1]
            )


def test_direct_binary_clone_same_batch_and_materialization():
    """Direct binary clone batch-downloads and materializes like via-git."""
    keep, other = _two_tracked_paths()
    data_a, data_b = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_a, data_b]
    ) as svc:
        with workspace() as ws:
            _install_global_filters(ws)
            src, digests = _prepare_clone_source(
                ws,
                f"src_{token()}",
                svc.url,
                [(keep, data_a), (other, data_b)],
            )
            dst_rel = f"dst_{token()}"
            start = len(svc.records)
            result = ws.invoke(["clone", str(src), dst_rel])
            print(f"direct clone exit={result.returncode}")
            require_success(result)
            dst = ws.resolve(dst_rel)
            recs = _records_since(svc, start)
            require_download_batch_accounts_for_oids(recs, digests)
            require_gets_of_action_paths(
                recs,
                [svc.action_path(digests[0]), svc.action_path(digests[1])],
            )
            require_working_tree_bytes(ws, keep, data_a, cwd=dst)
            require_working_tree_bytes(ws, other, data_b, cwd=dst)


# ---------------------------------------------------------------------------
# J. Clone download failure vs hook-install failure
# ---------------------------------------------------------------------------


def test_clone_download_failure_is_nonsuccess_while_git_repo_may_remain():
    """A failed clone download is non-success, distinguishable from success."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            _install_global_filters(ok)
            src, _d = _prepare_clone_source(
                ok, f"src_{token()}", svc.url, [(rel, payload)]
            )
            dst_rel = f"dst_{token()}"
            require_success(ok.invoke_via_git(["clone", str(src), dst_rel]))
            require_working_tree_bytes(
                ok, rel, payload, cwd=ok.resolve(dst_rel)
            )
    with workspace() as failed:
        _install_global_filters(failed)
        closed = reserve_loopback_port()
        url = f"http://127.0.0.1:{closed}/{token()}/info/lfs"
        src, _d = _prepare_clone_source(
            failed, f"src_{token()}", url, [(rel, payload)]
        )
        dst_rel = f"dst_{token()}"
        result = failed.invoke_via_git(
            [
                "clone",
                "--config",
                "lfs.transfer.maxretries=1",
                str(src),
                dst_rel,
            ]
        )
        print(f"clone download fail exit={result.returncode}")
        assert result.returncode != 0


def test_clone_hook_install_failure_is_nonsuccess_unlike_skip_and_unlike_success():
    """Hook-install failure is non-success, unlike skip-repo and unlike success."""
    rel = _tracked_rel()
    payload = _payload()

    def _blocker(ws) -> Path:
        tmpl_rel = f"tmpl_{token()}"
        hook = ws.resolve(f"{tmpl_rel}/hooks/pre-push")
        hook.mkdir(parents=True)
        (hook / f"block_{token()}").write_text("x\n", encoding="utf-8")
        return ws.resolve(tmpl_rel)

    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as ok:
            _install_global_filters(ok)
            src, _d = _prepare_clone_source(
                ok, f"src_{token()}", svc.url, [(rel, payload)]
            )
            dst_rel = f"dst_{token()}"
            tmpl = _empty_clone_template(ok)
            ok_run = ok.invoke_via_git(
                ["clone", "--template", str(tmpl), str(src), dst_rel]
            )
            require_success(ok_run)
            dst = ok.resolve(dst_rel)
            require_working_tree_bytes(ok, rel, payload, cwd=dst)
            read_git_orbulk_hook_bodies_at(ok, dst)
        with workspace() as skipped:
            _install_global_filters(skipped)
            src, _d = _prepare_clone_source(
                skipped, f"src_{token()}", svc.url, [(rel, payload)]
            )
            tmpl = _blocker(skipped)
            dst_rel = f"dst_{token()}"
            skip_run = skipped.invoke_via_git(
                [
                    "clone",
                    "--skip-repo",
                    "--template",
                    str(tmpl),
                    str(src),
                    dst_rel,
                ]
            )
            require_success(skip_run)
            dst = skipped.resolve(dst_rel)
            require_working_tree_bytes(skipped, rel, payload, cwd=dst)
        with workspace() as blocked:
            _install_global_filters(blocked)
            src, _d = _prepare_clone_source(
                blocked, f"src_{token()}", svc.url, [(rel, payload)]
            )
            tmpl = _blocker(blocked)
            dst_rel = f"dst_{token()}"
            fail_run = blocked.invoke_via_git(
                ["clone", "--template", str(tmpl), str(src), dst_rel]
            )
            print(
                f"hook-fail exit={fail_run.returncode} "
                f"skip exit={skip_run.returncode} "
                f"ok exit={ok_run.returncode}"
            )
            assert fail_run.returncode != 0
            assert (fail_run.returncode, fail_run.stdout, fail_run.stderr) != (
                skip_run.returncode,
                skip_run.stdout,
                skip_run.stderr,
            )
            assert (fail_run.returncode, fail_run.stdout, fail_run.stderr) != (
                ok_run.returncode,
                ok_run.stdout,
                ok_run.stderr,
            )


# ---------------------------------------------------------------------------
# K. Negative control
# ---------------------------------------------------------------------------


def test_fetch_pull_checkout_clone_fail_when_binary_removed_from_path():
    """Removing the binary from PATH fails all four public entries."""
    rel = _tracked_rel()
    payload = _payload()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as present:
            digest = _setup_tracked(present, svc, [(rel, payload)])[0]
            _wipe_store(present, [digest])
            _plant(present, [rel])
            ok = present.invoke_via_git(["fetch"])
            require_success(ok)
            require_object_bytes(
                default_lfs_store_root(present), digest, payload
            )
        with workspace() as missing:
            digest = _setup_tracked(missing, svc, [(rel, payload)])[0]
            _wipe_store(missing, [digest])
            _plant(missing, [rel])
            _install_global_filters(missing)
            src, _d = _prepare_clone_source(
                missing, f"src_{token()}", svc.url, [(rel, payload)]
            )
            dst_ok = f"dst_ok_{token()}"
            ok_clone = missing.invoke_via_git(["clone", str(src), dst_ok])
            require_success(ok_clone)
            print(f"with-binary clone dst={dst_ok}")
            require_working_tree_bytes(
                missing, rel, payload, cwd=missing.resolve(dst_ok)
            )
            hidden = path_without_product_bin(missing.env)
            env = {"PATH": hidden}
            fetch_f = missing.invoke_via_git(["fetch"], env_updates=env)
            pull_f = missing.invoke_via_git(["pull"], env_updates=env)
            checkout_f = missing.invoke_via_git(
                ["checkout"], env_updates=env
            )
            dst_fail = f"dst_{token()}"
            clone_f = missing.invoke_via_git(
                ["clone", str(src), dst_fail],
                env_updates=env,
            )
            print(
                f"absent fetch={fetch_f.returncode} pull={pull_f.returncode} "
                f"checkout={checkout_f.returncode} clone={clone_f.returncode}"
            )
            for name, failed, unlike in (
                ("fetch", fetch_f, ok),
                ("pull", pull_f, ok),
                ("checkout", checkout_f, ok),
                ("clone", clone_f, ok_clone),
            ):
                assert failed.returncode != 0, (
                    f"{name} succeeded after the product binary was removed "
                    "from PATH"
                )
                assert (failed.returncode, failed.stdout, failed.stderr) != (
                    unlike.returncode,
                    unlike.stdout,
                    unlike.stderr,
                ), f"absent-binary {name} was not distinguishable from success"
