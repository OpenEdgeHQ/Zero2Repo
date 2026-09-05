# VCS Orbulk — Full Product Requirements Document

## Product overview

**VCS Orbulk** (VCS Large Object Store) is a command-line Git extension and accompanying client–server specification for versioning large files alongside an ordinary Git repository. Instead of storing large file bytes as Git blobs, VCS Orbulk stores compact **pointer** blobs in Git and keeps the real content in a separate object store that is synchronized with a remote VCS Orbulk endpoint when the user fetches or pushes.

The finished product is a single compiled command-line utility named `git-orbulk`. Users interact with it as a Git extension (`git orbulk <command>`): each capability is reached by choosing a VCS Orbulk subcommand (and, for low-level filter and hook paths, by Git invoking those subcommands automatically). The client ships as a self-contained binary for Mac, Windows, Linux, and FreeBSD, and is intended to be used as that binary—not as a library API for other programs to import.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, wire media-type tokens, and other Interface Contract details are out of scope here. Every feature point below corresponds to behavior that exists in the finished product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Pointer** | A small UTF-8 text blob stored in Git in place of a large file. It names the content hash algorithm, object id, and byte size of the real content. |
| **LFS object** | The full file bytes identified by a pointer’s object id, stored outside Git’s object database. |
| **Local object store** | On-disk cache under the repository’s Git directory (by default under `.git/lfs/objects`) where VCS Orbulk keeps objects locally. |
| **Endpoint** | The remote VCS Orbulk service URL used for batch negotiation, transfers, and locking for a given Git remote. |
| **Batch API** | The request/response exchange that asks the endpoint which objects need upload or download and how to transfer them. |
| **Basic transfer** | The default transfer style: download via HTTP GET and upload via HTTP PUT of raw object bytes at URLs supplied by batch negotiation. |
| **Clean** | Converting working-tree file bytes into a pointer (and storing the object locally) as Git stages content. |
| **Smudge** | Converting a pointer back into working-tree file bytes (fetching the object if needed) as Git checks content out. |
| **Track pattern** | A path pattern recorded in Git attributes so matching paths use the VCS Orbulk filter. |
| **Lock** | A server-side exclusive claim on a repository-relative path that blocks other users from pushing changes to that path when lock verification is enabled. |
| **Porcelain command** | A user-facing VCS Orbulk subcommand (track, fetch, push, and similar). |
| **Plumbing command** | A low-level VCS Orbulk subcommand intended mainly for Git filters, hooks, or automation (clean, smudge, filter-process, pre-push, and similar). |
| **Core capability** | A user-observable capability that reflects the product’s design goal; acceptance must prove the real behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public command inventory

The product exposes a fixed, finite set of subcommands. Porcelain commands: checkout, clone, completion, dedup, env, ext, fetch, fsck, install, lock, locks, logs, ls-files, migrate, prune, pull, push, status, track, uninstall, unlock, untrack, update, and version. Plumbing commands: clean, filter-process, merge-driver, pointer, post-checkout, post-commit, post-merge, pre-push, smudge, and standalone-file. Built-in help covers the suite and those subcommands. Feature points below group these entries by independently verifiable capability; they do not invent additional commands.

## Non-functional constraints

- **Form factor:** One command-line binary that Git can locate and invoke; not a stable embeddable library API or ABI.
- **Platforms:** Builds and runs on Linux, macOS, Windows, and FreeBSD-class systems. This case’s acceptance targets Linux with a recent Go toolchain, GNU make, and a working Git installation (Git 2.0.0 or newer; recent Git recommended).
- **Hardware:** CPU-only. No GPU or accelerator substrate is required or claimed. The mandatory execution substrate is a real host able to build the binary and run Git plus the VCS Orbulk CLI.
- **Storage model:** Large content is never required to live as ordinary Git blobs for tracked paths; Git history holds pointers, and the local object store plus remotes hold objects.
- **Empty files:** An empty working-tree file maps to an empty pointer (passthrough); empty content is not forced through the hashed-object path.
- **Protocol hash:** Newly written pointers use SHA-256 object ids expressed as lowercase hexadecimal, prefixed by the protocol’s SHA-256 hash-method label (exact token lives in the Interface Contract). SHA-256 is the only hash method current clients write.
- **Protocol constants:** Exact version-identifier strings, JSON media-type tokens, hash-method labels, and similar wire literals are fixed by the VCS Orbulk specification and appear in the Interface Contract. This PRD states their behavioral roles (exact string comparison, required headers) without prescribing implementer-internal encodings beyond what an outside observer must see.

## Capability discrimination (global)

Every feature point below is a **core capability**. The mandatory substrate is a real CPU host with a built VCS Orbulk binary and a usable Git installation for repository operations. None of these capabilities is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real CLI (and, where applicable, real HTTP/SSH endpoint) behavior matches the described outcomes.
- **Absent / hollow:** Subcommands missing; filters that pass bytes unchanged without storing objects; fetch/push that never contact an endpoint; lock commands that only print local fiction; migrate that does not rewrite history or attributes as specified.

Cheaper proxies (printing fixed fixture pointers, skipping network with fabricated success, or substituting an in-memory fake Git) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces the real filter, object store, or transfer protocol for a core capability.

**Negative control (Git / binary substrate):** When the VCS Orbulk binary is deliberately removed from the executable search path, or when Git repository prerequisites for a repo-bound command are absent, the corresponding operation must fail with a non-zero exit—not pass silently or skip.

## Non-goals

- Providing a stable Go (or other language) library API or ABI for third-party imports.
- Implementing the remote VCS Orbulk **server**; this product is the client (plus protocol documentation the client obeys).
- Guaranteeing every forge already speaks every optional transfer style (custom agents, tus uploads, pure SSH); the client must implement the negotiation and built-in paths described here when the peer supports them.
- Automatic undo of history rewrite after migrate; users must validate and force-push carefully themselves.
- Enabling the text merge driver by default on every tracked path; track records the ordinary `lfs` merge attribute, and Git’s default merge of pointer text remains the default until a user separately configures a merge driver (FP-18).

---

## Feature points

### FP-01: Command-line entry, help, version, and environment report

**Public entry:** The `git-orbulk` binary as a Git extension top-level command (`git orbulk`), with nested subcommands; the version-reporting path (`git orbulk version`); the `git orbulk env` subcommand; and built-in help for the suite and individual subcommands (`git orbulk help` and per-command help).

**Normal behavior:**

- Invoking VCS Orbulk with no subcommand, or asking for help on the suite or a subcommand, yields user-facing usage information and exits successfully.
- A version path reports that this build is VCS Orbulk and includes version identity suitable for support and diagnostics. The environment-report subcommand presents that same identity among related environment facts, distinct from dedicated per-remote server indications; a caller tells this build from another well-shaped VCS Orbulk version banner by agreement of those two presentations of that identity, not by matching an unrelated related-fact token. Wording, layout, and version-number string of that identity are not fixed.
- The environment-report subcommand prints the effective VCS Orbulk-related configuration a user needs to debug setup: discovered endpoints for remotes, filter configuration summary, and related environment facts. For each remote, the report presents a dedicated indication of the VCS Orbulk server URL that would be used, distinct from related environment facts that merely list configuration, Git remotes, or other setup details, and distinct from other remotes’ dedicated indications. A caller confirms which server would be used for a remote from that remote’s dedicated indication. After a repository or global LFS URL override, that dedicated indication must name the override rather than the URL derived from the Git remote; an echo of the override among related facts while the dedicated indication still names the derived URL does not count as replacement. A per-remote LFS URL override is observed on that remote’s dedicated indication, not a sibling’s (FP-06). This obligation does not fix the indication’s label, wording, or layout.

**Boundary / error behavior:**

- An option token that the invoked entry does not define — whether given at the top-level entry or after a known subcommand — fails with a non-zero exit and a clear error on standard error, and is distinguishable from running the same entry without that token. Where a command defines mutually incompatible options, those combinations fail with the same shape. Unknown subcommands likewise fail with a non-zero exit and a clear error on standard error.
- Environment report remains usable in a repository that has remotes but has never transferred objects yet: the dedicated indication still names the URL that would be used after derivation or override.

**Verifiable oracle:**

