# feature: F05
"""Clean, smudge, filter-process, and local object-store acceptance tests.

PRD: FP-05. Assertions stay at the PRD's precision: non-empty non-pointer
clean hashes and stores a sharded object and writes a canonical pointer
without uploading; already-pointer input is written through without a
nested object; smudge restores original bytes from the local store and
copies non-pointer bytes through; missing objects without a reachable
endpoint fail unless skip / skip-smudge / skip-download-errors apply;
include/exclude and skip modes leave pointers in the working tree;
relocated storage uses objects-directory-plus-shard under the configured
root. Pointer version-identifier strings, hash-method labels, exit-code
numbers, error wording, pkt-line, and filter argv are not pinned.
"""

from __future__ import annotations

from _harness import token, workspace
from _helpers import (
    add_git_remote,
    assert_clean_wrote_canonical_pointer,
    assert_generated_pointer_shape,
    assert_object_absent,
    assert_object_bytes,
    clean_bytes,
    commit_tracked_payload,
    configure_fetch_exclude,
    configure_fetch_include,
    configure_lfs_clean_filter,
    configure_storage_root,
    configure_unreachable_endpoint,
    default_lfs_store_root,
    enable_skip_download_errors,
    enable_skip_smudge_environment,
    index_blob,
    install_local_keeping_process,
    lookup_git_config,
    path_without_product_bin,
    pointer_from_clean,
    pointer_from_clean_stdout,
    recording_http_server,
    require_filters_point_at_git_orbulk,
    require_generated_pointer_shape,
    require_git_config_set,
    require_invalid_unlike_success,
    require_points_at_git_orbulk,
    require_object_absent,
    require_object_bytes,
    require_smudge_passthrough,
    require_success,
    sha256_hex,
    sharded_object_rel,
    skip_download_errors_environment,
    smudge_bytes,
    smudge_skip_bytes,
    track_pattern,
)


def _payload() -> bytes:
    return f"blob-{token()}-X".encode("utf-8")


def _unrecognized() -> bytes:
    return f"not-pointer-{token()}\n".encode("utf-8")


def _seed_tracked(
    ws,
    rel: str,
    data: bytes,
    glob: str,
    *,
    keep_process: bool = True,
    skip_smudge_install: bool = False,
) -> str:
    """Init, install, track, add, and commit. Return independent SHA-256."""
    ws.init_repo()
    if skip_smudge_install:
        require_success(ws.invoke_via_git(["install", "--local", "--skip-smudge"]))
        require_filters_point_at_git_orbulk(ws, local=True)
    elif keep_process:
        install_local_keeping_process(ws)
    else:
        configure_lfs_clean_filter(ws)
    track_pattern(ws, glob)
    return commit_tracked_payload(ws, rel, data)


def _unlink_worktree(ws, *rels: str) -> None:
    for rel in rels:
        ws.resolve(rel).unlink()


def _checkout(ws, *rels: str, env_updates=None):
    return ws.git(
        ["checkout", "HEAD", "--", *rels],
        env_updates=env_updates,
    )


def _remove_object(ws, oid: str) -> None:
    path = default_lfs_store_root(ws) / sharded_object_rel(oid)
    try:
        path.unlink()
    except OSError as exc:
        raise AssertionError(f"cannot remove object at {path}: {exc}") from exc


def _require_worktree_pointer(ws, rel: str, *, digest: str, size: int) -> bytes:
    body = ws.read_bytes(rel)
    require_generated_pointer_shape(body, digest=digest, size=size)
    return body


# ---------------------------------------------------------------------------
# A. Non-empty non-pointer clean: hash, shard, canonical pointer, no upload
# ---------------------------------------------------------------------------


