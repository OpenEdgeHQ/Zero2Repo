# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**Hrefparse** is an embeddable C++20 library that parses, validates, normalizes, and mutates URLs according to the WHATWG URL Standard. It also implements URL Search Params query-string handling and URLPattern matching from the same family of web platform APIs. Internationalized domain names follow Unicode Technical Standard #46 (ToASCII / ToUnicode), including Punycode (`xn--`) labels.

A common use is to take a URL string and produce its WHATWG-normalized **href**. That is a different contract from RFC 3986 parsers: Hrefparse rewrites hosts and paths. The product’s canonical illustration is the input `https://www.7‑Eleven.com/Home/Privacy/Montréal` (Unicode hyphen in the host, accented path segment) normalizing to `https://www.xn--7eleven-506c.com/Home/Privacy/Montr%C3%A9al`. Leaving the string unchanged, or applying only RFC 3986 encoding, is a failure of the product.

The finished product is a **library**, not a network service and not an importable Python package. Integrators compile and link it. A matching **C interface** exposes the same parse, inspect, mutate, search-params, IDNA, and length-cap behavior. A command-line convenience named `hrefparsec` can validate, normalize, and print href or a chosen component; it is the same parse-and-inspect surface, not a separate product, and it is absent unless tools are enabled at configure time.

There is no runtime third-party dependency. A C++20 compiler is required (GCC 12 or newer, LLVM 14 or newer, or Microsoft Visual Studio 2022). CMake 3.16 or newer builds the library from this repository. Windows, Linux, and macOS are first-class; documented execution is Linux x86_64. Hardware is CPU-only. Public string inputs are ASCII or valid UTF-8; the caller is responsible for UTF-8 validity.

Hrefparse does not ship a regular-expression engine for URLPattern. The caller supplies an engine. Language bindings maintained outside this repository are not part of this product.

### Shape of the public surface

The public surface is a **C++ library plus a matching C interface**. There is no wire protocol and no product configuration-file format.

**Headers.** The public C++ umbrella header is `hrefparse.h`. The public C header is `hrefparse_c.h`. Both are shipped at the include-directory root so a translation unit compiles with `#include "`hrefparse.h`"` or `#include "`hrefparse_c.h`"` after adding that include directory. Nested headers under the include tree are pulled in by `hrefparse.h`; C++ callers include `hrefparse.h`, not those nested paths, to reach the published API. A documented single-header amalgamation is an alternative distribution of the same C++ API, not a second product.

**C++ library.** Symbols live in namespace `hrefparse`. The default parse result type is `hrefparse::url_aggregator`. Callers may also request `hrefparse::url`. Both layouts expose the same parse, inspect, and mutate outcomes; choosing a layout is not a separate product. Parse success is observed by treating `hrefparse::result` of `hrefparse::url_aggregator` as true and then reading components through `operator->` (for example `get_href`, `get_hostname`). A successful `hrefparse::result` is also dereferenceable with unary `*` so that `&*` of that result is a pointer to the `hrefparse::url_aggregator`. A failed parse is a falsy result and does not yield a usable URL.

The C++ free functions that define the library entry surface are:

- `hrefparse::parse` — first argument is `std::string_view`. Callers compile the one-argument form and the two-argument form whose second argument is a pointer to an already-parsed `hrefparse::url_aggregator` obtained by `&*` on a successful `hrefparse::result`. Returns `hrefparse::result` of `hrefparse::url_aggregator`.
- `hrefparse::can_parse` — first argument is `std::string_view`. Callers compile the one-argument form and the two-argument form whose second argument is a pointer to a `std::string_view` that holds the base URL string (not a parsed URL). Returns bool.
- `hrefparse::href_from_file` — argument is `std::string_view`; the returned value is stored in a `std::string`
- `hrefparse::set_max_input_length` / `hrefparse::get_max_input_length` — write and read the process-wide length cap
- `hrefparse::parse_url_pattern` — function template on the caller-supplied engine. Callers compile the form whose first argument is `std::string_view`, second is a pointer to a `std::string_view` base (null when absent), third is a pointer to `hrefparse::url_pattern_options`; and the form whose first argument is `hrefparse::url_pattern_init`, second is a null pointer, third is a pointer to `hrefparse::url_pattern_options`. Returns `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`. The engine exposes `regex_type` and these static members: `create_instance` takes `std::string_view` and bool and returns `std::optional` of `regex_type` (`std::nullopt` is compile failure); `regex_search` takes `std::string_view` and a const reference to `regex_type` and returns `std::optional` of `std::vector` of `std::optional` of `std::string`; `regex_match` takes `std::string_view` and a const reference to `regex_type` and returns bool.

On a successful parse of `file://`, pathname assignment is `set_pathname` with a `std::string_view` on the `hrefparse::url_aggregator` reached through `operator->`.

Inspect and mutate on a successful `hrefparse::url_aggregator` compile as follows. Readers: `get_href`, `get_origin`, `get_protocol`, `get_username`, `get_password`, `get_host`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`. The `get_origin` result is stored in a `std::string`; the other readers are used as `std::string_view`. Host kind is the public member `host_type` (not a method); callers convert that member to unsigned. Presence queries `has_credentials`, `has_hostname`, `has_port`, `has_search`, `has_hash` take no argument and are used as bool. Clears `clear_port`, `clear_search`, `clear_hash` take no argument. Flagged writers `set_host`, `set_hostname`, `set_protocol`, `set_pathname`, `set_username`, `set_password`, `set_port`, `set_href` take a `std::string_view` and return bool. `set_search` and `set_hash` take a `std::string_view`; callers compile those calls without using a return.

URL Search Params is the type `hrefparse::url_search_params`. Callers construct it from a `std::string_view`. Methods compile as follows. Pair count is `size`, assigned to `size_t`. Serialize is `to_string`, stored in a `std::string`. First-value lookup is `get` with a `std::string` key; the result is optional-like (`has_value`, then unary `*`). All-values lookup is `get_all` with a `std::string` key; the result is vector-like (`size` and `[]`). Presence is `has` in a one-argument (key) form and a two-argument (key, value) form, both used as bool. Writers `append` and `set` take two `std::string` arguments. `remove` compiles as one-argument (key) and two-argument (key, value). `sort` takes no argument. `reset` takes a `std::string` query. Iterators `get_keys`, `get_values`, and `get_entries` take no argument; callers walk with `has_next` and `next` where `next` is optional-like (`has_value`, then unary `*`). An entries item exposes `first` and `second`.

URLPattern is the class template `hrefparse::url_pattern` on the caller-supplied engine. A successful compile is observed by treating `tl::expected` of `hrefparse::url_pattern` as true and then using `operator->`. Methods compile as follows. Regexp-group report is `has_regexp_groups`, used as bool. Compiled component pattern strings are `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`, used as `std::string_view`. `test` compiles as `std::string_view` plus a null pointer, and as `hrefparse::url_pattern_init` plus a null pointer; the return is `hrefparse::result` of bool (boolean conversion, then unary `*`). `exec` compiles the same two overloads; the return is `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result` (a failed result is unexpected; empty optional is no-match; filled optional is a match). Callers default-construct `hrefparse::url_pattern_init` and assign protocol, username, password, hostname, port, pathname, search, hash, and `base_url` from `std::string`. Callers default-construct `hrefparse::url_pattern_options` and write public member `ignore_case`. A successful `exec` unwraps `hrefparse::url_pattern_result` with those eight component members, each an `hrefparse::url_pattern_component_result` exposing `input` and `groups` (sized; range-for of pair: `first` name, `second` optional-like with `has_value` then unary `*`). Remaining method-level defaults belong with those symbols.

**C interface.** C callers include `hrefparse_c.h` and link the same library (the implementation needs the C++ standard library; linking with a C++ driver is the usual way to satisfy that). The C type `hrefparse_url` is an opaque handle. Every handle returned by a parse entry is released with `hrefparse_free`. View strings use `hrefparse_string` (`data`, `length`) and remain valid only while the underlying `hrefparse_url` is unchanged. Owned strings use `hrefparse_owned_string` (`data`, `length`) and are released with `hrefparse_free_owned_string`. Among C component readers, `hrefparse_get_origin` is the owned-string exception: it returns `hrefparse_owned_string` and is released with `hrefparse_free_owned_string`; the other named C readers return `hrefparse_string` views.

The C free functions that define the C entry surface are:

- `hrefparse_parse` — two arguments: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length; returns `hrefparse_url`
- `hrefparse_parse_with_base` — four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length; returns `hrefparse_url`
- `hrefparse_can_parse` — two arguments: `const char*` and `size_t`
- `hrefparse_can_parse_with_base` — four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length
- `hrefparse_is_valid`
- `hrefparse_get_href` / `hrefparse_get_hostname` / `hrefparse_get_origin` / `hrefparse_get_protocol` / `hrefparse_get_username` / `hrefparse_get_password` / `hrefparse_get_host` / `hrefparse_get_port` / `hrefparse_get_pathname` / `hrefparse_get_search` / `hrefparse_get_hash`
- `hrefparse_get_host_type` — one argument `hrefparse_url`; the return converts to unsigned
- `hrefparse_set_host` / `hrefparse_set_hostname` / `hrefparse_set_protocol` / `hrefparse_set_pathname` / `hrefparse_set_username` / `hrefparse_set_password` / `hrefparse_set_port` / `hrefparse_set_href` — three arguments: `hrefparse_url`, `const char*`, `size_t`; the return is boolean-convertible (accepted or refused)
- `hrefparse_set_search` / `hrefparse_set_hash` — the same three arguments; callers compile those calls without using a return
- `hrefparse_clear_port` / `hrefparse_clear_search` / `hrefparse_clear_hash` — one argument `hrefparse_url`
- `hrefparse_has_credentials` / `hrefparse_has_hostname` / `hrefparse_has_port` / `hrefparse_has_search` / `hrefparse_has_hash` — one argument `hrefparse_url`; boolean-convertible
- `hrefparse_free` / `hrefparse_free_owned_string`
- `hrefparse_set_max_input_length` / `hrefparse_get_max_input_length`
- `hrefparse_idna_to_ascii` — two arguments: `const char*` and `size_t`; returns `hrefparse_owned_string`
- `hrefparse_idna_to_unicode` — two arguments: `const char*` and `size_t`; returns `hrefparse_owned_string`
- `hrefparse_parse_search_params` — two arguments: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length; returns `hrefparse_url_search_params`
- `hrefparse_free_search_params` — one argument `hrefparse_url_search_params`
- `hrefparse_search_params_size` — one argument `hrefparse_url_search_params`; the return is `size_t`-printable
- `hrefparse_search_params_to_string` — one argument `hrefparse_url_search_params`; returns `hrefparse_owned_string`, released with `hrefparse_free_owned_string`
- `hrefparse_search_params_get` — three arguments: `hrefparse_url_search_params`, `const char*`, `size_t`; returns `hrefparse_string`
- `hrefparse_search_params_get_all` — the same three arguments; returns `hrefparse_strings`, walked with `hrefparse_strings_size` and `hrefparse_strings_get`, released with `hrefparse_free_strings`
- `hrefparse_search_params_has` — the same three arguments; boolean-convertible
- `hrefparse_search_params_has_value` — five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`; boolean-convertible
- `hrefparse_search_params_append` / `hrefparse_search_params_set` / `hrefparse_search_params_remove_value` — the same five arguments
- `hrefparse_search_params_remove` — three arguments: `hrefparse_url_search_params`, `const char*`, `size_t`
- `hrefparse_search_params_sort` — one argument `hrefparse_url_search_params`
- `hrefparse_search_params_reset` — three arguments: `hrefparse_url_search_params`, query `const char*`, query `size_t`
- `hrefparse_search_params_get_keys` — one argument `hrefparse_url_search_params`; returns `hrefparse_url_search_params_keys_iter`, walked with `hrefparse_search_params_keys_iter_has_next` / `hrefparse_search_params_keys_iter_next` (`hrefparse_string`), released with `hrefparse_free_search_params_keys_iter`
- `hrefparse_search_params_get_values` — one argument `hrefparse_url_search_params`; returns `hrefparse_url_search_params_values_iter`, walked with `hrefparse_search_params_values_iter_has_next` / `hrefparse_search_params_values_iter_next` (`hrefparse_string`), released with `hrefparse_free_search_params_values_iter`
- `hrefparse_search_params_get_entries` — one argument `hrefparse_url_search_params`; returns `hrefparse_url_search_params_entries_iter`, walked with `hrefparse_search_params_entries_iter_has_next` / `hrefparse_search_params_entries_iter_next` (`hrefparse_string_pair` with `key` and `value` as `hrefparse_string`), released with `hrefparse_free_search_params_entries_iter`

Standalone ToASCII / ToUnicode are published on the C interface (`hrefparse_idna_to_ascii`, `hrefparse_idna_to_unicode`). URLPattern is not published on the C interface.

**Library artifact.** The CMake target name is `hrefparse`. The linked artifact is `libhrefparse.a` or `libhrefparse.so`. Including the public headers without linking that library must not produce a successful parse of an absolute `https` URL.

