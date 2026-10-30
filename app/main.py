"""Vercel FE에서 사용하는 시범 모델② API. 이미지·위치는 저장하지 않는다."""
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool

from nunchi_glare.inference import GlarePredictor
from .glare import MAX_IMAGE_BYTES, decode_image

MESSAGES = {
    "MODEL_NOT_READY": "눈부심 모델을 준비 중입니다.",
    "IMAGE_TOO_LARGE": "1MB 이하, 800만 픽셀 이하의 사진을 보내 주세요.",
    "UNSUPPORTED_IMAGE_TYPE": "JPEG 사진만 지원합니다.",
    "INVALID_IMAGE": "사진을 읽을 수 없습니다.",
    "INVALID_REQUEST": "image와 source(camera 또는 game)를 확인해 주세요.",
    "INFERENCE_FAILED": "사진 분석에 실패했습니다. 다시 시도해 주세요.",
}


def error(status, code):
    return JSONResponse(status_code=status, content={"error": code, "message": MESSAGES[code]})


class BodyLimitMiddleware:
    """Content-Length가 없거나 틀려도 multipart 파싱 전에 실제 수신량을 제한."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != "/predict/glare":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            # 파일 1MB + multipart 필드·헤더 오버헤드 64KB.
            if size > MAX_IMAGE_BYTES + 65536:
                return await error(413, "IMAGE_TOO_LARGE")(scope, receive, send)
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    model2: Literal["ready", "missing"] = Field(description="ready면 추론 가능, missing이면 추론 요청에 503 반환")
    model_config = {"json_schema_extra": {"examples": [
        {"status": "ok", "model2": "ready"}, {"status": "ok", "model2": "missing"},
    ]}}


class ApiError(BaseModel):
    error: str
    message: str


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


def documented_errors():
    statuses = {400: "INVALID_IMAGE", 413: "IMAGE_TOO_LARGE", 415: "UNSUPPORTED_IMAGE_TYPE",
                422: "INVALID_REQUEST", 500: "INFERENCE_FAILED", 503: "MODEL_NOT_READY"}
    return {status: {"model": ApiError, "description": MESSAGES[code], "content": {
        "application/json": {"example": {"error": code, "message": MESSAGES[code]}}
    }} for status, code in statuses.items()}


def create_app(model_dir=None, allowed_origins=None):
    directory = Path(model_dir or os.getenv("MODEL_DIR", "models/model2-pilot-v1"))

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = None
        try:
            app.state.predictor = await run_in_threadpool(GlarePredictor, directory)
        except Exception:
            logging.getLogger(__name__).warning("Model2 unavailable; check artifact and runtime versions")
        yield
        app.state.predictor = None

    app = FastAPI(
        title="눈치 드라이브 · 운전 시뮬레이터 API", version="0.1.0", lifespan=lifespan,
        description=(
            "전방 사진 한 장을 **정상 / 눈부심 / 심한 눈부심**으로 분류하는 모델② 시범 API입니다.\n\n"
            "**사용 순서**: `/health`에서 `model2=ready` 확인 → `/predict/glare`의 Try it out → "
            "JPEG 사진 선택, source 지정 → Execute. 요청 사진과 위치는 저장하지 않습니다.\n\n"
            "**입력 규약**: 전체 화면 비율 유지, 긴 변 최대 1280, JPEG quality 0.95, "
            "파일 1MiB(1,048,576바이트) 이하. 중앙 자르기·letterbox·미러링 없음. "
            "서버는 전체 화면을 640×368로 변환합니다.\n\n"
            "**결과 해석**: scores는 보정 전 모델 점수, brightest는 밝은 곳 후보입니다. "
            "태양 검출·앞유리 차광 좌표·사고 확률을 뜻하지 않습니다. "
            "시뮬레이터 화면은 실험 입력이며 실영상 검증과 구분합니다.\n\n"
            "GLARE 130장 Claude 보조 시범 라벨로 학습했으며 사람 2인·실기기 검증은 남아 있습니다. "
            "응답 예시는 설명용 값입니다. 실제 운전 중에는 동승자만 사용하세요."
        ),
        docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json",
        swagger_ui_parameters={"displayRequestDuration": True, "defaultModelsExpandDepth": 1},
        openapi_tags=[{"name": "서버 상태", "description": "서버 및 모델 준비 상태"},
                      {"name": "모델② · 시범", "description": "사진 한 장의 시인성 저하 분류"}],
    )
    app.add_middleware(BodyLimitMiddleware)
    origins = allowed_origins if allowed_origins is not None else [
        x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip()
    ]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in MESSAGES else "INVALID_REQUEST"
        return error(exc.status_code, code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(422, "INVALID_REQUEST")

    @app.get("/health", response_model=Health, tags=["서버 상태"],
             summary="서버와 모델② 준비 상태 확인",
             description="서버가 동작하면 HTTP 200입니다. model2가 missing이면 사진 분석은 503이며 가짜 판정을 반환하지 않습니다.")
    async def health():
        return {"status": "ok", "model2": "ready" if app.state.predictor is not None else "missing"}

    @app.post("/predict/glare", response_model=GlareResult,
              tags=["모델② · 시범"], summary="JPEG 사진의 눈부심 3단계 분류",
              description="multipart image 필드에 JPEG를 선택하세요. source는 이미지 출처이며 현재 모델의 특징 입력에는 포함하지 않습니다.",
              responses=documented_errors())
    async def predict(image: Annotated[UploadFile, File(description="전체 화면 JPEG. 파일 1MiB 이하·800만 픽셀 이하. 긴 변 1280·quality 0.95 권장 규약")],
                      source: Annotated[Literal["camera", "game"], Form(description="camera=실제 카메라 / game=운전 시뮬레이터 화면(실험)")] = "camera"):
        try:
            if app.state.predictor is None:
                return error(503, "MODEL_NOT_READY")
            data = await image.read(MAX_IMAGE_BYTES + 1)
            frame = await run_in_threadpool(decode_image, data, image.content_type)
            try:
                return await run_in_threadpool(app.state.predictor.predict, frame)
            except (ValueError, RuntimeError):
                return error(500, "INFERENCE_FAILED")
        finally:
            await image.close()

    return app


app = create_app()
