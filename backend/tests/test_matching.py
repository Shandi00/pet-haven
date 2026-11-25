import json
import math
from pathlib import Path

from app.services.advanced_matching import calculate_match

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "matching_golden.json").read_text(encoding="utf-8"))


def same(a, b, path="") -> list:
    if isinstance(a, float) or isinstance(b, float):
        return [] if math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9) else [f"{path}: {a} != {b}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(a)} != {sorted(b)}"]
        return [e for k in a for e in same(a[k], b[k], f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: len {len(a)} != {len(b)}"]
        return [e for i, (x, y) in enumerate(zip(a, b)) for e in same(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def test_matches_legacy_js_on_200_golden_cases():
    # golden 由舊版 advancedMatchingService.js 產生，確保搬遷後分數、分析、建議完全相同
    diffs = []
    for i, case in enumerate(GOLDEN):
        diffs += same(calculate_match(case["pet"], case["user"]), case["expected"], f"case{i}")
    assert not diffs, diffs[:10]


def test_profile_endpoints_and_analysis(api, make_user, make_pet):
    owner, _ = make_user("shelter")
    user, h = make_user()
    pet = make_pet(owner, personality={"activityLevel": "moderate", "traits": ["friendly", "calm"]})
    r = api.get("/api/matching/best-matches", headers=h).json()
    assert r["data"]["hasProfiles"] is False
    r = api.put("/api/matching/profile/lifestyle", json={"activityLevel": "high", "housingType": "apartment"}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["lifestyleProfile"]["activityLevel"] == "high"
    assert api.put("/api/matching/profile/lifestyle", json={"activityLevel": "crazy"}, headers=h).status_code == 400
    assert api.put("/api/matching/profile/experience", json={}, headers=h).json()["data"]["experienceProfile"][
        "petOwnershipExperience"] == "none"
    api.put("/api/matching/profile/environment", json={"hasChildren": True}, headers=h)
    prof = api.get("/api/matching/profile", headers=h).json()["data"]
    assert prof["environmentProfile"]["hasChildren"] is True and prof["recommendationProfile"] == {}

    r = api.get(f"/api/matching/analyze/{pet['_id']}", headers=h).json()["data"]
    assert r["pet"]["name"] == "小白" and r["matchScore"] > 0 and "strengths" in r["analysis"]
    best = api.get("/api/matching/best-matches", params={"minScore": 0}, headers=h).json()["data"]
    assert best["hasProfiles"] and best["count"] == 1 and best["matches"][0]["pet"]["_id"] == str(pet["_id"])
    batch = api.post("/api/matching/batch-analyze", json={"petIds": [str(pet["_id"]), "bad"]}, headers=h).json()
    assert batch["data"]["count"] == 1
    assert api.post("/api/matching/batch-analyze", json={}, headers=h).status_code == 400
    assert api.get("/api/matching/analyze/abc", headers=h).status_code == 404
