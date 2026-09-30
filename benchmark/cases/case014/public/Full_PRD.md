# NAVFILTER — Full Product Requirements Document

## Product overview

**NAVFILTER** is a portable C11 library for 3D navigation state estimation. Its core is a set of Kalman filters that fuse an inertial measurement unit (IMU: accelerometer and gyroscope) with aiding sensors — GNSS/GPS, barometer, magnetometer, local position references (lighthouse / UWB / motion capture), absolute yaw references, scalar ground speed, and zero-velocity / zero-rotation information — into one estimate of **where the body is** and **which way it is pointing**.

A first-time integrator zeros one caller-owned filter instance, hands it a coarse Earth anchor and options (almost every field left at zero picks a conservative consumer-MEMS default), then feeds a stream of IMU epochs with whatever aiding is present that epoch. After a short warm-up the filter reports a ready navigation solution: WGS84 position, local NED velocity, and body-to-NED attitude. A UAV that loses GNSS does not go silent: the navigation suite keeps publishing inertial-fused altitude through the parallel barometric vertical channel and full attitude from the independent attitude filters. A platform that only needs roll and pitch, with freely integrated yaw, can run the standalone ARS from IMU data alone and skip the magnetometer.

Typical uses advertised by the product: drones and autonomous vehicles, robotics, aerospace, cars, embedded tracking, and post-processing of recorded flights or drives. The same filters are reachable from C and from a Python package that wraps the compiled library. Recorded trials are replayed from a dataset directory of CSV streams plus one `config.yaml`.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, call spellings, and header paths belong in the Interface Contract, not here. Every feature point below corresponds to behavior that exists in the finished NAVFILTER product. Feature points are ordered so foundational capabilities come first; a later feature point may depend on an earlier one, never the reverse.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **INS** | The 3D navigation filter. It estimates local NED position and velocity, body-to-NED attitude, accelerometer bias, and gyroscope bias. |
| **AHRS** | The attitude-and-heading reference filter. Two modes are fixed per instance, listed under FP-06: ARS and AHRS. |
| **ARS** | The roll/pitch attitude filter whose yaw is the integral of the bias-corrected z-rate and is never measurement-corrected (directional gyro). |
| **Barometric vertical channel** | The independent barometer-plus-accelerometer vertical filter: height above a datum (positive up), vertical velocity (positive up), and a slow vertical-acceleration correction. |
| **Navigation suite** | The wrapper that runs INS, one ARS, one magnetometer AHRS, and the barometric vertical channel from the same measurement stream and publishes a best-available solution with an explicit mode. |
| **Python navigator** | The Python high-level entry that drives the navigation suite. Push sensors, run one epoch, read a unified solution. |
| **Python INS wrapper** | The lean Python entry that drives INS alone, without AHRS/baro fallback. |
| **Epoch** | One time-stamped measurement bundle. The IMU sample begins the epoch; aiding fields present on that epoch are fused with it. |
| **Ready** | The INS flag that means position and velocity are currently usable. False during warm-up, after an expired coasting window (unless unlimited dead reckoning is on), and after a GNSS quality-loss exit. |
| **Initialized** | The INS has bootstrapped and holds a 3D state. Position accessors succeed while initialized even if ready is false (for example a frozen coast). Quality-loss re-arm clears this, so those accessors then fail. |
| **Solution mode** | The suite’s four-valued status: FULL, COASTING, ATTITUDE_ONLY, or NONE. Defined in FP-08. |
| **FRD** | Body frame: x forward, y right, z down, right-handed. Every IMU, magnetometer, and lever arm is in this frame. |
| **NED** | Navigation frame: north, east, down. Local positions and velocities are in NED relative to an origin fixed at init. |
| **ECEF** | WGS84 Earth-centred Earth-fixed Cartesian coordinates, metres. GNSS positions arrive in ECEF. Double precision is used for this Earth anchor; the filter hot path is otherwise 32-bit float. |
| **Hamilton quaternion** | Attitude as body-to-NED, scalar-first: real part then vector part. |
| **Tait-Bryan ZYX** | Roll, pitch, yaw of the body relative to NED. Angles in radians unless a file format below says degrees. |
| **Timestamp** | Monotonic integer microseconds. |
| **Specific force** | Accelerometer reading. At rest and level in FRD, the sample is approximately (0, 0, −g): gravity appears as +g along −z. |
| **Aiding** | Any measurement other than the IMU that corrects the INS: GNSS position/velocity, local NED position, magnetometer, absolute yaw, scalar speed, barometric height, zero-velocity, zero-rotation. |
| **Coasting / dead reckoning** | IMU-only propagation after the last absolute position aiding (GNSS or local position). |
| **Coasting window** | Configurable IMU-only budget after which INS ready becomes false and the instance freezes. Default 10 seconds. Unlimited dead reckoning disables this. |
| **Entry gate / exit gate** | Two GNSS quality threshold sets. The entry gate plus its dwell decide whether the 3D solution may start. The exit gate plus its dwell decide whether the 3D solution is given up. Distinct from the per-fix fusion gate. |
| **World Magnetic Model (WMM)** | Built-in lookup of magnetic declination, inclination, total field, and the NED reference field for a geographic position and decimal year. |
| **Local height** | Height above the NED origin, positive up, zero at the origin. Shared by INS and the barometric vertical channel. |
| **Ellipsoid height** | Absolute WGS84 height. Available from INS under GNSS, or as local height plus the estimated local-to-ellipsoid offset during an outage. |
| **ISA altitude** | Barometric altitude from the international standard atmosphere formula, carrying weather offset and model error; not an absolute height. |
| **ZUPT** | Zero-velocity update: a known-standstill velocity measurement. |
| **ZARU** | Zero-rotation update: a known-standstill gyro-bias measurement. |
| **Lever arm** | Body-FRD offset from the IMU to an aiding sensor (GNSS antenna, local-position sensor). |
| **Dataset directory** | A folder of CSV streams plus one `config.yaml`, consumed by both replay harnesses. Layout in FP-10. |
| **Core capability** | A user-observable capability that reflects NAVFILTER’s design goal; acceptance must prove the real library behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

## Public surface inventory

NAVFILTER is a **library** with two language entries and a post-processing harness. Integrators compile the C sources into their firmware or desktop program, or build the shared library and use the Python package. There is no network stack inside the filters themselves.

The public, independently verifiable surfaces, grouped the way later feature points verify them, are:

- Frame conventions, WGS84 ECEF ↔ geodetic conversions, Hamilton / Tait-Bryan mapping, and the World Magnetic Model lookup (FP-01).
- The INS filter: init, per-epoch IMU-plus-GNSS fusion, auto-init, ready flag, position / velocity / attitude / bias accessors (FP-02).
- Further aiding on the same epoch bundle: magnetometer, local NED position, absolute yaw, scalar speed, barometric height inside INS, explicit and automatic ZUPT/ZARU (FP-03).
- Delayed GNSS, local-position, and yaw measurements, including the replay delay estimator (FP-04).
- GNSS entry/exit quality, the coasting window, freeze, re-acquisition, and unlimited dead reckoning (FP-05).
- Standalone ARS and AHRS attitude filters (FP-06).
- Standalone barometric vertical channel and the three height systems (FP-07).
- The navigation suite and Python navigator: parallel filters, mode arbitration FULL → COASTING → ATTITUDE_ONLY → NONE, continuous local and ellipsoid height (FP-08).
- Non-finite input drop, outlier downweighting, the global outlier-rejection override, and fail-safe (never publish a non-finite solution) (FP-09).
- Dataset replay from CSV plus `config.yaml`, and the YAML-configured custom-CSV runner (FP-10).

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

