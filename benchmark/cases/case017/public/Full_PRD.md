# klyvmap — Full Product Requirements Document

## Product overview

**klyvmap** is a Zig library of roaring bitmaps over 64-bit unsigned integers. Its defining product property is that **the in-memory form of a bitmap is the serialized form**: one flat byte buffer that can be stored or sent as-is. Opening that buffer does not convert it into a second in-memory form. Reads after open do not require a separate deserialize step the caller must invoke. The first set on a borrowed open does not write the caller’s buffer, which stays byte-identical to what was opened.

A first-time integrator creates an empty bitmap, sets 42 and a value above 2^40, observes that both are present and that the cardinality is 2, optionally compacts for long-term storage, emits the buffer, and later opens that same buffer and iterates the values. A bitmap that cannot round-trip through its own buffer, that treats 0 as “end of iteration”, or that cannot hold values above 2^32, is a failure of the product.

klyvmap is a 64-bit roaring bitmap only. It does not offer a run-length packing of consecutive values. It does not implement CRoaring’s portable or frozen interchange formats. The format version stamped into every buffer is tracked separately from the library’s calendar release version; buffers that share a format version read each other.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished klyvmap product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **klyvmap** | The product. A Zig library that stores a set of 64-bit unsigned integers as one roaring bitmap in one flat buffer. |
| **bitmap** | One such set. Empty until values are set. The caller creates it, mutates it, queries it, emits its buffer, and releases it. |
| **value** | A 64-bit unsigned integer in the closed range from 0 through the maximum 64-bit unsigned integer. Setting a value that is already present does not create a second copy. |
| **buffer** | The flat, 8-byte-aligned byte sequence that **is** the bitmap. Emitting the buffer does not convert a separate in-memory object graph. Opening the buffer does not build a second representation. |
| **borrow** | An open mode: the caller keeps the buffer. The bitmap never writes it and never frees it. The buffer must outlive the bitmap. The first set leaves the caller’s memory byte-identical to what was opened. |
| **own** | An open mode: the bitmap takes the buffer. Before the caller mutates it, the opened bitmap’s storage is that allocation, not a second buffer. Releasing the bitmap frees whatever storage it then holds. Whether a mutation replaces that allocation is the implementer’s and is not scored. The buffer must be a writable allocation from the same allocator the caller passes in. The transfer is unconditional: success and the failure paths in FP-04 both take responsibility for that allocation. |
| **format version** | An integer stamped into every buffer. This product’s current format version is **1**. Opening refuses any other version. |
| **compact** | The optional rewrite that produces the smallest buffer that still holds the same set, for long-term storage. Equal sets become byte-identical. The result stays an ordinary mutable bitmap. |
| **cleanup** | The operation that reclaims space left after in-place intersection, in-place difference, or remove have emptied prefixes, without changing membership. |
| **materializing intersection / union** | Entries that return a **new** bitmap equal to the intersection or union of two bitmaps, leaving both operands unchanged. |
| **n-ary union** | Many bitmaps in, one new bitmap out, equal to the union of every input. |
| **in-place intersection / union / difference** | Entries that replace the left bitmap with its intersection with, union with, or difference from the right bitmap. |
| **fused cardinality** | Entries that return how many values the intersection, union, or difference **would** contain, without producing that result bitmap. |
| **iterator** | A forward walk that yields each present value once, in ascending order, until it reports that it is exhausted. Exhaustion is distinct from the value 0. |
| **unsupported-format-version failure** | The distinct failure of opening a buffer that is large enough to be a bitmap but whose format version is not 1. It is not the empty-bitmap outcome used for a buffer that is not a bitmap at all. |
| **core capability** | A user-observable capability that reflects klyvmap’s design goal; acceptance must prove the real library behavior, not a stub. |
| **discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

