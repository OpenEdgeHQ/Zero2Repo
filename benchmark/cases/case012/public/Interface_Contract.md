### Product overview

**`lint-policy`** is an opinionated Oxlint ruleset that rejects low-evidence and low-signal TypeScript and JavaScript patterns. It reflects its author’s taste rather than attempting to be a universal coding standard.

The product is **meant to be vendored**, not treated as a fixed registry package. There is no official published package. A consuming repository copies the plugin, reads it, and may change it to match local standards. After the initial copy, the vendored files belong to that repository.

`lint-policy` is first a **generic Oxlint JavaScript plugin** whose eighteen rules apply to ordinary TypeScript and JavaScript. Effect-specific architecture policy lives in a **second, opt-in plugin** so projects that do not use Effect do not inherit Effect rules. A consuming Oxlint configuration registers one or both plugins by published name and specifier, enables the desired rules, and runs the host linter against source files. Each enabled rule either reports a diagnostic on a violating construct or stays silent on an allowed construct.

A first-time integrator copies the plugin into the target repository (by hand, or by running the bundled skill copy), registers the generic plugin, enables generic rules at `error` severity, and — only when wanted — also registers the Effect plugin and enables its five rules. From then on, a lint run on owned source is the observable product: violating patterns fail the lint; allowed patterns do not.

The finished product is a **pair of Oxlint JavaScript plugins plus a copy entry** that vendors them. It is not an importable Python package, not a network service, not a wire protocol, and not an end-user command of `lint-policy`’s own. There is no compiled native extension, no bundled binary, no GPU or accelerator, and no runtime network client. Node.js and the host linter are sufficient to run the copy script and to load the plugins against a short TypeScript or JavaScript snippet. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

Exact rule diagnostics, option objects, and per-rule silence cases belong with those symbols, not here.

### Shape of the public surface

The public, independently verifiable surfaces are the **copy entry**, the **generic plugin**, and the **opt-in Effect plugin**. There is no product-owned configuration-file format and no official registry package.

**Copy entry.** The skill copy is the Node script `skills/install-lint-policy/scripts/install.mjs`, invoked from a consuming repository as that script plus an optional relative destination and optional `--force`. The current working directory is the consuming tree. The copy places a pristine plugin tree at the destination. It does not fetch a remote revision, does not merge, does not edit the consuming repository’s lint configuration, and does not install packages.

- With no destination argument, the tree is placed at `tools/oxlint/lint-policy` relative to the current working directory.
- A destination argument uses that relative path instead. A caller-chosen destination does not also create the default destination.
- After a successful copy, the destination is a directory that contains both the generic plugin entry and a nested Effect plugin entry, along with license material and provenance material as files under that destination.
- A successful copy reports that the plugin was copied to the destination and names the generic entry to configure: a path under the destination that is more specific than the destination directory itself. That reported path is the specifier used to register the generic plugin.
- If the destination already exists and `--force` is not passed, the copy refuses to overwrite, exits unsuccessfully, identifies the destination in its report, and leaves the existing tree’s bytes unchanged. `--force` is the only way this copy proceeds against an occupied destination: it overwrites source-overlapping plugin paths so the destination then contains the copied generic plugin entry and the nested Effect plugin entry, both loadable. Destination-only extra files that were not in the copy are neither required to vanish nor required to remain.

**Generic plugin.** The always-applicable plugin. Its published plugin name is `lint-policy`. In the product tree the host loads it from `src/index.ts`. After skill copy, the specifier is the generic entry named in the copy report (under the destination). The integrator registers that name and specifier with the host linter and enables any subset of the eighteen generic rules. Registering the plugin does not enable any rule by itself.

**Effect plugin.** The opt-in plugin. Its published plugin name is `lint-policy-effect`. In the product tree the host loads it from `src/effect/index.ts`. After skill copy, a nested destination file other than the generic specifier is this plugin. It is not inherited merely because the generic plugin is registered. The integrator registers this second name and specifier independently and enables any subset of its five rules.