## Non-functional constraints

- **Form factor:** A C11 library with no heap and no operating-system calls in the core filters. All filter state lives in caller-owned instance structs of fixed size. The same sources build for bare-metal microcontrollers and for a desktop host.
- **Dependencies:** The core needs a C11 compiler, GNU make, and libm. No GPU, no accelerator, no runtime third-party C libraries. Optional Python bindings and replay helpers need CPython 3.8 or newer plus PyYAML and NumPy; they are not required for the mandatory CPU profile.
- **Precision:** The per-epoch hot path is 32-bit IEEE-754 float. Double precision is reserved for the WGS84 ECEF / lat-lon-height anchor.
- **Determinism:** Per-epoch work has a bounded worst-case execution time: no unbounded loops, no recursion, no iteration counts that depend on measurement values.
- **Platforms:** POSIX and Windows are both intended. This case’s acceptance targets Linux x86_64 with a C11 compiler.
- **Hardware:** CPU-only. The mandatory execution substrate is a real host that can compile the library sources from this repository and run a stationary IMU-plus-GNSS fusion that reports a ready navigation solution. There is no removable accelerator profile and therefore no negative-control clause.
- **Conventions:** Body FRD, navigation NED, Hamilton quaternion (scalar first), timestamps in integer microseconds, filter angles in radians. Matrices are column-major.
- **Defaults:** A configuration field left at zero (or an all-zero list) means “use the built-in default”, never “inject zero noise”. An all-zero options block is a working, conservative filter.
- **Error text:** Wording of log lines is informational. Graded behavior is success versus failure, ready versus not, which solution mode, whether a value is published, and diagnostic counters that an observer can read — not a particular sentence.
- **Identity of the product:** The library, the Python package, the shared object, and the dataset configuration keys use the spelling **NAVFILTER**.

## Capability discrimination (global)

Every feature point below is a **core capability**. None is an accelerator-backed mandatory-substrate GPU feature.

For every feature point:

- **Present:** Real NAVFILTER behavior matches the described outcomes when a filter or suite instance is initialized and fed the named measurement stream, or when a dataset directory is replayed.
- **Absent / hollow:** A kinematics integrator without fusion; a hard-coded Munich lat/lon; a generic Kalman-filter tutorial that does not consume FRD IMU and ECEF GNSS; a replay that prints a fixture trajectory regardless of the CSV; an attitude complementary filter that cannot be told apart from ARS versus AHRS.

Cheaper proxies (a strapdown integrator with no covariance, a GNSS smoother that ignores the IMU, MATLAB Navigation Toolbox, a Python-only reimplementation that is not this library, or a mock that returns the first fix forever) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces the real INS / AHRS / barometric vertical channel / suite for a core capability.

There is no removable mandatory hardware profile. Do not treat absence of a GPU as a test skip or as a negative control. The package under test and the interpreter are not substrates.

## Non-goals

- A public reference-board firmware. The hardware protocol and calibration GUIs exist as host tools around a board whose firmware is not part of this product surface.
- Live UDP ingest, PlotJuggler / MAVLink telemetry streaming, Google Earth model packaging, multi-page plot export, and the post-processing Qt GUI as independently graded capabilities. Replay that produces a navigation solution from CSV is FP-10; live sockets, plots, and interactive windows are not.
- IMU-TK / Allan-variance host utilities, u-blox receiver configuration scripts, OBD-II dongles, and SPARTN key loading.
- Requirements-database machinery, sanitizer builds, coverage HTML, and Doxygen as product capabilities.
- Claiming Galileo HAS, SPARTN, or RTK as filter features: those are receiver-side accuracy sources. NAVFILTER consumes whatever ECEF fix and covariance the caller supplies.
- Optional magnetometer hard-iron bias estimation, IMU/magnetometer calibration matrices consumed by the filter, and automotive course-over-ground yaw. They exist in the library but are outside this case’s ten-feature budget.
- Heap allocation, threads, or an operating-system abstraction inside the core filters.
- 64-bit FPU as a requirement of the hot path.

---

## Feature points

### FP-01: Frames, geodetic conversions, and the World Magnetic Model

**Public entry:** The geodetic / quaternion helpers shipped with the C library and re-exported by the Python package, plus the World Magnetic Model lookup. These run without constructing an INS instance. Filter-facing use of the same conventions is FP-02 through FP-08.

**Normal behavior:**

- Body quantities are FRD. Navigation quantities are NED. A specific-force sample of a vehicle sitting still on a level pad is near (0, 0, −g) in FRD. A local position of (1.5, 0, 0) metres is 1.5 m north of the origin, not east or up.
- Attitude is a Hamilton quaternion mapping body to NED, scalar first. Roll, pitch, yaw are Tait-Bryan ZYX in radians. Converting zero roll, pitch, and yaw yields the identity quaternion (real part 1, vector part 0). Converting yaw of π/2 with zero roll and pitch yields a quaternion whose real part and z-part are both cos(π/4) and sin(π/4) to single-precision tolerance, other parts near zero. Converting a non-trivial triple such as roll 0.3 rad, pitch −0.2 rad, yaw 1.1 rad to a quaternion and back recovers the same angles to single-precision tolerance.
- Geodetic positions use the WGS84 ellipsoid. Converting geodetic latitude 48.783°, longitude 9.181°, height 300 m to ECEF and back recovers latitude and longitude to 1e-10 rad and height to 0.1 mm. The inverse direction (ECEF → geodetic → ECEF) is consistent to the same order.
- At the geographic poles the NED azimuth transport rate stays finite: feeding a latitude whose cosine would otherwise vanish, together with a non-zero east velocity, does not produce a non-finite rate. Zero and other degenerate quaternions normalize to the identity (real part 1, vector part 0) rather than NaN.
- The World Magnetic Model lookup, given latitude, longitude, and a decimal year, returns magnetic declination in degrees (positive east), inclination in degrees (positive down in the northern hemisphere), total field in microtesla, and a three-axis NED reference field in microtesla. The assembled NED field is self-consistent: its horizontal direction matches the declination, its magnitude matches the total field. The C library exposes all four quantities. The Python package re-exports the NED field; heading and magnitude recovered from that field still match declination and total field.
- Declination at a mid-latitude site away from the geomagnetic poles matches the underlying WMM evaluation to within 0.15°. Near the geographic poles (absolute latitude above 88°) the tolerance widens to 0.6°. Longitude 190° and −170° at the same latitude and year produce the same declination (wrap). Longitude ±180° returns a finite declination.

**Boundary / error behavior:**

- Latitude is clamped to [−90°, +90°]. Longitude is wrapped into (−180°, +180°]. Out-of-range years are extrapolated rather than refused.
- A gimbal-lock pitch (near ±π/2) still yields finite roll/pitch/yaw; the mapping does not abort and does not produce NaN.

**Verifiable oracle:**

