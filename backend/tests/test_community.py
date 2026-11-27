import io
from datetime import datetime, timedelta, timezone

from bson import ObjectId

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 50


def test_post_crud_like_and_same_title(api, make_user, sync_db):
    author, ah = make_user()
    reader, rh = make_user()
    r = api.post("/api/posts", data={"title": "找狗狗", "content": "我家狗狗走失了請大家幫忙", "type": "lost-pet",
                                     "lostPetInfo": '{"petName": "小黃", "contactPhone": "0912345678"}',
                                     "tags": '["走失"]'},
                 files=[("images", ("a.png", io.BytesIO(PNG), "image/png"))], headers=ah)
    assert r.status_code == 201, r.text
    post = r.json()["data"]
    assert post["category"] == "lost-found" and post["lostPetInfo"]["petName"] == "小黃"
    assert post["slug"] == "找狗狗" and post["images"][0]["url"].startswith("/uploads/posts/") and post["publishedAt"]
    # 同標題不再因 slug 重複而失敗
    r2 = api.post("/api/posts", json={"title": "找狗狗", "content": "另一篇內容內容內容內容"}, headers=ah)
    assert r2.status_code == 201 and r2.json()["data"]["slug"] != "找狗狗"
    assert api.post("/api/posts", json={"title": "x", "content": "短"}, headers=ah).status_code == 400
    assert api.post("/api/posts", json={"title": "x", "content": "內容內容內容內容內容", "lostPetInfo": {}},
                    headers=ah).status_code == 400

    lst = api.get("/api/posts", headers=rh).json()
    assert lst["success"] and lst["pagination"]["totalItems"] == 2 and lst["data"]["posts"][0]["isLiked"] is False

    r = api.post(f"/api/posts/{post['_id']}/like", headers=rh).json()
    assert r["data"] == {"liked": True, "likesCount": 1}
    assert sync_db.notifications.find_one({"recipient": author["_id"], "type": "like"})
    detail = api.get(f"/api/posts/{post['_id']}", headers=rh).json()["data"]
    assert detail["isLiked"] is True and detail["stats"]["views"] == 1 and detail["comments"] == []

    assert api.put(f"/api/posts/{post['_id']}", json={"title": "改一下標題文字"}, headers=rh).status_code == 403
    r = api.put(f"/api/posts/{post['_id']}", json={"title": "改一下標題文字"}, headers=ah)
    assert r.status_code == 200 and r.json()["data"]["title"] == "改一下標題文字" and r.json()["data"]["content"]
    assert api.patch(f"/api/posts/{post['_id']}/status", json={"status": "found"}, headers=ah).json()["data"][
        "status"] == "found"
    assert api.delete(f"/api/posts/{post['_id']}", headers=ah).json()["message"] == "文章已刪除"
    assert api.get("/api/posts/categories/list").json()["data"][0]["value"] == "adoption-story"
    assert api.get(f"/api/posts/{ObjectId()}").status_code == 404


