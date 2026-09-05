# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**LINGORA** — the **Lingora Language Toolkit** — is a suite of open source Python modules, data sets, and tutorials for research and development in Natural Language Processing. It is a **library**. An integrator imports it and calls its published processing entries; it is not a single end-user application. A command-line convenience can tokenize a text stream with the same recommended word tokenizer the library exposes; that convenience is the same capability, not a second product.

The product advertises access to packaged corpora and lexical resources such as WordNet, together with text processing libraries for classification, tokenization, stemming, tagging, parsing, and semantic reasoning. The core processing path a first-time integrator actually runs is: split text into tokens, reduce words to stems, assign part-of-speech tags, group tagged tokens into shallow chunks, parse a sentence against a caller-supplied grammar and work with constituent trees, train a text classifier, and score outputs with the built-in evaluation metrics.

A common first use is the English sentence `At eight o'clock on Thursday morning Arthur didn't feel very good.`: obtain a list of word and punctuation tokens, then assign each token a part-of-speech tag. Leaving that sentence as one undifferentiated string is a failure of the tokenization path.

Exact published symbol names, import paths, and call signatures belong with those symbols, not here.

### Shape of the public surface

The product is an **importable Python library** with a flat package layout at the repository root, plus a command-line group. It is not a network service and not a wire protocol. There is no compiled extension, native code, or accelerator requirement. Python 3.10 or newer is sufficient. Documented execution is Linux.

**Distribution and import.** The installable distribution name and the importable top-level package are both `lingora`. Integrators write `import `lingora`` or `from `lingora` import …` and `from `lingora.tokenize` import …` / `from `lingora.cli` import …`. Importing the package does not download corpora or models.

**Library.** Tokenizers, stemmers, taggers, chunkers, parsers, classifiers, and metrics are Python callables and classes. A tokenizer applied to a string returns an ordered list of Unicode token strings. An empty string yields an empty list; that empty list is a successful result, never a stand-in for “the call could not be performed”. When a path requires a packaged model and that model is absent, the call does not succeed; the failure is distinguishable from a successful empty list.

**Command-line group.** The public group object is `cli`, imported as `from `lingora.cli` import `cli``. Invoking it as a program uses the public `main` entry with an argument-token list and a standalone-mode flag. The `tokenize` subcommand applies the recommended word tokenizer to each line of a text stream, including the sentence-splitting step, and writes the tokens joined by a delimiter (space by default). Because that path splits sentences first, it requires the Punkt models for the requested language.

**Packaged resources.** Sentence models, tagger models, and corpora live outside the source tree. They are located through the data finder imported as `from `lingora` import `data``. The finder searches a mutable directory list `path`. The process environment variable `LINGORA_DATA` contributes search directories. The English sentence-boundary model is the directory resource `tokenizers/punkt_tab/english/`. Word/punctuation tokenization, Penn Treebank word tokenization, recommended word tokenization of one already-delimited line (no sentence splitting), whitespace and blank-line tokenization, a caller-configured regular-expression tokenizer, and the tweet tokenizer do not require a downloaded model.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Naming conventions

**Product and package.** The product identity is LINGORA. The distribution and the import package are spelled `lingora`.

**Submodules.** Tokenizers live under `lingora.tokenize`. The command-line group lives under `lingora.cli`. The data finder is imported as `from `lingora` import `data``.

**Tokenizer classes versus functions.** Class names are CamelCase (`RegexpTokenizer`, `TreebankWordTokenizer`, `TweetTokenizer`, `WhitespaceTokenizer`, `WordPunctTokenizer`). Module-level functions are snake_case (`word_tokenize`, `wordpunct_tokenize`, `sent_tokenize`, `blankline_tokenize`). Instance methods that produce tokens are `tokenize`; methods that produce character-offset pairs are `span_tokenize`.

**Command-line tokens.** The program entry is `main`. The tokenize subcommand token is `tokenize`. Keyword names on `main` include `args` and `standalone_mode`.

**Recommended versus family names.** `word_tokenize` is the recommended word tokenizer (an improved Penn Treebank tokenizer). `sent_tokenize` is the recommended sentence tokenizer. `wordpunct_tokenize` / `WordPunctTokenizer` is the word/punctuation tokenizer. `TreebankWordTokenizer` is the Penn Treebank word tokenizer. These two families are distinguishable on a decimal currency amount: word/punctuation splits the decimal; Penn Treebank / recommended keep it as one token.

**Language default.** When a language name is omitted on the recommended sentence or word tokenizer, the language is `english`, and the corresponding Punkt resource is `tokenizers/punkt_tab/english/`.

### Global observables an implementer must reproduce

**Resource search list.** `data.path` is a mutable list of directory strings. Rewriting it in place changes where packaged models are found. An empty list means no packaged models are available. `clear_cache` on `data` drops in-process cached resources so a later lookup honors the current list. `find` on `data` locates a named resource under that list. For the English sentence model the resource name is `tokenizers/punkt_tab/english/`, and the located value is a filesystem directory (either via a `path` attribute or by converting the return to a filesystem path). For the averaged perceptron tagger resources `taggers/averaged_perceptron_tagger_eng/` and `taggers/averaged_perceptron_tagger_rus/`, a successful locator exposes a `path` attribute that is a non-empty filesystem directory; converting the return to a filesystem path is not sufficient for those tagger resources.

**Environment.** Isolated runs point `LINGORA_DATA` at a workspace resource directory so a host-installed model cannot satisfy an absent-resource condition, and cannot hide a present-resource condition that never provisioned one. The sealed suite binds that isolation through the host-interpreter surfaces `os`, `os.environ`, `os.pathsep`, and `sys`: process environment mapping, path-separator join/split of `PYTHONPATH`, and interpreter path/stream/argv. Those four names are host-interpreter surfaces, not product modules to implement. Changing the process environment after import does not by itself rewrite a search list already populated at import; the mutable `path` list is the in-process control.

**Unicode.** Input and output are Unicode text. Accented letters in the tweet tokenizer remain intact as single tokens.

**Library success versus refusal.** A successful tokenizer call returns a list of strings (possibly empty). A missing-model sentence-splitting call does not return a token list; it fails in a way that is distinguishable from a successful empty list. Exception class names and message wording are not pinned.

**Command-line process status (standalone mode).** A successful `tokenize` run exits with status 0 and writes one output line per nonempty input line. When the Punkt models for the requested language are missing, the process status is not 0 and the successful space-joined token line is not written. The exact nonzero status, stderr wording, and exception type are not pinned. Empty or garbage output with status 0 is not a missing-model refusal.

**Library substrate.** When the `lingora` package is not importable, a word/punctuation tokenization of `Hello, world!` does not produce the four-token list Hello / comma / world / exclamation mark. When the package is importable, that same tokenization succeeds and yields those four tokens. The suite establishes that importability through the same host-interpreter surfaces `os`, `os.environ`, `os.pathsep`, and `sys` (environment mapping, path-separator join/split, interpreter path/stream/argv, including dropping the product tree from `sys.path` for the negative control). Those names are not product APIs.

**No product config file.** Packaged models are data directories located by the finder. The library does not parse a configuration-file syntax of its own.

**Threading.** Not a graded concern. The library is used in-process.

## `lingora`

The installable distribution and the importable top-level package are both `lingora`. Integrators write `import `lingora`` or `from `lingora` import …`. The package uses a flat layout: one importable package directory named `lingora` at the repository root.

These names are importable from the package root:

- `data` — the packaged-resource finder (`from `lingora` import `data``)
- the submodules `lingora.tokenize` and `lingora.cli` (`from `lingora.tokenize` import …`, `from `lingora.cli` import `cli``)

When the package is not importable, `from `lingora.tokenize` import `wordpunct_tokenize`` does not run and does not print a successful token list. When the package is importable, that import succeeds.

### `data`

The finder object imported as `from `lingora` import `data`` exposes:

- `path` — a mutable `list` of directory strings searched for packaged resources. Slice assignment (``path`[:] = …`) and in-place rewrite are honored. An empty list means no packaged models are visible. A one-element list whose only entry is a workspace data directory makes resources copied under that directory visible and host-installed copies elsewhere invisible.
- `find` — callable. `find`(resource_name) locates a packaged resource by posix-style relative name. For the English sentence-boundary model the name is `tokenizers/punkt_tab/english/` (trailing slash). That return identifies a readable directory: if the return has a `path` attribute, that attribute is the directory; otherwise converting the return to a filesystem path is the directory. For the averaged perceptron tagger resources `taggers/averaged_perceptron_tagger_eng/` and `taggers/averaged_perceptron_tagger_rus/`, and for the packaged tables `taggers/universal_tagset/`, a successful locator exposes a `path` attribute that is a non-empty filesystem directory. A return with no `path` directory attribute is not a successful locator for those tagger resources, even when converting the return to a filesystem path would yield a directory.
- `clear_cache` — callable with no arguments. Drops in-process cached resources so a subsequent sentence-model lookup honors the current `path`.

The environment variable `LINGORA_DATA` contributes directories to `path` at import. After import, the mutable list is the control that a later call observes.

## `lingora.chunk`

Importable submodule `lingora.chunk`. The chunk parser that reads a chunk grammar, and the named-entity chunker, are imported from this module:

```
from `lingora.chunk` import (
    `RegexpParser`,
    `ne_chunk`,
)
```

The same submodule is importable as `from `lingora` import `chunk``. These names are importable as ``lingora.chunk`.<name>` and as `from `lingora.chunk` import <name>`:

- `RegexpParser`
- `ne_chunk`

`RegexpParser` instances expose `parse`, which takes a list of tagged pairings as the first positional argument and returns a chunk structure. `ne_chunk` is a module-level function that takes that same tagged list as the first positional argument.

A chunk structure is a shallow labelled tree: the root is a sentence, the leaves are the input tagged pairings in order, and the only internal nodes are chunks. Each internal node has a string `label` (a callable `label` method, or a string `label` attribute) and is a non-string sequence of children. A tagged leaf is a pairing whose first component is the token and whose second component is the tag string. A successful parse of a tagged list returns such a structure. A rooted tree with no children is a successful empty result, not a stand-in for a call that could not be performed.

`RegexpParser` constructs and parses when `data.path` is empty. It does not require a packaged chunker model. `ne_chunk` locates a packaged named-entity model; that path fails when the model is not visible on `data.path`.

If a loaded named-entity chunker is memoized, `clear_cache` on `data` (and any callable `cache_clear` exposed on objects in `lingora.chunk`) must drop that memo so the next call honors the current `data.path`.

Signatures, grammar syntax, resource names, and token-level chunk outcomes belong with each symbol.

## `lingora.chunk.RegexpParser`

Import `RegexpParser` from `lingora.chunk` (`from `lingora.chunk` import `RegexpParser``). Chunk parser that reads a **chunk grammar** and applies it to a list of tagged pairings. Does not require a packaged model. Constructs and parses when `data.path` is empty.

### Signature

```
`RegexpParser`(grammar)
```

- `grammar` (`str`) — chunk-grammar text. Required. Passed positionally.

The constructed object is used by calling `parse`:

```
`parse`(tagged)
```

- `tagged` — a list of tagged pairings. Each pairing is a two-element sequence: the token and its tag string. Required. Passed positionally.
- Returns a chunk structure when the call succeeds.

### Grammar text

The grammar is a string of one or more clauses. Each clause names a chunk label and then lists tag patterns. A clause begins with a line `NAME: pattern`. Further patterns of the same clause appear on following indented lines. The clause name is the `label` of every chunk that clause introduces. Different clause names on the same tagged list produce differently labelled chunks.

A **tag pattern** matches a sequence of tags. Each tag is written inside angle brackets. Whitespace in a tag pattern is ignored: `{<DT>? <JJ>* <NN>}` is the same pattern as `{<DT>?<JJ>*<NN>}`. Quantifiers apply to the preceding tag group: `?` (optional), `*` (zero or more), `+` (one or more), and a curly-bracket count such as `{4,}` (four or more). A `.` inside a tag group matches a character of that tag, so `<N.*>` matches any tag that begins with `N`. `|` inside a tag group is alternation, so `<VBD|IN>` matches either tag.

A pattern enclosed in braces (`{` … `}`) **chunks** every matching unchunked sequence. A pattern written with a closing brace, then a tag pattern, then an opening brace (`}` … `{`) **chinks**: it strips matching tokens out of an existing chunk. A chink is a later pattern in the **same** clause, not a later clause.

Clauses run in order and may cascade. A later clause can chunk remaining unchunked tokens after an earlier clause. A chink placed in a later clause does not strip tokens out of an earlier clause’s chunks.

The parser consults the grammar text. Two constructions whose tag patterns differ are independent: the same tagged list can be chunked under one pattern and left unchunked (or chunked differently) under the other.

The root `label` of the resulting structure defaults to a sentence label. Parsers constructed without a root override share that same sentence-label string. That string is not the clause’s chunk label.

### Observable chunks

