# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**VCS Orbulk** (VCS Large Object Store) is a compiled command-line Git extension. It versions large files beside an ordinary Git repository: Git stores compact **pointer** blobs, and the real bytes live in a local object store plus a remote VCS Orbulk endpoint.

The finished product is one self-contained executable named `git-orbulk`. Callers reach each capability by choosing a VCS Orbulk subcommand. Git also invokes plumbing subcommands automatically as clean/smudge/process filters and as repository hooks. The product is that binary and the on-disk, Git-config, and HTTP/SSH protocol surfaces it speaks. It is not a stable embeddable library API or ABI, and it does not implement the remote server.

The product builds and runs on Linux, macOS, Windows, and FreeBSD-class systems. Documented execution is Linux with a Go toolchain, GNU `make`, and Git 2.0.0 or newer. There is no GPU or accelerator requirement.

### Shape of the public surface

The public surface is a **CLI Git extension plus client protocol**. There is no importable package for other programs.

**Hidden-test process imports.** Hidden tests run as a Python process and import `os`, `os.environ`, `os.pathsep`, `pytest`, and `sys` for process environment, PATH joining with the platform separator, and the declared test runner. Those names are not product symbols and do not make the product an importable package.

**Binary.** The default `make` goal emits the `git-orbulk` executable under the built tree’s `bin` directory. Direct invocation is that executable followed by subcommand tokens (for example `git-orbulk` `version`). The same binary is the Git-extension entry `git orbulk`: Git locates `git-orbulk` on `PATH` and the remaining tokens are the same subcommands (for example `git orbulk version`). Both entry paths must accept the same subcommand vocabulary and, for `version` and `env`, must report the same build identity and the same per-remote dedicated server indications. When `git-orbulk` is absent from `PATH`, the Git-extension form of `version` fails with a non-zero exit.

**Subcommands.** Nested subcommands after the binary or after `git orbulk`. The finite porcelain set is: `checkout`, `clone`, `completion`, `dedup`, `env`, `ext`, `fetch`, `fsck`, `install`, `lock`, `locks`, `logs`, `ls-files`, `migrate`, `prune`, `pull`, `push`, `status`, `track`, `uninstall`, `unlock`, `untrack`, `update`, and `version`. The finite plumbing set is: `clean`, `filter-process`, `merge-driver`, `pointer`, `post-checkout`, `post-commit`, `post-merge`, `pre-push`, `smudge`, and `standalone-file`. Built-in help is `help`, optionally followed by a subcommand name (for example `help` `env`). Exact flags and return shapes for each subcommand belong with those symbols, not here. The option tokens used across `install`, `uninstall`, and `update` are `--skip-repo`, `--skip-smudge`, `--force`, `--manual`, `--local`, `--worktree`, `--system`, and `--file=` (equals-attached path). Which of those tokens each of those subcommands accepts, and the effect of each token, belong with those symbols. The option tokens used by `pointer` are `--file=` (equals-attached path), `--stdin`, `--check`, `--strict`, `--no-strict`, and `--pointer=` (equals-attached path). Generate, check, and compare share that vocabulary; roles and invalid combinations belong with that symbol. The pointer `--file=` names a local payload or pointer-document path, not the Git-config-file scope used by `install`, `uninstall`, and `update`. The option tokens used by `track` are `--no-excluded`, `--json`, `--filename`, `--lockable`, `--not-lockable`, `--no-modify-attrs`, `--dry-run`, and `--verbose`. Roles and invalid combinations belong with that symbol. The attribute word `lockable` on this surface is not those option tokens. `untrack` takes pattern arguments and has no option tokens in this contract; removal of matching `lfs` enable lines belongs with that symbol. The option token used by `smudge` is `--skip`. That token belongs with that symbol: it is not `install`’s `--skip-smudge`. The option tokens used by `push` are `--object-id`, `--all`, `--stdin`, and `--dry-run`. Roles belong with that symbol. Those `push` tokens are not `fetch`’s `--all`, `--stdin`, and `--dry-run`, `pointer`’s `--stdin`, `track`’s `--dry-run`, `ls-files`’s `--all`, `prune`’s `--dry-run`, or `fsck`’s `--dry-run`. The option token used by `pre-push` is `--dry-run`. That token belongs with that symbol; it is not `push`’s `--dry-run`, `fetch`’s `--dry-run`, `track`’s `--dry-run`, `prune`’s `--dry-run`, or `fsck`’s `--dry-run`. The option tokens used by `fetch` are `--include`, `--exclude`, `--recent`, `--all`, `--stdin`, `--prune`, `--refetch`, `--dry-run`, and `--json`. Roles and invalid combinations belong with that symbol. Those `fetch` tokens are not `pointer`’s `--stdin`, `track`’s `--json` and `--dry-run`, `push`’s `--all`, `--stdin`, and `--dry-run`, `ls-files`’s `--all`, `--json`, `--include=`, and `--exclude=`, `prune`’s `--dry-run` and `--recent`, `fsck`’s `--dry-run`, `migrate`’s `--include=`, or the porcelain subcommand `prune`. The option token used by `pull` is `--include`. That token belongs with that symbol. That `pull` `--include` is not `ls-files`’s `--include=` or `migrate`’s `--include=`. The option tokens used by `checkout` are `--to`, `--base`, `--ours`, and `--theirs`. Roles belong with that symbol. The option tokens used by `clone` are `--include` and `--skip-repo`. Roles belong with that symbol. That `clone` `--include` is not `ls-files`’s `--include=` or `migrate`’s `--include=`. That `clone` `--skip-repo` is not `install` / `uninstall` / `update`’s filter-scope skip; `clone` also forwards Git clone’s `--template` and `--config` (passthrough, not new product option names). The option token used by `lock` is `--json`. Roles belong with that symbol. That `lock` `--json` is not `track`’s `--json` or `fetch`’s `--json`. The option tokens used by `unlock` are `--id=` (equals-attached lock id), `--force`, and `--remote`. Roles belong with that symbol. That `unlock` `--force` is not `install` / `uninstall` / `update`’s hook-overwrite `--force` or `prune`’s `--force`. The option tokens used by `locks` are `--path`, `--id=` (equals-attached lock id), `--json`, `--local`, `--cached`, and `--verify`. Roles belong with that symbol. That `locks` `--json` is not `track`’s `--json`, `fetch`’s `--json`, or `lock`’s `--json`. That `locks` `--local` is not `install` / `uninstall` / `update`’s repository-local filter-scope `--local`. That `locks` `--verify` is not the batch action key `verify` and is not the locking route `locks/verify`. The option tokens used by `status` are `--porcelain` and `--json`. Roles belong with that symbol. That `status` `--json` is not `track`’s `--json`, `fetch`’s `--json`, `lock`’s `--json`, `locks`’s `--json`, or `ls-files`’s `--json`. The option tokens used by `ls-files` are `--json`, `--long`, `--size`, `--name-only`, `--debug`, `--all`, `--deleted`, `--include=` (equals-attached path), and `--exclude=` (equals-attached path). Roles and invalid combinations belong with that symbol. Those `ls-files` tokens are not `track`’s `--json`, `fetch`’s `--json`, `--include`, `--exclude`, and `--all`, `push`’s `--all`, `pull`’s `--include`, `clone`’s `--include`, `lock`’s `--json`, `locks`’s `--json`, `status`’s `--json`, or `migrate`’s `--include=`. That `ls-files` `--include=` is not `fetch` / `pull` / `clone`’s following-argument `--include` and is not `migrate`’s `--include=`. That `ls-files` `--exclude=` is not `fetch`’s following-argument `--exclude`. That `ls-files` `--all` is not `fetch`’s `--all` or `push`’s `--all`. The option tokens used by `prune` are `--dry-run`, `--force`, `--recent`, `--verify-remote`, `--verify-unreachable`, `--when-unverified=` (equals-attached halt or continue), and `--verbose`. Roles belong with that symbol. Those `prune` tokens are not `fetch`’s `--dry-run` and `--recent`, `track`’s `--dry-run` and `--verbose`, `push`’s `--dry-run`, `pre-push`’s `--dry-run`, `fsck`’s `--dry-run`, `install` / `uninstall` / `update`’s `--force`, or `unlock`’s `--force`. That porcelain `prune` is not `fetch`’s `--prune`. The option tokens used by `fsck` are `--objects`, `--pointers`, and `--dry-run`. Roles belong with that symbol. Those `fsck` tokens are not `track`’s `--dry-run`, `push`’s `--dry-run`, `fetch`’s `--dry-run`, `pre-push`’s `--dry-run`, or `prune`’s `--dry-run`. That `fsck` `--pointers` is not `migrate`’s `--pointers=`. The nested mode tokens used by `migrate` are `info`, `import`, and `export`. The option tokens used by `migrate` are `--yes`, `--pointers=` (equals-attached `follow`, `ignore`, or `no-follow`), `--include=` (equals-attached glob), `--include-ref=` (equals-attached ref), `--exclude-ref=` (equals-attached ref), `--everything`, `--fixup`, `--no-rewrite`, and `--skip-fetch`. Roles belong with that symbol. That `migrate` `--include=` is not `fetch` / `pull` / `clone`’s following-argument `--include` and is not `ls-files`’s `--include=`. That `migrate` `--pointers=` is not `fsck`’s `--pointers`. The nested mode tokens used by `logs` are `show`, `last`, and `clear`. Default `logs` (no nested token) lists stored-log names. Roles belong with that symbol. The option token used by `dedup` is `--test`. That token is the filesystem-support test-mode switch. Roles belong with that symbol. The option tokens used by `merge-driver` are `--ancestor`, `--current`, `--other`, `--marker-size`, and `--output`. The Git-invoked user merge-driver command supplies Git’s stage placeholders after those tokens: `%O` after `--ancestor`, `%A` after `--current`, `%B` after `--other`, `%L` after `--marker-size`, and `%A` after `--output`. Roles belong with that symbol.

