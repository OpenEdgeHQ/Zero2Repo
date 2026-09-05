# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only Python video-editing library that materializes clip frames as numeric arrays and encodes them through an external media binary. It has no compiled native extensions and no GPU or accelerator requirement. The documented interpreter floor is Python 3.9 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter, the declared imaging/array Python packages, and a working media encoder is sufficient to install from this repository's source and write a short generated clip.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is loading the library from this repository's source tree, constructing a short solid-color clip, and encoding it to a video file through the configured media encoder.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under that tree's package directory, construct a 16-by-16 solid-color clip lasting a fraction of a second, encode it to a video file through the configured media encoder with audio disabled, and assert the output file exists and is non-empty.
- **Setup:** Python 3.9 or newer. Declared runtime dependencies are an array library, an image I/O stack with a bundled encoder helper, a decorator helper, a progress logger, an environment-file loader, an imaging library, and headless computer-vision bindings. A working media encoder must be available — either a system encoder on PATH or one fetched by the image I/O helper on first encode. A liberation-style font set is needed when rendering text clips; the solid-color encode check does not require it. A preview player is optional and is not required for this readiness check. Hidden tests use the default Python test runner pinned below version 7 plus a coverage plugin.
- **Build:** No native compile step. The package is a flat layout built with the standard Python packaging backend. An editable install from the project root, or putting the project root on the import path, is enough to import from this tree.
