import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image
from starlette.datastructures import Headers, UploadFile

import main
import pipeline


class ProcessImageTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((48, 64, 3), dtype=np.uint8)
        self.image[:, :, 0] = 40
        self.image[:, :, 1] = 110
        self.image[:, :, 2] = 190
        rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        self.restoration_result = SimpleNamespace(image=Image.fromarray(rgb))

    def test_enabled_checkbox_calls_denoising(self):
        with (
            patch.object(pipeline, "denoise_image", return_value=self.image.copy()) as denoise,
            patch.object(pipeline, "restore_image", return_value=self.restoration_result) as restore,
            patch.object(pipeline, "enhance_full_photo", side_effect=lambda image, **_: image) as enhance,
        ):
            result = pipeline.process_image(self.image, denoise_enabled=True)

        denoise.assert_called_once_with(self.image, method="nlm", strength=25)
        restore.assert_called_once()
        enhance.assert_called_once()
        np.testing.assert_array_equal(enhance.call_args.args[0], self.image)
        self.assertEqual(
            enhance.call_args.kwargs,
            {"fading": True, "color_restore": True, "sharpen_enabled": True},
        )
        self.assertEqual(result.shape, self.image.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_disabled_checkbox_skips_denoising(self):
        with (
            patch.object(pipeline, "denoise_image") as denoise,
            patch.object(pipeline, "restore_image", return_value=self.restoration_result) as restore,
            patch.object(pipeline, "enhance_full_photo", side_effect=lambda image, **_: image) as enhance,
        ):
            result = pipeline.process_image(self.image, denoise_enabled=False)

        denoise.assert_not_called()
        restore.assert_called_once()
        enhance.assert_called_once()
        self.assertEqual(result.shape, self.image.shape)
        self.assertEqual(result.dtype, np.uint8)

    def test_small_image_runs_full_pipeline(self):
        small_image = np.full((48, 64, 3), 128, dtype=np.uint8)
        result = pipeline.process_image(small_image, denoise_enabled=False)
        self.assertEqual(result.shape, small_image.shape)
        self.assertEqual(result.dtype, np.uint8)


class RestoreEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_openapi_declares_denoise_as_multipart_boolean(self):
        schema_ref = main.app.openapi()["paths"]["/restore"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
        schema_name = schema_ref.rsplit("/", 1)[-1]
        properties = main.app.openapi()["components"]["schemas"][schema_name]["properties"]

        self.assertEqual(properties["denoise"]["type"], "boolean")
        self.assertNotIn("remove_noise", properties)

    async def test_denoise_boolean_is_passed_to_pipeline(self):
        image = np.full((24, 32, 3), 128, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(ok)

        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.object(main, "OUTPUT_DIR", Path(output_dir)),
                patch.object(main, "process_image", return_value=image) as process,
            ):
                for denoise_value in (True, False):
                    upload = UploadFile(
                        filename="request.png",
                        file=io.BytesIO(encoded.tobytes()),
                        headers=Headers({"content-type": "image/png"}),
                    )
                    response = await main.restore_photo(upload, denoise_value)
                    chunks = [chunk async for chunk in response.body_iterator]
                    decoded = cv2.imdecode(
                        np.frombuffer(b"".join(chunks), dtype=np.uint8),
                        cv2.IMREAD_COLOR,
                    )
                    self.assertEqual(response.media_type, "image/png")
                    self.assertEqual(decoded.shape, image.shape)

            self.assertEqual(
                [call.kwargs["denoise_enabled"] for call in process.call_args_list],
                [True, False],
            )

    async def test_restore_endpoint_returns_json_details(self):
        image = np.full((24, 32, 3), 128, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        self.assertTrue(ok)

        mock_details = {
            "restored_bgr": image,
            "mask_np": np.zeros((24, 32), dtype=np.uint8),
            "overlay_bgr": image,
            "coverage": 0.05,
            "steps": ["mock step"],
            "warning": None,
            "backend_used": "biharmonic",
        }

        with tempfile.TemporaryDirectory() as output_dir:
            with (
                patch.object(main, "OUTPUT_DIR", Path(output_dir)),
                patch.object(main, "process_image", return_value=mock_details) as process,
            ):
                upload = UploadFile(
                    filename="request.png",
                    file=io.BytesIO(encoded.tobytes()),
                    headers=Headers({"content-type": "image/png"}),
                )
                response = await main.restore_photo(
                    upload,
                    denoise=True,
                    sensitivity=1.2,
                    dark_cracks=True,
                    detect_dust=True,
                    return_details=True,
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/json", response.media_type)
                import json
                data = json.loads(response.body.decode("utf-8"))
                self.assertIn("restored_image", data)
                self.assertIn("damage_mask", data)
                self.assertIn("damage_overlay", data)
                self.assertEqual(data["coverage"], 0.05)
                self.assertEqual(data["steps"], ["mock step"])

    def test_samples_endpoint(self):
        res = main.list_sample_images()
        self.assertIn("samples", res)
        self.assertIsInstance(res["samples"], list)


if __name__ == "__main__":
    unittest.main()

