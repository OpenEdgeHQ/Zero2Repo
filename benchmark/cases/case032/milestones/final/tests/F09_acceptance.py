# feature: F09
"""Encode clips to video, audio, GIF, and images (FP-09).

Assertions stay at the PRD's precision: finite clips with a frame rate
encode to openable files whose loaded duration, size, and frames match
the source (muxer/lossy tolerance); soundtrack on by default, off, or
replaced; codecs-by-extension including avi requiring a named codec;
GIF playback length at the frame rate and ordinary color frames; image
sequences from a name pattern; single-frame save including stills with
no duration; companion audio cleanup; missing duration/fps/codec and
unreachable-encoder refusals. Exception types, ffmpeg argv, lib names
in logs, GIF loop-field spelling, and three-digit padding are not pinned.
"""

from __future__ import annotations

import re
import secrets
import time
import warnings
from pathlib import Path

import numpy as np
import pytest
from clipkit import (
    AudioClip,
    AudioFileClip,
    ColorClip,
    VideoClip,
    VideoFileClip,
)

from _harness import HarnessError, workspace
from _helpers import (
    as_numeric_array,
    container_duration,
    container_frame_rate,
    container_has_audio,
    container_video_size,
    dominant_picture_rgb,
    dominant_tone_hz,
    failure_identifies_missing_duration,
    failure_identifies_missing_frame_rate,
    independent_rgb_frames,
    media_file_nonempty,
    pcm_close_lossy,
    pcm_from_container,
    pcm_same_signal,
    pictures_close_lossy,
    pictures_equal,
    require_failed,
    require_ok,
    require_rgb_picture,
    write_pcm_wav,
)
from F07_helpers import read_png_rgb_and_alpha
from F09_helpers import (
    container_audio_codec,
    container_pixel_format,
    container_video_codec,
    failure_identifies_codec_must_be_supplied,
    ffmpeg_opens_nonempty_media,
    gif_frames_rgba,
    gif_loop_count,
    gif_playback_seconds,
    sibling_audio_paths,
)

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

pytestmark = pytest.mark.filterwarnings(
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
)

_PCM_RATE = 44100
_MUXER_SLACK = 0.25
_ORACLE_SIZE = (16, 16)
_ORACLE_RED = (255, 0, 0)
_ORACLE_DURATION = 0.2
_ORACLE_FPS = 10
_PRESETS = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
    "placebo",
)
_VIDEO_CODEC_BY_EXT = (
    ("mp4", "h264"),
    ("mkv", "h264"),
    ("mov", "h264"),
    ("ogv", "theora"),
    ("webm", "vpx"),
)
_VIDEO_AUDIO_CODEC_BY_EXT = (
    ("mp4", "mp3"),
    ("mkv", "mp3"),
    ("mov", "mp3"),
    ("ogv", "vorbis"),
    ("webm", "vorbis"),
)
_AUDIO_CODEC_BY_EXT = (
    ("mp3", "mp3"),
    ("ogg", "vorbis"),
    ("wav", "pcm_s16le"),
    ("flac", "flac"),
)


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _rect_even_size() -> tuple[int, int]:
    width = _rand_int(10, 18) * 2
    height = _rand_int(8, 14) * 2
    if width == height:
        height = width + 2
    if (width, height) == _ORACLE_SIZE:
        height = height + 2
    return width, height


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(20, 230), _rand_int(20, 230), _rand_int(20, 230))


def _rgb_dist(a, b) -> int:
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b))


def _rgb_away_from(*others: tuple[int, int, int]) -> tuple[int, int, int]:
    banned = others + ((0, 0, 0), (255, 255, 255))
    for _ in range(32):
        candidate = _rgb()
        if all(_rgb_dist(candidate, other) > 90 for other in banned):
            return candidate
    return (255 - others[0][0], 255 - others[0][1], 255 - others[0][2])


def _tone_hz() -> float:
    return float(_rand_int(310, 720))


def _tone_mono(freq: float, duration: float, rate: int = _PCM_RATE) -> np.ndarray:
    n = int(round(duration * rate))
    if n < 32:
        raise HarnessError(f"tone array too short: n={n}")
    t = np.arange(n, dtype=float) / float(rate)
    return (0.5 * np.sin(2.0 * np.pi * freq * t)).reshape(n, 1)


def _assert_close(got, expected, *, slack, label):
    print(f"{label} got={got} expected={expected} slack={slack}", flush=True)
    try:
        value = float(got)
        target = float(expected)
    except (TypeError, ValueError) as exc:
        raise AssertionError(
            f"{label} is not numeric: got={got!r} expected={expected!r}: {exc}"
        ) from exc
    if abs(value - target) > slack:
        raise AssertionError(f"{label} {value} is not within {slack} of {target}")


def _codec_in_family(token: str, family: str) -> bool:
    name = token.casefold()
    if family == "h264":
        return "h264" in name or name in {"avc", "avc1", "libx264"}
    if family == "theora":
        return "theora" in name
    if family == "vpx":
        return any(part in name for part in ("vp8", "vp9", "vpx"))
    if family == "mpeg4":
        return "mpeg4" in name or name in {"mp4v", "xvid"}
    if family == "mp3":
        return "mp3" in name or "lame" in name
    if family == "vorbis":
        return "vorbis" in name
    if family == "pcm_s16le":
        return "pcm_s16" in name
    if family == "aac":
        return "aac" in name
    if family == "flac":
        return "flac" in name
    raise HarnessError(f"unknown codec family {family!r}")


def _assert_codec_family(token: str, family: str, *, label: str):
    print(f"{label} codec={token!r} family={family}", flush=True)
    if not _codec_in_family(token, family):
        raise AssertionError(
            f"{label} codec {token!r} is not in the {family} family"
        )


def _make_color(ws, size, color, duration=None, fps=None):
    clip = require_ok(ws.call(ColorClip, size, color=color))
    if duration is not None:
        clip = require_ok(ws.call(clip.with_duration, duration))
    if fps is not None:
        clip = require_ok(ws.call(clip.with_fps, fps))
    return clip


def _split_fn(height, width, first, second, split: float):
    first_a = np.asarray(first, dtype=np.uint8)
    second_a = np.asarray(second, dtype=np.uint8)

    def frame_function(t):
        picture = np.empty((height, width, 3), dtype=np.uint8)
        picture[:, :] = first_a if float(t) < split else second_a
        return picture

    return frame_function


def _split_clip(ws, width, height, first, second, duration, fps=None):
    fn = _split_fn(height, width, first, second, duration / 2.0)
    clip = require_ok(ws.call(VideoClip, frame_function=fn, duration=duration))
    if fps is not None:
        clip = require_ok(ws.call(clip.with_fps, fps))
    return clip


def _unique_frames_fn(height, width, salt: int):
    def frame_function(t):
        picture = np.empty((height, width, 3), dtype=np.uint8)
        phase = int(abs(float(t)) * 250.0) + salt
        picture[:, :, 0] = 40 + (phase * 3) % 180
        picture[:, :, 1] = 30 + (phase * 5) % 160
        picture[:, :, 2] = 50 + (phase * 7) % 170
        return picture

    return frame_function


def _unique_clip(ws, width, height, duration, fps, salt: int):
    clip = require_ok(
        ws.call(
            VideoClip,
            frame_function=_unique_frames_fn(height, width, salt),
            duration=duration,
        )
    )
    return require_ok(ws.call(clip.with_fps, fps))


def _pattern_fn(height, width, salt: int):
    def frame_function(t):
        tt = float(np.asarray(t).reshape(-1)[0])
        ys, xs = np.mgrid[0:height, 0:width]
        phase = (salt % 200) + int(tt * 50)
        picture = np.empty((height, width, 3), dtype=np.uint8)
        picture[:, :, 0] = (xs * 9 + ys * 3 + phase) % 200 + 30
        picture[:, :, 1] = (xs * 5 + ys * 11 + phase * 2) % 200 + 30
        picture[:, :, 2] = (xs * 2 + ys * 13 + salt) % 200 + 30
        return picture

    return frame_function


def _pattern_clip(ws, width, height, duration, fps, salt: int):
    clip = require_ok(
        ws.call(
            VideoClip,
            frame_function=_pattern_fn(height, width, salt),
            duration=duration,
        )
    )
    return require_ok(ws.call(clip.with_fps, fps))


