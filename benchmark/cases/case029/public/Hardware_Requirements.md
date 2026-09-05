# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a pure-Python natural-language processing library with no compiled extensions, native code, or GPU/accelerator requirements. The documented interpreter floor is Python 3.10 or newer. Any standard x86_64 or arm64 Linux, macOS, or Windows host with a supported interpreter is sufficient to install from source and exercise the baseline tokenizer path. Optional extra groups add scientific-computing libraries for some classifiers and plot helpers; they are not required for the mandatory CPU profile.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only Python execution path. Core capability is loading the library from this repository's source tree and running one real word/punctuation tokenization with no downloaded corpus or model.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Load the library from this repository's source tree (not a separately published wheel), confirm the imported module file lives under that tree's package directory, tokenize a short English sentence with the regular-expression word/punctuation splitter, and assert the token list matches the documented split (words and punctuation as separate tokens, including a split of a currency amount).
- **Setup:** Python 3.10 or newer. Declared runtime dependencies are a small set of PyPI packages (XML hardening, a CLI helper, a parallelism helper, a regular-expression engine, and a progress bar). The test extra is the default Python test runner plus a mock plugin. Full-suite corpus downloads are documented for the upstream suite and are not required for this readiness check. No extra system libraries beyond a normal interpreter.
- **Build:** No native compile step. The package is a flat layout built with the standard Python packaging backend. An editable install from the project root, or putting the project root on the import path, is enough to import from this tree.
