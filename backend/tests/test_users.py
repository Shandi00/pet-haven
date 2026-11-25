from bson import ObjectId


def test_profile_update_cannot_escalate_role(api, make_user, sync_db):
    user, h = make_user()
    r = api.put("/api/users/profile", json={"firstName": "新名", "role": "admin", "isActive": False,
                                            "recommendationProfile": {"species": ["cat"]}}, headers=h)
    assert r.status_code == 200
    stored = sync_db.users.find_one({"_id": user["_id"]})
    assert stored["role"] == "user" and stored["isActive"] is True and stored["firstName"] == "新名"
    assert stored["recommendationProfile"]["species"] == ["cat"] and stored["recommendationProfile"]["lastUpdated"]
    assert api.get("/api/users/profile", headers=h).json()["firstName"] == "新名"
    assert "password" not in api.get("/api/users/profile", headers=h).json()


def test_favorites_and_saved_posts(api, make_user, make_pet, sync_db):
    owner, _ = make_user()
    user, h = make_user()
    pet = make_pet(owner)
    r = api.post(f"/api/users/favorites/{pet['_id']}", headers=h).json()
    assert r["data"] == {"favorited": True, "favoritesCount": 1}
    favs = api.get("/api/users/favorites", headers=h).json()["data"]
    assert favs["count"] == 1 and favs["favorites"][0]["createdBy"]["username"] == owner["username"]
    assert api.post(f"/api/users/favorites/{pet['_id']}", headers=h).json()["data"]["favorited"] is False
    assert api.post(f"/api/users/favorites/{ObjectId()}", headers=h).status_code == 404

    post_id = sync_db.posts.insert_one({"title": "t", "content": "內容內容內容內容內容", "author": owner["_id"],
                                        "slug": "t"}).inserted_id
    assert api.post(f"/api/users/saved-posts/{post_id}", headers=h).json()["data"]["saved"] is True
    posts = api.get("/api/users/saved-posts", headers=h).json()["data"]["posts"]
    assert posts[0]["url"] == "/posts/t" and posts[0]["author"]["username"] == owner["username"]


def test_admin_routes(api, make_user):
    target, th = make_user()
    _, ah = make_user("admin")
    assert api.get("/api/users/admin/all", headers=th).json() == {"error": "需要管理員權限"}
    r = api.get("/api/users/admin/all", params={"role": "user"}, headers=ah).json()
    assert r["pagination"]["totalItems"] == 1
    # 舊版 /admin/search 被 /admin/:id 擋住而無法使用，現在固定路徑在前
    found = api.get("/api/users/admin/search", params={"q": target["username"][:6]}, headers=ah).json()
    assert found[0]["_id"] == str(target["_id"])
    assert api.get("/api/users/admin/search", params={"q": "a"}, headers=ah).status_code == 400
    assert api.get("/api/users/admin/stats/overview", headers=ah).json()["totalUsers"] == 2
    assert api.get(f"/api/users/admin/{target['_id']}", headers=ah).json()["_id"] == str(target["_id"])
    r = api.put(f"/api/users/admin/{target['_id']}/role", json={"role": "shelter"}, headers=ah)
    assert r.status_code == 200 and r.json()["user"]["role"] == "shelter"
    assert api.put(f"/api/users/admin/{target['_id']}/role", json={"role": "god"}, headers=ah).status_code == 400
    r = api.put(f"/api/users/admin/{target['_id']}/active", json={"isActive": False}, headers=ah)
    assert r.json()["message"] == "使用者帳號已停用"
    assert api.get("/api/users/profile", headers=th).status_code == 401


def test_stats_activities_and_adoptions(api, make_user):
    user, h = make_user(environmentProfile={"hasChildren": True})
    _, oh = make_user()
    stats = api.get("/api/users/me/stats", headers=h).json()["data"]
    assert stats["matchingProfileComplete"] == 25 and stats["applicationsCount"] == 0
    assert api.get("/api/users/me/activities", headers=h).json() == {"success": True, "data": []}
    assert api.get(f"/api/users/{user['_id']}/adoptions", headers=h).json()["pagination"]["totalItems"] == 0
    assert api.get(f"/api/users/{user['_id']}/adoptions", headers=oh).status_code == 403
