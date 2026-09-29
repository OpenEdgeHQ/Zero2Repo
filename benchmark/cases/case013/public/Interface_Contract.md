### Product overview

**MEMBUNDLE Agent Memory** is a domain-neutral, Git-native persistent project memory for AI agents, based on the Open Bundle Format (MEMBUNDLE) v0.2. Durable project knowledge lives as an on-disk MEMBUNDLE v0.2 knowledge bundle of plain-text Markdown files so later sessions can retrieve decisions, facts, and runbooks without stuffing the entire corpus into a system prompt.

The Dual-Memory Bundle Architecture (DMBA) splits that memory into two layers a caller can observe as files and tools:

- **Normative working memory (push layer).** A compact `AGENTS.md` codex, written in Bundle Action Grammar (MBG), that states invariants, tone, and search-before-write triggers. It is ordinary project text, not a hidden database.
- **Semantic domain memory (pull layer).** An MEMBUNDLE v0.2 bundle, conventionally a directory named `knowledge`, that is not injected in full at session start. Callers retrieve selected concepts through search and show operations, and persist new knowledge through create, update, and relate operations.

The finished product is one self-contained executable named `membundle`. Callers reach each capability by choosing an `membundle` command. The same binary also runs as a Model Context Protocol server over standard input and standard output. The product is that binary plus the on-disk Markdown/YAML bundle layout it reads and writes. It is not an importable library API (neither a Python package nor a stable embeddable ABI). There is no required external database, embedding API, or network service for memory retrieval.

The product is **CPU-only**. Faithful implementation is a local `membundle` executable plus on-disk Markdown/YAML bundles. There is no accelerator substrate.

Exact flags, argument lists, and per-command return shapes belong with those commands, not here, except `create` / `membundle_create`, `update` / `membundle_update`, and `relate` / `membundle_relate`, whose public invocation is stated under Shape of the public surface.

### Shape of the public surface

The public surface is a **command-line tool plus a stdio protocol server**. There is no importable package for other programs.

**Binary.** Direct invocation is the executable `membundle` followed by a command token and that command’s arguments (for example `membundle` `init`). The default build artifact is `bin/membundle` under the built tree. Callers invoke that executable; they do not import Go packages or Python modules to reach the product.

**Commands.** Nested command tokens after `membundle`. The finite command set is: `validate`, `search`, `show`, `create`, `update`, `relate`, `init`, `bootstrap`, `agents`, `mcp`, `version` (also accepted as a version request), and `help`. Exact flags and return shapes for each command belong with those symbols, not here, except `create` / `membundle_create`, `update` / `membundle_update`, and `relate` / `membundle_relate`, whose public invocation is stated in this surface.

**Create invocation.** There is no per-command page for `create` / `membundle_create`. Command-line invocation is:

```
`membundle` `create` <identity> [path] [`--type` <type>] [`--title` <title>] [`--desc` <description>] [`--body` <body>] [`--tags` <tags>] [`--actor` <actor>] [`--no-log`] [`--no-index`] [`--json`]
```

- `<identity>` — required first positional concept identity.
- `[path]` — optional second positional bundle path. Omit-path uses the default bundle path rule below. A named path is the write root and does not apply the nested-load redirect.
- `--type`, `--title`, `--desc`, `--body`, `--tags`, `--actor` — optional. Each is followed by one value token. `--desc` supplies the description; it is not spelled `description` as a command-line flag.
- `--no-log` and `--no-index` — independent skip flags. Each takes no value token. `--no-log` skips the Creation bullet in `log.md`. `--no-index` skips parent-index bookkeeping.
- `--json` — optional. Takes no value token. On `create` this is structured create output that names this-run identity and a distinct path string. It is not the structured inspect record of `show`.

`tools/call` name `membundle_create`, arguments:

- `concept_id` — required string. The concept identity.
- `type` — required string.
- `title` — required string.
- `description` — optional string.
- `body` — optional string.
- `bundle` — optional string. Bundle path (same omit-path and named-path rules as command-line `create`).

`--type`, `--title`, `--desc`, `--body`, `--tags`, `--actor`, `--no-log`, `--no-index`, and `--json` are command-line flags. They are not `membundle_create` argument keys. `membundle_create` has no skip-log or skip-index argument and always writes the parent listing and the Creation bullet.

**Update invocation.** There is no per-command page for `update` / `membundle_update`. Command-line invocation is:

```
`membundle` `update` <identity> [path] [`--title` <title>] [`--desc` <description>] [`--body` <body>] [`--actor` <actor>] [`--no-log`] [`--no-index`] [`--json`]
```

- `<identity>` — required first positional concept identity.
- `[path]` — optional second positional bundle path. Omit-path uses the default bundle path rule below. A named path is the write root and does not apply the nested-load redirect.
- `--title`, `--desc`, `--body`, `--actor` — optional. Each is followed by one value token. `--desc` supplies the description; it is not spelled `description` as a command-line flag.
- `--no-log` and `--no-index` — independent skip flags. Each takes no value token. `--no-log` skips the Update bullet in `log.md`. `--no-index` skips parent-index bookkeeping, leaving an existing parent listing un-updated.
- `--json` — optional. Takes no value token. On `update` this is structured success output: structured success still rewrites the concept, the parent listing, and the Update bullet. It is not the structured inspect record of `show`.

`tools/call` name `membundle_update`, arguments:

- `concept_id` — required string. The concept identity.
- `title` — optional string.
- `description` — optional string.
- `body` — optional string.
- `bundle` — optional string. Bundle path (same omit-path and named-path rules as command-line `update`).

`--title`, `--desc`, `--body`, `--actor`, `--no-log`, `--no-index`, and `--json` are command-line flags. They are not `membundle_update` argument keys. `membundle_update` has no skip-log or skip-index argument and always writes the parent listing and the Update bullet.

**Relate invocation.** There is no per-command page for `relate` / `membundle_relate`. Command-line invocation is:

```
`membundle` `relate` <source> <target> [path] [`--desc` <prose>] [`--actor` <actor>] [`--json`]
```

- `<source>` — required first positional source identity.
- `<target>` — required second positional target identity.
- `[path]` — optional third positional bundle path. Omit-path uses the default bundle path rule below. A named path is the write root and does not apply the nested-load redirect.
- `--desc`, `--actor` — optional. Each is followed by one value token. `--desc` supplies relationship prose; it is not spelled `description` as a command-line flag.
- `--json` — optional. Takes no value token. On `relate` this is structured success output: structured success still rewrites the source link and the Update bullet. It is not the structured inspect record of `show`.

`tools/call` name `membundle_relate`, arguments:

- `source_id` — required string. The source identity.
- `target_id` — required string. The target identity.
- `description` — optional string. Relationship prose.
- `bundle` — optional string. Bundle path (same omit-path and named-path rules as command-line `relate`).

