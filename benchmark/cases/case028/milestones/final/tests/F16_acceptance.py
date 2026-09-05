# feature: F16
"""Custom transfers, standalone file URLs, and clean/smudge extensions.

PRD: FP-16. JSON event field names, pointer extension key spelling,
append-token text, a particular priority-number pair, stderr wording,
and exact exit-code numbers are not pinned.
"""

from __future__ import annotations

from pathlib import Path

from _harness import token, workspace
from _helpers import (
    add_git_remote,
    agent_was_launched,
    agent_wrote_payload,
    append_token_transform_scripts,
    assert_adapter_name_advertised,
    assert_agent_control_has_json_without_payload,
    assert_agent_was_launched,
    assert_agent_wrote_payload,
    assert_batch_post,
    assert_invalid_unlike_success,
    assert_no_get_of_object_action,
    assert_no_objects_batch_post,
    assert_no_put_of,
    assert_object_absent,
    assert_object_bytes,
    assert_put_of,
    assert_success,
    clean_bytes,
    configure_custom_transfer_agent,
    configure_lfs_clean_filter,
    configure_standalone_transfer_agent,
    contract_basic_adapter_name,
    default_lfs_store_root,
    default_lfs_store_root_at,
    extract_generated_pointer_document,
    extension_command_stdin,
    failing_extension_command,
    file_remote_url,
    index_blob,
    init_bare_git_remote,
    install_json_path_agent,
    named_transfer_batch_server,
    path_without_product_bin,
    pointer_matches_digest_and_size,
    pointer_non_core_pairs,
    point_lfs_at,
    prepare_tracked_commit,
    priority_pair_numeric_not_lexicographic,
    register_transform_extension,
    remove_stored_object,
    require_batch_post,
    require_ext_listing_names,
    require_generated_pointer_shape,
    require_git_config_set,
    require_invalid_unlike_success,
    require_object_absent,
    require_object_bytes,
    require_put_of,
    require_success,
    seed_agent_payload,
    sha256_hex,
    smudge_bytes,
    storing_batch_server,
    strip_listing_covariates,
    track_pattern,
    unlaunchable_process_path,
)


def _payload() -> bytes:
    return f"blob-{token()}\n".encode("utf-8")


def _rel() -> str:
    return f"payload_{token()}.bin"


def _agent_name() -> str:
    return f"xf{token()}"


def _bind_agent(ws, name: str, path) -> None:
    configure_custom_transfer_agent(ws, name, path)
    require_git_config_set(
        ws, f"lfs.customtransfer.{name}.concurrent", "false", local=True
    )


def _require_missing_path(path: Path) -> None:
    try:
        exists = path.exists()
    except OSError as exc:
        raise AssertionError(f"cannot stat decoy path {path}: {exc}") from exc
    assert not exists, f"object was written at unrelated path {path}"


def _pointer_for_stored(result, stored: bytes) -> bytes:
    digest = sha256_hex(stored)
    document = extract_generated_pointer_document(
        result, digest=digest, size=len(stored)
    )
    require_generated_pointer_shape(document, digest=digest, size=len(stored))
    return document


def _setup_tracked(ws, svc_url: str, payload: bytes) -> str:
    ws.init_repo()
    point_lfs_at(ws, svc_url)
    return prepare_tracked_commit(ws, _rel(), payload)


# ---------------------------------------------------------------------------
# A. Advertise registered custom name; invoke when selected
# ---------------------------------------------------------------------------


def test_registered_custom_agent_is_advertised_and_invoked_on_upload_when_selected():
    """Upload batch advertises N; selected agent moves bytes via paths, not PUT."""
    payload = _payload()
    name = _agent_name()
    with named_transfer_batch_server(select=name, payloads=[payload]) as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, name, probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(
                f"upload exit={result.returncode} name={name!r} "
                f"n={len(svc.records)} digest={digest}"
            )
            assert_success(result)
            parsed = assert_batch_post(svc.records, operation="upload")
            assert_adapter_name_advertised(parsed, name)
            assert_agent_was_launched(probe)
            assert_agent_control_has_json_without_payload(probe, payload)
            wrote = assert_agent_wrote_payload(probe, payload)
            assert_no_put_of(svc.records, payload)
            print(f"agent wrote {wrote} advertised={parsed.transfers!r}")


