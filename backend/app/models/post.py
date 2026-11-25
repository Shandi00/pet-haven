"""posts collection：對應舊版 models/Post.js。"""
import math
import re
from datetime import datetime, timezone

from bson import ObjectId

from app.core.schema import Arr, F, MongooseError, apply_defaults, cast, validate
from app.core.serialize import to_json
from app.db import get_db

CATEGORIES = ("adoption-story", "care-tips", "health-info", "training", "general-discussion", "lost-found",
              "announcement", "volunteer", "donation", "other")
TYPES = ("general", "lost-pet", "found-pet", "adoption-story")
STATUSES = ("draft", "published", "archived", "deleted", "found")

SCHEMA = {
    "title": F("str", required="文章標題為必填項目", trim=True, maxlength=(100, "標題不能超過 100 個字元")),
    "content": F("str", required="文章內容為必填項目", trim=True, minlength=(10, "內容至少需要 10 個字元"),
                 maxlength=(5000, "內容不能超過 5000 個字元")),
    "excerpt": F("str", maxlength=(200, "摘要不能超過 200 個字元")),
    "author": F("oid", required="作者為必填項目"),
    "category": F("str", enum=CATEGORIES, enum_msg="請選擇有效的文章分類", default="general-discussion"),
    "type": F("str", required="貼文類型為必填項目", enum=TYPES, enum_msg="請選擇有效的貼文類型", default="general"),
    "tags": Arr(F("str", trim=True, maxlength=(30, "標籤不能超過 30 個字元"))),
    "relatedPets": Arr(F("oid")),
    "images": Arr({
        "url": F("str", required=True), "filename": F("str", required=True),
        "caption": F("str", maxlength=(200, "圖片說明不能超過 200 個字元")),
        "alt": F("str", maxlength=(100, "Alt 文字不能超過 100 個字元")),
    }),
    "status": F("str", enum=STATUSES, enum_msg="請選擇有效的文章狀態", default="published"),
    "publishedAt": F("date"),
    "deletedAt": F("date", default=None),
    "lostPetInfo": {
        "petName": F("str", trim=True, maxlength=(50, "寵物名稱不能超過 50 個字元")),
        "species": F("str", enum=("dog", "cat", "other")),
        "lastSeenLocation": F("str", trim=True, maxlength=(200, "最後出現地點不能超過 200 個字元")),
        "lastSeenDate": F("date"),
        "contactPhone": F("str", trim=True, match=(r"^09\d{8}$", "請輸入有效的手機號碼格式 (09xxxxxxxx)")),
        "reward": F("num", min=(0, "懸賞金額不能為負數")),
    },
    "stats": {"views": F("num", default=0), "likes": F("num", default=0), "comments": F("num", default=0),
              "shares": F("num", default=0)},
    "likedBy": Arr(F("oid")),
    "isPinned": F("bool", default=False),
    "isFeatured": F("bool", default=False),
    "slug": F("str", trim=True),
    "metaDescription": F("str", maxlength=(160, "Meta 描述不能超過 160 個字元")),
    "moderationStatus": F("str", enum=("pending", "approved", "rejected", "flagged"), default="pending"),
    "moderatedBy": F("oid"),
    "moderatedAt": F("date"),
    "allowComments": F("bool", default=True),
    "location": {"type": F("str", enum=("Point",)), "coordinates": Arr(F("num")),
                 "address": F("str", maxlength=(200, "地址不能超過 200 個字元"))},
}


def make_slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9一-龥]", "-", title.lower())
    return re.sub(r"^-|-$", "", re.sub(r"-+", "-", s))


async def _unique_slug(base: str) -> str:
    # 舊版 slug 有 unique 索引但同標題會衝突而發文失敗；重複時加上短後綴
    slug = base
    while await get_db().posts.find_one({"slug": slug}, {"_id": 1}):
        slug = f"{base}-{str(ObjectId())[-6:]}"
    return slug


def run_save_hooks(doc: dict) -> None:
    if doc.get("status") == "published" and not doc.get("publishedAt"):
        doc["publishedAt"] = datetime.now(timezone.utc)
    content = doc.get("content")
    if not doc.get("excerpt") and content:
        doc["excerpt"] = content[:200] + ("..." if len(content) > 200 else "")


async def prepare_new_post(data: dict) -> dict:
    errors: list = []
    doc = cast(SCHEMA, data, errors=errors)
    apply_defaults(SCHEMA, doc)
    # 空的 location 不存，避免 2dsphere 索引無法解析
    if not (doc.get("location") or {}).get("coordinates"):
        doc.pop("location", None)
    run_save_hooks(doc)
    errors += validate(SCHEMA, doc)
    if errors:
        raise MongooseError(errors, "Post")
    if not doc.get("slug") and doc.get("title"):
        doc["slug"] = await _unique_slug(make_slug(doc["title"]))
    now = datetime.now(timezone.utc)
    doc.update(createdAt=now, updatedAt=now, __v=0)
    return doc


def post_json(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    out = to_json(doc)
    out["url"] = f"/posts/{doc.get('slug') or doc.get('_id')}"
    content = doc.get("content")
    if isinstance(content, str):
        out["readingTime"] = math.ceil(len(content.split(" ")) / 200)
    return out
