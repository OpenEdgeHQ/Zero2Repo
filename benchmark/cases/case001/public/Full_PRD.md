# Tomlparse — Full Product Requirements Document

## Product overview

**Tomlparse** is a Python library that reads TOML text and returns ordinary Python values. It is a parser only: it does not write TOML, and it does not preserve comments, ordering of presentation, or other style. Version 2.4.0 and later of Tomlparse are compatible with **TOML v1.1.0**. That is the language this product implements.

A first-time integrator hands Tomlparse a short document such as two array-of-tables items, each with a name and a number, and receives a mapping whose sequence contains those two mappings with a Python string and a Python integer. Leaving the number as a string, accepting a document that TOML v1.1.0 forbids, or returning a custom comment-preserving node instead of a plain mapping is a failure of the product.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished Tomlparse product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **TOML document** | A Unicode text that the caller treats as one TOML v1.1.0 document. The product parses one document per call. |
| **String-parse entry** | The library entry that accepts TOML as a Python text string and returns a mapping, or fails. |
| **Binary-file parse entry** | The library entry that reads TOML from a binary file object and returns a mapping, or fails. Specified in FP-03. |
| **Document mapping** | The successful result: a Python mapping whose keys are strings and whose values are the native types in FP-01 and FP-02. |
| **Table** | A TOML table. Constructed as a mapping. Includes tables declared with square-bracket headers, tables implied by dotted keys, and inline tables. |
| **Array** | A TOML array. Constructed as a sequence. |
| **Array of tables** | A sequence of mappings built by repeating a double-square-bracket header. |
| **Bare key** | An unquoted key made only of Latin letters, decimal digits, underscores, and hyphens. |
| **Dotted key** | Two or more key parts joined by dots. Each part may be bare or quoted. Dots inside a quoted part are part of that part’s name, not separators. |
| **Inline table** | A table written with curly braces as a value. After it is built, that namespace is frozen. |
| **Offset date-time** | A TOML date-time with a `Z` / `z` suffix or a numeric offset. Constructed as a timezone-aware datetime. |
| **Local date-time** | A TOML date-time with no offset. Constructed as a timezone-naive datetime. |
| **Local date** | A TOML calendar date with no time. Constructed as a date. |
| **Local time** | A TOML clock time with no date. Constructed as a time. |
| **Float converter** | An optional callable the caller supplies so TOML floats (including `inf` and `nan` spellings) are built as something other than a Python float. Specified in FP-05. |
| **Decode error** | The product’s documented parse-failure exception. It is a kind of value error. Specified in FP-04. |
| **Core capability** | A user-observable capability that reflects Tomlparse’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

Tomlparse is a **library**. Integrators reach it by installing the Tomlparse package. There is no command-line product, no writer, and no configuration file of Tomlparse’s own.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- Parse one TOML v1.1.0 document from a Python text string into a document mapping: keys, comments, tables, arrays, arrays of tables, inline tables (FP-01).
- Construct TOML scalars as native Python values: the four string forms, integers in four bases, floats, booleans, and the four date-time kinds (FP-02).
- Parse the same language from a binary file object whose bytes are interpreted as UTF-8 (FP-03).
- Refuse invalid TOML and refuse the wrong Python input type, without returning a document mapping (FP-04).
- Optionally build TOML floats through a caller-supplied converter, with dictionaries and lists forbidden as conversion results (FP-05).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library with zero runtime third-party dependencies. Optional compiled wheels exist on some platforms for speed; they are not required. The default, graded path is the pure-Python parser.
- **Language:** Python 3.8 or newer, including the CPython and PyPy implementations the project tests.
- **Platforms:** Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. No GPU or accelerator is required or claimed. The mandatory execution substrate is a real host that can import tomlparse from this repository’s source tree and parse a one-table document.
- **TOML dialect:** TOML v1.1.0. Behaviors that exist only in older Tomlparse releases (TOML v1.0.0-only, text-mode file objects as parse input) are not this product.
- **Result types:** Successful parses return plain mappings, sequences, and scalars from Python and its standard library. The product does not return custom node types in order to keep comments or layout.
- **Error text:** Wording of decode-error messages is informational. Graded behavior is success versus failure, the exception kind, and (when a parse fails) that the failure identifies the offending place in the document — not a particular sentence.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real Tomlparse behavior matches the described outcomes when a TOML string or binary file is parsed, or when invalid input is refused.
- **Absent / hollow:** Parse always succeeds or always fails; every scalar stays a string; tables are not nested; invalid TOML is accepted; a writer is required to “round-trip”; floats cannot be built as decimals.

