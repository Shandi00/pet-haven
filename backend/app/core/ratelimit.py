"""簡單的記憶體速率限制，對應舊版 express-rate-limit 的登入限制。"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

WINDOW_SECONDS = 15 * 60


class FailureLimiter:
    """只記錄失敗次數（舊版 skipSuccessfulRequests: true）。
    shortcut: 存在單一程序的記憶體，多個 worker 時各自計算，要部署多台時改用 Redis。"""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)

    def _max(self) -> int | None:
        env = get_settings().app_env
        if env == "test":
            return None
        return 50 if env == "development" else 5

    def _key(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        limit = self._max()
        if limit is None:
            return
        q = self._hits[self._key(request)]
        now = time.monotonic()
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "嘗試次數過多，請稍後再試")

    def fail(self, request: Request) -> None:
        self._hits[self._key(request)].append(time.monotonic())


auth_limiter = FailureLimiter()
