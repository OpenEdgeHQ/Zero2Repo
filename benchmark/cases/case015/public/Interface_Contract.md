### Product overview

**oggrepack** is a command-line tool that losslessly recompresses Ogg Vorbis and Ogg Opus files. A caller compresses a seekable input to a oggrepack archive and later expands that archive; the expanded file is byte-identical to the original. The product detects the codec from the input.

The first-time path is: invoke `oggrepack` with the compress verb, an Ogg Vorbis or Ogg Opus file, and a destination path; then invoke it with the expand verb on that archive and a destination path; compare the recovered bytes with the original. Batch mode processes many paths in one invocation. Optional progress writes to standard error.

The finished product is one compiled **C99** executable named `oggrepack`. It uses only the C and math libraries at runtime. There is no library API in this product's public contract, no importable package, and no wire protocol. Input and output must be seekable files. Standard input / standard output pipes are not a supported compress or expand path.

Documented execution is Linux x86_64. Hardware is CPU-only. A git checkout is built with `./bootstrap`, then `./configure`, then `make`.

### Shape of the public surface

The public surface is a **CLI**. Callers spawn the `oggrepack` binary with a caller-controlled argument vector, working directory, standard streams, and environment, then observe exit status, standard streams, and destination files.

**Binary.** The Autotools `bin_PROGRAMS` artifact is `oggrepack` at the built repository root. Direct invocation is that executable followed by options, then a verb, then the paths that verb requires.

**Verbs.** The finite verb set is exactly `e` (compress), `d` (expand), `dump`, and `pages`. Unknown verbs are usage errors.

**Options.** Options precede the verb. The tokens this surface publishes are:

- `-h` / `--help` — usage on standard output, exit `0`
- `-v` / `--version` — identity on standard output, exit `0`
- `-b` / `--batch` — every remaining argument after the verb is an input path; destinations are derived
- `-j` / `--jobs` — how many files run at once; `--jobs` requires a positive integer with no sign and no trailing text. Equals-attached form (a single argument such as `--jobs=1`) is accepted
- `-p` / `--progress` — opt-in progress on standard error
- `--progress-lines` — progress as separate log lines
- `--no-mmap` — accepted on compress and expand; compress with and without that option on the same input and effort writes byte-identical archives
- `-1` … `-9` — effort on compress; the last effort option on the command line applies; default is `-9`. There is no effort 0: a lone `-0` is an unknown option.

Unknown options are usage errors.

**Environment.** The product honors these environment variables:

- `ORP_MEMCAP` — memory cap override in MiB; `0` disables it. A non-empty value that is not a non-negative integer is a usage error. The numeric default when unset is not pinned.
- `ORP_SIMD` — mixer-kernel request on x86. Legal tokens are exactly `scalar`, `sse2`, and `avx2`. The default prefers AVX2, then SSE2, then the portable kernel. An unsupported or unbuilt request is a usage error. Bit-identical archives and lossless expands must not depend on which valid kernel ran.

**Inspection.** `dump` takes exactly one archive path. `pages` takes exactly one Ogg file path. On a valid archive this product wrote, `dump` exits `0` and writes a layout description to standard output. On that standard output, a dedicated codec-mode field — not the archive path, not a byte size, not a leftover that varies with the file — answers whether the archive is Opus or Vorbis: two successful Opus archives share one payload of that field, and a successful Vorbis archive of a different input has a distinguishable payload of the same field, independent of path and size. The payload may be a number or a hex value. Exact wording is the implementer's. On that same dump standard output, a dedicated stored-stage field — not the archive path, not a byte size, not a leftover that varies with the file — answers the encoding stage stored for a Vorbis archive: a Vorbis archive made at effort `-1` and a Vorbis archive made at effort `-3` of the same input have distinguishable payloads of that field, independent of path and size. Dump of archives made at effort 4 through 9 of the same Vorbis input need not distinguish those efforts. The stored-stage payload may be a number or a hex value. On a valid Ogg Vorbis or Ogg Opus file, `pages` exits `0` and lists every page. On that standard output, each listed page carries a dedicated reconstruction-status field — not the file path, not a byte size, not a leftover that varies with the file — whose two payloads are success and mismatch. Success means the stored page bytes equal the RFC 3533 reconstruction of that page's parsed header and body, including the CRC-32 computed with the checksum field treated as zero; mismatch means they do not. Well-formed files carry the success payload on every listed page. A still-parseable same-codec sibling that differs only by one page's stored RFC 3533 checksum not matching that CRC still exits `0` and lists; that page carries the mismatch payload. The distinction is independent of path and size. Exact wording is the implementer's. `pages` on a valid file does not modify the file.

