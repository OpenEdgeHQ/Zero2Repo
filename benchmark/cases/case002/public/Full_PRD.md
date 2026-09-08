# PathSel — Full Product Requirements Document

## Product overview

**PathSel** (pronounced "path sel") lets a caller declaratively specify how to extract values from a JSON document. The **pathsel.py** library evaluates a PathSel expression against ordinary Python data — mappings, sequences, strings, numbers, booleans, and null — and returns the selected value.

A first-time integrator takes a document whose `foo` key holds a mapping whose `bar` key is the string `baz`, evaluates the expression `foo.bar`, and receives `baz`. Evaluating `foo.bar` on a document that has no such path yields null rather than failing. Leaving `baz` unextracted, returning the whole document, or raising on a missing path is a failure of the product.

The library exposes two complementary ways to evaluate an expression: a one-shot search that takes the expression text and the document together, and a compile-then-search path that parses the expression once and applies the same parsed expression to many documents. Both paths produce the same result for the same expression and document. Optional evaluation options control how constructed mappings are built and let the caller attach extra language functions.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call spellings belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished pathsel.py product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **PathSel expression** | A Unicode text in the PathSel language. One expression is evaluated against one current value at a time. |
| **Document** | The Python value supplied as the starting current value: typically a mapping or sequence that came from JSON, but any nested combination of the six data types below is accepted. |
| **Search entry** | The one-shot library entry: the caller supplies an expression and a document (and optionally evaluation options) and receives the selected value, or the call does not succeed. Specified in FP-01. |
| **Compile entry** | The library entry that parses an expression once and returns a parsed expression. Specified in FP-01. |
| **Parsed expression** | The successful result of the compile entry. It can be searched against many documents without re-supplying the expression text. |
| **Current value** | The value the expression is looking at. Search starts with the document. Pipe, projection, and function argument evaluation change the current value for a subexpression. |
| **Null** | The language’s missing or empty result. It is Python’s none. A missing field, an out-of-range index, and a selector applied to the wrong kind of value all yield null; they do not fail. |
| **Object** | A mapping (JSON object). Keys are strings. |
| **Array** | A sequence (JSON array). |
| **Number** | An integer or a floating-point value. Host decimal values participate as numbers. A boolean is not a number. |
| **String** | A Unicode text value. |
| **Boolean** | The values true and false. They are not the numbers 1 and 0. |
| **Expression reference** | A deferred subexpression, written with a leading ampersand, that a built-in function later applies to each element. Specified in FP-05 and used in FP-07. |
| **False value** | A value the language treats as false for the and operator, the or operator, the not operator, and filter predicates. The finite set is: false, null, the empty string, the empty array, and the empty object. The number 0 and the number 0.0 are not false values. |
| **True value** | Any value that is not a false value. |
| **Projection** | An expression that walks every element of an array (or every value of an object) and collects the non-null results of a right-hand subexpression into a new array. Null results are dropped, not stored. |
| **Evaluation options** | An optional object the caller attaches to a search. It may supply a mapping type for constructed objects and a custom function provider. Specified in FP-08. |
| **Built-in function** | One of the finite set of language functions listed in FP-07. A function is invoked by name with parentheses. |
| **Core capability** | A user-observable capability that reflects PathSel’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

pathsel.py is a **library**. Integrators reach it by installing the package and calling the search entry or the compile entry. A command-line helper is installed with the package; it is not a graded core capability (see Non-goals).

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- Evaluate a PathSel expression against a document, either in one shot or by compiling first and searching the parsed expression; missing paths yield null; empty or ill-formed expression text does not succeed (FP-01).
- Select fields by unquoted and quoted identifiers, including dotted subexpressions and whitespace between tokens (FP-02).
- Select array elements by index (including negative indices), by slice, and by one-level flatten (FP-03).
- Project through list wildcards, object wildcards, and filter predicates (FP-04).
- Build new arrays and objects with multiselect, chain results with pipe, name the current value, write JSON literals and raw strings, and form expression references (FP-05).
- Compare values and combine them with and, or, not, and parentheses (FP-06).
- Call the finite set of built-in functions, including those that consume expression references (FP-07).
- Control constructed-object type and attach custom language functions through evaluation options (FP-08).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library with zero declared runtime third-party dependencies. No compiled extensions, native code, GPU, or accelerator are required or claimed.
- **Language:** Python 3.9 or newer, including the CPython and PyPy implementations the project tests.
- **Platforms:** Linux, macOS, and Windows. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host that can import pathsel.py from this repository’s source tree and evaluate `foo.bar` against a nested mapping.
- **Data model:** The six JSON types — object, array, string, number, boolean, null — plus expression references as function arguments. Host decimal numbers are numbers for comparison (FP-06), not for built-in functions: a function that requires a number refuses a host decimal as an invalid type. Host values that are not one of those types are accepted as current values; built-in functions that need a JSON type refuse them as an invalid type unless a conversion function defines another outcome (FP-07).
- **Missing is null:** A path that does not exist yields null. That is success with a null result, not a search failure.
- **Error text:** Wording of failure messages is informational. Graded behavior is success versus failure, that the failure is a kind of value error, and that the observer can tell the failure kinds in FP-01 apart — not a particular sentence.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real pathsel.py behavior matches the described outcomes when an expression is searched against a constructed document, or when invalid expression text or an invalid function call is refused.
- **Absent / hollow:** Search always returns the document; every missing path raises; wildcards return objects instead of arrays of values; filters ignore the predicate; built-in functions are stubs; compile does not reuse.

Cheaper proxies (a single hardcoded `foo.bar` lookup, a JSON-pointer subset, a regular-expression scrape, or a memorized fixture table) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces PathSel evaluation for a core capability.

**Negative control (library substrate):** When pathsel.py is deliberately not importable in an isolated subprocess (removed from the import path), a search of `foo.bar` against a mapping whose `foo` holds a mapping whose `bar` is `baz` must fail to produce the string `baz` — a hard assertion, not a skip. When the interpreter is present and the package is imported from this tree, that same search yields `baz`. Output-equality alone is not proof that the real package ran.

## Non-goals

- Shipping a graded command-line product. A helper named psel.py is installed with the package and can search a JSON file or standard input, or print a parse tree, but those behaviors are not a core feature point.
- Being a JSON encoder or decoder. The library evaluates expressions against already-loaded Python values. How a caller reads JSON text into those values is outside this product.
- Mutating the input document. Evaluation returns a selected or constructed value; it does not write back into the caller’s document.
- Guaranteeing a particular evaluation-throughput benchmark. The performance suite and the hypothesis suite are development tools, not graded oracles.
- Treating compliance-sync scripts, the grammar stress helper, the parse-tree renderer, packaging scripts, or the expression-compilation cache as product capabilities. Cache presence or size is not observable through the public entries and is not graded.
- Treating a later official language revision that this library does not implement as required. The graded language is the expression surface documented here and exercised by this repository’s compliance cases.

