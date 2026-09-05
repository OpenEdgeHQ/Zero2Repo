# feature: F15
"""Configuration surface and repository ``.lfsconfig`` acceptance tests.

PRD: FP-15. Oracles are dedicated endpoint indications, which loopback
host a transfer contacts, working-tree pointer versus original bytes,
whether a pre-push PUT happened, checkout success versus failure when a
download cannot, on/off in-progress reporting after shared completion
chunks are removed, and post-* read-only versus writable bits.
Message wording, Endpoint= labels, progress punctuation, boolean tokens
in output, and exit-code numbers are not pinned.
"""

from __future__ import annotations

import json

from _harness import token, workspace
from _helpers import (
    TwoRemoteLayout,
    add_git_remote,
    assert_adapter_name_advertised,
    assert_agent_was_launched,
    caller_visible,
    clean_bytes,
    commit_ordinary_blob,
    commit_tracked_payload,
    commit_tracked_payload_dated,
    configure_concurrent_transfers,
    configure_custom_transfer_agent,
    configure_default_remote,
    configure_fetch_exclude,
    configure_fetch_include,
    configure_force_progress,
    configure_http_timeouts,
    configure_lockable_readonly,
    configure_recentness,
    configure_skip_download_errors,
    configure_ssh_transfer_mode,
    configure_storage_root,
    configure_unreachable_endpoint,
    conforming_batch_server,
    contacts,
    dedicated_server_url,
    default_lfs_store_root,
    delayed_download_batch_server,
    derived_https_endpoint,
    disable_lock_verification,
    documented_falsey,
    documented_truthy_skip,
    enable_basic_transfers_only,
    enable_lock_verification,
    enable_tus_transfers,
    env_force_progress,
    env_lockable_readonly,
    env_report,
    env_skip_download_errors,
    env_skip_push,
    env_skip_smudge,
    head_oid,
    in_progress_on_remainder_off_empty,
    indication_names,
    init_bare_git_remote,
    install_credential_helper,
    install_json_path_agent,
    install_local_keeping_process,
    install_ssh_transfer_peer,
    install_two_remote_layout,
    locking_api_server,
    make_file_writable,
    named_transfer_batch_server,
    non_truthy_boolean_token,
    path_without_product_bin,
    point_lfs_at,
    pointer_from_clean,
    pre_push_stdin,
    prepare_tracked_commit,
    recording_api_server,
    remove_stored_object,
    require_advanced_advertised,
    require_authenticate_invocation,
    require_basic_only_or_omitted,
    require_batch_post,
    require_bound_prevents_overlap_unlike_unbounded,
    require_file_read_only,
    require_file_writable,
    require_git_config_set,
    require_invalid_unlike_success,
    require_lfsconfig_set,
    require_locking_verify_received,
    require_no_authenticate_invocation,
    require_no_http_exchanges,
    require_no_put_of,
    require_no_transfer_invocation,
    require_object_absent,
    require_object_bytes,
    require_put_of,
    require_ref_at,
    require_request_carries_basic,
    require_success,
    require_transfer_invocation,
    require_working_tree_bytes,
    require_working_tree_pointer,
    run_post_checkout,
    run_prune,
    runtime_http_url,
    set_lfs_endpoint,
    set_remote_tracking,
    sha256_hex,
    ssh_env_updates,
    ssh_style_remote,
    storing_batch_server,
    track_lockable,
    track_pattern,
    unlink_worktree_lfsconfig,
    write_pointer_placeholders_from_index,
)


def _payload(*, pad: int = 0) -> bytes:
    return (f"blob-{token()}\n" + ("x" * pad)).encode("utf-8")


def _rel(prefix: str = "payload") -> str:
    return f"{prefix}_{token()}.bin"


def _git_ok(ws, argv, **kwargs):
    result = ws.git(argv, **kwargs)
    assert result.returncode == 0, (
        f"git {argv!r} failed (exit {result.returncode}): {result.stderr_text}"
    )
    return result


def _checkout(ws, *rels: str, env_updates=None):
    return ws.git(
        ["checkout", "HEAD", "--", *rels],
        env_updates=env_updates,
    )


def _unlink_worktree(ws, *rels: str) -> None:
    for rel in rels:
        path = ws.resolve(rel)
        try:
            path.unlink()
        except FileNotFoundError:
            raise AssertionError(
                f"cannot unlink worktree {rel!r}; file is missing"
            ) from None
        except OSError as exc:
            raise AssertionError(f"cannot unlink worktree {rel!r}: {exc}") from exc


def _origin_dedicated(report: str, git_remote_url: str) -> str:
    return dedicated_server_url(
        report,
        remote_name="origin",
        git_remote_url=git_remote_url,
    )


def _require_names(observed: str, url: str, *, role: str) -> None:
    assert indication_names(observed, url), (
        f"{role} dedicated indication did not name {url!r}: {observed!r}"
    )


def _require_omits(observed: str, url: str, *, role: str) -> None:
    assert not indication_names(observed, url), (
        f"{role} dedicated indication unexpectedly named {url!r}: {observed!r}"
    )


def _require_contacted(records, url: str, *, role: str) -> None:
    hit = contacts(records, url_or_host=url)
    print(f"contact {role} url={url!r} hit={hit} n={len(records)}")
    assert hit, f"{role} endpoint was not contacted ({url!r})"


def _require_not_contacted(records, url: str, *, role: str) -> None:
    hit = contacts(records, url_or_host=url)
    print(f"contact {role} url={url!r} hit={hit} n={len(records)}")
    assert not hit, f"{role} endpoint was contacted unexpectedly ({url!r})"


def _records_since(svc, start: int):
    return svc.records[start:]


def _wipe_store(ws, *digests: str) -> None:
    store = default_lfs_store_root(ws)
    for digest in digests:
        remove_stored_object(ws, digest)
        require_object_absent(store, digest)


