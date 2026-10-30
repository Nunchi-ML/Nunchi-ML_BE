"""JPEG 헤더/해상도를 먼저 확인하고 AI 공통 패키지로 추론한다."""
from io import BytesIO
import warnings

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import HTTPException

MAX_IMAGE_BYTES = 1024 * 1024
MAX_PIXELS = 8_000_000


def decode_image(data, content_type):
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, detail="IMAGE_TOO_LARGE")
    if content_type != "image/jpeg":
        raise HTTPException(415, detail="UNSUPPORTED_IMAGE_TYPE")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as header:
                if header.format != "JPEG":
                    raise HTTPException(415, detail="UNSUPPORTED_IMAGE_TYPE")
                width, height = header.size
                if width * height > MAX_PIXELS:
                    raise HTTPException(413, detail="IMAGE_TOO_LARGE")
                header.verify()
        # 브라우저 canvas JPEG에는 EXIF가 없음. 직접 보낸 JPEG는 OpenCV가 EXIF 회전을 적용.
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[0] * image.shape[1] > MAX_PIXELS:
            raise HTTPException(400, detail="INVALID_IMAGE")
        return image
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, cv2.error,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(400, detail="INVALID_IMAGE") from None
