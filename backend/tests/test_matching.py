import json
import math
from pathlib import Path

import pytest

from app.services.advanced_matching import calculate_compatibility, calculate_compatibility_normalized, calculate_match

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


NORM_PET = {"species": "dog", "size": "medium", "ageCategory": "adult", "personality": {"traits": ["friendly"]}}


def test_normalized_compatibility_uses_only_filled_preferences():
    # 舊版在偏好沒填時把 max_score 重設，分數會超過 100；normalized 只用有填的偏好計算
    assert calculate_compatibility(NORM_PET, {}) > 100
    assert calculate_compatibility_normalized(NORM_PET, {}) == 75
    full = {"recommendationProfile": {"species": ["dog"], "sizes": ["medium"], "ageCategories": ["adult"],
                                      "personality": ["friendly"]}}
    assert calculate_compatibility_normalized(NORM_PET, full) == 100
    assert calculate_compatibility_normalized(NORM_PET, {"recommendationProfile": {"species": ["dog"]}}) == 100
    assert calculate_compatibility_normalized(
        NORM_PET, {"recommendationProfile": {"species": ["cat"]}}) == pytest.approx(100 / 3)
    adjacent = {"recommendationProfile": {"sizes": ["small"], "personality": ["calm", "friendly"]}}
    assert calculate_compatibility_normalized(NORM_PET, adjacent) == pytest.approx((10 + 17.5) / 55 * 100)
    assert calculate_compatibility_normalized({"species": "dog"}, {"recommendationProfile": {
        "personality": ["calm"]}}) == 75
    match = calculate_match(NORM_PET, {}, normalized=True)
    assert match["breakdown"]["compatibility"] == 75 and match["matchScore"] <= 100


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


GAME = {
    "answers": [{"questionId": f"q{i}", "optionId": "A"} for i in range(1, 9)],
    "petType": {"code": "outdoor-buddy", "label": "戶外冒險型", "description": "適合活動量高的毛孩"},
}


def test_save_game_profile(api, make_user):
    _, h = make_user()
    assert api.get("/api/matching/profile", headers=h).json()["data"]["gameProfile"] is None  # 沒玩過
    res = api.put("/api/matching/profile/game", json=GAME, headers=h)
    assert res.status_code == 200
    saved = res.json()["data"]["gameProfile"]
    assert saved["petType"] == GAME["petType"] and saved["answers"] == GAME["answers"] and saved["completedAt"]
    prof = api.get("/api/matching/profile", headers=h).json()["data"]
    assert prof["gameProfile"]["answers"] == GAME["answers"]
    assert prof["gameProfile"]["petType"]["label"] == "戶外冒險型"
    # 再玩一次整筆覆蓋；不會改動配對欄位
    again = {**GAME, "petType": {"code": "couch-buddy", "label": "居家宅宅型"}}
    assert api.put("/api/matching/profile/game", json=again, headers=h).status_code == 200
    prof = api.get("/api/matching/profile", headers=h).json()["data"]
    assert prof["gameProfile"]["petType"] == {"code": "couch-buddy", "label": "居家宅宅型"}
    assert prof["lifestyleProfile"] == {}


@pytest.mark.parametrize("bad", [
    {**GAME, "answers": GAME["answers"][:7]},                                                   # 只有 7 題
    {**GAME, "answers": GAME["answers"][:7] + [{"questionId": "q1", "optionId": "B"}]},         # 題號重複
    {**GAME, "answers": GAME["answers"][:7] + [{"questionId": "q9", "optionId": "A"}]},         # 題號超出範圍
    {**GAME, "answers": GAME["answers"][:7] + [{"questionId": "q8", "optionId": "E"}]},         # 選項不是 A-D
    {**GAME, "petType": {**GAME["petType"], "code": "outdoor buddy!"}},                         # code 有空白與符號
    {**GAME, "petType": {**GAME["petType"], "label": "字" * 21}},                               # label 超過 20 字
    {**GAME, "petType": {**GAME["petType"], "description": "字" * 101}},                        # 說明超過 100 字
    {"answers": GAME["answers"]},                                                               # 沒有 petType
    {"answers": "q1", "petType": GAME["petType"]},
])
def test_game_profile_validation(api, make_user, bad):
    _, h = make_user()
    res = api.put("/api/matching/profile/game", json=bad, headers=h)
    assert res.status_code == 400 and res.json() == {"success": False, "message": "參數錯誤"}
    assert api.get("/api/matching/profile", headers=h).json()["data"]["gameProfile"] is None  # 不寫入任何資料


def test_game_profile_requires_login(client):
    assert client.put("/api/matching/profile/game", json=GAME).status_code == 401