**Git integration.** Install writes Git clean/smudge/process filters under the filter name `lfs` and, inside a repository, the four hooks `pre-push`, `post-checkout`, `post-commit`, and `post-merge`. Track records filter, diff, and merge attributes as `lfs` in `.gitattributes`. The on-disk namespace under the Git directory remains `.git/lfs`.

**Protocol.** The client is an HTTP(S) and optional SSH peer of a VCS Orbulk endpoint. It is not itself a server. Batch negotiation, basic GET/PUT transfer, locking (collection `POST`/`GET` on a path that is `locks` or ends with `/locks`, unlock `POST` addressed by lock id on a path that contains `/locks/` and ends with `/unlock`, and a verify-class `POST` whose path is `locks/verify` or ends with `/locks/verify`), and optional pure SSH transfer (`git-orbulk-transfer`) plus the SSH authentication helper `git-orbulk-authenticate` are wire surfaces, not library calls.

### Naming conventions

**Product and executable.** The product identity is VCS Orbulk. The executable basename is `git-orbulk`. Usage text names the product (the `orbulk` span); hyphen versus space and letter case in that product mention are not pinned. Version identity is not a product-name mention alone: it is a dotted token adjacent to the `git-orbulk` / `git orbulk` entry spelling.

**Git-extension entry.** The documented multi-word entry is `git orbulk` followed by a subcommand. Direct entry is `git-orbulk` followed by the same subcommand. Subcommand names are lowercase tokens as listed above, including hyphenated plumbing names such as `filter-process`, `ls-files`, and `standalone-file`.

**Git filter and attributes.** The Git filter, diff, and merge attribute value used for tracked paths is `lfs`. Ordinary track writes those three plus disabled Git text conversion; lockable is an additional optional attribute. The text merge-driver plumbing command is not selected by that ordinary `lfs` merge attribute; a separate merge attribute (documentation illustrates a name such as `lfs-text`) must point at `merge-driver`.

**Git config namespace.** Product settings live under the `lfs` Git-config section and as per-remote keys `remote.<remote>.lfsurl` / `remote.<remote>.lfspushurl`. The default Git remote name is `origin`.

**Repository file names.** Team defaults may live in `.lfsconfig` at the repository root (Git-config syntax). Attribute patterns live in `.gitattributes`.

**Batch operations and transfer adapters.** Batch operation names are `download` and `upload`. The built-in HTTP adapter name is `basic` (omitting the advertised-transfer list means the peer assumes `basic`). The advanced HTTP adapter name is `tus`. Pure SSH transfer mode names are `negotiate`, `always`, and `never`, selected by the Git-config key `lfs.sshtransfer`. SSH helpers are invoked with the repository path and the same `download` or `upload` operation.

**Completion shells.** `completion` emits a script for exactly `bash`, `fish`, and `zsh`.

**Logs.** Nested tokens after `logs` are `show`, `last`, and `clear`. Default `logs` writes each stored-log name as a nonempty standard-output line used as the `show` argument and as a filename under the Git-directory `lfs` namespace. `last` shows the most recent stored log. List, show, and clear shapes belong with that symbol.

### Global observables an implementer must reproduce

**Process exits and streams.**

- A successful run of no-subcommand invocation, `help`, per-command help, `version`, and `env` exits 0.
- No-subcommand invocation and `help` write user-facing usage on standard output: they name the product (the `orbulk` span), span more than one line, and are not merely the version-identity presentation. Product-wide `help` and `help` `env` are different texts. Per-command help for `env` still names that subcommand.
- `version` writes a non-empty identity presentation on standard output. That presentation includes a dotted version-identity token (decimal components separated by dots, at least major.minor, or longer) adjacent to the `git-orbulk` / `git orbulk` entry spelling. A banner that only names VCS Orbulk plus a dotted number is not a recognized identity. Exact banner wording and the version-number string are not fixed. The same identity is a fact of this build: it does not change across repositories, and the Git-extension path and the direct binary report the same token.
- `env` writes a non-empty configuration report on standard output (more than one line). That report is not merely the version-identity presentation.
- An unknown subcommand, an undefined option at the top-level entry, and an undefined option after a known subcommand (`env` or `version`) each exit non-zero, write a non-empty error on standard error, and are distinguishable from running the same entry without that token. A bare invocation (no subcommand) succeeds and is distinguishable from an unknown subcommand.
- Mutually incompatible options on a command fail with the same non-zero-plus-stderr shape. This surface does not pin a numeric failure code beyond zero versus non-zero.
- Removing `git-orbulk` from `PATH` makes the Git-extension `version` path (`git orbulk version`) fail with a non-zero exit, distinguishable from the same invocation with the binary present.

**Version identity versus environment related facts.**

- `env` presents the same build identity among related environment facts, not as a dedicated per-remote server indication and not as a Git-remote listing.
- Agreement is of that identity token, not of a dedicated server URL, a Git remote URL, or an unrelated related-fact string such as a filter command.

**Environment report: dedicated per-remote server indication.**

- For each Git remote, `env` presents a dedicated indication of the VCS Orbulk server URL that would be used. That indication is an HTTP(S) URL, distinct from that remote’s Git URL, and distinct from other remotes’ dedicated indications when those remotes have distinct Git URLs.
- The indication is available before any object transfer. Wording, label, and layout of the indication are not pinned.
- Default remote `origin`: the report is not required to contain the word `origin`. The origin indication is the would-use-server URL that is not on a named sibling remote’s observations and is not merely the origin Git remote listing.
- Named remotes other than `origin`: observations are lines that carry both the remote name and an HTTP(S) URL.
- With no remotes, `env` still succeeds and still prints effective configuration (including filter summary and related facts that present this build’s identity). It does not have to invent a dedicated would-use-server URL.

**Endpoint derivation and URL overrides.**

- With no override, the client derives the endpoint from the Git remote URL by appending the conventional `.git/info/lfs` suffix (whether or not the remote URL already ended in `.git`), including translating SSH-style Git remotes into the corresponding HTTPS host/path form for HTTP API use. A `git://` remote's dedicated indication starts with `https://` by default. Setting `lfs.gitprotocol` to `http` changes that derived dedicated indication so it starts with `http://` and not `https://`.
- Repository or global `lfs.url` replaces that derived URL on every remote’s dedicated indication. An echo of the override among related facts while the dedicated indication still names the derived URL does not count as replacement.
- `remote.<remote>.lfsurl` (including `remote.origin.lfsurl`) replaces the derived URL only on that remote’s dedicated indication. A sibling remote without the same override keeps its own discovery result.
- `lfs.pushurl` / `remote.<remote>.lfspushurl` override the upload endpoint when push must use a different host than download.
- Default remote selection: explicit Orbulk URL, then branch remote settings, then the configured Orbulk default remote name in `remote.lfsdefault`, then a single existing remote, otherwise `origin`. Analogous upload/lock remote selection uses the current branch’s push remote, then the configured Orbulk push-default remote name in `remote.lfspushdefault`, then the same sole-remote / `origin` fallback.

**Git configuration and `.lfsconfig`.**

