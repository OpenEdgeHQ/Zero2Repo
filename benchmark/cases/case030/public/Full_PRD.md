# ymlcodec — Full Product Requirements Document

## Product overview

**ymlcodec** is a YAML parser and writer for JavaScript. It reads YAML text into ordinary JavaScript values and writes JavaScript values back as YAML text. It supports the YAML 1.2 specification as the default loading dialect and the YAML 1.1 type set when the caller asks for that dialect. The product advertises that it is a complete YAML 1.2 implementation; that completeness claim is background. Graded behavior is the concrete parse, type-resolution, and dump outcomes named in the feature points below.

A common first use is to take a one-key mapping such as `answer: 42` and obtain a plain object whose `answer` property is the number 42, then write that object back to YAML. Leaving `42` as the string `42`, or writing a document that re-parses as a different value, is a failure of the product.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names and other Interface Contract details are out of scope here. Every feature point below corresponds to behavior that exists in the finished ymlcodec library. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **YAML text** | A Unicode string that the caller treats as a YAML stream (one document or several, possibly empty). |
| **Document** | One YAML document inside a stream. Documents may be separated by the document-start marker `---` and the document-end marker `...`. |
| **Single-document parse** | The library entry that accepts a stream and returns exactly one constructed value. |
| **Multi-document parse** | The library entry that accepts a stream and returns every constructed document, in order, as a list. An empty stream yields an empty list. |
| **Dump** | The library entry that serializes one JavaScript value as YAML text. |
| **Schema** | The finite set of tags that decide how a node is constructed on load and how a JavaScript value is identified on dump. The four built-in schemas are **Failsafe**, **JSON**, **Core**, and **YAML 1.1**. |
| **Tag** | A YAML type name such as `!!null`, `!!bool`, `!!int`, `!!float`, `!!str`, `!!seq`, `!!map`, or a local tag such as `!point`. An explicit tag is written on the node; an implicit tag is inferred from plain scalar text. |
| **Failsafe schema** | Only strings, sequences, and mappings. Plain scalars stay strings. |
| **JSON schema** | Failsafe plus the JSON subset of null, boolean, integer, and float. |
| **Core schema** | Failsafe plus the YAML 1.2 Core notations for null, boolean, integer, and float. This is the default schema for both parse entries. |
| **YAML 1.1 schema** | Failsafe plus the YAML 1.1 scalar notations and the extra YAML 1.1 types: `!!binary`, `!!timestamp`, `!!set`, `!!omap`, `!!pairs`, and merge keys. |
| **Plain object map** | The default `!!map` container: a plain JavaScript object. Keys that are not strings are converted to strings. Complex keys (sequences and mappings used as keys) are rejected. |
| **Real map** | An alternative `!!map` container: a JavaScript `Map` that stores each key exactly as constructed. |
| **Legacy map** | An alternative `!!map` container: a plain object that stringifies complex keys instead of rejecting them. |
| **Merge key** | The YAML 1.1 mapping key `<<`. Its value is one mapping, or a sequence of mappings, whose pairs are copied into the surrounding mapping. The Core schema does not include merge keys. |
| **Anchor / alias** | An `&name` label on a node and a later `*name` reference to that same constructed value. |
| **Core capability** | A user-observable capability that reflects ymlcodec’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

ymlcodec is a **library**. Integrators reach it by installing the ymlcodec package and calling the published parse and dump entries. A command-line convenience named `ymlcodec` can turn a YAML file into JSON text, or a JSON file into YAML text, for a quick check; it is the same parse-and-dump behavior, not a separate product, and is not a graded feature point.

The library’s public, independently verifiable surfaces are:

- Parse one YAML document from a string, or fail when the stream is empty or contains more than one document.
- Parse every document in a multi-document stream, including an empty stream.
- Choose among the four built-in schemas, or a schema the caller has extended with extra tags.
- Construct the YAML 1.2 Failsafe / JSON / Core types, and (when that schema is selected) the YAML 1.1 extra types including merge keys.
- Choose how mappings are stored: plain object, real `Map`, or legacy stringified keys.
- Serialize a JavaScript value to YAML text, with schema-aware quoting and the documented presentation choices.
- Register custom scalar, sequence, and mapping tags and use them on both load and dump.
- Cap collection nesting, alias count, and merge-key work so compact hostile documents cannot expand without bound.

Feature points below group these entries by capability. They do not invent additional products.

## Non-functional constraints

- **Form factor:** A TypeScript/JavaScript library with no compiled native extensions. A current Node.js LTS interpreter and npm are sufficient to install from this repository, run the documented bundle step, and exercise a parse against the locally built artifact.
- **Platforms:** Linux, macOS, and Windows. This case’s acceptance targets Linux with Node.js.
- **Hardware:** CPU-only. No GPU or accelerator is required or claimed. The mandatory execution substrate is a real host that can load the locally built ymlcodec artifact and run a parse of a one-key mapping.
- **Default load dialect:** YAML 1.2 Core. Merge keys and the YAML 1.1-only types are off until the caller selects the YAML 1.1 schema or adds those tags.
- **Default dump dialect:** A YAML 1.1 schema slightly extended so that YAML 1.2 octal integers (`0o…`) and exponent-only floats are treated as typed scalars when deciding whether a string needs quotes. That combination is what makes dump quoting safe across both dialects.
- **Untrusted input:** The YAML design allows a tiny document to expand into a huge object graph. The library exposes the limits in FP-07. Walking a constructed value after a successful parse (for example by converting it to JSON) is the caller’s responsibility; the library does not automatically refuse a graph that is cheap to construct but expensive to walk.
- **JavaScript-specific tags:** Tags that construct functions, regular expressions, or other JavaScript-only values are not part of this library. They live in a separate optional package and are out of scope here.

