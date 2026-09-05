# Lingora Language Toolkit (LINGORA) — Full Product Requirements Document

## Product overview

**LINGORA** — the **Lingora Language Toolkit** — is a suite of open source Python modules, data sets, and tutorials for research and development in Natural Language Processing. It is a **library**. An integrator imports it and calls its published processing entries; it is not a single end-user application. A command-line convenience can tokenize a text stream with the same recommended word tokenizer the library exposes; that convenience is the same capability, not a second product.

The product advertises easy-to-use access to many packaged corpora and lexical resources such as WordNet, together with a suite of text processing libraries for **classification**, **tokenization**, **stemming**, **tagging**, **parsing**, and **semantic reasoning**. This document specifies the **core processing path a first-time integrator actually runs**: split text into tokens, reduce words to stems, assign part-of-speech tags, group tagged tokens into shallow chunks, parse a sentence against a caller-supplied grammar and work with constituent trees, train a text classifier, and score outputs with the built-in evaluation metrics.

A common first use, as the public documentation leads with, is the English sentence `At eight o'clock on Thursday morning Arthur didn't feel very good.`: obtain a list of word and punctuation tokens, then assign each token a part-of-speech tag. Leaving that sentence as one undifferentiated string, or returning tags that do not distinguish Arthur as a proper name from morning as a common noun when the recommended English tagger resource is installed, is a failure of that path.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call signatures belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished LINGORA library. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

Packaged corpora, WordNet, graphical corpus browsers, chat demos, Twitter helpers, wrappers for external industrial taggers and parsers, and first-order semantic inference against external theorem provers are part of the wider suite. They are **not** graded feature points in this medium-tier specification. When a graded path needs a packaged model (the Punkt sentence models, the averaged perceptron tagger), that prerequisite is stated on that path; a missing model is a failure of that path, not a license to substitute a stub.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Token** | A contiguous substring the tokenizer treats as one unit: a word, a number, a punctuation mark, or a similar piece. |
| **Token list** | An ordered sequence of tokens produced from one string. |
| **Span** | A pair of character offsets into the original string. Slicing the original string at a span must recover the corresponding token. |
| **Sentence token** | A substring the sentence tokenizer treats as one sentence. |
| **Stem** | The residual form a stemmer returns after stripping morphological affixes. A stem is not required to be a dictionary word. |
| **Tag** | A case-sensitive label on a token, typically a part-of-speech category such as a common noun or a proper noun. |
| **Tagged token** | A pairing of a token with a tag. |
| **Backoff** | A fallback tagger consulted only when the primary tagger does not assign a tag. |
| **Chunk** | A non-overlapping group of consecutive tagged tokens (for example a base noun phrase). |
| **Chunk structure** | A shallow tree whose root is the sentence, whose leaves are tagged tokens, and whose only internal nodes are chunks. |
| **Chunk grammar** | A small text grammar whose clauses name a chunk label and list tag patterns. A pattern in braces chunks matching tag sequences; later clauses may cascade. |
| **Tag pattern** | A pattern over tags, written with each tag inside angle brackets. Whitespace in a tag pattern is ignored. |
| **Context-free grammar** | A set of productions the caller supplies as text. A production has a left-hand nonterminal, an arrow, and a right-hand sequence of nonterminals or quoted terminals. |
| **Parse tree** | A constituent tree whose root is the grammar’s start symbol and whose leaves, in order, are the input tokens. |
| **Bracketed tree text** | The parenthesized encoding used by the Penn Treebank and by LINGORA: a node is an opening parenthesis, a label, its children, and a closing parenthesis. Example: a sentence whose subject is the pronoun I and whose verb phrase is saw him. |
| **Featureset** | A mapping from feature names to feature values that describes one example for a classifier. Values are typically booleans, numbers, or strings. |
| **Label** | The category a classifier assigns, such as positive or negative. |
| **Punkt** | LINGORA’s packaged sentence-boundary models. The recommended sentence tokenizer, and the recommended word tokenizer when it first splits the text into sentences, require Punkt for the requested language. |
| **Penn Treebank tokenizer** | The word tokenizer that follows Penn Treebank conventions: most punctuation is a token of its own; standard contractions are split; decimal amounts such as 3.88 stay one token. |
| **Word/punctuation tokenizer** | The simpler regular-expression tokenizer that splits on the boundary between word characters and non-word characters, so a decimal amount is also split at the point. |
| **Porter stemmer** | The English suffix-stripping stemmer after Porter’s published algorithm, with the three modes listed in FP-02. |
| **Snowball stemmer** | The family of language-specific stemmers after Martin Porter’s Snowball algorithms. The supported language names are listed in FP-02. |
| **Lancaster stemmer** | The Paice/Husk English stemmer. It is more aggressive than Porter on the words named in FP-02. |
| **Naive Bayes classifier** | The built-in classifier that learns label and feature-value frequencies from labeled featuresets and returns the most probable label. |
| **Decision tree classifier** | The built-in classifier that learns a tree of feature tests and assigns the label at the leaf reached by an example. |
| **BLEU** | The Bilingual Evaluation Understudy score over token lists: a candidate is scored against one or more reference token lists. |
| **Core capability** | A user-observable capability that reflects LINGORA’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |
| **Mandatory substrate** | A real host that can import this repository’s LINGORA package and run one word/punctuation tokenization. No GPU or compiled extension is required. |

## Public surface inventory

LINGORA is imported and used from Python. The public surface, grouped the way later feature points verify it, is:

