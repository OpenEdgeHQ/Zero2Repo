### Product overview

**`prosecheck`** is a local detector for AI-writing patterns. It is a command-line tool and an agent plugin. There is no website and no hosted version. Nothing the user writes is uploaded; there is no account; no text leaves the machine.

A first-time user installs the `prosecheck` plugin into a coding agent, restarts, and runs `/prosecheck` `doctor`. When the install is sound and the tool is on, the doctor answers with four successful-check lines. From then on, two layers work together. A writing contract is placed in the session (and into any subagent) so prose deliverables are shaped as they are written. After a supported file-edit tool saves a prose file, a saved-file guard scores the first 262,144 characters of extracted prose against a catalogue of 71 documented patterns and, when the score is above the active threshold, names the flagged spans and asks for them to be fixed. The same detector can be run by hand on a file path or on standard input.

The finished product is a **Python standard-library detector command** plus **Node.js plugin hooks**. There is no installable Python package, no compiled extension, and no runtime third-party dependency. The detector needs Python 3.9 or newer. The plugin’s saved-file and command hooks need Node.js. Analysis is local: the runtime contains no network client and no telemetry. There is no model and no random component in the default scan. Prose only, never code.

The score is a triage heuristic on the writing in front of the detector, not a calibrated authorship classifier. A score, a band, and a hook phrase describe prose; they do not name a person or a model as the author.

Exact argv spellings of optional detector switches, per-finding label strings, per-hook JSON field names, and per-subcommand reply shapes belong with those symbols, not here.

**Layout.** Callers do not import a Python module to reach the product. They spawn the host Python interpreter against `scripts/detect.py`, and they fire plugin hooks by spawning Node against the shipped files under `hooks/`. When a hook runs the detector, it finds the host Python interpreter by looking up `python3`, then `python`, then `py` on the `PATH` it was given, not by a fixed absolute path.

### Shape of the public surface

The public, independently verifiable surfaces are a **command-line detector** and a companion **agent plugin**. There is no network service and no wire protocol of the product’s own.

**Detector command.** Invocation is the host Python interpreter followed by `scripts/detect.py`, then optional switches and at most one file operand. A file path or empty argv (standard input) in; a structured report, scrubbed text, a usage message, or a structured error out.

- Readable non-empty extracted prose prints a structured report on standard output and exits 0. The report has two kinds of content: **findings** and **metrics**. Encoding of that structured mapping is the implementer’s: it is not a required JSON spelling and not a required field name.
- No path means the detector reads standard input. Standard input and standard output use UTF-8. A leading UTF-8 byte-order mark is not part of the prose. UTF-16 with a byte-order mark is decoded as text. A buffer that is not UTF-16 and contains a NUL byte is not text.
- Optional switches, discovered from the usage message rather than from a required flag spelling: a cleanup / scrub switch (prints scrubbed text instead of the report); a resampled-interval / resample switch (adds a low/high interval on the score when the document has at least four sentences). The end-of-options token `--` stops option parsing so a file name may begin with a dash.
- A help switch or a short help alias prints the usage message to standard output and exits 0. Usage names the cleanup switch, the interval switch, the double-dash `--`, and the single-file operand (a file / path / document name on the synopsis — not the word `input`, and not an `[options]` placeholder).
- Cleanup of document files prints extracted plain text, not a rebuilt archive. Redirecting that output onto the original path would replace the document with loose text.

**Twenty supported formats.** Plain text: `.md`, `.mdx`, `.markdown`, `.txt`, `.text`, `.rst`, `.tex`, `.org`, `.adoc`. Zip-based documents: `.docx`, `.docm`, `.pptx`, `.pptm`, `.xlsx`, `.xlsm`, `.odt`, `.odp`, `.ods`, `.epub`. Notebook: `.ipynb`. Plain text is accepted up to 512 KB. Zip-based documents and notebooks are accepted up to 4 MB. Those caps are file size on disk as the plugin enforces them, in binary units: 512 KB is 524,288 bytes and 4 MB is 4,194,304 bytes (4096 KB). A file whose size equals its cap is accepted; one byte more is over the cap. The detector command itself reads a path it is given. `.pdf` and `.rtf` are not among the twenty; they yield no extracted prose. The extracted prose of a zip-based document or a notebook does not begin or end with whitespace: line breaks sit only between its paragraphs, slides, cells, chapters, or markdown cells, so a single paragraph extracts as exactly its visible text. The 262,144-character window is measured on that text.

**Plugin hooks.** Host events send JSON on standard input. Named entries and the shipped files under `hooks/`:

