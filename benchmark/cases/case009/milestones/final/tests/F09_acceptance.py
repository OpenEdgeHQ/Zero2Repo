# feature: F09
"""Push porcelain and pre-push hook acceptance tests.

PRD: FP-09. Observations are which objects are PUT, whether a dry-run
remainder is a stable designation of the pending set after covariate
stripping in one workspace, whether Git refs move, and whether a later
clone/pull restores working-tree bytes. Message wording, exit-code
numbers, dry-run layout, and lock JSON field names are not pinned.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _harness import reserve_loopback_port, token, workspace
from _helpers import (
    add_git_remote,
    assert_dry_run_remainder_stable_unlike,
    assert_invalid_unlike_success,
    assert_no_put_of,
    assert_put_of,
    caller_visible,
    commit_tracked_payload,
    configure_unreachable_endpoint,
    conforming_batch_server,
    disable_lock_verification,
    dry_run_remainder,
    enable_lock_verification,
    foreign_lock_on_path_server,
    git_state_sha_tokens,
    git_zero_oid,
    head_oid,
    init_bare_git_remote,
    install_local_keeping_process,
    path_without_product_bin,
    point_lfs_at,
    pre_push_stdin,
    prepare_tracked_commit,
    require_ref_at,
    require_success,
    require_working_tree_bytes,
    set_lfs_endpoint,
    set_remote_tracking,
    skip_push_environment,
    storing_batch_server,
)


def _payload(*, pad: int = 0) -> bytes:
    return (f"blob-{token()}\n" + ("x" * pad)).encode("utf-8")


def _tracked_rel(prefix: str = "payload") -> str:
    return f"{prefix}_{token()}.bin"


def _records_since(svc, start: int):
    return svc.records[start:]


def _origin_url(ws) -> str:
    result = ws.git(["remote", "get-url", "origin"])
    assert result.returncode == 0, (
        f"git remote get-url origin failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    url = result.stdout_text.strip()
    assert url, "origin remote URL is empty"
    return url


def _git_ok(ws, argv, **kwargs):
    result = ws.git(argv, **kwargs)
    assert result.returncode == 0, (
        f"git {argv!r} failed (exit {result.returncode}): {result.stderr_text}"
    )
    return result


def _porcelain_http(ws, url: str) -> None:
    ws.init_repo()
    point_lfs_at(ws, url)
    disable_lock_verification(ws)


def _bare_origin(ws, url: str):
    ws.init_repo()
    bare = init_bare_git_remote(ws, f"bare_{token()}")
    add_git_remote(ws, "origin", str(bare))
    set_lfs_endpoint(ws, url)
    disable_lock_verification(ws)
    return bare


def _restore_push_source(ws, url: str, rel: str, payload: bytes):
    """A subdirectory source plus a sibling bare remote.

    Dest clone must not sit inside the source worktree: a nested dest
    can materialize from the source local store without a PUT.
    """
    src_rel = f"src_{token()}"
    src = ws.init_repo(src_rel)
    bare = init_bare_git_remote(ws, f"bare_{token()}")
    added = ws.git(["remote", "add", "origin", str(bare)], cwd=src)
    assert added.returncode == 0, (
        f"git remote add origin failed (exit {added.returncode}): "
        f"{added.stderr_text}"
    )
    for key, value in (
        ("lfs.url", url),
        ("lfs.transfer.maxretries", "1"),
        ("lfs.transfer.maxretrydelay", "0"),
        ("lfs.dialtimeout", "1"),
        ("lfs.locksverify", "false"),
    ):
        written = ws.git_config_set(key, value, local=True, cwd=src)
        assert written.returncode == 0, written.stderr_text
    require_success(ws.invoke_via_git(["install", "--local"], cwd=src))
    cfg = ws.git_config_set("lfs.url", url, file=".lfsconfig", cwd=src)
    assert cfg.returncode == 0, cfg.stderr_text
    locks = ws.git_config_set(
        "lfs.locksverify", "false", file=".lfsconfig", cwd=src
    )
    assert locks.returncode == 0, locks.stderr_text
    _git_ok(ws, ["add", "--", ".lfsconfig"], cwd=src)
    _git_ok(ws, ["commit", "-m", "lfsconfig"], cwd=src)
    suffix = Path(rel).suffix
    assert suffix, f"tracked relpath {rel!r} has no suffix"
    require_success(ws.invoke_via_git(["track", f"*{suffix}"], cwd=src))
    ws.write(f"{src_rel}/{rel}", payload)
    to_add = [rel]
    try:
        ws.read_bytes(f"{src_rel}/.gitattributes")
        to_add.append(".gitattributes")
    except FileNotFoundError:
        pass
    _git_ok(ws, ["add", "--", *to_add], cwd=src)
    _git_ok(ws, ["commit", "-m", f"add {rel}"], cwd=src)
    return src, bare


def _dry_strip(ws, result, *payloads: bytes, extra: tuple[str, ...] = ()):
    tokens = [
        str(ws.path.resolve()),
        ws.path.name,
        _origin_url(ws),
        *git_state_sha_tokens(ws),
        *extra,
    ]
    for data in payloads:
        tokens.append(data.decode("utf-8"))
    return dry_run_remainder(caller_visible(result), strip=tokens)


def _invoke_dry_run(
    ws,
    kind: str,
    *,
    ref: str = "main",
    local_sha: str | None = None,
    remote_sha: str | None = None,
):
    if kind == "push":
        return ws.invoke_via_git(["push", "--dry-run", "origin", ref])
    if local_sha is None:
        local_sha = head_oid(ws)
    if remote_sha is None:
        remote_sha = git_zero_oid()
    stdin = pre_push_stdin(
        local_ref=f"refs/heads/{ref}",
        local_sha=local_sha,
        remote_ref=f"refs/heads/{ref}",
        remote_sha=remote_sha,
    )
    return ws.invoke_via_git(
        ["pre-push", "--dry-run", "origin", _origin_url(ws)],
        stdin=stdin,
    )


def _plant_tracking(ws, sha: str, *, name: str = "main") -> None:
    set_remote_tracking(ws, "origin", name, sha)


def _install_global_filters(ws) -> None:
    """Setup: install filters in this workspace's Git global scope.

    A later clone dest has no repository-local filters of its own. Same
    setup F08 uses before clone; not an install-scope oracle.
    """
    require_success(ws.invoke_via_git(["install", "--skip-repo"]))


def _orphan_commit(ws, rel: str, data: bytes) -> tuple[str, str]:
    """Commit *data* on a new orphan branch and return to main.

    The orphan's worktree must not keep main's files as untracked leftovers:
    checking out main would then refuse to overwrite them, and dropping
    attributes would store the new path as an ordinary blob.
    """
    branch = f"br_{token()}"
    try:
        attrs = ws.read_bytes(".gitattributes")
    except FileNotFoundError as exc:
        raise AssertionError(
            ".gitattributes missing before orphan commit; "
            "cannot restore tracking on the new branch"
        ) from exc
    orphaned = ws.git(["checkout", "--orphan", branch])
    assert orphaned.returncode == 0, (
        f"git checkout --orphan failed: {orphaned.stderr_text}"
    )
    wiped = ws.git(["rm", "-rf", "."])
    assert wiped.returncode == 0, (
        f"git rm -rf . after orphan failed: {wiped.stderr_text}"
    )
    cleaned = ws.git(["clean", "-fd"])
    assert cleaned.returncode == 0, (
        f"git clean -fd after orphan failed: {cleaned.stderr_text}"
    )
    ws.write(".gitattributes", attrs)
    digest = commit_tracked_payload(ws, rel, data)
    back = ws.git(["checkout", "main"])
    assert back.returncode == 0, (
        f"git checkout main after orphan failed: {back.stderr_text}"
    )
    return branch, digest


@dataclass
class ThreeCommitLine:
    rel: str
    payload_a: bytes
    payload_m: bytes
    payload_b: bytes
    digest_a: str
    digest_m: str
    digest_b: str
    sha1: str
    sha2: str
    sha3: str


def _three_commit_line(
    ws,
    url: str,
    *,
    rel: str,
    payload_a: bytes,
    payload_m: bytes,
    payload_b: bytes,
) -> ThreeCommitLine:
    _porcelain_http(ws, url)
    digest_a = prepare_tracked_commit(ws, rel, payload_a)
    sha1 = head_oid(ws)
    digest_m = commit_tracked_payload(ws, rel, payload_m)
    sha2 = head_oid(ws)
    digest_b = commit_tracked_payload(ws, rel, payload_b)
    sha3 = head_oid(ws)
    return ThreeCommitLine(
        rel=rel,
        payload_a=payload_a,
        payload_m=payload_m,
        payload_b=payload_b,
        digest_a=digest_a,
        digest_m=digest_m,
        digest_b=digest_b,
        sha1=sha1,
        sha2=sha2,
        sha3=sha3,
    )


@dataclass
class TwoBranchLayout:
    rel_a: str
    rel_d: str
    payload_a: bytes
    payload_d: bytes
    digest_a: str
    digest_d: str
    branch: str
    sha_main: str
    sha_other: str


def _two_branches(
    ws,
    url: str,
    *,
    rel_a: str,
    rel_d: str,
    payload_a: bytes,
    payload_d: bytes,
) -> TwoBranchLayout:
    """HEAD/main has A; an orphan local branch has D. Neither is on origin."""
    _porcelain_http(ws, url)
    digest_a = prepare_tracked_commit(ws, rel_a, payload_a)
    sha_main = head_oid(ws)
    branch, digest_d = _orphan_commit(ws, rel_d, payload_d)
    other = _git_ok(ws, ["rev-parse", f"refs/heads/{branch}"])
    sha_other = other.stdout_text.strip()
    return TwoBranchLayout(
        rel_a=rel_a,
        rel_d=rel_d,
        payload_a=payload_a,
        payload_d=payload_d,
        digest_a=digest_a,
        digest_d=digest_d,
        branch=branch,
        sha_main=sha_main,
        sha_other=sha_other,
    )


def _history_only_on_other(
    ws,
    url: str,
    *,
    rel_a: str,
    rel_d: str,
    payload_a: bytes,
    payload_d: bytes,
) -> TwoBranchLayout:
    """D lives only in another local ref's history, not on any local tip."""
    layout = _two_branches(
        ws,
        url,
        rel_a=rel_a,
        rel_d=rel_d,
        payload_a=payload_a,
        payload_d=payload_d,
    )
    switched = ws.git(["checkout", layout.branch])
    assert switched.returncode == 0, switched.stderr_text
    dropped = ws.git(["rm", "--", layout.rel_d])
    assert dropped.returncode == 0, dropped.stderr_text
    _git_ok(ws, ["commit", "-m", "drop D from tip"])
    back = ws.git(["checkout", "main"])
    assert back.returncode == 0, back.stderr_text
    return layout


