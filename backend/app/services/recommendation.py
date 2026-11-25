"""熱門／偏好推薦，對應舊版 services/recommendationService.js。"""
import math
from datetime import datetime, timezone

from app.core.populate import populate
from app.db import get_db
from app.models.pet import pet_json


def _list(v) -> list:
    return v if isinstance(v, list) else []


def preference_score(pet: dict, profile: dict) -> float:
    if not profile:
        return 0
    score, max_score = 0.0, 0.0
    max_score += 25
    if pet.get("species") in _list(profile.get("species")):
        score += 25
    max_score += 15
    if pet.get("size") in _list(profile.get("sizes")):
        score += 15
    max_score += 10
    if pet.get("ageCategory") in _list(profile.get("ageCategories")):
        score += 10
    max_score += 30
    wanted = _list(profile.get("personality"))
    traits = (pet.get("personality") or {}).get("traits")
    if wanted and pet.get("personality") and traits is not None:
        score += len([t for t in wanted if t in _list(traits)]) / len(wanted) * 30
    max_score += 10
    health_pref = profile.get("healthPreferences")
    if health_pref:
        status = pet.get("healthStatus") or {}
        wanted_h = [k for k in ("vaccinated", "spayed", "microchipped") if health_pref.get(k)]
        if wanted_h:
            score += len([k for k in wanted_h if status.get(k)]) / len(wanted_h) * 10
    max_score += 10
    needs = profile.get("specialNeeds")
    if needs:
        good = (pet.get("personality") or {}).get("goodWith") or {}
        wanted_n = [(flag, key) for flag, key in (("goodWithChildren", "children"), ("goodWithOtherPets", "otherPets"))
                    if needs.get(flag)]
        if wanted_n:
            score += len([1 for _, key in wanted_n if good.get(key)]) / len(wanted_n) * 10
    return (score / max_score) * 100 if max_score > 0 else 0


def popularity_score(pet: dict) -> float:
    likes = len(_list(pet.get("likes")))
    views = pet.get("views") or 0
    return min(math.log(likes + 1) * 15, 50) + min(math.log(views + 1) * 10, 50)


def freshness_score(pet: dict, now: datetime | None = None) -> float:
    intake = (pet.get("shelterInfo") or {}).get("intakeDate")
    if not intake:
        return 50
    if isinstance(intake, str):
        intake = datetime.fromisoformat(intake.replace("Z", "+00:00"))
    if intake.tzinfo is None:
        intake = intake.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    days = math.floor((now - intake).total_seconds() / 86400)
    if days <= 30:
        return 100 - days
    if days <= 90:
        return 70 - (days - 30) * 0.5
    if days <= 180:
        return 40 - (days - 90) * 0.22
    return max(0, 20 - (days - 180) * 0.1)


def calculate_scores(pet: dict, user: dict, now: datetime | None = None) -> dict:
    return {"preferenceScore": preference_score(pet, user.get("recommendationProfile") or {}),
            "popularityScore": popularity_score(pet), "freshnessScore": freshness_score(pet, now)}


def total_score(scores: dict) -> float:
    return scores["preferenceScore"] * 0.5 + scores["popularityScore"] * 0.3 + scores["freshnessScore"] * 0.2


def generate_reasons(scores: dict, user: dict) -> list[str]:
    reasons = []
    profile = user.get("recommendationProfile") or {}
    if scores["preferenceScore"] >= 60:
        matched = [label for key, label in (("species", "物種"), ("sizes", "體型"), ("personality", "性格"))
                   if _list(profile.get(key))]
        if matched:
            reasons.append(f"符合你的偏好: {'、'.join(matched)}")
    if scores["popularityScore"] >= 60:
        reasons.append("社群熱門推薦")
    if scores["freshnessScore"] >= 80:
        reasons.append("剛進入收容所")
    return reasons or ["推薦給你"]


QUERY = {"adoptionStatus": "available", "isActive": True}


async def generate_recommendations(user: dict, limit: int = 8, exclude_ids: list | None = None) -> list[dict]:
    pets = await get_db().pets.find({**QUERY, "_id": {"$nin": exclude_ids or []}}).to_list(None)
    if not pets:
        return []
    await populate(pets, "createdBy", "users", "username")
    scored = []
    for pet in pets:
        scores = calculate_scores(pet, user)
        scored.append({**pet_json(pet), "recommendationScore": total_score(scores), "scoreBreakdown": scores,
                       "recommendationReasons": generate_reasons(scores, user)})
    return sorted(scored, key=lambda p: p["recommendationScore"], reverse=True)[:limit]


async def get_popular_pets(limit: int = 8, exclude_ids: list | None = None) -> list[dict]:
    pets = await get_db().pets.find({**QUERY, "_id": {"$nin": exclude_ids or []}}).sort("views", -1) \
        .limit(limit).to_list(None)
    await populate(pets, "createdBy", "users", "username")
    return [{**pet_json(p), "recommendationReasons": ["熱門寵物"]} for p in pets]
