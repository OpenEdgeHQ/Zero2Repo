# feature: F04
"""FP-04: URLPattern matching (C++ library; caller supplies the engine)."""

from __future__ import annotations

from _helpers import (
    compile_url_pattern,
    match_url_pattern,
    try_url_pattern_without_linked_library,
    unique_digits,
    unique_letters,
    unique_token,
    url_pattern_probe_has_named_books_id,
)

BOOKS_ID = "/books/:id"
HTTPS_BASE = "https://example.com"
HTTP_BASE = "http://example.com"
NAMED_BOOKS_URL = "https://example.com/books/123"
NAMED_BOOKS_HTTP = "http://example.com/books/123"
NAMED_BOOKS_ABC = "https://example.com/books/abc"

DIGITS_ONLY = "[0-9]+"
LETTERS_ONLY = "[A-Za-z]+"


def _print_compile(label: str, compiled) -> None:
    print(
        f"{label} ok={compiled.ok} regexp={compiled.has_regexp_groups} "
        f"path_pat={compiled.pathname!r} prot_pat={compiled.protocol!r} "
        f"host_pat={compiled.hostname!r} stderr={compiled.stderr!r}"
    )


def _print_match(label: str, match) -> None:
    path_in = None if match.pathname is None else match.pathname.input
    groups = None if match.pathname is None else {
        name: (cap.present, cap.value)
        for name, cap in match.pathname.groups.items()
    }
    print(
        f"{label} compile_ok={match.compile.ok} test={match.test} "
        f"exec={match.exec_matched} path_in={path_in!r} groups={groups} "
        f"stderr={match.stderr!r}"
    )


def _require_compile_ok(compiled, *, what: str):
    assert compiled.ok, (
        f"{what} must compile; stderr={compiled.stderr!r}"
    )
    assert compiled.pathname is not None
    assert compiled.has_regexp_groups is not None
    return compiled


def _require_compile_fail(compiled, *, what: str):
    assert not compiled.ok, (
        f"{what} must fail to compile; pathname={compiled.pathname!r} "
        f"stderr={compiled.stderr!r}"
    )
    assert compiled.pathname is None, (
        f"{what}: failed compile must not expose a pathname pattern; "
        f"got {compiled.pathname!r}"
    )
    assert compiled.has_regexp_groups is None, (
        f"{what}: failed compile must not report regexp-groups; "
        f"got {compiled.has_regexp_groups!r}"
    )
    return compiled


def _require_matched(match, *, what: str, **groups: str):
    assert match.compile.ok, (
        f"{what} compile failed; stderr={match.stderr!r}"
    )
    assert match.test is True, (
        f"{what} test is {match.test!r}, expected True; "
        f"stderr={match.stderr!r}"
    )
    assert match.exec_matched is True, (
        f"{what} execute has no match payload; stderr={match.stderr!r}"
    )
    assert match.pathname is not None, (
        f"{what} MATCH omitted pathname sub-result"
    )
    for name, expected in groups.items():
        cap = match.pathname.groups.get(name)
        assert cap is not None and cap.present, (
            f"{what}: group {name!r} ABSENT; groups={match.pathname.groups!r}"
        )
        assert cap.value == expected, (
            f"{what}: group {name!r}={cap.value!r} expected {expected!r}"
        )
    return match


def _require_nomatch(match, *, what: str):
    assert match.compile.ok, (
        f"{what} compile failed (no-match is not a compile error); "
        f"stderr={match.stderr!r}"
    )
    assert match.test is False, (
        f"{what} test is {match.test!r}, expected False; "
        f"stderr={match.stderr!r}"
    )
    assert match.exec_matched is False, (
        f"{what} execute still produced a match payload; "
        f"path_in={None if match.pathname is None else match.pathname.input!r} "
        f"stderr={match.stderr!r}"
    )
    assert match.pathname is None, (
        f"{what}: EXEC_NONE must not hand a pathname input; "
        f"got {match.pathname!r}"
    )
    return match


