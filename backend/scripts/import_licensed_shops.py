"""匯入農業部「合法特定寵物業名單」到 licensedshops，對應舊版 scripts/import-moa-licensed-shops.js。

預設只做 dry-run；加上 --run 才會寫入。可用 --top N 限制筆數、--sample N 隨機抽樣。
用法（在 backend/ 目錄）：python -m scripts.import_licensed_shops --top 50 --run
"""
import argparse
import asyncio
import json
import random
import re
from datetime import datetime, timezone

from app.config import get_settings
from app.db import close, connect, get_db
from app.services import gov_data


def parse_date(raw):
    if not raw:
        return None
    s = re.sub("上午|下午", "", str(raw)).strip().replace("/", "-")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def map_record(rec: dict) -> dict:
    return {
        "govId": str(rec.get("ID") or rec.get("id") or ""),
        "legalType": rec.get("legaltype"),
        "name": rec.get("legalname") or rec.get("legal_name"),
        "address": rec.get("legaladdress"),
        "businessItem": rec.get("busitem"),
        "animalType": rec.get("animaltype"),
        "validNumber": rec.get("validnum"),
        "validDate": parse_date(rec.get("validdate")),
        "ownerName": rec.get("own_name"),
        "bossName": rec.get("bos_name"),
        "rankYear": rec.get("rank_year"),
        "rankCode": rec.get("rank_code"),
        "rankFlags": [f for f in (rec.get("rank_flag_1"), rec.get("rank_flag_2")) if f],
        "rankText": rec.get("rank_text"),
        "stateFlag": rec.get("state_flag"),
        "originalData": rec,
    }


async def upsert(records: list[dict]) -> int:
    count = 0
    for item in records:
        if not item["govId"] or not item["name"]:
            continue
        await get_db().licensedshops.update_one(
            {"govId": item["govId"]},
            {"$set": item, "$setOnInsert": {"importedAt": datetime.now(timezone.utc)}}, upsert=True)
        count += 1
    return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="真的寫入資料庫")
    parser.add_argument("--top", type=int)
    parser.add_argument("--sample", type=int)
    args = parser.parse_args()
    print("執行模式:", "寫入" if args.run else "dry-run（不寫入）")
    params: dict = {"UnitId": gov_data.LICENSED_SHOP_UNIT_ID}
    if args.top:
        params["$top"] = args.top
    rows = await gov_data.fetch(params, timeout=60)
    records = [map_record(r) for r in rows]
    if args.sample and args.sample < len(records):
        records = random.sample(records, args.sample)
    print("取得筆數:", len(records))
    if not args.run:
        print("缺少必要欄位的筆數:", sum(1 for r in records if not r["govId"] or not r["name"]))
        print(json.dumps(records[:3], ensure_ascii=False, default=str, indent=2))
        print("若要寫入資料庫，請加上 --run")
        return
    connect(get_settings())
    try:
        print("寫入完成，upserted:", await upsert(records))
    finally:
        await close()


if __name__ == "__main__":
    asyncio.run(main())