- Tokenizing a string into words, punctuation, sentences, or spans, including the word/punctuation tokenizer, the Penn Treebank word tokenizer, LINGORA’s recommended word tokenizer, the recommended sentence tokenizer, whitespace and blank-line tokenizers, a caller-supplied regular-expression tokenizer, and a tweet tokenizer. An s-expression tokenizer also exists; it is not independently graded. A command-line tokenize command applies the recommended word tokenizer to each line of a text stream, including the sentence-splitting step, so it requires the Punkt models for the requested language.
- Stemming a word with Porter, Lancaster, Snowball, a caller-supplied suffix pattern, or the language-specific stemmers listed in FP-02.
- Tagging a token list: sequential taggers the caller trains (default, unigram, bigram, trigram, affix, regular-expression) with optional backoff, and LINGORA’s recommended English or Russian tagger when the corresponding averaged perceptron tagger resource is installed.
- Chunking a tagged token list with a chunk grammar. A named-entity chunker exists when its packaged model is installed; it is not the primary way to satisfy chunking.
- Building a context-free grammar from productions, parsing a token list with a recursive-descent, shift-reduce, or chart parser, generating strings from a grammar, and building, comparing, and pretty-printing constituent trees from bracketed tree text.
- Training and applying a Naive Bayes classifier or a decision tree classifier on labeled featuresets, including a probability distribution over labels for Naive Bayes.
- Scoring: Levenshtein edit distance (optional transpositions), Jaccard distance, accuracy, precision, recall, f-measure, and BLEU.

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A pure-Python library with no compiled extensions, native code, or GPU/accelerator requirements. Packaging uses a flat package layout. An editable install from this repository’s source tree is sufficient.
- **Language:** Python 3.10 or newer, through the latest 3.14. Declared runtime dependencies are XML safety, a command-line helper, joblib, a regular-expression engine at or newer than the 2021.8.3 series, and a progress-bar helper. Optional extra groups add scientific-computing libraries for some classifiers and plot helpers; they are not required for the mandatory CPU profile.
- **Platforms:** Windows, Mac OS X, and Linux. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host that can import the installed package from this repository and run one word/punctuation tokenization with no downloaded corpus or model.
- **Packaged data:** Many advertised resources (Punkt, the averaged perceptron tagger, WordNet, Treebank, and other corpora) live outside the source tree and are located through LINGORA’s data finder. Full-suite corpus download is documented via the package downloader. It is **not** required for the baseline word/punctuation tokenizer, for trainable sequential taggers, for regular-expression chunking, for grammar-based parsing, for in-memory classification, or for the evaluation metrics. When a feature point names a packaged model as a prerequisite, absence of that model makes that path fail observably.
- **Unicode:** Input and output are Unicode text. Accented letters in a tweet-style tokenizer remain intact as single tokens.
- **Threading and process model:** Not a graded concern. The library is used in-process.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature. The mandatory substrate is a real CPU host with LINGORA loaded from this repository’s sources.

For every feature point:

- **Present:** The loaded LINGORA library produces the tokenization, stemming, tagging, chunking, parsing, classification, or scoring outcomes described below on the named inputs.
- **Absent / hollow:** Tokenization always returns the original string or splits only on spaces; stemming is an identity function for the named Porter and Snowball examples; tagging assigns one constant tag regardless of training; chunking never introduces a chunk node; parsing always yields one dummy tree or always yields none; classification ignores the training labels; metrics always return zero or one.

Cheaper proxies (hard-coded token tables, a single regular expression that cannot tell the word/punctuation tokenizer from the Penn Treebank tokenizer, a stemmer that only lowercases, a tagger that does not learn from training data, a parser that does not consult the caller’s grammar) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces a core capability with a stub.

**Negative control (library substrate):** When the LINGORA package is deliberately not importable in an isolated subprocess (removed from the import path), a word/punctuation tokenization of `Hello, world!` must fail to produce a successful LINGORA token list — a hard assertion, not a skip. When the package is importable, that same tokenization succeeds and yields four tokens: Hello, a comma, world, and an exclamation mark. Output-equality alone is not proof that the real package ran.

## Non-goals

- Being a general-purpose regular-expression engine, machine-learning framework, or theorem prover.
- Shipping WordNet, Treebank, or other corpora inside the source tree. Those are packaged data. The data finder and downloader exist so callers can install them; they are not graded feature points here.
- Graphical applications (chart parser, chunk parser, WordNet browser, concordance, and similar desktop demos) and drawing helpers.
- Chat bots, Twitter clients, Hugging Face dataset helpers, and Toolbox readers.
- Wrappers that require an external binary or service (Stanford, Senna, Hunpos, Malt, Bllip, CoreNLP, Weka, MEGAM, TADM).
- Combinatory categorial grammar, discourse representation, first-order inference against Prover9 or Mace, and other semantic-reasoning tools that are not on the first-time processing path.
- N-gram language-model training as a separate graded product. Counting and scoring that classifiers and metrics already perform are specified where they are observable.
- Guaranteeing a particular tokens-per-second throughput (speed is a design note on the regular-expression chunker, not a graded oracle).

---

## Feature points

### FP-01: Word, punctuation, and sentence tokenization

**Public entry:** LINGORA’s tokenizer entries: the word/punctuation tokenizer; the Penn Treebank word tokenizer; LINGORA’s recommended word tokenizer (an improved Penn Treebank word tokenizer); the recommended sentence tokenizer; the whitespace tokenizer; the blank-line tokenizer; a regular-expression tokenizer the caller configures; the tweet tokenizer; and span extraction on a tokenizer that supports spans. An s-expression tokenizer also exists; it is not independently graded.

The command-line tokenize command applies the recommended word tokenizer to each line of a text stream, including the sentence-splitting step, and writes the tokens joined by a delimiter (space by default). Because that path splits sentences first, it requires the **Punkt** models for the requested language.

