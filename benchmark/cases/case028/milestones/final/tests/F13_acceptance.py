# feature: F13
"""Object and pointer integrity-check acceptance tests.

PRD: FP-13. Oracles are process status (zero vs non-zero) and local
store occupancy: whether an independently hashed object remains on its
sharded path, and whether corrupt bytes appear in the repository LFS
``bad`` quarantine. Message wording, exit-code numbers, and flag
spellings in output are not pinned.
"""

from __future__ import annotations

from _harness import token, workspace
from _helpers import (
    assert_invalid_unlike_success,
    assert_not_quarantined_bytes,
    assert_object_bytes,
    assert_success,
    bitflip_stored_object,
    commit_tracked_payload,
    configure_fetch_exclude,
    default_lfs_store_root,
    git_add_unfiltered,
    head_oid,
    index_blob,
    install_local_keeping_process,
    path_without_product_bin,
    remove_stored_object,
    require_invalid_unlike_success,
    require_lfs_enable_roles,
    require_not_quarantined_bytes,
    require_object_absent,
    require_object_bytes,
    require_quarantined_bytes,
    require_success,
    run_fsck,
    sha256_hex,
    stage_tracked_payload,
    track_pattern,
)


def _payload() -> bytes:
    return f"blob-{token()}\n".encode("utf-8")


def _rel(prefix: str = "p") -> str:
    return f"{prefix}_{token()}.bin"


def _git_ok(ws, argv, **kwargs):
    result = ws.git(argv, **kwargs)
    assert result.returncode == 0, (
        f"git {argv!r} failed (exit {result.returncode}): {result.stderr_text}"
    )
    return result


def _init_tracked(ws) -> None:
    ws.init_repo()
    install_local_keeping_process(ws)
    track_pattern(ws, "*.bin")


def _store(ws):
    return default_lfs_store_root(ws)


def _commit_two(ws, rel_a: str, data_a: bytes, rel_b: str, data_b: bytes):
    ws.write(rel_a, data_a)
    ws.write(rel_b, data_b)
    to_add = [rel_a, rel_b]
    try:
        ws.read_bytes(".gitattributes")
        to_add.append(".gitattributes")
    except FileNotFoundError:
        pass
    _git_ok(ws, ["add", "--", *to_add])
    _git_ok(ws, ["commit", "-m", f"add {rel_a} {rel_b}"])
    return sha256_hex(data_a), sha256_hex(data_b)


def _clean_one(ws):
    """Init, track, commit one non-empty LFS file. Return store, oid, data, rel."""
    _init_tracked(ws)
    rel = _rel("c")
    data = _payload()
    oid = commit_tracked_payload(ws, rel, data)
    store = _store(ws)
    require_object_bytes(store, oid, data)
    return store, oid, data, rel


def _pair_on_head(ws):
    """One commit with two LFS files U (good) and M (to flip)."""
    _init_tracked(ws)
    u_rel, m_rel = _rel("u"), _rel("m")
    u_data, m_data = _payload(), _payload()
    oid_u, oid_m = _commit_two(ws, u_rel, u_data, m_rel, m_data)
    store = _store(ws)
    require_object_bytes(store, oid_u, u_data)
    require_object_bytes(store, oid_m, m_data)
    return {
        "store": store,
        "u_rel": u_rel,
        "m_rel": m_rel,
        "u_data": u_data,
        "m_data": m_data,
        "oid_u": oid_u,
        "oid_m": oid_m,
    }


def _add_with_attrs(ws, rel: str) -> None:
    """Stage *rel* and the attributes file if it exists (not a product oracle)."""
    to_add = [rel]
    try:
        ws.read_bytes(".gitattributes")
        to_add.append(".gitattributes")
    except FileNotFoundError:
        pass
    _git_ok(ws, ["add", "--", *to_add])


def _stage_gitattributes(ws) -> None:
    """Stage `.gitattributes` if present so the commit carries LFS roles."""
    try:
        ws.read_bytes(".gitattributes")
    except FileNotFoundError:
        raise AssertionError(
            "setup: .gitattributes is missing; track did not write it"
        ) from None
    _git_ok(ws, ["add", "--", ".gitattributes"])