**CLI.** The optional convenience binary is `hrefparsec`. It is the same parse-and-inspect behavior. The default CMake configuration does not enable tools, so the binary is not required to be present.

The C++ and C call arities and parameter types above are the published compile surface. Remaining method-level defaults belong with those symbols.

### Naming conventions

**Product and library.** The product identity is Hrefparse. The CMake project, the library target, and the link stem are spelled `hrefparse`. The archive and shared-object basenames are `libhrefparse.a` and `libhrefparse.so`. The C++ namespace is `hrefparse`. The C prefix is `hrefparse_`.

**Headers.** C++: `hrefparse.h`. C: `hrefparse_c.h`.

**CLI.** The convenience tool basename is `hrefparsec`.

**Parse and validity.** C++ parse and can-parse are `hrefparse::parse` and `hrefparse::can_parse`. C splits the optional-base forms into `hrefparse_parse` / `hrefparse_parse_with_base` and `hrefparse_can_parse` / `hrefparse_can_parse_with_base`. C validity is `hrefparse_is_valid`. C++ validity is the boolean conversion of `hrefparse::result`.

**Filesystem path.** C++ only: `hrefparse::href_from_file`.

**Length cap.** C++: `hrefparse::set_max_input_length`, `hrefparse::get_max_input_length`. C: `hrefparse_set_max_input_length`, `hrefparse_get_max_input_length`.

**IDNA.** C: `hrefparse_idna_to_ascii`, `hrefparse_idna_to_unicode`. Punycode labels use the `xn--` prefix.

**WHATWG component vocabulary.** The component names are `href`, `origin`, `protocol`, `username`, `password`, `host`, `hostname`, `port`, `pathname`, `search`, and `hash`.

C++ readers: `get_href`, `get_origin`, `get_protocol`, `get_username`, `get_password`, `get_host`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`. C++ writers: `set_href`, `set_protocol`, `set_username`, `set_password`, `set_host`, `set_hostname`, `set_port`, `set_pathname`, `set_search`, `set_hash`. C++ clear: `clear_port`, `clear_search`, `clear_hash`. C++ presence: `has_credentials`, `has_hostname`, `has_port`, `has_search`, `has_hash`. Host kind on C++ is the public member `host_type` of `hrefparse::url_aggregator` (not a method).

C readers: `hrefparse_get_href`, `hrefparse_get_origin`, `hrefparse_get_protocol`, `hrefparse_get_username`, `hrefparse_get_password`, `hrefparse_get_host`, `hrefparse_get_hostname`, `hrefparse_get_port`, `hrefparse_get_pathname`, `hrefparse_get_search`, `hrefparse_get_hash`. C writers: `hrefparse_set_href`, `hrefparse_set_protocol`, `hrefparse_set_username`, `hrefparse_set_password`, `hrefparse_set_host`, `hrefparse_set_hostname`, `hrefparse_set_port`, `hrefparse_set_pathname`, `hrefparse_set_search`, `hrefparse_set_hash`. C clear: `hrefparse_clear_port`, `hrefparse_clear_search`, `hrefparse_clear_hash`. C presence: `hrefparse_has_credentials`, `hrefparse_has_hostname`, `hrefparse_has_port`, `hrefparse_has_search`, `hrefparse_has_hash`. Host kind on the C side is `hrefparse_get_host_type`.

**C string types.** `hrefparse_string` and `hrefparse_owned_string` each have `data` and `length`. `hrefparse_url` is the parse handle. `hrefparse_url_search_params` is the search-params handle. A multi-string result is `hrefparse_strings`, walked with `hrefparse_strings_size` and `hrefparse_strings_get` and released with `hrefparse_free_strings`. An entries walk yields `hrefparse_string_pair` (`key`, `value`).

**URL Search Params.** C++ type `hrefparse::url_search_params`, constructed from `std::string_view`. Methods: `size`, `to_string`, `get`, `get_all`, `has`, `append`, `set`, `remove`, `sort`, `reset`, `get_keys`, `get_values`, `get_entries`. Iterator walk: `has_next`, `next`. C construct/release: `hrefparse_parse_search_params` / `hrefparse_free_search_params`. C operations: `hrefparse_search_params_size`, `hrefparse_search_params_to_string`, `hrefparse_search_params_get`, `hrefparse_search_params_get_all`, `hrefparse_search_params_has`, `hrefparse_search_params_has_value`, `hrefparse_search_params_append`, `hrefparse_search_params_set`, `hrefparse_search_params_remove`, `hrefparse_search_params_remove_value`, `hrefparse_search_params_sort`, `hrefparse_search_params_reset`, `hrefparse_search_params_get_keys`, `hrefparse_search_params_get_values`, `hrefparse_search_params_get_entries`.

**Special schemes.** The finite special-scheme set is exactly `ftp`, `file`, `http`, `https`, `ws`, and `wss`. Any other scheme is non-special.

**URLPattern.** C++ parse entry `hrefparse::parse_url_pattern` (function template on the caller-supplied engine). Compiled type `hrefparse::url_pattern`. Initializer `hrefparse::url_pattern_init` (component members protocol, username, password, hostname, port, pathname, search, hash, plus `base_url`). Options `hrefparse::url_pattern_options` (member `ignore_case`). Compile result is `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`. Methods: `has_regexp_groups`, `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`, `test`, `exec`. Execute result `hrefparse::url_pattern_result` of eight `hrefparse::url_pattern_component_result` members (`input`, `groups`). Engine: `regex_type`; static `create_instance` takes `std::string_view` and bool and returns `std::optional` of `regex_type` (`std::nullopt` is compile failure); static `regex_search` takes `std::string_view` and a const reference to `regex_type` and returns `std::optional` of `std::vector` of `std::optional` of `std::string`; static `regex_match` takes `std::string_view` and a const reference to `regex_type` and returns bool. The compile definition `HREFPARSE_USE_UNSAFE_STD_REGEX_PROVIDER` exposes a `std::regex`-backed provider; it is not a safe default for untrusted patterns.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**Input encoding.** Public string inputs are ASCII or valid UTF-8. The caller is responsible for UTF-8 validity.

**Process-wide length cap.** The cap is a process-wide byte limit on a URL’s serialized href and on related inputs. The default is the maximum 32-bit unsigned integer. The caller may lower it with `hrefparse::set_max_input_length` / `hrefparse_set_max_input_length` and read it back with `hrefparse::get_max_input_length` / `hrefparse_get_max_input_length`. The cap applies to both the raw input and the **normalized** href (percent-encoding expansion counts). The same cap applies to `hrefparse::href_from_file` and to URL Search Params construction and reset. Individual search-parameter append/set calls are not length-capped. A parse or conversion that would exceed the cap fails: parse yields no usable URL, `hrefparse::can_parse` / `hrefparse_can_parse` agree with that failure, and `hrefparse::href_from_file` returns an empty string. Raising the cap back to the default restores acceptance of ordinary-length URLs.

**Success versus failure.** A failed parse does not yield a usable URL. The caller can tell success from failure before reading href or any component. In C++, a failed `hrefparse::result` is falsy. In C, `hrefparse_is_valid` is false on that handle. Standalone IDNA on the C interface hands the caller a usable domain only when the owned string has non-null `data` and non-zero `length`; null `data` or zero `length` is “no usable domain.” Empty string is not the only allowed failure encoding.

**WHATWG href, not identity copy.** A successful parse serializes the WHATWG href, which may differ from the input. Leading and trailing C0 controls and spaces are stripped. ASCII tab, line feed, and carriage return are then removed wherever they remain; they are not percent-encoded. A space that is not stripped is percent-encoded as `%20` in the URL href (a plus in a path is not treated as a space). Scheme and host matching for special-scheme URLs is ASCII-case-insensitive.

**Special schemes and default ports.** Special schemes are `ftp`, `file`, `http`, `https`, `ws`, and `wss`. Default ports used in parsing and serialization are: `http` and `ws` → 80; `https` and `wss` → 443; `ftp` → 21; `file` has none. A default port is omitted from the href (for example `https://example.com:443/` serializes without `:443`). A non-default port is kept.

**Hosts.** Host parsing follows the WHATWG host parser, not dotted-decimal-only IPv4 (mixed-base IPv4 is canonicalized to dotted decimal). IPv6 hosts appear in brackets in the href. Internationalized hosts are converted with ToASCII; host parsing of an `http`/`https` URL uses the same mapping as standalone `hrefparse_idna_to_ascii`, including Unicode Normalization Form C reordering when the host is not already NFC. A space in a host is a parse failure; the same embedded space in a standalone ToASCII input is not.

**`file:` drive letters.** A `file:` path whose first segment is a normalized Windows drive letter (exactly one ASCII letter followed by `:`) is protected from `..` shortening (`file:c:/..` serializes as `file:///c:/`). A longer first segment that merely starts with letter-colon is not protected (`file:c:x/..` serializes as `file:///`).

**Filesystem-path conversion.** `hrefparse::href_from_file` takes a `std::string_view` and produces a `file:` href (stored in a `std::string`) that matches the href obtained by parsing `file://` and assigning that path with `set_pathname` given a `std::string_view`. When the raw path or the percent-expanded href exceeds the length cap, the conversion returns `""`.

**Can-parse agreement.** `hrefparse::can_parse` / `hrefparse_can_parse` (and `hrefparse_can_parse_with_base` when a base is given) return yes if and only if parse of the same input and base would succeed, including length-cap rejections. The caller does not have to keep the URL object.

**C handle lifetime.** Every `hrefparse_url` from `hrefparse_parse` / `hrefparse_parse_with_base` is released with `hrefparse_free`. Every `hrefparse_url_search_params` from `hrefparse_parse_search_params` is released with `hrefparse_free_search_params`. Every `hrefparse_owned_string` from IDNA, `hrefparse_search_params_to_string`, or other owned-string entries is released with `hrefparse_free_owned_string`. `hrefparse_string` views returned by getters are invalidated by any subsequent mutation of that handle.

**Linking.** The published headers are not a complete implementation. A program that includes `hrefparse.h` (or `hrefparse_c.h`) but does not link `libhrefparse.a` / `libhrefparse.so` must not produce a successful Hrefparse url for an absolute `https` input.

**URLPattern engine.** Hrefparse does not ship a regular-expression engine. Compile fails when the caller does not supply a usable engine. That failure is distinguishable from a compiled pattern that matches nothing. URLPattern is C++-only.

**No product-owned process exit codes.** The library reports parse and mutation outcomes through `hrefparse::result` / `hrefparse_is_valid` / setter return values, not through `main` exit status. The optional `hrefparsec` tool is not a required entry of this surface.

## `_Node_iterator_base`

This name is not a published Hrefparse entry. Caller-side C++ iteration over `groups` uses `operator==`; Hrefparse does not export a type whose published members are that equality.

### Signature

`operator==` compiles with arity one.

## `_mm_and_si128`

`_mm_and_si128`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_andnot_si128`

`_mm_andnot_si128`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_cmpeq_epi8`

`_mm_cmpeq_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_cmpgt_epi8`

`_mm_cmpgt_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_loadu_si128`

`_mm_loadu_si128`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is one.

## `_mm_movemask_epi8`

`_mm_movemask_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is one.

## `_mm_or_si128`

`_mm_or_si128`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_set1_epi8`

`_mm_set1_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is one.

## `_mm_setr_epi8`

`_mm_setr_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is sixteen.

## `_mm_setzero_si128`

`_mm_setzero_si128`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is zero.

## `_mm_shuffle_epi8`

`_mm_shuffle_epi8`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `_mm_srli_epi16`

`_mm_srli_epi16`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and do not call it. It is a platform 128-bit integer SIMD intrinsic used only inside an optional SSSE3 percent-encode path.

Compile arity is two.

## `apply_comp`

`apply_comp`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is three.

## `apply_write`

`apply_write`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is five.

## `basic_ostream`

This name is not a published Hrefparse entry. Callers include `hrefparse.h` and `iostream`. Insertion on `std::cout` is a C++ standard-library operation, not an Hrefparse export.

### Signature

`operator<<` compiles with arity one. Callers chain that insertion on `std::cout`.

## `basic_string`

This name is not a published Hrefparse entry. Callers include `hrefparse.h` and use `std::string` from the C++ standard library.

### Signature

`operator==` compiles with arity one. Callers compare a `std::string` with that equality. Hrefparse does not re-export this type under another name.

## `const_iterator`

`const_iterator`. This name is not a published Hrefparse entry. Caller-side C++ iteration uses `operator++`; Hrefparse does not export a type whose published members are that increment. Callers also name `std::string_view::const_iterator` as the iterator type of `std::match_results`.

### Signature

`operator++` compiles with arity zero.

## `copy_hrefparse_string`

`copy_hrefparse_string`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is two: an `hrefparse_string` and a `size_t` out-length pointer. Callers read `data` and `length` from the `hrefparse_string`.

## `emit_can`

`emit_can`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is one.

## `emit_field`

`emit_field`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arities are two and three.

## `emit_get`

`emit_get`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is five. Callers pass an `hrefparse::url_search_params` reference and a `std::string` key, then call `get` on that object and test `has_value`.