---

## Feature points

### FP-01: Search an expression and compile it for reuse

**Public entry:** The search entry and the compile entry of the pathsel.py library. The caller supplies expression text. The search entry also supplies a document and may supply evaluation options (FP-08). The compile entry returns a parsed expression; searching that parsed expression against a document (with optional evaluation options) is the second path. Field selection, indexing, projections, constructors, logic, and functions are specified in FP-02 through FP-07. This feature point is the two entries, the missing-path-is-null rule, and the failures that prevent any evaluation.

**Normal behavior:**

- A search of `foo.bar` against a mapping whose `foo` key holds a mapping whose `bar` key is the string `baz` yields the string `baz`.
- Compiling `foo.bar` and searching the parsed expression against that same document also yields `baz`. Searching that same parsed expression against a second document whose `foo.bar` is the string `other` yields `other`. The two documents do not need to be searched with a new compile.
- A search of the same expression and document through the one-shot entry equals a compile-then-search of that pair. This holds at least for `foo.bar` on the `baz` document and for `foo.bar[0]` on a document whose `foo.bar` is the array of strings `one` then `two` (the result is `one`).
- A search of `foo.bar.baz.bad` against a mapping whose only path is `foo.bar.baz` equal to `correct` yields null. A search of `bad` against that document yields null. A search of `one` against the array of strings `one`, `two`, `three` yields null: an identifier selects a field of an object, not an array element.
- A search of an expression that is only spaces, tabs, line feeds, or carriage returns, with no other tokens, does not succeed. A search of a zero-length expression does not succeed. Neither call yields a document value.

**Boundary / error behavior:**

- A zero-length expression does not succeed. That failure is a kind of value error. The observer can tell this empty-expression failure apart from a successful null (`missing` on `{}` succeeds and is null), apart from a syntax failure on a non-empty ill-formed expression such as `foo.`, and apart from an incomplete-expression failure.
- An expression of only spaces, tabs, line feeds, or carriage returns, with no other tokens, does not succeed. That failure is the incomplete-expression kind: the observer can tell that no token was supplied. It is the same kind as an opening parenthesis with no matching close, and it is not the empty-expression kind of a zero-length expression.
- An expression that is not well-formed does not succeed and does not yield a search result. The failure is a kind of value error. The observer can tell a failure of `foo.` apart from a failure of `.foo` as different places in the expression; wording of the report is informational. Concrete cases that fail this way include: a lone `.`; a trailing `.` such as `foo.`; a leading `.` such as `.foo`; doubled dots `foo..bar`; a lone `]`, `}`, or `)`; `foo.1` (a bare number after a dot); `foo.-11`; an unclosed double-quoted identifier; an unclosed backtick literal; an unclosed raw string; a lone `=`; a lone `-` that is not part of a number; `foo-bar` (a hyphen is not part of an unquoted identifier); `foo[*]bar` (a wildcard not followed by a continuation the grammar allows); and `foo[8:2:0:1]` (a slice with more than three colon-separated parts). A lone `[` or `{` or `(` is the incomplete-expression kind of an opening token with no matching close, not this syntax kind.
- Those failures are distinguishable from a successful search that happens to return null. `foo.bar` on `{}` succeeds and is null. `foo.` does not succeed.
- An incomplete expression that ends where a token is still required (for example an opening parenthesis with no matching close) does not succeed. The observer can tell the expression was not finished, and can tell that failure apart from a syntax failure on `foo.` and apart from the empty-expression failure of a zero-length expression.

**Verifiable oracle:**

- Success: `foo.bar` on `{foo: {bar: baz}}` is `baz` through the search entry; the same pair through compile-then-search is `baz`; the same parsed expression on `{foo: {bar: other}}` is `other`; `foo.bar[0]` on `{foo: {bar: [one, two]}}` is `one` on both entries; `foo.bar.baz.bad` and `bad` on `{foo: {bar: {baz: correct}}}` are null; `one` on `[one, two, three]` is null; `missing` on `{}` succeeds and is null.
- Failure / absence: the one-shot entry and compile-then-search disagree on `foo.bar`; a parsed expression cannot be applied to a second document; a missing path raises instead of returning null; a zero-length expression yields null or the document; a whitespace-only expression is treated as the same kind of failure as a zero-length expression; `foo.` succeeds; a lone `.` yields null; a successful null and a syntax failure cannot be told apart; a `foo.` failure and a `.foo` failure cannot be told apart as different places.

---

### FP-02: Select fields with identifiers and subexpressions

**Public entry:** The search entry and the compile-then-search path of FP-01. This feature point is how an identifier names a field and how a dot chains selections. Indexing is FP-03. Wildcards are FP-04.

**Normal behavior:**

- An unquoted identifier starts with a Latin letter or an underscore and continues with Latin letters, decimal digits, or underscores. The expression `foo` on `{foo: {bar: {baz: correct}}}` yields that inner mapping. `foo.bar` yields `{baz: correct}`. `foo.bar.baz` yields the string `correct`. The identifier `__L` on `{__L: true}` yields true. The identifier `Y_1623` on `{Y_1623: true}` yields true.
- Spaces, tabs, line feeds, and carriage returns may appear between tokens and do not change meaning. The expression `foo` then a line feed then `.` then a line feed then `bar` then a line feed then `.baz` on the document above yields `correct`.
- A quoted identifier is a JSON string in double quotes. It can name a field that an unquoted identifier cannot: a space, a dot, a hyphenated token that is not a valid unquoted identifier, a Unicode character, or a key that starts with a digit. The expression `"foo.bar"` on a mapping whose key `foo.bar` is the string `dot` yields `dot`. The expression `"foo bar"` on a mapping whose key `foo bar` is the string `space` yields `space`. The expression `"foo\nbar"` on a mapping whose key is a `foo`, a line feed, and `bar` yields that field. The expression `"1"` on a mapping whose `foo` holds a mapping whose key `1` is an array selects that array when written as `foo."1"`. The expression `"☯"` on `{☯: true}` yields true.
- Quoted identifiers interpret JSON string escapes, including a Unicode escape. The expression `"\tF\uCebb"` selects the field whose key is a tab, `F`, and that Unicode character. The expression `"foo\"bar"` on a mapping whose key is `foo` then a double quote then `bar` yields that field.
- Chained identifiers select nested fields. `foo.bar.baz` on `{foo: {bar: {baz: correct}}}` is the string `correct`.
- Applying a field identifier to a value that is not an object yields null. `foo.bar` on a document whose `foo` is the array of mappings `[{bar: one}, {bar: two}]` yields null — it does not project. Projecting that array is FP-04.