Cheaper proxies (a JSON parser, a TOML subset that skips date-times or dotted keys, a hard-coded fixture table, or a comment-preserving toolkit that is not this parser) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces Tomlparse’s parser for a core capability.

**Negative control (library substrate):** When Tomlparse is deliberately not importable in an isolated subprocess (removed from the import path), a parse of the one-line document `name = "probe"` must fail to produce a successful Tomlparse document mapping — a hard assertion, not a skip. When the interpreter is present and the package is imported from this tree, that same document yields a mapping whose `name` value is the string `probe`. Output-equality alone is not proof that the real package ran.

## Non-goals

- Encoding or writing TOML. There is no dump, write, or encode entry. A separate write-only companion project exists for that job; it is not this product.
- Comment-preserving or style-preserving round-trip parsing. A successful parse is a plain mapping of builtin and standard-library values.
- Being a TOML v1.0.0-only parser. This product accepts TOML v1.1.0 documents that v1.0.0 forbids, including newlines and trailing commas in inline tables, the `\e` and `\x` string escapes, and date-times whose seconds are omitted.
- Shipping a command-line program, a web server, or a configuration framework.
- Guaranteeing a particular parse-throughput benchmark. Speed is a design goal, not a graded oracle.
- Treating the benchmark harness, the fuzzer, the profiler, or packaging scripts as product capabilities.
- Treating a fallback import of the standard-library TOML module on Python 3.11+ as a Tomlparse feature. That pattern is integrator guidance for dependency selection; this product’s graded entries are Tomlparse’s own parse entries.

---

## Feature points

### FP-01: Parse TOML document structure from text

**Public entry:** Tomlparse’s string-parse entry. The caller supplies a Python text string. Scalar construction is specified in FP-02. Invalid documents are specified in FP-04. The binary-file entry in FP-03 yields the same document mapping for the same TOML text after UTF-8 decoding. The optional float converter in FP-05 does not change table or array structure.

**Normal behavior:**