def _commit_crlf_pointer(ws, rel: str, data: bytes) -> tuple[str, bytes]:
    """Commit *rel* as a CRLF pointer for *data*. Object bytes stay hashed."""
    ws.write(rel, data)
    _add_with_attrs(ws, rel)
    blob = index_blob(ws, rel)
    crlf = blob.replace(b"\n", b"\r\n")
    assert b"\r" in crlf, f"CRLF rewrite produced no CR: {crlf!r}"
    ws.write(rel, crlf)
    git_add_unfiltered(ws, rel)
    staged = index_blob(ws, rel)
    assert b"\r" in staged, (
        f"setup: index blob for {rel!r} has no CR after unfiltered add"
    )
    _git_ok(ws, ["commit", "-m", f"crlf {rel}"])
    committed = _blob_at(ws, "HEAD", rel)
    assert b"\r" in committed, (
        f"setup: HEAD blob for {rel!r} has no CR after commit"
    )
    require_lfs_enable_roles(ws, rel)
    return sha256_hex(data), crlf


def _commit_raw_blob(ws, rel: str, data: bytes) -> bytes:
    """Commit *rel* as ordinary Git bytes despite LFS attributes."""
    _stage_gitattributes(ws)
    ws.write(rel, data)
    git_add_unfiltered(ws, rel)
    staged = index_blob(ws, rel)
    assert staged == data, (
        f"setup: index blob for {rel!r} is not the raw payload"
    )
    _git_ok(ws, ["commit", "-m", f"raw {rel}"])
    committed = _blob_at(ws, "HEAD", rel)
    assert committed == data, (
        f"setup: HEAD blob for {rel!r} is not the raw payload"
    )
    require_lfs_enable_roles(ws, rel)
    return data