**Boundary / error behavior:**

- `foo.1` and `foo.-11` do not succeed (syntax). Selecting a key that looks like a number requires a quoted identifier.
- `foo-bar` does not succeed (syntax). A hyphen is not a legal character in an unquoted identifier; a hyphenated key is selected with a quoted identifier.
- `foo.`, `.foo`, `foo..bar`, and `foo.bar.` do not succeed.
- An unclosed `"` does not succeed. A quoted identifier whose interior is not a legal JSON string (an illegal escape) does not succeed.
- A missing field yields null, not a failure: `foo.bad` on `{foo: {bar: 1}}` is null; `bad.morebad.morebad` on that document is null.

**Verifiable oracle:**

- Success: `foo.bar.baz` on `{foo: {bar: {baz: correct}}}` is `correct`; the same path written with line feeds around the dots is `correct`; `__L` and `Y_1623` select those keys; `"foo.bar"` selects the dotted key; `"foo bar"` selects the spaced key; `foo."1"` selects the key `1` under `foo`; `"☯"` selects that key; `"foo\nbar"` selects the key that contains a line feed; `"foo\"bar"` selects the key with an embedded quote; `foo.bar` on `{foo: [{bar: one}]}` is null.
- Failure / absence: `foo.bar` on a list of objects returns `[one]` instead of null; `foo.1` succeeds; `foo-bar` succeeds; quoted identifiers are treated as literal quote characters in the key; `"foo.bar"` walks `foo` then `bar` instead of the single dotted key; a missing field raises; whitespace between `foo` and `.bar` is rejected.

---

### FP-03: Index, slice, and flatten arrays

**Public entry:** The search and compile entries of FP-01. This feature point is bracket selection on arrays: a single index, a slice, and the flatten operator. Wildcards and filters are FP-04.

**Normal behavior:**

- A zero-based index in square brackets selects one element. On `{foo: {bar: [zero, one, two]}}`, `foo.bar[0]` is `zero`, `foo.bar[1]` is `one`, `foo.bar[2]` is `two`.
- A negative index counts from the end: `foo.bar[-1]` is `two`, `foo.bar[-2]` is `one`, `foo.bar[-3]` is `zero`.
- An index past either end yields null: `foo.bar[3]` and `foo.bar[-4]` are null.
- Indexing a value that is not an array yields null. Indexing a string yields null. `foo[0]` on `{foo: {bar: 1}}` is null. `foo.bar[0][0][0]` on `{foo: {bar: [[one, two], [three, four]]}}` is null once the current value is the string `one`.
- On `{foo: [{bar: one}, {bar: two}, {bar: three}, {notbar: four}]}`, `foo[0].bar` is `one`, `foo[3].notbar` is `four`, and `foo[3].bar` is null. `foo.bar` on that document is null (FP-02): a field does not walk an array.
- A slice `[start:stop:step]` selects a sub-array using the host slice rules. Omitted parts are allowed. On `{foo: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]}`:
  - `foo[0:10]`, `foo[:]`, `foo[::]`, and `foo[0:10:1]` each yield the ten numbers in order.
  - `foo[1:9]` yields `[1, 2, 3, 4, 5, 6, 7, 8]`.
  - `foo[0:10:2]` yields `[0, 2, 4, 6, 8]`.
  - `foo[5:]` yields `[5, 6, 7, 8, 9]`.
  - `foo[::-1]` yields `[9, 8, 7, 6, 5, 4, 3, 2, 1, 0]`.
  - `foo[8:2:-2]` yields `[8, 6, 4]`.
  - `foo[-4:-1]` yields `[6, 7, 8]`.
  - `foo[10:-20]` yields an empty array.
- A slice on a non-array yields null: `bar[0:10]` on `{bar: {baz: 1}}` is null. `baz[:2].a` on a document whose `baz` is the number 50 is null.
- A slice is a projection: `foo[:2].a` on `{foo: [{a: 1}, {a: 2}, {a: 3}]}` yields `[1, 2]`. `foo[:2].b` yields an empty array (every element’s `b` is null and is dropped). `bar[::-1].a.b` on `{bar: [{a: {b: 1}}, {a: {b: 2}}, {a: {b: 3}}]}` yields `[3, 2, 1]`.
- A slice may be the whole expression when the document itself is an array: `[:2].a` on `[{a: 1}, {a: 2}, {a: 3}]` yields `[1, 2]`.
- The flatten operator is empty square brackets `[]`. If the current value is an array, each element that is itself an array is spliced in one level; an element that is not an array is kept as a single item. On `{foo: [[["one", "two"], ["three", "four"]], [["five", "six"], ["seven", "eight"]], [["nine"], ["ten"]]]}`, `foo[]` yields `[["one", "two"], ["three", "four"], ["five", "six"], ["seven", "eight"], ["nine"], ["ten"]]`, and `foo[][0]` yields `["one", "three", "five", "seven", "nine", "ten"]`. Flatten on a non-array yields null: `[]` on `{type: object}` is null.
- Flatten is a projection: `foo[].bar` on `{foo: [{bar: one}, {notbar: x}]}` yields `["one"]`. `foo[][0][0]` on the triple-nested document above yields an empty array (each first element is a string; indexing a string is null and is dropped).

**Boundary / error behavior:**

- A slice whose step is the number 0 does not succeed. That failure is distinguishable from a syntax failure and from a successful empty array. `foo[8:2:0]` does not succeed. `foo[10:-20]` succeeds and is `[]`.
- A slice with four colon-separated parts, such as `foo[8:2:0:1]`, does not succeed (syntax). `foo[2:a:3]` does not succeed. `foo[8:2&]` does not succeed.
- Out-of-range indices and slices do not fail: they yield null or an empty array as specified above.

**Verifiable oracle:**