## Capability discrimination (global)

Every feature point below is a **core capability**. The mandatory substrate is a real CPU host with ymlcodec built from this repository’s sources and loaded into the test process. None of these capabilities is an accelerator-backed GPU feature.

For every feature point:

- **Present:** The loaded ymlcodec library produces the YAML 1.2 / YAML 1.1 outcomes described below.
- **Absent / hollow:** Parse always succeeds or always fails; every scalar stays a string; dump writes JSON or a single quoted blob; schemas do not change resolution; limits never fire.

Cheaper proxies (hard-coded document tables, a JSON-only parser, a YAML subset that does not implement Core integer and boolean rules, or a dumper that does not quote schema collisions) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces YAML parsing with a JSON parser for a core capability.

**Negative control (library substrate):** When the built ymlcodec artifact is deliberately removed from the module search path in an isolated subprocess, a parse of the one-key mapping `answer: 42` must fail to produce a successful ymlcodec document — a hard assertion, not a skip.

## Non-goals

- Being a JSON-only parser, or treating YAML as a thin skin over JSON.
- Shipping JavaScript-specific tags (functions, regular expressions, and similar) inside this library.
- Guaranteeing a particular nanosecond-per-document benchmark number (speed is a design goal, not a graded oracle).
- Treating the command-line convenience, the online demo, the benchmark harness, the distribution bundler, or the YAML Test Suite runner as independent product capabilities.
- Treating the low-level event stream, document tree, and tree visitor as a separate graded product. Those layers exist so advanced callers can build their own pipeline; the graded parse and dump entries already cover the outcomes a first-time integrator needs.

---

## Feature points

### FP-01: Parse YAML documents

**Public entry:** The ymlcodec library’s single-document parse entry and multi-document parse entry. The caller supplies YAML text and may supply a schema (FP-02), a source-path label for failure reports, and a JSON-parse compatibility switch for duplicate keys. Nesting, alias, and merge-key limits are specified in FP-07. Mapping-container choice is specified in FP-03.

**Normal behavior:**

- A single-document parse of `answer: 42` under the default Core schema succeeds and yields a plain object whose `answer` property is the number 42, not the string `42`.
- A single-document parse of a stream that contains exactly one document returns that document’s constructed value, including when the document is a bare scalar (`hello`), a sequence (`- a\n- b`), or a mapping.
- A leading byte-order mark is ignored: a single-document parse of the text that begins with a byte-order mark and then `foo: bar` yields the same object as a parse of `foo: bar` alone.
- A multi-document parse of a stream with two documents separated by `---` — first document `1`, second document `2` — returns a two-element list whose values are the numbers 1 and 2, in that order.
- A multi-document parse of a stream whose only content is two document-start markers (two empty documents) returns a two-element list of null values.
- A multi-document parse of empty text, or of text that is only whitespace and comments, returns an empty list.
- An alias refers to the constructed value of its anchor. A single-document parse of `base: &base { a: 1 }\ncopy: *base` yields a mapping whose `copy` value is the same object as `base` (same identity, not a separately constructed copy).
- A recursive alias is allowed for the default sequence and mapping tags: a single-document parse of `&a [*a]` succeeds, and the sole sequence item is the sequence itself.
- Duplicate keys in one mapping are rejected by default. A single-document parse of `a: 1\na: 2` fails. When JSON-parse compatibility is enabled, that same text succeeds and the `a` property is 2 (the later pair wins). The same compatibility switch applies to every document of a multi-document parse.
- Double-quoted scalars fold a carriage-return/line-feed pair to a space the same way they fold a line-feed: a single-document parse of a double-quoted `folded` then a carriage-return/line-feed then `to a space` yields the string `folded to a space`. A backslash immediately before that line break joins the lines without a space. Single-quoted scalars fold that same carriage-return/line-feed pair to a space (`folded` then a carriage-return/line-feed then `to a space` yields `folded to a space`); they have no backslash-join form.
- An eight-digit Unicode escape inside a double-quoted scalar is decoded: a single-document parse of a double-quoted `\U0001F600` yields the corresponding Unicode character.
- A `%TAG` directive may use digits in the handle. A stream that declares `%TAG !a1! tag:yaml.org,2002:` and then a document `!a1!str 123` parses as the string `123`.

**Boundary / error behavior:**