- The client reads every file Git’s config machinery supports. Git config overrides `.lfsconfig`.
- `.lfsconfig` sits at the repository root. If it is missing from the work tree, the client looks in the index, then `HEAD` (bare repositories: `HEAD` only). Unknown keys in that file are ignored. The finite keys accepted there are exactly: `lfs.url`, `lfs.pushurl`, `remote.<remote>.lfsurl`, `remote.lfsdefault`, `remote.lfspushdefault`, `lfs.fetchinclude`, `lfs.fetchexclude`, `lfs.storage`, `lfs.skipdownloaderrors`, `lfs.allowincompletepush`, `lfs.locksverify`, `lfs.<url>.access`, and `lfs.gitprotocol`.
- The URL-scoped access key is `lfs.` plus the endpoint URL plus `.access`. Setting that key in `.lfsconfig` to `basic` makes the first API request already carry HTTP Basic. Without that SET, the first API request has no Authorization.
- `lfs.allowincompletepush` set to a documented truthy token (`true`) lets `git push` of a missing local object succeed: Git refs advance and the client omits the PUT of those bytes. Unset, that same missing-object `git push` fails with a non-zero exit and still omits the PUT.
- `env`’s filter configuration summary reflects the effective Git values for `filter.lfs.process`, `filter.lfs.smudge`, and `filter.lfs.clean`. A locally or globally set `filter.lfs.clean` value appears in the report; a value that was never configured does not.
- Fetch include and exclude Git-config keys the client honors are `lfs.fetchinclude` and `lfs.fetchexclude`. The environment report names the configured fetch include and exclude patterns.
- Transfer-path Git-config keys the client honors are `lfs.tustransfers`, `lfs.basictransfersonly`, and `lfs.concurrenttransfers`. `lfs.tustransfers` set to `true` enables the tus advertisement path. Enabling optional tus uploads is visible on the environment report after the configuration-key spelling is removed. `lfs.basictransfersonly` set to `true` is the basic-transfers-only switch that drops advanced adapter names from the advertised list. `lfs.concurrenttransfers` is the concurrent-transfer bound (default parallelism is greater than one; a bound of `1` keeps a second transfer from overlapping). These three keys are the configuration that produces the on/off advertisement contrast and the overlap bound. The environment report names the configured concurrent-transfer bound.
- Fetch recentness Git-config keys the client honors are `lfs.fetchrecentrefsdays`, `lfs.fetchrecentcommitsdays`, and `lfs.fetchrecentalways`. `fetch` `--recent` uses that window. The environment report names the configured `lfs.fetchrecentrefsdays` value. Transfer-retry Git-config keys the client honors are `lfs.transfer.maxretries` and `lfs.transfer.maxretrydelay`.
- HTTP timeout Git-config keys the client honors are `lfs.dialtimeout`, `lfs.tlstimeout`, `lfs.activitytimeout`, and `lfs.keepalive`. Integer Git-config values for those keys are seconds of wall clock. `lfs.activitytimeout` is the inactivity bound on a transfer: a stall longer than that bound fails the transfer; a bound longer than the stall lets it complete.
- Pure SSH transfer mode is the Git-config key `lfs.sshtransfer`. Accepted values are `negotiate`, `always`, and `never`. Default mode is `negotiate`.
- Progress-forcing Git-config key is `lfs.forceprogress`. Lockable read-only Git-config key is `lfs.setlockablereadonly` (default enabled). Those two keys are not in the `.lfsconfig` allowlist: writing either only in `.lfsconfig` is ignored.
- Prune-default Git-config keys the client honors are `lfs.pruneoffsetdays` and `lfs.pruneverifyremotealways`. The environment report names the configured prune-offset value. `lfs.pruneverifyremotealways` set to `true` makes `prune` consult the endpoint as `--verify-remote` does, including when `--verify-remote` is omitted.
- Custom transfer agent bindings use `lfs.customtransfer.<name>.path` for the process path of a named agent. The per-agent concurrent-instances sibling of that process-path key is `lfs.customtransfer.<name>.concurrent`. A documented falsey token (`false`) on that sibling means concurrent instances are not allowed, so a single agent process runs. That sibling is not the transfer-overlap bound `lfs.concurrenttransfers`. The standalone transfer agent binding is `lfs.standalonetransferagent`. After those bindings, the environment report still names the agent name.
- Each registered content extension is three Git-config keys under the `lfs.extension.<name>` family: `lfs.extension.<name>.clean` is the clean external command, `lfs.extension.<name>.smudge` is the smudge external command, and `lfs.extension.<name>.priority` is the priority number. Clean applies those commands in ascending priority-number order (a smaller number before a larger one). Smudge reverses that clean order from the pointer-recorded metadata, not from a later swap of only those priority numbers. This surface does not pin pointer metadata key spelling, append-token text, a particular pair of numeric values, stderr wording, or exit-code numbers. `ext` names each registered extension.

**Boolean tokens.**

- `true` is a documented truthy token for the skip, progress-forcing, and lockable-read-only environment carriers and for the Git-config booleans those same settings use. `1` is also a documented truthy token for the skip environment carriers. `false` is a documented falsey token. A boolean that is not a documented truthy token is falsey: skip and progress-forcing stay off, and lockable read-only is disabled rather than left at its default-enabled state.

**Skip environment carriers.**

- Exporting `GIT_ORBULK_SKIP_SMUDGE` to a documented truthy token (`true`) turns skip-smudge on: checkout and smudge pass pointer text through without downloading or materializing object bytes, including when the object is already local. A documented falsey token (`false`) or a boolean that is not a documented truthy token leaves skip-smudge off: checkout still materializes object bytes.
- Exporting `GIT_ORBULK_SKIP_PUSH` to a documented truthy token (`true`) turns skip-push on: `pre-push` uploads nothing and `git push` still updates Git refs. With that setting off (unset, a documented falsey token, or a boolean that is not a documented truthy token), the same pending object is PUT.
- Exporting `GIT_ORBULK_SKIP_DOWNLOAD_ERRORS` to a documented truthy token (`true`) turns skip-download-errors on: when a smudge download would fail, checkout succeeds and leaves pointer text in the working tree. Unset and a boolean that is not a documented truthy token still fail that cannot-download checkout.

**Progress-forcing.**

- Exporting `GIT_ORBULK_FORCE_PROGRESS` to a documented truthy token (`true`), or setting `lfs.forceprogress` to that same token, turns on in-progress transfer reporting when standard output is not a terminal. The discriminating leftover is in-progress reporting after shared completion chunks are removed; a completion line on both arms is not that contrast. Exact progress text and meter punctuation are not pinned. A boolean that is not a documented truthy token stays off. Writing `lfs.forceprogress` only in `.lfsconfig` is ignored.

**Lockable read-only.**

- Lockable read-only defaults to enabled. Exporting `GIT_ORBULK_SET_LOCKABLE_READONLY` to a documented truthy token (`true`), or leaving both that carrier and `lfs.setlockablereadonly` unset, leaves an unlocked lockable working-tree path read-only after the post-* file-checkout path. Exporting that carrier or setting `lfs.setlockablereadonly` to a documented falsey token (`false`), or to a boolean that is not a documented truthy token, leaves that unlocked lockable path writable after the same path. Writing `lfs.setlockablereadonly` only in `.lfsconfig` is ignored: it cannot disable lockable read-only, unlike the same key in Git config.

**Local object store.**

- Default store root is the Git directory’s `lfs` namespace. Objects live under `.git/lfs/objects`, then a shard of the first two hex digits of the object id, then the next two hex digits, then the full object id.
- The Git-config key `lfs.storage` replaces that store root (the parent of the objects directory), not the objects directory itself. Cleaned objects still use the objects-directory-plus-shard layout under the relocated root and are not written at the default Git-directory objects path. The environment report names the configured storage-root path.
- Corrupted objects moved aside by integrity check go to the repository’s Orbulk `bad` quarantine directory.

**Pointer documents (Git blob payload).**

- A non-empty pointer is a UTF-8 text document of key/value lines: one key, one space, one value, one Unix newline. Keys use only lowercase letters, digits, dot, and hyphen. The first key is `version`. Required keys after that are `oid` and `size`. Lines after the version line are sorted by key ascending. Values contain no carriage returns or newlines. The whole document stays under 1024 bytes. There is exactly one canonical encoding for a given payload.
- The `version` value is a fixed protocol version identifier compared by exact string equality (no URL parsing or case folding). Newly written pointers use the current VCS Orbulk v1 identifier https://git-orbulk.example.com/spec/v1. The client can still read pointers that use the leftover still-readable legacy pre-release identifier `https://cordage.example.com/spec/v1`; ordinary check of that leftover document succeeds, and strict check fails with a valid-but-not-canonical status distinguishable from both canonical success and a merely invalid pointer. Generate writes the current identifier and must not emit the leftover identifier. Some other still-readable alias is not a substitute for that leftover role.
- The `oid` value is the SHA-256 hash-method label `sha256`, then a colon, then a 64-character lowercase hex digest. Current clients write only SHA-256.
- The `size` value is the object size in bytes as a decimal integer.
- Empty working-tree content maps to an empty pointer document (passthrough) and is not forced through the hashed-object path.
- Pointer blobs stored in Git preserve the executable bit of the replaced working-tree file.

**HTTP batch and basic transfer.**

- The client POSTs a batch request to the endpoint’s `objects/batch` path. Each batch request sends `Accept` and `Content-Type` naming the designated JSON media type `application/vnd.git-orbulk+json` (type/subtype; an optional charset parameter on `Content-Type` is accepted, and `Accept` may list additional types). Batch responses use that same media type.
- The request JSON is an object with `operation` (`download` or `upload`), an `objects` list of objects each naming `oid` and `size` (size at least zero), and an optional `transfers` list of adapter names. Omitting `transfers` means the peer assumes `basic`. The request may name the hash algorithm (default SHA-256 / `sha256`).
- With `lfs.tustransfers` set to `true` and `lfs.basictransfersonly` not enabled, the advertised `transfers` list includes `tus` in addition to `basic`. With `lfs.basictransfersonly` set to `true` under that same tus enablement, `tus` is absent and only `basic` remains (or `transfers` is omitted).
- The reply JSON is an object with a selected `transfer` and an `objects` list. Each reply object either carries an `actions` map, carries an `error` object, or names the object without `actions`.
- Action maps are keyed `download`, `upload`, and (when present) `verify`. Each action object has `href` and `header` (the header map the client forwards on the subsequent GET or PUT). An action may include `expires_at`; a past `expires_at` is a visible failure, not a successful transfer of missing content.
- Already-exists encoding: the reply object has no `actions` map; the client omits a second PUT of that oid.
- Per-object error encoding: the reply object has an `error` object with `code` and `message` and no `actions`; that object is not transferred and the command fails.
- Basic download is HTTP GET of the action `href` with the supplied `header` map; the response body is raw object bytes. Basic upload is HTTP PUT of raw bytes to the action `href` with that same `header` map. A `verify` action, when present, runs after upload.

