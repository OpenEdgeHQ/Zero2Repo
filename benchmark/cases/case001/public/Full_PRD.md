# Hrefparse — Full Product Requirements Document

## Product overview

**Hrefparse** is a C++ library that parses, validates, normalizes, and mutates URLs according to the WHATWG URL Standard. It also implements URLPattern matching (compatible with the web-platform URLPattern tests) and URL Search Params query-string handling from the same family of web platform APIs. Internationalized domain names follow Unicode Technical Standard #46 (ToASCII / ToUnicode), including Punycode for non-ASCII labels.

A common use is to take a URL string and produce its WHATWG-normalized href. That is a different contract from RFC 3986 parsers (for example curl): Hrefparse rewrites hosts and paths. The README’s canonical illustration is graded below: the input `https://www.7‑Eleven.com/Home/Privacy/Montréal` (Unicode hyphen in the host, accented path segment) must normalize to `https://www.xn--7eleven-506c.com/Home/Privacy/Montr%C3%A9al`. Leaving the string unchanged, or applying only RFC 3986 encoding, is a failure of the product.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, header paths, and other Interface Contract details are out of scope here. Every feature point below corresponds to behavior that exists in the finished Hrefparse library. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **href** | The full serialized URL after WHATWG parsing or mutation (the URL Standard’s href). |
| **Base URL** | An already-parsed absolute URL used to resolve a relative input. |
| **Special scheme** | One of the WHATWG special schemes: `ftp`, `file`, `http`, `https`, `ws`, `wss`. These schemes have dedicated parsing rules and (except `file`) a default port. |
| **Non-special scheme** | Any other scheme (for example `git`, `mailto`, `data`, `non-spec`). |
| **Opaque path** | A non-hierarchical path, as in `mailto:` or `data:` URLs. Host mutation is refused; path shortening with `..` does not apply the same way as for hierarchical paths. |
| **Host** | Hostname plus port when a non-default port is present (WHATWG host). |
| **Hostname** | The host without a port (WHATWG hostname). Domain names, IPv4 addresses, and IPv6 addresses are the three host kinds. |
| **Origin** | The WHATWG serialized origin (scheme, host, and port for tuple origins; the Standard’s opaque-origin serialization for opaque URLs). Credentials, path, query, and fragment are not part of the origin. |
| **IDNA** | Internationalized Domain Names in Applications: ToASCII / ToUnicode per UTS #46, with Punycode (`xn--`) labels in ASCII hosts. |
| **URL Search Params** | The WHATWG query-string list of key/value pairs (the search parameters API), independent of a full URL object. |
| **URLPattern** | The WHATWG URLPattern matcher: patterns over URL components, with named groups, wildcards, and optional custom regular expressions. |
| **Length cap** | A process-wide maximum byte length for a URL’s serialized href (and for related search-parameter input). Default is the maximum 32-bit unsigned integer (about four gigabytes). The caller may lower it. |
| **Core capability** | A user-observable capability that reflects Hrefparse’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

Hrefparse is a **library**. Integrators reach it by compiling and linking the Hrefparse C++ library (including the documented single-header amalgamation) or by using the matching **C interface**. A command-line convenience named `hrefparsec` can validate, normalize, and print href or a chosen component from one URL or from a file/pipe of URLs; it is the same parse-and-inspect behavior, not a separate product.

The library’s public, independently verifiable surfaces are:

- Parse a URL string (ASCII or valid UTF-8), optionally against a base URL; report success or failure; serialize the href.
- Answer whether a string (optionally with a base) would parse successfully, in agreement with an actual parse of the same input, including length-cap rejections.
- Convert a filesystem path to a `file:` URL.
- Convert a domain with ToASCII and ToUnicode (IDNA), including as a standalone conversion on the C interface.
- Read and write WHATWG URL components on a successfully parsed URL: href, origin, protocol, username, password, host, hostname, port, pathname, search, hash; query presence of credentials, hostname, port, search, and hash; distinguish host kind (domain, IPv4, IPv6).
- Configure and read the length cap; rejected parse and rejected mutation never leave a longer href.
- Parse, mutate, sort, iterate, and serialize URL Search Params.
- Compile and match URLPattern patterns (C++ library; the caller supplies a regular-expression engine).