- A single-document parse of empty text fails. A single-document parse of text that is only whitespace and comments (for example three spaces, a newline, a `# comment` line) also fails. In both cases the multi-document parse of the same text succeeds with an empty list. The caller can tell these two entries apart on empty input.
- A single-document parse of a stream that contains more than one document fails. The two-document stream `--- # first document\n--- # second document\n` fails on the single-document entry and succeeds on the multi-document entry.
- An unknown explicit tag is rejected. A single-document parse of `!unknown_scalar_tag foo` under the default Core schema fails. (Catch-all prefix tags in FP-06 are the way to accept unknown tags.)
- An explicit tag on the wrong node kind is rejected. A single-document parse of `--- !!str [not a scalar]` fails.
- Malformed YAML fails and does not yield a constructed value. The following inputs each fail on both parse entries: a line of only `@` characters; a null byte in the middle of `foobar`; an unclosed single-quoted scalar; an unclosed double-quoted scalar; an alias whose name was never anchored; a `%YAML 2.0` directive; a flow mapping that opens with `{` and closes with `]`; a non-printable character such as the byte 0x01, 0x7F, or 0x9F; a lone Unicode surrogate pair written as UTF-16 code units that are not a valid scalar; a control character inside a quoted scalar.
- When a source-path label is supplied (for example `my.yml`) and parse fails, the failure is distinguishable from a success, and an observer can see that the label is part of the failure report. A parse of `@` with that label fails and the report includes that label. A parse of `a: 1` then a carriage-return/line-feed then `@`, with a source-path label, fails on the second line; the report identifies that later line, not the first.
- A failed parse does not yield a usable document. The caller can tell success from failure before reading any constructed value.

**Verifiable oracle:**

- Success: `answer: 42` parses as an object whose `answer` is the number 42; a leading byte-order mark does not change `foo: bar`; the two-document stream `1` then `2` yields `[1, 2]` on the multi-document entry and fails on the single-document entry; empty text fails on the single-document entry and yields an empty list on the multi-document entry; `copy: *base` after `&base { a: 1 }` shares identity with `base`; `&a [*a]` is a sequence that contains itself; `a: 1\na: 2` fails unless JSON-parse compatibility is on, in which case `a` is 2; a double-quoted or single-quoted `folded` then a carriage-return/line-feed then `to a space` yields `folded to a space`; `\U0001F600` in double quotes decodes to that character; a supplied source-path label appears in the failure report for `@`.
- Failure / absence: every scalar stays a string; empty text is treated as null or as success on the single-document entry; a second `---` is silently ignored; aliases copy by value and break cycles; duplicate keys silently keep the first pair; unknown tags are accepted as strings; malformed input yields a partial object; failures carry no source-path label when one was supplied.

---

### FP-02: Built-in schemas and YAML 1.2 type resolution

**Public entry:** The schema selection on both parse entries (FP-01) and on dump (FP-05). The four built-in schemas are exactly Failsafe, JSON, Core, and YAML 1.1. Single-document and multi-document parse use Core when the caller does not choose a schema. YAML 1.1 extra types beyond these Core/JSON/Failsafe scalars are specified in FP-04.

**Normal behavior:**

- Under **Failsafe**, a single-document parse of `v: 1` yields an object whose `v` is the string `1`. A parse of `flag: true` yields the string `true`. Sequences and mappings still construct as arrays and plain objects.
- Under **JSON**, the only implicit null is the lowercase word `null`. A parse of `english: null` yields a null value. A parse of `canonical: ~` yields the string `~`. A parse of an empty mapping value (`empty:` with nothing after the colon) yields an empty string, not null. `Null` and `NULL` stay strings. The only implicit booleans are `true` and `false`; `True`, `TRUE`, `False`, `FALSE`, and all YAML 1.1 words (`yes`, `no`, `on`, `off`, and their case variants) stay strings. Implicit integers are JSON decimal integers without a leading plus and without a leading zero; `+685230`, `0123`, `0b1010`, `0o123`, and `0x1A` stay strings. Implicit floats include a signed exponent (`-2E+05`, `12e03`) but not a leading plus on the number, not a leading dot, not `.inf` / `.nan`, and not a leading zero (`01.0` stays a string). An explicit empty `!!null` node is still null.
- Under **Core** (the parse default), implicit nulls are the empty scalar, `~`, `null`, `Null`, and `NULL`. Implicit booleans are `true` / `True` / `TRUE` and `false` / `False` / `FALSE`; the YAML 1.1 words `y`, `yes`, `on`, `n`, `no`, `off` and their case variants stay strings. Implicit integers accept an optional leading plus, treat a leading-zero token such as `0123` as decimal 123, accept `0o123` as octal 83, and accept `0x1A` as hexadecimal 26; they do not treat `0b1010`, `+0o123`, `-0x1A`, `1_000`, or `1:23` as integers (those stay strings). An explicit `!!int` may still resolve forms the implicit rule rejects: `!!int +0o123` is 83 and `!!int -0x1A` is -26. Implicit floats accept a leading plus, a leading dot (`.5` is 0.5), and the infinity / not-a-number spellings `.inf`, `-.Inf`, `+.INF`, `.NAN` (any of the case patterns `.inf` / `.Inf` / `.INF` and `.nan` / `.NaN` / `.NAN`, with an optional sign on infinity). A trailing-dot decimal such as `12.` is a float. Underscored floats such as `1_000.0` stay strings. A single `.` stays a string. An overflow such as `1e999` stays a string on implicit resolve and is rejected as an explicit `!!float`.
- Under **YAML 1.1**, Core’s `true` / `false` spellings still resolve as booleans, and the additional words `y`, `Y`, `yes`, `Yes`, `YES`, `on`, `On`, `ON` are true and `n`, `N`, `no`, `No`, `NO`, `off`, `Off`, `OFF` are false. Implicit integers treat a leading-zero token such as `0123` as octal 83, accept `0b1010` as 10, accept `0x1A` as 26, accept underscores (`1_000` is 1000), and accept sexagesimal (`1:23` is 83). The YAML 1.2 `0o123` prefix stays a string; `09` stays a string; `1:99` stays a string because minutes and seconds are base 60. An explicit `!!int 0o123` under YAML 1.1 fails (that prefix is not YAML 1.1 integer text). Implicit floats accept underscores and sexagesimal (`190:20:30.15`) and require a sign on an exponent (`685.23015e03` stays a string; `685.230_15e+03` is a float).
- Across JSON, Core, and YAML 1.1, the following implicit or explicit forms construct the same values: decimal `685230` and `-685230`; `0`; an explicit `!!int +685230`; an explicit `!!int 0b1010` (10) and `!!int 0x1A` (26); canonical / exponential / fixed floats that equal 685230.15; `-1.0`; `0.`; `-0.0`; an explicit `!!float .inf`, `!!float -.Inf`, `!!float .NaN`, `!!float +12.3`, and `!!float .5`. An integer whose decimal representation does not fit in a JavaScript number stays a string rather than becoming an inexact float.
- An explicit empty `!!str` is the empty string. An explicit empty `!!seq` is an empty array. An explicit empty `!!map` is an empty mapping (plain object under the default map). An explicit `!!seq` on a non-empty scalar (`!!seq foo`) fails.
- An explicit tag that cannot resolve its text fails and does not yield a value: `!!bool garbage`, `!!int 1.5`, and `!!float abc` each fail on JSON, Core, and YAML 1.1. An explicit empty `!!bool`, `!!int`, or `!!float` node also fails.

