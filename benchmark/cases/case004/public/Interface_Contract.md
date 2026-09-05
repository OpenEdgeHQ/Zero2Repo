# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**ymlcodec** is a YAML parser and writer for JavaScript. It reads YAML text into ordinary JavaScript values and writes JavaScript values back as YAML text. The default load dialect is YAML 1.2 Core. The YAML 1.1 type set is available when the caller selects that dialect. Completeness against the YAML 1.2 specification is background; graded behavior is the parse, type-resolution, and dump outcomes of the published library entries.

A common first use is to take a one-key mapping such as `answer: 42` and obtain a plain object whose `answer` property is the number 42, then write that object back as YAML. Leaving `42` as the string `42`, or writing a document that re-parses as a different value, is a failure of the product.

The finished product is a **library**, not a network service and not an importable Python package. Integrators install the ymlcodec package and call the published parse and dump entries. A command-line convenience also named ymlcodec can turn a YAML file into JSON text, or a JSON file into YAML text; it is the same parse-and-dump behavior, not a separate product.

There are no compiled native extensions. A current Node.js LTS interpreter and npm are sufficient to install from this repository, run the documented bundle step, and exercise a parse against the locally built artifact. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

JavaScript-specific tags that construct functions, regular expressions, or other host-only values are not part of this library. The low-level event stream, document tree, and tree visitor exist so advanced callers can build their own pipeline; they are not a separate graded product. Speed is a design goal, not a graded oracle.

### Shape of the public surface

The public surface is a **JavaScript library** published as an ESM module, plus an optional convenience CLI that applies the same parse-and-dump entries to a file. There is no wire protocol and no product configuration-file format.

**Distribution and import.** The installable package name and the import specifier are both ymlcodec. Callers write `import { `load` } from 'ymlcodec'` (and the same form for the other named exports below). The library is not a default-export singleton.

The package manifest is `package.json` at the built repository root. The ESM library artifact is the file named by `exports``["."].``import`, or, if that field is absent, by `module`. That file must exist and must be importable as an ES module. A CommonJS build and a browser export may ship alongside; they are not required for this surface. The convenience CLI, when published, is the file named by `bin` (the ymlcodec key, or the sole / first `bin` path).

Importing the module performs no I/O against caller files, starts no processes, and opens no sockets. Each call is self-contained: schema objects and custom tags constructed for one call do not leak into another unless the caller passes them again.

**Library entries.** The three published call entries are:

- `load` — single-document parse. The first argument is YAML text. An optional options object may follow. Returns exactly one constructed value. Throws when the stream is empty, contains only whitespace and comments, or contains more than one document.
- `loadAll` — multi-document parse. The first argument is YAML text. An optional options object may follow. Returns every constructed document, in order, as an array. An empty stream, or a stream of only whitespace and comments, returns an empty array.
- `dump` — serialize one JavaScript value as YAML text. The first argument is the value. An optional options object may follow.

Parameter defaults, return shapes, and thrown conditions for each entry belong with those symbols.

**Schemas.** The four built-in schemas are named exports: `FAILSAFE_SCHEMA`, `JSON_SCHEMA`, `CORE_SCHEMA`, and `YAML11_SCHEMA`. They are values of `Schema`. Both parse entries use `CORE_SCHEMA` when the caller does not pass `schema`. The default dump schema is `YAML11_SCHEMA` extended so that YAML 1.2 `0o` integers and exponent-only floats count as typed scalars when deciding whether a string needs quotes. A schema is extended by `withTags` on that schema object.

**Tags.** Custom scalar, sequence, and mapping tags are created with `defineScalarTag`, `defineSequenceTag`, and `defineMappingTag`, then attached with `withTags`. Built-in tags that callers attach by name include `mergeTag` (YAML 1.1 merge keys on a schema that does not already have them), `realMapTag` (`!!map` stored as a JavaScript `Map`), `legacyMapTag` (`!!map` that stringifies complex keys), and `mapTag` (the default plain-object `!!map`). Attaching `realMapTag` or `legacyMapTag` replaces the default map for that schema; the three mapping tags share the `!!map` name and are not three simultaneous containers. A schema must include the default string tag `!!str`.

