"""/api/users：對應舊版 routes/users.js 與 routes/user-stats.js（兩者都掛在 /api/users）。"""
import math
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import F, cast, validate as schema_validate
from app.core.serialize import to_json
from app.db import get_db
from app.deps import current_user, token_user_zh
from app.models.adoption import adoption_json
from app.models.pet import pet_json
from app.models.post import post_json
from app.models.user import ROLES, user_json
from app.responses import RawError

router = APIRouter(prefix="/api/users", tags=["Users"])


def _err(status: int, error: str, **extra) -> RawError:
    return RawError(status, {"error": error, **extra})


def _int(value, default: int) -> int:
    m = re.match(r"^\s*-?\d+", str(value)) if value is not None else None
    return int(m.group()) if m else default


def _pagination(page: int, limit: int, total: int) -> dict:
    total_pages = math.ceil(total / limit) if limit else 0
    return {"currentPage": page, "totalPages": total_pages, "totalItems": total, "itemsPerPage": limit,
            "hasNextPage": page < total_pages, "hasPrevPage": page > 1}


async def require_admin(user: dict = Depends(token_user_zh)) -> dict:
    if user.get("role") != "admin":
        raise _err(403, "需要管理員權限")
    return user


# ---------- user-stats.js ----------

@router.get("/me/stats", summary="我的統計")
async def my_stats(user: dict = Depends(current_user)):
    db = get_db()
    uid = user["_id"]
    full = await db.users.find_one({"_id": uid}) or {}
    post_ids = [p["_id"] async for p in db.posts.find({"author": uid}, {"_id": 1})]
    comments = await db.comments.count_documents({"post": {"$in": post_ids}}) if post_ids else 0
    completed = 0
    if (full.get("recommendationProfile") or {}).get("species"):
        completed += 1
    life = full.get("lifestyleProfile") or {}
    if life.get("activityLevel") and life.get("availableTime") and life.get("housingType"):
        completed += 1
    if (full.get("experienceProfile") or {}).get("petOwnershipExperience"):
        completed += 1
    env = full.get("environmentProfile") or {}
    if "hasChildren" in env or "hasOtherPets" in env:
        completed += 1
    return {"success": True, "data": {
        "petsViewed": len(full.get("browsingHistory") or []),
        "favoritesCount": len(full.get("favorites") or []),
        "applicationsCount": await db.adoptions.count_documents({"applicant": uid}),
        "postsCount": len(post_ids) + comments,
        "matchingProfileComplete": round(completed / 4 * 100),
    }}


@router.get("/me/activities", summary="我的活動時間軸")
async def my_activities(request: Request, user: dict = Depends(current_user)):
    db = get_db()
    uid = user["_id"]
    limit = _int(request.query_params.get("limit"), 20) or 20
    full = await db.users.find_one({"_id": uid}) or {}
    activities = []
    history = (full.get("browsingHistory") or [])[:5]
    await populate(history, "pet", "pets", "name species")
    for h in history:
        if isinstance(h.get("pet"), dict):
            kind = "狗" if h["pet"].get("species") == "dog" else "貓"
            activities.append({"type": "pet_view", "description": f"瀏覽了 {h['pet'].get('name')} ({kind})",
                               "createdAt": h.get("viewedAt")})
    now = datetime.now(timezone.utc)
    async for pet in db.pets.find({"_id": {"$in": full.get("favorites") or []}}, {"name": 1}).limit(5):
        activities.append({"type": "favorite", "description": f"收藏了 {pet.get('name')}", "createdAt": now})
    apps = await db.adoptions.find({"applicant": uid}).sort("createdAt", -1).limit(5).to_list(None)
    await populate(apps, "pet", "pets", "name")
    for a in apps:
        name = (a.get("pet") or {}).get("name") if isinstance(a.get("pet"), dict) else None
        activities.append({"type": "application", "description": f"提交了 {name or '某寵物'} 的認養申請",
                           "createdAt": a.get("createdAt")})
    async for post in db.posts.find({"author": uid}).sort("createdAt", -1).limit(5):
        title = post.get("title") or ""
        activities.append({"type": "post", "description": f"發表了貼文：{title[:30]}{'...' if len(title) > 30 else ''}",
                           "createdAt": post.get("createdAt")})

    def key(a):
        ts = a.get("createdAt")
        if not isinstance(ts, datetime):
            return datetime.min.replace(tzinfo=timezone.utc)
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    activities.sort(key=key, reverse=True)
    return {"success": True, "data": to_json(activities[:limit])}


# ---------- users.js ----------

@router.get("/profile", summary="取得我的資料")
async def get_profile(user: dict = Depends(token_user_zh)):
    full = await get_db().users.find_one({"_id": user["_id"]}, {"password": 0})
    if not full:
        raise _err(404, "找不到使用者")
    return user_json(full)


# 舊版把整個 body 寫進使用者資料，任何人都能把自己改成 admin；改成只允許這些欄位
PROFILE_FIELDS = ("firstName", "lastName", "name", "username", "phone", "contact_info", "address", "avatar_url",
                  "introduction", "preferences", "recommendationProfile")