`--desc`, `--actor`, and `--json` are command-line flags. They are not `membundle_relate` argument keys. `membundle_relate` takes `source_id` and `target_id`, not `concept_id`. `membundle_relate` has no actor argument and always writes actor `agent/mcp`.

**Agents subcommands.** Nested tokens after `agents` are exactly `lint`, `init`, `link`, and `check`.

**Stdio protocol server.** `membundle` `mcp`, given an optional bundle path (default bundle path rule below). The process reads newline-delimited JSON-RPC from standard input and writes newline-delimited JSON-RPC to standard output until input ends. It is not an HTTP server.

**On-disk bundle.** Commands that read or write memory operate on an MEMBUNDLE v0.2 bundle directory of Markdown files. The conventional bundle directory name is `knowledge`. Root reserved documents are `index.md` and `log.md`. A bundle-root `AGENTS.md` is a governance document, not a concept. Nested directory `index.md` files are navigation listings.

**Not in this surface.** An importable library. A network daemon. A required product configuration-file format. Homebrew packaging, release automation, and a separate benchmark runner.

### Naming conventions

**Product and executable.** The product identity is MEMBUNDLE Agent Memory. The executable basename is `membundle`. The format name may be spelled as the contiguous token `membundle` in any case, or as the phrase Open Bundle Format in any case. Version identity for the format is the scalar `0.2` or the token `v0.2`.

**Command names.** Command tokens after `membundle` are the lowercase names listed above. Hyphenated plumbing names are not used. Nested agents tokens are lowercase `lint`, `init`, `link`, and `check`.

**Default bundle path.** When the caller omits a bundle path, bundle-reading commands (`show`, `search`, `validate`, and other bundle-load commands), omit-path `init`, omit-path `create` (command line and `membundle_create`), omit-path `update` (command line and `membundle_update`), and omit-path `relate` (command line and `membundle_relate`) use the directory `knowledge` if that name is a directory in the current working directory; otherwise they use the current directory. A file named `knowledge` is not a directory, so the omit-path rule uses the current directory. When the caller names a path, that named path is the command’s target. If a named load path has no root `index.md` but does contain a `knowledge` subdirectory, loading resolves into that nested bundle. `init`, `bootstrap`, `create` (command line and `membundle_create`), `update` (command line and `membundle_update`), and `relate` (command line and `membundle_relate`) write at the named directory and do not apply that nested-load redirect. A named `create` path is the write root even when it has no root `index.md` and contains a `knowledge` subdirectory: the new concept file and the default parent-index and log bookkeeping files land under that named path and not inside the nested subdirectory; command-line human success and the `membundle_create` confirmation name the named path as the bundle, not only the nested `knowledge` spelling. A named `update` path is the write root even when it has no root `index.md` and contains a `knowledge` subdirectory that already holds the concept: the rewritten concept file and the default parent-index and log bookkeeping files land under that named path; those nested files remain as they were; command-line human success and the `membundle_update` confirmation name the named path as the bundle, not only the nested `knowledge` spelling. A named `relate` path is the write root even when it has no root `index.md` and contains a `knowledge` subdirectory that already holds both concepts: the rewritten source file and the log Update land under that named path; those nested files remain as they were; command-line human success and the `membundle_relate` confirmation name the named path as the bundle, not only the nested `knowledge` spelling. Omit-path `bootstrap` keeps the current working directory as the project and still writes `AGENTS.md`, the skill tree, and `Makefile` beside an already-present `knowledge` directory rather than inside it; a named `bootstrap` path remains the project even when the current working directory also contains `knowledge`; neither form applies the nested-load redirect.

**Reserved bundle documents.** `index.md` in any directory, the bundle-root `log.md`, and a bundle-root `AGENTS.md` are navigation or governance documents, not concepts. The product must not treat them as creatable concept identities and must not count a root `AGENTS.md` as a concept when loading a bundle.

**Concept identity.** A concept is one non-reserved Markdown file in the bundle. Its identity is the bundle-relative path without the `.md` suffix.

**Root index version key.** The root `index.md` YAML frontmatter mapping key that declares the format version is `membundle_version`. The declared scalar is `0.2`.

**YAML frontmatter fences.** Frontmatter is the YAML block at the start of a file, delimited by conventional triple-dash fence lines `---`.

**Recognized frontmatter fields.** The only field MEMBUNDLE v0.2 requires on a concept is a non-empty `type`. Other recognized fields include `title`, `description`, `tags`, `generated`, `verified`, `status`, `governance`, `code_refs`, `stale_after`, `sources`, and `resource`. Unknown fields must be tolerated and, when the product rewrites a concept, preserved.

**Governance values.** The closed set is `constraint`, `hold`, and `context`. If the file omits governance, identities under `convention` default to `constraint` and all other identities default to `context`. Declared values are compared case-insensitively and normalized to lowercase.

**Status values.** The validator accepts `draft`, `stable`, and `deprecated`.

**Actor strings.** Two forms are accepted: a producer-slash-version form whose two sides are both non-empty and contain neither spaces nor slashes (the product itself uses `agent/cli` for the command line, `agent/mcp` for the Model Context Protocol server, and `agent/membundle-tool` when the caller supplies an empty actor); or a prefix-colon-id form that starts with a letter, then zero or more letters, digits, underscores, dots, or hyphens, then a colon, then a remainder with no spaces.

**MCP tools.** The closed set is `membundle_search`, `membundle_show`, `membundle_create`, `membundle_update`, `membundle_relate`, and `membundle_validate`.

**MCP server identity.** The initialize reply names the server `membundle-agent-memory`. The Model Context Protocol version is `2024-11-05`.

**MBG lint rules.** The closed set is `MBG-001`, `MBG-002`, `MBG-003`, `MBG-004`, and `MBG-005`.

**MBG modal prefixes.** Accepted at the start of an invariant bullet: `MUST`, `MUST NOT`, `NEVER`, `PREFER`, `ALWAYS`, `SHOULD`, `MAY`, and a leading exclamation mark.

**Domain codex profiles.** For agents init: `software`, `research`, `legal`, `coaching`, `books`. An unrecognized profile is treated as `software`.

**Bootstrap-installed skill documents** under `.agents` / `skills` / `membundle-memory`: `SKILL.md`, `discovery.md`, `remember.md`, `update.md`, `relationships.md`, `examples.md`.

**SSoT link mappings** (link path → canonical target): `CLAUDE.md` → `AGENTS.md`; `.cursorrules` → `AGENTS.md`; `.windsurfrules` → `AGENTS.md`; `.github/copilot-instructions.md` → `../AGENTS.md`.

**MEMBUNDLE Agent Memory delimiters.** The HTML comments `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->` and `<!-- END MEMBUNDLE AGENT MEMORY -->` that bound the working-memory block inside `AGENTS.md`.

**Log date headings.** Dated sections in `log.md` use ISO 8601 calendar headings of the form year-month-day (four-digit year, two-digit month, two-digit day), taken from UTC, with newer days listed before older days.

### Global observables an implementer must reproduce

**Process exits and streams.**

