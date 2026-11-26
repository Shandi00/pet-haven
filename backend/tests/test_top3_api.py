def test_top3_requires_login(api):
    assert api.get("/api/matching/top3").status_code == 401
    assert api.post("/api/matching/feedback", json={}).status_code == 401
    assert api.delete("/api/matching/feedback").status_code == 401


def test_top3_filters_ranks_and_handles_few_pets(api, make_user, make_pet):
    owner, _ = make_user("shelter")
    _, h = make_user(environmentProfile={"hasChildren": True})
    assert api.get("/api/matching/top3", headers=h).json()["data"]["items"] == []
    make_pet(owner, name="怕小孩", personality={"activityLevel": "high", "goodWith": {"children": False}})
    make_pet(owner, name="已認養", adoptionStatus="adopted")
    make_pet(owner, name="可以")
    data = api.get("/api/matching/top3", headers=h).json()["data"]
    assert [i["pet"]["name"] for i in data["items"]] == ["可以"]
    item = data["items"][0]
    assert item["reason"]["source"] == "rule" and item["pet"]["photo"] == "" and data["avoided"] == []
    assert item["reason"]["cautions"][0].startswith("還不確定可以能否和小孩相處")
    assert isinstance(item["score"], int) and data["generatedAt"]


def test_dislike_reranks_and_like_overrides(api, make_user, make_pet):
    owner, _ = make_user("shelter")
    # 有填偏好，分數才不會超過 100 而看不到扣分
    _, h = make_user(recommendationProfile={"species": ["dog", "cat"], "sizes": ["small"],
                                            "ageCategories": ["senior"], "personality": ["calm"]})
    a = make_pet(owner, name="阿福", personality={"activityLevel": "high"})
    make_pet(owner, name="相似", personality={"activityLevel": "high"})
    make_pet(owner, name="不同", species="cat", personality={"activityLevel": "low"})
    before = {i["pet"]["name"]: i["score"] for i in api.get("/api/matching/top3", headers=h).json()["data"]["items"]}
    r = api.post("/api/matching/feedback", json={"petId": str(a["_id"]), "verdict": "dislike"}, headers=h).json()["data"]
    after = {i["pet"]["name"]: i["score"] for i in r["items"]}
    assert "阿福" not in after and after["相似"] == before["相似"] - 5 and after["不同"] == before["不同"]
    assert r["avoided"][0]["name"] == "阿福"
    assert api.post("/api/matching/feedback", json={"petId": str(a["_id"]), "verdict": "like"},
                    headers=h).json()["data"] == {"recorded": True}
    data = api.get("/api/matching/top3", headers=h).json()["data"]
    assert data["avoided"] == [] and "阿福" in [i["pet"]["name"] for i in data["items"]]


def test_avoided_skips_deleted_pet_and_feedback_is_per_user(api, make_user, make_pet, sync_db):
    owner, _ = make_user("shelter")
    _, h = make_user()
    _, other = make_user()
    a = make_pet(owner, name="阿福")
    api.post("/api/matching/feedback", json={"petId": str(a["_id"]), "verdict": "dislike"}, headers=h)
    assert api.get("/api/matching/top3", headers=other).json()["data"]["avoided"] == []
    sync_db.pets.delete_one({"_id": a["_id"]})
    assert api.get("/api/matching/top3", headers=h).json()["data"]["avoided"] == []
    assert api.delete("/api/matching/feedback", headers=h).json()["data"] == {"cleared": 1}
    assert api.delete("/api/matching/feedback", headers=h).json()["data"] == {"cleared": 0}


def test_feedback_validation(api, make_user, make_pet):
    owner, _ = make_user("shelter")
    _, h = make_user()
    pid = str(make_pet(owner)["_id"])
    for body in ({"petId": pid}, {"petId": pid, "verdict": "maybe"}, {"petId": 123, "verdict": "like"},
                 {"petId": "bad", "verdict": "like"}, ["x"]):
        r = api.post("/api/matching/feedback", json=body, headers=h)
        assert r.status_code == 400 and r.json()["success"] is False, body
    assert api.post("/api/matching/feedback", json={"petId": "6b06a40e4382ba73f6fb0000", "verdict": "like"},
                    headers=h).status_code == 404


def test_top3_and_feedback_are_rate_limited(api, make_user, make_pet, monkeypatch):
    from app.core.ratelimit import UserRateLimiter
    from app.routers import matching

    owner, _ = make_user("shelter")
    _, h = make_user()
    pid = str(make_pet(owner)["_id"])
    monkeypatch.setattr(matching, "matching_limiter", UserRateLimiter(2, 60, enabled=True))
    assert api.get("/api/matching/top3", headers=h).status_code == 200
    assert api.post("/api/matching/feedback", json={"petId": pid, "verdict": "like"}, headers=h).status_code == 200
    r = api.get("/api/matching/top3", headers=h)
    assert r.status_code == 429 and r.json()["message"] == "呼叫太頻繁，請稍後再試"
    assert api.post("/api/matching/feedback", json={"petId": pid, "verdict": "like"}, headers=h).status_code == 429