With a single clause whose tag pattern is optional determiner, zero or more adjectives, then a common noun (`{<DT>?<JJ>*<NN>}`):

- `the`/`DT`, `big`/`JJ`, `dog`/`NN`, `barked`/`VBD` yields one chunk of that clause’s label covering `the big dog`, and `barked`/`VBD` as a direct sentence leaf (not inside that chunk).
- `dog`/`NN`, `barked`/`VBD` yields one chunk covering only `dog`, then `barked` as a leaf.
- `barked`/`VBD` alone yields a sentence whose only child is that tagged pairing; it does not invent a chunk of that clause’s label.
- `the`/`DT`, `dog`/`NN`, `barked`/`VBD` (zero adjectives) yields a chunk covering `the dog`, then `barked` as a leaf.
- `the`/`DT`, `big`/`JJ`, `barked`/`VBD` (determiner and adjective, no noun) yields no chunk of that label; every pairing is a direct sentence leaf.
- Two adjectives then a noun then a verb yields one chunk covering the determiner–adjective–adjective–noun span, then the verb as a leaf.
- Adjective then noun, with no determiner, yields a chunk covering those two pairings, then the following verb as a leaf.
- Two disjoint determiner–noun spans separated by a verb yield two chunks of that label, one per span, with the verb as a leaf between them.
- Two adjacent determiner–noun spans yield two chunks, not one merged chunk.

The compact writing `{<DT>?<JJ>*<NN>}` and the spaced writing `{<DT>? <JJ>* <NN>}` produce the same chunks on those lists. A different pattern on the same clause name, `{<VBD>}`, does not: on `the`/`DT`, `big`/`JJ`, `dog`/`NN`, `barked`/`VBD` it chunks only `barked` and leaves the first three pairings as sentence leaves. A pattern written with one caller-chosen tag chunks a pairing that carries that tag; a pattern written with a different tag does not.

With a single clause whose tag pattern chunks four or more consecutive tags that begin with `N` (`{<N.*>{4,}}`):

- On a list that concatenates, in this order, the four-token run `Court`/`NN-TL`, `Judge`/`NN-TL`, `Durwood`/`NP`, `Pye`/`NP`; then a separator whose tag does not begin with `N`; then the two-token run `term`/`NN`, `jury`/`NN`; then another such separator; then the four-token run `Mayor-nominate`/`NN-TL`, `Ivan`/`NP`, `Allen`/`NP`, `Jr.`/`NP` — the result has exactly two chunks of that clause’s label, covering the two four-token runs, and does not chunk `term`/`jury`. Each separator and each `term`/`jury` pairing is a direct sentence leaf.
- Concatenating those three runs with no separator yields one chunk over all ten tokens, not two four-token chunks.
- Three consecutive tags that begin with `N` are not a chunk. A run of four or more such tags is one chunk covering the whole run.

With a clause whose first pattern chunks every tagged pairing (`{<.*>+}`) and whose next pattern in the same clause is a chink of one or more consecutive past-tense-verb or preposition tags (`}<VBD|IN>+{`), applied to `the`/`DT`, `little`/`JJ`, `cat`/`NN`, `sat`/`VBD`, `on`/`IN`, `the`/`DT`, `mat`/`NN`: the result is two chunks of that clause’s label (`the little cat` and `the mat`) with `sat`/`VBD` and `on`/`IN` as sentence leaves between them. Without the chink, the whole list is one chunk of that label. Putting that chink in a later clause (a different clause name) instead of in the same clause leaves the whole list as one chunk of the first clause’s label; the later clause introduces no chunk.

A first clause that chunks optional-determiner–adjective–noun, followed by a later clause that chunks `{<VBD>}`, applied to `the`/`DT`, `big`/`JJ`, `dog`/`NN`, `barked`/`VBD`, yields a first-clause chunk over `the big dog` and a second-clause chunk over `barked`. `barked` is not inside the first-clause chunk.

The structure’s leaves, in order, are exactly the input tagged pairings. Chunking groups; it does not drop, reorder, or retag.

### Empty list and refused grammars

`parse` of `[]` yields a chunk structure whose root `label` is the default sentence label (a string, shared across parsers that omit a root override, and not equal to either parser’s clause name) and whose children are empty. That empty child list is a successful empty result.

A chunk grammar that is not text and not a list of chunk-parser stages is refused. An integer, a mapping, and a list of ordinary strings each fail: construction does not yield a parser that returns a chunk structure for tagged input. Exception class and message wording are not pinned. A valid grammar string on the same process still constructs and parses.

## `lingora.chunk.ne_chunk`

Import `ne_chunk` from `lingora.chunk` (`from `lingora.chunk` import `ne_chunk``). Named-entity chunker. Chunks a **list of tagged pairings** using a packaged trained model. This is a resource-gated path, not the grammar-based parser.

### Signature

```
`ne_chunk`(tagged_tokens)
```

- `tagged_tokens` — a list of tagged pairings. Each pairing is a two-element sequence: the token and its tag string. Required. Passed positionally.

The call locates a packaged named-entity model through `data.path`. When that model is not visible, the call does not yield a chunk structure.

### Packaged model

The model is the directory resource `chunkers/maxent_ne_chunker_tab/english_ace_multiclass/` under `data.path`. An empty search list, or a search list that does not contain that directory, does not satisfy the path. An averaged perceptron tagger model on the same search list does not satisfy it.

If a loaded named-entity chunker is memoized, `clear_cache` on `data` (and any callable `cache_clear` exposed on objects in `lingora.chunk`) must drop that memo so the next call honors the current `data.path`.

### Absent resource

When `chunkers/maxent_ne_chunker_tab/english_ace_multiclass/` is not on `data.path`, `ne_chunk` does not yield a chunk structure. Returning a labelled chunk tree, including a rooted tree with no children, is success and is incorrect for this absent-resource case. Exception class and message wording are not pinned.

A `RegexpParser` constructed from caller-supplied grammar text still parses on the same process. Applied to `the`/`DT`, `big`/`JJ`, `dog`/`NN`, `barked`/`VBD` with an optional-determiner–adjective–noun clause, that grammar path still yields one chunk over the first three pairings and `barked`/`VBD` as a sentence leaf.

The same split holds when an English averaged perceptron tagger is installed and the named-entity directory is not: tagging a token list still proceeds, `ne_chunk` of that tagged list still does not yield a chunk structure, and the grammar path still parses.

## `lingora.classify`

Importable submodule `lingora.classify`. The Naive Bayes classifier, the decision tree classifier, and the classifier-versus-gold accuracy helper are imported from this module:

```
from `lingora.classify` import (
    `DecisionTreeClassifier`,
    `NaiveBayesClassifier`,
    `accuracy`,
)
```

These names are importable as ``lingora.classify`.<name>` and as `from `lingora.classify` import <name>`:

- `DecisionTreeClassifier`
- `NaiveBayesClassifier`
- `accuracy`

`train` is a classmethod on `NaiveBayesClassifier` and on `DecisionTreeClassifier`, not a module-level import. The caller supplies a list of labeled featuresets to `train`. The returned object exposes `classify`, which takes a featureset as the first positional argument and returns a label.

A featureset is a mapping from feature names to feature values. A labeled featureset is a two-element pairing `(featureset, label)`. A successful `classify` returns a label (not `None`). An empty-string label is a successful label, not a stand-in for a call that could not be performed.

`NaiveBayesClassifier` also exposes `prob_classify` (a probability distribution over labels for one featureset) and `labels` (the trained label inventory). `DecisionTreeClassifier` is a hard-label classifier: `classify` is required; a probability-distribution entry is not.

The module-level `accuracy` compares a classifier’s labels on a gold list of labeled featuresets to those gold labels. It is not the two-list `accuracy` imported from `lingora.metrics`.

Training, classification, and classifier-versus-gold accuracy succeed when `data.path` is empty. They do not require a packaged corpus or model.

Signatures, ranked probabilities, unseen-feature ignore, inventory, empty-featureset labels, and accuracy fractions belong with each symbol.

## `lingora.classify.DecisionTreeClassifier`

Import `DecisionTreeClassifier` from `lingora.classify` (`from `lingora.classify` import `DecisionTreeClassifier``). Classifier that learns a tree of feature tests from labeled featuresets and assigns the label at the leaf reached by an example. Does not require a packaged model. Trains and classifies when `data.path` is empty.

Construction is the classmethod `train` (`DecisionTreeClassifier`.`train`). That classmethod’s parameters belong with `train`. A probability-distribution entry is not required.

### Instance entries

```
`classify`(featureset)
```

- `featureset` — a mapping from feature names to feature values. Required. Passed positionally.
- Returns a trained label for that featureset. The return is not `None`.

Internal stump names, split feature names, and tree pretty-print text are not pinned.

### Two-example training (full featuresets)

Trained on this list:

- `{nice: True, good: True}` labeled `positive`
- `{bad: True, mean: True}` labeled `negative`

`classify` of `{nice: True, good: True}` yields `positive`. `classify` of `{bad: True, mean: True}` yields `negative`. The two labels differ.

### Caller-chosen names

The same protocol holds when the four feature names and the two labels are caller-chosen strings. Trained on `{f1a: True, f1b: True} → lab1` and `{f2a: True, f2b: True} → lab2`:

- `classify` of `{f1a: True, f1b: True}` yields `lab1`
- `classify` of `{f2a: True, f2b: True}` yields `lab2`
- those two labels differ

A classifier that always returns one frozen label regardless of the featureset fails this split.

### Empty of training features

`classify` of `{}` still returns one of the trained labels. The call is not refused and the return is not a label that was not in training. Which of the trained labels is returned is not pinned.

## `lingora.classify.NaiveBayesClassifier`

Import `NaiveBayesClassifier` from `lingora.classify` (`from `lingora.classify` import `NaiveBayesClassifier``). Classifier that learns label and feature-value frequencies from labeled featuresets and returns the most probable label. After training, the caller asks for a hard label and for a probability distribution over labels. Does not require a packaged model. Trains and classifies when `data.path` is empty.

Construction is the classmethod `train` (`NaiveBayesClassifier`.`train`). That classmethod’s parameters belong with `train`.

### Instance entries

```
`classify`(featureset)
```

- `featureset` — a mapping from feature names to feature values. Required. Passed positionally.
- Returns the most probable trained label for that featureset. The return is not `None`.

```
`prob_classify`(featureset)
```

- `featureset` — the same mapping shape as `classify`. Required. Passed positionally.
- Returns a probability distribution over trained labels. The object must yield a named label before any probability can be read: a callable `samples` that returns a non-string iterable of labels (a `str` return is not a label list), or a callable `max` that returns a label, or iteration over the object itself when it is a non-string sequence or a dict. An object that only exposes `prob` and cannot name a label is not a distribution. The distribution exposes `prob`: `prob`(label) returns a real number (not a boolean) for that label. A successfully read `0` is the number zero, not a stand-in for a lookup that could not be performed.

```
`labels`()
```

- No arguments.
- Returns a non-string sequence of the labels seen in training. A `str` return is not a label list (it would iterate as characters). The sequence contains every trained label and does not contain a label that was never seen.

### Two-example training

Trained on this list:

- `{nice: True, good: True}` labeled `positive`
- `{bad: True, mean: True}` labeled `negative`

`classify` of `{nice: True}` yields `positive`. On that featureset, `prob` of `positive` is strictly greater than `prob` of `negative`.

`classify` of `{bad: True}` yields `negative`. On that featureset, `prob` of `negative` is strictly greater than `prob` of `positive`.

Swapping those two queries swaps the two labels: `classify` of `{bad: True}` then `{nice: True}` yields `negative` then `positive`. The two labels differ. A classifier that always returns the first training label fails this split.

`labels` of that classifier is exactly `{positive, negative}`: both names are present, and no third name is present.

### Caller-chosen names

The same protocol holds when the four feature names and the two labels are caller-chosen strings, not `nice` / `good` / `bad` / `mean` and `positive` / `negative`. Trained on `{f1a: True, f1b: True} → lab1` and `{f2a: True, f2b: True} → lab2`:

- `classify` of `{f1a: True}` yields `lab1`, and `prob` of `lab1` is strictly greater than `prob` of `lab2`
- `classify` of `{f2a: True}` yields `lab2`, and `prob` of `lab2` is strictly greater than `prob` of `lab1`
- swapping those two queries swaps the two labels
- `labels` is exactly `{lab1, lab2}`

### Unseen feature names

A feature name that never occurred in training is ignored. After the two-example training above, adding a never-seen name to `{nice: True}` does not flip the label from `positive` to `negative` and does not make every trained-label probability zero. Adding that same never-seen name to `{bad: True}` does not flip the label from `negative` to `positive` and does not make every trained-label probability zero.

### Empty of training features

`classify` of `{}` still returns one of the trained labels. The call is not refused and the return is not a label that was not in training. Which of the trained labels is returned is not pinned. The same holds after training on two caller-chosen labels.

## `lingora.classify.accuracy`

