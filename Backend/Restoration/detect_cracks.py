from __future__ import annotations

import cv2
import numpy as np

from .refine_mask import refine_mask


def _line_kernel(length: int, angle: int) -> np.ndarray:
    size = max(3, int(length) | 1)
    kernel = np.zeros((size, size), dtype=np.uint8)
    centre = size // 2
    radians = np.deg2rad(angle)
    dx, dy = int(np.cos(radians) * centre), int(np.sin(radians) * centre)
    cv2.line(kernel, (centre - dx, centre - dy), (centre + dx, centre + dy), 1, 1)
    return kernel


def _robust_threshold(values: np.ndarray, sensitivity: float) -> float:
    """Use a high response quantile so texture is not damage by default."""
    finite = values[np.isfinite(values) & (values > 0)]
    if finite.size == 0:
        return 255.0
    level = float(np.clip((sensitivity - 0.25) / 1.75, 0.0, 1.0))
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    quantile = float(np.quantile(finite, 0.985 - 0.055 * level))
    return min(float(np.max(finite)), max(7.0 / sensitivity, quantile, median + 3.0 * mad / sensitivity))


def _contrast_threshold(values: np.ndarray, sensitivity: float) -> float:
    """Find a high local-contrast floor while retaining faded scratches."""
    positive = values[np.isfinite(values) & (values > 0)]
    if positive.size == 0:
        return 255.0
    level = float(np.clip((sensitivity - 0.25) / 1.75, 0.0, 1.0))
    quantile = float(np.quantile(positive, 0.985 - 0.055 * level))
    return max(8.0 / sensitivity, quantile * 0.78)