- Success: Stuttgart-ish 48.783° / 9.181° / 300 m round-trips through ECEF as above; identity and 90° yaw quaternion mappings hold; a non-trivial roll/pitch/yaw round-trips; WMM declination at a mid-latitude test location matches the published vector within 0.15°; the NED field’s heading equals that declination and its magnitude equals the total field; longitude 190° agrees with −170°; ±180° is finite; polar transport rate stays finite under a non-zero east velocity; a zero quaternion normalizes to the identity.
- Failure / absence: ECEF conversion uses a spherical Earth that misses the WGS84 flattening (height error of metres); body frame is RFU or FLU so a level rest IMU is stored as +g on +z; quaternion is vector-first so identity is not (1, 0, 0, 0); WMM returns a constant or magnetic-north-only heading with no declination; longitude 190° disagrees with −170°; polar latitude with a non-zero east velocity produces Inf.

---

### FP-02: INS 3D navigation from IMU and GNSS

**Public entry:** The C INS instance and the Python INS wrapper. The caller zeros the instance, supplies an initial Earth anchor and options, then feeds epochs (IMU plus optional GNSS) and reads position, velocity, attitude, and biases. Auto-init, quality gates, and coasting lifecycle details that refine when ready is true are scoped in FP-05. Extra aiding sensors are FP-03. Delay is FP-04. The suite that wraps INS is FP-08.

**This feature point uses FP-01.** Positions, attitudes, and timestamps follow FP-01.

**Normal behavior:**

- Construction requires a coarse WGS84 ECEF origin (the local NED origin). A zeroed options block with auto-init enabled is valid. Fields left at zero resolve to conservative consumer-MEMS defaults; they do not lock the corresponding process noise at zero.
- The INS estimates, continuously after bootstrap: local NED position relative to that origin, NED velocity, body-to-NED attitude, body-frame accelerometer bias, and body-frame gyroscope bias.
- Each epoch is one bundle. The caller marks which sub-measurements are valid. An epoch that carries only IMU is normal. A GNSS position, when present, is ECEF metres with a 3×3 NED covariance (a diagonal receiver fills the three diagonal entries and leaves the rest zero). A GNSS velocity, when present, is NED metres per second with a NED covariance. The Python sensor-push calls accept either the three NED diagonal variances or a full 3-by-3 NED covariance.
- Auto-init (the default happy path): the filter bootstraps from the stream. Roll and pitch come from accelerometer leveling over a window (by default the most recent 0.1 s of IMU samples, `auto_init_window_sec`). Yaw comes from an absolute yaw measurement if present, else the magnetometer, else it is left unknown with a correspondingly large uncertainty. Position and velocity come from the first usable GNSS (or local-position, FP-03) fix that also satisfies the entry gate and dwell of FP-05. A coarse origin guess is enough; the first real fix refines the solution.
- After bootstrap, feeding a stationary, level IMU at 100 Hz with specific force (0, 0, −9.81) m/s² and zero rotation, plus a once-per-second GNSS fix at the origin with about 2 m / 2 m / 2 m NED 1-sigma (at or inside the FP-05 default entry gate), for long enough to cover that gate’s default dwell plus the 1.5 s ready wait after the instance is initialized, yields: ready true; ECEF position matching that fix to well under a metre; roll and pitch near level (a few hundredths of a degree in the noise-free case, well under half a degree with light MEMS noise).
- The GNSS antenna lever arm in body FRD is applied: a non-zero lever arm couples attitude into the position residual at the measurement’s time of validity. Two identical trajectories that differ only by a 15 cm rightward lever arm do not produce the same position innovation during a yaw rate.
- Ready is false until both a minimum of four filter-update epochs and 1.5 seconds of runtime have elapsed after the instance is initialized, even if a fix is already in. Reading the solution for use as a navigation answer is gated on ready. Accessors for position, velocity, and attitude succeed as soon as the filter is initialized, including during a later freeze (FP-05); they fail when the instance is not initialized.
- The Python INS wrapper uses the same conventions and the same three-move loop: push IMU (and any GNSS), run the epoch, then read. Readers do not themselves run the filter. Forgetting the epoch step leaves ready false.

**Boundary / error behavior:**

- Init fails (no instance is started) when the supplied ECEF origin has Euclidean norm below 1 km — a neighbourhood of (0, 0, 0), not a point on the Earth. A valid ECEF has norm on the order of 6.4×10⁶ m.
- Init fails if a required pointer is missing: the instance, its init block, and its options block are all required (a zeroed options block is valid; a missing one is not).
- An IMU epoch whose accelerometer or gyroscope is marked invalid is not a strapdown step. Processing continues with later valid IMU.
- GNSS with a non-positive covariance diagonal is not fused. A fix whose reported accuracy exceeds the fusion gate of FP-05 is not fused. Neither case disables the filter.

**Verifiable oracle:**

- Success: auto-init plus a stationary Munich-style 100 Hz IMU and 1 Hz GNSS at the origin with 2 m / 2 m / 2 m NED 1-sigma, after the FP-05 default entry dwell and the 1.5 s ready wait, reports ready true, ECEF matching the fix, and near-level roll/pitch; a zeroed options block starts; a 15 cm FRD lever arm changes the GNSS residual under rotation relative to a zero lever arm; ready stays false for 1.5 s after initialization even with good fixes; the Python wrapper that skips the epoch step never becomes ready.
- Failure / absence: the filter reports the init ECEF as the solution without consuming IMU; ready is true on the first epoch; a (0, 0, 0) ECEF origin is accepted; leaving IMU noise at zero produces a locked, overconfident filter that ignores subsequent GNSS; the Python reader call itself advances the filter.

---

### FP-03: Aiding beyond GNSS

**Public entry:** The same INS epoch bundle and Python sensor-push calls as FP-02, with additional valid fields: magnetometer, local NED position, absolute yaw, scalar ground speed, barometric static pressure (as an INS height source), and explicit zero-velocity / zero-rotation flags. Automatic standstill detection is part of this feature point. The standalone barometric vertical channel is FP-07. Suite-level height arbitration is FP-08.

**This feature point uses FP-02.** GNSS-only fusion remains available; this FP adds the other aiding the same instance accepts.

**Normal behavior:**

- **Local NED position** (lighthouse, UWB, motion capture, total station): the sample is already in the filter’s NED frame (origin = the init Earth anchor). Aligning the tracker’s frame is the caller’s job. A 10 Hz indoor tracker at (1.5, 0, 0) m with centimetre covariance, plus a stationary IMU, bootstraps a ready 3D solution without any GNSS. The published local position matches that tracker. Outliers on this channel are skipped, not downweighted: a high-rate glitch is omitted from fusion rather than fused at reduced weight; after a clean tracker lock the published local position stays with the tracker and the downweight diagnostic does not rise.
- **Magnetometer:** fused so that only heading is corrected — a disturbed field must not tilt roll or pitch. Fusion is rate-limited; the default minimum interval is 1 second (a long-term yaw anchor, not a per-epoch yaw sensor). A negative interval disables the limit. A sample supplied without per-axis variance uses the library’s own weak default, never a zero-noise measurement. After the World Magnetic Model is armed from a geographic position and decimal year (FP-01), estimated yaw is relative to true north; until then the magnetic reference is magnetic north.
- **Absolute yaw** (dual-antenna GNSS, mocap pose, gyro compass): a scalar heading in radians. Either a single-turn convention in [−π, π] or in [0, 2π) is accepted and normalized. Fusion is skipped near gimbal lock (pitch approaching ±90°).
- **Scalar ground speed** (OBD-II, wheel odometry, Doppler log): the magnitude of velocity, with no direction. It observes speed only, not heading: an along-track speed error is pulled toward the measurement, a purely sideways velocity error is not. If the filter’s own speed is below a minimum (default 1 m/s), the sample is skipped.
- **Barometric height inside INS:** when barometer samples are supplied and the barometric height source is selected, INS uses the barometer for the vertical channel and restricts GNSS position fusion to the horizontal. With both GNSS and barometer wired and the disable switch off (the default), the barometer is the height source — a fail-safe through a GNSS outage. Setting the barometric-height disable switch forces GNSS height instead. A local-position bootstrap keeps tracker height even when a barometer is present.
- **Explicit ZUPT / ZARU:** a caller who knows the platform is standing still flags zero-velocity and/or zero-rotation on that epoch. The filter then fuses a direct velocity measurement of zero and/or a direct gyro-bias measurement of a still body. Each is rate-limited to one fusion per filter-update interval.
- **Automatic ZUPT / ZARU:** enabled by default. The detector declares stillness from the IMU sample spread over a short window (bias does not trip it) plus magnitude bounds (a steady turn is not stillness) and, when a recent accurate GNSS velocity exists, a speed gate. It does not gate on the filter’s own velocity. A public diagnostic reports whether the detector currently considers the platform stationary. A runtime disable switch turns the detector off without affecting explicit ZUPT/ZARU flags; re-enabling requires a fresh stillness run.

