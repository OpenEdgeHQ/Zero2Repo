# oggrepack — Full Product Requirements Document

## Product overview

**oggrepack** is a command-line tool that losslessly recompresses Ogg Vorbis and Ogg Opus files. A caller compresses a seekable input to a oggrepack archive and later expands that archive; the expanded file is byte-identical to the original. The product detects the codec from the input. Archives are typically smaller than the source `.ogg` or `.opus` file; the typical percentage is **not scored**. What is scored is a minimum (FP-04): at effort 9 the archive of an ordinary file is smaller than that file, and at no effort does an archive carry the file's audio packets as stored copies.

The first-time path is: invoke oggrepack with the compress verb, an Ogg Vorbis or Ogg Opus file, and a destination path; then invoke it with the expand verb on that archive and a destination path; compare the recovered bytes with the original. Batch mode processes many paths in one invocation. Optional progress writes to standard error. Releases are not backwards or forwards compatible until v2.0; expanding an archive whose format generation is not the one this product writes is refused.

This document specifies **user-observable behavior only**. Exact published flag spellings that an implementer must accept are named here only when a caller types them; internal construction is out of scope. Every feature point corresponds to behavior that exists in the finished product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **oggrepack** | The product: a command-line lossless recompressor for Ogg Vorbis and Ogg Opus. |
| **Compress** | The `e` verb: read a seekable Ogg Vorbis or Ogg Opus file and write a oggrepack archive. |
| **Expand** | The `d` verb: read a oggrepack archive and write the original Ogg bytes. |
| **Archive** | The file oggrepack writes on compress and reads on expand. On Unix and Linux, batch compress names it by appending `.orp` to the input path. |
| **Ogg Vorbis file** | A seekable Ogg bitstream whose first page carries a Vorbis identification header as defined by the Vorbis I specification. |
| **Ogg Opus file** | A seekable Ogg bitstream whose first page carries an OpusHead identification header as defined by RFC 7845. |
| **Link** | One logical bitstream in a chained Ogg file, beginning at a beginning-of-stream page and ending at the corresponding end-of-stream page (or at end of file when the final end-of-stream flag is absent but the last packet is complete — FP-06). |
| **Effort** | An integer from 1 through 9 selected with `-1` … `-9`. Higher values spend more encoder work. The default is 9. |
| **Batch** | The `-b` / `--batch` mode: every remaining argument after the verb is an input path; destinations are derived. |
| **Refusal** | Compress or expand does not succeed. The process exits with status 1 (unless a higher status from FP-01 applies). A diagnostic is written to standard error. No usable destination is delivered for that input. |
| **Usage error** | The command line cannot be interpreted. Exit status 2. No archive is written. |
| **File-access error** | A named path cannot be opened, read, or written, or the input and output name the same file. Exit status 3. |
| **Core capability** | A user-observable capability that reflects oggrepack’s design goal; acceptance must prove the real command, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

oggrepack is a **command-line program**. It is C99, uses only the C and math libraries at runtime, and is invoked as `oggrepack` with a verb and paths. There is no library API in this product’s public contract.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- The program itself: help, version, verbs, options, environment overrides, and the five exit-status classes (FP-01).
- Compress and expand of Ogg Vorbis, including packet padding, shortened packets, alternative floor subclass choices, comments, and determinism (FP-02).
- Compress and expand of Ogg Opus, including family-0 mono and stereo, extended frame headers, RFC 6716 padding, comments, and the packet-size caps (FP-03).
- Effort `-1` through `-9`, default `-9` (FP-04).
- Refusal of files that cannot be reproduced exactly, wrong-type inputs, and foreign archive generations (FP-05).
- Chained bitstreams, and Vorbis files that omit a final end-of-stream flag when they end on a complete packet (FP-06).
- Batch processing with derived names, larger inputs first, continuation after a refusal, and `--jobs` (FP-07).
- Opt-in progress on standard error (FP-08).
- The `dump` and `pages` inspection verbs (FP-09).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

Build, packaging, sanitizer and SIMD configure switches, Windows, Windows 95, and MS-DOS ports, and fuzzing are not feature points. They are not part of the product a first-time user must have.

## Non-functional constraints

