import asyncio

from bson import ObjectId

from app.models import notification as notification_model


def seed(sync_db, recipient, n=2, **extra):
    from datetime import datetime, timezone
    ids = []
    for i in range(n):
        ids.append(sync_db.notifications.insert_one({
            "recipient": recipient["_id"], "type": "system", "title": f"t{i}", "content": "c",
            "isRead": False, "priority": "high", "createdAt": datetime.now(timezone.utc), **extra}).inserted_id)
    return ids


def test_list_count_read_delete(api, make_user, sync_db):
    user, h = make_user()
    other, oh = make_user()
    ids = seed(sync_db, user)
    r = api.get("/api/notifications", headers=h).json()
    assert r["success"] and r["data"]["pagination"]["total"] == 2 and r["data"]["notifications"][0]["isUrgent"]
    assert api.get("/api/notifications/unread-count", headers=h).json()["data"]["count"] == 2
    assert api.post(f"/api/notifications/{ids[0]}/read", headers=oh).status_code == 403
    r = api.post(f"/api/notifications/{ids[0]}/read", headers=h)
    assert r.json()["data"]["isRead"] is True
    assert api.get("/api/notifications", params={"unreadOnly": "true"}, headers=h).json()["data"]["pagination"]["total"] == 1
    assert api.post("/api/notifications/read-all", headers=h).json()["data"]["modifiedCount"] == 1
    assert api.delete("/api/notifications", headers=h).json()["data"]["deletedCount"] == 2
    assert api.post(f"/api/notifications/{ObjectId()}/read", headers=h).status_code == 404
    assert api.get("/api/notifications").json()["message"] == "未提供認證令牌，請先登入"


def test_create_notification_emits_socket_event(api, make_user, monkeypatch):
    user, _ = make_user()
    sent = []

    async def fake_emit(user_id, event, data):
        sent.append((str(user_id), event, data))

    monkeypatch.setattr(notification_model, "emit_to_user", fake_emit)

    async def run():
        return await notification_model.create_notification({
            "recipient": user["_id"], "type": "system", "title": "標題\x00", "content": "內容"})

    # 用 TestClient 的事件迴圈執行，資料庫 client 綁在那個迴圈上
    doc = api.portal.call(run)
    assert doc["title"] == "標題"
    assert sent and sent[0][0] == str(user["_id"]) and sent[0][1] == "newNotification"
