import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def ok(data: Any) -> dict:
    return {"success": True, "data": data}


def fail(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "message": message})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return fail(404, "找不到請求的資源")
        message = exc.detail if isinstance(exc.detail, str) else "請求失敗"
        return fail(exc.status_code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return fail(400, "輸入資料格式錯誤")

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未處理的錯誤：%s %s", request.method, request.url.path)
        return fail(500, "伺服器發生錯誤")
