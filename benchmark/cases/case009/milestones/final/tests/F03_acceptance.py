# feature: F03
"""Pointer format and pointer-plumbing acceptance tests.

PRD: FP-03. Assertions stay at the PRD's precision: canonical key/value
shape, independent SHA-256 hex, empty passthrough, executable-bit
contrast, ordinary vs strict check, leftover pre-release version
ordinary-ok/strict-valid-not-canonical contrast, extension-line order,
compare relation classes after covariate stripping, and invocation
refusals. The current v1 version-identifier string, hash-method labels,
exit-code numbers, and banner wording are not pinned. The leftover
pre-release identifier is used only as Interface Contract substitution
input, not as a generate-output golden.
"""

from __future__ import annotations

from _harness import token
from _helpers import (
    assert_smudge_recognizes,
    check_pointer,
    compare_class_observation,
    compare_pointer,
    configure_lfs_clean_filter,
    contract_still_readable_legacy_pre_release_version_identifier,
    extract_generated_pointer_document,
    join_pointer_kv,
    object_id_field_key,
    object_id_field_value,
    parse_pointer_kv,
    path_without_product_bin,
    require_distinct_classes,
    require_generated_pointer_shape,
    reorder_required_size_before_object_id,
    require_git_config_set,
    require_invalid_check_invocation,
    require_pointer_check_ok,
    require_pointer_invalid,
    require_shared_class,
    require_smudge_not_recognized_as_pointer,
    require_smudge_recognized_unlike_independent_failure,
    require_smudge_recognizes,
    require_success,
    require_valid_not_canonical_stripped,
    run_pointer,
    sha256_hex,
    smudge_bytes,
    stage_mode,
    well_formed_oversize_pointer,
)


def _payload() -> bytes:
    return f"body-{token()}-X".encode("utf-8")


def _write_payload(ws, payload: bytes, suffix: str = "") -> str:
    rel = f"f_{token()}{suffix}"
    ws.write(rel, payload)
    return rel


def _generate_doc(ws, payload: bytes, *, rel: str | None = None, via_git: bool = True) -> bytes:
    path = rel or _write_payload(ws, payload)
    result = run_pointer(ws, [f"--file={path}"], via_git=via_git)
    digest = sha256_hex(payload)
    document = extract_generated_pointer_document(
        result, digest=digest, size=len(payload)
    )
    print(
        f"generate file={path!r} exit={result.returncode} "
        f"doc_len={len(document)} digest={digest}"
    )
    return document


def _not_a_pointer() -> bytes:
    return f"not-pointer-{token()}\n".encode("utf-8")