klyvmap is a **library**. Integrators reach it by depending on the klyvmap Zig module. There is no command-line product and no I/O inside the library: callers pass allocators and byte buffers.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- Create an empty bitmap, clone it, and release it (FP-01).
- Set, test membership of, and remove 64-bit values (FP-02).
- Report cardinality, emptiness, minimum, and maximum, and enumerate values in ascending order (FP-03).
- Emit the buffer and open it again, in borrow or own mode, including the copying open that accepts unaligned input (FP-04).
- Compact a bitmap to the smallest canonical buffer that still round-trips (FP-05).
- Materialize intersection and union of two bitmaps, and the n-ary union of many (FP-06).
- Intersect, union, or difference **into** an existing bitmap, then reclaim emptied-prefix space with cleanup (FP-07).
- Count intersection, union, and difference without producing a result bitmap (FP-08).
- Build a bitmap from a non-decreasing list of values (FP-09).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A Zig library with no runtime third-party dependencies. Library code performs no file or network I/O. Callers supply a memory allocator and, when opening, a byte buffer.
- **Language / toolchain:** Zig 0.16. The package’s minimum Zig version is 0.16.0.
- **Endianness:** The on-disk format is little-endian by definition. Big-endian targets are refused at compile time. A file written on any supported machine reads on every supported machine.
- **Platforms:** Little-endian hosts the toolchain supports (including x86-64 and ARM64). This case’s acceptance targets Linux with Zig 0.16.
- **Hardware:** CPU-only. No GPU or accelerator is required or claimed. There is no removable mandatory substrate.
- **Integer domain:** 64-bit unsigned integers only. There is no 32-bit variant.
- **Run-length packing:** Not offered. How dense versus sparse runs are packed internally is the implementer’s and is not scored.
- **Trusted buffers:** Beyond the size check and the format-version check in FP-04, a buffer is trusted input. Integrity checks (checksums, signatures) belong a layer above. This product does not promise a distinct diagnostic for a corrupt payload whose version and size look like a bitmap.
- **Release vs format version:** The version the Zig package publishes for itself — its declared release version — is calendar form `0.YYMM.patch`. That identifier is a different value from the format-version integer in an emitted buffer, which stays 1. Releases that share format version 1 read each other’s buffers.
- **Error policy:** Operations that may allocate can fail by not producing a bitmap when the allocator cannot satisfy the request. That out-of-memory outcome is an allocator failure, not a product boundary this document grades. Reads cannot fail. An unsupported format version is the only graded open-time failure (FP-04).
- **Performance vs CRoaring:** Speed on warm or cold open, and serialized size relative to CRoaring, are design goals. They are **not scored**.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate capability. Faithful implementation is a real roaring bitmap over 64-bit values whose in-memory form is its serialized buffer, running on a CPU host.

For every feature point:

- **Present:** Real klyvmap behavior matches the described outcomes when a bitmap is created, mutated, queried, emitted, opened, compacted, or combined.
- **Absent / hollow:** Every membership check returns the same answer; cardinality counts duplicates as extra members; opening a buffer does not make membership available until the caller builds a second structure; compact changes the set; set algebra disagrees with ordinary set intersection, union, or difference; the iterator treats 0 as “done”.

Cheaper proxies (a hash set that cannot emit a klyvmap buffer, a 32-bit roaring bitmap, a CRoaring wrapper, a hard-coded fixture buffer, or a serializer that cannot be queried until it is parsed back into objects) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces klyvmap’s buffer-identity bitmap for a core capability.

There is no removable mandatory hardware profile. Do not write a device-disable negative control. Discrimination is against hollow behavior: feeding a construct the capability claims to handle and observing that the outcome is indistinguishable from “feature absent.”

## Non-goals

- CRoaring’s portable format or frozen format. klyvmap does not read or write those encodings.
- Run containers, a 32-bit roaring variant, rank, select, range removal, bitmap splitting, exclusive-or, a materializing difference that returns a new bitmap, or a parallel n-ary union other than the n-ary union in FP-06.
- Bindings in other languages.
- Guaranteeing a particular throughput or a particular serialized size relative to CRoaring. Those comparisons live in the project’s benchmark report; they are not graded oracles.
- Treating the CRoaring differential harness, the search microbench, the plot scripts, or packaging as product capabilities.
- Optional memory-movement counters a program may enable for profiling. They are not a core capability.
- Validating untrusted buffers beyond the size and format-version checks in FP-04.

---

## Feature points

### FP-01: Create, clone, and release a bitmap

**Public entry:** klyvmap’s bitmap constructor, which takes a memory allocator and returns an empty bitmap the caller owns and must release; the clone entry, which returns an independent owned copy; and release, which frees the buffer when the bitmap owns it and is safe on a bitmap that only borrows.

**Normal behavior:**

- A freshly created bitmap holds no values. Emptiness is true. Cardinality is 0. Minimum and maximum are absent (not 0). Membership of 0 is false: 0 is a legal value that is simply not present yet.
- Emitting that empty bitmap’s buffer (FP-04) yields a non-empty buffer. There is no null-buffer special case for “empty”. Opening that buffer again yields a bitmap that is still empty and still usable: setting 42 afterwards makes 42 present.
- Clone produces a second bitmap that holds the same values. Mutating the clone does not change the original, and mutating the original does not change the clone. After cloning a bitmap that contains 0 through 2999 and the value 2^40, setting 2^50 on the clone makes 2^50 present only on the clone; removing 0 from the original leaves 0 present only on the clone.
- Release of a bitmap that owns its buffer frees that buffer. Release of a bitmap opened in borrow mode (FP-04) does not free the caller’s buffer.