- session-start — `prosecheck-activate.js`
- prompt-submit — `prosecheck-tracker.js`
- subagent-start — `prosecheck-subagent.js`
- post-tool-use — `prosecheck-guard.js`
- stats — `prosecheck-stats.js`

The prompt-submit hook is also the `/prosecheck` command router. A marketplace install namespaces the command as `/prosecheck:prosecheck`; both forms behave the same. When the doctor's closing line points at `show`, when that closing line points at turning the tool on, and when `init` replies that it is switched off, that follow-up uses the form the user typed. The help list, the mode line's pointer at `on`, and the doctor's request to run `doctor` again after a fault keep the non-namespaced spelling `/prosecheck`. A reply that puts the typed form on every command line does not meet those three surfaces. Subcommands are exactly: `lite`, `full`, `strict`, `off`, `on`, `status`, `show`, `check`, `doctor`, `stats`, `init`, `help`. A bare `/prosecheck` (or `/prosecheck:prosecheck`) is help.

**Exported contract files.** `/prosecheck` `init` writes the writing contract into `AGENTS.md` in the current working directory and copies the shipped Cursor rule to `.cursor/rules/prosecheck.mdc` when that file does not yet exist. The Cursor rule’s front matter limits it to prose globs (`*.md`, `*.mdx`, `*.markdown`, `*.txt`, `*.rst`, `*.tex`, `*.org`, `*.adoc`) and does not include `*.py`, `*.js`, `*.ts`, or `*.json`.

**Not in this surface.** A website, account, or hosted API. An installable Python distribution. A compiled native extension. Rewriting a `.docx`, `.epub`, `.odt`, or `.ipynb` in place when cleanup is requested. The bundled skill’s rewrite instructions as a detector obligation. The recorded-session demo, the documentation checker, the public benchmark harness, and the status-line helper.

### Naming conventions

**Product.** The product identity is `prosecheck`. The detector script path from the working-directory root is `scripts/detect.py`. Plugin hooks live under `hooks/` with the filenames listed above.

**Bands.** Five named ranges of the 0–100 score, each describing the prose, never an author: `clean` (0–20), `light tells` (21–40), `mixed` (41–60), `heavy tells` (61–80), `pervasive tells` (81–100).

**Hook phrases.** The plugin’s plain-language rendering of a band: `reads clean`, `reads mostly clean`, `reads with some AI tells`, `reads with heavy AI tells`, `reads with pervasive AI tells`. User-visible phrases use “reads …” rather than “was written by …”.

**Confidence.** Closed set: `none`, `low`, `moderate`, `high`. When confidence is not `high`, metrics carry a reason a caller can read. Wording of that reason is not pinned.

**Operating level.** The one-word mode stored for the install: `lite`, `full`, `strict`, or `off`. Default when nothing valid is stored is `full`. Any stored value other than those four words is ignored. The environment may supply one of those four words as `PROSECHECK_DEFAULT_MODE`.

**Catalogue.** 71 documented patterns, numbered 1 through 71. When a machine-checked pattern fires, the finding’s label identifies that numbered kind; two reports are told apart by which numbered kind the label points at, not by whether the label copies a listed title string. Catalogue 17 may be labeled as either of its two forms or as the combined title. The nine numbers with no detector — 7, 9, 28, 29, 43, 45, 49, 52, 53 — never appear as findings. Of the remaining 62, twelve are writing advice (reported, weight zero): 4, 19, 22, 41, 42, 46, 54, 55, 58, 60, 61, 68.

**Host environment.** Plugin config directory: `CLAUDE_CONFIG_DIR`. Plugin root (the built tree that contains `scripts/detect.py` and the `hooks/` files): `CLAUDE_PLUGIN_ROOT`.

**Config filenames** under the plugin config directory: the one-word level flag `.prosecheck-active`; session ledger files whose names are `.prosecheck-ledger` or start with that prefix followed by a hyphen.

### Global observables an implementer must reproduce

**Process exits (detector).**

- Readable non-empty extracted prose, help that prints usage, cleanup that prints scrubbed text, and a two-or-more-file run that still scans the first file: exit 0.
- Empty extracted prose (empty standard input, a file that decodes to nothing, a notebook with no markdown cells, an empty archive, `.pdf`, `.rtf`, and a NUL non-text buffer) fails: non-zero exit, a structured error on the error stream, no traceback, and no structured success report on standard output. Those named empty sources share one identifying kind with each other. Encoding of the structured error is the implementer’s: not a required JSON spelling and not a required field named `error`.
- An unreadable path, or a file whose extension is a supported archive type but whose bytes are not a readable zip, shares that failing-status family (the same non-zero status as empty input, not the unknown-option status) and the no-traceback structured-error shape, but a different identifying kind from empty input.
- An unknown option fails with a distinct failing status from empty input, a structured error that identifies the unknown option and points at help, and no traceback.

