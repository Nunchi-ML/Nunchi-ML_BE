"""실제 export 산출물과 HTTP 경계를 검수한다. MODEL_DIR 환경 변수가 필요."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import BodyLimitMiddleware, create_app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_dir = Path(os.environ["MODEL_DIR"]).resolve()
        cls.reference = json.loads((cls.model_dir / "reference/expected.json").read_text(encoding="utf-8"))

    def test_reference_predictions(self):
        with TestClient(create_app(self.model_dir)) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok", "model2": "ready"})
            for item in self.reference:
                data = (self.model_dir / "reference" / item["file"]).read_bytes()
                for source in ["camera", "game"]:
                    response = client.post("/predict/glare", files={"image": ("ref.jpg", data, "image/jpeg")}, data={"source": source})
                    self.assertEqual(response.status_code, 200, response.text)
                    result = response.json()
                    self.assertEqual(set(result), set(item["expected"]))
                    for key in ["model_version", "status", "level", "label", "brightest"]:
                        self.assertEqual(result[key], item["expected"][key])
                    for key, score in item["expected"]["scores"].items():
                        self.assertAlmostEqual(result["scores"][key], score, places=10)

    def test_swagger_and_openapi_contract(self):
        with TestClient(create_app(self.model_dir)) as client:
            docs = client.get("/docs")
            self.assertEqual(docs.status_code, 200)
            self.assertIn("swagger-ui", docs.text)
            self.assertEqual(client.get("/redoc").status_code, 200)
            schema = client.get("/openapi.json").json()
            self.assertIn("운전 시뮬레이터", schema["info"]["title"])
            operation = schema["paths"]["/predict/glare"]["post"]
            ref = operation["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"].split("/")[-1]
            body = schema["components"]["schemas"][ref]
            self.assertIn("image", body["required"])
            self.assertEqual(body["properties"]["image"]["format"], "binary")
            self.assertEqual(body["properties"]["source"]["enum"], ["camera", "game"])
            self.assertEqual(operation["responses"]["503"]["content"]["application/json"]["example"]["error"], "MODEL_NOT_READY")

    def test_missing_and_corrupt_model(self):
        with tempfile.TemporaryDirectory() as folder:
            for corrupt in [False, True]:
                if corrupt:
                    (Path(folder) / "meta.json").write_text("{}", encoding="utf-8")
                with TestClient(create_app(folder)) as client:
                    self.assertEqual(client.get("/health").json()["model2"], "missing")
                    response = client.post("/predict/glare", files={"image": ("a.jpg", b"bad", "image/jpeg")})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["error"], "MODEL_NOT_READY")

    def test_invalid_inputs_and_cors(self):
        origin = "https://nunchi-example.vercel.app"
        with TestClient(create_app(self.model_dir, [origin])) as client:
            reference = (self.model_dir / "reference" / self.reference[0]["file"]).read_bytes()
            cases = [(b"bad", "image/jpeg", {}, 400, "INVALID_IMAGE"),
                     (reference, "image/png", {}, 415, "UNSUPPORTED_IMAGE_TYPE"),
                     (reference, "image/jpeg", {"source": "other"}, 422, "INVALID_REQUEST"),
                     (b"x" * (1048576 + 1), "image/jpeg", {}, 413, "IMAGE_TOO_LARGE")]
            for body, mime, fields, status, code in cases:
                response = client.post("/predict/glare", files={"image": ("a.jpg", body, mime)}, data=fields)
                self.assertEqual(response.status_code, status, response.text)
                self.assertEqual(response.json()["error"], code)
            self.assertEqual(client.post("/predict/glare").status_code, 422)
            allowed = client.options("/predict/glare", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertEqual(allowed.headers["access-control-allow-origin"], origin)
            denied = client.get("/health", headers={"Origin": "https://unrelated.vercel.app"})
            self.assertNotIn("access-control-allow-origin", denied.headers)
            too_large = client.post("/predict/glare", content=b"x" * 1200000, headers={"Origin": origin})
            self.assertEqual(too_large.status_code, 413)
            self.assertEqual(too_large.headers["access-control-allow-origin"], origin)

    def test_resolution_limit_before_decode(self):
        # JPEG 파일이 작아도 펼쳤을 때 해상도 상한을 넘으면 거절한다.
        ok, encoded = cv2.imencode(".jpg", np.zeros((3000, 3000, 3), dtype=np.uint8))
        self.assertTrue(ok)
        with TestClient(create_app(self.model_dir)) as client:
            response = client.post("/predict/glare", files={"image": ("large.jpg", encoded.tobytes(), "image/jpeg")})
            self.assertEqual(response.status_code, 413)

    def test_chunked_body_limit(self):
        sent, called = [], []

        async def downstream(scope, receive, send):
            called.append(True)

        chunks = iter([{"type": "http.request", "body": b"x" * 600000, "more_body": True},
                       {"type": "http.request", "body": b"x" * 600000, "more_body": False}])

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        asyncio.run(BodyLimitMiddleware(downstream)({"type": "http", "method": "POST", "path": "/predict/glare"}, receive, send))
        self.assertEqual(called, [])
        self.assertEqual(sent[0]["status"], 413)


if __name__ == "__main__":
    unittest.main()