There is no product configuration-file format.

### Naming conventions

**Product and executable.** The product identity and the executable basename are both `oggrepack`. Version identity names that product as a whole token.

**Verbs.** Lowercase tokens `e`, `d`, `dump`, `pages`.

**Option stems.** Help names the stems `batch`, `jobs`, `progress`, `progress-lines`, and `no-mmap` as whole tokens (with or without leading dashes). Effort options are `-1` through `-9`.

**Mixer kernels.** The finite legal `ORP_SIMD` set, and the kernel names version stdout may report as whole tokens, are `scalar`, `sse2`, and `avx2`.

**Batch archives.** On Unix and Linux, batch compress names the destination by appending `.orp` to the input path. Batch expand strips a trailing `.orp`; if the input name has no `.orp` suffix, expand appends `.out`.

**Exit-status class digits.** Help names the five classes as whole tokens `0`, `1`, `2`, `3`, and `4`.

### Global observables an implementer must reproduce

**Process exits.**

- `0` — success
- `1` — refusal (malformed, unsupported, or unrecognized input). Non-empty standard error. The diagnostic names the offending input.
- `2` — usage error. Non-empty standard error. No archive is written (no new file named by appending `.orp`).
- `3` — file-access error (a named path cannot be opened, read, or written, or the input and output name the same file). Non-empty standard error. Standard error identifies that the path could not be opened or could not be created (a remainder after stripping the path, not the path alone).
- `4` — internal error. Reserved for product bugs; illegal caller input must not be required to produce it. Expand of a truncated archive stays in exit `0` or `1`; if it exits `0`, the destination matches the original source of that archive. Expand of an archive whose interior bytes are flipped stays in exit `0` or `1`.

Diagnostics for refusal, usage error, and file-access error go to standard error. Successful compress and expand write no requirement on standard output.

**Help.** `-h` and `--help` exit `0` and write a non-empty usage summary on standard output that names the four verbs, the effort range `-1` … `-9` with default `-9`, `batch`, `jobs`, `progress`, `progress-lines`, `no-mmap`, and the five status-class digits. Help stdout is distinguishable from version stdout.

**Version.** `-v` and `--version` exit `0` and write non-empty identity on standard output. That identity names `oggrepack`, a version, the build host, mixer kernel(s) from `scalar` / `sse2` / `avx2`, and a dedicated field — not usage, not the shared product banner, not license or copyright prose — for whether Ogg Opus encode and decode are compiled in. Help and version stdout differ.

**Compress and expand.** `e` with a valid Ogg Vorbis or Ogg Opus input and a distinct destination path exits `0` and writes that destination; destination bytes are not a copy of the source. `d` of a valid archive from this product generation and a distinct destination path exits `0` and restores the original bytes. A chained Ogg Vorbis file of two or more links, and a chained family-0 Ogg Opus file whose every link is a supported mono or stereo stream (including concatenating stereo CELT, mono SILK, and mono hybrid, and a two-link SILK-then-CELT file), each compress with exit `0`, write a destination that is not a copy of the source, and expand restores the original chained bytes. A Vorbis file that ends on a complete packet and lacks the end-of-stream flag on the last page, including when the file is a chain and when complete copies are prefixed before the copy that lacks the flag, still compresses with exit `0` after that last page's checksum is corrected as RFC 3533 specifies with the checksum field treated as zero; expand restores those original bytes. A chain of two Vorbis links that each merge later header packets onto the same page as that link's first audio packet still compresses with exit `0` and expand restores the original bytes. On a supported family-0 Ogg Opus file, a page after a finished end-of-stream page of the same stream with no new beginning-of-stream, and a packet that continues onto a following page that is not marked as a continuation, each compress with exit `0`; expand of that archive restores those constructed bytes. Codec detection for compress uses the first Ogg page. The same input, same effort, and same options, compressed twice (including once with `--no-mmap` and once without), produce byte-identical archives, for either codec and at any effort. Accepted mixer kernels produce bit-identical archives of the same input, for either codec and at any effort. Expand needs nothing but the archive: after compress, with the input and every other file, process, or shared-memory object compress left on the host removed, a copy of the archive under another name, in another working directory and with another home directory, expands to the original bytes.