- **Form factor:** A C99 command-line tool. No GPU, no accelerator, no runtime third-party libraries beyond the C and math libraries.
- **Host for this case:** Linux. Acceptance targets a Linux x86_64 host that can build the program from this repository (`./configure` then `make`; a git checkout runs `./bootstrap` first) and invoke the resulting binary on seekable files.
- **Hardware:** CPU-only. The mandatory profile is a CPU baseline that means the tool builds and runs on the host CPU. That profile does **not** license a negative control. Do not write a negative-control clause that disables the package under test, the compiler, or the C library.
- **I/O:** Input and output must be seekable files. Standard input / standard output pipes are not a supported compress or expand path.
- **Memory:** Supported hosts apply a per-process memory cap to reject unreasonable allocations. The environment variable `ORP_MEMCAP` overrides that cap in MiB; `0` disables it. A non-empty value that is not a non-negative integer is a usage error (FP-01). Sanitizer builds omit the cap. The numeric default when the variable is unset, whether a particular huge allocation is actually aborted, and the effect of a well-formed numeric override on allocations are host- and build-dependent and are **not scored**. Refusal of a malformed override is scored.
- **Mixer kernel:** On x86, `ORP_SIMD` may be `scalar`, `sse2`, or `avx2`. The default prefers AVX2, then SSE2, then the portable kernel. An unsupported or unbuilt request is a usage error. Which kernel is dispatched is reported by the version verb (FP-01). Bit-identical archives and lossless expands must not depend on which valid kernel ran, for either codec and at any effort; kernel choice is **not scored** beyond that identity and the usage-error path.
- **Mapping:** `--no-mmap` is accepted on compress and expand. Compress with and without that option on the same input and effort must write byte-identical archives, for either codec and at any effort (FP-02, FP-03). How the option is implemented is out of scope.
- **Portability of archives:** An archive written on one supported host expands on another supported host of this same product generation. Cross-host identity is the same format contract as a local expand; it is not a separate scored quantity. Expand therefore needs nothing but the archive: after compress, with the original input and every other file, process, or shared-memory object that compress left on the host removed, a copy of the archive under another name, in another working directory and with another home directory, expands to the original bytes (FP-02, FP-03).
- **Typical size:** Archives are typically 8–12% smaller than `.ogg` files and 3–8% smaller than `.opus` files. Those typical percentages are **not scored**. The scored size relationships are in FP-04: the effort scale; at effort 9, an ordinary file's archive is smaller than the file; and at no effort does an archive carry the input's audio packets as stored copies.
- **License:** GNU GPL version 3. Not a runtime behavior.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature. The mandatory `cpu_baseline` profile only means the tool runs on CPU; it does not license a negative control.

For every feature point:

- **Present:** Invoking the real `oggrepack` binary with the named verb, options, and seekable files produces the stated exit status, destination bytes, and standard-error distinction.
- **Absent / hollow:** A stub that copies the input to the output; a compressor that emits a smaller file that does not expand to the original bytes; a detector that always takes the Vorbis path; a batch that stops at the first refusal; progress that changes archive bytes.

Cheaper proxies (re-encoding audio, transcoding to another codec, storing a copy of the input inside a wrapper without actually recompressing, or skipping expand) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces lossless recompression.

## Non-goals

- Lossy transcoding, sample-accurate decode-and-re-encode that changes Ogg framing, or any expand that is not byte-identical to the original file.
- Ogg codecs other than Vorbis and Opus (Theora, Speex, Opus with channel mapping family other than 0, Vorbis floor type 0, codebook lookup type 2).
- Reading or writing non-seekable streams as the compress or expand operands.
- Backwards or forwards compatibility with archives from a different oggrepack generation before v2.0.
- Guaranteeing a particular wall-clock speed. Speed relationships across efforts are the implementer’s and are **not scored**.
- Windows Unicode paths, Windows 95, MS-DOS 8.3 names, and the DOS batch rule that expands Opus to `.opu` are out of scope. The product targets Linux.
- Build-time sanitizers, SIMD configure switches, and fuzzing.

---

## Feature points

### FP-01: Command invocation, verbs, help, version, and exit status

**Public entry:** The `oggrepack` program. The caller supplies options, then a verb, then the paths that verb requires. Verbs are exactly: `e` (compress), `d` (expand), `dump` (FP-09), and `pages` (FP-09). Options that this feature point itself interprets are help (`-h` / `--help`), version (`-v` / `--version`), and unknown tokens. Compress, expand, batch, progress, effort, and inspection behavior are specified in later feature points; this feature point is how a caller reaches them and how the process reports success or failure.

**Normal behavior:**

- Invoking help writes a usage summary to standard output and exits 0. The summary names the four verbs, the effort range `-1` … `-9` with default `-9`, batch, jobs, progress, progress-lines, and the no-mmap option. It also names the five exit-status classes below.
- Invoking version writes identity to standard output and exits 0. The identity is distinguishable from help: it names the product, a version, the build host, and which mixer kernel was built and which was dispatched. On version standard output, a dedicated identity field — not usage text, not the shared product banner, not license or copyright prose — answers whether Ogg Opus encode and decode are compiled into this binary; present and absent are two distinguishable payloads of that same field, independent of whether the codec name appears as a substring in usage, banner, or license text. Help names usage; version names build identity.
- Compress with a valid Ogg Vorbis or Ogg Opus input and a distinct destination path exits 0 and writes that destination (FP-02, FP-03). Expand with a valid archive from this product generation and a distinct destination path exits 0 and writes the original bytes.
- The five exit-status classes are: **0** success; **1** malformed, unsupported, or unrecognized input (a refusal); **2** usage error; **3** file-access error; **4** internal error. Status 4 is reserved for product bugs; illegal caller input must not be required to produce it, and it is **not scored** as an input-driven outcome.
- Diagnostics for refusal, usage error, and file-access error go to standard error. Successful compress and expand write no requirement on standard output.

**Boundary / error behavior:**