def test_registered_custom_agent_is_invoked_on_download_when_selected():
    """Download batch advertises N; bytes arrive via agent paths, not GET."""
    payload = _payload()
    name = _agent_name()
    with named_transfer_batch_server(select=name, payloads=[payload]) as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, name, probe.path)
            seed_agent_payload(probe, payload)
            remove_stored_object(ws, digest)
            require_object_absent(default_lfs_store_root(ws), digest)
            result = ws.invoke(["fetch"])
            print(
                f"download exit={result.returncode} name={name!r} "
                f"n={len(svc.records)}"
            )
            assert_success(result)
            parsed = assert_batch_post(svc.records, operation="download")
            assert_adapter_name_advertised(parsed, name)
            assert_agent_was_launched(probe)
            assert_agent_control_has_json_without_payload(probe, payload)
            wrote = assert_agent_wrote_payload(probe, payload)
            assert_object_bytes(default_lfs_store_root(ws), digest, payload)
            assert_no_get_of_object_action(
                svc.records, svc.action_path(digest)
            )
            print(f"download agent wrote {wrote}")


def test_custom_agent_control_stream_is_json_without_object_bytes():
    """Selected custom agent speaks JSON on the control stream, not file bytes."""
    payload = _payload()
    name = _agent_name()
    with named_transfer_batch_server(select=name, payloads=[payload]) as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, name, probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            assert_success(result)
            assert_adapter_name_advertised(
                assert_batch_post(svc.records, operation="upload"), name
            )
            assert_agent_was_launched(probe)
            raw = assert_agent_control_has_json_without_payload(probe, payload)
            assert_agent_wrote_payload(probe, payload)
            print(f"control_len={len(raw)}")


# ---------------------------------------------------------------------------
# B. Built-in basic / ssh override a same-name custom agent
# ---------------------------------------------------------------------------


def test_custom_agent_named_basic_does_not_replace_builtin_basic_http_transfer():
    """A custom agent registered as basic still uses HTTP PUT; it is not launched."""
    payload = _payload()
    live_name = _agent_name()
    with named_transfer_batch_server(
        select=live_name, payloads=[payload]
    ) as live_svc:
        with workspace() as live:
            probe_live = install_json_path_agent(live)
            digest = _setup_tracked(live, live_svc.url, payload)
            _bind_agent(live, live_name, probe_live.path)
            ok = live.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            require_success(ok)
            agent_was_launched(probe_live)
            agent_wrote_payload(probe_live, payload)
            print(f"live custom launch name={live_name!r}")
    with storing_batch_server() as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, contract_basic_adapter_name(), probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"basic-name exit={result.returncode} n={len(svc.records)}")
            require_success(result)
            require_put_of(svc.records, payload)
            try:
                probe.marker.read_bytes()
            except FileNotFoundError:
                print("basic-name custom agent was not launched")
            except OSError as exc:
                raise AssertionError(
                    f"cannot read custom-agent marker: {exc}"
                ) from exc
            else:
                raise AssertionError(
                    "custom agent registered as basic was launched"
                )


def test_custom_agent_named_ssh_is_not_invoked_on_http_basic_transfer():
    """Built-in ssh overrides a same-name custom agent; basic upload still PUTs.

    Live baseline: a non-built-in custom name is launched when selected.
    HTTP basic upload of that object still PUTs the object bytes.
    The ssh-named custom process is not launched. HTTP advertisement of
    ssh is not required: a basic-only or omitted transfer list still
    honours the override.
    """
    payload = _payload()
    live_name = _agent_name()
    with named_transfer_batch_server(
        select=live_name, payloads=[payload]
    ) as live_svc:
        with workspace() as live:
            probe_live = install_json_path_agent(live)
            digest = _setup_tracked(live, live_svc.url, payload)
            _bind_agent(live, live_name, probe_live.path)
            ok = live.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            require_success(ok)
            agent_was_launched(probe_live)
            print(f"live custom launch name={live_name!r}")
    with storing_batch_server() as svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, "ssh", probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"ssh-name basic exit={result.returncode} n={len(svc.records)}")
            require_success(result)
            require_put_of(svc.records, payload)
            try:
                probe.marker.read_bytes()
            except FileNotFoundError:
                print("ssh-name custom agent was not launched on HTTP basic")
            except OSError as exc:
                raise AssertionError(
                    f"cannot read custom-agent marker: {exc}"
                ) from exc
            else:
                raise AssertionError(
                    "custom agent registered as ssh was launched on HTTP basic"
                )
    with named_transfer_batch_server(select="ssh", payloads=[payload]) as ssh_svc:
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, ssh_svc.url, payload)
            _bind_agent(ws, "ssh", probe.path)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(
                f"ssh-selected exit={result.returncode} n={len(ssh_svc.records)}"
            )
            parsed = require_batch_post(ssh_svc.records, operation="upload")
            print(f"ssh-arm advertised={parsed.transfers!r}")
            try:
                probe.marker.read_bytes()
            except FileNotFoundError:
                print("ssh-name custom agent was not launched on the ssh arm")
            except OSError as exc:
                raise AssertionError(
                    f"cannot read custom-agent marker: {exc}"
                ) from exc
            else:
                raise AssertionError(
                    "custom agent registered as ssh was launched"
                )


