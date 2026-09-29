### Product overview

`klyvmap` is a Zig library of roaring bitmaps over 64-bit unsigned integers. The in-memory form of a bitmap is the serialized form: one flat, 8-byte-aligned byte buffer that can be stored or sent as-is. Opening that buffer does not convert it into a second in-memory form, and reads do not require a separate deserialize step. The first `set` on a bitmap opened with `fromBuffer` under `borrow` leaves the caller’s buffer byte-identical to the bytes that were opened.

The product is a 64-bit roaring bitmap only. It does not offer a run-length packing of consecutive values. It does not implement CRoaring portable or frozen interchange formats. A format version is stamped into every buffer and is independent of the library’s calendar release version; buffers that share a format version read each other. That format-version integer, and which values opening accepts or refuses, belong in the product requirements, not here.

A first-time integrator creates an empty bitmap with the library’s constructor, clones it, mutates membership, emits the buffer, opens that buffer again, and releases both owned and borrowed bitmaps. A bitmap that already contains 0 when fresh, that reports minimum 0 while empty, that has no buffer when empty, whose clone aliases the original, or whose borrowed release frees or overwrites the caller’s bytes, is a failure of the product.

The names below are the module, the bitmap type, and the constructor / clone / release / query / emit / open spellings a caller uses to reach that product. Algebra, compact, iteration, and bulk-build entries are separate public surfaces.

### Shape of the public surface

The product is an **importable Zig library**, not a command-line program, not a network service, and not a wire protocol. There is no published console binary. Integrators compile a Zig program that depends on the Zig module named `klyvmap`. The module root source file, relative to the repository root, is `src/klyvmap.zig`.

Callers write `@import("`klyvmap`")` and then use `klyvmap`.`Bitmap`. Attaching the module at compile time uses that same module name with the root source above (Zig `--dep` / `-M` form). Importing the module performs no file I/O, starts no processes, and opens no sockets. Library operations themselves perform no file or network I/O: callers pass a memory allocator and, when opening, a byte buffer.

The toolchain is Zig 0.16. The on-disk format is little-endian by definition. Big-endian targets are refused at compile time. A program that does not import the product may still compile for a big-endian target; a program that imports `klyvmap` and constructs a `Bitmap` does not compile for a big-endian target. Platforms are little-endian hosts the toolchain supports (including x86-64 and ARM64). Hardware is CPU-only. There is no 32-bit variant.

There is no product-owned configuration file.

### Naming conventions

**Product and module.** The product identity and the Zig module name are both spelled `klyvmap`. The module root file name is `src/klyvmap.zig`.

**Bitmap type.** The published bitmap type is `Bitmap` on that module: `klyvmap`.`Bitmap`.

**Constructor, clone, and release.** A new owned empty bitmap is `init`, which takes a memory allocator. Release is `deinit`. An independent owned copy is `clone`. These are methods / associated functions of `Bitmap`, not free functions on the module root.

**Membership and queries used with those entries.** `set` adds a 64-bit unsigned integer. `contains` reports membership. `remove` deletes a present value. `isEmpty` is emptiness. `getCardinality` is the number of distinct present values. `minimum` and `maximum` are extrema; on an empty bitmap both are absent, not the integer 0.

**Buffer emit and open.** `toBuffer` returns a borrowed view of the bitmap’s buffer. `toBufferCopy` returns an owning copy allocated from a caller-supplied allocator. `fromBuffer` opens a buffer. The open-mode argument that leaves the caller owning the bytes is the enum member `borrow`. The open-mode argument that transfers the buffer to the bitmap is the enum member `own`. Callers spell the borrow mode as `.`borrow``.

**Integer domain.** Values are 64-bit unsigned integers. 0 is a legal value.

### Published type and entries

The module `klyvmap` exposes the type `Bitmap`. Callers construct, clone, query, emit, open, and release it as follows. Parameter names in the blocks below match the published signatures.

```
pub fn init(allocator: std.mem.Allocator) !Bitmap
```

`init` takes a memory allocator and returns a `Bitmap` the caller owns, or fails when the allocator cannot satisfy the request. That out-of-memory outcome is an allocator failure, not a product boundary. The returned bitmap holds no values.

```
pub fn deinit(self: *Bitmap) void
```

`deinit` releases a bitmap. When the bitmap owns its buffer, the buffer is freed back to the allocator that created it. When the bitmap only borrows, `deinit` does not free and does not overwrite the caller’s buffer. It is safe on a borrowed bitmap.

```
pub fn clone(self: *const Bitmap) !Bitmap
```

`clone` returns a second, independent, owned `Bitmap` that holds the same values. It uses the source bitmap’s allocator. Mutating the clone does not change the original, and mutating the original does not change the clone. Clone of an empty bitmap is an empty bitmap, still distinct from the original.

```
pub fn isEmpty(self: *const Bitmap) bool
```

`isEmpty` is true exactly when the bitmap holds no values.

```
pub fn getCardinality(self: *const Bitmap) u64
```

`getCardinality` is the number of distinct present values. On a fresh bitmap it is 0.

```
pub fn contains(self: *const Bitmap, x: u64) bool
```

`contains` is true exactly for values that have been set and not since removed. On a fresh bitmap, `contains` of 0 is false: 0 is a legal value that is simply not present yet.

```
pub fn minimum(self: *const Bitmap) ?u64
pub fn maximum(self: *const Bitmap) ?u64
```

