# feature: F06
"""Overlay, concatenate, and juxtapose (FP-06).

Assertions stay at the PRD's precision: list-order and layer-index stacking,
canvas size and fill, designated background, play windows, opaque replace and
partial-opacity blend, overlay duration as max end when every layer has an
end, max of existing frame rates, mixed soundtracks, chain vs compose
geometry, padding and transition duration, grid cell layout, audio overlay
and concatenate, and the three refusals. Exception types, failure wording,
blend formulas, and chain-gap pixels are not pinned.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import numpy as np
import pytest
from clipkit import (
    AudioArrayClip,
    AudioClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    VideoClip,
    clips_array,
    concatenate_audioclips,
    concatenate_videoclips,
)

from _harness import HarnessError, workspace
from _helpers import (
    as_numeric_array,
    failure_identifies_missing_duration,
    failure_remainder,
    media_file_nonempty,
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
_BLACK = (0, 0, 0)
_PCM_RATE = 44100


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _even(lo: int, hi: int) -> int:
    return _rand_int(lo, hi) * 2


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(40, 220), _rand_int(40, 220), _rand_int(40, 220))


def _rgb_away_from(*others: tuple[int, int, int]) -> tuple[int, int, int]:
    banned = others + (_BLACK,)
    for _ in range(48):
        candidate = _rgb()
        if all(sum(abs(a - b) for a, b in zip(candidate, other)) > 90 for other in banned):
            return candidate
    return (220, 40, 180)


def _picture_rgb(frame) -> np.ndarray:
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise AssertionError(
            f"expected a picture with at least 3 channels; got shape {arr.shape}"
        )
    return arr[:, :, :3]


def _frame_hw(frame) -> tuple[int, int]:
    arr = as_numeric_array(frame)
    if arr.ndim < 2:
        raise AssertionError(f"frame has no spatial axes; shape={arr.shape!r}")
    return int(arr.shape[0]), int(arr.shape[1])


def _rgb_at(frame, x: int, y: int) -> tuple[int, int, int]:
    rgb = _picture_rgb(frame)
    height, width = rgb.shape[0], rgb.shape[1]
    if not (0 <= x < width and 0 <= y < height):
        raise AssertionError(f"pixel ({x}, {y}) is outside {width}x{height}")
    pix = rgb[y, x].astype(float)
    return (int(round(pix[0])), int(round(pix[1])), int(round(pix[2])))


def _colors_close(got, color, *, atol: int) -> bool:
    return all(abs(a - b) <= atol for a, b in zip(got, color))


def _assert_color_at(frame, x: int, y: int, color, *, atol: int = 0):
    got = _rgb_at(frame, x, y)
    if not _colors_close(got, color, atol=atol):
        raise AssertionError(
            f"pixel ({x}, {y}) is {got}, expected {color} atol={atol}"
        )


def _assert_not_color_at(frame, x: int, y: int, color, *, atol: int = 12):
    got = _rgb_at(frame, x, y)
    if _colors_close(got, color, atol=atol):
        raise AssertionError(
            f"pixel ({x}, {y}) is {got}, which matches {color} atol={atol}"
        )


def _centered_origin(canvas_w: int, canvas_h: int, clip_w: int, clip_h: int):
    if clip_w > canvas_w or clip_h > canvas_h:
        raise AssertionError(
            f"clip {clip_w}x{clip_h} does not fit canvas {canvas_w}x{canvas_h}"
        )
    return (canvas_w - clip_w) // 2, (canvas_h - clip_h) // 2


def _interior_off_center(x: int, y: int, w: int, h: int) -> tuple[int, int]:
    if w < 4 or h < 4:
        raise AssertionError(f"clip {w}x{h} is too small to probe off-center")
    px = x + max(1, w // 4)
    py = y + max(1, h // 4)
    cx, cy = x + w // 2, y + h // 2
    if (px, py) == (cx, cy):
        px = x + 1
        py = y + 1
    return px, py


def _just_outside_rect(x: int, y: int, w: int, h: int, canvas_w: int, canvas_h: int):
    cy = y + h // 2
    if x > 0:
        return x - 1, cy
    if x + w < canvas_w:
        return x + w, cy
    cx = x + w // 2
    if y > 0:
        return cx, y - 1
    if y + h < canvas_h:
        return cx, y + h
    raise AssertionError("centered rectangle leaves no outside pixel on the canvas")


def _duration_or_missing(clip) -> float | None:
    value = clip.duration
    if value is None:
        return None
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"clip duration is not numeric: {value!r}") from exc
    if seconds != seconds:
        raise AssertionError(f"clip duration is NaN: {value!r}")
    return seconds


def _require_duration(clip) -> float:
    seconds = _duration_or_missing(clip)
    if seconds is None:
        raise AssertionError("clip duration is absent; missing duration is not 0")
    return seconds


def _fps_or_missing(clip) -> float | None:
    if not hasattr(clip, "fps"):
        return None
    value = clip.fps
    if value is None:
        return None
    try:
        rate = float(value)
    except (TypeError, ValueError) as exc:
        raise AssertionError(f"frame rate is not numeric: {value!r}") from exc
    if rate != rate:
        raise AssertionError(f"frame rate is NaN: {value!r}")
    if rate <= 0:
        raise AssertionError(f"frame rate is not positive: {rate!r}")
    return rate


def _require_fps(clip) -> float:
    rate = _fps_or_missing(clip)
    if rate is None:
        raise AssertionError("clip frame rate is absent; missing is not 0")
    return rate


def _frame(ws, clip, t=0.0):
    return require_ok(ws.call(clip.get_frame, t))


def _color(ws, size, color, duration=None, fps=None):
    clip = require_ok(ws.call(ColorClip, size, color=color))
    if duration is not None:
        clip = require_ok(ws.call(clip.with_duration, duration))
    if fps is not None:
        clip = require_ok(ws.call(clip.with_fps, fps))
    return clip


def _video(ws, fn, duration=None, *, is_mask=False):
    if duration is None:
        return require_ok(ws.call(VideoClip, frame_function=fn, is_mask=is_mask))
    return require_ok(
        ws.call(VideoClip, frame_function=fn, duration=duration, is_mask=is_mask)
    )


def _overlay(ws, clips, **kwargs):
    return require_ok(ws.call(CompositeVideoClip, clips, **kwargs))


def _concat(ws, clips, **kwargs):
    return require_ok(ws.call(concatenate_videoclips, clips, **kwargs))


def _grid(ws, rows, **kwargs):
    return require_ok(ws.call(clips_array, rows, **kwargs))


def _audio_overlay(ws, clips):
    return require_ok(ws.call(CompositeAudioClip, clips))


def _audio_concat(ws, clips):
    return require_ok(ws.call(concatenate_audioclips, clips))


def _tone_fn(freq: float, amp: float = 0.85, phase: float = 0.37):
    # Integer Hz at integer (or half-period) seconds collapse every tone
    # to amp*sin(phase), so two frequencies become indistinguishable.
    detuned = float(freq) + 0.13

    def frame_function(t):
        tt = float(np.asarray(t).reshape(-1)[0])
        return np.array(
            [amp * np.sin(2.0 * np.pi * detuned * tt + phase)], dtype=float
        )

    return frame_function


def _tone(ws, freq: float, duration: float, *, fps: float = _PCM_RATE):
    return require_ok(
        ws.call(AudioClip, frame_function=_tone_fn(freq), duration=duration, fps=fps)
    )


def _sound(ws, clip, t, channels=1):
    return require_sound_frame(_frame(ws, clip, t), channels)


def _mask_value(ws, clip, x: int, y: int, t=0.0) -> float | None:
    mask = clip.mask
    if mask is None:
        return None
    picture = _frame(ws, clip, t)
    height, width = _frame_hw(picture)
    arr = require_mask_picture(_frame(ws, mask, t), height, width)
    return float(arr[y, x])


def _complete_media(path: Path) -> bool:
    try:
        present = path.is_file()
    except OSError as exc:
        raise HarnessError(f"cannot stat {path}: {exc}") from exc
    if not present:
        return False
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat {path}: {exc}") from exc
    return size > 0


def _block_mask_fn(height: int, width: int, y0: int, y1: int, x0: int, x1: int):
    def frame_function(t):
        pic = np.zeros((height, width), dtype=float)
        pic[y0:y1, x0:x1] = 1.0
        return pic

    return frame_function


def _find_overlap_t(ws, first, second, mixed, start: float, end: float):
    """Pick an overlap instant that is not sequenced and not silent.

    Equal-amplitude sines can cancel at a random t. Skip first-only,
    second-only, and silence so a correct play-together mix cannot go red
    on one unlucky sample. This is not the mix-together oracle: a canned
    third signal also survives these skips. Mixing formula is not pinned.
    """
    span = end - start
    if span <= 0:
        raise AssertionError(f"overlap window is empty: [{start}, {end})")
    n = 96
    times = [start + (i + 0.37) * span / n for i in range(n)]
    for t in times:
        if not (start <= t < end):
            continue
        a = _sound(ws, first, t - first.start)
        b = _sound(ws, second, t - second.start)
        mix = _sound(ws, mixed, t)
        if abs(float(a[0])) <= 0.18 or abs(float(b[0])) <= 0.18:
            continue
        if abs(float(mix[0])) <= 0.02:
            continue
        if samples_close(mix, a) or samples_close(mix, b):
            continue
        return t, a, b
    raise AssertionError(
        f"no overlap instant in [{start}, {end}) where both tones are audible "
        "and the mix is neither first-only, second-only, nor silence"
    )


def _find_overlap_t_where_mixes_differ(
    ws, mixed, other_mixed, first, second, start: float, end: float
):
    """Overlap instant where changing a member changes the mix.

    Both original members must be audible so the window is a live overlap.
    Mixing formula is not pinned: any combination that depends on the
    changed member differs here; a canned third signal that ignores the
    members cannot.
    """
    span = end - start
    if span <= 0:
        raise AssertionError(f"overlap window is empty: [{start}, {end})")
    n = 96
    times = [start + (i + 0.37) * span / n for i in range(n)]
    heard_both = False
    for t in times:
        if not (start <= t < end):
            continue
        a = _sound(ws, first, t - first.start)
        b = _sound(ws, second, t - second.start)
        if abs(float(a[0])) <= 0.18 or abs(float(b[0])) <= 0.18:
            continue
        heard_both = True
        mix = _sound(ws, mixed, t)
        other = _sound(ws, other_mixed, t)
        if samples_close(mix, other):
            continue
        return t, mix, other
    if not heard_both:
        raise AssertionError(
            f"no overlap instant in [{start}, {end}) where both members "
            "are audible"
        )
    raise AssertionError(
        f"overlap mix in [{start}, {end}) did not change when a member "
        "changed; a canned third signal independent of the members would "
        "look the same"
    )


def _find_concat_window_distinct(ws, concat, member, win_start, win_end, other):
    """Instant in a concat window where the playing member is not `other`.

    Different tones can share one sample at one t. Search the window so a
    correct sequence cannot go red on that coincidence. Mixing formula is
    not involved.
    """
    span = win_end - win_start
    other_dur = _require_duration(other)
    if span <= 0:
        raise AssertionError(f"concat window is empty: [{win_start}, {win_end})")
    if other_dur <= 0:
        raise AssertionError(f"other clip duration is not positive: {other_dur!r}")
    n = 96
    for i in range(n):
        frac = (i + 0.37) / n
        if not (0.08 <= frac <= 0.92):
            continue
        t = win_start + frac * span
        got = _sound(ws, concat, t)
        member_s = _sound(ws, member, frac * span)
        other_s = _sound(ws, other, frac * other_dur)
        if abs(float(member_s[0])) <= 0.05:
            continue
        if samples_close(member_s, other_s):
            continue
        if not samples_close(got, member_s):
            raise AssertionError(
                f"concat at t={t} does not match the member that should be "
                f"playing; got={got!r} member={member_s!r}"
            )
        return t, got, member_s, other_s
    raise AssertionError(
        f"no instant in [{win_start}, {win_end}) where the playing member "
        "is distinguishable from the later clip"
    )


# ---------------------------------------------------------------------------
# A. Overlay stacking, canvas, fill, blend, play window
# ---------------------------------------------------------------------------


def test_oracle_overlay_small_green_center_on_full_red():
    with workspace() as ws:
        canvas_w, canvas_h = 40, 32
        green_w, green_h = 16, 12
        red = _color(ws, (canvas_w, canvas_h), _RED, duration=2.0)
        green = _color(ws, (green_w, green_h), _GREEN, duration=2.0)
        placed = require_ok(ws.call(green.with_position, "center"))
        comp = _overlay(ws, [red, placed])
        frame = _frame(ws, comp, 0.0)
        ox, oy = _centered_origin(canvas_w, canvas_h, green_w, green_h)
        ix, iy = _interior_off_center(ox, oy, green_w, green_h)
        ox_out, oy_out = _just_outside_rect(
            ox, oy, green_w, green_h, canvas_w, canvas_h
        )
        cx, cy = canvas_w // 2, canvas_h // 2
        print(
            f"oracle_center=({cx},{cy}) interior=({ix},{iy}) outside=({ox_out},{oy_out})",
            flush=True,
        )
        require_rgb_picture(frame, canvas_h, canvas_w)
        _assert_color_at(frame, cx, cy, _GREEN)
        _assert_color_at(frame, ix, iy, _GREEN)
        _assert_color_at(frame, ox_out, oy_out, _RED)
        _assert_not_color_at(frame, 1, 1, _GREEN)
        assert (ix, iy) != (cx, cy)

        rw, rh = _even(18, 24), _even(14, 20)
        gw, gh = _even(6, 10), _even(5, 8)
        while rw - gw < 8 or rh - gh < 8:
            rw, rh = _even(18, 24), _even(14, 20)
            gw, gh = _even(6, 10), _even(5, 8)
        lower_c = _rgb_away_from(_RED, _GREEN, _BLACK)
        upper_c = _rgb_away_from(lower_c, _RED, _GREEN, _BLACK)
        lower = _color(ws, (rw, rh), lower_c, duration=1.5)
        upper = _color(ws, (gw, gh), upper_c, duration=1.5)
        runtime = _overlay(ws, [lower, require_ok(ws.call(upper.with_position, "center"))])
        runtime_frame = _frame(ws, runtime, 0.0)
        rx, ry = _centered_origin(rw, rh, gw, gh)
        rix, riy = _interior_off_center(rx, ry, gw, gh)
        rox, roy = _just_outside_rect(rx, ry, gw, gh, rw, rh)
        print(
            f"runtime canvas={rw}x{rh} green={gw}x{gh} interior=({rix},{riy}) "
            f"outside=({rox},{roy})",
            flush=True,
        )
        require_rgb_picture(runtime_frame, rh, rw)
        _assert_color_at(runtime_frame, rix, riy, upper_c)
        _assert_color_at(runtime_frame, rox, roy, lower_c)
        assert (rix, riy) != (rw // 2, rh // 2)


def test_same_layer_index_later_list_clip_is_on_top():
    with workspace() as ws:
        w, h = _even(8, 12), _even(7, 11)
        first_c = _rgb_away_from(_BLACK)
        later_c = _rgb_away_from(first_c, _BLACK)
        duration = 1.2
        a = _color(ws, (w, h), first_c, duration=duration)
        b = _color(ws, (w, h), later_c, duration=duration)
        ab = _overlay(ws, [a, b])
        ba = _overlay(ws, [b, a])
        frame_ab = _frame(ws, ab, 0.0)
        frame_ba = _frame(ws, ba, 0.0)
        print(
            f"same_index ab={_rgb_at(frame_ab, 1, 1)} ba={_rgb_at(frame_ba, 1, 1)}",
            flush=True,
        )
        require_rgb_picture(frame_ab, h, w, color=later_c)
        require_rgb_picture(frame_ba, h, w, color=first_c)
        assert not pictures_equal(frame_ab, frame_ba)


def test_higher_layer_index_on_top_regardless_of_list_order():
    with workspace() as ws:
        w, h = _even(8, 12), _even(7, 11)
        a_c = _rgb_away_from(_BLACK)
        b_c = _rgb_away_from(a_c, _BLACK)
        high = _rand_int(4, 9)
        low = _rand_int(0, high - 1)
        a = _color(ws, (w, h), a_c, duration=1.4)
        b = _color(ws, (w, h), b_c, duration=1.4)
        a_high = require_ok(ws.call(a.with_layer_index, high))
        b_low = require_ok(ws.call(b.with_layer_index, low))
        # Larger index first, smaller last: list order would show b if it won.
        high_first = _overlay(ws, [a_high, b_low])
        high_first_frame = _frame(ws, high_first, 0.0)
        a_low = require_ok(ws.call(a.with_layer_index, low))
        b_high = require_ok(ws.call(b.with_layer_index, high))
        swapped = _overlay(ws, [a_low, b_high])
        swapped_frame = _frame(ws, swapped, 0.0)
        print(
            f"layer_index high={high} low={low} first={_rgb_at(high_first_frame, 0, 0)} "
            f"swapped={_rgb_at(swapped_frame, 0, 0)}",
            flush=True,
        )
        require_rgb_picture(high_first_frame, h, w, color=a_c)
        require_rgb_picture(swapped_frame, h, w, color=b_c)
        assert not pictures_equal(high_first_frame, swapped_frame)


def test_default_composition_size_is_first_clip():
    with workspace() as ws:
        small_w, small_h = _even(6, 9), _even(5, 8)
        large_w, large_h = small_w + _even(4, 7), small_h + _even(3, 6)
        small_c = _rgb_away_from(_BLACK)
        large_c = _rgb_away_from(small_c, _BLACK)
        small = _color(ws, (small_w, small_h), small_c, duration=1.0)
        large = _color(ws, (large_w, large_h), large_c, duration=1.0)
        first_small = _overlay(ws, [small, large])
        first_large = _overlay(ws, [large, small])
        frame_small = _frame(ws, first_small, 0.0)
        frame_large = _frame(ws, first_large, 0.0)
        hs, ws_ = _frame_hw(frame_small)
        hl, wl = _frame_hw(frame_large)
        print(
            f"default_size first_small={ws_}x{hs} first_large={wl}x{hl} "
            f"small={small_w}x{small_h} large={large_w}x{large_h}",
            flush=True,
        )
        require_rgb_picture(frame_small, small_h, small_w)
        require_rgb_picture(frame_large, large_h, large_w)
        assert (ws_, hs) == (small_w, small_h)
        assert (wl, hl) == (large_w, large_h)
        assert (ws_, hs) != (wl, hl)


def test_named_larger_canvas_defaults_to_black_fill():
    with workspace() as ws:
        a_w, a_h = 16, 12
        b_w, b_h = 10, 8
        canvas_w, canvas_h = 36, 28
        a_c = _rgb_away_from(_BLACK)
        b_c = _rgb_away_from(a_c, _BLACK)
        a = _color(ws, (a_w, a_h), a_c, duration=1.0)
        b = _color(ws, (b_w, b_h), b_c, duration=1.0)
        # Keep the second layer on the first clip's canvas so the default-size
        # arm is the same pair of clips, differing only by the named size.
        bx, by = 2, 2
        placed_b = require_ok(ws.call(b.with_position, (bx, by)))
        named = _overlay(ws, [a, placed_b], size=(canvas_w, canvas_h))
        default = _overlay(ws, [a, placed_b])
        named_frame = _frame(ws, named, 0.0)
        default_frame = _frame(ws, default, 0.0)
        nh, nw = _frame_hw(named_frame)
        dh, dw = _frame_hw(default_frame)
        gap_x, gap_y = canvas_w - 1, canvas_h - 1
        print(
            f"named={nw}x{nh} default={dw}x{dh} a={a_w}x{a_h} "
            f"canvas={canvas_w}x{canvas_h} "
            f"origin={_rgb_at(named_frame, 0, 0)} "
            f"b={_rgb_at(named_frame, bx + b_w // 2, by + b_h // 2)} "
            f"gap={_rgb_at(named_frame, gap_x, gap_y)}",
            flush=True,
        )
        require_rgb_picture(named_frame, canvas_h, canvas_w)
        require_rgb_picture(default_frame, a_h, a_w)
        assert (nw, nh) == (canvas_w, canvas_h)
        assert (dw, dh) == (a_w, a_h)
        assert (nw, nh) != (dw, dh)
        _assert_color_at(named_frame, 0, 0, a_c)
        _assert_color_at(named_frame, bx + b_w // 2, by + b_h // 2, b_c)
        _assert_color_at(named_frame, gap_x, gap_y, _BLACK)
        _assert_not_color_at(named_frame, gap_x, gap_y, a_c)
        _assert_not_color_at(named_frame, gap_x, gap_y, b_c)
        _assert_color_at(default_frame, 0, 0, a_c)
        _assert_color_at(default_frame, bx + b_w // 2, by + b_h // 2, b_c)
        mask_v = _mask_value(ws, named, gap_x, gap_y)
        print(f"named_unfilled_mask={mask_v}", flush=True)
        if mask_v is None:
            assert named.mask is None
        else:
            assert mask_v > 0.5


def test_no_color_fill_leaves_unfilled_transparent():
    with workspace() as ws:
        a_w, a_h = 16, 12
        b_w, b_h = 10, 8
        canvas_w, canvas_h = 36, 28
        a_c = _rgb_away_from(_BLACK)
        b_c = _rgb_away_from(a_c, _BLACK)
        a = _color(ws, (a_w, a_h), a_c, duration=1.0)
        b = _color(ws, (b_w, b_h), b_c, duration=1.0)
        placed_b = require_ok(ws.call(b.with_position, (2, 2)))
        colorless = _overlay(
            ws, [a, placed_b], size=(canvas_w, canvas_h), bg_color=None
        )
        black = _overlay(ws, [a, placed_b], size=(canvas_w, canvas_h))
        color_frame = _frame(ws, colorless, 0.0)
        black_frame = _frame(ws, black, 0.0)
        gap_x, gap_y = canvas_w - 1, canvas_h - 1
        print(
            f"nocolor_mask={colorless.mask is not None} black_mask={black.mask is not None} "
            f"gap=({gap_x},{gap_y})",
            flush=True,
        )
        require_rgb_picture(color_frame, canvas_h, canvas_w)
        require_rgb_picture(black_frame, canvas_h, canvas_w)
        if colorless.mask is None:
            raise AssertionError("no-color fill did not give the composite a mask")
        color_gap = _mask_value(ws, colorless, gap_x, gap_y)
        color_filled = _mask_value(ws, colorless, 1, 1)
        if color_gap is None or color_filled is None:
            raise AssertionError("no-color composite mask frame was not readable")
        print(f"nocolor_gap_mask={color_gap} filled_mask={color_filled}", flush=True)
        assert color_gap <= 0.15
        assert color_filled >= 0.85
        black_gap = _mask_value(ws, black, gap_x, gap_y)
        _assert_color_at(black_frame, gap_x, gap_y, _BLACK)
        if black_gap is None:
            assert black.mask is None
        else:
            assert black_gap > 0.5
        assert color_gap != pytest.approx(black_gap if black_gap is not None else 1.0)


def test_designated_background_is_canvas_and_has_no_mask_if_unmasked():
    with workspace() as ws:
        canvas_w, canvas_h = _even(16, 22), _even(12, 18)
        overlay_w, overlay_h = _even(5, 8), _even(4, 7)
        dx, dy = _even(3, 5), _even(2, 4)
        bg_c = _rgb_away_from(_BLACK)
        over_c = _rgb_away_from(bg_c, _BLACK)
        background = _color(ws, (canvas_w, canvas_h), bg_c, duration=1.5)
        shifted = require_ok(ws.call(background.with_position, (dx, dy)))
        overlay = _color(ws, (overlay_w, overlay_h), over_c, duration=1.5)
        ox, oy = canvas_w - overlay_w, canvas_h - overlay_h
        placed = require_ok(ws.call(overlay.with_position, (ox, oy)))
        designated = _overlay(ws, [shifted, placed], use_bgclip=True)
        ordinary = _overlay(ws, [shifted, placed])
        des_frame = _frame(ws, designated, 0.0)
        ord_frame = _frame(ws, ordinary, 0.0)
        print(
            f"designated origin={_rgb_at(des_frame, 0, 0)} "
            f"ordinary origin={_rgb_at(ord_frame, 0, 0)} dx={dx} dy={dy} "
            f"des_mask={designated.mask is not None}",
            flush=True,
        )
        require_rgb_picture(des_frame, canvas_h, canvas_w)
        require_rgb_picture(ord_frame, canvas_h, canvas_w)
        _assert_color_at(des_frame, 0, 0, bg_c)
        _assert_not_color_at(des_frame, 0, 0, _BLACK)
        _assert_not_color_at(des_frame, 0, 0, over_c)
        _assert_color_at(ord_frame, 0, 0, _BLACK)
        _assert_color_at(des_frame, ox + overlay_w // 2, oy + overlay_h // 2, over_c)
        _assert_color_at(ord_frame, ox + overlay_w // 2, oy + overlay_h // 2, over_c)
        assert designated.mask is None
        assert not pictures_equal(des_frame, ord_frame)


def test_opaque_upper_layer_replaces_lower():
    with workspace() as ws:
        w, h = _even(8, 12), _even(7, 11)
        lower_c = _rgb_away_from(_BLACK)
        upper_c = _rgb_away_from(lower_c, _BLACK)
        lower = _color(ws, (w, h), lower_c, duration=1.0)
        upper = _color(ws, (w, h), upper_c, duration=1.0)
        comp = _overlay(ws, [lower, upper])
        frame = _frame(ws, comp, 0.0)
        print(f"opaque_replace={_rgb_at(frame, 1, 1)}", flush=True)
        require_rgb_picture(frame, h, w, color=upper_c)
        _assert_not_color_at(frame, 1, 1, lower_c)


def test_oracle_half_opacity_green_on_red_is_blend():
    with workspace() as ws:
        w, h = 20, 16
        red = _color(ws, (w, h), _RED, duration=2.0)
        green = _color(ws, (w, h), _GREEN, duration=2.0)
        faded = require_ok(ws.call(green.with_opacity, 0.5))
        blended = _overlay(ws, [red, faded])
        at_half = _frame(ws, blended, 0.5)
        other_t = 0.2
        at_other = _frame(ws, blended, other_t)
        sample = _rgb_at(at_half, w // 2, h // 2)
        print(f"half_opacity t=0.5 center={sample} t={other_t}", flush=True)
        require_rgb_picture(at_half, h, w)
        _assert_not_color_at(at_half, w // 2, h // 2, _RED, atol=20)
        _assert_not_color_at(at_half, w // 2, h // 2, _GREEN, atol=20)
        _assert_not_color_at(at_other, w // 2, h // 2, _RED, atol=20)
        _assert_not_color_at(at_other, w // 2, h // 2, _GREEN, atol=20)

        lower_c = _rgb_away_from(_RED, _GREEN, _BLACK)
        lower = _color(ws, (w, h), lower_c, duration=2.0)
        other = _overlay(ws, [lower, faded])
        other_frame = _frame(ws, other, 0.5)
        opaque = _overlay(ws, [lower, green])
        opaque_frame = _frame(ws, opaque, 0.5)
        bare = _frame(ws, lower, 0.5)
        print(
            f"other_lower={_rgb_at(other_frame, w // 2, h // 2)} "
            f"opaque={_rgb_at(opaque_frame, w // 2, h // 2)} "
            f"bare={_rgb_at(bare, w // 2, h // 2)}",
            flush=True,
        )
        assert not pictures_equal(at_half, other_frame)
        assert not pictures_equal(other_frame, opaque_frame)
        assert not pictures_equal(other_frame, bare)
        assert not pictures_equal(at_half, _frame(ws, red, 0.5))
        _assert_not_color_at(other_frame, w // 2, h // 2, _GREEN, atol=20)
        _assert_not_color_at(other_frame, w // 2, h // 2, lower_c, atol=20)


def test_title_play_window_center_first_10s():
    with workspace() as ws:
        canvas_w, canvas_h = 36, 28
        title_w, title_h = 12, 10
        lower_c = _rgb_away_from(_BLACK)
        title_c = _rgb_away_from(lower_c, _BLACK)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=16.0)
        title = _color(ws, (title_w, title_h), title_c, duration=10.0)
        placed = require_ok(ws.call(title.with_position, "center"))
        started = require_ok(ws.call(placed.with_start, 0))
        comp = _overlay(ws, [lower, started])
        at_five = _frame(ws, comp, 5.0)
        at_ten = _frame(ws, comp, 10.0)
        after = _frame(ws, comp, 11.0)
        cx, cy = canvas_w // 2, canvas_h // 2
        print(
            f"title_window t5={_rgb_at(at_five, cx, cy)} t10={_rgb_at(at_ten, cx, cy)} "
            f"t11={_rgb_at(after, cx, cy)}",
            flush=True,
        )
        _assert_color_at(at_five, cx, cy, title_c)
        _assert_color_at(at_ten, cx, cy, lower_c)
        _assert_color_at(after, cx, cy, lower_c)

        start_s = 3.5
        duration = 8.0
        end_e = start_s + duration
        assert not (start_s == 0.0 and duration == 10.0)
        assert end_e != 10.0
        runtime_title = _color(ws, (title_w, title_h), title_c, duration=duration)
        runtime_placed = require_ok(ws.call(runtime_title.with_position, "center"))
        runtime_started = require_ok(ws.call(runtime_placed.with_start, start_s))
        runtime = _overlay(ws, [lower, runtime_started])
        before = _frame(ws, runtime, start_s - 0.2)
        at_start = _frame(ws, runtime, start_s)
        inside_late = _frame(ws, runtime, 10.2)
        near_end = _frame(ws, runtime, end_e - 0.15)
        at_end = _frame(ws, runtime, end_e)
        print(
            f"runtime_window S={start_s} E={end_e} "
            f"before={_rgb_at(before, cx, cy)} start={_rgb_at(at_start, cx, cy)} "
            f"t10.2={_rgb_at(inside_late, cx, cy)} near={_rgb_at(near_end, cx, cy)} "
            f"end={_rgb_at(at_end, cx, cy)}",
            flush=True,
        )
        _assert_color_at(before, cx, cy, lower_c)
        _assert_color_at(at_start, cx, cy, title_c)
        _assert_color_at(inside_late, cx, cy, title_c)
        _assert_color_at(near_end, cx, cy, title_c)
        _assert_color_at(at_end, cx, cy, lower_c)


def test_layer_masks_mixed_unless_stripped():
    with workspace() as ws:
        w, h = _even(12, 16), _even(10, 14)
        lower_c = _rgb_away_from(_BLACK)
        upper_c = _rgb_away_from(lower_c, _BLACK)
        lower = _color(ws, (w, h), lower_c, duration=1.2)
        upper = _color(ws, (w, h), upper_c, duration=1.2)
        x0, x1 = w // 2 + 1, w
        y0, y1 = h // 2 + 1, h
        mask = _video(ws, _block_mask_fn(h, w, y0, y1, x0, x1), 1.2, is_mask=True)
        masked = require_ok(ws.call(upper.with_mask, mask))
        mixed = _overlay(ws, [lower, masked])
        stripped = _overlay(ws, [lower, require_ok(ws.call(masked.without_mask))])
        mixed_frame = _frame(ws, mixed, 0.0)
        stripped_frame = _frame(ws, stripped, 0.0)
        block_x, block_y = (x0 + x1) // 2, (y0 + y1) // 2
        right_top_x, right_top_y = (x0 + x1) // 2, max(1, y0 // 2)
        left_bot_x, left_bot_y = max(1, x0 // 2), (y0 + y1) // 2
        print(
            f"mask_block=({block_x},{block_y}) right_top=({right_top_x},{right_top_y}) "
            f"left_bot=({left_bot_x},{left_bot_y})",
            flush=True,
        )
        require_rgb_picture(mixed_frame, h, w)
        _assert_color_at(mixed_frame, block_x, block_y, upper_c)
        _assert_color_at(mixed_frame, right_top_x, right_top_y, lower_c)
        _assert_color_at(mixed_frame, left_bot_x, left_bot_y, lower_c)
        require_rgb_picture(stripped_frame, h, w, color=upper_c)
        assert not pictures_equal(mixed_frame, stripped_frame)


# ---------------------------------------------------------------------------
# B. Overlay duration, frame rate, soundtracks
# ---------------------------------------------------------------------------


def test_overlay_duration_is_max_end_when_every_layer_has_end():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        a_c = _rgb_away_from(_BLACK)
        b_c = _rgb_away_from(a_c, _BLACK)
        d_a = _rand_int(10, 14) / 10.0
        d_b = _rand_int(10, 14) / 10.0
        start_b = _rand_int(5, 8) / 10.0
        end_a = d_a
        end_b = start_b + d_b
        max_end = end_b
        max_duration = max(d_a, d_b)
        assert max_end > end_a
        assert max_end != pytest.approx(max_duration)
        a = _color(ws, (w, h), a_c, duration=d_a)
        b = _color(ws, (w, h), b_c, duration=d_b)
        delayed = require_ok(ws.call(b.with_start, start_b))
        comp = _overlay(ws, [a, delayed])
        duration = _require_duration(comp)
        print(
            f"overlay_duration={duration} max_end={max_end} max_d={max_duration} "
            f"sum={d_a + d_b} start_b={start_b}",
            flush=True,
        )
        assert duration == pytest.approx(max_end)
        assert duration != pytest.approx(d_a + d_b)
        assert duration != pytest.approx(min(end_a, end_b))
        assert duration != pytest.approx(max_duration)


def test_overlay_has_no_duration_if_any_layer_has_no_end():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        still_c = _rgb_away_from(_BLACK)
        finite_c = _rgb_away_from(still_c, _BLACK)
        d_finite = _rand_int(10, 16) / 10.0
        assigned_d = d_finite + _rand_int(6, 12) / 10.0
        still = _color(ws, (w, h), still_c)
        finite = _color(ws, (w, h), finite_c, duration=d_finite)
        both_finite = _overlay(
            ws,
            [
                _color(ws, (w, h), still_c, duration=d_finite),
                finite,
            ],
        )
        mixed = _overlay(ws, [still, finite])
        print(
            f"mixed_duration={_duration_or_missing(mixed)} "
            f"both_finite={_duration_or_missing(both_finite)} "
            f"finite_end={d_finite} assigned={assigned_d}",
            flush=True,
        )
        assert _duration_or_missing(mixed) is None
        assert _require_duration(both_finite) == pytest.approx(d_finite)
        given = require_ok(ws.call(mixed.with_duration, assigned_d))
        assert _require_duration(given) == pytest.approx(assigned_d)
        assert _require_duration(given) != pytest.approx(d_finite)
        during = _frame(ws, given, min(0.4, d_finite / 2))
        after = _frame(ws, given, d_finite + 0.15)
        require_rgb_picture(during, h, w, color=finite_c)
        require_rgb_picture(after, h, w, color=still_c)
        assert not pictures_equal(during, after)


def test_overlay_frame_rate_is_max_of_layers_that_have_one():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        a_c = _rgb_away_from(_BLACK)
        b_c = _rgb_away_from(a_c, _BLACK)
        r_small = 8.0
        r_large = float(_rand_int(12, 20))
        assert r_large != r_small
        a = _color(ws, (w, h), a_c, duration=1.0, fps=r_small)
        b = _color(ws, (w, h), b_c, duration=1.0, fps=r_large)
        both = _overlay(ws, [a, b])
        print(f"both_fps={_fps_or_missing(both)} max={r_large}", flush=True)
        assert _require_fps(both) == pytest.approx(r_large)

        no_fps = _color(ws, (w, h), a_c, duration=1.0)
        only_second = _overlay(ws, [no_fps, b])
        print(f"one_fps={_fps_or_missing(only_second)}", flush=True)
        assert _require_fps(only_second) == pytest.approx(r_large)

        none = _overlay(
            ws,
            [
                _color(ws, (w, h), a_c, duration=1.0),
                _color(ws, (w, h), b_c, duration=1.0),
            ],
        )
        print(f"no_fps={_fps_or_missing(none)}", flush=True)
        assert _fps_or_missing(none) is None


def test_overlay_mixes_soundtracks_with_same_starts_unless_stripped():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        d1 = 1.6
        d2 = 1.2
        start_s = 0.45
        f1 = float(_rand_int(280, 360))
        f2 = float(_rand_int(520, 680))
        tone_a = _tone(ws, f1, d1)
        tone_b = _tone(ws, f2, d2)
        video_a = require_ok(
            ws.call(_color(ws, (w, h), _rgb_away_from(_BLACK), duration=d1).with_audio, tone_a)
        )
        video_b = require_ok(
            ws.call(_color(ws, (w, h), _rgb_away_from(_BLACK), duration=d2).with_audio, tone_b)
        )
        delayed = require_ok(ws.call(video_b.with_start, start_s))
        mixed = _overlay(ws, [video_a, delayed])
        soundtrack = mixed.audio
        if soundtrack is None:
            raise AssertionError("overlay dropped layer soundtracks")
        overlap_end = min(d1, start_s + d2)
        delayed_tone = require_ok(ws.call(tone_b.with_start, start_s))
        t_mix, first_s, second_s = _find_overlap_t(
            ws, tone_a, delayed_tone, soundtrack, start_s, overlap_end
        )
        mixed_s = _sound(ws, soundtrack, t_mix)
        before = _sound(ws, soundtrack, start_s - 0.12)
        first_before = _sound(ws, tone_a, start_s - 0.12)
        print(
            f"mix t={t_mix} mix={mixed_s} first={first_s} second={second_s} "
            f"before={before}",
            flush=True,
        )
        assert samples_close(before, first_before)
        assert not samples_close(before, second_s)
        assert not samples_close(mixed_s, first_s)
        assert not samples_close(mixed_s, second_s)
        assert abs(float(mixed_s[0])) > 0.02

        f1_other = float(_rand_int(740, 860))
        f2_other = float(_rand_int(180, 250))
        tone_a2 = _tone(ws, f1_other, d1)
        video_a2 = require_ok(
            ws.call(
                _color(ws, (w, h), _rgb_away_from(_BLACK), duration=d1).with_audio,
                tone_a2,
            )
        )
        mixed_first = _overlay(ws, [video_a2, delayed])
        st_first = mixed_first.audio
        if st_first is None:
            raise AssertionError(
                "overlay dropped layer soundtracks after changing the first"
            )
        tone_b2 = _tone(ws, f2_other, d2)
        video_b2 = require_ok(
            ws.call(
                _color(ws, (w, h), _rgb_away_from(_BLACK), duration=d2).with_audio,
                tone_b2,
            )
        )
        delayed2 = require_ok(ws.call(video_b2.with_start, start_s))
        mixed_second = _overlay(ws, [video_a, delayed2])
        st_second = mixed_second.audio
        if st_second is None:
            raise AssertionError(
                "overlay dropped layer soundtracks after changing the second"
            )
        t_first, mix_keep_f, mix_chg_f = _find_overlap_t_where_mixes_differ(
            ws, soundtrack, st_first, tone_a, delayed_tone, start_s, overlap_end
        )
        t_second, mix_keep_s, mix_chg_s = _find_overlap_t_where_mixes_differ(
            ws, soundtrack, st_second, tone_a, delayed_tone, start_s, overlap_end
        )
        print(
            f"mix_depends_first t={t_first} keep={mix_keep_f} chg={mix_chg_f} "
            f"mix_depends_second t={t_second} keep={mix_keep_s} chg={mix_chg_s}",
            flush=True,
        )
        assert not samples_close(mix_keep_f, mix_chg_f)
        assert not samples_close(mix_keep_s, mix_chg_s)

        stripped_a = require_ok(ws.call(video_a.without_audio))
        stripped_b = require_ok(ws.call(delayed.without_audio))
        stripped = _overlay(ws, [stripped_a, stripped_b])
        print(f"stripped_audio={stripped.audio is not None}", flush=True)
        if stripped.audio is None:
            assert soundtrack is not None
        else:
            stripped_s = _sound(ws, stripped.audio, t_mix)
            assert not samples_close(stripped_s, mixed_s)
            assert not samples_close(stripped_s, first_s)
            assert not samples_close(stripped_s, second_s)


# ---------------------------------------------------------------------------
# C. Video concatenate
# ---------------------------------------------------------------------------


def test_oracle_concat_1s_red_then_1s_blue():
    with workspace() as ws:
        w, h = 20, 16
        red = _color(ws, (w, h), _RED, duration=1.0)
        blue = _color(ws, (w, h), _BLUE, duration=1.0)
        cat = _concat(ws, [red, blue], method="chain")
        duration = _require_duration(cat)
        at_half = _frame(ws, cat, 0.5)
        at_one_half = _frame(ws, cat, 1.5)
        print(f"oracle_concat D={duration}", flush=True)
        assert duration == pytest.approx(2.0)
        require_rgb_picture(at_half, h, w, color=_RED)
        require_rgb_picture(at_one_half, h, w, color=_BLUE)
        assert not pictures_equal(at_half, at_one_half)


def test_concat_plays_clips_in_sequence_runtime():
    with workspace() as ws:
        w, h = _even(8, 12), _even(6, 10)
        d1 = _rand_int(7, 13) / 10.0
        d2 = _rand_int(7, 13) / 10.0
        while abs((d1 + d2) - 2.0) < 0.15:
            d2 = _rand_int(7, 13) / 10.0
        c1 = _rgb_away_from(_RED, _BLUE, _BLACK)
        c2 = _rgb_away_from(c1, _RED, _BLUE, _BLACK)
        a = _color(ws, (w, h), c1, duration=d1)
        b = _color(ws, (w, h), c2, duration=d2)
        cat = _concat(ws, [a, b], method="chain")
        duration = _require_duration(cat)
        first = _frame(ws, cat, d1 * 0.4)
        second = _frame(ws, cat, d1 + d2 * 0.4)
        print(f"runtime_concat D={duration} d1={d1} d2={d2}", flush=True)
        assert duration == pytest.approx(d1 + d2)
        require_rgb_picture(first, h, w, color=c1)
        require_rgb_picture(second, h, w, color=c2)
        assert not pictures_equal(first, second)


def test_concat_three_clips_duration_is_sum():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        d1 = _rand_int(5, 9) / 10.0
        d2 = _rand_int(5, 9) / 10.0
        d3 = _rand_int(5, 9) / 10.0
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        c3 = _rgb_away_from(c1, c2, _BLACK)
        clips = [
            _color(ws, (w, h), c1, duration=d1),
            _color(ws, (w, h), c2, duration=d2),
            _color(ws, (w, h), c3, duration=d3),
        ]
        cat = _concat(ws, clips, method="chain")
        duration = _require_duration(cat)
        mid = _frame(ws, cat, d1 + d2 * 0.4)
        print(f"three_concat D={duration} sum={d1 + d2 + d3}", flush=True)
        assert duration == pytest.approx(d1 + d2 + d3)
        require_rgb_picture(mid, h, w, color=c2)
        _assert_not_color_at(mid, 1, 1, c1)
        _assert_not_color_at(mid, 1, 1, c3)


def test_concat_chain_keeps_per_segment_size():
    with workspace() as ws:
        w1, h1 = _even(6, 8), _even(5, 7)
        w2, h2 = w1 + _even(4, 6), h1 + _even(3, 5)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        d1, d2 = 0.8, 0.7
        a = _color(ws, (w1, h1), c1, duration=d1)
        b = _color(ws, (w2, h2), c2, duration=d2)
        chain = _concat(ws, [a, b], method="chain")
        first = _frame(ws, chain, d1 * 0.4)
        second = _frame(ws, chain, d1 + d2 * 0.4)
        fh, fw = _frame_hw(first)
        sh, sw = _frame_hw(second)
        print(f"chain sizes t1={fw}x{fh} t2={sw}x{sh}", flush=True)
        require_rgb_picture(first, h1, w1, color=c1)
        require_rgb_picture(second, h2, w2, color=c2)
        assert (fw, fh) != (sw, sh)
        assert (fw, fh) != (max(w1, w2), max(h1, h2))


def test_concat_chain_concatenates_masks_opaque_where_missing():
    with workspace() as ws:
        w1, h1 = _even(10, 14), _even(8, 12)
        w2, h2 = _even(8, 12), _even(6, 10)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        d1, d2 = 0.7, 0.6
        a = _color(ws, (w1, h1), c1, duration=d1)
        b = _color(ws, (w2, h2), c2, duration=d2)
        x0, x1 = w1 // 2 + 1, w1
        y0, y1 = 0, h1 // 2
        mask = _video(ws, _block_mask_fn(h1, w1, y0, y1, x0, x1), d1, is_mask=True)
        masked_a = require_ok(ws.call(a.with_mask, mask))
        cat = _concat(ws, [masked_a, b], method="chain")
        if cat.mask is None:
            raise AssertionError("chain concat of a masked clip has no concatenated mask")
        t1, t2 = d1 * 0.4, d1 + d2 * 0.4
        first_rgb = _frame(ws, cat, t1)
        second_rgb = _frame(ws, cat, t2)
        first_mask = require_mask_picture(_frame(ws, cat.mask, t1), h1, w1)
        second_mask = require_mask_picture(_frame(ws, cat.mask, t2), h2, w2)
        bx, by = (x0 + x1) // 2, max(0, (y0 + y1) // 2)
        outside_x, outside_y = max(1, x0 // 2), min(h1 - 1, h1 // 2 + 1)
        print(
            f"chain_mask t1_block={first_mask[by, bx]} t1_out={first_mask[outside_y, outside_x]} "
            f"t2_min={second_mask.min()} t2_max={second_mask.max()}",
            flush=True,
        )
        require_rgb_picture(first_rgb, h1, w1)
        require_rgb_picture(second_rgb, h2, w2)
        assert first_mask[by, bx] >= 0.85
        assert first_mask[outside_y, outside_x] <= 0.15
        assert float(second_mask.min()) >= 0.85


def test_concat_compose_max_size_centers_smaller_clips():
    with workspace() as ws:
        w1, h1 = _even(6, 8), _even(5, 7)
        w2, h2 = w1 + _even(5, 8), h1 + _even(4, 7)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        d1, d2 = 0.8, 0.7
        a = _color(ws, (w1, h1), c1, duration=d1)
        b = _color(ws, (w2, h2), c2, duration=d2)
        compose = _concat(ws, [a, b], method="compose")
        chain = _concat(ws, [a, b], method="chain")
        max_w, max_h = max(w1, w2), max(h1, h2)
        first = _frame(ws, compose, d1 * 0.4)
        second = _frame(ws, compose, d1 + d2 * 0.4)
        chain_first = _frame(ws, chain, d1 * 0.4)
        fh, fw = _frame_hw(first)
        sh, sw = _frame_hw(second)
        ch, cw = _frame_hw(chain_first)
        ox, oy = _centered_origin(max_w, max_h, w1, h1)
        ix, iy = _interior_off_center(ox, oy, w1, h1)
        out_x, out_y = _just_outside_rect(ox, oy, w1, h1, max_w, max_h)
        print(
            f"compose={fw}x{fh} chain_first={cw}x{ch} interior=({ix},{iy}) "
            f"outside=({out_x},{out_y})",
            flush=True,
        )
        require_rgb_picture(first, max_h, max_w)
        require_rgb_picture(second, max_h, max_w)
        assert (fw, fh) == (max_w, max_h)
        assert (sw, sh) == (max_w, max_h)
        assert (cw, ch) == (w1, h1)
        _assert_color_at(first, ix, iy, c1)
        _assert_not_color_at(first, out_x, out_y, c1)
        assert (ix, iy) != (max_w // 2, max_h // 2)


def test_concat_duration_includes_padding_and_transition():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        d1 = _rand_int(6, 10) / 10.0
        d2 = _rand_int(6, 10) / 10.0
        d3 = _rand_int(6, 10) / 10.0
        padding = _rand_int(3, 7) / 10.0
        t_trans = _rand_int(3, 6) / 10.0
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        c3 = _rgb_away_from(c1, c2, _BLACK)
        trans_c = _rgb_away_from(c1, c2, c3, _BLACK)
        a = _color(ws, (w, h), c1, duration=d1)
        b = _color(ws, (w, h), c2, duration=d2)
        c = _color(ws, (w, h), c3, duration=d3)
        trans = _color(ws, (w, h), trans_c, duration=t_trans)
        two = _concat(ws, [a, b], method="compose", padding=padding)
        two_d = _require_duration(two)
        gap_t = d1 + padding / 2.0
        after_gap = d1 + padding
        gap_frame = _frame(ws, two, gap_t)
        after_frame = _frame(ws, two, after_gap + 0.05)
        print(
            f"pad_two D={two_d} expected={d1 + d2 + padding} gap_t={gap_t}",
            flush=True,
        )
        assert two_d == pytest.approx(d1 + d2 + padding)
        _assert_not_color_at(gap_frame, w // 2, h // 2, c2)
        require_rgb_picture(after_frame, h, w, color=c2)

        three = _concat(ws, [a, b, c], method="compose", padding=padding)
        three_d = _require_duration(three)
        second_gap = d1 + padding + d2 + padding / 2.0
        second_gap_frame = _frame(ws, three, second_gap)
        print(
            f"pad_three D={three_d} expected={d1 + d2 + d3 + 2 * padding} "
            f"second_gap={second_gap}",
            flush=True,
        )
        assert three_d == pytest.approx(d1 + d2 + d3 + 2 * padding)
        _assert_not_color_at(second_gap_frame, w // 2, h // 2, c3)

        with_trans = _concat(ws, [a, b, c], method="compose", transition=trans)
        trans_d = _require_duration(with_trans)
        first_trans_t = d1 + t_trans / 2.0
        second_trans_t = d1 + t_trans + d2 + t_trans / 2.0
        first_trans = _frame(ws, with_trans, first_trans_t)
        second_trans = _frame(ws, with_trans, second_trans_t)
        print(
            f"trans D={trans_d} expected={d1 + d2 + d3 + 2 * t_trans} "
            f"t1={first_trans_t} t2={second_trans_t}",
            flush=True,
        )
        assert trans_d == pytest.approx(d1 + d2 + d3 + 2 * t_trans)
        require_rgb_picture(first_trans, h, w, color=trans_c)
        require_rgb_picture(second_trans, h, w, color=trans_c)
        _assert_not_color_at(second_trans, 1, 1, c3)


def test_concat_nonzero_padding_does_not_switch_chain_to_compose():
    with workspace() as ws:
        w1, h1 = _even(6, 8), _even(5, 7)
        w2, h2 = w1 + _even(4, 6), h1 + _even(3, 5)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        d1, d2 = 0.8, 0.7
        padding = _rand_int(3, 7) / 10.0
        a = _color(ws, (w1, h1), c1, duration=d1)
        b = _color(ws, (w2, h2), c2, duration=d2)
        chain = _concat(ws, [a, b], method="chain", padding=padding)
        compose = _concat(ws, [a, b], method="compose", padding=padding)
        chain_d = _require_duration(chain)
        first = _frame(ws, chain, d1 * 0.3)
        second = _frame(ws, chain, d1 + padding + d2 * 0.3)
        compose_first = _frame(ws, compose, d1 * 0.3)
        fh, fw = _frame_hw(first)
        sh, sw = _frame_hw(second)
        ch, cw = _frame_hw(compose_first)
        print(
            f"pad_chain D={chain_d} t1={fw}x{fh} t2={sw}x{sh} compose={cw}x{ch} p={padding}",
            flush=True,
        )
        assert chain_d == pytest.approx(d1 + d2 + padding)
        require_rgb_picture(first, h1, w1, color=c1)
        require_rgb_picture(second, h2, w2, color=c2)
        require_rgb_picture(compose_first, max(h1, h2), max(w1, w2))
        assert (fw, fh) != (max(w1, w2), max(h1, h2))
        assert (cw, ch) == (max(w1, w2), max(h1, h2))


def test_concat_compose_negative_padding_overlaps():
    with workspace() as ws:
        w1, h1 = _even(10, 14), _even(8, 12)
        w2, h2 = w1 - _even(4, 6), h1 - _even(3, 5)
        d1 = _rand_int(10, 14) / 10.0
        d2 = _rand_int(10, 14) / 10.0
        padding = -(_rand_int(3, 6) / 10.0)
        assert d1 + padding > 0.2
        assert w2 >= 4 and h2 >= 4
        assert w2 < w1 and h2 < h1
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        a = _color(ws, (w1, h1), c1, duration=d1)
        b = _color(ws, (w2, h2), c2, duration=d2)
        cat = _concat(ws, [a, b], method="compose", padding=padding)
        duration = _require_duration(cat)
        appear_t = d1 + padding
        before_t = appear_t / 2.0
        overlap_t = appear_t + 0.05
        assert overlap_t < d1
        before = _frame(ws, cat, before_t)
        appeared = _frame(ws, cat, overlap_t)
        canvas_h, canvas_w = _frame_hw(appeared)
        ox, oy = _centered_origin(w1, h1, w2, h2)
        ix, iy = _interior_off_center(ox, oy, w2, h2)
        out_x, out_y = _just_outside_rect(ox, oy, w2, h2, w1, h1)
        print(
            f"neg_pad D={duration} expected={d1 + d2 + padding} appear={appear_t} "
            f"overlap_t={overlap_t} canvas={canvas_w}x{canvas_h} "
            f"second={w2}x{h2} interior=({ix},{iy}) outside=({out_x},{out_y})",
            flush=True,
        )
        assert duration == pytest.approx(d1 + d2 + padding)
        require_rgb_picture(before, h1, w1, color=c1)
        require_rgb_picture(appeared, h1, w1)
        assert (canvas_w, canvas_h) == (w1, h1)
        assert not pictures_equal(appeared, before)
        _assert_color_at(appeared, ix, iy, c2)
        _assert_color_at(appeared, out_x, out_y, c1)
        _assert_not_color_at(appeared, ix, iy, c1)
        _assert_not_color_at(appeared, out_x, out_y, c2)


def test_concat_frame_rate_is_max_of_inputs():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        r_small = 8.0
        r_large = float(_rand_int(13, 21))
        a = _color(ws, (w, h), _rgb_away_from(_BLACK), duration=0.6, fps=r_small)
        b = _color(ws, (w, h), _rgb_away_from(_BLACK), duration=0.6, fps=r_large)
        cat = _concat(ws, [a, b], method="chain")
        print(f"concat_fps={_fps_or_missing(cat)} max={r_large}", flush=True)
        assert _require_fps(cat) == pytest.approx(r_large)


def test_concat_soundtracks_in_same_order():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        d1, d2 = 0.9, 0.8
        f1 = float(_rand_int(280, 360))
        f2 = float(_rand_int(520, 680))
        tone_a = _tone(ws, f1, d1)
        tone_b = _tone(ws, f2, d2)
        v1 = require_ok(
            ws.call(_color(ws, (w, h), _rgb_away_from(_BLACK), duration=d1).with_audio, tone_a)
        )
        v2 = require_ok(
            ws.call(_color(ws, (w, h), _rgb_away_from(_BLACK), duration=d2).with_audio, tone_b)
        )
        cat = _concat(ws, [v1, v2], method="chain")
        soundtrack = cat.audio
        if soundtrack is None:
            raise AssertionError("concat dropped soundtracks")
        t1 = d1 * 0.4
        t2 = d1 + d2 * 0.4
        first = _sound(ws, soundtrack, t1)
        second = _sound(ws, soundtrack, t2)
        first_src = _sound(ws, tone_a, t1)
        second_src = _sound(ws, tone_b, t2 - d1)
        print(f"concat_audio t1={first} t2={second}", flush=True)
        assert samples_close(first, first_src)
        assert samples_close(second, second_src)
        assert not samples_close(first, second_src)
        assert not samples_close(second, first_src)


def test_concat_requires_every_input_duration():
    with workspace() as ws:
        w, h = _even(8, 10), _even(6, 8)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        d1, d2 = 0.6, 0.7
        still = _color(ws, (w, h), c1)
        finite = _color(ws, (w, h), c2, duration=d2)
        assert _duration_or_missing(still) is None
        failed = ws.call(concatenate_videoclips, [still, finite], method="chain")
        require_failed(failed)
        print(f"concat_missing_duration={failed.exception}", flush=True)
        assert failed.exception is not None

        later_still = _color(ws, (w, h), c2)
        earlier = _color(ws, (w, h), c1, duration=d1)
        assert _duration_or_missing(later_still) is None
        failed_later = ws.call(
            concatenate_videoclips, [earlier, later_still], method="chain"
        )
        require_failed(failed_later)
        print(f"concat_missing_duration_later={failed_later.exception}", flush=True)
        assert failed_later.exception is not None

        filled = require_ok(ws.call(still.with_duration, d1))
        cat = _concat(ws, [filled, finite], method="chain")
        assert _require_duration(cat) == pytest.approx(d1 + d2)
        first = _frame(ws, cat, d1 * 0.5)
        second = _frame(ws, cat, d1 + d2 * 0.4)
        require_rgb_picture(first, h, w, color=c1)
        require_rgb_picture(second, h, w, color=c2)
        assert not pictures_equal(first, second)


# ---------------------------------------------------------------------------
# D. Grid
# ---------------------------------------------------------------------------


def test_oracle_grid_1x3_equal_red_green_blue():
    with workspace() as ws:
        w, h = 12, 10
        red = _color(ws, (w, h), _RED, duration=1.0)
        green = _color(ws, (w, h), _GREEN, duration=1.0)
        blue = _color(ws, (w, h), _BLUE, duration=1.0)
        grid = _grid(ws, [[red, green, blue]])
        frame = _frame(ws, grid, 0.0)
        gh, gw = _frame_hw(frame)
        print(f"oracle_grid {gw}x{gh}", flush=True)
        require_rgb_picture(frame, h, 3 * w)
        assert gw == 3 * w
        assert gh == h
        _assert_color_at(frame, w // 2, h // 2, _RED)
        _assert_color_at(frame, w + w // 2, h // 2, _GREEN)
        _assert_color_at(frame, 2 * w + w // 2, h // 2, _BLUE)


def test_grid_row_is_spatial_not_temporal():
    with workspace() as ws:
        n = _rand_int(3, 4)
        w, h = _even(6, 8), _even(5, 7)
        colors = []
        banned = [_BLACK]
        clips = []
        for _ in range(n):
            color = _rgb_away_from(*banned)
            banned.append(color)
            colors.append(color)
            clips.append(_color(ws, (w, h), color, duration=1.0))
        grid = _grid(ws, [clips])
        frame = _frame(ws, grid, 0.0)
        gh, gw = _frame_hw(frame)
        print(f"runtime_grid n={n} {gw}x{gh} cell={w}x{h}", flush=True)
        require_rgb_picture(frame, h, n * w)
        assert gw == n * w
        assert gh == h
        for index, color in enumerate(colors):
            _assert_color_at(frame, index * w + w // 2, h // 2, color)


def test_grid_cells_are_max_in_row_and_column_smaller_centered():
    with workspace() as ws:
        # 2x2, unequal: at least one row with two widths, one column with two heights.
        a_w, a_h = 16, 10
        b_w, b_h = 28, 18
        c_w, c_h = 24, 14
        d_w, d_h = 20, 22
        ca = _rgb_away_from(_BLACK)
        cb = _rgb_away_from(ca, _BLACK)
        cc = _rgb_away_from(ca, cb, _BLACK)
        cd = _rgb_away_from(ca, cb, cc, _BLACK)
        a = _color(ws, (a_w, a_h), ca, duration=1.0)
        b = _color(ws, (b_w, b_h), cb, duration=1.0)
        c = _color(ws, (c_w, c_h), cc, duration=1.0)
        d = _color(ws, (d_w, d_h), cd, duration=1.0)
        grid = _grid(ws, [[a, b], [c, d]])
        frame = _frame(ws, grid, 0.0)
        col0 = max(a_w, c_w)
        col1 = max(b_w, d_w)
        row0 = max(a_h, b_h)
        row1 = max(c_h, d_h)
        total_w, total_h = col0 + col1, row0 + row1
        gh, gw = _frame_hw(frame)
        ox, oy = _centered_origin(col0, row0, a_w, a_h)
        ix, iy = _interior_off_center(ox, oy, a_w, a_h)
        print(
            f"grid2x2 {gw}x{gh} expected={total_w}x{total_h} "
            f"a_cell={col0}x{row0} interior=({ix},{iy})",
            flush=True,
        )
        require_rgb_picture(frame, total_h, total_w)
        assert (gw, gh) == (total_w, total_h)
        _assert_color_at(frame, ix, iy, ca)
        _assert_not_color_at(frame, 0, 0, ca)
        assert (ix, iy) != (col0 // 2, row0 // 2)


def test_grid_height_is_sum_of_row_heights():
    with workspace() as ws:
        w = _even(8, 10)
        h1 = _even(5, 7)
        h2 = h1 + _even(2, 4)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        top = _color(ws, (w, h1), c1, duration=1.0)
        bottom = _color(ws, (w, h2), c2, duration=1.0)
        grid = _grid(ws, [[top], [bottom]])
        frame = _frame(ws, grid, 0.0)
        gh, gw = _frame_hw(frame)
        print(f"two_rows {gw}x{gh} expected={w}x{h1 + h2}", flush=True)
        require_rgb_picture(frame, h1 + h2, w)
        assert gh == h1 + h2
        _assert_color_at(frame, w // 2, h1 // 2, c1)
        _assert_color_at(frame, w // 2, h1 + h2 // 2, c2)


# ---------------------------------------------------------------------------
# E. Audio overlay and concatenate
# ---------------------------------------------------------------------------


def test_audio_overlay_plays_together_by_start():
    with workspace() as ws:
        d1, d2 = 1.5, 1.1
        start_s = 0.4
        f1 = float(_rand_int(280, 360))
        f2 = float(_rand_int(520, 680))
        a = _tone(ws, f1, d1)
        b = require_ok(ws.call(_tone(ws, f2, d2).with_start, start_s))
        mixed = _audio_overlay(ws, [a, b])
        overlap_end = min(d1, start_s + d2)
        t_mix, first_s, second_s = _find_overlap_t(
            ws, a, b, mixed, start_s, overlap_end
        )
        mix_s = _sound(ws, mixed, t_mix)
        before = _sound(ws, mixed, start_s - 0.12)
        first_before = _sound(ws, a, start_s - 0.12)
        print(
            f"audio_overlay t={t_mix} mix={mix_s} first={first_s} second={second_s}",
            flush=True,
        )
        assert samples_close(before, first_before)
        assert not samples_close(before, second_s)
        assert not samples_close(mix_s, first_s)
        assert not samples_close(mix_s, second_s)
        assert abs(float(mix_s[0])) > 0.02

        f1_other = float(_rand_int(740, 860))
        f2_other = float(_rand_int(180, 250))
        a2 = _tone(ws, f1_other, d1)
        b2 = require_ok(ws.call(_tone(ws, f2_other, d2).with_start, start_s))
        mixed_first = _audio_overlay(ws, [a2, b])
        mixed_second = _audio_overlay(ws, [a, b2])
        t_first, mix_keep_f, mix_chg_f = _find_overlap_t_where_mixes_differ(
            ws, mixed, mixed_first, a, b, start_s, overlap_end
        )
        t_second, mix_keep_s, mix_chg_s = _find_overlap_t_where_mixes_differ(
            ws, mixed, mixed_second, a, b, start_s, overlap_end
        )
        print(
            f"audio_mix_depends_first t={t_first} keep={mix_keep_f} "
            f"chg={mix_chg_f} audio_mix_depends_second t={t_second} "
            f"keep={mix_keep_s} chg={mix_chg_s}",
            flush=True,
        )
        assert not samples_close(mix_keep_f, mix_chg_f)
        assert not samples_close(mix_keep_s, mix_chg_s)


def test_audio_overlay_duration_is_max_end():
    with workspace() as ws:
        d_a = _rand_int(10, 14) / 10.0
        d_b = _rand_int(10, 14) / 10.0
        start_b = _rand_int(5, 8) / 10.0
        max_end = start_b + d_b
        max_d = max(d_a, d_b)
        assert max_end > d_a
        assert max_end != pytest.approx(max_d)
        a = _tone(ws, 330.0, d_a)
        b = require_ok(ws.call(_tone(ws, 550.0, d_b).with_start, start_b))
        mixed = _audio_overlay(ws, [a, b])
        duration = _require_duration(mixed)
        print(
            f"audio_overlay_D={duration} max_end={max_end} max_d={max_d}",
            flush=True,
        )
        assert duration == pytest.approx(max_end)
        assert duration != pytest.approx(max_d)
        assert duration != pytest.approx(d_a + d_b)


def test_audio_overlay_channel_count_and_sample_rate_are_maxima():
    with workspace() as ws:
        n = 80
        low_rate = float(_rand_int(8, 11) * 1000)
        high_rate = float(_rand_int(14, 18) * 1000)
        mono = np.linspace(-0.4, 0.5, n).reshape(n, 1)
        stereo = np.column_stack(
            (np.linspace(-0.3, 0.4, n), np.linspace(0.2, -0.25, n))
        )
        mono_clip = require_ok(ws.call(AudioArrayClip, mono, low_rate))
        stereo_clip = require_ok(ws.call(AudioArrayClip, stereo, high_rate))
        mixed = _audio_overlay(ws, [mono_clip, stereo_clip])
        two_mono = _audio_overlay(
            ws,
            [
                require_ok(ws.call(AudioArrayClip, mono, low_rate)),
                require_ok(ws.call(AudioArrayClip, mono, high_rate)),
            ],
        )
        mix_frame = _sound(ws, mixed, 0.0, channels=2)
        mono_frame = _sound(ws, two_mono, 0.0, channels=1)
        print(
            f"mix_channels={mix_frame.size} two_mono={mono_frame.size} "
            f"mix_rate={_fps_or_missing(mixed)}",
            flush=True,
        )
        assert mix_frame.size == 2
        assert mono_frame.size == 1
        assert _require_fps(mixed) == pytest.approx(high_rate)
        assert _require_fps(mixed) != pytest.approx(low_rate)


def test_oracle_audio_concat_2s_then_5s():
    with workspace() as ws:
        f1 = 330.7
        f2 = 551.3
        a = _tone(ws, f1, 2.0)
        b = _tone(ws, f2, 5.0)
        cat = _audio_concat(ws, [a, b])
        duration = _require_duration(cat)
        t_first, t_second = 1.0, 4.0
        first = _sound(ws, cat, t_first)
        second = _sound(ws, cat, t_second)
        first_src = _sound(ws, a, t_first)
        second_src = _sound(ws, b, t_second - 2.0)
        just_before = _sound(ws, cat, 1.9)
        just_after = _sound(ws, cat, 2.1)
        before_src = _sound(ws, a, 1.9)
        after_src = _sound(ws, b, 0.1)
        print(
            f"oracle_audio_concat D={duration} t1={first} t4={second} "
            f"src1={first_src} src4={second_src}",
            flush=True,
        )
        assert duration == pytest.approx(7.0)
        assert samples_close(first, first_src)
        assert samples_close(second, second_src)
        assert not samples_close(first, second_src)
        assert not samples_close(second, first_src)
        assert samples_close(just_before, before_src)
        assert samples_close(just_after, after_src)
        assert not samples_close(just_before, after_src)


def test_audio_concat_sequences_and_duration_is_sum():
    with workspace() as ws:
        d1 = _rand_int(6, 11) / 10.0
        d2 = _rand_int(6, 11) / 10.0
        d3 = _rand_int(6, 11) / 10.0
        while abs((d1 + d2) - 7.0) < 1.0:
            d1 = _rand_int(6, 11) / 10.0
            d2 = _rand_int(6, 11) / 10.0
        f1 = float(_rand_int(260, 320))
        f2 = float(_rand_int(400, 480))
        f3 = float(_rand_int(600, 720))
        a = _tone(ws, f1, d1)
        b = _tone(ws, f2, d2)
        c = _tone(ws, f3, d3)
        two = _audio_concat(ws, [a, b])
        three = _audio_concat(ws, [a, b, c])
        two_d = _require_duration(two)
        three_d = _require_duration(three)
        t1 = d1 - 0.08
        t2 = d1 + 0.08
        first = _sound(ws, two, t1)
        second = _sound(ws, two, t2)
        first_src = _sound(ws, a, t1)
        second_src = _sound(ws, b, t2 - d1)
        t_join, two_early, two_first, two_second = _find_concat_window_distinct(
            ws, two, a, 0.0, d1, b
        )
        t_early, third_early, early_first, early_third = _find_concat_window_distinct(
            ws, three, a, 0.0, d1, c
        )
        t_mid, third_mid, mid_second, mid_third = _find_concat_window_distinct(
            ws, three, b, d1, d1 + d2, c
        )
        t_late = d1 + d2 + d3 * 0.4
        third_late = _sound(ws, three, t_late)
        third_src = _sound(ws, c, d3 * 0.4)
        print(
            f"audio_concat two_D={two_d} three_D={three_d} d1={d1} d2={d2} d3={d3} "
            f"t_join={t_join} t_early={t_early} t_mid={t_mid} t_late={t_late}",
            flush=True,
        )
        assert two_d == pytest.approx(d1 + d2)
        assert three_d == pytest.approx(d1 + d2 + d3)
        assert samples_close(first, first_src)
        assert samples_close(second, second_src)
        assert samples_close(two_early, two_first)
        assert not samples_close(two_early, two_second)
        assert samples_close(third_late, third_src)
        assert samples_close(third_early, early_first)
        assert not samples_close(third_early, early_third)
        assert samples_close(third_mid, mid_second)
        assert not samples_close(third_mid, mid_third)


def test_audio_concat_sample_rate_and_channels_are_maxima():
    with workspace() as ws:
        n = 64
        low_rate = float(_rand_int(8, 11) * 1000)
        high_rate = float(_rand_int(14, 18) * 1000)
        mono = np.linspace(-0.4, 0.5, n).reshape(n, 1)
        stereo = np.column_stack(
            (np.linspace(-0.3, 0.4, n), np.linspace(0.2, -0.25, n))
        )
        mono_clip = require_ok(ws.call(AudioArrayClip, mono, low_rate))
        stereo_clip = require_ok(ws.call(AudioArrayClip, stereo, high_rate))
        cat = _audio_concat(ws, [mono_clip, stereo_clip])
        frame = _sound(ws, cat, 0.0, channels=2)
        print(
            f"audio_concat_rate={_fps_or_missing(cat)} channels={frame.size}",
            flush=True,
        )
        assert frame.size == 2
        assert _require_fps(cat) == pytest.approx(high_rate)


# ---------------------------------------------------------------------------
# F. Refusals
# ---------------------------------------------------------------------------


def test_concat_method_other_than_chain_or_compose_does_not_succeed():
    with workspace() as ws:
        w1, h1 = _even(6, 8), _even(5, 7)
        w2, h2 = w1 + _even(3, 5), h1 + _even(2, 4)
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        a = _color(ws, (w1, h1), c1, duration=0.6)
        b = _color(ws, (w2, h2), c2, duration=0.5)
        word = "weave_" + secrets.token_hex(3)
        while word.casefold() in {"chain", "compose"}:
            word = "weave_" + secrets.token_hex(3)
        failed = ws.call(concatenate_videoclips, [a, b], method=word)
        require_failed(failed)
        print(f"bad_method={word!r} err={failed.exception}", flush=True)
        chain = _concat(ws, [a, b], method="chain")
        compose = _concat(ws, [a, b], method="compose")
        chain_first = _frame(ws, chain, 0.2)
        chain_second = _frame(ws, chain, 0.6 + 0.2)
        compose_frame = _frame(ws, compose, 0.2)
        require_rgb_picture(chain_first, h1, w1, color=c1)
        require_rgb_picture(chain_second, h2, w2, color=c2)
        require_rgb_picture(compose_frame, max(h1, h2), max(w1, w2))
        assert failed.exception is not None


def test_write_overlay_of_stills_without_duration_does_not_succeed():
    with workspace() as ws:
        w, h = 16, 12
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        a = _color(ws, (w, h), c1, fps=8)
        b = _color(ws, (w, h), c2, fps=8)
        overlay = _overlay(ws, [a, b])
        missing = ws.resolve("overlay_no_duration.mp4")
        failed = ws.call(overlay.write_videofile, str(missing), logger=None)
        require_failed(failed)
        print(f"overlay_no_duration={failed.exception}", flush=True)
        assert not _complete_media(missing)
        rest = failure_identifies_missing_duration(failed, missing, (w, h), c1, c2)
        print(f"overlay_no_duration_rest={rest!r}", flush=True)
        fps_only = ws.resolve("overlay_fps_at_write.mp4")
        still_fps = ws.call(
            overlay.write_videofile, str(fps_only), fps=8, logger=None
        )
        require_failed(still_fps)
        assert not _complete_media(fps_only)
        failure_identifies_missing_duration(still_fps, fps_only, (w, h), c1, c2)
        finite = require_ok(ws.call(overlay.with_duration, 0.4))
        ok_path = ws.resolve("overlay_with_duration.mp4")
        require_ok(ws.call(finite.write_videofile, str(ok_path), logger=None))
        media_file_nonempty(ok_path)


def test_write_grid_of_stills_without_duration_does_not_succeed():
    with workspace() as ws:
        w, h = 16, 12
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        a = _color(ws, (w, h), c1, fps=8)
        b = _color(ws, (w, h), c2, fps=8)
        grid = _grid(ws, [[a, b]])
        missing = ws.resolve("grid_no_duration.mp4")
        failed = ws.call(grid.write_videofile, str(missing), logger=None)
        require_failed(failed)
        print(f"grid_no_duration={failed.exception}", flush=True)
        assert not _complete_media(missing)
        failure_identifies_missing_duration(failed, missing, (w, h), c1, c2)
        finite = require_ok(ws.call(grid.with_duration, 0.4))
        ok_path = ws.resolve("grid_with_duration.mp4")
        require_ok(ws.call(finite.write_videofile, str(ok_path), logger=None))
        media_file_nonempty(ok_path)


def test_write_composite_with_duration_but_no_frame_rate_does_not_succeed():
    """Duration-but-no-frame-rate write does not succeed (L265).

    Contrasts that refusal with a duration-missing write. Does not require
    the no-frame-rate refusal text to contain fps, frame rate, or framerate.
    """
    with workspace() as ws:
        w, h = 16, 12
        c1 = _rgb_away_from(_BLACK)
        c2 = _rgb_away_from(c1, _BLACK)
        a = _color(ws, (w, h), c1, duration=0.4)
        b = _color(ws, (w, h), c2, duration=0.4)
        comp = _overlay(ws, [a, b])
        assert _require_duration(comp) == pytest.approx(0.4)
        assert _fps_or_missing(comp) is None
        missing = ws.resolve("composite_no_fps.mp4")
        failed = ws.call(comp.write_videofile, str(missing), logger=None)
        require_failed(failed)
        print(f"composite_no_frame_rate={failed.exception}", flush=True)
        assert not _complete_media(missing)
        extra = require_ok(ws.call(comp.with_duration, 0.8))
        extra_path = ws.resolve("composite_more_duration.mp4")
        extra_failed = ws.call(extra.write_videofile, str(extra_path), logger=None)
        require_failed(extra_failed)
        assert not _complete_media(extra_path)
        ok_path = ws.resolve("composite_fps_at_write.mp4")
        require_ok(ws.call(comp.write_videofile, str(ok_path), fps=8, logger=None))
        media_file_nonempty(ok_path)
        duration_missing = _overlay(
            ws,
            [
                _color(ws, (w, h), c1, fps=8),
                _color(ws, (w, h), c2, fps=8),
            ],
        )
        dur_path = ws.resolve("composite_no_duration_contrast.mp4")
        dur_failed = ws.call(duration_missing.write_videofile, str(dur_path), logger=None)
        require_failed(dur_failed)
        dur_rest = failure_identifies_missing_duration(
            dur_failed, dur_path, (w, h), c1, c2
        )
        no_rate_rest = failure_remainder(failed, missing, (w, h), c1, c2)
        print(
            f"duration_contrast_rest={dur_rest!r} no_frame_rate_rest={no_rate_rest!r}",
            flush=True,
        )
        assert "duration" in dur_rest.casefold()
        assert dur_rest.casefold() != no_rate_rest.casefold()