# ---------------------------------------------------------------------------
# C. Named standalone agent skips the batch API
# ---------------------------------------------------------------------------


def test_named_standalone_custom_agent_skips_batch_api_and_is_driven_directly():
    """A registered standalone name skips objects-batch and still moves bytes."""
    payload = _payload()
    name = _agent_name()
    with storing_batch_server() as svc:
        with workspace() as baseline:
            digest = _setup_tracked(baseline, svc.url, payload)
            ok = baseline.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            assert_success(ok)
            assert_batch_post(svc.records, operation="upload")
            assert_put_of(svc.records, payload)
            print(f"baseline batch n={len(svc.records)}")
            n = len(svc.records)
        with workspace() as ws:
            probe = install_json_path_agent(ws)
            digest = _setup_tracked(ws, svc.url, payload)
            _bind_agent(ws, name, probe.path)
            configure_standalone_transfer_agent(ws, name)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"standalone exit={result.returncode} extra={len(svc.records) - n}")
            assert_success(result)
            assert_no_objects_batch_post(svc.records[n:])
            assert_no_put_of(svc.records[n:], payload)
            assert_agent_was_launched(probe)
            assert_agent_wrote_payload(probe, payload)


# ---------------------------------------------------------------------------
# D. file:// / local-path Git remotes write dest default shard layout
# ---------------------------------------------------------------------------


def test_file_url_git_remote_upload_writes_destination_default_sharded_store():
    """file:// upload lands in dest Git dir default objects shard, not a decoy."""
    payload = _payload()
    with workspace() as ws:
        dest = init_bare_git_remote(ws, f"dest_{token()}.git")
        url = file_remote_url(dest)
        ws.init_repo()
        add_git_remote(ws, "origin", url)
        digest = prepare_tracked_commit(ws, _rel(), payload)
        result = ws.git(["push", "origin", "HEAD:refs/heads/main"])
        print(
            f"file-url push exit={result.returncode} dest={dest} "
            f"digest={digest}"
        )
        assert result.returncode == 0, (
            f"push to file:// remote failed (exit {result.returncode}): "
            f"{result.stderr_text}"
        )
        require_object_bytes(
            default_lfs_store_root_at(ws, dest), digest, payload
        )
        _require_missing_path(dest / digest)
        _require_missing_path(dest / "objects" / digest)
        _require_missing_path(ws.path / digest)


def test_local_path_git_remote_upload_writes_destination_default_sharded_store():
    """A scheme-less local-path Git remote uses the same dest default shard."""
    payload = _payload()
    with workspace() as ws:
        dest = init_bare_git_remote(ws, f"dest_{token()}.git")
        url = str(dest.resolve())
        ws.init_repo()
        add_git_remote(ws, "origin", url)
        digest = prepare_tracked_commit(ws, _rel(), payload)
        result = ws.git(["push", "origin", "HEAD:refs/heads/main"])
        print(
            f"local-path push exit={result.returncode} dest={dest} "
            f"digest={digest}"
        )
        assert result.returncode == 0, (
            f"push to local-path remote failed (exit {result.returncode}): "
            f"{result.stderr_text}"
        )
        require_object_bytes(
            default_lfs_store_root_at(ws, dest), digest, payload
        )
        _require_missing_path(dest / digest)
        _require_missing_path(dest / "objects" / digest)
        _require_missing_path(ws.path / digest)