Feature points below group these entries by capability. They do not invent additional products.

## Non-functional constraints

- **Form factor:** An embeddable C++20 library with a C interface. No runtime third-party dependency. A recent C++ compiler is required (GCC 12 or newer, LLVM 14 or newer, or Microsoft Visual Studio 2022). CMake 3.16 or newer builds the library from this repository.
- **Platforms:** Windows, Linux, and macOS are first-class. This case’s acceptance targets Linux x86_64 with a C++20 toolchain and CMake.
- **Hardware:** CPU-only. No GPU or accelerator is required or claimed. The mandatory execution substrate is a real host that can compile Hrefparse from source and run a parse against the locally built library.
- **Input encoding:** Public string inputs are ASCII or valid UTF-8. The caller is responsible for UTF-8 validity.
- **Default length cap:** The maximum 32-bit unsigned integer until the caller lowers it. The cap applies to both the raw input and the **normalized** href (percent-encoding expansion counts). The same cap applies to filesystem-path conversion and to URL Search Params construction and reset. Individual search-parameter append/set calls are not length-capped.
- **URLPattern regular expressions:** Hrefparse does not ship a regular-expression engine. The caller supplies an engine that can compile a pattern (with or without case folding), search (yielding capture groups), and match (yes or no). That is a security boundary: the C++ standard library’s regular expressions are not treated as a safe default for untrusted patterns.
- **Two in-memory layouts (narrative only, not graded as distinct products):** Callers may request a compact form backed by one serialized string, or a form that stores components as separate strings. Both must expose the same parse, inspect, and mutate outcomes described here. Choosing a layout is not a separate feature point.

## Capability discrimination (global)

Every feature point below is a **core capability**. The mandatory substrate is a real CPU host with Hrefparse compiled from this repository’s sources and linked into the test process. None of these capabilities is an accelerator-backed GPU feature.

For every feature point:

- **Present:** The linked Hrefparse library produces the WHATWG (and, for URLPattern, URLPattern-standard) outcomes described below.
- **Absent / hollow:** Parse always succeeds or always fails; href is a copy of the input; IDNA hosts are not Punycode-encoded; setters ignore WHATWG validation; search parameters do not percent-encode; URLPattern always matches or never captures groups.

Cheaper proxies (hard-coded href tables, RFC 3986-only parsers, in-memory URL objects that do not implement WHATWG setters, or a URLPattern that only does literal string equality) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces WHATWG parsing with a looser parser for a core capability.

**Negative control (library substrate):** When the Hrefparse library is deliberately not linked, or the built artifact is removed from the link/search path in an isolated subprocess, a parse of an absolute `https` URL must fail to produce a successful Hrefparse URL — a hard assertion, not a skip.

## Non-goals

- Being an RFC 3986 parser, or matching curl’s “leave the string unchanged” behavior.
- Shipping a regular-expression engine for URLPattern.
- Guaranteeing a particular nanosecond-per-URL benchmark number (speed is a design goal, not a graded oracle).
- Language bindings maintained outside this repository (Rust, Go, Python, and others).
- Treating build options, amalgamation scripts, release automation, fuzzers, or benchmarks as user-facing product capabilities.

---

## Feature points

### FP-01: Parse, validate, and serialize URLs

**Public entry:** The Hrefparse C++ library parse entry and the matching C interface parse entry, each taking an ASCII or UTF-8 URL string and optionally a base URL; the dedicated “can this parse” entry (string, optionally with a base string); filesystem-path conversion to a `file:` URL; standalone IDNA ToASCII and ToUnicode on the C interface; the process-wide length cap configuration.

**Normal behavior:**