**Boundary / error behavior:**

- An absolute yaw whose magnitude exceeds one full turn is treated as a unit or unwrapping mistake: it is not fused, and the invalid-input diagnostic counter increments. It is not wrapped into a plausible but wrong heading.
- Magnetometer fusion is skipped when the horizontal reference field is unusable (near-zero or near-vertical field).
- Local-position samples whose covariance is degenerate are not fused.
- Automatic ZUPT does not fire on a single IMU sample: the variance window must cover both a minimum duration and a minimum sample count before the first verdict. An epoch with no IMU leaves the window and the latched verdict untouched. By default the window is 0.2 s and at least 8 IMU samples, and the verdict must hold for a 0.2 s dwell before the detector reports stationary.

**Verifiable oracle:**

- Success: local-position-only auto-init at (1.5, 0, 0) m becomes ready and reports that local position; a local-position bootstrap with a barometer present still reports tracker height; a magnetometer-aided yaw run changes heading while leaving roll/pitch at the accelerometer-levelled values; arming WMM makes yaw track true north rather than magnetic north by the local declination; a yaw of π and the same heading expressed as −π both fuse; a 3π yaw is dropped and the invalid-input counter increases; default magnetometer rate-limiting does not fuse every 100 Hz mag sample; with barometer and GNSS both present and the disable switch off, cutting GNSS keeps a usable vertical solution; explicit ZUPT on a stationary IMU holds velocity near zero; the auto-detector reports stationary on a still IMU after the dwell and does not report stationary on a constant-rate turntable.
- Failure / absence: local position is interpreted as ECEF; magnetometer residuals tilt roll/pitch; WMM is ignored so yaw stays on magnetic north after a position is supplied; a 3π yaw is wrapped and fused; zero mag variance is treated as a perfect heading; automatic ZUPT uses the filter’s own velocity and self-locks on a biased IMU; barometer plus GNSS still uses GNSS height during a GNSS outage.

---

### FP-04: Delayed aiding

**Public entry:** The delay fields on GNSS position/velocity, local position, and absolute yaw in the same epoch bundle as FP-02 / FP-03 (and the matching Python delay argument). The Python replay harness’s GNSS-latency estimator is the offline measurement of that delay from a dataset. History depth and what happens when a delay is too old are this feature point. Quality gates that decide whether a fix is used at all remain FP-05.

**This feature point uses FP-02 and FP-03.**

**Normal behavior:**

- A GNSS, local-position, or yaw measurement may be older than the current IMU epoch by a known latency. The filter fuses that sample against the navigation state that was valid at the measurement’s time of validity, not as if it had arrived at the current IMU timestamp. This is the path GNSS receivers need: processing, internal filtering, and serial transport commonly add 100–200 ms.
- Delays up to 500 ms are fused this way when the history still holds that time of validity. A delay of zero is current-time fusion (the usual case).
- On a moving trajectory, a GNSS position that is 200 ms late, fused with that delay stated, produces a smaller along-track position error than the same sample fused as if it were current. The difference is visible as soon as the vehicle has non-zero speed.
- The Python replay estimator, given a dataset that has IMU, barometer, and GNSS with usable vertical velocity, plus a real climb or descent, reports a latency matching the lag between the near-zero-latency barometric vertical velocity and GNSS vertical velocity. Forcing the estimator on a dataset that meets those inputs produces a lag, not silence.

**Boundary / error behavior:**

- A measurement older than 500 ms is not fused as a delayed update and is not applied as a current-time update. The same skip applies when the delay is still within 500 ms but the history does not hold that time of validity. GNSS of either kind increments the no-anchor diagnostic; local-position and yaw are skipped without that count. A later in-window sample with a history match fuses; the skip is per sample.
- A delay of zero is current-time fusion (the usual case).

**Verifiable oracle:**

- Success: a 200 ms late GNSS on a moving path, with the delay stated, tracks closer to truth than the same bytes fused with delay zero; a 80 ms delayed Python GNSS push is accepted; a sample 600 ms late is not applied as a current-time update; an in-window delay with no history match is likewise not applied as current-time, and GNSS of that kind raises the no-anchor diagnostic; the replay delay estimator on a climb/descent dataset with baro and GNSS velocity reports a peak lag.
- Failure / absence: every GNSS is applied at the IMU timestamp regardless of the stated delay, so a 200 ms-late receiver biases position by velocity × 0.2 s during motion; delays above 500 ms, or an in-window delay with no history match, still move the current state as if they were now; the estimator never produces a lag on a dataset that has a clear climb.

---

### FP-05: Quality gates, coasting, and re-acquisition

**Public entry:** INS options (and the matching `config.yaml` / Python config fields) that set GNSS fusion / entry / exit thresholds, the coasting window, unlimited dead reckoning, and the re-acquire / stop-disable switches. Observable outcomes are the ready flag, whether position accessors still succeed, dead-reckoning age, and — when the caller is the suite of FP-08 — the solution mode.

**This feature point uses FP-02.** It refines when the 3D solution of FP-02 is entered, held, frozen, or given up. Suite mode names are defined in FP-08; this FP states the INS-side conditions those modes read.

**Normal behavior:**

- Three distinct GNSS quality questions:
  1. **Fusion gate:** may this one fix be fused. Default limits equal the accuracy caps (120 m position, 60 m/s velocity), so an unconfigured filter does not reject a fix for reported accuracy alone; it caps and fuses. A broken (non-positive) covariance is always rejected. A caller who wants a hard accuracy gate sets the fusion limits below the caps.
  2. **Entry gate:** may the 3D solution start. Defaults: 2 m horizontal and 3 m vertical position 1-sigma, 0.25 m/s horizontal and 0.30 m/s vertical velocity 1-sigma, held for a 5 s dwell (the dwell can be disabled so the first good fix starts 3D). Fixes that are fusable but coarser than this keep being consumed without ever starting 3D.
  3. **Exit gate:** must the 3D solution be given up. Defaults: 5 m / 7 m position, 0.4 / 0.5 m/s velocity, for a 10 s dwell. When the dwell of bad fixes elapses, INS re-arms into collecting: initialized becomes false, position and velocity accessors fail (nothing keeps drifting off bad fixes), and a later return is a full re-bootstrap through the entry gate. IMU biases are carried into that re-bootstrap at an inflated uncertainty. The exit can be disabled so the filter never leaves 3D on GNSS quality alone. Setting auto_reacquire_disable, when that dwell of bad fixes elapses, keeps the filter running and only clears ready, without a full re-arm, so ready is false while the instance stays initialized and position accessors still succeed.