- Success: the built binary reports version identity that agrees with the environment report’s related-fact presentation of this build, and that agreement is of that identity rather than of an unrelated related-fact token; help for the suite and for at least one porcelain subcommand is available; the environment report presents, for each remote, a dedicated indication of the VCS Orbulk server URL that would be used, distinct from related environment facts; after a repository or global LFS URL override that dedicated indication names the override rather than the derived URL; a related-facts echo of an override while the dedicated indication still names the derived URL does not satisfy the report.
- Failure / absence: no runnable CLI; version cannot be reported, or the version path’s identity disagrees with the environment report’s related-fact presentation of this build; undefined option tokens are accepted as success; environment report omits that dedicated indication, invents unrelated output, or treats a related-facts echo of an override as replacement while the dedicated indication still names the derived URL.

---

### FP-02: Install, uninstall, and repository hook update

**Public entry:** The `git orbulk install`, `git orbulk uninstall`, and `git orbulk update` subcommands.

**Normal behavior:**

- Install configures Git’s clean and smudge filters under the filter name `lfs` (and the long-running process-filter equivalent that modern Git prefers) in the chosen Git configuration scope so Git will invoke VCS Orbulk for attributed paths. By default it writes to the user’s global Git configuration and does not overwrite an existing non-Orbulk filter definition unless the user forces replacement.
- When install runs inside a repository (unless the user asks to skip repository changes), it installs VCS Orbulk’s repository hooks into the repository’s hooks directory, or into the directory named by Git’s shared hooks-path setting when that setting is in effect and the installed Git is new enough to support it (Git 2.9.0 or newer). The installed hooks are: **pre-push** (uploads LFS objects before Git refs update), **post-checkout**, **post-commit**, and **post-merge** (enforce lockable working-tree permissions—see FP-10).
- Install supports scopes: global (default), local repository, worktree (when Git is at least 2.20.0 and worktree config is enabled), system, or an explicit configuration file path. Combining more than one of local, worktree, system, and explicit-file is invalid. It can install filters while skipping smudge downloads (so clones do not auto-download objects), and can install filters while skipping repository hook installation.
- When an existing hook body would block automatic installation, **manual mode** leaves that hook file unchanged and emits caller-visible hook-integration guidance on that conflict path. Preserve-alone is not enough: non-force automatic install also leaves a foreign body untouched while failing the conflict, so the discriminating observation is that instructional guidance together with the unchanged foreign body. The guidance must be distinguishable from empty output, from an unknown-option or other rejection error, and from a filter-install success message that says nothing about integrating hooks; it must give the caller enough hook-integration material to finish the merge of the blocked task without the tool rewriting the foreign body. A complete dump of all four hook-integration recipes satisfies that even when only one of the four hook files is the blocking foreign body. This obligation does not require remainders after stripping foreign-body and absolute-path covariates to differ across different blocked hook types, does not pin hook-type spellings, and does not fix the exact wording of the guidance or require any particular dump of hook script text.
- Uninstall reverses filter configuration in the chosen scope and, when run in a repository context analogous to install (and not asked to skip repository changes), removes the VCS Orbulk hooks for all four hook types above.
- Update refreshes repository hooks for the current repository so VCS Orbulk’s hook entry points remain installed after Git or repository layout changes. For each of the four hook types above:
  - If the hook file is missing, update installs the current standard VCS Orbulk hook body for that type (a script that invokes VCS Orbulk for that hook).
  - If the hook file exists and its body is empty, or is already exactly the current standard body, or is exactly one of the finite predecessor standard bodies this product recognizes for that same hook type (historical VCS Orbulk-issued scripts for that hook), a non-force update leaves an already-current body unchanged and silently replaces an empty or predecessor body with the current standard body.
  - If the hook file exists and its body matches none of those upgradeable cases (a custom or foreign hook), a non-force update leaves that file unchanged and the update fails for that conflict. Force overwrites such a file with the current standard body. Manual mode on that same conflict leaves the foreign body unchanged and emits the same class of caller-visible hook-integration guidance described above (distinguishable from empty output, rejection errors, and filter-only success chatter), instead of writing over the foreign body.

**Boundary / error behavior:**

- Install without force that encounters pre-existing non-Orbulk filter settings leaves those settings intact and fails.
- Worktree scope is rejected or unavailable on Git versions that lack the required worktree configuration support.
- Uninstall outside a repository still reverses filter configuration in the non-repository scope it claims (for example global filters) and does not pretend to have modified a repository that does not exist. Update outside a repository fails and does not modify filters or hooks.
- Non-force install or update that encounters a custom or foreign hook body fails without modifying that hook file. Force overwrites as described above. Manual mode on that conflict path preserves the foreign body and emits the hook-integration guidance described above rather than rewriting the file.

**Verifiable oracle:**

- Success: after install, Git configuration shows `lfs` clean/smudge (and process filter) settings pointing at VCS Orbulk; a repository gains pre-push, post-checkout, post-commit, and post-merge hooks that invoke VCS Orbulk; uninstall removes those filter settings and hooks; update re-establishes missing hooks; non-force update replaces an empty hook file with the current standard body while leaving a custom/foreign body untouched and failing; force replaces a custom/foreign body; on a blocking foreign hook, manual mode leaves that file unchanged and emits hook-integration guidance distinguishable from empty output, from rejection errors, and from filter-only success chatter that says nothing about integrating hooks.
- Failure / absence: Git never invokes VCS Orbulk on attributed paths; push does not upload LFS objects because no pre-push hook was installed; uninstall leaves filters or hooks in place; non-force update either skips empty-hook replacement or overwrites custom hooks without force; manual mode on a blocking foreign hook either rewrites the foreign body, emits nothing distinguishable from silence or rejection noise, or emits only filter-install success chatter with no hook-integration guidance.

---

### FP-03: Pointer format and pointer utility

**Public entry:** The `git orbulk pointer` plumbing subcommand, and every clean path that writes pointers into Git.

**Normal behavior:**

- A pointer is a UTF-8 text document of key/value lines. Each line is one key, one space, one value, and a Unix newline. Keys use only lowercase letters, digits, dot, and hyphen. Lines after the version line are sorted by key ascending. Values contain no carriage returns or newlines. The whole pointer must stay under 1024 bytes including any extension lines. There is exactly one canonical encoding for a given pointer payload.
- The first key is always the version key. Its value is a fixed protocol version identifier compared by exact string equality (no URL parsing or case folding). Newly written pointers use the current VCS Orbulk v1 protocol version identifier, which is distinct from the still-readable legacy pre-release identifier. The Interface Contract names those two exact strings in those two roles. That distinction is observable on generate and check: a generated pointer passes both ordinary check and strict check; a pointer that is otherwise the same except that its version identifier is the Contract’s still-readable legacy pre-release identifier — not some other still-readable alias this build happens to accept — is accepted by ordinary check and fails strict check with the already-distinguished valid-but-not-canonical status.
- Required keys after version include: an object-id key whose value is the hash-method label, then a colon, then a lowercase hex digest (SHA-256 for current clients), and a size key giving the object size in bytes as a decimal integer.
- Empty file content corresponds to an empty pointer document (passthrough): empty working-tree bytes are not rewritten into a hashed pointer body.
- Pointer blobs stored in Git preserve the executable bit of the replaced working-tree file.
- Keys in the protocol’s extension-line form (content-extension metadata lines on the pointer) are part of a valid pointer document and of the single canonical encoding. Using the pointer check entry on such a document: when those extension lines appear together with the required version, object-id, and size keys in the product’s canonical order, both ordinary check and strict check succeed; when the same extension keys and values are present but not in that canonical order, ordinary check still succeeds while strict check fails with a status distinguishable from the canonical case.
- The pointer subcommand can generate a pointer from a local file; compare that generated pointer to another implementation’s pointer file or to standard input; and check whether input is a valid pointer (with an optional strict mode that also requires the canonical encoding VCS Orbulk itself would write). Compare classifies the relation between the file-built pointer and the other pointer into three caller-distinguishable outcome classes: match, mismatch, and malformed-other. The class is determined by that relation, not by incidental properties of the input bytes alone: two different files each compared to their own matching other share one match class; each compared to the other file’s pointer share one mismatch class distinct from match; a non-pointer other yields a third, malformed class. The same three classes apply when the other pointer is supplied via standard input. Callers must be able to tell the classes apart without relying on input-byte covariates. This obligation does not fix the observable carrier to any particular exit status or message text.

**Boundary / error behavior:**

