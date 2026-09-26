# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python command-line interface toolkit with no compiled extensions, native code, or GPU/accelerator requirements. It has zero declared runtime dependencies and requires Python 3.10 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported Python interpreter is sufficient to install from source and run the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is defining composable CLI commands and options and invoking them, including through the in-process test runner helper.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the toolkit from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the source layout, construct a command whose callback writes a short token to standard output, invoke that command through the in-process runner helper, and assert a zero exit status with captured output equal to the token.
- **Setup:** Python 3.10 or newer. The test extra is the default Python test runner only. No extra system libraries are required beyond a normal interpreter; pager helpers may look up the system pager if present.
- **Build:** No native compile step. The package is src-layout, built with a PEP 517 backend. An editable install from the project root, or putting the source directory on the import path, is enough to import from this tree.