**Streams and encoding.**

- Standard input and standard output are UTF-8. A successful report’s standard output decodes as UTF-8.
- Failure does not print a traceback or other multi-frame dump on the error stream.
- Two or more file operands: the first file is scanned (exit 0), and the error stream states that only one file at a time is supported and names the file that was scanned. A silent drop of the extra files is not this product.

**Structured success report.**

- Findings: each fired machine-checked pattern carries a human-readable label that identifies the numbered kind, a positive hit count, and up to three short samples drawn from the scanned text. Unfired numbers are omitted. The nine no-detector numbers never appear.
- Metrics always include: characters scanned (capped at 262,144); a two-valued indication of whether the extracted prose was longer than that window (the “not longer” value when extracted prose is at most 262,144 characters; the “longer” value when it exceeds that window), distinguishable from the scanned count, the score, the band, and the confidence — encoding of that indication is open and is not a leftover-length field that grows with extra bytes, and not a required field name; the integer score from 0 through 100; the band name from the five-name set; a confidence label from the four-name set and, when confidence is not `high`, a readable reason; a count of fired findings; and character-layer counts for invisible/zero-width characters, non-standard spaces, and mixed-script lookalikes.
- The band name agrees with the score’s range.
- Findings, including character-layer findings, are computed only on the 262,144-character prefix. A mark that sits only past that window does not appear as a finding. A file of exactly 262,144 characters is still scored and carries the “not longer” value, with scanned count 262,144. A file of 262,145 or more characters is still a structured success, carries the “longer” value, and reports 262,144 scanned.
- When the resampled-interval switch is on and the document has at least four sentences, metrics include a low/high interval on the score. That interval does not replace the point score. With fewer than four sentences, the interval is omitted and the metrics state that there are too few sentences. The resampling count and seed are the implementer’s. Presence or absence of the interval does not change the point score.
- The same extracted prose, on the same detector, produces the same report. There is no model and no random component in the default scan.

**Cleanup versus report.**

- Without the cleanup switch, the character layer is reported as findings and as metrics counts; it is not applied to the text.
- With the cleanup switch, standard output is the scrubbed text, not the structured report, and the process exits 0. Empty input still fails.

**Network.**

- A detector scan opens no connection, including when HTTP/HTTPS/ALL proxy variables point at a local sink. Analysis is local.

**Plugin config and ledger.**

- The one-word level is stored as `.prosecheck-active` under `CLAUDE_CONFIG_DIR`. Valid contents are exactly `lite`, `full`, `strict`, and `off`.
- Every eligible guard attempt is recorded on the session ledger for that session id. The ledger holds the file’s base name only — never the document text and never the full path. Ledgers of different session ids are separate. A ledger whose last modification is more than seven days old is gone by the time a later session is in use. Ledger files are written with owner-only permissions.
- A hook that throws, receives malformed JSON, or cannot read the mode flag still exits successfully. It must not fail the host session. Malformed input is treated as an empty object.

**Portable export.**

- The contract exported by `/prosecheck` `init` does not embed this machine’s install path or user name. `init` while the level is `off` writes no files: not `AGENTS.md`, not the Cursor rule.

## `content`

Request field nested under `tool_input` on the post-tool-use hook (`prosecheck-guard.js`). Host JSON on a `Write` request includes a content string beside the saved path.

### Signature

```
{
  "`tool_name`": "`Write`",
  "`tool_input`": {
    "`file_path`": string,
    "`content`": string
  },
  "`cwd`": string
}
```

`content` is a string member of `tool_input`, next to `file_path`. It is part of the request object. The guard scores the saved file named by `file_path`; this string does not replace that path.

## `cwd`

Request field on the post-tool-use hook (`prosecheck-guard.js`). Host JSON on standard input places the working directory beside the tool name and the tool-input object.

### Signature

```
{
  "`tool_name`": "`Write`",
  "`tool_input`": {
    "`file_path`": string,
    "`content`": string
  },
  "`cwd`": string
}
```

`cwd` is a string at the top level of that object, beside `tool_name` and `tool_input` — not nested inside `tool_input`. When it is supplied, a relative `file_path` is resolved against it.

## `file_path`

