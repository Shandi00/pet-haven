from pydantic import SecretStr

import seed
from app.config import get_settings


def _login(api, password):
    return api.post("/api/auth/login", json={"email": "shelter@example.com", "password": password})


def test_seed_is_idempotent_and_valid(api, sync_db):
    first = api.portal.call(seed.seed)
    assert first["added"] == 8 and first["skipped"] == 0
    second = api.portal.call(seed.seed)
    assert second["added"] == 0 and second["skipped"] == 8
    assert sync_db.users.count_documents({"email": "shelter@example.com"}) == 1
    pets = api.get("/api/pets", params={"limit": 20}).json()["pets"]
    assert len(pets) == 8 and all(p["createdBy"]["username"] == "lovepets_shelter" for p in pets)
    r = _login(api, seed.DEFAULT_SHELTER_PASSWORD)
    assert r.status_code == 200 and r.json()["user"]["role"] == "shelter"


def test_seed_adds_demo_adoption_stories_once_and_can_remove_them(api, sync_db):
    # 首頁「成功故事」原本寫死在前端，改由 seed 寫進資料庫；作者是無法登入的示範帳號
    first = api.portal.call(seed.seed)
    assert first["stories"] == 3
    assert api.portal.call(seed.seed)["stories"] == 0  # 重跑不會重複新增
    posts = api.get("/api/posts", params={"type": "adoption-story", "limit": 10}).json()["data"]["posts"]
    assert sorted(p["title"] for p in posts) == sorted(s["title"] for s in seed.DEMO_STORIES)
    assert all("示範" in p["tags"] and p["images"][0]["url"].startswith("https://") for p in posts)
    demo_users = list(sync_db.users.find({"email": {"$regex": f"@{seed.DEMO_DOMAIN}$"}}))
    assert len(demo_users) == 3 and {u["role"] for u in demo_users} == {"user"}
    assert {p["author"]["firstName"] for p in posts} == {s["nickname"] for s in seed.DEMO_STORIES}

    removed = api.portal.call(seed.remove_demo)
    assert removed == {"users": 3, "posts": 3}
    assert api.get("/api/posts", params={"type": "adoption-story"}).json()["data"]["posts"] == []
    assert sync_db.users.count_documents({"email": "shelter@example.com"}) == 1  # 收容所帳號不受影響


def test_seed_uses_env_password(api, monkeypatch):
    # 展示機設定 SEED_SHELTER_PASSWORD，公開 repo 裡的預設密碼就登不進去
    monkeypatch.setattr(get_settings(), "seed_shelter_password", SecretStr("DemoOnly9x"))
    api.portal.call(seed.seed)
    assert _login(api, "DemoOnly9x").status_code == 200
    assert _login(api, seed.DEFAULT_SHELTER_PASSWORD).status_code == 401


def test_seed_resets_existing_password_when_env_set(api, monkeypatch):
    # 資料庫先前已用預設密碼 seed 過（例如共用的 Atlas），設定環境變數後重跑要換掉密碼
    api.portal.call(seed.seed)
    monkeypatch.setattr(get_settings(), "seed_shelter_password", SecretStr("DemoOnly9x"))
    api.portal.call(seed.seed)
    assert _login(api, "DemoOnly9x").status_code == 200
    assert _login(api, seed.DEFAULT_SHELTER_PASSWORD).status_code == 401
