"""/api/data-import：對應舊版 routes/data-import.js（政府開放資料）。"""
import logging
import re
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Request

from app.core.logging import audit
from app.core.schema import MongooseError
from app.core.serialize import to_json
from app.db import get_db
from app.deps import current_user
from app.models.pet import prepare_new_pet
from app.responses import RawError
from app.services import gov_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data-import", tags=["Data Import"])


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _error(status: int, code: str, message: str, details: str | None = None) -> RawError:
    err = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return RawError(status, {"success": False, "error": err})


def _require_staff(user: dict) -> None:
    if user.get("role") not in ("admin", "shelter"):
        raise _error(403, "PERMISSION_DENIED", "您沒有權限執行此操作")


@router.get("/animal-recognition", summary="取得政府動物認領養資料（admin/shelter）")
async def animal_recognition(request: Request, user: dict = Depends(current_user)):
    _require_staff(user)
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 20)
    params: dict = {"UnitId": gov_data.ANIMAL_UNIT_ID, "$top": limit,
                    "$skip": _int(q.get("skip"), 0) or (page - 1) * limit}
    filters = []
    if q.get("county"):
        filters.append(f"contains(animal_place,'{gov_data.odata_literal(q['county'])}')")
    if q.get("status"):
        filters.append(f"contains(animal_status,'{gov_data.odata_literal(q['status'])}')")
    if filters:
        params["$filter"] = " and ".join(filters)
    try:
        animals = await gov_data.fetch(params)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("政府動物資料取得失敗：%s", e)
        raise _error(500, "API_ERROR", "獲取資料失敗", "政府資料平台無法連線或回應格式錯誤")
    return {"success": True, "data": {"animals": animals,
                                      "pagination": {"page": page, "limit": limit, "total": len(animals)}}}


def _description(a: dict) -> str:
    def v(key, default="未提供"):
        return a.get(key) or default

    sterilized = {"T": "是", "F": "否"}.get(a.get("animal_sterilization"), "未知")
    return f"""【收容資訊】
收容編號: {a.get('animal_subid') or a.get('animal_id')}
收容所: {v('shelter_name')}
收容地區: {v('animal_place')}
尋獲地: {v('animal_foundplace')}

【動物資訊】
年齡: {v('animal_age', '未知')}
毛色: {v('animal_colour', '未知')}
體型: {v('animal_bodytype', '未知')}
是否絕育: {sterilized}

【聯絡資訊】
電話: {v('shelter_tel')}
地址: {v('shelter_address')}

【其他說明】
{a.get('animal_caption') or ''}
{a.get('animal_remark') or ''}

開放認養時間: {v('animal_opendate')}
資料更新: {v('animal_update')}""".strip()[:1000]


def _date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("/", "-"))
    except ValueError:
        return None


def animal_to_pet(a: dict, user_id) -> dict:
    """政府資料轉成 Pet。舊版欄位（age 數字、photos 字串、缺 createdBy）存不進去，這裡改成符合 schema。"""
    animal_id = str(a.get("animal_subid") or a.get("animal_id"))
    photo = a.get("album_file")
    return {
        "name": (a.get("animal_title") or a.get("animal_subid") or "待命名")[:50],
        "species": gov_data.map_species(a.get("animal_kind")),
        "breed": a.get("animal_kind") or "混種",
        "age": gov_data.parse_age(a.get("animal_age")),
        "gender": gov_data.map_gender(a.get("animal_sex")),
        "size": gov_data.map_size(a.get("animal_bodytype")),
        "color": a.get("animal_colour") or "未知",
        "description": _description(a),
        "adoptionStatus": gov_data.map_status(a.get("animal_status")),
        "photos": [{"url": photo, "filename": photo.rsplit("/", 1)[-1] or "photo", "isPrimary": True}] if photo else [],
        "healthStatus": {"vaccinated": True, "spayed": a.get("animal_sterilization") == "T"},
        "personality": {"activityLevel": "moderate"},
        "shelterInfo": {
            "intakeDate": _date(a.get("animal_createtime")) or datetime.now(timezone.utc),
            "source": "stray",
            "location": a.get("shelter_name") or a.get("animal_place") or "政府開放資料",
            "kennel": animal_id,
        },
        "createdBy": user_id,
        "govData": {
            "animalId": animal_id, "subId": a.get("animal_subid"), "areaCode": _str(a.get("animal_area_pkid")),
            "shelterCode": _str(a.get("animal_shelter_pkid")), "foundPlace": a.get("animal_foundplace"),
            "foundDate": _date(a.get("animal_createtime")), "openDate": _date(a.get("animal_opendate")),
            "updateDate": _date(a.get("animal_update")), "closedDate": _date(a.get("animal_closeddate")),
            "shelterName": a.get("shelter_name"), "shelterTel": a.get("shelter_tel"),
            "shelterAddress": a.get("shelter_address"), "title": a.get("animal_title"),
            "caption": a.get("animal_caption"), "remark": a.get("animal_remark"), "originalData": a,
        },
    }


