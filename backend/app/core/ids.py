from typing import Any

from bson import ObjectId
from fastapi import HTTPException


def oid(value: Any) -> ObjectId | None:
    """可以轉成 ObjectId 就轉，不行回 None。"""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, dict) and "_id" in value:
        value = value["_id"]
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    if isinstance(value, ObjectId):
        return value
    return None


def require_oid(value: Any, message: str = "無效的 ID 格式") -> ObjectId:
    result = oid(value)
    if result is None:
        raise HTTPException(400, message)
    return result


def same_id(a: Any, b: Any) -> bool:
    """比較兩個 id；任一方可以是 ObjectId、字串或含 _id 的物件。"""
    x, y = oid(a), oid(b)
    return x is not None and x == y
