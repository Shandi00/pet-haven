from datetime import datetime, timedelta, timezone

import httpx
import jwt

from app.config import get_settings
from app.core.security import token_revoked
from app.routers import auth as auth_router
from tests.conftest import TEST_PASSWORD

REG = {"username": "alice01", "email": "Alice@Example.com", "password": "Abc123",
       "firstName": "小", "lastName": "愛", "phone": "0912345678"}


def test_register_login_me_flow(api):
    r = api.post("/api/auth/register", json=REG)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["message"] == "Registration successful" and body["token"]
    u = body["user"]
    assert u["email"] == "alice@example.com" and u["role"] == "user" and "password" not in u
    assert u["_id"] == u["id"] and u["contact_info"]["phone"] == "0912345678"

    r = api.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "Abc123"})
    assert r.status_code == 200 and r.json()["message"] == "Login successful"
    token = r.json()["token"]
    r = api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "alice01"


def test_register_duplicate_and_validation(api):
    assert api.post("/api/auth/register", json=REG).status_code == 201
    r = api.post("/api/auth/register", json=REG)
    assert r.status_code == 400 and r.json() == {"error": "Email already registered"}
    r = api.post("/api/auth/register", json={**REG, "email": "x@example.com", "password": "abc"})
    assert r.status_code == 400
    details = {d["field"]: d["message"] for d in r.json()["error"]["details"]}
    assert details["password"] in ("密碼至少 6 個字元", "密碼必須包含大小寫字母和數字")


def test_login_wrong_password_and_inactive(api, make_user):
    user, _ = make_user()
    r = api.post("/api/auth/login", json={"email": user["email"], "password": "wrong"})
    assert r.status_code == 401 and r.json() == {"error": "Invalid email or password"}
    inactive, _ = make_user(isActive=False)
    r = api.post("/api/auth/login", json={"email": inactive["email"], "password": TEST_PASSWORD})
    assert r.status_code == 401


