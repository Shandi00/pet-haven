from bson import ObjectId

from app.services.review_insights import checks
from tests.test_adoptions import apply, setup_flow


def pet(**personality):
    return {"name": "小白", "species": "dog", "personality": {"activityLevel": "moderate", **personality}}


def application(**details):
    return {"applicantDetails": details}


def levels(result):
    return [(c["level"], c["message"]) for c in result]


def test_no_checks_when_nothing_conflicts():
    assert checks(application(householdMembers={"children": 0}), pet(goodWith={"children": False})) == []


def test_children_against_good_with():
    kids = application(householdMembers={"children": 2})
    assert levels(checks(kids, pet(goodWith={"children": False}))) == [
        ("warning", "申請表填有 2 位兒童，小白標示不適合有小孩的家庭")]
    assert checks(kids, pet(goodWith={"children": None}))[0]["level"] == "info"
    assert checks(kids, pet(goodWith={"children": True})) == []


def test_current_pets_against_good_with():
    has_pets = application(petExperience={"currentPets": [{"species": "cat"}]})
    assert levels(checks(has_pets, pet(goodWith={"otherPets": False}))) == [
        ("warning", "申請人目前養了 1 隻寵物，小白標示不適合與其他寵物相處")]
    assert checks(has_pets, pet(goodWith={}))[0]["level"] == "info"  # 沒填相處條件


def test_allergies_are_a_warning_for_cats_only():
    allergic = application(allergies={"hasAllergies": True})
    cat = {**pet(), "species": "cat"}
    assert levels(checks(allergic, cat)) == [("warning", "申請人表示家中有人過敏，請確認是否對貓過敏")]
    assert levels(checks(allergic, pet())) == [("info", "申請人表示家中有人過敏，請確認是否對狗過敏")]


def test_rented_without_landlord_approval():
    assert levels(checks(application(isRented=True, landlordApproval=False), pet())) == [
        ("warning", "申請人租屋，申請表填寫尚未取得房東同意")]
    assert checks(application(isRented=True, landlordApproval=True), pet()) == []


def test_high_activity_in_apartment_without_yard():
    flat = application(housingType="apartment", hasYard=False)
    assert levels(checks(flat, pet(activityLevel="high"))) == [
        ("info", "小白活動量高，申請人住公寓且沒有院子，請確認每天的運動安排")]
    assert checks(application(housingType="apartment", hasYard=True), pet(activityLevel="high")) == []


def test_special_needs_are_quoted_and_warnings_come_first():
    result = checks(application(householdMembers={"children": 1}),
                    pet(goodWith={"children": False}, specialNeeds=["每天需要服藥", "怕打雷"]))
    assert [c["level"] for c in result] == ["warning", "info"]
    assert result[1]["message"] == "小白有特殊照顧需求：每天需要服藥、怕打雷，請確認申請人了解"


# --- API ---

def test_owner_sees_review_insights(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, p = setup_flow(make_user, make_pet)
    aid = apply(api, p, ah).json()["data"]["adoption"]["_id"]
    # 同一隻動物另有一份進行中的申請（動物進入審核後 API 不收新申請，直接寫入）；
    # 申請人另外申請了別隻、也曾完成過一次認養；已拒絕的不算進行中
    sync_db.adoptions.insert_many([{"pet": p["_id"], "applicant": ObjectId(), "status": "under-review"},
                                   {"pet": p["_id"], "applicant": ObjectId(), "status": "rejected"}])
    second_pet = make_pet(owner, name="阿福")
    assert apply(api, second_pet, ah).status_code == 201
    sync_db.adoptions.insert_one({"pet": ObjectId(), "applicant": applicant["_id"], "status": "completed"})

    data = api.get(f"/api/adoptions/{aid}/details", headers=oh).json()["data"]
    insights = data["reviewInsights"]
    assert insights["pet"] == {"otherActiveApplications": 1}
    assert insights["applicant"] == {"otherActiveApplications": 1, "completedAdoptions": 1,
                                     "matchingProfileFilled": False}
    assert insights["match"] is None and insights["source"] == "rule"
    assert isinstance(insights["checks"], list)


def test_match_score_when_applicant_filled_profile(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, p = setup_flow(make_user, make_pet)
    sync_db.users.update_one({"_id": applicant["_id"]}, {"$set": {"lifestyleProfile": {"activityLevel": "moderate"}}})
    aid = apply(api, p, ah).json()["data"]["adoption"]["_id"]
    match = api.get(f"/api/adoptions/{aid}/details", headers=oh).json()["data"]["reviewInsights"]["match"]
    assert 0 <= match["score"] <= 100 and match["label"]
    assert set(match["breakdown"]) == {"compatibility", "lifestyle", "experience", "environment"}


def test_applicant_and_other_shelters_do_not_get_insights(api, make_user, make_pet):
    owner, oh, applicant, ah, xh, p = setup_flow(make_user, make_pet)
    aid = apply(api, p, ah).json()["data"]["adoption"]["_id"]
    mine = api.get(f"/api/adoptions/{aid}/details", headers=ah)
    assert mine.status_code == 200 and "reviewInsights" not in mine.json()["data"]
    assert api.get(f"/api/adoptions/{aid}/details", headers=xh).status_code == 403