- Parsing a well-formed absolute URL succeeds and yields a URL whose href is the WHATWG-normalized serialization, which may differ from the input. Leading and trailing C0 controls and spaces are stripped. ASCII tab, line feed, and carriage return are then removed wherever they remain; they are not percent-encoded. A leading and trailing space around `https://www.google.com` still parses with href `https://www.google.com/`. Parsing `http://ab?a` immediately followed by an ASCII tab then `b` succeeds with href `http://ab/?ab`. The same position with a space instead of a tab percent-encodes: `http://ab?x y` succeeds with href `http://ab/?x%20y`.
- The README illustration is required: parsing `https://www.7‑Eleven.com/Home/Privacy/Montréal` succeeds, and the href is `https://www.xn--7eleven-506c.com/Home/Privacy/Montr%C3%A9al` (IDNA ToASCII on the host, percent-encoding of the path). A parser that returns the input unchanged fails this obligation.
- Special schemes are exactly `ftp`, `file`, `http`, `https`, `ws`, and `wss`. Default ports used in parsing and serialization are: `http` and `ws` → 80; `https` and `wss` → 443; `ftp` → 21; `file` has none. A default port is omitted from the href (for example `https://example.com:443/` serializes without `:443`).
- Relative inputs resolve against a successful base. Parsing `/hello` with no base fails. Parsing `/hello` against base `https://www.google.com` succeeds with href `https://www.google.com/hello`. Parsing `../other/page` against `https://example.com/dir/` succeeds with href `https://example.com/other/page`.
- Host parsing follows the WHATWG host parser, not dotted-decimal-only IPv4. Parsing `http://0300.168.0xF0` succeeds with hostname `192.168.0.240` and href `http://192.168.0.240/`. IPv6 hosts appear in brackets in the href (for example `http://[::1]/`).
- Path spaces are percent-encoded as `%20` in the href. Parsing `http://www.google.com/%37/ /` succeeds with href `http://www.google.com/%37/%20/`. A plus in a path is not treated as a space: `http://www.google.com/%37+/` keeps `%37+` in the path.
- Scheme and host matching for special-scheme URLs is ASCII-case-insensitive: parsing `http://GOOgoo.com` against base `http://other.com/` succeeds with hostname `googoo.com`.
- A `file:` path whose first segment is a normalized Windows drive letter (exactly one ASCII letter followed by `:`) is protected from `..` shortening: `file:c:/..` serializes as `file:///c:/`. A longer first segment that merely starts with letter-colon is not protected: `file:c:x/..` serializes as `file:///`.
- Filesystem-path conversion produces a `file:` href that matches the href obtained by starting from `file://` and assigning that path as the pathname, for paths such as `/home/user/txt.txt`, an empty path, and a Windows-style path with backslashes.
- The “can this parse” entry returns yes if and only if parse of the same input (and base, when given) would succeed — including when the length cap rejects a normalized href that is longer than the input. It does not require the caller to keep the URL object.
- Standalone ToASCII on a domain with non-ASCII labels yields a Punycode ASCII domain; standalone ToUnicode reverses Punycode labels. Host parsing of an http(s) URL uses the same ToASCII mapping, including Unicode Normalization Form C reordering when the host is not already NFC (for example `http://%C3%A1%CC%A3/` has hostname `xn--lsa752l`).
- When the length cap is set to 1024 bytes, parsing `https://example.com/` plus 1024 ASCII `a` characters in the path fails. Parsing `https://example.com/ok` succeeds. An input whose raw size is under the cap but whose normalized href (after `%20` expansion of spaces in the path) would exceed the cap also fails, and “can this parse” agrees.

**Boundary / error behavior:**

- The empty string, a fragment-only input such as `#x` with no base, and a host containing a literal space such as `http://www.google com/` fail to parse.
- A relative path such as `/hello-world` fails without a base and succeeds with base `https://www.google.com`.
- A percent-encoded host that is not a valid host, such as `http://www.google%X%.com/`, fails. A percent-encoded path that is not a valid percent-sequence, such as `http://www.google.com/%X%`, still parses; the href keeps `%X%`.
- When the length cap would be exceeded, parse fails, filesystem-path conversion yields an empty string, and the URL is not produced. Raising the cap back to the default restores acceptance of ordinary-length URLs.
- Standalone ToASCII of `www.google.com` succeeds. Standalone ToASCII of the ASCII domain `www.google com` (embedded space) also succeeds and yields that lowercased ASCII domain; a space is a host-parse failure (`http://www.google com/`), not a standalone ToASCII failure. Standalone ToASCII of a 20000-byte ASCII domain (twenty thousand letter `a` characters) fails and yields no usable ASCII domain; a short internationalized label still converts to Punycode.
- A failed parse does not yield a usable URL. The caller can tell success from failure before reading href or any component.

