from bson import ObjectId

APPLY = {
    "age": "30", "occupation": "工程師", "noPetExperience": True, "housingType": "apartment",
    "housingOwnership": "owned", "address": "台北市", "householdMembers": 2, "veterinaryCare": "定期健檢",
    "adoptionReason": "想給牠一個家", "emergencyContactName": "王小明", "emergencyContactPhone": "0912345678",
    "dailyCareTime": "3-5",
}


def setup_flow(make_user, make_pet):
    owner, oh = make_user("shelter")
    applicant, ah = make_user("user")
    other, xh = make_user("shelter")
    pet = make_pet(owner)
    return owner, oh, applicant, ah, xh, pet


def apply(api, pet, ah, **extra):
    return api.post(f"/api/adoptions/apply/{pet['_id']}", json={**APPLY, **extra}, headers=ah)


def test_main_line_apply_review_complete(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    r = apply(api, pet, ah)
    assert r.status_code == 201, r.text
    adoption = r.json()["data"]["adoption"]
    aid = adoption["_id"]
    assert adoption["applicationId"].startswith("AD") and adoption["status"] == "pending"
    assert adoption["applicantDetails"]["carePlan"]["dailyAvailableHours"] == 4
    assert adoption["pet"]["name"] == "小白" and adoption["applicant"]["username"]
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "pending"
    assert sync_db.notifications.find_one({"recipient": owner["_id"], "type": "adoption_received"})

    # 別的收容機構不能審核
    r = api.post(f"/api/adoptions/{aid}/review", json={"decision": "approved"}, headers=xh)
    assert r.status_code == 403
    r = api.post(f"/api/adoptions/{aid}/review", json={"decision": "approved"}, headers=oh)
    assert r.status_code == 200 and r.json()["adoption"]["status"] == "approved"
    assert sync_db.notifications.find_one({"recipient": applicant["_id"], "type": "adoption_approved"})
    assert api.post(f"/api/adoptions/{aid}/review", json={"decision": "approved"}, headers=oh).status_code == 400

    assert api.post(f"/api/adoptions/{aid}/complete", json={}, headers=xh).status_code == 403
    r = api.post(f"/api/adoptions/{aid}/complete", json={}, headers=oh)
    assert r.status_code == 200 and r.json()["adoption"]["status"] == "completed"
    p = sync_db.pets.find_one({"_id": pet["_id"]})
    assert p["adoptionStatus"] == "adopted" and "已認養" in p["tags"]
    assert sync_db.notifications.find_one({"recipient": applicant["_id"], "type": "adoption_completed"})
    assert ObjectId(aid) in sync_db.users.find_one({"_id": applicant["_id"]})["adoptionHistory"]

    mine = api.get("/api/adoptions/my-applications", headers=ah).json()
    assert mine["applications"][0]["status"] == "completed" and "reviewNotes" not in mine["applications"][0]


def test_leftover_application_on_adopted_pet_keeps_pet_adopted(api, make_user, make_pet, sync_db):
    # 動物已被認養，卻還留著一份待審核的舊申請：不能核准；拒絕時只關閉申請，動物不能變回可認養
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    sync_db.pets.update_one({"_id": pet["_id"]}, {"$set": {"adoptionStatus": "adopted"}})
    url = f"/api/adoptions/{aid}/review"
    r = api.post(url, json={"decision": "approved"}, headers=oh)
    assert r.status_code == 400 and r.json()["error"] == "這隻動物已被認養，不能再核准申請"
    assert sync_db.adoptions.find_one({"_id": ObjectId(aid)})["status"] == "pending"
    r = api.post(url, json={"decision": "rejected", "reason": "已被認養"}, headers=oh)
    assert r.status_code == 200 and r.json()["adoption"]["status"] == "rejected"
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "adopted"

    # 舊的改狀態 API 也一樣
    aid2 = sync_db.adoptions.insert_one({"pet": pet["_id"], "applicant": applicant["_id"], "status": "pending",
                                         "applicationId": "AD-LEFTOVER"}).inserted_id
    r = api.put(f"/api/adoptions/{aid2}/status", json={"status": "approved"}, headers=oh)
    assert r.status_code == 400 and r.json()["error"] == "這隻動物已被認養，不能再核准申請"
    assert api.put(f"/api/adoptions/{aid2}/status", json={"status": "rejected"}, headers=oh).status_code == 200
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "adopted"


def test_complete_closes_other_active_applications_and_notifies(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    assert api.post(f"/api/adoptions/{aid}/review", json={"decision": "approved"}, headers=oh).status_code == 200
    # 同一隻動物留下的其他申請：進行中的要結束，已經結束的不動
    other_a, other_b, done = ObjectId(), ObjectId(), ObjectId()
    ids = sync_db.adoptions.insert_many([
        {"pet": pet["_id"], "applicant": other_a, "status": "pending"},
        {"pet": pet["_id"], "applicant": other_b, "status": "under-review"},
        {"pet": pet["_id"], "applicant": done, "status": "cancelled"},
    ]).inserted_ids
    r = api.post(f"/api/adoptions/{aid}/complete", json={}, headers=oh)
    assert r.status_code == 200 and r.json()["closedApplications"] == 2
    closed = [sync_db.adoptions.find_one({"_id": i}) for i in ids]
    assert [a["status"] for a in closed] == ["rejected", "rejected", "cancelled"]
    assert closed[0]["reviewDecision"]["reason"] == "這隻動物已由其他認養人完成認養"
    for who in (other_a, other_b):
        note = sync_db.notifications.find_one({"recipient": who, "type": "adoption_rejected"})
        assert note["title"] == "認養申請已結束" and "已經找到家了" in note["content"]
    assert not sync_db.notifications.find_one({"recipient": done})
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "adopted"


def test_status_api_completed_also_closes_others(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    other = sync_db.adoptions.insert_one({"pet": pet["_id"], "applicant": ObjectId(), "status": "pending"}).inserted_id
    assert api.put(f"/api/adoptions/{aid}/status", json={"status": "completed"}, headers=oh).status_code == 200
    assert sync_db.adoptions.find_one({"_id": other})["status"] == "rejected"


def test_reject_keeps_pet_pending_while_other_applications_are_active(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    sync_db.adoptions.insert_one({"pet": pet["_id"], "applicant": ObjectId(), "status": "approved"})
    r = api.post(f"/api/adoptions/{aid}/review", json={"decision": "rejected", "reason": "已有其他認養人"}, headers=oh)
    assert r.status_code == 200
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "pending"


def test_reject_reason_is_validated_and_sent_to_applicant(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    url = f"/api/adoptions/{aid}/review"
    for bad in ("字" * 501, 123, ["x"]):
        r = api.post(url, json={"decision": "rejected", "reason": bad}, headers=oh)
        assert r.status_code == 400 and r.json() == {"success": False, "error": "審核原因最多 500 字"}
    assert sync_db.adoptions.find_one({"_id": ObjectId(aid)})["status"] == "pending"  # 沒有被改動
    r = api.post(url, json={"decision": "rejected", "reason": "照顧時間不足"}, headers=oh)
    assert r.status_code == 200 and r.json()["adoption"]["status"] == "rejected"
    note = sync_db.notifications.find_one({"recipient": applicant["_id"], "type": "adoption_rejected"})
    assert "原因：照顧時間不足" in note["content"]


def test_apply_validation_and_duplicates(api, make_user, make_pet):
    _, _, _, ah, _, pet = setup_flow(make_user, make_pet)
    r = api.post(f"/api/adoptions/apply/{pet['_id']}", json={**APPLY, "occupation": ""}, headers=ah)
    assert r.status_code == 400 and r.json()["details"] == {"missing": ["occupation"]}
    r = apply(api, pet, ah, previousPetExperience=True)
    assert r.json()["message"] == "養寵經驗欄位衝突"
    r = apply(api, pet, ah, emergencyContactPhone="123")
    assert r.status_code == 400 and "請輸入有效的台灣手機號碼格式" in r.json()["error"]
    assert apply(api, pet, ah).status_code == 201
    # 寵物已變成 pending，不能再申請
    assert apply(api, pet, ah).json()["message"] == "此寵物目前無法申請認養"
    assert api.post("/api/adoptions/apply/abc", json=APPLY, headers=ah).status_code == 400


def test_status_update_permissions_and_invalid_ids(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    assert api.put(f"/api/adoptions/{aid}/status", json={"status": "approved"}, headers=xh).json() == \
        {"error": "只能處理自己動物的申請"}
    r = api.put(f"/api/adoptions/{aid}/status", json={"status": "rejected", "reason": "不適合"}, headers=oh)
    assert r.status_code == 200 and r.json()["adoption"]["reviewDecision"]["decision"] == "rejected"
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "available"
    assert api.put(f"/api/adoptions/{aid}/status", json={"status": "weird"}, headers=oh).status_code == 400
    # 不合法的 id 回 404，不能 500
    assert api.put("/api/adoptions/abc/status", json={"status": "approved"}, headers=oh).status_code == 404
    assert api.post(f"/api/adoptions/{ObjectId()}/complete", headers=oh).status_code == 404


def test_deleted_pet_returns_404(api, make_user, make_pet, sync_db):
    _, oh, _, ah, _, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    sync_db.pets.delete_one({"_id": pet["_id"]})
    assert api.put(f"/api/adoptions/{aid}/status", json={"status": "approved"}, headers=oh).status_code == 404


def test_admin_can_manage_any(api, make_user, make_pet):
    _, _, _, ah, _, pet = setup_flow(make_user, make_pet)
    _, admin_h = make_user("admin")
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    r = api.post(f"/api/adoptions/{aid}/review", json={"decision": "approved"}, headers=admin_h)
    assert r.status_code == 200
    assert api.get("/api/adoptions/admin/stats", headers=admin_h).status_code == 200
    assert api.get("/api/adoptions/admin/all", headers=ah).json() == {"error": "需要管理員權限"}


def test_cancel_notes_details(api, make_user, make_pet, sync_db):
    owner, oh, applicant, ah, xh, pet = setup_flow(make_user, make_pet)
    aid = apply(api, pet, ah).json()["data"]["adoption"]["_id"]
    r = api.post(f"/api/adoptions/{aid}/notes", json={"note": "已電話聯絡"}, headers=oh)
    assert r.status_code == 200 and r.json()["reviewNotes"][0]["reviewer"]["role"] == "shelter"
    assert api.post(f"/api/adoptions/{aid}/notes", json={"note": "x"}, headers=xh).status_code == 403

    owner_view = api.get(f"/api/adoptions/{aid}/details", headers=oh).json()["data"]
    applicant_view = api.get(f"/api/adoptions/{aid}/details", headers=ah).json()["data"]
    assert owner_view["reviewNotes"] and "reviewNotes" not in applicant_view
    assert api.get(f"/api/adoptions/{aid}/details", headers=xh).status_code == 403
    assert api.get(f"/api/adoptions/{aid}", headers=ah).json()["rawSubmission"]["occupation"] == "工程師"

    received = api.get("/api/adoptions/my-pets-applications", headers=oh).json()["data"]
    assert received["pagination"]["totalItems"] == 1

    assert api.put(f"/api/adoptions/{aid}/cancel", headers=oh).status_code == 403
    r = api.put(f"/api/adoptions/{aid}/cancel", headers=ah)
    assert r.status_code == 200 and r.json()["adoption"]["status"] == "cancelled"
    assert sync_db.pets.find_one({"_id": pet["_id"]})["adoptionStatus"] == "available"
    assert sync_db.notifications.find_one({"recipient": owner["_id"], "type": "adoption_cancelled"})
    assert api.put(f"/api/adoptions/{aid}/cancel", headers=ah).status_code == 400


def test_legacy_create_endpoint(api, make_user, make_pet):
    _, _, _, ah, _, pet = setup_flow(make_user, make_pet)
    body = {"petId": str(pet["_id"]), "reason": "我很喜歡這隻狗狗想要照顧牠",
            "emergencyContact": {"name": "王", "phone": "0912345678"}}
    r = api.post("/api/adoptions", json=body, headers=ah)
    assert r.status_code == 201, r.text
    assert api.post("/api/adoptions", json={"reason": "短"}, headers=ah).status_code == 400


def test_owner_cannot_apply_for_own_pet(api, make_user, make_pet, sync_db):
    owner, oh, _, _, _, pet = setup_flow(make_user, make_pet)
    r = apply(api, pet, oh)
    assert r.status_code == 400 and r.json()["message"] == "不能申請認養自己刊登的動物"
    legacy = {"petId": str(pet["_id"]), "reason": "我很喜歡這隻狗狗想要照顧牠",
              "emergencyContact": {"name": "王", "phone": "0912345678"}}
    r = api.post("/api/adoptions", json=legacy, headers=oh)
    assert r.status_code == 400 and r.json()["error"] == "不能申請認養自己刊登的動物"
    assert sync_db.adoptions.count_documents({}) == 0