`e` and `d` each require both an input path and an output path. One path or none is a usage error.

**Usage errors (exit `2`).** No arguments; unknown verb; unknown option; `dump` or `pages` with other than exactly one path; `-b` / `--batch` without at least one file path after `e` or `d`; combining `-b` / `--batch` with `dump`, `pages`, or any verb other than `e` or `d` even when a file path is present (including an unknown verb after `-b` / `--batch`); `--jobs=0`, a leading sign (for example `--jobs=+1`), or trailing text after a digit prefix; non-empty `ORP_MEMCAP` that is not a non-negative integer (including on version); `ORP_SIMD` set to a token other than `scalar`, `sse2`, or `avx2`, or to an unbuilt/unsupported kernel. `--jobs=1` is not a usage error. `ORP_MEMCAP` set to `0` is not a usage error. `ORP_SIMD=scalar` on version is not a usage error.

**File-access errors (exit `3`).** A missing compress input; a missing directory on the output path; a missing `dump` or `pages` path; a non-seekable operand. If the input path and the output path name the same file (same path string, or two paths that resolve to the same existing file), compress and expand are file-access errors and leave the input bytes unchanged.

**Refusals (exit `1`).** Compress of a non-Ogg file; compress of a file whose first page is not a Vorbis identification header and not OpusHead; compress of a oggrepack archive; expand of a raw `.ogg` / non-archive; expand of an archive whose generation identifier is not the generation this product writes (both an older generation and a newer generation); the generation identifier is its own whole-byte field with the same value in every archive this product writes, whatever the input, codec, or effort. Leftover tokens on standard error after stripping paths and sizes distinguish expand-of-Ogg from compress-of-archive, and distinguish a foreign-generation expand from expand of a non-archive. Unsupported Vorbis floor type 0, codebook lookup type 2, and a sparse empty codebook; Opus channel mapping family other than 0, or channel count other than 1 or 2 under family 0, including on every link of a chained Opus file and not only the first page used for codec detection; compress of Ogg pages that fail RFC 3533 CRC-32. On compress of an Ogg Vorbis file, a page that follows a finished end-of-stream page of the same stream with no new beginning-of-stream, and a packet that continues onto a following page that is not marked as a continuation, are each refused. Trailing bytes after the last Ogg page that are not a following chained link are refused on both codecs. On compress of a supported family-0 Ogg Opus file, those same two page-sequence constructions are not refusals (they exit `0` as under Compress and expand). An incomplete final packet (the file ends in the middle of a packet) is refused on compress of Ogg Vorbis, of a supported family-0 Ogg Opus file, and of a later link of a chain of either codec. `dump` of a file that is not a `oggrepack` archive of this generation is refused, including a valid Ogg file, a random non-Ogg file, and an archive whose generation identifier was rewritten older or newer than the generation this product writes. `pages` of a file that is not Ogg, including an archive of this product, is refused. A refusal diagnostic names the offending input. A missing file is `3`, not `1`.