@router.put("/profile", summary="更新我的資料（含推薦偏好）")
async def update_profile(body: dict | None = None, user: dict = Depends(token_user_zh)):
    body = body or {}
    updates = {k: v for k, v in body.items() if k in PROFILE_FIELDS}
    if isinstance(updates.get("recommendationProfile"), dict):
        updates["recommendationProfile"] = {**updates["recommendationProfile"],
                                            "lastUpdated": datetime.now(timezone.utc)}
    if "username" in updates and (not isinstance(updates["username"], str)
                                  or not 3 <= len(updates["username"].strip()) <= 30):
        raise _err(400, "更新使用者資料失敗", details="使用者名稱需要 3 到 30 個字元")
    updates["updatedAt"] = datetime.now(timezone.utc)
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": updates})
    full = await get_db().users.find_one({"_id": user["_id"]}, {"password": 0})
    return {"message": "使用者資料更新成功", "user": user_json(full)}


@router.get("/favorites", summary="我收藏的寵物")
async def favorites(user: dict = Depends(token_user_zh)):
    full = await get_db().users.find_one({"_id": user["_id"]}, {"favorites": 1}) or {}
    ids = full.get("favorites") or []
    pets = await get_db().pets.find({"_id": {"$in": ids}, "isActive": True}, {
        "name": 1, "species": 1, "breed": 1, "age": 1, "gender": 1, "size": 1, "photos": 1, "adoptionStatus": 1,
        "shelterInfo": 1, "createdBy": 1}).to_list(None)
    order = {pid: i for i, pid in enumerate(ids)}
    pets.sort(key=lambda p: order.get(p["_id"], 0))
    await populate(pets, "createdBy", "users", "username firstName lastName")
    return {"success": True, "data": {"favorites": [pet_json(p) for p in pets], "count": len(pets)}}


@router.post("/favorites/{pet_id}", summary="加入／移除收藏")
async def toggle_favorite(pet_id: str, user: dict = Depends(token_user_zh)):
    pid = oid(pet_id)
    pet = await get_db().pets.find_one({"_id": pid}, {"isActive": 1}) if pid else None
    if not pet or not pet.get("isActive", True):
        raise HTTPException(404, "找不到此寵物")
    full = await get_db().users.find_one({"_id": user["_id"]}, {"favorites": 1}) or {}
    favorited = any(same_id(x, pid) for x in full.get("favorites") or [])
    op = {"$pull": {"favorites": pid}} if favorited else {"$push": {"favorites": pid}}
    await get_db().users.update_one({"_id": user["_id"]}, op)
    count = len((await get_db().users.find_one({"_id": user["_id"]}, {"favorites": 1})).get("favorites") or [])
    return {"success": True, "message": "已取消收藏" if favorited else "已加入收藏",
            "data": {"favorited": not favorited, "favoritesCount": count}}


@router.get("/saved-posts", summary="我收藏的貼文")
async def saved_posts(request: Request, user: dict = Depends(token_user_zh)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 15)
    full = await get_db().users.find_one({"_id": user["_id"]}, {"collections": 1}) or {}
    ids = full.get("collections") or []
    posts = await get_db().posts.find({"_id": {"$in": ids}}).sort("createdAt", -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(posts, "author", "users", "firstName lastName username avatar_url")
    total = len(posts)
    total_pages = math.ceil(total / limit) if limit else 0
    return {"success": True, "data": {"posts": [post_json(p) for p in posts], "pagination": {
        "page": page, "limit": limit, "total": total, "totalPages": total_pages,
        "hasNextPage": page < total_pages, "hasPrevPage": page > 1}}}


@router.post("/saved-posts/{post_id}", summary="收藏／取消收藏貼文")
async def toggle_saved_post(post_id: str, user: dict = Depends(token_user_zh)):
    pid = oid(post_id)
    if pid is None:
        raise HTTPException(400, "無效的貼文 ID")
    full = await get_db().users.find_one({"_id": user["_id"]}, {"collections": 1}) or {}
    saved = any(same_id(x, pid) for x in full.get("collections") or [])
    op = {"$pull": {"collections": pid}} if saved else {"$push": {"collections": pid}}
    await get_db().users.update_one({"_id": user["_id"]}, op)
    count = len((await get_db().users.find_one({"_id": user["_id"]}, {"collections": 1})).get("collections") or [])
    return {"success": True, "message": "已取消收藏" if saved else "已收藏貼文",
            "data": {"saved": not saved, "savedCount": count}}


@router.get("/admin/all", summary="所有使用者（管理員）")
async def admin_all(request: Request, admin: dict = Depends(require_admin)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 20)
    query: dict = {}
    if q.get("role"):
        query["role"] = q["role"]
    if "isActive" in q:
        query["isActive"] = q["isActive"] == "true"
    if q.get("search"):
        rx = re.compile(re.escape(q["search"]), re.I)
        query["$or"] = [{"username": rx}, {"firstName": rx}, {"lastName": rx}, {"email": rx}, {"phone": rx}]
    order = -1 if q.get("sortOrder", "desc") == "desc" else 1
    users = await get_db().users.find(query, {"password": 0}).sort(q.get("sortBy", "createdAt"), order) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(users, "adoptionHistory", "adoptions", "applicationId status createdAt")
    total = await get_db().users.count_documents(query)
    return {"users": [user_json(u) for u in users], "pagination": _pagination(page, limit, total)}


@router.get("/admin/search", summary="搜尋使用者（管理員）")
async def admin_search(request: Request, admin: dict = Depends(require_admin)):
    q = request.query_params
    term = (q.get("q") or "").strip()
    if len(term) < 2:
        raise _err(400, "搜尋關鍵字至少需要 2 個字元")
    rx = re.compile(re.escape(term), re.I)
    users = await get_db().users.find(
        {"$or": [{"username": rx}, {"firstName": rx}, {"lastName": rx}, {"email": rx}], "isActive": True},
        {"username": 1, "firstName": 1, "lastName": 1, "email": 1, "role": 1, "createdAt": 1},
    ).sort([("firstName", 1), ("lastName", 1)]).limit(_int(q.get("limit"), 10)).to_list(None)
    return [user_json(u) for u in users]


@router.get("/admin/stats/overview", summary="使用者統計（管理員）")
async def admin_stats(admin: dict = Depends(require_admin)):
    users = get_db().users
    by_role = await (await users.aggregate([{"$match": {"isActive": True}},
                                            {"$group": {"_id": "$role", "count": {"$sum": 1}}}])).to_list(None)
    monthly = await (await users.aggregate([
        {"$match": {"isActive": True}},
        {"$group": {"_id": {"year": {"$year": "$createdAt"}, "month": {"$month": "$createdAt"}},
                    "count": {"$sum": 1}}},
        {"$sort": {"_id.year": -1, "_id.month": -1}}, {"$limit": 12}])).to_list(None)
    return {
        "totalUsers": await users.count_documents({"isActive": True}),
        "usersByRole": by_role,
        "newUsersLast30Days": await users.count_documents({
            "isActive": True, "createdAt": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}}),
        "usersWithAdoptions": await users.count_documents({
            "isActive": True, "adoptionHistory": {"$exists": True, "$not": {"$size": 0}}}),
        "monthlyRegistrations": monthly,
    }