- A parse of empty text, of text that is only whitespace, or of text that is only comments succeeds and yields an empty mapping. A document whose only content is the comment `#no newlines at all here` (no line feed) yields an empty mapping.
- A parse of `one = 1` then a line feed then `two = 'two'` then a line feed then `arr = []` yields a mapping with `one` equal to the integer 1, `two` equal to the string `two`, and `arr` equal to an empty sequence.
- Keys are strings. A bare key `1234` is the string `1234`, not an integer. A bare key may contain letters, digits, underscores, and hyphens: `bare_key` and `bare-key` are distinct from each other and from `barekey`. Letter case is significant: `name` and `Name` are different keys; a table header `[section]` is a different table from `[Section]`.
- The words `true`, `false`, `inf`, and `nan` are valid **keys**. A document `false = false` then a line feed then `true = 1` then a line feed then `inf = 100000000` then a line feed then `nan = "ceci n'est pas un nombre"` yields those four keys with a boolean, an integer, an integer, and a string respectively.
- A key may be written as a basic string or as a literal string. A quoted key may be empty: `"" = "blank"` is a binding whose key is the empty string. A quoted key may contain characters a bare key cannot, including `#`, spaces, dots, and non-ASCII letters. The header `["key#group"]` names a table whose key is `key#group`. The quoted key `"with.dot"` is a single key containing a dot, not two dotted parts.
- A dotted key creates nested mappings. `name.first = "Arthur"` then `"name".'last' = "Dent"` yields a mapping `name` with string keys `first` and `last`. Spaces around dots are ignored: `a   .   b  =  1` is the same nesting as `a.b = 1`. The same spacing is allowed in table headers: `[ g . h . i ]` is the same nesting as `[g.h.i]`. Intermediate tables created this way may later receive more dotted keys under the same prefix: `apple.type = "fruit"` then `apple.color = "red"` yields one `apple` mapping with both keys.
- A table header `[owner]` opens a table. Key/value pairs after that header belong to `owner` until another header appears. A header `[servers.alpha]` creates `servers` if needed and opens `alpha` inside it. Super-tables may be omitted: a document whose first (and until then only) header is `[x.y.z.w]` succeeds and yields nested empty tables `x`, `y`, `z`, and `w`. Declaring a super-table afterwards is allowed: that same document may later contain `[x]`.
- After dotted keys have created a nested table, a **new sub-table** that was not already opened as a header may still be declared. A document `[fruit]` then `apple.color = "red"` then `apple.taste.sweet = true` then `[fruit.apple.texture]` then `smooth = true` succeeds: `fruit.apple` has `color`, `taste`, and `texture`.
- An array of tables is opened with a double-square-bracket header. Each repetition appends one new mapping to that sequence. A document `[[players]]` then `name = "Lehtinen"` then `number = 26` then `[[players]]` then `name = "Numminen"` then `number = 27` yields `players` as a two-element sequence of mappings. Nested arrays of tables attach to the **most recently appended** parent item: two `[[albums]]` items, each followed by two `[[albums.songs]]` items, yield two albums whose `songs` sequences each have two mappings. A later single-bracket header whose first part is that array name attaches to the same current item: `[[arr]]` then `[arr.subtab]` then `val = 1` then `[[arr]]` then `[arr.subtab]` then `val = 2` yields `arr` as a two-element sequence whose mappings each contain `subtab`.
- An array-of-tables header may imply parent tables. `[[albums.songs]]` then `name = "Glory Days"` yields `albums` as a mapping that contains a `songs` sequence of one mapping. After `[[a.b]]` then `x = 1`, a later `[a]` then `y = 2` is allowed and yields `a` as a mapping that has both `b` (the sequence) and `y`.
- After one or more `[[parent-table.arr]]` headers, a later `[parent-table]` may still add a sibling key that is not `arr`.
- An inline table is a mapping written as a value. `point = { x = 1, y = 2 }` yields `point` as a mapping whose string keys `x` and `y` have integer values 1 and 2. An empty inline table `{ }` (spaces allowed) is an empty mapping. Dotted keys work inside inline tables: `{ a.b = 1 }` is a nested mapping `a` containing `b`.
- Inline tables may span lines, may contain comments, and may have a trailing comma after the last pair. `{ c = 1, }` and a brace, a line feed, `c = 1,`, a line feed, and a closing brace are both a one-key mapping. Comments may sit after the opening brace, after commas, and after the closing brace on the same line as other tokens (`{ c = 1, }#comment`).
- An array is a sequence written in square brackets. `[]` is empty. Arrays may mix types: `[1, 1.1]` is an integer then a float. Arrays may nest: `[ ["gamma", "delta"], [1, 2] ]` is a sequence of two sequences. Arrays may span lines, may contain comments between elements, and may have a trailing comma: `[1,]` and a bracketed list with a comma before the closing bracket are both valid.
- A comment starts at `#` and runs to the end of the line. A hash inside a string is not a comment: `another = "# This is not a comment"` yields that string including the hash. A comment may follow a value with no space: `true=true#true` is boolean true for key `true`. Non-ASCII text is allowed in comments. A comment may follow a table header, an array-of-tables header, and a date-time value.
- Indentation may be spaces or tabs and does not change meaning.
- A carriage-return/line-feed pair in the input is treated as a single line feed, including inside string values. A document that uses only carriage-return/line-feed between two keys parses as those two keys.

**Boundary / error behavior:**

- Duplicate keys in the same table are refused. `a = 1` then `a = 2` fails. Two `[table]` headers for the same table fail. A second key of the same name inside one inline table fails.
- A table already opened by a header cannot be reopened. Dotted keys that would reopen such a table fail. `[a.b.c]` then `z = 9` then `[a]` then `b.c.t = 9` fails. `[t1]` then `t2.t3.v = 0` then `[t1.t2]` fails. `[fruit]` with `apple.color` set, then a later `[fruit.apple]` header, fails.
- A value cannot be overwritten by a table or array-of-tables header. `a = 1` then `[a.b.c.d]` fails. `a = true` then `[[a]]` fails. An inline table cannot be mutated afterwards: `a = { b = 1 }` then `a.b = 2` fails.
- After `[[tab.arr]]` then `[tab]`, a later `arr.val1 = 1` fails: `arr` is a sequence of tables, not a table that can take a dotted key.
- A key/value pair must have a value. A line `key =` with nothing after the equals (except whitespace or a comment) fails. A line with no key before the equals fails.
- A pair whose key is a multiline string fails: `"""key""" = 1` does not yield a mapping. A table header whose name is a multiline string fails: `["""tbl"""]` then `k = 1` does not yield a mapping.
- A table header must close on the same line: `[tbl` then a line feed then `]` then `k = 1` fails. A header cannot share its line with a following pair: `[tbl] k = 1` on one line fails.
- An inline array nested 470 levels deep succeeds. An inline table nested 310 levels deep succeeds. A dotted key with 310 parts succeeds. An inline array, inline table, or dotted key nested deeper than the interpreter’s recursion limit fails with a recursion error and does not yield a mapping.

