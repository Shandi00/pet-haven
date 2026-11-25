from fastapi import APIRouter, Depends

from app.db import is_db_ready
from app.responses import fail, ok

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health", summary="健康檢查（不檢查資料庫）")
async def health():
    return ok({"status": "ok"})


@router.get(
    "/ready",
    summary="就緒檢查（資料庫可連線時回 200，否則 503）",
    responses={503: {"description": "資料庫無法連線"}},
)
async def ready(db_ready: bool = Depends(is_db_ready)):
    if not db_ready:
        return fail(503, "資料庫無法連線")
    return ok({"status": "ready"})
