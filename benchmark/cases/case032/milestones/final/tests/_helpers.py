"""Pipeline-owned sealed test helpers.

This file is the complete module. Import what you need (`from _helpers import ...`).
Add a new helper here, with the imports and constants it closes over. Do not paste
a sealed body into a feature file. Do not change a sealed name unless you own it
and that feature's PRD was amended.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import wave
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from _harness import CallResult, HarnessError, find_executable, run_command

_PCM_RATE = 44100


def _stderr_snippet(result: CallResult) -> str:
    try:
        return result.stderr_text
    except HarnessError:
        raise


def require_ok(result: CallResult) -> Any:
    """Return the value of a successful library call.

    A product exception is a hard failure. A timeout or other harness
    failure is already a ``HarnessError`` and is not mapped to a value.
    """
    if not isinstance(result, CallResult):
        raise HarnessError(f"require_ok expects a CallResult; got {type(result)!r}")
    if result.exception is not None:
        stderr = _stderr_snippet(result)
        raise AssertionError(
            "library call did not succeed: "
            f"{type(result.exception).__name__}: {result.exception}; "
            f"stderr={stderr!r}"
        )
    return result.value


def require_failed(result: CallResult) -> BaseException:
    """Return the product exception from a call that did not succeed.

    A harness failure is not a product refusal. Success (no exception) is
    a hard assertion failure, not an absent sentinel.
    """
    if not isinstance(result, CallResult):
        raise HarnessError(
            f"require_failed expects a CallResult; got {type(result)!r}"
        )
    if result.exception is None:
        raise AssertionError(
            "library call succeeded; expected the entry itself not to succeed; "
            f"value={result.value!r}"
        )
    return result.exception


def failure_remainder(result: CallResult, *covariates: Any) -> str:
    """Caller-visible product-failure text with covariates stripped.

    A missing product exception is an assertion failure. Stream-decode
    errors raise. An empty remainder after stripping is a real
    observation: the failure carried only the stripped tokens.
    """
    if not isinstance(result, CallResult):
        raise HarnessError(
            f"failure_remainder expects a CallResult; got {type(result)!r}"
        )
    if result.exception is None:
        raise AssertionError(
            "no product failure from which to read a caller-visible remainder; "
            f"value={result.value!r}"
        )
    try:
        stderr = result.stderr_text
        stdout = result.stdout_text
    except HarnessError:
        raise
    text = " ".join(part for part in (str(result.exception), stderr, stdout) if part)
    tokens: list[str] = []
    if result.cwd:
        tokens.append(result.cwd)
    for raw in covariates:
        if raw is None:
            continue
        if isinstance(raw, Path):
            tokens.append(str(raw))
            tokens.append(raw.name)
        else:
            tokens.append(str(raw))
    for token in tokens:
        if not token:
            continue
        text = text.replace(token, "")
        alt = token.replace("\\", "/")
        if alt != token:
            text = text.replace(alt, "")
    return text


def failure_identifies_missing_duration(result: CallResult, *covariates: Any) -> str:
    """Require that a caller-visible failure names duration as missing.

    Covariates (paths, sizes, colors) are stripped first so identification
    cannot ride on those tokens. Does not pin an exception class or a
    canned sentence: surrounding wording is free. After stripping, the
    remainder must still name duration as the missing quantity. An empty
    remainder means the failure carried only the stripped tokens.
    """
    rest = failure_remainder(result, *covariates)
    if not rest.strip():
        raise AssertionError(
            "caller-visible failure carried only stripped covariates; "
            "it does not identify that duration is missing"
        )
    if "duration" not in rest.casefold():
        raise AssertionError(
            "caller-visible failure does not identify duration as the "
            f"missing quantity; remainder={rest!r}"
        )
    return rest


def failure_identifies_missing_frame_rate(result: CallResult, *covariates: Any) -> str:
    """Require that a caller-visible failure names frame rate as missing.

    Covariates (paths, sizes, colors) are stripped first so identification
    cannot ride on those tokens. Does not pin an exception class or a
    canned sentence: surrounding wording is free. After stripping, the
    remainder must still name frame rate as the missing quantity (any
    wording that identifies that quantity, such as frame rate or fps).
    An empty remainder means the failure carried only the stripped tokens.
    """
    rest = failure_remainder(result, *covariates)
    if not rest.strip():
        raise AssertionError(
            "caller-visible failure carried only stripped covariates; "
            "it does not identify that frame rate is missing"
        )
    folded = rest.casefold()
    named = (
        "frame rate" in folded
        or "framerate" in folded
        or "frames per second" in folded
        or "fps" in folded
    )
    if not named:
        raise AssertionError(
            "caller-visible failure does not identify frame rate as the "
            f"missing quantity; remainder={rest!r}"
        )
    return rest


def as_numeric_array(frame: Any) -> np.ndarray:
    """Coerce a frame to a numeric array. Illegal input raises."""
    if frame is None:
        raise AssertionError("frame is None; no numeric array was produced")
    try:
        arr = np.asarray(frame)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"frame is not a numeric array: {exc}") from exc
    if arr.dtype.kind not in "biufc":
        raise AssertionError(
            f"frame is not numeric; dtype={arr.dtype!r} shape={arr.shape!r}"
        )
    return arr


def require_rgb_picture(
    frame: Any,
    height: int,
    width: int,
    color: tuple[int, int, int] | None = None,
) -> np.ndarray:
    """Require a height×width×3 picture with integer channels in 0–255."""
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[0] != height or arr.shape[1] != width or arr.shape[2] != 3:
        raise AssertionError(
            f"expected RGB picture shape {(height, width, 3)}; got {arr.shape}"
        )
    if np.any(arr < 0) or np.any(arr > 255):
        raise AssertionError(
            f"RGB channels are not in 0–255; min={arr.min()!r} max={arr.max()!r}"
        )
    if not np.allclose(arr, np.round(arr), atol=1e-6, rtol=0):
        raise AssertionError("RGB channels are not integer-valued")
    if color is not None:
        expected = np.asarray(color, dtype=float).reshape(1, 1, 3)
        if not np.allclose(arr.astype(float), expected, atol=0.5, rtol=0):
            got = tuple(int(round(v)) for v in arr.reshape(-1, 3)[0])
            raise AssertionError(
                f"pixels do not match requested RGB {color}; sample={got}"
            )
    return arr


def require_mask_picture(frame: Any, height: int, width: int) -> np.ndarray:
    """Require a height×width greyscale picture with values in 0–1."""
    arr = as_numeric_array(frame)
    if arr.ndim != 2 or arr.shape[0] != height or arr.shape[1] != width:
        raise AssertionError(
            f"expected mask picture shape {(height, width)}; got {arr.shape}"
        )
    if np.any(arr < 0) or np.any(arr > 1):
        raise AssertionError(
            f"mask values are not in 0–1; min={arr.min()!r} max={arr.max()!r}"
        )
    return arr


def require_sound_frame(frame: Any, channels: int) -> np.ndarray:
    """Require a mono (length 1) or stereo (length 2) floating-point sample."""
    if channels not in (1, 2):
        raise HarnessError(f"channels must be 1 or 2; got {channels!r}")
    arr = as_numeric_array(frame)
    if arr.dtype.kind not in "fc":
        raise AssertionError(
            f"sound samples are not floating-point; dtype={arr.dtype!r}"
        )
    flat = np.atleast_1d(arr.astype(float)).reshape(-1)
    if flat.size != channels:
        raise AssertionError(
            f"expected {channels} floating-point sample(s); got shape {arr.shape}"
        )
    return flat


def pictures_equal(a: Any, b: Any) -> bool:
    """Whether two already-fetched pictures match exactly."""
    aa = as_numeric_array(a)
    bb = as_numeric_array(b)
    if aa.shape != bb.shape:
        return False
    return bool(np.array_equal(aa, bb))


def samples_close(a: Any, b: Any) -> bool:
    """Whether two already-fetched sound frames match within numeric tolerance."""
    aa = as_numeric_array(a).astype(float).reshape(-1)
    bb = as_numeric_array(b).astype(float).reshape(-1)
    if aa.shape != bb.shape:
        return False
    return bool(np.allclose(aa, bb, rtol=1e-5, atol=1e-6))


def pcm_close_lossy(a: Any, b: Any, *, atol: float = 3e-3, rtol: float = 1e-3) -> bool:
    """Whether two PCM arrays match within ordinary encode/decode tolerance.

    Compares the overlapping prefix. Illegal input raises. An empty
    overlap is not a match.
    """
    aa = as_numeric_array(a).astype(float)
    bb = as_numeric_array(b).astype(float)
    if aa.size == 0 or bb.size == 0:
        raise AssertionError("PCM array is empty; cannot compare encode/decode")
    if aa.ndim == 1:
        aa = aa.reshape(-1, 1)
    if bb.ndim == 1:
        bb = bb.reshape(-1, 1)
    if aa.ndim != 2 or bb.ndim != 2:
        raise AssertionError(
            f"PCM arrays must be N×C; got shapes {aa.shape} and {bb.shape}"
        )
    channels = min(aa.shape[1], bb.shape[1])
    n = min(aa.shape[0], bb.shape[0])
    if n < 32 or channels < 1:
        raise AssertionError(
            f"PCM overlap too short to compare; n={n} channels={channels}"
        )
    return bool(
        np.allclose(aa[:n, :channels], bb[:n, :channels], rtol=rtol, atol=atol)
    )


def pcm_same_signal(a: Any, b: Any, *, min_corr: float = 0.85) -> bool:
    """Whether two PCM arrays carry the same waveform (allowing a small lag).

    File decode may prime a few samples. Illegal input raises.
    """
    aa = as_numeric_array(a).astype(float)
    bb = as_numeric_array(b).astype(float)
    if aa.size == 0 or bb.size == 0:
        raise AssertionError("PCM array is empty; cannot compare signals")
    if aa.ndim == 1:
        aa = aa.reshape(-1, 1)
    if bb.ndim == 1:
        bb = bb.reshape(-1, 1)
    n = min(aa.shape[0], bb.shape[0])
    if n < 32:
        raise AssertionError(f"PCM overlap too short to compare; n={n}")
    left_a = aa[:n, 0] - aa[:n, 0].mean()
    left_b = bb[:n, 0] - bb[:n, 0].mean()
    denom = float(np.linalg.norm(left_a) * np.linalg.norm(left_b))
    if denom == 0.0:
        return False
    corr0 = float(np.dot(left_a, left_b) / denom)
    best = corr0
    max_lag = min(256, n // 8)
    for lag in range(1, max_lag + 1):
        da = left_a[lag:]
        db = left_b[: da.size]
        d = float(np.linalg.norm(da) * np.linalg.norm(db))
        if d == 0.0:
            continue
        best = max(best, float(np.dot(da, db) / d))
        da = left_a[: n - lag]
        db = left_b[lag:]
        d = float(np.linalg.norm(da) * np.linalg.norm(db))
        if d == 0.0:
            continue
        best = max(best, float(np.dot(da, db) / d))
    print(f"pcm_same_signal corr0={corr0:.4f} best={best:.4f} n={n}", flush=True)
    return best >= min_corr


def media_file_nonempty(path: str | Path) -> int:
    """Return the size of a regular nonempty file.

    Missing paths raise ``FileNotFoundError``, never size 0. An existing
    empty file is an assertion failure, not a stand-in for absence.
    """
    src = Path(path)
    try:
        if not src.exists():
            raise FileNotFoundError(f"media file does not exist: {src}")
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
        size = src.stat().st_size
    except FileNotFoundError:
        raise
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat media file {src}: {exc}") from exc
    if size <= 0:
        raise AssertionError(f"media file is empty: {src}")
    return size


def _encoder_exe() -> Path:
    """Locate an invocable media encoder (PATH, then the bundled binary)."""
    found = find_executable("ffmpeg")
    if found is not None:
        return found
    errors: list[str] = ["ffmpeg is not on PATH"]
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except ImportError as exc:
        errors.append(f"imageio_ffmpeg missing: {exc}")
    else:
        try:
            exe = get_ffmpeg_exe()
        except Exception as exc:
            errors.append(f"imageio_ffmpeg.get_ffmpeg_exe failed: {exc}")
        else:
            path = Path(exe)
            if path.is_file():
                return path
            errors.append(f"bundled encoder path is not a file: {exe!r}")
    raise HarnessError("; ".join(errors))


def _ffprobe_exe() -> Path | None:
    found = find_executable("ffprobe")
    if found is not None:
        return found
    sibling = _encoder_exe().parent / "ffprobe"
    try:
        if sibling.is_file():
            return sibling
    except OSError as exc:
        raise HarnessError(f"cannot stat bundled ffprobe {sibling}: {exc}") from exc
    return None


def _require_regular_media(path: str | Path) -> Path:
    src = Path(path)
    try:
        if not src.exists():
            raise FileNotFoundError(f"media file does not exist: {src}")
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
    except FileNotFoundError:
        raise
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat media file {src}: {exc}") from exc
    return src


def _streams_from_ffmpeg_identify(src: Path) -> list[dict[str, Any]]:
    encoder = _encoder_exe()
    result = run_command(
        [
            str(encoder),
            "-hide_banner",
            "-nostdin",
            "-i",
            str(src),
            "-f",
            "null",
            "-",
        ],
        timeout=30.0,
    )
    text = result.stderr_text
    streams: list[dict[str, Any]] = []
    for match in re.finditer(
        r"Stream #\d+:\d+[^:]*: (Video|Audio): ([^\n]+)",
        text,
    ):
        kind = match.group(1).lower()
        detail = match.group(2)
        stream: dict[str, Any] = {"codec_type": kind, "detail": detail}
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", detail)
        if fps_match is None:
            fps_match = re.search(r"(\d+(?:\.\d+)?)\s*tbr", detail)
        if fps_match is not None:
            stream["r_frame_rate"] = fps_match.group(1)
        streams.append(stream)
    if not streams:
        raise HarnessError(
            "media identify listed no streams: "
            f"rc={result.returncode} stderr={text!r}"
        )
    return streams


def _media_probe_streams(path: str | Path) -> list[dict[str, Any]]:
    src = _require_regular_media(path)
    probe = _ffprobe_exe()
    if probe is None:
        return _streams_from_ffmpeg_identify(src)
    result = run_command(
        [
            str(probe),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            str(src),
        ],
        timeout=30.0,
    )
    if result.returncode != 0:
        raise HarnessError(
            "media probe failed: "
            f"rc={result.returncode} stderr={result.stderr_text!r}"
        )
    try:
        payload = json.loads(result.stdout_text or "{}")
    except json.JSONDecodeError as exc:
        raise HarnessError(
            f"media probe JSON is not parseable: {exc}; "
            f"stdout={result.stdout_text!r}"
        ) from exc
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise HarnessError(f"media probe listed no streams: {payload!r}")
    return streams


def container_has_audio(path: str | Path) -> bool:
    """Whether a probed container reports an audio stream.

    Probe crashes raise. Only a successful probe that lists no audio
    stream returns false.
    """
    streams = _media_probe_streams(path)
    return any(stream.get("codec_type") == "audio" for stream in streams)


def _parse_frame_rate(raw: Any) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text in {"0/0", "N/A", "nan"}:
        return None
    try:
        if "/" in text:
            num_s, den_s = text.split("/", 1)
            den = float(den_s)
            if den == 0:
                return None
            return float(num_s) / den
        return float(text)
    except (TypeError, ValueError):
        return None


def container_frame_rate(path: str | Path) -> float:
    """Independently read the written video stream's frame rate.

    Probe crash or a container with no video stream raises; never returns
    0 to mean failure.
    """
    streams = _media_probe_streams(path)
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        for key in ("avg_frame_rate", "r_frame_rate"):
            rate = _parse_frame_rate(stream.get(key))
            if rate is not None and rate > 0:
                return rate
        raise HarnessError(
            f"video stream has no usable frame rate; stream={stream!r}"
        )
    raise HarnessError(f"container has no video stream: {path}")


def container_playback_frame_rate(path: str | Path) -> float:
    """Independently read a video stream's ordinary playback frame rate.

    When a container reports both a time-base rate and a playback rate,
    prefers a value in the ordinary playback range. Probe crash or a
    container with no video stream raises; never returns 0 to mean failure.
    """
    streams = _media_probe_streams(path)
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        rates: list[float] = []
        for key in ("avg_frame_rate", "r_frame_rate"):
            rate = _parse_frame_rate(stream.get(key))
            if rate is not None and rate > 0:
                rates.append(rate)
        plausible = [rate for rate in rates if 0.5 <= rate <= 60.0]
        if plausible:
            return plausible[0]
        if rates:
            return rates[0]
        detail = stream.get("detail")
        if isinstance(detail, str):
            fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", detail)
            if fps_match is None:
                fps_match = re.search(r"(\d+(?:\.\d+)?)\s*tbr", detail)
            if fps_match is not None:
                rate = _parse_frame_rate(fps_match.group(1))
                if rate is not None and rate > 0:
                    return rate
        raise HarnessError(
            f"video stream has no usable frame rate; stream={stream!r}"
        )
    raise HarnessError(f"container has no video stream: {path}")


def pcm_from_container(path: str | Path) -> np.ndarray:
    """Decode mono PCM from a container via the environment encoder.

    Failure raises. Does not return an empty array to mean 'no audio'.
    Samples are float64 in the encoder's native scaling after s16le decode.
    The extract always resamples to 44100 Hz mono.
    """
    src = _require_regular_media(path)

    encoder = _encoder_exe()
    result = run_command(
        [
            str(encoder),
            "-hide_banner",
            "-nostats",
            "-nostdin",
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(_PCM_RATE),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "pipe:1",
        ],
        timeout=30.0,
    )
    if result.returncode != 0:
        raise HarnessError(
            "PCM extract failed: "
            f"rc={result.returncode} stderr={result.stderr_text!r}"
        )
    raw = result.stdout or b""
    if len(raw) < 4:
        raise HarnessError(
            f"PCM extract produced no samples ({len(raw)} bytes); "
            f"stderr={result.stderr_text!r}"
        )
    if len(raw) % 2:
        raw = raw[:-1]
    return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0


def dominant_tone_hz(pcm: Any, sample_rate: float) -> float:
    """Independent peak-frequency estimate. Not a product transform."""
    arr = as_numeric_array(pcm).astype(float).reshape(-1)
    if arr.size < 32:
        raise AssertionError(f"not enough PCM samples to estimate a tone ({arr.size})")
    if sample_rate <= 0:
        raise HarnessError(f"sample_rate must be positive; got {sample_rate!r}")
    windowed = arr * np.hanning(arr.size)
    spec = np.fft.rfft(windowed)
    mag = np.abs(spec)
    mag[0] = 0.0
    peak = int(np.argmax(mag))
    freqs = np.fft.rfftfreq(arr.size, d=1.0 / float(sample_rate))
    return float(freqs[peak])


def find_opentype_fonts(count: int) -> list[Path]:
    """Locate *count* readable OpenType files with distinct contents.

    Searches ordinary environment font directories. Raises
    ``HarnessError`` listing searched paths when fewer than *count*
    distinct files exist. Never returns an empty list or ``None``.
    """
    if count < 1:
        raise HarnessError(f"count must be at least 1; got {count!r}")

    home = os.environ.get("HOME") or ""
    search_roots = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path("/usr/share/fonts/truetype"),
        Path("/usr/share/fonts/opentype"),
        Path("/usr/share/fonts/TTF"),
        Path("/usr/X11R6/lib/X11/fonts"),
    ]
    if home:
        search_roots.extend(
            [Path(home) / ".fonts", Path(home) / ".local/share/fonts"]
        )

    suffixes = {".ttf", ".otf", ".TTF", ".OTF"}
    found: list[Path] = []
    seen_digests: set[str] = set()
    searched: list[str] = []

    for root in search_roots:
        try:
            present = root.is_dir()
        except OSError as exc:
            raise HarnessError(f"cannot stat font directory {root}: {exc}") from exc
        if not present:
            searched.append(f"{root} (absent)")
            continue
        searched.append(str(root))
        try:
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    if Path(name).suffix not in suffixes:
                        continue
                    path = Path(dirpath) / name
                    try:
                        data = path.read_bytes()
                    except OSError:
                        continue
                    if not data:
                        continue
                    digest = hashlib.sha256(data).hexdigest()
                    if digest in seen_digests:
                        continue
                    seen_digests.add(digest)
                    found.append(path)
                    if len(found) >= count:
                        return found
        except OSError as exc:
            raise HarnessError(f"cannot walk font directory {root}: {exc}") from exc

    raise HarnessError(
        f"need {count} OpenType font file(s) with distinct contents; "
        f"found {len(found)}; searched: {searched}"
    )


def _parse_clock_duration(raw: Any) -> float | None:
    """Parse a duration given as seconds or an HH:MM:SS clock string."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        if value <= 0 or value != value:
            return None
        return value
    text = str(raw).strip()
    if not text or text in {"N/A", "n/a", "nan"}:
        return None
    try:
        if ":" in text:
            parts = text.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = parts
                value = float(hours) * 3600.0 + float(minutes) * 60.0 + float(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                value = float(minutes) * 60.0 + float(seconds)
            else:
                return None
        else:
            value = float(text)
    except (TypeError, ValueError):
        return None
    if value <= 0 or value != value:
        return None
    return value


def _duration_from_mapping(payload: dict[str, Any]) -> float | None:
    parsed = _parse_clock_duration(payload.get("duration"))
    if parsed is not None:
        return parsed
    tags = payload.get("tags")
    if isinstance(tags, dict):
        for key in ("DURATION", "duration"):
            parsed = _parse_clock_duration(tags.get(key))
            if parsed is not None:
                return parsed
    duration_ts = payload.get("duration_ts")
    time_base = payload.get("time_base")
    if duration_ts is None or time_base is None:
        return None
    try:
        num_s, den_s = str(time_base).split("/", 1)
        den = float(den_s)
        if den == 0:
            return None
        value = float(duration_ts) * float(num_s) / den
    except (TypeError, ValueError):
        return None
    if value <= 0 or value != value:
        return None
    return value


def _media_probe_format(path: str | Path) -> dict[str, Any]:
    """Return ffprobe-style format+streams, or raise."""
    src = _require_regular_media(path)
    probe = _ffprobe_exe()
    if probe is not None:
        result = run_command(
            [
                str(probe),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-show_format",
                str(src),
            ],
            timeout=30.0,
        )
        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout_text or "{}")
            except HarnessError:
                raise
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                return payload
    encoder = _encoder_exe()
    result = run_command(
        [
            str(encoder),
            "-hide_banner",
            "-nostdin",
            "-i",
            str(src),
            "-f",
            "null",
            "-",
        ],
        timeout=30.0,
    )
    text = result.stderr_text
    streams: list[dict[str, Any]] = []
    for match in re.finditer(
        r"Stream #\d+:\d+[^:]*: (Video|Audio): ([^\n]+)",
        text,
    ):
        kind = match.group(1).lower()
        detail = match.group(2)
        stream: dict[str, Any] = {"codec_type": kind, "detail": detail}
        fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", detail)
        if fps_match is None:
            fps_match = re.search(r"(\d+(?:\.\d+)?)\s*tbr", detail)
        if fps_match is not None:
            stream["r_frame_rate"] = fps_match.group(1)
        size_match = re.search(r"(\d+)x(\d+)", detail)
        if size_match is not None:
            stream["width"] = int(size_match.group(1))
            stream["height"] = int(size_match.group(2))
        streams.append(stream)
    duration = None
    dur_match = re.search(r"Duration:\s*([0-9:.]+)", text)
    if dur_match is not None:
        duration = _parse_clock_duration(dur_match.group(1))
    if not streams:
        raise HarnessError(
            "media identify listed no streams: "
            f"rc={result.returncode} stderr={text!r}"
        )
    fmt: dict[str, Any] = {}
    if duration is not None:
        fmt["duration"] = duration
    return {"streams": streams, "format": fmt}


