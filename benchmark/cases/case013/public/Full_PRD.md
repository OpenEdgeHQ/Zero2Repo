# MEMBUNDLE Agent Memory — Full Product Requirements Document

This document specifies the finished **MEMBUNDLE Agent Memory** product: a domain-neutral, Git-native persistent project memory for AI agents, based on the Open Bundle Format (MEMBUNDLE) v0.2. It describes user-observable capabilities of the standalone `membundle` tool (command-line commands and a Model Context Protocol server over standard input and output). Later stages verify these capabilities against real bundle files and real process invocations. Nothing here is aspirational; every feature point exists in the current product.

The product’s own names are used throughout: MEMBUNDLE Agent Memory, `membundle`, MEMBUNDLE v0.2, Dual-Memory Bundle Architecture (DMBA), Bundle Action Grammar (MBG), `knowledge/`, `AGENTS.md`, `index.md`, `log.md`, and the three governance tiers constraint, hold, and context.

---

## Product overview

Conversations with AI agents reset when context windows close. MEMBUNDLE Agent Memory stores durable project knowledge as an MEMBUNDLE v0.2 knowledge bundle of plain-text Markdown files so later sessions can retrieve decisions, facts, and runbooks without stuffing the entire corpus into the system prompt.

The Dual-Memory Bundle Architecture (DMBA) splits that memory into two layers a caller can observe as files and tools:

- **Normative working memory (push layer).** A compact `AGENTS.md` codex, written in Bundle Action Grammar (MBG), that states invariants, tone, and search-before-write triggers. It is ordinary project text, not a hidden database.
- **Semantic domain memory (pull layer).** An MEMBUNDLE v0.2 bundle, conventionally `knowledge/`, that is not injected in full at session start. Agents retrieve selected concepts through search and show operations, and persist new knowledge through create, update, and relate operations.

The `membundle` executable is the tooling layer: it initializes and bootstraps that layout, reads and writes concepts, ranks search hits, audits bundle health, lints the MBG codex, and exposes the same memory operations as Model Context Protocol tools. Everything stored is version-controllable plain text. There is no required external database, embedding API, or network service for memory retrieval.

This product is **CPU-only**. Faithful implementation is a local `membundle` executable plus on-disk Markdown/YAML bundles. There is no removable accelerator substrate and therefore no negative-control clause.

---

## Terminology

- **MEMBUNDLE v0.2 bundle.** A directory of Markdown files that follows the Open Bundle Format (MEMBUNDLE) v0.2: concepts with YAML frontmatter, a root `index.md` that may declare the format version, a root `log.md` change history, and optional nested `index.md` navigation files. The conventional bundle directory name is `knowledge/`.
- **Concept.** One non-reserved Markdown file in the bundle. Its **concept identity** is the bundle-relative path without the `.md` suffix (for example, a file `architecture/layers.md` has identity `architecture/layers`). That identity rule is the Open Bundle Format (MEMBUNDLE) v0.2 identity rule.
- **Reserved bundle documents.** `index.md` in any directory, the bundle-root `log.md`, and a bundle-root `AGENTS.md` are navigation or governance documents, not concepts. The product must not treat them as creatable concept identities. A loaded bundle does not count a root `AGENTS.md` as a concept, and excludes every file named `log.md` from the concept set (only the bundle-root log is the change history). A nested identity whose file is named `log.md` is not reserved against create.
- **Frontmatter.** The YAML block at the start of a concept file, delimited by the conventional triple-dash fences used by MEMBUNDLE v0.2. The only field MEMBUNDLE v0.2 requires is a non-empty **type**. Other recognized fields include title, description, tags, generated, verified, status, governance, code_refs, stale_after, sources, and resource. Unknown fields must be tolerated and, when the product rewrites a concept, preserved.
- **Generated vs verified.** Provenance mappings defined by MEMBUNDLE v0.2. **Generated** records who authored the file and when. **Verified** records later human or process confirmations. The product writes generated provenance on create/update; it does not invent verified entries.
- **Actor string.** An identity in the MEMBUNDLE v0.2 actor family. Two forms are accepted: a producer-slash-version form whose two sides are both non-empty and contain neither spaces nor slashes (the product itself uses `agent/cli` for the command line, `agent/mcp` for the Model Context Protocol server, and `agent/membundle-tool` when the caller supplies an empty actor); or a prefix-colon-id form that starts with a letter, then zero or more letters, digits, underscores, dots, or hyphens, then a colon, then a remainder with no spaces.
- **Governance.** Operational authority of a concept over code edits: **constraint** (mandatory guardrail), **hold** (do not edit the bound paths without human approval), **context** (advisory). If the file omits governance, identities under `convention/` default to constraint and all other identities default to context. Declared values are compared case-insensitively and normalized to lowercase.
- **code_refs.** A list of project-relative source paths or globs naming the files or directories a concept governs.
- **Producer gate.** An optional stricter audit on top of MEMBUNDLE v0.2 conformance. Conformance means the bundle has no hard errors (for example, a concept missing type). The producer gate additionally treats selected connectivity and provenance problems as fatal when the caller requests strict mode, and treats expired review dates as fatal when the caller requests stale-date gating.
- **MBG.** Bundle Action Grammar: the compact ASCII instruction syntax used in `AGENTS.md`. The product lints five rules labeled MBG-001 through MBG-005.
- **MEMBUNDLE Agent Memory delimiters.** The HTML comments `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->` and `<!-- END MEMBUNDLE AGENT MEMORY -->` that bound the working-memory block inside `AGENTS.md`.
- **SSoT tool links.** Symbolic links from editor-specific instruction filenames to the canonical `AGENTS.md` so multiple tools share one codex.

---

## Bundle layout a caller can construct

A minimal MEMBUNDLE v0.2 bundle directory contains:

1. A root `index.md` whose YAML frontmatter declares `membundle_version` as `0.2`, followed by a Markdown heading and body. Nested directory `index.md` files are navigation listings and should not carry frontmatter.
2. A root `log.md` whose dated sections use ISO 8601 calendar headings of the form year-month-day (four-digit year, two-digit month, two-digit day), with newer days listed before older days.
3. Zero or more concept files: Markdown whose first lines are a YAML frontmatter block containing at least type, then a Markdown body. Nested folders are organizational only.