- A successful run ends with POSIX status 0. Standard output and standard error are UTF-8 text.
- A command that does not succeed ends with a non-zero status. `init` of an uncreatable or unwritable target also writes a non-empty failure report on standard output and/or standard error. `bootstrap` of an uncreatable target — the named path’s parent is a regular file, or the named path exists as a regular file — ends with a non-zero status and nothing more; empty streams are allowed.
- For `validate` specifically: successful conformant gate-pass ends with status 0; non-conformance or a failed producer gate ends with status 1; failure to load the bundle ends with status 2.
- Exact report wording is not a fixed sentence. Per-command report contents belong with those commands.

**Encoding.** Bundle Markdown files and process streams are UTF-8. Bytes that are not valid UTF-8 are not product text.

**No product config file.** The tool does not require a configuration-file syntax of its own. The process environment variable `MEMBUNDLE_MCP_ROOT`, when set, names the Model Context Protocol workspace root. Calendar dates written into `log.md` use UTC even when the process environment `TZ` names a zone whose local calendar date differs from UTC.

**Root index file.** When the product creates a missing root `index.md`, that file begins with YAML frontmatter fenced by `---` lines. The mapping contains the key `membundle_version` whose stripped scalar is `0.2`. The body after the closing fence contains a Markdown heading with non-empty text. An already-present root `index.md` is left unchanged.

**Root log file.** When `init` creates a missing root `log.md`, that file’s first heading is today’s UTC calendar date in ISO 8601 year-month-day form, and the section under that heading contains a list item that names the format (`membundle` or Open Bundle Format) together with `0.2` or `v0.2`. An already-present root `log.md` is left unchanged by `init`. When `bootstrap` creates a missing bundle `log.md`, that file has a heading whose text is today’s UTC calendar date in ISO 8601 year-month-day form; that heading is not required to be the first heading in the file. The section under it contains a non-empty Markdown list item, and that item is not required to name the format or the version. An already-present bundle `log.md` is left unchanged by `bootstrap`, including a second bootstrap, a run that writes only a missing sibling, and an omit-path run that finds an existing `knowledge` directory. `create`, `update`, and `relate` append under today’s UTC date heading.

**Load exclusions.** Hidden files and directories (names beginning with a dot) and a directory named `node_modules` are not loaded as concepts and do not by themselves make the load fail. Only Markdown files are loaded. A symlink that is itself a Markdown file and whose resolved target leaves the bundle directory makes the load not succeed, including when that resolved target is a directory; search of that bundle then fails as a load error, and that failure is distinct from a successful search with no hit records. A symlink that is a directory, whose own name is not a Markdown file, and whose resolved target leaves the bundle directory is not walked; concepts that exist only through it are not loaded; the load still succeeds; search succeeds and those outside concepts are not hit records. That success is distinct from a load that does not succeed and from a search that returns an outside concept. A write whose resolved target leaves the bundle, including a write through a directory symlink, does not succeed. That write refusal is not the load outcome of that directory symlink.

**JSON-RPC stdio wire format.** Each non-empty standard-input line is one JSON-RPC message; each non-empty standard-output line is one JSON-RPC message. Empty input lines are ignored. The protocol is JSON-RPC `2.0` as used by the Model Context Protocol version `2024-11-05`.

- A request object carries `jsonrpc`, `id`, and `method`, and may carry `params`.
- A notification has no `id` and receives no reply.
- A JSON-RPC reply to a request that has an `id` carries that same `id`.
- A line that is not JSON is a JSON-RPC 2.0 parse error (code `-32700`) and does not crash the server.
- A request that carries an `id` whose method is unknown is JSON-RPC 2.0 method-not-found (code `-32601`).
- A notification (no `id`) for an unknown method produces no reply.
- A tools-call with unreadable parameters is JSON-RPC 2.0 invalid-params (code `-32602`).
- Tools list replies with exactly the six tools `membundle_search`, `membundle_show`, `membundle_create`, `membundle_update`, `membundle_relate`, and `membundle_validate`, and no additional memory-mutation tools.
- Tool success and tool-level failures are returned as MCP tool results (text content; failures marked as tool errors), not as a substitute for JSON-RPC protocol errors.

Per-command flags for commands that have their own pages, search ranking, and validate finding classes belong with those symbols, not here. Create’s command-line flags and `membundle_create` argument keys, update’s command-line flags and `membundle_update` argument keys, and relate’s command-line flags and `membundle_relate` argument keys, are stated in this surface.

## `--name`

Flag of `membundle` `bootstrap`. It takes one value token: the project name. The flag is optional.

### Signature

```
`membundle` `bootstrap` [path] [`--name` <name>] [`--no-bundle`] [`--no-skill`] [`--no-agents-md`] [`--no-makefile`] [`--overwrite-agents-md`]
```

- `[path]` — optional positional target project directory. When omitted, the project root is the current working directory. When present, that named directory is the project root. A missing named directory is created. Neither form applies the nested-load redirect into an existing `knowledge` directory: omit-path still writes `AGENTS.md`, the skill tree, and `Makefile` beside an already-present `knowledge` directory in the current working directory; a named path is the project even when the current working directory also contains `knowledge`.
- `--name` — optional. Followed by one value token. That value is the project name. It overrides the target directory’s base name.
- `--no-bundle`, `--no-skill`, `--no-agents-md`, `--no-makefile` — independent skip flags. Each takes no value token. Each omits only its own component; the others still install.
- `--overwrite-agents-md` — optional. Takes no value token. Requests overwrite of an existing `AGENTS.md` instead of non-destructive enrichment.

### Omitted `--name`

The project name is the target directory’s base name. If that base name is empty, `.`, or `/`, the name is `my-project`.

### Present `--name`

The supplied value is the project name. The knowledge-index heading and `AGENTS.md` contain that name, not the directory basename.

### Success report

On success the process reports which of the four components were not skipped, including when some of those files already existed and were left unchanged. The four identities are `knowledge`, `membundle-memory` (also accepted as `.agents` / `skills` / `membundle-memory`), `AGENTS.md`, and `Makefile`. Exact report layout is not pinned.

### Uncreatable target

If the target directory cannot be created — the named path’s parent is a regular file, or the named path exists as a regular file — `bootstrap` does not succeed and ends with a non-zero status.

`bootstrap` does not delete unrelated project files.

## `--no-makefile`

Independent skip flag of `membundle` `bootstrap`. It takes no value token.

### Signature

```
`membundle` `bootstrap` [path] `--no-makefile`
```

The optional `[path]` is the same target project directory as for `bootstrap` (current working directory when omitted; the named directory when present). This flag may be combined with `--name` (one value token), `--no-bundle`, `--no-skill`, `--no-agents-md`, and `--overwrite-agents-md`. Each skip is independent.

### Observable effect

Installing `Makefile` is omitted. That file is left uncreated. The other not-skipped components still install.

