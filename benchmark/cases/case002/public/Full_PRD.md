# python-envfile — Full Product Requirements Document

## Product overview

**python-envfile** reads key-value pairs from a `.env` file and can set them as environment variables. It exists so an application that follows the [12-factor](https://12factor.net/) pattern — configuration from the process environment — can still be launched in development without the operator exporting every name by hand. When a `.env` file is present, python-envfile loads it; when a name is already in the process environment, that live value stays in control unless the caller asks to override.

A first-time integrator adds a `.env` next to the application, asks python-envfile to load it, and then reads configuration from the process environment as if those names had been exported by the shell. A second, equally supported path is to parse the same file into an in-memory mapping and leave the process environment untouched, so several files (shared settings, secrets) can be merged under caller control.

A command-line program named `envfile` is included so operators can list, get, set, and unset bindings in a `.env` file, and so they can run another program with those bindings present in that program’s environment.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished python-envfile product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **`.env` file** | A text file of environment bindings. The default file name is `.env`. The product also reads the same format from an in-memory text stream, and on Unix from a FIFO (named pipe) in place of a regular file. |
| **Binding** | One recognized name, with either a text value, an empty string, or no value. |
| **Name / key** | The left-hand side of a binding. |
| **Value** | The right-hand side of a binding after quoting and escapes are applied. Distinct from **no value** (a name with no equals sign) and from the **empty string** (a name followed by an equals sign and nothing else). |
| **Process environment** | The environment mapping of the running Python process. Load writes here. The mapping-without-mutation entry does not. |
| **Load** | Parse a `.env` source and write recognized values into the process environment. |
| **Values mapping** | Parse a `.env` source and return the bindings as a mapping, without writing them into the process environment. |
| **Override** | When on, a value from the `.env` source replaces a name that is already in the process environment. When off, an already-present process-environment name is left unchanged. |
| **Expansion** | Replacing `${NAME}` and `${NAME:-default}` inside a value with another binding’s value, a process-environment value, the given default, or empty text. Bare `$NAME` (no braces) is not expansion. Specified in FP-05. |
| **`envfile`** | The command-line program shipped with python-envfile. Also reachable as a Python module invocation of the installed package. |
| **Quote mode** | How `envfile set` (and the library write entry) writes values: `always`, `never`, or `auto`. |
| **List format** | How `envfile list` prints bindings: `simple`, `json`, `shell`, or `export`. |
| **Core capability** | A user-observable capability that reflects python-envfile’s design goal; acceptance must prove the real library or CLI behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

python-envfile is a **library** with an optional **command-line program**. Integrators reach the library by installing the python-envfile package. Operators reach the CLI by installing python-envfile with the `cli` extra (the CLI depends on a third-party command-line library declared by that extra).

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- The `.env` file format: names, values, quoting, escapes, comments, `export`, multiline quoted values, empty versus missing values, UTF-8 byte-order mark, Unix FIFOs, and in-memory streams (FP-01).
- Locating a `.env` file by walking from a starting directory up to the filesystem root (FP-02).
- Loading recognized values into the process environment, including the default “do not override” policy, an explicit override, a dedicated disable switch, and streams (FP-03).
- Parsing the same sources into a mapping without mutating the process environment (FP-04).
- POSIX-style `${NAME}` / `${NAME:-default}` expansion, including the different resolution order used when override is on versus off (FP-05).
- Reading, writing, and deleting a named binding in a `.env` file, including quote modes, an optional `export` prefix, and the default of not following symbolic links (FP-06).
- The `envfile` command’s list / get / set / unset subcommands and global file, quote, export, and version flags (FP-07).
- The `envfile run` subcommand, which starts another program with `.env` values in that program’s environment (FP-08).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library. No compiled extensions, native code, GPU, or accelerator are required or claimed.
- **Language:** Python 3.10 or newer, including the CPython and PyPy implementations the project tests.
- **Platforms:** Intended to work on Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter. Unix FIFOs are a Unix-only source; they are not a Windows acceptance obligation.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host able to import python-envfile from this repository’s source tree and apply a short in-memory `NAME=value` stream onto the process environment.
- **Default file name:** `.env`.
- **Default load policy:** Do not override names already present in the process environment.
- **Default CLI file:** `.env` in the current working directory.
- **Default CLI quote mode:** `always`.
- **Default CLI list format:** `simple`.
- **Character encoding:** Unless the caller names a different encoding, `.env` files are read and written as UTF-8.
- **CLI extra:** The `envfile` program requires the `cli` extra. Without that extra, invoking the program does not run subcommands.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real python-envfile behavior matches the described outcomes when a `.env` source is parsed, loaded, written, or when `envfile` is invoked with the named inputs.
- **Absent / hollow:** A stub that always writes a fixed mapping; a loader that always overrides or always no-ops; a parser that splits on the first equals sign and ignores quoting; a CLI that prints hard-coded text; expansion that treats `$NAME` and `${NAME}` the same.

Cheaper proxies (hard-coded environment tables, shelling out to Bash to parse the file, skipping override rules, or treating every line as `NAME=rest-of-line`) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces python-envfile’s parser, loader, or CLI for a core capability.

**Negative control (Python / package substrate):** When python-envfile is deliberately not importable in an isolated subprocess (removed from the import path), an application that depends on it must fail to start with a hard error — not pass silently or skip. When the interpreter is present and the package is installed from this tree, loading a stream `PROBE=from_stream` writes `PROBE` with value `from_stream` into the process environment. Output-equality alone is not proof that the real package ran.

## Non-goals

- Being a general-purpose configuration framework (typed settings objects, layered YAML/TOML, remote secret stores). python-envfile reads `.env` text and optionally writes the process environment.
- Shipping a web server, GUI, or cloud control plane.
- Treating the IPython line magic (`%envfile`) as a graded core capability. That integration exists so a notebook can load a `.env` file; it is not a feature point below.
- Treating the helper that renders a `envfile …` shell string for remote task runners as a graded capability.
- Guaranteeing a particular parse-throughput benchmark.
- Formal compatibility with every Bash or POSIX shell quirk. The format is similar to Bash and is specified by FP-01 and FP-05, not by a shell standard.

---

## Feature points

### FP-01: `.env` file format

**Public entry:** Any python-envfile parse of a `.env` file, FIFO, or in-memory text stream — the load entry (FP-03), the values-mapping entry (FP-04), the file read/write entries (FP-06), and the `envfile` command (FP-07, FP-08). This feature point is the shared format those entries consume. Expansion of `${…}` inside values is specified in FP-05; until expansion runs, a dollar-brace sequence is ordinary text in the parsed value.

**Normal behavior:**

- A line `DOMAIN=example.org` is one binding whose name is `DOMAIN` and whose value is `example.org`.
- Spaces around the name, the equals sign, and the value are ignored: a line ` a = b ` is the same binding as `a=b`.
- Names may be unquoted or wrapped in single quotes. `'a'=b` is a binding named `a` with value `b`. An unquoted name may include characters such as `[`, `%`, and `$`. A line `uglyKey[%$="secret"` is a binding named `uglyKey[%$` with value `secret`; an unquoted name may not contain an equals sign, a hash, or whitespace.
- Values may be unquoted, single-quoted, or double-quoted. Single quotes and double quotes preserve interior spaces, including trailing spaces: `a='b c '` and `a="b c "` both yield the value `b c ` (space after `c`).
- An unquoted value may contain spaces and other interior whitespace: `a=b c` yields `b c`; `a=b` then a tab then `c` yields a value with that tab between `b` and `c`. Trailing whitespace on an unquoted value is stripped: `a=b c ` yields `b c`.
- A line may begin with the `export` directive. `export a=b` and ` export 'a'=b` are the same binding as `a=b`. The directive does not change interpretation. A name that itself starts with `export` is not eaten as a directive: `export export_a=1` is a binding named `export_a` with value `1`; `export port=8000` is a binding named `port` with value `8000`.
- A line whose first non-space character is `#` is a comment and is not a binding. Several comment lines in a row are all comments.
- A value may be followed by a comment when whitespace separates the value from `#`: `a=b #c` is name `a`, value `b`. A hash that is glued to the value is part of the value: `a=b#c` is name `a`, value `b#c`. A tab before `#` also starts a comment: `a=b` then a tab then `#c` is value `b`.
- Allowed escape sequences in a **single-quoted** value are a backslash followed by a backslash, and a backslash followed by a single quote. `a='b\'c'` yields `b'c`. A backslash followed by `n` inside single quotes is **not** a newline: `a='b\nc'` yields the four characters `b`, `\`, `n`, `c`.
- Allowed escape sequences in a **double-quoted** value are a backslash followed by a backslash, a single quote, a double quote, `a`, `b`, `f`, `n`, `r`, `t`, or `v`. `a="b\nc"` yields `b`, newline, `c`. `a="b\"c"` yields `b"c`.
- A single-quoted or double-quoted value may span multiple lines. These two sources are equivalent after parse: a double-quoted value whose interior contains a real newline between `first line` and `second line`, and a double-quoted value whose interior contains the two-character escape `\n` between those phrases. Both yield a value with a newline between the two phrases. The same pair of forms is valid with single quotes for a real interior newline; the `\n` escape form is **not** equivalent under single quotes (see the single-quote escape list above).
- A variable can have no value: a line that is only the name `FOO` (no equals sign) is a binding named `FOO` with **no value**. This is not the same as `FOO=`, which is a binding named `FOO` whose value is the empty string.
- Bindings may be separated by a line feed, a carriage return, or a carriage-return/line-feed pair. `a=b` then a carriage return then `c=d` is two bindings, `a=b` and `c=d`.
- A leading UTF-8 byte-order mark is ignored. A stream that begins with a byte-order mark and then `a=b` is the same as a stream that is only `a=b`. The mark is not part of the first name.
- Unicode text in names and values is preserved: `a=à` and `a="à"` both yield value `à`.
- On Unix, a FIFO (named pipe) whose contents are one or more bindings in this format is a valid `.env` source for load and for file location (FP-02, FP-03). A reader that only accepts a regular disk file, and cannot consume a FIFO, does not implement this format’s Unix source.

**Boundary / error behavior:**

- A line that is not a valid binding does not contribute a name. `a: b` (colon instead of equals) is not a binding. A later valid line in the same source is still recognized: a source whose first line is an unclosed double quote `a="` and whose second line is `b=c` yields the binding `b=c` and does not yield `a`.
- An empty source, a source of only blank lines, or a source of only comments yields no bindings.
- `a=` (equals, then end of line or newline) is the empty string, not “no value”, and not an error.
- The format does not treat a colon, a YAML-style mapping, or a JSON object as a binding.

**Verifiable oracle:**

- Success: `DOMAIN=example.org` parses as name `DOMAIN`, value `example.org`; ` a = b ` matches `a=b`; `'a'=b` is name `a`; `export a=b` matches `a=b`; `export export_a=1` is name `export_a`; `# a=b` is not a binding; `a=b #c` is value `b` and `a=b#c` is value `b#c`; `a='b c '` keeps the trailing space; `a=b` then a tab then `c` keeps the interior tab; `uglyKey[%$="secret"` is name `uglyKey[%$` with value `secret`; `a="b\nc"` is `b`, newline, `c`; `a='b\nc'` is `b\nc` as four characters; a quoted value with a real interior newline spans lines; a line `FOO` has no value and a line `FOO=` has the empty string; a leading byte-order mark does not eat `a` from `a=b`; `a=b` then carriage return then `c=d` is two bindings; on Unix, a FIFO that writes `MY_PASSWORD=pipe-secret` is readable as that binding.
- Failure / absence: every line is split on the first equals sign with no quoting; `export` becomes part of the name; comments are loaded as names; `FOO` and `FOO=` are indistinguishable; `\n` inside single quotes becomes a newline; a byte-order mark leaves the first name wrong; a FIFO is refused; `a: b` is accepted as a binding.

---

### FP-02: Locate a `.env` file by walking ancestors

**Public entry:** The library’s file-location entry, and the default of the load entry and the values-mapping entry when the caller does not supply a path or a stream (FP-03, FP-04). The caller may name a file other than `.env`. The `envfile` command does **not** walk ancestors: it uses `.env` in the current working directory unless `--file` names another path (FP-07).

**Normal behavior:**

- Location walks from a starting directory toward the filesystem root, one parent at a time, and returns the first path that is a regular file or (on Unix) a FIFO whose base name is the requested name (default `.env`).
- In ordinary script execution (the main program is a script file, the session is not an interactive interpreter, no debugger is attached, and the process is not a frozen packaged executable), the starting directory is the directory that contains the calling script, not the process working directory. A script that lives in a leaf folder and a `.env` that lives in an ancestor of that leaf are found; a `.env` that lives only in a different working directory the process later switched into, and that is not an ancestor of the script, is not found unless the caller asks to start from the working directory.
- When the caller asks to start from the working directory, when the session is an interactive interpreter (including a session whose main program has no script file path), when a debugger is attached, or when the process is a frozen packaged executable, the starting directory is the current working directory. A `.env` in an ancestor of the working directory is then found even if the calling code lives elsewhere.
- When a matching file exists, the result is the path to that file. When none exists after walking to the root, the result is empty text (no path), unless the caller asked to fail if not found, in which case the operation does not succeed and no path is delivered.
- A custom file name is searched under that name, not under `.env`. A tree that contains only `.env` does not satisfy a search for a different name, and a tree that contains only that other name does not satisfy a default `.env` search.

**Boundary / error behavior:**

- When the start is the working directory and that directory cannot be determined because it does not exist, location does not succeed.
- When the calling code was imported from a zip archive, location still completes: it does not fail merely because the zipped file has no ordinary filesystem directory. A `.env` sitting next to the zip on disk remains findable from an outer script that imported the zipped caller.
- A missing file with “fail if not found” off yields empty text. The same missing file with “fail if not found” on is a failure. An observer can tell those two requests apart.
- The CLI’s default path is not this walk: `envfile get` with no `--file` reads `./.env` in the working directory only (FP-07).

**Verifiable oracle:**

- Success: from `child1/child2/child3/child4`, with `.env` at the tree root and the caller asking to start from the working directory, the returned path is that root `.env`; with no `.env` anywhere in the ancestors, the result is empty text when failure-on-missing is off and the operation does not succeed when failure-on-missing is on; a search for a custom name finds that file and does not return a sibling `.env`; in script mode, a `.env` in the working directory that is not an ancestor of the script is not selected; in interactive or debugger or working-directory mode, that working-directory `.env` is selected; a zip-imported caller does not crash location, and a `.env` beside the zip remains findable from the outer script.
- Failure / absence: location only looks in the working directory and never walks up; script mode and interactive mode cannot be told apart; a missing file always fails, or always pretends a path exists; zip-imported callers crash.

---

### FP-03: Load `.env` values into the process environment

**Public entry:** The library’s load entry. The caller may pass a file path, an in-memory text stream, or neither (in which case FP-02 locates a `.env` file). The IPython magic, when used, calls this same load; it is not a separate graded entry (see Non-goals). The `envfile run` command applies values to a **child** process and is specified in FP-08; it does not replace this entry.

**Normal behavior:**

- Given a `.env` file whose only binding is `a=b`, and a process environment that does not already contain `a`, load writes `a` with value `b` into the process environment and reports success. Subsequent reads of the process environment see `b`.
- By default, load does **not** override. If the process environment already has `a=c` and the file has `a=b`, load reports success and leaves `a` as `c`. When the caller asks to override, the same inputs leave `a` as `b`.
- A name that has **no value** in the file (a line `FOO` with no equals) is not written into the process environment. A name whose value is the empty string (`FOO=`) is written as the empty string.
- If the caller supplies neither a path nor a stream, load locates a `.env` file as in FP-02 and loads that file. A script placed next to a `.env` that contains `a=b`, with the process working directory at that same folder, results in the process environment containing `a=b` after a no-argument load.
- Load accepts an in-memory text stream. A stream whose text is `USER=foo` then a newline then `EMAIL=foo@example.org` writes those two names. A stream of `a=à` writes `a` with value `à`.
- If a path names a readable regular file or Unix FIFO, that path is read even when a stream was also supplied. If the path is absent or is not a readable file or FIFO, and a stream was supplied, the stream is read.
- On Unix, a FIFO that delivers `MY_PASSWORD=pipe-secret` loads that name with that value when override is on (or when the name was not already present).
- When the caller names an encoding, the file is decoded with that encoding. A latin-1 file containing `é=è` is readable as that pair when latin-1 is named.
- Load reports **success** when the source produced at least one recognized name, even if every name was left unchanged because it was already in the process environment and override was off, and even if the only names had no value and therefore were not written. Load reports **failure** when the source produced no recognized names (missing file, empty file, comments only). A missing file does not abort the caller; the process environment is unchanged and the result is failure. When the caller asked for extra reporting, a missing file also emits a diagnostic that identifies that the configuration file was not found; without extra reporting, that diagnostic is absent.
- When expansion is left on (the default), the strings written into the process environment are the expanded strings specified in FP-05, not the raw parsed text. Turning expansion off leaves dollar-brace text literal in the process environment.

**Disable switch:**

- When the process environment already contains `PYTHON_ENVFILE_DISABLED` with a value that, after folding letter case, is one of `1`, `true`, `t`, `yes`, or `y`, load does **not** read the file or stream and does **not** write any names from that source. It reports failure. The process environment is left as it was (including the disable variable itself). This holds for both a file path and a stream.
- Any other value of that variable, including empty text, `0`, `false`, `no`, `f`, `n`, or the variable being absent, leaves loading enabled. A file `a=b` is then applied as usual.
- A `.env` file that itself contains `PYTHON_ENVFILE_DISABLED=true` does **not** disable the load that is reading it. That load still applies the file (so the process environment then contains `PYTHON_ENVFILE_DISABLED` as `true`). Only a disable variable already present in the process environment — set by the caller or the operating system, not discovered in this source — turns loading off.
- The values-mapping entry (FP-04) is not gated by this switch: it still returns parsed bindings when the switch is on.

**Boundary / error behavior:**

- A path that does not exist: load reports failure, writes nothing, and the call completes (the caller is not aborted). Extra reporting emits the missing-file diagnostic; without it, the diagnostic is absent.
- A source whose parsed mapping is empty reports failure.
- A disable spelling that appears only inside the source being loaded does not gate that same load.

**Verifiable oracle:**

- Success: file `a=b` in an empty process environment yields process environment `a=b` and success; with existing `a=c` and override off, `a` stays `c`; with override on, `a` becomes `b`; a no-value line is not written; `FOO=` writes an empty string; a stream `a=à` writes `à`; a missing file reports failure and the call completes; a latin-1 file containing `é=è` writes that pair when latin-1 is named; `PYTHON_ENVFILE_DISABLED=true` (any listed truthy spelling) blocks a file `a=b` so `a` is absent and the result is failure; `PYTHON_ENVFILE_DISABLED=false` (or `0`, empty, absent) still loads `a=b`; a file whose only assignment is `PYTHON_ENVFILE_DISABLED=true` still loads when the process did not already disable; on Unix a FIFO `MY_PASSWORD=pipe-secret` writes that value.
- Failure / absence: load always overwrites; load never overwrites even when asked; a missing file aborts the caller; the disable switch is ignored; a disable line inside the file blocks the same load; streams are refused; a no-value line is written as empty or as the name itself.

---

### FP-04: Read `.env` bindings as a mapping without mutating the process environment

**Public entry:** The library’s values-mapping entry. The caller may pass a file path, a stream, or neither (FP-02 locates a `.env` file). This is the README’s “load configuration without altering the environment” path.

**Normal behavior:**

- Given a file `a=b`, the mapping contains `a` with value `b`. The process environment is not modified: a name that was absent stays absent; a name that was present keeps its previous value.
- A name with **no value** (`FOO` with no equals) is present in the mapping and is recorded as having no value — distinct from a missing name and distinct from `FOO=` (empty string).
- An empty or missing file yields an empty mapping. The call completes; the process environment is unchanged.
- A stream is accepted the same way as in FP-03. A stream `a=b` yields a mapping in which name `a` has value `b` and does not write `a` into the process environment.
- The caller can parse several files and combine the mappings in application code (shared file, then secret file, then the live process environment). python-envfile itself does not merge files in one call; each call returns one source. That combining pattern is narrative; the graded obligation is that one call returns one source’s bindings and does not write the process environment.
- Expansion, when left on (the default), uses the override-on resolution order in FP-05 (file values beat the process environment when a name appears in both). Turning expansion off leaves dollar-brace text literal in the returned mapping.

**Boundary / error behavior:**

- A missing path yields an empty mapping. The call completes; the caller is not aborted.
- The disable switch in FP-03 does not apply: with `PYTHON_ENVFILE_DISABLED=true` in the process environment, a file `a=b` still yields a mapping with `a=b`, and the process environment still does not gain `a` from this entry.
- Values in the mapping are the parsed strings (after expansion if on). They are not automatically copied into the process environment.

**Verifiable oracle:**

- Success: file `a=b` returns a mapping with `a` equal to `b` and leaves the process environment without a new `a` (or with the previous `a` unchanged); a line `FOO` yields a present name with no value; a line `FOO=` yields the empty string; a missing file yields an empty mapping and the call completes; a stream `a=b` returns that pair without writing the process environment; with the disable switch on, this entry still returns `a=b` from a file `a=b` and still does not write `a`.
- Failure / absence: this entry writes the process environment; no-value and empty-string are collapsed; a missing file aborts the caller; the disable switch also blanks this entry.

---

### FP-05: Variable expansion

**Public entry:** The load entry (FP-03) and the values-mapping entry (FP-04), both of which expand by default. The caller can turn expansion off on either entry. File-format parse (FP-01) leaves dollar-brace sequences as ordinary text in the parsed value. This feature point specifies what load and the values-mapping entry do with those sequences when expansion is on. **This feature point refines FP-03 and FP-04:** when expansion is on, the values those entries apply or return are the expanded strings specified here, not the raw parsed text.

**Normal behavior:**

- Only the braced forms are expanded: a dollar sign, an opening brace, a name, and a closing brace (`${NAME}`), optionally with a default introduced by `:-` before the closing brace (`${NAME:-default}`). Bare `$NAME` without braces is left unchanged: with process environment `b=c` and source `a=$b`, the value of `a` remains `$b` whether expansion is on or off.
- With expansion **on** (the default) and source `a=${b}` and process environment `b=c`, the value of `a` is `c`. With expansion **off**, the value of `a` is the literal characters `${b}`. The same on/off contrast holds for `${b:-d}`.
- Surrounding text is kept: with `b=c` and source `a=x${b}y`, the value of `a` is `xcy`. A name may be reused: `a=${b}${b}` with `b=c` yields `cc`.
- Quotes do **not** suppress expansion. After parse, a double-quoted `${b}` and a single-quoted `${b}` both expand when expansion is on: with `b=c`, both `a="${b}"` and `a='${b}'` yield `c`. (This is unlike Bash, where single quotes would prevent expansion.)
- When the named variable is unset and no default is given, the replacement is the empty string: source `a=${b}` with `b` absent yields `a` as empty text.
- When the named variable is unset and a default is given, the replacement is that default: source `a=${b:-d}` with `b` absent yields `a` as `d`.
- A name that is **present with no value** is not “unset”. In `${b:-d}`, if `b` exists with no value, the default is **not** used; the replacement is empty text. The default is used only when the name is absent.
- **Resolution order when override is on** (this is the order used by the values-mapping entry, and by load when the caller asked to override): for each `${NAME}`, the first defined of (1) that name’s value already computed from an earlier binding in this same `.env` source, (2) that name in the process environment, (3) the default if one was written, (4) empty text. A later binding in the file therefore wins over the process environment: source `b=d` then `a=${b}` with process environment `b=c` yields `b=d` and `a=d`. A name redefined in the file uses the latest assignment: `a=b` then `a=c` then `d=${a}` yields `a=c` and `d=c`.
- **Resolution order when override is off** (load’s default): for each `${NAME}`, the first defined of (1) that name in the process environment, (2) that name’s value already computed from an earlier binding in this same source, (3) the default if one was written, (4) empty text. Load of `a=b` then `d="${a}"` with process environment `a=c` and override off leaves `a` as `c` and sets `d` to `c` (the process environment wins both the write of `a` and the expansion of `d`). The same file with override on sets `a` to `b` and `d` to `b`.
- Self-reference: source `a=${a}` with process environment `a=b` yields `a=b` (the existing environment value). Source `a=${a}` with `a` absent yields empty text. Source `a=${a:-c}` with `a` absent yields `c`; with process environment `a=b` yields `b`.
- A binding with no value is not expanded (it stays no-value in the mapping; load still does not write it).

**Boundary / error behavior:**

- Expansion off: every dollar-brace sequence is returned or written literally, including `${b}` and `${b:-d}`, even when `b` is set.
- An unknown name without a default becomes empty text, not a failure, and not the raw `${name}` string.
- Bare `$b` is never expanded, including when expansion is on and `b` is set.

**Verifiable oracle:**

- Success: `${b}` with `b=c` becomes `c` when expansion is on and stays `${b}` when expansion is off; `$b` stays `$b` in both cases; `${b:-d}` is `c` when `b=c` and `d` when `b` is absent; `x${b}y` is `xcy`; `"${b}"` and `'${b}'` both become `c`; values-mapping of `b=d` then `a=${b}` with environment `b=c` yields `a=d`; load with override off of `a=b` then `d="${a}"` with environment `a=c` yields process environment `a=c` and `d=c`; load with override on of the same file yields `a=b` and `d=b`; `a=${a}` with environment `a=b` yields `b`; `a=${b}` with `b` absent yields empty text.
- Failure / absence: `$b` and `${b}` are treated the same; single quotes block expansion; expansion cannot be turned off; override-off load still expands `d` from the file’s `a=b` instead of from the process environment; a missing name leaves the raw `${b}` text in the value.

---

### FP-06: Get, set, and unset a binding in a `.env` file

**Public entry:** The library’s three file-editing entries: read one name, write one name, and delete one name. The `envfile` command’s `get` / `set` / `unset` subcommands (FP-07) call this same behavior; CLI output and exit status are specified there. Quote modes and the `export` prefix apply to write.

**Normal behavior:**

- **Write** of name `foo` with value `bar` to a path that does not yet exist creates that file and stores the binding. The operation reports success. A subsequent read of that name returns `bar`.
- **Write** of an existing name replaces that name’s binding and leaves other bindings in place. A file `a=b` then a newline then `c=d`, after writing `a` as `e`, still contains `c=d`, and `a` now has the new value. Blank lines after the replaced binding are kept.
- If the last existing line has no trailing newline, a newline is inserted before an appended new binding so the new binding starts on its own line.
- **Quote mode** is one of `always`, `never`, or `auto` (default `always`):
  - `always`: the stored value is wrapped in single quotes. An interior single quote is escaped with a backslash. Writing `a` as `b` stores `a='b'` (plus a trailing newline). Writing a value that is itself a quoted string stores the quotes as content: writing `a` as `'b'` stores `a='\'b\''`.
  - `never`: the stored value is written without added quotes: writing `a` as `x` stores `a=x`.
  - `auto`: a value that is only letters and digits is written without quotes (`a=x`); any other value, including one with a space or `$`, is written in single quotes (`a='x y'`, `a='$'`).
- When the caller asks to write with `export`, the stored line is prefixed with `export` and a space: `export a='x'` (under `always`). When `export` is off, the line has no such prefix.
- **Read** of a present name with a text value returns that value (`foo=bar` yields `bar`). Read of a missing name in an existing file returns no value and emits a diagnostic that identifies that the key was not found. Read of a name that has no value in the file (line `foo` with no equals) returns no value. Read of a path that does not exist returns no value and emits a diagnostic that identifies that the configuration file was not found, and a diagnostic that identifies that the key was not found.
- **Delete** of a present name removes that binding and leaves other bindings. A file `a=b` then `c=d`, after deleting `a`, contains `c=d`. Delete of a no-value line `foo` removes that line.
- When the caller names an encoding, read and write use that encoding. Writing `a` as `é` with latin-1 stores that character under latin-1; reading `é=è` with latin-1 returns `è`.
- On Unix, rewriting an existing **regular** file keeps that file’s permission bits. A file whose mode was owner-read/write plus group-read stays that mode after a write.
- When a new regular file must be created, or when the path was not a regular file (including the default handling of a symbolic link, below), the new file is created with owner-read/write only.

**Symbolic links (default: do not follow):**

- By default, write and delete do **not** follow a symbolic link at the `.env` path. If `.env` is a symlink to an existing target file that contains `a=x`, writing `a` as `y` through `.env` leaves the target file still equal to `a=x`, replaces the symlink with a regular file, and stores the new binding in that new regular file. The same default on delete removes the binding from a new regular file at `.env` and leaves the target unchanged.
- If `.env` is a symlink to a **missing** target, write creates a regular file at `.env` with the new binding and does not create the missing target. Delete of a name through a symlink to a missing target does not succeed; the symlink remains.
- When the caller asks to follow symbolic links, write and delete modify the target file and leave the symlink in place: writing `a` as `y` through a symlink updates the target to contain `a='y'` (under `always`) and `.env` is still a symlink.

**Boundary / error behavior:**

- A quote mode other than `always`, `never`, or `auto` is refused; the file is not written.
- Delete of a path that does not exist does not succeed, does not create the file, and emits a diagnostic that the path does not exist.
- Delete of a name that is not in an existing file does not succeed, leaves the file unchanged, and emits a diagnostic that the key was not removed.
- Write to a writable missing path creates the file; it does not fail merely because the file was absent.

**Verifiable oracle:**

- Success: writing `foo=bar` to a missing path creates the file and a later read returns `bar`; replacing `a` in `a=b` then `c=d` updates `a` and keeps `c=d`; `always` stores `a='b'`; `never` stores `a=x`; `auto` stores `a=x` for alphanumeric `x` and `a='x y'` for a spaced value; `export` stores a line beginning with `export `; delete of `a` from `a=b` then `c=d` leaves `c=d`; read of a missing name returns no value and identifies that the key was not found; read of a missing path returns no value and identifies that the configuration file was not found; default write through a symlink to `target.env` leaves `target.env` unchanged and makes `.env` a regular file with the new value; follow-links write updates `target.env` and keeps the symlink; Unix regular-file permission bits are preserved on rewrite; latin-1 write and read round-trip `é`.
- Failure / absence: write to a missing path no-ops; replace rewrites the whole file and drops other keys; quote modes are ignored; delete of a missing file creates an empty file or reports success; default write follows the symlink and changes the target.

---

### FP-07: `envfile` command — list, get, set, and unset

**Public entry:** The `envfile` command-line program, also reachable as a Python module invocation of the installed package. Global options apply to every subcommand: `--file` / `-f` (path of the `.env` file; default `.env` in the current working directory), `--quote` / `-q` (`always`, `never`, or `auto`; default `always`), `--export` / `-e` (whether written lines begin with `export `; default off), and `--version` (print the package version and exit successfully). Subcommands specified here: `list`, `get`, `set`, `unset`. `run` is FP-08.

Installing python-envfile **without** the `cli` extra leaves this program unable to run subcommands: invocation does not run subcommands, the operator-visible report identifies that python-envfile was not installed with the CLI extra, and the process exits unsuccessfully. With the extra present, the subcommands below run.

**Normal behavior:**

- **`set NAME VALUE`** writes that binding using FP-06 (creating the file if needed) under the chosen quote mode and export flag, then prints `NAME=VALUE` (the requested name and value, not necessarily the quoted on-disk form) and exits successfully. After `envfile set USER foo` then `envfile set EMAIL foo@example.org` against a default `.env`, that file contains those two bindings.
- **`get NAME`** prints the stored value followed by a newline and exits successfully when the name is present with a non-empty value. `envfile get A` against a working-directory `.env` that contains `A=x` prints `x`.
- **`unset NAME`** removes the binding (FP-06) and prints a success confirmation that identifies the removed name, then exits successfully. After unset of `a` from a file that only contained `a=b`, the file has no `a` binding.
- **`list`** prints every stored name that has a value, in sorted name order. The `--format` option is one of:
  - `simple` (default): each line is `NAME=value` with no added quotes. A value that contains spaces is printed as those spaces, not wrapped in quotes. A value that was stored quoted is shown unquoted after parse.
  - `json`: a JSON object with names sorted, pretty-printed across multiple lines (not a single compact line). A name with no value appears as JSON null. Names with values appear as JSON strings.
  - `shell`: each line is `NAME=` followed by a shell-quoted value (safe to paste into a POSIX shell).
  - `export`: like `shell`, with the prefix `export ` before each name.
- In `simple`, `shell`, and `export`, a name that has **no value** is omitted. In `json`, that name is present with a null.
- `--version` prints an identity that ends with the installed python-envfile version and exits successfully, including when it appears before `run` (FP-08). A `--version` that belongs to the **child** command after `run` is not this flag (FP-08).

**Boundary / error behavior:**

- `list` or `get` against a path that cannot be opened (missing file, or a directory instead of a file) fails in a way that is distinguishable from a missing key in an existing file: the operator-visible report identifies that the env file could not be opened, and the exit status is the usage-style failure class, not the missing-key class. `get` of a missing name in an **existing** file, or of a name whose stored value is empty, exits unsuccessfully with empty output (missing-key class). `unset` of a missing name in an existing file exits unsuccessfully and leaves the file unchanged.
- `set` without both a name and a value is a usage failure (missing argument).
- `set` / `unset` use FP-06’s default of not following symbolic links.
- A default path of `.env` in the working directory is used when `--file` is omitted: `envfile get A` from a folder whose `.env` contains `A=x` prints `x`.

**Verifiable oracle:**

- Success: `set USER foo` then `list` shows `USER=foo`; `list --format json` of `x='a b c'` is a JSON object with `x` equal to `a b c`; `list --format json` of a no-value line `FOO` includes `FOO` as JSON null while `list --format simple` of the same source omits `FOO`; `list --format export` prefixes `export ` and shell-quotes the value; `list --format simple` of `x='a b c'` prints `x=a b c`; `get A` against `A=x` prints `x` and succeeds; `get` of a name whose stored value is empty, in an existing file, exits unsuccessfully with empty output (missing-key class), distinguishable from a missing file (usage-style failure); `unset a` on `a=b` empties that binding and succeeds; `--quote never set a x` stores `a=x`; `--export true set a x` stores a line beginning with `export `; `--version` succeeds and the printed text ends with the package version; missing `--file` reads `./.env`.
- Failure / absence: `list` against a missing file uses the same unsuccessful outcome as `get` of a missing key; `get` of a present name prints nothing; `list` formats cannot be told apart; `set` does not create a missing file; `--version` fails or prints nothing identifiable as a version.

---

### FP-08: `envfile run` — run a program with `.env` values in its environment

**Public entry:** The `envfile run` subcommand of the `envfile` program (FP-07). Global `--file` selects the `.env` file. This entry starts another program with the selected bindings in that program’s environment. It is not the load entry (FP-03): it does not write those names into a surviving caller’s process environment.

**Normal behavior:**

- `envfile run -- printenv A` in a working directory whose `.env` contains `A=x` runs `printenv A` with `A=x` in that program’s environment. The child prints `x` and the `envfile` process’s exit status is that child’s exit status.
- By default, values from the `.env` file **override** names already present in the environment inherited by the child. With inherited `A=y` and file `A=x`, `envfile run -- printenv A` prints `x`.
- With `--no-override`, inherited names win: the same inputs print `y` (or whatever the inherited value was). `--override` restores the default override-on policy.
- A name that has **no value** in the file is not exported to the child. File `A=x` then a no-value line `c`, then `envfile run -- printenv A`, still prints `x`; the child does not receive a `c` binding from that no-value line.
- `--file` selects a `.env` that is not the working-directory default. `envfile --file path/to/file run -- printenv A` against that file’s `A=x` prints `x` even when the working directory has no `.env`.
- Tokens after `run` belong to the child command, including tokens that look like `envfile` flags. `envfile --file FILE run printenv --version` runs `printenv --version` (the child’s version), not `envfile --version`. A `envfile --version` placed **before** `run` is consumed by `envfile` itself (FP-07) and does not start the child.
- The observer sees the child program’s standard output and exit status. The `envfile` process’s exit status is that child’s exit status.

**Boundary / error behavior:**

- If the selected `.env` path is not an existing file, `run` fails as an invalid `--file` value (usage-style failure) and does not start the child. This failure takes precedence over a child command that would also have been missing: `envfile run i_do_not_exist` in a folder with no `.env` reports the invalid file, not “command not found”.
- If the file exists but no child command is given, `run` reports that no command was given and exits unsuccessfully without starting a child program.
- If the file exists and the child program cannot be found, `run` reports that the command was not found (the report identifies the missing program name) and exits unsuccessfully.
- `run` does not create a `.env` file.

**Verifiable oracle:**

- Success: `run printenv A` with `.env` containing `A=x` prints `x` and exits successfully; with inherited `A=y` and default override, the child sees `x`; with `--no-override`, the child sees `y`; a no-value line is not exported; `--file` points at another file and that file’s values are the ones the child sees; `run printenv --version` prints `printenv`’s version text, not `envfile`’s; `envfile --version … run …` prints `envfile`’s version and does not run the child.
- Failure / absence: the child does not see `.env` values; default `run` never overrides; `--no-override` is ignored; flags after `run` are eaten as `envfile` flags so `printenv --version` cannot run; a missing `.env` still starts the child; a missing child program is reported as success; a missing `.env` and a missing program cannot be told apart.

---

## Information completeness notes

- **Quote modes (finite):** `always`, `never`, `auto`.
- **List formats (finite):** `simple`, `json`, `shell`, `export`.
- **Disable-switch truthy values (finite, after folding letter case):** `1`, `true`, `t`, `yes`, `y`. Any other value leaves loading enabled.
- **Default file name:** `.env`. **CLI default path:** `.env` in the current working directory.
- **Load default:** override off. **`envfile run` default:** override on. Those two defaults differ; an implementation that uses one default for both is wrong.
- **Expansion forms (finite):** `${NAME}` and `${NAME:-default}`. Bare `$NAME` is not expanded.
- **Single-quote escapes (finite):** `\\`, `\'`. **Double-quote escapes (finite):** `\\`, `\'`, `\"`, `\a`, `\b`, `\f`, `\n`, `\r`, `\t`, `\v`.
- **CLI extra name:** `cli` (install as `python-envfile[cli]`).
- No GPU or accelerator substrate applies. The negative control in Capability discrimination is the only substrate control required.