**Boundary / error behavior:**

- Creating a bitmap can fail only when the allocator cannot satisfy the request. That outcome is not scored.
- Clone of an empty bitmap is an empty bitmap, still distinct from the original: setting a value on the clone leaves the original empty.

**Verifiable oracle:**

- Success: a newly created bitmap reports empty, cardinality 0, no minimum, no maximum, and not-contains 0; its emitted buffer has positive length and reopens as empty; after setting 42 on that reopened bitmap, 42 is present; cloning a bitmap that holds 0 through 2999 and 2^40, then setting 2^50 on the clone and removing 0 from the original, leaves the clone containing 0 and 2^50 and the original containing 2999 and 2^40 but not 0 and not 2^50; releasing a borrowed open leaves the caller’s buffer intact for a second open.
- Failure / absence: a new bitmap already contains 0, or reports minimum 0 while empty; the empty bitmap has no buffer; clone aliases the original so one mutation shows up on both; releasing a borrowed bitmap frees or overwrites the caller’s bytes.

---

### FP-02: Set, membership, and remove of 64-bit values

**Public entry:** The bitmap’s set, membership, and remove operations. Enumeration and extrema are FP-03. Opening and emitting buffers are FP-04. A bitmap opened in borrow mode does not write the caller’s buffer on the first **set** (FP-04). **Remove** on a still-borrowed bitmap is not specified until after a set, or after compact in FP-05.

**Normal behavior:**

- Set adds a 64-bit unsigned integer. It reports whether the value was **newly** added: true on the first set of that value, false on a second set of the same value. Cardinality increases by one only when the report is true.
- Membership is true exactly for values that have been set and not since removed, and false for every other 64-bit unsigned integer.
- Remove deletes a value if it is present and reports whether it was present: true once, then false if called again. Cardinality decreases by one only when the report is true. Remove of a value whose high bits have no other members in the bitmap does not disturb membership of values under other high bits.
- The following values, set in any order, are each present and each count once: 0; 65535; 2^16; (2^32) + 5; (2^32) + 65535; (2^48) + 7; (2^48) + 2^32; the maximum 64-bit unsigned integer; one less than that maximum. After those nine are set, cardinality is 9, minimum is 0, maximum is the maximum 64-bit unsigned integer, and membership is false for 1, for (2^32) + 6, and for 2^47.
- A dense run of consecutive values that starts at 0 and is thousands long (for example five thousand) still reports every value present, cardinality equal to the length of the run, minimum 0, and maximum one less than the length. Membership just past the run is false.
- Setting values under hundreds of distinct high-48-bit prefixes (for example 600 prefixes, three values each, inserted out of order) preserves every value and reports cardinality equal to the number of distinct values.

**Boundary / error behavior:**

- Set of a value already present does not change cardinality and reports that it was not newly added.
- Remove of a value that was never set reports false and does not change cardinality. Remove of 2^32 from a bitmap that has no value with that high-bit prefix is this case.
- Whether remove shortens the emitted buffer or matches FP-05’s compact canonical bytes is the implementer’s and is not scored. Membership after remove is what is graded.
- Set on a borrowed bitmap never writes the caller’s buffer (FP-04). Remove on a borrowed bitmap is not specified until after a set, or after compact in FP-05.

**Verifiable oracle:**

- Success: set 42 reports newly added, a second set 42 reports not newly added, membership of 42 is true, cardinality is 1; the nine boundary values listed above are all present with cardinality 9, minimum 0, maximum the 64-bit maximum, and membership false for 1, (2^32)+6, and 2^47; removing 0 after setting 0 and 65535 leaves 65535 as minimum and not-contains 0; a consecutive run 0 .. n−1 with n equal to five thousand still contains every value in the run and not n; 600 prefixes × 3 values, inserted out of order, yield cardinality 1800 and membership true for each inserted value; remove of an absent value reports false.
- Failure / absence: a second set of 42 increases cardinality; 0 cannot round-trip through membership; values at or above 2^32 are lost or alias lower values; a dense run of thousands drops members; remove of 0 empties the whole bitmap; set always reports newly added even on duplicates.

---

### FP-03: Cardinality, extrema, and ascending enumeration

**Public entry:** The bitmap’s cardinality query, emptiness query, minimum query, maximum query, the forward iterator, the entry that allocates a new array of every value, and the entry that writes every value into a caller-supplied destination whose length equals the cardinality.

**Normal behavior:**

