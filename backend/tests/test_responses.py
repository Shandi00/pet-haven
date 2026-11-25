from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.responses import register_error_handlers

demo_app = FastAPI()
register_error_handlers(demo_app)


@demo_app.get("/items/{n}")
def get_item(n: int):
    return {"n": n}


@demo_app.get("/forbidden")
def forbidden():
    raise HTTPException(403, "只能處理自己的資源")


@demo_app.get("/boom")
def boom():
    raise RuntimeError("secret stack info")


def test_unknown_route_returns_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json() == {"success": False, "message": "找不到請求的資源"}


def test_validation_error_returns_400():
    r = TestClient(demo_app).get("/items/abc")
    assert r.status_code == 400
    assert r.json() == {"success": False, "message": "輸入資料格式錯誤"}


def test_http_exception_keeps_message():
    r = TestClient(demo_app).get("/forbidden")
    assert r.status_code == 403
    assert r.json() == {"success": False, "message": "只能處理自己的資源"}


def test_unhandled_error_returns_500():
    r = TestClient(demo_app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json() == {"success": False, "message": "伺服器發生錯誤"}
    assert "secret" not in r.text