`minimum` is the smallest present value; `maximum` is the largest. On an empty bitmap both are absent, not the integer 0.

```
pub fn set(self: *Bitmap, x: u64) !bool
```

`set` adds a 64-bit unsigned integer. It is fallible (allocator). The boolean result reports whether the value was newly added. A second `set` of the same value does not create a second copy.

```
pub fn remove(self: *Bitmap, x: u64) bool
```

`remove` deletes a value if it is present and reports whether it was present. It is not an error union.

```
pub fn toBuffer(self: *const Bitmap) []align(8) const u8
```

`toBuffer` returns a borrowed view of the bitmap’s buffer. The view is invalidated by growth or by `deinit`. Length is positive even when the bitmap is empty: there is no null-buffer special case for empty.

```
pub fn toBufferCopy(self: *const Bitmap, allocator: std.mem.Allocator) ![]align(8) u8
```

`toBufferCopy` returns an owning copy of that buffer, allocated from the caller-supplied allocator. The caller frees that copy.

```
pub fn fromBuffer(allocator: std.mem.Allocator, buf: []align(8) const u8, ownership) !Bitmap
```

`fromBuffer` opens the byte buffer. The third argument is the open mode whose members are `borrow` and `own`. Under `borrow`, the caller keeps the buffer; the bitmap never writes it and never frees it; the buffer must outlive the bitmap. Callers pass `.`borrow`` for that mode. Opening a buffer this product emitted, under either mode, allocates nothing through `allocator` and does not copy, index, or decode the buffer’s contents into any other memory; `contains`, `getCardinality`, `isEmpty`, `minimum`, `maximum`, `iterator` / `next`, and `toBuffer` on the opened bitmap allocate nothing either until the first `set`. Until that `set`, `toBuffer` of the opened bitmap is `buf` itself: the same address and the same length. Opening an emitted empty buffer under `borrow` yields a bitmap that is still empty and still usable: a later `set` makes that value present. Releasing a borrowed open leaves the caller’s bytes intact for a second open.

### Global observables an implementer must reproduce

**Fresh bitmap.** A newly created bitmap reports empty, cardinality 0, no minimum, no maximum, and not-contains 0. Delivering the integer 0 as minimum or maximum is not absence.

**Empty emit and reopen.** Emitting that empty bitmap’s buffer yields a buffer whose length is strictly greater than 0. Opening that buffer again yields a bitmap that is still empty. A later `set` on that reopened bitmap makes that value present. A sibling bitmap that holds other values does not leak into an empty reopen.

**Clone independence.** The clone holds the same values as the original at the moment of cloning. A later `set` on the clone does not make that value present on the original. A later `remove` on the original does not remove that value from the clone. Clone of empty stays empty on the original after a `set` on the clone.

**Owned release.** `init` takes memory from the caller allocator. `deinit` of that owned bitmap returns live bytes to the pre-construct baseline.

**Borrowed release.** `deinit` of a bitmap opened with `fromBuffer` under `borrow` does not change caller-allocator live bytes and does not overwrite the caller’s buffer. The same bytes can be opened a second time.

**No file I/O.** Create, clone, emit, open, and release write no files under the process working directory, the caller home directory, or the process temporary directory.

**No network I/O.** Create, clone, and release issue no socket, connect, bind, listen, or accept-family system calls.

**Endianness.** Big-endian compile targets are refused at compile time when the product module is imported. Little-endian hosts compile successfully.

**Independent constructors.** A second `init` returns a distinct empty bitmap. Values present on a first bitmap do not appear on a second fresh bitmap.

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

## `iterator`

### iterator

`iterator` is a method of `klyvmap`.`Bitmap`. Callers write `bm.iterator()`. It takes no extra arguments. The result is a `Iterator`, typed as `klyvmap`.`Iterator`.

```
pub fn iterator(self: *const Bitmap) Iterator
```

A later `next` on that iterator yields each present value once, in strictly ascending order, then reports exhaustion. Insert order does not change yield order.

**Empty.** On a bitmap that holds no values, the first `next` is exhaustion, and the next `next` is still exhaustion.

**Zero is a real yield.** Exhaustion is distinct from yielding 0. A bitmap that contains only 0 yields 0 on the first pull, then exhaustion, and a pull after that is still exhaustion. A bitmap that contains 0 and 2^32 yields 0, then 2^32, then exhaustion. A dense consecutive run that includes 0 still yields 0 first, then 1, 2, through the last present value, then exhaustion. 0 is not treated as “done”.

**Removed values and emptied prefixes.** After setting 5, 2^16, and 2×2^16, then removing 2^16, the walk yields 5 then 2×2^16 then exhaustion. Removed values and prefixes that currently hold no values do not appear. After removing every value in a low consecutive run, the first yield is the smallest remaining value, not a removed low value.

**Lifetime.** The iterator is valid until the bitmap is mutated. Behavior of an iterator used after a mutation of its bitmap is not specified.

**No file or network I/O.** Walking the iterator writes no files under the process working directory, the caller home directory, or the process temporary directory, and issues no socket, connect, bind, listen, or accept-family system calls.

## `Iterator`

### Iterator

`Iterator` is a published type on the module `klyvmap`. Callers spell it `klyvmap`.`Iterator`. They do not construct it directly: `Bitmap`.`iterator` returns it.

