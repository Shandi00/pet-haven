def test_browsing_history_flow(api, make_user, make_pet):
    owner, _ = make_user()
    _, h = make_user()
    a = make_pet(owner, name="甲")
    b = make_pet(owner, name="乙", adoptionStatus="adopted")
    for pet in (a, b, a):
        assert api.post("/api/browsing-history", json={"petId": str(pet["_id"])}, headers=h).json()["success"]
    r = api.get("/api/browsing-history", headers=h).json()
    # 只回傳可認養的，同一隻只留最新一筆
    assert r["count"] == 1 and r["history"][0]["name"] == "甲" and r["history"][0]["viewedAt"]
    assert api.post("/api/browsing-history", json={}, headers=h).json() == {"error": "缺少寵物 ID"}
    assert api.delete("/api/browsing-history", headers=h).json()["success"]
    assert api.get("/api/browsing-history", headers=h).json()["count"] == 0


def test_public_stats(api, make_user, make_pet):
    owner, _ = make_user()
    make_pet(owner, species="cat")
    make_pet(owner, govData={"animalId": "123"})
    d = api.get("/api/stats").json()["data"]
    assert d["available"] == 2 and d["importedPets"] == 1 and sorted(d["bySpecies"]) == ["cat", "dog"]


def test_shelter_stats_counts_own_pets(api, make_user, make_pet):
    shelter, sh = make_user("shelter")
    _, other_h = make_user("shelter")
    _, uh = make_user()
    make_pet(shelter)
    make_pet(shelter, adoptionStatus="adopted", sponsorship={"enabled": True, "externalLink": "https://x.org",
                                                             "clickCount": 3})
    d = api.get(f"/api/shelters/{shelter['_id']}/stats", headers=sh).json()["data"]
    assert d["overview"]["totalPets"] == 2 and d["overview"]["adoptedPets"] == 1
    assert d["overview"]["totalSponsorshipClicks"] == 3 and d["topSponsoredPets"][0]["name"] == "小白"
    assert api.get(f"/api/shelters/{shelter['_id']}/stats", headers=other_h).status_code == 403
    assert api.get(f"/api/shelters/{shelter['_id']}/stats", headers=uh).status_code == 403
