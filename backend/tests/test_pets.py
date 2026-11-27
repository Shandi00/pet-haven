import io

from bson import ObjectId

from tests.conftest import PET_DESC

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def form_fields(**extra):
    base = {
        "name": "阿福", "species": "dog", "breed": "柴犬", "gender": "male", "size": "medium", "color": "棕色",
        "description": PET_DESC, "ageCategory": "adult", "age[value]": "3", "age[unit]": "years",
        "location[city]": "台北", "healthStatus[vaccinated]": "true", "healthStatus[spayed]": "false",
        "healthStatus[microchipped]": "false", "shelterInfo[source]": "owner-surrender",
        "shelterInfo[location]": "台灣", "personality[activityLevel]": "moderate",
        "personalityTraits": '["friendly","calm"]',
    }
    base.update(extra)
    return base


def test_create_pet_multipart_like_frontend(api, make_user, sync_db):
    _, h = make_user("shelter")
    r = api.post("/api/pets", data=form_fields(),
                 files=[("photos", ("a.png", io.BytesIO(PNG), "image/png"))], headers=h)
    assert r.status_code == 201, r.text
    pet = r.json()["pet"]
    assert pet["age"] == {"value": 3, "unit": "years"} and pet["ageCategory"] == "adult"
    assert pet["healthStatus"]["vaccinated"] is True
    assert pet["personality"]["traits"] == ["friendly", "calm"]
    assert pet["photos"][0]["isPrimary"] is True and pet["photos"][0]["url"].startswith("/uploads/pets/pet-")
    assert pet["tags"] == ["待認養"] and pet["createdBy"]["username"]
    assert pet["primaryPhoto"]["url"] == pet["photos"][0]["url"] and pet["ageDescription"] == "3 歲"
    assert "location" not in pet  # strict：不在 schema 的欄位丟掉
    # 上傳的檔案可以透過 /uploads 讀到
    assert api.get(pet["photos"][0]["url"]).status_code == 200


def test_create_pet_validation_error_details(api, make_user):
    _, h = make_user()
    r = api.post("/api/pets", data=form_fields(description="太短"), headers=h)
    assert r.status_code == 400
    assert r.json()["error"] == "新增寵物失敗" and "描述至少需要 50 個字元" in r.json()["details"]


def test_create_pet_rejects_non_image(api, make_user):
    _, h = make_user()
    r = api.post("/api/pets", data=form_fields(), files=[("photos", ("a.txt", io.BytesIO(b"x"), "text/plain"))],
                 headers=h)
    assert r.status_code == 400


def test_list_filters_and_pagination(api, make_user, make_pet):
    owner, _ = make_user("shelter")
    make_pet(owner, name="狗一", species="dog")
    make_pet(owner, name="貓一", species="cat", featured=True)
    make_pet(owner, name="狗二", species="dog", adoptionStatus="adopted")
    r = api.get("/api/pets", params={"species": "dog"})
    body = r.json()
    assert r.status_code == 200 and [p["name"] for p in body["pets"]] == ["狗一"]
    assert body["pagination"]["totalItems"] == 1 and body["pagination"]["itemsPerPage"] == 12
    assert len(api.get("/api/pets", params={"showAll": "true"}).json()["pets"]) == 3
    assert [p["name"] for p in api.get("/api/pets/featured").json()] == ["貓一"]
    assert api.get("/api/pets", params={"search": "貓"}).json()["pets"][0]["name"] == "貓一"
    assert api.get("/api/pets", params={"search": "(("}).status_code == 200  # 不再因正規表示式回 500
    assert api.get("/api/pets", params={"species": "dragon"}).status_code == 400
    by_age = api.get("/api/pets", params={"sortBy": "age", "showAll": "true"}).json()["pets"]
    assert len(by_age) == 3 and "password" not in by_age[0]["createdBy"]


def test_get_pet_increments_views_and_404(api, make_user, make_pet, sync_db):
    owner, _ = make_user()
    pet = make_pet(owner)
    r = api.get(f"/api/pets/{pet['_id']}")
    assert r.status_code == 200 and r.json()["pet"]["name"] == "小白"
    assert sync_db.pets.find_one({"_id": pet["_id"]})["views"] == 1
    assert api.get(f"/api/pets/{ObjectId()}").json() == {"error": "找不到此寵物"}
    assert api.get("/api/pets/abc").status_code == 404


