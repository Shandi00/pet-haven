"""/api/stats（首頁統計）與 /api/shelters/{id}/stats（收容所儀表板）。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from app.core.ids import oid
from app.core.serialize import to_json
from app.db import get_db
from app.deps import current_user
from app.models.pet import pet_json
from app.responses import RawError

router = APIRouter(tags=["Stats"])


@router.get("/api/stats", summary="首頁公開統計")
async def public_stats():
    db = get_db()
    return {"success": True, "data": {
        "available": await db.pets.count_documents({"adoptionStatus": "available", "isActive": True}),
        "adopted": await db.adoptions.count_documents({"status": {"$in": ["approved", "completed"]}}),
        "importedPets": await db.pets.count_documents({"govData.animalId": {"$exists": True, "$ne": None},
                                                        "isActive": True}),
        "bySpecies": await db.pets.distinct("species", {"adoptionStatus": "available", "isActive": True}),
    }}


async def _avg(pipeline: list, field: str) -> float:
    rows = await (await get_db().adoptions.aggregate(pipeline)).to_list(None)
    return (rows[0].get(field) if rows else 0) or 0


@router.get("/api/shelters/{shelter_id}/stats", summary="收容所統計（本人或管理員）")
async def shelter_stats(shelter_id: str, request: Request, user: dict = Depends(current_user)):
    if user.get("role") not in ("shelter", "admin"):
        raise RawError(403, {"success": False, "error": "權限不足", "message": "此功能僅限 shelter, admin 角色存取"})
    if user.get("role") == "shelter" and str(user["_id"]) != shelter_id:
        raise RawError(403, {"success": False, "error": "您只能查看自己的統計資料"})
    sid = oid(shelter_id)
    if sid is None:
        raise RawError(400, {"success": False, "error": "無效的收容所 ID"})
    try:
        days = int(request.query_params.get("range", 30)) or 30
    except ValueError:
        days = 30
    start = datetime.now(timezone.utc) - timedelta(days=days)
    db = get_db()
    # 舊版查詢 Pet 不存在的 shelter/status 欄位，結果永遠是 0；改用 createdBy 與 adoptionStatus
    owned = {"createdBy": sid}
    pet_ids = [p["_id"] async for p in db.pets.find(owned, {"_id": 1})]
    by_pet = {"pet": {"$in": pet_ids}}
    total_apps = await db.adoptions.count_documents(by_pet)
    approved = await db.adoptions.count_documents({**by_pet, "status": "approved"})
    avg_days = await _avg([
        {"$match": {**by_pet, "status": "completed", "completionInfo.adoptionDate": {"$exists": True}}},
        {"$project": {"days": {"$divide": [{"$subtract": ["$completionInfo.adoptionDate", "$createdAt"]}, 86400000]}}},
        {"$group": {"_id": None, "avgDays": {"$avg": "$days"}}}], "avgDays")
    avg_hours = await _avg([
        {"$match": {**by_pet, "status": {"$in": ["approved", "rejected"]}, "updatedAt": {"$exists": True}}},
        {"$project": {"hours": {"$divide": [{"$subtract": ["$updatedAt", "$createdAt"]}, 3600000]}}},
        {"$group": {"_id": None, "avgHours": {"$avg": "$hours"}}}], "avgHours")
    species = await (await db.pets.aggregate([
        {"$match": owned}, {"$group": {"_id": "$species", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}])).to_list(None)
    trend = await (await db.adoptions.aggregate([
        {"$match": {**by_pet, "createdAt": {"$gte": start}}},
        {"$group": {"_id": {"year": {"$year": "$createdAt"}, "month": {"$month": "$createdAt"},
                            "day": {"$dayOfMonth": "$createdAt"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}}])).to_list(None)
    sponsor = await (await db.pets.aggregate([
        {"$match": {**owned, "sponsorship.enabled": True}},
        {"$group": {"_id": None, "totalClicks": {"$sum": "$sponsorship.clickCount"}, "enabledCount": {"$sum": 1}}},
    ])).to_list(None)
    top = await db.pets.find({**owned, "sponsorship.enabled": True, "sponsorship.clickCount": {"$gt": 0}},
                             {"name": 1, "species": 1, "sponsorship.clickCount": 1, "photos": 1}) \
        .sort("sponsorship.clickCount", -1).limit(5).to_list(None)
    return {"success": True, "data": {
        "overview": {
            "totalPets": len(pet_ids),
            "availablePets": await db.pets.count_documents({**owned, "adoptionStatus": "available"}),
            "adoptedPets": await db.pets.count_documents({**owned, "adoptionStatus": "adopted"}),
            "pendingPets": await db.pets.count_documents({**owned, "adoptionStatus": "pending"}),
            "totalApplications": total_apps,
            "pendingApplications": await db.adoptions.count_documents(
                {**by_pet, "status": {"$in": ["pending", "under-review"]}}),
            "approvedApplications": approved,
            "rejectedApplications": await db.adoptions.count_documents({**by_pet, "status": "rejected"}),
            "monthApplications": await db.adoptions.count_documents({**by_pet, "createdAt": {"$gte": start}}),
            "successfulAdoptions": await db.adoptions.count_documents({**by_pet, "status": "completed"}),
            "approvalRate": round(approved / total_apps * 100) if total_apps else 0,
            "averageAdoptionDays": round(avg_days) if avg_days else 0,
            "averageReviewTime": round(avg_hours) if avg_hours else 0,
            "sponsorshipEnabled": sponsor[0]["enabledCount"] if sponsor else 0,
            "totalSponsorshipClicks": sponsor[0]["totalClicks"] if sponsor else 0,
        },
        "speciesDistribution": [{"species": s["_id"], "count": s["count"]} for s in species],
        "applicationTrend": [{"date": f"{t['_id']['year']}-{t['_id']['month']:02d}-{t['_id']['day']:02d}",
                              "count": t["count"]} for t in trend],
        "topSponsoredPets": [pet_json(p) for p in top],
    }}
