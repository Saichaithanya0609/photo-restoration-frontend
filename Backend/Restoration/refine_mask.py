from __future__ import annotations

import cv2
import numpy as np


def _elongation(component: np.ndarray) -> float:
    points = np.column_stack(np.where(component > 0))
    if len(points) < 3:
        return 1.0
    covariance = np.cov(points.astype(np.float32), rowvar=False)
    eigenvalues = np.linalg.eigvalsh(covariance)
    return float((eigenvalues[-1] + 1e-3) / (eigenvalues[0] + 1e-3))


def refine_mask(
    mask: np.ndarray,
    image_shape: tuple[int, ...],
    strength: float = 1.0,
    gray: np.ndarray | None = None,
    *,
    sensitivity: float | None = None,
    expansion: float | None = None,
) -> np.ndarray:
    """Join small gaps, reject broad/low-contrast regions, and expand seams.

    Thickness and shape, rather than a fixed image-area cutoff, let long,
    wide and intersecting cracks survive. With ``gray`` supplied, a candidate
    must also differ from its surroundings on both sides; a normal object
    boundary is not sufficient evidence. ``expansion`` is a radius in pixels
    (0..8); when omitted, ``strength`` retains its historical seam allowance.
    """
    mask = np.asarray(mask)
    if mask.ndim != 2 or mask.size == 0:
        raise ValueError("refine_mask expects a non-empty two-dimensional mask")
    if tuple(image_shape[:2]) != mask.shape:
        raise ValueError("image_shape must match the mask dimensions")
    if gray is not None:
        gray = np.asarray(gray)
        if gray.ndim != 2 or gray.shape != mask.shape:
            raise ValueError("gray must match the mask dimensions")
        gray = np.clip(np.nan_to_num(gray, nan=0.0, posinf=255.0, neginf=0.0), 0, 255).astype(np.uint8)
    sensitivity_value = float(1.0 if sensitivity is None else sensitivity)
    expansion_value = float(strength) * 0.75 if expansion is None else float(expansion)
    if not np.isfinite(sensitivity_value) or not np.isfinite(expansion_value):
        raise ValueError("sensitivity and expansion must be finite")
    sensitivity_value = float(np.clip(sensitivity_value, 0.25, 2.0))
    radius = int(np.clip(round(expansion_value), 0, 2 if expansion is None else 8))
    binary = ((np.isfinite(mask) & (mask > 0)).astype(np.uint8) * 255)
    if not np.any(binary):
        return binary
    # Do not open with a 2x2 kernel: it erases genuine one-pixel diagonal
    # cracks. A single conservative close reconnects small response gaps.
    joined = binary.copy()
    gap_length = 3 if sensitivity_value < 1.5 else 5
    for kernel in (
        np.ones((1, gap_length), np.uint8),
        np.ones((gap_length, 1), np.uint8),
        np.eye(gap_length, dtype=np.uint8),
        np.fliplr(np.eye(gap_length, dtype=np.uint8)),
    ):
        joined = cv2.bitwise_or(joined, cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel))
    binary = joined
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    height, width = mask.shape
    min_area = max(3, int(round(8.0 / sensitivity_value)))
    kept = np.zeros_like(binary)
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        x, y = stats[index, cv2.CC_STAT_LEFT], stats[index, cv2.CC_STAT_TOP]
        box_w, box_h = stats[index, cv2.CC_STAT_WIDTH], stats[index, cv2.CC_STAT_HEIGHT]
        box_area = max(1, box_w * box_h)
        fill = area / box_area
        # Work in the component's padded bounding box, rather than scanning
        # the full photograph once per piece of dust/noise.
        margin = 4
        left, top = max(0, x - margin), max(0, y - margin)
        right, bottom = min(width, x + box_w + margin), min(height, y + box_h + margin)
        component = (labels[top:bottom, left:right] == index).astype(np.uint8)
        elongation = _elongation(component)
        max_dim = max(box_w, box_h)
        if area < min_area or max_dim < 6:
            continue
        # Padding keeps distance estimates meaningful for components touching
        # an image edge. A wide crack is allowed; a broad solid region is not.
        distances = cv2.distanceTransform(np.pad(component, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
        thickness = 2.0 * float(np.quantile(distances[component > 0], 0.85))
        if thickness > 20.0:
            continue
        # PCA admits straight diagonal lines. Low fill plus bounded thickness
        # admits bent/crossing networks whose overall PCA may be nearly round.
        crack_like = (
            (elongation >= 3.0 and max_dim >= max(7.0, thickness * 2.5))
            or (fill <= 0.40 and max_dim >= max(9.0, thickness * 3.0))
        )
        if not crack_like:
            continue

        if gray is not None:
            surround = cv2.dilate(component, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))) > 0
            # Other detected cracks are not a reliable background sample.
            ring = surround & (binary[top:bottom, left:right] == 0)
            if not np.any(ring):
                continue
            pixels = gray[top:bottom, left:right]
            inner = pixels[component > 0]
            outer = pixels[ring]
            contrast = max(
                float(np.quantile(inner, 0.60)) - float(np.quantile(outer, 0.75)),
                float(np.quantile(outer, 0.25)) - float(np.quantile(inner, 0.40)),
            )
            # A one-pixel candidate must pass the two-sided contrast test.
            # Wider candidates can have a one-pixel response fringe at their
            # boundary (especially after diagonal/scale fusion); shape and
            # thickness checks still constrain those crack networks.
            if contrast < 5.0 / sensitivity_value and thickness < 2.0:
                continue
        region = kept[top:bottom, left:right]
        region[component > 0] = 255
        kept[top:bottom, left:right] = region

    # Only a minimal seam allowance for inpainting; never use strength to
    # create a large expanding disk.
    if radius:
        kept = cv2.dilate(kept, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1)))
    return ((kept > 0).astype(np.uint8) * 255).astype(np.uint8)