- Check mode exits non-zero when the input is not a valid pointer; strict check exits with a distinguishable failure status when the pointer is valid-but-not-canonical (different from a merely invalid pointer).
- Compare mode’s match, mismatch, and malformed-other outcome classes remain mutually distinguishable under the relation rules above, including when the other side is not a valid pointer document.
- Pointer documents that exceed the size limit, omit required keys, place required keys out of order, or are not parseable as key/value pointer lines are rejected as pointers by check and by filter smudge recognition, whereas carriage-return line endings, a missing final newline, and a well-formed pointer that still uses the Contract’s still-readable legacy pre-release identifier still parse as valid-but-not-canonical (ordinary check succeeds; strict check fails with the distinguishable status).
- Invoking check without exactly one of file-path or standard-input sources is invalid. Combining check with a compare-pointer file is invalid. Combining strict and non-strict check flags is invalid.

**Verifiable oracle:**

- Success: hashing a known file yields a deterministic pointer with version, oid, and size; that generated pointer passes both ordinary check and strict check; check rejects truncated or structurally invalid forms; carriage-return line endings, a missing final newline, and a pointer that is otherwise the same as that generated document except that its version identifier is the Contract’s still-readable legacy pre-release identifier remain ordinary-check successes that fail only under strict mode with the distinguishable valid-but-not-canonical status; a pointer that includes protocol extension-line keys in canonical order passes strict check, while the same keys out of that order fail strict check while still passing ordinary check; compare on two different files yields one shared match class when each is paired with its own matching other, one shared mismatch class (distinct from match) when each is paired with the other file’s pointer, and a third malformed class for a non-pointer other—observable without depending on input-byte covariates.
- Failure / absence: large files are stored as ordinary Git blobs; generated “pointers” are non-deterministic, binary, or missing required keys; check always succeeds; compare never makes the match class shared across two files each paired with their own matching other, or never makes the mismatch class shared across those files each paired with the other file’s pointer and distinct from both match and malformed.

---

### FP-04: Track and untrack patterns

**Public entry:** The `git orbulk track` and `git orbulk untrack` porcelain subcommands.

**Normal behavior:**

- Track with one or more patterns appends VCS Orbulk filter attributes for those patterns to the appropriate `.gitattributes` file (patterns follow Git attributes / gitignore glob rules). After track or untrack, the user must commit attribute changes themselves; VCS Orbulk does not create the Git commit.
- Each newly written tracking line names the filter, diff, and merge attributes as `lfs`, disables Git text conversion for the pattern, and may additionally mark the pattern lockable. Those four attribute roles (filter, diff, merge, text-disabled) are the finite set written for an ordinary track; lockable is the additional optional attribute.
- Track with no patterns lists currently tracked patterns. An **excluded pattern** is an attributes line that names the filter attribute in a form that disables or unsets filtering for that pattern (Git’s attribute negation or unset forms for the filter attribute), rather than enabling the `lfs` filter value. When such excluded patterns are present alongside tracked `lfs` filter patterns, the default listing surfaces those excluded pattern texts in a portion of the listing distinct from the tracked patterns. A mode that avoids listing excluded patterns still lists tracked patterns but omits that excluded-pattern portion. A machine-readable JSON listing mode is available when listing (and must not be combined with pattern arguments).
- Track can treat arguments as literal filenames (escaping glob metacharacters in the attributes file), mark patterns lockable (working-tree files become read-only unless locked—see FP-10), clear lockable, or dirty matching index entries without rewriting attributes so Git will re-clean files into VCS Orbulk.
- Dry-run reports what would change without mutating disk and implies detailed logging. Verbose still applies the track attribute mutation (unlike dry-run) while reporting in more detail which matching files would be touched; when matching previously Git-tracked files exist for the pattern, that report is distinguishable from the same track without verbose.
- Untrack removes the matching VCS Orbulk tracking lines (those that enable the `lfs` filter for the given patterns) from attributes. Untrack does not write excluded-pattern lines; excluded patterns are arranged by placing the disabling/unsetting filter attribute forms in attributes files directly.

**Boundary / error behavior:**

- Patterns must be quoted by the user in shells that expand globs; VCS Orbulk records the pattern text it is given.
- JSON list mode combined with pattern arguments is invalid.
- Track/untrack outside a Git repository fails.

**Verifiable oracle:**

- Success: after tracking a pattern such as all PSD files, `.gitattributes` contains an `lfs` filter rule for that pattern; listing shows it; when attributes also contain a pattern line that disables or unsets the filter attribute for a pattern (rather than enabling `lfs`), the default listing includes that pattern text in the excluded portion and the avoid-excluded listing omits that portion while still showing tracked patterns; untrack removes the matching `lfs` tracking lines for that pattern without adding excluded-pattern lines; lockable tracking marks paths as lockable in attributes; dry-run leaves attributes unchanged while reporting the intended change; verbose still writes the attribute rule and reports differently from non-verbose when matching files exist.
- Failure / absence: attributes unchanged; listing empty despite prior track; default and avoid-excluded listings cannot be told apart when excluded-form attribute lines are present; Git never routes matching files through VCS Orbulk filters.

---

### FP-05: Clean, smudge, filter-process, and local object store

**Public entry:** The clean, smudge, and filter-process plumbing subcommands as configured by install (FP-02) and attributes (FP-04); Git add/checkout as the user-visible trigger.

**Normal behavior:**

- **Clean:** Git supplies file bytes on standard input. For non-empty content that is not already a pointer document, VCS Orbulk computes the SHA-256 digest of those bytes, stores the object in the local object store when absent under the repository’s LFS objects directory using the content-addressed nested path derived from the object id (first two hex digits, next two hex digits, then the full object id), and writes a canonical pointer to standard output; an already-pointer input is written through without hashing or storing a nested object. Clean does not upload to a remote.
- **Smudge:** Git supplies blob bytes on standard input. If the content is recognized as a pointer, VCS Orbulk loads the object from the local store or downloads it from the endpoint, then writes raw object bytes to standard output. Non-pointer content is copied through unchanged.
- **Filter-process:** Speaks Git’s long-running filter protocol and services clean and smudge requests with the same semantics; this is the preferred path when modern Git is configured to use it.
- Smudge and filter-process honor include/exclude path settings (configuration or `.lfsconfig`): when include is set, only matching paths are smudged to real content; when exclude is set, matching paths are left as pointers. Skip modes (command flag or skip-smudge environment / install option) pass pointers through without downloading.
- Local object store root defaults under the Git directory’s `lfs` namespace. A configured storage location replaces that default store root — the parent of the LFS objects directory — rather than replacing the objects directory itself. The LFS objects directory remains a child of the relocated root, so cleaned objects still appear under that root using the same objects-directory-plus-shard layout as the default (objects directory, then first two hex digits of the object id, next two hex digits, then the full object id) and are not written at the default Git-directory objects path. Objects are content-addressed and shared across commits that reference the same oid.

**Boundary / error behavior:**

- If download fails during smudge, the default is to fail the filter operation; configuration or environment may instead allow checkout to succeed while leaving pointer text in the working tree (explicit skip-download-errors behavior).
- Modified working-tree files are never overwritten by checkout-style smudging of placeholders (see also FP-08).
- Missing local object without a reachable endpoint causes smudge failure unless skip/smudge-disable settings apply.

**Verifiable oracle:**

- Success: adding a tracked large file stores an object under the sharded local path and stages a pointer blob in Git; checking out that commit restores identical file bytes when the object is present or downloadable; skip-smudge leaves pointer text in the working tree; when storage is relocated to a configured directory, a cleaned object appears under that relocated store root with the same objects-directory-plus-shard layout as the default and does not appear at the default Git-directory objects path.
- Failure / absence: `git add` stores full large blobs in Git; working tree never materializes real content from pointers; object store directory never appears; a relocated storage location still receives objects at the default Git-directory objects path, or receives the shard directly under the configured path without the objects-directory child.

---

### FP-06: Endpoint discovery and authentication

**Public entry:** Implicit behavior of any transfer or lock command; visible via `git orbulk env` (FP-01); configuration keys that override discovery.

**Normal behavior:**