**Custom transfer JSON control protocol.**

- When a registered custom agent is selected, the client launches the process bound at `lfs.customtransfer.<name>.path` and speaks line-delimited JSON objects on that process’s standard input and standard output. Object bytes travel via paths the agent understands, not as raw file bytes on that control stream.
- Each control-stream object has an `event` field. The client writes `init` to start the session and `terminate` to end it. Transfer events are `upload` and `download`. Those transfer events name the object in `oid` and the path the agent understands in `path`.
- The agent writes later control-stream objects whose `event` is `progress` and then `complete`. On `upload`, that client-supplied `path` is the file the agent reads. A `download` finishes when the agent reports `complete` with the `path` where it stored the object. The client takes those bytes from that reported `path` into the local store.

**Locking API.**

- Create, list, and unlock use the collection and unlock-by-id routes below. Those are the routes the porcelain subcommands `lock`, `unlock`, and `locks` speak. Verify is a distinct route those porcelain names are not.
- The collection path is `locks`. A request path that is `/locks` or that ends with `/locks` is that route.
- Create is a collection `POST`. The request JSON names `path` as the repository-relative path being locked. A successful create records that path on the endpoint.
- List is a collection `GET`. The reply JSON is an object with a `locks` list. Each lock object names `id`, `path`, `locked_at`, and `owner` (an object with `name`).
- Unlock is a `POST` addressed by lock id: a request path that contains `/locks/` and ends with `/unlock`, with the lock id as the path segment between `locks` and `unlock`. The request JSON may name `force`; porcelain `--force` of a foreign lock depends on that body when the endpoint permits it. A successful unlock removes that lock from the endpoint.
- Create and unlock replies wrap that same lock object under `lock`.
- The client POSTs a verify-class locking exchange to the endpoint’s `locks/verify` path. A request path that is `/locks/verify` or that ends with `/locks/verify` is that route. This is not the batch action key `verify`, and it is not named by the porcelain subcommands `lock`, `unlock`, or `locks`.
- When lock verification is enabled (`lfs.locksverify` set to `true`), `push` consults that route.

**SSH helpers.**

- For SSH Git remotes, the client may run `git-orbulk-authenticate` over SSH with the repository path and `download` or `upload`. On success, the helper’s JSON uses the field `header` for the authorization-header map and may use the field `href` for an alternate endpoint URL. A successful helper’s `header` map is attached to later API requests. A present `href` replaces the derived HTTPS endpoint. Expiry hints stay optional.
- Pure SSH transfer runs `git-orbulk-transfer` over SSH with the repository path and the same operations, then speaks a pkt-line capability-oriented protocol. The peer writes a `version=1` capability line and a flush. The client selects version 1 by sending a command that starts with the `version` token plus a space. The peer writes object bytes onto the channel when the client command starts with `get-object`. The peer stores upload bytes when the client command starts with `put-object`. After a successful put, a further same-channel round-trip is required; that verification command’s token, packet wording, and numeric status are not pinned. The Git-config key `lfs.sshtransfer` selects among `negotiate`, `always`, and `never`. Default mode is `negotiate`.

## `checkout`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--to` — following output path. Used with `--base`, `--ours`, or `--theirs` to write that merge-conflict stage to a separate file.
- `--base` — write the base-stage object bytes of the named path to the `--to` file.
- `--ours` — write the ours-stage object bytes of the named path to the `--to` file.
- `--theirs` — write the theirs-stage object bytes of the named path to the `--to` file.

### Observable rules

`checkout` materializes working-tree files from the local store for the current ref when the working tree has missing files or pointer placeholders. It does not download. A glob argument that is not an exact path updates only matching paths.

Modified working-tree files are not overwritten.

`--to` plus `--base`, `--ours`, or `--theirs` writes that stage’s object bytes to the named output file.

In a bare repository, `checkout` has no effect: it does not materialize a working-tree path and does not change local store occupancy.

Removing `git-orbulk` from `PATH` makes the Git-extension `checkout` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `clone`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--include` — following path argument. Replaces configured include (`lfs.fetchinclude`) for the download phase. Only matching paths are downloaded and materialized.
- `--skip-repo` — withhold repository-hook installation. This is not an absence or presence observation of the four hooks `pre-push`, `post-checkout`, `post-commit`, and `post-merge`. This token is not `install` / `uninstall` / `update`’s filter-scope skip.

`clone` also forwards Git clone’s `--template` and `--config`. Those are Git passthrough, not new product option names. The product-key half of `--config` is the transfer-retry key `lfs.transfer.maxretries`.

### Observable rules

`clone` wraps Git clone, then batch-downloads objects and materializes tracked files. Without `--skip-repo`, it installs the four hooks `pre-push`, `post-checkout`, `post-commit`, and `post-merge`. `--skip-repo` withholds that installation and is not an absence or presence observation of those four hooks.

Configured exclude is `lfs.fetchexclude` and applies to the download phase.

When the download phase fails, the command ends in a non-success outcome distinguishable from success; a usable Git repository produced by the underlying clone may still remain.

When repository hook installation cannot succeed and `--skip-repo` was not given, the command ends in a non-success outcome distinguishable from both a successful hook-installing clone and a `--skip-repo` success; a Git repository produced by the underlying clone may still remain.

Removing `git-orbulk` from `PATH` makes the Git-extension `clone` path fail with a non-zero exit.

Transfer-retry bounds the client honors are `lfs.transfer.maxretries`, `lfs.transfer.maxretrydelay`, and `lfs.dialtimeout`.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, and banner wording, are not pinned.

## `dedup`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--test` — filesystem-support test-mode switch. Reports whether copy-on-write cloning is supported and does not re-link working-tree files as clones of local store objects.

### Observable rules

Ordinary `dedup` (no `--test`) on a copy-on-write-capable repository root re-links tracked working-tree files as independently writable clones of the matching local store objects.

`dedup` `--test` on that same root succeeds and does not perform that re-link.

Both ordinary `dedup` and `dedup` `--test` fail with a non-zero exit when the repository root does not support copy-on-write cloning, or when content extensions are configured.

Ordinary `dedup` (no `--test`) fails with a non-zero exit when Git repository prerequisites are absent. This surface does not pin whether `dedup` `--test` fails when those prerequisites are absent.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned. This surface does not require `--test` to appear in product output.

## `fetch`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--include` — following path argument. Replaces configured include (`lfs.fetchinclude`). Only matching paths are fetched.
- `--exclude` — following path argument. Replaces configured exclude (`lfs.fetchexclude`). Matching paths are not fetched.
- `--recent` — fetch recent refs using the recentness window.
- `--all` — with a given ref, walk that ref’s history; with no refs, walk all refs. Ignores configured include/exclude. Cannot be combined with `--recent`, `--include`, or `--exclude`.
- `--stdin` — select the listed ref from standard input. This token is not `pointer`’s `--stdin`.
- `--prune` — after a successful fetch, delete an unreferenced local object. This token is not the porcelain subcommand `prune`.
- `--refetch` — GET an already-local object.
- `--dry-run` — neither GET nor populate the store. This token is not `track`’s `--dry-run`.
- `--json` — with `--dry-run`, emit parseable JSON of the transfer plan. Field names and layout are not pinned. This token is not `track`’s `--json`.

### Observable rules

`fetch` writes objects into the local store and leaves working-tree bytes unchanged. Omitting remote and refs fetches the current checkout, not another branch. Naming a remote and a ref fetches that ref.

Configured include is the Git-config key `lfs.fetchinclude`. Configured exclude is `lfs.fetchexclude`. CLI `--include` and `--exclude` replace those configured filters.

`--recent` uses the recentness window from `lfs.fetchrecentrefsdays`, `lfs.fetchrecentcommitsdays`, and `lfs.fetchrecentalways`.

`--all` with a given ref walks that ref’s history (objects reachable from history, not only the current tree). `--all` with no refs walks all refs. `--all` ignores configured include/exclude. Combining `--all` with `--recent`, `--include`, or `--exclude` is invalid: the command fails and does not populate the store.

`--stdin` selects the listed ref in place of the default.

`--prune` deletes an unreferenced local object after a successful fetch; fetch without `--prune` leaves that object.

`--refetch` GETs an already-local object; default fetch does not.

`--dry-run` neither GETs nor populates the store.

