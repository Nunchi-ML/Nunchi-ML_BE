"""운영 앱의 선정 모델 주소(/predict/glare/photo-g) 연결 테스트.

선정 모델 묶음(models/model2-photo-g-prototype-v1 + models/photo-g-runtime)이 설치된 경우에만
실제 모델로 실행한다. 설치는 scripts/install_model.py가 시범 모델과 함께 한다.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import unittest

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
PHOTO_G = Path(os.getenv("PHOTO_G_MODEL_DIR", ROOT / "models/model2-photo-g-prototype-v1"))
RUNTIME = Path(os.getenv("PHOTO_G_RUNTIME_DIR", ROOT / "models/photo-g-runtime"))
PILOT = Path(os.getenv("MODEL_DIR", ROOT / "models/model2-pilot-v1"))
KST = timezone(timedelta(hours=9))


def frame_jpeg(width=1280, height=720):
    """정면 아래쪽에 밝은 원반이 있는 합성 도로 장면."""
    y = np.linspace(0, 1, height)[:, None]
    sky = (np.clip(200 + 40 * (1 - y), 0, 255) * np.ones((1, width))).astype(np.uint8)
    img = np.dstack([sky, sky, np.clip(sky.astype(int) + 20, 0, 255).astype(np.uint8)])
    img[height // 2:] = 60
    cv2.circle(img, (width // 2, int(height * 0.42)), 40, (255, 255, 255), -1)
    ok, data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ok
    return data.tobytes()


def context(width=1280, height=720, **over):
    captured = datetime(2026, 4, 5, 18, 0, tzinfo=KST)
    data = dict(lat=35.8612, lon=128.6060, heading=265.0, focal=0.9, width=width, height=height,
                captured_at=captured.isoformat(), cloud=0.0, sunshine=1.0,
                weather_observed_at=(captured - timedelta(minutes=30)).isoformat(),
                weather_source="simulator_setting", geometry_source="simulator_camera",
                projection="legacy_level_assumed")
    data.update(over)
    return json.dumps(data)


@unittest.skipUnless((PHOTO_G / "parameters.json").is_file() and (RUNTIME / "nunchi_ml").is_dir(),
                     "photo-g bundle not installed")
class PhotoGRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_cm = TestClient(create_app(PILOT, ["http://localhost:5173"], PHOTO_G, RUNTIME))
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)

    def post(self, ctx, data=None):
        return self.client.post("/predict/glare/photo-g",
                                files={"image": ("f.jpg", data or frame_jpeg(), "image/jpeg")},
                                data={"context": ctx})

    def test_health_reports_both_models(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["model2_photo_g"], "ready")
        self.assertIn(body["model2"], {"ready", "missing"})

    def test_prediction_matches_direct_model(self):
        response = self.post(context())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["variant"], "B_geometry_aug")
        self.assertIn(body["level"], [0, 1, 2])
        self.assertAlmostEqual(sum(body["scores"].values()), 1.0, places=6)
        direct = self.client.app.state.photo_g.analyze(
            cv2.imdecode(np.frombuffer(frame_jpeg(), np.uint8), cv2.IMREAD_COLOR),
            json.loads(context()), body["image_sha256"])
        self.assertEqual(direct["level"], body["level"])
        for key, value in direct["scores"].items():
            self.assertAlmostEqual(value, body["scores"][key], places=9)

    def test_sun_behind_is_normal(self):
        # 해를 등지고 달리면(진행 방향 반대) 정상이어야 한다.
        body = self.post(context(heading=85.0)).json()
        self.assertEqual(body["level"], 0)

    def test_missing_context_field_is_rejected(self):
        bad = json.loads(context())
        del bad["heading"]
        self.assertEqual(self.post(json.dumps(bad)).status_code, 422)

    def test_size_mismatch_is_rejected(self):
        self.assertEqual(self.post(context(width=640)).status_code, 400)

    def test_pilot_route_still_served(self):
        response = self.client.post("/predict/glare", files={"image": ("f.jpg", frame_jpeg(), "image/jpeg")},
                                    data={"source": "game"})
        self.assertIn(response.status_code, {200, 503})
        if response.status_code == 200:
            self.assertEqual(response.json()["status"], "pilot")


class PhotoGMissingTest(unittest.TestCase):
    def test_missing_bundle_returns_503_not_fake(self):
        with TestClient(create_app(PILOT, None, ROOT / "models/none", ROOT / "models/none-runtime")) as client:
            self.assertEqual(client.get("/health").json()["model2_photo_g"], "missing")
            response = client.post("/predict/glare/photo-g",
                                   files={"image": ("f.jpg", frame_jpeg(), "image/jpeg")},
                                   data={"context": context()})
            self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
