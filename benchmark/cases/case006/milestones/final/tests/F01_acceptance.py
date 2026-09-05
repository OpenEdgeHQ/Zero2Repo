# feature: F01
"""Clip as a timed media unit (FP-01).

Assertions stay at the PRD's precision: frame shapes and integer 0–255
channels, mask 0–1 layout, start/end/duration arithmetic, fps assignment
with and without 1:1 conserving, copy-on-modify, time encodings, whole-frame
iteration counts, still equality, missing-duration refusal, and soundtrack
attach/strip including encode. Exception types and failure wording are not
pinned.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import numpy as np
import pytest
from clipkit import AudioClip, ColorClip, VideoClip

from _harness import workspace
from _helpers import (
    as_numeric_array,
    container_frame_rate,
    container_has_audio,
    dominant_tone_hz,
    failure_identifies_missing_duration,
    media_file_nonempty,
    pcm_from_container,
    pictures_equal,
    require_failed,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
    require_sound_frame,
    samples_close,
)

_PCM_RATE = 44100


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _even_size() -> tuple[int, int]:
    width = _rand_int(10, 18) * 2
    height = _rand_int(8, 14) * 2
    return width, height


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(20, 230), _rand_int(20, 230), _rand_int(20, 230))


def _tone_hz() -> float:
    return float(_rand_int(310, 720))


def _make_color(ws, size, color, duration=None, fps=None):
    clip = require_ok(ws.call(ColorClip, size, color=color))
    if duration is not None:
        clip = require_ok(ws.call(clip.with_duration, duration))
    if fps is not None:
        clip = require_ok(ws.call(clip.with_fps, fps))
    return clip


def _time_picture(height: int, width: int):
    def frame_function(t):
        picture = np.zeros((height, width, 3), dtype=np.uint8)
        picture[:, :, 0] = int(np.clip(t * 400.0, 0, 255))
        picture[:, :, 1] = 90
        picture[:, :, 2] = 40
        return picture

    return frame_function


def _collect_frames(ws, clip):
    iterator = require_ok(ws.call(clip.iter_frames, logger=None))
    frames = [as_numeric_array(picture) for picture in iterator]
    print(f"iterated_count={len(frames)}", flush=True)
    return frames


def _consume_frames(iterator):
    return list(iterator)


def _ask_all_frames(ws, clip):
    """Iterate every frame, or return the caller-visible failure.

    Asking to iterate all frames has not succeeded when obtaining the
    iterator fails, or when consuming a returned iterator fails. Either
    CallResult is the failure the caller sees.
    """
    obtained = ws.call(clip.iter_frames, logger=None)
    if obtained.exception is not None:
        print("iter_frames_call_did_not_succeed", flush=True)
        return obtained, None
    consumed = ws.call(_consume_frames, obtained.value)
    if consumed.exception is not None:
        print("iter_frames_consume_did_not_succeed", flush=True)
        return consumed, None
    frames = [as_numeric_array(picture) for picture in consumed.value]
    print(f"iterated_count={len(frames)}", flush=True)
    return None, frames


def _write_kind(ws, clip, kind: str, stem: str) -> Path:
    if kind == "video":
        path = ws.resolve(f"{stem}.mp4")
        require_ok(ws.call(clip.write_videofile, str(path), logger=None))
        return path
    if kind == "gif":
        path = ws.resolve(f"{stem}.gif")
        require_ok(ws.call(clip.write_gif, str(path), logger=None))
        return path
    if kind == "sequence":
        folder = ws.resolve(stem)
        folder.mkdir(parents=True, exist_ok=True)
        pattern = str(folder / "frame%03d.png")
        require_ok(ws.call(clip.write_images_sequence, pattern, logger=None))
        return folder
    raise HarnessKindError(kind)


class HarnessKindError(RuntimeError):
    pass


def _sequence_complete(folder: Path) -> bool:
    files = sorted(folder.glob("frame*.png"))
    return any(path.is_file() and path.stat().st_size > 0 for path in files)


def _try_write(ws, clip, kind: str, stem: str):
    if kind == "video":
        path = ws.resolve(f"{stem}.mp4")
        result = ws.call(clip.write_videofile, str(path), logger=None)
        return result, path
    if kind == "gif":
        path = ws.resolve(f"{stem}.gif")
        result = ws.call(clip.write_gif, str(path), logger=None)
        return result, path
    if kind == "sequence":
        folder = ws.resolve(stem)
        folder.mkdir(parents=True, exist_ok=True)
        pattern = str(folder / "frame%03d.png")
        result = ws.call(clip.write_images_sequence, pattern, logger=None)
        return result, folder
    raise HarnessKindError(kind)


# ---------------------------------------------------------------------------
# A. Frame shapes, colors, determinism
# ---------------------------------------------------------------------------


def test_color_clip_frame_at_zero_matches_size_and_color():
    with workspace() as ws:
        oracle_size = (32, 24)
        oracle_color = (255, 0, 0)
        oracle = _make_color(ws, oracle_size, oracle_color, duration=1, fps=8)
        oracle_frame = require_ok(ws.call(oracle.get_frame, 0))
        print(
            f"oracle size={oracle_size} color={oracle_color} shape={np.asarray(oracle_frame).shape}",
            flush=True,
        )
        oracle_picture = require_rgb_picture(
            oracle_frame, oracle_size[1], oracle_size[0], color=oracle_color
        )
        assert oracle_picture.shape == (oracle_size[1], oracle_size[0], 3)
        assert np.allclose(
            oracle_picture.astype(float),
            np.asarray(oracle_color, dtype=float).reshape(1, 1, 3),
            atol=0.5,
            rtol=0,
        )

        size = _even_size()
        color = _rgb()
        clip = _make_color(ws, size, color, duration=0.5, fps=6)
        frame = require_ok(ws.call(clip.get_frame, 0))
        print(f"runtime size={size} color={color} shape={np.asarray(frame).shape}", flush=True)
        picture = require_rgb_picture(frame, size[1], size[0], color=color)
        assert picture.shape == (size[1], size[0], 3)
        assert np.allclose(
            picture.astype(float),
            np.asarray(color, dtype=float).reshape(1, 1, 3),
            atol=0.5,
            rtol=0,
        )


def test_repeated_frame_at_same_time_matches():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        clip = _make_color(ws, size, color, duration=0.8, fps=8)
        first = require_ok(ws.call(clip.get_frame, 0))
        second = require_ok(ws.call(clip.get_frame, 0))
        require_rgb_picture(first, size[1], size[0], color=color)
        print(f"repeat_match={pictures_equal(first, second)}", flush=True)
        assert pictures_equal(first, second)


def test_mask_mode_color_frame_is_hw_unit_interval():
    with workspace() as ws:
        width, height = _even_size()
        level = 0.25 + secrets.randbelow(50) / 100.0
        clip = require_ok(
            ws.call(ColorClip, (width, height), color=level, is_mask=True)
        )
        clip = require_ok(ws.call(clip.with_duration, 0.4))
        clip = require_ok(ws.call(clip.with_fps, 8))
        frame = require_ok(ws.call(clip.get_frame, 0))
        print(f"mask size={(width, height)} level={level} shape={np.asarray(frame).shape}", flush=True)
        mask = require_mask_picture(frame, height, width)
        assert np.allclose(mask, level, atol=1e-5)


def test_audio_frame_mono_and_stereo_floats():
    with workspace() as ws:
        freq = _tone_hz()
        t = 0.1

        def mono(t):
            return np.array([np.sin(2.0 * np.pi * freq * t)], dtype=float)

        def stereo(t):
            return np.array(
                [
                    np.sin(2.0 * np.pi * freq * t),
                    np.sin(2.0 * np.pi * (freq * 2.0) * t),
                ],
                dtype=float,
            )

        mono_clip = require_ok(
            ws.call(AudioClip, frame_function=mono, duration=0.5, fps=_PCM_RATE)
        )
        stereo_clip = require_ok(
            ws.call(AudioClip, frame_function=stereo, duration=0.5, fps=_PCM_RATE)
        )

        mono_raw = require_ok(ws.call(mono_clip.get_frame, t))
        stereo_raw = require_ok(ws.call(stereo_clip.get_frame, t))
        mono_a = require_sound_frame(mono_raw, 1)
        stereo_a = require_sound_frame(stereo_raw, 2)
        print(f"freq={freq} t={t} mono={mono_a} stereo={stereo_a}", flush=True)
        assert as_numeric_array(mono_raw).dtype.kind in "fc"
        assert as_numeric_array(stereo_raw).dtype.kind in "fc"
        assert mono_a.size == 1
        assert stereo_a.size == 2


# ---------------------------------------------------------------------------
# B. Start, end, duration arithmetic
# ---------------------------------------------------------------------------


def test_new_clip_starts_at_composition_zero():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        fresh = require_ok(ws.call(ColorClip, size, color=color))
        print(f"fresh_start={fresh.start} fresh_end={fresh.end} fresh_duration={fresh.duration}", flush=True)
        timed = require_ok(ws.call(fresh.with_duration, 5))
        print(f"oracle5 start={timed.start} end={timed.end} duration={timed.duration}", flush=True)
        assert timed.start == 0
        assert timed.duration == pytest.approx(5)
        assert timed.end == pytest.approx(5)

        duration = 0.4 + secrets.randbelow(80) / 100.0
        runtime = require_ok(ws.call(fresh.with_duration, duration))
        print(f"runtime D={duration} start={runtime.start} end={runtime.end}", flush=True)
        assert runtime.start == 0
        assert runtime.end == pytest.approx(duration)


def test_assign_duration_sets_end_to_start_plus_duration():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        started = require_ok(ws.call(base.with_start, "00:00:02"))
        duration = 1.25 + secrets.randbelow(50) / 100.0
        timed = require_ok(ws.call(started.with_duration, duration))
        print(
            f"clock_start=2 D={duration} start={timed.start} end={timed.end} duration={timed.duration}",
            flush=True,
        )
        assert timed.start == pytest.approx(2)
        assert timed.duration == pytest.approx(duration)
        assert timed.end == pytest.approx(2 + duration)
        assert started.duration is None
        assert started is not timed

        pair_base = require_ok(ws.call(ColorClip, size, color=color))
        pair_started = require_ok(ws.call(pair_base.with_start, 1.5))
        pair_timed = require_ok(ws.call(pair_started.with_duration, (0, 2)))
        print(
            f"pair_duration start={pair_timed.start} end={pair_timed.end} duration={pair_timed.duration}",
            flush=True,
        )
        assert pair_timed.duration == pytest.approx(2)
        assert pair_timed.end == pytest.approx(1.5 + 2)


def test_assign_end_sets_duration_to_end_minus_start():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        started = require_ok(ws.call(base.with_start, (0, 1)))
        ended = require_ok(ws.call(started.with_end, "00:00:04"))
        print(
            f"pair_start=1 clock_end=4 start={ended.start} end={ended.end} duration={ended.duration}",
            flush=True,
        )
        assert ended.start == pytest.approx(1)
        assert ended.end == pytest.approx(4)
        assert ended.duration == pytest.approx(3)
        assert started is not ended
        assert started.duration is None


def test_new_start_keeps_duration_or_keeps_end():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        duration = 4.0
        new_start = 1.5
        base = _make_color(ws, size, color, duration=duration, fps=8)
        original_start, original_end, original_duration = base.start, base.end, base.duration
        keep_duration = require_ok(ws.call(base.with_start, new_start, change_end=True))
        keep_end = require_ok(ws.call(base.with_start, new_start, change_end=False))
        print(
            f"base=({original_start},{original_end},{original_duration}) "
            f"keep_duration=({keep_duration.start},{keep_duration.end},{keep_duration.duration}) "
            f"keep_end=({keep_end.start},{keep_end.end},{keep_end.duration})",
            flush=True,
        )
        assert keep_duration is not base
        assert keep_end is not base
        assert base.start == original_start
        assert base.end == pytest.approx(original_end)
        assert base.duration == pytest.approx(original_duration)

        assert keep_duration.start == pytest.approx(new_start)
        assert keep_duration.duration == pytest.approx(duration)
        assert keep_duration.end == pytest.approx(new_start + duration)

        assert keep_end.start == pytest.approx(new_start)
        assert keep_end.end == pytest.approx(original_end)
        assert keep_end.duration == pytest.approx(original_end - new_start)


def test_start_change_does_not_shift_clip_local_first_frame():
    with workspace() as ws:
        width, height = _even_size()
        duration = 1.0
        generated = require_ok(
            ws.call(
                VideoClip,
                frame_function=_time_picture(height, width),
                duration=duration,
            )
        )
        generated = require_ok(ws.call(generated.with_fps, 8))
        original_zero = require_ok(ws.call(generated.get_frame, 0))
        new_start = 0.4
        at_new_start = require_ok(ws.call(generated.get_frame, new_start))
        moved = require_ok(ws.call(generated.with_start, new_start, change_end=True))
        moved_zero = require_ok(ws.call(moved.get_frame, 0))
        print(
            f"new_start={new_start} original_t0_r={int(original_zero[0, 0, 0])} "
            f"original_tS_r={int(at_new_start[0, 0, 0])} moved_t0_r={int(moved_zero[0, 0, 0])}",
            flush=True,
        )
        assert pictures_equal(moved_zero, original_zero)
        assert not pictures_equal(moved_zero, at_new_start)
        assert generated.start == 0


# ---------------------------------------------------------------------------
# C. Frame rate: conserving vs not; iteration and encode defaults
# ---------------------------------------------------------------------------


def test_assign_fps_without_conserve_leaves_duration():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        duration = 0.8
        rate = 8
        new_rate = 12
        base = _make_color(ws, size, color, duration=duration, fps=rate)
        original_frame = require_ok(ws.call(base.get_frame, 0))
        changed = require_ok(ws.call(base.with_fps, new_rate, change_duration=False))
        print(
            f"old_fps={base.fps} old_D={base.duration} new_fps={changed.fps} new_D={changed.duration}",
            flush=True,
        )
        assert changed is not base
        assert base.fps == pytest.approx(rate)
        assert base.duration == pytest.approx(duration)
        assert changed.fps == pytest.approx(new_rate)
        assert changed.duration == pytest.approx(duration)
        assert pictures_equal(require_ok(ws.call(base.get_frame, 0)), original_frame)
        assert pictures_equal(require_ok(ws.call(changed.get_frame, 0)), original_frame)


def test_assign_fps_conserving_scales_duration_inversely():
    with workspace() as ws:
        width, height = _even_size()
        duration = 0.5
        rate = 10
        generated = require_ok(
            ws.call(
                VideoClip,
                frame_function=_time_picture(height, width),
                duration=duration,
            )
        )
        generated = require_ok(ws.call(generated.with_fps, rate))
        t0 = 0.1
        original_at_t0 = require_ok(ws.call(generated.get_frame, t0))
        original_at_2t0 = require_ok(ws.call(generated.get_frame, 2 * t0))
        assert not pictures_equal(original_at_t0, original_at_2t0)

        halved = require_ok(ws.call(generated.with_fps, rate / 2, change_duration=True))
        doubled = require_ok(ws.call(generated.with_fps, rate * 2, change_duration=True))
        print(
            f"orig D={generated.duration} fps={generated.fps} "
            f"halved D={halved.duration} fps={halved.fps} "
            f"doubled D={doubled.duration} fps={doubled.fps}",
            flush=True,
        )
        assert generated.duration == pytest.approx(duration)
        assert generated.fps == pytest.approx(rate)
        assert halved is not generated
        assert halved.duration == pytest.approx(duration * 2)
        assert halved.fps == pytest.approx(rate / 2)
        assert doubled.duration == pytest.approx(duration / 2)
        assert doubled.fps == pytest.approx(rate * 2)

        conserved = require_ok(ws.call(halved.get_frame, 2 * t0))
        assert pictures_equal(conserved, original_at_t0)
        assert not pictures_equal(conserved, original_at_2t0)


def test_assigned_fps_is_default_for_iteration():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        duration = 0.5
        rate = 8
        clip = _make_color(ws, size, color, duration=duration, fps=rate)
        frames = _collect_frames(ws, clip)
        expected = int(duration * rate)
        print(f"D={duration} R={rate} expected={expected} got={len(frames)}", flush=True)
        assert len(frames) == expected


def test_assigned_fps_is_default_for_encode():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        duration = 0.4
        rate = float(_rand_int(6, 12))
        clip = _make_color(ws, size, color, duration=duration, fps=rate)
        path = ws.resolve("default_fps.mp4")
        require_ok(ws.call(clip.write_videofile, str(path), logger=None))
        media_file_nonempty(path)
        probed = container_frame_rate(path)
        print(f"assigned_fps={rate} container_fps={probed}", flush=True)
        assert probed == pytest.approx(rate, abs=0.05)


# ---------------------------------------------------------------------------
# D. Copy-on-modify; soundtrack attach / strip
# ---------------------------------------------------------------------------


def test_assign_soundtrack_returns_distinct_clip_pixels_unchanged():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        video = _make_color(ws, size, color, duration=0.6, fps=8)
        freq_a = _tone_hz()
        freq_b = freq_a + 80.0
        t_peak = 0.25 / freq_a

        def tone(freq):
            def frame_function(t):
                return np.array([np.sin(2.0 * np.pi * freq * t)], dtype=float)

            return frame_function

        audio_a = require_ok(
            ws.call(AudioClip, frame_function=tone(freq_a), duration=0.6, fps=_PCM_RATE)
        )
        audio_b = require_ok(
            ws.call(AudioClip, frame_function=tone(freq_b), duration=0.6, fps=_PCM_RATE)
        )
        before = require_ok(ws.call(video.get_frame, 0))
        with_a = require_ok(ws.call(video.with_audio, audio_a))
        with_b = require_ok(ws.call(video.with_audio, audio_b))
        print(
            f"original_audio={video.audio is not None} "
            f"with_a_is={with_a is video} t_peak={t_peak}",
            flush=True,
        )
        assert with_a is not video
        assert video.audio is None
        assert with_a.audio is not None
        assert pictures_equal(require_ok(ws.call(video.get_frame, 0)), before)
        assert pictures_equal(require_ok(ws.call(with_a.get_frame, 0)), before)

        assigned = require_sound_frame(require_ok(ws.call(with_a.audio.get_frame, t_peak)), 1)
        source = require_sound_frame(require_ok(ws.call(audio_a.get_frame, t_peak)), 1)
        other_t = require_sound_frame(
            require_ok(ws.call(with_a.audio.get_frame, 0.75 / freq_a)), 1
        )
        other_clip = require_sound_frame(
            require_ok(ws.call(with_b.audio.get_frame, t_peak)), 1
        )
        zero = require_sound_frame(require_ok(ws.call(audio_a.get_frame, 0)), 1)
        assert samples_close(assigned, source)
        assert not samples_close(assigned, other_t)
        assert not samples_close(assigned, other_clip)
        assert not samples_close(assigned, zero)
        assert abs(float(assigned[0])) > 0.2


def test_strip_soundtrack_leaves_original_audio():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        freq = _tone_hz()
        t_peak = 0.25 / freq

        def mono(t):
            return np.array([np.sin(2.0 * np.pi * freq * t)], dtype=float)

        video = _make_color(ws, size, color, duration=0.5, fps=8)
        audio = require_ok(
            ws.call(AudioClip, frame_function=mono, duration=0.5, fps=_PCM_RATE)
        )
        with_sound = require_ok(ws.call(video.with_audio, audio))
        stripped = require_ok(ws.call(with_sound.without_audio))
        print(
            f"with_sound_audio={with_sound.audio is not None} "
            f"stripped_audio={stripped.audio is not None} distinct={stripped is not with_sound}",
            flush=True,
        )
        assert stripped is not with_sound
        assert with_sound.audio is not None
        assert stripped.audio is None
        original_sample = require_sound_frame(
            require_ok(ws.call(with_sound.audio.get_frame, t_peak)), 1
        )
        source_sample = require_sound_frame(require_ok(ws.call(audio.get_frame, t_peak)), 1)
        assert samples_close(original_sample, source_sample)


def test_assign_duration_does_not_mutate_original():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        infinite = require_ok(ws.call(ColorClip, size, color=color))
        infinite = require_ok(ws.call(infinite.with_fps, 8))
        before = require_ok(ws.call(infinite.get_frame, 0))
        duration = 0.7
        timed = require_ok(ws.call(infinite.with_duration, duration))
        print(
            f"orig_duration={infinite.duration} new_duration={timed.duration} distinct={timed is not infinite}",
            flush=True,
        )
        assert timed is not infinite
        assert infinite.duration is None
        assert timed.duration == pytest.approx(duration)
        assert pictures_equal(require_ok(ws.call(infinite.get_frame, 0)), before)
        require_rgb_picture(require_ok(ws.call(timed.get_frame, 0)), size[1], size[0], color=color)


def test_copy_is_distinct_and_original_duration_stable():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        original = _make_color(ws, size, color, duration=0.6, fps=8)
        before = require_ok(ws.call(original.get_frame, 0))
        replica = require_ok(ws.call(original.copy))
        print(f"copy_distinct={replica is not original} orig_D={original.duration}", flush=True)
        assert replica is not original
        require_rgb_picture(
            require_ok(ws.call(replica.get_frame, 0)), size[1], size[0], color=color
        )
        changed = require_ok(ws.call(replica.with_duration, 1.4))
        assert original.duration == pytest.approx(0.6)
        assert changed.duration == pytest.approx(1.4)
        assert pictures_equal(require_ok(ws.call(original.get_frame, 0)), before)


# ---------------------------------------------------------------------------
# E. Time encodings
# ---------------------------------------------------------------------------


def test_duration_five_from_number_triple_and_clock_string():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        as_number = require_ok(ws.call(base.with_duration, 5))
        as_triple = require_ok(ws.call(base.with_duration, (0, 0, 5)))
        as_clock = require_ok(ws.call(base.with_duration, "00:00:05"))
        print(
            f"number={as_number.duration} triple={as_triple.duration} clock={as_clock.duration}",
            flush=True,
        )
        for clip in (as_number, as_triple, as_clock):
            assert clip.duration == pytest.approx(5)
            assert clip.start == pytest.approx(0)
            assert clip.end == pytest.approx(5)


def test_pair_minutes_seconds_duration():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        ninety = require_ok(ws.call(base.with_duration, (1, 30)))
        minutes = _rand_int(0, 2)
        seconds = _rand_int(1, 40)
        runtime = require_ok(ws.call(base.with_duration, (minutes, seconds)))
        print(
            f"pair_1_30={ninety.duration} runtime=({minutes},{seconds})->{runtime.duration}",
            flush=True,
        )
        assert ninety.duration == pytest.approx(90)
        assert runtime.duration == pytest.approx(minutes * 60 + seconds)


def test_triple_and_clock_with_nonzero_hours_or_minutes():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        one_minute = require_ok(ws.call(base.with_duration, (0, 1, 0)))
        clock_minute = require_ok(ws.call(base.with_duration, "00:01:00"))
        hour_plus = require_ok(ws.call(base.with_duration, "01:00:01"))
        print(
            f"triple_010={one_minute.duration} clock_000100={clock_minute.duration} "
            f"clock_010001={hour_plus.duration}",
            flush=True,
        )
        assert one_minute.duration == pytest.approx(60)
        assert one_minute.duration != pytest.approx(1)
        assert clock_minute.duration == pytest.approx(60)
        assert hour_plus.duration == pytest.approx(3601)
        assert hour_plus.duration != pytest.approx(1)
        assert hour_plus.duration != pytest.approx(2)


def test_clock_string_hms_fractional():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        fractional = require_ok(ws.call(base.with_duration, "00:00:01.5"))
        print(f"hms_fractional={fractional.duration} end={fractional.end}", flush=True)
        assert fractional.duration == pytest.approx(1.5)
        assert fractional.end == pytest.approx(1.5)


def test_clock_string_ms_and_seconds_only():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        base = require_ok(ws.call(ColorClip, size, color=color))
        minutes_seconds = require_ok(ws.call(base.with_duration, "1:30"))
        seconds_only = require_ok(ws.call(base.with_duration, "8"))
        print(
            f"ms={minutes_seconds.duration} seconds_only={seconds_only.duration}",
            flush=True,
        )
        assert minutes_seconds.duration == pytest.approx(90)
        assert minutes_seconds.duration != pytest.approx(30)
        assert seconds_only.duration == pytest.approx(8)


def test_comma_decimal_equals_period_decimal():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        period_base = require_ok(ws.call(ColorClip, size, color=color))
        comma_base = require_ok(ws.call(ColorClip, size, color=color))
        period = require_ok(ws.call(period_base.with_duration, "1.25"))
        comma = require_ok(ws.call(comma_base.with_duration, "1,25"))
        print(f"period={period.duration} comma={comma.duration}", flush=True)
        assert period.duration == pytest.approx(1.25)
        assert comma.duration == pytest.approx(period.duration)


def test_frame_at_nonzero_time_accepts_pair_clock_and_comma():
    with workspace() as ws:
        width, height = _even_size()
        duration = 2.0
        generated = require_ok(
            ws.call(
                VideoClip,
                frame_function=_time_picture(height, width),
                duration=duration,
            )
        )
        generated = require_ok(ws.call(generated.with_fps, 8))
        t = 1.5
        by_number = require_ok(ws.call(generated.get_frame, t))
        by_pair = require_ok(ws.call(generated.get_frame, (0, 1.5)))
        by_clock = require_ok(ws.call(generated.get_frame, "00:00:01.5"))
        by_comma = require_ok(ws.call(generated.get_frame, "00:00:01,5"))
        other = require_ok(ws.call(generated.get_frame, 0.2))
        print(
            f"t={t} r_number={int(by_number[0, 0, 0])} r_pair={int(by_pair[0, 0, 0])} "
            f"r_clock={int(by_clock[0, 0, 0])} r_comma={int(by_comma[0, 0, 0])} "
            f"r_other={int(other[0, 0, 0])}",
            flush=True,
        )
        assert pictures_equal(by_pair, by_number)
        assert pictures_equal(by_clock, by_number)
        assert pictures_equal(by_comma, by_number)
        assert not pictures_equal(by_number, other)


# ---------------------------------------------------------------------------
# F. Iteration count and corresponding frames
# ---------------------------------------------------------------------------


def test_one_second_at_60_fps_yields_60_frames():
    with workspace() as ws:
        clip = _make_color(ws, (16, 16), (0, 255, 0), duration=1, fps=60)
        frames = _collect_frames(ws, clip)
        print(f"oracle_60 got={len(frames)}", flush=True)
        assert len(frames) == 60
        for picture in frames:
            require_rgb_picture(picture, 16, 16, color=(0, 255, 0))


def test_iteration_count_is_duration_times_fps_whole_frames():
    with workspace() as ws:
        duration = float(_rand_int(1, 2))
        rate = float(_rand_int(5, 9))
        expected = int(duration * rate)
        clip = _make_color(ws, _even_size(), _rgb(), duration=duration, fps=rate)
        frames = _collect_frames(ws, clip)
        print(f"runtime D={duration} R={rate} expected={expected} got={len(frames)}", flush=True)
        assert len(frames) == expected


def test_each_yielded_picture_is_a_frame_at_a_corresponding_time():
    with workspace() as ws:
        width, height = _even_size()
        duration = 0.5
        rate = 8
        generated = require_ok(
            ws.call(
                VideoClip,
                frame_function=_time_picture(height, width),
                duration=duration,
            )
        )
        generated = require_ok(ws.call(generated.with_fps, rate))
        frames = _collect_frames(ws, generated)
        expected = int(duration * rate)
        assert len(frames) == expected
        assert expected > 1
        for picture in frames:
            require_rgb_picture(picture, height, width)
        first, last = frames[0], frames[-1]
        assert not pictures_equal(first, last)

        # Uniform sampling of duration at this rate. Left edge, mid-slot,
        # and right edge of each 1/rate slot are accepted; one phase must
        # fit every yielded picture. A mixed sequence (early times bunched,
        # then a jump into the last slot) does not.
        slot = 1.0 / rate
        phases = (0.0, 0.5 * slot, slot)
        matched_phase = None
        for phase in phases:
            matches = True
            for i, picture in enumerate(frames):
                t = phase + i * slot
                if t > duration:
                    t = duration
                asked = require_ok(ws.call(generated.get_frame, t))
                if not pictures_equal(picture, asked):
                    matches = False
                    break
            if matches:
                matched_phase = phase
                break
        print(
            f"D={duration} R={rate} n={len(frames)} slot={slot} "
            f"uniform_phase={matched_phase}",
            flush=True,
        )
        assert matched_phase is not None


# ---------------------------------------------------------------------------
# G. Still equality
# ---------------------------------------------------------------------------


def test_same_stills_duration_fps_compare_equal():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        duration = 0.5 + secrets.randbelow(40) / 100.0
        rate = 8
        left = _make_color(ws, size, color, duration=duration, fps=rate)
        right = _make_color(ws, size, color, duration=duration, fps=rate)
        print(f"equal_pair size={size} color={color} D={duration}", flush=True)
        assert left == right


def test_different_pictures_compare_unequal():
    with workspace() as ws:
        size = _even_size()
        duration, rate = 0.5, 8
        color = _rgb()
        other = ((color[0] + 80) % 230 + 20, (color[1] + 110) % 230 + 20, (color[2] + 50) % 230 + 20)
        twin_left = _make_color(ws, size, color, duration=duration, fps=rate)
        twin_right = _make_color(ws, size, color, duration=duration, fps=rate)
        print(f"picture_twins_equal color={color}", flush=True)
        assert twin_left == twin_right
        changed = _make_color(ws, size, other, duration=duration, fps=rate)
        print(f"picture_unequal other={other}", flush=True)
        assert twin_left != changed


def test_different_duration_compare_unequal():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        rate = 8
        duration = 0.5
        other_duration = 1.0
        twin_left = _make_color(ws, size, color, duration=duration, fps=rate)
        twin_right = _make_color(ws, size, color, duration=duration, fps=rate)
        print(f"duration_twins_equal D={duration}", flush=True)
        assert twin_left == twin_right
        changed = _make_color(ws, size, color, duration=other_duration, fps=rate)
        print(f"duration_unequal {twin_left.duration} vs {changed.duration}", flush=True)
        assert twin_left != changed


# ---------------------------------------------------------------------------
# H. Missing duration refuses iteration and the three encodes
# ---------------------------------------------------------------------------


def test_iterate_without_duration_does_not_succeed():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        rate = 8
        duration = 0.5
        infinite = _make_color(ws, size, color, duration=None, fps=rate)
        failed, missing_frames = _ask_all_frames(ws, infinite)
        assert failed is not None
        assert missing_frames is None
        failure = require_failed(failed)
        print(f"iterate_missing_duration={type(failure).__name__}: {failure}", flush=True)
        rest = failure_identifies_missing_duration(failed, size, color)
        print(f"iterate_missing_remainder={rest!r}", flush=True)

        finite = require_ok(ws.call(infinite.with_duration, duration))
        success, frames = _ask_all_frames(ws, finite)
        assert success is None
        expected = int(duration * rate)
        assert len(frames) == expected
        assert failed.exception is not None
        assert failed.exception is not frames


@pytest.mark.parametrize("kind", ["video", "gif", "sequence"])
def test_encode_without_duration_fails_for_video_gif_and_sequence(kind):
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        rate = 8
        duration = 0.4
        infinite = _make_color(ws, size, color, duration=None, fps=rate)
        failed, target = _try_write(ws, infinite, kind, f"missing_{kind}")
        failure = require_failed(failed)
        print(f"encode_{kind}_missing={type(failure).__name__}: {failure}", flush=True)
        if kind == "sequence":
            complete = _sequence_complete(target)
        else:
            complete = Path(target).is_file() and Path(target).stat().st_size > 0
        assert not complete
        rest = failure_identifies_missing_duration(failed, target, size, color)
        print(f"encode_{kind}_missing_remainder={rest!r}", flush=True)

        finite = require_ok(ws.call(infinite.with_duration, duration))
        success, written = _try_write(ws, finite, kind, f"present_{kind}")
        require_ok(success)
        if kind == "sequence":
            assert _sequence_complete(written)
        else:
            media_file_nonempty(written)
        assert failed.exception is not None
        assert success.exception is None


def test_same_clip_writable_after_duration_assigned():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        infinite = _make_color(ws, size, color, duration=None, fps=8)
        finite = require_ok(ws.call(infinite.with_duration, 0.4))
        video = _write_kind(ws, finite, "video", "after_video")
        gif = _write_kind(ws, finite, "gif", "after_gif")
        sequence = _write_kind(ws, finite, "sequence", "after_seq")
        print(
            f"video={media_file_nonempty(video)} gif={media_file_nonempty(gif)} "
            f"seq={_sequence_complete(sequence)}",
            flush=True,
        )
        assert _sequence_complete(sequence)


# ---------------------------------------------------------------------------
# I. Soundtrack included or omitted on encode; encoder negative control
# ---------------------------------------------------------------------------


def test_encode_with_assigned_tone_contains_that_tone():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        freq = _tone_hz()
        duration = 0.5

        def mono(t):
            return np.array([np.sin(2.0 * np.pi * freq * t)], dtype=float)

        video = _make_color(ws, size, color, duration=duration, fps=8)
        audio = require_ok(
            ws.call(AudioClip, frame_function=mono, duration=duration, fps=_PCM_RATE)
        )
        with_sound = require_ok(ws.call(video.with_audio, audio))
        path = ws.resolve("with_tone.mp4")
        require_ok(ws.call(with_sound.write_videofile, str(path), audio=True, logger=None))
        media_file_nonempty(path)
        assert container_has_audio(path)
        pcm = pcm_from_container(path)
        peak = dominant_tone_hz(pcm, _PCM_RATE)
        print(f"requested_hz={freq} measured_hz={peak}", flush=True)
        assert peak == pytest.approx(freq, rel=0.08, abs=12)


def test_encode_after_strip_omits_soundtrack():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        freq = _tone_hz()
        duration = 0.5

        def mono(t):
            return np.array([np.sin(2.0 * np.pi * freq * t)], dtype=float)

        video = _make_color(ws, size, color, duration=duration, fps=8)
        audio = require_ok(
            ws.call(AudioClip, frame_function=mono, duration=duration, fps=_PCM_RATE)
        )
        with_sound = require_ok(ws.call(video.with_audio, audio))
        baseline = ws.resolve("baseline_tone.mp4")
        require_ok(ws.call(with_sound.write_videofile, str(baseline), audio=True, logger=None))
        media_file_nonempty(baseline)
        assert container_has_audio(baseline) is True

        stripped = require_ok(ws.call(with_sound.without_audio))
        path = ws.resolve("stripped.mp4")
        require_ok(ws.call(stripped.write_videofile, str(path), audio=True, logger=None))
        media_file_nonempty(path)
        has_audio = container_has_audio(path)
        print(f"baseline_has_audio=True stripped_has_audio={has_audio}", flush=True)
        assert has_audio is False


def test_video_encode_fails_when_encoder_unreachable():
    code = """