def test_clean_stores_sharded_object_and_writes_canonical_pointer(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    result = clean_bytes(isolated_ws, data)
    print(f"clean exit={result.returncode} stdout_len={len(result.stdout)}")
    document = assert_clean_wrote_canonical_pointer(
        result, digest=digest, size=len(data)
    )
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    print(f"stored={stored} doc_len={len(document)}")
    assert document != data, (
        "clean wrote the original bytes through instead of a canonical pointer"
    )
    assert stored.read_bytes() == data, (
        "sharded object is not the original content"
    )


def test_clean_via_direct_binary_stores_object(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    result = clean_bytes(isolated_ws, data, via_git=False)
    print(f"direct clean exit={result.returncode} len={len(result.stdout)}")
    document = assert_clean_wrote_canonical_pointer(
        result, digest=digest, size=len(data)
    )
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    assert document != data, (
        "direct-binary clean wrote the original bytes through instead of "
        "a canonical pointer"
    )
    assert stored.read_bytes() == data, (
        "sharded object from direct-binary clean is not the original content"
    )


def test_git_add_stages_pointer_blob_and_stores_object(isolated_ws):
    isolated_ws.init_repo()
    install_local_keeping_process(isolated_ws)
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    track_pattern(isolated_ws, f"*.{ext}")
    digest = commit_tracked_payload(isolated_ws, rel, data)
    blob = index_blob(isolated_ws, rel)
    print(f"add rel={rel} digest={digest} blob_len={len(blob)}")
    assert_generated_pointer_shape(blob, digest=digest, size=len(data))
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    assert blob != data, (
        "git add staged the original bytes instead of a pointer blob"
    )
    assert stored.read_bytes() == data, (
        "sharded object after git add is not the original content"
    )


def test_clean_does_not_upload_to_configured_endpoint(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    with recording_http_server() as (url, records):
        add_git_remote(isolated_ws, "origin", url)
        require_git_config_set(isolated_ws, "lfs.url", url, local=True)
        result = clean_bytes(isolated_ws, data)
        pointer_from_clean(result, digest=digest, size=len(data))
        require_object_bytes(default_lfs_store_root(isolated_ws), digest, data)
        leaked = [
            (method, body)
            for method, body in records
            if data == body or data in body
        ]
        print(f"records={len(records)} leaked={len(leaked)} url={url}")
        assert not leaked, (
            "clean sent object bytes to the configured endpoint: "
            f"{leaked!r}"
        )


def test_two_independent_cleans_of_identical_bytes_match(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    first = pointer_from_clean_stdout(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    second = pointer_from_clean_stdout(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    print(f"first_len={len(first)} second_len={len(second)}")
    assert first == second, "two cleans of identical bytes wrote different pointers"
    require_object_bytes(default_lfs_store_root(isolated_ws), digest, data)


# ---------------------------------------------------------------------------
# B. Already-pointer write-through; unrecognized still hashes
# ---------------------------------------------------------------------------


def test_clean_of_already_pointer_writes_through_without_nested_object(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    pointer = assert_clean_wrote_canonical_pointer(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    assert_object_bytes(default_lfs_store_root(isolated_ws), digest, data)
    nested_oid = sha256_hex(pointer)
    second = assert_clean_wrote_canonical_pointer(
        clean_bytes(isolated_ws, pointer), digest=digest, size=len(data)
    )
    print(f"nested_oid={nested_oid} second_len={len(second)}")
    assert_object_absent(default_lfs_store_root(isolated_ws), nested_oid)
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    assert stored.read_bytes() == data, (
        "original object was lost after clean of an already-pointer document"
    )
    assert second != data, (
        "clean of an already-pointer document wrote the original payload "
        "instead of a pointer for that payload"
    )


def test_git_add_of_pointer_worktree_does_not_nest(isolated_ws):
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    digest = _seed_tracked(isolated_ws, rel, data, glob)
    pointer = index_blob(isolated_ws, rel)
    _unlink_worktree(isolated_ws, rel)
    skipped = _checkout(
        isolated_ws, rel, env_updates=enable_skip_smudge_environment()
    )
    require_success(skipped)
    worktree = _require_worktree_pointer(
        isolated_ws, rel, digest=digest, size=len(data)
    )
    print(f"pointer_wt_len={len(worktree)}")
    added = isolated_ws.git(["add", "--", rel])
    require_success(added)
    blob = index_blob(isolated_ws, rel)
    assert_generated_pointer_shape(blob, digest=digest, size=len(data))
    assert_object_absent(default_lfs_store_root(isolated_ws), sha256_hex(pointer))
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    assert blob != data, (
        "git add of a pointer worktree staged the original payload instead "
        "of a pointer blob"
    )
    assert stored.read_bytes() == data, (
        "original object was lost after git add of a pointer worktree"
    )


def test_clean_of_unrecognized_bytes_still_hashes_and_stores(isolated_ws):
    isolated_ws.init_repo()
    data = _unrecognized()
    digest = sha256_hex(data)
    result = clean_bytes(isolated_ws, data)
    print(f"unrecognized clean exit={result.returncode} len={len(result.stdout)}")
    document = assert_clean_wrote_canonical_pointer(
        result, digest=digest, size=len(data)
    )
    stored = assert_object_bytes(
        default_lfs_store_root(isolated_ws), digest, data
    )
    assert document != data, (
        "clean of unrecognized bytes wrote the input through instead of "
        "hashing it into a pointer"
    )
    assert stored.read_bytes() == data, (
        "unrecognized bytes were not stored as the sharded object"
    )


# ---------------------------------------------------------------------------
# C. Smudge restore, non-pointer copy-through, missing-object failure
# ---------------------------------------------------------------------------


def test_smudge_restores_original_bytes_from_local_store(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    pointer = pointer_from_clean(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    restored = smudge_bytes(isolated_ws, pointer)
    print(f"smudge exit={restored.returncode} len={len(restored.stdout)}")
    require_success(restored)
    assert restored.stdout == data, (
        "smudge did not restore original bytes from the local store"
    )


def test_git_checkout_restores_identical_bytes_when_object_local(isolated_ws):
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    digest = _seed_tracked(isolated_ws, rel, data, f"*.{ext}")
    require_generated_pointer_shape(
        index_blob(isolated_ws, rel), digest=digest, size=len(data)
    )
    require_object_bytes(default_lfs_store_root(isolated_ws), digest, data)
    _unlink_worktree(isolated_ws, rel)
    checked = _checkout(isolated_ws, rel)
    print(f"checkout exit={checked.returncode}")
    require_success(checked)
    got = isolated_ws.read_bytes(rel)
    print(f"worktree_len={len(got)} digest={digest}")
    assert got == data, "checkout did not restore original working-tree bytes"


def test_checkout_style_smudge_does_not_overwrite_modified_worktree_file(
    isolated_ws,
):
    ext = token()
    glob = f"*.{ext}"
    placeholder = f"keep_{token()}.{ext}"
    modified = f"dirty_{token()}.{ext}"
    data_keep = _payload()
    data_mod = _payload()
    dirty = f"dirty-{token()}\n".encode("utf-8")
    digest_keep = _seed_tracked(isolated_ws, placeholder, data_keep, glob)
    digest_mod = commit_tracked_payload(isolated_ws, modified, data_mod)
    require_object_bytes(
        default_lfs_store_root(isolated_ws), digest_keep, data_keep
    )
    require_object_bytes(
        default_lfs_store_root(isolated_ws), digest_mod, data_mod
    )
    _unlink_worktree(isolated_ws, placeholder, modified)
    planted = _checkout(
        isolated_ws,
        placeholder,
        modified,
        env_updates=enable_skip_smudge_environment(),
    )
    require_success(planted)
    _require_worktree_pointer(
        isolated_ws, placeholder, digest=digest_keep, size=len(data_keep)
    )
    _require_worktree_pointer(
        isolated_ws, modified, digest=digest_mod, size=len(data_mod)
    )
    isolated_ws.write(modified, dirty)
    smudged = isolated_ws.invoke_via_git(["checkout"])
    print(
        f"placeholder={placeholder} modified={modified} "
        f"smudge_exit={smudged.returncode}"
    )
    require_success(smudged)
    kept = isolated_ws.read_bytes(placeholder)
    left = isolated_ws.read_bytes(modified)
    print(f"kept_len={len(kept)} left_len={len(left)}")
    assert kept == data_keep, (
        "unmodified placeholder was not replaced with original bytes "
        "by checkout-style smudging"
    )
    assert left == dirty, (
        "modified working-tree file was overwritten by checkout-style "
        "smudging of placeholders"
    )
    assert left != data_mod, (
        "modified working-tree file was restored to the committed payload"
    )


def test_smudge_copies_non_pointer_bytes_through(isolated_ws):
    isolated_ws.init_repo()
    data = _payload()
    digest = sha256_hex(data)
    pointer = pointer_from_clean(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    restored = smudge_bytes(isolated_ws, pointer)
    require_success(restored)
    assert restored.stdout == data
    other = _unrecognized()
    copied = smudge_bytes(isolated_ws, other)
    print(f"non-pointer smudge exit={copied.returncode} len={len(copied.stdout)}")
    require_success(copied)
    require_smudge_passthrough(copied, other)


def test_smudge_fails_when_object_missing_and_endpoint_unreachable():
    data = _payload()
    with workspace() as present:
        present.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(present, data), digest=digest, size=len(data)
        )
        ok = smudge_bytes(present, pointer)
        require_success(ok)
        assert ok.stdout == data
        print(f"present smudge len={len(ok.stdout)}")
    with workspace() as missing:
        missing.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(missing, data), digest=digest, size=len(data)
        )
        _remove_object(missing, digest)
        configure_unreachable_endpoint(missing)
        failed = smudge_bytes(missing, pointer)
        print(f"missing smudge exit={failed.returncode}")
        require_invalid_unlike_success(ok, failed)


def test_git_checkout_fails_when_object_missing_and_endpoint_unreachable():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as present:
        digest = _seed_tracked(present, rel, data, glob)
        _unlink_worktree(present, rel)
        ok = _checkout(present, rel)
        require_success(ok)
        assert present.read_bytes(rel) == data
        print(f"present checkout digest={digest}")
    with workspace() as missing:
        digest = _seed_tracked(missing, rel, data, glob)
        _remove_object(missing, digest)
        configure_unreachable_endpoint(missing)
        _unlink_worktree(missing, rel)
        failed = _checkout(missing, rel)
        print(f"missing checkout exit={failed.returncode}")
        require_invalid_unlike_success(ok, failed)


# ---------------------------------------------------------------------------
# D. Filter-process same semantics as clean/smudge
# ---------------------------------------------------------------------------


def test_git_add_via_process_filter_matches_clean_plumbing_store_and_pointer():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as proc:
        digest = _seed_tracked(proc, rel, data, glob, keep_process=True)
        process = lookup_git_config(proc, "filter.lfs.process", local=True)
        assert process is not None, "process filter was unset on the process arm"
        require_points_at_git_orbulk(process)
        blob = index_blob(proc, rel)
        require_generated_pointer_shape(blob, digest=digest, size=len(data))
        require_object_bytes(default_lfs_store_root(proc), digest, data)
        print(f"process blob_len={len(blob)}")
    with workspace() as pipe:
        digest_b = _seed_tracked(pipe, rel, data, glob, keep_process=False)
        process_b = lookup_git_config(pipe, "filter.lfs.process", local=True)
        assert process_b is None, "plumbing arm still has a process filter"
        blob_b = index_blob(pipe, rel)
        require_generated_pointer_shape(blob_b, digest=digest_b, size=len(data))
        require_object_bytes(default_lfs_store_root(pipe), digest_b, data)
        print(f"plumbing blob_len={len(blob_b)}")
        assert digest == digest_b


def test_git_checkout_via_process_filter_restores_like_smudge():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as proc:
        digest = _seed_tracked(proc, rel, data, glob, keep_process=True)
        process = lookup_git_config(proc, "filter.lfs.process", local=True)
        assert process is not None, "process filter was unset on the process arm"
        require_points_at_git_orbulk(process)
        require_generated_pointer_shape(
            index_blob(proc, rel), digest=digest, size=len(data)
        )
        require_object_bytes(default_lfs_store_root(proc), digest, data)
        _unlink_worktree(proc, rel)
        checked = _checkout(proc, rel)
        require_success(checked)
        got = proc.read_bytes(rel)
        print(f"process checkout len={len(got)}")
        assert got == data
    with workspace() as pipe:
        digest_b = _seed_tracked(pipe, rel, data, glob, keep_process=False)
        process_b = lookup_git_config(pipe, "filter.lfs.process", local=True)
        assert process_b is None, "plumbing arm still has a process filter"
        require_generated_pointer_shape(
            index_blob(pipe, rel), digest=digest_b, size=len(data)
        )
        require_object_bytes(default_lfs_store_root(pipe), digest_b, data)
        _unlink_worktree(pipe, rel)
        checked = _checkout(pipe, rel)
        require_success(checked)
        got = pipe.read_bytes(rel)
        print(f"plumbing checkout len={len(got)}")
        assert got == data
        assert digest == digest_b


# ---------------------------------------------------------------------------
# E. Include / exclude and skip-smudge when the object is local
# ---------------------------------------------------------------------------


def test_include_smudges_only_matching_path():
    ext = token()
    glob = f"*.{ext}"
    keep = f"keep_{token()}.{ext}"
    other = f"other_{token()}.{ext}"
    data_keep = _payload()
    data_other = _payload()
    with workspace() as baseline:
        _seed_tracked(baseline, keep, data_keep, glob)
        commit_tracked_payload(baseline, other, data_other)
        _unlink_worktree(baseline, keep, other)
        require_success(_checkout(baseline, keep, other))
        assert baseline.read_bytes(keep) == data_keep
        assert baseline.read_bytes(other) == data_other
        print("baseline both materialized")
    with workspace() as limited:
        _seed_tracked(limited, keep, data_keep, glob)
        commit_tracked_payload(limited, other, data_other)
        configure_fetch_include(limited, keep)
        _unlink_worktree(limited, keep, other)
        require_success(_checkout(limited, keep, other))
        got_keep = limited.read_bytes(keep)
        got_other = limited.read_bytes(other)
        print(f"include keep_len={len(got_keep)} other_len={len(got_other)}")
        assert got_keep == data_keep
        require_generated_pointer_shape(
            got_other, digest=sha256_hex(data_other), size=len(data_other)
        )
        assert got_other != data_other


def test_exclude_leaves_matching_path_as_pointer():
    ext = token()
    glob = f"*.{ext}"
    keep = f"keep_{token()}.{ext}"
    drop = f"drop_{token()}.{ext}"
    data_keep = _payload()
    data_drop = _payload()
    with workspace() as baseline:
        _seed_tracked(baseline, keep, data_keep, glob)
        commit_tracked_payload(baseline, drop, data_drop)
        _unlink_worktree(baseline, keep, drop)
        require_success(_checkout(baseline, keep, drop))
        assert baseline.read_bytes(drop) == data_drop
        print("baseline drop materialized")
    with workspace() as limited:
        _seed_tracked(limited, keep, data_keep, glob)
        commit_tracked_payload(limited, drop, data_drop)
        configure_fetch_exclude(limited, drop)
        _unlink_worktree(limited, keep, drop)
        require_success(_checkout(limited, keep, drop))
        got_keep = limited.read_bytes(keep)
        got_drop = limited.read_bytes(drop)
        print(f"exclude keep_len={len(got_keep)} drop_len={len(got_drop)}")
        assert got_keep == data_keep
        require_generated_pointer_shape(
            got_drop, digest=sha256_hex(data_drop), size=len(data_drop)
        )
        assert got_drop != data_drop


def test_include_from_lfsconfig_same_contrast():
    ext = token()
    glob = f"*.{ext}"
    keep = f"keep_{token()}.{ext}"
    other = f"other_{token()}.{ext}"
    data_keep = _payload()
    data_other = _payload()
    with workspace() as baseline:
        _seed_tracked(baseline, keep, data_keep, glob)
        commit_tracked_payload(baseline, other, data_other)
        _unlink_worktree(baseline, keep, other)
        require_success(_checkout(baseline, keep, other))
        assert baseline.read_bytes(keep) == data_keep
        assert baseline.read_bytes(other) == data_other
    with workspace() as limited:
        _seed_tracked(limited, keep, data_keep, glob)
        commit_tracked_payload(limited, other, data_other)
        limited.write(
            ".lfsconfig",
            f"[lfs]\n\tfetchinclude = {keep}\n",
        )
        _unlink_worktree(limited, keep, other)
        require_success(_checkout(limited, keep, other))
        got_keep = limited.read_bytes(keep)
        got_other = limited.read_bytes(other)
        print(f"lfsconfig keep_len={len(got_keep)} other_len={len(got_other)}")
        assert got_keep == data_keep
        require_generated_pointer_shape(
            got_other, digest=sha256_hex(data_other), size=len(data_other)
        )
        assert got_other != data_other


def test_smudge_skip_flag_passes_pointer_through():
    data = _payload()
    with workspace() as baseline:
        baseline.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(baseline, data), digest=digest, size=len(data)
        )
        restored = smudge_bytes(baseline, pointer)
        require_success(restored)
        assert restored.stdout == data
        print(f"baseline smudge len={len(restored.stdout)}")
    with workspace() as skipped:
        skipped.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(skipped, data), digest=digest, size=len(data)
        )
        result = smudge_skip_bytes(skipped, pointer)
        print(f"skip smudge exit={result.returncode} len={len(result.stdout)}")
        require_success(result)
        require_generated_pointer_shape(
            result.stdout, digest=digest, size=len(data)
        )
        assert result.stdout != data


def test_skip_smudge_environment_leaves_pointer_in_worktree():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as baseline:
        digest = _seed_tracked(baseline, rel, data, glob)
        _unlink_worktree(baseline, rel)
        require_success(_checkout(baseline, rel))
        assert baseline.read_bytes(rel) == data
        print(f"baseline checkout digest={digest}")
    with workspace() as skipped:
        digest = _seed_tracked(skipped, rel, data, glob)
        _unlink_worktree(skipped, rel)
        require_success(
            _checkout(
                skipped, rel, env_updates=enable_skip_smudge_environment()
            )
        )
        body = skipped.read_bytes(rel)
        print(f"skip-env worktree_len={len(body)}")
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data


def test_install_skip_smudge_checkout_leaves_pointer_text():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as baseline:
        digest = _seed_tracked(baseline, rel, data, glob)
        _unlink_worktree(baseline, rel)
        require_success(_checkout(baseline, rel))
        assert baseline.read_bytes(rel) == data
        print(f"ordinary install checkout digest={digest}")
    with workspace() as skipped:
        digest = _seed_tracked(
            skipped, rel, data, glob, skip_smudge_install=True
        )
        _unlink_worktree(skipped, rel)
        require_success(_checkout(skipped, rel))
        body = skipped.read_bytes(rel)
        print(f"skip-smudge install worktree_len={len(body)}")
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data


# ---------------------------------------------------------------------------
# F. Relocated store root and content-addressed sharing
# ---------------------------------------------------------------------------


def test_relocated_storage_uses_objects_directory_plus_shard_not_default_path(
    isolated_ws,
):
    isolated_ws.init_repo()
    store = isolated_ws.home / f"lfsstore_{token()}"
    store.mkdir()
    configure_storage_root(isolated_ws, store)
    data = _payload()
    digest = sha256_hex(data)
    pointer_from_clean(
        clean_bytes(isolated_ws, data), digest=digest, size=len(data)
    )
    stored = require_object_bytes(store, digest, data)
    require_object_absent(default_lfs_store_root(isolated_ws), digest)
    bogus = store / digest[:2] / digest[2:4] / digest
    try:
        bogus_exists = bogus.exists()
    except OSError as exc:
        raise AssertionError(f"cannot stat {bogus}: {exc}") from exc
    print(f"relocated={stored} bogus_exists={bogus_exists}")
    assert not bogus_exists, (
        "relocated store wrote the shard directly under the configured "
        f"path without an objects directory: {bogus}"
    )


def test_identical_content_shares_one_sharded_object(isolated_ws):
    isolated_ws.init_repo()
    install_local_keeping_process(isolated_ws)
    ext = token()
    glob = f"*.{ext}"
    data = _payload()
    rel_a = f"a_{token()}.{ext}"
    rel_b = f"b_{token()}.{ext}"
    track_pattern(isolated_ws, glob)
    digest = commit_tracked_payload(isolated_ws, rel_a, data)
    commit_tracked_payload(isolated_ws, rel_b, data)
    blob_a = index_blob(isolated_ws, rel_a)
    blob_b = index_blob(isolated_ws, rel_b)
    require_generated_pointer_shape(blob_a, digest=digest, size=len(data))
    require_generated_pointer_shape(blob_b, digest=digest, size=len(data))
    store = default_lfs_store_root(isolated_ws)
    require_object_bytes(store, digest, data)
    matches = list((store / "objects").rglob(digest))
    print(f"shared matches={len(matches)} digest={digest}")
    assert len(matches) == 1, (
        "identical content did not share a single sharded object file: "
        f"{matches!r}"
    )


# ---------------------------------------------------------------------------
# G. Missing object: default fail, skip family, skip-download-errors
# ---------------------------------------------------------------------------


def test_skip_download_errors_allows_checkout_with_pointer_text():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as default:
        digest = _seed_tracked(default, rel, data, glob)
        _remove_object(default, digest)
        configure_unreachable_endpoint(default)
        _unlink_worktree(default, rel)
        failed = _checkout(default, rel)
        print(f"default missing checkout exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        digest = _seed_tracked(skipped, rel, data, glob)
        _remove_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        enable_skip_download_errors(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(skipped, rel)
        print(f"skip-download-errors checkout exit={ok.returncode}")
        require_success(ok)
        body = skipped.read_bytes(rel)
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data
        require_invalid_unlike_success(ok, failed)


def test_skip_download_errors_from_environment_allows_checkout_with_pointer_text():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as default:
        digest = _seed_tracked(default, rel, data, glob)
        _remove_object(default, digest)
        configure_unreachable_endpoint(default)
        _unlink_worktree(default, rel)
        failed = _checkout(default, rel)
        assert failed.returncode != 0
        print(f"default env-carrier checkout exit={failed.returncode}")
    with workspace() as skipped:
        digest = _seed_tracked(skipped, rel, data, glob)
        _remove_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(
            skipped, rel, env_updates=skip_download_errors_environment()
        )
        print(f"skip-download-errors env checkout exit={ok.returncode}")
        require_success(ok)
        body = skipped.read_bytes(rel)
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data
        require_invalid_unlike_success(ok, failed)


def test_skip_download_errors_still_smudges_when_object_is_local():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as default:
        digest = _seed_tracked(default, rel, data, glob)
        _unlink_worktree(default, rel)
        require_success(_checkout(default, rel))
        assert default.read_bytes(rel) == data
        print(f"default local checkout digest={digest}")
    with workspace() as skip_dl:
        digest = _seed_tracked(skip_dl, rel, data, glob)
        enable_skip_download_errors(skip_dl)
        _unlink_worktree(skip_dl, rel)
        require_success(_checkout(skip_dl, rel))
        got = skip_dl.read_bytes(rel)
        print(f"skip-download-errors local len={len(got)}")
        assert got == data
    with workspace() as skip_sm:
        digest = _seed_tracked(skip_sm, rel, data, glob)
        _unlink_worktree(skip_sm, rel)
        require_success(
            _checkout(
                skip_sm, rel, env_updates=enable_skip_smudge_environment()
            )
        )
        body = skip_sm.read_bytes(rel)
        print(f"skip-smudge local len={len(body)}")
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data


def test_smudge_skip_flag_succeeds_when_object_missing():
    data = _payload()
    with workspace() as default:
        default.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(default, data), digest=digest, size=len(data)
        )
        _remove_object(default, digest)
        configure_unreachable_endpoint(default)
        failed = smudge_bytes(default, pointer)
        print(f"default missing smudge exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        skipped.init_repo()
        digest = sha256_hex(data)
        pointer = pointer_from_clean(
            clean_bytes(skipped, data), digest=digest, size=len(data)
        )
        _remove_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        ok = smudge_skip_bytes(skipped, pointer)
        print(f"skip-flag missing smudge exit={ok.returncode}")
        require_success(ok)
        require_generated_pointer_shape(
            ok.stdout, digest=digest, size=len(data)
        )
        assert ok.stdout != data
        require_invalid_unlike_success(ok, failed)


def test_skip_smudge_environment_checkout_succeeds_when_object_missing():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as default:
        digest = _seed_tracked(default, rel, data, glob)
        _remove_object(default, digest)
        configure_unreachable_endpoint(default)
        _unlink_worktree(default, rel)
        failed = _checkout(default, rel)
        print(f"default missing checkout exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        digest = _seed_tracked(skipped, rel, data, glob)
        _remove_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(
            skipped, rel, env_updates=enable_skip_smudge_environment()
        )
        print(f"skip-env missing checkout exit={ok.returncode}")
        require_success(ok)
        body = skipped.read_bytes(rel)
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data
        require_invalid_unlike_success(ok, failed)


def test_install_skip_smudge_checkout_succeeds_when_object_missing():
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    with workspace() as default:
        digest = _seed_tracked(default, rel, data, glob)
        _remove_object(default, digest)
        configure_unreachable_endpoint(default)
        _unlink_worktree(default, rel)
        failed = _checkout(default, rel)
        print(f"ordinary install missing checkout exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        digest = _seed_tracked(
            skipped, rel, data, glob, skip_smudge_install=True
        )
        _remove_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(skipped, rel)
        print(f"skip-smudge install missing checkout exit={ok.returncode}")
        require_success(ok)
        body = skipped.read_bytes(rel)
        require_generated_pointer_shape(body, digest=digest, size=len(data))
        assert body != data
        require_invalid_unlike_success(ok, failed)


# ---------------------------------------------------------------------------
# H. Negative control
# ---------------------------------------------------------------------------


def test_git_add_fails_when_binary_removed_from_path(isolated_ws, product_binary):
    isolated_ws.init_repo()
    install_local_keeping_process(isolated_ws)
    ext = token()
    glob = f"*.{ext}"
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    track_pattern(isolated_ws, glob)
    isolated_ws.write(rel, data)
    present = isolated_ws.git(["add", "--", rel, ".gitattributes"])
    require_success(present)
    hidden_path = path_without_product_bin(isolated_ws.env)
    rel2 = f"payload_{token()}.{ext}"
    isolated_ws.write(rel2, data)
    missing = isolated_ws.git(
        ["add", "--", rel2],
        env_updates={"PATH": hidden_path},
    )
    print(
        f"product_binary={product_binary} hidden_path={hidden_path!r} "
        f"absent-add exit={missing.returncode}"
    )
    assert missing.returncode != 0, (
        "git add succeeded after the product binary was removed from PATH"
    )
    assert (missing.returncode, missing.stdout, missing.stderr) != (
        present.returncode,
        present.stdout,
        present.stderr,
    ), "absent-binary git add was not distinguishable from git add with the binary"
