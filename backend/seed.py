"""載入展示測資，對應舊版 seed.js。可以重複執行：帳號與同名寵物已存在就略過。

用法（在專案根目錄）：npm run seed
加上 --clear 會先刪除所有寵物。測試帳號只能用在本機與 CI（見 AGENTS.md）。
"""
import asyncio
import json
import sys
from pathlib import Path

from app.config import get_settings
from app.core.schema import MongooseError
from app.core.security import hash_password
from app.db import close, connect, get_db
from app.models.pet import prepare_new_pet
from app.models.user import new_user_doc

SHELTER = {
    "username": "lovepets_shelter", "name": "愛心收容所", "email": "shelter@example.com",
    "firstName": "愛心", "lastName": "收容所", "role": "shelter",
    "address": {"city": "台北市", "district": "大安區", "street": "愛心路100號"},
}
# repo 是公開的，這組預設密碼人人都知道；展示機請設定 SEED_SHELTER_PASSWORD
DEFAULT_SHELTER_PASSWORD = "shelter123"


def shelter_password() -> str:
    return get_settings().seed_shelter_password.get_secret_value() or DEFAULT_SHELTER_PASSWORD


async def seed(clear: bool = False) -> dict:
    db = get_db()
    shelter = await db.users.find_one({"email": SHELTER["email"]})
    custom = get_settings().seed_shelter_password.get_secret_value()
    if shelter:
        print(" 使用現有收容所帳號")
        if custom:
            # 資料庫可能先前用預設密碼 seed 過，有設定時一律換成指定的密碼
            await db.users.update_one({"_id": shelter["_id"]}, {"$set": {"password": hash_password(custom)}})
            print(" 已依 SEED_SHELTER_PASSWORD 更新收容所密碼")
    else:
        shelter = new_user_doc(**SHELTER, password=hash_password(shelter_password()))
        shelter["_id"] = (await db.users.insert_one(shelter)).inserted_id
        print(f" 收容所帳號已建立：{SHELTER['email']}")
    if clear:
        await db.pets.delete_many({})
        print("  已清除現有寵物資料")
    added = skipped = 0
    pets = json.loads((Path(__file__).parent / "app" / "seed_pets.json").read_text(encoding="utf-8"))
    for data in pets:
        if await db.pets.find_one({"name": data["name"]}, {"_id": 1}):
            print(f"  {data['name']} 已存在,跳過")
            skipped += 1
            continue
        try:
            doc = prepare_new_pet({**data, "createdBy": shelter["_id"]})
        except MongooseError as e:
            print(f" 載入 {data['name']} 失敗: {e}")
            continue
        await db.pets.insert_one(doc)
        added += 1
        print(f" 已新增: {data['name']} ({data['breed']})")
    return {"shelter": shelter["_id"], "added": added, "skipped": skipped}


async def main() -> None:
    connect(get_settings())
    try:
        result = await seed("--clear" in sys.argv)
        print(f"\n 完成：新增 {result['added']} 隻，略過 {result['skipped']} 隻")
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(main())
