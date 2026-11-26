import asyncio
import json

import pytest

from app.services import ai_explain, llm

PET = {"name": "小黑", "species": "dog", "size": "medium",
       "personality": {"traits": ["friendly"], "activityLevel": "high", "goodWith": {"children": None}}}
USER = {"environmentProfile": {"hasChildren": True}}


def test_rule_reason_shape_and_limits():
    r = ai_explain.rule_reason(PET, USER)
    assert r["source"] == "rule" and len(r["summary"]) <= 80 and "小黑" in r["summary"]
    assert len(r["highlights"]) <= 3 and len(r["cautions"]) <= 3


def test_rule_reason_flags_unknown_good_with():
    assert ai_explain.rule_reason(PET, USER)["cautions"][0] == "還不確定小黑能否和小孩相處，建議先向送養人確認"
    known = {**PET, "personality": {**PET["personality"], "goodWith": {"children": True}}}
    assert not any("小孩" in c for c in ai_explain.rule_reason(known, USER)["cautions"])


def test_rule_reason_flags_unknown_other_pets_when_good_with_missing():
    pet = {**PET, "personality": {"activityLevel": "high"}}
    cautions = ai_explain.rule_reason(pet, {"environmentProfile": {"hasOtherPets": True}})["cautions"]
    assert cautions[0] == "還不確定小黑能否和其他寵物相處，建議先向送養人確認"


def test_rule_reason_ignores_unfilled_preferences():
    # 沒填偏好不能說「基本屬性高度相容」，也不能叫使用者考慮其他選項
    r = ai_explain.rule_reason(PET, {})
    assert "基本屬性高度相容" not in r["highlights"]
    assert not any("基本偏好" in c for c in r["cautions"])


def test_rule_reason_skips_claims_about_unfilled_profiles():
    # 沒填的檔案用的是預設分數，不能說成使用者的實際狀況
    r = ai_explain.rule_reason(PET, {"lifestyleProfile": {}, "environmentProfile": {}})
    said = r["highlights"] + r["cautions"] + [r["summary"]]
    for claim in ("家庭環境理想", "生活方式", "您的經驗適合"):
        assert not any(claim in s for s in said), claim


def test_rule_reason_keeps_claims_about_filled_profiles():
    user = {"environmentProfile": {"hasChildren": False, "hasOtherPets": False},
            "lifestyleProfile": {"activityLevel": "low", "availableTime": "minimal", "housingType": "apartment"},
            "experienceProfile": {"petOwnershipExperience": "experienced"}}
    pet = {**PET, "size": "large", "careRequirements": {"exerciseNeeds": "high", "timeCommitment": "high",
                                                        "careLevel": "high"}}
    r = ai_explain.rule_reason(pet, user)
    assert "家庭環境理想" in r["highlights"] and "您的經驗適合照顧這隻寵物" in r["highlights"]
    assert "生活方式可能需要調整以適應寵物需求" in r["cautions"]


def test_summary_truncated_to_80():
    assert len(ai_explain.rule_reason({**PET, "name": "長" * 80}, USER)["summary"]) == 80


def test_explain_falls_back_to_rule():
    assert asyncio.run(ai_explain.explain(PET, USER))["source"] == "rule"


# ---- Gemini 路徑（T12 Task 7）----

PRIVATE_USER = {"_id": "u1", "name": "王小明", "email": "a@example.com", "phone": "0912345678",
                "address": {"city": "台北市", "street": "信義路"},
                "lifestyleProfile": {"activityLevel": "high", "housingType": "apartment", "lastUpdated": "x"},
                "experienceProfile": {"petOwnershipExperience": "beginner", "trainingExperience": True,
                                      "previousPets": [{"species": "dog"}]},
                "environmentProfile": {"hasChildren": True, "hasOtherPets": False, "noiseSensitive": False,
                                       "hasAllergies": False, "childrenAges": ["4-6"]},
                "gameProfile": {"petType": {"code": "outdoor-buddy", "label": "戶外冒險型", "description": "x"}}}
FULL_PET = {**PET, "_id": "p1", "breed": "米克斯", "ageCategory": "adult", "description": "很乖",
            "healthStatus": {"medicalHistory": "曾經骨折"}, "shelterInfo": {"contactPhone": "0223456789"},
            "personality": {**PET["personality"], "specialNeeds": ["需要每天吃藥"]}}


def _capture(monkeypatch, reply):
    seen = {}

    async def fake(system, prompt):
        seen.update(system=system, prompt=prompt)
        return reply
    monkeypatch.setattr(llm, "generate_json", fake)
    return seen


def test_llm_input_only_whitelisted_fields():
    data = ai_explain._llm_input(FULL_PET, PRIVATE_USER)
    assert set(data) == {"pet", "user"}
    assert set(data["pet"]) == {"name", "species", "breed", "ageCategory", "size", "traits", "activityLevel",
                                "goodWith", "specialNeeds"}
    assert set(data["user"]) == {"lifestyleProfile", "experienceProfile", "environmentProfile", "petType"}
    assert set(data["user"]["experienceProfile"]) == {"petOwnershipExperience", "trainingExperience"}
    assert set(data["user"]["environmentProfile"]) == {"hasChildren", "hasOtherPets", "noiseSensitive",
                                                      "hasAllergies"}
    assert data["user"]["petType"] == "戶外冒險型"