def _require_agree(match, *, what: str):
    assert match.test is not None and match.exec_matched is not None, (
        f"{what}: test/exec unset after a successful compile; "
        f"test={match.test!r} exec={match.exec_matched!r}"
    )
    assert match.test is match.exec_matched, (
        f"{what}: test={match.test!r} disagrees with "
        f"exec_matched={match.exec_matched!r}"
    )
    return match


def _require_eight_components(match, *, what: str):
    missing = [
        name
        for name in (
            "protocol",
            "username",
            "password",
            "hostname",
            "port",
            "pathname",
            "search",
            "hash",
        )
        if getattr(match, name) is None
    ]
    assert not missing, (
        f"{what}: successful execute omitted components {missing}"
    )
    return match


def _group(match, name: str) -> object:
    assert match.pathname is not None
    return match.pathname.groups.get(name)


# ---------------------------------------------------------------------------
# A. Compile: pattern string or per-component init, optional base
# ---------------------------------------------------------------------------


def test_compile_books_id_with_base_matches_named_url() -> None:
    named = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input=NAMED_BOOKS_URL
    )
    _print_match("books-id-named", named)
    _require_matched(named, what="named /books/123", id="123")
    _require_agree(named, what="named /books/123")

    digits = unique_digits()
    digit_url = f"https://example.com/books/{digits}"
    digit_match = match_url_pattern(BOOKS_ID, base=HTTPS_BASE, input=digit_url)
    _print_match("books-id-runtime-digits", digit_match)
    _require_matched(digit_match, what=f"runtime digits {digits}", id=digits)
    _require_agree(digit_match, what="runtime digits")

    letters = unique_letters()
    letter_url = f"https://example.com/books/{letters}"
    letter_match = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input=letter_url
    )
    _print_match("books-id-runtime-letters", letter_match)
    _require_matched(
        letter_match, what=f"unconstrained letters {letters}", id=letters
    )
    _require_agree(letter_match, what="unconstrained letters")


def test_pathname_only_compiles_without_base() -> None:
    compiled = compile_url_pattern(components={"pathname": "/:a/:b"})
    _print_compile("pathname-only-no-base", compiled)
    _require_compile_ok(compiled, what="pathname-only /:a/:b without base")
    matched = match_url_pattern(
        components={"pathname": "/:a/:b"},
        input_components={"pathname": "/foo/bar"},
    )
    _print_match("pathname-only-foo-bar", matched)
    _require_matched(matched, what="pathname-only /foo/bar", a="foo", b="bar")


def test_base_fixes_protocol_and_hostname_not_href_equality() -> None:
    success = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input=NAMED_BOOKS_URL
    )
    _print_match("https-base-named-success", success)
    _require_matched(success, what="https base named URL live baseline", id="123")
    _require_agree(success, what="https base named URL live baseline")
    assert success.protocol is not None, (
        "successful execute omitted the protocol sub-result"
    )
    assert success.hostname is not None, (
        "successful execute omitted the hostname sub-result"
    )
    protocol_scheme = success.protocol.input.rstrip(":")
    print(
        f"base-fixed protocol={success.protocol.input!r} "
        f"hostname={success.hostname.input!r}"
    )
    assert protocol_scheme == "https", (
        "base-fixed protocol must participate as https "
        f"(got {success.protocol.input!r})"
    )
    assert success.hostname.input == "example.com", (
        "base-fixed hostname must participate as example.com "
        f"(got {success.hostname.input!r})"
    )

    http_scheme = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input="http://example.com/books/123"
    )
    _print_match("https-base-http-scheme", http_scheme)
    _require_nomatch(http_scheme, what="http scheme against https base")
    _require_agree(http_scheme, what="http scheme against https base")

    other_host = unique_token()
    host_url = f"https://{other_host}.example.com/books/123"
    host_match = match_url_pattern(BOOKS_ID, base=HTTPS_BASE, input=host_url)
    _print_match("https-base-other-host", host_match)
    _require_nomatch(host_match, what=f"host {other_host} against example.com")
    _require_agree(host_match, what="other host")

    missing = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input="https://example.com/books"
    )
    _print_match("https-base-missing-segment", missing)
    _require_nomatch(missing, what="missing /:id segment")
    extra = match_url_pattern(
        BOOKS_ID,
        base=HTTPS_BASE,
        input="https://example.com/books/123/extra",
    )
    _print_match("https-base-extra-segment", extra)
    _require_nomatch(extra, what="extra pathname segment")
    other_prefix = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input="https://example.com/other/123"
    )
    _print_match("https-base-other-prefix", other_prefix)
    _require_nomatch(other_prefix, what="different pathname prefix")


