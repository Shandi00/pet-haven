import os

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    # 不用 with，lifespan 不會執行，測試不連資料庫
    yield TestClient(app)
    app.dependency_overrides.clear()
