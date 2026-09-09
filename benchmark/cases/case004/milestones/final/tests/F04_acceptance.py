# feature: F04
"""FP-04: URL-safe tokens.

Assertions follow Full_PRD.original.md FP-04 (L185–L209) plus the library
substrate negative control (L72). Exception class names, failure message
text, and failure-object attribute spellings are not pinned.
"""

from __future__ import annotations

import hashlib

from signtoken import URLSafeSerializer, URLSafeTimedSerializer  # noqa: F401

from _harness import (
    frozen_clock,
    product_package_name,
    replace_bytes,
    run_python,
    workspace,
)
from F01_helpers import runtime_ascii_digit, runtime_ascii_letter, runtime_secret
from F02_helpers import (
    JSON_LIST_ONE_THROUGH_FOUR,
    PUBLIC_ID_MAPPING,
    TEXT_SEPARATOR,
    chop_last_character,
    dump_object,
    dump_to_stream,
    load_from_stream,
    load_object,
    load_object_call,
    make_helper,
    payload_section,
    require_load_failure,
    require_load_success,
    require_payload_decode_failure,
    require_round_trip_object,
    require_signature_mismatch,
    require_unsafe_pair,
    runtime_mapping,
    tagged_text_codec,
    unsafe_load_object,
)
from F03_helpers import (
    AGE_EXPIRED_SECONDS,
    AGE_SUCCESS_SECONDS,
    MAX_AGE_SECONDS,
    OTHER_SIGNING_INSTANT,
    PUBLIC_SIGNING_INSTANT,
    require_distinct_failure_kinds,
    require_integer_list,
    require_returned_signing_time,
    require_signing_time_absent,
    require_signing_time_on_failure,
)
from F04_helpers import (
    COMPRESSION_LENGTH_LIMIT,
    PUBLIC_INTEGER_LIST,
    PUBLIC_README_MAPPING,
    PUBLIC_README_NAME,
    PUBLIC_README_SALT,
    PUBLIC_README_SECRET,
    THOUSAND_A,
    arrange_invalid_compressed_token,
    arrange_invalid_urlsafe_token,
    byte_echoes_on_failure,
    make_urlsafe_helper,
    make_urlsafe_timestamped_helper,
    repeated_letter,
    require_compressed_payload_section,
    require_exact_text_token,
    require_id_equals,
    require_named_payload_markers,
    require_no_extra_whitespace,
    require_readme_mapping,
    require_serialized_json_without_extra_whitespace,
    require_shorter_than,
    require_uncompressed_payload_section,
    require_urlsafe_text_token,
    runtime_letter_other_than_a,
    uppercase_signature_letters,
)


def _public_urlsafe(secret=PUBLIC_README_SECRET, salt=PUBLIC_README_SALT):
    return make_urlsafe_helper(secret, salt=salt)


def _public_urlsafe_timed(secret=PUBLIC_README_SECRET, salt=PUBLIC_README_SALT):
    return make_urlsafe_timestamped_helper(secret, salt=salt)


def _assert_tamper_is_mismatch(helper, obj, transform):
    token = dump_object(helper, obj)
    require_load_success(load_object_call(helper, token), expected=obj)
    require_urlsafe_text_token(token)
    tampered = transform(token)
    print(
        f"tamper from_len={len(token)} to_len={len(tampered)} "
        f"from_type={type(token).__name__}",
        flush=True,
    )
    assert tampered != token, f"transform was a no-op on {token!r}"
    require_signature_mismatch(helper, tampered)


def _uppercase_token(token: str) -> str:
    changed = token.upper()
    if changed == token:
        raise AssertionError(f"uppercasing was a no-op on {token!r}")
    return changed


def _append_runtime_char(token: str) -> str:
    extra = runtime_ascii_letter()
    return token + extra


def _replace_first_char(token: str) -> str:
    if not token:
        raise AssertionError("cannot replace the first character of an empty token")
    first = token[:1]
    replacement = "X" if first != "X" else "Y"
    return replacement + token[1:]


def _drop_signature_separator(token: str) -> str:
    require_uncompressed_payload_section(token)
    return replace_bytes(token, TEXT_SEPARATOR, "", count=1)


def _require_urlsafe_expired(result, *, instant):
    exc = require_load_failure(result)
    dt = require_signing_time_on_failure(exc, instant)
    assert dt == instant, (
        "expiry failure signing time "
        f"{dt.isoformat()} != frozen signing instant {instant.isoformat()}"
    )
    print("classified as URL-safe expiry (failure + datetime==T)", flush=True)
    return exc


# ---------------------------------------------------------------------------
# S. Library-substrate negative control (L72)
# ---------------------------------------------------------------------------


def test_urlsafe_readme_round_trip_when_package_importable():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_README_MAPPING)
    require_urlsafe_text_token(token)
    require_exact_text_token(token)
    require_named_payload_markers(token, PUBLIC_README_MAPPING)
    require_serialized_json_without_extra_whitespace(token)
    loaded = load_object(helper, token)
    require_readme_mapping(loaded)
    assert loaded == PUBLIC_README_MAPPING
    assert loaded["id"] == 5
    assert loaded["name"] == PUBLIC_README_NAME
    print(f"importable readme loaded={loaded!r}", flush=True)


def test_urlsafe_helper_fails_when_package_not_importable():
    pkg = product_package_name()
    code = (
        f"from {pkg} import URLSafeSerializer\n"
        "h = URLSafeSerializer('secret key', salt='auth')\n"
        "token = h.dumps({'id': 5, 'name': 'signtoken'})\n"
        "got = h.loads(token)\n"
        "ok = isinstance(got, dict) and got.get('id') == 5 "
        "and got.get('name') == 'signtoken'\n"
        "print('RECOVERED_README=' + ('yes' if ok else 'no'))\n"
    )
    outcome = run_python(argv=["-S", "-c", code], include_product=False)
    print(
        f"absent-package rc={outcome.returncode} "
        f"stdout={outcome.stdout_text!r} stderr={outcome.stderr_text[:500]!r}",
        flush=True,
    )
    assert "RECOVERED_README=yes" not in outcome.stdout_text, (
        "URL-safe dump/load of the README mapping still yielded that mapping "
        "after the package was removed from the import path"
    )
    assert outcome.returncode != 0, (
        "child exited 0 after the package was removed from the import path; "
        f"stdout={outcome.stdout_text!r}"
    )