When the current working directory contains a subdirectory named `knowledge/` that is a directory, commands that omit a bundle path use `knowledge/`. Otherwise they use the current directory. If the path the caller names has no root `index.md` but does contain a `knowledge/` subdirectory, loading resolves into that nested bundle.

Hidden files and directories (names beginning with a dot) and a directory named `node_modules` are not loaded as concepts and do not by themselves make the load fail. Only Markdown files are loaded. A symlink that is itself a Markdown file and whose resolved target leaves the bundle directory makes the load not succeed, including when that resolved target is a directory; search of that bundle then fails as a load error, and that failure is distinct from a successful search with no hit records. A symlink that is a directory, whose own name is not a Markdown file, and whose resolved target leaves the bundle directory is not walked; concepts that exist only through it are not loaded; the load still succeeds; search succeeds and those outside concepts are not hit records. That success is distinct from a load that does not succeed and from a search that returns an outside concept. A write whose resolved target leaves the bundle, including a write through a directory symlink, does not succeed.

---

## Finite vocabularies

These closed sets are part of the product, not examples:

- **membundle commands:** validate, search, show, create, update, relate, init, bootstrap, agents, mcp, version (also accepted as a version request), and help.
- **agents subcommands:** lint, init, link, check.
- **MCP tools:** membundle_search, membundle_show, membundle_create, membundle_update, membundle_relate, membundle_validate.
- **Governance values:** constraint, hold, context.
- **Status values the validator accepts:** draft, stable, deprecated. Status is compared exactly as written (unlike governance), so `Draft` is not accepted.
- **MBG lint rules:** MBG-001 (ASCII-only lines), MBG-002 (RFC 2119 modal verbs on invariant bullets), MBG-003 (balanced parentheses on tool-like invocations), MBG-004 (Mermaid mentioned in Domain Codex / section 0), MBG-005 (working-memory token budget).
- **MBG modal prefixes accepted at the start of an invariant bullet:** MUST, MUST NOT, NEVER, PREFER, ALWAYS, SHOULD, MAY, and a leading exclamation mark.
- **Domain codex profiles for agents init:** software, research, legal, coaching, books. An unrecognized profile is treated as software.
- **Bootstrap-installed skill documents** under `.agents/skills/membundle-memory/`: SKILL.md, discovery.md, remember.md, update.md, relationships.md, examples.md.
- **SSoT link mappings** (link path → canonical target): `CLAUDE.md` → `AGENTS.md`; `.cursorrules` → `AGENTS.md`; `.windsurfrules` → `AGENTS.md`; `.github/copilot-instructions.md` → `../AGENTS.md`.
- **MEMBUNDLE Agent Memory delimiters:** `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->` and `<!-- END MEMBUNDLE AGENT MEMORY -->`.

---

## Non-functional constraints (not scored as separate features)

Latency figures advertised in marketing (microsecond search, millisecond validation) are **not scored**. The numeric search score formula (how term weights combine) is **not scored** beyond the ordering rules in the search feature. The formula that produces the MBG working-memory token estimate is **not scored**; that waiver does not cover the structured lint report of the in-force cap, the exceeded mark, or estimate presence, nor pass/fail against the stated budget. The `version` and `help` commands, Homebrew packaging, release automation, and the separate benchmark runner are not product capabilities scored by this PRD’s feature points.

---

## Out of scope for this PRD’s feature points

The progressive-disclosure benchmark harness, Homebrew formula templates, and CI/release workflows are operator or maintainer tooling, not the agent-memory product surface.

---

### FP-01: Initialize a bare MEMBUNDLE v0.2 knowledge bundle

**Public entry.** The `membundle` **init** command. The caller may name a target directory. If the caller omits the path, the tool uses the default bundle path rule in “Bundle layout a caller can construct.”

**Normal behavior.** The command creates the target directory if needed. If the directory has no root `index.md`, it writes one whose frontmatter declares MEMBUNDLE version 0.2 and whose body is a knowledge-base heading. If the directory has no root `log.md`, it writes one whose first heading is today’s UTC date as an ISO 8601 year-month-day calendar date, with a creation bullet stating that an MEMBUNDLE v0.2 knowledge bundle was initialized. If those files already exist, they are left unchanged. On success the process reports that an MEMBUNDLE v0.2 bundle was initialized at the target path and ends successfully.

**Boundary / error behavior.** If the target cannot be created or the files cannot be written, the command does not succeed and reports the failure. Init does not create concepts, `AGENTS.md`, skill files, or a Makefile.

**Verifiable oracle.**

- After init on an empty directory, that directory contains a root `index.md` and a root `log.md`. Holding this document and the Open Bundle Format (MEMBUNDLE) v0.2 rules for indexes and change history, an outside party can check: the root index declares version 0.2 in frontmatter; the log’s dated heading is today’s UTC date in ISO 8601 YYYY-MM-DD form.
- A second init on the same directory still succeeds and does not replace an already-present root index or log whose contents the caller can distinguish from the templates (for example, a custom heading left intact).
- Absence: a tool that writes no `index.md`, omits the version declaration, or treats init as a no-op on a missing directory fails this feature.

---

### FP-02: Bootstrap the Dual-Memory Agent Memory stack

**Public entry.** The `membundle` **bootstrap** command. The caller may name a target project directory (default: the current directory) and may supply a project name (default: the target directory’s base name, or `my-project` if that name is empty, `.`, or `/`). The caller may independently skip installing the skill tree, skip `AGENTS.md`, skip the Makefile, skip the `knowledge/` bundle, and may request overwrite of an existing `AGENTS.md` instead of non-destructive enrichment.

**Normal behavior.** With all installs enabled (the default), bootstrap creates the target directory if needed and installs four components:

1. **`knowledge/` bundle.** Root `index.md` declaring MEMBUNDLE version 0.2, titled with the project name, and root `log.md` with today’s UTC ISO 8601 date and a creation bullet. Existing index or log files are not overwritten.
2. **`.agents/skills/membundle-memory/` skill.** The six skill documents listed under Finite vocabularies. These files are written even if they already exist.
3. **`AGENTS.md`.** If the file is missing, or the caller requested overwrite, a DMBA-protocol `AGENTS.md` is written with the project name substituted and a delimited MEMBUNDLE Agent Memory section bounded by the HTML comments `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->` and `<!-- END MEMBUNDLE AGENT MEMORY -->`, containing search-before-write invariants, governance guard clauses, and a completion pipeline that requires validation before exit. If `AGENTS.md` already exists and overwrite was not requested, and the file does not already contain the phrase `BEGIN MEMBUNDLE AGENT MEMORY`, the substring `membundle-agent-memory`, or the phrase Open Bundle Format (MEMBUNDLE), the product appends that delimited MEMBUNDLE Agent Memory block without deleting the caller’s existing rules. If any of those three strings already appear, the existing file is left unchanged.
4. **Makefile.** Written only when absent. It provides convenience tasks that run strict-and-drift validation on `knowledge/` and that search that bundle.

On success the command reports which of those four components were not skipped, including when some of those files already existed and were left unchanged.

**Boundary / error behavior.** Each skip option omits only that component; the others still install. If the target directory cannot be created, bootstrap does not succeed. Bootstrap does not delete unrelated project files.

**Verifiable oracle.**

- After a full bootstrap of an empty directory, an outside observer finds `knowledge/index.md` declaring MEMBUNDLE v0.2, `knowledge/log.md` with today’s UTC ISO 8601 date heading, the six skill files under `.agents/skills/membundle-memory/`, an `AGENTS.md` that contains `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->`, `<!-- END MEMBUNDLE AGENT MEMORY -->`, and the project name, and a Makefile. Holding MEMBUNDLE v0.2, the root index’s version field is `0.2`.
- Skipping the bundle leaves no new `knowledge/` scaffold; skipping the skill leaves no `.agents/skills/membundle-memory/`; skipping `AGENTS.md` leaves that file uncreated; skipping the Makefile leaves it uncreated. A skip-Makefile success report is distinguishable from a full-run report because the Makefile is not presented as installed.
- A pre-existing `knowledge/index.md`, `knowledge/log.md`, or Makefile whose contents the caller can distinguish from the templates is left unchanged. A pre-existing skill file under `.agents/skills/membundle-memory/` is replaced when the skill is not skipped.
- An existing `AGENTS.md` that contains only unrelated human rules, and does not already contain the MEMBUNDLE markers named above, gains the delimited MEMBUNDLE block and retains the original rules. An existing `AGENTS.md` that already contains the begin marker is not duplicated when overwrite is off. With overwrite requested, the file is replaced by the product template.
- Absence: a bootstrap that only writes `knowledge/` and omits skill plus `AGENTS.md` when those installs were not skipped fails this feature.

---

### FP-03: Inspect a concept

**Public entry.** The `membundle` **show** command. The caller supplies a concept identity and optionally a bundle path, and may request machine-readable structured output or verbatim raw Markdown. The **membundle_show** Model Context Protocol tool performs that same load, identity resolution, and locate operation (concept identity required) and returns the same parsed concept record as structured command-line inspect, not the command-line human presentation of inbound and outbound relationship lists.

**Normal behavior.** The product loads the bundle, resolves the identity by stripping a trailing `.md` if the caller included it, and locates the concept. Human command-line output presents identity, type, title, description, tags if any, generated provenance if present, inbound concept identities (others that link to this concept), outbound concept identities (this concept’s links to other concepts), and the Markdown body after frontmatter. Those inbound and outbound lists are distinct from the body: after the body is removed, the source still names the target as outbound and the target still names the source as inbound, and those remainders differ. Structured command-line output and the Model Context Protocol inspect tool present the parsed concept record including identity, type, and body; they are not a carrier of inbound and outbound identity lists independent of that body, so after the body is stripped they need not still contain the related identity. Raw mode emits the file bytes as stored, including frontmatter, without reformatting. Inbound and outbound identities reflect Markdown links to other concept files in the body, ignoring fenced code blocks and ignoring links whose targets are `index.md`, `log.md`, `AGENTS.md`, or external URLs.

**Boundary / error behavior.** A missing identity argument prints usage and does not succeed. An identity that is empty, absolute, contains `..`, starts with a hyphen, contains a control character that is a null byte, newline, carriage return, or tab, or names a reserved document is rejected. A bundle that cannot be loaded fails as a load error (distinct from “concept not found”). A well-formed identity that is not in the bundle fails as not found. Show never creates or mutates files.

**Verifiable oracle.**

- Given a bundle with concept `architecture/layers` whose body links to `architecture/governance-model.md`, human command-line show of `architecture/layers` reports that identity, its type and title from frontmatter, its body, and an outbound relationship to `architecture/governance-model` that remains after the body is removed. Human command-line show of the target reports a corresponding inbound relationship that remains after the body is removed.
- Raw mode on that identity equals the on-disk file. Structured command-line inspect and **membundle_show** are parseable as a concept record and include the same identity, type, and body; after the body is stripped they need not still contain the related identity.
- Show of an identity that does not exist does not succeed and identifies the missing identity. Show of reserved identity `index` does not succeed.
- Absence: a show that only prints a filename list, or that cannot distinguish inbound from outbound links, fails this feature.

---

### FP-04: Search concepts and path-bound governance

**Public entry.** The `membundle` **search** command, and the **membundle_search** Model Context Protocol tool. The caller supplies a query string, or a source-file path to discover governing concepts, or both, plus an optional bundle path, an optional result cap, and optional structured output.

**Normal behavior.**

**Keyword search.** The product splits the query into terms case-insensitively: letters and digits, including non-ASCII letters, stay inside a term; other characters split terms. It scores every concept using those terms against title, tags, description, concept identity, and body. A term matches a field when that field contains a token that equals the term or starts with the term. A concept that matches nothing is omitted. Structured results include identity, type, title, description, effective governance, code_refs if any, a numeric score, which fields matched (from the set: title, tags, description, id, body), tags if any, and inbound/outbound identities if any. Results are ordered by score descending; equal scores are ordered by concept identity ascending. When one concept matches a term in its title and another matches the same term only as a single incidental body occurrence, the titled concept ranks first. The numeric score formula beyond that title-over-incidental-body contrast and the score-then-identity order is the implementer’s and is not scored. When structured output is not requested, human output makes each hit identifiable as one concept, on a carrier distinct from a detached governance word, from a detached list of the three governance words, and from a structured record. That hit’s governance badge, one of constraint, hold, or context, is a prefix of that hit. How the hit is identified, and the punctuation around the badge, are the implementer’s and are not scored. A human hit’s text runs from its badge to the next hit’s badge; path-bound hits also name their matched fields there (see Path-bound search).

