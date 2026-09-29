# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only, standard-library prose-pattern detector with companion JavaScript hooks. It has no compiled extensions, native code, GPU or accelerator requirement, and no runtime third-party dependencies. The documented interpreter floor is Python 3.9 or newer; the saved-file hooks require Node.js. Any standard x86_64 or arm64 Linux, macOS, or Windows host with those interpreters is sufficient to run the detector from this repository's source tree and execute the test suite.

## Execution profiles

### CPU baseline (**mandatory**)

Standard CPU-only execution path. Core capability is scoring a short prose sample with the detector script from this repository's source tree and returning a 0-100 JSON report.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Run the detector from this repository's source tree (not a separately published distribution) on a short sample of formulaic English prose via standard input, parse the JSON report, assert the 0-100 score field is an integer in range, and assert that the banned-vocabulary family is present in the report.
- **Setup:** Python 3.9 or newer and Node.js. Zero runtime third-party dependencies. The test suite uses a Python test runner, a YAML parser for skill-file frontmatter checks, and a Bash harness that pipes synthetic payloads into the JavaScript hooks. No extra system libraries are required beyond those interpreters.
- **Build:** No native compile step and no installable package. The detector is a Python script invoked from the source tree; the hooks are JavaScript files run with Node. Putting the repository root as the working directory is enough.
