from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .detect_cracks import detect_cracks
from .detect_dust import detect_dust
from .enhance import denoise as apply_denoise
from .inpaint import inpaint, inpaint_high_quality
from .preprocessing import bgr_to_pil, luminance, normalize_luminance, pil_to_bgr
from .refine_mask import refine_mask



# ── Internal constants ────────────────────────────────────────────────────────
_EXPANSION_PX: float = 2.0   # fixed seam allowance around detected damage
_MAX_COVERAGE: float = 0.20  # warn if mask exceeds this fraction of the image
_TINY_COVERAGE: float = 0.005  # below this use fast NS instead of biharmonic


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    """Output of ``detect_damage``; pass directly to ``restore_from_mask``."""
    mask_np: np.ndarray        # uint8 {0, 255} at original image resolution
    mask_image: Image.Image    # PIL L-mode mask for display / download
    coverage: float            # fraction of image pixels in the mask
    warning: str | None = None
    saved_steps: dict[str, str] = field(default_factory=dict)
    debug_dir: str | None = None


@dataclass
class RestorationResult:
    """Final output returned to the UI / API caller."""
    image: Image.Image
    mask: Image.Image
    mask_coverage: float
    steps: list[str]
    warning: str | None = None
    restoration_applied: bool = False
    backend_used: str = "none"
    saved_steps: dict[str, str] = field(default_factory=dict)
    debug_dir: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_image(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(((mask > 0).astype(np.uint8) * 255), mode="L")


def _make_red_overlay_bgr(original_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Highlight mask in semi-transparent bright red over original BGR image."""
    overlay = original_bgr.copy()
    red = np.zeros_like(original_bgr)
    red[:, :] = [30, 30, 235]  # BGR bright red
    active = mask > 0
    if np.any(active):
        overlay[active] = cv2.addWeighted(original_bgr[active], 0.35, red[active], 0.65, 0)
    return overlay


def _save_step_image(name: str, data: np.ndarray | Image.Image, output_dir: Path) -> str:
    """Format and write intermediate step image to disk as lossless PNG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{name}.png"

    if isinstance(data, Image.Image):
        data.save(out_path)
        return str(out_path)

    arr = np.asarray(data)
    if arr.dtype == bool:
        cv2.imwrite(str(out_path), (arr.astype(np.uint8) * 255))
    elif arr.ndim == 2 and arr.dtype in (np.float32, np.float64):
        if "local_contrast" in name:
            # Symmetrical contrast: 128 is neutral, darker is valley, brighter is ridge
            vis = np.clip(128.0 + arr * 2.0, 0, 255).astype(np.uint8)
        else:
            mx = float(arr.max())
            if mx > 0:
                vis = np.clip((arr / mx) * 255.0, 0, 255).astype(np.uint8)
            else:
                vis = np.zeros(arr.shape, dtype=np.uint8)
        cv2.imwrite(str(out_path), vis)
    elif arr.ndim == 2:
        cv2.imwrite(str(out_path), arr)
    elif arr.ndim == 3:
        cv2.imwrite(str(out_path), arr)

    return str(out_path)


def _generate_step_index(saved_steps: dict[str, str], output_dir: Path) -> None:
    """Generate an INDEX.md markdown file explaining every saved step."""
    descriptions = {
        "01_original_input": "Original input photograph as loaded/uploaded.",
        "02_grayscale_luminance": "Grayscale luminance channel (Y) used as detection baseline.",
        "03_gaussian_smooth_3x3": "Gaussian 3x3 filter to suppress microscopic film grain and sensor noise.",
        "04_background_illumination_sigma8": "Gaussian sigma=8 low-pass filter capturing broad lighting gradients.",
        "05_local_contrast": "High-pass contrast map (source minus smooth background); gray=neutral, light=ridge, dark=valley.",
        "06_symmetry_bright_response": "Multi-scale (2..12px) and multi-angle (0..165°) two-sided bright ridge response.",
        "07_symmetry_dark_response": "Multi-scale and multi-angle two-sided dark valley response (if dark cracks enabled).",
        "08_symmetry_candidates_thresholded": "Binary candidates passing the statistical quantile response threshold and local contrast gate.",
        "09_symmetry_seeds_longitudinal": "Seed pixels exhibiting >=60% directional continuity along a line kernel.",
        "10_symmetry_hysteresis_supported": "Connected candidate components preserved because they contain at least one seed pixel.",
        "11_symmetry_closed_fragments": "Directional morphological line-closing bridging short gaps in the symmetry mask.",
        "12_frangi_vesselness_map": "Multi-scale Hessian eigenvalue ridge score map (Frangi vesselness).",
        "13_frangi_binary_mask": "Thresholded Frangi vesselness mask capturing faint, curved, and low-contrast cracks.",
        "14_combined_crack_mask_raw": "Union (bitwise OR) of symmetry line candidates and Frangi ridge candidates.",
        "15_crack_mask_refined": "Crack mask after component filtering (PCA elongation >=3.0 or low fill, thickness <=20px, local contrast).",
        "16_dust_mask": "Compact spot and dust blemish mask detected via morphological top-hat / black-hat transforms.",
        "17_raw_damage_mask": "Combined crack and dust damage mask before seam expansion.",
        "18_final_damage_mask_expanded": "Final damage mask with fixed 2-pixel seam allowance expansion for seamless inpainting.",
        "19_damage_overlay_red": "Detected damage regions highlighted in semi-transparent red over the original photograph.",
        "20_inpainting_output_raw": "Raw full-image inpainting output (biharmonic PDE / Navier-Stokes).",
        "21_grain_reduction_denoised": "Grain reduction / non-local means denoising applied inside the repaired mask area.",
        "22_final_restored_composite": "Final restored photograph with exact pixel preservation everywhere outside the mask.",
    }

    lines = [
        "# Intermediate Process Step Analysis",
        "",
        "This directory contains images captured at every transformation step in the photo restoration pipeline.",
        "",
        "| Step Name | Image File | Description |",
        "|---|---|---|",
    ]

    for name, path_str in sorted(saved_steps.items()):
        fname = Path(path_str).name
        desc = descriptions.get(name, "Intermediate processing stage.")
        lines.append(f"| `{name}` | [`{fname}`]({fname}) | {desc} |")

    lines.append("")
    lines.append("---")
    lines.append("*Generated automatically by photo_restoration pipeline.*")

    try:
        (output_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass


# ── Stage 1: Detect ───────────────────────────────────────────────────────────

def detect_damage(
    image: Image.Image,
    sensitivity: float = 1.0,
    bright_cracks: bool = True,
    dark_cracks: bool = False,
    detect_dust_marks: bool = False,
    debug_dir: str | Path | None = None,
) -> DetectionResult:
    """Detect damage and return a mask for user inspection (Stage 1).

    If ``debug_dir`` is provided, every intermediate step image is saved into
    that directory for detailed visual inspection and analysis.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("image must be a PIL Image")

    sensitivity = float(np.clip(sensitivity, 0.4, 1.8))
    original = pil_to_bgr(image)
    gray = normalize_luminance(luminance(original))

    steps_dict: dict[str, np.ndarray | Image.Image] = {} if debug_dir is not None else None
    if steps_dict is not None:
        steps_dict["01_original_input"] = original
        steps_dict["02_grayscale_luminance"] = gray

    crack_mask = np.zeros_like(gray, dtype=np.uint8)
    if bright_cracks or dark_cracks:
        crack_mask = detect_cracks(
            gray,
            sensitivity=sensitivity,
            detect_dark=dark_cracks,
            expansion=0.0,
            steps_dict=steps_dict,
        )

    dust_mask = (
        detect_dust(gray, sensitivity)
        if detect_dust_marks
        else np.zeros_like(gray, dtype=np.uint8)
    )
    if steps_dict is not None and detect_dust_marks:
        steps_dict["16_dust_mask"] = dust_mask

    raw_mask = cv2.bitwise_or(crack_mask, dust_mask)
    if steps_dict is not None:
        steps_dict["17_raw_damage_mask"] = raw_mask

    # Second refinement pass: combines crack + dust, adds fixed seam allowance
    final_mask = refine_mask(
        raw_mask,
        original.shape,
        gray=gray,
        sensitivity=sensitivity,
        expansion=_EXPANSION_PX,
    )

    if steps_dict is not None:
        steps_dict["18_final_damage_mask_expanded"] = final_mask
        steps_dict["19_damage_overlay_red"] = _make_red_overlay_bgr(original, final_mask)

    coverage = float(np.count_nonzero(final_mask)) / final_mask.size
    mask_img = _mask_image(final_mask)

    saved_steps: dict[str, str] = {}
    if debug_dir is not None and steps_dict is not None:
        out_dir = Path(debug_dir)
        for step_name, data in steps_dict.items():
            saved_steps[step_name] = _save_step_image(step_name, data, out_dir)
        _generate_step_index(saved_steps, out_dir)

    warning: str | None = None
    if coverage == 0:
        warning = "No damage detected. Try raising the sensitivity slider."
    elif coverage > _MAX_COVERAGE:
        warning = (
            f"Mask covers {coverage:.1%} of the image — unusually large. "
            "Lower the sensitivity slider or uncheck damage types to reduce false positives."
        )

    return DetectionResult(
        mask_np=final_mask,
        mask_image=mask_img,
        coverage=coverage,
        warning=warning,
        saved_steps=saved_steps,
        debug_dir=str(debug_dir) if debug_dir else None,
    )


# ── Stage 2: Restore ──────────────────────────────────────────────────────────

def restore_from_mask(
    image: Image.Image,
    detection: DetectionResult,
    denoise_strength: int = 0,
    debug_dir: str | Path | None = None,
) -> RestorationResult:
    """Inpaint the detected mask region (Stage 2).

    If ``debug_dir`` is provided (or if ``detection`` recorded a debug_dir),
    the inpainting and compositing step images are saved into that directory.
    """
    if not isinstance(image, Image.Image):
        raise TypeError("image must be a PIL Image")

    active_debug_dir = debug_dir or detection.debug_dir
    saved_steps: dict[str, str] = dict(detection.saved_steps)

    if detection.coverage == 0:
        return RestorationResult(
            image=image.copy(),
            mask=detection.mask_image,
            mask_coverage=0.0,
            steps=["no damage detected — original returned"],
            warning="No damage was detected; the image is unchanged.",
            saved_steps=saved_steps,
            debug_dir=str(active_debug_dir) if active_debug_dir else None,
        )

    original_bgr = pil_to_bgr(image)
    final_mask = detection.mask_np
    steps: list[str] = []

    if detection.coverage < _TINY_COVERAGE:
        restored = inpaint(original_bgr, final_mask, method="ns", radius=3.0)
        backend_used = "Navier–Stokes"
        steps.append("Navier–Stokes inpainting (small mask, fast path)")
    else:
        restored = inpaint_high_quality(original_bgr, final_mask)
        backend_used = "biharmonic"
        steps.append("biharmonic inpainting (high quality)")

    # Composite: preserve every pixel outside the mask exactly
    output = original_bgr.copy()
    denoised_img = None
    if denoise_strength > 0:
        denoised_img = apply_denoise(restored, int(np.clip(denoise_strength, 1, 10)))
        output[final_mask > 0] = denoised_img[final_mask > 0]
        steps.append(f"local grain reduction (strength {denoise_strength})")
    else:
        output[final_mask > 0] = restored[final_mask > 0]

    steps.append("localized compositing — outside-mask pixels preserved exactly")

    if active_debug_dir is not None:
        out_dir = Path(active_debug_dir)
        saved_steps["20_inpainting_output_raw"] = _save_step_image("20_inpainting_output_raw", restored, out_dir)
        if denoised_img is not None:
            saved_steps["21_grain_reduction_denoised"] = _save_step_image("21_grain_reduction_denoised", denoised_img, out_dir)
        saved_steps["22_final_restored_composite"] = _save_step_image("22_final_restored_composite", output, out_dir)
        _generate_step_index(saved_steps, out_dir)

    return RestorationResult(
        image=bgr_to_pil(output),
        mask=detection.mask_image,
        mask_coverage=detection.coverage,
        steps=steps,
        warning=None,
        restoration_applied=True,
        backend_used=backend_used,
        saved_steps=saved_steps,
        debug_dir=str(active_debug_dir) if active_debug_dir else None,
    )


# ── Convenience wrapper (CLI / API / tests) ───────────────────────────────────

def restore_image(
    image: Image.Image,
    sensitivity: float = 1.0,
    denoise_strength: int = 0,
    bright_cracks: bool = True,
    dark_cracks: bool = False,
    detect_dust_marks: bool = False,
    debug_dir: str | Path | None = None,
    # Legacy keyword arguments accepted but ignored for backward compatibility
    **_legacy_kwargs,
) -> RestorationResult:
    """Detect + restore in one call.  Accepts (and silently ignores) old keyword
    arguments so existing test code and CLI scripts keep working.
    """
    detection = detect_damage(
        image,
        sensitivity=sensitivity,
        bright_cracks=bright_cracks,
        dark_cracks=dark_cracks,
        detect_dust_marks=detect_dust_marks,
        debug_dir=debug_dir,
    )
    return restore_from_mask(
        image,
        detection,
        denoise_strength=denoise_strength,
        debug_dir=debug_dir,
    )

