# feature: F07
"""Masks, opacity, and transparency (FP-07).

Assertions stay at the PRD's precision: mask vs non-mask frame contracts,
same-size attach as overlay visibility (1 / 0 / in-between blend), a
different-size mask is not that same-size visibility map, PNG frame alpha
matching the mask when alpha is left on (the default), opacity as a
multiply of the existing mask including factors outside 0–1, four-channel
76.5 → mask near 0.3 with stacked coverage, color↔mask conversion leaving
an already-correct clip unchanged, PNG still alpha on by default, and
cross-fade through the effect list. Exception types, failure wording, the
overlay mix formula, 8-bit rounding tables, GIF write, PNG alpha-off, and
crop/pad geometry are not pinned.
"""

from __future__ import annotations

import secrets
from pathlib import Path

import numpy as np
from clipkit import ColorClip, CompositeVideoClip, ImageClip, VideoClip, vfx

from _harness import HarnessError, workspace
from _helpers import (
    as_numeric_array,
    pictures_equal,
    require_failed,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
)
from F07_helpers import read_png_rgb_and_alpha, require_greyscale_frame

_RED = (255, 0, 0)
_GREEN = (0, 255, 0)
_BLUE = (0, 0, 255)
_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_DURATION = 1.2


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _even(lo: int, hi: int) -> int:
    return _rand_int(lo, hi) * 2


def _rect_size() -> tuple[int, int]:
    width = _even(8, 12)
    height = _even(7, 11)
    if width == height:
        height = width + 2
    return width, height


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(40, 220), _rand_int(40, 220), _rand_int(40, 220))