- **Coasting window:** INS tracks milliseconds since the last absolute position aiding (GNSS or local position) and publishes that age while it is initialized; an INS that is not initialized publishes no age (the age accessor returns -1). While the age is within the window (default 10 s) and INS is otherwise ready, ready stays true: this is IMU-only dead reckoning with a drifting position. Once the age exceeds the window, ready becomes false and the whole instance freezes — strapdown, covariance, attitude, biases, position, and velocity hold their last value — until re-acquisition. A fusion-usable GNSS velocity that arrives inside the expired window without a usable position is still fused into that held state: it does not re-anchor, ready stays false, and the coasting age keeps counting. Unlimited dead reckoning disables the window: ready does not degrade on IMU-only time, and freeze / re-acquire do not apply. After an IMU-only gap longer than that window, the next fusion-usable GNSS that carries a position offset is ordinary fusion, not a freeze re-anchor: published ECEF moves toward that offset relative to skipping those same bytes, yet stays farther from the offset than an unlimited-off freeze-reanchor twin of those same bytes, and published yaw 1-sigma stays on the pre-gap scale rather than jumping to the freeze-reanchor unknown. Ready staying true through the gap is not that contrast.
- **Re-acquisition** after an expired window (unlimited off): the next usable position fix that passes the fusion gate re-anchors the 3D solution and ready is true on that epoch — not an entry-dwell bootstrap. Attitude and IMU biases are kept across the freeze; yaw uncertainty is reset to unknown unless a heading hint is supplied. With the navigation suite (FP-08), that hint is the parallel AHRS/ARS.
- **GNSS fusion rate limit:** by default at most one fused GNSS epoch per 100 ms. Faster streams are skipped whole and counted. The limit is suspended while the coasting window is expired so a tunnel exit is not paced. A related position-decimation option, default off, spends only every Nth combined position-and-velocity epoch as a position fuse (the rest fuse velocity alone) to avoid double-counting a receiver’s internally coupled solution.

**Boundary / error behavior:**

- A prescribed (non-auto) init is the caller’s assertion and is not held at the entry dwell.
- Vertical position rows that the height-source choice of FP-03 has dropped are ignored by the fusion and exit gates, not the entry gate: a barometric-height run does not leave 3D because GNSS vertical accuracy is poor. The entry gate still grades GNSS vertical accuracy at bootstrap, before the height source is latched.
- When unlimited dead reckoning is on, a large forward time gap skips that epoch; subsequent normal-rate epochs run again rather than remaining stuck on the same jump.

**Verifiable oracle:**

- Success: a stream whose GNSS 1-sigma is 10 m stays fusable but, with default entry gates, never becomes ready 3D until the caller raises the entry gate or the stream improves; a 5 s run of entry-quality fixes with the default dwell does start 3D; after 10 s of exit-quality-or-worse fixes, ready is false and position accessors fail until a full re-bootstrap; with auto_reacquire_disable set, that same dwell leaves ready false while the instance stays initialized and position accessors still succeed, the filter still running without a full re-arm; during a 3 s GNSS outage inside a 10 s window, ready stays true and dead-reckoning age is about 3000 ms; after 11 s of IMU-only (unlimited off), ready is false and the state no longer integrates; the first fusion-usable position fix after that freeze re-anchors and ready is true on that epoch; unlimited dead reckoning keeps ready true through that 11 s; after that 11 s with unlimited on, the next fusion-usable GNSS with a position offset is ordinary fusion — published ECEF closer to the offset than a skip of the same bytes, farther than the unlimited-off freeze-reanchor twin, yaw 1-sigma still on the pre-gap scale; a 50 Hz GNSS stream with the default rate limit does not fuse every sample.
- Failure / absence: any GNSS sample starts 3D on the first epoch regardless of reported 10 m accuracy; expired coasting keeps publishing an integrating (not frozen) position with ready true; quality-loss keeps publishing drifting ECEF; unlimited mode still freezes at 10 s; under unlimited, that next offset GNSS after the gap is skipped or snapped as a freeze re-anchor; tunnel-exit GNSS is rate-limited away.

---

### FP-06: ARS and AHRS attitude

**Public entry:** The standalone attitude-filter instance, in either ARS or AHRS mode, and the two instances the navigation suite (FP-08) runs in parallel. Helpers that estimate roll/pitch from a static accelerometer sample and yaw from a tilt-compensated magnetometer sample are part of this surface. INS attitude is FP-02; this FP is the IMU-only (plus optional magnetometer) attitude path.

**This feature point uses FP-01.** True-north yaw uses the WMM of FP-01.

**Normal behavior:**

- Exactly two modes, fixed per instance:
  - **ARS:** roll and pitch are corrected from the accelerometer against gravity; yaw is the integral of the bias-corrected z-rate and is never measurement-corrected. Gyro bias is estimated online. Earth rate is not corrected.
  - **AHRS:** as ARS, plus yaw is stabilized with tilt-compensated magnetometer heading. Magnetic disturbances do not tilt roll/pitch. Until a geographic position and decimal year are supplied, yaw is relative to magnetic north; after they are supplied, WMM declination is applied and yaw is relative to true north. Switching declination steps the published yaw by the declination change (it does not slew there through magnetometer fusion). The published gyro-bias estimate does not jump.
- Configuration fields left at zero take documented defaults. For a standalone instance the initial-attitude standard deviations are mandatory (roll and pitch; yaw too in AHRS mode); a non-positive or non-finite standard deviation, or a non-finite initial attitude, is refused at init.
- On the reference scenario — 100 Hz IMU with Gaussian gyro noise of spectral density 0.0001 (rad/s)/√Hz and accelerometer noise of 0.05 m/s², constant gyro bias of 1 / −2 / 0 °/s, initial roll/pitch error of 3°, static body — within 10 s the filter converges to roll/pitch within 0.2° of truth and x/y gyro bias within 0.1 °/s.
- In ARS mode, a constant z-rate integrates into yaw with no magnetometer or GNSS correction, even when a magnetometer is present on the instance (the instance is ARS). In AHRS mode, a persistent heading error is pulled toward the magnetic (or true-north) reference.
- An explicit zero-rotation flag is opt-in: the caller (or the suite, using INS’s standstill detector) flags known zero body rate; the filter then fuses a direct gyro-bias measurement. While roll and pitch are published, that attitude solution carries no velocity, unlike the navigation filter’s velocity on the same stream. A count of private estimate components is the implementer’s and is not scored.
- The suite’s ARS bootstraps roll/pitch from the first valid IMU; its yaw is 0 unless a known heading was supplied (prescribed INS attitude or a static yaw hint). The suite’s AHRS waits for the first magnetometer sample before starting. If after an ARS or AHRS instance has been producing a solution the reported attitude 1-sigma stays implausibly large (for example after a long outage of the correcting sensor left that 1-sigma unreduced), that instance’s attitude accessors fail. Implausibly large means above the attitude filter's precision-restart thresholds — by default 10° roll or pitch, or 90° yaw, once 10 s have passed since init. The suite then re-bootstraps on the next suitable epoch — IMU for ARS, a magnetometer sample for AHRS — so those accessors succeed again without the caller re-initing; a standalone caller must re-init. First-start publication, a dropped epoch, skipped fusion, or a specific-force sample far from g that only withholds leveling, is not that contrast.