- Success: `foo.bar[0]` / `[1]` / `[2]` / `[-1]` / `[-2]` / `[-3]` on `[zero, one, two]` match those strings; `[3]` and `[-4]` are null; `foo.bar` on a list of objects is null while `foo[0].bar` is `one`; `foo[1:9]` is `[1..8]`; `foo[::-1]` reverses `0..9`; `foo[8:2:-2]` is `[8, 6, 4]`; `foo[:2].a` is `[1, 2]` and `foo[:2].b` is `[]`; a slice of a non-array is null; `foo[]` one-level-flattens the triple-nested document; `foo[][0]` is the six first elements; `foo[].bar` on `{foo: [{bar: one}, {notbar: x}]}` is `["one"]`; `foo[][0][0]` on the triple-nested document is `[]`; `[]` on an object is null.
- Failure / absence: negative indices raise or wrap incorrectly; `foo.bar` on a list of objects projects; a slice of an object returns that object; flatten walks more than one nesting level in a single `[]`; `foo[8:2:0]` yields an empty array; out-of-range `[3]` raises.

---

### FP-04: Wildcard and filter projections

**Public entry:** The search and compile entries of FP-01. This feature point is the star wildcard on arrays and on objects, and the filter projection `[?...]`. Flatten and slices are FP-03. Filter predicates use the comparators and truthiness of FP-06; the collection rule is specified here.

**Normal behavior:**

- A list wildcard is `[*]`. It requires an array. On `{foo: [{bar: one}, {bar: two}, {bar: three}, {notbar: four}]}`, `foo[*].bar` yields `["one", "two", "three"]` and `foo[*].notbar` yields `["four"]`. Nulls from the right-hand side are dropped.
- When the document itself is that array, `[*]` yields the four mappings and `[*].bar` yields `["one", "two", "three"]`.
- `foo[*].bar[*].kind` on an array of mappings whose `bar` is an array of mappings with `kind` collects a nested array per left-hand element: `[["basic", "intermediate"], ["advanced", "expert"]]` for two matching parents. A parent whose `bar` is the string `string` contributes nothing to that projection (the inner wildcard on a string is null and is dropped).
- `foo[*][0]` on `{foo: [[one, two], [three, four], [five]]}` yields `["one", "three", "five"]`. `foo[*][1]` yields `["two", "four"]`. `foo[*][2]` yields an empty array.
- A list wildcard on a missing or non-array value yields null: `bar[*]` on a document that has no `bar` is null.
- An object wildcard is a star in a field position: `*` or `foo.*`. It requires an object and projects over that object’s **values**. On `{foo: {bar: {baz: val}, other: {baz: val}, other2: {baz: val}, other3: {notbaz: [a, b, c]}, other4: {notbaz: [a, b, c]}}}`, `foo.*.baz` yields `["val", "val", "val"]` and `foo.*.notbaz` yields `[[a, b, c], [a, b, c]]`. `foo.*.notbaz[0]` yields `["a", "a"]`.
- `*.bar` on `{foo: {bar: one}, other: {bar: one}, nomatch: {notbar: three}}` yields `["one", "one"]`.
- `*` on `{top1: {sub1: {foo: one}}, top2: {sub1: {foo: one}}}` yields the two `top` mappings. `*.*.foo[]` flattens the projected arrays and yields `["one", "one"]`.
- Object wildcard on a non-object yields null.
- A filter is `[?predicate]`. The left-hand value must be an array; otherwise the result is null. For each element, the predicate is evaluated with that element as the current value. Elements whose predicate is a true value are kept; others are omitted. A following selector is a projection over the kept elements.
- A filter predicate may be a field’s truthiness, without a comparator. On `{foo: [{age: 0}, {age: null}]}`, `foo[?age]` yields `[{age: 0}]`: the number 0 is a true value and null is a false value.
- On `{foo: [{name: a}, {name: b}]}`, `foo[?name == 'a']` yields `[{name: a}]`. Comparators and and/or/not inside a filter are the operators of FP-06.
- On `{foo: [{first: foo, last: bar}, {first: foo, last: foo}, {first: foo, last: baz}]}`, `foo[?first == last]` yields the one mapping whose first and last are both `foo`, and `foo[?first == last].first` yields `["foo"]`.
- On `{foo: [{age: 20}, {age: 25}, {age: 30}]}`, `foo[?age > \`25\`]` yields `[{age: 30}]`, `foo[?age >= \`25\`]` yields the 25 and 30 mappings, `foo[?age < \`25\`]` yields `[{age: 20}]`, `foo[?age == \`20\`]` yields `[{age: 20}]`, and `foo[?age != \`20\`]` yields the 25 and 30 mappings. `foo[?age > \`30\`]` yields an empty array.
- A filter predicate may use a subexpression: `foo[?top.name == 'a']` on `{foo: [{top: {name: a}}, {top: {name: b}}]}` yields the first mapping.
- A filter predicate may compare against a JSON literal object: `foo[?top == \`{"first": "foo", "last": "bar"}\`]` keeps the matching mapping.
- Equality in a filter does not treat the number 0 as false or the number 1 as true: on an array of mappings whose `key` values are true, false, 0, 1, `[0]`, `{bar: [0]}`, null, `[1]`, and `{a: 2}`, `foo[?key == \`true\`]` keeps only `{key: true}`, `foo[?key == \`false\`]` keeps only `{key: false}`, `foo[?key == \`0\`]` keeps only `{key: 0}`, and `foo[?key == \`1\`]` keeps only `{key: 1}`.
- A comparison or and/or after a list wildcard compares or combines the whole projected array, not each element. On `{foo: [{bar: one}, {bar: two}, {bar: three}, {notbar: four}]}`, `foo[*].bar == \`["one", "two", "three"]\`` is true, and `foo[*].bar == 'one'` is false.

**Boundary / error behavior:**

- `foo[*]bar` and `foo[*]*` do not succeed (syntax). A wildcard that continues must use a dot, a bracket, or another grammatical continuation.
- `.*` and `*foo` and `*0` do not succeed.
- A filter on a non-array yields null, not an empty array and not a failure. A filter whose predicate is ill-formed does not succeed.
- Projected nulls are dropped. An implementation that stores nulls in `foo[*].bar` when some elements lack `bar` is wrong.

**Verifiable oracle:**

- Success: `foo[*].bar` is `["one", "two", "three"]` and `foo[*].notbar` is `["four"]`; `foo[*][0]` on nested arrays is `["one", "three", "five"]`; `bar[*]` on a missing field is null; `foo.*.baz` is three `val` strings; `*.bar` skips the mapping that has no `bar`; `foo[?age]` on `[{age: 0}, {age: null}]` is `[{age: 0}]`; `foo[?name == 'a']` is the one matching mapping; `foo[?age >= \`25\`]` is the two older mappings; `foo[?first == last].first` is `["foo"]`; `foo[?key == \`true\`]` does not also keep `{key: 1}`; `foo[*].bar` omits elements without `bar`; `foo[*].bar == \`["one", "two", "three"]\`` is true and `foo[*].bar == 'one'` is false.
- Failure / absence: `foo[*].bar` includes nulls; object wildcard returns keys instead of values; `*.bar` includes `three`; a filter on an object walks its values; `foo[?age]` drops `{age: 0}`; `foo[?key == \`true\`]` also keeps `1`; `foo[*].bar == 'one'` is true or yields `[false, false, false]`; `foo[*]bar` succeeds; a missing-array wildcard yields `[]` instead of null.

