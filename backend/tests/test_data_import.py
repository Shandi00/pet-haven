from app.services import gov_data
from scripts import create_admin, import_licensed_shops

ANIMAL = {
    "animal_id": 12345, "animal_subid": "TPE-001", "animal_kind": "狗", "animal_sex": "M",
    "animal_bodytype": "SMALL", "animal_colour": "黑色", "animal_age": "CHILD", "animal_status": "OPEN",
    "animal_place": "臺北市動物之家", "shelter_name": "臺北市動物之家", "shelter_tel": "02-0000",
    "animal_createtime": "2024/01/15", "album_file": "https://example.org/a.jpg", "animal_sterilization": "F",
}


def test_mapping_helpers():
    assert gov_data.map_species("貓") == "cat" and gov_data.map_species(None) == "other"
    assert gov_data.map_gender("F") == "female" and gov_data.map_size("大型") == "large"
    assert gov_data.map_status("已認養") == "adopted" and gov_data.map_status("死亡") == "not-available"
    assert gov_data.parse_age("3個月") == {"value": 3, "unit": "months"}
    assert gov_data.odata_literal("a'b") == "a''b"


def test_fetch_filter_is_escaped_and_staff_only(api, make_user, monkeypatch):
    calls = []

    async def fake_fetch(params, timeout=30):
        calls.append(params)
        return [ANIMAL]

    monkeypatch.setattr(gov_data, "fetch", fake_fetch)
    _, uh = make_user()
    _, sh = make_user("shelter")
    assert api.get("/api/data-import/animal-recognition", headers=uh).status_code == 403
    r = api.get("/api/data-import/animal-recognition", params={"county": "臺北' or 1"}, headers=sh).json()
    assert r["data"]["animals"][0]["animal_id"] == 12345
    assert calls[0]["$filter"] == "contains(animal_place,'臺北'' or 1')"
    assert api.get("/api/data-import/legal-pet-shops", headers=uh).json()["data"]["shops"]


def test_import_animals_creates_valid_pets_and_skips_duplicates(api, make_user, sync_db):
    _, sh = make_user("shelter")
    r = api.post("/api/data-import/import-animals", json={"animals": [ANIMAL, {"x": 1}]}, headers=sh).json()
    assert r["data"]["imported"] == 1 and r["data"]["failed"] == 1, r
    pet = sync_db.pets.find_one({"govData.animalId": "TPE-001"})
    assert pet["species"] == "dog" and pet["ageCategory"] == "young" and pet["photos"][0]["url"].endswith("a.jpg")
    assert api.post("/api/data-import/import-animals", json={"animals": [ANIMAL]}, headers=sh).json()["data"][
        "skipped"] == 1
    assert api.get("/api/stats").json()["data"]["importedPets"] == 1
    assert api.post("/api/data-import/import-animals", json={"animals": []}, headers=sh).status_code == 400


def test_licensed_shops_script_and_db_route(api, make_user):
    rec = import_licensed_shops.map_record({"ID": 9, "legalname": "好寵物店", "legaladdress": "台北市中正區",
                                            "validdate": "2025/01/02 上午", "rank_flag_1": "A"})
    assert rec["govId"] == "9" and rec["validDate"].year == 2025 and rec["rankFlags"] == ["A"]
    assert api.portal.call(import_licensed_shops.upsert, [rec, rec]) == 2
    _, sh = make_user("shelter")
    r = api.get("/api/data-import/legal-pet-shops-db", params={"county": "台北"}, headers=sh).json()
    assert r["data"]["pagination"]["total"] == 1 and r["data"]["shops"][0]["name"] == "好寵物店"


def test_create_admin_script(api, sync_db):
    created, _ = api.portal.call(create_admin.create_admin, "Boss@Example.com", "boss", "Str0ngPass!")
    again, _ = api.portal.call(create_admin.create_admin, "boss@example.com", "boss", "x")
    assert created and not again
    r = api.post("/api/auth/login", json={"email": "boss@example.com", "password": "Str0ngPass!"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
