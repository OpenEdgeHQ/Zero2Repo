# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that cryptographically signs serialized payloads so they can be sent to untrusted environments and verified on return. It has no compiled extensions, native code, or GPU/accelerator requirements, and zero declared runtime dependencies. The documented interpreter floor is Python 3.10 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is signing a small mapping into a compact token and verifying that loading the token recovers the original mapping.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the signing library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the source layout, construct a serializer with a secret key, dump a small mapping to a compact signed token, load that token, and assert the recovered mapping matches the original.
- **Setup:** Python 3.10 or newer. The tests extra is the default Python test runner plus a clock-freezing helper used by timed-signature tests. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step. The package is src-layout, built with a PEP 517 backend. An editable install from the project root, or putting the source directory on the import path, is enough to import from this tree.
