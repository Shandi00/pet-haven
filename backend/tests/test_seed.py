import seed


def test_seed_is_idempotent_and_valid(api, sync_db):
    first = api.portal.call(seed.seed)
    assert first["added"] == 8 and first["skipped"] == 0
    second = api.portal.call(seed.seed)
    assert second["added"] == 0 and second["skipped"] == 8
    assert sync_db.users.count_documents({"email": "shelter@example.com"}) == 1
    pets = api.get("/api/pets", params={"limit": 20}).json()["pets"]
    assert len(pets) == 8 and all(p["createdBy"]["username"] == "lovepets_shelter" for p in pets)
    r = api.post("/api/auth/login", json={"email": "shelter@example.com", "password": seed.SHELTER_PASSWORD})
    assert r.status_code == 200 and r.json()["user"]["role"] == "shelter"