def test_urlsafe_timestamped_dump_load_when_package_importable():
    helper = _public_urlsafe_timed()
    token = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(token)
    require_exact_text_token(token)
    require_named_payload_markers(token, PUBLIC_ID_MAPPING)
    loaded = load_object(helper, token)
    require_id_equals(loaded, 42)
    assert loaded == PUBLIC_ID_MAPPING
    assert loaded["id"] == 42
    print(f"importable timestamped loaded={loaded!r}", flush=True)


def test_urlsafe_timestamped_fails_when_package_not_importable():
    pkg = product_package_name()
    code = (
        f"from {pkg} import URLSafeTimedSerializer\n"
        "h = URLSafeTimedSerializer('secret key', salt='auth')\n"
        "token = h.dumps({'id': 42})\n"
        "got = h.loads(token)\n"
        "ok = isinstance(got, dict) and got.get('id') == 42\n"
        "print('RECOVERED_ID=' + ('42' if ok else 'no'))\n"
    )
    outcome = run_python(argv=["-S", "-c", code], include_product=False)
    print(
        f"absent-package rc={outcome.returncode} "
        f"stdout={outcome.stdout_text!r} stderr={outcome.stderr_text[:500]!r}",
        flush=True,
    )
    assert "RECOVERED_ID=42" not in outcome.stdout_text, (
        "URL-safe timestamped dump/load of {id: 42} still yielded that mapping "
        "after the package was removed from the import path"
    )
    assert outcome.returncode != 0, (
        "child exited 0 after the package was removed from the import path; "
        f"stdout={outcome.stdout_text!r}"
    )


# ---------------------------------------------------------------------------
# A. README mapping round-trip is a text token (L13, L187, L193, L208)
# ---------------------------------------------------------------------------


def test_readme_mapping_round_trip_is_text():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_README_MAPPING)
    require_urlsafe_text_token(token)
    assert not isinstance(token, (bytes, bytearray))
    loaded = load_object(helper, token)
    require_readme_mapping(loaded)
    print(f"readme token is text len={len(token)}", flush=True)


def test_readme_mapping_recovers_name_and_id():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_README_MAPPING)
    loaded = load_object(helper, token)
    require_readme_mapping(loaded)
    assert loaded["name"] == PUBLIC_README_NAME
    assert loaded["id"] == 5
    print(f"readme name={loaded['name']!r} id={loaded['id']!r}", flush=True)


def test_runtime_urlsafe_mapping_round_trip_is_text():
    secret = runtime_secret()
    salt = runtime_secret()
    obj = runtime_mapping()
    helper = make_urlsafe_helper(secret, salt=salt)
    token = dump_object(helper, obj)
    require_urlsafe_text_token(token)
    loaded = load_object(helper, token)
    assert loaded == obj
    print(f"runtime mapping token_len={len(token)}", flush=True)


def test_urlsafe_helper_round_trips_a_list():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_INTEGER_LIST)
    require_urlsafe_text_token(token)
    require_exact_text_token(token)
    require_named_payload_markers(token, PUBLIC_INTEGER_LIST)
    require_serialized_json_without_extra_whitespace(token)
    loaded = load_object(helper, token)
    require_integer_list(loaded, PUBLIC_INTEGER_LIST)
    assert loaded == PUBLIC_INTEGER_LIST
    secret = runtime_secret()
    salt = runtime_secret()
    runtime_list = [int(runtime_ascii_digit()) + 10, int(runtime_ascii_digit()) + 20]
    while runtime_list == PUBLIC_INTEGER_LIST:
        runtime_list.append(int(runtime_ascii_digit()) + 30)
    other = make_urlsafe_helper(secret, salt=salt)
    other_token = dump_object(other, runtime_list)
    require_urlsafe_text_token(other_token)
    require_exact_text_token(other_token)
    require_serialized_json_without_extra_whitespace(other_token)
    other_loaded = load_object(other, other_token)
    require_integer_list(other_loaded, runtime_list)
    assert other_loaded == runtime_list
    print(f"list round-trip public={loaded!r} runtime={runtime_list!r}", flush=True)


def test_second_urlsafe_helper_loads_readme_token():
    helper_a = _public_urlsafe()
    token = dump_object(helper_a, PUBLIC_README_MAPPING)
    require_urlsafe_text_token(token)
    helper_b = _public_urlsafe()
    loaded = load_object(helper_b, token)
    require_readme_mapping(loaded)
    assert loaded["id"] == 5
    assert loaded["name"] == PUBLIC_README_NAME
    print("second helper loaded first helper's README token", flush=True)


# ---------------------------------------------------------------------------
# I. Inherited FP-02 serializer arms on the URL-safe helper (L189)
# ---------------------------------------------------------------------------


def test_urlsafe_per_call_salt_is_isolated():
    helper = _public_urlsafe()
    baseline = dump_object(helper, PUBLIC_ID_MAPPING)
    require_id_equals(load_object(helper, baseline), 42)
    token = dump_object(helper, PUBLIC_ID_MAPPING, salt="other")
    default_load = load_object_call(helper, token)
    assert default_load.exception is not None, (
        "token dumped with salt='other' loaded under the default salt as "
        f"success: {default_load.value!r}"
    )
    require_signature_mismatch(helper, token)
    loaded = load_object(helper, token, salt="other")
    require_id_equals(loaded, 42)
    assert loaded["id"] == 42

    secret = runtime_secret()
    helper_none = make_urlsafe_helper(
        secret, signer_kwargs={"key_derivation": "none"}
    )
    token_none = dump_object(helper_none, PUBLIC_ID_MAPPING, salt="other")
    loaded_none = load_object(helper_none, token_none)
    require_id_equals(loaded_none, 42)
    assert loaded_none["id"] == 42
    print("URL-safe per-call salt isolated; none derivation ignores salt", flush=True)


