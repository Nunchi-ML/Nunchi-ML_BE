"""요청 크기 제한 — multipart 파싱 전에 실제 수신량으로 자름."""
from .errors import error
from .image import MAX_IMAGE_BYTES


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