The recommended sentence tokenizer, and the recommended word tokenizer when it is asked to split the input into sentences first, require the **Punkt** models for the requested language. The word/punctuation tokenizer, the Penn Treebank word tokenizer, the recommended word tokenizer applied to one already-delimited line (no sentence splitting), the whitespace and blank-line tokenizers, a caller-configured regular-expression tokenizer, and the tweet tokenizer do **not** require a downloaded model. The mortgage, quotation, `cannot`, and homepage-sentence examples below are word-level behavior on a single line (no sentence splitting).

**Normal behavior:**

- The word/punctuation tokenizer applied to `Hello, world!` yields exactly four tokens, in order: Hello, a comma, world, and an exclamation mark.
- The word/punctuation tokenizer applied to `Good muffins cost $3.88 in New York.` yields exactly eleven tokens, in order: Good, muffins, cost, a dollar sign, 3, a point, 88, in, New, York, and a final point. The currency amount is split so the dollar sign, the digits before the point, the point, and the digits after the point are four separate tokens. The sentence-final point is its own token.
- The Penn Treebank word tokenizer and the recommended word tokenizer applied to that same muffin sentence keep `3.88` as one token. They still split the dollar sign off as its own token. An observer can tell these two families apart on this sentence: word/punctuation splits the decimal; Penn Treebank / recommended does not.
- The Penn Treebank word tokenizer applied to `They'll save and invest more.` yields seven tokens: They, a clitic `'ll`, save, and, invest, more, and a final point. The recommended word tokenizer applied to `I cannot cannot work under these conditions!` splits each `cannot` into `can` and `not`.
- The recommended word tokenizer applied to `On a $50,000 mortgage of 30 years at 8 percent, the monthly payment would be $366.88.` keeps `50,000` and `366.88` as single tokens, splits each dollar sign off, and splits the comma and the final point off as their own tokens.
- The recommended word tokenizer applied to a sentence that begins with a straight double quote (for example `"We beat some pretty good teams to get here," Slocum said.`) replaces the opening quote with two backticks as a token and the closing quote with two single quotes as a token.
- The recommended word tokenizer, applied to the advertised homepage sentence `At eight o'clock on Thursday morning Arthur didn't feel very good.` as one already-delimited line (no sentence splitting), yields exactly these thirteen tokens, in order: At, eight, `o'clock` as one token, on, Thursday, morning, Arthur, did, `n't`, feel, very, good, and a final point. An observer can tell this from a space split: `o'clock` stays one token and `didn't` becomes `did` plus `n't`.
- The whitespace tokenizer applied to the two-line string whose first line is `Good muffins cost $3.88` and whose second line is `in New York. Please buy me two of them.` does **not** split `$3.88` or `York.`; it splits only on whitespace, so `$3.88` is one token and `York.` (point attached) is one token.
- The blank-line tokenizer applied to a string whose first paragraph is `Good muffins cost $3.88 in New York. Please buy me two of them.` and whose second paragraph is `Thanks.`, the two paragraphs being separated by a blank line, yields exactly two segments: the first paragraph as one string and `Thanks.` as the other.
- A regular-expression tokenizer configured to match capitalized words, applied to `Good muffins cost $3.88 in New York. Please buy me two of them. Thanks.`, yields exactly the capitalized tokens Good, New, York, Please, and Thanks, and does not yield muffins or cost.
- A regular-expression tokenizer configured to treat whitespace as the delimiter (gap mode) applied to a string that begins or ends with whitespace does not return empty tokens at the ends.
- The tweet tokenizer, with handle stripping and length reduction enabled, applied to `@myke: Let's test these words: resumé España München français` omits the `@myke` handle, keeps the colon after it, keeps `Let's` as one token, and keeps each of `resumé`, `España`, `München`, and `français` as one token (accents intact).
- When a tokenizer reports spans for `Good muffins cost $3.88 in New York.`, each span is a pair of offsets into that same string; slicing the string at that span equals the corresponding token; spans are in left-to-right order and do not overlap.
- When the Punkt English models are installed, the recommended sentence tokenizer applied to `Good muffins cost $3.88 in New York. Please buy me two of them. Thanks.` yields three sentence strings, in order: the muffin sentence, the please-buy sentence, and `Thanks.`
- When the Punkt English models are installed, the recommended word tokenizer applied to that same three-sentence string (with sentence splitting enabled) tokenizes each sentence and concatenates the tokens, so the result contains three sentence-final points and does not glue `York.` to `Please`.

**Boundary / error behavior:**

- An empty string yields an empty token list on the word/punctuation tokenizer, the Penn Treebank word tokenizer, the whitespace tokenizer, and a regular-expression tokenizer.
- A string that is only spaces yields an empty token list on the word/punctuation tokenizer and the whitespace tokenizer.
- When sentence splitting is requested and the Punkt models for the requested language are not installed, the recommended sentence tokenizer and the recommended word tokenizer do **not** succeed. The failure is distinguishable from a successful empty token list. The word/punctuation tokenizer on the same string still succeeds.
- The command-line tokenize command reads standard input and writes one output line per input line. It does not silently skip a non-empty input line. Because it applies the recommended word tokenizer with sentence splitting, it does **not** succeed when the Punkt models for the requested language are missing. When those models are installed, the input line `Hello, world!` writes the four recommended-word-tokenizer tokens of that line joined by spaces: Hello, a comma, world, and an exclamation mark.

**Verifiable oracle:**