def test_second_base_resolves_relative_pattern() -> None:
    https_arm = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input=NAMED_BOOKS_URL
    )
    http_on_https_input = match_url_pattern(
        BOOKS_ID, base=HTTP_BASE, input=NAMED_BOOKS_URL
    )
    _print_match("https-base-named", https_arm)
    _print_match("http-base-https-input", http_on_https_input)
    _require_matched(https_arm, what="https base named URL", id="123")
    _require_nomatch(
        http_on_https_input, what="http base against https named URL"
    )
    _require_agree(http_on_https_input, what="http base vs https input")
    assert https_arm.test is not http_on_https_input.test, (
        "stripping the two base strings still leaves the yes/no identical; "
        "the second base did not change matching"
    )
    assert https_arm.exec_matched is not http_on_https_input.exec_matched

    http_baseline = match_url_pattern(
        BOOKS_ID, base=HTTP_BASE, input=NAMED_BOOKS_HTTP
    )
    _print_match("http-base-http-input", http_baseline)
    _require_matched(
        http_baseline, what="http base live baseline", id="123"
    )
    _require_agree(http_baseline, what="http base live baseline")


# ---------------------------------------------------------------------------
# B. Named groups bind in order; custom expressions constrain matches
# ---------------------------------------------------------------------------


def test_named_groups_bind_in_order() -> None:
    match = match_url_pattern(
        components={"pathname": "/:a/:b"},
        input_components={"pathname": "/foo/bar"},
    )
    _print_match("named-a-b", match)
    _require_matched(match, what="/:a/:b vs /foo/bar", a="foo", b="bar")
    assert match.pathname.groups["a"].value != "bar"
    assert match.pathname.groups["b"].value != "foo"


def test_three_named_groups_bind_independently() -> None:
    match = match_url_pattern(
        components={"pathname": "/:a/:b/:c"},
        input_components={"pathname": "/x/y/z"},
    )
    _print_match("named-a-b-c", match)
    _require_matched(match, what="/:a/:b/:c vs /x/y/z", a="x", b="y", c="z")


def test_letters_only_custom_group() -> None:
    match = match_url_pattern(
        components={"pathname": f"/:a({LETTERS_ONLY})"},
        input_components={"pathname": "/hello"},
    )
    _print_match("letters-only-hello", match)
    _require_matched(match, what="letters-only /hello", a="hello")


def test_digits_only_custom_group_match_and_reject() -> None:
    accept = match_url_pattern(
        f"/books/:id({DIGITS_ONLY})",
        base=HTTPS_BASE,
        input=NAMED_BOOKS_URL,
    )
    reject = match_url_pattern(
        f"/books/:id({DIGITS_ONLY})",
        base=HTTPS_BASE,
        input=NAMED_BOOKS_ABC,
    )
    _print_match("digits-only-123", accept)
    _print_match("digits-only-abc", reject)
    _require_matched(accept, what="digits-only /books/123", id="123")
    _require_agree(accept, what="digits-only accept")
    _require_nomatch(reject, what="digits-only /books/abc")
    _require_agree(reject, what="digits-only reject")