**Verifiable oracle:**

- Success: empty or comment-only text is an empty mapping; `one = 1` / `two = 'two'` / `arr = []` matches those three values; `1234` as a key is the string `1234`; `name` and `Name` are distinct; `false = false` and `true = 1` coexist; `"" = "blank"` uses the empty key; `"with.dot"` is one key; `name.first` and `"name".'last'` nest under `name`; `[ g . h . i ]` matches `[g.h.i]`; `[x.y.z.w]` then `[x]` succeeds; `[fruit]` with `apple.color` then `[fruit.apple.texture]` succeeds; two `[[players]]` items yield a two-element sequence; nested `[[albums.songs]]` attach to the current album; `[arr.subtab]` after each `[[arr]]` attaches to that item; `{ x = 1, y = 2 }` is a mapping of string keys to integers; `{ c = 1, }` with a newline and a trailing comma succeeds; `[1,]` and `[1, 1.1]` succeed; `#` in a string is kept; `true=true#true` is boolean true; carriage-return/line-feed between keys is one separator; 310 nested inline tables and 470 nested arrays succeed.
- Failure / absence: every key stays at the root; dotted keys do not nest; array-of-tables items overwrite instead of append; inline tables reject newlines or trailing commas; comments become keys; duplicate keys silently keep the last value; `a = { b = 1 }` then `a.b = 2` succeeds; empty text fails; after `[[tab.arr]]` then `[tab]`, `arr.val1 = 1` succeeds; `"""key""" = 1` succeeds; `[tbl] k = 1` on one line succeeds.

---

### FP-02: Map TOML scalar types to native values

**Public entry:** The same string-parse entry as FP-01 (and the binary-file entry in FP-03). This feature point is the type each TOML scalar becomes in the document mapping. Structure of tables and arrays is FP-01. Default float construction uses Python’s float; a replacement converter is FP-05.

**Normal behavior:**

- **Booleans.** The tokens `true` and `false`, all lowercase, are Boolean true and Boolean false. They are not the integers 1 and 0, and they are not strings.
- **Strings — four forms.**
  - A basic string is wrapped in double quotes on one line. Escapes are processed.
  - A literal string is wrapped in single quotes on one line. The interior is taken as-is: `'\x20 \x09'` is those characters including backslashes, not a decoded space.
  - A multiline basic string is wrapped in three double quotes. A line feed immediately after the opening delimiter is discarded; later line feeds are kept. Escapes are processed. A backslash followed by a line feed, or by spaces or tabs that then reach a line feed, joins the next non-whitespace text with no inserted newline; a document that ends a multiline basic string with a backslash, spaces or tabs, a line feed, and the closing delimiter succeeds and does not keep that trailing whitespace.
  - A multiline literal string is wrapped in three single quotes. A line feed immediately after the opening delimiter is discarded. No escapes are processed. Interior apostrophes are allowed; a value may close with four or five apostrophes so that one or two apostrophes remain in the value. The same four-or-five-delimiter close applies to multiline basic strings with double quotes.