**Boundary / error behavior:**

- Non-finite gyro or accelerometer samples drop the epoch; a non-finite magnetometer sample is ignored; both increment the invalid-input counter. The next valid epoch proceeds.
- A backwards timestamp skips that epoch; later increasing timestamps continue. A forward gap larger than 0.2 s skips attitude integration for that epoch (sensor-outage semantics).
- Magnetometer heading fusion is skipped near gimbal lock, for near-zero fields, and when the de-tilted horizontal field is unusable.
- An optional field-strength gate (off by default), when enabled and a position is known, downweights (does not drop) a heading sample whose magnitude disagrees with the WMM total field by more than a tolerance (default 30%).

**Verifiable oracle:**

- Success: ARS versus AHRS are distinguishable: ARS yaw drifts with residual z-bias while AHRS yaw is pulled to the mag reference; the 10 s reference scenario meets 0.2° / 0.1 °/s; supplying a position steps yaw by the WMM declination; a static leveling helper on (0, 0, −g) reports near-zero roll and pitch; a finite mag sample after NaN gyro epochs still yields a finite attitude; suite ARS starts on IMU alone, suite AHRS does not start until a mag sample; standalone init refuses a non-positive mandatory standard deviation or a non-finite initial attitude, and accepts a zero attitude; while roll and pitch are published, the attitude solution carries no velocity; after a published solution whose attitude 1-sigma stays implausibly large, that instance’s attitude accessors fail then succeed again on the suite’s next suitable epoch, while a standalone instance stays unpublished until the caller re-inits.
- Failure / absence: a single mode that always uses the magnetometer, or never; ARS yaw is pulled to mag heading; the reference scenario stays at the 3° initial error past 10 s; declination is applied by slowly fusing mag rather than stepping yaw; NaN gyro corrupts the published attitude; init refuses a zero attitude, or ARS init fails when yaw standard deviation is left at zero; the attitude solution carries a velocity while roll and pitch are published; after that degraded 1-sigma the instance keeps publishing, or the suite never recovers.

---

### FP-07: Barometric vertical channel

**Public entry:** The standalone barometric vertical-channel instance, and the same filter inside the navigation suite (FP-08). INS-internal barometric height selection is FP-03; this FP is the independent vertical filter and the three height systems.

**This feature point uses FP-01** for timestamps and the body-to-NED rotation supplied each epoch.

**Normal behavior:**

- The filter estimates three quantities: height above its start anchor (positive up), vertical velocity (positive up), and a slow additive correction to measured vertical acceleration. Between barometer samples, a level IMU plus the supplied attitude keeps height and climb rate consistent with specific force after gravity is removed. The barometer observes height only.
- Static pressure in pascals is converted to altitude with the tropospheric international standard atmosphere (sea-level standard pressure 101325 Pa maps to zero altitude), then anchored at the init pressure so that the height passed in at init (zero = “height above start”) is the datum. Implausible barometer innovations are downweighted, not dropped, so a persistent weather offset cannot deadlock the filter.
- A separate offset estimate tracks the slowly varying difference between a local height (above the caller’s vertical datum) and GNSS ellipsoid height — the ellipsoid height of the datum origin. Local height plus that offset is an absolute height during a GNSS outage. How fast that offset tracks is the implementer’s and is not scored. Pairs without a positive GNSS vertical variance are skipped.
- After a few seconds of realistic pressure around a pad plus a level IMU, height stays near the anchor (zero if started at zero) and vertical velocity stays near zero. Climbing then holding a new pressure yields a higher local height of the same sign as the ISA altitude change.
- ISA altitude is readable separately from the datum-relative height; it still carries weather and model error.
- A vertical zero-velocity update, when triggered, fuses a direct zero climb-rate measurement and is not gated on the filter’s own velocity.
- If after the instance has been producing a solution the reported height or vertical-velocity 1-sigma stays implausibly large (for example after a long barometer outage left it integrating on the accelerometer alone), height and climb-rate accessors fail. Implausibly large means above the vertical channel's precision-restart thresholds — by default 20 m height or 10 m/s vertical-velocity 1-sigma, once 8 s have passed since init. The suite then re-bootstraps so those accessors succeed again without the caller re-initing; a standalone caller must re-init.

**Boundary / error behavior:**

- Non-finite pressure or IMU samples are dropped; processing continues. Init itself reports success or failure: a non-finite anchor pressure fails; an anchor the tropospheric international standard atmosphere conversion already named in this section cannot map to a finite altitude — a negative pressure — fails; sea-level-standard pressure and ordinary tropospheric positive pressure succeed. A numeric 16 km ISA-altitude cap or below-sea-level floor on otherwise-finite positive pressure is the implementer’s and is not scored; a zero sample still maps to a finite ISA altitude, so it sits at that high-altitude extreme and is not a second scored class.
- A backwards timestamp skips that epoch; later increasing timestamps continue. A forward gap larger than 0.5 s skips IMU-driven height integration for that epoch (sensor-outage semantics) while a barometer sample on that same epoch is still fused.
- An all-zero config is valid and fills defaults (including a 2 m default barometer altitude 1-sigma).

**Verifiable oracle:**

- Success: a static pad run holds near-zero datum height and climb rate; sea-level standard pressure 101325 Pa maps to zero ISA altitude and a pressure the tropospheric international standard atmosphere assigns a few hundred metres yields that altitude within a metre; a pressure drop consistent with a climb increases ISA altitude and the datum-relative height in the same direction; GNSS plus local height produces an offset such that local height plus offset tracks ellipsoid height; during a GNSS gap that offset still converts local height into an ellipsoid height; a large barometer spike is downweighted so height does not jump to the spike; ZUPT holds climb rate near zero on a still pad; a forward gap just under 0.5 s with absurd vertical specific force still integrates, a gap just over 0.5 s does not, and a barometer sample on that over-gap epoch still fuses; after a published solution whose height or climb-rate 1-sigma stays implausibly large, those accessors fail then succeed again on the suite without the caller re-initing, while a standalone instance stays unpublished until the caller re-inits; init fails on a non-finite anchor and on a negative pressure the tropospheric ISA conversion cannot map to a finite altitude, and succeeds on sea-level-standard and ordinary tropospheric positive pressure; a numeric 16 km ISA-altitude cap or below-sea-level floor on otherwise-finite positive pressure is the implementer’s and is not scored.
- Failure / absence: pressure is treated as metres already; 101325 Pa is not zero ISA altitude; height is positive down and disagrees in sign with NED-down negated; a one-sample pressure glitch becomes the whole datum; no ellipsoid height can be formed from local height after GNSS has been seen; init accepts a non-finite or negative (ISA-undefined) anchor; NaN pressure disables the filter permanently; a 0.3 s gap is treated as an outage so IMU height is not integrated, or a >0.5 s gap also drops the barometer sample; after that degraded 1-sigma the instance keeps publishing, or the suite never recovers.

---

### FP-08: Navigation suite and graceful degradation

