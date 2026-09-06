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

URLPattern is the class template `hrefparse::url_pattern` on the caller-supplied engine. A successful compile is observed by treating `tl::expected` of `hrefparse::url_pattern` as true and then using `operator->`. Callers default-construct that `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`, then assign the return of `hrefparse::parse_url_pattern`. Methods compile as follows. Regexp-group report is `has_regexp_groups`, used as bool. Compiled component pattern strings are `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`, used as `std::string_view`. `test` compiles as `std::string_view` plus a null pointer, and as `hrefparse::url_pattern_init` plus a null pointer; the return is `hrefparse::result` of bool (boolean conversion, then unary `*`). `exec` compiles the same two overloads; the return is `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result` (a failed result is unexpected; empty optional is no-match; filled optional is a match). Callers default-construct those `hrefparse::result` objects, then assign the returns of `test` and `exec`. Callers default-construct `hrefparse::url_pattern_init` and assign protocol, username, password, hostname, port, pathname, search, hash, and `base_url` from `std::string`. Callers default-construct `hrefparse::url_pattern_options` and write public member `ignore_case`. A successful `exec` unwraps `hrefparse::url_pattern_result` with those eight component members, each an `hrefparse::url_pattern_component_result` exposing `input` and `groups` (sized; range-for of pair: `first` name, `second` optional-like with `has_value` then unary `*`). Remaining method-level defaults belong with those symbols.

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

**URLPattern.** C++ parse entry `hrefparse::parse_url_pattern` (function template on the caller-supplied engine). Compiled type `hrefparse::url_pattern`. Initializer `hrefparse::url_pattern_init` (component members protocol, username, password, hostname, port, pathname, search, hash, plus `base_url`). Options `hrefparse::url_pattern_options` (member `ignore_case`). Compile result is `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`; callers default-construct that expected and assign the parse return. Methods: `has_regexp_groups`, `get_protocol`, `get_username`, `get_password`, `get_hostname`, `get_port`, `get_pathname`, `get_search`, `get_hash`, `test`, `exec`. Callers default-construct `hrefparse::result` of bool and `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result`, then assign the returns of `test` and `exec`. Execute result `hrefparse::url_pattern_result` of eight `hrefparse::url_pattern_component_result` members (`input`, `groups`). Engine: `regex_type`; static `create_instance` takes `std::string_view` and bool and returns `std::optional` of `regex_type` (`std::nullopt` is compile failure); static `regex_search` takes `std::string_view` and a const reference to `regex_type` and returns `std::optional` of `std::vector` of `std::optional` of `std::string`; static `regex_match` takes `std::string_view` and a const reference to `regex_type` and returns bool. The compile definition `HREFPARSE_USE_UNSAFE_STD_REGEX_PROVIDER` exposes a `std::regex`-backed provider; it is not a safe default for untrusted patterns.

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

## `hrefparse::can_parse`

Include `hrefparse.h`. The C++ can-parse entry is `hrefparse::can_parse` in namespace `hrefparse`.

### Signature

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to a `std::string_view` that holds the base URL string, not a parsed URL. Returns bool: yes if and only if parse of the same input and base would succeed.

The matching C entry is `hrefparse_can_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer and a `size_t` length.

## `hrefparse::errors`

`hrefparse::parse_url_pattern` returns `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`.

### Signature

Callers default-construct `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`, then assign the return of `hrefparse::parse_url_pattern`. A failed expected is falsy and does not yield a usable pattern. That failure is distinguishable from a compiled pattern whose `test` / `exec` is no-match.

## `hrefparse::href_from_file`

Include `hrefparse.h`. The C++ filesystem-path conversion is `hrefparse::href_from_file`.

### Signature

The argument is `std::string_view`. The returned value is stored in a `std::string`.

When the raw path or the percent-expanded href exceeds the process-wide length cap, the conversion returns `""`. Otherwise the href matches the result of parsing `file://` and assigning that path with `set_pathname` given a `std::string_view`.

## `hrefparse::parse`

Include `hrefparse.h`. The C++ parse entry is `hrefparse::parse` in namespace `hrefparse`.

### Signature

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to an already-parsed `hrefparse::url_aggregator`, obtained by applying unary `*` to a successful `hrefparse::result` and taking its address (`&*` of the result). Returns `hrefparse::result` of `hrefparse::url_aggregator`.