- **Basic-string escapes (finite set).** In basic and multiline-basic strings the following two-character escapes are replaced: backslash-b (backspace), backslash-t (tab), backslash-n (line feed), backslash-f (form feed), backslash-r (carriage return), backslash-e (escape, code point 27), backslash-double-quote, and backslash-backslash. A backslash-x followed by two hex digits, a backslash-u followed by four hex digits, and a backslash-U followed by eight hex digits each insert the Unicode scalar with that code point: `"\x68\x65\x6c\x6c\x6f\x0a"` is `hello` plus a line feed; `"\e"` is a single escape character; `"\u0061"` is `a`; `"\U00000063"` is `c`. Hex digits are case-insensitive. A quoted key may use the same basic-string escapes: `"\u0000"` as a key is a one-character null key, which is a different key from the six-character literal key `'\u0000'`.
- **Integers.** An unsuffixed decimal integer becomes a Python integer: `42`, `+42`, `-42`, `0`, `+0`, and `-0` are integers (the signed zeros are the integer 0). Hexadecimal integers use a `0x` prefix (`0xDEADBEEF`, `0xdead_beef`, `0x0`). Octal integers use a `0o` prefix (`0o755`, `0o7_6_5`). Binary integers use a `0b` prefix (`0b11010110`, `0b1_0_1`). Underscores may separate digits in every base. Prefix letters `x`, `o`, and `b` are lowercase only.
- **Floats (default converter).** A number with a fractional part, an exponent, or both becomes a Python float: `3.14`, `+3.14`, `-3.14`, `0.123`, `3e2`, `3E-2`, `3.1e2`. Underscores may separate digits (`3_141.5927`, `3e1_4`). The special spellings `inf`, `+inf`, `-inf`, `nan`, `+nan`, and `-nan` are floats: positive infinity, negative infinity, and a not-a-number value (a signed NaN token still constructs a NaN).
- **Offset date-time.** A value such as `1979-05-27T07:32:00-08:00` is a timezone-aware datetime whose offset is eight hours behind UTC. A `Z` or `z` suffix is UTC. The separator between date and time may be `T`, `t`, or a space: `1987-07-05 17:45:00Z` and `1987-07-05t17:45:00z` are the same instant. Seconds may be omitted: `1979-05-27 07:32Z` is that hour and minute with second 0. A fractional second of up to six digits is kept as microseconds; further digits are ignored. `1987-07-05T17:45:56.123Z` has 123000 microseconds.
- **Local date-time.** A date-time with no offset, such as `1988-10-27t01:01:01` or `2025-04-18T20:05` (seconds omitted), is a timezone-naive datetime. It is not the same type of value as an offset date-time: an observer can tell the timezone is missing.
- **Local date.** `1988-10-27` is a date with no time. Leap-year dates `2000-02-29` and `2024-02-29` are valid.
- **Local time.** `17:45:00` is a clock time with no date. Seconds may be omitted: `13:37` is 13 hours and 37 minutes. Fractional seconds are allowed: `10:32:00.555`.
- Parsed date-times, dates, and times are ordinary standard-library values: a deep copy of a mapping that contains an offset date-time equals the original mapping.

**Boundary / error behavior:**

- Boolean tokens are only `true` and `false` in lowercase. `True`, `FALSE`, `t`, and `f` are not booleans and, as values, fail (FP-04).
- A decimal integer with a leading zero other than the number zero itself fails: `01` fails; `+01` and `-01` fail. A hex/octal/binary prefix with a capital letter (`0X1`, `0O1`, `0B1`) fails. A leading or trailing underscore, a doubled underscore, a sign on a hex/octal/binary integer, or digits that do not belong to that base, fail.
- A float with a leading zero on the integer part other than a single `0` before the decimal point fails: `03.14`, `+03.14`, and `-03.14` fail. A float that begins with a decimal point fails: `.12345`, `+.12345`, and `-.12345` fail. A token that is only a dot, or that has a trailing dot with no fractional digit, fails as a float.
- An escaped code point that is not a Unicode scalar (a UTF-16 surrogate) fails. An incomplete `\x`, `\u`, or `\U` hex run fails. A backslash in a basic string that is not one of the escapes listed above fails.
- A raw control character other than tab is illegal inside a one-line string: a basic string that contains a raw form-feed character fails. A carriage return that is not part of a carriage-return/line-feed pair is illegal inside a multiline basic string. An unclosed string of any of the four forms fails.
- A calendar value that matches the date-time shape but is not a real date fails: `1988-02-30` as a local date fails; a February 29 on a non-leap year fails. An hour outside 0 through 23, a minute outside 0 through 59, or a second outside 0 through 59 fails: `2006-01-01T24:00:00Z` fails; `17:60:00` as a local time fails; `17:45:60` fails.

**Verifiable oracle:**

