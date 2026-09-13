# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**PathSel** (pronounced "path sel") lets a caller declaratively specify how to extract values from a JSON document. The **pathsel.py** library evaluates a PathSel expression against ordinary Python data — mappings, sequences, strings, numbers, booleans, and null — and returns the selected value.

A first-time integrator takes a document whose `foo` key holds a mapping whose `bar` key is the string `baz`, evaluates the expression `foo.bar`, and receives `baz`. Evaluating `foo.bar` on a document that has no such path yields null rather than failing. Leaving `baz` unextracted, returning the whole document, or raising on a missing path is a failure of the product.

The library exposes two complementary ways to evaluate an expression: a one-shot search that takes the expression text and the document together, and a compile-then-search path that parses the expression once and applies the same parsed expression to many documents. Both paths produce the same result for the same expression and document. Optional evaluation options control how constructed mappings are built and let the caller attach extra language functions.

The finished product is an **importable Python library**, not a command-line program, not a network service, and not a wire protocol. Integrators install the package and call the published search and compile entries. There is no product-owned configuration file. The library evaluates expressions against already-loaded Python values; it is not a JSON encoder or decoder, and it does not write back into the caller’s document.

The product is a pure-Python library with zero declared runtime third-party dependencies. No compiled extension, native code, GPU, or accelerator is required. The language is Python 3.9 or newer, including CPython and PyPy. Platforms are Linux, macOS, and Windows; documented execution is Linux. Hardware is CPU-only.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is the importable package `pathsel`. Callers write `import `pathsel`` or `from `pathsel` import …` and obtain the published entries from that package root. The importable package is a single top-level directory named `pathsel`. Importing the package performs no I/O against caller files, starts no processes, and opens no sockets.

The independently verifiable library entries named from this package root are:

- `search` — one-shot evaluation. The caller supplies expression text and a document and receives the selected value, or the call does not succeed. An optional evaluation-options object may be attached.
- `compile` — parse the expression once and return a parsed expression. The parsed expression is then searched against one or more documents without re-supplying the expression text. An optional evaluation-options object may be attached at search time.

The successful result of `compile` exposes a callable attribute named `search`. That method is the compile-then-search path. It is not a second top-level function.

**Not in this surface.** A command-line program, a `python -m` entry, a web server, or a configuration framework. Encoding or decoding JSON text. Mutating the input document. A particular evaluation-throughput figure. An expression-compilation cache size. A later official language revision that this library does not implement.

### Naming conventions

**Product and package.** The product identity is PathSel. The installable distribution name and the importable top-level package are spelled `pathsel`.

**Evaluation entries.** One-shot evaluation is `search`. Parse-once is `compile` (this is the published name on the package, even though it coincides with the host builtin of the same spelling). Both names are snake_case callables imported from the package root. The first positional argument of each is the expression as a Python text string. The second positional argument of one-shot `search` is the document.

**Parsed-expression search.** The callable used to apply a compiled expression is also spelled `search`. It is an attribute of the parsed expression, not a name imported from the package root. Its first positional argument is the document.

**Null.** The language’s missing or empty result is the host none. A successful search that selects nothing returns that none; it does not raise.

**Refusal.** Empty, ill-formed, and incomplete expression text is refused as a kind of `ValueError` (or a subclass of `ValueError`). Wording of the report is not a fixed sentence. The observer can tell those kinds apart by a kind marker on the raised value that does not vary with the expression text and is not the wording of any report. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that type object, and different kinds when the type objects differ. A more specific type is a different marker; subclassing is not the same kind. Class names are not a graded spelling. Leftover after stripping the expression text is not that marker.

**Built-in language functions.** A function call is an unquoted identifier followed by a parenthesized argument list. The built-in names are exactly `abs`, `avg`, `ceil`, `contains`, `ends_with`, `floor`, `join`, `keys`, `length`, `map`, `max`, `max_by`, `merge`, `min`, `min_by`, `not_null`, `reverse`, `sort`, `sort_by`, `starts_with`, `sum`, `to_array`, `to_number`, `to_string`, `type`, and `values`.