from clipkit import ColorClip
clip = ColorClip((32, 24), color=(20, 180, 40), duration=0.3).with_fps(8)
clip.write_videofile("neg_control.mp4", logger=None)
import os
print("SIZE", os.path.getsize("neg_control.mp4"))
"""
    with workspace() as ws:
        unreachable = ws.run_python(code=code, encoder_reachable=False, timeout=45.0)
        print(
            f"unreachable rc={unreachable.returncode} stderr={unreachable.stderr_text[:500]!r}",
            flush=True,
        )
        assert unreachable.returncode != 0

        reachable = ws.run_python(code=code, encoder_reachable=True, timeout=45.0)
        print(
            f"reachable rc={reachable.returncode} stdout={reachable.stdout_text!r}",
            flush=True,
        )
        assert reachable.returncode == 0
        media_file_nonempty(ws.resolve("neg_control.mp4"))


# ---------------------------------------------------------------------------
# J. Missing duration while keeping end does not succeed
# ---------------------------------------------------------------------------


def test_missing_duration_while_keeping_end_does_not_succeed():
    with workspace() as ws:
        size, color = _even_size(), _rgb()
        finite = _make_color(ws, size, color, duration=2.0, fps=8)
        original_duration, original_end = finite.duration, finite.end
        failed = ws.call(finite.with_duration, None, change_end=False)
        failure = require_failed(failed)
        print(
            f"keep_end_missing={type(failure).__name__}: {failure} "
            f"orig_D={finite.duration} orig_end={finite.end} returned={failed.value!r}",
            flush=True,
        )
        assert failed.value is None
        assert finite.duration == pytest.approx(original_duration)
        assert finite.end == pytest.approx(original_end)

        moved = require_ok(ws.call(finite.with_duration, 0.8, change_end=True))
        assert moved.duration == pytest.approx(0.8)
        assert moved.end == pytest.approx(finite.start + 0.8)


# ---------------------------------------------------------------------------
# K. Package substrate negative control
# ---------------------------------------------------------------------------


def test_package_unimportable_subprocess_fails():
    code = """
from clipkit import ColorClip
clip = ColorClip((32, 24), color=(255, 0, 0), duration=0.4).with_fps(8)
frame = clip.get_frame(0)
print("SHAPE", tuple(int(v) for v in frame.shape))
print("PIXEL", int(frame[0, 0, 0]), int(frame[0, 0, 1]), int(frame[0, 0, 2]))
"""
    with workspace() as ws:
        hidden = ws.run_python(code=code, include_product=False, timeout=20.0)
        print(
            f"hidden rc={hidden.returncode} stderr={hidden.stderr_text[:400]!r}",
            flush=True,
        )
        assert hidden.returncode != 0

        present = ws.run_python(code=code, include_product=True, timeout=20.0)
        print(f"present rc={present.returncode} stdout={present.stdout_text!r}", flush=True)
        assert present.returncode == 0
        assert "PIXEL 255 0 0" in present.stdout_text