**CLI.** The convenience binary is ymlcodec. It reads one file (or standard input) and writes JSON or YAML on standard output using `loadAll` and `dump`. It is the same library behavior. Exact flags and process exit codes belong with that entry if it is specified; they are not a separate product.

Exact signatures, option defaults, and raised conditions for individual symbols belong with those symbols, not here.

### Naming conventions

**Product and package.** The product identity is ymlcodec. The package name, the import specifier, the `bin` key, and the convenience CLI basename are spelled ymlcodec.

**Parse and dump entries.** Single-document parse is `load`. Multi-document parse is `loadAll` (camelCase, capital A). Serialize is `dump`.

**Schema exports.** Failsafe is `FAILSAFE_SCHEMA`. JSON is `JSON_SCHEMA`. Core is `CORE_SCHEMA`. YAML 1.1 is `YAML11_SCHEMA`. The constructor / type name is `Schema`. The attach operation is `withTags`.

**Parse option keys.** The options object accepted by `load` and `loadAll` uses these keys: `filename` (source-path label for failure reports), `schema`, `json` (JSON-parse compatibility for duplicate keys), `maxDepth` (collection nesting), `maxAliases` (alias count per document), `maxTotalMergeKeys` (merge-key work across the whole call).

**Dump option keys.** The options object accepted by `dump` uses `schema` plus these presentation keys: `indent`, `flowLevel`, `seqNoIndent`, `seqInlineFirst`, `skipInvalid`, `sortKeys`, `lineWidth`, `noRefs`, `quoteStyle`, `forceQuotes`, `flowBracketPadding`, `flowSkipCommaSpace`, `flowSkipColonSpace`, `quoteFlowKeys`, `tagBeforeAnchor`, `transform`. When quotes are required, `quoteStyle` is `single` or `double`.

**Tag factories and attachable tags.** Factories: `defineScalarTag`, `defineSequenceTag`, `defineMappingTag`. Attachable replacements and extras: `mapTag`, `realMapTag`, `legacyMapTag`, `mergeTag`.

**YAML type names.** The Failsafe / JSON / Core tags are `!!null`, `!!bool`, `!!int`, `!!float`, `!!str`, `!!seq`, `!!map`. The YAML 1.1 extras are `!!binary`, `!!timestamp`, `!!set`, `!!omap`, `!!pairs`. The merge key is `<<`. A local tag is written with a single `!` (for example `!point`). The long form of the standard prefix is `tag:yaml.org,2002:`. A `%TAG` directive may put digits in the handle.

**Document markers.** Documents may be separated by the document-start marker `---` and the document-end marker `...`.

**Constructed JavaScript types.** Default `!!map` is a plain object. `!!seq` is an array. `!!null` is JavaScript `null`. `!!bool` is boolean. `!!int` / `!!float` are numbers when they fit in a JavaScript number; an integer that does not fit stays a string. `realMapTag` constructs a `Map`. `!!set` constructs a `Set`. `!!binary` constructs a `Uint8Array`. `!!timestamp` constructs a date value. The prototype-accessor key `__proto__` is stored as an own data property.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**Built artifact.** The graded surface is the locally built ESM module named from `package.json` as above. When that artifact is absent from the module search path, a parse of `answer: 42` does not produce a successful ymlcodec document.

**Success versus failure.** A successful parse returns the constructed value (`load`) or the array of constructed documents (`loadAll`). A failed parse throws and does not yield a usable document. The caller can tell success from failure before reading any constructed value. The exact exception class name, the exact wording of the message, and whether reported line numbers are zero-based or one-based are not part of this surface.

**Source-path label.** When `filename` is supplied (for example `my.yml`) and parse fails, an observer can see that label in the failure report. A parse of `@` with that label fails and the report includes that label. A parse of `a: 1` then a carriage-return/line-feed then `@`, with a source-path label, fails on the later line; the report identifies that later line, not the first.

**The two parse entries differ on empty and multi-document streams.** `load` of empty text, or of text that is only whitespace and comments, fails. `loadAll` of the same text succeeds with an empty array. `load` of a stream that contains more than one document fails. `loadAll` of that stream succeeds with one array element per document, in order. Two document-start markers and nothing else are two empty documents: `loadAll` returns two null values; `load` fails.

