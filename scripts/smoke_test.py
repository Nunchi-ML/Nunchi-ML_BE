"""클라우드 API의 모델 준비·Swagger·기준 JPEG 실제 응답을 확인한다."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid


def request(base_url, path, data=None, headers=None):
    with urlopen(Request(base_url.rstrip("/") + path, data=data, headers=headers or {}), timeout=30) as response:
        return response.read(), response.headers


def smoke(base_url, directory, origin=None):
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise ValueError("Expected an HTTPS API base URL")
    raw, _ = request(base_url, "/health")
    if json.loads(raw) != {"status": "ok", "model2": "ready"}:
        raise RuntimeError("Deployed model is not ready")
    schema, _ = request(base_url, "/openapi.json")
    if not {"/health", "/predict/glare"}.issubset(json.loads(schema)["paths"]):
        raise RuntimeError("Missing deployed API paths")
    docs, _ = request(base_url, "/docs")
    if b"SwaggerUIBundle" not in docs:
        raise RuntimeError("Swagger is unavailable")
    directory = Path(directory)
    expected = json.loads((directory / "reference/expected.json").read_text(encoding="utf-8"))
    for item in expected:
        if item["file"] != Path(item["file"]).name:
            raise ValueError("Invalid reference filename")
        boundary = "nunchi-" + uuid.uuid4().hex
        image = (directory / "reference" / item["file"]).read_bytes()
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="source"\r\n\r\ncamera\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="reference.jpg"\r\n'
                'Content-Type: image/jpeg\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if origin:
            headers["Origin"] = origin
        raw, response_headers = request(base_url, "/predict/glare", body, headers)
        actual = json.loads(raw)
        for key in ["model_version", "status", "level", "label"]:
            if actual[key] != item["expected"][key]:
                raise RuntimeError(f"Deployed model mismatch: {key}")
        if any(abs(actual["scores"][key] - value) > 1e-6
               for key, value in item["expected"]["scores"].items()):
            raise RuntimeError("Deployed model scores differ from CI references")
        if origin and response_headers.get("Access-Control-Allow-Origin") != origin:
            raise RuntimeError("Deployed CORS origin mismatch")
    print(json.dumps({"smoke": "passed", "reference_images": len(expected), "api": base_url}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--directory", type=Path, default="models/model2-pilot-v1")
    parser.add_argument("--origin")
    args = parser.parse_args()
    smoke(args.base_url, args.directory, args.origin)