---

### FP-05: Construct results, pipe, current value, and literals

**Public entry:** The search and compile entries of FP-01. This feature point is multiselect lists and hashes, the pipe operator, the current-value token, JSON literals, raw string literals, and expression references. Functions that consume expression references are FP-07.

**Normal behavior:**

- A multiselect hash is curly braces of `key: expression` pairs. On `{foo: {bar: bar, baz: baz, qux: qux}}`, `foo.{bar: bar}` yields `{bar: bar}`, and `foo.{bar: bar, baz: baz}` yields `{bar: bar, baz: baz}`. A missing right-hand field becomes null inside the new object: `foo.{bar: bar, noexist: noexist}` yields `{bar: bar, noexist: null}`. A multiselect hash whose left-hand current value is null yields null: `foo.badkey.{nokey: nokey}` is null, not `{nokey: null}`.
- Hash keys may be unquoted or quoted identifiers. `foo.{"foo.bar": bar}` yields a mapping whose key is the string `foo.bar`. `{"baz": baz, "qux\"": "qux\""}` on `{baz: 2, qux": 3}` yields those two keys.
- A multiselect hash after an object wildcard builds one mapping per value: `foo.nested.*.{a: a, b: b}` yields three mappings each with `a` and `b`.
- A multiselect list is square brackets of comma-separated expressions, written after a dot or as a top-level constructor. `foo.[includeme, bar.baz[*].common]` on a document whose `foo.includeme` is true and whose `foo.bar.baz` is an array of mappings with `common` `first` then `second` yields `[true, ["first", "second"]]`. A multiselect list on a null current value yields null.
- Pipe `|` evaluates the left-hand expression, then evaluates the right-hand expression with that result as the current value. On `{foo: {bar: {baz: one}, other: {baz: two}}}`, `foo | bar` yields `{baz: one}` and `foo | bar | baz` yields `one`. Spaces around `|` are optional: `foo|bar| baz` is the same. `foo.*.baz | [0]` on three `baz` values of `subkey` yields `subkey`.
- Pipe stops a projection: the right-hand side sees the whole left-hand array, not one element. `foo.*.baz | [0]` indexes the projected array.
- The current-value token `@` is the value being searched. On `{foo: [{name: a}, {name: b}], bar: {baz: qux}}`, `@` yields that whole mapping, `@.bar` yields `{baz: qux}`, and `@.foo[0]` yields `{name: a}`.
- A JSON literal is a JSON value written between backticks. The literal is the result, regardless of the document. `` `"foo"` `` yields the string `foo`. `` `[1, 2, 3]` `` yields that array. `` `{"a": "b"}` `` yields that object. `` `true` ``, `` `false` ``, and `` `null` `` yield those values. `` `0` `` through `` `9` `` yield those integers. A literal may be used as the start of a subexpression: `` `{"a": "b"}`.a `` yields `b`; `` `[0, 1, 2]`[1] `` yields `1`. Leading or trailing whitespace inside the backticks is allowed: `` `  {"foo": true}` `` yields `{foo: true}`.
- A backtick literal interprets JSON Unicode escapes: `` `"\u03a6"` `` yields the character Φ. A backtick inside a literal is escaped with a backslash.
- A raw string literal is text between single quotes. No JSON escapes are processed. `'foo'` yields `foo`. `'  foo  '` keeps the spaces. `'0'` is the string `0`, not the number 0. `'\u03a6'` is the six characters backslash, u, 0, 3, a, 6. A single quote inside a raw string is escaped as backslash then quote: `'foo\'bar'` yields `foo'bar`. A backslash not followed by a quote is kept: `'\z'` is backslash then `z`; `'\\'` is two backslashes.
- An expression reference is an ampersand followed by an expression. It does not evaluate immediately. It is a value of type expression reference, used as an argument to `map`, `sort_by`, `min_by`, and `max_by` (FP-07). Passing a non-reference where those functions require a reference is an invalid type (FP-07).

**Boundary / error behavior:**

- `` `foo"bar` `` does not succeed. An unclosed backtick does not succeed. An unclosed raw string does not succeed.
- A literal in a position the grammar does not allow does not succeed. `foo.\`"bar"\`` does not succeed (a literal is not a legal right-hand identifier after a dot).
- A multiselect list or hash that is missing a closing bracket or brace, or that has a trailing comma the grammar does not accept, does not succeed.
- A pipe with a missing side (`foo |` or `| foo`) does not succeed.

**Verifiable oracle:**

- Success: `foo.{bar: bar, baz: baz}` is the two-key mapping; `foo.{bar: bar, noexist: noexist}` stores null for `noexist`; `foo.badkey.{nokey: nokey}` is null; `foo.[includeme, bar.baz[*].common]` is `[true, ["first", "second"]]`; `foo | bar | baz` is `one`; `foo.*.baz | [0]` is `subkey`; `@` is the document; `` `{"a": "b"}`.a `` is `b`; `` `[1, 2, 3]` `` is that array; `'foo'` is `foo`; `'\u03a6'` is the escape text, not Φ; `'foo\'bar'` is `foo'bar`; `` `"\u03a6"` `` is Φ.
- Failure / absence: a missing multiselect field omits the key instead of storing null; a multiselect on null yields an empty object; pipe projects element-wise so `foo.*.baz | [0]` indexes each string; `@` is rejected; raw strings interpret Unicode escapes; `` `{"a": "b"}`.a `` is rejected; `foo.\`"bar"\`` succeeds.

---

### FP-06: Compare values and combine them with logic

**Public entry:** The search and compile entries of FP-01. This feature point is `==`, `!=`, `<`, `<=`, `>`, `>=`, `&&`, `||`, `!`, and parentheses. Filters in FP-04 use these operators. Truthiness is the false-value set in Terminology.

**Normal behavior:**

