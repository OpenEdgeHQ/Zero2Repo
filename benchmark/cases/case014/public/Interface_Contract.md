### Product overview

**NAVFILTER** is a portable C11 library for 3D navigation state estimation. Its core is a set of Kalman filters that fuse an inertial measurement unit (IMU: accelerometer and gyroscope) with aiding sensors — GNSS/GPS, barometer, magnetometer, local position references, absolute yaw, scalar ground speed, and zero-velocity / zero-rotation information — into one estimate of where the body is and which way it is pointing.

A first-time integrator zeros one caller-owned filter instance, hands it a coarse Earth anchor and options (almost every field left at zero picks a conservative consumer-MEMS default), then feeds a stream of IMU epochs with whatever aiding is present that epoch. After a short warm-up the filter reports a ready navigation solution: WGS84 position, local NED velocity, and body-to-NED attitude. Frame helpers, WGS84 geodesy, and the World Magnetic Model lookup run without constructing a filter instance.

Typical uses: drones and autonomous vehicles, robotics, aerospace, cars, embedded tracking, and post-processing of recorded flights or drives. The same filters are reachable from C and from a Python package that wraps the compiled library. Recorded trials are replayed from a dataset directory of CSV streams plus one `config.yaml`. Arbitrary CSVs are mapped by `python -m NAVFILTER` with a mapping YAML; that runner entry is specified below.

The finished product is a **C11 library** plus a matching **importable Python package**. There is no network stack inside the filters. Integrators compile the C sources into firmware or a desktop program, or build the shared library and use the Python package.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Shape of the public surface

The public surface is a **C library** (headers at the include-directory root) plus a **Python package** spelled `NAVFILTER`. Callers compile against the headers with `#include "…"` after adding the C include directory (`src/`) and the linear-algebra include directory (`NavCore/c`). Python callers write `from `NAVFILTER` import …` or `import `NAVFILTER``.

**C headers.** Independently verifiable C entries are reached by including:

- `geodetic_toolbox.h` — Hamilton quaternion helpers, WGS84 ECEF ↔ geodetic conversions, NED transport rate, gravity, small helpers
- `magnetic_model.h` — World Magnetic Model lookup (declination, inclination, total field, NED field)
- `linalg.h` — column-major linear algebra; the `MAT_ELEM` accessor used when rotating a body vector by `ins_quat_to_rotmat`
- `ins.h` — the 3D INS filter
- `ahrs.h` — standalone ARS / AHRS attitude filters
- `baro_alt.h` — standalone barometric vertical channel
- `nav_suite.h` — wrapper that runs INS, ARS, AHRS, and the barometric channel from one measurement stream
- `log.h` — optional diagnostic logging
- `kalman_udu.h` — UDU Kalman update / predict used by the filters
- `ins_capi.h` — thin C ABI over INS / nav_suite for language bindings (include directory `python/csrc`)

A translation unit that includes `geodetic_toolbox.h`, `linalg.h`, and `magnetic_model.h` compiles the geodetic / quaternion / WMM surface without constructing an INS instance.

**C library artifact.** The shared library stem is `NAVFILTER`. The linked artifact is `libNAVFILTER.so` (or `libNAVFILTER.dylib` / `libNAVFILTER.dll` on other hosts). Including the public headers without linking that library must not produce a successful call of `ins_quat_from_rpy` or `magnetic_declination_deg`. The C standard is C11; link libm (`-lm`).

**Python package.** The importable package directory is `NAVFILTER`. The package loads `libNAVFILTER.so` from inside the package directory. Independently verifiable package-root entries for frames, geodesy, and the World Magnetic Model are:

- `rpy_to_quat` — Hamilton quaternion from roll/pitch/yaw (same mapping as `ins_quat_from_rpy`)
- `llh_to_ecef` — WGS84 geodetic (radians, metres) to ECEF metres
- `ecef_to_llh` — ECEF metres to geodetic (radians, metres)
- `wmm_field_ned` — World Magnetic Model NED field in µT (wraps `magnetic_field_ned_uT`)

An independently verifiable Python helper, imported from `geodetic_toolbox` rather than from the `NAVFILTER` package root, is:

- `mag_heading` — tilt-compensated magnetic heading (same three arguments as `ahrs_mag_heading`)

`geodetic_toolbox` is a module file in the same directory as the package directory (`python/geodetic_toolbox.py` beside the package), not a submodule of the package, so the import path that finds the package also finds it.

Filter-facing Python entries (`Navigator` / `Ins` wrappers) belong with those symbols. After `Ins`(`Config`(...)), the INS wrapper uses a three-move loop: push IMU (and any GNSS), run one epoch, then read. Readers do not run the filter. The suite wrapper is started as `Navigator`(`Config`(...)) with `auto_init`, `lat_rad`, `lon_rad`, `h_m`, `allow_unlimited_deadreckoning`, and optional `rpy_init_rad`; a failed start raises `ValueError`, the same as `Ins`. Argument shapes and return shapes belong with those INS and suite symbols, not here. `python -m NAVFILTER <mapping.yaml>` is the YAML custom-CSV runner. The mapping YAML is nested and distinct from a dataset `config.yaml`. Its section keys, column maps, format tokens, merge-at-or-before rule, `csv_hz` of 0, and solution-CSV columns are specified in the section below. The Python dataset-replay program is `replay.py`; it takes a dataset directory (or the `config.yaml` path in that directory). The C dataset-replay program takes the same dataset directory and an optional second path; that dump row shape belongs with that program. The force-on estimator switch, the plot-rate flag, and the dataset CSV plus `config.yaml` layout belong with `replay.py`.

**Not in this surface.** A network protocol. A public reference-board firmware. Live UDP ingest as a graded capability. Heap, threads, or an OS abstraction inside the core filters.

### Naming conventions

**Product and package.** The product identity is NAVFILTER. The importable Python package, the shared-object stem, and the library identity use the spelling `NAVFILTER`.

**C entries.** Snake_case. Quaternion / geodesy helpers are prefixed `ins_` even when they do not require an INS instance (`ins_quat_from_rpy`, `ins_latlonh_to_ecef`, …). World Magnetic Model lookups use the `magnetic_` prefix (`magnetic_declination_deg`, `magnetic_inclination_deg`, `magnetic_field_strength_uT`, `magnetic_field_ned_uT`). Attitude-filter entries are prefixed `ahrs_`. Barometric vertical-channel entries are prefixed `baro_alt_`. Suite entries are prefixed `nav_suite_`. Instance types end in `_t` (`ins_t`, `ahrs_t`, `baro_alt_t`, `nav_suite_t`). Timestamps are `ins_time_us_t` / `ahrs_time_us_t` / `baro_alt_time_us_t`, aliases of a signed 64-bit microsecond count.

**Python entries.** The geodetic / quaternion / WMM names on the package root are unprefixed: `rpy_to_quat`, `llh_to_ecef`, `ecef_to_llh`, `wmm_field_ned`. They are not aliases of the C spellings; both spellings are published. `mag_heading` is imported from `geodetic_toolbox`, not from the `NAVFILTER` package root.

**Frames.** Body is FRD (x forward, y right, z down). Navigation is NED (north, east, down). Attitude is a Hamilton quaternion, scalar first, mapping body to NED. Roll, pitch, yaw are Tait-Bryan ZYX in radians unless a file format says degrees. Matrices are column-major. Specific force of a vehicle sitting still on a level pad is near (0, 0, −g) in FRD.

**Defaults.** A configuration field left at zero (or an all-zero list) means “use the built-in default”, never “inject zero noise”. An all-zero options block is a working, conservative filter.

**Error text.** Wording of log lines is informational. Graded behavior is success versus failure, ready versus not, which solution mode, whether a value is published, and diagnostic counters — not a particular sentence.

### Global observables an implementer must reproduce

**No product config file for the core filters.** The filters do not read a configuration-file syntax of their own. Dataset replay uses one `config.yaml` plus CSV streams in a dataset directory; that layout belongs with `replay.py`.

**Library substrate.** When `geodetic_toolbox.h` is not available on the include path, a program that includes that header and calls `ins_quat_from_rpy` does not compile. When the `NAVFILTER` package is not importable, `from `NAVFILTER` import `rpy_to_quat`` does not run to completion.

**WGS84.** Geodetic conversions use the WGS84 ellipsoid (semi-major axis 6378137.0 m, flattening 1/298.257223563), not a spherical Earth. Double precision is used for the ECEF / lat-lon-height anchor. The per-epoch filter hot path is 32-bit IEEE-754 float.

**World Magnetic Model.** The lookup, given latitude, longitude, and a decimal year, returns magnetic declination in degrees (positive east), inclination in degrees (positive down in the northern hemisphere), total field in microtesla, and a three-axis NED reference field in microtesla. Latitude is clamped to [−90°, +90°]. Longitude is wrapped into (−180°, +180°]. Out-of-range years are extrapolated rather than refused.

**Determinism.** Per-epoch work has a bounded worst-case execution time: no unbounded loops, no recursion, no iteration counts that depend on measurement values. Core filters use no heap.

**Platforms.** POSIX and Windows are both intended. Documented execution is Linux x86_64 with a C11 compiler. Hardware is CPU-only.

**Python / C agreement.** For the same roll/pitch/yaw, `ins_quat_from_rpy` and `rpy_to_quat` produce matching Hamilton components to 1e-5. For the same geodetic position, `ins_latlonh_to_ecef` / `ins_ecef_to_latlonh` and `llh_to_ecef` / `ecef_to_llh` round-trip to 1e-10 rad / 1e-4 m. The Python NED field from `wmm_field_ned` matches C declination and total field as described under those symbols.

## python -m NAVFILTER

`python -m NAVFILTER <mapping.yaml>` is the custom-CSV runner. The argument is a nested mapping YAML: a section, then a key. That file is distinct from a dataset `config.yaml`. Dataset `config.yaml` keys stay with `replay.py`. Relative file paths resolve against the YAML's directory.

Sections and keys:

- `imu` takes `file`, `time`, `gyr`, and `acc`.
- `gnss` takes `file`, `format`, `time`, `pos`, and `stddev_ned`, plus optional `vel_ned`. `format` is `llh_deg` (geodetic degrees), `llh_rad` (radians), or `ecef` (ECEF).
- `baro` takes `file`, `time`, and `pressure`.
- `mag` takes `file`, `time`, and `mag`.
- `wmm` takes `year` (a decimal year).
- `filter` takes `auto_zupt_disable`.
- `output` takes `csv` and `csv_hz`, and also accepts the booleans `plotjuggler` and `mavlink`.

A column map for time or a scalar field is `{col, unit}`. A column map for a 3-vector is `{cols, unit}` with three columns. GNSS `pos` names its three columns; the frame is the `format` token, so that map need not carry a unit. Each column is a 0-based index or a header-row name.

Unit tokens: time is `s`, `ms`, or `µs` (also the ASCII token `us`); gyro is `deg/s` or `rad/s`; accelerometer is `m/s²` or `g` (also the ASCII token `m/s2`); pressure is `Pa`, `hPa`, `mbar`, or `kPa`; magnetometer is `µT`, `gauss`, `mGauss`, or `nT` (also the ASCII token `uT`). GNSS position is geodetic degrees, radians, or ECEF, selected by `llh_deg`, `llh_rad`, or `ecef`.

`csv_hz` of 0 writes one solution row per IMU epoch. IMU begins each epoch. The latest GNSS, barometer, and magnetometer sample at or before that IMU epoch is attached.

The solution CSV begins with a header row. Columns are identified by header name, and a contestant may add columns. An unpublished value is an empty cell. Header-name stems:

- time in microseconds: `t_us` (also `time`)
- `mode`
- latitude and longitude in degrees: `lat` and `lon`
- ellipsoidal height: `h_ell` or `alt` (also `h_m` and `height_ell`)
- NED position north/east/down: `pos_n`, `pos_e`, `pos_d` (also `north`, `east`, `down`)
- NED velocity north/east/down: `vel_n`, `vel_e`, `vel_d`
- roll, pitch, and yaw in degrees: `roll`, `pitch`, `yaw`
- arbitrated height: `height_m` (also `height`)

## `acc`

Published member `acc`.

It appears on:

- `ins_measurements_t` (`ins_meas3_t acc`)
- `ins_t` (`float acc[3]`)

## `acc_bias`

Published member `acc_bias`.

It appears on:

- `ins_state_t` (`float acc_bias[3]`)
- `ins_t` (`float acc_bias[3]`)

## `acc_bias_stddev_mps2`

Published member `acc_bias_stddev_mps2`.

It appears on:

- `ins_t` (`float acc_bias_stddev_mps2`)

## `acc_bias_window_mps2`

Published member `acc_bias_window_mps2`.

It appears on:

- `ins_t` (`float acc_bias_window_mps2`)

## `acc_mps2`

Published member `acc_mps2`.

It appears on:

- `ahrs_t` (`float acc_mps2[3]`)

## `active`

Published member `active`.

It appears on:

- `ins_t` (`bool active`)
- `ahrs_t` (`bool active`)
- `baro_alt_t` (`bool active`)
- `nav_suite_t` (`bool active`)

## `ahrs_auto_zaru_active`

Include `ahrs.h`. The C entry is `ahrs_auto_zaru_active`.

### Signature

```
bool `ahrs_auto_zaru_active`(const ahrs_t* a);
```

Compile arity is 1.

## `ahrs_correct_step`

Include `ahrs.h`. The C entry is `ahrs_correct_step`.

### Signature

```
void `ahrs_correct_step`(ahrs_t* a);
```

Compile arity is 1.

## `ahrs_get_bias_gyr`

Include `ahrs.h`. The C entry is `ahrs_get_bias_gyr`.

### Signature

```
bool `ahrs_get_bias_gyr`(const ahrs_t* a, float gyr_bias_rps[3]);
```

Compile arity is 2.

Get current gyroscope bias estimate.

## `ahrs_get_bias_gyr_stddev`

Include `ahrs.h`. The C entry is `ahrs_get_bias_gyr_stddev`.

### Signature

```
bool `ahrs_get_bias_gyr_stddev`(const ahrs_t* a, float gyr_bias_stddev_rps[3]);
```

Compile arity is 2.

Get the 1-sigma uncertainty of the current gyroscope bias.

## `ahrs_get_quaternion`

Include `ahrs.h`. The C entry is `ahrs_get_quaternion`.

### Signature

```
bool `ahrs_get_quaternion`(const ahrs_t* a, float q[4]);
```

Compile arity is 2.

Get current attitude quaternion.

## `ahrs_get_rpy`

Include `ahrs.h`. The C entry is `ahrs_get_rpy`.

### Signature

