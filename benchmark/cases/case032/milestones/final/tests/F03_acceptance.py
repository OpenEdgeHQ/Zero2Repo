# feature: F03
"""Load video and audio files (FP-03).

Assertions stay at the PRD's precision: file-backed open matches the
file's video/audio streams, decoder-side named resize, default stereo
44100 decode, close/context-manager release, path refusals that identify
the path, and the unreachable-decoder negative control. Exception types
and failure wording are not pinned.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import numpy as np
import pytest
from clipkit import (
    AudioArrayClip,
    AudioFileClip,
    CompositeVideoClip,
    VideoClip,
    VideoFileClip,
)

from _harness import HarnessError, workspace
from _helpers import (
    as_numeric_array,
    container_audio_duration,
    container_duration,
    container_frame_rate,
    container_has_audio,
    container_playback_frame_rate,
    container_video_size,
    dominant_picture_rgb,
    dominant_tone_hz,
    failure_remainder,
    independent_rgb_frames,
    media_file_nonempty,
    pictures_close_lossy,
    pcm_same_signal,
    require_failed,
    require_ok,
    require_rgb_picture,
    write_independent_audio,
    write_independent_video,
    write_pcm_wav,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

_PCM_RATE = 44100
_ORACLE_DURATION = 5.0
_ORACLE_FPS = 10
_ORACLE_RED = (255, 0, 0)
_ORACLE_BLUE = (0, 0, 255)
_ORACLE_HEIGHT = 128
_MUXER_SLACK = 0.2


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _rect_even_size() -> tuple[int, int]:
    width = _rand_int(10, 18) * 2
    height = _rand_int(8, 14) * 2
    if width == height:
        height = width + 2
    if height == _ORACLE_HEIGHT:
        height = _ORACLE_HEIGHT - 8
    return width, height


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(20, 230), _rand_int(20, 230), _rand_int(20, 230))


def _rgb_away_from(other: tuple[int, int, int]) -> tuple[int, int, int]:
    for _ in range(24):
        candidate = _rgb()
        if _rgb_dist(candidate, other) > 90:
            return candidate
    return (255 - other[0], 255 - other[1], 255 - other[2])


def _tone_hz() -> float:
    return float(_rand_int(310, 720))


def _rgb_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum(abs(x - y) for x, y in zip(a, b))


def _clip_size(clip) -> tuple[int, int]:
    size = clip.size
    return (int(size[0]), int(size[1]))


def _split_fn(height: int, width: int, first, second, split: float):
    first_a = np.asarray(first, dtype=np.uint8)
    second_a = np.asarray(second, dtype=np.uint8)

    def frame_function(t):
        picture = np.empty((height, width, 3), dtype=np.uint8)
        picture[:, :] = first_a if t < split else second_a
        return picture

    return frame_function


def _split_pictures(height, width, first, second, duration, fps):
    count = max(2, int(round(duration * fps)))
    split = duration / 2.0
    first_a = np.asarray(first, dtype=np.uint8)
    second_a = np.asarray(second, dtype=np.uint8)
    pictures = []
    for index in range(count):
        t = index / float(fps)
        picture = np.empty((height, width, 3), dtype=np.uint8)
        picture[:, :] = first_a if t < split else second_a
        pictures.append(picture)
    return pictures


def _tone_stereo(freq: float, duration: float, rate: int) -> np.ndarray:
    n = int(round(duration * rate))
    if n < 32:
        raise HarnessError(f"tone array too short: n={n}")
    t = np.arange(n, dtype=float) / float(rate)
    left = 0.45 * np.sin(2.0 * np.pi * freq * t)
    right = 0.35 * np.sin(2.0 * np.pi * freq * t + 0.6)
    return np.column_stack([left, right])


def _tone_mono(freq: float, duration: float, rate: int) -> np.ndarray:
    n = int(round(duration * rate))
    if n < 32:
        raise HarnessError(f"tone array too short: n={n}")
    t = np.arange(n, dtype=float) / float(rate)
    return (0.5 * np.sin(2.0 * np.pi * freq * t)).reshape(n, 1)


def _write_product_mp4(ws, path: Path, height, width, first, second, duration, fps):
    fn = _split_fn(height, width, first, second, duration / 2.0)
    clip = require_ok(ws.call(VideoClip, frame_function=fn, duration=duration))
    clip = require_ok(ws.call(clip.with_fps, fps))
    require_ok(ws.call(clip.write_videofile, str(path), logger=None, audio=False))
    media_file_nonempty(path)
    return path


def _open_video(ws, path: Path, **kwargs):
    return require_ok(ws.call(VideoFileClip, str(path), **kwargs))


def _open_audio(ws, path: Path, **kwargs):
    return require_ok(ws.call(AudioFileClip, str(path), **kwargs))


def _frame(ws, clip, t):
    return require_ok(ws.call(clip.get_frame, t))


def _decode_times(clip):
    """Sample times at the clip's decode rate, strictly before duration.

    The file decoder refuses t == duration; a default conversion that
    lands on that endpoint is not a usable observation.
    """
    try:
        duration = float(clip.duration)
        fps = float(clip.fps)
    except (TypeError, ValueError) as exc:
        raise AssertionError(
            f"clip duration/fps are not numeric: duration={clip.duration!r} "
            f"fps={getattr(clip, 'fps', None)!r}: {exc}"
        ) from exc
    if duration <= 0 or fps <= 0:
        raise AssertionError(
            f"need positive duration and decode rate; duration={duration} fps={fps}"
        )
    n = max(32, int(np.floor(duration * fps)))
    times = np.arange(n, dtype=float) / fps
    times = times[times < duration]
    if times.size < 32:
        raise AssertionError(
            f"not enough in-range sample times; n={times.size} "
            f"duration={duration} fps={fps}"
        )
    return times, fps


def _sound_array(ws, clip, times=None, fps=None):
    if times is None or fps is None:
        times, fps = _decode_times(clip)

    def _convert(target, sample_times, sample_rate):
        # Scalar times: a vector of times is converted-to-seconds as a
        # clock tuple and collapses to t == duration, which the decoder
        # refuses. Asking for each t separately is the public get-frame
        # path at the decode rate.
        rows = []
        for t in sample_times:
            row = np.asarray(target.get_frame(float(t)), dtype=float)
            rows.append(np.atleast_1d(row).reshape(-1))
        return np.vstack(rows)

    print(
        f"decode times n={times.size} first={times[0]} last={times[-1]} fps={fps}",
        flush=True,
    )
    return as_numeric_array(require_ok(ws.call(_convert, clip, times, fps)))


def _close(ws, clip):
    require_ok(ws.call(clip.close))


def _assert_duration_close(got, expected, *, slack=_MUXER_SLACK, label="duration"):
    print(f"{label} got={got} expected={expected} slack={slack}", flush=True)
    try:
        value = float(got)
        target = float(expected)
    except (TypeError, ValueError) as exc:
        raise AssertionError(
            f"{label} is not numeric: got={got!r} expected={expected!r}: {exc}"
        ) from exc
    if abs(value - target) > slack:
        raise AssertionError(
            f"{label} {value} is not within {slack} of {target}"
        )


def _assert_matches_video_stream(clip, path: Path, *, slack=_MUXER_SLACK, fps_slack=None):
    file_duration = container_duration(path)
    file_fps = container_playback_frame_rate(path)
    file_size = container_video_size(path)
    print(
        f"file duration={file_duration} fps={file_fps} size={file_size} "
        f"clip duration={clip.duration} fps={clip.fps} size={_clip_size(clip)}",
        flush=True,
    )
    _assert_duration_close(clip.duration, file_duration, slack=slack)
    if fps_slack is None:
        fps_slack = (0.05, 0.2)
    rel, abs_ = fps_slack
    got_fps = float(clip.fps)
    if abs(got_fps - file_fps) > max(abs_, rel * file_fps):
        raise AssertionError(
            f"clip fps {got_fps} is not within rel={rel} abs={abs_} of file fps {file_fps}"
        )
    if _clip_size(clip) != file_size:
        raise AssertionError(
            f"clip size {_clip_size(clip)} does not match file stream {file_size}"
        )
    return file_duration, file_fps, file_size


def _assert_halves(
    ws,
    clip,
    first,
    second,
    duration,
    *,
    near=55,
    gif=False,
    lossy=False,
    t1=None,
    t2=None,
):
    if t1 is None:
        t1 = duration * 0.25
    if t2 is None:
        t2 = duration * 0.75
    picture1 = _frame(ws, clip, t1)
    picture2 = _frame(ws, clip, t2)
    width, height = _clip_size(clip)
    require_rgb_picture(picture1, height, width)
    require_rgb_picture(picture2, height, width)
    limit = 110 if (gif or lossy) else near
    c1 = dominant_picture_rgb(picture1)
    c2 = dominant_picture_rgb(picture2)
    print(
        f"t={t1} dominant={c1} first={first} second={second}; "
        f"t={t2} dominant={c2} limit={limit}",
        flush=True,
    )
    if _rgb_dist(c1, first) > limit:
        raise AssertionError(
            f"first-half colour {c1} is not near written {first}; dist={_rgb_dist(c1, first)} limit={limit}"
        )
    if _rgb_dist(c1, first) >= _rgb_dist(c1, second):
        raise AssertionError(
            f"first-half colour {c1} is not closer to {first} than to {second}"
        )
    if _rgb_dist(c2, second) > limit:
        raise AssertionError(
            f"second-half colour {c2} is not near written {second}; dist={_rgb_dist(c2, second)} limit={limit}"
        )
    if _rgb_dist(c2, second) >= _rgb_dist(c2, first):
        raise AssertionError(
            f"second-half colour {c2} is not closer to {second} than to {first}"
        )
    if pictures_close_lossy(picture1, picture2) is True:
        raise AssertionError("the two halves produced the same picture")


def _assert_open_failed(result):
    require_failed(result)
    if not (result.value is None):
        raise AssertionError('result.value is None')
    return result


def _assert_identifies_path(result, path: Path, *other_covariates):
    rest = failure_remainder(result, *other_covariates)
    folded = rest.casefold()
    name = path.name
    full = str(path)
    if name.casefold() not in folded and full.casefold() not in folded:
        raise AssertionError(
            "caller-visible failure does not identify the offending path; "
            f"path={path!s} remainder={rest!r}"
        )
    return rest


def _assert_stereo_tone(array, freq: float, rate: float, duration: float):
    arr = as_numeric_array(array).astype(float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    peak_amp = float(np.max(np.abs(arr))) if arr.size else 0.0
    print(
        f"sound_array shape={arr.shape} rate={rate} duration={duration} "
        f"peak_amp={peak_amp}",
        flush=True,
    )
    if arr.ndim != 2:
        raise AssertionError(f"decoded sound is not 2-D; shape={arr.shape}")
    if arr.shape[1] != 2:
        raise AssertionError(f"decoded sound is not stereo; shape={arr.shape}")
    expected = duration * rate
    slack = max(64.0, 0.08 * expected)
    if abs(arr.shape[0] - expected) > slack:
        raise AssertionError(
            f"sample count {arr.shape[0]} is not about duration×rate={expected}"
        )
    if peak_amp <= 0.02:
        raise AssertionError(f"decoded sound is silent; peak_amp={peak_amp}")
    # One channel: flattening stereo L/R interleave is not a tone at `rate`.
    peak = dominant_tone_hz(arr[:, 0], rate)
    print(f"requested_hz={freq} measured_hz={peak}", flush=True)
    if abs(peak - freq) > max(16.0, 0.08 * freq):
        raise AssertionError(
            f"dominant tone {peak} Hz is not the written {freq} Hz"
        )


# ---------------------------------------------------------------------------
# A. Open a decodable video: duration, rate, size, picture at t
# ---------------------------------------------------------------------------


def test_oracle_mp4_five_seconds_ten_fps_red_then_blue():
    width, height = 32, 24
    with workspace() as ws:
        path = ws.resolve("oracle.mp4")
        _write_product_mp4(
            ws, path, height, width, _ORACLE_RED, _ORACLE_BLUE, _ORACLE_DURATION, _ORACLE_FPS
        )
        clip = _open_video(ws, path)
        file_duration, file_fps, file_size = _assert_matches_video_stream(clip, path)
        _assert_duration_close(clip.duration, _ORACLE_DURATION)
        _assert_duration_close(file_duration, _ORACLE_DURATION)
        if not (clip.fps == pytest.approx(_ORACLE_FPS, abs=0.05)):
            raise AssertionError('clip.fps == pytest.approx(_ORACLE_FPS, abs=0.05)')
        if not (file_fps == pytest.approx(_ORACLE_FPS, abs=0.05)):
            raise AssertionError('file_fps == pytest.approx(_ORACLE_FPS, abs=0.05)')
        if not (file_size == (width, height)):
            raise AssertionError('file_size == (width, height)')
        if not (_clip_size(clip) == (width, height)):
            raise AssertionError('_clip_size(clip) == (width, height)')
        frame = _frame(ws, clip, 0.0)
        require_rgb_picture(frame, height, width)
        _assert_halves(ws, clip, _ORACLE_RED, _ORACLE_BLUE, _ORACLE_DURATION)
        _close(ws, clip)


def test_loaded_clip_matches_file_stream_runtime():
    width, height = _rect_even_size()
    duration = 0.4 + _rand_int(0, 3) * 0.1
    fps = float(_rand_int(8, 12))
    first, second = _rgb(), None
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("runtime.mp4")
        pictures = _split_pictures(height, width, first, second, duration, fps)
        write_independent_video(
            path,
            pictures,
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        clip = _open_video(ws, path)
        _assert_matches_video_stream(clip, path)
        if not (_clip_size(clip)[0] != _clip_size(clip)[1]):
            raise AssertionError('_clip_size(clip)[0] != _clip_size(clip)[1]')
        frame = _frame(ws, clip, 0.0)
        require_rgb_picture(frame, height, width)
        if not (frame.shape[0] == height and frame.shape[1] == width):
            raise AssertionError('frame.shape[0] == height and frame.shape[1] == width')
        _assert_halves(ws, clip, first, second, duration)
        _close(ws, clip)


_NAMED_VIDEO = [
    pytest.param(
        ".mp4",
        ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        id="mp4",
    ),
    pytest.param(
        ".webm",
        ["-c:v", "libvpx", "-b:v", "256k", "-auto-alt-ref", "0", "-an"],
        id="webm",
    ),
    pytest.param(
        ".mov",
        ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        id="mov",
    ),
    pytest.param(
        ".avi",
        ["-c:v", "mpeg4", "-qscale:v", "5", "-an"],
        id="avi",
    ),
    pytest.param(
        ".mpeg",
        [
            "-c:v",
            "mpeg2video",
            "-qscale:v",
            "2",
            "-g",
            "1",
            "-bf",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-an",
        ],
        id="mpeg",
    ),
    pytest.param(
        ".ogv",
        ["-c:v", "libtheora", "-qscale:v", "10", "-pix_fmt", "yuv420p", "-an"],
        id="ogv",
    ),
    pytest.param(
        ".gif",
        [
            "-filter_complex",
            "[0:v]split[a][b];"
            "[a]palettegen=max_colors=16:reserve_transparent=0[p];"
            "[b][p]paletteuse=dither=none",
            "-an",
        ],
        id="gif",
    ),
]


def test_load_reads_this_file_not_a_placeholder():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first_a = _rgb()
    second_a = _rgb_away_from(first_a)
    first_b = _rgb_away_from(first_a)
    second_b = _rgb_away_from(first_b)
    with workspace() as ws:
        path = ws.resolve("rewritten.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first_a, second_a, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        clip_a = _open_video(ws, path)
        _assert_halves(ws, clip_a, first_a, second_a, duration)
        _close(ws, clip_a)
        write_independent_video(
            path,
            _split_pictures(height, width, first_b, second_b, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        clip_b = _open_video(ws, path)
        _assert_halves(ws, clip_b, first_b, second_b, duration)
        t1 = duration * 0.25
        picture = _frame(ws, clip_b, t1)
        color = dominant_picture_rgb(picture)
        if not (_rgb_dist(color, first_b) < _rgb_dist(color, first_a)):
            raise AssertionError('_rgb_dist(color, first_b) < _rgb_dist(color, first_a)')
        _close(ws, clip_b)


# ---------------------------------------------------------------------------
# B. Soundtrack on by default; off has none; picture still from the file
# ---------------------------------------------------------------------------


def test_video_with_audio_carries_soundtrack_by_default():
    width, height = _rect_even_size()
    video_duration = 0.4
    audio_duration = 1.2
    fps = 10.0
    freq = _tone_hz()
    first = _rgb()
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("av_mismatch.mkv")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, video_duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p"],
            audio_pcm=_tone_stereo(freq, audio_duration, _PCM_RATE),
            audio_sample_rate=_PCM_RATE,
        )
        if not (container_has_audio(path) is True):
            raise AssertionError('container_has_audio(path) is True')
        video_d = container_duration(path)
        audio_d = container_audio_duration(path)
        print(f"probe video_d={video_d} audio_d={audio_d}", flush=True)
        if not (abs(audio_d - video_d) > 0.15):
            raise AssertionError('abs(audio_d - video_d) > 0.15')
        clip = _open_video(ws, path)
        if not (clip.audio is not None):
            raise AssertionError('clip.audio is not None')
        _assert_duration_close(clip.audio.duration, audio_d, label="soundtrack")
        if not (abs(clip.audio.duration - audio_d) < abs(clip.audio.duration - video_d)):
            raise AssertionError('abs(clip.audio.duration - audio_d) < abs(clip.audio.duration - video_d)')
        samples = _sound_array(ws, clip.audio)
        peak = dominant_tone_hz(as_numeric_array(samples)[:, 0], _PCM_RATE)
        print(f"requested_hz={freq} soundtrack_hz={peak}", flush=True)
        if abs(peak - freq) > max(16.0, 0.08 * freq):
            raise AssertionError(
                f"soundtrack tone {peak} Hz is not the written {freq} Hz"
            )
        _close(ws, clip)


def test_video_audio_off_has_no_soundtrack():
    width, height = _rect_even_size()
    video_duration = 0.4
    audio_duration = 1.0
    fps = 10.0
    freq = _tone_hz()
    first = _rgb()
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("av_off.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, video_duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p"],
            audio_pcm=_tone_stereo(freq, audio_duration, _PCM_RATE),
            audio_sample_rate=_PCM_RATE,
        )
        if not (container_has_audio(path) is True):
            raise AssertionError('container_has_audio(path) is True')
        on = _open_video(ws, path)
        if not (on.audio is not None):
            raise AssertionError('on.audio is not None')
        baseline = _frame(ws, on, video_duration * 0.25)
        off = _open_video(ws, path, audio=False)
        print(f"off.audio={off.audio!r}", flush=True)
        if not (off.audio is None):
            raise AssertionError('off.audio is None')
        picture = _frame(ws, off, video_duration * 0.25)
        require_rgb_picture(picture, height, width)
        color = dominant_picture_rgb(picture)
        base_color = dominant_picture_rgb(baseline)
        print(f"off_color={color} on_color={base_color} first={first}", flush=True)
        if not (_rgb_dist(color, first) <= 55):
            raise AssertionError('_rgb_dist(color, first) <= 55')
        if not (pictures_close_lossy(picture, baseline, mean_atol=20.0)):
            raise AssertionError('pictures_close_lossy(picture, baseline, mean_atol=20.0)')
        _assert_halves(ws, off, first, second, video_duration)
        _close(ws, on)
        _close(ws, off)


# ---------------------------------------------------------------------------
# C. Open a decodable audio file
# ---------------------------------------------------------------------------


def test_oracle_stereo_wav_44100_roundtrip():
    freq = _tone_hz()
    duration = 1.0
    samples = _tone_stereo(freq, duration, _PCM_RATE)
    with workspace() as ws:
        path = ws.resolve("oracle.wav")
        write_pcm_wav(path, samples, _PCM_RATE)
        clip = _open_audio(ws, path)
        file_d = container_audio_duration(path)
        _assert_duration_close(clip.duration, file_d, slack=_MUXER_SLACK)
        _assert_duration_close(clip.duration, duration, slack=_MUXER_SLACK)
        got = _sound_array(ws, clip)
        _assert_stereo_tone(got, freq, _PCM_RATE, duration)
        if not pcm_same_signal(got, samples):
            raise AssertionError(
                "decoded WAV does not carry the written stereo waveform"
            )
        _close(ws, clip)


def test_default_decode_rate_is_44100_not_source_rate():
    freq = _tone_hz()
    duration = 1.0
    source_rate = 22050
    samples = _tone_stereo(freq, duration, source_rate)
    with workspace() as ws:
        path = ws.resolve("rate_22050.wav")
        write_pcm_wav(path, samples, source_rate)
        clip = _open_audio(ws, path)
        file_d = container_audio_duration(path)
        _assert_duration_close(clip.duration, file_d, slack=_MUXER_SLACK)
        got = _sound_array(ws, clip)
        n_src = duration * source_rate
        n_default = duration * _PCM_RATE
        print(f"decoded_n={got.shape[0]} src_n={n_src} default_n={n_default}", flush=True)
        if abs(got.shape[0] - n_default) > max(200.0, 0.08 * n_default):
            raise AssertionError(
                f"decoded sample count {got.shape[0]} is not about {n_default} at 44100"
            )
        if abs(got.shape[0] - n_src) <= abs(got.shape[0] - n_default):
            raise AssertionError(
                f"decoded sample count {got.shape[0]} follows source rate {n_src}, not 44100"
            )
        _assert_stereo_tone(got, freq, _PCM_RATE, duration)
        _close(ws, clip)


def test_named_decode_rate_is_used():
    freq = _tone_hz()
    duration = 1.0
    samples = _tone_stereo(freq, duration, _PCM_RATE)
    named_rate = 22050
    with workspace() as ws:
        path = ws.resolve("named_rate.wav")
        write_pcm_wav(path, samples, _PCM_RATE)
        clip = _open_audio(ws, path, fps=named_rate)
        file_d = container_audio_duration(path)
        _assert_duration_close(clip.duration, file_d, slack=_MUXER_SLACK)
        got = _sound_array(ws, clip)
        _assert_stereo_tone(got, freq, named_rate, duration)
        _close(ws, clip)


_NAMED_AUDIO = [
    pytest.param(".wav", None, False, id="wav"),
    pytest.param(".mp3", ["-c:a", "libmp3lame", "-q:a", "4"], True, id="mp3"),
    pytest.param(".ogg", ["-c:a", "libvorbis", "-q:a", "4"], True, id="ogg"),
    pytest.param(".flac", ["-c:a", "flac"], False, id="flac"),
]


@pytest.mark.parametrize("ext,ffmpeg_args,lossy", _NAMED_AUDIO)
def test_load_named_audio_formats(ext, ffmpeg_args, lossy):
    freq = _tone_hz()
    duration = 1.0
    samples = _tone_stereo(freq, duration, _PCM_RATE)
    with workspace() as ws:
        path = ws.resolve(f"named{ext}")
        write_independent_audio(path, samples, _PCM_RATE, ffmpeg_args=ffmpeg_args)
        clip = _open_audio(ws, path)
        file_d = container_audio_duration(path)
        _assert_duration_close(clip.duration, file_d, slack=0.12)
        got = _sound_array(ws, clip)
        _assert_stereo_tone(got, freq, _PCM_RATE, duration)
        if not lossy:
            if not pcm_same_signal(got, samples):
                raise AssertionError(
                    f"{ext} decode does not carry the written waveform"
                )
        _close(ws, clip)


def test_audio_clip_from_video_container():
    width, height = _rect_even_size()
    duration = 0.8
    fps = 10.0
    freq = _tone_hz()
    first = _rgb()
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("video_as_audio.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p"],
            audio_pcm=_tone_stereo(freq, duration, _PCM_RATE),
            audio_sample_rate=_PCM_RATE,
        )
        clip = _open_audio(ws, path)
        file_d = container_audio_duration(path)
        _assert_duration_close(clip.duration, file_d, slack=0.15)
        got = _sound_array(ws, clip)
        _assert_stereo_tone(got, freq, _PCM_RATE, clip.duration)
        _close(ws, clip)


def test_mono_source_decodes_stereo():
    freq = _tone_hz()
    duration = 1.0
    samples = _tone_mono(freq, duration, _PCM_RATE)
    with workspace() as ws:
        path = ws.resolve("mono.wav")
        write_pcm_wav(path, samples, _PCM_RATE)
        clip = _open_audio(ws, path)
        got = _sound_array(ws, clip)
        _assert_stereo_tone(got, freq, _PCM_RATE, duration)
        _close(ws, clip)


# ---------------------------------------------------------------------------
# D. Named target width and/or height while reading
# ---------------------------------------------------------------------------


def _aspect_other(named: int, src_named: int, src_other: int) -> float:
    return named * (src_other / src_named)


def test_oracle_target_height_128():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("scale_h128.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        file_size = container_video_size(path)
        src_w, src_h = file_size
        if not (src_w != src_h):
            raise AssertionError('src_w != src_h')
        if not (src_h != _ORACLE_HEIGHT):
            raise AssertionError('src_h != _ORACLE_HEIGHT')
        clip = _open_video(ws, path, target_resolution=(None, _ORACLE_HEIGHT))
        got_w, got_h = _clip_size(clip)
        frame = _frame(ws, clip, 0.1)
        require_rgb_picture(frame, got_h, got_w)
        print(
            f"src={file_size} named_h={_ORACLE_HEIGHT} got=({got_w},{got_h}) "
            f"frame={frame.shape}",
            flush=True,
        )
        if not (got_h == _ORACLE_HEIGHT):
            raise AssertionError('got_h == _ORACLE_HEIGHT')
        if not (frame.shape[0] == _ORACLE_HEIGHT):
            raise AssertionError('frame.shape[0] == _ORACLE_HEIGHT')
        expected_w = _aspect_other(_ORACLE_HEIGHT, src_h, src_w)
        if not (abs(got_w - expected_w) <= 1.5):
            raise AssertionError('abs(got_w - expected_w) <= 1.5')
        if not (got_w != src_w):
            raise AssertionError('got_w != src_w')
        _close(ws, clip)


def test_named_width_keeps_aspect():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    target_w = 64 if width != 64 else 48
    with workspace() as ws:
        path = ws.resolve("scale_w.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, _rgb_away_from(first), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        src_w, src_h = container_video_size(path)
        clip = _open_video(ws, path, target_resolution=(target_w, None))
        got_w, got_h = _clip_size(clip)
        frame = _frame(ws, clip, 0.1)
        require_rgb_picture(frame, got_h, got_w)
        print(f"src=({src_w},{src_h}) named_w={target_w} got=({got_w},{got_h})", flush=True)
        if not (got_w == target_w):
            raise AssertionError('got_w == target_w')
        if not (frame.shape[1] == target_w):
            raise AssertionError('frame.shape[1] == target_w')
        expected_h = _aspect_other(target_w, src_w, src_h)
        if not (abs(got_h - expected_h) <= 1.5):
            raise AssertionError('abs(got_h - expected_h) <= 1.5')
        _close(ws, clip)


def test_named_height_keeps_aspect_runtime():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    target_h = 64
    if target_h == height:
        target_h = 48
    with workspace() as ws:
        path = ws.resolve("scale_h_runtime.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, _rgb_away_from(first), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        src_w, src_h = container_video_size(path)
        if not (src_h != target_h):
            raise AssertionError('src_h != target_h')
        clip = _open_video(ws, path, target_resolution=(None, target_h))
        got_w, got_h = _clip_size(clip)
        frame = _frame(ws, clip, 0.1)
        require_rgb_picture(frame, got_h, got_w)
        print(f"src=({src_w},{src_h}) named_h={target_h} got=({got_w},{got_h})", flush=True)
        if not (got_h == target_h):
            raise AssertionError('got_h == target_h')
        expected_w = _aspect_other(target_h, src_h, src_w)
        if not (abs(got_w - expected_w) <= 1.5):
            raise AssertionError('abs(got_w - expected_w) <= 1.5')
        _close(ws, clip)


def test_both_dimensions_named():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    target_w, target_h = 40, 80
    with workspace() as ws:
        path = ws.resolve("scale_both.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, _rgb_away_from(first), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        src_w, src_h = container_video_size(path)
        if not (abs(target_w / target_h - src_w / src_h) > 0.2):
            raise AssertionError('abs(target_w / target_h - src_w / src_h) > 0.2')
        clip = _open_video(ws, path, target_resolution=(target_w, target_h))
        got_w, got_h = _clip_size(clip)
        frame = _frame(ws, clip, 0.1)
        require_rgb_picture(frame, got_h, got_w)
        print(f"src=({src_w},{src_h}) named=({target_w},{target_h}) got=({got_w},{got_h})", flush=True)
        if not ((got_w, got_h) == (target_w, target_h)):
            raise AssertionError('(got_w, got_h) == (target_w, target_h)')
        if not (frame.shape[0] == target_h and frame.shape[1] == target_w):
            raise AssertionError('frame.shape[0] == target_h and frame.shape[1] == target_w')
        _close(ws, clip)


def test_no_target_keeps_file_size():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    with workspace() as ws:
        path = ws.resolve("scale_none.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, _rgb_away_from(first), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        file_size = container_video_size(path)
        clip = _open_video(ws, path)
        got = _clip_size(clip)
        frame = _frame(ws, clip, 0.1)
        require_rgb_picture(frame, got[1], got[0])
        print(f"file_size={file_size} clip_size={got} frame={frame.shape}", flush=True)
        if not (got == file_size):
            raise AssertionError('got == file_size')
        if not (frame.shape[0] == file_size[1] and frame.shape[1] == file_size[0]):
            raise AssertionError('frame.shape[0] == file_size[1] and frame.shape[1] == file_size[0]')
        _close(ws, clip)


# ---------------------------------------------------------------------------
# E. Copy-on-modify keeps file geometry and encode defaults
# ---------------------------------------------------------------------------


def test_copy_on_modify_keeps_file_geometry_and_encode_defaults():
    width, height = _rect_even_size()
    duration = 0.5
    fps = float(_rand_int(8, 12))
    first = _rgb()
    freq = _tone_hz()
    with workspace() as ws:
        path = ws.resolve("com_src.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, _rgb_away_from(first), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        loaded = _open_video(ws, path)
        file_duration, file_fps, file_size = _assert_matches_video_stream(loaded, path)
        orig_duration, orig_fps, orig_size = loaded.duration, loaded.fps, _clip_size(loaded)
        orig_audio = loaded.audio
        tone = _tone_stereo(freq, duration, _PCM_RATE)
        soundtrack = require_ok(ws.call(AudioArrayClip, tone, _PCM_RATE))
        modified = require_ok(ws.call(loaded.with_audio, soundtrack))
        print(
            f"orig=({orig_duration},{orig_fps},{orig_size}) "
            f"mod=({modified.duration},{modified.fps},{_clip_size(modified)})",
            flush=True,
        )
        if not (modified is not loaded):
            raise AssertionError('modified is not loaded')
        if not (loaded.duration == orig_duration):
            raise AssertionError('loaded.duration == orig_duration')
        if not (loaded.fps == orig_fps):
            raise AssertionError('loaded.fps == orig_fps')
        if not (_clip_size(loaded) == orig_size):
            raise AssertionError('_clip_size(loaded) == orig_size')
        if not (loaded.audio is orig_audio):
            raise AssertionError('loaded.audio is orig_audio')
        _assert_duration_close(modified.duration, file_duration)
        if not (modified.fps == pytest.approx(file_fps, rel=0.05, abs=0.2)):
            raise AssertionError('modified.fps == pytest.approx(file_fps, rel=0.05, abs=0.2)')
        if not (_clip_size(modified) == file_size):
            raise AssertionError('_clip_size(modified) == file_size')
        out = ws.resolve("com_out.mp4")
        require_ok(ws.call(modified.write_videofile, str(out), logger=None))
        media_file_nonempty(out)
        out_duration = container_duration(out)
        out_fps = container_frame_rate(out)
        out_size = container_video_size(out)
        print(
            f"written duration={out_duration} fps={out_fps} size={out_size}",
            flush=True,
        )
        _assert_duration_close(out_duration, file_duration)
        if not (out_fps == pytest.approx(file_fps, rel=0.05, abs=0.2)):
            raise AssertionError('out_fps == pytest.approx(file_fps, rel=0.05, abs=0.2)')
        if not (out_size == file_size):
            raise AssertionError('out_size == file_size')
        _close(ws, loaded)
        _close(ws, modified)


# ---------------------------------------------------------------------------
# F. Close and context manager; derived clips that still need the file;
# closing a composition does not close sources
# ---------------------------------------------------------------------------


def test_explicit_close_then_frame_does_not_succeed():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve("close_video.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        clip = _open_video(ws, path)
        before = _frame(ws, clip, duration * 0.25)
        require_rgb_picture(before, height, width)
        if not (_rgb_dist(dominant_picture_rgb(before), first) <= 55):
            raise AssertionError('_rgb_dist(dominant_picture_rgb(before), first) <= 55')
        _close(ws, clip)
        failed = ws.call(clip.get_frame, duration * 0.25)
        print(f"after_close={type(failed.exception).__name__}: {failed.exception}", flush=True)
        require_failed(failed)


def test_explicit_close_audio_then_convert_does_not_succeed():
    freq = _tone_hz()
    duration = 0.5
    samples = _tone_stereo(freq, duration, _PCM_RATE)
    with workspace() as ws:
        path = ws.resolve("close_audio.wav")
        write_pcm_wav(path, samples, _PCM_RATE)
        clip = _open_audio(ws, path)
        times, fps = _decode_times(clip)
        before = _sound_array(ws, clip, times, fps)
        _assert_stereo_tone(before, freq, _PCM_RATE, duration)
        _close(ws, clip)
        failed = ws.call(clip.get_frame, float(times[len(times) // 4]))
        print(f"after_close={type(failed.exception).__name__}: {failed.exception}", flush=True)
        require_failed(failed)


def test_context_manager_exit_then_frame_does_not_succeed():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    second = _rgb_away_from(first)

    def _in_block(path, t):
        with VideoFileClip(path) as clip:
            frame = clip.get_frame(t)
            return clip, frame

    with workspace() as ws:
        path = ws.resolve("with_video.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        t = duration * 0.25
        clip, frame = require_ok(ws.call(_in_block, str(path), t))
        require_rgb_picture(frame, height, width)
        if not (_rgb_dist(dominant_picture_rgb(frame), first) <= 55):
            raise AssertionError('_rgb_dist(dominant_picture_rgb(frame), first) <= 55')
        failed = ws.call(clip.get_frame, t)
        print(f"after_with={type(failed.exception).__name__}: {failed.exception}", flush=True)
        require_failed(failed)


def test_audio_context_manager_exit_then_convert_does_not_succeed():
    freq = _tone_hz()
    duration = 0.5
    samples = _tone_stereo(freq, duration, _PCM_RATE)

    def _in_block(path):
        with AudioFileClip(path) as clip:
            duration = float(clip.duration)
            fps = float(clip.fps)
            n = max(32, int(np.floor(duration * fps)))
            times = np.arange(n, dtype=float) / fps
            times = times[times < duration]
            rows = [np.asarray(clip.get_frame(float(t)), dtype=float) for t in times]
            array = np.vstack(rows)
            return clip, array, times, fps

    with workspace() as ws:
        path = ws.resolve("with_audio.wav")
        write_pcm_wav(path, samples, _PCM_RATE)
        clip, array, times, fps = require_ok(ws.call(_in_block, str(path)))
        _assert_stereo_tone(array, freq, _PCM_RATE, duration)
        failed = ws.call(clip.get_frame, float(times[len(times) // 4]))
        print(f"after_with={type(failed.exception).__name__}: {failed.exception}", flush=True)
        require_failed(failed)


def test_derived_clip_that_still_needs_the_file_fails_after_source_close():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first = _rgb()
    second = _rgb_away_from(first)
    freq = _tone_hz()
    with workspace() as ws:
        path = ws.resolve("derived_needs_file.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        source = _open_video(ws, path)
        soundtrack = require_ok(
            ws.call(AudioArrayClip, _tone_stereo(freq, duration, _PCM_RATE), _PCM_RATE)
        )
        derived = require_ok(ws.call(source.with_audio, soundtrack))
        if not (derived is not source):
            raise AssertionError("derived is not source")
        t = duration * 0.25
        before = _frame(ws, derived, t)
        require_rgb_picture(before, height, width)
        before_color = dominant_picture_rgb(before)
        print(
            f"derived_before color={before_color} first={first} "
            f"source_id={id(source)} derived_id={id(derived)}",
            flush=True,
        )
        if not (_rgb_dist(before_color, first) <= 55):
            raise AssertionError("_rgb_dist(before_color, first) <= 55")
        _close(ws, source)
        failed = ws.call(derived.get_frame, t)
        print(
            f"derived_after_source_close={type(failed.exception).__name__}: "
            f"{failed.exception}",
            flush=True,
        )
        require_failed(failed)


def test_closing_composition_does_not_close_sources():
    width, height = _rect_even_size()
    duration = 0.4
    fps = 8.0
    first_a = _rgb()
    first_b = _rgb_away_from(first_a)
    with workspace() as ws:
        path_a = ws.resolve("comp_a.mp4")
        path_b = ws.resolve("comp_b.mp4")
        write_independent_video(
            path_a,
            _split_pictures(height, width, first_a, _rgb_away_from(first_a), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        write_independent_video(
            path_b,
            _split_pictures(height, width, first_b, _rgb_away_from(first_b), duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        src_a = _open_video(ws, path_a)
        src_b = _open_video(ws, path_b)
        composition = require_ok(ws.call(CompositeVideoClip, [src_a, src_b]))
        require_ok(ws.call(composition.close))
        still_a = _frame(ws, src_a, duration * 0.25)
        still_b = _frame(ws, src_b, duration * 0.25)
        require_rgb_picture(still_a, height, width)
        require_rgb_picture(still_b, height, width)
        print(
            f"after_comp_close a={dominant_picture_rgb(still_a)} "
            f"b={dominant_picture_rgb(still_b)}",
            flush=True,
        )
        if not (_rgb_dist(dominant_picture_rgb(still_a), first_a) <= 55):
            raise AssertionError('_rgb_dist(dominant_picture_rgb(still_a), first_a) <= 55')
        if not (_rgb_dist(dominant_picture_rgb(still_b), first_b) <= 55):
            raise AssertionError('_rgb_dist(dominant_picture_rgb(still_b), first_b) <= 55')
        _close(ws, src_a)
        failed = ws.call(src_a.get_frame, duration * 0.25)
        require_failed(failed)
        _close(ws, src_b)


# ---------------------------------------------------------------------------
# G. Missing path, directory, non-media, unparsable video
# ---------------------------------------------------------------------------


def _sibling_video(ws, stem: str) -> Path:
    width, height = 24, 16
    path = ws.resolve(f"{stem}.mp4")
    write_independent_video(
        path,
        _split_pictures(height, width, (20, 180, 40), (40, 40, 200), 0.3, 8.0),
        8.0,
        ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
    )
    return path


def _sibling_audio(ws, stem: str) -> Path:
    path = ws.resolve(f"{stem}.wav")
    write_pcm_wav(path, _tone_stereo(440.0, 0.4, _PCM_RATE), _PCM_RATE)
    return path


def test_missing_path_does_not_succeed_and_identifies_path():
    with workspace() as ws:
        sibling = _sibling_video(ws, "present_video")
        good = _open_video(ws, sibling)
        _frame(ws, good, 0.05)
        _close(ws, good)
        missing_a = ws.resolve("absent_one.mp4")
        missing_b = ws.resolve("absent_two.mp4")
        failed_a = ws.call(VideoFileClip, str(missing_a))
        failed_b = ws.call(VideoFileClip, str(missing_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, missing_a)
        rest_b = _assert_identifies_path(failed_b, missing_b)
        print(f"missing_a={rest_a!r} missing_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')


def test_directory_path_does_not_succeed():
    with workspace() as ws:
        sibling = _sibling_video(ws, "dir_sibling")
        good = _open_video(ws, sibling)
        _frame(ws, good, 0.05)
        _close(ws, good)
        dir_a = ws.resolve("not_a_file_a")
        dir_b = ws.resolve("not_a_file_b")
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / sibling.name).write_bytes(sibling.read_bytes())
        failed_a = ws.call(VideoFileClip, str(dir_a))
        failed_b = ws.call(VideoFileClip, str(dir_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, dir_a)
        rest_b = _assert_identifies_path(failed_b, dir_b)
        print(f"dir_a={rest_a!r} dir_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')
        nested = _open_video(ws, dir_a / sibling.name)
        _frame(ws, nested, 0.05)
        _close(ws, nested)


def test_non_media_file_does_not_succeed():
    with workspace() as ws:
        sibling = _sibling_video(ws, "media_ok")
        good = _open_video(ws, sibling)
        _frame(ws, good, 0.05)
        _close(ws, good)
        fake_a = ws.resolve("fake_alpha.mp4")
        fake_b = ws.resolve("fake_beta.mp4")
        fake_a.write_bytes(b"this is not a media container " + secrets.token_bytes(32))
        fake_b.write_bytes(b"this is not a media container " + secrets.token_bytes(32))
        failed_a = ws.call(VideoFileClip, str(fake_a))
        failed_b = ws.call(VideoFileClip, str(fake_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, fake_a)
        rest_b = _assert_identifies_path(failed_b, fake_b)
        print(f"fake_a={rest_a!r} fake_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')


def test_unparsable_duration_or_size_does_not_succeed():
    with workspace() as ws:
        sibling = _sibling_video(ws, "intact")
        good = _open_video(ws, sibling)
        _frame(ws, good, 0.05)
        _close(ws, good)
        broken = ws.resolve("unparsable.mp4")
        data = sibling.read_bytes()
        broken.write_bytes(data[:48] if len(data) > 48 else b"\x00" * 24)
        duration_readable = True
        try:
            container_duration(broken)
        except HarnessError:
            duration_readable = False
        size_readable = True
        try:
            container_video_size(broken)
        except HarnessError:
            size_readable = False
        print(
            f"probe duration_readable={duration_readable} size_readable={size_readable}",
            flush=True,
        )
        if duration_readable and size_readable:
            broken.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40)
            duration_readable = True
            try:
                container_duration(broken)
            except HarnessError:
                duration_readable = False
            size_readable = True
            try:
                container_video_size(broken)
            except HarnessError:
                size_readable = False
        if duration_readable and size_readable:
            raise HarnessError(
                "could not build a fixture whose duration or size is unreadable"
            )
        failed = ws.call(VideoFileClip, str(broken))
        _assert_open_failed(failed)


def test_audio_missing_path_does_not_succeed_and_identifies_path():
    with workspace() as ws:
        sibling = _sibling_audio(ws, "present_audio")
        good = _open_audio(ws, sibling)
        _sound_array(ws, good)
        _close(ws, good)
        missing_a = ws.resolve("silent_gap_one.wav")
        missing_b = ws.resolve("silent_gap_two.wav")
        failed_a = ws.call(AudioFileClip, str(missing_a))
        failed_b = ws.call(AudioFileClip, str(missing_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, missing_a)
        rest_b = _assert_identifies_path(failed_b, missing_b)
        print(f"audio_missing_a={rest_a!r} audio_missing_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')


def test_audio_directory_path_does_not_succeed():
    with workspace() as ws:
        sibling = _sibling_audio(ws, "audio_dir_sib")
        good = _open_audio(ws, sibling)
        _sound_array(ws, good)
        _close(ws, good)
        dir_a = ws.resolve("audio_dir_a")
        dir_b = ws.resolve("audio_dir_b")
        dir_a.mkdir()
        dir_b.mkdir()
        failed_a = ws.call(AudioFileClip, str(dir_a))
        failed_b = ws.call(AudioFileClip, str(dir_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, dir_a)
        rest_b = _assert_identifies_path(failed_b, dir_b)
        print(f"audio_dir_a={rest_a!r} audio_dir_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')
        nested = dir_a / sibling.name
        nested.write_bytes(sibling.read_bytes())
        ok = _open_audio(ws, nested)
        _sound_array(ws, ok)
        _close(ws, ok)


def test_audio_non_media_file_does_not_succeed():
    with workspace() as ws:
        sibling = _sibling_audio(ws, "audio_ok")
        good = _open_audio(ws, sibling)
        _sound_array(ws, good)
        _close(ws, good)
        fake_a = ws.resolve("noise_alpha.mp4")
        fake_b = ws.resolve("noise_beta.mp4")
        fake_a.write_bytes(b"not audio media " + secrets.token_bytes(24))
        fake_b.write_bytes(b"not audio media " + secrets.token_bytes(24))
        failed_a = ws.call(AudioFileClip, str(fake_a))
        failed_b = ws.call(AudioFileClip, str(fake_b))
        _assert_open_failed(failed_a)
        _assert_open_failed(failed_b)
        rest_a = _assert_identifies_path(failed_a, fake_a)
        rest_b = _assert_identifies_path(failed_b, fake_b)
        print(f"audio_fake_a={rest_a!r} audio_fake_b={rest_b!r}", flush=True)
        if not (rest_a != rest_b):
            raise AssertionError('rest_a != rest_b')


# ---------------------------------------------------------------------------
# H. Decoder unreachable: construction itself must fail
# ---------------------------------------------------------------------------


def test_load_video_fails_when_decoder_unreachable():
    width, height = 32, 24
    first = (30, 200, 40)
    second = (40, 40, 210)
    duration = 0.4
    fps = 8.0
    with workspace() as ws:
        path = ws.resolve("neg_load.mp4")
        write_independent_video(
            path,
            _split_pictures(height, width, first, second, duration, fps),
            fps,
            ffmpeg_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
        )
        code = """