def test_runtime_named_group_order() -> None:
    first = unique_token()
    second = unique_token()
    assert first != second
    match = match_url_pattern(
        components={"pathname": "/:a/:b"},
        input_components={"pathname": f"/{first}/{second}"},
    )
    _print_match("runtime-order", match)
    _require_matched(
        match, what="runtime /:a/:b order", a=first, b=second
    )


def test_runtime_custom_group_accepts_and_rejects() -> None:
    digits = unique_digits()
    letters = unique_letters()
    digit_ok = match_url_pattern(
        f"/books/:id({DIGITS_ONLY})",
        base=HTTPS_BASE,
        input=f"https://example.com/books/{digits}",
    )
    letter_no = match_url_pattern(
        f"/books/:id({DIGITS_ONLY})",
        base=HTTPS_BASE,
        input=f"https://example.com/books/{letters}",
    )
    _print_match("runtime-digits-accept", digit_ok)
    _print_match("runtime-digits-reject-letters", letter_no)
    _require_matched(digit_ok, what="runtime digits-only accept", id=digits)
    _require_nomatch(letter_no, what="runtime digits-only reject letters")

    letter_ok = match_url_pattern(
        components={"pathname": f"/:a({LETTERS_ONLY})"},
        input_components={"pathname": f"/{letters}"},
    )
    digit_no = match_url_pattern(
        components={"pathname": f"/:a({LETTERS_ONLY})"},
        input_components={"pathname": f"/{digits}"},
    )
    _print_match("runtime-letters-accept", letter_ok)
    _print_match("runtime-letters-reject-digits", digit_no)
    _require_matched(letter_ok, what="runtime letters-only accept", a=letters)
    _require_nomatch(digit_no, what="runtime letters-only reject digits")


def test_custom_expression_hi_constrains_match() -> None:
    accept = match_url_pattern(
        components={"pathname": "/:foo(hi)"},
        input_components={"pathname": "/hi"},
    )
    reject = match_url_pattern(
        components={"pathname": "/:foo(hi)"},
        input_components={"pathname": "/ho"},
    )
    other = unique_letters()
    reject_runtime = match_url_pattern(
        components={"pathname": "/:foo(hi)"},
        input_components={"pathname": f"/{other}"},
    )
    _print_match("hi-accept", accept)
    _print_match("hi-reject-ho", reject)
    _print_match("hi-reject-runtime", reject_runtime)
    _require_matched(accept, what="custom expression hi", foo="hi")
    _require_nomatch(reject, what="twin segment ho against hi")
    _require_nomatch(reject_runtime, what=f"runtime {other} against hi")


# ---------------------------------------------------------------------------
# C. Literal, full wildcard, optional named group; structured result
# ---------------------------------------------------------------------------


def test_full_wildcard_matches_remainder_including_slash() -> None:
    bar = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo/bar"},
    )
    baz = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo/bar/baz"},
    )
    only_foo = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo"},
    )
    _print_match("wild-bar", bar)
    _print_match("wild-bar-baz", baz)
    _print_match("wild-foo", only_foo)
    _require_matched(bar, what="/foo/* vs /foo/bar")
    _require_agree(bar, what="/foo/* vs /foo/bar")
    _require_matched(baz, what="/foo/* vs /foo/bar/baz")
    _require_agree(baz, what="/foo/* vs /foo/bar/baz")
    _require_nomatch(only_foo, what="/foo/* vs /foo")
    _require_agree(only_foo, what="/foo/* vs /foo")