- Success: `Hello, world!` through the word/punctuation tokenizer is Hello / comma / world / exclamation mark; `Good muffins cost $3.88 in New York.` through the word/punctuation tokenizer is eleven tokens and splits `$`, `3`, the point, and `88`, while the Penn Treebank and recommended word tokenizers keep `3.88` and still split `$`; `They'll save and invest more.` splits `They` from `'ll`; `cannot` splits into `can` and `not` on the recommended word tokenizer; a leading straight double quote becomes two backticks; the homepage Arthur sentence keeps `o'clock` and splits `didn't` into `did` plus `n't`; whitespace tokenization of the two-line muffin string keeps `$3.88` intact; blank-line tokenization of the muffin paragraph plus a blank line plus `Thanks.` is two segments; a capitalized-word regular-expression tokenizer returns Good, New, York, Please, Thanks; the tweet tokenizer drops `@myke` and keeps `resumé`; spans slice back to the same tokens; with Punkt installed, the three-sentence muffin string is three sentences and the command-line tokenize of `Hello, world!` writes those four tokens joined by spaces; without Punkt, the sentence-splitting path and the command-line tokenize command fail and the word/punctuation path still works.
- Failure / absence: every tokenizer is a space split; `$3.88` is never split by the word/punctuation tokenizer or is always split by the Penn Treebank tokenizer; contractions stay one token; `o'clock` is split or `didn't` stays one token on the recommended word tokenizer; sentence splitting or the command-line tokenize command succeeds with no Punkt models; spans do not recover the original substrings; the tweet tokenizer drops accented letters or keeps the handle when handle stripping was requested.

---

### FP-02: Stemming

**Public entry:** LINGORA’s stemmer entries. The built-in stemmer families are exactly: **Porter** (English), **Lancaster** (English, Paice/Husk), **Snowball** (the languages listed below), a **regular-expression** stemmer that strips a caller-supplied suffix pattern, **ISRI** (Arabic), **ARLSTem** and **ARLSTem2** (Arabic), **Cistem** (German), and **RSLP** (Portuguese). A WordNet lemmatizer also lives in this family; it requires the WordNet resource.

The **graded** stemmer families of this feature point are Porter in its default mode, Lancaster, Snowball for the languages named below, ARLSTem, ARLSTem2, and a regular-expression stemmer. ISRI, Cistem, RSLP, and the WordNet lemmatizer are **not** independently graded. RSLP and the WordNet lemmatizer require packaged data; their absence is not a substitute for the graded families, which do not require WordNet.

The Snowball language names are exactly: arabic, danish, dutch, english, finnish, french, german, hungarian, italian, norwegian, porter, portuguese, romanian, russian, spanish, and swedish. Enabling Snowball stopword skipping requires the packaged stopwords list for that language.

The Porter stemmer has exactly three modes: the original published algorithm, the Martin Porter extensions, and the LINGORA extensions. The default mode is the LINGORA extensions. The other two modes exist; they are **not** independently graded.

**Normal behavior:**

- The default Porter stemmer (LINGORA extensions) applied to each of the following words, in this order, yields the following stems: caresses → caress; flies → fli; dies → die; mules → mule; denied → deni; died → die; agreed → agre; owned → own; humbled → humbl; sized → size; meeting → meet; stating → state; siezing → siez; itemization → item; sensational → sensat; traditional → tradit; reference → refer; colonizer → colon; plotted → plot.
- The default Porter stemmer applied to `oed` succeeds and yields `o`. It does not refuse the word.
- The default Porter stemmer lowercases before stemming: `Running` and `running` yield the same stem. When the caller disables lowercasing, `I` is left as `I`; with lowercasing left on, `I` yields `i`. An observer can tell the two settings apart on that one-letter word.
- The Lancaster stemmer applied to `maximum` yields `maxim`; applied to `presumably` yields `presum`; applied to `multiply` yields `multiply` unchanged; applied to `owed` yields `ow`; applied to `saying` yields `say`; applied to `crying` yields `cry`; applied to `cement` yields `cem`. An observer can tell Lancaster from Porter on `maximum`: Lancaster yields `maxim`; default Porter does not yield `maxim`.
- The Snowball stemmer for english applied to `running` yields `run`. Applied to `generously` it yields `generous`.
- The Snowball stemmer for the language named porter applied to `generously` yields `gener`. An observer can tell the english Snowball language from the porter Snowball language on this one word.
- The Snowball stemmer for english, when stopword skipping is disabled (the default), applied to `having` yields `have`. When the packaged stopwords list for english is installed, the same stemmer with stopword skipping enabled leaves `having` unchanged.
- The Snowball stemmer for german applied to `Schränke` yields `schrank`. With stopword skipping disabled, `keinen` is stemmed to `kein`. When the packaged stopwords list for german is installed and stopword skipping is enabled, `keinen` is left unchanged.
- The Snowball stemmer for arabic applied to `العربية` yields `عرب`; applied to `الطالبات` yields `طالب`; applied to `فقالوا` yields `قال`.
- The Snowball stemmer for spanish applied to `Visionado` yields `vision`.
- The Snowball stemmer for russian applied to `авантненькая` yields `авантненьк`.
- ARLSTem and ARLSTem2 applied to `يعمل` each yield `عمل`.
- A regular-expression stemmer configured to strip a trailing `ing` applied to `running` yields `runn` (it strips the suffix; it does not apply Porter’s rewriting). Applied to `run` it yields `run`.

**Boundary / error behavior:**

- Asking Snowball for a language that is not in the list above (for example `klingon`) does not produce a usable stemmer. The failure identifies the unsupported language. Asking for `english` on the same entry succeeds.
- When Snowball stopword skipping is requested and the packaged stopwords list for that language is not installed, constructing the stemmer does **not** succeed. The same language with skipping left off still succeeds.
- Stemming is per word. Passing a whole sentence as one string is not split into words by the stemmer; the stemmer treats that string as a single token.
- The WordNet lemmatizer, when WordNet is not installed, does not succeed. That failure is not a substitute for Porter, Lancaster, or Snowball, which do not require WordNet.

**Verifiable oracle:**

