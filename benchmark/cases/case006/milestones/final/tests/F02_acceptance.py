# feature: F02
"""Construct clips from pictures, color, text, sequences, and generated frames (FP-02).

Assertions stay at the PRD's precision: stills from files and arrays, optional
duration, alpha-to-mask, still-from-frame, solid color (default black, four
channel, mask mode), text layout and rendering, image sequences, generated
video and audio, array audio, constructor refusals, and construction without
the encoder. Exception types and failure wording are not pinned.
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
    ImageClip,
    ImageSequenceClip,
    TextClip,
    VideoClip,
)

from _harness import HarnessError, workspace
from _helpers import (
    as_numeric_array,
    find_opentype_fonts,
    pictures_equal,
    require_failed,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
    require_sound_frame,
    samples_close,
)


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


def _solid(height: int, width: int, color: tuple[int, int, int]) -> np.ndarray:
    picture = np.zeros((height, width, 3), dtype=np.uint8)
    picture[:, :] = np.asarray(color, dtype=np.uint8)
    return picture


def _write_rgb(path: Path, picture: np.ndarray, fmt: str) -> Path:
    arr = as_numeric_array(picture)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise AssertionError(f"cannot write an RGB image from shape {arr.shape}")
    rgb = np.round(arr[:, :, :3]).astype(np.uint8)
    try:
        from PIL import Image
    except ImportError as exc:
        raise HarnessError(f"Pillow is required to write image fixtures: {exc}") from exc
    Image.fromarray(rgb, mode="RGB").save(path, format=fmt)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HarnessError(f"cannot stat written image {path}: {exc}") from exc
    if not path.is_file() or size <= 0:
        raise AssertionError(f"image was not written as a nonempty file: {path}")
    return path


def _write_rgba_png(
    path: Path, rgb: np.ndarray, alpha: np.ndarray
) -> Path:
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


def _copy_font(ws, src: Path, stem: str) -> Path:
    dest = ws.resolve(stem + src.suffix.lower())
    try:
        data = src.read_bytes()
    except OSError as exc:
        raise HarnessError(f"cannot read font {src}: {exc}") from exc
    if not data:
        raise AssertionError(f"font file is empty: {src}")
    dest.write_bytes(data)
    if dest.stat().st_size <= 0:
        raise AssertionError(f"copied font is empty: {dest}")
    return dest


def _picture_rgb(frame) -> np.ndarray:
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise AssertionError(f"expected a picture with at least 3 channels; got {arr.shape}")
    return arr[:, :, :3]


def _near_color_mask(frame, color: tuple[int, int, int], atol: float = 45.0) -> np.ndarray:
    rgb = _picture_rgb(frame).astype(float)
    target = np.asarray(color, dtype=float).reshape(1, 1, 3)
    return np.linalg.norm(rgb - target, axis=2) <= atol


def _require_ink(frame, color: tuple[int, int, int], atol: float = 45.0) -> np.ndarray:
    mask = _near_color_mask(frame, color, atol=atol)
    if not np.any(mask):
        raise AssertionError(
            f"picture has no pixels near requested text color {color}; "
            f"shape={as_numeric_array(frame).shape}"
        )
    return mask


def _ink_com(mask: np.ndarray) -> tuple[float, float]:
    rows, cols = np.nonzero(mask)
    if cols.size == 0:
        raise AssertionError("no ink pixels from which to take a center of mass")
    return float(cols.mean()), float(rows.mean())


def _ink_bbox_height(mask: np.ndarray) -> int:
    rows, cols = np.nonzero(mask)
    if cols.size == 0:
        raise AssertionError("no ink pixels from which to take a bounding box")
    return int(rows.max() - rows.min() + 1)


def _blank_canvas(frame) -> bool:
    rgb = _picture_rgb(frame)
    return bool(np.allclose(rgb.astype(float), 0.0, atol=1.0))


def _time_picture(height: int, width: int, scale: float = 80.0):
    def frame_function(t):
        picture = np.zeros((height, width, 3), dtype=np.uint8)
        picture[:, :, 0] = int(np.clip(float(t) * scale, 0, 255))
        picture[:, :, 1] = 90
        picture[:, :, 2] = 40
        return picture

    return frame_function


def _attached_mask_frame(ws, clip, t: float = 0.0):
    mask = clip.mask
    if mask is None:
        return None
    raw = require_ok(ws.call(mask.get_frame, t))
    return as_numeric_array(raw)


def _equal_length_words() -> tuple[str, str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    n = _rand_int(5, 8)
    left = "".join(alphabet[secrets.randbelow(len(alphabet))] for _ in range(n))
    right = "".join(alphabet[secrets.randbelow(len(alphabet))] for _ in range(n))
    if left == right:
        right = right[:-1] + ("Z" if right[-1] != "Z" else "Y")
    return left, right


def _jpeg_near_solid(frame, color: tuple[int, int, int], atol: float = 28.0) -> None:
    rgb = _picture_rgb(frame).astype(float)
    mean = rgb.reshape(-1, 3).mean(axis=0)
    target = np.asarray(color, dtype=float)
    print(f"jpeg_mean={tuple(mean)} requested={color}", flush=True)
    if np.linalg.norm(mean - target) > atol:
        raise AssertionError(
            f"JPEG picture mean {tuple(mean)} is not near requested {color}"
        )


# ---------------------------------------------------------------------------
# A. Still from array / file; same picture at every time
# ---------------------------------------------------------------------------


def test_array_still_same_picture_at_every_time():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        source = _solid(height, width, color)
        duration = 0.4 + _rand_int(1, 6) / 10.0
        still = require_ok(ws.call(ImageClip, source, duration=duration))
        at_zero = require_ok(ws.call(still.get_frame, 0))
        at_mid = require_ok(ws.call(still.get_frame, duration / 2.0))
        print(
            f"array_still size={(width, height)} color={color} D={duration} "
            f"shape={as_numeric_array(at_zero).shape}",
            flush=True,
        )
        require_rgb_picture(at_zero, height, width, color=color)
        assert pictures_equal(at_zero, source)
        assert pictures_equal(at_zero, at_mid)

        varying = require_ok(
            ws.call(
                VideoClip,
                frame_function=_time_picture(height, width),
                duration=duration,
            )
        )
        gen_zero = require_ok(ws.call(varying.get_frame, 0))
        gen_mid = require_ok(ws.call(varying.get_frame, duration / 2.0))
        assert pictures_equal(require_ok(ws.call(still.get_frame, 0)), at_mid)
        assert not pictures_equal(gen_zero, gen_mid)


def test_file_still_png_jpeg_tiff_size_and_pixels():
    with workspace() as ws:
        width, height = _rect_size()
        png_color = _rgb()
        jpeg_color = _rgb_away_from(png_color)
        jpeg_other = _rgb_away_from(jpeg_color)
        tiff_color = _rgb_away_from(jpeg_color)

        png_src = _solid(height, width, png_color)
        png_path = _write_rgb(ws.resolve("still.png"), png_src, "PNG")
        png_clip = require_ok(ws.call(ImageClip, str(png_path)))
        png_frame = require_ok(ws.call(png_clip.get_frame, 0))
        print(f"png shape={as_numeric_array(png_frame).shape} color={png_color}", flush=True)
        require_rgb_picture(png_frame, height, width, color=png_color)
        assert pictures_equal(png_frame, png_src)

        jpeg_path = _write_rgb(
            ws.resolve("still.jpg"), _solid(height, width, jpeg_color), "JPEG"
        )
        jpeg_other_path = _write_rgb(
            ws.resolve("still_other.jpg"), _solid(height, width, jpeg_other), "JPEG"
        )
        jpeg_clip = require_ok(ws.call(ImageClip, str(jpeg_path)))
        jpeg_other_clip = require_ok(ws.call(ImageClip, str(jpeg_other_path)))
        jpeg_frame = require_ok(ws.call(jpeg_clip.get_frame, 0))
        jpeg_other_frame = require_ok(ws.call(jpeg_other_clip.get_frame, 0))
        require_rgb_picture(jpeg_frame, height, width)
        require_rgb_picture(jpeg_other_frame, height, width)
        _jpeg_near_solid(jpeg_frame, jpeg_color)
        assert not pictures_equal(jpeg_frame, jpeg_other_frame)

        tiff_src = _solid(height, width, tiff_color)
        tiff_path = _write_rgb(ws.resolve("still.tiff"), tiff_src, "TIFF")
        tiff_clip = require_ok(ws.call(ImageClip, str(tiff_path)))
        tiff_frame = require_ok(ws.call(tiff_clip.get_frame, 0))
        print(f"tiff color={tiff_color} shape={as_numeric_array(tiff_frame).shape}", flush=True)
        require_rgb_picture(tiff_frame, height, width, color=tiff_color)
        assert pictures_equal(tiff_frame, tiff_src)


def test_non_image_path_does_not_succeed():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        fake = ws.resolve("looks_like.png")
        fake.write_bytes(b"not-an-image-payload-" + secrets.token_bytes(32))
        if not fake.is_file() or fake.stat().st_size <= 0:
            raise AssertionError(f"non-image fixture was not written: {fake}")
        failed = ws.call(ImageClip, str(fake))
        print(f"non_image_failed={failed.exception is not None}", flush=True)
        require_failed(failed)

        real = _write_rgb(
            ws.resolve("real.png"), _solid(height, width, color), "PNG"
        )
        sibling = require_ok(ws.call(ImageClip, str(real)))
        frame = require_ok(ws.call(sibling.get_frame, 0))
        require_rgb_picture(frame, height, width, color=color)


# ---------------------------------------------------------------------------
# B. Optional duration
# ---------------------------------------------------------------------------


def test_still_duration_absent_unless_supplied():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        source = _solid(height, width, color)
        infinite = require_ok(ws.call(ImageClip, source))
        duration = 0.5 + _rand_int(1, 8) / 10.0
        finite = require_ok(ws.call(ImageClip, source, duration=duration))
        print(
            f"absent={infinite.duration} supplied={finite.duration} D={duration}",
            flush=True,
        )
        assert infinite.duration is None
        assert finite.duration == pytest.approx(duration)
        require_rgb_picture(require_ok(ws.call(infinite.get_frame, 0)), height, width, color=color)
        require_rgb_picture(require_ok(ws.call(finite.get_frame, 0)), height, width, color=color)


# ---------------------------------------------------------------------------
# C. Alpha becomes mask when transparency is left on
# ---------------------------------------------------------------------------


def test_still_alpha_becomes_mask_by_default():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        rgb = _solid(height, width, color)
        alpha = np.zeros((height, width), dtype=np.uint8)
        alpha[:, width // 2 :] = 255
        packed = np.zeros((height, width, 4), dtype=np.uint8)
        packed[:, :, :3] = rgb
        packed[:, :, 3] = alpha

        array_default = require_ok(ws.call(ImageClip, packed))
        array_on = require_ok(ws.call(ImageClip, packed, transparent=True))
        array_frame = require_ok(ws.call(array_default.get_frame, 0))
        print(
            f"array_alpha shape={as_numeric_array(array_frame).shape} "
            f"mask={array_default.mask is not None}",
            flush=True,
        )
        require_rgb_picture(array_frame, height, width, color=color)
        default_mask = _attached_mask_frame(ws, array_default)
        on_mask = _attached_mask_frame(ws, array_on)
        assert default_mask is not None
        assert on_mask is not None
        require_mask_picture(default_mask, height, width)
        expected = alpha.astype(float) / 255.0
        assert np.allclose(default_mask, expected, atol=1.0 / 255.0 + 1e-6)
        assert np.allclose(on_mask, default_mask, atol=1e-6)

        png_path = _write_rgba_png(ws.resolve("alpha.png"), rgb, alpha)
        file_clip = require_ok(ws.call(ImageClip, str(png_path)))
        file_frame = require_ok(ws.call(file_clip.get_frame, 0))
        require_rgb_picture(file_frame, height, width, color=color)
        file_mask = _attached_mask_frame(ws, file_clip)
        assert file_mask is not None
        require_mask_picture(file_mask, height, width)
        assert np.allclose(file_mask, expected, atol=1.0 / 255.0 + 1e-6)


def test_still_transparency_off_ignores_alpha():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        rgb = _solid(height, width, color)
        alpha = np.zeros((height, width), dtype=np.uint8)
        alpha[:, width // 2 :] = 255
        packed = np.zeros((height, width, 4), dtype=np.uint8)
        packed[:, :, :3] = rgb
        packed[:, :, 3] = alpha
        expected = alpha.astype(float) / 255.0

        baseline = require_ok(ws.call(ImageClip, packed))
        baseline_mask = _attached_mask_frame(ws, baseline)
        assert baseline_mask is not None
        require_mask_picture(baseline_mask, height, width)
        assert np.allclose(baseline_mask, expected, atol=1.0 / 255.0 + 1e-6)

        off = require_ok(ws.call(ImageClip, packed, transparent=False))
        off_rgb = _picture_rgb(require_ok(ws.call(off.get_frame, 0)))
        require_rgb_picture(off_rgb, height, width, color=color)
        off_mask = _attached_mask_frame(ws, off)
        print(f"off_mask_present={off_mask is not None}", flush=True)
        if off_mask is not None:
            require_mask_picture(off_mask, height, width)
            assert not np.allclose(off_mask, expected, atol=0.05)

        png_path = _write_rgba_png(ws.resolve("alpha_off.png"), rgb, alpha)
        file_off = require_ok(ws.call(ImageClip, str(png_path), transparent=False))
        file_rgb = _picture_rgb(require_ok(ws.call(file_off.get_frame, 0)))
        require_rgb_picture(file_rgb, height, width, color=color)
        file_mask = _attached_mask_frame(ws, file_off)
        if file_mask is not None:
            require_mask_picture(file_mask, height, width)
            assert not np.allclose(file_mask, expected, atol=0.05)


# ---------------------------------------------------------------------------
# D. Still from a video clip at time t
# ---------------------------------------------------------------------------


def test_still_from_color_at_zero_matches():
    with workspace() as ws:
        size = (16, 16)
        color = (255, 0, 0)
        source = require_ok(ws.call(ColorClip, size, color=color, duration=0.5))
        source_frame = require_ok(ws.call(source.get_frame, 0))
        still = require_ok(ws.call(source.to_ImageClip, 0))
        still_frame = require_ok(ws.call(still.get_frame, 0))
        print(
            f"from_color_zero shape={as_numeric_array(still_frame).shape}",
            flush=True,
        )
        require_rgb_picture(still_frame, 16, 16, color=color)
        assert pictures_equal(still_frame, source_frame)


def test_still_from_generated_at_t_matches_that_frame():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        duration = 3.5
        source = require_ok(ws.call(VideoClip, frame_function=fn, duration=duration))
        t0 = 1.0 + _rand_int(2, 8) / 10.0
        at_t0 = require_ok(ws.call(source.get_frame, t0))
        at_zero = require_ok(ws.call(source.get_frame, 0))
        still = require_ok(ws.call(source.to_ImageClip, t0))
        still_a = require_ok(ws.call(still.get_frame, 0))
        still_b = require_ok(ws.call(still.get_frame, 0.8))
        print(f"from_generated t0={t0} still_match={pictures_equal(still_a, at_t0)}", flush=True)
        assert pictures_equal(still_a, at_t0)
        assert pictures_equal(still_b, at_t0)
        assert pictures_equal(still_a, still_b)
        assert not pictures_equal(at_t0, at_zero)
        assert not pictures_equal(still_a, at_zero)


# ---------------------------------------------------------------------------
# E. Solid color
# ---------------------------------------------------------------------------


def test_color_clip_oracle_16x16_red():
    with workspace() as ws:
        clip = require_ok(ws.call(ColorClip, (16, 16), color=(255, 0, 0)))
        frame = require_ok(ws.call(clip.get_frame, 0))
        print(f"oracle_red shape={as_numeric_array(frame).shape}", flush=True)
        picture = require_rgb_picture(frame, 16, 16, color=(255, 0, 0))
        assert picture.shape == (16, 16, 3)


def test_color_clip_runtime_rgb_every_pixel():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        clip = require_ok(ws.call(ColorClip, (width, height), color=color))
        frame = require_ok(ws.call(clip.get_frame, 0))
        print(f"runtime_color size={(width, height)} color={color}", flush=True)
        picture = require_rgb_picture(frame, height, width, color=color)
        assert picture.shape == (height, width, 3)
        assert width != height


def test_omitted_color_is_black():
    with workspace() as ws:
        width, height = _rect_size()
        omitted = require_ok(ws.call(ColorClip, (width, height)))
        explicit = require_ok(
            ws.call(ColorClip, (width, height), color=(0, 0, 0))
        )
        omitted_frame = require_ok(ws.call(omitted.get_frame, 0))
        explicit_frame = require_ok(ws.call(explicit.get_frame, 0))
        print(
            f"omitted_color shape={as_numeric_array(omitted_frame).shape}",
            flush=True,
        )
        picture = require_rgb_picture(
            omitted_frame, height, width, color=(0, 0, 0)
        )
        assert picture.shape == (height, width, 3)
        assert np.allclose(
            picture.astype(float),
            np.asarray((0, 0, 0), dtype=float).reshape(1, 1, 3),
            atol=0.5,
            rtol=0,
        )
        assert pictures_equal(omitted_frame, explicit_frame)


def test_four_channel_color_picture_and_mask():
    with workspace() as ws:
        width, height = _rect_size()
        rgb = _rgb()
        alpha_lo = _rand_int(40, 110)
        alpha_hi = _rand_int(140, 220)
        if alpha_hi == alpha_lo:
            alpha_hi = alpha_lo + 30
        low = require_ok(
            ws.call(ColorClip, (width, height), color=(*rgb, alpha_lo))
        )
        high = require_ok(
            ws.call(ColorClip, (width, height), color=(*rgb, alpha_hi))
        )
        low_pic = require_ok(ws.call(low.get_frame, 0))
        high_pic = require_ok(ws.call(high.get_frame, 0))
        require_rgb_picture(low_pic, height, width, color=rgb)
        require_rgb_picture(high_pic, height, width, color=rgb)
        low_mask = _attached_mask_frame(ws, low)
        high_mask = _attached_mask_frame(ws, high)
        print(
            f"A_lo={alpha_lo} A_hi={alpha_hi} "
            f"masks={low_mask is not None},{high_mask is not None}",
            flush=True,
        )
        assert low_mask is not None
        assert high_mask is not None
        require_mask_picture(low_mask, height, width)
        require_mask_picture(high_mask, height, width)
        assert not np.allclose(low_mask, high_mask, atol=1e-4)
        if alpha_hi > alpha_lo:
            assert float(high_mask.mean()) > float(low_mask.mean())
        else:
            assert float(low_mask.mean()) > float(high_mask.mean())


def test_mask_mode_scalar_greyscale():
    with workspace() as ws:
        width, height = _rect_size()
        level = 0.2 + _rand_int(1, 60) / 100.0
        clip = require_ok(
            ws.call(ColorClip, (width, height), color=level, is_mask=True)
        )
        frame = require_ok(ws.call(clip.get_frame, 0))
        print(f"mask_scalar size={(width, height)} level={level}", flush=True)
        mask = require_mask_picture(frame, height, width)
        assert np.allclose(mask, level, atol=1e-5)


def test_mask_mode_rejects_non_scalar_color():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        level = 0.4
        failed = ws.call(ColorClip, (width, height), color=color, is_mask=True)
        print(f"mask_non_scalar_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        assert failed.exception is not None
        sibling = require_ok(
            ws.call(ColorClip, (width, height), color=level, is_mask=True)
        )
        mask = require_mask_picture(
            require_ok(ws.call(sibling.get_frame, 0)), height, width
        )
        assert np.allclose(mask, level, atol=1e-5)


def test_non_mask_rejects_scalar_or_string_color():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        scalar = ws.call(ColorClip, (width, height), color=0.4)
        named = ws.call(ColorClip, (width, height), color="red")
        print(
            f"scalar_failed={scalar.exception is not None} "
            f"string_failed={named.exception is not None}",
            flush=True,
        )
        require_failed(scalar)
        require_failed(named)
        assert scalar.exception is not None
        assert named.exception is not None
        sibling = require_ok(ws.call(ColorClip, (width, height), color=color))
        picture = require_rgb_picture(
            require_ok(ws.call(sibling.get_frame, 0)), height, width, color=color
        )
        assert picture.shape == (height, width, 3)


# ---------------------------------------------------------------------------
# F. Text rendering
# ---------------------------------------------------------------------------


def test_text_hello_white_glyphs_distinct_from_world():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "hello_font")
        white = (255, 255, 255)
        hello = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="Hello",
                font_size=28,
                color=white,
            )
        )
        world = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="World",
                font_size=28,
                color=white,
            )
        )
        hello_frame = require_ok(ws.call(hello.get_frame, 0))
        world_frame = require_ok(ws.call(world.get_frame, 0))
        print(
            f"hello_shape={as_numeric_array(hello_frame).shape} "
            f"world_shape={as_numeric_array(world_frame).shape}",
            flush=True,
        )
        assert not _blank_canvas(hello_frame)
        _require_ink(hello_frame, white)
        assert not pictures_equal(hello_frame, world_frame)

        left, right = _equal_length_words()
        a = require_ok(
            ws.call(TextClip, font=str(font), text=left, font_size=26, color=white)
        )
        b = require_ok(
            ws.call(TextClip, font=str(font), text=right, font_size=26, color=white)
        )
        a_frame = require_ok(ws.call(a.get_frame, 0))
        b_frame = require_ok(ws.call(b.get_frame, 0))
        print(f"runtime_words {left!r} vs {right!r}", flush=True)
        assert not pictures_equal(a_frame, b_frame)

        ascii_text = "Cafe"
        unicode_text = "Café"
        ascii_clip = require_ok(
            ws.call(
                TextClip, font=str(font), text=ascii_text, font_size=26, color=white
            )
        )
        unicode_clip = require_ok(
            ws.call(
                TextClip, font=str(font), text=unicode_text, font_size=26, color=white
            )
        )
        assert not pictures_equal(
            require_ok(ws.call(ascii_clip.get_frame, 0)),
            require_ok(ws.call(unicode_clip.get_frame, 0)),
        )


def test_text_named_fonts_produce_distinct_pictures():
    with workspace() as ws:
        fonts = find_opentype_fonts(2)
        first = _copy_font(ws, fonts[0], "named_a")
        second = _copy_font(ws, fonts[1], "named_b")
        same_as_first = _copy_font(ws, fonts[0], "named_a_copy")
        text = "GlyphProbe"
        color = (255, 255, 255)
        size = 30
        a = require_ok(
            ws.call(TextClip, font=str(first), text=text, font_size=size, color=color)
        )
        b = require_ok(
            ws.call(TextClip, font=str(second), text=text, font_size=size, color=color)
        )
        a_again = require_ok(
            ws.call(
                TextClip, font=str(same_as_first), text=text, font_size=size, color=color
            )
        )
        fa = require_ok(ws.call(a.get_frame, 0))
        fb = require_ok(ws.call(b.get_frame, 0))
        fa2 = require_ok(ws.call(a_again.get_frame, 0))
        print(
            f"fonts {fonts[0].name} vs {fonts[1].name} "
            f"distinct={not pictures_equal(fa, fb)}",
            flush=True,
        )
        assert not pictures_equal(fa, fb)
        assert pictures_equal(fa, fa2)


def test_text_default_font_renders_distinct_strings():
    with workspace() as ws:
        white = (255, 255, 255)
        hello = require_ok(ws.call(TextClip, text="Hello", font_size=24, color=white))
        world = require_ok(ws.call(TextClip, text="World", font_size=24, color=white))
        hf = require_ok(ws.call(hello.get_frame, 0))
        wf = require_ok(ws.call(world.get_frame, 0))
        print(
            f"default_font hello_blank={_blank_canvas(hf)} distinct={not pictures_equal(hf, wf)}",
            flush=True,
        )
        assert not _blank_canvas(hf)
        _require_ink(hf, white, atol=80.0)
        assert not pictures_equal(hf, wf)


def test_text_from_file_matches_string():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "file_font")
        color = (255, 255, 255)
        body = "FileBody"
        path = ws.write("caption.txt", body)
        from_file = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                filename=str(path),
                font_size=24,
                color=color,
            )
        )
        from_string = require_ok(
            ws.call(
                TextClip, font=str(font), text=body, font_size=24, color=color
            )
        )
        file_frame = require_ok(ws.call(from_file.get_frame, 0))
        string_frame = require_ok(ws.call(from_string.get_frame, 0))
        print(
            f"file_vs_string match={pictures_equal(file_frame, string_frame)}",
            flush=True,
        )
        assert pictures_equal(file_frame, string_frame)

        other = ws.write("caption_other.txt", "OtherBody")
        other_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                filename=str(other),
                font_size=24,
                color=color,
            )
        )
        assert not pictures_equal(
            file_frame, require_ok(ws.call(other_clip.get_frame, 0))
        )


def test_text_color_rgb_hex_and_name():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "color_font")
        rgb = (255, 0, 0)
        hex_clip = require_ok(
            ws.call(
                TextClip, font=str(font), text="Tint", font_size=28, color="#FF0000"
            )
        )
        rgb_clip = require_ok(
            ws.call(TextClip, font=str(font), text="Tint", font_size=28, color=rgb)
        )
        hex_frame = require_ok(ws.call(hex_clip.get_frame, 0))
        rgb_frame = require_ok(ws.call(rgb_clip.get_frame, 0))
        print(
            f"hex_vs_rgb match={pictures_equal(hex_frame, rgb_frame)}",
            flush=True,
        )
        _require_ink(rgb_frame, rgb)
        assert pictures_equal(hex_frame, rgb_frame)

        rgba_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="Tint",
                font_size=28,
                color=(0, 180, 40, 200),
            )
        )
        rgba_frame = require_ok(ws.call(rgba_clip.get_frame, 0))
        assert not _blank_canvas(rgba_frame)
        assert not pictures_equal(_picture_rgb(rgba_frame), _picture_rgb(rgb_frame))

        red = require_ok(
            ws.call(TextClip, font=str(font), text="Name", font_size=28, color="red")
        )
        blue = require_ok(
            ws.call(TextClip, font=str(font), text="Name", font_size=28, color="blue")
        )
        red_frame = require_ok(ws.call(red.get_frame, 0))
        blue_frame = require_ok(ws.call(blue.get_frame, 0))
        assert not pictures_equal(red_frame, blue_frame)


def test_text_omitted_background_distinct_from_opaque():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "bg_font")
        text = "Hole"
        color = (255, 255, 255)
        contrast = (40, 180, 40)
        box = (280, 100)
        omitted = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=28,
                color=color,
                method="caption",
                size=box,
            )
        )
        opaque = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=28,
                color=color,
                method="caption",
                size=box,
                bg_color=contrast,
            )
        )
        omitted_frame = require_ok(ws.call(omitted.get_frame, 0))
        opaque_frame = require_ok(ws.call(opaque.get_frame, 0))
        assert np.any(_near_color_mask(opaque_frame, contrast, atol=35.0))
        glyphs = _require_ink(omitted_frame, color)
        omitted_mask = _attached_mask_frame(ws, omitted)
        print(
            f"omitted_mask={omitted_mask is not None} "
            f"opaque_has_contrast={np.any(_near_color_mask(opaque_frame, contrast, atol=35.0))}",
            flush=True,
        )
        assert omitted_mask is not None
        require_mask_picture(omitted_mask, box[1], box[0])
        outside = ~glyphs
        assert np.any(outside)
        assert float(omitted_mask[outside].mean()) < 0.2

        opaque_mask = _attached_mask_frame(ws, opaque)
        contrast_pixels = _near_color_mask(opaque_frame, contrast, atol=35.0)
        assert np.any(contrast_pixels)
        if opaque_mask is None:
            print("opaque_has_no_mask (fully visible)", flush=True)
        else:
            require_mask_picture(opaque_mask, box[1], box[0])
            assert float(opaque_mask[contrast_pixels].mean()) > 0.5


# ---------------------------------------------------------------------------
# G. Label / caption layout
# ---------------------------------------------------------------------------


def test_text_default_layout_is_label():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "layout_font")
        kwargs = dict(font=str(font), text="Layout", font_size=22, color=(255, 255, 255))
        omitted = require_ok(ws.call(TextClip, **kwargs))
        explicit = require_ok(ws.call(TextClip, method="label", **kwargs))
        of = require_ok(ws.call(omitted.get_frame, 0))
        ef = require_ok(ws.call(explicit.get_frame, 0))
        print(
            f"default_vs_label match={pictures_equal(of, ef)} shapes={of.shape},{ef.shape}",
            flush=True,
        )
        assert pictures_equal(of, ef)


def test_label_font_size_computes_width_and_height():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "label_size_font")
        color = (255, 255, 255)
        short = require_ok(
            ws.call(TextClip, font=str(font), text="Hi", font_size=24, color=color)
        )
        long = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="HelloWorldLonger",
                font_size=24,
                color=color,
            )
        )
        short_f = require_ok(ws.call(short.get_frame, 0))
        long_f = require_ok(ws.call(long.get_frame, 0))
        print(
            f"label_short={as_numeric_array(short_f).shape} long={as_numeric_array(long_f).shape}",
            flush=True,
        )
        short_arr = as_numeric_array(short_f)
        long_arr = as_numeric_array(long_f)
        assert long_arr.shape[1] > short_arr.shape[1]

        small_fs = _rand_int(14, 18)
        large_fs = small_fs * 2
        same_text = "Hi"
        small_type = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=same_text,
                font_size=small_fs,
                color=color,
            )
        )
        large_type = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=same_text,
                font_size=large_fs,
                color=color,
            )
        )
        small_h = as_numeric_array(require_ok(ws.call(small_type.get_frame, 0))).shape[0]
        large_h = as_numeric_array(require_ok(ws.call(large_type.get_frame, 0))).shape[0]
        print(
            f"label_height_from_font small_fs={small_fs} h={small_h} "
            f"large_fs={large_fs} h={large_h}",
            flush=True,
        )
        assert large_h > small_h


def test_caption_requires_width():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "cap_w_font")
        failed = ws.call(
            TextClip,
            font=str(font),
            text="NeedWidth",
            font_size=20,
            method="caption",
            size=(None, 80),
            color=(255, 255, 255),
        )
        print(f"caption_no_width_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        ok = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="NeedWidth",
                font_size=20,
                method="caption",
                size=(220, None),
                color=(255, 255, 255),
            )
        )
        frame = require_ok(ws.call(ok.get_frame, 0))
        assert as_numeric_array(frame).shape[1] == 220
        assert not _blank_canvas(frame)


def test_caption_requires_height_or_font_size():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "cap_hf_font")
        failed = ws.call(
            TextClip,
            font=str(font),
            text="NeedOne",
            method="caption",
            size=(200, None),
            color=(255, 255, 255),
        )
        print(f"caption_no_h_no_size_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        sibling = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="NeedOne",
                font_size=18,
                method="caption",
                size=(200, None),
                color=(255, 255, 255),
            )
        )
        assert not _blank_canvas(require_ok(ws.call(sibling.get_frame, 0)))


def test_caption_omitted_font_size_fits_box():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "fit_font")
        text = "Scale"
        color = (255, 255, 255)
        width = 220
        short_box = (width, 32)
        tall_box = (width, 72)
        short_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                method="caption",
                size=short_box,
                color=color,
            )
        )
        tall_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                method="caption",
                size=tall_box,
                color=color,
            )
        )
        short_f = require_ok(ws.call(short_clip.get_frame, 0))
        tall_f = require_ok(ws.call(tall_clip.get_frame, 0))
        print(
            f"fit_short={as_numeric_array(short_f).shape} tall={as_numeric_array(tall_f).shape}",
            flush=True,
        )
        require_rgb_picture(short_f, short_box[1], short_box[0])
        require_rgb_picture(tall_f, tall_box[1], tall_box[0])
        assert not _blank_canvas(short_f)
        assert not _blank_canvas(tall_f)
        short_ink_h = _ink_bbox_height(_require_ink(short_f, color, atol=55.0))
        tall_ink_h = _ink_bbox_height(_require_ink(tall_f, color, atol=55.0))
        print(f"ink_bbox_h short={short_ink_h} tall={tall_ink_h}", flush=True)
        assert tall_ink_h > short_ink_h


def test_caption_omitted_height_computes_height():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "cap_h_font")
        text = "ComputeHeight Please"
        color = (255, 255, 255)
        width = 240
        small_fs = _rand_int(12, 16)
        large_fs = small_fs * 2
        small_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=small_fs,
                method="caption",
                size=(width, None),
                color=color,
            )
        )
        large_clip = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=large_fs,
                method="caption",
                size=(width, None),
                color=color,
            )
        )
        small_f = require_ok(ws.call(small_clip.get_frame, 0))
        large_f = require_ok(ws.call(large_clip.get_frame, 0))
        small_arr = as_numeric_array(small_f)
        large_arr = as_numeric_array(large_f)
        print(
            f"computed_caption small_fs={small_fs} shape={small_arr.shape} "
            f"large_fs={large_fs} shape={large_arr.shape}",
            flush=True,
        )
        assert small_arr.shape[1] == width
        assert large_arr.shape[1] == width
        assert not _blank_canvas(small_f)
        assert not _blank_canvas(large_f)
        assert large_arr.shape[0] > small_arr.shape[0]


def test_caption_wraps_same_text_narrower_taller():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "wrap_font")
        text = "alpha beta gamma delta epsilon zeta eta"
        color = (255, 255, 255)
        narrow_w = 90
        wide_w = 420
        narrow = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=16,
                method="caption",
                size=(narrow_w, None),
                color=color,
            )
        )
        wide = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=16,
                method="caption",
                size=(wide_w, None),
                color=color,
            )
        )
        nf = as_numeric_array(require_ok(ws.call(narrow.get_frame, 0)))
        wf = as_numeric_array(require_ok(ws.call(wide.get_frame, 0)))
        print(f"wrap narrow={nf.shape} wide={wf.shape}", flush=True)
        assert nf.shape[1] == narrow_w
        assert wf.shape[1] == wide_w
        assert nf.shape[0] > wf.shape[0]


# ---------------------------------------------------------------------------
# H. Alignment, block placement, stroke, margin
# ---------------------------------------------------------------------------


def test_text_align_left_center_right():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "align_font")
        text = "AB\nABCDEFGH"
        color = (255, 255, 255)
        bg = (20, 20, 20)
        box = (320, 110)
        common = dict(
            font=str(font),
            text=text,
            font_size=22,
            color=color,
            bg_color=bg,
            method="caption",
            size=box,
        )
        default = require_ok(ws.call(TextClip, **common))
        left = require_ok(ws.call(TextClip, text_align="left", **common))
        center = require_ok(ws.call(TextClip, text_align="center", **common))
        right = require_ok(ws.call(TextClip, text_align="right", **common))
        df = require_ok(ws.call(default.get_frame, 0))
        lf = require_ok(ws.call(left.get_frame, 0))
        cf = require_ok(ws.call(center.get_frame, 0))
        rf = require_ok(ws.call(right.get_frame, 0))
        assert pictures_equal(df, lf)
        lx, _ = _ink_com(_require_ink(lf, color))
        cx, _ = _ink_com(_require_ink(cf, color))
        rx, _ = _ink_com(_require_ink(rf, color))
        print(f"align com x left={lx:.1f} center={cx:.1f} right={rx:.1f}", flush=True)
        assert not pictures_equal(lf, rf)
        assert lx < rx
        assert not pictures_equal(cf, lf)
        assert not pictures_equal(cf, rf)
        assert lx < cx < rx


def test_text_block_placement_defaults_and_sides():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "place_font")
        text = "Ag"
        color = (255, 255, 255)
        bg = (20, 20, 20)
        box = (300, 140)
        common = dict(
            font=str(font),
            text=text,
            font_size=20,
            color=color,
            bg_color=bg,
            method="caption",
            size=box,
            text_align="left",
        )
        default = require_ok(ws.call(TextClip, **common))
        center = require_ok(
            ws.call(TextClip, horizontal_align="center", vertical_align="center", **common)
        )
        h_left = require_ok(ws.call(TextClip, horizontal_align="left", **common))
        h_right = require_ok(ws.call(TextClip, horizontal_align="right", **common))
        v_top = require_ok(ws.call(TextClip, vertical_align="top", **common))
        v_bottom = require_ok(ws.call(TextClip, vertical_align="bottom", **common))
        df = require_ok(ws.call(default.get_frame, 0))
        cf = require_ok(ws.call(center.get_frame, 0))
        assert pictures_equal(df, cf)
        lx, _ = _ink_com(_require_ink(require_ok(ws.call(h_left.get_frame, 0)), color))
        cx, cy = _ink_com(_require_ink(cf, color))
        rx, _ = _ink_com(_require_ink(require_ok(ws.call(h_right.get_frame, 0)), color))
        _, ty = _ink_com(_require_ink(require_ok(ws.call(v_top.get_frame, 0)), color))
        _, by = _ink_com(_require_ink(require_ok(ws.call(v_bottom.get_frame, 0)), color))
        print(
            f"place x L={lx:.1f} C={cx:.1f} R={rx:.1f} y T={ty:.1f} C={cy:.1f} B={by:.1f}",
            flush=True,
        )
        assert lx < rx
        assert lx < cx < rx
        assert ty < by
        assert ty < cy < by
        assert not pictures_equal(
            require_ok(ws.call(h_left.get_frame, 0)),
            require_ok(ws.call(h_right.get_frame, 0)),
        )
        assert not pictures_equal(
            require_ok(ws.call(v_top.get_frame, 0)),
            require_ok(ws.call(v_bottom.get_frame, 0)),
        )


def test_text_stroke_outline_distinct():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "stroke_font")
        text = "Stroke"
        fill = (255, 255, 255)
        stroke = (220, 30, 30)
        bg = (10, 10, 80)
        box = (280, 90)
        common = dict(
            font=str(font),
            text=text,
            font_size=28,
            color=fill,
            bg_color=bg,
            method="caption",
            size=box,
            stroke_color=stroke,
        )
        none = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text=text,
                font_size=28,
                color=fill,
                bg_color=bg,
                method="caption",
                size=box,
            )
        )
        w1 = 2
        w2 = 5
        thin = require_ok(ws.call(TextClip, stroke_width=w1, **common))
        thick = require_ok(ws.call(TextClip, stroke_width=w2, **common))
        nf = require_ok(ws.call(none.get_frame, 0))
        tf = require_ok(ws.call(thin.get_frame, 0))
        kf = require_ok(ws.call(thick.get_frame, 0))
        print(
            f"stroke distinct_none={not pictures_equal(nf, tf)} "
            f"widths_distinct={not pictures_equal(tf, kf)}",
            flush=True,
        )
        assert not pictures_equal(nf, tf)
        assert not pictures_equal(tf, kf)
        _require_ink(tf, fill, atol=50.0)
        stroke_mask = _near_color_mask(tf, stroke, atol=50.0)
        text_mask = _near_color_mask(tf, fill, atol=50.0)
        assert np.any(stroke_mask)
        assert np.any(text_mask)
        h, w = stroke_mask.shape
        adjacent = False
        rows, cols = np.nonzero(stroke_mask)
        for y, x in zip(rows.tolist(), cols.tolist()):
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and text_mask[ny, nx]:
                    adjacent = True
                    break
            if adjacent:
                break
        print(f"stroke_text_adjacent={adjacent}", flush=True)
        assert adjacent


def test_text_margin_pair_and_quadruple_accepted():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "margin_font")
        kwargs = dict(font=str(font), text="Pad", font_size=20, color=(255, 255, 255))
        pair = require_ok(ws.call(TextClip, margin=(8, 4), **kwargs))
        quad = require_ok(ws.call(TextClip, margin=(2, 3, 6, 7), **kwargs))
        pf = require_ok(ws.call(pair.get_frame, 0))
        qf = require_ok(ws.call(quad.get_frame, 0))
        print(
            f"margin_pair_shape={as_numeric_array(pf).shape} "
            f"quad_shape={as_numeric_array(qf).shape}",
            flush=True,
        )
        assert as_numeric_array(pf).shape[0] > 0
        assert as_numeric_array(qf).shape[0] > 0
        assert not _blank_canvas(pf)
        assert not _blank_canvas(qf)


# ---------------------------------------------------------------------------
# I. Image sequence
# ---------------------------------------------------------------------------


def test_sequence_two_images_one_fps_oracle():
    with workspace() as ws:
        a = _solid(12, 16, (255, 0, 0))
        b = _solid(12, 16, (0, 255, 0))
        clip = require_ok(ws.call(ImageSequenceClip, [a, b], fps=1))
        print(f"seq_oracle duration={clip.duration}", flush=True)
        assert clip.duration == pytest.approx(2)
        assert pictures_equal(require_ok(ws.call(clip.get_frame, 0)), a)
        assert pictures_equal(require_ok(ws.call(clip.get_frame, 1)), b)


def test_sequence_file_list_keeps_given_order():
    with workspace() as ws:
        height, width = 10, 14
        first_color = _rgb()
        second_color = _rgb_away_from(first_color)
        zebra = _write_rgb(
            ws.resolve("zebra.png"), _solid(height, width, first_color), "PNG"
        )
        apple = _write_rgb(
            ws.resolve("apple.png"), _solid(height, width, second_color), "PNG"
        )
        clip = require_ok(
            ws.call(ImageSequenceClip, [str(zebra), str(apple)], fps=2)
        )
        t0 = require_ok(ws.call(clip.get_frame, 0))
        print(f"list_order t0 matches first={pictures_equal(t0, _solid(height, width, first_color))}", flush=True)
        require_rgb_picture(t0, height, width, color=first_color)
        assert not pictures_equal(t0, _solid(height, width, second_color))


def test_sequence_folder_alphanumerical_order():
    with workspace() as ws:
        height, width = 10, 14
        created_first = _rgb()
        alpha_first = _rgb_away_from(created_first)
        folder = ws.resolve("seq_dir")
        folder.mkdir()
        _write_rgb(
            folder / "z_created_first.png", _solid(height, width, created_first), "PNG"
        )
        _write_rgb(
            folder / "a_alpha_first.png", _solid(height, width, alpha_first), "PNG"
        )
        clip = require_ok(ws.call(ImageSequenceClip, str(folder), fps=2))
        t0 = require_ok(ws.call(clip.get_frame, 0))
        print("folder_t0 uses alphanumerical first name", flush=True)
        require_rgb_picture(t0, height, width, color=alpha_first)
        assert not pictures_equal(t0, _solid(height, width, created_first))


def test_sequence_arrays_duration_is_sum():
    with workspace() as ws:
        height, width = 8, 12
        first = _solid(height, width, _rgb())
        second = _solid(height, width, _rgb_away_from(tuple(int(x) for x in first[0, 0])))
        d0 = 0.25
        d1 = 0.75
        clip = require_ok(
            ws.call(ImageSequenceClip, [first, second], durations=[d0, d1])
        )
        print(f"durations_sum={clip.duration} expected={d0 + d1}", flush=True)
        assert clip.duration == pytest.approx(d0 + d1)
        assert pictures_equal(require_ok(ws.call(clip.get_frame, d0 / 2.0)), first)
        assert pictures_equal(
            require_ok(ws.call(clip.get_frame, d0 + d1 / 2.0)), second
        )


def test_sequence_fps_duration_is_n_over_rate():
    with workspace() as ws:
        height, width = 8, 12
        n = 3
        rate = float(_rand_int(4, 10))
        frames = [
            _solid(height, width, _rgb()) if i == 0 else _solid(height, width, _rgb())
            for i in range(n)
        ]
        frames[1] = _solid(height, width, _rgb_away_from(tuple(int(x) for x in frames[0][0, 0])))
        clip = require_ok(ws.call(ImageSequenceClip, frames, fps=rate))
        print(f"fps_duration={clip.duration} N/R={n / rate}", flush=True)
        assert clip.duration == pytest.approx(n / rate)
        assert pictures_equal(require_ok(ws.call(clip.get_frame, 0)), frames[0])


def test_sequence_png_alpha_mask_when_left_on():
    with workspace() as ws:
        width, height = _rect_size()
        color = _rgb()
        rgb = _solid(height, width, color)
        alpha = np.zeros((height, width), dtype=np.uint8)
        alpha[:, width // 2 :] = 255
        path_a = _write_rgba_png(ws.resolve("seq_a.png"), rgb, alpha)
        path_b = _write_rgba_png(
            ws.resolve("seq_b.png"), _solid(height, width, _rgb_away_from(color)), alpha
        )
        expected = alpha.astype(float) / 255.0
        on = require_ok(
            ws.call(ImageSequenceClip, [str(path_a), str(path_b)], fps=2)
        )
        off = require_ok(
            ws.call(
                ImageSequenceClip,
                [str(path_a), str(path_b)],
                fps=2,
                with_mask=False,
            )
        )
        on_mask = _attached_mask_frame(ws, on)
        off_mask = _attached_mask_frame(ws, off)
        print(
            f"seq_alpha on={on_mask is not None} off_matches="
            f"{off_mask is not None and np.allclose(off_mask, expected, atol=0.05)}",
            flush=True,
        )
        assert on_mask is not None
        require_mask_picture(on_mask, height, width)
        assert np.allclose(on_mask, expected, atol=1.0 / 255.0 + 1e-6)
        if off_mask is not None:
            require_mask_picture(off_mask, height, width)
            assert not np.allclose(off_mask, expected, atol=0.05)


def test_sequence_requires_fps_or_durations():
    with workspace() as ws:
        a = _solid(8, 10, _rgb())
        b = _solid(8, 10, _rgb())
        failed = ws.call(ImageSequenceClip, [a, b])
        print(f"seq_no_timing_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        sibling = require_ok(ws.call(ImageSequenceClip, [a, b], fps=2))
        assert sibling.duration == pytest.approx(1.0)


def test_sequence_mixed_sizes_does_not_succeed():
    with workspace() as ws:
        a = _solid(8, 10, _rgb())
        b = _solid(12, 10, _rgb())
        failed_arr = ws.call(ImageSequenceClip, [a, b], fps=2)
        print(f"mixed_array_failed={failed_arr.exception is not None}", flush=True)
        require_failed(failed_arr)
        pa = _write_rgb(ws.resolve("mix_a.png"), a, "PNG")
        pb = _write_rgb(ws.resolve("mix_b.png"), b, "PNG")
        failed_file = ws.call(ImageSequenceClip, [str(pa), str(pb)], fps=2)
        require_failed(failed_file)
        sibling = require_ok(
            ws.call(ImageSequenceClip, [a, _solid(8, 10, _rgb())], fps=2)
        )
        require_rgb_picture(require_ok(ws.call(sibling.get_frame, 0)), 8, 10)


# ---------------------------------------------------------------------------
# J. Generated video
# ---------------------------------------------------------------------------


def test_generated_video_frame_is_function_at_t():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        duration = 3.0
        clip = require_ok(ws.call(VideoClip, frame_function=fn, duration=duration))
        oracle_0 = require_ok(ws.call(clip.get_frame, 0))
        oracle_half = require_ok(ws.call(clip.get_frame, 0.5))
        print(
            f"gen_oracle distinct={not pictures_equal(oracle_0, oracle_half)}",
            flush=True,
        )
        assert pictures_equal(oracle_0, fn(0))
        assert pictures_equal(oracle_half, fn(0.5))
        assert not pictures_equal(oracle_0, oracle_half)

        base = float(_rand_int(1, 3))
        t0 = base + 0.15
        t1 = base + 0.65
        f0 = require_ok(ws.call(clip.get_frame, t0))
        f1 = require_ok(ws.call(clip.get_frame, t1))
        print(f"gen_runtime t0={t0} t1={t1}", flush=True)
        assert pictures_equal(f0, fn(t0))
        assert pictures_equal(f1, fn(t1))
        assert not pictures_equal(f0, f1)
        assert not pictures_equal(f0, fn(int(t0)))


def test_generated_video_finite_only_when_duration_supplied():
    with workspace() as ws:
        width, height = _rect_size()
        fn = _time_picture(height, width)
        infinite = require_ok(ws.call(VideoClip, frame_function=fn))
        duration = 0.6 + _rand_int(1, 5) / 10.0
        finite = require_ok(ws.call(VideoClip, frame_function=fn, duration=duration))
        print(
            f"gen_D absent={infinite.duration} supplied={finite.duration}",
            flush=True,
        )
        assert infinite.duration is None
        assert finite.duration == pytest.approx(duration)
        require_rgb_picture(require_ok(ws.call(infinite.get_frame, 0.2)), height, width)


# ---------------------------------------------------------------------------
# K. Generated and array audio
# ---------------------------------------------------------------------------


def test_generated_audio_channels_from_time_zero():
    with workspace() as ws:
        duration = 0.8

        def mono(t):
            return np.array([np.sin(2.0 * np.pi * 5.5 * t) + 0.2 * t], dtype=float)

        def stereo(t):
            return np.array(
                [
                    np.sin(2.0 * np.pi * 5.5 * t),
                    np.sin(2.0 * np.pi * 8.0 * t) + 0.1 * t,
                ],
                dtype=float,
            )

        mono_clip = require_ok(
            ws.call(AudioClip, frame_function=mono, duration=duration)
        )
        stereo_clip = require_ok(
            ws.call(AudioClip, frame_function=stereo, duration=duration)
        )
        m0 = require_sound_frame(require_ok(ws.call(mono_clip.get_frame, 0.3)), 1)
        s0 = require_sound_frame(require_ok(ws.call(stereo_clip.get_frame, 0.3)), 2)
        t0 = 1.15
        t1 = 1.65
        # keep times inside duration by using a longer clip for the fractional pair
        long_mono = require_ok(ws.call(AudioClip, frame_function=mono, duration=2.5))
        a = require_sound_frame(require_ok(ws.call(long_mono.get_frame, t0)), 1)
        b = require_sound_frame(require_ok(ws.call(long_mono.get_frame, t1)), 1)
        print(
            f"gen_audio mono={m0.shape} stereo={s0.shape} t0={t0} t1={t1}",
            flush=True,
        )
        assert not samples_close(a, b)
        assert samples_close(a, mono(t0))
        assert samples_close(b, mono(t1))
        assert long_mono.duration == pytest.approx(2.5)
        assert mono_clip.duration == pytest.approx(duration)

        later_t = 0.45

        def mono_at_zero_stereo_later(t):
            if float(t) == 0.0:
                return np.array([0.31], dtype=float)
            return np.array([0.31, -0.17], dtype=float)

        def stereo_at_zero_mono_later(t):
            if float(t) == 0.0:
                return np.array([0.22, -0.41], dtype=float)
            return np.array([0.22], dtype=float)

        locked_mono = require_ok(
            ws.call(
                AudioClip,
                frame_function=mono_at_zero_stereo_later,
                duration=duration,
            )
        )
        locked_stereo = require_ok(
            ws.call(
                AudioClip,
                frame_function=stereo_at_zero_mono_later,
                duration=duration,
            )
        )
        require_sound_frame(require_ok(ws.call(locked_mono.get_frame, 0)), 1)
        require_sound_frame(require_ok(ws.call(locked_stereo.get_frame, 0)), 2)
        require_ok(ws.call(locked_mono.get_frame, later_t))
        require_ok(ws.call(locked_stereo.get_frame, later_t))
        print(
            f"channel_lock later_t={later_t} "
            f"mono_nchannels={locked_mono.nchannels} "
            f"stereo_nchannels={locked_stereo.nchannels}",
            flush=True,
        )
        assert locked_mono.nchannels == 1
        assert locked_stereo.nchannels == 2


def _time_inside_sample(index: int, rate: float) -> float:
    """A time strictly inside sample *index*, not on the i/R bin edge.

    t = i/R sits on the slot boundary: converting that instant to an
    index can land on i-1 under ordinary floating-point. L152 requires
    that samples play in order, not that get_frame(i/R) equals
    source[i]. A quarter-slot offset stays in the same sample for both
    truncation and rounding of rate*t.
    """
    return (float(index) + 0.25) / float(rate)


def test_array_audio_duration_n_over_rate_and_roundtrip():
    with workspace() as ws:
        n = _rand_int(10, 18)
        rate = float(_rand_int(8, 16) * 1000)
        stereo = np.column_stack(
            (
                np.linspace(-0.4, 0.5, n),
                np.linspace(0.2, -0.3, n),
            )
        )
        clip = require_ok(ws.call(AudioArrayClip, stereo, rate))
        print(f"array_audio N={n} R={rate} D={clip.duration}", flush=True)
        assert clip.duration == pytest.approx(n / rate)
        first = require_sound_frame(require_ok(ws.call(clip.get_frame, 0)), 2)
        last_t = _time_inside_sample(n - 1, rate)
        last = require_sound_frame(
            require_ok(ws.call(clip.get_frame, last_t)), 2
        )
        assert samples_close(first, stereo[0])
        assert samples_close(last, stereo[-1])
        interior = _rand_int(1, n - 2)
        interior_t = _time_inside_sample(interior, rate)
        mid = require_sound_frame(
            require_ok(ws.call(clip.get_frame, interior_t)), 2
        )
        print(
            f"interior_i={interior} interior_t={interior_t} last_t={last_t}",
            flush=True,
        )
        assert samples_close(mid, stereo[interior])
        roundtrip = as_numeric_array(require_ok(ws.call(clip.to_soundarray)))
        print(f"roundtrip_shape={roundtrip.shape} n={n}", flush=True)
        recovered = np.asarray(roundtrip, dtype=float)
        if recovered.ndim != 2 or recovered.shape[1] != 2:
            raise AssertionError(
                f"converted array is not stereo N×2; shape={roundtrip.shape}"
            )
        # L163: converting back round-trips those samples within ordinary
        # numeric tolerance. That is a value contract, not an exact length.
        # Sampling duration N/R at rate R may include one extra instant.
        assert n <= recovered.shape[0] <= n + 1
        assert np.allclose(recovered[:n], stereo, rtol=1e-5, atol=1e-6)

        mono_n = _rand_int(8, 14)
        mono_rate = float(_rand_int(9, 15) * 1000)
        mono = (np.linspace(-0.5, 0.6, mono_n)).reshape(mono_n, 1)
        mono_clip = require_ok(ws.call(AudioArrayClip, mono, mono_rate))
        assert mono_clip.duration == pytest.approx(mono_n / mono_rate)
        i = _rand_int(1, mono_n - 2)
        mono_t = _time_inside_sample(i, mono_rate)
        sample = require_sound_frame(
            require_ok(ws.call(mono_clip.get_frame, mono_t)), 1
        )
        print(f"mono_i={i} mono_t={mono_t}", flush=True)
        assert samples_close(sample, mono[i])


# ---------------------------------------------------------------------------
# L. Remaining refusals
# ---------------------------------------------------------------------------


def test_text_without_string_or_file_does_not_succeed():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "missing_text_font")
        failed = ws.call(TextClip, font=str(font), font_size=20)
        print(f"no_text_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        sibling = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="Present",
                font_size=20,
                color=(255, 255, 255),
            )
        )
        assert not _blank_canvas(require_ok(ws.call(sibling.get_frame, 0)))


def test_text_layout_other_than_label_or_caption_does_not_succeed():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "method_font")
        other = f"layout_{secrets.token_hex(3)}"
        failed = ws.call(
            TextClip,
            font=str(font),
            text="X",
            font_size=18,
            method=other,
            color=(255, 255, 255),
        )
        print(f"other_method={other!r} failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        label = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="X",
                font_size=18,
                method="label",
                color=(255, 255, 255),
            )
        )
        caption = require_ok(
            ws.call(
                TextClip,
                font=str(font),
                text="X",
                font_size=18,
                method="caption",
                size=(160, None),
                color=(255, 255, 255),
            )
        )
        assert not _blank_canvas(require_ok(ws.call(label.get_frame, 0)))
        assert as_numeric_array(require_ok(ws.call(caption.get_frame, 0))).shape[1] == 160


def test_unopenable_font_path_does_not_succeed():
    with workspace() as ws:
        width, height = 8, 8
        png = _write_rgb(ws.resolve("not_font.png"), _solid(height, width, _rgb()), "PNG")
        fake = ws.resolve("not_font.ttf")
        fake.write_bytes(png.read_bytes())
        failed = ws.call(
            TextClip,
            font=str(fake),
            text="Hi",
            font_size=18,
            color=(255, 255, 255),
        )
        print(f"unopenable_font_failed={failed.exception is not None}", flush=True)
        require_failed(failed)
        real = _copy_font(ws, find_opentype_fonts(1)[0], "openable")
        sibling = require_ok(
            ws.call(
                TextClip,
                font=str(real),
                text="Hi",
                font_size=18,
                color=(255, 255, 255),
            )
        )
        assert not _blank_canvas(require_ok(ws.call(sibling.get_frame, 0)))


def test_margin_not_pair_or_quadruple_does_not_succeed():
    with workspace() as ws:
        font = _copy_font(ws, find_opentype_fonts(1)[0], "bad_margin_font")
        kwargs = dict(
            font=str(font), text="M", font_size=18, color=(255, 255, 255)
        )
        scalar = ws.call(TextClip, margin=6, **kwargs)
        triple = ws.call(TextClip, margin=(1, 2, 3), **kwargs)
        print(
            f"margin_scalar_failed={scalar.exception is not None} "
            f"triple_failed={triple.exception is not None}",
            flush=True,
        )
        require_failed(scalar)
        require_failed(triple)
        pair = require_ok(ws.call(TextClip, margin=(4, 2), **kwargs))
        quad = require_ok(ws.call(TextClip, margin=(1, 2, 3, 4), **kwargs))
        assert not _blank_canvas(require_ok(ws.call(pair.get_frame, 0)))
        assert not _blank_canvas(require_ok(ws.call(quad.get_frame, 0)))


# ---------------------------------------------------------------------------
# M. Constructors do not require the encoder
# ---------------------------------------------------------------------------


def test_constructors_succeed_when_encoder_unreachable():
    with workspace() as ws:
        width, height = 12, 10
        still_color = (20, 180, 90)
        seq_a = (200, 30, 30)
        seq_b = (30, 30, 200)
        _write_rgb(ws.resolve("enc_still.png"), _solid(height, width, still_color), "PNG")
        _write_rgb(ws.resolve("enc_seq0.png"), _solid(height, width, seq_a), "PNG")
        _write_rgb(ws.resolve("enc_seq1.png"), _solid(height, width, seq_b), "PNG")
        code = f"""
