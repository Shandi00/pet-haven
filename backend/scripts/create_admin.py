"""建立管理員帳號，對應舊版 create-admin.js。

舊版把密碼寫死在程式裡（而且漏了必填的 name，實際上建立不起來）。
這裡改成從 ADMIN_PASSWORD 環境變數或 --password 讀取；都沒有就產生隨機密碼，只印出一次。
用法（在 backend/ 目錄）：python -m scripts.create_admin --email admin@example.com
"""
import argparse
import asyncio
import os
import secrets

from app.config import get_settings
from app.core.security import hash_password
from app.db import close, connect, get_db
from app.models.user import new_user_doc


async def create_admin(email: str, username: str, password: str) -> tuple[bool, dict]:
    users = get_db().users
    existing = await users.find_one({"$or": [{"email": email.lower()}, {"username": username}]})
    if existing:
        return False, existing
    doc = new_user_doc(username=username, email=email.lower(), password=hash_password(password),
                       name="系統管理員", firstName="系統", lastName="管理員", role="admin", isEmailVerified=True)
    doc["_id"] = (await users.insert_one(doc)).inserted_id
    return True, doc


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="admin@petadoption.com")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    args = parser.parse_args()
    password = args.password or secrets.token_urlsafe(12)
    connect(get_settings())
    try:
        created, user = await create_admin(args.email, args.username, password)
    finally:
        await close()
    if not created:
        print(f"管理員帳號已存在：{user.get('email')}")
        return
    print(f"管理員帳號建立成功：{user['email']}")
    if not args.password:
        print(f"隨機密碼（只顯示這一次，請自行保存）：{password}")


if __name__ == "__main__":
    asyncio.run(main())