Request field nested under `tool_input` on the post-tool-use hook (`prosecheck-guard.js`). It is the saved file’s path.

### Signature

```
{
  "`tool_name`": "`Write`",
  "`tool_input`": {
    "`file_path`": string,
    "`content`": string
  },
  "`cwd`": string
}
```

`file_path` is a string member of `tool_input`, not a top-level field. The guard scores the just-saved file at that path (eligible prose only). When the value is relative and `cwd` is supplied on the same request, the path is resolved against that directory.

## `prompt`

Request field on the prompt-submit hook (`prosecheck-tracker.js`). Host JSON on standard input names the submitted text as `prompt`. When the host supplies a session, the same object names it as `session_id`.

### Signature

```
{
  "`prompt`": string,
  "`session_id`": string
}
```

`prompt` is a string. For operator commands the value is the slash command, including `/prosecheck` `check` followed by a file path, and `/prosecheck` `show`.

`session_id` is a string beside `prompt`, not nested inside the prompt text. `/prosecheck` `show` with that value reads the ledger recorded for that session. A different `session_id` is a different ledger; rows from one session are not listed for the other.

The hook reads those fields from the JSON object on standard input. Command replies are observed as string values walked from a JSON envelope on standard output. Envelope field names and the wording of `check` / `show` bodies are not pinned. The process exits successfully.

## `tool_input`

Request field on the post-tool-use hook (`prosecheck-guard.js`). Host JSON on standard input nests the tool’s arguments under `tool_input`.

### Signature

```
{
  "`tool_name`": "`Write`",
  "`tool_input`": {
    "`file_path`": string,
    "`content`": string
  },
  "`session_id`": string,
  "`cwd`": string
}
```

`tool_input` is an object, not a string, and not a top-level path. It sits beside `tool_name`, `session_id`, and `cwd`. Its members on a `Write` request are `file_path` and `content`.

A `NotebookEdit` request names the notebook with `notebook_path`, a string member of this same object. An `apply_patch` request names the patch body with `command`, a string member of this same object. That `command` member is the patch-body field. It is not the slash command carried by `prompt`.

## `tool_name`

Request field on the post-tool-use hook (`prosecheck-guard.js`). Host JSON on standard input names the file-edit tool as `tool_name`. When the host supplies a session, the same object names it as `session_id`.

### Signature

```
{
  "`tool_name`": "`Write`",
  "`tool_input`": { ... },
  "`session_id`": string,
  "`cwd`": string
}
```

`tool_name` is a string at the top level of that object, beside `tool_input`, `session_id`, and `cwd`. For a saved-file Write the value is `Write`. `session_id` is a string sibling of `tool_name`, not a member of `tool_input`. The ledger written for that attempt is the one `/prosecheck` `show` reads when the same `session_id` is supplied beside `prompt`.

## `/prosecheck`

Operator command on the prompt-submit hook (`prosecheck-tracker.js`). The submitted text is the `prompt` string. A marketplace install also accepts the namespaced spelling. Both spellings run the same router, and a follow-up that echoes the command uses the spelling the user typed, except where a line below keeps the non-namespaced spelling.

### Signature

```
`/prosecheck`
`/prosecheck` <subcommand> [argument]
`/prosecheck:prosecheck`
`/prosecheck:prosecheck` <subcommand> [argument]
```

Subcommands are exactly `lite`, `full`, `strict`, `off`, `on`, `status`, `show`, `check`, `doctor`, `stats`, `init`, `help`. A bare invocation, with no subcommand, is `help`.

### Block decision

A command prompt is not sent on as an ordinary message. Standard output is one JSON object and the process exits successfully:

```
{
  "`decision`": "`block`",
  "`reason`": string
}
```

`reason` is the command reply. Joining every string in the object is not that reply. A prompt that is not a command does not use `decision` `block`.

### Unknown word

An unknown subcommand word is reported as unknown: the typed word and the word `unknown` sit together in the reply, and the reply lists every subcommand above as its own word. The stored level does not change. The reply is not empty.

### Stop phrases

The entire prompt `stop prosecheck`, or the entire prompt `prosecheck off`, stores `off` and the reply names `off`. Comparison ignores case. The same words with any extra token before or after are an ordinary prompt: they do not store `off`, and they are not a block decision.

### Ordinary prompts

A prompt that is not a command and not one of those two stop phrases falls through to the writing-contract reminder. When the stored level is `off`, that prompt produces no output. When the stored level is not `off`, the reminder still names the stored level, and it is not a block decision.

### Shipped menu document

