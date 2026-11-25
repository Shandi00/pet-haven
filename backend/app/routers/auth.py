"""/api/auth：對應舊版 routes/auth.js，回應格式（{ error } / { message, token, user }）維持不變。"""
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import get_settings
from app.core.ids import oid
from app.core.ratelimit import auth_limiter
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.core.validation import A, B, O, S, validate
from app.db import get_db
from app.models.user import new_user_doc, user_json
from app.responses import RawError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

PET_TYPES = ("dog", "cat", "rabbit", "bird", "hamster", "guinea-pig", "other")

REGISTER_SCHEMA = O({
    "username": S(required=True, alphanum=True, min=3, max=30, msgs={
        "string.alphanum": "使用者名稱只能包含英文字母和數字",
        "string.min": "使用者名稱至少 3 個字元",
        "string.max": "使用者名稱最多 30 個字元",
        "any.required": "使用者名稱為必填欄位"}),
    "email": S(required=True, email=True, msgs={
        "string.email": "Email 格式不正確", "any.required": "Email 為必填欄位"}),
    "password": S(required=True, min=6, pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)", msgs={
        "string.min": "密碼至少 6 個字元",
        "string.pattern.base": "密碼必須包含大小寫字母和數字",
        "any.required": "密碼為必填欄位"}),
    "firstName": S(required=True, min=1, max=50, msgs={"any.required": "名字為必填欄位"}),
    "lastName": S(required=True, min=1, max=50, msgs={"any.required": "姓氏為必填欄位"}),
    "phone": S(pattern=r"^09\d{8}$", msgs={"string.pattern.base": "手機號碼格式不正確 (例: 0912345678)"}),
    "address": O({"city": S(), "district": S(), "street": S(), "postalCode": S()}),
})

LOGIN_SCHEMA = O({
    "email": S(required=True, email=True, msgs={
        "string.email": "Email 格式不正確", "any.required": "Email 為必填欄位"}),
    "password": S(required=True, msgs={"any.required": "密碼為必填欄位"}),
})

_E = ("",)
UPDATE_SCHEMA = O({
    "firstName": S(min=1, max=50),
    "lastName": S(min=1, max=50),
    "bio": S(max=500, allow=_E),
    "avatar": S(uri=True),
    "phone": S(pattern=r"^09\d{8}$", allow=_E),
    "address": O({"city": S(allow=_E), "district": S(allow=_E), "street": S(allow=_E),
                  "postalCode": S(allow=_E)}),
    "preferences": O({
        "petTypes": A(S(valid=PET_TYPES)),
        "sizes": A(S(valid=("small", "medium", "large"))),
        "ages": A(S(valid=("puppy", "young", "adult", "senior"))),
        "notificationEmail": B(),
        "notificationSms": B(),
    }),
}, min_keys=1)


def _err(status: int, error: str, **extra) -> RawError:
    return RawError(status, {"error": error, **extra})


async def token_user(request: Request) -> dict:
    """舊版 auth.js 自己的 authenticateToken：錯誤格式是 { error }，token 無效回 403。"""
    header = request.headers.get("authorization") or ""
    parts = header.split(" ")
    token = parts[1] if len(parts) > 1 else None
    if not token:
        raise _err(401, "Authentication token required")
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        raise _err(403, "Invalid token")
    uid = oid(payload.get("userId"))
    user = await get_db().users.find_one({"_id": uid}, {"password": 0}) if uid else None
    if not user or not user.get("isActive", True):
        raise _err(401, "Invalid user account")
    return user


async def _touch_login(user_id) -> dict:
    now = datetime.now(timezone.utc)
    return await get_db().users.find_one_and_update(
        {"_id": user_id}, {"$set": {"lastLogin": now, "updatedAt": now}},
        return_document=ReturnDocument.AFTER)


