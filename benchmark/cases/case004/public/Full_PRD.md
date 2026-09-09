# Signtoken — Full Product Requirements Document

## Product overview

**Signtoken** is a Python library of helpers for passing data to untrusted environments and getting it back intact. A token is cryptographically signed so that a later load can tell whether anyone changed the payload. The receiver can read the data; they cannot produce a different payload that still verifies, unless they also have the secret key.

The product’s own three-line summary of what it delivers:

- Data is cryptographically signed so a token that has been tampered with is rejected.
- How the payload is serialized is customizable. The default is JSON.
- A timestamp can be recorded at sign time and checked automatically on load. Data is compressed when that actually shortens a URL-safe token.

A first-time integrator constructs a URL-safe serialize-and-sign helper with a secret key and a salt, dumps a mapping such as a user id and a name, hands the resulting text token to a client or email link, and later loads that same token to recover the mapping. That README path is specified under FP-04. It rests on the basic signer (FP-01) and the serialize-and-sign helper (FP-02). Timestamped helpers (FP-03) add an age check on top of those.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished Signtoken product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Secret key** | A value only the signer’s owner should know. It may be one key or a list of keys oldest-to-newest for rotation. Changing the secret invalidates tokens that were signed with keys no longer in the list. |
| **Salt** | Extra material mixed with the secret to isolate signing contexts (for example an account-activation context versus an upgrade context). The salt does not have to be secret; it does have to differ between contexts that must not accept each other’s tokens. |
| **Token** | The signed string or byte string emitted by a helper. A valid token verifies and yields the original payload; a tampered token does not. |
| **Signer** | The basic helper: it signs raw byte values and later verifies them. It does not serialize objects and does not record a timestamp. Specified in FP-01. |
| **Serializer** | A helper that serializes an object with an internal dump/load object (JSON by default), then signs that payload with a signer. Specified in FP-02. |
| **Timestamped signer / timestamped serializer** | The signer and serializer variants that also record signing time and can refuse a token older than a caller-supplied maximum age. Specified in FP-03. |
| **URL-safe serializer** | A serializer whose tokens use only a URL-safe alphabet, and that compresses the payload when compression shortens it. Specified in FP-04. The URL-safe timestamped serializer is the same encoding plus FP-03’s age check. |
| **Separator** | The delimiter between the payload, any timestamp field, and the signature. The product default is a period. |
| **Digest** | The hash function used as the intermediate step of the default HMAC signature. The product default is SHA-1. |
| **Key-derivation scheme** | How the signing key is derived from the secret and the salt. The four built-in names are `concat`, `django-concat`, `hmac`, and `none`. The product default is `django-concat`. |
| **Fallback signing configuration** | An extra signing setup a serializer tries when the current configuration cannot verify a token, so parameters can be upgraded without instantly invalidating old tokens. |
| **Unsafe load** | An inspection entry for signature problems: it reports whether the signature verified, and yields the payload when that payload can still be decoded. A signature mismatch does not abort the caller. It does not make a bad token valid. When the signature is valid but the payload cannot be deserialized, the caller observes the same payload-decode failure as ordinary load. |
| **Core capability** | A user-observable capability that reflects Signtoken’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

Signtoken is a **library**, not a command users type. Integrators install the package and construct helpers in Python.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- The signer: sign a value, recover the original bytes from a valid token, check validity without recovering the payload, reject a tampered or separator-less value, isolate contexts with a salt, rotate keys, choose a digest and a key-derivation scheme, and opt into HMAC or a no-op algorithm (FP-01).
- The serializer: dump an object to a signed token and load it back; dump and load through a file stream; inspect a failed signature; unsafe load; per-call salt; custom dump/load object; fallback signing configurations (FP-02).
- Timestamped signing and serialize-and-sign: record signing time, enforce a maximum age in seconds, return the signing time as a timezone-aware UTC datetime, and distinguish expiry from a missing or malformed timestamp and from a mere signature mismatch (FP-03).
- URL-safe serialize-and-sign, with and without timestamps: tokens restricted to a URL-safe alphabet, compression when it shortens the payload, and the README round-trip of a mapping through a URL-safe helper (FP-04).