- Success: `true` / `false` are booleans; `"hello"` is a string; `'\\x20'` is the four characters backslash, x, 2, 0; a multiline basic string with a line-joining backslash concatenates without a newline; `"\e"` is code point 27; `"\x68\x65\x6c\x6c\x6f\x0a"` is `hello` plus a line feed; `0xDEADBEEF` is the corresponding integer; `0o755` and `0b11010110` are integers; `42` is an integer and `3.14` is a float; `inf` is positive infinity and `nan` is a NaN; `1979-05-27T07:32:00-08:00` is aware; `1988-10-27t01:01:01` is naive; `1988-10-27` is a date; `13:37` is a time with second 0; `2000-02-29` is accepted; `"\u0000"` and `'\u0000'` as keys are two different keys.
- Failure / absence: `true` is the integer 1 or the string `true`; hex integers stay strings; date-times stay strings; `\e` and `\x` are rejected; `01` is accepted as 1; `.12345` is accepted as a float; `03.14` is accepted; `1988-02-30` is accepted; `2006-01-01T24:00:00Z` is accepted; a naive date-time is stored as UTC; seconds-omitted date-times are rejected.

---

### FP-03: Parse TOML from a binary file

**Public entry:** Tomlparse’s binary-file parse entry. The caller passes a file object opened for **binary** reading. The optional float converter in FP-05 applies to this entry the same way it applies to the string-parse entry. Invalid TOML inside the file is specified in FP-04.

**Normal behavior:**

- A binary file whose UTF-8 bytes are `one=1` then a line feed then `two='two'` then a line feed then `arr=[]` parses to the same mapping as the string-parse entry on that text: `one` is 1, `two` is `two`, `arr` is an empty sequence.
- The file’s bytes are interpreted as UTF-8. A binary file whose UTF-8 bytes are `one=1`, a carriage-return/line-feed pair, then `two='two'` parses to those two keys, with the pair treated as one line feed per FP-01. A binary file with no bytes yields an empty mapping, the same as empty text in FP-01.
- Every structural and scalar rule in FP-01 and FP-02 applies to that UTF-8 text. A binary file containing two `[[players]]` tables yields the same sequence as the string-parse entry on the same characters.

**Boundary / error behavior:**

- A file object opened in **text** mode is refused with a type error. The call does not return a document mapping. This is not a decode error: the observer can tell a wrong file mode from invalid TOML.
- Bytes that are not valid UTF-8 do not yield a document mapping. The call does not succeed.
- The string-parse entry does not accept a file object or a bytes object; that refusal is FP-04. This feature point is only the binary-file entry.

**Verifiable oracle:**

- Success: a binary-mode file of `one=1` / `two='two'` / `arr=[]` matches the string-parse of that text; a binary-mode file of a valid TOML v1.1.0 document from FP-01 / FP-02 yields the same mapping as parsing that document as a string; a binary file with no bytes is an empty mapping; a binary file with carriage-return/line-feed between two keys parses those two keys.
- Failure / absence: a text-mode file is accepted; a text-mode file is reported as invalid TOML rather than as a type error; the binary entry cannot parse a document that the string entry parses; non-UTF-8 bytes are silently misread as if they were UTF-8.

---

### FP-04: Reject invalid TOML

**Public entry:** Both parse entries (FP-01 and FP-03). This feature point is what a caller observes when the input is not valid TOML v1.1.0, or is not the Python type that entry accepts. Structural conflicts already named in FP-01 (duplicate keys, frozen inline tables, overwrite) and scalar conflicts already named in FP-02 (illegal integers, illegal dates, illegal escapes) fail in the same way described here.

**Normal behavior:**

- When the document is not valid TOML, the parse does not succeed. Nothing is delivered as a document mapping. The failure is the product’s decode error, which is a kind of value error: a caller who handles value errors also handles parse failures, and a caller who handles only the decode error does not catch unrelated type errors.
- The failure identifies the offending place. When the problem is at a character inside the document, an observer can recover a 1-based line number and a 1-based column number for that character. When the problem is that the document ended too early (for example `fwfw=` with no value before the end), an observer can tell the failure is at the end of the document rather than at a line and column in the interior. From the same failure, the unformatted reason, the original document text, and a 0-based character offset are each recoverable, separately from the formatted report that includes that location.
- Invalid documents that fail include at least the following constructed cases:
  - A document that is only a lone `.`
  - A value that is only `.` after an equals, such as `val=.`
  - A missing value: `fwfw=` at the end of the document
  - An unclosed basic string: `v = "abc`
  - An unclosed literal string
  - An unclosed multiline string
  - An unclosed array: `arr = [1` with no closing bracket
  - An unclosed inline table: `t = { a = 1` with no closing brace
  - A missing comma between array values or between inline-table pairs
  - A table header with no closing `]` or an array-of-tables header with no closing `]]`
  - A comment containing a form-feed character (a raw control character other than tab)
  - A boolean with the wrong letter case: `True` or `FALSE` as a value
  - A capitalized or mixed-case `inf` / `nan` used as a float token
