# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only C99 command-line tool that losslessly recompresses Ogg Vorbis and Ogg Opus bitstreams. It has no GPU or accelerator requirement and no runtime third-party libraries beyond the C and math libraries. A standard Linux x86_64 host with a C99 compiler, GNU make, and Autotools (autoconf and automake) for a git checkout is sufficient to compile the tool from this repository's sources and round-trip a short Vorbis file: compress, then expand, and assert the recovered bytes match the original.

## Execution profiles

### CPU baseline (**mandatory**)

Build the recompressor CLI from this repository's Autotools sources and run one real lossless round-trip of a bundled Vorbis fixture against the locally built binary.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Generate the configure script if it is missing, configure and compile the command-line tool from this repository's C99 sources, encode a bundled short Vorbis fixture into the tool's archive format at effort 1, decode that archive back to a bitstream, and assert the recovered bytes are identical to the input.
- **Setup:** C99 compiler and GNU make; link against the C and math libraries only. A git checkout additionally needs autoconf and automake to generate the configure script. Optional configure flags enable sanitizers or a portable mixer without SIMD. The in-tree test harness is built by the project's check target and needs the just-built binary plus the shipped fixtures.
- **Build:** From the repository root, generate the configure script if it is missing, run configure, then make. The default target produces the command-line tool. The check target builds and runs the bundled C test harness. An optional target repeats the suite once per mixer kernel this host can dispatch.