`--json` plus `--dry-run` emits parseable JSON that is stable at fixed occupancy and unlike `--refetch` or `--exclude` at that same occupancy. JSON field names are not pinned.

An unreachable endpoint or a rejected-credentials endpoint fails and does not populate the store. Removing `git-orbulk` from `PATH` makes the Git-extension `fetch` path fail with a non-zero exit.

Transfer-retry bounds the client honors are `lfs.transfer.maxretries`, `lfs.transfer.maxretrydelay`, and `lfs.dialtimeout`.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, and JSON field names are not pinned.

## `fsck`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--objects` — object checks only. A pointer-only defect is not a finding.
- `--pointers` — pointer checks only. Object corruption is not a finding.
- `--dry-run` — report a hash mismatch without moving the mismatched file into the repository Orbulk `bad` quarantine. This token is not `track`’s `--dry-run`, `push`’s `--dry-run`, `fetch`’s `--dry-run`, `pre-push`’s `--dry-run`, or `prune`’s `--dry-run`.

### Observable rules

Default `fsck` (neither `--objects` nor `--pointers`) runs both object checks and pointer checks.

`--objects` does not treat a pointer-only defect as a finding. `--pointers` does not treat object corruption as a finding.

A bit-flipped local object is a non-zero finding. Without `--dry-run`, that file is moved into the repository Orbulk `bad` quarantine and a timestamp-aligned neighbor stays on its sharded path. A missing object is a non-zero finding and is not quarantined.

Pointer defects are reported and are not quarantined: a non-canonical pointer whose line endings include carriage returns, and an Orbulk-attributed path stored as an ordinary Git blob.

Omitted-revision default object checks cover a staged index-only path. Explicit `HEAD` does not: that index-only flipped object stays on its sharded path and is not quarantined.

Configured exclude is `lfs.fetchexclude`. Matching paths are omitted from object checks and remain subject to pointer checks. An unmatched flipped path is still isolated.

A named committish or a two-dot range is the checked set, not always `HEAD`. A single argument that cannot be resolved as a committish or as both ends of a two-dot range, including a three-dot range token, exits non-zero and does not complete a successful integrity check of the default revision: a flipped `HEAD` object stays put.

`--dry-run` reports a hash mismatch without moving the file. Live `fsck` of the same layout quarantines it.

Both entry paths succeed on a clean repository. Removing `git-orbulk` from `PATH` makes the Git-extension `fsck` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, and report layout are not pinned.

## `install`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--skip-repo` — write `filter.lfs.clean`, `filter.lfs.smudge`, and `filter.lfs.process` in the chosen Git-config scope and do not install repository hooks.
- `--skip-smudge` — write smudge and process values that differ from an ordinary (would-download) install. The product’s own skip-smudge values are not a protected foreign filter: an ordinary install may replace them without `--force`, and `--skip-smudge` may replace the product’s own ordinary smudge/process values without `--force`.
- `--force` — replace a pre-existing non-Orbulk filter definition, and overwrite a foreign hook body with the current standard hook body.
- `--manual` — when a foreign hook body would block automatic installation, leave that file unchanged and emit caller-visible hook-integration guidance. That guidance is distinguishable from empty output, from an unknown-option rejection, and from a filter-only success that says nothing about integrating hooks. Exact wording is not pinned.
- `--local` — write the three `lfs` filter keys in repository-local Git config. Default install (no scope option) writes those keys in global scope, not local. `--local` outside a repository fails and does not write global filters.
- `--worktree` — write the three `lfs` filter keys in worktree Git config when Git is at least 2.20.0 and worktree config is enabled. On Git that lacks that support, or outside a repository, `--worktree` fails and does not rewrite global filters.
- `--system` — write the three `lfs` filter keys in system Git config. When that scope cannot be written, the command fails and does not rewrite global filters.
- `--file=` — write the three `lfs` filter keys only in the named Git-config file (equals-attached path, no space). Hooks still install when the command runs inside a repository and `--skip-repo` is not given.

Combining more than one of `--local`, `--worktree`, `--system`, and `--file=` is invalid: the command fails and does not write filters in those scopes.

### Observable rules

Without `--skip-repo`, an in-repository install also writes the four hook files `pre-push`, `post-checkout`, `post-commit`, and `post-merge`, honoring `core.hooksPath` when Git is 2.9.0 or newer. Outside a repository, install writes global filters and does not create hook files.

A non-force install that encounters a pre-existing non-Orbulk filter leaves those settings intact and fails. A non-force install that encounters a foreign hook body leaves that file unchanged and fails.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned. Filter argv, hook-script text, and banner wording are not pinned.

## `lock`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--json` — machine-readable mode on a successful create that still holds the path on the locking endpoint, and that a later live `locks` listing from another repository on the same endpoint still names. Field names and layout are not pinned. This token is not `track`’s `--json` or `fetch`’s `--json`.

### Observable rules

`lock` followed by a repository-relative path creates a server-side lock for that path. The path need not already exist in the working tree. A nested repository-relative path is the locked path.

A successful `--json` create still creates that server-side lock. JSON field names and layout are not pinned.

Locking a working-copy directory fails and does not create a server-side lock.

A second `lock` of a path the endpoint already holds fails with a conflict outcome; one lock remains.

`lock` fails when the endpoint lacks locking support and when authentication fails. Removing `git-orbulk` from `PATH` makes the Git-extension `lock` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, and JSON field names are not pinned.

## `locks`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--path` — following path argument. Names the matching lock and omits the others.
- `--id=` — equals-attached lock id. Selects one lock and is not an echo of the id token. This token is not `unlock`’s `--id=`.
- `--json` — machine-readable live listing. Parseable and names the locked path. Field names and layout are not pinned. This token is not `track`’s `--json`, `fetch`’s `--json`, or `lock`’s `--json`.
- `--local` — list the local cache of locks this repository created. Names a locally created lock and omits a foreign lock a live listing names. Still succeeds when the endpoint is unreachable. This token is not `install` / `uninstall` / `update`’s repository-local filter-scope `--local`.
- `--cached` — reuse the last successful server fetch. Must not name a lock that appeared on the endpoint only after that fetch.
- `--verify` — mark locks owned by the current user. After stripping path, owner, id, and URL covariates, two `--verify` runs are stable and unlike a live listing and unlike a foreign-owned lock on the same path. Mark characters are not pinned. This token is not the batch action key `verify` and is not the locking API path `locks/verify`.

### Observable rules

Default `locks` (no listing option) lists locks from the locking endpoint. An unreachable endpoint must not claim live-server truth for a lock that appeared on the endpoint only after the last successful fetch.

`--path` followed by a path names that lock and omits another lock on the same endpoint. A path that matches no lock names neither.

`--id=` selects the lock with that id. An unknown id names neither lock. The remainder after stripping identity covariates is not merely an echo of the id token.

`--json` emits parseable JSON that names the locked path. JSON field names and layout are not pinned.

`--local` lists the locally created lock and omits a foreign lock the live list names. `--local` still succeeds and still names the locally created lock when the endpoint is unreachable.

`--cached` reuses the last successful fetch: after a live list, it still names those locks, and it must not name a lock that appeared on the endpoint only after that fetch. A later live list does name that new lock.

`--verify` marks current-user ownership. Two `--verify` observations of the same ownership state have a stable remainder after stripping path, owner, id, and URL covariates. That remainder is distinguishable from a live listing without `--verify` and from a `--verify` listing of a foreign-owned lock on the same path. Exact mark characters are not pinned.

`locks` fails when the endpoint lacks locking support and when authentication fails. Removing `git-orbulk` from `PATH` makes the Git-extension `locks` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, verify mark characters, and JSON field names are not pinned.

## `logs`

Accepted after `git-orbulk` and after `git orbulk`. Nested mode tokens after `logs` are `show`, `last`, and `clear`. Both entry paths accept the same mode tokens.

### Modes

- `show` — show one stored log by name. The name is a nonempty standard-output line from default `logs`. Writes that log’s contents on standard output.
- `last` — show the most recent stored log. Standard output matches `show` of that most recent listed name.
- `clear` — remove stored logs. Subsequent default `logs` lists no names.

### Observable rules

Default `logs` (no nested token) lists stored logs: each stored-log name is a nonempty standard-output line. Success with no nonempty lines is an empty list. Each listed name is the `show` argument and a filename under the Git directory’s `lfs` namespace. This surface does not pin a subdirectory spelling under that namespace.

A nested diagnostic-exception entry distinct from `show`, `last`, and `clear` fails with a non-zero exit and leaves a newly listed stored log. This surface does not pin that entry’s spelling, help advertisement, or log-body wording.

After a later such failure, `last` matches `show` of the new name; `show` of an earlier listed name is unchanged.

`clear` empties the subsequent default list.

Removing `git-orbulk` from `PATH` makes the Git-extension `logs` path fail with a non-zero exit.

