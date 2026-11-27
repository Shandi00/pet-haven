"""/api/adoptions：對應舊版 routes/adoptions.js。

權限依 T07：審核、改狀態、完成、備註由「寵物擁有者或 admin」處理（舊版是只限 admin，或任何 shelter 都能操作）。
"""
import logging
import math
import re
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, Request

from app.core.logging import audit
from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import MongooseError, cast
from app.core.serialize import to_json
from app.core.validation import A, ANY, B, N, O, S, validate
from app.db import get_db
from app.deps import token_user_zh
from app.models.adoption import SCHEMA as ADOPTION_SCHEMA
from app.models.adoption import (ACTIVE_STATUSES, DEFAULT_PROJECTION, STATUSES, adoption_json, check_adoption,
                                 prepare_new_adoption)
from app.models.message import prepare_new_message
from app.models.notification import notify_owner_and_shelters, safe_notify
from app.models.pet import pet_json, set_pet_status
from app.responses import RawError
from app.services import review_insights

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/adoptions", tags=["Adoptions"])

_E = ("",)
CREATE_SCHEMA = O({
    "petId": S(required=True, pattern=r"^[0-9a-fA-F]{24}$",
               msgs={"any.required": "寵物 ID 為必填欄位", "string.pattern.base": "無效的 ID 格式"}),
    "reason": S(required=True, min=10, max=1000, msgs={"string.min": "請簡述領養原因", "any.required": "領養原因為必填欄位"}),
    "experience": S(max=500, allow=_E),
    "applicantDetails": O({
        "housingType": S(valid=("apartment", "house", "condo", "other")),
        "hasYard": B(),
        "housingOwnership": S(valid=("owned", "rented", "other")),
        "landlordApproval": B(),
        "householdMembers": O({"adults": N(integer=True, min=0), "children": N(integer=True, min=0),
                               "childrenAges": A(N(integer=True, min=0))}),
        "allergies": O({"hasAllergies": B(), "allergyDetails": S(allow=_E)}),
        "petExperience": O({"noExperience": B(), "hasPrevious": B(), "previousPets": A(O()), "currentPets": A(O())}),
        "workSchedule": O({"employmentStatus": S(), "hoursAway": N(), "whoWillCare": S(allow=_E)}),
        "veterinarianInfo": O({"hasVet": B(), "vetName": S(allow=_E), "vetPhone": S(allow=_E),
                               "vetAddress": S(allow=_E)}),
        "address": S(allow=_E),
    }),
    "personalInfo": O({"age": N(integer=True, min=0), "occupation": S(max=200, allow=_E)}),
    "emergencyContact": O({"name": S(allow=_E), "relationship": S(allow=_E), "phone": S(allow=_E),
                           "email": S(email=True, allow=_E)}),
    "carePlan": O({k: S(allow=_E) for k in (
        "veterinaryCare", "exercisePlan", "dailyCareTime", "financialCapability", "otherNotes",
        "adoptionExpectations", "commitmentStatement", "emergencyContactName", "emergencyContactPhone")}
        | {"adoptionReason": ANY()}),
    "contactInfo": O({"phone": S(pattern=r"^09\d{8}$", msgs={"string.pattern.base": "手機號碼格式不正確 (例: 0912345678)"}),
                      "email": S(email=True, allow=_E),
                      "preferredContactMethod": S(valid=("phone", "email", "both"))}),
    "livingEnvironment": O({"type": S(valid=("apartment", "house", "condo", "other")), "hasYard": B(),
                            "familyMembers": N(integer=True, min=0)}),
    "age": ANY(), "occupation": S(allow=_E), "housingType": S(allow=_E), "address": S(allow=_E),
    "householdMembers": ANY(), "veterinaryCare": S(allow=_E), "adoptionReason": ANY(),
    "additionalNotes": S(allow=_E),
})


def _err(status: int, error: str, **extra) -> RawError:
    return RawError(status, {"error": error, **extra})


def _fail(status: int, error: str, **extra) -> RawError:
    return RawError(status, {"success": False, "error": error, **extra})


def _int(value, default: int) -> int:
    m = re.match(r"^\s*-?\d+", str(value)) if value is not None else None
    return int(m.group()) if m else default


def _js_int(value):
    """parseInt(value, 10)，失敗回 None。"""
    if value is None:
        return None
    m = re.match(r"^\s*([+-]?\d+)", str(value))
    return int(m.group(1)) if m else None


def _pagination(page: int, limit: int, total: int) -> dict:
    total_pages = math.ceil(total / limit) if limit else 0
    return {"currentPage": page, "totalPages": total_pages, "totalItems": total, "itemsPerPage": limit,
            "hasNextPage": page < total_pages, "hasPrevPage": page > 1}


