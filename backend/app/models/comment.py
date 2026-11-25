"""comments collection：對應舊版 models/Comment.js。"""
from datetime import datetime, timezone

from app.core.schema import Arr, F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json
from app.db import get_db

SCHEMA = {
    "content": F("str", required="評論內容為必填項目", trim=True, minlength=(1, "評論內容至少需要 1 個字元"),
                 maxlength=(1000, "評論內容不能超過 1000 個字元")),
    "post": F("oid", required="所屬文章為必填項目"),
    "author": F("oid", required="評論作者為必填項目"),
    "parentComment": F("oid", default=None),
    "replies": Arr(F("oid")),
    "status": F("str", enum=("pending", "approved", "rejected", "hidden"), enum_msg="請選擇有效的評論狀態",
                default="approved"),
    "likes": F("num", default=0),
    "likedBy": Arr(F("oid")),
    "reports": Arr({
        "reporter": F("oid", required=True),
        "reason": F("str", enum=("spam", "inappropriate", "harassment", "misinformation", "other"), required=True),
        "description": F("str", maxlength=(500, "檢舉說明不能超過 500 個字元")),
        "reportedAt": F("date", default=lambda: datetime.now(timezone.utc)),
    }),
    "moderatedBy": F("oid"),
    "moderatedAt": F("date"),
    "moderationReason": F("str", maxlength=(200, "審核原因不能超過 200 個字元")),
    "editHistory": Arr({"content": F("str"), "editedAt": F("date", default=lambda: datetime.now(timezone.utc))}),
    "isEdited": F("bool", default=False),
    "ipAddress": F("str"),
    "sortWeight": F("num", default=0),
}


def prepare_new_comment(data: dict) -> dict:
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Comment")
    now = datetime.now(timezone.utc)
    doc.update(createdAt=now, updatedAt=now, __v=0)
    return doc


def comment_json(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    out = to_json(doc)
    out["replyCount"] = len(doc.get("replies") or [])
    out["isReply"] = doc.get("parentComment") is not None
    out["level"] = 1 if doc.get("parentComment") else 0
    return out


async def update_comment_count(post_id) -> int:
    """post.updateCommentCount()：重新計算已核准留言數。"""
    count = await get_db().comments.count_documents({"post": post_id, "status": "approved"})
    await get_db().posts.update_one({"_id": post_id}, {"$set": {"stats.comments": count}})
    return count