Import `accuracy` from `lingora.classify` (`from `lingora.classify` import `accuracy``). Accuracy helper that compares a classifier’s labels on a gold list of labeled featuresets to those gold labels. It asks the classifier for a label on each gold featureset; it is not a comparison of two caller-supplied label lists. The two-list helper is `lingora.metrics`.`accuracy`. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`accuracy`(classifier, gold)
```

- `classifier` — a trained classifier with callable `classify`. Required. Passed positionally.
- `gold` — a list of labeled featuresets, each a pairing `(featureset, label)`. Required. Passed positionally.
- Returns a real number: the fraction of positions `i` where the classifier’s label for gold[i]’s featureset equals gold[i]’s gold label. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

Accuracy is a fraction of aligned positions. It is not the size of the intersection of unique labels, and it is not a bag comparison that ignores order.

### Observable scores

After training `NaiveBayesClassifier` on `{nice: True, good: True} → positive` and `{bad: True, mean: True} → negative` (so `{nice: True}` classifies as `positive` and `{bad: True}` classifies as `negative`):

- gold `({nice: True}, positive)`, `({nice: True}, negative)`, `({bad: True}, negative)` yields `2/3`
- gold `({nice: True}, positive)`, `({nice: True}, negative)`, `({bad: True}, positive)`, `({bad: True}, negative)` yields `1/2` (not `2/3`)
- gold `({nice: True}, positive)`, `({nice: True}, negative)`, `({bad: True}, positive)` — the same three predicted labels as the first row, in the same order, against a permutation of the gold labels — yields `1/3` (not `2/3`)

The helper consults the classifier on those gold featuresets. A constant `2/3`, or a comparison that never asks the classifier, fails the length-four and permutation rows.

## `lingora.classify.train`

Classmethod `train` on `NaiveBayesClassifier` and `DecisionTreeClassifier` (`NaiveBayesClassifier`.`train`, `DecisionTreeClassifier`.`train`). Builds a classifier from a caller-supplied training list of labeled featuresets. Invoked after `from `lingora.classify` import `NaiveBayesClassifier`, `DecisionTreeClassifier``. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`NaiveBayesClassifier`.`train`(labeled_featuresets)
`DecisionTreeClassifier`.`train`(labeled_featuresets)
```

- `labeled_featuresets` — a list of labeled featuresets. Required. Passed positionally. Each item is a two-element pairing `(featureset, label)`. A featureset is a mapping from feature names to feature values (booleans, numbers, or strings). A label is the category for that example.
- Returns a trained classifier. The return has a callable `classify`. Returning `None`, or an object with no callable `classify`, is not a trained classifier.

`NaiveBayesClassifier`.`train` returns a Naive Bayes classifier: `classify`, `prob_classify`, and `labels` belong with `NaiveBayesClassifier`. `DecisionTreeClassifier`.`train` returns a decision tree classifier: `classify` belongs with `DecisionTreeClassifier`.

The trainer consults the caller’s list. Two trainings whose feature names or labels differ are independent classifiers. A classifier is not a frozen table of the names `nice` / `good` / `bad` / `mean` and `positive` / `negative`.

Smoothing constants, estimator names, tree-stump names, and extra keyword arguments are not pinned.

## `lingora.cli`

Importable submodule `lingora.cli`. The command-line group is imported from this module:

```
from `lingora.cli` import `cli`
```

The module exposes the public name `cli`, which is the command-line group object. That object is the program entry: it has a public callable `main`. Parameter lists, subcommand tokens, stdin/stdout behavior, and process status belong with that group object, not here.

## `lingora.cli.cli`

Import `cli` from `lingora.cli` (`from `lingora.cli` import `cli``). Command-line group for the library. The object has a public callable `main` used as the program entry.

### `main`

```
`main`(args=None, standalone_mode=True, **extra)
```

- `args` — argument tokens after the program name, as a list of strings. The tokenize subcommand is selected by the token `tokenize`, for example ``main`(`args`=['`tokenize`'], `standalone_mode`=True)`.
- `standalone_mode` — default `True`. When `True`, a successful run exits the process with status 0; a failure exits with a nonzero status (the exact nonzero number is not pinned).

Additional Click-style keywords such as `prog_name` may be accepted; callers who only pass `args` and `standalone_mode` omit them.

### Subcommand `tokenize`

The token `tokenize` selects the command-line tokenizer. That command:

- Reads a Unicode text stream from standard input.
- Applies the recommended word tokenizer `word_tokenize` to each input line, **including the sentence-splitting step** (the default in which the line is not treated as already delimited). Because of that step, the Punkt models for the requested language must be installed. The default language is `english`, located as `tokenizers/punkt_tab/english/` under `data.path`.
- Writes tokens joined by a single space (the default delimiter) as one output line per input line, terminated by a newline. A nonempty input line is not skipped.
- Does not write the original untokenized line in place of the joined tokens.

Standard input `Hello, world!` (followed by a newline) writes a line whose content is `Hello , world !` — the four recommended-word-tokenizer tokens of that line joined by spaces. That successful line is not the original `Hello, world!`.

Two nonempty input lines write two output lines, in order: the space-joined tokens of the first line, then the space-joined tokens of the second. For the homepage sentence `At eight o'clock on Thursday morning Arthur didn't feel very good.` the output line is the thirteen recommended-word-tokenizer tokens of that line joined by spaces (`At eight o'clock on Thursday morning Arthur did n't feel very good .`).

### Missing Punkt

When `data.path` does not contain the English sentence-boundary model, ``main`(`args`=['`tokenize`'], `standalone_mode`=True)` does not succeed: the process status is not 0, and the successful line `Hello , world !` is not written. Empty or garbage output with status 0 is not this refusal. The exact nonzero status, stderr wording, and exception type are not pinned.

## `lingora.corpus`

Importable submodule `lingora.corpus`. Packaged stopwords lists, the WordNet resource, and the English wordlist are imported from this module:

```
from `lingora.corpus` import (
    `stopwords`,
    `wordnet`,
    `words`,
)
```

These names are importable as ``lingora.corpus`.<name>` and as `from `lingora.corpus` import <name>`:

- `stopwords`
- `wordnet`
- `words`

Each imported object has a callable `unload` or `_unload`. Calling that hook drops a loaded corpus so a later lookup honors the current `data.path`. `clear_cache` on `data` is not a substitute for the hook. Details belong with each symbol.

## `lingora.corpus.stopwords`

Import `stopwords` from `lingora.corpus` (`from `lingora.corpus` import `stopwords``). Packaged per-language stopwords lists.

The import yields an object that has a callable `unload` or `_unload` (on the object or on its type). Calling that hook drops a loaded stopwords corpus so a later lookup honors the current `data.path`. Missing both names is a failure. `clear_cache` on `data` is not a substitute for this hook.

Packaged lists live under `corpora/stopwords` relative to a directory on `data.path` (file named with the language). Snowball stopword skipping reads that language’s list; signatures belong with `SnowballStemmer`.

## `lingora.corpus.wordnet`

Import `wordnet` from `lingora.corpus` (`from `lingora.corpus` import `wordnet``). Packaged WordNet resource.

The import yields an object that has a callable `unload` or `_unload` (on the object or on its type). Calling that hook drops a loaded WordNet corpus so a later lookup honors the current `data.path`. Missing both names is a failure. `clear_cache` on `data` is not a substitute for this hook.

When the WordNet resource is not visible on `data.path`, `WordNetLemmatizer` does not yield a lemma string. Graded stemmers do not require this resource. Signatures belong with `WordNetLemmatizer`.

## `lingora.corpus.words`

Import `words` from `lingora.corpus` (`from `lingora.corpus` import `words``). Packaged English wordlist.

The import yields an object that has a callable `unload` or `_unload` (on the object or on its type). Calling that hook drops a loaded English wordlist corpus so a later lookup honors the current `data.path`. Missing both names is a failure. `clear_cache` on `data` is not a substitute for this hook.

## `lingora.grammar`

Importable submodule `lingora.grammar`. The context-free grammar reader is imported from this module:

```
from `lingora.grammar` import `CFG`
```

That name is importable as `lingora.grammar`.`CFG` and as `from `lingora.grammar` import `CFG``.

`CFG` is the class that reads a grammar from production text via the classmethod `fromstring`. A grammar object exposes:

- `start` — no-argument callable. The start nonterminal of the grammar (the left-hand side of the first production when the text does not name another start).
- `productions` — no-argument callable. The sequence of productions the text defined, one production per alternative (a vertical bar on a right-hand side is additional productions, not one combined production).

Each production exposes `rhs`, a no-argument callable that returns a non-string sequence of right-hand-side symbols. Quoted terminals appear in that sequence as `str` values (the quote marks are not part of the terminal). Unquoted identifiers are nonterminals and are not those terminal strings.

Reading a grammar does not require a packaged model, tagger, or corpus. `fromstring` succeeds when `data.path` is empty.

Signatures, production syntax, start-symbol identity, production counts, and terminal sets belong with `CFG` and `fromstring`.

## `lingora.grammar.CFG`

Import `CFG` from `lingora.grammar` (`from `lingora.grammar` import `CFG``). Context-free grammar: a start symbol and a set of productions. Built from production text by the classmethod `fromstring`. Does not require a packaged model. Constructs when `data.path` is empty.

The usual construction is `CFG`.`fromstring`(text), not a direct constructor call. The classmethod’s parameters, production syntax, and observable start / production / terminal outcomes belong with `fromstring`.

A successful `fromstring` return is a grammar object used as the first positional argument to `ChartParser` and `ShiftReduceParser`, and as the first positional argument to `generate`.

### Grammar object

```
`start`()
```

- No arguments.
- Identifies the start nonterminal. The value is either a non-empty `str`, or an object whose callable `symbol` returns that non-empty `str`. Converting the value to `str` also yields a non-empty string form of the same start.
- For a grammar whose first production is `S -> …`, the start string is `S`. For a grammar whose first production’s left-hand side is a caller-chosen identifier, the start string is that identifier, not a hardcoded `S`.

```
`productions`()
```

- No arguments.
- Returns a non-string sequence of production objects. An empty sequence is returned only when the grammar actually has no productions; a failed read is not represented as `[]`.
- The length is the number of productions after expanding `|` alternatives. The fourteen-line toy grammar with eight written rules, four of which have two alternatives, has length 14. A three-rule grammar `Start -> L R`, `L -> 'w1'`, `R -> 'w2'` has length 3, not 14.

Each production exposes:

```
`rhs`()
```

- No arguments.
- Returns a non-string sequence (not a `str`). Quoted terminals on that production appear as `str` items equal to the quoted token (without the surrounding quotes). An empty production (nothing after the arrow) has an empty right-hand side. A quoted empty string `''` is one `str` item equal to `''`, not an empty right-hand side.

Terminals of the grammar are exactly those `str` items collected from every production’s `rhs`. They follow the caller’s quoted tokens. The fourteen-production grammar’s terminals include `the`, `cat`, `chased`, and `dog`. A grammar that never quotes `the` does not include `the`.

## `lingora.grammar.fromstring`