def container_duration(path: str | Path) -> float:
    """Independently read the video-stream (else container) duration.

    Probe crash or an unreadable duration raises; never returns 0 to
    mean failure.
    """
    payload = _media_probe_format(path)
    streams = payload.get("streams")
    if not isinstance(streams, list):
        streams = []
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        parsed = _duration_from_mapping(stream)
        if parsed is not None:
            return parsed
        frames = stream.get("nb_frames")
        rate = _parse_frame_rate(stream.get("r_frame_rate") or stream.get("avg_frame_rate"))
        try:
            n_frames = int(frames) if frames not in (None, "N/A", "") else 0
        except (TypeError, ValueError):
            n_frames = 0
        if n_frames > 0 and rate is not None and rate > 0:
            value = n_frames / rate
            if value > 0:
                return value
    counted = _video_duration_by_decode(path)
    if counted is not None:
        return counted
    fmt = payload.get("format")
    if isinstance(fmt, dict):
        parsed = _duration_from_mapping(fmt)
        if parsed is not None:
            return parsed
    raise HarnessError(f"container has no usable duration: {path}")


def _video_duration_by_decode(path: str | Path) -> float | None:
    """Duration of the first video stream from an identify pass."""
    src = _require_regular_media(path)
    encoder = _encoder_exe()
    result = run_command(
        [
            str(encoder),
            "-hide_banner",
            "-nostdin",
            "-i",
            str(src),
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
        ],
        timeout=30.0,
    )
    text = result.stderr_text
    match = re.search(r"time=\s*(\d+:\d+:\d+[.\d]*)", text)
    if match is not None:
        parsed = _parse_clock_duration(match.group(1))
        if parsed is not None:
            return parsed
    return None


