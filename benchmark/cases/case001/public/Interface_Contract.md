# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**Tomlparse** is a Python library that reads TOML text and returns ordinary Python values. It is a parser only: it does not write TOML, and it does not preserve comments, ordering of presentation, or other style. The language this product implements is **TOML v1.1.0**.

A first-time integrator hands Tomlparse a short document such as two array-of-tables items, each with a name and a number, and receives a mapping whose sequence contains those two mappings with a Python string and a Python integer. Leaving the number as a string, accepting a document that TOML v1.1.0 forbids, or returning a custom comment-preserving node instead of a plain mapping is a failure of the product.

The finished product is an **importable Python library**, not a command-line program, not a network service, and not a wire protocol. Integrators install the Tomlparse package and call the published parse entries. There is no dump, write, or encode entry. There is no product-owned configuration file.

The product is a pure-Python library with zero runtime third-party dependencies. Optional compiled wheels may exist on some platforms for speed; they are not required. The language is Python 3.8 or newer, including CPython and PyPy. Platforms are Linux, macOS, and Windows. Hardware is CPU-only.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is the importable package `tomlparse`. Callers write `import `tomlparse`` or `from `tomlparse` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `tomlparse` under `src`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

The independently verifiable library entries, grouped by role, are:

- `loads` — parse one TOML v1.1.0 document from a Python text string into a document mapping, or fail.
- `load` — parse the same language from a binary file object whose bytes are interpreted as `UTF-8`, or fail.
- `TOMLDecodeError` — the documented parse-failure exception. It is a kind of `ValueError`.

Both parse entries accept an optional float converter (keyword `parse_float`) so TOML floats, including `inf` and `nan` spellings, can be built as something other than a Python float. When that converter is omitted, floats are Python floats. The converter does not change table or array structure, and it is not applied to integers, strings, booleans, or date-times.

**Not in this surface.** Encoding or writing TOML. Comment-preserving or style-preserving round-trip parsing. A command-line program, a web server, or a configuration framework. A fallback import of the standard-library TOML module. Parse throughput is not a published interface.

### Naming conventions

**Product and package.** The product identity is Tomlparse. The installable distribution name and the importable top-level package are spelled `tomlparse`.

**Parse entries.** String parse is `loads` (plural). Binary-file parse is `load` (singular). The first argument of `loads` is the document as a Python text string, passed positionally. The first argument of `load` is a file object opened for binary reading. The optional float converter on both entries is the keyword `parse_float`.

**Decode error.** Parse failure of invalid TOML is `TOMLDecodeError`. That name is PascalCase. It is a subclass of `ValueError`. It is not `RecursionError` and it is not `TypeError`.

**TOML keyword spellings.** Boolean values are only the lowercase tokens `true` and `false`. Special float spellings are `inf`, `+inf`, `-inf`, `nan`, `+nan`, and `-nan`. The same four words `true`, `false`, `inf`, and `nan` are valid **keys** when used as bare keys.

**Layout.** The importable package directory is `tomlparse` under `src`.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**No command-line product.** There is no console-script entry and no `python -m` program that is part of this surface. Outcomes are returned or raised from library calls. Parse entries do not exit the host process.

**Library substrate.** When the `tomlparse` package is not importable, a program that does `from `tomlparse` import `loads`` and then calls `loads` on the one-line document `name = "probe"` does not run to completion and does not yield a successful document mapping. When the package is importable, that same document yields a mapping whose `name` value is the string `probe`.

**Document mapping.** A successful parse returns a Python mapping whose keys are strings and whose values are ordinary Python mappings, sequences, and scalars (strings, integers, floats, booleans, and standard-library date, time, and datetime values). The product does not return custom node types in order to keep comments or layout. Integers are integers and not booleans; booleans are booleans and not the integers 1 and 0 and not strings.

**Empty document.** A parse of empty text, of text that is only whitespace, or of text that is only comments succeeds and yields an empty mapping. A document whose only content is the comment `#no newlines at all here` (no line feed) yields an empty mapping. A binary file with no bytes yields the same empty mapping.

**TOML v1.1.0.** The dialect is TOML v1.1.0. Documents that v1.0.0 forbids and v1.1.0 allows are accepted, including newlines and trailing commas in inline tables. A table header must close on the same line. Keys may be bare, quoted as a basic or literal string, or dotted. Letter case is significant. Duplicate keys in the same table are refused. An inline table cannot be mutated after it is built.