def test_comments_reply_like_report_edit(api, make_user, sync_db):
    author, ah = make_user()
    reader, rh = make_user()
    pid = api.post("/api/posts", json={"title": "分享", "content": "認養後的生活真的很開心"}, headers=ah).json()["data"]["_id"]
    r = api.post("/api/comments", json={"content": "好棒", "post": pid}, headers=rh)
    assert r.status_code == 201
    cid = r.json()["data"]["_id"]
    assert sync_db.posts.find_one({"_id": ObjectId(pid)})["stats"]["comments"] == 1
    r = api.post(f"/api/comments/{cid}/reply", json={"content": "謝謝"}, headers=ah)
    assert r.status_code == 201 and r.json()["data"]["isReply"] is True
    top = api.get(f"/api/comments/post/{pid}").json()["data"]
    assert top["pagination"]["total"] == 1 and top["comments"][0]["replies"][0]["author"]["username"]
    assert api.get(f"/api/comments/{cid}/replies").json()["data"]["pagination"]["total"] == 1
    assert sync_db.posts.find_one({"_id": ObjectId(pid)})["stats"]["comments"] == 2

    assert api.post(f"/api/comments/{cid}/like", headers=ah).json()["data"]["liked"] is True
    assert api.post(f"/api/comments/{cid}/report", json={"reason": "spam"}, headers=ah).json()["success"]
    assert api.post(f"/api/comments/{cid}/report", json={"reason": "spam"}, headers=ah).status_code == 400
    assert api.post(f"/api/comments/{cid}/report", json={"reason": "bad"}, headers=rh).status_code == 400

    r = api.put(f"/api/comments/{cid}", json={"content": "超棒", "post": pid}, headers=rh).json()["data"]
    assert r["content"] == "超棒" and r["isEdited"] is True
    sync_db.comments.update_one({"_id": ObjectId(cid)},
                                {"$set": {"createdAt": datetime.now(timezone.utc) - timedelta(minutes=20)}})
    assert api.put(f"/api/comments/{cid}", json={"content": "x", "post": pid}, headers=rh).status_code == 403
    assert api.delete(f"/api/comments/{cid}", headers=ah).status_code == 403
    assert api.delete(f"/api/comments/{cid}", headers=rh).json()["message"] == "評論已刪除"
    assert sync_db.posts.find_one({"_id": ObjectId(pid)})["stats"]["comments"] == 1
    assert api.get(f"/api/comments/user/{reader['_id']}").json()["data"]["pagination"]["total"] == 0
    # 貼文詳情不能再出現已刪除的留言
    detail = api.get(f"/api/posts/{pid}").json()["data"]["comments"]
    assert [c["_id"] for c in detail] != [] and cid not in [c["_id"] for c in detail]


def test_comment_output_hides_ip_and_reporters(api, make_user, sync_db):
    # 留言者的 IP 與檢舉人是個資，公開的留言 API 不能回傳（AGENTS.md）
    author, ah = make_user()
    reader, rh = make_user()
    pid = api.post("/api/posts", json={"title": "分享", "content": "認養後的生活真的很開心"}, headers=ah).json()["data"]["_id"]
    cid = api.post("/api/comments", json={"content": "好棒", "post": pid}, headers=rh).json()["data"]["_id"]
    api.post(f"/api/comments/{cid}/reply", json={"content": "謝謝"}, headers=ah)
    assert api.post(f"/api/comments/{cid}/report", json={"reason": "spam"}, headers=ah).status_code == 200
    assert sync_db.comments.find_one({"_id": ObjectId(cid)}).get("reports")  # 資料庫仍保留，供管理用
    outputs = [api.get(f"/api/comments/post/{pid}").json()["data"]["comments"][0],
               api.get(f"/api/comments/user/{reader['_id']}").json()["data"]["comments"][0],
               api.get(f"/api/comments/{cid}/replies").json()["data"]["replies"][0],
               *api.get(f"/api/posts/{pid}").json()["data"]["comments"]]
    for c in outputs:
        assert "ipAddress" not in c and "reports" not in c
        for reply in c.get("replies") or []:
            assert "ipAddress" not in reply and "reports" not in reply


def test_deleted_and_draft_posts_are_hidden_from_others(api, make_user):
    author, ah = make_user()
    _, rh = make_user()
    _, admin_h = make_user("admin")
    draft = api.post("/api/posts", json={"title": "草稿標題", "content": "還沒寫完的草稿內容內容",
                                         "status": "draft"}, headers=ah).json()["data"]["_id"]
    gone = api.post("/api/posts", json={"title": "要刪除的", "content": "之後會刪掉的內容內容"},
                    headers=ah).json()["data"]["_id"]
    api.delete(f"/api/posts/{gone}", headers=ah)
    for pid in (draft, gone):
        assert api.get(f"/api/posts/{pid}").status_code == 404
        assert api.get(f"/api/posts/{pid}", headers=rh).status_code == 404
        assert api.get(f"/api/posts/{pid}", headers=admin_h).status_code == 200
    assert api.get(f"/api/posts/{draft}", headers=ah).status_code == 200
    # 已刪除的貼文也不能再按讚、留言
    assert api.post(f"/api/posts/{gone}/like", headers=rh).status_code == 404
    assert api.post("/api/comments", json={"content": "嗨", "post": gone}, headers=rh).status_code == 404
