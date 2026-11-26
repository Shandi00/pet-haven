"""/api/matching：對應舊版 routes/matching.js。"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.ids import oid
from app.core.schema import Arr, F, cast, validate as schema_validate
from app.core.serialize import to_json
from app.db import get_db
from app.deps import current_user
from app.services.advanced_matching import batch_calculate_matches, calculate_match, find_best_matches
from app.services.top3 import build_top3

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/matching", tags=["Matching"])

LIFESTYLE = {
    "activityLevel": F("str", enum=("low", "medium", "high")),
    "availableTime": F("str", enum=("minimal", "moderate", "extensive")),
    "housingType": F("str", enum=("apartment", "condo", "townhouse", "house-no-yard", "house-with-yard")),
}
EXPERIENCE = {
    "petOwnershipExperience": F("str", enum=("none", "beginner", "intermediate", "experienced")),
    "previousPets": Arr({"species": F("str"), "yearsOwned": F("num")}),
    "trainingExperience": F("bool"),
}
ENVIRONMENT = {
    "hasChildren": F("bool"),
    "childrenAges": Arr(F("str", enum=("0-3", "4-6", "7-12", "13+"))),
    "hasOtherPets": F("bool"),
    "otherPets": Arr({"species": F("str"), "temperament": F("str")}),
    "noiseSensitive": F("bool"),
    "hasAllergies": F("bool"),
}


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _full_user(user: dict) -> dict:
    full = await get_db().users.find_one({"_id": user["_id"]}, {"password": 0})
    if not full:
        raise HTTPException(404, "找不到使用者資料")
    return full


def _match_json(match: dict) -> dict:
    return to_json(match)


@router.get("/analyze/{pet_id}", summary="單一寵物配對分析")
async def analyze(pet_id: str, user: dict = Depends(current_user)):
    pid = oid(pet_id)
    pet = await get_db().pets.find_one({"_id": pid}) if pid else None
    if not pet:
        raise HTTPException(404, "找不到指定的寵物")
    result = calculate_match(pet, await _full_user(user))
    return {"success": True, "data": to_json({
        "pet": {k: pet.get(k) for k in ("_id", "name", "species", "breed", "photos")}, **result})}


@router.get("/best-matches", summary="最佳配對")
async def best_matches(request: Request, user: dict = Depends(current_user)):
    q = request.query_params
    full = await _full_user(user)
    has_profiles = any(full.get(k) for k in ("recommendationProfile", "lifestyleProfile", "experienceProfile",
                                             "environmentProfile"))
    if not has_profiles:
        return {"success": True, "message": "請先完成個人檔案設定以獲得更精準的配對結果",
                "data": {"matches": [], "hasProfiles": False}}
    matches = await find_best_matches(full, _int(q.get("limit"), 10), _int(q.get("minScore"), 40))
    return {"success": True, "data": {"matches": to_json(matches), "hasProfiles": True, "count": len(matches)}}


@router.post("/batch-analyze", summary="批次配對分析")
async def batch_analyze(body: dict | None = None, user: dict = Depends(current_user)):
    pet_ids = (body or {}).get("petIds")
    if not isinstance(pet_ids, list) or not pet_ids:
        raise HTTPException(400, "請提供寵物 ID 列表")
    ids = [i for i in (oid(p) for p in pet_ids) if i]
    pets = await get_db().pets.find({"_id": {"$in": ids}, "adoptionStatus": "available",
                                     "isActive": True}).to_list(None)
    if not pets:
        return {"success": True, "data": {"matches": []}}
    matches = batch_calculate_matches(pets, await _full_user(user))
    return {"success": True, "data": {"matches": to_json(matches), "count": len(matches)}}


async def _update_profile(user: dict, field: str, schema: dict, data: dict, message: str) -> dict:
    errors: list = []
    casted = cast(schema, data, errors=errors)
    errors += schema_validate(schema, casted)
    if errors:
        raise HTTPException(400, "更新失敗：" + ", ".join(f"{p}: {m}" for p, m in errors))
    profile = {k: v for k, v in casted.items() if v is not None}
    profile["lastUpdated"] = datetime.now(timezone.utc)
    result = await get_db().users.update_one({"_id": user["_id"]}, {"$set": {
        field: profile, "updatedAt": datetime.now(timezone.utc)}})
    if result.matched_count == 0:
        raise HTTPException(404, "找不到使用者")
    return {"success": True, "message": message, "data": {field: to_json(profile)}}


@router.put("/profile/lifestyle", summary="更新生活方式檔案")
async def update_lifestyle(body: dict | None = None, user: dict = Depends(current_user)):
    b = body or {}
    return await _update_profile(user, "lifestyleProfile", LIFESTYLE, {
        k: b.get(k) for k in ("activityLevel", "availableTime", "housingType")}, "生活方式檔案更新成功")


@router.put("/profile/experience", summary="更新經驗檔案")
async def update_experience(body: dict | None = None, user: dict = Depends(current_user)):
    b = body or {}
    return await _update_profile(user, "experienceProfile", EXPERIENCE, {
        "petOwnershipExperience": b.get("petOwnershipExperience") or "none",
        "previousPets": b.get("previousPets") or [],
        "trainingExperience": b.get("trainingExperience") or False,
    }, "經驗檔案更新成功")


@router.put("/profile/environment", summary="更新環境檔案")
async def update_environment(body: dict | None = None, user: dict = Depends(current_user)):
    b = body or {}
    return await _update_profile(user, "environmentProfile", ENVIRONMENT, {
        "hasChildren": b.get("hasChildren") or False, "childrenAges": b.get("childrenAges") or [],
        "hasOtherPets": b.get("hasOtherPets") or False, "otherPets": b.get("otherPets") or [],
        "noiseSensitive": b.get("noiseSensitive") or False, "hasAllergies": b.get("hasAllergies") or False,
    }, "環境檔案更新成功")


@router.get("/profile", summary="取得配對檔案")
async def get_profile(user: dict = Depends(current_user)):
    full = await get_db().users.find_one({"_id": user["_id"]}, {
        "recommendationProfile": 1, "lifestyleProfile": 1, "experienceProfile": 1, "environmentProfile": 1})
    if not full:
        raise HTTPException(404, "找不到使用者")
    return {"success": True, "data": to_json({k: full.get(k) or {} for k in (
        "recommendationProfile", "lifestyleProfile", "experienceProfile", "environmentProfile")})}


@router.get("/top3", summary="Top 3 推薦與理由")
async def top3(user: dict = Depends(current_user)):
    return {"success": True, "data": await build_top3(await _full_user(user))}


@router.post("/feedback", summary="適合／不適合回饋；不適合時回傳重排後的 Top 3")
async def feedback(body: dict | None = None, user: dict = Depends(current_user)):
    b = body or {}
    verdict, pet_id = b.get("verdict"), b.get("petId")
    pid = oid(pet_id) if isinstance(pet_id, str) else None
    if verdict not in ("like", "dislike") or not pid:
        raise HTTPException(400, "參數錯誤")
    if not await get_db().pets.find_one({"_id": pid}, {"_id": 1}):
        raise HTTPException(404, "找不到指定的寵物")
    full = await _full_user(user)
    # 同一隻動物只保留最新一筆
    entries = [f for f in (full.get("matchFeedback") or []) if f.get("pet") != pid]
    entries.append({"pet": pid, "verdict": verdict, "createdAt": datetime.now(timezone.utc)})
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"matchFeedback": entries}})
    logger.info("matching feedback user=%s pet=%s verdict=%s", user["_id"], pid, verdict)
    if verdict == "like":
        return {"success": True, "data": {"recorded": True}}
    return {"success": True, "data": await build_top3({**full, "matchFeedback": entries})}


@router.delete("/feedback", summary="清除自己的回饋紀錄")
async def clear_feedback(user: dict = Depends(current_user)):
    full = await _full_user(user)
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"matchFeedback": []}})
    return {"success": True, "data": {"cleared": len(full.get("matchFeedback") or [])}}