- Cardinality is the number of distinct present values. Emptiness is true exactly when cardinality is 0. On a non-empty bitmap, minimum is the smallest present value and maximum is the largest. On an empty bitmap both are absent, not 0.
- The iterator yields each present value once, in strictly ascending order, then reports exhaustion. Exhaustion is a distinct outcome from yielding 0: a bitmap that contains 0 yields 0 as a real first value. A second pull after exhaustion is still exhaustion.
- An empty bitmap’s iterator reports exhaustion on the first pull and on the next pull.
- A bitmap that contains only 0 and 2^32 yields 0 then 2^32 then exhaustion.
- A bitmap that contains 0 as part of a dense consecutive run of five thousand values still yields 0 first, then 1, 2, … up through the last present value, then exhaustion. 0 is not treated as “done”.
- After setting 5, 2^16, and 2×2^16, then removing 2^16 (which empties that prefix), the iterator yields 5 then 2×2^16 then exhaustion. Removed values and emptied prefixes do not appear.
- The allocated-array entry returns a slice the caller owns, of length equal to cardinality, holding the same values as a full drain of the iterator, in the same order. On an empty bitmap that slice has length 0.
- The caller-supplied-destination entry writes those same values into a destination whose length equals cardinality. On an empty bitmap the destination has length 0 and nothing is written. Writing into a prefix of a larger reusable buffer leaves the suffix of that buffer untouched.

**Boundary / error behavior:**

- The iterator is valid until the bitmap is mutated. Behavior of an iterator used after a mutation of its bitmap is not specified.
- The caller-supplied destination must have length exactly equal to cardinality. A destination of the wrong length is not a graded failure mode.
- Minimum and maximum skip prefixes that currently hold no values (for example after removing every value under the lowest prefix): after setting 0..99 and a dense run under prefix 2^16, then removing 0..99, minimum is 2^16, not absent and not a removed low value.

**Verifiable oracle:**

- Success: empty bitmap — cardinality 0, empty true, min and max absent, iterator exhausted immediately, allocated array length 0; bitmap of 0 and 2^32 — iterator yields 0 then 2^32 then exhaustion, min 0, max 2^32, allocated array is those two values in that order; dense run 0 .. 4999 — iterator’s first yield is 0, last yield is 4999, then exhaustion; after setting 5, 2^16, and 2×2^16 and removing 2^16 — iterator yields 5 then 2×2^16; allocated array of a mixed dense-and-scattered bitmap matches a sorted unique list of the values that were newly set; writing into a destination of length cardinality inside a larger buffer that was filled with a sentinel leaves the sentinel in the unused suffix; after emptying the low prefix, minimum is the smallest remaining value.
- Failure / absence: empty bitmap reports minimum 0; iterator that sees 0 stops without yielding later values; allocated array is unsorted or contains duplicates; emptiness disagrees with cardinality 0; destination write overruns into the unused suffix; removed values still appear in the iterator.

---

### FP-04: Emit and open the buffer (in-memory form is the serialized form)

**Public entry:** The entry that returns the bitmap’s current buffer as a borrowed byte view; the entry that returns an owning copy of those bytes; the entry that opens an 8-byte-aligned buffer as a bitmap in **borrow** or **own** mode; and the copying open, which accepts any byte slice (including a slice that is not 8-byte aligned) and always yields an owned bitmap.

This feature point is the product’s defining surface. Reads after open must work without a second deserialize step the caller has to invoke. Compact before storage is FP-05.

**Normal behavior:**

- Emitting the borrowed view is valid until the bitmap grows or is released. The owning copy remains valid after the source bitmap is released. An empty bitmap still emits a buffer of positive length (FP-01).
- Every emitted buffer of a valid bitmap is at least **64** bytes long and has even length. Its **first two bytes** are the little-endian encoding of the unsigned 16-bit integer **1** (the format version). Byte 0 is 1 and byte 1 is 0.
- Opening a buffer that this product emitted, in borrow mode, yields a bitmap with the same membership, cardinality, minimum, maximum, and iterator sequence as the source. The opened bitmap’s in-use bytes match the source’s in-use bytes. Opening the borrowed view of a live bitmap (without taking an owning copy first) is allowed in borrow mode and does not write through that view on reads.
- Borrow: reads (membership, cardinality, emptiness, minimum, maximum, iteration, emitting again) do not write the caller’s buffer. The open and those reads allocate nothing through the allocator passed to the open, and they do not copy, index, or decode the buffer’s contents into any other memory: until the first set, the view the bitmap emits is the caller’s buffer itself, at the same address and of the same length. The first **set** leaves the caller’s buffer byte-identical to what was opened, including when the set would have fitted without growing. Setting a brand-new high prefix also leaves the caller’s buffer untouched. A second open of that same caller buffer still reports the original set, not the values added after that set.
- Own: before the caller sets a value, an own-open of a well-formed buffer does not build a second buffer — the opened bitmap’s emitted view is the supplied allocation. The open and reads before that set allocate nothing through the allocator. After a set, membership and cardinality follow that set, and release frees whatever the bitmap then owns so the allocator’s outstanding total returns to the total from before the open. The caller must not free the original allocation. Whether any particular value, including a value under a prefix the buffer already holds, fits without replacing the allocation is the implementer’s and is not scored.
- The copying open of a well-formed buffer yields an owned bitmap whose in-use bytes match the source. A source slice that starts two bytes into a larger allocation (deliberately not 8-byte aligned) still opens and matches. Mutating the copy does not change the source bytes.
- After opening in borrow mode, compact (FP-05) also produces an owned mutable bitmap without writing the caller’s buffer.