A successful run of default `logs`, `show`, `last`, and `clear` exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `ls-files`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--json` — machine-readable listing. Field names and layout are not pinned. Combined with `--debug`, the listing is the debug format. Combined with `--long`, `--size`, or `--name-only`, the JSON listing is unchanged. This token is not `track`’s `--json`, `fetch`’s `--json`, `lock`’s `--json`, `locks`’s `--json`, or `status`’s `--json`.
- `--long` — listing carries the full object id. Under `--json`, this token has no effect.
- `--size` — listing is distinguishable from the default named-path listing and follows object byte length. Under `--json`, this token has no effect.
- `--name-only` — names the path and is distinguishable from the default named-path listing. Under `--json`, this token has no effect.
- `--debug` — debug listing format, distinguishable from the default named-path listing and from `--json`. Combined with `--json`, preferred over `--json`.
- `--all` — names a VCS Orbulk path that exists only on another branch, which the default listing and current `--deleted` omit. Cannot be combined with an explicit ref. This token is not `fetch`’s `--all` or `push`’s `--all`.
- `--deleted` — names a path deleted on the selected ref (the current ref when none is given; one explicit non-current ref is valid). Cannot be combined with two refs.
- `--include=` — equals-attached path filter (no space). Names matching VCS Orbulk paths and omits others. Include of a never-tracked path is not an echo of a matching include. This token is not `fetch`’s `--include`, `pull`’s `--include`, or `clone`’s `--include`.
- `--exclude=` — equals-attached path filter (no space). Omits matching VCS Orbulk paths and names the others. This token is not `fetch`’s `--exclude`.

### Observable rules

Default `ls-files` (no ref) lists VCS Orbulk files on the current branch including the index: the index takes precedence for a path also in the tree (the listing carries the index object id, not the tree object id). A path present only in the index is listed. An explicit ref is that ref’s tree and ignores the index: the listing carries the tree object id, not the index object id, and an index-only path is omitted.

Two refs list VCS Orbulk files changed between those refs: a modified path is named; an unchanged path and a deleted path are omitted. Those omitted paths remain nameable on a single-ref listing of the side that still has them.

On the default named-path listing line, each entry presents a dedicated checkout indication of whether the working-tree file is the full object or only a pointer, distinct from the path, the object id, and from a dump of working-tree size or file contents. That indication differs between those two checkout states, is stable across two observations of the same checkout state, and does not flip when the working-tree file is held fixed and only local-store presence varies. Mark characters, field names, and layout are not pinned.

`--json` separately indicates local-store presence on the named entry. When the working-tree file is a pointer, store-present versus store-missing remain distinct on that named entry. When the working-tree file is the full object, store-present versus store-missing remain distinct on that named entry.

When both `--debug` and `--json` are requested, `ls-files` prefers `--debug`: the combined remainder after stripping path, object id, and payload is distinguishable from `--json` alone and from the default named-path listing, and with any JSON document excised matches `--debug` alone. Under `--json`, `--long`, `--size`, and `--name-only` have no effect: the JSON listing equals `--json` alone.

`--long` carries the independently computed full object id. `--long` plus one explicit current-branch ref still succeeds and still carries that id.

`--size` is distinguishable from the default listing after stripping path, object id, and payload, and remainders for two object byte lengths are distinguishable.

`--name-only` names the path and is distinguishable from the default listing after stripping the path, or by the full object id being present only on the default listing.

`--include=` of a tracked path names that path and omits another tracked path. `--exclude=` of a tracked path omits it and names the other. `--include=` of a never-tracked path is distinguishable from a matching include after stripping filter words.

`--all` names an other-branch-only object that the default listing omits. `--deleted` names a path deleted on the current ref that the default listing omits, and does not name an other-branch-only object.

Combining `--all` with an explicit ref is invalid: the command fails and is distinguishable from `--all` without a ref. Combining `--deleted` with two refs is invalid: the command fails and is distinguishable from `--deleted` plus one non-current ref, which succeeds and names a deletion on that ref. An invalid ref fails and is distinguishable from a legal ref that lists a path.

Removing `git-orbulk` from `PATH` makes the Git-extension `ls-files` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, mark characters, and JSON field names are not pinned.

## `merge-driver`

Accepted after `git-orbulk` and after `git orbulk`. Git invokes this plumbing entry when a user merge attribute’s driver command names it.

### Options

- `--ancestor` — ancestor-stage path. The Git-invoked command supplies Git’s `%O` placeholder after this token.
- `--current` — current-stage path. The Git-invoked command supplies Git’s `%A` placeholder after this token.
- `--other` — other-stage path. The Git-invoked command supplies Git’s `%B` placeholder after this token.
- `--marker-size` — conflict-marker size. The Git-invoked command supplies Git’s `%L` placeholder after this token.
- `--output` — designated output path. The Git-invoked command supplies Git’s `%A` placeholder after this token.

### Observable rules

The user merge-driver command Git is configured to run is `git orbulk merge-driver` `--ancestor` `%O` `--current` `%A` `--other` `%B` `--marker-size` `%L` `--output` `%A`.

Ordinary track’s `lfs` merge attribute does not select this plumbing command. A separate merge attribute must point at `merge-driver` using that command.

When so invoked on text-oriented content, a successful merge writes a pointer document for the three-way-merged object bytes to the designated output and stores those merged bytes in the local object store under the content-addressed nested layout.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned. This surface does not require those option tokens to appear in product output.

## `migrate`

Accepted after `git-orbulk` and after `git orbulk`. Nested mode tokens after `migrate` are `info`, `import`, and `export`. Both entry paths accept the same mode tokens and option tokens.

### Modes

- `info` — summarize counts and sizes by file type for the selected ref set. Does not rewrite history.
- `import` — rewrite matching Git blobs to pointers, store objects locally, and write tracking lines. Uses `--yes`.
- `export` — rewrite matching pointers to ordinary Git blobs and write excluded-pattern filter forms. Uses `--yes`.

### Options

- `--yes` — confirmation on `import` and `export`. `info` does not use this token.
- `--pointers=` — equals-attached pointer mode for `info`: `--pointers=follow`, `--pointers=ignore`, or `--pointers=no-follow`. Default `info` is `--pointers=follow`. This token is not `fsck`’s `--pointers`.
- `--include=` — equals-attached glob (no space). Selects matching paths for `import` and `export`. This token is not `fetch`’s `--include`, `pull`’s `--include`, `clone`’s `--include`, or `ls-files`’s `--include=`.
- `--include-ref=` — equals-attached ref (no space). Adds that local ref to the selected set.
- `--exclude-ref=` — equals-attached ref (no space). Removes that local ref from the selected set.
- `--everything` — select all local refs.
- `--fixup` — `import` converts only paths attributes already mark.
- `--no-rewrite` — `import` adds a new commit for listed positional paths and ignores ordinary rewrite options (`--include=`, `--everything`, `--include-ref=`).
- `--skip-fetch` — `import` does not refresh remotes first.

### Observable rules

`info` names extensions and presents separately identifiable count and size figures per type: a same-type size-only payload change moves the size figure while the count figure stays put. Default `info` (no `--include-ref=` and no `--everything`) summarizes the current branch and does not name a type unique to another local branch. `--include-ref=` and `--everything` expand that selected ref set.

Default `info` is `--pointers=follow`: it reports referenced object size. `--pointers=ignore` omits pointer types. `--pointers=no-follow` reports pointer-blob size, not referenced size.

`import` with `--include=` rewrites matching blobs to pointers on every rewritten commit (including ancestors), stores objects locally, and writes tracking lines as if `track` had been run (`filter`, `diff`, and `merge` as `lfs`), with non-executable `.gitattributes`. Unmatched paths stay ordinary blobs.

`--fixup` converts only paths attributes already mark, and does not add tracking for an unattributed sibling.

`--no-rewrite` adds a new commit whose parent is the old `HEAD`, converts only listed positional paths, and does not move other refs. Ordinary rewrite options on that invocation are ignored.

`export` with `--include=` restores included pointers to ordinary blobs and writes excluded-pattern filter forms (attributes lines that disable or unset the filter rather than enabling `lfs`) on rewritten commits, including ancestors that had no matching path. Unmatched pointers stay pointers. `.gitattributes` is not executable. `export` requires at least one `--include=` pathspec: missing `--include=` is non-zero relative to a successful `--include=` `export` and does not rewrite.

When the local object is gone, `export` fetches missing objects from default remote `origin` (`remote.origin.lfsurl`) and restores ordinary blob bytes. Without a reachable `origin`, that restore does not happen.

Default `import` rewrites only unpushed commits. `--include-ref=`, `--exclude-ref=`, and `--everything` rewrite trees on the chosen local refs; remote-tracking refs stay aligned with remotes.

Under an unreachable remote, default `import` fails before rewrite. `--skip-fetch` succeeds when objects are already local.

`migrate` refuses when `.gitattributes` is a symbolic link: `import` is non-zero relative to a regular-file `import` and does not rewrite; `info` is also non-zero.

Both `git-orbulk` `migrate` `info` and `git orbulk` `migrate` `info` succeed on a clean repository. Removing `git-orbulk` from `PATH` makes the Git-extension `migrate` `info` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, column order, and unit spelling are not pinned.

## `pointer`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens. Generate, check, and compare share this vocabulary.

### Options

- `--file=` — local file path, equals-attached (no space). Generate reads this path as the payload to hash. Ordinary and strict check read this path as the pointer document. Compare reads this path as the payload file.
- `--stdin` — read a pointer document from standard input. Ordinary and strict check use this as the pointer-document source. Compare uses this as the other pointer.
- `--check` — check whether the input is a valid pointer document. Requires exactly one of `--file=` or `--stdin`.
- `--strict` — with `--check`, also require the canonical encoding this build would write.
- `--no-strict` — the non-strict check flag. Combining `--strict` and `--no-strict` is invalid.
- `--pointer=` — compare-pointer file, equals-attached path (no space). Compare supplies the other pointer from this path. Combining `--check` with `--pointer=` is invalid.

### Observable rules

Generate is `pointer` plus `--file=` naming a local payload file. Both the Git-extension entry and the direct binary accept that form.

Ordinary check is `--check` plus exactly one of `--file=` (pointer document) or `--stdin`. Strict check is the same plus `--strict`.

Compare is `--file=` naming a payload file plus either `--pointer=` naming the other pointer file or `--stdin` carrying the other pointer.

These check invocations are invalid and fail distinguishably from a successful check of the same document: `--check` with neither `--file=` nor `--stdin`; `--check` with both `--file=` and `--stdin`; `--check` with `--file=` plus `--pointer=`; `--check` with `--file=` plus both `--strict` and `--no-strict`.

A successful generate or check exits 0. Numeric failure codes beyond zero versus non-zero, and banner wording, are not pinned.

## `post-checkout`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same arguments. Git also invokes this plumbing entry as the `post-checkout` hook.

`post-checkout` takes three positional arguments. It has no option tokens in this contract.

### Observable rules

The three arguments after the subcommand are the previous revision object id, the new revision object id, and a flag token that is `0` or `1`. Both the Git-extension entry and the direct binary accept that form.

When the flag token is `0`, `post-checkout` re-applies read-only permissions on the broader working-copy set of unlocked lockable paths. A non-lockable control path stays writable.

When the previous revision object id is forty `0` characters and the flag token is `1`, `post-checkout` likewise re-applies read-only on that broader unlocked lockable set. A non-lockable control path stays writable.

When the flag token is `1` and both revision object ids are ordinary (non-zero) commits, `post-checkout` re-applies read-only only on lockable paths that changed between those revisions. An unchanged unlocked lockable sibling stays writable if it was already writable.

A lockable path the local user currently holds a lock for stays writable through this scan.

Removing `git-orbulk` from `PATH` makes the Git-extension `post-checkout` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, and banner wording, are not pinned.

## `post-merge`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same arguments. Git also invokes this plumbing entry as the `post-merge` hook.

`post-merge` takes one positional argument. It has no option tokens in this contract.

### Observable rules

The argument after the subcommand is the token `0`. Both the Git-extension entry and the direct binary accept that form.

`post-merge` `0` re-applies read-only permissions on the broader working-copy set of unlocked lockable paths, including lockable paths the merge did not touch. A non-lockable control path stays writable.

A lockable path the local user currently holds a lock for stays writable through this scan.

Removing `git-orbulk` from `PATH` makes the Git-extension `post-merge` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, and banner wording, are not pinned.

## `pre-push`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens. Git also invokes this plumbing entry as the `pre-push` hook.

### Options

- `--dry-run` — identify the pending set and do not PUT those bytes. This token is not `push`’s `--dry-run`, `fetch`’s `--dry-run`, or `track`’s `--dry-run`.

### Observable rules

`pre-push` reads Git pre-push lines from standard input. For a non-delete update it uploads objects required by that commit range. A delete update does not upload.

`pre-push` `--dry-run` identifies the pending set and does not PUT those bytes. The identification of one pending set is stable and distinguishable from a different pending set and from a no-pending run. Wording, layout, and designation form are not pinned.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `prune`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--dry-run` — report prune candidates without deleting them. This token is not `fetch`’s `--dry-run`, `track`’s `--dry-run`, `push`’s `--dry-run`, or `pre-push`’s `--dry-run`.
- `--force` — delete objects needed by current checkouts that default prune keeps, when those objects are not unpushed. This token is not `install` / `uninstall` / `update`’s `--force` or `unlock`’s `--force`.
- `--recent` — drop the recentness window as a retention root while still keeping the current checkout. This token is not `fetch`’s `--recent`.
- `--verify-remote` — consult the endpoint before deleting a prune candidate.
- `--verify-unreachable` — extend that remote verification to unreachable local objects.
- `--when-unverified=` — equals-attached halt or continue (`--when-unverified=halt` or `--when-unverified=continue`). Selects retention versus deletion when remote verification fails.
- `--verbose` — reporting distinguishable from default prune. Exact wording is not pinned. This token is not `track`’s `--verbose`.