The slash command is also a host menu document, not a program. After an optional front-matter block — a leading line that is only `---`, closed by a later line that is only `---` — the body is a prompt template. That body begins with `/prosecheck` followed by whitespace. The next token is `$ARGUMENTS`, not one of the twelve subcommands. The host replaces `$ARGUMENTS` with the user’s full argument string and submits the resulting prompt to this router. A level word in that string changes the stored level. A body that does not contain `$ARGUMENTS` does not forward: those arguments are not in the prompt the router parses, so the stored level stays as it was.

### Stored level

`lite`, `full`, and `strict` store that word. `off` stores `off`. `on` stores `full`. The word is the one-word mode flag `.prosecheck-active`. When no valid word is stored, the level is `full`. `check`, `doctor`, `show`, `stats`, and `init` do not open a network connection.

## `help`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. A bare invocation of either form is this same reply. The reply is the block `reason`.

### Signature

```
`/prosecheck`
`/prosecheck` `help`
`/prosecheck:prosecheck`
`/prosecheck:prosecheck` `help`
```

### What the reply contains

The reply names the live stored level. After the stored level changes from `full` to `strict`, the reply contains more standalone occurrences of `strict` and fewer of `full` than it did before the change.

It lists every subcommand except `help`: `lite`, `full`, `strict`, `off`, `on`, `status`, `show`, `check`, `doctor`, `stats`, `init`. Each of those words appears as its own word on a line that contains the non-namespaced command `/prosecheck` followed by that word. A namespaced help reply keeps that non-namespaced spelling on those lines. `help` is not listed in that subcommand slot. `off` and `on` may share one line. Each listed command occupies exactly one such line.

The reply states that `code`, `commits`, `config`, and `chat` are never touched (the word untouched, or a denial of touch, in the same statement as each of those four words).

It contains the phrases `prosecheck this` and `humanize this`.

On the single line that contains `/prosecheck` `lite`: contract only, and no file scoring. That line does not show the integers 40 or 20.

On the single line that contains `/prosecheck` `full`: contract plus guard, the integer 40, and that this guard at 40 is the default.

On the single line that contains `/prosecheck` `strict`: the word guard, the integer 20, and character scrub.

On the `off` / `on` line or lines: disable and re-enable.

On the single line that contains `/prosecheck` `check`: it scores a file and does not rewrite.

On the single line that contains `/prosecheck` `doctor`: health check.

On the single line that contains `/prosecheck` `stats`: session token use, and an own-prose score.

On the single line that contains `/prosecheck` `init`: the path `AGENTS.md`, and that the command writes the contract for other agents.

Wording around those claims may vary. The line still has to state the claim.

## `status`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `status`
`/prosecheck:prosecheck` `status`
```

The reply is one line. That line names the stored level and no other stored level. The stored levels are `lite`, `full`, `strict`, and `off`. The same single line is the only line of the whole delivery that names a stored level. A level stored by either command spelling is what the other spelling’s `status` reports.

## `lite`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `lite`
`/prosecheck:prosecheck` `lite`
```

Stores the level `lite` and the reply names `lite`. A later `status` reports `lite` on one line.

## `full`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `full`
`/prosecheck:prosecheck` `full`
```

Stores the level `full` and the reply names `full`. A later `status` reports `full` on one line. `full` is also the level stored when nothing valid is stored yet, and the level stored by `on`.

## `strict`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `strict`
`/prosecheck:prosecheck` `strict`
```

Stores the level `strict` and the reply names `strict`. A later `status`, on either command spelling, reports `strict` on one line.

