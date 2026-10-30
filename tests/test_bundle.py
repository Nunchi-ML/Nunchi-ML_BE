"""배포 bundle의 실제 모델 복원 및 손상·경로 탈출 방어를 검수한다."""
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.install_model import download, unpack
from nunchi_glare.inference import GlarePredictor


def archive(files):
    manifest = {"format": "nunchi-model2-bundle-v1", "wheel": "nunchi_glare-0.1.0-py3-none-any.whl",
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as out:
        out.writestr("manifest.json", json.dumps(manifest))
        for name, data in files.items():
            out.writestr(name, data)
    return stream.getvalue()


class BundleTests(unittest.TestCase):
    def test_real_bundle_restore(self):
        bundle_path = Path(os.environ["MODEL_BUNDLE_PATH"])
        data = bundle_path.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            wheel = unpack(data, hashlib.sha256(data).hexdigest(), folder)
            self.assertTrue(wheel.is_file())
            predictor = GlarePredictor(folder)
            self.assertEqual(predictor.meta["model_version"], "model2-pilot-v1")

    def test_wrong_hash_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "checksum"):
                unpack(b"not a trusted model", "0" * 64, folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_unsafe_paths_and_unexpected_files(self):
        for name in ["../escape", "/absolute", "C:/absolute", "reference\\escape", "extra.py"]:
            data = archive({name: b"untrusted"})
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    unpack(data, hashlib.sha256(data).hexdigest(), folder)
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_duplicate_archive_entries(self):
        data = BytesIO()
        with zipfile.ZipFile(data, "w") as out:
            out.writestr("manifest.json", "{}")
            # zipfile warns about duplicates; the installer must reject them.
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                out.writestr("manifest.json", "{}")
        raw = data.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                unpack(raw, hashlib.sha256(raw).hexdigest(), folder)

    def test_download_only_team_release(self):
        for url in ["http://github.com/Nunchi-ML/Nunchi-ML_AI/releases/download/v1/model.zip",
                    "https://example.com/model.zip", "file:///model.zip",
                    "https://github.com/other/team/releases/download/v1/model.zip"]:
            with self.assertRaisesRegex(ValueError, "team GitHub"):
                download(url)


if __name__ == "__main__":
    unittest.main()