def test_update_permissions_and_partial_update(api, make_user, make_pet):
    owner, oh = make_user("shelter")
    other, xh = make_user("shelter")
    _, ah = make_user("admin")
    pet = make_pet(owner)
    r = api.put(f"/api/pets/{pet['_id']}", json={"name": "改名"}, headers=xh)
    assert r.status_code == 403  # 別的收容機構不能改
    r = api.put(f"/api/pets/{pet['_id']}", json={"personality": {"activityLevel": "high"}, "createdBy": str(other["_id"])},
                headers=oh)
    assert r.status_code == 200, r.text
    p = r.json()["pet"]
    assert p["personality"]["activityLevel"] == "high" and p["personality"]["traits"] == ["friendly"]
    assert p["createdBy"]["_id"] == str(owner["_id"])  # 不能透過 body 改擁有者
    assert api.put(f"/api/pets/{pet['_id']}", json={"species": "dragon"}, headers=ah).status_code == 400
    assert api.put(f"/api/pets/{pet['_id']}", data={"name": "管理員改"}, headers=ah).json()["pet"]["name"] == "管理員改"


def test_photos_to_delete_only_removes_own_photos(api, make_user, make_pet):
    owner, oh = make_user()
    pet = make_pet(owner, photos=[{"url": "/uploads/pets/a.png", "filename": "a.png"},
                                  {"url": "/uploads/pets/b.png", "filename": "b.png"}])
    r = api.put(f"/api/pets/{pet['_id']}", data={"photosToDelete": '["a.png", "../../app/main.py"]'}, headers=oh)
    assert r.status_code == 200
    assert [x["filename"] for x in r.json()["pet"]["photos"]] == ["b.png"]


def test_update_good_with_can_be_reset_to_unknown(api, make_user, make_pet):
    # 編輯表單（multipart）選「不確定」時送空字串，要存回 null，Top 3 才不會再排除這隻動物（T09）
    owner, oh = make_user()
    pet = make_pet(owner)
    url = f"/api/pets/{pet['_id']}"
    r = api.put(url, data={"personality[goodWith][children]": "false", "personality[goodWith][otherPets]": "true"},
                headers=oh)
    assert r.status_code == 200, r.text
    assert r.json()["pet"]["personality"]["goodWith"]["children"] is False
    r = api.put(url, data={"personality[goodWith][children]": "", "personality[goodWith][otherPets]": ""}, headers=oh)
    assert r.status_code == 200, r.text
    good_with = r.json()["pet"]["personality"]["goodWith"]
    assert good_with["children"] is None and good_with["otherPets"] is None
    assert r.json()["pet"]["personality"]["traits"] == ["friendly"]  # 其他個性欄位不受影響
    bad = api.put(url, data={"personality[goodWith][children]": "maybe"}, headers=oh)
    assert bad.status_code == 400


def test_like_delete_and_sponsorship(api, make_user, make_pet):
    owner, oh = make_user()
    _, uh = make_user()
    pet = make_pet(owner, sponsorship={"enabled": True, "externalLink": "https://donate.example.com"})
    r = api.post(f"/api/pets/{pet['_id']}/like", headers=uh)
    assert r.json() == {"message": "喜愛狀態已更新", "likesCount": 1, "isLiked": True}
    assert api.post(f"/api/pets/{pet['_id']}/like", headers=uh).json()["isLiked"] is False
    r = api.post(f"/api/pets/{pet['_id']}/sponsorship/click")
    assert r.json()["clickCount"] == 1 and r.json()["success"] is True
    assert api.post("/api/pets/xyz/sponsorship/click").status_code == 400
    assert api.delete(f"/api/pets/{pet['_id']}", headers=uh).status_code == 403
    assert api.delete(f"/api/pets/{pet['_id']}", headers=oh).json() == {"message": "寵物資料已刪除"}
    assert api.post(f"/api/pets/{pet['_id']}/like", headers=uh).status_code == 404


def test_my_pets_and_stats(api, make_user, make_pet):
    owner, oh = make_user()
    make_pet(owner)
    make_pet(owner, adoptionStatus="adopted")
    r = api.get("/api/pets/my-pets", headers=oh)
    assert r.json()["pagination"]["totalPets"] == 2 and "email" in r.json()["pets"][0]["createdBy"]
    assert api.get("/api/pets/my-pets").json() == {"error": "需要提供存取權杖"}
    stats = api.get("/api/pets/stats/overview").json()
    assert stats["available"] == 1 and stats["adopted"] == 1 and stats["bySpecies"][0]["count"] == 2