**Host observation.** Lint of TypeScript or JavaScript source through the host linter is the observation point for the plugins. The host loads each plugin as a JavaScript plugin by published name and specifier. Enabled rules are addressed as ``lint-policy`/⟨rule⟩` or ``lint-policy-effect`/⟨rule⟩`. A diagnostic from a rule enabled at `error` makes that lint invocation fail. Exact host-config field names of the linter itself are not a product surface.

**Manual copy.** Copying the product tree by hand (without the skill script) is a supported path: the canonical generic entry `src/index.ts` is loadable as `lint-policy` and publishes the same eighteen-rule catalog.

**Not in this surface.** An official npm package. A product-owned merge engine that edits lint configuration or pins host versions. Fetching or three-way-merging updates inside the copy entry. A TypeScript type checker. Oxlint’s native accumulating-spread check. A network service.

### Naming conventions

**Product and plugins.** The product identity is `lint-policy`. The generic plugin’s published name is exactly `lint-policy`. The opt-in Effect plugin’s published name is exactly `lint-policy-effect`. Those two names are distinct: `lint-policy` does not match `lint-policy-effect`.

**Copy script and default destination.** The copy entry path is `skills/install-lint-policy/scripts/install.mjs`. The default destination relative to the consuming cwd is `tools/oxlint/lint-policy`. The overwrite switch is `--force`. The bundled skill name is `install-lint-policy`.

**Canonical product-tree entries.** Generic plugin entry: `src/index.ts`. Effect plugin entry: `src/effect/index.ts`.

**Copied-tree entries.** After skill copy, the generic specifier is whatever configure target the copy report names under dest (a path more specific than the dest directory). The Effect plugin is a nested dest file other than that generic specifier. Dest-relative entry filenames are not a fixed spelling.

**Diagnostic ids.** A finding attributable to a plugin rule is the published pair of plugin name and rule name. The slash form is ``lint-policy`/`no-array-filter-map`` (and the same pattern for every other published rule). A host may also render that pair with other punctuation; the published pair is the plugin name plus the rule name.

**Generic rule catalog.** The generic plugin publishes exactly these eighteen independently enableable rules, and no others:

- `no-array-filter-map`
- `no-reduce-accumulator-copy`
- `no-chained-type-assertions`
- `no-conditional-empty-object-spread`
- `no-known-value-widening`
- `no-module-mocking`
- `no-object-parameters`
- `no-reflect-apply`
- `no-reflect-get`
- `no-runtime-typeof`
- `no-shape-in-symbol-names`
- `no-unknown-parameters`
- `no-unknown-returns`
- `no-unknown-type-aliases`
- `no-unsafe-dictionary-type`
- `no-widen-then-assert`
- `require-readable-spacing`
- `require-safety-comment-for-type-assertion`

The generic plugin does **not** publish the five Effect rules.

**Effect rule catalog.** The Effect plugin publishes exactly these five independently enableable rules, and no others:

- `no-manual-effect-error-tag`
- `no-manual-tag-comparison`
- `no-manual-tagged-construction`
- `no-service-constructor-imports`
- `prefer-effect-match`

**Rule-level options (names only).** `no-runtime-typeof` accepts an optional `allowInTypeGuards` flag; when omitted, that flag is off. `require-safety-comment-for-type-assertion` accepts an optional object property `markers` that is a list of strings; when omitted, the sole marker is `SAFETY`. Option shapes and scored defaults belong with those rules.

**Autofix.** `require-readable-spacing` is the only generic rule that offers a fix. No other generic or Effect rule offers a fix.

**Severity.** Enabling a rule at `error` means a diagnostic from that rule fails the lint invocation.

### Global observables an implementer must reproduce

**No product config file.** The product does not parse a configuration-file syntax of its own and does not require a config file to be present. Copy does not write or edit a consuming-tree lint config.

**Copy process exits and reports.**

- A successful copy exits 0, creates the destination as a directory, identifies that destination in the combined standard output and standard error text, and names a generic-entry configure target more specific than the destination directory.
- An occupied destination without `--force` exits non-zero, identifies the destination, and leaves destination bytes unchanged.
- Exact wording of success and refusal text is not pinned beyond identifying the destination (and, on success, naming the generic configure target).

