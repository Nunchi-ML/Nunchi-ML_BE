"""발표 선정 모델(사진 + 해 위치·날씨) 묶음을 팀 Release에서 받아 검증하고 푼다.

운영 시범 모델(nunchi_glare)을 덮어쓰지 않도록 wheel은 pip로 설치하지 않고
런타임 폴더에 풀어 두며, 서버가 시작할 때 그 폴더만 import 경로에 추가한다.
"""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile

try:
    from scripts.install_model import download, model_source
except ImportError:  # python scripts/install_photo_g.py
    from install_model import download, model_source

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "deployment/photo_g_model.json"
FILES = {"parameters.json", "meta.json", "reference.json", "USAGE.txt", "SHA256.json"}
WHEEL = re.compile(r"nunchi_ml-[\w.]+-py3-none-any\.whl")
DEFAULT_MODEL_DIR = "models/model2-photo-g-prototype-v1"
DEFAULT_RUNTIME_DIR = "models/photo-g-runtime"


def _safe(name):
    path = PurePosixPath(name)
    return not (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name)


def unpack(data, expected_sha256, destination, runtime):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("A pinned photo-g bundle SHA-256 is required")
    if hashlib.sha256(data).hexdigest() != expected_sha256.lower():
        raise ValueError("Photo-g bundle checksum mismatch")
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        wheels = [n for n in names if WHEEL.fullmatch(n)]
        if len(wheels) != 1 or set(names) != FILES | set(wheels) or not all(map(_safe, names)):
            raise ValueError("Unexpected photo-g bundle files")
        contents = {name: archive.read(name) for name in names}
    manifest = json.loads(contents["SHA256.json"])
    for name in [wheels[0], "parameters.json", "meta.json"]:
        if hashlib.sha256(contents[name]).hexdigest() != manifest.get(name):
            raise ValueError("Photo-g bundle file checksum mismatch: " + name)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        (destination / name).write_bytes(content)
    runtime = Path(runtime).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(contents[wheels[0]])) as wheel:
        for entry in wheel.infolist():
            if not _safe(entry.filename):
                raise ValueError("Unsafe wheel path")
            target = runtime.joinpath(*PurePosixPath(entry.filename).parts).resolve()
            if not target.is_relative_to(runtime):
                raise ValueError("Wheel entry escapes runtime directory")
            if entry.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(wheel.read(entry))
    return destination


def install(config=CONFIG, bundle=None, destination=None, runtime=None):
    destination = destination or os.getenv("PHOTO_G_MODEL_DIR", DEFAULT_MODEL_DIR)
    runtime = runtime or os.getenv("PHOTO_G_RUNTIME_DIR", DEFAULT_RUNTIME_DIR)
    url, digest = model_source(config)
    data = Path(bundle).read_bytes() if bundle else download(url)
    unpack(data, digest, destination, runtime)
    return {"photo_g_installed": str(destination), "runtime": str(runtime), "bundle_sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Local bundle instead of downloading")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    print(json.dumps(install(args.config, args.bundle)))


if __name__ == "__main__":
    main()