**Byte-order mark.** A leading byte-order mark is ignored. A single-document parse of a stream that begins with a byte-order mark and then `foo: bar` yields the same object as a parse of `foo: bar` alone.

**Default load dialect.** Implicit type resolution on both parse entries is YAML 1.2 Core unless the caller passes `schema`. Merge keys and the YAML 1.1-only types are off until the caller selects `YAML11_SCHEMA` or attaches those tags. Switching schema is the only way those implicit rules change.

**Default dump dialect.** `dump` quotes strings that the default dump schema would otherwise read back as a different type (for example the string `yes`, the string `true`, the string `42`, the string `null`, and the document markers `---` / `...`). Presentation defaults are two-space indent and an 80-column line width. Shared object identity becomes an anchor plus an alias unless `noRefs` is on.

**Duplicate keys.** Duplicate keys in one mapping are rejected by default. When `json` is true, the later pair wins. That switch applies to every document of a multi-document parse.

**Anchors and aliases.** An `&name` label and a later `*name` refer to the same constructed value (same identity, not a copy). A recursive alias is allowed for the default sequence and mapping tags.

**Limits.** Default collection nesting (`maxDepth`) is 100 levels and does not count aliases. Default alias budget (`maxAliases`) is unlimited (`-1`; `0` rejects every alias). Default merge-key budget (`maxTotalMergeKeys`) is 10000 keys processed by `<<` across one `load` / `loadAll` call (`-1` disables). Crossing a limit fails the parse and yields no document. The alias budget is per document; the merge-key budget is per call. These limits do not, by themselves, cap the cost of walking a constructed graph after a successful parse.

**Untrusted input.** The YAML design allows a tiny document to expand into a huge object graph. Walking a constructed value after a successful parse (for example by converting it to JSON) is the caller’s responsibility.

**No product-owned process exit codes on the library path.** `load`, `loadAll`, and `dump` report outcomes by returning a value or throwing. They do not exit the host process.

## `Schema`

Named export. Constructor / type name for a schema. Callers write `import { `Schema` } from 'ymlcodec'`. The four built-in schemas `FAILSAFE_SCHEMA`, `JSON_SCHEMA`, `CORE_SCHEMA`, and `YAML11_SCHEMA` are values of `Schema`.

### Create call

The create call is `new `Schema`(tagArray)`: one argument, the complete tag list as an array. That list is the whole schema, not an extension of a built-in. A successful instance has `withTags`.

A schema must include the default string tag `!!str`. A list without `!!str` cannot be used:

- `new `Schema`([])` fails. The caller does not obtain a usable schema.
- `new `Schema`(tags)` whose array is nonempty but still has no `!!str` (for example one custom scalar from `defineScalarTag`) also fails. The caller does not obtain a usable schema.

Failure is a throw. A later parse failure is not evidence that create failed.

Extending a built-in schema is `withTags` on that schema, not a second `Schema` create. Custom tags are built with `defineScalarTag`, `defineSequenceTag`, and `defineMappingTag` and then either attached with `withTags` or, when creating from scratch, included in the `Schema` list together with `!!str`.

## `defineMappingTag`

Named export. Factory for a mapping custom tag. Callers write `import { `defineMappingTag` } from 'ymlcodec'`.

The call is a tag-name string plus one options object: `defineMappingTag``(name, options)`. The name is the handle (`!space`, `!Include`, or another local tag). The options object uses these keys: `matchByTagPrefix`, `create`, `addPair`, `has`, `keys`, `get`, `identify`, `represent`, and `representTagName`. Keys a given tag does not use may be omitted. The return is a tag object attached with `withTags` or passed in the list given to `Schema`.

The same tag name may be registered for more than one node kind. A schema that defines both a scalar `!Include` (via `defineScalarTag`) and a mapping `!Include` parses `!Include foobar` as the scalar result and `!Include` followed by a `location: foobar` mapping as the mapping result. Those two results are distinct.

### Options

