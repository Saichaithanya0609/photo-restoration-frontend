# Photo Restoration Backend

FastAPI accepts an uploaded photograph, optionally denoises it, runs crack
detection and mask-based inpainting, saves the restored PNG locally, and
returns that PNG to the frontend.

## Requirements and installation

From the repository root in PowerShell:

```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux, activate with `source .venv/bin/activate` instead.

## Start the API

From the `Backend` directory with the virtual environment active:

```powershell
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

- API base: `http://127.0.0.1:8000`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health route: `GET /`

The frontend development server runs at `http://localhost:5173`. These local
frontend origins are allowed by the API's CORS configuration:
`http://localhost:5173` and `http://127.0.0.1:5173`.

## API endpoint

### `POST /restore`

Accepts `multipart/form-data`:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | JPEG, PNG, or WebP file | Yes | Photograph to restore |
| `denoise` | Boolean | No | Run denoising before detection; defaults to `false` |
| `denoise_method` | String (`nlm`, `gaussian`, `median`) | No | Denoising algorithm; defaults to `nlm` |
| `denoise_strength` | Integer (0..100) | No | Denoising intensity; defaults to `25` |
| `sensitivity` | Float (0.4..1.8) | No | Damage detection sensitivity; defaults to `1.0` |
| `bright_cracks` | Boolean | No | Detect bright scratches and cracks; defaults to `true` |
| `dark_cracks` | Boolean | No | Detect dark cracks and fissures; defaults to `false` |
| `detect_dust` | Boolean | No | Detect dust spots and film blemishes; defaults to `false` |
| `fading` | Boolean | No | Apply CLAHE contrast & fading correction; defaults to `true` |
| `color_restore` | Boolean | No | Gentle chroma / color balance recovery; defaults to `true` |
| `sharpen` | Boolean | No | Unsharp mask detail sharpening; defaults to `true` |
| `return_details` | Boolean | No | When `true`, returns JSON with base64 data URLs for restored image, damage mask, red damage overlay, and coverage stats. Defaults to `false` (returns raw PNG stream) |

### `GET /samples`

Returns a JSON list of built-in sample photos (`old_photo.jpg`, `image02.jpeg`, `image.png`) with preview metadata.

### `GET /samples/{filename}`

Serves the specified sample image file for demonstration and direct browser preview.

On success with `return_details=false`, returns the processed image as `image/png`. On success with `return_details=true`, returns JSON containing `restored_image`, `damage_mask`, `damage_overlay`, `coverage`, and `steps`. The API also writes a unique copy named `restored_<id>.png` into `Backend/outputs/`. Generated files are ignored by Git; `.gitkeep` preserves the empty folder in a fresh checkout.

Possible validation errors include `400` for empty or undecodable files and
`415` for unsupported upload types. Processing or PNG-encoding errors return
`500` with a detail message.

## Manual API check

With the server running, open another terminal in the `Backend` directory and
run this PowerShell command:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/restore" `
  -F "file=@test_images/image02.jpeg;type=image/jpeg" `
  -F "denoise=false" `
  --output outputs/manual_test.png
```

Open `outputs/manual_test.png` to inspect the API response. The server also
stores its own uniquely named copy in the same folder. To check denoising,
repeat the request with `denoise=true`. The same request can be sent from
Swagger UI at `/docs`.

Run the backend tests from this directory with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`Backend/test_images/` also contains local sample images for manual endpoint checks.

## Processing flow

1. `main.py` validates and decodes the upload to an OpenCV BGR array and reads
   the `denoise` multipart boolean.
2. `pipeline.py` runs NLM denoising through `image_processor.py` only when
   `denoise=true`; otherwise it passes the decoded BGR image unchanged.
3. The root pipeline converts BGR to PIL RGB and calls
   `Restoration.pipeline.restore_image()`.
4. The `Restoration` package detects candidate damage, refines the mask, and
   inpaints masked regions.
5. `pipeline.py` converts the restored PIL RGB image back to BGR and calls
   `Restoration.enhance.enhance_full_photo()` once, with fading correction,
   color balance, and sharpening enabled. Its denoising option stays disabled
   so denoising remains controlled by the frontend checkbox.
6. `main.py` encodes and saves the enhanced result, then returns the PNG response.
