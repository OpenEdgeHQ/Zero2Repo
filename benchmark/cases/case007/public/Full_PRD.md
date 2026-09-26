# Otpkit — Full Product Requirements Document

## Product overview

**Otpkit** is a Python library for generating and verifying one-time passwords. It is used to implement two-factor (2FA) or multi-factor (MFA) authentication in web applications and in other systems that require users to log in.

Open MFA standards are defined in RFC 4226 (HOTP: An HMAC-Based One-Time Password Algorithm) and RFC 6238 (TOTP: Time-Based One-Time Password Algorithm). Otpkit implements server-side support for both of these standards. Client-side support can be enabled by sending authentication codes to users over SMS or email (HOTP) or, for TOTP, by instructing users to use Google Authenticator, Authy, or another compatible app. Users can set up auth tokens in their apps by scanning otpauth URIs that Otpkit provides (typically rendered as QR codes by the integrator).

A first-time integrator generates a random shared secret, constructs a time-based helper with that secret, reads the code for the current clock, and checks a candidate code the user typed. The same secret can instead drive an HMAC-based helper whose codes are indexed by a counter the application stores. Either helper can emit an otpauth URI so a phone app can be provisioned; Otpkit can also parse such a URI back into a helper that produces the same codes.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished Otpkit product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

The security checklist in the project README (HTTPS, secret storage, replay denial in the application database, brute-force throttling, and considering FIDO U2F / WebAuthn for new applications) is **integrator guidance**, not a graded library obligation. Otpkit generates and verifies codes; it does not store used codes, rate-limit logins, or render QR images.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Shared secret** | The key stored on both the server and the client. Helpers consume it as a base32 string. Missing base32 padding is accepted. Letter case in the secret does not matter. |
| **One-time password / code** | The short value a helper emits or checks. A successful generation returns a **text string** of decimal digits (or, for unofficial Steam codes only, a different alphabet — see Non-goals). The string is exactly as wide as the configured digit count; leading zeros are kept. A code is never returned as a bare integer. |
| **HMAC-based helper (HOTP)** | A helper whose codes are indexed by a counter the caller supplies. Specified in FP-02. |
| **Time-based helper (TOTP)** | A helper whose codes are indexed by the current time, divided into fixed-length steps. Specified in FP-03. |
| **Digit count** | How many characters each code contains. The product default is 6. Construction refuses a count greater than 10. An otpauth URI may carry only 6, 7, or 8. |
| **Digest** | The hash function used inside HMAC. The product default is SHA1. SHA256 and SHA512 are also supported. MD5 and SHAKE-128 are refused. |
| **Starting counter** | For an HMAC-based helper, the counter value that relative count zero maps to. The product default is 0. The code for relative count N is the code for (starting counter + N). |
| **Time-step length** | For a time-based helper, how many seconds a code remains the current code. The product default is 30. |
| **Time-step number** | The integer number of time-step lengths that have elapsed from the Unix epoch to a given instant (using UTC when the instant is timezone-aware, and the host local timezone when it is timezone-naive). |
| **Acceptance window** | How many time steps on either side of a target instant a time-based check will still accept. Zero means only the target step. |
| **Account name** | The account label stored on a helper and written into an otpauth URI path. When the caller never supplies one, the product uses the placeholder Secret. |
| **Issuer** | The organization title stored on a helper and written into an otpauth URI (path prefix and query field). |
| **otpauth URI** | A provisioning URI whose scheme is otpauth, whose type is totp or hotp, and whose query carries at least the shared secret. Specified in FP-04 and FP-05. Compatible with the Google Authenticator Key URI Format. |
| **Core capability** | A user-observable capability that reflects Otpkit’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