def _tone_clip(ws, freq: float, duration: float, *, stereo: bool = False):
    if stereo:

        def frame_function(t):
            tt = np.asarray(t, dtype=float)
            left = 0.45 * np.sin(2.0 * np.pi * freq * tt)
            right = 0.35 * np.sin(2.0 * np.pi * freq * tt + 0.6)
            if tt.ndim == 0:
                return np.array([float(left), float(right)], dtype=float)
            return np.column_stack([left, right])

    else:

        def frame_function(t):
            tt = np.asarray(t, dtype=float)
            sig = 0.5 * np.sin(2.0 * np.pi * freq * tt)
            if tt.ndim == 0:
                return float(sig)
            return sig

    return require_ok(
        ws.call(AudioClip, frame_function=frame_function, duration=duration, fps=_PCM_RATE)
    )


def _with_tone(ws, clip, freq: float, duration: float):
    audio = _tone_clip(ws, freq, duration)
    return require_ok(ws.call(clip.with_audio, audio))


def _block_mask(height: int, width: int) -> np.ndarray:
    pattern = np.zeros((height, width), dtype=float)
    hy, hx = max(1, height // 2), max(1, width // 2)
    pattern[:hy, :hx] = 1.0
    pattern[hy:, hx:] = 1.0
    return pattern


def _mask_clip(ws, pattern: np.ndarray, duration: float):
    arr = np.asarray(pattern, dtype=float)

    def frame_function(t):
        return arr.copy()

    return require_ok(
        ws.call(VideoClip, frame_function=frame_function, duration=duration, is_mask=True)
    )


def _write_video(ws, clip, path: Path, **kwargs):
    kwargs.setdefault("logger", None)
    require_ok(ws.call(clip.write_videofile, str(path), **kwargs))
    media_file_nonempty(path)
    return path


def _write_audio(ws, clip, path: Path, **kwargs):
    kwargs.setdefault("logger", None)
    require_ok(ws.call(clip.write_audiofile, str(path), **kwargs))
    media_file_nonempty(path)
    return path


def _write_gif(ws, clip, path: Path, **kwargs):
    kwargs.setdefault("logger", None)
    require_ok(ws.call(clip.write_gif, str(path), **kwargs))
    media_file_nonempty(path)
    return path


def _write_sequence(ws, clip, pattern: str, **kwargs):
    kwargs.setdefault("logger", None)
    paths = require_ok(ws.call(clip.write_images_sequence, pattern, **kwargs))
    if paths is None:
        raise AssertionError("image-sequence write returned no path list")
    listed = [Path(item) for item in paths]
    if not listed:
        raise AssertionError("image-sequence write returned an empty path list")
    for item in listed:
        media_file_nonempty(item)
    return listed


def _save_frame(ws, clip, path: Path, **kwargs):
    require_ok(ws.call(clip.save_frame, str(path), **kwargs))
    media_file_nonempty(path)
    return path


def _load_video(ws, path: Path, **kwargs):
    return require_ok(ws.call(VideoFileClip, str(path), **kwargs))


def _load_audio(ws, path: Path, **kwargs):
    return require_ok(ws.call(AudioFileClip, str(path), **kwargs))


def _close(ws, clip):
    require_ok(ws.call(clip.close))


def _frame(ws, clip, t):
    return require_ok(ws.call(clip.get_frame, t))


def _gif_playback_slack(fps: float) -> float:
    """One frame plus a small muxer slack; tighter than a zero-delay GIF."""
    if fps <= 0:
        raise HarnessError(f"gif playback slack needs a positive fps; got {fps!r}")
    return 1.0 / fps + 0.05


def _assert_near_color(frame, color, *, atol: int, label: str):
    got = dominant_picture_rgb(frame)
    dist = _rgb_dist(got, color)
    print(f"{label} dominant={got} expected={color} dist={dist} atol={atol}", flush=True)
    if dist > atol:
        raise AssertionError(
            f"{label} dominant {got} is not within {atol} of {color}"
        )


def _png_rgb(path: Path) -> np.ndarray:
    rgb, _alpha = read_png_rgb_and_alpha(path)
    return rgb


def _integer_stripped_name(path: Path) -> str:
    return re.sub(r"\d+", "", path.name)


def _file_size(path: Path) -> int:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat {path}: {exc}") from exc
    return size


def _not_nonempty_media(path: Path) -> bool:
    try:
        if not path.exists():
            return True
        if not path.is_file():
            return True
        return path.stat().st_size <= 0
    except OSError as exc:
        raise HarnessError(f"cannot stat {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# A. Finite video write
# ---------------------------------------------------------------------------


def test_oracle_red_clip_writes_mp4_that_loads_red():
    with workspace() as ws:
        clip = _make_color(
            ws, _ORACLE_SIZE, _ORACLE_RED, duration=_ORACLE_DURATION, fps=_ORACLE_FPS
        )
        path = ws.resolve("oracle_red.mp4")
        _write_video(ws, clip, path)
        width, height = _ORACLE_SIZE
        file_size = container_video_size(path)
        file_duration = container_duration(path)
        print(
            f"oracle file size={file_size} duration={file_duration}",
            flush=True,
        )
        assert file_size == (width, height)
        _assert_close(file_duration, _ORACLE_DURATION, slack=_MUXER_SLACK, label="file_duration")
        loaded = _load_video(ws, path)
        try:
            _assert_close(
                loaded.duration, _ORACLE_DURATION, slack=_MUXER_SLACK, label="loaded_duration"
            )
            _assert_close(
                loaded.duration, file_duration, slack=_MUXER_SLACK, label="loaded_vs_probe"
            )
            assert tuple(int(v) for v in loaded.size) == (width, height)
            first = _frame(ws, loaded, 0.0)
            require_rgb_picture(first, height, width)
            _assert_near_color(first, _ORACLE_RED, atol=40, label="oracle_first")
        finally:
            _close(ws, loaded)


def test_written_video_frames_match_source_within_lossy():
    with workspace() as ws:
        width, height = _rect_even_size()
        first = _rgb_away_from()
        second = _rgb_away_from(first)
        duration = 0.4 + _rand_int(0, 2) * 0.1
        fps = float(_rand_int(8, 12))
        clip = _split_clip(ws, width, height, first, second, duration, fps=fps)
        path = ws.resolve("runtime_split.mp4")
        _write_video(ws, clip, path)
        probed = container_video_size(path)
        print(
            f"runtime size={width}x{height} duration={duration} fps={fps} "
            f"probed={probed} first={first} second={second}",
            flush=True,
        )
        assert probed == (width, height)
        loaded = _load_video(ws, path)
        try:
            _assert_close(loaded.duration, duration, slack=_MUXER_SLACK, label="runtime_duration")
            assert tuple(int(v) for v in loaded.size) == (width, height)
            early = _frame(ws, loaded, 0.05)
            late = _frame(ws, loaded, duration * 0.8)
            _assert_near_color(early, first, atol=55, label="early")
            _assert_near_color(late, second, atol=55, label="late")
            assert _rgb_dist(dominant_picture_rgb(early), dominant_picture_rgb(late)) > 40
            src_early = _frame(ws, clip, 0.05)
            src_late = _frame(ws, clip, duration * 0.8)
            assert pictures_close_lossy(early, src_early)
            assert pictures_close_lossy(late, src_late)
        finally:
            _close(ws, loaded)


def test_supplied_frame_rate_is_used_for_encode():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb_away_from()
        duration = 0.6
        rate_a = 8.0
        rate_b = 16.0
        source = _make_color(ws, (width, height), color, duration=duration)
        path_a = ws.resolve("fps_a.mp4")
        path_b = ws.resolve("fps_b.mp4")
        _write_video(ws, source, path_a, fps=rate_a, audio=False)
        _write_video(ws, source, path_b, fps=rate_b, audio=False)
        frames_a = independent_rgb_frames(path_a)
        frames_b = independent_rgb_frames(path_b)
        fps_a = container_frame_rate(path_a)
        fps_b = container_frame_rate(path_b)
        print(
            f"fps_a_frames={len(frames_a)} fps_b_frames={len(frames_b)} "
            f"probe_a={fps_a} probe_b={fps_b}",
            flush=True,
        )
        distinguishable = len(frames_a) != len(frames_b) or abs(fps_a - fps_b) > 1.0
        if not distinguishable:
            raise AssertionError(
                "two write-time frame rates produced indistinguishable "
                f"frame counts/container rates: {len(frames_a)}/{fps_a} vs "
                f"{len(frames_b)}/{fps_b}"
            )
        src = _frame(ws, source, 0.0)
        assert pictures_close_lossy(frames_a[0], src)
        assert pictures_close_lossy(frames_b[0], src)


def test_soundtrack_muxed_when_audio_left_on():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.6
        freq = _tone_hz()
        clip = _with_tone(
            ws, _make_color(ws, (width, height), color, duration=duration, fps=10), freq, duration
        )
        path = ws.resolve("tone_on.mp4")
        _write_video(ws, clip, path)
        assert container_has_audio(path) is True
        peak = dominant_tone_hz(pcm_from_container(path), _PCM_RATE)
        print(f"requested_hz={freq} measured_hz={peak}", flush=True)
        assert peak == pytest.approx(freq, rel=0.08, abs=12)


def test_audio_off_omits_soundtrack():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.6
        freq = _tone_hz()
        clip = _with_tone(
            ws, _make_color(ws, (width, height), color, duration=duration, fps=10), freq, duration
        )
        baseline = ws.resolve("audio_on.mp4")
        _write_video(ws, clip, baseline)
        assert container_has_audio(baseline) is True
        off = ws.resolve("audio_off.mp4")
        _write_video(ws, clip, off, audio=False)
        has_audio = container_has_audio(off)
        print(f"baseline_has_audio=True off_has_audio={has_audio}", flush=True)
        assert has_audio is False


def test_named_audio_file_replaces_soundtrack():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.8
        freq_a = _tone_hz()
        freq_b = _tone_hz()
        while abs(freq_a - freq_b) < 80:
            freq_b = _tone_hz()
        clip = _with_tone(
            ws,
            _make_color(ws, (width, height), color, duration=duration, fps=10),
            freq_a,
            duration,
        )
        replacement = ws.resolve("replacement.wav")
        write_pcm_wav(replacement, _tone_mono(freq_b, duration), _PCM_RATE)
        path = ws.resolve("replaced.mp4")
        _write_video(ws, clip, path, audio=str(replacement))
        assert container_has_audio(path) is True
        peak = dominant_tone_hz(pcm_from_container(path), _PCM_RATE)
        print(f"freq_a={freq_a} freq_b={freq_b} measured={peak}", flush=True)
        assert peak == pytest.approx(freq_b, rel=0.08, abs=12)
        assert abs(peak - freq_a) > 40


# ---------------------------------------------------------------------------
# B. Codecs, bitrate, preset
# ---------------------------------------------------------------------------


def test_default_video_codec_by_extension():
    # One inventory name (no pytest parametrize id). Every listed extension
    # is still a tooth: a swapped default for any of them fails this test.
    for ext, family in _VIDEO_CODEC_BY_EXT:
        with workspace() as ws:
            width, height = _rect_even_size()
            color = _rgb_away_from(_ORACLE_RED)
            clip = _make_color(ws, (width, height), color, duration=0.3, fps=10)
            path = ws.resolve(f"default_video.{ext}")
            _write_video(ws, clip, path, audio=False)
            token = container_video_codec(path)
            _assert_codec_family(token, family, label=f"{ext}_video")
            loaded = _load_video(ws, path, audio=False)
            try:
                _assert_near_color(
                    _frame(ws, loaded, 0.0), color, atol=60, label=f"{ext}_picture"
                )
            finally:
                _close(ws, loaded)


def test_default_audio_codec_by_extension():
    for ext, family in _VIDEO_AUDIO_CODEC_BY_EXT:
        with workspace() as ws:
            width, height = _rect_even_size()
            color = _rgb()
            duration = 0.6
            freq = _tone_hz()
            clip = _with_tone(
                ws, _make_color(ws, (width, height), color, duration=duration, fps=10), freq, duration
            )
            path = ws.resolve(f"default_av.{ext}")
            _write_video(ws, clip, path)
            token = container_audio_codec(path)
            _assert_codec_family(token, family, label=f"{ext}_audio")
            peak = dominant_tone_hz(pcm_from_container(path), _PCM_RATE)
            print(f"{ext} requested_hz={freq} measured_hz={peak}", flush=True)
            assert peak == pytest.approx(freq, rel=0.1, abs=16)


def test_avi_without_codec_does_not_succeed():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        clip = _make_color(ws, (width, height), color, duration=0.3, fps=10)
        missing = ws.resolve("needs_codec.avi")
        failed = ws.call(clip.write_videofile, str(missing), logger=None)
        require_failed(failed)
        rest = failure_identifies_codec_must_be_supplied(failed, missing, (width, height), color)
        print(f"avi_missing_codec remainder={rest!r}", flush=True)
        if not _not_nonempty_media(missing):
            raise AssertionError("avi write without a codec left a nonempty media file")
        ok = ws.resolve("named_codec.avi")
        _write_video(ws, clip, ok, codec="mpeg4", audio=False)
        loaded = _load_video(ws, ok, audio=False)
        try:
            _assert_near_color(_frame(ws, loaded, 0.0), color, atol=55, label="avi_named_codec")
        finally:
            _close(ws, loaded)


def test_caller_codec_overrides_extension_default():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        clip = _make_color(ws, (width, height), color, duration=0.3, fps=10)
        default_path = ws.resolve("default_mp4.mp4")
        override_path = ws.resolve("override_mpeg4.mp4")
        _write_video(ws, clip, default_path, audio=False)
        _write_video(ws, clip, override_path, codec="mpeg4", audio=False)
        default_token = container_video_codec(default_path)
        override_token = container_video_codec(override_path)
        _assert_codec_family(default_token, "h264", label="mp4_default")
        _assert_codec_family(override_token, "mpeg4", label="mp4_override")
        assert not _codec_in_family(override_token, "h264")
        loaded = _load_video(ws, override_path, audio=False)
        try:
            _assert_near_color(_frame(ws, loaded, 0.0), color, atol=55, label="override_picture")
        finally:
            _close(ws, loaded)


def test_pixel_format_override_is_in_the_file():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        clip = _make_color(ws, (width, height), color, duration=0.3, fps=10)
        path_a = ws.resolve("pix_a.mkv")
        path_b = ws.resolve("pix_b.mkv")
        fmt_a = "rgb24"
        fmt_b = "rgba"
        _write_video(ws, clip, path_a, codec="png", pixel_format=fmt_a, audio=False)
        _write_video(ws, clip, path_b, codec="png", pixel_format=fmt_b, audio=False)
        got_a = container_pixel_format(path_a)
        got_b = container_pixel_format(path_b)
        print(f"pix_a={got_a} pix_b={got_b}", flush=True)
        if got_a.casefold() == got_b.casefold():
            raise AssertionError(
                f"PIX two pixel formats produced the same probed format {got_a!r}"
            )
        frames_a = independent_rgb_frames(path_a)
        frames_b = independent_rgb_frames(path_b)
        if not frames_a or not frames_b:
            raise AssertionError("PIX pixel-format files decoded no RGB frames")
        require_rgb_picture(frames_a[0], height, width)
        require_rgb_picture(frames_b[0], height, width)
        _assert_near_color(frames_a[0], color, atol=55, label="pix_a_picture")
        _assert_near_color(frames_b[0], color, atol=55, label="pix_b_picture")


def test_bitrate_override_changes_encoded_size():
    with workspace() as ws:
        width, height = 160, 120
        duration = 2.0
        fps = 15
        salt = _rand_int(1, 10**6)
        clip = _pattern_clip(ws, width, height, duration, fps, salt)
        low = ws.resolve("br_low.mp4")
        high = ws.resolve("br_high.mp4")
        _write_video(ws, clip, low, codec="mpeg4", bitrate="64k", audio=False)
        _write_video(ws, clip, high, codec="mpeg4", bitrate="4000k", audio=False)
        size_low = _file_size(low)
        size_high = _file_size(high)
        print(f"bitrate_low={size_low} bitrate_high={size_high}", flush=True)
        if size_low == size_high:
            raise AssertionError(
                f"BR two video bitrates produced identical file sizes {size_low}"
            )
        src = _frame(ws, clip, 0.05)
        loaded = _load_video(ws, high, audio=False)
        try:
            got = _frame(ws, loaded, 0.05)
            close = pictures_close_lossy(got, src, mean_atol=45.0, max_atol=140.0)
            print(f"bitrate picture close={close}", flush=True)
            if not close:
                src_mean = float(as_numeric_array(src).mean())
                got_mean = float(as_numeric_array(got).mean())
                if abs(src_mean - got_mean) > 30:
                    raise AssertionError(
                        "bitrate override changed the picture away from the source"
                    )
        finally:
            _close(ws, loaded)


def test_audio_bitrate_override_changes_encoded_size():
    with workspace() as ws:
        width, height = 20, 16
        duration = 2.0
        fps = 10
        color = _rgb()
        freq = _tone_hz()
        clip = _with_tone(
            ws,
            _make_color(ws, (width, height), color, duration=duration, fps=fps),
            freq,
            duration,
        )
        low = ws.resolve("abr_low.mp4")
        high = ws.resolve("abr_high.mp4")
        _write_video(ws, clip, low, audio_bitrate="32k")
        _write_video(ws, clip, high, audio_bitrate="192k")
        assert container_has_audio(low) is True
        assert container_has_audio(high) is True
        size_low = _file_size(low)
        size_high = _file_size(high)
        print(
            f"video_audio_bitrate_low={size_low} video_audio_bitrate_high={size_high}",
            flush=True,
        )
        if size_low == size_high:
            raise AssertionError(
                "two video-file audio bitrates produced identical file sizes "
                f"{size_low}; the audio bitrate override was not used for encode"
            )
        peak = dominant_tone_hz(pcm_from_container(high), _PCM_RATE)
        assert peak == pytest.approx(freq, rel=0.1, abs=16)


def test_preset_changes_size_not_picture():
    with workspace() as ws:
        width, height = 80, 64
        duration = 1.2
        fps = 15
        salt = _rand_int(1, 10**6)
        clip = _pattern_clip(ws, width, height, duration, fps, salt)
        src = _frame(ws, clip, 0.1)
        omitted = ws.resolve("preset_omit.mp4")
        medium = ws.resolve("preset_medium.mp4")
        ultra = ws.resolve("preset_ultra.mp4")
        slow = ws.resolve("preset_slow.mp4")
        _write_video(ws, clip, omitted, audio=False)
        _write_video(ws, clip, medium, preset="medium", audio=False)
        _write_video(ws, clip, ultra, preset="ultrafast", audio=False)
        _write_video(ws, clip, slow, preset="slow", audio=False)
        s_omit = _file_size(omitted)
        s_med = _file_size(medium)
        s_fast = _file_size(ultra)
        s_slow = _file_size(slow)
        print(
            f"preset omit={s_omit} medium={s_med} ultrafast={s_fast} slow={s_slow}",
            flush=True,
        )
        if s_fast == s_slow:
            raise AssertionError(
                "ultrafast and slow presets produced identical sizes; "
                "preset did not change file size"
            )
        omit_fast = s_omit - s_fast
        med_fast = s_med - s_fast
        if omit_fast * med_fast <= 0:
            raise AssertionError(
                "omitted preset vs ultrafast is not in the same size "
                f"direction as named medium vs ultrafast ({omit_fast} vs {med_fast})"
            )
        ultra_gap = abs(med_fast)
        omit_med = abs(s_omit - s_med)
        if ultra_gap > 400 and omit_med >= ultra_gap * 0.7:
            raise AssertionError(
                "omitted preset vs named medium shows an ultrafast-scale "
                f"size gap ({omit_med} vs ultrafast-gap {ultra_gap})"
            )
        loaded = _load_video(ws, slow, audio=False)
        try:
            got = _frame(ws, loaded, 0.1)
            close = pictures_close_lossy(got, src, mean_atol=45.0, max_atol=140.0)
            if not close:
                src_mean = float(as_numeric_array(src).mean())
                got_mean = float(as_numeric_array(got).mean())
                if abs(src_mean - got_mean) > 30:
                    raise AssertionError(
                        "slow preset changed the picture away from the source"
                    )
        finally:
            _close(ws, loaded)
        loaded_fast = _load_video(ws, ultra, audio=False)
        try:
            got_fast = _frame(ws, loaded_fast, 0.1)
            close_fast = pictures_close_lossy(got_fast, src, mean_atol=45.0, max_atol=140.0)
            if not close_fast:
                src_mean = float(as_numeric_array(src).mean())
                got_mean = float(as_numeric_array(got_fast).mean())
                if abs(src_mean - got_mean) > 30:
                    raise AssertionError(
                        "ultrafast preset changed the picture away from the source"
                    )
        finally:
            _close(ws, loaded_fast)

        color_clip = _make_color(ws, (160, 128), _rgb(), duration=1.2, fps=15)
        warm = ws.resolve("preset_time_warm.mp4")
        timed_fast = ws.resolve("preset_time_ultra.mp4")
        timed_slow = ws.resolve("preset_time_slow.mp4")
        _write_video(ws, color_clip, warm, preset="ultrafast", audio=False)
        t0 = time.perf_counter()
        _write_video(ws, color_clip, timed_fast, preset="ultrafast", audio=False)
        time_fast = time.perf_counter() - t0
        t1 = time.perf_counter()
        _write_video(ws, color_clip, timed_slow, preset="slow", audio=False)
        time_slow = time.perf_counter() - t1
        print(
            f"preset encode_s ultrafast={time_fast:.4f} slow={time_slow:.4f}",
            flush=True,
        )
        if time_slow <= time_fast:
            raise AssertionError(
                "slow preset did not change encode time relative to ultrafast; "
                f"ultrafast={time_fast:.4f}s slow={time_slow:.4f}s"
            )


def test_each_listed_preset_writes_loadable_picture():
    # One inventory name. Refusing any listed preset other than medium fails
    # here; ultrafast is the first arm a non-medium-only writer hits.
    for preset in _PRESETS:
        with workspace() as ws:
            color = _rgb_away_from(_ORACLE_RED)
            clip = _make_color(ws, (20, 16), color, duration=0.2, fps=10)
            path = ws.resolve(f"preset_{preset}.mp4")
            _write_video(ws, clip, path, preset=preset, audio=False)
            loaded = _load_video(ws, path, audio=False)
            try:
                _assert_near_color(
                    _frame(ws, loaded, 0.0), color, atol=55, label=f"preset_{preset}"
                )
            finally:
                _close(ws, loaded)


def test_thread_count_still_writes_loadable():
    with workspace() as ws:
        color = _rgb()
        clip = _make_color(ws, (20, 16), color, duration=0.2, fps=10)
        path = ws.resolve("threads.mp4")
        _write_video(ws, clip, path, threads=3, audio=False)
        loaded = _load_video(ws, path, audio=False)
        try:
            _assert_near_color(_frame(ws, loaded, 0.0), color, atol=55, label="threads")
        finally:
            _close(ws, loaded)


# ---------------------------------------------------------------------------
# C. Audio file write
# ---------------------------------------------------------------------------


def test_oracle_tone_writes_wav_that_roundtrips():
    with workspace() as ws:
        freq = 440.0
        duration = 2.0
        clip = _tone_clip(ws, freq, duration)
        path = ws.resolve("oracle_tone.wav")
        _write_audio(ws, clip, path)
        token = container_audio_codec(path)
        _assert_codec_family(token, "pcm_s16le", label="oracle_wav")
        loaded = _load_audio(ws, path)
        try:
            _assert_close(loaded.duration, duration, slack=_MUXER_SLACK, label="wav_duration")
        finally:
            _close(ws, loaded)
        extracted = pcm_from_container(path)
        n = int(as_numeric_array(extracted).reshape(-1).size)
        t = np.arange(n, dtype=float) / float(_PCM_RATE)
        synth = 0.5 * np.sin(2.0 * np.pi * freq * t)
        same = pcm_same_signal(extracted, synth)
        close = pcm_close_lossy(extracted, synth)
        print(f"oracle wav same={same} close={close} n={n}", flush=True)
        if not (same or close):
            raise AssertionError(
                "WAV PCM does not match the generated tone within ordinary "
                "codec tolerance"
            )
        peak = dominant_tone_hz(extracted, _PCM_RATE)
        assert peak == pytest.approx(freq, rel=0.05, abs=8)

        runtime_freq = _tone_hz()
        runtime_duration = 0.7 + _rand_int(0, 3) * 0.1
        runtime = _tone_clip(ws, runtime_freq, runtime_duration, stereo=True)
        runtime_path = ws.resolve("runtime_tone.wav")
        _write_audio(ws, runtime, runtime_path)
        runtime_loaded = _load_audio(ws, runtime_path)
        try:
            _assert_close(
                runtime_loaded.duration,
                runtime_duration,
                slack=_MUXER_SLACK,
                label="runtime_wav_duration",
            )
        finally:
            _close(ws, runtime_loaded)
        runtime_pcm = pcm_from_container(runtime_path)
        runtime_peak = dominant_tone_hz(runtime_pcm, _PCM_RATE)
        print(
            f"runtime_freq={runtime_freq} measured={runtime_peak} D={runtime_duration}",
            flush=True,
        )
        assert runtime_peak == pytest.approx(runtime_freq, rel=0.08, abs=12)


def test_audio_codec_by_extension():
    # One inventory name covering mp3/ogg/wav/flac. A swapped wav default
    # is not pcm_s16le and cannot reproduce the runtime tone.
    for ext, family in _AUDIO_CODEC_BY_EXT:
        with workspace() as ws:
            freq = _tone_hz()
            duration = 0.8
            clip = _tone_clip(ws, freq, duration)
            path = ws.resolve(f"audio_default.{ext}")
            _write_audio(ws, clip, path)
            token = container_audio_codec(path)
            _assert_codec_family(token, family, label=f"{ext}_audio_file")
            loaded = _load_audio(ws, path)
            try:
                _assert_close(
                    loaded.duration, duration, slack=_MUXER_SLACK, label=f"{ext}_duration"
                )
            finally:
                _close(ws, loaded)
            peak = dominant_tone_hz(pcm_from_container(path), _PCM_RATE)
            print(f"{ext} freq={freq} measured={peak} codec={token}", flush=True)
            assert peak == pytest.approx(freq, rel=0.1, abs=16)


# ---------------------------------------------------------------------------
# D. GIF
# ---------------------------------------------------------------------------


def test_gif_exists_and_playback_length_matches_duration():
    with workspace() as ws:
        width, height = 20, 16
        fps = 10.0
        duration_a = 0.4
        duration_b = 0.8
        salt = _rand_int(1, 10**6)
        clip_a = _unique_clip(ws, width, height, duration_a, fps, salt)
        clip_b = _unique_clip(ws, width, height, duration_b, fps, salt)
        path_a = ws.resolve("gif_a.gif")
        path_b = ws.resolve("gif_b.gif")
        _write_gif(ws, clip_a, path_a)
        _write_gif(ws, clip_b, path_b)
        frames_a = gif_frames_rgba(path_a)
        frames_b = gif_frames_rgba(path_b)
        play_a = gif_playback_seconds(path_a)
        play_b = gif_playback_seconds(path_b)
        slack = _gif_playback_slack(fps)
        print(
            f"gif n_a={len(frames_a)} play_a={play_a} n_b={len(frames_b)} play_b={play_b}",
            flush=True,
        )
        _assert_close(play_a, duration_a, slack=slack, label="gif_play_a")
        _assert_close(play_b, duration_b, slack=slack, label="gif_play_b")
        if len(frames_a) == len(frames_b):
            raise AssertionError(
                f"two durations at {fps} fps produced the same GIF frame count "
                f"{len(frames_a)}"
            )


def test_gif_frame_count_follows_frame_rate():
    with workspace() as ws:
        width, height = 20, 16
        duration = 0.4
        fps_slow = 5.0
        fps_fast = 10.0
        salt = _rand_int(1, 10**6)
        clip_slow = _unique_clip(ws, width, height, duration, fps_slow, salt)
        clip_fast = _unique_clip(ws, width, height, duration, fps_fast, salt)
        path_slow = ws.resolve("gif_slow.gif")
        path_fast = ws.resolve("gif_fast.gif")
        _write_gif(ws, clip_slow, path_slow)
        _write_gif(ws, clip_fast, path_fast)
        n_slow = len(gif_frames_rgba(path_slow))
        n_fast = len(gif_frames_rgba(path_fast))
        play_slow = gif_playback_seconds(path_slow)
        play_fast = gif_playback_seconds(path_fast)
        slack_slow = _gif_playback_slack(fps_slow)
        slack_fast = _gif_playback_slack(fps_fast)
        print(
            f"gif fps n={n_slow}/{n_fast} play slow={play_slow} fast={play_fast}",
            flush=True,
        )
        _assert_close(play_slow, duration, slack=slack_slow, label="gif_play_slow")
        _assert_close(play_fast, duration, slack=slack_fast, label="gif_play_fast")
        if n_slow == n_fast:
            raise AssertionError(
                f"two frame rates produced the same GIF frame count {n_slow}"
            )


def test_gif_animates_time_varying_frames():
    with workspace() as ws:
        width, height = _rect_even_size()
        first = _rgb_away_from()
        second = _rgb_away_from(first)
        duration = 0.4
        clip = _split_clip(ws, width, height, first, second, duration, fps=10)
        path = ws.resolve("gif_anim.gif")
        _write_gif(ws, clip, path)
        frames = gif_frames_rgba(path)
        if len(frames) < 2:
            raise AssertionError(f"GIF is not animated; frame_count={len(frames)}")
        early = dominant_picture_rgb(frames[0][:, :, :3])
        late = dominant_picture_rgb(frames[-1][:, :, :3])
        print(f"gif early={early} late={late} first={first} second={second}", flush=True)
        assert _rgb_dist(early, first) < 70
        assert _rgb_dist(late, second) < 70
        assert _rgb_dist(early, late) > 40


def test_gif_stores_loop_count():
    with workspace() as ws:
        clip = _make_color(ws, (20, 16), _rgb(), duration=0.2, fps=10)
        path_a = ws.resolve("loop_a.gif")
        path_b = ws.resolve("loop_b.gif")
        loop_a = 2
        loop_b = 8
        _write_gif(ws, clip, path_a, loop=loop_a)
        _write_gif(ws, clip, path_b, loop=loop_b)
        got_a = gif_loop_count(path_a)
        got_b = gif_loop_count(path_b)
        print(f"gif loop stored {got_a!r} vs {got_b!r}", flush=True)
        if got_a == got_b:
            raise AssertionError(
                f"two loop counts stored the same field {got_a!r}"
            )


def test_gif_writes_color_frames_not_mask_transparency():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb_away_from()
        duration = 0.3
        pattern = _block_mask(height, width)
        clip = _make_color(ws, (width, height), color, duration=duration, fps=10)
        masked = require_ok(ws.call(clip.with_mask, _mask_clip(ws, pattern, duration)))
        png_path = ws.resolve("mask_baseline.png")
        _save_frame(ws, masked, png_path)
        rgb_png, alpha_png = read_png_rgb_and_alpha(png_path)
        if alpha_png is None:
            raise AssertionError("default PNG frame write produced no alpha layer")
        opaque = float(np.mean(alpha_png[pattern >= 0.5]))
        clear = float(np.mean(alpha_png[pattern < 0.5]))
        print(f"png_alpha opaque={opaque:.1f} clear={clear:.1f}", flush=True)
        assert opaque > 200.0
        assert clear < 40.0
        gif_path = ws.resolve("mask_color.gif")
        _write_gif(ws, masked, gif_path)
        frames = gif_frames_rgba(gif_path)
        rgba = frames[0]
        mask0 = pattern < 0.5
        mask1 = pattern >= 0.5
        trans0 = float(np.mean(rgba[:, :, 3][mask0] < 40))
        trans1 = float(np.mean(rgba[:, :, 3][mask1] < 40))
        rgb0 = tuple(int(round(v)) for v in np.median(rgba[:, :, :3][mask0], axis=0))
        print(
            f"gif trans0={trans0:.2f} trans1={trans1:.2f} rgb0={rgb0} color={color}",
            flush=True,
        )
        if trans0 > 0.7 and trans1 < 0.3:
            raise AssertionError(
                "GIF stored the clip mask as transparency "
                f"(mask0 transparent={trans0:.2f}, mask1 transparent={trans1:.2f})"
            )
        if _rgb_dist(rgb0, color) > 70:
            raise AssertionError(
                f"GIF mask-0 region is {rgb0}, not the picture color {color}"
            )


# ---------------------------------------------------------------------------
# E. Image sequence
# ---------------------------------------------------------------------------


def test_oracle_image_sequence_one_png_per_frame():
    with workspace() as ws:
        duration = 0.04
        fps = 50.0
        color = _rgb_away_from(_ORACLE_RED)
        clip = _make_color(ws, (20, 16), color, duration=duration, fps=fps)
        folder = ws.resolve("seq_oracle")
        folder.mkdir(parents=True, exist_ok=True)
        pattern = str(folder / "frame_%d.png")
        paths = _write_sequence(ws, clip, pattern)
        expected = int(duration * fps)
        print(f"oracle_seq count={len(paths)} expected={expected}", flush=True)
        assert len(paths) == expected
        assert expected >= 2
        src0 = _frame(ws, clip, 0.0)
        assert pictures_equal(_png_rgb(paths[0]), src0)


def test_sequence_later_image_matches_later_frame():
    with workspace() as ws:
        width, height = _rect_even_size()
        first = _rgb_away_from()
        second = _rgb_away_from(first)
        duration = 0.4
        fps = 10.0
        clip = _split_clip(ws, width, height, first, second, duration, fps=fps)
        folder = ws.resolve("seq_later")
        folder.mkdir(parents=True, exist_ok=True)
        pattern = str(folder / "pic_%d.png")
        paths = _write_sequence(ws, clip, pattern)
        src0 = _frame(ws, clip, 0.0)
        t_late = duration * 0.75
        src_late = _frame(ws, clip, t_late)
        assert not pictures_equal(src0, src_late)
        assert pictures_equal(_png_rgb(paths[0]), src0)
        assert not pictures_equal(_png_rgb(paths[0]), src_late)
        matched = False
        for item in paths[1:]:
            rgb = _png_rgb(item)
            if pictures_equal(rgb, src_late):
                matched = True
                print(f"later_match path={item}", flush=True)
                break
        if not matched:
            raise AssertionError(
                "no later sequence image matched the source picture at a "
                f"later time t={t_late}; first-frame copies would look like this"
            )


def test_sequence_paths_instantiate_caller_pattern():
    with workspace() as ws:
        clip = _make_color(ws, (20, 16), _rgb(), duration=0.2, fps=10)
        folder_a = ws.resolve("seq_stem_a")
        folder_b = ws.resolve("seq_stem_b")
        folder_a.mkdir(parents=True, exist_ok=True)
        folder_b.mkdir(parents=True, exist_ok=True)
        letters = "abcdefghijkmnopqrstuvwxyz"
        stem_a = "alpha" + letters[_rand_int(0, len(letters) - 1)]
        stem_b = "beta" + letters[_rand_int(0, len(letters) - 1)]
        pattern_a = str(folder_a / f"{stem_a}_%d.png")
        pattern_b = str(folder_b / f"{stem_b}_%d.png")
        paths_a = _write_sequence(ws, clip, pattern_a)
        paths_b = _write_sequence(ws, clip, pattern_b)
        marks_a = {_integer_stripped_name(path) for path in paths_a}
        marks_b = {_integer_stripped_name(path) for path in paths_b}
        print(
            f"pattern stems {stem_a!r}/{stem_b!r} marks {marks_a} vs {marks_b}",
            flush=True,
        )
        if marks_a == marks_b:
            raise AssertionError(
                "two name-pattern stems produced the same stripped filenames "
                f"{marks_a}"
            )
        if not any(stem_a in mark for mark in marks_a):
            raise AssertionError(
                f"returned names {marks_a} do not carry stem {stem_a!r}"
            )
        if not any(stem_b in mark for mark in marks_b):
            raise AssertionError(
                f"returned names {marks_b} do not carry stem {stem_b!r}"
            )


def test_png_sequence_alpha_matches_mask_by_default():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.2
        fps = 10.0
        pattern = _block_mask(height, width)
        clip = _make_color(ws, (width, height), color, duration=duration, fps=fps)
        masked = require_ok(ws.call(clip.with_mask, _mask_clip(ws, pattern, duration)))
        folder = ws.resolve("seq_alpha_on")
        folder.mkdir(parents=True, exist_ok=True)
        paths = _write_sequence(ws, masked, str(folder / "on_%d.png"))
        rgb, alpha = read_png_rgb_and_alpha(paths[0])
        if alpha is None:
            raise AssertionError("default PNG sequence write produced no alpha layer")
        src = _frame(ws, clip, 0.0)
        assert pictures_equal(rgb, src)
        opaque = float(np.mean(alpha[pattern >= 0.5]))
        clear = float(np.mean(alpha[pattern < 0.5]))
        print(f"seq_alpha opaque={opaque:.1f} clear={clear:.1f}", flush=True)
        assert opaque > 200.0
        assert clear < 40.0


def test_png_sequence_alpha_off_omits_mask():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.2
        fps = 10.0
        pattern = _block_mask(height, width)
        clip = _make_color(ws, (width, height), color, duration=duration, fps=fps)
        masked = require_ok(ws.call(clip.with_mask, _mask_clip(ws, pattern, duration)))
        on_dir = ws.resolve("seq_alpha_live")
        off_dir = ws.resolve("seq_alpha_off")
        on_dir.mkdir(parents=True, exist_ok=True)
        off_dir.mkdir(parents=True, exist_ok=True)
        on_paths = _write_sequence(ws, masked, str(on_dir / "on_%d.png"))
        rgb_on, alpha_on = read_png_rgb_and_alpha(on_paths[0])
        if alpha_on is None:
            raise AssertionError("omitted-alpha-flag sequence PNG has no alpha baseline")
        assert float(np.mean(alpha_on[pattern < 0.5])) < 40.0
        off_paths = _write_sequence(
            ws, masked, str(off_dir / "off_%d.png"), with_mask=False
        )
        rgb_off, alpha_off = read_png_rgb_and_alpha(off_paths[0])
        src = _frame(ws, clip, 0.0)
        assert pictures_equal(rgb_off, src)
        if alpha_off is not None:
            punched = float(np.mean(alpha_off[pattern < 0.5])) < 40.0
            kept = float(np.mean(alpha_off[pattern >= 0.5])) > 200.0
            if punched and kept:
                raise AssertionError(
                    "alpha-off sequence PNG still uses the mask as alpha"
                )


# ---------------------------------------------------------------------------
# F. Single frame
# ---------------------------------------------------------------------------


def test_save_frame_defaults_to_time_zero():
    with workspace() as ws:
        width, height = _rect_even_size()
        first = _rgb_away_from()
        second = _rgb_away_from(first)
        duration = 0.6
        clip = _split_clip(ws, width, height, first, second, duration, fps=10)
        path = ws.resolve("frame_default.png")
        _save_frame(ws, clip, path)
        src0 = _frame(ws, clip, 0.0)
        src_late = _frame(ws, clip, duration * 0.8)
        rgb = _png_rgb(path)
        assert pictures_equal(rgb, src0)
        assert not pictures_equal(rgb, src_late)


def test_save_frame_at_named_time_matches_clip():
    with workspace() as ws:
        width, height = _rect_even_size()
        first = _rgb_away_from()
        second = _rgb_away_from(first)
        duration = 0.8
        t1 = duration * 0.75
        clip = _split_clip(ws, width, height, first, second, duration, fps=10)
        numeric = ws.resolve("frame_numeric.png")
        encoded = ws.resolve("frame_encoded.png")
        _save_frame(ws, clip, numeric, t=t1)
        clock = f"00:00:{t1:06.3f}"
        _save_frame(ws, clip, encoded, t=clock)
        src = _frame(ws, clip, t1)
        src0 = _frame(ws, clip, 0.0)
        rgb_n = _png_rgb(numeric)
        rgb_c = _png_rgb(encoded)
        assert pictures_equal(rgb_n, src)
        assert pictures_equal(rgb_c, src)
        assert pictures_equal(rgb_n, rgb_c)
        assert not pictures_equal(rgb_n, src0)
        print(f"save_frame t1={t1} clock={clock}", flush=True)


def test_save_frame_png_alpha_matches_mask_by_default():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.4
        pattern = _block_mask(height, width)
        clip = _make_color(ws, (width, height), color, duration=duration, fps=8)
        masked = require_ok(ws.call(clip.with_mask, _mask_clip(ws, pattern, duration)))
        path = ws.resolve("frame_alpha_on.png")
        _save_frame(ws, masked, path)
        rgb, alpha = read_png_rgb_and_alpha(path)
        if alpha is None:
            raise AssertionError("default PNG frame write produced no alpha layer")
        src = _frame(ws, clip, 0.0)
        assert pictures_equal(rgb, src)
        opaque = float(np.mean(alpha[pattern >= 0.5]))
        clear = float(np.mean(alpha[pattern < 0.5]))
        print(f"frame_alpha opaque={opaque:.1f} clear={clear:.1f}", flush=True)
        assert opaque > 200.0
        assert clear < 40.0


def test_save_frame_alpha_off_omits_mask():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        duration = 0.4
        pattern = _block_mask(height, width)
        clip = _make_color(ws, (width, height), color, duration=duration, fps=8)
        masked = require_ok(ws.call(clip.with_mask, _mask_clip(ws, pattern, duration)))
        on_path = ws.resolve("frame_alpha_live.png")
        off_path = ws.resolve("frame_alpha_off.png")
        _save_frame(ws, masked, on_path)
        rgb_on, alpha_on = read_png_rgb_and_alpha(on_path)
        if alpha_on is None:
            raise AssertionError("omitted-alpha-flag frame PNG has no alpha baseline")
        _save_frame(ws, masked, off_path, with_mask=False)
        rgb_off, alpha_off = read_png_rgb_and_alpha(off_path)
        src = _frame(ws, clip, 0.0)
        assert pictures_equal(rgb_off, src)
        if alpha_off is not None:
            punched = float(np.mean(alpha_off[pattern < 0.5])) < 40.0
            kept = float(np.mean(alpha_off[pattern >= 0.5])) > 200.0
            if punched and kept:
                raise AssertionError("alpha-off frame PNG still uses the mask as alpha")


def test_save_frame_still_without_duration_or_fps():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb_away_from()
        still = require_ok(ws.call(ColorClip, (width, height), color=color))
        path = ws.resolve("still.png")
        _save_frame(ws, still, path)
        rgb = _png_rgb(path)
        src = _frame(ws, still, 0.0)
        assert pictures_equal(rgb, src)
        require_rgb_picture(rgb, height, width, color)


# ---------------------------------------------------------------------------
# G. Companion audio
# ---------------------------------------------------------------------------


def test_default_write_leaves_no_companion_audio_file():
    with workspace() as ws:
        duration = 0.6
        freq = _tone_hz()
        clip = _with_tone(
            ws, _make_color(ws, (20, 16), _rgb(), duration=duration, fps=10), freq, duration
        )
        path = ws.resolve("mux_default.mp4")
        _write_video(ws, clip, path)
        assert container_has_audio(path) is True
        leftovers = sibling_audio_paths(path)
        print(f"default companions={leftovers}", flush=True)
        if leftovers:
            raise AssertionError(
                f"default video write left companion audio files: {leftovers}"
            )


def test_named_companion_kept_contains_soundtrack():
    with workspace() as ws:
        duration = 0.8
        freq = _tone_hz()
        clip = _with_tone(
            ws, _make_color(ws, (20, 16), _rgb(), duration=duration, fps=10), freq, duration
        )
        video = ws.resolve("mux_keep.mp4")
        companion = ws.resolve("kept_soundtrack.mp3")
        _write_video(
            ws, clip, video, temp_audiofile=str(companion), remove_temp=False
        )
        assert container_has_audio(video) is True
        media_file_nonempty(companion)
        assert container_has_audio(companion) is True
        peak = dominant_tone_hz(pcm_from_container(companion), _PCM_RATE)
        print(f"kept companion hz={peak} requested={freq}", flush=True)
        assert peak == pytest.approx(freq, rel=0.1, abs=16)


def test_named_companion_without_keep_is_not_left():
    with workspace() as ws:
        duration = 0.6
        freq = _tone_hz()
        clip = _with_tone(
            ws, _make_color(ws, (20, 16), _rgb(), duration=duration, fps=10), freq, duration
        )
        companion_name = "named_soundtrack.mp3"

        keep_dir = ws.resolve("keep_arm")
        keep_dir.mkdir(parents=True, exist_ok=True)
        keep_video = keep_dir / "mux.mp4"
        keep_companion = keep_dir / companion_name
        _write_video(
            ws, clip, keep_video, temp_audiofile=str(keep_companion), remove_temp=False
        )
        assert container_has_audio(keep_video) is True
        media_file_nonempty(keep_companion)
        assert container_has_audio(keep_companion) is True
        keep_peak = dominant_tone_hz(pcm_from_container(keep_companion), _PCM_RATE)
        print(f"keep arm companion hz={keep_peak} requested={freq}", flush=True)
        assert keep_peak == pytest.approx(freq, rel=0.1, abs=16)

        drop_dir = ws.resolve("drop_arm")
        drop_dir.mkdir(parents=True, exist_ok=True)
        drop_video = drop_dir / "mux.mp4"
        drop_companion = drop_dir / companion_name
        _write_video(ws, clip, drop_video, temp_audiofile=str(drop_companion))
        assert container_has_audio(drop_video) is True
        print(f"named_without_keep exists={drop_companion.exists()}", flush=True)
        if drop_companion.exists():
            raise AssertionError(
                "named companion path was left after write without asking to keep it"
            )
        leftovers = sibling_audio_paths(drop_video)
        if leftovers:
            raise AssertionError(
                f"unnamed leftover companion audio remains: {leftovers}"
            )


# ---------------------------------------------------------------------------
# H. Refusals and FFmpeg negative control
# ---------------------------------------------------------------------------


def test_encode_without_duration_fails_for_video_gif_sequence():
    # One inventory name. Skipping the duration check on video, GIF, or
    # sequence makes require_failed / missing-duration identification fail.
    for kind in ("video", "gif", "sequence"):
        with workspace() as ws:
            size = _rect_even_size()
            color = _rgb()
            infinite = _make_color(ws, size, color, duration=None, fps=10)
            if kind == "video":
                target = ws.resolve("missing_dur.mp4")
                failed = ws.call(infinite.write_videofile, str(target), logger=None)
            elif kind == "gif":
                target = ws.resolve("missing_dur.gif")
                failed = ws.call(infinite.write_gif, str(target), logger=None)
            else:
                folder = ws.resolve("missing_dur_seq")
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / "frame_%d.png"
                failed = ws.call(infinite.write_images_sequence, str(target), logger=None)
            require_failed(failed)
            rest = failure_identifies_missing_duration(failed, target, size, color)
            print(f"{kind}_missing_duration remainder={rest!r}", flush=True)
            if kind != "sequence":
                if not _not_nonempty_media(Path(target)):
                    raise AssertionError(
                        f"{kind} write without duration left nonempty media"
                    )
            finite = require_ok(ws.call(infinite.with_duration, 0.3))
            if kind == "video":
                _write_video(ws, finite, ws.resolve("has_dur.mp4"), audio=False)
            elif kind == "gif":
                _write_gif(ws, finite, ws.resolve("has_dur.gif"))
            else:
                folder = ws.resolve("has_dur_seq")
                folder.mkdir(parents=True, exist_ok=True)
                _write_sequence(ws, finite, str(folder / "frame_%d.png"))


def test_encode_without_frame_rate_fails_for_video_gif_sequence():
    for kind in ("video", "gif", "sequence"):
        with workspace() as ws:
            size = _rect_even_size()
            color = _rgb()
            clip = _make_color(ws, size, color, duration=0.3, fps=None)
            if kind == "video":
                target = ws.resolve("missing_fps.mp4")
                failed = ws.call(clip.write_videofile, str(target), logger=None)
            elif kind == "gif":
                target = ws.resolve("missing_fps.gif")
                failed = ws.call(clip.write_gif, str(target), logger=None)
            else:
                folder = ws.resolve("missing_fps_seq")
                folder.mkdir(parents=True, exist_ok=True)
                target = folder / "frame_%d.png"
                failed = ws.call(clip.write_images_sequence, str(target), logger=None)
            require_failed(failed)
            rest = failure_identifies_missing_frame_rate(failed, target, size, color)
            print(f"{kind}_missing_fps remainder={rest!r}", flush=True)
            if kind == "video":
                _write_video(ws, clip, ws.resolve("has_fps.mp4"), fps=10, audio=False)
            elif kind == "gif":
                _write_gif(ws, clip, ws.resolve("has_fps.gif"), fps=10)
            else:
                folder = ws.resolve("has_fps_seq")
                folder.mkdir(parents=True, exist_ok=True)
                _write_sequence(ws, clip, str(folder / "frame_%d.png"), fps=10)


def test_extension_without_default_codec_fails():
    with workspace() as ws:
        clip = _make_color(ws, (20, 16), _rgb(), duration=0.3, fps=10)
        unknown = ws.resolve("unknown.nope")
        failed = ws.call(clip.write_videofile, str(unknown), logger=None)
        require_failed(failed)
        rest = failure_identifies_codec_must_be_supplied(failed, unknown)
        print(f"unknown_ext remainder={rest!r}", flush=True)
        if not _not_nonempty_media(unknown):
            raise AssertionError("unknown extension encoded without a codec")


def test_unknown_codec_does_not_produce_openable_encode():
    with workspace() as ws:
        width, height = _rect_even_size()
        color = _rgb()
        clip = _make_color(ws, (width, height), color, duration=0.3, fps=10)
        ok = ws.resolve("known_codec.mp4")
        _write_video(ws, clip, ok, audio=False)
        if not ffmpeg_opens_nonempty_media(ok):
            raise AssertionError("named-codec sibling is not a nonempty openable media file")
        bogus = f"notacodec{_rand_int(1000, 9999)}"
        target = ws.resolve("unknown_codec.mp4")
        result = ws.call(
            clip.write_videofile,
            str(target),
            codec=bogus,
            logger=None,
            audio=False,
        )
        openable = ffmpeg_opens_nonempty_media(target)
        print(
            f"unknown_codec={bogus!r} completed={result.exception is None} "
            f"openable={openable} exists={target.exists()}",
            flush=True,
        )
        if result.exception is None:
            print("unknown codec write returned as a completed call", flush=True)
        if openable:
            raise AssertionError(
                "a codec name FFmpeg does not know produced a nonempty media "
                f"file that FFmpeg can open; path={target} codec={bogus!r}"
            )


def test_ffmpeg_unreachable_fails_mp4_and_wav_not_gif_sequence_frame():
    gif_color_a = (200, 30, 30)
    gif_color_b = (30, 30, 200)
    seq_color = (12, 190, 40)
    still_color = (9, 88, 177)
    still_size = (18, 16)
    seq_size = (20, 16)
    code = f"""
import os
import sys
import numpy as np
from clipkit import AudioClip, ColorClip, VideoClip

def tone(t):
    return np.array([0.5 * np.sin(2.0 * np.pi * 440.0 * t)])

duration = 0.4
fps = 10
clip = ColorClip((32, 24), color=(20, 180, 40), duration=duration).with_fps(fps)
audio = AudioClip(frame_function=tone, duration=duration, fps=44100)
clip = clip.with_audio(audio)

mp4_ok = False
try:
    clip.write_videofile("neg.mp4", logger=None)
    mp4_ok = True
except Exception as exc:
    print("MP4_FAIL", type(exc).__name__, str(exc)[:240])
print("MP4_OK", mp4_ok)
print("MP4_SIZE", os.path.getsize("neg.mp4") if os.path.exists("neg.mp4") else "missing")

wav_ok = False
try:
    audio.write_audiofile("neg.wav", logger=None)
    wav_ok = True
except Exception as exc:
    print("WAV_FAIL", type(exc).__name__, str(exc)[:240])
print("WAV_OK", wav_ok)
print("WAV_SIZE", os.path.getsize("neg.wav") if os.path.exists("neg.wav") else "missing")

first = np.asarray({gif_color_a}, dtype=np.uint8)
second = np.asarray({gif_color_b}, dtype=np.uint8)

def gif_fn(t):
    picture = np.empty((24, 32, 3), dtype=np.uint8)
    picture[:, :] = first if float(t) < 0.2 else second
    return picture

gif_clip = VideoClip(frame_function=gif_fn, duration=duration).with_fps(fps)
gif_clip.write_gif("neg.gif", logger=None)
print("GIF_SIZE", os.path.getsize("neg.gif"))

seq = ColorClip({seq_size}, color={seq_color}, duration=0.2).with_fps(10)
os.makedirs("seq", exist_ok=True)
paths = seq.write_images_sequence("seq/frame_%d.png", logger=None)
print("SEQ_PATHS", paths)

still = ColorClip({still_size}, color={still_color})
still.save_frame("still.png")
print("STILL_SIZE", os.path.getsize("still.png"))
print("DONE")
"""
    with workspace() as ws:
        unreachable = ws.run_python(code=code, encoder_reachable=False, timeout=60.0)
        print(
            f"unreachable rc={unreachable.returncode} "
            f"stdout={unreachable.stdout_text!r} stderr={unreachable.stderr_text[:800]!r}",
            flush=True,
        )
        out = unreachable.stdout_text
        if "MP4_OK True" in out:
            raise AssertionError("MP4 write succeeded while the encoder was unreachable")
        if "WAV_OK True" in out:
            raise AssertionError("WAV write succeeded while the encoder was unreachable")
        if "MP4_OK False" not in out:
            raise AssertionError(
                "unreachable subprocess did not report MP4 write failure; "
                f"stdout={out!r}"
            )
        if "WAV_OK False" not in out:
            raise AssertionError(
                "unreachable subprocess did not report WAV write failure; "
                f"stdout={out!r}"
            )
        mp4 = ws.resolve("neg.mp4")
        wav = ws.resolve("neg.wav")
        if mp4.exists() and mp4.is_file() and mp4.stat().st_size == 0:
            print("mp4 leftover is zero bytes; not success", flush=True)
        if wav.exists() and wav.is_file() and wav.stat().st_size == 0:
            print("wav leftover is zero bytes; not success", flush=True)
        gif = ws.resolve("neg.gif")
        media_file_nonempty(gif)
        play = gif_playback_seconds(gif)
        frames = gif_frames_rgba(gif)
        print(f"unreachable gif play={play} frames={len(frames)}", flush=True)
        _assert_close(play, 0.4, slack=0.25, label="unreachable_gif_play")
        if not frames:
            raise AssertionError("unreachable GIF wrote a file that has no frames")
        seq_first = ws.resolve("seq/frame_0.png")
        if not seq_first.exists():
            matches = sorted((ws.resolve("seq")).glob("frame_*.png"))
            if not matches:
                raise AssertionError("unreachable sequence write produced no PNG files")
            seq_first = matches[0]
        media_file_nonempty(seq_first)
        rgb, _alpha = read_png_rgb_and_alpha(seq_first)
        require_rgb_picture(rgb, seq_size[1], seq_size[0], seq_color)
        still = ws.resolve("still.png")
        media_file_nonempty(still)
        still_rgb, _ = read_png_rgb_and_alpha(still)
        require_rgb_picture(still_rgb, still_size[1], still_size[0], still_color)

        reachable_code = """
from clipkit import AudioClip, ColorClip
import numpy as np

def tone(t):
    return np.array([0.5 * np.sin(2.0 * np.pi * 440.0 * t)])

clip = ColorClip((32, 24), color=(20, 180, 40), duration=0.4).with_fps(10)
clip.write_videofile("reach.mp4", logger=None, audio=False)
AudioClip(frame_function=tone, duration=0.4, fps=44100).write_audiofile("reach.wav", logger=None)
print("REACH_OK")
"""
        reachable = ws.run_python(code=reachable_code, encoder_reachable=True, timeout=60.0)
        print(
            f"reachable rc={reachable.returncode} stdout={reachable.stdout_text!r}",
            flush=True,
        )
        assert reachable.returncode == 0
        media_file_nonempty(ws.resolve("reach.mp4"))
        media_file_nonempty(ws.resolve("reach.wav"))
        loaded = _load_video(ws, ws.resolve("reach.mp4"), audio=False)
        try:
            require_rgb_picture(_frame(ws, loaded, 0.0), 24, 32)
        finally:
            _close(ws, loaded)


def test_m4a_defaults_to_aac_encoder():
    with workspace() as ws:
        freq = _tone_hz()
        duration = 0.8
        clip = _tone_clip(ws, freq, duration)
        baseline = ws.resolve("audio_write_baseline.wav")
        _write_audio(ws, clip, baseline)
        _assert_codec_family(
            container_audio_codec(baseline), "pcm_s16le", label="m4a_write_baseline"
        )
        if not ffmpeg_opens_nonempty_media(baseline):
            raise AssertionError(
                "WAV write of the same clip is not nonempty media FFmpeg can open"
            )
        wav_peak = dominant_tone_hz(pcm_from_container(baseline), _PCM_RATE)
        print(f"m4a wav baseline freq={freq} measured={wav_peak}", flush=True)
        assert wav_peak == pytest.approx(freq, rel=0.1, abs=16)

        working = (
            ("mp3", "mp3"),
            ("ogg", "vorbis"),
            ("flac", "flac"),
        )
        for ext, family in working:
            path = ws.resolve(f"audio_write_baseline.{ext}")
            _write_audio(ws, clip, path)
            token = container_audio_codec(path)
            _assert_codec_family(token, family, label=f"m4a_{ext}_baseline")
            if not ffmpeg_opens_nonempty_media(path):
                raise AssertionError(
                    f"{ext} write of the same clip is not nonempty media "
                    "FFmpeg can open"
                )
            peak = dominant_tone_hz(pcm_from_container(path), _PCM_RATE)
            print(
                f"m4a {ext} baseline freq={freq} measured={peak} codec={token}",
                flush=True,
            )
            assert peak == pytest.approx(freq, rel=0.1, abs=16)

        default_path = ws.resolve("audio_default.m4a")
        named_path = ws.resolve("audio_named_default_encoder.m4a")
        default_result = ws.call(clip.write_audiofile, str(default_path), logger=None)
        named_result = ws.call(
            clip.write_audiofile,
            str(named_path),
            codec="libfdk_aac",
            logger=None,
        )
        default_openable = ffmpeg_opens_nonempty_media(default_path)
        named_openable = ffmpeg_opens_nonempty_media(named_path)
        print(
            f"m4a default completed={default_result.exception is None} "
            f"openable={default_openable} named_completed="
            f"{named_result.exception is None} named_openable={named_openable}",
            flush=True,
        )
        if default_result.exception is None:
            print("m4a default write returned as a completed call", flush=True)
        if named_result.exception is None:
            print("m4a named-encoder write returned as a completed call", flush=True)
        if default_openable:
            raise AssertionError(
                "m4a write with no named codec produced nonempty media "
                "FFmpeg can open; that default is the unknown-codec case "
                "and a completed return is not a successful encode"
            )
        if named_openable:
            raise AssertionError(
                "m4a write naming the AAC encoder that extension defaults to "
                "produced nonempty media FFmpeg can open; "
                "a completed return is not a successful encode"
            )
