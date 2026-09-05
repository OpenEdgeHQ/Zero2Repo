# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that reads key-value pairs from environment files and applies them to the process environment. It has no compiled extensions, native code, or GPU/accelerator requirements. The documented interpreter floor is Python 3.10 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite. An optional CLI extra depends on a third-party command-line library; it is not required for the mandatory CPU profile.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is parsing a KEY=value stream from this repository's source tree and setting those pairs on the process environment.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the source layout, parse a short in-memory `KEY=value` stream, apply those pairs onto the process environment, and assert the key is present with the expected value.
- **Setup:** Python 3.10 or newer. The optional CLI extra depends on a third-party command-line library declared in the project metadata; it is not required for this profile. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step. The package is src-layout, built with a PEP 517 backend. An editable install from the project root, or putting the source directory on the import path, is enough to import from this tree.