**Boundary / error behavior:**

- A buffer whose length is **not a multiple of 2**, or whose length is **strictly less than 64 bytes**, is not a bitmap. Opening it — borrow, own, or the copying open — yields a **fresh empty bitmap**, not an unsupported-format-version failure. An 8-byte buffer, a 62-byte buffer, a 0-byte slice, and a 65-byte (odd) buffer are this case, even if their first bytes look like a version.
- A buffer that is at least 64 bytes and even-length, but whose first two bytes are **not** the little-endian encoding of 1, is refused with an **unsupported-format-version failure**. Nothing is delivered as a bitmap that reports the payload’s values. This includes a copy of a valid buffer whose first byte was changed to 2, and a copy whose first byte was changed to 0.
- Own mode takes the allocation on every path: a successful open, an unsupported-format-version failure, and the empty-bitmap path for a too-small buffer. The caller does not free the allocation after passing it as own.
- Buffers are otherwise trusted. This feature does not grade a distinct corrupt-payload diagnostic.

**Verifiable oracle:**

- Success: emit an owning copy of a bitmap that holds the 3000 values 0, 7, 14, …, 2999×7 together with the 64-bit maximum; open it in borrow mode; membership, cardinality, min, max, and the allocated-array of values match the source, and the in-use bytes match; the copy’s first two bytes are 1 then 0; opening that copy in borrow and setting a new value leaves the copy’s bytes unchanged and a fresh open of the copy does not contain the new value; reads on a borrowed open of a 100-value bitmap succeed and leave the caller’s buffer untouched, with no allocation at all until a later set, and the emitted view is the caller’s buffer; the copying open of the same bytes placed at offset 2 in a larger allocation matches the source and a later set on the copy leaves those source bytes unchanged; own-open of a well-formed copy, before any set, emits that same allocation rather than a second buffer; setting a value that was not already present then makes that value present and raises cardinality by one; release returns the allocator’s outstanding total to the total from before the open. Whether that value fits in the original allocation is not scored.
- Failure / absence: opening does not make membership available until the caller runs a separate deserialize; a borrow open or a read before a set allocates, or builds a copy or decoded form of the buffer in other memory; first two bytes are not version 1; changing the first byte to 2 still opens and reports the old values; a 0-byte or 8-byte open fails instead of yielding empty, or a 65-byte open is treated as a version error; set on a borrowed open writes the caller’s bytes; the copying open rejects a slice that is not 8-byte aligned; own-open of a version-mismatched copy leaks the allocation (the caller is not expected to free it, and a subsequent leak check fails) or still requires the caller to free it.

---

### FP-05: Compact to the smallest canonical buffer

**Public entry:** The compact operation on a bitmap. It is optional. The README’s storage path is: mutate, compact, emit the buffer. Opening is FP-04. Compact does not change the set algebra in FP-06 and FP-07.

**Normal behavior:**

- Compact preserves membership, cardinality, minimum, maximum, and the ascending sequence of values. After compact, every value that was present is still present and no new value appears.
- Compact does not freeze the bitmap. After compact, a second set of an already-present value reports not newly added; setting a value that was not present reports newly added and that value is then present. Compact of an empty bitmap stays empty and still accepts a later set of 2^40.
- Two bitmaps that hold the same set, built by different routes — for example one built by many sets and removes that leave slack, and one built by setting only the remaining values — need **not** have identical buffers **before** compact. **After** compact, their in-use buffers are byte-identical. That is the canonical form compact exists to produce.
- The same canonical bytes are produced when a compacted bitmap is then shrunk in place by one value (by remove, by in-place difference, or by in-place intersection) and compacted again: the result matches compact of a bitmap built directly from the remaining values.
- When a bitmap is already the length that compact would produce, compact still makes the in-use bytes match a bitmap built directly from the same values and then compacted: leftover bytes of a just-removed value do not remain as a difference.
- Compact of a borrowed bitmap (already canonical, nothing to reclaim) still hands back a bitmap that owns its storage, of the same length as the caller’s buffer, without writing the caller’s buffer. Remove afterwards is then legal and still leaves the caller’s bytes unchanged.
- After a workload that inserted many values, removed some of them, and left emptied prefixes, compact shortens the emitted buffer compared with the pre-compact emit, then a second compact leaves that length unchanged.
- A compacted bitmap emits a buffer that opens (FP-04) with the same cardinality and the same value sequence.

