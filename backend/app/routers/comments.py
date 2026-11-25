"""/api/comments：對應舊版 routes/comments.js。"""
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.ids import oid, same_id
from app.core.populate import populate
from app.core.schema import MongooseError
from app.core.validation import O, S, validate
from app.db import get_db
from app.deps import current_user
from app.models.comment import comment_json, prepare_new_comment, update_comment_count
from app.models.notification import safe_notify
from app.responses import ApiError

router = APIRouter(prefix="/api/comments", tags=["Comments"])

AUTHOR_BRIEF = "username firstName lastName avatar_url"
OID = r"^[0-9a-fA-F]{24}$"
CREATE_SCHEMA = O({
    "content": S(required=True, min=1, max=1000, msgs={"any.required": "留言內容為必填欄位"}),
    "post": S(required=True, pattern=OID, msgs={"any.required": "貼文 ID 為必填欄位",
                                                "string.pattern.base": "無效的 ID 格式"}),
    "parentId": S(pattern=OID, msgs={"string.pattern.base": "無效的 ID 格式"}),
})
REPORT_SCHEMA = O({
    "reason": S(required=True, valid=("spam", "inappropriate", "harassment", "misinformation", "other"),
                msgs={"any.only": "請選擇有效的檢舉原因", "any.required": "檢舉原因為必填欄位"}),
    "description": S(max=500, msgs={"string.max": "檢舉說明不能超過 500 個字元"}),
})
EDIT_LIMIT_SECONDS = 15 * 60
REPORT_HIDE_THRESHOLD = 5


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _page(request: Request, default_limit: int) -> tuple[int, int]:
    q = request.query_params
    return _int(q.get("page"), 1), _int(q.get("limit"), default_limit)


def _pagination(page: int, limit: int, total: int) -> dict:
    return {"page": page, "limit": limit, "total": total, "pages": math.ceil(total / limit) if limit else 0}


def _name(user: dict) -> str:
    return user.get("username") or user.get("firstName") or ""


async def _find(comment_id: str) -> dict:
    cid = oid(comment_id)
    doc = await get_db().comments.find_one({"_id": cid}) if cid else None
    if not doc:
        raise HTTPException(404, "找不到指定的評論")
    return doc


async def _post(post_id) -> dict | None:
    pid = oid(post_id)
    return await get_db().posts.find_one({"_id": pid}) if pid else None


@router.get("/post/{post_id}", summary="貼文的留言（不含回覆）")
async def by_post(post_id: str, request: Request):
    if not await _post(post_id):
        raise HTTPException(404, "找不到指定的文章")
    page, limit = _page(request, 20)
    sort = request.query_params.get("sort", "createdAt")
    query = {"post": oid(post_id), "status": "approved", "parentComment": None}
    docs = await get_db().comments.find(query).sort(sort, -1).skip(max(page - 1, 0) * limit).limit(limit).to_list(None)
    await populate(docs, "author", "users", AUTHOR_BRIEF)
    await populate(docs, "replies", "comments")
    for d in docs:
        await populate(d.get("replies") or [], "author", "users", AUTHOR_BRIEF)
    total = await get_db().comments.count_documents(query)
    return {"success": True, "data": {"comments": [comment_json(d) for d in docs],
                                      "pagination": _pagination(page, limit, total)}}


@router.get("/user/{user_id}", summary="某使用者的留言")
async def by_user(user_id: str, request: Request):
    page, limit = _page(request, 20)
    query = {"author": oid(user_id) or user_id, "status": {"$in": ["approved", "pending"]}}
    docs = await get_db().comments.find(query).sort("createdAt", -1).skip(max(page - 1, 0) * limit) \
        .limit(limit).to_list(None)
    await populate(docs, "post", "posts", "title slug")
    total = await get_db().comments.count_documents(query)
    return {"success": True, "data": {"comments": [comment_json(d) for d in docs],
                                      "pagination": _pagination(page, limit, total)}}


@router.get("/{comment_id}/replies", summary="留言的回覆")
async def replies(comment_id: str, request: Request):
    page, limit = _page(request, 10)
    query = {"parentComment": oid(comment_id) or comment_id, "status": "approved"}
    docs = await get_db().comments.find(query).sort("createdAt", 1).skip(max(page - 1, 0) * limit) \
        .limit(limit).to_list(None)
    await populate(docs, "author", "users", AUTHOR_BRIEF)
    total = await get_db().comments.count_documents(query)
    return {"success": True, "data": {"replies": [comment_json(d) for d in docs],
                                      "pagination": _pagination(page, limit, total)}}


async def _create(data: dict, error_message: str) -> dict:
    try:
        doc = prepare_new_comment(data)
    except MongooseError as e:
        raise ApiError(500, error_message, error=str(e))
    doc["_id"] = (await get_db().comments.insert_one(doc)).inserted_id
    await populate(doc, "author", "users", AUTHOR_BRIEF)
    return doc


@router.post("", status_code=201, summary="留言")
async def create(request: Request, body: dict | None = None, user: dict = Depends(current_user)):
    data = validate(CREATE_SCHEMA, body)
    post = await _post(data["post"])
    if not post:
        raise HTTPException(404, "找不到指定的文章")
    if not post.get("allowComments", True):
        raise HTTPException(403, "此文章不允許評論")
    doc = await _create({"content": data["content"], "post": post["_id"], "author": user["_id"],
                         "ipAddress": request.client.host if request.client else None}, "發布評論失敗")
    await update_comment_count(post["_id"])
    if not same_id(post.get("author"), user["_id"]):
        await safe_notify({
            "recipient": post["author"], "sender": user["_id"], "type": "comment", "title": "新留言通知",
            "content": f"{_name(user)} 留言了您的貼文", "relatedPost": post["_id"], "relatedComment": doc["_id"],
            "link": f"/community/{post['_id']}", "priority": "normal",
        })
    return {"success": True, "message": "評論發布成功", "data": comment_json(doc)}


