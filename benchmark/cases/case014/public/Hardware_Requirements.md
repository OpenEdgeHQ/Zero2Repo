# Hardware Requirements

This document lists the hardware and toolchain a submitted solution must run
under. Hidden tests exercise the real capabilities below; a fallback that skips
a mandatory profile is not a substitute.

## Summary

This is a CPU-only portable C11 library for 3D inertial-navigation state estimation: an error-state Kalman filter that fuses IMU specific-force and angular-rate samples with GNSS and other aiding sensors. It has no GPU or accelerator requirement and no runtime third-party dependencies beyond libm. A standard Linux x86_64 host with a C11 compiler and GNU make is sufficient to compile the library sources from this repository and run a stationary IMU-plus-GNSS fusion that reports a ready navigation solution. Optional language bindings and dataset-replay helpers need CPython 3.8 or newer plus PyYAML and NumPy; they are not required for the mandatory CPU profile.

## Execution profiles

### CPU baseline (**mandatory**)

Compile the navigation-filter sources from this repository and run one real stationary IMU-plus-GNSS fusion against the locally built artifact.

- **Profile id:** `cpu_baseline`
- **Platforms:** linux, darwin, windows
- **Required on:** linux
- **Verification** (what the readiness check exercises, in neutral language — no real
  package/module names, no raw command):
  - Compile this repository's C11 filter sources (strapdown mechanization, geodetic helpers, and the bundled square-root Kalman linear-algebra sources) together with a small driver, initialize the error-state filter with auto-bootstrap enabled, feed ten seconds of 100 Hz stationary IMU data plus a 1 Hz GNSS position fix at a known geodetic origin with metre-level reported accuracy, and assert that the filter reports ready, that recovered latitude/longitude/height match that origin, and that roll and pitch stay near level.
- **Setup:** C11 compiler and GNU make; link against libm. The core library has no other runtime third-party dependencies. A recursive checkout of the bundled linear-algebra submodule is required before the first compile. Optional CPython 3.8 or newer, PyYAML, and NumPy for the language binding and dataset-replay helpers.
- **Build:** From the repository root, the documented default make target compiles the C test binaries; the shared library used by the language binding is a separate make target. The tutorial path compiles the filter C sources alongside a driver with `cc -std=c11` and `-lm`. There is no CMake (or other) extra build-system dependency.