**Path-bound search.** When the caller supplies a source path, the product keeps only concepts whose code_refs list matches that path. A code_ref matches when it is the same path (slash-normalized, with an optional leading `./` or `/` ignored), when it is a directory prefix of the path, when a glob matches the entire slash-normalized path with stars not crossing a slash (so `*.go` matches `foo.go` and does not match `pkg/foo.go`), or when it uses a recursive `**` wildcard (including `**/*.go`-style suffix matching on the filename). Absolute paths still match the same relative code_ref. Matching concepts are ordered first by governance authority: **hold**, then **constraint**, then **context**. Within the same governance, a higher combined score ranks first (path match plus any keyword score if a query was also supplied); remaining ties use concept identity ascending. Hits report that they matched on code_refs, and also any keyword fields if a query was supplied. That report is also made when structured output is not requested: each path-bound human hit’s text names `code_refs` and exactly the keyword fields that matched, spelled as the structured field names (title, tags, description, id, body), and does not use any of those six names otherwise (for example as labels).

If a path filter is supplied but no code_ref matches, the search succeeds with no hit records even if keywords would have matched other concepts; on structured command-line output an empty list and a null JSON value are both that outcome, and a payload that contains hit records is not. If the path filter is empty and a query is supplied, behavior is ordinary keyword search.

**Limits.** If the caller omits a cap or supplies a non-positive cap, the product returns at most **10** hits. If the caller requests more than **100**, the product returns at most **100**. Queries longer than **1000** characters are truncated to 1000 characters before matching. After splitting into terms, at most the first **50** terms are used for matching; further terms are ignored. These four quantities are scored.

**Boundary / error behavior.** On the command line, if neither a query nor a path filter is supplied, search does not succeed and prints usage. The Model Context Protocol search tool, given neither a query nor a path, succeeds with an empty list. A missing bundle fails as a load error. Zero hits is success with no hit records (human text states that nothing matched); on structured command-line output an empty list and a null JSON value are both that outcome, and a payload that contains hit records is not. Search does not write the bundle.

**Verifiable oracle.**

- In a bundle with one concept titled “OAuth2 PKCE” and another whose body mentions OAuth2 only in passing, a query for OAuth2 returns the titled concept first and reports a title match on that hit.
- Two concepts with identical titles “Shared title” and identities `alpha` and `zeta`, queried with a term that matches only that title, return `alpha` before `zeta` when the cap is 1.
- A concept with governance hold and code_refs covering `pkg/auth/login.go`, plus a constraint concept covering the same path, plus a context concept covering it, appear in that governance order when searching by that path, even if the context concept would score higher as a keyword hit.
- A concept whose code_refs is `*.go` is a hit for path `foo.go` and is not a hit for path `pkg/foo.go`.
- Requesting a cap of 3 returns at most 3 hits. Requesting a cap of 100000 returns at most 100. Omitting the cap, or supplying a non-positive cap, returns at most 10. A query longer than 1000 characters is matched using only its first 1000 characters, so a distinctive term that begins only after that cut does not match a concept that only that later term would have matched. A query whose first 50 terms do not include a later distinctive term does not match a concept that only that later term would have matched.
- A Unicode query matching a Unicode title returns that concept.
- When structured output is not requested, each human hit is identifiable as one concept and is prefixed with that hit’s governance badge, one of constraint, hold, or context. A detached governance word, a legend of those three words without the hits, or a structured record in place of that human text does not pass. How the hit is identified, and the punctuation around the badge, are the implementer’s and are not scored. On a path-bound search without structured output, each hit’s text (from its badge to the next hit’s badge) names `code_refs` and exactly the keyword fields that matched, using the structured field names; a hit that omits `code_refs`, omits a matched field, or names a field that did not match does not pass.
- Absence: a search that ignores code_refs, that ranks context above hold for a path query, that is non-deterministic across identical reruns, or that always returns every concept, fails this feature.

---

### FP-05: Create a concept with index and log bookkeeping

**Public entry.** The `membundle` **create** command, and the **membundle_create** Model Context Protocol tool. The caller supplies a concept identity, an optional bundle path, a type (CLI default **Fact** if omitted), a title (CLI default if omitted, empty, or only whitespace: the identity’s final path segment), an optional description, optional Markdown body, optional comma-separated tags (CLI), and optional CLI actor (default **agent/cli**; an actor that is empty after trimming is written as **agent/membundle-tool**). If the caller omits the path, the tool uses only the omit-path default in “Bundle layout a caller can construct”: a nested conventional bundle subdirectory when the current working directory contains one, otherwise the current directory. If the caller names a path, that named path is the write root even when it has no root `index.md` and contains a nested conventional bundle subdirectory. CLI callers may skip log or parent-index bookkeeping. The Model Context Protocol create tool requires a type and a non-whitespace title, always writes actor **agent/mcp**, and always performs log and parent-index bookkeeping.

**Normal behavior.** The product writes `identity.md` under the bundle (creating parent directories). The file is MEMBUNDLE v0.2 Markdown: YAML frontmatter with at least type, title if any, description if any, tags if any, and a generated mapping whose **by** is the actor and whose **at** is the current UTC time in ISO 8601 combined date-and-time form, then the body. Unless the caller skipped index bookkeeping, the immediate parent directory’s `index.md` lists the new concept as a Markdown bullet whose link target is the concept filename and whose visible text is the title and description (description omitted from the listing if empty). A missing parent index is created: if that parent is nested, the new index has no MEMBUNDLE version frontmatter; if that parent is the bundle root, the new index declares MEMBUNDLE version 0.2. A nested create does not write a missing root index. Unless the caller skipped log bookkeeping, `log.md` gains a **Creation** bullet under today’s UTC ISO 8601 date heading (that heading is inserted at the top if today is not already present). Structured CLI output, when requested, indicates success and names the identity and path.