Standalone URL-safe encoding helpers exist so signatures can be encoded; they are not a separate core capability. Failure kinds (signature mismatch, payload that will not deserialize, missing or malformed timestamp, expired signature) are specified with the helper that raises them, not as their own feature point.

## Non-functional constraints

- **Form factor:** A pure-Python library. No compiled extensions, native code, GPU, or accelerator are required or claimed. Zero declared runtime dependencies.
- **Language:** Python 3.10 or newer.
- **Platforms:** Intended to work on Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host able to import the installed package and run Python. There is no accelerator profile.
- **Integrity, not confidentiality:** A verified token yields the original object. The payload is not encrypted. Anyone who can see a default JSON token can read the JSON text in it; they still cannot forge a new payload that verifies without the secret.
- **Default digest:** SHA-1 used as the HMAC intermediate. The hash’s collision story for standalone SHA-1 does not apply to this HMAC use; a project that wants a different digest configures one (FP-01, FP-02).
- **Default key derivation:** `django-concat`.
- **Default separator:** a period.
- **Default payload format (serializer):** JSON from the language’s built-in JSON library. The URL-safe helper uses compact JSON (no extra whitespace between tokens) so tokens stay short.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real Signtoken behavior matches the described outcomes when a helper is constructed with the named secret, salt, and options, then used to sign or dump and to recover or load.
- **Absent / hollow:** A helper that concatenates a fixed suffix and always accepts it back; a helper that always returns the input object without verifying; a helper that encrypts but cannot detect a bit flip; a timestamped helper that ignores maximum age; a URL-safe helper that emits characters that cannot appear in a URL.

Cheaper proxies (hard-coded tokens, skipping the signature check, treating every token as valid, or substituting a different library’s token format) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces Signtoken’s signer, serializer, timestamp check, or URL-safe encoding for a core capability.

**Negative control (Python / package substrate):** When Signtoken is deliberately not importable in an isolated subprocess (removed from the import path), an application that depends on it must fail to start with a hard error — not pass silently or skip. When the interpreter is present and the package is installed from this tree, constructing a signer with secret `secret-key`, signing the text `my string`, and recovering that token yields the original value as bytes. Output-equality alone is not proof that the real package ran.

## Non-goals

- Encrypting payloads so the receiver cannot read them. Signtoken signs; it does not hide.
- Being a general-purpose JWT / JWS stack. JSON Web Signature helpers were removed; they are not part of this product.
- Shipping a command-line program, HTTP server, or cookie framework. Those are application patterns that *use* tokens; they are not Signtoken commands.
- Treating the exported URL-safe base64 encode/decode utilities as a graded core capability. They exist to serve the signer and the URL-safe serializer.
- A header-bearing token format. A header-related failure kind exists on the exception types for historical reasons; no remaining public helper emits a separate signed header.
- Guaranteeing a particular token throughput or token-size benchmark beyond the compression obligation in FP-04.
- Key-generation or key-storage machinery. How an application creates and rotates the list of secrets is outside the library; the library accepts one key or a list (FP-01).

---

## Feature points

### FP-01: Cryptographic signing of byte values

**Public entry:** Signtoken’s signing helper, constructed with a secret key. The caller may also supply a salt, a separator, a digest, a key-derivation scheme, and a signing algorithm. This is the basic system: it signs bytes (or text, which is encoded as UTF-8) and later verifies them. It does not serialize objects (FP-02), does not record a timestamp (FP-03), and does not rewrite the payload into a URL-safe alphabet (FP-04).

**Normal behavior:**

