"""Mongoose populate()：把參照的 ObjectId 換成文件（只取指定欄位）。"""
from typing import Any

from bson import ObjectId

from app.db import get_db


def _fields(select: str) -> dict:
    return {f: 1 for f in select.split()}


def _get(doc: dict, path: str):
    cur: Any = doc
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _set(doc: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


async def populate(docs: list[dict] | dict | None, path: str, collection: str, select: str = "") -> Any:
    """支援單一參照或參照陣列；找不到的單一參照設為 None，陣列中找不到的移除（同 Mongoose）。"""
    if docs is None:
        return None
    many = isinstance(docs, list)
    items = docs if many else [docs]
    ids: set[ObjectId] = set()
    for d in items:
        v = _get(d, path)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, ObjectId):
                ids.add(x)
            elif isinstance(x, dict) and isinstance(x.get("_id"), ObjectId):
                ids.add(x["_id"])
    found = {}
    if ids:
        proj = _fields(select) if select else {"password": 0}
        async for f in get_db()[collection].find({"_id": {"$in": list(ids)}}, proj):
            found[f["_id"]] = f
    for d in items:
        v = _get(d, path)
        if isinstance(v, list):
            _set(d, path, [found[x] if isinstance(x, ObjectId) else x for x in v
                           if not isinstance(x, ObjectId) or x in found])
        elif isinstance(v, ObjectId):
            _set(d, path, found.get(v))
    return docs