**Boundary / error behavior.** Missing identity prints usage and fails. Invalid identities a command-line argument can carry (empty, absolute, `..` traversal, leading hyphen, newline, carriage return, or tab, reserved `index` / root `log` / root `AGENTS`) fail without writing a concept on both the command line and Model Context Protocol create. On Model Context Protocol create, where the identity is a string the caller supplies, an identity that contains a null byte fails as a tool error and writes no concept; command-line create is not required to demonstrate a null-byte identity, because a process argument cannot contain that byte. Type that is empty or only whitespace fails (CLI omit of type still uses Fact). MCP title that is empty or only whitespace fails as a tool error and writes no concept; CLI empty or whitespace title uses the identity’s final path segment as above. A description that is present but only whitespace fails; omitting the description succeeds on both CLI and MCP. Type, title, description, and actor must not contain newlines or the YAML frontmatter delimiter of three dashes; such values fail without writing. Writes that would resolve outside the bundle fail. MCP create without identity, type, or title fails as a tool error. Create of an identity that already exists overwrites that concept file and still performs bookkeeping as a creation.

**Verifiable oracle.**

- After create of `decisions/auth-flow` with type Decision, title “OAuth2 Authorization Flow”, and a one-sentence description, the bundle contains `decisions/auth-flow.md` whose frontmatter type is Decision and whose generated.by is `agent/cli` for CLI (or `agent/mcp` for MCP). Holding MEMBUNDLE v0.2, the file has YAML frontmatter with non-empty type, and concept identity is the path without `.md`.
- The parent `decisions/index.md` contains a list item linking to `auth-flow.md` with that title and description. Root `log.md` has today’s UTC YYYY-MM-DD heading (ISO 8601) and a Creation bullet naming the new file.
- On the CLI with log skipped, `log.md` does not gain that Creation bullet. On the CLI with index skipped, the parent index is not updated. The Model Context Protocol create tool cannot skip those updates: it still writes the parent listing and the Creation bullet. MCP create of `decisions/auth-flow` that omits title does not succeed and writes no file.
- Create of `../outside` or `index` does not succeed and does not write outside the bundle. Model Context Protocol create of an identity that contains a null byte fails as a tool error and writes no concept file.
- After create with an explicit bundle path whose directory has no root `index.md` but contains a conventional nested `knowledge/` subdirectory, the new concept file and the default parent-index and log bookkeeping files are present under the named path and absent from that nested subdirectory. Command-line human success and the Model Context Protocol create confirmation name the named path as the bundle. Omitting the path still uses the cwd-versus-nested-subdirectory default.
- Absence: a create that writes a Markdown file without YAML type, or that does not update the parent index when bookkeeping was not skipped, fails this feature.

---

### FP-06: Update an existing concept

**Public entry.** The `membundle` **update** command, and the **membundle_update** Model Context Protocol tool. The caller supplies an existing concept identity, optional new title, description, and/or body, optional CLI actor (default **agent/cli**; an actor that is empty after trimming is written as **agent/membundle-tool**), optional bundle path, and optional structured output. If the caller omits the path, the tool uses only the omit-path default in “Bundle layout a caller can construct”: a nested conventional bundle subdirectory when the current working directory contains one, otherwise the current directory. If the caller names a path, that named path is the write root even when it has no root `index.md` and contains a nested conventional bundle subdirectory. Command-line human success and the Model Context Protocol update confirmation name the named path as the bundle. CLI callers may skip log or parent-index bookkeeping. The Model Context Protocol update tool always writes actor **agent/mcp** and always performs log and parent-index bookkeeping.

**Normal behavior.** The product loads the bundle, finds the identity in the loaded concept set, applies only the fields the caller supplied, rewrites the concept file, refreshes generated provenance (actor and current UTC ISO 8601 timestamp), and by default updates the parent index listing and appends an **Update** bullet to `log.md` under today’s UTC date heading. Fields the caller did not supply remain. Unknown extra frontmatter keys present before the update remain after the rewrite (MEMBUNDLE v0.2 unknown-key tolerance). Verified provenance and sources already on the concept remain.

**Boundary / error behavior.** Missing identity prints usage and fails. Invalid identity fails as in create. A load failure is a load error. An identity not in the loaded concept set fails as not found and does not rewrite, including a nested identity whose file is named `log.md` even when that file already exists. Empty/whitespace title, newline or three-dash delimiter in title/description/actor, and path-escaping writes fail without a successful update. A description that is present but only whitespace fails; supplying an empty description clears it; omitting the description leaves the existing description. MCP update without identity fails as a tool error. Update does not create a new identity.

**Verifiable oracle.**

- A concept `decisions/auth-flow` with description “Use PKCE.” and a custom extra frontmatter key, after an update that changes only the description to a new sentence, shows the new description, still has the extra key, still has its original type, and has a new generated.at. The parent index listing text follows the new description. `log.md` contains an Update bullet for that file under today’s UTC ISO 8601 date.
- Update of a missing identity does not succeed and does not create a file. Command-line and Model Context Protocol update of a nested identity whose file is named `log.md`, after that file is already present, is the same not-found failure and does not rewrite the file. Update of a nested identity whose file is not named `log.md`, present as a concept file, succeeds and rewrites. Update of a nested identity whose file is named `AGENTS.md`, present as a concept file, succeeds and rewrites.
- On the CLI with log skipped, `log.md` does not gain that Update bullet. On the CLI with index skipped, the parent index listing is not updated. The Model Context Protocol update tool cannot skip those updates: it still writes the parent listing and the Update bullet.
- An update that supplies an empty description removes the description; an update that omits the description leaves it. A whitespace-only description does not succeed.
- After update with an explicit bundle path whose directory has no root `index.md` but contains a conventional nested `knowledge/` subdirectory that holds the concept, the rewritten concept file and the default parent-index and log bookkeeping files are present under the named path; those nested files remain as they were before the update. Command-line human success and the Model Context Protocol update confirmation name the named path as the bundle. Omitting the path still uses the cwd-versus-nested-subdirectory default.
- Absence: an update that drops unknown frontmatter keys, or that always requires recreating the file under a new identity, fails this feature. Holding MEMBUNDLE v0.2, unknown keys must survive a producer rewrite.

---

### FP-07: Relate two concepts with a relative Markdown link