```
bool `ahrs_get_rpy`(const ahrs_t* a, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Get current attitude as roll/pitch/yaw.

## `ahrs_init`

Include `ahrs.h`. The C entry is `ahrs_init`.

### Signature

```
int `ahrs_init`(ahrs_t* a, const ahrs_config_t* cfg, ahrs_time_us_t t);
```

Compile arity is 3.

The instance may be uninitialized memory. Returns 0 on success, -1 on invalid configuration.

## `ahrs_leveling_from_acc`

Include `ahrs.h`. The C entry is `ahrs_leveling_from_acc`.

### Signature

```
void `ahrs_leveling_from_acc`(const float acc_mps2[3], float* roll_rad, float* pitch_rad);
```

Compile arity is 3.

Estimate roll/pitch from a single accelerometer sample (leveling). Works best if the sensor is at rest (specific force = reaction to gravity only).

## `ahrs_predict_step`

Include `ahrs.h`. The C entry is `ahrs_predict_step`.

### Signature

```
int `ahrs_predict_step`(ahrs_t* a, ahrs_time_us_t t, const float gyr_rps[3], const float acc_mps2[3], const float mag_b[3], bool zero_rotation_update, float* phi_out);
```

Compile arity is 7.

Time-propagation half of ahrs_update(): quaternion integration plus the (throttled) Kalman covariance prediction.

## `ahrs_set_auto_zaru_disable`

Include `ahrs.h`. The C entry is `ahrs_set_auto_zaru_disable`.

### Signature

```
void `ahrs_set_auto_zaru_disable`(ahrs_t* a, bool disable);
```

Compile arity is 2.

## `ahrs_set_position`

Include `ahrs.h`. The C entry is `ahrs_set_position`.

### Signature

```
void `ahrs_set_position`(ahrs_t* a, float lat_rad, float lon_rad, float year);
```

Compile arity is 4.

Supply the current position so the filter can apply the World Magnetic Model (declination + expected field strength).

A non-finite latitude, longitude, or year drops the whole call: the declination and the yaw reference stay as they were, so yaw stays relative to magnetic north until a call with all three finite.

## `ahrs_t`

Include `ahrs.h`. The published type is `ahrs_t`.

### Signature

```
typedef struct
{
    ahrs_config_t cfg;
    int           n;
    float q[4];
    float gyr_bias_rps[3];
    float declination_rad;
    float mag_field_expected_uT;
    float U[AHRS_UNKNOWNS_MAX * AHRS_UNKNOWNS_MAX];
    float d[AHRS_UNKNOWNS_MAX];
    float acc_lowpass_mps2[3];
    float    zaru_gyr_sum[3];
    uint32_t zaru_gyr_count;
    ahrs_time_us_t auto_zaru_static_since;
    ahrs_time_us_t auto_zaru_var_since;
    ahrs_time_us_t static_var_window_since;
    float          static_var_mean[6];
    float          static_var_m2[6];
    uint32_t       static_var_count;
    bool static_var_ok;
    bool last_zaru_trigger;
    struct
    {
        ahrs_time_us_t t;
        float          gyr_rps[3];
        float          acc_mps2[3];
        float          mag_b[3];
        bool           mag_valid;
        bool           zero_rotation_update;
        bool           active;
    } step_ctx;
    ahrs_time_us_t t_init;
    ahrs_time_us_t t_last_gyr;
    ahrs_time_us_t t_last_cov_predict;
    ahrs_time_us_t t_last_acc_fusion;
    ahrs_time_us_t t_last_mag_fusion;
    ahrs_time_us_t t_last_zero_rot_fusion;
    uint32_t       epoch;
    bool           is_initialized;
    uint32_t n_fuse_fail;
    uint32_t n_invalid_input;
    uint32_t n_acc_rejected;
    uint32_t n_restart;
    uint32_t n_downweighted;
    bool     overconfident;
    uint32_t n_overconfident;
    float    min_att_stddev_deg;
    struct
    {
        ahrs_time_us_t t_last_mag_gap_warn;
        ahrs_time_us_t t_yaw_stddev_window;
        ahrs_time_us_t t_gyr_bias_window;
        ahrs_time_us_t t_last_gyr_bias_sanity_warn;
        float yaw_stddev_window_deg;
        float gyr_bias_window_dps;
    } log_state;
} ahrs_t;
```

Members the caller compiles against:

- `cfg` — `ahrs_config_t cfg`
- `n` — `int n`
- `q` — `float q[4]`
- `gyr_bias_rps` — `float gyr_bias_rps[3]`
- `declination_rad` — `float declination_rad`
- `mag_field_expected_uT` — `float mag_field_expected_uT`
- `U` — `float U[AHRS_UNKNOWNS_MAX * AHRS_UNKNOWNS_MAX]`
- `d` — `float d[AHRS_UNKNOWNS_MAX]`
- `acc_lowpass_mps2` — `float acc_lowpass_mps2[3]`
- `zaru_gyr_sum` — `float zaru_gyr_sum[3]`
- `zaru_gyr_count` — `uint32_t zaru_gyr_count`
- `auto_zaru_static_since` — `ahrs_time_us_t auto_zaru_static_since`
- `auto_zaru_var_since` — `ahrs_time_us_t auto_zaru_var_since`
- `static_var_window_since` — `ahrs_time_us_t static_var_window_since`
- `static_var_mean` — `float static_var_mean[6]`
- `static_var_m2` — `float static_var_m2[6]`
- `static_var_count` — `uint32_t static_var_count`
- `static_var_ok` — `bool static_var_ok`
- `last_zaru_trigger` — `bool last_zaru_trigger`
- `step_ctx` — `struct { ... } step_ctx`
- `t_init` — `ahrs_time_us_t t_init`
- `t_last_gyr` — `ahrs_time_us_t t_last_gyr`
- `t_last_cov_predict` — `ahrs_time_us_t t_last_cov_predict`
- `t_last_acc_fusion` — `ahrs_time_us_t t_last_acc_fusion`
- `t_last_mag_fusion` — `ahrs_time_us_t t_last_mag_fusion`
- `t_last_zero_rot_fusion` — `ahrs_time_us_t t_last_zero_rot_fusion`
- `epoch` — `uint32_t epoch`
- `is_initialized` — `bool is_initialized`
- `n_fuse_fail` — `uint32_t n_fuse_fail`
- `n_invalid_input` — `uint32_t n_invalid_input`
- `n_acc_rejected` — `uint32_t n_acc_rejected`
- `n_restart` — `uint32_t n_restart`
- `n_downweighted` — `uint32_t n_downweighted`
- `overconfident` — `bool overconfident`
- `n_overconfident` — `uint32_t n_overconfident`
- `min_att_stddev_deg` — `float min_att_stddev_deg`
- `log_state` — `struct { ... } log_state`

Caller-owned instance. Zero before the first `ahrs_init`. Nested anonymous structs `step_ctx` and `log_state` are part of the published layout.

## `ahrs_time_us_t`

Include `ahrs.h`. The published type is `ahrs_time_us_t`.

### Signature

```
typedef int64_t `ahrs_time_us_t`;
```

Alias of `int64_t`. The published spelling is `ahrs_time_us_t`.
A monotonic timestamp in integer microseconds.

## `ahrs_update`

Include `ahrs.h`. The C entry is `ahrs_update`.

### Signature

```
void `ahrs_update`(ahrs_t* a, ahrs_time_us_t t, const float gyr_rps[3], const float acc_mps2[3], const float mag_b[3], bool zero_rotation_update);
```

Compile arity is 6.

Feed one IMU epoch and advance the filter.

A `NULL` magnetometer pointer means the magnetometer sample is absent. The epoch is not dropped, and `n_invalid_input` does not increment for that absence. The filter continues as a no-magnetometer epoch. On that epoch, ARS yaw is the integral of the bias-corrected z-rate.

ARS is not measurement-corrected by the magnetometer even when that pointer is non-null. Published ARS yaw is not pulled to the magnetometer heading.

A non-finite magnetometer sample is ignored and does increment the invalid-input counter. That sample does not drop the epoch, and the next valid epoch proceeds.

## `ahrs_zaru_applied`

Include `ahrs.h`. The C entry is `ahrs_zaru_applied`.

### Signature

```
bool `ahrs_zaru_applied`(const ahrs_t* a);
```

Compile arity is 1.

## `automotive_logged`

Published member `automotive_logged`.

It appears on:

- `ins_t` (`bool automotive_logged`)

## `baro_alt_config_t`

Include `baro_alt.h`. The published type is `baro_alt_config_t`.

### Signature

```
typedef struct {
    float h_init_stddev_m;
    float v_init_stddev_mps;
    float acc_bias_init_stddev_mps2;
    float acc_noise_mps2_sqrthz;
    float acc_bias_drift_mps2_sqrthz;
    float h_process_noise_m_sqrthz;
    float baro_stddev_m;
    float chi2_threshold;
    float zupt_stddev_mps;
    bool precision_restart_disable;
    float restart_h_stddev_m;
    float restart_v_stddev_mps;
    float restart_warmup_sec;
    bool chi2_disable;
} baro_alt_config_t;
```

Members the caller compiles against:

- `h_init_stddev_m` — `float h_init_stddev_m`
- `v_init_stddev_mps` — `float v_init_stddev_mps`
- `acc_bias_init_stddev_mps2` — `float acc_bias_init_stddev_mps2`
- `acc_noise_mps2_sqrthz` — `float acc_noise_mps2_sqrthz`
- `acc_bias_drift_mps2_sqrthz` — `float acc_bias_drift_mps2_sqrthz`
- `h_process_noise_m_sqrthz` — `float h_process_noise_m_sqrthz`
- `baro_stddev_m` — `float baro_stddev_m`
- `chi2_threshold` — `float chi2_threshold`
- `zupt_stddev_mps` — `float zupt_stddev_mps`
- `precision_restart_disable` — `bool precision_restart_disable`
- `restart_h_stddev_m` — `float restart_h_stddev_m`
- `restart_v_stddev_mps` — `float restart_v_stddev_mps`
- `restart_warmup_sec` — `float restart_warmup_sec`
- `chi2_disable` — `bool chi2_disable`

Precision restart: once `restart_warmup_sec` has passed since init (0 → 8 s), a reported height 1-sigma above `restart_h_stddev_m` (0 → 20 m) or a vertical-velocity 1-sigma above `restart_v_stddev_mps` (0 → 10 m/s) makes the instance uninitialized, so its height and climb-rate accessors fail. A negative threshold leaves that state unchecked; `precision_restart_disable` turns the check off. The navigation suite re-bootstraps its own instance; a standalone caller must re-init.

## `baro_alt_correct_step`

Include `baro_alt.h`. The C entry is `baro_alt_correct_step`.

### Signature

```
void `baro_alt_correct_step`(baro_alt_t* b);
```

Compile arity is 1.

## `baro_alt_get_acc_bias`

Include `baro_alt.h`. The C entry is `baro_alt_get_acc_bias`.

### Signature

```
bool `baro_alt_get_acc_bias`(const baro_alt_t* b, float* acc_bias_mps2);
```

Compile arity is 2.

Vertical acceleration correction a_b (added to the measured up-acceleration in the prediction).

## `baro_alt_get_height`

Include `baro_alt.h`. The C entry is `baro_alt_get_height`.

### Signature

```
bool `baro_alt_get_height`(const baro_alt_t* b, float* h_m);
```

Compile arity is 2.

## `baro_alt_get_velocity`

Include `baro_alt.h`. The C entry is `baro_alt_get_velocity`.

### Signature

```
bool `baro_alt_get_velocity`(const baro_alt_t* b, float* v_mps);
```

Compile arity is 2.

## `baro_alt_predict_step`

Include `baro_alt.h`. The C entry is `baro_alt_predict_step`.

### Signature

```
int `baro_alt_predict_step`(baro_alt_t* b, baro_alt_time_us_t t, const float acc_mps2[3], const float q_bn[4], float pressure_pa, float baro_stddev_m, bool baro_valid, float* phi_out);
```

Compile arity is 8.

Time-propagation half of baro_alt_update(): the accelerometer-driven state propagation plus the covariance prediction.

## `baro_alt_pressure_to_altitude`

Include `baro_alt.h`. The C entry is `baro_alt_pressure_to_altitude`.

### Signature

```
float `baro_alt_pressure_to_altitude`(float pressure_pa);
```

Compile arity is 1.

Barometric altitude from static pressure via the international standard atmosphere formula (p0 = 101325 Pa).

## `baro_alt_t`

Include `baro_alt.h`. The published type is `baro_alt_t`.

### Signature

```
typedef struct
{
    baro_alt_config_t cfg;
    float x[BARO_ALT_STATES];
    float U[BARO_ALT_STATES * BARO_ALT_STATES];
    float d[BARO_ALT_STATES];
    float h0_baro_m;
    baro_alt_time_us_t t_init;
    baro_alt_time_us_t t_last;
    baro_alt_time_us_t t_last_baro_fix;
    uint32_t epoch;
    bool     is_initialized;
    uint32_t n_fuse_fail;
    uint32_t n_restart;
    uint32_t n_invalid_input;
    uint32_t n_zupt;
    uint32_t n_acc_bias_prior_exceeded;
    baro_alt_time_us_t t_last_zupt;
    baro_alt_time_us_t acc_bias_prior_since;
    float    acc_bias_prior_sum;
    uint32_t acc_bias_prior_count;
    uint32_t n_downweighted;
    float last_a_up_mps2;
    bool  have_last_a_up;
    float last_h_meas_m;
    bool have_last_h_meas;
    struct
    {
        float pressure_pa;
        float baro_stddev_m;
        bool  baro_valid;
        bool  active;
    } step_ctx;
    struct
    {
        baro_alt_time_us_t t_last_gap_warn;
        baro_alt_time_us_t t_last_acc_bias_prior_warn;
    } log_state;
} baro_alt_t;
```

Members the caller compiles against:

- `cfg` — `baro_alt_config_t cfg`
- `x` — `float x[BARO_ALT_STATES]`
- `U` — `float U[BARO_ALT_STATES * BARO_ALT_STATES]`
- `d` — `float d[BARO_ALT_STATES]`
- `h0_baro_m` — `float h0_baro_m`
- `t_init` — `baro_alt_time_us_t t_init`
- `t_last` — `baro_alt_time_us_t t_last`
- `t_last_baro_fix` — `baro_alt_time_us_t t_last_baro_fix`
- `epoch` — `uint32_t epoch`
- `is_initialized` — `bool is_initialized`
- `n_fuse_fail` — `uint32_t n_fuse_fail`
- `n_restart` — `uint32_t n_restart`
- `n_invalid_input` — `uint32_t n_invalid_input`
- `n_zupt` — `uint32_t n_zupt`
- `n_acc_bias_prior_exceeded` — `uint32_t n_acc_bias_prior_exceeded`
- `t_last_zupt` — `baro_alt_time_us_t t_last_zupt`
- `acc_bias_prior_since` — `baro_alt_time_us_t acc_bias_prior_since`
- `acc_bias_prior_sum` — `float acc_bias_prior_sum`
- `acc_bias_prior_count` — `uint32_t acc_bias_prior_count`
- `n_downweighted` — `uint32_t n_downweighted`
- `last_a_up_mps2` — `float last_a_up_mps2`
- `have_last_a_up` — `bool have_last_a_up`
- `last_h_meas_m` — `float last_h_meas_m`
- `have_last_h_meas` — `bool have_last_h_meas`
- `step_ctx` — `struct { ... } step_ctx`
- `log_state` — `struct { ... } log_state`

Caller-owned instance. Nested anonymous structs `step_ctx` and `log_state` are part of the published layout.

## `baro_alt_time_us_t`

Include `baro_alt.h`. The published type is `baro_alt_time_us_t`.

### Signature

```
typedef int64_t `baro_alt_time_us_t`;
```

Alias of `int64_t`. The published spelling is `baro_alt_time_us_t`.
A monotonic timestamp in integer microseconds.

## `baro_stddev_m`

Published member `baro_stddev_m`.

It appears on:

- `baro_alt_config_t` (`float baro_stddev_m`)
- `baro_alt_t` (`float baro_stddev_m`)

## `baro_valid`

Published member `baro_valid`.

It appears on:

- `baro_alt_t` (`bool baro_valid`)

## `cholesky`

Include `linalg.h`. The C entry is `cholesky`.

### Signature

```
int `cholesky`(float* A, const int n, int onlyWriteLowerPart);
```

Compile arity is 3.

## `data`

Published member `data`.

It appears on:

- `ins_meas3_t` (`float data[3]`)
- `ins_t` (`float data[3]`)

## `decorrelate`

Include `kalman_udu.h`. The C entry is `decorrelate`.

### Signature

```
int `decorrelate`(float* z, float* Ht, float* R, int n, int m);
```

Compile arity is 5.

## `dr_frozen`

Published member `dr_frozen`.

It appears on:

- `ins_t` (`bool dr_frozen`)

## `gnss_delay_logged`

Published member `gnss_delay_logged`.

It appears on:

- `ins_t` (`bool gnss_delay_logged`)

## `gnss_pos_Qll_fuse`

Published member `gnss_pos_Qll_fuse`.

It appears on:

- `ins_t` (`float gnss_pos_Qll_fuse[3*3]`)

## `gnss_pos_vel_Qll_fuse`

Published member `gnss_pos_vel_Qll_fuse`.

It appears on:

- `ins_t` (`float gnss_pos_vel_Qll_fuse[3*3]`)

## `gnss_vel_Qll_fuse`

Published member `gnss_vel_Qll_fuse`.

It appears on:

- `ins_t` (`float gnss_vel_Qll_fuse[3*3]`)

## `gyr`

Published member `gyr`.

It appears on:

- `ins_measurements_t` (`ins_meas3_t gyr`)
- `ins_t` (`float gyr[3]`)

## `gyr_bias`

Published member `gyr_bias`.

It appears on:

- `ins_state_t` (`float gyr_bias[3]`)
- `ins_t` (`float gyr_bias[3]`)

## `gyr_bias_stddev_rps`

Published member `gyr_bias_stddev_rps`.

It appears on:

- `ins_t` (`float gyr_bias_stddev_rps`)

## `gyr_bias_window_dps`

Published member `gyr_bias_window_dps`.

It appears on:

- `ins_t` (`float gyr_bias_window_dps`)
- `ahrs_t` (`float gyr_bias_window_dps`)

## `gyr_rps`

Published member `gyr_rps`.

It appears on:

- `ahrs_t` (`float gyr_rps[3]`)

## `ins_angle_diff`

Include `geodetic_toolbox.h`. The C entry is `ins_angle_diff`.

### Signature

```
float `ins_angle_diff`(float a, float b);
```

Compile arity is 2.

Signed smallest difference (a - b) wrapped to [-pi, pi].

## `ins_apply_calibration`

Include `ins.h`. The C entry is `ins_apply_calibration`.

### Signature

```
void `ins_apply_calibration`(const ins_options_t* opt, ins_measurements_t* m);
```

Compile arity is 2.

Apply the configured sensor calibration to a measurement block.

## `ins_calc_omega_n_in`

Include `geodetic_toolbox.h`. The C entry is `ins_calc_omega_n_in`.

### Signature

```
void `ins_calc_omega_n_in`(double lat_rad, double height_m, const float vel_ned[3], float omega_n_in[3], float omega_n_ie_out[3], float omega_n_en_out[3]);
```

Compile arity is 6.

Compute rotation rate of n-frame relative to inertial frame in n-frame.

`omega_n_in = omega_n_ie + omega_n_en`. The optional Earth-rate and transport-rate outputs may be non-NULL; callers that need the transport rate pass a 3-vector for `omega_n_en_out`.

At mid-latitude, the azimuth (z) component of the transport rate changes with east velocity: 40 m/s east versus 90 m/s east are distinguishable. At the geographic poles (latitude ±90°) with a non-zero east velocity (for example 80 m/s), every component of `omega_n_in`, `omega_n_ie`, and `omega_n_en` stays finite — including the azimuth transport rate. The polar cosine floor that bounds tan(lat) is an internal bound; its numeric value is not a published constant.

## `ins_cfg_t`

Include `ins_capi.h`. The published type is `ins_cfg_t`.

### Signature

```
typedef struct {
    int64_t time_us;
    double lat_rad;
    double lon_rad;
    double h_m;
    float pos_init_stddev_m;
    float vel_init_stddev_mps;
    float rpy_init_stddev_rad[3];
    float acc_bias_init_stddev_mps2;
    float gyr_bias_init_stddev_rps;
    float pos_pred_stddev_m_sqrts;
    float vel_pred_stddev_mps_sqrts;
    float rpy_pred_stddev_rad_sqrts;
    float acc_bias_pred_stddev_mps2_sqrts;
    float gyr_bias_pred_stddev_rps_sqrts;
    float zero_vel_stddev_mps;
    float zero_rot_stddev_rps;
    float gyr_bias_init_rps[3];
    float magnetic_n[3];
    float kalman_update_dt_sec;
    float max_prediction_time_sec;
    float gnss_max_horizontal_pos_stddev_m;
    float gnss_max_vertical_pos_stddev_m;
    float gnss_max_horizontal_vel_stddev_mps;
    float gnss_max_vertical_vel_stddev_mps;
    int32_t magnetometer_min_delay_ms;
    int32_t auto_init;
    int32_t allow_unlimited_deadreckoning;
    float rpy_init_rad[3];
    float max_deadreckoning_sec;
    int32_t auto_zupt_disable;
    float mag_field_tolerance;
    int32_t mag_field_check_disable;
    int32_t estimate_mag_bias;
    float mag_bias_init_stddev_ut;
    float mag_bias_pred_stddev_ut_sqrts;
    int32_t automotive_mode;
    float automotive_min_speed_mps;
    float automotive_min_yaw_stddev;
    int32_t chi2_disable;
    float imu_acc_misalignment[9];
    float imu_gyr_misalignment[9];
    float imu_acc_fixed_bias[3];
    float imu_gyr_fixed_bias[3];
    float gnss_pos_cov_scale;
    float gnss_pos_cov_scale_height;
    float gnss_vel_cov_scale;
    float gnss_pos_stddev_floor_hor_m;
    float gnss_pos_stddev_floor_ver_m;
    float gnss_vel_stddev_floor_hor_mps;
    float gnss_vel_stddev_floor_ver_mps;
    float mag_misalignment[9];
    float mag_fixed_bias[3];
    float init_vel_ned[3];
    float chi2_reject_alpha;
    float auto_init_window_sec;
    float auto_zupt_static_gyr_rps;
    float auto_zupt_max_vel_mps;
    float gnss_start_max_horizontal_pos_stddev_m;
    float gnss_start_max_vertical_pos_stddev_m;
    float gnss_start_max_horizontal_vel_stddev_mps;
    float gnss_start_max_vertical_vel_stddev_mps;
    float gnss_stop_max_horizontal_pos_stddev_m;
    float gnss_stop_max_vertical_pos_stddev_m;
    float gnss_stop_max_horizontal_vel_stddev_mps;
    float gnss_stop_max_vertical_vel_stddev_mps;
    float gnss_init_dwell_sec;
    int32_t gnss_init_dwell_disable;
    float gnss_stop_dwell_sec;
    int32_t gnss_stop_disable;
    int32_t baro_height_disable;
    float auto_zupt_static_acc_mps2;
    float auto_zupt_max_vel_stddev_mps;
    float auto_zupt_static_gyr_stddev_rps;
    float auto_zupt_static_acc_stddev_mps2;
    float auto_zupt_dwell_sec;
    float auto_zupt_min_interval_sec;
    int32_t auto_zupt_velocity_blind_disable;
    int32_t gnss_pos_decimation;
    float speed_scale;
    float speed_stddev_rel;
    float speed_min_mps;
    float gnss_pos_stddev_cap_hor_m;
    float gnss_pos_stddev_cap_ver_m;
    float gnss_vel_stddev_cap_hor_mps;
    float gnss_vel_stddev_cap_ver_mps;
    float gnss_acc_envelope_tau_sec;
    float gnss_vel_noise_acc_scale_hor;
    float gnss_vel_noise_acc_scale_ver;
    float gnss_vel_noise_acc_window_sec;
    int32_t gnss_min_delay_ms;
} ins_cfg_t;
```

Members the caller compiles against:

- `time_us` — `int64_t time_us`
- `lat_rad` — `double lat_rad`
- `lon_rad` — `double lon_rad`
- `h_m` — `double h_m`
- `pos_init_stddev_m` — `float pos_init_stddev_m`
- `vel_init_stddev_mps` — `float vel_init_stddev_mps`
- `rpy_init_stddev_rad` — `float rpy_init_stddev_rad[3]`
- `acc_bias_init_stddev_mps2` — `float acc_bias_init_stddev_mps2`
- `gyr_bias_init_stddev_rps` — `float gyr_bias_init_stddev_rps`
- `pos_pred_stddev_m_sqrts` — `float pos_pred_stddev_m_sqrts`
- `vel_pred_stddev_mps_sqrts` — `float vel_pred_stddev_mps_sqrts`
- `rpy_pred_stddev_rad_sqrts` — `float rpy_pred_stddev_rad_sqrts`
- `acc_bias_pred_stddev_mps2_sqrts` — `float acc_bias_pred_stddev_mps2_sqrts`
- `gyr_bias_pred_stddev_rps_sqrts` — `float gyr_bias_pred_stddev_rps_sqrts`
- `zero_vel_stddev_mps` — `float zero_vel_stddev_mps`
- `zero_rot_stddev_rps` — `float zero_rot_stddev_rps`
- `gyr_bias_init_rps` — `float gyr_bias_init_rps[3]`
- `magnetic_n` — `float magnetic_n[3]`
- `kalman_update_dt_sec` — `float kalman_update_dt_sec`
- `max_prediction_time_sec` — `float max_prediction_time_sec`
- `gnss_max_horizontal_pos_stddev_m` — `float gnss_max_horizontal_pos_stddev_m`
- `gnss_max_vertical_pos_stddev_m` — `float gnss_max_vertical_pos_stddev_m`
- `gnss_max_horizontal_vel_stddev_mps` — `float gnss_max_horizontal_vel_stddev_mps`
- `gnss_max_vertical_vel_stddev_mps` — `float gnss_max_vertical_vel_stddev_mps`
- `magnetometer_min_delay_ms` — `int32_t magnetometer_min_delay_ms`
- `auto_init` — `int32_t auto_init`
- `allow_unlimited_deadreckoning` — `int32_t allow_unlimited_deadreckoning`
- `rpy_init_rad` — `float rpy_init_rad[3]`
- `max_deadreckoning_sec` — `float max_deadreckoning_sec`
- `auto_zupt_disable` — `int32_t auto_zupt_disable`
- `mag_field_tolerance` — `float mag_field_tolerance`
- `mag_field_check_disable` — `int32_t mag_field_check_disable`
- `estimate_mag_bias` — `int32_t estimate_mag_bias`
- `mag_bias_init_stddev_ut` — `float mag_bias_init_stddev_ut`
- `mag_bias_pred_stddev_ut_sqrts` — `float mag_bias_pred_stddev_ut_sqrts`
- `automotive_mode` — `int32_t automotive_mode`
- `automotive_min_speed_mps` — `float automotive_min_speed_mps`
- `automotive_min_yaw_stddev` — `float automotive_min_yaw_stddev`
- `chi2_disable` — `int32_t chi2_disable`
- `imu_acc_misalignment` — `float imu_acc_misalignment[9]`
- `imu_gyr_misalignment` — `float imu_gyr_misalignment[9]`
- `imu_acc_fixed_bias` — `float imu_acc_fixed_bias[3]`
- `imu_gyr_fixed_bias` — `float imu_gyr_fixed_bias[3]`
- `gnss_pos_cov_scale` — `float gnss_pos_cov_scale`
- `gnss_pos_cov_scale_height` — `float gnss_pos_cov_scale_height`
- `gnss_vel_cov_scale` — `float gnss_vel_cov_scale`
- `gnss_pos_stddev_floor_hor_m` — `float gnss_pos_stddev_floor_hor_m`
- `gnss_pos_stddev_floor_ver_m` — `float gnss_pos_stddev_floor_ver_m`
- `gnss_vel_stddev_floor_hor_mps` — `float gnss_vel_stddev_floor_hor_mps`
- `gnss_vel_stddev_floor_ver_mps` — `float gnss_vel_stddev_floor_ver_mps`
- `mag_misalignment` — `float mag_misalignment[9]`
- `mag_fixed_bias` — `float mag_fixed_bias[3]`
- `init_vel_ned` — `float init_vel_ned[3]`
- `chi2_reject_alpha` — `float chi2_reject_alpha`
- `auto_init_window_sec` — `float auto_init_window_sec`
- `auto_zupt_static_gyr_rps` — `float auto_zupt_static_gyr_rps`
- `auto_zupt_max_vel_mps` — `float auto_zupt_max_vel_mps`
- `gnss_start_max_horizontal_pos_stddev_m` — `float gnss_start_max_horizontal_pos_stddev_m`
- `gnss_start_max_vertical_pos_stddev_m` — `float gnss_start_max_vertical_pos_stddev_m`
- `gnss_start_max_horizontal_vel_stddev_mps` — `float gnss_start_max_horizontal_vel_stddev_mps`
- `gnss_start_max_vertical_vel_stddev_mps` — `float gnss_start_max_vertical_vel_stddev_mps`
- `gnss_stop_max_horizontal_pos_stddev_m` — `float gnss_stop_max_horizontal_pos_stddev_m`
- `gnss_stop_max_vertical_pos_stddev_m` — `float gnss_stop_max_vertical_pos_stddev_m`
- `gnss_stop_max_horizontal_vel_stddev_mps` — `float gnss_stop_max_horizontal_vel_stddev_mps`
- `gnss_stop_max_vertical_vel_stddev_mps` — `float gnss_stop_max_vertical_vel_stddev_mps`
- `gnss_init_dwell_sec` — `float gnss_init_dwell_sec`
- `gnss_init_dwell_disable` — `int32_t gnss_init_dwell_disable`
- `gnss_stop_dwell_sec` — `float gnss_stop_dwell_sec`
- `gnss_stop_disable` — `int32_t gnss_stop_disable`
- `baro_height_disable` — `int32_t baro_height_disable`
- `auto_zupt_static_acc_mps2` — `float auto_zupt_static_acc_mps2`
- `auto_zupt_max_vel_stddev_mps` — `float auto_zupt_max_vel_stddev_mps`
- `auto_zupt_static_gyr_stddev_rps` — `float auto_zupt_static_gyr_stddev_rps`
- `auto_zupt_static_acc_stddev_mps2` — `float auto_zupt_static_acc_stddev_mps2`
- `auto_zupt_dwell_sec` — `float auto_zupt_dwell_sec`
- `auto_zupt_min_interval_sec` — `float auto_zupt_min_interval_sec`
- `auto_zupt_velocity_blind_disable` — `int32_t auto_zupt_velocity_blind_disable`
- `gnss_pos_decimation` — `int32_t gnss_pos_decimation`
- `speed_scale` — `float speed_scale`
- `speed_stddev_rel` — `float speed_stddev_rel`
- `speed_min_mps` — `float speed_min_mps`
- `gnss_pos_stddev_cap_hor_m` — `float gnss_pos_stddev_cap_hor_m`
- `gnss_pos_stddev_cap_ver_m` — `float gnss_pos_stddev_cap_ver_m`
- `gnss_vel_stddev_cap_hor_mps` — `float gnss_vel_stddev_cap_hor_mps`
- `gnss_vel_stddev_cap_ver_mps` — `float gnss_vel_stddev_cap_ver_mps`
- `gnss_acc_envelope_tau_sec` — `float gnss_acc_envelope_tau_sec`
- `gnss_vel_noise_acc_scale_hor` — `float gnss_vel_noise_acc_scale_hor`
- `gnss_vel_noise_acc_scale_ver` — `float gnss_vel_noise_acc_scale_ver`
- `gnss_vel_noise_acc_window_sec` — `float gnss_vel_noise_acc_window_sec`
- `gnss_min_delay_ms` — `int32_t gnss_min_delay_ms`

## `ins_core_ctx_t`

`ins_core_ctx_t`. This type is not declared in a published header. The language-binding ABI in `ins_capi.h` hands out an opaque `void*` handle; callers include that header and do not name this type.

### Signature

```
typedef struct {
    ins_t filter;
    ins_measurements_t meas;
} ins_core_ctx_t;
```

Members:

- `filter` — `ins_t filter`
- `meas` — `ins_measurements_t meas`

The handle owns one `ins_t` instance plus one pending `ins_measurements_t` so setter calls can accumulate an epoch before an update fuses it.

## `ins_correct_step`

Include `ins.h`. The C entry is `ins_correct_step`.

### Signature

```
void `ins_correct_step`(ins_t* f);
```

Compile arity is 1.

## `ins_cross`

Include `geodetic_toolbox.h`. The C entry is `ins_cross`.

### Signature

```
void `ins_cross`(const float a[3], const float b[3], float out[3]);
```

Compile arity is 3.

Vector cross product: out = a x b.

## `ins_cross_matrix`

Include `geodetic_toolbox.h`. The C entry is `ins_cross_matrix`.

### Signature

```
void `ins_cross_matrix`(const float v[3], float M[9]);
```

Compile arity is 2.

Fill a 3x3 skew-symmetric cross-product matrix from a vector.

## `ins_dlatlonh_to_dned`

Include `geodetic_toolbox.h`. The C entry is `ins_dlatlonh_to_dned`.

### Signature

```
void `ins_dlatlonh_to_dned`(const double dlatlonh[3], double lat_rad, double height_m, float dxyz_n[3]);
```

Compile arity is 4.

Convert a small lat/lon/height delta to a position delta in NED.

## `ins_dned_to_dlatlonh`

Include `geodetic_toolbox.h`. The C entry is `ins_dned_to_dlatlonh`.

### Signature

```
void `ins_dned_to_dlatlonh`(const float dxyz_n[3], double lat_rad, double height_m, double dlatlonh[3]);
```

Compile arity is 4.

Convert small position delta in n-frame to delta in lat/lon/height.

A local NED displacement of (1.5, 0, 0) m increases latitude and does not change height. A (0, 1.5, 0) m east displacement increases longitude (north of the equator) and does not change height. A (0, 0, −1.5) m displacement (negative down) raises height by 1.5 m. Navigation quantities are NED: north, east, down; a local position of (1.5, 0, 0) m is 1.5 m north of the origin, not east or up.

## `ins_ecef_to_latlonh`

Include `geodetic_toolbox.h`. The C entry is `ins_ecef_to_latlonh`.

### Signature

```
void `ins_ecef_to_latlonh`(const double xyz[3], double* lat_rad, double* lon_rad, double* height_m);
```

Compile arity is 4.

Convert ECEF coordinates to geodetic lat/lon/height (WGS84).

Inverse of `ins_latlonh_to_ecef`. Valid globally. Converting geodetic latitude 48.783°, longitude 9.181°, height 300 m to ECEF and back recovers latitude and longitude to 1e-10 rad and height to 1e-4 m (0.1 mm). The inverse direction (ECEF → geodetic → ECEF) is consistent to the same order (3-D Euclidean error ≤ 1e-4 m).

The matching Python package entry is `ecef_to_llh` imported from `NAVFILTER`: it takes ECEF metres as three arguments and returns `(lat_rad, lon_rad, height_m)`.

## `ins_get_acc_n`

Include `ins.h`. The C entry is `ins_get_acc_n`.

### Signature

```
bool `ins_get_acc_n`(const ins_t* f, float acc_n_mps2[3]);
```

Compile arity is 2.

Get current body acceleration in the n-frame (gravity removed).

## `ins_get_bias_mag`

Include `ins.h`. The C entry is `ins_get_bias_mag`.

### Signature

```
bool `ins_get_bias_mag`(const ins_t* f, float mag_bias_uT[3]);
```

Compile arity is 2.

Get current magnetometer hard-iron bias estimate.

## `ins_get_omega_b_nb`

Include `ins.h`. The C entry is `ins_get_omega_b_nb`.

### Signature

```
bool `ins_get_omega_b_nb`(const ins_t* f, float omega_rps[3]);
```

Compile arity is 2.

Get current body rotation rate.

## `ins_get_quaternion`

Include `ins.h`. The C entry is `ins_get_quaternion`.

### Signature

```
bool `ins_get_quaternion`(const ins_t* f, float q[4]);
```

Compile arity is 2.

Get current attitude quaternion.

## `ins_get_rotmat_b_to_n`

Include `ins.h`. The C entry is `ins_get_rotmat_b_to_n`.

### Signature

```
bool `ins_get_rotmat_b_to_n`(const ins_t* f, float R_b_to_n[9]);
```

Compile arity is 2.

Get current body-to-NED rotation matrix.

## `ins_gnss_condition_pos_cov`

Include `ins.h`. The C entry is `ins_gnss_condition_pos_cov`.

### Signature

```
void `ins_gnss_condition_pos_cov`(const ins_options_t* opt, const float Qll_in[3 * 3], float Qll_out[3 * 3]);
```

Compile arity is 3.

Condition a reported GNSS covariance into the one the fusion weights the fix with (REQ-NAV-038, REQ-NAV-041).

## `ins_gnss_condition_vel_cov`

Include `ins.h`. The C entry is `ins_gnss_condition_vel_cov`.

### Signature

```
void `ins_gnss_condition_vel_cov`(const ins_options_t* opt, const float Qll_in[3 * 3], float Qll_out[3 * 3]);
```

Compile arity is 3.

Velocity-block twin of ins_gnss_condition_pos_cov().

## `ins_gravity_ned`

Include `geodetic_toolbox.h`. The C entry is `ins_gravity_ned`.

### Signature

```
void `ins_gravity_ned`(float lat_rad, float height_m, float gravity_n[3]);
```

Compile arity is 3.

Compute gravity vector in n-frame (includes centrifugal term).

## `ins_history_item_t`

Include `ins.h`. The published type is `ins_history_item_t`.

### Signature

```
typedef struct {
    ins_time_us_t time;
    ins_state_t state;
    double latlonh[3];
    float U[INS_UNKNOWNS_MAX*INS_UNKNOWNS_MAX];
    float d[INS_UNKNOWNS_MAX];
    float omega_b_nb[3];
    float R_b_to_n[9];
} ins_history_item_t;
```

Members the caller compiles against:

- `time` — `ins_time_us_t time`
- `state` — `ins_state_t state`
- `latlonh` — `double latlonh[3]`
- `U` — `float U[INS_UNKNOWNS_MAX*INS_UNKNOWNS_MAX]`
- `d` — `float d[INS_UNKNOWNS_MAX]`
- `omega_b_nb` — `float omega_b_nb[3]`
- `R_b_to_n` — `float R_b_to_n[9]`

## `ins_isa_altitude_from_pressure`

Include `geodetic_toolbox.h`. The C entry is `ins_isa_altitude_from_pressure`.

### Signature

```
float `ins_isa_altitude_from_pressure`(float pressure_pa);
```

Compile arity is 1.

## `ins_isa_pressure_plausible`

Include `geodetic_toolbox.h`. The C entry is `ins_isa_pressure_plausible`.

### Signature

```
bool `ins_isa_pressure_plausible`(float pressure_pa);
```

Compile arity is 1.

## `ins_latlonh_to_ecef`

Include `geodetic_toolbox.h`. The C entry is `ins_latlonh_to_ecef`.

### Signature

```
void `ins_latlonh_to_ecef`(double lat_rad, double lon_rad, double height_m, double xyz[3]);
```

Compile arity is 4.

Convert geodetic lat/lon/height to ECEF coordinates (WGS84).

Uses the WGS84 ellipsoid, not a sphere: semi-major axis 6378137.0 m and flattening 1/298.257223563. Latitude and longitude are radians; height is metres above the ellipsoid. Output ECEF is metres as a 3-vector of doubles.

A geodetic position such as latitude 48.783°, longitude 9.181°, height 300 m converts to ECEF that matches the closed-form WGS84 formula to within 1 m, and is more than 10 m away from the spherical-Earth (same semi-major axis, no flattening) result. The matching Python package entry is `llh_to_ecef` imported from `NAVFILTER`: it takes latitude and longitude in radians and height in metres and returns an ECEF 3-tuple in metres.

## `ins_meas3_t`

Include `ins.h`. The published type is `ins_meas3_t`.

### Signature

```
typedef struct {
    float data[3];
    float Qll_diag[3];
    bool is_valid;
} ins_meas3_t;
```

Members the caller compiles against:

- `data` — `float data[3]`
- `Qll_diag` — `float Qll_diag[3]`
- `is_valid` — `bool is_valid`

## `ins_meas_att_hint_t`

Include `ins.h`. The published type is `ins_meas_att_hint_t`.

### Signature

```
typedef struct {
    bool is_valid;
    float roll_rad;
    float pitch_rad;
    float stddev_roll_rad;
    float stddev_pitch_rad;
    float yaw_rad;
    float stddev_yaw_rad;
    float gyr_bias_rps[3];
    float stddev_gyr_bias_rps[3];
} ins_meas_att_hint_t;
```

Members the caller compiles against:

- `is_valid` — `bool is_valid`
- `roll_rad` — `float roll_rad`
- `pitch_rad` — `float pitch_rad`
- `stddev_roll_rad` — `float stddev_roll_rad`
- `stddev_pitch_rad` — `float stddev_pitch_rad`
- `yaw_rad` — `float yaw_rad`
- `stddev_yaw_rad` — `float stddev_yaw_rad`
- `gyr_bias_rps` — `float gyr_bias_rps[3]`
- `stddev_gyr_bias_rps` — `float stddev_gyr_bias_rps[3]`

## `ins_meas_baro_t`

Include `ins.h`. The published type is `ins_meas_baro_t`.

### Signature

```
typedef struct {
    float pressure_pa;
    float stddev_m;
    bool is_valid;
} ins_meas_baro_t;
```

Members the caller compiles against:

- `pressure_pa` — `float pressure_pa`
- `stddev_m` — `float stddev_m`
- `is_valid` — `bool is_valid`

## `ins_meas_gnss_pos_t`

Include `ins.h`. The published type is `ins_meas_gnss_pos_t`.

### Signature

```
typedef struct {
    double xyz_ecef[3];
    float Qll_ned[3*3];
    bool is_valid;
} ins_meas_gnss_pos_t;
```

Members the caller compiles against:

- `xyz_ecef` — `double xyz_ecef[3]`
- `Qll_ned` — `float Qll_ned[3*3]`
- `is_valid` — `bool is_valid`

## `ins_meas_gnss_vel_t`

Include `ins.h`. The published type is `ins_meas_gnss_vel_t`.

### Signature

```
typedef struct {
    float vel_ned[3];
    float Qll_ned[3*3];
    bool is_valid;
} ins_meas_gnss_vel_t;
```

Members the caller compiles against:

- `vel_ned` — `float vel_ned[3]`
- `Qll_ned` — `float Qll_ned[3*3]`
- `is_valid` — `bool is_valid`

## `ins_meas_local_pos_t`

Include `ins.h`. The published type is `ins_meas_local_pos_t`.

### Signature

```
typedef struct {
    float pos_ned[3];
    float Qll_ned[3*3];
    bool is_valid;
} ins_meas_local_pos_t;
```

Members the caller compiles against:

- `pos_ned` — `float pos_ned[3]`
- `Qll_ned` — `float Qll_ned[3*3]`
- `is_valid` — `bool is_valid`

## `ins_meas_speed_t`

Include `ins.h`. The published type is `ins_meas_speed_t`.

### Signature

```
typedef struct {
    float speed_mps;
    float stddev_mps;
    bool is_valid;
} ins_meas_speed_t;
```

Members the caller compiles against:

- `speed_mps` — `float speed_mps`
- `stddev_mps` — `float stddev_mps`
- `is_valid` — `bool is_valid`

## `ins_meas_yaw_t`

Include `ins.h`. The published type is `ins_meas_yaw_t`.

### Signature

```
typedef struct {
    float yaw_rad;
    float stddev_rad;
    bool is_valid;
} ins_meas_yaw_t;
```

Members the caller compiles against:

- `yaw_rad` — `float yaw_rad`
- `stddev_rad` — `float stddev_rad`
- `is_valid` — `bool is_valid`

## `ins_predict_step`

Include `ins.h`. The C entry is `ins_predict_step`.

### Signature

```
int `ins_predict_step`(ins_t* f, const ins_measurements_t* m, float* phi_out);
```

Compile arity is 3.

Time-propagation half of ins_update(): strapdown mechanization plus the (throttled) Kalman covariance prediction.

## `ins_quat_from_rpy`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_from_rpy`.