def test_urlsafe_fallback_loads_when_current_cannot_verify():
    secret = PUBLIC_README_SECRET
    obj = PUBLIC_ID_MAPPING
    sha256 = make_urlsafe_helper(
        secret, signer_kwargs={"digest_method": hashlib.sha256}
    )
    token = dump_object(sha256, obj)
    require_urlsafe_text_token(token)
    require_id_equals(load_object(sha256, token), 42)
    with_fb = make_urlsafe_helper(
        secret,
        signer_kwargs={"digest_method": hashlib.sha1},
        fallback_signers=[{"digest_method": hashlib.sha256}],
    )
    loaded_fb = load_object(with_fb, token)
    require_id_equals(loaded_fb, 42)
    assert loaded_fb["id"] == 42
    sha1_only = make_urlsafe_helper(
        secret, signer_kwargs={"digest_method": hashlib.sha1}
    )
    own = dump_object(sha1_only, obj)
    require_id_equals(load_object(sha1_only, own), 42)
    refused = load_object_call(sha1_only, token)
    assert refused.exception is not None, (
        "SHA-256 token loaded on a SHA-1 helper with no fallback as "
        f"success: {refused.value!r}"
    )
    require_signature_mismatch(sha1_only, token)
    print("URL-safe SHA-256 token loads only when SHA-256 is a fallback", flush=True)


def test_urlsafe_unsafe_load_valid_token_is_valid_and_object():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(token)
    first, second = require_unsafe_pair(unsafe_load_object(helper, token))
    assert first, (
        "unsafe load of a valid URL-safe token did not report a valid "
        f"signature: first={first!r} second={second!r}"
    )
    require_id_equals(second, 42)

    obj = runtime_mapping()
    token_rt = dump_object(helper, obj)
    first_rt, second_rt = require_unsafe_pair(unsafe_load_object(helper, token_rt))
    assert first_rt, (
        "unsafe load of a valid runtime URL-safe token did not report a "
        f"valid signature: first={first_rt!r} second={second_rt!r}"
    )
    assert second_rt == obj
    print("URL-safe unsafe load of a valid token is (valid, object)", flush=True)


def test_urlsafe_dump_then_load_through_file_stream():
    with workspace() as ws:
        helper = _public_urlsafe()
        with ws.open_text_write("id42.txt") as fp:
            dump_to_stream(helper, PUBLIC_ID_MAPPING, fp)
        with ws.open_text("id42.txt") as fp:
            loaded = require_load_success(
                load_from_stream(helper, fp), expected=PUBLIC_ID_MAPPING
            )
        require_id_equals(loaded, 42)

        obj = runtime_mapping()
        assert obj != PUBLIC_ID_MAPPING
        with ws.open_text_write("runtime.txt") as fp:
            dump_to_stream(helper, obj, fp)
        with ws.open_text("runtime.txt") as fp:
            loaded_rt = require_load_success(
                load_from_stream(helper, fp), expected=obj
            )
        assert loaded_rt == obj
    print("URL-safe dump then load through a file stream recovered", flush=True)


def test_urlsafe_custom_dump_load_object_round_trips():
    secret = runtime_secret()
    salt = runtime_secret()
    codec = tagged_text_codec()
    helper = make_urlsafe_helper(secret, salt=salt, serializer=codec)
    obj = runtime_mapping()
    token = require_round_trip_object(helper, obj)
    require_urlsafe_text_token(token)
    assert load_object(helper, token) == obj
    json_helper = make_urlsafe_helper(secret, salt=salt)
    json_token = require_round_trip_object(json_helper, obj)
    assert load_object(json_helper, json_token) == obj
    refused = load_object_call(json_helper, token)
    assert refused.exception is not None, (
        "JSON helper loaded a non-JSON URL-safe token as success: "
        f"{refused.value!r}"
    )
    require_payload_decode_failure(json_helper, token)
    print("URL-safe attached custom dump/load round-tripped", flush=True)


# ---------------------------------------------------------------------------
# B. URL-safe alphabet and compact JSON (L59, L194–L195, L208–L209)
# ---------------------------------------------------------------------------


def test_default_list_token_contains_json_with_brackets_and_spaces():
    default = make_helper(PUBLIC_README_SECRET, salt=PUBLIC_README_SALT)
    token = dump_object(default, PUBLIC_INTEGER_LIST)
    loaded = load_object(default, token)
    require_integer_list(loaded, PUBLIC_INTEGER_LIST)
    if isinstance(token, str):
        assert JSON_LIST_ONE_THROUGH_FOUR in token, (
            "default token does not contain JSON list text with brackets "
            f"and spaces: {token!r}"
        )
    elif isinstance(token, (bytes, bytearray)):
        needle = JSON_LIST_ONE_THROUGH_FOUR.encode("utf-8")
        assert needle in token, (
            "default token does not contain JSON list text with brackets "
            f"and spaces: {token!r}"
        )
    else:
        raise AssertionError(
            f"default dump is neither text nor bytes: {type(token).__name__}"
        )
    print(f"default list token carries {JSON_LIST_ONE_THROUGH_FOUR!r}", flush=True)


def test_urlsafe_list_token_has_no_brackets_or_spaces_and_loads():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_INTEGER_LIST)
    require_urlsafe_text_token(token)
    require_exact_text_token(token)
    require_named_payload_markers(token, PUBLIC_INTEGER_LIST)
    require_serialized_json_without_extra_whitespace(token)
    assert "[" not in token and "]" not in token, (
        f"URL-safe list token still contains brackets: {token!r}"
    )
    assert " " not in token, f"URL-safe list token still contains spaces: {token!r}"
    loaded = load_object(helper, token)
    require_integer_list(loaded, PUBLIC_INTEGER_LIST)
    print(f"urlsafe list token_len={len(token)} loaded={loaded!r}", flush=True)


