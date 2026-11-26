"""/api/ai：AI 推薦理由與助理聊天（T12、T14）。"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from app.core.ids import oid
from app.core.ratelimit import ai_chat_limiter, matching_limiter
from app.core.validation import A, O, S, validate
from app.db import get_db
from app.deps import current_user
from app.responses import RawError
from app.services import ai_chat
from app.services.ai_explain import explain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])

MESSAGE_MAX = 500
HISTORY_MAX = 10
CHAT = O({
    "message": S(required=True),
    "history": A(O({"role": S(required=True, valid=("user", "assistant")),
                    "content": S(required=True, max=MESSAGE_MAX)})),
})


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


@router.post("/chat", summary="AI 助理聊天：先檢索知識庫再回答並附來源；醫療問題與查無資料不呼叫 LLM")
async def chat(body: dict | None = None, user: dict = Depends(current_user)):
    try:
        data = validate(CHAT, body)
    except RawError:
        raise HTTPException(400, "參數錯誤")
    message = data["message"].strip()
    if not 0 < len(message) <= MESSAGE_MAX:
        raise HTTPException(400, "參數錯誤")
    ai_chat_limiter.check(user["_id"])
    start = time.monotonic()
    result = await ai_chat.answer(message, (data.get("history") or [])[-HISTORY_MAX:])
    # 契約 §0：log 只記 user id、source、耗時，不記訊息內容與回覆
    logger.info("chat user=%s source=%s elapsed_ms=%d", user["_id"], result["source"],
                (time.monotonic() - start) * 1000)
    return {"success": True, "data": result}