**Verifiable oracle:**

- Success: `https://www.google.com` parses and the href is `https://www.google.com/`; the 7‑Eleven / Montréal input parses to `https://www.xn--7eleven-506c.com/Home/Privacy/Montr%C3%A9al`; `/hello` fails alone and succeeds against `https://www.google.com`; `http://0300.168.0xF0` normalizes to `http://192.168.0.240/`; `file:c:/..` keeps `file:///c:/` while `file:c:x/..` becomes `file:///`; a tab inside a query is removed while a space in that position becomes `%20`; “can this parse” matches parse success and failure on those inputs and on a length-cap rejection whose normalized href overruns a 1024-byte cap; ToASCII of an internationalized label is Punycode, and that same mapping appears in the hostname of a parsed http URL; ToASCII of twenty thousand `a` characters fails; ToASCII of `www.google com` succeeds as ASCII while parse of `http://www.google com/` fails.
- Failure / absence: parse always copies the input to href; the 7‑Eleven host is not Punycode; relative URLs never resolve; IPv4 mixed-base hosts are left uncanonicalized; tabs in the query are percent-encoded rather than removed; “can this parse” disagrees with parse; length-cap overruns still succeed; there is no failure outcome for empty, space-in-host, or oversized-domain input; standalone ToASCII of `www.google com` is rejected as if it were a host parse.

---

### FP-02: Inspect and mutate URL components

**Public entry:** Component readers and writers on a successfully parsed Hrefparse URL, through the C++ library and the C interface: href, origin, protocol, username, password, host, hostname, port, pathname, search, hash; presence queries for credentials, hostname (including empty hostname), port, search, and hash; host-kind distinction; clearing port, search, and hash; replacing the entire href. The length cap from FP-01 also governs these mutations. This feature point depends on a successful parse (FP-01).

**Normal behavior:**

- After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the components are: href the full serialization; origin `https://www.google.com:8080`; protocol `https:` (scheme plus colon); username `username`; password `password`; port `8080`; hash `#hash-exists`; host `www.google.com:8080`; hostname `www.google.com`; pathname `/pathname`; search `?query=true`. Host kind is domain.
- After parsing `https://www.google.com` (no path in the input), pathname is `/` and href ends with `/`.
- Setting username `username` and password `password` on `https://www.google.com` yields href `https://username:password@www.google.com/`.
- Setting protocol `wss` on `https://www.google.com` succeeds; protocol becomes `wss:` and href becomes `wss://www.google.com/`. Setting protocol `http` on that result succeeds (special scheme to special scheme).
- Setting host `github.com`, port `8080`, pathname `/my-super-long-path`, search `target=self`, and hash `is-this-the-real-life` on a parsed `https://www.google.com` makes those readers return `github.com`, `8080`, `/my-super-long-path`, `?target=self`, and `#is-this-the-real-life` respectively. Search and hash writers accept values with or without a leading `?` or `#`; the readers always include the delimiter when the component is present, and return the empty string when it is absent.
- Setting host `changed-host:9090` updates both hostname and port together. Setting hostname does not consume a port. Host includes the port when a non-default port is present; hostname never does.
- Clearing port, search, or hash removes that component: port reader returns empty and “has port” is false; search and hash readers return empty.
- Replacing href with `https://www.google.com` succeeds and rebuilds all components from that parse. Replacing href with `http://0300.168.0xF0` yields href `http://192.168.0.240/` (same IPv4 canonicalization as FP-01).
- Origin for a special-scheme URL other than `file:` is scheme plus host plus non-default port, without credentials or path. Origin for an opaque URL such as a `mailto:` or `data:` URL is the WHATWG opaque-origin serialization (exact token belongs in the Interface Contract), distinguishable from a tuple origin that contains `https` and a hostname. A `file:` origin is that same opaque-origin serialization, not a `file://` tuple.
- After parsing `http://127.0.0.1/`, host kind is IPv4. After parsing `http://[::1]/`, host kind is IPv6. After parsing `https://example.com/`, host kind is domain. Those three kinds are mutually distinguishable.
- Setting an empty host on a non-special hierarchical URL that has no authority, such as `non-special:/x`, succeeds and the href becomes `non-special:///x` (empty authority inserted). The same holds when setting hostname to empty on `sc:/x` → `sc:///x`.
- Changing protocol from non-special `git` to non-special `svn` on `git://example.com/` succeeds. Changing protocol from `a://h:0` to `b` keeps port `0` in the href (`b://h:0`), because a non-special scheme has no default port that would drop it.
- “Has credentials” is true when username or password is non-empty. “Has hostname” is true when a host is present (including an empty host). “Has port”, “has search”, and “has hash” track those components independently of the others.

