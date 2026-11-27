"""/api/messages：對應舊版 routes/messages.js。"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.forms import read_body
from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import MongooseError
from app.core.serialize import to_json
from app.core.uploads import save_files
from app.core.validation import O, S, validate
from app.db import get_db
from app.deps import current_user
from app.models.message import conversation_id, message_json, prepare_new_message
from app.models.notification import safe_notify
from app.responses import ApiError
from app.core.params import limit_param

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/messages", tags=["Messages"])

OID = r"^[0-9a-fA-F]{24}$"
OID_MSG = {"string.pattern.base": "無效的 ID 格式"}
CREATE_SCHEMA = O({
    "receiver": S(required=True, pattern=OID, msgs={**OID_MSG, "any.required": "收件人 ID 為必填欄位"}),
    "content": S(min=1, max=2000, msgs={"string.min": "訊息內容不能為空", "string.max": "訊息內容不能超過 2000 個字元"}),
    "type": S(valid=("text", "image", "file"), default="text"),
    "relatedPet": S(pattern=OID, msgs=OID_MSG),
    "relatedAdoption": S(pattern=OID, msgs=OID_MSG),
})
UPDATE_SCHEMA = O({
    "content": S(required=True, min=1, max=2000, msgs={
        "any.required": "訊息內容為必填欄位", "string.min": "訊息內容不能為空", "string.max": "訊息內容不能超過 2000 個字元"}),
})
FILE_EXTS = {".jpeg", ".jpg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".txt", ".mp3", ".wav", ".mp4",
             ".avi", ".mov"}
USER_BRIEF = "username firstName lastName avatar_url"
EDIT_LIMIT_SECONDS = 5 * 60


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _populate(docs) -> None:
    await populate(docs, "sender", "users", USER_BRIEF)
    await populate(docs, "receiver", "users", USER_BRIEF)
    await populate(docs, "relatedPet", "pets", "name species photos")


@router.get("/conversations", summary="對話列表")
async def conversations(user: dict = Depends(current_user)):
    db = get_db()
    # 舊資料補上 conversationId
    async for msg in db.messages.find({"conversationId": {"$exists": False}}).limit(100):
        await db.messages.update_one({"_id": msg["_id"]}, {"$set": {
            "conversationId": conversation_id(msg["sender"], msg["receiver"])}})
    uid = user["_id"]
    rows = await (await db.messages.aggregate([
        {"$match": {"$or": [{"sender": uid}, {"receiver": uid}], "status": {"$ne": "deleted"},
                    "conversationId": {"$exists": True, "$nin": [None, ""]}}},
        {"$sort": {"createdAt": -1}},
        {"$group": {"_id": "$conversationId", "lastMessage": {"$first": "$$ROOT"}, "unreadCount": {"$sum": {
            "$cond": [{"$and": [{"$eq": ["$receiver", uid]}, {"$eq": ["$status", "delivered"]}]}, 1, 0]}}}},
        {"$lookup": {"from": "users", "localField": "lastMessage.sender", "foreignField": "_id", "as": "senderInfo"}},
        {"$lookup": {"from": "users", "localField": "lastMessage.receiver", "foreignField": "_id",
                     "as": "receiverInfo"}},
        {"$sort": {"lastMessage.createdAt": -1}},
    ])).to_list(None)
    out = []
    for conv in rows:
        last = conv["lastMessage"]
        mine = same_id(last.get("sender"), uid)
        others = conv["receiverInfo"] if mine else conv["senderInfo"]
        if not others:
            continue  # 對方帳號已被刪除
        other = others[0]
        out.append({
            "conversationId": conv["_id"],
            "otherUser": {k: other.get(k) for k in ("_id", "username", "firstName", "lastName", "avatar_url")},
            "lastMessage": {"content": last.get("content"), "type": last.get("type"),
                            "createdAt": last.get("createdAt"), "isFromCurrentUser": mine},
            "unreadCount": conv["unreadCount"],
        })
    return {"success": True, "data": to_json(out)}


@router.get("/unread-count", summary="未讀訊息數")
async def unread_count(user: dict = Depends(current_user)):
    count = await get_db().messages.count_documents({"receiver": user["_id"], "status": "delivered"})
    return {"success": True, "data": {"unreadCount": count}}


async def _other_user(user_id: str, projection: dict) -> dict:
    uid = oid(user_id)
    other = await get_db().users.find_one({"_id": uid}, projection) if uid else None
    if not other:
        raise HTTPException(404, "找不到指定的用戶")
    return other


@router.get("/conversation/{user_id}", summary="與某人的對話")
async def conversation(user_id: str, request: Request, user: dict = Depends(current_user)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), limit_param(q.get("limit"), 50)
    other = await _other_user(user_id, {"username": 1, "firstName": 1, "lastName": 1, "avatar_url": 1})
    conv = conversation_id(user["_id"], other["_id"])
    query: dict = {"conversationId": conv, "status": {"$ne": "deleted"}}
    if q.get("before"):
        try:
            query["createdAt"] = {"$lt": datetime.fromisoformat(q["before"].replace("Z", "+00:00"))}
        except ValueError:
            raise HTTPException(400, "before 參數格式錯誤")
    docs = await get_db().messages.find(query).sort("createdAt", -1).skip(max(page - 1, 0) * limit) \
        .limit(limit).to_list(None)
    await _populate(docs)
    await populate(docs, "replyTo", "messages", "content sender createdAt")
    await get_db().messages.update_many({"conversationId": conv, "receiver": user["_id"], "status": "delivered"},
                                        {"$set": {"status": "read", "readAt": datetime.now(timezone.utc)}})
    return {"success": True, "data": {
        "messages": [message_json(d) for d in reversed(docs)], "otherUser": to_json(other),
        "pagination": {"page": page, "limit": limit, "hasMore": len(docs) == limit}}}


@router.post("", status_code=201, summary="發送訊息（文字或 multipart 檔案欄位 file）")
async def send_message(request: Request, user: dict = Depends(current_user)):
    body, files = await read_body(request, "file")
    data = validate(CREATE_SCHEMA, body)
    receiver = await get_db().users.find_one({"_id": oid(data["receiver"])}, {"_id": 1})
    if not receiver:
        raise HTTPException(404, "找不到指定的接收者")
    if same_id(receiver["_id"], user["_id"]) and user.get("role") not in ("shelter", "admin"):
        raise HTTPException(400, "不能發送訊息給自己")
    msg: dict = {"sender": user["_id"], "receiver": receiver["_id"], "type": data["type"]}
    if data["type"] == "text":
        if not data.get("content"):
            raise HTTPException(400, "文字訊息內容不能為空")
        msg["content"] = data["content"]
    else:
        if not files:
            raise HTTPException(400, "檔案訊息必須包含檔案")
        saved = (await save_files(files[:1], "messages", "file", allowed_exts=FILE_EXTS, allowed_mime=None,
                                  max_bytes=10 * 1024 * 1024, max_files=1, type_error="不支援的檔案類型"))[0]
        kind = "image" if (saved["mimetype"] or "").startswith("image/") else "file"
        msg["type"] = kind
        msg["content"] = data.get("content") or f"發送了一個{'圖片' if kind == 'image' else '檔案'}"
        # 舊版 attachments.type 只接受 image/document/video/audio，傳 file 會驗證失敗；改存 document
        msg["attachments"] = [{"type": "image" if kind == "image" else "document", "url": saved["path"],
                               "filename": saved["filename"], "originalName": saved["originalname"],
                               "size": saved["size"], "mimeType": saved["mimetype"]}]
    for key in ("relatedPet", "relatedAdoption"):
        if data.get(key):
            msg[key] = data[key]
    try:
        doc = prepare_new_message(msg)
    except MongooseError as e:
        raise ApiError(500, "發送訊息失敗", error=str(e), details=[m for _, m in e.errors])
    doc["_id"] = (await get_db().messages.insert_one(doc)).inserted_id
    await _populate(doc)
    await safe_notify({
        "recipient": receiver["_id"], "sender": user["_id"], "type": "message", "title": "新訊息",
        "content": f"{user.get('username') or user.get('firstName')} 傳送了一則訊息給您",
        "relatedMessage": doc["_id"], "link": f"/messages/{user['_id']}", "priority": "normal",
    })
    return {"success": True, "message": "訊息發送成功", "data": message_json(doc)}


async def _find_message(message_id: str) -> dict:
    mid = oid(message_id)
    doc = await get_db().messages.find_one({"_id": mid}) if mid else None
    if not doc:
        raise HTTPException(404, "找不到指定的訊息")
    return doc


@router.put("/{message_id}", summary="編輯訊息（5 分鐘內）")
async def edit_message(message_id: str, body: dict | None = None, user: dict = Depends(current_user)):
    data = validate(UPDATE_SCHEMA, body)
    msg = await _find_message(message_id)
    if not same_id(msg.get("sender"), user["_id"]):
        raise HTTPException(403, "沒有權限編輯此訊息")
    if msg.get("type") != "text":
        raise HTTPException(400, "只能編輯文字訊息")
    created = msg["createdAt"] if msg["createdAt"].tzinfo else msg["createdAt"].replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - created).total_seconds() > EDIT_LIMIT_SECONDS:
        raise HTTPException(403, "訊息發送超過 5 分鐘後無法編輯")
    now = datetime.now(timezone.utc)
    sets = {"content": data["content"].strip(), "isEdited": True, "editedAt": now, "updatedAt": now}
    if not msg.get("isEdited"):
        sets["originalContent"] = msg.get("content")
    await get_db().messages.update_one({"_id": msg["_id"]}, {"$set": sets})
    msg.update(sets)
    await populate(msg, "sender", "users", USER_BRIEF)
    await populate(msg, "receiver", "users", USER_BRIEF)
    return {"success": True, "message": "訊息編輯成功", "data": message_json(msg)}


@router.delete("/{message_id}", summary="刪除訊息（軟刪除）")
async def delete_message(message_id: str, user: dict = Depends(current_user)):
    msg = await _find_message(message_id)
    if not same_id(msg.get("sender"), user["_id"]):
        raise HTTPException(403, "沒有權限刪除此訊息")
    await get_db().messages.update_one({"_id": msg["_id"]}, {"$set": {
        "status": "deleted", "updatedAt": datetime.now(timezone.utc)}})
    return {"success": True, "message": "訊息已刪除"}


@router.post("/{message_id}/read", summary="標記訊息已讀")
async def read_message(message_id: str, user: dict = Depends(current_user)):
    msg = await _find_message(message_id)
    if not same_id(msg.get("receiver"), user["_id"]):
        raise HTTPException(403, "沒有權限標記此訊息")
    if msg.get("status") == "delivered":
        await get_db().messages.update_one({"_id": msg["_id"]}, {"$set": {
            "status": "read", "readAt": datetime.now(timezone.utc)}})
    return {"success": True, "message": "訊息已標記為已讀"}


@router.post("/conversation/{user_id}/read-all", summary="整段對話標記已讀")
async def read_all(user_id: str, user: dict = Depends(current_user)):
    other = await _other_user(user_id, {"_id": 1})
    result = await get_db().messages.update_many(
        {"conversationId": conversation_id(user["_id"], other["_id"]), "receiver": user["_id"],
         "status": "delivered"},
        {"$set": {"status": "read", "readAt": datetime.now(timezone.utc)}})
    return {"success": True, "message": "對話已標記為已讀", "data": {"modifiedCount": result.modified_count}}