The walk method on that type is `next`. Callers hold a `klyvmap`.`Iterator` and pull values until `next` reports exhaustion.

`next` yields each present 64-bit unsigned integer once, in strictly ascending order. Exhaustion is the optional-absent outcome, spelled `null`, and is distinct from yielding 0. A bitmap that contains 0 yields 0 as a real first value. A second pull after exhaustion is still exhaustion.

## `next`

### next

`next` is a method of `klyvmap`.`Iterator`. Callers write `it.next()`. It takes no extra arguments.

```
pub fn next(self: *Iterator) ?u64
```

The result is an optional 64-bit unsigned integer. A present result is the next value in strictly ascending order. Exhaustion is the absent outcome, equal to `null`, and is distinct from yielding 0.

**Zero is a value.** A bitmap that contains 0 yields 0 from `next`; that yield is not exhaustion. A later pull after the last present value is `null`, and a pull after that is still `null`.

**Empty.** On a bitmap that holds no values, the first `next` is `null` and the next `next` is still `null`.

**Named walks.** A bitmap that contains 0 and 2^32 yields 0, then 2^32, then `null`. A dense consecutive run from 0 through 4999 yields 0 first, 4999 last, then `null`. After setting 5, 2^16, and 2×2^16, then removing 2^16, `next` yields 5, then 2×2^16, then `null`. Removed values do not appear.

## `toArray`

### toArray

`toArray` is a method of `klyvmap`.`Bitmap`. Callers write `try bm.toArray(allocator)`. It takes a memory allocator and returns a slice the caller owns.

```
pub fn toArray(self: *const Bitmap, allocator: std.mem.Allocator) ![]u64
```

The slice length equals `getCardinality`. The contents are the same values as a full drain of `iterator` / `next`, in the same strictly ascending order. The caller frees that slice with the allocator that produced it. The call is fallible when the allocator cannot satisfy the request.

**Empty.** On a bitmap that holds no values, the slice has length 0.

**Named dumps.** A bitmap of 0 and 2^32 yields a slice of length 2 holding 0 then 2^32. After setting 5, 2^16, and 2×2^16, then removing 2^16, the slice has length 2 and holds 5 then 2×2^16; the removed value is absent. A mixed dense-and-scattered bitmap’s slice matches the sorted unique list of the values that were newly set. A dense consecutive run from 0 through 4999 yields a slice of length 5000 whose entries are those values in order.

**No file or network I/O.** `toArray` writes no files under the process working directory, the caller home directory, or the process temporary directory, and issues no socket, connect, bind, listen, or accept-family system calls.

## `toArrayInto`

### toArrayInto

`toArrayInto` is a method of `klyvmap`.`Bitmap`. Callers write `bm.toArrayInto(dest)`. It is not an error union.

```
pub fn toArrayInto(self: *const Bitmap, dest: []u64) void
```

The destination is a caller-supplied slice of 64-bit unsigned integers whose length equals `getCardinality`. `toArrayInto` writes every present value into that destination, in the same order as a full drain of `iterator` / `next` and the same contents as `toArray`.

**Empty.** On a bitmap that holds no values, the destination has length 0 and nothing is written.

**Reusable buffer.** Writing into a prefix of a larger buffer leaves the unused suffix untouched. A destination of the wrong length is not a specified failure mode; the specified call uses length equal to cardinality.

**Named writes.** A bitmap of 0 and 2^32 writes 0 then 2^32 into a destination of length 2. After setting 5, 2^16, and 2×2^16, then removing 2^16, a destination of length 2 receives 5 then 2×2^16 and not the removed value. A mixed dense-and-scattered bitmap writes the sorted unique list of the values that were newly set. A dense consecutive run from 0 through 4999 writes those 5000 values in order.

**No file or network I/O.** `toArrayInto` writes no files under the process working directory, the caller home directory, or the process temporary directory, and issues no socket, connect, bind, listen, or accept-family system calls.

## `fromBufferCopy`

### fromBufferCopy

`fromBufferCopy` is an associated function of `klyvmap`.`Bitmap`. Callers write `try klyvmap.Bitmap.fromBufferCopy(allocator, buf)`. It copies a byte slice into a new owned bitmap. The slice need not be 8-byte aligned.

```
pub fn fromBufferCopy(allocator: std.mem.Allocator, buf: []const u8) !Bitmap
```

The first argument is a memory allocator. The second argument is any byte slice, including a slice that starts at a non-zero offset inside a larger allocation. The result is a `Bitmap` the caller owns, or a failure that delivers no bitmap.

**Well-formed source.** A slice whose bytes are an emitted buffer of a valid bitmap opens as an owned bitmap. Membership, cardinality, minimum, and maximum match the source. The opened bitmap’s in-use bytes, read back with `toBuffer`, match the source slice. The opened view is 8-byte aligned. Opening does not write the source slice. Overwriting the source slice afterward does not change the opened bitmap’s membership, cardinality, or in-use bytes. A later `set` of a value that was absent makes that value present and does not change the source slice. Opening the source slice again does not contain that newly set value. `deinit` of the opened bitmap returns the caller allocator’s outstanding bytes to the total from before the call. The caller’s source allocation stays allocated until the caller frees it.