@dataclass
class HookLayout:
    line: ThreeCommitLine
    rel_d: str
    payload_d: bytes
    digest_d: str
    branch: str
    sha_d: str


def _hook_layout(
    ws,
    url: str,
    *,
    rel: str,
    payload_a: bytes,
    payload_m: bytes,
    payload_b: bytes,
    rel_d: str,
    payload_d: bytes,
) -> HookLayout:
    line = _three_commit_line(
        ws,
        url,
        rel=rel,
        payload_a=payload_a,
        payload_m=payload_m,
        payload_b=payload_b,
    )
    branch, digest_d = _orphan_commit(ws, rel_d, payload_d)
    other = _git_ok(ws, ["rev-parse", f"refs/heads/{branch}"])
    return HookLayout(
        line=line,
        rel_d=rel_d,
        payload_d=payload_d,
        digest_d=digest_d,
        branch=branch,
        sha_d=other.stdout_text.strip(),
    )


def _line_payloads():
    rel = _tracked_rel("line")
    payload_a = _payload(pad=11)
    payload_m = _payload(pad=29)
    payload_b = _payload(pad=53)
    return rel, payload_a, payload_m, payload_b


def _branch_payloads():
    rel_a = _tracked_rel("main")
    rel_d = _tracked_rel("other")
    payload_a = _payload(pad=13)
    payload_d = _payload(pad=31)
    return rel_a, rel_d, payload_a, payload_d