- By default the client derives the VCS Orbulk endpoint from the Git remote URL by appending the conventional `.git/info/lfs` suffix (whether or not the remote URL already ended in `.git`), including translating SSH-style Git remotes into the corresponding HTTPS endpoint host/path form for HTTP API use.
- Users may override the endpoint with repository or global LFS URL settings, per-remote LFS URL settings, and separate push URL overrides when upload must hit a different host than download. After a repository or global LFS URL override, the environment report’s dedicated indication for a remote (FP-01) must name that override rather than the URL derived from the Git remote. An echo of the override among related environment facts while the dedicated indication still names the derived URL does not count as replacement. A per-remote LFS URL override changes that remote’s dedicated indication, not a sibling remote’s; a sibling remote without the same override still shows its own discovery result on its own dedicated indication. An echo among related facts, or the sibling remaining unchanged, does not prove this remote’s selected endpoint changed. A repository or global LFS URL override replaces derivation on every remote’s dedicated indication even when that remote also has a per-remote LFS URL; the per-remote override is the selected endpoint only in the absence of that repository or global override. A separate push URL override does not replace that dedicated indication — the indication remains the download URL that would be used — and is observed on the transfer path as upload contacting a different endpoint than download. This obligation does not fix the indication’s label, wording, or layout.
- Default remote selection follows: the current branch’s remote if set, otherwise a configured LFS default remote name, otherwise the single existing remote if there is only one, otherwise `origin`, with analogous rules for push defaults.
- For SSH Git remotes on the hybrid HTTPS API path (not the pure SSH transfer path of FP-17), the client runs the remote helper command **git-orbulk-authenticate** over SSH with the repository path and operation (`download` or `upload`). On success, the helper’s JSON supplies authorization headers and may supply an alternate endpoint URL and expiry hints. Those headers are attached to subsequent API requests; when that JSON names an alternate endpoint URL, subsequent API requests use that URL rather than the derived HTTPS form.
- Otherwise the client uses Git’s credential helpers and HTTP Basic authentication material, and may use credentials embedded in URLs when present (discouraged but supported). Kerberos is supported where the environment provides it. NTLM is not supported on current major versions (VCS Orbulk 3.0 and later).

**Boundary / error behavior:**

- Failed SSH authentication helper invocation surfaces the helper’s error output and fails the operation.
- Invalid or missing credentials cause API requests to fail with a non-zero exit rather than silently skipping transfers.
- Pure configuration mistakes (empty endpoint where one cannot be derived) fail before pretending a transfer succeeded.

**Verifiable oracle:**

- Success: the environment report’s dedicated indication for a remote names the derived or overridden URL that would be used — a repository or global LFS URL override replaces remote derivation on that indication, including on a remote that also has a per-remote LFS URL, and a per-remote LFS URL override (with no repository or global override) changes only that remote’s indication while a sibling without the same override keeps its own discovery result on its own indication; a push URL override leaves that dedicated download indication unchanged while upload contacts a different endpoint than download; an SSH remote on the hybrid path that offers git-orbulk-authenticate can authorize batch requests without a manual credential prompt when the helper succeeds, and when the helper names an alternate endpoint URL those requests use that URL; HTTPS remotes use credential helper results.
- Failure / absence: always requires hard-coded URLs with no derivation; a repository or global override is only echoed among related facts while the dedicated indication still names the derived URL, or is ignored on a remote that also has a per-remote LFS URL; a per-remote override does not change that remote’s dedicated indication; a push URL override is treated as replacing the dedicated download indication, or upload and download still contact the same endpoint; SSH remotes on the hybrid path never attempt git-orbulk-authenticate; transfers “succeed” with no credential path when the server requires auth.

---

### FP-07: Batch negotiation and basic object transfer

**Public entry:** Used internally by fetch, push, pull, clone, smudge, and related commands; exercised whenever objects move to or from an HTTP(S) endpoint.

**Normal behavior:**

- The client posts a batch request to the endpoint’s objects batch path. Each batch request must send an Accept header that names the protocol’s designated VCS Orbulk JSON media type, and must send a Content-Type header that carries that same media type; servers must accept an optional charset parameter on Content-Type. Batch responses are expected to use that media type as well.
- The request names the operation (`download` or `upload`), optionally advertises supported transfer adapters (servers must assume **basic** when the list is omitted), optionally includes the Git ref name for authorization schemes that need it, lists objects by oid and size (size at least zero), and may name the hash algorithm (default SHA-256).
- The response selects a transfer adapter and, per object, either indicates the object already exists on the server, returns transfer actions with href/header/expiry metadata, or returns per-object errors.
- **Basic download:** HTTP GET of the action href with supplied headers; response body is raw object bytes. Partial or resumable downloads may reuse HTTP range requests when applicable.
- **Basic upload:** HTTP PUT of raw bytes to the action href with supplied headers. A verify action, when present, is performed after upload as the protocol requires. Upload content typing may be auto-detected from the object or forced to a generic binary stream via configuration.
- When the tus transfer path is explicitly enabled in configuration and basic-transfers-only is not enabled, the client must include that advanced adapter in the batch request’s advertised transfer list (in addition to basic), not merely leave the list basic-only or omitted.
- When basic-transfers-only is then enabled while that same advanced path remains configured, the batch request’s advertised transfer list must change so advanced adapter names are absent and only basic remains (or the list is omitted, which peers treat as basic). The discriminating observation is that on/off change of the advertised list under those two configurations — not an environment echo of the setting alone, and not a successful PUT that any always-basic client can produce.
- Concurrent transfers are bounded by configuration (default parallelism is greater than one). Progress may be shown on a terminal or forced via configuration/environment, and may be mirrored to a progress file when requested.

**Boundary / error behavior:**

- Per-object batch errors fail that object’s transfer and cause the overall command to fail when any required object cannot be transferred.
- Expired action URLs result in visible failure (and may trigger re-auth / retry according to client policy) rather than treating missing content as success.
- Servers that only understand basic transfer remain interoperable when the client advertises basic (or omits the transfers list so the server assumes basic): a basic-only server still completes the upload PUT for a conforming client that stays on basic.

**Verifiable oracle:**

- Success: against a conforming endpoint, downloading an object not present locally results in a batch download request that carries both Accept and Content-Type naming the designated VCS Orbulk JSON media type, and a GET that populates the local store with bytes whose digest matches the oid; uploading a new object results in a batch upload request with the same Accept and Content-Type obligations and a PUT of those bytes; a second upload of the same oid can be omitted when the server reports the object already exists.
- Success (adapter advertisement contrast): with the tus path explicitly enabled and basic-transfers-only off, the batch upload request’s advertised transfer list includes that advanced adapter; enabling basic-transfers-only under the same advanced configuration changes the advertisement so advanced names are gone and only basic remains (or the list is omitted). A basic-only server remains interoperable for the basic advertisement arm.
- Failure / absence: fetch/push never perform HTTP batch calls; object bytes are fabricated locally without server round-trips; digests on disk do not match oids; enabling basic-transfers-only never changes an advanced-enabled advertisement (always-basic clients that ignore the setting are distinguishable by lacking the on/off contrast).

---

### FP-08: Fetch, pull, checkout, and clone

**Public entry:** The `git orbulk fetch`, `git orbulk pull`, `git orbulk checkout`, and `git orbulk clone` porcelain subcommands.

**Normal behavior:**

- **Fetch** downloads VCS Orbulk objects for the given remote and refs into the local object store without updating the working tree. Defaults pick the usual remote and refs when omitted. It supports include/exclude path filters (CLI overrides configuration), fetching recent refs/commits per recentness settings, fetching all objects reachable from the given refs, or from all refs when none are given (backup/migration mode that ignores configured include/exclude), reading refs from standard input, pruning after fetch, refetching objects already present, dry-run, and JSON reporting of transfer plans.
- **Checkout** materializes working-tree files from local objects for the current ref when the working tree has missing files or pointer placeholders, without downloading. Glob arguments restrict which paths are updated. Modified working-tree files are never overwritten. In merge conflicts, checkout can extract base/ours/theirs stages of an LFS path into a separate output file. On sufficiently new Git, attribute matching follows index/worktree attribute rules described in the product’s checkout documentation (including sparse/partial clone caveats).
- **Pull** is the composition of fetch for the current ref plus checkout into the working tree, with the same include/exclude options.
- **Clone** wraps Git clone while deferring LFS downloads during the clone, then performs an efficient pull-style batch download, and installs repository hooks unless asked to skip that installation. Skipping withholds that install obligation and is not an absence or presence observation of those four hooks. Include/exclude options apply to the download phase.

**Boundary / error behavior:**

