# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python library that encodes high-level HTTP request and response events into on-the-wire bytes and parses incoming bytes back into events, without performing any network I/O of its own. It has no compiled extensions, native code, or GPU/accelerator requirements, and zero declared runtime dependencies. The documented interpreter floor is Python 3.8 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and run the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is encoding a client-role HTTP/1.1 request event from this repository's source tree into on-the-wire bytes.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the protocol library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under the package directory, construct a client-role connection, encode a GET request for `/` with a Host header into wire bytes, and assert those bytes start with the HTTP/1.1 request line.
- **Setup:** Python 3.8 or newer. Zero runtime third-party dependencies. Tests use the default Python test runner plus its coverage plugin. No extra system libraries are required beyond a normal interpreter.
- **Build:** No native compile step. The package is a flat layout at the repository root, built with setuptools. An editable install from the project root, or putting the repository root on the import path, is enough to import from this tree.