**Layout.** The importable package directory is `pathsel`.

### Global observables an implementer must reproduce

**No product config file.** The library does not read a configuration-file syntax of its own and does not require a config file to be present.

**No command-line product.** There is no console-script entry and no `python -m` program that is part of this surface. Outcomes are returned or raised from library calls. Library entries do not exit the host process as their success or failure report.

**Library substrate.** When the `pathsel` package is not importable, a program that does `from `pathsel` import `search`` and then calls `search` on the expression `foo.bar` against a mapping whose `foo` holds a mapping whose `bar` is `baz` does not run to completion and does not yield the string `baz`. When the package is importable, that same search yields `baz`.

**Document is not the result.** A successful search returns the selected or constructed value. It does not return the caller’s document object. Evaluation does not mutate the document.

**Missing is null.** A path that does not exist yields the host none. That is success with a null result, not a search failure. A search of `missing` against `{}` succeeds and is none. A search of `foo.bar` against `{}` succeeds and is none. Applying an identifier to an array yields none: a search of `one` against the array of strings `one`, `two`, `three` is none, while the same identifier against a mapping whose `one` key is `found` yields `found`.

**One-shot equals compile-then-search.** For the same expression and document, `search` and “`compile` then parsed `search`” return equal values. Compiling once and searching the same parsed expression against a second document uses that second document; a new compile is not required.

**Data model.** The six JSON types — object (a mapping whose keys are strings), array (a sequence), string, number (integer or floating-point, including host decimals; a boolean is not a number), boolean (true and false, not the numbers 1 and 0), and null (the host none) — plus expression references as function arguments. Host decimals participate as numbers for comparison; a built-in that requires a number refuses a host decimal as an invalid-type failure (a kind of `ValueError`), distinguishable from unknown-function and invalid-arity. Host values that are not one of those types are accepted as current values; built-in functions that need a JSON type refuse them as an invalid type unless a conversion function defines another outcome.

**False values.** For the and operator, the or operator, the not operator, and filter predicates, the finite false-value set is: false, null, the empty string, the empty array, and the empty object. The number 0 and the number 0.0 are not false values.

**Expression refusals.** A zero-length expression does not succeed. An expression of only spaces, tabs, line feeds, or carriage returns, with no other tokens, does not succeed. An expression that is not well-formed does not succeed. An incomplete expression that ends where a token is still required does not succeed. None of those calls yields a document value or a successful none. Each refusal is a kind of `ValueError` (or a subclass of `ValueError`).

The observer can tell the empty, syntax, and incomplete kinds apart by a kind marker that does not vary with the expression text and is not the wording of any report. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that type object, and different kinds when the type objects differ. A more specific type is a different marker; subclassing is not the same kind. Class names are not a graded spelling. Message wording is not a compatibility contract.

After the expression text itself is set aside, the remaining failure report — the report text together with public, non-callable attributes whose values are strings, integers, floats, or none — of an empty refusal still differs from a syntax refusal of `foo.` and from an incomplete refusal of `(`. That leftover contrast is how the observer tells those failures apart as different places or different reports; it is not the same-kind marker.

- **Empty.** The zero-length expression. That kind marker differs from a syntax refusal of `foo.`, from an incomplete refusal of `(`, and from a successful none (`missing` on `{}` succeeds and is none).
- **Incomplete.** An opening token with no matching close, and an expression of only spaces, tabs, line feeds, or carriage returns. Concrete incomplete texts include `(`, `[`, `{`, a single space, a single tab, a single line feed, a single carriage return, and a string that is only those whitespace characters. A whitespace-only refusal shares the incomplete-expression kind marker with `(`. It does not use the empty-expression kind marker of a zero-length expression. After the expression text is set aside, that leftover still differs from the empty kind of a zero-length expression and from the syntax kind of `foo.`.
- **Syntax.** A non-empty ill-formed expression, including: a lone `.`; a trailing `.` such as `foo.`; a leading `.` such as `.foo`; doubled dots `foo..bar`; a lone `]`, `}`, or `)`; `foo.1`; `foo.-11`; a lone `-` that is not part of a number; `foo[*]bar`; and `foo[8:2:0:1]`. A failure of `foo.` and a failure of `.foo` remain distinguishable as different places in the expression after the expression text is set aside. A lone `[` or `{` or `(` is the incomplete kind, not this syntax kind.

