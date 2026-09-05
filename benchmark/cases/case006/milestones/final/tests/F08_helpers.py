# feature: F08
"""F08 helpers: apply an effect list, read duration, custom progress-bar effect."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from clipkit import Effect

from _helpers import require_ok


def apply_effects(ws, clip, effects: Sequence[Any]):
    """Apply *effects* through the public list entry. Failure raises."""
    return require_ok(ws.call(clip.with_effects, list(effects)))


def duration_or_missing(clip) -> float | None:
    """Clip duration, or None when the clip has none. Access failure raises."""
    return clip.duration


def progress_bar_effect(bar_color):
    """Caller-defined effect: read duration and draw a bar along the bottom."""
    color = tuple(int(c) for c in bar_color)

    class ProgressBar(Effect):
        def __init__(self, bar_color=color):
            self.bar_color = bar_color

        def apply(self, clip):
            duration = clip.duration
            rgb = np.asarray(self.bar_color, dtype=np.uint8).reshape(3)

            def filter(get_frame, t):
                frame = np.array(get_frame(t), copy=True)
                height, width = int(frame.shape[0]), int(frame.shape[1])
                bar_h = max(2, height // 8)
                tt = float(np.asarray(t).reshape(-1)[0])
                if duration is None or float(duration) <= 0:
                    frac = 0.0
                else:
                    frac = min(1.0, max(0.0, tt / float(duration)))
                filled = int(round(frac * width))
                if filled > 0 and frame.ndim >= 3 and frame.shape[2] >= 3:
                    frame[height - bar_h :, :filled, :3] = rgb
                return frame

            return clip.transform(filter)

    return ProgressBar()