### Observable rules

Default `prune` deletes a local object that is only on an old, pushed, non-recent commit, and keeps the current-checkout object.

Retention roots are the current checkout, stashes, other worktree checkouts, unpushed commits, and the recentness window from `lfs.fetchrecentrefsdays`, `lfs.fetchrecentcommitsdays`, and `lfs.fetchrecentalways`. The reflog is not a retention root: an object only on an orphaned commit is deleted.

An unpushed object is kept, including when the endpoint already holds those bytes.

`--dry-run` leaves candidates in the store and writes a non-empty caller-visible report. Live `prune` of the same layout deletes those candidates. Wording is not pinned.

`--force` deletes a pushed current-checkout object that default `prune` keeps, and still deletes a pushed stale object. `--force` still keeps an unpushed object, including when the endpoint already holds those bytes.

`--recent` deletes a recent other-branch tip that default `prune` keeps under a covering recentness window, and keeps the current checkout. `--force` on that same layout deletes both the other-branch tip and the current checkout.

Configured exclude is `lfs.fetchexclude`. A matched pushed path is deleted even when it is the current checkout; an unmatched current-checkout path is kept. A matched unpushed path and a matched stashed object are kept. A matched path retained only by another worktree is deleted under exclude; without exclude, that worktree checkout keeps it.

`--verify-remote` with `--when-unverified=halt`: when every candidate verifies on the endpoint, those candidates are deleted and the current checkout remains. When at least one candidate fails remote verification, every prune candidate from that run remains.

`lfs.pruneverifyremotealways` set to `true` makes `prune` consult the endpoint as `--verify-remote` does, including when `--verify-remote` is omitted. With that SET and `--when-unverified=halt`, an unverified stale object remains. Unset, default `prune` deletes that same stale object.

`--verify-remote` with `--when-unverified=continue`: only candidates the endpoint holds are deleted; candidates that fail verification remain, and the current checkout remains.

`--verify-remote` `--verify-unreachable` with `--when-unverified=halt`: when an unreachable object fails remote verification, reachable prune candidates of that same run also remain. Without `--verify-unreachable`, an unreachable object is deleted even under halt when the reachable candidates all verify.

`fetch` `--prune` after a successful fetch uses the same retention as live `prune`: it deletes a stale pushed object and keeps a stashed object. `fetch` without `--prune` leaves that stale object. That `fetch` token is not this porcelain command.

`lfs.storage` relocates the store root. `prune` still deletes a stale pushed object and keeps the current checkout under that root. When repositories share that root, `prune` applies the invoked repository’s retention: an object retained only as another repository’s current checkout is deleted when `prune` runs in a repository that does not retain it, and is kept when `prune` runs in the repository that does.

Removing `git-orbulk` from `PATH` makes the Git-extension `prune` path fail with a non-zero exit and leaves the local store unchanged.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, and verbose/dry-run layout are not pinned.

## `pull`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--include` — following path argument. Replaces configured include (`lfs.fetchinclude`). Only matching paths are fetched and materialized.

### Observable rules

`pull` is fetch for the current ref plus checkout: it populates the local store and replaces pointer placeholders with object bytes. Fetch alone leaves working-tree bytes unchanged. `pull` does not fetch another branch’s unique object.

Configured include is `lfs.fetchinclude`. Configured exclude is `lfs.fetchexclude`. CLI `--include` replaces configured include. Configured exclude skips the matching path: that path stays a pointer and is not fetched.