def test_optional_named_group_bound_vs_absent() -> None:
    bound = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": "/foo/bar"},
    )
    absent = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": "/foo"},
    )
    extra = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": "/foo/bar/baz"},
    )
    glued = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": "/foobar"},
    )
    _print_match("optional-bound", bound)
    _print_match("optional-absent", absent)
    _print_match("optional-extra", extra)
    _print_match("optional-glued", glued)
    _require_matched(bound, what="/foo/:bar? vs /foo/bar", bar="bar")
    _require_agree(bound, what="optional bound")
    _require_matched(absent, what="/foo/:bar? vs /foo")
    _require_agree(absent, what="optional absent")
    bound_cap = _group(bound, "bar")
    absent_cap = _group(absent, "bar")
    assert bound_cap is not None and bound_cap.present
    assert absent_cap is None or not absent_cap.present, (
        f"optional /foo still bound bar={absent_cap!r}"
    )
    assert (bound_cap.present, bound_cap.value) != (
        False if absent_cap is None else absent_cap.present,
        None if absent_cap is None else absent_cap.value,
    )
    _require_nomatch(extra, what="/foo/:bar? vs /foo/bar/baz")
    _require_agree(extra, what="optional extra")
    _require_nomatch(glued, what="/foo/:bar? vs /foobar")
    _require_agree(glued, what="optional glued")


def test_literal_pathname_exact() -> None:
    exact = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/foo/bar"},
    )
    other = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/foo/baz"},
    )
    _print_match("literal-exact", exact)
    _print_match("literal-other", other)
    _require_matched(exact, what="literal /foo/bar")
    _require_agree(exact, what="literal exact")
    _require_nomatch(other, what="literal /foo/baz")
    _require_agree(other, what="literal other")


def test_test_agrees_with_execute_on_named_pathnames() -> None:
    cases = (
        ("/foo/*", "/foo/bar", True),
        ("/foo/*", "/foo/bar/baz", True),
        ("/foo/*", "/foo", False),
        ("/foo/:bar?", "/foo/bar", True),
        ("/foo/:bar?", "/foo", True),
        ("/foo/:bar?", "/foo/bar/baz", False),
        ("/foo/:bar?", "/foobar", False),
        ("/foo/bar", "/foo/bar", True),
        ("/foo/bar", "/foo/baz", False),
    )
    for pattern, pathname, should_match in cases:
        match = match_url_pattern(
            components={"pathname": pattern},
            input_components={"pathname": pathname},
        )
        _print_match(f"agree {pattern} {pathname}", match)
        _require_agree(match, what=f"{pattern} vs {pathname}")
        if should_match:
            _require_matched(match, what=f"{pattern} vs {pathname}")
        else:
            _require_nomatch(match, what=f"{pattern} vs {pathname}")


def test_execute_result_has_all_eight_components() -> None:
    bar = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo/bar"},
    )
    baz = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo/bar/baz"},
    )
    _print_match("eight-bar", bar)
    _print_match("eight-baz", baz)
    _require_matched(bar, what="/foo/* /foo/bar")
    _require_matched(baz, what="/foo/* /foo/bar/baz")
    _require_eight_components(bar, what="/foo/bar")
    _require_eight_components(baz, what="/foo/bar/baz")
    assert bar.pathname.input != baz.pathname.input, (
        "two successful /foo/* executes that differ only in pathname "
        "still share the same pathname input field; "
        f"bar={bar.pathname.input!r} baz={baz.pathname.input!r}"
    )