- Fetch/pull fail when the remote endpoint is unreachable or authentication fails (FP-06/FP-07).
- Checkout in a bare repository has no effect.
- All-mode fetch cannot be combined with recent or include/exclude flags.
- When the LFS download phase of clone fails, the caller must be able to tell that outcome apart from a clone whose download completed: the command ends in a non-success outcome distinguishable from success, while a usable Git repository produced by the underlying clone may still remain.
- When repository hook installation during clone cannot succeed and was not intentionally skipped, the caller must be able to tell that outcome apart from a clone that completed hook installation or intentionally skipped it: the command ends in a non-success outcome distinguishable from success, while the Git repository produced by the underlying clone may still remain.

**Verifiable oracle:**

- Success: fetch populates `.git/lfs/objects` for pointers in the requested ref without changing working-tree bytes; checkout then replaces pointer placeholders with real content; pull does both; clone of a VCS Orbulk-enabled repo yields real content for tracked files after its download phase (unless skip-smudge style settings apply) and, when repository-hook installation was not skipped, leaves the repository hooks installed. Skipping that installation is not an absence or presence observation of those hooks.
- Failure / absence: pull leaves only pointers with no objects fetched; clone smudges file-by-file only and never batch-fetches; checkout overwrites dirty user edits; a clone whose LFS download phase fails ends indistinguishably from success; a clone whose hook installation cannot succeed (and was not skipped) ends indistinguishably from success.

---

### FP-09: Push and pre-push hook

**Public entry:** The `git orbulk push` porcelain subcommand; the `git orbulk pre-push` plumbing subcommand installed as a Git hook (FP-02); ordinary `git push` as the user-visible trigger.

**Normal behavior:**

- **Push** uploads locally referenced LFS objects for the given remote and refs (or for object ids when object-id mode is selected). By default it considers only objects not already referenced by the local clone of that remote; **push-all** considers every object reachable from the given refs, or from all local refs when none are given. It also supports dry-run and reading refs or oids from standard input.
- **Pre-push** reads Git’s pre-push stdin lines (local ref, local sha, remote ref, remote sha). For non-delete updates, it uploads LFS objects required by the commits being pushed. Branch deletion pushes do not upload objects.
- **Dry-run** (push and pre-push): when pending objects would be uploaded, the command prints a caller-visible plan that identifies those objects and does not transfer their bytes. A report that names a pending object by any designation of that same object is distinguishable from generic non-empty chatter that names none of them, and from a live upload of those same objects. The designation form, the wording, and the layout of the plan are not fixed.
- An environment skip-push setting makes the pre-push hook do nothing, allowing Git push to proceed without LFS uploads when explicitly requested.
- A successful push that uploaded the objects required for the pushed refs leaves those objects available at the endpoint so a subsequent clone or pull of those refs can restore the corresponding tracked files as working-tree bytes (materialization itself is specified under FP-08; the cross-cutting end-to-end happy path is the same install → track → commit → push → fresh clone/pull sequence).

**Boundary / error behavior:**

- If required uploads fail, pre-push fails and Git aborts the push.
- When lock verification is enabled (FP-10), pushes that would update paths locked by others are rejected.
- Push to a remote without a workable endpoint fails visibly.

**Verifiable oracle:**

- Success: after committing a new tracked large file, `git push` triggers VCS Orbulk upload before Git refs update on the server; the endpoint receives the object; a second push of the same commit does not re-upload unnecessarily; a dry-run with pending objects prints a caller-visible plan that identifies those objects and does not transfer them, so that plan is distinguishable from generic non-empty chatter that names none of them and from a live upload of those same objects (designation form, wording, and layout are not fixed); after that successful push, a fresh clone or pull of the pushed ref restores those tracked files as working-tree bytes matching what was pushed (unless skip-smudge style settings apply).
- Failure / absence: Git push succeeds while the endpoint never receives objects; pre-push ignores stdin commit ranges; skip-push cannot be distinguished because uploads never happened anyway; a client that only uploaded fiction or left only pointers so a subsequent clone/pull cannot restore the pushed working-tree bytes; a dry-run with pending objects either still transfers those objects or emits only generic chatter that names none of them.

---

### FP-10: File locking

**Public entry:** The `git orbulk lock`, `git orbulk unlock`, and `git orbulk locks` porcelain subcommands; the `git orbulk post-checkout`, `git orbulk post-commit`, and `git orbulk post-merge` plumbing commands installed as Git hooks (FP-02); lock verification during push/pre-push; lockable attributes from track (FP-04).

**Normal behavior:**

- **Lock** creates a server-side lock for a repository-relative path. The path need not already exist in the working tree (locking a locally missing path still requests creation of a server-side lock). JSON output mode is available on success.
- **Unlock** removes a lock by path or by lock id (exactly one of those two selectors). A force mode asks the server to remove the lock even when another user owns it, when the server permits that, and also skips the local clean-status check described below. Optional remote selection chooses which endpoint’s locks are targeted.
- **Locks** lists locks from the server with filters by id or path, local-only cache listing, cached listing from the last server fetch, verification marking of locks owned by the current user, and JSON output.
- Lockable-tracked files are set read-only in the working tree when not locked by the user (controllable via configuration / environment), and become writable when locked.
- After checkout, commit, or merge, the corresponding post-* hooks re-apply read-only permissions on lockable paths that the local user does not currently hold a lock for. Post-commit focuses on paths changed in HEAD (especially newly added lockable files). Post-merge examines the broader working-copy set of lockable paths. Post-checkout examines that broader set on a file checkout or on an initial checkout; on an ordinary branch, tag, or commit checkout it focuses on paths that changed between the previous and new revisions.
- Push paths consult the locking API’s verify capability when locks-verify is enabled for the endpoint, refusing pushes that violate foreign locks. Configuration can force verification on, off, or prompt on unknown server support.

**Boundary / error behavior:**

- Locking a path that resolves to a directory in the working copy fails.
- Creating a lock when one already exists for that path fails with a conflict outcome from the server.
- Unlock by path without force fails when that path has uncommitted working-tree changes, or when the path cannot be resolved for a status check (including a missing path that makes that check fail). Unlock by lock id does not apply that local check. Force skips that local check and still requests the server-side unlock.
- Unlock invoked with both a path and a lock id, or with neither, is invalid.
- Lock commands fail when the endpoint lacks locking support or authentication fails.
- Local-only / cached listing modes must not claim live server truth when they intentionally skip or reuse network results.
- Invoking a post-* plumbing command outside the Git hook context may warn that the user should run update to install hooks.

**Verifiable oracle:**

- Success: lock then locks-list shows the path (including when the locked path is absent from the working tree); unlock clears it; a second user (or simulated foreign lock) causes push verification to fail when verification is on; after tracking a lockable pattern and committing, an unlocked lockable file is read-only in the working tree and becomes writable after lock; locking a directory path fails observably; unlock by path without force of a dirty path fails while the same unlock with force proceeds to the server request; unlock by lock id of a dirty path still proceeds to the server request without force.
- Failure / absence: lock only writes local markers with no server round-trip; push never checks locks; lockable files remain writable always; post-* hooks are never installed; unlock by path without force of a dirty path always succeeds, or force never reaches the server.

---

### FP-11: Status and ls-files inspection

**Public entry:** The `git orbulk status` and `git orbulk ls-files` porcelain subcommands.

**Normal behavior:**

- **Status** (non-bare repositories only) lists paths that are not yet pushed (VCS Orbulk objects reachable from the current ref but not from the current branch’s remote-tracking ref), differ between index and HEAD, or differ between working tree and index—mirroring the intuition of what would be uploaded, committed, or staged. The unpushed listing names only VCS Orbulk-related paths. Of the index/HEAD and working-tree/index listings, the default human listing and porcelain name ordinary Git paths that differ in those slots as well as VCS Orbulk-related ones; JSON names only VCS Orbulk-related paths. Porcelain and JSON scripting modes cover the index/HEAD and working-tree/index listings only, not the unpushed set.
- **Ls-files** lists VCS Orbulk files at a ref (when no ref is given: the current branch including the index, which takes precedence for a path also in the tree; an explicit ref is that ref’s tree and ignores the index), or the VCS Orbulk files changed between two refs (deletions omitted in the two-ref form). Options include long oid, size, debug, entire-history listing, include deleted history objects, include/exclude path filters, name-only, and JSON.
- On the default named-path listing line, each entry presents a dedicated checkout indication of whether the working-tree file is the full object or only a pointer, distinct from the path, the object id, and from a dump of working-tree size or file contents. That indication must differ between those two checkout states and be stable across two observations of the same checkout state. Holding the working-tree file fixed and varying only whether the object bytes exist in the local store is not this default-line duty: both store-present and store-missing then share one checkout indication. This obligation does not fix mark characters, field names, or layout.
- JSON listing separately indicates local-store presence on the named entry. When the working-tree file is a pointer, store-present versus store-missing remain distinct on that named entry. When the working-tree file is the full object, store-present versus store-missing remain distinct on that named entry.