def parse_daily_hours(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip()
    if not s:
        return None
    m = re.search(r"(\d+)\s*[-~～]\s*(\d+)", s)
    if m:
        return round((int(m.group(1)) + int(m.group(2))) / 2)
    digits = re.sub(r"[^0-9]", "", s)
    return int(digits) if digits else None


def normalize_daily_hours(data: dict) -> None:
    """把各處的每日照顧時間（例如 "3-5"）轉成數字，並同步到 carePlan 與 applicantDetails.carePlan。"""
    def first(*vals):
        return next((v for v in vals if v is not None), None)

    def obj(parent: dict, key: str) -> dict:
        if not isinstance(parent.get(key), dict):
            parent[key] = {}
        return parent[key]

    cp = data.get("carePlan")
    if isinstance(cp, dict):
        top = parse_daily_hours(first(cp.get("dailyAvailableHours"), cp.get("dailyCareTime"), data.get("dailyCareTime")))
        if top is not None:
            cp["dailyCareTime"] = cp["dailyAvailableHours"] = top
    acp = _g(data, "applicantDetails", "carePlan")
    if isinstance(acp, dict):
        v = parse_daily_hours(first(acp.get("dailyAvailableHours"), acp.get("dailyCareTime")))
        if v is not None:
            acp["dailyAvailableHours"] = acp["dailyCareTime"] = v
    fdn = parse_daily_hours(first(data.get("dailyCareTime"), data.get("dailyAvailableHours")))
    if fdn is not None:
        data["dailyCareTime"] = data["dailyAvailableHours"] = fdn
        for target in (obj(data, "carePlan"), obj(obj(data, "applicantDetails"), "carePlan")):
            for key in ("dailyCareTime", "dailyAvailableHours"):
                if not target.get(key):
                    target[key] = fdn


def _g(d, *path):
    """安全取值，等同 JS 的 a?.b?.c。"""
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _or(*vals):
    """JS 的 a || b || c。"""
    for v in vals:
        if v:
            return v
    return vals[-1] if vals else None


def _nn(*vals):
    """JS 的 a ?? b ?? c。"""
    return next((v for v in vals if v is not None), None)


def _contact_phone(a: dict):
    return _or(_g(a, "applicantDetails", "contact", "phone"), _g(a, "applicantDetails", "contactPhone"),
               _g(a, "contactInfo", "phone"), a.get("contactPhone"), a.get("phone"), "")


def _motivation(a: dict) -> dict:
    return {
        "reasons": _g(a, "motivation", "reasons") or ([a["adoptionReason"]] if a.get("adoptionReason") else []),
        "expectations": _or(_g(a, "motivation", "expectations"), a.get("adoptionReason"), ""),
        "commitment": _or(_g(a, "motivation", "commitment"), a.get("additionalNotes"), ""),
    }


def _emergency(a: dict) -> dict:
    return {
        "name": _or(_g(a, "emergencyContact", "name"), a.get("emergencyContactName"),
                    _g(a, "carePlan", "emergencyContactName"), ""),
        "relationship": _or(_g(a, "emergencyContact", "relationship"), "其他"),
        "phone": _or(_g(a, "emergencyContact", "phone"), a.get("emergencyContactPhone"), ""),
        "email": _or(_g(a, "emergencyContact", "email"), a.get("email"), ""),
    }


async def _pet_owner_id(pet: dict):
    return pet.get("createdBy") if pet else None


def can_manage_adoption(user: dict, pet: dict | None) -> bool:
    """T07：admin 可以處理全部；其他人只能處理自己動物的申請。動物已刪除時不行。"""
    if user.get("role") == "admin":
        return True
    return bool(pet) and same_id(pet.get("createdBy"), user["_id"])


async def _load(adoption_id: str, projection: dict | None = DEFAULT_PROJECTION) -> dict | None:
    aid = oid(adoption_id)
    return await get_db().adoptions.find_one({"_id": aid}, projection) if aid else None


async def _notify_new_application(pet: dict, adoption_id) -> None:
    owner = await _pet_owner_id(pet)
    if not owner:
        return
    await notify_owner_and_shelters(owner, {
        "type": "adoption_received", "title": "收到新的認養申請",
        "content": f"有人想認養您發布的 {pet.get('name')}！請前往查看申請詳情。",
        "link": f"/my-pets-applications?applicationId={adoption_id}", "relatedAdoption": adoption_id,
    }, broadcast_content=f"有人想認養 {pet.get('name')}（透過政府資料匯入的寵物），請前往查看申請詳情。")


async def _existing(pet_id, user_id) -> dict | None:
    return await get_db().adoptions.find_one(
        {"pet": pet_id, "applicant": user_id, "status": {"$nin": ["rejected", "cancelled"]}}, {"_id": 1})


async def _insert(data: dict) -> dict:
    doc = await prepare_new_adoption(data)
    doc["_id"] = (await get_db().adoptions.insert_one(doc)).inserted_id
    return doc


@router.post("", status_code=201, summary="提交認養申請（舊格式）")
async def create_adoption(body: dict | None = None, user: dict = Depends(token_user_zh)):
    data = validate(CREATE_SCHEMA, body)
    pet_id = oid(data.pop("petId"))
    a = data
    normalize_daily_hours(a)
    pet = await get_db().pets.find_one({"_id": pet_id})
    if not pet or not pet.get("isActive", True) or pet.get("adoptionStatus") != "available":
        raise _err(400, "此寵物目前無法申請認養")
    if same_id(pet.get("createdBy"), user["_id"]):
        raise _err(400, "不能申請認養自己刊登的動物")
    if await _existing(pet_id, user["_id"]):
        raise _err(400, "您已經為此寵物提交過認養申請")
    ad = a.get("applicantDetails") or {}
    try:
        adoption = await _insert({
            "pet": pet_id, "applicant": user["_id"], "rawSubmission": a,
            "rawSubmissionMeta": {"source": "web", "createdAt": datetime.now(timezone.utc)},
            "applicantDetails": {
                "housingType": _or(a.get("housingType"), ad.get("housingType")) or None,
                "hasYard": bool(a.get("hasYard") or ad.get("hasYard")),
                "isRented": a.get("housingOwnership") == "rented" or bool(ad.get("isRented")),
                "landlordApproval": _or(a.get("landlordApproval"), ad.get("landlordApproval"), False),
                "householdMembers": _or(a.get("householdMembers") if isinstance(a.get("householdMembers"), dict)
                                        else None, ad.get("householdMembers"), {}),
                "allergies": _or(a.get("allergies"), ad.get("allergies"), {"hasAllergies": False, "allergyDetails": ""}),
                "petExperience": _or(a.get("petExperience"), ad.get("petExperience"), {}),
                "workSchedule": _or(a.get("workSchedule"), ad.get("workSchedule"), {}),
                "veterinarianInfo": _or(a.get("veterinarianInfo"), ad.get("veterinarianInfo"), {}),
                "address": _or(a.get("address"), ad.get("address"), ""),
                "age": _nn(ad.get("age"), _g(a, "personalInfo", "age"), _js_int(a.get("age")) if a.get("age") else None),
                "occupation": _nn(ad.get("occupation"), _g(a, "personalInfo", "occupation"), a.get("occupation")),
                "contactPhone": _contact_phone(a),
            },
            "motivation": a.get("motivation") or _motivation(a),
            "emergencyContact": _emergency(a),
            "status": "pending",
            "agreementAccepted": _nn(a.get("agreementAccepted"), True),
            "agreementDate": a.get("agreementDate") or datetime.now(timezone.utc),
        })
    except MongooseError as e:
        raise _err(400, "提交認養申請失敗", details=str(e))
    await set_pet_status(pet_id, "pending")
    await _notify_new_application(pet, adoption["_id"])
    full = await get_db().adoptions.find_one({"_id": adoption["_id"]})
    await populate(full, "pet", "pets", "name species breed photos")
    await populate(full, "applicant", "users", "firstName lastName email phone")
    return {"message": "認養申請提交成功", "adoption": adoption_json(full)}


def _validation(message: str, **details) -> RawError:
    return RawError(400, {"success": False, "message": message, "details": details})


def _current_pets(a: dict) -> list:
    if not a.get("currentPets"):
        return []
    details = a.get("currentPetsDetails") or _g(a, "applicantDetails", "petExperience", "currentPetsDetails") or ""
    parts = [p.strip() for p in re.split(r"\r?\n|;|，|,|；", str(details)) if p.strip()]
    return [{"species": p or "未指定", "age": None, "vaccinated": False, "spayed": False} for p in parts]


@router.post("/apply/{pet_id}", status_code=201, summary="提交認養申請（前端使用）")
async def apply(pet_id: str, request: Request, user: dict = Depends(token_user_zh)):
    try:
        a = await request.json()
    except ValueError:
        a = {}
    a = a if isinstance(a, dict) else {}
    normalize_daily_hours(a)
    pid = oid(pet_id)
    pet = await get_db().pets.find_one({"_id": pid}) if pid else None
    if not pet or not pet.get("isActive", True):
        raise RawError(400, {"success": False, "message": "此寵物不存在或已下架"})
    if pet.get("adoptionStatus") != "available":
        raise RawError(400, {"success": False, "message": "此寵物目前無法申請認養"})
    if same_id(pet.get("createdBy"), user["_id"]):
        raise RawError(400, {"success": False, "message": "不能申請認養自己刊登的動物"})
    if await _existing(pid, user["_id"]):
        raise RawError(400, {"success": False, "message": "您已經為此寵物提交過認養申請，請勿重複申請"})

    missing = [k for k in ("age",) if not a.get("age") and a.get("age") != 0]
    if not a.get("occupation"):
        missing.append("occupation")
    if missing:
        raise _validation("個人資訊缺少必填欄位", missing=missing)
    has_prev, no_exp, has_cur = bool(a.get("previousPetExperience")), bool(a.get("noPetExperience")), bool(a.get("currentPets"))
    if not (has_prev or no_exp or has_cur):
        raise _validation("養寵經驗欄位缺失", requiredOneOf=["previousPetExperience", "noPetExperience", "currentPets"])
    if no_exp and (has_prev or has_cur):
        raise _validation("養寵經驗欄位衝突", conflict=["noPetExperience"] + (["previousPetExperience"] if has_prev else [])
                          + (["currentPets"] if has_cur else []))
    missing = [k for k in ("housingType", "housingOwnership", "address") if not a.get(k)]
    if a.get("householdMembers") is None:
        missing.append("householdMembers")
    if missing:
        raise _validation("居住環境欄位缺失", missing=missing)
    missing = []
    if not a.get("veterinaryCare") and not _g(a, "carePlan", "veterinaryCare"):
        missing.append("veterinaryCare")
    if not a.get("adoptionReason") and not _g(a, "motivation", "reasons"):
        missing.append("adoptionReason")
    if missing:
        raise _validation("照顧計畫或認養原因缺失", missing=missing)

    ages = [] if not (a.get("hasChildren") and a.get("childrenAges")) else \
        [n for n in (_js_int(x.strip()) for x in str(a["childrenAges"]).split(",")) if n is not None]
    rented = a.get("housingOwnership") == "rented"
    try:
        adoption = await _insert({
            "pet": pid, "applicant": user["_id"], "rawSubmission": a,
            "rawSubmissionMeta": {"source": "web", "createdAt": datetime.now(timezone.utc)},
            "applicantDetails": {
                "housingType": a.get("housingType"),
                "hasYard": bool(a.get("hasYard")),
                "isRented": rented,
                "landlordApproval": bool(a.get("landlordApproval")) if rented else False,
                "householdMembers": {
                    "adults": a.get("householdMembers") or 1,
                    "children": len(str(a["childrenAges"]).split(",")) if a.get("hasChildren") and a.get("childrenAges")
                    else 0,
                    "childrenAges": ages,
                },
                "allergies": {"hasAllergies": bool(a.get("hasAllergies")), "allergyDetails": a.get("allergyDetails") or ""},
                "petExperience": {
                    "hasPrevious": has_prev,
                    "previousPets": [{"species": "未指定", "yearsOwned": 0, "whatHappened": a["previousPetDetails"]}]
                    if has_prev and a.get("previousPetDetails") else [],
                    "currentPets": _current_pets(a),
                },
                "workSchedule": {"employmentStatus": a.get("employmentStatus") or "employed",
                                 "hoursAway": a.get("hoursAway") or 8, "whoWillCare": a.get("whoWillCare") or "本人"},
                "veterinarianInfo": {"hasVet": bool(a.get("hasVet")), "vetName": a.get("vetName") or "",
                                     "vetPhone": a.get("vetPhone") or "", "vetAddress": a.get("vetAddress") or ""},
                "age": _nn(_g(a, "applicantDetails", "age"), _g(a, "personalInfo", "age"),
                           _js_int(a.get("age")) if a.get("age") else None),
                "occupation": _nn(_g(a, "applicantDetails", "occupation"), _g(a, "personalInfo", "occupation"),
                                  a.get("occupation")),
                "carePlan": {
                    "dailyAvailableHours": _or(_g(a, "carePlan", "dailyAvailableHours"), a.get("dailyCareTime"),
                                               _g(a, "applicantDetails", "carePlan", "dailyAvailableHours"), None),
                    "exercisePlan": _or(_g(a, "carePlan", "exercisePlan"), a.get("exercisePlan"),
                                        _g(a, "applicantDetails", "carePlan", "exercisePlan"), None),
                    "vetCarePlan": _or(_g(a, "carePlan", "vetCarePlan"), a.get("veterinaryCare"),
                                       _g(a, "applicantDetails", "carePlan", "vetCarePlan"), None),
                    "financialPlan": _or(_g(a, "carePlan", "financialPlan"), a.get("financialCapability"),
                                         _g(a, "applicantDetails", "carePlan", "financialPlan"), None),
                    "otherNotes": _or(_g(a, "carePlan", "otherNotes"), a.get("otherNotes"),
                                      _g(a, "applicantDetails", "carePlan", "otherNotes"), None),
                },
                "address": a.get("address") or "",
                "contactPhone": _contact_phone(a),
            },
            "motivation": _motivation(a),
            "emergencyContact": _emergency(a),
            "status": "pending",
            "agreementAccepted": True,
            "agreementDate": datetime.now(timezone.utc),
        })
    except MongooseError as e:
        # 舊版回 500；欄位格式錯誤屬於使用者輸入，改回 400，body 格式不變
        raise RawError(400, {"success": False, "message": "提交認養申請失敗", "error": str(e)})
    await set_pet_status(pid, "pending")
    await _notify_new_application(pet, adoption["_id"])
    full = await get_db().adoptions.find_one({"_id": adoption["_id"]})
    await populate(full, "pet", "pets", "name species breed photos shelterInfo")
    await populate(full, "applicant", "users", "firstName lastName email username")
    return {"success": True, "message": "認養申請提交成功！我們會儘快審核並與您聯繫。",
            "data": {"adoption": adoption_json(full)}}


@router.get("/my-applications", summary="我的認養申請")
async def my_applications(request: Request, user: dict = Depends(token_user_zh)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 10)
    query: dict = {"applicant": user["_id"]}
    if q.get("status"):
        query["status"] = q["status"]
    docs = await get_db().adoptions.find(query, {"reviewNotes": 0, "rawSubmission": 0}).sort("createdAt", -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "pet", "pets", "name species breed photos adoptionStatus")
    total = await get_db().adoptions.count_documents(query)
    return {"applications": [adoption_json(d) for d in docs], "pagination": _pagination(page, limit, total)}


@router.get("/my-pets-applications", summary="我的動物收到的申請")
async def my_pets_applications(request: Request, user: dict = Depends(token_user_zh)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 10)
    pet_ids = [p["_id"] async for p in get_db().pets.find({"createdBy": user["_id"]}, {"_id": 1})]
    query: dict = {"pet": {"$in": pet_ids}}
    if q.get("status"):
        query["status"] = q["status"]
    docs = await get_db().adoptions.find(query, DEFAULT_PROJECTION).sort("createdAt", -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "pet", "pets", "name species breed photos adoptionStatus createdBy")
    await populate(docs, "applicant", "users", "username email firstName lastName phone")
    total = await get_db().adoptions.count_documents(query)
    return {"success": True, "data": {"applications": [adoption_json(d) for d in docs],
                                      "pagination": _pagination(page, limit, total)}}


async def require_admin(user: dict = Depends(token_user_zh)) -> dict:
    if user.get("role") not in ("admin", "volunteer"):
        raise _err(403, "需要管理員權限")
    return user


@router.get("/admin/all", summary="所有認養申請（管理員）")
async def admin_all(request: Request, user: dict = Depends(require_admin)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 20)
    query: dict = {}
    if q.get("status"):
        query["status"] = q["status"]
    if q.get("priority"):
        query["priority"] = q["priority"]
    db = get_db()
    if q.get("search"):
        rx = re.compile(re.escape(q["search"]), re.I)
        users = [u["_id"] async for u in db.users.find({"$or": [{"firstName": rx}, {"lastName": rx}, {"email": rx}]},
                                                        {"_id": 1})]
        pets = [p["_id"] async for p in db.pets.find({"$or": [{"name": rx}, {"breed": rx}]}, {"_id": 1})]
        query["$or"] = [{"applicationId": rx}, {"applicant": {"$in": users}}, {"pet": {"$in": pets}}]
    admin_ids = [u["_id"] async for u in db.users.find({"role": "admin"}, {"_id": 1})]
    admin_pets = [p["_id"] async for p in db.pets.find({"createdBy": {"$in": admin_ids}}, {"_id": 1})]
    if "$or" in query:
        query["$and"] = [{"$or": query.pop("$or")}, {"pet": {"$in": admin_pets}}]
    else:
        query["pet"] = {"$in": admin_pets}
    order = -1 if q.get("sortOrder", "desc") == "desc" else 1
    docs = await db.adoptions.find(query, DEFAULT_PROJECTION).sort(q.get("sortBy", "createdAt"), order) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "pet", "pets", "name species breed photos adoptionStatus")
    await populate(docs, "applicant", "users", "firstName lastName email phone")
    await populate(docs, "reviewDecision.reviewer", "users", "firstName lastName")
    total = await db.adoptions.count_documents(query)
    return {"applications": [adoption_json(d) for d in docs], "pagination": _pagination(page, limit, total)}