**Not a bitmap.** A slice whose length is not a multiple of 2, or whose length is strictly less than 64, is not a bitmap. `fromBufferCopy` of that slice yields a fresh empty `Bitmap`, not an unsupported-format-version failure. A 0-byte slice, an 8-byte slice, a 62-byte slice, and a 65-byte slice are this case, even when their first bytes look like a version. The fresh bitmap reports empty, cardinality 0, no minimum, no maximum, and not-contains 0. A later `set` makes that value present, and a later `toBuffer` is an even length of at least 64 whose first two bytes are 1 then 0. `deinit` returns the allocator’s outstanding bytes to the total from before the call. The source slice is left unchanged.

**Wrong format version.** A slice that is at least 64 bytes and even-length, but whose first two bytes are not the little-endian encoding of 1, fails. No bitmap is delivered, and the payload’s values are not reported. This includes a copy of a valid buffer whose first byte is 2, whose first byte is 0, whose second byte is not 0, or whose first two bytes are 0 then 1. The source slice is left unchanged.

**No file or network I/O.** `fromBufferCopy` writes no files under the process working directory, the caller home directory, or the process temporary directory, and issues no socket, connect, bind, listen, or accept-family system calls.

## `compact`

### compact

`compact` is a method of `klyvmap`.`Bitmap`. Callers write `try bm.compact()`. It takes no arguments besides the bitmap and returns nothing on success. It is fallible.

```
pub fn compact(self: *Bitmap) !void
```

**After a borrowed open.** Open an emitted buffer with `fromBuffer` under `borrow`, then call `compact`. The caller’s buffer is left byte-identical to the bytes that were opened. The bitmap then owns storage of its own: `toBuffer` has length at least 64, and the allocator’s outstanding bytes have grown by at least that length. Overwriting the caller’s buffer afterward does not change the bitmap’s `getCardinality` or its `toBuffer` bytes.

The result stays mutable. `set` of a value that was absent succeeds, `contains` reports that value, and `getCardinality` is one greater than before that `set`. `deinit` returns the allocator’s outstanding bytes to the total from before `compact`. It does not free the caller’s buffer. A later `fromBuffer` of that same caller buffer under `borrow` still reports the values that were present at the open, and does not contain the value added after `compact`. The caller’s buffer is still byte-identical to the bytes that were opened.

## `andInPlace`

### andInPlace

`andInPlace` is a method of `klyvmap`.`Bitmap`. Callers write `bm.andInPlace(&other)`. It takes a pointer to another bitmap and returns nothing. It cannot fail.

```
pub fn andInPlace(self: *Bitmap, other: *const Bitmap) void
```

The left bitmap’s membership becomes the values present in both bitmaps. `getCardinality` becomes the number of those values. The other bitmap is unchanged. The call succeeds even when the allocator cannot satisfy a further request. On a borrowed bitmap the operation is not specified until the bitmap owns its storage.

**Drop one present value.** The other bitmap holds every value of the left bitmap except one value that was present. After `andInPlace`, that value is absent, the remaining values are still present, and `getCardinality` equals the number of remaining values. A following `compact` makes the in-use bytes from `toBuffer` match `compact` of a bitmap built by `set` of only those remaining values.

## `andNotInPlace`

### andNotInPlace

`andNotInPlace` is a method of `klyvmap`.`Bitmap`. Callers write `bm.andNotInPlace(&other)`. It takes a pointer to another bitmap and returns nothing. It cannot fail.

```
pub fn andNotInPlace(self: *Bitmap, other: *const Bitmap) void
```

The left bitmap’s membership becomes the values that were present on the left and absent from the other bitmap. `getCardinality` becomes the number of those values. The other bitmap is unchanged. The call succeeds even when the allocator cannot satisfy a further request. On a borrowed bitmap the operation is not specified until the bitmap owns its storage.

**Drop one present value.** The other bitmap holds exactly one value that is present on the left. After `andNotInPlace`, that value is absent, every other value that was present stays present, and `getCardinality` equals the number of remaining values. A following `compact` makes the in-use bytes from `toBuffer` match `compact` of a bitmap built by `set` of only those remaining values.

## `And`

### And

`And` is an associated function of `klyvmap`.`Bitmap`. Callers write `klyvmap.Bitmap.And(allocator, &a, &b)`. It builds a new bitmap owned by the caller and does not change either operand. The caller releases the result with `deinit`.

```
pub fn And(
    allocator: std.mem.Allocator,
    a: *const Bitmap,
    b: *const Bitmap,
) !Bitmap
```

The result holds exactly the values present in both operands. `getCardinality` is the number of those values. `contains` is true for each of them and false for a value present on only one side or on neither. `minimum` and `maximum` are the smallest and largest values of that set. `iterator` yields those values once, in ascending order. Swapping the two operands yields the same set. Both operands still hold the values they held before the call.

**Nothing in common.** Two bitmaps that share no values produce an empty result: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent. A following `iterator` is exhausted on the first pull and on a second pull.

**With itself.** Passing the same bitmap as both operands, or two bitmaps that hold the same values, produces that set. Setting a new value on the result does not make that value present on the operand.

**With an empty bitmap.** Intersection of a non-empty bitmap and an empty bitmap is empty, in either operand order. The non-empty operand is unchanged. The empty operand stays empty.

The result is a usable bitmap. `set` and `remove` change it without changing the operands. `compact` preserves its membership. `toBuffer` emits a buffer that `fromBufferCopy` opens with the same values, and the opened bitmap’s in-use bytes match that emit.