def _shift(image: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift an image without introducing a constant-valued border."""
    height, width = image.shape[:2]
    matrix = np.float32([[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]])
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT101,
    )


def _noise_level(gray: np.ndarray) -> float:
    """Estimate small-scale luminance noise without being driven by a crack."""
    values = gray.astype(np.float32)
    smooth = cv2.GaussianBlur(values, (0, 0), sigmaX=2.0)
    residual = np.abs(values - smooth)
    median = float(np.median(residual))
    return max(0.5, 1.4826 * median)


def _close_fragments(mask: np.ndarray, sensitivity: float) -> np.ndarray:
    """Reconnect short response gaps while preserving line-like geometry."""
    if not np.any(mask):
        return mask
    level = float(np.clip((sensitivity - 0.25) / 1.75, 0.0, 1.0))
    max_gap = 1 + int(round(level * 2.0))
    result = mask.copy()
    for angle in range(0, 180, 15):
        for length in (3, 3 + 2 * max_gap):
            kernel = _line_kernel(length, angle)
            closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            result = np.maximum(result, closed)
    return result


def _as_binary(mask: np.ndarray) -> np.ndarray:
    return ((mask > 0).astype(np.uint8) * 255).astype(np.uint8)


def _compute_frangi_native(gray: np.ndarray, sensitivity: float, detect_dark: bool) -> tuple[np.ndarray, np.ndarray]:
    """Pure NumPy/OpenCV multi-scale Hessian ridge detector (Frangi vesselness).

    Used as native implementation or fallback when scikit-image is not installed.
    Computes Hessian eigenvalues across scales 1..6 px to isolate elongated ridges.
    """
    float_img = gray.astype(np.float32)
    max_vesselness = np.zeros_like(float_img)
    level = float(np.clip((sensitivity - 0.25) / 1.75, 0.0, 1.0))
    beta = 0.5
    c = 15.0

    for s in range(1, 7):
        ksize = int(2 * round(3 * s) + 1)
        smoothed = cv2.GaussianBlur(float_img, (ksize, ksize), float(s))
        s2 = float(s ** 2)
        Dxx = cv2.Sobel(smoothed, cv2.CV_32F, 2, 0, ksize=3) * s2
        Dyy = cv2.Sobel(smoothed, cv2.CV_32F, 0, 2, ksize=3) * s2
        Dxy = cv2.Sobel(smoothed, cv2.CV_32F, 1, 1, ksize=3) * s2

        trace = Dxx + Dyy
        det = Dxx * Dyy - Dxy * Dxy
        disc = np.maximum(0.0, trace * trace - 4.0 * det)
        sqrt_disc = np.sqrt(disc)

        l1 = 0.5 * (trace - sqrt_disc)
        l2 = 0.5 * (trace + sqrt_disc)

        swap = np.abs(l1) > np.abs(l2)
        e1 = np.where(swap, l2, l1)
        e2 = np.where(swap, l1, l2)

        condition = (e2 > 0) if detect_dark else (e2 < 0)
        Rb = np.abs(e1) / (np.abs(e2) + 1e-8)
        S2 = e1 * e1 + e2 * e2

        vesselness = np.exp(-(Rb ** 2) / (2.0 * (beta ** 2))) * (1.0 - np.exp(-S2 / (2.0 * (c ** 2))))
        vesselness = np.where(condition, vesselness, 0.0)
        max_vesselness = np.maximum(max_vesselness, vesselness)

    pos = max_vesselness[max_vesselness > 0]
    if pos.size == 0:
        return np.zeros(gray.shape[:2], dtype=np.uint8), max_vesselness

    q = float(np.clip(0.97 - 0.04 * level, 0.90, 0.98))
    thresh = float(np.quantile(pos, q))
    binary = ((max_vesselness >= thresh).astype(np.uint8) * 255)
    return binary, max_vesselness


def _compute_frangi(source: np.ndarray, sensitivity: float, detect_dark: bool) -> tuple[np.ndarray, np.ndarray]:
    """Multi-scale Hessian ridge detection (Frangi filter).

    Returns (binary_mask, vesselness_map).
    """
    try:
        from skimage.filters import frangi
        gray_float = source.astype(np.float64) / 255.0
        level = float(np.clip((sensitivity - 0.25) / 1.75, 0.0, 1.0))

        vesselness = frangi(
            gray_float,
            sigmas=range(1, 7),
            black_ridges=False,
            mode="reflect",
        )
        if detect_dark:
            dark_v = frangi(
                gray_float,
                sigmas=range(1, 7),
                black_ridges=True,
                mode="reflect",
            )
            vesselness = np.maximum(vesselness, dark_v)

        pos = vesselness[vesselness > 0]
        if pos.size == 0:
            return np.zeros(source.shape[:2], dtype=np.uint8), vesselness.astype(np.float32)

        q = float(np.clip(0.97 - 0.04 * level, 0.90, 0.98))
        thresh = float(np.quantile(pos, q))
        binary = ((vesselness >= thresh).astype(np.uint8) * 255)
        return binary, vesselness.astype(np.float32)
    except ImportError:
        return _compute_frangi_native(source, sensitivity, detect_dark)


def detect_cracks(
    gray: np.ndarray,
    strength: float = 1.0,
    sensitivity: float | None = None,
    detect_dark: bool = False,
    *,
    include_dark: bool | None = None,
    dark: bool | None = None,
    expansion: float = 0.0,
    steps_dict: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    """Detect line-like bright cracks and, optionally, dark cracks.

    Two complementary detectors are combined:

    1. **Symmetry detector** — compares each pixel's brightness with both
       perpendicular flanks at 5 radii × 12 angles.  A crack pixel scores
       high only if it is brighter (or darker, for dark cracks) than *both*
       sides.  Longitudinal support then filters out isolated corners: the
       same evidence must persist along ≥ 60 % of the crack's direction.
       Hysteresis keeps whole connected components that contain at least one
       well-supported seed pixel.  Seeds are scattered throughout *every*
       crack across the image — there can be thousands of them.

    2. **Frangi ridge filter** — uses Hessian eigenvalues at scales 1–6 px to
       score elongated ridge/valley structures.  Catches faded and curved
       cracks the symmetry detector misses.

    Both masks are combined (bitwise OR) before ``refine_mask`` applies final
    component-level shape, thickness, and contrast filtering.

    The returned mask always has the input dimensions and contains only
    uint8 values 0 and 255.
    """
    if gray.ndim != 2 or gray.size == 0:
        raise ValueError("detect_cracks expects a non-empty grayscale image")
    if include_dark is not None:
        detect_dark = bool(include_dark)
    if dark is not None:
        detect_dark = bool(dark)
    selected_sensitivity = strength if sensitivity is None else sensitivity
    try:
        sensitivity_value = float(selected_sensitivity)
    except (TypeError, ValueError) as exc:
        raise ValueError("sensitivity must be numeric") from exc
    if not np.isfinite(sensitivity_value):
        raise ValueError("sensitivity must be finite")
    sensitivity_value = float(np.clip(sensitivity_value, 0.25, 2.0))

    clean = np.nan_to_num(np.asarray(gray), nan=0.0, posinf=255.0, neginf=0.0)
    clean = np.clip(clean, 0, 255).astype(np.uint8)
    source = clean.astype(np.float32)
    smooth = cv2.GaussianBlur(source, (3, 3), 0)
    background = cv2.GaussianBlur(source, (0, 0), sigmaX=8.0)
    noise = _noise_level(clean)
    local_contrast = source - background
    contrast_threshold = max(_contrast_threshold(np.abs(local_contrast), sensitivity_value), noise * 1.5 / sensitivity_value)
    bright_pixels = local_contrast >= contrast_threshold
    dark_pixels = local_contrast <= -contrast_threshold
    bright_response = np.zeros_like(smooth, dtype=np.float32)
    dark_response = np.zeros_like(smooth, dtype=np.float32)

    # Build response maps first. Their distributions determine the damage threshold.
    for radius in (2, 3, 5, 8, 12):
        for angle in range(0, 180, 15):
            radians = np.deg2rad(angle)
            dx = int(round(-np.sin(radians) * radius))
            dy = int(round(np.cos(radians) * radius))
            side_a = _shift(smooth, dx, dy)
            side_b = _shift(smooth, -dx, -dy)
            bright_response = np.maximum(bright_response, np.minimum(smooth - side_a, smooth - side_b))
            if detect_dark:
                dark_response = np.maximum(dark_response, np.minimum(side_a - smooth, side_b - smooth))
    bright_threshold = max(_robust_threshold(bright_response, sensitivity_value), noise * 2.5 / sensitivity_value)
    dark_threshold = max(_robust_threshold(dark_response, sensitivity_value), noise * 2.5 / sensitivity_value)
    if bright_response.max() > 0:
        bright_threshold = min(bright_threshold, float(bright_response.max()) * 0.75)
    if dark_response.max() > 0:
        dark_threshold = min(dark_threshold, float(dark_response.max()) * 0.75)
    candidates = np.zeros_like(clean, dtype=np.uint8)
    seeds = np.zeros_like(clean, dtype=np.uint8)

    # Compare centre pixel to both flanks.  Longitudinal support separates a
    # genuine crack (same contrast along its full length) from a corner or spot.
    for radius in (2, 3, 5, 8, 12):
        for angle in range(0, 180, 15):
            radians = np.deg2rad(angle)
            dx = int(round(-np.sin(radians) * radius))
            dy = int(round(np.cos(radians) * radius))
            side_a = _shift(smooth, dx, dy)
            side_b = _shift(smooth, -dx, -dy)
            responses = [(np.minimum(smooth - side_a, smooth - side_b), bright_pixels, bright_threshold)]
            if detect_dark:
                responses.append((np.minimum(side_a - smooth, side_b - smooth), dark_pixels, dark_threshold))
            kernel = _line_kernel(max(7, radius * 4 + 1), angle).astype(np.float32)
            kernel /= kernel.sum()
            for response, local_pixels, response_threshold in responses:
                evidence = (response >= response_threshold) & local_pixels
                along = cv2.filter2D(evidence.astype(np.float32), cv2.CV_32F, kernel, borderType=cv2.BORDER_CONSTANT)
                candidates |= evidence.astype(np.uint8)
                seeds |= (evidence & (along >= 0.60)).astype(np.uint8)

    raw_candidates = candidates.copy()

    # Hysteresis: keep whole components that contain at least one seed pixel.
    count, labels = cv2.connectedComponents(candidates, connectivity=8)
    supported = np.zeros(count, dtype=np.uint8)
    supported[np.unique(labels[seeds > 0])] = 1
    supported[0] = 0
    candidates = supported[labels]

    hysteresis_candidates = candidates.copy()
    result = _close_fragments(candidates, sensitivity_value)

    # ── Frangi ridge filter (complementary to symmetry detector) ────────────
    symmetry_binary = _as_binary(result)
    frangi_binary, frangi_vesselness = _compute_frangi(clean, sensitivity_value, detect_dark)

    # Gate Frangi with a two-sided contrast floor so broad object step-edges are rejected
    flank_support = (bright_response >= max(1.0, noise * 1.5 / sensitivity_value))
    if detect_dark:
        flank_support |= (dark_response >= max(1.0, noise * 1.5 / sensitivity_value))
    frangi_gated = np.where(flank_support, frangi_binary, 0).astype(np.uint8)

    combined = cv2.bitwise_or(symmetry_binary, frangi_gated)

    # Final shape/thickness/contrast filtering on the combined mask
    refined = refine_mask(
        combined,
        clean.shape,
        gray=clean,
        sensitivity=sensitivity_value,
        expansion=expansion,
    )

    if steps_dict is not None:
        steps_dict["03_gaussian_smooth_3x3"] = smooth
        steps_dict["04_background_illumination_sigma8"] = background
        steps_dict["05_local_contrast"] = local_contrast
        steps_dict["06_symmetry_bright_response"] = bright_response
        if detect_dark:
            steps_dict["07_symmetry_dark_response"] = dark_response
        steps_dict["08_symmetry_candidates_thresholded"] = _as_binary(raw_candidates)
        steps_dict["09_symmetry_seeds_longitudinal"] = _as_binary(seeds)
        steps_dict["10_symmetry_hysteresis_supported"] = _as_binary(hysteresis_candidates)
        steps_dict["11_symmetry_closed_fragments"] = symmetry_binary
        steps_dict["12_frangi_vesselness_map"] = frangi_vesselness
        steps_dict["13_frangi_binary_mask"] = frangi_gated
        steps_dict["14_combined_crack_mask_raw"] = combined
        steps_dict["15_crack_mask_refined"] = refined

    return refined
