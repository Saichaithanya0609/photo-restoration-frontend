"""Classical photo restoration toolkit."""

from .pipeline import DetectionResult, RestorationResult, detect_damage, restore_from_mask, restore_image

__all__ = [
    "DetectionResult",
    "RestorationResult",
    "detect_damage",
    "restore_from_mask",
    "restore_image",
]
