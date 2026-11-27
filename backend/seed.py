"""載入展示測資，對應舊版 seed.js。可以重複執行：帳號、同名寵物與示範故事已存在就略過。

用法（在專案根目錄）：npm run seed
加上 --clear 會先刪除所有寵物；在 backend 目錄執行 `.venv/Scripts/python seed.py --remove-demo`
會刪除示範帳號和他們的貼文（正式上線前使用）。測試帳號只能用在本機與 CI（見 AGENTS.md）。
"""
import asyncio
import json
import secrets
import sys
from pathlib import Path

from app.config import get_settings
from app.core.schema import MongooseError
from app.core.security import hash_password
from app.db import close, connect, get_db
from app.models.pet import prepare_new_pet
from app.models.post import prepare_new_post
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


# 首頁「成功故事」的示範資料：原本寫死在 HomePage.js，2026-11-27 改存資料庫（社群的領養故事貼文）。
# 作者是示範帳號：Email 用保留的 .test 網域、密碼隨機產生且不保存（沒有人能登入），貼文標籤加「示範」。
# 不連到 seed 的寵物，避免「小白已找到家」但小白仍在待認養列表上；照片也不和 seed 寵物共用。
# 原本寫死資料裡小白那張其實是潛水照，已換成實際看過內容的狗狗照片。
DEMO_DOMAIN = "demo.pethaven.test"
_UNSPLASH = "https://images.unsplash.com/photo-{}?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=80"
DEMO_STORIES = [
    {"username": "demo_story_1", "nickname": "小白的家人", "title": "小白來到我們家",
     "content": "透過這個平台，我找到了我的最佳夥伴小白。整個認養流程非常順利，工作人員也很貼心。",
     "photo": "1587300003388-59208cc962cb"},
    {"username": "demo_story_2", "nickname": "咪咪的家人", "title": "咪咪成為我們家的一員",
     "content": "這個平台讓我們全家都找到了快樂。咪咪現在是我們家不可或缺的一員。",
     "photo": "1573865526739-10659fec78a5"},
    {"username": "demo_story_3", "nickname": "旺旺的家人", "title": "遇見旺旺之後",
     "content": "感謝平台讓我遇見旺旺，牠改變了我的生活，每天都充滿歡笑。",
     "photo": "1543466835-00a7907e9de1"},
]


async def seed_demo_stories() -> int:
    """建立示範帳號與領養故事，已存在就略過；回傳新增的貼文數。"""
    db = get_db()
    added = 0
    for s in DEMO_STORIES:
        email = f"{s['username']}@{DEMO_DOMAIN}"
        user = await db.users.find_one({"email": email})
        if not user:
            user = new_user_doc(username=s["username"], email=email, firstName=s["nickname"], role="user",
                                password=hash_password(secrets.token_urlsafe(32)))
            user["_id"] = (await db.users.insert_one(user)).inserted_id
        if await db.posts.find_one({"author": user["_id"], "type": "adoption-story", "title": s["title"]}, {"_id": 1}):
            continue
        post = await prepare_new_post({
            "title": s["title"], "content": s["content"], "author": user["_id"], "type": "adoption-story",
            "category": "adoption-story", "tags": ["領養故事", "示範"],
            "images": [{"url": _UNSPLASH.format(s["photo"]), "filename": f"unsplash-{s['photo']}.jpg",
                        "alt": s["title"]}],
        })
        await db.posts.insert_one(post)
        added += 1
        print(f" 已新增示範故事：{s['title']}")
    return added


async def remove_demo() -> dict:
    """刪除示範帳號和他們的貼文、留言（正式上線前使用）。"""
    db = get_db()
    ids = [u["_id"] async for u in db.users.find({"email": {"$regex": f"@{DEMO_DOMAIN.replace('.', '[.]')}$"}},
                                                 {"_id": 1})]
    posts = (await db.posts.delete_many({"author": {"$in": ids}})).deleted_count
    await db.comments.delete_many({"author": {"$in": ids}})
    users = (await db.users.delete_many({"_id": {"$in": ids}})).deleted_count
    return {"users": users, "posts": posts}


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
    stories = await seed_demo_stories()
    return {"shelter": shelter["_id"], "added": added, "skipped": skipped, "stories": stories}


async def main() -> None:
    connect(get_settings())
    try:
        if "--remove-demo" in sys.argv:
            result = await remove_demo()
            print(f" 已刪除示範帳號 {result['users']} 個、示範貼文 {result['posts']} 篇")
            return
        result = await seed("--clear" in sys.argv)
        print(f"\n 完成：新增 {result['added']} 隻，略過 {result['skipped']} 隻；新增示範故事 {result['stories']} 篇")
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(main())