## `emit_get_all`

`emit_get_all`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is three. Callers pass an `hrefparse::url_search_params` reference and a `std::string` key, then call `get_all` on that object and walk the result with `size` and `[]`.

## `emit_groups`

`emit_groups`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is two.

## `emit_indexed`

`emit_indexed`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arities are three and four.

## `emit_indexed_cstr`

`emit_indexed_cstr`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is three.

## `emit_snapshot`

`emit_snapshot`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is one.

## `emit_status`

`emit_status`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is one.

## `emit_yesno`

`emit_yesno`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is two.

## `exit`

`exit`. This name is not a published Hrefparse entry. Callers include `hrefparse.h`; this name comes from the C or C++ standard library (`std::exit`), not from the Hrefparse headers.

### Signature

Compile arity is one.

## `flag_type`

This name is not a published Hrefparse entry. Caller-side regular-expression flags use `operator|`; Hrefparse does not export a type whose published members are that bitwise or. Callers combine `std::regex::icase` with `std::regex_constants::ECMAScript`.

### Signature

`operator|` compiles with arity one.

## `fprintf`

`fprintf`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arities are two, three, and four.

## `fputc`

`fputc`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is two.

## `fread`

`fread`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is four.

## `free`

`free`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is one.

## `fwrite`

`fwrite`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is four.

## `hrefparse::can_parse`

Include `hrefparse.h`. The C++ can-parse entry is `hrefparse::can_parse` in namespace `hrefparse`.

### Signature

```
bool hrefparse::can_parse(std::string_view input);
bool hrefparse::can_parse(std::string_view input, const std::string_view* base_input);
```

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to a `std::string_view` that holds the base URL string, not a parsed URL. Returns bool: yes if and only if parse of the same input and base would succeed, including length-cap rejections. The caller does not have to keep the URL object.

The matching C entry is `hrefparse_can_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer and a `size_t` length. Returns bool.

## `hrefparse::character_sets::bit_at`

`hrefparse::character_sets::bit_at`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

### Signature

When defined, compile arity is two:

```
constexpr bool bit_at(const uint8_t a[], uint8_t i);
```

## `hrefparse::character_sets::hex`

`hrefparse::character_sets::hex`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, it is a lookup table of percent-encoded bytes (`%00` through `%FF`), not a parse-entry argument.

## `hrefparse::errors`

`hrefparse::parse_url_pattern` returns `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`.

### Signature

Callers declare the compile result as `tl::expected` of `hrefparse::url_pattern` and `hrefparse::errors`. A failed expected is falsy and does not yield a usable pattern. That failure is distinguishable from a compiled pattern whose `test` / `exec` is no-match.

## `hrefparse::get_max_input_length`

Include `hrefparse.h`. The C++ length-cap reader is `hrefparse::get_max_input_length`.

### Signature

```
uint32_t hrefparse::get_max_input_length();
```

Compile arity is zero. Returns the process-wide byte cap as `uint32_t`. The default is the maximum 32-bit unsigned integer.

The matching C entry is `hrefparse_get_max_input_length` (include `hrefparse_c.h`). Compile arity is zero. The C return is printed as an unsigned decimal.

## `hrefparse::href_from_file`

Include `hrefparse.h`. The C++ filesystem-path conversion is `hrefparse::href_from_file`.

### Signature

```
std::string hrefparse::href_from_file(std::string_view path);
```

The argument is `std::string_view`. The returned value is stored in a `std::string`.

When the raw path or the percent-expanded href exceeds the process-wide length cap, the conversion returns `""`. Otherwise the href matches the result of parsing `file://` and assigning that path with `set_pathname` given a `std::string_view` on the `hrefparse::url_aggregator` reached through arrow access.

## `hrefparse::parse`

Include `hrefparse.h`. The C++ parse entry is `hrefparse::parse` in namespace `hrefparse`.

### Signature

```
hrefparse::result<hrefparse::url_aggregator> hrefparse::parse(std::string_view input);
hrefparse::result<hrefparse::url_aggregator> hrefparse::parse(std::string_view input, const hrefparse::url_aggregator* base_url);
```

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to an already-parsed `hrefparse::url_aggregator`, obtained by applying unary `*` to a successful `hrefparse::result` and taking its address (`&*` of the result). Returns `hrefparse::result` of `hrefparse::url_aggregator`.

A successful result converts to true. Components are read through arrow access (`get_href`, `get_hostname`). A failed result is falsy and does not yield a usable URL. When the process-wide length cap would be exceeded by the raw input or the normalized href, parse fails.

The matching C entry is `hrefparse_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. It returns `hrefparse_url`. Every returned handle is released with `hrefparse_free`. Success is observed with `hrefparse_is_valid`.

## `hrefparse::parse_url_pattern`

Include `hrefparse.h`. The C++ URLPattern parse entry is `hrefparse::parse_url_pattern` in namespace `hrefparse`. There is no matching C entry.

### Signature

This entry is a function template on the caller-supplied regular-expression engine. Callers write `hrefparse::parse_url_pattern` with that engine as the template argument. Compile arity is three.

```
tl::expected<hrefparse::url_pattern<regex_provider>, hrefparse::errors>
hrefparse::parse_url_pattern<regex_provider>(std::string_view input,
                                       const std::string_view* base_url,
                                       const hrefparse::url_pattern_options* options);

tl::expected<hrefparse::url_pattern<regex_provider>, hrefparse::errors>
hrefparse::parse_url_pattern<regex_provider>(hrefparse::url_pattern_init input,
                                       const std::string_view* base_url,
                                       const hrefparse::url_pattern_options* options);
```

The first argument is either a pattern string as `std::string_view` or a moved `hrefparse::url_pattern_init`. The second argument is a pointer to a `std::string_view` holding a base URL string, or a null pointer. The third argument is a pointer to `hrefparse::url_pattern_options`. Returns `tl::expected` of `hrefparse::url_pattern` (templated on the same engine) and `hrefparse::errors`. A successful result converts to true; a failed result is falsy and does not yield a usable pattern.

When the first argument is a relative pattern string, a non-null base pointer resolves it. Compiling pathname `/books/:id` with base `https://example.com` succeeds. Compiling a pathname-only `hrefparse::url_pattern_init` such as `/:a/:b` succeeds with a null base pointer. When the initializer carries a base, that base is the `base_url` member of `hrefparse::url_pattern_init` and the second argument is a null pointer.

The engine type must expose:

```
using regex_type = /* engine regex object */;
static std::optional<regex_type> create_instance(std::string_view pattern,
                                                 bool ignore_case);
static std::optional<std::vector<std::optional<std::string>>>
regex_search(std::string_view input, const regex_type& pattern);
static bool regex_match(std::string_view input, const regex_type& pattern);
```

The engine exposes the nested type `regex_type`. `create_instance`, `regex_search`, and `regex_match` are static. `create_instance` takes the compiled component expression and the `ignore_case` flag from options. Returning `std::nullopt` from `create_instance` is a parse failure. `regex_search` returns a missing optional when the component does not match, or a `std::vector` of per-group `std::optional` of `std::string` (a missing inner optional is an unbound capture). `regex_match` returns bool.

Parse fails (falsy result) for a syntactically invalid pattern (for example an unclosed `{`), for a custom regular expression the engine cannot compile, and when `create_instance` yields no instance. That failure is distinguishable from a compiled pattern that matches nothing.

## `hrefparse::result`

`hrefparse::parse` returns `hrefparse::result` of `hrefparse::url_aggregator`.

### Signature

A successful result converts to true. Components are read through arrow access (`operator->`; for example `get_href`, `get_hostname`). A successful result is also dereferenceable with unary `*` (`operator*`) so that `&*` of that result is a pointer to the `hrefparse::url_aggregator`, which is the already-parsed base passed to two-argument `hrefparse::parse`.

A failed result is falsy and does not yield a usable URL.

## `hrefparse::set_max_input_length`

Include `hrefparse.h`. The C++ length-cap writer is `hrefparse::set_max_input_length`.

### Signature

```
void hrefparse::set_max_input_length(uint32_t length);
```

Compile arity is one. The argument is `uint32_t`. The cap is process-wide. It applies to both the raw input and the normalized href (percent-encoding expansion counts), and to `hrefparse::href_from_file`. A parse that would exceed the cap fails. Raising the cap back to the maximum 32-bit unsigned integer restores acceptance of ordinary-length URLs.

The matching C entry is `hrefparse_set_max_input_length` (include `hrefparse_c.h`). Compile arity is one: `uint32_t`.

## `hrefparse::unicode::bits`

`bits`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::cs_byte`

`cs_byte`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::encode_mask_window`

`encode_mask_window`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is four.

## `hrefparse::unicode::hi`

`hi`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::high_byte`

`high_byte`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::hits`

`hits`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::idx`

`idx`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::kPercentEncodeSimdMin`

`kPercentEncodeSimdMin`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, it is an internal size threshold for an optional SIMD percent-encode path, not a caller-facing constant.

## `hrefparse::unicode::lo`

`lo`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::load_ssse3_percent_tables`

`load_ssse3_percent_tables`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is one.

## `hrefparse::unicode::mask`

`mask`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::mask0`

`mask0`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::mask1`

`mask1`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::off`

`off`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::percent_encode_to_scalar`

`percent_encode_to_scalar`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is four.

## `hrefparse::unicode::percent_encode_to_ssse3`

`percent_encode_to_ssse3`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is five.

## `hrefparse::unicode::percent_encode_to_wide`

`percent_encode_to_wide`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is four.

## `hrefparse::unicode::ssse3_percent_mask`

`ssse3_percent_mask`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is two.

## `hrefparse::unicode::t`

`t`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::tables`

`tables`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::trailing_zeroes32`

`trailing_zeroes32`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, compile arity is one.

## `hrefparse::unicode::word`

`word`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::word0`

`word0`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::word1`

`word1`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::unicode::zero_run`

`zero_run`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

This is a local value in an internal percent-encode path, not a library export.

## `hrefparse::url_aggregator`

Include `hrefparse.h`. The default parse result type is `hrefparse::url_aggregator`.

### Signature

```
std::string_view get_href() const;
std::string_view get_hostname() const;
bool set_pathname(std::string_view input);
```

On a successful `hrefparse::result` of `hrefparse::url_aggregator`, readers and writers are reached through arrow access. `get_href` and `get_hostname` take no argument; callers store those views in a `std::string`. `set_pathname` takes a `std::string_view`. Callers compile that write after parsing `file://`.

## `hrefparse::url_aggregator.host_type`

On a successful `hrefparse::result` of `hrefparse::url_aggregator`, host kind is the public member `host_type` (not a method).

### Signature

Callers read `host_type` on the `hrefparse::url_aggregator` and convert the value to unsigned. IPv4, IPv6, and domain hosts produce distinguishable unsigned values; two domain hosts share a value; two IPv4 hosts share a value.

## `hrefparse::url_aggregator.set_host`

On a successful `hrefparse::result` of `hrefparse::url_aggregator`, host assignment is `set_host`.

### Signature

`set_host` takes a `std::string_view` and returns bool (accepted or refused). The same compile shape is used by `set_hostname`, `set_protocol`, `set_pathname`, `set_username`, `set_password`, `set_port`, and `set_href`.

`set_search` and `set_hash` take a `std::string_view`; callers compile those calls without using a return.

## `hrefparse::url_aggregator.set_pathname`

On a successful `hrefparse::result` of `hrefparse::url_aggregator`, pathname assignment is reached through arrow access (`set_pathname`, then `get_href`).

### Signature

`set_pathname` takes a `std::string_view`. Callers compile that call after parsing `file://`.

## `hrefparse::url_base`

Include `hrefparse.h`. Host kind is the public data member `host_type` on `url_base` (inherited by `hrefparse::url_aggregator`; not a method).

### Signature

Callers read `host_type` on a successful `hrefparse::url_aggregator` and convert the value to unsigned. IPv4 hosts (for example after parsing `http://127.0.0.1/`), IPv6 hosts (for example after parsing `http://[::1]/`), and domain hosts (for example after parsing `https://example.com/` or `https://www.google.com`) produce three mutually distinguishable unsigned values. Two domain hosts share a value. Two IPv4 hosts share a value.

The matching C entry is `hrefparse_get_host_type` (include `hrefparse_c.h`).

## `hrefparse::url_pattern`

Include `hrefparse.h`. URLPattern is the class template `hrefparse::url_pattern` in namespace `hrefparse`, parameterized by the same caller-supplied engine passed to `hrefparse::parse_url_pattern`. Callers name a successful compile as `tl::expected` of `hrefparse::url_pattern` and `hrefparse::errors` and reach members through arrow access.

### Signature

```
bool has_regexp_groups() const;
std::string_view get_protocol() const;
std::string_view get_username() const;
std::string_view get_password() const;
std::string_view get_hostname() const;
std::string_view get_port() const;
std::string_view get_pathname() const;
std::string_view get_search() const;
std::string_view get_hash() const;
hrefparse::result<bool> test(const url_pattern_input& input,
                       const std::string_view* base_url);
hrefparse::result<std::optional<hrefparse::url_pattern_result>> exec(
    const url_pattern_input& input, const std::string_view* base_url);
```