Otpkit is a **library**, not a command users type. Integrators install the package and construct helpers in Python. There is no command-line product, no HTTP server, and no QR-code renderer.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- Random shared-secret generation as a base32 string or as a hex string, with a 160-bit minimum (FP-01).
- HMAC-based codes: emit the code for a counter, and accept or reject a candidate at a counter, matching RFC 4226 (FP-02).
- Time-based codes: emit the code for the current clock or for a given instant, accept or reject a candidate with an optional acceptance window, and report the matching time-step number, matching RFC 6238 (FP-03).
- Build an otpauth URI from an HMAC-based or time-based helper so a compatible app can be provisioned (FP-04).
- Parse an otpauth URI back into a helper that produces the same codes and can rebuild an equivalent URI (FP-05).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library. No compiled extensions, native code, GPU, or accelerator are required or claimed. Zero declared runtime dependencies.
- **Language:** Python 3.8 or newer, including the CPython and PyPy implementations the project tests.
- **Platforms:** Intended to work on Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host able to import the installed package and run Python. There is no accelerator profile.
- **Code representation:** Generated codes are text strings of the configured width. An implementation that returns integers (so that a leading zero disappears) does not implement this product.
- **Secret representation:** Helpers take the shared secret as base32 text. A secret whose length is not a multiple of eight is accepted; the missing padding is not the caller’s problem. Hex secrets produced by FP-01 are for applications that want a hex-encoded key; the HOTP and TOTP helpers still consume base32.
- **Default digit count:** 6.
- **Default digest:** SHA1.
- **Default time-step length:** 30 seconds.
- **Default HMAC starting counter:** 0.
- **URI type set (finite):** totp and hotp. No other otpauth type is accepted.
- **URI algorithm set (finite):** SHA1, SHA256, SHA512.
- **URI digit-count set (finite):** 6, 7, and 8.
- **Versioning:** The package follows Semantic Versioning 2.0.0. That policy is background; it is not a graded runtime obligation.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real Otpkit behavior matches the described outcomes when a helper is constructed with the named secret and options, then used to emit or check a code, or to build or parse an otpauth URI.
- **Absent / hollow:** A helper that always returns a fixed six-digit string; a helper that accepts every candidate; a helper that returns integers so leading zeros vanish; a helper that ignores the counter or the clock; a URI builder that concatenates the secret into a non-otpauth string; a parser that never refuses a bad URI.

Cheaper proxies (hard-coded codes, skipping the HMAC, treating every candidate as valid, or substituting a different OTP library’s format) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces Otpkit’s HMAC-based helper, time-based helper, secret generator, or otpauth URI support for a core capability.

