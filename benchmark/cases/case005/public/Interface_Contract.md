# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

`python-envfile` reads key-value pairs from a `.env` file and can set them as environment variables. An application that takes configuration from the process environment can keep a local `.env` file for development instead of exporting every name by hand. When a `.env` file is present, the library loads it; when a name is already in the process environment, that live value stays in control unless the caller asks to override.

A first-time integrator places a `.env` file next to the application, asks the library to load it, and then reads configuration from the process environment as if those names had been exported by the shell. A second, equally supported path is to parse the same file into an in-memory mapping and leave the process environment untouched, so several files can be merged under caller control.

A command-line program named `envfile` is included so operators can list, get, set, and unset bindings in a `.env` file, and so they can run another program with those bindings present in that program’s environment.

The product is a pure-Python library. No compiled extensions, native code, GPU, or accelerator are required. The language is Python 3.10 or newer. Intended platforms are Linux, macOS, and Windows; Unix FIFOs are a Unix-only source. Hardware is CPU-only.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The product is an **importable Python library** plus an optional **command-line program**. It is not a network service and not a wire protocol.

**Distribution and import.** The installable distribution name is `python-envfile`. The importable top-level package is `envfile`. Callers write `import `envfile`` or `from `envfile` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `envfile` under `src`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

**Library.** The independently verifiable library entries, grouped by role, are:

- Parse a `.env` source into a mapping without mutating the process environment: `envfile_values`.
- Locate a `.env` file by walking from a starting directory up to the filesystem root: `find_envfile`.
- Parse a `.env` source and write recognized values into the process environment: `load_envfile`.
- Write one named binding into a `.env` file: `set_key`.

The caller may pass a file path, an in-memory text stream, or neither (in which case `find_envfile` locates a `.env` file). The same `.env` file format is consumed by load, by the values-mapping entry, by file write, and by the command-line program.

**Command-line program.** The program is named `envfile` and is also reachable as a Python module invocation of the installed package (`python -m `envfile``). Installing `python-envfile` without the `cli` extra leaves this program unable to run subcommands. With that extra present, operators use `list`, `get`, `set`, `unset`, and `run`. The CLI’s default file is `.env` in the current working directory; it does **not** walk ancestors. Exact flags, subcommand outcomes, and process exit codes belong with that program’s entries if specified; they are not a separate product.

**Not in this surface.** Typed settings objects, layered YAML/TOML, remote secret stores, a web server, a GUI, and a cloud control plane are out of scope. An IPython line magic and a helper that renders a `envfile …` shell string for remote task runners are out of scope.

### Naming conventions

**Product and package.** The product identity is `python-envfile`. The import package, the command-line program, and the module invocation name are spelled `envfile`.

**Default file.** The default file name is `.env`.

**Library entries.** Values mapping is `envfile_values`. File location is `find_envfile`. Load into the process environment is `load_envfile`. Write one binding is `set_key`.

**Keywords on the parse and load entries.** A file path is `envfile_path`. An in-memory text stream is `stream`. POSIX-style expansion inside values is `interpolate` (on by default; pass false to leave dollar-brace text literal). Load’s “replace names already in the process environment” switch is `override` (off by default). A named character encoding is `encoding`. Extra missing-file reporting on load is `verbose`.

**Keywords on file location.** The searched base name is `filename` (default `.env`). Fail-if-missing is `raise_error_if_not_found`. Start-from-working-directory is `usecwd`.

**Keywords on file write.** Quote mode is `quote_mode`: `always`, `never`, or `auto` (default `always`). An `export ` line prefix is `export` (off by default). Whether to follow a symbolic link at the path is `follow_symlinks` (off by default).

**File-format directive.** A line may begin with the `export` directive; that word is not part of the binding name.

**Disable switch.** Load is gated by the process-environment name `PYTHON_ENVFILE_DISABLED`.

**CLI extra.** The extra that enables the program is `cli` (install as `python-envfile[cli]`).

**CLI global flags.** `--file` / `-f` (path of the `.env` file), `--quote` / `-q` (`always`, `never`, or `auto`), `--export` / `-e`, `--version`.

**CLI subcommands.** `list`, `get`, `set`, `unset`, `run`. `list` accepts `--format` with `simple`, `json`, `shell`, or `export`. `run` accepts `--override` and `--no-override`.

**CLI list formats.** `simple` (default), `json`, `shell`, `export`.

### Global observables an implementer must reproduce

**Default file name.** When the caller supplies neither a path nor a stream, the library locates and reads `.env`. A sibling file with a different name is not that default source.

**Character encoding.** Unless the caller names a different encoding, `.env` files are read and written as `utf-8`.

**Load default versus `run` default.** Library load does **not** override names already present in the process environment. The `envfile` `run` subcommand **does** override by default. Those two defaults differ.

**Expansion.** By default, load and the values-mapping entry expand the braced forms `${NAME}` and `${NAME:-default}`. Bare `$NAME` (no braces) is not expansion. Passing `interpolate` as false leaves every dollar-brace sequence as ordinary text in the parsed value. Until expansion runs, a dollar-brace sequence is ordinary text.

**Disable switch (load only).** When the process environment already contains `PYTHON_ENVFILE_DISABLED` with a value that, after folding letter case, is one of `1`, `true`, `t`, `yes`, or `y`, `load_envfile` does not read the file or stream and does not write any names from that source. Any other value of that variable, including empty text, `0`, `false`, `no`, `f`, `n`, or the variable being absent, leaves loading enabled. A `.env` file that itself contains `PYTHON_ENVFILE_DISABLED=true` does **not** disable the load that is reading it. The values-mapping entry is not gated by this switch.

**Library substrate.** When the `envfile` package is not importable, a program that does `from `envfile` import `load_envfile`` does not run to completion. When the package is importable, loading a stream `PROBE=from_stream` writes `PROBE` with value `from_stream` into the process environment.

**CLI extra.** Without the `cli` extra, invoking the program does not run subcommands, the operator-visible report identifies that `python-envfile` was not installed with the CLI extra, and the process exits unsuccessfully.

**No product-owned process exit on the library path.** `envfile_values`, `find_envfile`, `load_envfile`, and `set_key` report outcomes by returning a value or raising. They do not exit the host process. Warning wording and exception types that are not named below are not pinned.

**Unix FIFO.** On Unix, a FIFO (named pipe) whose contents are one or more bindings in this format is a valid `.env` source for load and for file location. A reader that only accepts a regular disk file, and cannot consume a FIFO, does not implement this format’s Unix source.

#### Shared `.env` file format

This format is the shared source for `envfile_values`, `load_envfile`, file write, and the command-line program.

**Names, values, whitespace.** A line `DOMAIN=example.org` is one binding whose name is `DOMAIN` and whose value is `example.org`. Spaces around the name, the equals sign, and the value are ignored: a line ` a = b ` is the same binding as `a=b`. Names may be unquoted or wrapped in single quotes. `'a'=b` is a binding named `a` with value `b`. An unquoted name may include characters such as `[`, `%`, and `$`. A line `uglyKey[%$="secret"` is a binding named `uglyKey[%$` with value `secret`. An unquoted name may not contain an equals sign, a hash, or whitespace: a line `a b=c` is not a binding named `a b` and not a binding named `a`; a line `a#b=c` is not a binding named `a#b`.

**Quoted and unquoted values.** Values may be unquoted, single-quoted, or double-quoted. Single quotes and double quotes preserve interior spaces, including trailing spaces: `a='b c '` and `a="b c "` both yield the value `b c ` (space after `c`). An unquoted value may contain spaces and other interior whitespace: `a=b c` yields `b c`; `a=b` then a tab then `c` yields a value with that tab between `b` and `c`. Trailing whitespace on an unquoted value is stripped: `a=b c ` and `a=b c` then a trailing tab both yield `b c`.

**`export` directive.** A line may begin with the `export` directive. `export a=b` and ` export 'a'=b` are the same binding as `a=b`. The directive does not change interpretation and is not part of the name. A name that itself starts with `export` is not eaten as a directive: `export export_a=1` is a binding named `export_a` with value `1`; `export port=8000` is a binding named `port` with value `8000`.

**Comments.** A line whose first non-space character is `#` is a comment and is not a binding. Several comment lines in a row are all comments. A value may be followed by a comment when whitespace separates the value from `#`: `a=b #c` is name `a`, value `b`. A hash that is glued to the value is part of the value: `a=b#c` is name `a`, value `b#c`. A tab before `#` also starts a comment: `a=b` then a tab then `#c` is value `b`. A hash inside a quoted value is value text: `a="hello #world"` and `a='hello #world'` both yield `hello #world`.

**Single-quoted escapes.** Allowed escape sequences in a single-quoted value are a backslash followed by a backslash, and a backslash followed by a single quote. `a='b\'c'` yields `b'c`. `a='b\\c'` yields the three characters `b`, `\`, `c` (one backslash). A backslash followed by `n` inside single quotes is **not** a newline: `a='b\nc'` yields the four characters `b`, `\`, `n`, `c`.

**Double-quoted escapes.** Allowed escape sequences in a double-quoted value are a backslash followed by a backslash, a single quote, a double quote, `a`, `b`, `f`, `n`, `r`, `t`, or `v`. Each listed escape decodes to a single character and is not the two-character literal backslash-plus-letter. `a="b\nc"` yields `b`, newline, `c`. `a="b\"c"` yields `b"c`. A backslash followed by `\\` is a backslash; a backslash followed by `'` is a single quote. For the letters `a`, `b`, `f`, `r`, `t`, and `v`, the decoded character is not that letter itself. A backslash followed by an unlisted letter (for example `q`) is not a listed escape; surrounding text on either side of that sequence remains in the value. Exact code points for unlisted letters, and for listed letters other than `n` (newline) and `"` (double quote) plus `\\` and `'`, are not pinned.

**Quoted values spanning lines.** A single-quoted or double-quoted value may span multiple lines. A double-quoted value whose interior contains a real newline between `first line` and `second line` is equivalent to a double-quoted value whose interior contains the two-character escape `\n` between those phrases; both yield a value with a newline between the two phrases. The same pair of forms is valid with single quotes for a real interior newline; the `\n` escape form is **not** equivalent under single quotes. After the closing quote, a later valid line is a separate binding. An assignment-shaped phrase inside a still-open quoted value is value text, not a second binding.

**No-value versus empty string.** A line that is only the name `FOO` (no equals sign) is a binding named `FOO` with **no value**. This is not the same as `FOO=`, which is a binding named `FOO` whose value is the empty string. No-value, empty string, and absence of the name are three distinct outcomes. `FOO=` is not an error; a later valid line in the same source is still recognized.

**Line separators, blank lines, BOM, Unicode.** Bindings may be separated by a line feed, a carriage return, or a carriage-return/line-feed pair. `a=b` then a carriage return then `c=d` is two bindings. A blank line between bindings is not itself a binding and does not drop the surrounding names. A leading UTF-8 byte-order mark is ignored: a stream or file that begins with a byte-order mark and then `a=b` is the same as a source that is only `a=b`; the mark is not part of the first name. Unicode text in names and values is preserved: `a=à` and `a="à"` both yield value `à`.

**Streams and files.** The same source text yields the same bindings when parsed from an in-memory text stream and when parsed from a file decoded as `utf-8`.

**Invalid lines.** A line that is not a valid binding does not contribute a name. `a: b` (colon instead of equals) is not a binding. A later valid line in the same source is still recognized: a source whose first line is an unclosed double quote `a="` and whose second line is `b=c` yields the binding `b=c` and does not yield `a`. An empty source, a source of only blank lines, or a source of only comments yields no bindings. A YAML-style mapping (`host:` then indented `name:` / `port:`) and a JSON object (`{"DOMAIN":"example.org"}`) are not bindings; a later valid `NAME=value` line in the same source is still recognized.

## `envfile`

The installable distribution is `python-envfile`. The importable top-level package is `envfile`. Callers declare the interface from this package root (`import `envfile`` or `from `envfile` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `envfile` under `src`.

These names are importable as ``envfile`.<name>` and as `from `envfile` import <name>`:

- `envfile_values`
- `find_envfile`
- `load_envfile`
- `set_key`

Typical import used to parse, locate, load, and write:

```
from `envfile` import `envfile_values`, `find_envfile`, `load_envfile`, `set_key`
```

A script that only needs a subset may import that subset, for example `from `envfile` import `envfile_values`` or `from `envfile` import `load_envfile``.

## `envfile.envfile_values`

Import `envfile_values` from the package root `envfile` (`from `envfile` import `envfile_values``). Parse a `.env` source and return the bindings as a mapping, without writing them into the process environment.

### Signature

```
`envfile_values`(`envfile_path`=None, `stream`=None, `verbose`=False, `interpolate`=True, `encoding`="utf-8")
```

- `envfile_path` — absolute or relative path of a `.env` file or Unix FIFO, as text or a path-like object, or `None`. `None` (the default) means no path was supplied.
- `stream` — in-memory text stream (for example `io.StringIO`) whose contents are `.env` text, or `None`. Used when no readable path is available. `None` (the default) means no stream was supplied.
- `verbose` — whether to emit a missing-file diagnostic. Default `False`.
- `interpolate` — whether to expand `${NAME}` / `${NAME:-default}` in values. Default `True`. Pass `False` to leave dollar-brace sequences as ordinary text.
- `encoding` — encoding used to decode a file. Default `"utf-8"`. When the caller does not name an encoding, the file is decoded as `utf-8`.

If both `envfile_path` and `stream` are `None`, `find_envfile` is used to locate a `.env` file with its default parameters, and that file is parsed.

If `envfile_path` names a readable regular file or Unix FIFO, that path is read even when a stream was also supplied. If the path is absent or is not a readable file or FIFO, and a stream was supplied, the stream is read.

### Return shape

Returns a mapping from binding name (text) to recorded value. Membership is `name in mapping`; the recorded value is `mapping[name]`. An empty source yields a mapping whose list of keys is empty.

- A name with a text value is present; `mapping[name]` is that text after quoting, escapes, and (when `interpolate` is true) expansion.
- A name whose source line is `NAME=` (equals, then end of line) is present with the empty string.
- A name whose source line is only the name (no equals) is present and has **no value**: the recorded carrier is distinguishable from the empty string and from absence. Absence is `name not in mapping`, not a failed lookup. The carrier is not pinned to a particular language sentinel.
- A name that did not appear as a valid binding is absent.

The process environment is not modified: a name that was absent stays absent; a name that was present keeps its previous value.

### Source selection and completion

- A missing path yields an empty mapping. The call completes; the caller is not aborted.
- An empty file, a file of only blank lines, or a file of only comments yields an empty mapping. The call completes.
- The disable switch `PYTHON_ENVFILE_DISABLED` does **not** apply: with that variable set in the process environment, a file `a=b` still yields a mapping with `a=b`, and the process environment still does not gain `a` from this entry.
- When neither path nor stream is supplied, the default file name is `.env`. A sibling file with another name is not read.

### Parse

The shared `.env` file format (names, quoting, comments, `export`, multiline quoted values, no-value versus empty string, line separators, byte-order mark, Unicode, invalid-line skipping, UTF-8 files, streams, and Unix FIFOs) applies. A stream and a file of the same text yield the same bindings.

### Expansion

When `interpolate` is `False`, every dollar-brace sequence is returned literally, including `${NAME}` and `${NAME:-default}`, even when `NAME` is set. Bare `$NAME` without braces is left unchanged whether expansion is on or off.

When `interpolate` is left on (the default), only the braced forms `${NAME}` and `${NAME:-default}` are expanded. Resolution order is override-on: for each `${NAME}`, the first defined of (1) that name’s value already computed from an earlier binding in this same source, (2) that name in the process environment, (3) the default if one was written, (4) empty text. Quotes do not suppress expansion. A name present with no value is not unset: in `${NAME:-default}` the default is used only when the name is absent. A binding with no value is not expanded (it stays no-value in the mapping).

## `envfile.find_envfile`

Import `find_envfile` from the package root `envfile` (`from `envfile` import `find_envfile``). Walk from a starting directory toward the filesystem root and return the first matching `.env` path.

### Signature

```
`find_envfile`(`filename`=".env", `raise_error_if_not_found`=False, `usecwd`=False)
```

- `filename` — base name to search for. Default `".env"`. A custom name is searched under that name, not under `.env`. A tree that contains only `.env` does not satisfy a search for a different name, and a tree that contains only that other name does not satisfy a default `.env` search.
- `raise_error_if_not_found` — when `False` (the default), a walk that finds no match returns empty text (no path). When `True`, a walk that finds no match does not succeed and no path is delivered. An observer can tell those two requests apart. A missing file with this flag off is empty text, not a pretended path.
- `usecwd` — when `True`, the starting directory is the current working directory. Default `False`.

### Return shape

When a matching file exists, the result is the path to that file as text. When none exists after walking to the root and `raise_error_if_not_found` is `False`, the result is empty text. The result is not `None` as a stand-in for “not found”.

A matching path is a regular file or (on Unix) a FIFO whose base name is the requested name. On Unix, a FIFO named `.env` is a valid file-location result: the returned path resolves to that FIFO, the path’s base name is `.env`, and a subsequent values-mapping parse of that path is accepted. A locator that only accepts a regular disk file does not implement this.

### Starting directory

Location walks from the starting directory toward the filesystem root, one parent at a time.

- In ordinary script execution (the main program is a script file, the session is not an interactive interpreter, no debugger is attached, and the process is not a frozen packaged executable), and when `usecwd` is `False`, the starting directory is the directory that contains the calling script, not the process working directory. A script that lives in a leaf folder and a `.env` that lives in an ancestor of that leaf are found. A `.env` that lives only in a different working directory the process later switched into, and that is not an ancestor of the script, is not found unless the caller asks to start from the working directory.
- When `usecwd` is `True`, when the session is an interactive interpreter (including a session whose main program has no script file path), when a debugger is attached, or when the process is a frozen packaged executable, the starting directory is the current working directory. A `.env` in an ancestor of the working directory is then found even if the calling code lives elsewhere.

The command-line program does **not** use this walk: its default path is `.env` in the current working directory only.

### Boundary behavior

- When the start is the working directory and that directory cannot be determined because it does not exist, location does not succeed.
- When the calling code was imported from a zip archive, location still completes: it does not fail merely because the zipped file has no ordinary filesystem directory. A `.env` sitting next to the zip on disk remains findable from an outer script that imported the zipped caller.
- Exception class names and exact message wording are not pinned.

## `envfile.get_key`

Import `get_key` from the package root `envfile` (`from `envfile` import `get_key``). Read the value of one named binding from a `.env` file.

### Signature

```
`get_key`(`envfile_path`, `key_to_get`, `encoding`="utf-8")
```

The first two arguments are positional: path, name. A call ``get_key`(path, name)` reads that name without naming an encoding.

- `envfile_path` — path of the `.env` file, as text or a path-like object.
- `key_to_get` — binding name to read (text).
- `encoding` — encoding used to decode the file. Default `"utf-8"`. When the caller does not name an encoding, the file is decoded as `utf-8`. When the caller names an encoding, the file is decoded with that encoding (a latin-1 file containing `é=è` is readable as that pair when latin-1 is named).

### Return shape

The call completes (the caller is not aborted) for a present text value, an empty string, a no-value line, a missing name in an existing file, and a missing path.

- **Text value:** a present name with a text value returns that text. `foo=bar` yields `bar`. A stored line written with an `export` prefix still yields the binding value: after a write that stored `export a='x'`, read of `a` yields `x`. A stored line written under always-quoting still yields the unquoted value: after a write that stored `a='b'`, read of `a` yields `b`.
- **Empty string:** a name whose stored line is `foo=` (equals, then end of line) returns the empty string. That outcome is text. It is distinguishable from no-value.
- **No value:** the return is not text. This is the outcome for a name whose stored line is only the name (no equals), for a name that is not in an existing file, and for a path that does not exist. The empty string is not this outcome. The concrete non-text carrier is not pinned.

Reading the same latin-1 bytes as `utf-8` is distinguishable from reading them as latin-1: the utf-8 read may abort, or it may complete with a different value.

### Diagnostics

Read of a missing name in an existing file returns no value and emits a diagnostic that identifies that the key was not found. That diagnostic is distinguishable from a present-name read of the same file.

Read of a path that does not exist returns no value and emits a diagnostic that identifies that the configuration file was not found, and a diagnostic that identifies that the key was not found. The missing-path case remains distinguishable from a missing-name read against an existing file, and it still includes that key-not-found situation.

Exact message wording is not pinned.

### Boundary behavior

- A missing path does not abort the caller; the result is no value.
- Exception class names and exact message wording are not pinned.

## `envfile.load_envfile`

Import `load_envfile` from the package root `envfile` (`from `envfile` import `load_envfile``). Parse a `.env` source and write recognized values into the process environment.

### Signature

```
`load_envfile`(`envfile_path`=None, `stream`=None, `verbose`=False, `override`=False, `interpolate`=True, `encoding`="utf-8")
```

- `envfile_path` — absolute or relative path of a `.env` file or Unix FIFO, as text or a path-like object, or `None`. `None` (the default) means no path was supplied.
- `stream` — in-memory text stream (for example `io.StringIO`) whose contents are `.env` text, or `None`. `None` (the default) means no stream was supplied.
- `verbose` — whether to emit a missing-file diagnostic. Default `False`. When `True`, a missing file also emits a diagnostic that identifies that the configuration file was not found; without extra reporting, that diagnostic is absent.
- `override` — whether a value from the source replaces a name that is already in the process environment. Default `False` (do not override).
- `interpolate` — whether to expand `${NAME}` / `${NAME:-default}` in values before they are written. Default `True`. Pass `False` to leave dollar-brace sequences as ordinary text in the process environment.
- `encoding` — encoding used to decode a file. Default `"utf-8"`. When the caller does not name an encoding, the file is decoded as `utf-8`. When the caller names an encoding, the file is decoded with that encoding (a latin-1 file containing `é=è` is readable as that pair when latin-1 is named).

If both `envfile_path` and `stream` are `None`, `find_envfile` is used to locate a `.env` file with its default parameters, and that file is loaded. A script placed next to a `.env` that contains `a=b`, with the process working directory at that same folder, results in the process environment containing `a=b` after a no-argument load.

If `envfile_path` names a readable regular file or Unix FIFO, that path is read even when a stream was also supplied. If the path is absent or is not a readable file or FIFO, and a stream was supplied, the stream is read.

### Return shape

Returns a boolean. The call completes (the caller is not aborted) in both the success and failure cases below.

- **Success (`True`):** the source produced at least one recognized name, even if every name was left unchanged because it was already in the process environment and `override` was off, and even if the only names had no value and therefore were not written.
- **Failure (`False`):** the source produced no recognized names (missing file, empty file, comments only), or loading was disabled by `PYTHON_ENVFILE_DISABLED`.

### Side effects on the process environment

Recognized names that have a value (including the empty string) are written into the process environment of the running Python process. Subsequent reads of the process environment see those values.

- Given a `.env` file whose only binding is `a=b`, and a process environment that does not already contain `a`, load writes `a` with value `b` and reports success.
- By default (`override` false), if the process environment already has `a=c` and the file has `a=b`, load reports success and leaves `a` as `c`. When `override` is true, the same inputs leave `a` as `b`.
- A name that has **no value** in the file (a line `FOO` with no equals) is not written into the process environment. A name whose value is the empty string (`FOO=`) is written as the empty string.
- A stream whose text is `PROBE=from_stream` writes `PROBE` with value `from_stream`. A stream `USER=foo` then a newline then `EMAIL=foo@example.org` writes those two names. A stream of `a=à` writes `a` with value `à`.
- On Unix, a FIFO that delivers `MY_PASSWORD=pipe-secret` loads that name with that value when `override` is on, or when the name was not already present. The same binding loaded from a FIFO and from a regular file of the same text is the same process-environment value.
- A missing file reports failure, writes nothing, and the call completes. Extra reporting emits the missing-file diagnostic; without it, that diagnostic is absent.

### Disable switch

When the process environment already contains `PYTHON_ENVFILE_DISABLED` with a value that, after folding letter case, is one of `1`, `true`, `t`, `yes`, or `y`, load does **not** read the file or stream and does **not** write any names from that source. It reports failure. The process environment is left as it was (including the disable variable itself). This holds for both a file path and a stream.

Any other value of that variable, including empty text, `0`, `false`, `no`, `f`, `n`, or the variable being absent, leaves loading enabled.

A `.env` file that itself contains `PYTHON_ENVFILE_DISABLED=true` does **not** disable the load that is reading it. That load still applies the file. Only a disable variable already present in the process environment — set by the caller or the operating system, not discovered in this source — turns loading off.

### Parse and expansion

The shared `.env` file format (names, quoting, comments, `export`, multiline quoted values, no-value versus empty string, line separators, byte-order mark, Unicode, invalid-line skipping, UTF-8 files, streams, and Unix FIFOs) applies.

When `interpolate` is `False`, dollar-brace text is written literally. When `interpolate` is left on (the default), the strings written into the process environment are the expanded strings, not the raw parsed text. Bare `$NAME` is never expanded.

**Resolution order when `override` is true:** for each `${NAME}`, the first defined of (1) that name’s value already computed from an earlier binding in this same source, (2) that name in the process environment, (3) the default if one was written, (4) empty text.

**Resolution order when `override` is false (the default):** for each `${NAME}`, the first defined of (1) that name in the process environment, (2) that name’s value already computed from an earlier binding in this same source, (3) the default if one was written, (4) empty text. Load of `a=b` then `d="${a}"` with process environment `a=c` and override off leaves `a` as `c` and sets `d` to `c`. The same file with override on sets `a` to `b` and `d` to `b`.

## `envfile.set_key`

Import `set_key` from the package root `envfile` (`from `envfile` import `set_key``). Write one named binding into a `.env` file, creating the file if it does not yet exist.

### Signature

```
`set_key`(`envfile_path`, `key_to_set`, `value_to_set`, `quote_mode`="always", `export`=False, `encoding`="utf-8", `follow_symlinks`=False)
```

The first three arguments are positional: path, name, value. A call ``set_key`(path, name, value)` writes that binding without naming an encoding, a quote mode, or an export flag.

- `envfile_path` — path of the `.env` file, as text or a path-like object.
- `key_to_set` — binding name to write (text).
- `value_to_set` — binding value to write (text).
- `quote_mode` — how the stored value is quoted. One of `always`, `never`, or `auto`. Default `"always"`. A quote mode other than those three is refused; the file is not written.
- `export` — when true, the stored line is prefixed with `export` and a space. Default `False` (no such prefix).
- `encoding` — encoding used to write the file. Default `"utf-8"`. When the caller does not name an encoding, the file is written as `utf-8`. When the caller names an encoding, write uses that encoding (writing `a` as `é` with latin-1 stores that character under latin-1).
- `follow_symlinks` — whether to follow a symbolic link at the `.env` path. Default `False`.

### Return shape

On success the call completes without aborting the caller and reports success. Write to a writable missing path creates the file; it does not fail merely because the file was absent. The public return is a three-element tuple: a success flag, the name that was written, and the value that was written.

### On-disk form

**Quote mode**

- `always` (default): the stored value is wrapped in single quotes. An interior single quote is escaped with a backslash. Writing `a` as `b` stores `a='b'` (plus a trailing newline). Writing a value that is itself a quoted string stores the quotes as content: writing `a` as `'b'` stores `a='\'b\''`.
- `never`: the stored value is written without added quotes: writing `a` as `x` stores `a=x`.
- `auto`: a value that is only letters and digits is written without quotes (`a=x`); any other value, including one with a space or `$`, is written in single quotes (`a='x y'`, `a='$'`).

**Export prefix.** When `export` is true, the stored line is `export a='x'` under `always`. When `export` is off, the line has no such prefix.

**Newlines.** If the last existing line has no trailing newline, a newline is inserted before an appended new binding so the new binding starts on its own line. A newly written binding is followed by a trailing newline.

**Unicode.** Writing `a` as `à` without a named encoding stores UTF-8 bytes that decode as text containing `à`. The same holds for an arbitrary name and a value that contains `à`.

### Replacement and other bindings

Write of an existing name replaces that name’s binding and leaves other bindings in place. A file `a=b` then a newline then `c=d`, after writing `a` as `e`, still contains `c=d`, and `a` now has the new value. Blank lines after the replaced binding are kept.

A subsequent parse of that file (values mapping or load) sees the written name with the written value.

### Permissions (Unix)

On Unix, rewriting an existing **regular** file keeps that file’s permission bits. A file whose mode was owner-read/write plus group-read stays that mode after a write. When a new regular file must be created, or when the path was not a regular file (including the default handling of a symbolic link), the new file is created with owner-read/write only.

### Symbolic links (default: do not follow)

By default (`follow_symlinks` false), write does **not** follow a symbolic link at the `.env` path. If `.env` is a symlink to an existing target file that contains `a=x`, writing `a` as `y` through `.env` leaves the target file still equal to `a=x`, replaces the symlink with a regular file, and stores the new binding in that new regular file.

If `.env` is a symlink to a **missing** target, write creates a regular file at `.env` with the new binding and does not create the missing target.

When `follow_symlinks` is true, write modifies the target file and leaves the symlink in place: writing `a` as `y` through a symlink updates the target to contain `a='y'` (under `always`) and `.env` is still a symlink.

### Boundary behavior

- A permission failure on write (the file is not writable) does not succeed; the original contents are unchanged.
- Exception class names and exact message wording are not pinned.

## `envfile.unset_key`

Import `unset_key` from the package root `envfile` (`from `envfile` import `unset_key``). Remove one named binding from a `.env` file. The file is not created if it does not yet exist.

### Signature

```
`unset_key`(`envfile_path`, `key_to_unset`, `quote_mode`="always", `encoding`="utf-8", `follow_symlinks`=False)
```

The first two arguments are positional: path, name. A call ``unset_key`(path, name)` deletes that name without naming an encoding or a follow-links flag.

- `envfile_path` — path of the `.env` file, as text or a path-like object.
- `key_to_unset` — binding name to remove (text).
- `quote_mode` — accepted with default `"always"`. Remaining bindings keep their original stored lines; delete does not rewrite them under a quote mode.
- `encoding` — encoding used to read and rewrite the file. Default `"utf-8"`. When the caller does not name an encoding, the file is rewritten as `utf-8`.
- `follow_symlinks` — whether to follow a symbolic link at the `.env` path. Default `False`.

### Return shape

On success the call completes without aborting the caller and reports success. The public return is a two-element tuple: a success flag and the name that was removed. Success/failure markers are not pinned to a language boolean.

A refused delete is distinguishable from a successful delete: it may abort the caller, or it may complete with a report that differs from success.

### Deletion

Delete of a present name removes that binding and leaves other bindings in place. A file `a=b` then a newline then `c=d`, after deleting `a`, still contains the independent line `c=d` and no longer contains `a=b`. The removed name does not remain as its own line. Other bindings keep their original stored lines. A subsequent read of the deleted name returns no value.

Delete of a no-value line `foo` removes that line. A subsequent read of `foo` returns no value.

Delete of a name that has already been removed from the same file does not succeed, leaves the file unchanged, and emits a diagnostic that the key was not removed.

### Symbolic links (default: do not follow)

By default (`follow_symlinks` false), delete does **not** follow a symbolic link at the `.env` path. If `.env` is a symlink to an existing target file that contains `a=x`, deleting `a` through `.env` leaves the target file still equal to `a=x`, replaces the symlink with a regular file, and removes the binding from that new regular file. A subsequent read of `a` through `.env` returns no value. The new regular file is created with owner-read/write only.

If `.env` is a symlink to a **missing** target, delete does not succeed; the symlink remains.

When `follow_symlinks` is true, delete modifies the target file and leaves the symlink in place. Deleting `a` through a symlink whose target is `a=x` then a sibling binding removes `a` from the target, keeps that sibling, and `.env` is still a symlink. A subsequent read of `a` from the target returns no value.

### Boundary behavior

- Delete of a path that does not exist does not succeed, does not create the file, and emits a diagnostic that the path does not exist.
- Delete of a name that is not in an existing file does not succeed, leaves the file unchanged, and emits a diagnostic that the key was not removed.
- A missing-name diagnostic and a missing-path diagnostic remain distinguishable.
- Exception class names and exact message wording are not pinned.

