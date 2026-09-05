# Hardware Requirements

This document describes the hardware and toolchain expectations for running
Judge tests against this case's **PRD-declared core capabilities**.

## Summary

This is a CPU-only Go command-line Git extension. No GPU or specialized
accelerator is required. A standard Linux x86_64 contestant machine with a
Go toolchain meeting the module minimum (Go 1.25 or newer), GNU make, and
Git is sufficient to compile the client from source and exercise the
PRD-declared CLI entrypoints.

## Judge policy

Milestone tests verify **PRD-declared capabilities**, not cheaper
cross-machine proxies. When a capability is platform-specific, tests must
exercise that capability on runners where the corresponding profile's
readiness check succeeds. Graceful-degradation is a separate scenario only
when the PRD explicitly requires fallback — it must not replace the primary
capability test.

## Execution profiles

### CPU baseline (**mandatory**)

Build the large-file Git extension CLI from this repository's Go module and
run one real CLI operation against the locally built binary.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language —
  no real package/module names, no raw command):
  - Compile the module-root main package from this repository into a
    temporary binary, invoke its version subcommand, and assert a successful
    exit (the built-from-source client reports its version string).
- **Setup:** Go 1.25 or newer, GNU make, and Git. Module dependencies are
  fetched via the Go module proxy.
- **Build:** Compile the module-root main package into a CLI binary
  (`go build` at the repository root, or the equivalent `make` target that
  produces the same binary).