**Comments and line endings.** A comment starts at `#` and runs to the end of the line. A hash inside a string is not a comment. Indentation may be spaces or tabs and does not change meaning. A carriage-return/line-feed pair in the input is treated as a single line feed, including inside string values.

**Binary input.** `load` reads a **binary** file object and interprets the bytes as `UTF-8`. A file object opened in text mode is refused with `TypeError`, not `TOMLDecodeError`. Bytes that are not valid `UTF-8` do not yield a document mapping. For the same TOML characters, `load` after `UTF-8` decoding yields the same document mapping as `loads`.

**Wrong Python type versus invalid TOML.** `loads` accepts a Python text string only. Passing a bytes object or a boolean fails with `TypeError`, not `TOMLDecodeError`. The observer can tell “wrong Python type” from “invalid TOML”.

**Decode error.** When the document is not valid TOML, the parse does not succeed and does not deliver a document mapping. The failure is `TOMLDecodeError`, which is a `ValueError`: a caller who handles `ValueError` also handles parse failures, and a caller who handles only `TOMLDecodeError` does not catch unrelated type errors. Wording of the decode-error report is not a compatibility contract. When the problem is at a character inside the document, an observer can recover a 1-based line number and a 1-based column number for that character. When the document ended too early, an observer can tell the failure is at the end of the document. From the same failure, the unformatted reason, the original document text, and a 0-based character offset are each recoverable, separately from the formatted report.

**Recursion versus decode.** An inline array nested 470 levels deep succeeds. An inline table nested 310 levels deep succeeds. A dotted key with 310 parts succeeds. An inline array, inline table, or dotted key nested deeper than the interpreter’s recursion limit fails with `RecursionError` and does not yield a mapping. That failure is not `TOMLDecodeError`. The observer can tell those two failure kinds apart.

**Float converter.** Any callable that accepts the token text and returns a value that is not a dictionary or a list (and not a subtype of either) is allowed as `parse_float`. If the converter returns a dictionary or a list, the parse fails with `ValueError`. That failure is not `TOMLDecodeError`.

## `tomlparse`

