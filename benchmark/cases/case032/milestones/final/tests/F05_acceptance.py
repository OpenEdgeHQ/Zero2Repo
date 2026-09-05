# feature: F05
"""Resize, crop, rotate, and place (FP-05).

Assertions stay at the PRD's precision: result frames have the requested
size; crop keeps a pixel rectangle and drops the rest; rotation is
anticlockwise, degrees by default, radians when requested, with expand
growing the canvas so a non-orthogonal turn is not clipped; 180° with
expand swaps corners on an asymmetric clip; composition position encodings
and layer index; inverted crop is not a positive-size crop; an undocumented
position keyword is not a documented placement. Exception types, failure
wording, unit tokens in output, interpolation kernels, and exact expanded
canvas sizes are not pinned.
"""

from __future__ import annotations

import math
import secrets

import numpy as np
from clipkit import ColorClip, CompositeVideoClip, VideoClip

from _harness import CallResult, HarnessError, workspace
from _helpers import (
    as_numeric_array,
    dominant_picture_rgb,
    pictures_equal,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
)

_DURATION = 2.0
_COMPOSE_DURATION = 5.0
_FORBIDDEN_SCALE = {0.25, 0.5, 1.0, 2.0}
_DOC_KEYWORDS = ("center", "left", "right", "top", "bottom")
_COMPASS = ("north", "south", "east", "west")


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(20, 230), _rand_int(20, 230), _rand_int(20, 230))


def _rgb_away_from(*others: tuple[int, int, int]) -> tuple[int, int, int]:
    for _ in range(40):
        candidate = _rgb()
        if all(sum(abs(a - b) for a, b in zip(candidate, other)) > 90 for other in others):
            return candidate
    acc = (255, 255, 255)
    for other in others:
        acc = tuple(max(0, min(255, a - b)) for a, b in zip(acc, other))
    return tuple(int(v) for v in acc)


def _scalar_t(t) -> float:
    return float(np.asarray(t).reshape(-1)[0])