Construction fails only when the allocator cannot satisfy the request.

## `Or`

### Or

`Or` is an associated function of `klyvmap`.`Bitmap`. Callers write `klyvmap.Bitmap.Or(allocator, &a, &b)`. It builds a new bitmap owned by the caller and does not change either operand. The caller releases the result with `deinit`.

```
pub fn Or(
    allocator: std.mem.Allocator,
    a: *const Bitmap,
    b: *const Bitmap,
) !Bitmap
```

The result holds exactly the values present in either operand. `getCardinality` is the number of those values. `contains` is true for each of them and false for a value present in neither. `minimum` and `maximum` are the smallest and largest values of that set. `iterator` yields those values once, in ascending order. Swapping the two operands yields the same set. Both operands still hold the values they held before the call.

**With an empty bitmap.** Union of a non-empty bitmap and an empty bitmap equals the non-empty side, in either operand order. The result is a new bitmap: `set` of a value that was absent puts that value on the result and leaves both operands unchanged, including the empty operand staying empty.

**With itself.** Passing the same bitmap as both operands produces that set. `set` of a new value on the result does not make that value present on the operand, and the operand’s ascending sequence is unchanged.

The result is a usable bitmap. `set` and `remove` change it without changing the operands. `compact` preserves its membership. `toBuffer` emits a buffer that `fromBufferCopy` opens with the same values, and the opened bitmap’s in-use bytes match that emit.

Construction fails only when the allocator cannot satisfy the request.

## `fastOr`

### fastOr

`fastOr` is an associated function of `klyvmap`.`Bitmap`. Callers write `klyvmap.Bitmap.fastOr(allocator, &bitmaps)`, where the second argument is a slice of pointers to bitmaps (`[]const *const Bitmap`), including a zero-length slice and a one-element slice. It builds a new bitmap owned by the caller and does not change any input. The caller releases the result with `deinit`.

```
pub fn fastOr(
    allocator: std.mem.Allocator,
    bitmaps: []const *const Bitmap,
) !Bitmap
```

The result is the union of the inputs: a value is present when it is present on at least one input. `getCardinality`, `contains`, `minimum`, `maximum`, and `iterator` match that set. Reversing the slice yields the same set. Folding the same inputs with two-operand `Or` yields the same set, including when the inputs share no high prefixes, when they pile into one prefix, and when some inputs are empty or have had every value removed.

**Empty list.** A zero-length slice returns an empty bitmap: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent. A following `iterator` is exhausted on the first pull and on a second pull. `set` of a new value then reports newly added, that value is present, and `getCardinality` is 1. A second call on a zero-length slice is a separate empty bitmap and does not contain the value set on the first result.

**One bitmap.** A one-element slice is an independent copy of that bitmap, not the input itself. For inputs holding 0, 3, 2^16, and 2^48, the result contains those four values, does not contain a value absent from the input, and its ascending sequence starts at 0. `set` of 2^40 on the result makes 2^40 present on the result and leaves it absent from the input. The input’s ascending sequence is unchanged.

**Inputs that hold nothing.** A list of empty bitmaps, or of bitmaps whose values were all removed, returns an empty bitmap. That result still accepts a later `set`.

The result is a usable bitmap. `set` and `remove` change it without changing the inputs. `compact` preserves its membership. `toBuffer` emits a buffer that `fromBufferCopy` opens with the same values, and the opened bitmap’s in-use bytes match that emit.

Construction fails only when the allocator cannot satisfy the request.

## `orInPlace`

### orInPlace

`orInPlace` is a method of `klyvmap`.`Bitmap`. Callers write `try left.orInPlace(&right)`. The argument is a pointer to another bitmap. Success returns nothing. The call can fail.

```
pub fn orInPlace(self: *Bitmap, other: *const Bitmap) !void
```

The left bitmap’s membership becomes the values present in either bitmap. `getCardinality` is the number of those values. `contains` is true for each of them and false for a value present in neither. `minimum` and `maximum` are the smallest and largest values of that set. `iterator` yields those values once, in ascending order, including when the smallest value is 0. The other bitmap is unchanged. Either bitmap may be the left operand: swapping them yields the same set on whichever side is written.

The call is specified when the other bitmap is a distinct bitmap. A distinct `clone` of the left bitmap leaves the set unchanged on the left and leaves the clone unchanged.

**With an empty bitmap.** Union with an empty bitmap equals the non-empty side, in either operand order. An empty bitmap created with `init` stays empty when it is the right operand. When the empty bitmap is the left operand, it becomes the other bitmap’s set and the other bitmap is unchanged.

**One prefix.** Two bitmaps whose values all sit under one prefix at or above 2^16 still follow that union: shared values stay, values that were only on one side appear on the left, and the right bitmap is unchanged.

**Dense and sparse.** A consecutive run of at least 1000 values below 2^16, against a handful that includes a value inside that run, a value below 2^16 outside that run, and a value at or above 2^16 and below 2^32, still matches the reference union, with either bitmap on the left.

**Growing a run.** Two adjacent runs below 2^16, neither of which is the whole result, become one consecutive run of at least 5000 values. Cardinality, minimum, maximum, membership, and the ascending sequence match that run. The right bitmap is unchanged.

**Borrowed bitmap.** On a bitmap opened with `fromBuffer` under `borrow`, the call leaves the caller’s buffer byte-identical. Opening that same buffer again under `borrow` still shows the values the caller stored, not the union. The left bitmap itself holds the union. The right bitmap is unchanged.