def _oversize_nonpointer() -> bytes:
    chunk = f"not-pointer-{token()}-".encode("utf-8")
    document = chunk * (1 + 1024 // max(len(chunk), 1))
    assert len(document) > 1024
    return document


def _version_canonicalization_variants(value: str) -> list[str]:
    """Mutations that exact string equality rejects and folding/URL-parse would accept."""
    variants: list[str] = []
    upper = value.upper()
    if upper != value:
        variants.append(upper)
    lower = value.lower()
    if lower != value:
        variants.append(lower)
    if "://" in value:
        slashed = value.rstrip("/") + "/"
        if slashed != value:
            variants.append(slashed)
        if value.startswith("https://"):
            swapped = "http://" + value[len("https://"):]
            if swapped != value:
                variants.append(swapped)
        elif value.startswith("http://"):
            swapped = "https://" + value[len("http://"):]
            if swapped != value:
                variants.append(swapped)
    unique = list(dict.fromkeys(variants))
    assert unique, (
        "version identifier had no case-fold or URL-shape variant to reject"
    )
    return unique


def _replace_version(document: bytes, new_value: str) -> bytes:
    pairs = parse_pointer_kv(document)
    assert pairs and pairs[0][0] == "version"
    mutated = [(pairs[0][0], new_value), *pairs[1:]]
    return join_pointer_kv(mutated)


def _constructed_extension_documents(
    generated: bytes, *, digest: str
) -> tuple[bytes, bytes]:
    """Build canonical and reordered pointers that already have extension lines.

    Starts from a generated pointer (no generate-with-extension duty). Adds a
    protocol extension-line key. Does not look up the object-id key spelling.
    """
    pairs = parse_pointer_kv(generated)
    assert pairs and pairs[0][0] == "version"
    object_id_value = object_id_field_value(pairs, digest=digest)
    object_id_key = object_id_field_key(pairs, digest=digest)
    ext_key = f"ext-0-x{token()}"
    ext_pair = (ext_key, object_id_value)
    version = pairs[0]
    rest = list(pairs[1:])
    canonical_rest = sorted([*rest, ext_pair], key=lambda item: item[0])
    canonical = join_pointer_kv([version, *canonical_rest])
    assert rest, "generated pointer has no keys after version"
    reordered = join_pointer_kv([version, rest[0], ext_pair, *rest[1:]])
    assert reordered != canonical, (
        "reordered extension-line document matched the canonical key order"
    )
    extras = [
        (key, value)
        for key, value in parse_pointer_kv(canonical)
        if key not in ("version", object_id_key, "size")
    ]
    assert extras, "constructed pointer has no protocol extension-line keys"
    return canonical, reordered


def _prepare_smudge_repo(ws) -> None:
    ws.init_repo()
    require_git_config_set(ws, "lfs.url", "http://127.0.0.1:1", local=True)


def _compare_strip(ws, rel_a, rel_b, payload_a, payload_b, ptr_a, ptr_b, malformed) -> list[str]:
    tokens = [
        str(rel_a),
        str(rel_b),
        str(ws.resolve(rel_a)),
        str(ws.resolve(rel_b)),
        payload_a.decode("utf-8"),
        payload_b.decode("utf-8"),
        ptr_a.decode("utf-8"),
        ptr_b.decode("utf-8"),
        sha256_hex(payload_a),
        sha256_hex(payload_b),
        str(len(payload_a)),
        str(len(payload_b)),
        malformed.decode("utf-8"),
    ]
    return tokens


def test_pointer_generate_is_deterministic_kv_document(isolated_ws):
    payload = _payload()
    first = _generate_doc(isolated_ws, payload)
    second = _generate_doc(isolated_ws, payload)
    print(f"first={first!r}\nsecond={second!r}")
    require_generated_pointer_shape(
        first, digest=sha256_hex(payload), size=len(payload)
    )
    assert first == second, (
        "two generates of the same file did not produce one canonical encoding"
    )
    other = _payload()
    assert other != payload
    other_doc = _generate_doc(isolated_ws, other)
    other_pairs = require_generated_pointer_shape(
        other_doc, digest=sha256_hex(other), size=len(other)
    )
    first_pairs = parse_pointer_kv(first)
    first_hex = object_id_field_value(
        first_pairs, digest=sha256_hex(payload)
    ).rsplit(":", 1)[-1]
    other_hex = object_id_field_value(
        other_pairs, digest=sha256_hex(other)
    ).rsplit(":", 1)[-1]
    assert first_hex != other_hex, (
        "different file bytes produced the same object-id hex digest"
    )


def test_pointer_generate_version_first_keys_sorted_unix_nl_under_1024(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    pairs = require_generated_pointer_shape(
        document, digest=sha256_hex(payload), size=len(payload)
    )
    keys = [key for key, _ in pairs]
    print(f"keys={keys} len={len(document)}")
    assert keys[0] == "version"
    assert "size" in keys
    object_id_field_value(pairs, digest=sha256_hex(payload))
    assert b"\r" not in document
    assert len(document) < 1024
    assert payload not in document, (
        "generated pointer was the original file bytes, not a key/value document"
    )


def test_generated_pointer_passes_ordinary_and_strict_check_file_and_stdin(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    require_generated_pointer_shape(
        document, digest=sha256_hex(payload), size=len(payload)
    )
    for via in ("file", "stdin"):
        ordinary = check_pointer(isolated_ws, document, via=via)
        print(f"ordinary via={via} exit={ordinary.returncode}")
        require_pointer_check_ok(ordinary)
        strict = check_pointer(isolated_ws, document, strict=True, via=via)
        print(f"strict via={via} exit={strict.returncode}")
        require_pointer_check_ok(strict)


def test_pointer_generate_via_direct_binary(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload, via_git=False)
    pairs = require_generated_pointer_shape(
        document, digest=sha256_hex(payload), size=len(payload)
    )
    digest = object_id_field_value(
        pairs, digest=sha256_hex(payload)
    ).rsplit(":", 1)[-1]
    print(f"direct-binary digest={digest}")
    assert digest == sha256_hex(payload)


def test_generate_writes_stable_current_version_identifier(isolated_ws):
    payload_a = _payload()
    payload_b = _payload()
    assert payload_a != payload_b
    doc_a = _generate_doc(isolated_ws, payload_a)
    doc_b = _generate_doc(isolated_ws, payload_b)
    version_a = parse_pointer_kv(doc_a)[0]
    version_b = parse_pointer_kv(doc_b)[0]
    assert version_a[0] == "version" and version_b[0] == "version"
    print(f"version_a_len={len(version_a[1])} version_b_len={len(version_b[1])}")
    assert version_a[1] == version_b[1], (
        "newly written pointers did not share one current version identifier"
    )
    assert version_a[1], "version identifier is empty"


def test_legacy_pre_release_version_ordinary_ok_strict_fails_unlike_invalid(isolated_ws):
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    require_generated_pointer_shape(
        canonical, digest=sha256_hex(payload), size=len(payload)
    )
    current = parse_pointer_kv(canonical)[0][1]
    leftover = contract_still_readable_legacy_pre_release_version_identifier()
    print(
        f"current_id_len={len(current)} leftover_id_len={len(leftover)} "
        f"same={current == leftover}"
    )
    assert current != leftover, (
        "newly written pointer used the Contract still-readable leftover "
        "pre-release version identifier instead of the current v1 identifier"
    )
    ordinary_ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ordinary_ok)
    strict_ok = check_pointer(isolated_ws, canonical, strict=True)
    require_pointer_check_ok(strict_ok)
    leftover_doc = _replace_version(canonical, leftover)
    assert leftover_doc != canonical
    ordinary_leftover = check_pointer(isolated_ws, leftover_doc)
    print(f"leftover ordinary exit={ordinary_leftover.returncode}")
    require_pointer_check_ok(ordinary_leftover)
    unparseable = _not_a_pointer()
    invalid = check_pointer(isolated_ws, unparseable, strict=True)
    require_pointer_invalid(invalid, unlike=strict_ok)
    strict_leftover = check_pointer(isolated_ws, leftover_doc, strict=True)
    print(f"leftover strict exit={strict_leftover.returncode}")
    require_valid_not_canonical_stripped(
        strict_leftover,
        unlike_ok=strict_ok,
        unlike_invalid=invalid,
        input_documents=(
            leftover_doc,
            canonical,
            unparseable,
            leftover.encode("utf-8"),
        ),
    )


def test_version_identifier_exact_string_equality_no_casefold_or_url_parse(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    baseline = check_pointer(isolated_ws, document)
    require_pointer_check_ok(baseline)
    version_value = parse_pointer_kv(document)[0][1]
    for variant in _version_canonicalization_variants(version_value):
        mutated = _replace_version(document, variant)
        print(f"variant_len={len(variant)} mutated_len={len(mutated)}")
        refused = check_pointer(isolated_ws, mutated)
        require_pointer_invalid(refused, unlike=baseline)


def test_empty_file_generate_is_empty_pointer_not_hashed_body(isolated_ws):
    nonempty = _payload()
    nonempty_doc = _generate_doc(isolated_ws, nonempty)
    assert nonempty_doc, "live baseline generate of nonempty content was empty"
    require_generated_pointer_shape(
        nonempty_doc, digest=sha256_hex(nonempty), size=len(nonempty)
    )
    empty_rel = _write_payload(isolated_ws, b"")
    result = run_pointer(isolated_ws, [f"--file={empty_rel}"])
    document = extract_generated_pointer_document(
        result, digest=sha256_hex(b""), size=0
    )
    print(f"empty generate len={len(document)} exit={result.returncode}")
    assert document == b"", (
        "empty file was rewritten into a hashed pointer body: "
        f"{document!r}"
    )
    assert parse_pointer_kv(document) == []


def test_empty_pointer_document_passes_ordinary_and_strict_check(isolated_ws):
    empty = b""
    ordinary = check_pointer(isolated_ws, empty)
    print(f"empty ordinary exit={ordinary.returncode}")
    require_pointer_check_ok(ordinary)
    strict = check_pointer(isolated_ws, empty, strict=True)
    print(f"empty strict exit={strict.returncode}")
    require_pointer_check_ok(strict)
    stdin_ordinary = check_pointer(isolated_ws, empty, via="stdin")
    require_pointer_check_ok(stdin_ordinary)
    stdin_strict = check_pointer(isolated_ws, empty, strict=True, via="stdin")
    require_pointer_check_ok(stdin_strict)


def test_empty_clean_stdout_is_passthrough(isolated_ws):
    isolated_ws.init_repo()
    nonempty = _payload()
    clean_ne = isolated_ws.invoke_via_git(["clean"], stdin=nonempty)
    print(f"nonempty clean exit={clean_ne.returncode} len={len(clean_ne.stdout)}")
    require_success(clean_ne)
    require_generated_pointer_shape(
        clean_ne.stdout, digest=sha256_hex(nonempty), size=len(nonempty)
    )
    clean_empty = isolated_ws.invoke_via_git(["clean"], stdin=b"")
    print(f"empty clean exit={clean_empty.returncode} len={len(clean_empty.stdout)}")
    require_success(clean_empty)
    assert clean_empty.stdout == b"", (
        "empty clean stdin was rewritten into a hashed pointer body: "
        f"{clean_empty.stdout!r}"
    )


def test_pointer_blob_preserves_executable_bit_contrast(isolated_ws):
    isolated_ws.init_repo()
    configure_lfs_clean_filter(isolated_ws)
    payload = _payload()
    isolated_ws.write(".gitattributes", "*.bin filter=lfs diff=lfs merge=lfs -text\n")
    exec_rel = f"e_{token()}.bin"
    plain_rel = f"p_{token()}.bin"
    isolated_ws.write(exec_rel, payload)
    isolated_ws.write(plain_rel, payload)
    isolated_ws.resolve(exec_rel).chmod(0o755)
    isolated_ws.resolve(plain_rel).chmod(0o644)
    added_plain = isolated_ws.git(["add", "--", plain_rel])
    assert added_plain.returncode == 0, (
        f"git add {plain_rel!r} failed: {added_plain.stderr_text}"
    )
    added_exec = isolated_ws.git(["add", "--", exec_rel])
    assert added_exec.returncode == 0, (
        f"git add {exec_rel!r} failed: {added_exec.stderr_text}"
    )
    plain_mode = stage_mode(isolated_ws, plain_rel)
    exec_mode = stage_mode(isolated_ws, exec_rel)
    print(f"plain_mode={plain_mode} exec_mode={exec_mode}")
    assert int(plain_mode, 8) & 0o111 == 0, (
        f"non-executable working-tree file staged with executable mode {plain_mode}"
    )
    assert int(exec_mode, 8) & 0o111, (
        f"executable working-tree file staged without executable mode {exec_mode}"
    )
    assert plain_mode != exec_mode
    digest = sha256_hex(payload)
    for rel, mode in ((plain_rel, plain_mode), (exec_rel, exec_mode)):
        staged = isolated_ws.git(["ls-files", "--stage", "--", rel])
        assert staged.returncode == 0 and staged.stdout_text.strip()
        blob = staged.stdout_text.split()[1]
        shown = isolated_ws.git(["cat-file", "-p", blob])
        assert shown.returncode == 0, (
            f"git cat-file -p failed for {rel!r}: {shown.stderr_text}"
        )
        print(f"{rel} mode={mode} blob_len={len(shown.stdout)}")
        assert shown.stdout != payload, (
            f"Git blob for {rel!r} stored the working-tree bytes, not a pointer"
        )
        require_generated_pointer_shape(
            shown.stdout, digest=digest, size=len(payload)
        )


def test_canonical_extension_lines_pass_ordinary_and_strict_check(isolated_ws):
    payload = _payload()
    generated = _generate_doc(isolated_ws, payload)
    digest = sha256_hex(payload)
    document, _reordered = _constructed_extension_documents(
        generated, digest=digest
    )
    pairs = parse_pointer_kv(document)
    print(
        f"extension keys={[key for key, _ in pairs[1:]]} len={len(document)}"
    )
    assert pairs and pairs[0][0] == "version"
    object_id_field_value(pairs, digest=digest)
    after = [key for key, _ in pairs[1:]]
    assert after == sorted(after), (
        "constructed extension-line keys after version are not canonical order: "
        f"{after!r}"
    )
    assert len(document) < 1024
    ordinary = check_pointer(isolated_ws, document)
    require_pointer_check_ok(ordinary)
    strict = check_pointer(isolated_ws, document, strict=True)
    require_pointer_check_ok(strict)


def test_reordered_extension_lines_ordinary_ok_strict_fails_unlike_invalid(isolated_ws):
    payload = _payload()
    generated = _generate_doc(isolated_ws, payload)
    digest = sha256_hex(payload)
    canonical, reordered = _constructed_extension_documents(
        generated, digest=digest
    )
    assert reordered != canonical
    ordinary_ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ordinary_ok)
    ordinary_reordered = check_pointer(isolated_ws, reordered)
    print(f"reordered ordinary exit={ordinary_reordered.returncode}")
    require_pointer_check_ok(ordinary_reordered)
    strict_ok = check_pointer(isolated_ws, canonical, strict=True)
    require_pointer_check_ok(strict_ok)
    unparseable = _not_a_pointer()
    invalid = check_pointer(isolated_ws, unparseable, strict=True)
    require_pointer_invalid(invalid, unlike=strict_ok)
    strict_reordered = check_pointer(isolated_ws, reordered, strict=True)
    print(f"reordered strict exit={strict_reordered.returncode}")
    require_valid_not_canonical_stripped(
        strict_reordered,
        unlike_ok=strict_ok,
        unlike_invalid=invalid,
        input_documents=(reordered, canonical, unparseable),
    )


def test_check_rejects_unparseable_truncated_and_missing_keys(isolated_ws):
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ok)
    ok_stdin = check_pointer(isolated_ws, canonical, via="stdin")
    require_pointer_check_ok(ok_stdin)

    unparseable = _not_a_pointer()
    refused_unparseable = check_pointer(isolated_ws, unparseable)
    print(f"unparseable exit={refused_unparseable.returncode}")
    require_pointer_invalid(refused_unparseable, unlike=ok)

    lines = canonical.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    assert len(lines) >= 2
    truncated = b"\n".join(lines[:-1]) + b"\n"
    refused_truncated = check_pointer(isolated_ws, truncated)
    print(f"truncated exit={refused_truncated.returncode}")
    require_pointer_invalid(refused_truncated, unlike=ok)

    pairs = parse_pointer_kv(canonical)
    digest = sha256_hex(payload)
    object_id_key = object_id_field_key(pairs, digest=digest)
    by_key = {key: value for key, value in pairs}
    missing_size = join_pointer_kv(
        [("version", by_key["version"]), (object_id_key, by_key[object_id_key])]
    )
    refused_missing_size = check_pointer(isolated_ws, missing_size)
    print(f"missing size exit={refused_missing_size.returncode}")
    require_pointer_invalid(refused_missing_size, unlike=ok)

    missing_version = join_pointer_kv(
        [(object_id_key, by_key[object_id_key]), ("size", by_key["size"])]
    )
    refused_missing_version = check_pointer(isolated_ws, missing_version)
    print(f"missing version exit={refused_missing_version.returncode}")
    require_pointer_invalid(refused_missing_version, unlike=ok)

    oversize = _oversize_nonpointer()
    refused_oversize = check_pointer(isolated_ws, oversize)
    print(f"oversize len={len(oversize)} exit={refused_oversize.returncode}")
    require_pointer_invalid(refused_oversize, unlike=ok)

    well_formed_oversize = well_formed_oversize_pointer(
        canonical, digest=digest
    )
    refused_well_formed_oversize = check_pointer(
        isolated_ws, well_formed_oversize
    )
    print(
        f"well-formed oversize len={len(well_formed_oversize)} "
        f"exit={refused_well_formed_oversize.returncode}"
    )
    require_pointer_invalid(refused_well_formed_oversize, unlike=ok)


def test_check_rejects_required_key_reorder_as_invalid_not_noncanonical(isolated_ws):
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ok)
    reordered = reorder_required_size_before_object_id(
        canonical, digest=sha256_hex(payload)
    )
    ordinary = check_pointer(isolated_ws, reordered)
    print(f"required-key reorder ordinary exit={ordinary.returncode}")
    require_pointer_invalid(ordinary, unlike=ok)
    stdin_ordinary = check_pointer(isolated_ws, reordered, via="stdin")
    require_pointer_invalid(stdin_ordinary, unlike=ok)


