import asyncio

from pymongo.errors import ServerSelectionTimeoutError

from app import db
from app.db import is_db_ready
from app.main import app


class _FakeAdmin:
    async def command(self, name):
        raise ServerSelectionTimeoutError("unreachable")


class FakeClientRaising:
    admin = _FakeAdmin()


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": {"status": "ok"}}


def test_ready_when_db_up(client):
    app.dependency_overrides[is_db_ready] = lambda: True
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": {"status": "ready"}}


def test_ready_when_db_down(client):
    app.dependency_overrides[is_db_ready] = lambda: False
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert r.json() == {"success": False, "message": "資料庫無法連線"}


def test_is_db_ready_false_on_error(monkeypatch):
    monkeypatch.setattr(db, "_client", FakeClientRaising())
    assert asyncio.run(db.is_db_ready()) is False


def test_is_db_ready_false_when_not_connected(monkeypatch):
    monkeypatch.setattr(db, "_client", None)
    assert asyncio.run(db.is_db_ready()) is False


def test_swagger_served(client):
    assert client.get("/api-docs").status_code == 200
    assert client.get("/api-docs.json").json()["info"]["title"] == "Pet Haven API"


def test_cors_preflight_allows_frontend(client):
    r = client.options("/api/health", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
