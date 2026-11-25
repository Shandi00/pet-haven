import logging

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.config import Settings

logger = logging.getLogger(__name__)

_client: AsyncMongoClient | None = None
_db_name: str | None = None

# 舊版由 Mongoose autoIndex 建立；新資料庫沒有這些索引，unique 尤其重要（避免重複 email）
INDEXES = {
    "users": [([("email", ASCENDING)], {"unique": True}),
              ([("googleId", ASCENDING)], {"unique": True, "sparse": True}),
              ([("google_id", ASCENDING)], {"unique": True, "sparse": True}),
              ([("username", ASCENDING)], {})],
    "pets": [([("govData.animalId", ASCENDING)], {"unique": True, "sparse": True}),
             ([("adoptionStatus", ASCENDING), ("isActive", ASCENDING)], {}),
             ([("createdBy", ASCENDING)], {}),
             ([("createdAt", DESCENDING)], {})],
    "adoptions": [([("applicationId", ASCENDING)], {"unique": True, "sparse": True}),
                  ([("pet", ASCENDING), ("status", ASCENDING)], {}),
                  ([("applicant", ASCENDING), ("createdAt", DESCENDING)], {})],
    "notifications": [([("recipient", ASCENDING), ("isRead", ASCENDING)], {})],
    "messages": [([("conversationId", ASCENDING)], {})],
    "posts": [([("slug", ASCENDING)], {"unique": True, "sparse": True}),
              ([("status", ASCENDING), ("publishedAt", DESCENDING)], {})],
    "comments": [([("post", ASCENDING), ("status", ASCENDING), ("createdAt", DESCENDING)], {})],
    "licensedshops": [([("govId", ASCENDING)], {"unique": True})],
}


def connect(settings: Settings) -> None:
    global _client, _db_name
    # 5 秒逾時：Atlas 連不上時 /api/ready 不會卡住 30 秒；tz_aware 讓讀回的日期都帶時區
    _client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    _db_name = settings.mongodb_db


async def close() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_db() -> AsyncDatabase:
    if _client is None:
        raise RuntimeError("資料庫尚未連線")
    return _client[_db_name]


async def is_db_ready() -> bool:
    if _client is None:
        return False
    try:
        await _client.admin.command("ping")
        return True
    except PyMongoError:
        return False


async def ensure_indexes() -> None:
    """啟動時建立索引；失敗（例如資料庫連不上、既有資料重複）只記錄，不讓伺服器起不來。"""
    db = get_db()
    for collection, specs in INDEXES.items():
        for keys, options in specs:
            try:
                await db[collection].create_index(keys, **options)
            except PyMongoError as e:
                logger.warning("建立索引失敗 %s %s：%s", collection, keys, e)
