# feature: F04
"""Observation helpers for URL-safe serialize-and-sign tokens (FP-04).

Helpers classify dump / load outcomes of the URL-safe helper and the
URL-safe timestamped helper. They never return ``None`` to mean "the
observation could not be classified".
"""

from __future__ import annotations

import base64
import json
import string
import zlib
from typing import Any

from _harness import (
    CallResult,
    HarnessError,
    call,
    require_value,
)
from F01_helpers import runtime_ascii_letter
from F02_helpers import (
    PUBLIC_ID_MAPPING,
    _inspectable_text_and_bytes,
    join_payload_and_signature,
    payload_section,
    signature_section,
    signed_garbage_token,
)

PUBLIC_README_SECRET = "secret key"
PUBLIC_README_SALT = "auth"
PUBLIC_README_NAME = "signtoken"
PUBLIC_README_MAPPING = {"id": 5, "name": PUBLIC_README_NAME}
PUBLIC_INTEGER_LIST = [1, 2, 3, 4]
THOUSAND_A = "a" * 1000
COMPRESSION_LENGTH_LIMIT = 1000
URLSAFE_ALPHABET = frozenset(string.ascii_letters + string.digits + "_-.")
FORBIDDEN_URLSAFE_CHARS = ("+", "/", "=", " ", "[", "]", '"', "'")


def load_urlsafe_surface() -> Any:
    """Import the URL-safe serialize-and-sign helper from the package root.

    Import happens here, not at module import time, so this helper still
    loads when the product is absent from ``sys.path``.
    """
    from signtoken import URLSafeSerializer

    if not callable(URLSafeSerializer):
        raise HarnessError(
            f"URLSafeSerializer is not callable; got {type(URLSafeSerializer)!r}"
        )
    return URLSafeSerializer


def load_urlsafe_timestamped_surface() -> Any:
    """Import the URL-safe timestamped helper from the package root."""
    from signtoken import URLSafeTimedSerializer

    if not callable(URLSafeTimedSerializer):
        raise HarnessError(
            "URLSafeTimedSerializer is not callable; "
            f"got {type(URLSafeTimedSerializer)!r}"
        )
    return URLSafeTimedSerializer


def construct_urlsafe_helper(*args: Any, **kwargs: Any) -> CallResult:
    return call(load_urlsafe_surface(), *args, **kwargs)


def construct_urlsafe_timestamped_helper(*args: Any, **kwargs: Any) -> CallResult:
    return call(load_urlsafe_timestamped_surface(), *args, **kwargs)


def make_urlsafe_helper(*args: Any, **kwargs: Any) -> Any:
    helper = require_value(construct_urlsafe_helper(*args, **kwargs))
    print(
        f"constructed URL-safe helper args={args!r} kwargs={list(kwargs)!r}",
        flush=True,
    )
    return helper


def make_urlsafe_timestamped_helper(*args: Any, **kwargs: Any) -> Any:
    helper = require_value(construct_urlsafe_timestamped_helper(*args, **kwargs))
    print(
        f"constructed URL-safe timestamped helper args={args!r} "
        f"kwargs={list(kwargs)!r}",
        flush=True,
    )
    return helper


def require_no_extra_whitespace(token: Any) -> str:
    """Require a URL-safe text token contains no extra whitespace.

    Spaces, tabs, and newlines are extra whitespace. Raises if *token*
    is not text — never flattens bytes.
    """
    if not isinstance(token, str):
        raise AssertionError(
            "URL-safe token must be text, not "
            f"{type(token).__name__}: {token!r}"
        )
    extras = [ch for ch in (" ", "\t", "\n", "\r") if ch in token]
    if extras:
        raise AssertionError(
            "URL-safe token still contains extra whitespace "
            f"{extras!r}; token={token!r}"
        )
    print("urlsafe token has no extra whitespace", flush=True)
    return token


def _json_has_whitespace_between_tokens(text: str) -> bool:
    """True when *text* has whitespace outside JSON string literals."""
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch in " \t\n\r":
            return True
    return False


