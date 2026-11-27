from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

TOKEN_DAYS = 7
BCRYPT_ROUNDS = 12


def _bcrypt_bytes(password: str) -> bytes:
    # bcrypt 只用前 72 bytes；bcrypt 5 起超過會丟 ValueError（註冊與改密碼回 500），
    # 這裡照舊版 bcryptjs 的行為截斷，舊帳號的長密碼也能照常登入
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_bytes(password), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed: str | None) -> bool:
    # Google 登入的帳號沒有密碼
    if not hashed or not password:
        return False
    try:
        return bcrypt.checkpw(_bcrypt_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id, role: str) -> str:
    payload = {
        "userId": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    """失敗時丟 jwt.ExpiredSignatureError 或 jwt.InvalidTokenError。"""
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def token_revoked(payload: dict, user: dict) -> bool:
    """改密碼之前發出的 token 一律失效，帳號被盜時改密碼就能把對方踢出去。
    iat 只到秒，所以和改密碼時間的整數秒比較，改密碼當下發的新 token 仍可用。"""
    changed = user.get("passwordChangedAt")
    if not isinstance(changed, datetime):
        return False
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=timezone.utc)
    iat = payload.get("iat")
    return not isinstance(iat, (int, float)) or iat < int(changed.timestamp())
