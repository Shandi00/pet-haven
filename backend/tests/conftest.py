import os
from datetime import datetime, timezone

from dotenv import dotenv_values

# 測試資料庫：有 TEST_MONGODB_URI（CI）就用它，否則用 backend/.env 的連線字串，
# 但資料庫名稱固定為 pet_haven_test，不會碰到開發資料
_TEST_DB = "pet_haven_test"
_test_uri = (os.environ.get("TEST_MONGODB_URI")
             or dotenv_values(".env").get("MONGODB_URI")
             or "mongodb://localhost:27017")
os.environ["MONGODB_URI"] = _test_uri
os.environ["MONGODB_DB"] = _TEST_DB
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ.setdefault("JWT_SECRET", "test-secret")

import bcrypt  # noqa: E402
import pytest  # noqa: E402
from bson import ObjectId  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.core.security import create_token  # noqa: E402
from app.main import app  # noqa: E402

assert _TEST_DB.endswith("_test"), "測試只能使用 _test 結尾的資料庫"


@pytest.fixture
def client():
    # 不用 with，lifespan 不會執行，測試不連資料庫
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def sync_db():
    mc = MongoClient(_test_uri, serverSelectionTimeoutMS=10000)
    db = mc[_TEST_DB]
    yield db
    # Atlas 帳號沒有 dropDatabase 權限，只清空資料
    for name in db.list_collection_names():
        db[name].delete_many({})
    mc.close()


@pytest.fixture(scope="session")
def _api_session(sync_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def api(_api_session, sync_db):
    """連真資料庫的 client；每個測試開始前清空所有 collection。"""
    for name in sync_db.list_collection_names():
        sync_db[name].delete_many({})
    yield _api_session
    app.dependency_overrides.clear()


TEST_PASSWORD = "Passw0rd!"
_HASH = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt(4)).decode()


@pytest.fixture
def make_user(sync_db):
    """建立使用者並回傳 (user, headers)。"""
    counter = {"n": 0}

    def _make(role: str = "user", **fields):
        counter["n"] += 1
        now = datetime.now(timezone.utc)
        n = f"{role}{counter['n']}{ObjectId()}"[-12:]
        doc = {
            "email": f"{n}@example.com",
            "username": n,
            "name": f"測試{role}",
            "password": _HASH,
            "role": role,
            "authProvider": "local",
            "status": "active",
            "isActive": True,
            "isEmailVerified": False,
            "favorites": [],
            "collections": [],
            "adoptionHistory": [],
            "browsingHistory": [],
            "createdAt": now,
            "updatedAt": now,
        }
        doc.update(fields)
        doc["_id"] = sync_db.users.insert_one(doc).inserted_id
        token = create_token(doc["_id"], role)
        return doc, {"Authorization": f"Bearer {token}"}

    return _make