- Success: the nineteen default-Porter pairs above hold; `oed` stems to `o`; `Running` and `running` match under default lowercasing; disabling lowercasing leaves `I` as `I` while the default yields `i`; Lancaster `maximum` is `maxim` and `multiply` is unchanged; Snowball english `running` is `run` and `generously` is `generous`; Snowball porter `generously` is `gener`; Snowball english skip-off stems `having` to `have`, and with the english stopwords list installed skip-on leaves `having` unchanged; Snowball german `Schränke` is `schrank` and skip-off stems `keinen` to `kein`, and with the german stopwords list installed skip-on leaves `keinen` unchanged; Snowball arabic `العربية` is `عرب`; an unsupported Snowball language fails; without the stopwords list, enabling skip fails and skip-off still works; a suffix-pattern stemmer strips `ing` from `running` without Porter rewriting.
- Failure / absence: every stemmer returns the input unchanged; Porter and Snowball english disagree with the named pairs; english and porter Snowball languages produce the same stem for `generously`; stopword skipping does not change `having` or `keinen` when the list is installed; enabling skip succeeds with no stopwords list; an unknown Snowball language is silently treated as english.

---

### FP-03: Part-of-speech tagging

**Public entry:** LINGORA’s tagger entries. The sequential taggers a caller can train without a downloaded model are exactly: a **default** tagger that assigns one tag to every token; a **unigram** tagger; a **bigram** tagger; a **trigram** tagger; an **affix** tagger; and a **regular-expression** tagger. Any of these may name another sequential tagger as backoff.

The **graded** trainable taggers of this feature point are the default tagger, the unigram tagger (with and without backoff), and the regular-expression tagger. Bigram, trigram, and affix taggers exist and follow the same train-then-tag protocol; they are **not** independently graded.

LINGORA’s **recommended** tagger for English and for Russian is a separately packaged averaged perceptron tagger. The recommended English tagger uses the Penn Treebank tagset; the recommended Russian tagger uses the Russian National Corpus tagset. The caller may ask the recommended tagger to map tags into the **universal** tagset. Mapping English tags into that tagset also requires the packaged universal tagset tables; mapping Russian tags does not. English mapping success when those tables are present is **not** independently graded.

**Normal behavior:**

- A default tagger constructed to assign `NN` applied to the token list `This`, `is`, `a`, `test` yields four tagged tokens, each tagged `NN`.
- A unigram tagger trained on two tagged sentences — `the`/`DT` then `dog`/`NN`, and `the`/`DT` then `cat`/`NN` — applied to `the`, `dog` tags `the` as `DT` and `dog` as `NN`. Applied to `the`, `xyz` tags `the` as `DT` and assigns **no tag** to `xyz` (the tag is absent). An observer can tell a trained unigram tagger from a default tagger on `xyz`.
- The same unigram tagger with a default-`NN` tagger as backoff tags `xyz` as `NN`. The backoff is used only for tokens the unigram tagger does not tag; `the` remains `DT`.
- A regular-expression tagger whose only rule tags any token matching a number pattern as `CD`, applied to `saw`, `3`, `dogs`, tags `3` as `CD` and assigns no tag to `saw` and `dogs` unless a backoff is set.
- Tagging an empty token list yields an empty list of tagged tokens.
- When the English averaged perceptron tagger resource is installed, the recommended English tagger applied to this ten-token list — John, `'s`, big, idea, is, `n't`, all, that, bad, and a point — yields these tags, in order: John is a singular proper noun; `'s` is a possessive ending; big is an adjective; idea is a common singular noun; is is a third-person singular verb; `n't` is an adverb; all is a predeterminer; that is a determiner; bad is an adjective; the point is a punctuation tag.
- When that same English resource is installed, the recommended English tagger applied to the thirteen homepage tokens of `At eight o'clock on Thursday morning Arthur didn't feel very good.` tags Thursday and Arthur as singular proper nouns and morning as a common singular noun. An observer can tell a proper name from a common noun on that advertised sentence.
- When the Russian averaged perceptron tagger resource is installed, the recommended tagger with the language set to Russian, applied to the seven-token list Илья, оторопел, и, дважды, перечитал, бумажку, and a point, tags Илья as a noun (S), оторопел as a verb (V), и as a conjunction, дважды as an adverb, перечитал as a verb, бумажку as a noun, and the point as non-lexical. Asking for the universal tagset maps the noun and verb tags to the universal noun and verb labels.

**Boundary / error behavior:**

- The recommended tagger accepts a **list of tokens**, not a raw string. Passing the untokenized string `John's big idea isn't all that bad.` does not succeed. The failure is distinguishable from a successful tagging of the tokenized list.
- The recommended tagger supports only English and Russian. Asking it to tag with a language that is neither (for example Korean) does not succeed. Asking it with English on a token list succeeds when the English resource is installed.
- When the averaged perceptron tagger resource for the requested language is not installed, the recommended tagger does not succeed. A unigram or default tagger trained or constructed by the caller on the same process still succeeds; the recommended path’s failure is not a license to skip tagging entirely.
- When the caller asks the recommended English tagger for the universal tagset and the packaged universal tagset tables are not installed, that mapping does **not** succeed. Tagging the same list without asking for the universal tagset still succeeds if the English averaged perceptron tagger resource is installed.
- Words never seen in unigram training receive no tag unless a backoff tagger assigns one. An implementation that invents a tag for an unseen word without backoff fails this feature point.

**Verifiable oracle:**

- Success: a default `NN` tagger tags every token `NN`; a unigram tagger trained on `the`/`DT` and `dog`/`NN` tags those words that way and leaves `xyz` untagged; the same tagger with default-`NN` backoff tags `xyz` as `NN` and keeps `the` as `DT`; an empty token list tags as empty; a raw string is refused by the recommended tagger; an unsupported language is refused; with the English resource installed, the ten-token John list receives the Penn Treebank tags named above, and the homepage Arthur sentence tags Thursday and Arthur as proper nouns and morning as a common noun; without the perceptron resource, the recommended path fails and a trained unigram tagger still works; without the universal tagset tables, English universal mapping fails and Penn Treebank tagging of the same list still works.
- Failure / absence: every token gets the same tag regardless of training; unseen words are tagged without backoff; the recommended tagger accepts a raw string; Korean is treated as English; the recommended path succeeds with no tagger resource; English universal mapping succeeds with no universal tagset tables; the John sentence or the homepage Arthur sentence is tagged with tags that do not distinguish a proper noun from a common noun when the English resource is installed.

