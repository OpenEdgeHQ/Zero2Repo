# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**Otpkit** is a Python library for generating and verifying one-time passwords. It implements server-side support for RFC 4226 (HMAC-based one-time passwords) and RFC 6238 (time-based one-time passwords). Integrators use it to add two-factor or multi-factor authentication: generate a random shared secret, construct an HMAC-based or time-based helper, emit a code, check a candidate the user typed, and build or parse an `otpauth` provisioning URI so a compatible app can be enrolled.

A first-time integrator generates a random shared secret, constructs a time-based helper with that secret, reads the code for the current clock, and checks a candidate code. The same secret can instead drive an HMAC-based helper whose codes are indexed by a counter the application stores. Either helper can emit an `otpauth` URI; the library can also parse such a URI back into a helper that produces the same codes.

The finished product is an **importable Python library**, not a command-line program, not a network service, and not a wire protocol of its own. Integrators install the package and construct helpers in Python. There is no product-owned configuration file. The library does not store used codes, rate-limit logins, send SMS or email, or render QR images.

The product is a pure-Python library with zero declared runtime dependencies. No compiled extension, native code, GPU, or accelerator is required. The language is Python 3.8 or newer, including CPython and PyPy. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is the importable package `otpkit`. Callers write `import `otpkit`` or `from `otpkit` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `otpkit` under `src`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

The independently verifiable library entries named from this package root are:

- `random_base32` — emit a newly drawn base32 shared secret as text.
- `random_hex` — emit a newly drawn hex-encoded shared secret as text.
- `HOTP` — the HMAC-based helper. Constructed with a shared secret in base32. Emits and checks codes indexed by a caller-supplied counter. Does not consult the clock.
- `TOTP` — the time-based helper. Constructed with a shared secret in base32. Emits and checks codes indexed by the current clock or a given instant, with an optional acceptance window.
- `parse_uri` — parse one `otpauth` provisioning URI and return an `HOTP` or `TOTP` helper that emits the same codes and can rebuild an equivalent URI.

Either helper can emit an `otpauth` provisioning URI. Building a URI does not require a prior successful check. Parsing a URI is the inverse of a well-formed build for types `totp` and `hotp`.

Callers construct `HOTP` or `TOTP` with a base32 shared secret. They may also supply a digit count, a digest, an account name, and an issuer. An HMAC-based helper also accepts a starting counter. A time-based helper also accepts a time-step length. Exact parameter lists belong with those symbols.

Hex secrets produced by `random_hex` are for applications that want a hex-encoded key. `HOTP` and `TOTP` still consume the shared secret as base32 text.

**Not in this surface.** A command-line program, HTTP server, or authentication framework. Rendering QR codes, sending SMS or email, or shipping a phone client. Storing used codes or denying replay inside the library. Transport confidentiality, rate limiting, or secret-at-rest storage. FIDO U2F / WebAuthn. Steam TOTP. A fallback import of another OTP library.

### Naming conventions

**Product and package.** The product identity is Otpkit. The importable top-level package is spelled `otpkit`.

**Secret helpers.** Random secret generation uses snake_case function names `random_base32` and `random_hex`. The optional requested width on both helpers is the argument named `length`.

**Helper types.** Published helper types use PascalCase: `HOTP` and `TOTP`. Each is a callable class. Callers construct instances by calling the class.

**URI parser.** Provisioning-URI parse is the snake_case function `parse_uri`.

**URI tokens.** The provisioning URI scheme is `otpauth`. The URI type is `totp` for a time-based helper and `hotp` for an HMAC-based helper. No other `otpauth` type is accepted.

**Digest spellings.** The product default digest is `SHA1`. `SHA256` and `SHA512` are also supported. `MD5` and `SHAKE-128` are refused. When a digest appears in an `otpauth` query, it is spelled in uppercase (`SHA1`, `SHA256`, `SHA512`).

**Account placeholder.** When the caller never supplies an account name, the product uses the placeholder `Secret`.

**Layout.** The importable package directory is `otpkit` under `src`.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**No command-line product.** There is no console-script entry and no `python -m` program that is part of this surface. Outcomes are returned or raised from library calls. Library entries do not exit the host process as their success or failure report.

**Library substrate.** When the `otpkit` package is importable, a program that does `from `otpkit` import `random_base32``, calls `random_base32` with no arguments, and prints the result exits successfully and prints a 32-character string whose every character is one of `A` through `Z` or `2` through `7`. When the package is importable, constructing `HOTP` with secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` and asking for the code at relative count 0 yields the six-character string `755224`.

**Codes are text strings.** A successful generation returns a text string (`str`) of decimal digits. The string is exactly as wide as the configured digit count; leading zeros are kept. A code is never returned as a bare integer.

**Secret representation.** Helpers take the shared secret as base32 text. A secret whose length is not a multiple of eight is accepted; missing padding is not the caller’s problem. Letter case in a consumed secret does not matter.

**Generated-secret minimum.** Random secret generation enforces a 160-bit minimum. The default base32 secret has length 32. The default hex secret has length 40. A requested width at or above that minimum succeeds and returns a string of exactly that length. A width below the minimum does not succeed and returns no secret.

**Generated-secret alphabets.** A base32 secret uses only the characters `ABCDEFGHIJKLMNOPQRSTUVWXYZ234567` (`A`–`Z` and `2`–`7`; not `0`, `1`, `8`, or `9`). A hex secret uses only the characters `ABCDEF0123456789` (`A`–`F` and `0`–`9`; not lowercase letters).

**Default digit count.** 6. Construction refuses a count greater than 10. An `otpauth` URI may carry only 6, 7, or 8.

**Default digest.** `SHA1`. An explicit `SHA1` digest produces the same codes as leaving the digest at the default.

**Default time-step length.** 30 seconds.

**Default HMAC starting counter.** 0.

**URI type set.** `totp` and `hotp` only.

**URI algorithm set.** `SHA1`, `SHA256`, `SHA512`.

**Check versus generate.** Checking a wrong candidate is a negative result and does not abort the caller. Asking for a code at an illegal counter or instant is a failure: no code is returned. Those two outcomes are distinguishable. Checking a valid candidate twice at the same counter or the same instant succeeds both times; the library does not consume the code.

**Integrity of the helper.** A helper that always returns a fixed six-digit string, that accepts every candidate, that returns integers so leading zeros vanish, or that ignores the counter or the clock does not implement this product.

## `image`

Extra query-field keyword on `provisioning_uri`. Callers pass `image` by name when they attach an image URL to that one URI build on an `HOTP` or `TOTP` helper. `image` is not a constructor argument.

`image` is accepted only when its value is an `https` URL with both a host and a path. All three parts are required together. On success, the URL is written as query field `image` (decoded value equals the supplied URL) and the URL is percent-encoded in the raw query.

A time-based helper with secret `GEZDGNBV`, digest `SHA512`, account `n`, issuer `i`, and `image` `https://test.net/test.png` builds exactly:

`otpauth://totp/i:n?secret=GEZDGNBV&issuer=i&algorithm=SHA512&image=https%3A%2F%2Ftest.net%2Ftest.png`

The same `image` value is accepted on an HMAC-based helper; that HMAC URI still includes `counter`.

