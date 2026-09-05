# feature: F08
"""Built-in effects and caller-defined transformations (FP-08).

Assertions stay at the PRD's precision: copy-on-apply and list order,
the 34+7 catalogs, mask/soundtrack alignment vs color-only vs overlay-only,
oracles (invert red→cyan, speed×2, volume 0.5, fade-in, cross-fade overlay,
channel-swap, progress bar), time/picture/joint filters, and the listed
refusals. Exception types, failure wording, easing curves, byte polynomials,
blur kernels, and pixel-displacement tables are not pinned.
"""

from __future__ import annotations

import secrets

import numpy as np
from clipkit import (
    AudioClip,
    ColorClip,
    CompositeVideoClip,
    Effect,
    ImageClip,
    VideoClip,
    afx,
    vfx,
)

from _harness import workspace
from _helpers import (
    as_numeric_array,
    pictures_equal,
    require_failed,
    require_mask_picture,
    require_ok,
    require_rgb_picture,
    require_sound_frame,
    samples_close,
)
from F08_helpers import apply_effects, duration_or_missing, progress_bar_effect

_RED = (255, 0, 0)
_GREEN = (0, 255, 0)
_BLUE = (0, 0, 255)
_CYAN = (0, 255, 255)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_PCM_RATE = 22050

_VISUAL_NAMES = (
    "AccelDecel",
    "BlackAndWhite",
    "Blink",
    "Crop",
    "CrossFadeIn",
    "CrossFadeOut",
    "EvenSize",
    "FadeIn",
    "FadeOut",
    "Freeze",
    "FreezeRegion",
    "GammaCorrection",
    "HeadBlur",
    "InvertColors",
    "Loop",
    "LumContrast",
    "MakeLoopable",
    "Margin",
    "MasksAnd",
    "MaskColor",
    "MasksOr",
    "MirrorX",
    "MirrorY",
    "MultiplyColor",
    "MultiplySpeed",
    "Painting",
    "Resize",
    "Rotate",
    "Scroll",
    "SlideIn",
    "SlideOut",
    "SuperSample",
    "TimeMirror",
    "TimeSymmetrize",
)

_AUDIO_NAMES = (
    "AudioDelay",
    "AudioFadeIn",
    "AudioFadeOut",
    "AudioLoop",
    "AudioNormalize",
    "MultiplyStereoVolume",
    "MultiplyVolume",
)


def _rand_int(lo: int, hi: int) -> int:
    return lo + secrets.randbelow(hi - lo + 1)


def _even(lo: int, hi: int) -> int:
    return _rand_int(lo, hi) * 2


def _rgb() -> tuple[int, int, int]:
    return (_rand_int(30, 220), _rand_int(30, 220), _rand_int(30, 220))


def _l1(a, b) -> int:
    return sum(abs(int(x) - int(y)) for x, y in zip(a, b))


def _rgb_away_from(*others: tuple[int, int, int]) -> tuple[int, int, int]:
    banned = others + (_BLACK,)
    for _ in range(80):
        candidate = _rgb()
        if all(_l1(candidate, other) > 90 for other in banned):
            return candidate
    for candidate in (_RED, _GREEN, _BLUE, (255, 255, 0), (255, 0, 255), _CYAN, _WHITE):
        if all(_l1(candidate, other) > 90 for other in banned):
            return candidate
    raise AssertionError(f"could not pick a color away from {banned}")


def _scalar_t(t) -> float:
    return float(np.asarray(t).reshape(-1)[0])


def _frame(ws, clip, t=0.0):
    return require_ok(ws.call(clip.get_frame, t))


def _color(ws, size, color, duration=None, *, is_mask=False):
    kwargs = {"color": color}
    if is_mask:
        kwargs["is_mask"] = True
    clip = require_ok(ws.call(ColorClip, size, **kwargs))
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
    arr = np.ascontiguousarray(picture, dtype=np.uint8)
    if duration is None:
        return require_ok(ws.call(ImageClip, arr))
    return require_ok(ws.call(ImageClip, arr, duration=duration))


def _overlay(ws, clips, **kwargs):
    return require_ok(ws.call(CompositeVideoClip, list(clips), **kwargs))


def _audio(ws, fn, duration, *, fps=_PCM_RATE):
    return require_ok(
        ws.call(AudioClip, frame_function=fn, duration=duration, fps=fps)
    )


def _const_mono(amp: float):
    def frame_function(t):
        return amp * np.ones(np.shape(np.asarray(t)))

    return frame_function


def _const_stereo(left: float, right: float):
    def frame_function(t):
        tt = np.asarray(t, dtype=float)
        if tt.ndim == 0:
            return np.array([left, right], dtype=float)
        z = np.ones(np.shape(tt), dtype=float)
        return np.column_stack([left * z, right * z])

    return frame_function


def _pulse_mono(amp: float, width: float):
    def frame_function(t):
        return amp * (np.asarray(t, dtype=float) < width)

    return frame_function


def _sound(ws, clip, t, channels=1):
    return require_sound_frame(_frame(ws, clip, t), channels)