import numpy as np
from clipkit import (
    AudioArrayClip,
    ColorClip,
    ImageClip,
    ImageSequenceClip,
    TextClip,
    VideoClip,
)

width, height = {width}, {height}
still_color = {still_color}
seq_a = {seq_a}

color = ColorClip((width, height), color=still_color)
cf = np.asarray(color.get_frame(0))
assert cf.shape == (height, width, 3)
assert np.allclose(cf.astype(float), np.asarray(still_color, dtype=float).reshape(1, 1, 3), atol=0.5)

arr = np.zeros((height, width, 3), dtype=np.uint8)
arr[:, :] = (40, 50, 60)
still_arr = ImageClip(arr)
sf = np.asarray(still_arr.get_frame(0))
assert np.array_equal(sf, arr)

a = np.zeros((height, width, 3), dtype=np.uint8)
a[:, :] = (10, 20, 30)
b = np.zeros((height, width, 3), dtype=np.uint8)
b[:, :] = (70, 80, 90)
seq_arr = ImageSequenceClip([a, b], fps=2)
assert np.array_equal(np.asarray(seq_arr.get_frame(0)), a)

def fn(t):
    pic = np.zeros((height, width, 3), dtype=np.uint8)
    pic[:, :, 0] = int(min(255, t * 80))
    pic[:, :, 1] = 40
    pic[:, :, 2] = 50
    return pic