@router.post("/register", status_code=201, summary="註冊")
async def register(request: Request, body: dict | None = None):
    auth_limiter.check(request)
    try:
        data = validate(REGISTER_SCHEMA, body)
    except RawError:
        auth_limiter.fail(request)
        raise
    email = data["email"].lower()
    users = get_db().users
    existing = await users.find_one({"$or": [{"email": email}, {"username": data["username"]}]})
    if existing:
        auth_limiter.fail(request)
        raise _err(400, "Email already registered" if existing.get("email") == email else "Username already taken")
    doc = new_user_doc(
        username=data["username"].strip(),
        email=email,
        password=hash_password(data["password"]),
        name=f"{data.get('firstName') or ''} {data.get('lastName') or ''}".strip(),
        firstName=data["firstName"].strip(),
        lastName=data["lastName"].strip(),
        contact_info={"phone": data["phone"]} if data.get("phone") else {},
        address=data.get("address"),
    )
    try:
        doc["_id"] = (await users.insert_one(doc)).inserted_id
    except DuplicateKeyError:
        auth_limiter.fail(request)
        raise _err(400, "Registration failed", details="Email or username already exists")
    return {"message": "Registration successful", "token": create_token(doc["_id"], doc["role"]),
            "user": user_json(doc)}


@router.post("/login", summary="登入")
async def login(request: Request, body: dict | None = None):
    auth_limiter.check(request)
    try:
        data = validate(LOGIN_SCHEMA, body)
    except RawError:
        auth_limiter.fail(request)
        raise
    user = await get_db().users.find_one({"email": data["email"].lower()})
    if not user or not user.get("isActive", True) or not verify_password(data["password"], user.get("password")):
        auth_limiter.fail(request)
        raise _err(401, "Invalid email or password")
    user = await _touch_login(user["_id"])
    return {"message": "Login successful", "token": create_token(user["_id"], user.get("role", "user")),
            "user": user_json(user)}


@router.get("/me", summary="取得目前使用者")
async def me(user: dict = Depends(token_user)):
    return {"user": user_json(user)}


@router.put("/profile", summary="更新個人資料")
async def update_profile(body: dict | None = None, user: dict = Depends(token_user)):
    data = validate(UPDATE_SCHEMA, body)
    allowed = ("firstName", "lastName", "phone", "address", "preferences")
    updates = {k: v for k, v in data.items() if k in allowed}
    updates["updatedAt"] = datetime.now(timezone.utc)
    updated = await get_db().users.find_one_and_update(
        {"_id": user["_id"]}, {"$set": updates}, projection={"password": 0},
        return_document=ReturnDocument.AFTER)
    if not updated:
        raise _err(404, "User not found")
    return {"message": "Profile updated successfully", "user": user_json(updated)}


@router.put("/change-password", summary="變更密碼")
async def change_password(body: dict | None = None, user: dict = Depends(token_user)):
    body = body or {}
    current, new = body.get("currentPassword"), body.get("newPassword")
    if not current or not new:
        raise _err(400, "Current password and new password required")
    if not isinstance(new, str) or len(new) < 6:
        raise _err(400, "New password must be at least 6 characters")
    full = await get_db().users.find_one({"_id": user["_id"]})
    if not verify_password(str(current), full.get("password")):
        raise _err(400, "Current password is incorrect")
    await get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": hash_password(new), "updatedAt": datetime.now(timezone.utc)}})
    return {"message": "Password changed successfully"}


@router.delete("/account", summary="停用帳號")
async def delete_account(body: dict | None = None, user: dict = Depends(token_user)):
    password = (body or {}).get("password")
    if not password:
        raise _err(400, "Password required to delete account")
    full = await get_db().users.find_one({"_id": user["_id"]})
    if not verify_password(str(password), full.get("password")):
        raise _err(400, "Incorrect password")
    await get_db().users.update_one(
        {"_id": user["_id"]}, {"$set": {"isActive": False, "updatedAt": datetime.now(timezone.utc)}})
    return {"message": "Account deleted successfully"}