On success the process reports the not-skipped components. That success report is distinguishable from a full-run report because `Makefile` is not presented as installed. Exact report layout is not pinned. A skip rendering may still contain the word `Makefile`; it must not present that identity as installed the way a full run does.

## `--overwrite-agents-md`

Flag of `membundle` `bootstrap`. It takes no value token. When present, an existing `AGENTS.md` is overwritten with the product template instead of non-destructive enrichment.

### Signature

```
`membundle` `bootstrap` [path] `--overwrite-agents-md`
```

The optional `[path]` is the same target project directory as for `bootstrap` (current working directory when omitted; the named directory when present). This flag may be combined with `--name` (one value token) and the independent skip flags `--no-bundle`, `--no-skill`, `--no-agents-md`, and `--no-makefile`.

### Present

`AGENTS.md` is replaced by the product template. Caller rules that were in the previous file are gone. The written file contains the project name and the delimited MEMBUNDLE Agent Memory section.

### Omitted

Non-destructive enrichment:

- Missing `AGENTS.md` is written as the product template (project name and the delimited section).
- An existing file that does not already contain the phrase `BEGIN MEMBUNDLE AGENT MEMORY`, the substring `membundle-agent-memory`, or the phrase `Open Bundle Format (MEMBUNDLE)` is appended: original rules stay, and the delimited section is added after them. The original prefix is not replaced.
- An existing file that already contains any of those three strings is left unchanged. The begin marker is not duplicated.

## `my-project`

Fallback project name for `membundle` `bootstrap` when `--name` is omitted.

### When it applies

The project name defaults to the target directory’s base name. If that base name is empty, `.`, or `/`, the project name is `my-project`.

The constructable `/` target is that last case: omit `--name`, and the written `AGENTS.md` contains `my-project`.

### Where it appears

The fallback name is the project name substituted into a newly written or overwritten `AGENTS.md`, and into a newly written knowledge-index heading, the same way an explicit `--name` value or a normal directory basename is substituted.

## `--json`

Independent structured-output flag of `membundle` `show`. It takes no value token.

### Signature

```
`membundle` `show` <identity> [path] [`--json`] [`--raw`]
```

- `<identity>` — required positional concept identity.
- `[path]` — optional positional bundle path.
- `--json` and `--raw` — independent mode flags. Each takes no value token.

### Present

A successful run ends with POSIX status 0. Standard output is a parseable structured concept record. That record contains exact string values for the resolved identity (a trailing `.md` is stripped), the concept `type`, and the Markdown body after frontmatter. `membundle_show` returns that same parsed record. Structured inspect is not the human command-line presentation of inbound and outbound relationship lists.

A well-formed identity that is not in the bundle does not succeed, names that identity, and is not a successful structured record. A reserved or invalid identity is not a successful structured inspect.

The command does not create or mutate files.

### Omitted

When this flag is omitted and `--raw` is also omitted, `show` is human inspect: it presents identity, `type`, `title`, `description`, `tags` if any, `generated` provenance if present, inbound and outbound concept identities, and the Markdown body after frontmatter. Human inspect is not replaced by structured-only or raw-only output.

## `--raw`

Independent verbatim-file flag of `membundle` `show`. It takes no value token.

### Signature

```
`membundle` `show` <identity> [path] [`--json`] [`--raw`]
```

- `<identity>` — required positional concept identity.
- `[path]` — optional positional bundle path.
- `--json` and `--raw` — independent mode flags. Each takes no value token.

### Present

A successful run ends with POSIX status 0. Standard output bytes equal the on-disk concept file, including frontmatter, without reformatting.

A well-formed identity that is not in the bundle does not succeed, names that identity, and does not emit another concept file’s bytes. A reserved or invalid identity is not a successful raw inspect and does not emit the aimed file bytes.

The command does not create or mutate files.

### Omitted

When this flag is omitted, output is not constrained to verbatim file bytes. With `--json`, inspect is the structured concept record. With neither flag, inspect is human presentation.

## `concept_id`

Required identity argument of `membundle_show`. Command-line `show` takes that same identity as a required first positional.

### Signature

```
`membundle` `show` <identity> [path] [`--json`] [`--raw`]
```

`tools/call` name `membundle_show`, arguments:

- `concept_id` — required string. The concept identity.
- `bundle` — optional string. Bundle path.

`--json` and `--raw` are independent command-line flags (each takes no value token). They are not `membundle_show` arguments.

### Resolution

A trailing `.md` on the supplied identity is stripped before locate. The presented identity value is the stripped spelling.

### Required

`show` with no identity argument prints usage and does not succeed. That failure is not the not-found class.

`membundle_show` without `concept_id` does not return a successful concept record. The reply is a tool-level failure marked `isError` true, or the JSON-RPC unreadable-parameters failure.

### Rejected and missing identities

An identity that is empty, absolute, contains `..`, starts with a hyphen, contains a null byte, newline, carriage return, or tab, or names a reserved document is rejected on human, structured, and raw command-line inspect. A null byte in `concept_id` on `membundle_show` is a tool-level failure marked `isError` true, not a JSON-RPC protocol error.

A well-formed identity that is not in the bundle is not-found and is identified in the report. `membundle_show` not-found is a tool-level failure marked `isError` true and names that identity.

Inspect does not create or mutate files.

## `isError`

Tool-error marker on an `membundle_show` `tools/call` result. The marker is the boolean true.

### Where it appears

A tool-level inspect failure is a Model Context Protocol tool result whose `result` object marks `isError` true. It is not a JSON-RPC protocol error.

### When it is true

- `membundle_show` of a well-formed identity that is not in the bundle: `isError` is true, and the report names that identity.
- `membundle_show` with a null byte in `concept_id`: `isError` is true. The concatenated identity is not inspected.
- `membundle_show` without `concept_id` may mark `isError` true (the other allowed non-success is the JSON-RPC unreadable-parameters failure).

A successful inspect does not mark `isError` true.

## `--for-path`

Path-filter flag of `membundle` `search`. It takes one value token. The flag is optional.

### Signature

```
`membundle` `search` [query] [path] [`--for-path` <path>] [`--limit`=N] [`--json`]
```

- `[query]` — optional first positional. The query string.
- `[path]` — optional second positional. Bundle path.
- `--for-path` — optional. Followed by one value token (the source-file path). Independent of `--limit` and `--json`.
- `--limit` — optional numeric cap (`=` attached or a following value token).
- `--json` — optional. Takes no value token. On `search` it selects structured search hits, not a structured inspect record.

The `membundle_search` argument for this filter is `for_path`, not this hyphenated flag spelling.

### Present (non-empty value)

Search keeps only concepts whose `code_refs` list matches that source path. Absolute paths still match the same relative entry. If the filter is supplied and nothing matches, the result list is empty even when the same query without a path filter would have hit. Hits report a `code_refs` match, and also any keyword matched-field tokens when a query was supplied. On human output (`--json` omitted) that report is in each hit’s own text, as described under Human output for `search`.