An `image` value that is not an `https` URL with both a host and a path is refused. The build does not succeed: no `otpauth` URI is handed back. The call may raise, or it may return a value that is not `otpauth` text. Returning `otpauth` text is not a refusal. Refused forms include `nourl`, a token with no scheme, a URL whose scheme is not `https` (even when it has a host and a path), an `https` URL with a host and no path, and an `https` URL with a path and no host.

An extra query field that is not `image` is forwarded as that extra keyword when its value is text. A non-text extra-field value is refused the same way. The exception class and message text are not a compatibility contract.

## `issuer_name`

Build-time keyword on `provisioning_uri`. Callers pass `issuer_name` by name when they override the issuer for that one URI build on an `HOTP` or `TOTP` helper.

`issuer_name` is not the constructor keyword. Construction stores the issuer as `issuer`. The build-time overlay is the distinct name `issuer_name`. Passing the constructor’s `issuer` spelling as this overlay is not this contract.

When `issuer_name` is omitted, the build uses the issuer already stored on the helper (including when that stored value came from constructor `issuer`). When neither construction nor this call supplied an issuer, the path is the account name alone and the query has no `issuer` field.

When `issuer_name` is supplied, that text is the issuer for this build: the path is the percent-encoded issuer, a literal colon, and the percent-encoded account, and the query includes `issuer` (the query key is `issuer`, not `issuer_name`). A helper constructed with only an account, then built with `issuer_name`, gains that path prefix and that `issuer` query field on that call.

A helper constructed with secret `JBSWY3DPEHPK3PXP` and no account or issuer, then built with `name` `alice@google.com` and `issuer_name` `Secure App`, yields the same URI as constructing that helper with `name` `alice@google.com` and `issuer` `Secure App` and calling `provisioning_uri` with no overlay:

- time-based: `otpauth://totp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App`
- HMAC-based (with starting counter `0`): `otpauth://hotp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App&counter=0`

Spaces in the issuer are encoded as `%20`, not a plus sign. `!` in the issuer is encoded as `%21` in the path and in the raw query.

## `otpkit`