**Public entry:** The C navigation suite and the Python navigator. One epoch call drives INS (FP-02, FP-03, FP-05), ARS and AHRS (FP-06), the barometric vertical channel (FP-07), and the local-to-ellipsoid offset (FP-07). The caller reads one unified solution: mode, ready, best attitude, positions, velocity, and heights.

**This feature point uses FP-02, FP-05, FP-06, and FP-07.** It does not replace them: INS-only callers still exist. This FP is the arbitration and the parallel operation.

**Normal behavior:**

- Exactly four solution modes, and an observer can tell them apart:
  - **FULL:** INS is ready and the last absolute position aiding is no older than 2 seconds.
  - **COASTING:** INS is ready but the last absolute position aiding is older than 2 seconds (IMU-only, position drifting inside the coasting window of FP-05).
  - **ATTITUDE_ONLY:** INS position/velocity is not usable (not initialized, quality-loss re-arm, or expired coasting window), but ARS or AHRS is initialized so roll/pitch/yaw remain available.
  - **NONE:** nothing usable yet.
- Best-available attitude is INS when INS is ready, else the magnetometer AHRS, else ARS. A consumer keeps receiving an attitude through a GNSS outage. When the suite falls back to ARS after INS was once converged, yaw is the last good INS heading plus the yaw *change* the ARS free-integrated since — not an arbitrary zero.
- Local height (positive up, zero at the NED origin) is available whenever any local height source is running. The first source to start fixes the datum; a later source conforms so height is continuous (no jump) when a source arrives or leaves. With GNSS and barometer both present, the barometer is the outage-surviving local-height reference (FP-03). An external local-position (mocap) system owns the NED frame: the suite does not shift the INS origin out from under it; it subtracts a constant offset from every local-position sample instead.
- Ellipsoid height is reported only after a real GNSS fix has anchored the origin to WGS84. Indoor local-position-only runs do not pass off the prescribed init origin as ellipsoid height. Under GNSS, ellipsoid height comes from INS; during an outage it is local height plus the offset of FP-07. The suite reports whether an absolute height is currently available.
- The Python navigator exposes the same four mode names as text, a ready flag, roll/pitch/yaw, ECEF and local position, NED velocity, datum height, and ellipsoid height. Pushing IMU, GNSS, baro, and mag, then running the epoch, on a stationary 100 Hz IMU and 1 Hz GNSS at the origin with 2 m / 2 m / 2 m NED 1-sigma, after the FP-05 default entry dwell and the 1.5 s ready wait, yields mode FULL, ready true, and lat/lon/height matching the fix. Readers do not run the filter; skipping the epoch step leaves mode NONE.
- Outlier-rejection disable and the definition of standstill are one decision for the whole suite: constructing the suite from INS options applies those two settings to INS, ARS, AHRS, and the barometric vertical channel, so they do not have to be restated per filter.

**Boundary / error behavior:**

- Mode NONE on a null or unused instance.
- After GNSS quality-loss re-arm (FP-05), mode is ATTITUDE_ONLY; INS position accessors fail; suite attitude remains the AHRS/ARS value.
- After the coasting window expires, mode is ATTITUDE_ONLY while ARS/AHRS live; INS ready is false; INS is frozen (FP-05).
- A static initial-attitude hint, armed after suite init and before the first epoch, seeds INS auto-init and ARS yaw only until INS itself initializes; it does not bias a later re-acquisition.

**Verifiable oracle:**

- Success: the Python navigator on a stationary 100 Hz IMU and 1 Hz GNSS at the origin with 2 m / 2 m / 2 m NED 1-sigma, after the FP-05 default entry dwell and the 1.5 s ready wait, reports FULL and ready with matching lat/lon/height; dropping GNSS for 3 s inside a 10 s window yields COASTING with attitude still published and local height still available from the barometric vertical channel if a barometer is running; after the window expires, mode is ATTITUDE_ONLY, INS ready is false, and roll/pitch remain finite from ARS; the next fusion-usable position fix returns FULL on that epoch — not an entry-dwell bootstrap; a mocap-only suite run reports FULL with local position and refuses ellipsoid height; quality-loss makes INS positions unpublished while AHRS attitude continues; skipping the Python epoch step stays NONE.
- Failure / absence: a single mode bit that is only “ready/not”; GNSS outage immediately yields NONE with no attitude; local height jumps when the barometer starts; indoor mocap reports a WGS84 ellipsoid height from the init guess; the first fusion-usable fix after the expired window still waits through the entry dwell before FULL; a Python solution read itself advances the filter.

---

### FP-09: Input sanitization, outliers, and fail-safe outputs

**Public entry:** Every per-epoch update on INS, AHRS/ARS, the barometric vertical channel, and the suite, plus the diagnostic counters and the global outlier-rejection override (the same switch on the filter options and on `config.yaml`). Fusion behavior of healthy measurements is FP-02 through FP-08; this FP is what happens when inputs or published outputs are not healthy.

**Normal behavior:**

- Non-finite measurement payloads (NaN or Inf) are dropped at the API boundary and counted in the invalid-input diagnostic. A single corrupt sample does not disable the filter; the next valid epoch proceeds. Non-finite noise densities fall back to defaults. Non-finite optional fields (lever arms, cross-covariance) are treated as zero.
- Aiding measurements that are statistically implausible do not corrupt the state. Persistent absolute references (GNSS, yaw, magnetometer, barometer) are downweighted rather than rejected, so a persistent offset cannot deadlock the filter. High-rate glitchy local-position samples are skipped instead (FP-03).
- A single configuration switch disables that downweighting across every fusion filter in the suite: every measurement that would have been tested is fused at its nominal variance. Off by default. Standalone INS / AHRS / barometric-vertical-channel instances have the same switch on their own config.
- The system never publishes a non-finite navigation solution: a successful position, velocity, or attitude read after a dropped non-finite sample is finite.
- Diagnostic counters for silent reject/skip paths (timing anomalies, GNSS gating, fusion failures, auto-ZUPT triggers, invalid inputs, downweights) are readable and are not acted on by the filter. A GNSS position covariance whose diagonal entries are positive — so the fusion gate of FP-05 does not reject it as a broken (non-positive) covariance — but that is not positive definite is a fusion failure: that diagnostic increases, GNSS gating and invalid-input do not, the sample is not fused, and the next valid epoch proceeds. A backwards timestamp on INS is a timing anomaly: that diagnostic increases, invalid-input and downweight do not, the epoch is skipped, a later increasing timestamp of the same extra IMU does not increment that class, and the next valid epoch proceeds.

**Boundary / error behavior:**

- Zero-velocity and zero-rotation updates are not statistically gated.

**Verifiable oracle:**

- Success: one NaN accelerometer sample is dropped, the invalid-input counter increases, and later finite epochs still produce a finite ready solution; a persistent GNSS offset is downweighted rather than locking the filter off GNSS forever; with the override on, the same outlier is fused at full weight and the downweight counter does not increase; a GNSS position covariance with positive diagonals that is not positive definite increments fusion-failure without incrementing GNSS gating or invalid-input, is not fused, and later finite epochs still produce a finite ready solution; a backwards timestamp on INS increments timing-anomaly without incrementing invalid-input or downweight, skips that epoch, a later increasing timestamp of the same extra IMU does not increment timing-anomaly, and later finite epochs still produce a finite ready solution.
- Failure / absence: NaN IMU poisons all subsequent positions; an outlier GNSS is hard-rejected so a biased receiver deadlocks 3D; the override still downweights; diagnostics are missing so skipped GNSS is indistinguishable from fused GNSS; that illegal GNSS covariance is fused, or fusion-failure is the same increment as GNSS gating or as invalid-input; that backwards INS timestamp is applied, or timing-anomaly is the same increment as invalid-input or as downweight, or a later increasing timestamp also increments timing-anomaly.