An unclosed backtick literal, an unclosed raw string, a lone `=`, `foo-bar`, and an unclosed double-quoted identifier do not succeed on either public entry. Each refusal is a kind of `ValueError` (or a subclass of `ValueError`) and does not yield a document value or a successful none. Each does not use the empty-expression kind marker of a zero-length expression. Each does not use the incomplete-expression kind marker of unmatched `(`. A caller who already handles the syntax kind of `foo.` also handles these refusals, including when the syntax form is more specific than the trailing-dot form. They do not share the kind marker of `foo.`. Leftover report text after stripping, and a fixed phrase, are not required.

A successful none and a syntax refusal are distinguishable: `foo.bar` on `{}` succeeds and is none; `foo.` does not succeed.

**Evaluation options.** When the caller omits options, constructed objects use the host’s ordinary mapping type and only the built-in functions above are available. When options are supplied, the mapping-type slot is the attribute `dict_cls` and the custom-function slot is the attribute `custom_functions`. When `dict_cls` is omitted or is the host none, every constructed multiselect hash uses the host ordinary mapping. When `dict_cls` is set to a type, every multiselect hash — including nested hashes — is built with that type. A custom function on one options object does not change a later search that does not attach that provider. Built-in functions that return a new object, including `merge`, still return the host’s ordinary mapping.

**Function-call refusals.** A name that is not in the built-in set and is not supplied as a custom function is an unknown-function failure. A wrong argument count is an invalid-arity failure. A wrong argument type is an invalid-type failure. Each is a kind of `ValueError`. They do not return a search result. They are distinguishable from each other and from a successful none.

## `pathsel`

The installable distribution and the importable top-level package are both `pathsel`. Callers declare the interface from this package root (`import `pathsel`` or `from `pathsel` import …`). Importing the package performs no I/O, starts no processes, and opens no sockets.

The importable package is a single top-level directory named `pathsel`.

These names are importable as ``pathsel`.<name>` and as `from `pathsel` import <name>`:

- `compile`
- `search`

Each of those names is a callable.

Typical import used to evaluate an expression in one shot and to parse an expression for reuse:

```
from `pathsel` import `compile`, `search`
```

A script that only needs a subset may import that subset, for example `from `pathsel` import `search`` or `from `pathsel` import `compile``.

When `pathsel` is not importable, a program that does `from `pathsel` import `search`` and then calls `search` on the expression `foo.bar` against a mapping whose `foo` holds a mapping whose `bar` is `baz` does not run to completion and does not yield the string `baz`. When the package is importable, that same call yields `baz`.

## `pathsel.compile`

Import `compile` from the package root `pathsel` (`from `pathsel` import `compile``). Parse one PathSel expression from a Python text string and return a parsed expression that can be searched against many documents, or fail. The expression is passed as the first positional argument.

### Signature

```
`compile`(expression)
```

- `expression` — the PathSel expression as a Python text string. Passed positionally.

The call does not take a document. It does not evaluate the expression against data. It does not take evaluation options. It does not read or write files, does not mutate the process environment, and does not exit the host process.

### Return shape

On success, returns a parsed expression. The return is not the host none and is not a document value. The parsed expression exposes a callable attribute named `search`. That attribute is how the compiled expression is applied to a document. The parsed expression can be kept and searched against a second document without calling `compile` again.

On failure, the call raises and does not return a searchable parsed object.

### Parsed `search`

```
`search`(value, options=None)
```