def container_audio_duration(path: str | Path) -> float:
    """Independently read the audio-stream duration.

    No audio stream, or an unreadable audio duration, raises.
    Prefers a clock/seconds duration over a piped-header estimate:
    a WAV written to a pipe often has a sentinel size in the RIFF
    header, which is not a duration.
    """
    payload = _media_probe_format(path)
    streams = payload.get("streams")
    if not isinstance(streams, list):
        streams = []
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise HarnessError(f"container has no audio stream: {path}")
    for stream in audio_streams:
        parsed = _duration_from_mapping(stream)
        if parsed is not None:
            return parsed
    fmt = payload.get("format")
    if isinstance(fmt, dict):
        parsed = _duration_from_mapping(fmt)
        if parsed is not None:
            return parsed
    extracted = _audio_duration_by_extract(path)
    if extracted is not None:
        return extracted
    raise HarnessError(f"audio stream has no usable duration: {path}")


def _audio_duration_by_extract(path: str | Path) -> float | None:
    """Duration of the first audio stream via a real WAV file. None if empty.

    Writes a seekable file so the RIFF sizes are real. A pipe header is
    not used: muxers put 0xFFFFFFFF there when they cannot seek back.
    """
    src = _require_regular_media(path)
    encoder = _encoder_exe()
    tmp_path: str | None = None
    try:
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = handle.name
        handle.close()
        result = run_command(
            [
                str(encoder),
                "-y",
                "-hide_banner",
                "-nostats",
                "-nostdin",
                "-i",
                str(src),
                "-vn",
                "-f",
                "wav",
                tmp_path,
            ],
            timeout=30.0,
        )
        if result.returncode != 0:
            return None
        try:
            with wave.open(tmp_path, "rb") as wav:
                n_frames = wav.getnframes()
                rate = wav.getframerate()
        except wave.Error:
            return None
        except OSError as exc:
            raise HarnessError(
                f"cannot read extracted WAV {tmp_path}: {exc}"
            ) from exc
        if n_frames <= 0 or rate <= 0:
            return None
        value = n_frames / float(rate)
        if value <= 0:
            return None
        return value
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def container_video_size(path: str | Path) -> tuple[int, int]:
    """Independently read the video stream (width, height).

    No video stream, or missing dimensions, raises. Never returns (0, 0)
    to mean failure.
    """
    streams = _media_probe_streams(path)
    for stream in streams:
        if stream.get("codec_type") != "video":
            continue
        width = stream.get("width")
        height = stream.get("height")
        try:
            w = int(width) if width is not None else 0
            h = int(height) if height is not None else 0
        except (TypeError, ValueError):
            w, h = 0, 0
        if w > 0 and h > 0:
            return (w, h)
        detail = stream.get("detail")
        if isinstance(detail, str):
            size_match = re.search(r"(\d+)x(\d+)", detail)
            if size_match is not None:
                w = int(size_match.group(1))
                h = int(size_match.group(2))
                if w > 0 and h > 0:
                    return (w, h)
    raise HarnessError(f"video stream has no usable size: {path}")


