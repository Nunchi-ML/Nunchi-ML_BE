"""배포 build 또는 로컬에서 실제 JPEG 3장의 모델 예측을 검수한다."""
import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np
from nunchi_glare.inference import GlarePredictor, sha256


def verify(directory):
    directory = Path(directory)
    predictor = GlarePredictor(directory)
    items = json.loads((directory / "reference/expected.json").read_text(encoding="utf-8"))
    if len(items) != 3:
        raise ValueError("Expected three reference images")
    for item in items:
        if item["file"] != Path(item["file"]).name:
            raise ValueError("Invalid reference path")
        path = directory / "reference" / item["file"]
        if sha256(path) != item["sha256"]:
            raise ValueError("Reference checksum mismatch")
        result = predictor.predict(cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR))
        for key in ["level", "label", "model_version", "status", "brightest"]:
            if result[key] != item["expected"][key]:
                raise ValueError(f"Reference mismatch: {item['file']} / {key}")
        if any(abs(result["scores"][key] - expected) > 1e-6
               for key, expected in item["expected"]["scores"].items()):
            raise ValueError("Reference score mismatch")
    print(json.dumps({"model2": "ready", "model_version": predictor.meta["model_version"],
                      "reference_images_verified": len(items)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        default=os.getenv("MODEL_DIR", "models/model2-pilot-v1"))
    verify(parser.parse_args().directory)