- `value` — the document, as ordinary Python data. Passed as the first positional argument.
- `options` — optional evaluation-options object. Passed as the second positional argument when supplied. When omitted or `None`, constructed objects use the host’s ordinary mapping type and only the built-in language functions are available. When supplied, the mapping-type slot is the attribute `dict_cls`: omitted or the host none keeps every constructed multiselect hash as the host ordinary mapping; a type builds every multiselect hash — including nested hashes — with that type. Built-in functions that return a new object, including `merge`, still return the host ordinary mapping. The custom-function provider slot is `custom_functions`.

Searching a parsed expression does not re-parse the expression text. For the same expression and document, this call returns a value equal to the one-shot package-root `search` of that pair.

The call does not mutate the document, does not mutate the process environment, and does not exit the host process.

### Reuse

Compiling `foo.bar` once and searching the parsed expression against a mapping whose `foo.bar` is the string `baz` yields `baz`. Searching that same parsed expression against a second mapping whose `foo.bar` is the string `other` yields `other`. The two documents do not need a new compile.

The same reuse holds when the identifier segments are not the sample names `foo` and `bar`: compiling a two-segment dotted path once and searching it against two documents that bind that path to different payloads yields those two payloads.

### Agreement with one-shot `search`

A successful compile-then-search equals a one-shot `search` of the same expression and document. This holds at least for:

- `foo.bar` on `{foo: {bar: baz}}` — both paths yield `baz`.
- `foo.bar[0]` on a document whose `foo.bar` is the array of strings `one` then `two` — both paths yield `one`.
- A two-segment dotted path whose keys are not those sample names, including when the selected value is the first element of an array written as `[0]` after the path.

### Successful null through a parsed expression

A compiled expression whose path is missing on the document succeeds and yields the host none. Compiling `foo.bar.baz.bad` and searching the parsed expression against a mapping whose only path is `foo.bar.baz` equal to `correct` yields none. That call does not raise.

### Refusal

When the expression text is empty, whitespace-only, incomplete, or otherwise not well-formed, `compile` raises a `ValueError` (or a subclass of `ValueError`). It does not return a parsed expression.

The observer can tell the empty, syntax, and incomplete kinds apart by a kind marker that does not vary with the expression text and is not the wording of any report. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that type object, and different kinds when the type objects differ. A more specific type is a different marker; subclassing is not the same kind. Class names are not a graded spelling. Message wording is not a fixed sentence.

After the expression text itself is set aside, the remaining failure report — the report text together with public, non-callable attributes whose values are strings, integers, floats, or none — of an empty refusal still differs from a syntax refusal of `foo.` and from an incomplete refusal of `(`. That leftover contrast is how the observer tells those failures apart as different places or different reports; it is not the same-kind marker.

- A zero-length expression is the empty kind. That kind marker differs from a syntax refusal of `foo.` and from an incomplete refusal of `(`. After the expression text is set aside, that leftover also differs from those two refusals. That leftover contrast is not the same-kind marker.
- An expression of only spaces, or of only a tab, is the incomplete kind: it shares the incomplete-expression kind marker with `(`, and it does not use the empty-expression kind marker of a zero-length expression. After the expression text is set aside, that leftover still differs from the empty kind of a zero-length expression and from the syntax kind of `foo.`.
- `foo.` is the syntax kind. That leftover differs from the empty kind and from the incomplete kind of `(`.
- An unmatched opening parenthesis `(` is the incomplete kind. After the expression text is set aside, that leftover differs from a syntax refusal of `foo.` and from the empty kind of a zero-length expression.

The same expression texts that one-shot `search` refuses, `compile` refuses. Empty, incomplete, and ordinary syntax refusals such as `foo.` remain the same kinds as on one-shot `search`.

