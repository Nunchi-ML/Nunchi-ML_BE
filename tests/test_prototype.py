"""Prototype HTTP boundaries; optional real bundle parity, never synthetic accuracy."""
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.prototype import (ContextError, PATH, PhotoGPredictor, PrototypeBodyLimit,
                           create_prototype_app)


def context():
    return dict(lat=35.8, lon=128.6, heading=90, focal=.55, width=32, height=24,
                captured_at="2026-11-06T08:30:00+09:00", cloud=0, sunshine=.5,
                weather_observed_at="2026-11-06T08:00:00+09:00",
                weather_source="test observation", geometry_source="test geometry",
                projection="legacy_level_assumed")


class BoundaryPredictor:
    """Synthetic response only for transport tests. Real model test below is separate."""
    def __init__(self, directory):
        pass

    def analyze(self, image, metadata, image_sha256):
        return dict(model_version="photo-g-candidate-v1", status="prototype", variant="B_geometry_aug",
                    level=2, label="심한 눈부심", scores=dict(normal=.4, glare=.24, severe=.36),
                    alert_score=.6, conditional_severe_score=.6,
                    image_sha256=image_sha256, captured_at=metadata["captured_at"],
                    weather_age_seconds=1800, weather_availability_verified=False,
                    projection="legacy_level_assumed", camera_pose_validated=False,
                    roadside_validated=False, future_route_validated=False, processing_ms=1)


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ok, encoded = cv2.imencode(".jpg", np.zeros((24, 32, 3), np.uint8))
        assert ok
        cls.jpeg = encoded.tobytes()

    def client(self, factory=BoundaryPredictor):
        return TestClient(create_prototype_app("unused", predictor_factory=factory))

    def post(self, client, metadata=None, data=None, mime="image/jpeg"):
        return client.post(PATH, files={"image": ("test.jpg", self.jpeg if data is None else data, mime)},
                           data={"context": json.dumps(context() if metadata is None else metadata)})

    def test_conditional_decision_and_no_production_route(self):
        with self.client() as client:
            result = self.post(client)
            self.assertEqual(result.status_code, 200, result.text)
            body = result.json()
            # A/B decision is severe even when the largest joint score is normal.
            self.assertEqual(body["level"], 2)
            self.assertEqual(body["image_sha256"], hashlib.sha256(self.jpeg).hexdigest())
            self.assertFalse(body["future_route_validated"])
            self.assertEqual(client.post("/predict/glare").status_code, 404)
            self.assertEqual(client.get("/health").json()["model2_prototype"], "ready")
            schema = client.get("/openapi.json").json()
            self.assertEqual(set(schema["paths"]), {"/health", PATH})

    def test_metadata_rejected_before_inference(self):
        bad = [{}, {**context(), "cloud": None}, {**context(), "heading": "90"},
               {**context(), "lat": True}, {**context(), "width": 32.5},
               {**context(), "focal": float("nan")}, {**context(), "heading": 360},
               {**context(), "captured_at": "2026-11-06T08:30:00"},
               {**context(), "captured_at": 1793921400},
               {**context(), "geometry_source": " "}, {**context(), "unexpected": 0}]
        with self.client() as client, patch.object(BoundaryPredictor, "analyze") as infer:
            for metadata in bad:
                with self.subTest(metadata=metadata):
                    response = self.post(client, metadata)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(response.json()["error"], "INVALID_REQUEST")
            for raw_context in ["{", "[]", '"x"', "x" * 8193]:
                response = client.post(PATH, files={"image": ("a.jpg", self.jpeg, "image/jpeg")},
                                       data={"context": raw_context})
                self.assertEqual(response.status_code, 422)
            self.assertEqual(client.post(PATH).status_code, 422)
            infer.assert_not_called()

    def test_bad_image_type_bytes_size_and_resolution(self):
        ok, png = cv2.imencode(".png", np.zeros((24, 32, 3), np.uint8))
        assert ok
        ok, large = cv2.imencode(".jpg", np.zeros((3000, 3000, 3), np.uint8))
        assert ok
        cases = [(b"bad", "image/jpeg", 400), (png.tobytes(), "image/jpeg", 415),
                 (self.jpeg, "image/png", 415), (b"x" * (1048576 + 1), "image/jpeg", 413),
                 (large.tobytes(), "image/jpeg", 413)]
        with self.client() as client, patch.object(BoundaryPredictor, "analyze") as infer:
            for data, mime, status in cases:
                response = self.post(client, data=data, mime=mime)
                self.assertEqual(response.status_code, status, response.text)
            infer.assert_not_called()

    def test_context_error_and_inference_error_no_input_echo(self):
        with self.client() as client:
            for exception, status, code in [(ContextError("private metadata"), 400, "INVALID_CONTEXT"),
                                             (RuntimeError("private metadata"), 500, "INFERENCE_FAILED")]:
                with patch.object(BoundaryPredictor, "analyze", side_effect=exception):
                    response = self.post(client)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json()["error"], code)
                    self.assertNotIn("private metadata", response.text)

    def test_invalid_model_output_fails_closed(self):
        with self.client() as client:
            original = BoundaryPredictor.analyze
            def invalid(instance, *args):
                result = original(instance, *args)
                result["level"] = 0  # Forbidden joint argmax shortcut.
                return result
            with patch.object(BoundaryPredictor, "analyze", invalid):
                response = self.post(client)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn("level", response.json())

    def test_missing_model_and_required_startup(self):
        def missing(_):
            raise ValueError("unavailable")
        with self.client(missing) as client:
            self.assertEqual(client.get("/health").json()["model2_prototype"], "missing")
            self.assertEqual(self.post(client).status_code, 503)
        with patch.dict(os.environ, {"PROTOTYPE_MODEL_REQUIRED": "true"}):
            with self.assertRaisesRegex(RuntimeError, "before startup"):
                with self.client(missing):
                    pass

    def test_cors_and_actual_chunked_body_limit(self):
        with self.client() as client:
            allowed = client.options(PATH, headers={"Origin": "http://localhost:5173",
                                                   "Access-Control-Request-Method": "POST"})
            self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:5173")
            denied = client.get("/health", headers={"Origin": "https://unrelated.example"})
            self.assertNotIn("access-control-allow-origin", denied.headers)
        delivered, output = [], []
        async def downstream(scope, receive, send):
            delivered.append(scope["path"])
        async def receive():
            return {"type": "http.request", "body": b"x" * 600000, "more_body": True}
        async def send(message):
            output.append(message)
        asyncio.run(PrototypeBodyLimit(downstream)(dict(type="http", method="POST", path=PATH), receive, send))
        self.assertEqual(delivered, [])
        self.assertEqual(output[0]["status"], 413)

    def test_geometry_semantics_use_shared_ai_package(self):
        # No synthetic G fallback. The wrapper must propagate failed geometry as context error.
        service = object.__new__(PhotoGPredictor)
        service.photo_g = lambda *_: (_ for _ in ()).throw(ValueError("mismatch"))
        with self.assertRaises(ContextError):
            service.analyze(np.zeros((24, 32, 3), np.uint8), context(), "0" * 64)