**Boundary / error behavior:**

- Status in a bare repository fails.
- Ls-files with invalid refs fails; entire-history listing cannot be combined with an explicit ref; include-deleted listing cannot be combined with the two-ref form.
- When both machine-readable JSON and a mutually overriding human format are requested: status prefers the porcelain human format over JSON; ls-files prefers debug over JSON, and when JSON is selected the long/size/name-only options have no effect.

**Verifiable oracle:**

- Success: after committing a tracked file that is not on the current branch’s remote-tracking ref, the default human status lists it among unpushed LFS content; after an ordinary Git path differs in index/HEAD or working-tree/index, the default human listing and porcelain name that path while JSON does not; on the default named-path listing line, the dedicated checkout indication differs when the working-tree file is the full object versus only a pointer, is stable across two observations of the same checkout state, and is distinct from the path, the object id, and a dump of working-tree size or file contents; holding the working-tree file fixed and varying only local-store presence is not this default-line duty; JSON listing indicates local-store presence on the named entry when the working-tree file is a pointer (store-present versus store-missing distinct on that entry), and store-present versus store-missing remain distinct on that named entry when the working-tree file is the full object.
- Failure / absence: status always empty; default human or porcelain index/HEAD or working-tree/index listings omit ordinary Git paths that differ in those slots, or JSON names those ordinary Git paths; the default named-path listing cannot tell a working-tree full-object checkout from a pointer-only checkout, or that distinction is only a dump of working-tree size or file contents; JSON listing does not indicate local-store presence on the named entry when the working-tree file is a pointer.

---

### FP-12: Local object pruning

**Public entry:** The `git orbulk prune` porcelain subcommand (also invocable after fetch via fetch’s prune option).

**Normal behavior:**

- Prune deletes local objects that are not retained by: the current checkout, stashes, recent branches/commits per recentness configuration, unpushed commits, or other worktree checkouts. Objects only reachable from orphaned commits are deleted. The reflog is not a retention root.
- Paths matching fetch-exclude rules may be pruned more aggressively unless retained by stash or unpushed commits.
- Options include dry-run, force (prune even objects needed by current checkouts, implying recent), recent, verify-remote before delete, verify unreachable objects on the remote, when-unverified halt or continue after remote verification fails, and verbose reporting.

**Boundary / error behavior:**

- Prune must not delete the only copy of an unpushed object.
- Users sharing one custom storage directory across multiple repositories are warned (via documentation and config notes) not to prune unsafely; prune still applies retention rules inside the invoked repository context.
- When remote verification is enabled and at least one prune candidate fails verification on the remote: under when-unverified halt, every prune candidate from that run remains in the local store (neither the unverified object nor other candidates from the same run are deleted); under when-unverified continue, only objects that verified successfully on the remote are deleted and objects that failed verification remain in the local store. Halt versus continue is distinguished by those retention-versus-deletion outcomes on the local store.

**Verifiable oracle:**

- Success: an object only referenced by an old, pushed, non-recent commit disappears from the local store after prune while objects for HEAD remain; dry-run reports without deleting; with verify-remote, when-unverified halt leaves all prune candidates from a run that had a remote verification failure in the local store, while when-unverified continue deletes only successfully verified prune candidates and leaves failed ones in the local store.
- Failure / absence: prune deletes unpushed objects; prune never deletes anything even when retention rules say it should; force still leaves unreachable stale data forever without a way to reclaim space; under halt, a run with remote verification failures still deletes some prune candidates from that run; under continue, objects that failed remote verification are deleted.

---

### FP-13: Object and pointer integrity check

**Public entry:** The `git orbulk fsck` porcelain subcommand.

**Normal behavior:**

- Fsck checks VCS Orbulk files for consistency for HEAD by default (and, for object checks, the index in that omitted-revision default), or for a single committish, or for a two-dot range form only. Object checks and pointer checks both run by default and may be requested independently.
- Object checks verify each object’s hash matches its oid and that the file exists on disk.
- Pointer checks verify pointers are canonical and that files that should be stored as VCS Orbulk objects are actually stored that way.
- Hash-mismatched local object files are moved aside into the repository’s LFS `bad` quarantine directory unless dry-run is set; pointer defects are reported and are not moved into that quarantine.
- Fetch-exclude path patterns skip object checks for matching paths; they do not skip pointer checks.

**Boundary / error behavior:**

- Hash mismatches, missing objects, and pointer defects cause non-zero exit.
- A single revision argument which cannot be resolved as a committish or as both ends of a two-dot range causes a non-zero exit and does not complete a successful integrity check of the default revision. A three-dot range token is such an unresolvable single-argument form.
- Dry-run reports problems without moving files.

**Verifiable oracle:**

- Success: a bit-flipped local object is detected and (without dry-run) moved to the bad quarantine; a non-canonical pointer is reported under pointer checking and is not quarantined; an omitted-revision default object check covers a staged index path that an explicit HEAD check does not; fetch-exclude matching paths are omitted from object checks while still subject to pointer checks; requesting object checks alone does not treat a pointer-only defect as a finding; requesting pointer checks alone does not treat object corruption as a finding; a clean repository with omitted HEAD, a single resolvable committish, or a two-dot range exits successfully.
- Failure / absence: corruption is ignored; fsck always exits zero; quarantine never receives bad objects; pointer defects are quarantined as if they were local object files; an omitted-revision default object check ignores a staged index-only path; fetch-exclude matching paths are also skipped for pointer checks; requesting one check kind still treats the other kind’s defects as findings; a single revision argument that cannot be resolved as a committish or as both ends of a two-dot range, including a three-dot range token, completes a successful integrity check of the default revision.

---

### FP-14: History migration

**Public entry:** The `git orbulk migrate` porcelain subcommand with modes info, import, and export.

**Normal behavior:**

- **Info** summarizes counts and sizes by file type for the selected ref set to help users decide what to migrate. Each file-type summary presents a count figure and a size figure as separately identifiable fields on that type's report, so a caller can tell which figure is the count and which is the size without relying on a particular punctuation, column order, or unit spelling. When only the blob payload bytes for that type change while the number of matching files stays the same, the size figure must change and the count figure must not. Pointer objects are handled by exactly one of three pointer modes: **follow** (default: report referenced object sizes separately), **ignore** (omit pointers), or **no-follow** (treat pointer documents as ordinary files).
- **Import** rewrites local history so matching Git blobs become VCS Orbulk pointers, stores objects locally, and updates `.gitattributes` on rewritten commits as if track had been run for those patterns (unless fixup mode only converts files that attributes already say should be VCS Orbulk but are not yet). A no-rewrite import mode creates a new commit that migrates matching objects into VCS Orbulk without rewriting prior published history; that mode uses its own argument list and ignores the ordinary migrate rewrite options.
- **Export** rewrites local history in the reverse direction: matching VCS Orbulk pointers become ordinary Git blobs again, fetching missing objects from a remote when needed (default remote `origin`), and inserts excluded-pattern attribute entries (FP-04 disabling/unsetting filter forms) for the exported patterns rather than removing tracking lines or deleting attribute files.
- By default migrate considers the current branch and commits not present on remotes; options expand to chosen refs, exclude refs, or everything. After rewrite, only local refs are updated even when everything was read—remote-tracking refs stay aligned with remotes until the user force-pushes.
- Migrate refuses to proceed when `.gitattributes` is a symbolic link. Attribute files it writes use non-executable permissions.

**Boundary / error behavior:**

- Export requires at least one include pathspec.
- Import/export are destructive history rewrites (except no-rewrite import, which adds a new commit instead of rewriting prior history); they do not update remotes automatically.
- Uncommitted work should be committed or stashed first; migrate fails or risks data loss if the working tree is unsafe for rewrite—users are expected to validate before force-push.
- By default, when migrate selects the unpushed commit set using remote refs, it refreshes those remote refs over the network first. An unreachable configured remote makes that default migrate path fail observably before any history rewrite completes.
- With skip-fetch, the same unreachable remote still allows import to succeed when objects are already local: matching blobs become pointers and objects are stored locally. The discriminating observation is success with skip-fetch versus failure of the identical import without skip-fetch under that unreachable remote—not a particular fetch error string. Export or import may still need a reachable remote when objects themselves are missing locally.