---

### FP-10: Dataset replay from CSV and config.yaml

**Public entry:** The C replay harness and the Python replay program, both consuming a dataset directory; and the Python YAML runner that maps custom CSVs into the same navigator loop. Live UDP and the Qt GUI are non-goals. Filter semantics of what is replayed are FP-02 through FP-09.

**This feature point uses FP-08** (it drives the navigation suite). The file layout and harness behavior are this FP.

**Normal behavior:**

- A dataset directory contains one `config.yaml` and CSV streams. Both replay harnesses require the IMU stream and the reference trajectory; GNSS is required when aiding is `gnss`; magnetometer, barometer, and speed are optional. Conventional names, each with a leading `#` header line and a first column `t_us` in microseconds, then:
  - `imu.csv` — gyro FRD x/y/z [rad/s], accelerometer FRD x/y/z [m/s²]; an optional eighth column IMU die temperature [°C] is ignored by both harnesses.
  - `ref.csv` — latitude [deg], longitude [deg], height [m], roll/pitch/yaw [deg], NED velocity north/east/down.
  - `gnss.csv` — latitude [deg], longitude [deg], height [m]; the six unique NED position-covariance entries in the order north-north, north-east, north-down, east-east, east-down, down-down [m²]; NED velocity north/east/down; the six unique NED velocity-covariance entries in that same packed order [(m/s)²]; and a velocity-valid flag. Zero diagonal means “unknown” and is replaced at replay time by the config fallback: the horizontal position fallback for north and east, the vertical one for down, and the velocity fallback for each velocity axis.
  - `mag.csv` — magnetometer FRD x/y/z [µT].
  - `baro.csv` — static pressure [Pa].
  - `speed.csv` — scalar ground speed [m/s]; per-sample uncertainty and delay come from `config.yaml`, not extra columns.
- An `inputs:` section may override those filenames per stream, relative to the `config.yaml` directory. Unset keeps the conventional name.
- `config.yaml` tells the harness how to run: aiding mode, init mode, IMU noise model (required), lever arms, gates, calibration, and scoring limits. Every key is optional except the IMU gyro and accelerometer spectral densities (and, when aiding is `ref`, the GNSS fallback standard deviations: a horizontal-and-vertical position pair and one velocity value). Those required values must be written and positive: omitting one or writing 0 for any of them, including either element of the position pair, aborts the run with no scored solution; a positive written value lets the same directory run. Optional keys still treat 0 as the built-in default. Both harnesses reject an unknown key and name it: a typo must not produce a full scored run. Two sections used only by other tools in the same directory — the local-frame origin block and the radio-link block — are accepted and ignored by both replay harnesses.
- `aiding` is exactly one of: `gnss` (real per-epoch covariance from `gnss.csv`), `ref` (fix synthesized from `ref.csv`), `none` (no absolute position aiding). Unrecognized aiding values are refused with a non-zero exit; `none` is not that refusal. On `none`, INS stays uninitialized for the whole log and ARS attitude still exists. Omitting the optional barometer is legal. A present barometer still runs the vertical channel, observed as published local height: matching pad pressure stays near the pad, and a pressure drop consistent with a climb yields a higher local height of the same sign as that altitude change. That height contrast is not scored on the C harness process exit. `init` is `auto` or `ref`.
- Replaying a committed dataset directory that includes IMU, GNSS, and the reference trajectory (for example the fog trial or a simulated profile) produces a navigation solution for the length of the log: modes move through FULL when GNSS is present, and the published lat/lon/height is a fused INS solution, not a copy of the reference. Both harnesses compare that solution to the reference; a violation of configured regression limits fails the C harness with a non-zero exit. That C exit is the GNSS-aided INS scoring gate, where INS samples exist; it is not the none-run barometer contrast.
- The Python replay additionally accepts the directory or the `config.yaml` path and can estimate GNSS delay (FP-04). The C harness is the regression gate used by the dataset target. Optional plot and Google Earth export exist on the Python replay; they are not independently graded (see Non-goals).
- The Python YAML runner reads a different YAML that names *arbitrary* CSV files and column mappings. Time unit is one of s / ms / µs. Gyro is deg/s or rad/s. Accelerometer is m/s² or g. Pressure is Pa, hPa, mbar, or kPa. Magnetometer is µT, gauss, mGauss, or nT. GNSS position is geodetic degrees, radians, or ECEF. It merges streams by timestamp (IMU begins each epoch; the latest GNSS/baro/mag sample at or before t is attached) and writes a solution CSV with one row per epoch: mode, lat/lon/h, NED position and velocity, roll/pitch/yaw, arbitrated heights. Milligauss-scale counts labeled mGauss are converted onto the microtesla convention; that conversion is not scored on those columns. A 30 s static IMU-plus-GNSS mapping in mixed units produces a solution file whose mode is FULL and whose position matches the GNSS pad.

**Boundary / error behavior:**

- Missing IMU stream or missing reference trajectory: the run does not succeed.
- `aiding: gnss` without a GNSS stream: the run does not succeed.
- Unknown `config.yaml` keys and unknown `aiding` values fail the run with a non-zero exit and identify the offender. Keys that belong to other tools in the same directory are accepted when they are on the shared known-schema list and ignored by that harness; a typo *inside* a section the harness owns remains an error. The two foreign sections named above are on that list.
- The C regression harness refuses a dataset that does not state a positive scoring minimum-epoch count. The Python replay fills a zero default and still produces a solution.
- Comment lines and malformed CSV lines are skipped; mixed sample rates are allowed.

**Verifiable oracle:**

- Success: replaying a GNSS-aided dataset directory yields a fused trajectory distinct from both raw GNSS and `ref.csv` and a zero exit when within that dataset’s limits; `aiding: none` keeps INS uninitialized for the whole log while ARS attitude still exists and is not the unknown-aiding refusal; a present barometer on none publishes local height that stays near the pad under matching pad pressure and is higher, of the same sign as the altitude change, after a pressure drop consistent with a climb, and that contrast is not the C none exit; `aiding: not-a-mode` exits non-zero; `aiding: gnss` with no GNSS stream exits non-zero; a directory without the reference trajectory does not succeed; a misspelled IMU noise key aborts before a score; omitting a required IMU density or writing 0 for it aborts before a score, and the same omit-or-zero abort applies to the GNSS fallbacks when aiding is `ref`; a positive written value of each lets the same directory run; an origin or radio-link section in the same file does not abort replay; the YAML runner’s mixed-unit static pad writes FULL and a lat/lon near the GNSS pad; `t_us` is the time base of the dataset CSVs.
- Failure / absence: replay prints `ref.csv` as the solution; unknown keys are ignored and the run “succeeds”; `aiding: none` still reports FULL; a present barometer on none leaves local height unpublished, or matching-pad and climb-pressure local heights are indistinguishable; a missing or zero required IMU density, or a missing or zero GNSS fallback under aiding: `ref`, still produces a scored run; the runner does not convert deg/s or hPa and the solution is nonsense; only Python replay works and the C harness cannot consume the same directory.