- `matchByTagPrefix` — boolean. Same exact-versus-prefix rule as `defineScalarTag`. A prefix-matching `!` mapping accepts `!unknown_mapping_tag { foo: 1, bar: 2 }` and remembers that name plus the constructed pairs.
- `create` — start the container. Invoked with no arguments, or as `(tagName)` so a prefix catch-all can store the original node name. A `!space` tag that understands `height`, `width`, and `points` starts a space object.
- `addPair` — receive each key/value pair. Invoked as `(container, key, value)`. A parse of a `!space` node with those three keys stores the numbers and the `points` sequence on the space object. A nested `!point` item inside `points` is constructed by the sequence tag on the same schema.
- `has` — dump membership. Invoked as `(container, key)`.
- `keys` — dump key list. Invoked as `(container)` and returns the keys to write (`height`, `width`, `points` for a space).
- `get` — dump lookup. Invoked as `(container, key)` and returns the value for that key.
- `identify` — dump predicate. A true result means this tag owns the value. Dump of a space writes `!space`. Dump of a plain object with the same keys does not write `!space`.
- `represent` — dump body. Receives the identified value. May return a `Map` of pairs that dump must write. Dump of a `!space` object writes `height`, `width`, and `points` under `!space`. Dump of a never-parsed space-shaped value that `identify` accepts writes `!space` and those keys. Dump-then-parse restores the tagged form and the same numbers.
- `representTagName` — dump tag name. A prefix catch-all that stored `tagName` writes that same name back (`!unknown_mapping_tag`).

Without an attached matching tag, a parse of a `!space` node or of an unknown local mapping fails and yields no document.

## `defineScalarTag`

Named export. Factory for a scalar custom tag. Callers write `import { `defineScalarTag` } from 'ymlcodec'`.

The call is a tag-name string plus one options object: `defineScalarTag``(name, options)`. The name is the handle (`!tag2`, `!foo`, `!`, or another local tag). The options object uses these keys: `matchByTagPrefix`, `implicit`, `resolve`, `identify`, `represent`, and `representTagName`. Keys a given tag does not use may be omitted. The return is a tag object, not a schema. Callers attach it with `withTags` or pass it in the list given to `Schema`.

### Options

- `matchByTagPrefix` — boolean. `false` is an exact name. `true` matches any node whose tag begins with the given name. An exact name wins over a prefix: a schema that has an exact `!foo` scalar and prefix-matching `!foo` and `!` scalars uses the exact tag for `!foo 1`, the `!foo` prefix for `!foo2 2`, and the `!` prefix for `!bar 3`. Prefix-matching `!` tags are the supported way to accept an otherwise unknown local tag.
- `implicit` — boolean. `true` marks an implicit scalar. A tag that is both `implicit` and `matchByTagPrefix` cannot be used: `withTags` of that combination fails and the caller does not obtain a usable schema. The same name with `matchByTagPrefix` true and `implicit` false attaches and then matches a longer handle that starts with that name.
- `resolve` — construct the tagged scalar. Invoked as `(source)` with the scalar text, and as `(source, second, tagName)` so a prefix catch-all can see the original node name in `tagName`. A `!tag2` tag that reads a decimal integer into a caller-defined object parses `!tag2 10` and a block `!tag2` plus `10` as that object, not as the bare number 10 and not as the text `10`. A prefix `!` tag that remembers `tagName` plus the source text parses `!unknown_scalar_tag foo bar` as a value that still holds that name and that text.
- `identify` — dump predicate. Receives the JavaScript value. A true result means this tag owns the value. Dump of a value that `identify` accepts writes this tag. Dump of a plain number does not write this tag.
- `represent` — dump body. Receives the identified value and returns the scalar text to write. Dump-then-parse of a `!tag2` object that holds 10 still holds 10. Dump of a never-parsed object that `identify` accepts writes the tag and that same body.
- `representTagName` — dump tag name. Receives the identified value and returns the handle to write. A prefix catch-all that stored `tagName` writes that same name back (`!unknown_scalar_tag`, not only `!`).

Without an attached matching tag, a parse of `!tag2 10` or of an unknown local scalar fails and yields no document.

## `defineSequenceTag`

Named export. Factory for a sequence custom tag. Callers write `import { `defineSequenceTag` } from 'ymlcodec'`.