**Boundary / error behavior:**

- Switching schema is the only way these implicit rules change. A parse of `v: 1` under Failsafe is the string `1`; the same text under Core is the number 1. A parse of `yes` under Core is the string `yes`; under YAML 1.1 it is boolean true.
- Sexagesimal, underscore, leading-zero-octal, and YAML 1.1 boolean words are not Core behavior. An implementation that applies those rules under Core fails this feature point even if it is correct under the YAML 1.1 schema.

**Verifiable oracle:**

- Success: `v: 1` is a string under Failsafe and a number under Core; JSON keeps `True`, `~`, `+685230`, `.5`, and `.inf` as strings and accepts `null` / `true` / `false` / `-2E+05`; Core accepts `True`, `~`, `+685230`, `0o123` as 83, `0x1A` as 26, `.5`, and `.inf`, and keeps `yes`, `0b1010`, and `1_000` as strings; YAML 1.1 accepts `yes` / `on` / `0123` as octal / `0b1010` / `1_000` / `1:23` and keeps `0o123` as a string; explicit `!!int 0o123` fails under YAML 1.1; explicit `!!int 0b1010` is 10 on all three typed schemas; explicit `!!bool garbage` fails on all three; empty `!!str` is `""`; empty `!!seq` is `[]`.
- Failure / absence: every schema behaves like Failsafe; Core treats `yes` as boolean or `0123` as octal; JSON accepts `~` as null; YAML 1.1 rejects `yes`; explicit `!!int 1.5` succeeds.

---

### FP-03: Mapping containers and key policies

**Public entry:** The default `!!map` tag on every built-in schema, and the two replacement mapping tags the caller may attach to a schema (FP-02 / FP-06): the real-map tag and the legacy-map tag. This feature point depends on a successful parse (FP-01) and on schema selection (FP-02).

**Normal behavior:**

- Under the default plain-object map, a parse of `Clark: Evans\nBrian: Ingerson\nOren: Ben-Kiki` yields a plain object with those three string properties and those three string values. Non-string scalar keys become strings: a mapping whose key is `~` and whose value is `null key` (as in the Core null example that uses `~` as a key) stores the property name `null`, not a null key. A numeric plain key such as `1: num` stores the property name `1` (the string).
- A mapping key that is the JavaScript prototype-accessor name (the `__proto__` key) becomes an **own** data property of the result. A parse of `{ __proto__: { polluted: true } }` yields an object that has its own `__proto__` property whose value is `{ polluted: true }`, whose prototype is still the ordinary object prototype, and that does not have a `polluted` property inherited through the prototype.
- When the real-map tag replaces the default map, a parse of `Clark: Evans` yields a `Map` whose entries are the string key `Clark` and the string value `Evans`. Numeric keys stay numbers and stay distinct from their string form: a parse of `1: num\n"1": str` yields a `Map` of size 2, with number 1 mapping to `num` and string `1` mapping to `str`. Object and array keys are kept as constructed values and survive a dump-then-parse round trip under that same schema: a `Map` that maps `[1, 2]` to `arr` and maps a one-entry `Map` of `x` → 1 to `obj` comes back with those same key values. Dumping a plain object `{ a: 1, b: 2 }` under the real-map schema and parsing the result yields a `Map` with those two string keys, not a plain object.
- When the legacy-map tag replaces the default map, a sequence used as a key is stringified: a parse of an explicit key that is the sequence `foo`, `bar` with value `baz` yields a plain object whose property name is `foo,bar`. A mapping used as a key is stringified to the ordinary JavaScript object rendering. The prototype-accessor key is still stored as an own data property, as with the default map.