def test_file_url_git_remote_fetch_populates_local_default_sharded_store():
    """Fetching from a file:// remote that already holds the object fills local store."""
    payload = _payload()
    with workspace() as ws:
        dest = init_bare_git_remote(ws, f"dest_{token()}.git")
        url = file_remote_url(dest)
        ws.init_repo()
        add_git_remote(ws, "origin", url)
        digest = prepare_tracked_commit(ws, _rel(), payload)
        pushed = ws.git(["push", "origin", "HEAD:refs/heads/main"])
        assert pushed.returncode == 0, (
            f"setup push to file:// dest failed (exit {pushed.returncode}): "
            f"{pushed.stderr_text}"
        )
        require_object_bytes(
            default_lfs_store_root_at(ws, dest), digest, payload
        )
        remove_stored_object(ws, digest)
        require_object_absent(default_lfs_store_root(ws), digest)
        fetched = ws.invoke_via_git(["fetch"])
        print(f"file-url fetch exit={fetched.returncode} digest={digest}")
        require_success(fetched)
        require_object_bytes(default_lfs_store_root(ws), digest, payload)


# ---------------------------------------------------------------------------
# E. Clean applies extensions in ascending priority-number order
# ---------------------------------------------------------------------------


def _register_pair(ws, *, lo: int, hi: int, token_a: str, token_b: str):
    name_lo = f"lo{token()}"
    name_hi = f"hi{token()}"
    clean_a, smudge_a = append_token_transform_scripts(ws, token_a)
    clean_b, smudge_b = append_token_transform_scripts(ws, token_b)
    register_transform_extension(
        ws, name=name_lo, priority=lo, clean_cmd=clean_a, smudge_cmd=smudge_a
    )
    register_transform_extension(
        ws, name=name_hi, priority=hi, clean_cmd=clean_b, smudge_cmd=smudge_b
    )
    return name_lo, name_hi, clean_a, clean_b, smudge_a, smudge_b