## `off`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `off`
`/prosecheck:prosecheck` `off`
```

Stores the level `off` and the reply names `off`. The reply is not empty. A later `status` reports `off` on one line. After this command, an ordinary non-command prompt emits nothing.

The entire-prompt phrases `stop prosecheck` and `prosecheck off` store the same level. They are not this subcommand; extra tokens around those phrases do not store `off`.

## `on`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. The reply is the block `reason`.

### Signature

```
`/prosecheck` `on`
`/prosecheck:prosecheck` `on`
```

Stores the level `full`, not a separate stored word. The reply names both `on` and `full`. A later `status` reports `full` on one line and does not report `on` as the stored level.

## `check`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. It scores one file and does not rewrite it. The reply is the block `reason`. The file’s bytes are unchanged on every outcome below.

### Signature

```
`/prosecheck` `check` [path]
`/prosecheck:prosecheck` `check` [path]
```

The path argument is one token after surrounding quotes and one leading `@` are stripped. Accepted spellings of the same path, each on its own, are: the bare path; the path inside one pair of double quotes; the path inside one pair of single quotes; `@` immediately before the bare path; `@` immediately before the double-quoted path; `@` immediately before the single-quoted path. Quotes that wrap the `@` are not one of those spellings.

### Report

A readable file inside the size cap prints a report-only summary. The reply contains the base name, the hook phrase for the detector’s band, the band name, the confidence word, and the integer score from 0 through 100. Confidence words are `none`, `low`, `moderate`, and `high`. Band names are `clean`, `light tells`, `mixed`, `heavy tells`, and `pervasive tells`. Hook phrases are `reads clean`, `reads mostly clean`, `reads with some AI tells`, `reads with heavy AI tells`, and `reads with pervasive AI tells`. The reply does not contain `was written by`. It states that the result is a report only.

When confidence is not `high` and the detector supplied a reason, that reason text is in the reply. When confidence is `high`, a reason is not required.

When the detector fired more than eight labels, the reply shows at least one and at most eight of those labels, each with its hit count. When no pattern fired, the reply has a visible indication that nothing fired (a denial next to pattern, tell, label, or hit). Labels that did not fire are absent.

A coverage line is present only when extracted prose is longer than 262,144 characters. That line shows 262144 or 262,144, a leading-span word (first or prefix), and a limitation word (only or include). When extracted prose is exactly 262,144 characters, that window is not named and that coverage statement is absent. The file is still scored.

Plain text (`.md`, `.txt`) at 400 KB is scored. A `.docx` or notebook between the 512 KB and 4 MB caps is scored and the reply names that file’s base name. The same detector the command line runs is the score, band, phrase, confidence, and labels this summary shows.

### Without a path

`check` with no path returns a non-empty reply that contains no score from 0 through 100. That reply is not the unknown-subcommand reply. Whether it asks for a path is open.

### Not scored

These replies contain no score from 0 through 100, and they stay different from each other once the path and its base name are removed:

- A directory is reported as not a file.
- A path that is not on disk is reported as cannot read, and the path string itself is in the reply.
- `.pdf` and `.rtf` are the same report: no readable text. That report is not the directory report and not the missing-path report.

A plain-text file over 512 KB names 512 next to an over-cap word (over, above, beyond, or exceed) and has no score. A `.docx`, `.pptx`, or notebook over 4 MB names that cap in kilobytes as 4000 or 4096, or both, next to an over-cap word, and has no score.

If Python cannot be launched, the reply says the detector is unavailable and has no score. That reply is not the cannot-read reply and is not a no-report statement.

If the detector exits without failure and produces no output, the reply names the base name and says there was no report. If the detector exits without failure and prints text that is not a report, the reply says there was no report and does not name the file. If the detector exits with a failure, the reply names the base name and reports a failure. When that failed run wrote text on its error stream, that text is in the reply. When it wrote none, the reply still names the file and reports a failure, and that report is not the no-report statement. The exit status is not required.

## `doctor`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. It is a health check. The reply is the block `reason`. It runs the bundled detector; a reply that claims success without that run is not this check.

### Signature

```
`/prosecheck` `doctor`
`/prosecheck:prosecheck` `doctor`
```

### Shape

The first non-empty line is a title. The last non-empty line is the closer. The non-empty lines between them are the four checks, in any order: current mode, bundled detector present, Python running the detector, settings folder writable. A successful check carries one marker token. That token’s spelling is open. It sits on every successful check line of a healthy reply and does not sit on the closer. A faulty check line does not carry it. Each of the four checks is a different line.

### The four checks

Current mode names the stored level (`lite`, `full`, `strict`, or `off`) and no other stored level. When the level is not `off`, this line is successful. When the level is `off`, this line does not carry the success marker; it names `off` and `on`, and it points at the non-namespaced command `/prosecheck` `on`. `off` is not a fault of the install.

Detector present names the detector and that it is present (present, found, exists, available, or installed), without a denial. This line does not name Python. It stays successful when Python cannot be launched, and it does not carry the Python-missing report. When the bundled detector is not in the plugin tree, this line is the faulty one and does not affirm presence.

Python running the detector names Python and the detector, without a denial that Python ran. The line is successful only when that run produced a numeric score. It does not have to print the score. When the run returns text that is not a numeric score, this line is the faulty one, names Python, and is not the Python-missing statement. When Python cannot be launched, this line is faulty: it names Python together with that absence (Python is missing, or a denial that Python was found; the token missing is not required), states that prose is still shaped, and states that saved files are not re-scored. A denial that Python was found is not a failure.

Settings folder writable names the two words settings folder (a hyphen is the same name) and says the write can happen, without a denial. A line that only says directory, or only one of those two words, is not this check. When the settings folder is not writable, this line is faulty: it names settings folder and denies the write, it does not name Python, and it does not carry the success marker.

### Closers

When all four succeed and the mode is not `off`, the closer affirms that the tool is on. The subject is the noun tool or the pronoun it; the noun is not required. “is” may be its own word or contracted onto that subject. A negation between the subject and `on` is not that affirmation. The closer names 512, names the 4 MB cap as 4 MB (the digit 4 followed by MB; a space between them is optional — a kilobyte figure such as 4096 is not this rendering), names the 262,144-character window as 262144 or 262,144, and points at `show` in the form the user typed (`/prosecheck` `show` or `/prosecheck:prosecheck` `show`) for partial or skipped checks. Partial, skipped, and check sit with that show command.

When any check is faulty, the closer contains the non-namespaced command `/prosecheck` `doctor`, asks for those lines to be fixed, and asks for doctor to be run again. It does not use the healthy closer and it does not deny that anything is wrong.

When the only issue is that the mode is `off`, the other three checks stay successful, and the closer denies that anything is wrong (nothing with wrong; the noun install is not required) and states that saved files are not scored. It points at turning the tool on in the form the user typed: `/prosecheck` `on` or `/prosecheck:prosecheck` `on`. That statement is not the not-re-scored wording used when Python cannot be launched. The word until is not required.

## `show`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. It lists this session’s ledger, newest first. The reply is the block `reason`. The session is the `session_id` on the same prompt-submit object. A different `session_id` is a different ledger.

### Signature

```
`/prosecheck` `show`
`/prosecheck:prosecheck` `show`
```

The ledger holds base names only. The reply does not contain a parent-directory name and does not contain the document body.

### Empty ledger

An empty ledger says nothing has been scored yet, and that the list fills in once a prose file or a deliverable is saved. The reply contains `.docx` and `.pdf`. It contains no score from 0 through 100, and it does not name a file that was not saved.

A ledger whose last modification is more than seven days old is not listed after a later session starts; that later `show` is the empty-ledger reply. A ledger last modified exactly seven days ago, or more recently, is still listed. Younger than seven days is still listed.

### Scored row

A scored row shows the base name, the hook phrase, the integer score, and the band. Hook phrases and band names are the same set `check` prints. The row does not contain `was written by`.

When the row has pattern labels, it also says whether the file was flagged or was under the threshold, and it shows at least one and at most five of those labels. Flagged is the word flagged, affirmed. Under the threshold is the words under and threshold, affirmed. A flagged row does not say under the threshold, and an under-threshold row does not say flagged. A scored row with no labels shows the hook phrase, the score, and the band, and does not add the flagged clause or the under-threshold clause.

When the scan was truncated, the row names the 262,144-character window (262144 or 262,144) and states that only that prefix was included. A row for exactly 262,144 characters does not name that window.

Rows are newest first. That order is save order, not base-name order and not score order.

### Other rows

A size skip says the file was not scored and names the limit in kilobytes: 512 for plain text over 512 KB, and 4000 or 4096 for an archive or notebook over 4 MB. It has no score from 0 through 100.

A binary row, such as `.pdf`, says the file was not re-scored. A failed row says it was not scored and gives a reason a person can read. The size-skip remainder, the binary remainder, and the failed remainder are three different texts. None of them is a scored row.

## `init`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. It writes the writing contract into the project that is the process’s current working directory. The reply is the block `reason`. It opens no network connection.

### Signature

```
`/prosecheck` `init`
`/prosecheck:prosecheck` `init`
```

### When the level is off

No files are written: not `AGENTS.md`, and not `.cursor/rules/prosecheck.mdc`. Files that already exist are left byte for byte. The reply names `off`, says it is switched off, and says that `on` enables export. That follow-up is the on command in the form the user typed: `/prosecheck` `on` or `/prosecheck:prosecheck` `on`.

### When the level is not off

Two writes, independent of each other.

`AGENTS.md` in the working directory receives the writing contract, appended after any text already in the file. Those earlier bytes stay as the prefix of the file. The contract is one section, so a second `init` does not add another copy. The section is recognised by that single copy of the contract, not by a required marker spelling. If the section is already present, the reply says it is already present and the file is not changed.

The exported contract does not contain this machine’s detector path and does not contain the user name. At `full` and at `strict` one resolution paragraph tells the other agent how to resolve the bundled detector. That paragraph states both conditions: use the host plugin-root variable `CLAUDE_PLUGIN_ROOT` when that variable is set, and otherwise locate the detector in installed `skills` and `plugins`. Export writes that same paragraph whether or not `CLAUDE_PLUGIN_ROOT` is set when `init` runs. A requirement that the set case and the unset case be different texts does not meet this entry. At `lite` that resolution paragraph is absent: the export does not include it, and it does not name `skills`, `plugins`, or `CLAUDE_PLUGIN_ROOT`, and it does not show the integer 40 or the band `light tells`. Including that paragraph at `lite` does not meet this entry. At `full` the export shows 40 and the full scoring target, and it does not name the cleanup switch. At `strict` the export names the cleanup switch and keeps the strict band apart from the lite export.

`.cursor/rules/prosecheck.mdc` is copied from the shipped Cursor rule when that file does not yet exist. If it exists, the reply says the rule is already there and the bytes are not overwritten. The two writes are independent: an existing contract section still receives a missing rule, and an existing rule still allows `AGENTS.md` to be written when the section is absent.

The rule opens with a front-matter block delimited by lines that are only `---`. Inside that block the glob list is exactly the eight prose globs `*.md`, `*.mdx`, `*.markdown`, `*.txt`, `*.rst`, `*.tex`, `*.org`, and `*.adoc`. It does not include `*.py`, `*.js`, `*.ts`, or `*.json`. The body is prose-only scope and the banned-vocabulary list from the writing contract. It does not show the integer 40, does not name `light tells`, and does not tell the agent to run the detector after a write.

### Cannot read or write

If `AGENTS.md` cannot be read, or cannot be written, the reply says it cannot, and the file is not given the contract. If the Cursor rule cannot be written, the reply says it cannot write, and the rule file is not created. A failed write is not reported as the successful export.

## `stats`

Subcommand of `/prosecheck` and of `/prosecheck:prosecheck`. It prints session token use and, when the scored slice is long enough, an own-prose score. The reply is the block `reason`. It opens no network connection.

### Signature

```
`/prosecheck` `stats`
`/prosecheck:prosecheck` `stats`
```

The transcript is the host-named `transcript_path` on the same prompt-submit object when that member is supplied. Otherwise it is the newest `.jsonl` file under the `projects` folder of `CLAUDE_CONFIG_DIR`, chosen by modification time, not by name. A named path wins over a newer file in that folder.

### Transcript rows

The file is JSON lines. An assistant row has `type` `assistant` and a `message` object. Token totals are the sums of `output_tokens` and `cache_read_input_tokens` on that message’s `usage` object. Text is taken from `content` entries whose type is text.

A row whose `type` is not `assistant` contributes no tokens, no turn, and no prose text. Its usage is not part of either token total. Its text does not enter the scored slice and does not move the session-prose score.

Assistant rows that share one `message` `id` contribute one turn and one copy of those token totals. The text of every one of those assistant rows still enters the scored slice. A row with no identifier is counted on its own.

### Reply

When a transcript can be read, the reply names the stored level, the assistant-turn count, the output-token total, and the cache-read input-token total. Each total is attributed to its own quantity. When the two totals are different integers, exchanging them changes the reply once the host-named transcript text is removed, and both integers remain. A reply that contains both integers and is unchanged by that exchange does not meet this entry. A raw usage field that happens to print the same integer does not stand in for the total. No particular label, order, or phrase is required.

A readable transcript with no assistant row still names those three quantities, and they are 0.

The scored slice is assistant text with fenced blocks removed (a fence opens and closes with three backticks), then only the last 40,000 characters, then surrounding whitespace trimmed. A session-prose score is printed only when that slice is longer than 200 characters. A slice of 200 characters after trimming has no session-prose score. One more character does, and that integer is the detector’s score of that slice.

### Missing transcript

A path that is not a readable transcript yields a non-empty reply with no assistant-turn count and no token totals. Digits that only name the host-named transcript are not those quantities. An integer that is none of those three may remain. Naming the stored level, or leaving it out, does not fail the reply.

## `transcript_path`

Request field on the prompt-submit hook (`prosecheck-tracker.js`). Host JSON on standard input may name the session transcript beside `prompt`.

### Signature

```
{
  "`prompt`": "`/prosecheck` `stats`",
  "`transcript_path`": string
}
```

`transcript_path` is a string at the top level of that object, beside `prompt`. It is not nested inside the prompt text. `/prosecheck` `stats` and `/prosecheck:prosecheck` `stats` read the transcript at that path. When the member is absent, `stats` uses the newest transcript under the config directory’s `projects` folder instead.
