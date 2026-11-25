import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def ok(data: Any) -> dict:
    return {"success": True, "data": data}


def fail(status_code: int, message: str, headers: dict | None = None, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "message": message, **extra},
                        headers=headers)


class ApiError(Exception):
    """需要在失敗回應多帶欄位（例如 errors）時使用。"""

    def __init__(self, status_code: int, message: str, **extra: Any) -> None:
        self.status_code, self.message, self.extra = status_code, message, extra


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return fail(exc.status_code, exc.message, **exc.extra)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        headers = getattr(exc, "headers", None)
        if isinstance(exc.detail, str) and exc.detail not in ("Not Found", "Method Not Allowed"):
            return fail(exc.status_code, exc.detail, headers)
        defaults = {404: "找不到請求的資源", 405: "不支援此請求方法"}
        return fail(exc.status_code, defaults.get(exc.status_code, "請求失敗"), headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return fail(400, "輸入資料格式錯誤")

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未處理的錯誤：%s %s", request.method, request.url.path)
        return fail(500, "伺服器發生錯誤")