def test_me_token_errors_match_legacy(api):
    assert api.get("/api/auth/me").json() == {"error": "Authentication token required"}
    r = api.get("/api/auth/me", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 403 and r.json() == {"error": "Invalid token"}


def test_profile_change_password_delete(api, make_user):
    user, h = make_user()
    r = api.put("/api/auth/profile", json={"firstName": "新", "role": "admin"}, headers=h)
    assert r.status_code == 200 and r.json()["user"]["firstName"] == "新"
    assert r.json()["user"]["role"] == "user"  # role 不在允許清單
    assert api.put("/api/auth/profile", json={}, headers=h).status_code == 400

    r = api.put("/api/auth/change-password", json={"currentPassword": "nope", "newPassword": "Newpass1"}, headers=h)
    assert r.status_code == 400 and r.json()["error"] == "Current password is incorrect"
    r = api.put("/api/auth/change-password", json={"currentPassword": TEST_PASSWORD, "newPassword": "Newpass1"},
                headers=h)
    assert r.status_code == 200
    assert api.post("/api/auth/login", json={"email": user["email"], "password": "Newpass1"}).status_code == 200
    h = {"Authorization": f"Bearer {r.json()['token']}"}  # 舊 token 已失效，改用改密碼回傳的新 token

    assert api.request("DELETE", "/api/auth/account", json={"password": "Newpass1"}, headers=h).status_code == 200
    assert api.get("/api/auth/me", headers=h).status_code == 401


def test_verify_token(api, make_user):
    _, h = make_user()
    token = h["Authorization"].split()[1]
    assert api.post("/api/auth/verify-token", json={"token": token}).json()["valid"] is True
    r = api.post("/api/auth/verify-token", json={"token": "x"})
    assert r.status_code == 401 and r.json() == {"valid": False, "error": "Invalid token"}


def test_google_verify_creates_then_reuses_user(api, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "google_client_id", "cid")
    monkeypatch.setattr(auth_router, "_verify_google_id_token", lambda t: {
        "sub": "g-1", "email": "g@example.com", "email_verified": True, "name": "G", "picture": "http://p"})
    r1 = api.post("/api/auth/google/verify", json={"token": "t"})
    r2 = api.post("/api/auth/google/verify", json={"token": "t"})
    assert r1.status_code == 200 and r1.json()["user"]["authProvider"] == "google"
    assert r1.json()["user"]["_id"] == r2.json()["user"]["_id"]


def test_google_not_configured(api, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert api.post("/api/auth/google/verify", json={"token": "t"}).status_code == 503
    assert api.get("/api/auth/google", follow_redirects=False).status_code == 503


def test_captcha_required_when_configured(api, make_user, monkeypatch):
    # 設定 Turnstile 密鑰後，登入與註冊都要附上驗證碼 token；沒設定時（開發、CI）不檢查
    from pydantic import SecretStr
    from app.config import get_settings
    from app.core import captcha
    user, _ = make_user()
    login = {"email": user["email"], "password": TEST_PASSWORD}
    assert api.post("/api/auth/login", json=login).status_code == 200
    monkeypatch.setattr(get_settings(), "turnstile_secret_key", SecretStr("secret"))
    seen = []

    async def fake_siteverify(secret, token, ip):
        seen.append((secret, token))
        return {"success": token == "good"}

    monkeypatch.setattr(captcha, "_siteverify", fake_siteverify)
    r = api.post("/api/auth/login", json=login)
    assert r.status_code == 400 and r.json()["error"] == "請先完成人機驗證"
    assert api.post("/api/auth/login", json={**login, "captchaToken": "bad"}).status_code == 400
    assert api.post("/api/auth/login", json={**login, "captchaToken": "good"}).status_code == 200
    assert seen[-1] == ("secret", "good")
    assert api.post("/api/auth/register", json=REG).status_code == 400
    assert api.post("/api/auth/register", json={**REG, "captchaToken": "good"}).status_code == 201


def test_captcha_service_unreachable_does_not_block_login(api, make_user, monkeypatch):
    from pydantic import SecretStr
    from app.config import get_settings
    from app.core import captcha
    user, _ = make_user()
    monkeypatch.setattr(get_settings(), "turnstile_secret_key", SecretStr("secret"))

    async def down(secret, token, ip):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(captcha, "_siteverify", down)
    r = api.post("/api/auth/login", json={"email": user["email"], "password": TEST_PASSWORD, "captchaToken": "t"})
    assert r.status_code == 200


def test_successful_signups_are_capped_per_ip(api, monkeypatch):
    from app.core.ratelimit import UserRateLimiter
    monkeypatch.setattr(auth_router, "register_limiter", UserRateLimiter(2, 3600, enabled=True))
    for i in range(2):
        r = api.post("/api/auth/register", json={**REG, "username": f"bulk{i}x", "email": f"bulk{i}@example.com"})
        assert r.status_code == 201, r.text
    r = api.post("/api/auth/register", json={**REG, "username": "bulk9x", "email": "bulk9@example.com"})
    assert r.status_code == 429


def test_google_does_not_take_over_unverified_password_account(api, monkeypatch, sync_db):
    # 有人先用別人的 Email 加自己的密碼註冊（沒驗證 Email），本人之後用 Google 登入不能被綁進這個帳號
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "google_client_id", "cid")
    assert api.post("/api/auth/register", json=REG).status_code == 201
    monkeypatch.setattr(auth_router, "_verify_google_id_token", lambda t: {
        "sub": "g-9", "email": "alice@example.com", "email_verified": True, "name": "A"})
    r = api.post("/api/auth/google/verify", json={"token": "t"})
    assert r.status_code == 409 and r.json()["error"] == "這個 Email 已用密碼註冊，請用密碼登入"
    assert not sync_db.users.find_one({"email": "alice@example.com"}).get("googleId")
    # 已驗證 Email 的帳號照舊可以綁定
    sync_db.users.update_one({"email": "alice@example.com"}, {"$set": {"isEmailVerified": True}})
    assert api.post("/api/auth/google/verify", json={"token": "t"}).status_code == 200


def _token_issued(user, seconds_ago):
    now = datetime.now(timezone.utc)
    payload = {"userId": str(user["_id"]), "role": user["role"],
               "iat": now - timedelta(seconds=seconds_ago), "exp": now + timedelta(days=1)}
    return {"Authorization": f"Bearer {jwt.encode(payload, get_settings().jwt_secret, algorithm='HS256')}"}


def test_change_password_revokes_older_tokens(api, make_user):
    # 帳號被盜時改密碼，對方手上較早發出的 token 要立刻失效；改密碼回傳的新 token 可以繼續用
    user, _ = make_user()
    old = _token_issued(user, 60)
    assert api.get("/api/auth/me", headers=old).status_code == 200
    r = api.put("/api/auth/change-password", json={"currentPassword": TEST_PASSWORD, "newPassword": "Newpass1"},
                headers=old)
    assert r.status_code == 200
    new = {"Authorization": f"Bearer {r.json()['token']}"}

    assert api.get("/api/auth/me", headers=old).status_code == 401  # 舊版格式的路由（token_user）
    r = api.get("/api/notifications", headers=old)  # current_user
    assert r.status_code == 401 and "密碼已變更" in r.text
    assert api.post("/api/auth/verify-token", json={"token": old["Authorization"].split()[1]}).status_code == 401

    me = api.get("/api/auth/me", headers=new)
    assert me.status_code == 200 and "passwordChangedAt" not in me.json()["user"]
    assert api.get("/api/notifications", headers=new).status_code == 200


def test_token_revoked_compares_whole_seconds():
    changed = datetime(2026, 11, 27, 12, 0, 0, 700000, tzinfo=timezone.utc)
    second = int(changed.timestamp())
    assert token_revoked({"iat": second - 1}, {"passwordChangedAt": changed}) is True
    assert token_revoked({"iat": second}, {"passwordChangedAt": changed}) is False  # 改密碼當下發的新 token
    assert token_revoked({}, {"passwordChangedAt": changed}) is True
    assert token_revoked({"iat": second - 1}, {}) is False  # 從沒改過密碼