async def _target(user_id: str) -> dict:
    uid = oid(user_id)
    target = await get_db().users.find_one({"_id": uid}, {"password": 0}) if uid else None
    if not target:
        raise _err(404, "找不到此使用者")
    return target


@router.get("/admin/{user_id}", summary="使用者詳情（管理員）")
async def admin_get(user_id: str, admin: dict = Depends(require_admin)):
    target = await _target(user_id)
    await populate(target, "adoptionHistory", "adoptions")
    await populate(target.get("adoptionHistory") or [], "pet", "pets", "name species breed photos")
    return user_json(target)


@router.put("/admin/{user_id}/role", summary="更新角色（管理員）")
async def admin_role(user_id: str, body: dict | None = None, admin: dict = Depends(require_admin)):
    role = (body or {}).get("role")
    # 舊版允許 volunteer（不在 User schema 內，存檔會失敗）卻不允許 shelter；改用 User schema 的角色
    if role not in ROLES:
        raise _err(400, "無效的角色類型")
    await _target(user_id)
    await get_db().users.update_one({"_id": oid(user_id)}, {"$set": {
        "role": role, "updatedAt": datetime.now(timezone.utc)}})
    return {"message": "使用者角色更新成功", "user": user_json(await _target(user_id))}


@router.put("/admin/{user_id}/active", summary="啟用／停用帳號（管理員）")
async def admin_active(user_id: str, body: dict | None = None, admin: dict = Depends(require_admin)):
    errors: list = []
    value = cast({"isActive": F("bool")}, {"isActive": (body or {}).get("isActive")}, errors=errors).get("isActive")
    errors += schema_validate({"isActive": F("bool")}, {"isActive": value}, partial=True)
    if errors:
        raise _err(400, "更新使用者狀態失敗", details=", ".join(m for _, m in errors))
    await _target(user_id)
    await get_db().users.update_one({"_id": oid(user_id)}, {"$set": {
        "isActive": value, "updatedAt": datetime.now(timezone.utc)}})
    return {"message": f"使用者帳號已{'啟用' if value else '停用'}", "user": user_json(await _target(user_id))}


@router.get("/{user_id}/adoptions", summary="使用者的認養申請（本人或管理員）")
async def user_adoptions(user_id: str, request: Request, user: dict = Depends(token_user_zh)):
    if user_id != str(user["_id"]) and user.get("role") not in ("admin", "volunteer"):
        raise _err(403, "沒有權限查看此使用者的認養申請")
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 10)
    query: dict = {"applicant": oid(user_id)}
    if q.get("status"):
        query["status"] = q["status"]
    docs = await get_db().adoptions.find(query, {"rawSubmission": 0}).sort("createdAt", -1) \
        .skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "pet", "pets", "name species breed photos adoptionStatus")
    total = await get_db().adoptions.count_documents(query)
    return {"adoptions": [adoption_json(d) for d in docs], "pagination": _pagination(page, limit, total)}