@router.get("/admin/stats", summary="認養統計（管理員）")
async def admin_stats(user: dict = Depends(require_admin)):
    join = [
        {"$lookup": {"from": "pets", "localField": "pet", "foreignField": "_id", "as": "pet"}}, {"$unwind": "$pet"},
        {"$lookup": {"from": "users", "localField": "pet.createdBy", "foreignField": "_id", "as": "owner"}},
        {"$unwind": "$owner"},
    ]
    a = get_db().adoptions
    status_counts = await (await a.aggregate(join + [{"$match": {"owner.role": "admin"}},
                                                     {"$group": {"_id": "$status", "count": {"$sum": 1}}}])).to_list(None)
    monthly = await (await a.aggregate(join + [
        {"$match": {"status": "completed", "owner.role": "admin"}},
        {"$group": {"_id": {"year": {"$year": "$completionInfo.adoptionDate"},
                            "month": {"$month": "$completionInfo.adoptionDate"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id.year": -1, "_id.month": -1}}, {"$limit": 12}])).to_list(None)
    avg = await (await a.aggregate(join + [
        {"$match": {"status": {"$in": ["approved", "rejected", "completed"]}, "owner.role": "admin"}},
        {"$project": {"processingTime": {"$divide": [{"$subtract": ["$reviewDecision.reviewDate", "$createdAt"]},
                                                     86400000]}}},
        {"$group": {"_id": None, "averageProcessingTime": {"$avg": "$processingTime"}}}])).to_list(None)
    return {"statusCounts": status_counts, "monthlyCompletions": monthly,
            "averageProcessingTime": (avg[0].get("averageProcessingTime") if avg else 0) or 0}


@router.get("/{adoption_id}", summary="認養申請詳情（申請人或管理員）")
async def get_adoption(adoption_id: str, user: dict = Depends(token_user_zh)):
    doc = await _load(adoption_id, None)
    if not doc:
        raise _err(404, "找不到此認養申請")
    if not same_id(doc.get("applicant"), user["_id"]) and user.get("role") not in ("admin", "volunteer"):
        raise _err(403, "沒有權限查看此申請")
    await populate(doc, "pet", "pets")
    await populate(doc, "applicant", "users", "-password")
    await populate(doc, "reviewNotes.reviewer", "users", "firstName lastName")
    await populate(doc, "reviewDecision.reviewer", "users", "firstName lastName")
    await populate(doc, "completionInfo.completedBy", "users", "firstName lastName")
    out = adoption_json(doc)
    if isinstance(doc.get("pet"), dict):
        out["pet"] = pet_json(doc["pet"])
    return out


STATUS_NOTICE = {
    "approved": ("adoption_approved", "認養申請已核准", "您對 {} 的認養申請已被核准！", "high"),
    "rejected": ("adoption_rejected", "認養申請未通過", "很抱歉，您對 {} 的認養申請未能通過審核", "high"),
    "completed": ("adoption_completed", "認養完成", "恭喜完成 {} 的認養程序！", "urgent"),
}
PET_STATUS_FOR = {"approved": "pending", "rejected": "available", "cancelled": "available", "completed": "adopted"}
ADOPTED_PET = "這隻動物已被認養，不能再核准申請"


async def _sync_pet_status(pet: dict, adoption_id, target: str) -> None:
    """申請狀態改變後同步動物狀態。
    已被認養的動物不動：處理同一隻動物留下的舊申請時，不能讓牠變回可認養或審核中。
    要變回可認養時，同一隻動物還有其他進行中的申請就維持原狀。"""
    if pet.get("adoptionStatus") == "adopted" and target != "adopted":
        return
    if target == "available" and await get_db().adoptions.count_documents(
            {"pet": pet["_id"], "_id": {"$ne": adoption_id}, "status": {"$in": list(ACTIVE_STATUSES)}}):
        return
    await set_pet_status(pet["_id"], target)


async def _load_managed(adoption_id: str, user: dict, error_404: RawError, error_403: RawError) -> tuple[dict, dict]:
    adoption = await _load(adoption_id)
    if not adoption:
        raise error_404
    pet = await get_db().pets.find_one({"_id": adoption.get("pet")}) if adoption.get("pet") else None
    if not pet:
        # 動物已被刪除：視同找不到
        raise error_404
    if not can_manage_adoption(user, pet):
        raise error_403
    return adoption, pet


async def _notify_applicant(adoption: dict, pet: dict, status: str, content: str | None = None,
                            title: str | None = None) -> None:
    ntype, default_title, template, priority = STATUS_NOTICE.get(status, ("adoption_received", "認養申請更新", "", "high"))
    await safe_notify({
        "recipient": adoption["applicant"], "type": ntype, "title": title or default_title,
        "content": content or template.format(pet.get("name")) or f"您對 {pet.get('name')} 的認養申請狀態已更新",
        "relatedAdoption": adoption["_id"], "relatedPet": pet["_id"],
        "link": f"/my-applications?applicationId={adoption['_id']}", "priority": priority,
    })


@router.put("/{adoption_id}/status", summary="更新申請狀態（寵物擁有者或管理員）")
async def update_status(adoption_id: str, body: dict | None = None, user: dict = Depends(token_user_zh)):
    body = body or {}
    status, reason = body.get("status"), body.get("reason")
    adoption, pet = await _load_managed(adoption_id, user, _err(404, "找不到此認養申請"),
                                        _err(403, "只能處理自己動物的申請"))
    if status not in STATUSES:
        raise _err(400, "更新申請狀態失敗", details="Adoption validation failed: status: 請選擇有效的申請狀態")
    if pet.get("adoptionStatus") == "adopted" and status in ("approved", "completed"):
        raise _err(400, ADOPTED_PET)
    sets: dict = {"status": status, "updatedAt": datetime.now(timezone.utc)}
    if status in ("approved", "rejected"):
        sets["reviewDecision"] = {"decision": status, "reviewer": user["_id"], "reason": reason,
                                  "reviewDate": datetime.now(timezone.utc)}
    await get_db().adoptions.update_one({"_id": adoption["_id"]}, {"$set": sets})
    if status in PET_STATUS_FOR:
        await _sync_pet_status(pet, adoption["_id"], PET_STATUS_FOR[status])
    await _notify_applicant(adoption, pet, status)
    if status == "completed":
        await _close_other_applications(adoption, pet, user)
    updated = await _load(adoption_id)
    await populate(updated, "pet", "pets", "name species breed photos adoptionStatus")
    await populate(updated, "applicant", "users", "firstName lastName email phone")
    await populate(updated, "reviewDecision.reviewer", "users", "firstName lastName")
    audit("adoption_status_changed", by=user["_id"], adoption=adoption["_id"], status=status)
    return {"message": "申請狀態更新成功", "adoption": adoption_json(updated)}


@router.post("/{adoption_id}/complete",
             summary="完成認養（寵物擁有者或管理員）；同一隻動物其他進行中的申請一併結束並通知申請人")
async def complete(adoption_id: str, body: dict | None = None, user: dict = Depends(token_user_zh)):
    body = body or {}
    adoption, pet = await _load_managed(adoption_id, user, _err(404, "找不到此認養申請"),
                                        _err(403, "只能處理自己動物的申請"))
    if adoption.get("status") != "approved":
        raise _err(400, "只有已核准的申請才能完成認養流程")
    adoption["completionInfo"] = {
        "adoptionDate": body.get("adoptionDate") or datetime.now(timezone.utc),
        "fee": body.get("fee") or pet.get("adoptionFee") or 0,
        "microchipTransferred": body.get("microchipTransferred") or False,
        "documentsProvided": body.get("documentsProvided") or [],
        "completedBy": user["_id"],
    }
    errors: list = []
    info = cast(ADOPTION_SCHEMA, {"completionInfo": adoption["completionInfo"]}, errors=errors)["completionInfo"]
    try:
        if errors:
            raise MongooseError(errors, "Adoption")
        check_adoption({**adoption, "completionInfo": info, "status": "completed"})
    except MongooseError as e:
        raise _err(400, "完成認養流程失敗", details=str(e))
    await get_db().adoptions.update_one({"_id": adoption["_id"]}, {"$set": {
        "completionInfo": info, "status": "completed", "updatedAt": datetime.now(timezone.utc)}})
    await set_pet_status(pet["_id"], "adopted")
    await get_db().users.update_one({"_id": adoption["applicant"]}, {"$push": {"adoptionHistory": adoption["_id"]}})
    # T07：完成時通知認養者（舊版只有改狀態 API 會通知）
    await _notify_applicant(adoption, pet, "completed")
    closed = await _close_other_applications(adoption, pet, user)
    updated = await _load(adoption_id)
    updated["pet"] = await get_db().pets.find_one({"_id": pet["_id"]})
    out = adoption_json(updated)
    out["pet"] = pet_json(updated["pet"])
    audit("adoption_completed", by=user["_id"], adoption=adoption["_id"], closed_others=closed)
    return {"message": "認養流程完成", "adoption": out, "closedApplications": closed}


CLOSED_REASON = "這隻動物已由其他認養人完成認養"


async def _close_other_applications(adoption: dict, pet: dict, user: dict) -> int:
    """完成認養後，同一隻動物其他進行中的申請改為已拒絕並通知申請人，否則他們會一直停在待審核。
    用中性的「已結束」措辭，不寫成申請未通過。回傳結束的筆數。"""
    others = await get_db().adoptions.find(
        {"pet": pet["_id"], "_id": {"$ne": adoption["_id"]}, "status": {"$in": list(ACTIVE_STATUSES)}},
        {"_id": 1, "applicant": 1}).to_list(None)
    if not others:
        return 0
    now = datetime.now(timezone.utc)
    await get_db().adoptions.update_many({"_id": {"$in": [o["_id"] for o in others]}}, {"$set": {
        "status": "rejected", "updatedAt": now,
        "reviewDecision": {"decision": "rejected", "reviewer": user["_id"], "reason": CLOSED_REASON, "reviewDate": now}}})
    content = f"{pet.get('name')} 已經找到家了，你的認養申請已結束，歡迎看看其他毛孩。"
    for other in others:
        if other.get("applicant"):
            await _notify_applicant(other, pet, "rejected", content=content, title="認養申請已結束")
    return len(others)


@router.put("/{adoption_id}/cancel", summary="取消申請（申請人）")
async def cancel(adoption_id: str, user: dict = Depends(token_user_zh)):
    adoption = await _load(adoption_id)
    if not adoption:
        raise _err(404, "找不到此認養申請")
    if not same_id(adoption.get("applicant"), user["_id"]):
        raise _err(403, "沒有權限取消此申請")
    if adoption.get("status") in ("completed", "cancelled"):
        raise _err(400, "此申請無法取消")
    await get_db().adoptions.update_one({"_id": adoption["_id"]}, {"$set": {
        "status": "cancelled", "updatedAt": datetime.now(timezone.utc)}})
    pet = await get_db().pets.find_one({"_id": adoption.get("pet")}) if adoption.get("pet") else None
    if pet and pet.get("adoptionStatus") == "pending":
        await _sync_pet_status(pet, adoption["_id"], "available")
    if pet and pet.get("createdBy"):
        name = user.get("firstName") or user.get("username") or "申請人"
        content = f"{name} 已取消對 {pet.get('name')} 的認養申請。"
        await notify_owner_and_shelters(pet["createdBy"], {
            "type": "adoption_cancelled", "title": "認養申請已取消", "content": content,
            "link": f"/my-pets-applications?applicationId={adoption['_id']}",
            "relatedAdoption": adoption["_id"], "relatedPet": pet["_id"],
        })
    updated = await _load(adoption_id)
    await populate(updated, "pet", "pets")
    await populate(updated, "applicant", "users", "firstName lastName username")
    out = adoption_json(updated)
    if isinstance(updated.get("pet"), dict):
        out["pet"] = pet_json(updated["pet"])
    audit("adoption_cancelled", by=user["_id"], adoption=adoption["_id"])
    return {"message": "認養申請已取消", "adoption": out}


@router.post("/{adoption_id}/notes", summary="新增審核備註（寵物擁有者或管理員）")
async def add_note(adoption_id: str, body: dict | None = None, user: dict = Depends(token_user_zh)):
    note = (body or {}).get("note")
    if not isinstance(note, str) or not note.strip():
        raise _fail(400, "備註內容不能為空")
    adoption, _pet = await _load_managed(adoption_id, user, _fail(404, "找不到此認養申請"),
                                         _fail(403, "僅管理員或該寵物的發布者可新增審核備註"))
    if len(note.strip()) > 1000:
        raise _fail(400, "新增審核備註失敗", details="Adoption validation failed: 審核備註不能超過 1000 個字元")
    entry = {"_id": ObjectId(), "reviewer": user["_id"], "note": note.strip(),
             "createdAt": datetime.now(timezone.utc)}
    await get_db().adoptions.update_one({"_id": adoption["_id"]}, {
        "$push": {"reviewNotes": entry}, "$set": {"updatedAt": datetime.now(timezone.utc)}})
    updated = await _load(adoption_id, {"reviewNotes": 1})
    notes = updated.get("reviewNotes") or []
    await populate(notes, "reviewer", "users", "username role")
    return {"success": True, "message": "審核備註已新增", "reviewNotes": [adoption_json(n) for n in notes]}


@router.post("/{adoption_id}/review", summary="審核申請（寵物擁有者或管理員）")
async def review(adoption_id: str, body: dict | None = None, user: dict = Depends(token_user_zh)):
    body = body or {}
    decision, reason = body.get("decision"), body.get("reason")
    if decision not in ("approved", "rejected"):
        raise _fail(400, "請提供有效的審核決定 (approved 或 rejected)")
    # 原因會存進申請並寫進給申請人的通知，限制型別與長度
    if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
        raise _fail(400, "審核原因最多 500 字")
    adoption, pet = await _load_managed(adoption_id, user, _fail(404, "找不到此認養申請"),
                                        _fail(403, "您沒有權限審核此申請"))
    if adoption.get("status") not in ("pending", "under-review"):
        raise _fail(400, "此申請已被審核過")
    if decision == "approved" and pet.get("adoptionStatus") == "adopted":
        raise _fail(400, ADOPTED_PET)
    decision_doc = {"decision": decision, "reviewer": user["_id"], "reason": reason or "",
                    "reviewDate": datetime.now(timezone.utc)}
    await get_db().adoptions.update_one({"_id": adoption["_id"]}, {"$set": {
        "reviewDecision": decision_doc, "status": decision, "updatedAt": datetime.now(timezone.utc)}})
    await _sync_pet_status(pet, adoption["_id"], "pending" if decision == "approved" else "available")
    content = (f"您對 {pet.get('name')} 的認養申請已被核准！" if decision == "approved"
               else f"很抱歉，您對 {pet.get('name')} 的認養申請未通過。{f'原因：{reason}' if reason else ''}")
    await safe_notify({
        "recipient": adoption["applicant"], "type": f"adoption_{decision}",
        "title": "認養申請已核准" if decision == "approved" else "認養申請未通過", "content": content,
        "relatedAdoption": adoption["_id"], "relatedPet": pet["_id"],
        "link": f"/my-applications?applicationId={adoption['_id']}",
    })
    if decision == "approved" and user.get("role") == "admin":
        try:
            msg = prepare_new_message({
                "content": "您的申請已被同意，請撥空與欲領養動物所在的機構聯絡，進行後續領養所需的步驟。",
                "type": "adoption-update", "sender": user["_id"], "receiver": adoption["applicant"],
                "relatedPet": pet["_id"], "relatedAdoption": adoption["_id"],
                "systemData": {"eventType": "adoption-approved", "metadata": {"by": user["_id"]}},
            })
            await get_db().messages.insert_one(msg)
        except Exception:
            logger.exception("建立聊天室訊息失敗")
    audit("adoption_reviewed", by=user["_id"], adoption=adoption["_id"], decision=decision)
    return {"success": True, "message": f"申請已{'核准' if decision == 'approved' else '拒絕'}",
            "adoption": {"_id": str(adoption["_id"]), "status": decision, "reviewDecision": to_json(decision_doc)}}


@router.get("/{adoption_id}/details",
            summary="申請詳情（申請人、寵物擁有者或管理員）；審核者另外取得 reviewInsights（規則產生的審核輔助）")
async def details(adoption_id: str, user: dict = Depends(token_user_zh)):
    doc = await _load(adoption_id, None)
    if not doc:
        raise _fail(404, "找不到此認養申請")
    pet = await get_db().pets.find_one({"_id": doc.get("pet")}) if doc.get("pet") else None
    is_applicant = same_id(doc.get("applicant"), user["_id"])
    is_owner = bool(pet) and same_id(pet.get("createdBy"), user["_id"])
    if not (is_applicant or is_owner or user.get("role") in ("admin", "volunteer")):
        raise _fail(403, "您沒有權限查看此申請（需為申請人、該寵物的發布者或管理員）")
    # 審核輔助只給審核者，申請人看不到（要在 populate 前算，applicant 還是 ObjectId）
    insights = await review_insights.build(doc, pet) if pet and not is_applicant and doc.get("applicant") else None
    doc["pet"] = pet
    await populate(doc, "applicant", "users", "username email phone")
    await populate(doc, "reviewNotes.reviewer", "users", "username role")
    await populate(doc, "reviewDecision.reviewer", "users", "username role")
    if is_applicant:
        doc.pop("reviewNotes", None)
    out = adoption_json(doc)
    if pet:
        out["pet"] = pet_json(pet)
    if insights is not None:
        out["reviewInsights"] = insights
    return {"success": True, "data": out}
