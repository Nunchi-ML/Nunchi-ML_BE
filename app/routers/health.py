"""GET /health — 서버와 모델 준비 상태."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["서버 상태"])


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    model2: Literal["ready", "missing"] = Field(description="ready면 추론 가능, missing이면 추론 요청에 503 반환")
    model2_photo_g: Literal["ready", "missing"] = Field(
        "missing", description="발표 선정 모델(/predict/glare/photo-g) 준비 상태")
    model_config = {"json_schema_extra": {"examples": [
        {"status": "ok", "model2": "ready", "model2_photo_g": "ready"},
        {"status": "ok", "model2": "missing", "model2_photo_g": "missing"},
    ]}}


@router.get("/health", response_model=Health, summary="서버와 모델② 준비 상태 확인",
            description="서버가 동작하면 HTTP 200입니다. model2가 missing이면 사진 분석은 503이며 가짜 판정을 반환하지 않습니다.")
async def health(request: Request):
    return {"status": "ok", "model2": "ready" if request.app.state.predictor is not None else "missing",
            "model2_photo_g": "ready" if getattr(request.app.state, "photo_g", None) is not None else "missing"}