def test_crlf_ordinary_ok_strict_fails_unlike_invalid(isolated_ws):
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    ordinary_ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ordinary_ok)
    strict_ok = check_pointer(isolated_ws, canonical, strict=True)
    require_pointer_check_ok(strict_ok)
    crlf = canonical.replace(b"\n", b"\r\n")
    assert crlf != canonical
    ordinary_crlf = check_pointer(isolated_ws, crlf)
    print(f"crlf ordinary exit={ordinary_crlf.returncode}")
    require_pointer_check_ok(ordinary_crlf)
    unparseable = _not_a_pointer()
    invalid = check_pointer(isolated_ws, unparseable, strict=True)
    require_pointer_invalid(invalid, unlike=strict_ok)
    strict_crlf = check_pointer(isolated_ws, crlf, strict=True)
    print(f"crlf strict exit={strict_crlf.returncode}")
    require_valid_not_canonical_stripped(
        strict_crlf,
        unlike_ok=strict_ok,
        unlike_invalid=invalid,
        input_documents=(crlf, canonical, unparseable),
    )


def test_missing_final_newline_ordinary_ok_strict_fails_unlike_invalid(isolated_ws):
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    assert canonical.endswith(b"\n")
    ordinary_ok = check_pointer(isolated_ws, canonical)
    require_pointer_check_ok(ordinary_ok)
    strict_ok = check_pointer(isolated_ws, canonical, strict=True)
    require_pointer_check_ok(strict_ok)
    missing_nl = canonical[:-1]
    ordinary_missing = check_pointer(isolated_ws, missing_nl)
    print(f"missing-nl ordinary exit={ordinary_missing.returncode}")
    require_pointer_check_ok(ordinary_missing)
    unparseable = _not_a_pointer()
    invalid = check_pointer(isolated_ws, unparseable, strict=True)
    require_pointer_invalid(invalid, unlike=strict_ok)
    strict_missing = check_pointer(isolated_ws, missing_nl, strict=True)
    print(f"missing-nl strict exit={strict_missing.returncode}")
    require_valid_not_canonical_stripped(
        strict_missing,
        unlike_ok=strict_ok,
        unlike_invalid=invalid,
        input_documents=(missing_nl, canonical, unparseable),
    )


