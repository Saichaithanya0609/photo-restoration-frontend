from __future__ import annotations

import cv2
import numpy as np

from .detect_cracks import detect_cracks


def detect_scratches(
    gray: np.ndarray,
    strength: float = 1.0,
    sensitivity: float | None = None,
    detect_dark: bool = False,
    *,
    include_dark: bool | None = None,
    dark: bool | None = None,
    expansion: float = 0.0,
) -> np.ndarray:
    """Compatibility wrapper for bright and optional dark crack detection."""
    return detect_cracks(
        gray,
        strength=strength,
        sensitivity=sensitivity,
        detect_dark=detect_dark,
        include_dark=include_dark,
        dark=dark,
        expansion=expansion,
    )