### Signature

```
void `ins_quat_from_rpy`(float roll_rad, float pitch_rad, float yaw_rad, float q[4]);
```

Compile arity is 4.

Build a quaternion from roll/pitch/yaw (Tait-Bryan ZYX).

Roll, pitch, yaw are Tait-Bryan ZYX in radians. The result is a Hamilton quaternion mapping body FRD to NED, scalar first: `q[0]` is the real part, `q[1..3]` the vector part.

Zero roll, pitch, and yaw yield the identity (real part 1, vector part 0) to single-precision absolute tolerance 1e-5. Yaw of π/2 with zero roll and pitch yields a quaternion whose real part and z-part are both cos(π/4) (equivalently sin(π/4)), other parts near 0, to that same tolerance. A non-trivial triple such as roll 0.3 rad, pitch −0.2 rad, yaw 1.1 rad matches the Hamilton ZYX composition R = Rz(yaw) Ry(pitch) Rx(roll) to 1e-5 on each component.

The matching Python package entry is `rpy_to_quat` imported from `NAVFILTER` (`from `NAVFILTER` import `rpy_to_quat``). It takes the same three angles in radians and returns a 4-tuple `(w, x, y, z)` with the same mapping.

## `ins_quat_multiply`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_multiply`.

### Signature

```
void `ins_quat_multiply`(const float q1[4], const float q2[4], float q_out[4]);
```

Compile arity is 3.

Hamilton product of two quaternions: q_out = q1 q2.

## `ins_quat_normalize`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_normalize`.

### Signature

```
void `ins_quat_normalize`(float q[4]);
```

Compile arity is 1.

Normalize a quaternion in place.

Normalizes in place. A zero quaternion and other degenerate inputs (including a tiny non-zero vector such as (0, 1e-25, 0, 0)) normalize to the identity (real part 1, vector part 0) rather than NaN, to 1e-5.

## `ins_quat_rotate`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_rotate`.

### Signature

```
void `ins_quat_rotate`(const float q[4], const float omega[3], float dt_sec, float q_new[4]);
```

Compile arity is 4.

Rotate quaternion q by a constant rotation rate omega over dt.

## `ins_quat_small_angle_correction`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_small_angle_correction`.

### Signature

```
void `ins_quat_small_angle_correction`(const float q_in[4], const float drpy_rad[3], float q_out[4]);
```

Compile arity is 3.

Apply a small-angle correction to a quaternion.

## `ins_quat_to_rotmat`

Include `geodetic_toolbox.h`. The C entry is `ins_quat_to_rotmat`.

### Signature

```
void `ins_quat_to_rotmat`(const float q[4], float R_b_to_n[9]);
```

Compile arity is 2.

Convert a quaternion to a 3x3 rotation matrix R_b_to_n.

The 3×3 matrix is stored column-major, consistent with `linalg.h`. It is the body-to-NED rotation: a body vector `v_b` maps to NED as `v_n[row] += MAT_ELEM(R, row, col, 3, 3) * v_b[col]`.

At identity attitude, body +x maps to north (1, 0, 0), body +y to east (0, 1, 0), and body +z to down (0, 0, 1), to 1e-5. Yaw of π/2 with zero roll and pitch maps body +x to east (0, 1, 0).

## `ins_rotmat_n_to_e`

Include `geodetic_toolbox.h`. The C entry is `ins_rotmat_n_to_e`.

### Signature

```
void `ins_rotmat_n_to_e`(double lat_rad, double lon_rad, float R_n_to_e[9]);
```

Compile arity is 3.

Get rotation matrix from n-frame (NED) to ECEF (e-frame).

## `ins_rotmat_to_rpy`

Include `geodetic_toolbox.h`. The C entry is `ins_rotmat_to_rpy`.

### Signature

