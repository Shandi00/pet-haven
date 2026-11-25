"""把 MongoDB 文件轉成與 Mongoose toJSON 相同的格式：ObjectId 轉字串、日期轉 ISO、有 _id 的物件補上 id。"""
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def to_json(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return iso(value)
    if isinstance(value, dict):
        out = {k: to_json(v) for k, v in value.items() if k != "password"}
        if "_id" in out and "id" not in out:
            out["id"] = out["_id"]
        return out
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    return value