**Boundary / error behavior:**

- The default plain-object map rejects a sequence used as a key. A parse of an explicit key that is the sequence `foo`, `bar` with value `baz` fails. The default map also rejects a mapping used as a key (`{ a: 1 }` as an explicit key).
- The legacy map rejects a nested array inside a key. A parse of an explicit key that is a sequence containing another sequence (`nested`) fails. The same nested-array key delivered through an alias also fails.
- These three mapping tags share the `!!map` name: attaching the real-map tag or the legacy-map tag replaces the default map for that schema. They are not three simultaneous containers in one schema.

**Verifiable oracle:**

- Success: default parse of `Clark: Evans` is a plain object; `{ __proto__: { polluted: true } }` does not pollute the prototype; default parse of a sequence key fails; real-map parse of `1: num` and `"1": str` keeps two distinct keys; real-map dump-then-parse of a `Map` with an array key restores that array key; legacy-map parse of a `foo`/`bar` sequence key yields the property `foo,bar`; legacy-map parse of a nested-array key fails.
- Failure / absence: default map silently stringifies a sequence key; the `__proto__` key changes the object’s prototype so that a `polluted` property appears as inherited; real-map still returns a plain object and collapses `1` with `"1"`; legacy-map rejects the same keys the default map rejects, or accepts nested-array keys.

---

### FP-04: YAML 1.1 types and merge keys

**Public entry:** The YAML 1.1 schema on both parse entries, and the merge tag the caller may attach to the Core schema when merge keys are needed without the rest of YAML 1.1. This feature point depends on FP-01, FP-02, and (for complex keys inside `!!pairs`) FP-03. Dump of binary, timestamp, and set values is specified here for those types; general dump presentation is FP-05.

**Normal behavior:**

- **`!!binary`.** Under the YAML 1.1 schema, an explicit `!!binary` scalar whose text is Base64 (whitespace inside the Base64 is ignored) constructs a `Uint8Array` of the decoded bytes. A value that is already a `Uint8Array` dumps as `!!binary` and parses back to the same bytes. An empty `!!binary` node is an empty `Uint8Array`.
- **`!!timestamp`.** Under the YAML 1.1 schema, the following implicit forms construct date values in UTC: `2001-12-15T02:59:43.1Z`; `2001-12-14t21:59:43.10-05:00`; `2001-12-14 21:59:43.10 -5`; `2001-12-15 2:59:43.10` (no zone, treated as UTC); `2002-12-14` (midnight UTC). A one-digit month such as `2002-1-1` stays a string. A date value dumps as a timestamp and parses back to the same instant. An empty `!!timestamp` node fails. Impossible calendar values stay strings when implicit and fail when written as explicit `!!timestamp`: `2023-02-30`, `2023-01-01 24:00:00`, `2023-01-01 00:60:00`, and a zone offset of `+24` or `+1:60`.
- **`!!set`.** Under the YAML 1.1 schema, `!!set { Boston Red Sox, Detroit Tigers, New York Yankees }` constructs a JavaScript `Set` of those three strings. A `Set` dumps with an explicit `!!set` tag and parses back as a `Set` with the same members. An empty `!!set` node is an empty `Set`. Each set item must have a null value; a `? key` / `: not null` pair under `!!set` fails.
- **`!!omap`.** Under the YAML 1.1 schema, an explicit `!!omap` sequence of single-key mappings constructs an array of those mappings, in order: `!!omap [ one: 1, two: 2, three: 3 ]` is `[{ one: 1 }, { two: 2 }, { three: 3 }]`. Keys across items must be unique. An empty `!!omap` is an empty array. When the real-map tag is also attached, each item is a one-entry `Map` instead of a plain object. `!!omap` and `!!pairs` are load-only compatibility types: they are not identified on dump, so a dumped result is a plain sequence (or sequence of mappings), not an `!!omap` / `!!pairs` node.
- **`!!pairs`.** Under the YAML 1.1 schema, `!!pairs [ meeting: with team, meeting: with boss ]` constructs an array of two-element arrays: `[['meeting', 'with team'], ['meeting', 'with boss']]`. Duplicate keys are allowed. An empty `!!pairs` is an empty array. A complex key is rejected under the default map and preserved under the real-map tag: `!!pairs [ ? [ foo, bar ] : baz ]` fails on the default map and yields `[[['foo', 'bar'], 'baz']]` on the real-map schema.
- **Merge keys.** The Core schema does not apply `<<` as a merge. A parse of a `defaults` mapping anchored with `adapter: postgres` and `host: localhost`, plus a `development` mapping that contains `<<: *defaults` and `database: app_development`, under Core without the merge tag, yields a `development` object that has a property literally named `<<` (whose value is that defaults mapping) and a `database` property, and does **not** have `adapter` or `host` of its own. Under the YAML 1.1 schema, or under Core with the merge tag attached, that same document yields a `development` mapping with `adapter`, `host`, and `database`, and no `<<` property. Several merge keys in one mapping all apply: `<<: {x: 1, y: 2}` then `foo: bar` then `<<: {z: 3, t: 4}` yields `x`, `y`, `foo`, `z`, and `t`. An explicit pair overrides a merged pair of the same key: `<< : [ { r: 10 }, { x: 0 } ]` with an explicit `x: 1` yields `x: 1` and `r: 10`. A merge value may be one mapping or a sequence of mappings. When the value is a sequence, a key already brought in by an earlier mapping in that sequence is not overwritten by a later mapping: `<<: [ { r: 10 }, { r: 1 } ]` yields `r: 10`, not `r: 1`. A merge into a mapping whose tag rejects the incoming pair fails (a `!!set` whose merge source is `{ a: 1 }` fails, because a set item cannot have a non-null value). A merge source that is a scalar, or a merge sequence that contains a scalar, fails.

