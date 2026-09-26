# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that parses TOML documents into native mappings, sequences, and scalars. The default path has no compiled extensions, no runtime third-party dependencies, and no GPU or accelerator requirements. The documented interpreter floor is Python 3.8 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite. Optional compiled wheels exist for performance on some platforms; they are not required for the mandatory CPU profile.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is parsing a TOML document from this repository's source tree into native Python dict, list, and scalar values.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the parser from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the source layout, parse a short in-memory TOML document containing one integer assignment, and assert the result equals the expected native mapping.
- **Setup:** Python 3.8 or newer. Zero runtime third-party dependencies. Tests use the standard-library unit-test runner. Optional compiled-extension wheels exist for performance on some platforms and are not required for this profile. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step for the default path. The package is src-layout, built with a PEP 517 backend. An editable install from the project root, or putting the source directory on the import path, is enough to import from this tree.
