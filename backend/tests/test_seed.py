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