**Boundary / error behavior:**

- A mutation that the WHATWG URL Standard rejects leaves the URL unchanged (same href, same components). The caller can tell a refused host/hostname/protocol/pathname/username/password/port/href write from a successful one.
- `mailto:a@b.com` refuses host and hostname writes (opaque path / cannot-have-a-host). `file:` with an empty host refuses a protocol change to `https` or to a non-special scheme; after a host such as `google.com` is set, changing protocol to `https` succeeds (`https://google.com/`). Changing protocol from `https://example.com/` to a non-special scheme such as `foo` is refused; protocol stays `https:` and href is unchanged.
- A failed host or hostname write on an authority-less non-special URL such as `non-spec:/x` must not invent an authority: href stays `non-spec:/x`, not a triple-slash form.
- Setting pathname on an opaque-path URL is refused. Setting username or password is refused when the URL cannot have credentials (no host).
- Setting port to the empty string removes the port. Setting port on a URL that cannot have a port is refused.
- When a write would make the serialized href exceed the length cap, the URL is left unchanged. Host, hostname, protocol, username, password, port, pathname, and href writes that overrun are refused. Search and hash writes that overrun also leave search, hash, and href unchanged (there is no separate success flag; the observation is that the URL did not change). Percent-encoding expansion counts: a short string of spaces that would encode past the cap is refused the same way.
- Invalid percent-encoding in a host write is refused on a special-scheme URL (`www.google%X%.com`); on a non-special hierarchical URL that same sequence is accepted as a host, and an authority is inserted if the URL had none. The same sequence in an href path write is accepted, matching FP-01.

**Verifiable oracle:**

- Success: the fully qualified Google URL above yields the listed component strings and origin without credentials; protocol `wss` on `https://www.google.com` yields `wss://www.google.com/`; username and password appear in the href; search and hash readers include `?` and `#` only when present; refused writes on `mailto:` and empty-host `file:` leave href unchanged; `https` → `foo` protocol change is refused; empty host on `non-special:/x` becomes `non-special:///x` while a garbage host write leaves `non-spec:/x` untouched; IPv4, IPv6, and domain host kinds are distinguishable; a length-cap overrun on pathname or search leaves the original href.
- Failure / absence: component readers return raw substrings of the input without WHATWG delimiters or default `/` pathname; refused setters still mutate href; special-to-non-special protocol changes succeed; origin includes username; host and hostname are not distinguishable when a port is present; over-length writes still grow the href.

---

### FP-03: URL Search Params

**Public entry:** The Hrefparse URL Search Params type through the C++ library and the C interface: construct from a query string (with or without a leading `?`); append; set; get the first value; get all values for a key; has (by key, or by key and value); remove (by key, or by key and value); sort; serialize to a query string; iterate keys, values, and entries; reset from a new query string; report the number of pairs. Construction and reset honor the length cap from FP-01. This capability is independent of a full URL object; a caller may also take a URL’s search component (FP-02) and feed it here.

**Normal behavior:**