def test_urlsafe_tokens_use_only_urlsafe_alphabet():
    helper = _public_urlsafe()
    objects = (
        PUBLIC_README_MAPPING,
        PUBLIC_ID_MAPPING,
        THOUSAND_A,
        runtime_mapping(),
    )
    for obj in objects:
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        require_exact_text_token(token)
        require_named_payload_markers(token, obj)
        if obj != THOUSAND_A:
            require_serialized_json_without_extra_whitespace(token)
        loaded = load_object(helper, token)
        assert loaded == obj
        print(f"alphabet-ok obj_type={type(obj).__name__} len={len(token)}", flush=True)


def test_timestamped_urlsafe_tokens_use_only_urlsafe_alphabet():
    helper = _public_urlsafe_timed()
    objects = (
        PUBLIC_README_MAPPING,
        PUBLIC_INTEGER_LIST,
        PUBLIC_ID_MAPPING,
        THOUSAND_A,
        runtime_mapping(),
    )
    for obj in objects:
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        require_exact_text_token(token)
        require_named_payload_markers(token, obj)
        loaded = load_object(helper, token)
        assert loaded == obj
        print(
            f"timed alphabet-ok obj_type={type(obj).__name__} len={len(token)}",
            flush=True,
        )


def test_urlsafe_compact_dump_still_loads():
    default = make_helper(PUBLIC_README_SECRET, salt=PUBLIC_README_SALT)
    default_token = dump_object(default, PUBLIC_INTEGER_LIST)
    if isinstance(default_token, str):
        default_text = default_token
    elif isinstance(default_token, (bytes, bytearray)):
        default_text = default_token.decode("utf-8")
    else:
        raise AssertionError(
            "default dump is neither text nor bytes: "
            f"{type(default_token).__name__}"
        )
    assert JSON_LIST_ONE_THROUGH_FOUR in default_text, (
        "default token does not contain JSON list text with extra "
        f"whitespace: {default_text!r}"
    )

    helper = _public_urlsafe()
    list_token = dump_object(helper, PUBLIC_INTEGER_LIST)
    require_urlsafe_text_token(list_token)
    require_no_extra_whitespace(list_token)
    require_serialized_json_without_extra_whitespace(list_token)
    require_integer_list(load_object(helper, list_token), PUBLIC_INTEGER_LIST)

    id_token = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(id_token)
    require_uncompressed_payload_section(id_token)
    require_serialized_json_without_extra_whitespace(id_token)
    require_id_equals(load_object(helper, id_token), 42)

    obj = runtime_mapping()
    mapped = require_round_trip_object(helper, obj)
    require_urlsafe_text_token(mapped)
    require_no_extra_whitespace(mapped)
    require_serialized_json_without_extra_whitespace(mapped)
    print(
        "URL-safe JSON has no extra whitespace; dump then load recovered",
        flush=True,
    )


# ---------------------------------------------------------------------------
# C. Compress when shorter; both forms load (L11, L196, L208–L209)
# ---------------------------------------------------------------------------


def test_thousand_a_is_compressed_shorter_than_1000():
    helper = _public_urlsafe()
    token = dump_object(helper, THOUSAND_A)
    require_urlsafe_text_token(token)
    require_shorter_than(token, COMPRESSION_LENGTH_LIMIT)
    loaded = load_object(helper, token)
    assert loaded == THOUSAND_A
    print(f"thousand-a token_len={len(token)}", flush=True)


def test_thousand_a_payload_section_begins_with_period():
    helper = _public_urlsafe()
    token = dump_object(helper, THOUSAND_A)
    require_urlsafe_text_token(token)
    require_compressed_payload_section(token)
    assert load_object(helper, token) == THOUSAND_A


def test_id_42_is_uncompressed_payload_not_leading_period():
    helper = _public_urlsafe()
    token = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(token)
    require_uncompressed_payload_section(token)
    loaded = load_object(helper, token)
    require_id_equals(loaded, 42)
    assert loaded == PUBLIC_ID_MAPPING


def test_runtime_repeated_letter_is_compressed():
    secret = runtime_secret()
    salt = runtime_secret()
    letter = runtime_letter_other_than_a()
    blob = repeated_letter(letter, 1000)
    assert blob != THOUSAND_A
    helper = make_urlsafe_helper(secret, salt=salt)
    token = dump_object(helper, blob)
    require_urlsafe_text_token(token)
    require_shorter_than(token, COMPRESSION_LENGTH_LIMIT)
    require_compressed_payload_section(token)
    loaded = load_object(helper, token)
    assert loaded == blob
    print(f"runtime repeated {letter!r} token_len={len(token)}", flush=True)


def test_runtime_small_mapping_is_uncompressed():
    secret = runtime_secret()
    salt = runtime_secret()
    obj = runtime_mapping()
    assert obj != PUBLIC_ID_MAPPING
    helper = make_urlsafe_helper(secret, salt=salt)
    token = dump_object(helper, obj)
    require_urlsafe_text_token(token)
    require_uncompressed_payload_section(token)
    assert load_object(helper, token) == obj


def test_compressed_and_uncompressed_both_load():
    helper = _public_urlsafe()
    compressed = dump_object(helper, THOUSAND_A)
    uncompressed = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(compressed)
    require_urlsafe_text_token(uncompressed)
    require_compressed_payload_section(compressed)
    require_uncompressed_payload_section(uncompressed)
    assert load_object(helper, compressed) == THOUSAND_A
    loaded_small = load_object(helper, uncompressed)
    require_id_equals(loaded_small, 42)
    print("both compressed and uncompressed forms load", flush=True)


def test_second_urlsafe_helper_loads_first_helpers_compressed_and_readme_tokens():
    helper_a = _public_urlsafe()
    first = dump_object(helper_a, THOUSAND_A)
    second = dump_object(helper_a, PUBLIC_README_MAPPING)
    require_urlsafe_text_token(first)
    require_urlsafe_text_token(second)
    assert load_object(helper_a, first) == THOUSAND_A
    helper_b = _public_urlsafe()
    assert load_object(helper_b, first) == THOUSAND_A
    require_readme_mapping(load_object(helper_b, second))
    print("second helper loaded both of first helper's tokens", flush=True)