The matching C entry is `hrefparse_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. It returns `hrefparse_url`.

## `hrefparse::parse_url_pattern`

Include `hrefparse.h`. The C++ URLPattern compile entry is `hrefparse::parse_url_pattern`. It is a function template on the caller-supplied engine. URLPattern is not published on the C interface.

### Signature

Callers compile two forms. The first takes `std::string_view`, a pointer to a `std::string_view` base (null when the caller has no base), and a pointer to `hrefparse::url_pattern_options`. The second takes `hrefparse::url_pattern_init`, a null pointer, and a pointer to `hrefparse::url_pattern_options`. Both return `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`. Callers default-construct that expected, then assign the return. A failed expected is falsy and does not yield a usable pattern.

The engine type must expose `regex_type` and these static members. `create_instance` takes `std::string_view` and bool and returns `std::optional` of `regex_type`; returning `std::nullopt` is compile failure. `regex_search` takes `std::string_view` and a const reference to `regex_type` and returns `std::optional` of `std::vector` of `std::optional` of `std::string`. `regex_match` takes `std::string_view` and a const reference to `regex_type` and returns bool.

## `hrefparse::result`

`hrefparse::parse` returns `hrefparse::result` of `hrefparse::url_aggregator`.

A successful result converts to true. Components are read through arrow access (for example `get_href`, `get_hostname`). A successful result is also dereferenceable with unary `*` so that `&*` of that result is a pointer to the `hrefparse::url_aggregator`, which is the already-parsed base passed to two-argument `hrefparse::parse`.

A failed result is falsy and does not yield a usable URL.

Callers default-construct `hrefparse::result` of bool and `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result`, then assign the returns of `test` and `exec`.

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

## `hrefparse::url_pattern`

Include `hrefparse.h`. URLPattern is the class template `hrefparse::url_pattern` on the caller-supplied engine.

### Signature

A successful `hrefparse::parse_url_pattern` is `tl::expected` of `hrefparse::url_pattern` with error type `hrefparse::errors`. Callers default-construct that expected, assign the parse return, treat a successful expected as true, and reach methods through `operator->`.

## `hrefparse::url_pattern.exec`

On a successful `hrefparse::url_pattern`, structured match is `exec`.

### Signature

Callers compile `exec` with `std::string_view` and a null pointer, and with `hrefparse::url_pattern_init` and a null pointer. The return is `hrefparse::result` of `std::optional` of `hrefparse::url_pattern_result`. Callers default-construct that result, then assign the return. A failed result is unexpected after a successful compile. Callers use `operator->` then `has_value`: empty optional is no-match; a filled optional is a match and unwraps `hrefparse::url_pattern_result`. A failed compile has no `exec`. No-match is not a compile error.

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

Callers compile `test` with `std::string_view` and a null pointer, and with `hrefparse::url_pattern_init` and a null pointer. The return is `hrefparse::result` of bool. Callers default-construct that result, then assign the return. A successful result converts to true; callers then dereference with unary `*` for the yes/no. `test` agrees with whether `exec` produced a match. A failed compile has no `test`.

## `hrefparse::url_pattern_component_result`

Each component of `hrefparse::url_pattern_result` is `hrefparse::url_pattern_component_result`.

### Signature

Callers read `input` as a string-like value and `groups` as a sized range. Walking `groups` yields pairs: `first` is the group name; `second` is optional-like (`has_value`, then unary `*`). A bound named group is the `has_value` case; an optional group that does not participate is the falsy `has_value` case.

## `hrefparse::url_pattern_init`

Include `hrefparse.h`. The per-component URLPattern initializer is `hrefparse::url_pattern_init`.

### Signature

Callers default-construct `hrefparse::url_pattern_init` and assign protocol, username, password, hostname, port, pathname, search, hash, and `base_url` from `std::string`. The same type is the first argument of the initializer overload of `hrefparse::parse_url_pattern`, `test`, and `exec`.

## `hrefparse::url_pattern_options`

Include `hrefparse.h`. Compile options for URLPattern are `hrefparse::url_pattern_options`.

### Signature

Callers default-construct `hrefparse::url_pattern_options` and write the public member `ignore_case`. A pointer to that object is the last argument of both `hrefparse::parse_url_pattern` overloads. Ignore-case is a compile-time choice, not a bool on the parse entry itself.

## `hrefparse::url_pattern_result`

A successful `exec` unwraps `hrefparse::url_pattern_result`.

### Signature

`hrefparse::url_pattern_result` has public members `protocol`, `username`, `password`, `hostname`, `port`, `pathname`, `search`, and `hash`. Each is an `hrefparse::url_pattern_component_result`. A successful match includes all eight.

## `hrefparse::url_search_params`

Include `hrefparse.h`. URL Search Params is the type `hrefparse::url_search_params`.

### Signature

Callers construct `hrefparse::url_search_params` from a `std::string_view`.

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

## `hrefparse_can_parse`

Include `hrefparse.h`. The C++ can-parse entry is `hrefparse::can_parse` in namespace `hrefparse`.

### Signature

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to a `std::string_view` that holds the base URL string, not a parsed URL. Returns bool: yes if and only if parse of the same input and base would succeed.

The matching C entry is `hrefparse_can_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer and a `size_t` length.