def _blob_at(ws, commit: str, rel: str) -> bytes:
    result = ws.git(["cat-file", "blob", f"{commit}:{rel}"])
    assert result.returncode == 0, (
        f"git cat-file blob {commit}:{rel} failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    return result.stdout


def _history_unique_d(ws, *, crlf: bool = False):
    """C0 has U; C1 adds unique D; C2/HEAD deletes D. U remains."""
    _init_tracked(ws)
    u_rel, d_rel = _rel("u"), _rel("d")
    u_data, d_data = _payload(), _payload()
    oid_u = commit_tracked_payload(ws, u_rel, u_data)
    c0 = head_oid(ws)
    crlf_doc = b""
    if crlf:
        oid_d, crlf_doc = _commit_crlf_pointer(ws, d_rel, d_data)
    else:
        oid_d = commit_tracked_payload(ws, d_rel, d_data)
    c1 = head_oid(ws)
    _git_ok(ws, ["rm", "-f", "--", d_rel])
    _git_ok(ws, ["commit", "-m", f"rm {d_rel}"])
    c2 = head_oid(ws)
    store = _store(ws)
    require_object_bytes(store, oid_u, u_data)
    require_object_bytes(store, oid_d, d_data)
    return {
        "store": store,
        "u_rel": u_rel,
        "d_rel": d_rel,
        "u_data": u_data,
        "d_data": d_data,
        "oid_u": oid_u,
        "oid_d": oid_d,
        "c0": c0,
        "c1": c1,
        "c2": c2,
        "crlf_doc": crlf_doc,
    }


def _dirty_head_with_range(ws):
    """C0 U, C1 extra good file, HEAD adds M then M is flipped. Align M to U."""
    _init_tracked(ws)
    u_rel, v_rel, m_rel = _rel("u"), _rel("v"), _rel("m")
    u_data, v_data, m_data = _payload(), _payload(), _payload()
    oid_u = commit_tracked_payload(ws, u_rel, u_data)
    c0 = head_oid(ws)
    oid_v = commit_tracked_payload(ws, v_rel, v_data)
    c1 = head_oid(ws)
    oid_m = commit_tracked_payload(ws, m_rel, m_data)
    store = _store(ws)
    require_object_bytes(store, oid_u, u_data)
    require_object_bytes(store, oid_v, v_data)
    require_object_bytes(store, oid_m, m_data)
    corrupt_m = bitflip_stored_object(ws, oid_m, align_mtime_oid=oid_u)
    return {
        "store": store,
        "oid_u": oid_u,
        "oid_v": oid_v,
        "oid_m": oid_m,
        "u_data": u_data,
        "m_data": m_data,
        "corrupt_m": corrupt_m,
        "c0": c0,
        "c1": c1,
    }


# ---------------------------------------------------------------------------
# A. Clean repository: omitted / HEAD / two-dot / direct binary
# ---------------------------------------------------------------------------


def test_omitted_head_and_clean_dry_run_succeed():
    """Omitted revision, explicit HEAD, and clean dry-run exit 0 and leave the object."""
    with workspace() as ws:
        store, oid, data, rel = _clean_one(ws)
        omitted = run_fsck(ws)
        print(f"omitted fsck exit={omitted.returncode} rel={rel}")
        assert_success(omitted)
        assert_object_bytes(store, oid, data)
        assert_not_quarantined_bytes(ws, data)
        named = run_fsck(ws, ["HEAD"])
        print(f"HEAD fsck exit={named.returncode}")
        assert_success(named)
        assert_object_bytes(store, oid, data)
        dry = run_fsck(ws, ["--dry-run"])
        print(f"clean dry-run exit={dry.returncode}")
        assert_success(dry)
        assert_object_bytes(store, oid, data)
        assert_not_quarantined_bytes(ws, data)


def test_direct_binary_fsck_succeeds_on_clean_repo():
    """Direct product binary fsck succeeds on a clean tracked file."""
    with workspace() as ws:
        store, oid, data, rel = _clean_one(ws)
        result = ws.invoke(["fsck"])
        print(f"direct fsck exit={result.returncode} rel={rel}")
        assert_success(result)
        assert_object_bytes(store, oid, data)
        assert_not_quarantined_bytes(ws, data)


def test_two_dot_range_succeeds_on_clean_segment():
    """Two-dot range over a clean history exits 0."""
    with workspace() as ws:
        _init_tracked(ws)
        a_rel, b_rel = _rel("a"), _rel("b")
        a_data, b_data = _payload(), _payload()
        oid_a = commit_tracked_payload(ws, a_rel, a_data)
        c0 = head_oid(ws)
        oid_b = commit_tracked_payload(ws, b_rel, b_data)
        store = _store(ws)
        span = f"{c0}..HEAD"
        result = run_fsck(ws, [span])
        print(f"two-dot clean exit={result.returncode} span={span}")
        assert_success(result)
        assert_object_bytes(store, oid_a, a_data)
        assert_object_bytes(store, oid_b, b_data)
        assert_not_quarantined_bytes(ws, a_data)
        assert_not_quarantined_bytes(ws, b_data)


# ---------------------------------------------------------------------------
# B. Object checks: hash mismatch quarantines; missing does not
# ---------------------------------------------------------------------------


def test_hash_mismatch_quarantines_corrupt_leaves_neighbor():
    """Bit-flipped object is moved to bad; timestamp-aligned neighbor stays."""
    with workspace() as ws:
        layout = _pair_on_head(ws)
        corrupt = bitflip_stored_object(
            ws, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        require_object_bytes(layout["store"], layout["oid_m"], corrupt)
        result = run_fsck(ws)
        print(f"mismatch fsck exit={result.returncode}")
        assert result.returncode != 0, (
            "hash-mismatched object was not a finding: "
            f"exit={result.returncode}"
        )
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(ws, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
        require_not_quarantined_bytes(ws, layout["u_data"])


def test_missing_object_fails_without_quarantine_leaves_neighbor():
    """A missing object is a non-zero finding and is not moved into bad."""
    with workspace() as ws:
        layout = _pair_on_head(ws)
        pointer = index_blob(ws, layout["m_rel"])
        ws.write(layout["m_rel"], pointer)
        remove_stored_object(ws, layout["oid_m"])
        require_object_absent(layout["store"], layout["oid_m"])
        result = run_fsck(ws, ["--objects"])
        print(
            f"missing fsck exit={result.returncode} "
            f"stdout={result.stdout_text!r} stderr={result.stderr_text!r}"
        )
        assert result.returncode != 0, (
            "missing object was not a finding: "
            f"exit={result.returncode} stdout={result.stdout_text!r} "
            f"stderr={result.stderr_text!r}"
        )
        require_not_quarantined_bytes(ws, layout["m_data"])
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
        require_not_quarantined_bytes(ws, layout["u_data"])
        require_object_absent(layout["store"], layout["oid_m"])


# ---------------------------------------------------------------------------
# C. Dry-run: report without moving; live baseline actually moves
# ---------------------------------------------------------------------------


def test_dry_run_reports_without_moving_unlike_live():
    """Dry-run is non-zero and leaves the flipped file; live quarantines it."""
    with workspace() as live:
        layout = _pair_on_head(live)
        corrupt = bitflip_stored_object(
            live, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        moved = run_fsck(live)
        print(f"live mismatch exit={moved.returncode}")
        assert moved.returncode != 0, (
            "live object check did not fail on a hash mismatch"
        )
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(live, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
    with workspace() as dry:
        layout = _pair_on_head(dry)
        corrupt = bitflip_stored_object(
            dry, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        reported = run_fsck(dry, ["--dry-run"])
        print(f"dry-run mismatch exit={reported.returncode}")
        assert reported.returncode != 0, (
            "dry-run did not report the hash mismatch"
        )
        require_object_bytes(layout["store"], layout["oid_m"], corrupt)
        require_not_quarantined_bytes(dry, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])


# ---------------------------------------------------------------------------
# D. Pointer checks: CRLF and non-pointer blob; report, do not quarantine
# ---------------------------------------------------------------------------


def test_crlf_pointer_fails_and_is_not_quarantined():
    """A CRLF pointer is a finding and is not moved into bad."""
    with workspace() as clean:
        _init_tracked(clean)
        rel = _rel("ok")
        data = _payload()
        oid = commit_tracked_payload(clean, rel, data)
        ok = run_fsck(clean)
        print(f"canonical pointer fsck exit={ok.returncode}")
        require_success(ok)
        require_object_bytes(_store(clean), oid, data)
    with workspace() as dirty:
        _init_tracked(dirty)
        rel = _rel("cr")
        data = _payload()
        oid, crlf = _commit_crlf_pointer(dirty, rel, data)
        require_lfs_enable_roles(dirty, rel)
        staged = index_blob(dirty, rel)
        assert b"\r" in staged, "setup: HEAD index blob has no CR"
        store = _store(dirty)
        require_object_bytes(store, oid, data)
        result = run_fsck(dirty)
        print(f"CRLF pointer fsck exit={result.returncode}")
        assert result.returncode != 0, (
            "CRLF pointer was not a finding: "
            f"exit={result.returncode}"
        )
        require_object_bytes(store, oid, data)
        require_not_quarantined_bytes(dirty, data)
        require_not_quarantined_bytes(dirty, crlf)


def test_lfs_attributed_non_pointer_fails_and_is_not_quarantined():
    """An LFS-attributed path stored as an ordinary blob is a finding."""
    with workspace() as clean:
        _init_tracked(clean)
        rel = _rel("ok")
        data = _payload()
        oid = commit_tracked_payload(clean, rel, data)
        ok = run_fsck(clean, ["--pointers"])
        print(f"clean pointer-check exit={ok.returncode}")
        require_success(ok)
        require_object_bytes(_store(clean), oid, data)
    with workspace() as dirty:
        _init_tracked(dirty)
        rel = _rel("raw")
        data = _payload()
        _commit_raw_blob(dirty, rel, data)
        require_lfs_enable_roles(dirty, rel)
        staged = index_blob(dirty, rel)
        assert staged == data, "setup: index blob is not the raw payload"
        result = run_fsck(dirty, ["--pointers"])
        print(f"non-pointer blob fsck exit={result.returncode}")
        assert result.returncode != 0, (
            "LFS-attributed ordinary blob was not a finding: "
            f"exit={result.returncode}"
        )
        require_not_quarantined_bytes(dirty, data)


# ---------------------------------------------------------------------------
# E. Both checks by default; each kind may be requested alone
# ---------------------------------------------------------------------------


def test_objects_only_ignores_pointer_only_defect():
    """Object checks alone do not treat a CRLF pointer as a finding."""
    with workspace() as default_ws:
        _init_tracked(default_ws)
        rel = _rel("cr")
        data = _payload()
        oid, crlf = _commit_crlf_pointer(default_ws, rel, data)
        store = _store(default_ws)
        require_object_bytes(store, oid, data)
        default = run_fsck(default_ws)
        print(f"default on CRLF exit={default.returncode}")
        assert default.returncode != 0, (
            "default fsck did not catch a pointer-only defect"
        )
        require_object_bytes(store, oid, data)
        require_not_quarantined_bytes(default_ws, data)
        require_not_quarantined_bytes(default_ws, crlf)
    with workspace() as ptr:
        _init_tracked(ptr)
        rel = _rel("cr")
        data = _payload()
        oid, crlf = _commit_crlf_pointer(ptr, rel, data)
        pointers = run_fsck(ptr, ["--pointers"])
        print(f"pointers-only on CRLF exit={pointers.returncode}")
        assert pointers.returncode != 0, (
            "pointer checks did not catch a CRLF pointer"
        )
        require_object_bytes(_store(ptr), oid, data)
        require_not_quarantined_bytes(ptr, crlf)
    with workspace() as obj:
        _init_tracked(obj)
        rel = _rel("cr")
        data = _payload()
        oid, crlf = _commit_crlf_pointer(obj, rel, data)
        objects = run_fsck(obj, ["--objects"])
        print(f"objects-only on CRLF exit={objects.returncode}")
        require_success(objects)
        require_object_bytes(_store(obj), oid, data)
        require_not_quarantined_bytes(obj, data)
        require_not_quarantined_bytes(obj, crlf)


def test_pointers_only_ignores_object_corruption():
    """Pointer checks alone do not treat a flipped object as a finding."""
    with workspace() as default_ws:
        layout = _pair_on_head(default_ws)
        corrupt = bitflip_stored_object(
            default_ws, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        default = run_fsck(default_ws)
        print(f"default on mismatch exit={default.returncode}")
        assert default.returncode != 0, (
            "default fsck did not catch object corruption"
        )
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(default_ws, corrupt)
    with workspace() as obj:
        layout = _pair_on_head(obj)
        corrupt = bitflip_stored_object(
            obj, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        objects = run_fsck(obj, ["--objects"])
        print(f"objects-only on mismatch exit={objects.returncode}")
        assert objects.returncode != 0, (
            "object checks did not catch a hash mismatch"
        )
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(obj, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
    with workspace() as ptr:
        layout = _pair_on_head(ptr)
        corrupt = bitflip_stored_object(
            ptr, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        pointers = run_fsck(ptr, ["--pointers"])
        print(f"pointers-only on mismatch exit={pointers.returncode}")
        require_success(pointers)
        require_object_bytes(layout["store"], layout["oid_m"], corrupt)
        require_not_quarantined_bytes(ptr, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])


# ---------------------------------------------------------------------------
# F. Omitted default object checks cover the index; explicit HEAD does not
# ---------------------------------------------------------------------------


def _index_only_flipped(ws):
    """HEAD has good U; index-only I is staged and flipped, timestamps aligned."""
    _init_tracked(ws)
    u_rel, i_rel = _rel("u"), _rel("i")
    u_data, i_data = _payload(), _payload()
    oid_u = commit_tracked_payload(ws, u_rel, u_data)
    oid_i = stage_tracked_payload(ws, i_rel, i_data)
    store = _store(ws)
    require_object_bytes(store, oid_u, u_data)
    require_object_bytes(store, oid_i, i_data)
    staged = index_blob(ws, i_rel)
    assert staged != i_data, (
        "setup: index-only path was not stored as a pointer"
    )
    corrupt_i = bitflip_stored_object(ws, oid_i, align_mtime_oid=oid_u)
    return {
        "store": store,
        "oid_u": oid_u,
        "oid_i": oid_i,
        "u_data": u_data,
        "i_data": i_data,
        "corrupt_i": corrupt_i,
        "i_rel": i_rel,
    }


def test_omitted_default_checks_index_unlike_explicit_head():
    """Omitted default isolates an index-only flipped object; explicit HEAD does not."""
    with workspace() as omitted:
        layout = _index_only_flipped(omitted)
        result = run_fsck(omitted)
        print(
            f"omitted default index-only exit={result.returncode} "
            f"rel={layout['i_rel']}"
        )
        assert result.returncode != 0, (
            "omitted-revision default did not check the index-only path"
        )
        require_object_absent(layout["store"], layout["oid_i"])
        require_quarantined_bytes(omitted, layout["corrupt_i"])
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
    with workspace() as named:
        layout = _index_only_flipped(named)
        result = run_fsck(named, ["HEAD"])
        print(f"explicit HEAD index-only exit={result.returncode}")
        require_success(result)
        require_object_bytes(layout["store"], layout["oid_i"], layout["corrupt_i"])
        require_not_quarantined_bytes(named, layout["corrupt_i"])
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])


def test_objects_only_omitted_checks_index_unlike_explicit_head():
    """Object checks alone: omitted covers the index; explicit HEAD does not."""
    with workspace() as omitted:
        layout = _index_only_flipped(omitted)
        result = run_fsck(omitted, ["--objects"])
        print(f"omitted --objects index-only exit={result.returncode}")
        assert result.returncode != 0, (
            "omitted object checks did not cover the index-only path"
        )
        require_object_absent(layout["store"], layout["oid_i"])
        require_quarantined_bytes(omitted, layout["corrupt_i"])
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])
    with workspace() as named:
        layout = _index_only_flipped(named)
        result = run_fsck(named, ["--objects", "HEAD"])
        print(f"HEAD --objects index-only exit={result.returncode}")
        require_success(result)
        require_object_bytes(layout["store"], layout["oid_i"], layout["corrupt_i"])
        require_not_quarantined_bytes(named, layout["corrupt_i"])


# ---------------------------------------------------------------------------
# G. Fetch-exclude skips matching object checks, not pointer checks
# ---------------------------------------------------------------------------


def test_fetch_exclude_skips_matching_object_not_unmatched():
    """Exclude omits only the matching flipped path; the unmatched path is still isolated."""
    with workspace() as excluded:
        layout = _pair_on_head(excluded)
        configure_fetch_exclude(excluded, layout["m_rel"])
        corrupt_m = bitflip_stored_object(
            excluded, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        corrupt_u = bitflip_stored_object(
            excluded, layout["oid_u"], align_mtime_oid=layout["oid_m"]
        )
        result = run_fsck(excluded, ["--objects"])
        print(
            f"exclude objects exit={result.returncode} "
            f"match={layout['m_rel']}"
        )
        assert result.returncode != 0, (
            "object checks skipped every path once exclude was set"
        )
        require_object_absent(layout["store"], layout["oid_u"])
        require_quarantined_bytes(excluded, corrupt_u)
        require_object_bytes(layout["store"], layout["oid_m"], corrupt_m)
        require_not_quarantined_bytes(excluded, corrupt_m)
    with workspace() as baseline:
        layout = _pair_on_head(baseline)
        corrupt_m = bitflip_stored_object(
            baseline, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        corrupt_u = bitflip_stored_object(
            baseline, layout["oid_u"], align_mtime_oid=layout["oid_m"]
        )
        result = run_fsck(baseline, ["--objects"])
        print(f"no-exclude both-flipped exit={result.returncode}")
        assert result.returncode != 0, (
            "live object check did not fail when both objects were flipped"
        )
        require_object_absent(layout["store"], layout["oid_u"])
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(baseline, corrupt_u)
        require_quarantined_bytes(baseline, corrupt_m)


def test_fetch_exclude_does_not_skip_pointer_check():
    """A pointer defect on an excluded path is still a pointer-check finding."""
    with workspace() as ws:
        _init_tracked(ws)
        u_rel, m_rel = _rel("u"), _rel("m")
        u_data, m_data = _payload(), _payload()
        oid_u = commit_tracked_payload(ws, u_rel, u_data)
        oid_m, crlf = _commit_crlf_pointer(ws, m_rel, m_data)
        configure_fetch_exclude(ws, m_rel)
        store = _store(ws)
        require_object_bytes(store, oid_u, u_data)
        require_object_bytes(store, oid_m, m_data)
        staged = index_blob(ws, m_rel)
        assert b"\r" in staged, "setup: excluded path blob has no CR"
        objects = run_fsck(ws, ["--objects"])
        print(f"exclude objects-only on pointer defect exit={objects.returncode}")
        require_success(objects)
        pointers = run_fsck(ws, ["--pointers"])
        print(f"exclude pointers-only on pointer defect exit={pointers.returncode}")
        assert pointers.returncode != 0, (
            "fetch-exclude skipped pointer checks for the matching path"
        )
        require_object_bytes(store, oid_m, m_data)
        require_not_quarantined_bytes(ws, m_data)
        require_not_quarantined_bytes(ws, crlf)


# ---------------------------------------------------------------------------
# H. Committish / two-dot are the checked set; unresolvable does not scan default
# ---------------------------------------------------------------------------


def test_single_committish_checks_that_commit_not_head():
    """A flipped object unique to C1 is found at C1 and not at HEAD."""
    with workspace() as at_c1:
        hist = _history_unique_d(at_c1)
        corrupt = bitflip_stored_object(
            at_c1, hist["oid_d"], align_mtime_oid=hist["oid_u"]
        )
        result = run_fsck(at_c1, ["--objects", hist["c1"]])
        print(f"objects C1 unique-D exit={result.returncode}")
        assert result.returncode != 0, (
            "single committish did not check that commit's unique path"
        )
        require_object_absent(hist["store"], hist["oid_d"])
        require_quarantined_bytes(at_c1, corrupt)
        require_object_bytes(hist["store"], hist["oid_u"], hist["u_data"])
    with workspace() as at_head:
        hist = _history_unique_d(at_head)
        corrupt = bitflip_stored_object(
            at_head, hist["oid_d"], align_mtime_oid=hist["oid_u"]
        )
        result = run_fsck(at_head, ["--objects", "HEAD"])
        print(f"objects HEAD unique-D exit={result.returncode}")
        require_success(result)
        require_object_bytes(hist["store"], hist["oid_d"], corrupt)
        require_not_quarantined_bytes(at_head, corrupt)
        require_object_bytes(hist["store"], hist["oid_u"], hist["u_data"])


def test_two_dot_range_checks_that_segment():
    """C0..C1 finds C1's unique flipped object; C1..HEAD does not."""
    with workspace() as in_range:
        hist = _history_unique_d(in_range)
        corrupt = bitflip_stored_object(
            in_range, hist["oid_d"], align_mtime_oid=hist["oid_u"]
        )
        span = f"{hist['c0']}..{hist['c1']}"
        result = run_fsck(in_range, ["--objects", span])
        print(f"objects {span} exit={result.returncode}")
        assert result.returncode != 0, (
            "two-dot range did not check the segment that still has D"
        )
        require_object_absent(hist["store"], hist["oid_d"])
        require_quarantined_bytes(in_range, corrupt)
        require_object_bytes(hist["store"], hist["oid_u"], hist["u_data"])
    with workspace() as out_range:
        hist = _history_unique_d(out_range)
        corrupt = bitflip_stored_object(
            out_range, hist["oid_d"], align_mtime_oid=hist["oid_u"]
        )
        span = f"{hist['c1']}..HEAD"
        result = run_fsck(out_range, ["--objects", span])
        print(f"objects {span} exit={result.returncode}")
        require_success(result)
        require_object_bytes(hist["store"], hist["oid_d"], corrupt)
        require_not_quarantined_bytes(out_range, corrupt)


def test_pointer_check_follows_committish_and_range():
    """Pointer checks use the named committish/range, not always HEAD."""
    with workspace() as ws:
        hist = _history_unique_d(ws, crlf=True)
        blob = _blob_at(ws, hist["c1"], hist["d_rel"])
        assert b"\r" in blob, (
            f"setup: C1 blob for {hist['d_rel']!r} has no CR"
        )
        store = hist["store"]
        require_object_bytes(store, hist["oid_d"], hist["d_data"])
        at_c1 = run_fsck(ws, ["--pointers", hist["c1"]])
        print(f"pointers C1 CRLF exit={at_c1.returncode}")
        assert at_c1.returncode != 0, (
            "pointer checks at C1 did not catch that commit's CRLF pointer"
        )
        span_in = f"{hist['c0']}..{hist['c1']}"
        in_range = run_fsck(ws, ["--pointers", span_in])
        print(f"pointers {span_in} exit={in_range.returncode}")
        assert in_range.returncode != 0, (
            "pointer checks over C0..C1 did not catch C1's CRLF pointer"
        )
        at_head = run_fsck(ws, ["--pointers", "HEAD"])
        print(f"pointers HEAD after D removed exit={at_head.returncode}")
        require_success(at_head)
        span_out = f"{hist['c1']}..HEAD"
        out_range = run_fsck(ws, ["--pointers", span_out])
        print(f"pointers {span_out} exit={out_range.returncode}")
        require_success(out_range)
        require_object_bytes(store, hist["oid_d"], hist["d_data"])
        require_not_quarantined_bytes(ws, hist["d_data"])
        require_not_quarantined_bytes(ws, hist["crlf_doc"])


def test_unresolvable_argument_unlike_omitted_success():
    """A runtime token that is not a committish or two-dot range is non-zero."""
    with workspace() as ws:
        store, oid, data, rel = _clean_one(ws)
        omitted = run_fsck(ws)
        print(f"omitted fsck exit={omitted.returncode} rel={rel}")
        assert_success(omitted)
        assert_object_bytes(store, oid, data)
        assert_not_quarantined_bytes(ws, data)
        bogus = f"zxq_{token()}"
        dirty = run_fsck(ws, [bogus])
        print(f"unresolvable {bogus!r} exit={dirty.returncode}")
        assert_invalid_unlike_success(omitted, dirty)
        assert_object_bytes(store, oid, data)
        assert_not_quarantined_bytes(ws, data)


def test_unresolvable_argument_does_not_complete_default_check():
    """An unresolvable token must not quarantine a flipped HEAD object."""
    with workspace() as live:
        layout = _pair_on_head(live)
        corrupt = bitflip_stored_object(
            live, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        omitted = run_fsck(live)
        print(f"live omitted mismatch exit={omitted.returncode}")
        assert omitted.returncode != 0, (
            "omitted revision did not isolate the flipped HEAD object"
        )
        require_object_absent(layout["store"], layout["oid_m"])
        require_quarantined_bytes(live, corrupt)
    with workspace() as blocked:
        layout = _pair_on_head(blocked)
        corrupt = bitflip_stored_object(
            blocked, layout["oid_m"], align_mtime_oid=layout["oid_u"]
        )
        bogus = f"zxq_{token()}"
        result = run_fsck(blocked, [bogus])
        print(f"unresolvable dirty-HEAD exit={result.returncode} arg={bogus}")
        assert result.returncode != 0, (
            "unresolvable argument exited 0"
        )
        require_object_bytes(layout["store"], layout["oid_m"], corrupt)
        require_not_quarantined_bytes(blocked, corrupt)
        require_object_bytes(layout["store"], layout["oid_u"], layout["u_data"])


def test_three_dot_does_not_complete_default_check():
    """Three-dot is unresolvable: non-zero, and a flipped HEAD object stays put."""
    with workspace() as live:
        hist = _dirty_head_with_range(live)
        omitted = run_fsck(live)
        print(f"live omitted for three-dot baseline exit={omitted.returncode}")
        assert omitted.returncode != 0, (
            "omitted revision did not isolate the flipped HEAD object"
        )
        require_object_absent(hist["store"], hist["oid_m"])
        require_quarantined_bytes(live, hist["corrupt_m"])
    with workspace() as ws:
        hist = _dirty_head_with_range(ws)
        two = f"{hist['c0']}..{hist['c1']}"
        two_dot = run_fsck(ws, [two])
        print(f"two-dot {two} exit={two_dot.returncode}")
        require_success(two_dot)
        require_object_bytes(hist["store"], hist["oid_m"], hist["corrupt_m"])
        three = f"{hist['c0']}...{hist['c1']}"
        three_dot = run_fsck(ws, [three])
        print(f"three-dot {three} exit={three_dot.returncode}")
        assert three_dot.returncode != 0, (
            "three-dot range token was treated as a successful check"
        )
        require_object_bytes(hist["store"], hist["oid_m"], hist["corrupt_m"])
        require_not_quarantined_bytes(ws, hist["corrupt_m"])
        require_invalid_unlike_success(two_dot, three_dot)


# ---------------------------------------------------------------------------
# I. PATH negative control
# ---------------------------------------------------------------------------


def test_fsck_fails_without_product_on_path():
    """Fsck without the product on PATH is non-success; with PATH it succeeds."""
    with workspace() as ws:
        store, oid, data, rel = _clean_one(ws)
        blocked = run_fsck(
            ws,
            env_updates={"PATH": path_without_product_bin(ws.env)},
        )
        print(f"PATH-blocked fsck exit={blocked.returncode} rel={rel}")
        assert blocked.returncode != 0, (
            "fsck succeeded after the product was removed from PATH"
        )
        require_object_bytes(store, oid, data)
        require_success(run_fsck(ws))
        require_object_bytes(store, oid, data)
        require_not_quarantined_bytes(ws, data)