- Constructing from `a=b&c=d&e=f` yields three pairs in that order. Appending `g` / `h` adds a fourth pair; get of `g` is `h`; size is 4.
- Append of the same key twice preserves both pairs. Get returns the first value. Get-all returns every value in insertion order. Has-by-key is true if any pair has that key.
- Set of an existing key replaces the first matching pair’s value and deletes later pairs with that key, keeping the first pair’s position. Set of `key1` to `hello` on `key1=value1&key1=value2` serializes as `key1=hello`. Set of `key1` to `value3` on `key1=value1&key1=value2&key2=value1` serializes as `key1=value3&key2=value1`.
- Remove-by-key deletes every pair with that key. Remove-by-key-and-value deletes only matching pairs: after `key1=value1&key1=value2&key2=value2`, removing `key2` leaves two `key1` pairs; then removing `key1`/`value2` leaves `key1=value1`.
- Sort orders pairs by key using UTF-16 code-unit comparison (not UTF-8 bytes) and is stable for equal keys: `z=b&a=b&z=a&a=a` sorts to keys `a`, `a`, `z`, `z` with values `b`, `a`, `b`, `a` respectively. The keys U+1F308 and U+FB03 sort with U+1F308 first.
- Serialize does **not** include a leading `?`. Application/x-www-form-urlencoded rules apply: a space in a value serializes as `+` (get still returns a space); a plus sign serializes as `%2B`; an ampersand in a key or value serializes as `%26`; empty values produce `a=`; an empty key is allowed (`a=&=&=b` after appending `a`/empty, empty/empty, empty/`b`).
- Non-ASCII values round-trip: appending a value containing `é` serializes with percent-encoding (`%C3%A9` for that character) and get returns the original Unicode value.
- Iterators over keys, values, and entries walk the current list in order. After a mutation of the list, previously obtained iterators are not required to remain valid.
- Reset replaces the list from a new query string, subject to the length cap.

**Boundary / error behavior:**

- Construction or reset with a query string longer than the length cap leaves the object empty (size 0, serialize empty). Append and set of individual pairs are not rejected for length.
- Get of a missing key yields no value (distinguishable from a present key whose value is the empty string). Has is false for a missing key. Get-all of a missing key is an empty list.
- A key with no `=` in the input has an empty value (`bbb&bb` contributes empty values for those keys).
- Leading `?` on the constructor input is ignored as a query delimiter, not stored as part of the first key.

**Verifiable oracle:**

- Success: `a=b&c=d&e=f` plus append `g`/`h` makes get `g` equal `h`; set collapses duplicate keys while preserving later different keys; remove-by-value leaves the non-matching duplicate; sort of `z=b&a=b&z=a&a=a` yields the stable key order above; sorting the keys U+1F308 and U+FB03 puts U+1F308 first; serialize of a space is `a=b+c` while get returns `b c`; serialize of `+` uses `%2B`; size 0 after constructing from an over-length string under a lowered cap; get of a missing key is empty while get of a key whose value was appended as empty is present-and-empty.
- Failure / absence: the list is a single opaque string; set appends instead of replacing; sort reorders values within the same key; spaces stay as `%20` in search-params serialization (URL path encoding rather than form encoding); over-length construction still populates pairs.

---

### FP-04: URLPattern matching

**Public entry:** The Hrefparse C++ library URLPattern parse entry (not the C interface). The caller supplies a regular-expression engine with compile, search, and match. Input is either a pattern string or a per-component initializer covering the finite component set: protocol, username, password, hostname, port, pathname, search, hash. An optional base URL string resolves relative patterns. An optional ignore-case flag folds case in the compiled expressions. After a successful compile, the caller may test (yes/no), execute/match (structured result), and read each compiled component’s pattern string.

**Normal behavior:**