**Boundary / error behavior:**

- `!!omap` on a mapping (not a sequence) fails. An `!!omap` item that is a scalar, an item with more than one key, or a repeated key across items fails. The same three item rules apply to `!!pairs`, except that repeated keys are allowed for `!!pairs`.
- `!!binary` rejects text that is not valid Base64, including a run of `@` characters and an unpadded wrong-length payload such as `AAA`.
- Merge-key processing is counted against the merge-key budget in FP-07.

**Verifiable oracle:**

- Success: YAML 1.1 parse of `!!binary` Base64 yields a `Uint8Array` that dump-then-parse restores; `2001-12-15T02:59:43.1Z` is that UTC instant and `2002-1-1` is a string; `!!set { a, b }` is a `Set` and dumps with `!!set`; `!!omap [ one: 1, two: 2 ]` is two single-key objects and rejects a duplicate `a`; `!!pairs` keeps two `meeting` pairs; Core without the merge tag does not copy `<<: *defaults` into the parent; Core with the merge tag (or YAML 1.1) does copy `adapter` and `host` and lets an explicit pair win; `<<: [ { r: 10 }, { r: 1 } ]` yields `r: 10`; a scalar merge source fails.
- Failure / absence: binary stays a Base64 string; timestamps stay strings; `!!set` is a plain object of nulls; `!!omap` / `!!pairs` accept multi-key items; Core always merges `<<`; YAML 1.1 never merges `<<`.

---

### FP-05: Serialize JavaScript values to YAML

**Public entry:** The ymlcodec library’s dump entry. The caller supplies one JavaScript value and may supply a schema (FP-02), the presentation choices listed below, a switch that skips unrepresentable values instead of failing, and a switch that disables anchor/alias reuse. This feature point depends on FP-02 for quoting rules and on FP-03 / FP-04 when the value uses a `Map`, a `Set`, a date, or an 8-bit byte array.

**Normal behavior:**

- Dump of `{ answer: 42 }` under the default dump schema produces YAML text that a Core or YAML 1.1 parse reads back as an object whose `answer` is the number 42. Dump of a string that needs no quoting (for example `hello`) is that string followed by a newline, in plain style.
- The default dump schema is the YAML 1.1 schema extended so that YAML 1.2 `0o` integers and exponent-only floats count as typed scalars for quoting. A dump of the string `yes` therefore quotes it (YAML 1.1 would otherwise read it as boolean true). The same quoting applies to the other YAML 1.1 boolean words listed under YAML 1.1 in FP-02 (`Yes`, `YES`, `on`, `n`, `no`, `off`, and their case variants). A dump of the string `yes` under the JSON schema is unquoted (plain), because JSON has no `yes` boolean. A dump of the string `true`, `42`, `99.9`, or `null` is quoted so that a parse does not change the type.
- Strings that would be read as YAML structure are quoted. Dump of `---` is a quoted `---`. Dump of `...` is a quoted `...`. Dump of `--- x` and `... x` (the marker, a space, and more text) is quoted. Dump of `- value`, `? value`, `=`, `foo: bar`, `foo:`, and `foo #bar` is quoted. Dump of `---x`, `...x`, `http://example.com`, and `foo#bar` stays plain. A string that begins or ends with a space is quoted (` leading space`, `trailing space `).
- When quotes are required, the default quote style is single quotes. The caller may choose double quotes instead: dump of `null` with double-quote style is a double-quoted `null`. A “quote every non-key string” switch quotes values such as `world` in `{ hello: world }` while leaving the key `hello` unquoted unless other rules require quotes.
- Integers that JavaScript would print in exponential notation at or above `1e21` dump as floats (`1.e+21`), not as an integer tag whose text is exponential. `1e20` still dumps as a decimal integer. Those values parse back to the same number under JSON, Core, and YAML 1.1.
- Special floats dump in a form the selected schema will read back: not-a-number, positive infinity, negative infinity, and a small exponent such as `1e-7` survive dump-then-parse on JSON, Core, and YAML 1.1.
- By default, a second occurrence of the same object (including a cycle) becomes an alias to an anchor on the first occurrence. Dump of an array that contains the same `{ k: 1 }` object twice produces one anchored mapping and one alias. A “do not reuse references” switch dumps that array as two separate mappings with no anchors.
- Default indentation is two spaces: dump of `{ a: { b: 1 } }` puts `b` on the next line, indented two spaces under `a`. An indent width of four spaces uses four spaces. Default line width is 80 columns; a long scalar such as `one two three four five six seven eight nine ten` under a line width of 20 is folded onto several lines, and under the default width it stays on one line.
- Sequences under a mapping key are indented under that key by default (`a:\n  - 1`). A “no extra sequence indent” switch aligns the dash with the key (`a:\n- 1`). A nested sequence starts on the parent dash line by default (`- - 1`); a switch forces the nested sequence onto the next line.
- A flow-style depth of 0 dumps the whole value in flow style (`{a: [1, 2]}` for `{ a: [1, 2] }`). A flow-style depth of 1 dumps the root as a block mapping and the nested sequence as `[1, 2]`. The default depth never switches to flow. Optional flow presentation switches pad inside brackets (`[ 1, 2 ]`), drop the space after commas (`[1,2]`), drop the space after colons (`{a:1}`), and quote flow keys (`{"a": 1}`).
- When a dumped node has both an anchor and an explicit tag, the default order is the anchor then the tag. A switch reverses that order to the tag then the anchor. A dump of two references to one custom-tagged mapping therefore emits the tag after the anchor by default, and emits the tag before the anchor when that switch is on.
- When a comparator-less key sort is requested, dump of `{ b: 1, a: 2 }` emits `a` before `b`. Without that request, keys stay in insertion order (`b` then `a`). Complex keys are not reordered relative to each other.
- Unrepresentable values (a function, a regular expression) cause dump to fail by default. When the skip-unrepresentable switch is on, a function in a mapping is omitted (`{ a: <function>, b: 2 }` dumps as `b: 2`) and a function in a sequence is omitted (`[<function>, 'a']` dumps as `- a`). An `undefined` sequence item dumps as null even without that switch (`[undefined]` dumps as `- null`). An `undefined` mapping value omits that pair. An `undefined` root dumps as empty text.