Path-only invocation (this flag present, query omitted) is a valid search. It is not the neither-query-nor-path usage failure.

### Empty value

An empty path-filter value together with a query is ordinary keyword search.

### Omitted

When this flag is omitted and a query is supplied, search is ordinary keyword search. When this flag is omitted and no query is supplied, command-line `search` does not succeed and prints usage (including when only `--json` or `--limit` plus a value is present).

`search` does not create or mutate files.

## `--limit`

Result-cap flag of `membundle` `search`. It takes a numeric value. The flag is optional. A default exists when it is omitted.

### Signature

```
`membundle` `search` [query] [path] [`--for-path` <path>] [`--limit`=N] [`--json`]
```

- `[query]` — optional first positional. The query string.
- `[path]` — optional second positional. Bundle path.
- `--for-path` — optional. Followed by one value token.
- `--limit` — optional. The cap is accepted as one argv token `--limit``=`N (including `0` and a negative cap) and as `--limit` followed by a separate value token. Independent of `--for-path` and `--json`.
- `--json` — optional. Takes no value token. On `search` it selects structured search hits, not a structured inspect record.

The `membundle_search` argument for this cap is `limit`, not this flag spelling.

### Present

A positive cap at or below the maximum returns at most that many hits, in rank order (the leading prefix of the uncapped ranking). A requested cap above the maximum is clamped to that maximum. A non-positive cap (`0` or negative) uses the same default as an omitted cap.

This flag alone, without a query and without `--for-path`, does not make command-line `search` succeed: `search` `--limit` `5` is still the neither-query-nor-path usage failure.

### Omitted

A default cap exists. Omitting the flag returns at most that default number of hits.

`search` does not create or mutate files.

## `for_path`

Optional source-path argument of `membundle_search`. Command-line `search` takes that path as `--for-path` followed by one value token.

### Signature

```
`membundle` `search` [query] [path] [`--for-path` <path>] [`--limit`=N] [`--json`]
```

`tools/call` name `membundle_search`, arguments (all optional):

- `query` — string. The query.
- `for_path` — string. Source-file path filter.
- `bundle` — string. Bundle path.
- `limit` — integer. Result cap.

`--for-path` is the command-line flag (one value token). It is not an `membundle_search` argument key.

### Present (non-empty)

Search keeps only concepts whose `code_refs` list matches that source path. Absolute paths still match the same relative entry. If the filter is supplied and nothing matches, the result list is empty even when the same query without a path filter would have hit. Hits report a `code_refs` match, and also any keyword matched-field tokens when a query was supplied.

A non-empty `for_path` with `query` omitted is a valid `membundle_search`. It is not an empty-list “neither” call.

### Empty string

`for_path` set to an empty string together with a `query` is ordinary keyword search.

### Omitted

When `for_path` is omitted and a `query` is supplied, search is ordinary keyword search. When both `query` and `for_path` are omitted, `membundle_search` succeeds with an empty hit list. That success is not a tool-level failure.

A named missing `bundle` is a tool-level failure, not empty-list success.

## `limit`

Optional result-cap argument of `membundle_search`. Command-line `search` takes that cap as `--limit`. A default exists when it is omitted.

### Signature

```
`membundle` `search` [query] [path] [`--for-path` <path>] [`--limit`=N] [`--json`]
```

`tools/call` name `membundle_search`, arguments (all optional):

- `query` — string. The query.
- `for_path` — string. Source-file path filter.
- `bundle` — string. Bundle path.
- `limit` — integer. Result cap.

`--limit` is the command-line flag. It is not an `membundle_search` argument key. On the command line the cap is accepted as one argv token `--limit``=`N (including `0` and a negative cap) and as `--limit` followed by a separate value token.

### Present

A positive cap at or below the maximum returns at most that many hits, in rank order (the leading prefix of the uncapped ranking). A requested cap above the maximum is clamped to that maximum. A non-positive cap (`0` or negative) uses the same default as an omitted cap.

### Omitted

A default cap exists. Omitting `limit` returns at most that default number of hits. Omitting `limit` does not, by itself, change whether a query or path filter is required: `membundle_search` with neither `query` nor `for_path` still succeeds with an empty hit list.

## `query`

Optional query of `membundle_search`. Command-line `search` takes that same query as an optional first positional.

### Signature

```
`membundle` `search` [query] [path] [`--for-path` <path>] [`--limit`=N] [`--json`]
```

- `[query]` — optional first positional. The query string. Independent of the path filter and of the result cap.
- `[path]` — optional second positional. Bundle path.
- `--for-path` — optional. Followed by one value token.
- `--limit` — optional numeric cap. Accepted as one argv token `--limit``=`N (including `0` and a negative cap) and as `--limit` followed by a separate value token.
- `--json` — optional structured-output flag. It takes no value token. This is the same flag spelling as on `show`; on `search` it selects structured search hits, not a structured inspect record.

`tools/call` name `membundle_search`, arguments (all optional):

- `query` — string. The query.
- `for_path` — string. Source-file path filter.
- `bundle` — string. Bundle path.
- `limit` — integer. Result cap.

`--for-path`, `--limit`, and `--json` are command-line flags. They are not `membundle_search` argument keys.

### Present

A non-empty query is keyword search (alone, or combined with a path filter). A Unicode query that matches a Unicode title is a hit.

### Omitted or empty with no path filter

On the command line, `search` with neither a query nor a path filter does not succeed and prints usage. That failure is not a live zero-hit success and is not a missing-bundle load error. The same usage failure holds when the only extra tokens are `--json`, or `--limit` followed by a value token.

On `membundle_search`, omitting both `query` and `for_path` succeeds with an empty hit list. That success is not a tool-level failure.

### Structured output (`--json` on `search`)

When `--json` is present, a successful run ends with POSIX status 0. Standard output is a parseable hit list: a JSON array of objects, JSON null or an empty array for zero hits, or a JSON object that wraps exactly one array of objects. It is not the structured inspect record of `show`. Each hit presents the concept identity, `type`, `title`, and `description` as exact string values, the matched-field tokens that apply (from `title`, `tags`, `description`, `id`, `body`, and `code_refs` when the path filter matched), and a JSON number. JSON object key names are not pinned.

`membundle_search` returns that same parsed hit list (no `--json` flag).

### Human output

When `--json` is omitted, `search` is human hits: matching identities are presented. Human search is not replaced by structured-only output. Zero hits is success; human text states that nothing matched.

Each human hit is prefixed with its governance badge (`constraint`, `hold`, or `context`), and that hit’s text runs from its badge to the next hit’s badge. When the path filter is supplied, each hit’s text names `code_refs` and exactly the keyword matched-field tokens that matched (`title`, `tags`, `description`, `id`, `body`), spelled as in structured output, and does not use any of those six tokens otherwise (for example as labels).

### Named missing bundle

A named bundle path that cannot be loaded does not succeed. `membundle_search` of a named missing bundle is a tool-level failure, not empty-list success.

