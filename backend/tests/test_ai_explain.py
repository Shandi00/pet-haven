import asyncio

from app.services import ai_explain

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


def test_summary_truncated_to_80():
    assert len(ai_explain.rule_reason({**PET, "name": "長" * 80}, USER)["summary"]) == 80


def test_explain_falls_back_to_rule():
    assert asyncio.run(ai_explain.explain(PET, USER))["source"] == "rule"