## `hrefparse_can_parse_with_base`

Include `hrefparse_c.h`. Can-parse with a base on the C interface is `hrefparse_can_parse_with_base`.

### Signature

Four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length.

Returns yes if and only if `hrefparse_parse_with_base` of the same input and base would succeed.

## `hrefparse_free_search_params`

Include `hrefparse_c.h`. Search-params release on the C interface is `hrefparse_free_search_params`.

### Signature

One argument: `hrefparse_url_search_params`. Every handle from `hrefparse_parse_search_params` is released with this call.

## `hrefparse_get_host_type`

Include `hrefparse_c.h`. Host kind on the C interface is `hrefparse_get_host_type`.

### Signature

One argument: `hrefparse_url`. The return converts to unsigned. IPv4, IPv6, and domain hosts produce distinguishable unsigned values.

## `hrefparse_get_origin`

Include `hrefparse_c.h`. Origin on the C interface is `hrefparse_get_origin`.

### Signature

One argument: `hrefparse_url`. Returns `hrefparse_owned_string` (`data`, `length`). The owned string is released with `hrefparse_free_owned_string`.

Other C component getters (`hrefparse_get_href`, `hrefparse_get_protocol`, `hrefparse_get_username`, `hrefparse_get_password`, `hrefparse_get_host`, `hrefparse_get_hostname`, `hrefparse_get_port`, `hrefparse_get_pathname`, `hrefparse_get_search`, `hrefparse_get_hash`) return `hrefparse_string` views. Origin is the owned-string exception among those readers.

## `hrefparse_idna_to_ascii`

Include `hrefparse_c.h`. Standalone ToASCII on the C interface is `hrefparse_idna_to_ascii`.

### Signature

Two arguments: a `const char*` buffer and a `size_t` length. Returns `hrefparse_owned_string`.

A usable domain is handed to the caller only when that owned string has non-null `data` and non-zero `length`. Null `data` or zero `length` is “no usable domain.” The owned string is released with `hrefparse_free_owned_string`.

## `hrefparse_idna_to_unicode`

Include `hrefparse_c.h`. Standalone ToUnicode on the C interface is `hrefparse_idna_to_unicode`.

### Signature

Two arguments: a `const char*` buffer and a `size_t` length. Returns `hrefparse_owned_string`.

A usable payload is handed to the caller only when that owned string has non-null `data` and non-zero `length`. The owned string is released with `hrefparse_free_owned_string`. ToASCII of that Unicode result uses `hrefparse_idna_to_ascii` on the same `data` and `length`.

## `hrefparse_parse`

Include `hrefparse.h`. The C++ parse entry is `hrefparse::parse` in namespace `hrefparse`.

### Signature

The first argument is `std::string_view`. Callers compile a one-argument form and a two-argument form. The second argument is a pointer to an already-parsed `hrefparse::url_aggregator`, obtained by applying unary `*` to a successful `hrefparse::result` and taking its address (`&*` of the result). Returns `hrefparse::result` of `hrefparse::url_aggregator`.

The matching C entry is `hrefparse_parse` (include `hrefparse_c.h`). It is the two-argument form: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. It returns `hrefparse_url`.

## `hrefparse_parse_search_params`

Include `hrefparse_c.h`. Search-params construction on the C interface is `hrefparse_parse_search_params`.

### Signature

Two arguments: a `const char*` buffer (a `char*` pointer is accepted) and a `size_t` length. Returns `hrefparse_url_search_params`.

Every returned handle is released with `hrefparse_free_search_params`.

## `hrefparse_parse_with_base`

Include `hrefparse_c.h`. Relative parse on the C interface is `hrefparse_parse_with_base`.

### Signature

Four arguments: input `const char*`, input `size_t` length, base `const char*`, base `size_t` length. Returns `hrefparse_url`.

Every returned handle is released with `hrefparse_free`. Success is observed with `hrefparse_is_valid`.

## `hrefparse_search_params_append`

Include `hrefparse_c.h`. Append on the C interface is `hrefparse_search_params_append`.

