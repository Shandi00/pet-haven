"""/api/posts：對應舊版 routes/posts.js（社群討論區、走失協尋）。"""
import json
import math
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.forms import read_body
from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import MongooseError, cast, validate as schema_validate
from app.core.uploads import save_images
from app.core.validation import A, ANY, N, O, S, validate
from app.db import get_db
from app.deps import current_user, optional_user
from app.models.comment import comment_json
from app.models.notification import safe_notify
from app.models.post import CATEGORIES, SCHEMA, STATUSES, post_json, prepare_new_post, run_save_hooks
from app.responses import ApiError, RawError

router = APIRouter(prefix="/api/posts", tags=["Posts"])

AUTHOR_BRIEF = "username firstName lastName avatar_url"
CREATE_SCHEMA = O({
    "title": S(required=True, max=100, msgs={"any.required": "標題為必填欄位", "string.max": "標題不能超過 100 個字元"}),
    "content": S(required=True, min=10, max=5000, msgs={"string.min": "內容至少 10 個字元", "any.required": "內容為必填欄位"}),
    "type": S(valid=("general", "lost-pet", "found-pet", "adoption-story"), default="general"),
    "category": S(valid=CATEGORIES),
    "tags": A(S(max=20), max=10),
    "relatedPets": A(S()),
    "status": S(valid=("draft", "published", "archived"), default="published"),
    "lostPetInfo": ANY(),
})
LOST_PET_SCHEMA = O({
    "petName": S(max=50), "species": S(valid=("dog", "cat", "other")), "lastSeenLocation": S(max=200),
    "lastSeenDate": ANY(), "contactPhone": S(pattern=r"^09\d{8}$"), "reward": N(min=0),
})
UPDATE_SCHEMA = O({
    "title": S(min=5, max=100), "content": S(min=10, max=5000), "images": A(S(uri=True), max=10),
    "tags": A(S(max=20), max=10), "status": S(valid=("active", "resolved", "closed")),
}, min_keys=1)
TYPE_TO_CATEGORY = {"lost-pet": "lost-found", "found-pet": "lost-found", "adoption-story": "adoption-story",
                    "general": "general-discussion"}
