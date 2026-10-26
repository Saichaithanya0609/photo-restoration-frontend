"""Image denoising algorithms for the Photo Restoration project."""
from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np


SUPPORTED_METHODS = ("median", "gaussian", "nlm")


def denoise_image(
    image: np.ndarray,
    method: str = "nlm",
    strength: int = 58,
) -> np.ndarray:
    """
    Denoise an OpenCV image without modifying the input.

    Args:
        image: Grayscale (H, W) or BGR color (H, W, 3) uint8 image.
        method: 'median', 'gaussian', or 'nlm'.
        strength: Integer from 0 (no denoising) to 100 (stronger denoising).

    Returns:
        A denoised image with the same shape and dtype as the input.
    """
    if image is None or not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Input image is empty or invalid.")

    if image.dtype != np.uint8:
        raise ValueError("Expected an 8-bit image (uint8). Convert the image before denoising.")

    if image.ndim not in (2, 3) or (image.ndim == 3 and image.shape[2] not in (3, 4)):
        raise ValueError("Expected a grayscale, BGR, or BGRA image.")

    method = method.strip().lower()
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"Unknown method '{method}'. Choose from: {', '.join(SUPPORTED_METHODS)}.")

    strength = int(np.clip(strength, 0, 100))
    source = image.copy()

    if strength == 0:
        return source

    # OpenCV's denoising functions work on grayscale or 3-channel BGR.
    has_alpha = source.ndim == 3 and source.shape[2] == 4
    alpha = source[:, :, 3].copy() if has_alpha else None
    working = source[:, :, :3].copy() if has_alpha else source

    if method == "median":
        # Odd kernel sizes are required by medianBlur.
        kernel = 3 if strength <= 35 else 5 if strength <= 70 else 7
        result = cv2.medianBlur(working, kernel)

    elif method == "gaussian":
        # Increasing sigma applies progressively stronger smoothing.
        sigma = 0.3 + (strength / 100.0) * 2.7
        result = cv2.GaussianBlur(working, (0, 0), sigmaX=sigma, sigmaY=sigma)

    else:  # Non-Local Means
        h = 2.0 + (strength / 100.0) * 13.0
        if working.ndim == 2:
            result = cv2.fastNlMeansDenoising(working, None, h, 7, 21)
        else:
            result = cv2.fastNlMeansDenoisingColored(
                working, None, h, h, templateWindowSize=7, searchWindowSize=21
            )

    if has_alpha:
        result = cv2.cvtColor(result, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = alpha

    return result


def process_and_measure(
    image: np.ndarray,
    method: str,
    strength: int = 58,
) -> tuple[np.ndarray, float]:
    """Return (processed_image, elapsed_seconds)."""
    start = time.perf_counter()
    result = denoise_image(image, method, strength)
    elapsed = time.perf_counter() - start
    return result, elapsed


def calculate_psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    """Calculate PSNR in dB for same-size images; requires a clean reference."""
    if reference.shape != candidate.shape:
        raise ValueError("Reference and candidate must have identical shapes.")
    return float(cv2.PSNR(reference, candidate))


def calculate_ssim(reference: np.ndarray, candidate: np.ndarray) -> float:
    """
    Calculate SSIM using scikit-image.
    Install scikit-image to use this optional metric.
    """
    from skimage.metrics import structural_similarity

    if reference.shape != candidate.shape:
        raise ValueError("Reference and candidate must have identical shapes.")

    if reference.ndim == 3:
        return float(
            structural_similarity(
                reference, candidate, channel_axis=2, data_range=255
            )
        )
    return float(structural_similarity(reference, candidate, data_range=255))