```
void `ins_rotmat_to_rpy`(const float R_b_to_n[9], float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Extract roll/pitch/yaw (Tait-Bryan ZYX) from a rotation matrix.

Assumes `R_b_to_n` is the body-to-NED matrix in column-major order. Converting a quaternion built by `ins_quat_from_rpy` through `ins_quat_to_rotmat` and then this call recovers the original roll, pitch, and yaw to 1e-5 for ordinary attitudes such as (0.3, −0.2, 1.1) rad.

A gimbal-lock pitch (near ±π/2, including exactly ±π/2) still yields finite roll, pitch, and yaw. The mapping does not abort and does not produce NaN.

## `ins_set_auto_zupt_disable`

Include `ins.h`. The C entry is `ins_set_auto_zupt_disable`.

### Signature

```
void `ins_set_auto_zupt_disable`(ins_t* f, bool disable);
```

Compile arity is 2.

Enable/disable the automatic ZUPT/ZARU detector at runtime (REQ-NAV-013), independent of the opt.auto_zupt_disable set at ins_init.

## `ins_shift_origin_down`

Include `ins.h`. The C entry is `ins_shift_origin_down`.

### Signature

```
void `ins_shift_origin_down`(ins_t* f, float dz_m);
```

Compile arity is 2.

Move the n-frame origin down by dz_m [m] (vertical datum relocation).

## `ins_state_t`

Include `ins.h`. The published type is `ins_state_t`.

### Signature

```
typedef struct {
    float pos_local[3];
    float vel_ned[3];
    float qbn[4];
    float acc_bias[3];
    float gyr_bias[3];
    float mag_bias[3];
} ins_state_t;
```

Members the caller compiles against:

- `pos_local` — `float pos_local[3]`
- `vel_ned` — `float vel_ned[3]`
- `qbn` — `float qbn[4]`
- `acc_bias` — `float acc_bias[3]`
- `gyr_bias` — `float gyr_bias[3]`
- `mag_bias` — `float mag_bias[3]`

## `ins_suite_ctx_t`

`ins_suite_ctx_t`. This type is not declared in a published header. The language-binding ABI in `ins_capi.h` hands out an opaque `void*` handle; callers include that header and do not name this type.

### Signature

```
typedef struct {
    nav_suite_t suite;
    ins_measurements_t meas;
} ins_suite_ctx_t;
```

Members:

- `suite` — `nav_suite_t suite`
- `meas` — `ins_measurements_t meas`

The handle owns one `nav_suite_t` instance plus one pending `ins_measurements_t` so setter calls can accumulate an epoch before an update fuses it.

## `ins_t`

Include `ins.h`. The published type is `ins_t`.

### Signature

```
typedef struct
{
    ins_init_t    init;
    ins_options_t opt;
    float chi2_thr_gnss;
    float chi2_thr_mag;
    float chi2_thr_local;
    float chi2_thr_yaw;
    ins_state_t state;
    int n;
    float U[INS_UNKNOWNS_MAX * INS_UNKNOWNS_MAX];
    float d[INS_UNKNOWNS_MAX];
    float Qxx_noise_diag[INS_UNKNOWNS_MAX];
    double origin_ecef[3];
    double latlonh[3];
    double meta_dlat_per_dN;
    double meta_dlon_per_dE;
    float  meta_travel_m;
    float  R_n_to_e[9];
    float  R_b_to_n[9];
    float  gravity_n[3];
    float  magnetic_n[3];
    float  mag_field_expected_uT;
    float last_omega_b_nb[3];
    float last_acc_n[3];
    float acc_n_avg[3];
    float omega_outer_avg[6];
    bool acc_n_avg_valid;
    float last_acc_meas[3];
    bool  last_acc_valid;
    struct
    {
        ins_measurements_t m;
        float gnss_pos_Qll_fuse[3 * 3];
        float gnss_vel_Qll_fuse[3 * 3];
        float gnss_pos_vel_Qll_fuse[3 * 3];
        bool active;
        bool run_fusion;
        bool dr_frozen;
    } step_ctx;
    ins_time_us_t t_last_kalman_predict;
    uint32_t      time_dropped_run;
    ins_time_us_t t_last_pos_aiding;
    ins_time_us_t t_last_mag_fusion;
    ins_time_us_t t_last_zero_rot_fusion;
    ins_time_us_t t_last_zero_vel_fusion;
    ins_time_us_t t_init;
    unsigned      kalman_epochs;
    bool          is_initialized;
    bool          is_collecting;
    bool          have_pending_imu;
    bool          have_pending_fix;
    ins_time_us_t t_pending_imu;
    ins_time_us_t t_pending_fix;
    int           autoinit_count;
    struct
    {
        ins_time_us_t t;
        float         acc[3];
        float         gyr[3];
    } autoinit_buf[INS_AUTOINIT_SAMPLES_MAX];
    struct
    {
        ins_time_us_t t;
        float         data[3];
        bool          valid;
    } autoinit_mag;
    struct
    {
        ins_time_us_t t;
        float         pressure_pa;
        bool          valid;
    } autoinit_baro;
    struct
    {
        ins_time_us_t t;
        float         pressure_pa;
        float         stddev_m;
        bool          valid;
    } last_baro;
    ins_time_us_t gnss_dwell_since;
    ins_time_us_t gnss_dwell_last;
    int           gnss_dwell_count;
    uint32_t gnss_pos_decim_count;
    float         gnss_env_pos_hor_m;
    float         gnss_env_pos_ver_m;
    float         gnss_env_vel_hor_mps;
    float         gnss_env_vel_ver_mps;
    ins_time_us_t t_gnss_env_pos;
    ins_time_us_t t_gnss_env_vel;
    ins_time_us_t t_last_gnss_fused;
    bool gnss_quality_ok;
    ins_time_us_t gnss_bad_since;
    struct
    {
        bool  valid;
        float acc_bias[3];
        float gyr_bias[3];
        float acc_bias_stddev_mps2;
        float gyr_bias_stddev_rps;
    } bias_carry;
    struct
    {
        bool   valid;
        double origin_ecef[3];
        float  pos_local[3];
        double latlonh[3];
        ins_time_us_t t;
    } origin_carry;
    bool height_from_baro;
    float baro_h0_m;
    ins_time_us_t auto_zupt_static_since;
    ins_time_us_t auto_zupt_var_since;
    ins_time_us_t t_last_auto_zupt;
    float auto_zupt_gyr_sum[3];
    uint32_t auto_zupt_gyr_count;
    float    auto_zupt_ext_vel_mps;
    ins_time_us_t auto_zupt_ext_vel_time;
    ins_time_us_t static_var_window_since;
    float         static_var_mean[6];
    float         static_var_m2[6];
    uint32_t      static_var_count;
    bool static_var_ok;
    ins_time_us_t bias_prior_since;
    float    bias_prior_acc_sum[3];
    float    bias_prior_gyr_sum[3];
    uint32_t bias_prior_count;
    ins_diag_t diag;
    struct
    {
        ins_time_us_t t_last_gnss_outage_warn;
        ins_time_us_t t_last_invalid_warn;
        ins_time_us_t t_last_yaw_aid;
        ins_time_us_t t_last_yaw_stddev_warn;
        ins_time_us_t t_last_stuck_warn;
        ins_time_us_t t_last_mag_disturb_warn;
        ins_time_us_t t_yaw_stddev_window;
        ins_time_us_t t_gyr_bias_window;
        ins_time_us_t t_acc_bias_window;
        ins_time_us_t t_last_gyr_bias_sanity_warn;
        ins_time_us_t t_last_acc_bias_sanity_warn;
        ins_time_us_t t_last_gyr_bias_prior_warn;
        ins_time_us_t t_last_acc_bias_prior_warn;
        ins_time_us_t t_last_entry_gate_warn;
        ins_time_us_t t_last_baro_height_aid;
        ins_time_us_t t_last_baro_height_warn;
        ins_time_us_t t_last_large_pos_res_log;
        float last_gyr_raw[3];
        float    yaw_stddev_window_deg;
        float    gyr_bias_window_dps;
        float    acc_bias_window_mps2;
        uint32_t stuck_gyr_count;
        uint32_t mag_disturbed_count;
        bool automotive_logged;
        bool gnss_delay_logged;
        bool last_gyr_raw_valid;
    } log_state;
    ins_history_item_t history[INS_HISTORY_ITEMS_MAX];
    int history_index;
} ins_t;
```

Members the caller compiles against:

- `init` — `ins_init_t init`
- `opt` — `ins_options_t opt`
- `chi2_thr_gnss` — `float chi2_thr_gnss`
- `chi2_thr_mag` — `float chi2_thr_mag`
- `chi2_thr_local` — `float chi2_thr_local`
- `chi2_thr_yaw` — `float chi2_thr_yaw`
- `state` — `ins_state_t state`
- `n` — `int n`
- `U` — `float U[INS_UNKNOWNS_MAX * INS_UNKNOWNS_MAX]`
- `d` — `float d[INS_UNKNOWNS_MAX]`
- `Qxx_noise_diag` — `float Qxx_noise_diag[INS_UNKNOWNS_MAX]`
- `origin_ecef` — `double origin_ecef[3]`
- `latlonh` — `double latlonh[3]`
- `meta_dlat_per_dN` — `double meta_dlat_per_dN`
- `meta_dlon_per_dE` — `double meta_dlon_per_dE`
- `meta_travel_m` — `float meta_travel_m`
- `R_n_to_e` — `float R_n_to_e[9]`
- `R_b_to_n` — `float R_b_to_n[9]`
- `gravity_n` — `float gravity_n[3]`
- `magnetic_n` — `float magnetic_n[3]`
- `mag_field_expected_uT` — `float mag_field_expected_uT`
- `last_omega_b_nb` — `float last_omega_b_nb[3]`
- `last_acc_n` — `float last_acc_n[3]`
- `acc_n_avg` — `float acc_n_avg[3]`
- `omega_outer_avg` — `float omega_outer_avg[6]`
- `acc_n_avg_valid` — `bool acc_n_avg_valid`
- `last_acc_meas` — `float last_acc_meas[3]`
- `last_acc_valid` — `bool last_acc_valid`
- `step_ctx` — `struct { ... } step_ctx`
- `t_last_kalman_predict` — `ins_time_us_t t_last_kalman_predict`
- `time_dropped_run` — `uint32_t time_dropped_run`
- `t_last_pos_aiding` — `ins_time_us_t t_last_pos_aiding`
- `t_last_mag_fusion` — `ins_time_us_t t_last_mag_fusion`
- `t_last_zero_rot_fusion` — `ins_time_us_t t_last_zero_rot_fusion`
- `t_last_zero_vel_fusion` — `ins_time_us_t t_last_zero_vel_fusion`
- `t_init` — `ins_time_us_t t_init`
- `kalman_epochs` — `unsigned kalman_epochs`
- `is_initialized` — `bool is_initialized`
- `is_collecting` — `bool is_collecting`
- `have_pending_imu` — `bool have_pending_imu`
- `have_pending_fix` — `bool have_pending_fix`
- `t_pending_imu` — `ins_time_us_t t_pending_imu`
- `t_pending_fix` — `ins_time_us_t t_pending_fix`
- `autoinit_count` — `int autoinit_count`
- `autoinit_buf` — `struct { ... } autoinit_buf[INS_AUTOINIT_SAMPLES_MAX]`
- `autoinit_mag` — `struct { ... } autoinit_mag`
- `autoinit_baro` — `struct { ... } autoinit_baro`
- `last_baro` — `struct { ... } last_baro`
- `gnss_dwell_since` — `ins_time_us_t gnss_dwell_since`
- `gnss_dwell_last` — `ins_time_us_t gnss_dwell_last`
- `gnss_dwell_count` — `int gnss_dwell_count`
- `gnss_pos_decim_count` — `uint32_t gnss_pos_decim_count`
- `gnss_env_pos_hor_m` — `float gnss_env_pos_hor_m`
- `gnss_env_pos_ver_m` — `float gnss_env_pos_ver_m`
- `gnss_env_vel_hor_mps` — `float gnss_env_vel_hor_mps`
- `gnss_env_vel_ver_mps` — `float gnss_env_vel_ver_mps`
- `t_gnss_env_pos` — `ins_time_us_t t_gnss_env_pos`
- `t_gnss_env_vel` — `ins_time_us_t t_gnss_env_vel`
- `t_last_gnss_fused` — `ins_time_us_t t_last_gnss_fused`
- `gnss_quality_ok` — `bool gnss_quality_ok`
- `gnss_bad_since` — `ins_time_us_t gnss_bad_since`
- `bias_carry` — `struct { ... } bias_carry`
- `origin_carry` — `struct { ... } origin_carry`
- `height_from_baro` — `bool height_from_baro`
- `baro_h0_m` — `float baro_h0_m`
- `auto_zupt_static_since` — `ins_time_us_t auto_zupt_static_since`
- `auto_zupt_var_since` — `ins_time_us_t auto_zupt_var_since`
- `t_last_auto_zupt` — `ins_time_us_t t_last_auto_zupt`
- `auto_zupt_gyr_sum` — `float auto_zupt_gyr_sum[3]`
- `auto_zupt_gyr_count` — `uint32_t auto_zupt_gyr_count`
- `auto_zupt_ext_vel_mps` — `float auto_zupt_ext_vel_mps`
- `auto_zupt_ext_vel_time` — `ins_time_us_t auto_zupt_ext_vel_time`
- `static_var_window_since` — `ins_time_us_t static_var_window_since`
- `static_var_mean` — `float static_var_mean[6]`
- `static_var_m2` — `float static_var_m2[6]`
- `static_var_count` — `uint32_t static_var_count`
- `static_var_ok` — `bool static_var_ok`
- `bias_prior_since` — `ins_time_us_t bias_prior_since`
- `bias_prior_acc_sum` — `float bias_prior_acc_sum[3]`
- `bias_prior_gyr_sum` — `float bias_prior_gyr_sum[3]`
- `bias_prior_count` — `uint32_t bias_prior_count`
- `diag` — `ins_diag_t diag`
- `log_state` — `struct { ... } log_state`
- `history` — `ins_history_item_t history[INS_HISTORY_ITEMS_MAX]`
- `history_index` — `int history_index`

Caller-owned instance. Zero before the first `ins_init`. Nested anonymous structs `step_ctx`, `autoinit_mag`, `autoinit_baro`, `last_baro`, `bias_carry`, `origin_carry`, and `log_state` are part of the published layout, as is the `autoinit_buf` array of per-sample records with members `t`, `acc`, and `gyr`.

## `ins_time_us_t`

Include `ins.h`. The published type is `ins_time_us_t`.

### Signature

```
typedef int64_t `ins_time_us_t`;
```

Alias of `int64_t`. The published spelling is `ins_time_us_t`.
A monotonic timestamp in integer microseconds.

## `ins_vec3_finite`

Include `geodetic_toolbox.h`. The C entry is `ins_vec3_finite`.

### Signature

```
bool `ins_vec3_finite`(const float v[3]);
```

Compile arity is 1.

True iff all three components are finite (not NaN/Inf).

## `ins_wrap_pi_bounded`

Include `geodetic_toolbox.h`. The C entry is `ins_wrap_pi_bounded`.

### Signature

```
float `ins_wrap_pi_bounded`(float a);
```

Compile arity is 1.

## `kalman_udu`

Include `kalman_udu.h`. The C entry is `kalman_udu`.

### Signature

```
int `kalman_udu`(float* KFC_RESTRICT x, float* KFC_RESTRICT U, float* KFC_RESTRICT d, const float* KFC_RESTRICT z, const float* KFC_RESTRICT R, const float* KFC_RESTRICT Ht, int n, int m, float chi2_threshold, int downweight_outlier);
```

Compile arity is 10.

UDU Kalman Filter (Bierman/Thornton "Square Root" Implementation).

## `kalman_udu_predict`

Include `kalman_udu.h`. The C entry is `kalman_udu_predict`.

### Signature

```
int `kalman_udu_predict`(float* KFC_RESTRICT x, float* KFC_RESTRICT U, float* KFC_RESTRICT d, const float* KFC_RESTRICT Phi, const float* KFC_RESTRICT G, const float* KFC_RESTRICT Q, int n, int r);
```

Compile arity is 8.

UDU' (Thornton) Filter Temporal / Prediction Step.

## `kalman_udu_scalar`

Include `kalman_udu.h`. The C entry is `kalman_udu_scalar`.

### Signature

```
int `kalman_udu_scalar`(float* KFC_RESTRICT x, float* KFC_RESTRICT U, float* KFC_RESTRICT d, const float dz, const float R, const float* KFC_RESTRICT H_line, int n);
```

Compile arity is 7.

Square Root Kalman Filter (Bierman) Routine for a single scalar measurement.

## `last_gyr_raw`

Published member `last_gyr_raw`.

It appears on:

- `ins_t` (`float last_gyr_raw[3]`)

## `last_gyr_raw_valid`

Published member `last_gyr_raw_valid`.

It appears on:

- `ins_t` (`bool last_gyr_raw_valid`)

## `last_ins_initialized`

Published member `last_ins_initialized`.

It appears on:

- `nav_suite_t` (`bool last_ins_initialized`)

## `last_mode`

Published member `last_mode`.

It appears on:

- `nav_suite_t` (`nav_suite_mode_t last_mode`)

## `latlonh`

Published member `latlonh`.

It appears on:

- `ins_history_item_t` (`double latlonh[3]`)
- `ins_t` (`double latlonh[3]`)

## `local_gnss_alt_config_t`

Include `baro_alt.h`. The published type is `local_gnss_alt_config_t`.

### Signature

```
typedef struct {
    float rw_stddev_mps;
    float local_stddev_m;
    float chi2_threshold;
    float min_update_interval_sec;
    float stddev_inflation_factor;
    bool chi2_disable;
} local_gnss_alt_config_t;
```

Members the caller compiles against:

- `rw_stddev_mps` — `float rw_stddev_mps`
- `local_stddev_m` — `float local_stddev_m`
- `chi2_threshold` — `float chi2_threshold`
- `min_update_interval_sec` — `float min_update_interval_sec`
- `stddev_inflation_factor` — `float stddev_inflation_factor`
- `chi2_disable` — `bool chi2_disable`

## `local_gnss_alt_get`

Include `baro_alt.h`. The C entry is `local_gnss_alt_get`.

### Signature

```
bool `local_gnss_alt_get`(const local_gnss_alt_t* g, float* offset_m, float* stddev_m);
```

Compile arity is 3.

Current offset o = h_gnss_ell - h_local (the ellipsoid height of the datum origin) and its 1-sigma uncertainty. Either output pointer may be NULL.

## `local_gnss_alt_t`

Include `baro_alt.h`. The published type is `local_gnss_alt_t`.

### Signature

```
typedef struct {
    local_gnss_alt_config_t cfg;
    float offset_m;
    float var_m2;
    baro_alt_time_us_t t_last;
    uint32_t epoch;
    bool is_initialized;
    uint32_t n_invalid_input;
    uint32_t n_decimated;
    uint32_t n_downweighted;
    baro_alt_time_us_t t_last_downweight_warn;
} local_gnss_alt_t;
```

Members the caller compiles against:

- `cfg` — `local_gnss_alt_config_t cfg`
- `offset_m` — `float offset_m`
- `var_m2` — `float var_m2`
- `t_last` — `baro_alt_time_us_t t_last`
- `epoch` — `uint32_t epoch`
- `is_initialized` — `bool is_initialized`
- `n_invalid_input` — `uint32_t n_invalid_input`
- `n_decimated` — `uint32_t n_decimated`
- `n_downweighted` — `uint32_t n_downweighted`
- `t_last_downweight_warn` — `baro_alt_time_us_t t_last_downweight_warn`

## `local_gnss_alt_update`

Include `baro_alt.h`. The C entry is `local_gnss_alt_update`.

### Signature

```
void `local_gnss_alt_update`(local_gnss_alt_t* g, baro_alt_time_us_t t, float h_local_m, float local_stddev_m, float h_gnss_ell_m, float gnss_stddev_m);
```

Compile arity is 6.

Feed one baro/GNSS pair.

## `log_write`

Include `log.h`. The C entry is `log_write`.

### Signature

```
void `log_write`(int level, const char* file, int line, const char* fmt, ...);
```

Variadic after the format string. Compile arities include 4, 5, 6, 7, 8, 9, 10, 11, 12, 17.

## `lsame_`

Include `miniblas.h`. The C entry is `lsame_`.

### Signature

```
int `lsame_`(const char* a, const char* b);
```

Compile arity is 2.

## `m`

Published member `m`.

It appears as the nested `step_ctx` field `ins_measurements_t m` on:

- `ins_t`
- `nav_suite_t`

## `mag_b`

Published member `mag_b`.

It appears on:

- `ahrs_t` (`float mag_b[3]`)

## `mag_disturbed_count`

Published member `mag_disturbed_count`.

It appears on:

- `ins_t` (`uint32_t mag_disturbed_count`)

## `mag_valid`

Published member `mag_valid`.

It appears on:

- `ahrs_t` (`bool mag_valid`)

## `magnetic_declination_deg`

Include `magnetic_model.h`. The C entry is `magnetic_declination_deg`.

### Signature

```
float `magnetic_declination_deg`(float lat_deg, float lon_deg, float year);
```

Compile arity is 3.

Latitude is degrees, clamped to [−90, +90]. Longitude is degrees, wrapped into (−180, +180]. Decimal year (for example 2026.5) is an input: distinct legal years are distinguishable. Years outside the model epoch are extrapolated rather than refused — 1990 versus 2000, and 2045 versus 2055, produce different declinations (wrap difference greater than 1e-3°), rather than collapsing onto a single table epoch.

Return is declination in degrees, positive east. At a mid-latitude site away from the geomagnetic poles, declination matches an independent WMM2025 spherical-harmonic evaluation to within 0.15°. Near the geographic poles (absolute latitude above 88°) the tolerance widens to 0.6°. Longitude 190° and −170° at the same latitude and year produce the same declination (wrap difference ≤ 1e-3°); wrapping by additional full turns (190 + 360k) agrees with −170°. Longitude ±180° returns a finite declination. The lookup is not a constant heading: a western mid-latitude site is distinguishable from a European mid-latitude site.

## `magnetic_field_ned_uT`

Include `magnetic_model.h`. The C entry is `magnetic_field_ned_uT`.

### Signature

```
void `magnetic_field_ned_uT`(float lat_deg, float lon_deg, float year, float b_ned_uT[3]);
```

Compile arity is 4.

Full magnetic reference field in the NED frame.

Writes a three-axis NED reference field in microtesla. The assembled field is self-consistent with the scalar lookups: its horizontal heading (atan2(east, north), degrees east of north) matches `magnetic_declination_deg` to 0.05°, and its magnitude matches `magnetic_field_strength_uT` to a relative 1e-3.

The C library exposes all four quantities (D, I, F, and the NED vector). The Python package re-exports the NED field as `wmm_field_ned` imported from `NAVFILTER` (`from `NAVFILTER` import `wmm_field_ned``): arguments are latitude degrees, longitude degrees, and decimal year; the result is a 3-tuple `(north, east, down)` in µT. Heading and magnitude recovered from that Python tuple still match C declination and total field to the same 0.05° / 1e-3 relative tolerances. Longitude wrap (190° vs −170°) holds for the Python NED field as well.

Years outside the model epoch are extrapolated: 1990 versus 2000, and 2045 versus 2055, are distinguishable from each other and from a mid-epoch evaluation, rather than clamped to a single table epoch.

## `magnetic_field_strength_uT`

Include `magnetic_model.h`. The C entry is `magnetic_field_strength_uT`.

### Signature

```
float `magnetic_field_strength_uT`(float lat_deg, float lon_deg);
```

Compile arity is 2.

Total magnetic field strength at the location.

Latitude and longitude in degrees, same clamp/wrap as `magnetic_declination_deg`. Return is total field in microtesla, not nanotesla. Agreement with an independent WMM2025 evaluation is within 20 µT.

## `magnetic_inclination_deg`

Include `magnetic_model.h`. The C entry is `magnetic_inclination_deg`.

### Signature

```
float `magnetic_inclination_deg`(float lat_deg, float lon_deg);
```

Compile arity is 2.

Magnetic inclination (dip) at the location.

Latitude and longitude in degrees, same clamp/wrap as `magnetic_declination_deg`. Return is inclination in degrees, positive down in the northern hemisphere. At a mid-latitude northern site the value is positive. Units are degrees, not radians; agreement with an independent WMM2025 evaluation is within 15°.

## `mateye`

Include `linalg.h`. The C entry is `mateye`.

### Signature

```
void `mateye`(float* A, int n);
```

Compile arity is 2.

Fill array with an identity matrix.

## `matmul`

Include `linalg.h`. The C entry is `matmul`.

### Signature

```
void `matmul`(const char* ta, const char* tb, int n, int k, int m, float alpha, const float* A, const float* B, float beta, float* C);
```

Compile arity is 10.

matrix multiply C = alpha A B + beta C BLAS: ?gemm.

## `nav_suite_correct_step`

Include `nav_suite.h`. The C entry is `nav_suite_correct_step`.

### Signature

```
void `nav_suite_correct_step`(nav_suite_t* s);
```

Compile arity is 1.

## `nav_suite_get_baro_alt`

Include `nav_suite.h`. The C entry is `nav_suite_get_baro_alt`.

### Signature

```
bool `nav_suite_get_baro_alt`(const nav_suite_t* s, float* h_m, float* v_mps);
```

Compile arity is 3.

The matching Python reader on the `Navigator` wrapper is `baro_alt`. It takes no arguments. It does not run the filter. It is the barometric vertical channel. It yields None when unpublished and a height-then-climb pair when published.

## `nav_suite_get_height`

Include `nav_suite.h`. The C entry is `nav_suite_get_height`.

### Signature

```
bool `nav_suite_get_height`(const nav_suite_t* s, float* h_m);
```

Compile arity is 2.

The matching Python reader on the `Navigator` wrapper is `height`. It takes no arguments. It does not run the filter. It is the datum height. It yields None when unpublished and a finite number when published.

## `nav_suite_get_height_ellipsoid`

Include `nav_suite.h`. The C entry is `nav_suite_get_height_ellipsoid`.

### Signature

```
bool `nav_suite_get_height_ellipsoid`(const nav_suite_t* s, float* h_ell_m);
```

Compile arity is 2.

The matching Python reader on the `Navigator` wrapper is `height_ellipsoid`. It takes no arguments. It does not run the filter. It is the ellipsoid height. It yields None when unpublished and a finite number when published.

## `nav_suite_get_mode`

Include `nav_suite.h`. The C entry is `nav_suite_get_mode`.

### Signature

```
nav_suite_mode_t `nav_suite_get_mode`(const nav_suite_t* s);
```

Compile arity is 1.

Current solution mode (see nav_suite_mode_t).

## `nav_suite_get_rpy`

Include `nav_suite.h`. The C entry is `nav_suite_get_rpy`.

### Signature

```
bool `nav_suite_get_rpy`(const nav_suite_t* s, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Roll/pitch/yaw from the best available source: INS if ready, else the magnetometer AHRS, else the ARS.

The matching Python reader on the `Navigator` wrapper is `rpy`. It takes no arguments. It does not run the filter. It is the best-available roll/pitch/yaw. It yields None when unpublished and a 3-sequence when published.

## `nav_suite_get_rpy_ins`

Include `nav_suite.h`. The C entry is `nav_suite_get_rpy_ins`.

### Signature

```
bool `nav_suite_get_rpy_ins`(const nav_suite_t* s, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Roll/pitch/yaw of the INS filter.

The matching Python reader on the `Navigator` wrapper is `rpy_ins`. It takes no arguments. It does not run the filter. It is the INS roll/pitch/yaw. It yields None when unpublished and a 3-sequence when published.

## `nav_suite_get_vertical_zupt_active`

Include `nav_suite.h`. The C entry is `nav_suite_get_vertical_zupt_active`.

### Signature

```
bool `nav_suite_get_vertical_zupt_active`(const nav_suite_t* s);
```

Compile arity is 1.

## `nav_suite_get_zaru_active`

Include `nav_suite.h`. The C entry is `nav_suite_get_zaru_active`.

### Signature

```
bool `nav_suite_get_zaru_active`(const nav_suite_t* s);
```

Compile arity is 1.

True when the suite zero-rotation flag is raised. The suite standstill test reads this predicate: a zero GNSS speed raises the flag, and a fast GNSS speed on the same still IMU does not.

The matching Python reader on the `Navigator` wrapper is `zaru_active`. It takes no arguments. It reports the same flag as `nav_suite_get_zaru_active`. The Python suite probe reads it for that standstill test, so the still arm reports the flag and the moving arm does not.

## `nav_suite_local_ref_t`

`nav_suite_local_ref_t`. This type is not declared in a published header. Callers include `nav_suite.h`; they do not name this type.

### Signature

```
typedef struct {
    float h_m;
    float v_up_mps;
    float stddev_m;
    bool has_v;
} nav_suite_local_ref_t;
```

Members:

- `h_m` — `float h_m` — height above the NED origin in metres, positive up
- `v_up_mps` — `float v_up_mps` — climb rate of that source in m/s, positive up
- `stddev_m` — `float stddev_m` — 1-sigma of `h_m` in metres; 0 means the offset filter default
- `has_v` — `bool has_v` — whether `v_up_mps` is usable

Zero-initialized by `nav_suite_local_ref` before it fills the fields.

## `nav_suite_predict_step`

Include `nav_suite.h`. The C entry is `nav_suite_predict_step`.

### Signature

```
int `nav_suite_predict_step`(nav_suite_t* s, const ins_measurements_t* m, float* phi_out);
```

Compile arity is 3.

Time-propagation part of nav_suite_update(): the local-datum adjustment, the ARS/AHRS attitude hint, and ins_predict_step() on the INS sub-filter.

## `nav_suite_t`

Include `nav_suite.h`. The published type is `nav_suite_t`.

### Signature

```
typedef struct
{
    ins_t            ins;
    ahrs_t           ars;
    ahrs_t           ahrs;
    baro_alt_t       baro_alt;
    local_gnss_alt_t local_gnss;
    ahrs_config_t           ars_cfg;
    ahrs_config_t           ahrs_cfg;
    baro_alt_config_t       baro_cfg;
    local_gnss_alt_config_t local_gnss_cfg;
    ins_meas_att_hint_t init_att_hint;
    bool   vertical_datum_aligned;
    double datum_origin_ecef[3];
    float datum_offset_m;
    float datum_offset_var_min;
    baro_alt_time_us_t datum_offset_t_last;
    bool datum_offset_valid;
    bool local_frame_external;
    float local_pos_offset_ned[3];
    bool  local_pos_offset_valid;
    bool  local_pos_datum_locked;
    bool wgs84_anchor_seen;
    bool ars_yaw_from_init;
    struct
    {
        bool          valid;
        float         yaw_ins_rad;
        float         yaw_ars_rad;
        float         stddev_rad;
        ins_time_us_t t;
        bool          out_valid;
        float         out_yaw_rad;
    } yaw_carry;
    bool last_zaru_trigger;
    bool last_vertical_zupt;
    double             baro_boot_p_sum;
    uint32_t           baro_boot_count;
    baro_alt_time_us_t baro_boot_t0;
    struct
    {
        ins_measurements_t m;
        bool               active;
    } step_ctx;
    struct
    {
        nav_suite_mode_t last_mode;
        ins_time_us_t t_last_gyr_bias_warn;
        ins_time_us_t t_last_vvel_warn;
        ins_time_us_t t_last_height_warn;
        ins_time_us_t t_last_yaw_warn;
        bool last_ins_initialized;
    } log_state;
} nav_suite_t;
```

Members the caller compiles against:

- `ins` — `ins_t ins`
- `ars` — `ahrs_t ars`
- `ahrs` — `ahrs_t ahrs`
- `baro_alt` — `baro_alt_t baro_alt`
- `local_gnss` — `local_gnss_alt_t local_gnss`
- `ars_cfg` — `ahrs_config_t ars_cfg`
- `ahrs_cfg` — `ahrs_config_t ahrs_cfg`
- `baro_cfg` — `baro_alt_config_t baro_cfg`
- `local_gnss_cfg` — `local_gnss_alt_config_t local_gnss_cfg`
- `init_att_hint` — `ins_meas_att_hint_t init_att_hint`
- `vertical_datum_aligned` — `bool vertical_datum_aligned`
- `datum_origin_ecef` — `double datum_origin_ecef[3]`
- `datum_offset_m` — `float datum_offset_m`
- `datum_offset_var_min` — `float datum_offset_var_min`
- `datum_offset_t_last` — `baro_alt_time_us_t datum_offset_t_last`
- `datum_offset_valid` — `bool datum_offset_valid`
- `local_frame_external` — `bool local_frame_external`
- `local_pos_offset_ned` — `float local_pos_offset_ned[3]`
- `local_pos_offset_valid` — `bool local_pos_offset_valid`
- `local_pos_datum_locked` — `bool local_pos_datum_locked`
- `wgs84_anchor_seen` — `bool wgs84_anchor_seen`
- `ars_yaw_from_init` — `bool ars_yaw_from_init`
- `yaw_carry` — `struct { ... } yaw_carry`
- `last_zaru_trigger` — `bool last_zaru_trigger`
- `last_vertical_zupt` — `bool last_vertical_zupt`
- `baro_boot_p_sum` — `double baro_boot_p_sum`
- `baro_boot_count` — `uint32_t baro_boot_count`
- `baro_boot_t0` — `baro_alt_time_us_t baro_boot_t0`
- `step_ctx` — `struct { ... } step_ctx`
- `log_state` — `struct { ... } log_state`

Caller-owned wrapper. Zero before `nav_suite_init`. Nested anonymous structs `yaw_carry`, `step_ctx`, and `log_state` are part of the published layout. Individual filters remain reachable through their own accessors.

## `nav_suite_update`

Include `nav_suite.h`. The C entry is `nav_suite_update`.

### Signature

```
void `nav_suite_update`(nav_suite_t* s, const ins_measurements_t* m);
```

Compile arity is 2.

Feed one measurement epoch to all three filters.

The matching Python navigator, after `nav = `Navigator`(`Config`(...))`, uses the same three-move loop as the `Ins` wrapper: push the sample that begins the epoch, push aiding present on that epoch, run the epoch, then read. These are the same method spellings the `Ins` wrapper already uses for those moves, not a second Python API. Readers do not themselves run the filter.

```
nav.`imu`(timestamp, dt, specific_force, rotation)
nav.`imu`(timestamp, dt, specific_force, rotation, `acc_var`=..., `gyr_var`=...)
nav.`mag`(field, variance)
nav.`gnss_pos`(ecef, variance)
nav.`gnss_pos`(ecef, covariance)
nav.`gnss_vel`(vel_ned, variance)
nav.`update`()
nav.`velocity_ned`()
```

`imu` takes a timestamp in microseconds, the strapdown interval in seconds, specific force as a 3-sequence in body FRD, and rotation as a 3-sequence in body FRD. Optional `acc_var` and `gyr_var` are 3-sequences; all-zero means fall back to configured PSD. This push begins the epoch.

`mag` takes the magnetometer field as a 3-sequence in body FRD plus per-axis variance. All-zero variance is the weak default, not a zero-noise lock.

`gnss_pos` takes ECEF metres as a 3-sequence plus either a 3-sequence of NED diagonal variances or a full 3-by-3 NED covariance.

`gnss_vel` takes NED metres per second as a 3-sequence plus a 3-sequence of NED diagonal variances.

Any subset of `mag`, `gnss_pos`, and `gnss_vel` may be pushed on that same epoch, including each one alone and all three together. Aiding pushes are optional on an IMU-only epoch. Those pushes do not themselves run the filter.

`update` runs the epoch. It takes no arguments. Forgetting `update` leaves that epoch un-run.

`velocity_ned` is the navigation filter's NED velocity on this stream. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published. It is a separate read from the attitude solution on the same epoch. While roll and pitch are published, that attitude solution carries no velocity.

On this suite path, ARS starts from the first valid IMU epoch and is not measurement-corrected by a magnetometer sample or by GNSS position or GNSS velocity. AHRS does not start until a magnetometer sample.

## `origin_ecef`

Published member `origin_ecef`.

It appears on:

- `ins_t` (`double origin_ecef[3]`)

## `out_valid`

Published member `out_valid`.

It appears on:

- `nav_suite_t` (`bool out_valid`)

## `out_yaw_rad`

Published member `out_yaw_rad`.

It appears on:

- `nav_suite_t` (`float out_yaw_rad`)

## `pos_local`

Published member `pos_local`.

It appears on:

- `ins_state_t` (`float pos_local[3]`)
- `ins_t` (`float pos_local[3]`)

## `pressure_pa`

Published member `pressure_pa`.

It appears on:

- `ins_meas_baro_t` (`float pressure_pa`)
- `ins_t` (`float pressure_pa`)
- `baro_alt_t` (`float pressure_pa`)

## `run_fusion`

Published member `run_fusion`.

It appears on:

- `ins_t` (`bool run_fusion`)

## `sgemm_`

Include `miniblas.h`. The C entry is `sgemm_`.

### Signature

```
int `sgemm_`(const char* transa, const char* transb, int* m, int* n, int* k, float* alpha, float* a, int* lda, float* b, int* ldb, float* beta, float* c, int* ldc);
```

Compile arity is 13.

## `ssymm_`

Include `miniblas.h`. The C entry is `ssymm_`.

### Signature

```
int `ssymm_`(const char* side, const char* uplo, int* m, int* n, float* alpha, float* a, int* lda, float* b, int* ldb, float* beta, float* c, int* ldc);
```

Compile arity is 12.

## `ssyrk_`

Include `miniblas.h`. The C entry is `ssyrk_`.

### Signature

```
int `ssyrk_`(const char* uplo, const char* trans, int* n, int* k, float* alpha, float* a, int* lda, float* beta, float* c, int* ldc);
```

Compile arity is 10.

## `stddev_m`

Published member `stddev_m`.

It appears on:

- `ins_meas_baro_t` (`float stddev_m`)
- `ins_t` (`float stddev_m`)

## `stddev_rad`

Published member `stddev_rad`.

It appears on:

- `ins_meas_yaw_t` (`float stddev_rad`)
- `nav_suite_t` (`float stddev_rad`)

## `strmm_`

Include `miniblas.h`. The C entry is `strmm_`.

### Signature

```
int `strmm_`(const char* side, const char* uplo, const char* transa, const char* diag, int* m, int* n, float* alpha, float* a, int* lda, float* b, int* ldb);
```

Compile arity is 11.

## `strsm_`

Include `miniblas.h`. The C entry is `strsm_`.

### Signature

```
int `strsm_`(const char* side, const char* uplo, const char* transa, const char* diag, int* m, int* n, float* alpha, const float* a, int* lda, float* b, int* ldb);
```

Compile arity is 11.

## `stuck_gyr_count`

Published member `stuck_gyr_count`.

It appears on:

- `ins_t` (`uint32_t stuck_gyr_count`)

## `t`

Published member `t`.

It appears on:

- `ins_t` (`ins_time_us_t t`)
- `ahrs_t` (`ahrs_time_us_t t`)
- `nav_suite_t` (`ins_time_us_t t`)

## `t_acc_bias_window`

Published member `t_acc_bias_window`.

It appears on:

- `ins_t` (`ins_time_us_t t_acc_bias_window`)

## `t_gyr_bias_window`

Published member `t_gyr_bias_window`.

It appears on:

- `ins_t` (`ins_time_us_t t_gyr_bias_window`)
- `ahrs_t` (`ahrs_time_us_t t_gyr_bias_window`)

## `t_last_acc_bias_prior_warn`

Published member `t_last_acc_bias_prior_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_acc_bias_prior_warn`)
- `baro_alt_t` (`baro_alt_time_us_t t_last_acc_bias_prior_warn`)

## `t_last_acc_bias_sanity_warn`

Published member `t_last_acc_bias_sanity_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_acc_bias_sanity_warn`)

## `t_last_baro_height_aid`

Published member `t_last_baro_height_aid`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_baro_height_aid`)