def test_prompt_contains_no_personal_data(monkeypatch):
    seen = _capture(monkeypatch, None)
    asyncio.run(ai_explain.explain(FULL_PET, PRIVATE_USER))
    for secret in ("王小明", "a@example.com", "0912345678", "台北市", "信義路", "曾經骨折", "0223456789", "很乖"):
        assert secret not in seen["prompt"] and secret not in seen["system"]
    assert json.loads(seen["prompt"]) == ai_explain._llm_input(FULL_PET, PRIVATE_USER)


def test_valid_ai_reason_is_used_and_keeps_unknown_good_with_caution(monkeypatch):
    _capture(monkeypatch, {"summary": "小黑活動量高，跟你的生活很合。", "highlights": ["活動量相符"],
                           "cautions": ["住公寓需留意吠叫"]})
    r = asyncio.run(ai_explain.explain(PET, USER))
    assert r == {"summary": "小黑活動量高，跟你的生活很合。", "highlights": ["活動量相符"],
                 "cautions": ["還不確定小黑能否和小孩相處，建議先向送養人確認", "住公寓需留意吠叫"],
                 "source": "ai"}


@pytest.mark.parametrize("reply", [
    None,
    {"summary": "字" * 81, "highlights": [], "cautions": []},
    {"summary": "", "highlights": [], "cautions": []},
    {"highlights": [], "cautions": []},
    {"summary": "好", "highlights": ["a", "b", "c", "d"], "cautions": []},
    {"summary": "好", "highlights": [1], "cautions": []},
    {"summary": "好", "highlights": [""], "cautions": []},
    {"summary": "好", "highlights": "不是陣列", "cautions": []},
])
def test_invalid_ai_output_falls_back_to_rule(monkeypatch, reply):
    _capture(monkeypatch, reply)
    assert asyncio.run(ai_explain.explain(PET, USER)) == ai_explain.rule_reason(PET, USER)


@pytest.fixture(autouse=True)
def _clear_cache():
    ai_explain._cache.clear()
    yield
    ai_explain._cache.clear()


def _counting(monkeypatch, reply):
    calls = []

    async def fake(system, prompt):
        calls.append(prompt)
        return reply
    monkeypatch.setattr(llm, "generate_json", fake)
    return calls


GOOD = {"summary": "小黑很適合你。", "highlights": ["活潑"], "cautions": []}


def test_same_input_reuses_cached_ai_reason(monkeypatch):
    calls = _counting(monkeypatch, GOOD)
    first = asyncio.run(ai_explain.explain(PET, USER))
    assert asyncio.run(ai_explain.explain(PET, USER)) == first and first["source"] == "ai"
    assert len(calls) == 1


def test_changed_input_calls_llm_again(monkeypatch):
    calls = _counting(monkeypatch, GOOD)
    asyncio.run(ai_explain.explain(PET, USER))
    asyncio.run(ai_explain.explain({**PET, "personality": {**PET["personality"], "traits": ["calm"]}}, USER))
    asyncio.run(ai_explain.explain(PET, {"environmentProfile": {"hasChildren": False}}))
    assert len(calls) == 3


def test_failed_output_is_not_cached(monkeypatch):
    calls = _counting(monkeypatch, None)
    asyncio.run(ai_explain.explain(PET, USER))
    asyncio.run(ai_explain.explain(PET, USER))
    assert len(calls) == 2


def test_cache_expires(monkeypatch):
    calls = _counting(monkeypatch, GOOD)
    now = [1000.0]
    monkeypatch.setattr(ai_explain.time, "monotonic", lambda: now[0])
    asyncio.run(ai_explain.explain(PET, USER))
    now[0] += ai_explain.CACHE_TTL_SECONDS + 1
    asyncio.run(ai_explain.explain(PET, USER))
    assert len(calls) == 2


def test_cache_size_is_bounded(monkeypatch):
    _counting(monkeypatch, GOOD)
    monkeypatch.setattr(ai_explain, "CACHE_MAX", 2)
    for name in ("甲", "乙", "丙"):
        asyncio.run(ai_explain.explain({**PET, "name": name}, USER))
    assert len(ai_explain._cache) == 2


def test_explain_endpoint(api, make_user, make_pet, monkeypatch):
    owner, _ = make_user("shelter")
    _, h = make_user()
    pet = make_pet(owner, name="小黑")
    assert api.post("/api/ai/explain", json={"petId": str(pet["_id"])}).status_code == 401
    for body in ({"petId": "abc"}, {"petId": 1}, {}, ["x"]):
        r = api.post("/api/ai/explain", json=body, headers=h)
        assert r.status_code == 400 and r.json()["success"] is False, body
    assert api.post("/api/ai/explain", json={"petId": "6b06a40e4382ba73f6fb0000"}, headers=h).status_code == 404
    assert api.post("/api/ai/explain", json={"petId": str(pet["_id"])},
                    headers=h).json()["data"]["reason"]["source"] == "rule"
    _capture(monkeypatch, {"summary": "小黑很適合你。", "highlights": [], "cautions": []})
    reason = api.post("/api/ai/explain", json={"petId": str(pet["_id"])}, headers=h).json()["data"]["reason"]
    assert reason["source"] == "ai" and reason["summary"] == "小黑很適合你。"