**Boundary / error behavior:**

- Compact can fail only when a rewrite needs an allocation the allocator cannot satisfy. That outcome is not scored. A second compact of an already-canonical bitmap succeeds even when the allocator refuses the next allocation.
- Compact is not cleanup (FP-07). Cleanup reclaims emptied prefixes without promising byte-identical canonical form across construction routes. Compact is the step that makes equal sets byte-identical.

**Verifiable oracle:**

- Success: a bitmap filled with a mix of a dense low prefix, a mid prefix, and many one-or-two-value high prefixes, then compacted, has a strictly shorter emitted buffer, the same sorted value list as before, and still accepts two thousand new values under a fresh high prefix without dropping the old values; a second compact of that bitmap, before those new values are set, leaves the emitted length unchanged even when the allocator is set to refuse the next allocation; an empty compact stays empty and then contains 2^40 after a set; two bitmaps of the same remaining set — one built by inserting extras and removing them, one built from the sorted remainder — have identical in-use bytes after compact; a borrowed already-canonical buffer, compacted, can remove 99 without writing the caller’s bytes; emit-after-compact opens with the same values.
- Failure / absence: compact drops or adds members; compact after which a further set is refused or ignored; two equal sets still differ byte-for-byte after both are compacted; compact of a borrowed bitmap writes the caller’s bytes; compact is a no-op on a bitmap full of slack so the emitted length never shrinks after a slack-producing workload.

---

### FP-06: Materializing intersection, union, and n-ary union

**Public entry:** The two-operand intersection that returns a new bitmap; the two-operand union that returns a new bitmap; and the n-ary union, which takes a list of bitmaps (including the empty list and a one-element list) and returns a new bitmap equal to their union. In-place forms are FP-07. Fused counts are FP-08.

**Normal behavior:**

- Intersection of A and B is the set of values present in both. Union of A and B is the set of values present in either. Neither operand is mutated. Cardinality, membership, minimum, maximum, and the iterator of the result match that set.
- Intersection of two bitmaps that share no values is empty. Intersection of a bitmap with itself (two references to bitmaps holding the same values, including the same bitmap passed as both operands) equals that set. Intersection of a non-empty bitmap with an empty bitmap is empty, either operand order.
- Union of a bitmap with an empty bitmap equals the non-empty side, either operand order. Union of a bitmap with itself equals that set. Union is the same set either operand order.
- N-ary union of an empty list is an empty bitmap. N-ary union of a one-element list is an independent copy of that one bitmap: setting 2^40 on the result does not make 2^40 present on the input. N-ary union of many bitmaps equals folding two-operand union across those inputs, including when the inputs share no prefixes, when they all pile into one prefix, and when some inputs are empty or have had every value removed.
- The result is a usable bitmap: it can be compacted (FP-05), emitted and opened (FP-04), and mutated with set and remove (FP-02). An intersection result opens from its emitted buffer with the same values, byte-identical on the in-use region.

**Boundary / error behavior:**

- N-ary union of inputs that hold nothing (empty bitmaps, or bitmaps whose values were all removed) is empty, and that result still accepts a later set.
- Construction of a result can fail only when the allocator cannot satisfy the request. That outcome is not scored.

**Verifiable oracle:**

- Success: for random pairs of 1500-value sets, the intersection result’s membership equals the set-intersection of the two inputs and both inputs still match their originals; the union result equals the set-union and is independent of operand order; intersection of disjoint four-value bitmaps is empty; intersection or union of a bitmap with an empty bitmap matches the empty or non-empty identity above; n-ary union of no inputs is empty; n-ary union of one bitmap with values 0, 3, 2^16, 2^48 matches that set and is not aliased with the input; n-ary union of sixty random bitmaps matches a fold of two-operand union; an intersection that keeps some values under a dense prefix and some under 2^32 / 2^48, and drops a prefix present on only one side, emits a buffer that reopens with the same sorted values and the same in-use bytes.
- Failure / absence: intersection mutates an operand; union depends on operand order; n-ary union of one input is the input itself so mutating the result changes the input; n-ary union of many bitmaps drops a prefix that only one input held; disjoint intersection is non-empty; empty list n-ary union fails instead of returning empty.

