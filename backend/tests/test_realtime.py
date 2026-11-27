"""Socket.IO 事件處理：連線必須帶有效 JWT，只能加入自己的房間，不能冒名轉送訊息。"""
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from app import realtime
from app.core.security import create_token


class FakeSio:
    def __init__(self):
        self.sessions, self.rooms, self.emitted = {}, [], []

    async def save_session(self, sid, data):
        self.sessions[sid] = data

    async def get_session(self, sid):
        return self.sessions.get(sid, {})

    async def enter_room(self, sid, room):
        self.rooms.append((sid, room))

    async def emit(self, event, data=None, room=None, skip_sid=None):
        self.emitted.append((event, data, room))


@pytest.fixture
def fake(monkeypatch):
    f = FakeSio()
    for name in ("save_session", "get_session", "enter_room", "emit"):
        monkeypatch.setattr(realtime.sio, name, getattr(f, name))
    return f


def run(api, fn, *args):
    return api.portal.call(fn, *args)


def test_connect_requires_valid_token(api, make_user, fake):
    user, h = make_user()
    token = h["Authorization"].split()[1]
    assert run(api, realtime.connect, "s1", {}, None) is False
    assert run(api, realtime.connect, "s1", {}, {"token": "bad"}) is False
    assert run(api, realtime.connect, "s1", {}, {"token": create_token(ObjectId(), "user")}) is False
    inactive, ih = make_user(isActive=False)
    assert run(api, realtime.connect, "s1", {}, {"token": ih["Authorization"].split()[1]}) is False
    # 改密碼之前發出的 token 不能連線
    _, rh = make_user(passwordChangedAt=datetime.now(timezone.utc) + timedelta(minutes=1))
    assert run(api, realtime.connect, "s1", {}, {"token": rh["Authorization"].split()[1]}) is False
    assert run(api, realtime.connect, "s1", {}, {"token": token}) is True
    assert fake.sessions["s1"]["user_id"] == str(user["_id"])
    # 連線成功就自動加入自己的房間
    assert ("s1", str(user["_id"])) in fake.rooms


def test_join_only_own_room(api, make_user, fake):
    user, h = make_user()
    run(api, realtime.connect, "s1", {}, {"token": h["Authorization"].split()[1]})
    fake.rooms.clear()
    run(api, realtime.join, "s1", str(ObjectId()))
    assert fake.rooms == []
    run(api, realtime.join, "s1", str(user["_id"]))
    assert fake.rooms == [("s1", str(user["_id"]))]


def test_client_cannot_relay_messages(api):
    # 用戶端送來的訊息物件可以偽造寄件人與內容；私訊只由伺服器在存進資料庫後推送（messages.py）
    assert not hasattr(realtime, "sendMessage")


def test_typing_uses_authenticated_user_id(api, make_user, fake):
    user, h = make_user()
    run(api, realtime.connect, "s1", {}, {"token": h["Authorization"].split()[1]})
    run(api, realtime.typing, "s1", {"receiverId": "r1", "isTyping": True})
    assert ("userTyping", {"isTyping": True, "userId": str(user["_id"])}, "r1") in fake.emitted


def test_events_ignored_without_session(api, fake):
    run(api, realtime.typing, "nosession", {"receiverId": "r", "isTyping": True})
    assert fake.emitted == []
