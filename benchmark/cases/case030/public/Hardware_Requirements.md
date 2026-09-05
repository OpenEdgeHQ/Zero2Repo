# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only TypeScript/JavaScript library that parses and serializes YAML 1.2 (with optional YAML 1.1 types). It has no compiled native extensions, no GPU or accelerator requirement, and one declared runtime dependency used only by the command-line entry. A standard Linux, macOS, or Windows host with a current Node.js LTS interpreter and npm is sufficient to install from this repository, run the documented bundle step, and exercise a parse of a one-key mapping against the locally built artifact.

## Execution profiles

### CPU baseline (**mandatory**)

Build the YAML parser/serializer from this repository's TypeScript sources and run one real load of a one-key mapping against the locally produced ESM artifact.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Run the documented from-source bundle step, import the locally produced ESM artifact from the distribution directory (not a separately published registry package), parse a one-key YAML mapping whose value is an integer, and assert the loaded object carries that integer under the expected key.
- **Setup:** A current Node.js LTS interpreter and npm. The suite uses the runtime's built-in test runner. The only declared runtime dependency is a command-line argument parser used by the CLI entry, not by the library load/dump path. No extra system libraries beyond a normal JavaScript toolchain; no GPU or accelerator.
- **Build:** TypeScript sources are bundled into ESM, CommonJS, and browser artifacts plus type declarations under the distribution directory. There is no native compile step.