- Constructing a signer with secret `secret-key` and signing the text `my string` yields a byte-string token. Recovering that same token with the same signer yields `my string` as bytes. A separate validity check on that token reports success without returning the payload. The recovered value is always bytes: if the input was text, it was encoded as UTF-8 at sign time, and recovery does not say whether the original was text or bytes.
- The token is the payload, then the separator, then a signature. The default separator is a period. Replacing that period in a signed token with a different character such as `*` makes the validity check report failure and recovery refuse the token.
- Changing the payload of a valid token — for example replacing the bytes `my` with `other` in a token that was signed for `my string` — makes the validity check report failure and recovery refuse the token.
- Truncating the signature of a valid token makes recovery refuse the token. That failure still carries the original payload bytes for inspection: after signing `b` and chopping the last byte of the token, the failure still exposes payload `b`. The validity check reports failure.
- Two signers that share the secret `secret-key` but use different salts produce tokens that the other will not recover. The same salt and secret on both sides round-trips. Under the `none` key-derivation scheme the salt is not mixed in, so two such signers that differ only in salt still recover each other’s tokens.
- When the caller omits the salt, a product-defined default salt is used. Two signers constructed the same way with the same secret and no caller salt interchange tokens.
- The secret may be a list of keys **oldest to newest**. Signing uses the **last** (newest) key. Recovery tries keys from newest to oldest and succeeds if any remaining key verifies. A token produced with secret `a` is accepted by a signer whose secrets are `a` then `b`. After the list becomes only `b`, that same token is refused. A new token produced with secrets `a` then `b` is refused by a signer that only has `a`, and accepted by a signer that has `b`.
- The four built-in key-derivation schemes are `concat`, `django-concat`, `hmac`, and `none`. The default is `django-concat`. For each of those four names, a signer constructed with that scheme, secret `secret-key`, and value `value` round-trips: recovering a token just signed yields `value` as bytes. A token produced under `hmac` is refused by a `django-concat` signer that did not produce it.
- The default digest is SHA-1. A signer given SHA-1 explicitly produces the same token as one that leaves the digest at the default. A signer given a different digest such as MD5 still round-trips under that same signer. A SHA-512 digest produces a longer signature than SHA-1; a SHA-1 signer without fallbacks (FP-02) does not recover a SHA-512 token.
- The default signing algorithm is HMAC using the configured digest. The caller may instead supply a no-op algorithm that emits an empty signature; signing then recovering `value` still yields `value` as bytes. The caller may supply a different algorithm; tokens from HMAC and from that other algorithm do not interchange.

**Boundary / error behavior:**

- Constructing a signer whose separator is a hyphen is refused: ASCII letters, digits, hyphen, underscore, and equals are not allowed as separators because they can appear in the encoded signature. The same refusal applies to a letter, a digit, an underscore, or an equals sign as the separator. A period is accepted.
- Recovering a value that does not contain the separator at all is refused as a signature failure. The validity check reports failure. This is distinguishable from a token that has a separator but a wrong signature: both fail, and neither recovers a verified value.
- An unrecognized key-derivation name (any name other than the four listed above) is not treated as the default. Signing a value under that name does not succeed: no verified token is produced.
- A no-op algorithm does **not** provide tamper detection. HMAC is the configuration that must reject a changed payload. A stub that always accepts is not an HMAC signer.
- A wrong secret, a flipped bit in the payload or signature, or a wrong salt (except under `none`) all refuse recovery. None of those paths returns the original value as a successful recovery.

**Verifiable oracle:**

- Success: signer secret `secret-key`, sign `my string`, recovery yields `my string` as bytes; a validity check on that token is success; a validity check after replacing the separator with `*` is failure and recovery refuses; replacing `my` with `other` in the token is refused; a truncated signature is refused and the failure still exposes payload `b` when the original value was `b`; salts that differ cannot recover each other’s tokens except under `none`, where they still recover; secrets `a` then `b` still recover a token made with only `a`, and after dropping `a` that token is refused; each of `concat`, `django-concat`, `hmac`, and `none` round-trips; default digest matches explicit SHA-1; hyphen as separator is refused at construction; unknown derivation does not produce a successful signature.
- Failure / absence: recovery always returns the input; a changed payload is accepted; a list of secrets only uses the first key so rotated-in keys cannot verify old tokens; hyphen is accepted as a separator; only one derivation scheme works; SHA-1 is not the default; a validity check cannot be told apart from recovery (for example it refuses with a failure instead of reporting failure, or always reports success).