The call performs no file I/O and no network I/O.

It fails only when the allocator cannot satisfy the request.

## `cleanup`

### cleanup

`cleanup` is a method of `klyvmap`.`Bitmap`. Callers write `bm.cleanup()`. It takes no arguments and returns nothing. It cannot fail.

```
pub fn cleanup(self: *Bitmap) void
```

It reclaims space of prefixes left empty by `andInPlace`, `andNotInPlace`, or `remove`, without changing membership. `getCardinality`, `contains`, `minimum`, `maximum`, and `iterator` stay the set that was already present. A following `toBuffer` still opens with `fromBuffer` under `borrow` as that same set.

**Emitted length.** `andInPlace` and `andNotInPlace` update membership and cardinality immediately. They do not by themselves shorten `toBuffer` when they empty prefixes. After they empty a prefix at or above 2^16 that had been taking room, `cleanup` makes `toBuffer` strictly shorter and leaves the surviving values present. A second `cleanup` on that bitmap leaves the emitted length unchanged and leaves those values present.

Emptying only the prefix of values below 2^16 does not by itself make `cleanup` shorten the buffer. Values on higher prefixes that remain stay present, and the low-prefix values that were removed stay absent. This holds after a preceding `compact`, both when intersection drops the low prefix and when difference drops the low prefix.

Emptying four neighbouring prefixes at or above 2^16 down to the two end prefixes keeps both ends, drops the two middle prefixes, and shortens the buffer. Opening the buffer shows the two ends.

**Empty bitmap.** `cleanup` of a fresh bitmap from `init` stays empty: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent. A following `set` reports newly added, that value is present, and cardinality is 1. The same holds after `andNotInPlace` of a bitmap with itself, and after `andInPlace` that removes every value: the bitmap stays empty through `cleanup`, an open of the buffer does not contain the removed values, and a later `set` still succeeds. When that intersection emptied prefixes at or above 2^16, the emitted length stays the same until `cleanup` and is strictly shorter afterwards.

**Many emptied prefixes.** A bitmap that holds 0 together with one value on each of 499 other prefixes, after `remove` of every value except 0 and then `cleanup`, still contains 0, has cardinality 1, and opens as only 0. Setting 800 new values, each under its own prefix at or above 2^16, reports each as newly added. Cardinality is 801, `minimum` is 0, every new value is present, none of the removed values return, and the ascending sequence starts at 0.

After at least 600 prefixes at or above 2^16 are reduced by `andInPlace` to one surviving value, the emitted length stays the same until `cleanup` and is strictly shorter afterwards. The survivor stays present. A following `set` of a new value leaves both present and leaves the dropped values absent.

**Further sets.** Intersecting a 3000-value bitmap spread across prefixes at or above 2^16 down to one surviving value, then `cleanup`, keeps that value and shortens the buffer. A following `set` of 2^60 and of 3 reports both newly added. Cardinality is 3. Those three values are present, a value that was never set is absent, and opening the buffer shows those three values in ascending order. The address of the buffer `toBuffer` returns is a multiple of 8.

**Allocator.** `cleanup` succeeds even when the allocator cannot satisfy a further request. In that window it still shortens the buffer after an intersection that emptied a prefix at or above 2^16, and the surviving value remains. Opening the buffer shows that survivor.

On a borrowed bitmap the operation is not specified until the bitmap owns its storage.

The call performs no file I/O and no network I/O.

## `andCardinality`

### andCardinality

`andCardinality` is a method of `klyvmap`.`Bitmap`. Callers write `left.andCardinality(right)` when `right` is already a pointer, and `bm.andCardinality(&other)` when `other` is a bitmap value. It returns a 64-bit count. It does not return a bitmap. It cannot fail.

```
pub fn andCardinality(self: *const Bitmap, other: *const Bitmap) u64
```

The count is how many values are present in both bitmaps. It equals `getCardinality` of the bitmap `And` would build from the same two operands, and equals `getCardinality` of a `clone` of the left bitmap after `andInPlace` with the right. Swapping the operands yields the same count. Passing the same bitmap as both operands yields that bitmap’s cardinality.

Neither operand changes. Membership, `getCardinality`, and the bytes `toBuffer` emits stay as they were. The call does not allocate, so it still returns that count when the allocator cannot satisfy a further request. It performs no file I/O and no network I/O. On a bitmap opened with `fromBuffer` under `borrow`, the caller’s buffer stays byte-identical, and opening that buffer again under `borrow` still shows the values the caller stored.

**Empty.** Intersection with an empty bitmap from `init` is 0, in either operand order. Intersection of two empty bitmaps is 0. An empty bitmap stays empty: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent.

**Named set.** On the set {0, 7, 2^16, 2^32+5, the 64-bit maximum}, intersection with itself is 5. Intersection with an empty bitmap is 0.

**Disjoint.** When the two bitmaps share no value, the count is 0. That includes prefixes that miss entirely, and a shared prefix that holds no common value. One shared value inside a single prefix above 2^32 counts as 1.

**Runs.** The consecutive run 0 through 4999 against 2957 through 7956 counts 2043. Two identical runs of those 5000 values count 5000. The run 0 through 3999 plus 2^32, against {5, 4000, 4001, 2^32}, counts 2 in either operand order. Consecutive runs that cross a prefix boundary still count the ordinary number of shared values.