@router.post("/verify-token", summary="驗證 token")
async def verify_token(body: dict | None = None):
    token = (body or {}).get("token")
    if not token:
        raise _err(400, "Token required")
    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        raise RawError(401, {"valid": False, "error": "Invalid token"})
    uid = oid(payload.get("userId"))
    user = await get_db().users.find_one({"_id": uid}, {"password": 0}) if uid else None
    if not user or not user.get("isActive", True):
        raise _err(401, "Invalid token")
    return {"valid": True, "user": user_json(user)}


# ==================== Google OAuth ====================

def _verify_google_id_token(token: str) -> dict:
    """同步呼叫 Google 驗證（需要網路），測試時 monkeypatch 這個函式。"""
    return google_id_token.verify_oauth2_token(token, google_requests.Request(), get_settings().google_client_id)


async def _google_user(payload: dict) -> dict:
    users = get_db().users
    email, google_id = payload.get("email"), payload.get("sub")
    avatar = payload.get("picture")
    user = await users.find_one({"$or": [{"email": email}, {"googleId": google_id}]})
    if user:
        updates = {"lastLogin": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc)}
        if not user.get("googleId"):
            updates["googleId"] = google_id
        if avatar and not user.get("avatar_url"):
            updates["avatar_url"] = avatar
        return await users.find_one_and_update({"_id": user["_id"]}, {"$set": updates},
                                               return_document=ReturnDocument.AFTER)
    local = email.split("@")[0]
    doc = new_user_doc(
        email=email, googleId=google_id,
        firstName=payload.get("given_name") or "", lastName=payload.get("family_name") or "",
        name=payload.get("name") or local,
        username=f"{local}_{int(time.time() * 1000)}",
        avatar_url=avatar, isEmailVerified=True, authProvider="google",
    )
    doc["_id"] = (await users.insert_one(doc)).inserted_id
    return doc


@router.post("/google/verify", summary="Google 登入（ID token）")
async def google_verify(request: Request, body: dict | None = None):
    auth_limiter.check(request)
    token = (body or {}).get("token")
    if not token:
        raise _err(400, "Google token required")
    if not get_settings().google_client_id:
        raise _err(503, "Google OAuth not configured", details="GOOGLE_CLIENT_ID not set in environment variables")
    try:
        payload = await run_in_threadpool(_verify_google_id_token, token)
    except Exception:
        logger.exception("Google token 驗證失敗")
        auth_limiter.fail(request)
        raise _err(500, "Google verification failed")
    if not payload.get("email_verified"):
        raise _err(400, "Email not verified", details="Please verify your email with Google")
    user = await _google_user(payload)
    return {"message": "Google login successful", "token": create_token(user["_id"], user.get("role", "user")),
            "user": user_json(user)}


@router.get("/google", summary="Google 登入（轉址）")
async def google_redirect(request: Request):
    s = get_settings()
    if not s.google_client_id:
        raise _err(503, "Google OAuth not configured")
    redirect_uri = s.google_callback_url or str(request.url_for("google_callback"))
    query = urlencode({
        "client_id": s.google_client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": "openid email profile", "access_type": "offline", "prompt": "consent",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


async def _exchange_code(code: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": s.google_client_id, "client_secret": s.google_client_secret,
            "redirect_uri": s.google_callback_url, "grant_type": "authorization_code",
        })
        return r.json()


@router.get("/google/callback", summary="Google 登入回呼", name="google_callback")
async def google_callback(code: str | None = None, error: str | None = None):
    front = get_settings().frontend_url
    if error:
        return RedirectResponse(f"{front}/login?error=google_auth_failed")
    if not code:
        return RedirectResponse(f"{front}/login?error=no_code")
    try:
        token_data = await _exchange_code(code)
        if not token_data.get("id_token"):
            raise ValueError("No id_token received")
        payload = await run_in_threadpool(_verify_google_id_token, token_data["id_token"])
        if not payload.get("email_verified"):
            return RedirectResponse(f"{front}/login?error=email_not_verified")
        user = await _google_user(payload)
        return RedirectResponse(f"{front}/auth/callback?token={create_token(user['_id'], user.get('role', 'user'))}")
    except Exception:
        logger.exception("Google callback 失敗")
        return RedirectResponse(f"{front}/login?error=callback_failed")