---

### FP-02: Serialize and sign structured objects

**Public entry:** Signtoken’s serialize-and-sign helper, constructed with a secret key. The caller may also supply a salt, an internal dump/load object, extra dump options, a signer type, signing options, and fallback signing configurations. This helper wraps a signer (FP-01) so callers can round-trip objects other than raw bytes. It does not add a timestamp unless the timestamped serializer of FP-03 is used, and it does not force a URL-safe alphabet unless the URL-safe helper of FP-04 is used.

**This feature point uses FP-01.** Secret lists, salts, separators, digests, and key-derivation schemes behave as in FP-01 for the signer this helper constructs. The obligations below are the object round-trip, the JSON default, customization, fallbacks, and inspection.

**Normal behavior:**

- Dumping then loading the same object with the same helper recovers an equal object. This holds at least for: JSON null, JSON true, a text string, a list of the integers 1, 2, and 3, and a mapping whose `id` is 42. The default internal dump/load object is the language’s JSON library. For that default, the token for the list of integers 1 through 4 includes that list’s JSON text (including spaces after commas), then the separator, then a signature.
- When the internal dump/load object returns text, dump returns text. When it returns bytes, dump returns bytes. Load accepts either text or bytes for a given token.
- The same object can be dumped into a file stream and loaded back from that stream. The loaded object equals the original. An unsafe load from that stream on a valid token reports that the signature is valid and yields the object.
- A dump that passes an explicit salt `other` produces a token that the same helper will not load unless that same salt `other` is passed to load. Loading with salt `other` recovers the object. Loading with the helper’s default salt refuses the token as a signature mismatch. Under the `none` key-derivation scheme the salt is not mixed in, so that default-salt load still recovers the object, as in FP-01.
- The caller may replace the internal dump/load object with another object that has dump and load. A helper configured that way round-trips values that object can represent. A helper that still uses JSON cannot load a token produced by a helper whose dump format is not JSON: if the signature still verifies, that refusal is a payload-decode failure, not a signature mismatch. Extra dump options the caller attaches are forwarded into the internal dump. With the default JSON dump object, asking dump to skip keys that are not basic JSON key types, then dumping a mapping whose only key is an empty tuple, produces a token that loads as an empty mapping.
- The caller may replace the signer type or the signing options (for example a different key-derivation scheme). Dump then load still round-trips under that helper. A token from the default helper is not equal to a token for the same object from a helper whose derivation is `hmac`, and the two helpers do not load each other’s tokens.
- Fallback signing configurations are tried when the current signer cannot verify a token, in the order the caller listed them, until one verifies or all fail. Each fallback item is one of: a mapping of signing options (for example a digest) applied to the helper’s signer type; an alternative signer type, constructed with the helper’s secret, salt, and current signing options; or a pair of a signer type and a mapping of signing options. Concrete case: a helper that signs with SHA-256 dumps a mapping whose `id` is 42; a second helper whose current digest is SHA-1 but that lists SHA-256 as a fallback loads that token and recovers the mapping; a third helper whose current digest is SHA-1 and that has no fallback refuses the token.
- The default digest on a serializer is SHA-1, matching FP-01. Dumping the JSON list containing only 42 with no digest override produces the same token as dumping it with SHA-1 set explicitly. Dumping it with SHA-512 produces a different token with a longer signature. A SHA-1 helper without a SHA-512 fallback cannot load the SHA-512 token.
- After a signature mismatch on load (for example the last character of a valid token is chopped off), the failure is distinguishable as a signature problem, and the unsigned payload is still available on that failure. Decoding that inspected payload recovers the original object. That does not count as a successful load of the token.
- Unsafe load of a valid token returns a pair: signature valid, and the original object. Unsafe load of a token whose signature was chopped off returns: signature not valid, and the original object (when the payload can still be decoded). Unsafe load of a chopped token whose remaining payload also cannot be decoded returns: signature not valid, and no object. A signature mismatch never aborts the caller: the pair is always returned. Unsafe load does not make a bad signature look valid.

**Boundary / error behavior:**

