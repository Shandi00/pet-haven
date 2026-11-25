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
