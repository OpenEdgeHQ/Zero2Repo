# feature: F04
"""Cut, skip, and schedule on the timeline (FP-04).

Assertions stay at the PRD's precision: a time slice A→B has duration B−A
and the picture / soundtrack / mask at t is the source at A+t; omitting B
uses the source duration; the original is unchanged; negative bounds count
from the end; skipping C→D jumps from C to D and shortens by D−C; start and
end are a composition schedule, not a crop. Exception types, failure
wording, and method-name strings are not pinned.
"""

from __future__ import annotations

import secrets

import numpy as np
import pytest
from clipkit import (
    AudioClip,
    ColorClip,
    CompositeVideoClip,
    VideoClip,
)

from _harness import workspace
from _helpers import (
    dominant_picture_rgb,
    pictures_equal,
    require_failed,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
    require_sound_frame,
    samples_close,
)

_RED = (255, 0, 0)
_GREEN = (0, 255, 0)
_BLUE = (0, 0, 255)
_ORACLE_SIZE = (20, 16)
_ORACLE_DURATION = 3.0
_COMPOSE_WINDOW = 10.0


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _rect_size() -> tuple[int, int]:
    width = _rand_int(10, 18) * 2
    height = _rand_int(8, 14) * 2
    if width == height:
        height = width + 2
    return width, height


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(20, 230), _rand_int(20, 230), _rand_int(20, 230))


def _rgb_away_from(other: tuple[int, int, int]) -> tuple[int, int, int]:
    for _ in range(24):
        candidate = _rgb()
        if sum(abs(a - b) for a, b in zip(candidate, other)) > 90:
            return candidate
    return (255 - other[0], 255 - other[1], 255 - other[2])


def _scalar_t(t) -> float:
    return float(np.asarray(t).reshape(-1)[0])


def _require_duration(clip) -> float:
    value = clip.duration
    if value is None:
        raise AssertionError(
            "clip duration is absent; missing duration is not 0"
        )
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"clip duration is not numeric: {value!r}") from exc
    if seconds != seconds:
        raise AssertionError(f"clip duration is NaN: {value!r}")
    return seconds


def _soundtrack(clip):
    audio = clip.audio
    if audio is None:
        raise AssertionError("clip has no soundtrack")
    return audio


def _mask_of(clip):
    mask = clip.mask
    if mask is None:
        raise AssertionError("clip has no mask")
    return mask


def _frame(ws, clip, t):
    return require_ok(ws.call(clip.get_frame, t))


def _color(ws, size, color, duration=None):
    clip = require_ok(ws.call(ColorClip, size, color=color))
    if duration is not None:
        clip = require_ok(ws.call(clip.with_duration, duration))
    return clip


def _video(ws, fn, duration=None, *, is_mask=False):
    if duration is None:
        return require_ok(
            ws.call(VideoClip, frame_function=fn, is_mask=is_mask)
        )
    return require_ok(
        ws.call(VideoClip, frame_function=fn, duration=duration, is_mask=is_mask)
    )


def _audio(ws, fn, duration):
    return require_ok(ws.call(AudioClip, frame_function=fn, duration=duration))


def _overlay(ws, lower, upper):
    return require_ok(ws.call(CompositeVideoClip, [lower, upper]))


def _solid_fn(height: int, width: int, color: tuple[int, int, int]):
    def frame_function(t):
        picture = np.zeros((height, width, 3), dtype=np.uint8)
        picture[:, :] = np.asarray(color, dtype=np.uint8)
        return picture

    return frame_function


def _three_color_fn(height: int, width: int):
    def frame_function(t):
        moment = _scalar_t(t)
        if moment < 1.0:
            color = _RED
        elif moment < 2.0:
            color = _GREEN
        else:
            color = _BLUE
        picture = np.zeros((height, width, 3), dtype=np.uint8)
        picture[:, :] = np.asarray(color, dtype=np.uint8)
        return picture

    return frame_function