**Negative control (Python / package substrate):** When the interpreter is present and the package is imported from this tree, constructing an HMAC-based helper with the RFC 4226 example secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` and asking for the code at relative count 0 yields the six-character string `755224`, and checking that same string at relative count 0 succeeds. Output-equality alone is not proof that the real package ran.

## Non-goals

- Rendering QR codes, sending SMS or email, or shipping a phone client. Otpkit emits codes and otpauth URIs; the integrator renders and delivers them.
- Storing used codes, timestamps, or hashes in a database in order to deny replay. The README tells application authors to do that. The library check of a candidate does not consume the code: checking the same valid candidate twice at the same counter or the same instant succeeds both times. A time-based helper can report the matching time-step number (FP-03) so the application can refuse a repeated step; the library itself does not remember previous successes.
- Transport confidentiality, rate limiting, or secret-at-rest storage. Those are application obligations listed in the README checklist.
- FIDO U2F, WebAuthn, or the sister project Warpkit. The README recommends them for new applications; they are not this product.
- Steam TOTP. A third-party contribution exists that emits five-character Steam codes and can be recovered from an otpauth URI that carries a Steam encoder field. It is not described by a standard, is not officially supported, and is provided for reference only. It is **not** a graded core capability.
- A command-line program, HTTP server, or authentication framework.
- Guaranteeing a particular code-generation throughput.
- Treating packaging scripts, the Makefile, or the project test runner as product capabilities.

---

## Feature points

### FP-01: Random shared-secret generation

**Public entry:** Otpkit’s random-secret helpers. One helper emits a base32 secret compatible with Google Authenticator and other OTP apps. The other emits a hex-encoded secret for applications that want that format. Neither helper constructs an HMAC-based or time-based generator; FP-02 and FP-03 consume a secret the caller already has.

**Normal behavior:**

- Asking for a base32 secret with no length override yields a string of length 32. Every character is one of `A` through `Z` or `2` through `7`.
- Asking for a base32 secret of length 34 yields a string of length 34 from that same alphabet.
- Asking for a hex secret with no length override yields a string of length 40. Every character is one of `A` through `F` or `0` through `9`.
- Asking for a hex secret of length 42 yields a string of length 42 from that same hex alphabet.
- Each generation is a newly drawn string from the stated alphabet, not a single built-in constant. A helper that always returns the same canned 32-character base32 string, or the same canned 40-character hex string, does not implement this feature point.

**Boundary / error behavior:**

- Asking for a base32 secret of length 31 does not succeed. The caller observes a failure. No secret is returned.
- Asking for a hex secret of length 39 does not succeed. The caller observes a failure. No secret is returned.
- Lengths at or above the documented minimum (32 for base32, 40 for hex) succeed and return a string of exactly that length.

**Verifiable oracle:**

- Success: a default base32 secret has length 32 and uses only `A`–`Z` and `2`–`7`; a base32 secret of length 34 has length 34; a default hex secret has length 40 and uses only `A`–`F` and `0`–`9`; a hex secret of length 42 has length 42; the helper is not a constant function that always returns one canned secret.
- Failure / absence: the helper always returns one hard-coded string; a length of 31 or 39 is accepted; a default base32 result is not length 32; a default hex result is not length 40; the alphabet includes `0`, `1`, `8`, or `9` in a base32 secret, or letters outside `A`–`F` in a hex secret.

---

### FP-02: HMAC-based one-time passwords (HOTP)

**Public entry:** Otpkit’s HMAC-based helper, constructed with a shared secret in base32. The caller may also supply a digit count, a digest, an account name, an issuer, and a starting counter. This helper emits and checks codes indexed by a counter. It does not consult the clock (FP-03) and does not build or parse otpauth URIs (FP-04, FP-05).

**Normal behavior:**

- Constructing a helper with secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` (the RFC 4226 example secret: the base32 form of the 20-byte ASCII string `12345678901234567890`) and asking for the code at relative counts 0 through 9 yields these six-character strings, in order: `755224`, `287082`, `359152`, `969429`, `338314`, `254676`, `287922`, `162583`, `399871`, `520489`. Checking `520489` at relative count 9 succeeds. Checking `520489` at relative count 10 fails. Checking `520489` at relative count 10 a second time still fails.
- Constructing a helper with secret `base32secret3232` yields `260182` at relative count 0, `055283` at relative count 1, and `316439` at relative count 1401. Checking `316439` at relative count 1401 succeeds. Checking `316439` at relative count 1402 fails. The code at relative count 1 is the six-character string `055283`, including the leading zero — not the integer 55283.
- Constructing a helper with secret `N3OVNIBRERIO5OHGVCMDGS4V4RJ3AUZOUN34J6FRM4P6JIFCG3ZA` yields `737863` at 0, `390601` at 1, `363354` at 2, `936780` at 3, and `654019` at 4.
- A lowercase secret is accepted and produces the same codes as the same secret in uppercase. Secret `wrn3pqx5uqxqvnqr` is usable.
- The default digit count is 6 and the default digest is SHA1. An explicit SHA1 digest produces the same codes as leaving the digest at the default.
- When a starting counter of 1 is configured, the code at relative count 0 equals the code a default-start helper would emit at relative count 1. In particular, a helper built from secret `GEZDGNBV` with starting counter 1 emits `662488` at relative count 0 and `289363` at relative count 1.
- Checking a candidate succeeds when the candidate equals the expected code, or differs from it only by Unicode compatibility-equivalent characters. For secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` at relative count 0, the fullwidth-digit candidate `７５５２２４` succeeds. A candidate that is not compatibility-equivalent to the expected code fails.
- Generated codes are text strings. They are exactly as wide as the digit count. They are not integers.

**Boundary / error behavior:**

- Asking for the code at a negative relative count (for example −1) does not succeed. No code is returned. This is distinguishable from checking a wrong candidate, which returns a negative result and does not abort the caller.
- Constructing a helper with digit count 11 does not succeed. Digit count 6 is accepted. Digit count 8 is accepted.
- Constructing a helper with digest MD5 does not succeed. Constructing a helper with digest SHAKE-128 does not succeed. SHA1, SHA256, and SHA512 are accepted.
- Checking a code that belongs to a different counter fails. The helper does not advance or store a counter of its own; the caller always supplies the counter to check against.

**Verifiable oracle:**

- Success: RFC 4226 secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` at relative counts 0–9 matches the ten strings listed above; `520489` checks true at 9 and false at 10; the fullwidth-digit candidate `７５５２２４` succeeds at relative count 0; `base32secret3232` yields `260182` / `055283` / `316439` at 0 / 1 / 1401 and those check results; `055283` is a six-character string; starting counter 1 on secret `GEZDGNBV` yields `662488` at relative count 0; a negative relative count does not produce a code; digit count 11 is refused; MD5 and SHAKE-128 are refused.
- Failure / absence: codes are integers so `055283` becomes 55283; the RFC 4226 sequence does not match; a code for count 9 is accepted at count 10; a negative count yields a code; every candidate is accepted; MD5 is accepted; the helper consults the clock instead of the supplied counter.

