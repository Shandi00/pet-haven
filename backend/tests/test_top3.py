from datetime import datetime, timezone

from bson import ObjectId

from app.services import top3


def pet(**kw):
    base = {"_id": ObjectId(), "name": "小白", "species": "dog", "size": "medium", "ageCategory": "adult",
            "personality": {"activityLevel": "high", "traits": [], "goodWith": {}},
            "createdAt": datetime(2026, 11, 1, tzinfo=timezone.utc)}
    base.update(kw)
    return base


def test_hard_rules():
    user = {"environmentProfile": {"hasChildren": True, "hasAllergies": True},
            "recommendationProfile": {"species": ["dog"]}}
    ok = pet()
    assert top3.passes_hard_rules(ok, user, set())
    assert not top3.passes_hard_rules(ok, user, {ok["_id"]})
    assert not top3.passes_hard_rules(pet(personality={"goodWith": {"children": False}}), user, set())
    assert top3.passes_hard_rules(pet(personality={"goodWith": {"children": None}}), user, set())
    assert not top3.passes_hard_rules(pet(species="cat"), {"environmentProfile": {"hasAllergies": True}}, set())
    assert not top3.passes_hard_rules(pet(species="rabbit"), user, set())
    assert top3.passes_hard_rules(pet(species="rabbit"), {"recommendationProfile": {"species": []}}, set())


def test_hard_rules_other_pets():
    user = {"environmentProfile": {"hasOtherPets": True}}
    assert not top3.passes_hard_rules(pet(personality={"goodWith": {"otherPets": False}}), user, set())
    assert top3.passes_hard_rules(pet(personality={}), user, set())


def test_penalty_caps_at_15_and_needs_same_species_and_activity():
    target = pet()
    same = [pet() for _ in range(4)]
    assert top3.penalty(target, same) == 15
    assert top3.penalty(target, [pet(species="cat"), pet(personality={"activityLevel": "low"})]) == 0
    assert top3.penalty(target, [target]) == 0
    no_activity = pet(personality={})
    assert top3.penalty(no_activity, [pet(personality={})]) == 0


def test_rank_tie_breaks_by_newer_and_limits_to_3():
    pets = [pet(name=str(i), createdAt=datetime(2026, 11, i + 1, tzinfo=timezone.utc)) for i in range(5)]
    ranked = top3.rank(pets, {}, [])
    assert [r["pet"]["name"] for r in ranked] == ["4", "3", "2"]
    assert all(isinstance(r["score"], int) for r in ranked)


def test_rank_applies_penalty_and_missing_created_at_sorts_last():
    disliked = pet(name="阿福")
    similar, other = pet(name="相似"), pet(name="不同", createdAt=None)
    base = {r["pet"]["name"]: r["score"] for r in top3.rank([similar, other], {}, [])}
    after = {r["pet"]["name"]: r for r in top3.rank([similar, other], {}, [disliked])}
    assert after["相似"]["score"] == base["相似"] - 5
    assert after["相似"]["matchLevel"] in ("perfect", "excellent", "good", "fair", "poor")
    assert [r["pet"]["name"] for r in top3.rank([other, similar], {}, [])] == ["相似", "不同"]


def test_pet_summary_photo_and_avoided_note():
    assert top3.pet_summary(pet())["photo"] == ""
    photos = [{"url": "/a.jpg"}, {"url": "/b.jpg", "isPrimary": True}]
    s = top3.pet_summary(pet(photos=photos))
    assert s["photo"] == "/b.jpg" and s["activityLevel"] == "high" and isinstance(s["_id"], str)
    assert top3.pet_summary(pet(photos=[{"url": "/a.jpg"}]))["photo"] == "/a.jpg"
    assert top3.avoided_note(pet(name="阿福"))["note"] == "已避開：阿福（狗，活動量高），並降低相似動物的排序"
    assert top3.avoided_note(pet(name="咪", species="cat", personality={}))["note"] == "已避開：咪（貓），並降低相似動物的排序"