# ---------------------------------------------------------------------------
# A. Default push Git range; given refs; push-all still PUTs skipped objects
# ---------------------------------------------------------------------------


def test_default_push_uploads_only_objects_not_on_local_clone_of_remote():
    """Default push PUTs the tip and the middle commit, not the tracked tip."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_m, payload_b]
    ) as svc:
        with workspace() as ws:
            line = _three_commit_line(
                ws,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws, line.sha1)
            start = len(svc.records)
            result = ws.invoke_via_git(["push", "origin", "main"])
            print(
                f"default range exit={result.returncode} "
                f"sha1={line.sha1[:12]} sha3={line.sha3[:12]}"
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, line.payload_b)
            assert_put_of(recs, line.payload_m)
            assert_no_put_of(recs, line.payload_a)


def test_default_push_uploads_objects_for_the_given_ref_only():
    """Default push of one argv ref does not upload another local ref's object."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d]
    ) as svc:
        with workspace() as ws_main:
            layout = _two_branches(
                ws_main,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_main.invoke_via_git(["push", "origin", "main"])
            print(f"push main exit={result.returncode} HEAD=main")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_a)
            assert_no_put_of(recs, layout.payload_d)
        with workspace() as ws_other:
            layout = _two_branches(
                ws_other,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_other.invoke_via_git(
                ["push", "origin", layout.branch]
            )
            head = _git_ok(ws_other, ["symbolic-ref", "--short", "HEAD"])
            print(
                f"push other exit={result.returncode} "
                f"HEAD={head.stdout_text.strip()!r} branch={layout.branch!r}"
            )
            assert head.stdout_text.strip() == "main", (
                "HEAD must stay on main; only the argv ref changes"
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_d)
            assert_no_put_of(recs, layout.payload_a)


def test_default_push_two_given_refs_upload_both():
    """One push with two argv refs uploads both refs' pending objects."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d]
    ) as svc:
        with workspace() as ws_one:
            one = _two_branches(
                ws_one,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            only_main = ws_one.invoke_via_git(["push", "origin", "main"])
            require_success(only_main)
            recs_one = _records_since(svc, start)
            assert_put_of(recs_one, one.payload_a)
            assert_no_put_of(recs_one, one.payload_d)
        with workspace() as ws_both:
            both = _two_branches(
                ws_both,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_both.invoke_via_git(
                ["push", "origin", "main", both.branch]
            )
            print(f"two-ref push exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, both.payload_a)
            assert_put_of(recs, both.payload_d)


def test_push_all_still_uploads_objects_default_skips_as_already_on_remote_clone():
    """Live push-all PUTs an object the default Git range skips as already tracked."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_m, payload_b]
    ) as svc:
        with workspace() as ws_default:
            line = _three_commit_line(
                ws_default,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_default, line.sha1)
            start = len(svc.records)
            result = ws_default.invoke_via_git(["push", "origin", "main"])
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, line.payload_b)
            assert_put_of(recs, line.payload_m)
            assert_no_put_of(recs, line.payload_a)
            print("default skipped A on local clone of remote")
        with workspace() as ws_all:
            line = _three_commit_line(
                ws_all,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_all, line.sha1)
            start = len(svc.records)
            result = ws_all.invoke_via_git(
                ["push", "--all", "origin", "main"]
            )
            print(f"push-all exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, line.payload_a)
            assert_put_of(recs, line.payload_b)
            assert_put_of(recs, line.payload_m)


def test_second_default_push_of_same_commit_does_not_reupload():
    """When tracking already names the tip, a default push does not PUT again."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_m, payload_b]
    ) as svc:
        with workspace() as ws_pending:
            line = _three_commit_line(
                ws_pending,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_pending, line.sha1)
            start = len(svc.records)
            result = ws_pending.invoke_via_git(["push", "origin", "main"])
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, line.payload_b)
            assert_put_of(recs, line.payload_m)
        with workspace() as ws_aligned:
            line = _three_commit_line(
                ws_aligned,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_aligned, line.sha3)
            start = len(svc.records)
            result = ws_aligned.invoke_via_git(["push", "origin", "main"])
            print(f"aligned default exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_no_put_of(recs, line.payload_a)
            assert_no_put_of(recs, line.payload_m)
            assert_no_put_of(recs, line.payload_b)


def test_direct_binary_push_uploads_new_object():
    """Direct binary push of a pending object PUTs its original bytes."""
    payload = _payload(pad=15)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws:
            _porcelain_http(ws, svc.url)
            rel = _tracked_rel()
            prepare_tracked_commit(ws, rel, payload)
            result = ws.invoke(["push", "origin", "main"])
            print(f"direct push exit={result.returncode}")
            require_success(result)
            assert_put_of(svc.records, payload)


# ---------------------------------------------------------------------------
# B. Push-all reachable history; no refs = all local refs, not remote-tracking
# ---------------------------------------------------------------------------


def test_push_all_given_ref_uploads_reachable_history_unlike_default():
    """Push-all of a given ref PUTs history the default range skips at the tip."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_m, payload_b]
    ) as svc:
        with workspace() as ws_default:
            line = _three_commit_line(
                ws_default,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_default, line.sha3)
            start = len(svc.records)
            result = ws_default.invoke_via_git(["push", "origin", "main"])
            require_success(result)
            recs = _records_since(svc, start)
            assert_no_put_of(recs, line.payload_a)
            print("default at tip skipped history object A")
        with workspace() as ws_all:
            line = _three_commit_line(
                ws_all,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
            )
            _plant_tracking(ws_all, line.sha3)
            start = len(svc.records)
            result = ws_all.invoke_via_git(
                ["push", "--all", "origin", "main"]
            )
            print(f"push-all given-ref exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, line.payload_a)
            assert_put_of(recs, line.payload_b)


def test_push_all_without_refs_uploads_reachable_history_of_all_local_refs():
    """No-ref push-all PUTs another local ref's historical object, not just tips."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d]
    ) as svc:
        with workspace() as ws_given:
            layout = _history_only_on_other(
                ws_given,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_given.invoke_via_git(
                ["push", "--all", "origin", "main"]
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_a)
            assert_no_put_of(recs, layout.payload_d)
            print("push-all given main omitted other-ref history D")
        with workspace() as ws_all:
            layout = _history_only_on_other(
                ws_all,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_all.invoke_via_git(["push", "--all", "origin"])
            print(f"push-all no-refs exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_a)
            assert_put_of(recs, layout.payload_d)


def test_push_all_without_refs_omits_remote_tracking_only_object():
    """No-ref push-all is local refs' reachable set, not fetch-all remote-tracking."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    payload_c = _payload(pad=37)
    rel_c = _tracked_rel("remoteonly")
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d, payload_c]
    ) as svc:
        with workspace() as ws:
            layout = _history_only_on_other(
                ws,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            tmp = f"tmp_{token()}"
            created = ws.git(["checkout", "-b", tmp])
            assert created.returncode == 0, created.stderr_text
            commit_tracked_payload(ws, rel_c, payload_c)
            sha_c = head_oid(ws)
            _plant_tracking(ws, sha_c, name="other")
            back = ws.git(["checkout", "main"])
            assert back.returncode == 0, back.stderr_text
            deleted = ws.git(["branch", "-D", tmp])
            assert deleted.returncode == 0, deleted.stderr_text
            start = len(svc.records)
            result = ws.invoke_via_git(["push", "--all", "origin"])
            print(
                f"no-ref push-all exit={result.returncode} "
                f"tracking-only={sha_c[:12]}"
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_d)
            assert_put_of(recs, layout.payload_a)
            assert_no_put_of(recs, payload_c)


# ---------------------------------------------------------------------------
# C. Dry-run identifies pending objects and does not transfer
# ---------------------------------------------------------------------------


def _dry_run_contrast(kind: str) -> None:
    payload_p = _payload(pad=21)
    payload_q = _payload(pad=43)
    rel_p = _tracked_rel("p")
    rel_q = _tracked_rel("q")
    with conforming_batch_server(
        mode="upload", payloads=[payload_p, payload_q]
    ) as svc:
        with workspace() as ws_live:
            _porcelain_http(ws_live, svc.url)
            prepare_tracked_commit(ws_live, rel_p, payload_p)
            start = len(svc.records)
            live = ws_live.invoke_via_git(["push", "origin", "main"])
            require_success(live)
            recs = _records_since(svc, start)
            assert_put_of(recs, payload_p)
            print(f"{kind} live PUT P")
        with workspace() as ws:
            layout = _two_branches(
                ws,
                svc.url,
                rel_a=rel_p,
                rel_d=rel_q,
                payload_a=payload_p,
                payload_d=payload_q,
            )
            p_ref = f"p_{token()}"
            _git_ok(ws, ["branch", p_ref, "main"])
            extra = (
                p_ref,
                layout.branch,
                f"refs/heads/{p_ref}",
                f"refs/heads/{layout.branch}",
            )
            start = len(svc.records)
            dry_p_a = _invoke_dry_run(
                ws, kind, ref=p_ref, local_sha=layout.sha_main
            )
            dry_p_b = _invoke_dry_run(
                ws, kind, ref=p_ref, local_sha=layout.sha_main
            )
            dry_q = _invoke_dry_run(
                ws,
                kind,
                ref=layout.branch,
                local_sha=layout.sha_other,
            )
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload_p)
            assert_no_put_of(recs, payload_q)
            _plant_tracking(ws, layout.sha_main)
            _plant_tracking(ws, layout.sha_main, name=p_ref)
            dry_none = _invoke_dry_run(
                ws,
                kind,
                ref=p_ref,
                local_sha=layout.sha_main,
                remote_sha=layout.sha_main,
            )
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload_p)
            assert_no_put_of(recs, payload_q)
            rem_p_a = _dry_strip(
                ws, dry_p_a, payload_p, payload_q, extra=extra
            )
            rem_p_b = _dry_strip(
                ws, dry_p_b, payload_p, payload_q, extra=extra
            )
            rem_q = _dry_strip(
                ws, dry_q, payload_p, payload_q, extra=extra
            )
            rem_none = _dry_strip(
                ws, dry_none, payload_p, payload_q, extra=extra
            )
            print(
                f"{kind} dry remainders P={rem_p_a!r} {rem_p_b!r} "
                f"Q={rem_q!r} none={rem_none!r}"
            )
            assert_dry_run_remainder_stable_unlike(
                rem_p_a, rem_p_b, rem_q, rem_none
            )