# ---------------------------------------------------------------------------
# D. Timestamped URL-safe: same objects, age 10, signing time, still compressed
# ---------------------------------------------------------------------------


def test_timestamped_urlsafe_round_trips_named_objects_as_text():
    helper = _public_urlsafe_timed()
    runtime_obj = runtime_mapping()
    objects = (
        PUBLIC_README_MAPPING,
        PUBLIC_INTEGER_LIST,
        PUBLIC_ID_MAPPING,
        THOUSAND_A,
        runtime_obj,
    )
    for obj in objects:
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        require_exact_text_token(token)
        require_named_payload_markers(token, obj)
        loaded = load_object(helper, token)
        assert loaded == obj
        print(
            f"timed round-trip obj_type={type(obj).__name__} len={len(token)}",
            flush=True,
        )


def test_timestamped_urlsafe_thousand_a_still_compressed():
    helper = _public_urlsafe_timed()
    token = dump_object(helper, THOUSAND_A)
    require_urlsafe_text_token(token)
    require_shorter_than(token, COMPRESSION_LENGTH_LIMIT)
    require_compressed_payload_section(token)
    assert load_object(helper, token) == THOUSAND_A


def test_timestamped_urlsafe_id_42_uncompressed():
    helper = _public_urlsafe_timed()
    token = dump_object(helper, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(token)
    require_uncompressed_payload_section(token)
    loaded = load_object(helper, token)
    require_id_equals(loaded, 42)
    assert loaded["id"] == 42


def test_timestamped_urlsafe_max_age_10_succeeds_at_one_second():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, PUBLIC_ID_MAPPING)
        require_urlsafe_text_token(token)
        clock.tick(AGE_SUCCESS_SECONDS)
        loaded = load_object(helper, token, max_age=MAX_AGE_SECONDS)
        require_id_equals(loaded, 42)
        assert loaded["id"] == 42
        print(f"max-age 10 at 1s loaded={loaded!r}", flush=True)


def test_timestamped_urlsafe_max_age_10_expired_at_eleven():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        young = load_object(helper, token, max_age=MAX_AGE_SECONDS)
        require_id_equals(young, 42)
        assert young["id"] == 42
        clock.tick(AGE_EXPIRED_SECONDS - AGE_SUCCESS_SECONDS)
        expired = load_object_call(helper, token, max_age=MAX_AGE_SECONDS)
        assert expired.exception is not None, (
            "token accepted at eleven seconds under max-age 10: "
            f"{expired.value!r}"
        )
        _require_urlsafe_expired(expired, instant=instant)
        still = load_object(helper, token)
        require_id_equals(still, 42)
        assert still["id"] == 42
        print("eleven seconds expired; same token without max-age still loads", flush=True)


def test_timestamped_urlsafe_eleven_seconds_without_max_age_still_loads():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, PUBLIC_ID_MAPPING)
        clock.tick(AGE_EXPIRED_SECONDS)
        loaded = load_object(helper, token)
        require_id_equals(loaded, 42)
        assert loaded["id"] == 42


def test_timestamped_urlsafe_thousand_a_max_age_10_succeeds_at_one_second():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, THOUSAND_A)
        require_compressed_payload_section(token)
        clock.tick(AGE_SUCCESS_SECONDS)
        loaded = load_object(helper, token, max_age=MAX_AGE_SECONDS)
        assert loaded == THOUSAND_A


def test_timestamped_urlsafe_thousand_a_max_age_10_expired_at_eleven():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, THOUSAND_A)
        instant = clock.instant
        require_compressed_payload_section(token)
        clock.tick(AGE_SUCCESS_SECONDS)
        assert load_object(helper, token, max_age=MAX_AGE_SECONDS) == THOUSAND_A
        clock.tick(AGE_EXPIRED_SECONDS - AGE_SUCCESS_SECONDS)
        _require_urlsafe_expired(
            load_object_call(helper, token, max_age=MAX_AGE_SECONDS),
            instant=instant,
        )
        assert load_object(helper, token) == THOUSAND_A


def test_timestamped_urlsafe_ask_signing_time_after_tick_equals_instant():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        assert clock.instant != instant
        value, dt = require_returned_signing_time(
            load_object_call(helper, token, return_timestamp=True),
            PUBLIC_ID_MAPPING,
            instant,
        )
        require_id_equals(value, 42)
        print(f"asked signing time dt={dt.isoformat()} instant={instant.isoformat()}", flush=True)

    secret = runtime_secret()
    salt = runtime_secret()
    obj = runtime_mapping()
    other = make_urlsafe_timestamped_helper(secret, salt=salt)
    with frozen_clock(OTHER_SIGNING_INSTANT) as clock:
        token = dump_object(other, obj)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        require_returned_signing_time(
            load_object_call(other, token, return_timestamp=True),
            obj,
            instant,
        )


def test_timestamped_urlsafe_ask_signing_time_on_compressed():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, THOUSAND_A)
        instant = clock.instant
        require_compressed_payload_section(token)
        clock.tick(AGE_SUCCESS_SECONDS)
        value, dt = require_returned_signing_time(
            load_object_call(helper, token, return_timestamp=True),
            THOUSAND_A,
            instant,
        )
        assert value == THOUSAND_A
        print(f"compressed asked signing time dt={dt.isoformat()}", flush=True)


def test_timestamped_urlsafe_return_time_with_max_age_succeeds_then_expires():
    helper = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        value, dt = require_returned_signing_time(
            load_object_call(
                helper, token, max_age=MAX_AGE_SECONDS, return_timestamp=True
            ),
            PUBLIC_ID_MAPPING,
            instant,
        )
        assert value["id"] == 42
        assert dt == instant
        clock.tick(AGE_EXPIRED_SECONDS - AGE_SUCCESS_SECONDS)
        expired = load_object_call(
            helper, token, max_age=MAX_AGE_SECONDS, return_timestamp=True
        )
        assert expired.exception is not None, (
            "joint max-age+return-time load succeeded at eleven seconds: "
            f"{expired.value!r}"
        )
        _require_urlsafe_expired(expired, instant=instant)
        print("joint max-age+return-time succeeded then expired", flush=True)


