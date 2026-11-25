"""pets collection：schema、save hook 與虛擬欄位對應舊版 models/Pet.js。"""
import math
import re
from datetime import datetime, timezone

from app.core.schema import Arr, F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json

SPECIES = ("dog", "cat", "rabbit", "bird", "hamster", "guinea-pig", "other")
TRAITS = ("friendly", "shy", "playful", "calm", "energetic", "independent", "social", "protective", "gentle",
          "curious", "loyal", "active", "quiet")


def _now():
    return datetime.now(timezone.utc)


def _https_if_enabled(value, root):
    sp = root.get("sponsorship") or {}
    return not sp.get("enabled") or not value or bool(re.match(r"^https://.+", value))


SCHEMA = {
    "name": F("str", required="寵物名稱為必填項目", trim=True, maxlength=(50, "寵物名稱不能超過 50 個字元")),
    "species": F("str", required="動物種類為必填項目", enum=SPECIES, enum_msg="請選擇有效的動物種類"),
    "breed": F("str", required="品種為必填項目", trim=True, maxlength=(100, "品種名稱不能超過 100 個字元")),
    "gender": F("str", required="性別為必填項目", enum=("male", "female", "unknown"),
                enum_msg="性別必須是 male、female 或 unknown"),
    "age": {
        "value": F("num", required="年齡為必填項目", min=(0, "年齡不能為負數"), max=(30, "年齡不能超過 30 歲")),
        "unit": F("str", enum=("years", "months"), default="years"),
    },
    "ageCategory": F("str", enum=("young", "adult", "senior"), required=True),
    "size": F("str", required="體型為必填項目", enum=("small", "medium", "large", "extra-large"),
              enum_msg="請選擇有效的體型大小"),
    "weight": F("num", min=(0, "體重不能為負數"), max=(100, "體重不能超過 100 公斤")),
    "color": F("str", required="毛色為必填項目", trim=True, maxlength=(100, "毛色描述不能超過 100 個字元")),
    "healthStatus": {
        "vaccinated": F("bool", default=False),
        "spayed": F("bool", default=False),
        "microchipped": F("bool", default=False),
        "healthConditions": Arr({
            "condition": F("str", trim=True), "description": F("str", trim=True),
            "severity": F("str", enum=("mild", "moderate", "severe"), default="mild"),
        }),
        "lastVetVisit": F("date"),
        "medications": Arr({"name": F("str"), "dosage": F("str"), "frequency": F("str")}),
    },
    "personality": {
        "traits": Arr(F("str", enum=TRAITS)),
        "goodWith": {
            "children": F("bool", default=None),
            "otherPets": F("bool", default=None),
            "strangers": F("bool", default=None),
        },
        "activityLevel": F("str", enum=("low", "moderate", "high"), required=True),
        "specialNeeds": Arr(F("str", trim=True)),
    },
    "photos": Arr({
        "url": F("str", required=True), "filename": F("str", required=True),
        "isPrimary": F("bool", default=False),
        "caption": F("str", maxlength=(200, "照片說明不能超過 200 個字元")),
    }),
    "tags": Arr(F("str", trim=True, lowercase=True)),
    "shelterInfo": {
        "intakeDate": F("date", required="入所日期為必填項目", default=_now),
        "source": F("str", enum=("stray", "owner-surrender", "transfer", "born-in-shelter"), required="來源為必填項目"),
        "location": F("str", required="收容地點為必填項目", trim=True),
        "kennel": F("str", trim=True),
    },
    "adoptionStatus": F("str", enum=("available", "pending", "adopted", "hold", "not-available", "pending_review"),
                        enum_msg="請選擇有效的認養狀態", default="available"),
    "adoptionFee": F("num", min=(0, "認養費用不能為負數"), default=0),
    "description": F("str", required="動物描述為必填項目", trim=True, minlength=(50, "描述至少需要 50 個字元"),
                     maxlength=(1000, "描述不能超過 1000 個字元")),
    "story": F("str", maxlength=(2000, "故事不能超過 2000 個字元")),
    "externalLink": F("str", trim=True, match=(r"^https?://.+", "外部連結必須是有效的 URL (http:// 或 https://)")),
    "createdBy": F("oid", required=True),
    "updatedBy": F("oid"),
    "isActive": F("bool", default=True),
    "featured": F("bool", default=False),
    "views": F("num", default=0),
    "likes": Arr(F("oid")),
    "adoptionHistory": Arr(F("oid")),
    "sponsorship": {
        "enabled": F("bool", default=False),
        "externalLink": F("str", trim=True, validator=_https_if_enabled, validator_msg="助養連結必須使用 HTTPS 協定"),
        "clickCount": F("num", default=0, min=(0, "點擊次數不能為負數")),
        "lastClickedAt": F("date"),
    },
    "govData": {
        "animalId": F("str"), "subId": F("str"), "areaCode": F("str"), "shelterCode": F("str"),
        "foundPlace": F("str"), "foundDate": F("date"), "openDate": F("date"), "updateDate": F("date"),
        "closedDate": F("date"), "shelterName": F("str"), "shelterTel": F("str"), "shelterAddress": F("str"),
        "title": F("str"), "caption": F("str"), "remark": F("str"), "originalData": F("mixed"),
    },
}

