# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**Signtoken** is a Python library of helpers for passing data to untrusted environments and getting it back intact. A token is cryptographically signed so that a later recovery can tell whether anyone changed the payload. The receiver can read the data; they cannot produce a different payload that still verifies, unless they also have the secret key.

The product delivers:

- Data is cryptographically signed so a token that has been tampered with is refused.
- How the payload is serialized is customizable. The default is JSON.
- A timestamp can be recorded at sign time and checked automatically on load. Data is compressed when that actually shortens a URL-safe token.

A first-time integrator constructs a signing helper with a secret key, signs a value, and later recovers the original bytes from that token. Timestamped and URL-safe serialize-and-sign helpers refine that same idea; their call spellings belong with those symbols.

The finished product is an **importable Python library**, not a command-line program, not a network service, and not a wire protocol of its own. Integrators install the package and construct helpers in Python. There is no product-owned configuration file.

The product is a pure-Python library with zero declared runtime dependencies. No compiled extension, native code, GPU, or accelerator is required. The language is Python 3.10 or newer. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

Integrity, not confidentiality: a verified token yields the original value. The payload is not encrypted.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is the importable package `signtoken`. Callers write `import `signtoken`` or `from `signtoken` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `signtoken` under `src`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

The independently verifiable library entries named from this package root are:

- `Signer` — sign a byte or text value, recover the original bytes from a valid token, and check validity without handing back the payload.
- `TimestampSigner` — the timestamped signing helper. It signs like `Signer` and also records the signing time in the token. On recovery the caller may supply a maximum age and may ask to receive that signing time.
- `Serializer` — serialize an object, sign that payload, and recover the original object from a valid token. Default dump/load is JSON.
- `TimedSerializer` — the timestamped serialize-and-sign helper. It serializes like `Serializer` and signs with `TimestampSigner` by default, so the token records the signing time. On load the caller may supply a maximum age and may ask to receive that signing time.
- `URLSafeSerializer` — the URL-safe serialize-and-sign helper. It serializes like `Serializer` (same dump/load family). Tokens use a restricted alphabet. Default dump/load is compact JSON. The payload is compressed when that shortens it.
- `URLSafeTimedSerializer` — the URL-safe timestamped serialize-and-sign helper. It serializes like `URLSafeSerializer` (restricted alphabet, compact JSON, compression when that shortens the payload) and also applies the age check: on load the caller may supply a maximum age and may ask to receive that signing time.
- `HMACAlgorithm` — the HMAC signing algorithm. An instance may be supplied as a signer’s algorithm.
- `NoneAlgorithm` — the no-op signing algorithm that emits an empty signature. An instance may be supplied as a signer’s algorithm.

Callers construct `Signer` with a secret key (one key, or a list of keys oldest-to-newest). They may also supply a salt, a separator, a digest, a key-derivation scheme, and a signing algorithm. Text values are encoded as `UTF-8` at sign time. On the basic signer, recovery always yields bytes.

Callers construct `Serializer` with a secret key (one key, or a list of keys oldest-to-newest). They may also supply a salt, an internal dump/load object, extra dump options, a signer type, signing options, and fallback signing configurations. Exact parameter lists belong with that symbol.

**Not in this surface.** A command-line program, HTTP server, or cookie framework. Encrypting payloads so the receiver cannot read them. A general-purpose JWT / JWS stack. Key-generation or key-storage machinery. A header-bearing token format.

### Naming conventions

**Product and package.** The product identity is Signtoken. The installable distribution name and the importable top-level package are spelled `signtoken`.

**Classes.** Published types use PascalCase: `Signer`, `TimestampSigner`, `Serializer`, `TimedSerializer`, `URLSafeSerializer`, `URLSafeTimedSerializer`, `HMACAlgorithm`, `NoneAlgorithm`. Each is a callable class. Callers construct instances by calling the class.

**Methods.** Instance operations use snake_case: `sign`, `unsign`, `validate` on the basic signer; `dumps`, `loads`, `dump`, `load`, `loads_unsafe`, `load_unsafe` on the serialize-and-sign helper.

**Constructor keywords.** Optional construction arguments use snake_case: `salt`, `sep`, `key_derivation`, `digest_method`, `algorithm` on the basic signer; `serializer`, `serializer_kwargs`, `signer`, `signer_kwargs`, `fallback_signers` on the serialize-and-sign helper (in addition to `salt`). The secret is the first positional argument.

**Key-derivation names.** The four built-in scheme spellings are exactly `concat`, `django-concat`, `hmac`, and `none`. The product default is `django-concat`.

**Layout.** The importable package directory is `signtoken` under `src`.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**No command-line product.** There is no console-script entry and no `python -m` program that is part of this surface. Outcomes are returned or raised from library calls. Library entries do not exit the host process as their success or failure report.

**Library substrate.** When the `signtoken` package is not importable, a program that does `from `signtoken` import `Signer``, constructs `Signer` with secret `secret-key`, calls `sign` on the text `my string`, and then calls `unsign` on that token does not run to completion and does not yield the original value. When the package is importable, that same construction, sign, and recovery yields `my string` as bytes.

When the package is not importable, a program that does `from `signtoken` import `Serializer``, constructs `Serializer` with secret `secret-key`, calls `dumps` on the mapping `{'id': 42}`, and then calls `loads` on that token does not run to completion and does not yield that mapping. When the package is importable, that same construction, dump, and load recovers `{'id': 42}`.

**Token layout.** On the basic signer (`Signer`), a signed token is bytes. It is the payload, then the separator, then a signature. The default separator is a period (`.`). Recovery splits on the **last** separator, so a payload that itself contains that separator still round-trips. Replacing the separator in a signed token with a different character such as `*` makes recovery refuse the token and the validity check report failure.

On `Serializer`, a token is the serialized payload, then the separator, then a signature. The default separator is a period (`.`). When the default JSON dump returns text, `dumps` returns text (`str`), not bytes. `loads` accepts that token as text or as its UTF-8 bytes.

**Recovered value on the basic signer is bytes.** On `Signer`, recovery always yields a `bytes` object, never text. If the input to `sign` was text, it was encoded as `UTF-8` at sign time. Signing the same characters as text and as those `UTF-8` bytes recovers identically.

**Recovered value on `Serializer` is the original object.** Default JSON `dumps` returns text. `loads` accepts text or bytes and, on success, yields an object equal to the original — including JSON null (`None`), JSON true, JSON false, text, lists, and mappings. When a custom dump/load object’s `dumps` returns bytes, this helper’s `dumps` returns bytes; `loads` still accepts text or bytes for a given token.

**Validity is not recovery.** A validity check on a good token reports success without returning the payload. A validity check on a bad token reports failure by returning a false value; it does not raise. Recovery of a bad token refuses by raising.

**Default digest and derivation.** The default digest is SHA-1. A signer given SHA-1 explicitly produces the same token as one that leaves the digest at the default. The default key-derivation scheme is `django-concat`: a signer that omits the scheme interchanges tokens with one that sets the scheme to `django-concat`.

**Default algorithm.** The default signing algorithm is HMAC using the configured digest. HMAC rejects a changed payload. The no-op algorithm emits an empty signature and does not provide tamper detection.

**Separator alphabet.** ASCII letters, digits, hyphen, underscore, and equals are not allowed as separators, because they can appear in the encoded signature. Constructing a signer with any of those as the separator is refused. A period is accepted and is the default.

**Secret lists.** A secret may be a list of keys oldest to newest. Signing uses the last (newest) key. Recovery succeeds if any remaining key verifies. Dropping an older key makes tokens that were signed with only that key start to be refused.

**Salt.** Extra material mixed with the secret to isolate signing contexts. Two signers that share a secret but use different salts do not recover each other’s tokens, except under the `none` key-derivation scheme, where the salt is not mixed in. When the caller omits the salt, a product-defined default salt is used: two identically constructed signers with the same secret and no caller salt interchange tokens.

**Integrity, not confidentiality.** Anyone who can see a token can read the payload bytes in it. They still cannot forge a new payload that verifies without the secret.

## `signtoken`

The installable distribution and the importable top-level package are both `signtoken`. Callers declare the interface from this package root (`import `signtoken`` or `from `signtoken` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `signtoken` under `src`.

