# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only Go command-line tool and standard-library library for Git-native project-memory bundles: parse Markdown/YAML concepts, in-memory lexical search, graph validation, project scaffold, and a stdio tool-server. It has no GPU or accelerator requirement and no third-party Go module dependencies. A standard Linux x86_64 host with Go 1.22 or newer (the module language floor; the contributing guide also documents 1.24 or newer), GNU make, Git, and a C compiler for the race detector is sufficient to compile the CLI from this repository's sources and exercise initializing a bundle, creating a concept, and searching it.

## Execution profiles

### CPU baseline (**mandatory**)

Build the knowledge-bundle CLI from this repository's Go module and run one real create-then-search operation against the locally built binary.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Compile this repository's command package from source into a temporary binary, initialize a new bundle directory, create one concept whose description mentions a distinctive probe phrase, search that bundle for the phrase with JSON output, and assert that the created concept identifier appears in the result.
- **Setup:** Go 1.22 or newer (module language floor; contributing docs also state 1.24 or newer), GNU make, and Git. The module has no third-party Go dependencies. A C compiler is required when running the race-enabled test target. No GPU or extra system libraries.
- **Build:** Compile this repository's command-line package from source into a CLI binary (`go build` of that package, or the equivalent `make` target that produces the same binary). The build also produces the stdio tool-server in the same binary.