## `t_last_baro_height_warn`

Published member `t_last_baro_height_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_baro_height_warn`)

## `t_last_entry_gate_warn`

Published member `t_last_entry_gate_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_entry_gate_warn`)

## `t_last_gap_warn`

Published member `t_last_gap_warn`.

It appears on:

- `baro_alt_t` (`baro_alt_time_us_t t_last_gap_warn`)

## `t_last_gnss_outage_warn`

Published member `t_last_gnss_outage_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_gnss_outage_warn`)

## `t_last_gyr_bias_prior_warn`

Published member `t_last_gyr_bias_prior_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_gyr_bias_prior_warn`)

## `t_last_gyr_bias_sanity_warn`

Published member `t_last_gyr_bias_sanity_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_gyr_bias_sanity_warn`)
- `ahrs_t` (`ahrs_time_us_t t_last_gyr_bias_sanity_warn`)

## `t_last_gyr_bias_warn`

Published member `t_last_gyr_bias_warn`.

It appears on:

- `nav_suite_t` (`ins_time_us_t t_last_gyr_bias_warn`)

## `t_last_height_warn`

Published member `t_last_height_warn`.

It appears on:

- `nav_suite_t` (`ins_time_us_t t_last_height_warn`)

## `t_last_invalid_warn`

Published member `t_last_invalid_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_invalid_warn`)

## `t_last_large_pos_res_log`

Published member `t_last_large_pos_res_log`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_large_pos_res_log`)

## `t_last_mag_disturb_warn`

Published member `t_last_mag_disturb_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_mag_disturb_warn`)

## `t_last_mag_gap_warn`

Published member `t_last_mag_gap_warn`.

It appears on:

- `ahrs_t` (`ahrs_time_us_t t_last_mag_gap_warn`)

## `t_last_stuck_warn`

Published member `t_last_stuck_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_stuck_warn`)

## `t_last_vvel_warn`

Published member `t_last_vvel_warn`.

It appears on:

- `nav_suite_t` (`ins_time_us_t t_last_vvel_warn`)

## `t_last_yaw_aid`

Published member `t_last_yaw_aid`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_yaw_aid`)

## `t_last_yaw_stddev_warn`

Published member `t_last_yaw_stddev_warn`.

It appears on:

- `ins_t` (`ins_time_us_t t_last_yaw_stddev_warn`)

## `t_last_yaw_warn`

Published member `t_last_yaw_warn`.

It appears on:

- `nav_suite_t` (`ins_time_us_t t_last_yaw_warn`)

## `t_yaw_stddev_window`

Published member `t_yaw_stddev_window`.

