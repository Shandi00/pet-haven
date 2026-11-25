"""Socket.IO：事件名稱與 payload 沿用舊版 server.js。"""
import logging

import socketio

from app.config import get_settings
from app.core.serialize import to_json

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=get_settings().cors_origin_list(),
)


@sio.event
async def join(sid, user_id):
    await sio.enter_room(sid, str(user_id))


@sio.event
async def sendMessage(sid, data):  # noqa: N802 - 事件名稱沿用前端
    data = data or {}
    if data.get("receiverId"):
        await sio.emit("newMessage", data.get("message"), room=str(data["receiverId"]), skip_sid=sid)


@sio.event
async def messageRead(sid, data):  # noqa: N802
    data = data or {}
    if data.get("senderId"):
        await sio.emit("messageReadConfirm", {"messageId": data.get("messageId")},
                       room=str(data["senderId"]), skip_sid=sid)


@sio.event
async def typing(sid, data):
    data = data or {}
    if data.get("receiverId"):
        await sio.emit("userTyping", {"isTyping": data.get("isTyping"), "userId": None},
                       room=str(data["receiverId"]), skip_sid=sid)


async def emit_to_user(user_id, event: str, data) -> None:
    try:
        await sio.emit(event, to_json(data), room=str(user_id))
    except Exception:  # 推送失敗不影響主要流程
        logger.exception("Socket.IO 推送失敗：%s", event)