- A token that was dumped and then transformed in any of these ways is refused as a signature mismatch on load: all letters uppercased; an extra character appended; the first character replaced; the separator removed. None of those transformations yields a successful load of the original object.
- When the signature is valid but the payload cannot be deserialized (the payload bytes were shortened and then signed so the signature matches garbage), ordinary load refuses with a payload-decode failure, not a signature mismatch. That failure retains the original decode error. This is distinguishable from a signature mismatch. Unsafe load does **not** convert that case into a success pair: the caller observes the same payload-decode failure as ordinary load.
- A signature mismatch and a payload-decode failure are distinguishable from each other and from success. A stub that raises a single generic error for every bad token does not implement these two failure kinds.
- If every signer including fallbacks fails to verify, load refuses with a signature mismatch. It does not return a decoded object as a successful load.
- Unsafe load never treats a bad signature as success: the first item of the pair is false whenever verification failed, even if a payload is still yielded for inspection.

**Verifiable oracle:**

- Success: dump then load of null, true, text, the list of integers 1 through 3, and a mapping whose `id` is 42 recovers the same object; the default token for the list of integers 1 through 4 includes that JSON text; dump into a stream and load back recovers a mapping whose `id` is 42; salt `other` on dump is refused by default load and accepted by load with salt `other`, except under `none`, where default load still recovers; a JSON helper’s load of a non-JSON token is a payload-decode failure when the signature verifies; a SHA-256 token loads on a SHA-1 helper only when SHA-256 is a fallback; default digest matches SHA-1 and differs from SHA-512; chopped-signature load is a signature mismatch whose inspected payload still decodes to the object; unsafe load of a valid token is (valid, object) and of a chopped-signature token is (not valid, object); unsafe load of a chopped token whose payload also cannot be decoded is (not valid, no object); with default JSON and skip-non-basic-keys, a mapping whose only key is an empty tuple loads back as an empty mapping.
- Failure / absence: dump is unsigned JSON with no signature check on load; a changed token still loads; salt is ignored; fallbacks are ignored so digest upgrades invalidate every old token; SHA-512 and SHA-1 tokens are interchangeable without fallbacks; unsafe load either aborts on a mere signature mismatch or always reports valid; unsafe load reports success for a valid signature over undecodable garbage; payload-decode failure cannot be told apart from a signature mismatch; a non-JSON dump/load object cannot be attached.

---

### FP-03: Timestamped signatures and expiry

**Public entry:** Signtoken’s timestamped signer and timestamped serialize-and-sign helper. Each is constructed like the corresponding helper in FP-01 or FP-02, and records the signing time in the token. On recovery or load, the caller may supply a maximum age in seconds and may ask to receive the signing time. **This feature point refines FP-01 and FP-02:** the basic signer and serializer do not record or check age. A timestamped helper that is also URL-safe is specified with FP-04; age rules here still apply there.

A timestamped signer still satisfies every FP-01 obligation (round-trip of bytes, missing separator, changed payload, invalid separator, derivation schemes, digest, algorithms, secret lists). A timestamped serializer still satisfies every FP-02 obligation (object round-trip, tamper transforms, salt, fallbacks, unsafe load, streams). The obligations below are the time field and the age check.

**Normal behavior:**