def test_runtime_timestamped_urlsafe_max_age_10():
    secret = runtime_secret()
    salt = runtime_secret()
    obj = runtime_mapping()
    helper = make_urlsafe_timestamped_helper(secret, salt=salt)
    with frozen_clock(OTHER_SIGNING_INSTANT) as clock:
        token = dump_object(helper, obj)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        assert load_object(helper, token, max_age=MAX_AGE_SECONDS) == obj
        clock.tick(AGE_EXPIRED_SECONDS - AGE_SUCCESS_SECONDS)
        _require_urlsafe_expired(
            load_object_call(helper, token, max_age=MAX_AGE_SECONDS),
            instant=instant,
        )
        assert load_object(helper, token) == obj


def test_second_timestamped_urlsafe_helper_reads_signing_time_from_token():
    helper_a = _public_urlsafe_timed()
    helper_b = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper_a, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        young = load_object(helper_b, token, max_age=MAX_AGE_SECONDS)
        require_id_equals(young, 42)
        assert young["id"] == 42
        value, dt = require_returned_signing_time(
            load_object_call(helper_b, token, return_timestamp=True),
            PUBLIC_ID_MAPPING,
            instant,
        )
        require_id_equals(value, 42)
        assert value["id"] == 42
        assert dt == instant
        print(
            f"second timed helper read dt={dt.isoformat()} from token",
            flush=True,
        )


def test_timestamped_urlsafe_earlier_token_keeps_its_signing_time():
    helper = _public_urlsafe_timed()
    first_obj = PUBLIC_ID_MAPPING
    second_obj = PUBLIC_README_MAPPING
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token_a = dump_object(helper, first_obj)
        instant_a = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        token_b = dump_object(helper, second_obj)
        instant_b = clock.instant
        assert instant_b != instant_a
        clock.tick(AGE_SUCCESS_SECONDS)
        require_returned_signing_time(
            load_object_call(helper, token_a, return_timestamp=True),
            first_obj,
            instant_a,
        )
        require_returned_signing_time(
            load_object_call(helper, token_b, return_timestamp=True),
            second_obj,
            instant_b,
        )
        print(
            f"earlier token kept T1={instant_a.isoformat()} "
            f"later T2={instant_b.isoformat()}",
            flush=True,
        )


def test_second_timestamped_urlsafe_helper_expires_first_helpers_token():
    helper_a = _public_urlsafe_timed()
    helper_b = _public_urlsafe_timed()
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        token = dump_object(helper_a, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_SUCCESS_SECONDS)
        young = load_object(helper_b, token, max_age=MAX_AGE_SECONDS)
        require_id_equals(young, 42)
        assert young["id"] == 42
        clock.tick(AGE_EXPIRED_SECONDS - AGE_SUCCESS_SECONDS)
        expired = load_object_call(helper_b, token, max_age=MAX_AGE_SECONDS)
        assert expired.exception is not None, (
            "second helper accepted first helper's token at eleven seconds "
            f"under max-age 10: {expired.value!r}"
        )
        _require_urlsafe_expired(expired, instant=instant)
        print("second timed helper expired first helper's token", flush=True)


# ---------------------------------------------------------------------------
# E. Four tamper transforms are a signature mismatch (L141, L201, L209)
# ---------------------------------------------------------------------------


def test_urlsafe_uppercased_token_is_signature_mismatch():
    helper = _public_urlsafe()
    _assert_tamper_is_mismatch(helper, PUBLIC_README_MAPPING, _uppercase_token)
    _assert_tamper_is_mismatch(helper, PUBLIC_ID_MAPPING, _uppercase_token)
    # Full-token uppercasing also rewrites the URL-safe payload encoding
    # (the alphabet is case-sensitive). Holding the payload section fixed
    # and uppercasing only signature letters isolates L201's signature
    # mismatch from that encoding covariate.
    _assert_tamper_is_mismatch(
        helper, PUBLIC_README_MAPPING, uppercase_signature_letters
    )
    _assert_tamper_is_mismatch(helper, PUBLIC_ID_MAPPING, uppercase_signature_letters)


def test_urlsafe_appended_character_is_signature_mismatch():
    helper = _public_urlsafe()
    _assert_tamper_is_mismatch(helper, PUBLIC_README_MAPPING, _append_runtime_char)
    _assert_tamper_is_mismatch(helper, PUBLIC_ID_MAPPING, _append_runtime_char)


def test_urlsafe_replaced_first_character_is_signature_mismatch():
    helper = _public_urlsafe()
    for obj in (PUBLIC_README_MAPPING, PUBLIC_ID_MAPPING):
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        require_exact_text_token(token)
        require_named_payload_markers(token, obj)
        require_serialized_json_without_extra_whitespace(token)
        require_load_success(load_object_call(helper, token), expected=obj)
        _assert_tamper_is_mismatch(helper, obj, _replace_first_char)


def test_urlsafe_separator_removed_is_signature_mismatch():
    helper = _public_urlsafe()
    _assert_tamper_is_mismatch(
        helper, PUBLIC_README_MAPPING, _drop_signature_separator
    )
    _assert_tamper_is_mismatch(helper, PUBLIC_ID_MAPPING, _drop_signature_separator)


def test_runtime_urlsafe_tamper_transforms_are_signature_mismatch():
    secret = runtime_secret()
    salt = runtime_secret()
    helper = make_urlsafe_helper(secret, salt=salt)
    obj = runtime_mapping()
    _assert_tamper_is_mismatch(helper, obj, _uppercase_token)
    _assert_tamper_is_mismatch(helper, obj, _append_runtime_char)
    _assert_tamper_is_mismatch(helper, obj, _replace_first_char)
    _assert_tamper_is_mismatch(helper, obj, _drop_signature_separator)


