"""POST /predict/glare — 모델 ② 사진 한 장 눈부심 3단계 분류 (시범)."""
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ..errors import documented_errors, error
from ..image import MAX_IMAGE_BYTES, decode_image

router = APIRouter(tags=["모델② · 시범"])


class Scores(BaseModel):
    normal: float = Field(ge=0, le=1, description="정상 클래스 모델 점수 (확률 보정 전)")
    glare: float = Field(ge=0, le=1, description="눈부심 클래스 모델 점수 (확률 보정 전)")
    severe: float = Field(ge=0, le=1, description="심한 눈부심 클래스 모델 점수 (확률 보정 전)")


class Brightest(BaseModel):
    x: float = Field(ge=0, le=1, description="전체 사진 기준 가로 위치. 0=왼쪽, 1=오른쪽")
    y: float = Field(ge=0, le=1, description="전체 사진 기준 세로 위치. 0=위, 1=아래")


class GlareResult(BaseModel):
    model_version: str
    status: Literal["pilot"]
    level: Literal[0, 1, 2] = Field(description="0 정상 / 1 눈부심 / 2 심한 눈부심")
    label: str
    scores: Scores
    brightest: Brightest
    model_config = {"json_schema_extra": {"examples": [{
        "model_version": "model2-pilot-v1", "status": "pilot", "level": 2,
        "label": "심한 눈부심", "scores": {"normal": 0.05, "glare": 0.13, "severe": 0.82},
        "brightest": {"x": 0.31, "y": 0.12},
    }]}}


@router.post("/predict/glare", response_model=GlareResult, summary="JPEG 사진의 눈부심 3단계 분류",
             description="multipart image 필드에 JPEG를 선택하세요. source는 이미지 출처이며 현재 모델의 특징 입력에는 포함하지 않습니다.",
             responses=documented_errors())
async def predict(request: Request,
                  image: Annotated[UploadFile, File(description="전체 화면 JPEG. 파일 1MiB 이하·800만 픽셀 이하. 긴 변 1280·quality 0.95 권장 규약")],
                  source: Annotated[Literal["camera", "game"], Form(description="camera=실제 카메라 / game=운전 시뮬레이터 화면(실험)")] = "camera"):
    predictor = request.app.state.predictor
    try:
        if predictor is None:
            return error(503, "MODEL_NOT_READY")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        frame = await run_in_threadpool(decode_image, data, image.content_type)
        try:
            return await run_in_threadpool(predictor.predict, frame)
        except (ValueError, RuntimeError):
            return error(500, "INFERENCE_FAILED")
    finally:
        await image.close()