**Copy side effects.**

- Copy creates, deletes, or edits files only under the destination. A consuming-tree `package.json`, an existing lint-configuration file, and the rest of the tree outside dest remain byte-identical. Copy does not create `node_modules`.
- Copy does not require network access.
- The destination contains license material and provenance material as files (basename or file-body role, not a pinned filename).

**Plugin load and catalog.**

- A specifier that is the generic entry, registered as `lint-policy`, publishes the eighteen generic rules above. Each rule fires only when that rule is enabled. Enabling a second catalog name on a snippet that violates only the first still attributes only the first. Enabling all eighteen on a unique violating snippet still attributes only the violating rule.
- The same generic specifier does not emit `lint-policy-effect` diagnostics, including when all eighteen generic rules are enabled and when Effect rule names are listed in host configuration together with a known generic rule.
- A nested destination file other than the generic specifier, registered as `lint-policy-effect`, is the Effect plugin: enabling `no-manual-tag-comparison` on a manual `_tag` comparison reports that Effect rule and fails lint.
- Registering the generic plugin with no `lint-policy` rules enabled reports no `lint-policy` and no `lint-policy-effect` diagnostics. Leaving the plugin unregistered likewise reports none, even on a construct that would violate an enabled rule.
- The canonical product-tree entry `src/index.ts` registers the same generic catalog without running the skill copy.

**Lint outcomes.**

- An enabled generic rule at `error` that fires fails the lint invocation (non-zero host-linter exit) and produces a diagnostic attributable to ``lint-policy`/⟨that rule⟩`.
- A diagnostic's reported position starts within the offending construct the rule reports, not on a neighboring allowed construct. Where a rule names a narrower position (for example the wrapper name in `no-unsafe-dictionary-type` below), that position holds.
- An omitted or unregistered rule produces no diagnostic from that rule on the same source.
- An unpublished `lint-policy` rule name listed together with a known enabled rule is a host-configuration concern, not an invented nineteenth `lint-policy` diagnostic. The caller observes either a host refusal that identifies the unpublished name and the loaded generic plugin `lint-policy`, or classified lint that does not invent a diagnostic for the unpublished name.
- Source the host cannot parse is a host failure, not an `lint-policy` or `lint-policy-effect` diagnostic. Unparsable source is distinguishable from a successful lint of a valid non-violating file.
- The same source, with the same rules enabled and the same options, produces the same `lint-policy` rule ids. There is no model and no random component.

**Same-file analysis.** Alias, annotation, and binding evidence that appears in the file under lint is in scope. Block-scoped aliases, forward references in the same file, and transparent generic aliases are resolved. A rule that scores a type only as written (a keyword written as that keyword) does not resolve a same-file alias in that position (for example a type-predicate parameter of `no-known-value-widening` and the store annotation of `no-widen-then-assert` below). Imported type definitions and names not defined in the same file are not treated as if they were local. The product does not consult a TypeScript type checker or cross-file call signatures.

**Languages.** The plugins lint TypeScript and JavaScript. Generic rules that apply to JavaScript still load through the same `lint-policy` plugin as TypeScript-oriented rules.

**No product-owned process exit codes on the lint path.** Plugin diagnostics are reported through the host linter. Success versus failure of a lint invocation is the host’s exit (zero when no enabled-at-`error` diagnostic fired; non-zero when one did). The plugins do not define a separate lint-policy CLI exit table.

## `no-chained-type-assertions`

### Published rule

`no-chained-type-assertions` is a generic `lint-policy` rule. It reports only when that rule is enabled. Enabling it at `error` makes a diagnostic from this rule fail the lint. It does not rewrite source when the host is asked to fix: the violating file bytes stay unchanged and the diagnostic is still reported.

A diagnostic is this rule alone when the source is only a nested assertion. An unjustified nested assertion is also reported by `require-safety-comment-for-type-assertion`. This rule does not report `no-known-value-widening` or `no-widen-then-assert` on a nested assertion that is not otherwise a widening.

### What reports