def test_smudge_recognizes_valid_pointer_not_passthrough(isolated_ws):
    _prepare_smudge_repo(isolated_ws)
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    unparseable = _not_a_pointer()
    unrecognized = smudge_bytes(isolated_ws, unparseable)
    print(
        f"unparseable smudge exit={unrecognized.returncode} "
        f"out_len={len(unrecognized.stdout)}"
    )
    hidden_path = path_without_product_bin(isolated_ws.env)
    independent = isolated_ws.invoke_via_git(
        ["smudge"], stdin=document, env_updates={"PATH": hidden_path}
    )
    print(
        f"independent-failure exit={independent.returncode} "
        f"stderr_len={len(independent.stderr)}"
    )
    result = smudge_bytes(isolated_ws, document)
    print(
        f"valid smudge exit={result.returncode} "
        f"stdout_len={len(result.stdout)} input_len={len(document)}"
    )
    assert_smudge_recognizes(result, document)
    require_smudge_recognized_unlike_independent_failure(
        result,
        document,
        unlike_independent_failure=independent,
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized,
        unparseable,
        unlike_recognized=result,
        recognized_input=document,
    )
    crlf = document.replace(b"\n", b"\r\n")
    independent_crlf = isolated_ws.invoke_via_git(
        ["smudge"], stdin=crlf, env_updates={"PATH": hidden_path}
    )
    crlf_result = smudge_bytes(isolated_ws, crlf)
    print(f"crlf smudge exit={crlf_result.returncode}")
    assert_smudge_recognizes(crlf_result, crlf)
    require_smudge_recognized_unlike_independent_failure(
        crlf_result,
        crlf,
        unlike_independent_failure=independent_crlf,
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized,
        unparseable,
        unlike_recognized=crlf_result,
        recognized_input=crlf,
    )