- `==` is true when the two sides are the same JSON value; `!=` is the negation. The number 0 is not equal to false. The number 1 is not equal to true. On `{one: 1, two: 2}`, `one == one` is true and `one == two` is false and `one != two` is true.
- Ordering operators `<`, `<=`, `>`, `>=` compare two numbers or two strings. `one < two` is true, `one <= two` is true, `one > two` is false, `one >= two` is false when `one` is 1 and `two` is 2. Two strings compare in the host’s Unicode ordering: on `{a: 2016, b: 2017}` as strings, `a < b` is true. A host decimal participates as a number: `[?a >= \`1\`].a` on `[{a: <host decimal 3>}]` yields an array holding that same decimal.
- An ordering comparison whose sides are not both numbers and not both strings yields null, not false, when at least one side is an array, an object, a boolean, or null. On `{one: 1, emptylist: [], boolvalue: false}`, `emptylist < one` is null, `emptylist < boolvalue` is null, and `one < boolvalue` is null.
- `||` returns the first side if that side is a true value; otherwise it returns the second side. On `{outer: {foo: foo, bar: bar, baz: baz}}`, `outer.foo || outer.bar` is `foo`, `outer.bad || outer.foo` is `foo`, and `outer.bad || outer.alsobad` is null. Spaces around `||` are optional.
- `||` treats false values as not taken: on `{outer: {foo: foo, bool: false, empty_list: [], empty_string: ""}}`, `outer.empty_string || outer.foo` is `foo`, and `outer.nokey || outer.bool || outer.empty_list || outer.empty_string || outer.foo` is `foo`.
- The number 0 and the number 0.0 are true values. On `{Zero: 0, ZeroFloat: 0.0, Number: 5}`, `Zero || Number` is 0 and `ZeroFloat || Number` is 0.0. `!Zero` is false. `!!Zero` is true.
- `&&` returns the first side if that side is a false value; otherwise it returns the second side. On `{True: true, False: false, Number: 5, EmptyList: []}`, `True && False` is false, `True && True` is true, `True && Number` is 5, `Number && True` is true, `Number && EmptyList` is `[]`, and `EmptyList && True` is `[]`.
- `!` inverts truthiness: `!True` is false, `!False` is true, `!Number` is false when Number is 5, `!EmptyList` is true.
- Parentheses group. `&&` binds tighter than `||`. On `{Number: 5}`, `Number || True && False` is 5, `(Number || True) && False` is false, and `Number || (True && False)` is 5. `!(True && False)` is true.
- `one < two && three > one` is true when the three fields are 1, 2, and 3. `two < one || three < one` is false.
- The same operators apply inside a filter (FP-04). On `{foo: [{a: 1, b: 2}, {a: 1, b: 3}]}`, `foo[?a == \`1\` && b == \`2\`]` yields `[{a: 1, b: 2}]`. On `{foo: [{name: a}, {name: b}]}`, `foo[?name == 'a' || name == 'b']` yields both mappings. On `{foo: [{a: 1, b: 2, c: 3}, {a: 3, b: 4}]}`, `foo[?a == \`1\` || b == \`2\` && c == \`5\`]` yields the first mapping (`&&` binds tighter than `||`), and `foo[?(a == \`1\` || b == \`2\`) && c == \`5\`]` yields an empty array. `foo[?!(a == \`1\` || b == \`2\`)]` yields `[{a: 3, b: 4}]`.

**Boundary / error behavior:**

- A lone `=` does not succeed. Equality is the two-character token `==`.
- A lone `&` that is not `&&` and not an expression reference, or a dangling `||`, does not succeed.
- Ordering of a number and a boolean, of an array and a number, or of null and anything, is null, not a failure and not a boolean.

**Verifiable oracle:**

- Success: `one == one` is true; `one != two` is true; `1 == true` is false; `0 == false` is false; `one < two` is true; `'2016' < '2017'` (as field values) is true; a host decimal 3 compared with `>= \`1\`` is kept; `emptylist < one` is null; `outer.foo || outer.bar` is `foo`; `outer.empty_string || outer.foo` is `foo`; `Zero || Number` is 0; `!Zero` is false; `True && Number` is 5; `EmptyList && True` is `[]`; `Number || True && False` is 5; `(Number || True) && False` is false; `foo[?a == \`1\` && b == \`2\`]` is the one matching mapping; `foo[?a == \`1\` || b == \`2\` && c == \`5\`]` is the first mapping and the parenthesized form with `c == \`5\`` is empty.
- Failure / absence: `0 == false` is true; `Zero || Number` is 5; `!Zero` is true; `emptylist < one` is false; `&&` and `||` always return booleans instead of operands; `Number || True && False` is false; string ordering is rejected; a host decimal is refused as not a number; `foo[?a == \`1\` && b == \`2\`]` keeps both mappings; `&&` inside a filter binds looser than `||`.

---

### FP-07: Call built-in functions

**Public entry:** The search and compile entries of FP-01. A function call is an unquoted identifier followed by a parenthesized argument list. Arguments are expressions evaluated against the current value. Expression references from FP-05 are required by `map`, `sort_by`, `min_by`, and `max_by`. Custom functions are FP-08. This feature point is the finite built-in set and the three function-call failure kinds.

The built-in function names are exactly: `abs`, `avg`, `ceil`, `contains`, `ends_with`, `floor`, `join`, `keys`, `length`, `map`, `max`, `max_by`, `merge`, `min`, `min_by`, `not_null`, `reverse`, `sort`, `sort_by`, `starts_with`, `sum`, `to_array`, `to_number`, `to_string`, `type`, `values`.

Unless noted, a wrong argument count is an **invalid-arity** failure and a wrong argument type is an **invalid-type** failure. Both are kinds of value error; they do not return a search result. They are distinguishable from each other and from an **unknown-function** failure. A successful function that has nothing to compute returns null or an empty collection as specified below — that is not a failure.

**Normal behavior:**

The following hold on a document that has `foo` equal to `-1`, `zero` equal to `0`, `numbers` equal to `[-1, 3, 4, 5]`, `array` equal to `[-1, 3, 4, 5, "a", "100"]`, `strings` equal to `["a", "b", "c"]`, `decimals` equal to `[1.01, 1.2, -1.5]`, `str` equal to `Str`, `false` equal to false, `empty_list` equal to `[]`, `empty_hash` equal to `{}`, `objects` equal to `{foo: bar, bar: baz}`, and `null_key` equal to null — except where a case names another document.