def independent_rgb_frames(path: str | Path) -> list[np.ndarray]:
    """Decode every RGB frame with the environment encoder.

    Fixture observation, not a product transform. A container that
    yields no complete frame raises; never returns an empty list.
    """
    src = _require_regular_media(path)
    width, height = container_video_size(src)
    nbytes = width * height * 3
    encoder = _encoder_exe()
    result = run_command(
        [
            str(encoder),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(src),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        timeout=60.0,
    )
    if result.returncode != 0:
        raise HarnessError(
            "independent RGB decode failed: "
            f"rc={result.returncode} stderr={result.stderr_text!r}"
        )
    raw = result.stdout or b""
    if len(raw) < nbytes:
        raise HarnessError(
            "independent RGB decode produced no complete frame: "
            f"got {len(raw)} bytes, need {nbytes}; stderr={result.stderr_text!r}"
        )
    count = len(raw) // nbytes
    frames = [
        np.frombuffer(raw[index * nbytes : (index + 1) * nbytes], dtype=np.uint8)
        .reshape((height, width, 3))
        .copy()
        for index in range(count)
    ]
    return frames


def independent_video_frame(path: str | Path, t: float) -> np.ndarray:
    """Decode the RGB frame displayed at time t in the file.

    Indexes the independently decoded frame list. A time past the last
    decoded frame returns that last frame; it does not return a blank
    picture or raise as if the file were empty.
    """
    if t < 0:
        raise HarnessError(f"frame time must be >= 0; got {t!r}")
    frames = independent_rgb_frames(path)
    fps = container_playback_frame_rate(path)
    index = int(fps * t + 0.00001)
    if index < 0:
        raise HarnessError(f"negative frame index from t={t!r} fps={fps!r}")
    if index >= len(frames):
        index = len(frames) - 1
    return frames[index]


def pictures_close_lossy(
    a: Any,
    b: Any,
    *,
    mean_atol: float = 28.0,
    max_atol: float = 90.0,
) -> bool:
    """Whether two already-fetched pictures match within lossy tolerance.

    Illegal input raises.
    """
    aa = as_numeric_array(a).astype(float)
    bb = as_numeric_array(b).astype(float)
    if aa.shape != bb.shape:
        return False
    diff = np.abs(aa - bb)
    return bool(diff.mean() <= mean_atol and diff.max() <= max_atol)


def dominant_picture_rgb(frame: Any) -> tuple[int, int, int]:
    """Median RGB of an already-fetched picture. Illegal input raises."""
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[-1] < 3:
        raise AssertionError(
            f"expected a picture with at least 3 channels; got shape {arr.shape}"
        )
    rgb = arr[..., :3].reshape(-1, 3).astype(float)
    if rgb.size == 0:
        raise AssertionError("picture has no pixels")
    med = np.median(rgb, axis=0)
    return (int(round(med[0])), int(round(med[1])), int(round(med[2])))


def write_pcm_wav(path: str | Path, array: Any, sample_rate: float) -> Path:
    """Write PCM WAV from a mono (N×1 or N) or stereo (N×2) array.

    Failure raises. Refuses to write an empty file.
    """
    dest = Path(path)
    arr = as_numeric_array(array)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2 or arr.shape[1] not in (1, 2):
        raise HarnessError(
            f"WAV array must be N×1 or N×2; got shape {arr.shape}"
        )
    if arr.shape[0] < 1:
        raise HarnessError("refusing to write a WAV with no samples")
    if sample_rate <= 0:
        raise HarnessError(f"sample_rate must be positive; got {sample_rate!r}")
    pcm = np.clip(np.round(arr.astype(float) * 32767.0), -32768, 32767).astype("<i2")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as handle:
            handle.setnchannels(int(arr.shape[1]))
            handle.setsampwidth(2)
            handle.setframerate(int(sample_rate))
            handle.writeframes(pcm.tobytes())
    except OSError as exc:
        raise HarnessError(f"cannot write WAV {dest}: {exc}") from exc
    try:
        size = dest.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat written WAV {dest}: {exc}") from exc
    if size <= 0:
        raise AssertionError(f"WAV was written empty: {dest}")
    return dest


def _uint8_rgb_pictures(pictures: Sequence[Any]) -> list[np.ndarray]:
    if not pictures:
        raise HarnessError("need at least one picture to write a video fixture")
    frames: list[np.ndarray] = []
    expected: tuple[int, ...] | None = None
    for index, picture in enumerate(pictures):
        arr = as_numeric_array(picture)
        if arr.ndim != 3 or arr.shape[2] < 3:
            raise HarnessError(
                f"fixture picture {index} is not RGB; shape={arr.shape}"
            )
        rgb = np.round(arr[..., :3]).astype(np.uint8)
        if expected is None:
            expected = rgb.shape
        elif rgb.shape != expected:
            raise HarnessError(
                f"fixture picture {index} shape {rgb.shape} != {expected}"
            )
        frames.append(np.ascontiguousarray(rgb))
    return frames


def write_independent_video(
    path: str | Path,
    pictures: Sequence[Any],
    fps: float,
    *,
    ffmpeg_args: Sequence[str] | None = None,
    audio_pcm: Any = None,
    audio_sample_rate: float | None = None,
) -> Path:
    """Encode known pictures with the environment encoder.

    Extension selects the container. Extra encoder arguments are the
    caller's. Optional audio is muxed without shortening the longer
    stream. Failure raises; never leaves an empty file as success.
    """
    dest = Path(path)
    if fps <= 0:
        raise HarnessError(f"fps must be positive; got {fps!r}")
    frames = _uint8_rgb_pictures(pictures)
    height, width = frames[0].shape[0], frames[0].shape[1]
    encoder = _encoder_exe()
    dest.parent.mkdir(parents=True, exist_ok=True)
    video_dest = dest
    if audio_pcm is not None:
        video_dest = dest.with_name(dest.stem + ".video-only" + dest.suffix)
    raw_path = dest.with_name(dest.stem + ".rawvideo")
    raw = b"".join(frame.tobytes() for frame in frames)
    try:
        raw_path.write_bytes(raw)
    except OSError as exc:
        raise HarnessError(f"cannot write raw video fixture {raw_path}: {exc}") from exc
    cmd = [
        str(encoder),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        str(raw_path),
        "-frames:v",
        str(len(frames)),
        "-r",
        str(fps),
    ]
    if ffmpeg_args:
        cmd.extend(str(arg) for arg in ffmpeg_args)
    cmd.append(str(video_dest))
    result = run_command(cmd, timeout=60.0)
    if result.returncode != 0:
        raise HarnessError(
            "independent video write failed: "
            f"rc={result.returncode} stderr={result.stderr_text!r} argv={cmd!r}"
        )
    media_file_nonempty(video_dest)
    if audio_pcm is None:
        return dest
    if audio_sample_rate is None or audio_sample_rate <= 0:
        raise HarnessError(
            f"audio_sample_rate must be positive when audio_pcm is given; "
            f"got {audio_sample_rate!r}"
        )
    wav_path = dest.with_name(dest.stem + ".mux-audio.wav")
    write_pcm_wav(wav_path, audio_pcm, audio_sample_rate)
    mux = [
        str(encoder),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(video_dest),
        "-i",
        str(wav_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
    ]
    suffix = dest.suffix.lower()
    if suffix == ".mkv":
        mux.extend(["-c:a", "pcm_s16le"])
    else:
        mux.extend(["-c:a", "aac", "-b:a", "96k"])
    mux.append(str(dest))
    muxed = run_command(mux, timeout=60.0)
    if muxed.returncode != 0:
        raise HarnessError(
            "independent A/V mux failed: "
            f"rc={muxed.returncode} stderr={muxed.stderr_text!r}"
        )
    media_file_nonempty(dest)
    return dest


def write_independent_audio(
    path: str | Path,
    array: Any,
    sample_rate: float,
    *,
    ffmpeg_args: Sequence[str] | None = None,
) -> Path:
    """Write PCM, then optionally transcode with the environment encoder."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not ffmpeg_args and dest.suffix.lower() == ".wav":
        return write_pcm_wav(dest, array, sample_rate)
    wav_path = dest.with_name(dest.stem + ".source.wav")
    write_pcm_wav(wav_path, array, sample_rate)
    encoder = _encoder_exe()
    cmd = [
        str(encoder),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(wav_path),
    ]
    if ffmpeg_args:
        cmd.extend(str(arg) for arg in ffmpeg_args)
    cmd.append(str(dest))
    result = run_command(cmd, timeout=60.0)
    if result.returncode != 0:
        raise HarnessError(
            "independent audio write failed: "
            f"rc={result.returncode} stderr={result.stderr_text!r} argv={cmd!r}"
        )
    media_file_nonempty(dest)
    return dest