It appears on:

- `ins_t` (`ins_time_us_t t_yaw_stddev_window`)
- `ahrs_t` (`ahrs_time_us_t t_yaw_stddev_window`)

## `trisolve`

Include `linalg.h`. The C entry is `trisolve`.

### Signature

```
void `trisolve`(const float* A, float* B, int n, int m, const char* tp);
```

Compile arity is 5.

Triangular solve BLAS: ?trsm.

## `trisolveright`

Include `linalg.h`. The C entry is `trisolveright`.

### Signature

```
void `trisolveright`(const float* L, float* A, int n, int m, const char* tp);
```

Compile arity is 5.

Triangular solve (right hand side). BLAS: ?trsm.

## `valid`

Published member `valid`.

It appears on:

- `ins_t` (`bool valid`)
- `nav_suite_t` (`bool valid`)

## `yaw_ars_rad`

Published member `yaw_ars_rad`.

It appears on:

- `nav_suite_t` (`float yaw_ars_rad`)

## `yaw_ins_rad`

Published member `yaw_ins_rad`.

It appears on:

- `nav_suite_t` (`float yaw_ins_rad`)

## `yaw_stddev_window_deg`

Published member `yaw_stddev_window_deg`.

It appears on:

- `ins_t` (`float yaw_stddev_window_deg`)
- `ahrs_t` (`float yaw_stddev_window_deg`)

## `zero_rotation_update`

Published member `zero_rotation_update`.

It appears on:

- `ins_measurements_t` (`bool zero_rotation_update`)
- `ahrs_t` (`bool zero_rotation_update`)

## `ins_init`

Include `ins.h`. The C entry is `ins_init`.

### Signature

```
int `ins_init`(ins_t* f, const ins_init_t* init, const ins_options_t* opt);
```

Compile arity is 3.

Zero the instance before the first call. Returns 0 on success, -1 on failure (for example an invalid ECEF origin).

Python construction is `Ins`(`Config`(...)) as on Config. This C entry is not a second Python constructor. After that start, the wrapper is driven by the three-move loop on the INS epoch and accessor symbols.

## `ins_is_ready`

Include `ins.h`. The C entry is `ins_is_ready`.

### Signature

```
bool `ins_is_ready`(const ins_t* f);
```

Compile arity is 1.

Is the filter ready to publish a solution?.

The matching Python reader on the `Ins` wrapper is `is_ready`. It takes no arguments. It does not run the filter. It is true when the wrapper is ready to publish a navigation solution, and false otherwise. Forgetting the epoch step leaves it false.

The `Navigator` wrapper has a reader with the same spelling and meaning, reporting the suite's INS sub-filter. `is_ready` is the ready flag. It takes no arguments. It does not run the filter.

## `ins_get_position_ecef`

Include `ins.h`. The C entry is `ins_get_position_ecef`.

### Signature

```
bool `ins_get_position_ecef`(const ins_t* f, double pos_ecef[3]);
```

Compile arity is 2.

Get current position in ECEF.

The matching Python reader on the `Ins` wrapper is `position_ecef`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published.

The `Navigator` wrapper has a reader with the same spelling and meaning, reporting the suite's INS sub-filter. `position_ecef` takes no arguments and does not run the filter. It yields None when unpublished and a 3-sequence when published.

## `ins_get_position_local`

Include `ins.h`. The C entry is `ins_get_position_local`.

### Signature

```
bool `ins_get_position_local`(const ins_t* f, float pos_ned[3]);
```

Compile arity is 2.

Get current position in the local NED frame (relative to the origin set at ins_init()).

The matching Python reader on the `Ins` wrapper is `position_local`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published.

The `Navigator` wrapper has a reader with the same spelling and meaning, reporting the suite's INS sub-filter. `position_local` takes no arguments and does not run the filter. It yields None when unpublished and a 3-sequence when published.

## `ins_get_velocity_ned`

Include `ins.h`. The C entry is `ins_get_velocity_ned`.

### Signature

```
bool `ins_get_velocity_ned`(const ins_t* f, float vel_ned[3]);
```

Compile arity is 2.

Get current velocity in the NED frame.

The matching Python reader on the `Ins` wrapper is `velocity_ned`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published.

## `ins_get_bias_acc`

Include `ins.h`. The C entry is `ins_get_bias_acc`.

### Signature

```
bool `ins_get_bias_acc`(const ins_t* f, float acc_bias_mps2[3]);
```

Compile arity is 2.

Get current accelerometer bias estimate.

The matching Python reader on the `Ins` wrapper is `bias_acc`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published.

## `ins_get_bias_gyr`

Include `ins.h`. The C entry is `ins_get_bias_gyr`.

### Signature

```
bool `ins_get_bias_gyr`(const ins_t* f, float gyr_bias_rps[3]);
```

Compile arity is 2.

Get current gyroscope bias estimate.

The matching Python reader on the `Ins` wrapper is `bias_gyr`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published.

## `ins_auto_zupt_active`

Include `ins.h`. The C entry is `ins_auto_zupt_active`.

### Signature

```
bool `ins_auto_zupt_active`(const ins_t* f);
```

Compile arity is 1.

True when the detector currently considers the platform stationary. This call does not run the filter.

The matching Python reader on the `Ins` wrapper is `auto_zupt_active`. It takes no arguments. It does not run the filter. It is true when the detector currently considers the platform stationary.

## `ins_set_magnetic_model_from_position`

Include `ins.h`. The C entry is `ins_set_magnetic_model_from_position`.

### Signature

```
void `ins_set_magnetic_model_from_position`(ins_t* f, double lat_rad, double lon_rad, float year);
```

Compile arity is 4.

Set the magnetic reference field from a position, via the World Magnetic Model (declination + inclination + total field).

The matching Python call on the `Ins` wrapper is `set_magnetic_model`. It takes latitude in radians, longitude in radians, and decimal year. It does not itself run the filter. It is not a second Python construction API.

## `ins_init_t`

Include `ins.h`. The published type is `ins_init_t`.

### Signature

```
typedef struct {
    ins_time_us_t time;
    double x_ecef[3];
    double xdot_ecef[3];
    float rpy_init_rad[3];
    float acc_bias_init_mps2[3];
    float gyr_bias_init_rps[3];
    float pos_init_stddev_m;
    float vel_init_stddev_mps;
    float rpy_init_stddev_rad[3];
    float acc_bias_init_stddev_mps2;
    float gyr_bias_init_stddev_rps;
    float pos_pred_stddev_m_sqrts;
    float vel_pred_stddev_mps_sqrts;
    float rpy_pred_stddev_rad_sqrts;
    float acc_bias_pred_stddev_mps2_sqrts;
    float gyr_bias_pred_stddev_rps_sqrts;
    float zero_vel_stddev_mps;
    float zero_rot_stddev_rps;
    float gravity_n[3];
    float magnetic_n[3];
    float mag_bias_init_stddev_ut;
    float mag_bias_pred_stddev_ut_sqrts;
} ins_init_t;
```

Members the caller compiles against:

- `time` — `ins_time_us_t time`
- `x_ecef` — `double x_ecef[3]`
- `xdot_ecef` — `double xdot_ecef[3]`
- `rpy_init_rad` — `float rpy_init_rad[3]`
- `acc_bias_init_mps2` — `float acc_bias_init_mps2[3]`
- `gyr_bias_init_rps` — `float gyr_bias_init_rps[3]`
- `pos_init_stddev_m` — `float pos_init_stddev_m`
- `vel_init_stddev_mps` — `float vel_init_stddev_mps`
- `rpy_init_stddev_rad` — `float rpy_init_stddev_rad[3]`
- `acc_bias_init_stddev_mps2` — `float acc_bias_init_stddev_mps2`
- `gyr_bias_init_stddev_rps` — `float gyr_bias_init_stddev_rps`
- `pos_pred_stddev_m_sqrts` — `float pos_pred_stddev_m_sqrts`
- `vel_pred_stddev_mps_sqrts` — `float vel_pred_stddev_mps_sqrts`
- `rpy_pred_stddev_rad_sqrts` — `float rpy_pred_stddev_rad_sqrts`
- `acc_bias_pred_stddev_mps2_sqrts` — `float acc_bias_pred_stddev_mps2_sqrts`
- `gyr_bias_pred_stddev_rps_sqrts` — `float gyr_bias_pred_stddev_rps_sqrts`
- `zero_vel_stddev_mps` — `float zero_vel_stddev_mps`
- `zero_rot_stddev_rps` — `float zero_rot_stddev_rps`
- `gravity_n` — `float gravity_n[3]`
- `magnetic_n` — `float magnetic_n[3]`
- `mag_bias_init_stddev_ut` — `float mag_bias_init_stddev_ut`
- `mag_bias_pred_stddev_ut_sqrts` — `float mag_bias_pred_stddev_ut_sqrts`

The Python construction keyword `magnetic_n` on `Config` is this NED magnetic reference as a 3-sequence. The Python construction keyword `rpy_init_rad` on `Config` is this initial roll/pitch/yaw as a 3-sequence in radians. That is not a second Python init type.

## `INS_IDX_ACC`

Include `ins.h`. The published grouping offset is `INS_IDX_ACC`.

### Signature

```
#define `INS_IDX_ACC`
```

Integer sub-state offset. It is the published grouping offset for accelerometer-bias error-state 1-sigma on the UDU factors `n`, `U`, and `d` of `ins_t`.

## `INS_IDX_GYR`

Include `ins.h`. The published grouping offset is `INS_IDX_GYR`.

### Signature

```
#define `INS_IDX_GYR`
```

Integer sub-state offset. It is the published grouping offset for gyroscope-bias error-state 1-sigma on the UDU factors `n`, `U`, and `d` of `ins_t`.

## `ins_options_t`

Include `ins.h`. The published type is `ins_options_t`.

### Signature

```
typedef struct {
    float kalman_update_dt_sec;
    float max_prediction_time_sec;
    float gnss_max_horizontal_pos_stddev_m;
    float gnss_max_vertical_pos_stddev_m;
    float gnss_max_horizontal_vel_stddev_mps;
    float gnss_max_vertical_vel_stddev_mps;
    int magnetometer_min_delay_ms;
    bool allow_unlimited_deadreckoning;
    float max_deadreckoning_sec;
    bool auto_init;
    float auto_init_window_sec;
    float auto_init_static_gyr_rps;
    float auto_init_static_acc_mps2;
    float auto_init_moving_rpy_stddev_rad;
    float gnss_init_dwell_sec;
    bool gnss_init_dwell_disable;
    bool auto_reacquire_disable;
    bool auto_zupt_disable;
    float auto_zupt_static_gyr_rps;
    float auto_zupt_static_acc_mps2;
    float auto_zupt_max_vel_mps;
    float auto_zupt_dwell_sec;
    float auto_zupt_min_interval_sec;
    float mag_field_tolerance;
    bool mag_field_check_disable;
    bool estimate_mag_bias;
    bool automotive_mode;
    float automotive_min_speed_mps;
    float automotive_min_yaw_stddev;
    bool chi2_disable;
    float imu_acc_misalignment[9];
    float imu_gyr_misalignment[9];
    float imu_acc_fixed_bias[3];
    float imu_gyr_fixed_bias[3];
    float gnss_pos_cov_scale;
    float gnss_vel_cov_scale;
    float gnss_pos_stddev_floor_hor_m;
    float gnss_pos_stddev_floor_ver_m;
    float gnss_vel_stddev_floor_hor_mps;
    float gnss_vel_stddev_floor_ver_mps;
    float mag_misalignment[9];
    float mag_fixed_bias[3];
    float gnss_pos_cov_scale_height;
    float chi2_reject_alpha;
    float auto_zupt_static_gyr_stddev_rps;
    float auto_zupt_static_acc_stddev_mps2;
    float gnss_start_max_horizontal_pos_stddev_m;
    float gnss_start_max_vertical_pos_stddev_m;
    float gnss_start_max_horizontal_vel_stddev_mps;
    float gnss_start_max_vertical_vel_stddev_mps;
    float gnss_stop_max_horizontal_pos_stddev_m;
    float gnss_stop_max_vertical_pos_stddev_m;
    float gnss_stop_max_horizontal_vel_stddev_mps;
    float gnss_stop_max_vertical_vel_stddev_mps;
    float gnss_stop_dwell_sec;
    bool gnss_stop_disable;
    bool baro_height_disable;
    float auto_zupt_max_vel_stddev_mps;
    bool auto_zupt_velocity_blind_disable;
    int gnss_pos_decimation;
    float speed_scale;
    float speed_stddev_rel;
    float speed_min_mps;
    float gnss_pos_stddev_cap_hor_m;
    float gnss_pos_stddev_cap_ver_m;
    float gnss_vel_stddev_cap_hor_mps;
    float gnss_vel_stddev_cap_ver_mps;
    float gnss_acc_envelope_tau_sec;
    float gnss_vel_noise_acc_scale_hor;
    float gnss_vel_noise_acc_scale_ver;
    float gnss_vel_noise_acc_window_sec;
    int gnss_min_delay_ms;
} ins_options_t;
```

Members the caller compiles against:

- `kalman_update_dt_sec` — `float kalman_update_dt_sec`
- `max_prediction_time_sec` — `float max_prediction_time_sec`
- `gnss_max_horizontal_pos_stddev_m` — `float gnss_max_horizontal_pos_stddev_m`
- `gnss_max_vertical_pos_stddev_m` — `float gnss_max_vertical_pos_stddev_m`
- `gnss_max_horizontal_vel_stddev_mps` — `float gnss_max_horizontal_vel_stddev_mps`
- `gnss_max_vertical_vel_stddev_mps` — `float gnss_max_vertical_vel_stddev_mps`
- `magnetometer_min_delay_ms` — `int magnetometer_min_delay_ms`
- `allow_unlimited_deadreckoning` — `bool allow_unlimited_deadreckoning`
- `max_deadreckoning_sec` — `float max_deadreckoning_sec`
- `auto_init` — `bool auto_init`
- `auto_init_window_sec` — `float auto_init_window_sec`
- `auto_init_static_gyr_rps` — `float auto_init_static_gyr_rps`
- `auto_init_static_acc_mps2` — `float auto_init_static_acc_mps2`
- `auto_init_moving_rpy_stddev_rad` — `float auto_init_moving_rpy_stddev_rad`
- `gnss_init_dwell_sec` — `float gnss_init_dwell_sec`
- `gnss_init_dwell_disable` — `bool gnss_init_dwell_disable`
- `auto_reacquire_disable` — `bool auto_reacquire_disable`
- `auto_zupt_disable` — `bool auto_zupt_disable`
- `auto_zupt_static_gyr_rps` — `float auto_zupt_static_gyr_rps`
- `auto_zupt_static_acc_mps2` — `float auto_zupt_static_acc_mps2`
- `auto_zupt_max_vel_mps` — `float auto_zupt_max_vel_mps`
- `auto_zupt_dwell_sec` — `float auto_zupt_dwell_sec`
- `auto_zupt_min_interval_sec` — `float auto_zupt_min_interval_sec`
- `mag_field_tolerance` — `float mag_field_tolerance`
- `mag_field_check_disable` — `bool mag_field_check_disable`
- `estimate_mag_bias` — `bool estimate_mag_bias`
- `automotive_mode` — `bool automotive_mode`
- `automotive_min_speed_mps` — `float automotive_min_speed_mps`
- `automotive_min_yaw_stddev` — `float automotive_min_yaw_stddev`
- `chi2_disable` — `bool chi2_disable`
- `imu_acc_misalignment` — `float imu_acc_misalignment[9]`
- `imu_gyr_misalignment` — `float imu_gyr_misalignment[9]`
- `imu_acc_fixed_bias` — `float imu_acc_fixed_bias[3]`
- `imu_gyr_fixed_bias` — `float imu_gyr_fixed_bias[3]`
- `gnss_pos_cov_scale` — `float gnss_pos_cov_scale`
- `gnss_vel_cov_scale` — `float gnss_vel_cov_scale`
- `gnss_pos_stddev_floor_hor_m` — `float gnss_pos_stddev_floor_hor_m`
- `gnss_pos_stddev_floor_ver_m` — `float gnss_pos_stddev_floor_ver_m`
- `gnss_vel_stddev_floor_hor_mps` — `float gnss_vel_stddev_floor_hor_mps`
- `gnss_vel_stddev_floor_ver_mps` — `float gnss_vel_stddev_floor_ver_mps`
- `mag_misalignment` — `float mag_misalignment[9]`
- `mag_fixed_bias` — `float mag_fixed_bias[3]`
- `gnss_pos_cov_scale_height` — `float gnss_pos_cov_scale_height`
- `chi2_reject_alpha` — `float chi2_reject_alpha`
- `auto_zupt_static_gyr_stddev_rps` — `float auto_zupt_static_gyr_stddev_rps`
- `auto_zupt_static_acc_stddev_mps2` — `float auto_zupt_static_acc_stddev_mps2`
- `gnss_start_max_horizontal_pos_stddev_m` — `float gnss_start_max_horizontal_pos_stddev_m`
- `gnss_start_max_vertical_pos_stddev_m` — `float gnss_start_max_vertical_pos_stddev_m`
- `gnss_start_max_horizontal_vel_stddev_mps` — `float gnss_start_max_horizontal_vel_stddev_mps`
- `gnss_start_max_vertical_vel_stddev_mps` — `float gnss_start_max_vertical_vel_stddev_mps`
- `gnss_stop_max_horizontal_pos_stddev_m` — `float gnss_stop_max_horizontal_pos_stddev_m`
- `gnss_stop_max_vertical_pos_stddev_m` — `float gnss_stop_max_vertical_pos_stddev_m`
- `gnss_stop_max_horizontal_vel_stddev_mps` — `float gnss_stop_max_horizontal_vel_stddev_mps`
- `gnss_stop_max_vertical_vel_stddev_mps` — `float gnss_stop_max_vertical_vel_stddev_mps`
- `gnss_stop_dwell_sec` — `float gnss_stop_dwell_sec`
- `gnss_stop_disable` — `bool gnss_stop_disable`
- `baro_height_disable` — `bool baro_height_disable`
- `auto_zupt_max_vel_stddev_mps` — `float auto_zupt_max_vel_stddev_mps`
- `auto_zupt_velocity_blind_disable` — `bool auto_zupt_velocity_blind_disable`
- `gnss_pos_decimation` — `int gnss_pos_decimation`
- `speed_scale` — `float speed_scale`
- `speed_stddev_rel` — `float speed_stddev_rel`
- `speed_min_mps` — `float speed_min_mps`
- `gnss_pos_stddev_cap_hor_m` — `float gnss_pos_stddev_cap_hor_m`
- `gnss_pos_stddev_cap_ver_m` — `float gnss_pos_stddev_cap_ver_m`
- `gnss_vel_stddev_cap_hor_mps` — `float gnss_vel_stddev_cap_hor_mps`
- `gnss_vel_stddev_cap_ver_mps` — `float gnss_vel_stddev_cap_ver_mps`
- `gnss_acc_envelope_tau_sec` — `float gnss_acc_envelope_tau_sec`
- `gnss_vel_noise_acc_scale_hor` — `float gnss_vel_noise_acc_scale_hor`
- `gnss_vel_noise_acc_scale_ver` — `float gnss_vel_noise_acc_scale_ver`
- `gnss_vel_noise_acc_window_sec` — `float gnss_vel_noise_acc_window_sec`
- `gnss_min_delay_ms` — `int gnss_min_delay_ms`

Python construction keywords of the same fusion-gate names (`gnss_max_horizontal_pos_stddev_m`, `gnss_max_vertical_pos_stddev_m`, `gnss_max_horizontal_vel_stddev_mps`, `gnss_max_vertical_vel_stddev_mps`) set these C fields through `Config`. The same constructor also accepts `magnetometer_min_delay_ms`, `auto_zupt_disable`, `auto_zupt_velocity_blind_disable`, `baro_height_disable`, `chi2_disable`, and `gnss_min_delay_ms` for the matching C fields, and `rpy_init_rad` with the same meaning as the C init field. It also accepts `allow_unlimited_deadreckoning`, `gnss_init_dwell_disable`, `gnss_stop_disable`, `gnss_start_max_horizontal_pos_stddev_m`, `gnss_start_max_vertical_pos_stddev_m`, `gnss_start_max_horizontal_vel_stddev_mps`, `gnss_start_max_vertical_vel_stddev_mps`, `gnss_stop_max_horizontal_pos_stddev_m`, `gnss_stop_max_vertical_pos_stddev_m`, `gnss_stop_max_horizontal_vel_stddev_mps`, `gnss_stop_max_vertical_vel_stddev_mps`, `max_deadreckoning_sec`, and `gnss_pos_decimation` for the matching C fields. Omit `gnss_pos_decimation` to leave the default-off path. A zero `magnetometer_min_delay_ms` field means the built-in 1 s magnetometer interval; a negative delay disables the limit. A zero `gnss_min_delay_ms` field means the built-in GNSS fusion interval; a negative delay disables the limit. That is not a second Python options type. After `Ins`(`Config`(...)), the wrapper is driven by the three-move loop on the INS epoch and accessor symbols.

## `ins_deadreckoning_ms`