def test_push_dry_run_identifies_pending_object_and_does_not_transfer():
    """Porcelain dry-run names the pending object and does not PUT it."""
    _dry_run_contrast("push")


def test_pre_push_dry_run_identifies_pending_object_and_does_not_transfer():
    """Pre-push dry-run names the pending object and does not PUT it."""
    _dry_run_contrast("pre-push")


# ---------------------------------------------------------------------------
# D. Object-id mode and stdin refs / oids
# ---------------------------------------------------------------------------


def test_object_id_mode_uploads_listed_oid_unlike_default_git_range():
    """Object-id mode PUTs a listed oid the default Git range would skip."""
    payload_e = _payload(pad=17)
    with conforming_batch_server(mode="upload", payloads=[payload_e]) as svc:
        with workspace() as ws_default:
            _porcelain_http(ws_default, svc.url)
            rel = _tracked_rel()
            prepare_tracked_commit(ws_default, rel, payload_e)
            _plant_tracking(ws_default, head_oid(ws_default))
            start = len(svc.records)
            result = ws_default.invoke_via_git(["push", "origin", "main"])
            require_success(result)
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload_e)
        with workspace() as ws_oid:
            _porcelain_http(ws_oid, svc.url)
            rel = _tracked_rel()
            digest = prepare_tracked_commit(ws_oid, rel, payload_e)
            _plant_tracking(ws_oid, head_oid(ws_oid))
            start = len(svc.records)
            result = ws_oid.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"object-id exit={result.returncode} oid={digest}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, payload_e)