def test_two_extensions_clean_smaller_priority_number_first():
    """Numeric ascending clean order stores payload+A+B, not the reverse."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    expected = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    reversed_order = payload + token_b.encode("utf-8") + token_a.encode("utf-8")
    assert expected != reversed_order
    with workspace() as ws:
        ws.init_repo()
        _register_pair(
            ws, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        configure_lfs_clean_filter(ws)
        rel = _rel()
        track_pattern(ws, f"*{Path(rel).suffix}")
        ws.write(rel, payload)
        added = ws.git(["add", "--", rel, ".gitattributes"])
        print(
            f"git add exit={added.returncode} lo={lo} hi={hi} "
            f"str_lo={str(lo)!r} str_hi={str(hi)!r}"
        )
        require_success(added)
        digest = sha256_hex(expected)
        require_object_bytes(default_lfs_store_root(ws), digest, expected)
        blob = index_blob(ws, rel)
        require_generated_pointer_shape(
            blob, digest=digest, size=len(expected)
        )
        assert sha256_hex(payload) != digest


def test_swapping_only_priority_numbers_reverses_stored_object():
    """Swapping only the two priority numbers reverses the stored pipeline."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    expected_asc = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    expected_swap = payload + token_b.encode("utf-8") + token_a.encode("utf-8")
    with workspace() as asc:
        asc.init_repo()
        _register_pair(
            asc, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        result = clean_bytes(asc, payload)
        require_success(result)
        _pointer_for_stored(result, expected_asc)
        require_object_bytes(
            default_lfs_store_root(asc), sha256_hex(expected_asc), expected_asc
        )
    with workspace() as swapped:
        swapped.init_repo()
        name_lo, name_hi, *_ = _register_pair(
            swapped, lo=hi, hi=lo, token_a=token_a, token_b=token_b
        )
        print(f"swap names={name_lo},{name_hi} priorities={hi} then {lo}")
        result = clean_bytes(swapped, payload)
        require_success(result)
        _pointer_for_stored(result, expected_swap)
        require_object_bytes(
            default_lfs_store_root(swapped),
            sha256_hex(expected_swap),
            expected_swap,
        )
    assert expected_asc != expected_swap


def test_two_extension_stored_object_differs_from_each_single_extension():
    """Both-extension stored bytes differ from applying only Lo or only Hi."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    both = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    only_a = payload + token_a.encode("utf-8")
    only_b = payload + token_b.encode("utf-8")
    swapped = payload + token_b.encode("utf-8") + token_a.encode("utf-8")
    distinct = {both, swapped, only_a, only_b}
    assert len(distinct) == 4
    with workspace() as ws_both:
        ws_both.init_repo()
        _register_pair(
            ws_both, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        result = clean_bytes(ws_both, payload)
        require_success(result)
        require_object_bytes(
            default_lfs_store_root(ws_both), sha256_hex(both), both
        )
    with workspace() as ws_a:
        ws_a.init_repo()
        name = f"lo{token()}"
        clean_a, smudge_a = append_token_transform_scripts(ws_a, token_a)
        register_transform_extension(
            ws_a, name=name, priority=lo, clean_cmd=clean_a, smudge_cmd=smudge_a
        )
        result = clean_bytes(ws_a, payload)
        require_success(result)
        require_object_bytes(
            default_lfs_store_root(ws_a), sha256_hex(only_a), only_a
        )
    with workspace() as ws_b:
        ws_b.init_repo()
        name = f"hi{token()}"
        clean_b, smudge_b = append_token_transform_scripts(ws_b, token_b)
        register_transform_extension(
            ws_b, name=name, priority=hi, clean_cmd=clean_b, smudge_cmd=smudge_b
        )
        result = clean_bytes(ws_b, payload)
        require_success(result)
        require_object_bytes(
            default_lfs_store_root(ws_b), sha256_hex(only_b), only_b
        )
    print(
        f"lens both={len(both)} only_a={len(only_a)} only_b={len(only_b)} "
        f"swap={len(swapped)}"
    )


# ---------------------------------------------------------------------------
# F. Smudge reverses clean order; pointer carries extra metadata lines
# ---------------------------------------------------------------------------


def test_smudge_reverses_clean_extension_order_and_restores_working_tree_bytes():
    """Smudge of a two-extension pointer restores the original working-tree bytes."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    stored = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    with workspace() as ws:
        ws.init_repo()
        _register_pair(
            ws, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        cleaned = clean_bytes(ws, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, stored)
        require_object_bytes(
            default_lfs_store_root(ws), sha256_hex(stored), stored
        )
        smudged = smudge_bytes(ws, document)
        print(
            f"smudge exit={smudged.returncode} out_len={len(smudged.stdout)} "
            f"payload_len={len(payload)}"
        )
        require_success(smudged)
        assert smudged.stdout == payload, (
            "smudge did not restore original working-tree bytes "
            f"(got {smudged.stdout!r})"
        )
        assert smudged.stdout != stored


def test_smudge_of_already_written_pointer_restores_bytes_after_only_priority_numbers_swap():
    """After only swapping priority numbers, smudge still follows the written pointer."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    stored = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    with workspace() as ws:
        ws.init_repo()
        name_lo, name_hi, *_ = _register_pair(
            ws, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        cleaned = clean_bytes(ws, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, stored)
        require_object_bytes(
            default_lfs_store_root(ws), sha256_hex(stored), stored
        )
        require_git_config_set(
            ws, f"lfs.extension.{name_lo}.priority", str(hi), local=True
        )
        require_git_config_set(
            ws, f"lfs.extension.{name_hi}.priority", str(lo), local=True
        )
        smudged = smudge_bytes(ws, document)
        print(
            f"swap-then-smudge exit={smudged.returncode} "
            f"out_len={len(smudged.stdout)}"
        )
        require_success(smudged)
        assert smudged.stdout == payload, (
            "smudge after swapping only priority numbers did not restore "
            f"original bytes (got {smudged.stdout!r})"
        )


def test_clean_records_per_extension_metadata_lines_on_pointer():
    """A two-extension clean leaves non-core pointer lines; a no-extension clean does not."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    stored = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    with workspace() as with_ext:
        with_ext.init_repo()
        _register_pair(
            with_ext, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        cleaned = clean_bytes(with_ext, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, stored)
        extra = pointer_non_core_pairs(document)
        print(f"with-ext extra_n={len(extra)}")
        assert extra, (
            "two-extension pointer had no non-core metadata lines after "
            "removing version/oid/size"
        )
    with workspace() as none:
        none.init_repo()
        cleaned = clean_bytes(none, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, payload)
        extra_none = pointer_non_core_pairs(document)
        print(f"no-ext extra_n={len(extra_none)}")
        assert not extra_none, (
            "no-extension pointer still had non-core lines: "
            f"{extra_none!r}"
        )


def test_extensions_receive_content_bytes_not_the_pointer_document():
    """Each clean extension sees working-tree/pipeline bytes, not the pointer."""
    payload = _payload()
    token_a = f"A{token()}"
    token_b = f"B{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    stored = payload + token_a.encode("utf-8") + token_b.encode("utf-8")
    mid = payload + token_a.encode("utf-8")
    with workspace() as ws:
        ws.init_repo()
        _name_lo, _name_hi, clean_a, clean_b, *_ = _register_pair(
            ws, lo=lo, hi=hi, token_a=token_a, token_b=token_b
        )
        cleaned = clean_bytes(ws, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, stored)
        first = extension_command_stdin(clean_a)
        second = extension_command_stdin(clean_b)
        print(
            f"ext0_len={len(first)} ext1_len={len(second)} "
            f"ptr_len={len(document)}"
        )
        assert first == payload, (
            "first clean extension did not receive the working-tree bytes"
        )
        assert second == mid, (
            "second clean extension did not receive the previous extension output"
        )
        assert first != document
        assert second != document
        assert not pointer_matches_digest_and_size(
            first, digest=sha256_hex(stored), size=len(stored)
        )


# ---------------------------------------------------------------------------
# G. git orbulk ext lists registered extension names
# ---------------------------------------------------------------------------


def test_ext_lists_registered_extension_names():
    """ext names each registered extension; renaming changes the listing."""
    name_a = f"ex{token()}"
    name_b = f"ex{token()}"
    name_c = f"ex{token()}"
    lo, hi = priority_pair_numeric_not_lexicographic()
    with workspace() as empty:
        empty.init_repo()
        none = empty.invoke(["ext"])
        print(f"empty ext exit={none.returncode}")
        require_success(none)
        empty_text = none.stdout_text + none.stderr_text
        stripped_empty = strip_listing_covariates(
            empty_text, [str(empty.path)]
        )
    with workspace() as ws:
        ws.init_repo()
        clean_a, smudge_a = append_token_transform_scripts(ws, f"A{token()}")
        clean_b, smudge_b = append_token_transform_scripts(ws, f"B{token()}")
        register_transform_extension(
            ws, name=name_a, priority=lo, clean_cmd=clean_a, smudge_cmd=smudge_a
        )
        register_transform_extension(
            ws, name=name_b, priority=hi, clean_cmd=clean_b, smudge_cmd=smudge_b
        )
        listed = ws.invoke_via_git(["ext"])
        text = require_ext_listing_names(listed, name_a, name_b)
        stripped = strip_listing_covariates(
            text, [str(ws.path), clean_a, clean_b, smudge_a, smudge_b]
        )
        print(f"listed names={name_a!r},{name_b!r}")
        assert stripped != stripped_empty
        assert name_a not in empty_text
        assert name_b not in empty_text
    with workspace() as renamed:
        renamed.init_repo()
        clean_a, smudge_a = append_token_transform_scripts(
            renamed, f"A{token()}"
        )
        register_transform_extension(
            renamed,
            name=name_c,
            priority=lo,
            clean_cmd=clean_a,
            smudge_cmd=smudge_a,
        )
        listed_c = renamed.invoke_via_git(["ext"])
        text_c = require_ext_listing_names(listed_c, name_c)
        assert name_a not in text_c
        assert name_c not in text


# ---------------------------------------------------------------------------
# H. Unlaunchable selected path fails; unknown standalone still batches
# ---------------------------------------------------------------------------


def test_selected_custom_agent_with_unlaunchable_path_fails_transfer():
    """A selected custom agent whose path cannot launch fails download; no GET."""
    payload = _payload()
    name = _agent_name()
    with named_transfer_batch_server(select=name, payloads=[payload]) as svc:
        with workspace() as live:
            probe = install_json_path_agent(live)
            digest = _setup_tracked(live, svc.url, payload)
            _bind_agent(live, name, probe.path)
            seed_agent_payload(probe, payload)
            remove_stored_object(live, digest)
            ok = live.invoke_via_git(["fetch"])
            assert_success(ok)
            assert_object_bytes(default_lfs_store_root(live), digest, payload)
            assert_agent_was_launched(probe)
            print(f"live download ok name={name!r}")
            n = len(svc.records)
        with workspace() as ws:
            digest = _setup_tracked(ws, svc.url, payload)
            missing = unlaunchable_process_path(ws)
            _bind_agent(ws, name, missing)
            remove_stored_object(ws, digest)
            assert_object_absent(default_lfs_store_root(ws), digest)
            failed = ws.invoke_via_git(["fetch"])
            print(f"unlaunchable download exit={failed.returncode}")
            assert_invalid_unlike_success(ok, failed)
            assert_object_absent(default_lfs_store_root(ws), digest)
            assert_no_get_of_object_action(
                svc.records[n:], svc.action_path(digest)
            )


def test_unknown_standalone_agent_name_is_ignored_and_ordinary_batch_still_transfers():
    """An unknown standalone name is ignored; ordinary batch still PUTs."""
    payload = _payload()
    unk = f"unk{token()}"
    with storing_batch_server() as svc:
        with workspace() as ws:
            digest = _setup_tracked(ws, svc.url, payload)
            configure_standalone_transfer_agent(ws, unk)
            result = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"unknown standalone exit={result.returncode} n={len(svc.records)}")
            assert_success(result)
            assert_batch_post(svc.records, operation="upload")
            assert_put_of(svc.records, payload)


def test_standalone_registered_agent_with_unlaunchable_path_fails_transfer():
    """A registered standalone name with an unlaunchable path fails; no PUT."""
    payload = _payload()
    name = _agent_name()
    with storing_batch_server() as svc:
        with workspace() as live:
            probe = install_json_path_agent(live)
            digest = _setup_tracked(live, svc.url, payload)
            _bind_agent(live, name, probe.path)
            configure_standalone_transfer_agent(live, name)
            ok = live.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            assert_success(ok)
            assert_agent_was_launched(probe)
            assert_agent_wrote_payload(probe, payload)
            n = len(svc.records)
            print(f"live standalone ok extra_until={n}")
        with workspace() as ws:
            digest = _setup_tracked(ws, svc.url, payload)
            missing = unlaunchable_process_path(ws)
            _bind_agent(ws, name, missing)
            configure_standalone_transfer_agent(ws, name)
            failed = ws.invoke_via_git(
                ["push", "--object-id", "origin", digest]
            )
            print(f"standalone unlaunchable exit={failed.returncode}")
            assert_invalid_unlike_success(ok, failed)
            assert_no_put_of(svc.records[n:], payload)


# ---------------------------------------------------------------------------
# I. Extension failure during clean/smudge fails the filter
# ---------------------------------------------------------------------------


def test_extension_failure_during_clean_fails_the_filter():
    """A failing clean extension fails the filter; a live success still stores."""
    payload = _payload()
    token_a = f"A{token()}"
    lo, _hi = priority_pair_numeric_not_lexicographic()
    transformed = payload + token_a.encode("utf-8")
    with workspace() as ok_ws:
        ok_ws.init_repo()
        name = f"ex{token()}"
        clean_ok, smudge_ok = append_token_transform_scripts(ok_ws, token_a)
        register_transform_extension(
            ok_ws,
            name=name,
            priority=lo,
            clean_cmd=clean_ok,
            smudge_cmd=smudge_ok,
        )
        ok = clean_bytes(ok_ws, payload)
        require_success(ok)
        require_object_bytes(
            default_lfs_store_root(ok_ws),
            sha256_hex(transformed),
            transformed,
        )
        print(f"clean success stored {sha256_hex(transformed)}")
    with workspace() as ws:
        ws.init_repo()
        name = f"ex{token()}"
        fail = failing_extension_command(ws)
        _clean_ok, smudge_ok = append_token_transform_scripts(ws, token_a)
        register_transform_extension(
            ws, name=name, priority=lo, clean_cmd=fail, smudge_cmd=smudge_ok
        )
        dirty = clean_bytes(ws, payload)
        print(f"clean fail exit={dirty.returncode}")
        require_invalid_unlike_success(ok, dirty)
        require_object_absent(
            default_lfs_store_root(ws), sha256_hex(transformed)
        )
        assert not pointer_matches_digest_and_size(
            dirty.stdout,
            digest=sha256_hex(transformed),
            size=len(transformed),
        )
        configure_lfs_clean_filter(ws)
        rel = _rel()
        track_pattern(ws, f"*{Path(rel).suffix}")
        ws.write(rel, payload)
        added = ws.git(["add", "--", rel, ".gitattributes"])
        print(f"git add fail exit={added.returncode}")
        assert added.returncode != 0, (
            "git add succeeded while the clean extension failed"
        )
        require_object_absent(
            default_lfs_store_root(ws), sha256_hex(transformed)
        )


def test_extension_failure_during_smudge_fails_the_filter():
    """A failing smudge extension fails smudge; live success still restores bytes."""
    payload = _payload()
    token_a = f"A{token()}"
    lo, _hi = priority_pair_numeric_not_lexicographic()
    transformed = payload + token_a.encode("utf-8")
    with workspace() as ok_ws:
        ok_ws.init_repo()
        name = f"ex{token()}"
        clean_ok, smudge_ok = append_token_transform_scripts(ok_ws, token_a)
        register_transform_extension(
            ok_ws,
            name=name,
            priority=lo,
            clean_cmd=clean_ok,
            smudge_cmd=smudge_ok,
        )
        cleaned = clean_bytes(ok_ws, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, transformed)
        ok = smudge_bytes(ok_ws, document)
        require_success(ok)
        assert ok.stdout == payload
        print("smudge success restored payload")
    with workspace() as ws:
        ws.init_repo()
        name = f"ex{token()}"
        clean_ok, _smudge_ok = append_token_transform_scripts(ws, token_a)
        fail = failing_extension_command(ws)
        register_transform_extension(
            ws, name=name, priority=lo, clean_cmd=clean_ok, smudge_cmd=fail
        )
        cleaned = clean_bytes(ws, payload)
        require_success(cleaned)
        document = _pointer_for_stored(cleaned, transformed)
        dirty = smudge_bytes(ws, document)
        print(f"smudge fail exit={dirty.returncode}")
        require_invalid_unlike_success(ok, dirty)
        assert dirty.stdout != payload
        assert dirty.stdout != transformed


# ---------------------------------------------------------------------------
# J. Negative control
# ---------------------------------------------------------------------------


def test_custom_transfer_ext_or_file_remote_fails_when_binary_removed_from_path():
    """Removing the product from PATH fails ext after a live successful listing."""
    name = f"ex{token()}"
    lo, _hi = priority_pair_numeric_not_lexicographic()
    with workspace() as present:
        present.init_repo()
        clean_a, smudge_a = append_token_transform_scripts(
            present, f"A{token()}"
        )
        register_transform_extension(
            present,
            name=name,
            priority=lo,
            clean_cmd=clean_a,
            smudge_cmd=smudge_a,
        )
        ok = present.invoke_via_git(["ext"])
        require_ext_listing_names(ok, name)
        print(f"present ext exit={ok.returncode}")
    with workspace() as missing:
        missing.init_repo()
        clean_a, smudge_a = append_token_transform_scripts(
            missing, f"A{token()}"
        )
        register_transform_extension(
            missing,
            name=name,
            priority=lo,
            clean_cmd=clean_a,
            smudge_cmd=smudge_a,
        )
        hidden = path_without_product_bin(missing.env)
        failed = missing.invoke_via_git(
            ["ext"], env_updates={"PATH": hidden}
        )
        print(f"absent ext exit={failed.returncode} hidden={hidden!r}")
        assert failed.returncode != 0, (
            "ext succeeded after the product binary was removed from PATH"
        )
        assert (failed.returncode, failed.stdout, failed.stderr) != (
            ok.returncode,
            ok.stdout,
            ok.stderr,
        ), "absent-binary ext was not distinguishable from a successful ext"
