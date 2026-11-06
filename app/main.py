"""Vercel FE에서 사용하는 시범 모델② API. 이미지·위치는 저장하지 않는다.

여기서는 앱 설정(문서 · CORS · 오류 · 모델 불러오기)만 하고, 주소별 처리는 routers/ 에 모델마다 둔다.
"""
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from .errors import add_error_handlers
from .middleware import BodyLimitMiddleware
from .predictor import GlarePredictor
from .routers import glare, health, photo_g

__all__ = ["BodyLimitMiddleware", "app", "create_app"]


def load_photo_g(model_dir, runtime_dir):
    """선정 모델 묶음을 불러온다. 시범 모델이 먼저 import된 뒤 런타임 폴더만 경로에 추가한다."""
    model_dir, runtime_dir = Path(model_dir), Path(runtime_dir)
    if not (model_dir / "parameters.json").is_file() or not (runtime_dir / "nunchi_ml").is_dir():
        raise FileNotFoundError("Photo-g bundle or runtime missing")
    runtime = str(runtime_dir.resolve())
    if runtime not in sys.path:
        sys.path.insert(0, runtime)
    from .prototype import PhotoGPredictor
    return PhotoGPredictor(model_dir)


def create_app(model_dir=None, allowed_origins=None, photo_g_dir=None, photo_g_runtime=None):
    directory = Path(model_dir or os.getenv("MODEL_DIR", "models/model2-pilot-v1"))
    photo_g_directory = photo_g_dir or os.getenv("PHOTO_G_MODEL_DIR", "models/model2-photo-g-prototype-v1")
    photo_g_runtime_dir = photo_g_runtime or os.getenv("PHOTO_G_RUNTIME_DIR", "models/photo-g-runtime")

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = None
        try:
            app.state.predictor = await run_in_threadpool(GlarePredictor, directory)
        except Exception:
            logging.getLogger(__name__).warning("Model2 unavailable; check artifact and runtime versions")
            if os.getenv("MODEL_REQUIRED", "").lower() == "true":
                raise RuntimeError("Model2 must be ready before production startup") from None
        app.state.photo_g = None
        try:
            app.state.photo_g = await run_in_threadpool(load_photo_g, photo_g_directory, photo_g_runtime_dir)
        except Exception:
            logging.getLogger(__name__).warning("Photo-g model unavailable; /predict/glare/photo-g returns 503")
            if os.getenv("PHOTO_G_REQUIRED", "").lower() == "true":
                raise RuntimeError("Photo-g model must be ready before production startup") from None
        yield
        app.state.predictor = None
        app.state.photo_g = None

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
                      {"name": "모델② · 시범", "description": "사진 한 장의 시인성 저하 분류"},
                      {"name": "태양광 눈부심 분류 · 선정 모델",
                       "description": "사진 + 촬영 시각·위치·방향·날씨로 판정하는 발표 선정 모델"}],
    )
    app.add_middleware(BodyLimitMiddleware)
    origins = allowed_origins if allowed_origins is not None else [
        x.strip() for x in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x.strip()
    ]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    add_error_handlers(app)
    app.include_router(health.router)
    app.include_router(glare.router)
    app.include_router(photo_g.router)
    return app


app = create_app()
