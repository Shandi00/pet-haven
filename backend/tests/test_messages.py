import io
from datetime import datetime, timedelta, timezone

from bson import ObjectId


def test_send_list_conversation_edit_delete(api, make_user, sync_db):
    alice, ah = make_user()
    bob, bh = make_user()
    r = api.post("/api/messages", json={"receiver": str(bob["_id"]), "content": "你好"}, headers=ah)
    assert r.status_code == 201, r.text
    msg = r.json()["data"]
    assert msg["sender"]["username"] == alice["username"] and msg["conversationId"]
    assert sync_db.notifications.find_one({"recipient": bob["_id"], "type": "message"})

    convs = api.get("/api/messages/conversations", headers=bh).json()["data"]
    assert convs[0]["otherUser"]["_id"] == str(alice["_id"]) and convs[0]["lastMessage"]["content"] == "你好"

    conv = api.get(f"/api/messages/conversation/{alice['_id']}", headers=bh).json()["data"]
    assert [m["content"] for m in conv["messages"]] == ["你好"]

    assert api.put(f"/api/messages/{msg['_id']}", json={"content": "改"}, headers=bh).status_code == 403
    r = api.put(f"/api/messages/{msg['_id']}", json={"content": "您好"}, headers=ah).json()["data"]
    assert r["content"] == "您好" and r["isEdited"] is True and r["originalContent"] == "你好"
    sync_db.messages.update_one({"_id": ObjectId(msg["_id"])},
                                {"$set": {"createdAt": datetime.now(timezone.utc) - timedelta(minutes=10)}})
    assert api.put(f"/api/messages/{msg['_id']}", json={"content": "再改"}, headers=ah).status_code == 403

    assert api.delete(f"/api/messages/{msg['_id']}", headers=bh).status_code == 403
    assert api.delete(f"/api/messages/{msg['_id']}", headers=ah).json()["message"] == "訊息已刪除"
    assert api.get(f"/api/messages/conversation/{alice['_id']}", headers=bh).json()["data"]["messages"] == []


def test_send_validation_self_and_file(api, make_user):
    alice, ah = make_user()
    bob, _ = make_user()
    assert api.post("/api/messages", json={"receiver": "bad"}, headers=ah).status_code == 400
    assert api.post("/api/messages", json={"receiver": str(ObjectId())}, headers=ah).status_code == 404
    assert api.post("/api/messages", json={"receiver": str(alice["_id"]), "content": "x"}, headers=ah).json()[
        "message"] == "不能發送訊息給自己"
    assert api.post("/api/messages", json={"receiver": str(bob["_id"])}, headers=ah).json()["message"] == \
        "文字訊息內容不能為空"
    r = api.post("/api/messages", data={"receiver": str(bob["_id"]), "type": "file"},
                 files={"file": ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf")}, headers=ah)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["type"] == "file" and r.json()["data"]["attachments"][0]["url"].startswith(
        "/uploads/messages/file-")
    r = api.post("/api/messages", data={"receiver": str(bob["_id"]), "type": "file"},
                 files={"file": ("a.exe", io.BytesIO(b"MZ"), "application/octet-stream")}, headers=ah)
    assert r.status_code == 400


def test_unread_and_read_all(api, make_user, sync_db):
    alice, ah = make_user()
    bob, bh = make_user()
    api.post("/api/messages", json={"receiver": str(bob["_id"]), "content": "1"}, headers=ah)
    # 新訊息狀態是 sent，舊版只把 delivered 算未讀
    sync_db.messages.update_many({}, {"$set": {"status": "delivered"}})
    assert api.get("/api/messages/unread-count", headers=bh).json()["data"]["unreadCount"] == 1
    r = api.post(f"/api/messages/conversation/{alice['_id']}/read-all", headers=bh).json()
    assert r["data"]["modifiedCount"] == 1
    assert api.get("/api/messages/unread-count", headers=bh).json()["data"]["unreadCount"] == 0