The rule reports a chain of more than one TypeScript assertion when at least one assertion in the chain is not a const assertion. Both `as` assertions and angle-bracket assertions count, including a mix, and parentheses around a link do not break the chain.

These shapes report:

- `input as unknown as User`, including with a justification comment on the statement.
- `(input as unknown) as User`.
- `input as User as User`, and `input as Kind as Role` when neither type is `const` or `unknown`.
- `<User>(<unknown>input)`, and `<Outer>(<Inner>value)` when neither type name is `const` or `unknown`.
- `({ id: 1 } as const) as User`.
- `value as const as Target`, with `as const` not wrapped in parentheses and the second type not `const`.
- `input as User as const`.

### What stays silent

A single assertion stays silent for this rule, including a parenthesized single assertion such as `(input as User)`. A chain whose every assertion is a const assertion stays silent, with or without a comment:

- `({ id: 1 } as const) as const`
- `{ id: 1 } as const as const`
- `<const>(<const>value)`

Const-only chains also stay silent for `require-safety-comment-for-type-assertion`.

## `no-known-value-widening`

### Published rule

`no-known-value-widening` is a generic `lint-policy` rule. It reports only when that rule is enabled. Enabling it at `error` makes a diagnostic from this rule fail the lint. It does not rewrite source when the host is asked to fix: the violating file bytes stay unchanged and the diagnostic is still reported.

The keyword `any` is not a target of this rule. A known value stored under `any` stays silent here.

### Known values and vehicles

On the five non-predicate vehicles below, a known value is an object literal with at least one concrete key, a numeric literal, an array literal (including an empty array), or a `const` local whose initializer is one of those literals and which has no type annotation of its own. Each of those six value forms reports when it flows into each target, on each vehicle:

- a variable annotation: `const held: Target = expr`
- an assignment into an already annotated binding: `let held: Target; held = expr`
- a return annotation: `function create(): Target { return expr }`
- a class field initializer: `class Registry { value: Target = expr }`
- an assertion: `const held = expr as Target`

The four targets are the keyword `unknown`, the keyword `object`, an inline object type that has at least one member, and an open dictionary.

An open dictionary is `Record` with key `string`, or a same-file alias of `string` (program scope or block scope), and a value type such as a named type or `number`. The scored spellings include `Record<string, Command>` for a same-file `type Command = () => void` and `Record<string, number>`. An index-signature type literal is not this open-dictionary spelling.

A same-file non-generic alias of `unknown`, `object`, or that open dictionary is the same target, including a block-scoped alias and a forward reference used before its declaration. A same-file generic alias whose body is its own type parameter, applied to an open dictionary (`type Identity<T> = T` used as `Identity<Record<string, Command>>`), is that open-dictionary target.

These report, among the combinations above:

- `const commands: Record<string, Command> = { start: startCommand }`
- the same literal assigned, returned, stored on a class field, or asserted to that open record
- `const held: unknown = [1, 2]`, `const n = 1; const held: unknown = n`, and `const xs = [1, 2]; const held: unknown = xs`
- `const held = 1 as unknown`, `const held = [] as object`, `const held = [] as unknown`, and `const held = 1 as object`
- a concrete-key object literal, or a `const` alias of one, asserted or annotated as `unknown`, `object`, or an inline object type with a member
- a `const` alias of `{ start: startCommand }` annotated as the open record

### Local type predicates

A local function whose return type is a type predicate (`value is string`) reports when it is called with a known argument and its parameter is written as the keyword `unknown`, or as a union that contains that keyword (`string | unknown` or `unknown | string`).

Known arguments that report on that call are a string literal (`isString("known")`) and a local whose only same-file evidence is a precise annotation with no literal initializer (`function check(known: string) { return isString(known) }`).

These predicate calls stay silent:

- the argument is already `unknown`, including `declare const input: unknown` and a call of a function declared to return `unknown`
- an unreassigned `let` or `var` alias of a string literal is the argument
- the parameter type is a same-file alias of `unknown`, including a block-scoped alias, rather than the keyword `unknown`
- one member of the parameter union is a same-file alias of `unknown` and the parameter is not the keyword `unknown`

