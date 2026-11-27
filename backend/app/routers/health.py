from fastapi import APIRouter, Depends

from app.db import is_db_ready
from app.responses import fail, ok

# 不設 prefix：根路徑 / 也放在這裡（其他路由都是 /api 開頭）
router = APIRouter(tags=["System"])


@router.get("/", summary="API 首頁：服務名稱、文件與健康檢查的位置")
async def root():
    # 打開 http://localhost:5000/ 原本回 404「找不到請求的資源」，容易以為後端壞了
    return ok({"name": "Pet Haven API", "status": "ok", "docs": "/api-docs", "health": "/api/health"})


@router.get("/api/health", summary="健康檢查（不檢查資料庫）")
async def health():
    return ok({"status": "ok"})


@router.get(
    "/api/ready",
    summary="就緒檢查（資料庫可連線時回 200，否則 503）",
    responses={503: {"description": "資料庫無法連線"}},
)
async def ready(db_ready: bool = Depends(is_db_ready)):
    if not db_ready:
        return fail(503, "資料庫無法連線")
    return ok({"status": "ready"})