**Public entry.** The `membundle` **relate** command, and the **membundle_relate** Model Context Protocol tool. The caller supplies a source identity, a target identity, optional relationship prose, optional CLI actor (default **agent/cli**; an actor that is empty after trimming is written as **agent/membundle-tool**), optional bundle path, and optional structured output. If the caller omits the path, the tool uses only the omit-path default in “Bundle layout a caller can construct”: a nested conventional bundle subdirectory when the current working directory contains one, otherwise the current directory. If the caller names a path, that named path is the write root even when it has no root `index.md` and contains a nested conventional bundle subdirectory. Command-line human success and the Model Context Protocol relate confirmation name the named path as the bundle. The Model Context Protocol relate tool always writes actor **agent/mcp**.

**Normal behavior.** Both concepts must exist. The product appends to the source body a relative Markdown link to the target file (path relative to the source file’s directory, slash-separated) using the target’s title as link text (or the target’s final identity segment if title is empty). If relationship prose is supplied and is not empty after trimming, the list item is a link followed by that prose; if omitted or only whitespace, the list item is a “Related to” link. The item is placed under an existing single-hash level-1 heading whose text is exactly “Related Concepts” or “Related”, if that heading line already exists in the source body outside fenced code blocks; otherwise a new level-1 “Related Concepts” heading is created, including when the only same-text heading is a Setext heading (title line plus an equals underline). A deeper heading with those words is not reused. Generated provenance on the source is refreshed. `log.md` gains an Update bullet describing the link. The operation does not add a reciprocal link on the target.

**Boundary / error behavior.** Fewer than two identities prints usage and fails. Invalid identities fail as in create. Source equal to target fails. Missing source or missing target fails without writing. A second relate of the same source, target, and prose that is already present in the related section succeeds without duplicating the line, without rewriting the source file, and without appending another log bullet. Path-escaping identities fail. Model Context Protocol relate without a source or target identity fails as a tool error and writes no link.

**Verifiable oracle.**

- Relating `architecture/tooling` to `architecture/layers` with prose “implements the 5-layer architecture” leaves a relative link in the source body to `layers.md` (or `./layers.md`-equivalent relative form) together with that prose, under a level-1 Related Concepts (or Related) heading, and a log Update naming both files. The source’s generated.by is `agent/cli` for CLI (or `agent/mcp` for MCP).
- When the source body already has a single-hash level-1 heading whose text is exactly “Related Concepts” or “Related” outside fenced code blocks, the new list item sits under that heading and no second related heading is added. When the only same-text heading is Setext (title line plus an equals underline), a new level-1 “Related Concepts” heading is created and the list item sits under that new heading, not under the Setext block.
- After the same relate is repeated, the related section still contains one such link, not two identical lines, and the source file and `log.md` are unchanged from the first successful relate.
- Relating a concept to itself does not succeed. Relating when either identity is absent does not succeed.
- After relate with an explicit bundle path whose directory has no root `index.md` but contains a conventional nested `knowledge/` subdirectory that holds both concepts, the rewritten source file and the log Update are present under the named path; those nested files remain as they were before the relate. Command-line human success and the Model Context Protocol relate confirmation name the named path as the bundle. Omitting the path still uses the cwd-versus-nested-subdirectory default.
- Absence: a relate that only stores a sidecar database row and does not put a relative Markdown link in the source file fails this feature.

---

### FP-08: Validate MEMBUNDLE v0.2 conformance and the producer gate

**Public entry.** The `membundle` **validate** command, and the **membundle_validate** Model Context Protocol tool. The caller names a bundle (optional; default bundle rule). Optional modes: **strict producer gate**, **stale-date gate**, **drift audit**, **agents governance check**, and structured output. MCP validate applies the producer gate by default unless the caller sets it off, always applies the drift audit, and applies the stale-date gate only when requested.

**Normal behavior.** The product loads the bundle and reports: bundle path, declared MEMBUNDLE version if any, concept count, hard errors, warnings, gate findings, broken concept links, orphan identities, stale count, whether the bundle is conformant, and whether the producer gate passed.

**Conformance (always).** A concept file without YAML frontmatter is a hard error. A concept whose type is missing or empty is a hard error. A README.md inside the bundle without frontmatter is a hard error. Whitespace-only title is a hard error. If any hard error exists, the bundle is not conformant.

**Warnings (advisory unless a gate mode promotes a related class of finding).** Nested `index.md` files that have frontmatter; `log.md` two-hash headings that are not ISO 8601 YYYY-MM-DD; a concept-body reference written `[^label]` outside fenced code whose label matches none of the concept’s sources ids, when the concept lists at least one sources id (the label is the footnote key and is what gets compared to the concept’s sources ids; a sources id is the value of the id key on a sources entry, and that value is what the `[^label]` label is compared to; id is a separate sources-entry key from resource, the last-modified field, and sources.author; a label equal to that id value is a listed sources id, and a label equal to the entry’s resource, last-modified date, or author, while unequal to its id, matches none of the sources ids; the same spelling inside a fence, a label that matches a listed sources id, and that spelling in a concept with no sources id are not this warning, and this warning stays advisory and does not by itself fail the producer gate); invalid actor strings on generated.by, verified.by, or sources.author; a verified entry with no by; generated.at or verified.at that is missing or not a parseable timestamp; a sources last-modified date that is not YYYY-MM-DD; stale_after that is not YYYY-MM-DD; a concept whose stale_after calendar date is today or earlier in UTC (also counted in stale count).

**Gate findings (fatal in strict mode when the bundle declares version 0.2).** Legacy `timestamp` frontmatter leftover from v0.1; a single-hash body heading whose text is Citations leftover from v0.1, outside fenced code blocks; a sources entry with no resource; generated with no by; a verified.at that predates generated.at; a present governance value other than constraint, hold, or context; a present status value other than draft, stable, or deprecated; a code_refs entry that is absolute or contains `..` traversal.

**Connectivity.** Markdown links from a concept body (outside fences, not external URLs) to a missing concept, or to reserved `index.md` / `log.md` / `AGENTS.md`, are broken links. When the bundle has more than one concept, a concept with no inbound and no outbound concept-to-concept links is an orphan. A single-concept bundle is not orphaned by that rule.

**Strict producer gate.** When requested (CLI strict mode; MCP default on), broken links, orphans, and (if declared version is 0.2) any gate finding fail the producer gate. They do not by themselves make the bundle non-conformant if there are no hard errors.

**Stale-date gate.** When requested, a non-zero stale count fails the producer gate. Without this mode, stale concepts are warnings only, including under strict mode.