**Boundary / error behavior:**

- Dump of a function or regular expression without the skip-unrepresentable switch fails and produces no YAML text. Dump of a `Map` that contains a function key, under the real-map schema, fails without that switch and omits that pair with the switch on.
- A string that contains a colon followed by a flow indicator (`:{`, `:[`, `:,`, `:}`, `:]`, `x:{`) is quoted when dumped in flow style, so that dump-then-parse restores the original string.

**Verifiable oracle:**

- Success: dump of `{ answer: 42 }` parses back with numeric 42; dump of `yes` is quoted under the default dump schema and is plain under JSON; dump of `---` and `--- x` is quoted and dump of `---x` is not; dump of a leading-space string is quoted; dump of two references to one object uses an anchor and an alias, and the no-reuse switch inlines both; when a tagged shared mapping is dumped, the default order is anchor then tag and the reverse-order switch emits tag then anchor; indent 4 on `{ a: { b: 1 } }` uses four spaces; flow depth 0 on `{ a: [1, 2] }` is a single flow mapping; sort emits `a` before `b` for `{ b: 1, a: 2 }`; a function makes dump fail without skip and is omitted with skip; `[undefined]` is `- null`; `1e21` dumps as a float that parses back as `1e21`.
- Failure / absence: dump writes JSON; `yes` is dumped unquoted under the default schema and parses back as boolean true; shared objects are always inlined or always aliased regardless of the reuse switch; functions are silently omitted without the skip switch; `1e21` dumps as a tagged integer whose text is exponential and does not parse as that number.

---

### FP-06: Custom tags

**Public entry:** The library’s tag-description entries for a scalar tag, a sequence tag, and a mapping tag, and the schema operation that attaches one or more tags to an existing schema (Failsafe, JSON, Core, YAML 1.1, or an already extended schema). This feature point depends on FP-01, FP-02, and FP-05. Built-in tags from FP-02 and FP-04 stay available; a newly attached tag with the same name, node kind, and prefix-match flag replaces the earlier one.

**Normal behavior:**