- Signing a value with the timestamped signer produces a token that still recovers to the original bytes when no maximum age is supplied. Dumping an object with the timestamped serializer and loading it with no maximum age recovers the object, as in FP-02.
- The token contains a time field between the payload and the signature (separated by the same separator as FP-01). Recovering or loading with a request to return the signing time yields the original value (bytes for the signer, the object for the serializer) **and** a datetime that is timezone-aware in UTC and equal to the time at which the token was signed.
- When a maximum age of 10 seconds is supplied, checking the token 1 second after signing succeeds and yields the original value. After 11 seconds have passed since signing, the same check with maximum age 10 seconds refuses as **expired**. Expiry is distinguishable from a signature mismatch and from a missing or malformed timestamp. A validity check that is given the same maximum age reports failure on that expired token and success on the one-second-old token.
- An expired failure still carries the original payload. For the timestamped serializer, decoding that inspected payload recovers the original object (for example a mapping whose `id` is 42). The failure also exposes the signing time as a timezone-aware UTC datetime equal to the time of signing.
- A token whose signing time is in the future relative to the clock used at check time, when a maximum age is supplied, is also expired (age less than zero is not treated as valid). That expiry still exposes a datetime for the signing time.
- Unsafe load on the timestamped serializer, when given a maximum age, still returns the pair described in FP-02 rather than aborting the caller on expiry or on a signature mismatch. An expired token is not reported as a valid signature.
- When a timestamped serialize-and-sign helper has fallback signing configurations, a token whose signature verifies under the current configuration but whose age exceeds the maximum is refused as expired. Further fallback configurations are not tried. Concrete case: a helper that currently signs with SHA-256 and lists SHA-1 as a fallback dumps a mapping whose `id` is 42; eleven seconds later, load with maximum age 10 is expired, not a signature mismatch and not a successful load via the fallback.

**Boundary / error behavior:**

- A token produced by the **non-timestamped** signer of FP-01 (payload and signature only, no time field) is refused by the timestamped signer as a **missing timestamp**. That failure is distinguishable from a signature mismatch and from expiry. The signing-time field on that failure is absent.
- A token whose time field is not a well-formed timestamp (for example a non-timestamped signer signs a payload that happens to contain a period and a dummy time-looking suffix that does not decode to a time) is refused as a **malformed timestamp**. That failure is distinguishable from expiry and from a missing timestamp. The signing-time field on that failure is absent.
- When a timestamped token's time field is replaced with an encoding that cannot be converted to a calendar date, recovery is refused, the signing-time field is absent, and that refusal is not expiry: an expired unreplaced token still exposes a signing-time datetime, and the same replace-without-re-sign of an in-range time field still exposes a signing-time datetime.
- A timestamped token whose payload was changed (for example `my` replaced with `other` in a signed `my string`) is refused as a time-signature failure, not as a successful recovery. When the time field can still be decoded, that failure exposes a signing-time datetime.
- Expiry is not a successful load. A helper that returns the object after the maximum age has elapsed, even with a warning, does not implement this feature point.

**Verifiable oracle:**

- Success: timestamped sign of `value` then recover with maximum age 10 one second later yields `value` as bytes; after eleven seconds the same call is expired; a validity check with maximum age 10 is success at one second and failure at eleven seconds; asking for the signing time returns a timezone-aware UTC datetime equal to the frozen signing instant; timestamped dump of a mapping whose `id` is 42 then load with maximum age 10 one second later yields that mapping, and after eleven seconds is expired with inspected payload decoding to that mapping and with signing time equal to the signing instant; a future clock with maximum age 10 is expired; a non-timestamped token is refused as a missing timestamp; a malformed time field is refused as malformed, not as expiry; an expired SHA-256 token on a helper that lists SHA-1 as a fallback is still expired, not loaded via the fallback.
- Failure / absence: age is ignored so an eleven-second-old token still loads; expiry cannot be told apart from a bad signature; signing time is naive or not UTC; a non-timestamped token is accepted; a malformed time is treated as expiry or as success; an expired token is accepted because a fallback exists; the timestamped serializer cannot dump and load objects as in FP-02.

---

### FP-04: URL-safe tokens

**Public entry:** Signtoken’s URL-safe serialize-and-sign helper, and the URL-safe timestamped serialize-and-sign helper. The README’s first example is the URL-safe helper: construct it with a secret key and a salt, dump a mapping, pass the text token through an untrusted environment, and load it back. **This feature point refines FP-02:** the token is text in a restricted alphabet, and the payload is compressed when that shortens it. The URL-safe timestamped helper also applies FP-03.

The URL-safe helper still satisfies the serializer behavior of FP-02 (object round-trip, tamper refusal, salt, fallbacks, unsafe load, streams, custom dump/load where attached). The URL-safe timestamped helper also satisfies FP-03’s maximum-age and signing-time behavior. The obligations below are the alphabet, compactness, compression, and the README round-trip.