**Drift audit.** When requested (CLI drift mode; always on for MCP validate), the product warns when an index list item’s description text does not contain the linked concept’s description after both sides are compared as follows: case-insensitive; backslash, double quote, single quote, backtick, asterisk, and underscore removed; internal whitespace collapsed; a trailing period stripped. It also warns when a non-glob code_refs path exists neither in the project directory that contains the bundle nor inside the bundle. Drift warnings do not fail the producer gate by themselves.

**Exit status (CLI).** Successful conformant gate-pass ends with status 0. Non-conformance or a failed producer gate ends with status 1. Failure to load the bundle ends with status 2. These three statuses are scored.

**Agents check option.** When requested, validate also runs the AGENTS.md MBG-and-symlink check (FP-10) against `AGENTS.md` in the named path, or in that path’s parent if only the parent contains `AGENTS.md`. Failure of that check ends with status 1.

**Boundary / error behavior.** A missing bundle directory is a load failure (status 2). An empty but well-formed initialized bundle with version 0.2, no concepts, and no errors is conformant and passes the producer gate.

**Verifiable oracle.**

- Holding this document and Open Bundle Format (MEMBUNDLE) v0.2, an outside party can decide conformance of a fixture: a concept whose only missing required field is type is non-conformant; a concept with type Fact and no other fields is conformant.
- A two-concept bundle with no Markdown links between them, under strict mode, is conformant but fails the producer gate, and CLI status is 1. The same bundle without strict mode is conformant, the gate passes, and CLI status is 0, while orphans still appear in the report.
- A concept with stale_after equal to yesterday’s UTC date increments stale count. Without stale-date gating, strict mode still passes if there are no other gate failures. With stale-date gating, the gate fails.
- A declared 0.2 bundle whose concept still has a `timestamp` field produces a gate finding; strict mode then fails the gate.
- A broken relative link to a non-existent `missing.md` is listed as a broken link and fails the gate only in strict mode.
- Drift mode warns when an index listing’s description does not contain the concept description after the comparison in Normal behavior; that warning alone does not flip the producer gate to failed.
- Load of a non-existent path yields CLI status 2.
- Absence: a validator that only checks that files exist, or that treats orphans as hard non-conformance even without strict mode, fails this feature.

---

### FP-09: Model Context Protocol server over standard I/O

**Public entry.** The `membundle` **mcp** command, given an optional bundle path (default bundle rule). The process reads newline-delimited JSON-RPC from standard input and writes newline-delimited JSON-RPC to standard output until input ends.

**Normal behavior.** The server speaks JSON-RPC 2.0 as used by the Model Context Protocol, protocol version **2024-11-05**. On initialize, it replies with that protocol version, server identity **membundle-agent-memory**, and capabilities that advertise tools, resources, and prompts without list-changed streaming. A subsequent initialized notification produces **no** response. Cancel notifications produce no response. Ping replies with an empty result. Resources list and prompts list reply with empty collections. Tools list replies with exactly the six tools membundle_search, membundle_show, membundle_create, membundle_update, membundle_relate, and membundle_validate. Tools call invokes the same observable behaviors as FP-03 through FP-08, including search limits (default 10, max 100), path-bound search, create/update bookkeeping, relate links, and validate’s MCP defaults (producer gate on unless turned off, drift always on, stale-date gate optional). Tool success and tool-level failures are returned as MCP tool results (text content; failures marked as tool errors), not as a substitute for JSON-RPC protocol errors. Create uses actor `agent/mcp`; update and relate use `agent/mcp`.

If the process environment names an MEMBUNDLE MCP root directory (`MEMBUNDLE_MCP_ROOT`), that directory is the workspace root. Otherwise, if the server was started with a bundle directory whose final segment is `knowledge/`, the workspace root is that directory’s parent; otherwise the workspace root is the started path (or the current directory). A tool argument that names a bundle path is resolved inside that workspace root.

**Boundary / error behavior.** A line that is not JSON is a JSON-RPC 2.0 parse error (code −32700) and does not crash the server. A request that carries an id whose method is unknown is JSON-RPC 2.0 method-not-found (code −32601). A notification (no id) for an unknown method produces no reply. A tools-call whose parameters are a JSON array, a string, or omitted is JSON-RPC 2.0 invalid-params (code −32602). Notifications never receive replies. A bundle path that resolves outside the workspace root fails as a tool error naming path traversal, without reading that outside directory. An unknown tool name fails as a tool error. Load failures of a named bundle fail as tool errors. A search tool call with neither query nor path succeeds with an empty list (unlike the command line).

**Verifiable oracle.**

- Holding JSON-RPC 2.0 and Model Context Protocol version 2024-11-05, an initialize request returns protocol version 2024-11-05; a JSON-RPC notification with no id receives zero output lines; a malformed line yields parse error code −32700; an unknown method on a request that has an id yields method-not-found code −32601; a tools-call whose parameters are a JSON array yields invalid-params code −32602.
- Tools list includes all six names membundle_search, membundle_show, membundle_create, membundle_update, membundle_relate, membundle_validate and no additional memory-mutation tools.
- After initialize, a tools-call to membundle_create for a new identity followed by membundle_show for that identity returns the created concept; membundle_search finds it; membundle_validate reports it in concept count.
- A tools-call whose bundle path is an absolute directory outside the workspace root fails as a tool error and does not read that directory.
- Absence: a process that only prints help, that replies to notifications, that omits create/update/relate tools, or that requires HTTP instead of stdio, fails this feature.

---

### FP-10: AGENTS.md Bundle Action Grammar lint, domain codex, and SSoT links

**Public entry.** The `membundle` **agents** command with subcommands **lint**, **init**, **link**, and **check**. Validate’s optional agents-governance check (FP-08) invokes the same check as **check**.

**Normal behavior.**

**Lint.** The product reads an `AGENTS.md` path (default: `AGENTS.md` in the current directory). It estimates working-memory tokens for the text between `<!-- BEGIN MEMBUNDLE AGENT MEMORY -->` and `<!-- END MEMBUNDLE AGENT MEMORY -->` when both delimiters are present and the end delimiter follows the begin delimiter; otherwise it estimates tokens for the whole file. Default budget cap is **400** tokens; a non-positive caller cap is treated as 400; the caller may supply another positive cap. Findings:

