# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that evaluates declarative path expressions against nested JSON-like mappings and sequences and returns the selected values. It has no compiled extensions, native code, or GPU/accelerator requirements, and zero declared runtime dependencies. The documented interpreter floor is Python 3.9 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is evaluating a dotted-field expression against a nested mapping from this repository's source tree and returning the selected scalar.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the query engine from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the repository package directory, evaluate a dotted-field expression against a small nested mapping, and assert the extracted scalar equals the expected value.
- **Setup:** Python 3.9 or newer. Zero runtime third-party dependencies. Tests use a third-party Python test runner. Optional coverage and property-based extras exist and are not required for this profile. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step. The importable package uses a flat layout at the project root and is packaged with setuptools. An editable install from the project root, or putting the project root on the import path, is enough to import from this tree.
