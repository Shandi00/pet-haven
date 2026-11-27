"""/api/notifications：對應舊版 routes/notifications.js。"""
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.ids import oid, same_id
from app.core.populate import populate
from app.db import get_db
from app.deps import current_user
from app.models.notification import notification_json
from app.core.params import limit_param

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.get("", summary="我的通知")
async def list_notifications(request: Request, user: dict = Depends(current_user)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), limit_param(q.get("limit"), 20)
    query: dict = {"recipient": user["_id"]}
    if q.get("unreadOnly") == "true":
        query["isRead"] = False
    docs = await get_db().notifications.find(query).sort("createdAt", -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "sender", "users", "firstName lastName username avatar_url")
    await populate(docs, "relatedPet", "pets", "name species photos")
    total = await get_db().notifications.count_documents(query)
    return {"success": True, "data": {
        "notifications": [notification_json(d) for d in docs],
        "pagination": {"page": page, "limit": limit, "total": total,
                       "pages": math.ceil(total / limit) if limit else 0}}}


@router.get("/unread-count", summary="未讀數量")
async def unread_count(user: dict = Depends(current_user)):
    count = await get_db().notifications.count_documents({"recipient": user["_id"], "isRead": False})
    return {"success": True, "data": {"count": count}}


async def _own(notification_id: str, user: dict, action: str) -> dict:
    nid = oid(notification_id)
    doc = await get_db().notifications.find_one({"_id": nid}) if nid else None
    if not doc:
        raise HTTPException(404, "找不到指定的通知")
    if not same_id(doc.get("recipient"), user["_id"]):
        raise HTTPException(403, f"沒有權限{action}此通知")
    return doc


@router.post("/read-all", summary="全部標記已讀")
async def read_all(user: dict = Depends(current_user)):
    result = await get_db().notifications.update_many(
        {"recipient": user["_id"], "isRead": False},
        {"$set": {"isRead": True, "readAt": datetime.now(timezone.utc)}})
    return {"success": True, "message": "所有通知已標記為已讀", "data": {"modifiedCount": result.modified_count}}


@router.post("/{notification_id}/read", summary="標記已讀")
async def mark_read(notification_id: str, user: dict = Depends(current_user)):
    doc = await _own(notification_id, user, "操作")
    now = datetime.now(timezone.utc)
    await get_db().notifications.update_one({"_id": doc["_id"]},
                                            {"$set": {"isRead": True, "readAt": now, "updatedAt": now}})
    doc.update(isRead=True, readAt=now, updatedAt=now)
    return {"success": True, "message": "通知已標記為已讀", "data": notification_json(doc)}


@router.delete("/{notification_id}", summary="刪除通知")
async def delete_one(notification_id: str, user: dict = Depends(current_user)):
    doc = await _own(notification_id, user, "刪除")
    await get_db().notifications.delete_one({"_id": doc["_id"]})
    return {"success": True, "message": "通知已刪除"}


@router.delete("", summary="刪除所有已讀通知")
async def delete_read(user: dict = Depends(current_user)):
    result = await get_db().notifications.delete_many({"recipient": user["_id"], "isRead": True})
    return {"success": True, "message": "已刪除所有已讀通知", "data": {"deletedCount": result.deleted_count}}
