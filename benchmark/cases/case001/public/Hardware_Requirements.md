# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only C++20 library for WHATWG-compliant URL parsing, normalization, and component access. It has no GPU or accelerator requirement and no runtime third-party dependencies. A standard Linux x86_64 host with a C++20 compiler (GCC 12 or newer, LLVM 14 or newer, or MSVC 2022 or newer) and CMake 3.16 or newer is sufficient to compile the library from this repository's sources and exercise a parse of an absolute https URL.

## Execution profiles

### CPU baseline (**mandatory**)

Build the URL-parser library from this repository's CMake sources and run one real parse of an absolute https URL against the locally built artifact.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Configure and compile this repository's library target from source with CMake in Release mode, compile a small C++20 program that includes the public header and links the just-built archive, parse an absolute `https` URL, and assert that hostname and pathname match the input and that a serialized href is printed.
- **Setup:** C++20 compiler at the documented floors (GCC 12 or newer, LLVM 14 or newer, or MSVC 2022 or newer) and CMake 3.16 or newer. The library is self-contained at runtime. Optional Ninja generator. Enabling the project's test option additionally fetches a unit-test framework through the CMake package manager.
- **Build:** Configure from the repository root with CMake and build the library target (library-only configure does not enable tests). When the build type is left unset, the project defaults to Release.