def test_push_refs_from_stdin_select_listed_ref():
    """Non-empty stdin refs replace argv refs: each arm uploads only its ref."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d]
    ) as svc:
        with workspace() as ws_other:
            layout = _two_branches(
                ws_other,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_other.invoke_via_git(
                ["push", "--stdin", "origin"],
                stdin=f"{layout.branch}\n",
            )
            print(f"stdin other exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_d)
            assert_no_put_of(recs, layout.payload_a)
        with workspace() as ws_main:
            layout = _two_branches(
                ws_main,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws_main.invoke_via_git(
                ["push", "--stdin", "origin"],
                stdin="main\n",
            )
            print(f"stdin main exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_a)
            assert_no_put_of(recs, layout.payload_d)


def test_push_two_refs_from_stdin_upload_both():
    """One stdin invocation listing two refs PUTs both objects."""
    rel_a, rel_d, payload_a, payload_d = _branch_payloads()
    with conforming_batch_server(
        mode="upload", payloads=[payload_a, payload_d]
    ) as svc:
        with workspace() as ws:
            layout = _two_branches(
                ws,
                svc.url,
                rel_a=rel_a,
                rel_d=rel_d,
                payload_a=payload_a,
                payload_d=payload_d,
            )
            start = len(svc.records)
            result = ws.invoke_via_git(
                ["push", "--stdin", "origin"],
                stdin=f"main\n{layout.branch}\n",
            )
            print(f"stdin two refs exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, layout.payload_a)
            assert_put_of(recs, layout.payload_d)


def test_object_id_stdin_uploads_each_listed_oid():
    """Object-id stdin listing two oids PUTs both; listing one omits the other."""
    payload_e = _payload(pad=18)
    payload_f = _payload(pad=36)
    with conforming_batch_server(
        mode="upload", payloads=[payload_e, payload_f]
    ) as svc:
        with workspace() as ws_one:
            _porcelain_http(ws_one, svc.url)
            digest_e = prepare_tracked_commit(
                ws_one, _tracked_rel("e"), payload_e
            )
            commit_tracked_payload(ws_one, _tracked_rel("f"), payload_f)
            _plant_tracking(ws_one, head_oid(ws_one))
            start = len(svc.records)
            result = ws_one.invoke_via_git(
                ["push", "--object-id", "--stdin", "origin"],
                stdin=f"{digest_e}\n",
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, payload_e)
            assert_no_put_of(recs, payload_f)
        with workspace() as ws_two:
            _porcelain_http(ws_two, svc.url)
            digest_e = prepare_tracked_commit(
                ws_two, _tracked_rel("e"), payload_e
            )
            digest_f = commit_tracked_payload(
                ws_two, _tracked_rel("f"), payload_f
            )
            _plant_tracking(ws_two, head_oid(ws_two))
            start = len(svc.records)
            result = ws_two.invoke_via_git(
                ["push", "--object-id", "--stdin", "origin"],
                stdin=f"{digest_e}\n{digest_f}\n",
            )
            print(
                f"stdin two oids exit={result.returncode} "
                f"e={digest_e[:12]} f={digest_f[:12]}"
            )
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, payload_e)
            assert_put_of(recs, payload_f)


# ---------------------------------------------------------------------------
# E. Pre-push stdin ranges; two lines; delete uploads nothing
# ---------------------------------------------------------------------------


def test_pre_push_uploads_objects_required_by_stdin_commit_range():
    """Non-delete pre-push PUTs the stdin range, including a middle commit."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    rel_d = _tracked_rel("hookd")
    payload_d = _payload(pad=27)
    with conforming_batch_server(
        mode="upload",
        payloads=[payload_a, payload_m, payload_b, payload_d],
    ) as svc:
        with workspace() as ws_main:
            hook = _hook_layout(
                ws_main,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
                rel_d=rel_d,
                payload_d=payload_d,
            )
            start = len(svc.records)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=hook.line.sha3,
                remote_ref="refs/heads/main",
                remote_sha=hook.line.sha1,
            )
            result = ws_main.invoke_via_git(
                ["pre-push", "origin", _origin_url(ws_main)],
                stdin=stdin,
            )
            print(f"pre-push main range exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, hook.line.payload_b)
            assert_put_of(recs, hook.line.payload_m)
            assert_no_put_of(recs, hook.line.payload_a)
            assert_no_put_of(recs, hook.payload_d)
        with workspace() as ws_other:
            hook = _hook_layout(
                ws_other,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
                rel_d=rel_d,
                payload_d=payload_d,
            )
            start = len(svc.records)
            stdin = pre_push_stdin(
                local_ref=f"refs/heads/{hook.branch}",
                local_sha=hook.sha_d,
                remote_ref=f"refs/heads/{hook.branch}",
                remote_sha=git_zero_oid(),
            )
            result = ws_other.invoke_via_git(
                ["pre-push", "origin", _origin_url(ws_other)],
                stdin=stdin,
            )
            print(f"pre-push other range exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, hook.payload_d)
            assert_no_put_of(recs, hook.line.payload_b)
            assert_no_put_of(recs, hook.line.payload_m)


def test_pre_push_two_stdin_lines_upload_both_refs():
    """One pre-push reading two stdin lines PUTs both ranges' objects."""
    rel, payload_a, payload_m, payload_b = _line_payloads()
    rel_d = _tracked_rel("hookd")
    payload_d = _payload(pad=27)
    with conforming_batch_server(
        mode="upload",
        payloads=[payload_a, payload_m, payload_b, payload_d],
    ) as svc:
        with workspace() as ws:
            hook = _hook_layout(
                ws,
                svc.url,
                rel=rel,
                payload_a=payload_a,
                payload_m=payload_m,
                payload_b=payload_b,
                rel_d=rel_d,
                payload_d=payload_d,
            )
            start = len(svc.records)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=hook.line.sha3,
                remote_ref="refs/heads/main",
                remote_sha=hook.line.sha1,
            ) + pre_push_stdin(
                local_ref=f"refs/heads/{hook.branch}",
                local_sha=hook.sha_d,
                remote_ref=f"refs/heads/{hook.branch}",
                remote_sha=git_zero_oid(),
            )
            result = ws.invoke(
                ["pre-push", "origin", _origin_url(ws)],
                stdin=stdin,
            )
            print(f"pre-push two lines exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, hook.line.payload_b)
            assert_put_of(recs, hook.line.payload_m)
            assert_put_of(recs, hook.payload_d)


def test_pre_push_delete_update_does_not_upload():
    """A delete stdin line (zero local sha) does not PUT; non-delete does."""
    payload = _payload(pad=22)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_live:
            _porcelain_http(ws_live, svc.url)
            prepare_tracked_commit(ws_live, _tracked_rel(), payload)
            sha = head_oid(ws_live)
            start = len(svc.records)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=sha,
                remote_ref="refs/heads/main",
                remote_sha=git_zero_oid(),
            )
            live = ws_live.invoke_via_git(
                ["pre-push", "origin", _origin_url(ws_live)],
                stdin=stdin,
            )
            require_success(live)
            assert_put_of(_records_since(svc, start), payload)
        with workspace() as ws_del:
            _porcelain_http(ws_del, svc.url)
            prepare_tracked_commit(ws_del, _tracked_rel(), payload)
            sha = head_oid(ws_del)
            start = len(svc.records)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=git_zero_oid(),
                remote_ref="refs/heads/main",
                remote_sha=sha,
            )
            result = ws_del.invoke_via_git(
                ["pre-push", "origin", _origin_url(ws_del)],
                stdin=stdin,
            )
            print(f"pre-push delete exit={result.returncode}")
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload)