**Verifiable oracle:**

- Success: import with an include glob rewrites commits so those paths are pointers, objects exist locally, and those rewritten commits carry tracking lines for the pattern; info names extensions and presents separately identifiable count and size figures per type such that a same-type size-only payload change moves the size figure while the count figure stays the same; export restores blob contents for included paths, those rewritten commits carry excluded-pattern attribute entries for the exported patterns, and history no longer depends on those pointers; with skip-fetch, import succeeds under an unreachable remote when objects are already local.
- Failure / absence: migrate only changes working tree without rewriting commits; attributes never updated; import writes tracking lines only at a first-appearance commit while leaving other rewritten commits untouched; export leaves pointers in history or updates attributes only by removing tracking lines; under an unreachable remote, the default (non-skip-fetch) path that refreshes remote refs for unpushed-commit selection fails observably while the skip-fetch arm of the same import succeeds.

---

### FP-15: Configuration surface and repository `.lfsconfig`

**Public entry:** Git configuration keys under the `lfs` namespace, per-remote overrides, the environment variables that skip smudge, skip push, skip download errors, force progress, or set lockable read-only behavior, and an optional `.lfsconfig` file at the repository root.

**Normal behavior:**

- VCS Orbulk reads all files Git’s config machinery supports. A restricted subset of settings may also live in `.lfsconfig` at the repo root (same format as Git config files) so teams can ship endpoint and access defaults. Git config overrides `.lfsconfig`. If `.lfsconfig` is missing from the work tree, VCS Orbulk looks in the index, then HEAD (bare repositories: HEAD only).
- The finite set of keys accepted in `.lfsconfig` is: the LFS URL, the LFS push URL, per-remote LFS URLs, fetch include, fetch exclude, skip-download-errors, allow-incomplete-push, locks-verify, URL-scoped access, and the Git protocol setting used for LFS. Other keys in that file are ignored for security.
- Users can configure at least: endpoint and push endpoint URLs; default remotes; dial/TLS/activity/keepalive timeouts; concurrent transfers; fetch include/exclude; transfer and locking behavior; lock verification; pure SSH transfer mode (`negotiate`, `always`, or `never`); storage location; skip download errors; progress forcing; lockable read-only behavior; prune recentness and verify defaults; optional tus uploads; basic-transfers-only; and standalone/custom transfer agent bindings (FP-16).
- Environment variables can skip smudge, skip push, and skip download errors, matching the documented boolean truthy/falsey conventions. On/off contrasts against the same transfer paths: skip-smudge leaves pointer text in the working tree on checkout/filter instead of materializing; skip-push makes the pre-push path perform no LFS uploads; skip-download-errors lets a checkout/smudge that cannot download leave pointers rather than failing the whole operation.
- Environment or Git configuration can force progress, matching the documented boolean truthy/falsey conventions. When a transferring command runs with standard output not a terminal, enabling progress forcing must produce caller-visible in-progress transfer reporting that is absent when the same command runs with progress forcing off. A completion or summary line that appears on both arms is not that contrast. The discriminating observation is that on/off change of in-progress reporting — not whole-stream byte inequality, not mere nonempty output, and not a particular meter punctuation such as carriage-return rewrites or percent signs. This obligation does not fix the reporting channel or the exact progress text.
- Environment or Git configuration can enable or disable lockable read-only behavior (default enabled). Construct the contrast with FP-04 lockable marking and FP-10 permission outcomes: after tracking a pattern as lockable and committing a matching file that the local user does not hold a lock for, with lockable read-only enabled a checkout, commit, or merge that runs the corresponding post-* permission path leaves that unlocked lockable working-tree path read-only; with the same path state but lockable read-only disabled (falsey environment or configuration), the same Git operation leaves that unlocked lockable path writable.

**Boundary / error behavior:**

- A boolean value that is not a documented truthy token is falsey under those conventions: skip and progress-forcing stay off, and lockable read-only is disabled rather than left at its default-enabled state.
- Unknown keys in `.lfsconfig` do not crash the client; they are ignored for unrecognized names.

**Verifiable oracle:**

- Success: setting an explicit LFS URL changes the environment report’s dedicated endpoint indication (FP-01/FP-06) and causes transfers to target that URL; `.lfsconfig` endpoint applies until Git config overrides it; skip-smudge, skip-push, and skip-download-errors environment flags produce the on/off contrasts above on the same checkout/filter and pre-push paths; when a transferring command runs with standard output not a terminal, enabling progress forcing produces caller-visible in-progress transfer reporting that is absent with progress forcing off (a completion or summary line that appears on both arms is not that contrast); lockable read-only enabled versus disabled produces the read-only versus writable contrast on an unlocked lockable working-tree path prepared via FP-04 and observed through the FP-10 post-* permission path.
- Failure / absence: `.lfsconfig` never read; overrides ignored; environment skip flags have no effect; progress forcing on versus off cannot be told apart by in-progress transfer reporting when standard output is not a terminal; lockable read-only enabled and disabled cannot be told apart on unlocked lockable paths after the post-* permission path.

---

### FP-16: Custom transfers, standalone file URLs, and clean/smudge extensions

**Public entry:** Custom transfer configuration; the standalone-file plumbing adapter; the `git orbulk ext` subcommand; extension registration in Git config.

**Normal behavior:**

- **Custom transfer agents:** Named agents registered in config specify a process path, arguments, whether concurrent instances are allowed, and direction (download, upload, or both). During batch negotiation the client advertises these transfer names; when the server selects one, VCS Orbulk launches the process and speaks the documented JSON stdin/stdout protocol to move bytes via paths the agent understands (no file bytes on the control stream). Built-in adapter names such as basic and ssh always override a custom agent registered under the same name.
- **Standalone transfer without API:** Configuration may name a standalone agent (including the built-in standalone file adapter) so VCS Orbulk skips contacting the batch API and drives transfers directly when the endpoint URL matches.
- **Standalone file adapter:** Handles `file://` URLs / local paths as a transfer backend, speaking the standalone JSON transfer protocol. End users do not invoke it manually for routine workflows; the client selects it when appropriate. When that adapter uploads to a file:// or local-path Git remote that uses the default store location, the object appears in that destination Git directory’s LFS object store using the same objects-directory-plus-shard layout as the local store: store root under that Git directory’s lfs namespace, the objects-directory child, then the shard (first two hex digits of the object id, next two hex digits, then the full object id). It is not written only at an unrelated path beside the destination. This obligation does not name a particular configuration key and does not pin a relocated destination storage path.
- **Content extensions (experimental):** Registered extensions supply clean and smudge external commands with priority ordering. On clean, registered extensions are applied in ascending priority-number order: a smaller priority number runs before a larger one, so two transforming extensions produce one stored-object result at those numbers and swapping only those numbers produces the reverse pipeline’s stored-object result, distinguishable from each other and from applying only one of the two. Smudge reverses that clean order. The client records per-extension metadata lines on the pointer so smudge can reverse the pipeline. Extensions do not edit the pointer directly. The ext subcommand lists registered extension details. This obligation does not fix pointer metadata key spelling, append-token text, or any particular pair of numeric values beyond the smaller-before-larger contrast.

**Boundary / error behavior:**

- A selected custom agent whose process path cannot be launched fails that transfer. An unknown name selected as the standalone agent is ignored, so ordinary batch transfer still proceeds rather than inventing success without a transfer.
- Extension failures during clean/smudge fail the filter operation; buggy extensions can corrupt repositories—hence experimental status—but when registered they are still applied on clean in ascending priority-number order (a smaller number before a larger one) and on smudge in the reverse of that clean order.

Non-binding background (not graded here): content-extension registration can interact with dedup; the graded refusal when extensions are configured is owned by FP-18 (dedup’s public entry), not by this feature’s suite.

**Verifiable oracle:**

- Success: a registered custom agent is advertised in batch requests and is invoked when the server selects it; when the standalone file adapter uploads to a file:// or local-path Git remote that uses the default store location, that destination Git directory’s LFS object store receives the object under the same objects-directory-plus-shard layout as the local store, without an HTTP batch exchange; on clean, two transforming extensions at two different priority numbers produce one stored-object result and swapping only those numbers produces the reverse pipeline’s stored-object result, distinguishable from each other and from applying only one of the two, while smudge reverses that clean order and restores working-tree bytes, preserving extension metadata on the pointer; ext lists the registration.
- Failure / absence: custom transfer config never launches a process; a file:// upload never appears in that destination Git directory’s default LFS object store; extensions are ignored while still claiming success, or swapping only priority numbers leaves the stored-object result indistinguishable from the original pair (including an inverted-order client).

