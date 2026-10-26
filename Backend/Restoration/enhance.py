from __future__ import annotations

import cv2
import numpy as np


def denoise(image: np.ndarray, strength: int = 7) -> np.ndarray:
    if strength <= 0:
        return image
    if image.ndim == 2:
        return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)
    return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)


def correct_fading(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)


def sharpen(image: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (0, 0), 1.2)
    return cv2.addWeighted(image, 1.18, blurred, -0.18, 0)


def restore_color_balance(image: np.ndarray, strength: float = 0.35) -> np.ndarray:
    """Gently restore chroma balance for colour photographs.

    This is not colourization and is intentionally disabled for grayscale
    images. It only prevents faded colour channels from looking desaturated.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        return image
    strength = float(np.clip(strength, 0.0, 1.0))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    saturation = hsv[:, :, 1]
    target = np.percentile(saturation, 75)
    if target <= 1.0:
        return image
    hsv[:, :, 1] = np.clip(saturation + (target - saturation) * strength * 0.18, 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def enhance_full_photo(
    image: np.ndarray,
    denoise_strength: int = 0,
    fading: bool = False,
    color_restore: bool = False,
    sharpen_enabled: bool = False,
) -> np.ndarray:
    """Explicit full-photo enhancement; never used by localized mode."""
    output = image.copy()
    if denoise_strength > 0:
        output = denoise(output, denoise_strength)
    if fading:
        output = correct_fading(output)
    if color_restore:
        output = restore_color_balance(output)
    if sharpen_enabled:
        output = sharpen(output)
    return output