def test_git_push_delete_does_not_upload():
    """User-visible git push --delete does not PUT; a live non-delete push does."""
    payload = _payload(pad=24)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_live:
            bare = _bare_origin(ws_live, svc.url)
            install_local_keeping_process(ws_live)
            prepare_tracked_commit(ws_live, _tracked_rel(), payload)
            start = len(svc.records)
            live = ws_live.git(["push", "origin", "main"])
            print(f"git push live exit={live.returncode} bare={bare}")
            require_success(live)
            assert_put_of(_records_since(svc, start), payload)
        with workspace() as ws_del:
            _bare_origin(ws_del, svc.url)
            install_local_keeping_process(ws_del)
            prepare_tracked_commit(ws_del, _tracked_rel(), payload)
            planted = ws_del.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            start = len(svc.records)
            result = ws_del.git(["push", "origin", "--delete", "main"])
            print(f"git push --delete exit={result.returncode}")
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload)


def test_direct_binary_pre_push_uploads_for_non_delete():
    """Direct binary pre-push of a non-delete line PUTs the required object."""
    payload = _payload(pad=16)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws:
            _porcelain_http(ws, svc.url)
            prepare_tracked_commit(ws, _tracked_rel(), payload)
            sha = head_oid(ws)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=sha,
                remote_ref="refs/heads/main",
                remote_sha=git_zero_oid(),
            )
            result = ws.invoke(
                ["pre-push", "origin", _origin_url(ws)],
                stdin=stdin,
            )
            print(f"direct pre-push exit={result.returncode}")
            require_success(result)
            assert_put_of(svc.records, payload)


# ---------------------------------------------------------------------------
# F. skip-push: hook does nothing, git push still updates refs
# ---------------------------------------------------------------------------


def test_skip_push_makes_pre_push_do_nothing_while_git_push_proceeds():
    """Skip-push omits LFS PUT while git push still advances the bare ref."""
    payload = _payload(pad=20)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_live:
            bare = _bare_origin(ws_live, svc.url)
            install_local_keeping_process(ws_live)
            _git_ok(ws_live, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_live)
            planted = ws_live.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            require_ref_at(ws_live, "refs/heads/main", old, cwd=bare)
            prepare_tracked_commit(ws_live, _tracked_rel(), payload)
            new = head_oid(ws_live)
            start = len(svc.records)
            live = ws_live.git(["push", "origin", "main"])
            print(f"skip baseline git push exit={live.returncode}")
            require_success(live)
            assert_put_of(_records_since(svc, start), payload)
            require_ref_at(ws_live, "refs/heads/main", new, cwd=bare)
        with workspace() as ws_skip:
            bare = _bare_origin(ws_skip, svc.url)
            install_local_keeping_process(ws_skip)
            _git_ok(ws_skip, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_skip)
            planted = ws_skip.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            prepare_tracked_commit(ws_skip, _tracked_rel(), payload)
            new = head_oid(ws_skip)
            start = len(svc.records)
            result = ws_skip.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            print(f"skip-push git push exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_no_put_of(recs, payload)
            require_ref_at(ws_skip, "refs/heads/main", new, cwd=bare)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=new,
                remote_ref="refs/heads/main",
                remote_sha=old,
            )
            start = len(svc.records)
            hook = ws_skip.invoke_via_git(
                ["pre-push", "origin", str(bare)],
                stdin=stdin,
                env_updates=skip_push_environment(),
            )
            print(f"skip-push pre-push exit={hook.returncode}")
            assert hook.returncode == 0, (
                "skip-push pre-push must not fail as an upload failure "
                f"(exit {hook.returncode}): {hook.stderr_text}"
            )
            assert_no_put_of(_records_since(svc, start), payload)