def _l1(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum(abs(x - y) for x, y in zip(a, b))


def _max_channel(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def _far_enough(candidate: tuple[int, int, int], banned: tuple[tuple[int, int, int], ...]) -> bool:
    # L1>90 alone is not enough: a 0.22–0.36 mix can still sit inside
    # atol=20 of an endpoint when the gap is spread across channels.
    return all(
        _l1(candidate, other) > 90 and _max_channel(candidate, other) >= 110
        for other in banned
    )


def _rgb_away_from(*others: tuple[int, int, int]) -> tuple[int, int, int]:
    banned = others + (_BLACK,)
    for _ in range(96):
        candidate = _rgb()
        if _far_enough(candidate, banned):
            return candidate
        forced = list(candidate)
        ch = _rand_int(0, 2)
        mean_ch = sum(other[ch] for other in banned) / len(banned)
        forced[ch] = 0 if mean_ch >= 128 else 255
        if forced[ch] == 0:
            forced[(ch + 1) % 3] = 255
        candidate = tuple(forced)
        if _far_enough(candidate, banned):
            return candidate
    extremes = (
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (0, 255, 255),
        (255, 0, 255),
        (255, 40, 40),
        (40, 255, 40),
        (40, 40, 255),
    )
    for candidate in extremes:
        if _far_enough(candidate, banned):
            return candidate
    raise AssertionError(f"could not pick a color away from {banned}")


def _picture_rgb(frame) -> np.ndarray:
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise AssertionError(
            f"expected a picture with at least 3 channels; got shape {arr.shape}"
        )
    return arr[:, :, :3]


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


def _frame(ws, clip, t=0.0):
    return require_ok(ws.call(clip.get_frame, t))


def _color(ws, size, color, duration=_DURATION, *, is_mask=False):
    return require_ok(
        ws.call(ColorClip, size, color=color, is_mask=is_mask, duration=duration)
    )


def _overlay(ws, clips, **kwargs):
    return require_ok(ws.call(CompositeVideoClip, clips, **kwargs))


def _attached_mask_frame(ws, clip, t: float = 0.0):
    mask = clip.mask
    if mask is None:
        return None
    return as_numeric_array(require_ok(ws.call(mask.get_frame, t)))


def _require_attached_mask(ws, clip, height: int, width: int, t: float = 0.0):
    raw = _attached_mask_frame(ws, clip, t)
    if raw is None:
        raise AssertionError("clip has no attached mask")
    return require_mask_picture(raw, height, width)


def _video_mask(ws, array, duration=_DURATION):
    arr = np.asarray(array, dtype=float)

    def frame_function(t):
        return arr.copy()

    return require_ok(
        ws.call(VideoClip, frame_function=frame_function, duration=duration, is_mask=True)
    )


def _write_rgba_png(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> Path:
    picture = as_numeric_array(rgb)
    alpha_arr = as_numeric_array(alpha)
    if picture.ndim != 3 or picture.shape[2] < 3:
        raise AssertionError(f"RGBA RGB plane has shape {picture.shape}")
    if alpha_arr.shape != picture.shape[:2]:
        raise AssertionError(
            f"alpha shape {alpha_arr.shape} does not match {picture.shape[:2]}"
        )
    packed = np.zeros(picture.shape[:2] + (4,), dtype=np.uint8)
    packed[:, :, :3] = np.round(picture[:, :, :3]).astype(np.uint8)
    packed[:, :, 3] = np.round(alpha_arr).astype(np.uint8)
    try:
        from PIL import Image
    except ImportError as exc:
        raise HarnessError(f"Pillow is required to write image fixtures: {exc}") from exc
    Image.fromarray(packed, mode="RGBA").save(path, format="PNG")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat written PNG {path}: {exc}") from exc
    if not path.is_file() or size <= 0:
        raise AssertionError(f"RGBA PNG was not written as a nonempty file: {path}")
    return path


def _quadrant_block(height: int, width: int) -> tuple[int, int, int, int]:
    """A unique opaque block inside one quadrant — not a vertical half-plane."""
    q = _rand_int(0, 3)
    mid_y, mid_x = height // 2, width // 2
    inset_y = max(1, height // 10)
    inset_x = max(1, width // 10)
    if q == 0:
        y0, y1 = inset_y, max(inset_y + 2, mid_y - inset_y)
        x0, x1 = inset_x, max(inset_x + 2, mid_x - inset_x)
    elif q == 1:
        y0, y1 = inset_y, max(inset_y + 2, mid_y - inset_y)
        x0, x1 = min(mid_x + inset_x, width - 3), width - inset_x
    elif q == 2:
        y0, y1 = min(mid_y + inset_y, height - 3), height - inset_y
        x0, x1 = inset_x, max(inset_x + 2, mid_x - inset_x)
    else:
        y0, y1 = min(mid_y + inset_y, height - 3), height - inset_y
        x0, x1 = min(mid_x + inset_x, width - 3), width - inset_x
    if y1 - y0 < 2:
        y1 = min(height, y0 + 2)
    if x1 - x0 < 2:
        x1 = min(width, x0 + 2)
    if x0 == 0 and x1 == width:
        raise AssertionError("quadrant block spanned the full width")
    if y0 == 0 and y1 == height and x0 == 0 and x1 == width // 2:
        raise AssertionError("quadrant block is a left vertical half")
    return y0, y1, x0, x1


def _sample_xy(y0: int, y1: int, x0: int, x1: int) -> tuple[int, int]:
    return (x0 + x1) // 2, (y0 + y1) // 2


def _outside_block(
    height: int, width: int, y0: int, y1: int, x0: int, x1: int
) -> tuple[int, int]:
    for y, x in (
        (1, 1),
        (1, width - 2),
        (height - 2, 1),
        (height - 2, width - 2),
        (height // 2, width // 2),
    ):
        if not (y0 <= y < y1 and x0 <= x < x1):
            return x, y
    raise AssertionError("could not find a pixel outside the unique block")


def _left_right_mask(height: int, width: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=float)
    mask[:, : width // 2] = 1.0
    return mask


def _block_mask(
    height: int, width: int, y0: int, y1: int, x0: int, x1: int, fill: float = 1.0
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=float)
    mask[y0:y1, x0:x1] = fill
    return mask


def _png_nonempty(path: Path) -> int:
    try:
        if not path.is_file():
            raise FileNotFoundError(f"PNG was not written: {path}")
        size = path.stat().st_size
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat PNG {path}: {exc}") from exc
    if size <= 0:
        raise AssertionError(f"PNG is empty: {path}")
    return size


def _apply_crossfade(ws, clip, effect):
    return require_ok(ws.call(clip.with_effects, [effect]))


# ---------------------------------------------------------------------------
# A. Mask vs non-mask frame contracts
# ---------------------------------------------------------------------------


def test_non_mask_frames_are_hw3_in_0_255():
    with workspace() as ws:
        oracle = require_ok(ws.call(ColorClip, (16, 16), color=_RED, duration=_DURATION))
        oracle_frame = _frame(ws, oracle, 0.0)
        print(f"oracle_red shape={as_numeric_array(oracle_frame).shape}", flush=True)
        require_rgb_picture(oracle_frame, 16, 16, color=_RED)

        width, height = _rect_size()
        color = _rgb_away_from(_RED)
        clip = _color(ws, (width, height), color)
        frame = _frame(ws, clip, 0.0)
        print(
            f"non_mask size={(width, height)} color={color} shape={as_numeric_array(frame).shape}",
            flush=True,
        )
        picture = require_rgb_picture(frame, height, width, color=color)
        assert picture.shape == (height, width, 3)


def test_mask_mode_frames_are_hw_in_0_1():
    with workspace() as ws:
        width, height = _rect_size()
        level = 0.15 + _rand_int(1, 70) / 100.0
        clip = _color(ws, (width, height), level, is_mask=True)
        frame = _frame(ws, clip, 0.0)
        print(
            f"mask_mode size={(width, height)} level={level} shape={as_numeric_array(frame).shape}",
            flush=True,
        )
        mask = require_mask_picture(frame, height, width)
        assert np.allclose(mask, level, atol=1e-5)
        sibling = _color(ws, (width, height), _rgb_away_from())
        rgb_frame = _frame(ws, sibling, 0.0)
        require_rgb_picture(rgb_frame, height, width)
        assert as_numeric_array(rgb_frame).shape != as_numeric_array(frame).shape


def test_generated_mask_clip_obeys_greyscale_contract():
    with workspace() as ws:
        width, height = _rect_size()
        y0, y1, x0, x1 = _quadrant_block(height, width)
        source = np.full((height, width), 0.2, dtype=float)
        source[y0:y1, x0:x1] = 0.85

        def frame_function(t):
            return source.copy()

        clip = require_ok(
            ws.call(
                VideoClip,
                frame_function=frame_function,
                duration=_DURATION,
                is_mask=True,
            )
        )
        frame = _frame(ws, clip, 0.0)
        print(
            f"generated_mask shape={as_numeric_array(frame).shape} "
            f"block=({x0},{y0})-({x1},{y1})",
            flush=True,
        )
        mask = require_mask_picture(frame, height, width)
        assert np.allclose(mask, source, atol=1e-5)
        assert as_numeric_array(frame).ndim == 2


# ---------------------------------------------------------------------------
# B. Same-size mask is overlay visibility; PNG frame alpha
# ---------------------------------------------------------------------------


def test_oracle_left_opaque_right_transparent_red_on_blue():
    with workspace() as ws:
        width, height = 16, 16
        lower = _color(ws, (width, height), _BLUE)
        upper = _color(ws, (width, height), _RED)
        mask = _video_mask(ws, _left_right_mask(height, width))
        masked = require_ok(ws.call(upper.with_mask, mask))
        comp = _overlay(ws, [lower, masked])
        frame = _frame(ws, comp, 0.0)
        left_x, right_x = width // 4, width - width // 4
        y = height // 2
        print(
            f"oracle_lr left={_rgb_at(frame, left_x, y)} right={_rgb_at(frame, right_x, y)}",
            flush=True,
        )
        require_rgb_picture(frame, height, width)
        _assert_color_at(frame, left_x, y, _RED)
        _assert_color_at(frame, right_x, y, _BLUE)
        _assert_not_color_at(frame, left_x, y, _BLUE)
        _assert_not_color_at(frame, right_x, y, _RED)
        assert not pictures_equal(frame, _frame(ws, upper, 0.0))


def test_same_size_mask_is_overlay_visibility_map():
    with workspace() as ws:
        width, height = _rect_size()
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        y0, y1, x0, x1 = _quadrant_block(height, width)
        lower = _color(ws, (width, height), lower_c)
        upper = _color(ws, (width, height), upper_c)
        mask = _video_mask(ws, _block_mask(height, width, y0, y1, x0, x1, 1.0))
        masked = require_ok(ws.call(upper.with_mask, mask))
        attached = _overlay(ws, [lower, masked])
        stripped = _overlay(ws, [lower, upper])
        attached_frame = _frame(ws, attached, 0.0)
        stripped_frame = _frame(ws, stripped, 0.0)
        bx, by = _sample_xy(y0, y1, x0, x1)
        ox, oy = _outside_block(height, width, y0, y1, x0, x1)
        print(
            f"visibility block=({bx},{by}) outside=({ox},{oy}) "
            f"q=({x0},{y0})-({x1},{y1})",
            flush=True,
        )
        require_rgb_picture(attached_frame, height, width)
        _assert_color_at(attached_frame, bx, by, upper_c)
        _assert_color_at(attached_frame, ox, oy, lower_c)
        require_rgb_picture(stripped_frame, height, width, color=upper_c)
        assert not pictures_equal(attached_frame, stripped_frame)


def test_in_between_mask_blends_upper_and_lower():
    with workspace() as ws:
        width, height = _even(10, 14), _even(10, 14)
        if height < 12:
            height = 12
        if width < 12:
            width = 12
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        other_lower = _rgb_away_from(lower_c, upper_c)
        other_upper = _rgb_away_from(lower_c, upper_c, other_lower)
        mid_a = 0.22 + _rand_int(0, 10) / 100.0
        mid_b = 0.68 + _rand_int(0, 10) / 100.0
        if abs(mid_a - 0.5) < 0.04:
            mid_a = 0.28
        if abs(mid_b - 0.5) < 0.04:
            mid_b = 0.72
        hy, hx = height // 2, width // 2
        pattern = np.zeros((height, width), dtype=float)
        pattern[:hy, :hx] = 1.0
        pattern[:hy, hx:] = 0.0
        pattern[hy:, :hx] = mid_a
        pattern[hy:, hx:] = mid_b
        # The 1/0 split here is a 2×2 grid, not a vertical half-plane of the
        # whole frame: the opaque block is one quadrant.
        mask = _video_mask(ws, pattern)
        lower = _color(ws, (width, height), lower_c)
        upper = _color(ws, (width, height), upper_c)
        masked = require_ok(ws.call(upper.with_mask, mask))
        comp = _overlay(ws, [lower, masked])
        frame = _frame(ws, comp, 0.0)
        x1, y1 = hx // 2, hy // 2
        x0, y0 = hx + (width - hx) // 2, hy // 2
        xa, ya = hx // 2, hy + (height - hy) // 2
        xb, yb = hx + (width - hx) // 2, hy + (height - hy) // 2
        print(
            f"blend 1={_rgb_at(frame, x1, y1)} 0={_rgb_at(frame, x0, y0)} "
            f"mid_a={mid_a} {_rgb_at(frame, xa, ya)} "
            f"mid_b={mid_b} {_rgb_at(frame, xb, yb)}",
            flush=True,
        )
        require_rgb_picture(frame, height, width)
        _assert_color_at(frame, x1, y1, upper_c)
        _assert_color_at(frame, x0, y0, lower_c)
        _assert_not_color_at(frame, xa, ya, upper_c, atol=20)
        _assert_not_color_at(frame, xa, ya, lower_c, atol=20)
        _assert_not_color_at(frame, xb, yb, upper_c, atol=20)
        _assert_not_color_at(frame, xb, yb, lower_c, atol=20)
        assert not pictures_equal(
            _picture_rgb(frame)[ya : ya + 1, xa : xa + 1],
            _picture_rgb(frame)[yb : yb + 1, xb : xb + 1],
        )

        def overlay_with(upper_color, lower_color):
            lo = _color(ws, (width, height), lower_color)
            up = _color(ws, (width, height), upper_color)
            m = require_ok(ws.call(up.with_mask, mask))
            return _frame(ws, _overlay(ws, [lo, m]), 0.0)

        same_upper_a = overlay_with(upper_c, lower_c)
        same_upper_b = overlay_with(upper_c, other_lower)
        opaque_upper = _frame(ws, _overlay(ws, [_color(ws, (width, height), lower_c), _color(ws, (width, height), upper_c)]), 0.0)
        bare_a = _frame(ws, _color(ws, (width, height), lower_c), 0.0)
        bare_b = _frame(ws, _color(ws, (width, height), other_lower), 0.0)
        pix_a = _rgb_at(same_upper_a, xa, ya)
        pix_b = _rgb_at(same_upper_b, xa, ya)
        print(f"swap_lower mid_a {pix_a} vs {pix_b}", flush=True)
        assert pix_a != pix_b
        _assert_not_color_at(same_upper_a, xa, ya, upper_c, atol=20)
        _assert_not_color_at(same_upper_b, xa, ya, upper_c, atol=20)
        _assert_not_color_at(same_upper_a, xa, ya, lower_c, atol=20)
        _assert_not_color_at(same_upper_b, xa, ya, other_lower, atol=20)
        assert not pictures_equal(same_upper_a, opaque_upper)
        assert not pictures_equal(same_upper_a, bare_a)
        assert not pictures_equal(same_upper_b, bare_b)

        same_lower_a = overlay_with(upper_c, lower_c)
        same_lower_b = overlay_with(other_upper, lower_c)
        print(
            f"swap_upper mid_a {_rgb_at(same_lower_a, xa, ya)} vs "
            f"{_rgb_at(same_lower_b, xa, ya)}",
            flush=True,
        )
        assert _rgb_at(same_lower_a, xa, ya) != _rgb_at(same_lower_b, xa, ya)


def test_png_frame_alpha_matches_mask_by_default():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb_away_from()
        hy, hx = height // 2, width // 2
        mid_a = 0.25 + _rand_int(0, 8) / 100.0
        mid_b = 0.62 + _rand_int(0, 8) / 100.0
        # 2×2 quadrants: one is 1, one is 0, two distinct mids — not a vertical half.
        pattern = np.zeros((height, width), dtype=float)
        pattern[:hy, :hx] = 1.0
        pattern[:hy, hx:] = 0.0
        pattern[hy:, :hx] = mid_a
        pattern[hy:, hx:] = mid_b
        y0, y1, x0, x1 = 0, hy, 0, hx
        oy0, oy1, ox0, ox1 = 0, hy, hx, width
        yb0, yb1, xb0, xb1 = hy, height, hx, width
        clip = _color(ws, (width, height), color)
        masked = require_ok(ws.call(clip.with_mask, _video_mask(ws, pattern)))
        on_path = ws.resolve("frame_on.png")
        require_ok(ws.call(masked.save_frame, str(on_path)))
        _png_nonempty(on_path)
        rgb_on, alpha_on = read_png_rgb_and_alpha(on_path)
        print(
            f"png_default alpha={'none' if alpha_on is None else alpha_on.shape} "
            f"block=({x0},{y0})-({x1},{y1}) mid_a={mid_a} mid_b={mid_b}",
            flush=True,
        )
        if alpha_on is None:
            raise AssertionError("default PNG frame write produced no alpha layer")
        if alpha_on.shape != (height, width):
            raise AssertionError(
                f"PNG alpha shape {alpha_on.shape} != {(height, width)}"
            )
        opaque = float(np.mean(alpha_on[y0:y1, x0:x1]))
        clear = float(np.mean(alpha_on[oy0:oy1, ox0:ox1]))
        a_mid = float(np.mean(alpha_on[np.isclose(pattern, mid_a)]))
        b_mid = float(np.mean(alpha_on[yb0:yb1, xb0:xb1]))
        print(
            f"png_alpha opaque={opaque:.1f} clear={clear:.1f} "
            f"mid_a={a_mid:.1f} mid_b={b_mid:.1f}",
            flush=True,
        )
        assert opaque > 200.0
        assert clear < 40.0
        assert 20.0 < a_mid < 230.0
        assert 20.0 < b_mid < 230.0
        assert abs(a_mid - b_mid) > 12.0
        assert abs(a_mid - opaque) > 12.0
        assert abs(b_mid - opaque) > 12.0
        assert abs(a_mid - clear) > 12.0
        left_half = float(np.mean(alpha_on[:, : width // 2]))
        right_half = float(np.mean(alpha_on[:, width // 2 :]))
        top_half = float(np.mean(alpha_on[: height // 2, :]))
        bot_half = float(np.mean(alpha_on[height // 2 :, :]))
        print(
            f"png_half_means L={left_half:.1f} R={right_half:.1f} "
            f"T={top_half:.1f} B={bot_half:.1f}",
            flush=True,
        )
        if abs(left_half - 255.0) < 8 and abs(right_half) < 8:
            raise AssertionError("PNG alpha is a vertical left/right half, not the quadrant block")
        if abs(right_half - 255.0) < 8 and abs(left_half) < 8:
            raise AssertionError("PNG alpha is a vertical left/right half, not the quadrant block")


# ---------------------------------------------------------------------------
# C. Opacity multiplies the existing mask
# ---------------------------------------------------------------------------


def test_oracle_opacity_half_green_on_red_is_blend():
    with workspace() as ws:
        width, height = 20, 16
        red = _color(ws, (width, height), _RED)
        green = _color(ws, (width, height), _GREEN)
        faded = require_ok(ws.call(green.with_opacity, 0.5))
        mask = _require_attached_mask(ws, faded, height, width)
        print(f"opacity_half mask_mean={float(mask.mean()):.4f}", flush=True)
        assert np.allclose(mask, 0.5, atol=1e-5)
        blended = _overlay(ws, [red, faded])
        frame = _frame(ws, blended, 0.0)
        cx, cy = width // 2, height // 2
        print(f"opacity_half center={_rgb_at(frame, cx, cy)}", flush=True)
        require_rgb_picture(frame, height, width)
        _assert_not_color_at(frame, cx, cy, _RED, atol=20)
        _assert_not_color_at(frame, cx, cy, _GREEN, atol=20)

        other_c = _rgb_away_from(_RED, _GREEN)
        other_lower = _color(ws, (width, height), other_c)
        other = _frame(ws, _overlay(ws, [other_lower, faded]), 0.0)
        opaque = _frame(ws, _overlay(ws, [other_lower, green]), 0.0)
        bare = _frame(ws, other_lower, 0.0)
        print(
            f"other_lower={_rgb_at(other, cx, cy)} opaque={_rgb_at(opaque, cx, cy)} "
            f"bare={_rgb_at(bare, cx, cy)}",
            flush=True,
        )
        assert not pictures_equal(frame, other)
        assert not pictures_equal(other, opaque)
        assert not pictures_equal(other, bare)
        _assert_not_color_at(other, cx, cy, _GREEN, atol=20)
        _assert_not_color_at(other, cx, cy, other_c, atol=20)

        other_upper_c = _rgb_away_from(_RED, _GREEN, other_c)
        other_upper = require_ok(
            ws.call(_color(ws, (width, height), other_upper_c).with_opacity, 0.5)
        )
        swapped_upper = _frame(ws, _overlay(ws, [red, other_upper]), 0.0)
        print(f"swap_upper={_rgb_at(swapped_upper, cx, cy)}", flush=True)
        assert not pictures_equal(frame, swapped_upper)


def test_opacity_multiplies_existing_mask():
    with workspace() as ws:
        width, height = _rect_size()
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        y0, y1, x0, x1 = _quadrant_block(height, width)
        high, hole = 1.0, 0.0
        source = np.full((height, width), hole, dtype=float)
        source[y0:y1, x0:x1] = high
        factor = 0.25 + _rand_int(1, 40) / 100.0
        if abs(factor - 0.5) < 0.04:
            factor = 0.35
        lower = _color(ws, (width, height), lower_c)
        upper = _color(ws, (width, height), upper_c)
        mask_clip = _video_mask(ws, source)
        masked = require_ok(ws.call(upper.with_mask, mask_clip))
        before = as_numeric_array(_frame(ws, mask_clip, 0.0))
        require_mask_picture(before, height, width)
        faded = require_ok(ws.call(masked.with_opacity, factor))
        after_raw = _attached_mask_frame(ws, faded)
        if after_raw is None:
            raise AssertionError("opacity result has no attached mask")
        after = require_mask_picture(after_raw, height, width)
        expected = before.astype(float) * factor
        print(
            f"multiply f={factor} before_high={float(before[y0:y1, x0:x1].mean()):.3f} "
            f"after_high={float(after[y0:y1, x0:x1].mean()):.3f}",
            flush=True,
        )
        assert np.allclose(after, expected, atol=1e-4, rtol=1e-4)
        assert float(np.std(after)) > 1e-4

        baseline = _frame(ws, _overlay(ws, [lower, masked]), 0.0)
        scaled = _frame(ws, _overlay(ws, [lower, faded]), 0.0)
        bx, by = _sample_xy(y0, y1, x0, x1)
        ox, oy = _outside_block(height, width, y0, y1, x0, x1)
        print(
            f"overlay high={_rgb_at(scaled, bx, by)} hole={_rgb_at(scaled, ox, oy)} "
            f"baseline_high={_rgb_at(baseline, bx, by)}",
            flush=True,
        )
        _assert_color_at(baseline, bx, by, upper_c, atol=8)
        _assert_color_at(baseline, ox, oy, lower_c, atol=8)
        _assert_not_color_at(scaled, bx, by, upper_c, atol=20)
        _assert_color_at(scaled, ox, oy, lower_c, atol=8)
        assert _rgb_at(scaled, bx, by) != _rgb_at(scaled, ox, oy)
        assert float(np.std(_picture_rgb(scaled).astype(float))) > 1.0


def test_opacity_factors_outside_unit_interval_scale_the_same_way():
    with workspace() as ws:
        width, height = _rect_size()
        y0, y1, x0, x1 = _quadrant_block(height, width)
        source = np.full((height, width), 0.3, dtype=float)
        source[y0:y1, x0:x1] = 0.8
        upper = _color(ws, (width, height), _rgb_away_from())
        mask_clip = _video_mask(ws, source)
        masked = require_ok(ws.call(upper.with_mask, mask_clip))
        before = as_numeric_array(_frame(ws, mask_clip, 0.0)).astype(float)
        doubled = require_ok(ws.call(masked.with_opacity, 2.0))
        negated = require_ok(ws.call(masked.with_opacity, -0.5))
        raw_2 = _attached_mask_frame(ws, doubled)
        raw_neg = _attached_mask_frame(ws, negated)
        if raw_2 is None or raw_neg is None:
            raise AssertionError("out-of-range opacity dropped the attached mask")
        got_2 = require_greyscale_frame(raw_2, height, width)
        got_neg = require_greyscale_frame(raw_neg, height, width)
        print(
            f"out_of_range ×2 high={float(got_2[y0:y1, x0:x1].mean()):.3f} "
            f"×-0.5 high={float(got_neg[y0:y1, x0:x1].mean()):.3f}",
            flush=True,
        )
        assert np.allclose(got_2, before * 2.0, atol=1e-4, rtol=1e-4)
        assert np.allclose(got_neg, before * -0.5, atol=1e-4, rtol=1e-4)
        assert float(np.std(got_2)) > 1e-4
        assert not np.allclose(got_2, 2.0, atol=1e-3)


# ---------------------------------------------------------------------------
# D. Four-channel color → mask; stacked coverage
# ---------------------------------------------------------------------------


def test_oracle_four_channel_76_5_is_mask_near_0_3():
    with workspace() as ws:
        width, height = _rect_size()
        rgb = _rgb_away_from()
        clip = _color(ws, (width, height), (*rgb, 76.5))
        picture = _frame(ws, clip, 0.0)
        require_rgb_picture(picture, height, width, color=rgb)
        layer_mask = _require_attached_mask(ws, clip, height, width)
        print(
            f"four_ch_76.5 layer_mask_mean={float(layer_mask.mean()):.4f} rgb={rgb}",
            flush=True,
        )
        assert np.allclose(layer_mask, 76.5 / 255.0, atol=0.02)
        assert abs(float(layer_mask.mean()) - 0.3) < 0.03
        voided = _overlay(ws, [clip], bg_color=None)
        comp_mask_raw = _attached_mask_frame(ws, voided)
        if comp_mask_raw is None:
            raise AssertionError("void overlay of a four-channel layer has no mask")
        comp_mask = require_mask_picture(comp_mask_raw, height, width)
        print(f"void_composite_mask_mean={float(comp_mask.mean()):.4f}", flush=True)
        assert abs(float(comp_mask.mean()) - 0.3) < 0.05


def test_fourth_channel_scales_into_unit_interval():
    with workspace() as ws:
        width, height = _rect_size()
        rgb = _rgb_away_from()
        low_a = _rand_int(20, 90)
        high_a = _rand_int(130, 220)
        if low_a == 76 or low_a == 77:
            low_a = 40
        if high_a == 76 or high_a == 77:
            high_a = 180
        low = _color(ws, (width, height), (*rgb, low_a))
        high = _color(ws, (width, height), (*rgb, high_a))
        low_m = _require_attached_mask(ws, low, height, width)
        high_m = _require_attached_mask(ws, high, height, width)
        print(
            f"fourth_channel A_lo={low_a} μ={float(low_m.mean()):.4f} "
            f"A_hi={high_a} μ={float(high_m.mean()):.4f}",
            flush=True,
        )
        assert not np.allclose(low_m, high_m, atol=1e-4)
        assert float(high_m.mean()) > float(low_m.mean())
        assert abs(float(low_m.mean()) - low_a / 255.0) < 0.03
        assert abs(float(high_m.mean()) - high_a / 255.0) < 0.03


def test_stacked_four_channel_layers_accumulate_coverage():
    with workspace() as ws:
        width, height = _rect_size()
        rgb = _rgb_away_from()
        alpha = 76.5

        def layer():
            return _color(ws, (width, height), (*rgb, alpha))

        one = _overlay(ws, [layer()], bg_color=None)
        two = _overlay(ws, [layer(), layer()], bg_color=None)
        three = _overlay(ws, [layer(), layer(), layer()], bg_color=None)
        cx, cy = width // 2, height // 2

        def coverage(comp):
            raw = _attached_mask_frame(ws, comp)
            if raw is None:
                raise AssertionError("stacked void overlay has no composite mask")
            mask = require_mask_picture(raw, height, width)
            return float(mask[cy, cx])

        c1, c2, c3 = coverage(one), coverage(two), coverage(three)
        print(f"stack coverage 1={c1:.4f} 2={c2:.4f} 3={c3:.4f}", flush=True)
        assert abs(c1 - c2) > 1e-3
        assert abs(c2 - c3) > 1e-3
        assert abs(c1 - c3) > 1e-3
        assert c2 > c1
        assert c3 > c2
        assert abs(c1 - 0.3) < 0.05


# ---------------------------------------------------------------------------
# E. Color ↔ mask conversion
# ---------------------------------------------------------------------------


def test_oracle_white_color_to_mask_near_1():
    with workspace() as ws:
        width, height = _rect_size()
        white = _color(ws, (width, height), _WHITE)
        white_mask = require_ok(ws.call(white.to_mask))
        frame = _frame(ws, white_mask, 0.0)
        mask = require_mask_picture(frame, height, width)
        print(f"white_to_mask mean={float(mask.mean()):.4f}", flush=True)
        assert np.allclose(mask, 1.0, atol=1e-3)

        black = _color(ws, (width, height), _BLACK)
        black_mask = require_ok(ws.call(black.to_mask))
        black_frame = require_mask_picture(_frame(ws, black_mask, 0.0), height, width)
        print(f"black_to_mask mean={float(black_frame.mean()):.4f}", flush=True)
        assert np.allclose(black_frame, 0.0, atol=1e-3)

        grey_v = _rand_int(40, 210)
        grey = _color(ws, (width, height), (grey_v, grey_v, grey_v))
        grey_mask = require_ok(ws.call(grey.to_mask))
        grey_frame = require_mask_picture(_frame(ws, grey_mask, 0.0), height, width)
        print(f"grey {grey_v} to_mask mean={float(grey_frame.mean()):.4f}", flush=True)
        assert abs(float(grey_frame.mean()) - grey_v / 255.0) < 0.02
        assert not np.allclose(grey_frame, 0.0, atol=0.05)
        assert not np.allclose(grey_frame, 1.0, atol=0.05)


def test_mask_to_color_repeats_greyscale_into_three_channels():
    with workspace() as ws:
        width, height = _rect_size()
        ones = _color(ws, (width, height), 1.0, is_mask=True)
        white = require_ok(ws.call(ones.to_RGB))
        white_frame = _frame(ws, white, 0.0)
        print(f"mask1_to_rgb shape={as_numeric_array(white_frame).shape}", flush=True)
        require_rgb_picture(white_frame, height, width, color=_WHITE)

        level = 0.2 + _rand_int(1, 60) / 100.0
        if abs(level - 1.0) < 1e-6:
            level = 0.4
        src = _color(ws, (width, height), level, is_mask=True)
        rgb_clip = require_ok(ws.call(src.to_RGB))
        rgb_frame = require_rgb_picture(_frame(ws, rgb_clip, 0.0), height, width)
        channels = rgb_frame.astype(float).reshape(-1, 3)
        print(
            f"mask_{level:.3f}_to_rgb mean={tuple(channels.mean(axis=0))}",
            flush=True,
        )
        assert np.allclose(channels[:, 0], channels[:, 1], atol=1.5)
        assert np.allclose(channels[:, 1], channels[:, 2], atol=1.5)
        assert abs(float(channels[:, 0].mean()) - level * 255.0) < 2.0


def test_already_mask_to_mask_and_already_color_to_color_unchanged():
    with workspace() as ws:
        width, height = _rect_size()
        level = 0.3 + _rand_int(1, 40) / 100.0
        mask_clip = _color(ws, (width, height), level, is_mask=True)
        before_mask = _frame(ws, mask_clip, 0.0)
        again_mask = require_ok(ws.call(mask_clip.to_mask))
        after_mask = _frame(ws, again_mask, 0.0)
        print(
            f"already_mask shape={as_numeric_array(after_mask).shape} "
            f"level={level}",
            flush=True,
        )
        require_mask_picture(after_mask, height, width)
        assert np.allclose(
            as_numeric_array(before_mask).astype(float),
            as_numeric_array(after_mask).astype(float),
            atol=1e-5,
        )

        color = _rgb_away_from()
        color_clip = _color(ws, (width, height), color)
        before_rgb = _frame(ws, color_clip, 0.0)
        again_rgb = require_ok(ws.call(color_clip.to_RGB))
        after_rgb = _frame(ws, again_rgb, 0.0)
        require_rgb_picture(after_rgb, height, width, color=color)
        assert pictures_equal(before_rgb, after_rgb)


# ---------------------------------------------------------------------------
# F. PNG still alpha as mask
# ---------------------------------------------------------------------------


def test_png_still_alpha_is_mask_by_default():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb_away_from()
        y0, y1, x0, x1 = _quadrant_block(height, width)
        mid = _rand_int(60, 190)
        alpha = np.full((height, width), mid, dtype=np.uint8)
        alpha[y0:y1, x0:x1] = 255
        oy0 = 1 if y0 > height // 3 else height - 4
        ox0 = 1 if x0 > width // 3 else width - 4
        if y0 <= oy0 < y1 and x0 <= ox0 < x1:
            oy0, ox0 = 0, 0
            if y0 == 0 and x0 == 0:
                oy0, ox0 = height - 3, width - 3
        alpha[oy0 : oy0 + 3, ox0 : ox0 + 3] = 0
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[:, :] = np.asarray(color, dtype=np.uint8)
        path = _write_rgba_png(ws.resolve("still.png"), rgb, alpha)
        default = require_ok(ws.call(ImageClip, str(path), duration=_DURATION))
        explicit = require_ok(
            ws.call(ImageClip, str(path), duration=_DURATION, transparent=True)
        )
        picture = _frame(ws, default, 0.0)
        require_rgb_picture(picture, height, width, color=color)
        default_mask = _require_attached_mask(ws, default, height, width)
        on_mask = _require_attached_mask(ws, explicit, height, width)
        expected = alpha.astype(float) / 255.0
        print(
            f"png_still default_block={float(default_mask[y0:y1, x0:x1].mean()):.3f} "
            f"mid={mid} mask_mid={float(default_mask[alpha == mid].mean()):.3f}",
            flush=True,
        )
        assert np.allclose(default_mask, expected, atol=1.0 / 255.0 + 1e-6)
        assert np.allclose(on_mask, default_mask, atol=1e-6)
        assert abs(float(default_mask[y0:y1, x0:x1].mean()) - 1.0) < 0.02
        hole = default_mask[oy0 : oy0 + 3, ox0 : ox0 + 3]
        assert abs(float(hole.mean()) - 0.0) < 0.02
        mid_vals = default_mask[alpha == mid]
        assert abs(float(mid_vals.mean()) - mid / 255.0) < 0.02
        assert not np.allclose(mid_vals, 0.0, atol=0.05)
        assert not np.allclose(mid_vals, 1.0, atol=0.05)
        left = float(np.mean(default_mask[:, : width // 2]))
        right = float(np.mean(default_mask[:, width // 2 :]))
        if abs(left - 1.0) < 0.05 and abs(right) < 0.05:
            raise AssertionError("PNG still mask is a vertical half-plane")
        if abs(right - 1.0) < 0.05 and abs(left) < 0.05:
            raise AssertionError("PNG still mask is a vertical half-plane")


def test_png_transparency_off_does_not_use_alpha_as_mask():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb_away_from()
        y0, y1, x0, x1 = _quadrant_block(height, width)
        mid = _rand_int(70, 180)
        alpha = np.full((height, width), mid, dtype=np.uint8)
        alpha[y0:y1, x0:x1] = 255
        alpha[0:3, 0:3] = 0
        if y0 < 3 and x0 < 3:
            alpha[height - 3 : height, width - 3 : width] = 0
            alpha[0:3, 0:3] = mid
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[:, :] = np.asarray(color, dtype=np.uint8)
        path = _write_rgba_png(ws.resolve("still_off.png"), rgb, alpha)
        baseline = require_ok(ws.call(ImageClip, str(path), duration=_DURATION))
        expected = alpha.astype(float) / 255.0
        base_mask = _require_attached_mask(ws, baseline, height, width)
        assert np.allclose(base_mask, expected, atol=1.0 / 255.0 + 1e-6)
        off = require_ok(
            ws.call(ImageClip, str(path), duration=_DURATION, transparent=False)
        )
        off_rgb = _picture_rgb(_frame(ws, off, 0.0))
        require_rgb_picture(off_rgb, height, width, color=color)
        off_mask = _attached_mask_frame(ws, off)
        print(f"png_off mask_present={off_mask is not None}", flush=True)
        if off_mask is not None:
            off_arr = require_mask_picture(off_mask, height, width)
            assert not np.allclose(off_arr, expected, atol=0.05)


def test_png_still_mask_is_overlay_visibility():
    with workspace() as ws:
        width, height = _rect_size()
        png_c = _rgb_away_from()
        lower_c = _rgb_away_from(png_c)
        y0, y1, x0, x1 = _quadrant_block(height, width)
        alpha = np.zeros((height, width), dtype=np.uint8)
        alpha[y0:y1, x0:x1] = 255
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        rgb[:, :] = np.asarray(png_c, dtype=np.uint8)
        path = _write_rgba_png(ws.resolve("still_overlay.png"), rgb, alpha)
        still = require_ok(ws.call(ImageClip, str(path), duration=_DURATION))
        off = require_ok(
            ws.call(ImageClip, str(path), duration=_DURATION, transparent=False)
        )
        lower = _color(ws, (width, height), lower_c)
        on_comp = _overlay(ws, [lower, still])
        on_frame = _frame(ws, on_comp, 0.0)
        opaque = _color(ws, (width, height), png_c)
        covered = _frame(ws, _overlay(ws, [lower, opaque]), 0.0)
        bx, by = _sample_xy(y0, y1, x0, x1)
        ox, oy = _outside_block(height, width, y0, y1, x0, x1)
        print(
            f"png_overlay on_block={_rgb_at(on_frame, bx, by)} "
            f"on_out={_rgb_at(on_frame, ox, oy)} "
            f"opaque_out={_rgb_at(covered, ox, oy)}",
            flush=True,
        )
        _assert_color_at(on_frame, bx, by, png_c, atol=8)
        _assert_color_at(on_frame, ox, oy, lower_c, atol=8)
        _assert_color_at(covered, ox, oy, png_c, atol=8)
        assert not pictures_equal(on_frame, covered)
        require_rgb_picture(_picture_rgb(_frame(ws, off, 0.0)), height, width, color=png_c)
        off_mask = _attached_mask_frame(ws, off)
        expected = alpha.astype(float) / 255.0
        print(f"png_overlay_off mask_present={off_mask is not None}", flush=True)
        if off_mask is not None:
            off_arr = require_mask_picture(off_mask, height, width)
            assert not np.allclose(off_arr, expected, atol=0.05)


# ---------------------------------------------------------------------------
# G. Cross-fade in / out via the effect list
# ---------------------------------------------------------------------------


def test_crossfade_in_overlay_goes_from_lower_to_upper():
    with workspace() as ws:
        width, height = _rect_size()
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        fade_d = 0.35 + _rand_int(1, 8) / 10.0
        play = fade_d + 0.55 + _rand_int(0, 4) / 10.0
        assert play > fade_d
        lower = _color(ws, (width, height), lower_c, duration=play)
        upper = _color(ws, (width, height), upper_c, duration=play)
        faded = _apply_crossfade(ws, upper, vfx.CrossFadeIn(fade_d))
        comp = _overlay(ws, [lower, faded])
        t0 = 0.0
        t_mid = fade_d * (0.28 + _rand_int(0, 8) / 100.0)
        t_end = fade_d + min(0.2, (play - fade_d) * 0.4)
        if not (0.0 < t_mid < fade_d):
            raise AssertionError(f"mid time {t_mid} not in (0, {fade_d})")
        if t_end < fade_d or t_end >= play:
            raise AssertionError(f"end time {t_end} not in [{fade_d}, {play})")
        at0 = _frame(ws, comp, t0)
        at_mid = _frame(ws, comp, t_mid)
        at_end = _frame(ws, comp, t_end)
        cx, cy = width // 2, height // 2
        print(
            f"fade_in D={fade_d:.2f} play={play:.2f} t_mid={t_mid:.3f} "
            f"t0={_rgb_at(at0, cx, cy)} mid={_rgb_at(at_mid, cx, cy)} "
            f"end={_rgb_at(at_end, cx, cy)}",
            flush=True,
        )
        _assert_color_at(at0, cx, cy, lower_c, atol=12)
        _assert_color_at(at_end, cx, cy, upper_c, atol=12)
        # Interior arm is a live contrast against the proven ends, not
        # atol=20 vs the requested colors: a correct linear fade at ~28%
        # of D can still sit inside that box when L1>90 is spread across
        # channels. Do not pin a 50% mix or an easing curve.
        mid_px = _rgb_at(at_mid, cx, cy)
        t0_px = _rgb_at(at0, cx, cy)
        end_px = _rgb_at(at_end, cx, cy)
        print(
            f"fade_in interior mid={mid_px} vs t0={t0_px} end={end_px}",
            flush=True,
        )
        assert mid_px != t0_px
        assert mid_px != end_px


def test_crossfade_out_overlay_goes_from_upper_to_lower():
    with workspace() as ws:
        width, height = _rect_size()
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        fade_d = 0.4 + _rand_int(1, 7) / 10.0
        lower = _color(ws, (width, height), lower_c, duration=fade_d)
        upper = _color(ws, (width, height), upper_c, duration=fade_d)
        faded = _apply_crossfade(ws, upper, vfx.CrossFadeOut(fade_d))
        comp = _overlay(ws, [lower, faded])
        t0 = 0.0
        t_mid = fade_d * (0.3 + _rand_int(0, 10) / 100.0)
        # Fully-transparent end is near D, still strictly inside the play
        # window (t>=D has left it). Remaining upper mix is 1 - t/D; with
        # atol=12 that remainder must be <= 12/255 even when one channel
        # differs by 255. 0.92 left 0.08 (~20 levels) and failed a correct
        # linear fade. Do not pin a 50% mix or an easing curve.
        t_end = fade_d * (0.985 + _rand_int(0, 10) / 1000.0)
        if not (0.0 < t_mid < fade_d):
            raise AssertionError(f"mid time {t_mid} not in (0, {fade_d})")
        if not (t_mid < t_end < fade_d):
            raise AssertionError(
                f"end sample {t_end} not in ({t_mid}, {fade_d})"
            )
        at0 = _frame(ws, comp, t0)
        at_mid = _frame(ws, comp, t_mid)
        at_end = _frame(ws, comp, t_end)
        cx, cy = width // 2, height // 2
        print(
            f"fade_out D={fade_d:.2f} t_mid={t_mid:.3f} t_end={t_end:.3f} "
            f"t0={_rgb_at(at0, cx, cy)} mid={_rgb_at(at_mid, cx, cy)} "
            f"end={_rgb_at(at_end, cx, cy)}",
            flush=True,
        )
        _assert_color_at(at0, cx, cy, upper_c, atol=12)
        _assert_color_at(at_end, cx, cy, lower_c, atol=12)
        mid_px = _rgb_at(at_mid, cx, cy)
        t0_px = _rgb_at(at0, cx, cy)
        end_px = _rgb_at(at_end, cx, cy)
        print(
            f"fade_out interior mid={mid_px} vs t0={t0_px} end={end_px}",
            flush=True,
        )
        assert mid_px != t0_px
        assert mid_px != end_px


# ---------------------------------------------------------------------------
# H. Mask-mode RGB is refused; mismatched size is not a same-size attach
# ---------------------------------------------------------------------------


def test_mask_mode_solid_color_rejects_rgb_triple():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb_away_from(_RED)
        failed = ws.call(ColorClip, (width, height), color=color, is_mask=True)
        print(f"mask_rgb_failed={failed.exception is not None} color={color}", flush=True)
        require_failed(failed)
        level = 0.2 + _rand_int(1, 60) / 100.0
        sibling = _color(ws, (width, height), level, is_mask=True)
        mask = require_mask_picture(_frame(ws, sibling, 0.0), height, width)
        assert np.allclose(mask, level, atol=1e-5)


def test_mismatched_size_mask_is_not_same_size_overlay_visibility():
    """A different-size mask is not a successful same-size attach (L291).

    Overlay 1 / 0 / blend visibility is specified only when the mask and the
    clip share the same size. Live baseline: a clip-sized copy of the same
    1 / 0 / in-between pattern does apply that map. The mismatched pair must
    not produce that overlay. Does not pin a raised error, a crop/pad
    geometry, or failure wording.
    """
    with workspace() as ws:
        width, height = _rect_size()
        small_w, small_h = width // 2, height // 2
        if (small_w, small_h) == (width, height):
            raise AssertionError("need a strictly smaller mask than the clip")
        if small_w < 4 or small_h < 4:
            raise AssertionError(
                f"small mask {(small_w, small_h)} is too small to split 1/0/blend"
            )
        # Oracle red-on-blue: far apart so 1 / 0 / in-between stay distinguishable.
        lower_c = _BLUE
        upper_c = _RED
        mid_a = 0.35
        mid_b = 0.7
        hy, hx = small_h // 2, small_w // 2
        pattern = np.zeros((small_h, small_w), dtype=float)
        pattern[:hy, :hx] = 1.0
        pattern[:hy, hx:] = 0.0
        pattern[hy:, :hx] = mid_a
        pattern[hy:, hx:] = mid_b
        # Clip-sized 1/0/blend map with the same pattern. Treating the
        # mismatched mask as a successful same-size attach by filling the
        # clip with this pattern would produce this overlay.
        same_pattern = np.repeat(np.repeat(pattern, 2, axis=0), 2, axis=1)
        if same_pattern.shape != (height, width):
            raise AssertionError(
                f"scaled pattern {same_pattern.shape} != {(height, width)}"
            )
        lower = _color(ws, (width, height), lower_c)
        upper = _color(ws, (width, height), upper_c)
        same_masked = require_ok(ws.call(upper.with_mask, _video_mask(ws, same_pattern)))
        same_frame = _frame(ws, _overlay(ws, [lower, same_masked]), 0.0)
        require_rgb_picture(same_frame, height, width)
        x1, y1 = _sample_xy(0, 2 * hy, 0, 2 * hx)
        x0, y0 = _sample_xy(0, 2 * hy, 2 * hx, width)
        xa, ya = _sample_xy(2 * hy, height, 0, 2 * hx)
        xb, yb = _sample_xy(2 * hy, height, 2 * hx, width)
        print(
            f"same_size_map 1={_rgb_at(same_frame, x1, y1)} "
            f"0={_rgb_at(same_frame, x0, y0)} "
            f"mid_a={_rgb_at(same_frame, xa, ya)} "
            f"mid_b={_rgb_at(same_frame, xb, yb)} "
            f"clip={(width, height)} small={(small_w, small_h)}",
            flush=True,
        )
        _assert_color_at(same_frame, x1, y1, upper_c)
        _assert_color_at(same_frame, x0, y0, lower_c)
        _assert_not_color_at(same_frame, xa, ya, upper_c, atol=20)
        _assert_not_color_at(same_frame, xa, ya, lower_c, atol=20)
        _assert_not_color_at(same_frame, xb, yb, upper_c, atol=20)
        _assert_not_color_at(same_frame, xb, yb, lower_c, atol=20)

        attached = ws.call(upper.with_mask, _video_mask(ws, pattern))
        print(
            f"mismatch_attach failed={attached.exception is not None}",
            flush=True,
        )
        mis_frame = None
        if attached.exception is None:
            composed = ws.call(CompositeVideoClip, [lower, attached.value])
            print(
                f"mismatch_overlay failed={composed.exception is not None}",
                flush=True,
            )
            if composed.exception is None:
                fetched = ws.call(composed.value.get_frame, 0.0)
                if fetched.exception is None:
                    mis_frame = fetched.value
                    require_rgb_picture(mis_frame, height, width)
                    print(
                        f"mismatch 1-sample={_rgb_at(mis_frame, x1, y1)} "
                        f"0-sample={_rgb_at(mis_frame, x0, y0)} "
                        f"mid_a={_rgb_at(mis_frame, xa, ya)} "
                        f"mid_b={_rgb_at(mis_frame, xb, yb)}",
                        flush=True,
                    )
        # Same-size 1/0/blend map at clip-sized sample points: 1→upper,
        # 0→lower, both mids neither pure layer. A mismatched pair must
        # not present that map. Does not pin a raise, crop/pad, or wording.
        applied_same_size_map = False
        if mis_frame is not None:
            one_is_upper = _colors_close(_rgb_at(mis_frame, x1, y1), upper_c, atol=0)
            zero_is_lower = _colors_close(_rgb_at(mis_frame, x0, y0), lower_c, atol=0)
            mida_blends = not _colors_close(
                _rgb_at(mis_frame, xa, ya), upper_c, atol=20
            ) and not _colors_close(_rgb_at(mis_frame, xa, ya), lower_c, atol=20)
            midb_blends = not _colors_close(
                _rgb_at(mis_frame, xb, yb), upper_c, atol=20
            ) and not _colors_close(_rgb_at(mis_frame, xb, yb), lower_c, atol=20)
            applied_same_size_map = (
                one_is_upper and zero_is_lower and mida_blends and midb_blends
            )
        print(
            f"applied_same_size_1_0_blend_map={applied_same_size_map}",
            flush=True,
        )
        assert not applied_same_size_map