---

### FP-03: Time-based one-time passwords (TOTP)

**Public entry:** Otpkit’s time-based helper, constructed with a shared secret in base32. The caller may also supply a digit count, a digest, an account name, an issuer, and a time-step length. This helper emits and checks codes indexed by time. **This feature point uses the same construction rules as FP-02** for digit count (default 6, greater than 10 refused) and digest (default SHA1; SHA256 and SHA512 accepted; MD5 and SHAKE-128 refused). Codes remain text strings of the configured width. The obligations below are the clock, the time-step, the acceptance window, and RFC 6238.

**Normal behavior:**

- The helper accepts either a Unix timestamp or a datetime as the instant to use. A timezone-aware datetime is read as UTC. A timezone-naive datetime is read in the host local timezone.
- Asking for the code at the current clock yields the same string as asking for the code at that same current instant supplied explicitly. Checking that string against the current clock, with no acceptance window, succeeds.
- After one full default time-step (30 seconds) has passed, checking the previous step’s code against the new clock, with no acceptance window, fails. Checking the same valid code twice at the same instant succeeds both times; the helper does not consume the code.
- Constructing a helper with secret `wrn3pqx5uqxqvnqr` and reading the current-clock code while the clock is frozen at Unix time 1297553958 yields `102705`. Checking `102705` at that frozen clock succeeds. Checking `102705` at Unix time 1297553958 + 30 fails.
- Constructing a helper with the RFC 4226 / RFC 6238 SHA1 secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` and the default six-digit width yields `050471` at Unix time 1111111111, `005924` at Unix time 1234567890, and `279037` at Unix time 2000000000. Those strings keep their leading zeros. Checking `050471` while the clock is frozen at 1111111111 succeeds. Checking `050471` at 1297553958 + 30 fails.
- Constructing an eight-digit helper with that same SHA1 secret matches RFC 6238 Appendix B: Unix 59 yields `94287082`; 1111111109 yields `07081804`; 1111111111 yields `14050471`; 1234567890 yields `89005924`; 2000000000 yields `69279037`; 20000000000 yields `65353130`.
- Constructing an eight-digit helper with SHA256 and the RFC 6238 SHA256 secret (the base32 form of the 32-byte ASCII string `12345678901234567890123456789012`) matches RFC 6238 Appendix B: Unix 59 yields `46119246`; 1111111109 yields `68084774`; 1111111111 yields `67062674`; 1234567890 yields `91819424`; 2000000000 yields `90698825`; 20000000000 yields `77737706`.
- Constructing an eight-digit helper with SHA512 and the RFC 6238 SHA512 secret (the base32 form of the 64-byte ASCII string `1234567890123456789012345678901234567890123456789012345678901234`) matches RFC 6238 Appendix B: Unix 59 yields `90693936`; 1111111109 yields `25091201`; 1111111111 yields `99943326`; 1234567890 yields `93441116`; 2000000000 yields `38618901`; 20000000000 yields `47863826`.
- A time-step length other than 30 changes which instants share a code. A helper with secret `GEZDGNBV`, SHA1, and a 60-second step emits `734055` at Unix time 30 and `662488` at Unix time 60 — the same strings a 30-second helper emits at Unix time 0 and Unix time 30.
- The caller may ask for the code at a given instant plus a whole-step offset. For secret `ABCDEFGH` at Unix time 200 (default 30-second step), offset 0 yields `028307`, offset −1 yields `451564`, and offset +1 yields `681610`.
- Checking with an acceptance window of 1 step at Unix time 200 for secret `ABCDEFGH` accepts `451564`, `028307`, and `681610`, and rejects `195979`. Checking with a window of 0 accepts only the on-step code `028307`.
- The caller may ask a check to return the matching time-step number when the candidate is accepted. For secret `ABCDEFGH` at Unix time 200 with a window of 1: `451564` yields 5, `028307` yields 6, and `681610` yields 7. `195979` does not yield a time-step number; the caller observes failure. The library does not remember previous successes.
- Checking a candidate uses the same compatibility-equivalent rule as FP-02: a fullwidth-digit form of the expected code succeeds; a candidate that is not compatibility-equivalent fails.

**Boundary / error behavior:**

- For secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ`, asking for the code at Unix time −1 or at −29.5 succeeds and yields `755224` (those instants fall on the epoch step). Asking for the code at Unix time −30 does not succeed. No code is returned.
- Asking a matching-time-step check to use a negative acceptance window does not succeed. A window of 0 or a positive window is accepted.
- Digit count 11, digest MD5, and digest SHAKE-128 are refused at construction, as in FP-02.
- A wrong code, a code from outside the acceptance window, or a code from a different secret fails the check. Failure of a check is a negative result, not an aborted caller, except for the negative-window case above.