# ---------------------------------------------------------------------------
# G. git push uploads before refs update; clone/pull restores bytes
# ---------------------------------------------------------------------------


def test_git_push_uploads_before_updating_git_refs():
    """A reachable git push PUTs then advances refs; an unreachable one does neither."""
    payload = _payload(pad=26)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_ok:
            bare = _bare_origin(ws_ok, svc.url)
            install_local_keeping_process(ws_ok)
            _git_ok(ws_ok, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_ok)
            planted = ws_ok.git(["push", "origin", "main"])
            require_success(planted)
            require_ref_at(ws_ok, "refs/heads/main", old, cwd=bare)
            prepare_tracked_commit(ws_ok, _tracked_rel(), payload)
            new = head_oid(ws_ok)
            start = len(svc.records)
            result = ws_ok.git(["push", "origin", "main"])
            print(f"reachable git push exit={result.returncode}")
            require_success(result)
            recs = _records_since(svc, start)
            assert_put_of(recs, payload)
            require_ref_at(ws_ok, "refs/heads/main", new, cwd=bare)
        with workspace() as ws_fail:
            port = reserve_loopback_port()
            dead = f"http://127.0.0.1:{port}/{token()}/info/lfs"
            bare = _bare_origin(ws_fail, dead)
            install_local_keeping_process(ws_fail)
            _git_ok(ws_fail, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_fail)
            planted = ws_fail.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            require_ref_at(ws_fail, "refs/heads/main", old, cwd=bare)
            prepare_tracked_commit(ws_fail, _tracked_rel(), payload)
            new = head_oid(ws_fail)
            result = ws_fail.git(["push", "origin", "main"])
            print(f"unreachable git push exit={result.returncode}")
            assert result.returncode != 0, (
                "git push to an unreachable LFS endpoint succeeded; "
                "refs would be indistinguishable from a successful upload"
            )
            require_ref_at(ws_fail, "refs/heads/main", old, cwd=bare)
            assert head_oid(ws_fail) == new


def test_successful_push_lets_clone_or_pull_restore_working_tree_bytes():
    """After a PUT, clone/pull restores payload bytes; without a PUT it does not."""
    payload = _payload(pad=28)
    rel = _tracked_rel("restore")
    with storing_batch_server() as svc:
        with workspace() as ws_ok:
            src, bare = _restore_push_source(ws_ok, svc.url, rel, payload)
            start = len(svc.records)
            pushed = ws_ok.git(["push", "origin", "main"], cwd=src)
            print(f"restore source push exit={pushed.returncode}")
            require_success(pushed)
            assert_put_of(_records_since(svc, start), payload)
            _install_global_filters(ws_ok)
            dst = f"dst_{token()}"
            cloned = ws_ok.invoke_via_git(["clone", str(bare), dst])
            print(
                f"restore clone exit={cloned.returncode} "
                f"stderr={cloned.stderr_text!r}"
            )
            require_success(cloned)
            require_working_tree_bytes(
                ws_ok, rel, payload, cwd=ws_ok.resolve(dst)
            )
    with storing_batch_server() as svc:
        with workspace() as ws_skip:
            src, bare = _restore_push_source(ws_skip, svc.url, rel, payload)
            start = len(svc.records)
            planted = ws_skip.git(
                ["push", "origin", "main"],
                cwd=src,
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            assert_no_put_of(_records_since(svc, start), payload)
            _install_global_filters(ws_skip)
            dst = f"dst_{token()}"
            cloned = ws_skip.invoke_via_git(["clone", str(bare), dst])
            print(f"no-PUT clone exit={cloned.returncode}")
            try:
                data = ws_skip.read_bytes(f"{dst}/{rel}")
            except FileNotFoundError:
                data = None
            assert data != payload, (
                "clone restored payload bytes even though the object "
                "was never PUT"
            )


# ---------------------------------------------------------------------------
# H. Required-upload failure aborts; unworkable endpoint; foreign locks
# ---------------------------------------------------------------------------


def test_pre_push_failure_aborts_git_push_and_leaves_refs_unmoved():
    """A reachable endpoint that cannot land the object fails pre-push and git push."""
    payload = _payload(pad=25)
    with conforming_batch_server(
        mode="upload+object_error", payloads=[payload]
    ) as bad:
        with workspace() as ws_bad:
            bare = _bare_origin(ws_bad, bad.url)
            install_local_keeping_process(ws_bad)
            _git_ok(ws_bad, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_bad)
            planted = ws_bad.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            require_ref_at(ws_bad, "refs/heads/main", old, cwd=bare)
            prepare_tracked_commit(ws_bad, _tracked_rel(), payload)
            new = head_oid(ws_bad)
            start = len(bad.records)
            git_push = ws_bad.git(["push", "origin", "main"])
            print(f"object_error git push exit={git_push.returncode}")
            assert git_push.returncode != 0, (
                "git push succeeded although the required object could not "
                "be stored"
            )
            assert_no_put_of(_records_since(bad, start), payload)
            require_ref_at(ws_bad, "refs/heads/main", old, cwd=bare)
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=new,
                remote_ref="refs/heads/main",
                remote_sha=old,
            )
            start = len(bad.records)
            hook = ws_bad.invoke_via_git(
                ["pre-push", "origin", str(bare)],
                stdin=stdin,
            )
            print(f"object_error pre-push exit={hook.returncode}")
            assert hook.returncode != 0, (
                "pre-push succeeded although the required object could not "
                "be stored"
            )
            assert_no_put_of(_records_since(bad, start), payload)
    with conforming_batch_server(mode="upload", payloads=[payload]) as good:
        with workspace() as ws_ok:
            bare = _bare_origin(ws_ok, good.url)
            install_local_keeping_process(ws_ok)
            _git_ok(ws_ok, ["commit", "--allow-empty", "-m", "seed"])
            planted = ws_ok.git(
                ["push", "origin", "main"],
                env_updates=skip_push_environment(),
            )
            require_success(planted)
            prepare_tracked_commit(ws_ok, _tracked_rel(), payload)
            new = head_oid(ws_ok)
            start = len(good.records)
            result = ws_ok.git(["push", "origin", "main"])
            print(f"upload-ok git push exit={result.returncode}")
            require_success(result)
            assert_put_of(_records_since(good, start), payload)
            require_ref_at(ws_ok, "refs/heads/main", new, cwd=bare)


