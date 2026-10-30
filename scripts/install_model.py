"""팀 Release의 고정한 bundle만 검증·설치한다. 사용자 업로드와 연결하지 않는다."""
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import urlopen
import zipfile

MAX_BUNDLE = 16 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024


def download(url):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or not parsed.path.startswith("/Nunchi-ML/Nunchi-ML_AI/releases/download/")
            or parsed.query or parsed.fragment):
        raise ValueError("Expected a team GitHub Release HTTPS URL")
    with urlopen(url, timeout=60) as response:
        data = response.read(MAX_BUNDLE + 1)
    if len(data) > MAX_BUNDLE:
        raise ValueError("Model bundle exceeds 16MiB")
    return data


def unpack(data, expected_sha256, destination):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("A pinned MODEL_BUNDLE_SHA256 is required")
    if len(data) > MAX_BUNDLE or hashlib.sha256(data).hexdigest() != expected_sha256.lower():
        raise ValueError("Model bundle checksum mismatch")
    with zipfile.ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(names) > 20:
            raise ValueError("Duplicate or excessive archive entries")
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED:
            raise ValueError("Expanded model bundle exceeds 32MiB")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or ":" in entry.filename or entry.is_dir()
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe archive path")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "nunchi-model2-bundle-v1":
            raise ValueError("Unsupported model bundle format")
        files, wheel = manifest["files"], manifest["wheel"]
        required = {"model2.joblib", "meta.json", "reference/expected.json", wheel}
        if (not re.fullmatch(r"nunchi_glare-[\w.]+-py3-none-any\.whl", wheel)
                or not required.issubset(files)
                or set(names) != set(files) | {"manifest.json"}
                or any(name not in required and not re.fullmatch(r"reference/class-[012]\.jpg", name)
                       for name in files)):
            raise ValueError("Unexpected bundle files")
        contents = {name: archive.read(name) for name in files}
        if any(hashlib.sha256(contents[name]).hexdigest() != digest for name, digest in files.items()):
            raise ValueError("Bundle file checksum mismatch")
    # Validate all paths and hashes before writing anything. No extractall or recursive deletion.
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for name, content in contents.items():
        target = destination.joinpath(*PurePosixPath(name).parts).resolve()
        if not target.is_relative_to(destination):
            raise ValueError("Bundle destination escapes model directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination / wheel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="Local bundle instead of downloading")
    parser.add_argument("--url", default=os.getenv("MODEL_BUNDLE_URL"))
    parser.add_argument("--sha256", default=os.getenv("MODEL_BUNDLE_SHA256", ""))
    parser.add_argument("--destination", type=Path,
                        default=os.getenv("MODEL_DIR", "models/model2-pilot-v1"))
    args = parser.parse_args()
    if args.bundle is None and not args.url:
        parser.error("Set MODEL_BUNDLE_URL and MODEL_BUNDLE_SHA256 before deploying")
    data = args.bundle.read_bytes() if args.bundle else download(args.url)
    wheel = unpack(data, args.sha256, args.destination)
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--force-reinstall", str(wheel)], check=True)
    print(json.dumps({"installed": str(args.destination), "bundle_sha256": args.sha256}))


if __name__ == "__main__":
    main()