**Verifiable oracle:**

- Success: frozen clock 1297553958 with secret `wrn3pqx5uqxqvnqr` yields and accepts `102705`, and rejects it 30 seconds later; RFC six-digit times 1111111111 / 1234567890 / 2000000000 yield `050471` / `005924` / `279037`; the RFC 6238 eight-digit SHA1, SHA256, and SHA512 tables above match; a 60-second step on `GEZDGNBV` yields `734055` at time 30; `ABCDEFGH` at time 200 yields `028307` / `451564` / `681610` at offsets 0 / −1 / +1; a window of 1 accepts those three and rejects `195979`; a matching-step check returns 5, 6, and 7 for those three codes and fails for `195979`; Unix −1 yields `755224` and Unix −30 is refused; a negative acceptance window on the matching-step check is refused; current-clock generation equals generation for that same instant; a fullwidth-digit form of an expected code succeeds a check, as in FP-02.
- Failure / absence: the helper ignores the clock and always returns one string; leading zeros are dropped; SHA256 codes match the SHA1 table; a window of 1 still rejects the adjacent-step codes; a matching-step check never returns a number; Unix −30 yields a code; a code remains valid after a full time-step with window 0; MD5 is accepted.

---

### FP-04: otpauth provisioning URI generation

**Public entry:** The provisioning-URI builder on an HMAC-based helper (FP-02) or a time-based helper (FP-03). The caller may override the account name, the issuer, and — for an HMAC-based helper — the starting counter written into the URI. The caller may also attach extra query fields; an image field is accepted only when it is a valid https URL. This feature point emits URIs. Parsing them is FP-05.

**Normal behavior:**

- The URI uses scheme otpauth. A time-based helper produces type totp. An HMAC-based helper produces type hotp. The path is a percent-encoded label. The query always includes the shared secret.
- When the caller supplies an issuer, the path is the issuer, a colon, and the account name, each percent-encoded, and the query also includes the issuer. When no issuer is supplied, the path is the account name alone.
- When no account name was ever supplied, the path uses the placeholder Secret.
- Special characters in the label and query are percent-encoded. `@` becomes `%40`. `!` becomes `%21`. A space becomes `%20` (not a plus sign).
- A time-based helper constructed with secret `JBSWY3DPEHPK3PXP`, account `alice@google.com`, and issuer `Secure App` builds exactly: `otpauth://totp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App`.
- An HMAC-based helper with that same secret, account, and issuer, and starting counter 0, builds exactly: `otpauth://hotp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App&counter=0`.
- A time-based helper constructed with secret `S46SQCPPTCNPROMHWYBDCTBZXV` and no account or issuer builds exactly: `otpauth://totp/Secret?secret=S46SQCPPTCNPROMHWYBDCTBZXV`. Checking a candidate does not change a later build of that URI: after checking `123456`, the URI is still that same string.
- An HMAC-based helper with secret `wrn3pqx5uqxqvnqr` and account `alice@example.com` (no issuer) has path `/alice%40example.com` and query fields secret `wrn3pqx5uqxqvnqr` and counter `0`. When that helper’s starting counter is 12, the query counter is `12`. When a helper whose stored starting counter is 7 is asked to build a URI with starting counter 0, the query counter is `0` — zero is written, not omitted. Omitting the counter would make the URI look like a time-based URI; that must not happen.
- An HMAC-based helper with secret `wrn3pqx5uqxqvnqr`, account `alice@example.com`, and issuer `FooCorp!` has path `/FooCorp%21:alice%40example.com` and query fields secret, counter `0`, and issuer `FooCorp!`.
- Query fields that still have product defaults are omitted. Digit count appears only when it is not 6. Time-step length appears as period only when it is not 30. Algorithm appears only when it is not SHA1, and is spelled in uppercase (`SHA256`, `SHA512`).
- A time-based helper with secret `c7uxuqhgflpw7oruedmglbrk7u6242vb`, digit count 8, time-step 60 seconds, digest SHA256, account `baco@peperina`, and issuer `FooCorp` has path `/FooCorp:baco%40peperina` and query fields secret, issuer `FooCorp`, digits `8`, period `60`, and algorithm `SHA256`. The same helper with SHA1 instead of SHA256 omits algorithm and still includes digits and period. The same helper with the default 30-second step and SHA1 includes digits `8` and omits period and algorithm.
- An HMAC-based helper with that same secret, digit count 8, digest SHA256, account `baco@peperina`, and issuer `FooCorp` includes digits `8` and algorithm `SHA256` and always includes counter.
- An extra image field whose value is `https://test.net/test.png` is included in the query, with the URL percent-encoded. A time-based helper with secret `GEZDGNBV`, SHA512, account `n`, issuer `i`, and that image builds exactly: `otpauth://totp/i:n?secret=GEZDGNBV&issuer=i&algorithm=SHA512&image=https%3A%2F%2Ftest.net%2Ftest.png`.