@unittest.skipUnless(os.getenv("HYBRID_TEST_BUNDLE") and os.getenv("HYBRID_TEST_IMAGE")
                     and os.getenv("HYBRID_TEST_CONTEXT"), "Private photo+G fixtures not configured")
class RealPrototypeTests(unittest.TestCase):
    def test_real_bundle_http_parity_and_invalid_geometry(self):
        bundle = Path(os.environ["HYBRID_TEST_BUNDLE"])
        raw = Path(os.environ["HYBRID_TEST_IMAGE"]).read_bytes()
        metadata = json.loads(Path(os.environ["HYBRID_TEST_CONTEXT"]).read_text(encoding="utf-8-sig"))
        from nunchi_ml.glare.hybrid import HybridCandidate
        from nunchi_ml.glare.roadside import photo_g
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        expected = HybridCandidate(bundle).predict_image(image, photo_g(metadata, image.shape)["features"])
        with TestClient(create_prototype_app(bundle)) as client:
            response = client.post(PATH, files={"image": ("photo.jpg", raw, "image/jpeg")},
                                   data={"context": json.dumps(metadata)})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertEqual(result["level"], int(expected["level"][0]))
            self.assertEqual(list(result["scores"].values()), expected["joint_scores"][0].tolist())
            self.assertEqual(result["alert_score"], float(expected["alert_score"][0]))
            self.assertEqual(result["conditional_severe_score"], float(expected["conditional_severe_score"][0]))
            captured = datetime.fromisoformat(metadata["captured_at"])
            invalid = [dict(metadata, width=metadata["width"] - 1),
                       dict(metadata, weather_observed_at=(captured + timedelta(seconds=1)).isoformat()),
                       dict(metadata, weather_observed_at=(captured - timedelta(seconds=3601)).isoformat()),
                       dict(metadata, weather_available_at=(captured + timedelta(seconds=1)).isoformat())]
            for item in invalid:
                response = client.post(PATH, files={"image": ("photo.jpg", raw, "image/jpeg")},
                                       data={"context": json.dumps(item)})
                self.assertEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["error"], "INVALID_CONTEXT")