@router.post("/{comment_id}/reply", status_code=201, summary="回覆留言")
async def reply(comment_id: str, request: Request, body: dict | None = None, user: dict = Depends(current_user)):
    content = (body or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(400, "回覆內容不能為空")
    if len(content) > 1000:
        raise HTTPException(400, "回覆內容不能超過 1000 個字元")
    parent = await _find(comment_id)
    post = await _post(parent.get("post"))
    if not post or not post.get("allowComments", True):
        raise HTTPException(403, "此文章不允許評論")
    doc = await _create({"content": content, "post": parent["post"], "author": user["_id"],
                         "parentComment": parent["_id"],
                         "ipAddress": request.client.host if request.client else None}, "發布回覆失敗")
    await get_db().comments.update_one({"_id": parent["_id"]}, {"$addToSet": {"replies": doc["_id"]}})
    await update_comment_count(post["_id"])
    if not same_id(parent.get("author"), user["_id"]):
        await safe_notify({
            "recipient": parent["author"], "sender": user["_id"], "type": "reply", "title": "新回覆通知",
            "content": f"{_name(user)} 回覆了您的留言", "relatedPost": parent["post"], "relatedComment": doc["_id"],
            "link": f"/community/{parent['post']}", "priority": "normal",
        })
    return {"success": True, "message": "回覆發布成功", "data": comment_json(doc)}


@router.put("/{comment_id}", summary="編輯留言（15 分鐘內）")
async def edit(comment_id: str, body: dict | None = None, user: dict = Depends(current_user)):
    data = validate(CREATE_SCHEMA, body)
    comment = await _find(comment_id)
    if not same_id(comment.get("author"), user["_id"]):
        raise HTTPException(403, "沒有權限修改此評論")
    created = comment["createdAt"] if comment["createdAt"].tzinfo else comment["createdAt"].replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - created).total_seconds() > EDIT_LIMIT_SECONDS:
        raise HTTPException(403, "評論發布超過 15 分鐘後無法編輯")
    now = datetime.now(timezone.utc)
    content = data["content"].strip()
    sets: dict = {"updatedAt": now}
    push = None
    if content != comment.get("content"):
        sets.update(content=content, isEdited=True)
        push = {"editHistory": {"content": content, "editedAt": now}}
    await get_db().comments.update_one({"_id": comment["_id"]}, {"$set": sets, **({"$push": push} if push else {})})
    updated = await _find(comment_id)
    await populate(updated, "author", "users", AUTHOR_BRIEF)
    return {"success": True, "message": "評論編輯成功", "data": comment_json(updated)}


@router.delete("/{comment_id}", summary="刪除留言（隱藏）")
async def delete(comment_id: str, user: dict = Depends(current_user)):
    comment = await _find(comment_id)
    if not same_id(comment.get("author"), user["_id"]) and user.get("role") != "admin":
        raise HTTPException(403, "沒有權限刪除此評論")
    await get_db().comments.update_one({"_id": comment["_id"]}, {"$set": {
        "status": "hidden", "updatedAt": datetime.now(timezone.utc)}})
    if await _post(comment.get("post")):
        await update_comment_count(comment["post"])
    return {"success": True, "message": "評論已刪除"}


@router.post("/{comment_id}/like", summary="留言按讚／取消")
async def like(comment_id: str, user: dict = Depends(current_user)):
    comment = await _find(comment_id)
    liked = any(same_id(x, user["_id"]) for x in comment.get("likedBy") or [])
    op = ({"$pull": {"likedBy": user["_id"]}, "$inc": {"likes": -1}} if liked
          else {"$addToSet": {"likedBy": user["_id"]}, "$inc": {"likes": 1}})
    await get_db().comments.update_one({"_id": comment["_id"]}, op)
    if not liked and not same_id(comment.get("author"), user["_id"]):
        await safe_notify({
            "recipient": comment["author"], "sender": user["_id"], "type": "like", "title": "按讚通知",
            "content": f"{_name(user)} 喜歡您的留言", "relatedComment": comment["_id"],
            "relatedPost": comment.get("post"), "link": f"/community/{comment.get('post')}", "priority": "low",
        })
    likes = max(0, (comment.get("likes") or 0) + (-1 if liked else 1))
    return {"success": True, "message": "操作成功", "data": {"liked": not liked, "likesCount": likes}}


@router.post("/{comment_id}/report", summary="檢舉留言")
async def report(comment_id: str, body: dict | None = None, user: dict = Depends(current_user)):
    data = validate(REPORT_SCHEMA, body)
    comment = await _find(comment_id)
    if any(same_id(r.get("reporter"), user["_id"]) for r in comment.get("reports") or []):
        raise HTTPException(400, "您已經檢舉過此評論")
    entry = {"reporter": user["_id"], "reason": data["reason"], "description": data.get("description"),
             "reportedAt": datetime.now(timezone.utc)}
    sets = {"updatedAt": datetime.now(timezone.utc)}
    if len(comment.get("reports") or []) + 1 >= REPORT_HIDE_THRESHOLD:
        sets["status"] = "hidden"
    await get_db().comments.update_one({"_id": comment["_id"]}, {"$push": {"reports": entry}, "$set": sets})
    return {"success": True, "message": "檢舉已提交，我們會盡快處理"}