- A **scalar** custom tag turns tagged text into a caller-defined value and, on dump, recognizes that value and writes the tag plus the represented text. A Core schema extended with a `!tag2` scalar that reads a decimal integer into a caller-defined object parses `!tag2` followed by `10` as that object, and dump of that object under the same schema writes the `!tag2` tag.
- A **sequence** custom tag creates a container and receives each item in order. A Core schema extended with a `!point` sequence that stores three numbers as `x` / `y` / `z` parses `!point [10, 43, 23]` as a point with those coordinates. Dump of that point writes a `!point` sequence of three numbers. A sequence tag that collects items and then yields a different result than the collection itself: a parse of `!point [10, 20]` for a tag that converts two numbers into a frozen point yields that frozen point; an alias to that node refers to the same frozen point (same identity as the converted value).
- A **mapping** custom tag creates a container and receives each key/value pair. A Core schema extended with a `!space` mapping that understands `height`, `width`, and `points` parses a `!space` node with those keys as a space object, and dump writes those keys back under `!space`.
- The same tag name may be registered for more than one node kind. A schema that defines both a scalar `!Include` and a mapping `!Include` parses `!Include foobar` as the scalar result and `!Include\n  location: foobar` as the mapping result.
- An exact tag name wins over a prefix match. In a schema that has an exact `!foo` scalar and prefix-matching `!foo` and `!` scalars, `!foo 1` uses the exact tag, `!foo2 2` uses the `!foo` prefix, and `!bar 3` uses the `!` prefix.
- Prefix-matching tags are the supported way to accept unknown tags. A Core schema extended with prefix-matching `!` tags for scalar, sequence, and mapping kinds parses `!unknown_scalar_tag foo bar`, `!unknown_sequence_tag [1, 2, 3]`, and `!unknown_mapping_tag { foo: 1, bar: 2 }` as values that remember the tag name and the constructed content, and dump writes those same tag names back.
- A schema must include the default string tag (`!!str`). Attaching tags to Core, JSON, Failsafe, or YAML 1.1 preserves that tag.

**Boundary / error behavior:**

- A recursive alias into a tag that yields a different result than the collection itself fails. A parse of `&point !point [*point]` for a `!point` tag that converts the collected items into a new value fails. A recursive alias into a default sequence (`&a [*a]`) still succeeds (FP-01).
- A tag that refuses the collected items fails the parse and does not yield a document. A `!point` tag that requires exactly two coordinates fails on `!point [10]`.
- An implicit scalar tag that also matches by tag prefix cannot be used: the schema operation that would attach that combination fails, and the caller does not obtain a usable schema.
- A schema that does not define the default string tag cannot be used: the schema operation that would create it fails.

**Verifiable oracle:**

- Success: Core plus `!point` / `!space` parses `!point [10, 43, 23]` as that point and a `!space` mapping with `height` / `width` / `points` as that space, and dump-then-parse restores the tagged form; `!Include` as scalar and as mapping are distinct; exact `!foo` wins over a `!foo` prefix; prefix `!` tags round-trip unknown local tags; `&a [*a]` still works for the default sequence; `&point !point [*point]` fails when `!point` converts the collection into a different result; a schema with no string tag cannot be obtained; an implicit prefix-matching scalar cannot be attached.
- Failure / absence: custom tags are ignored and unknown tags always fail or always become strings; dump of a custom object writes a plain mapping with no tag; exact and prefix tags are indistinguishable; a converting tag accepts a recursive self-alias.

---

### FP-07: Resource limits for untrusted input

**Public entry:** The three numeric limits on both parse entries (FP-01): collection nesting depth, alias count per document, and total merge-key work across the whole parse call. This feature point depends on FP-01 and, for the merge-key budget, on FP-04. It does not change type resolution.

**Normal behavior:**

- **Nesting depth.** The default collection nesting limit is finite and does not count aliases. A flow sequence of ten nested empty sequences parses successfully when the limit is 20 and fails when the limit is 5. A collection nest of 100000 opening brackets fails under the default limit, and the failure is a parse failure (not an uncaught host stack overflow).
- **Alias count.** The default alias budget is unlimited. A document with one anchored mapping and two aliases to it parses successfully under the default and under an alias budget of 2, and fails under an alias budget of 1. An alias budget of 0 rejects every alias, including that document. The caller may also request an unlimited budget explicitly. The alias budget is applied **per document**: a two-document stream in which each document has one alias succeeds when the budget is 1, and fails when the budget is 0.
- **Merge-key work.** The default merge-key budget is 10000 keys processed by `<<` across one single-document or multi-document parse call. A document that merges three one-key mappings into a fourth mapping succeeds when the budget is 5 and fails when the budget is 2. The caller may disable the budget; with the budget disabled, a merge chain that maps 150 keys into one mapping succeeds and that mapping has 150 keys. The merge-key budget is shared across every document of a multi-document parse: two documents that each merge two keys succeed when the budget is 4 and fail when the budget is 3. A merge chain of 100000 steps fails under the default budget, as a parse failure.

**Boundary / error behavior:**

- Crossing a limit fails the parse and yields no document (and no prefix of the multi-document list). The failure is distinguishable from a successful parse of the same text with a higher budget.
- These limits do not, by themselves, cap the cost of walking a constructed graph after a successful parse. A document that stays under the alias budget may still be expensive to convert to JSON if aliases repeat a large subgraph; that follow-on walk is outside this feature point (see the untrusted-input note in Non-functional constraints).

**Verifiable oracle:**

- Success: ten nested flow sequences parse at limit 20 and fail at limit 5; 100000 nested brackets fail under the default depth limit; two aliases succeed at alias budget 2 and fail at 1; alias budget 0 rejects a single alias; two documents that each contain one alias succeed at alias budget 1; three merged keys succeed at merge budget 5 and fail at 2; two documents that each merge two keys fail at merge budget 3 and succeed at 4; disabling the merge budget allows a 150-key merge chain.
- Failure / absence: hostile nesting throws a host stack overflow instead of a parse failure, or succeeds past the stated default; alias and merge budgets are ignored; the merge budget is applied per document instead of per call; the alias budget is applied per call instead of per document.
