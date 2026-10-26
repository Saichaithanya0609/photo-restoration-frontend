from __future__ import annotations

import cv2
import numpy as np
from PIL import Image


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_to_pil(image: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(np.clip(image, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def luminance(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def normalize_luminance(gray: np.ndarray) -> np.ndarray:
    """Return a safe uint8 copy for detection without global contrast remapping.

    The old implementation divided by a blurred image and then globally
    min-max-normalised it. That made ordinary bright facial and background
    detail look like damage. Detection now uses the original luminance; this
    helper remains for API compatibility and only validates/copies it.
    """
    return np.clip(gray, 0, 255).astype(np.uint8, copy=True)