CATEGORY_LABELS = [("adoption-story", "認養故事"), ("care-tips", "照護技巧"), ("health-info", "健康資訊"),
                   ("training", "訓練方法"), ("general-discussion", "一般討論"), ("lost-found", "走失協尋"),
                   ("announcement", "公告通知"), ("volunteer", "志工招募"), ("donation", "捐助相關"), ("other", "其他")]


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_list(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


async def _saved_ids(user: dict | None) -> set:
    if not user:
        return set()
    full = await get_db().users.find_one({"_id": user["_id"]}, {"collections": 1}) or {}
    return {str(x) for x in full.get("collections") or []}


def _with_status(post: dict, user: dict | None, saved: set) -> dict:
    out = post_json(post)
    out["isSaved"] = str(post["_id"]) in saved
    out["isLiked"] = bool(user) and any(same_id(x, user["_id"]) for x in post.get("likedBy") or [])
    return out


@router.get("", summary="貼文列表")
async def list_posts(request: Request, user: dict | None = Depends(optional_user)):
    q = request.query_params
    page, limit = _int(q.get("page"), 1), _int(q.get("limit"), 15)
    filters: dict = {"status": "published"}
    for key in ("type", "category"):
        if q.get(key):
            filters[key] = q[key]
    if q.get("tags"):
        filters["tags"] = {"$in": q["tags"].split(",")}
    if q.get("author"):
        filters["author"] = oid(q["author"]) or q["author"]
    if q.get("featured") == "true":
        filters["isFeatured"] = True
    if q.get("search"):
        rx = re.compile(re.escape(q["search"]), re.I)
        filters["$or"] = [{"title": rx}, {"content": rx}, {"tags": rx}]
    sort = {"views": "stats.views", "likes": "stats.likes", "comments": "stats.comments"}.get(q.get("sort"),
                                                                                             "publishedAt")
    posts = await get_db().posts.find(filters).sort(sort, -1).skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(posts, "author", "users", AUTHOR_BRIEF)
    await populate(posts, "relatedPets", "pets", "name species photos")
    total = await get_db().posts.count_documents(filters)
    saved = await _saved_ids(user)
    total_pages = math.ceil(total / limit) if limit else 0
    payload = {"posts": [_with_status(p, user, saved) for p in posts], "pagination": {
        "page": page, "limit": limit, "totalItems": total, "totalPages": total_pages,
        "hasPrevPage": page > 1, "hasNextPage": page < total_pages}}
    # 舊版同時提供 { posts, pagination } 與 { success, data } 兩種格式
    return {"success": True, "data": payload, **payload}


@router.get("/categories/list", summary="貼文分類")
async def categories():
    return {"success": True, "data": [{"value": v, "label": label} for v, label in CATEGORY_LABELS]}


async def _find(post_id: str) -> dict:
    pid = oid(post_id)
    post = await get_db().posts.find_one({"_id": pid}) if pid else None
    if not post:
        raise HTTPException(404, "找不到指定的文章")
    return post


@router.get("/{post_id}", summary="貼文詳情（含留言）")
async def get_post(post_id: str, user: dict | None = Depends(optional_user)):
    post = await _find(post_id)
    await get_db().posts.update_one({"_id": post["_id"]}, {"$inc": {"stats.views": 1}})
    post.setdefault("stats", {})["views"] = (post.get("stats") or {}).get("views", 0) + 1
    await populate(post, "author", "users", AUTHOR_BRIEF + " introduction")
    await populate(post, "relatedPets", "pets", "name species breed photos adoptionStatus")
    comments = await get_db().comments.find({"post": post["_id"]}).to_list(None)
    await populate(comments, "author", "users", AUTHOR_BRIEF)
    out =_with_status(post, user, await _saved_ids(user))
    out["comments"] = [comment_json(c) for c in comments]
    return {"success": True, "data": out}


@router.post("", status_code=201, summary="發表貼文（multipart，圖片欄位 images，最多 5 張）")
async def create_post(request: Request, user: dict = Depends(current_user)):
    body, files = await read_body(request, "images")
    for key in ("lostPetInfo", "tags", "relatedPets"):
        if key in body:
            body[key] = _json_list(body[key])
    data = validate(CREATE_SCHEMA, body)
    lost = data.get("lostPetInfo")
    if lost is not None:
        if data["type"] not in ("lost-pet", "found-pet"):
            # Joi.when(...).otherwise(Joi.forbidden())
            raise RawError(400, {"success": False, "error": {
                "code": "VALIDATION_ERROR", "message": "輸入驗證失敗",
                "details": [{"field": "lostPetInfo", "message": '"lostPetInfo" is not allowed'}]}})
        lost = validate(LOST_PET_SCHEMA, lost)
    saved = await save_images(files, "posts", "images", max_files=5)
    status = data["status"]
    post_data = {
        "title": data["title"], "content": data["content"], "type": data["type"],
        "category": data.get("category") or TYPE_TO_CATEGORY.get(data["type"], "general-discussion"),
        "author": user["_id"], "status": status,
        "images": [{"url": f["path"], "filename": f["filename"], "caption": "", "alt": data["title"]} for f in saved],
        "publishedAt": datetime.now(timezone.utc) if status == "published" else None,
    }
    if data.get("tags"):
        post_data["tags"] = data["tags"]
    if data.get("relatedPets"):
        post_data["relatedPets"] = data["relatedPets"]
    if lost:
        post_data["lostPetInfo"] = lost
    try:
        doc = await prepare_new_post(post_data)
    except MongooseError as e:
        raise ApiError(500, "建立文章失敗", error=str(e))
    doc["_id"] = (await get_db().posts.insert_one(doc)).inserted_id
    await populate(doc, "author", "users", AUTHOR_BRIEF)
    return {"success": True, "message": "文章建立成功", "data": post_json(doc)}


def _check_owner(post: dict, user: dict, message: str) -> None:
    if not same_id(post.get("author"), user["_id"]) and user.get("role") != "admin":
        raise HTTPException(403, message)


async def _save(post: dict, sets: dict, error_message: str) -> dict:
    """pet.save() 的對應：套用 hook、驗證整份文件，再寫回變動欄位。"""
    merged = {**post, **sets}
    run_save_hooks(merged)
    errors = schema_validate(SCHEMA, merged)
    if errors:
        raise ApiError(500, error_message, error="Post validation failed: " + ", ".join(f"{p}: {m}" for p, m in errors))
    changed = {k: merged[k] for k in set(sets) | {"publishedAt", "excerpt"} if k in merged}
    changed["updatedAt"] = datetime.now(timezone.utc)
    await get_db().posts.update_one({"_id": post["_id"]}, {"$set": changed})
    return {**merged, **changed}


@router.put("/{post_id}", summary="編輯貼文（作者或管理員）")
async def update_post(post_id: str, request: Request, user: dict = Depends(current_user)):
    body, files = await read_body(request, "images")
    if "tags" in body:
        body["tags"] = _json_list(body["tags"])
    data = validate(UPDATE_SCHEMA, body)
    post = await _find(post_id)
    _check_owner(post, user, "沒有權限修改此文章")
    # 舊版會把沒傳的欄位設成 undefined 而存檔失敗；改成只更新有傳的欄位
    sets = {k: data[k] for k in ("title", "content", "status", "tags") if k in data}
    sets = cast(SCHEMA, sets)
    if files:
        saved = await save_images(files, "posts", "images", max_files=5)
        sets["images"] = list(post.get("images") or []) + cast(SCHEMA, {"images": [
            {"url": f["path"], "filename": f["filename"], "caption": "", "alt": data.get("title") or post.get("title")}
            for f in saved]})["images"]
    updated = await _save(post, sets, "更新文章失敗")
    await populate(updated, "author", "users", AUTHOR_BRIEF)
    return {"success": True, "message": "文章更新成功", "data": post_json(updated)}


@router.delete("/{post_id}", summary="刪除貼文（軟刪除）")
async def delete_post(post_id: str, user: dict = Depends(current_user)):
    post = await _find(post_id)
    _check_owner(post, user, "沒有權限刪除此文章")
    await get_db().posts.update_one({"_id": post["_id"]}, {"$set": {
        "status": "deleted", "deletedAt": datetime.now(timezone.utc), "updatedAt": datetime.now(timezone.utc)}})
    return {"success": True, "message": "文章已刪除"}


@router.post("/{post_id}/like", summary="按讚／取消按讚")
async def like_post(post_id: str, user: dict = Depends(current_user)):
    post = await _find(post_id)
    liked = any(same_id(x, user["_id"]) for x in post.get("likedBy") or [])
    if liked:
        op = {"$pull": {"likedBy": user["_id"]}, "$inc": {"stats.likes": -1}}
    else:
        op = {"$addToSet": {"likedBy": user["_id"]}, "$inc": {"stats.likes": 1}}
    await get_db().posts.update_one({"_id": post["_id"]}, op)
    likes = max(0, ((post.get("stats") or {}).get("likes") or 0) + (-1 if liked else 1))
    if not liked and not same_id(post.get("author"), user["_id"]):
        await safe_notify({
            "recipient": post["author"], "sender": user["_id"], "type": "like", "title": "按讚通知",
            "content": f"{user.get('username') or user.get('firstName')} 喜歡您的貼文",
            "relatedPost": post["_id"], "link": f"/community/{post['_id']}", "priority": "low",
        })
    return {"success": True, "message": "操作成功", "data": {"liked": not liked, "likesCount": likes}}


@router.patch("/{post_id}/status", summary="更新貼文狀態（例如走失協尋標記已尋獲）")
async def patch_status(post_id: str, body: dict | None = None, user: dict = Depends(current_user)):
    if oid(post_id) is None:
        raise HTTPException(400, "無效的 ID 格式")
    status = (body or {}).get("status")
    if status not in STATUSES:
        raise HTTPException(400, "無效的狀態值")
    post = await _find(post_id)
    _check_owner(post, user, "無權限修改此文章")
    updated = await _save(post, {"status": status}, "更新狀態失敗")
    return {"success": True, "message": "狀態更新成功", "data": post_json(updated)}
