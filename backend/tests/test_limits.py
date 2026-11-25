"""請求大小上限：避免超大上傳把記憶體吃光。"""
import asyncio
import io

import pytest

from app.config import get_settings
from app.core import uploads


@pytest.fixture
def small_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "max_request_bytes", 1000)


def test_rejects_large_content_length(api, make_user, small_limit):
    _, h = make_user()
    r = api.post("/api/pets", files=[("photos", ("a.png", io.BytesIO(b"x" * 5000), "image/png"))], headers=h)
    assert r.status_code == 413 and r.json() == {"success": False, "message": "上傳內容過大"}


def test_rejects_large_streamed_body(api, make_user, small_limit):
    _, h = make_user()

    def chunks():
        for _ in range(10):
            yield b"x" * 500

    r = api.post("/api/auth/login", content=chunks(), headers={**h, "Content-Type": "application/json"})
    assert r.status_code == 413


def test_small_requests_still_work(api, small_limit):
    assert api.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}).status_code == 401


class FakeUpload:
    filename, content_type = "a.png", "image/png"

    def __init__(self, size):
        self.size, self.requested = size, None

    async def read(self, n=-1):
        self.requested = n
        return b"x" * (self.size if n < 0 else min(n, self.size))

    async def close(self):
        pass


def test_save_files_reads_at_most_limit_plus_one(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_path", str(tmp_path))
    f = FakeUpload(10_000)
    with pytest.raises(Exception) as e:
        asyncio.run(uploads.save_images([f], "pets", "pet", max_bytes=100))
    assert f.requested == 101 and "檔案大小超過限制" in str(e.value.detail)