An unreachable endpoint or a rejected-credentials endpoint fails and does not materialize working-tree bytes. Removing `git-orbulk` from `PATH` makes the Git-extension `pull` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `push`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--object-id` — upload a named object by digest. The following arguments are a remote name and an object digest. Combined with `--stdin`, the listed oids replace argv digests.
- `--all` — with a given ref, upload objects reachable from that ref’s history, including objects the default Git range skips; with no refs, upload the reachable set of all local refs and omit a remote-tracking-only object. This token is not `fetch`’s `--all`.
- `--stdin` — replace argv refs with the listed refs (or, with `--object-id`, listed oids) from standard input. This token is not `pointer`’s `--stdin` or `fetch`’s `--stdin`.
- `--dry-run` — identify the pending set and do not PUT those bytes. This token is not `fetch`’s `--dry-run`, `track`’s `--dry-run`, or `pre-push`’s `--dry-run`.

### Observable rules

Default `push` of a given ref uploads pending objects for that ref’s Git range (objects not already referenced by the local clone of that remote) and does not upload another local ref’s object.

`push` `--all` of a given ref uploads reachable history the default Git range skips. `push` `--all` with no refs uploads the reachable set of all local refs and omits a remote-tracking-only object.

`push` `--stdin` replaces argv refs with the listed refs.

`push` `--object-id` followed by a remote name and an object digest contacts the upload endpoint for that object, including when download and upload use different endpoints. That listed oid is uploaded even when the default Git range would skip it. `push` `--object-id` `--stdin` uploads each listed oid.

`push` `--dry-run` identifies the pending set and does not PUT those bytes. The identification of one pending set is stable and distinguishable from a different pending set and from a no-pending run. Wording, layout, and designation form are not pinned.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `smudge`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens. Git also invokes this plumbing entry as the `lfs` smudge filter.

### Options

- `--skip` — write the pointer document through without downloading or replacing it with object bytes. This token is not `install`’s `--skip-smudge`.

### Observable rules

Git supplies blob bytes on standard input. Ordinary `smudge` (no `--skip`) replaces a recognized pointer with object bytes from the local store or a download. `smudge` `--skip` writes that pointer through unchanged: standard output is the pointer document, not the object bytes, even when those bytes are already in the local store.

When the object is absent and no endpoint is reachable, ordinary `smudge` fails. `smudge` `--skip` of the same pointer succeeds and still writes the pointer through.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned.

## `status`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--porcelain` — scripting listing of index/HEAD and working-tree/index only. Combined with `--json`, the remainder after stripping named paths matches `--porcelain` alone and is distinguishable from `--json` alone.
- `--json` — machine-readable listing of index/HEAD and working-tree/index only. Names VCS Orbulk-related paths and omits ordinary Git paths that the default human listing and `--porcelain` still name. Field names and layout are not pinned. This token is not `track`’s `--json`, `fetch`’s `--json`, `lock`’s `--json`, `locks`’s `--json`, or `ls-files`’s `--json`.

### Observable rules

Default `status` (no scripting option) lists unpushed VCS Orbulk paths — objects reachable from the current ref but not from the current branch’s remote-tracking ref — plus index/HEAD and working-tree/index differences. The unpushed listing names only VCS Orbulk-related paths. When the remote-tracking ref has caught up with the current ref, those unpushed paths are omitted. One default human listing may name unpushed Orbulk paths and a staged Orbulk path together.

`--porcelain` and `--json` cover the index/HEAD and working-tree/index listings only: they name a staged uncommitted Orbulk path and an unstaged working-tree Orbulk edit, and they omit the unpushed set that the default human listing names.

Of the index/HEAD and working-tree/index listings, the default human listing and `--porcelain` name ordinary Git paths that differ in those slots as well as VCS Orbulk-related ones; `--json` names only VCS Orbulk-related paths.

When both `--porcelain` and `--json` are requested, `status` prefers `--porcelain`: after stripping named paths, the combined remainder equals `--porcelain` alone and is distinguishable from `--json` alone.

`status` in a bare repository fails and is distinguishable from a work-tree success. Removing `git-orbulk` from `PATH` makes the Git-extension `status` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, banner wording, and JSON field names are not pinned.

## `track`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--no-excluded` — listing mode that still names tracked pattern text and omits excluded-pattern text (attributes lines that disable or unset the filter rather than enabling `lfs`).
- `--json` — machine-readable listing mode. Combining `--json` with pattern arguments is invalid: the command fails and does not write `.gitattributes`. Field names and layout are not pinned.
- `--filename` — treat arguments as literal filenames rather than globs. A name that contains glob metacharacters enables `lfs` on that exact path and does not enable `lfs` on a different path that the same text would match as a glob.
- `--lockable` — mark the `lockable` attribute while still writing the ordinary `lfs` enable roles (`filter`, `diff`, and `merge` as `lfs`). Ordinary track without this token does not mark `lockable`.
- `--not-lockable` — clear the `lockable` attribute and keep the ordinary `lfs` filter enablement.
- `--no-modify-attrs` — dirty matching previously Git-tracked index entries without rewriting `.gitattributes`.
- `--dry-run` — report the intended pattern change without creating or rewriting `.gitattributes`.
- `--verbose` — still write the attribute rule (unlike `--dry-run`). When matching previously Git-tracked files exist, the report names those files and is distinguishable from the same track without `--verbose`. Exact wording is not pinned.

### Observable rules

`track` with one or more pattern arguments appends those pattern texts to `.gitattributes` (it does not expand a glob into matching filenames). Ordinary track writes `filter`, `diff`, and `merge` as `lfs` and does not enable Git text conversion as `lfs`. Unrelated existing attribute lines remain. The command does not create a Git commit.

`track` with no pattern arguments lists currently tracked pattern text. When excluded-pattern lines are also present, the default listing surfaces that excluded text in a portion distinct from the tracked patterns.

`track` outside a repository fails and is distinguishable from an in-repository success of the same pattern. It does not create `.gitattributes`. Removing `git-orbulk` from `PATH` makes the Git-extension `track` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned. Banner wording and JSON field names are not pinned.

## `uninstall`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--skip-repo` — unset `filter.lfs.clean`, `filter.lfs.smudge`, and `filter.lfs.process` in the chosen Git-config scope and leave the four hook files `pre-push`, `post-checkout`, `post-commit`, and `post-merge` in place.
- `--local` — unset those three `lfs` filter keys in repository-local Git config and leave global values unchanged.
- `--file=` — unset those three `lfs` filter keys only in the named Git-config file (equals-attached path, no space).

### Observable rules

Default uninstall (no scope option) reverses filters in global scope. An in-repository uninstall that is not given `--skip-repo` also removes the four hook files, honoring `core.hooksPath` when that path is the one in use. Outside a repository, uninstall still reverses the claimed non-repository filters and does not create a hooks directory.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero are not pinned. Filter argv, hook-script text, and banner wording are not pinned.

## `unlock`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--id=` — equals-attached lock id. Removes only that lock and leaves another lock on the same endpoint held. This token is not `locks`’s `--id=`.
- `--force` — skip the local clean-status check and still request the server-side unlock, including of a foreign lock when the endpoint permits it. This token is not `install` / `uninstall` / `update`’s hook-overwrite `--force`.
- `--remote` — following remote name. Targets that endpoint’s locks and does not clear a lock held on a different named remote.

### Observable rules

`unlock` removes a lock by path or by `--id=` (exactly one of those two selectors). Unlock by path removes the server lock; a later live `locks` listing from another repository on the same endpoint omits that path.

Unlock with both a path and `--id=`, or with neither, is invalid: the command fails and the lock remains.

Unlock by path without `--force` fails when that path has uncommitted working-tree changes, or when the path is missing from the working tree so a status check cannot run; the server lock remains. The clean-status check is the unlocked path: an unrelated dirty path does not block unlock of a clean locked path. `--force` skips that check and still unlocks. Unlock by `--id=` does not apply that local clean-status check, so a dirty path or a path missing from the working tree still proceeds to the server request without `--force`.

`--force` asks the server to drop a foreign lock when the endpoint permits it. Unlock without `--force` leaves a foreign lock held.

`--remote` followed by a remote name (including `origin`) unlocks on that remote’s locking endpoint and leaves a lock on a sibling remote held.

`unlock` fails when the endpoint lacks locking support and when authentication fails. Removing `git-orbulk` from `PATH` makes the Git-extension `unlock` path fail with a non-zero exit.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero and banner wording are not pinned.

## `untrack`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same arguments.

`untrack` takes pattern arguments. It has no option tokens in this contract.

### Observable rules

`untrack` with a pattern removes matching lines that enable the `lfs` filter for that pattern. Other tracked patterns remain. Unrelated non-lfs attribute lines remain. The command does not write excluded-pattern lines (Git negation or unset forms of the filter attribute).

The command does not create a Git commit. A successful in-repository run that removed a matching enable line leaves `.gitattributes` as an uncommitted change.

`untrack` outside a repository fails and is distinguishable from an in-repository success of the same pattern. It does not create `.gitattributes`.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, and banner wording, are not pinned.

## `update`

Accepted after `git-orbulk` and after `git orbulk`. Both entry paths accept the same option tokens.

### Options

- `--force` — overwrite a foreign hook body with the current standard body for that hook type.
- `--manual` — when a foreign hook body would block automatic update, leave that file unchanged and emit caller-visible hook-integration guidance. That guidance is distinguishable from empty output, from an unknown-option rejection, and from a no-conflict success or a filter-only success that says nothing about integrating hooks. Exact wording is not pinned.

### Observable rules

With neither option, `update` requires a repository. For each of `pre-push`, `post-checkout`, `post-commit`, and `post-merge`: a missing or empty hook file is written as the current standard body; an already-current standard body is left unchanged; a foreign body is left unchanged and the command fails.

`update` outside a repository fails and does not modify filters or hooks.

A successful run exits 0. Numeric failure codes beyond zero versus non-zero, hook-script text, and banner wording are not pinned.

