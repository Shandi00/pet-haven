"""log 設定：統一格式、request id、存取紀錄與稽核紀錄。

規則：log 只記使用者 id，不記姓名、Email、電話、密碼、token；路徑不含 query string（OAuth code 會在那裡）。
"""
import logging
import logging.config
import re
import time
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

access_log = logging.getLogger("access")
audit_log = logging.getLogger("audit")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str = "INFO") -> None:
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"request_id": {"()": RequestIdFilter}},
        "formatters": {"default": {
            "format": "%(asctime)s %(levelname)s %(name)s rid=%(request_id)s %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default",
                                 "filters": ["request_id"]}},
        "root": {"handlers": ["console"], "level": level.upper()},
        # httpx 在 INFO 會記錄完整網址（含 query string）；uvicorn 的存取紀錄由我們自己的 access log 取代
        "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"},
                    "uvicorn.access": {"level": "WARNING"}},
    })
    # 每筆 record 都要有 request_id（caplog 等其他 handler 也會用到）
    for name in ("", "access", "audit"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RequestIdFilter) for f in lg.filters):
            lg.addFilter(RequestIdFilter())


def audit(action: str, **fields) -> None:
    """稽核紀錄：action 加上 key=value。只能放 id、角色、狀態這類欄位。"""
    detail = " ".join(f"{k}={v}" for k, v in fields.items())
    audit_log.info(f"{action} {detail}".strip())


# 每個回應都帶的安全標頭：不讓瀏覽器猜檔案類型（上傳的檔案不會被當成網頁執行）、不能被別的網站用 iframe 嵌入、
# 連到外站時只送出來源網域。CSP 要列出 Google 登入、Turnstile、圖片來源等網域，等展示環境確定再加。
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
]


class RequestContextMiddleware:
    """純 ASGI middleware：設定 request id、回傳 X-Request-ID 與安全標頭、記錄存取紀錄與 401/403。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message.setdefault("headers", [])
                message["headers"] = list(message["headers"]) + [(b"x-request-id", rid.encode())] + SECURITY_HEADERS
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            method, path, code = scope.get("method"), scope.get("path"), status["code"]
            ms = (time.perf_counter() - start) * 1000
            access_log.info("%s %s %s %.0fms", method, path, code, ms)
            if code in (401, 403):
                audit_log.info("access_denied status=%s %s %s", code, method, path)
            request_id_var.reset(token)