Include `ins.h`. The C entry is `ins_deadreckoning_ms`.

### Signature

```
int `ins_deadreckoning_ms`(const ins_t* f);
```

Compile arity is 1.

Integer milliseconds since the last absolute position aiding.

The matching Python reader on the `Ins` wrapper is `deadreckoning_ms`. It takes no arguments. It does not run the filter. It is integer milliseconds of published coasting age with the same meaning as `ins_deadreckoning_ms`.

## `ins_get_rpy_stddev`

Include `ins.h`. The C entry is `ins_get_rpy_stddev`.

### Signature

```
bool `ins_get_rpy_stddev`(const ins_t* f, float* roll_stddev_rad, float* pitch_stddev_rad, float* yaw_stddev_rad);
```

Compile arity is 4.

Get the current attitude 1-sigma uncertainty.

The matching Python reader on the `Ins` wrapper is `stddev`. It takes no arguments. It does not run the filter. When published it is a mapping that exposes `rpy`, `pos_ned`, `vel_ned`, `acc_bias`, and `gyr_bias` as 3-sequences of 1-sigma. Attitude is not published without `rpy` uncertainty.

## `ins_get_rpy`

Include `ins.h`. The C entry is `ins_get_rpy`.

### Signature

```
bool `ins_get_rpy`(const ins_t* f, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Get current attitude as roll/pitch/yaw.

The matching Python reader on the `Ins` wrapper is `rpy`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published. Attitude is not published without uncertainty: when `rpy` yields a 3-sequence, `stddev` is a mapping that exposes `rpy`, `pos_ned`, `vel_ned`, `acc_bias`, and `gyr_bias` as 3-sequences of 1-sigma.

## `ahrs_config_t`

Include `ahrs.h`. The published type is `ahrs_config_t`.

### Signature

```
typedef struct {
    ahrs_mode_t mode;
    float rpy_init_rad[3];
    float rpy_init_stddev_rad[3];
    float gyr_bias_init_rps[3];
    float gyr_bias_init_stddev_rps[3];
    float gyr_noise_psd;
    float gyr_bias_rw;
    float acc_noise_mps2;
    float kalman_update_dt_sec;
    float acc_freq_hz;
    float gravity_diff_penalty;
    float chi2_threshold;
    float acc_cutoff_freq_hz;
    float acc_reject_gravity_mps2;
    float mag_yaw_stddev_rad;
    float mag_freq_hz;
    float mag_chi2_threshold;
    bool mag_field_check_enable;
    float mag_field_tolerance;
    float zero_rot_stddev_rps;
    bool auto_zaru_disable;
    float auto_zaru_static_gyr_rps;
    float auto_zaru_static_acc_mps2;
    float auto_zaru_dwell_sec;
    float auto_zaru_static_gyr_stddev_rps;
    float auto_zaru_static_acc_stddev_mps2;
    bool precision_restart_disable;
    float restart_att_stddev_rad[3];
    float restart_warmup_sec;
    bool chi2_disable;
} ahrs_config_t;
```

Members the caller compiles against:

- `mode` — `ahrs_mode_t mode`. The published values of this field are `AHRS_MODE_ARS` (ARS: roll/pitch corrected, yaw free) and `AHRS_MODE_AHRS` (AHRS: roll/pitch plus magnetometer-aided yaw).
- `rpy_init_rad` — `float rpy_init_rad[3]`
- `rpy_init_stddev_rad` — `float rpy_init_stddev_rad[3]`
- `gyr_bias_init_rps` — `float gyr_bias_init_rps[3]`
- `gyr_bias_init_stddev_rps` — `float gyr_bias_init_stddev_rps[3]`
- `gyr_noise_psd` — `float gyr_noise_psd`
- `gyr_bias_rw` — `float gyr_bias_rw`
- `acc_noise_mps2` — `float acc_noise_mps2`
- `kalman_update_dt_sec` — `float kalman_update_dt_sec`
- `acc_freq_hz` — `float acc_freq_hz`
- `gravity_diff_penalty` — `float gravity_diff_penalty`
- `chi2_threshold` — `float chi2_threshold`
- `acc_cutoff_freq_hz` — `float acc_cutoff_freq_hz`
- `acc_reject_gravity_mps2` — `float acc_reject_gravity_mps2`
- `mag_yaw_stddev_rad` — `float mag_yaw_stddev_rad`
- `mag_freq_hz` — `float mag_freq_hz`
- `mag_chi2_threshold` — `float mag_chi2_threshold`
- `mag_field_check_enable` — `bool mag_field_check_enable`
- `mag_field_tolerance` — `float mag_field_tolerance`
- `zero_rot_stddev_rps` — `float zero_rot_stddev_rps`
- `auto_zaru_disable` — `bool auto_zaru_disable`
- `auto_zaru_static_gyr_rps` — `float auto_zaru_static_gyr_rps`
- `auto_zaru_static_acc_mps2` — `float auto_zaru_static_acc_mps2`
- `auto_zaru_dwell_sec` — `float auto_zaru_dwell_sec`
- `auto_zaru_static_gyr_stddev_rps` — `float auto_zaru_static_gyr_stddev_rps`
- `auto_zaru_static_acc_stddev_mps2` — `float auto_zaru_static_acc_stddev_mps2`
- `precision_restart_disable` — `bool precision_restart_disable`
- `restart_att_stddev_rad` — `float restart_att_stddev_rad[3]`
- `restart_warmup_sec` — `float restart_warmup_sec`
- `chi2_disable` — `bool chi2_disable`


Precision restart: once `restart_warmup_sec` has passed since init (0 → 10 s), a reported roll, pitch, or yaw 1-sigma above its entry of `restart_att_stddev_rad` (0 → 10°, 10°, 90°; the yaw entry is unused in ARS mode; a negative entry leaves that axis unchecked) makes the instance uninitialized, so its attitude accessors fail. `precision_restart_disable` turns the check off. The navigation suite re-bootstraps its own ARS and AHRS on the next suitable epoch; a standalone caller must re-init.
## `ahrs_get_rpy_stddev`

Include `ahrs.h`. The C entry is `ahrs_get_rpy_stddev`.

### Signature

```
bool `ahrs_get_rpy_stddev`(const ahrs_t* a, float* roll_stddev_rad, float* pitch_stddev_rad, float* yaw_stddev_rad);
```

Compile arity is 4.

Get the 1-sigma uncertainty of the current roll/pitch/yaw.

The matching Python readers on the `Navigator` wrapper are `rpy_stddev_ars` and `rpy_stddev_ahrs`. They take no arguments. They do not run the filter. They are `ahrs_get_rpy_stddev` applied to the suite's ARS and AHRS instances. They yield None when unpublished and a 3-sequence when published, with the same meaning as this C getter.

## `Config`

Import from the Python package: `from `NAVFILTER` import `Config`, `Ins``. The same `Config` is also used with the suite wrapper: `from `NAVFILTER` import `Config`, `Navigator``.

`Config` is the Python construction object. There is not a second Config type. The Earth anchor on this object is geodetic, not ECEF: latitude `lat_rad` and longitude `lon_rad` in radians, ellipsoidal height `h_m` in metres. The INS wrapper is started as `Ins`(`Config`(...)). The navigation-suite wrapper is started as `Navigator`(`Config`(...)) with `auto_init`, `lat_rad`, `lon_rad`, `h_m`, `allow_unlimited_deadreckoning`, and optional `rpy_init_rad`.

### Signature

```
`Config`(`auto_init`=True, `lat_rad`=..., `lon_rad`=..., `h_m`=...)
`Config`(`auto_init`=True, `lat_rad`=..., `lon_rad`=..., `h_m`=...,
         `gnss_max_horizontal_pos_stddev_m`=...,
         `gnss_max_vertical_pos_stddev_m`=...,
         `gnss_max_horizontal_vel_stddev_mps`=...,
         `gnss_max_vertical_vel_stddev_mps`=...)
`Config`(`auto_init`=True, `lat_rad`=..., `lon_rad`=..., `h_m`=...,
         `magnetometer_min_delay_ms`=...,
         `auto_zupt_disable`=...,
         `auto_zupt_velocity_blind_disable`=...,
         `baro_height_disable`=...,
         `magnetic_n`=...,
         `chi2_disable`=...,
         `rpy_init_rad`=...,
         `gnss_min_delay_ms`=...)
`Config`(`auto_init`=True, `lat_rad`=..., `lon_rad`=..., `h_m`=...,
         `allow_unlimited_deadreckoning`=...,
         `gnss_init_dwell_disable`=...,
         `gnss_stop_disable`=...,
         `gnss_start_max_horizontal_pos_stddev_m`=...,
         `gnss_start_max_vertical_pos_stddev_m`=...,
         `gnss_start_max_horizontal_vel_stddev_mps`=...,
         `gnss_start_max_vertical_vel_stddev_mps`=...,
         `gnss_stop_max_horizontal_pos_stddev_m`=...,
         `gnss_stop_max_vertical_pos_stddev_m`=...,
         `gnss_stop_max_horizontal_vel_stddev_mps`=...,
         `gnss_stop_max_vertical_vel_stddev_mps`=...,
         `max_deadreckoning_sec`=...,
         `gnss_pos_decimation`=...)
nav = `Ins`(`Config`(...))
nav = `Navigator`(`Config`(`auto_init`=..., `lat_rad`=..., `lon_rad`=..., `h_m`=...,
                          `allow_unlimited_deadreckoning`=..., `rpy_init_rad`=...))