def test_runtime_wildcard_optional_and_literal() -> None:
    token = unique_token()
    other = unique_token()
    assert token != other

    wild_one = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": f"/foo/{token}"},
    )
    wild_two = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": f"/foo/{token}/x"},
    )
    wild_none = match_url_pattern(
        components={"pathname": "/foo/*"},
        input_components={"pathname": "/foo"},
    )
    _print_match("runtime-wild-one", wild_one)
    _print_match("runtime-wild-two", wild_two)
    _print_match("runtime-wild-none", wild_none)
    _require_matched(wild_one, what=f"/foo/* vs /foo/{token}")
    _require_matched(wild_two, what=f"/foo/* vs /foo/{token}/x")
    _require_nomatch(wild_none, what="/foo/* vs /foo runtime")

    opt_bound = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": f"/foo/{token}"},
    )
    opt_absent = match_url_pattern(
        components={"pathname": "/foo/:bar?"},
        input_components={"pathname": "/foo"},
    )
    _print_match("runtime-optional-bound", opt_bound)
    _print_match("runtime-optional-absent", opt_absent)
    _require_matched(
        opt_bound, what=f"/foo/:bar? vs /foo/{token}", bar=token
    )
    _require_matched(opt_absent, what="runtime optional /foo")
    absent_cap = _group(opt_absent, "bar")
    assert absent_cap is None or not absent_cap.present

    lit_ok = match_url_pattern(
        components={"pathname": f"/foo/{token}"},
        input_components={"pathname": f"/foo/{token}"},
    )
    lit_no = match_url_pattern(
        components={"pathname": f"/foo/{token}"},
        input_components={"pathname": f"/foo/{other}"},
    )
    _print_match("runtime-literal-ok", lit_ok)
    _print_match("runtime-literal-no", lit_no)
    _require_matched(lit_ok, what=f"literal /foo/{token}")
    _require_nomatch(lit_no, what=f"literal /foo/{other}")


# ---------------------------------------------------------------------------
# D. Ignore-case is a compile-time choice
# ---------------------------------------------------------------------------


def test_ignore_case_matches_folded_literal() -> None:
    folded = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/FOO/BAR"},
        ignore_case=True,
    )
    sensitive = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/FOO/BAR"},
        ignore_case=False,
    )
    same_case = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/foo/bar"},
        ignore_case=False,
    )
    folded_same = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/foo/bar"},
        ignore_case=True,
    )
    _print_match("ignore-case-folded", folded)
    _print_match("case-sensitive-folded", sensitive)
    _print_match("case-sensitive-baseline", same_case)
    _print_match("ignore-case-same", folded_same)
    _require_matched(folded, what="ignore-case /FOO/BAR")
    _require_nomatch(sensitive, what="default /FOO/BAR")
    _require_matched(same_case, what="default /foo/bar live baseline")
    _require_matched(folded_same, what="ignore-case still matches /foo/bar")
    assert folded.test is not sensitive.test
    assert folded.exec_matched is not sensitive.exec_matched


def test_runtime_ignore_case_contrast() -> None:
    token = unique_letters()
    upper = token.upper()
    assert token != upper
    folded = match_url_pattern(
        components={"pathname": f"/foo/{token}"},
        input_components={"pathname": f"/FOO/{upper}"},
        ignore_case=True,
    )
    sensitive = match_url_pattern(
        components={"pathname": f"/foo/{token}"},
        input_components={"pathname": f"/FOO/{upper}"},
        ignore_case=False,
    )
    _print_match("runtime-ignore-case-on", folded)
    _print_match("runtime-ignore-case-off", sensitive)
    _require_matched(folded, what=f"ignore-case /FOO/{upper}")
    _require_nomatch(sensitive, what=f"default /FOO/{upper}")


# ---------------------------------------------------------------------------
# E. Compiled component pattern strings; regexp-group report
# ---------------------------------------------------------------------------


def test_compiled_pathname_pattern_string_nonempty_and_distinct() -> None:
    named = compile_url_pattern(components={"pathname": "/:a/:b"})
    literal = compile_url_pattern(components={"pathname": "/foo/bar"})
    token = unique_token()
    runtime = compile_url_pattern(components={"pathname": f"/{token}"})
    _print_compile("pat-named", named)
    _print_compile("pat-literal", literal)
    _print_compile("pat-runtime", runtime)
    _require_compile_ok(named, what="/:a/:b")
    _require_compile_ok(literal, what="/foo/bar")
    _require_compile_ok(runtime, what=f"/{token}")
    assert named.pathname, (
        f"/:a/:b left the pathname pattern empty: {named.pathname!r}"
    )
    assert runtime.pathname != named.pathname, (
        f"runtime /{token} pathname pattern equals /:a/:b: "
        f"{runtime.pathname!r}"
    )
    assert runtime.pathname != literal.pathname, (
        f"runtime /{token} pathname pattern equals /foo/bar: "
        f"{runtime.pathname!r}"
    )
    assert named.pathname != literal.pathname, (
        f"/:a/:b and /foo/bar share pathname pattern {named.pathname!r}"
    )