def test_compressed_urlsafe_uppercased_appended_and_replaced_are_signature_mismatch():
    helper = _public_urlsafe()
    token = dump_object(helper, THOUSAND_A)
    require_load_success(load_object_call(helper, token), expected=THOUSAND_A)
    require_compressed_payload_section(token)
    _assert_tamper_is_mismatch(helper, THOUSAND_A, _uppercase_token)
    _assert_tamper_is_mismatch(helper, THOUSAND_A, _append_runtime_char)
    _assert_tamper_is_mismatch(helper, THOUSAND_A, _replace_first_char)


# ---------------------------------------------------------------------------
# F. Invalid URL-safe encoding or fake compression is payload-decode failure
# ---------------------------------------------------------------------------


def test_invalid_urlsafe_encoding_is_payload_decode_failure():
    helper = _public_urlsafe()
    legal = dump_object(helper, PUBLIC_ID_MAPPING)
    require_id_equals(load_object(helper, legal), 42)
    garbage = arrange_invalid_urlsafe_token(
        PUBLIC_README_SECRET, PUBLIC_README_SALT
    )
    refused = load_object_call(helper, garbage)
    assert refused.exception is not None, (
        "valid signature over invalid URL-safe encoding loaded as success: "
        f"{refused.value!r}"
    )
    require_payload_decode_failure(helper, garbage)


def test_invalid_compressed_payload_is_payload_decode_failure():
    helper = _public_urlsafe()
    legal = dump_object(helper, THOUSAND_A)
    assert load_object(helper, legal) == THOUSAND_A
    garbage = arrange_invalid_compressed_token(
        PUBLIC_README_SECRET, PUBLIC_README_SALT
    )
    refused = load_object_call(helper, garbage)
    assert refused.exception is not None, (
        "valid signature over fake compressed data loaded as success: "
        f"{refused.value!r}"
    )
    require_payload_decode_failure(helper, garbage)


def test_payload_decode_distinguishable_from_signature_mismatch():
    helper = _public_urlsafe()
    legal = dump_object(helper, PUBLIC_ID_MAPPING)
    require_id_equals(load_object(helper, legal), 42)
    chopped = chop_last_character(legal)
    chopped_load = load_object_call(helper, chopped)
    assert chopped_load.exception is not None, (
        f"chopped token loaded as success: {chopped_load.value!r}"
    )
    require_signature_mismatch(helper, chopped)
    invalid = arrange_invalid_urlsafe_token(
        PUBLIC_README_SECRET, PUBLIC_README_SALT
    )
    invalid_load = load_object_call(helper, invalid)
    assert invalid_load.exception is not None, (
        "valid signature over invalid URL-safe encoding loaded as success: "
        f"{invalid_load.value!r}"
    )
    require_payload_decode_failure(helper, invalid)
    fake_compressed = arrange_invalid_compressed_token(
        PUBLIC_README_SECRET, PUBLIC_README_SALT
    )
    fake_load = load_object_call(helper, fake_compressed)
    assert fake_load.exception is not None, (
        "valid signature over fake compressed data loaded as success: "
        f"{fake_load.value!r}"
    )
    require_payload_decode_failure(helper, fake_compressed)
    print("payload-decode and chopped-signature outcomes differ", flush=True)


def test_chopped_compressed_token_is_signature_mismatch():
    helper = _public_urlsafe()
    token = dump_object(helper, THOUSAND_A)
    require_load_success(load_object_call(helper, token), expected=THOUSAND_A)
    require_compressed_payload_section(token)
    chopped = chop_last_character(token)
    chopped_load = load_object_call(helper, chopped)
    assert chopped_load.exception is not None, (
        f"chopped compressed token loaded as success: {chopped_load.value!r}"
    )
    require_signature_mismatch(helper, chopped)
    print("chopped compressed token is a signature mismatch", flush=True)


def test_runtime_invalid_urlsafe_and_invalid_compressed():
    secret = runtime_secret()
    salt = runtime_secret()
    helper = make_urlsafe_helper(secret, salt=salt)
    obj = runtime_mapping()
    legal = dump_object(helper, obj)
    require_load_success(load_object_call(helper, legal), expected=obj)
    invalid = arrange_invalid_urlsafe_token(secret, salt)
    invalid_load = load_object_call(helper, invalid)
    assert invalid_load.exception is not None, (
        "valid signature over invalid URL-safe encoding loaded as success: "
        f"{invalid_load.value!r}"
    )
    require_payload_decode_failure(helper, invalid)
    fake = arrange_invalid_compressed_token(secret, salt)
    fake_load = load_object_call(helper, fake)
    assert fake_load.exception is not None, (
        "valid signature over fake compressed data loaded as success: "
        f"{fake_load.value!r}"
    )
    require_payload_decode_failure(helper, fake)


# ---------------------------------------------------------------------------
# G. No time field: uncompressed is missing; compressed thousand-a is malformed
# ---------------------------------------------------------------------------