---

### FP-07: In-place intersection, union, difference, and cleanup

**Public entry:** The in-place intersection, in-place union, and in-place difference entries (left bitmap becomes left ∩ right, left ∪ right, or left \ right); and cleanup, which reclaims space of prefixes left empty by those operations or by remove, without changing membership.

**Normal behavior:**

- After in-place intersection, the left bitmap’s membership is exactly the intersection of the original left set and the right set. After in-place union, it is the union. After in-place difference, it is the values that were in the left and not in the right. The right bitmap is unchanged.
- In-place intersection of a bitmap with itself (left and right the same bitmap, or left and a clone of left) leaves the set unchanged. In-place difference of a bitmap with itself empties it. In-place union of a bitmap with a **distinct** clone of itself leaves the set unchanged.
- In-place intersection, union, and difference against an empty bitmap follow the same identities as FP-06: A ∩ ∅ = ∅, ∅ ∩ A = ∅, A \ ∅ = A, ∅ \ A = ∅, A ∪ ∅ = A, ∅ ∪ A = A.
- In-place intersection and in-place difference do not by themselves shorten the emitted buffer when they empty prefixes: membership and cardinality update immediately, but the emitted length stays the same until cleanup. Cleanup then shortens the buffer when an emptied prefix at or above 2^16 had been taking room, does not change membership, and leaves the bitmap usable: further sets succeed. Emptying only the prefix of values below 2^16 does not by itself make cleanup shorten the buffer. A second cleanup on an already-cleaned bitmap leaves the emitted length unchanged.
- Cleanup of a bitmap that is entirely empty stays empty and valid. Cleanup never drops the ability to set new values afterwards, including after shrinking away hundreds of emptied prefixes.
- Mixed dense and sparse operands (a long consecutive run of values below 2^16 against a handful of values below 2^16 and under 2^32) still produce the set-algebra result. In-place union that grows a dense run until it is thousands of consecutive values still matches the reference union.

**Boundary / error behavior:**

- In-place union is specified when the right bitmap is a **distinct** bitmap. Passing the same bitmap as both operands of in-place union is not a graded successful case (the two-operand union in FP-06 covers union-with-self). Passing a clone is the distinct-bitmap case and succeeds.
- In-place intersection and in-place difference on a borrowed bitmap are not specified until the bitmap owns its storage (FP-04, FP-05). In-place union on a borrowed bitmap leaves the caller’s buffer untouched, like set.
- Cleanup on a borrowed bitmap is not specified until the bitmap owns its storage.
- In-place union can fail only when an allocation cannot be satisfied. That outcome is not scored. In-place intersection, in-place difference, and cleanup succeed even when the allocator cannot satisfy a further request.

**Verifiable oracle:**

- Success: for random pairs, in-place intersection / union / difference match the corresponding reference sets and the right operand is unchanged; A ∩ A stays A; A \ A is empty; A ∪ clone(A) stays A; identities with the empty bitmap hold; after intersecting a 3000-value bitmap spread across several prefixes at or above 2^16 down to a single surviving value under one of those prefixes, cardinality is 1 while the emitted length is still the pre-intersection length, then cleanup shortens the buffer, membership of that one value remains, and setting 2^60 and 3 afterwards yields cardinality 3 and a buffer that reopens with those three values; emptying neighbouring prefixes then cleanup leaves the two end prefixes’ values and a shorter buffer; after creating 500 prefixes, removing all but 0, and cleanup, setting 800 new high-prefix values matches a reference set that contains 0 plus those 800.
- Failure / absence: in-place intersection leaves values that were only on the right; the right operand is mutated; cleanup drops the surviving value; in-place intersection already changes membership but cleanup is required before cardinality is correct; cleanup of an empty bitmap makes a later set fail; in-place difference of a bitmap with itself leaves members.

---

### FP-08: Fused intersection, union, and difference cardinalities

**Public entry:** The three fused-cardinality entries on a bitmap, each taking a second bitmap and returning a 64-bit count: how many values the intersection would contain, how many the union would contain, and how many the difference (left minus right) would contain. They do not return a bitmap. Materialized results are FP-06 and FP-07.

**Normal behavior:**