Classmethod `fromstring` on `CFG` (`CFG`.`fromstring`). Reads a context-free grammar from production text. Invoked after `from `lingora.grammar` import `CFG``. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`CFG`.`fromstring`(input)
```

- `input` (`str`) — grammar text. Required. Passed positionally.
- Returns a `CFG` grammar object.

### Production text

The text is one or more productions, one per line. Blank lines are ignored. A production is a left-hand nonterminal, an arrow `->`, and a right-hand sequence of nonterminals and/or quoted terminals.

Nonterminals are unquoted identifiers (for example `S`, `NP`, `Det`). Terminals are single-quoted (or double-quoted) tokens; the stored terminal is the text inside the quotes. `|` separates alternatives of the same left-hand side: `NP -> Det N | NP PP` is two productions.

The start symbol is the left-hand side of the first production.

An empty production is a left-hand side and an arrow with nothing after it (`B ->`). That is not the same as a production whose right-hand side is a quoted empty string (`B -> ''`).

Concatenating further production lines onto a grammar string adds those productions. `N -> 'rug'` appended to a grammar that already has `N -> 'dog' | 'cat'` adds `rug` as a terminal of `N`.

The reader consults the caller’s text. Two strings whose quoted terminals or whose right-hand-side order differ are independent grammars.

### Observable grammars

This text:

```
S -> NP VP
PP -> P NP
NP -> Det N | NP PP
VP -> V NP | VP PP
Det -> 'a' | 'the'
N -> 'dog' | 'cat'
V -> 'chased' | 'sat'
P -> 'on' | 'in'
```

yields a grammar whose `start` string is `S`, whose `productions` sequence has length 14, and whose terminals include `the`, `cat`, `chased`, and `dog`.

A caller-chosen start Z… with two further nonterminals and two quoted tokens, written as three productions `Z -> L R`, `L -> 'w1'`, `R -> 'w2'`, yields start `Z` (not `S`), three productions (not 14), and terminals `{w1, w2}` (not `{the, cat}`).

The same fourteen-production shape with caller-chosen quoted tokens for the determiner, the two nouns, the verb, and the preposition yields those caller tokens as terminals and uses them as the lexicon a parser consults.

## `lingora.metrics`

Importable submodule `lingora.metrics`. The two-list accuracy helper is imported from this module:

```
from `lingora.metrics` import `accuracy`
```

That name is importable as `lingora.metrics`.`accuracy` and as `from `lingora.metrics` import `accuracy``.

This `accuracy` takes two equal-length lists and returns the fraction of aligned positions that match. It is not the classifier-versus-gold `accuracy` imported from `lingora.classify`.

Scoring is a pure function of the arguments the caller supplies. It does not require a packaged corpus or a trained model. It succeeds when `data.path` is empty.

Signatures, position-fraction scores, and mismatched-length refusal belong with `accuracy`.

## `lingora.metrics.accuracy`

Import `accuracy` from `lingora.metrics` (`from `lingora.metrics` import `accuracy``). Position-wise accuracy of two lists: the fraction of indices at which the corresponding values are equal. Pure function of the two arguments. Does not require a packaged model or a trained classifier. Succeeds when `data.path` is empty.

This is not `lingora.classify`.`accuracy` (classifier plus gold labeled featuresets).

### Signature

```
`accuracy`(reference, test)
```

- `reference` — an ordered list of gold / reference values. Required. Passed positionally (first).
- `test` — an ordered list of values to compare against `reference` at the same positions. Required. Passed positionally (second).
- Returns a real number when the two lists have the same length: the fraction of positions `i` where `test[i] == reference[i]`. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

Accuracy is a fraction of aligned positions. It is not the size of the intersection of unique values, and it is not a bag comparison that ignores order.

### Observable scores

- `reference` `positive`, `negative`, `negative` against `test` `positive`, `positive`, `negative` yields `2/3`
- `reference` `positive`, `negative`, `positive` against the same `test` `positive`, `positive`, `negative` (the same bag of gold labels, permuted) yields `1/3`, which is not `2/3`
- `reference` `1`, `2`, `3` against `test` `1`, `2`, `4` yields `2/3`
- a list against itself yields `1`
- two caller-chosen length-four lists that match at two positions and differ at two yield `1/2` (not `2/3`)

### Mismatched lengths

When the two lists have different lengths, the call does **not** succeed: it does not return a real number, including `0`. Returning `None` is a refusal, not a score. Exception class and message wording are not pinned.

A one-element list against a two-element list is refused in both argument orders. The same two values as equal-length lists still yield `1`.

## `lingora.metrics.edit_distance`

Import `edit_distance` from `lingora.metrics` (`from `lingora.metrics` import `edit_distance``). Levenshtein edit distance between two strings: the number of insertions, deletions, and substitutions that transform the first string into the second. Substitution has a caller-chosen cost. Transposition of adjacent characters is a distinct, optional edit. Pure function of the arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`edit_distance`(s1, s2, substitution_cost=1, transpositions=False)
```

- `s1` — first string. Required. Passed positionally (first).
- `s2` — second string. Required. Passed positionally (second).
- `substitution_cost` — cost of replacing one character with a different character. Default `1`. Passed as a keyword.
- `transpositions` — whether an adjacent transposition counts as one edit. Default `False` (off). `True` is on. Passed as a keyword.
- Returns a real number: the edit distance. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

The two `transpositions` modes are distinguishable. Distance is a function of both strings and of those two keyword arguments; it is not a constant, and it is not a comparison that ignores order or transpositions.

### Observable distances

With `substitution_cost`=`1` and `transpositions`=`False`:

- `rain` against `shine` is `3`
- `shine` against `rain` is `3` (symmetric on that pair)
- `abc` against `ca` is `3`
- `acbdef` against `abcdef` is `2`
- a six-character string against the string formed by swapping one adjacent pair of its characters is `2`
- a string against itself is `0` (`rain` against `rain`; any other string against itself)
- two empty strings is `0`

With `substitution_cost`=`2` and `transpositions`=`False`:

- `rain` against `shine` is `5` (not `3`)

With `substitution_cost`=`1` and `transpositions`=`True`:

- `abc` against `ca` is `2` (not `3`)
- `acbdef` against `abcdef` is `1` (not `2`)
- a six-character string against the string formed by swapping one adjacent pair of its characters is `1` (not `2`)

## `lingora.metrics.f_measure`

Import `f_measure` from `lingora.metrics` (`from `lingora.metrics` import `f_measure``). Equal-weight f-measure of a reference set against a test set: the harmonic mean of `precision` and `recall` of that pair, with equal weight on the two. Pure function of the two arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`f_measure`(reference, test)
```

- `reference` — a set of gold / reference values. Required. Passed positionally (first).
- `test` — a set of values to score against `reference`. Required. Passed positionally (second).
- Returns a real number when both sets are non-empty: the equal-weight harmonic mean of precision (size of the intersection divided by the size of `test`) and recall (size of the intersection divided by the size of `reference`). A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

The two-argument call is equal-weight. It is not precision alone, not recall alone, and not their arithmetic mean.

### Observable scores

- `reference` `{1, 2, 3}` against `test` `{2, 3, 4}` yields `2/3`
- two non-empty disjoint sets yield `0`

When the two sets have different sizes and a proper partial overlap (for example a three-element reference against a two-element test that share one element), the result is a real number that is not `0`, not `1`, and not `2/3`.

### Empty either side

When `test` is empty, or when `reference` is empty, the call does **not** return a real number, including `0`. Returning `None` is absence, not a score. Exception class and message wording are not pinned.

That absence is distinguishable from the number `0`, which is the result when both sets are non-empty and their intersection is empty.

## `lingora.metrics.jaccard_distance`

Import `jaccard_distance` from `lingora.metrics` (`from `lingora.metrics` import `jaccard_distance``). Jaccard distance between two sets: the size of the symmetric difference divided by the size of the union. Pure function of the two arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`jaccard_distance`(label1, label2)
```

- `label1` — a set. Required. Passed positionally (first).
- `label2` — a set. Required. Passed positionally (second).
- Returns a real number: `|label1 △ label2| / |label1 ∪ label2|`. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

The result is a distance in `[0, 1]`, not a raw overlap count and not Jaccard similarity (`|intersection| / |union|`).

### Observable distances

- a set against itself yields `0` (`{1, 2, 3}` against `{1, 2, 3}`; any other set against a copy of itself)
- two non-empty disjoint sets yield `1`
- `{1, 2, 3}` against `{2, 3, 4}` yields `1/2` (symmetric difference has two elements; union has four)
- two three-element sets that share exactly two elements likewise yield `1/2` (not `0`, not `1`)

## `lingora.metrics.precision`

Import `precision` from `lingora.metrics` (`from `lingora.metrics` import `precision``). Precision of a reference set against a test set: the fraction of test values that appear in the reference. Pure function of the two arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`precision`(reference, test)
```

- `reference` — a set of gold / reference values. Required. Passed positionally (first).
- `test` — a set of values to compare against `reference`. Required. Passed positionally (second).
- Returns a real number when `test` is a non-empty set: the size of `reference ∩ test` divided by the size of `test`. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

Precision is a set overlap against `test`. It is not recall (overlap against `reference`), and it is not a position-wise list comparison.

### Observable scores

- `reference` `{1, 2, 3}` against `test` `{2, 3, 4}` yields `2/3` (two of the three test elements are in the reference)
- two three-element sets that share exactly two elements likewise yield `2/3`

When `reference` has three elements and `test` has two, and they share exactly one element, the result is a real number that is not `0`, not `1`, and not `2/3`, and it is not equal to `recall` of the same pair.

### Empty test

When `reference` is non-empty and `test` is empty, the call does **not** return a real number, including `0`. Returning `None` is absence, not a score. Exception class and message wording are not pinned.

### Non-sets

`reference` and `test` must be sets. Passing lists (for example `[1, 2, 3]` against `[2, 3, 4]`) or other non-set collections (for example tuples `(1, 2, 3)` against `(2, 3, 4)`) does **not** succeed: the call does not return a real number, including `0`. Returning `None` is a refusal, not a score. Exception class and message wording are not pinned. The same pair as sets still yields `2/3`.

## `lingora.metrics.recall`

Import `recall` from `lingora.metrics` (`from `lingora.metrics` import `recall``). Recall of a reference set against a test set: the fraction of reference values that appear in the test. Pure function of the two arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`recall`(reference, test)
```

- `reference` — a set of gold / reference values. Required. Passed positionally (first).
- `test` — a set of values to compare against `reference`. Required. Passed positionally (second).
- Returns a real number when `reference` is a non-empty set: the size of `reference ∩ test` divided by the size of `reference`. A boolean is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

Recall is a set overlap against `reference`. It is not precision (overlap against `test`), and it is not a position-wise list comparison.

### Observable scores

- `reference` `{1, 2, 3}` against `test` `{2, 3, 4}` yields `2/3` (two of the three reference elements are in the test)
- two three-element sets that share exactly two elements likewise yield `2/3`

When `reference` has three elements and `test` has two, and they share exactly one element, the result is a real number that is not `0`, not `1`, and not `2/3`, and it is not equal to `precision` of the same pair.

### Empty reference

When `reference` is empty and `test` is non-empty, the call does **not** return a real number, including `0`. Returning `None` is absence, not a score. Exception class and message wording are not pinned.

### Non-sets

`reference` and `test` must be sets. Passing lists (for example `[1, 2, 3]` against `[2, 3, 4]`) or other non-set collections does **not** succeed: the call does not return a real number, including `0`. Returning `None` is a refusal, not a score. Exception class and message wording are not pinned. The same pair as sets still yields `2/3`.

## `lingora.parse`

Importable submodule `lingora.parse`. Chart and shift-reduce parsers are imported from this module:

```
from `lingora.parse` import (
    `ChartParser`,
    `ShiftReduceParser`,
)
```

These names are importable as ``lingora.parse`.<name>` and as `from `lingora.parse` import <name>`:

- `ChartParser`
- `ShiftReduceParser`

String generation from a grammar lives in the nested submodule `lingora.parse.generate` (`from `lingora.parse.generate` import `generate``).

Parser instances are constructed with a `CFG` grammar as the first positional argument and expose `parse`, which takes a list of token strings as the first positional argument. A successful `parse` returns an iterable of constituent trees (a single tree is also a successful one-tree set). Iterating that result yields labelled, traversable trees whose leaves, in order, are the input tokens. An empty iterable is a successful empty parse set, not a stand-in for a call that could not be performed. Returning `None` is not a parse set. Returning a `str` is not a parse set.

`ChartParser` is exhaustive: it yields every parse the grammar assigns to the token list. `ShiftReduceParser` yields the single covering parse of an unambiguous sentence.

Both constructors and `parse` succeed when `data.path` is empty. They do not require a packaged model, tagger, or corpus.

The parser consults the caller’s grammar. Two grammars that differ in quoted terminals or in right-hand-side order are independent: the same token list can parse under one and yield an empty set under the other.

A token that no production quotes is uncovered. `parse` of a list that contains an uncovered token does not succeed. That failure is distinguishable from a successful empty parse set (the outcome for a covered but ungrammatical list). Exception class and message wording are not pinned.

Signatures, exhaustive counts, covering shapes, and uncovered-token refusal belong with each parser.

## `lingora.parse.ChartParser`

Import `ChartParser` from `lingora.parse` (`from `lingora.parse` import `ChartParser``). Exhaustive chart parser for a caller-supplied `CFG`. Does not require a packaged model. Constructs and parses when `data.path` is empty.

### Signature

```
`ChartParser`(grammar)
```

- `grammar` — a `CFG` object (the return of `CFG`.`fromstring`). Required. Passed positionally.

The constructed object is used by calling `parse`:

```
`parse`(tokens)
```

- `tokens` — a list of token strings. Required. Passed positionally.
- Returns an iterable of constituent trees when the call succeeds. A single tree is a successful one-tree set. An empty iterable is a successful empty parse set.

Each yielded tree is a labelled constituent: a string `label` (callable `label`, or a string `label` attribute) and a non-string sequence of children. Token-string children are leaves. Nested labelled nodes are internal constituents. Leaves in left-to-right order are the input tokens.

### Fourteen-production grammar

With the grammar whose productions are `S -> NP VP`, `PP -> P NP`, `NP -> Det N | NP PP`, `VP -> V NP | VP PP`, `Det -> 'a' | 'the'`, `N -> 'dog' | 'cat'`, `V -> 'chased' | 'sat'`, `P -> 'on' | 'in'`:

- `the`, `cat`, `chased`, `the`, `dog` yields exactly one tree. The root `label` is `S`. Leaves in order are those five tokens. An `NP` covers `the cat`. A `VP` covers `chased the dog` and contains a `V` covering `chased` and an `NP` covering `the dog`.
- The same five tokens against the same grammar with `NP -> N Det` in place of `NP -> Det N` yield an empty parse set.
- `dog`, `cat`, `the` (every token is a quoted terminal, but the sequence is ungrammatical) yields an empty parse set. The call succeeds with no trees. It does not invent a tree.
- `[]` against that grammar (the start symbol does not expand to the empty string) yields an empty parse set.
- After appending `N -> 'rug'`, the list `the`, `cat`, `chased`, `the`, `dog`, `on`, `the`, `rug` yields **more than one** tree. Every tree has those eight leaves in that order. At least one tree has the `PP` covering `on the rug` immediately dominated by `NP` (the object noun phrase `the dog on the rug`). At least one other tree has that same `PP` immediately dominated by `VP` (the verb phrase `chased the dog on the rug`). Those two attachments are distinct trees.

The same fourteen-production shape with caller-chosen quoted tokens for the determiner, subject noun, object noun, verb, and preposition, applied to `[det, n_subj, verb, det, n_obj]`, yields exactly one tree whose root is that grammar’s start and whose `NP` / `VP` / `V` covering matches those five tokens. Extending that grammar with a further noun and parsing `[det, n_subj, verb, det, n_obj, prep, det, n_pp]` likewise yields more than one tree, with both `NP` and `VP` attachments of the final `PP`.

### The parser consults the grammar

`S -> A B`, `A -> 'x'`, `B -> 'y'` applied to `x`, `y` yields exactly one tree whose leaves are `x`, `y`. The grammar with the terminals swapped (`A -> 'y'`, `B -> 'x'`) applied to the same `x`, `y` yields an empty parse set.

### Uncovered tokens

A token that no production quotes is uncovered. `parse` of `the`, `unicorn`, `chased`, `the`, `dog` against the fourteen-production grammar (which never quotes `unicorn`) does **not** succeed. The failure is distinguishable from the successful empty set returned for `dog`, `cat`, `the`. Exception class and message wording are not pinned. The same split holds for a caller-chosen nonce token in an otherwise legal five-token frame: the legal list parses as one tree; a permutation of covered tokens that is ungrammatical yields `[]`; substituting the nonce for the verb is refused.

## `lingora.parse.ShiftReduceParser`

Import `ShiftReduceParser` from `lingora.parse` (`from `lingora.parse` import `ShiftReduceParser``). Shift-reduce parser for a caller-supplied `CFG`. Does not require a packaged model. Constructs and parses when `data.path` is empty.

### Signature

```
`ShiftReduceParser`(grammar)
```

- `grammar` — a `CFG` object (the return of `CFG`.`fromstring`). Required. Passed positionally.

The constructed object is used by calling `parse`:

```
`parse`(tokens)
```

- `tokens` — a list of token strings. Required. Passed positionally.
- Returns an iterable of constituent trees when the call succeeds. A single tree is a successful one-tree set.

Each yielded tree is a labelled constituent with the same shape described for `ChartParser`: a string `label` and a non-string sequence of children; token-string children are leaves.

### Unambiguous five-token sentence

With the fourteen-production grammar `S -> NP VP`, `PP -> P NP`, `NP -> Det N | NP PP`, `VP -> V NP | VP PP`, `Det -> 'a' | 'the'`, `N -> 'dog' | 'cat'`, `V -> 'chased' | 'sat'`, `P -> 'on' | 'in'`, applied to `the`, `cat`, `chased`, `the`, `dog`: `parse` yields exactly one tree. That tree has the same covering as `ChartParser` on the same grammar and tokens: root `label` `S`; leaves those five tokens in order; an `NP` covering `the cat`; a `VP` covering `chased the dog` that contains a `V` covering `chased` and an `NP` covering `the dog`.

The same covering holds for the fourteen-production shape with caller-chosen quoted tokens: both parsers, given `[det, n_subj, verb, det, n_obj]`, each yield exactly one tree whose root is that grammar’s start and whose `NP` / `VP` / `V` spans match those five tokens.

## `lingora.parse.generate`

Importable submodule `lingora.parse.generate`. String generation from a context-free grammar is imported from this module:

```
from `lingora.parse.generate` import `generate`
```

That name is importable as `lingora.parse.generate`.`generate` and as `from `lingora.parse.generate` import `generate``.

`generate` takes a `CFG` grammar as the first positional argument and enumerates sentences as lists of terminal tokens. A successful call returns a non-string iterable of token lists. An empty iterable is a successful empty generation, not a stand-in for a call that could not be performed. Returning a `str`, or yielding a `str` as a sentence, is not a generated set.

Generation does not require a packaged model. It succeeds when `data.path` is empty.

A quoted empty string on a right-hand side is a token (the empty string). An empty production is the absence of a token. Those two writings are not interchangeable; signature, the `n` bound, and the observable sentence sets belong with `generate`.

## `lingora.parse.generate.generate`