---

### FP-04: Chunking

**Public entry:** LINGORA’s chunk parser that reads a **chunk grammar** and is applied to a list of tagged tokens. The grammar is a text with one or more clauses. Each clause names a chunk label and then lists tag patterns. A pattern enclosed in braces chunks every matching unchunked sequence. A pattern written with a closing brace, then a tag pattern, then an opening brace, strips matching tokens out of an existing chunk (a chink). Clauses run in order and may cascade, so a later clause can chunk over the output of an earlier clause. A chink is a later pattern in the same clause, not a later clause. The root label of the resulting chunk structure defaults to a sentence label.

A separately packaged named-entity chunker exists. It requires its trained model and tagged input. It is a resource-gated path, not the primary way to satisfy this feature point. Present-resource success of that path is **not** independently graded.

**Normal behavior:**

- A chunk grammar whose only clause is a noun-phrase label with the tag pattern “optional determiner, zero or more adjectives, then a common noun”, applied to the tagged tokens `the`/`DT`, `big`/`JJ`, `dog`/`NN`, `barked`/`VBD`, yields a chunk structure whose root is the sentence, whose first child is one noun-phrase chunk covering `the big dog`, and whose next child is the tagged token `barked`/`VBD` as a leaf (not inside that noun phrase).
- The same grammar applied to `dog`/`NN`, `barked`/`VBD` yields a noun-phrase chunk covering only `dog`, then `barked` as a leaf.
- The same grammar applied to `barked`/`VBD` alone yields a sentence whose only child is that tagged token; it does **not** invent a noun-phrase chunk.
- A chunk grammar whose only clause chunks four or more consecutive tags that begin with `N` (a curly-bracket quantifier inside the tag pattern), applied to a tagged-token list in which these runs appear in this order and are separated by tagged tokens whose tags do not begin with `N` — first the four-token run `Court`/`NN-TL`, `Judge`/`NN-TL`, `Durwood`/`NP`, `Pye`/`NP`; later the two-token run `term`/`NN`, `jury`/`NN`; and later the four-token run `Mayor-nominate`/`NN-TL`, `Ivan`/`NP`, `Allen`/`NP`, `Jr.`/`NP` — yields exactly two chunks of that label, each covering one of those two four-token runs, and does not chunk the two-token `term`/`jury` run. Concatenating the three runs with no such separator yields one chunk over all ten tokens, not two four-token chunks.
- A grammar whose first pattern chunks every tagged token into one noun-phrase, and whose next pattern in the same clause is a chink of one or more consecutive past-tense-verb or preposition tags, applied to `the`/`DT`, `little`/`JJ`, `cat`/`NN`, `sat`/`VBD`, `on`/`IN`, `the`/`DT`, `mat`/`NN`, yields two noun-phrase chunks (`the little cat` and `the mat`) with `sat`/`VBD` and `on`/`IN` as sentence leaves between them. An observer can tell a chink from a grammar that only chunks: without the chink, the whole list is one noun-phrase. Putting that chink in a later clause instead of in the same clause leaves the whole list as one noun-phrase.
- The chunk structure’s leaves, in order, are exactly the input tagged tokens. Chunking groups; it does not drop, reorder, or retag tokens.

**Boundary / error behavior:**

- An empty tagged-token list yields a chunk structure with a sentence root and no children.
- A chunk grammar that is not text and not a list of chunk-parser stages is refused. The operation does not succeed and does not return a chunk structure.
- When the named-entity chunker resource is not installed, the named-entity path does not succeed. A chunk-grammar parse of a caller-supplied tagged sentence still succeeds.

**Verifiable oracle:**

- Success: `the`/`DT` `big`/`JJ` `dog`/`NN` `barked`/`VBD` with an optional-determiner–adjective–noun grammar has one noun-phrase chunk over the first three tokens and `barked` as a sentence leaf; `barked` alone has no noun-phrase chunk; the four-or-more-noun-tags grammar, on those three runs separated by non-N tags, chunks the two four-token proper-noun runs and not the two-token `term jury` run; the same-clause chunk-then-chink grammar on `the little cat sat on the mat` yields two noun-phrases with `sat` and `on` as leaves; leaves equal the input; a non-grammar value is refused; without the named-entity resource that path fails and the grammar path still works.
- Failure / absence: the output is a flat list with no chunk nodes; tokens are dropped or reordered; `barked` is placed inside the noun phrase; the four-token quantifier is ignored so `term jury` is also chunked; the chink is ignored so `sat` stays inside one noun-phrase; a missing named-entity resource is treated as success with an empty tree.

---

### FP-05: Grammar-based parsing and constituent trees

**Public entry:** LINGORA’s context-free grammar reader; the recursive-descent, shift-reduce, and chart parsers that take such a grammar and a token list; the generator that enumerates strings from a grammar; and the constituent-tree entries that build a tree from a label plus children, build a tree from **bracketed tree text**, compare trees, read a node label, read children by position, list leaves, and pretty-print a tree.

The **graded** exhaustive parse counts on the fourteen-production grammar below are those of a **chart** parser. A recursive-descent parser exists; listing every parse of that grammar with it does not complete, so it is **not** independently graded here. A shift-reduce parser is graded on the unambiguous five-token sentence, not on the ambiguous rug sentence.