`search` does not create or mutate files.

## `--agents`

Independent agents-governance-check flag of `membundle` `validate`. It takes no value token. It is not the `agents` command.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

- `[path]` — optional positional bundle path.
- `--strict`, `--stale`, `--drift`, `--agents`, and `--json` — independent mode flags. Each takes no value token.

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--agents` is the command-line flag. It is not an `membundle_validate` argument key. `membundle_validate` has no agents argument key.

### Present

`validate` also runs the `AGENTS.md` MBG-and-symlink check against `AGENTS.md` in the named path, or in that path’s parent if only the parent contains `AGENTS.md`. The symlink half of the check is the four SSoT mappings: `CLAUDE.md` → `AGENTS.md`; `.cursorrules` → `AGENTS.md`; `.windsurfrules` → `AGENTS.md`; `.github/copilot-instructions.md` → `../AGENTS.md`.

Failure of that check — including a missing `AGENTS.md`, an omitted mapping, or a mapping path that is a regular file instead of a link — ends with status 1. A passing `AGENTS.md` together with the four mappings as links succeeds.

### Omitted

Omitting this flag does not run that check. A missing `AGENTS.md` does not fail `validate`.

### Structured output (`--json` on `validate`)

When `--json` is present, standard output is machine-readable JSON (an object or an array). JSON object key names are not pinned. Walked booleans carry conformant gate-pass versus mixed conformant gate-fail versus all-false nonconformant. Walked numbers carry relative concept and stale counts. This is not the structured inspect record of `show`.

`membundle_validate` returns that same walkable report without a `--json` flag.

When `--json` is omitted, `validate` is a human report.

`validate` does not create or mutate files.

## `--drift`

Independent drift-audit flag of `membundle` `validate`. It takes no value token.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

- `[path]` — optional positional bundle path.
- `--strict`, `--stale`, `--drift`, `--agents`, and `--json` — independent mode flags. Each takes no value token.

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--drift` is the command-line flag. It is not an `membundle_validate` argument key. `membundle_validate` has no drift argument key. Drift is always on for `membundle_validate`.

### Present

The drift audit runs. The product warns when a root-index list item’s description text does not contain the linked concept’s `description` after both sides are compared as follows: case-insensitive; backslash, double quote, single quote, backtick, asterisk, and underscore removed; internal whitespace collapsed; a trailing period stripped. Containment after that comparison does not warn.

It also warns when a non-glob `code_refs` path exists neither in the project directory that contains the bundle nor inside the bundle. A glob `code_refs` entry, and a non-glob path that exists in the project directory or inside the bundle, do not warn.

Drift warnings do not fail the producer gate by themselves, including when `--strict` is also present.

### Omitted

On the command line, omitting this flag does not run the drift audit. Index-description mismatch and missing non-glob `code_refs` are not that warning.

On `membundle_validate`, the drift audit always runs. There is no argument that turns it off.

### Structured output (`--json` on `validate`)

When `--json` is present, standard output is machine-readable JSON (an object or an array). JSON object key names are not pinned. Walked booleans carry conformant gate-pass versus mixed conformant gate-fail versus all-false nonconformant. Walked numbers carry relative concept and stale counts. This is not the structured inspect record of `show`.

`membundle_validate` returns that same walkable report without a `--json` flag.

When `--json` is omitted, `validate` is a human report.

`validate` does not create or mutate files.

## `--stale`

Independent stale-date-gate flag of `membundle` `validate`. It takes no value token.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

- `[path]` — optional positional bundle path.
- `--strict`, `--stale`, `--drift`, `--agents`, and `--json` — independent mode flags. Each takes no value token.

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--stale` is the command-line flag. It is not an `membundle_validate` argument key. The `membundle_validate` argument is `stale`.

### Present

The stale-date gate is applied. A non-zero stale count fails the producer gate.

A concept whose `stale_after` calendar date is today or earlier in UTC is stale and is counted. Tomorrow’s UTC date is not stale. The comparison uses UTC even when the process environment `TZ` names a zone whose local calendar date differs from UTC.

A `stale_after` value that is not year-month-day is an advisory warning and is not a stale count. That warning alone does not fail the producer gate.

### Omitted

Omitting this flag does not apply the stale-date gate. Stale concepts remain warnings and are still counted. They do not fail the producer gate, including when `--strict` is present.

On `membundle_validate`, omitting `stale` does not apply the stale-date gate. The gate is applied only when `stale` is true.

### Structured output (`--json` on `validate`)

When `--json` is present, standard output is machine-readable JSON (an object or an array). JSON object key names are not pinned. Walked booleans carry conformant gate-pass versus mixed conformant gate-fail versus all-false nonconformant. Walked numbers carry relative concept and stale counts. This is not the structured inspect record of `show`.

`membundle_validate` returns that same walkable report without a `--json` flag.

When `--json` is omitted, `validate` is a human report.

`validate` does not create or mutate files.

## `--strict`

Independent producer-gate flag of `membundle` `validate`. It takes no value token.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

- `[path]` — optional positional bundle path.
- `--strict`, `--stale`, `--drift`, `--agents`, and `--json` — independent mode flags. Each takes no value token.

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--strict` is the command-line flag. It is not an `membundle_validate` argument key. The `membundle_validate` argument is `strict`. There is no drift or agents argument key.

### Present

The producer gate is applied. Broken concept links, orphan identities, and (when the bundle declares version `0.2`) gate findings fail the producer gate. They do not by themselves make the bundle non-conformant when there are no hard errors. Gate findings are not fatal when the declared version is not `0.2`.

Gate findings are: leftover `timestamp`; a single-hash body heading whose text is `Citations` outside fenced blocks (a deeper heading, a title-plus-equals underline, or a fenced occurrence is not this finding); a `sources` entry with no `resource`; `generated` with no `by` (an invalid `by` is not this finding); a `verified` `at` that predates `generated` `at`; a present `governance` other than `constraint`, `hold`, or `context`; a present `status` other than `draft`, `stable`, or `deprecated`; a `code_refs` entry that is absolute or contains `..` traversal.

A bundle with more than one concept and a concept that has no inbound and no outbound concept-to-concept links is an orphan and fails the gate. A single-concept bundle is not orphaned. Fenced peer links, external URLs, reserved-document hrefs, and root-index listings do not rescue orphans. A relative Markdown link (outside fences, not an external URL) to a missing concept, or to reserved `index.md` / `log.md` / `AGENTS.md`, is a broken link and fails the gate. A fenced or external href is not a broken link.

Advisory warnings do not fail the producer gate, including under this flag: nested `index.md` frontmatter, non-ISO `log.md` two-hash headings, unmatched footnote keys, invalid actor strings, a `verified` entry with no `by`, missing or unparseable `generated` / `verified` `at`, a `sources` `last_modified` that is not year-month-day, a malformed `stale_after`, and a stale concept when `--stale` is omitted. A drift warning alone does not fail the gate.

### Omitted