def test_push_to_unworkable_endpoint_fails_visibly():
    """Porcelain push to an unreachable endpoint fails; a reachable one PUTs."""
    payload = _payload(pad=14)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_ok:
            _porcelain_http(ws_ok, svc.url)
            prepare_tracked_commit(ws_ok, _tracked_rel(), payload)
            start = len(svc.records)
            ok = ws_ok.invoke_via_git(["push", "origin", "main"])
            require_success(ok)
            assert_put_of(_records_since(svc, start), payload)
        with workspace() as ws_dead:
            ws_dead.init_repo()
            configure_unreachable_endpoint(ws_dead)
            disable_lock_verification(ws_dead)
            prepare_tracked_commit(ws_dead, _tracked_rel(), payload)
            dead = ws_dead.invoke_via_git(["push", "origin", "main"])
            print(f"unworkable push exit={dead.returncode}")
            assert_invalid_unlike_success(ok, dead)


def test_lock_verification_rejects_update_of_path_locked_by_others():
    """With verify on, a foreign lock on the updated path rejects; others do not."""
    payload = _payload(pad=33)
    rel = _tracked_rel("locked")
    unrelated = _tracked_rel("unrelated")
    with foreign_lock_on_path_server(rel, payloads=[payload]) as locked:
        with workspace() as ws_rej:
            ws_rej.init_repo()
            point_lfs_at(ws_rej, locked.url)
            enable_lock_verification(ws_rej)
            prepare_tracked_commit(ws_rej, rel, payload)
            start = len(locked.records)
            rejected = ws_rej.invoke_via_git(["push", "origin", "main"])
            print(f"foreign-lock reject exit={rejected.returncode}")
            assert rejected.returncode != 0, (
                "push succeeded while updating a path locked by others"
            )
            assert_no_put_of(_records_since(locked, start), payload)
    with foreign_lock_on_path_server(None, payloads=[payload]) as open_locks:
        with workspace() as ws_ok:
            ws_ok.init_repo()
            point_lfs_at(ws_ok, open_locks.url)
            enable_lock_verification(ws_ok)
            prepare_tracked_commit(ws_ok, rel, payload)
            start = len(open_locks.records)
            ok = ws_ok.invoke_via_git(["push", "origin", "main"])
            print(f"no-foreign-lock exit={ok.returncode}")
            require_success(ok)
            assert_put_of(_records_since(open_locks, start), payload)
    with foreign_lock_on_path_server(
        unrelated, payloads=[payload]
    ) as other_path:
        with workspace() as ws_other:
            ws_other.init_repo()
            point_lfs_at(ws_other, other_path.url)
            enable_lock_verification(ws_other)
            prepare_tracked_commit(ws_other, rel, payload)
            start = len(other_path.records)
            result = ws_other.invoke_via_git(["push", "origin", "main"])
            print(f"unrelated-path lock exit={result.returncode}")
            require_success(result)
            assert_put_of(_records_since(other_path, start), payload)


# ---------------------------------------------------------------------------
# I. Negative control
# ---------------------------------------------------------------------------


def test_push_and_pre_push_fail_when_binary_removed_from_path():
    """Removing the product from PATH fails push, pre-push, and hooked git push."""
    payload = _payload(pad=12)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_ok:
            _porcelain_http(ws_ok, svc.url)
            prepare_tracked_commit(ws_ok, _tracked_rel(), payload)
            start = len(svc.records)
            ok = ws_ok.invoke_via_git(["push", "origin", "main"])
            print(f"present push exit={ok.returncode}")
            require_success(ok)
            assert_put_of(_records_since(svc, start), payload)
        with workspace() as ws_miss:
            bare = _bare_origin(ws_miss, svc.url)
            install_local_keeping_process(ws_miss)
            prepare_tracked_commit(ws_miss, _tracked_rel(), payload)
            hidden = path_without_product_bin(ws_miss.env)
            env = {"PATH": hidden}
            push_f = ws_miss.invoke_via_git(
                ["push", "origin", "main"], env_updates=env
            )
            stdin = pre_push_stdin(
                local_ref="refs/heads/main",
                local_sha=head_oid(ws_miss),
                remote_ref="refs/heads/main",
                remote_sha=git_zero_oid(),
            )
            pre_f = ws_miss.invoke_via_git(
                ["pre-push", "origin", str(bare)],
                stdin=stdin,
                env_updates=env,
            )
            git_f = ws_miss.git(["push", "origin", "main"], env_updates=env)
            print(
                f"absent push={push_f.returncode} pre-push={pre_f.returncode} "
                f"git-push={git_f.returncode}"
            )
            for name, failed in (
                ("push", push_f),
                ("pre-push", pre_f),
                ("git push", git_f),
            ):
                assert failed.returncode != 0, (
                    f"{name} succeeded after the product binary was removed "
                    "from PATH"
                )
