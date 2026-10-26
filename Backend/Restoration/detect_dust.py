from __future__ import annotations

import cv2
import numpy as np


def detect_dust(gray: np.ndarray, sensitivity: float = 1.0) -> np.ndarray:
    """Detect optional compact dust/spot blemishes, not elongated cracks."""
    if gray.ndim != 2 or gray.size == 0:
        raise ValueError("detect_dust expects a non-empty grayscale image")
    sensitivity = float(np.clip(sensitivity, 0.25, 2.0))
    source = np.clip(gray, 0, 255).astype(np.uint8)
    response = np.zeros_like(source, dtype=np.float32)
    for size in (3, 5, 7):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        bright = cv2.morphologyEx(source, cv2.MORPH_TOPHAT, kernel)
        dark = cv2.morphologyEx(source, cv2.MORPH_BLACKHAT, kernel)
        response = np.maximum(response, np.maximum(bright, dark).astype(np.float32))
    positive = response[response > 0]
    if positive.size == 0:
        return np.zeros_like(source, dtype=np.uint8)
    threshold = max(18.0 / sensitivity, float(np.quantile(positive, np.clip(0.995 - 0.04 * sensitivity, 0.90, 0.995))))
    candidates = (response >= threshold).astype(np.uint8) * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidates, 8)
    result = np.zeros_like(candidates)
    image_area = source.shape[0] * source.shape[1]
    max_area = max(20, int(image_area * 0.0015))
    for index in range(1, count):
        area = int(stats[index, cv2.CC_STAT_AREA])
        width = int(stats[index, cv2.CC_STAT_WIDTH])
        height = int(stats[index, cv2.CC_STAT_HEIGHT])
        if 2 <= area <= max_area and max(width, height) <= 18 and min(width, height) >= 1:
            fill = area / max(1, width * height)
            if fill >= 0.12:
                result[labels == index] = 255
    return result.astype(np.uint8)