```

Constructor keywords:

- `auto_init` — boolean; the auto-init happy path passes true
- `lat_rad` — geodetic latitude, radians
- `lon_rad` — geodetic longitude, radians
- `h_m` — ellipsoidal height, metres
- `gnss_max_horizontal_pos_stddev_m` — optional GNSS fusion-gate horizontal position 1-sigma, metres
- `gnss_max_vertical_pos_stddev_m` — optional GNSS fusion-gate vertical position 1-sigma, metres
- `gnss_max_horizontal_vel_stddev_mps` — optional GNSS fusion-gate horizontal velocity 1-sigma, metres per second
- `gnss_max_vertical_vel_stddev_mps` — optional GNSS fusion-gate vertical velocity 1-sigma, metres per second
- `magnetometer_min_delay_ms` — optional magnetometer fusion minimum interval, milliseconds. A zero delay field means the built-in 1 s magnetometer interval. A negative delay disables the limit.
- `auto_zupt_disable` — optional boolean; true turns the automatic ZUPT/ZARU detector off at construction
- `auto_zupt_velocity_blind_disable` — optional boolean; the same meaning as the C `auto_zupt_velocity_blind_disable` field
- `baro_height_disable` — optional boolean; true forces GNSS height instead of barometric height inside INS
- `magnetic_n` — optional NED magnetic reference as a 3-sequence
- `chi2_disable` — optional boolean; the same meaning as the C `chi2_disable` field
- `rpy_init_rad` — optional initial roll/pitch/yaw as a 3-sequence in radians; the same meaning as the C `rpy_init_rad` field
- `gnss_min_delay_ms` — optional GNSS fusion minimum interval, milliseconds. A zero delay field means the built-in GNSS fusion interval. A negative delay disables the limit.
- `allow_unlimited_deadreckoning` — optional boolean; the same meaning as the C `allow_unlimited_deadreckoning` field
- `gnss_init_dwell_disable` — optional boolean; the same meaning as the C `gnss_init_dwell_disable` field
- `gnss_stop_disable` — optional boolean; the same meaning as the C `gnss_stop_disable` field
- `gnss_start_max_horizontal_pos_stddev_m` — optional GNSS entry-gate horizontal position 1-sigma, metres
- `gnss_start_max_vertical_pos_stddev_m` — optional GNSS entry-gate vertical position 1-sigma, metres
- `gnss_start_max_horizontal_vel_stddev_mps` — optional GNSS entry-gate horizontal velocity 1-sigma, metres per second
- `gnss_start_max_vertical_vel_stddev_mps` — optional GNSS entry-gate vertical velocity 1-sigma, metres per second
- `gnss_stop_max_horizontal_pos_stddev_m` — optional GNSS exit-gate horizontal position 1-sigma, metres
- `gnss_stop_max_vertical_pos_stddev_m` — optional GNSS exit-gate vertical position 1-sigma, metres
- `gnss_stop_max_horizontal_vel_stddev_mps` — optional GNSS exit-gate horizontal velocity 1-sigma, metres per second
- `gnss_stop_max_vertical_vel_stddev_mps` — optional GNSS exit-gate vertical velocity 1-sigma, metres per second
- `max_deadreckoning_sec` — optional coasting window, seconds; the same meaning as the C `max_deadreckoning_sec` field
- `gnss_pos_decimation` — optional; the same meaning as the C `gnss_pos_decimation` field. Omit the keyword to leave the default-off path.

The four fusion-gate keywords and the other optional keywords may be omitted. `auto_init` true together with a ground geodetic site (Earth-scale, not a neighbourhood of the ECEF origin) starts the wrapper.

A failed start of `Ins`(`Config`(...)) raises `ValueError`. A failed start of `Navigator`(`Config`(...)) raises `ValueError`, the same as `Ins`. Neither yields a silent unstarted instance.

After a successful start, the `Ins` wrapper is driven by a three-move loop: push IMU (and any GNSS or other aiding), run the epoch, then read. Readers do not themselves run the filter. Construction of that INS wrapper stays this `Ins`(`Config`(...)) form. The push, epoch, and reader calling forms of that INS wrapper belong with the INS epoch and accessor symbols. The `Navigator` wrapper uses the same three-move spellings on a suite epoch: push the IMU that begins the epoch, push magnetometer, GNSS position, and GNSS velocity when that aiding is present, run the epoch, and read the navigation filter's NED velocity. Those Navigator calling forms belong with `nav_suite_update`. Suite readers belong with the navigation-suite symbols.

## `nav_suite_init`

Include `nav_suite.h`. The C entry is `nav_suite_init`.

### Signature

```
int `nav_suite_init`(nav_suite_t* s, const ins_init_t* init, const ins_options_t* opt);
```

Compile arity is 3.

The instance must be zeroed. Returns 0 on success, -1 on failure (including a null `init` or `opt`). The AHRS filters start on the first suitable measurement epoch; when auto-init is off, ARS initial yaw is seeded from `rpy_init_rad` index 2.

The matching Python construction is `Navigator`(`Config`(...)) as on Config, with `auto_init`, `lat_rad`, `lon_rad`, `h_m`, `allow_unlimited_deadreckoning`, and optional `rpy_init_rad`. That Python start is the matching start of this C `nav_suite_init` path, including that `auto_init` false plus `rpy_init_rad` index 2 seeds suite ARS yaw. A failed start raises `ValueError`, the same as `Ins`. This is not a second Config type.

## `nav_suite_get_rpy_ars`

Include `nav_suite.h`. The C entry is `nav_suite_get_rpy_ars`.

### Signature

```
bool `nav_suite_get_rpy_ars`(const nav_suite_t* s, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Roll/pitch/yaw of the roll/pitch (free yaw / gyro compassing) filter.

The matching Python reader on the `Navigator` wrapper is `rpy_ars`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published, with the same meaning as `nav_suite_get_rpy_ars`.

## `nav_suite_get_rpy_ahrs`

Include `nav_suite.h`. The C entry is `nav_suite_get_rpy_ahrs`.

### Signature

```
bool `nav_suite_get_rpy_ahrs`(const nav_suite_t* s, float* roll_rad, float* pitch_rad, float* yaw_rad);
```

Compile arity is 4.

Roll/pitch/yaw of the magnetometer-aided filter.

The matching Python reader on the `Navigator` wrapper is `rpy_ahrs`. It takes no arguments. It does not run the filter. It yields None when unpublished and a 3-sequence when published, with the same meaning as `nav_suite_get_rpy_ahrs`.

## `nav_suite_set_init_att_hint`

Include `nav_suite.h`. The C entry is `nav_suite_set_init_att_hint`.

### Signature

```
void `nav_suite_set_init_att_hint`(nav_suite_t* s, float roll_rad, float pitch_rad, float stddev_roll_pitch_rad, float yaw_rad, float stddev_yaw_rad);
```

Compile arity is 6.

Arm a static "I just know it" initial attitude hint for ins's auto-init bootstrap (e.g. a known launch heading with no magnetometer/GNSS-course yaw aiding to derive it from).

The matching Python spelling on the `Navigator` wrapper is `set_init_att_hint`. After construction and before the first update, the caller passes `yaw_rad` and `stddev_yaw_rad`. That is the static yaw hint. This is not a second Python API.

## `ahrs_mag_heading`

Include `ahrs.h`. The C entry is `ahrs_mag_heading`.

### Signature

```
float `ahrs_mag_heading`(const float mag_b[3], float roll_rad, float pitch_rad);
```

Compile arity is 3.

Tilt-compensated magnetic heading. Arguments are a body-FRD magnetometer sample plus roll and pitch; the return is yaw in radians.

The matching Python helper is `mag_heading` imported from `geodetic_toolbox` (not from the `NAVFILTER` package root): `from `geodetic_toolbox` import `mag_heading``. It takes the same three arguments and returns the same tilt-compensated magnetic heading. This is not a second heading formula.

## `baro_alt_get_isa_altitude`

Include `baro_alt.h`. The C entry is `baro_alt_get_isa_altitude`.

### Signature

```
bool `baro_alt_get_isa_altitude`(const baro_alt_t* b, float* h_isa_m);
```

Compile arity is 2.

Barometric ISA altitude in metres, positive up, readable separately from the datum-relative height. It still carries weather and model error.

## `local_gnss_alt_init`

Include `baro_alt.h`. The C entry is `local_gnss_alt_init`.

### Signature

```
int `local_gnss_alt_init`(local_gnss_alt_t* g, const local_gnss_alt_config_t* cfg, baro_alt_time_us_t t, float h_local_m, float local_stddev_m, float h_gnss_ell_m, float gnss_stddev_m);
```

Compile arity is 7.

Initialise (or reset) the offset filter from the first pair. Returns 0 on success, -1 on invalid arguments. 0 means the instance initialised and later accessors may publish; a nonzero return is refused-init.

## `baro_alt_update`

Include `baro_alt.h`. The C entry is `baro_alt_update`.

### Signature

```
void `baro_alt_update`(baro_alt_t* b, baro_alt_time_us_t t, const float acc_mps2[3], const float q_bn[4], float pressure_pa, float baro_stddev_m, bool baro_valid);
```

Compile arity is 7.

Feed one epoch and advance the filter. A 0 per-sample altitude 1-sigma (`baro_stddev_m`) means use the instance config value (the `baro_stddev_m` field of `baro_alt_config_t`; an all-zero config still fills the 2 m barometer altitude 1-sigma).

## `baro_alt_zero_velocity_update`

Include `baro_alt.h`. The C entry is `baro_alt_zero_velocity_update`.

### Signature

```
void `baro_alt_zero_velocity_update`(baro_alt_t* b, float stddev_mps);
```

Compile arity is 2.

Fuse a zero-velocity pseudo-measurement (ZUPT) into the vertical channel: z = 0 observing only v (H = [0 1 0]). A 0 1-sigma argument (`stddev_mps`) means use the configured ZUPT 1-sigma.

## `baro_alt_init`

Include `baro_alt.h`. The C entry is `baro_alt_init`.

### Signature

```
int `baro_alt_init`(baro_alt_t* b, const baro_alt_config_t* cfg, baro_alt_time_us_t t, float pressure_pa, float h_init_m, float h_init_stddev_m);
```

Compile arity is 6.

Initialise (or reset) the filter. Returns 0 on success, -1 on invalid arguments / implausible anchor. 0 means the instance initialised and later accessors may publish; a nonzero return is the refused-init outcome for a non-finite anchor or a negative pressure the tropospheric ISA conversion cannot map to a finite altitude.

## `baro_alt_pressure_plausible`

Include `baro_alt.h`. The C entry is `baro_alt_pressure_plausible`.

### Signature

```
bool `baro_alt_pressure_plausible`(float pressure_pa);
```

Compile arity is 1.

Is this a plausible static pressure sample? Finite pressure is required. A numeric 16 km ISA-altitude cap or below-sea-level floor on otherwise-finite positive pressure is the implementer's and is not scored.

## `bias_gyr_ahrs`

The matching Python reader on the `Navigator` wrapper is `bias_gyr_ahrs`.

### Signature

```
`bias_gyr_ahrs`()
```

It takes no arguments. It does not run the filter. It is `ahrs_get_bias_gyr` applied to the suite's AHRS instance. It yields None when unpublished and a 3-sequence when published, with the same meaning as `ahrs_get_bias_gyr` on that instance.

## `bias_gyr_ars`

The matching Python reader on the `Navigator` wrapper is `bias_gyr_ars`.

### Signature

```
`bias_gyr_ars`()
```

It takes no arguments. It does not run the filter. It is `ahrs_get_bias_gyr` applied to the suite's ARS instance. It yields None when unpublished and a 3-sequence when published, with the same meaning as `ahrs_get_bias_gyr` on that instance.

## `mode_name`

The matching Python reader on the `Navigator` wrapper is `mode_name`.

### Signature

```
`mode_name`()
```

It takes no arguments. It does not run the filter. It returns one of `FULL`, `COASTING`, `ATTITUDE_ONLY`, `NONE` as a string. Skipping the epoch step leaves `NONE`. An unused instance yields `NONE`.

## `dump_solution`

`--dump-solution` is a flag of the Python dataset-replay program `replay.py`. It is not an `Ins` method. The C library fields are not a substitute for this CLI.

### Signature

```
replay.py <dataset> `--dump-solution` FILE
```

The flag takes a file path. It writes a solution CSV at that path. Each data row is comma-separated and has ten fields: a time field, geodetic latitude in degrees, longitude in degrees, height in metres, then roll, pitch, and yaw in degrees, then north, east, and down velocity. Lines that begin with `#` are comments, not data rows. A data row is written only at an epoch where the INS position, INS attitude, and NED velocity are all published; an epoch where any of them is unpublished writes no row, not a row of empty or NaN cells. A run whose INS never publishes leaves a file of comment lines only.

The dump rate is the companion flag `--dump-solution-hz`.

## `dump_solution_hz`

`--dump-solution-hz` is a flag of the Python dataset-replay program `replay.py`. It is the dump rate of `--dump-solution`. It is not an `Ins` method. The C library fields are not a substitute for this CLI.

### Signature

```
replay.py <dataset> `--dump-solution` FILE `--dump-solution-hz`=...
```

The rate is given explicitly on the flag, attached with `=`. A written 0 is accepted and dumps every IMU epoch. A default exists when the flag is omitted.

## `gnss_pos_vel_cov`

After `nav = `Ins`(`Config`(...))`, the Python INS wrapper exposes `gnss_pos_vel_cov`. It is not a C function of that spelling. The C field it writes is `gnss_Qll_pos_vel_ned`. There is not a second C field for this push.

### Signature

```
nav.`gnss_pos_vel_cov`(cov)
```

`gnss_pos_vel_cov` takes a 3-by-3 NED position-velocity cross-covariance. It writes that matrix onto `gnss_Qll_pos_vel_ned` on the epoch bundle. It does not itself run the filter.

The push is optional. It is consumed together with `gnss_pos` and `gnss_vel` on that epoch. Non-finite entries are treated as zero, not as a dropped measurement payload.

## `ins_get_diag`

Include `ins.h`. The C entry is `ins_get_diag`.

### Signature

```
const ins_diag_t* `ins_get_diag`(const ins_t* f);
```

Compile arity is 1.

Access the passive debug/health bookkeeping.

The matching Python reader on the `Ins` wrapper is `diag`. It takes no arguments. It does not run the filter. It is a mapping that exposes `n_gnss_used`, `n_predict`, `n_gnss_seen`, `n_gnss_rejected_noise`, `n_invalid_input`, `n_downweighted`, `n_fuse_fail`, `n_auto_zupt`, `n_gnss_no_anchor`, and `n_time_backward`. `n_gnss_no_anchor` increments for GNSS older than 500 ms and for an in-window delay with no history match. Local-position and yaw skips do not increment it.

## `ins_diag_t`

Include `ins.h`. The published type is `ins_diag_t`.

### Signature

```
typedef struct {
    uint32_t n_updates;
    uint32_t n_predict;
    uint32_t n_time_backward;
    uint32_t n_time_dropped;
    uint32_t n_time_jump_reset;
    uint32_t n_time_restart_reset;
    int32_t dt_ms_min;
    int32_t dt_ms_max;
    uint32_t n_gnss_seen;
    uint32_t n_gnss_used;
    uint32_t n_gnss_rejected_noise;
    uint32_t n_gnss_quality_exit;
    uint32_t n_gnss_no_anchor;
    uint32_t n_gnss_large_residual;
    ins_time_us_t t_last_gnss_fusion;
    float last_gnss_pos_residual_m;
    float max_gnss_pos_residual_m;
    float last_gnss_vel_residual_mps;
    uint32_t n_baro_height_used;
    uint32_t n_speed_seen;
    uint32_t n_speed_used;
    uint32_t n_speed_skipped;
    float last_speed_residual_mps;
    uint32_t n_fuse_fail;
    uint32_t n_invalid_input;
    uint32_t n_downweighted;
    uint32_t n_auto_zupt;
    uint32_t n_acc_bias_prior_exceeded;
    uint32_t n_gyr_bias_prior_exceeded;
    uint32_t n_reacquire;
    uint32_t n_autoinit_moving;
    uint32_t n_health_reset;
    bool overconfident;
    uint32_t n_overconfident;
    float min_pos_stddev_m;
    float min_vel_stddev_mps;
    float min_att_stddev_deg;
    uint32_t n_gnss_rate_limited;
} ins_diag_t;
```

Members the caller compiles against:

- `n_updates` — `uint32_t n_updates`
- `n_predict` — `uint32_t n_predict`
- `n_time_backward` — `uint32_t n_time_backward`
- `n_time_dropped` — `uint32_t n_time_dropped`
- `n_time_jump_reset` — `uint32_t n_time_jump_reset`
- `n_time_restart_reset` — `uint32_t n_time_restart_reset`
- `dt_ms_min` — `int32_t dt_ms_min`
- `dt_ms_max` — `int32_t dt_ms_max`
- `n_gnss_seen` — `uint32_t n_gnss_seen`
- `n_gnss_used` — `uint32_t n_gnss_used`
- `n_gnss_rejected_noise` — `uint32_t n_gnss_rejected_noise`
- `n_gnss_quality_exit` — `uint32_t n_gnss_quality_exit`
- `n_gnss_no_anchor` — `uint32_t n_gnss_no_anchor`
- `n_gnss_large_residual` — `uint32_t n_gnss_large_residual`
- `t_last_gnss_fusion` — `ins_time_us_t t_last_gnss_fusion`
- `last_gnss_pos_residual_m` — `float last_gnss_pos_residual_m`
- `max_gnss_pos_residual_m` — `float max_gnss_pos_residual_m`
- `last_gnss_vel_residual_mps` — `float last_gnss_vel_residual_mps`
- `n_baro_height_used` — `uint32_t n_baro_height_used`
- `n_speed_seen` — `uint32_t n_speed_seen`
- `n_speed_used` — `uint32_t n_speed_used`
- `n_speed_skipped` — `uint32_t n_speed_skipped`
- `last_speed_residual_mps` — `float last_speed_residual_mps`
- `n_fuse_fail` — `uint32_t n_fuse_fail`
- `n_invalid_input` — `uint32_t n_invalid_input`
- `n_downweighted` — `uint32_t n_downweighted`
- `n_auto_zupt` — `uint32_t n_auto_zupt`
- `n_acc_bias_prior_exceeded` — `uint32_t n_acc_bias_prior_exceeded`
- `n_gyr_bias_prior_exceeded` — `uint32_t n_gyr_bias_prior_exceeded`
- `n_reacquire` — `uint32_t n_reacquire`
- `n_autoinit_moving` — `uint32_t n_autoinit_moving`
- `n_health_reset` — `uint32_t n_health_reset`
- `overconfident` — `bool overconfident`
- `n_overconfident` — `uint32_t n_overconfident`
- `min_pos_stddev_m` — `float min_pos_stddev_m`
- `min_vel_stddev_mps` — `float min_vel_stddev_mps`
- `min_att_stddev_deg` — `float min_att_stddev_deg`
- `n_gnss_rate_limited` — `uint32_t n_gnss_rate_limited`

The matching Python reader on the `Ins` wrapper is `diag`. It does not run the filter. It is a mapping that exposes `n_gnss_used`, `n_predict`, `n_gnss_seen`, `n_gnss_rejected_noise`, `n_invalid_input`, `n_downweighted`, `n_fuse_fail`, `n_auto_zupt`, `n_gnss_no_anchor`, and `n_time_backward`. `n_gnss_no_anchor` increments for GNSS older than 500 ms and for an in-window delay with no history match. Local-position and yaw skips do not increment it.

## `ins_update`

Include `ins.h`. The C entry is `ins_update`.

### Signature

```
void `ins_update`(ins_t* f, const ins_measurements_t* m);
```

Compile arity is 2.

Feed measurements and advance the filter.

The matching Python INS wrapper, after `nav = `Ins`(`Config`(...))`, uses a three-move loop: push IMU (and any GNSS or other aiding), run the epoch, then read. Readers do not themselves run the filter.

```
nav.`imu`(timestamp, dt, specific_force, rotation)
nav.`imu`(timestamp, dt, specific_force, rotation, `acc_var`=..., `gyr_var`=...)
nav.`gnss_pos`(ecef, variance)
nav.`gnss_pos`(ecef, covariance)
nav.`gnss_pos`(ecef, variance, `delay_ms`=...)
nav.`gnss_pos`(ecef, covariance, `delay_ms`=...)
nav.`gnss_vel`(vel_ned, variance)
nav.`gnss_vel`(vel_ned, covariance)
nav.`gnss_leverarm`(lever)
nav.`local_pos`(ned, variance)
nav.`local_pos`(ned, variance, `delay_ms`=...)
nav.`mag`(field, variance)
nav.`yaw`(heading_rad, stddev)
nav.`yaw`(heading_rad, stddev, `delay_ms`=...)
nav.`speed`(speed_mps)
nav.`speed`(speed_mps, stddev)
nav.`baro`(pressure_pa)
nav.`zupt`(flag)
nav.`zaru`(flag)
nav.`set_magnetic_model`(lat_rad, lon_rad, year)
nav.`update`()
```

`imu` takes a timestamp in microseconds, the strapdown interval in seconds, specific force as a 3-sequence in body FRD, and rotation as a 3-sequence in body FRD. Optional `acc_var` and `gyr_var` are 3-sequences; all-zero means fall back to configured PSD.

`gnss_pos` takes ECEF metres as a 3-sequence plus either a 3-sequence of NED diagonal variances or a full 3-by-3 NED covariance. An optional `delay_ms` keyword is how many milliseconds older than the current IMU epoch the sample is. The sample is fused against the history state at that time of validity. Zero means current-time fusion. This is the same delay keyword as on `local_pos` and `yaw`, not a second Python API.

`gnss_vel` takes NED metres per second as a 3-sequence plus the same variance-or-matrix choice.

`gnss_leverarm` takes the GNSS antenna lever arm as a 3-sequence in body FRD.

`local_pos` takes local NED metres as a 3-sequence plus a 3-sequence of NED diagonal variances. The same optional `delay_ms` keyword has the same meaning as on `gnss_pos`.

`mag` takes the magnetometer field as a 3-sequence in body FRD plus per-axis variance. All-zero variance is the weak default, not a zero-noise lock.

`yaw` takes heading in radians plus a 1-sigma. The same optional `delay_ms` keyword has the same meaning as on `gnss_pos`.

`speed` takes scalar ground speed in metres per second. An optional second argument is the per-sample 1-sigma, matching the C `stddev_mps` field.

`baro` takes static pressure in pascals.

`zupt` and `zaru` take a boolean standstill flag.

`set_magnetic_model` is the Python spelling of `ins_set_magnetic_model_from_position`. It takes latitude in radians, longitude in radians, and decimal year. It does not itself run the filter.

`update` runs the epoch. It takes no arguments. GNSS and other aiding pushes are optional on an IMU-only epoch. Forgetting `update` leaves that epoch un-run.

## `ins_measurements_t`

Include `ins.h`. The published type is `ins_measurements_t`.

### Signature

```
typedef struct {
    ins_time_us_t timestamp;
    float strapdown_dt_sec;
    ins_meas3_t acc;
    ins_meas3_t gyr;
    ins_meas3_t mag;
    ins_meas_gnss_pos_t gnss_pos;
    ins_meas_gnss_vel_t gnss_vel;
    float gnss_Qll_pos_vel_ned[3*3];
    float gnss_leverarm_b[3];
    int gps_week;
    int gps_itow_ms;
    int gnss_delay_ms;
    ins_meas_local_pos_t local_pos;
    float local_pos_leverarm_b[3];
    int local_pos_delay_ms;
    ins_meas_yaw_t yaw;
    int yaw_delay_ms;
    ins_meas_att_hint_t att_hint;
    ins_meas_baro_t baro;
    ins_meas_speed_t speed;
    int speed_delay_ms;
    bool zero_velocity_update;
    bool zero_rotation_update;
} ins_measurements_t;
```

Members the caller compiles against:

- `timestamp` — `ins_time_us_t timestamp`
- `strapdown_dt_sec` — `float strapdown_dt_sec`
- `acc` — `ins_meas3_t acc`
- `gyr` — `ins_meas3_t gyr`
- `mag` — `ins_meas3_t mag`
- `gnss_pos` — `ins_meas_gnss_pos_t gnss_pos`
- `gnss_vel` — `ins_meas_gnss_vel_t gnss_vel`
- `gnss_Qll_pos_vel_ned` — `float gnss_Qll_pos_vel_ned[3*3]`
- `gnss_leverarm_b` — `float gnss_leverarm_b[3]`
- `gps_week` — `int gps_week`
- `gps_itow_ms` — `int gps_itow_ms`
- `gnss_delay_ms` — `int gnss_delay_ms`
- `local_pos` — `ins_meas_local_pos_t local_pos`
- `local_pos_leverarm_b` — `float local_pos_leverarm_b[3]`
- `local_pos_delay_ms` — `int local_pos_delay_ms`
- `yaw` — `ins_meas_yaw_t yaw`
- `yaw_delay_ms` — `int yaw_delay_ms`
- `att_hint` — `ins_meas_att_hint_t att_hint`
- `baro` — `ins_meas_baro_t baro`
- `speed` — `ins_meas_speed_t speed`
- `speed_delay_ms` — `int speed_delay_ms`
- `zero_velocity_update` — `bool zero_velocity_update`
- `zero_rotation_update` — `bool zero_rotation_update`

All sub-measurements are optional. Only those marked valid are consumed. Zero the struct and fill what is present. IMU specific force is FRD; GNSS position is ECEF metres with a 3×3 NED covariance stored column-major.

On the `Ins` wrapper the same epoch bundle is filled by Python pushes, then `update` runs it. `imu` writes timestamp, strapdown interval, specific force, and rotation (the C `acc` / `gyr` 3-vectors). Optional `acc_var` and `gyr_var` are 3-sequences; all-zero means fall back to configured PSD. `gnss_pos` writes ECEF metres plus either a 3-sequence of NED diagonal variances or a full 3-by-3 NED covariance (the C `gnss_pos` fields). An optional `delay_ms` keyword on `gnss_pos` writes the C `gnss_delay_ms` field: how many milliseconds older than the current IMU epoch the sample is, fused against the history state at that time of validity; zero means current-time fusion. `gnss_vel` writes NED velocity plus the same variance-or-matrix choice (the C `gnss_vel` fields). `gnss_leverarm` writes the antenna lever arm in body FRD (the C `gnss_leverarm_b` 3-vector). `local_pos` writes NED metres plus a 3-sequence of NED diagonal variances (the C `local_pos` fields). The same optional `delay_ms` keyword on `local_pos` writes the C `local_pos_delay_ms` field, with the same meaning. `mag` writes a 3-sequence plus per-axis variance (the C `mag` fields); all-zero variance is the weak default, not a zero-noise lock. `yaw` writes heading radians plus 1-sigma (the C `yaw` fields). The same optional `delay_ms` keyword on `yaw` writes the C `yaw_delay_ms` field, with the same meaning. That delay keyword is one Python spelling, not a second Python API. `speed` writes a scalar metres-per-second (the C `speed` field). An optional second argument is the per-sample 1-sigma, matching the C `stddev_mps` field. `baro` writes static pressure in pascals (the C `baro` field). `zupt` / `zaru` write the boolean standstill flags (the C `zero_velocity_update` / `zero_rotation_update`). `set_magnetic_model` is the Python spelling of `ins_set_magnetic_model_from_position` (latitude radians, longitude radians, decimal year); it is not a field of this struct. Those pushes do not themselves run the filter.

## `replay.py`

The Python dataset-replay program is `replay.py`. It is not an `Ins` method. The C library fields are not a substitute for this CLI.

### Signature

```
replay.py <dataset>
replay.py <dataset> --estimate-gnss-delay --plot-hz=...
```

It takes a dataset directory (or the `config.yaml` path in that directory).

`--estimate-gnss-delay` is the force-on GNSS-latency estimator switch. `--plot-hz` is the plot-rate flag.

A dataset directory holds CSV streams plus one `config.yaml`. That `config.yaml` is nested (section then key), not a flat top-level list of C members. It accepts the same `chi2_disable` switch already named on `Config` and `ins_options_t`. The top-level dataset field is `name`. Unlimited dead-reckoning is a top-level optional `allow_unlimited_deadreckoning`: a written 0 is the built-in default, and omitting the key is accepted. Required IMU densities are under `imu` as `gyr_psd` and `acc_psd` and must be written and positive: omitting either or writing 0 aborts. Under `imu` the suite also writes `gyr_bias_rw`, `acc_bias_rw`, and `auto_zupt_disable`. Filename overrides are under `inputs` (`imu`, `ref`, `gnss`, and the other stream names); unset keeps the conventional name. Scoring `min_epochs` is under `score`. The C program refuses a dataset that does not state a positive scoring minimum-epoch count, including a missing key, not only a written non-positive value; this Python program fills a zero default and still writes a solution. GNSS fallback is `gnss.`pos_stddev_fallback_m``: a two-element list `[horizontal, vertical]` of position 1-sigma in metres, not a single number. Under `gnss` the suite also writes `delay_ms`, `leverarm_frd`, and `vel_stddev_fallback_mps` (one velocity 1-sigma in m/s). A zero diagonal entry of a `gnss.csv` covariance is replaced by the horizontal position fallback for north and east, the vertical one for down, and the velocity fallback for each velocity axis; under aiding `ref` the synthesized fix carries exactly those variances. When aiding is `ref`, omitting either fallback key, or writing 0 for the velocity fallback or for either element of the position fallback, aborts. `mag`, `baro`, and `speed` each write `enable` under that section, not a top-level enable name. Under `speed`, `delay_ms` and `stddev_mps` come from this file, not extra CSV columns. Under `score` the suite also writes `warmup_sec`, `ahrs`, `attitude`, `lim_pos_rms_m`, `lim_baro_rms_m`, `lim_att_bias_deg`, `lim_att_std_deg`, `lim_yaw_bias_deg`, `lim_yaw_std_deg`, and when AHRS scoring is on `lim_ars_att_bias_deg`, `lim_ars_roll_std_deg`, `lim_ars_pitch_std_deg`, and `lim_ars_yaw_drift_deg_min`. Sections `origin` (`lat_deg`, `lon_deg`, `h_m`) and `crazyflie` are accepted and ignored. A typo inside an owned section still fails and names the offender. Optional keys still treat written 0 as the built-in default. Value types: `name` is text; `aiding` and `init` take the words listed for the dataset harness; `chi2_disable`, `allow_unlimited_deadreckoning`, `imu.auto_zupt_disable`, each section's `enable`, `score.ahrs`, and `score.attitude` are 0/1 switches; `imu.gyr_psd` is in (rad/s)²/Hz and `imu.acc_psd` in (m/s²)²/Hz; `imu.gyr_bias_rw` is in rad/s/√s and `imu.acc_bias_rw` in m/s²/√s; `gnss.leverarm_frd` is a three-element list in metres, body FRD; both `delay_ms` keys are milliseconds; `speed.stddev_mps` is m/s; `score.warmup_sec` is seconds and `score.min_epochs` a whole count; each `score.lim_*` limit is in the unit its name ends with (`_deg` degrees, `_m` metres, `_deg_min` degrees per minute); each `inputs` entry is a file name relative to the `config.yaml` directory; `origin` holds degrees and metres. Do not put `gyr_psd`, `lim_pos_rms_m`, or `enable` at the top level.

When the run finishes, the report on standard output states the navigation suite's final solution mode on one line of the form `final nav_suite mode: NAME`, NAME being one of `FULL`, `COASTING`, `ATTITUDE_ONLY`, `NONE`.

The climb/descent estimator path uses `imu.csv`, `baro.csv`, `gnss.csv`, `ref.csv`, and `config.yaml`. The GNSS delay field in `config.yaml` stays 0. The lag lives in GNSS vertical velocity versus barometric vertical velocity, not in that config delay field.

Forcing the estimator on a climb or descent that has IMU, barometer, and usable GNSS vertical velocity prints a numeric lag rather than silence, on its own line that starts with `gnss delay estimate:` (letter case aside) followed by the lag as a number of milliseconds and `ms`. The rest of that line and of the report is not pinned.

The C dataset-replay program is a separate argv: `replay <dataset>` with an optional second dump path. That dump row shape belongs with that program, not with `--dump-solution`. The second path receives a per-epoch error dump: lines that begin with `#` are comments; each data row has nine comma-separated fields — seconds since the first GNSS fix (the first reference sample when aiding is not `gnss`), reference ground speed in m/s, INS roll, pitch, and yaw error against `ref.csv` in degrees, INS position error in metres, then ARS roll, pitch, and yaw error in degrees. A row is written at each reference epoch where INS is ready or, with `score.ahrs: 1`, the suite's ARS attitude is published; the fields of the filter that is not published at that epoch are 0. A run refused before replay, such as one with an unknown aiding value, writes no data row.
