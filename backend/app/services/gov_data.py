"""農業部開放資料平台（動物認領養、合法特定寵物業）。"""
import re

import httpx

GOV_API_BASE = "https://data.moa.gov.tw/Service/OpenData/TransService.aspx"
ANIMAL_UNIT_ID = "QcbUEzN6E6DL"
LICENSED_SHOP_UNIT_ID = "fNT9RMo8PQRO"


def odata_literal(value: str) -> str:
    """OData 字串常值：單引號要寫成兩個，避免使用者輸入改變 $filter。"""
    return value.replace("'", "''")


async def fetch(params: dict, timeout: float = 30) -> list:
    """呼叫政府 API，回傳資料陣列；測試時 monkeypatch 這個函式。"""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(GOV_API_BASE, params=params, headers={"Accept": "application/json"})
        r.raise_for_status()
        data = r.json()
    return data if isinstance(data, list) else []


def map_species(kind: str | None) -> str:
    k = (kind or "").lower()
    for words, species in ((("狗", "dog"), "dog"), (("貓", "cat"), "cat"), (("兔", "rabbit"), "rabbit"),
                           (("鳥", "bird"), "bird")):
        if any(w in k for w in words):
            return species
    return "other"


def map_gender(sex: str | None) -> str:
    s = (sex or "").upper()
    if s in ("M", "MALE") or "公" in s:
        return "male"
    if s in ("F", "FEMALE") or "母" in s:
        return "female"
    return "unknown"


def map_size(body: str | None) -> str:
    b = (body or "").lower()
    if "small" in b or "小" in b:
        return "small"
    if "large" in b or "大" in b:
        return "large"
    return "medium"


def map_status(status: str | None) -> str:
    s = (status or "").lower()
    if "已認養" in s or "adopted" in s:
        return "adopted"
    if "其他" in s or "死亡" in s:
        # 舊版回傳 unavailable，不在 Pet 的 adoptionStatus enum 內；改用 not-available
        return "not-available"
    return "available"


def parse_age(age: str | None) -> dict:
    """舊版回傳純數字（存不進 age 物件）；改回傳 { value, unit }。"""
    if not age:
        return {"value": 1, "unit": "years"}
    m = re.search(r"(\d+)", age)
    if m:
        return {"value": int(m.group(1)), "unit": "months" if "月" in age else "years"}
    a = age.lower()
    if any(w in a for w in ("幼", "baby", "puppy", "kitten", "child")):
        return {"value": 6, "unit": "months"}
    if "老" in a or "senior" in a or "old" in a:
        return {"value": 8, "unit": "years"}
    return {"value": 2, "unit": "years"}