def _pcm_at(ws, clip, t, *, n=24):
    """Fetch a short sample vector. Some audio filters only accept array times."""
    fps = getattr(clip, "fps", None)
    if fps is None or float(fps) <= 0:
        fps = _PCM_RATE
    tt = float(t) + np.arange(int(n), dtype=float) / float(fps)
    raw = require_ok(ws.call(clip.get_frame, tt))
    arr = as_numeric_array(raw).astype(float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.shape[0] < 1:
        raise AssertionError("audio get_frame produced no samples")
    return arr


def _with_fps(ws, clip, fps=10):
    return require_ok(ws.call(clip.with_fps, fps))


def _soundtrack(ws, clip, t, channels=1):
    audio = clip.audio
    if audio is None:
        raise AssertionError("clip has no soundtrack; missing audio is not silence")
    return _sound(ws, audio, t, channels)


def _attach_audio(ws, clip, audio):
    return require_ok(ws.call(clip.with_audio, audio))


def _attach_mask(ws, clip, mask):
    return require_ok(ws.call(clip.with_mask, mask))


def _picture_rgb(frame) -> np.ndarray:
    arr = as_numeric_array(frame)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise AssertionError(
            f"expected a picture with at least 3 channels; got shape {arr.shape}"
        )
    return arr[:, :, :3]


def _rgb_at(frame, x: int, y: int) -> tuple[int, int, int]:
    pix = _picture_rgb(frame)[y, x]
    return (int(round(pix[0])), int(round(pix[1])), int(round(pix[2])))


def _near(got, color, atol: int = 18) -> bool:
    return all(abs(int(a) - int(b)) <= atol for a, b in zip(got, color))


def _assert_color_at(frame, x, y, color, atol: int = 18):
    got = _rgb_at(frame, x, y)
    if not _near(got, color, atol=atol):
        raise AssertionError(
            f"pixel ({x},{y})={got} not within {atol} of {color}"
        )


def _frame_size(frame) -> tuple[int, int]:
    arr = as_numeric_array(frame)
    if arr.ndim < 2:
        raise AssertionError(f"frame has no spatial axes; shape={arr.shape!r}")
    return int(arr.shape[1]), int(arr.shape[0])


def _mean_rgb(frame) -> float:
    return float(_picture_rgb(frame).astype(float).mean())


def _channel_spread(frame) -> float:
    arr = _picture_rgb(frame).astype(float)
    return float((arr.max(axis=-1) - arr.min(axis=-1)).mean())


def _luminance(color) -> float:
    r, g, b = color
    return 0.3 * r + 0.6 * g + 0.1 * b


def _solid(h, w, color) -> np.ndarray:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[...] = color
    return arr


def _lr_picture(h, w, left, right) -> np.ndarray:
    pic = _solid(h, w, right)
    pic[:, : w // 2] = left
    return pic


def _tb_picture(h, w, top, bottom) -> np.ndarray:
    pic = _solid(h, w, bottom)
    pic[: h // 2, :] = top
    return pic


def _lr_mask(h, w, left=1.0, right=0.0) -> np.ndarray:
    mask = np.full((h, w), float(right), dtype=float)
    mask[:, : w // 2] = float(left)
    return mask


def _tb_mask(h, w, top=1.0, bottom=0.0) -> np.ndarray:
    mask = np.full((h, w), float(bottom), dtype=float)
    mask[: h // 2, :] = float(top)
    return mask


def _two_tone(ws, size, first, second, split, duration, *, is_mask=False):
    w, h = size

    def fn(t, first=first, second=second, split=split, h=h, w=w, is_mask=is_mask):
        tt = _scalar_t(t)
        value = first if tt < split else second
        if is_mask:
            return np.full((h, w), float(value), dtype=float)
        return np.full((h, w, 3), value, dtype=np.uint8)

    return _video(ws, fn, duration, is_mask=is_mask)


def _no_soundtrack(clip) -> bool:
    return clip.audio is None


# ---------------------------------------------------------------------------
# A. Copy, list order, independent apply
# ---------------------------------------------------------------------------


class TestF08_applying_effects_returns_copy:
    def test_applying_effects_returns_copy(self):
        with workspace() as ws:
            source = _color(ws, (12, 10), _RED, duration=0.8)
            result = apply_effects(ws, source, [vfx.InvertColors()])
            src_frame = _frame(ws, source, 0.0)
            out_frame = _frame(ws, result, 0.0)
            print(
                f"copy src={_rgb_at(src_frame, 1, 1)} out={_rgb_at(out_frame, 1, 1)} "
                f"same_object={result is source}",
                flush=True,
            )
            require_rgb_picture(src_frame, 10, 12, color=_RED)
            require_rgb_picture(out_frame, 10, 12, color=_CYAN)
            assert result is not source
            assert not pictures_equal(src_frame, out_frame)


def test_effect_list_applies_in_list_order():
    with workspace() as ws:
        color = _rgb_away_from(_RED, _CYAN)
        source = _color(ws, (10, 8), color, duration=0.6)
        invert = vfx.InvertColors()
        dim = vfx.MultiplyColor(0.5)
        listed = apply_effects(ws, source, [invert, dim])
        chained = apply_effects(ws, apply_effects(ws, source, [invert]), [dim])
        swapped = apply_effects(ws, source, [dim, invert])
        swapped_chain = apply_effects(ws, apply_effects(ws, source, [dim]), [invert])
        a = _frame(ws, listed, 0.0)
        b = _frame(ws, chained, 0.0)
        c = _frame(ws, swapped, 0.0)
        d = _frame(ws, swapped_chain, 0.0)
        print(
            f"order listed={_rgb_at(a, 0, 0)} chained={_rgb_at(b, 0, 0)} "
            f"swapped={_rgb_at(c, 0, 0)}",
            flush=True,
        )
        assert pictures_equal(a, b)
        assert pictures_equal(c, d)
        assert not pictures_equal(a, c)


def test_same_effect_object_applies_independently():
    with workspace() as ws:
        invert = vfx.InvertColors()
        green = _color(ws, (8, 8), _GREEN, duration=0.5)
        blue = _color(ws, (8, 8), _BLUE, duration=0.5)
        g_out = apply_effects(ws, green, [invert])
        b_out = apply_effects(ws, blue, [invert])
        print(
            f"independent invert g={_rgb_at(_frame(ws, g_out, 0), 0, 0)} "
            f"b={_rgb_at(_frame(ws, b_out, 0), 0, 0)}",
            flush=True,
        )
        require_rgb_picture(_frame(ws, green, 0.0), 8, 8, color=_GREEN)
        require_rgb_picture(_frame(ws, blue, 0.0), 8, 8, color=_BLUE)
        require_rgb_picture(_frame(ws, g_out, 0.0), 8, 8, color=(255, 0, 255))
        require_rgb_picture(_frame(ws, b_out, 0.0), 8, 8, color=(255, 255, 0))

        final_d = 0.8 + _rand_int(0, 4) / 10.0
        speed = vfx.MultiplySpeed(final_duration=final_d)
        first_c = _rgb_away_from(_BLACK)
        second_c = _rgb_away_from(first_c)
        src_a = _two_tone(ws, (10, 8), first_c, second_c, 0.4, 1.2)
        src_b = _two_tone(ws, (10, 8), first_c, second_c, 0.9, 2.0)
        out_a = apply_effects(ws, src_a, [speed])
        t_obs = final_d * 0.5
        src_ta = t_obs * (1.2 / final_d)
        src_tb = t_obs * (2.0 / final_d)
        before_second = _frame(ws, out_a, t_obs)
        out_b = apply_effects(ws, src_b, [speed])
        da = duration_or_missing(out_a)
        db = duration_or_missing(out_b)
        print(
            f"independent speed D={final_d:.2f} da={da} db={db} "
            f"src_ta={src_ta:.3f} src_tb={src_tb:.3f}",
            flush=True,
        )
        assert da is not None and abs(da - final_d) < 1e-6
        assert db is not None and abs(db - final_d) < 1e-6
        assert pictures_equal(_frame(ws, out_a, t_obs), _frame(ws, src_a, src_ta))
        assert pictures_equal(_frame(ws, out_b, t_obs), _frame(ws, src_b, src_tb))
        assert pictures_equal(_frame(ws, out_a, t_obs), before_second)


# ---------------------------------------------------------------------------
# B. Catalog members exist and apply
# ---------------------------------------------------------------------------


def test_every_listed_visual_catalog_member_is_applicable():
    with workspace() as ws:
        w, h = 16, 14
        duration = 1.0
        rgb = _color(ws, (w, h), _rgb_away_from(), duration=duration)
        mask_a = _color(ws, (w, h), 0.7, duration=duration, is_mask=True)
        mask_b = _color(ws, (w, h), 0.3, duration=duration, is_mask=True)
        odd = _color(ws, (11, 9), _rgb_away_from(), duration=duration)
        cx = lambda t: float(w) / 2.0
        cy = lambda t: float(h) / 2.0
        members = {
            "AccelDecel": vfx.AccelDecel(),
            "BlackAndWhite": vfx.BlackAndWhite(),
            "Blink": vfx.Blink(0.2, 0.2),
            "Crop": vfx.Crop(x1=0, y1=0, x2=w // 2, y2=h),
            "CrossFadeIn": vfx.CrossFadeIn(0.25),
            "CrossFadeOut": vfx.CrossFadeOut(0.25),
            "EvenSize": vfx.EvenSize(),
            "FadeIn": vfx.FadeIn(0.2),
            "FadeOut": vfx.FadeOut(0.2),
            "Freeze": vfx.Freeze(t=0.0, freeze_duration=0.15),
            "FreezeRegion": vfx.FreezeRegion(region=(1, 1, 6, 6)),
            "GammaCorrection": vfx.GammaCorrection(1.0),
            "HeadBlur": vfx.HeadBlur(cx, cy, 3),
            "InvertColors": vfx.InvertColors(),
            "Loop": vfx.Loop(n=2),
            "LumContrast": vfx.LumContrast(),
            "MakeLoopable": vfx.MakeLoopable(0.2),
            "Margin": vfx.Margin(margin_size=1),
            "MasksAnd": vfx.MasksAnd(mask_b),
            "MaskColor": vfx.MaskColor(color=_BLACK),
            "MasksOr": vfx.MasksOr(mask_b),
            "MirrorX": vfx.MirrorX(),
            "MirrorY": vfx.MirrorY(),
            "MultiplyColor": vfx.MultiplyColor(1.0),
            "MultiplySpeed": vfx.MultiplySpeed(1.0),
            "Painting": vfx.Painting(),
            "Resize": vfx.Resize(width=w - 2),
            "Rotate": vfx.Rotate(90),
            "Scroll": vfx.Scroll(x_speed=1),
            "SlideIn": vfx.SlideIn(0.2, "left"),
            "SlideOut": vfx.SlideOut(0.2, "left"),
            "SuperSample": vfx.SuperSample(0.05, 2),
            "TimeMirror": vfx.TimeMirror(),
            "TimeSymmetrize": vfx.TimeSymmetrize(),
        }
        assert tuple(members) == _VISUAL_NAMES
        missing = [name for name in _VISUAL_NAMES if not hasattr(vfx, name)]
        assert not missing, f"visual catalog missing members: {missing}"
        for name in _VISUAL_NAMES:
            effect = members[name]
            target = odd if name == "EvenSize" else mask_a if name in {"MasksAnd", "MasksOr"} else rgb
            applied = apply_effects(ws, target, [effect])
            print(f"visual_catalog {name} ok duration={duration_or_missing(applied)}", flush=True)
            assert applied is not None


def test_every_listed_audio_catalog_member_is_applicable():
    with workspace() as ws:
        missing = [name for name in _AUDIO_NAMES if not hasattr(afx, name)]
        assert not missing, f"audio catalog missing members: {missing}"
        clip = _audio(ws, _const_mono(0.4), 0.6)
        members = {
            "AudioDelay": afx.AudioDelay(offset=0.1, n_repeats=1, decay=0.5),
            "AudioFadeIn": afx.AudioFadeIn(0.15),
            "AudioFadeOut": afx.AudioFadeOut(0.15),
            "AudioLoop": afx.AudioLoop(n_loops=2),
            "AudioNormalize": afx.AudioNormalize(),
            "MultiplyStereoVolume": afx.MultiplyStereoVolume(left=1.0, right=1.0),
            "MultiplyVolume": afx.MultiplyVolume(1.0),
        }
        assert tuple(members) == _AUDIO_NAMES
        stereo = _audio(ws, _const_stereo(0.4, 0.4), 0.6)
        for name in _AUDIO_NAMES:
            target = stereo if name == "MultiplyStereoVolume" else clip
            applied = apply_effects(ws, target, [members[name]])
            print(
                f"audio_catalog {name} ok duration={duration_or_missing(applied)}",
                flush=True,
            )
            assert applied is not None
            if name == "MultiplyStereoVolume":
                pcm = _pcm_at(ws, applied, 0.05)
                assert pcm.shape[1] == 2
            else:
                _sound(ws, applied, 0.02, channels=1)


# ---------------------------------------------------------------------------
# C. Speed, loop, time mirror / symmetrize
# ---------------------------------------------------------------------------


def test_oracle_multiply_speed_by_2_halves_duration():
    with workspace() as ws:
        source = _two_tone(ws, (12, 10), _RED, _GREEN, 2.0, 4.0)
        result = apply_effects(ws, source, [vfx.MultiplySpeed(2)])
        dur = duration_or_missing(result)
        src_at_2 = _frame(ws, source, 2.0)
        out_at_1 = _frame(ws, result, 1.0)
        print(f"speed2 duration={dur} out_t1={_rgb_at(out_at_1, 1, 1)}", flush=True)
        assert dur is not None and abs(dur - 2.0) < 1e-6
        assert pictures_equal(out_at_1, src_at_2)
        assert not pictures_equal(_frame(ws, result, 1.0), _frame(ws, source, 1.0))


def test_multiply_speed_fits_final_duration():
    with workspace() as ws:
        src_d = 1.6 + _rand_int(0, 6) / 10.0
        final_d = 0.7 + _rand_int(0, 4) / 10.0
        split = src_d * 0.45
        first, second = _rgb_away_from(), None
        second = _rgb_away_from(first)
        source = _two_tone(ws, (10, 8), first, second, split, src_d)
        result = apply_effects(ws, source, [vfx.MultiplySpeed(final_duration=final_d)])
        dur = duration_or_missing(result)
        t = final_d * 0.5
        src_t = t * (src_d / final_d)
        print(f"speed_fit src_d={src_d:.2f} D={final_d:.2f} src_t={src_t:.3f}", flush=True)
        assert dur is not None and abs(dur - final_d) < 1e-6
        assert pictures_equal(_frame(ws, result, t), _frame(ws, source, src_t))


def test_multiply_speed_aligns_mask_and_soundtrack():
    with workspace() as ws:
        w, h = 12, 10
        source = _two_tone(ws, (w, h), _RED, _GREEN, 2.0, 4.0)
        mask = _two_tone(ws, (w, h), 0.2, 0.9, 2.0, 4.0, is_mask=True)
        audio = _audio(ws, lambda t: 0.2 + 0.6 * (np.asarray(t) >= 2.0), 4.0)
        source = _attach_mask(ws, source, mask)
        source = _attach_audio(ws, source, audio)
        result = apply_effects(ws, source, [vfx.MultiplySpeed(2)])
        out_mask = require_mask_picture(_frame(ws, result.mask, 1.0), h, w)
        src_mask = require_mask_picture(_frame(ws, source.mask, 2.0), h, w)
        out_s = _soundtrack(ws, result, 1.0)
        src_s = _soundtrack(ws, source, 2.0)
        print(
            f"speed_align mask_out={float(out_mask.mean()):.3f} "
            f"mask_src={float(src_mask.mean()):.3f} s_out={float(out_s[0]):.3f}",
            flush=True,
        )
        assert pictures_equal(out_mask, src_mask)
        assert samples_close(out_s, src_s)


def test_multiply_speed_without_factor_or_final_duration_does_not_succeed():
    with workspace() as ws:
        source = _color(ws, (8, 8), _rgb_away_from(), duration=1.0)
        ok = apply_effects(ws, source, [vfx.MultiplySpeed(2)])
        assert duration_or_missing(ok) is not None
        failed = ws.call(source.with_effects, [vfx.MultiplySpeed()])
        print(f"speed_missing_args failed={failed.exception is not None}", flush=True)
        require_failed(failed)


class TestF08_loop_without_count_or_total_duration_has_no_duration:
    def test_loop_without_count_or_total_duration_has_no_duration(self):
        with workspace() as ws:
            first, second = _rgb_away_from(), None
            second = _rgb_away_from(first)
            source = _two_tone(ws, (10, 8), first, second, 0.4, 0.8)
            result = apply_effects(ws, source, [vfx.Loop()])
            dur = duration_or_missing(result)
            t_rep = 0.8 + 0.25
            print(f"infinite_loop duration={dur} t_rep={t_rep}", flush=True)
            assert dur is None
            assert pictures_equal(_frame(ws, result, t_rep), _frame(ws, source, 0.25))
            assert pictures_equal(_frame(ws, result, 0.1), _frame(ws, source, 0.1))


class TestF08_loop_with_count_or_total_duration_sets_looped_length:
    def test_loop_with_count_or_total_duration_sets_looped_length(self):
        with workspace() as ws:
            first, second = _rgb_away_from(), None
            second = _rgb_away_from(first)
            src_d = 0.6
            source = _two_tone(ws, (10, 8), first, second, 0.3, src_d)
            n = 3
            counted = apply_effects(ws, source, [vfx.Loop(n=n)])
            total = 1.0
            timed = apply_effects(ws, source, [vfx.Loop(duration=total)])
            cd = duration_or_missing(counted)
            td = duration_or_missing(timed)
            t_rep = src_d + 0.15
            print(f"loop n={n} cd={cd} D={total:.2f} td={td} t_rep={t_rep}", flush=True)
            assert cd is not None and abs(cd - n * src_d) < 1e-6
            assert td is not None and abs(td - total) < 1e-6
            assert pictures_equal(_frame(ws, counted, t_rep), _frame(ws, source, 0.15))
            assert pictures_equal(_frame(ws, timed, t_rep), _frame(ws, source, 0.15))


def test_loop_aligns_mask_and_soundtrack():
    with workspace() as ws:
        w, h = 10, 8
        src_d = 0.7
        source = _two_tone(ws, (w, h), _RED, _GREEN, 0.35, src_d)
        mask = _two_tone(ws, (w, h), 0.15, 0.85, 0.35, src_d, is_mask=True)
        audio = _audio(ws, lambda t: 0.15 + 0.7 * (np.asarray(t) >= 0.35), src_d)
        source = _attach_audio(ws, _attach_mask(ws, source, mask), audio)
        result = apply_effects(ws, source, [vfx.Loop(n=2)])
        t_rep = src_d + 0.2
        src_t = 0.2
        print(f"loop_align t_rep={t_rep} src_t={src_t}", flush=True)
        assert pictures_equal(
            require_mask_picture(_frame(ws, result.mask, t_rep), h, w),
            require_mask_picture(_frame(ws, source.mask, src_t), h, w),
        )
        assert samples_close(_soundtrack(ws, result, t_rep), _soundtrack(ws, source, src_t))


class TestF08_looping_clip_without_duration_does_not_succeed:
    def test_looping_clip_without_duration_does_not_succeed(self):
        with workspace() as ws:
            infinite = _color(ws, (8, 8), _rgb_away_from())
            assert duration_or_missing(infinite) is None
            failed = ws.call(infinite.with_effects, [vfx.Loop(n=2)])
            timed = require_ok(ws.call(infinite.with_duration, 0.5))
            ok = apply_effects(ws, timed, [vfx.Loop(n=2)])
            print(
                f"loop_no_duration failed={failed.exception is not None} "
                f"ok_d={duration_or_missing(ok)}",
                flush=True,
            )
            require_failed(failed)
            assert duration_or_missing(ok) is not None


class TestF08_time_mirror_plays_backward_and_aligns:
    def test_time_mirror_plays_backward_and_aligns(self):
        with workspace() as ws:
            w, h = 10, 8
            duration = 1.0
            source = _two_tone(ws, (w, h), _RED, _GREEN, 0.5, duration)
            mask = _two_tone(ws, (w, h), 0.2, 0.9, 0.5, duration, is_mask=True)
            audio = _audio(ws, lambda t: 0.1 + 0.7 * (np.asarray(t) >= 0.5), duration)
            source = _attach_audio(ws, _attach_mask(ws, source, mask), audio)
            source = _with_fps(ws, source, 12)
            result = apply_effects(ws, source, [vfx.TimeMirror()])
            print(
                f"mirror early={_rgb_at(_frame(ws, result, 0.2), 1, 1)} "
                f"late={_rgb_at(_frame(ws, result, 0.8), 1, 1)}",
                flush=True,
            )
            assert pictures_equal(_frame(ws, result, 0.2), _frame(ws, source, 0.8))
            assert pictures_equal(
                require_mask_picture(_frame(ws, result.mask, 0.2), h, w),
                require_mask_picture(_frame(ws, source.mask, 0.8), h, w),
            )
            assert samples_close(_soundtrack(ws, result, 0.2), _soundtrack(ws, source, 0.8))


class TestF08_time_symmetrize_forwards_then_backwards_doubles_duration:
    def test_time_symmetrize_forwards_then_backwards_doubles_duration(self):
        with workspace() as ws:
            w, h = 10, 8
            duration = 0.8
            source = _two_tone(ws, (w, h), _RED, _GREEN, 0.4, duration)
            mask = _two_tone(ws, (w, h), 0.2, 0.85, 0.4, duration, is_mask=True)
            audio = _audio(ws, lambda t: 0.2 + 0.5 * (np.asarray(t) >= 0.4), duration)
            source = _attach_audio(ws, _attach_mask(ws, source, mask), audio)
            source = _with_fps(ws, source, 12)
            result = apply_effects(ws, source, [vfx.TimeSymmetrize()])
            dur = duration_or_missing(result)
            print(f"symmetrize duration={dur}", flush=True)
            assert dur is not None and abs(dur - 2 * duration) < 1e-6
            # After the midpoint, playback is the forward clip mirrored.
            assert pictures_equal(_frame(ws, result, duration + 0.1), _frame(ws, source, duration - 0.1))
            assert pictures_equal(
                require_mask_picture(_frame(ws, result.mask, duration + 0.1), h, w),
                require_mask_picture(_frame(ws, source.mask, duration - 0.1), h, w),
            )
            assert samples_close(
                _soundtrack(ws, result, duration + 0.1),
                _soundtrack(ws, source, duration - 0.1),
            )


class TestF08_time_mirror_and_symmetrize_require_duration:
    def test_time_mirror_and_symmetrize_require_duration(self):
        with workspace() as ws:
            infinite = _color(ws, (8, 8), _rgb_away_from())
            timed = _with_fps(ws, require_ok(ws.call(infinite.with_duration, 0.6)), 12)
            ok_m = apply_effects(ws, timed, [vfx.TimeMirror()])
            ok_s = apply_effects(ws, timed, [vfx.TimeSymmetrize()])
            fail_m = ws.call(infinite.with_effects, [vfx.TimeMirror()])
            fail_s = ws.call(infinite.with_effects, [vfx.TimeSymmetrize()])
            print(
                f"mirror/symm require duration ok_m={duration_or_missing(ok_m)} "
                f"ok_s={duration_or_missing(ok_s)}",
                flush=True,
            )
            require_failed(fail_m)
            require_failed(fail_s)
            assert duration_or_missing(ok_m) is not None
            assert duration_or_missing(ok_s) is not None


# ---------------------------------------------------------------------------
# D. Crop, resize, rotate, mirrors: mask follows, samples unchanged
# ---------------------------------------------------------------------------


def test_crop_effect_matches_fp05_oracle_and_leaves_samples():
    with workspace() as ws:
        color = (210, 40, 40)
        source = _color(ws, (10, 10), color, duration=1.0)
        audio = _audio(ws, _const_mono(0.55), 1.0)
        source = _attach_audio(ws, source, audio)
        cropped = apply_effects(ws, source, [vfx.Crop(x1=0, y1=0, x2=5, y2=10)])
        frame = _frame(ws, cropped, 0.0)
        print(f"crop_oracle size={_frame_size(frame)}", flush=True)
        require_rgb_picture(frame, 10, 5, color=color)
        assert samples_close(_soundtrack(ws, cropped, 0.2), _soundtrack(ws, source, 0.2))

        rw, rh = _even(6, 9), _even(5, 8)
        if rw == rh:
            rh = rw + 2
        x2 = rw // 2
        runtime_c = _rgb_away_from(color)
        runtime = _color(ws, (rw, rh), runtime_c, duration=0.6)
        got = apply_effects(ws, runtime, [vfx.Crop(x1=0, y1=0, x2=x2, y2=rh)])
        require_rgb_picture(_frame(ws, got, 0.0), rh, x2, color=runtime_c)


def test_resize_effect_matches_fp05_oracle_and_leaves_samples():
    with workspace() as ws:
        source = _color(ws, (1024, 800), _rgb_away_from(), duration=0.5)
        audio = _audio(ws, _const_mono(0.4), 0.5)
        source = _attach_audio(ws, source, audio)
        resized = apply_effects(ws, source, [vfx.Resize(width=480)])
        frame = _frame(ws, resized, 0.0)
        print(f"resize_oracle size={_frame_size(frame)}", flush=True)
        _w, _h = _frame_size(frame)
        assert _w == 480 and _h == 375
        assert samples_close(_soundtrack(ws, resized, 0.1), _soundtrack(ws, source, 0.1))

        src_w, src_h = 48, 32
        new_w = 24
        runtime = apply_effects(
            ws, _color(ws, (src_w, src_h), _rgb_away_from(), duration=0.4), [vfx.Resize(width=new_w)]
        )
        rw, rh = _frame_size(_frame(ws, runtime, 0.0))
        assert rw == new_w
        assert rh == int(round(src_h * (new_w / src_w)))


class TestF08_rotate_effect_matches_fp05_oracle_and_leaves_samples:
    def test_rotate_effect_matches_fp05_oracle_and_leaves_samples(self):
        with workspace() as ws:
            w, h, block = 16, 12, 4
            tl = _rgb_away_from()
            br = _rgb_away_from(tl)
            fill = _rgb_away_from(tl, br)
            pic = _solid(h, w, fill)
            pic[:block, :block] = tl
            pic[h - block :, w - block :] = br
            mask_arr = np.full((h, w), 0.1, dtype=float)
            mask_arr[:block, :block] = 0.9
            mask = _video(ws, lambda t, arr=mask_arr: arr.copy(), 0.8, is_mask=True)
            source = _still(ws, pic, 0.8)
            audio = _audio(ws, _const_mono(0.33), 0.8)
            source = _attach_audio(ws, _attach_mask(ws, source, mask), audio)
            rotated = apply_effects(ws, source, [vfx.Rotate(180, expand=True)])
            frame = _frame(ws, rotated, 0.0)
            rw, rh = _frame_size(frame)
            rmask = require_mask_picture(_frame(ws, rotated.mask, 0.0), rh, rw)
            print(f"rotate180 size={rw}x{rh} br_px={_rgb_at(frame, rw - 1, rh - 1)}", flush=True)
            _assert_color_at(frame, rw - 1, rh - 1, tl, atol=25)
            assert float(rmask[rh // 2 :, rw // 2 :].mean()) > float(
                rmask[: rh // 2, : rw // 2].mean()
            )
            assert samples_close(_soundtrack(ws, rotated, 0.2), _soundtrack(ws, source, 0.2))


def test_oracle_horizontal_mirror_swaps_left_and_right():
    with workspace() as ws:
        h, w = 10, 12
        left, right = _rgb_away_from(), None
        right = _rgb_away_from(left)
        pic = _lr_picture(h, w, left, right)
        source = _still(ws, pic, 0.5)
        result = apply_effects(ws, source, [vfx.MirrorX()])
        frame = _frame(ws, result, 0.0)
        print(
            f"hmirror L={_rgb_at(frame, 1, h // 2)} R={_rgb_at(frame, w - 2, h // 2)}",
            flush=True,
        )
        _assert_color_at(frame, 1, h // 2, right)
        _assert_color_at(frame, w - 2, h // 2, left)


def test_vertical_mirror_swaps_top_and_bottom():
    with workspace() as ws:
        h, w = 12, 10
        top, bottom = _rgb_away_from(), None
        bottom = _rgb_away_from(top)
        pic = _tb_picture(h, w, top, bottom)
        result = apply_effects(ws, _still(ws, pic, 0.5), [vfx.MirrorY()])
        frame = _frame(ws, result, 0.0)
        print(
            f"vmirror T={_rgb_at(frame, w // 2, 1)} B={_rgb_at(frame, w // 2, h - 2)}",
            flush=True,
        )
        _assert_color_at(frame, w // 2, 1, bottom)
        _assert_color_at(frame, w // 2, h - 2, top)


def test_geometry_effects_transform_mask_not_samples():
    with workspace() as ws:
        w, h = 12, 10
        left, right = _rgb_away_from(), None
        right = _rgb_away_from(left)
        pic = _lr_picture(h, w, left, right)
        mask_arr = _lr_mask(h, w, 0.9, 0.1)
        audio = _audio(ws, lambda t: 0.15 + 0.6 * (np.asarray(t) >= 0.5), 1.0)
        mask = _video(ws, lambda t, arr=mask_arr: arr.copy(), 1.0, is_mask=True)
        still = _video(ws, lambda t, arr=pic: arr.copy(), 1.0)
        source = _attach_audio(ws, _attach_mask(ws, still, mask), audio)
        before = _soundtrack(ws, source, 0.3)
        sped = apply_effects(ws, source, [vfx.MultiplySpeed(2)])
        assert not samples_close(_soundtrack(ws, sped, 0.3), before)

        cropped = apply_effects(ws, source, [vfx.Crop(x1=0, y1=0, x2=w // 2, y2=h)])
        cw, ch = w // 2, h
        cmask = require_mask_picture(_frame(ws, cropped.mask, 0.0), ch, cw)
        print(f"geo crop mask mean={float(cmask.mean()):.3f}", flush=True)
        assert float(cmask.mean()) > 0.7
        assert samples_close(_soundtrack(ws, cropped, 0.3), before)

        hx = apply_effects(ws, source, [vfx.MirrorX()])
        hmask = require_mask_picture(_frame(ws, hx.mask, 0.0), h, w)
        assert float(hmask[:, : w // 2].mean()) < float(hmask[:, w // 2 :].mean())
        assert samples_close(_soundtrack(ws, hx, 0.3), before)

        top_c, bot_c = left, right
        tb_pic = _tb_picture(h, w, top_c, bot_c)
        tb_mask_arr = _tb_mask(h, w, 0.9, 0.1)
        tb_still = _video(ws, lambda t, arr=tb_pic: arr.copy(), 1.0)
        tb_mask = _video(ws, lambda t, arr=tb_mask_arr: arr.copy(), 1.0, is_mask=True)
        tb_source = _attach_audio(ws, _attach_mask(ws, tb_still, tb_mask), audio)
        vy = apply_effects(ws, tb_source, [vfx.MirrorY()])
        vframe = _frame(ws, vy, 0.0)
        vmask = require_mask_picture(_frame(ws, vy.mask, 0.0), h, w)
        print(
            f"geo vmirror pic T={_rgb_at(vframe, w // 2, 1)} "
            f"B={_rgb_at(vframe, w // 2, h - 2)} "
            f"mask T={float(vmask[: h // 2].mean()):.3f} "
            f"B={float(vmask[h // 2 :].mean()):.3f}",
            flush=True,
        )
        _assert_color_at(vframe, w // 2, 1, bot_c)
        _assert_color_at(vframe, w // 2, h - 2, top_c)
        assert float(vmask[: h // 2, :].mean()) < float(vmask[h // 2 :, :].mean())
        assert samples_close(_soundtrack(ws, vy, 0.3), before)

        resized = apply_effects(ws, source, [vfx.Resize(width=w // 2)])
        rw, rh = _frame_size(_frame(ws, resized, 0.0))
        rmask = require_mask_picture(_frame(ws, resized.mask, 0.0), rh, rw)
        assert rmask.shape == (rh, rw)
        assert samples_close(_soundtrack(ws, resized, 0.3), before)

        rot_pic = _solid(h, w, right)
        rot_pic[: h // 2, : w // 2] = left
        rot_mask_arr = np.full((h, w), 0.1, dtype=float)
        rot_mask_arr[: h // 2, : w // 2] = 0.9
        rot_still = _video(ws, lambda t, arr=rot_pic: arr.copy(), 1.0)
        rot_mask = _video(ws, lambda t, arr=rot_mask_arr: arr.copy(), 1.0, is_mask=True)
        rot_source = _attach_audio(ws, _attach_mask(ws, rot_still, rot_mask), audio)
        rotated = apply_effects(ws, rot_source, [vfx.Rotate(180, expand=True)])
        rframe = _frame(ws, rotated, 0.0)
        rot_w, rot_h = _frame_size(rframe)
        rot_mask_frame = require_mask_picture(
            _frame(ws, rotated.mask, 0.0), rot_h, rot_w
        )
        print(
            f"geo rotate size={rot_w}x{rot_h} "
            f"br_px={_rgb_at(rframe, rot_w - 1, rot_h - 1)} "
            f"mask BR={float(rot_mask_frame[rot_h // 2 :, rot_w // 2 :].mean()):.3f} "
            f"TL={float(rot_mask_frame[: rot_h // 2, : rot_w // 2].mean()):.3f}",
            flush=True,
        )
        _assert_color_at(rframe, rot_w - 1, rot_h - 1, left, atol=25)
        assert float(rot_mask_frame[rot_h // 2 :, rot_w // 2 :].mean()) > float(
            rot_mask_frame[: rot_h // 2, : rot_w // 2].mean()
        )
        assert samples_close(_soundtrack(ws, rotated, 0.3), before)


# ---------------------------------------------------------------------------
# E. Color-only
# ---------------------------------------------------------------------------


def test_oracle_invert_red_is_cyan():
    with workspace() as ws:
        source = _color(ws, (8, 8), _RED, duration=0.4)
        out = apply_effects(ws, source, [vfx.InvertColors()])
        require_rgb_picture(_frame(ws, out, 0.0), 8, 8, color=_CYAN)
        other = _rgb_away_from(_RED, _CYAN)
        expected = tuple(255 - c for c in other)
        runtime = apply_effects(ws, _color(ws, (9, 7), other, duration=0.4), [vfx.InvertColors()])
        print(f"invert other={other} expected={expected}", flush=True)
        require_rgb_picture(_frame(ws, runtime, 0.0), 7, 9, color=expected)


def test_black_and_white_desaturates():
    with workspace() as ws:
        bright = (40, 220, 40)
        dark = (40, 40, 180)
        assert abs(_luminance(bright) - _luminance(dark)) > 40
        a = apply_effects(ws, _color(ws, (8, 8), bright, duration=0.4), [vfx.BlackAndWhite()])
        b = apply_effects(ws, _color(ws, (8, 8), dark, duration=0.4), [vfx.BlackAndWhite()])
        fa, fb = _frame(ws, a, 0.0), _frame(ws, b, 0.0)
        print(
            f"bw spread_a={_channel_spread(fa):.2f} spread_b={_channel_spread(fb):.2f} "
            f"mean_a={_mean_rgb(fa):.1f} mean_b={_mean_rgb(fb):.1f}",
            flush=True,
        )
        assert _channel_spread(fa) < 12
        assert _channel_spread(fb) < 12
        assert abs(_mean_rgb(fa) - _mean_rgb(fb)) > 8
        assert not pictures_equal(fa, fb)


def test_multiply_color_scales_rgb():
    with workspace() as ws:
        factor = 0.35 + _rand_int(0, 20) / 100.0
        assert 0 < factor < 1
        source = _color(ws, (8, 8), _RED, duration=0.4)
        scaled = apply_effects(ws, source, [vfx.MultiplyColor(factor)])
        ident = apply_effects(ws, source, [vfx.MultiplyColor(1.0)])
        got = _rgb_at(_frame(ws, scaled, 0.0), 1, 1)
        print(f"mulcolor factor={factor:.2f} got={got}", flush=True)
        assert abs(got[0] - 255 * factor) <= 2
        assert got[1] <= 2 and got[2] <= 2
        assert pictures_equal(_frame(ws, ident, 0.0), _frame(ws, source, 0.0))


def test_gamma_correction_changes_mid_grey():
    with workspace() as ws:
        grey = (128, 128, 128)
        source = _color(ws, (8, 8), grey, duration=0.4)
        g1 = apply_effects(ws, source, [vfx.GammaCorrection(1.0)])
        ga = apply_effects(ws, source, [vfx.GammaCorrection(0.5)])
        gb = apply_effects(ws, source, [vfx.GammaCorrection(2.0)])
        src_f, f1, fa, fb = (_frame(ws, c, 0.0) for c in (source, g1, ga, gb))
        print(
            f"gamma means src={_mean_rgb(src_f):.1f} g1={_mean_rgb(f1):.1f} "
            f"g05={_mean_rgb(fa):.1f} g2={_mean_rgb(fb):.1f}",
            flush=True,
        )
        assert abs(_mean_rgb(f1) - _mean_rgb(src_f)) <= 2
        assert abs(_mean_rgb(fa) - _mean_rgb(src_f)) > 4
        assert not pictures_equal(fa, fb)


def test_luminosity_and_contrast_shift_picture():
    with workspace() as ws:
        dark, bright = (50, 50, 50), (200, 200, 200)
        h, w = 10, 12
        pic = _solid(h, w, dark)
        pic[:, w // 2 :] = bright
        source = _still(ws, pic, 0.5)
        lum_only = apply_effects(ws, source, [vfx.LumContrast(lum=40)])
        contrast_only = apply_effects(ws, source, [vfx.LumContrast(contrast=0.6)])
        src_f = _frame(ws, source, 0.0)
        lum_f = _frame(ws, lum_only, 0.0)
        con_f = _frame(ws, contrast_only, 0.0)
        src_spread = abs(_rgb_at(src_f, 1, 1)[0] - _rgb_at(src_f, w - 2, 1)[0])
        con_spread = abs(_rgb_at(con_f, 1, 1)[0] - _rgb_at(con_f, w - 2, 1)[0])
        print(
            f"lum mean {_mean_rgb(src_f):.1f}->{_mean_rgb(lum_f):.1f} "
            f"contrast spread {src_spread}->{con_spread}",
            flush=True,
        )
        assert _mean_rgb(lum_f) > _mean_rgb(src_f) + 8
        assert abs(con_spread - src_spread) > 8
        assert not pictures_equal(lum_f, con_f)


def test_color_only_effects_leave_soundtrack_samples_unchanged():
    with workspace() as ws:
        audio = _audio(ws, _const_mono(0.58), 0.8)
        source = _attach_audio(ws, _color(ws, (8, 8), _rgb_away_from(_BLACK), duration=0.8), audio)
        before = _soundtrack(ws, source, 0.2)
        effects = [
            vfx.InvertColors(),
            vfx.BlackAndWhite(),
            vfx.GammaCorrection(0.7),
            vfx.MultiplyColor(0.6),
            vfx.LumContrast(lum=20),
        ]
        for effect in effects:
            out = apply_effects(ws, source, [effect])
            print(f"color_leave_audio {type(effect).__name__}", flush=True)
            assert samples_close(_soundtrack(ws, out, 0.2), before)
            assert not pictures_equal(_frame(ws, out, 0.0), _frame(ws, source, 0.0))


# ---------------------------------------------------------------------------
# F. Fade in / out
# ---------------------------------------------------------------------------


def test_oracle_fade_in_from_black_on_white_is_darker_near_zero():
    with workspace() as ws:
        fade_d = 0.4
        play = 1.0
        source = _color(ws, (10, 8), _WHITE, duration=play)
        faded = apply_effects(ws, source, [vfx.FadeIn(fade_d)])
        t_mid = fade_d * 0.35
        near0 = _frame(ws, faded, 0.0)
        mid = _frame(ws, faded, t_mid)
        after = _frame(ws, faded, fade_d + 0.1)
        print(
            f"fadein_black means 0={_mean_rgb(near0):.1f} mid={_mean_rgb(mid):.1f} "
            f"after={_mean_rgb(after):.1f}",
            flush=True,
        )
        assert _mean_rgb(near0) < _mean_rgb(after) - 20
        assert _near(_rgb_at(after, 1, 1), _WHITE, atol=12)
        assert not _near(_rgb_at(mid, 1, 1), _BLACK, atol=12)
        assert not _near(_rgb_at(mid, 1, 1), _WHITE, atol=12)


def test_fade_in_from_named_color():
    with workspace() as ws:
        src_c = _WHITE
        from_c = _rgb_away_from(src_c, _BLACK)
        fade_d = 0.5
        named = apply_effects(
            ws, _color(ws, (10, 8), src_c, duration=1.0), [vfx.FadeIn(fade_d, initial_color=from_c)]
        )
        default = apply_effects(
            ws, _color(ws, (10, 8), src_c, duration=1.0), [vfx.FadeIn(fade_d)]
        )
        t_mid = fade_d * 0.4
        n0 = _frame(ws, named, 0.0)
        n_after = _frame(ws, named, fade_d + 0.1)
        n_mid = _frame(ws, named, t_mid)
        print(
            f"fadein_named from={from_c} t0={_rgb_at(n0, 1, 1)} after={_rgb_at(n_after, 1, 1)}",
            flush=True,
        )
        _assert_color_at(n0, 1, 1, from_c, atol=12)
        _assert_color_at(n_after, 1, 1, src_c, atol=12)
        assert not _near(_rgb_at(n_mid, 1, 1), from_c, atol=12)
        assert not _near(_rgb_at(n_mid, 1, 1), src_c, atol=12)
        d_after = _frame(ws, default, fade_d + 0.1)
        _assert_color_at(d_after, 1, 1, src_c, atol=12)
        assert _mean_rgb(_frame(ws, default, 0.0)) < _mean_rgb(d_after) - 20


def test_fade_in_on_mask_uses_unit_scalar():
    with workspace() as ws:
        w, h = 10, 8
        fade_d = 0.4
        mask = _color(ws, (w, h), 1.0, duration=1.0, is_mask=True)
        faded = apply_effects(ws, mask, [vfx.FadeIn(fade_d)])
        t_mid = fade_d * 0.33
        a0 = require_mask_picture(_frame(ws, faded, 0.0), h, w)
        amid = require_mask_picture(_frame(ws, faded, t_mid), h, w)
        aafter = require_mask_picture(_frame(ws, faded, fade_d + 0.1), h, w)
        print(
            f"fadein_mask 0={float(a0.mean()):.3f} mid={float(amid.mean()):.3f} "
            f"after={float(aafter.mean()):.3f}",
            flush=True,
        )
        assert float(a0.mean()) < float(aafter.mean()) - 0.2
        assert abs(float(amid.mean()) - float(a0.mean())) > 0.05
        assert abs(float(amid.mean()) - float(aafter.mean())) > 0.05

        from_s = 0.25 + _rand_int(0, 20) / 100.0
        named = apply_effects(ws, mask, [vfx.FadeIn(fade_d, initial_color=from_s)])
        n0 = require_mask_picture(_frame(ws, named, 0.0), h, w)
        nmid = require_mask_picture(_frame(ws, named, t_mid), h, w)
        nafter = require_mask_picture(_frame(ws, named, fade_d + 0.1), h, w)
        print(
            f"fadein_mask_scalar from={from_s:.3f} 0={float(n0.mean()):.3f} "
            f"mid={float(nmid.mean()):.3f} after={float(nafter.mean()):.3f}",
            flush=True,
        )
        assert abs(float(n0.mean()) - from_s) <= 0.08
        assert abs(float(nafter.mean()) - 1.0) <= 0.08
        assert abs(float(nmid.mean()) - from_s) > 0.05
        assert abs(float(nmid.mean()) - 1.0) > 0.05


class TestF08_fade_out_to_color_over_duration:
    def test_fade_out_to_color_over_duration(self):
        with workspace() as ws:
            fade_d = 0.5
            faded = apply_effects(
                ws, _color(ws, (10, 8), _WHITE, duration=fade_d), [vfx.FadeOut(fade_d)]
            )
            t_mid = fade_d * 0.4
            t_end = fade_d * 0.96
            a0 = _frame(ws, faded, 0.0)
            amid = _frame(ws, faded, t_mid)
            aend = _frame(ws, faded, t_end)
            print(
                f"fadeout means 0={_mean_rgb(a0):.1f} mid={_mean_rgb(amid):.1f} "
                f"end={_mean_rgb(aend):.1f}",
                flush=True,
            )
            assert _mean_rgb(a0) > _mean_rgb(aend) + 20
            assert not _near(_rgb_at(amid, 1, 1), _WHITE, atol=12)
            assert not _near(_rgb_at(amid, 1, 1), _BLACK, atol=12)

            to_c = _rgb_away_from(_WHITE, _BLACK)
            named = apply_effects(
                ws,
                _color(ws, (10, 8), _WHITE, duration=fade_d),
                [vfx.FadeOut(fade_d, final_color=to_c)],
            )
            n0 = _frame(ws, named, 0.0)
            nmid = _frame(ws, named, t_mid)
            nend = _frame(ws, named, t_end)
            print(
                f"fadeout_named to={to_c} t0={_rgb_at(n0, 1, 1)} "
                f"mid={_rgb_at(nmid, 1, 1)} end={_rgb_at(nend, 1, 1)}",
                flush=True,
            )
            _assert_color_at(n0, 1, 1, _WHITE, atol=12)
            _assert_color_at(nend, 1, 1, to_c, atol=18)
            assert not _near(_rgb_at(nmid, 1, 1), _WHITE, atol=12)
            assert not _near(_rgb_at(nmid, 1, 1), to_c, atol=12)


# ---------------------------------------------------------------------------
# G. Cross-fade overlay
# ---------------------------------------------------------------------------


def test_oracle_cross_fade_in_overlay_goes_from_lower_to_upper():
    with workspace() as ws:
        w, h = 12, 10
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        fade_d = 0.45
        play = 1.0
        lower = _color(ws, (w, h), lower_c, duration=play)
        upper = apply_effects(ws, _color(ws, (w, h), upper_c, duration=play), [vfx.CrossFadeIn(fade_d)])
        comp = _overlay(ws, [lower, upper])
        t_mid = fade_d * 0.32
        t_end = fade_d + 0.15
        at0, amid, aend = _frame(ws, comp, 0.0), _frame(ws, comp, t_mid), _frame(ws, comp, t_end)
        cx, cy = w // 2, h // 2
        print(
            f"xfade_in t0={_rgb_at(at0, cx, cy)} mid={_rgb_at(amid, cx, cy)} "
            f"end={_rgb_at(aend, cx, cy)}",
            flush=True,
        )
        _assert_color_at(at0, cx, cy, lower_c, atol=14)
        _assert_color_at(aend, cx, cy, upper_c, atol=14)
        assert _rgb_at(amid, cx, cy) != _rgb_at(at0, cx, cy)
        assert _rgb_at(amid, cx, cy) != _rgb_at(aend, cx, cy)


class TestF08_cross_fade_out_overlay_goes_from_upper_to_lower:
    def test_cross_fade_out_overlay_goes_from_upper_to_lower(self):
        with workspace() as ws:
            w, h = 12, 10
            lower_c = _rgb_away_from()
            upper_c = _rgb_away_from(lower_c)
            fade_d = 0.5
            lower = _color(ws, (w, h), lower_c, duration=fade_d)
            upper = apply_effects(
                ws, _color(ws, (w, h), upper_c, duration=fade_d), [vfx.CrossFadeOut(fade_d)]
            )
            comp = _overlay(ws, [lower, upper])
            t_mid = fade_d * 0.35
            t_end = fade_d * 0.97
            at0, amid, aend = _frame(ws, comp, 0.0), _frame(ws, comp, t_mid), _frame(ws, comp, t_end)
            cx, cy = w // 2, h // 2
            print(
                f"xfade_out t0={_rgb_at(at0, cx, cy)} mid={_rgb_at(amid, cx, cy)} "
                f"end={_rgb_at(aend, cx, cy)}",
                flush=True,
            )
            _assert_color_at(at0, cx, cy, upper_c, atol=14)
            _assert_color_at(aend, cx, cy, lower_c, atol=18)
            assert _rgb_at(amid, cx, cy) != _rgb_at(at0, cx, cy)
            assert _rgb_at(amid, cx, cy) != _rgb_at(aend, cx, cy)


# ---------------------------------------------------------------------------
# H. Blink / slide: overlay visibility; standalone picture unchanged
# ---------------------------------------------------------------------------


class TestF08_blink_toggles_overlay_visibility_standalone_picture_unchanged:
    def test_blink_toggles_overlay_visibility_standalone_picture_unchanged(self):
        with workspace() as ws:
            w, h = 12, 10
            lower_c = _rgb_away_from()
            upper_c = _rgb_away_from(lower_c)
            on_d, off_d = 0.3, 0.3
            play = 1.2
            lower = _color(ws, (w, h), lower_c, duration=play)
            upper = _color(ws, (w, h), upper_c, duration=play)
            blinked = apply_effects(ws, upper, [vfx.Blink(on_d, off_d)])
            comp = _overlay(ws, [lower, blinked])
            t_on, t_off = 0.1, 0.45
            on_f, off_f = _frame(ws, comp, t_on), _frame(ws, comp, t_off)
            cx, cy = w // 2, h // 2
            print(
                f"blink on={_rgb_at(on_f, cx, cy)} off={_rgb_at(off_f, cx, cy)}",
                flush=True,
            )
            _assert_color_at(on_f, cx, cy, upper_c, atol=14)
            _assert_color_at(off_f, cx, cy, lower_c, atol=14)
            require_rgb_picture(_frame(ws, blinked, t_on), h, w, color=upper_c)
            require_rgb_picture(_frame(ws, blinked, t_off), h, w, color=upper_c)
            untouched = _overlay(ws, [lower, upper])
            assert pictures_equal(_frame(ws, untouched, t_on), _frame(ws, untouched, t_off))


def _coverage_vs_lower(frame, lower_c, upper_c, atol=22) -> float:
    arr = _picture_rgb(frame).astype(float)
    lower = np.asarray(lower_c, dtype=float)
    upper = np.asarray(upper_c, dtype=float)
    d_low = np.linalg.norm(arr - lower, axis=-1)
    d_up = np.linalg.norm(arr - upper, axis=-1)
    return float((d_up < d_low).mean())


def test_slide_in_from_each_side_on_overlay():
    with workspace() as ws:
        w, h = 16, 14
        lower_c = _rgb_away_from()
        upper_c = _rgb_away_from(lower_c)
        fade_d = 0.5
        play = 1.0
        lower = _color(ws, (w, h), lower_c, duration=play)
        sides = ("left", "right", "top", "bottom")
        t_near0, t_mid, t_after = 0.04, fade_d * 0.45, fade_d + 0.1
        frames = {}
        for side in sides:
            upper = apply_effects(
                ws, _color(ws, (w, h), upper_c, duration=play), [vfx.SlideIn(fade_d, side)]
            )
            comp = _overlay(ws, [lower, upper])
            frames[side] = (
                _frame(ws, comp, t_near0),
                _frame(ws, comp, t_mid),
                _frame(ws, comp, t_after),
            )
            cov0 = _coverage_vs_lower(frames[side][0], lower_c, upper_c)
            cov_mid = _coverage_vs_lower(frames[side][1], lower_c, upper_c)
            cov_after = _coverage_vs_lower(frames[side][2], lower_c, upper_c)
            print(
                f"slide_in {side} cov0={cov0:.3f} mid={cov_mid:.3f} after={cov_after:.3f}",
                flush=True,
            )
            assert cov_after > 0.85
            assert cov0 < cov_after - 0.2
            assert 0.08 < cov_mid < 0.92
        for i, a in enumerate(sides):
            for b in sides[i + 1 :]:
                assert not pictures_equal(frames[a][1], frames[b][1])


class TestF08_slide_out_toward_each_side_on_overlay:
    def test_slide_out_toward_each_side_on_overlay(self):
        with workspace() as ws:
            w, h = 16, 14
            lower_c = _rgb_away_from()
            upper_c = _rgb_away_from(lower_c)
            fade_d = 0.5
            lower = _color(ws, (w, h), lower_c, duration=fade_d)
            sides = ("left", "right", "top", "bottom")
            t_near0, t_mid, t_end = 0.02, fade_d * 0.5, fade_d * 0.96
            frames = {}
            for side in sides:
                upper = apply_effects(
                    ws, _color(ws, (w, h), upper_c, duration=fade_d), [vfx.SlideOut(fade_d, side)]
                )
                comp = _overlay(ws, [lower, upper])
                frames[side] = (
                    _frame(ws, comp, t_near0),
                    _frame(ws, comp, t_mid),
                    _frame(ws, comp, t_end),
                )
                cov0 = _coverage_vs_lower(frames[side][0], lower_c, upper_c)
                cov_mid = _coverage_vs_lower(frames[side][1], lower_c, upper_c)
                cov_end = _coverage_vs_lower(frames[side][2], lower_c, upper_c)
                print(
                    f"slide_out {side} cov0={cov0:.3f} mid={cov_mid:.3f} end={cov_end:.3f}",
                    flush=True,
                )
                assert cov0 > cov_end + 0.2
                assert 0.08 < cov_mid < 0.92
            for i, a in enumerate(sides):
                for b in sides[i + 1 :]:
                    assert not pictures_equal(frames[a][1], frames[b][1])
            # Same side: coverage grows on the way in, shrinks on the way out.
            in_left = apply_effects(
                ws, _color(ws, (w, h), upper_c, duration=1.0), [vfx.SlideIn(fade_d, "left")]
            )
            in_comp = _overlay(ws, [_color(ws, (w, h), lower_c, duration=1.0), in_left])
            c_early = _coverage_vs_lower(_frame(ws, in_comp, 0.08), lower_c, upper_c)
            c_late = _coverage_vs_lower(_frame(ws, in_comp, fade_d * 0.7), lower_c, upper_c)
            assert c_late > c_early


def test_slide_in_out_standalone_picture_unchanged():
    with workspace() as ws:
        w, h = 12, 10
        lower_c = _rgb_away_from()
        color = _rgb_away_from(lower_c)
        slide_d = 0.4
        play_in = 0.8
        lower_in = _color(ws, (w, h), lower_c, duration=play_in)
        source_in = _color(ws, (w, h), color, duration=play_in)
        slid_in = apply_effects(ws, source_in, [vfx.SlideIn(slide_d, "right")])
        lower_out = _color(ws, (w, h), lower_c, duration=slide_d)
        source_out = _color(ws, (w, h), color, duration=slide_d)
        slid_out = apply_effects(ws, source_out, [vfx.SlideOut(slide_d, "top")])
        t_in0, t_in_after = 0.05, 0.5
        t_out0, t_out_end = 0.05, 0.35
        in_comp = _overlay(ws, [lower_in, slid_in])
        out_comp = _overlay(ws, [lower_out, slid_out])
        in_cov0 = _coverage_vs_lower(_frame(ws, in_comp, t_in0), lower_c, color)
        in_cov_after = _coverage_vs_lower(_frame(ws, in_comp, t_in_after), lower_c, color)
        out_cov0 = _coverage_vs_lower(_frame(ws, out_comp, t_out0), lower_c, color)
        out_cov_end = _coverage_vs_lower(_frame(ws, out_comp, t_out_end), lower_c, color)
        print(
            f"slide_standalone overlay in cov0={in_cov0:.3f} after={in_cov_after:.3f} "
            f"out cov0={out_cov0:.3f} end={out_cov_end:.3f}",
            flush=True,
        )
        assert in_cov_after > in_cov0 + 0.2
        assert out_cov0 > out_cov_end + 0.2
        untouched_in = _overlay(ws, [lower_in, source_in])
        untouched_out = _overlay(ws, [lower_out, source_out])
        assert pictures_equal(
            _frame(ws, untouched_in, t_in0), _frame(ws, untouched_in, t_in_after)
        )
        assert pictures_equal(
            _frame(ws, untouched_out, t_out0), _frame(ws, untouched_out, t_out_end)
        )
        for clip, t in (
            (slid_in, t_in0),
            (slid_in, t_in_after),
            (slid_out, t_out0),
            (slid_out, t_out_end),
        ):
            require_rgb_picture(_frame(ws, clip, t), h, w, color=color)
            print(f"slide_standalone t={t} still source color", flush=True)


def test_slide_in_out_require_side_among_four():
    with workspace() as ws:
        source = _color(ws, (10, 8), _rgb_away_from(), duration=0.6)
        ok = apply_effects(ws, source, [vfx.SlideIn(0.3, "left")])
        require_rgb_picture(_frame(ws, ok, 0.0), 8, 10)
        fail_in = ws.call(source.with_effects, [vfx.SlideIn(0.3, "diagonal")])
        fail_out = ws.call(source.with_effects, [vfx.SlideOut(0.3, "north")])
        print(
            f"slide_side ok={duration_or_missing(ok)} "
            f"fail_in={fail_in.exception is not None}",
            flush=True,
        )
        require_failed(fail_in)
        require_failed(fail_out)


# ---------------------------------------------------------------------------
# I. Remaining visual members
# ---------------------------------------------------------------------------


def test_accel_decel_warps_playback_versus_linear():
    with workspace() as ws:
        w, h, duration = 10, 8, 1.0
        first, second = _rgb_away_from(), None
        second = _rgb_away_from(first)
        split = 0.35
        source = _two_tone(ws, (w, h), first, second, split, duration)
        result = apply_effects(ws, source, [vfx.AccelDecel()])
        t0, t_end, t_in = 0.0, duration * 0.97, 0.40
        print(
            f"accel t0={_rgb_at(_frame(ws, result, t0), 1, 1)} "
            f"tin={_rgb_at(_frame(ws, result, t_in), 1, 1)} "
            f"src_tin={_rgb_at(_frame(ws, source, t_in), 1, 1)}",
            flush=True,
        )
        assert pictures_equal(_frame(ws, result, t0), _frame(ws, source, t0))
        assert pictures_equal(_frame(ws, result, t_end), _frame(ws, source, t_end))
        assert not pictures_equal(_frame(ws, result, t_in), _frame(ws, source, t_in))


def test_even_size_makes_width_and_height_even():
    with workspace() as ws:
        w = _rand_int(5, 9) * 2 + 1
        h = _rand_int(4, 8) * 2 + 1
        source = _color(ws, (w, h), _rgb_away_from(), duration=0.4)
        result = apply_effects(ws, source, [vfx.EvenSize()])
        rw, rh = _frame_size(_frame(ws, result, 0.0))
        print(f"even_size {w}x{h} -> {rw}x{rh}", flush=True)
        assert rw % 2 == 0 and rh % 2 == 0
        assert rw <= w and rh <= h


class TestF08_freeze_holds_frame_for_a_duration:
    def test_freeze_holds_frame_for_a_duration(self):
        with workspace() as ws:
            w, h = 10, 8
            a, b = _rgb_away_from(), None
            b = _rgb_away_from(a)
            source = _two_tone(ws, (w, h), a, b, 0.12, 1.2)
            short_d, long_d = 0.25, 0.7
            short = apply_effects(ws, source, [vfx.Freeze(t=0.0, freeze_duration=short_d)])
            long = apply_effects(ws, source, [vfx.Freeze(t=0.0, freeze_duration=long_d)])
            t_probe = 0.45
            sf, lf = _frame(ws, short, t_probe), _frame(ws, long, t_probe)
            freeze_px = _rgb_at(_frame(ws, source, 0.0), 1, 1)
            print(
                f"freeze short={_rgb_at(sf, 1, 1)} long={_rgb_at(lf, 1, 1)} frozen={freeze_px}",
                flush=True,
            )
            _assert_color_at(lf, 1, 1, freeze_px, atol=14)
            assert not _near(_rgb_at(sf, 1, 1), freeze_px, atol=14)


class TestF08_freeze_region_freezes_rectangle_rest_animates:
    def test_freeze_region_freezes_rectangle_rest_animates(self):
        with workspace() as ws:
            w, h = 16, 14
            c0, c1, c2 = _rgb_away_from(), None, None
            c1 = _rgb_away_from(c0)
            c2 = _rgb_away_from(c0, c1)
            x1, y1, x2, y2 = 3, 3, 8, 9

            def fn(t):
                tt = _scalar_t(t)
                color = c0 if tt < 0.3 else c1 if tt < 0.6 else c2
                return np.full((h, w, 3), color, dtype=np.uint8)

            source = _video(ws, fn, 1.0)
            result = apply_effects(ws, source, [vfx.FreezeRegion(region=(x1, y1, x2, y2))])
            t_a, t_b = 0.4, 0.8
            assert not pictures_equal(_frame(ws, source, t_a), _frame(ws, source, t_b))
            fa, fb = _frame(ws, result, t_a), _frame(ws, result, t_b)
            in_a, in_b = _rgb_at(fa, (x1 + x2) // 2, (y1 + y2) // 2), _rgb_at(
                fb, (x1 + x2) // 2, (y1 + y2) // 2
            )
            out_a, out_b = _rgb_at(fa, w - 2, 1), _rgb_at(fb, w - 2, 1)
            print(f"freeze_region in={in_a}/{in_b} out={out_a}/{out_b}", flush=True)
            assert _near(in_a, in_b, atol=10)
            assert not _near(out_a, out_b, atol=20)
            assert not _near(in_a, out_a, atol=20)


class TestF08_head_blur_moves_and_blurs_a_region:
    def test_head_blur_moves_and_blurs_a_region(self):
        with workspace() as ws:
            w, h = 24, 24
            left, right = (220, 40, 40), (40, 40, 220)
            pic = _lr_picture(h, w, left, right)
            source = _still(ws, pic, 1.0)
            edge = w // 2
            y_early, y_late = h // 4, (3 * h) // 4
            radius = 5
            fx = lambda t: float(edge)
            fy = lambda t: float(y_early if _scalar_t(t) < 0.5 else y_late)
            result = apply_effects(ws, source, [vfx.HeadBlur(fx, fy, radius)])
            early, late = _frame(ws, result, 0.1), _frame(ws, result, 0.8)
            src = _frame(ws, source, 0.0)

            def sharp_at(frame, y):
                return _near(_rgb_at(frame, edge - 3, y), left, 25) and _near(
                    _rgb_at(frame, edge + 3, y), right, 25
                )

            def bled_at(frame, y):
                return not sharp_at(frame, y)

            print(
                f"headblur early_mid={bled_at(early, y_early)} early_far={sharp_at(early, y_late)} "
                f"late_mid={bled_at(late, y_late)}",
                flush=True,
            )
            assert sharp_at(src, y_early) and sharp_at(src, y_late)
            assert bled_at(early, y_early)
            assert sharp_at(early, y_late)
            assert bled_at(late, y_late)
            assert sharp_at(late, y_early)


def test_make_loopable_fades_end_into_beginning():
    with workspace() as ws:
        w, h, duration, overlap = 12, 10, 1.0, 0.35
        start_c, end_c = _rgb_away_from(), None
        end_c = _rgb_away_from(start_c)
        other_start = _rgb_away_from(start_c, end_c)
        other_end = _rgb_away_from(start_c, end_c, other_start)

        def two(start, end):
            return _two_tone(ws, (w, h), start, end, duration * 0.5, duration)

        src = two(start_c, end_c)
        out = apply_effects(ws, src, [vfx.MakeLoopable(overlap)])
        dur = duration_or_missing(out)
        assert dur is not None
        t_end = dur * 0.92
        end_seg = _frame(ws, out, t_end)
        freeze_start = _frame(ws, src, 0.0)
        freeze_end = _frame(ws, src, duration * 0.95)
        print(
            f"loopable t_end={t_end:.3f} px={_rgb_at(end_seg, 1, 1)} "
            f"start={_rgb_at(freeze_start, 1, 1)} end={_rgb_at(freeze_end, 1, 1)}",
            flush=True,
        )
        assert not pictures_equal(end_seg, freeze_start)
        assert not pictures_equal(end_seg, freeze_end)
        swapped_start = apply_effects(ws, two(other_start, end_c), [vfx.MakeLoopable(overlap)])
        swapped_end = apply_effects(ws, two(start_c, other_end), [vfx.MakeLoopable(overlap)])
        d2 = duration_or_missing(swapped_start)
        d3 = duration_or_missing(swapped_end)
        assert d2 is not None and d3 is not None
        assert not pictures_equal(_frame(ws, swapped_start, d2 * 0.92), end_seg)
        assert not pictures_equal(_frame(ws, swapped_end, d3 * 0.92), end_seg)


def test_margin_grows_size_with_colored_or_transparent_border():
    with workspace() as ws:
        w, h = 10, 8
        inner = _rgb_away_from()
        border = _rgb_away_from(inner)
        source = _color(ws, (w, h), inner, duration=0.5)
        m = 3
        colored = apply_effects(ws, source, [vfx.Margin(margin_size=m, color=border)])
        cf = _frame(ws, colored, 0.0)
        cw, ch = _frame_size(cf)
        print(f"margin {w}x{h} -> {cw}x{ch}", flush=True)
        assert cw == w + 2 * m and ch == h + 2 * m
        _assert_color_at(cf, 0, 0, border, atol=12)
        _assert_color_at(cf, m + 1, m + 1, inner, atol=12)
        trans = apply_effects(
            ws, source, [vfx.Margin(margin_size=m, color=border, opacity=0.0)]
        )
        lower_c = _rgb_away_from(inner, border)
        lower = _color(ws, (cw, ch), lower_c, duration=0.5)
        comp = _overlay(ws, [lower, trans])
        of = _frame(ws, comp, 0.0)
        _assert_color_at(of, 0, 0, lower_c, atol=18)
        _assert_color_at(of, m + 1, m + 1, inner, atol=18)


class TestF08_masks_and_is_pixelwise_minimum:
    def test_masks_and_is_pixelwise_minimum(self):
        with workspace() as ws:
            w, h = 8, 6
            a = _color(ws, (w, h), 0.8, duration=0.4, is_mask=True)
            b_arr = np.full((h, w), 0.3, dtype=float)
            b_arr[:, w // 2 :] = 0.9
            b = _video(ws, lambda t, arr=b_arr: arr.copy(), 0.4, is_mask=True)
            out = apply_effects(ws, a, [vfx.MasksAnd(b)])
            got = require_mask_picture(_frame(ws, out, 0.0), h, w)
            a0 = require_mask_picture(_frame(ws, a, 0.0), h, w)
            b0 = require_mask_picture(_frame(ws, b, 0.0), h, w)
            print(f"masks_and mean={float(got.mean()):.3f}", flush=True)
            assert np.allclose(got, np.minimum(a0, b0), atol=1e-5)


class TestF08_masks_or_is_pixelwise_maximum:
    def test_masks_or_is_pixelwise_maximum(self):
        with workspace() as ws:
            w, h = 8, 6
            a = _color(ws, (w, h), 0.2, duration=0.4, is_mask=True)
            b_arr = np.full((h, w), 0.4, dtype=float)
            b_arr[:, : w // 2] = 0.95
            b = _video(ws, lambda t, arr=b_arr: arr.copy(), 0.4, is_mask=True)
            out = apply_effects(ws, a, [vfx.MasksOr(b)])
            got = require_mask_picture(_frame(ws, out, 0.0), h, w)
            a0 = require_mask_picture(_frame(ws, a, 0.0), h, w)
            b0 = require_mask_picture(_frame(ws, b, 0.0), h, w)
            print(f"masks_or mean={float(got.mean()):.3f}", flush=True)
            assert np.allclose(got, np.maximum(a0, b0), atol=1e-5)


def test_mask_from_color_keys_matching_pixels():
    with workspace() as ws:
        w, h = 14, 10
        match = (20, 180, 20)
        near_c = (24, 184, 20)
        far_c = (220, 30, 200)
        pic = _solid(h, w, far_c)
        pic[:, : w // 3] = match
        pic[:, w // 3 : 2 * w // 3] = near_c
        upper = _still(ws, pic, 0.6)
        keyed = apply_effects(ws, upper, [vfx.MaskColor(color=match, threshold=80)])
        lower_c = _rgb_away_from(match, near_c, far_c)
        lower = _color(ws, (w, h), lower_c, duration=0.6)
        comp = _overlay(ws, [lower, keyed])
        frame = _frame(ws, comp, 0.0)
        near_px = _rgb_at(frame, w // 2, h // 2)
        far_px = _rgb_at(frame, w - 2, h // 2)
        print(
            f"maskcolor match={_rgb_at(frame, 1, h // 2)} near={near_px} far={far_px}",
            flush=True,
        )
        _assert_color_at(frame, 1, h // 2, lower_c, atol=22)
        assert _l1(near_px, lower_c) < _l1(near_px, near_c)
        assert _l1(far_px, far_c) < _l1(far_px, lower_c)


def test_painting_changes_the_picture():
    with workspace() as ws:
        w, h = 16, 12
        a, b = _rgb_away_from(), None
        b = _rgb_away_from(a)
        pic = _lr_picture(h, w, a, b)
        pic[2:5, 2:5] = _rgb_away_from(a, b)
        source = _still(ws, pic, 0.4)
        painted = apply_effects(ws, source, [vfx.Painting()])
        src_f, out_f = _frame(ws, source, 0.0), _frame(ws, painted, 0.0)
        print(
            f"painting src={_rgb_at(src_f, 3, 3)} out={_rgb_at(out_f, 3, 3)}",
            flush=True,
        )
        assert not pictures_equal(src_f, out_f)


class TestF08_scroll_moves_picture_over_time:
    def test_scroll_moves_picture_over_time(self):
        with workspace() as ws:
            w, h = 20, 12
            bg = _rgb_away_from()
            mark = _rgb_away_from(bg)
            pic = _solid(h, w, bg)
            mx, my, mw, mh = 8, 3, 4, 4
            pic[my : my + mh, mx : mx + mw] = mark
            source = _still(ws, pic, 1.0)
            speed = 8
            result = apply_effects(ws, source, [vfx.Scroll(x_speed=speed)])
            t0, t1 = 0.0, 0.4
            f0, f1 = _frame(ws, result, t0), _frame(ws, result, t1)
            print(
                f"scroll t0 mark@{(mx, my)}={_rgb_at(f0, mx, my)} "
                f"t1={_rgb_at(f1, mx, my)}",
                flush=True,
            )
            _assert_color_at(f0, mx + 1, my + 1, mark, atol=16)
            assert not pictures_equal(f0, f1)
            shifted_x = mx - int(round(speed * t1))
            if 0 <= shifted_x < w:
                _assert_color_at(f1, shifted_x + 1, my + 1, mark, atol=20)


class TestF08_super_sample_means_nearby_frames:
    def test_super_sample_means_nearby_frames(self):
        with workspace() as ws:
            w, h = 10, 8
            pre, post = _rgb_away_from(), None
            post = _rgb_away_from(pre)
            split = 0.5
            source = _two_tone(ws, (w, h), pre, post, split, 1.0)
            t = split
            d = 0.2
            n1 = apply_effects(ws, source, [vfx.SuperSample(d, 1)])
            n5 = apply_effects(ws, source, [vfx.SuperSample(d, 5)])
            f1, f5 = _frame(ws, n1, t), _frame(ws, n5, t)
            src_pre = _frame(ws, source, 0.0)
            src_post = _frame(ws, source, 0.9)
            print(
                f"supersample n1={_rgb_at(f1, 1, 1)} n5={_rgb_at(f5, 1, 1)} "
                f"pre={_rgb_at(src_pre, 1, 1)} post={_rgb_at(src_post, 1, 1)}",
                flush=True,
            )
            assert pictures_equal(f1, src_pre) or pictures_equal(f1, src_post)
            assert not pictures_equal(f5, src_pre)
            assert not pictures_equal(f5, src_post)
            assert not pictures_equal(f5, f1)


# ---------------------------------------------------------------------------
# J. Audio catalog
# ---------------------------------------------------------------------------


def test_oracle_multiply_volume_half_and_point_eight_and_zero():
    with workspace() as ws:
        amp = 0.64
        source = _audio(ws, _const_mono(amp), 0.6)
        orig = _sound(ws, source, 0.2)
        half = _sound(ws, apply_effects(ws, source, [afx.MultiplyVolume(0.5)]), 0.2)
        pt8 = _sound(ws, apply_effects(ws, source, [afx.MultiplyVolume(0.8)]), 0.2)
        zero = _sound(ws, apply_effects(ws, source, [afx.MultiplyVolume(0)]), 0.2)
        runtime_k = 0.3 + _rand_int(0, 20) / 100.0
        rk = _sound(ws, apply_effects(ws, source, [afx.MultiplyVolume(runtime_k)]), 0.2)
        print(
            f"volume orig={float(orig[0]):.3f} half={float(half[0]):.3f} "
            f"0.8={float(pt8[0]):.3f} k={runtime_k:.2f}",
            flush=True,
        )
        assert samples_close(half, orig * 0.5)
        assert samples_close(pt8, orig * 0.8)
        assert samples_close(zero, orig * 0.0)
        assert samples_close(rk, orig * runtime_k)


def test_multiply_volume_optional_time_window():
    with workspace() as ws:
        amp = 0.7
        source = _audio(ws, _const_mono(amp), 1.0)
        start_t, end_t = 0.3, 0.6
        k = 0.2
        out = apply_effects(
            ws, source, [afx.MultiplyVolume(k, start_time=start_t, end_time=end_t)]
        )
        inside = _pcm_at(ws, out, 0.45)[0]
        before = _pcm_at(ws, out, 0.1)[0]
        after = _pcm_at(ws, out, 0.8)[0]
        orig = _pcm_at(ws, source, 0.1)[0]
        print(
            f"vol_window in={float(inside[0]):.3f} before={float(before[0]):.3f}",
            flush=True,
        )
        assert samples_close(inside, orig * k)
        assert samples_close(before, orig)
        assert samples_close(after, orig)


def test_multiply_volume_on_video_soundtrack_leaves_picture_timing():
    with workspace() as ws:
        w, h = 10, 8
        first, second = _rgb_away_from(), None
        second = _rgb_away_from(first)
        video = _two_tone(ws, (w, h), first, second, 0.4, 1.0)
        audio = _audio(ws, _const_mono(0.5), 1.0)
        source = _attach_audio(ws, video, audio)
        out = apply_effects(ws, source, [afx.MultiplyVolume(0.4)])
        print(
            f"vol_on_video pic_equal={pictures_equal(_frame(ws, out, 0.55), _frame(ws, source, 0.55))}",
            flush=True,
        )
        assert pictures_equal(_frame(ws, out, 0.2), _frame(ws, source, 0.2))
        assert pictures_equal(_frame(ws, out, 0.7), _frame(ws, source, 0.7))
        assert samples_close(_soundtrack(ws, out, 0.2), _soundtrack(ws, source, 0.2) * 0.4)


class TestF08_non_volume_audio_effect_on_video_leaves_picture_timing:
    def test_non_volume_audio_effect_on_video_leaves_picture_timing(self):
        with workspace() as ws:
            w, h = 10, 8
            first, second = _rgb_away_from(), None
            second = _rgb_away_from(first)
            video = _two_tone(ws, (w, h), first, second, 0.4, 1.0)
            audio = _audio(ws, _pulse_mono(0.8, 0.03), 1.0)
            source = _attach_audio(ws, video, audio)
            out = apply_effects(ws, source, [afx.AudioDelay(offset=0.2, n_repeats=2, decay=0.5)])
            t_pic = 0.55
            print(
                f"delay_on_video duration={duration_or_missing(out)} "
                f"pic={_rgb_at(_frame(ws, out, t_pic), 1, 1)}",
                flush=True,
            )
            assert duration_or_missing(out) == duration_or_missing(source)
            assert not pictures_equal(_frame(ws, source, t_pic), _frame(ws, source, 0.1))
            assert pictures_equal(_frame(ws, out, t_pic), _frame(ws, source, t_pic))
            assert pictures_equal(_frame(ws, out, 0.1), _frame(ws, source, 0.1))
            delayed = abs(float(_soundtrack(ws, out, 0.2)[0]))
            orig_late = abs(float(_soundtrack(ws, source, 0.2)[0]))
            orig_pulse = abs(float(_soundtrack(ws, source, 0.01)[0]))
            assert orig_pulse > orig_late + 0.05
            assert delayed > orig_late + 0.05


def test_audio_delay_repeats_quieter():
    with workspace() as ws:
        offset = 0.12
        source = _audio(ws, _pulse_mono(0.85, 0.02), 1.0)
        small = apply_effects(ws, source, [afx.AudioDelay(offset=offset, n_repeats=1, decay=0.4)])
        large = apply_effects(ws, source, [afx.AudioDelay(offset=offset, n_repeats=4, decay=0.4)])
        late = 4 * offset
        e_small = abs(float(_sound(ws, small, late)[0]))
        e_large = abs(float(_sound(ws, large, late)[0]))
        print(f"delay late={late:.2f} small={e_small:.3f} large={e_large:.3f}", flush=True)
        assert e_large > 0.05
        assert e_small < 0.03
        a = apply_effects(ws, source, [afx.AudioDelay(offset=offset, n_repeats=3, decay=0.2)])
        b = apply_effects(ws, source, [afx.AudioDelay(offset=offset, n_repeats=3, decay=0.8)])
        slot = 2 * offset
        va, vb = abs(float(_sound(ws, a, slot)[0])), abs(float(_sound(ws, b, slot)[0]))
        assert abs(va - vb) > 0.04


def test_audio_fade_in_from_silence():
    with workspace() as ws:
        amp, fade_d = 0.7, 0.4
        source = _audio(ws, _const_mono(amp), 1.0)
        out = apply_effects(ws, source, [afx.AudioFadeIn(fade_d)])
        a0 = abs(float(_sound(ws, out, 0.02)[0]))
        amid = abs(float(_sound(ws, out, fade_d * 0.4)[0]))
        after = abs(float(_sound(ws, out, fade_d + 0.1)[0]))
        print(f"afadein 0={a0:.3f} mid={amid:.3f} after={after:.3f}", flush=True)
        assert a0 < after - 0.2
        assert 0.05 < amid < after - 0.05


def test_audio_fade_out_to_silence():
    with workspace() as ws:
        amp, fade_d = 0.7, 0.5
        source = _audio(ws, _const_mono(amp), fade_d)
        out = apply_effects(ws, source, [afx.AudioFadeOut(fade_d)])
        a0 = abs(float(_sound(ws, out, 0.02)[0]))
        amid = abs(float(_sound(ws, out, fade_d * 0.4)[0]))
        aend = abs(float(_sound(ws, out, fade_d * 0.96)[0]))
        print(f"afadeout 0={a0:.3f} mid={amid:.3f} end={aend:.3f}", flush=True)
        assert a0 > aend + 0.2
        assert 0.05 < amid < a0 - 0.05


class TestF08_audio_loop_sets_looped_length:
    def test_audio_loop_sets_looped_length(self):
        with workspace() as ws:
            src_d = 0.3
            pulse_w = 0.04
            source = _audio(ws, _pulse_mono(0.7, pulse_w), src_d)
            n = 3
            n_short = 2
            counted = apply_effects(ws, source, [afx.AudioLoop(n_loops=n)])
            counted_short = apply_effects(ws, source, [afx.AudioLoop(n_loops=n_short)])
            total = 0.7
            timed = apply_effects(ws, source, [afx.AudioLoop(duration=total)])
            cd = duration_or_missing(counted)
            cd_short = duration_or_missing(counted_short)
            td = duration_or_missing(timed)
            t_pulse = src_d + 0.01
            t_quiet = src_d + src_d * 0.5
            src_pulse = _sound(ws, source, 0.01)
            src_quiet = _sound(ws, source, src_d * 0.5)
            counted_pulse = _sound(ws, counted, t_pulse)
            counted_quiet = _sound(ws, counted, t_quiet)
            timed_pulse = _sound(ws, timed, t_pulse)
            timed_quiet = _sound(ws, timed, t_quiet)
            print(
                f"aloop cd={cd} cd_short={cd_short} td={td} "
                f"counted_pulse={float(counted_pulse[0]):.3f} "
                f"timed_quiet={float(timed_quiet[0]):.3f}",
                flush=True,
            )
            assert cd is not None and abs(cd - n * src_d) < 1e-6
            assert cd_short is not None and abs(cd_short - n_short * src_d) < 1e-6
            assert abs(cd - cd_short) > src_d * 0.5
            assert td is not None and abs(td - total) < 1e-6
            assert abs(total - n_short * src_d) > 1e-6
            assert samples_close(counted_pulse, src_pulse)
            assert samples_close(counted_quiet, src_quiet)
            assert samples_close(timed_pulse, src_pulse)
            assert samples_close(timed_quiet, src_quiet)
            assert abs(float(counted_pulse[0])) > 0.2
            assert abs(float(timed_pulse[0])) > 0.2
            assert abs(float(counted_quiet[0])) < 0.05
            assert abs(float(timed_quiet[0])) < 0.05


class TestF08_audio_loop_without_count_or_duration_does_not_succeed:
    def test_audio_loop_without_count_or_duration_does_not_succeed(self):
        with workspace() as ws:
            src_d = 0.4
            source = _audio(ws, _const_mono(0.4), src_d)
            ok = apply_effects(ws, source, [afx.AudioLoop(n_loops=2)])
            failed = ws.call(source.with_effects, [afx.AudioLoop()])
            ok_d = duration_or_missing(ok)
            print(
                f"aloop_missing ok_d={ok_d} failed={failed.exception is not None}",
                flush=True,
            )
            require_failed(failed)
            assert ok_d is not None and abs(ok_d - 2 * src_d) < 1e-6
            assert samples_close(_sound(ws, ok, src_d + 0.02), _sound(ws, source, 0.02))


class TestF08_normalize_scales_peak_to_full_scale:
    def test_normalize_scales_peak_to_full_scale(self):
        with workspace() as ws:
            quiet = _audio(ws, _const_mono(0.35), 0.4)
            full = _audio(ws, _const_mono(1.0), 0.4)
            nq = apply_effects(ws, quiet, [afx.AudioNormalize()])
            nf = apply_effects(ws, full, [afx.AudioNormalize()])
            q = abs(float(_sound(ws, nq, 0.1)[0]))
            f = abs(float(_sound(ws, nf, 0.1)[0]))
            orig_f = abs(float(_sound(ws, full, 0.1)[0]))
            print(f"normalize quiet->{q:.3f} full->{f:.3f}", flush=True)
            assert q > 0.9
            assert abs(f - orig_f) < 0.05


class TestF08_multiply_stereo_volume_independent_channels:
    def test_multiply_stereo_volume_independent_channels(self):
        with workspace() as ws:
            source = _audio(ws, _const_stereo(0.8, 0.8), 0.5)
            left_only = apply_effects(ws, source, [afx.MultiplyStereoVolume(left=0.2, right=1.0)])
            right_only = apply_effects(ws, source, [afx.MultiplyStereoVolume(left=1.0, right=0.2)])
            a = _pcm_at(ws, left_only, 0.1).mean(axis=0)
            b = _pcm_at(ws, right_only, 0.1).mean(axis=0)
            print(f"stereo left={a} right_arm={b}", flush=True)
            assert a.shape == (2,) and b.shape == (2,)
            assert abs(float(a[0]) - 0.16) < 0.05
            assert abs(float(a[1]) - 0.8) < 0.05
            assert abs(float(b[0]) - 0.8) < 0.05
            assert abs(float(b[1]) - 0.16) < 0.05
            assert abs(float(a[0]) - float(b[0])) > 0.3


def test_audio_effect_on_video_without_soundtrack_does_not_invent_samples():
    with workspace() as ws:
        w, h = 10, 8
        color = _rgb_away_from()
        bare = _color(ws, (w, h), color, duration=0.6)
        with_a = _attach_audio(ws, bare, _audio(ws, _const_mono(0.5), 0.6))
        changed = apply_effects(ws, with_a, [afx.MultiplyVolume(0.3)])
        assert not samples_close(_soundtrack(ws, changed, 0.2), _soundtrack(ws, with_a, 0.2))
        assert _no_soundtrack(bare)
        out = apply_effects(ws, bare, [afx.MultiplyVolume(0.3)])
        print(
            f"no_soundtrack still_none={_no_soundtrack(out)} pic_same="
            f"{pictures_equal(_frame(ws, out, 0.1), _frame(ws, bare, 0.1))}",
            flush=True,
        )
        assert _no_soundtrack(out)
        require_rgb_picture(_frame(ws, out, 0.1), h, w, color=color)


# ---------------------------------------------------------------------------
# K. Time / picture / joint / sound filters
# ---------------------------------------------------------------------------


class TestF08_time_only_filter_t_to_2t_plays_twice_as_fast:
    def test_time_only_filter_t_to_2t_plays_twice_as_fast(self):
        with workspace() as ws:
            first, second = _rgb_away_from(), None
            second = _rgb_away_from(first)
            source = _two_tone(ws, (10, 8), first, second, 1.0, 2.0)
            src_early, src_late = _frame(ws, source, 0.5), _frame(ws, source, 1.0)
            assert not pictures_equal(src_early, src_late)
            result = require_ok(ws.call(source.time_transform, lambda t: 2 * t))
            # Same t→2t map through the joint filter entry (frame-at-time, time).
            via_joint = require_ok(
                ws.call(source.transform, lambda get_frame, t: get_frame(2 * t))
            )
            got = _frame(ws, result, 0.5)
            print(
                f"t_to_2t t0.5={_rgb_at(got, 1, 1)} "
                f"src_t1={_rgb_at(src_late, 1, 1)}",
                flush=True,
            )
            assert pictures_equal(got, src_late)
            assert not pictures_equal(got, src_early)
            assert pictures_equal(_frame(ws, via_joint, 0.5), src_late)
            assert not pictures_equal(_frame(ws, via_joint, 0.5), src_early)


class TestF08_time_only_on_animated_leaves_mask_and_audio_unless_asked:
    def test_time_only_on_animated_leaves_mask_and_audio_unless_asked(self):
        with workspace() as ws:
            w, h = 10, 8
            first, second = _rgb_away_from(), None
            second = _rgb_away_from(first)
            source = _two_tone(ws, (w, h), first, second, 1.0, 2.0)
            mask = _two_tone(ws, (w, h), 0.2, 0.9, 1.0, 2.0, is_mask=True)
            audio = _audio(ws, lambda t: 0.15 + 0.7 * (np.asarray(t) >= 1.0), 2.0)
            source = _attach_audio(ws, _attach_mask(ws, source, mask), audio)
            defaulted = require_ok(ws.call(source.time_transform, lambda t: 2 * t))
            mapped = require_ok(
                ws.call(source.time_transform, lambda t: 2 * t, apply_to=["mask", "audio"])
            )
            t = 0.5
            assert not pictures_equal(_frame(ws, source, t), _frame(ws, source, 1.0))
            print(
                f"time_anim default mask={float(require_mask_picture(_frame(ws, defaulted.mask, t), h, w).mean()):.3f}",
                flush=True,
            )
            assert pictures_equal(_frame(ws, defaulted, t), _frame(ws, source, 1.0))
            assert pictures_equal(
                require_mask_picture(_frame(ws, defaulted.mask, t), h, w),
                require_mask_picture(_frame(ws, source.mask, t), h, w),
            )
            assert samples_close(_soundtrack(ws, defaulted, t), _soundtrack(ws, source, t))
            assert pictures_equal(
                require_mask_picture(_frame(ws, mapped.mask, t), h, w),
                require_mask_picture(_frame(ws, source.mask, 1.0), h, w),
            )
            assert samples_close(_soundtrack(ws, mapped, t), _soundtrack(ws, source, 1.0))


class TestF08_time_only_on_still_maps_mask_and_audio_picture_unchanged:
    def test_time_only_on_still_maps_mask_and_audio_picture_unchanged(self):
        with workspace() as ws:
            w, h = 10, 8
            still_c = _rgb_away_from()
            still = _color(ws, (w, h), still_c, duration=2.0)
            mask = _two_tone(ws, (w, h), 0.2, 0.9, 1.0, 2.0, is_mask=True)
            audio = _audio(ws, lambda t: 0.15 + 0.7 * (np.asarray(t) >= 1.0), 2.0)
            still = _attach_audio(ws, _attach_mask(ws, still, mask), audio)
            defaulted = require_ok(ws.call(still.time_transform, lambda t: 2 * t))
            opted = require_ok(ws.call(still.time_transform, lambda t: 2 * t, apply_to=[]))
            t = 0.5
            print(
                f"time_still default_mask={float(require_mask_picture(_frame(ws, defaulted.mask, t), h, w).mean()):.3f}",
                flush=True,
            )
            require_rgb_picture(_frame(ws, defaulted, t), h, w, color=still_c)
            require_rgb_picture(_frame(ws, defaulted, 0.1), h, w, color=still_c)
            assert pictures_equal(
                require_mask_picture(_frame(ws, defaulted.mask, t), h, w),
                require_mask_picture(_frame(ws, still.mask, 1.0), h, w),
            )
            assert samples_close(_soundtrack(ws, defaulted, t), _soundtrack(ws, still, 1.0))
            assert pictures_equal(
                require_mask_picture(_frame(ws, opted.mask, t), h, w),
                require_mask_picture(_frame(ws, still.mask, t), h, w),
            )
            assert samples_close(_soundtrack(ws, opted, t), _soundtrack(ws, still, t))


def _swap_gb(pic):
    arr = np.array(pic, copy=True)
    arr[..., 1], arr[..., 2] = pic[..., 2].copy(), pic[..., 1].copy()
    return arr


def test_picture_only_channel_swap_visible_and_stable_on_still():
    with workspace() as ws:
        color = (10, 200, 40)
        swapped_c = (10, 40, 200)
        still = _color(ws, (10, 8), color, duration=1.0)
        out = require_ok(ws.call(still.image_transform, _swap_gb))
        a, b = _frame(ws, out, 0.1), _frame(ws, out, 0.7)
        print(f"pic_still swap={_rgb_at(a, 1, 1)}", flush=True)
        require_rgb_picture(a, 8, 10, color=swapped_c)
        assert pictures_equal(a, b)


class TestF08_picture_only_channel_swap_runs_on_each_animated_frame:
    def test_picture_only_channel_swap_runs_on_each_animated_frame(self):
        with workspace() as ws:
            w, h = 10, 8
            first, second = (10, 200, 40), (10, 40, 200)
            source = _two_tone(ws, (w, h), first, second, 0.4, 1.0)
            out = require_ok(ws.call(source.image_transform, _swap_gb))
            t0, t1 = 0.1, 0.7
            src0, src1 = _frame(ws, source, t0), _frame(ws, source, t1)
            print(
                f"pic_anim t0={_rgb_at(_frame(ws, out, t0), 1, 1)} t1={_rgb_at(_frame(ws, out, t1), 1, 1)}",
                flush=True,
            )
            require_rgb_picture(src0, h, w, color=first)
            require_rgb_picture(src1, h, w, color=second)
            assert not pictures_equal(src0, src1)
            require_rgb_picture(_frame(ws, out, t0), h, w, color=(10, 40, 200))
            require_rgb_picture(_frame(ws, out, t1), h, w, color=(10, 200, 40))
            assert not pictures_equal(_frame(ws, out, t0), _frame(ws, out, t1))
            assert not pictures_equal(_frame(ws, out, t0), src0)
            assert not pictures_equal(_frame(ws, out, t1), src1)


class TestF08_joint_filter_vertical_window_is_time_dependent_crop:
    def test_joint_filter_vertical_window_is_time_dependent_crop(self):
        with workspace() as ws:
            w, h = 12, 24
            top_c, bot_c = _rgb_away_from(), None
            bot_c = _rgb_away_from(top_c)
            pic = _tb_picture(h, w, top_c, bot_c)
            source = _still(ws, pic, 1.0)
            win = 6

            def joint(get_frame, t):
                frame = get_frame(t)
                y0 = 0 if _scalar_t(t) < 0.4 else h - win
                return frame[y0 : y0 + win, :]

            out = require_ok(ws.call(source.transform, joint))
            early, late = _frame(ws, out, 0.1), _frame(ws, out, 0.7)
            src = _picture_rgb(_frame(ws, source, 0.0))
            print(
                f"joint early={_frame_size(early)} late={_frame_size(late)} "
                f"e={_rgb_at(early, 1, 1)} l={_rgb_at(late, 1, 1)}",
                flush=True,
            )
            assert _frame_size(early) == (w, win)
            assert not pictures_equal(early, late)
            assert pictures_equal(early, src[0:win, :])
            assert pictures_equal(late, src[h - win : h, :])


class TestF08_sound_only_filter_scales_samples:
    def test_sound_only_filter_scales_samples(self):
        with workspace() as ws:
            amp = 0.55
            k = 0.3 + _rand_int(0, 25) / 100.0
            source = _audio(ws, _const_mono(amp), 0.5)
            out = require_ok(ws.call(source.transform, lambda get_frame, t: k * get_frame(t)))
            orig, got = _sound(ws, source, 0.2), _sound(ws, out, 0.2)
            print(f"sound_filter k={k:.2f} orig={float(orig[0]):.3f} got={float(got[0]):.3f}", flush=True)
            assert samples_close(got, orig * k)


# ---------------------------------------------------------------------------
# L. Custom effect through the same list
# ---------------------------------------------------------------------------


def test_custom_effect_applies_through_same_list_as_builtins():
    with workspace() as ws:
        bar = _rgb_away_from(_RED, _CYAN)
        source = _color(ws, (20, 16), _RED, duration=1.0)
        custom = progress_bar_effect(bar)
        assert isinstance(custom, Effect)
        both = apply_effects(ws, source, [custom, vfx.InvertColors()])
        frame = _frame(ws, both, 0.8)
        print(f"custom+invert sample={_rgb_at(frame, 10, 2)} bottom={_rgb_at(frame, 2, 15)}", flush=True)
        # Invert happened (top stays near cyan, not red) and the bar is present.
        _assert_color_at(frame, 10, 2, _CYAN, atol=14)
        bottom = _rgb_at(frame, 2, 15)
        inverted_bar = tuple(255 - c for c in bar)
        assert _near(bottom, inverted_bar, atol=20) or _near(bottom, bar, atol=20)


class TestF08_oracle_progress_bar_empty_at_zero_complete_near_duration:
    def test_oracle_progress_bar_empty_at_zero_complete_near_duration(self):
        with workspace() as ws:
            w, h = 24, 16
            src_c = _rgb_away_from()
            bar = _rgb_away_from(src_c)
            source = _color(ws, (w, h), src_c, duration=1.0)
            out = apply_effects(ws, source, [progress_bar_effect(bar)])
            t0, t_late = 0.0, 0.92
            f0, fl = _frame(ws, out, t0), _frame(ws, out, t_late)
            bar_h = max(2, h // 8)
            top0 = _rgb_at(f0, w // 2, 1)
            bot0 = _picture_rgb(f0)[h - 1, :, :]
            botl = _picture_rgb(fl)[h - 1, :, :]
            filled0 = float(np.mean(np.linalg.norm(bot0.astype(float) - np.array(bar), axis=-1) < 30))
            filledl = float(np.mean(np.linalg.norm(botl.astype(float) - np.array(bar), axis=-1) < 30))
            print(f"progress filled0={filled0:.3f} filled_late={filledl:.3f}", flush=True)
            _assert_color_at(f0, w // 2, 1, src_c, atol=12)
            _assert_color_at(fl, w // 2, 1, src_c, atol=12)
            assert filled0 < 0.15
            assert filledl > 0.8
            assert filledl > filled0 + 0.5
            assert top0 != bar
            # Bar lives on the bottom strip.
            _assert_color_at(fl, w // 2, h - 1, bar, atol=18)