- **MBG-001:** any non-ASCII character on a line is an error for that line.
- **MBG-002:** in a section whose heading contains “constraints”, “invariants”, or “rfc 2119” ignoring letter case, or whose heading starts with “1.”, each list item that starts with a hyphen and a space must begin, after that hyphen marker, with an RFC 2119-style modal from the Finite vocabularies list (MUST, MUST NOT, NEVER, PREFER, ALWAYS, SHOULD, MAY, or an exclamation mark) followed by a space, or with that token alone. That section is the lines after the heading until the next heading of any level, so a deeper heading ends the section and a line after that heading is not in the section. A backtick immediately before the modal is accepted. RFC 2119 is the named standard for those modal verbs.
- **MBG-003:** a line containing `membundle_` or `tool_` with more opening parentheses than closing parentheses is an error.
- **MBG-004:** this rule applies only when a heading starts with “0.” or contains “domain codex” ignoring letter case. That section is the lines after the heading until the next heading of any level, so a deeper heading ends the section and a line after that heading is not in the section. If such a section exists, some line in that section must mention Mermaid (any case); otherwise this rule errors. If no such section exists, MBG-004 does not fail.
- **MBG-005:** if the working-memory token estimate exceeds the budget cap, this rule errors and the budget is marked exceeded.

The five rules emit errors, not warnings. Lint passes only when the error count is zero. Structured output, when requested, reports pass/fail, error and warning counts, findings (including rule identifiers MBG-001–MBG-005), and a token-statistics grouping distinct from those three. After pass/fail, counts, and findings are removed, that grouping still reports three facts: the in-force budget cap as a sortable integer (400 when the caller omits the cap or supplies a non-positive cap; the caller’s positive cap otherwise); a two-state exceeded mark that is the over-budget state exactly when MBG-005 is among the findings and the under-budget state when it is not; and an estimate of the working-memory text (the delimited inner when both HTML comment delimiters are present and the end follows the begin, otherwise the whole file) as a sortable integer whose exact value is not scored. Two structured runs of the same file that differ only in the caller cap must differ in the reported in-force cap. Two structured runs that differ only in whether the estimate exceeds the cap must differ in the exceeded mark, matching MBG-005 presence. Field names and the encoding of the exceeded mark are the implementer’s. Human output prints the in-force budget.

**Init.** Writes `AGENTS.md` under a target root (default current directory) using one of the five domain profiles (software, research, legal, coaching, books). The file includes a Domain Codex section 0 specialized to that profile (software mentions clean architecture and TDD; research mentions citation integrity; legal mentions privacy/compliance; coaching mentions ICF ethics; books mentions canon and spoilers), the MEMBUNDLE Agent Memory delimited block, and Mermaid diagram assertions. Default profile is software. An unknown profile name is treated as software. Optional project name is substituted into the title.

**Link.** Requires a canonical `AGENTS.md` in the target root. It creates the four SSoT symbolic links listed under Finite vocabularies, creating `.github/` if needed. If a path already is the correct symlink, it is left as already valid. If a path exists and is not that symlink, the operation records a failure unless the caller requested overwrite, which replaces the path with the symlink. Check-only mode reports each mapping as valid or invalid without creating links.

**Check.** Runs lint on that root’s `AGENTS.md` and then verifies all four SSoT links. Both parts must pass.

**Boundary / error behavior.** Lint of a missing file does not succeed. Init without overwrite fails if `AGENTS.md` already exists. Link without `AGENTS.md` does not succeed. Check fails if lint fails or any SSoT mapping is missing or points at the wrong target. A file that exists at a link path but is not a symlink is invalid in check-only mode.

**Verifiable oracle.**

- A Domain Codex that contains a non-ASCII arrow character yields an MBG-001 error and a failed lint. The same file with only ASCII passes MBG-001.
- An invariants hyphen list item “Please search before editing” yields MBG-002; a hyphen list item beginning with MUST does not. A heading matches “constraints”, “invariants”, or “rfc 2119” ignoring letter case, including when the heading’s letter case differs from those fragments. The section is the lines after that heading until the next heading of any level, so a deeper heading ends the section and a line after that heading is not in the section.
- A Domain Codex section 0 with no occurrence of the word Mermaid yields MBG-004; adding a Mermaid mention removes that finding. A heading matches “domain codex” ignoring letter case. The section is the lines after that heading until the next heading of any level, so a deeper heading ends the section and a line after that heading is not in the section; a Mermaid mention only after that deeper heading does not satisfy MBG-004. A file with no heading that starts with “0.” and no heading that contains “domain codex” ignoring letter case does not fail MBG-004.
- A file whose delimited MEMBUNDLE Agent Memory block (text between the two HTML comment delimiters) is clearly larger than a caller-supplied cap of 20 tokens fails MBG-005; the same file against the default cap of 400 may pass. The default cap is **400**. A non-positive cap is treated as 400. The formula that produces the token estimate is the implementer’s and is not scored; pass/fail against the cap is scored. Structured lint of that same file reports a token-statistics grouping distinct from pass/fail, counts, and findings: the in-force cap as a sortable integer that is 400 when the cap is omitted or non-positive and 20 when the caller supplies 20; a two-state exceeded mark that is the over-budget state when MBG-005 is among the findings and the under-budget state when it is not; and a working-memory estimate as a sortable integer whose exact value is not scored. Two structured runs of that file that differ only in the caller cap differ in the reported in-force cap. Two structured runs that differ only in whether the estimate exceeds the cap differ in the exceeded mark, matching MBG-005 presence. Human output prints the in-force budget.
- Agents init with profile legal, on an empty directory, creates `AGENTS.md` whose Domain Codex is the legal/compliance profile (observably different from the software profile). A second init without overwrite does not succeed. Unrecognized profile `unknown-domain` still writes a file using the software profile.
- After link on a root that contains `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, and `.windsurfrules` are symbolic links to `AGENTS.md`, and `.github/copilot-instructions.md` is a symbolic link to `../AGENTS.md`. Check-only then reports all four valid. If `CLAUDE.md` is a regular file, check-only reports it invalid; overwrite link replaces it with the symlink.
- Absence: a lint that ignores non-ASCII, an init that always writes the software codex even when legal was requested, or a link command that copies file contents instead of creating the four symbolic links, fails this feature.