def _sha(ws, ref: str = "HEAD") -> str:
    result = ws.git(["rev-parse", "--verify", ref])
    assert result.returncode == 0, (
        f"git rev-parse --verify {ref!r} failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    sha = result.stdout_text.strip()
    assert sha, f"git rev-parse --verify {ref!r} produced no sha"
    return sha


def _plant_origin_at_head(ws) -> None:
    bare = init_bare_git_remote(ws, f"rmt_{token()}.git")
    add_git_remote(ws, "origin", str(bare))
    branch = ws.git(["rev-parse", "--abbrev-ref", "HEAD"])
    assert branch.returncode == 0, (
        "git rev-parse --abbrev-ref HEAD failed "
        f"(exit {branch.returncode}): {branch.stderr_text}"
    )
    name = branch.stdout_text.strip()
    assert name and name != "HEAD", f"not on a named branch: {name!r}"
    set_remote_tracking(ws, "origin", name, _sha(ws))


def _init_tracked(ws) -> None:
    ws.init_repo()
    install_local_keeping_process(ws)
    track_pattern(ws, "*.bin")


def _auth_json(url: str) -> str:
    return json.dumps({"href": url, "header": {}})


def _bind_named_agent(ws, name: str, path) -> None:
    configure_custom_transfer_agent(ws, name, path)
    require_git_config_set(
        ws, f"lfs.customtransfer.{name}.concurrent", "false", local=True
    )


def _setup_two_downloads(ws, svc, payloads: list[bytes]) -> list[str]:
    ws.init_repo()
    point_lfs_at(ws, svc.url)
    disable_lock_verification(ws)
    digests: list[str] = []
    for index, data in enumerate(payloads):
        rel = _rel()
        if index == 0:
            digests.append(prepare_tracked_commit(ws, rel, data))
        else:
            digests.append(commit_tracked_payload(ws, rel, data))
    _wipe_store(ws, *digests)
    return digests


def _setup_one_download(ws, svc, payload: bytes) -> str:
    ws.init_repo()
    point_lfs_at(ws, svc.url)
    disable_lock_verification(ws)
    digest = prepare_tracked_commit(ws, _rel(), payload)
    _wipe_store(ws, digest)
    return digest


def _setup_one_upload(ws, svc, payload: bytes) -> str:
    ws.init_repo()
    point_lfs_at(ws, svc.url)
    disable_lock_verification(ws)
    return prepare_tracked_commit(ws, _rel(), payload)


def _live_git_remote(base: str) -> str:
    return f"{base.rstrip('/')}/{token()}/repo.git"


def _progress_strip(
    ws,
    result,
    *,
    rel: str,
    payload: bytes,
    digest: str,
    urls: tuple[str, ...] = (),
    extra: tuple[str, ...] = (),
) -> list[str]:
    tokens = [
        rel,
        str(ws.resolve(rel)),
        digest,
        *urls,
        *extra,
    ]
    for arg in result.argv:
        text = str(arg)
        if "/" in text or text.startswith("http"):
            tokens.append(text)
    try:
        tokens.append(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise AssertionError(
            f"payload is not UTF-8; cannot strip it as a covariate: {exc}"
        ) from exc
    return [item for item in tokens if item]


def _fetch_missing(ws, digest: str, *, env_updates=None, timeout: float = 90.0):
    remove_stored_object(ws, digest)
    return ws.invoke_via_git(
        ["fetch"], env_updates=env_updates, timeout=timeout
    )


def _commit_lockable_and_control(ws):
    """Track one lockable glob, commit a match plus a non-lockable control."""
    install_ok = ws.invoke_via_git(["install", "--local"])
    require_success(install_ok)
    commit_ordinary_blob(ws, f"keep_{token()}.txt", f"{token()}\n")
    ext = token()
    track_lockable(ws, f"*.{ext}")
    rel = f"a_{token()}.{ext}"
    ctrl = f"n_{token()}.txt"
    ws.write(rel, _payload())
    ws.write(ctrl, f"ctrl-{token()}\n")
    _git_ok(ws, ["add", "--", rel, ctrl, ".gitattributes"])
    _git_ok(ws, ["commit", "-m", "lockable and control"])
    return rel, ctrl


def _reapply_via_file_checkout(ws, rel: str, *, env_updates=None):
    make_file_writable(ws.resolve(rel))
    result = _checkout(ws, rel, env_updates=env_updates)
    assert result.returncode == 0, (
        f"git checkout HEAD -- {rel!r} failed "
        f"(exit {result.returncode}): {result.stderr_text}"
    )
    return result


# ---------------------------------------------------------------------------
# A. .lfsconfig endpoint applies until Git config overrides; transfers follow
# ---------------------------------------------------------------------------


def test_lfsconfig_endpoint_names_dedicated_indication_and_is_contacted():
    """Worktree .lfsconfig LFS URL is the dedicated indication and is contacted."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_a, recs_a):
        with recording_api_server() as (url_g, recs_g):
            git_remote = _live_git_remote(url_g)
            derived = derived_https_endpoint(git_remote)
            with workspace() as ws:
                ws.init_repo()
                add_git_remote(ws, "origin", git_remote)
                disable_lock_verification(ws)
                require_lfsconfig_set(ws, "lfs.url", url_a)
                digest = prepare_tracked_commit(ws, rel, payload)
                direct = ws.invoke(["env"])
                print(
                    f"direct env exit={direct.returncode} "
                    f"len={len(direct.stdout_text)}"
                )
                require_success(direct)
                observed = _origin_dedicated(direct.stdout_text, git_remote)
                print(f"lfsconfig dedicated={observed!r} a={url_a!r}")
                _require_names(observed, url_a, role="lfsconfig")
                _require_omits(observed, derived, role="lfsconfig-derived")
                remove_stored_object(ws, digest)
                fetched = ws.invoke_via_git(["fetch"])
                print(f"fetch exit={fetched.returncode}")
                _require_contacted(recs_a, url_a, role="lfsconfig")
                _require_not_contacted(recs_g, url_g, role="derived-host")


def test_git_config_overrides_lfsconfig_endpoint_on_dedicated_indication_and_transfers():
    """Local VCS Orbulk URL wins over .lfsconfig for indication and contact."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_a, recs_a):
        with recording_api_server() as (url_b, recs_b):
            with recording_api_server() as (url_g, recs_g):
                git_remote = _live_git_remote(url_g)
                with workspace() as ws:
                    ws.init_repo()
                    add_git_remote(ws, "origin", git_remote)
                    disable_lock_verification(ws)
                    require_lfsconfig_set(ws, "lfs.url", url_a)
                    require_git_config_set(ws, "lfs.url", url_b, local=True)
                    digest = prepare_tracked_commit(ws, rel, payload)
                    report = env_report(ws)
                    observed = _origin_dedicated(report, git_remote)
                    print(
                        f"override dedicated={observed!r} a={url_a!r} b={url_b!r}"
                    )
                    _require_names(observed, url_b, role="git-config-override")
                    _require_omits(observed, url_a, role="git-config-override")
                    remove_stored_object(ws, digest)
                    fetched = ws.invoke_via_git(["fetch"])
                    print(f"override fetch exit={fetched.returncode}")
                    _require_contacted(recs_b, url_b, role="git-config-override")
                    _require_not_contacted(recs_a, url_a, role="lfsconfig-loser")
                    _require_not_contacted(recs_g, url_g, role="derived-host")


def test_git_config_overrides_lfsconfig_skip_download_errors():
    """Git config skip-download-errors falsey overrides a truthy .lfsconfig."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    falsey = documented_falsey()
    with workspace() as file_on:
        file_on.init_repo()
        digest = prepare_tracked_commit(file_on, rel, data)
        remove_stored_object(file_on, digest)
        configure_unreachable_endpoint(file_on)
        require_lfsconfig_set(file_on, "lfs.skipdownloaderrors", truthy)
        _unlink_worktree(file_on, rel)
        ok = _checkout(file_on, rel)
        print(f"lfsconfig skip-download-errors exit={ok.returncode}")
        require_success(ok)
        require_working_tree_pointer(
            file_on, rel, digest=digest, size=len(data)
        )
        body = file_on.read_bytes(rel)
        assert body != data
    with workspace() as overridden:
        overridden.init_repo()
        digest = prepare_tracked_commit(overridden, rel, data)
        remove_stored_object(overridden, digest)
        configure_unreachable_endpoint(overridden)
        require_lfsconfig_set(overridden, "lfs.skipdownloaderrors", truthy)
        configure_skip_download_errors(overridden, falsey)
        _unlink_worktree(overridden, rel)
        failed = _checkout(overridden, rel)
        print(f"git-config override skip-download-errors exit={failed.returncode}")
        assert failed.returncode != 0, (
            "Git config falsey skip-download-errors still succeeded "
            "like the .lfsconfig truthy arm"
        )
        require_invalid_unlike_success(ok, failed)


# ---------------------------------------------------------------------------
# B. Worktree, else index, else HEAD; bare reads HEAD only
# ---------------------------------------------------------------------------


def _seed_payload_then_lfsconfig_layers(
    ws,
    *,
    rel: str,
    payload: bytes,
    git_remote: str,
    url_h: str,
    url_i: str | None = None,
    url_w: str | None = None,
) -> str:
    """Commit a tracked payload, then layer .lfsconfig H / optional I / W."""
    ws.init_repo()
    add_git_remote(ws, "origin", git_remote)
    disable_lock_verification(ws)
    digest = prepare_tracked_commit(ws, rel, payload)
    require_lfsconfig_set(ws, "lfs.url", url_h)
    _git_ok(ws, ["add", "--", ".lfsconfig"])
    _git_ok(ws, ["commit", "-m", "head lfsconfig"])
    if url_i is not None:
        require_lfsconfig_set(ws, "lfs.url", url_i)
        _git_ok(ws, ["add", "--", ".lfsconfig"])
    if url_w is not None:
        require_lfsconfig_set(ws, "lfs.url", url_w)
    return digest


def test_lfsconfig_prefers_worktree_over_index_over_head():
    """When W, I, and H all exist, indication and transfers follow W."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_w, recs_w):
        with recording_api_server() as (url_i, recs_i):
            with recording_api_server() as (url_h, recs_h):
                with recording_api_server() as (url_g, recs_g):
                    git_remote = _live_git_remote(url_g)
                    with workspace() as ws:
                        digest = _seed_payload_then_lfsconfig_layers(
                            ws,
                            rel=rel,
                            payload=payload,
                            git_remote=git_remote,
                            url_h=url_h,
                            url_i=url_i,
                            url_w=url_w,
                        )
                        report = env_report(ws)
                        observed = _origin_dedicated(report, git_remote)
                        print(
                            f"worktree-win dedicated={observed!r} "
                            f"w={url_w!r} i={url_i!r} h={url_h!r}"
                        )
                        _require_names(observed, url_w, role="worktree")
                        _require_omits(observed, url_i, role="worktree")
                        _require_omits(observed, url_h, role="worktree")
                        remove_stored_object(ws, digest)
                        fetched = ws.invoke_via_git(["fetch"])
                        print(f"worktree-win fetch exit={fetched.returncode}")
                        _require_contacted(recs_w, url_w, role="worktree")
                        _require_not_contacted(recs_i, url_i, role="index-loser")
                        _require_not_contacted(recs_h, url_h, role="head-loser")
                        _require_not_contacted(
                            recs_g, url_g, role="derived-host"
                        )


def test_lfsconfig_reads_index_when_worktree_file_missing():
    """Missing worktree file: indication and transfers follow the index URL."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_i, recs_i):
        with recording_api_server() as (url_h, recs_h):
            with recording_api_server() as (url_g, recs_g):
                git_remote = _live_git_remote(url_g)
                with workspace() as ws:
                    digest = _seed_payload_then_lfsconfig_layers(
                        ws,
                        rel=rel,
                        payload=payload,
                        git_remote=git_remote,
                        url_h=url_h,
                        url_i=url_i,
                        url_w=url_i,
                    )
                    unlink_worktree_lfsconfig(ws)
                    report = env_report(ws)
                    observed = _origin_dedicated(report, git_remote)
                    print(f"index-win dedicated={observed!r} i={url_i!r}")
                    _require_names(observed, url_i, role="index")
                    _require_omits(observed, url_h, role="index")
                    remove_stored_object(ws, digest)
                    fetched = ws.invoke_via_git(["fetch"])
                    print(f"index-win fetch exit={fetched.returncode}")
                    _require_contacted(recs_i, url_i, role="index")
                    _require_not_contacted(recs_h, url_h, role="head-loser")
                    _require_not_contacted(recs_g, url_g, role="derived-host")


def test_lfsconfig_reads_head_when_worktree_and_index_missing():
    """No worktree file and no index path: indication and transfers follow HEAD."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_h, recs_h):
        with recording_api_server() as (url_g, recs_g):
            git_remote = _live_git_remote(url_g)
            with workspace() as ws:
                digest = _seed_payload_then_lfsconfig_layers(
                    ws,
                    rel=rel,
                    payload=payload,
                    git_remote=git_remote,
                    url_h=url_h,
                )
                unlink_worktree_lfsconfig(ws)
                _git_ok(ws, ["rm", "--cached", "--", ".lfsconfig"])
                report = env_report(ws)
                observed = _origin_dedicated(report, git_remote)
                print(f"head-win dedicated={observed!r} h={url_h!r}")
                _require_names(observed, url_h, role="head")
                _require_omits(
                    observed,
                    derived_https_endpoint(git_remote),
                    role="head",
                )
                remove_stored_object(ws, digest)
                fetched = ws.invoke_via_git(["fetch"])
                print(f"head-win fetch exit={fetched.returncode}")
                _require_contacted(recs_h, url_h, role="head")
                _require_not_contacted(recs_g, url_g, role="derived-host")


def test_bare_repo_lfsconfig_reads_head_only_not_decoy_file():
    """A bare repository reads HEAD .lfsconfig, not a decoy file in that directory."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_h, recs_h):
        with recording_api_server() as (url_w, recs_w):
            with recording_api_server() as (url_g, recs_g):
                git_remote = _live_git_remote(url_g)
                with workspace() as ws:
                    digest = _seed_payload_then_lfsconfig_layers(
                        ws,
                        rel=rel,
                        payload=payload,
                        git_remote=git_remote,
                        url_h=url_h,
                    )
                    bare_rel = f"bare_{token()}"
                    cloned = ws.git(["clone", "--bare", ".", bare_rel])
                    assert cloned.returncode == 0, (
                        "git clone --bare failed "
                        f"(exit {cloned.returncode}): {cloned.stderr_text}"
                    )
                    bare_path = ws.resolve(bare_rel)
                    set_url = ws.git(
                        ["remote", "set-url", "origin", git_remote],
                        cwd=bare_path,
                    )
                    assert set_url.returncode == 0, (
                        "git remote set-url on bare failed "
                        f"(exit {set_url.returncode}): {set_url.stderr_text}"
                    )
                    decoy = bare_path / ".lfsconfig"
                    written = ws.git_config_set(
                        "lfs.url",
                        url_w,
                        file=str(decoy),
                        cwd=bare_path,
                    )
                    assert written.returncode == 0, (
                        "writing decoy .lfsconfig failed "
                        f"(exit {written.returncode}): {written.stderr_text}"
                    )
                    env_run = ws.invoke_via_git(["env"], cwd=bare_path)
                    print(f"bare env exit={env_run.returncode}")
                    require_success(env_run)
                    observed = _origin_dedicated(env_run.stdout_text, git_remote)
                    print(
                        f"bare dedicated={observed!r} h={url_h!r} decoy={url_w!r}"
                    )
                    _require_names(observed, url_h, role="bare-head")
                    _require_omits(observed, url_w, role="bare-decoy")
                    fetched = ws.invoke_via_git(["fetch"], cwd=bare_path)
                    print(f"bare fetch exit={fetched.returncode}")
                    _require_contacted(recs_h, url_h, role="bare-head")
                    _require_not_contacted(recs_w, url_w, role="bare-decoy")
                    _require_not_contacted(recs_g, url_g, role="derived-host")
                    print(f"bare digest={digest}")


# ---------------------------------------------------------------------------
# C. Allowlisted .lfsconfig keys take effect; others are ignored
# ---------------------------------------------------------------------------


def test_lfsconfig_per_remote_url_changes_only_that_remote_indication_and_is_contacted():
    """A per-remote .lfsconfig LFS URL changes that remote's indication and contact."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_s, recs_s):
        with recording_api_server() as (url_sib_git, recs_sib_git):
            sibling_name = f"sib_{token()}"
            sibling_git = _live_git_remote(url_sib_git)
            layout = TwoRemoteLayout(
                origin_url=runtime_http_url("alpha"),
                sibling_name=sibling_name,
                sibling_url=sibling_git,
            )
            with workspace() as ws:
                install_two_remote_layout(ws, layout)
                disable_lock_verification(ws)
                require_lfsconfig_set(
                    ws, f"remote.{layout.sibling_name}.lfsurl", url_s
                )
                digest = prepare_tracked_commit(ws, rel, payload)
                report = env_report(ws)
                sibling = dedicated_server_url(
                    report,
                    remote_name=layout.sibling_name,
                    git_remote_url=layout.sibling_url,
                    other_remote_name="origin",
                )
                origin = dedicated_server_url(
                    report,
                    remote_name="origin",
                    git_remote_url=layout.origin_url,
                    other_remote_name=layout.sibling_name,
                )
                print(
                    f"per-remote sibling={sibling!r} origin={origin!r} s={url_s!r}"
                )
                _require_names(sibling, url_s, role="per-remote-sibling")
                _require_omits(origin, url_s, role="per-remote-origin")
                remove_stored_object(ws, digest)
                fetched = ws.invoke_via_git(["fetch", layout.sibling_name])
                print(f"per-remote fetch exit={fetched.returncode}")
                _require_contacted(recs_s, url_s, role="per-remote-sibling")
                _require_not_contacted(
                    recs_sib_git, url_sib_git, role="sibling-derived"
                )


def test_lfsconfig_push_url_contacts_upload_endpoint_without_replacing_download_indication():
    """``.lfsconfig`` push URL splits upload contact from the download indication."""
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (url_a, recs_a):
        with recording_api_server() as (url_p, recs_p):
            git_remote = f"https://{token()}.origin.example.test/{token()}/repo.git"
            with workspace() as ws:
                ws.init_repo()
                add_git_remote(ws, "origin", git_remote)
                disable_lock_verification(ws)
                require_lfsconfig_set(ws, "lfs.url", url_a)
                require_lfsconfig_set(ws, "lfs.pushurl", url_p)
                digest = prepare_tracked_commit(ws, rel, payload)
                report = env_report(ws)
                observed = _origin_dedicated(report, git_remote)
                print(
                    f"pushurl dedicated={observed!r} a={url_a!r} p={url_p!r}"
                )
                _require_names(observed, url_a, role="pushurl-download")
                _require_omits(observed, url_p, role="pushurl-download")
                pushed = ws.invoke_via_git(
                    ["push", "--object-id", "origin", digest]
                )
                print(f"pushurl push exit={pushed.returncode}")
                _require_contacted(recs_p, url_p, role="pushurl-upload")
                download_before = len(recs_a)
                remove_stored_object(ws, digest)
                fetched = ws.invoke_via_git(["fetch"])
                print(f"pushurl fetch exit={fetched.returncode}")
                assert len(recs_a) > download_before, (
                    "download path did not contact the download endpoint"
                )
                _require_contacted(recs_a, url_a, role="pushurl-download")


def test_lfsconfig_skip_download_errors_allows_checkout_with_pointer():
    """Allowlisted skip-download-errors in ``.lfsconfig`` leaves a pointer."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    with workspace() as baseline:
        baseline.init_repo()
        digest = prepare_tracked_commit(baseline, rel, data)
        remove_stored_object(baseline, digest)
        configure_unreachable_endpoint(baseline)
        _unlink_worktree(baseline, rel)
        failed = _checkout(baseline, rel)
        print(f"no-file skip-download-errors exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        skipped.init_repo()
        digest = prepare_tracked_commit(skipped, rel, data)
        remove_stored_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        require_lfsconfig_set(skipped, "lfs.skipdownloaderrors", truthy)
        _unlink_worktree(skipped, rel)
        ok = _checkout(skipped, rel)
        print(f"lfsconfig skip-download-errors exit={ok.returncode}")
        require_success(ok)
        require_working_tree_pointer(
            skipped, rel, digest=digest, size=len(data)
        )
        assert skipped.read_bytes(rel) != data
        require_invalid_unlike_success(ok, failed)


def test_disallowed_lfsconfig_lockable_key_is_ignored_unlike_git_config():
    """``.lfsconfig`` lockable read-only cannot disable; Git config can."""
    falsey = documented_falsey()
    with workspace() as file_arm:
        file_arm.init_repo()
        rel, ctrl = _commit_lockable_and_control(file_arm)
        require_lfsconfig_set(file_arm, "lfs.setlockablereadonly", falsey)
        _reapply_via_file_checkout(file_arm, rel)
        print("lfsconfig lockable falsey still read-only")
        require_file_read_only(file_arm.resolve(rel))
        require_file_writable(file_arm.resolve(ctrl))
    with workspace() as git_arm:
        git_arm.init_repo()
        rel, ctrl = _commit_lockable_and_control(git_arm)
        configure_lockable_readonly(git_arm, falsey)
        _reapply_via_file_checkout(git_arm, rel)
        print("git-config lockable falsey is writable")
        require_file_writable(git_arm.resolve(rel))
        require_file_writable(git_arm.resolve(ctrl))


def test_disallowed_lfsconfig_force_progress_is_ignored():
    """Progress-forcing in ``.lfsconfig`` does not produce in-progress reporting."""
    payload = _payload()
    rel = _rel()
    truthy = documented_truthy_skip()
    extra = (
        "GIT_ORBULK_FORCE_PROGRESS",
        "lfs.forceprogress",
        truthy,
        ".lfsconfig",
    )
    with conforming_batch_server(
        mode="overlap_gate,download", payloads=[payload]
    ) as svc:
        with workspace() as git_on:
            git_on.init_repo()
            point_lfs_at(git_on, svc.url)
            disable_lock_verification(git_on)
            digest = prepare_tracked_commit(git_on, rel, payload)
            configure_force_progress(git_on, truthy)
            on_run = _fetch_missing(git_on, digest)
            print(f"git-config force-progress fetch exit={on_run.returncode}")
            require_success(on_run)
            require_object_bytes(
                default_lfs_store_root(git_on), digest, payload
            )
        with workspace() as file_arm:
            file_arm.init_repo()
            point_lfs_at(file_arm, svc.url)
            disable_lock_verification(file_arm)
            digest = prepare_tracked_commit(file_arm, rel, payload)
            require_lfsconfig_set(file_arm, "lfs.forceprogress", truthy)
            file_run = _fetch_missing(file_arm, digest)
            print(f"lfsconfig force-progress fetch exit={file_run.returncode}")
            require_success(file_run)
            require_object_bytes(
                default_lfs_store_root(file_arm), digest, payload
            )
        unknown = f"lfs.unk{token()}"
        with workspace() as warn_ctrl:
            warn_ctrl.init_repo()
            point_lfs_at(warn_ctrl, svc.url)
            disable_lock_verification(warn_ctrl)
            digest = prepare_tracked_commit(warn_ctrl, rel, payload)
            require_lfsconfig_set(warn_ctrl, unknown, f"val_{token()}")
            ctrl_run = _fetch_missing(warn_ctrl, digest)
            print(f"lfsconfig unrelated-ignore fetch exit={ctrl_run.returncode}")
            require_success(ctrl_run)
            require_object_bytes(
                default_lfs_store_root(warn_ctrl), digest, payload
            )
        extra = extra + (unknown,)
        strip = _progress_strip(
            git_on,
            on_run,
            rel=rel,
            payload=payload,
            digest=sha256_hex(payload),
            urls=(svc.url,),
            extra=extra,
        )
        strip.extend(
            _progress_strip(
                file_arm,
                file_run,
                rel=rel,
                payload=payload,
                digest=sha256_hex(payload),
                urls=(svc.url,),
                extra=extra,
            )
        )
        strip.extend(
            _progress_strip(
                warn_ctrl,
                ctrl_run,
                rel=rel,
                payload=payload,
                digest=sha256_hex(payload),
                urls=(svc.url,),
                extra=extra,
            )
        )
        leftover = in_progress_on_remainder_off_empty(
            on_run, file_run, strip=strip, ignore=(ctrl_run,)
        )
        print(f"ignored lfsconfig force-progress leftover={leftover!r}")


def test_unknown_lfsconfig_key_does_not_crash_env():
    """An unrecognized ``.lfsconfig`` key leaves env successful."""
    unknown = f"lfs.unk{token()}"
    value = f"val_{token()}"
    git_remote = f"https://{token()}.origin.example.test/{token()}/repo.git"
    with workspace() as ws:
        ws.init_repo()
        add_git_remote(ws, "origin", git_remote)
        require_lfsconfig_set(ws, unknown, value)
        result = ws.invoke_via_git(["env"])
        print(
            f"unknown-key env exit={result.returncode} key={unknown!r}"
        )
        require_success(result)
        assert result.stdout_text.strip(), (
            "env succeeded with an unknown .lfsconfig key but printed "
            "no configuration report"
        )


# ---------------------------------------------------------------------------
# D. skip-smudge environment on git checkout / filter
# ---------------------------------------------------------------------------


def test_skip_smudge_env_truthy_leaves_pointer_on_git_checkout():
    """Truthy skip-smudge leaves pointer text; unset materializes bytes."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    with workspace() as baseline:
        baseline.init_repo()
        digest = prepare_tracked_commit(baseline, rel, data)
        _unlink_worktree(baseline, rel)
        ok = _checkout(baseline, rel)
        print(f"skip-smudge unset checkout exit={ok.returncode}")
        require_success(ok)
        require_working_tree_bytes(baseline, rel, data)
    with workspace() as skipped:
        skipped.init_repo()
        digest = prepare_tracked_commit(skipped, rel, data)
        _unlink_worktree(skipped, rel)
        result = _checkout(skipped, rel, env_updates=env_skip_smudge(truthy))
        print(f"skip-smudge truthy checkout exit={result.returncode}")
        require_success(result)
        body = require_working_tree_pointer(
            skipped, rel, digest=digest, size=len(data)
        )
        assert body != data


def test_skip_smudge_env_falsey_and_non_truthy_still_materialize():
    """Falsey and non-truthy skip-smudge still materialize; they are not a skip."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    falsey = documented_falsey()
    junk = non_truthy_boolean_token()
    with workspace() as skipped:
        skipped.init_repo()
        digest = prepare_tracked_commit(skipped, rel, data)
        _unlink_worktree(skipped, rel)
        on = _checkout(skipped, rel, env_updates=env_skip_smudge(truthy))
        print(f"skip-smudge truthy live arm exit={on.returncode}")
        require_success(on)
        pointer = require_working_tree_pointer(
            skipped, rel, digest=digest, size=len(data)
        )
        assert pointer != data
    with workspace() as off:
        off.init_repo()
        digest = prepare_tracked_commit(off, rel, data)
        _unlink_worktree(off, rel)
        result = _checkout(off, rel, env_updates=env_skip_smudge(falsey))
        print(f"skip-smudge falsey exit={result.returncode}")
        require_success(result)
        require_working_tree_bytes(off, rel, data)
    with workspace() as junk_ws:
        junk_ws.init_repo()
        digest = prepare_tracked_commit(junk_ws, rel, data)
        _unlink_worktree(junk_ws, rel)
        result = _checkout(junk_ws, rel, env_updates=env_skip_smudge(junk))
        print(
            f"skip-smudge non-truthy exit={result.returncode} token={junk!r}"
        )
        require_success(result)
        require_working_tree_bytes(junk_ws, rel, data)


# ---------------------------------------------------------------------------
# E. skip-push environment on pre-push / git push
# ---------------------------------------------------------------------------


def _bare_push_layout(ws, url: str):
    ws.init_repo()
    bare = init_bare_git_remote(ws, f"bare_{token()}")
    add_git_remote(ws, "origin", str(bare))
    set_lfs_endpoint(ws, url)
    disable_lock_verification(ws)
    return bare


def test_skip_push_env_truthy_skips_pre_push_upload_while_git_push_proceeds():
    """Truthy skip-push omits the PUT while git push still advances the ref."""
    payload = _payload(pad=20)
    truthy = documented_truthy_skip()
    skip = env_skip_push(truthy)
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_live:
            bare = _bare_push_layout(ws_live, svc.url)
            install_ok = ws_live.invoke_via_git(["install", "--local"])
            require_success(install_ok)
            _git_ok(ws_live, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_live)
            planted = ws_live.git(["push", "origin", "main"], env_updates=skip)
            require_success(planted)
            require_ref_at(ws_live, "refs/heads/main", old, cwd=bare)
            prepare_tracked_commit(ws_live, _rel(), payload)
            new = head_oid(ws_live)
            start = len(svc.records)
            live = ws_live.git(["push", "origin", "main"])
            print(f"skip-push baseline git push exit={live.returncode}")
            require_success(live)
            require_put_of(svc.records[start:], payload)
            require_ref_at(ws_live, "refs/heads/main", new, cwd=bare)
        with workspace() as ws_skip:
            bare = _bare_push_layout(ws_skip, svc.url)
            install_ok = ws_skip.invoke_via_git(["install", "--local"])
            require_success(install_ok)
            _git_ok(ws_skip, ["commit", "--allow-empty", "-m", "seed"])
            old = head_oid(ws_skip)
            planted = ws_skip.git(["push", "origin", "main"], env_updates=skip)
            require_success(planted)
            prepare_tracked_commit(ws_skip, _rel(), payload)
            new = head_oid(ws_skip)
            start = len(svc.records)
            result = ws_skip.git(
                ["push", "origin", "main"], env_updates=skip
            )
            print(f"skip-push truthy git push exit={result.returncode}")
            require_success(result)
            require_no_put_of(svc.records[start:], payload)
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
                env_updates=skip,
            )
            print(f"skip-push pre-push exit={hook.returncode}")
            assert hook.returncode == 0, (
                "skip-push pre-push must not fail as an upload failure "
                f"(exit {hook.returncode}): {hook.stderr_text}"
            )
            require_no_put_of(svc.records[start:], payload)


def test_skip_push_env_non_truthy_still_uploads():
    """A non-truthy skip-push token still uploads; it is not a skip."""
    payload = _payload(pad=12)
    truthy = documented_truthy_skip()
    skip = env_skip_push(truthy)
    junk = non_truthy_boolean_token()
    with conforming_batch_server(mode="upload", payloads=[payload]) as svc:
        with workspace() as ws_skip:
            bare = _bare_push_layout(ws_skip, svc.url)
            install_ok = ws_skip.invoke_via_git(["install", "--local"])
            require_success(install_ok)
            _git_ok(ws_skip, ["commit", "--allow-empty", "-m", "seed"])
            planted = ws_skip.git(["push", "origin", "main"], env_updates=skip)
            require_success(planted)
            prepare_tracked_commit(ws_skip, _rel(), payload)
            new = head_oid(ws_skip)
            start = len(svc.records)
            skipped = ws_skip.git(
                ["push", "origin", "main"], env_updates=skip
            )
            print(f"skip-push truthy live arm exit={skipped.returncode}")
            require_success(skipped)
            require_no_put_of(svc.records[start:], payload)
            require_ref_at(ws_skip, "refs/heads/main", new, cwd=bare)
        with workspace() as ws:
            bare = _bare_push_layout(ws, svc.url)
            install_ok = ws.invoke_via_git(["install", "--local"])
            require_success(install_ok)
            _git_ok(ws, ["commit", "--allow-empty", "-m", "seed"])
            planted = ws.git(["push", "origin", "main"], env_updates=skip)
            require_success(planted)
            prepare_tracked_commit(ws, _rel(), payload)
            new = head_oid(ws)
            start = len(svc.records)
            result = ws.git(
                ["push", "origin", "main"],
                env_updates=env_skip_push(junk),
            )
            print(
                f"skip-push non-truthy exit={result.returncode} token={junk!r}"
            )
            require_success(result)
            require_put_of(svc.records[start:], payload)
            require_ref_at(ws, "refs/heads/main", new, cwd=bare)


# ---------------------------------------------------------------------------
# F. skip-download-errors environment
# ---------------------------------------------------------------------------


def test_skip_download_errors_env_truthy_allows_checkout_with_pointer():
    """Truthy skip-download-errors lets checkout succeed with a pointer."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    with workspace() as baseline:
        baseline.init_repo()
        digest = prepare_tracked_commit(baseline, rel, data)
        remove_stored_object(baseline, digest)
        configure_unreachable_endpoint(baseline)
        _unlink_worktree(baseline, rel)
        failed = _checkout(baseline, rel)
        print(f"skip-download-errors unset exit={failed.returncode}")
        assert failed.returncode != 0
    with workspace() as skipped:
        skipped.init_repo()
        digest = prepare_tracked_commit(skipped, rel, data)
        remove_stored_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(
            skipped, rel, env_updates=env_skip_download_errors(truthy)
        )
        print(f"skip-download-errors truthy exit={ok.returncode}")
        require_success(ok)
        require_working_tree_pointer(
            skipped, rel, digest=digest, size=len(data)
        )
        assert skipped.read_bytes(rel) != data
        require_invalid_unlike_success(ok, failed)


def test_skip_download_errors_env_non_truthy_still_fails_when_download_cannot():
    """Non-truthy skip-download-errors does not skip a failed download."""
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    junk = non_truthy_boolean_token()
    with workspace() as skipped:
        skipped.init_repo()
        digest = prepare_tracked_commit(skipped, rel, data)
        remove_stored_object(skipped, digest)
        configure_unreachable_endpoint(skipped)
        _unlink_worktree(skipped, rel)
        ok = _checkout(
            skipped, rel, env_updates=env_skip_download_errors(truthy)
        )
        print(f"skip-download-errors truthy live arm exit={ok.returncode}")
        require_success(ok)
        require_working_tree_pointer(
            skipped, rel, digest=digest, size=len(data)
        )
        assert skipped.read_bytes(rel) != data
    with workspace() as ws:
        ws.init_repo()
        digest = prepare_tracked_commit(ws, rel, data)
        remove_stored_object(ws, digest)
        configure_unreachable_endpoint(ws)
        _unlink_worktree(ws, rel)
        failed = _checkout(ws, rel, env_updates=env_skip_download_errors(junk))
        print(
            f"skip-download-errors non-truthy exit={failed.returncode} "
            f"token={junk!r}"
        )
        assert failed.returncode != 0, (
            "non-truthy skip-download-errors succeeded with a missing object"
        )
        require_invalid_unlike_success(ok, failed)


def test_skip_download_errors_env_still_materializes_when_object_is_local():
    """Truthy skip-download-errors leaves pointer text when download cannot.

    Local expansion when the object is already present is not this flag's
    duty. Line 443 only requires a checkout that cannot download to succeed
    with leftover pointer text rather than failing the whole operation.
    An implementation that leaves pointers whenever the flag is set has
    not broken that written promise.
    """
    ext = token()
    rel = f"payload_{token()}.{ext}"
    data = _payload()
    truthy = documented_truthy_skip()
    with workspace() as cannot:
        cannot.init_repo()
        digest = prepare_tracked_commit(cannot, rel, data)
        remove_stored_object(cannot, digest)
        configure_unreachable_endpoint(cannot)
        _unlink_worktree(cannot, rel)
        ok = _checkout(
            cannot, rel, env_updates=env_skip_download_errors(truthy)
        )
        print(f"skip-download-errors cannot-download exit={ok.returncode}")
        require_success(ok)
        require_working_tree_pointer(
            cannot, rel, digest=digest, size=len(data)
        )
        assert cannot.read_bytes(rel) != data


# ---------------------------------------------------------------------------
# G. Progress-forcing: in-progress reporting when stdout is not a terminal
# ---------------------------------------------------------------------------


def _progress_fetch_workspace(ws, svc, rel: str, payload: bytes, **kwargs):
    ws.init_repo()
    point_lfs_at(ws, svc.url)
    disable_lock_verification(ws)
    digest = prepare_tracked_commit(ws, rel, payload)
    result = _fetch_missing(ws, digest, **kwargs)
    print(f"progress fetch exit={result.returncode} visible_len={len(caller_visible(result))}")
    require_success(result)
    require_object_bytes(default_lfs_store_root(ws), digest, payload)
    return result, digest


def test_force_progress_env_adds_in_progress_reporting_when_stdout_not_a_terminal():
    """Environment progress-forcing adds in-progress reporting off-terminal."""
    payload = _payload()
    rel = _rel()
    truthy = documented_truthy_skip()
    extra = ("GIT_ORBULK_FORCE_PROGRESS", "lfs.forceprogress", truthy)
    with conforming_batch_server(
        mode="overlap_gate,download", payloads=[payload]
    ) as svc:
        with workspace() as on_ws:
            on_run, digest = _progress_fetch_workspace(
                on_ws,
                svc,
                rel,
                payload,
                env_updates=env_force_progress(truthy),
            )
        with workspace() as off_ws:
            off_run, _digest = _progress_fetch_workspace(
                off_ws, svc, rel, payload
            )
        strip = _progress_strip(
            on_ws,
            on_run,
            rel=rel,
            payload=payload,
            digest=digest,
            urls=(svc.url,),
            extra=extra,
        )
        strip.extend(
            _progress_strip(
                off_ws,
                off_run,
                rel=rel,
                payload=payload,
                digest=digest,
                urls=(svc.url,),
                extra=extra,
            )
        )
        leftover = in_progress_on_remainder_off_empty(
            on_run, off_run, strip=strip
        )
        print(f"env force-progress leftover={leftover!r}")


def test_force_progress_git_config_same_in_progress_contrast():
    """Git config progress-forcing produces the same on/off in-progress contrast."""
    payload = _payload()
    rel = _rel()
    truthy = documented_truthy_skip()
    extra = ("GIT_ORBULK_FORCE_PROGRESS", "lfs.forceprogress", truthy)
    with conforming_batch_server(
        mode="overlap_gate,download", payloads=[payload]
    ) as svc:
        with workspace() as on_ws:
            on_ws.init_repo()
            point_lfs_at(on_ws, svc.url)
            disable_lock_verification(on_ws)
            digest = prepare_tracked_commit(on_ws, rel, payload)
            configure_force_progress(on_ws, truthy)
            on_run = _fetch_missing(on_ws, digest)
            print(f"git-config force-progress on exit={on_run.returncode}")
            require_success(on_run)
            require_object_bytes(default_lfs_store_root(on_ws), digest, payload)
        with workspace() as off_ws:
            off_run, _digest = _progress_fetch_workspace(
                off_ws, svc, rel, payload
            )
        strip = _progress_strip(
            on_ws,
            on_run,
            rel=rel,
            payload=payload,
            digest=digest,
            urls=(svc.url,),
            extra=extra,
        )
        strip.extend(
            _progress_strip(
                off_ws,
                off_run,
                rel=rel,
                payload=payload,
                digest=digest,
                urls=(svc.url,),
                extra=extra,
            )
        )
        leftover = in_progress_on_remainder_off_empty(
            on_run, off_run, strip=strip
        )
        print(f"git-config force-progress leftover={leftover!r}")


def test_force_progress_non_truthy_stays_off():
    """A non-truthy progress-forcing token stays off, like the unset arm."""
    payload = _payload()
    rel = _rel()
    truthy = documented_truthy_skip()
    junk = non_truthy_boolean_token()
    extra = (
        "GIT_ORBULK_FORCE_PROGRESS",
        "lfs.forceprogress",
        truthy,
        junk,
    )
    with conforming_batch_server(
        mode="overlap_gate,download", payloads=[payload]
    ) as svc:
        with workspace() as on_ws:
            on_run, digest = _progress_fetch_workspace(
                on_ws,
                svc,
                rel,
                payload,
                env_updates=env_force_progress(truthy),
            )
        with workspace() as junk_ws:
            junk_run, _d = _progress_fetch_workspace(
                junk_ws,
                svc,
                rel,
                payload,
                env_updates=env_force_progress(junk),
            )
        strip = _progress_strip(
            on_ws,
            on_run,
            rel=rel,
            payload=payload,
            digest=digest,
            urls=(svc.url,),
            extra=extra,
        )
        strip.extend(
            _progress_strip(
                junk_ws,
                junk_run,
                rel=rel,
                payload=payload,
                digest=digest,
                urls=(svc.url,),
                extra=extra,
            )
        )
        leftover = in_progress_on_remainder_off_empty(
            on_run, junk_run, strip=strip
        )
        print(f"non-truthy force-progress leftover={leftover!r} token={junk!r}")


# ---------------------------------------------------------------------------
# H. Lockable read-only enable / disable via environment or Git config
# ---------------------------------------------------------------------------


def test_lockable_readonly_default_and_truthy_leave_unlocked_path_read_only_after_post_hook():
    """Default and truthy lockable read-only leave an unlocked path read-only."""
    truthy = documented_truthy_skip()
    with workspace() as default_ws:
        default_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(default_ws)
        _reapply_via_file_checkout(default_ws, rel)
        print("lockable default after post-*")
        require_file_read_only(default_ws.resolve(rel))
        require_file_writable(default_ws.resolve(ctrl))
        head = head_oid(default_ws)
        plumbing = run_post_checkout(default_ws, [head, head, "0"], via_git=False)
        require_success(plumbing)
        require_file_read_only(default_ws.resolve(rel))
    with workspace() as truthy_ws:
        truthy_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(truthy_ws)
        _reapply_via_file_checkout(
            truthy_ws, rel, env_updates=env_lockable_readonly(truthy)
        )
        print("lockable truthy after post-*")
        require_file_read_only(truthy_ws.resolve(rel))
        require_file_writable(truthy_ws.resolve(ctrl))


def test_lockable_readonly_falsey_leaves_unlocked_path_writable_after_post_hook():
    """Falsey environment or Git config leaves the unlocked lockable path writable.

    Only accepted after a live default-enabled arm where that same unlocked
    lockable path is actually read-only after the post-* file-checkout path.
    """
    falsey = documented_falsey()
    with workspace() as enabled:
        enabled.init_repo()
        rel, ctrl = _commit_lockable_and_control(enabled)
        _reapply_via_file_checkout(enabled, rel)
        print("lockable default live arm after post-*")
        require_file_read_only(enabled.resolve(rel))
        require_file_writable(enabled.resolve(ctrl))
    with workspace() as env_ws:
        env_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(env_ws)
        _reapply_via_file_checkout(
            env_ws, rel, env_updates=env_lockable_readonly(falsey)
        )
        print("lockable env falsey after post-*")
        require_file_writable(env_ws.resolve(rel))
        require_file_writable(env_ws.resolve(ctrl))
    with workspace() as git_ws:
        git_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(git_ws)
        configure_lockable_readonly(git_ws, falsey)
        _reapply_via_file_checkout(git_ws, rel)
        print("lockable git-config falsey after post-*")
        require_file_writable(git_ws.resolve(rel))
        require_file_writable(git_ws.resolve(ctrl))


def test_lockable_readonly_non_truthy_disables_rather_than_default_enabled():
    """Non-truthy lockable tokens disable read-only on both env and Git config.

    Only accepted after a live default-enabled arm where that same unlocked
    lockable path is actually read-only after the post-* file-checkout path.
    A non-truthy token must disable rather than leave that default-enabled
    state.
    """
    junk_git = non_truthy_boolean_token()
    junk_env = non_truthy_boolean_token()
    with workspace() as enabled:
        enabled.init_repo()
        rel, ctrl = _commit_lockable_and_control(enabled)
        _reapply_via_file_checkout(enabled, rel)
        print("lockable default live arm after post-*")
        require_file_read_only(enabled.resolve(rel))
        require_file_writable(enabled.resolve(ctrl))
    with workspace() as git_ws:
        git_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(git_ws)
        configure_lockable_readonly(git_ws, junk_git)
        _reapply_via_file_checkout(git_ws, rel)
        print(f"lockable git-config non-truthy token={junk_git!r}")
        require_file_writable(git_ws.resolve(rel))
        require_file_writable(git_ws.resolve(ctrl))
    with workspace() as env_ws:
        env_ws.init_repo()
        rel, ctrl = _commit_lockable_and_control(env_ws)
        _reapply_via_file_checkout(
            env_ws, rel, env_updates=env_lockable_readonly(junk_env)
        )
        print(f"lockable env non-truthy token={junk_env!r}")
        require_file_writable(env_ws.resolve(rel))
        require_file_writable(env_ws.resolve(ctrl))


# ---------------------------------------------------------------------------
# I. L442 catalog: already-traceable endpoint + default-remote observations
# ---------------------------------------------------------------------------


def test_git_config_catalog_is_observable_on_the_public_surface():
    """Endpoint SET names the dedicated indication; default remote is contacted.

    Catalog knobs that take effect on transfer, prune, storage, or agent
    paths are asserted by the later L442 take-effect tests, not as
    environment-report substrings.
    """
    url_a = runtime_http_url("endpoint")
    git_remote = runtime_http_url("origin")
    with workspace() as ws:
        ws.init_repo()
        add_git_remote(ws, "origin", git_remote)
        disable_lock_verification(ws)
        require_git_config_set(ws, "lfs.url", url_a, local=True)
        report = env_report(ws)
        observed = _origin_dedicated(report, git_remote)
        print(f"catalog dedicated={observed!r} endpoint={url_a!r}")
        _require_names(observed, url_a, role="catalog-endpoint")
    payload = _payload()
    rel = _rel()
    with recording_api_server() as (origin_url, origin_recs):
        with recording_api_server() as (sib_url, sib_recs):
            sibling_name = f"sib_{token()}"
            layout = TwoRemoteLayout(
                origin_url=f"{origin_url.rstrip('/')}/{token()}/repo.git",
                sibling_name=sibling_name,
                sibling_url=f"{sib_url.rstrip('/')}/{token()}/repo.git",
            )
            with workspace() as selected:
                install_two_remote_layout(selected, layout)
                disable_lock_verification(selected)
                digest = prepare_tracked_commit(selected, rel, payload)
                configure_default_remote(selected, layout.sibling_name)
                remove_stored_object(selected, digest)
                fetched = selected.invoke_via_git(["fetch"])
                print(f"default-remote fetch exit={fetched.returncode}")
                _require_contacted(
                    sib_recs, sib_url, role="catalog-default-remote"
                )
                _require_not_contacted(
                    origin_recs, origin_url, role="catalog-default-origin"
                )


# ---------------------------------------------------------------------------
# J. L442 Git-config catalog take-effect (not environment-report echoes)
# ---------------------------------------------------------------------------


def test_activity_timeout_takes_effect_on_stalling_download():
    """A stall longer than the activity timeout fails; a longer timeout succeeds."""
    payload = _payload()
    delay = 2.5
    with delayed_download_batch_server(
        delay_seconds=delay, payloads=[payload]
    ) as short_svc:
        with workspace() as short_ws:
            digest = _setup_one_download(short_ws, short_svc, payload)
            configure_http_timeouts(
                short_ws, dial=30, tls=30, activity=1, keepalive=30
            )
            failed = short_ws.invoke_via_git(["fetch"], timeout=20.0)
            print(f"short activity fetch exit={failed.returncode}")
            assert failed.returncode != 0, (
                "fetch succeeded with an activity timeout shorter than the "
                "stalling download"
            )
            require_object_absent(default_lfs_store_root(short_ws), digest)
    with delayed_download_batch_server(
        delay_seconds=delay, payloads=[payload]
    ) as long_svc:
        with workspace() as long_ws:
            digest = _setup_one_download(long_ws, long_svc, payload)
            configure_http_timeouts(
                long_ws, dial=30, tls=30, activity=20, keepalive=30
            )
            ok = long_ws.invoke_via_git(["fetch"], timeout=30.0)
            print(f"long activity fetch exit={ok.returncode}")
            require_success(ok)
            require_object_bytes(
                default_lfs_store_root(long_ws), digest, payload
            )


def test_concurrent_transfers_bound_prevents_overlap_unlike_unbounded():
    """Bound of 1 stays serial only after an unbounded run of the same pair overlaps."""
    payloads = [_payload(), _payload()]
    unbounded_max = 0
    with conforming_batch_server(
        mode="overlap_gate", payloads=payloads
    ) as unbounded:
        with workspace() as ws:
            digests = _setup_two_downloads(ws, unbounded, payloads)
            result = ws.invoke_via_git(["fetch"], timeout=90.0)
            print(
                f"unbounded overlap exit={result.returncode} "
                f"max_in_flight={unbounded.max_in_flight}"
            )
            require_success(result)
            store = default_lfs_store_root(ws)
            for digest, data in zip(digests, payloads):
                require_object_bytes(store, digest, data)
        unbounded_max = unbounded.max_in_flight
    with conforming_batch_server(
        mode="overlap_gate", payloads=payloads
    ) as bound:
        with workspace() as ws:
            digests = _setup_two_downloads(ws, bound, payloads)
            configure_concurrent_transfers(ws, 1)
            result = ws.invoke_via_git(["fetch"], timeout=90.0)
            print(
                f"bound-1 exit={result.returncode} "
                f"max_in_flight={bound.max_in_flight}"
            )
            require_success(result)
            store = default_lfs_store_root(ws)
            for digest, data in zip(digests, payloads):
                require_object_bytes(store, digest, data)
        require_bound_prevents_overlap_unlike_unbounded(
            bound.max_in_flight, unbounded_max
        )


def test_git_config_fetch_include_and_exclude_select_fetch_paths():
    """Git-config include fetches only the match; exclude skips the match."""
    keep = _rel("keep")
    skip = _rel("skip")
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as inc_svc:
        with workspace() as inc:
            inc.init_repo()
            point_lfs_at(inc, inc_svc.url)
            disable_lock_verification(inc)
            d_keep = prepare_tracked_commit(inc, keep, data_keep)
            d_skip = commit_tracked_payload(inc, skip, data_skip)
            configure_fetch_include(inc, keep)
            _wipe_store(inc, d_keep, d_skip)
            write_pointer_placeholders_from_index(inc, [keep, skip])
            require_success(inc.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(inc)
            require_object_bytes(store, d_keep, data_keep)
            require_object_absent(store, d_skip)
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as exc_svc:
        with workspace() as exc:
            exc.init_repo()
            point_lfs_at(exc, exc_svc.url)
            disable_lock_verification(exc)
            d_keep = prepare_tracked_commit(exc, keep, data_keep)
            d_skip = commit_tracked_payload(exc, skip, data_skip)
            configure_fetch_exclude(exc, skip)
            _wipe_store(exc, d_keep, d_skip)
            write_pointer_placeholders_from_index(exc, [keep, skip])
            require_success(exc.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(exc)
            require_object_bytes(store, d_keep, data_keep)
            require_object_absent(store, d_skip)


def test_git_config_lock_verification_refuses_foreign_lock_unlike_disabled():
    """Enabled locks-verify refuses a foreign-locked update; disabled still PUTs."""
    payload = _payload(pad=24)
    rel = _rel("lk")
    with locking_api_server(payloads=[payload]) as svc_on:
        with workspace() as on_ws:
            on_ws.init_repo()
            point_lfs_at(on_ws, svc_on.url)
            enable_lock_verification(on_ws)
            prepare_tracked_commit(on_ws, rel, payload)
            svc_on.inject_foreign_lock(rel)
            start = len(svc_on.records)
            rejected = on_ws.invoke_via_git(["push", "origin", "main"])
            print(f"locks-verify on exit={rejected.returncode}")
            assert rejected.returncode != 0, (
                "push succeeded while updating a path locked by others"
            )
            require_no_put_of(_records_since(svc_on, start), payload)
            require_locking_verify_received(svc_on)
    with locking_api_server(payloads=[payload]) as svc_off:
        with workspace() as off_ws:
            off_ws.init_repo()
            point_lfs_at(off_ws, svc_off.url)
            disable_lock_verification(off_ws)
            prepare_tracked_commit(off_ws, rel, payload)
            svc_off.inject_foreign_lock(rel)
            start = len(svc_off.records)
            ok = off_ws.invoke_via_git(["push", "origin", "main"])
            print(f"locks-verify off exit={ok.returncode}")
            require_success(ok)
            require_put_of(_records_since(svc_off, start), payload)


def test_ssh_transfer_modes_select_different_transfer_families():
    """never uses hybrid HTTPS; always uses git-orbulk-transfer and not HTTPS."""
    payload = _payload()
    ssh_url, repo_path = ssh_style_remote()
    with storing_batch_server() as svc:
        svc.stored[sha256_hex(payload)] = payload
        with workspace() as never_ws:
            probe = install_ssh_transfer_peer(
                never_ws, mode="serve", authenticate_json=_auth_json(svc.url)
            )
            never_ws.init_repo()
            add_git_remote(never_ws, "origin", ssh_url)
            rel = _rel()
            digest = prepare_tracked_commit(never_ws, rel, payload)
            configure_ssh_transfer_mode(never_ws, "never")
            _wipe_store(never_ws, digest)
            write_pointer_placeholders_from_index(never_ws, [rel])
            result = never_ws.invoke_via_git(
                ["fetch"], env_updates=ssh_env_updates(probe)
            )
            print(
                f"never fetch exit={result.returncode} nhttp={len(svc.records)}"
            )
            require_success(result)
            require_no_transfer_invocation(probe.argv_log)
            require_authenticate_invocation(
                probe.argv_log,
                repo_path_fragment=repo_path,
                operation="download",
            )
            gets = [rec for rec in svc.records if rec.method == "GET"]
            assert gets, (
                "never mode did not GET object bytes on the hybrid path"
            )
            require_object_bytes(
                default_lfs_store_root(never_ws), digest, payload
            )
        n0 = len(svc.records)
        with workspace() as always_ws:
            probe_a = install_ssh_transfer_peer(
                always_ws, mode="serve", authenticate_json=_auth_json(svc.url)
            )
            always_ws.init_repo()
            add_git_remote(always_ws, "origin", ssh_url)
            rel = _rel()
            digest = prepare_tracked_commit(always_ws, rel, payload)
            configure_ssh_transfer_mode(always_ws, "always")
            _wipe_store(always_ws, digest)
            write_pointer_placeholders_from_index(always_ws, [rel])
            oid = sha256_hex(payload)
            (probe_a.seed_dir / oid).write_bytes(payload)
            result = always_ws.invoke_via_git(
                ["fetch"], env_updates=ssh_env_updates(probe_a)
            )
            later = svc.records[n0:]
            print(
                f"always fetch exit={result.returncode} nhttp={len(later)}"
            )
            require_success(result)
            require_transfer_invocation(
                probe_a.argv_log,
                repo_path_fragment=repo_path,
                operation="download",
            )
            require_no_authenticate_invocation(probe_a.argv_log)
            require_no_http_exchanges(later)
            require_object_bytes(
                default_lfs_store_root(always_ws), digest, payload
            )
        n1 = len(svc.records)
        with workspace() as negotiate_ws:
            probe_n = install_ssh_transfer_peer(
                negotiate_ws,
                mode="serve",
                authenticate_json=_auth_json(svc.url),
            )
            negotiate_ws.init_repo()
            add_git_remote(negotiate_ws, "origin", ssh_url)
            rel = _rel()
            digest = prepare_tracked_commit(negotiate_ws, rel, payload)
            configure_ssh_transfer_mode(negotiate_ws, "negotiate")
            _wipe_store(negotiate_ws, digest)
            write_pointer_placeholders_from_index(negotiate_ws, [rel])
            oid = sha256_hex(payload)
            (probe_n.seed_dir / oid).write_bytes(payload)
            result = negotiate_ws.invoke_via_git(
                ["fetch"], env_updates=ssh_env_updates(probe_n)
            )
            later_n = svc.records[n1:]
            print(
                f"negotiate fetch exit={result.returncode} "
                f"nhttp={len(later_n)}"
            )
            require_success(result)
            require_transfer_invocation(
                probe_n.argv_log,
                repo_path_fragment=repo_path,
                operation="download",
            )
            require_object_bytes(
                default_lfs_store_root(negotiate_ws), digest, payload
            )


def test_relocated_storage_root_receives_cleaned_objects_not_default_path():
    """Configured storage is the objects-directory parent; default store is unused."""
    data = _payload()
    digest = sha256_hex(data)
    with workspace() as ws:
        ws.init_repo()
        store = (ws.home / f"lfsstore_{token()}").resolve()
        store.mkdir()
        configure_storage_root(ws, store)
        pointer_from_clean(
            clean_bytes(ws, data), digest=digest, size=len(data)
        )
        stored = require_object_bytes(store, digest, data)
        require_object_absent(default_lfs_store_root(ws), digest)
        print(f"relocated stored={stored}")


def test_prune_recentness_and_verify_default_take_effect():
    """Covering recent refs keep an other-branch tip; verify-always without the flag keeps unverified candidates."""
    other = f"br_{token()}"
    rel_o = _rel("r")
    data_o = _payload()
    with workspace() as covering:
        _init_tracked(covering)
        rel_h = _rel("h")
        data_h = _payload()
        oid_h = commit_tracked_payload(covering, rel_h, data_h)
        _git_ok(covering, ["checkout", "-b", other])
        oid_o = commit_tracked_payload(covering, rel_o, data_o)
        _git_ok(covering, ["checkout", "main"])
        configure_recentness(covering, ref_days=2)
        _plant_origin_at_head(covering)
        set_remote_tracking(covering, "origin", other, _sha(covering, other))
        store = default_lfs_store_root(covering)
        require_success(run_prune(covering))
        print(f"recent covering kept other={oid_o} head={oid_h}")
        require_object_bytes(store, oid_o, data_o)
        require_object_bytes(store, oid_h, data_h)
    with workspace() as zero:
        _init_tracked(zero)
        rel_h = _rel("h")
        data_h = _payload()
        oid_h = commit_tracked_payload(zero, rel_h, data_h)
        _git_ok(zero, ["checkout", "-b", other])
        oid_o = commit_tracked_payload(zero, rel_o, data_o)
        _git_ok(zero, ["checkout", "main"])
        configure_recentness(zero, ref_days=0)
        _plant_origin_at_head(zero)
        set_remote_tracking(zero, "origin", other, _sha(zero, other))
        store = default_lfs_store_root(zero)
        require_success(run_prune(zero))
        print(f"recent zero deleted other={oid_o}")
        require_object_absent(store, oid_o)
        require_object_bytes(store, oid_h, data_h)
    far = "1990-01-15T12:00:00"
    with workspace() as baseline:
        _init_tracked(baseline)
        rel_v = _rel("v")
        data_v = _payload()
        data_h = _payload()
        oid_v = commit_tracked_payload_dated(baseline, rel_v, data_v, far)
        _git_ok(baseline, ["rm", "--", rel_v])
        oid_h = commit_tracked_payload(baseline, _rel("h"), data_h)
        configure_recentness(baseline, ref_days=0)
        _plant_origin_at_head(baseline)
        store = default_lfs_store_root(baseline)
        require_success(run_prune(baseline))
        print(f"verify-default unset deleted stale={oid_v}")
        require_object_absent(store, oid_v)
        require_object_bytes(store, oid_h, data_h)
    with storing_batch_server() as svc:
        with workspace() as always:
            _init_tracked(always)
            rel_v = _rel("v")
            data_v = _payload()
            data_h = _payload()
            oid_v = commit_tracked_payload_dated(always, rel_v, data_v, far)
            _git_ok(always, ["rm", "--", rel_v])
            oid_h = commit_tracked_payload(always, _rel("h"), data_h)
            configure_recentness(always, ref_days=0)
            _plant_origin_at_head(always)
            set_lfs_endpoint(always, svc.url)
            require_git_config_set(
                always, "lfs.pruneverifyremotealways", "true", local=True
            )
            store = default_lfs_store_root(always)
            result = run_prune(always, ["--when-unverified=halt"])
            print(f"verify-always halt exit={result.returncode}")
            require_object_bytes(store, oid_v, data_v)
            require_object_bytes(store, oid_h, data_h)


def test_tus_and_basic_transfers_only_change_advertised_adapter_list():
    """tus appears on the advertised list; basic-transfers-only drops it."""
    payload = _payload()
    with conforming_batch_server(
        mode="upload", payloads=[payload]
    ) as on_svc:
        with workspace() as on_ws:
            digest = _setup_one_upload(on_ws, on_svc, payload)
            enable_tus_transfers(on_ws)
            run_on = on_ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            parsed_on = require_batch_post(on_svc.records, operation="upload")
            names_on = require_advanced_advertised(parsed_on)
            print(f"tus-on advertised={names_on!r} exit={run_on.returncode}")
    with conforming_batch_server(
        mode="upload", payloads=[payload]
    ) as off_svc:
        with workspace() as off_ws:
            digest = _setup_one_upload(off_ws, off_svc, payload)
            enable_tus_transfers(off_ws)
            enable_basic_transfers_only(off_ws)
            run_off = off_ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            parsed_off = require_batch_post(off_svc.records, operation="upload")
            names_off = require_basic_only_or_omitted(parsed_off)
            print(
                f"basic-only advertised={names_off!r} exit={run_off.returncode}"
            )
    assert names_on != names_off, (
        "basic-transfers-only did not change the advertised adapter list"
    )


def test_registered_custom_agent_is_advertised_and_launched_when_selected():
    """A bound custom agent is advertised and launched when the peer selects it."""
    payload = _payload()
    name = f"xf{token()}"
    with named_transfer_batch_server(select=name, payloads=[payload]) as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_one_upload(ws, svc, payload)
            _bind_named_agent(ws, name, probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(
                f"agent upload exit={result.returncode} name={name!r} "
                f"n={len(svc.records)}"
            )
            require_success(result)
            parsed = require_batch_post(svc.records, operation="upload")
            assert_adapter_name_advertised(parsed, name)
            assert_agent_was_launched(probe)


# ---------------------------------------------------------------------------
# K. L441 .lfsconfig allowlist take-effect
# ---------------------------------------------------------------------------


def test_lfsconfig_fetch_include_and_exclude_select_fetch_paths():
    """Accepted .lfsconfig include fetches only the match; exclude skips the match."""
    keep = _rel("keep")
    skip = _rel("skip")
    data_keep, data_skip = _payload(), _payload()
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as inc_svc:
        with workspace() as inc:
            inc.init_repo()
            point_lfs_at(inc, inc_svc.url)
            disable_lock_verification(inc)
            d_keep = prepare_tracked_commit(inc, keep, data_keep)
            d_skip = commit_tracked_payload(inc, skip, data_skip)
            require_lfsconfig_set(inc, "lfs.fetchinclude", keep)
            _wipe_store(inc, d_keep, d_skip)
            write_pointer_placeholders_from_index(inc, [keep, skip])
            require_success(inc.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(inc)
            require_object_bytes(store, d_keep, data_keep)
            require_object_absent(store, d_skip)
    with conforming_batch_server(
        mode="download", payloads=[data_keep, data_skip]
    ) as exc_svc:
        with workspace() as exc:
            exc.init_repo()
            point_lfs_at(exc, exc_svc.url)
            disable_lock_verification(exc)
            d_keep = prepare_tracked_commit(exc, keep, data_keep)
            d_skip = commit_tracked_payload(exc, skip, data_skip)
            require_lfsconfig_set(exc, "lfs.fetchexclude", skip)
            _wipe_store(exc, d_keep, d_skip)
            write_pointer_placeholders_from_index(exc, [keep, skip])
            require_success(exc.invoke_via_git(["fetch"]))
            store = default_lfs_store_root(exc)
            require_object_bytes(store, d_keep, data_keep)
            require_object_absent(store, d_skip)


def test_lfsconfig_allow_incomplete_push_lets_missing_object_proceed():
    """Truthy allow-incomplete-push in .lfsconfig lets a missing object push proceed."""
    payload = _payload()
    with conforming_batch_server(mode="upload", payloads=[payload]) as fail_svc:
        with workspace() as fail_ws:
            _bare_push_layout(fail_ws, fail_svc.url)
            digest = prepare_tracked_commit(fail_ws, _rel(), payload)
            _wipe_store(fail_ws, digest)
            failed = fail_ws.git(["push", "origin", "main"])
            print(f"incomplete-push unset exit={failed.returncode}")
            assert failed.returncode != 0, (
                "push of a missing object succeeded without allow-incomplete-push"
            )
            require_no_put_of(fail_svc.records, payload)
    with conforming_batch_server(mode="upload", payloads=[payload]) as ok_svc:
        with workspace() as ok_ws:
            bare = _bare_push_layout(ok_ws, ok_svc.url)
            digest = prepare_tracked_commit(ok_ws, _rel(), payload)
            require_lfsconfig_set(
                ok_ws, "lfs.allowincompletepush", documented_truthy_skip()
            )
            new = head_oid(ok_ws)
            _wipe_store(ok_ws, digest)
            allowed = ok_ws.git(["push", "origin", "main"])
            print(f"incomplete-push allowed exit={allowed.returncode}")
            require_success(allowed)
            require_no_put_of(ok_svc.records, payload)
            require_ref_at(ok_ws, "refs/heads/main", new, cwd=bare)


def test_lfsconfig_locks_verify_refuses_foreign_lock_unlike_absent_file():
    """Truthy locks-verify in .lfsconfig refuses a foreign-locked update."""
    payload = _payload(pad=18)
    rel = _rel("cfg")
    with locking_api_server(payloads=[payload]) as svc_on:
        with workspace() as on_ws:
            on_ws.init_repo()
            point_lfs_at(on_ws, svc_on.url)
            require_lfsconfig_set(
                on_ws, "lfs.locksverify", documented_truthy_skip()
            )
            prepare_tracked_commit(on_ws, rel, payload)
            svc_on.inject_foreign_lock(rel)
            start = len(svc_on.records)
            rejected = on_ws.invoke_via_git(["push", "origin", "main"])
            print(f"lfsconfig locks-verify on exit={rejected.returncode}")
            assert rejected.returncode != 0, (
                "push succeeded while updating a path locked by others"
            )
            require_no_put_of(_records_since(svc_on, start), payload)
            require_locking_verify_received(svc_on)
    with locking_api_server(payloads=[payload]) as svc_off:
        with workspace() as off_ws:
            off_ws.init_repo()
            point_lfs_at(off_ws, svc_off.url)
            require_lfsconfig_set(
                off_ws, "lfs.locksverify", documented_falsey()
            )
            prepare_tracked_commit(off_ws, rel, payload)
            svc_off.inject_foreign_lock(rel)
            start = len(svc_off.records)
            ok = off_ws.invoke_via_git(["push", "origin", "main"])
            print(f"lfsconfig locks-verify off exit={ok.returncode}")
            require_success(ok)
            require_put_of(_records_since(svc_off, start), payload)


def test_lfsconfig_url_scoped_access_sends_basic_on_first_request():
    """URL-scoped access in .lfsconfig puts Basic on the first request."""
    user = f"u_{token()}"
    password = f"p_{token()}"
    payload = _payload()
    with recording_api_server(
        accepted_user=user, accepted_password=password
    ) as (url, records):
        with workspace() as with_access:
            with_access.init_repo()
            add_git_remote(with_access, "origin", f"{url}/{token()}/repo.git")
            set_lfs_endpoint(with_access, url)
            disable_lock_verification(with_access)
            install_credential_helper(with_access, user, password)
            require_lfsconfig_set(with_access, f"lfs.{url}.access", "basic")
            digest = prepare_tracked_commit(with_access, _rel(), payload)
            _wipe_store(with_access, digest)
            with_access.invoke_via_git(["fetch"])
            print(f"access-on n={len(records)}")
            assert records, "no API request with URL-scoped access set"
            first = records[0]
            assert first.authorization, (
                "first request had no Authorization after URL-scoped access SET"
            )
            require_request_carries_basic(records, user, password)
    with recording_api_server(
        accepted_user=user, accepted_password=password
    ) as (url, records):
        with workspace() as without:
            without.init_repo()
            add_git_remote(without, "origin", f"{url}/{token()}/repo.git")
            set_lfs_endpoint(without, url)
            disable_lock_verification(without)
            install_credential_helper(without, user, password)
            digest = prepare_tracked_commit(without, _rel(), payload)
            _wipe_store(without, digest)
            without.invoke_via_git(["fetch"])
            print(f"access-off n={len(records)}")
            assert records, "no API request without URL-scoped access"
            first = records[0]
            assert not first.authorization, (
                "first request already carried Authorization without "
                "URL-scoped access SET"
            )


def test_lfsconfig_git_protocol_changes_dedicated_indication_scheme():
    """Accepted Git-protocol setting in .lfsconfig changes the derived scheme."""
    host = f"{token()}.gitproto.example.test"
    repo_path = f"{token()}/repo"
    git_url = f"git://{host}/{repo_path}"
    with workspace() as default_ws:
        default_ws.init_repo()
        add_git_remote(default_ws, "origin", git_url)
        disable_lock_verification(default_ws)
        report = env_report(default_ws)
        default_ind = _origin_dedicated(report, git_url)
        print(f"gitprotocol default dedicated={default_ind!r}")
        assert default_ind.startswith("https://"), (
            "default Git protocol indication was not https: "
            f"{default_ind!r}"
        )
    with workspace() as http_ws:
        http_ws.init_repo()
        add_git_remote(http_ws, "origin", git_url)
        disable_lock_verification(http_ws)
        require_lfsconfig_set(http_ws, "lfs.gitprotocol", "http")
        report = env_report(http_ws)
        http_ind = _origin_dedicated(report, git_url)
        print(f"gitprotocol http dedicated={http_ind!r}")
        assert http_ind.startswith("http://"), (
            "http Git protocol indication was not http: "
            f"{http_ind!r}"
        )
        assert not http_ind.startswith("https://"), (
            "http Git protocol indication still used https: "
            f"{http_ind!r}"
        )
    assert default_ind != http_ind, (
        "Git protocol setting in .lfsconfig did not change the dedicated "
        "indication"
    )


# ---------------------------------------------------------------------------
# L. Negative control
# ---------------------------------------------------------------------------



def test_env_and_config_backed_command_fail_when_binary_removed_from_path():
    """Removing the product from PATH fails env and a transfer-backed fetch."""
    git_remote = f"https://{token()}.origin.example.test/{token()}/repo.git"
    payload = _payload()
    rel = _rel()
    with conforming_batch_server(mode="download", payloads=[payload]) as svc:
        with workspace() as present:
            present.init_repo()
            add_git_remote(present, "origin", git_remote)
            require_lfsconfig_set(present, "lfs.url", svc.url)
            digest = prepare_tracked_commit(present, rel, payload)
            ok_env = present.invoke_via_git(["env"])
            print(f"present env exit={ok_env.returncode}")
            require_success(ok_env)
            observed = _origin_dedicated(ok_env.stdout_text, git_remote)
            _require_names(observed, svc.url, role="present-env")
            remove_stored_object(present, digest)
            ok_fetch = present.invoke_via_git(["fetch"])
            print(f"present fetch exit={ok_fetch.returncode}")
            require_success(ok_fetch)
        with workspace() as missing:
            missing.init_repo()
            add_git_remote(missing, "origin", git_remote)
            require_lfsconfig_set(missing, "lfs.url", svc.url)
            digest = prepare_tracked_commit(missing, rel, payload)
            hidden = path_without_product_bin(missing.env)
            env = {"PATH": hidden}
            failed_env = missing.invoke_via_git(["env"], env_updates=env)
            remove_stored_object(missing, digest)
            failed_fetch = missing.invoke_via_git(
                ["fetch"], env_updates=env
            )
            print(
                f"absent env={failed_env.returncode} "
                f"fetch={failed_fetch.returncode} hidden={hidden!r}"
            )
            assert failed_env.returncode != 0, (
                "env succeeded after the product binary was removed from PATH"
            )
            assert failed_fetch.returncode != 0, (
                "fetch succeeded after the product binary was removed from PATH"
            )
            assert (failed_env.returncode, failed_env.stdout, failed_env.stderr) != (
                ok_env.returncode,
                ok_env.stdout,
                ok_env.stderr,
            ), "absent-binary env was not distinguishable from a successful env"
