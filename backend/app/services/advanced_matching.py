"""規則配對，逐行對應舊版 services/advancedMatchingService.js（包含它原本的計分細節）。"""
import logging

from app.db import get_db

logger = logging.getLogger(__name__)

SIZE_ORDER = ["small", "medium", "large", "extra-large"]


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _traits(pet: dict) -> list:
    return _list((pet.get("personality") or {}).get("traits"))


def calculate_compatibility(pet: dict, user: dict) -> float:
    profile = user.get("recommendationProfile") or {}
    score = 0.0
    max_score = 0.0

    max_score += 30
    species = _list(profile.get("species"))
    if species:
        score += 30 if pet.get("species") in species else 10
    else:
        score += 15
        max_score = 15

    max_score += 20
    sizes = _list(profile.get("sizes"))
    if sizes:
        if pet.get("size") in sizes:
            score += 20
        else:
            idx = SIZE_ORDER.index(pet["size"]) if pet.get("size") in SIZE_ORDER else -1
            if any(abs((SIZE_ORDER.index(s) if s in SIZE_ORDER else -1) - idx) == 1 for s in sizes):
                score += 10
    else:
        score += 10
        max_score = 10

    max_score += 15
    ages = _list(profile.get("ageCategories"))
    if ages:
        score += 15 if pet.get("ageCategory") in ages else 5
    else:
        score += 7
        max_score = 7

    max_score += 35
    wanted = _list(profile.get("personality"))
    traits = (pet.get("personality") or {}).get("traits")
    if wanted and pet.get("personality") and traits is not None:
        matched = [t for t in wanted if t in _list(traits)]
        ratio = len(matched) / len(wanted)
        score += ratio * 35
        if ratio == 1:
            score += 5
            max_score += 5
    else:
        score += 15
        max_score = 15

    return (score / max_score) * 100 if max_score > 0 else 50


NEUTRAL_COMPATIBILITY = 75  # 介於 60 與 80：generate_analysis 不加優點也不加注意事項


def calculate_compatibility_normalized(pet: dict, user: dict) -> float:
    """與 calculate_compatibility 同樣的給分，但只用有填的偏好計算，分數維持 0–100（Top 3 用）。

    舊版在偏好沒填時把 max_score 重設，分數會超過 100；既有 API 與 golden 測試依賴舊行為，所以另寫一份。
    """
    profile = user.get("recommendationProfile") or {}
    score = max_score = 0.0
    species = _list(profile.get("species"))
    if species:
        max_score += 30
        score += 30 if pet.get("species") in species else 10
    sizes = _list(profile.get("sizes"))
    if sizes:
        max_score += 20
        if pet.get("size") in sizes:
            score += 20
        else:
            idx = SIZE_ORDER.index(pet["size"]) if pet.get("size") in SIZE_ORDER else -1
            if any(abs((SIZE_ORDER.index(s) if s in SIZE_ORDER else -1) - idx) == 1 for s in sizes):
                score += 10
    ages = _list(profile.get("ageCategories"))
    if ages:
        max_score += 15
        score += 15 if pet.get("ageCategory") in ages else 5
    wanted = _list(profile.get("personality"))
    traits = (pet.get("personality") or {}).get("traits")
    if wanted and pet.get("personality") and traits is not None:
        ratio = len([t for t in wanted if t in _list(traits)]) / len(wanted)
        max_score += 35
        score += ratio * 35
        if ratio == 1:
            score += 5
            max_score += 5
    return (score / max_score) * 100 if max_score > 0 else NEUTRAL_COMPATIBILITY


ACTIVITY_MATCH = {"low-low": 40, "low-medium": 20, "low-high": 0, "medium-low": 20, "medium-medium": 40,
                  "medium-high": 30, "high-low": 10, "high-medium": 30, "high-high": 40}
TIME_MATCH = {"minimal-low": 30, "minimal-medium": 15, "minimal-high": 5, "moderate-low": 25, "moderate-medium": 30,
              "moderate-high": 20, "extensive-low": 20, "extensive-medium": 25, "extensive-high": 30}
HOUSING_SCORE = {"apartment": 10, "condo": 15, "townhouse": 20, "house-no-yard": 20, "house-with-yard": 30}