### What stays silent

- an empty object literal annotated as an open record (`const commands: Record<string, Command> = {}`) or assigned to a binding already annotated as that open record
- `Record` whose key is a union of string-literal types, written inline or through a same-file alias of that union, including a block-scoped alias; the same finite-key record used as an assignment target, a return type, a class field, or a justified assertion. The value type `number` in `Record<string, number>` does not by itself make a `string` key finite
- `satisfies` of an open record (`{ start: startCommand } satisfies Record<string, Command>`)
- a known object assigned to a named interface or a named type alias that declares those finite keys
- an annotation whose type name is imported and not defined in the file, even when the imported declaration is an open record
- an annotation whose type name is not defined in the file
- an unreassigned `let` or `var` alias of an object, numeric, or array literal flowing into `unknown`, `object`, or an open record
- a local whose only same-file evidence is a precise annotation with no literal initializer, used on a variable annotation, assignment, return annotation, class field initializer, or assertion (that local reports only as the type-predicate argument above)

## `no-widen-then-assert`

### Published rule

`no-widen-then-assert` is a generic `lint-policy` rule. It reports only when that rule is enabled. Enabling it at `error` makes a diagnostic from this rule fail the lint. It does not rewrite source when the host is asked to fix: the violating file bytes stay unchanged and the diagnostic is still reported.

The later assertion this rule scores is an `as` assertion. The store and the assertion name the same `const` binding.

### What reports

The rule reports an immutable local `const` that first stores a known value under one of the broad annotations below, then later asserts that same binding to a narrower type. The two steps may sit at top level or in the same function. Inside a function the assertion need not be the next statement, and it may sit in a nested block of that function.

A known value here is a concrete-key object literal, a numeric literal, an array literal, or a `const` local alias of one of those. The broad annotations are the keywords `unknown`, `any`, and `object`, and the written dictionary types `Record<string, unknown>` and `Record<string, any>`.

A narrower type is a named alias or an inline object type with a field, such as `{ readonly id: string }` or `type UserId = { readonly id: string }`. A numeric literal stored under `unknown` and later asserted to `number` reports. An array literal stored under `unknown` and later asserted to `number[]` reports.

These report:

- `const source = { id: "second" }; const widened: unknown = source; const parsed = widened as { readonly id: string }`
- the same store under `any`, then `widened as UserId` where `type UserId = { readonly id: string }`, inside a function or at top level
- the same store under `object`, `Record<string, unknown>`, or `Record<string, any>`, then an assertion of that binding to `{ readonly id: string }` or to a named alias of that object type
- a numeric or array literal stored as `const widened: unknown = literal` and then asserted to `number` or `number[]`

A store under `unknown` or `object`, or under `Record<string, unknown>`, also reports `no-known-value-widening`. A store under `any` reports only this rule. A store under `Record<string, any>` reports this rule; `no-known-value-widening` may report as well.

### What stays silent

- the broad store with no later narrower assertion of that binding
- a later assertion of a different binding
- a later assertion back to a still-broad type: `any`, `object`, or the same `Record<string, unknown>` or `Record<string, any>`
- asserting a binding that was already `unknown` at the boundary and was never a known value in this file
- the later assertion is in a nested function, not in the function that stored the value
- the store annotation is a same-file alias of `unknown` or `object` rather than the keyword (that store still reports `no-known-value-widening`)
- the store annotation is an open record whose values are a named type, including `Record<string, Command>`, even when that binding is later asserted to `{ readonly id: string }` (that store still reports `no-known-value-widening`)

## `require-safety-comment-for-type-assertion`

### Published rule

`require-safety-comment-for-type-assertion` is a generic `lint-policy` rule. It reports only when that rule is enabled. Enabling it at `error` makes a diagnostic from this rule fail the lint. It does not rewrite source when the host is asked to fix: the violating file bytes stay unchanged and the diagnostic is still reported.

The rule does not grade whether the justification is true. It only checks that a configured marker and a non-empty justification are present in the places below.

### Options

