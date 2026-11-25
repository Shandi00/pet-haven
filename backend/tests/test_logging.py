"""log：request id、存取紀錄、稽核紀錄，且不能出現 Email 或密碼。"""
import logging

from tests.conftest import TEST_PASSWORD


def records(caplog, name):
    return [r for r in caplog.records if r.name == name]


def test_request_id_header_and_access_log(api, caplog):
    caplog.set_level(logging.INFO)
    r = api.get("/api/health?code=secret-oauth-code", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    access = records(caplog, "access")
    assert access and "GET /api/health 200" in access[-1].getMessage()
    assert access[-1].request_id == "abc-123"
    assert "secret-oauth-code" not in caplog.text  # 不記錄 query string
    generated = api.get("/api/health").headers["x-request-id"]
    assert generated and generated != "abc-123"
    # 外部傳入的 request id 只接受安全字元
    assert api.get("/api/health", headers={"X-Request-ID": "bad\nid"}).headers["x-request-id"] != "bad\nid"


def test_login_audit_without_email_or_password(api, make_user, caplog):
    caplog.set_level(logging.INFO)
    user, _ = make_user()
    api.post("/api/auth/login", json={"email": user["email"], "password": "wrong-pass"})
    api.post("/api/auth/login", json={"email": user["email"], "password": TEST_PASSWORD})
    audit = " | ".join(r.getMessage() for r in records(caplog, "audit"))
    assert "login_failed" in audit and f"login_success user={user['_id']}" in audit
    assert user["email"] not in caplog.text and TEST_PASSWORD not in caplog.text and "wrong-pass" not in caplog.text


def test_admin_and_adoption_actions_are_audited(api, make_user, caplog):
    caplog.set_level(logging.INFO)
    target, _ = make_user()
    admin, ah = make_user("admin")
    api.put(f"/api/users/admin/{target['_id']}/role", json={"role": "shelter"}, headers=ah)
    api.put(f"/api/users/admin/{target['_id']}/active", json={"isActive": False}, headers=ah)
    audit = " | ".join(r.getMessage() for r in records(caplog, "audit"))
    assert f"user_role_changed by={admin['_id']} target={target['_id']} role=shelter" in audit
    assert f"user_active_changed by={admin['_id']} target={target['_id']} active=False" in audit


def test_access_denied_is_logged(api, make_user, caplog):
    caplog.set_level(logging.INFO)
    _, h = make_user()
    api.get("/api/users/admin/all", headers=h)
    api.get("/api/notifications")
    denied = [r.getMessage() for r in records(caplog, "audit") if "access_denied" in r.getMessage()]
    assert any("status=403 GET /api/users/admin/all" in m for m in denied)
    assert any("status=401 GET /api/notifications" in m for m in denied)