Import `generate` from `lingora.parse.generate` (`from `lingora.parse.generate` import `generate``). Enumerates terminal strings of a `CFG`. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`generate`(grammar, start=None, depth=None, n=None)
```

- `grammar` — a `CFG` object. Required. Passed positionally.
- `start` — default `None`. `None`: generate from grammar.`start`().
- `depth` — default `None`. Bound on derivation depth. `None`: a finite default sufficient for a recursive grammar.
- `n` — default `None`. Maximum number of sentences to yield. `None`: no count cap. Passed as a keyword by callers who only need a prefix (for example `n`=`20`).
- Returns a non-string iterable of sentences. Each sentence is a non-string sequence of `str` tokens (a token list). A successful empty generation is `[]`. A `str` return, a `None` return, or a sentence that is itself a `str` is not a generated set.

### Quoted empty string versus empty production

The grammar

```
S -> A B
A -> 'a'
B -> 'b' | ''
```

yields both `['a', 'b']` and `['a', '']` (the second token is the empty string). With `n` large enough to cover both derivations (for example 20), both sentences are present.

The grammar

```
S -> A B
A -> 'a'
B -> 'b'
B ->
```

yields both `['a', 'b']` and `['a']` (one token). It does **not** yield `['a', '']`. With `n` large enough to cover both derivations, `('a', 'b')` and `('a',)` are present and `('a', '')` is absent.

The two grammars are not equivalent: one inserts an empty-string token; the other omits a token. The same split holds when `'a'` and `'b'` are replaced by caller-chosen quoted tokens: quoted-empty generation contains `(a, b)` and `(a, '')`; empty-production generation contains `(a, b)` and `(a,)` and does not contain `(a, '')`.

## `lingora.stem`

Importable submodule `lingora.stem`. Stemmers and the WordNet lemmatizer are imported from this module:

```
from `lingora.stem` import (
    `ARLSTem`,
    `ARLSTem2`,
    `LancasterStemmer`,
    `PorterStemmer`,
    `RegexpStemmer`,
    `SnowballStemmer`,
    `WordNetLemmatizer`,
)
```

These names are importable as ``lingora.stem`.<name>` and as `from `lingora.stem` import <name>`:

- `ARLSTem`
- `ARLSTem2`
- `LancasterStemmer`
- `PorterStemmer`
- `RegexpStemmer`
- `SnowballStemmer`
- `WordNetLemmatizer`

Stemmer class instances expose `stem`, which takes the input as the first positional argument and returns a `str`. A successful stem is a Unicode string. An empty string is a successful stem, not a stand-in for a call that could not be performed. `WordNetLemmatizer` exposes `lemmatize` rather than `stem`.

`stem` treats its argument as one token. A string that contains a space is not split into words.

`PorterStemmer`, `LancasterStemmer`, `SnowballStemmer` (with stopword skipping left off), `ARLSTem`, `ARLSTem2`, and `RegexpStemmer` do not require WordNet or a packaged stemmer model. They construct and stem when `data.path` is empty. `WordNetLemmatizer` does not yield a lemma string when the WordNet resource is absent.

Signatures, defaults, language names, and word-level stems belong with each symbol.

## `lingora.stem.ARLSTem`

Import `ARLSTem` from `lingora.stem` (`from `lingora.stem` import `ARLSTem``). Arabic light stemmer. Does not require a packaged model, a stopwords list, or WordNet.

Construct with no arguments: `ARLSTem`(). Construction succeeds when `data.path` is empty.

### Signature

```
`stem`(word)
```

- `word` (`str`) — Unicode Arabic input treated as a single token.
- Returns `str`.

### Observable stems

`يعمل` → `عمل`.

## `lingora.stem.ARLSTem2`

Import `ARLSTem2` from `lingora.stem` (`from `lingora.stem` import `ARLSTem2``). Arabic light stemmer (improved `ARLSTem`). Does not require a packaged model, a stopwords list, or WordNet.

Construct with no arguments: `ARLSTem2`(). Construction succeeds when `data.path` is empty.

### Signature

```
`stem`(word)
```

- `word` (`str`) — Unicode Arabic input treated as a single token.
- Returns `str`.

### Observable stems

`يعمل` → `عمل`.

## `lingora.stem.LancasterStemmer`

Import `LancasterStemmer` from `lingora.stem` (`from `lingora.stem` import `LancasterStemmer``). English Paice/Husk stemmer. More aggressive than default Porter on the words named below. Does not require a packaged model or WordNet.

Construct with no arguments: `LancasterStemmer`().

### Signature

```
`stem`(word)
```

- `word` (`str`) — input treated as a single token.
- Returns `str`.

### Observable stems

Each of the following words yields the stem on the right:

- `maximum` → `maxim`
- `presumably` → `presum`
- `multiply` → `multiply` (unchanged)
- `owed` → `ow`
- `saying` → `say`
- `crying` → `cry`
- `cement` → `cem`

On `maximum`, Lancaster yields `maxim` and default Porter does not.

### Per-word input

A string that contains a space is one token. `stem` of `owed saying` is a `str` and is not the concatenation of the stems of `owed` and `saying`.

## `lingora.stem.PorterStemmer`

Import `PorterStemmer` from `lingora.stem` (`from `lingora.stem` import `PorterStemmer``). English suffix-stripping stemmer after Porter’s algorithm. No-argument construction is the default (LINGORA extensions). Does not require a packaged model or WordNet.

Construct with no arguments: `PorterStemmer`().

### Signature

```
`stem`(word, to_lowercase=True)
```

- `word` (`str`) — input treated as a single token.
- `to_lowercase` (`bool`) — default `True`. `True`: lowercase `word` before stemming. `False`: keep the input case.
- Returns `str`.

When the `lingora` package is importable, `PorterStemmer`().`stem`('caresses') yields `caress`.

### Observable stems (default construction)

Each of the following words yields the stem on the right:

- `caresses` → `caress`
- `flies` → `fli`
- `dies` → `die`
- `mules` → `mule`
- `denied` → `deni`
- `died` → `die`
- `agreed` → `agre`
- `owned` → `own`
- `humbled` → `humbl`
- `sized` → `size`
- `meeting` → `meet`
- `stating` → `state`
- `siezing` → `siez`
- `itemization` → `item`
- `sensational` → `sensat`
- `traditional` → `tradit`
- `reference` → `refer`
- `colonizer` → `colon`
- `plotted` → `plot`

`oed` succeeds and yields `o`. The call is not refused.

### Case

Default `stem` of `Running` equals default `stem` of `running`.

Default `stem` of Caresses yields `caress`, the same stem as `caresses`.

`stem` of `I` with `to_lowercase`=`True` yields `i`. `stem` of `I` with `to_lowercase`=`False` yields `I`. The two settings differ on that one-letter word.

### Per-word input

A string that contains a space is one token. `stem` of `flies died` is a `str` and is not the concatenation of the stems of `flies` and `died`.

On `maximum`, default Porter does not yield `maxim` (Lancaster does).

## `lingora.stem.RegexpStemmer`

Import `RegexpStemmer` from `lingora.stem` (`from `lingora.stem` import `RegexpStemmer``). Stemmer that strips a caller-supplied regular-expression suffix pattern. It does not apply Porter rewriting. Does not require a packaged model or WordNet.

The constructor pattern is passed positionally:

```
`RegexpStemmer`(regexp)
```

- `regexp` (`str`) — regular expression identifying material to remove. Required. Passed positionally. A trailing-suffix pattern is written with a final `$` (example: `ing$` strips a trailing `ing`).

The constructed object is used by calling `stem`:

```
`stem`(word)
```

- `word` (`str`) — input treated as a single token.
- Returns `str`.

Matching material is removed; if the pattern does not match, `word` is returned unchanged.

### Observable stems

Configured as `RegexpStemmer`('ing$'):

- `running` → `runn` (the trailing `ing` is stripped; this is not Snowball `english`, which yields `run`)
- `run` → `run`
- a letter-token concatenated with trailing `ing` yields that letter-token
- the same letter-token with no trailing `ing` is unchanged
- `ing` that is not at the end of the string is not stripped: a letter-token, then `ing`, then another letter-token, is returned unchanged

Two different suffix patterns on one shared word differ: a pattern `S$` for a trailing suffix `S` strips that suffix; `ing$` does not strip a word whose trailing suffix is not `ing`.

## `lingora.stem.SnowballStemmer`

Import `SnowballStemmer` from `lingora.stem` (`from `lingora.stem` import `SnowballStemmer``). Language-specific Snowball stemmer. The first argument names the language. Does not require WordNet. Stopword skipping requires the packaged stopwords list for that language.

### Signature

```
`SnowballStemmer`(language, ignore_stopwords=False)
```

- `language` (`str`) — required. Passed positionally. Must be one of the names listed below.
- `ignore_stopwords` (`bool`) — default `False`. `False`: stem every word, including words that appear in a stopwords list. `True`: words that appear in the packaged stopwords list for `language` are returned unchanged. `True` requires that list to be visible on `data.path` at construction.

A successful construction yields an object whose `stem` is callable:

```
`stem`(word)
```

- `word` (`str`) — input treated as a single token.
- Returns `str`.

Construction with `ignore_stopwords`=`False` succeeds when `data.path` is empty. Stopword lookup honors the current `data.path` at construction. `clear_cache` on `data` drops in-process cached resources so a later construction honors the current list.

### Supported language names

The supported `language` names are exactly:

- `arabic`
- `danish`
- `dutch`
- `english`
- `finnish`
- `french`
- `german`
- `hungarian`
- `italian`
- `norwegian`
- `porter`
- `portuguese`
- `romanian`
- `russian`
- `spanish`
- `swedish`

Each of those names constructs a usable stemmer (callable `stem` that returns a `str`) when skipping is left off. Named stems below pin `english`, `porter`, `german`, `arabic`, `spanish`, and `russian`. `danish` is usable: `stem` returns a `str` (the exact stem of an arbitrary letter-token is not pinned).

### Unsupported language

A `language` that is not in the list above does not produce a usable stemmer: construction does not yield an object with a callable `stem` that returns a `str`. The failure identifies the requested language: that language name is observable in the failure. Exception class and full message wording are not pinned. Asking for `english` on the same entry still succeeds.

### Packaged stopwords list

The packaged list for a language is a per-language word list under `corpora/stopwords` relative to a directory on `data.path` (file named with that language). Enabling `ignore_stopwords`=`True` for `english` requires the `english` list, not a list installed only under another language name. Enabling it for `german` requires the `german` list; an `english` list alone does not make `german` with skipping construct.

When `ignore_stopwords`=`True` and that language’s list is not installed, construction does not succeed. Exception class and message wording are not pinned. The same language with `ignore_stopwords`=`False` still constructs and stems.

### Observable stems (skipping off, unless noted)

`english`: `running` → `run`; `generously` → `generous`; `having` → `have` (no stopwords list required).

`porter`: `generously` → `gener`. `english` and `porter` differ on `generously`.

`german`: `Schränke` → `schrank`; `keinen` → `kein` (no stopwords list required).

`arabic`:

- `العربية` → `عرب`
- `الطالبات` → `طالب`
- `فقالوا` → `قال`

`spanish`: `Visionado` → `vision`.

`russian`: `авантненькая` → `авантненьк`.

### Stopword skipping on, list present

When the `english` list is installed and contains `having`, `english` with `ignore_stopwords`=`True` leaves `having` unchanged. The same language with skipping off still yields `have`.

When the `german` list is installed and contains `keinen`, `german` with `ignore_stopwords`=`True` leaves `keinen` unchanged. The same language with skipping off still yields `kein`.

## `lingora.stem.WordNetLemmatizer`

Import `WordNetLemmatizer` from `lingora.stem` (`from `lingora.stem` import `WordNetLemmatizer``). WordNet lemmatizer. Requires the WordNet resource. Absence of WordNet is not a substitute for `PorterStemmer`, `LancasterStemmer`, or `SnowballStemmer`, which still construct and stem on the same process.

Construct with no arguments: `WordNetLemmatizer`().

### Signature

```
`lemmatize`(word)
```

- `word` (`str`) — input word.
- Returns `str` when the WordNet resource is available and the call succeeds.

### Missing WordNet

When the WordNet resource is not installed (`data.path` empty / the resource not visible), this path does not yield a lemma string. Either construction does not succeed, or `lemmatize` does not return a `str`. A returned `str` — including the original word unchanged — is a successful lemma and must not occur on that path. Exception class and message wording are not pinned.

## `lingora.tag`

Importable submodule `lingora.tag`. Sequential taggers and the recommended tagger are imported from this module:

```
from `lingora.tag` import (
    `DefaultTagger`,
    `RegexpTagger`,
    `UnigramTagger`,
    `pos_tag`,
)
```

The same submodule is importable as `from `lingora` import `tag``. These names are importable as ``lingora.tag`.<name>` and as `from `lingora.tag` import <name>`:

- `DefaultTagger`
- `RegexpTagger`
- `UnigramTagger`
- `pos_tag`

Class instances expose `tag`, which takes a token list as the first positional argument and returns a list of tagged pairings. `pos_tag` is the recommended tagger: a module-level function that takes the token list as the first positional argument and returns the same pairing-list shape.

A successful tagging of a token list returns a sequence whose length equals the input. Each item is a pairing whose first component is the corresponding input token and whose second component is the tag. A present tag is a case-sensitive string. When no tag is assigned, the second component is not a string (it is not an invented tag string). An empty token list yields `[]`. That empty list is a successful empty result, not a stand-in for a call that could not be performed.

`DefaultTagger`, `UnigramTagger`, and `RegexpTagger` construct and tag when `data.path` is empty. They do not require a packaged tagger model. `pos_tag` locates a packaged averaged perceptron model for the requested language; that path fails when the model is not visible on `data.path`.

If a loaded recommended tagger is memoized, `clear_cache` on `data` (and any callable `cache_clear` exposed on objects in `lingora.tag`) must drop that memo so the next call honors the current `data.path`.

Signatures, defaults, language names, resource names, and token-level tags belong with each symbol.

## `lingora.tag.DefaultTagger`

Import `DefaultTagger` from `lingora.tag` (`from `lingora.tag` import `DefaultTagger``). Sequential tagger that assigns one caller-chosen tag to every token. Does not require a packaged model. Constructs and tags when `data.path` is empty.

### Signature

```
`DefaultTagger`(tag)
```

- `tag` (`str`) — the tag assigned to every token. Required. Passed positionally.

The constructed object is used by calling `tag`:

```
`tag`(tokens)
```

- `tokens` — a list of token strings.
- Returns a list of tagged pairings aligned with `tokens`. Each pairing’s first component is the input token. Each pairing’s second component is the constructor tag string.

### Observable tags

Configured as `DefaultTagger`('NN'), `tag` of `This`, `is`, `a`, `test` yields four pairings, each tagged `NN`.

The constructor tag is the tag on every token. A tag string other than `NN` is applied to every token of a list that was never used as training data. An observer can tell this tagger from a unigram tagger that leaves an unseen word untagged.

`tag` of `[]` yields `[]`.

## `lingora.tag.RegexpTagger`

Import `RegexpTagger` from `lingora.tag` (`from `lingora.tag` import `RegexpTagger``). Sequential tagger that assigns tags by matching each token against caller-supplied regular expressions. Does not require a packaged model. Constructs and tags when `data.path` is empty.

### Signature

```
`RegexpTagger`(regexps, backoff=None)
```

- `regexps` — a list of `(pattern, tag)` pairs. Required. Passed positionally. Each `pattern` is a regular-expression string; each `tag` is the string assigned when that pattern matches the token. Example used for cardinal numbers: `(r'^[0-9]+$', 'CD')`.
- `backoff` — default `None`. When not `None`, a sequential tagger (for example a `DefaultTagger`) consulted only for tokens that match none of the patterns.

The constructed object is used by calling `tag`:

```
`tag`(tokens)
```

- `tokens` — a list of token strings.
- Returns a list of tagged pairings aligned with `tokens`. A token that matches a rule receives that rule’s tag string. A token that matches no rule receives no tag unless `backoff` assigns one.

Two constructions with different rule lists are independent: a shared token can be untagged under one rule list and tagged under another.

### Observable tags

Configured with the single number rule `(r'^[0-9]+$', 'CD')` and no backoff, `tag` of `saw`, `3`, `dogs` leaves `saw` untagged, tags `3` as `CD`, and leaves `dogs` untagged. A digit-only token other than `3` is tagged `CD`; a non-number letter-token is untagged.

The same number-rule tagger with a `DefaultTagger`(`'NN'`) as `backoff` tags `saw` as `NN`, keeps `3` as `CD`, and tags `dogs` as `NN`. Backoff fills only positions the regular-expression tagger left untagged.

`tag` of `[]` yields `[]`.

## `lingora.tag.UnigramTagger`

Import `UnigramTagger` from `lingora.tag` (`from `lingora.tag` import `UnigramTagger``). Sequential tagger trained on tagged sentences: each word is tagged with the tag seen for that word in training. Words never seen in training receive no tag unless a backoff tagger assigns one. Does not require a packaged model. Constructs and tags when `data.path` is empty.

### Signature

```
`UnigramTagger`(train=None, backoff=None)
```

- `train` — a tagged corpus: a list of sentences, each sentence a list of token/tag pairings (two-element sequences). Passed as the keyword `train`. The tagger learns a tag for each word string that appears in this corpus.
- `backoff` — default `None`. When not `None`, a sequential tagger (for example a `DefaultTagger`) consulted only for tokens this tagger does not tag.

The constructed object is used by calling `tag`:

```
`tag`(tokens)
```

- `tokens` — a list of token strings.
- Returns a list of tagged pairings aligned with `tokens`. A word seen in `train` receives the tag learned for that word. A word never seen in `train` has no tag string unless `backoff` assigns one. Inventing a tag for an unseen word when `backoff` is `None` is incorrect.

### Observable tags

Trained on two tagged sentences — `the`/`DT` then `dog`/`NN`, and `the`/`DT` then `cat`/`NN` — `tag` of `the`, `dog` tags `the` as `DT` and `dog` as `NN`. `tag` of `the`, `cat` tags `the` as `DT` and `cat` as `NN`.

The same trained tagger applied to `the`, `xyz` tags `the` as `DT` and assigns **no tag** to `xyz`. A `DefaultTagger`(`'NN'`) on `xyz` tags it `NN`. An observer can tell the trained unigram tagger from a default tagger on that unseen word.

The same unigram tagger with a `DefaultTagger`(`'NN'`) as `backoff` tags `xyz` as `NN` and keeps `the` as `DT`. Backoff fills only untagged positions; a word the unigram tagged keeps the unigram’s tag.

Training on other token/tag pairs tags those seen words with their trained tags and leaves a third, unseen word untagged when `backoff` is `None`. With backoff, that unseen word receives the backoff tag and a seen word keeps the trained tag.

`tag` of `[]` yields `[]`.

## `lingora.tag.pos_tag`

Import `pos_tag` from `lingora.tag` (`from `lingora.tag` import `pos_tag``). Recommended part-of-speech tagger. Tags a **list of tokens**, not a raw string. Supports English and Russian only. Each language uses a separately packaged averaged perceptron model located through `data.path`.

### Signature

```
`pos_tag`(tokens, tagset=None, lang="eng")
```

- `tokens` — a list of token strings. Required. Passed positionally. A `str` is not a token list.
- `tagset` — default `None`. `None`: return the tagger’s native tags (Penn Treebank for English, Russian National Corpus for Russian). `universal`: map those tags into the universal tagset.
- `lang` — default `"eng"`. `eng`: English. `rus`: Russian. Callers who omit it receive English.

Returns a list of tagged pairings aligned with `tokens` when the call succeeds.

### Packaged models

The English model is the directory resource `taggers/averaged_perceptron_tagger_eng/` under `data.path`. The Russian model is `taggers/averaged_perceptron_tagger_rus/`. Mapping English tags into `universal` also requires the packaged tables `taggers/universal_tagset/`. Mapping Russian tags into `universal` does not require those tables.

If a loaded recommended tagger is memoized, `clear_cache` on `data` (and any callable `cache_clear` exposed on objects in `lingora.tag`) must drop that memo so the next call honors the current `data.path`.

### English, native tags (English model present, `tagset` omitted)

Applied to this ten-token list — `John`, `'s`, `big`, `idea`, `is`, `n't`, `all`, `that`, `bad`, `.` — the result has ten pairings. Category structure (same named category → same tag; different named categories → distinct tags):

- `John` is a singular proper noun
- `'s` is a possessive ending
- `big` and `bad` share an adjective tag
- `idea` is a common singular noun
- `is` is a third-person singular verb
- `n't` is an adverb
- `all` is a predeterminer
- `that` is a determiner
- `.` is punctuation

Those nine categories are pairwise distinct.

Applied to the thirteen homepage tokens of `At eight o'clock on Thursday morning Arthur didn't feel very good.` — `At`, `eight`, `o'clock`, `on`, `Thursday`, `morning`, `Arthur`, `did`, `n't`, `feel`, `very`, `good`, `.` — `Thursday` and `Arthur` share a singular proper-noun tag with `John`, and `morning` shares a common-singular-noun tag with `idea`. `Thursday` / `Arthur` are distinct from `morning`. An observer can tell a proper name from a common noun on that sentence.

