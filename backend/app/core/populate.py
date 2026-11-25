"""Mongoose populate()：把參照的 ObjectId 換成文件（只取指定欄位）。路徑可以穿過子文件陣列，例如 reviewNotes.reviewer。"""
from typing import Any, Callable

from bson import ObjectId

from app.db import get_db


def _walk(node: Any, parts: list[str], fn: Callable[[dict, str], None]) -> None:
    if isinstance(node, list):
        for item in node:
            _walk(item, parts, fn)
        return
    if not isinstance(node, dict):
        return
    if len(parts) == 1:
        fn(node, parts[0])
    else:
        _walk(node.get(parts[0]), parts[1:], fn)


async def populate(docs: list[dict] | dict | None, path: str, collection: str, select: str = "") -> Any:
    """單一參照找不到時設為 None；參照陣列中找不到的移除（同 Mongoose）。select 以空白分隔，前面加 - 表示排除。"""
    if docs is None:
        return None
    parts = path.split(".")
    ids: set[ObjectId] = set()

    def collect(parent: dict, key: str) -> None:
        v = parent.get(key)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, ObjectId):
                ids.add(x)

    _walk(docs, parts, collect)
    found: dict = {}
    if ids:
        fields = select.split()
        if fields and all(f.startswith("-") for f in fields):
            proj = {f[1:]: 0 for f in fields}
        elif fields:
            proj = {f: 1 for f in fields}
        else:
            proj = {"password": 0}
        if collection == "users" and "password" not in proj and not any(v == 1 for v in proj.values()):
            proj["password"] = 0
        async for f in get_db()[collection].find({"_id": {"$in": list(ids)}}, proj):
            found[f["_id"]] = f

    def replace(parent: dict, key: str) -> None:
        v = parent.get(key)
        if isinstance(v, list):
            parent[key] = [found[x] if isinstance(x, ObjectId) else x for x in v
                           if not isinstance(x, ObjectId) or x in found]
        elif isinstance(v, ObjectId):
            parent[key] = found.get(v)

    _walk(docs, parts, replace)
    return docs