- For any two bitmaps A and B, the fused intersection count equals the cardinality of the materializing intersection of A and B, and equals the cardinality of A after in-place intersection with B (measured on a clone). The fused union count equals the cardinality of the materializing union. The fused difference count equals the cardinality of A after in-place difference with B (measured on a clone).
- Neither operand’s membership, cardinality, or emitted buffer changes.
- Against the empty bitmap: fused intersection is 0 either order; fused union is the non-empty side’s cardinality either order; fused difference is the left cardinality (so A \ ∅ is |A| and ∅ \ A is 0). Fused union of two empty bitmaps is 0.
- Against itself: fused intersection equals cardinality; fused union equals cardinality; fused difference is 0.
- Disjoint operands (no shared values, whether because prefixes miss entirely or because shared prefixes have no overlapping values): fused intersection is 0; fused union is the sum of the two cardinalities; fused difference is the left cardinality.
- Concrete overlapping consecutive runs: A is {0, 1, …, 4999} and B is {2957, 2958, …, 7956}. Fused intersection is 2043. Fused union is 7957. Fused difference A \ B is 2957. Fused difference B \ A is 2957. Identical dense runs of those 5000 values: fused intersection 5000, fused union 5000, fused difference 0.
- Dense 0 through 3999 plus 2^32 against sparse {5, 4000, 4001, 2^32}: fused intersection is 2 either order.
- A left bitmap whose values were all removed in place (cardinality already 0, cleanup not yet run) still reports fused intersection 0 with a non-empty right, fused union equal to the right’s cardinality, and fused difference 0.

**Boundary / error behavior:**

- These entries cannot fail. They do not produce a bitmap the caller must release.
- Operand order matters for difference and is observable: the fused difference count follows the left operand, and the two directions are different counts when the left-minus-right sizes differ. Intersection and union counts do not depend on operand order.

**Verifiable oracle:**

- Success: for random pairs, each fused count equals the cardinality of the corresponding materialized result, both operand orders, and both operands still match their pre-call membership; the empty / self / disjoint identities above hold on the set {0, 7, 2^16, 2^32+5, 64-bit maximum}; A = 0..4999 and B = 2957..7956 yield fused intersection 2043, fused union 7957, fused difference 2957 each way; dense 0 through 3999 plus 2^32 against sparse {5, 4000, 4001, 2^32} yields fused intersection 2 either order; a clone emptied by in-place intersection still fuses as the empty set.
- Failure / absence: fused intersection returns a bitmap instead of a count, or a count that disagrees with the materialized intersection; operands are mutated; the two difference directions are equal when the left-minus-right sizes differ; the 0..4999 vs 2957..7956 case returns anything other than fused intersection 2043, fused union 7957, and fused difference 2957 either way; emptied-but-not-cleaned left side still counts stale members.

---

### FP-09: Build a bitmap from a sorted list

**Public entry:** The entry that takes a memory allocator and a sequence of 64-bit unsigned integers that is **non-decreasing**, and returns a new owned bitmap holding the unique values. Repeated set (FP-02) remains the way to build from an unsorted stream.

**Normal behavior:**

- The result’s membership is the unique values in the list. Duplicates in the list are ignored: a list that repeats a value still counts it once. Cardinality equals the number of distinct values. Minimum is the first distinct value; maximum is the last. The iterator and the allocated-array entry (FP-03) match the sorted unique list.
- An empty list yields an empty bitmap, the same as FP-01’s constructor, still usable for later sets.
- A one-element list holding the maximum 64-bit unsigned integer yields cardinality 1 and membership true for that value.
- A list that packs thousands of values under one prefix and also includes other prefixes, with duplicates, matches a bitmap built by setting each list element in turn, and matches a reference set of those elements. Emitting its buffer and opening it (FP-04) reproduces the same in-use bytes and the same membership.
- A list of 5000 values, each under a distinct high prefix (value i lives at (i shifted up by 32 bits) plus i mod 1000), yields cardinality 5000, minimum the first element, maximum the last, and membership of every element.

**Boundary / error behavior:**

- The entry is specified for a non-decreasing sequence. Behavior on a sequence that decreases at some adjacent pair is not a graded failure mode (debug builds may refuse; that refusal is not a product oracle).
- Construction can fail only when the allocator cannot satisfy the request. That outcome is not scored.

**Verifiable oracle:**

- Success: a 6000-element non-decreasing list that repeats values under 2^32 enough times to be dense there, plus scattered other prefixes, yields the same sorted unique array as setting each element on a fresh bitmap, and a borrowed open of its emitted copy has the same in-use bytes; an empty list is empty; a single-element list of the 64-bit maximum contains only that value; 5000 prefix-distinct sorted values are all present with that cardinality, min, and max.
- Failure / absence: duplicates in the list increase cardinality above the unique count; empty list fails; the 64-bit maximum cannot be the sole member; a buffer round-trip of the built bitmap disagrees with the source bitmap’s in-use bytes; building from the sorted unique list disagrees with setting the same values one by one.