On the command line, omitting this flag does not apply the producer gate. Orphans, broken links, and gate findings still appear in the report, and the producer gate passes.

On `membundle_validate`, omitting `strict` applies the producer gate. `strict` false turns the producer gate off. `strict` true applies it.

### Structured output (`--json` on `validate`)

When `--json` is present, standard output is machine-readable JSON (an object or an array). JSON object key names are not pinned. Walked booleans carry conformant gate-pass (every boolean true, at least two) versus mixed conformant gate-fail versus all-false nonconformant. Walked numbers carry relative concept and stale counts. This is not the structured inspect record of `show`.

`membundle_validate` returns that same walkable report without a `--json` flag.

When `--json` is omitted, `validate` is a human report. Human validate still lists orphan identities.

`validate` does not create or mutate files.

## `last_modified`

Nested mapping key of a `sources` entry. It is the last-modified date on that source. It is not a command-line flag and not an `membundle_validate` argument.

### Where it appears

On a concept frontmatter `sources` item, beside `resource`. The key spelling is `last_modified`.

### Shape

A string. When present, the accepted calendar shape is ISO 8601 year-month-day (four-digit year, two-digit month, two-digit day).

### Observable

A `last_modified` value that is not year-month-day is an advisory warning. That warning does not fail the producer gate, including when `--strict` is present. A year-month-day value does not produce that warning.

This key is not `stale_after` and is not the stale-date gate.

## `stale`