def test_smudge_passthrough_on_structural_invalid_and_oversize_nonpointer(isolated_ws):
    _prepare_smudge_repo(isolated_ws)
    payload = _payload()
    canonical = _generate_doc(isolated_ws, payload)
    recognized = smudge_bytes(isolated_ws, canonical)
    print(f"baseline smudge exit={recognized.returncode}")
    require_smudge_recognizes(recognized, canonical)
    assert_smudge_recognizes(recognized, canonical)

    unparseable = _not_a_pointer()
    unrecognized = smudge_bytes(isolated_ws, unparseable)
    print(
        f"unparseable smudge exit={unrecognized.returncode} "
        f"out={len(unrecognized.stdout)}"
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized,
        unparseable,
        unlike_recognized=recognized,
        recognized_input=canonical,
    )

    reordered = reorder_required_size_before_object_id(
        canonical, digest=sha256_hex(payload)
    )
    unrecognized_reorder = smudge_bytes(isolated_ws, reordered)
    print(f"reorder smudge exit={unrecognized_reorder.returncode}")
    require_smudge_not_recognized_as_pointer(
        unrecognized_reorder,
        reordered,
        unlike_recognized=recognized,
        recognized_input=canonical,
    )

    oversize = _oversize_nonpointer()
    unrecognized_oversize = smudge_bytes(isolated_ws, oversize)
    print(
        f"oversize smudge exit={unrecognized_oversize.returncode} "
        f"in={len(oversize)}"
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized_oversize,
        oversize,
        unlike_recognized=recognized,
        recognized_input=canonical,
    )

    pairs = parse_pointer_kv(canonical)
    digest = sha256_hex(payload)
    object_id_key = object_id_field_key(pairs, digest=digest)
    by_key = {key: value for key, value in pairs}
    missing_size = join_pointer_kv(
        [("version", by_key["version"]), (object_id_key, by_key[object_id_key])]
    )
    unrecognized_omit = smudge_bytes(isolated_ws, missing_size)
    print(
        f"omit-keys smudge exit={unrecognized_omit.returncode} "
        f"in={len(missing_size)}"
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized_omit,
        missing_size,
        unlike_recognized=recognized,
        recognized_input=canonical,
    )

    well_formed_oversize = well_formed_oversize_pointer(
        canonical, digest=digest
    )
    unrecognized_well_formed_oversize = smudge_bytes(
        isolated_ws, well_formed_oversize
    )
    print(
        f"well-formed oversize smudge "
        f"exit={unrecognized_well_formed_oversize.returncode} "
        f"in={len(well_formed_oversize)}"
    )
    require_smudge_not_recognized_as_pointer(
        unrecognized_well_formed_oversize,
        well_formed_oversize,
        unlike_recognized=recognized,
        recognized_input=canonical,
    )