The installable distribution and the importable top-level package are both `tomlparse`. Callers declare the interface from this package root (`import `tomlparse`` or `from `tomlparse` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `tomlparse` under `src`.

These names are importable as ``tomlparse`.<name>` and as `from `tomlparse` import <name>`:

- `loads`
- `load`
- `TOMLDecodeError`

Typical import used to parse a TOML string and handle invalid input:

```
from `tomlparse` import `TOMLDecodeError`, `loads`
```

A script that only needs a subset may import that subset, for example `from `tomlparse` import `loads`` or `from `tomlparse` import `TOMLDecodeError``. Binary-file parse is `from `tomlparse` import `load``.

When `tomlparse` is not importable, a program that does `from `tomlparse` import `loads`` does not run to completion and does not yield a document mapping. When the package is importable, `loads` of the one-line document `name = "probe"` yields a mapping whose `name` value is the string `probe`.

## `tomlparse.TOMLDecodeError`

Import `TOMLDecodeError` from the package root `tomlparse` (`from `tomlparse` import `TOMLDecodeError``). Exception class raised when a document is not valid TOML. It is a class (a type), not a factory function and not a string.

### Signature

```
`TOMLDecodeError`(`msg`, `doc`, `pos`)
```

- `msg` — the unformatted reason, as text.
- `doc` — the TOML document text being parsed, as text.
- `pos` — the 0-based character offset into `doc` where parsing failed, as an integer.

A caller can produce the exception by supplying those three values. The resulting failure identifies that place the same way a parse failure does: reason, document, offset, 1-based line, and 1-based column are each recoverable, and the formatted report includes that location. Supplying reason `error parsing`, document `v=1` then a line feed then `[table]` then a line feed then `v='val'`, and offset 13, the recovered line is 3 and the recovered column is 2.

### Inheritance and discrimination

`TOMLDecodeError` is a subclass of `ValueError`. An instance raised for invalid TOML is both a `TOMLDecodeError` and a `ValueError`. It is not a `RecursionError`. A `RecursionError` raised when nesting exceeds the interpreter’s recursion limit is not a `TOMLDecodeError`. A `TypeError` raised for the wrong Python input type (for example a bytes object or a boolean passed to `loads`, or a text-mode file passed to `load`) is not a `TOMLDecodeError`.

### Recoverable location

A raised instance exposes:

- `msg` — the unformatted reason.
- `doc` — the original document text.
- `pos` — the 0-based character offset.
- `lineno` — the 1-based line corresponding to `pos`.
- `colno` — the 1-based column corresponding to `pos`.

These values are recoverable separately from the formatted report that includes the location. Wording of that formatted report is not a compatibility contract. When `pos` is at or past the end of `doc`, an observer can tell the failure is at the end of the document rather than at a line and column in the interior.

### Raised by parse

`loads` and `load` raise `TOMLDecodeError` when the input is not valid TOML v1.1.0. The call does not return a document mapping. Duplicate keys, frozen inline-table mutation, overwrite of a value by a table or array-of-tables header, a missing value, a multiline string used as a key or table name, a header that spans lines or shares its line with a following pair, and other invalid documents fail this way. Nesting past the interpreter’s recursion limit does **not** raise `TOMLDecodeError`; that failure is `RecursionError`.

## `tomlparse.load`

Import `load` from the package root `tomlparse` (`from `tomlparse` import `load``). Parse one TOML v1.1.0 document from a binary file object whose bytes are interpreted as `UTF-8` and return a document mapping, or fail. The file object is passed as the first positional argument.

### Signature

```
`load`(fp, *, `parse_float`=float)
```

- `fp` — an already-open file object for **binary** reading. Passed positionally. The call reads that object’s current contents (a `read` that yields bytes). It does not take a filesystem path as the document. On-disk files opened in binary mode and in-memory binary buffers are both accepted.
- `parse_float` — optional callable that receives the spelling of a TOML float (including `inf` and `nan` tokens) and returns the constructed value. Keyword-only. The default is the builtin `float`. Integers, strings, booleans, and date-times are not passed through this converter. If the converter returns a dictionary or a list (including a subtype of either), the parse fails with `ValueError`, not `TOMLDecodeError`. This keyword applies the same way it applies to `loads`.

### Return shape

On success, returns a mapping whose keys are strings. Nested tables are mappings. Arrays and arrays of tables are sequences (not strings). Successful parses do not return `None` in place of a mapping. An empty file (no bytes) yields an empty mapping (length 0), not `None`.

Integers in the mapping are integers and are not booleans. Booleans are booleans (`True` / `False`) and are not the integers 1 and 0 and not strings. Floats are floats (when `parse_float` is left at the default). Strings are strings.

The call reads from the supplied file object. It does not open a path of its own, does not write files, does not mutate the process environment, and does not exit the host process.

### Same mapping as string parse after UTF-8

The file’s bytes are interpreted as `UTF-8`. For the same TOML characters, `load` after that decoding yields a document mapping equal to `loads` on that text. Every structural and scalar rule of the string-parse entry applies to that decoded text.

- A binary file whose `UTF-8` bytes are `one=1` then a line feed then `two='two'` then a line feed then `arr=[]` yields `one` equal to the integer 1, `two` equal to the string `two`, and `arr` equal to an empty sequence, matching `loads` on that text.
- A two-key root document encoded as `UTF-8` yields those integer and string values and matches `loads` on the same characters.
- A binary file with no bytes yields an empty mapping, the same as empty text through `loads`. An in-memory binary buffer with no bytes is the same empty mapping.
- A carriage-return/line-feed pair in the file is treated as a single line feed. A binary file whose `UTF-8` bytes are `one=1`, a carriage-return/line-feed pair, then `two='two'` parses to those two keys and matches both `loads` on that text and the same document written with line feeds only.
- Multi-byte `UTF-8` letters in keys or string values parse as those Unicode characters and match `loads` on the same characters.
- Two array-of-tables items `[[players]]` then `name = "Lehtinen"` then `number = 26` then `[[players]]` then `name = "Numminen"` then `number = 27` yield `players` as a two-element sequence of mappings, matching `loads`. A runtime pair of double-bracket headers with a shared integer key is the same: a two-element sequence matching `loads`.
- A dotted key `prefix.leaf = n` nested under `prefix` then `leaf` matches `loads`. The dotted spelling of those two parts is not a key of the root.
- A basic string `k = "\e"` yields the string of code point 27. A basic string using `\x` plus two hex digits yields the corresponding character. Both match `loads`.
- An inline table that spans lines and has a trailing comma, `t = {` then a line feed then `c = 1,` then a line feed then `}`, yields `t` as a one-key mapping whose `c` is the integer 1, matching `loads`.

### Text-mode file object

A file object opened in **text** mode is refused with `TypeError`. The call does not return a document mapping. This is not a decode error: the exception is not `TOMLDecodeError`. The observer can tell a wrong file mode from invalid TOML.

That refusal applies to an on-disk file opened as text and to an in-memory text-mode file object, including when the text itself is valid TOML that the same characters would parse through a binary file or through `loads`.

### Bytes that are not valid UTF-8

Bytes that are not valid `UTF-8` do not yield a document mapping. The call does not succeed. Those bytes are not silently treated as some other 8-bit encoding even when that other decoding would be valid TOML.

This includes at least:

- A quoted key whose bytes contain one value in the range 0xA0–0xFF, followed by ASCII ` = 10001` and a line feed.
- A quoted key whose bytes contain a lone 0xC3 (an incomplete two-byte `UTF-8` sequence), followed by the same ASCII assignment.

A neighboring binary file of valid `UTF-8` TOML still succeeds.

### Invalid TOML after a successful UTF-8 decode

When the bytes are valid `UTF-8` but the decoded text is not valid TOML v1.1.0, the call does not return a document mapping. The failure is `TOMLDecodeError`, which is a `ValueError` and is not a `TypeError`. Nesting past the interpreter’s recursion limit fails with `RecursionError` and does not yield a mapping; that exception is not `TOMLDecodeError`.

The recoverable document on that failure is the decoded text, not the raw bytes. The identified place matches `loads` on that same text. That holds for an on-disk binary file and for an in-memory binary buffer. A neighboring binary file of valid `UTF-8` TOML still succeeds.

Documents that fail this way include at least `val=.`, `]] this is invalid TOML [[`, an unclosed basic string `v = "abc`, and duplicate keys `a = 1` then `a = 2`. Two leading line feeds before `val=.` shift the recovered 1-based line from 1 to 3.

### Float converter

A binary file whose `UTF-8` bytes are `precision-matters = 0.982492`, parsed with a converter that builds a standard-library decimal from the token text, binds `precision-matters` to a decimal of the characters `0.982492`, not a binary float. The same file without a converter binds a Python float. A token `inf` is also passed to the converter. In `a = 1` then `b = 1.0`, the integer is not passed through the converter; only the float token is. A custom converter’s return value is the bound value. A converter that returns a dictionary or a list (including a subtype of either) fails with `ValueError`, not `TOMLDecodeError`.

## `tomlparse.loads`

Import `loads` from the package root `tomlparse` (`from `tomlparse` import `loads``). Parse one TOML v1.1.0 document from a Python text string and return a document mapping, or fail. The document is passed as the first positional argument.

### Signature

```
`loads`(s, *, `parse_float`=float)
```

- `s` — the TOML document as a Python text string. Passed positionally. A bytes object, a boolean, a file object, or any other non-text value is refused with `TypeError`, not `TOMLDecodeError`.
- `parse_float` — optional callable that receives the spelling of a TOML float (including `inf` and `nan` tokens) and returns the constructed value. Keyword-only. The default is the builtin `float`. Integers, strings, booleans, and date-times are not passed through this converter. If the converter returns a dictionary or a list (including a subtype of either), the parse fails with `ValueError`, not `TOMLDecodeError`.

### Return shape

On success, returns a mapping whose keys are strings. Nested tables are mappings. Arrays and arrays of tables are sequences (not strings). Successful parses do not return `None` in place of a mapping. An empty document yields an empty mapping (length 0), not `None`.

Integers in the mapping are integers and are not booleans. Booleans are booleans (`True` / `False`) and are not the integers 1 and 0 and not strings. Floats are floats (when `parse_float` is left at the default). Strings are strings.

The call does not read or write files, does not mutate the process environment, and does not exit the host process.

### Empty document and root pairs

- Empty text, whitespace-only text, and comment-only text (with or without a trailing line feed) succeed as an empty mapping. `#no newlines at all here` with no line feed is an empty mapping.
- `one = 1` then a line feed then `two = 'two'` then a line feed then `arr = []` yields `one` equal to the integer 1, `two` equal to the string `two`, and `arr` equal to an empty sequence.
- A single root pair `key = n` yields a one-key mapping whose bound value is that integer, not the decimal spelling of that integer as a string.
- When the package is importable, `name = "probe"` yields a mapping whose `name` value is the string `probe`.

### Keys are strings

- Keys are strings. A bare key `1234` is the string `1234`, not the integer 1234.
- A bare key may contain letters, digits, underscores, and hyphens: `bare_key`, `bare-key`, and `barekey` are three distinct keys.
- Letter case is significant: `name` and `Name` are different keys; a table header `[section]` is a different table from `[Section]`.
- The words `true`, `false`, `inf`, and `nan` are valid keys. A document `false = false` then a line feed then `true = 1` then a line feed then `inf = 100000000` then a line feed then `nan = "ceci n'est pas un nombre"` yields those four string keys with a boolean, an integer, an integer, and a string respectively. The boolean `True`, the boolean `False`, and the float infinity are not keys of that mapping.
- A key may be written as a basic string or as a literal string. A quoted key may be empty: `"" = "blank"` binds the empty string as a key. A quoted key may contain characters a bare key cannot, including `#`, spaces, dots, and non-ASCII letters. The header `["key#group"]` names a table whose key is `key#group`. The quoted key `"with.dot"` is a single key containing a dot, not two dotted parts. A literal quoted key (single quotes) binds the interior text as the key.

### Dotted keys

- A dotted key creates nested mappings. `name.first = "Arthur"` then `"name".'last' = "Dent"` yields a mapping `name` with string keys `first` and `last`. The string `name.first` is not a key of the root.
- Spaces around dots are ignored: `a   .   b  =  1` is the same nesting as `a.b = 1`. The same spacing is allowed in table headers: `[ g . h . i ]` is the same nesting as `[g.h.i]`.
- Intermediate tables created this way may later receive more dotted keys under the same prefix: `apple.type = "fruit"` then `apple.color = "red"` yields one `apple` mapping with both keys.
- An unquoted dotted key `with.dot = 1` nests under `with` then `dot`. A quoted key `"with.dot" = 1` is a single root key. Those two documents are not equal.

### Square-bracket headers

- A table header `[owner]` opens a table. Key/value pairs after that header belong to `owner` until another header appears. Those pairs are not keys of the root.
- A header `[servers.alpha]` creates `servers` if needed and opens `alpha` inside it. Super-tables may be omitted: a document whose first header is `[x.y.z.w]` succeeds and yields nested empty tables `x`, `y`, `z`, and `w`, each containing only the next name in that chain, with the innermost table empty. Declaring a super-table afterwards is allowed: that same document may later contain `[x]` with a sibling key that is not on the omitted chain.
- After dotted keys have created a nested table, a **new sub-table** that was not already opened as a header may still be declared. A document `[fruit]` then `apple.color = "red"` then `apple.taste.sweet = true` then `[fruit.apple.texture]` then `smooth = true` succeeds: `fruit.apple` has `color`, `taste`, and `texture`.

### Arrays of tables

- An array of tables is opened with a double-square-bracket header. Each repetition appends one new mapping to that sequence. A document `[[players]]` then `name = "Lehtinen"` then `number = 26` then `[[players]]` then `name = "Numminen"` then `number = 27` yields `players` as a two-element sequence of mappings.
- Nested arrays of tables attach to the **most recently appended** parent item: two `[[albums]]` items, each followed by two `[[albums.songs]]` items, yield two albums whose `songs` sequences each have two mappings.
- An array-of-tables header may imply parent tables. `[[albums.songs]]` then `name = "Glory Days"` yields `albums` as a mapping (not a sequence) that contains a `songs` sequence of one mapping. After `[[albums]]` then `[[albums.songs]]`, `albums` is a sequence (not a mapping). Those two parent kinds are not the same.
- After `[[a.b]]` then `x = 1`, a later `[a]` then `y = 2` is allowed and yields `a` as a mapping that has both `b` (the sequence) and `y`. After one or more `[[parent-table.arr]]` headers, a later `[parent-table]` may still add a sibling key that is not `arr`.
- After `[[tab.arr]]` then `[tab]`, a later `arr.val1 = 1` is refused: `arr` is a sequence of tables, not a table that can take a dotted key. A sibling key that is not `arr` on that same `[tab]` is allowed.

### Inline tables

- An inline table is a mapping written as a value. `point = { x = 1, y = 2 }` yields `point` as a mapping whose string keys `x` and `y` have integer values 1 and 2. An empty inline table `{ }` (spaces allowed) is an empty mapping.
- Dotted keys work inside inline tables: `{ a.b = 1 }` is a nested mapping `a` containing `b`.
- Inline tables may span lines, may contain comments, and may have a trailing comma after the last pair. `{ c = 1, }` and a brace, a line feed, `c = 1,`, a line feed, and a closing brace are both a one-key mapping. Comments may sit after the opening brace, after commas, and after the closing brace on the same line as other tokens (`{ c = 1, }#comment`). Comment text is not a key of the table or of the root.

### Arrays

- An array is a sequence written in square brackets. `[]` is empty. Arrays may mix types: `[1, 1.1]` is an integer then a float; the second element is not an integer. Arrays may nest: `[ ["gamma", "delta"], [1, 2] ]` is a sequence of two sequences, not a flat four-element sequence.
- Arrays may span lines, may contain comments between elements, and may have a trailing comma: `[1,]` and `[1, 2,]` are valid. Comment text between elements is not an array element.

### Comments, indent, CRLF

- A comment starts at `#` and runs to the end of the line. A hash inside a string is not a comment: `another = "# This is not a comment"` yields that string including the hash.
- A comment may follow a value with no space: `true=true#true` is boolean true for key `true`. Non-ASCII text is allowed in comments and is not a key.
- A comment may follow a table header, an array-of-tables header, and a date-time value. Those comment words are not keys of the document or of the table they follow.
- Indentation may be spaces or tabs and does not change meaning: `k = 1`, two spaces then `k = 1`, and a tab then `k = 1` are the same mapping.
- A carriage-return/line-feed pair in the input is treated as a single line feed, including inside string values. A document that uses only carriage-return/line-feed between two keys parses as those two keys, equal to the same document with line feeds. A carriage return does not remain inside a multiline basic string that used carriage-return/line-feed as line endings.

### Structural refusal

These documents do not return a mapping. The failure is `TOMLDecodeError`, which is a `ValueError` and is not a `RecursionError`. A neighboring document that omits only the illegal part succeeds.

- Duplicate keys in the same table: `a = 1` then `a = 2`. Two `[table]` headers for the same table. A second key of the same name inside one inline table. Duplicate keys under a header table.
- A table already opened by a header cannot be reopened. `[a.b.c]` then `z = 9` then `[a]` then `b.c.t = 9` fails. `[t1]` then `t2.t3.v = 0` then `[t1.t2]` fails. `[fruit]` with `apple.color` set, then a later `[fruit.apple]` header, fails.
- A value cannot be overwritten by a table or array-of-tables header. `a = 1` then `[a.b.c.d]` fails. `a = true` then `[[a]]` fails. An inline table cannot be mutated afterwards: `a = { b = 1 }` then `a.b = 2` fails.
- A key/value pair must have a value. A line `key =` with nothing after the equals (except whitespace or a comment) fails. A line with no key before the equals (`= 1`) fails.
- A pair whose key is a multiline string fails: `"""key""" = 1` and `'''key''' = 1` do not yield a mapping. A table header whose name is a multiline string fails: `["""tbl"""]` and `['''tbl''']`.
- A table header must close on the same line: `[tbl` then a line feed then `]` then `k = 1` fails. A header cannot share its line with a following pair: `[tbl] k = 1` on one line fails.

### Nesting limits

- An inline array nested 470 levels deep (`arr =` then 470 opening brackets then 470 closing brackets) succeeds as a chain of one-element sequences whose innermost sequence is empty.
- An inline table nested 310 levels deep (`key = {` repeated 310 times then 310 closing braces) succeeds as nested mappings under `key` whose innermost mapping is empty.
- A dotted key with 310 parts (`a.a.…a = 1`) succeeds as nested mappings whose leaf integer is 1.
- Intermediate nesting well below those depths also succeeds.
- An inline array, inline table, or dotted key nested deeper than the interpreter’s recursion limit fails with `RecursionError` and does not yield a mapping. That exception is not `TOMLDecodeError`. The same entry still raises `TOMLDecodeError` (not `RecursionError`) for an ordinary invalid document such as a duplicate key.

