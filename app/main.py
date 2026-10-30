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
    model2: Literal["ready", "missing"]


class ApiError(BaseModel):
    error: str
    message: str


class Scores(BaseModel):
    normal: float = Field(ge=0, le=1)
    glare: float = Field(ge=0, le=1)
    severe: float = Field(ge=0, le=1)


class Brightest(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class GlareResult(BaseModel):
    model_version: str
    status: Literal["pilot"]
    level: Literal[0, 1, 2]
    label: str
    scores: Scores
    brightest: Brightest


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

    app = FastAPI(title="눈치 모델② API", version="0.1.0", lifespan=lifespan)
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

    @app.get("/health", response_model=Health)
    async def health():
        return {"status": "ok", "model2": "ready" if app.state.predictor is not None else "missing"}

    @app.post("/predict/glare", response_model=GlareResult,
              responses={status: {"model": ApiError} for status in [400, 413, 415, 422, 500, 503]})
    async def predict(image: Annotated[UploadFile, File()],
                      source: Annotated[Literal["camera", "game"], Form()] = "camera"):
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