Compile of an unclosed backtick literal, of an unclosed raw string, of a lone `=`, of `foo-bar`, and of an unclosed double-quoted identifier does not succeed and does not return a searchable parsed expression. Each refusal is a kind of `ValueError` (or a subclass of `ValueError`). Each does not use the empty-expression kind marker of a zero-length expression. Each does not use the incomplete-expression kind marker of unmatched `(`. A caller who already handles the syntax kind of `foo.` also handles these refusals, including when the syntax form is more specific than the trailing-dot form. They do not share the kind marker of `foo.`. Leftover report text after stripping, and a fixed phrase, are not required.

Those refusals are distinguishable from a successful compile of a well-formed expression, including an expression whose later search will yield none (`foo.bar.baz.bad` compiles; the none appears when that parsed expression is searched).

## `pathsel.functions`

Import the function-provider surface from the submodule `pathsel`.`functions` (`from `pathsel`.`functions` import …`). This submodule is the published attachment path for extra language functions. It is not a name imported from the package root.

Importing `pathsel`.`functions` performs no I/O, starts no processes, and opens no sockets.

These names are importable as ``pathsel`.`functions`.<name>` and as `from `pathsel`.`functions` import <name>`:

- `Functions`
- `signature`

Each of those names is a callable.

Typical import used to declare extra language functions and to build a provider that extends the built-in set:

```
from `pathsel`.`functions` import `Functions`, `signature`
```

A script that only needs one of those names may import that subset, for example `from `pathsel`.`functions` import `Functions`` or `from `pathsel`.`functions` import `signature``.

## `pathsel.functions.Functions`

Import `Functions` from `pathsel`.`functions` (`from `pathsel`.`functions` import `Functions``). Callable class. A provider is an instance of `Functions` or of a subclass. The instance is the custom function provider attached to an evaluation-options object. Subclassing extends the built-in language functions; it does not replace them.

### Signature

```
`Functions`()
```

No required arguments. Returns a provider instance that implements the built-in language-function set.

A subclass is created by supplying attributes whose names start with the prefix `_func_` and whose values are callables that have been passed through `signature`. Instantiating that subclass with no arguments yields a provider that implements every built-in name plus each extra name. The language-function name is the attribute name with that prefix removed: the attribute whose name is `_func_` followed by `custom_add` is the language function `custom_add`.

The implementation callable receives the provider instance as its first argument. Each remaining argument is one already-evaluated function argument, in the same order as the mappings passed to `signature`. The callable’s return value is the value of that function call.

### Attachment

The provider is attached on the evaluation-options object as the attribute `custom_functions`. The mapping type used for every constructed multiselect hash is attached on that same object as the attribute `dict_cls`. That options object is passed to package-root `search` as its third positional argument, or to the parsed-expression `search` as its second positional argument. `compile` does not take a provider.

When `custom_functions` is omitted or is the host none, only the built-in set is available. When `dict_cls` is omitted or is the host none, every constructed multiselect hash uses the host ordinary mapping. When `dict_cls` is set to a type, every multiselect hash — including nested hashes — is built with that type. Built-in functions that return a new object, including `merge`, still return the host ordinary mapping. One options object may carry a provider and a mapping type together; both apply on that search. A provider on one options object does not change a later search that does not attach that provider, a search whose `custom_functions` is the host none, or a search that attaches a different provider. A mapping type on one options object does not change a later search that omits options or whose `dict_cls` is the host none.

### Built-in set on an extending provider

A provider that extends `Functions` still implements every built-in name: `abs`, `avg`, `ceil`, `contains`, `ends_with`, `floor`, `join`, `keys`, `length`, `map`, `max`, `max_by`, `merge`, `min`, `min_by`, `not_null`, `reverse`, `sort`, `sort_by`, `starts_with`, `sum`, `to_array`, `to_number`, `to_string`, `type`, and `values`.

A search that uses that provider still evaluates a call of `length` on the JSON array `[1, 2]` as 2. A later search without a provider still evaluates that same call as 2.

### Extra functions

After attaching a provider that declares `custom_add` of two `number` arguments as their sum and `my_subtract` of two `number` arguments as their difference:

- calling `custom_add` with the JSON numbers 1 and 2 yields 3
- calling `my_subtract` with the JSON numbers 10 and 3 yields 7

The same declarations apply when the two arguments are selected fields: the sum is the host sum of those field values, and the difference is the host difference, for integers and for floating-point values.

A provider that declares a one-argument function whose accepted types are `string`, `array`, `object`, and `null`, and whose implementation returns 0 for null and the host length otherwise, yields 3 for the path `a.b` on `{a: {b: [1, 2, 3]}}` and yields 0 for the path `a.c` (a missing field, which is null). That 0 is the integer zero, not the host none. The same function yields the host length of an array, of an object, and of a string.

A successful extra-function result is not the caller’s document object. Evaluation does not mutate the document.

The same extra function is available on one-shot `search` and on compile-then-search when the same options object is passed at search time. Compiling an expression that names an extra function succeeds; searching that parsed expression without a provider is an unknown-function failure.

A name registered on one provider is absent from another provider that did not declare it.

When one options object carries both a mapping type and a provider that declares `custom_add` of two `number` arguments as their sum, searching `{sum: custom_add(\`1\`, \`2\`)}` yields a mapping of that supplied type whose `sum` field is 3.

### Refusal

Each of the following is a kind of `ValueError` (or a subclass of `ValueError`). The call does not return a document value and does not succeed as none. Message wording is not a fixed sentence. Class names are not a graded spelling.

The observer can tell the three kinds apart by a kind marker that does not vary with the expression text, the function name, or leftover report wording. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that marker, and different kinds when the type objects differ. A more specific form of the same kind still counts as that kind. Leftover report text after the expression text and the function-name identifiers are set aside is not that marker.

- **Unknown-function.** A name that is not built-in and is not declared on the attached provider. This is the same kind as a search of `unknown_function(\`1\`, \`2\`)` with no provider. `custom_add` without a provider, with an options object whose `custom_functions` is the host none, or with an options object that supplies only a mapping type, is this kind. A name declared only on a different provider is this kind on the provider that lacks it.
- **Invalid-arity.** A declared extra function given the wrong number of arguments. This is the same kind as a search of `abs()` and of `abs(\`1\`, \`2\`)`. `custom_add` of two `number` arguments refuses one argument and refuses three arguments; those two refusals share this kind with each other.
- **Invalid-type.** A declared extra function given a value outside its accepted types. This is the same kind as a search of `abs(str)` against a mapping whose `str` field is a string. `custom_add` of two `number` arguments refuses a string in either slot and refuses a boolean. A function that accepts `string`, `array`, `object`, and `null` refuses a boolean, refuses a number, and refuses a host value that is not a JSON type. A host value that is not a JSON type is not one of those accepted types.

Those three kinds remain distinguishable from each other and from a successful none (`missing` on `{}` succeeds and is none). The same three kinds hold on one-shot `search` with options and on compile-then-search of a successfully parsed call with the same options.

## `pathsel.functions.signature`

Import `signature` from `pathsel`.`functions` (`from `pathsel`.`functions` import `signature``). Callable decorator factory. It records the accepted types of one language-function implementation so a `Functions` subclass can register that implementation as a named function.

### Signature

```
`signature`(*arguments)
```

- `arguments` — zero or more positional mappings, one per function parameter, in call order. The number of mappings is the required argument count.

Each mapping has a `types` key whose value is a list of type-name strings. A value is accepted when its language type is one of those names. The type names used to declare extra functions are:

- `number` — an integer or a floating-point value. A boolean is not a `number`.
- `string` — a Unicode text value.
- `array` — a sequence.
- `object` — a mapping whose keys are strings.
- `null` — the host none.

A host value that is not one of those language types is not accepted by a declaration that lists only those names.

The call returns a decorator. Applying that decorator to an implementation callable returns a callable suitable as a `_func_`-prefixed attribute on a `Functions` subclass:

```
`signature`(*arguments)(implementation)
```