gen = VideoClip(frame_function=fn, duration=0.5)
gf = np.asarray(gen.get_frame(0.25))
assert np.array_equal(gf, fn(0.25))

pcm = np.linspace(-0.3, 0.4, 12).reshape(12, 1)
audio = AudioArrayClip(pcm, 8000)
assert abs(audio.duration - 12 / 8000) < 1e-9

text = TextClip(text="Hi", font_size=18, color=(255, 255, 255))
tf = np.asarray(text.get_frame(0))
assert tf.size > 0
assert not np.allclose(tf[:, :, :3].astype(float), 0.0, atol=1.0)

file_still = ImageClip("enc_still.png")
ff = np.asarray(file_still.get_frame(0))
assert ff.shape[0] == height and ff.shape[1] == width
assert np.allclose(ff[:, :, :3].astype(float), np.asarray(still_color, dtype=float).reshape(1, 1, 3), atol=0.5)

file_seq = ImageSequenceClip(["enc_seq0.png", "enc_seq1.png"], fps=1)
seq0 = np.asarray(file_seq.get_frame(0))
assert np.allclose(seq0[:, :, :3].astype(float), np.asarray(seq_a, dtype=float).reshape(1, 1, 3), atol=0.5)
print("encoder_unreachable_constructors_ok")
"""
        unreachable = ws.run_python(code=code, encoder_reachable=False, timeout=60.0)
        print(
            f"unreachable rc={unreachable.returncode} "
            f"stderr={unreachable.stderr_text[:800]!r}",
            flush=True,
        )
        assert unreachable.returncode == 0
        assert "encoder_unreachable_constructors_ok" in unreachable.stdout_text

        reachable = ws.run_python(code=code, encoder_reachable=True, timeout=60.0)
        print(f"reachable rc={reachable.returncode}", flush=True)
        assert reachable.returncode == 0
        assert "encoder_unreachable_constructors_ok" in reachable.stdout_text