def require_serialized_json_without_extra_whitespace(token: Any) -> str:
    """Require the public dump serialized JSON with no extra whitespace.

    Reads the payload section of a dumped URL-safe token with the
    language's URL-safe decoder (and, when that section begins with a
    period, the language's decompressor). Does not call a product
    decoder and does not recompute a compact dump to compare against.
    Probe failures raise — they are never treated as "compact".
    """
    section = _payload_section_text(token)
    raw = section.encode("ascii")
    if raw.startswith(b"."):
        decoded = _stdlib_urlsafe_decode(raw[1:])
        try:
            decoded = zlib.decompress(decoded)
        except Exception as exc:
            raise AssertionError(
                "payload section begins with a period but is not "
                f"compressed JSON: {exc}"
            ) from exc
    else:
        decoded = _stdlib_urlsafe_decode(raw)
    try:
        text = decoded.decode("utf-8")
    except Exception as exc:
        raise AssertionError(
            f"serialized payload is not UTF-8 text: {exc}; raw={decoded!r}"
        ) from exc
    try:
        json.loads(text)
    except Exception as exc:
        raise AssertionError(
            f"serialized payload is not JSON: {exc}; text={text!r}"
        ) from exc
    if _json_has_whitespace_between_tokens(text):
        raise AssertionError(
            "URL-safe helper serialized JSON with extra whitespace "
            f"between tokens: {text!r}"
        )
    print(
        f"serialized JSON has no extra whitespace text={text!r}",
        flush=True,
    )
    return text


def require_exact_text_token(token: Any) -> str:
    """Require *token* is text, not bytes.

    Lines 193 and 197 name the token as URL-safe text, not bytes. A
    text subclass that still presents as text satisfies that contrast;
    only bytes or another non-text result is refused. The built-in
    ``str`` identity is not pinned.
    """
    if isinstance(token, (bytes, bytearray)):
        raise AssertionError(
            "URL-safe token must be text, not bytes: "
            f"{type(token).__name__}: {token!r}"
        )
    if not isinstance(token, str):
        raise AssertionError(
            "URL-safe token must be text, not "
            f"{type(token).__name__}: {token!r}"
        )
    print(f"text token (not bytes) len={len(token)}", flush=True)
    return token


def require_urlsafe_text_token(token: Any) -> str:
    """Require *token* is text using only the URL-safe alphabet.

    Raises if the token is bytes (or any non-text) — never flattens
    bytes into text. Named forbidden characters are asserted explicitly.
    """
    if not isinstance(token, str):
        raise AssertionError(
            "URL-safe token must be text, not "
            f"{type(token).__name__}: {token!r}"
        )
    extras = sorted({ch for ch in token if ch not in URLSAFE_ALPHABET})
    if extras:
        raise AssertionError(
            "URL-safe token contains characters outside the alphabet "
            f"{extras!r}; token={token!r}"
        )
    for ch in FORBIDDEN_URLSAFE_CHARS:
        if ch in token:
            raise AssertionError(
                "URL-safe token contains forbidden character "
                f"{ch!r}; token={token!r}"
            )
    print(
        f"urlsafe text token len={len(token)} alphabet_ok",
        flush=True,
    )
    return token


def _payload_section_text(token: Any) -> str:
    """Payload section of a text token. Raises if the section cannot be cut."""
    if not isinstance(token, str):
        raise HarnessError(
            "payload-section observation requires a text token; "
            f"got {type(token).__name__}"
        )
    section = payload_section(token)
    if not isinstance(section, str):
        raise HarnessError(
            "payload_section did not return text; "
            f"got {type(section).__name__}: {section!r}"
        )
    if not section:
        raise HarnessError("payload section is empty; cannot classify compression")
    return section


def require_compressed_payload_section(token: Any) -> str:
    """Require the payload section begins with a period."""
    section = _payload_section_text(token)
    if not section.startswith("."):
        raise AssertionError(
            "compressed payload section must begin with a period; "
            f"section_prefix={section[:24]!r}"
        )
    print(
        f"compressed payload section len={len(section)} leading_period",
        flush=True,
    )
    return section


def require_uncompressed_payload_section(token: Any) -> str:
    """Require the payload section does not begin with a period."""
    section = _payload_section_text(token)
    if section.startswith("."):
        raise AssertionError(
            "uncompressed payload section must not begin with a period; "
            f"section_prefix={section[:24]!r}"
        )
    print(
        f"uncompressed payload section len={len(section)} no_leading_period",
        flush=True,
    )
    return section


