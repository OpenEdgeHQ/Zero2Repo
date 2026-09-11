# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that generates and verifies HMAC-based and time-based one-time passwords. It has no compiled extensions, native code, or GPU/accelerator requirements, and zero declared runtime dependencies. The documented interpreter floor is Python 3.8 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is generating a counter-based one-time password from a shared secret and verifying that code against the same counter.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the source layout, construct a counter-based generator with a known shared secret, emit the code for counter 0, and assert that value matches the expected RFC test-vector string and that verifying the same code against counter 0 succeeds.
- **Setup:** Python 3.8 or newer. Zero runtime third-party dependencies. Tests use the standard-library unit-test runner; an optional coverage wrapper is documented but not required for this profile. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step. The package is src-layout, built with a PEP 517 backend whose version metadata is taken from version control. An editable install from the project root, or putting the source directory on the import path, is enough to import from this tree.
