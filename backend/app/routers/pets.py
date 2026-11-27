"""/api/pets：對應舊版 routes/pets.js，錯誤格式 { error, details }。"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pymongo import ReturnDocument

from app.core.forms import read_body
from app.core.logging import audit
from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import MongooseError, cast, flatten, validate as schema_validate
from app.core.uploads import save_images, upload_root
from app.core.validation import A, ANY, N, O, S, validate
from app.core.params import limit_param
from app.db import get_db
from app.deps import token_user_zh
from app.models.pet import SCHEMA, SPECIES, age_category, pet_json, prepare_new_pet
from app.responses import RawError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pets", tags=["Pets"])

USER_BRIEF = "username firstName lastName"
TF = ("true", "false")
QUERY_SCHEMA = O({
    "species": S(valid=SPECIES),
    "gender": S(valid=("male", "female", "unknown")),
    "size": S(valid=("small", "medium", "large")),
    "ageCategory": S(valid=("puppy", "young", "adult", "senior")),
    "location": S(),
    "featured": S(valid=TF),
    "search": S(max=100),
    "age": S(pattern=r"^\d+\s*(?:個月|月|歲)$"),
    "personality": ANY(),
    "vaccinated": S(valid=TF), "spayed": S(valid=TF), "microchipped": S(valid=TF),
    "goodWithChildren": S(valid=TF), "goodWithOtherPets": S(valid=TF),
    "daysInShelterMin": N(integer=True, min=0), "daysInShelterMax": N(integer=True, min=0),
    "createdBy": S(pattern=r"^[0-9a-fA-F]{24}$", msgs={"string.pattern.base": "無效的 ID 格式"}),
    "showAll": S(valid=TF),
    "sortBy": S(valid=("createdAt", "age", "name", "intakeDate")),
    "sortOrder": S(valid=("asc", "desc")),
    "page": N(integer=True, min=1, default=1),
    "limit": N(integer=True, min=1, max=100, default=12),
})
PERSONALITY_VALUES = ("friendly", "playful", "calm", "energetic", "independent", "social", "shy", "gentle",
                      "curious", "loyal", "protective", "affectionate", "needs-training")


def _err(status: int, error: str, **extra) -> RawError:
    return RawError(status, {"error": error, **extra})


def query_dict(request: Request) -> dict:
    """重複的 query 參數轉成陣列（同 Express qs）。"""
    out: dict = {}
    for k, v in request.query_params.multi_items():
        k = k[:-2] if k.endswith("[]") else k
        if k in out:
            out[k] = out[k] + [v] if isinstance(out[k], list) else [out[k], v]
        else:
            out[k] = v
    return out


def _int(value, default: int) -> int:
    m = re.match(r"^\s*-?\d+", str(value)) if value is not None else None
    return int(m.group()) if m else default


async def _json_pets(docs: list[dict], select: str = USER_BRIEF) -> list[dict]:
    await populate(docs, "createdBy", "users", select)
    return [pet_json(d) for d in docs]


async def _find_pet(pet_id: str) -> dict | None:
    pid = oid(pet_id)
    return await get_db().pets.find_one({"_id": pid}) if pid else None


@router.get("/my-pets", summary="我發布的寵物")
async def my_pets(request: Request, user: dict = Depends(token_user_zh)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), limit_param(q.get("limit"), 12)
    query = {"createdBy": user["_id"], "isActive": True}
    total = await get_db().pets.count_documents(query)
    total_pages = -(-total // limit) if limit else 0
    docs = await get_db().pets.find(query).sort(q.get("sortBy", "createdAt"),
                                                1 if q.get("sortOrder") == "asc" else -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    return {"pets": await _json_pets(docs, USER_BRIEF + " email"),
            "pagination": {"currentPage": page, "totalPages": total_pages, "totalPets": total,
                           "hasNextPage": page < total_pages, "hasPrevPage": page > 1}}


@router.get("", summary="寵物列表（篩選、分頁）")
async def list_pets(request: Request):
    p = validate(QUERY_SCHEMA, query_dict(request))
    query: dict = {"isActive": True}
    if "showAll" not in p:
        query["adoptionStatus"] = "available"
    if p.get("createdBy"):
        query["createdBy"] = oid(p["createdBy"])
    for key in ("species", "size", "ageCategory", "gender"):
        if p.get(key):
            query[key] = p[key]
    if p.get("age"):
        raw = str(p["age"]).strip()
        m = re.match(r"^(\d+)\s*(?:個月|月|m|歲|y)$", raw, re.I)
        if m:
            query["age.value"] = int(m.group(1))
            query["age.unit"] = "months" if ("月" in raw or "m" in raw.lower()) else "years"
    if p.get("location"):
        query["shelterInfo.location"] = re.compile(re.escape(p["location"]), re.I)
    if p.get("featured") == "true":
        query["featured"] = True
    if p.get("personality"):
        traits = p["personality"] if isinstance(p["personality"], list) else [p["personality"]]
        if isinstance(p["personality"], list) and any(t not in PERSONALITY_VALUES for t in traits):
            validate(O({"personality": A(S(valid=PERSONALITY_VALUES))}), {"personality": traits})
        query["personality.traits"] = {"$in": traits}
    for flag, path in (("vaccinated", "healthStatus.vaccinated"), ("spayed", "healthStatus.spayed"),
                       ("microchipped", "healthStatus.microchipped"),
                       ("goodWithChildren", "personality.goodWith.children"),
                       ("goodWithOtherPets", "personality.goodWith.otherPets")):
        if p.get(flag) == "true":
            query[path] = True
    if p.get("daysInShelterMin") or p.get("daysInShelterMax"):
        today = datetime.now(timezone.utc)
        rng = {}
        if p.get("daysInShelterMax"):
            rng["$gte"] = today - timedelta(days=p["daysInShelterMax"])
        if p.get("daysInShelterMin"):
            rng["$lte"] = today - timedelta(days=p["daysInShelterMin"])
        query["shelterInfo.intakeDate"] = rng
    if p.get("search"):
        rx = re.compile(re.escape(p["search"]), re.I)
        query["$or"] = [{"name": rx}, {"breed": rx}, {"description": rx}, {"color": rx}]

    page, limit = p["page"], p["limit"]
    sort_by = p.get("sortBy", "createdAt")
    order = -1 if p.get("sortOrder", "desc") == "desc" else 1
    skip = (page - 1) * limit
    if sort_by == "age":
        pipeline = [
            {"$match": query},
            {"$addFields": {"ageInMonths": {"$cond": [{"$eq": ["$age.unit", "months"]}, "$age.value",
                                                       {"$multiply": ["$age.value", 12]}]}}},
            {"$sort": {"ageInMonths": order}}, {"$skip": skip}, {"$limit": limit},
            {"$lookup": {"from": "users", "localField": "createdBy", "foreignField": "_id", "as": "createdBy"}},
            {"$unwind": {"path": "$createdBy", "preserveNullAndEmptyArrays": True}},
            {"$project": {"createdBy.password": 0}},
        ]
        docs = await (await get_db().pets.aggregate(pipeline)).to_list(None)
        pets = [pet_json(d) for d in docs]
    else:
        field = "shelterInfo.intakeDate" if sort_by == "intakeDate" else sort_by
        docs = await get_db().pets.find(query).sort(field, order).skip(skip).limit(limit).to_list(None)
        pets = await _json_pets(docs)
    total = await get_db().pets.count_documents(query)
    total_pages = -(-total // limit)
    return {"pets": pets, "pagination": {
        "currentPage": page, "totalPages": total_pages, "totalItems": total, "itemsPerPage": limit,
        "hasNextPage": page < total_pages, "hasPrevPage": page > 1}}


async def _featured(request: Request) -> list:
    limit = limit_param(request.query_params.get("limit"), 6)
    docs = await get_db().pets.find({"featured": True, "adoptionStatus": "available", "isActive": True}) \
        .sort("createdAt", -1).limit(limit).to_list(None)
    return await _json_pets(docs)


@router.get("/featured", summary="特色寵物")
async def featured(request: Request):
    return await _featured(request)


@router.get("/featured/list", summary="特色寵物（舊端點）")
async def featured_list(request: Request):
    return await _featured(request)


@router.get("/stats/overview", summary="寵物統計")
async def stats_overview():
    pets = get_db().pets
    by_species = await (await pets.aggregate([{"$match": {"isActive": True}},
                                              {"$group": {"_id": "$species", "count": {"$sum": 1}}}])).to_list(None)
    return {
        "available": await pets.count_documents({"adoptionStatus": "available", "isActive": True}),
        "adopted": await pets.count_documents({"adoptionStatus": "adopted"}),
        "pending": await pets.count_documents({"adoptionStatus": "pending"}),
        "bySpecies": by_species,
    }


@router.get("/{pet_id}", summary="寵物詳情")
async def get_pet(pet_id: str):
    pet = await _find_pet(pet_id)
    if not pet:
        raise _err(404, "找不到此寵物")
    await get_db().pets.update_one({"_id": pet["_id"]}, {"$inc": {"views": 1}})
    await populate(pet, "createdBy", "users", USER_BRIEF)
    await populate(pet, "likes", "users", USER_BRIEF)
    return {"pet": pet_json(pet)}


def _parse_int_like(value):
    """JS parseInt：取開頭的整數，失敗回 None。"""
    m = re.match(r"^\s*([+-]?\d+)", str(value))
    return int(m.group(1)) if m else None


def _normalize_age(body: dict, target: dict) -> None:
    age = body.get("age")
    raw_value = body.get("age[value]") or body.get("age.value") or (age.get("value") if isinstance(age, dict) else None)
    if raw_value is None and age is not None and not isinstance(age, dict):
        raw_value = age
    raw_unit = body.get("age[unit]") or body.get("age.unit") or (age.get("unit") if isinstance(age, dict) else None)
    if raw_value is not None or raw_unit is not None:
        new_age = dict(target["age"]) if isinstance(target.get("age"), dict) else {}
        parsed = _parse_int_like(raw_value) if raw_value is not None else None
        if parsed is not None:
            new_age["value"] = parsed
        if raw_unit:
            new_age["unit"] = str(raw_unit)
        target["age"] = new_age
    if not target.get("ageCategory") and isinstance(target.get("age"), dict) and target["age"].get("value") is not None:
        cat = age_category(target["age"]["value"], target["age"].get("unit") or "years")
        if cat:
            target["ageCategory"] = cat


def _json_field(body: dict, key: str):
    try:
        return json.loads(body[key])
    except (TypeError, ValueError):
        logger.warning("解析 %s JSON 失敗", key)
        return None


def _remove_files(files: list[dict]) -> None:
    for f in files:
        (upload_root() / "pets" / f["filename"]).unlink(missing_ok=True)


@router.post("", status_code=201, summary="新增寵物（multipart，照片欄位 photos）")
async def create_pet(request: Request, user: dict = Depends(token_user_zh)):
    body, files = await read_body(request, "photos")
    saved = await save_images(files, "pets", "pet")
    try:
        data = {**_strip_protected(body, user), "createdBy": user["_id"], "adoptionStatus": "available",
                "isActive": True}
        _normalize_age(body, data)
        if saved:
            data["photos"] = [{"url": f["path"], "filename": f["filename"], "isPrimary": i == 0,
                               "caption": body.get(f"photoCaption{i}") or ""} for i, f in enumerate(saved)]
        for key, parent, child in (("healthConditions", "healthStatus", "healthConditions"),
                                   ("medications", "healthStatus", "medications"),
                                   ("personalityTraits", "personality", "traits")):
            if body.get(key):
                parsed = _json_field(body, key)
                if parsed is not None:
                    data[parent] = {**(data.get(parent) if isinstance(data.get(parent), dict) else {}), child: parsed}
        doc = prepare_new_pet(data)
        doc["_id"] = (await get_db().pets.insert_one(doc)).inserted_id
    except MongooseError as e:
        _remove_files(saved)
        raise _err(400, "新增寵物失敗", details=str(e))
    await populate(doc, "createdBy", "users", USER_BRIEF)
    return {"message": "寵物資料新增成功", "pet": pet_json(doc)}


# 不讓使用者透過 body 改這些欄位（舊版直接 {...req.body}）。
# 照片只能由上傳產生（否則可寫入別人的檔名再用 photosToDelete 刪掉）；govData 只由政府資料匯入產生
_PROTECTED = ("_id", "createdBy", "likes", "views", "adoptionHistory", "createdAt", "updatedAt", "photos", "govData")
FEATURE_ROLES = ("shelter", "admin")


def _strip_protected(body: dict, user: dict) -> dict:
    data = {k: v for k, v in body.items() if k not in _PROTECTED}
    if user.get("role") not in FEATURE_ROLES:
        data.pop("featured", None)  # 首頁精選只給收容所與管理員設定（收容所編輯頁有這個選項）
    if isinstance(data.get("sponsorship"), dict):
        # 點擊次數只由 /sponsorship/click 累加
        data["sponsorship"] = {k: v for k, v in data["sponsorship"].items() if k != "clickCount"}
    return data


def _can_manage(user: dict, pet: dict) -> bool:
    # AGENTS.md：只能處理自己的動物，admin 例外（舊版連 shelter 都能改別人的動物）
    return user.get("role") == "admin" or same_id(pet.get("createdBy"), user["_id"])


@router.put("/{pet_id}", summary="更新寵物（multipart，新照片欄位 newPhotos）")
async def update_pet(pet_id: str, request: Request, user: dict = Depends(token_user_zh)):
    pet = await _find_pet(pet_id)
    if not pet:
        raise _err(404, "找不到此寵物")
    if not _can_manage(user, pet):
        raise _err(403, "您沒有權限編輯此寵物資訊")
    body, files = await read_body(request, "newPhotos")
    saved = await save_images(files, "pets", "pet")
    update = {**_strip_protected(body, user), "updatedBy": user["_id"]}
    _normalize_age(body, update)
    # 編輯表單的相處選「不確定」時送空字串（multipart 送不了 null），存回 null（未填）（T09）
    good_with = update["personality"].get("goodWith") if isinstance(update.get("personality"), dict) else None
    if isinstance(good_with, dict):
        for key in ("children", "otherPets"):
            if good_with.get(key) == "":
                good_with[key] = None
    if body.get("personalityTraits"):
        traits = _json_field(body, "personalityTraits")
        if traits is not None:
            update["personality"] = {**(update.get("personality") if isinstance(update.get("personality"), dict)
                                        else {}), "traits": traits}
    photos = None
    if saved:
        photos = list(pet.get("photos") or []) + [
            {"url": f["path"], "filename": f["filename"], "isPrimary": False, "caption": ""} for f in saved]
    delete_names: list[str] = []
    if body.get("photosToDelete"):
        parsed = _json_field(body, "photosToDelete")
        if isinstance(parsed, list):
            existing = {p.get("filename") for p in (pet.get("photos") or [])}
            # 只刪這隻寵物自己的照片，避免路徑穿越
            delete_names = [n for n in parsed if isinstance(n, str) and n in existing and Path(n).name == n]
            photos = [p for p in (photos if photos is not None else list(pet.get("photos") or []))
                      if p.get("filename") not in delete_names]
    if photos is not None:
        update["photos"] = photos
    errors: list = []
    casted = cast(SCHEMA, update, errors=errors)
    errors += schema_validate(SCHEMA, casted, partial=True)
    if errors:
        _remove_files(saved)
        raise _err(400, "更新寵物失敗", details="Validation failed: " + ", ".join(f"{p}: {m}" for p, m in errors))
    casted.pop("_id", None)
    sets = flatten({k: v for k, v in casted.items() if k != "photos"})
    if "photos" in casted:
        sets["photos"] = casted["photos"]
    sets["updatedAt"] = datetime.now(timezone.utc)
    updated = await get_db().pets.find_one_and_update({"_id": pet["_id"]}, {"$set": sets},
                                                      return_document=ReturnDocument.AFTER)
    for name in delete_names:
        (upload_root() / "pets" / name).unlink(missing_ok=True)
    await populate(updated, "createdBy", "users", USER_BRIEF)
    await populate(updated, "updatedBy", "users", USER_BRIEF)
    return {"message": "寵物資料更新成功", "pet": pet_json(updated)}


@router.post("/{pet_id}/like", summary="切換喜愛")
async def toggle_like(pet_id: str, user: dict = Depends(token_user_zh)):
    pet = await _find_pet(pet_id)
    if not pet or not pet.get("isActive", True):
        raise _err(404, "找不到此寵物")
    liked = any(same_id(x, user["_id"]) for x in pet.get("likes") or [])
    op = {"$pull": {"likes": user["_id"]}} if liked else {"$addToSet": {"likes": user["_id"]}}
    updated = await get_db().pets.find_one_and_update({"_id": pet["_id"]}, op, return_document=ReturnDocument.AFTER)
    likes = updated.get("likes") or []
    return {"message": "喜愛狀態已更新", "likesCount": len(likes),
            "isLiked": any(same_id(x, user["_id"]) for x in likes)}


@router.delete("/{pet_id}", summary="刪除寵物（軟刪除）")
async def delete_pet(pet_id: str, user: dict = Depends(token_user_zh)):
    pet = await _find_pet(pet_id)
    if not pet:
        raise _err(404, "找不到此寵物")
    if not _can_manage(user, pet):
        raise _err(403, "您沒有權限刪除此寵物資訊")
    await get_db().pets.update_one({"_id": pet["_id"]}, {"$set": {
        "isActive": False, "updatedBy": user["_id"], "updatedAt": datetime.now(timezone.utc)}})
    audit("pet_deleted", by=user["_id"], pet=pet["_id"])
    return {"message": "寵物資料已刪除"}


@router.post("/{pet_id}/sponsorship/click", summary="記錄助養連結點擊")
async def sponsorship_click(pet_id: str):
    if not re.fullmatch(r"[0-9a-fA-F]{24}", pet_id):
        raise _err(400, "無效的寵物 ID")
    pet = await _find_pet(pet_id)
    if not pet:
        raise _err(404, "找不到該寵物")
    sp = pet.get("sponsorship") or {}
    if not sp.get("enabled"):
        raise _err(400, "此寵物未啟用助養功能")
    if not sp.get("externalLink"):
        raise _err(400, "未設定助養連結")
    updated = await get_db().pets.find_one_and_update(
        {"_id": pet["_id"]},
        {"$inc": {"sponsorship.clickCount": 1}, "$set": {"sponsorship.lastClickedAt": datetime.now(timezone.utc)}},
        return_document=ReturnDocument.AFTER)
    count = updated["sponsorship"]["clickCount"]
    logger.info("助養點擊記錄 - Pet ID: %s, 總點擊數: %s", pet_id, count)
    return {"success": True, "clickCount": count, "message": "已記錄助養點擊"}
