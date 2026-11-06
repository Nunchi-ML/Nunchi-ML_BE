"""Run a private prototype bundle without installing over the pilot package."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile


def run(bundle, port):
    bundle = Path(bundle).resolve(strict=True)
    wheels = list(bundle.glob("nunchi_ml-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise ValueError("Exactly one nunchi_ml wheel required")
    manifest = json.loads((bundle / "SHA256.json").read_text(encoding="utf-8"))
    for name in [wheels[0].name, "meta.json", "parameters.json"]:
        if hashlib.sha256((bundle / name).read_bytes()).hexdigest() != manifest[name]:
            raise ValueError("Prototype bundle checksum mismatch: " + name)
    # HybridCandidate checks source bytes using real paths; zipimport is unsupported.
    with tempfile.TemporaryDirectory(prefix="nunchi-photo-g-") as runtime:
        with zipfile.ZipFile(wheels[0]) as archive:
            for entry in archive.infolist():
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or ":" in entry.filename:
                    raise ValueError("Unsafe wheel path")
            archive.extractall(runtime)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        sys.path.insert(0, runtime)
        os.environ["PROTOTYPE_MODEL_REQUIRED"] = "true"
        from app.prototype import create_prototype_app
        import uvicorn
        uvicorn.run(create_prototype_app(bundle), host="127.0.0.1", port=port, workers=1, access_log=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    run(args.bundle, args.port)