`pos_tag` of `[]` yields `[]`.

### Russian, native tags (Russian model present, `lang`=`rus`, `tagset` omitted)

Applied to Илья, оторопел, и, дважды, перечитал, бумажку, `.`:

- Илья is tagged `S` (noun)
- оторопел is tagged `V` (verb)
- Илья and бумажку share the noun tag
- оторопел and перечитал share the verb tag
- и is a conjunction
- дважды is an adverb
- `.` is non-lexical

Those five categories are pairwise distinct.

### Universal mapping

With the Russian model present, `lang`=`rus` and `tagset`=`universal` maps the noun and verb tags off the Russian National Corpus labels: Илья and бумажку share a mapped tag that is not `S`; оторопел and перечитал share a mapped tag that is not `V`; the mapped noun tag differs from the mapped verb tag. The same list without `tagset` still yields `S` on Илья and `V` on оторопел. This Russian mapping succeeds when `taggers/universal_tagset/` is not installed.

With the English model present and `taggers/universal_tagset/` absent, asking for `tagset`=`universal` does **not** succeed as a mapping. Either the call does not yield an aligned tagged list, or an aligned list is returned in which `John` and `idea` do not share a tag (the universal collapse of proper noun and common noun does not appear). Tagging that same list with `tagset` omitted still succeeds with the Penn Treebank category structure above. On a search list that has both language models but not the universal tables, Russian `universal` mapping still succeeds and English `universal` mapping still does not.

### Refusals

A raw string is refused. Passing `John's big idea isn't all that bad.` (untokenized) does not produce a nonempty tagged-pairing sequence. Tagging the ten-token list of that sentence succeeds when the English model is present. The two outcomes are distinguishable. Exception class and message wording are not pinned.

`lang` supports only `eng` and `rus`. Asking with `lang`=`Korean` does not yield an aligned tagged list when the English model is present. Asking with `lang`=`eng` on a token list still succeeds in that layout. A language name that is neither `eng` nor `rus` likewise does not succeed. Exception class and message wording are not pinned.

When the averaged perceptron model for the requested language is not on `data.path`, `pos_tag` does not yield an aligned tagged list. A `DefaultTagger` or trained `UnigramTagger` on the same process still tags. The English model does not satisfy `lang`=`rus`; the Russian model does not satisfy `lang`=`eng`. Exception class and message wording are not pinned.

## `lingora.tokenize`

Importable submodule `lingora.tokenize`. Tokenizers are imported from this module:

```
from `lingora.tokenize` import (
    `RegexpTokenizer`,
    `TreebankWordTokenizer`,
    `TweetTokenizer`,
    `WhitespaceTokenizer`,
    `WordPunctTokenizer`,
    `blankline_tokenize`,
    `sent_tokenize`,
    `word_tokenize`,
    `wordpunct_tokenize`,
)
```

These names are importable as ``lingora.tokenize`.<name>` and as `from `lingora.tokenize` import <name>`:

- `RegexpTokenizer`
- `TreebankWordTokenizer`
- `TweetTokenizer`
- `WhitespaceTokenizer`
- `WordPunctTokenizer`
- `blankline_tokenize`
- `sent_tokenize`
- `word_tokenize`
- `wordpunct_tokenize`

Class instances expose `tokenize` (returns a `list` of `str`). Tokenizers that support spans also expose `span_tokenize` (an iterable of integer offset pairs). Module-level functions take the text as the first positional argument and return a `list` of `str`.

A successful call returns a list of Unicode strings. An empty list is a successful empty result. Signatures, defaults, and token-level outcomes belong with each symbol.

## `lingora.tokenize.RegexpTokenizer`

Import `RegexpTokenizer` from `lingora.tokenize` (`from `lingora.tokenize` import `RegexpTokenizer``). Caller-configured regular-expression tokenizer. The constructor pattern matches either the tokens themselves (default) or the separators between tokens (gap mode). Does not require a packaged model.

### Signature

```
`RegexpTokenizer`(pattern, gaps=False, discard_empty=True)
```

- `pattern` (`str`) — regular expression. Required. Passed positionally. Example used for capitalized words: `[A-Z]\w+`. Example used as a whitespace delimiter: `\s+`.
- `gaps` (`bool`) — default `False`. `False`: the pattern finds tokens (`re.findall` semantics). `True`: the pattern finds separators between tokens (`re.split` semantics).
- `discard_empty` (`bool`) — default `True`. When `gaps` is `True`, empty strings produced at the start or end of the input (or between adjacent separators) are discarded.

The constructed object is used by calling `tokenize`:

```
`tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`.

### Observable token lists

Configured as `RegexpTokenizer`(r'[A-Z]\w+') (gap mode off), `tokenize` of `Good muffins cost $3.88 in New York. Please buy me two of them. Thanks.` yields exactly `['Good', 'New', 'York', 'Please', 'Thanks']`. Lowercase words such as `muffins` and `cost` are absent. An additional capitalized word that matches `[A-Z]\w+` is included; a lowercase word is not.

Configured as ``RegexpTokenizer`(r'\s+', `gaps`=True)`, `tokenize` of a string that begins and ends with whitespace and contains two nonempty words separated by spaces yields those two words and does not include `''`. The first and last elements are not empty strings.

`tokenize` of `''` yields `[]`.

## `lingora.tokenize.TreebankWordTokenizer`

Import `TreebankWordTokenizer` from `lingora.tokenize` (`from `lingora.tokenize` import `TreebankWordTokenizer``). Penn Treebank word tokenizer. Most punctuation is a token of its own; standard contractions are split; decimal amounts such as `3.88` stay one token. Does not require a packaged model.

Construct with no arguments: `TreebankWordTokenizer`().

### Signature

```
`tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`.

### Observable token lists

`Good muffins cost $3.88 in New York.` keeps `3.88` as one token and still splits `$` off as its own token. The decimal is not split into `3`, `.`, and `88`. This list is not the word/punctuation tokenization of the same sentence.

`They'll save and invest more.` yields exactly `['They', "'ll", 'save', 'and', 'invest', 'more', '.']`. A host word followed by `'ll` is split so `'ll` is a token of its own and the host concatenated with `'ll` is not a token.

`tokenize` of `''` yields `[]`.

## `lingora.tokenize.TweetTokenizer`

Import `TweetTokenizer` from `lingora.tokenize` (`from `lingora.tokenize` import `TweetTokenizer``). Twitter-aware tokenizer. Accented letters remain intact as single tokens. Does not require a packaged model.

### Signature

```
`TweetTokenizer`(preserve_case=True, reduce_len=False, strip_handles=False)
```

- `preserve_case` (`bool`) — default `True`. When `True`, token casing is kept.
- `reduce_len` (`bool`) — default `False`. When `True`, repeated character sequences of length 3 or greater are reduced to length 3.
- `strip_handles` (`bool`) — default `False`. When `True`, Twitter @handle mentions are removed from the input before tokens are produced, so the handle string is not a token.

The constructed object is used by calling `tokenize`:

```
`tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`.

### Observable token lists

Configured as ``TweetTokenizer`(`strip_handles`=True, `reduce_len`=True)`, `tokenize` of `@myke: Let's test these words: resumé España München français`:

- omits `@myke` (the handle is not a token)
- keeps `:` as a token
- keeps `Let's` as one token
- keeps each of `resumé`, `España`, `München`, and `français` as one token (accents intact)

The same configuration applied to `@u…: hello café` omits that handle and keeps `café` as one token.

## `lingora.tokenize.WhitespaceTokenizer`

Import `WhitespaceTokenizer` from `lingora.tokenize` (`from `lingora.tokenize` import `WhitespaceTokenizer``). Splits only on whitespace (space, tab, newline). Punctuation attached to a word, and a currency amount with no internal space, stay inside that token. Does not require a packaged model.

Construct with no arguments: `WhitespaceTokenizer`().

### Signature

```
`tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`.

### Observable token lists

The two-line string whose first line is `Good muffins cost $3.88` and whose second line is `in New York. Please buy me two of them.` yields a list that contains `$3.88` as one token and `York.` (point attached) as one token. It does not split `$3.88` into `$` plus digits.

A runtime amount of the form `$<whole>.<frac>` with no internal space is one token. A word with a trailing point and no space before the point is one token.

`tokenize` of `''` yields `[]`. `tokenize` of `'   '` (spaces only) yields `[]`.

## `lingora.tokenize.WordPunctTokenizer`

Import `WordPunctTokenizer` from `lingora.tokenize` (`from `lingora.tokenize` import `WordPunctTokenizer``). Word/punctuation tokenizer: splits on the boundary between word characters and non-word characters, so a decimal amount is split at the point. Same family as `wordpunct_tokenize`. Does not require a packaged model.

Construct with no arguments: `WordPunctTokenizer`().

### Signature

```
`tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`. Same token lists as `wordpunct_tokenize` on the same string.

```
`span_tokenize`(text)
```

- `text` (`str`) — the same original string.
- Returns an iterable of span pairs. Each span is a two-element sequence of `int` offsets `(start, end)` such that `text[start:end]` equals the corresponding token from `tokenize`. The number of spans equals the number of tokens. Spans are in left-to-right order and do not overlap (each start is greater than or equal to the previous end). Exact integer pairs are not pinned beyond those recovery and ordering rules.

### Observable token lists

`Hello, world!` yields exactly `['Hello', ',', 'world', '!']`.

`Good muffins cost $3.88 in New York.` yields exactly eleven tokens, in order: `Good`, `muffins`, `cost`, `$`, `3`, `.`, `88`, `in`, `New`, `York`, `.`. The currency amount is four tokens (`$`, `3`, `.`, `88`); the joined amount `3.88` is not a token. The sentence-final point is its own token.

`tokenize` of `''` yields `[]`. `tokenize` of `'   '` (spaces only) yields `[]`.

## `lingora.tokenize.blankline_tokenize`

Import `blankline_tokenize` from `lingora.tokenize` (`from `lingora.tokenize` import `blankline_tokenize``). Blank-line tokenizer: any sequence of blank lines is a delimiter; the material between those delimiters is one segment. Does not require a packaged model.

### Signature

```
`blankline_tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str` (paragraph segments, not word tokens).

### Observable segments

A string whose first paragraph is `Good muffins cost $3.88 in New York. Please buy me two of them.` and whose second paragraph is `Thanks.`, the two paragraphs being separated by a blank line (`\n\n`), yields exactly `['Good muffins cost $3.88 in New York. Please buy me two of them.', 'Thanks.']`.

Two nonempty paragraphs separated by `\n\n` yield exactly those two strings, in order.

## `lingora.tokenize.sent_tokenize`

Import `sent_tokenize` from `lingora.tokenize` (`from `lingora.tokenize` import `sent_tokenize``). Recommended sentence tokenizer. Requires the Punkt models for the requested language. The default language is `english`, located as `tokenizers/punkt_tab/english/` under `data.path`.

### Signature

```
`sent_tokenize`(text, language="english")
```

- `text` (`str`) — input string.
- `language` (`str`) — default `"english"`. Names the Punkt language directory under `tokenizers/punkt_tab/`. Callers who omit it receive English.
- Returns `list` of `str` (sentence strings) when the model is present.

If a loaded sentence model is memoized, `clear_cache` on `data` (and any callable `cache_clear` exposed on objects in `lingora.tokenize`) must drop that memo so the next call honors the current `data.path`.

### Observable sentence lists (English Punkt present)

`Good muffins cost $3.88 in New York. Please buy me two of them. Thanks.` yields exactly three strings, in order: `Good muffins cost $3.88 in New York.`, `Please buy me two of them.`, `Thanks.`

The same three clauses in another order yield three sentences in that other order. A single clause `Thanks.` yields ['Thanks.'].

### Missing Punkt

When `data.path` does not contain the English sentence-boundary model, the call does not succeed. The failure is distinguishable from a successful empty list `[]`. A successful list of sentence strings is not returned. Exception class and message wording are not pinned. The word/punctuation tokenizer on the same process still succeeds.

## `lingora.tokenize.word_tokenize`

Import `word_tokenize` from `lingora.tokenize` (`from `lingora.tokenize` import `word_tokenize``). Recommended word tokenizer: an improved Penn Treebank word tokenizer. When sentence splitting is requested, it first splits the text with the recommended sentence tokenizer, then tokenizes each sentence and concatenates the tokens. When the caller asks to treat the input as one already-delimited line, no sentence model is required.

### Signature

```
`word_tokenize`(text, language="english", preserve_line=False)
```

- `text` (`str`) — input string.
- `language` (`str`) — default `"english"`. Used when sentences are split first. Names the Punkt language directory under `tokenizers/punkt_tab/`.
- `preserve_line` (`bool`) — default `False`. `True`: do not sentence-tokenize; treat `text` as one already-delimited line (no Punkt). `False`: sentence-tokenize first, which requires Punkt for `language`.
- Returns `list` of `str` when the call succeeds.

The command-line `tokenize` subcommand calls this entry with sentence splitting enabled (the `preserve_line`=`False` path).

### Already-delimited line (`preserve_line`=`True`; no Punkt)

Keeps decimal and grouped currency amounts as single tokens and still splits `$` off. Distinguishes this family from word/punctuation tokenization: `Good muffins cost $3.88 in New York.` contains `3.88` and `$`; it does not split that decimal into `3` / `.` / `88`.

`On a $50,000 mortgage of 30 years at 8 percent, the monthly payment would be $366.88.` keeps `50,000` and `366.88` as single tokens, contains `$` twice, contains `,` as a token, and ends with `.`.

`I cannot cannot work under these conditions!` does not contain `cannot`. Each `cannot` becomes the adjacent pair `can` then `not` (two such pairs). A surrounding-word sentence that contains one `cannot` likewise has no `cannot` token and has the pair `can` / `not`.

A sentence that begins with a straight double quote, such as `"We beat some pretty good teams to get here," Slocum said.`, replaces the opening quote with two backticks as one token and the closing quote with two single quotes as one token. The straight double-quote character is not itself a token.

`At eight o'clock on Thursday morning Arthur didn't feel very good.` yields exactly these thirteen tokens, in order: `At`, `eight`, `o'clock`, `on`, `Thursday`, `morning`, `Arthur`, `did`, `n't`, `feel`, `very`, `good`, `.`. `o'clock` is one token; `didn't` is not a token; `did` and `n't` are adjacent.