def test_optional_named_group_is_not_regexp_group() -> None:
    compiled = compile_url_pattern(components={"pathname": "/:foo?"})
    _print_compile("optional-foo", compiled)
    _require_compile_ok(compiled, what="/:foo?")
    assert compiled.has_regexp_groups is False, (
        f"/:foo? reported regexp-groups={compiled.has_regexp_groups!r}"
    )


def test_custom_expression_reports_regexp_groups() -> None:
    hi = compile_url_pattern(components={"pathname": "/:foo(hi)"})
    digits = compile_url_pattern(
        components={"pathname": f"/books/:id({DIGITS_ONLY})"}
    )
    letters = compile_url_pattern(
        components={"pathname": f"/:a({LETTERS_ONLY})"}
    )
    literal = compile_url_pattern(components={"pathname": "/foo/bar"})
    named = compile_url_pattern(components={"pathname": "/:a/:b"})
    wild = compile_url_pattern(components={"pathname": "/foo/*"})
    optional = compile_url_pattern(components={"pathname": "/:foo?"})
    _print_compile("re-hi", hi)
    _print_compile("re-digits", digits)
    _print_compile("re-letters", letters)
    _print_compile("re-literal", literal)
    _print_compile("re-named", named)
    _print_compile("re-wild", wild)
    _print_compile("re-optional", optional)
    _require_compile_ok(hi, what=":foo(hi)")
    _require_compile_ok(digits, what="digits-only :id")
    _require_compile_ok(letters, what="letters-only :a")
    assert hi.has_regexp_groups is True, (
        f":foo(hi) reported regexp-groups={hi.has_regexp_groups!r}"
    )
    assert digits.has_regexp_groups is True, (
        f"digits-only reported regexp-groups={digits.has_regexp_groups!r}"
    )
    assert letters.has_regexp_groups is True, (
        f"letters-only reported regexp-groups={letters.has_regexp_groups!r}"
    )
    for compiled, label in (
        (literal, "literal /foo/bar"),
        (named, "named /:a/:b"),
        (wild, "full wildcard /foo/*"),
        (optional, "optional :foo?"),
    ):
        _require_compile_ok(compiled, what=label)
        assert compiled.has_regexp_groups is False, (
            f"{label} reported regexp-groups={compiled.has_regexp_groups!r}"
        )
        assert compiled.has_regexp_groups is not hi.has_regexp_groups


# ---------------------------------------------------------------------------
# F. Compile failure ≠ no-match; pattern string /foo + base; ? completes
# ---------------------------------------------------------------------------


def test_invalid_pattern_compile_fails() -> None:
    compiled = compile_url_pattern(components={"pathname": "/foo/{"})
    _print_compile("invalid-unclosed-brace", compiled)
    _require_compile_fail(compiled, what="unclosed {")
    matched = match_url_pattern(
        components={"pathname": "/foo/{"},
        input_components={"pathname": "/foo/bar"},
    )
    _print_match("invalid-cannot-test", matched)
    assert matched.test is None and matched.exec_matched is None, (
        f"failed compile still produced test={matched.test!r} "
        f"exec={matched.exec_matched!r}"
    )


def test_engine_rejected_custom_regexp_compile_fails() -> None:
    rejected = "/:id([)"
    compiled = compile_url_pattern(components={"pathname": rejected})
    _print_compile("engine-rejected-custom", compiled)
    _require_compile_fail(compiled, what="custom expression the engine rejects")
    matched = match_url_pattern(
        components={"pathname": rejected},
        input_components={"pathname": "/1"},
    )
    _print_match("engine-rejected-cannot-test", matched)
    assert not matched.compile.ok
    assert matched.test is None and matched.exec_matched is None