**Boundary / error behavior:**

- An image field whose value is not an https URL with both a host and a path (for example `nourl`) is refused. The build does not succeed.
- An extra query field whose value is not text is refused. The build does not succeed.
- Building a URI does not require a successful prior check, and a failed check does not rewrite the secret, account, issuer, or URI.

**Verifiable oracle:**

- Success: the two `JBSWY3DPEHPK3PXP` README URIs match exactly; the no-account URI for `S46SQCPPTCNPROMHWYBDCTBZXV` is the Secret URI above and is unchanged after checking `123456`; HMAC URIs always include a counter, including `0`; a build-time starting-counter override of 0 on a helper stored as 7 writes `counter=0`; issuer `FooCorp!` percent-encodes the exclamation mark in the path; digits / period / algorithm appear only when they are not 6 / 30 / SHA1; the SHA256 8-digit 60-second FooCorp URI includes those three query fields; the SHA512 image URI for `GEZDGNBV` / `n` / `i` matches the exact string above; spaces become `%20`.
- Failure / absence: the scheme is not otpauth; a time-based URI uses type hotp or the reverse; counter 0 is omitted so an HMAC URI becomes totp; defaults are always written or non-defaults are dropped; `@` is left unencoded; a failed check mutates the next URI; `nourl` is accepted as an image; plus signs appear where spaces should be `%20`.

---

### FP-05: otpauth provisioning URI parsing

**Public entry:** Otpkit’s provisioning-URI parser. The caller supplies one URI string. A successful parse returns an HMAC-based helper (FP-02) or a time-based helper (FP-03) that can emit codes and can build a URI (FP-04). **This feature point is the inverse of FP-04** for well-formed otpauth URIs of type totp or hotp, except that an image query field is not recovered on rebuild.

**Normal behavior:**