These names are importable as ``signtoken`.<name>` and as `from `signtoken` import <name>`:

- `HMACAlgorithm`
- `NoneAlgorithm`
- `Serializer`
- `Signer`
- `TimedSerializer`
- `TimestampSigner`
- `URLSafeSerializer`
- `URLSafeTimedSerializer`

Each of those names is a callable class.

Typical import used to construct the serialize-and-sign helper, to name the signer type it wraps, and to select HMAC or the no-op algorithm:

```
from `signtoken` import `HMACAlgorithm`, `NoneAlgorithm`, `Serializer`, `Signer`
```

Typical import used to construct the timestamped signer and the timestamped serialize-and-sign helper:

```
from `signtoken` import `TimedSerializer`, `TimestampSigner`
```

Typical import used to construct the URL-safe serialize-and-sign helper and the URL-safe timestamped serialize-and-sign helper from the package root (secret `secret key`, salt `auth`):

```
from `signtoken` import `URLSafeSerializer`, `URLSafeTimedSerializer`
h = `URLSafeSerializer`('secret key', salt='auth')
timed = `URLSafeTimedSerializer`('secret key', salt='auth')
```

A caller that only needs the serialize-and-sign helper may import `from `signtoken` import `Serializer``. A caller that only needs the signing helper, or that passes that type as a fallback signing configuration, may import `from `signtoken` import `Signer``. A caller that supplies an HMAC or no-op algorithm instance may import `from `signtoken` import `HMACAlgorithm`` or `from `signtoken` import `NoneAlgorithm``. A caller that only needs the timestamped signer may import `from `signtoken` import `TimestampSigner``. A caller that only needs the timestamped serialize-and-sign helper may import `from `signtoken` import `TimedSerializer``. A caller that only needs the URL-safe serialize-and-sign helper may import `from `signtoken` import `URLSafeSerializer``. A caller that only needs the URL-safe timestamped serialize-and-sign helper may import `from `signtoken` import `URLSafeTimedSerializer``.

When the `signtoken` package is importable, constructing `Serializer` with secret `secret-key`, calling `dumps` on the mapping whose `id` is 42, and calling `loads` on that token recovers that mapping. When the package is not importable, a program that performs that same import, construction, dump, and load does not run to completion and does not yield that mapping.

## `signtoken.HMACAlgorithm`

Import `HMACAlgorithm` from the package root `signtoken` (`from `signtoken` import `HMACAlgorithm``). Callable class for the HMAC signing algorithm. Callers construct an instance and pass that instance as a `Signer`’s `algorithm`.

### Signature

```
`HMACAlgorithm`(`digest_method`=None)
```

- `digest_method` — optional hash constructor compatible with HMAC, such as `hashlib.sha1`, `hashlib.md5`, or `hashlib.sha512`. When omitted or `None`, SHA-1 is used.

Calling the class returns an algorithm instance. The instance is what is passed to `Signer`, not the class object itself.

### Observable effect when used as a signer algorithm

A `Signer` constructed with `algorithm`=`HMACAlgorithm`() uses HMAC. Signing then recovering a value with that same signer yields the original value as bytes. The signature section of the token is non-empty.

HMAC provides tamper detection. Changing the payload of a valid token — for example replacing the bytes `my` with `other` in a token that was signed for `my string` — makes `unsign` refuse the token and `validate` report failure.

Tokens produced under HMAC do not interchange with tokens produced under `NoneAlgorithm`: a no-op signer refuses an HMAC token, and an HMAC signer refuses a no-op token.

Omitting `algorithm` on `Signer` selects HMAC using that signer’s configured digest. Passing an `HMACAlgorithm` instance is the explicit form of the same algorithm family.

## `signtoken.NoneAlgorithm`

Import `NoneAlgorithm` from the package root `signtoken` (`from `signtoken` import `NoneAlgorithm``). Callable class for the no-op signing algorithm. Callers construct an instance and pass that instance as a `Signer`’s `algorithm`.

### Signature

```
`NoneAlgorithm`()
```

No parameters. Calling the class returns an algorithm instance. The instance is what is passed to `Signer`, not the class object itself.

### Observable effect when used as a signer algorithm

A `Signer` constructed with `algorithm`=`NoneAlgorithm`() emits an empty signature. Signing the text `value` yields a bytes token whose layout is the payload, then the separator, then an empty signature section (`b""`). Recovering that token with the same signer still yields `value` as bytes.

The no-op algorithm does **not** provide tamper detection. Changing the payload of a valid token — for example replacing the bytes `my` with `other` in a token that was signed for `my string` — is recovered as `other string` as bytes, and `validate` reports success on that changed token.

Tokens produced under `NoneAlgorithm` do not interchange with tokens produced under HMAC: an HMAC signer refuses a no-op token, and a no-op signer refuses an HMAC token.

## `signtoken.Serializer`

Import `Serializer` from the package root `signtoken` (`from `signtoken` import `Serializer``). Callable class for the serialize-and-sign helper. It serializes an object with an internal dump/load object (the language JSON library by default), then signs that payload with a `Signer`. It does not record a timestamp and does not force a URL-safe alphabet.

This helper wraps a `Signer`: secret lists, salts, separators, digests, and key-derivation schemes behave as they do on the signer this helper constructs.

### Signature