This feature point depends on tokens (FP-01) only as a list of terminals the caller already has. It does not require Punkt, a tagger, or a corpus.

**Normal behavior:**

- A context-free grammar read from the productions `S -> NP VP`, `PP -> P NP`, `NP -> Det N | NP PP`, `VP -> V NP | VP PP`, `Det -> 'a' | 'the'`, `N -> 'dog' | 'cat'`, `V -> 'chased' | 'sat'`, `P -> 'on' | 'in'` reports a start symbol S and fourteen productions. The terminals include `the`, `cat`, `chased`, and `dog`.
- A chart parser for that grammar, applied to the token list `the`, `cat`, `chased`, `the`, `dog`, yields exactly one parse tree. That tree’s root label is S. Its leaves, in order, are those five tokens. It has an NP covering `the cat` and a VP that contains a V `chased` and an NP covering `the dog`.
- The same parser applied to `the`, `cat`, `chased`, `the`, `dog`, `on`, `the`, `rug` — after the grammar is extended with `N -> 'rug'` — yields **more than one** parse tree. One tree attaches `on the rug` inside the object noun phrase; another attaches it to the verb phrase. An observer can tell the two trees apart by which constituent immediately dominates the PP. Both trees have the same eight leaves in the same order.
- The same parser applied to `dog`, `cat`, `the` yields **no** parse tree. The operation succeeds as an empty set of parses; it does not invent a tree.
- A shift-reduce parser for the unambiguous five-token sentence yields the same single tree shape as the chart parser on that sentence (S over NP `the cat` and VP `chased the dog`).
- Generating strings from a grammar `S -> A B`, `A -> 'a'`, `B -> 'b' | ''` (B may be the empty string) yields both `a` then `b`, and `a` then an empty token. Generating from the same grammar where B has an empty production (no quoted empty string) yields `a` then `b`, and a one-token string `a`.
- A tree built from the bracketed text `(S (NP I) (VP (V saw) (NP him)))` equals a tree built by giving label S two children: an NP whose only leaf is I, and a VP whose children are a V `saw` and an NP `him`. The pretty-printed form of either tree shows the S, NP, VP, V, and NP labels and the leaves I, saw, and him in that order. Changing the inner NP’s label to X makes the two trees unequal and makes the pretty-printed form show X in place of that NP.
- Two trees compare equal when they have the same labels and the same children recursively, and unequal otherwise. A tree’s length is the number of its immediate children. Leaves of the S-I-saw-him tree are I, saw, him in that order.

**Boundary / error behavior:**

- Building a tree from a label and a **string** as the child list (instead of a list of children) is refused. Building a tree from a label with no child list is refused. The failure is distinguishable from a successful tree with no children.
- A parser given a token that the grammar’s productions do not mention — `the`, `unicorn`, `chased`, `the`, `dog` against the grammar above — does **not** succeed. The failure is distinguishable from a successful empty set of parses.
- A chart parser given an empty token list against a grammar whose start symbol cannot expand to the empty string yields an empty set of parses.

**Verifiable oracle:**

- Success: a chart parser on the fourteen-production grammar parses `the cat chased the dog` as exactly one S tree with those leaves; the eight-token rug sentence has at least two parses that differ in PP attachment; `dog cat the` has zero parses; generation from A=`a` and B=`b` or empty yields both the two-token and the empty-B outcomes; the bracketed S-I-saw-him text equals the constructed tree and pretty-prints those labels and leaves; changing a label breaks equality; a string passed as the child list is refused; an out-of-lexicon token is refused, distinct from a successful empty set of parses.
- Failure / absence: every token list yields one dummy tree; ambiguity is collapsed to a single tree; ungrammatical input still yields a tree; bracketed text is not read; trees with different labels compare equal; generation ignores empty productions.

---

### FP-06: Text classification

**Public entry:** LINGORA’s Naive Bayes classifier and decision tree classifier. The caller supplies a training list of labeled featuresets. After training, the caller asks for a label, and (for Naive Bayes) for a probability distribution over labels. An accuracy helper compares a classifier’s labels on a test list to the gold labels.

This feature point does not require a downloaded corpus. The caller builds featuresets in memory.

**Normal behavior:**

- Training a Naive Bayes classifier on two examples — one featureset in which the features named nice and good are present, labeled positive; one featureset in which the features named bad and mean are present, labeled negative — then classifying a featureset in which only nice is present, yields the label positive. The probability assigned to positive is strictly greater than the probability assigned to negative.
- The same trained classifier, given a featureset in which only bad is present, yields the label negative, and the probability of negative is strictly greater than the probability of positive.
- A feature name that never occurred in training is ignored: adding a never-seen feature to the nice-only featureset does not flip the label from positive to negative and does not make every label probability zero.
- Training a decision tree classifier on the same two labeled featuresets, then classifying the featureset in which nice and good are present, yields positive; classifying the featureset in which bad and mean are present yields negative.
- Accuracy of a classifier that labels three test examples as positive, positive, negative against gold labels positive, negative, negative is two thirds (two of three positions match). Accuracy is a fraction of positions, not of unique labels.
- The trained Naive Bayes classifier can list its labels; the list contains positive and negative and does not contain a third training label that was never seen.

**Boundary / error behavior:**

- Classifying with a featureset that is empty of every training feature still returns one of the trained labels. It does not refuse the call and does not return a label that was not in training.
- Accuracy on two lists of different lengths does not succeed. Accuracy on two lists of the same length succeeds and is the fraction of matching positions.
- This feature point is not satisfied by a function that always returns the first training label regardless of the featureset. An observer who swaps the nice-only and bad-only queries on the trained Naive Bayes classifier must see the two labels swap.

**Verifiable oracle:**