def calculate_lifestyle_match(pet: dict, user: dict) -> float:
    profile = user.get("lifestyleProfile") or {}
    care = pet.get("careRequirements") or {}
    score = 0.0
    max_score = 0.0

    max_score += 40
    if profile.get("activityLevel") and care.get("exerciseNeeds"):
        # JS 的 `|| 20`：0 分也會變成 20
        score += ACTIVITY_MATCH.get(f"{profile['activityLevel']}-{care['exerciseNeeds']}") or 20
    else:
        score += 20

    max_score += 30
    if profile.get("availableTime") and care.get("timeCommitment"):
        score += TIME_MATCH.get(f"{profile['availableTime']}-{care['timeCommitment']}") or 15
    else:
        score += 15

    max_score += 30
    if profile.get("housingType"):
        if pet.get("size") in ("large", "extra-large"):
            score += HOUSING_SCORE.get(profile["housingType"]) or 15
        else:
            score += 25
    else:
        score += 15

    return (score / max_score) * 100 if max_score > 0 else 50


EXPERIENCE_MATRIX = {"none-easy": 100, "none-medium": 60, "none-high": 30, "beginner-easy": 90,
                     "beginner-medium": 80, "beginner-high": 50, "intermediate-easy": 85, "intermediate-medium": 95,
                     "intermediate-high": 75, "experienced-easy": 80, "experienced-medium": 90,
                     "experienced-high": 100}


def calculate_experience_match(pet: dict, user: dict) -> float:
    profile = user.get("experienceProfile") or {}
    level = profile.get("petOwnershipExperience") or "none"
    care_level = (pet.get("careRequirements") or {}).get("careLevel") or "medium"
    score = EXPERIENCE_MATRIX.get(f"{level}-{care_level}") or 50
    if _list(pet.get("specialNeeds")):
        if level == "experienced":
            score = min(100, score + 10)
        elif level in ("none", "beginner"):
            score = max(0, score - 20)
    return score


def calculate_environment_match(pet: dict, user: dict) -> float:
    profile = user.get("environmentProfile") or {}
    good_with = (pet.get("personality") or {}).get("goodWith") or {}
    score, deductions = 100, 0
    for flag, key in (("hasChildren", "children"), ("hasOtherPets", "otherPets")):
        if profile.get(flag):
            if good_with.get(key) is False:
                deductions += 40
            elif good_with.get(key) is True:
                score += 10
            else:
                deductions += 10
    traits = _traits(pet)
    if profile.get("noiseSensitive") and (pet.get("personality") or {}).get("traits") is not None:
        if "vocal" in traits or "energetic" in traits:
            deductions += 15
    if profile.get("hasAllergies"):
        if pet.get("species") == "cat" or "long-hair" in (pet.get("breed") or ""):
            deductions += 25
    return max(0, min(110, score - deductions))


WEIGHTS = {"compatibility": 0.35, "lifestyle": 0.30, "experience": 0.20, "environment": 0.15}


def calculate_weighted_score(scores: dict) -> float:
    return sum(scores[k] * w for k, w in WEIGHTS.items())


def calculate_confidence(user: dict, scores: dict) -> float:
    profile = user.get("recommendationProfile") or {}
    lifestyle = user.get("lifestyleProfile") or {}
    experience = user.get("experienceProfile") or {}
    environment = user.get("environmentProfile") or {}
    confidence = 0.0
    if _list(profile.get("species")):
        confidence += 15
    if _list(profile.get("personality")):
        confidence += 15
    if lifestyle.get("activityLevel"):
        confidence += 15
    if experience.get("petOwnershipExperience"):
        confidence += 15
    if "hasChildren" in environment or "hasOtherPets" in environment:
        confidence += 10
    values = list(scores.values())
    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    confidence += max(0, 100 - variance / 10) * 0.3
    return min(100, confidence)