from clipkit import VideoFileClip
import numpy as np
clip = VideoFileClip("neg_load.mp4")
print("CONSTRUCTED")
frame = np.asarray(clip.get_frame(0.1))
print("SHAPE", int(frame.shape[0]), int(frame.shape[1]), int(frame.shape[2]))
print(
    "PIXEL",
    int(round(float(np.median(frame[:, :, 0])))),
    int(round(float(np.median(frame[:, :, 1])))),
    int(round(float(np.median(frame[:, :, 2])))),
)
"""
        unreachable = ws.run_python(code=code, encoder_reachable=False, timeout=45.0)
        print(
            f"unreachable rc={unreachable.returncode} "
            f"stdout={unreachable.stdout_text!r} "
            f"stderr={unreachable.stderr_text[:500]!r}",
            flush=True,
        )
        if not (unreachable.returncode != 0):
            raise AssertionError('unreachable.returncode != 0')
        if not ("CONSTRUCTED" not in unreachable.stdout_text):
            raise AssertionError('"CONSTRUCTED" not in unreachable.stdout_text')

        reachable = ws.run_python(code=code, encoder_reachable=True, timeout=45.0)
        print(
            f"reachable rc={reachable.returncode} stdout={reachable.stdout_text!r}",
            flush=True,
        )
        if not (reachable.returncode == 0):
            raise AssertionError('reachable.returncode == 0')
        if not ("CONSTRUCTED" in reachable.stdout_text):
            raise AssertionError('"CONSTRUCTED" in reachable.stdout_text')
        if not ("PIXEL" in reachable.stdout_text):
            raise AssertionError('"PIXEL" in reachable.stdout_text')
        pixel_line = [
            line for line in reachable.stdout_text.splitlines() if line.startswith("PIXEL")
        ][0]
        parts = pixel_line.split()
        got = (int(parts[1]), int(parts[2]), int(parts[3]))
        if not (_rgb_dist(got, first) <= 55):
            raise AssertionError('_rgb_dist(got, first) <= 55')


@pytest.mark.parametrize("ext,ffmpeg_args", _NAMED_VIDEO)
def test_load_named_video_containers(ext, ffmpeg_args):
    gif = ext.lower() == ".gif"
    ogv = ext.lower() == ".ogv"
    mpeg = ext.lower() == ".mpeg"
    lossy = gif or ogv or mpeg
    pairs = (
        ((16, 16, 220), (220, 220, 16)),
        ((220, 16, 16), (16, 220, 220)),
        ((16, 220, 16), (220, 16, 220)),
    )
    if mpeg:
        width, height = 96, 64
        duration = 2.0
        fps = 25.0
        first, second = pairs[secrets.randbelow(len(pairs))]
    elif ogv:
        width, height = 96, 64
        duration = 4.0
        fps = 10.0
        first, second = pairs[secrets.randbelow(len(pairs))]
    elif gif:
        width, height = 96, 64
        duration = 1.2
        fps = 10.0
        first, second = pairs[secrets.randbelow(len(pairs))]
    else:
        width, height = _rect_even_size()
        duration = 0.4
        fps = 8.0
        first = _rgb()
        second = _rgb_away_from(first)
    with workspace() as ws:
        path = ws.resolve(f"named{ext}")
        pictures = _split_pictures(height, width, first, second, duration, fps)
        write_independent_video(path, pictures, fps, ffmpeg_args=ffmpeg_args)
        frames = independent_rgb_frames(path)
        if len(frames) < 2:
            raise HarnessError(f"encoded {ext} fixture has fewer than 2 frames")
        i1 = max(0, len(frames) // 4)
        i2 = min(len(frames) - 1, (3 * len(frames)) // 4)
        fixture1 = frames[i1]
        fixture2 = frames[i2]
        print(
            f"fixture n={len(frames)} i1={i1} rgb={dominant_picture_rgb(fixture1)} "
            f"i2={i2} rgb={dominant_picture_rgb(fixture2)}",
            flush=True,
        )
        if pictures_close_lossy(fixture1, fixture2):
            raise HarnessError(
                f"encoded {ext} fixture halves are not distinct at "
                f"frames {i1} and {i2} of {len(frames)}"
            )
        clip = _open_video(ws, path)
        extra = {}
        if gif:
            extra["slack"] = 0.45
            extra["fps_slack"] = (0.25, 6.0)
        elif lossy:
            extra["slack"] = 0.45
        _assert_matches_video_stream(clip, path, **extra)
        file_fps = float(clip.fps)
        dur = float(clip.duration)
        eps = 1.0 / max(file_fps, 1.0)
        t1 = min(max(0.0, (i1 + 0.5) / file_fps), max(0.0, dur - eps))
        t2 = min(max(0.0, (i2 + 0.5) / file_fps), max(0.0, dur - eps))
        _assert_halves(
            ws,
            clip,
            first,
            second,
            dur,
            gif=gif,
            lossy=lossy,
            t1=t1,
            t2=t2,
        )
        _close(ws, clip)