**Normal behavior:**

- Constructing a URL-safe helper with secret `secret key` and salt `auth`, dumping the mapping whose `id` is 5 and whose `name` is `signtoken`, and loading the resulting token recovers that mapping, including the name `signtoken`. The token is text, not bytes.
- Every character of a URL-safe token is one of: uppercase letters, lowercase letters, digits, underscore, hyphen, or period. The token does not contain a plus sign, a slash, an equals sign, a space, a square bracket, or a quote. For the list of integers 1 through 4, the default (non-URL-safe) serializer’s token includes JSON list text with brackets and spaces; the URL-safe token for that same list does not include brackets or spaces, and loading it still yields the list of integers 1 through 4.
- The URL-safe helper serializes JSON without extra whitespace so tokens stay short. Dump then load still recovers the object.
- When compression shortens the payload, the helper emits a compressed token; when it would not shorten, the helper leaves the payload uncompressed. Both forms load. A compressed token is distinguishable from an uncompressed one: the payload section of a compressed token begins with a period; the payload section of an uncompressed token does not. Concrete compression case: dumping the string of the letter `a` repeated one thousand times produces a token that loads back to that same string, that contains only the URL-safe alphabet above, that is **shorter than one thousand characters**, and whose payload section begins with a period. A helper that never compresses emits a much longer token for that string and fails this length check. A small mapping such as one whose `id` is 42 also round-trips, and its payload section does not begin with a period (this is the uncompressed path).
- The URL-safe timestamped helper dumps and loads the same objects, still as URL-safe text. A maximum age of 10 seconds accepts a load one second after dump and refuses as expired after eleven seconds, as in FP-03. Asking for the signing time returns the object and a timezone-aware UTC datetime. The thousand-letter-`a` string also round-trips on the timestamped URL-safe helper, still yields a token shorter than one thousand characters, and still begins its payload section with a period.

**Boundary / error behavior:**

- A URL-safe token that is transformed the way FP-02 describes (uppercased, extra character appended, first character replaced, separator removed) is refused as a signature mismatch. Load does not return the original object.
- A payload that is not valid URL-safe encoding, or that claims to be compressed (payload section begins with a period) but is not valid compressed data, is refused as a payload-decode failure when the signature otherwise matches garbage that cannot be decoded. That failure is distinguishable from a signature mismatch.
- A URL-safe timestamped helper refuses an uncompressed token that has no time field (for example a mapping whose `id` is 42 dumped by the non-timestamped URL-safe helper) as a missing timestamp (FP-03), even if the rest of the alphabet is URL-safe. The thousand-`a` token from that same non-timestamped helper (compressed, payload section begins with a period) is refused as a malformed timestamp, not as a missing timestamp.
- Characters outside the URL-safe alphabet are not required to be accepted. A token containing a plus sign or a slash is not a successful URL-safe load of a product-emitted token; product-emitted tokens never include those characters.

**Verifiable oracle:**

- Success: URL-safe helper secret `secret key`, salt `auth`, dump a mapping whose `id` is 5 and whose `name` is `signtoken`, load recovers that mapping; the token is text made only of letters, digits, underscore, hyphen, and period; URL-safe dump of the list of integers 1 through 4 loads as that list and the token has no square brackets and no spaces; a mapping whose `id` is 42 round-trips and its payload section does not begin with a period; the string of one thousand `a` characters round-trips, the token is shorter than one thousand characters, and its payload section begins with a period; the URL-safe timestamped helper does the same round-trips, enforces maximum age 10 seconds as in FP-03, and still compresses the thousand-`a` string below one thousand characters with a payload section that begins with a period.
- Failure / absence: tokens contain plus, slash, equals, space, or brackets; load of the README mapping does not recover `name`; the thousand-`a` token is not shorter than the string (no compression); compressed and uncompressed tokens cannot be told apart by whether the payload section begins with a period; the URL-safe helper returns bytes that are not URL-safe text; the timestamped URL-safe helper ignores maximum age; a changed URL-safe token still loads.
