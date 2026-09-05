# feature: F07
"""F07 observation helpers: greyscale frames that may leave 0–1, and PNG alpha."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from _harness import HarnessError
from _helpers import as_numeric_array


def require_greyscale_frame(frame: Any, height: int, width: int) -> np.ndarray:
    """Require a height×width 2-D numeric frame. Values may leave 0–1."""
    arr = as_numeric_array(frame)
    if arr.ndim != 2 or arr.shape[0] != height or arr.shape[1] != width:
        raise AssertionError(
            f"expected greyscale frame shape {(height, width)}; got {arr.shape}"
        )
    return arr


def read_png_rgb_and_alpha(path: str | Path) -> tuple[np.ndarray, np.ndarray | None]:
    """Open a product-written PNG with a still-image library.

    Open/decode failure raises. A successful 3-channel image has alpha
    ``None`` (format has no alpha layer). A successful 4th channel is
    returned as that channel. IO failure is never mapped to “no alpha”.
    """
    src = Path(path)
    try:
        if not src.exists():
            raise FileNotFoundError(f"PNG does not exist: {src}")
        if not src.is_file():
            raise HarnessError(f"path exists but is not a regular file: {src}")
    except FileNotFoundError:
        raise
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot stat PNG {src}: {exc}") from exc

    try:
        from PIL import Image
    except ImportError as exc:
        raise HarnessError(f"Pillow is required to read PNG files: {exc}") from exc

    try:
        image = Image.open(src)
        image.load()
    except Exception as exc:
        raise HarnessError(f"cannot decode PNG {src}: {exc}") from exc

    arr = np.asarray(image)
    if arr.ndim == 2:
        rgb = np.stack([arr, arr, arr], axis=-1)
        return rgb, None
    if arr.ndim != 3:
        raise HarnessError(
            f"decoded PNG is not an image array; shape={arr.shape!r} path={src}"
        )
    channels = arr.shape[2]
    if channels == 4:
        return arr[:, :, :3], arr[:, :, 3]
    if channels == 3:
        return arr[:, :, :3], None
    if channels == 2:
        grey = arr[:, :, 0]
        rgb = np.stack([grey, grey, grey], axis=-1)
        return rgb, arr[:, :, 1]
    raise HarnessError(
        f"decoded PNG has unexpected channel count {channels}; path={src}"
    )