def _assert_compare_three_classes(isolated_ws, *, via: str) -> None:
    payload_a = _payload()
    payload_b = _payload()
    assert payload_a != payload_b
    rel_a = _write_payload(isolated_ws, payload_a)
    rel_b = _write_payload(isolated_ws, payload_b)
    ptr_a = _generate_doc(isolated_ws, payload_a, rel=rel_a)
    ptr_b = _generate_doc(isolated_ws, payload_b, rel=rel_b)
    malformed = _not_a_pointer()
    strip = _compare_strip(
        isolated_ws, rel_a, rel_b, payload_a, payload_b, ptr_a, ptr_b, malformed
    )

    match_a = compare_pointer(isolated_ws, rel_a, ptr_a, via=via)
    match_b = compare_pointer(isolated_ws, rel_b, ptr_b, via=via)
    mismatch_ab = compare_pointer(isolated_ws, rel_a, ptr_b, via=via)
    mismatch_ba = compare_pointer(isolated_ws, rel_b, ptr_a, via=via)
    malformed_a = compare_pointer(isolated_ws, rel_a, malformed, via=via)
    malformed_b = compare_pointer(isolated_ws, rel_b, malformed, via=via)

    obs_match_a = compare_class_observation(match_a, strip_tokens=strip)
    obs_match_b = compare_class_observation(match_b, strip_tokens=strip)
    obs_mis_ab = compare_class_observation(mismatch_ab, strip_tokens=strip)
    obs_mis_ba = compare_class_observation(mismatch_ba, strip_tokens=strip)
    obs_mal_a = compare_class_observation(malformed_a, strip_tokens=strip)
    obs_mal_b = compare_class_observation(malformed_b, strip_tokens=strip)
    print(
        f"via={via} match={obs_match_a} {obs_match_b} "
        f"mismatch={obs_mis_ab} {obs_mis_ba} "
        f"malformed={obs_mal_a} {obs_mal_b}"
    )
    match = require_shared_class(obs_match_a, obs_match_b)
    mismatch = require_shared_class(obs_mis_ab, obs_mis_ba)
    malformed_cls = require_shared_class(obs_mal_a, obs_mal_b)
    require_distinct_classes(match, mismatch, malformed_cls)