**Batch.** `-b` / `--batch` followed by `e` or `d` and one or more input paths. Destinations are derived (`.orp` on Unix/Linux compress). Remaining files still run after a refusal or file-access error on one file. The process exit status is the highest nonzero status reported by any file. Effort and `--no-mmap` apply to the whole batch: `--no-mmap` `-1` `-b` `e` of a valid Vorbis member and a family-0 Opus member exits `0` with each destination not a copy of its source, and `--no-mmap` `-b` `d` of those archives restores both originals. Larger inputs start first. On batch compress with `--jobs=1`, of two non-Ogg files of different sizes that both refuse, standard error carries the larger input path before the smaller input path. When at least one file fails, standard error writes a dedicated mixed-failure summary field — not the input path, not a per-file size or offset, not leftover after stripping paths and sizes, not a per-file diagnostic that varies with the file — whose two payloads are how many members failed and how many paths were attempted. That field is present with a nonzero failed-count payload on mixed failure; an all-success run of the same operands does not answer a nonzero failed-file count on that field; two mixed runs that differ only in how many members failed have distinguishable payloads of the failed-count half; two mixed runs that differ only in how many files were attempted have distinguishable payloads of the attempted-count half; each payload may be a number; mixed-versus-all-success full-text, leftover integers after a path or size is stripped, or mixed-to-mixed full-text of different members is not the count-answer. Batch mode with progress on always uses line-oriented progress and labels those lines with the input filename so two files in one batch are distinguishable. On batch compress with `--progress` and `--jobs=1`, two input names appear on distinct newline records. Batch `--progress` `--jobs=2` of three named files includes those names on standard error and a completion indication. Batch expand with `--progress` labels newline records with the archive names. Batch accepts `-p` and `--progress-lines` the same way.

**Progress.** Off by default. Enabling progress does not change archive bytes: at any effort, for either codec, with `-p`, `--progress`, or `--progress-lines`, and for batch compress with progress against single-file compress without it. A completion indication is a progress update whose text carries the literal 100%. Compress or expand of a valid file with `--progress` and `-p` omitted writes no such update; the same invocation with `--progress` or `-p` writes at least one. Family-0 Opus compress with `--progress` and expand with `--progress` of that archive each reach at least one such indication. `--progress-lines` by itself is an opt-in: it writes progress as newline-oriented records; a newline-only split of standard error matches a split that also cuts on carriage return, and there is more than one nonempty newline record. Batch mode with progress on always uses that line-oriented form and labels those lines with the input filename so two files in one batch are distinguishable. On Vorbis compress with `--progress`, effort `-1` writes exactly one completion indication; effort `-9` of the same input writes two or more. A progress run is the output up to and including one completion indication; the count of those indications is the observable; other label wording is the implementer's. A refusal with progress on still exits `1`, still writes the refusal diagnostic that names the offending input, and still delivers no usable destination; progress being on does not change that status or hide the diagnostic.

**Effort.** Each of `-1` through `-9` is accepted on compress. Omitting effort on compress uses `-9`. Expand of an archive produced at any effort in 1 through 9 recovers the original bytes. Effort does not change expand's recovered bytes.

**Recompression minimum.** At effort `-9`, the archive of an ordinary accepted file is strictly smaller than that file. An ordinary file is a single-link Ogg Vorbis file, or a single-link family-0 mono or stereo Ogg Opus file, carrying encoder-produced audio: identification, comment, and (for Vorbis) setup headers, then audio packets without added padding, ending on an end-of-stream page; how packets are laid out on valid pages, and the comment text, may be anything valid. At every effort the archive is a recompression, not a stored copy: counted by bytes, most of the input's audio packets of at least 16 bytes do not appear byte-for-byte anywhere in the archive. Wrapping, masking, splitting, or reordering the input without recompressing it does not meet this minimum. Typical size percentages beyond this minimum are not scored.

## `usage`

Help is the public entry.

### Public entry

`-h` and `--help` write a usage summary to standard output and exit `0`. Help stdout is distinguishable from version stdout (`-v` / `--version`).

The usage summary names the four verbs `e`, `d`, `dump`, and `pages`; the effort range `-1` … `-9` with default `-9`; the option stems `batch`, `jobs`, `progress`, `progress-lines`, and `no-mmap`; and the five exit-status classes `0`, `1`, `2`, `3`, and `4`.