- `abs` takes one number and returns its absolute value. `abs(foo)` is 1. `abs(\`-24\`)` is 24.
- `avg` takes one array of numbers and returns their arithmetic mean. `avg(numbers)` is 2.75. `avg(empty_list)` is null.
- `ceil` takes one number and returns the smallest integer that is not less than it. `ceil(\`1.2\`)` is 2. `ceil` of `-1.5` is `-1`.
- `floor` takes one number and returns the largest integer that is not greater than it. `floor(\`1.2\`)` is 1. `floor(foo)` is `-1`.
- `contains` takes a string or array, then any value, and returns whether the second is in the first. `contains('abc', 'a')` is true. `contains('abc', 'd')` is false. `contains(strings, 'a')` is true. `contains(decimals, \`1.2\`)` is true. `contains(decimals, \`false\`)` is false.
- `ends_with` takes two strings and returns whether the first ends with the second. `ends_with(str, 'r')` is true. `ends_with(str, 'SStr')` is false.
- `starts_with` takes two strings and returns whether the first starts with the second. `starts_with(str, 'S')` is true. `starts_with(str, 'String')` is false.
- `length` takes a string, an array, or an object and returns how many characters, elements, or keys it has. `length('abc')` is 3. `length('✓foo')` is 4. `length('')` is 0. `length(array)` is 6. `length(objects)` is 2. `length` of the twelve-key document above as `@` is 12.
- `reverse` takes an array or a string. `reverse(numbers)` is `[5, 4, 3, -1]`. `reverse('hello world')` is `dlrow olleh`. `reverse(\`[]\`)` is `[]`. `reverse('')` is `''`.
- `join` takes a string separator and an array of strings and concatenates the elements. `join(', ', strings)` is `a, b, c`. `join(',', \`["a", "b"]\`)` is `a,b`. `join('|', empty_list)` is the empty string. `join('|', decimals[].to_string(@))` is `1.01|1.2|-1.5`.
- `keys` takes an object and returns an array of its keys. `keys(empty_hash)` is `[]`. `sort(keys(objects))` is `["bar", "foo"]`.
- `values` takes an object and returns an array of its values. `sort(values(objects))` is `["bar", "baz"]`.
- `type` takes one value and returns one of the strings `string`, `number`, `boolean`, `array`, `object`, `null`. `type('abc')` is `string`. `type(\`1.0\`)` and `type(\`2\`)` are `number`. `type(\`true\`)` and `type(\`false\`)` are `boolean`. `type(\`null\`)` is `null`. `type(\`[0]\`)` is `array`. `type(\`{"a": "b"}\`)` is `object`.
- `to_array` takes one value. If it is already an array, that array is returned; otherwise a one-element array holding the value is returned. `to_array('foo')` is `["foo"]`. `to_array(\`[1, 2, 3]\`)` is `[1, 2, 3]`. `to_array(false)` is `[false]`.
- `to_string` takes one value. A string is returned unchanged. Any other JSON value is returned as compact JSON text with no extra spaces: `to_string(\`1.2\`)` is `1.2`; `to_string(\`[0, 1]\`)` is `[0,1]`. A host value that is not a JSON type is converted with the host’s ordinary text conversion, then that text is returned as compact JSON string encoding (quoted).
- `to_number` takes one value. A number is returned unchanged. A string is parsed as an integer if the whole string is an integer, otherwise as a floating-point number, including scientific notation: `to_number('4')` is the integer 4; `to_number('1.1')` is 1.1; `to_number('1e21')` is `1e21`. A boolean, null, array, object, or a string that is not a number yields null: `to_number('notanumber')`, `to_number(\`false\`)`, `to_number(\`null\`)`, `to_number(\`[0]\`)`, and `to_number(\`{"foo": 0}\`)` are null.
- `max` takes an array of only numbers or only strings and returns the greatest element. `max(numbers)` is 5. `max(decimals)` is 1.2. `max(strings)` is `c`. `max(empty_list)` is null.
- `min` takes an array of only numbers or only strings and returns the least element. `min(numbers)` is `-1`. `min(strings)` is `a`. `min(empty_list)` is null.
- `sort` takes an array of only numbers or only strings and returns a new array in ascending order. `sort(numbers)` is `[-1, 3, 4, 5]`. `sort(strings)` is `["a", "b", "c"]`. `sort(decimals)` is `[-1.5, 1.01, 1.2]`. `sort(empty_list)` is `[]`.
- `sum` takes an array of numbers and returns their sum. `sum(numbers)` is 11. `sum(\`[]\`)` is 0. `sum(array[].to_number(@))` is 111.
- `merge` takes one or more objects and returns a new object, applying each argument in order so a later key overwrites an earlier one. `merge(\`{"a": 1}\`, \`{"b": 2}\`)` is `{a: 1, b: 2}`. `merge(\`{"a": 1}\`, \`{"a": 2}\`)` is `{a: 2}`. `merge(\`{}\`)` is `{}`.
- `not_null` takes one or more arguments and returns the first that is not null. `not_null(unknown_key, str)` is `Str`. `not_null(unknown_key, foo.bar, empty_list, str)` is `[]` (the empty list is not null). `not_null(all, expressions, are_null)` is null.
- `map` takes an expression reference and an array, applies the referenced expression to each element, and returns the array of results, **including** nulls. On `{people: [{a: 10, b: 1, c: z}, {a: 10, b: 2, c: null}, {a: 10, b: 3}, {a: 10, b: 4, c: z}, {a: 10, b: 5, c: null}, {a: 10, b: 6}, {a: 10, b: 7, c: z}, {a: 10, b: 8, c: null}, {a: 10, b: 9}]}`, `map(&a, people)` is nine tens, and `map(&c, people)` is `["z", null, null, "z", null, null, "z", null, null]`. `map(&foo, empty)` on `{empty: []}` is `[]`. `map(&foo.bar, array)` on three mappings, two of which have `foo.bar` and one of which does not, is `["yes1", "yes2", null]`. `map(&[], array)` on `[[1, 2, 3, [4]], [5, 6, 7, [8, 9]]]` is `[[1, 2, 3, 4], [5, 6, 7, 8, 9]]`.
- `sort_by` takes an array and an expression reference. It returns a new array ordered by the referenced expression, which must resolve to a number or a string, and the same kind for every element. The sort is stable: on eleven mappings that all have `age` 10 and `order` `"1"` through `"11"`, `sort_by(people, &age)` keeps that input order. On people with ages 20, 40, 30, 50, 10, `sort_by(people, &age)` orders them 10, 20, 30, 40, 50, and `sort_by(people, &age)[].name` is `[3, a, c, b, d]` for the names in that document. `sort_by(\`[]\`, &age)` is `[]`.
- `max_by` takes an array and an expression reference and returns the element whose referenced value is greatest. On those people, `max_by(people, &age)` is the mapping whose age is 50. `max_by(\`[]\`, &age)` is null.
- `min_by` takes an array and an expression reference and returns the element whose referenced value is least. `min_by(people, &age)` is the mapping whose age is 10. `min_by(\`[]\`, &age)` is null.
- A projection may feed a function: `numbers[].to_string(@)` is `["-1", "3", "4", "5"]`. `array[].to_number(@)` is `[-1, 3, 4, 5, 100]` (the string `a` becomes null and is dropped by the projection; the string `100` becomes the number 100).