def test_compare_three_classes_via_pointer_file_covariate_stripped(isolated_ws):
    _assert_compare_three_classes(isolated_ws, via="file")


def test_compare_three_classes_via_stdin_covariate_stripped(isolated_ws):
    _assert_compare_three_classes(isolated_ws, via="stdin")


def test_check_invocation_requires_exactly_one_source(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    rel = _write_payload(isolated_ws, document)
    clean = run_pointer(isolated_ws, ["--check", f"--file={rel}"])
    require_pointer_check_ok(clean)
    none = run_pointer(isolated_ws, ["--check"])
    print(f"check no-source exit={none.returncode}")
    require_invalid_check_invocation(clean, none)
    both = run_pointer(
        isolated_ws, ["--check", f"--file={rel}", "--stdin"], stdin=document
    )
    print(f"check both-sources exit={both.returncode}")
    require_invalid_check_invocation(clean, both)


def test_check_cannot_combine_with_compare_pointer_file(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    rel = _write_payload(isolated_ws, document)
    other = _write_payload(isolated_ws, document)
    clean = run_pointer(isolated_ws, ["--check", f"--file={rel}"])
    require_pointer_check_ok(clean)
    dirty = run_pointer(
        isolated_ws, ["--check", f"--file={rel}", f"--pointer={other}"]
    )
    print(f"check+file+pointer exit={dirty.returncode}")
    require_invalid_check_invocation(clean, dirty)


def test_check_cannot_combine_strict_and_nonstrict(isolated_ws):
    payload = _payload()
    document = _generate_doc(isolated_ws, payload)
    rel = _write_payload(isolated_ws, document)
    clean = run_pointer(isolated_ws, ["--check", f"--file={rel}"])
    require_pointer_check_ok(clean)
    dirty = run_pointer(
        isolated_ws,
        ["--check", f"--file={rel}", "--strict", "--no-strict"],
    )
    print(f"strict+no-strict exit={dirty.returncode}")
    require_invalid_check_invocation(clean, dirty)


def test_pointer_fails_when_binary_removed_from_path(isolated_ws, product_binary):
    payload = _payload()
    rel = _write_payload(isolated_ws, payload)
    present = run_pointer(isolated_ws, [f"--file={rel}"])
    require_success(present)
    hidden_path = path_without_product_bin(isolated_ws.env)
    print(f"product_binary={product_binary} hidden_path={hidden_path!r}")
    result = isolated_ws.invoke_via_git(
        ["pointer", f"--file={rel}"],
        env_updates={"PATH": hidden_path},
    )
    print(f"absent-binary pointer exit={result.returncode}")
    assert result.returncode != 0, (
        "git orbulk pointer succeeded after the product binary was removed from PATH"
    )
    assert (result.returncode, result.stdout, result.stderr) != (
        present.returncode,
        present.stdout,
        present.stderr,
    ), "absent-binary pointer was not distinguishable from pointer with the binary"