`has_regexp_groups`, `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, and `get_hash` take no argument. The readers return `std::string_view`. `get_pathname` after a successful pathname-only compile of `/:a/:b` is nonempty and is not the same string as after compiling `/foo/bar` or a distinct runtime pathname. `has_regexp_groups` is true when a named group has a custom regular expression (for example `:foo(hi)`, digits-only on `:id`, letters-only on `:a`) and false for a literal, a named segment wildcard (`/:a/:b`), a full wildcard (`/foo/*`), and an optional named group (`/:foo?`).

`test` and `exec` compile with arity two. The parameter type is `url_pattern_input`: a `std::string_view` URL string or an `hrefparse::url_pattern_init`. The second argument is a pointer to a `std::string_view` base; callers pass a null pointer. `test` returns `hrefparse::result` of bool. A successful result converts to true; unary `*` yields the yes/no. `exec` returns `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result`. A successful result converts to true. An empty optional (`has_value` is false) is no-match. A filled optional is a match; callers read `protocol`, `username`, `password`, `hostname`, `port`, `pathname`, `search`, and `hash` from `value`.

`test` is true exactly when `exec` produces a match payload. Compiling `/books/:id` with base `https://example.com` then testing and executing `https://example.com/books/123` is a match: pathname group `id` is `123`, and the base-fixed protocol and hostname participate (`https` and `example.com`). The same pattern is no-match against an `http` scheme, a different host, a missing `/:id` segment, an extra pathname segment, or a different prefix. Compiling with base `http://example.com` changes that yes/no against the same `https` input.

Named groups bind in order: pathname-only `/:a/:b` matching `/foo/bar` binds `a` to `foo` and `b` to `bar`; `/:a/:b/:c` matching `/x/y/z` binds `a`, `b`, `c` independently. A custom expression constrains the capture: letters-only on `:a` matching `/hello` binds `a` to `hello`; digits-only on `:id` matches `/books/123` and is no-match against `/books/abc`; `:foo(hi)` matches `/hi` and is no-match against `/ho`. Full wildcard `/foo/*` matches `/foo/bar` and `/foo/bar/baz` (the remainder may include a slash) and is no-match against `/foo`. Optional `/foo/:bar?` matches `/foo/bar` with `bar` bound to `bar` and matches `/foo` with `bar` absent, and is no-match against `/foo/bar/baz` or `/foobar`. Literal `/foo/bar` matches itself and is no-match against `/foo/baz`. Matching the input `?` against `/foo` compiled with base `http://example.com` completes with a defined yes or no and does not fail the result.

No-match is not a compile error: `test` is false and `exec` has no payload. A pattern that failed to parse cannot be tested.

## `hrefparse::url_pattern.exec`

On a successful `hrefparse::url_pattern`, structured match is `exec`.

### Signature

Callers compile `exec` with `std::string_view` and a null pointer, and with `hrefparse::url_pattern_init` and a null pointer. The return is `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result`. A failed result is unexpected after a successful compile. Callers use `operator->` then `has_value`: empty optional is no-match; a filled optional is a match and unwraps `hrefparse::url_pattern_result`. A failed compile has no `exec`. No-match is not a compile error.

## `hrefparse::url_pattern.get_pathname`

On a successful `hrefparse::url_pattern`, compiled component pattern strings are read through `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, and `get_hash`.

### Signature

Each getter takes no argument and is used as `std::string_view`. A successful compile does not leave `get_pathname` empty. Distinct compiled pathnames yield pairwise distinct `get_pathname` strings.

## `hrefparse::url_pattern.has_regexp_groups`

On a successful `hrefparse::url_pattern`, the regexp-group report is `has_regexp_groups`.

### Signature

`has_regexp_groups` takes no argument and is used as bool. A custom-expression named group reports true. A pattern that uses only literals, named segment wildcards, optional named groups, and full wildcards reports false.

## `hrefparse::url_pattern.test`

On a successful `hrefparse::url_pattern`, yes/no match is `test`.

### Signature

Callers compile `test` with `std::string_view` and a null pointer, and with `hrefparse::url_pattern_init` and a null pointer. The return is `hrefparse::result` of bool. A successful result converts to true; callers then dereference with unary `*` for the yes/no. `test` agrees with whether `exec` produced a match. A failed compile has no `test`.

## `hrefparse::url_pattern_component_result`

Include `hrefparse.h`. One URLPattern component of a successful `exec` is `hrefparse::url_pattern_component_result`.

### Signature

```
std::string input;
/* named-group map */ groups;
```

`input` is the component input string. Two successful `/foo/*` executes that differ only in pathname do not share the same `pathname` `input`. After compiling `/books/:id` with base `https://example.com` and matching `https://example.com/books/123`, the protocol `input` is the `https` scheme (a trailing colon, if present, is not significant) and the hostname `input` is `example.com`.

`groups` is sized (callers read `size`) and is walked with range-for. Each item is a pair: `first` is the group name as `std::string`; `second` is optional-like. `has_value` true means the group is present and unary `*` is the captured string. `has_value` false means the capture is absent (the Standard leaves it undefined), distinguishable from the bound case. Pathname `/:a/:b` matching `/foo/bar` binds `a` to `foo` and `b` to `bar`. Optional `/foo/:bar?` matching `/foo/bar` binds `bar` to `bar`; matching `/foo` leaves `bar` absent (missing from the map, or present with no value).

## `hrefparse::url_pattern_init`

Include `hrefparse.h`. The per-component initializer is `hrefparse::url_pattern_init` in namespace `hrefparse`.

### Signature

Default construction compiles with arity zero (`hrefparse::url_pattern_init init;`). Callers then assign `std::string` values onto public members.

```
std::optional<std::string> protocol;
std::optional<std::string> username;
std::optional<std::string> password;
std::optional<std::string> hostname;
std::optional<std::string> port;
std::optional<std::string> pathname;
std::optional<std::string> search;
std::optional<std::string> hash;
std::optional<std::string> base_url;
```

The finite component set is `protocol`, `username`, `password`, `hostname`, `port`, `pathname`, `search`, `hash`. `base_url` is the optional base URL string used when compiling from an initializer (the parse entry’s base pointer is then null). A pathname-only initializer such as `/:a/:b` compiles with no base. The same type is also the structured input to `test` and `exec` (for example pathname `/foo/bar` as match input).

## `hrefparse::url_pattern_options`

Include `hrefparse.h`. Compile-time URLPattern options are `hrefparse::url_pattern_options` in namespace `hrefparse`.

### Signature

Default construction compiles with arity zero (`hrefparse::url_pattern_options options;`). Callers write the public member and pass a pointer into `hrefparse::parse_url_pattern`.

```
bool ignore_case;
```

`ignore_case` is the compile-time case-folding choice. When it is true, compiling pathname-only `/foo/bar` and matching `/FOO/BAR` succeeds. When it is false, that same pair is no-match, while `/foo/bar` still matches `/foo/bar`. The parse entry takes a pointer to this object, not a bare bool.

## `hrefparse::url_pattern_result`

A successful `exec` unwraps `hrefparse::url_pattern_result`.

### Signature

`hrefparse::url_pattern_result` has public members `protocol`, `username`, `password`, `hostname`, `port`, `pathname`, `search`, and `hash`. Each is an `hrefparse::url_pattern_component_result`. A successful match includes all eight.

## `hrefparse::url_pattern_result const`

Include `hrefparse.h`. A successful `exec` unwraps `hrefparse::url_pattern_result`. Callers bind a const reference to `value` and read the eight public component members.

### Signature

```
hrefparse::url_pattern_component_result protocol;
hrefparse::url_pattern_component_result username;
hrefparse::url_pattern_component_result password;
hrefparse::url_pattern_component_result hostname;
hrefparse::url_pattern_component_result port;
hrefparse::url_pattern_component_result pathname;
hrefparse::url_pattern_component_result search;
hrefparse::url_pattern_component_result hash;
```

On a match, all eight members are present: `protocol`, `username`, `password`, `hostname`, `port`, `pathname`, `search`, `hash`. Each is `hrefparse::url_pattern_component_result`. A no-match does not yield this object.

## `hrefparse::url_search_params`

Include `hrefparse.h`. URL Search Params is the type `hrefparse::url_search_params` in namespace `hrefparse`.

### Signature

```
explicit url_search_params(const std::string_view input);
size_t size() const noexcept;
void append(std::string_view key, std::string_view value);
std::optional<std::string_view> get(std::string_view key);
std::vector<std::string> get_all(std::string_view key);
bool has(std::string_view key) noexcept;
bool has(std::string_view key, std::string_view value) noexcept;
void set(std::string_view key, std::string_view value);
void remove(std::string_view key);
void remove(std::string_view key, std::string_view value);
void sort();
std::string to_string() const;
void reset(std::string_view input);
url_search_params_keys_iter get_keys();
url_search_params_values_iter get_values();
url_search_params_entries_iter get_entries();
```

Callers construct `hrefparse::url_search_params` from a `std::string_view` (brace initialization from a `std::string` view is accepted). Compile arity of the constructor is one.

The object is an ordered list of key/value pairs, independent of a full URL. A URL search component (with or without a leading `?`) may be fed as the constructor input. A leading `?` is a query delimiter and is not stored as part of the first key. A key with no `=` has an empty value.

Construction honors the process-wide length cap from `hrefparse::set_max_input_length`. An input longer than the cap leaves the object empty (`size` is 0, `to_string` is empty, `get` of a would-be key has no value, `has` is false, `get_all` is an empty list). An input whose length equals the cap is accepted. Individual `append` / `set` calls are not length-capped: they still add or replace pairs on an object that construction left empty.

- `size` takes no argument. Callers assign the result to `size_t`. It is the number of pairs, counting duplicates.
- `append` takes two arguments (key, then value). It adds a new pair at the end. Appending the same key twice preserves both pairs.
- `get` takes one argument (key). The result is optional-like: callers test `has_value` and then dereference with unary `*`. It returns the first matching value. A missing key is the falsy `has_value` case, distinguishable from a present key whose value is the empty string.
- `get_all` takes one argument (key). The result is vector-like: callers use `size` and index with `[]`. Values are in insertion order. A missing key yields an empty list.
- `has` compiles as a one-argument form (key) and a two-argument form (key, value). Both are used as bool. The one-argument form is true if any pair has that key. The two-argument form is true if any pair matches both key and value.
- `set` takes two arguments (key, then value). If the key is already present, it replaces the first matching pair’s value, deletes later pairs with that key, and keeps the first pair’s position. If the key is absent, it appends a new pair.
- `remove` compiles as a one-argument form (key) and a two-argument form (key, value). One argument deletes every pair with that key. Two arguments deletes only pairs that match both key and value.
- `sort` takes no argument. It orders pairs by key using UTF-16 code-unit comparison (not UTF-8 bytes) and is stable for equal keys. The keys U+1F308 and U+FB03 sort with U+1F308 first. After sorting `z=b&a=b&z=a&a=a`, keys are `a`, `a`, `z`, `z` with values `b`, `a`, `b`, `a`.
- `to_string` takes no argument. The returned value is stored in a `std::string`. The serialization has no leading `?`. Form-urlencoded rules apply: a space serializes as `+` (`get` still returns a space, not `+`); a plus serializes as `%2B`; an ampersand in a key or value serializes as `%26`; empty values produce `a=`; an empty key is allowed (`a=&=&=b` after appending `a`/empty, empty/empty, empty/`b`). Non-ASCII values round-trip: appending `é` serializes with `%C3%A9` and `get` returns the original value. `%20` is not used for a space in this serialization.
- `reset` takes one argument (a new query string). It replaces the list, subject to the same length cap as construction. An over-length reset leaves the object empty.
- `get_keys`, `get_values`, and `get_entries` take no argument. Callers walk with `has_next` and `next`. Duplicate keys and values appear once per pair, in list order.

The matching C handle is `hrefparse_url_search_params` (include `hrefparse_c.h`). A handle is obtained from `hrefparse_parse_search_params` and released with `hrefparse_free_search_params`.

## `hrefparse::url_search_params.append`

On `hrefparse::url_search_params`, append is `append`.

### Signature

`append` takes two `std::string` arguments (key, then value).

## `hrefparse::url_search_params.get`

On `hrefparse::url_search_params`, first-value lookup is `get`.

### Signature

`get` takes a `std::string` key. The result is optional-like: callers test `has_value` and then dereference with unary `*`. A missing key is the falsy `has_value` case, distinguishable from a present empty string.

## `hrefparse::url_search_params.get_all`

On `hrefparse::url_search_params`, all-values lookup is `get_all`.

### Signature

`get_all` takes a `std::string` key. The result is vector-like: callers use `size` and index with `[]`. Each element is used as a string.

## `hrefparse::url_search_params.get_entries`

On `hrefparse::url_search_params`, entry iteration is `get_entries`.

### Signature

`get_entries` takes no argument. Callers walk with `has_next` and `next`. `next` is optional-like: callers test `has_value` and then read `first` and `second` as strings.

## `hrefparse::url_search_params.get_keys`

On `hrefparse::url_search_params`, key iteration is `get_keys`.

### Signature

`get_keys` takes no argument. Callers walk with `has_next` and `next`. `next` is optional-like: callers test `has_value` and then dereference with unary `*`.

## `hrefparse::url_search_params.get_values`

On `hrefparse::url_search_params`, value iteration is `get_values`.

### Signature

`get_values` takes no argument. Callers walk with `has_next` and `next`. `next` is optional-like: callers test `has_value` and then dereference with unary `*`.

## `hrefparse::url_search_params.has`

On `hrefparse::url_search_params`, presence is `has`.

### Signature

Callers compile a one-argument form `has` with a `std::string` key and a two-argument form `has` with a `std::string` key and a `std::string` value. Both are used as bool.

## `hrefparse::url_search_params.remove`

On `hrefparse::url_search_params`, remove is `remove`.

### Signature

Callers compile a one-argument form `remove` with a `std::string` key and a two-argument form `remove` with a `std::string` key and a `std::string` value.

## `hrefparse::url_search_params.reset`

On `hrefparse::url_search_params`, reset is `reset`.

### Signature

`reset` takes a `std::string` query.

## `hrefparse::url_search_params.set`

On `hrefparse::url_search_params`, set is `set`.

### Signature

`set` takes two `std::string` arguments (key, then value).

## `hrefparse::url_search_params.size`

On `hrefparse::url_search_params`, pair count is `size`.

### Signature

`size` takes no argument. Callers assign the result to `size_t`.

## `hrefparse::url_search_params.sort`

On `hrefparse::url_search_params`, sort is `sort`.

### Signature

`sort` takes no argument.

## `hrefparse::url_search_params.to_string`

On `hrefparse::url_search_params`, serialize is `to_string`.

### Signature

`to_string` takes no argument. The returned value is stored in a `std::string`.

## `hrefparse::url_search_params_iter`

Include `hrefparse.h`. The C++ search-params iterator template is `url_search_params_iter` in namespace `hrefparse`.

### Signature

```
bool has_next() const;
```

`has_next` takes no argument and is used as bool. Callers walk an iterator returned by `get_keys`, `get_values`, or `get_entries` with a `while` on `has_next`, then call `next` on that same object. `has_next` is true while another item remains.

The keys, values, and entries instantiations are `url_search_params_keys_iter`, `url_search_params_values_iter`, and `url_search_params_entries_iter`.

## `hrefparse_can_parse`

Include `hrefparse.h`. The C++ can-parse entry is `hrefparse::can_parse` in namespace `hrefparse`.

### Signature

```
bool hrefparse::can_parse(std::string_view input);
bool hrefparse::can_parse(std::string_view input, const std::string_view* base_input);
```

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to a `std::string_view` that holds the base URL string, not a parsed URL. Returns bool: yes if and only if parse of the same input and base would succeed, including length-cap rejections. The caller does not have to keep the URL object.

The matching C entry is `hrefparse_can_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer and a `size_t` length. Returns bool.

## `hrefparse_can_parse_with_base`

Include `hrefparse_c.h`. Can-parse with a base on the C interface is `hrefparse_can_parse_with_base`.

### Signature

```
bool hrefparse_can_parse_with_base(const char* input, size_t input_length, const char* base, size_t base_length);
```

Four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length.

Returns yes if and only if `hrefparse_parse_with_base` of the same input and base would succeed.

## `hrefparse_clear_hash`

Include `hrefparse_c.h`. Dedicated hash removal on the C interface is `hrefparse_clear_hash`.

### Signature

```
void hrefparse_clear_hash(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. No return. Call after `hrefparse_is_valid` is true.

Removes the fragment. After a successful call, `hrefparse_get_hash` is empty and `hrefparse_has_hash` is false. Port and search are unchanged: `hrefparse_get_port`, `hrefparse_get_search`, `hrefparse_has_port`, and `hrefparse_has_search` keep their prior values. On a URL whose href contained a fragment such as `hash-exists`, that text is absent from the href afterward.

The matching C++ method is `clear_hash` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_clear_port`

Include `hrefparse_c.h`. Dedicated port removal on the C interface is `hrefparse_clear_port`.

### Signature

```
void hrefparse_clear_port(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. No return. Call after `hrefparse_is_valid` is true.

Removes the port. After a successful call, `hrefparse_get_port` is empty and `hrefparse_has_port` is false. Search and hash are unchanged: `hrefparse_get_search`, `hrefparse_get_hash`, `hrefparse_has_search`, and `hrefparse_has_hash` keep their prior values. On a URL whose href and origin contained a non-default port such as `8080`, that port is absent from both the href and `hrefparse_get_origin` afterward.

The matching C++ method is `clear_port` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_clear_search`

Include `hrefparse_c.h`. Dedicated search removal on the C interface is `hrefparse_clear_search`.

### Signature

```
void hrefparse_clear_search(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. No return. Call after `hrefparse_is_valid` is true.

Removes the query. After a successful call, `hrefparse_get_search` is empty and `hrefparse_has_search` is false. Port and hash are unchanged: `hrefparse_get_port`, `hrefparse_get_hash`, `hrefparse_has_port`, and `hrefparse_has_hash` keep their prior values. On a URL whose href contained a query such as `query=true`, that text is absent from the href afterward.

The matching C++ method is `clear_search` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_free`

Include `hrefparse_c.h`. Handle release is `hrefparse_free`.

### Signature

```
void hrefparse_free(hrefparse_url result);
```

Compile arity is one: an `hrefparse_url` from `hrefparse_parse` or `hrefparse_parse_with_base`.

## `hrefparse_free_owned_string`

Include `hrefparse_c.h`. Owned-string release is `hrefparse_free_owned_string`.

### Signature

```
void hrefparse_free_owned_string(hrefparse_owned_string owned);
```

Compile arity is one: an `hrefparse_owned_string` from `hrefparse_idna_to_ascii` or `hrefparse_idna_to_unicode`.

## `hrefparse_free_search_params`

Include `hrefparse_c.h`. Search-params release on the C interface is `hrefparse_free_search_params`.

### Signature

```
void hrefparse_free_search_params(hrefparse_url_search_params result);
```

Compile arity is one: an `hrefparse_url_search_params` from `hrefparse_parse_search_params`. Every handle returned by that entry is released with this call.

## `hrefparse_free_search_params_entries_iter`

Include `hrefparse_c.h`. Entries-iterator release on the C interface is `hrefparse_free_search_params_entries_iter`.

### Signature

```
void hrefparse_free_search_params_entries_iter(hrefparse_url_search_params_entries_iter result);
```

Compile arity is one: an `hrefparse_url_search_params_entries_iter` from `hrefparse_search_params_get_entries`. Every handle returned by that entry is released with this call.

## `hrefparse_free_search_params_keys_iter`

Include `hrefparse_c.h`. Keys-iterator release on the C interface is `hrefparse_free_search_params_keys_iter`.

### Signature

```
void hrefparse_free_search_params_keys_iter(hrefparse_url_search_params_keys_iter result);
```

Compile arity is one: an `hrefparse_url_search_params_keys_iter` from `hrefparse_search_params_get_keys`. Every handle returned by that entry is released with this call.

## `hrefparse_free_search_params_values_iter`

Include `hrefparse_c.h`. Values-iterator release on the C interface is `hrefparse_free_search_params_values_iter`.

### Signature

```
void hrefparse_free_search_params_values_iter(hrefparse_url_search_params_values_iter result);
```

Compile arity is one: an `hrefparse_url_search_params_values_iter` from `hrefparse_search_params_get_values`. Every handle returned by that entry is released with this call.

## `hrefparse_free_strings`

Include `hrefparse_c.h`. Multi-string release on the C interface is `hrefparse_free_strings`.

### Signature

```
void hrefparse_free_strings(hrefparse_strings result);
```

Compile arity is one: an `hrefparse_strings` from `hrefparse_search_params_get_all`. Every handle returned by that entry is released with this call after the caller has walked it with `hrefparse_strings_size` and `hrefparse_strings_get`.

## `hrefparse_get_hash`

Include `hrefparse_c.h`. The C hash reader is `hrefparse_get_hash`.

### Signature

```
hrefparse_string hrefparse_get_hash(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

When a fragment is present, the view includes a leading `#` (after parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `#hash-exists`). When a fragment is absent, the view is empty.

The matching C++ method is `get_hash` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_host`

Include `hrefparse_c.h`. The C host reader is `hrefparse_get_host`.

### Signature

```
hrefparse_string hrefparse_get_host(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

The view is hostname plus a non-default port when a port is present. After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `www.google.com:8080`. After a host write of `github.com` with no port, the value is `github.com`. When a non-default port is present, this view differs from `hrefparse_get_hostname`: the port appears here and not in hostname.

The matching C++ method is `get_host` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_host_type`

Include `hrefparse_c.h`. Host kind on the C interface is `hrefparse_get_host_type`.

### Signature

```
uint8_t hrefparse_get_host_type(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. The return converts to unsigned. Call after `hrefparse_is_valid` is true.

IPv4 hosts (for example after parsing `http://127.0.0.1/`), IPv6 hosts (for example after parsing `http://[::1]/`), and domain hosts (for example after parsing `https://example.com/` or `https://www.google.com`) produce three mutually distinguishable unsigned values. Two domain hosts share a value. Two IPv4 hosts share a value.

The matching C++ surface is the public member `host_type` on `hrefparse::url_aggregator` (include `hrefparse.h`).

## `hrefparse_get_hostname`

Include `hrefparse_c.h`. The C hostname reader is `hrefparse_get_hostname`.

### Signature

```
hrefparse_string hrefparse_get_hostname(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

## `hrefparse_get_href`

Include `hrefparse_c.h`. The C href reader is `hrefparse_get_href`.

### Signature

```
hrefparse_string hrefparse_get_href(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

## `hrefparse_get_max_input_length`

Include `hrefparse.h`. The C++ length-cap reader is `hrefparse::get_max_input_length`.

### Signature

```
uint32_t hrefparse::get_max_input_length();
```

Compile arity is zero. Returns the process-wide byte cap as `uint32_t`. The default is the maximum 32-bit unsigned integer.

The matching C entry is `hrefparse_get_max_input_length` (include `hrefparse_c.h`). Compile arity is zero. The C return is printed as an unsigned decimal.

## `hrefparse_get_origin`

Include `hrefparse_c.h`. The C origin reader is `hrefparse_get_origin`.

### Signature

```
hrefparse_owned_string hrefparse_get_origin(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_owned_string` (`data`, `length`). The owned string is released with `hrefparse_free_owned_string`. Call after `hrefparse_is_valid` is true. Origin is the owned-string exception among the C component readers; the other named C readers return `hrefparse_string` views.

For a special-scheme URL other than `file:`, the origin is scheme plus host plus non-default port, without credentials, path, query, or fragment. After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `https://www.google.com:8080`. After parsing `https://www.google.com`, the value is `https://www.google.com` (no `:443`).

Opaque origin serializes as `null`. That same token is returned for a `mailto:` URL, a `data:` URL, a `file:` URL with an empty host, and a `file:` URL after a host has been assigned. It is distinguishable from a tuple origin that contains `https` and a hostname, and it does not contain `file://`.

The matching C++ method is `get_origin` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument. Callers store that result in a `std::string`.

## `hrefparse_get_password`

Include `hrefparse_c.h`. The C password reader is `hrefparse_get_password`.

### Signature

```
hrefparse_string hrefparse_get_password(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `password`. When no password is set, the view is empty. The password is not part of `hrefparse_get_origin`.

The matching C++ method is `get_password` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_pathname`

Include `hrefparse_c.h`. The C pathname reader is `hrefparse_get_pathname`.

### Signature

```
hrefparse_string hrefparse_get_pathname(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `/pathname`. After parsing `https://www.google.com` with no path in the input, the value is `/` and the href ends with `/`.

The matching C++ method is `get_pathname` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_port`

Include `hrefparse_c.h`. The C port reader is `hrefparse_get_port`.

### Signature

```
hrefparse_string hrefparse_get_port(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

When a non-default port is present, the view is the decimal port with no colon (after parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `8080`). When no port is set, the view is empty.

The matching C++ method is `get_port` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_protocol`

Include `hrefparse_c.h`. The C protocol reader is `hrefparse_get_protocol`.

### Signature

```
hrefparse_string hrefparse_get_protocol(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

The view is the scheme plus a colon. After parsing `https://www.google.com` or `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `https:`. After a successful protocol write of `wss`, the value is `wss:`.

The matching C++ method is `get_protocol` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_search`

Include `hrefparse_c.h`. The C search reader is `hrefparse_get_search`.

### Signature

```
hrefparse_string hrefparse_get_search(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

When a query is present, the view includes a leading `?` (after parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `?query=true`). When a query is absent, the view is empty.

The matching C++ method is `get_search` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_get_username`

Include `hrefparse_c.h`. The C username reader is `hrefparse_get_username`.

### Signature

```
hrefparse_string hrefparse_get_username(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns `hrefparse_string` (`data`, `length`). Call after `hrefparse_is_valid` is true.

After parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`, the value is `username`. When no username is set, the view is empty. The username is not part of `hrefparse_get_origin`.

The matching C++ method is `get_username` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_has_credentials`

Include `hrefparse_c.h`. Credentials presence on the C interface is `hrefparse_has_credentials`.

### Signature

```
bool hrefparse_has_credentials(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns bool. Call after `hrefparse_is_valid` is true.

True when username or password is non-empty. False after parsing `https://www.google.com`. True after parsing `https://username:password@www.google.com:8080/pathname?query=true#hash-exists`. True after a username write or a password write that leaves a non-empty credential.

The matching C++ method is `has_credentials` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_has_hash`

Include `hrefparse_c.h`. Hash presence on the C interface is `hrefparse_has_hash`.

### Signature

```
bool hrefparse_has_hash(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns bool. Call after `hrefparse_is_valid` is true.

True when a fragment is present, false when it is absent. Independent of port and search: setting only a hash flips this flag and leaves `hrefparse_has_port` and `hrefparse_has_search` unchanged. After parsing `https://www.google.com`, the value is false. After a hash write, the value is true. After `hrefparse_clear_hash`, the value is false.

The matching C++ method is `has_hash` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_has_hostname`

Include `hrefparse_c.h`. Hostname presence on the C interface is `hrefparse_has_hostname`.

### Signature

```
bool hrefparse_has_hostname(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns bool. Call after `hrefparse_is_valid` is true.

True when a host is present, including an empty host. False after parsing `mailto:a@b.com` or `non-special:/x`. True after parsing `https://www.google.com`. True after an empty-host write on `non-special:/x` that yields href `non-special:///x`.

The matching C++ method is `has_hostname` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_has_port`

Include `hrefparse_c.h`. Port presence on the C interface is `hrefparse_has_port`.

### Signature

```
bool hrefparse_has_port(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns bool. Call after `hrefparse_is_valid` is true.

True when a port is present, false when it is absent. Independent of search and hash: setting only a port flips this flag and leaves `hrefparse_has_search` and `hrefparse_has_hash` unchanged. After parsing `https://www.google.com`, the value is false. After a port write of `8080`, the value is true. After `hrefparse_clear_port` or a port write of the empty string, the value is false.

The matching C++ method is `has_port` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_has_search`

Include `hrefparse_c.h`. Search presence on the C interface is `hrefparse_has_search`.

### Signature

```
bool hrefparse_has_search(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. Returns bool. Call after `hrefparse_is_valid` is true.

True when a query is present, false when it is absent. Independent of port and hash: setting only a search flips this flag and leaves `hrefparse_has_port` and `hrefparse_has_hash` unchanged. After parsing `https://www.google.com`, the value is false. After a search write, the value is true. After `hrefparse_clear_search`, the value is false.

The matching C++ method is `has_search` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes no argument.

## `hrefparse_idna_to_ascii`

Include `hrefparse_c.h`. Standalone ToASCII on the C interface is `hrefparse_idna_to_ascii`.

### Signature

```
hrefparse_owned_string hrefparse_idna_to_ascii(const char* input, size_t length);
```

Two arguments: a `const char*` buffer and a `size_t` length. Returns `hrefparse_owned_string`.

A usable domain is handed to the caller only when that owned string has non-null `data` and non-zero `length`. Null `data` or zero `length` is “no usable domain.” The owned string is released with `hrefparse_free_owned_string`.

## `hrefparse_idna_to_unicode`

Include `hrefparse_c.h`. Standalone ToUnicode on the C interface is `hrefparse_idna_to_unicode`.

### Signature

```
hrefparse_owned_string hrefparse_idna_to_unicode(const char* input, size_t length);
```

Two arguments: a `const char*` buffer and a `size_t` length. Returns `hrefparse_owned_string`.

A usable payload is handed to the caller only when that owned string has non-null `data` and non-zero `length`. The owned string is released with `hrefparse_free_owned_string`. ToASCII of that Unicode result uses `hrefparse_idna_to_ascii` on the same `data` and `length`.

## `hrefparse_is_valid`

Include `hrefparse_c.h`. C parse success is `hrefparse_is_valid`.

### Signature

```
bool hrefparse_is_valid(hrefparse_url result);
```

Compile arity is one: `hrefparse_url`. True on a successful parse; false when the handle is not a usable URL. Callers test this before reading `hrefparse_get_href` or `hrefparse_get_hostname`.

## `hrefparse_owned_string`

Include `hrefparse_c.h`. A C owned string is `hrefparse_owned_string`.

### Signature

```
typedef struct {
  const char* data;
  size_t length;
} hrefparse_owned_string;
```

Members are `data` (`const char*`) and `length` (`size_t`). Returned by `hrefparse_idna_to_ascii` and `hrefparse_idna_to_unicode`. Released with `hrefparse_free_owned_string`.

A usable domain is handed to the caller only when `data` is non-null and `length` is non-zero. Null `data` or zero `length` is “no usable domain.”

## `hrefparse_parse`

Include `hrefparse.h`. The C++ parse entry is `hrefparse::parse` in namespace `hrefparse`.

### Signature

```
hrefparse::result<hrefparse::url_aggregator> hrefparse::parse(std::string_view input);
hrefparse::result<hrefparse::url_aggregator> hrefparse::parse(std::string_view input, const hrefparse::url_aggregator* base_url);
```

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to an already-parsed `hrefparse::url_aggregator`, obtained by applying unary `*` to a successful `hrefparse::result` and taking its address (`&*` of the result). Returns `hrefparse::result` of `hrefparse::url_aggregator`.

A successful result converts to true. Components are read through arrow access (`get_href`, `get_hostname`). A failed result is falsy and does not yield a usable URL. When the process-wide length cap would be exceeded by the raw input or the normalized href, parse fails.

The matching C entry is `hrefparse_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. It returns `hrefparse_url`. Every returned handle is released with `hrefparse_free`. Success is observed with `hrefparse_is_valid`.

## `hrefparse_parse_search_params`

Include `hrefparse_c.h`. Search-params construction on the C interface is `hrefparse_parse_search_params`.

### Signature

```
hrefparse_url_search_params hrefparse_parse_search_params(const char* input, size_t length);
```

Two arguments: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. The length is the byte count of that buffer, not a requirement that the buffer be a C string. Returns `hrefparse_url_search_params`.

Every returned handle is released with `hrefparse_free_search_params`.

A leading `?` on the input is a query delimiter and is not stored as part of the first key. Construction honors the process-wide length cap from `hrefparse_set_max_input_length`. An input longer than the cap leaves the object empty (`hrefparse_search_params_size` is 0, `hrefparse_search_params_to_string` is empty). An input whose length equals the cap is accepted. Individual `hrefparse_search_params_append` / `hrefparse_search_params_set` calls are not length-capped.

## `hrefparse_parse_with_base`

Include `hrefparse_c.h`. Relative parse on the C interface is `hrefparse_parse_with_base`.

### Signature

```
hrefparse_url hrefparse_parse_with_base(const char* input, size_t input_length, const char* base, size_t base_length);
```

Four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length. Returns `hrefparse_url`.

Every returned handle is released with `hrefparse_free`. Success is observed with `hrefparse_is_valid`.

The C++ two-argument form of `hrefparse::parse` takes a pointer to an already-parsed `hrefparse::url_aggregator`, not a base string. The C entry takes the base as a string buffer and length.

## `hrefparse_search_params_append`

Include `hrefparse_c.h`. Append on the C interface is `hrefparse_search_params_append`.

### Signature

```
void hrefparse_search_params_append(hrefparse_url_search_params result, const char* key,
                              size_t key_length, const char* value,
                              size_t value_length);
```

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`. No return. Adds a new pair at the end. Appending the same key twice preserves both pairs. Not length-capped.

## `hrefparse_search_params_entries_iter_has_next`

Include `hrefparse_c.h`. Entries-iterator exhaustion on the C interface is `hrefparse_search_params_entries_iter_has_next`.

### Signature

```
bool hrefparse_search_params_entries_iter_has_next(
    hrefparse_url_search_params_entries_iter result);
```

One argument: `hrefparse_url_search_params_entries_iter`. The return is boolean-convertible. True while another pair remains. Callers use it as the `while` condition before `hrefparse_search_params_entries_iter_next`.

## `hrefparse_search_params_entries_iter_next`

Include `hrefparse_c.h`. Entries-iterator advance on the C interface is `hrefparse_search_params_entries_iter_next`.

### Signature

```
hrefparse_string_pair hrefparse_search_params_entries_iter_next(
    hrefparse_url_search_params_entries_iter result);
```

One argument: `hrefparse_url_search_params_entries_iter`. Returns `hrefparse_string_pair`. Callers read `key` and `value` as `hrefparse_string` views (each has `data` and `length`). Call after `hrefparse_search_params_entries_iter_has_next` is true.

## `hrefparse_search_params_get`

Include `hrefparse_c.h`. First-value lookup on the C interface is `hrefparse_search_params_get`.

### Signature

```
hrefparse_string hrefparse_search_params_get(hrefparse_url_search_params result, const char* key,
                                 size_t key_length);
```

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. Returns an `hrefparse_string` view (`data`, `length`). It is the first matching value. Callers distinguish a missing key with `hrefparse_search_params_has` before reading this view. A present empty value is `length` 0 after a true `hrefparse_search_params_has`, distinguishable from a missing key.

## `hrefparse_search_params_get_all`

Include `hrefparse_c.h`. All-values lookup on the C interface is `hrefparse_search_params_get_all`.

### Signature

```
hrefparse_strings hrefparse_search_params_get_all(hrefparse_url_search_params result,
                                      const char* key, size_t key_length);
```

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. Returns `hrefparse_strings`. Callers walk with `hrefparse_strings_size` and `hrefparse_strings_get` (index) as `hrefparse_string` views, then release with `hrefparse_free_strings`. Values are in insertion order. A missing key yields a list whose `hrefparse_strings_size` is 0.

## `hrefparse_search_params_get_entries`

Include `hrefparse_c.h`. Entry iteration on the C interface starts at `hrefparse_search_params_get_entries`.

### Signature

```
hrefparse_url_search_params_entries_iter hrefparse_search_params_get_entries(
    hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_entries_iter`. Callers walk with `hrefparse_search_params_entries_iter_has_next` and `hrefparse_search_params_entries_iter_next`. `hrefparse_search_params_entries_iter_next` returns `hrefparse_string_pair`; callers read `key` and `value` as `hrefparse_string` views. The iterator is released with `hrefparse_free_search_params_entries_iter`. Entries appear once per pair, in list order.

## `hrefparse_search_params_get_keys`

Include `hrefparse_c.h`. Key iteration on the C interface starts at `hrefparse_search_params_get_keys`.

### Signature

```
hrefparse_url_search_params_keys_iter hrefparse_search_params_get_keys(
    hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_keys_iter`. Callers walk with `hrefparse_search_params_keys_iter_has_next` and `hrefparse_search_params_keys_iter_next` (`hrefparse_string`), then release with `hrefparse_free_search_params_keys_iter`. Keys repeat once per pair, in list order.

## `hrefparse_search_params_get_values`

Include `hrefparse_c.h`. Value iteration on the C interface starts at `hrefparse_search_params_get_values`.

### Signature

```
hrefparse_url_search_params_values_iter hrefparse_search_params_get_values(
    hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_values_iter`. Callers walk with `hrefparse_search_params_values_iter_has_next` and `hrefparse_search_params_values_iter_next` (`hrefparse_string`), then release with `hrefparse_free_search_params_values_iter`. Values appear once per pair, in list order.

## `hrefparse_search_params_has`

Include `hrefparse_c.h`. Key presence on the C interface is `hrefparse_search_params_has`.

### Signature

```
bool hrefparse_search_params_has(hrefparse_url_search_params result, const char* key,
                           size_t key_length);
```

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. The return is boolean-convertible. True if any pair has that key. False for a missing key, including when `hrefparse_search_params_get_all` of that key is empty.

## `hrefparse_search_params_has_value`

Include `hrefparse_c.h`. Pair presence on the C interface is `hrefparse_search_params_has_value`.

### Signature

```
bool hrefparse_search_params_has_value(hrefparse_url_search_params result, const char* key,
                                 size_t key_length, const char* value,
                                 size_t value_length);
```

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`. The return is boolean-convertible. True if any pair matches both key and value.

## `hrefparse_search_params_keys_iter_has_next`

Include `hrefparse_c.h`. Keys-iterator exhaustion on the C interface is `hrefparse_search_params_keys_iter_has_next`.

### Signature

```
bool hrefparse_search_params_keys_iter_has_next(
    hrefparse_url_search_params_keys_iter result);
```

One argument: `hrefparse_url_search_params_keys_iter`. The return is boolean-convertible. True while another key remains. Callers use it as the `while` condition before `hrefparse_search_params_keys_iter_next`.

## `hrefparse_search_params_keys_iter_next`

Include `hrefparse_c.h`. Keys-iterator advance on the C interface is `hrefparse_search_params_keys_iter_next`.

### Signature

```
hrefparse_string hrefparse_search_params_keys_iter_next(
    hrefparse_url_search_params_keys_iter result);
```

One argument: `hrefparse_url_search_params_keys_iter`. Returns an `hrefparse_string` view (`data`, `length`). Call after `hrefparse_search_params_keys_iter_has_next` is true.

## `hrefparse_search_params_remove`

Include `hrefparse_c.h`. Remove-by-key on the C interface is `hrefparse_search_params_remove`.

### Signature

```
void hrefparse_search_params_remove(hrefparse_url_search_params result, const char* key,
                              size_t key_length);
```

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. No return. Deletes every pair with that key. Other keys are left in place.

## `hrefparse_search_params_remove_value`

Include `hrefparse_c.h`. Remove-by-key-and-value on the C interface is `hrefparse_search_params_remove_value`.

### Signature

```
void hrefparse_search_params_remove_value(hrefparse_url_search_params result,
                                    const char* key, size_t key_length,
                                    const char* value, size_t value_length);
```

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`. No return. Deletes only pairs that match both key and value. A duplicate of the same key with a different value remains.

## `hrefparse_search_params_reset`

Include `hrefparse_c.h`. Reset on the C interface is `hrefparse_search_params_reset`.

### Signature

```
void hrefparse_search_params_reset(hrefparse_url_search_params result, const char* input,
                             size_t length);
```

Three arguments: `hrefparse_url_search_params`, a `const char*` query, and a `size_t` query length. No return. Replaces the list from that query. Honors the process-wide length cap from `hrefparse_set_max_input_length`: an over-length query leaves the object empty (`hrefparse_search_params_size` 0, serialize empty). A leading `?` is a query delimiter, not part of the first key.

## `hrefparse_search_params_set`

Include `hrefparse_c.h`. Set on the C interface is `hrefparse_search_params_set`.

### Signature

```
void hrefparse_search_params_set(hrefparse_url_search_params result, const char* key,
                           size_t key_length, const char* value,
                           size_t value_length);
```

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`. No return. If the key is already present, replaces the first matching pair’s value, deletes later pairs with that key, and keeps the first pair’s position. If the key is absent, appends a new pair. Not length-capped.

## `hrefparse_search_params_size`

Include `hrefparse_c.h`. Pair count on the C interface is `hrefparse_search_params_size`.

### Signature

```
size_t hrefparse_search_params_size(hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. The return is `size_t`-printable. It is the number of pairs, counting duplicates.

## `hrefparse_search_params_sort`

Include `hrefparse_c.h`. Sort on the C interface is `hrefparse_search_params_sort`.

### Signature

```
void hrefparse_search_params_sort(hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. No return. Orders pairs by key using UTF-16 code-unit comparison (not UTF-8 bytes) and is stable for equal keys. The keys U+1F308 and U+FB03 sort with U+1F308 first. After sorting `z=b&a=b&z=a&a=a`, keys are `a`, `a`, `z`, `z` with values `b`, `a`, `b`, `a`.

## `hrefparse_search_params_to_string`

Include `hrefparse_c.h`. Search-params serialize on the C interface is `hrefparse_search_params_to_string`.

### Signature

```
hrefparse_owned_string hrefparse_search_params_to_string(hrefparse_url_search_params result);
```

One argument: `hrefparse_url_search_params`. Returns `hrefparse_owned_string` (`data`, `length`). The owned string is released with `hrefparse_free_owned_string`.

The serialization has no leading `?`. A space serializes as `+` (a later `hrefparse_search_params_get` of that key still returns a space); a plus serializes as `%2B`; an ampersand in a key or value serializes as `%26`; empty values produce `a=`; an empty key is allowed. Non-ASCII `é` serializes as `%C3%A9`. `%20` is not used for a space in this serialization.

## `hrefparse_search_params_values_iter_has_next`

Include `hrefparse_c.h`. Values-iterator exhaustion on the C interface is `hrefparse_search_params_values_iter_has_next`.

### Signature

```
bool hrefparse_search_params_values_iter_has_next(
    hrefparse_url_search_params_values_iter result);
```

One argument: `hrefparse_url_search_params_values_iter`. The return is boolean-convertible. True while another value remains. Callers use it as the `while` condition before `hrefparse_search_params_values_iter_next`.

## `hrefparse_search_params_values_iter_next`

Include `hrefparse_c.h`. Values-iterator advance on the C interface is `hrefparse_search_params_values_iter_next`.

### Signature

```
hrefparse_string hrefparse_search_params_values_iter_next(
    hrefparse_url_search_params_values_iter result);
```

One argument: `hrefparse_url_search_params_values_iter`. Returns an `hrefparse_string` view (`data`, `length`). Call after `hrefparse_search_params_values_iter_has_next` is true.

## `hrefparse_set_hash`

Include `hrefparse_c.h`. Hash assignment on the C interface is `hrefparse_set_hash`.

### Signature

```
void hrefparse_set_hash(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. No return. Callers compile the call without using a return. Call after `hrefparse_is_valid` is true.

Accepts a value with or without a leading `#`. After either form, `hrefparse_get_hash` includes the delimiter when the fragment is present (writing `is-this-the-real-life` or `#is-this-the-real-life` both yield `#is-this-the-real-life`). There is no separate success flag.

When the write would make the serialized href exceed the process-wide length cap, the URL is left unchanged (same search, hash, and href). There is no separate success flag for that overrun either.

The matching C++ method is `set_hash` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view`.

## `hrefparse_set_host`

Include `hrefparse_c.h`. Host assignment on the C interface is `hrefparse_set_host`.

### Signature

```
bool hrefparse_set_host(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

A host value that includes a port updates hostname and port together (writing `changed-host:9090` makes `hrefparse_get_port` `9090` and leaves that port out of `hrefparse_get_hostname`). Writing `github.com` on `https://www.google.com` makes `hrefparse_get_host` `github.com`.

An empty host on a non-special hierarchical URL that has no authority, such as `non-special:/x`, is accepted and the href becomes `non-special:///x`; `hrefparse_has_hostname` becomes true. A host-parse failure (a literal space in the host, such as `www.google com`) on an authority-less non-special URL such as `non-spec:/x` is refused and must not invent an authority: href stays `non-spec:/x`. `mailto:a@b.com` refuses host writes.

Invalid percent-encoding in a host (`www.google%X%.com`) is refused on a special-scheme URL. On a non-special hierarchical URL that same sequence is accepted as a host, and an authority is inserted if the URL had none.

The matching C++ method is `set_host` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_hostname`

Include `hrefparse_c.h`. Hostname assignment on the C interface is `hrefparse_set_hostname`.

### Signature

```
bool hrefparse_set_hostname(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

Hostname does not consume a port. After a port of `8080` is present, writing `changed-host:9090` as hostname must not make the port `9090`; either the write is refused and the URL is unchanged, or it is accepted without putting `9090` into `hrefparse_get_hostname` and without changing the existing port. A hostname without a port replaces the hostname and leaves the existing port.

An empty hostname on a non-special hierarchical URL that has no authority, such as `sc:/x`, is accepted and the href becomes `sc:///x`; `hrefparse_has_hostname` becomes true. A hostname-parse failure (a literal space) on an authority-less non-special URL such as `non-spec:/x` is refused and must not invent an authority. `mailto:a@b.com` refuses hostname writes.

Invalid percent-encoding in a hostname (`www.google%X%.com`) is refused on a special-scheme URL. On a non-special hierarchical URL that same sequence is accepted as a hostname, and an authority is inserted if the URL had none.

The matching C++ method is `set_hostname` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_href`

Include `hrefparse_c.h`. Href replacement on the C interface is `hrefparse_set_href`.

### Signature

```
bool hrefparse_set_href(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

A successful replacement rebuilds every component from a parse of the new input. Replacing with `https://www.google.com` on a fully qualified Google URL clears username, password, port, search, and hash, sets pathname to `/`, protocol to `https:`, and makes `hrefparse_has_credentials` false. Replacing with `http://0300.168.0xF0` yields href `http://192.168.0.240/` and hostname `192.168.0.240`. An empty string, or `http://www.google com/`, is refused. Invalid percent-encoding in an href path (`http://www.google.com/%X%`) is accepted and `%X%` remains in the href.

The matching C++ method is `set_href` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_max_input_length`

Include `hrefparse.h`. The C++ length-cap writer is `hrefparse::set_max_input_length`.

### Signature

```
void hrefparse::set_max_input_length(uint32_t length);
```

Compile arity is one. The argument is `uint32_t`. The cap is process-wide. It applies to both the raw input and the normalized href (percent-encoding expansion counts), and to `hrefparse::href_from_file`. A parse that would exceed the cap fails. Raising the cap back to the maximum 32-bit unsigned integer restores acceptance of ordinary-length URLs.

The matching C entry is `hrefparse_set_max_input_length` (include `hrefparse_c.h`). Compile arity is one: `uint32_t`.

## `hrefparse_set_password`

Include `hrefparse_c.h`. Password assignment on the C interface is `hrefparse_set_password`.

### Signature

```
bool hrefparse_set_password(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

Writing username `username` and password `password` on `https://www.google.com` yields href `https://username:password@www.google.com/`. Credentials appear in the href and not in `hrefparse_get_origin`. A non-empty password makes `hrefparse_has_credentials` true. Setting password is refused when the URL cannot have credentials (no host), including `mailto:a@b.com` and `non-spec:/x`.

The matching C++ method is `set_password` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_pathname`

Include `hrefparse_c.h`. Pathname assignment on the C interface is `hrefparse_set_pathname`.

### Signature

```
bool hrefparse_set_pathname(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused. Percent-encoding expansion counts against that cap: spaces in the path become `%20`, and a string of spaces that would encode past the cap is refused the same way.

Writing `/my-super-long-path` on `https://www.google.com` makes `hrefparse_get_pathname` `/my-super-long-path`. Setting pathname on an opaque-path URL such as `mailto:a@b.com` is refused.

The matching C++ method is `set_pathname` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_port`

Include `hrefparse_c.h`. Port assignment on the C interface is `hrefparse_set_port`.

### Signature

```
bool hrefparse_set_port(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

Writing `8080` on `https://www.google.com` makes `hrefparse_get_port` `8080` and `hrefparse_has_port` true. Writing the empty string removes the port: `hrefparse_get_port` is empty and `hrefparse_has_port` is false. Setting port on a URL that cannot have a port, such as `mailto:a@b.com`, is refused. Changing protocol from `a://h:0` to a non-special scheme `b` keeps port `0` in the href (`b://h:0`).

The matching C++ method is `set_port` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_protocol`

Include `hrefparse_c.h`. Protocol assignment on the C interface is `hrefparse_set_protocol`.

### Signature

```
bool hrefparse_set_protocol(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

Special scheme to special scheme is accepted: writing `wss` on `https://www.google.com` makes protocol `wss:` and href `wss://www.google.com/`; writing `http` on that result succeeds. Non-special to non-special is accepted: writing `svn` on `git://example.com/` succeeds. Writing `b` on `a://h:0` keeps port `0` (`b://h:0`).

Changing protocol from `https://example.com/` to a non-special scheme such as `foo` is refused; protocol stays `https:`. `file:` with an empty host refuses a protocol change to `https` or to a non-special scheme; after a host such as `google.com` is set, changing protocol to `https` succeeds (`https://google.com/`).

The matching C++ method is `set_protocol` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_set_search`

Include `hrefparse_c.h`. Search assignment on the C interface is `hrefparse_set_search`.

### Signature

```
void hrefparse_set_search(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. No return. Callers compile the call without using a return. Call after `hrefparse_is_valid` is true.

Accepts a value with or without a leading `?`. After either form, `hrefparse_get_search` includes the delimiter when the query is present (writing `target=self` or `?target=self` both yield `?target=self`). There is no separate success flag.

When the write would make the serialized href exceed the process-wide length cap, the URL is left unchanged (same search, hash, and href). There is no separate success flag for that overrun either.

The matching C++ method is `set_search` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view`.

## `hrefparse_set_username`

Include `hrefparse_c.h`. Username assignment on the C interface is `hrefparse_set_username`.

### Signature

```
bool hrefparse_set_username(hrefparse_url result, const char* input, size_t length);
```

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. Returns bool (accepted or refused). Call after `hrefparse_is_valid` is true.

A refused write leaves every named component unchanged. When the write would make the serialized href exceed the process-wide length cap, the write is refused.

Writing username `username` and password `password` on `https://www.google.com` yields href `https://username:password@www.google.com/`. Credentials appear in the href and not in `hrefparse_get_origin`. A non-empty username makes `hrefparse_has_credentials` true. Setting username is refused when the URL cannot have credentials (no host), including `mailto:a@b.com` and `non-spec:/x`.

The matching C++ method is `set_username` on `hrefparse::url_aggregator` (include `hrefparse.h`). It takes a `std::string_view` and returns bool.

## `hrefparse_string`

Include `hrefparse_c.h`. A C view string is `hrefparse_string`.

### Signature

```
typedef struct {
  const char* data;
  size_t length;
} hrefparse_string;
```

Members are `data` (`const char*`) and `length` (`size_t`). Views returned by `hrefparse_get_href` and `hrefparse_get_hostname` remain valid only while the underlying `hrefparse_url` is unchanged.

## `hrefparse_string_pair`

Include `hrefparse_c.h`. An entries pair on the C interface is `hrefparse_string_pair`.

### Signature

```
typedef struct {
  hrefparse_string key;
  hrefparse_string value;
} hrefparse_string_pair;
```

Members are `key` and `value`, each an `hrefparse_string` (`data`, `length`). Returned by `hrefparse_search_params_entries_iter_next`.

## `hrefparse_strings_get`

Include `hrefparse_c.h`. Indexed access into an `hrefparse_strings` list is `hrefparse_strings_get`.

### Signature

```
hrefparse_string hrefparse_strings_get(hrefparse_strings result, size_t index);
```

Two arguments: `hrefparse_strings` from `hrefparse_search_params_get_all`, and a `size_t` index. Returns an `hrefparse_string` view (`data`, `length`). Callers index from 0 up to, but not including, `hrefparse_strings_size`.

## `hrefparse_strings_size`

Include `hrefparse_c.h`. Length of an `hrefparse_strings` list is `hrefparse_strings_size`.

### Signature

```
size_t hrefparse_strings_size(hrefparse_strings result);
```

One argument: `hrefparse_strings` from `hrefparse_search_params_get_all`. The return is `size_t`-printable. Zero when the key is missing.

## `hrefparse_url`

Include `hrefparse_c.h`. The C parse handle is `hrefparse_url`.

### Signature

`hrefparse_url` is an opaque handle. Callers default-construct it (`hrefparse_url url;`) and assign the result of `hrefparse_parse` or `hrefparse_parse_with_base`. Every handle returned by a parse entry is released with `hrefparse_free`. Success is observed with `hrefparse_is_valid` before reading components.

## `hrefparse_url_search_params`

Include `hrefparse.h`. URL Search Params is the type `hrefparse::url_search_params` in namespace `hrefparse`.

### Signature

```
explicit url_search_params(const std::string_view input);
size_t size() const noexcept;
void append(std::string_view key, std::string_view value);
std::optional<std::string_view> get(std::string_view key);
std::vector<std::string> get_all(std::string_view key);
bool has(std::string_view key) noexcept;
bool has(std::string_view key, std::string_view value) noexcept;
void set(std::string_view key, std::string_view value);
void remove(std::string_view key);
void remove(std::string_view key, std::string_view value);
void sort();
std::string to_string() const;
void reset(std::string_view input);
url_search_params_keys_iter get_keys();
url_search_params_values_iter get_values();
url_search_params_entries_iter get_entries();
```

Callers construct `hrefparse::url_search_params` from a `std::string_view` (brace initialization from a `std::string` view is accepted). Compile arity of the constructor is one.

The object is an ordered list of key/value pairs, independent of a full URL. A URL search component (with or without a leading `?`) may be fed as the constructor input. A leading `?` is a query delimiter and is not stored as part of the first key. A key with no `=` has an empty value.

Construction honors the process-wide length cap from `hrefparse::set_max_input_length`. An input longer than the cap leaves the object empty (`size` is 0, `to_string` is empty, `get` of a would-be key has no value, `has` is false, `get_all` is an empty list). An input whose length equals the cap is accepted. Individual `append` / `set` calls are not length-capped: they still add or replace pairs on an object that construction left empty.

- `size` takes no argument. Callers assign the result to `size_t`. It is the number of pairs, counting duplicates.
- `append` takes two arguments (key, then value). It adds a new pair at the end. Appending the same key twice preserves both pairs.
- `get` takes one argument (key). The result is optional-like: callers test `has_value` and then dereference with unary `*`. It returns the first matching value. A missing key is the falsy `has_value` case, distinguishable from a present key whose value is the empty string.
- `get_all` takes one argument (key). The result is vector-like: callers use `size` and index with `[]`. Values are in insertion order. A missing key yields an empty list.
- `has` compiles as a one-argument form (key) and a two-argument form (key, value). Both are used as bool. The one-argument form is true if any pair has that key. The two-argument form is true if any pair matches both key and value.
- `set` takes two arguments (key, then value). If the key is already present, it replaces the first matching pair’s value, deletes later pairs with that key, and keeps the first pair’s position. If the key is absent, it appends a new pair.
- `remove` compiles as a one-argument form (key) and a two-argument form (key, value). One argument deletes every pair with that key. Two arguments deletes only pairs that match both key and value.
- `sort` takes no argument. It orders pairs by key using UTF-16 code-unit comparison (not UTF-8 bytes) and is stable for equal keys. The keys U+1F308 and U+FB03 sort with U+1F308 first. After sorting `z=b&a=b&z=a&a=a`, keys are `a`, `a`, `z`, `z` with values `b`, `a`, `b`, `a`.
- `to_string` takes no argument. The returned value is stored in a `std::string`. The serialization has no leading `?`. Form-urlencoded rules apply: a space serializes as `+` (`get` still returns a space, not `+`); a plus serializes as `%2B`; an ampersand in a key or value serializes as `%26`; empty values produce `a=`; an empty key is allowed (`a=&=&=b` after appending `a`/empty, empty/empty, empty/`b`). Non-ASCII values round-trip: appending `é` serializes with `%C3%A9` and `get` returns the original value. `%20` is not used for a space in this serialization.
- `reset` takes one argument (a new query string). It replaces the list, subject to the same length cap as construction. An over-length reset leaves the object empty.
- `get_keys`, `get_values`, and `get_entries` take no argument. Callers walk with `has_next` and `next`. Duplicate keys and values appear once per pair, in list order.

The matching C handle is `hrefparse_url_search_params` (include `hrefparse_c.h`). A handle is obtained from `hrefparse_parse_search_params` and released with `hrefparse_free_search_params`.

## `istream`

`istream`. This name is not a published Hrefparse entry. Callers may use `std::cin` from the C++ standard library.

### Signature

The member `read` compiles with arity two.

## `iterator`

This name is not a published Hrefparse entry. Caller-side C++ iteration uses `operator++`; Hrefparse does not export a type whose published members are that increment.

### Signature

`operator++` compiles with arity zero.

## `malloc`

`malloc`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is one.

## `memcpy`

`memcpy`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is three.

## `operator`

This name is not a published Hrefparse entry. Caller-side C++ lambdas use `operator()`; Hrefparse does not export a type whose published members are those call operators.

### Signature

Compile arities for `operator()` are one and two. Those arities belong to caller lambdas, not to `hrefparse::parse` or `hrefparse::can_parse`.

## `ostream`

`ostream`. This name is not a published Hrefparse entry. Callers may use `std::cout` from the C++ standard library.

### Signature

Members compile as: `put` arity one; `write` arity two; `operator<<` arity one.

## `read_stdin`

`read_stdin`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arities are zero and one.

## `realloc`

`realloc`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is two.

## `run_session`

`run_session`. This name is not a published Hrefparse entry. It is a helper in a caller program, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Compile arity is ten.

## `snprintf`

`snprintf`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is four.

## `ssse3_percent_tables`

`ssse3_percent_tables`. Not a published Hrefparse parse entry. Callers include `hrefparse.h` or `hrefparse_c.h` and call `hrefparse::parse` / `hrefparse_parse`; they do not call this name.

When defined, it is an internal aggregate. Member names that appear on that aggregate are `cs_hi`, `cs_lo`, `mask_07`, `mask_0f`, `pow2`, and `zero`. Those members are not a published Hrefparse type.

## `strcmp`

`strcmp`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is two.

## `string`

Include `hrefparse.h`. Callers use `std::string` from the C++ standard library.

### Signature

Callers construct `std::string` from a `std::string_view` (including the views returned by `get_href` and `get_hostname`) and store the result of `hrefparse::href_from_file` in a `std::string`. Hrefparse does not re-export this type under another name.

## `strlen`

`strlen`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is one.

## `strtoul`

`strtoul`. This name is not a published Hrefparse entry. Callers include `hrefparse.h` or `hrefparse_c.h`; this name comes from the C or C++ standard library, not from the Hrefparse headers.

### Signature

Compile arity is three.

## `tl::expected`

Include `hrefparse.h`. `hrefparse::result` is `tl::expected` of `hrefparse::url_aggregator`.

### Signature

Boolean conversion (`operator bool`) compiles with arity zero: a successful `hrefparse::result` is true; a failed result is falsy. Callers do not include a separate header to name `tl::expected`; they include `hrefparse.h` and use `hrefparse::result`.

## `url_pattern_input`

Include `hrefparse.h`. `url_pattern_input` is the input type of `test` and `exec`. It is `std::variant` of `std::string_view` and `hrefparse::url_pattern_init`.

### Signature

```
using url_pattern_input = std::variant<std::string_view, hrefparse::url_pattern_init>;
```

Construction compiles with arity one: a `std::string_view` URL string or an `hrefparse::url_pattern_init` converts to `url_pattern_input`. Callers pass those alternatives directly to `test` and `exec`.

## `url_search_params_entries_iter`

Include `hrefparse.h`. The entries iterator type is `url_search_params_entries_iter` in namespace `hrefparse` (`hrefparse::url_search_params_entries_iter`). It is the type returned by `get_entries` on `hrefparse::url_search_params`.

### Signature

```
std::optional<std::pair<std::string_view, std::string_view>> next();
```

`next` takes no argument. Compile arity is zero. The result is optional-like: callers test `has_value` and then read `first` (key) and `second` (value) through arrow access, each stored in a `std::string`. Callers walk with `has_next` before each `next`. Entries appear once per pair, in list order.

The matching C handle is `hrefparse_url_search_params_entries_iter` (include `hrefparse_c.h`).

## `url_search_params_keys_iter`

Include `hrefparse.h`. The keys iterator type is `url_search_params_keys_iter` in namespace `hrefparse` (`hrefparse::url_search_params_keys_iter`). It is the type returned by `get_keys` on `hrefparse::url_search_params`.

### Signature

```
std::optional<std::string_view> next();
```

`next` takes no argument. Compile arity is zero. The result is optional-like: callers test `has_value` and then dereference with unary `*` to obtain the key as a string view, stored in a `std::string`. Callers walk with `has_next` before each `next`. Keys repeat once per pair, in list order.

The matching C handle is `hrefparse_url_search_params_keys_iter` (include `hrefparse_c.h`).

## `url_search_params_values_iter`

Include `hrefparse.h`. The values iterator type is `url_search_params_values_iter` in namespace `hrefparse` (`hrefparse::url_search_params_values_iter`). It is the type returned by `get_values` on `hrefparse::url_search_params`.

### Signature

```
std::optional<std::string_view> next();
```

`next` takes no argument. Compile arity is zero. The result is optional-like: callers test `has_value` and then dereference with unary `*` to obtain the value as a string view, stored in a `std::string`. Callers walk with `has_next` before each `next`. Values appear once per pair, in list order.

The matching C handle is `hrefparse_url_search_params_values_iter` (include `hrefparse_c.h`).

## `usable_regex_provider::entry`

`entry`. This name is not a published Hrefparse entry. It is a local in a caller-supplied engine, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Callers index `std::match_results` and read member `matched`. When `matched` is true they take `str`; when it is false they store `std::nullopt`.

## `usable_regex_provider::flags`

`flags`. This name is not a published Hrefparse entry. It is a local in a caller-supplied engine, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

When the engine’s `create_instance` receives `ignore_case` true, callers form flags as `std::regex::icase` `operator|` `std::regex_constants::ECMAScript`. When that argument is false, the flags are `std::regex_constants::ECMAScript` alone. Those flags are passed to `std::regex`; Hrefparse does not export this name.

## `usable_regex_provider::i`

This name is not a published Hrefparse entry. It is a local in a caller-supplied engine, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Callers walk capture indices of `std::match_results` with a `size_t` loop. Hrefparse does not export this name.

## `usable_regex_provider::match_result`

`match_result`. This name is not a published Hrefparse entry. It is a local in a caller-supplied engine, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

Callers declare `std::match_results` of `std::string_view::const_iterator`. `std::regex_search` fills it. Callers then read `empty`, `size`, and index captures. Hrefparse does not export this name.

## `usable_regex_provider::matches`

`matches`. This name is not a published Hrefparse entry. It is a local in a caller-supplied engine, not a symbol exported from `hrefparse.h` or `hrefparse_c.h`.

### Signature

`regex_search` returns `std::optional` of `std::vector` of `std::optional` of `std::string`. Callers build that vector as `matches`: one inner optional per capturing group, `std::nullopt` when the group did not participate. A missing outer optional is no-match. Hrefparse must accept that return shape from the caller-supplied engine.

## `value_type`

This name is not a published Hrefparse class. It is the C++ item type yielded by iterator `next`, not a symbol exported from `hrefparse.h` or `hrefparse_c.h` under that name.

### Signature

On an entries item, callers read members `first` (key) and `second` (value) and store each in a `std::string`.

On a keys or values item, unary `*` yields a string view. Callers construct a `std::string` from that view. Conversion to `basic_string_view` compiles with arity zero.

