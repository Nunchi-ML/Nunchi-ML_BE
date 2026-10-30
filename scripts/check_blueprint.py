"""Render 공식 JSON 스키마로 현재 Blueprint를 검증한다."""
import json
from pathlib import Path
from urllib.request import urlopen

import jsonschema
import yaml

if __name__ == "__main__":
    with urlopen("https://render.com/schema/render.yaml.json", timeout=30) as response:
        schema = json.load(response)
    config = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(config)
    print("Render Blueprint schema: passed")
