"""API 오류: 코드 · 한국어 안내 · Swagger 예시를 한곳에서."""
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

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


class ApiError(BaseModel):
    error: str
    message: str


def documented_errors():
    statuses = {400: "INVALID_IMAGE", 413: "IMAGE_TOO_LARGE", 415: "UNSUPPORTED_IMAGE_TYPE",
                422: "INVALID_REQUEST", 500: "INFERENCE_FAILED", 503: "MODEL_NOT_READY"}
    return {status: {"model": ApiError, "description": MESSAGES[code], "content": {
        "application/json": {"example": {"error": code, "message": MESSAGES[code]}}
    }} for status, code in statuses.items()}


def add_error_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in MESSAGES else "INVALID_REQUEST"
        return error(exc.status_code, code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error(422, "INVALID_REQUEST")