**Emptied but not cleaned.** A bitmap whose values were all removed by `andInPlace`, so `getCardinality` is already 0 and `cleanup` has not run, counts as empty: intersection with a non-empty bitmap is 0 in either operand order. The removed values stay absent.

## `orCardinality`

### orCardinality

`orCardinality` is a method of `klyvmap`.`Bitmap`. Callers write `left.orCardinality(right)` when `right` is already a pointer, and `bm.orCardinality(&other)` when `other` is a bitmap value. It returns a 64-bit count. It does not return a bitmap. It cannot fail.

```
pub fn orCardinality(self: *const Bitmap, other: *const Bitmap) u64
```

The count is how many values are present in either bitmap. It equals `getCardinality` of the bitmap `Or` would build from the same two operands. Swapping the operands yields the same count. Passing the same bitmap as both operands yields that bitmap’s cardinality. When the bitmaps share no value, the count is the sum of the two cardinalities.

Neither operand changes. Membership, `getCardinality`, and the bytes `toBuffer` emits stay as they were. The call does not allocate, so it still returns that count when the allocator cannot satisfy a further request. It performs no file I/O and no network I/O. On a bitmap opened with `fromBuffer` under `borrow`, the caller’s buffer stays byte-identical, and opening that buffer again under `borrow` still shows the values the caller stored.

**Empty.** Union with an empty bitmap from `init` equals the non-empty side’s cardinality, in either operand order. Union of two empty bitmaps is 0. An empty bitmap stays empty: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent.

**Named set.** On the set {0, 7, 2^16, 2^32+5, the 64-bit maximum}, union with itself is 5. Union with an empty bitmap is 5.

**Disjoint and one prefix.** Prefixes that miss entirely, and a shared prefix that holds no common value, count the sum of the two cardinalities. Three distinct values inside one prefix above 2^32 count as 3.

**Runs.** The consecutive run 0 through 4999 against 2957 through 7956 counts 7957. Two identical runs of those 5000 values count 5000. Consecutive runs that cross a prefix boundary still count the ordinary number of distinct values in either run.

**Emptied but not cleaned.** A bitmap whose values were all removed by `andInPlace`, so `getCardinality` is already 0 and `cleanup` has not run, counts as empty. Union with a non-empty bitmap equals that non-empty cardinality, in either operand order. The removed values stay absent.

## `andNotCardinality`

### andNotCardinality

`andNotCardinality` is a method of `klyvmap`.`Bitmap`. Callers write `left.andNotCardinality(right)` when `right` is already a pointer, and `bm.andNotCardinality(&other)` when `other` is a bitmap value. It returns a 64-bit count. It does not return a bitmap. It cannot fail.

```
pub fn andNotCardinality(self: *const Bitmap, other: *const Bitmap) u64
```

The count is how many values are present on the left and absent from the right. It equals `getCardinality` of a `clone` of the left bitmap after `andNotInPlace` with the right. Operand order matters: the count follows the left operand. Swapping the operands yields the other side’s exclusive count, and those two counts differ when the left-minus-right sizes differ. Passing the same bitmap as both operands yields 0. When the bitmaps share no value, the count is the left bitmap’s cardinality.

Neither operand changes. Membership, `getCardinality`, and the bytes `toBuffer` emits stay as they were. The call does not allocate, so it still returns that count when the allocator cannot satisfy a further request. It performs no file I/O and no network I/O. On a bitmap opened with `fromBuffer` under `borrow`, the caller’s buffer stays byte-identical, and opening that buffer again under `borrow` still shows the values the caller stored.

