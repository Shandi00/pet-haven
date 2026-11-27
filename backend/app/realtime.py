"""Socket.IO：事件名稱與 payload 沿用舊版 server.js。

舊版不驗證身分，任何人送 join 加上別人的 userId 就能收到對方的通知與私訊。
這裡改成連線時必須帶有效 JWT（前端已在 handshake 的 auth.token 送出），只能加入自己的房間；
不提供用戶端轉發私訊（2026-11-27 移除 sendMessage），私訊只由伺服器存檔後推送。
"""
import logging

import jwt
import socketio

from app.config import get_settings
from app.core.ids import oid
from app.core.security import decode_token
from app.core.serialize import to_json
from app.db import get_db

logger = logging.getLogger(__name__)
audit = logging.getLogger("audit")

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=get_settings().cors_origin_list(),
)


async def _user_id(sid) -> str | None:
    session = await sio.get_session(sid)
    return (session or {}).get("user_id")


@sio.event
async def connect(sid, environ, auth=None):
    token = (auth or {}).get("token") if isinstance(auth, dict) else None
    if not token:
        return False
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        audit.info("socket_rejected reason=invalid_token")
        return False
    uid = oid(payload.get("userId"))
    user = await get_db().users.find_one({"_id": uid}, {"isActive": 1}) if uid else None
    if not user or not user.get("isActive", True):
        audit.info("socket_rejected reason=inactive_or_missing_user")
        return False
    await sio.save_session(sid, {"user_id": str(user["_id"])})
    await sio.enter_room(sid, str(user["_id"]))
    return True


@sio.event
async def join(sid, user_id):
    me = await _user_id(sid)
    if me and str(user_id) == me:
        await sio.enter_room(sid, me)
    elif me:
        audit.warning("socket_join_denied user=%s", me)


# 不提供用戶端轉發訊息的 sendMessage 事件：用戶端送來的訊息物件可以偽造寄件人名稱與內容，
# 私訊一律由伺服器在存進資料庫後推送 newMessage（messages.py）


@sio.event
async def messageRead(sid, data):  # noqa: N802
    data = data if isinstance(data, dict) else {}
    if await _user_id(sid) and data.get("senderId"):
        await sio.emit("messageReadConfirm", {"messageId": data.get("messageId")},
                       room=str(data["senderId"]), skip_sid=sid)


@sio.event
async def typing(sid, data):
    me = await _user_id(sid)
    data = data if isinstance(data, dict) else {}
    if me and data.get("receiverId"):
        await sio.emit("userTyping", {"isTyping": data.get("isTyping"), "userId": me},
                       room=str(data["receiverId"]), skip_sid=sid)


async def emit_to_user(user_id, event: str, data) -> None:
    try:
        await sio.emit(event, to_json(data), room=str(user_id))
    except Exception:  # 推送失敗不影響主要流程
        logger.exception("Socket.IO 推送失敗：%s", event)