---

### FP-17: Pure SSH transfer protocol

**Public entry:** Automatic when talking to SSH remotes that implement the pure SSH VCS Orbulk transfer service; controlled by the ssh-transfer configuration triad negotiate/always/never.

**Normal behavior:**

- The client attempts to run **git-orbulk-transfer** over SSH with the repository path and operation (`download` or `upload`). On success it speaks a pkt-line capability-oriented protocol: the server advertises capabilities including protocol version 1; the client selects version 1; further batch-like download/upload and optional locking commands proceed on the SSH channel without requiring HTTPS for the object bytes. After object bytes have been sent on the SSH upload channel, the client must still complete a post-upload verification round-trip on that same channel. Treating a successful byte put as finishing the upload is not enough: a conforming peer can still reject the object on that verification step after already storing the bytes. This obligation does not pin the verification command’s token, packet wording, or a numeric status code.
- Default mode is negotiate: try pure SSH first, then fall back to the hybrid git-orbulk-authenticate-plus-HTTPS approach (FP-06/FP-07). Always and never force only one family.

Non-binding background (not graded): some OpenSSH-family setups can reuse a shared SSH control connection for successive pure-SSH channels under configuration and platform defaults; that optimization is not required for correctness of pure SSH transfer.

**Boundary / error behavior:**

- If the git-orbulk-transfer session cannot be established in negotiate mode, the client falls back to the hybrid protocol rather than immediately aborting, unless configuration forbids fallback.
- In always mode, hybrid HTTPS transfer is not used; failure of pure SSH fails the operation.
- Server error packets surface as user-visible transfer failures (the transfer does not succeed; the failure is distinguishable from a successful download or upload). A server error packet on the post-upload verification round-trip fails the whole upload even though the peer already stored the bytes; that outcome is distinguishable from treating a successful byte put as a completed upload.

**Verifiable oracle:**

- Success: against a peer that implements git-orbulk-transfer, objects upload and download over the SSH protocol path; after object bytes have been sent on the SSH upload channel the client still completes a post-upload verification round-trip on that same channel, so a successful upload is distinguishable from a put-only completion that never verified; configuration can force never so only hybrid is used; negotiate falls back when the git-orbulk-transfer session cannot be established; a server error packet — including on that verification step after the object bytes were already stored — yields a failed transfer rather than a successful one.
- Failure / absence: SSH remotes always require HTTPS object transfer even when pure SSH would work; always mode still uses HTTPS; negotiate does not attempt git-orbulk-transfer; server error packets are treated as success; a successful byte put is treated as a completed upload even when a verification-step error after the peer stored the bytes would have rejected the object.

---

### FP-18: Logs, completion, dedup, and merge driver

**Public entry:** The `git orbulk logs`, `git orbulk completion`, `git orbulk dedup`, and `git orbulk merge-driver` subcommands; Git merge attribute integration when a user configures a merge driver that invokes the merge-driver plumbing command.

**Normal behavior:**

- **Logs:** Crash and unexpected-error details are written under the repository’s LFS logs directory. The logs command’s finite sub-entries are: list stored logs (default), show a named log or the most recent (`last`), clear stored logs, and intentionally trigger a diagnostic exception for testing.
- **Completion:** Emits a non-empty tab-completion script for each of a fixed set of shells—**bash**, **fish**, and **zsh**. When that script is loaded and exercised in the corresponding shell, completing the standalone binary yields VCS Orbulk porcelain subcommand names as completion candidates (and flag completion for those porcelain commands; not general Git remote/branch completion). The bash emission, when similarly loaded and exercised with Git’s own completion active, also yields those porcelain subcommand candidates for the multi-word git-invoked entry. The discriminating observation is the candidate set obtained through that shell’s use of the emitted script—not a direct call to a hidden completion interface that bypasses the script, and not a requirement that porcelain names appear as literal substrings in the script text.
- **Dedup:** On filesystems that support copy-on-write cloning, re-links working-tree LFS files as COW clones of the local store objects to save space. A test mode only checks filesystem support (and the extensions gate below). Dedup fails when unsupported or when content extensions are configured.
- **Merge driver:** Intended to be invoked by Git, not by end users by hand. Track records the ordinary `lfs` merge attribute, which leaves Git’s default merge of pointer text in effect and does **not** by itself select this driver. A user who knows some tracked files are text must separately set a merge attribute (the documentation illustrates this with a name such as `lfs-text`) and point that attribute at this plumbing command. When so invoked, the driver materializes ancestor/current/other stages and merges text-oriented LFS content via Git’s merge-file machinery or a configured external program. On a successful merge it writes a pointer document for the three-way-merged object bytes to the designated output, and — when that object is not already present — stores those merged bytes in the local object store under the same content-addressed nested path layout used by clean (first two hex digits of the object id, next two hex digits, then the full object id).

**Boundary / error behavior:**

- Dedup exits non-zero on unsupported platforms/filesystems rather than pretending to save space.
- When copy-on-write cloning is supported and content extensions are configured (registration described under FP-16), both ordinary dedup and its filesystem-support test mode refuse and exit non-zero rather than reporting support success or performing COW re-links, because working-tree bytes may not match stored object bytes. Construct the contrast on a COW-capable substrate: same repository and filesystem, with versus without extension registration—extensions-configured must not produce the support-success outcome that no-extensions produces.
- Completion for an unknown shell name fails with a non-zero exit.
- Merge driver does not claim to handle arbitrary binary merges or all rename/copy cases Git itself cannot express in this hook shape.
- A successful merge-driver invocation that writes only merged text, or only a pointer document with no corresponding bytes under the local content-addressed object layout, does not satisfy the merge-driver duty: later smudge of that pointer would have nothing local to restore.
- The diagnostic-exception logs entry deliberately fails; clear removes stored logs so subsequent list is empty.

**Verifiable oracle:**

- Success: after a controlled failure path, logs shows a new log file; completion for bash, fish, and zsh each succeeds with a non-empty script that, when loaded and exercised in that shell, yields porcelain subcommand candidates for the standalone binary, and the bash script likewise yields those candidates for the multi-word git-invoked entry once Git’s own completion is active (candidates observed through the shell’s use of the script—not via a bypass of the script, and not by requiring porcelain names as literal script substrings); dedup test mode reflects real COW support; on a COW-capable substrate with no content extensions configured, dedup test mode reports support success, while with content extensions configured the same dedup/test invocation refuses with a non-zero exit distinguishable from that support-success outcome; after a successful text LFS merge through the merge driver (invoked because a merge attribute was configured to select it), the designated output holds a pointer for the merged object and that object’s bytes are present in the local store under the content-addressed nested layout.
- Failure / absence: no log directory ever created; completion emissions that, when loaded and exercised in their shell, do not yield porcelain subcommand candidates for the standalone binary (or, for bash, for the multi-word git-invoked entry), including hollow scripts credited only through a hidden completion interface that bypasses the script; unknown shell names exit zero; dedup always exits zero without checking support; on a COW-capable substrate, configuring content extensions leaves dedup’s outcome indistinguishable from the no-extensions support-success path; merges of LFS text files always leave unresolved pointer conflicts with no driver path, or a successful merge leaves the designated output without a corresponding local object for the merged bytes; claiming that ordinary track alone selects the merge driver.

---

## Cross-cutting acceptance notes

- **End-to-end happy path:** install → track pattern → add/commit large file → push uploads object → fresh clone/pull restores bytes. Any implementation that only passes isolated unit stubs but cannot complete this path on a real Git repo and conforming endpoint is incomplete.
- **Pointer canonicality:** Two independent clean runs on identical bytes must produce identical pointer documents and identical local object digests.
- **Filter name stability:** The Git filter/attribute/merge name `lfs` and the on-disk `.git/lfs` namespace are part of the protocol compatibility surface and must remain those names.
- **Hook set stability:** Repository install/update installs the four VCS Orbulk hooks (pre-push, post-checkout, post-commit, post-merge); a faithful client must not silently omit the lockable post-* hooks.
- **Vocabulary:** This working PRD uses the repository’s own product names (VCS Orbulk, `git-orbulk`, git-orbulk-authenticate, git-orbulk-transfer, `.lfsconfig`, and related terms) exactly as the upstream project spells them.