**Boundary / error behavior:**

- A name that is not in the built-in set (and not supplied as a custom function in FP-08) is an unknown-function failure. `unknown_function(\`1\`, \`2\`)` does not succeed.
- Wrong arity: `abs(\`1\`, \`2\`)` and `abs()` do not succeed. `length(@, @)` does not succeed. `not_null()` does not succeed (at least one argument is required). `sort_by(people)` does not succeed.
- Wrong type: `abs(str)` and `abs(\`false\`)` do not succeed. `avg(array)` (mixed types), `avg('abc')`, and `avg(foo)` do not succeed. `length(\`false\`)` and `length(foo)` do not succeed. `join(',', \`["a", 0]\`)` does not succeed. `join(\`2\`, strings)` does not succeed. `max(array)` and `sort(array)` (mixed types) do not succeed. `keys(foo)` when `foo` is a number does not succeed. `map(&a, badkey)` when `badkey` is missing (null) does not succeed. `sort_by(people, name)` (a string, not an expression reference) does not succeed. `sort_by(people, &bool)` and `sort_by(people, &extra)` (a boolean, or a key missing on some elements so types mix) do not succeed. `max_by(people, &bool)` and `min_by(people, &extra)` do not succeed.
- A quoted identifier is not a legal function name: `"to_string"(\`1.0\`)` does not succeed (syntax), even though `to_string` is a built-in.
- `starts_with(str, \`0\`)` and `ends_with(str, \`0\`)` do not succeed (the second argument must be a string).
- These failures are distinguishable: unknown-function versus invalid-arity versus invalid-type versus a successful null (`avg(empty_list)`, `max(empty_list)`, `to_number('notanumber')`).

**Verifiable oracle:**

- Success: `abs(foo)` is 1; `avg(numbers)` is 2.75; `avg(empty_list)` is null; `ceil(\`1.2\`)` is 2; `contains('abc', 'a')` is true; `length('✓foo')` is 4; `length(objects)` is 2; `join(', ', strings)` is `a, b, c`; `type(\`true\`)` is `boolean`; `to_array('foo')` is `["foo"]`; `to_string(\`[0, 1]\`)` is `[0,1]`; `to_number('1e21')` is `1e21`; `to_number('notanumber')` is null; `max(numbers)` is 5; `min(empty_list)` is null; `sort(decimals)` is `[-1.5, 1.01, 1.2]`; `sum(\`[]\`)` is 0; `merge` of `{a: 1}` then `{a: 2}` is `{a: 2}`; `not_null(unknown_key, str)` is `Str`; `map(&c, people)` keeps nulls; `sort_by(people, &age)` is stable and orders by age; `max_by(people, &age)` is the age-50 mapping; `min_by(\`[]\`, &age)` is null; `array[].to_number(@)` is `[-1, 3, 4, 5, 100]`.
- Failure / absence: `unknown_function(\`1\`, \`2\`)` returns null; `abs()` returns 0; `avg(empty_list)` fails; `length('✓foo')` is 6 or 3; `to_string(\`[0, 1]\`)` includes spaces; `to_number('1e21')` is null; `map` drops nulls; `sort_by` is unstable so eleven equal keys permute; `sort_by(people, name)` succeeds; `"to_string"(\`1.0\`)` succeeds; `0 == false` inside a function argument is treated as true; invalid-type and invalid-arity cannot be told apart from unknown-function.

---

### FP-08: Evaluation options for constructed objects and custom functions

**Public entry:** The search entry and the parsed-expression search of FP-01, when the caller supplies evaluation options. Without options, constructed objects use the host’s ordinary mapping type and only the built-in functions of FP-07 are available. **This feature point refines FP-01 and FP-07:** the no-options path is unchanged; options add a mapping type and an extra function set.

**Normal behavior:**

- The caller may supply a mapping type. Every **multiselect hash** the evaluation constructs is built with that type. Built-in functions that return a new object, including `merge`, still return the host’s ordinary mapping; they do not use the caller-supplied type. On a document `{c: c, b: b, a: a, d: d}`, searching `{a: a, b: b, c: c}.*` with an order-preserving mapping type yields `["a", "b", "c"]` — the values in **key-declaration order**, not the document’s key order. The same expression searched through a parsed expression that is then given those options yields the same array.
- The caller may supply a custom function provider together with the options. A custom function is a named language function with declared argument types. After attaching a provider that defines `custom_add` of two numbers and `my_subtract` of two numbers, `custom_add(\`1\`, \`2\`)` yields 3 and `my_subtract(\`10\`, \`3\`)` yields 7.
- A provider that extends the built-in set still implements every FP-07 function. `length(\`[1, 2]\`)` on a search that uses that provider yields 2.
- A custom function on one options object does not change a later search that does not attach that provider. After evaluating `custom_add` with options, a search of `length(\`[1, 2]\`)` **without** options still yields 2, and `custom_add(\`1\`, \`2\`)` without options is an unknown-function failure.
- Custom argument types are enforced the same way as built-ins. A custom function declared to accept a string, an array, an object, or null may return 0 for null and the host length otherwise: on `{a: {b: [1, 2, 3]}}`, that function applied to `a.b` yields 3 and applied to `a.c` (null) yields 0.

**Boundary / error behavior:**

- A custom name that is not on the attached provider and not built-in is an unknown-function failure.
- A custom function given the wrong number of arguments is an invalid-arity failure. A custom function given a value outside its declared types is an invalid-type failure.
- Options that do not include a custom provider do not make `custom_add` exist. Options that do not include a mapping type do not promise declaration-order keys on a mapping type that does not preserve insertion order.

**Verifiable oracle:**

- Success: `{a: a, b: b, c: c}.*` with an order-preserving mapping type on `{c: c, b: b, a: a, d: d}` is `["a", "b", "c"]`; that result is the same through compile-then-search with the same options; `custom_add(\`1\`, \`2\`)` with a provider that adds two numbers is 3; `my_subtract(\`10\`, \`3\`)` is 7; `length(\`[1, 2]\`)` still works on that provider and on a later no-options search; a custom length that maps null to 0 yields 0 for a missing field and 3 for `[1, 2, 3]`.
- Failure / absence: an order-preserving mapping type is ignored so the projected values follow document key order (`c`, `b`, `a`); custom functions are visible on a later search that did not attach them; attaching a custom provider removes `length`; `custom_add` without options succeeds; a custom function ignores its declared types.
