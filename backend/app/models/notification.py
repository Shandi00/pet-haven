"""notifications collection：對應舊版 models/Notification.js 與 createNotification()。"""
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from app.core.populate import populate
from app.core.schema import F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json
from app.db import get_db
from app.realtime import emit_to_user

logger = logging.getLogger(__name__)

TYPES = ("message", "comment", "reply", "like", "adoption_received", "adoption_approved", "adoption_rejected",
         "adoption_completed",
         # 舊版少了這個值，取消申請的通知會驗證失敗而送不出去
         "adoption_cancelled",
         "pet_status_changed", "post_published", "lost_pet_found", "system")

SCHEMA = {
    "recipient": F("oid", required=True),
    "sender": F("oid"),
    "type": F("str", enum=TYPES, required=True),
    "title": F("str", required=True, maxlength=100),
    "content": F("str", required=True, maxlength=500),
    "relatedPost": F("oid"), "relatedComment": F("oid"), "relatedPet": F("oid"),
    "relatedAdoption": F("oid"), "relatedMessage": F("oid"),
    "link": F("str", maxlength=200),
    "icon": F("str", default="bell"),
    "isRead": F("bool", default=False),
    "readAt": F("date"),
    "priority": F("str", enum=("low", "normal", "high", "urgent"), default="normal"),
    "metadata": F("mixed"),
    "expiresAt": F("date", default=lambda: datetime.now(timezone.utc) + timedelta(days=30)),
}

_CONTROL = re.compile(r"[\u0000-\u001F\u007F-\u009F]")


def _clean(s):
    return unicodedata.normalize("NFC", _CONTROL.sub("", s)) if isinstance(s, str) else s


def notification_json(doc: dict) -> dict:
    out = to_json(doc)
    out["isUrgent"] = doc.get("priority") in ("urgent", "high")
    return out


async def create_notification(data: dict) -> dict:
    """建立通知、populate、補上 relatedPet，並用 Socket.IO 推送 newNotification。"""
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    doc["title"], doc["content"] = _clean(doc.get("title")), _clean(doc.get("content"))
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Notification")
    now = datetime.now(timezone.utc)
    doc.update(createdAt=now, updatedAt=now, __v=0)
    doc["_id"] = (await get_db().notifications.insert_one(doc)).inserted_id

    related_pet = None
    metadata = doc.get("metadata") or {}
    adoption_id = doc.get("relatedAdoption") or (metadata.get("relatedAdoption") if isinstance(metadata, dict) else None)
    if not doc.get("relatedPet") and adoption_id:
        try:
            adoption = await get_db().adoptions.find_one({"_id": adoption_id}, {"pet": 1})
            if adoption and adoption.get("pet"):
                related_pet = await get_db().pets.find_one({"_id": adoption["pet"]}, {"name": 1, "species": 1, "photos": 1})
                if related_pet:
                    await get_db().notifications.update_one({"_id": doc["_id"]},
                                                            {"$set": {"relatedPet": related_pet["_id"]}})
                    doc["relatedPet"] = related_pet["_id"]
        except Exception:
            logger.warning("通知補 relatedPet 失敗", exc_info=True)

    await populate(doc, "sender", "users", "firstName lastName username avatar_url")
    await populate(doc, "relatedPet", "pets", "name species photos")
    await emit_to_user(doc["recipient"], "newNotification", {
        "_id": doc["_id"], "type": doc["type"], "title": doc["title"], "content": doc["content"],
        "link": doc.get("link"), "icon": doc.get("icon"), "priority": doc.get("priority"),
        "isRead": doc.get("isRead"), "createdAt": doc["createdAt"], "sender": doc.get("sender"),
        "relatedAdoption": adoption_id,
        "relatedPet": doc.get("relatedPet") or related_pet,
    })
    return doc


async def safe_notify(data: dict) -> None:
    """通知失敗不影響主流程（舊版都包在 try/catch）。"""
    try:
        await create_notification(data)
    except Exception:
        logger.exception("建立通知失敗")


async def notify_owner_and_shelters(owner_id, data: dict, broadcast_content: str | None = None) -> None:
    """通知寵物擁有者；擁有者是 admin（政府資料匯入的寵物）或不存在時，同時通知所有收容所帳號。"""
    await safe_notify({**data, "recipient": owner_id})
    try:
        owner = await get_db().users.find_one({"_id": owner_id}, {"role": 1})
        if not owner or owner.get("role") == "admin":
            async for s in get_db().users.find({"role": "shelter", "isActive": True}, {"_id": 1}):
                if s["_id"] != owner_id:
                    await safe_notify({**data, "recipient": s["_id"],
                                       "content": broadcast_content or data["content"]})
    except Exception:
        logger.exception("廣播給收容所使用者時發生錯誤")