def uppercase_signature_letters(token: Any) -> str:
    """Uppercase letters in the signature section; keep the payload intact.

    Full-token uppercasing of a URL-safe token also rewrites the
    URL-safe encoding of the payload (the alphabet is case-sensitive).
    Holding the payload section fixed isolates L201's signature-mismatch
    refusal from that encoding covariate. Raises if *token* is not text
    or the transform is a no-op — never returns a sentinel.
    """
    if not isinstance(token, str):
        raise AssertionError(
            "uppercase-signature observation requires a text token; "
            f"got {type(token).__name__}: {token!r}"
        )
    payload = payload_section(token)
    signature = signature_section(token)
    if not isinstance(payload, str) or not isinstance(signature, str):
        raise HarnessError(
            "payload_section/signature_section did not return text; "
            f"payload={type(payload).__name__} "
            f"signature={type(signature).__name__}"
        )
    if not signature:
        raise AssertionError(
            f"cannot uppercase an empty signature section; token={token!r}"
        )
    changed_sig = signature.upper()
    if changed_sig == signature:
        raise AssertionError(
            f"uppercasing the signature section was a no-op on {token!r}"
        )
    joined = join_payload_and_signature(payload, changed_sig)
    if not isinstance(joined, str):
        raise HarnessError(
            "rejoined token is not text; "
            f"got {type(joined).__name__}: {joined!r}"
        )
    if joined == token:
        raise AssertionError(
            f"uppercasing the signature section was a no-op on {token!r}"
        )
    print(
        f"uppercased signature letters payload_len={len(payload)} "
        f"sig_len={len(signature)}",
        flush=True,
    )
    return joined


def require_shorter_than(
    token: Any, limit: int = COMPRESSION_LENGTH_LIMIT
) -> str:
    """Require a text token shorter than *limit* characters."""
    text = require_urlsafe_text_token(token)
    if len(text) >= limit:
        raise AssertionError(
            f"token length {len(text)} is not shorter than {limit} characters"
        )
    print(f"token length {len(text)} < {limit}", flush=True)
    return text


def require_readme_mapping(loaded: Any) -> Any:
    """Require *loaded* recovers the README mapping (id equals 5, named name).

    Equality only — does not pin ``id`` to a Python ``int`` type.
    Lookup failure raises; it is never treated as a missing key.
    """
    try:
        ident = loaded["id"]
        name = loaded["name"]
    except Exception as exc:
        raise AssertionError(
            f"cannot read id/name from loaded object {loaded!r}: {exc}"
        ) from exc
    if ident != 5:
        raise AssertionError(f"mapping id is {ident!r}, expected 5")
    if name != PUBLIC_README_NAME:
        raise AssertionError(
            f"mapping name is {name!r}, expected {PUBLIC_README_NAME!r}"
        )
    print(
        f"readme mapping id={ident!r} name={name!r}",
        flush=True,
    )
    return loaded


def byte_echoes_on_failure(exc: BaseException) -> tuple[bytes, ...]:
    """Bytes carried on a failure object (payload echoes to strip).

    Probe errors raise. An empty tuple means there is nothing to strip,
    not that classification failed.
    """
    found: list[bytes] = []
    for item in _inspectable_text_and_bytes(exc):
        if isinstance(item, (bytes, bytearray)):
            found.append(bytes(item))
    print(f"failure byte echoes n={len(found)}", flush=True)
    return tuple(found)


def require_named_payload_markers(token: Any, obj: Any) -> str:
    """Require the PRD-named payload markers for the public objects.

    Thousand-letter ``a``: token shorter than 1000 and payload section
    begins with a period (L196 / L197). The small ``id``-42 mapping, the
    README mapping, and the integer list 1 through 4: payload section
    does not begin with a period (uncompressed path). Other objects are
    not given a marker here — probe errors still raise through the
    helpers this function calls.
    """
    require_exact_text_token(token)
    if obj == THOUSAND_A:
        require_shorter_than(token)
        require_compressed_payload_section(token)
    elif obj in (PUBLIC_ID_MAPPING, PUBLIC_README_MAPPING, PUBLIC_INTEGER_LIST):
        require_uncompressed_payload_section(token)
    return token


