# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only TypeScript lint-plugin library that registers custom static-analysis rules with a JavaScript linter and reports diagnostics on TypeScript and JavaScript source. It has no compiled native extensions, no GPU or accelerator requirement, and is consumed as TypeScript source rather than a separately bundled binary. A standard Linux, macOS, or Windows host with Node.js 24 and the project's documented package manager is sufficient to install from this repository and exercise one rule against a short snippet.

## Execution profiles

### CPU baseline (**mandatory**)

Load a lint rule from this repository's TypeScript sources and run one real diagnostic against a snippet that chains array filter into map.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Import a lint rule from this repository's TypeScript sources (not a separately published registry package), construct the linter's rule tester for TypeScript, run it on a short snippet that chains array `filter` into `map`, and assert a diagnostic is produced for that pattern while a lazy iterator pipeline of the same operations is accepted.
- **Setup:** Node.js 24 and the project's declared package manager, installing from the committed lockfile. Runtime and development dependencies are the linter, its plugin-host package, a TypeScript runner, and a no-emit typechecker. No extra system libraries beyond a normal JavaScript toolchain; no GPU or accelerator.
- **Build:** No native compile step. The package exports TypeScript source directly. Typechecking is no-emit. A copy script mirrors production sources into a bundled installer snapshot, excluding test files.