`implementation` is a callable `(provider, *resolved_args) -> value`. The decorator does not call the implementation. It does not evaluate an expression.

### Enforcement

When a registered function is invoked during `search`, the attached provider requires exactly as many resolved arguments as mappings were passed to `signature`. A different count is an invalid-arity failure, a kind of `ValueError`. That kind is the same kind as a search of `abs()` and of `abs(\`1\`, \`2\`)`.

Each resolved argument is then checked against that slot’s `types` list. A value outside the list is an invalid-type failure, a kind of `ValueError`. That kind is the same kind as a search of `abs(str)` against a mapping whose `str` field is a string.

Those refusals do not return a search result and do not succeed as none. They are distinguishable from each other and from an unknown-function failure (the kind of a search of `unknown_function(\`1\`, \`2\`)`) by a kind marker that does not vary with the expression text, the function name, or leftover report wording. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that marker, and different kinds when the type objects differ. A more specific form of the same kind still counts as that kind. Message wording is not a fixed sentence. Class names are not a graded spelling. Leftover report text after the expression text and the function-name identifiers are set aside is not that marker.

A two-slot declaration of `{`types`: [`number`]}` then `{`types`: [`number`]}` accepts two integers, two floats, or one of each, and refuses a string or a boolean in either slot. A one-slot declaration of `{`types`: [`string`, `array`, `object`, `null`]}` accepts a string, an array, an object, or null, and refuses a boolean, a number, and a host value that is not a JSON type.

## `pathsel.search`

Import `search` from the package root `pathsel` (`from `pathsel` import `search``). Evaluate one PathSel expression against a document in a single call and return the selected value, or fail. The expression is the first positional argument. The document is the second positional argument.

### Signature

```
`search`(expression, data, options=None)
```

- `expression` — the PathSel expression as a Python text string. Passed positionally.
- `data` — the document: ordinary Python data used as the starting current value. Passed as the second positional argument. Typically a mapping or sequence that came from JSON; any nested combination of object, array, string, number, boolean, and null is accepted.
- `options` — optional evaluation-options object. Passed as the third positional argument when supplied. When omitted or `None`, constructed objects use the host’s ordinary mapping type and only the built-in language functions are available. When supplied, the mapping-type slot is the attribute `dict_cls`: omitted or the host none keeps every constructed multiselect hash as the host ordinary mapping; a type builds every multiselect hash — including nested hashes — with that type. Built-in functions that return a new object, including `merge`, still return the host ordinary mapping. The custom-function provider slot is `custom_functions`.

The call does not read or write files, does not mutate the document, does not mutate the process environment, and does not exit the host process.

### Return shape

On success, returns the selected or constructed value. A successful missing or empty result is the host none. A successful none is a real none: the call returned, and no exception was raised.

The return is not the caller’s document object. A search of `foo.bar` against `{foo: {bar: baz}}` yields the string `baz`, not the outer mapping.

On failure, the call raises and does not return a document value and does not succeed as none.

### Nested field and index (one shot)

- `foo.bar` on a mapping whose `foo` key holds a mapping whose `bar` key is the string `baz` yields `baz`.
- The same dotted selection works when the two identifier segments are not those sample names: the selected payload is returned, and that payload is not the document object.
- `foo.bar[0]` on a document whose `foo.bar` is the array of strings `one` then `two` yields `one`.

### Agreement with compile-then-search

A one-shot `search` of an expression and document equals compiling that expression and searching the parsed expression against that document. This holds at least for `foo.bar` on the `baz` document, for `foo.bar[0]` on the `[one, two]` document, and for a two-segment dotted path (with or without a trailing `[0]`) whose keys are not those sample names.

### Missing path is successful null

These calls return; they do not raise. The value is the host none.