def require_id_equals(loaded: Any, ident: Any) -> Any:
    """Require *loaded* exposes ``id`` equal to *ident* (no type pin)."""
    try:
        value = loaded["id"]
    except Exception as exc:
        raise AssertionError(
            f"cannot read id from loaded object {loaded!r}: {exc}"
        ) from exc
    if value != ident:
        raise AssertionError(f"mapping id is {value!r}, expected {ident!r}")
    print(f"mapping id equals {ident!r} (got {value!r})", flush=True)
    return loaded


def repeated_letter(ch: str, n: int = 1000) -> str:
    """Repeat a single character *n* times. Raises if *ch* is not one letter."""
    if not isinstance(ch, str) or len(ch) != 1:
        raise HarnessError(
            f"repeated letter must be a single character; got {ch!r}"
        )
    if n < 1:
        raise HarnessError(f"repeat count must be positive; got {n!r}")
    return ch * n


def runtime_letter_other_than_a() -> str:
    """Sample an ASCII letter that is not ``a``. Raises if none can be drawn."""
    for _ in range(32):
        ch = runtime_ascii_letter()
        if ch != "a":
            print(f"runtime letter other than a: {ch!r}", flush=True)
            return ch
    raise HarnessError("could not sample an ASCII letter other than 'a'")


def _stdlib_urlsafe_decode(data: bytes) -> bytes:
    """Stdlib URL-safe decode used only to arrange fixtures. Raises on failure."""
    padded = data + b"=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise HarnessError(
            f"stdlib URL-safe decode rejected {data!r}: {exc}"
        ) from exc


def _stdlib_urlsafe_rejected(data: bytes) -> bool:
    """True when stdlib URL-safe decode fails. Probe errors raise."""
    padded = data + b"=" * (-len(data) % 4)
    try:
        base64.urlsafe_b64decode(padded)
    except Exception:
        return True
    return False


def arrange_invalid_urlsafe_token(secret: str | bytes, salt: str | bytes) -> bytes:
    """Signed token whose payload is not valid URL-safe encoding.

    The payload does not begin with a period. Arrangement confirms
    stdlib URL-safe decode fails before the token is signed. Not a
    product API.
    """
    # Stdlib URL-safe decode ignores non-alphabet bytes, so "!!!" decodes
    # as empty. Incorrect padding (one alphabet character + added '=')
    # is what the stdlib actually refuses.
    candidates = (
        b"A",
        b"B",
        b"1",
        b"-",
        b"_",
        b"A===",
        b"xy",
    )
    chosen: bytes | None = None
    for raw in candidates:
        if raw.startswith(b"."):
            continue
        if _stdlib_urlsafe_rejected(raw):
            chosen = raw
            break
    if chosen is None:
        raise HarnessError(
            "could not arrange a payload that stdlib URL-safe decode rejects"
        )
    token = signed_garbage_token(chosen, secret=secret, salt=salt)
    print(
        f"arranged invalid URL-safe encoding payload={chosen!r} "
        f"token_len={len(token)}",
        flush=True,
    )
    return token


def arrange_invalid_compressed_token(
    secret: str | bytes, salt: str | bytes
) -> bytes:
    """Signed token that claims compression but is not valid compressed data.

    Payload is a period plus stdlib URL-safe encoding of bytes that are
    not zlib data. Arrangement confirms: decode after stripping the
    period succeeds, and stdlib decompress fails. Not a product API.
    """
    raw_candidates = (
        b"not-zlib-data",
        b"xxxx",
        b"\x00\x01\x02\x03hello",
        b"plain-text-not-deflate",
    )
    for raw in raw_candidates:
        encoded = base64.urlsafe_b64encode(raw).rstrip(b"=")
        try:
            decoded = _stdlib_urlsafe_decode(encoded)
        except HarnessError:
            continue
        if decoded != raw:
            continue
        try:
            zlib.decompress(decoded)
        except Exception:
            payload = b"." + encoded
            token = signed_garbage_token(payload, secret=secret, salt=salt)
            print(
                f"arranged invalid compressed payload={payload!r} "
                f"token_len={len(token)}",
                flush=True,
            )
            return token
        # decompress succeeded — this candidate is not "invalid compressed"
    raise HarnessError(
        "could not arrange period + URL-safe encoding of non-compressed bytes"
    )