- No arguments is a usage error (exit 2). An unknown verb is a usage error. An unknown option is a usage error.
- Compress without both an input path and an output path is a usage error. Expand without both paths is a usage error. `dump` and `pages` without exactly one path are usage errors. Batch without at least one file path after a compress or expand verb is a usage error (FP-07).
- `--jobs` requires a positive integer with no sign and no trailing text. `--jobs=0`, a leading sign, or trailing text is a usage error.
- A missing input path, a missing directory on the output path, or an input that cannot be opened is a file-access error (exit 3). Standard error identifies that the path could not be opened or could not be created. The distinction from a refusal (exit 1) is the status: a well-formed command aimed at a file that is not there is 3, not 1.
- If the input path and the output path name the same file (same path string, or two paths that resolve to the same existing file), compress and expand are file-access errors. The input bytes are left unchanged.
- `ORP_MEMCAP` set to a non-empty value that is not a non-negative integer is a usage error. Invoking version with `ORP_SIMD` set to a value other than `scalar`, `sse2`, or `avx2`, or to a kernel that was not built or is not supported on this CPU and OS, is a usage error. Whether a huge allocation is aborted, and which well-formed numeric cap applies, are **not scored**.

**Verifiable oracle:**

- Success: help exits 0 and the usage text on standard output is distinguishable from version output; version exits 0 and names a version, a build host, and a mixer kernel, and a dedicated identity field on that output answers whether Ogg Opus encode and decode are compiled into this binary, with present and absent as two distinguishable payloads of that field, independent of a codec-name substring in usage, banner, or license text; a valid compress-then-expand pair on a short Vorbis file (FP-02) exits 0 both times; a missing input on compress exits 3 and is distinguishable by status from compress of a non-Ogg file (exit 1, FP-05); naming the same file as input and output exits 3 and leaves the file bytes unchanged; `--jobs=0` with batch exits 2; an unknown verb exits 2; an empty invocation exits 2; `ORP_MEMCAP` set to a non-integer such as `abc` with any verb exits 2; invoking version with `ORP_SIMD` set to a token other than `scalar`, `sse2`, or `avx2` exits 2.
- Failure / absence: help and version cannot be told apart; version identity is silent on whether Ogg Opus encode and decode are compiled in, or answers that only by a codec-name substring in usage, banner, or license text; a missing file exits 1; overwriting the input through the output path succeeds or truncates the input; `--jobs=0` is accepted; unknown verbs are treated as file names; a malformed memory-cap or mixer-kernel override is ignored.

---

### FP-02: Lossless Ogg Vorbis compress and expand

**Public entry:** `oggrepack e` with a seekable Ogg Vorbis input and a distinct output path; `oggrepack d` with a oggrepack archive produced from that input and a distinct output path. Codec detection for compress uses the first Ogg page. Expand detects a Vorbis archive from the archive header (not from an `.ogg` sniff). Effort (FP-04), refusals (FP-05), chaining (FP-06), batch (FP-07), and progress (FP-08) refine this path; this feature point is the single-file lossless round-trip.

**Normal behavior:**