def generate_analysis(scores: dict, pet: dict, user: dict) -> dict:
    analysis = {"strengths": [], "concerns": [], "highlights": []}
    if scores["compatibility"] >= 80:
        analysis["strengths"].append("基本屬性高度相容")
    if scores["lifestyle"] >= 80:
        analysis["strengths"].append("生活方式非常匹配")
    if scores["experience"] >= 80:
        analysis["strengths"].append("您的經驗適合照顧這隻寵物")
    if scores["environment"] >= 80:
        analysis["strengths"].append("家庭環境理想")
    if scores["compatibility"] < 60:
        analysis["concerns"].append("基本偏好匹配度較低，建議考慮其他選項")
    if scores["lifestyle"] < 60:
        analysis["concerns"].append("生活方式可能需要調整以適應寵物需求")
    if scores["experience"] < 50:
        analysis["concerns"].append("這隻寵物可能需要較多照顧經驗")
    if scores["environment"] < 60:
        analysis["concerns"].append("家庭環境可能需要改善以適合寵物")
    profile = user.get("recommendationProfile") or {}
    if pet.get("species") in _list(profile.get("species")):
        analysis["highlights"].append(f"符合您偏好的 {pet.get('species')} 品種")
    if (pet.get("personality") or {}).get("traits") is not None:
        matched = [t for t in _list(profile.get("personality")) if t in _traits(pet)]
        if matched:
            analysis["highlights"].append(f"性格特質匹配: {'、'.join(matched)}")
    return analysis


def generate_recommendations(total: float, analysis: dict, pet: dict) -> list:
    name = pet.get("name")
    if total >= 80:
        recs = [{"type": "positive", "title": "極佳配對", "message": f"{name} 非常適合您！建議盡快提交認養申請。",
                 "action": "apply", "priority": "high"}]
    elif total >= 60:
        recs = [{"type": "neutral", "title": "良好配對", "message": f"{name} 適合您，建議先了解更多照顧細節。",
                 "action": "learn_more", "priority": "medium"}]
    else:
        recs = [{"type": "caution", "title": "需要考慮", "message": f"{name} 可能需要特別的照顧，建議諮詢專業意見。",
                 "action": "consult", "priority": "low"}]
    for concern in analysis["concerns"]:
        if "經驗" in concern:
            recs.append({"type": "tip", "title": "建議參加培訓", "message": "考慮參加寵物照顧培訓課程以提升經驗",
                         "action": "training", "priority": "medium"})
        if "環境" in concern:
            recs.append({"type": "tip", "title": "環境準備", "message": "建議在認養前改善家庭環境設施",
                         "action": "prepare", "priority": "high"})
    return recs


def match_level(score: float) -> dict:
    if score >= 85:
        return {"level": "perfect", "label": "完美配對", "color": "green"}
    if score >= 70:
        return {"level": "excellent", "label": "絕佳配對", "color": "blue"}
    if score >= 55:
        return {"level": "good", "label": "良好配對", "color": "teal"}
    if score >= 40:
        return {"level": "fair", "label": "尚可配對", "color": "yellow"}
    return {"level": "poor", "label": "配對度低", "color": "red"}


def calculate_match(pet: dict, user: dict, normalized: bool = False) -> dict:
    """normalized=True 用 calculate_compatibility_normalized（Top 3 用）；預設維持舊版行為。"""
    breakdown = {
        "compatibility": (calculate_compatibility_normalized if normalized else calculate_compatibility)(pet, user),
        "lifestyle": calculate_lifestyle_match(pet, user),
        "experience": calculate_experience_match(pet, user),
        "environment": calculate_environment_match(pet, user),
    }
    total = calculate_weighted_score(breakdown)
    analysis = generate_analysis(breakdown, pet, user)
    return {
        "matchScore": total,
        "confidence": calculate_confidence(user, breakdown),
        "breakdown": breakdown,
        "analysis": analysis,
        "recommendations": generate_recommendations(total, analysis, pet),
        "matchLevel": match_level(total),
    }


def batch_calculate_matches(pets: list[dict], user: dict) -> list[dict]:
    results = [{"pet": pet, **calculate_match(pet, user)} for pet in pets]
    return sorted(results, key=lambda r: r["matchScore"], reverse=True)


async def find_best_matches(user: dict, limit: int = 10, min_score: float = 40) -> list[dict]:
    pets = await get_db().pets.find({"adoptionStatus": "available", "isActive": True}).to_list(None)
    if not pets:
        return []
    return [m for m in batch_calculate_matches(pets, user) if m["matchScore"] >= min_score][:limit]
