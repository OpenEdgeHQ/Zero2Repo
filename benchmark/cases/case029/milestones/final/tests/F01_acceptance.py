# feature: F01
"""Word, punctuation, and sentence tokenization (FP-01).

Assertions stay at the PRD's precision: named token lists and family
contrasts, present-model sentence and command-line writes, and
missing-model refusal distinguishable from a successful empty list.
Exception types, exit-code numbers, and stderr wording are not pinned.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

from lingora.cli import cli
from lingora.tokenize import (
    RegexpTokenizer,
    TreebankWordTokenizer,
    TweetTokenizer,
    WhitespaceTokenizer,
    WordPunctTokenizer,
    blankline_tokenize,
    sent_tokenize,
    word_tokenize,
    wordpunct_tokenize,
)

from _harness import call, run_python, workspace
from _helpers import (
    assert_spans_recover,
    bound_resource_path,
    cli_output_lines,
    install_english_punkt,
    require_cli_non_success,
    require_unsuccessful,
    tokens_of,
)

# Public command-line tokenize entry, run in a child so a progress-bar
# teardown on a closed stream cannot replace the process status. The
# search list is emptied before main so a host model cannot satisfy the
# missing-asset arm.
_CLI_TOKENIZE_NO_MODELS = (
    "from lingora import data\n"
    "data.path[:] = []\n"
    "from lingora.cli import cli\n"
    "cli.main(args=['tokenize'], standalone_mode=True)\n"
)

HELLO = "Hello, world!"
HELLO_TOKENS = ["Hello", ",", "world", "!"]
HELLO_JOINED = "Hello , world !"

MUFFIN = "Good muffins cost $3.88 in New York."
WP_MUFFIN = [
    "Good",
    "muffins",
    "cost",
    "$",
    "3",
    ".",
    "88",
    "in",
    "New",
    "York",
    ".",
]

PLEASE_BUY = "Please buy me two of them."
THANKS = "Thanks."
THREE_SENT = f"{MUFFIN} {PLEASE_BUY} {THANKS}"

THEYLL = "They'll save and invest more."
THEYLL_TOKENS = ["They", "'ll", "save", "and", "invest", "more", "."]

CANNOT_LINE = "I cannot cannot work under these conditions!"

MORTGAGE = (
    "On a $50,000 mortgage of 30 years at 8 percent, "
    "the monthly payment would be $366.88."
)
SLOCUM = '"We beat some pretty good teams to get here," Slocum said.'

HOMEPAGE = "At eight o'clock on Thursday morning Arthur didn't feel very good."
HOMEPAGE_TOKENS = [
    "At",
    "eight",
    "o'clock",
    "on",
    "Thursday",
    "morning",
    "Arthur",
    "did",
    "n't",
    "feel",
    "very",
    "good",
    ".",
]
HOMEPAGE_JOINED = " ".join(HOMEPAGE_TOKENS)

WS_TWO_LINE = "Good muffins cost $3.88\nin New York. Please buy me two of them."
BLANK_FIRST = "Good muffins cost $3.88 in New York. Please buy me two of them."
BLANK_TEXT = f"{BLANK_FIRST}\n\n{THANKS}"

REGEXP_MUFFIN = (
    "Good muffins cost $3.88 in New York. Please buy me two of them. Thanks."
)
REGEXP_CAPS = ["Good", "New", "York", "Please", "Thanks"]
CAP_PATTERN = r"[A-Z]\w+"
GAP_PATTERN = r"\s+"

TWEET = "@myke: Let's test these words: resumé España München français"

CAPITALIZED = RegexpTokenizer(CAP_PATTERN).tokenize
GAP_WHITESPACE = RegexpTokenizer(GAP_PATTERN, gaps=True).tokenize
TREEBANK = TreebankWordTokenizer().tokenize
WORDPUNCT_SPANS = WordPunctTokenizer().span_tokenize
WHITESPACE = WhitespaceTokenizer().tokenize
BLANKLINE = blankline_tokenize
TWEET_STRIP = TweetTokenizer(strip_handles=True, reduce_len=True).tokenize


def _word() -> str:
    return "k" + uuid.uuid4().hex[:8]


def _runtime_currency_parts() -> tuple[str, str, str, str, str, str]:
    """Dollar amount that is not 3.88 and not two-digits.two-digits."""
    n = uuid.uuid4().int
    whole = str(100 + (n % 9000))
    frac = str(n % 10)
    amount = f"{whole}.{frac}"
    sentence = f"Pay ${amount} today."
    print(f"runtime currency sentence={sentence!r}", flush=True)
    return sentence, "$", whole, ".", frac, amount


def _runtime_grouped_amount() -> tuple[str, str]:
    """Grouped amount that is not the literal 50,000."""
    n = uuid.uuid4().int
    left = 10 + (n % 40)
    right = 100 + (n % 900)
    grouped = f"{left},{right}"
    sentence = f"Cost ${grouped} total."
    print(f"runtime grouped sentence={sentence!r}", flush=True)
    return sentence, grouped


@contextmanager
def _empty_resources():
    """No packaged models on the search list (already-delimited paths)."""
    with workspace() as ws:
        with bound_resource_path(ws, present=False):
            yield ws


@contextmanager
def _english_models():
    """Copy the host English sentence model into the workspace search list."""
    with workspace() as ws:
        install_english_punkt(ws)
        with bound_resource_path(ws, present=True):
            yield ws


def _cli_tokenize_with_data(data_dir: str) -> str:
    """Child main: bind the search list, then run command-line tokenize."""
    return (
        "from lingora import data\n"
        f"data.path[:] = [{data_dir!r}]\n"
        "from lingora.cli import cli\n"
        "cli.main(args=['tokenize'], standalone_mode=True)\n"
    )


def _recommended_line(text: str) -> list[str]:
    return tokens_of(word_tokenize, text, preserve_line=True)


# ---------------------------------------------------------------------------
# A. Word/punctuation: Hello and muffin decimal split
# ---------------------------------------------------------------------------


def test_wordpunct_hello_world_is_four_tokens():
    with _empty_resources():
        tokens = tokens_of(wordpunct_tokenize, HELLO)
    print(f"wordpunct hello={tokens!r}", flush=True)
    assert tokens == HELLO_TOKENS


def test_wordpunct_muffin_is_eleven_tokens_and_splits_decimal():
    with _empty_resources():
        tokens = tokens_of(wordpunct_tokenize, MUFFIN)
    print(f"wordpunct muffin={tokens!r}", flush=True)
    assert tokens == WP_MUFFIN
    assert tokens.count("$") == 1
    assert tokens.count("3") >= 1
    assert tokens.count("88") >= 1
    assert tokens[-1] == "."


def test_wordpunct_runtime_currency_splits_decimal():
    sentence, dollar, whole, point, frac, amount = _runtime_currency_parts()
    with _empty_resources():
        tokens = tokens_of(wordpunct_tokenize, sentence)
    print(f"wordpunct runtime={tokens!r}", flush=True)
    assert dollar in tokens
    assert whole in tokens
    assert point in tokens
    assert frac in tokens
    assert amount not in tokens


# ---------------------------------------------------------------------------
# B. Two families distinguishable; Treebank clitic; recommended cannot
# ---------------------------------------------------------------------------


def test_treebank_and_recommended_keep_muffin_decimal_unlike_wordpunct():
    with _empty_resources():
        wp = tokens_of(wordpunct_tokenize, MUFFIN)
        tb = tokens_of(TREEBANK, MUFFIN)
        rec = _recommended_line(MUFFIN)
    print(f"wp={wp!r} tb={tb!r} rec={rec!r}", flush=True)
    assert "3" in wp and "." in wp and "88" in wp
    assert "3.88" not in wp
    assert "3.88" in tb and "$" in tb
    assert "3.88" in rec and "$" in rec
    assert wp != tb
    assert wp != rec


def test_treebank_and_recommended_keep_runtime_decimal_unlike_wordpunct():
    sentence, dollar, whole, point, frac, amount = _runtime_currency_parts()
    with _empty_resources():
        wp = tokens_of(wordpunct_tokenize, sentence)
        tb = tokens_of(TREEBANK, sentence)
        rec = _recommended_line(sentence)
    print(f"runtime wp={wp!r} tb={tb!r} rec={rec!r}", flush=True)
    assert dollar in wp and whole in wp and point in wp and frac in wp
    assert amount not in wp
    assert amount in tb and dollar in tb
    assert amount in rec and dollar in rec


def test_treebank_theyll_splits_clitic():
    with _empty_resources():
        tokens = tokens_of(TREEBANK, THEYLL)
    print(f"treebank theyll={tokens!r}", flush=True)
    assert tokens == THEYLL_TOKENS


def test_treebank_runtime_ll_clitic_splits():
    host = _word()
    rest = _word()
    sentence = f"{host}'ll {rest}."
    with _empty_resources():
        tokens = tokens_of(TREEBANK, sentence)
    print(f"treebank runtime ll sentence={sentence!r} tokens={tokens!r}", flush=True)
    assert "'ll" in tokens
    assert f"{host}'ll" not in tokens


def test_recommended_cannot_splits_each_into_can_not():
    with _empty_resources():
        tokens = _recommended_line(CANNOT_LINE)
    print(f"recommended cannot={tokens!r}", flush=True)
    assert "cannot" not in tokens
    joined = " ".join(tokens)
    assert joined.count("can not") >= 2
    pairs = list(zip(tokens, tokens[1:]))
    assert pairs.count(("can", "not")) == 2


def test_recommended_runtime_cannot_splits():
    left = _word()
    right = _word()
    sentence = f"{left} cannot {right}."
    with _empty_resources():
        tokens = _recommended_line(sentence)
    print(f"recommended runtime cannot sentence={sentence!r} tokens={tokens!r}", flush=True)
    assert "cannot" not in tokens
    assert ("can", "not") in list(zip(tokens, tokens[1:]))


# ---------------------------------------------------------------------------
# C. Recommended word tokenizer on already-delimited lines (no Punkt)
# ---------------------------------------------------------------------------


def test_recommended_mortgage_keeps_grouped_and_decimal_amounts():
    with _empty_resources():
        tokens = _recommended_line(MORTGAGE)
    print(f"recommended mortgage={tokens!r}", flush=True)
    assert "50,000" in tokens
    assert "366.88" in tokens
    assert tokens.count("$") == 2
    assert "," in tokens
    assert tokens[-1] == "."
    assert "mortgage" in tokens or "payment" in tokens or "years" in tokens


def test_recommended_runtime_grouped_and_decimal_amounts():
    grouped_sentence, grouped = _runtime_grouped_amount()
    decimal_sentence, dollar, whole, point, frac, amount = _runtime_currency_parts()
    with _empty_resources():
        grouped_tokens = _recommended_line(grouped_sentence)
        decimal_tokens = _recommended_line(decimal_sentence)
    print(
        f"grouped={grouped_tokens!r} decimal={decimal_tokens!r}",
        flush=True,
    )
    assert grouped in grouped_tokens
    assert "$" in grouped_tokens
    assert amount in decimal_tokens
    assert dollar in decimal_tokens


def test_recommended_leading_straight_quote_becomes_backticks():
    with _empty_resources():
        tokens = _recommended_line(SLOCUM)
    print(f"recommended slocum={tokens!r}", flush=True)
    assert "``" in tokens
    assert "''" in tokens


def test_recommended_runtime_leading_quote_rewritten():
    body = _word()
    name = "Q" + uuid.uuid4().hex[:6]
    sentence = f'"{body}," {name} said.'
    with _empty_resources():
        tokens = _recommended_line(sentence)
    print(f"recommended runtime quote sentence={sentence!r} tokens={tokens!r}", flush=True)
    assert "``" in tokens
    assert "''" in tokens
    assert '"' not in tokens


def test_recommended_homepage_thirteen_tokens_without_sentence_split():
    with _empty_resources():
        tokens = _recommended_line(HOMEPAGE)
    print(f"recommended homepage={tokens!r}", flush=True)
    assert tokens == HOMEPAGE_TOKENS
    assert "o'clock" in tokens
    assert "didn't" not in tokens
    assert ("did", "n't") in list(zip(tokens, tokens[1:]))


def test_recommended_runtime_oclock_and_nt_without_sentence_split():
    left = _word()
    right = _word()
    sentence = f"{left} o'clock {right} didn't leave."
    with _empty_resources():
        tokens = _recommended_line(sentence)
    print(f"recommended runtime oclock sentence={sentence!r} tokens={tokens!r}", flush=True)
    assert "o'clock" in tokens
    assert "didn't" not in tokens
    assert ("did", "n't") in list(zip(tokens, tokens[1:]))


# ---------------------------------------------------------------------------
# D. Whitespace and blank-line tokenizers
# ---------------------------------------------------------------------------


def test_whitespace_keeps_currency_and_york_period():
    with _empty_resources():
        tokens = tokens_of(WHITESPACE, WS_TWO_LINE)
        wp = tokens_of(wordpunct_tokenize, MUFFIN)
    print(f"whitespace={tokens!r} wordpunct muffin={wp!r}", flush=True)
    assert "$3.88" in tokens
    assert "York." in tokens
    assert "$3.88" not in wp
    assert any(tok == "$" for tok in wp)


def test_whitespace_runtime_keeps_currency_and_word_period():
    n = uuid.uuid4().int
    whole = 100 + (n % 9000)
    frac = n % 10
    amount = f"${whole}.{frac}"
    host = _word()
    word_period = f"{host}."
    third = _word()
    text = f"{amount} here\n{word_period} {third}"
    with _empty_resources():
        tokens = tokens_of(WHITESPACE, text)
    print(f"whitespace runtime text={text!r} tokens={tokens!r}", flush=True)
    assert amount in tokens
    assert word_period in tokens
    assert third in tokens
    assert not any(amount != tok and amount in tok for tok in tokens)
    assert not any(word_period != tok and word_period in tok for tok in tokens)


def test_blankline_muffin_paragraph_and_thanks():
    with _empty_resources():
        segments = tokens_of(BLANKLINE, BLANK_TEXT)
    print(f"blankline={segments!r}", flush=True)
    assert segments == [BLANK_FIRST, THANKS]


def test_blankline_runtime_paragraphs():
    first = "Para " + uuid.uuid4().hex
    second = "End " + uuid.uuid4().hex + "."
    text = f"{first}\n\n{second}"
    with _empty_resources():
        segments = tokens_of(BLANKLINE, text)
    print(f"blankline runtime text={text!r} segments={segments!r}", flush=True)
    assert segments == [first, second]


# ---------------------------------------------------------------------------
# E. Caller-configured regular-expression tokenizer
# ---------------------------------------------------------------------------


def test_regexp_capitalized_words_on_muffin_string():
    with _empty_resources():
        tokens = tokens_of(CAPITALIZED, REGEXP_MUFFIN)
    print(f"regexp caps={tokens!r}", flush=True)
    assert tokens == REGEXP_CAPS
    assert "muffins" not in tokens
    assert "cost" not in tokens


def test_regexp_runtime_capitalized_word_included():
    cap = "Z" + uuid.uuid4().hex[:8]
    low = "q" + uuid.uuid4().hex[:8]
    text = f"{REGEXP_MUFFIN} {cap} {low}"
    with _empty_resources():
        tokens = tokens_of(CAPITALIZED, text)
    print(f"regexp runtime text={text!r} tokens={tokens!r}", flush=True)
    assert cap in tokens
    assert low not in tokens


def test_regexp_gap_mode_no_empty_tokens_at_whitespace_ends():
    left = _word()
    right = _word()
    text = f"  {left}   {right}  "
    with _empty_resources():
        tokens = tokens_of(GAP_WHITESPACE, text)
    print(f"regexp gap text={text!r} tokens={tokens!r}", flush=True)
    assert left in tokens
    assert right in tokens
    assert "" not in tokens
    assert tokens[0] != ""
    assert tokens[-1] != ""


# ---------------------------------------------------------------------------
# F. Tweet: strip handle, keep accents
# ---------------------------------------------------------------------------


def test_tweet_strips_myke_keeps_colon_lets_and_accents():
    with _empty_resources():
        tokens = tokens_of(TWEET_STRIP, TWEET)
    print(f"tweet={tokens!r}", flush=True)
    assert "@myke" not in tokens
    assert ":" in tokens
    assert "Let's" in tokens
    assert "resumé" in tokens
    assert "España" in tokens
    assert "München" in tokens
    assert "français" in tokens


def test_tweet_runtime_handle_stripped_accent_kept():
    handle = "@u" + uuid.uuid4().hex[:6]
    accent = "café"
    text = f"{handle}: hello {accent}"
    with _empty_resources():
        tokens = tokens_of(TWEET_STRIP, text)
    print(f"tweet runtime text={text!r} tokens={tokens!r}", flush=True)
    assert handle not in tokens
    assert accent in tokens


# ---------------------------------------------------------------------------
# G. Spans recover tokens, ordered, non-overlapping
# ---------------------------------------------------------------------------


def test_spans_on_muffin_recover_tokens_ordered_and_nonoverlapping():
    with _empty_resources():
        tokens = tokens_of(wordpunct_tokenize, MUFFIN)
        result = call(WORDPUNCT_SPANS, MUFFIN)
    print(f"muffin tokens={tokens!r}", flush=True)
    if result.exception is not None:
        raise AssertionError(
            "span extraction failed: "
            f"{type(result.exception).__name__}: {result.exception}"
        )
    spans = list(result.value)
    print(f"muffin spans={spans!r}", flush=True)
    assert tokens == WP_MUFFIN
    assert_spans_recover(MUFFIN, tokens, spans)


def test_spans_on_runtime_currency_recover_tokens():
    sentence, dollar, whole, point, frac, amount = _runtime_currency_parts()
    with _empty_resources():
        tokens = tokens_of(wordpunct_tokenize, sentence)
        result = call(WORDPUNCT_SPANS, sentence)
    print(f"runtime span tokens={tokens!r}", flush=True)
    if result.exception is not None:
        raise AssertionError(
            "span extraction failed: "
            f"{type(result.exception).__name__}: {result.exception}"
        )
    spans = list(result.value)
    print(f"runtime spans={spans!r}", flush=True)
    assert dollar in tokens and whole in tokens and point in tokens and frac in tokens
    assert amount not in tokens
    assert_spans_recover(sentence, tokens, spans)


# ---------------------------------------------------------------------------
# H. With the English sentence-boundary model: three muffin sentences;
# recommended word tokenizer with sentence splitting does not glue clauses
# ---------------------------------------------------------------------------


def test_recommended_sentence_tokenizer_three_muffin_sentences():
    with _english_models():
        sentences = tokens_of(sent_tokenize, THREE_SENT)
    print(f"sentences={sentences!r}", flush=True)
    assert sentences == [MUFFIN, PLEASE_BUY, THANKS]


def test_recommended_sentence_tokenizer_same_atoms_other_order():
    permuted = f"{THANKS} {MUFFIN} {PLEASE_BUY}"
    with _english_models():
        sentences = tokens_of(sent_tokenize, permuted)
    print(f"permuted={permuted!r} sentences={sentences!r}", flush=True)
    assert sentences == [THANKS, MUFFIN, PLEASE_BUY]


def test_recommended_sentence_tokenizer_single_atom_is_one_sentence():
    with _english_models():
        sentences = tokens_of(sent_tokenize, THANKS)
    print(f"single={sentences!r}", flush=True)
    assert sentences == [THANKS]


def test_recommended_word_with_sentence_split_three_points_no_glue():
    with _english_models():
        tokens = tokens_of(word_tokenize, THREE_SENT, preserve_line=False)
    print(f"word-split tokens={tokens!r}", flush=True)
    assert tokens.count(".") == 3
    glued = [tok for tok in tokens if "York." in tok and "Please" in tok]
    assert glued == [], f"York. glued to Please in {glued!r}"
    assert "Please" in tokens
    assert "muffins" in tokens
    assert "buy" in tokens


# ---------------------------------------------------------------------------
# I. Without the English sentence-boundary model: sentence paths fail;
# word/punctuation still works.
# ---------------------------------------------------------------------------


def test_sentence_split_fails_without_punkt_wordpunct_still_works():
    with _empty_resources():
        sent = call(sent_tokenize, THREE_SENT)
        wp = tokens_of(wordpunct_tokenize, HELLO)
    print(f"missing-punkt sent exception={sent.exception!r} wp={wp!r}", flush=True)
    require_unsuccessful(sent)
    assert wp == HELLO_TOKENS


def test_recommended_word_sentence_split_fails_without_punkt():
    with _empty_resources():
        result = call(word_tokenize, THREE_SENT, preserve_line=False)
        wp = tokens_of(wordpunct_tokenize, HELLO)
    print(
        f"missing-punkt word-split exception={result.exception!r} wp={wp!r}",
        flush=True,
    )
    require_unsuccessful(result)
    assert wp == HELLO_TOKENS


def test_cli_tokenize_fails_without_punkt():
    main = getattr(cli, "main", None)
    if not callable(main):
        raise AssertionError("command-line group has no public main entry")
    with workspace() as ws:
        result = ws.run_python(code=_CLI_TOKENIZE_NO_MODELS, stdin=HELLO + "\n")
    print(
        f"missing-punkt cli status={result.returncode} stdout={result.stdout!r}",
        flush=True,
    )
    require_cli_non_success(result, success_line=HELLO_JOINED)
    lines = cli_output_lines(result)
    assert result.returncode != 0
    assert HELLO_JOINED not in lines


# ---------------------------------------------------------------------------
# J. Command-line tokenize with models: one output line per input line
# ---------------------------------------------------------------------------


def test_cli_tokenize_hello_world_joined_by_spaces():
    main = getattr(cli, "main", None)
    if not callable(main):
        raise AssertionError("command-line group has no public main entry")
    with _english_models() as ws:
        result = ws.run_python(
            code=_cli_tokenize_with_data(str(ws.data)),
            stdin=HELLO + "\n",
        )
    lines = cli_output_lines(result)
    print(
        f"cli hello status={result.returncode} lines={lines!r}",
        flush=True,
    )
    assert HELLO_JOINED in lines
    assert HELLO not in lines


def test_cli_one_output_line_per_nonempty_input_line():
    main = getattr(cli, "main", None)
    if not callable(main):
        raise AssertionError("command-line group has no public main entry")
    one_in = HELLO + "\n"
    two_in = HELLO + "\n" + HOMEPAGE + "\n"
    with _english_models() as ws:
        code = _cli_tokenize_with_data(str(ws.data))
        one = ws.run_python(code=code, stdin=one_in)
        two = ws.run_python(code=code, stdin=two_in)
    one_lines = cli_output_lines(one)
    two_lines = cli_output_lines(two)
    print(f"cli one={one_lines!r} two={two_lines!r}", flush=True)
    assert one_lines == [HELLO_JOINED]
    assert two_lines == [HELLO_JOINED, HOMEPAGE_JOINED]
    assert len(two_lines) == 2


# ---------------------------------------------------------------------------
# K. Empty / spaces-only; library-substrate negative control
# ---------------------------------------------------------------------------


def test_empty_string_empty_list_on_named_tokenizers():
    with _empty_resources():
        wp = tokens_of(wordpunct_tokenize, "")
        tb = tokens_of(TREEBANK, "")
        ws_tok = tokens_of(WHITESPACE, "")
        rx = tokens_of(CAPITALIZED, "")
    print(f"empty wp={wp!r} tb={tb!r} ws={ws_tok!r} rx={rx!r}", flush=True)
    assert wp == []
    assert tb == []
    assert ws_tok == []
    assert rx == []


def test_spaces_only_empty_list_on_wordpunct_and_whitespace():
    spaces = "   "
    with _empty_resources():
        wp = tokens_of(wordpunct_tokenize, spaces)
        ws_tok = tokens_of(WHITESPACE, spaces)
    print(f"spaces wp={wp!r} ws={ws_tok!r}", flush=True)
    assert wp == []
    assert ws_tok == []


def test_wordpunct_fails_when_package_not_importable():
    four_repr = repr(HELLO_TOKENS)
    probe = (
        "from lingora.tokenize import wordpunct_tokenize\n"
        f"print('TOKENS=' + repr(wordpunct_tokenize({HELLO!r})))\n"
    )
    missing = run_python(code=probe, include_product=False)
    print(
        f"absent rc={missing.returncode} out={missing.stdout!r} err={missing.stderr!r}",
        flush=True,
    )
    absent_out = missing.stdout_text
    assert f"TOKENS={four_repr}" not in absent_out, (
        "word/punctuation tokenization produced the four-token list "
        "with the package not importable"
    )
    present = run_python(code=probe, include_product=True)
    print(
        f"present rc={present.returncode} out={present.stdout!r} err={present.stderr!r}",
        flush=True,
    )
    assert f"TOKENS={four_repr}" in present.stdout_text
