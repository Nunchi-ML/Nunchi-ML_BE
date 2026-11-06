"""POST /predict/glare/photo-g — 발표 선정 모델(사진 + 해 위치·날씨) 눈부심 3단계 분류.

입력 규약·검증·오류 코드는 로컬 시제품(app/prototype.py)과 같다. 운영 시범 주소
/predict/glare는 그대로 두고 이 주소를 추가한다. 사진·촬영 정보는 저장하지 않는다.
"""
import hashlib
import json
import logging

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..image import MAX_IMAGE_BYTES, decode_image
from ..prototype import (MAX_CONTEXT_BYTES, ContextError, PhotoContext, PrototypeReading,
                         error)

router = APIRouter(tags=["태양광 눈부심 분류 · 선정 모델"])


@router.post("/predict/glare/photo-g", response_model=PrototypeReading,
             summary="JPEG 사진 + 촬영 정보로 눈부심 3단계 분류 (발표 선정 모델)",
             description=(
                 "multipart `image`(JPEG 원본, 1MiB·800만 픽셀 이하)와 `context`(촬영 정보 JSON, 8KiB 이하)를 보내세요. "
                 "context 필수 항목: lat, lon, heading, focal, width, height, captured_at, cloud, sunshine, "
                 "weather_observed_at, weather_source, geometry_source, projection=\"legacy_level_assumed\". "
                 "점수는 확률 보정 전 값이며 사고 확률이 아닙니다."))
async def predict(request: Request, image: UploadFile = File(...), context: str = Form(...)):
    try:
        predictor = getattr(request.app.state, "photo_g", None)
        if predictor is None:
            return error(503, "MODEL_NOT_READY")
        if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
            return error(422, "INVALID_REQUEST")
        try:
            metadata = PhotoContext.model_validate(json.loads(context)).model_dump(mode="json", exclude_none=True)
        except (ValueError, TypeError, RecursionError):
            return error(422, "INVALID_REQUEST")
        raw = await image.read(MAX_IMAGE_BYTES + 1)
        decoded = await run_in_threadpool(decode_image, raw, image.content_type)
        try:
            result = await run_in_threadpool(predictor.analyze, decoded, metadata, hashlib.sha256(raw).hexdigest())
            return PrototypeReading.model_validate(result)
        except ContextError:
            return error(400, "INVALID_CONTEXT")
        except Exception:
            logging.getLogger(__name__).warning("Photo-g inference failed; request omitted")
            return error(500, "INFERENCE_FAILED")
    finally:
        await image.close()