Optional stale-date-gate argument of `membundle_validate`. Command-line `validate` takes that gate as `--stale` with no value token.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--stale` is the command-line flag. It is not an `membundle_validate` argument key. The argument spelling is `stale`, not `stale_after`.

### Present true

The stale-date gate is applied. A non-zero stale count fails the producer gate.

A concept whose `stale_after` calendar date is today or earlier in UTC is stale and is counted. Tomorrow’s UTC date is not stale. The comparison uses UTC even when the process environment `TZ` names a zone whose local calendar date differs from UTC.

A `stale_after` value that is not year-month-day is an advisory warning and is not a stale count.

### Omitted

Omitting `stale` does not apply the stale-date gate. Stale concepts remain warnings and are still counted. They do not fail the producer gate. The stale-date gate is applied only when requested.

`membundle_validate` returns a walkable report without a `--json` flag. JSON object key names are not pinned. Walked booleans carry conformant gate-pass versus mixed conformant gate-fail versus all-false nonconformant. Walked numbers carry relative concept and stale counts.

## `strict`

Optional producer-gate argument of `membundle_validate`. Command-line `validate` takes that gate as `--strict` with no value token.

### Signature

```
`membundle` `validate` [path] [`--strict`] [`--stale`] [`--drift`] [`--agents`] [`--json`]
```

`tools/call` name `membundle_validate`, arguments (all optional):

- `bundle` — string. Bundle path.
- `strict` — boolean. Producer gate.
- `stale` — boolean. Stale-date gate.

`--strict`, `--stale`, `--drift`, `--agents`, and `--json` are command-line flags. They are not `membundle_validate` argument keys. There is no drift or agents argument key. Drift is always on for `membundle_validate`.

### Present true

The producer gate is applied. Broken concept links, orphan identities, and (when the bundle declares version `0.2`) gate findings fail the producer gate. They do not by themselves make the bundle non-conformant when there are no hard errors.

### Present false

The producer gate is off. Orphans, broken links, and gate findings still appear in the report, and the producer gate passes.

### Omitted

Omitting `strict` applies the producer gate (the same as true). The caller must set it false to turn the gate off.

`membundle_validate` returns a walkable report without a `--json` flag. JSON object key names are not pinned. Walked booleans carry conformant gate-pass versus mixed conformant gate-fail versus all-false nonconformant.

## `--budget`

Caller-cap flag of `membundle` `agents` `lint`. The cap is accepted as one argv token `--budget``=`N (including `0` and a negative cap). The flag is optional. A default exists when it is omitted or the supplied cap is non-positive.

### Signature

```
`membundle` `agents` `lint` [`--budget`=N] [`--json`] [path]
```

- `--budget` — optional. The cap is one argv token `--budget``=`N (including `0` and a negative cap).
- `--json` — optional. Takes no value token. On `agents` `lint` this is structured lint output. It is the same no-value flag spelling as on `show`, `search`, `validate`, `create`, `update`, and `relate`. It is not a structured inspect record of `show`.
- `[path]` — optional positional `AGENTS.md` path. It comes after the cap and structured-output flags.

### Path

When `[path]` is omitted, `lint` reads `AGENTS.md` in the current directory. That omit-path does not follow a `knowledge` directory. A named path is the file that is linted.

`lint` of a missing file does not succeed.

### Present `--budget`

A positive cap is the in-force budget. Human `lint` prints that in-force budget. A non-positive cap (`0` or negative) uses the same default as an omitted cap.

### Omitted `--budget`

A default cap exists and is the in-force budget. Human `lint` still prints that in-force budget.

### Structured output (`--json` on `agents` `lint`)

When `--json` is present, standard output is machine-readable JSON (an object or an array), including when `lint` does not succeed. JSON object key names are not pinned. Walked strings carry the `MBG-001`, `MBG-002`, `MBG-003`, `MBG-004`, and `MBG-005` identifiers on fail and not on pass. The report includes pass/fail and counts. After finding records are removed, the leftover grouping still reports three facts: the in-force cap as a sortable integer; a two-state exceeded mark matching `MBG-005` presence; and a working-memory estimate as a sortable integer whose exact value is not scored. Two structured runs of the same file that differ only in the caller cap differ in the reported in-force cap.

When `--json` is omitted, `lint` is a human report that still prints the in-force budget.

`lint` does not create or mutate files.

## `--check`

Independent check-only flag of `membundle` `agents` `link`. It takes no value token. It is not the `check` nested command.

### Signature

```
`membundle` `agents` `link` [`--root` <dir>] [`--check`] [`--force`]
```

- `--root` — optional. Followed by one value token. The target root. When omitted, the target is the current directory.
- `--check` — optional. Takes no value token. Check-only: no creates.
- `--force` — optional. Takes no value token. Overwrite request.

### Present

`link` reports each SSoT mapping as valid or invalid and does not create links, does not replace existing paths, and does not create missing parent directories. A mapping that is missing is reported and left missing. A path that exists at a mapping and is a regular file is invalid and is left as a regular file. When every mapping is already the correct symlink, the run succeeds.

`link` without a canonical `AGENTS.md` in the target root does not succeed.

### Omitted

`link` creates the SSoT mappings under the target root, creating parent directories when needed. The created paths are symbolic links, not copies of file contents. A path that is already the correct symlink is left as already valid. A path that exists and is not that symlink is a failure unless `--force` is also present.

`--check` is not a flag of `membundle` `agents` `check`.

## `--domain`

Domain-profile flag of `membundle` `agents` `init`. It takes one value token: the profile name. The flag is optional. A default exists when it is omitted.

### Signature

```
`membundle` `agents` `init` [`--domain` <profile>] [`--name` <project>] [`--root` <dir>]
```

- `--domain` — optional. Followed by one value token. The domain profile for the written `AGENTS.md`.
- `--name` — optional. Followed by one value token. The project name. This is the same flag spelling as on `bootstrap`. On `agents` `init` the value is substituted into the written `AGENTS.md` title, not a bootstrap component report.
- `--root` — optional. Followed by one value token. The target root. When omitted, the target is the current directory even when a `knowledge` directory exists there.

### Present `--domain`

The written `AGENTS.md` Domain Codex is specialized to that profile. `legal` is observably different from `software`. An unrecognized profile name is treated as `software`.

### Omitted `--domain`

The written file uses the `software` profile.

### Present `--name`

The first heading of the written `AGENTS.md` contains that project name. Two different names produce different first headings.

### Omitted `--name`

`init` still writes `AGENTS.md`.

### Existing `AGENTS.md`

A second `init` on a root that already has `AGENTS.md`, without overwrite, does not succeed. Overwrite of an existing mapping on `agents` `link` is the separate no-value `--force` flag.

## `--force`

Overwrite flag of `membundle` `agents` `link`. It takes no value token. The flag is optional.

### Signature

```
`membundle` `agents` `link` [`--root` <dir>] [`--check`] [`--force`]
```

- `--root` — optional. Followed by one value token. The target root. When omitted, the target is the current directory.
- `--check` — optional. Takes no value token. Check-only: no creates.
- `--force` — optional. Takes no value token. Overwrite request.

This flag is the `link` overwrite spelling.

### Present

`link` requires a canonical `AGENTS.md` in the target root. If a mapping path exists and is not the correct symlink — a regular file, or a symlink whose target is not that root’s `AGENTS.md` — this flag replaces that path with the symlink. A path that is already the correct symlink is left as already valid.

`link` without a canonical `AGENTS.md` in the target root does not succeed.

### Omitted

If a mapping path exists and is not the correct symlink, `link` does not succeed and leaves that path unchanged. Missing mappings are still created as symbolic links, not as copies of file contents. A path that is already the correct symlink is left as already valid.

## `--root`

Target-root flag of `membundle` `agents` `init`, `membundle` `agents` `link`, and `membundle` `agents` `check`. It takes one value token: the target directory. The flag is optional. A default exists when it is omitted.

### Signature

```
`membundle` `agents` `init` [`--domain` <profile>] [`--name` <project>] [`--root` <dir>]
`membundle` `agents` `link` [`--root` <dir>] [`--check`] [`--force`]
`membundle` `agents` `check` [`--root` <dir>]
```

- `--root` — optional. Followed by one value token. Independent of `--domain`, `--name`, `--check`, and `--force`.
- `--domain` and `--name` — optional on `init`. Each is followed by one value token.
- `--check` and `--force` — optional on `link`. Each takes no value token.

### Present

The named directory is the target root. `init` writes `AGENTS.md` under that directory. `link` and `check` use that directory’s `AGENTS.md` and SSoT mappings, not a parent directory’s.

### Omitted

The target root is the current directory. For `init` that remains the current directory even when a `knowledge` directory exists there: `AGENTS.md` is written beside `knowledge`, not inside it.

### `init` at that root

Writes `AGENTS.md`. A second `init` without overwrite does not succeed if `AGENTS.md` already exists.

### `link` at that root

Requires a canonical `AGENTS.md` in that root. Without it, `link` does not succeed and creates no mappings.

### `check` at that root

Runs `lint` on that root’s `AGENTS.md` and then verifies the SSoT mappings under that root. Both parts must pass. It uses that root’s `AGENTS.md`, not the parent’s. It does not succeed when `AGENTS.md` is missing, when `lint` fails, or when any mapping is missing, is a regular file, or points at the wrong target. `--check` is not a flag of this command.

## `Makefile`

Fourth `bootstrap` install component. The on-disk file name is `Makefile`, written at the project root (the current working directory when the path is omitted; the named directory when a path is given). It is not written inside a nested `knowledge` redirect.

### When it is written

Written only when absent. A pre-existing `Makefile` whose contents differ from the template is left unchanged. Skip with `--no-makefile` leaves the file uncreated.

A full `bootstrap` (that skip omitted) of a directory that has no `Makefile` writes one.

### Recipes

The written file has at least one recipe line (not comment-only). Indentation of that line is not pinned. It provides convenience tasks that:

- run strict-and-drift validation on `knowledge`
- search that bundle

Exact Make target names and command-line flag punctuation are not pinned.

### Success report

On a successful full run the process names `Makefile` among the not-skipped components, including when a pre-existing file was left unchanged. A `--no-makefile` success report is distinguishable from that full-run report because `Makefile` is not presented as installed.

## `--no-skill`

Independent skip flag of `membundle` `bootstrap`. It takes no value token.

### Signature

```
`membundle` `bootstrap` [path] `--no-skill`
```

The optional `[path]` is the same target project directory as for `bootstrap` (current working directory when omitted; the named directory when present). This flag may be combined with `--name` (one value token), `--no-bundle`, `--no-agents-md`, `--no-makefile`, and `--overwrite-agents-md`. Each skip is independent.

### Observable effect

Installing the skill tree under `.agents` / `skills` / `membundle-memory` is omitted. That directory is not created for that run. A pre-existing skill tree at that path is left unchanged (not deleted and not replaced). The other not-skipped components still install.

On success the process reports the not-skipped components. The report names those components.

When this flag is omitted, a skill install replaces pre-existing skill files at that path.

## `--no-agents-md`

Independent skip flag of `membundle` `bootstrap`. It takes no value token.

### Signature

```
`membundle` `bootstrap` [path] `--no-agents-md`
```

The optional `[path]` is the same target project directory as for `bootstrap` (current working directory when omitted; the named directory when present). This flag may be combined with `--name` (one value token), `--no-bundle`, `--no-skill`, `--no-makefile`, and `--overwrite-agents-md`. Each skip is independent.

### Observable effect

Installing `AGENTS.md` is omitted. That file is left uncreated. The other not-skipped components still install.

On success the process reports the not-skipped components. The report names those components.

## `--no-bundle`

Independent skip flag of `membundle` `bootstrap`. It takes no value token.

### Signature

```
`membundle` `bootstrap` [path] `--no-bundle`
```

The optional `[path]` is the same target project directory as for `bootstrap` (current working directory when omitted; the named directory when present). This flag may be combined with `--name` (one value token), `--no-skill`, `--no-agents-md`, `--no-makefile`, and `--overwrite-agents-md`. Each skip is independent.

### Observable effect

Installing the `knowledge` scaffold is omitted. No new `knowledge` directory is created for that run. The other not-skipped components still install at the project root (not inside a nested `knowledge` redirect).

On success the process reports the not-skipped components. The report names those components.