- Compiling pathname `/books/:id` with base `https://example.com` succeeds. Test against `https://example.com/books/123` is true. Execute/match against that URL succeeds with a result: pathname group `id` is `123`, and the other components that were fixed by the base (protocol `https`, hostname `example.com`) match as well.
- Named groups (`:name`) bind the segment up to the next separator. Multiple named pathname groups map independently: a pathname-only pattern `/:a/:b` matching pathname `/foo/bar` binds `a` to `foo` and `b` to `bar`; `/:a/:b/:c` matching `/x/y/z` binds `a` to `x`, `b` to `y`, and `c` to `z`. A custom regular-expression group on a named segment (digits-only on `:id`, or letters-only on `:a`) captures only when the custom expression matches: pathname `/:a` with a letters-only custom group matching `/hello` binds `a` to `hello`, and `https://example.com/books/abc` does not match a digits-only `:id` pattern that otherwise matches `/books/123`.
- A full wildcard is the `*` in a component pattern and matches remaining input in that component. Compiling the pathname-only pattern `/foo/*` succeeds. Matching pathname `/foo/bar` is a match. Matching pathname `/foo/bar/baz` is a match (the remaining part after `/foo/` may include a slash). Matching pathname `/foo` is no-match. Literal text matches exactly: compiling pathname-only `/foo/bar` matches pathname `/foo/bar` and is no-match against `/foo/baz`.
- A named group may be marked optional. Compiling the pathname-only pattern `/foo/:bar?` (named group `bar` optional) succeeds. Matching pathname `/foo/bar` is a match and binds `bar` to `bar`. Matching pathname `/foo` is also a match: the optional group does not participate, and the capture for `bar` is absent (the Standard leaves it undefined), distinguishable from the bound case. Matching pathname `/foo/bar/baz` or `/foobar` is no-match. Compiling a pathname-only named group `foo` marked optional (`:foo?`) is reported as not containing regular-expression groups. Compiling the same named group with a custom expression `hi` is reported as containing regular-expression groups.
- Execute/match returns, on success, a result with one sub-result per component in the finite set above. Each sub-result includes the component input string and a map of named groups to captured strings (or an absent capture where the Standard leaves the group undefined). Test returns only yes or no and must agree with whether execute/match produced a match.
- Ignore-case is a compile-time choice. Compiling a pathname-only pattern `/foo/bar` with ignore-case, then matching pathname `/FOO/BAR`, succeeds. Compiling the same pathname pattern without ignore-case, then matching `/FOO/BAR`, is no-match.
- A pathname-only initializer such as `/:a/:b` compiles without a base URL. A relative pattern string such as `/books/:id` compiles when given base `https://example.com`, as in the library’s documented example.
- Each compiled component’s pattern string is readable and reflects the pattern that was compiled for that component: a pathname-only initializer `/:a/:b` does not leave the pathname pattern empty.
- The library reports whether the compiled pattern contains regular-expression groups, distinguishable from a pattern that uses only literals, named segment wildcards, and full wildcards.

**Boundary / error behavior:**

- Compile fails (no usable URLPattern) for a syntactically invalid pattern, for a custom regular expression that the supplied engine cannot compile, and when the caller does not supply a usable engine. That failure is distinguishable from a compiled pattern that simply matches nothing.
- Test or execute/match of a URL that does not match returns no-match (test is false; execute/match has no match payload), not a compile error. That outcome is distinguishable from a pattern that never compiled.
- Matching the input `?` against a pattern compiled from `/foo` with base `http://example.com` completes and yields a defined yes or no; it does not abort.
- URLPattern is not available through the C interface. C callers are not required to compile patterns; C++ callers of the complete library are.

**Verifiable oracle:**

- Success: `/books/:id` with a digits-only custom group and base `https://example.com` matches `https://example.com/books/123` with group `id` equal to `123` and does not match `https://example.com/books/abc`; pathname-only `/:a/:b` matching `/foo/bar` binds `a` to `foo` and `b` to `bar` rather than swapping them; pathname-only `/foo/*` matches `/foo/bar` and `/foo/bar/baz` and does not match `/foo`; pathname-only `/foo/:bar?` matches `/foo/bar` with group `bar` bound to `bar` and matches `/foo` with group `bar` absent, and does not match `/foo/bar/baz` or `/foobar`; pathname-only `/foo/bar` matches `/foo/bar` and does not match `/foo/baz`; test agrees with execute/match on those pathnames; a pattern that fails to compile cannot be tested; pathname `/foo/bar` with ignore-case matches `/FOO/BAR` and the same pattern without ignore-case does not; an optional named group is not reported as a regular-expression group, while a custom-expression group is.
- Failure / absence: URLPattern always returns true; named groups are missing or assigned in the wrong order; test and execute/match disagree; compile never fails; ignore-case compiles match the same as default compiles on `/FOO/BAR`; matching is implemented as href string equality without component structure.
