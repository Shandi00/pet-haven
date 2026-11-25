"""/api/browsing-history：對應舊版 routes/browsing-history.js。"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.core.ids import oid
from app.core.populate import populate
from app.core.serialize import to_json
from app.db import get_db
from app.deps import current_user
from app.models.pet import pet_json
from app.responses import RawError

router = APIRouter(prefix="/api/browsing-history", tags=["Users"])


@router.post("", summary="記錄瀏覽")
async def record(body: dict | None = None, user: dict = Depends(current_user)):
    pet_id = oid((body or {}).get("petId"))
    if pet_id is None:
        raise RawError(400, {"error": "缺少寵物 ID"})
    users = get_db().users
    await users.update_one({"_id": user["_id"]}, {"$pull": {"browsingHistory": {"pet": pet_id}}})
    result = await users.update_one({"_id": user["_id"]}, {"$push": {"browsingHistory": {
        "$each": [{"pet": pet_id, "viewedAt": datetime.now(timezone.utc)}], "$position": 0, "$slice": 50}}})
    if result.matched_count == 0:
        raise RawError(404, {"error": "使用者不存在"})
    return {"message": "瀏覽歷史已記錄", "success": True}


@router.get("", summary="瀏覽歷史（只回傳仍可認養的寵物）")
async def history(request: Request, user: dict = Depends(current_user)):
    try:
        limit = int(request.query_params.get("limit", 20))
    except ValueError:
        limit = 20
    full = await get_db().users.find_one({"_id": user["_id"]}, {"browsingHistory": 1})
    if not full:
        raise RawError(404, {"error": "使用者不存在"})
    items = full.get("browsingHistory") or []
    await populate(items, "pet", "pets", "name breed species age gender size photos shelterInfo adoptionStatus")
    out = [{**pet_json(i["pet"]), "viewedAt": i.get("viewedAt")} for i in items
           if isinstance(i.get("pet"), dict) and i["pet"].get("adoptionStatus") == "available"][:limit]
    return {"history": to_json(out), "count": len(out)}


@router.delete("", summary="清除瀏覽歷史")
async def clear(user: dict = Depends(current_user)):
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"browsingHistory": []}})
    return {"message": "瀏覽歷史已清除", "success": True}
