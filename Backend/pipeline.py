"""Coordinate denoising and damage restoration."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from PIL import Image

from image_processor import denoise_image
from Restoration.enhance import enhance_full_photo
from Restoration.pipeline import _make_red_overlay_bgr, restore_image


def process_image(
    image: np.ndarray,
    *,
    denoise_enabled: bool = False,
    denoise_method: str = "nlm",
    denoise_strength: int = 25,
    detection_sensitivity: float = 1.0,
    bright_cracks: bool = True,
    dark_cracks: bool = False,
    detect_dust: bool = False,
    fading: bool = True,
    color_restore: bool = True,
    sharpen_enabled: bool = True,
    return_details: bool = False,
) -> np.ndarray | dict[str, Any]:
    """Restore a BGR uint8 image and return either a BGR uint8 image or details dict.

    When selected, light denoising runs before the restoration package's
    crack detection and inpainting. Otherwise the original pixels go directly
    to restoration.
    Full-photo contrast, color, and sharpening enhancement runs after
    restoration, independently of the optional denoising choice.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Input image is empty or invalid.")
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected an 8-bit, three-channel BGR image.")

    working_image = image
    if denoise_enabled:
        working_image = denoise_image(
            image, method=denoise_method, strength=denoise_strength
        )
        if working_image.shape != image.shape or working_image.dtype != np.uint8:
            raise ValueError("Denoising must return a uint8 image with the input dimensions.")

    # The restoration package takes a PIL image and returns a RestorationResult.
    working_rgb = cv2.cvtColor(working_image, cv2.COLOR_BGR2RGB)
    working_pil = Image.fromarray(working_rgb)
    restoration = restore_image(
        working_pil,
        sensitivity=detection_sensitivity,
        bright_cracks=bright_cracks,
        dark_cracks=dark_cracks,
        detect_dust_marks=detect_dust,
    )
    if not isinstance(restoration.image, Image.Image):
        raise ValueError("The restoration pipeline returned an invalid image.")

    restored_rgb = np.asarray(restoration.image.convert("RGB"))
    restored_bgr = cv2.cvtColor(restored_rgb, cv2.COLOR_RGB2BGR)
    if restored_bgr.shape != image.shape:
        raise ValueError("Restoration changed the image dimensions unexpectedly.")

    # Keep enhancement in the existing BGR uint8 format.
    enhanced_bgr = enhance_full_photo(
        restored_bgr,
        fading=fading,
        color_restore=color_restore,
        sharpen_enabled=sharpen_enabled,
    )
    if enhanced_bgr.shape != image.shape or enhanced_bgr.dtype != np.uint8:
        raise ValueError("Enhancement must return a uint8 image with the input dimensions.")

    if not return_details:
        return enhanced_bgr

    mask_obj = getattr(restoration, "mask", None)
    if mask_obj is not None:
        mask_np = np.asarray(mask_obj)
        if mask_np.dtype != np.uint8:
            mask_np = (mask_np > 0).astype(np.uint8) * 255
    else:
        mask_np = np.zeros(image.shape[:2], dtype=np.uint8)

    overlay_bgr = _make_red_overlay_bgr(image, mask_np)

    return {
        "restored_bgr": enhanced_bgr,
        "mask_np": mask_np,
        "overlay_bgr": overlay_bgr,
        "coverage": float(getattr(restoration, "mask_coverage", 0.0)),
        "steps": list(getattr(restoration, "steps", [])),
        "warning": getattr(restoration, "warning", None),
        "backend_used": getattr(restoration, "backend_used", "none"),
    }

