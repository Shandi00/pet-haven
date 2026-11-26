"""/api/ai：AI 推薦理由（T12）。聊天 POST /api/ai/chat 之後加在這個檔案（後端計畫 Task 6）。"""
from fastapi import APIRouter, Depends, HTTPException

from app.core.ids import oid
from app.core.ratelimit import matching_limiter
from app.db import get_db
from app.deps import current_user
from app.services.ai_explain import explain

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/explain", summary="為指定動物產生推薦理由（依目前登入者的配對檔案）")
async def explain_pet(body: dict | None = None, user: dict = Depends(current_user)):
    pet_id = (body or {}).get("petId")
    pid = oid(pet_id) if isinstance(pet_id, str) else None
    if not pid:
        raise HTTPException(400, "參數錯誤")
    matching_limiter.check(user["_id"])
    # 已下架（isActive=False）的動物不產生理由，與 Top 3 候選條件一致
    pet = await get_db().pets.find_one({"_id": pid, "isActive": {"$ne": False}})
    if not pet:
        raise HTTPException(404, "找不到指定的寵物")
    full = await get_db().users.find_one({"_id": user["_id"]}, {"password": 0})
    if not full:
        raise HTTPException(404, "找不到使用者資料")
    return {"success": True, "data": {"reason": await explain(pet, full)}}
