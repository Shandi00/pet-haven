"""登入驗證與角色檢查，行為對應舊版 middleware/auth.js。"""
import jwt
from fastapi import Depends, HTTPException, Request

from app.core.ids import oid
from app.core.security import decode_token
from app.db import get_db


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer"):
        parts = header.split(" ")
        return parts[1] if len(parts) > 1 and parts[1] else None
    return None


async def _load_user(user_id) -> dict | None:
    uid = oid(user_id)
    if uid is None:
        return None
    return await get_db().users.find_one({"_id": uid}, {"password": 0})


async def current_user(request: Request) -> dict:
    token = _bearer(request)
    if not token:
        raise HTTPException(401, "未提供認證令牌，請先登入")
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "認證令牌已過期，請重新登入")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "無效的認證令牌")
    user = await _load_user(payload.get("userId") or payload.get("id"))
    if not user:
        raise HTTPException(401, "認證失敗,用戶不存在")
    if not user.get("isActive", True):
        raise HTTPException(401, "帳號已被停用，請聯繫管理員")
    return user


async def optional_user(request: Request) -> dict | None:
    token = _bearer(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        return None
    user = await _load_user(payload.get("userId") or payload.get("id"))
    if user and user.get("isActive", True):
        return user
    return None


def require_roles(*roles: str):
    async def checker(user: dict = Depends(current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(403, "沒有權限執行此操作")
        return user

    return checker