- `foo.bar.baz.bad` against a mapping whose only path is `foo.bar.baz` equal to `correct` (the complete path `foo.bar.baz` on that document yields `correct`).
- `bad` against that same document.
- `missing` against `{}`.
- `foo.bar` against `{}`.
- `one` against the array of strings `one`, `two`, `three` (an identifier selects a field of an object, not an array element). The same identifier against `{one: found}` yields `found`.
- A three-segment dotted path whose last segment is absent on an otherwise matching nested mapping.

### Refusal

When the expression text is empty, whitespace-only, incomplete, or otherwise not well-formed, `search` raises a `ValueError` (or a subclass of `ValueError`). The call does not return the document and does not succeed as none.

The observer can tell the empty, syntax, and incomplete kinds apart by a kind marker that does not vary with the expression text and is not the wording of any report. The marker is the type object of the raised value. Two failures are the same kind exactly when they share that type object, and different kinds when the type objects differ. A more specific type is a different marker; subclassing is not the same kind. Class names are not a graded spelling. Message wording is not a fixed sentence.

After the expression text itself is set aside, the remaining failure report — the report text together with public, non-callable attributes whose values are strings, integers, floats, or none — of an empty refusal still differs from a syntax refusal of `foo.` and from an incomplete refusal of `(`. That leftover contrast is how the observer tells those failures apart as different places or different reports; it is not the same-kind marker.

**Empty.** A zero-length expression. That kind marker differs from a syntax refusal of `foo.`, from an incomplete refusal of `(`, and from a successful none (`missing` on `{}` succeeds and is none). After the expression text is set aside, that leftover also differs from a syntax refusal of `foo.` and from an incomplete refusal of `(`.

**Incomplete.** An opening token with no matching close, and an expression of only spaces, tabs, line feeds, or carriage returns. Concrete incomplete texts include `(`, `[`, `{`, a single space, a single tab, a single line feed, a single carriage return, and a string that is only those whitespace characters. A whitespace-only refusal shares the incomplete-expression kind marker with `(`. It does not use the empty-expression kind marker of a zero-length expression. After the expression text is set aside, that leftover still differs from the empty kind of a zero-length expression and from the syntax kind of `foo.`.

**Syntax.** A non-empty ill-formed expression. Concrete texts that fail this way include:

- a lone `.`
- a trailing `.` such as `foo.`
- a leading `.` such as `.foo`
- doubled dots `foo..bar`
- a lone `]`, `}`, or `)`
- `foo.1` (a bare number after a dot)
- `foo.-11`
- a lone `-` that is not part of a number
- `foo[*]bar` (a wildcard not followed by a continuation the grammar allows)
- `foo[8:2:0:1]` (a slice with more than three colon-separated parts)

Each of those refusals is a kind of `ValueError` (or a subclass of `ValueError`) and does not yield the document or a successful none. After the expression text is set aside, each leftover differs from the empty kind of a zero-length expression and from the incomplete kind of `(`.

A failure of `foo.` and a failure of `.foo` remain distinguishable as different places in the expression after the expression text is set aside. The same place-contrast holds when the identifier is not the sample name `foo`. A lone `[` or `{` or `(` is the incomplete kind, not this syntax kind.

An unclosed backtick literal, an unclosed raw string, a lone `=`, `foo-bar`, and an unclosed double-quoted identifier do not succeed. Each refusal is a kind of `ValueError` (or a subclass of `ValueError`) and does not yield the document or a successful none. Each does not use the empty-expression kind marker of a zero-length expression. Each does not use the incomplete-expression kind marker of unmatched `(`. A caller who already handles the syntax kind of `foo.` also handles these refusals, including when the syntax form is more specific than the trailing-dot form. They do not share the kind marker of `foo.`. Leftover report text after stripping, and a fixed phrase, are not required.

`foo.bar` on `{}` succeeds and is none. `foo.` on `{}` does not succeed.

### Library substrate

When the `pathsel` package is importable, `from `pathsel` import `search`` followed by `search` of `foo.bar` against `{foo: {bar: baz}}` yields `baz`. When the package is not importable, that same program does not run to completion and does not produce `baz`.

