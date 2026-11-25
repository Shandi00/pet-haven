"""messages collection：對應舊版 models/Message.js。"""
from datetime import datetime, timedelta, timezone

from app.core.schema import Arr, F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json

SCHEMA = {
    "content": F("str", required="訊息內容為必填項目", trim=True, maxlength=(2000, "訊息內容不能超過 2000 個字元")),
    "type": F("str", enum=("text", "image", "file", "system", "adoption-update"), enum_msg="請選擇有效的訊息類型",
              default="text"),
    "sender": F("oid", required="發送者為必填項目"),
    "receiver": F("oid", required="接收者為必填項目"),
    "conversationId": F("str"),
    "relatedPet": F("oid"),
    "relatedAdoption": F("oid"),
    "status": F("str", enum=("sent", "delivered", "read", "deleted"), enum_msg="請選擇有效的訊息狀態", default="sent"),
    "readAt": F("date"),
    "deliveredAt": F("date"),
    "attachments": Arr({
        "type": F("str", enum=("image", "document", "video", "audio"), required=True),
        "url": F("str", required=True), "filename": F("str", required=True),
        "originalName": F("str"), "size": F("num"), "mimeType": F("str"),
    }),
    "replyTo": F("oid"),
    "systemData": {
        "eventType": F("str", enum=("adoption-submitted", "adoption-approved", "adoption-rejected",
                                    "adoption-completed", "pet-status-changed", "user-joined", "user-left")),
        "metadata": F("mixed"),
    },
    "priority": F("str", enum=("low", "normal", "high", "urgent"), default="normal"),
    "expiresAt": F("date"),
    "isEdited": F("bool", default=False),
    "editedAt": F("date"),
    "originalContent": F("str"),
}


def conversation_id(a, b) -> str:
    x, y = sorted([str(a), str(b)])
    return f"{x}_{y}"


def prepare_new_message(data: dict) -> dict:
    """new Message(data).save()：轉型、預設值、pre-save（conversationId、deliveredAt、系統訊息過期）、驗證。"""
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Message")
    now = datetime.now(timezone.utc)
    if not doc.get("conversationId"):
        doc["conversationId"] = conversation_id(doc["sender"], doc["receiver"])
    doc["deliveredAt"] = now
    if doc.get("type") == "system":
        doc["expiresAt"] = now + timedelta(days=30)
    doc.update(createdAt=now, updatedAt=now, __v=0)
    return doc


def message_json(doc: dict) -> dict:
    out = to_json(doc)
    out["isSystemMessage"] = doc.get("type") == "system"
    out["hasAttachments"] = bool(doc.get("attachments"))
    return out