The installable product identity is Otpkit. The importable top-level package is `otpkit`. Callers declare the interface from this package root (`import `otpkit`` or `from `otpkit` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `otpkit` under `src`.

These names are importable as ``otpkit`.<name>` and as `from `otpkit` import <name>`:

- `random_base32`
- `random_hex`
- `HOTP`
- `TOTP`
- `parse_uri`

`random_base32` and `random_hex` are callables that return a text string. `HOTP` and `TOTP` are callable classes. `parse_uri` is a callable that returns an `HOTP` or `TOTP` instance.

Typical import used to generate a random shared secret:

```
from `otpkit` import `random_base32`, `random_hex`
```

A script that only needs a subset may import that subset, for example `from `otpkit` import `random_base32`` or `from `otpkit` import `random_hex``.

Typical import used to construct helpers and to parse a provisioning URI:

```
from `otpkit` import `HOTP`, `TOTP`, `parse_uri`
```

When `otpkit` is importable, `from `otpkit` import `random_base32`` followed by a no-argument call to `random_base32` returns a 32-character string from the alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ234567`.

## `otpkit.HOTP`

Import `HOTP` from the package root `otpkit` (`from `otpkit` import `HOTP``). `HOTP` is a callable class. Calling it constructs an HMAC-based helper whose codes are indexed by a caller-supplied counter. The helper emits a code for a relative count and checks a candidate at a relative count. It does not consult the process clock.

Typical construction:

```
from `otpkit` import `HOTP`
helper = `HOTP`(<base32 secret>)
```

### Signature

```
`HOTP`(<base32 secret>, `digits`=6, `digest`=..., `name`=..., `issuer`=..., `initial_count`=0)
```

The shared secret is the first positional argument. It is base32 text. Callers pass it positionally; they do not have to name it as a keyword.

Keyword arguments the caller may supply by name:

- `digits` — integer digit count. Default 6.
- `digest` — a hash constructor from the standard hashlib module. When omitted, the digest is `SHA1`.
- `name` — optional account name as text. When omitted, codes are unchanged.
- `issuer` — optional issuer as text. When omitted, codes are unchanged.
- `initial_count` — integer starting counter. Default 0.

On success, construction returns a helper object. The value is not `None`, not a text string, and not a number.

```
helper.`at`(<relative count>)
```

The relative count is the first positional argument (an integer). On success, returns a Python text string (`str`) of decimal digits whose length equals the configured digit count.

```
helper.`verify`(<candidate>, <relative count>)
```

The candidate is the first positional argument (text). The relative count is the second positional argument (an integer). The call returns; it does not abort the caller. A candidate that matches the code for that relative count (or differs from it only by Unicode compatibility-equivalent characters) returns the same value as checking the just-emitted code at that same relative count. A candidate that is not compatibility-equivalent to the expected code returns a different value.

Construction, emit, and check do not read or write files, do not mutate the process environment, and do not exit the host process.

### Shared secret

The secret is base32 text. Letter case does not matter: a lowercase secret produces the same codes as the same secret in uppercase. Secret `wrn3pqx5uqxqvnqr` is usable.

A secret whose length is not a multiple of eight is accepted; missing padding is not the caller’s problem. Secret `N3OVNIBRERIO5OHGVCMDGS4V4RJ3AUZOUN34J6FRM4P6JIFCG3ZA` is accepted as given. Appending base32 padding so that the length becomes a multiple of eight produces the same codes as the unpadded spelling.

Hex-encoded secrets are not the input form this helper consumes.

### Digit count

The default digit count is 6. An explicit `digits` of 6 produces the same six-digit codes as omitting `digits`. An explicit `digits` of 8 is accepted. A successful code is exactly as wide as the configured digit count; leading zeros are kept. A code is never a bare integer.

Constructing with `digits` equal to 11 does not succeed. Constructing with any integer digit count greater than 10 does not succeed. In those cases no usable helper is handed back: the call may raise, or it may return a non-helper. Returning a helper is not a refusal. The exception class and message text are not a compatibility contract.

### Digest

The default digest is `SHA1`. Passing the SHA-1 constructor from hashlib as `digest` produces the same codes as omitting `digest`. The SHA-256 constructor (`SHA256`) and the SHA-512 constructor (`SHA512`) are accepted. With the default digit count, those helpers still emit six-character decimal-digit text; checking an emitted code at the same relative count succeeds, and checking that same code at a neighboring relative count fails. Exact SHA-256 and SHA-512 code strings are not a compatibility contract.

Constructing with the MD5 constructor (`MD5`) does not succeed. Constructing with the SHAKE-128 constructor (`SHAKE-128`) does not succeed. No usable helper is handed back. The exception class and message text are not a compatibility contract.

### Starting counter

The default starting counter is 0. An explicit `initial_count` of 0 produces the same codes as omitting `initial_count`.

Relative count N on a helper whose starting counter is K is the same code as relative count K+N on a helper built from the same secret with the default starting counter. In particular, secret `GEZDGNBV` with `initial_count` 1 emits `662488` at relative count 0 and `289363` at relative count 1, which equal the default-start codes at relative counts 1 and 2.

### Account name and issuer

The caller may supply `name` and `issuer` together. Supplying them does not change the codes. A helper built from the RFC 4226 secret below with an account name and an issuer still emits `755224` at relative count 0.

### Emit

``at`` uses the supplied relative count. It does not consult the process clock. Emitting at a fixed relative count yields the same code under two different process-clock epochs.

For any non-negative relative count, a successful emit returns decimal-digit text of the configured width. The code is indexed by the secret and that relative count: two different secrets at the same relative count yield different codes, and the code is not a copy of the secret string.

Asking for the code at a negative relative count (including −1, and any other negative integer) does not succeed. The call raises. No code string is returned. Returning `None` without raising is not a refusal. The exception class and message text are not a compatibility contract.

### Check

``verify`` always takes the candidate and the relative count from the caller. The helper does not store or advance a counter of its own.

Checking a matching candidate succeeds. Checking the same matching candidate a second time at the same relative count still succeeds; the check does not consume the code. Checking a code that belongs to a different relative count fails, including a second check at that wrong relative count. Checking a candidate that is not compatibility-equivalent to the expected code fails. A failed check returns a negative result and does not abort the caller. After a failed check, the same helper instance still emits the same code at the same relative count.

A candidate that differs from the expected code only by Unicode compatibility-equivalent characters succeeds. For the RFC 4226 secret below at relative count 0, the fullwidth-digit candidate `７５５２２４` succeeds.

### Named secrets and codes

Secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` (default digits, default digest, default starting counter) emits these six-character strings at relative counts 0 through 9, in order: `755224`, `287082`, `359152`, `969429`, `338314`, `254676`, `287922`, `162583`, `399871`, `520489`. Checking `520489` at relative count 9 succeeds. Checking `520489` at relative count 10 fails.

Secret `base32secret3232` emits `260182` at relative count 0, `055283` at relative count 1, and `316439` at relative count 1401. The code at relative count 1 is the six-character string `055283`, including the leading zero. Checking `316439` at relative count 1401 succeeds. Checking `316439` at relative count 1402 fails.

Secret `N3OVNIBRERIO5OHGVCMDGS4V4RJ3AUZOUN34J6FRM4P6JIFCG3ZA` emits `737863` at 0, `390601` at 1, `363354` at 2, `936780` at 3, and `654019` at 4. The same five strings are emitted when that secret is lowercased, and when missing base32 padding is restored.

An eight-digit helper built from `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` emits an eight-character decimal-digit string at relative count 0. Checking that emitted string at relative count 0 succeeds. Checking the six-digit string `755224` against that eight-digit helper at relative count 0 fails.

### Present-package use

When the `otpkit` package is importable, this program completes successfully and prints `755224`:

```
from `otpkit` import `HOTP`
helper = `HOTP`("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ")
code = helper.`at`(0)
print(code)
accepted = helper.`verify`(code, 0)
rejected = helper.`verify`("000000", 0)
```

`accepted` and `rejected` are not equal. Output-equality alone is not proof that the real package ran.

## `otpkit.HOTP.provisioning_uri`

Instance method on an `HOTP` helper. The method name is `provisioning_uri`. Callers obtain the helper from the package root (`from `otpkit` import `HOTP``) and call this method on that instance. There is no second public builder name.

A successful call returns `otpauth` text. The URI type is `hotp`. The query always includes the shared `secret`. An HMAC URI always includes `counter`, including when that value is `0`; omitting `counter` is not a successful HMAC build.

### Signature

```
helper.`provisioning_uri`(`name`=..., `initial_count`=..., `issuer_name`=..., ...)
```

Every argument the caller supplies on this call is passed by name. Omitting an overlay uses the value already stored on the helper.

- `name` — optional account name as text. Same keyword the `HOTP` constructor already uses. When omitted, the stored account is used. When the caller never supplied an account (constructor or this call), the path uses the placeholder `Secret`.
- `initial_count` — optional integer starting-counter overlay for this build. When omitted, the stored starting counter is used (constructor default `0`). An explicit `0` is a real overlay: zero is written as `counter` `0`, not omitted.
- `issuer_name` — optional issuer overlay as text. This build-time keyword is distinct from the constructor keyword `issuer`. When omitted, the stored issuer is used. When neither this call nor construction supplied an issuer, the path is the account alone and the query has no `issuer` field.
- Further keywords — extra query fields. Each extra keyword’s name is written as a query key whose value is that keyword’s text. The extra keyword `image` is accepted only when its value is an `https` URL with both a host and a path.

### Return shape

On success, returns a Python text string (`str`) whose scheme is `otpauth`. The value is not `None`, not bytes, and not a number. The type (URI host) is `hotp`, not `totp`.

The call does not read or write files, does not mutate the process environment, and does not exit the host process. Building does not require a prior successful check. Checking a candidate does not rewrite the secret, the account, the issuer, or a later build of the URI.

### Account, issuer, and starting counter

Constructor-supplied `name`, `issuer`, and `initial_count` appear in a no-argument build. The same URI is produced by constructing with only the secret and passing those values on this call: `name` for the account, `issuer_name` for the issuer, and `initial_count` for the starting counter.

A helper constructed with secret `JBSWY3DPEHPK3PXP`, account `alice@google.com`, issuer `Secure App`, and starting counter `0` builds exactly:

`otpauth://hotp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App&counter=0`

A helper constructed with only that secret, then called with `name` `alice@google.com`, `issuer_name` `Secure App`, and `initial_count` `0`, builds that same string.

When an issuer is present, the path is the percent-encoded issuer, a literal colon, and the percent-encoded account, and the query includes `issuer`. When no issuer is present, the path is the percent-encoded account alone.

A helper with no account still uses path `/Secret` and still includes `counter`. Passing `name` on the build replaces that placeholder for that call.

A helper whose stored starting counter is `7`, asked to build with `initial_count` `0`, writes `counter` `0`. A helper whose stored starting counter is `12` writes `counter` `12` when no overlay is passed.

### Query fields written from the helper

- `secret` — always written, as the helper’s base32 secret text.
- `counter` — always written, as the decimal text of the starting counter used for this build.
- `issuer` — written when an issuer is present (constructor `issuer` or this call’s `issuer_name`).
- `digits` — written only when the digit count is not `6`.
- `algorithm` — written only when the digest is not `SHA1`, and spelled in uppercase (`SHA256`, `SHA512`).

A helper with secret `wrn3pqx5uqxqvnqr` and account `alice@example.com` (no issuer) has path `/alice%40example.com` and query fields `secret` `wrn3pqx5uqxqvnqr` and `counter` `0`. With issuer `FooCorp!`, the path is `/FooCorp%21:alice%40example.com` and the query also includes `issuer` `FooCorp!`.

A helper with secret `c7uxuqhgflpw7oruedmglbrk7u6242vb`, digit count `8`, digest `SHA256`, account `baco@peperina`, and issuer `FooCorp` includes `digits` `8`, `algorithm` `SHA256`, and `counter`.

### Percent-encoding

Special characters in the label and query are percent-encoded. `@` becomes `%40`. `!` becomes `%21`. A space becomes `%20`, not a plus sign.

### Extra keywords and `image`

An extra keyword whose value is text is included in the query under that keyword’s name.

`image` is accepted only when its value is an `https` URL with both a host and a path. That URL is written as query field `image`, percent-encoded. A helper that accepts `image` `https://test.net/test.png` still includes `counter`.

### Refusal

An `image` value that is not an `https` URL with both a host and a path (for example `nourl`, a token with no scheme, a non-`https` URL, an `https` URL with no host, or an `https` URL with no path) is refused. The build does not succeed: no `otpauth` URI is handed back. The call may raise, or it may return a value that is not `otpauth` text. Returning `otpauth` text is not a refusal.

An extra query field whose value is not text is refused the same way. The exception class and message text are not a compatibility contract.

### Present-package use

When the `otpkit` package is importable, this program completes successfully and prints the HMAC README URI above:

```
from `otpkit` import `HOTP`
helper = `HOTP`("JBSWY3DPEHPK3PXP")
uri = helper.`provisioning_uri`(`name`="alice@google.com", `issuer_name`="Secure App", `initial_count`=0)
print(uri)
constructed = `HOTP`("JBSWY3DPEHPK3PXP", `name`="alice@google.com", `issuer`="Secure App", `initial_count`=0)
same = constructed.`provisioning_uri`()
```

`uri` and `same` are equal. Output-equality alone is not proof that the real package ran.

## `otpkit.TOTP`

Import `TOTP` from the package root `otpkit` (`from `otpkit` import `TOTP``). `TOTP` is a callable class. Calling it constructs a time-based helper whose codes are indexed by time, divided into fixed-length steps. The helper emits a code for the current process clock or for a caller-supplied instant, checks a candidate with an optional acceptance window, and can return the matching time-step number.

Typical construction:

```
from `otpkit` import `TOTP`
helper = `TOTP`(<base32 secret>)
```

### Signature

```
`TOTP`(<base32 secret>, `digits`=6, `digest`=..., `name`=..., `issuer`=..., `interval`=30)
```

The shared secret is the first positional argument. It is base32 text. Callers pass it positionally; they do not have to name it as a keyword.

Keyword arguments the caller may supply by name:

- `digits` — integer digit count. Default 6.
- `digest` — a hash constructor from the standard hashlib module. When omitted, the digest is `SHA1`.
- `name` — optional account name as text. When omitted, codes are unchanged.
- `issuer` — optional issuer as text. When omitted, codes are unchanged.
- `interval` — integer time-step length in seconds. Default 30.

On success, construction returns a helper object. The value is not `None`, not a text string, and not a number.

```
helper.`now`()
```

No arguments. Reads the current process clock. On success, returns a Python text string (`str`) of decimal digits whose length equals the configured digit count.

```
helper.`at`(<instant>, <offset>)
```

The instant is the first positional argument. It may be a Unix timestamp (an integer or a real number) or a datetime. The whole-step offset is the second positional argument (an integer). When the offset is omitted, it is 0. On success, returns a Python text string (`str`) of decimal digits whose length equals the configured digit count.

```
helper.`verify`(<candidate>, <instant>, `valid_window`=<window>)
helper.`verify`(<candidate>, `valid_window`=<window>)
```

The candidate is the first positional argument (text). When an instant is supplied, it is the second positional argument (the same Unix-timestamp or datetime forms `at` accepts). The acceptance window is the argument named `valid_window` (an integer). Callers pass `valid_window` by name when they omit the instant, so that the check uses the current process clock. Callers pass the window as the third positional argument when they also supply an instant. When `valid_window` is omitted, the window is 0. The call returns; it does not abort the caller. A candidate that matches a code inside the window (or differs from it only by Unicode compatibility-equivalent characters) returns the same value as checking the just-emitted on-step code at that same instant (or at the current clock, when the instant is omitted). A candidate that is not compatibility-equivalent to any code inside the window returns a different value.

```
helper.`verify_and_get_timecode`(<candidate>, <instant>, <window>)
```

The candidate is the first positional argument (text). The instant is the second positional argument. The acceptance window is the third positional argument (an integer). When the window is omitted, it is 0. When the candidate is accepted, the call returns the matching time-step number: a Python `int` that is not a `bool`. When the candidate is not accepted, the call returns (it does not abort the caller) and the value is not a time-step number: it is not a non-bool integer, and it is not equal to a successful ordinary `verify` of the on-step code at that same instant.

Construction, emit, and check do not read or write files, do not mutate the process environment, and do not exit the host process.

### Shared secret

The secret is base32 text. Letter case does not matter: a lowercase secret produces the same codes as the same secret in uppercase. Secret `wrn3pqx5uqxqvnqr` is usable. The uppercase spelling of that same secret, with the process clock at Unix time 1297553958, still emits and accepts `102705`.

Hex-encoded secrets are not the input form this helper consumes.

### Digit count

The default digit count is 6. An explicit `digits` of 6 produces the same six-digit codes as omitting `digits`. An explicit `digits` of 8 is accepted. A successful code is exactly as wide as the configured digit count; leading zeros are kept. A code is never a bare integer.

Constructing with `digits` equal to 11 does not succeed. Constructing with any integer digit count greater than 10 does not succeed. In those cases no usable helper is handed back: the call may raise, or it may return a non-helper. Returning a helper is not a refusal. The exception class and message text are not a compatibility contract.

### Digest

The default digest is `SHA1`. Passing the SHA-1 constructor from hashlib as `digest` produces the same codes as omitting `digest`. The SHA-256 constructor (`SHA256`) and the SHA-512 constructor (`SHA512`) are accepted. With the default digit count, those helpers still emit six-character decimal-digit text; checking an emitted code at the same instant succeeds, and checking that same code one default time-step later fails. Exact six-digit SHA-256 and SHA-512 code strings are not a compatibility contract.

Constructing with the MD5 constructor (`MD5`) does not succeed. Constructing with the SHAKE-128 constructor (`SHAKE-128`) does not succeed. No usable helper is handed back. The exception class and message text are not a compatibility contract.

### Time-step length

The default time-step length is 30 seconds. An explicit `interval` of 30 produces the same codes as omitting `interval`.

A time-step length other than 30 changes which instants share a code. A helper with secret `GEZDGNBV`, `SHA1`, and `interval` 60 emits `734055` at Unix time 30 and `662488` at Unix time 60 — the same strings a default 30-second helper emits at Unix time 0 and Unix time 30. At an instant strictly between 30 and 60, the 60-second helper still emits `734055` and the default 30-second helper emits `662488`; those two strings are not equal.

### Account name and issuer

The caller may supply `name` and `issuer` together. Supplying them does not change the codes. A helper built from the RFC 6238 SHA1 secret below with an account name and an issuer still emits `050471` at Unix time 1111111111.

### Instant forms

`at` and `verify` accept either a Unix timestamp or a datetime as the instant.

A timezone-aware datetime is read as UTC. A timezone-naive datetime is read in the host local timezone.

Unix timestamp, timezone-aware UTC datetime, and naive local datetime of one absolute instant all emit the same code. For secret `ABCDEFGH` at Unix time 200, all three forms emit `028307`.

When the host timezone is not UTC, a timezone-aware UTC datetime and a timezone-naive datetime that share the same civil year/month/day/hour/minute/second are not the same instant. Their codes differ. The naive civil numbers emit the same string as `at` at the Unix timestamp of that naive datetime interpreted as local time.

### Current-clock emit

`now` reads the process clock. It does not take an instant argument. Asking for the current-clock code yields the same string as `at` at that same current instant supplied explicitly, including when that instant is given as a Unix timestamp or as a timezone-aware UTC datetime.

Checking that string against the current clock, with window 0, succeeds. Checking the same valid code twice at the same current clock still succeeds; the helper does not consume the code.

After one full default time-step (30 seconds) has passed, checking the previous step’s code against the new clock, with window 0, fails. Checking that previous code at the later instant through `at`/`verify` also fails.

### Emit at an instant

`at` uses the supplied instant plus the whole-step offset. It does not read the process clock to choose the instant.

Offset 0 is the step that contains the instant. Offset −1 is the previous step. Offset +1 is the next step. For a default 30-second helper, offset +1 at instant T equals offset 0 at T+30, and offset −1 at T equals offset 0 at T−30.

For secret `ABCDEFGH` at Unix time 200 (default 30-second step), offset 0 yields `028307`, offset −1 yields `451564`, and offset +1 yields `681610`.

For any instant that falls on a non-negative time-step, a successful emit returns decimal-digit text of the configured width. The code is indexed by the secret and that time-step: two different secrets at the same instant yield different codes, and the code is not a copy of the secret string.

For secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ`, asking for the code at Unix time −1 or at −29.5 succeeds and yields `755224` (those instants fall on the epoch step). Other instants strictly after −30 and strictly before 0 also yield `755224`. Asking for the code at Unix time −30 does not succeed. No decimal-digit code string is returned. The call may raise, or it may return a value that is not a decimal-digit code string. Returning a configured-width decimal string is not a refusal. The exception class and message text are not a compatibility contract.

### Check

`verify` does not store or consume a code. Checking a matching candidate succeeds. Checking the same matching candidate a second time at the same instant still succeeds. A failed check returns a negative result and does not abort the caller. After a failed check, the same helper instance still emits and accepts the on-step code at that same instant.

Checking with an acceptance window of 1 step at Unix time 200 for secret `ABCDEFGH` accepts `451564`, `028307`, and `681610`, and rejects `195979`. Checking with a window of 0 accepts only the on-step code `028307` and rejects the adjacent-step codes and `195979`.

A code from a different secret, a code from outside the acceptance window, or a candidate that is not compatibility-equivalent to the expected code fails the check without aborting the caller.

A candidate that differs from the expected code only by Unicode compatibility-equivalent characters succeeds. For secret `ABCDEFGH` at Unix time 200, a fullwidth-digit form of `028307` succeeds. A candidate that is not compatibility-equivalent fails.

### Matching time-step

`verify_and_get_timecode` returns the integer number of time-step lengths that have elapsed from the Unix epoch to the matching step when the candidate is accepted. The library does not remember previous successes: a second accepted call with the same candidate, instant, and window still returns the same time-step number.

For secret `ABCDEFGH` at Unix time 200 with a window of 1: `451564` yields 5, `028307` yields 6, and `681610` yields 7. `195979` does not yield a time-step number; the caller observes a returned negative result, not an aborted call. With a window of 0, `028307` still yields 6 and `451564` does not yield a time-step number.

A window of 0 or a positive window is accepted. Asking `verify_and_get_timecode` to use a negative acceptance window (including −1, and any other negative integer) does not succeed. The caller observes a failure (any exception). No time-step number is handed back. Returning a negative result without failing is not this outcome. The exception class and message text are not a compatibility contract.

### Named secrets and codes

Secret `wrn3pqx5uqxqvnqr` (default digits, default digest, default time-step length), while the process clock is at Unix time 1297553958, emits `102705`. Checking `102705` at that current clock succeeds. Checking `102705` at Unix time 1297553958 + 30 fails.

Secret `GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ` (the RFC 4226 / RFC 6238 SHA1 secret) with the default six-digit width yields `050471` at Unix time 1111111111, `005924` at Unix time 1234567890, and `279037` at Unix time 2000000000. Those strings keep their leading zeros. Checking `050471` while the process clock is at 1111111111 succeeds. Checking `050471` at 1297553958 + 30 fails.

An eight-digit helper built from that same SHA1 secret matches RFC 6238 Appendix B: Unix 59 yields `94287082`; 1111111109 yields `07081804`; 1111111111 yields `14050471`; 1234567890 yields `89005924`; 2000000000 yields `69279037`; 20000000000 yields `65353130`. An explicit `digits` of 8 with the default digest also yields `94287082` at Unix 59. Those eight-digit SHA1 strings are text, eight characters, and keep leading zeros.

An eight-digit helper with `SHA256` and the base32 form of the 32-byte ASCII string `12345678901234567890123456789012` matches RFC 6238 Appendix B: Unix 59 yields `46119246`; 1111111109 yields `68084774`; 1111111111 yields `67062674`; 1234567890 yields `91819424`; 2000000000 yields `90698825`; 20000000000 yields `77737706`. Those SHA256 strings are not the SHA1 Appendix B table.

An eight-digit helper with `SHA512` and the base32 form of the 64-byte ASCII string `1234567890123456789012345678901234567890123456789012345678901234` matches RFC 6238 Appendix B: Unix 59 yields `90693936`; 1111111109 yields `25091201`; 1111111111 yields `99943326`; 1234567890 yields `93441116`; 2000000000 yields `38618901`; 20000000000 yields `47863826`. Those SHA512 strings are not the SHA1 Appendix B table.

At an instant other than the named times above, emit and check still round-trip: the emitted code is accepted at that instant with window 0, rejected one full default time-step later, and bound to the secret (a different secret at the same instant yields a different code). The same round-trip holds for eight-digit `SHA1` and eight-digit `SHA256` helpers. At one shared instant, eight-digit `SHA256` and eight-digit `SHA1` codes for the same secret still differ after the secret string itself is removed from both codes.

### Present-package use

When the `otpkit` package is importable, this program completes successfully and prints `028307`:

```
from `otpkit` import `TOTP`
helper = `TOTP`("ABCDEFGH")
code = helper.`at`(200)
print(code)
accepted = helper.`verify`(code, 200, 0)
rejected = helper.`verify`("195979", 200, 0)
step = helper.`verify_and_get_timecode`(code, 200, 0)
```

`accepted` and `rejected` are not equal. `step` is the integer 6. Output-equality alone is not proof that the real package ran.

## `otpkit.TOTP.provisioning_uri`

Instance method on a `TOTP` helper. The method name is `provisioning_uri`. Callers obtain the helper from the package root (`from `otpkit` import `TOTP``) and call this method on that instance. There is no second public builder name.

A successful call returns `otpauth` text. The URI type is `totp`. The query always includes the shared `secret`.

### Signature

```
helper.`provisioning_uri`(`name`=..., `issuer_name`=..., ...)
```

Every argument the caller supplies on this call is passed by name. Omitting an overlay uses the value already stored on the helper. This method does not take a starting-counter overlay.

- `name` — optional account name as text. Same keyword the `TOTP` constructor already uses. When omitted, the stored account is used. When the caller never supplied an account (constructor or this call), the path uses the placeholder `Secret`.
- `issuer_name` — optional issuer overlay as text. This build-time keyword is distinct from the constructor keyword `issuer`. When omitted, the stored issuer is used. When neither this call nor construction supplied an issuer, the path is the account alone and the query has no `issuer` field.
- Further keywords — extra query fields. Each extra keyword’s name is written as a query key whose value is that keyword’s text. The extra keyword `image` is accepted only when its value is an `https` URL with both a host and a path.

### Return shape

On success, returns a Python text string (`str`) whose scheme is `otpauth`. The value is not `None`, not bytes, and not a number. The type (URI host) is `totp`, not `hotp`.

The call does not read or write files, does not mutate the process environment, and does not exit the host process. Building does not require a prior successful check. Checking a candidate does not rewrite the secret, the account, the issuer, or a later build of the URI.

### Account and issuer

Constructor-supplied `name` and `issuer` appear in a no-argument build. The same URI is produced by constructing with only the secret and passing those values on this call: `name` for the account and `issuer_name` for the issuer.

A helper constructed with secret `JBSWY3DPEHPK3PXP`, account `alice@google.com`, and issuer `Secure App` builds exactly:

`otpauth://totp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App`

A helper constructed with only that secret, then called with `name` `alice@google.com` and `issuer_name` `Secure App`, builds that same string.

When an issuer is present, the path is the percent-encoded issuer, a literal colon, and the percent-encoded account, and the query includes `issuer`. When no issuer is present, the path is the percent-encoded account alone.

A helper constructed with secret `S46SQCPPTCNPROMHWYBDCTBZXV` and no account or issuer builds exactly:

`otpauth://totp/Secret?secret=S46SQCPPTCNPROMHWYBDCTBZXV`

After checking `123456`, a later build is still that same string.

Passing `name` on a helper that had no account replaces the `Secret` placeholder for that call. Passing `issuer_name` on a helper that had no issuer adds the issuer to the path and the `issuer` query field for that call.

### Query fields written from the helper

- `secret` — always written, as the helper’s base32 secret text.
- `issuer` — written when an issuer is present (constructor `issuer` or this call’s `issuer_name`).
- `digits` — written only when the digit count is not `6`.
- `period` — written only when the time-step length (constructor `interval`) is not `30`.
- `algorithm` — written only when the digest is not `SHA1`, and spelled in uppercase (`SHA256`, `SHA512`).

A helper with secret `wrn3pqx5uqxqvnqr` and account `alice@example.com` (no issuer) has path `/alice%40example.com` and query field `secret` `wrn3pqx5uqxqvnqr`. Default digit count, default time-step, and `SHA1` are omitted.

A helper with secret `c7uxuqhgflpw7oruedmglbrk7u6242vb`, digit count `8`, time-step `60` seconds, digest `SHA256`, account `baco@peperina`, and issuer `FooCorp` has path `/FooCorp:baco%40peperina` and query fields `secret`, `issuer` `FooCorp`, `digits` `8`, `period` `60`, and `algorithm` `SHA256`. The same helper with `SHA1` instead of `SHA256` omits `algorithm` and still includes `digits` and `period`. The same helper with the default 30-second step and `SHA1` includes `digits` `8` and omits `period` and `algorithm`.

### Percent-encoding

Special characters in the label and query are percent-encoded. `@` becomes `%40`. `!` becomes `%21`. A space becomes `%20`, not a plus sign.

### Extra keywords and `image`

An extra keyword whose value is text is included in the query under that keyword’s name.

`image` is accepted only when its value is an `https` URL with both a host and a path. That URL is written as query field `image`, percent-encoded. A helper with secret `GEZDGNBV`, digest `SHA512`, account `n`, issuer `i`, and `image` `https://test.net/test.png` builds exactly:

`otpauth://totp/i:n?secret=GEZDGNBV&issuer=i&algorithm=SHA512&image=https%3A%2F%2Ftest.net%2Ftest.png`

### Refusal

An `image` value that is not an `https` URL with both a host and a path (for example `nourl`, a token with no scheme, a non-`https` URL, an `https` URL with no host, or an `https` URL with no path) is refused. The build does not succeed: no `otpauth` URI is handed back. The call may raise, or it may return a value that is not `otpauth` text. Returning `otpauth` text is not a refusal.

An extra query field whose value is not text is refused the same way. The exception class and message text are not a compatibility contract.

### Present-package use

When the `otpkit` package is importable, this program completes successfully and prints the time-based README URI above:

```
from `otpkit` import `TOTP`
helper = `TOTP`("JBSWY3DPEHPK3PXP")
uri = helper.`provisioning_uri`(`name`="alice@google.com", `issuer_name`="Secure App")
print(uri)
constructed = `TOTP`("JBSWY3DPEHPK3PXP", `name`="alice@google.com", `issuer`="Secure App")
same = constructed.`provisioning_uri`()
```

`uri` and `same` are equal. Output-equality alone is not proof that the real package ran.

## `otpkit.parse_uri`

Import `parse_uri` from the package root `otpkit` (`from `otpkit` import `parse_uri``). `parse_uri` is a callable. The caller supplies one provisioning-URI string. A successful parse returns an `HOTP` or `TOTP` helper that can emit codes and can rebuild an equivalent URI. This call is the inverse of a well-formed `provisioning_uri` build for types `totp` and `hotp`, except that an `image` query field is not recovered on rebuild.

Typical parse:

```
from `otpkit` import `parse_uri`
helper = `parse_uri`(<uri>)
```

### Signature

```
`parse_uri`(<uri>)
```

The URI is the first positional argument. It is text. Callers pass it positionally.

On success, the call returns a helper object: an instance of `TOTP` when the URI type is `totp`, or an instance of `HOTP` when the URI type is `hotp`. The value is not `None`, not a text string, and not a number.

The returned helper emits codes through `at` and rebuilds a URI through `provisioning_uri`, using the same argument spellings those types already publish (including rebuild overlays `name`, `issuer_name`, and — on an HMAC helper — `initial_count`). A later code check on that helper uses `verify`. Checking a wrong candidate returns a negative result and does not abort the caller. That outcome is distinguishable from a refused parse, which hands back no helper.

The call does not read or write files, does not mutate the process environment, and does not exit the host process.

### URI type and query fields that become helper state

The scheme must be `otpauth`. The URI type (the host) selects the helper kind: `totp` yields a `TOTP` helper; `hotp` yields an `HOTP` helper.

Query fields that become helper state, by exact name:

- `secret` — the shared secret (base32 text). Required. It is the same secret a direct `TOTP` or `HOTP` construction would take as its first positional argument.
- `counter` — HMAC starting counter. Becomes constructor `initial_count`. When omitted on a `hotp` URI, the starting counter is `0`. An HMAC rebuild always writes `counter`, including `0`.
- `period` — time-step length in seconds. Becomes constructor `interval`. When omitted on a `totp` URI, the time-step is `30`.
- `digits` — digit count. Becomes constructor `digits`. When omitted, the digit count is `6`. An `otpauth` URI may carry only `6`, `7`, or `8`.
- `algorithm` — digest. Becomes constructor `digest`. Accepted values are `SHA1`, `SHA256`, and `SHA512` (uppercase). When omitted, or when the last value is `SHA1`, the digest is `SHA1` — the same codes as constructing the helper with no `digest`. A rebuild omits `algorithm` when the digest is `SHA1`.
- `issuer` — issuer text in the query. Combined with the path label as described below. The query key is `issuer`, not `issuer_name`.
- `image` — optional. Accepted and ignored. It does not change codes. A rebuild omits `image`. The parser does not require the value to be an `https` URL.

When the same query field among `secret`, `digits`, `algorithm`, `period`, and `counter` appears more than once, the last occurrence is the one that takes effect. `issuer` does not follow that last-occurrence rule; see the issuer comparison below.

A pathless URI such as `otpauth://totp?secret=GEZDGNBV` is accepted. When the URI never supplied an account name, a no-overlay rebuild uses the placeholder `Secret`.

### Inverse of a built URI

Parsing a URI that `provisioning_uri` just built, then calling `provisioning_uri` on the parsed helper with no overlay, yields the same URI string. That round-trip holds for HMAC and time-based builds, including issuer punctuation, non-default `digits`, `period`, `algorithm`, and starting `counter`.

It does not hold when the built URI carries `image`: that field is ignored at parse time and is absent from the rebuilt string. The rest of the helper state is kept.

Parsing `otpauth://totp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App` yields a `TOTP` helper whose codes match ``TOTP`("JBSWY3DPEHPK3PXP")` at Unix `0` and at other instants, including the next 30-second step. A no-overlay rebuild of that helper is type `totp`.

Parsing `otpauth://hotp/Secure%20App:alice%40google.com?secret=JBSWY3DPEHPK3PXP&issuer=Secure%20App&counter=0` yields an `HOTP` helper whose code at relative count `0` matches ``HOTP`("JBSWY3DPEHPK3PXP")`. A no-overlay rebuild is type `hotp` and includes `counter` `0`.

A time-based helper constructed with secret `S46SQCPPTCNPROMHWYBDCTBZXV` and no account or issuer builds `otpauth://totp/Secret?secret=S46SQCPPTCNPROMHWYBDCTBZXV`; parse-then-rebuild yields that same string.

An HMAC helper with secret `wrn3pqx5uqxqvnqr`, account `alice@example.com`, and issuer `FooCorp!` round-trips with `%21` still in the path and with query `issuer` `FooCorp!` and a `counter` field.

A time-based helper with secret `c7uxuqhgflpw7oruedmglbrk7u6242vb`, digit count `8`, time-step `60`, digest `SHA256`, account `baco@peperina`, and issuer `FooCorp` round-trips with query `secret`, `digits` `8`, `period` `60`, and `algorithm` `SHA256`. The parsed helper emits the same 8-digit code as that builder at the same Unix instant. The same helper with `SHA1` instead of `SHA256` round-trips with `digits` `8` and `period` `60` and omits `algorithm`. The same helper with the default 30-second step and `SHA1` round-trips with `digits` `8` and omits `period` and `algorithm`.

An HMAC helper with that same secret, digit count `8`, and digest `SHA256` round-trips with `digits` `8`, `algorithm` `SHA256`, and a `counter` field. The parsed helper’s code at relative count `0` matches ``HOTP`` constructed directly with that secret, `digits` `8`, and the SHA-256 digest.

An HMAC starting counter of `12` is recovered so a no-overlay rebuild writes `counter` `12`. A URI built with an `initial_count` overlay of `0` on a helper whose stored starting counter is `7` is recovered so a no-overlay rebuild writes `counter` `0`.

Parsing `otpauth://totp/i:n?secret=GEZDGNBV&issuer=i&algorithm=SHA512&image=https%3A%2F%2Ftest.net%2Ftest.png` succeeds as a `TOTP` helper that emits `816660` at Unix `0`. A no-overlay rebuild omits `image` and still includes `secret` `GEZDGNBV`, `issuer` `i`, `algorithm` `SHA512`, and path label `i:n`.

### Named GEZDGNBV codes

Parsing `otpauth://totp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1` yields a `TOTP` helper that emits `734055` at Unix `0`, `662488` at Unix `30`, and `289363` at Unix `60`. Those strings match ``TOTP`("GEZDGNBV")`. A no-overlay rebuild is exactly `otpauth://totp/Secret?secret=GEZDGNBV`. Rebuilding with `name` `n` and `issuer_name` `i` yields exactly `otpauth://totp/i:n?secret=GEZDGNBV&issuer=i`.

Parsing that same URI with an added `period` `60` (`otpauth://totp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1&period=60`) yields `734055` at Unix `30` and `662488` at Unix `60`. Rebuilding with `name` `n` and `issuer_name` `i` includes `period` `60`. A time-step other than `30`, including `60` and a time-step strictly greater than `60`, is accepted and becomes the helper’s `interval`. For secret `GEZDGNBV` and a time-step strictly greater than `60`, Unix `30` and Unix `60` both still emit `734055`, which is not the period-`60` code at Unix `60`. That helper matches ``TOTP`("GEZDGNBV", `interval`=<that time-step>)`.

Last `period` wins: `period=30&period=60` at Unix `30` emits `734055`; `period=60&period=30` at Unix `30` emits `662488`.

Parsing `otpauth://hotp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1` yields an `HOTP` helper that emits `734055` at relative count `0`, `662488` at `1`, and `289363` at `2`. Rebuilding with `name` `n` and `issuer_name` `i` includes `counter` `0`. Parsing the same URI with `counter` `1` yields `662488` at relative count `0` and `289363` at `1`, and the rebuilt URI includes `counter` `1`.

Last `counter` wins: `counter=0&counter=1` at relative count `0` emits `662488`; `counter=1&counter=0` at relative count `0` emits `734055`.

Parsing `otpauth://totp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA256` yields `918961` at Unix `0` and `934470` at Unix `9000`. Parsing `otpauth://totp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA512` yields `816660` at Unix `0` and `524153` at Unix `9000`. Those SHA-256 and SHA-512 strings are not the SHA-1 codes at Unix `0`. Last `algorithm` wins: a totp URI that lists `SHA256` then `SHA1` emits the SHA-1 codes; a URI that lists `SHA1` then `SHA256` emits the SHA-256 codes. The same last-occurrence rule holds for `SHA512`, and for `hotp` as well as `totp`. A totp or hotp URI whose last `algorithm` is `SHA256` or `SHA512` emits the same codes as constructing `TOTP` or `HOTP` directly with that secret and the matching digest.

Last `secret` wins on both totp and hotp: the last `secret` value is the shared secret used to emit codes.

Last `digits` wins on both totp and hotp: `digits=6&digits=8` emits an 8-digit code matching a helper constructed with `digits` `8`; `digits=8&digits=6` emits the 6-digit SHA-1 code `734055` for secret `GEZDGNBV`. An explicit `digits` `7` is accepted. Parsing `otpauth://totp?secret=GEZDGNBV&digits=7` (and the hotp counterpart) yields a helper whose codes are 7-digit text matching ``TOTP`("GEZDGNBV", `digits`=7)` or ``HOTP`("GEZDGNBV", `digits`=7)`, and whose rebuild includes `digits` `7`.

### Label: literal colon versus encoded colon

The path label uses a literal colon as the issuer-and-account separator. A percent-encoded colon (`%3A`) is part of the issuer or the account name, not a separator. The separator is that literal colon in the path as written; decoding the path before finding it would turn `%3A` into a colon and mis-read the two parts. A space in the label is `%20`; `@` is `%40`.

Parsing `otpauth://totp/Text%3A%20More%20Text:Secret?secret=FFFFFFFAAAAAABBBBBBB&issuer=Text%3A%20More%20Text` yields account name `Secret` and issuer `Text: More Text`. A no-overlay rebuild recovers those two parts: decoded path `Text: More Text:Secret` and query `issuer` `Text: More Text`.

Parsing `otpauth://totp/a%3Ab?secret=GEZDGNBV` yields account name `a:b` and no issuer. A no-overlay rebuild has decoded path `a:b` and omits query `issuer`.

Building a URI from ``TOTP`("FFFFFFFAAAAAABBBBBBB", `name`="Secret", `issuer`="Text: More Text")`, then parsing that URI, recovers issuer `Text: More Text` and account `Secret`.

Parsing `otpauth://totp/Big%20Corp:bob?secret=GEZDGNBV&issuer=Big%20Corp` yields account `bob` and issuer `Big Corp`.

An issuer that itself contains a literal colon, stored on a helper and written through `provisioning_uri`, parses back to that same issuer and account. The separator is the unencoded colon between the two parts, not a `%3A` inside either part.

### Image is accepted and ignored

Parsing `otpauth://totp?secret=GEZDGNBV&image=foobar` succeeds and returns a `TOTP` helper whose code at Unix `0` is `734055` — the same as ``TOTP`("GEZDGNBV")` and the same as parsing `otpauth://totp?secret=GEZDGNBV`. A rebuild omits `image` and still includes `secret` `GEZDGNBV`. A totp URI whose `image` value is a token with no scheme is accepted the same way: codes match a helper constructed with that secret, and the rebuild omits `image`.

### Issuer in both the label and the query

When an issuer appears both in the label (the decoded text before the literal colon) and in the query, each query `issuer` is compared to the label issuer as it is read. If any occurrence is not equal, the parse is refused.

Equal values succeed, including a repeated equal pair (`issuer=<I>&issuer=<I>`). Label issuer `I` with query `issuer` `I` succeeds, and a no-overlay rebuild recovers issuer `I` and the account. This comparison applies to both `totp` and `hotp`.

A mismatch is refused even when a later query `issuer` equals the label. Label issuer `I` with query `issuer=<J>&issuer=<I>` is refused. Label issuer `I` with only query `issuer` `J` is refused. Parsing `otpauth://totp/SomeIssuer:?issuer=AnotherIssuer` is refused.

### Refusal

Each of the following is a failed parse: no helper is handed back. The call may raise, or it may return a non-helper (`None`, text, or a number). Returning a helper is not a refusal. The exception class and message text are not a compatibility contract. These refusals are distinguishable from a successful parse that then fails a later `verify`.

- Scheme is not `otpauth`. Parsing `http://hello.com` is refused. Parsing `https://hello.example/path?secret=GEZDGNBV` is refused. Any other scheme that is not `otpauth` is refused, even when the query carries a `secret`.
- No `secret`. Parsing `otpauth://totp` is refused. Parsing `otpauth://hotp` is refused. Parsing `otpauth://totp?digits=6` is refused. Parsing `otpauth://hotp?counter=0` is refused.
- Type is neither `totp` nor `hotp`. Parsing `otpauth://derp?secret=foo` is refused. Any other type that is not `totp` or `hotp` is refused.
- `digits` is not `6`, `7`, or `8`. Parsing `otpauth://totp?digits=-1` is refused. Parsing `otpauth://totp?secret=GEZDGNBV&digits=-1` is refused. The same refusal applies to totp and hotp for any other integer digit count outside `{6, 7, 8}`. Digit count `7` is not this refusal.
- Label issuer and query `issuer` disagree as described above.
- `algorithm` is not `SHA1`, `SHA256`, or `SHA512`. Parsing `otpauth://totp?algorithm=aes` is refused. The same refusal applies to totp and hotp for any other algorithm token. An explicit `algorithm` `SHA1` on a hotp URI is accepted.

### Present-package use

When the `otpkit` package is importable, this program completes successfully and prints `734055`:

```
from `otpkit` import `HOTP`, `TOTP`, `parse_uri`
helper = `parse_uri`("otpauth://totp?secret=GEZDGNBV")
code = helper.`at`(0)
print(code)
rebuilt = helper.`provisioning_uri`()
direct = `TOTP`("GEZDGNBV")
hotp = `parse_uri`("otpauth://hotp?algorithm=SHA1&secret=GEZDGNBV&algorithm=SHA1")
hotp_code = hotp.`at`(0)
```

`code` equals `direct.`at`(0)`. `rebuilt` is `otpauth://totp/Secret?secret=GEZDGNBV`. `hotp_code` is `734055`. Output-equality alone is not proof that the real package ran.

## `otpkit.random_base32`

Import `random_base32` from the package root `otpkit` (`from `otpkit` import `random_base32``). Emit one newly drawn base32 shared secret as a text string. This helper does not construct an `HOTP` or `TOTP` instance.

### Signature

```
`random_base32`(`length`=32)
```

- `length` — optional requested width as an integer. Default 32. The caller supplies it as the argument named `length`. When omitted, the width is 32.

### Return shape

On success, returns a Python text string (`str`) whose length equals the requested width (32 when `length` is omitted). The value is not bytes, not an integer, and not `None`.

Every character is one of `ABCDEFGHIJKLMNOPQRSTUVWXYZ234567` — that is, `A` through `Z` or `2` through `7`. The characters `0`, `1`, `8`, and `9` do not appear.

The call does not read or write files, does not mutate the process environment, and does not exit the host process.

### Default width

A call with no arguments, and a call that sets `length` to 32, each return a string of length 32 from that alphabet. The default width is 32, not 34.

### Widths at or above the minimum

The minimum accepted width is 32 (160 bits at five bits per base32 character). A requested `length` of 32 succeeds. A requested `length` of 34 succeeds and returns a string of length 34 from the same alphabet. Any integer width at or above 32 succeeds and returns a string of exactly that length from the same alphabet.

### Widths below the minimum

A requested `length` of 31 does not succeed. The caller observes a failure: the call raises. No secret string is returned. Returning `None` without raising is not a failure. The exception class and message text are not a compatibility contract.

The same refusal applies to every integer width below 32: the call raises and does not hand back a secret string.

### Fresh draw

Each successful call returns a newly drawn string from the stated alphabet, not a single built-in constant. Two or more successful default-width calls are not all the same 32-character string. Two or more successful calls at `length` 34 are not all the same 34-character string. Adjacent draws need not differ, and pairwise uniqueness is not required.

## `otpkit.random_hex`

Import `random_hex` from the package root `otpkit` (`from `otpkit` import `random_hex``). Emit one newly drawn hex-encoded shared secret as a text string. This helper does not construct an `HOTP` or `TOTP` instance. Hex secrets are for applications that want a hex-encoded key; `HOTP` and `TOTP` still consume base32.

### Signature

```
`random_hex`(`length`=40)
```

- `length` — optional requested width as an integer. Default 40. The caller supplies it as the argument named `length`. When omitted, the width is 40.

### Return shape

On success, returns a Python text string (`str`) whose length equals the requested width (40 when `length` is omitted). The value is not bytes, not an integer, and not `None`.

Every character is one of `ABCDEF0123456789` — that is, `A` through `F` or `0` through `9`. Lowercase letters and letters outside `A`–`F` do not appear.

The call does not read or write files, does not mutate the process environment, and does not exit the host process.

### Default width

A call with no arguments, and a call that sets `length` to 40, each return a string of length 40 from that alphabet. The default width is 40, not 42.

### Widths at or above the minimum

The minimum accepted width is 40 (160 bits at four bits per hex character). A requested `length` of 40 succeeds. A requested `length` of 42 succeeds and returns a string of length 42 from the same alphabet. Any integer width at or above 40 succeeds and returns a string of exactly that length from the same alphabet.

### Widths below the minimum

A requested `length` of 39 does not succeed. The caller observes a failure: the call raises. No secret string is returned. Returning `None` without raising is not a failure. The exception class and message text are not a compatibility contract.

The same refusal applies to every integer width below 40: the call raises and does not hand back a secret string.

### Fresh draw

Each successful call returns a newly drawn string from the stated alphabet, not a single built-in constant. Two or more successful default-width calls are not all the same 40-character string. Two or more successful calls at `length` 42 are not all the same 42-character string. Adjacent draws need not differ, and pairwise uniqueness is not required.