def _str(v):
    return None if v is None else str(v)


@router.post("/import-animals", summary="匯入選定的動物（admin/shelter）")
async def import_animals(body: dict | None = None, user: dict = Depends(current_user)):
    _require_staff(user)
    animals = (body or {}).get("animals")
    if not isinstance(animals, list) or not animals:
        raise _error(400, "INVALID_INPUT", "請提供要匯入的動物資料")
    result = {"imported": 0, "skipped": 0, "failed": 0, "errors": []}
    for a in animals:
        if not isinstance(a, dict) or not (a.get("animal_subid") or a.get("animal_id")):
            result["failed"] += 1
            result["errors"].append({"animalId": None, "error": "缺少 animal_id"})
            continue
        animal_id = str(a.get("animal_subid") or a.get("animal_id"))
        if await get_db().pets.find_one({"govData.animalId": animal_id}, {"_id": 1}):
            result["skipped"] += 1
            continue
        try:
            await get_db().pets.insert_one(prepare_new_pet(animal_to_pet(a, user["_id"])))
            result["imported"] += 1
        except MongooseError as e:
            result["failed"] += 1
            result["errors"].append({"animalId": a.get("animal_id"), "error": str(e)})
    audit("animals_imported", by=user["_id"], imported=result["imported"], skipped=result["skipped"],
          failed=result["failed"])
    return {"success": True, "data": result}


@router.get("/legal-pet-shops", summary="取得政府合法特定寵物業名單")
async def legal_pet_shops(request: Request, user: dict = Depends(current_user)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 20)
    params: dict = {"UnitId": gov_data.LICENSED_SHOP_UNIT_ID, "$top": limit, "$skip": (page - 1) * limit}
    if q.get("county"):
        params["$filter"] = f"contains(業者地址,'{gov_data.odata_literal(q['county'])}')"
    try:
        shops = await gov_data.fetch(params)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("合法寵物業資料取得失敗：%s", e)
        raise _error(500, "API_ERROR", "獲取寵物業資料失敗", "政府資料平台無法連線或回應格式錯誤")
    return {"success": True, "data": {"shops": shops,
                                      "pagination": {"page": page, "limit": limit, "total": len(shops)}}}


@router.get("/legal-pet-shops-db", summary="已匯入的合法寵物業（admin/shelter）")
async def legal_pet_shops_db(request: Request, user: dict = Depends(current_user)):
    _require_staff(user)
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 20)
    query: dict = {}
    if q.get("county"):
        query["address"] = re.compile(re.escape(q["county"]), re.I)
    total = await get_db().licensedshops.count_documents(query)
    shops = await get_db().licensedshops.find(query).sort("importedAt", -1).skip(max(page - 1, 0) * limit) \
        .limit(limit).to_list(None)
    return {"success": True, "data": {"shops": to_json(shops),
                                      "pagination": {"page": page, "limit": limit, "total": total}}}