- Parsing a URI that FP-04 built, then asking that helper to build a URI again, yields the same URI string. This round-trip holds for the HMAC and time-based examples in FP-04 (including issuer punctuation, non-default digits, period, algorithm, and starting counter). It does not hold when the built URI carries an image field: that field is ignored at parse time and is absent from the rebuilt string.
- Parsing `otpauth://totp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App` yields a time-based helper whose codes match a helper constructed directly with secret `JBSWY3DPEHPK3PXP`.
- Parsing `otpauth://hotp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App&counter=0` yields an HMAC-based helper whose code at relative count 0 matches a helper constructed directly with that secret.
- The URI type selects the helper kind: totp yields a time-based helper; hotp yields an HMAC-based helper. The query field secret is the shared secret. The query field counter becomes the HMAC starting counter. The query field period becomes the time-step length. The query field digits becomes the digit count. The query field algorithm selects the digest: SHA1, SHA256, or SHA512. When the same query field appears more than once, the last occurrence is the one that takes effect.
- Parsing `otpauth://totp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1` yields a time-based helper that emits `734055` at Unix 0, `662488` at Unix 30, and `289363` at Unix 60, and whose rebuilt URI (no account or issuer supplied at rebuild time) is `otpauth://totp/Secret?secret=GEZDGNBV`. Rebuilding with account `n` and issuer `i` yields `otpauth://totp/i:n?secret=GEZDGNBV&issuer=i`.
- Parsing that same URI with an added `period=60` yields `734055` at Unix 30 and `662488` at Unix 60. The rebuilt URI with account `n` and issuer `i` includes `period=60`.
- Parsing `otpauth://hotp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1` yields an HMAC-based helper that emits `734055` at relative count 0, `662488` at 1, and `289363` at 2. Rebuilding with account `n` and issuer `i` includes `counter=0`. Parsing the same URI with `counter=1` yields `662488` at relative count 0 and `289363` at 1, and the rebuilt URI includes `counter=1`.
- Parsing a totp URI for `GEZDGNBV` whose last algorithm value is SHA256 yields `918961` at Unix 0 and `934470` at Unix 9000. Parsing one whose last algorithm value is SHA512 yields `816660` at Unix 0 and `524153` at Unix 9000.
- The label uses a literal colon as the issuer-and-account separator. A percent-encoded colon (`%3A`) is part of the issuer or the account name, not a separator. Parsing `otpauth://totp/Text%3A%20More%20Text:Secret?secret=FFFFFFFAAAAAABBBBBBB&issuer=Text%3A%20More%20Text` yields account name `Secret` and issuer `Text: More Text`. Parsing `otpauth://totp/a%3Ab?secret=GEZDGNBV` yields account name `a:b` and no issuer. Building a URI from a time-based helper whose account is `Secret` and whose issuer is `Text: More Text`, then parsing that URI, recovers those same two parts. Parsing `otpauth://totp/Big%20Corp:bob?secret=GEZDGNBV&issuer=Big%20Corp` yields account `bob` and issuer `Big Corp`.
- An optional image query field is accepted and ignored. Parsing `otpauth://totp?secret=GEZDGNBV&image=foobar` succeeds and returns a time-based helper whose code at Unix 0 is `734055` — the same as a helper constructed directly with secret `GEZDGNBV`. The parser does not require the image value to be a valid https URL.

**Boundary / error behavior:**

- A URI whose scheme is not otpauth (for example `http://hello.com`) is refused. The parse does not succeed.
- An otpauth URI that does not carry a secret (for example `otpauth://totp`) is refused.
- An otpauth URI whose type is neither totp nor hotp (for example `otpauth://derp?secret=foo`) is refused.
- A totp or hotp URI whose digits value is not 6, 7, or 8 (for example digits `−1`) is refused.
- When an issuer appears both in the label and in the query, each query issuer is compared to the label issuer as it is read; if any occurrence is not equal (for example label issuer `SomeIssuer` and query issuer `AnotherIssuer`, even when a later query issuer equals the label), the parse is refused.
- An algorithm value other than SHA1, SHA256, or SHA512 (for example `aes`) is refused.
- Each of those refusals is a failed parse: no helper is returned. They are distinguishable from a successful parse that then fails a later code check.

**Verifiable oracle:**

- Success: a URI built in FP-04 parses back to a helper that rebuilds the same URI, except that an image field is dropped on rebuild; the two `JBSWY3DPEHPK3PXP` README URIs parse to helpers whose codes match direct construction; `GEZDGNBV` totp SHA1 / period 60 / hotp / hotp counter 1 / SHA256 / SHA512 produce the codes listed above; last algorithm occurrence wins; `%3A` in the label is not treated as the issuer separator; `Text: More Text` / `Secret` round-trips; `a%3Ab` is account `a:b`; `otpauth://totp?secret=GEZDGNBV&image=foobar` parses to a helper that emits `734055` at Unix 0.
- Failure / absence: `http://hello.com` parses as a helper; a missing secret is accepted; type `derp` is accepted; digits `−1` is accepted; mismatched label and query issuers are accepted; algorithm `aes` is accepted; an encoded colon in the issuer is treated as the account separator so the account and issuer come out wrong; a parsed helper’s codes do not match a helper constructed with the same secret; round-trip rebuild changes the URI.