### Signature

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`.

## `hrefparse_search_params_get`

Include `hrefparse_c.h`. First-value lookup on the C interface is `hrefparse_search_params_get`.

### Signature

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. Returns an `hrefparse_string` view (`data`, `length`).

## `hrefparse_search_params_get_all`

Include `hrefparse_c.h`. All-values lookup on the C interface is `hrefparse_search_params_get_all`.

### Signature

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. Returns `hrefparse_strings`. Callers walk with `hrefparse_strings_size` and `hrefparse_strings_get` (index) as `hrefparse_string` views, then release with `hrefparse_free_strings`.

## `hrefparse_search_params_get_entries`

Include `hrefparse_c.h`. Entry iteration on the C interface starts at `hrefparse_search_params_get_entries`.

### Signature

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_entries_iter`. Callers walk with `hrefparse_search_params_entries_iter_has_next` and `hrefparse_search_params_entries_iter_next`. `hrefparse_search_params_entries_iter_next` returns `hrefparse_string_pair`; callers read `key` and `value` as `hrefparse_string` views. The iterator is released with `hrefparse_free_search_params_entries_iter`.

## `hrefparse_search_params_get_keys`

Include `hrefparse_c.h`. Key iteration on the C interface starts at `hrefparse_search_params_get_keys`.

### Signature

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_keys_iter`. Callers walk with `hrefparse_search_params_keys_iter_has_next` and `hrefparse_search_params_keys_iter_next` (`hrefparse_string`), then release with `hrefparse_free_search_params_keys_iter`.

## `hrefparse_search_params_get_values`

Include `hrefparse_c.h`. Value iteration on the C interface starts at `hrefparse_search_params_get_values`.

### Signature

One argument: `hrefparse_url_search_params`. Returns `hrefparse_url_search_params_values_iter`. Callers walk with `hrefparse_search_params_values_iter_has_next` and `hrefparse_search_params_values_iter_next` (`hrefparse_string`), then release with `hrefparse_free_search_params_values_iter`.

## `hrefparse_search_params_has`

Include `hrefparse_c.h`. Key presence on the C interface is `hrefparse_search_params_has`.

### Signature

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length. The return is boolean-convertible.

## `hrefparse_search_params_has_value`

Include `hrefparse_c.h`. Pair presence on the C interface is `hrefparse_search_params_has_value`.

### Signature

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`. The return is boolean-convertible.

## `hrefparse_search_params_remove`

Include `hrefparse_c.h`. Remove-by-key on the C interface is `hrefparse_search_params_remove`.

### Signature

Three arguments: `hrefparse_url_search_params`, a `const char*` key, and a `size_t` key length.

## `hrefparse_search_params_remove_value`

Include `hrefparse_c.h`. Remove-by-key-and-value on the C interface is `hrefparse_search_params_remove_value`.

### Signature

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`.

## `hrefparse_search_params_reset`

Include `hrefparse_c.h`. Reset on the C interface is `hrefparse_search_params_reset`.

### Signature

Three arguments: `hrefparse_url_search_params`, a `const char*` query, and a `size_t` query length.

## `hrefparse_search_params_set`

Include `hrefparse_c.h`. Set on the C interface is `hrefparse_search_params_set`.

### Signature

Five arguments: `hrefparse_url_search_params`, key `const char*`, key `size_t`, value `const char*`, value `size_t`.

## `hrefparse_search_params_size`

Include `hrefparse_c.h`. Pair count on the C interface is `hrefparse_search_params_size`.

### Signature

One argument: `hrefparse_url_search_params`. The return is `size_t`-printable.

## `hrefparse_search_params_sort`

Include `hrefparse_c.h`. Sort on the C interface is `hrefparse_search_params_sort`.

### Signature

One argument: `hrefparse_url_search_params`.

## `hrefparse_search_params_to_string`

Include `hrefparse_c.h`. Search-params serialize on the C interface is `hrefparse_search_params_to_string`.

### Signature

One argument: `hrefparse_url_search_params`. Returns `hrefparse_owned_string` (`data`, `length`). The owned string is released with `hrefparse_free_owned_string`.

## `hrefparse_set_host`

Include `hrefparse_c.h`. Host assignment on the C interface is `hrefparse_set_host`.

### Signature

Three arguments: `hrefparse_url`, a `const char*` buffer, and a `size_t` length. The return is boolean-convertible (accepted or refused). The same compile shape is used by `hrefparse_set_hostname`, `hrefparse_set_protocol`, `hrefparse_set_pathname`, `hrefparse_set_username`, `hrefparse_set_password`, `hrefparse_set_port`, and `hrefparse_set_href`.

`hrefparse_set_search` and `hrefparse_set_hash` take the same three arguments; callers compile those calls without using a return.

## `hrefparse_url_search_params`

Include `hrefparse.h`. URL Search Params is the type `hrefparse::url_search_params`.

### Signature

Callers construct `hrefparse::url_search_params` from a `std::string_view`.

The matching C handle is `hrefparse_url_search_params` (include `hrefparse_c.h`). A handle is obtained from `hrefparse_parse_search_params` and released with `hrefparse_free_search_params`.