def _require_size(clip) -> tuple[int, int]:
    size = getattr(clip, "size", None)
    if size is None:
        raise AssertionError("clip size is absent; missing size is not (0, 0)")
    try:
        width, height = int(size[0]), int(size[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise AssertionError(f"clip size is not a width-height pair: {size!r}") from exc
    return width, height


def _frame_size(frame) -> tuple[int, int]:
    arr = as_numeric_array(frame)
    if arr.ndim < 2:
        raise AssertionError(f"frame has no spatial axes; shape={arr.shape!r}")
    return int(arr.shape[1]), int(arr.shape[0])


def _frame(ws, clip, t=0.0):
    return require_ok(ws.call(clip.get_frame, t))


def _mask_of(clip):
    mask = clip.mask
    if mask is None:
        raise AssertionError("clip has no mask")
    return mask


def _color(ws, size, color, duration=None):
    clip = require_ok(ws.call(ColorClip, size, color=color))
    if duration is not None:
        clip = require_ok(ws.call(clip.with_duration, duration))
    return clip


def _video(ws, fn, duration=None, *, is_mask=False):
    if duration is None:
        return require_ok(ws.call(VideoClip, frame_function=fn, is_mask=is_mask))
    return require_ok(
        ws.call(VideoClip, frame_function=fn, duration=duration, is_mask=is_mask)
    )


def _still(ws, picture, duration=None):
    arr = np.ascontiguousarray(picture)

    def frame_function(t):
        return arr.copy()

    return _video(ws, frame_function, duration)


def _overlay(ws, lower, upper):
    return require_ok(ws.call(CompositeVideoClip, [lower, upper]))


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


def _near_color_mask(frame, color, atol: float) -> np.ndarray:
    rgb = _picture_rgb(frame).astype(float)
    target = np.asarray(color, dtype=float).reshape(1, 1, 3)
    return np.linalg.norm(rgb - target, axis=2) <= atol


def _color_xy(frame, color, *, atol: float = 40.0, min_count: int = 8):
    mask = _near_color_mask(frame, color, atol)
    rows, cols = np.nonzero(mask)
    if cols.size < min_count:
        raise AssertionError(
            f"color {color} is absent or too small as a block; count={cols.size}"
        )
    return float(cols.mean()), float(rows.mean()), int(cols.size)


def _solid(height: int, width: int, color) -> np.ndarray:
    picture = np.zeros((height, width, 3), dtype=np.uint8)
    picture[:, :] = np.asarray(color, dtype=np.uint8)
    return picture


def _four_distinct_colors():
    c0 = _rgb()
    c1 = _rgb_away_from(c0)
    c2 = _rgb_away_from(c0, c1)
    c3 = _rgb_away_from(c0, c1, c2)
    return c0, c1, c2, c3


def _corner_picture(height: int, width: int, colors, *, block: int, fill):
    picture = _solid(height, width, fill)
    tl, tr, bl, br = colors
    picture[:block, :block] = tl
    picture[:block, width - block :] = tr
    picture[height - block :, :block] = bl
    picture[height - block :, width - block :] = br
    return picture


def _corner_mask(height: int, width: int, values, *, block: int, fill: float):
    mask = np.full((height, width), float(fill), dtype=float)
    tl, tr, bl, br = values
    mask[:block, :block] = tl
    mask[:block, width - block :] = tr
    mask[height - block :, :block] = bl
    mask[height - block :, width - block :] = br
    return mask


def _right_heavy_mask(height: int, width: int):
    mask = np.full((height, width), 0.18, dtype=float)
    mask[:, width // 2 :] = 0.62
    mask[height // 2 :, width // 2 :] = 0.94
    return mask


def _aspect_width_dims():
    for _ in range(80):
        src_w = _rand_int(6, 18) * 2
        src_h = _rand_int(5, 14) * 2
        if src_w == src_h or (src_w, src_h) == (1024, 800):
            continue
        new_w = _rand_int(4, 16) * 2
        if new_w in {src_w, 480} or new_w * 2 == src_w:
            continue
        if (src_h * new_w) % src_w != 0:
            continue
        new_h = src_h * new_w // src_w
        if new_h <= 0 or new_h == new_w:
            continue
        return src_w, src_h, new_w, new_h
    raise AssertionError("could not sample integer-aspect width-resize dimensions")


def _aspect_height_dims():
    for _ in range(80):
        src_w = _rand_int(6, 18) * 2
        src_h = _rand_int(5, 14) * 2
        if src_w == src_h:
            continue
        new_h = _rand_int(4, 16) * 2
        if new_h == src_h or new_h * 2 == src_h:
            continue
        if (src_w * new_h) % src_h != 0:
            continue
        new_w = src_w * new_h // src_h
        if new_w <= 0 or new_w == new_h:
            continue
        return src_w, src_h, new_w, new_h
    raise AssertionError("could not sample integer-aspect height-resize dimensions")


def _scale_factor_dims():
    pairs = ((2, 5), (3, 5), (3, 4), (4, 5), (5, 4), (3, 2))
    num, den = pairs[secrets.randbelow(len(pairs))]
    factor = num / den
    if factor in _FORBIDDEN_SCALE:
        raise AssertionError(f"sampled a forbidden scale factor {factor}")
    k = _rand_int(2, 5)
    m = k + _rand_int(1, 3)
    src_w = den * k * 2
    src_h = den * m * 2
    new_w = num * k * 2
    new_h = num * m * 2
    return factor, src_w, src_h, new_w, new_h


def _invalid_keyword() -> str:
    alphabet = "abcdefghijkmnpqrstuvxyz"
    for _ in range(40):
        n = _rand_int(5, 9)
        word = "".join(alphabet[secrets.randbelow(len(alphabet))] for _ in range(n))
        if word not in _DOC_KEYWORDS and word not in _COMPASS:
            return word
    raise AssertionError("could not sample an undocumented position keyword")


def _assert_frame_size(frame, width: int, height: int):
    got_w, got_h = _frame_size(frame)
    if (got_w, got_h) != (width, height):
        raise AssertionError(
            f"frame size is {(got_w, got_h)}, expected {(width, height)}"
        )


def _assert_layer_top_left(frame, x: int, y: int, layer_color, lower_color, *, atol=0):
    _assert_color_at(frame, x, y, layer_color, atol=atol)
    width, height = _frame_size(frame)
    if x > 0:
        _assert_color_at(frame, x - 1, y, lower_color, atol=atol)
    if y > 0:
        _assert_color_at(frame, x, y - 1, lower_color, atol=atol)
    if x + 1 < width and y == 0:
        pass
    print(
        f"layer_top_left at=({x},{y}) canvas={width}x{height} "
        f"pixel={_rgb_at(frame, x, y)}",
        flush=True,
    )


def _keyword_top_left(keyword, canvas_w, canvas_h, layer_w, layer_h) -> tuple[int, int]:
    cx = (canvas_w - layer_w) // 2
    cy = (canvas_h - layer_h) // 2
    right = canvas_w - layer_w
    bottom = canvas_h - layer_h
    table = {
        "center": (cx, cy),
        "left": (0, cy),
        "right": (right, cy),
        "top": (cx, 0),
        "bottom": (cx, bottom),
    }
    if keyword not in table:
        raise AssertionError(f"undocumented single keyword in test setup: {keyword!r}")
    return table[keyword]


def _pair_top_left(pair, canvas_w, canvas_h, layer_w, layer_h) -> tuple[int, int]:
    hx, vy = pair
    x = {"left": 0, "center": (canvas_w - layer_w) // 2, "right": canvas_w - layer_w}[hx]
    y = {"top": 0, "center": (canvas_h - layer_h) // 2, "bottom": canvas_h - layer_h}[vy]
    return x, y


def _even_canvas_layer():
    layer_w = _rand_int(4, 7) * 2
    layer_h = _rand_int(3, 6) * 2
    if layer_w == layer_h:
        layer_h = layer_w + 2
    canvas_w = layer_w + _rand_int(6, 12) * 2
    canvas_h = layer_h + _rand_int(5, 10) * 2
    if (canvas_w - layer_w) % 2 or (canvas_h - layer_h) % 2:
        raise AssertionError("centering would not be an integer pixel")
    return canvas_w, canvas_h, layer_w, layer_h


def _marked_layer_picture(height, width, corner, body):
    picture = _solid(height, width, body)
    picture[0, 0] = corner
    return picture


# ---------------------------------------------------------------------------
# A. resize
# ---------------------------------------------------------------------------


def test_oracle_resize_1024x800_width_480_is_480x375():
    with workspace() as ws:
        color = (40, 180, 90)
        source = _color(ws, (1024, 800), color, duration=_DURATION)
        resized = require_ok(ws.call(source.resized, width=480))
        frame = _frame(ws, resized, 0.0)
        print(
            f"oracle_resize src=1024x800 width=480 frame={_frame_size(frame)}",
            flush=True,
        )
        _assert_frame_size(frame, 480, 375)
        require_rgb_picture(frame, 375, 480, color=color)
        assert _frame_size(_frame(ws, source, 0.0)) == (1024, 800)


def test_resize_width_keeps_aspect_runtime():
    with workspace() as ws:
        src_w, src_h, new_w, new_h = _aspect_width_dims()
        color = _rgb()
        source = _color(ws, (src_w, src_h), color, duration=_DURATION)
        resized = require_ok(ws.call(source.resized, width=new_w))
        frame = _frame(ws, resized, 0.0)
        print(
            f"resize_width {src_w}x{src_h} -> width={new_w} expect={new_w}x{new_h} "
            f"got={_frame_size(frame)}",
            flush=True,
        )
        _assert_frame_size(frame, new_w, new_h)
        require_rgb_picture(frame, new_h, new_w, color=color)
        src_frame = _frame(ws, source, 0.0)
        _assert_frame_size(src_frame, src_w, src_h)
        require_rgb_picture(src_frame, src_h, src_w, color=color)


def test_resize_height_keeps_aspect_runtime():
    with workspace() as ws:
        src_w, src_h, new_w, new_h = _aspect_height_dims()
        color = _rgb()
        source = _color(ws, (src_w, src_h), color, duration=_DURATION)
        by_height = require_ok(ws.call(source.resized, height=new_h))
        height_frame = _frame(ws, by_height, 0.0)
        by_width = require_ok(ws.call(source.resized, width=src_w // 2 * 2))
        width_frame = _frame(ws, by_width, 0.0)
        print(
            f"resize_height {src_w}x{src_h} -> height={new_h} expect={new_w}x{new_h} "
            f"got={_frame_size(height_frame)} width_arm={_frame_size(width_frame)}",
            flush=True,
        )
        _assert_frame_size(height_frame, new_w, new_h)
        require_rgb_picture(height_frame, new_h, new_w, color=color)
        assert _frame_size(height_frame) != _frame_size(width_frame)


def test_resize_pair_sets_both_dimensions():
    with workspace() as ws:
        src_w, src_h, aspect_w, aspect_h = _aspect_width_dims()
        new_w = aspect_w + 4 if aspect_w + 4 != src_w else aspect_w + 6
        new_h = src_h if src_h != new_w else src_h + 2
        if new_w * src_h == src_w * new_h:
            new_h = src_h + 4
        color = _rgb()
        source = _color(ws, (src_w, src_h), color, duration=_DURATION)
        paired = require_ok(ws.call(source.resized, (new_w, new_h)))
        pair_frame = _frame(ws, paired, 0.0)
        width_only = require_ok(ws.call(source.resized, width=aspect_w))
        width_frame = _frame(ws, width_only, 0.0)
        print(
            f"resize_pair {src_w}x{src_h} -> {(new_w, new_h)} "
            f"got={_frame_size(pair_frame)} width_arm={_frame_size(width_frame)}",
            flush=True,
        )
        _assert_frame_size(pair_frame, new_w, new_h)
        require_rgb_picture(pair_frame, new_h, new_w, color=color)
        _assert_frame_size(width_frame, aspect_w, aspect_h)
        assert _frame_size(pair_frame)[1] != _frame_size(width_frame)[1]


def test_resize_scale_factor_scales_both_axes():
    with workspace() as ws:
        factor, src_w, src_h, new_w, new_h = _scale_factor_dims()
        color = _rgb()
        source = _color(ws, (src_w, src_h), color, duration=_DURATION)
        scaled = require_ok(ws.call(source.resized, factor))
        frame = _frame(ws, scaled, 0.0)
        print(
            f"resize_factor {factor} {src_w}x{src_h} -> expect={new_w}x{new_h} "
            f"got={_frame_size(frame)}",
            flush=True,
        )
        assert factor not in _FORBIDDEN_SCALE
        _assert_frame_size(frame, new_w, new_h)
        require_rgb_picture(frame, new_h, new_w, color=color)
        assert new_w != src_w and new_h != src_h


def test_resize_leaves_original_unchanged():
    with workspace() as ws:
        src_w, src_h, new_w, new_h = _aspect_width_dims()
        color = _rgb()
        source = _color(ws, (src_w, src_h), color, duration=_DURATION)
        before = _frame(ws, source, 0.0)
        resized = require_ok(ws.call(source.resized, width=new_w))
        after = _frame(ws, source, 0.0)
        new_frame = _frame(ws, resized, 0.0)
        print(
            f"resize_copy src={_frame_size(after)} new={_frame_size(new_frame)}",
            flush=True,
        )
        assert resized is not source
        _assert_frame_size(after, src_w, src_h)
        assert pictures_equal(before, after)
        _assert_frame_size(new_frame, new_w, new_h)


def test_resize_follows_mask_by_default():
    with workspace() as ws:
        factor, src_w, src_h, new_w, new_h = _scale_factor_dims()
        color = _rgb()
        picture = _solid(src_h, src_w, color)
        mask_arr = _right_heavy_mask(src_h, src_w)
        source = _still(ws, picture, _DURATION)
        mask = _video(
            ws,
            lambda t, arr=mask_arr: arr.copy(),
            _DURATION,
            is_mask=True,
        )
        source = require_ok(ws.call(source.with_mask, mask))
        baseline = require_mask_picture(
            _frame(ws, _mask_of(source), 0.0), src_h, src_w
        )
        resized = require_ok(ws.call(source.resized, factor))
        new_pic = _frame(ws, resized, 0.0)
        new_mask = require_mask_picture(
            _frame(ws, _mask_of(resized), 0.0), new_h, new_w
        )
        tl = float(new_mask[new_h // 4, new_w // 4])
        br = float(new_mask[(3 * new_h) // 4, (3 * new_w) // 4])
        src_tl = float(baseline[src_h // 4, src_w // 4])
        src_br = float(baseline[(3 * src_h) // 4, (3 * src_w) // 4])
        print(
            f"resize_mask_follow factor={factor} new={new_w}x{new_h} "
            f"src_tl={src_tl:.3f} src_br={src_br:.3f} tl={tl:.3f} br={br:.3f}",
            flush=True,
        )
        _assert_frame_size(new_pic, new_w, new_h)
        assert src_br > src_tl + 0.4
        assert br > tl + 0.3
        assert br > 0.7
        assert tl < 0.45
        _assert_frame_size(baseline, src_w, src_h)


def test_resize_can_leave_mask_unchanged():
    with workspace() as ws:
        factor, src_w, src_h, new_w, new_h = _scale_factor_dims()
        color = _rgb()
        picture = _solid(src_h, src_w, color)
        mask_arr = _right_heavy_mask(src_h, src_w)
        source = require_ok(
            ws.call(
                _still(ws, picture, _DURATION).with_mask,
                _video(
                    ws,
                    lambda t, arr=mask_arr: arr.copy(),
                    _DURATION,
                    is_mask=True,
                ),
            )
        )
        followed = require_ok(ws.call(source.resized, factor))
        frozen = require_ok(ws.call(source.resized, factor, apply_to_mask=False))
        followed_mask = require_mask_picture(
            _frame(ws, _mask_of(followed), 0.0), new_h, new_w
        )
        frozen_mask = require_mask_picture(
            _frame(ws, _mask_of(frozen), 0.0), src_h, src_w
        )
        source_mask = require_mask_picture(
            _frame(ws, _mask_of(source), 0.0), src_h, src_w
        )
        print(
            f"resize_mask_unchanged followed={followed_mask.shape} "
            f"frozen={frozen_mask.shape}",
            flush=True,
        )
        _assert_frame_size(_frame(ws, followed, 0.0), new_w, new_h)
        _assert_frame_size(_frame(ws, frozen, 0.0), new_w, new_h)
        assert followed_mask.shape != frozen_mask.shape
        assert pictures_equal(frozen_mask, source_mask)
        assert not pictures_equal(followed_mask, source_mask)


# ---------------------------------------------------------------------------
# B. crop
# ---------------------------------------------------------------------------


def test_oracle_crop_10x10_left_half_is_5x10():
    with workspace() as ws:
        color = (210, 40, 40)
        source = _color(ws, (10, 10), color, duration=_DURATION)
        cropped = require_ok(ws.call(source.cropped, x1=0, y1=0, x2=5, y2=10))
        frame = _frame(ws, cropped, 0.0)
        print(f"oracle_crop left_half got={_frame_size(frame)}", flush=True)
        _assert_frame_size(frame, 5, 10)
        require_rgb_picture(frame, 10, 5, color=color)


def test_crop_opposite_corners_keeps_rectangle():
    with workspace() as ws:
        src_w = _rand_int(8, 14) * 2
        src_h = _rand_int(7, 12) * 2
        if src_w == src_h:
            src_h = src_w + 2
        x1 = _rand_int(2, 4)
        y1 = _rand_int(2, 4)
        x2 = src_w - _rand_int(2, 5)
        y2 = src_h - _rand_int(3, 6)
        if x2 <= x1 + 2:
            x2 = x1 + 4
        if y2 <= y1 + 2:
            y2 = y1 + 4
        # Not a left-half crop and not the full frame.
        assert (x1, y1, x2, y2) != (0, 0, src_w // 2, src_h)
        assert (x1, y1, x2, y2) != (0, 0, src_w, src_h)
        inside = _rgb()
        outside = _rgb_away_from(inside)
        picture = _solid(src_h, src_w, outside)
        picture[y1:y2, x1:x2] = inside
        source = _still(ws, picture, _DURATION)
        cropped = require_ok(ws.call(source.cropped, x1=x1, y1=y1, x2=x2, y2=y2))
        frame = _frame(ws, cropped, 0.0)
        expected = picture[y1:y2, x1:x2]
        print(
            f"crop_corners rect=({x1},{y1})-({x2},{y2}) src={src_w}x{src_h} "
            f"got={_frame_size(frame)}",
            flush=True,
        )
        _assert_frame_size(frame, x2 - x1, y2 - y1)
        assert pictures_equal(frame, expected)
        assert not _near_color_mask(frame, outside, 8.0).any()


def test_crop_top_left_plus_size():
    with workspace() as ws:
        src_w = _rand_int(8, 14) * 2
        src_h = _rand_int(7, 12) * 2
        if src_w == src_h:
            src_h = src_w + 2
        x1 = _rand_int(2, 4)
        y1 = _rand_int(2, 4)
        width = _rand_int(4, 7) * 2
        height = _rand_int(3, 6) * 2
        if x1 + width >= src_w:
            width = src_w - x1 - 1
        if y1 + height >= src_h:
            height = src_h - y1 - 1
        x2, y2 = x1 + width, y1 + height
        inside = _rgb()
        outside = _rgb_away_from(inside)
        picture = _solid(src_h, src_w, outside)
        picture[y1:y2, x1:x2] = inside
        source = _still(ws, picture, _DURATION)
        by_corners = require_ok(
            ws.call(source.cropped, x1=x1, y1=y1, x2=x2, y2=y2)
        )
        by_size = require_ok(
            ws.call(source.cropped, x1=x1, y1=y1, width=width, height=height)
        )
        corners_frame = _frame(ws, by_corners, 0.0)
        size_frame = _frame(ws, by_size, 0.0)
        print(
            f"crop_top_left+size ({x1},{y1}) {width}x{height} "
            f"corners={_frame_size(corners_frame)} size={_frame_size(size_frame)}",
            flush=True,
        )
        _assert_frame_size(size_frame, width, height)
        assert pictures_equal(size_frame, corners_frame)
        assert pictures_equal(size_frame, picture[y1:y2, x1:x2])


def test_crop_center_plus_size():
    with workspace() as ws:
        cw = _rand_int(3, 5) * 2
        ch = _rand_int(3, 5) * 2
        if cw == ch:
            ch = cw + 2
        cx = cw + _rand_int(4, 8) * 2
        cy = ch + _rand_int(3, 7) * 2
        if cx == 0 or cy == 0:
            raise AssertionError("center must not be 0")
        true_x1 = cx - cw // 2
        true_y1 = cy - ch // 2
        true_x2 = true_x1 + cw
        true_y2 = true_y1 + ch
        fake_x1, fake_y1 = cx, cy
        fake_x2, fake_y2 = cx + cw, cy + ch
        src_w = fake_x2 + 2
        src_h = fake_y2 + 2
        bg = _rgb()
        true_tl = _rgb_away_from(bg)
        fake_only = _rgb_away_from(bg, true_tl)
        picture = _solid(src_h, src_w, bg)
        picture[true_y1, true_x1] = true_tl
        # A pixel inside the fake (center-as-origin) window and outside
        # the true centred rectangle.
        fake_px = fake_x2 - 1
        fake_py = fake_y1
        assert not (true_x1 <= fake_px < true_x2 and true_y1 <= fake_py < true_y2)
        assert fake_x1 <= fake_px < fake_x2 and fake_y1 <= fake_py < fake_y2
        picture[fake_py, fake_px] = fake_only
        source = _still(ws, picture, _DURATION)
        cropped = require_ok(
            ws.call(
                source.cropped,
                x_center=cx,
                y_center=cy,
                width=cw,
                height=ch,
            )
        )
        frame = _frame(ws, cropped, 0.0)
        expected = picture[true_y1:true_y2, true_x1:true_x2]
        print(
            f"crop_center c=({cx},{cy}) size={cw}x{ch} true_tl=({true_x1},{true_y1}) "
            f"fake_only=({fake_px},{fake_py}) got={_frame_size(frame)}",
            flush=True,
        )
        _assert_frame_size(frame, cw, ch)
        assert pictures_equal(frame, expected)
        _assert_color_at(frame, 0, 0, true_tl)
        assert not _near_color_mask(frame, fake_only, 8.0).any()
        # Left-half crop would be a different rectangle.
        assert (true_x1, true_y1, true_x2, true_y2) != (0, 0, src_w // 2, src_h)


def test_crop_leaves_original_unchanged():
    with workspace() as ws:
        src_w, src_h = 16, 12
        x1, y1, x2, y2 = 3, 2, 11, 9
        inside = _rgb()
        outside = _rgb_away_from(inside)
        picture = _solid(src_h, src_w, outside)
        picture[y1:y2, x1:x2] = inside
        source = _still(ws, picture, _DURATION)
        before = _frame(ws, source, 0.0)
        cropped = require_ok(ws.call(source.cropped, x1=x1, y1=y1, x2=x2, y2=y2))
        after = _frame(ws, source, 0.0)
        print(
            f"crop_copy src={_frame_size(after)} new={_frame_size(_frame(ws, cropped, 0.0))}",
            flush=True,
        )
        assert cropped is not source
        assert pictures_equal(before, after)
        _assert_frame_size(after, src_w, src_h)
        _assert_frame_size(_frame(ws, cropped, 0.0), x2 - x1, y2 - y1)


def test_crop_follows_mask():
    with workspace() as ws:
        src_w, src_h = 18, 14
        x1, y1, x2, y2 = 4, 3, 13, 11
        color = _rgb()
        picture = _solid(src_h, src_w, color)
        mask_arr = np.full((src_h, src_w), 0.2, dtype=float)
        mask_arr[y1:y2, x1:x2] = 0.85
        mask_arr[:, :2] = 0.05
        source = require_ok(
            ws.call(
                _still(ws, picture, _DURATION).with_mask,
                _video(
                    ws,
                    lambda t, arr=mask_arr: arr.copy(),
                    _DURATION,
                    is_mask=True,
                ),
            )
        )
        cropped = require_ok(ws.call(source.cropped, x1=x1, y1=y1, x2=x2, y2=y2))
        kept = require_mask_picture(
            _frame(ws, _mask_of(cropped), 0.0), y2 - y1, x2 - x1
        )
        expected = mask_arr[y1:y2, x1:x2]
        print(
            f"crop_mask rect=({x1},{y1})-({x2},{y2}) kept={kept.shape}",
            flush=True,
        )
        assert pictures_equal(kept, expected)
        assert not np.any(np.isclose(kept, 0.05, atol=1e-6))


# ---------------------------------------------------------------------------
# C. rotate
# ---------------------------------------------------------------------------


def _asymmetric_corners(ws, *, width, height, block, duration=_DURATION):
    fill = _rgb()
    colors = _four_distinct_colors()
    while any(_colors_close(c, fill, atol=40) for c in colors):
        fill = _rgb_away_from(*colors)
    picture = _corner_picture(height, width, colors, block=block, fill=fill)
    clip = _still(ws, picture, duration)
    return clip, picture, colors, fill


def test_oracle_rotate_180_with_expand_puts_top_left_at_bottom_right():
    with workspace() as ws:
        width, height, block = 16, 10, 4
        clip, picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl, _tr, _bl, br = colors
        rotated = require_ok(ws.call(clip.rotated, 180, expand=True))
        frame = _frame(ws, rotated, 0.0)
        rw, rh = _frame_size(frame)
        print(
            f"oracle_rotate_180 size={rw}x{rh} br={_rgb_at(frame, rw - 1, rh - 1)} "
            f"src_tl={tl}",
            flush=True,
        )
        _assert_color_at(frame, rw - 1, rh - 1, tl)
        assert not _colors_close(_rgb_at(frame, rw - 1, rh - 1), br, atol=0)
        assert not pictures_equal(frame, picture)


def test_rotate_180_with_expand_swaps_corners_runtime():
    with workspace() as ws:
        width = _rand_int(8, 12) * 2
        height = _rand_int(6, 10) * 2
        if width == height:
            height = width + 2
        block = 4
        clip, picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl, _tr, _bl, br = colors
        rotated = require_ok(ws.call(clip.rotated, 180, expand=True))
        frame = _frame(ws, rotated, 0.0)
        rw, rh = _frame_size(frame)
        src_after = _frame(ws, clip, 0.0)
        print(
            f"rotate_180_runtime src={width}x{height} out={rw}x{rh}",
            flush=True,
        )
        _assert_color_at(frame, rw - 1, rh - 1, tl)
        _assert_color_at(frame, 0, 0, br)
        assert pictures_equal(src_after, picture)
        assert clip is not rotated


def test_rotate_90_with_expand_is_anticlockwise():
    with workspace() as ws:
        width = _rand_int(8, 12) * 2
        height = _rand_int(6, 10) * 2
        if width == height:
            height = width + 2
        block = 4
        clip, _picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl, _tr, _bl, br = colors
        rotated = require_ok(ws.call(clip.rotated, 90, expand=True))
        frame = _frame(ws, rotated, 0.0)
        rw, rh = _frame_size(frame)
        print(
            f"rotate_90 src={width}x{height} out={rw}x{rh} "
            f"bl={_rgb_at(frame, 0, rh - 1)} tr={_rgb_at(frame, rw - 1, 0)}",
            flush=True,
        )
        _assert_color_at(frame, 0, rh - 1, tl)
        assert not _colors_close(_rgb_at(frame, rw - 1, 0), tl, atol=0)
        assert not _colors_close(_rgb_at(frame, rw - 1, rh - 1), tl, atol=0)
        assert not _colors_close(_rgb_at(frame, 0, rh - 1), br, atol=0)


def test_rotate_radians_when_requested_matches_half_turn():
    with workspace() as ws:
        width, height, block = 18, 12, 4
        clip, _picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl, _tr, _bl, br = colors
        deg = require_ok(ws.call(clip.rotated, 180, expand=True))
        rad = require_ok(ws.call(clip.rotated, math.pi, expand=True, unit="rad"))
        deg_frame = _frame(ws, deg, 0.0)
        rad_frame = _frame(ws, rad, 0.0)
        dw, dh = _frame_size(deg_frame)
        rw, rh = _frame_size(rad_frame)
        print(
            f"rotate_rad_half deg={dw}x{dh} rad={rw}x{rh}",
            flush=True,
        )
        _assert_color_at(deg_frame, dw - 1, dh - 1, tl)
        _assert_color_at(deg_frame, 0, 0, br)
        _assert_color_at(rad_frame, rw - 1, rh - 1, tl)
        _assert_color_at(rad_frame, 0, 0, br)


def test_rotate_radians_quarter_turn_matches_90():
    with workspace() as ws:
        width, height, block = 18, 12, 4
        clip, _picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl = colors[0]
        deg = require_ok(ws.call(clip.rotated, 90, expand=True))
        rad = require_ok(ws.call(clip.rotated, math.pi / 2, expand=True, unit="rad"))
        deg_frame = _frame(ws, deg, 0.0)
        rad_frame = _frame(ws, rad, 0.0)
        dw, dh = _frame_size(deg_frame)
        rw, rh = _frame_size(rad_frame)
        print(
            f"rotate_rad_quarter deg={dw}x{dh} rad={rw}x{rh}",
            flush=True,
        )
        _assert_color_at(deg_frame, 0, dh - 1, tl)
        _assert_color_at(rad_frame, 0, rh - 1, tl)


def test_rotate_expand_grows_canvas_non_orthogonal_contrast():
    with workspace() as ws:
        width = _rand_int(10, 14) * 2
        height = _rand_int(8, 12) * 2
        if width == height:
            height = width + 4
        block = max(8, min(width, height) // 4)
        clip, _picture, colors, fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        tl, tr, bl, br = colors
        theta = float(_rand_int(20, 26) if secrets.randbelow(2) == 0 else _rand_int(66, 74))
        assert theta not in {0.0, 45.0, 90.0, 180.0}
        clipped = require_ok(ws.call(clip.rotated, theta, expand=False))
        expanded = require_ok(ws.call(clip.rotated, theta, expand=True))
        clipped_frame = _frame(ws, clipped, 0.0)
        expanded_frame = _frame(ws, expanded, 0.0)
        source_frame = _frame(ws, clip, 0.0)
        cw, ch = _frame_size(clipped_frame)
        ew, eh = _frame_size(expanded_frame)
        print(
            f"rotate_expand theta={theta} src={width}x{height} "
            f"clipped={cw}x{ch} expanded={ew}x{eh} block={block}",
            flush=True,
        )
        _assert_frame_size(clipped_frame, width, height)
        assert ew > width or eh > height
        src_rgb = _picture_rgb(source_frame)
        clip_rgb = _picture_rgb(clipped_frame)
        patch = 4
        src_patches = (
            src_rgb[:patch, :patch],
            src_rgb[:patch, width - patch :],
            src_rgb[height - patch :, :patch],
            src_rgb[height - patch :, width - patch :],
        )
        clip_patches = (
            clip_rgb[:patch, :patch],
            clip_rgb[:patch, cw - patch :],
            clip_rgb[ch - patch :, :patch],
            clip_rgb[ch - patch :, cw - patch :],
        )
        for src_p, clip_p, name in zip(
            src_patches, clip_patches, ("tl", "tr", "bl", "br")
        ):
            print(
                f"clipped_{name}_src={tuple(int(v) for v in src_p[0, 0])} "
                f"out={tuple(int(v) for v in clip_p[0, 0])}",
                flush=True,
            )
            assert not pictures_equal(src_p, clip_p)
        ex, ey, count = _color_xy(expanded_frame, tl, atol=55.0, min_count=8)
        print(
            f"expand_tl_centroid=({ex:.2f},{ey:.2f}) n={count}",
            flush=True,
        )
        src_tl_x, src_tl_y = (block - 1) / 2.0, (block - 1) / 2.0
        assert abs(ex - src_tl_x) > 3 or abs(ey - src_tl_y) > 3
        assert abs(ex - (block - 1) / 2.0) > 3 or abs(ey - (eh - 1 - (block - 1) / 2.0)) > 3
        assert not pictures_equal(expanded_frame, clipped_frame)


def test_rotate_follows_mask():
    with workspace() as ws:
        width, height, block = 16, 12, 4
        fill = _rgb()
        colors = _four_distinct_colors()
        picture = _corner_picture(height, width, colors, block=block, fill=fill)
        values = (0.2, 0.4, 0.65, 0.9)
        mask_arr = _corner_mask(height, width, values, block=block, fill=0.5)
        source = require_ok(
            ws.call(
                _still(ws, picture, _DURATION).with_mask,
                _video(
                    ws,
                    lambda t, arr=mask_arr: arr.copy(),
                    _DURATION,
                    is_mask=True,
                ),
            )
        )
        half = require_ok(ws.call(source.rotated, 180, expand=True))
        quarter = require_ok(ws.call(source.rotated, 90, expand=True))
        half_pic = _frame(ws, half, 0.0)
        quarter_pic = _frame(ws, quarter, 0.0)
        hw, hh = _frame_size(half_pic)
        qw, qh = _frame_size(quarter_pic)
        half_mask = require_mask_picture(_frame(ws, _mask_of(half), 0.0), hh, hw)
        quarter_mask = require_mask_picture(_frame(ws, _mask_of(quarter), 0.0), qh, qw)
        print(
            f"rotate_mask 180_br={half_mask[hh - 1, hw - 1]:.3f} "
            f"90_bl={quarter_mask[qh - 1, 0]:.3f}",
            flush=True,
        )
        assert abs(float(half_mask[hh - 1, hw - 1]) - values[0]) < 1e-6
        assert abs(float(quarter_mask[qh - 1, 0]) - values[0]) < 1e-6


def test_rotate_leaves_original_unchanged():
    with workspace() as ws:
        width, height, block = 14, 10, 4
        clip, picture, colors, _fill = _asymmetric_corners(
            ws, width=width, height=height, block=block
        )
        rotated = require_ok(ws.call(clip.rotated, 180, expand=True))
        after = _frame(ws, clip, 0.0)
        print(
            f"rotate_copy src={_frame_size(after)} new={_frame_size(_frame(ws, rotated, 0.0))}",
            flush=True,
        )
        assert rotated is not clip
        assert pictures_equal(after, picture)
        _assert_color_at(after, 0, 0, colors[0])


# ---------------------------------------------------------------------------
# D. position and layer index
# ---------------------------------------------------------------------------


def test_default_position_is_top_left():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        upper = _color(ws, (layer_w, layer_h), layer_c, duration=_COMPOSE_DURATION)
        default = _overlay(ws, lower, upper)
        centered = _overlay(
            ws, lower, require_ok(ws.call(upper.with_position, "center"))
        )
        default_frame = _frame(ws, default, 0.0)
        center_frame = _frame(ws, centered, 0.0)
        cx, cy = _keyword_top_left("center", canvas_w, canvas_h, layer_w, layer_h)
        mid_x, mid_y = canvas_w // 2, canvas_h // 2
        print(
            f"default_pos canvas={canvas_w}x{canvas_h} layer={layer_w}x{layer_h} "
            f"center_tl=({cx},{cy})",
            flush=True,
        )
        _assert_layer_top_left(default_frame, 0, 0, layer_c, lower_c)
        _assert_color_at(default_frame, mid_x, mid_y, lower_c)
        _assert_color_at(center_frame, mid_x, mid_y, layer_c)
        _assert_color_at(center_frame, 0, 0, lower_c)
        assert not pictures_equal(default_frame, center_frame)


def test_position_center_centers_both_axes():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        upper = _color(ws, (layer_w, layer_h), layer_c, duration=_COMPOSE_DURATION)
        placed = require_ok(ws.call(upper.with_position, "center"))
        frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
        x, y = _keyword_top_left("center", canvas_w, canvas_h, layer_w, layer_h)
        print(f"position_center tl=({x},{y})", flush=True)
        _assert_layer_top_left(frame, x, y, layer_c, lower_c)
        _assert_color_at(frame, canvas_w // 2, canvas_h // 2, layer_c)


def test_position_center_top_is_horizontally_centered_flush_top():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        upper = _color(ws, (layer_w, layer_h), layer_c, duration=_COMPOSE_DURATION)
        placed = require_ok(ws.call(upper.with_position, ("center", "top")))
        frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
        x, y = _pair_top_left(("center", "top"), canvas_w, canvas_h, layer_w, layer_h)
        full_cx, full_cy = _keyword_top_left(
            "center", canvas_w, canvas_h, layer_w, layer_h
        )
        print(f"position_center_top tl=({x},{y}) full_center=({full_cx},{full_cy})", flush=True)
        _assert_layer_top_left(frame, x, y, layer_c, lower_c)
        assert y == 0
        assert x == full_cx
        assert (x, y) != (0, 0)
        assert (x, y) != (full_cx, full_cy)
        # Flush-top does not promise the geometric canvas centre is
        # uncovered: a tall layer still covers it. The pixel just
        # below the layer, on its horizontal midline, is the lower clip.
        below_x = x + layer_w // 2
        below_y = layer_h
        assert below_y < canvas_h
        _assert_color_at(frame, below_x, below_y, lower_c)


def test_oracle_position_bottom_right_visible_there_not_top_left():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)
        placed = require_ok(ws.call(upper.with_position, ("right", "bottom")))
        frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
        x, y = _pair_top_left(("right", "bottom"), canvas_w, canvas_h, layer_w, layer_h)
        print(
            f"oracle_bottom_right canvas={canvas_w}x{canvas_h} layer={layer_w}x{layer_h} "
            f"tl=({x},{y})",
            flush=True,
        )
        _assert_layer_top_left(frame, x, y, corner, lower_c)
        _assert_color_at(frame, canvas_w - 1, canvas_h - 1, layer_c)
        _assert_color_at(frame, 0, 0, lower_c)
        assert x == canvas_w - layer_w
        assert y == canvas_h - layer_h


def test_position_keyword_pair_flush_named_edges():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)
        pair = ("right", "top") if secrets.randbelow(2) == 0 else ("left", "bottom")
        placed = require_ok(ws.call(upper.with_position, pair))
        frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
        x, y = _pair_top_left(pair, canvas_w, canvas_h, layer_w, layer_h)
        print(f"position_pair {pair} tl=({x},{y})", flush=True)
        _assert_layer_top_left(frame, x, y, corner, lower_c)
        assert pair not in {("center", "top"), ("right", "bottom")}
        if pair[0] == "right":
            assert x == canvas_w - layer_w
        if pair[0] == "left":
            assert x == 0
        if pair[1] == "top":
            assert y == 0
        if pair[1] == "bottom":
            assert y == canvas_h - layer_h
        assert (x, y) != (0, 0)


def test_position_single_keywords_center_the_missing_axis():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)
        for keyword in ("left", "right", "top", "bottom"):
            placed = require_ok(ws.call(upper.with_position, keyword))
            frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
            x, y = _keyword_top_left(keyword, canvas_w, canvas_h, layer_w, layer_h)
            print(f"position_single {keyword} tl=({x},{y})", flush=True)
            _assert_layer_top_left(frame, x, y, corner, lower_c)
            if keyword == "left":
                assert x == 0
                assert y == (canvas_h - layer_h) // 2
            elif keyword == "right":
                assert x == canvas_w - layer_w
                assert y == (canvas_h - layer_h) // 2
            elif keyword == "top":
                assert y == 0
                assert x == (canvas_w - layer_w) // 2
            else:
                assert y == canvas_h - layer_h
                assert x == (canvas_w - layer_w) // 2


def test_position_pixel_pair():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        x = _rand_int(3, canvas_w - layer_w - 3)
        y = _rand_int(3, canvas_h - layer_h - 3)
        center = (
            (canvas_w - layer_w) // 2,
            (canvas_h - layer_h) // 2,
        )
        br = (canvas_w - layer_w, canvas_h - layer_h)
        if (x, y) in {(0, 0), center, br}:
            x = 4 if x != 4 else 6
            y = 5 if y != 5 else 7
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)
        placed = require_ok(ws.call(upper.with_position, (x, y)))
        frame = _frame(ws, _overlay(ws, lower, placed), 0.0)
        print(f"position_pixels ({x},{y})", flush=True)
        _assert_layer_top_left(frame, x, y, corner, lower_c)
        _assert_color_at(frame, 0, 0, lower_c)


def test_relative_fractions_place_top_left():
    with workspace() as ws:
        # Oracle fractions (0.4, 0.7) on a canvas that is not 100×100.
        canvas_w, canvas_h = 50, 40
        layer_w, layer_h = 10, 8
        ox, oy = int(0.4 * canvas_w), int(0.7 * canvas_h)
        assert (ox, oy) == (20, 28)
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)
        oracle = require_ok(
            ws.call(upper.with_position, (0.4, 0.7), relative=True)
        )
        oracle_frame = _frame(ws, _overlay(ws, lower, oracle), 0.0)
        as_pixels = require_ok(ws.call(upper.with_position, (0.4, 0.7)))
        pixel_frame = _frame(ws, _overlay(ws, lower, as_pixels), 0.0)
        pixel_at_frac = _rgb_at(pixel_frame, ox, oy)
        not_at_relative = not _colors_close(pixel_at_frac, corner, atol=0)
        print(
            f"relative_oracle tl=({ox},{oy}) "
            f"nonrelative_at_40_70={pixel_at_frac} "
            f"not_at_relative={not_at_relative}",
            flush=True,
        )
        _assert_layer_top_left(oracle_frame, ox, oy, corner, lower_c)
        if _colors_close(pixel_at_frac, corner, atol=0):
            raise AssertionError(
                "non-relative (0.4, 0.7) placed the marked corner at the "
                f"40%/70% composition pixel ({ox},{oy})"
            )

        fx = (0.2, 0.3, 0.6, 0.8)[secrets.randbelow(4)]
        fy = (0.2, 0.5, 0.6, 0.8)[secrets.randbelow(4)]
        if (fx, fy) == (0.4, 0.7):
            fy = 0.5
        rt_w, rt_h = 40, 20
        rx, ry = int(fx * rt_w), int(fy * rt_h)
        assert (fx * rt_w, fy * rt_h) == (rx, ry)
        rt_layer_w, rt_layer_h = 8, 6
        if rx + rt_layer_w >= rt_w:
            rt_layer_w = rt_w - rx - 1
        if ry + rt_layer_h >= rt_h:
            rt_layer_h = rt_h - ry - 1
        rt_lower = _color(ws, (rt_w, rt_h), lower_c, duration=_COMPOSE_DURATION)
        rt_pic = _marked_layer_picture(rt_layer_h, rt_layer_w, corner, layer_c)
        rt_upper = _still(ws, rt_pic, _COMPOSE_DURATION)
        rt_placed = require_ok(
            ws.call(rt_upper.with_position, (fx, fy), relative=True)
        )
        rt_frame = _frame(ws, _overlay(ws, rt_lower, rt_placed), 0.0)
        print(f"relative_runtime ({fx},{fy}) -> ({rx},{ry})", flush=True)
        _assert_layer_top_left(rt_frame, rx, ry, corner, lower_c)


def test_position_function_of_time_moves_the_clip():
    with workspace() as ws:
        canvas_w, canvas_h = 48, 36
        layer_w, layer_h = 8, 6
        sampled = None
        for _ in range(80):
            t1 = float(_rand_int(1, 2))
            t2 = t1 + float(_rand_int(2, 3))
            sx = float(_rand_int(3, 6))
            sy = float(_rand_int(2, 5))
            if sx == sy:
                sy = sx + 2
            ox = float(_rand_int(2, 5))
            oy = float(_rand_int(2, 5))
            x1, y1 = int(ox + sx * t1), int(oy + sy * t1)
            x2, y2 = int(ox + sx * t2), int(oy + sy * t2)
            if (x1, y1) == (x2, y2):
                continue
            if x1 == y1 and x2 == y2:
                continue
            if min(x1, x2) < 1 or min(y1, y2) < 1:
                continue
            if max(x1, x2) + layer_w >= canvas_w:
                continue
            if max(y1, y2) + layer_h >= canvas_h:
                continue
            sampled = (t1, t2, sx, sy, ox, oy, x1, y1, x2, y2)
            break
        if sampled is None:
            raise AssertionError(
                "could not sample on-canvas time-function positions"
            )
        t1, t2, sx, sy, ox, oy, x1, y1, x2, y2 = sampled

        def pos_at(t):
            moment = _scalar_t(t)
            return (ox + sx * moment, oy + sy * moment)

        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        duration = t2 + 1.0
        lower_a = _color(ws, (canvas_w, canvas_h), lower_c, duration=duration)
        lower_b = _color(ws, (canvas_w, canvas_h), lower_c, duration=duration)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper_a = _still(ws, picture, duration)
        upper_b = _still(ws, picture, duration)
        placed_a = require_ok(ws.call(upper_a.with_position, pos_at))
        placed_b = require_ok(ws.call(upper_b.with_position, pos_at))
        comp_a = _overlay(ws, lower_a, placed_a)
        comp_b = _overlay(ws, lower_b, placed_b)
        frame_a = _frame(ws, comp_a, t1)
        frame_b = _frame(ws, comp_b, t2)
        print(
            f"position_fn t1={t1} -> ({x1},{y1}) t2={t2} -> ({x2},{y2}) "
            f"sx={sx} sy={sy}",
            flush=True,
        )
        _assert_layer_top_left(frame_a, x1, y1, corner, lower_c)
        _assert_layer_top_left(frame_b, x2, y2, corner, lower_c)
        assert not pictures_equal(frame_a, frame_b)


def test_greater_layer_index_is_drawn_on_top():
    with workspace() as ws:
        width, height = 12, 10
        low_c = _rgb()
        high_c = _rgb_away_from(low_c)
        high_index = _rand_int(4, 9)
        low_index = _rand_int(0, high_index - 1)
        a = _color(ws, (width, height), low_c, duration=_COMPOSE_DURATION)
        b = _color(ws, (width, height), high_c, duration=_COMPOSE_DURATION)
        a_high = require_ok(ws.call(a.with_layer_index, high_index))
        b_low = require_ok(ws.call(b.with_layer_index, low_index))
        # List order fixed: greater index first, lesser last.
        first = _overlay(ws, a_high, b_low)
        first_frame = _frame(ws, first, 0.0)
        a_low = require_ok(ws.call(a.with_layer_index, low_index))
        b_high = require_ok(ws.call(b.with_layer_index, high_index))
        swapped = _overlay(ws, a_low, b_high)
        swapped_frame = _frame(ws, swapped, 0.0)
        print(
            f"layer_index high={high_index} low={low_index} "
            f"first={dominant_picture_rgb(first_frame)} "
            f"swapped={dominant_picture_rgb(swapped_frame)}",
            flush=True,
        )
        require_rgb_picture(first_frame, height, width, color=low_c)
        require_rgb_picture(swapped_frame, height, width, color=high_c)
        assert not pictures_equal(first_frame, swapped_frame)


def test_position_leaves_original_unchanged():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        upper = _color(ws, (layer_w, layer_h), layer_c, duration=_COMPOSE_DURATION)
        moved = require_ok(ws.call(upper.with_position, "center"))
        orig_frame = _frame(ws, _overlay(ws, lower, upper), 0.0)
        moved_frame = _frame(ws, _overlay(ws, lower, moved), 0.0)
        print(
            f"position_copy default_tl={_rgb_at(orig_frame, 0, 0)} "
            f"moved_tl={_rgb_at(moved_frame, 0, 0)}",
            flush=True,
        )
        assert moved is not upper
        _assert_color_at(orig_frame, 0, 0, layer_c)
        _assert_color_at(moved_frame, 0, 0, lower_c)
        cx, cy = _keyword_top_left("center", canvas_w, canvas_h, layer_w, layer_h)
        _assert_color_at(moved_frame, cx, cy, layer_c)


# ---------------------------------------------------------------------------
# E. inverted crop and invalid position keyword
# ---------------------------------------------------------------------------


def test_inverted_crop_does_not_yield_positive_size():
    with workspace() as ws:
        src_w = _rand_int(8, 12) * 2
        src_h = _rand_int(7, 11) * 2
        if src_w == src_h:
            src_h = src_w + 2
        x_left = _rand_int(2, src_w // 3)
        x_right = _rand_int(src_w // 2, src_w - 2)
        y_top = _rand_int(2, src_h // 3)
        y_bottom = _rand_int(src_h // 2, src_h - 2)
        assert x_right > x_left and y_bottom > y_top
        inside = _rgb()
        outside = _rgb_away_from(inside)
        picture = _solid(src_h, src_w, outside)
        picture[y_top:y_bottom, x_left:x_right] = inside
        source = _still(ws, picture, _DURATION)
        sibling = require_ok(
            ws.call(
                source.cropped,
                x1=x_left,
                y1=y_top,
                x2=x_right,
                y2=y_bottom,
            )
        )
        sib_frame = _frame(ws, sibling, 0.0)
        print(
            f"invert_sibling rect=({x_left},{y_top})-({x_right},{y_bottom}) "
            f"size={_frame_size(sib_frame)}",
            flush=True,
        )
        _assert_frame_size(sib_frame, x_right - x_left, y_bottom - y_top)
        assert pictures_equal(sib_frame, picture[y_top:y_bottom, x_left:x_right])

        for label, kwargs in (
            (
                "horizontal",
                dict(x1=x_right, y1=y_top, x2=x_left, y2=y_bottom),
            ),
            (
                "vertical",
                dict(x1=x_left, y1=y_bottom, x2=x_right, y2=y_top),
            ),
        ):
            result = ws.call(source.cropped, **kwargs)
            if not isinstance(result, CallResult):
                raise HarnessError(
                    f"{label} inverted crop probe is not a CallResult"
                )
            if result.exception is not None:
                print(
                    f"{label} inverted crop call did not succeed: "
                    f"{result.exception!r}",
                    flush=True,
                )
                continue
            clip = result.value
            width, height = _require_size(clip)
            print(f"{label} inverted size={(width, height)}", flush=True)
            if width > 0 and height > 0:
                raise AssertionError(
                    f"{label} inverted crop yielded both dimensions "
                    f"positive: {(width, height)}"
                )
            pictured = ws.call(clip.get_frame, 0.0)
            if not isinstance(pictured, CallResult):
                raise HarnessError(
                    f"{label} inverted get_frame is not a CallResult"
                )
            if pictured.exception is not None:
                print(
                    f"{label} inverted get_frame did not succeed: "
                    f"{pictured.exception!r}",
                    flush=True,
                )
                continue
            pw, ph = _frame_size(pictured.value)
            print(f"{label} inverted picture={(pw, ph)}", flush=True)
            if pw > 0 and ph > 0:
                raise AssertionError(
                    f"{label} inverted crop still produced a picture "
                    f"with both dimensions positive: {(pw, ph)}"
                )


def test_invalid_position_keyword_is_not_valid_in_composition():
    with workspace() as ws:
        canvas_w, canvas_h, layer_w, layer_h = _even_canvas_layer()
        word = _invalid_keyword()
        assert word not in _DOC_KEYWORDS and word not in _COMPASS
        lower_c = _rgb()
        layer_c = _rgb_away_from(lower_c)
        corner = _rgb_away_from(lower_c, layer_c)
        lower = _color(ws, (canvas_w, canvas_h), lower_c, duration=_COMPOSE_DURATION)
        picture = _marked_layer_picture(layer_h, layer_w, corner, layer_c)
        upper = _still(ws, picture, _COMPOSE_DURATION)

        sibling = require_ok(ws.call(upper.with_position, "center"))
        sib_frame = _frame(ws, _overlay(ws, lower, sibling), 0.0)
        cx, cy = _keyword_top_left("center", canvas_w, canvas_h, layer_w, layer_h)
        _assert_layer_top_left(sib_frame, cx, cy, corner, lower_c)

        assigned = ws.call(upper.with_position, word)
        if not isinstance(assigned, CallResult):
            raise HarnessError("invalid-keyword with_position is not a CallResult")
        print(f"invalid_keyword word={word!r}", flush=True)

        # Only accepted green paths: assignment, composition, or the frame
        # request does not succeed as a placement of that keyword. A produced
        # frame is a successful placement, wherever the layer sits — origin,
        # center, right, bottom, omitted, or any other slot — and must not pass.
        placement_failed = False
        if assigned.exception is not None:
            placement_failed = True
            print(
                f"invalid keyword rejected at assignment: {assigned.exception!r}",
                flush=True,
            )
        else:
            composed = ws.call(CompositeVideoClip, [lower, assigned.value])
            if not isinstance(composed, CallResult):
                raise HarnessError("invalid-keyword compose is not a CallResult")
            if composed.exception is not None:
                placement_failed = True
                print(
                    f"invalid keyword rejected at compose: {composed.exception!r}",
                    flush=True,
                )
            else:
                got = ws.call(composed.value.get_frame, 0.0)
                if not isinstance(got, CallResult):
                    raise HarnessError(
                        "invalid-keyword get_frame is not a CallResult"
                    )
                if got.exception is not None:
                    placement_failed = True
                    print(
                        f"invalid keyword rejected at get_frame: {got.exception!r}",
                        flush=True,
                    )
                else:
                    frame = got.value
                    detect_atol = 40.0
                    body_count = int(
                        np.count_nonzero(
                            _near_color_mask(frame, layer_c, atol=detect_atol)
                        )
                    )
                    corner_count = int(
                        np.count_nonzero(
                            _near_color_mask(frame, corner, atol=detect_atol)
                        )
                    )
                    print(
                        f"invalid_keyword produced_frame "
                        f"size={_frame_size(frame)} "
                        f"layer_body_pixels={body_count} "
                        f"layer_corner_pixels={corner_count}",
                        flush=True,
                    )
                    raise AssertionError(
                        "invalid keyword was accepted as a placement: "
                        "assignment, composition, and frame request all "
                        "succeeded; "
                        f"size={_frame_size(frame)} "
                        f"body_pixels={body_count} "
                        f"corner_pixels={corner_count}"
                    )

        assert placement_failed
