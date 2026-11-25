from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.config import Settings

_client: AsyncMongoClient | None = None
_db_name: str | None = None


def connect(settings: Settings) -> None:
    global _client, _db_name
    # 5 秒逾時：Atlas 連不上時 /api/ready 不會卡住 30 秒
    _client = AsyncMongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
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
