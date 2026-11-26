"""Top 3 推薦（T13）：契約 §0 的硬條件、既有規則計分、「不適合」回饋重排，以及 §2 的回應組裝。"""
import asyncio
import math
from datetime import datetime, timezone

from app.core.serialize import to_json
from app.db import get_db
from app.services.advanced_matching import calculate_match, match_level
from app.config import get_settings
from app.services.ai_explain import explain, rule_reason

TOP_N = 3
PENALTY_STEP = 5
PENALTY_MAX = 15
SPECIES_ZH = {"dog": "狗", "cat": "貓", "rabbit": "兔", "bird": "鳥", "hamster": "倉鼠", "guinea-pig": "天竺鼠",
              "other": "其他"}
ACTIVITY_ZH = {"low": "低", "moderate": "中等", "high": "高"}
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def _personality(pet: dict) -> dict:
    return pet.get("personality") or {}


def _activity(pet: dict):
    return _personality(pet).get("activityLevel")


def passes_hard_rules(pet: dict, user: dict, disliked_ids: set) -> bool:
    if pet.get("_id") in disliked_ids:
        return False
    env = user.get("environmentProfile") or {}
    good_with = _personality(pet).get("goodWith") or {}
    if env.get("hasChildren") and good_with.get("children") is False:
        return False
    if env.get("hasOtherPets") and good_with.get("otherPets") is False:
        return False
    if env.get("hasAllergies") and pet.get("species") == "cat":
        return False
    species = (user.get("recommendationProfile") or {}).get("species") or []
    return not species or pet.get("species") in species


def penalty(pet: dict, disliked_pets: list[dict]) -> int:
    activity = _activity(pet)
    if not activity:
        return 0
    hits = sum(1 for d in disliked_pets if d.get("_id") != pet.get("_id")
               and d.get("species") == pet.get("species") and _activity(d) == activity)
    return min(PENALTY_MAX, hits * PENALTY_STEP)


def _created_at(pet: dict) -> datetime:
    dt = pet.get("createdAt")
    if not isinstance(dt, datetime):
        return _OLDEST
    # pymongo 預設讀出不帶時區的 UTC 時間，與帶時區的比較會丟 TypeError
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def rank(pets: list[dict], user: dict, disliked_pets: list[dict]) -> list[dict]:
    scored = []
    for p in pets:
        # 四捨五入用 floor(x + 0.5)；round() 是銀行家捨入，扣 5 分後可能差 1
        rounded = math.floor(calculate_match(p, user, normalized=True)["matchScore"] - penalty(p, disliked_pets) + 0.5)
        # environment 最高 110，加權後仍可能略超過 100；顯示夾在 0–100，排序用未夾的整數
        score = min(100, max(0, rounded))
        scored.append({"pet": p, "rounded": rounded, "score": score, "matchLevel": match_level(score)["level"]})
    scored.sort(key=lambda r: (r["rounded"], _created_at(r["pet"])), reverse=True)
    return [{k: r[k] for k in ("pet", "score", "matchLevel")} for r in scored[:TOP_N]]


def pet_summary(pet: dict) -> dict:
    photos = [p for p in (pet.get("photos") or []) if p]
    primary = next((p for p in photos if p.get("isPrimary")), photos[0] if photos else None)
    return {
        "_id": str(pet["_id"]),
        "name": pet.get("name"),
        "species": pet.get("species"),
        "breed": pet.get("breed"),
        "age": pet.get("age"),
        "ageCategory": pet.get("ageCategory"),
        "size": pet.get("size"),
        "activityLevel": _activity(pet),
        "photo": (primary or {}).get("url") or "",
    }


def avoided_note(pet: dict) -> dict:
    name = pet.get("name")
    parts = [SPECIES_ZH.get(pet.get("species"), "其他")]
    if _activity(pet) in ACTIVITY_ZH:
        parts.append(f"活動量{ACTIVITY_ZH[_activity(pet)]}")
    return {"petId": str(pet["_id"]), "name": name, "note": f"已避開：{name}（{'，'.join(parts)}），並降低相似動物的排序"}


async def _explain_within(pet: dict, user: dict, timeout: float) -> dict:
    # 契約 §2：3 隻並行產生，整體不超過 LLM_TIMEOUT_SECONDS；逾時的那隻改用規則理由
    try:
        return await asyncio.wait_for(explain(pet, user), timeout)
    except asyncio.TimeoutError:
        return rule_reason(pet, user)


async def build_top3(user: dict) -> dict:
    db = get_db()
    dislikes = sorted((f for f in (user.get("matchFeedback") or []) if f.get("verdict") == "dislike"),
                      key=lambda f: _created_at({"createdAt": f.get("createdAt")}), reverse=True)
    disliked_ids = [f.get("pet") for f in dislikes]
    disliked_pets = await db.pets.find({"_id": {"$in": disliked_ids}}).to_list(None) if disliked_ids else []
    candidates = await db.pets.find({"adoptionStatus": "available", "isActive": True}).to_list(None)
    candidates = [p for p in candidates if passes_hard_rules(p, user, set(disliked_ids))]
    top = rank(candidates, user, disliked_pets)
    timeout = get_settings().llm_timeout_seconds
    reasons = await asyncio.gather(*(_explain_within(r["pet"], user, timeout) for r in top))
    by_id = {p["_id"]: p for p in disliked_pets}
    return to_json({
        "items": [{"pet": pet_summary(r["pet"]), "score": r["score"], "matchLevel": r["matchLevel"], "reason": reason}
                  for r, reason in zip(top, reasons)],
        "avoided": [avoided_note(by_id[i]) for i in disliked_ids if i in by_id],
        "generatedAt": datetime.now(timezone.utc),
    })
