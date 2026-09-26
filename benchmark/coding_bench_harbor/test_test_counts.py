#!/usr/bin/env python3
"""Unit tests for test_counts.parse_test_counts (pure string parsing)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_counts import parse_test_counts


def _check(out, *, label="", cmd="", passed, total, failed=None, framework=None):
    c = parse_test_counts(out, framework_label=label, test_command=cmd)
    assert c is not None, f"expected a parse for framework={framework!r}"
    assert c.passed == passed, f"{framework}: passed {c.passed} != {passed}"
    assert c.total == total, f"{framework}: total {c.total} != {total}"
    if failed is not None:
        assert c.failed == failed, f"{framework}: failed {c.failed} != {failed}"
    if framework is not None:
        assert c.framework == framework, f"framework {c.framework} != {framework}"
    return c


def test_cargo_single_binary():
    out = "running 89 tests\n...\ntest result: ok. 89 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.20s\n"
    c = _check(out, label="cargo-test (Rust)", passed=89, total=89, failed=0, framework="cargo")
    assert c.pass_rate == 1.0


def test_cargo_multiple_binaries_with_failures():
    out = (
        "test result: ok. 40 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"
        "test result: FAILED. 47 passed; 2 failed; 1 ignored; 0 measured; 0 filtered out\n"
    )
    c = _check(out, cmd="cargo test", passed=87, total=89, failed=2, framework="cargo")
    assert abs(c.pass_rate - 87 / 89) < 1e-9


def test_pytest_all_pass():
    out = "==================== 89 passed in 3.40s ====================\n"
    _check(out, cmd="python -m pytest x.py", passed=89, total=89, framework="pytest")


def test_pytest_mixed():
    out = "============ 1 failed, 88 passed, 2 skipped, 1 error in 5.00s ============\n"
    c = _check(out, label="", cmd="pytest", passed=88, total=90, failed=1, framework="pytest")
    assert c.errors == 1 and c.skipped == 2


def test_dotnet_pass():
    out = "Passed!  - Failed:     0, Passed:    89, Skipped:     0, Total:    89, Duration: 1 s\n"
    _check(out, cmd="dotnet test x --framework net10.0", passed=89, total=89, framework="dotnet")


def test_dotnet_fail_multiproject():
    out = (
        "Failed!  - Failed:     2, Passed:    40, Skipped:     1, Total:    43\n"
        "Passed!  - Failed:     0, Passed:    47, Skipped:     0, Total:    47\n"
    )
    _check(out, cmd="dotnet test", passed=87, total=89, failed=2, framework="dotnet")


def test_flutter_pass():
    out = "00:05 +89: All tests passed!\n"
    _check(out, cmd="flutter test test/a_test.dart", passed=89, total=89, framework="flutter")


def test_flutter_fail():
    out = "00:03 +12 -1: test/foo_test.dart: bar [E]\n00:05 +87 -2: Some tests failed.\n"
    _check(out, cmd="flutter test", passed=87, total=89, failed=2, framework="flutter")


def test_vitest():
    out = " Test Files  1 failed | 3 passed (4)\n      Tests  2 failed | 87 passed (89)\n"
    _check(out, cmd="vitest run", passed=87, total=89, failed=2, framework="vitest")


def test_jest():
    out = "Tests:       2 failed, 87 passed, 89 total\nSnapshots:   0 total\n"
    _check(out, cmd="jest", passed=87, total=89, failed=2, framework="jest")


def test_mocha():
    out = "  89 passing (1s)\n  2 failing\n"
    _check(out, cmd="mocha --reporter spec", passed=89, total=91, failed=2, framework="mocha")


def test_tap_raw_stream():
    out = "TAP version 13\n1..3\nok 1 - a\nnot ok 2 - b\nok 3 - c # SKIP later\n"
    c = _check(out, cmd="tap test/*.js", passed=1, total=2, failed=1, framework="tap")
    assert c.skipped == 1


def test_prove_pass():
    out = "All tests successful.\nFiles=1, Tests=89, 2 wallclock secs\nResult: PASS\n"
    _check(out, cmd="prove t/", passed=89, total=89, failed=0, framework="prove")


def test_prove_fail():
    out = "Failed 3/89 subtests\nFiles=1, Tests=89\nResult: FAIL\n"
    _check(out, cmd="prove t/", passed=86, total=89, failed=3, framework="prove")


def test_ctest():
    out = "100% tests passed, 0 tests failed out of 89\n"
    _check(out, cmd="ctest --test-dir build", passed=89, total=89, framework="ctest")


def test_ctest_fail():
    out = "97% tests passed, 3 tests failed out of 89\n"
    _check(out, cmd="ctest", passed=86, total=89, failed=3, framework="ctest")


def test_maven_surefire():
    out = (
        "Tests run: 12, Failures: 0, Errors: 0, Skipped: 0\n"
        "Results:\n\nTests run: 89, Failures: 1, Errors: 1, Skipped: 2\n"
    )
    c = _check(out, cmd="./mvnw test", passed=85, total=87, failed=1, framework="maven")
    assert c.errors == 1 and c.skipped == 2


def test_unittest_ok():
    out = "Ran 89 tests in 0.42s\n\nOK\n"
    _check(out, cmd="python3 tests/x.py", passed=89, total=89, framework="unittest")


def test_unittest_failed():
    out = "Ran 89 tests in 0.42s\n\nFAILED (failures=2, errors=1, skipped=3)\n"
    c = _check(out, label="unittest", passed=83, total=86, failed=2, framework="unittest")
    assert c.errors == 1 and c.skipped == 3


def test_nosetests_routes_to_unittest():
    out = "Ran 12 tests in 0.10s\n\nOK\n"
    _check(out, cmd="nosetests -v -s tests/x.py", passed=12, total=12, framework="unittest")


def test_go_verbose():
    out = "=== RUN   TestA\n--- PASS: TestA (0.00s)\n--- FAIL: TestB (0.01s)\n--- PASS: TestC\nFAIL\n"
    _check(out, cmd="go test ./...", passed=2, total=3, failed=1, framework="go")


def test_catch2_summary():
    out = "test cases: 12 | 10 passed | 2 failed\nassertions: 30 | 28 passed | 2 failed\n"
    _check(out, cmd="ctest catch2", passed=10, total=12, failed=2, framework="catch2")


def test_unparseable_returns_none():
    assert parse_test_counts("some build log with no test summary", test_command="go test ./...") is None
    assert parse_test_counts("", test_command="pytest") is None


def test_fallback_without_route():
    # No framework hint, but pytest summary is unambiguous.
    out = "==================== 5 passed in 0.10s ====================\n"
    c = parse_test_counts(out)
    assert c is not None and c.passed == 5 and c.framework == "pytest"


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failures += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    raise SystemExit(1 if failures else 0)