**Empty.** Difference of a bitmap with an empty bitmap from `init` is the left cardinality. Difference of an empty bitmap with a non-empty bitmap is 0. Difference of two empty bitmaps is 0. An empty bitmap stays empty: `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent.

**Named set.** On the set {0, 7, 2^16, 2^32+5, the 64-bit maximum}, difference with itself is 0. Difference of that set with an empty bitmap is 5. Difference of an empty bitmap with that set is 0.

**Disjoint and one prefix.** Prefixes that miss entirely, and a shared prefix that holds no common value, count the left cardinality. One exclusive value on each side of a single prefix above 2^32 counts as 1 for each operand order.

**Runs.** The consecutive run 0 through 4999 against 2957 through 7956 counts 2957 either way. Two identical runs of those 5000 values count 0. Consecutive runs that cross a prefix boundary still count the ordinary number of values present only on the left.

**Emptied but not cleaned.** A bitmap whose values were all removed by `andInPlace`, so `getCardinality` is already 0 and `cleanup` has not run, counts as empty. Difference with that bitmap on the left is 0. Difference with that bitmap on the right is the other bitmap’s cardinality. The removed values stay absent.

## `fromSortedList`

### fromSortedList

`fromSortedList` is an associated function of `klyvmap`.`Bitmap`. Callers write `try klyvmap.Bitmap.fromSortedList(allocator, &vals)`. It builds a new owned bitmap from a non-decreasing sequence of 64-bit unsigned integers. Building from an unsorted stream remains repeated `set` on a bitmap from `init`.

```
pub fn fromSortedList(allocator: std.mem.Allocator, vals: []const u64) !Bitmap
```

The first argument is a memory allocator. The second argument is a slice of 64-bit unsigned integers in which each element is greater than or equal to the element before it. An empty slice is legal. The result is a `Bitmap` the caller owns. The call fails only when the allocator cannot satisfy the request, and then it delivers no bitmap. That out-of-memory outcome is an allocator failure.

**Membership.** The bitmap holds each distinct value in the slice once. A repeated value does not add a second member. `getCardinality` equals the number of distinct values, and `isEmpty` is true exactly when that count is 0. On a non-empty result, `minimum` is the first distinct value and `maximum` is the last distinct value. `contains` is true for every distinct value in the slice and false for every value the slice does not hold, including 0 when 0 is absent from the slice.

**Same values as setting each element.** `init` followed by `set` of every slice element, duplicates included, produces a bitmap whose `toArray` contents are the sorted unique values. The bitmap `fromSortedList` returns has that same `toArray` slice: length equal to the distinct count, strictly ascending, no duplicates. A full drain of `iterator` and `next` yields those same values and then exhaustion. A further pull after exhaustion is still exhaustion. Exhaustion is a distinct outcome from the value 0. When two or more distinct values are present, the first pull is the minimum and the next pull is the following distinct value. When exactly one distinct value is present, the pull after that value is exhaustion.

**Empty slice.** A zero-length slice yields an empty bitmap with the same observations as `init`. `isEmpty` is true, `getCardinality` is 0, `contains` of 0 is false, and `minimum` and `maximum` are absent rather than the integer 0. The first iterator pull and the pull after it are both exhaustion, and neither pull is the value 0. `toArray` has length 0. The bitmap still accepts a later `set`. After `set` of one value strictly above 2^40, that value is present, `getCardinality` is 1, `isEmpty` is false, 0 is still absent, and `minimum` and `maximum` are both that value. A different value, also strictly above 2^40, stays absent.

**Only the 64-bit maximum.** A one-element slice holding the maximum 64-bit unsigned integer yields cardinality 1 and membership of that value. One less than that maximum is absent, and 0 is absent. The iterator yields that single value and the following pull is exhaustion. Two or more copies of that same maximum, and no other value, still yield cardinality 1. The number of copies is not the cardinality.

**Several distinct values, one of them repeated.** A non-decreasing slice that does not contain 0, repeats one ordinary value, and also contains both the 64-bit maximum and one less than that maximum, with at least three distinct values, yields cardinality equal to the distinct count. That count is strictly greater than 1 and strictly less than the slice length. 0 is absent. Both the maximum and one less than the maximum are present. The iterator’s second pull is a present value.

**Six thousand elements, dense in the block that starts at 2^32.** A non-decreasing slice of length 6000 that repeats values inside the closed range from 2^32 through 2^32 + 2^16 − 1, includes both endpoints of that range, and also includes values outside that range, yields cardinality equal to the distinct count. That count is strictly less than 6000. 0 is absent. Both endpoints are present. A value inside that same range that the slice does not hold is absent.

**Distinct high prefixes.** The 5000 values `(i << 32) + (i mod 1000)` for `i` from 0 through 4999 are all present. Cardinality is 5000. `minimum` is 0. `maximum` is `(4999 << 32) + 999`. `contains` of 0 is true. `contains` of 1 is false. A 64-bit value that lies under one of those prefixes (the same high 32 bits as one of the 5000 values, and a low 16-bit part the formula did not use) is absent. The same shape with another count and another modulus — element `i` is `(i << 32) + (i mod modulus)`, the first element is 0, and 1 is not an element — yields cardinality equal to that count, membership of every element, absence of 1, and absence of a value under one of those prefixes that the slice does not hold.

**Consecutive run on another prefix.** A non-decreasing slice whose first values are a consecutive run on a prefix that is neither 0 nor the block starting at 2^32, followed by values on prefixes strictly above that run, with one duplicate inside the run and one duplicate on a higher prefix, yields cardinality equal to the distinct count. That count is strictly greater than the length of the consecutive run and strictly less than the slice length. The first value of the run is present and is `minimum`. The last value of the run is present. The integer immediately after the run, still inside the same prefix, is absent. 0 is absent.

**Emitted buffer.** `toBuffer` on the result, including the empty result, has positive even length of at least 64. Its first byte is 1 and its second byte is 0. That view’s address is 8-byte aligned. `toBufferCopy` returns an owning copy whose address is 8-byte aligned. Opening that copy with `fromBuffer` under `borrow` leaves the copy byte-identical to the bytes that were opened. The opened bitmap’s `toBuffer` bytes equal the source bitmap’s `toBuffer` bytes. The opened bitmap reports the same membership, the same `getCardinality`, the same `toArray` contents, and the same iterator sequence. On the empty result, a later `set` on the built bitmap and a later `set` of a different value on the opened bitmap stay independent: each bitmap contains the value set on it, and neither contains the value set only on the other.

**Release.** The caller owns the returned bitmap and releases it with `deinit`. Releasing the built bitmap, releasing the bitmap opened from the owning copy, and freeing that copy return the caller allocator’s outstanding bytes to the total from before the call. That still holds after the later `set` on an empty result.

**No file or network I/O.** `fromSortedList` writes no files under the process working directory, the caller home directory, or the process temporary directory, and issues no socket, connect, bind, listen, or accept-family system calls. Membership queries, iteration, the allocated array, emitting the buffer, and a borrowed open of that buffer do the same.