The call is a tag-name string plus one options object: `defineSequenceTag``(name, options)`. The name is the exact handle (`!point` or another local tag). The options object uses these keys: `matchByTagPrefix`, `create`, `addItem`, `finalize`, `identify`, `represent`, and `representTagName`. Keys that a given tag does not use may be omitted. The return is a tag object attached with `withTags` or passed in the list given to `Schema`.

### Options

- `matchByTagPrefix` — boolean. Same exact-versus-prefix rule as `defineScalarTag`. A prefix-matching `!` sequence accepts `!unknown_sequence_tag [1, 2, 3]` and remembers that name plus the constructed items.
- `create` — start the container. Invoked with no arguments, or as `(tagName)` so a prefix catch-all can store the original node name. A `!point` tag that stores three numbers as `x` / `y` / `z` starts a point object; a converting tag starts a collector that is not the final value.
- `addItem` — receive each item in order. Invoked as `(container, item, index)`. A `!point` parse of `!point [10, 43, 23]` puts 10 at `x`, 43 at `y`, and 23 at `z`. A parse of those three numbers in another order keeps that order on dump-then-parse. The two-argument form `(container, item)` is also used when the tag only appends.
- `finalize` — finish the collection. Invoked as `finalize``(container)`. This is how a converting tag yields a different value than the collector, or refuses a wrong-length collection. A `!point` tag that converts two numbers into a frozen point parses `!point [10, 20]` as a value that holds 10 and 20; an alias to that node refers to the same converted value (same identity). That same tag fails a parse of `!point [10]` and yields no document. A recursive alias into that converting tag (`&point !point [*point]`) fails. A recursive alias into the default sequence (`&a [*a]`) on the same attached schema still succeeds: the one item is the sequence itself.
- `identify` — dump predicate. A true result means this tag owns the value. Dump of a point writes `!point`. Dump of a plain three-number array does not write `!point`.
- `represent` — dump body. Receives the identified value and returns the item list to write. Dump-then-parse of `!point [10, 43, 23]` still has those three coordinates. Dump of a never-parsed point-shaped value that `identify` accepts writes `!point` and those numbers.
- `representTagName` — dump tag name. A prefix catch-all that stored `tagName` writes that same name back (`!unknown_sequence_tag`).

Without an attached matching tag, a parse of `!point [10, 43, 23]` or of an unknown local sequence fails and yields no document.

## `withTags`

Attach operation on a schema object. Not a free function. The four built-in named exports `FAILSAFE_SCHEMA`, `JSON_SCHEMA`, `CORE_SCHEMA`, and `YAML11_SCHEMA` each have `withTags`. The value returned by `withTags` is itself a schema that still has `withTags`, so a caller can attach again.

### Call shape

Custom tags from `defineScalarTag`, `defineSequenceTag`, and `defineMappingTag` are attached by calling `withTags` with one array of tag objects: `schema.`withTags`(tags)` and `schema.`withTags`([...])`. An implementation that only accepted rest arguments would not match that call.

Named attachable tags (`mergeTag`, `realMapTag`, `legacyMapTag`) are also passed as individual arguments: `schema.`withTags`(tag)` and `schema.`withTags`(tag, ...)`. Both shapes must work.

The return is passed to `load` and `dump` as the `schema` option: ``load`(text, { `schema` })` and ``dump`(value, { `schema` })`. Sequential attach assigns the return back: `schema = schema.`withTags`([...])`.

### Observable attach rules

- Attaching one or more tags to `CORE_SCHEMA`, `JSON_SCHEMA`, `FAILSAFE_SCHEMA`, or `YAML11_SCHEMA` preserves the default string tag `!!str`. A plain word on that extended schema is still a string. Built-in tags of that schema stay available (Core still constructs `42` as a number and `true` as a boolean; YAML 1.1 still constructs `yes` as a boolean and `!!set`; Failsafe still constructs `42` as a string; JSON still constructs `true` as a boolean and `yes` as a string).
- A newly attached tag with the same name, node kind, and prefix-match flag replaces the earlier one. Replacing an exact `!tag2` scalar does not drop a different prefix tag. Sequential attach is the observed replacement path.
- A tag that is both `implicit` and `matchByTagPrefix` cannot be attached: `withTags` fails and the caller does not obtain a usable schema.
- Each attach is self-contained. Tags constructed for one call do not leak into another unless the caller passes the extended schema again.