```
`Serializer`(secret_key, `salt`=..., `serializer`=None, `serializer_kwargs`=None, `signer`=None, `signer_kwargs`=None, `fallback_signers`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Dumping signs with the **last** (newest) key. Load tries remaining keys from newest to oldest and succeeds if any remaining key verifies.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. When omitted, a product-defined default salt is used.
- `serializer` — the internal dump/load object. An object that provides `dumps` and `loads`. When omitted or `None`, the language JSON library is used.
- `serializer_kwargs` — a mapping of extra dump options forwarded into the internal dump object’s `dumps`. When omitted or `None`, no extra dump options are forwarded.
- `signer` — a signer **class** (the `Signer` type, or a subclass) instantiated when signing. When omitted or `None`, `Signer` is used.
- `signer_kwargs` — a mapping of keyword arguments forwarded when instantiating that signer class, such as `key_derivation` and `digest_method`. When omitted or `None`, the signer’s own defaults apply.
- `fallback_signers` — a list of fallback signing configurations tried when the current signer cannot verify a token. When omitted or `None`, there are no fallbacks.

The class is callable. Construction returns a helper instance. Construction does not dump an object, does not write files, and does not exit the host process.

An illegal separator forwarded through `signer_kwargs` (``sep`` set to a hyphen, an underscore, an equals sign, an ASCII letter, or an ASCII digit) is refused on the `Signer` this helper constructs: either constructing this helper raises, or the first `dumps` raises, and the caller does not receive a signed token. A period (``.``) as `sep` is accepted and round-trips.

### `dumps`

```
`dumps`(obj, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Serializes `obj` with the internal dump/load object, then signs that payload. Returns a token: the serialized payload, then the separator, then a signature. The default separator is a period (``.``).

When the internal dump/load object’s `dumps` returns text, this call returns text (`str`), not bytes. When that `dumps` returns bytes, this call returns bytes.

The call does not mutate the process environment and does not exit the host process.

### `loads`

```
`loads`(s, `salt`=None)
```

- `s` — a token previously produced by `dumps`, as text or as bytes.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Reverse of `dumps`. On success, returns an object equal to the original. Load accepts either text or bytes for a given token: a default JSON token returned as text also loads when that same token is supplied as its `UTF-8` bytes, and a bytes token that is `UTF-8` also loads when supplied as text.

On failure, raises. Failure does not return the original object as a successful load. A signature mismatch and a payload-decode failure are distinguishable from each other and from success (see below).

### `dump` / `load`

```
`dump`(obj, f, `salt`=None)
`load`(f, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `f` — a file-like stream. `dump` writes the token that `dumps` would return (`f.write`). `load` reads the stream (`f.read`) and then loads. The stream must be compatible with the token kind: a text-mode stream (including a real text file) for a text token; a binary-mode stream for a bytes token.
- `salt` — optional per-call salt, as on `dumps` / `loads`.

Dumping an object into a stream and loading it back from that stream recovers an equal object. These calls do not exit the host process.

### `loads_unsafe` / `load_unsafe`

```
`loads_unsafe`(s, `salt`=None)
`load_unsafe`(f, `salt`=None)
```

- `s` — a token, as text or bytes.
- `f` — a file-like stream; `load_unsafe` reads it and then behaves as `loads_unsafe`.
- `salt` — optional per-call salt, as on `loads`.

Inspection entry for signature problems. Returns a **pair** of two items. It does not make a bad signature look valid.

- Valid token: first item is true (signature valid); second item is the original object.
- Token whose signature does not verify, but whose payload can still be deserialized: first item is false; second item is the original object. The caller is not aborted: the pair is returned.
- Token whose signature does not verify and whose remaining payload also cannot be deserialized: first item is false; second item is not a deserialized object — it is not the original object, not leftover payload bytes or text, and not the chopped token.

The first item is false whenever verification failed, even if a payload is still yielded for inspection. A true first item and a false first item are distinguishable.

When the signature **is** valid but the payload cannot be deserialized, this call does **not** convert that case into a pair: the caller observes the same payload-decode failure as `loads` (the call raises).

### Token layout (default JSON)

The default internal dump/load object is the language JSON library. Dumping then loading the same object recovers an equal object. This holds at least for JSON null (`None`), JSON true, JSON false (recovered false is not JSON true), a text string (including non-ASCII text), a list of integers, and a mapping.

For that default, the token for the list of integers 1 through 4 includes that list’s JSON text `[1, 2, 3, 4]` (spaces after commas), then the separator, then a non-empty signature. The payload section is exactly that JSON text: this helper does not insert a timestamp field between payload and signature, and the token still contains JSON brackets and spaces.

A JSON string whose text contains a period still round-trips. That token is still JSON text, then the separator, then a signature: an interior period inside the JSON is not treated as the payload/signature boundary.

Anyone who can see a default JSON token can read the JSON text in it. They still cannot forge a new payload that verifies without the secret.

### Per-call salt

A `dumps` that passes an explicit `salt` `other` produces a token that the same helper will not `loads` unless that same `salt` `other` is passed to `loads`. Loading with `salt` `other` recovers the object. Loading with the helper’s default salt refuses the token as a signature mismatch.

Under `key_derivation` `none` (passed through `signer_kwargs`) the salt is not mixed in, so that default-salt load still recovers the object.

### Custom dump/load object

The caller may replace the internal dump/load object by passing `serializer`. That object must provide `dumps` (object in, text or bytes out) and `loads` (text or bytes in, object out). A helper configured that way round-trips values that object can represent. The dumped token carries that object’s format rather than default JSON.

A helper that still uses JSON cannot load a token produced by a helper whose dump format is not JSON when both share secret and salt: if the signature still verifies, that refusal is a payload-decode failure, not a signature mismatch. `loads_unsafe` also raises in that case; it does not return a pair.

Extra dump options in `serializer_kwargs` are forwarded into the internal dump. With the default JSON dump object, `skipkeys`=True skips keys that are not basic JSON key types. Dumping a mapping whose only key is an empty tuple then produces a token that loads as an empty mapping. Dumping a mapping that mixes such a key with a basic key such as `id` loads as the mapping of only the basic keys. Without that option, dumping a mapping of only basic keys still round-trips as that mapping, not as an empty mapping.

### Signer type and signing options

The caller may replace the signer type (`signer`) or the signing options (`signer_kwargs`). Dump then load still round-trips under that helper.

A token from the default helper is not equal to a token for the same object from a helper whose `key_derivation` is `hmac`, and the two helpers do not load each other’s tokens.

A helper whose `signer` is a `Signer` subclass that defaults to SHA-512 produces a different token than both the default helper and an `hmac`-options helper; those tokens do not interchange.

The default digest on this helper is SHA-1. Dumping the JSON list containing only 42 with no digest override produces the same token as dumping it with `digest_method` set to SHA-1 explicitly. Dumping it with SHA-512 produces a different token with a longer signature. A SHA-1 helper without a SHA-512 fallback cannot load the SHA-512 token: that refusal is a signature mismatch. A SHA-1 helper without a SHA-256 fallback cannot load a SHA-256 token: that refusal is a signature mismatch.

### Fallback signing configurations

`fallback_signers` is a list. Fallbacks are tried when the current signer cannot verify a token, in the order the caller listed them, until one verifies or all fail. Each item is one of:

- A **mapping** of signing options (for example `{`digest_method`: …}`) applied to the helper’s signer type.
- An **alternative signer type**, constructed with the helper’s secret, salt, and **current** signing options (`signer_kwargs`). A type whose class-level digest default differs from the helper’s current `digest_method` does **not** override that current option: if the helper pins SHA-1 in `signer_kwargs` and the fallback is only a type whose class default is SHA-256, a SHA-256 token is not loaded. If the helper does not pin a digest in current options, that type’s class default is used.
- A **pair** of a signer type and a mapping of signing options, for example `(`Signer`, {`digest_method`: …})`.

Concrete case: a helper that signs with SHA-256 dumps a mapping; a second helper whose current digest is SHA-1 but that lists SHA-256 as a fallback (any of the three shapes) loads that token and recovers the mapping; a third helper whose current digest is SHA-1 and that has no fallback refuses the token as a signature mismatch. The same rescue holds for SHA-512 with a SHA-512 mapping, type, or pair. Listing SHA-512 then SHA-256, or SHA-256 then SHA-512, still loads a SHA-256 token once the matching fallback is reached.

If every signer including fallbacks fails to verify, `loads` refuses with a signature mismatch. It does not return a decoded object as a successful load.

### Secret rotation

A token produced with secret `a` is accepted by a helper whose secrets are `a` then `b`. After the list becomes only `b`, that same token is refused. A new token produced with secrets `a` then `b` is refused by a helper that only has `a`, and accepted by a helper that has `b`.

### Signature mismatch versus payload-decode failure

**Signature mismatch.** `loads` raises. `loads_unsafe` returns a pair whose first item is false. This is the outcome for a wrong salt (except under `none`), a digest or derivation that does not verify (including when every fallback fails), and for a token transformed in any of these ways after dump: all letters uppercased; an extra character appended; the first character replaced; the separator removed; the last character chopped off; the payload section changed while the signature section is kept. None of those paths is a successful `loads` of the original object.

After a signature mismatch, the raised failure still carries the unsigned payload for inspection: some text or bytes on that object (a constructor argument or a public non-callable attribute), distinct from the full token, can be deserialized with the internal dump/load object to recover the original object. That is not a successful load of the token.

**Payload-decode failure.** The signature verifies, but the payload cannot be deserialized (for example the payload was shortened and then signed so the signature matches garbage, or a JSON helper is given a verified non-JSON payload). `loads` raises. `loads_unsafe` also raises; it does not return a pair. The failure retains the original decode error: an observer can tell two different decode errors apart from the failure object itself, a public field, or inspectable text on it.

A signature mismatch and a payload-decode failure are distinguishable from each other and from success.

## `signtoken.Signer`

Import `Signer` from the package root `signtoken` (`from `signtoken` import `Signer``). Callable class for the basic signing helper. It signs raw byte values (or text, which is encoded as `UTF-8`) and later verifies them. It does not serialize objects and does not record a timestamp.

`Serializer` instantiates this type (or a subclass passed as `signer`) with the helper’s secret, salt, and `signer_kwargs`. The same class is a valid fallback item: a pair `(`Signer`, {`digest_method`: …})` names this type plus signing options.

### Signature

```
`Signer`(secret_key, `salt`=..., `sep`=b".", `key_derivation`=None, `digest_method`=None, `algorithm`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Signing uses the **last** (newest) key. Recovery tries remaining keys from newest to oldest and succeeds if any remaining key verifies.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. When omitted, a product-defined default salt is used.
- `sep` — separator between the payload and the signature. Text or bytes. The default is a period (``.``). A period passed explicitly interchanges with the default.
- `key_derivation` — how the signing key is derived from the secret and the salt. Built-in names include `concat`, `django-concat`, `hmac`, and `none`. When omitted or `None`, the scheme is `django-concat`.
- `digest_method` — hash constructor used as the HMAC intermediate and in key derivation, such as `hashlib.sha1`, `hashlib.sha256`, or `hashlib.sha512`. When omitted or `None`, this type’s `default_digest_method` is used (SHA-1 on the base `Signer` type). A signer given `hashlib.sha1` explicitly produces the same token as one that leaves the digest at the default.
- `algorithm` — a signing-algorithm **instance**. When omitted or `None`, HMAC using the configured digest is used. Pass an `HMACAlgorithm` instance for HMAC, or a `NoneAlgorithm` instance for the no-op algorithm that emits an empty signature.

The class is callable. Construction returns a signer instance. Construction does not sign a value, does not write files, and does not exit the host process.

### Construction refused

Constructing a signer whose separator is a hyphen (``-``) is refused: the constructor raises and does not return a signer. The same refusal applies to an underscore (``_``), an equals sign (``=``), an ASCII letter, or an ASCII digit as the separator. ASCII letters, digits, hyphen, underscore, and equals are not allowed as separators because they can appear in the encoded signature. A period is accepted.

### `default_digest_method`

`default_digest_method` is a **class** attribute. A subclass assigns a hash constructor to that name in the class body — the same kind of object accepted as `digest_method`, such as `hashlib.sha1`, `hashlib.sha256`, or `hashlib.sha512`.

On the base `Signer` type the attribute is SHA-1: constructing `Signer` with no `digest_method` produces the same token as constructing it with `digest_method` set to `hashlib.sha1`.

Constructing a `Signer` (including a subclass) without `digest_method`, or with `digest_method` equal to `None`, uses that type’s `default_digest_method` as the instance digest.

A subclass whose class body sets ``default_digest_method` = hashlib.sha512`, constructed that way, signs with SHA-512. The token is not equal to a token for the same value from a default (SHA-1) signer, and not equal to a token from a signer whose `key_derivation` is `hmac`; those tokens do not interchange. A SHA-512 signature is longer than a SHA-1 signature.

A subclass whose class body sets ``default_digest_method` = hashlib.sha256`, constructed that way, signs with SHA-256.

If `digest_method` is passed and is not `None`, that constructor argument is the digest the instance uses. The class attribute is not consulted and does not override the pin.

### `sign`

```
`sign`(value)
```

- `value` — the payload, as text or bytes.

Encodes text as `UTF-8`. Returns a **bytes** token: the payload bytes, then the separator, then a signature. The token is not text.

A signer constructed with the same secret and `salt` as a `Serializer` produces tokens that helper will treat as a valid signature over that payload. Signing a shortened or otherwise non-deserializable payload this way yields a token whose signature verifies and whose payload will not deserialize.

Under HMAC (the default, or an `HMACAlgorithm` instance) the signature section is non-empty. Under `NoneAlgorithm` the signature section is empty bytes.

The call does not mutate the process environment and does not exit the host process.

### `unsign`

```
`unsign`(signed_value)
```

- `signed_value` — a token previously produced by `sign`, as bytes (or text).

On success, returns the original payload as a `bytes` object, never text. Recovering a token signed for `my string` yields `b"my string"`, not the text `my string`. Non-ASCII text recovers as its `UTF-8` bytes. Signing the same characters as text and as those `UTF-8` bytes recovers identically.

On failure, raises. Failure does not return the original value as a successful recovery. A validity check is a separate entry; this call either returns verified bytes or refuses.

When the token has a separator but the signature does not verify, and the payload section can still be read, the raised failure object carries the original payload as bytes: some bytes field on that object (a constructor argument or a public attribute) equals the original payload. Message text is not the carrier. After signing `b` and chopping the last byte of the token, recovery refuses and that failure still exposes payload `b` as bytes.

### `validate`

```
`validate`(signed_value)
```

- `signed_value` — a token, as bytes (or text).

Reports whether the token verifies, **without** handing back the payload. This call returns; it does not raise for a bad token.

- Success: a true value that is not the recovered payload bytes and is not the original text. For a token signed as `my string`, the report is not `b"my string"` and is not `my string`.
- Failure: a false value.

A true report and a successful `unsign` of the same token are distinct observations: the validity report is not the payload.

### Token layout

The token is `payload + separator + signature`. The default separator is a period (``.``). Recovery splits on the **last** occurrence of the separator, so a payload that contains the default period still round-trips.

Replacing the period in a signed token with `*` makes `unsign` refuse and `validate` report failure. Changing the payload of a valid token — for example replacing the bytes `my` with `other` in a token signed for `my string` — is likewise refused. Flipping a bit in the payload section or in a non-empty signature section is refused.

A value that does not contain the separator at all is refused as a signature failure: `unsign` raises and `validate` reports failure. A token that has a separator but a wrong signature also fails; neither path returns a verified value.

### Salt isolation and key derivation

Two signers that share a secret but use different `salt` values produce tokens the other will not verify, under the default derivation and under `hmac`. Under `key_derivation` `none` the salt is not mixed in.

A token produced under `hmac` is not equal to a token for the same value from a default-derivation signer, and the two do not verify each other’s tokens.

### Digest

A SHA-512 digest produces a longer signature than SHA-1. A SHA-1 signer does not recover a SHA-512 token. A SHA-1 signer does not recover a SHA-256 token. A signer given `hashlib.md5` still round-trips under that same signer and still refuses a changed payload.

### Algorithms

The default algorithm is HMAC using the configured digest. HMAC rejects a changed payload. Supplying a `NoneAlgorithm` instance selects the no-op algorithm: recovery of a just-signed value still yields that value as bytes, the signature section is empty, and a changed payload is **not** refused. HMAC tokens and no-op tokens do not interchange.

## `signtoken.Signer.default_digest_method`

Class attribute on `Signer` (imported from the package root `signtoken`). It is the digest the instance uses when the constructor keyword `digest_method` is omitted or `None`. It is not a second override channel beside `digest_method`.

### Shape

`default_digest_method` is a **class** attribute. A subclass assigns a hash constructor to that name in the class body — the same kind of object accepted as `digest_method`, such as `hashlib.sha1`, `hashlib.sha256`, or `hashlib.sha512`. Construction does not require a private wrapper around that constructor.

On the base `Signer` type the attribute is SHA-1: constructing `Signer` with no `digest_method` produces the same token as constructing it with `digest_method` set to `hashlib.sha1`.

### When construction omits `digest_method`

Constructing a `Signer` (including a subclass) without `digest_method`, or with `digest_method` equal to `None`, uses that type’s `default_digest_method` as the instance digest.

A subclass whose class body sets ``default_digest_method` = hashlib.sha512`, constructed that way, signs with SHA-512. Dump then load still round-trips under that type. The token is not equal to a token for the same value from a default (SHA-1) signer, and not equal to a token from a signer whose `key_derivation` is `hmac`; those tokens do not interchange. A SHA-512 signature is longer than a SHA-1 signature.

A subclass whose class body sets ``default_digest_method` = hashlib.sha256`, constructed that way, signs with SHA-256.

### When construction supplies `digest_method`

If `digest_method` is passed and is not `None`, that constructor argument is the digest the instance uses. The class attribute is not consulted and does not override the pin.

### Use as a serialize-and-sign signer type

A `Serializer` instantiates its `signer` class with the helper’s secret, salt, and `signer_kwargs`. The same rule applies: those keyword arguments are constructor arguments to the signer type.

- If `signer_kwargs` omits `digest_method`, the type’s `default_digest_method` is the digest. A helper whose `signer` is a SHA-512 class-default subclass, with no digest in `signer_kwargs`, therefore signs with SHA-512.
- If `signer_kwargs` pins `digest_method`, that pin is used. A fallback item that is only an alternative signer type is constructed with the helper’s **current** `signer_kwargs`. A type whose `default_digest_method` is SHA-256 loads a SHA-256 token when listed in `fallback_signers` and the helper does not pin a digest. The same type does **not** load that SHA-256 token when the helper pins SHA-1 in `signer_kwargs`: the class attribute does not override the pin.

## `signtoken.TimedSerializer`

Import `TimedSerializer` from the package root `signtoken` (`from `signtoken` import `TimedSerializer``). Callable class for the timestamped serialize-and-sign helper. It is constructed like `Serializer`: it serializes an object with an internal dump/load object (the language JSON library by default), then signs that payload with timestamped signing (`TimestampSigner` by default). The token therefore records the signing time. On load, the caller may supply a maximum age in seconds and may ask to receive that signing time.

This helper still round-trips objects, refuses tampered tokens as a signature mismatch, isolates a per-call salt, tries fallback signing configurations, inspects a failed or expired token as a pair, and dumps and loads through a file stream.

### Signature

```
`TimedSerializer`(secret_key, `salt`=..., `serializer`=None, `serializer_kwargs`=None, `signer`=None, `signer_kwargs`=None, `fallback_signers`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Dumping signs with the **last** (newest) key. Load tries remaining keys from newest to oldest and succeeds if any remaining key verifies.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. When omitted, a product-defined default salt is used.
- `serializer` — the internal dump/load object. An object that provides `dumps` and `loads`. When omitted or `None`, the language JSON library is used.
- `serializer_kwargs` — a mapping of extra dump options forwarded into the internal dump object’s `dumps`. When omitted or `None`, no extra dump options are forwarded.
- `signer` — a signer **class** instantiated when signing. When omitted or `None`, `TimestampSigner` is used.
- `signer_kwargs` — a mapping of keyword arguments forwarded when instantiating that signer class, such as `digest_method` and `key_derivation`. When omitted or `None`, the signer’s own defaults apply.
- `fallback_signers` — a list of fallback signing configurations tried when the current signer cannot verify a token. When omitted or `None`, there are no fallbacks.

The class is callable. Construction returns a helper instance. Construction does not dump an object, does not write files, and does not exit the host process.

### `dumps`

```
`dumps`(obj, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Serializes `obj` with the internal dump/load object, then signs that payload with a timestamp. Returns a token: the serialized payload, then the separator, then a non-empty time field, then the separator, then a signature. The default separator is a period (``.``). The time field uses the same wire spelling as `TimestampSigner`.

When the internal dump/load object’s `dumps` returns text, this call returns text (`str`), not bytes. When that `dumps` returns bytes, this call returns bytes.

The time field is recorded at the moment of dumping from the process clock’s Unix epoch (`time.time`). Dumping the mapping `{'id': 42}` with secret `secret-key` produces a token whose payload prefix is that mapping’s default JSON text, then a period, then a non-empty time field.

A JSON string whose text contains a period still round-trips. That token is still the entire JSON text, then the separator, then the time field, then the signature: an interior period inside the JSON is not treated as the payload/time boundary.

The call does not mutate the process environment and does not exit the host process.

### `loads`

```
`loads`(s, `max_age`=None, `return_timestamp`=False, `salt`=None)
```

- `s` — a token previously produced by `dumps`, as text or as bytes.
- `max_age` — optional maximum age in seconds. When omitted or `None`, age is not checked.
- `return_timestamp` — when true, a successful load also returns the signing time. When omitted or false, only the object is returned.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Reverse of `dumps`.

**Success without asking for the signing time.** Returns an object equal to the original. Dumping then loading the mapping `{'id': 42}` recovers that mapping, including `id` as the integer 42. Dumping then loading a list of integers recovers that list.

**Success when asking for the signing time.** Returns a pair of two items: first the original object, then a timezone-aware datetime whose UTC offset is zero and that equals the process-clock instant at which that token was dumped. The datetime is read from the token. A second helper constructed with the same secret recovers the same signing time from that token after the clock has moved on. Two tokens dumped by the same helper at different instants each carry their own signing time.

**Age check.** Age is the process clock’s Unix epoch at check time minus the recorded signing epoch, in seconds. When `max_age` is 10, loading one second after dumping succeeds and yields the original object. After eleven seconds have passed since dumping, the same call with `max_age` 10 refuses as **expired**. A token whose signing time is in the future relative to the clock at check time, when a maximum age is supplied, is also expired. Omitting `max_age` still loads after eleven seconds and still loads a future signing time.

On failure, raises. Failure does not return the original object as a successful load, and it does not return a success pair when `return_timestamp` is true.

### `dump` / `load`

```
`dump`(obj, f, `salt`=None)
`load`(f, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `f` — a file-like stream. `dump` writes the token that `dumps` would return (`f.write`). `load` reads the stream (`f.read`) and then loads. The stream must be compatible with the token kind: a text-mode stream (including a real text file) for a text token; a binary-mode stream for a bytes token.
- `salt` — optional per-call salt, as on `dumps` / `loads`.

Dumping an object into a stream and loading it back from that stream recovers an equal object. Dumping the mapping `{'id': 42}` into a text file and loading it back yields that mapping. These calls do not exit the host process.

### `loads_unsafe`

```
`loads_unsafe`(s, `max_age`=None, `salt`=None)
```

- `s` — a token, as text or bytes.
- `max_age` — optional maximum age in seconds, as on `loads`. When omitted or `None`, age is not checked.
- `salt` — optional per-call salt, as on `loads`.

Inspection entry for signature problems and expiry. Returns a **pair** of two items. It does not make a bad signature or an expired token look valid, and it does not abort the caller on those cases.

- Valid token (including a one-second-old token checked with `max_age` 10): first item is true (signature valid and not expired); second item is the original object.
- Expired token (eleven seconds old with `max_age` 10): first item is false; second item is the original object. The caller is not aborted: the pair is returned. Ordinary `loads` of that same token with the same `max_age` still refuses as expired.
- Token whose signature does not verify, but whose payload can still be deserialized (for example the last character chopped off): first item is false; second item is the original object. The caller is not aborted.

The first item is false whenever verification failed or the token is expired, even if a payload is still yielded for inspection.

### Token layout (default JSON)

The default internal dump/load object is the language JSON library. The token is the serialized payload, then the separator, then a non-empty time field, then the separator, then a signature. This helper inserts that time field between payload and signature; it does not emit payload-then-signature only.

Anyone who can see a default JSON token can read the JSON text in it. They still cannot forge a new payload that verifies without the secret.

### Per-call salt

A `dumps` that passes an explicit `salt` `other` produces a token that the same helper will not `loads` unless that same `salt` `other` is passed to `loads`. Loading with `salt` `other` recovers the object. Loading with the helper’s default salt refuses the token as a signature mismatch.

Under `key_derivation` `none` (passed through `signer_kwargs`) the salt is not mixed in, so that default-salt load still recovers the object.

### Tamper transforms

A token that was dumped and then transformed in any of these ways is refused as a signature mismatch on `loads`: all letters uppercased; an extra character appended; the first character replaced; the separator removed. None of those transformations yields a successful load of the original object.

### Fallback signing configurations

`fallback_signers` is a list. Fallbacks are tried when the current signer cannot verify a token. A mapping of signing options (for example `{`digest_method`: …}`) is one accepted item shape.

Concrete case: a helper that signs with SHA-256 dumps a mapping; a second helper whose current digest is SHA-1 but that lists SHA-256 as a fallback loads that token and recovers the mapping; a third helper whose current digest is SHA-1 and that has no fallback refuses the token as a signature mismatch.

**Expired current configuration is not rescued by a fallback.** When the current configuration verifies the signature but the token is older than the maximum age, `loads` refuses as expired. Further fallback configurations are not tried. Concrete case: a helper that currently signs with SHA-256 and lists SHA-1 as a fallback dumps a mapping whose `id` is 42; one second later, load with `max_age` 10 recovers that mapping; eleven seconds later, that same load is expired — not a signature mismatch and not a successful load via the fallback. The expiry still exposes a signing-time datetime. That expired refusal is distinguishable from a signature mismatch even when both still carry the original object’s payload and a signing-time datetime.

### Expiry

An expired load raises. That failure still carries the original payload for inspection: some text or bytes on that object (a constructor argument or a public non-callable attribute), distinct from the full token, can be deserialized with the internal dump/load object to recover the original object (for example a mapping whose `id` is 42). That is not a successful load of the token.

The same failure also exposes the signing time: a timezone-aware UTC datetime on that object (a constructor argument or a public non-callable attribute) equals the time of signing. A language `None` sentinel is not a datetime.

Expiry is distinguishable from a signature mismatch. A helper that returns the object after the maximum age has elapsed does not implement this helper.

## `signtoken.TimestampSigner`

Import `TimestampSigner` from the package root `signtoken` (`from `signtoken` import `TimestampSigner``). Callable class for the timestamped signing helper. It is constructed like `Signer` and signs raw byte values (or text, which is encoded as `UTF-8`). It also records the signing time in the token. On recovery, the caller may supply a maximum age in seconds and may ask to receive that signing time.

This helper still round-trips bytes, refuses a value with no separator, refuses a changed payload, refuses an illegal separator at construction, accepts the built-in key-derivation schemes, selects a digest, distinguishes HMAC from the no-op algorithm, and accepts a secret list oldest to newest.

### Signature

```
`TimestampSigner`(secret_key, `salt`=..., `sep`=b".", `key_derivation`=None, `digest_method`=None, `algorithm`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Signing uses the **last** (newest) key. Recovery tries remaining keys from newest to oldest and succeeds if any remaining key verifies.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. When omitted, a product-defined default salt is used.
- `sep` — separator between the payload, the time field, and the signature. Text or bytes. The default is a period (``.``). A period passed explicitly interchanges with the default.
- `key_derivation` — how the signing key is derived from the secret and the salt. Built-in names include `concat`, `django-concat`, `hmac`, and `none`. When omitted or `None`, the scheme is `django-concat`.
- `digest_method` — hash constructor used as the HMAC intermediate and in key derivation, such as `hashlib.sha1`, `hashlib.md5`, or `hashlib.sha512`. When omitted or `None`, SHA-1 is used. A signer given `hashlib.sha1` explicitly produces the same token as one that leaves the digest at the default.
- `algorithm` — a signing-algorithm **instance**. When omitted or `None`, HMAC using the configured digest is used. Pass an `HMACAlgorithm` instance for HMAC, or a `NoneAlgorithm` instance for the no-op algorithm.

The class is callable. Construction returns a signer instance. Construction does not sign a value, does not write files, and does not exit the host process.

### Construction refused

Constructing a signer whose separator is a hyphen (``-``) is refused: the constructor raises and does not return a signer. The same refusal applies to an underscore (``_``), an equals sign (``=``), an ASCII letter, or an ASCII digit as the separator. ASCII letters, digits, hyphen, underscore, and equals are not allowed as separators because they can appear in the encoded signature. A period is accepted.

### `sign`

```
`sign`(value)
```

- `value` — the payload, as text or bytes.

Encodes text as `UTF-8`. Returns a **bytes** token: the entire payload bytes, then the separator, then a non-empty time field, then the separator, then a signature. The token is not text.

The time field is recorded at the moment of signing from the process clock’s Unix epoch (`time.time`). Signing the text `value` with secret `secret-key` yields a token whose payload prefix is the bytes `value`, then a period, then a non-empty time field.

A payload that itself contains the default period still produces this three-part layout: the payload prefix is the **entire** original payload, then one separator, then the time field.

The call does not mutate the process environment and does not exit the host process.

### `unsign`

```
`unsign`(signed_value, `max_age`=None, `return_timestamp`=False)
```

- `signed_value` — a token previously produced by `sign`, as bytes (or text).
- `max_age` — optional maximum age in seconds. When omitted or `None`, age is not checked.
- `return_timestamp` — when true, a successful recovery also returns the signing time. When omitted or false, only the payload is returned.

**Success without asking for the signing time.** Returns the original payload as a `bytes` object, never text. Recovering a token signed for `value` yields `b"value"`, not the text `value`.

**Success when asking for the signing time.** Returns a pair of two items: first the original payload as bytes, then a timezone-aware datetime whose UTC offset is zero and that equals the process-clock instant at which that token was signed. The datetime is read from the token. A second signer constructed with the same secret recovers the same signing time from that token after the clock has moved on. Two tokens signed by the same helper at different instants each carry their own signing time; the later sign does not overwrite the earlier token.

**Age check.** Age is the process clock’s Unix epoch at check time minus the recorded signing epoch, in seconds. When `max_age` is 10, recovering one second after signing succeeds and yields the original bytes. After eleven seconds have passed since signing, the same call with `max_age` 10 refuses as **expired**. A token whose signing time is in the future relative to the clock at check time, when a maximum age is supplied, is also expired (a negative age is not treated as valid). Omitting `max_age` still recovers after eleven seconds and still recovers a future signing time.

On failure, raises. Failure does not return the original value as a successful recovery, and it does not return a success pair when `return_timestamp` is true.

### `validate`

```
`validate`(signed_value, `max_age`=None)
```

- `signed_value` — a token, as bytes (or text).
- `max_age` — optional maximum age in seconds, as on `unsign`. When omitted or `None`, age is not checked.

Reports whether the token verifies, **without** handing back the payload. This call returns; it does not raise for a bad token, an expired token, a missing timestamp, or a malformed timestamp.

- Success: a true value that is not the recovered payload bytes and is not the original text.
- Failure: a false value.

When `max_age` is 10, a validity check reports success one second after signing and reports failure eleven seconds after signing. Omitting `max_age` reports success on that same eleven-second-old token.

A true report and a successful `unsign` of the same token are distinct observations: the validity report is not the payload.

### Token layout

The token is `payload + separator + time field + separator + signature`. The payload prefix is the entire original payload (including any separator bytes it contains), then one separator. The time field between payload and signature is non-empty. Under HMAC the signature section after the time field is non-empty.

The time field is the integer Unix-epoch seconds of the signing instant. On the wire it is the URL-safe base64 encoding of those seconds as big-endian bytes, with equals-sign (``=``) padding stripped. Leading zero bytes of that integer are omitted; a zero epoch is a single zero byte. Recovery reads that spelling: replacing only the middle field with another encoding of the same family that still converts to a calendar date still exposes a signing-time datetime; replacing it with an encoding of the same family that is out of range and cannot become a calendar date is refused with the signing-time field absent, and that refusal is not expiry. Decimal text, a datetime string, or any other encoding of the same epoch is not this field.

A value that does not contain the separator at all is refused as a signature failure: `unsign` raises and `validate` reports failure.

### Expiry

An expired recovery raises. That failure still carries the original payload as bytes: some bytes field on the failure object (a constructor argument or a public attribute) equals the original payload. Message text is not the carrier. After signing `value` and waiting eleven seconds, recovery with `max_age` 10 refuses and that failure still exposes payload `b"value"` as bytes.

The same failure also exposes the signing time: a timezone-aware UTC datetime on that object (a constructor argument or a public non-callable attribute) equals the time of signing. A language `None` sentinel is not a datetime.

Expiry is distinguishable from a missing timestamp and from a malformed timestamp: those refusals have no signing-time datetime, while expiry does. The same legal token still recovers when `max_age` is omitted. A helper that returns the original bytes after the maximum age has elapsed does not implement this helper.

### Missing timestamp

A token produced by the **non-timestamped** `Signer` (payload and signature only, no time field) is refused as a **missing timestamp**. `unsign` raises. The signing-time datetime on that failure is absent: no datetime appears in the failure’s constructor arguments or public non-callable attributes. That outcome is distinguishable from expiry and from a time-signature failure that still exposes a signing time.

### Malformed timestamp

A token whose time field is not a well-formed timestamp is refused as a **malformed timestamp**. `unsign` raises. The signing-time datetime on that failure is absent.

This includes a non-timestamped signer signing a payload that happens to contain a period and a dummy time-looking suffix that does not decode to a time.

A malformed-timestamp refusal is distinguishable from expiry (expiry still exposes a signing-time datetime; the legal token still recovers when `max_age` is omitted) and from a missing timestamp. The malformed-timestamp refusal and the missing-timestamp refusal are distinguishable from each other even when both have no signing-time datetime.

### Replaced time field (no re-sign)

When a timestamped token’s time field is replaced without re-signing:

- An encoding of the time-field spelling above that cannot be converted to a calendar date is refused. The signing-time field is absent. That refusal is not expiry: an expired unreplaced token still exposes a signing-time datetime.
- The same replace-without-re-sign of an in-range encoding of that spelling still exposes a signing-time datetime (the signature is broken, but the field still converts to a calendar date).

### Changed payload (time-signature failure)

Changing the payload of a valid timestamped token — for example replacing the bytes `my` with `other` in a token signed for `my string` — is refused as a time-signature failure, not as a successful recovery. The unaltered token still recovers as `b"my string"`. When the time field can still be decoded, that failure exposes a timezone-aware UTC signing-time datetime equal to the time of signing. A second signer constructed with the same secret observes that same signing time on the changed token.

### Secret rotation, derivation, digest, and algorithms

A token produced with secret `a` is accepted by a signer whose secrets are `a` then `b`. After the list becomes only `b`, that same token is refused. A new token produced with secrets `a` then `b` is refused by a signer that only has `a`, and accepted by a signer that has `b`.

For each built-in name `concat`, `django-concat`, `hmac`, and `none`, a signer constructed with that scheme round-trips: recovering a token just signed yields the original value as bytes. A token produced under `hmac` is refused by a `django-concat` signer that did not produce it.

A signer given `hashlib.md5` still round-trips under that same signer. A SHA-1 signer does not recover a SHA-512 token.

The default algorithm is HMAC using the configured digest. Supplying a `NoneAlgorithm` instance selects the no-op algorithm: recovery of a just-signed value still yields that value as bytes. HMAC tokens and no-op tokens do not interchange.

## `signtoken.URLSafeSerializer`

Import `URLSafeSerializer` from the package root `signtoken` (`from `signtoken` import `URLSafeSerializer``). Callable class for the URL-safe serialize-and-sign helper. It serializes an object with an internal dump/load object (compact JSON by default), encodes that payload into a restricted alphabet, then signs it with a `Signer`. It does not record a timestamp.

This helper still satisfies the serialize-and-sign obligations of `Serializer`: object round-trip, refusal of tampered tokens as a signature mismatch, per-call salt isolation, fallback signing configurations, unsafe load as a pair, dump/load through a file stream, and an attachable custom dump/load object. The obligations below are the text token, the alphabet, compactness, and compression.

### Signature

```
`URLSafeSerializer`(secret_key, `salt`=..., `serializer`=None, `serializer_kwargs`=None, `signer`=None, `signer_kwargs`=None, `fallback_signers`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Dumping signs with the **last** (newest) key. Load tries remaining keys from newest to oldest and succeeds if any remaining key verifies. The README construction uses the secret `secret key`.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. Accepted as the second positional argument or as a keyword. When omitted, a product-defined default salt is used. The README construction uses salt `auth`.
- `serializer` — the internal dump/load object. An object that provides `dumps` and `loads`. When omitted or `None`, compact JSON is used (language JSON with no extra whitespace between tokens).
- `serializer_kwargs` — a mapping of extra dump options forwarded into the internal dump object’s `dumps`. When omitted or `None`, no extra dump options are forwarded.
- `signer` — a signer **class** (the `Signer` type, or a subclass) instantiated when signing. When omitted or `None`, `Signer` is used.
- `signer_kwargs` — a mapping of keyword arguments forwarded when instantiating that signer class, such as `key_derivation` and `digest_method`. When omitted or `None`, the signer’s own defaults apply.
- `fallback_signers` — a list of fallback signing configurations tried when the current signer cannot verify a token. When omitted or `None`, there are no fallbacks.

The class is callable. Construction returns a helper instance. Construction does not dump an object, does not write files, and does not exit the host process.

Constructing with secret `secret key` and salt `auth`, then dumping the mapping whose `id` is 5 and whose `name` is `signtoken`, then loading that token recovers that mapping, including the name `signtoken`.

### `dumps`

```
`dumps`(obj, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Serializes `obj` with the internal dump/load object, encodes that payload into the URL-safe alphabet (compressing when that shortens it; see below), then signs. Returns a **text** token (`str`), not bytes.

The token is the encoded payload, then the separator, then a signature. The default separator is a period (`.`).

The call does not mutate the process environment and does not exit the host process.

### `loads`

```
`loads`(s, `salt`=None)
```

- `s` — a token previously produced by `dumps`, as text or as bytes.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Reverse of `dumps`. On success, returns an object equal to the original. Dumping then loading the README mapping recovers that mapping (`id` equals 5, `name` equals `signtoken`). Dumping then loading a mapping whose `id` is 42 recovers that mapping. Dumping then loading the list of integers 1 through 4 recovers a list of those integers. A second helper constructed with the same secret and salt loads the first helper’s tokens and recovers the same objects.

On failure, raises. Failure does not return the original object as a successful load. A signature mismatch and a payload-decode failure are distinguishable from each other and from success (see below).

### `dump` / `load`

```
`dump`(obj, f, `salt`=None)
`load`(f, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `f` — a file-like stream. `dump` writes the token that `dumps` would return (`f.write`). `load` reads the stream (`f.read`) and then loads. The stream must be compatible with the token kind: a text-mode stream (including a real text file) for this helper’s text token.
- `salt` — optional per-call salt, as on `dumps` / `loads`.

Dumping an object into a stream and loading it back from that stream recovers an equal object. Dumping the mapping whose `id` is 42 into a text file and loading it back yields that mapping. These calls do not exit the host process.

### `loads_unsafe`

```
`loads_unsafe`(s, `salt`=None)
```

- `s` — a token, as text or bytes.
- `salt` — optional per-call salt, as on `loads`.

Inspection entry for signature problems. Returns a **pair** of two items. It does not make a bad signature look valid.

- Valid token: first item is true (signature valid); second item is the original object.
- Token whose signature does not verify, but whose payload can still be deserialized: first item is false; second item is the original object. The caller is not aborted: the pair is returned.

The first item is false whenever verification failed, even if a payload is still yielded for inspection.

When the signature **is** valid but the payload cannot be deserialized, this call does **not** convert that case into a pair: the caller observes the same payload-decode failure as `loads` (the call raises).

### Token alphabet and compact JSON

Every character of a token this helper emits is one of: uppercase letters, lowercase letters, digits, underscore (`_`), hyphen (`-`), or period (`.`). Product-emitted tokens never contain a plus sign (`+`), a slash (`/`), an equals sign (`=`), a space, a square bracket, or a quote.

The default internal dump/load object serializes JSON **without extra whitespace** between tokens so tokens stay short. Dump then load still recovers the object.

For the list of integers 1 through 4, a non-URL-safe `Serializer` token includes that list’s JSON text `[1, 2, 3, 4]` (brackets and spaces after commas). This helper’s token for that same list does **not** contain brackets or spaces, and loading it still yields the list of integers 1 through 4.

Anyone who can see a default JSON token can recover the JSON text after decoding the payload section. They still cannot forge a new payload that verifies without the secret.

### Compression

When compression shortens the payload, the helper emits a compressed token; when it would not shorten, the helper leaves the payload uncompressed. Both forms load.

A compressed token is distinguishable from an uncompressed one: the payload section of a compressed token begins with a period (`.`); the payload section of an uncompressed token does not.

Concrete cases:

- Dumping the string of the letter `a` repeated one thousand times produces a token that loads back to that same string, that uses only the URL-safe alphabet above, that is **shorter than one thousand characters**, and whose payload section begins with a period.
- A small mapping such as one whose `id` is 42, the README mapping, and the list of integers 1 through 4 also round-trip, and their payload sections do **not** begin with a period (uncompressed path).

A second helper constructed with the same secret and salt loads both a compressed token and an uncompressed token produced by the first helper.

### Per-call salt

A `dumps` that passes an explicit `salt` `other` produces a token that the same helper will not `loads` unless that same `salt` `other` is passed to `loads`. Loading with `salt` `other` recovers the object. Loading with the helper’s default salt refuses the token as a signature mismatch.

Under `key_derivation` `none` (passed through `signer_kwargs`) the salt is not mixed in, so that default-salt load still recovers the object.

### Custom dump/load object

The caller may replace the internal dump/load object by passing `serializer`. That object must provide `dumps` (object in, text or bytes out) and `loads` (text or bytes in, object out). A helper configured that way round-trips values that object can represent. The dumped token is still URL-safe text and carries that object’s format rather than default JSON.

A helper that still uses JSON cannot load a token produced by a helper whose dump format is not JSON when both share secret and salt: if the signature still verifies, that refusal is a payload-decode failure, not a signature mismatch.

### Fallback signing configurations

`fallback_signers` is a list. Fallbacks are tried when the current signer cannot verify a token. A mapping of signing options (for example `{`digest_method`: …}`) is one accepted item shape.

Concrete case: a helper that signs with SHA-256 dumps a mapping; a second helper whose current digest is SHA-1 but that lists SHA-256 as a fallback loads that token and recovers the mapping; a third helper whose current digest is SHA-1 and that has no fallback refuses the token as a signature mismatch.

### Signature mismatch versus payload-decode failure

**Signature mismatch.** `loads` raises. `loads_unsafe` returns a pair whose first item is false. This is the outcome for a wrong salt (except under `none`), a digest that does not verify (including when every fallback fails), and for a token transformed in any of these ways after dump: all letters uppercased; letters in the signature section uppercased while the payload section is held fixed; an extra character appended; the first character replaced; the separator removed; the last character chopped off. None of those paths is a successful `loads` of the original object. The same refusals apply to a compressed token (the thousand-letter-`a` string) for uppercasing, appending a character, replacing the first character, and chopping the last character.

**Payload-decode failure.** The signature verifies, but the payload cannot be deserialized. `loads` raises. `loads_unsafe` also raises; it does not return a pair. This is the outcome when the payload is not valid URL-safe encoding, and when the payload claims compression (payload section begins with a period) but is not valid compressed data.

A signature mismatch and a payload-decode failure are distinguishable from each other and from success.

## `signtoken.URLSafeTimedSerializer`

Import `URLSafeTimedSerializer` from the package root `signtoken` (`from `signtoken` import `URLSafeTimedSerializer``). Callable class for the URL-safe timestamped serialize-and-sign helper. It is constructed like `URLSafeSerializer`: it serializes an object with an internal dump/load object (compact JSON by default), encodes that payload into a restricted alphabet (compressing when that shortens it), then signs with timestamped signing (`TimestampSigner` by default). The token therefore records the signing time. On load, the caller may supply a maximum age in seconds and may ask to receive that signing time.

This helper still dumps and loads the same objects as `URLSafeSerializer`, still as URL-safe text, and still compresses when that shortens the payload. It also applies the timestamped serialize-and-sign age check: a maximum age in seconds, a returned signing-time datetime, expiry that is distinguishable from a missing or malformed timestamp, and refusal of a non-timestamped URL-safe token.

### Signature

```
`URLSafeTimedSerializer`(secret_key, `salt`=..., `serializer`=None, `serializer_kwargs`=None, `signer`=None, `signer_kwargs`=None, `fallback_signers`=None)
```

- `secret_key` — required first positional argument. One secret (text or bytes) or a sequence of secrets **oldest to newest**. Dumping signs with the **last** (newest) key. Load tries remaining keys from newest to oldest and succeeds if any remaining key verifies. The README-style construction uses the secret `secret key`.
- `salt` — extra material mixed with the secret to isolate signing contexts. Text or bytes. Accepted as the second positional argument or as a keyword. When omitted, a product-defined default salt is used. The README-style construction uses salt `auth`.
- `serializer` — the internal dump/load object. An object that provides `dumps` and `loads`. When omitted or `None`, compact JSON is used (language JSON with no extra whitespace between tokens).
- `serializer_kwargs` — a mapping of extra dump options forwarded into the internal dump object’s `dumps`. When omitted or `None`, no extra dump options are forwarded.
- `signer` — a signer **class** instantiated when signing. When omitted or `None`, `TimestampSigner` is used.
- `signer_kwargs` — a mapping of keyword arguments forwarded when instantiating that signer class, such as `digest_method`. When omitted or `None`, the signer’s own defaults apply.
- `fallback_signers` — a list of fallback signing configurations tried when the current signer cannot verify a token. When omitted or `None`, there are no fallbacks.

The class is callable. Construction returns a helper instance. Construction does not dump an object, does not write files, and does not exit the host process.

Constructing with secret `secret key` and salt `auth`, then dumping the mapping whose `id` is 42, then loading that token recovers that mapping.

### `dumps`

```
`dumps`(obj, `salt`=None)
```

- `obj` — the object to serialize and sign.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Serializes `obj` with the internal dump/load object, encodes that payload into the URL-safe alphabet (compressing when that shortens it), then signs that payload with a timestamp. Returns a **text** token (`str`), not bytes.

The token is the encoded payload, then the separator, then a non-empty time field, then the separator, then a signature. The default separator is a period (`.`).

The time field is recorded at the moment of dumping from the process clock’s Unix epoch. A second helper constructed with the same secret and salt loads the first helper’s token and recovers the same object and the same signing time.

The call does not mutate the process environment and does not exit the host process.

### `loads`

```
`loads`(s, `max_age`=None, `return_timestamp`=False, `salt`=None)
```

- `s` — a token previously produced by `dumps`, as text or as bytes.
- `max_age` — optional maximum age in seconds. When omitted or `None`, age is not checked.
- `return_timestamp` — when true, a successful load also returns the signing time. When omitted or false, only the object is returned.
- `salt` — optional per-call salt. When omitted or `None`, the helper’s construction salt is used.

Reverse of `dumps`.

**Success without asking for the signing time.** Returns an object equal to the original. Dumping then loading the README mapping, the list of integers 1 through 4, a mapping whose `id` is 42, or the string of the letter `a` repeated one thousand times recovers that same object. The token is URL-safe text.

**Success when asking for the signing time.** Returns a pair of two items: first the original object, then a timezone-aware datetime whose UTC offset is zero and that equals the process-clock instant at which that token was dumped. The datetime is read from the token. A second helper constructed with the same secret and salt recovers the same signing time from that token after the clock has moved on. Two tokens dumped by the same helper at different instants each carry their own signing time. Asking for the signing time also works on a compressed token (the thousand-letter-`a` string).

**Age check.** Age is the process clock’s Unix epoch at check time minus the recorded signing epoch, in seconds. When `max_age` is 10, loading one second after dumping succeeds and yields the original object. After eleven seconds have passed since dumping, the same call with `max_age` 10 refuses as **expired**. Omitting `max_age` still loads after eleven seconds. The same one-second success and eleven-second expiry hold for the thousand-letter-`a` string (still compressed). Asking for the signing time together with `max_age` 10 succeeds at one second (pair of object and signing-time datetime) and is expired at eleven seconds.

On failure, raises. Failure does not return the original object as a successful load, and it does not return a success pair when `return_timestamp` is true.

### Token alphabet and compression

Every character of a token this helper emits is one of: uppercase letters, lowercase letters, digits, underscore (`_`), hyphen (`-`), or period (`.`). Product-emitted tokens never contain a plus sign (`+`), a slash (`/`), an equals sign (`=`), a space, a square bracket, or a quote.

When compression shortens the payload, the helper emits a compressed token; when it would not shorten, the helper leaves the payload uncompressed. Both forms load.

A compressed token is distinguishable from an uncompressed one: the payload section of a compressed token begins with a period (`.`); the payload section of an uncompressed token does not.

Concrete cases:

- Dumping the string of the letter `a` repeated one thousand times produces a token that loads back to that same string, that uses only the URL-safe alphabet above, that is **shorter than one thousand characters**, and whose payload section begins with a period.
- A small mapping whose `id` is 42 also round-trips, and its payload section does **not** begin with a period (uncompressed path).

### Expiry

An expired load raises. That failure exposes the signing time: a timezone-aware UTC datetime on that object (a constructor argument or a public non-callable attribute) equals the time of signing. A language `None` sentinel is not a datetime.

Expiry is distinguishable from a signature mismatch and from a missing or malformed timestamp. A helper that returns the object after the maximum age has elapsed does not implement this helper.

A second helper constructed with the same secret and salt expires the first helper’s token under the same `max_age` 10 after eleven seconds, and still loads that token when `max_age` is omitted.

### Missing or malformed timestamp

A token produced by the **non-timestamped** `URLSafeSerializer` (no time field) is refused by this helper. That failure is not a successful load. The signing-time datetime on that failure is **absent** (no datetime on the failure object).

- An uncompressed token from that non-timestamped helper (for example a mapping whose `id` is 42; payload section does not begin with a period) is refused as a **missing timestamp**.
- A compressed token from that same non-timestamped helper (the thousand-letter-`a` string; payload section begins with a period) is refused as a **malformed timestamp**, not as a missing timestamp.

Both refusals have the signing-time datetime absent. The two failure kinds remain distinguishable from each other. Neither refusal is expiry: an expired load of a legal timestamped token still exposes a signing-time datetime.

A token that is expired under `max_age` 10 is not treated as missing or malformed: that same token still loads when `max_age` is omitted.

