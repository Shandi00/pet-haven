"""請求大小上限（純 ASGI middleware），超過回 413。

有 Content-Length 時直接比對；沒有時（分段傳送）先讀進來，最多讀到上限 +1，沒超過再原樣交給應用程式。
"""
import json

from app.config import get_settings

_BODY = json.dumps({"success": False, "message": "上傳內容過大"}, ensure_ascii=False).encode("utf-8")


async def _send_413(send) -> None:
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json; charset=utf-8"),
                            (b"content-length", str(len(_BODY)).encode())]})
    await send({"type": "http.response.body", "body": _BODY})


class BodySizeLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = get_settings().max_request_bytes
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length is not None:
            try:
                too_large = int(length) > limit
            except ValueError:
                too_large = True
            if too_large:
                return await _send_413(send)
            return await self.app(scope, receive, send)

        # 沒有 Content-Length：先讀完（有上限）再重播
        messages, received = [], 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if received > limit:
                return await _send_413(send)
            if not message.get("more_body"):
                break

        async def replay():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, replay, send)