- Success: after the two-example training, nice-only is positive with a higher probability than negative; bad-only is negative with a higher probability than positive; a never-seen feature does not zero all probabilities or flip nice-only to negative; a decision tree trained on the same data labels the nice-and-good featureset positive and the bad-and-mean featureset negative; accuracy of positive/positive/negative against positive/negative/negative is two thirds; mismatched-length accuracy fails; swapping the two Naive Bayes queries swaps the labels.
- Failure / absence: every featureset gets the same label; probabilities are missing or do not rank the two labels as named; unseen features make the classifier fail closed (all probabilities zero) or throw away the example; a decision tree cannot be trained from the same labeled featuresets; accuracy ignores order and only compares bags of labels.

---

### FP-07: Evaluation metrics

**Public entry:** LINGORA’s scoring entries for **Levenshtein edit distance** (with an optional transposition edit), **Jaccard distance**, **accuracy**, **precision**, **recall**, **f-measure**, and **BLEU** (a candidate token list scored against one or more reference token lists, with caller-chosen n-gram weights and an optional smoothing function).

These metrics are pure functions of the arguments the caller supplies. They do not require a downloaded corpus or a trained model.

**Normal behavior:**

- Edit distance between `rain` and `shine`, with substitution cost 1 and transpositions off, is 3. The same pair with substitution cost 2 is 5.
- Edit distance between `abc` and `ca` with transpositions **off** is 3; with transpositions **on** it is 2. An observer can tell the two modes apart on this pair.
- Edit distance between `acbdef` and `abcdef` is 2 with transpositions off and 1 with transpositions on.
- Edit distance between a string and itself is 0. Edit distance is symmetric on `rain` and `shine`.
- Jaccard distance between two identical sets is 0. Jaccard distance between two disjoint non-empty sets is 1. Jaccard distance between `{1, 2, 3}` and `{2, 3, 4}` is one half (the symmetric difference has two elements, the union has four).
- Accuracy of the list 1, 2, 3 against the list 1, 2, 4 is two thirds. Accuracy of a list against itself is 1.
- Precision of the reference set `{1, 2, 3}` against the test set `{2, 3, 4}` is two thirds (two of the three test elements are in the reference). Recall of that same pair is two thirds (two of the three reference elements are in the test). The f-measure of that pair, with equal weight on precision and recall, is two thirds.
- BLEU computed with **only unigram** weight, of the candidate `John loves Mary` against a reference that shares no token with it, is 0. BLEU with only unigram weight, of a candidate that is identical to its only reference, is 1.
- BLEU computed with the default equal weights on unigrams through 4-grams and **without** smoothing, of a two-token candidate that is identical to its only reference, is 0 to four decimal places. An observer can tell that default from unigram-only BLEU on the same pair: unigram-only is 1; default unsmoothed four-weight is 0 to four decimal places.
- BLEU of the long candidate `It is a guide to action which ensures that the military always obeys the commands of the party` against these three reference token lists — `It is a guide to action that ensures that the military will forever heed Party commands`; `It is the guiding principle which guarantees the military forces always being under the command of the Party`; and `It is the practical guide for the army always to heed the directions of the party` — is a score strictly between 0 and 1, and is strictly greater than BLEU of the poorer candidate `It is to insure the troops forever hearing the activity guidebook that party direct` against the same three references.

**Boundary / error behavior:**

- Accuracy on two lists of different lengths does not succeed.
- Precision and recall require sets. Passing lists (or other non-set collections) does not succeed.
- Precision of a non-empty reference against an **empty** test set is absent (no number is returned). Recall of an **empty** reference against a non-empty test set is absent. F-measure is absent when either side is empty. These absences are distinguishable from the number 0, which is what f-measure returns when both sets are non-empty and their intersection is empty.
- Edit distance of two empty strings is 0.

**Verifiable oracle:**

- Success: `rain`/`shine` is 3 at substitution cost 1 and 5 at cost 2; `abc`/`ca` is 3 without transpositions and 2 with them; self-distance is 0; Jaccard of identical sets is 0, of disjoint sets is 1, of `{1,2,3}` vs `{2,3,4}` is one half; accuracy of 1,2,3 vs 1,2,4 is two thirds; precision and recall of `{1,2,3}` vs `{2,3,4}` are two thirds; empty-test precision is absent, not 0; empty-vs-disjoint f-measure is 0 when both sets are non-empty and disjoint; unigram BLEU is 0 on no overlap and 1 on identity; default unsmoothed four-weight BLEU is 0 to four decimal places on a two-token identity; the long guide-to-action candidate scores higher than the insure-the-troops candidate against the three fully written references named above; mismatched-length accuracy fails; precision on lists fails.
- Failure / absence: distances ignore transpositions; Jaccard is reported as a count instead of a distance; accuracy treats bags not sequences; empty-test precision is 0; default BLEU on a two-token identity is 1; the two guide-to-action candidates receive the same score; a list is silently accepted where a set is required.

---

## Out of graded scope (present in the product, not a feature point)

The following surfaces exist in LINGORA and are intentionally **not** independent feature points in this medium-tier PRD. Later stages must not treat them as missing core capabilities, and must not treat a stub of them as satisfying FP-01 through FP-07.

- Packaged corpora, WordNet, the data finder, and the downloader (including the downloader graphical interface).
- Graphical applications and tree/table drawing.
- Chat, Twitter, Hugging Face, and Toolbox helpers.
- External-binary wrappers (Stanford, Senna, Hunpos, Malt, Bllip, CoreNLP, Weka, MEGAM, TADM).
- Combinatory categorial grammar, discourse representation, glue semantics, and inference against Prover9 or Mace.
- N-gram language models, collocation finders, concordance over a Text object, and sentiment lexicons (including VADER).
- Optional machine-learning extras (CRF, scikit-learn wrapper) that are not required for Naive Bayes or the decision tree.