The options object has one property, `markers`, a list of strings. When the rule is enabled with no options object, the sole marker is `SAFETY`. Supplying `{ "markers": ["SAFETY"] }` behaves as that default. Supplying a list such as `{ "markers": ["INVARIANT"] }` accepts only those markers: an `INVARIANT` justification stays silent and a `SAFETY` justification reports. Several markers are alternatives; any one of them with a non-empty justification is enough.

A configured marker is matched as a whole string. A marker may contain `+`. The text before the plus, the text after the plus, or a different plus-containing string does not match. A trailing letter glued onto the marker (`SAFETY` plus one letter, or the whole plus-marker plus one letter) does not match. The marker need not be the first token: a word, a space, and then the whole marker still matches. One space between the marker and the colon still matches.

### What reports

A non-const `as` assertion or a non-const angle-bracket assertion that lacks a nearby justification reports. Const assertions are `as const` and `<const>`.

These report when no acceptable justification is attached:

- `void (input as User)` and `void (input as Target)`
- `<Brand>value` and an exported angle-bracket assertion
- `export const got = raw as Brand`
- a comment after the semicolon, or a justification on the line after the assertion with no later statement
- a justification that sits on an earlier sibling statement rather than on the assertion's statement
- a comment that is not a configured marker, a marker with no colon, a marker with nothing after the colon, or a marker with only whitespace after the colon, whether the comment is a `//` line, a `/* */` block immediately above the statement, or an inline `/* */` on the assertion

An unjustified nested assertion also reports `no-chained-type-assertions`. A justification does not silence that chain rule.

### What counts as a justification

The comment text contains a configured marker, a colon, and at least one non-whitespace character after the colon. A single period after the colon counts. A letter glued to the colon (`SAFETY:parsed`) counts. The words after the colon are not fixed; `// SAFETY: parsed before branding.` is one comment that counts, and any other non-empty text after the colon counts the same way.

The comment is one of:

- a `//` or `/* */` comment on the line immediately above the assertion's owning statement
- the same comment with only a blank line between it and that statement
- a comment immediately above an `export` of that statement
- an inline comment on the assertion, before the asserted expression (`const got = /* SAFETY: reason */ raw as Brand`, and the same inline form on an angle-bracket assertion)

A blank line before the comment, with the comment still immediately above the statement, still counts.

### What stays silent

- `as const` and `<const>`, including `[1, 2] as const` and `<const>{ id: "one" }`, with no comment
- a chain made only of const assertions, with no comment
- a non-const assertion with an acceptable justification in one of the positions above, including a block comment and an inline comment
- the same source when the markers list is only `INVARIANT` and the comment uses `INVARIANT`, and when the list contains several markers and the comment uses any one of them

## `no-unsafe-dictionary-type`

### Published rule

`no-unsafe-dictionary-type` is a generic `lint-policy` rule. It reports only when that rule is enabled. Enabling it at `error` makes a diagnostic from this rule fail the lint. It does not rewrite source when the host is asked to fix: the violating file bytes stay unchanged and the diagnostic is still reported.

### Wrapped dictionaries

`Readonly`, `Partial`, `Required`, `Pick`, and `Omit` applied to a dictionary whose value contract is unsafe are themselves reported. A diagnostic from this rule starts at the name of that wrapper:

- `type Frozen = Readonly<Record<string, unknown>>` reports with a diagnostic that starts at `Readonly`. The same holds for `Partial` and `Required` of that dictionary, for `Pick` of it that keeps every key (`Pick<…, string>`) and `Omit` of it that removes none (`Omit<…, never>`), and when the dictionary value is a brand-only empty type.
- When wrappers nest, as in `Readonly<Partial<Required<Record<string, unknown>>>>`, a diagnostic starts at the outermost wrapper name.
- When the wrapped dictionary is a same-file alias, as in `type Base = Record<string, unknown>; type Picked = Pick<Base, string>`, a diagnostic starts at `Pick`. The alias declaration `Base` reports as well.

A finding on the inner dictionary, on an inner wrapper, or on the alias used as the argument may also appear. It does not stand in for the finding at the wrapper name.