An empty argument list, an unknown verb, an unknown option, a verb given the wrong number of paths, `-b` / `--batch` without at least one file path after `e` or `d`, a `--jobs` value that is not a positive integer with no sign and no trailing text, a non-empty `ORP_MEMCAP` that is not a non-negative integer, and an illegal `ORP_SIMD` token are usage errors: exit `2`, non-empty standard error, and no new archive named by appending `.orp`.

## `version`

Version identity is the public entry.

### Public entry

`-v` and `--version` write identity to standard output and exit `0`. Either flag produces non-empty stdout. That text is distinguishable from help (`-h` / `--help`): the two streams are not identical.

### Identity

Version stdout names the product `oggrepack` as a whole token, a version (a release identifier; dotted numeric form is not required), the build host, and which mixer kernel was built and which was dispatched. Mixer kernel names that appear as whole tokens are from the finite set `scalar`, `sse2`, and `avx2`.

On version stdout, a dedicated identity field — not usage text, not the shared product banner, not license or copyright prose — answers whether Ogg Opus encode and decode are compiled into this binary. Present and absent are two distinguishable payloads of that same field. A codec-name substring in usage, banner, or license text is not that field.

### Environment

`ORP_SIMD` set to `scalar` on version is not a usage error: the process exits `0` and still writes identity. A token other than `scalar`, `sse2`, or `avx2` is a usage error (exit `2`, non-empty standard error). Requesting `sse2` or `avx2` when that kernel was not built or is not supported on this CPU and OS is a usage error of the same class.

A non-empty `ORP_MEMCAP` that is not a non-negative integer is a usage error even on version.

## `dump`

Accepted as a verb after `oggrepack`.

### Invocation

The caller supplies options, then `dump`, then exactly one path. Zero paths or two paths is a usage error: the process exits `2`, writes a non-empty diagnostic on standard error, and writes no new archive named by appending `.orp`.

A missing path is a file-access error (exit `3`, non-empty standard error). A path that is not a `oggrepack` archive of this product generation is a refusal (exit `1`, non-empty standard error).

On a valid archive this product wrote, `dump` exits `0` and writes a layout description to standard output. On that standard output, a dedicated codec-mode field — not the archive path, not a byte size, not a leftover that varies with the file — answers whether the archive is Opus or Vorbis: two successful Opus archives share one payload of that field, and a successful Vorbis archive of a different input has a distinguishable payload of the same field, independent of path and size. Opus archives whose inputs differ in page count, link count, channel count, duration, and OpusHead input sample rate, pre-skip, and output gain still share that payload, and no Vorbis archive carries it, including a Vorbis archive whose identification header names a 48 kHz rate. The payload may be a number or a hex value. On that same standard output, a dedicated stored-stage field — not the archive path, not a byte size, not a leftover that varies with the file — answers the encoding stage stored for a Vorbis archive: a Vorbis archive made at effort `-1` and a Vorbis archive made at effort `-3` of the same input have distinguishable payloads of that field, independent of path and size. Dump of archives made at effort 4 through 9 of the same Vorbis input need not distinguish those efforts. The stored-stage payload may be a number or a hex value. Exact wording is the implementer's.

## `pages`

Accepted as a verb after `oggrepack`.

### Invocation

The caller supplies options, then `pages`, then exactly one path. Zero paths or two paths is a usage error: the process exits `2`, writes a non-empty diagnostic on standard error, and writes no new archive named by appending `.orp`.

A missing path is a file-access error (exit `3`, non-empty standard error). A path that is not Ogg is a refusal (exit `1`, non-empty standard error).

On a valid Ogg Vorbis or Ogg Opus file, `pages` exits `0`, lists every page on standard output, and does not modify the file. On that standard output, each listed page carries a dedicated reconstruction-status field — not the file path, not a byte size, not a leftover that varies with the file — whose two payloads are success and mismatch. Success means the stored page bytes equal the RFC 3533 reconstruction of that page's parsed header and body, including the CRC-32 computed with the checksum field treated as zero; mismatch means they do not. Well-formed files carry the success payload on every listed page. A still-parseable same-codec sibling that differs only by one page's stored RFC 3533 checksum not matching that CRC still exits `0` and lists; that page carries the mismatch payload. The distinction is independent of path and size. Exact wording is the implementer's.