def test_uncompressed_urlsafe_token_is_missing_timestamp():
    plain = _public_urlsafe()
    timed = _public_urlsafe_timed()
    token = dump_object(plain, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(token)
    require_uncompressed_payload_section(token)
    require_id_equals(load_object(plain, token), 42)
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        legal = dump_object(timed, PUBLIC_ID_MAPPING)
        instant = clock.instant
        clock.tick(AGE_EXPIRED_SECONDS)
        expired = _require_urlsafe_expired(
            load_object_call(timed, legal, max_age=MAX_AGE_SECONDS),
            instant=instant,
        )
        require_id_equals(load_object(timed, legal), 42)
    refused = load_object_call(timed, token)
    exc = require_load_failure(refused)
    require_signing_time_absent(exc)
    assert expired is not None
    print("uncompressed cross-load refused; not expiry", flush=True)


def test_missing_timestamp_signing_time_absent():
    plain = _public_urlsafe()
    timed = _public_urlsafe_timed()
    token = dump_object(plain, PUBLIC_ID_MAPPING)
    require_uncompressed_payload_section(token)
    refused = load_object_call(timed, token)
    assert refused.exception is not None, (
        "uncompressed non-timestamped token loaded on the timestamped "
        f"helper as success: {refused.value!r}"
    )
    exc = require_load_failure(refused)
    require_signing_time_absent(exc)


def test_compressed_thousand_a_on_timestamped_is_malformed_not_expiry():
    plain = _public_urlsafe()
    timed = _public_urlsafe_timed()
    token = dump_object(plain, THOUSAND_A)
    require_urlsafe_text_token(token)
    require_compressed_payload_section(token)
    assert load_object(plain, token) == THOUSAND_A
    with frozen_clock(PUBLIC_SIGNING_INSTANT) as clock:
        legal = dump_object(timed, THOUSAND_A)
        instant = clock.instant
        clock.tick(AGE_EXPIRED_SECONDS)
        expired = _require_urlsafe_expired(
            load_object_call(timed, legal, max_age=MAX_AGE_SECONDS),
            instant=instant,
        )
        assert load_object(timed, legal) == THOUSAND_A
    refused = load_object_call(timed, token)
    exc = require_load_failure(refused)
    require_signing_time_absent(exc)
    assert expired is not None
    print("compressed thousand-a cross-load refused; not expiry", flush=True)


def test_compressed_cross_load_signing_time_absent():
    plain = _public_urlsafe()
    timed = _public_urlsafe_timed()
    token = dump_object(plain, THOUSAND_A)
    require_compressed_payload_section(token)
    refused = load_object_call(timed, token)
    assert refused.exception is not None, (
        "compressed non-timestamped token loaded on the timestamped "
        f"helper as success: {refused.value!r}"
    )
    exc = require_load_failure(refused)
    require_signing_time_absent(exc)


def test_runtime_uncompressed_cross_load_refused():
    secret = runtime_secret()
    salt = runtime_secret()
    obj = runtime_mapping()
    plain = make_urlsafe_helper(secret, salt=salt)
    timed = make_urlsafe_timestamped_helper(secret, salt=salt)
    token = dump_object(plain, obj)
    require_uncompressed_payload_section(token)
    assert load_object(plain, token) == obj
    exc = require_load_failure(load_object_call(timed, token))
    require_signing_time_absent(exc)


def test_runtime_compressed_cross_load_refused():
    secret = runtime_secret()
    salt = runtime_secret()
    letter = runtime_letter_other_than_a()
    blob = repeated_letter(letter, 1000)
    plain = make_urlsafe_helper(secret, salt=salt)
    timed = make_urlsafe_timestamped_helper(secret, salt=salt)
    token = dump_object(plain, blob)
    require_compressed_payload_section(token)
    assert load_object(plain, token) == blob
    exc = require_load_failure(load_object_call(timed, token))
    require_signing_time_absent(exc)


def test_missing_and_malformed_urlsafe_cross_load_are_distinguishable():
    plain = _public_urlsafe()
    timed = _public_urlsafe_timed()
    missing_token = dump_object(plain, PUBLIC_ID_MAPPING)
    require_urlsafe_text_token(missing_token)
    require_uncompressed_payload_section(missing_token)
    require_id_equals(load_object(plain, missing_token), 42)
    malformed_token = dump_object(plain, THOUSAND_A)
    require_urlsafe_text_token(malformed_token)
    require_compressed_payload_section(malformed_token)
    assert load_object(plain, malformed_token) == THOUSAND_A

    missing_exc = require_load_failure(load_object_call(timed, missing_token))
    require_signing_time_absent(missing_exc)
    malformed_exc = require_load_failure(load_object_call(timed, malformed_token))
    require_signing_time_absent(malformed_exc)

    missing_section = payload_section(missing_token)
    malformed_section = payload_section(malformed_token)
    require_distinct_failure_kinds(
        missing_exc,
        malformed_exc,
        covariates=(
            missing_token,
            malformed_token,
            missing_section,
            malformed_section,
            PUBLIC_ID_MAPPING,
            THOUSAND_A,
            42,
            *byte_echoes_on_failure(missing_exc),
            *byte_echoes_on_failure(malformed_exc),
        ),
    )
    print(
        "uncompressed {id:42} missing-timestamp refusal is distinguishable "
        "from compressed thousand-a malformed-timestamp refusal",
        flush=True,
    )


# ---------------------------------------------------------------------------
# H. Product-emitted tokens never contain plus or slash (L204, L209)
# ---------------------------------------------------------------------------


def test_product_emitted_urlsafe_tokens_never_contain_plus_or_slash():
    helper = _public_urlsafe()
    objects = (
        PUBLIC_README_MAPPING,
        PUBLIC_INTEGER_LIST,
        PUBLIC_ID_MAPPING,
        THOUSAND_A,
        runtime_mapping(),
    )
    for obj in objects:
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        loaded = load_object(helper, token)
        assert loaded == obj
        assert "+" not in token, f"product-emitted token contains plus: {token!r}"
        assert "/" not in token, f"product-emitted token contains slash: {token!r}"
        print(f"no plus/slash obj_type={type(obj).__name__}", flush=True)


def test_timestamped_product_emitted_tokens_never_contain_plus_or_slash():
    helper = _public_urlsafe_timed()
    objects = (
        PUBLIC_README_MAPPING,
        PUBLIC_INTEGER_LIST,
        PUBLIC_ID_MAPPING,
        THOUSAND_A,
        runtime_mapping(),
    )
    for obj in objects:
        token = dump_object(helper, obj)
        require_urlsafe_text_token(token)
        require_exact_text_token(token)
        require_named_payload_markers(token, obj)
        loaded = load_object(helper, token)
        assert loaded == obj
        assert "+" not in token, f"product-emitted timed token contains plus: {token!r}"
        assert "/" not in token, f"product-emitted timed token contains slash: {token!r}"
        print(f"timed no plus/slash obj_type={type(obj).__name__}", flush=True)
