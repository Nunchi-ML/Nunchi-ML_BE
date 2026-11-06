"""Opt-in local photo+G prototype. Not mounted by the production app."""
from contextlib import asynccontextmanager
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from time import perf_counter
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import (AwareDatetime, BaseModel, ConfigDict, Field,
                      field_validator, model_validator)
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from .image import MAX_IMAGE_BYTES, decode_image
from .middleware import BodyLimitMiddleware

PATH = "/predict/glare/prototype"
VARIANT = "B_geometry_aug"
VERSION = "photo-g-candidate-v1"
MAX_CONTEXT_BYTES = 8192
MESSAGES = {
    "MODEL_NOT_READY": "사진+G 시제품 모델을 준비 중입니다.",
    "IMAGE_TOO_LARGE": "1MiB 이하, 800만 픽셀 이하의 JPEG를 보내 주세요.",
    "UNSUPPORTED_IMAGE_TYPE": "JPEG 사진만 지원합니다.",
    "INVALID_IMAGE": "사진을 읽을 수 없습니다.",
    "INVALID_REQUEST": "JPEG image와 촬영 정보 context(JSON)를 확인해 주세요.",
    "INVALID_CONTEXT": "촬영 정보의 원본 사진 크기·시각·기상 관측시각을 확인해 주세요.",
    "INFERENCE_FAILED": "사진 분석에 실패했습니다. 입력을 저장하지 않았습니다.",
}


def error(status, code):
    return JSONResponse(status_code=status, content={"error": code, "message": MESSAGES[code]})


class PhotoContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(strict=True, ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(strict=True, ge=-180, le=180, allow_inf_nan=False)
    heading: float = Field(strict=True, ge=0, lt=360, allow_inf_nan=False)
    focal: float = Field(strict=True, ge=1e-6, le=100, allow_inf_nan=False)
    width: int = Field(strict=True, ge=1, le=100000)
    height: int = Field(strict=True, ge=1, le=100000)
    captured_at: AwareDatetime
    cloud: float = Field(strict=True, ge=0, le=10, allow_inf_nan=False)
    sunshine: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    weather_observed_at: AwareDatetime
    weather_available_at: AwareDatetime | None = None
    weather_source: str = Field(min_length=1, max_length=512)
    geometry_source: str = Field(min_length=1, max_length=512)
    projection: Literal["legacy_level_assumed"]

    @field_validator("captured_at", "weather_observed_at", "weather_available_at", mode="before")
    @classmethod
    def explicit_time(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("Explicit ISO timestamp with timezone required")
        return value

    @field_validator("weather_source", "geometry_source")
    @classmethod
    def provenance(cls, value):
        if not value.strip():
            raise ValueError("Nonblank provenance required")
        return value.strip()


Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Scores(BaseModel):
    normal: Score
    glare: Score
    severe: Score


class PrototypeReading(BaseModel):
    model_version: Literal["photo-g-candidate-v1"]
    status: Literal["prototype"]
    variant: Literal["B_geometry_aug"]
    level: Literal[0, 1, 2]
    label: str
    scores: Scores
    alert_score: Score
    conditional_severe_score: Score
    captured_at: AwareDatetime
    image_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    weather_age_seconds: float = Field(ge=0, le=3600, allow_inf_nan=False)
    weather_availability_verified: bool
    projection: Literal["legacy_level_assumed"]
    camera_pose_validated: Literal[False]
    roadside_validated: Literal[False]
    future_route_validated: Literal[False]
    processing_ms: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def consistent_scores(self):
        a, b = self.alert_score, self.conditional_severe_score
        actual = [self.scores.normal, self.scores.glare, self.scores.severe]
        if any(not math.isclose(x, y, abs_tol=1e-9) for x, y in
               zip(actual, [1 - a, a * (1 - b), a * b])):
            raise ValueError("Inconsistent conditional scores")
        level = 0 if a < .5 else (2 if b >= .5 else 1)
        if self.level != level or self.label != ["정상", "눈부심", "심한 눈부심"][level]:
            raise ValueError("Conditional decision mismatch")
        return self


class ContextError(ValueError):
    pass


class PhotoGPredictor:
    def __init__(self, directory):
        # Import only on opt-in startup; the deployed pilot wheel has no hybrid module.
        from nunchi_ml.glare.hybrid import HybridCandidate
        from nunchi_ml.glare.roadside import photo_g
        self.model = HybridCandidate(directory)
        self.photo_g = photo_g

    def analyze(self, image, metadata, image_sha256):
        started = perf_counter()
        try:
            prepared = self.photo_g(metadata, image.shape)
        except ValueError as exc:
            raise ContextError from exc
        result = self.model.predict_image(image, prepared["features"], VARIANT)
        if (result["model_version"] != VERSION or result["status"] != "candidate"
                or result["variant"] != VARIANT or result["roadside_validated"] is not False):
            raise ValueError("Unexpected candidate contract")
        level = int(result["level"][0])
        scores = [float(x) for x in result["joint_scores"][0]]
        return dict(model_version=VERSION, status="prototype", variant=VARIANT,
                    level=level, label=["정상", "눈부심", "심한 눈부심"][level],
                    scores=dict(zip(["normal", "glare", "severe"], scores)),
                    alert_score=float(result["alert_score"][0]),
                    conditional_severe_score=float(result["conditional_severe_score"][0]),
                    image_sha256=image_sha256, captured_at=prepared["captured_at"],
                    weather_age_seconds=prepared["weather_age_seconds"],
                    weather_availability_verified=prepared["weather_availability_verified"],
                    projection=prepared["projection"], camera_pose_validated=False,
                    roadside_validated=False, future_route_validated=False,
                    processing_ms=(perf_counter() - started) * 1000)


class PrototypeBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == PATH:
            # Apply the established actual-byte limit using a copied ASGI scope.
            limited_scope = dict(scope, path="/predict/glare")

            async def downstream(_, replay, respond):
                return await self.app(scope, replay, respond)

            return await BodyLimitMiddleware(downstream)(limited_scope, receive, send)
        return await self.app(scope, receive, send)


def create_prototype_app(model_dir=None, allowed_origins=None, *, predictor_factory=PhotoGPredictor):
    directory = model_dir or os.getenv("HYBRID_MODEL_DIR")

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = None
        try:
            if directory is None:
                raise ValueError("HYBRID_MODEL_DIR required")
            app.state.predictor = await run_in_threadpool(predictor_factory, Path(directory))
        except Exception:
            logging.getLogger(__name__).warning("Photo+G prototype unavailable; check bundle/runtime")
            if os.getenv("PROTOTYPE_MODEL_REQUIRED", "").lower() == "true":
                raise RuntimeError("Photo+G prototype must be ready before startup") from None
        yield
        app.state.predictor = None

    app = FastAPI(title="눈치 · 사진+G 로컬 시제품", version="0.1.0", lifespan=lifespan,
                  description="제안 검토용 별도 앱. 촬영 시점의 사진 분류이며 미래 경로·사고 확률이 아닙니다.")
    app.add_middleware(PrototypeBodyLimit)
    origins = allowed_origins if allowed_origins is not None else [
        x.strip() for x in os.getenv("PROTOTYPE_ALLOWED_ORIGINS",
                                    "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in MESSAGES else "INVALID_REQUEST"
        return error(exc.status_code, code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(422, "INVALID_REQUEST")

    @app.get("/health")
    async def health(request: Request):
        return {"status": "ok", "model2_prototype": "ready" if request.app.state.predictor else "missing",
                "variant": VARIANT, "production": False}

    @app.post(PATH, response_model=PrototypeReading)
    async def predict(request: Request, image: UploadFile = File(...), context: str = Form(...)):
        try:
            predictor = request.app.state.predictor
            if predictor is None:
                return error(503, "MODEL_NOT_READY")
            if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
                return error(422, "INVALID_REQUEST")
            try:
                # validate_json alone coerces JSON strings into numeric fields in some modes.
                metadata = PhotoContext.model_validate(json.loads(context)).model_dump(mode="json", exclude_none=True)
            except (ValueError, TypeError, RecursionError):
                return error(422, "INVALID_REQUEST")
            raw = await image.read(MAX_IMAGE_BYTES + 1)
            decoded = await run_in_threadpool(decode_image, raw, image.content_type)
            try:
                result = await run_in_threadpool(predictor.analyze, decoded, metadata,
                                                 hashlib.sha256(raw).hexdigest())
                return PrototypeReading.model_validate(result)
            except ContextError:
                return error(400, "INVALID_CONTEXT")
            except Exception:
                logging.getLogger(__name__).warning("Photo+G inference failed; request omitted")
                return error(500, "INFERENCE_FAILED")
        finally:
            await image.close()

    return app


app = create_prototype_app()