### Sentence splitting (`preserve_line`=`False`; English Punkt present)

`Good muffins cost $3.88 in New York. Please buy me two of them. Thanks.` yields a concatenated word-token list that contains `.` three times, contains `Please`, `muffins`, and `buy`, and does not glue `York.` to `Please` in one token.

### Missing Punkt (`preserve_line`=`False`)

When `data.path` does not contain the English sentence-boundary model, the call does not succeed. The failure is distinguishable from a successful empty list `[]`. Exception class and message wording are not pinned. The word/punctuation tokenizer on the same process still succeeds.

## `lingora.tokenize.wordpunct_tokenize`

Import `wordpunct_tokenize` from `lingora.tokenize` (`from `lingora.tokenize` import `wordpunct_tokenize``). Word/punctuation tokenizer as a module-level function. Same family as `WordPunctTokenizer`.`tokenize`. Splits on the boundary between word characters and non-word characters, so a decimal amount is split at the point. Does not require a packaged model.

### Signature

```
`wordpunct_tokenize`(text)
```

- `text` (`str`) — input string.
- Returns `list` of `str`. Same token lists as `WordPunctTokenizer` constructed with no arguments, then `tokenize` on the same string.

### Observable token lists

`Hello, world!` yields exactly `['Hello', ',', 'world', '!']`.

`Good muffins cost $3.88 in New York.` yields exactly eleven tokens, in order: `Good`, `muffins`, `cost`, `$`, `3`, `.`, `88`, `in`, `New`, `York`, `.`. The currency amount is four tokens (`$`, `3`, `.`, `88`); the joined amount `3.88` is not a token. A different dollar amount written as `$<whole>.<frac>` is likewise split so `$`, the whole digits, `.`, and the fraction digits are separate tokens and the joined amount is not a token.

This list is not the Penn Treebank / recommended tokenization of the same muffin sentence: those keep `3.88` as one token.

`wordpunct_tokenize` of `''` yields `[]`. `wordpunct_tokenize` of `'   '` (spaces only) yields `[]`.

When the `lingora` package is not importable, this function cannot be called and does not produce the four-token Hello list. When the package is importable, `Hello, world!` yields that four-token list.

## `lingora.translate`

Importable submodule `lingora.translate`. The sentence-level BLEU helper is imported from this module:

```
from `lingora.translate` import `bleu`
```

That name is importable as `lingora.translate`.`bleu` and as `from `lingora.translate` import `bleu``.

`bleu` scores a candidate token list against one or more reference token lists. The caller may supply n-gram `weights`; omitting `weights` uses equal weight on unigrams through 4-grams. Omitting a smoothing argument is unsmoothed.

Scoring is a pure function of the arguments the caller supplies. It does not require a packaged corpus or a trained model. It succeeds when `data.path` is empty.

Signatures, unigram versus default four-weight scores, and the guide-to-action versus insure-the-troops ranking belong with `bleu`.

## `lingora.translate.bleu`

Import `bleu` from `lingora.translate` (`from `lingora.translate` import `bleu``). Sentence-level BLEU of a candidate token list against one or more reference token lists. The caller chooses n-gram `weights`. The default is equal weights on unigrams through 4-grams and is unsmoothed. Pure function of the arguments. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`bleu`(references, hypothesis, weights=(0.25, 0.25, 0.25, 0.25))
```

- `references` — a list of reference token lists. Each reference is an ordered list of `str` tokens. Required. Passed positionally (first). A single reference is still wrapped in an outer list: [reference_tokens].
- `hypothesis` — the candidate token list: an ordered list of `str` tokens. Required. Passed positionally (second).
- `weights` — n-gram weights, in order from unigrams upward. Default `(0.25, 0.25, 0.25, 0.25)` (equal weight on 1-grams through 4-grams). Passed as a keyword when the caller does not want that default. A one-element sequence `[1]` is unigram-only.
- Returns a real number: the BLEU score. A boolean is not a score. A list of scores is not a score. A successful `0` is the number zero, not a stand-in for a call that could not be performed.

Arguments are token lists, not unsplit strings. Tokens are compared as given (case-sensitive). Omitting a smoothing argument leaves the score unsmoothed. Unigram-only BLEU and default four-weight unsmoothed BLEU are distinguishable on the same pair.

### Unigram-only (`weights`=[1])

- a candidate with no token in common with its only reference yields `0` (for example the tokens of `John loves Mary` against a three-token reference that shares none of those tokens)
- a candidate that is identical to its only reference yields `1` (the tokens of `John loves Mary` against themselves; any other token list against a copy of itself, including a two-token list)

### Default four-weight unsmoothed (`weights` omitted)

A two-token candidate that is identical to its only reference yields a score whose value rounded to four decimal places is `0`. Unigram-only BLEU of that same pair is `1`; the two calls are not equal.

### Guide-to-action versus insure-the-troops

Whitespace-split token lists of these strings, with `weights` omitted (default unsmoothed four-weight):

- candidate `It is a guide to action which ensures that the military always obeys the commands of the party`
- poorer candidate `It is to insure the troops forever hearing the activity guidebook that party direct`
- references:
  - `It is a guide to action that ensures that the military will forever heed Party commands`
  - `It is the guiding principle which guarantees the military forces always being under the command of the Party`
  - `It is the practical guide for the army always to heed the directions of the party`

BLEU of the guide-to-action candidate against those three references is a real number strictly between `0` and `1`, and is strictly greater than BLEU of the poorer candidate against the same three references.

## `lingora.tree`

Importable submodule `lingora.tree`. Constituent trees are imported from this module:

```
from `lingora.tree` import `Tree`
```

That name is importable as `lingora.tree`.`Tree` and as `from `lingora.tree` import `Tree``.

`Tree` is the labelled constituent-tree class. Construction is either ``Tree`(label, children)` (a label plus a list of children) or the classmethod `fromstring` (bracketed tree text). A tree is a labelled, non-string sequence of immediate children. Token-string children are leaves. Nested `Tree` children are internal nodes.

A tree exposes:

- `label` — a callable returning the node’s label string, or a string attribute of the same name.
- Sequence access to immediate children (`list(tree)` is those children in order; the sequence length is the number of immediate children).
- Equality: two trees compare equal when they have the same labels and the same children recursively, and unequal otherwise.
- Pretty-print / string linearization (`pformat`, or `pprint` / `pretty_print` / `str`) that contains labels and leaves in left-to-right order.

Building a tree from a label and a **string** as the child list is refused. Building a tree from a label with no child list is refused. ``Tree`(label, [])` succeeds as a labelled node with no children. Exception class and message wording are not pinned. Exact bracket golden strings and ASCII drawing are not pinned.

Tree construction and pretty-print do not require a packaged model. They succeed when `data.path` is empty.

Constructor parameters, refused child lists, equality, length, and pretty-print order belong with `Tree`. Bracketed-text syntax belongs with `fromstring`.

## `lingora.tree.Tree`

Import `Tree` from `lingora.tree` (`from `lingora.tree` import `Tree``). Labelled constituent tree: a node label and an ordered list of children. Children are token strings (leaves) or nested `Tree` values. Does not require a packaged model. Constructs when `data.path` is empty.

A second construction path is the classmethod `fromstring` (bracketed tree text). That classmethod’s parameters and bracket syntax belong with `fromstring`.

### Signature

```
`Tree`(label, children)
```

- `label` (`str`) — node label. Required. Passed positionally.
- `children` — a list of children (token strings and/or nested `Tree` values). Required. Passed positionally. Must be a list (or other non-string sequence), not a `str`. Omitting this argument is refused.

Returns a labelled constituent tree.

### Sequence, label, leaves, length

The tree is a non-string sequence of its **immediate** children. `list(tree)` is those children in order. Position `0` is the first child; position `1` is the second. The sequence length is the number of immediate children, not the number of leaves.

`label` is a callable that returns the label string, or a string attribute of the same name.

Leaves are the in-order token-string descendants: walk each child; a `str` child is a leaf; a labelled child contributes its own leaves.

``Tree`('S', [`Tree`('NP', ['I']), `Tree`('VP', [`Tree`('V', ['saw']), `Tree`('NP', ['him'])])])` has length 2, root label `S`, first child an `NP` whose only leaf is `I`, second child a `VP`, and leaves `I`, `saw`, `him` in that order. A flat tree whose children are `n` token strings has length `n`. ``Tree`(label, [])` has length 0, that `label`, and no leaves.

### Equality

`==` is recursive labels-and-children. Two independently constructed trees with the same labels and the same children (recursively) compare equal. Changing an inner label, changing a leaf, or changing the grouping of the same leaves makes them unequal.

The tree built from `(S (NP I) (VP (V saw) (NP him)))` equals the tree constructed from label `S` with children `NP`/`I` and `VP`/`V saw`/`NP him`. Changing that inner `NP`’s label to `X` makes the trees unequal. A wrapper `A -> B -> (C, leaf)` is not equal to siblings `A -> (B, C)` even when both have the same two leaves.

### Pretty-print

A public linearization shows labels and leaves in left-to-right order (gaps between them are allowed). If a callable `pformat` is present, calling it with no arguments returns a nonempty `str` that contains that order. Otherwise a callable `pprint` or `pretty_print` writes that text, or converting the tree to `str` yields it. Exact bracket golden strings and ASCII drawing are not pinned.

For `(S (NP I) (VP (V saw) (NP him)))` the text contains `S`, `NP`, `VP`, `V`, `NP` in that order and `I`, `saw`, `him` in that order. After relabelling the inner `NP` to `X`, the text contains `S`, `NP`, `VP`, `V`, `X` in that order and does not contain `S`, `NP`, `VP`, `V`, `NP` in that order. The same ordered-subsequence property holds for caller-chosen labels and leaves.

### Refused child lists versus empty children

``Tree`(label, 'not-children')` (a string as the child list) does not yield a labelled tree. `Tree`(label) (no child list) does not yield a labelled tree. Exception class and message wording are not pinned.

``Tree`(label, [])` **does** yield a labelled tree: root label is `label`, length 0, no leaves. That empty-child tree is distinguishable from both refusals.

## `lingora.tree.fromstring`

Classmethod `fromstring` on `Tree` (`Tree`.`fromstring`). Reads a constituent tree from **bracketed tree text**. Invoked after `from `lingora.tree` import `Tree``. Does not require a packaged model. Succeeds when `data.path` is empty.

### Signature

```
`Tree`.`fromstring`(s)
```

- `s` (`str`) — bracketed tree text. Required. Passed positionally.
- Returns a `Tree`.

### Bracketed text

A node is an opening parenthesis, a label, its children, and a closing parenthesis. Children are nested bracketed nodes or leaf tokens. Whitespace separates a label from its children and siblings from each other. Example:

```
(S (NP I) (VP (V saw) (NP him)))
```

That tree equals ``Tree`('S', [`Tree`('NP', ['I']), `Tree`('VP', [`Tree`('V', ['saw']), `Tree`('NP', ['him'])])])`: same labels, same children recursively, leaves `I`, `saw`, `him` in that order. Changing the inner `NP` label to `X` in the constructed tree makes the two unequal.

The same equality holds for caller-chosen labels and leaves written in the same nested-parenthesis form: `fromstring` of that text equals the tree built by nested ``Tree`(label, children)` calls, and is unequal to a tree that differs only by one inner label.

Exact printed bracket golden strings are not pinned; equality is structural (labels and children), not string identity of `s`.