def _time_picture(height: int, width: int):
    """Picture that varies with t inside any kept interval (not a colour band)."""

    def frame_function(t):
        moment = _scalar_t(t)
        hundredths = max(0.0, moment) * 100.0
        lo = int(hundredths) % 256
        hi = (int(hundredths) // 256) % 256
        frac = int(np.clip((moment % 1.0) * 200.0, 0, 255))
        picture = np.zeros((height, width, 3), dtype=np.uint8)
        picture[:, :, 0] = lo
        picture[:, :, 1] = hi
        picture[:, :, 2] = frac
        return picture

    return frame_function


def _time_mask(height: int, width: int):
    def frame_function(t):
        moment = _scalar_t(t)
        level = 0.12 + 0.8 * ((moment % 7.0) / 7.0)
        return np.full((height, width), float(level), dtype=float)

    return frame_function


def _time_sound(t):
    moment = _scalar_t(t)
    return np.array(
        [np.sin(2.0 * np.pi * 3.25 * moment) + 0.08 * moment],
        dtype=float,
    )


def _attach_sound_and_mask(ws, clip, duration: float, height: int, width: int):
    soundtrack = _audio(ws, _time_sound, duration)
    mask = _video(ws, _time_mask(height, width), duration, is_mask=True)
    with_sound = require_ok(ws.call(clip.with_audio, soundtrack))
    return require_ok(ws.call(with_sound.with_mask, mask))


def _assert_no_clip_returned(result) -> None:
    if result.value is not None:
        raise AssertionError(
            "slice entry did not succeed, but still returned an object "
            f"that could yield frames: {result.value!r}"
        )


# ---------------------------------------------------------------------------
# A. Time slice A→B: duration B−A; frame at t is the source at A+t
# ---------------------------------------------------------------------------


def test_oracle_slice_one_to_two_is_green_duration_one():
    with workspace() as ws:
        fn = _three_color_fn(_ORACLE_SIZE[1], _ORACLE_SIZE[0])
        source = _video(ws, fn, _ORACLE_DURATION)
        sliced = require_ok(ws.call(source.subclipped, 1, 2))
        duration = _require_duration(sliced)
        frame = _frame(ws, sliced, 0.5)
        print(
            f"oracle_slice duration={duration} rgb={dominant_picture_rgb(frame)}",
            flush=True,
        )
        assert duration == pytest.approx(1)
        require_rgb_picture(frame, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_GREEN)
        assert not pictures_equal(frame, fn(0.5))
        assert not pictures_equal(frame, fn(2.5))
        assert pictures_equal(frame, fn(1.5))


def test_slice_maps_source_at_A_plus_t_runtime():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 4.6
        start_a = 1.3
        end_b = 3.05
        source = _video(ws, fn, source_duration)
        sliced = require_ok(ws.call(source.subclipped, start_a, end_b))
        duration = _require_duration(sliced)
        t1, t2 = 0.25, 1.15
        f1 = _frame(ws, sliced, t1)
        f2 = _frame(ws, sliced, t2)
        print(
            f"runtime_slice A={start_a} B={end_b} D={duration} "
            f"t1={t1} t2={t2} size=({width},{height})",
            flush=True,
        )
        require_rgb_picture(f1, height, width)
        require_rgb_picture(f2, height, width)
        assert duration == pytest.approx(end_b - start_a)
        assert duration != pytest.approx(int(end_b) - int(start_a))
        assert pictures_equal(f1, fn(start_a + t1))
        assert pictures_equal(f2, fn(start_a + t2))
        assert not pictures_equal(f1, f2)
        assert not pictures_equal(f1, fn(t1))
        assert not pictures_equal(f1, fn(int(start_a) + t1))
        assert not pictures_equal(fn(start_a), fn(int(start_a)))
        assert not pictures_equal(fn(end_b), fn(int(end_b)))


def test_omitting_end_uses_source_duration():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 3.8
        start_a = 1.15
        source = _video(ws, fn, source_duration)
        omitted = require_ok(ws.call(source.subclipped, start_a))
        explicit = require_ok(ws.call(source.subclipped, start_a, source_duration))
        omitted_d = _require_duration(omitted)
        explicit_d = _require_duration(explicit)
        t0 = _frame(ws, omitted, 0)
        t1 = 0.4
        t2 = 1.2
        print(
            f"omit_B A={start_a} source_D={source_duration} "
            f"omitted_D={omitted_d} explicit_D={explicit_d}",
            flush=True,
        )
        assert omitted_d == pytest.approx(source_duration - start_a)
        assert omitted_d == pytest.approx(explicit_d)
        assert pictures_equal(t0, fn(start_a))
        assert not pictures_equal(t0, fn(0))
        assert pictures_equal(_frame(ws, omitted, t1), fn(start_a + t1))
        assert pictures_equal(_frame(ws, omitted, t2), fn(start_a + t2))
        assert pictures_equal(_frame(ws, omitted, t1), _frame(ws, explicit, t1))
        assert pictures_equal(_frame(ws, omitted, t2), _frame(ws, explicit, t2))
        assert not pictures_equal(_frame(ws, omitted, t1), _frame(ws, omitted, t2))


def test_slice_leaves_original_unchanged():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 3.4
        start_a, end_b = 0.8, 2.1
        source = _video(ws, fn, source_duration)
        before_mid = _frame(ws, source, 0.4)
        before_at_a = _frame(ws, source, start_a)
        sliced = require_ok(ws.call(source.subclipped, start_a, end_b))
        after_duration = _require_duration(source)
        after_mid = _frame(ws, source, 0.4)
        after_at_a = _frame(ws, source, start_a)
        print(
            f"original_unchanged source_D={after_duration} "
            f"slice_D={_require_duration(sliced)} same_object={sliced is source}",
            flush=True,
        )
        assert sliced is not source
        assert after_duration == pytest.approx(source_duration)
        assert pictures_equal(after_mid, before_mid)
        assert pictures_equal(after_at_a, before_at_a)
        assert pictures_equal(after_mid, fn(0.4))
        assert not pictures_equal(_frame(ws, sliced, 0), fn(0))


def test_slice_bounds_accept_time_encodings():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 85.0
        # PRD pair (minutes, seconds) and HMS clock; minutes field is non-zero.
        a_seconds = 1 * 60 + 10.5
        b_seconds = 1 * 60 + 18.0
        pair_a = (1, 10.5)
        pair_b = (1, 18)
        clock_a = "00:01:10.5"
        clock_b = "00:01:18"
        source = _video(ws, fn, source_duration)
        numeric = require_ok(ws.call(source.subclipped, a_seconds, b_seconds))
        as_pair = require_ok(ws.call(source.subclipped, pair_a, pair_b))
        as_clock = require_ok(ws.call(source.subclipped, clock_a, clock_b))
        omitted = require_ok(ws.call(source.subclipped, pair_a))
        numeric_d = _require_duration(numeric)
        pair_d = _require_duration(as_pair)
        clock_d = _require_duration(as_clock)
        omitted_d = _require_duration(omitted)
        t1, t2 = 0.2, 3.4
        last_field = 10.5
        unweighted = 0 + 1 + 10.5
        print(
            f"encodings a={a_seconds} b={b_seconds} numeric_D={numeric_d} "
            f"pair_D={pair_d} clock_D={clock_d} omit_D={omitted_d}",
            flush=True,
        )
        expected = b_seconds - a_seconds
        assert numeric_d == pytest.approx(expected)
        assert pair_d == pytest.approx(expected)
        assert clock_d == pytest.approx(expected)
        assert omitted_d == pytest.approx(source_duration - a_seconds)
        assert omitted_d != pytest.approx(source_duration - last_field)
        assert omitted_d != pytest.approx(source_duration - unweighted)
        for clip in (numeric, as_pair, as_clock):
            assert pictures_equal(_frame(ws, clip, t1), fn(a_seconds + t1))
            assert pictures_equal(_frame(ws, clip, t2), fn(a_seconds + t2))
        assert pictures_equal(_frame(ws, omitted, 0), fn(a_seconds))
        assert not pictures_equal(_frame(ws, omitted, 0), fn(last_field))
        assert not pictures_equal(_frame(ws, omitted, 0), fn(unweighted))
        assert not pictures_equal(_frame(ws, omitted, 0), fn(0))
        assert not pictures_equal(
            _frame(ws, numeric, t1), _frame(ws, numeric, t2)
        )


def test_slice_maps_soundtrack_and_mask():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 5.2
        source = _attach_sound_and_mask(
            ws, _video(ws, fn, source_duration), source_duration, height, width
        )
        orig_sound_t = 1.1
        orig_mask_t = 2.4
        orig_sound = require_sound_frame(
            _frame(ws, _soundtrack(source), orig_sound_t), 1
        )
        orig_mask = require_mask_picture(
            _frame(ws, _mask_of(source), orig_mask_t), height, width
        )

        start_a, end_b = 1.15, 3.4
        sliced = require_ok(ws.call(source.subclipped, start_a, end_b))
        t1, t2 = 0.3, 1.6
        sound = _soundtrack(sliced)
        mask = _mask_of(sliced)
        s1 = require_sound_frame(_frame(ws, sound, t1), 1)
        s2 = require_sound_frame(_frame(ws, sound, t2), 1)
        m1 = require_mask_picture(_frame(ws, mask, t1), height, width)
        m2 = require_mask_picture(_frame(ws, mask, t2), height, width)
        print(
            f"slice_streams A={start_a} B={end_b} t1={t1} t2={t2}",
            flush=True,
        )
        assert samples_close(s1, _time_sound(start_a + t1))
        assert samples_close(s2, _time_sound(start_a + t2))
        assert not samples_close(s1, s2)
        assert pictures_equal(m1, _time_mask(height, width)(start_a + t1))
        assert pictures_equal(m2, _time_mask(height, width)(start_a + t2))
        assert not pictures_equal(m1, m2)
        assert samples_close(
            require_sound_frame(_frame(ws, _soundtrack(source), orig_sound_t), 1),
            orig_sound,
        )
        assert pictures_equal(
            require_mask_picture(
                _frame(ws, _mask_of(source), orig_mask_t), height, width
            ),
            orig_mask,
        )

        omitted = require_ok(ws.call(source.subclipped, start_a))
        o1, o2 = 0.2, 2.1
        assert samples_close(
            require_sound_frame(_frame(ws, _soundtrack(omitted), o1), 1),
            _time_sound(start_a + o1),
        )
        assert samples_close(
            require_sound_frame(_frame(ws, _soundtrack(omitted), o2), 1),
            _time_sound(start_a + o2),
        )
        assert pictures_equal(
            require_mask_picture(_frame(ws, _mask_of(omitted), o1), height, width),
            _time_mask(height, width)(start_a + o1),
        )
        assert pictures_equal(
            require_mask_picture(_frame(ws, _mask_of(omitted), o2), height, width),
            _time_mask(height, width)(start_a + o2),
        )
        assert not samples_close(
            require_sound_frame(_frame(ws, _soundtrack(omitted), o1), 1),
            require_sound_frame(_frame(ws, _soundtrack(omitted), o2), 1),
        )

        neg_x, neg_y = -3.4, -1.1
        mapped_start = source_duration + neg_x
        negative = require_ok(ws.call(source.subclipped, neg_x, neg_y))
        n1, n2 = 0.25, 1.4
        print(
            f"slice_streams_negative X={-neg_x} Y={-neg_y} "
            f"mapped_start={mapped_start}",
            flush=True,
        )
        assert samples_close(
            require_sound_frame(_frame(ws, _soundtrack(negative), n1), 1),
            _time_sound(mapped_start + n1),
        )
        assert samples_close(
            require_sound_frame(_frame(ws, _soundtrack(negative), n2), 1),
            _time_sound(mapped_start + n2),
        )
        assert pictures_equal(
            require_mask_picture(
                _frame(ws, _mask_of(negative), n1), height, width
            ),
            _time_mask(height, width)(mapped_start + n1),
        )
        assert pictures_equal(
            require_mask_picture(
                _frame(ws, _mask_of(negative), n2), height, width
            ),
            _time_mask(height, width)(mapped_start + n2),
        )
        assert not pictures_equal(
            require_mask_picture(
                _frame(ws, _mask_of(negative), n1), height, width
            ),
            require_mask_picture(
                _frame(ws, _mask_of(negative), n2), height, width
            ),
        )


def test_slice_audio_clip_samples():
    with workspace() as ws:
        source_duration = 3.6
        start_a, end_b = 0.85, 2.4
        source = _audio(ws, _time_sound, source_duration)
        before_mid = require_sound_frame(_frame(ws, source, 1.4), 1)
        sliced = require_ok(ws.call(source.subclipped, start_a, end_b))
        duration = _require_duration(sliced)
        t1, t2 = 0.2, 1.05
        s1 = require_sound_frame(_frame(ws, sliced, t1), 1)
        s2 = require_sound_frame(_frame(ws, sliced, t2), 1)
        after_mid = require_sound_frame(_frame(ws, source, 1.4), 1)
        print(
            f"audio_slice A={start_a} B={end_b} D={duration} t1={t1} t2={t2}",
            flush=True,
        )
        assert sliced is not source
        assert duration == pytest.approx(end_b - start_a)
        assert samples_close(s1, _time_sound(start_a + t1))
        assert samples_close(s2, _time_sound(start_a + t2))
        assert not samples_close(s1, s2)
        assert not samples_close(s1, _time_sound(t1))
        assert samples_close(after_mid, before_mid)
        assert samples_close(after_mid, _time_sound(1.4))
        assert _require_duration(source) == pytest.approx(source_duration)


# ---------------------------------------------------------------------------
# B. Negative A or B count from the end
# ---------------------------------------------------------------------------


def test_oracle_slice_minus_one_to_end_is_blue():
    with workspace() as ws:
        fn = _three_color_fn(_ORACLE_SIZE[1], _ORACLE_SIZE[0])
        source = _video(ws, fn, _ORACLE_DURATION)
        sliced = require_ok(ws.call(source.subclipped, -1))
        duration = _require_duration(sliced)
        frame = _frame(ws, sliced, 0.5)
        print(
            f"oracle_neg_end duration={duration} rgb={dominant_picture_rgb(frame)}",
            flush=True,
        )
        assert duration == pytest.approx(1)
        require_rgb_picture(frame, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_BLUE)
        assert pictures_equal(frame, fn(2.5))
        assert not pictures_equal(frame, fn(0.5))


def test_slice_zero_to_minus_two_drops_last_two_seconds():
    with workspace() as ws:
        fn = _three_color_fn(_ORACLE_SIZE[1], _ORACLE_SIZE[0])
        source = _video(ws, fn, _ORACLE_DURATION)
        sliced = require_ok(ws.call(source.subclipped, 0, -2))
        duration = _require_duration(sliced)
        frame = _frame(ws, sliced, 0.5)
        print(
            f"oracle_drop_last_two duration={duration} "
            f"rgb={dominant_picture_rgb(frame)}",
            flush=True,
        )
        assert duration == pytest.approx(1)
        require_rgb_picture(frame, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_RED)
        assert pictures_equal(frame, fn(0.5))
        assert not pictures_equal(frame, fn(1.5))
        assert not pictures_equal(frame, fn(2.5))


def test_negative_slice_bounds_count_from_end_runtime():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 5.0
        neg_x, neg_y = 3.4, 1.1
        mapped_start = source_duration - neg_x
        mapped_end = source_duration - neg_y
        source = _video(ws, fn, source_duration)
        negative = require_ok(ws.call(source.subclipped, -neg_x, -neg_y))
        positive = require_ok(
            ws.call(source.subclipped, mapped_start, mapped_end)
        )
        duration = _require_duration(negative)
        t1, t2 = 0.3, 1.55
        n1 = _frame(ws, negative, t1)
        n2 = _frame(ws, negative, t2)
        print(
            f"neg_runtime D={source_duration} X={neg_x} Y={neg_y} "
            f"result_D={duration} window=({mapped_start},{mapped_end})",
            flush=True,
        )
        require_rgb_picture(n1, height, width)
        require_rgb_picture(n2, height, width)
        assert duration == pytest.approx(neg_x - neg_y)
        assert duration == pytest.approx(_require_duration(positive))
        assert pictures_equal(n1, fn(mapped_start + t1))
        assert pictures_equal(n2, fn(mapped_start + t2))
        assert pictures_equal(n1, _frame(ws, positive, t1))
        assert pictures_equal(n2, _frame(ws, positive, t2))
        assert not pictures_equal(n1, n2)
        assert not pictures_equal(n1, fn(t1))
        assert not pictures_equal(n1, fn(neg_x + t1))
        assert not pictures_equal(n1, fn(neg_y + t1))
        assert not pictures_equal(n1, fn(source_duration - t1))


# ---------------------------------------------------------------------------
# C. Skip open interval C→D
# ---------------------------------------------------------------------------


def test_oracle_skip_one_to_two_red_then_blue_duration_two():
    with workspace() as ws:
        fn = _three_color_fn(_ORACLE_SIZE[1], _ORACLE_SIZE[0])
        source = _video(ws, fn, _ORACLE_DURATION)
        skipped = require_ok(ws.call(source.with_section_cut_out, 1, 2))
        duration = _require_duration(skipped)
        before = _frame(ws, skipped, 0.5)
        delta = 0.05
        just_after = _frame(ws, skipped, 1 + delta)
        later = _frame(ws, skipped, 1.5)
        stretch_t = (1 + delta) * (_ORACLE_DURATION / 2.0)
        print(
            f"oracle_skip D={duration} before={dominant_picture_rgb(before)} "
            f"join={dominant_picture_rgb(just_after)} later={dominant_picture_rgb(later)}",
            flush=True,
        )
        assert duration == pytest.approx(2)
        require_rgb_picture(before, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_RED)
        require_rgb_picture(
            just_after, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_BLUE
        )
        require_rgb_picture(later, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=_BLUE)
        assert pictures_equal(just_after, fn(2 + delta))
        assert not pictures_equal(just_after, fn(1 + delta))
        assert not pictures_equal(just_after, fn(stretch_t))
        assert pictures_equal(before, fn(0.5))


def test_skip_jumps_from_C_to_D_runtime():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 5.0
        skip_c, skip_d = 1.4, 3.2
        hole = skip_d - skip_c
        source = _video(ws, fn, source_duration)
        skipped = require_ok(
            ws.call(source.with_section_cut_out, skip_c, skip_d)
        )
        duration = _require_duration(skipped)
        delta = 0.08
        before_t = 0.7
        join_t = skip_c + delta
        later_t = skip_c + 0.95
        stretch_join = join_t * (source_duration / duration)
        before = _frame(ws, skipped, before_t)
        join = _frame(ws, skipped, join_t)
        later = _frame(ws, skipped, later_t)
        print(
            f"skip_runtime C={skip_c} D={skip_d} hole={hole} "
            f"result_D={duration} join_t={join_t} later_t={later_t}",
            flush=True,
        )
        assert hole != pytest.approx(1)
        assert hole != pytest.approx(skip_c)
        assert duration == pytest.approx(source_duration - hole)
        assert duration != pytest.approx(source_duration - skip_c)
        assert duration != pytest.approx(source_duration - 1)
        require_rgb_picture(before, height, width)
        require_rgb_picture(join, height, width)
        assert pictures_equal(before, fn(before_t))
        assert pictures_equal(join, fn(skip_d + delta))
        assert not pictures_equal(join, fn(join_t))
        assert not pictures_equal(join, fn(stretch_join))
        assert pictures_equal(later, fn(later_t + hole))
        assert not pictures_equal(join, later)
        assert not pictures_equal(later, fn(skip_d))


def test_skip_maps_soundtrack_and_mask():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 5.0
        skip_c, skip_d = 1.4, 3.2
        hole = skip_d - skip_c
        source = _attach_sound_and_mask(
            ws, _video(ws, fn, source_duration), source_duration, height, width
        )
        skipped = require_ok(
            ws.call(source.with_section_cut_out, skip_c, skip_d)
        )
        delta = 0.08
        before_t = 0.55
        join_t = skip_c + delta
        sound = _soundtrack(skipped)
        mask = _mask_of(skipped)
        s_before = require_sound_frame(_frame(ws, sound, before_t), 1)
        s_join = require_sound_frame(_frame(ws, sound, join_t), 1)
        m_before = require_mask_picture(_frame(ws, mask, before_t), height, width)
        m_join = require_mask_picture(_frame(ws, mask, join_t), height, width)
        print(
            f"skip_streams C={skip_c} D={skip_d} before={before_t} join={join_t}",
            flush=True,
        )
        assert samples_close(s_before, _time_sound(before_t))
        assert samples_close(s_join, _time_sound(skip_d + delta))
        assert not samples_close(s_join, _time_sound(join_t))
        assert pictures_equal(m_before, _time_mask(height, width)(before_t))
        assert pictures_equal(m_join, _time_mask(height, width)(skip_d + delta))
        assert not pictures_equal(m_join, _time_mask(height, width)(join_t))
        mid_sound = _time_sound((skip_c + skip_d) / 2.0)
        mid_mask = _time_mask(height, width)((skip_c + skip_d) / 2.0)
        assert not samples_close(s_join, mid_sound)
        assert not pictures_equal(m_join, mid_mask)


def test_skip_leaves_original_unchanged():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 4.2
        skip_c, skip_d = 1.1, 2.6
        source = _video(ws, fn, source_duration)
        mid_t = (skip_c + skip_d) / 2.0
        before_mid = _frame(ws, source, mid_t)
        skipped = require_ok(
            ws.call(source.with_section_cut_out, skip_c, skip_d)
        )
        after_duration = _require_duration(source)
        after_mid = _frame(ws, source, mid_t)
        print(
            f"skip_original source_D={after_duration} "
            f"skip_D={_require_duration(skipped)} mid_t={mid_t}",
            flush=True,
        )
        assert skipped is not source
        assert after_duration == pytest.approx(source_duration)
        assert pictures_equal(after_mid, before_mid)
        assert pictures_equal(after_mid, fn(mid_t))
        join = _frame(ws, skipped, skip_c + 0.05)
        assert not pictures_equal(join, fn(mid_t))


def test_skip_audio_clip_samples():
    with workspace() as ws:
        source_duration = 4.4
        skip_c, skip_d = 1.15, 2.85
        hole = skip_d - skip_c
        source = _audio(ws, _time_sound, source_duration)
        mid_t = (skip_c + skip_d) / 2.0
        before_mid = require_sound_frame(_frame(ws, source, mid_t), 1)
        skipped = require_ok(
            ws.call(source.with_section_cut_out, skip_c, skip_d)
        )
        duration = _require_duration(skipped)
        delta = 0.07
        join = require_sound_frame(_frame(ws, skipped, skip_c + delta), 1)
        before = require_sound_frame(_frame(ws, skipped, 0.4), 1)
        after_mid = require_sound_frame(_frame(ws, source, mid_t), 1)
        print(
            f"audio_skip C={skip_c} D={skip_d} hole={hole} D_out={duration}",
            flush=True,
        )
        assert hole != pytest.approx(1)
        assert hole != pytest.approx(skip_c)
        assert duration == pytest.approx(source_duration - hole)
        assert samples_close(before, _time_sound(0.4))
        assert samples_close(join, _time_sound(skip_d + delta))
        assert not samples_close(join, _time_sound(skip_c + delta))
        assert not samples_close(join, _time_sound(mid_t))
        assert samples_close(after_mid, before_mid)
        assert samples_close(after_mid, _time_sound(mid_t))
        assert _require_duration(source) == pytest.approx(source_duration)


# ---------------------------------------------------------------------------
# D. start/end are composition schedule, not a crop
# ---------------------------------------------------------------------------


def test_oracle_layer_start_five_absent_at_four_present_at_five():
    with workspace() as ws:
        lower_color = (20, 40, 180)
        upper_color = (220, 30, 30)
        lower = _color(ws, _ORACLE_SIZE, lower_color, duration=_COMPOSE_WINDOW)
        upper = _color(ws, _ORACLE_SIZE, upper_color, duration=_COMPOSE_WINDOW)
        delayed = require_ok(ws.call(upper.with_start, 5))
        composition = _overlay(ws, lower, delayed)
        absent = _frame(ws, composition, 4)
        present = _frame(ws, composition, 5)
        print(
            f"oracle_schedule t4={dominant_picture_rgb(absent)} "
            f"t5={dominant_picture_rgb(present)}",
            flush=True,
        )
        require_rgb_picture(
            absent, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=lower_color
        )
        require_rgb_picture(
            present, _ORACLE_SIZE[1], _ORACLE_SIZE[0], color=upper_color
        )
        assert not pictures_equal(absent, present)


def test_start_delays_first_frame_does_not_crop():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        lower_color = _rgb()
        source_duration = 8.0
        start_s = 4.25
        epsilon = 0.25
        after_delta = 0.25
        lower = _color(ws, (width, height), lower_color, duration=_COMPOSE_WINDOW)
        upper = _video(ws, fn, source_duration)
        delayed = require_ok(ws.call(upper.with_start, start_s))
        composition = _overlay(ws, lower, delayed)
        baseline = require_ok(ws.call(upper.with_start, 0))
        live = _overlay(ws, lower, baseline)
        before_t = start_s - epsilon
        after_t = start_s + after_delta
        at_start = _frame(ws, composition, start_s)
        before = _frame(ws, composition, before_t)
        after = _frame(ws, composition, after_t)
        live_before = _frame(ws, live, before_t)
        truncated_t = float(int(start_s)) + 0.125
        print(
            f"anti_crop S={start_s} before={before_t} after={after_t} "
            f"truncated={truncated_t} size=({width},{height})",
            flush=True,
        )
        require_rgb_picture(at_start, height, width)
        require_rgb_picture(
            before, height, width, color=lower_color
        )
        assert pictures_equal(at_start, fn(0))
        assert not pictures_equal(at_start, fn(start_s))
        assert pictures_equal(after, fn(after_delta))
        assert not pictures_equal(before, at_start)
        assert pictures_equal(live_before, fn(before_t))
        assert not pictures_equal(live_before, before)
        assert not pictures_equal(fn(start_s), fn(int(start_s)))
        truncated = _frame(ws, composition, truncated_t)
        require_rgb_picture(truncated, height, width, color=lower_color)


def test_end_stops_layer_strictly_before_end():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        lower_color = _rgb()
        source_duration = 8.0
        start_s = 2.5
        end_e = 6.5
        epsilon = 0.125
        assert end_e < _COMPOSE_WINDOW
        assert (end_e - start_s) < source_duration
        lower = _color(ws, (width, height), lower_color, duration=_COMPOSE_WINDOW)
        upper = _video(ws, fn, source_duration)
        started = require_ok(ws.call(upper.with_start, start_s))
        scheduled = require_ok(ws.call(started.with_end, end_e))
        composition = _overlay(ws, lower, scheduled)
        baseline = require_ok(ws.call(upper.with_start, 0))
        live = _overlay(ws, lower, baseline)
        at_start = _frame(ws, composition, start_s)
        near_end_t = end_e - epsilon
        near_end = _frame(ws, composition, near_end_t)
        before_start = _frame(ws, composition, start_s - epsilon)
        at_end = _frame(ws, composition, end_e)
        live_before = _frame(ws, live, start_s - epsilon)
        local_near = near_end_t - start_s
        print(
            f"half_open S={start_s} E={end_e} near_t={near_end_t} "
            f"near_local={local_near}",
            flush=True,
        )
        require_rgb_picture(at_start, height, width)
        require_rgb_picture(before_start, height, width, color=lower_color)
        require_rgb_picture(at_end, height, width, color=lower_color)
        assert pictures_equal(at_start, fn(0))
        assert pictures_equal(near_end, fn(local_near))
        assert not pictures_equal(near_end, fn(end_e))
        assert not pictures_equal(near_end, fn(end_e - epsilon))
        assert not pictures_equal(before_start, at_start)
        assert not pictures_equal(at_end, near_end)
        assert pictures_equal(live_before, fn(start_s - epsilon))


def test_absent_end_plays_from_start_onward():
    with workspace() as ws:
        width, height = _rect_size()
        lower_color = _rgb()
        upper_color = _rgb_away_from(lower_color)
        start_s = 3.25
        earlier_end = 6.0
        late_t = 9.5
        epsilon = 0.2
        lower = _color(ws, (width, height), lower_color, duration=_COMPOSE_WINDOW)
        infinite = _color(ws, (width, height), upper_color)
        delayed = require_ok(ws.call(infinite.with_start, start_s))
        composition = _overlay(ws, lower, delayed)
        sibling_base = _color(ws, (width, height), upper_color)
        sibling_started = require_ok(ws.call(sibling_base.with_start, start_s))
        sibling_ended = require_ok(ws.call(sibling_started.with_end, earlier_end))
        contrast = _overlay(ws, lower, sibling_ended)
        before = _frame(ws, composition, start_s - epsilon)
        at_start = _frame(ws, composition, start_s)
        late = _frame(ws, composition, late_t)
        contrast_late = _frame(ws, contrast, late_t)
        print(
            f"absent_end S={start_s} late={late_t} "
            f"at_start={dominant_picture_rgb(at_start)} "
            f"late_rgb={dominant_picture_rgb(late)} "
            f"sibling_late={dominant_picture_rgb(contrast_late)}",
            flush=True,
        )
        require_rgb_picture(before, height, width, color=lower_color)
        require_rgb_picture(at_start, height, width, color=upper_color)
        require_rgb_picture(late, height, width, color=upper_color)
        require_rgb_picture(contrast_late, height, width, color=lower_color)
        assert not pictures_equal(before, at_start)
        assert not pictures_equal(late, contrast_late)


# ---------------------------------------------------------------------------
# E. Slice refusals
# ---------------------------------------------------------------------------


def test_slice_start_at_or_after_duration_does_not_succeed():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 4.0
        delta = 1.6
        source = _video(ws, fn, source_duration)
        at_omit = ws.call(source.subclipped, source_duration)
        at_equal = ws.call(source.subclipped, source_duration, source_duration)
        after = ws.call(source.subclipped, source_duration + delta)
        print(
            f"start_at_after D={source_duration} delta={delta} "
            f"at_omit_failed={at_omit.exception is not None} "
            f"at_equal_failed={at_equal.exception is not None} "
            f"after_failed={after.exception is not None}",
            flush=True,
        )
        require_failed(at_omit)
        _assert_no_clip_returned(at_omit)
        require_failed(at_equal)
        _assert_no_clip_returned(at_equal)
        require_failed(after)
        _assert_no_clip_returned(after)

        sibling_start = source_duration - 0.35
        sibling = require_ok(ws.call(source.subclipped, sibling_start))
        sibling_d = _require_duration(sibling)
        local = _frame(ws, sibling, 0.1)
        print(f"start_sibling A={sibling_start} D={sibling_d}", flush=True)
        assert sibling_d == pytest.approx(source_duration - sibling_start)
        assert pictures_equal(local, fn(sibling_start + 0.1))
        assert not pictures_equal(local, fn(0.1))


def test_slice_end_past_duration_does_not_succeed():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        source_duration = 3.5
        overshoot = 3.0
        source = _video(ws, fn, source_duration)
        equal = require_ok(ws.call(source.subclipped, 0, source_duration))
        equal_d = _require_duration(equal)
        past = ws.call(source.subclipped, 0, source_duration + overshoot)
        print(
            f"end_past D={source_duration} equal_D={equal_d} "
            f"overshoot={overshoot} past_failed={past.exception is not None}",
            flush=True,
        )
        assert equal_d == pytest.approx(source_duration)
        assert pictures_equal(_frame(ws, equal, 1.2), fn(1.2))
        require_failed(past)
        _assert_no_clip_returned(past)


def test_negative_slice_bound_without_duration_does_not_succeed():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        fn = _time_picture(height, width)
        still = _color(ws, (width, height), color)
        generated = _video(ws, fn)
        assert still.duration is None
        assert generated.duration is None

        for label, clip in (("color", still), ("generated", generated)):
            neg_start = ws.call(clip.subclipped, -1.2)
            neg_end = ws.call(clip.subclipped, 0, -1.2)
            print(
                f"no_duration_{label} neg_A_failed={neg_start.exception is not None} "
                f"neg_B_failed={neg_end.exception is not None}",
                flush=True,
            )
            require_failed(neg_start)
            _assert_no_clip_returned(neg_start)
            require_failed(neg_end)
            _assert_no_clip_returned(neg_end)

        assigned_d = 4.0
        still_timed = require_ok(ws.call(still.with_duration, assigned_d))
        gen_timed = require_ok(ws.call(generated.with_duration, assigned_d))
        still_from_end = require_ok(ws.call(still_timed.subclipped, -1.2))
        still_drop = require_ok(ws.call(still_timed.subclipped, 0, -1.2))
        gen_from_end = require_ok(ws.call(gen_timed.subclipped, -1.2))
        gen_drop = require_ok(ws.call(gen_timed.subclipped, 0, -1.2))
        print(
            f"duration_then_negative still_end_D={_require_duration(still_from_end)} "
            f"gen_end_D={_require_duration(gen_from_end)}",
            flush=True,
        )
        assert _require_duration(still_from_end) == pytest.approx(1.2)
        assert _require_duration(still_drop) == pytest.approx(assigned_d - 1.2)
        require_rgb_picture(
            _frame(ws, still_from_end, 0.4), height, width, color=color
        )
        assert _require_duration(gen_from_end) == pytest.approx(1.2)
        assert _require_duration(gen_drop) == pytest.approx(assigned_d - 1.2)
        t_local = 0.35
        assert pictures_equal(
            _frame(ws, gen_from_end, t_local),
            fn(assigned_d - 1.2 + t_local),
        )
        assert pictures_equal(_frame(ws, gen_drop, t_local), fn(t_local))
        assert not pictures_equal(
            _frame(ws, gen_from_end, t_local), fn(t_local)
        )
        assert not pictures_equal(
            _frame(ws, gen_drop, t_local), fn(assigned_d - 1.2 + t_local)
        )