STATUS_TAGS = {"adopted": "已認養", "available": "待認養", "pending": "審核中"}


def age_category(value, unit) -> str | None:
    try:
        years = float(value) / 12 if unit == "months" else float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(years):
        return None
    return "young" if years < 1 else "adult" if years < 7 else "senior"


def run_save_hooks(doc: dict) -> dict:
    """Mongoose pre('save')：年齡類別、唯一主照片、狀態標籤。"""
    age = doc.get("age") or {}
    if age.get("value") is not None:
        doc["ageCategory"] = age_category(age.get("value"), age.get("unit") or "years")
    photos = doc.get("photos") or []
    if photos:
        primaries = [p for p in photos if p.get("isPrimary")]
        if not primaries:
            photos[0]["isPrimary"] = True
        elif len(primaries) > 1:
            found = False
            for p in photos:
                if p.get("isPrimary"):
                    if found:
                        p["isPrimary"] = False
                    found = True
    tags = [t for t in (doc.get("tags") or []) if t not in STATUS_TAGS.values()]
    if doc.get("adoptionStatus") in STATUS_TAGS:
        tags.append(STATUS_TAGS[doc["adoptionStatus"]])
    doc["tags"] = tags
    return doc


def prepare_new_pet(data: dict) -> dict:
    """new Pet(data).save()：轉型、預設值、hook、驗證；失敗丟 MongooseError。"""
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    run_save_hooks(doc)
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(_dedupe(errors), "Pet")
    now = _now()
    doc.setdefault("createdAt", now)
    doc["updatedAt"] = now
    doc.setdefault("__v", 0)
    return doc


def validate_full(doc: dict) -> None:
    """pet.save() 對既有文件：hook 後整份驗證。"""
    run_save_hooks(doc)
    errors = validate(SCHEMA, doc)
    if errors:
        raise MongooseError(_dedupe(errors), "Pet")


def _dedupe(errors):
    seen, out = set(), []
    for path, msg in errors:
        if path not in seen:
            seen.add(path)
            out.append((path, msg))
    return out


def pet_json(doc: dict | None) -> dict | None:
    """toJSON({ virtuals: true })：ageDescription、primaryPhoto、daysInShelter。"""
    if doc is None:
        return None
    out = to_json(doc)
    age = doc.get("age") or {}
    value = age.get("value") if isinstance(age.get("value"), (int, float)) else None
    out["ageDescription"] = None if value is None else f"{value} {'歲' if (age.get('unit') or 'years') == 'years' else '個月'}"
    photos = out.get("photos") or []
    out["primaryPhoto"] = next((p for p in photos if p and p.get("isPrimary")), photos[0] if photos else None)
    intake = (doc.get("shelterInfo") or {}).get("intakeDate")
    if isinstance(intake, datetime):
        if intake.tzinfo is None:
            intake = intake.replace(tzinfo=timezone.utc)
        out["daysInShelter"] = math.ceil(abs((_now() - intake).total_seconds()) / 86400)
    else:
        out["daysInShelter"] = None
    return out


async def set_pet_status(pet_id, status: str) -> None:
    """改認養狀態並同步狀態標籤（舊版 pet.save() 的 hook）；用原子更新，避免舊資料驗證失敗。"""
    from app.db import get_db

    pet = await get_db().pets.find_one({"_id": pet_id}, {"tags": 1})
    if not pet:
        return
    tags = [t for t in (pet.get("tags") or []) if t not in STATUS_TAGS.values()]
    if status in STATUS_TAGS:
        tags.append(STATUS_TAGS[status])
    await get_db().pets.update_one({"_id": pet_id}, {"$set": {
        "adoptionStatus": status, "tags": tags, "updatedAt": _now()}})
