# feature: F09
"""F09 observation helpers: codecs, GIF timing, companion audio, write refusals."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from _harness import HarnessError
from _helpers import _encoder_exe, _media_probe_streams, as_numeric_array, failure_remainder

_AUDIO_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mka",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}

_PIX_TOKEN = re.compile(
    r"\b(yuva?\d+\w*|rgb\w*|bgr\w*|nv\d+|gray\w*|pal8|gbrp\w*)\b",
    re.IGNORECASE,
)


def _first_stream(path: str | Path, kind: str) -> dict[str, Any]:
    streams = _media_probe_streams(path)
    for stream in streams:
        if stream.get("codec_type") == kind:
            return stream
    raise HarnessError(f"container has no {kind} stream: {path}")


def _codec_token(stream: dict[str, Any], *, kind: str, path: str | Path) -> str:
    name = stream.get("codec_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    detail = stream.get("detail")
    if isinstance(detail, str) and detail.strip():
        token = detail.strip().split(",", 1)[0].split()[0].strip()
        if token:
            return token
    raise HarnessError(
        f"{kind} stream has no usable codec name; stream={stream!r} path={path}"
    )


def ffmpeg_opens_nonempty_media(path: str | Path) -> bool:
    """Whether *path* is a nonempty file FFmpeg can open as media.

    Missing, empty, or a file FFmpeg cannot identify as media is False.
    ``stat`` failure, or a probe that cannot run at all, raises. A probe
    that runs and does not list streams is "cannot open", not a crash.
    """
    src = Path(path)
    try:
        if not src.exists():
            return False
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
        size = src.stat().st_size
    except FileNotFoundError:
        return False
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat {src}: {exc}") from exc
    if size <= 0:
        return False
    _encoder_exe()
    try:
        streams = _media_probe_streams(src)
    except FileNotFoundError:
        return False
    except HarnessError:
        return False
    return bool(streams)


def container_video_codec(path: str | Path) -> str:
    """Independently read the video stream's encoder family token.

    No video stream, or a probe that cannot name the codec, raises.
    Never returns an empty string to mean 'unknown'.
    """
    stream = _first_stream(path, "video")
    return _codec_token(stream, kind="video", path=path)


def container_audio_codec(path: str | Path) -> str:
    """Independently read the audio stream's encoder family token.

    No audio stream, or a probe that cannot name the codec, raises.
    Never returns an empty string to mean 'unknown'.
    """
    stream = _first_stream(path, "audio")
    return _codec_token(stream, kind="audio", path=path)


def container_pixel_format(path: str | Path) -> str:
    """Independently read the video stream's pixel format.

    Probe crash or a missing format raises. Never returns '' as absence.
    """
    stream = _first_stream(path, "video")
    pix = stream.get("pix_fmt")
    if isinstance(pix, str) and pix.strip():
        return pix.strip()
    detail = stream.get("detail")
    if isinstance(detail, str):
        match = _PIX_TOKEN.search(detail)
        if match is not None:
            return match.group(1)
    raise HarnessError(
        f"video stream has no usable pixel format; stream={stream!r} path={path}"
    )


def _open_still_image(path: str | Path, *, load: bool = True):
    src = Path(path)
    try:
        if not src.exists():
            raise FileNotFoundError(f"image file does not exist: {src}")
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
    except FileNotFoundError:
        raise
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat image {src}: {exc}") from exc
    try:
        from PIL import Image
    except ImportError as exc:
        raise HarnessError(f"Pillow is required to read still images: {exc}") from exc
    try:
        image = Image.open(src)
        if load:
            image.load()
    except Exception as exc:
        raise HarnessError(f"cannot decode image {src}: {exc}") from exc
    return image


def _iter_gif_pil_frames(path: str | Path):
    image = _open_still_image(path, load=False)
    try:
        from PIL import ImageSequence
    except ImportError as exc:
        raise HarnessError(f"Pillow ImageSequence is required: {exc}") from exc
    try:
        frames = []
        for frame in ImageSequence.Iterator(image):
            frames.append(frame.copy())
    except Exception as exc:
        raise HarnessError(f"cannot iterate GIF frames in {path}: {exc}") from exc
    if not frames:
        raise AssertionError(f"nonempty GIF listed no frames: {path}")
    return frames


def gif_frame_delays(path: str | Path) -> list[float]:
    """GIF per-frame delays in seconds, via a still-image library.

    Open/decode failure raises. A nonempty file that yields no frames
    is an assertion failure, never an empty list standing in for an
    empty animation. Pillow reports GIF duration in milliseconds.
    """
    delays: list[float] = []
    last = 0.0
    for index, frame in enumerate(_iter_gif_pil_frames(path)):
        raw = frame.info.get("duration")
        if isinstance(raw, (list, tuple)):
            if index < len(raw):
                raw = raw[index]
            elif raw:
                raw = raw[-1]
            else:
                raw = None
        if raw is None:
            delay = last
        else:
            try:
                delay = float(raw) / 1000.0
            except (TypeError, ValueError) as exc:
                raise HarnessError(
                    f"GIF frame {index} delay is not numeric: {raw!r} path={path}"
                ) from exc
            if delay != delay:
                raise HarnessError(
                    f"GIF frame {index} delay is NaN; path={path}"
                )
        delays.append(delay)
        last = delay
    return delays


def gif_playback_seconds(path: str | Path) -> float:
    """Sum of GIF frame delays in seconds."""
    return float(sum(gif_frame_delays(path)))


def gif_loop_count(path: str | Path) -> Any:
    """Loop count stored in the GIF, or the still-library's unset value.

    Decode failure raises. A missing field is the library's absence
    value, never an I/O failure mapped to 0.
    """
    frames = _iter_gif_pil_frames(path)
    for frame in frames:
        if "loop" in frame.info:
            return frame.info["loop"]
    image = _open_still_image(path, load=False)
    return image.info.get("loop")


def gif_frames_rgba(path: str | Path) -> list[np.ndarray]:
    """RGBA pictures of every GIF frame. Decode failure raises."""
    frames: list[np.ndarray] = []
    for index, frame in enumerate(_iter_gif_pil_frames(path)):
        try:
            converted = frame.convert("RGBA")
        except Exception as exc:
            raise HarnessError(
                f"cannot convert GIF frame {index} in {path}: {exc}"
            ) from exc
        arr = as_numeric_array(np.asarray(converted))
        frames.append(np.ascontiguousarray(arr))
    return frames


def failure_identifies_codec_must_be_supplied(result, *covariates: Any) -> str:
    """Require that a caller-visible failure names codec as needing supply.

    Covariates are stripped first. Does not pin an exception class or a
    canned sentence. After stripping, the remainder must still name
    codec (or encoder) as the quantity to provide. An empty remainder
    means the failure carried only the stripped tokens.
    """
    rest = failure_remainder(result, *covariates)
    if not rest.strip():
        raise AssertionError(
            "caller-visible failure carried only stripped covariates; "
            "it does not identify that a codec must be supplied"
        )
    folded = rest.casefold()
    named = "codec" in folded or "encoder" in folded
    if not named:
        raise AssertionError(
            "caller-visible failure does not identify that a codec must "
            f"be supplied; remainder={rest!r}"
        )
    return rest


def failure_identifies_encoder_rejected_codec(result, *covariates: Any) -> str:
    """Require that a caller-visible failure names an encoder codec rejection.

    Covariates are stripped first. Empty remainder after stripping is a
    failure: the report carried only those tokens. Does not pin wording.
    """
    rest = failure_remainder(result, *covariates)
    if not rest.strip():
        raise AssertionError(
            "caller-visible failure carried only stripped covariates; "
            "it does not identify that the encoder rejected the codec"
        )
    folded = rest.casefold()
    named = "codec" in folded or "encoder" in folded or "ffmpeg" in folded
    if not named:
        raise AssertionError(
            "caller-visible failure does not identify that the encoder "
            f"rejected the codec; remainder={rest!r}"
        )
    return rest


def sibling_audio_paths(video_path: str | Path) -> list[Path]:
    """Audio files in the write directory other than the named video path.

    ``stat`` / listing failure raises. The named video itself is omitted.
    """
    video = Path(video_path)
    try:
        video = video.resolve()
    except OSError as exc:
        raise HarnessError(f"cannot resolve video path {video_path}: {exc}") from exc
    parent = video.parent
    try:
        entries = list(parent.iterdir())
    except OSError as exc:
        raise HarnessError(f"cannot list write directory {parent}: {exc}") from exc
    found: list[Path] = []
    for entry in entries:
        try:
            if not entry.is_file():
                continue
            resolved = entry.resolve()
        except OSError as exc:
            raise HarnessError(f"cannot stat {entry}: {exc}") from exc
        if resolved == video:
            continue
        if entry.suffix.lower() in _AUDIO_SUFFIXES:
            found.append(entry)
    return found