- Compress of a valid Ogg Vorbis file writes an archive and exits 0. The archive is a different file from the input. Expand of that archive writes a file whose bytes are identical to the original input, and exits 0.
- Compress detects Vorbis from the first page of the input: the page is an Ogg page as defined by RFC 3533, and its first complete packet is a Vorbis identification header as defined by the Vorbis I specification. A file whose first page is OpusHead takes the Opus path (FP-03), not this one.
- The round-trip is **byte-identical**, including Ogg page framing, checksums, granule positions, serial numbers, packet contents, comment packets, and any padding bits that were in the original packets. A decode that merely yields the same PCM, or an Ogg file that plays the same but differs in framing, is not this product.
- The same input, same effort, and same options, compressed twice (including in two process invocations, and including once with `--no-mmap` and once without), produce byte-identical archives.
- Vorbis audio packets that carry extra padding beyond the coded payload, packets that are shorter than a canonical encoding of the same symbols, and packets that use an alternative floor subclass choice still compress and expand to the original bytes. A file that only differs from an accepted fixture by such a legal packet boundary still round-trips.
- Comment packets, including large comment packets, vendor strings, repeated text fields, and `METADATA_BLOCK_PICTURE` fields, are part of the original bytes and therefore part of the round-trip.
- Expand needs only the archive. After compress, with the input and every other file, process, or shared-memory object compress left on the host removed, a copy of the archive under another name, in another working directory and with another home directory, expands to the original bytes.
- Size versus the input is scored in FP-04 (at effort 9 an ordinary file's archive is smaller than the file; no effort stores the audio packets as copies), not on this feature point; effort-vs-effort size is also FP-04.

**Boundary / error behavior:**

- A file that is not Ogg, or whose first page is not a Vorbis identification header and not OpusHead, is refused (FP-05). Expand of a raw `.ogg` file is refused: expand requires a oggrepack archive.
- Compress of a oggrepack archive is refused: compress requires an Ogg Vorbis or Ogg Opus file.
- Vorbis floor type 0 and codebook lookup type 2, as defined by the Vorbis I specification, are unsupported: such a file is refused.
- Input and output must be seekable. A non-seekable operand fails as a file-access error rather than a silent truncation.
- Overwrite of the input through the output path is a file-access error (FP-01).

**Verifiable oracle:**

- Success: compress then expand of a short valid Ogg Vorbis file exits 0 both times and a byte-for-byte compare of the recovered file against the original reports identity; repeating compress at the same effort yields a second archive identical to the first, at effort 1 and at the default effort 9; `--no-mmap` on compress yields that same archive at both efforts; with the input and every other trace of compress removed from the host, a copy of the archive in a fresh working directory and home directory expands to the original bytes at effort 1 and effort 9; a file whose only change from an accepted Vorbis file is extra padding on an interior audio packet, or a shortened interior audio packet, still round-trips at both effort 1 and effort 9; a file whose comment packet is replaced by a larger well-formed Vorbis comment still round-trips; expand of the original `.ogg` (not an archive) exits 1.
- Failure / absence: expand writes PCM or a re-muxed Ogg file that is not byte-identical; two compressions of the same input differ; `--no-mmap` changes archive bytes; extra legal padding or a shortened packet is refused even though the original fixture is accepted; expand of an `.ogg` succeeds.

---

### FP-03: Lossless Ogg Opus compress and expand

**Public entry:** The same compress and expand verbs as FP-02, when the input is Ogg Opus. Compress detects Opus from the first Ogg page’s OpusHead packet as defined by RFC 7845. Expand detects an Opus archive from the archive header.

**Normal behavior:**

- Compress of a valid Ogg Opus file that this product supports writes an archive and exits 0. Expand of that archive writes a file byte-identical to the original input and exits 0.
- Supported streams are logical bitstreams with **channel mapping family 0** and **one or two channels** (mono or stereo), as those terms are used in RFC 7845. SILK, CELT, and hybrid packets that appear in such a stream are all in scope.
- Audio packets and the OpusHead packet are limited to **61,440 bytes**, the maximum Opus packet size in RFC 7845 section 6. OpusTags comment packets may be up to **120 MiB** and are still part of the byte-identical round-trip.
- Extended Opus frame headers and padding, including RFC 6716 code-3 padding within the 61,440-byte packet limit, still compress and expand to the original bytes.
- The same input compressed twice at the same effort, including in two process invocations and with `--no-mmap`, produces byte-identical archives.
- Expand needs only the archive, as for Vorbis (FP-02): a copy of the archive expands to the original bytes after the input and every other trace of compress are removed from the host.
- On `dump` standard output, a dedicated codec-mode field — not the archive path, not a byte size, not a leftover that varies with the file — answers whether the archive is Opus or Vorbis; two successful Opus archives share one payload of that field and a successful Vorbis archive of a different input has a distinguishable payload of the same field, independent of path and size. Opus archives whose inputs differ in page count, link count, channel count, duration, and OpusHead input sample rate, pre-skip, and output gain still share that payload, and no Vorbis archive carries it. The payload may be a number or a hex value. Exact wording of the field is the implementer's (FP-09).

**Boundary / error behavior:**

- Channel mapping family other than 0 is refused. Channel count other than 1 or 2 under family 0 is refused. On compress standard error, a dedicated kind slot — not the input path, not a size or offset that varies with the file — answers whether the input was recognized as Opus and then rejected for mapping, versus never recognized as Ogg Vorbis or Ogg Opus; those two answers are two distinguishable payloads of that same slot. A dedicated kind slot on the same stream answers whether the input was recognized as Opus and then rejected for channel count, versus never recognized as Ogg Vorbis or Ogg Opus, with the same two-payload contrast. Each payload may carry the rejected RFC 7845 mapping-family value or channel count as a number, and a payload that is itself a stable number is valid. An observer who sees only that slot can tell the two outcomes apart; an observer who sees only that the paths or sizes differ cannot.
- An Opus audio or OpusHead packet larger than 61,440 bytes is refused. An OpusTags packet larger than 120 MiB is refused.
- A nonzero Ogg version on a page (RFC 3533 version field) is refused.
- Chained Ogg Opus is supported (FP-06). That later feature point is the chained case; this feature point is a single logical stream.
- Expand of a Vorbis archive on this path is not used: expand selects the codec from the archive header. Expanding a Vorbis archive recovers Vorbis bytes (FP-02); expanding an Opus archive recovers Opus bytes. Mixing them (expand does not transcode).

**Verifiable oracle:**

- Success: compress then expand of a family-0 mono Ogg Opus file and of a family-0 stereo Ogg Opus file each exit 0 and recover the original bytes; a second compress matches the first archive byte-for-byte, and `--no-mmap` yields that same archive, at effort 1 and at effort 9; with the input and every other trace of compress removed from the host, a copy of the archive in a fresh working directory and home directory expands to the original bytes; a constructed file whose first audio packet is the original packet plus RFC 6716 code-3 padding, still at most 61,440 bytes, round-trips at effort 1 and effort 9; `dump` of two successful Opus archives shares one payload of a dedicated codec-mode field on standard output that `dump` of a Vorbis archive of a different input does not share, independent of path and size, and which may be a number or a hex value; compress of an OpusHead whose mapping family is not 0, and compress of a family-0 OpusHead whose channel count is not 1 or 2, each exit 1, and a dedicated kind slot on standard error distinguishes each of those from compress of a file never recognized as Ogg Vorbis or Ogg Opus, independent of path and of other per-file covariates, and may carry the rejected RFC 7845 family or channel count as a number.
- Failure / absence: Opus input is refused as unknown; expand recovers a different encapsulation; two compressions differ; padding within the RFC 7845 limit is refused; family 0 stereo is refused; dump has no dedicated codec-mode field, or answers Opus versus Vorbis only by path or size; mapping-family or channel-count refusal reuses the never-recognized diagnostic, or is distinguishable from it only by path or size.

Holding only this document and RFC 7845, an outside party computes the 61,440-byte packet cap from RFC 7845 section 6 applied to each Opus audio packet and to OpusHead. Holding RFC 7845, that party also decides whether channel mapping family is 0 and whether the channel count is 1 or 2, from the OpusHead identification header of the first logical stream. Those values are the graded bounds of this feature point.

---

### FP-04: Effort selection

**Public entry:** The effort options `-1` through `-9` on a compress invocation (single-file or batch). Expand does not take an effort that changes decoded bytes: the archive already stores what expand needs. If no effort option is given, compress uses **9**.

**Normal behavior:**

- Each of `-1`, `-2`, `-3`, `-4`, `-5`, `-6`, `-7`, `-8`, and `-9` is accepted on compress. The last effort option on the command line is the one that applies when several are given.
- Expand of an archive produced at any effort in 1 through 9 recovers the original bytes. Whether archives produced at adjacent efforts differ in size or bytes is **not scored** except for the corpus totals below. Wall-clock decode speed at any effort is **not scored**.
- On a fixed collection of valid Ogg Vorbis files that this product accepts, the **total** size of archives produced at effort 9 is **strictly smaller** than the total size of archives produced at effort 1. That collection is any set of ordinary accepted Vorbis files large enough that the two totals can differ; a single empty or tiny file that encodes to the same size at both ends does not by itself falsify the scale.
- On a fixed collection of valid family-0 Ogg Opus files that this product accepts, the total size of archives produced at effort 9 is **less than or equal to** the total size produced at effort 1.
- Effort does not change expand’s recovered bytes: an archive made at effort 1 and an archive made at effort 9 of the same input both expand to that input.
- At effort 9, compress of an ordinary accepted file writes an archive strictly smaller than that file. An ordinary file here is a single-link Ogg Vorbis file, or a single-link family-0 mono or stereo Ogg Opus file, carrying encoder-produced audio: identification, comment, and (for Vorbis) setup headers, then audio packets without added padding, ending on an end-of-stream page; how packets are laid out on valid pages, and the comment text, may be anything valid.
- At every effort, the archive is a recompression, not a stored copy. Counted by bytes, most of the input's audio packets of at least 16 bytes do not appear byte-for-byte anywhere in the archive. Wrapping, masking, splitting, or reordering the input without recompressing it does not satisfy this feature point.

**Boundary / error behavior:**

- There is no effort 0 and no effort 10. Those tokens are not effort options; a lone `-0` is an unknown option (usage error, FP-01).
- Effort on expand is ignored for recovered bytes. Supplying `-3 d archive dest` still expands to the original file when the archive is valid.

**Verifiable oracle:**

- Success: omitting effort on compress of a valid Vorbis file produces the same archive bytes as `-9`; `-1` and `-9` both expand back to the original; over a bundle of several accepted Vorbis files, the sum of `-9` archive sizes is strictly less than the sum of `-1` archive sizes; over a bundle of accepted Opus files, the sum at `-9` is less than or equal to the sum at `-1`; at `-9`, the archive of each ordinary accepted Vorbis or Opus file is smaller than that file; at `-1`, `-5`, and `-9`, fewer than half of the input's audio-packet bytes (counting packets of at least 16 bytes) belong to packets that appear byte-for-byte in the archive.
- Failure / absence: default effort matches `-1` rather than `-9`; `-9` is larger in total than `-1` on that Vorbis bundle; expand of a `-9` archive does not match the original; effort changes recovered bytes; an ordinary file's `-9` archive is as large as the file or larger; an archive at any effort carries the audio packets unchanged.

---

### FP-05: Exact-reproduction refusals

**Public entry:** Compress (`e`) or expand (`d`) on a file that this product will not reproduce exactly, on a file of the wrong type for the verb, or on an archive whose format generation is not this product’s. Batch (FP-07) uses the same per-file refusal and continues with other files.

**Normal behavior:**

- Every accepted compress is a promise that expand will restore the original bytes. If the product cannot keep that promise for a given input, it refuses rather than writing an archive that would expand incorrectly.
- A refusal exits 1 for a single-file invocation, writes a diagnostic to standard error that identifies the offending input, and does not leave a successful archive at the destination as the outcome of that file. Three refusals name the construct instead of the input and are not required to identify the input path: expand of an input that is not a oggrepack archive, and compress of a Vorbis file whose setup carries floor type 0 or codebook lookup type 2. (A destination path may exist as a partial write; it must not expand to a file the caller could mistake for a successful round-trip of that input.)
- Pages with a checksum that does not match the CRC-32 defined by RFC 3533 for that Ogg page are refused. The outside party computes the expected checksum from RFC 3533 over the page bytes with the checksum field treated as zero, and compares it with the stored field.
- On compress of an Ogg Vorbis file, a page that follows a finished end-of-stream page of the same logical stream with no new beginning-of-stream, and a packet that continues onto a following page that is not marked as a continuation, are each refused. On compress of a supported family-0 Ogg Opus file, those same two constructions exit 0, and expand of that archive restores the constructed bytes. Trailing bytes after the last Ogg page that are not a following chained link are refused on both codecs.
- Unsupported Vorbis features are refused, including floor type 0 and codebook lookup type 2 as defined by the Vorbis I specification, and a codebook that cannot be reproduced exactly (including a sparse empty book that would not round-trip).
- Unsupported Opus mapping and packet limits are refused as in FP-03.
- Expand of a file that is not a oggrepack archive of this product generation is refused. Compress of a file that is not Ogg Vorbis or Ogg Opus is refused. Standard error makes those two wrong-type cases distinguishable from each other (expand-of-Ogg versus compress-of-archive).
- Expand of an archive whose generation identifier is not the generation this product writes is refused. The generation identifier is its own whole-byte field of the archive and has the same value in every archive this product writes, whatever the input, codec, or effort. The constructable case is: take an archive this product just wrote, change only the generation identifier to a value this product does not write (both an older generation and a newer generation), and expand; that run exits 1. Standard error makes that generation mismatch distinguishable from expand of a file that is not an archive.

**Boundary / error behavior:**

- A truncated archive either refuses (exit 1) or, if it exits 0, writes a destination that matches the original source of that archive’s valid encoding. It must not crash. An archive whose interior bytes are flipped stays in exit {0, 1} and must not crash; undetectable interior damage may exit 0 with a destination that does not match the original. A crash or exit 4 on damaged caller input is not this product’s promised failure class for that input.
- Vorbis files that omit the final end-of-stream flag but end on a complete packet are **accepted** (FP-06), not refused. That exception is not a refusal case.
- Vorbis audio packets with extra padding that is a legal packet ending are **accepted** (FP-02), not refused.
- A missing file is a file-access error (exit 3), not a refusal (exit 1).

**Verifiable oracle:**

- Success: an Ogg file whose only defect is a wrong page checksum, computed against RFC 3533 as above, exits 1 on compress; an Ogg Vorbis file that appends a page after a finished end-of-stream page of the same stream with no new beginning-of-stream exits 1 on compress; an Ogg Vorbis file in which a packet continues onto a following page that is not marked as a continuation exits 1 on compress; a supported family-0 Ogg Opus file with either of those same two constructions exits 0 on compress and expand restores the constructed bytes; trailing bytes after the last Ogg page that are not a following chained link exit 1 on compress of both codecs; a non-Ogg file exits 1 on compress and is distinguishable from a missing path (exit 3); expand of a valid `.ogg` exits 1; compress of a valid archive exits 1; expand of an archive this product wrote after only the generation identifier is changed to a value this product does not write exits 1 and is distinguishable from expand of a non-archive; a truncated archive exits 1 or, if it exits 0, the destination matches the original source of that archive’s valid encoding; an archive with an interior byte flipped exits 0 or 1.
- Failure / absence: a bad checksum is accepted and round-trips to different bytes; on an Ogg Vorbis file, a page after a finished end-of-stream of the same stream, or a continued packet onto a page not marked as a continuation, is accepted; on a supported family-0 Ogg Opus file, either of those two constructions is refused; trailing bytes after the last Ogg page that are not a following chained link are accepted; wrong-type inputs exit 0; a foreign generation expands; a truncated or interior-flipped archive crashes or exits 4; missing files exit 1.

Holding only this document and RFC 3533, an outside party computes the page checksum that must match for compress to proceed, from the complete Ogg page under test, with the checksum field treated as zero as RFC 3533 specifies.

---

### FP-06: Chained bitstreams and Vorbis files without a final end-of-stream flag

**Public entry:** Compress and expand (FP-02, FP-03) when the input is a chained Ogg file, or a Vorbis file whose last page does not have the end-of-stream flag set. This feature point changes the set of inputs FP-02 and FP-03 accept; it does not change the byte-identical expand contract.

**Normal behavior:**

- A chained Ogg Vorbis file (two or more links, each a Vorbis logical stream) compresses and expands to the original bytes. Links may differ in length. A later link may replay headers that already appeared; the original framing is still restored.
- A chained Ogg Opus file whose every link is a supported family-0 mono or stereo stream compresses and expands to the original bytes. Links may differ in mode and channel count (mono versus stereo) as long as each link stays on family 0 with one or two channels.
- Concatenating several valid family-0 Opus files into one chained Ogg file, then compressing and expanding, recovers that concatenation. Whether the chained archive is smaller than encoding the parts separately is **not scored** when the links differ in mode or channel count. Homogeneous chains may compress comparably to one long file; that typical gain is **not scored**.
- A Vorbis file that is otherwise valid, ends on a complete packet, and lacks the end-of-stream flag on the last page, compresses and expands to those original bytes — including when the file is a chain, and including when complete copies of the file are prefixed before the copy that lacks the flag.

**Boundary / error behavior:**

- A page that belongs to a stream that has already ended (a page after end-of-stream for that stream, without a new beginning-of-stream) is refused on an Ogg Vorbis file and accepted on a supported family-0 Ogg Opus file, with expand restoring the constructed bytes (FP-05).
- An Opus chain that includes a link with channel mapping family other than 0, or with a channel count other than 1 or 2, is refused.
- An incomplete final packet (the file ends in the middle of a packet) is refused.
- A chain of two Vorbis links that each merge later header packets onto the same page as that link’s first audio packet still round-trips.

**Verifiable oracle:**

- Success: compress then expand of a three-link chained Vorbis file recovers the original bytes; concatenating three different family-0 Opus files (stereo CELT, mono SILK, mono hybrid) into one file, then compress and expand, recovers that concatenation; taking a valid Vorbis file, clearing the end-of-stream flag on its last page, and correcting that page’s RFC 3533 checksum, yields a file that still round-trips; a chain of two Vorbis links that each merge later header packets onto the same page as that link’s first audio packet still round-trips.
- Failure / absence: chained inputs are refused; expand of a chain recovers only the first link; a Vorbis file without a final end-of-stream flag is refused even though the last packet is complete; a page after end-of-stream on an Ogg Vorbis file is accepted.

---

### FP-07: Batch compress and expand

**Public entry:** `oggrepack -b` / `--batch` followed by `e` or `d` and one or more input paths. Optional `--jobs=N` (or `-j N`) is accepted. Effort, progress, and no-mmap apply to the whole batch.

**Normal behavior:**

- Every remaining path after the verb is an input. There is no separate output operand.
- On Linux and other Unix hosts, batch compress writes, beside each input, a destination whose name is the input path with `.orp` appended. Batch expand strips a trailing `.orp` to recover the original path; if the input name has no `.orp` suffix, expand appends `.out`.
- Each file is processed as a single-file compress or expand (FP-02, FP-03) with the same effort and mapping option. Success for a file means that file’s destination exists and, for expand, matches the original source; for compress, a later expand of that destination matches the original source.
- Larger inputs start first. On batch compress with jobs set to one, of two non-Ogg files of different sizes that both refuse, standard error carries the larger input path before the smaller input path. Batch expand of two non-archive files of different sizes need not name those paths in the per-file refusal report; that construction is not the observer for larger-first.
- After a refusal or a file-access error on one file, remaining files still run. The process exit status is the **highest** nonzero status reported by any file (1, 2, 3, or 4 as in FP-01). If at least one file was refused and no higher status occurred, the status is 1.
- When at least one file fails, standard error writes a dedicated mixed-failure summary field — not the input path, not a per-file size or offset, not leftover after stripping paths and sizes, not a per-file diagnostic that varies with the file — whose two payloads are how many members failed and how many paths were attempted. That field is present with a nonzero failed-count payload on mixed failure; an all-success run of the same operands does not answer a nonzero failed-file count on that field. Two mixed runs that differ only in how many members failed have distinguishable payloads of the failed-count half of that field; two mixed runs that differ only in how many files were attempted have distinguishable payloads of the attempted-count half. Each payload may be a number. Mixed-versus-all-success full-text, leftover integers after a path or size is stripped, or mixed-to-mixed full-text of different members is not the count-answer. Successful files in that mixed batch still have valid destinations.
- Without `--jobs`, the program chooses a positive job count. That automatic count, and how many files overlap in time, are the implementer's and are **not scored**. With `--jobs=N`, N must be a positive integer (FP-01).
- Batch progress uses separate lines labeled with the input filename (FP-08).

**Boundary / error behavior:**

- Batch with no file paths, or with a verb other than `e` or `d`, is a usage error.
- `--jobs=0` and non-integer job counts are usage errors (FP-01).
- A missing path in a batch of otherwise valid files yields exit 3 (file-access) if that is the highest status, and the valid files still encode or expand.
- DOS replacement of the extension and `.opu` for expanded Opus is not a Linux obligation.

**Verifiable oracle:**

- Success: batch compress of three distinct valid Vorbis files with `--jobs=2` writes three `.orp` destinations and exits 0; batch expand of those three destinations restores three files byte-identical to the sources; a batch of one non-Ogg file and one valid Vorbis file exits 1, a dedicated mixed-failure summary field on standard error answers the failed-file count and the attempted-file count with a nonzero failed-count payload, an all-success run of the same operands does not answer a nonzero failed-file count on that field, two mixed runs that differ only in failed-file count or only in attempted-file count have distinguishable payloads of the corresponding half of that field which may be a number, independent of path, leftover after stripping paths and sizes, leftover integers, and mixed-to-mixed full-text, and the valid file still has a `.orp` that expands to the original; a batch of a missing path and a valid file exits 3 and still writes the valid file’s archive; with `--jobs=1`, batch compress of two non-Ogg files of different sizes that both refuse, the larger input path appears on standard error before the smaller.
- Failure / absence: batch requires explicit output paths; a refusal stops the rest; mixed failure exits 0; mixed failure has no dedicated summary field for the two counts, or answers them only by mixed-versus-all-success full-text, leftover after stripping paths and sizes, leftover integers, or mixed-to-mixed full-text; destinations are not named by appending `.orp`; larger files do not start first in a serial batch.

---

### FP-08: Opt-in progress on standard error

**Public entry:** `-p` / `--progress` and `--progress-lines` on compress, expand, or batch. Progress is off by default.

**Normal behavior:**

- With progress off, compress and expand of a valid file write no progress indication to standard error. A successful run may still be silent on standard error.
- With `--progress` or `-p` on a single-file compress or expand, standard error carries progress for that operation. A completion indication is a progress update whose text carries the literal `100%`; the invocation without the option writes no such update. An observer can distinguish a completed successful run from the same invocation without the option by the presence of that indication.
- `--progress-lines` writes progress as separate lines suitable for a log. Batch mode always uses line-oriented progress when progress is on, and labels those lines with the input filename so two files in one batch are distinguishable.
- A progress run is the progress output up to and including one completion indication. On Vorbis compress with progress on, effort 1 writes exactly one completion indication to standard error (a single progress run). Effort 9 on the same input writes two or more (several distinct progress runs). The wording of the labels is the implementer’s; the count of completion indications is the observable.
- Enabling progress does not change archive bytes: compress with progress and compress without progress on the same input and effort write identical archives. That holds at every effort, for Vorbis and Opus, for `-p`, `--progress`, and `--progress-lines`, and for batch compress with progress against single-file compress without it. Expand with progress still recovers the original bytes.

**Boundary / error behavior:**

- Progress is opt-in. Absence of the option is not a failure.
- A refusal with progress on still writes the refusal diagnostic (FP-05) to standard error and exits 1. Progress being on does not change that status or hide the diagnostic.
- Progress on Opus compress and on Opus expand both reach a completion indication on success.

**Verifiable oracle:**

- Success: compress without progress of a valid file produces standard error that does not carry a completion indication; the same compress with `--progress` does, and the archive bytes match the no-progress archive; at effort 1 and at effort 9, for a Vorbis and an Opus input, `-p`, `--progress`, `--progress-lines`, and batch compress with progress each write the archive that single-file compress without progress writes; expand with `--progress` of that archive recovers the original and standard error carries a completion indication; batch compress with `--progress` and `--jobs=2` of three named files includes those file names on standard error and a completion indication; Vorbis compress with `--progress` at effort 1 shows a single progress run, and the same input at effort 9 shows more than one distinct progress run.
- Failure / absence: progress is on by default; progress changes archive bytes; batch progress cannot be attributed to a filename; effort 1 and effort 9 Vorbis progress cannot be told apart by the count of completion indications (effort 1 not exactly one, or effort 9 fewer than two).

---

### FP-09: Archive dump and Ogg page listing

**Public entry:** `oggrepack dump` with one archive path; `oggrepack pages` with one Ogg file path.

**Normal behavior:**

- `dump` on a valid archive written by this product exits 0 and writes a layout description to standard output. On that standard output, a dedicated codec-mode field — not the archive path, not a byte size, not a leftover that varies with the file — answers whether the archive is Opus or Vorbis; two successful Opus archives share one payload of that field, and a successful Vorbis archive of a different input has a distinguishable payload of the same field, independent of path and size. Opus archives whose inputs differ in page count, link count, channel count, duration, and OpusHead input sample rate, pre-skip, and output gain still share that payload, and no Vorbis archive carries it, including a Vorbis archive whose identification header names a 48 kHz rate. The payload may be a number or a hex value. On that same standard output, a dedicated stored-stage field — not the archive path, not a byte size, not a leftover that varies with the file — answers the encoding stage stored for a Vorbis archive; a Vorbis archive made at effort 1 and a Vorbis archive made at effort 3 of the same input have distinguishable payloads of that field, independent of path and size. Dump of archives made at effort 4 through 9 of the same Vorbis input need not distinguish those efforts: they may share a payload of that stored-stage field. The stored-stage payload may be a number or a hex value. The exact wording is the implementer’s; the distinctions above must be observable.
- `pages` on a valid Ogg Vorbis or Ogg Opus file exits 0 and lists every page. On that standard output, each listed page carries a dedicated reconstruction-status field — not the file path, not a byte size, not a leftover that varies with the file — whose two payloads are success and mismatch. Success means the stored page bytes equal the RFC 3533 reconstruction of that page’s parsed header and body, including the CRC-32 computed with the checksum field treated as zero; mismatch means they do not. Well-formed Ogg Vorbis and Ogg Opus files carry the success payload on every listed page. A still-parseable same-codec sibling that differs only by one page’s stored RFC 3533 checksum not matching that CRC still exits 0 and lists; that page carries the mismatch payload. The distinction is independent of path and size. The exact wording is the implementer’s.
- `pages` on a valid file does not modify the file.

**Boundary / error behavior:**

- `dump` on a missing path is a file-access error (exit 3). `pages` on a missing path is a file-access error.
- `pages` on a file that is not Ogg is refused (exit 1). `dump` on a file that is not a oggrepack archive of this generation is refused.
- Extra operands beyond one path are usage errors (FP-01).

**Verifiable oracle:**

- Success: dump of a Vorbis archive exits 0 and writes a dedicated codec-mode field on standard output whose payload is distinguishable from dump of two successful Opus archives that share one payload of that field, independent of path and size, and which may be a number or a hex value; dump of a Vorbis archive made at effort 1 writes a dedicated stored-stage field on standard output whose payload is distinguishable from dump of an archive of the same input made at effort 3, independent of path and size, and which may be a number or a hex value; pages of a well-formed Vorbis file exits 0, lists pages, and writes a dedicated reconstruction-status field on each listed page whose payload is success, independent of path and size; pages of a still-parseable sibling that differs only by one page’s stored RFC 3533 checksum not matching the CRC computed with the checksum field treated as zero still exits 0 and that page carries the mismatch payload of that same field, independent of path and size; pages of an archive file (not Ogg) exits 1; dump of a missing path exits 3.
- Failure / absence: dump has no dedicated codec-mode field, or answers Opus versus Vorbis only by path or size; dump has no dedicated stored-stage field, or answers effort 1 versus effort 3 of the same Vorbis input only by path or size; pages has no dedicated reconstruction-status field, or answers success versus mismatch only by path or size, or a well-formed file carries the mismatch payload; pages rewrites the file; pages on a non-Ogg file exits 0.