def test_unusable_engine_compile_fails() -> None:
    failed = compile_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, engine="unusable"
    )
    usable = compile_url_pattern(BOOKS_ID, base=HTTPS_BASE, engine="usable")
    _print_compile("unusable-engine", failed)
    _print_compile("usable-engine-baseline", usable)
    _require_compile_fail(failed, what="unusable engine on /books/:id")
    _require_compile_ok(usable, what="usable engine baseline /books/:id")
    matched = match_url_pattern(
        BOOKS_ID,
        base=HTTPS_BASE,
        input=NAMED_BOOKS_URL,
        engine="unusable",
    )
    assert matched.test is None and matched.exec_matched is None, (
        f"unusable engine still produced test={matched.test!r} "
        f"exec={matched.exec_matched!r}"
    )


def test_nomatch_is_not_compile_error() -> None:
    match = match_url_pattern(
        components={"pathname": "/foo/bar"},
        input_components={"pathname": "/foo/baz"},
    )
    failed = compile_url_pattern(components={"pathname": "/foo/{"})
    _print_match("nomatch-not-compile", match)
    _print_compile("compile-fail-contrast", failed)
    _require_nomatch(match, what="literal /foo/baz")
    _require_agree(match, what="literal /foo/baz")
    _require_compile_fail(failed, what="unclosed { contrast")
    assert match.compile.ok is not failed.ok
    assert match.test is False
    assert match.exec_matched is False


def test_pattern_string_foo_with_base_matches_and_question_completes() -> None:
    foo = match_url_pattern(
        "/foo", base=HTTP_BASE, input="http://example.com/foo"
    )
    other = match_url_pattern(
        "/foo", base=HTTP_BASE, input="http://example.com/bar"
    )
    extra = match_url_pattern(
        "/foo", base=HTTP_BASE, input="http://example.com/foo/x"
    )
    question = match_url_pattern("/foo", base=HTTP_BASE, input="?")
    _print_match("foo-base-foo", foo)
    _print_match("foo-base-bar", other)
    _print_match("foo-base-foo-x", extra)
    _print_match("foo-base-question", question)
    _require_matched(foo, what="/foo + http base vs http://example.com/foo")
    _require_agree(foo, what="/foo exact")
    _require_nomatch(other, what="/foo + http base vs /bar")
    _require_agree(other, what="/foo vs /bar")
    _require_nomatch(extra, what="/foo + http base vs /foo/x")
    _require_agree(extra, what="/foo vs /foo/x")
    assert question.compile.ok, (
        f"matching ? aborted compile; stderr={question.stderr!r}"
    )
    assert question.test in (True, False), (
        f"matching ? did not yield a classified yes/no; test={question.test!r}"
    )
    assert question.exec_matched in (True, False), (
        f"matching ? did not yield MATCH/NONE; exec={question.exec_matched!r}"
    )
    _require_agree(question, what="input ?")


# ---------------------------------------------------------------------------
# G. Negative control
# ---------------------------------------------------------------------------


def test_urlpattern_fail_when_library_absent_from_link_path() -> None:
    baseline = match_url_pattern(
        BOOKS_ID, base=HTTPS_BASE, input=NAMED_BOOKS_URL
    )
    _print_match("unlink-baseline", baseline)
    _require_matched(baseline, what="linked library baseline", id="123")
    kind, result = try_url_pattern_without_linked_library()
    print(f"absent-library kind={kind}")
    assert result is not None
    if kind == "link_failed":
        assert result.returncode != 0
        print(f"link stderr={result.stderr_text[:800]!r}")
        return
    produced = url_pattern_probe_has_named_books_id(result)
    assert not produced, (
        "URLPattern without the recipe library still matched "
        "https://example.com/books/123 with group id=123"
    )