- A caller can also produce the decode error by supplying a reason, the document text, and a 0-based character offset into that document. The resulting failure identifies that place the same way a parse failure does: reason, document, offset, 1-based line, and 1-based column are each recoverable, and the formatted report includes that location. Supplying reason `error parsing`, document `v=1` then a line feed then `[table]` then a line feed then `v='val'`, and offset 13, the recovered line is 3 and the recovered column is 2.

**Boundary / error behavior:**

- The string-parse entry accepts a Python text string only. Passing a bytes object such as `v = 1` encoded as bytes, or passing a boolean, fails with a **type error**, not a decode error. The observer can tell “wrong Python type” from “invalid TOML”.
- The binary-file entry’s refusal of a text-mode file is a type error (FP-03), not a decode error.
- Wording of the decode-error report is not a compatibility contract. Two faithful implementations may phrase the report differently as long as the parse fails, the exception is the decode error, and the location of the failure is identifiable as specified above.
- Recursion failures from FP-01 are recursion errors, not decode errors. The observer can tell those two failure kinds apart.

**Verifiable oracle:**

- Success of this capability means refusal: `]] this is invalid TOML [[` does not return a mapping and raises the decode error; `val=.` fails as a decode error; `v = "abc` (unclosed) fails; `True` as a value fails; `a = 1` then `a = 2` fails; a comment containing a form-feed character fails; a string-parse of bytes fails as a type error; a string-parse of a boolean fails as a type error; supplying the decode error with reason `error parsing`, the three-line document above, and offset 13 yields recovered line 3, column 2.
- Failure / absence: invalid TOML returns a mapping; invalid TOML raises a generic exception that is not the decode error; bytes are silently decoded; `True` is accepted as boolean true; unclosed strings are accepted; type errors and decode errors cannot be told apart; a failed parse still returns a partial mapping.

---

### FP-05: Construct TOML floats with a caller-supplied converter

**Public entry:** The optional float converter on both the string-parse entry and the binary-file parse entry. When the caller does not supply a converter, FP-02’s default (Python float) applies. This feature point does not change integers, strings, booleans, date-times, tables, or arrays.

**Normal behavior:**

- For `precision-matters = 0.982492` and a converter that builds a standard-library decimal from the text it is given, the value of `precision-matters` is a decimal equal to the decimal of the characters `0.982492`, not a binary float of that magnitude.
- Special float tokens are also converted from their spelling: a document with `val=0.1`, `biggest1=inf`, `biggest2=+inf`, `smallest=-inf`, `notnum1=nan`, `notnum2=-nan`, and `notnum3=+nan`, parsed with the decimal converter, yields decimals: `0.1` as a decimal, positive infinity (both `inf` and `+inf`), negative infinity, and NaN values for the three NaN spellings. Each of those values is an instance of the decimal type.
- Integers are not passed through the converter. In `a = 1` then `b = 1.0`, with a decimal converter, `a` remains a Python integer and `b` is a decimal.
- Any callable that accepts the token text and returns a value that is not a dictionary or a list (and not a subtype of either) is allowed.

As background, not a second graded outcome: the standard-library decimal type is the documented practical choice when binary float inaccuracy cannot be tolerated.

**Boundary / error behavior:**

- If the converter returns a dictionary or a list (including a subtype of either), the parse fails with a **value error**. A parse of `f=0.1` with a converter that always returns an empty dictionary fails; a converter that always returns an empty list fails the same way. This is not a decode error: the observer can tell an illegal converter result from invalid TOML.
- A converter that returns a decimal for `0.1` succeeds; the same parse with a converter that returns a dictionary fails.

**Verifiable oracle:**

- Success: `precision-matters = 0.982492` with the decimal converter yields a decimal equal to 0.982492; `inf` / `+inf` / `-inf` / `nan` tokens become decimals of those kinds; `a = 1` stays an integer while `b = 1.0` becomes a decimal; without a converter, `0.982492` is a Python float.
- Failure / absence: the converter is ignored and values stay Python floats; integers are also converted; a converter that returns a dictionary or a list is accepted and the result is treated as a table or array; the illegal-converter failure is reported as a decode error.
