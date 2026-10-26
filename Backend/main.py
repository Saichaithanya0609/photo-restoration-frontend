import base64
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from pipeline import process_image

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
TEST_IMAGES_DIR = Path(__file__).resolve().parent / "test_images"


app = FastAPI(
    title="Photo Restoration API",
    description="API for photo restoration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "message": "Photo Restoration API is running"
    }


@app.get("/samples")
def list_sample_images():
    """List sample test images available for demonstration."""
    samples = []
    if TEST_IMAGES_DIR.exists():
        for p in sorted(TEST_IMAGES_DIR.iterdir()):
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                samples.append({
                    "id": p.name,
                    "name": p.stem.replace("_", " ").title(),
                    "filename": p.name,
                    "url": f"/samples/{p.name}",
                })
    return {"samples": samples}


@app.get("/samples/{filename}")
def get_sample_image(filename: str):
    """Serve a sample image file."""
    path = TEST_IMAGES_DIR / filename
    if not path.exists() or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=404, detail="Sample image not found.")
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return StreamingResponse(BytesIO(path.read_bytes()), media_type=media_type)


@app.post("/restore")
async def restore_photo(
    file: UploadFile = File(...),
    denoise: bool = Form(False),
    denoise_method: str = Form("nlm"),
    denoise_strength: int = Form(25),
    sensitivity: float = Form(1.0),
    bright_cracks: bool = Form(True),
    dark_cracks: bool = Form(False),
    detect_dust: bool = Form(False),
    fading: bool = Form(True),
    color_restore: bool = Form(True),
    sharpen: bool = Form(True),
    return_details: bool = Form(False),
):
    # 1. Validate the uploaded file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=415,
            detail="Please upload a JPEG, PNG, or WebP image.",
        )

    # 2. Read the uploaded file
    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    # 3. Decode the bytes into an OpenCV image
    image_array = np.frombuffer(contents, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file could not be decoded as an image.",
        )

    try:
        # 4. Run our pipeline
        result = process_image(
            image,
            denoise_enabled=denoise,
            denoise_method=denoise_method,
            denoise_strength=denoise_strength,
            detection_sensitivity=sensitivity,
            bright_cracks=bright_cracks,
            dark_cracks=dark_cracks,
            detect_dust=detect_dust,
            fading=fading,
            color_restore=color_restore,
            sharpen_enabled=sharpen,
            return_details=return_details,
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        if isinstance(result, dict):
            def to_b64(arr: np.ndarray) -> str:
                ok, enc = cv2.imencode(".png", arr)
                if not ok:
                    raise HTTPException(status_code=500, detail="Could not encode image.")
                return f"data:image/png;base64,{base64.b64encode(enc.tobytes()).decode('ascii')}"

            restored_bgr = result["restored_bgr"]
            mask_np = result["mask_np"]
            overlay_bgr = result["overlay_bgr"]

            success, encoded_image = cv2.imencode(".png", restored_bgr)
            output_name = f"restored_{uuid4().hex}.png"
            if success:
                (OUTPUT_DIR / output_name).write_bytes(encoded_image.tobytes())

            return JSONResponse(
                content={
                    "restored_image": to_b64(restored_bgr),
                    "damage_mask": to_b64(mask_np),
                    "damage_overlay": to_b64(overlay_bgr),
                    "coverage": round(result.get("coverage", 0.0), 4),
                    "steps": result.get("steps", []),
                    "warning": result.get("warning"),
                    "backend_used": result.get("backend_used", "none"),
                    "output_filename": output_name,
                }
            )

        # 5. Encode and save the result under Backend/outputs.
        success, encoded_image = cv2.imencode(".png", result)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Could not encode the restored image.",
            )

        png_bytes = encoded_image.tobytes()
        output_name = f"restored_{uuid4().hex}.png"
        (OUTPUT_DIR / output_name).write_bytes(png_bytes)

        # 6. Return the processed image
        return StreamingResponse(
            BytesIO(png_bytes),
            media_type="image/png",
            headers={
                "Content-Disposition": 'inline; filename="restored.png"',
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Image processing failed: {str(exc)}",
        ) from exc

