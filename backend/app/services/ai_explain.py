"""推薦理由：Top 3（T13）與 POST /api/ai/explain（T12）共用。

explain() 先請 Gemini 依契約 §0 白名單欄位產生理由；失敗、逾時或格式不符時改用 rule_reason()。
"""
import json
import logging
import time

from app.services import llm
from app.services.advanced_matching import calculate_match

logger = logging.getLogger(__name__)

SUMMARY_MAX = 80
LIST_MAX = 3
_UNKNOWN_GOOD_WITH = (("hasChildren", "children", "小孩"), ("hasOtherPets", "otherPets", "其他寵物"))

SYSTEM_PROMPT = (
    "你是寵物認養平台的配對小幫手，用繁體中文、親切的語氣，向認養者說明這隻動物為什麼適合或需要注意什麼。"
    "只能根據使用者訊息中提供的 JSON 欄位說明；欄位沒有提供或值為 null 的資訊不能推測或編造。"
    "不做疾病或醫療判斷；specialNeeds 只能照原文轉述，並提醒向送養人或獸醫確認。"
    '只回傳 JSON：{"summary": 一句話，最多 80 字, "highlights": 最多 3 個優點字串, '
    '"cautions": 最多 3 個注意事項字串}。'
)


def _unknown_good_with(pet: dict, user: dict) -> list[str]:
    # 契約 §0：goodWith 沒填時不篩掉，寫進 cautions
    name = pet.get("name") or "這隻毛孩"
    env = user.get("environmentProfile") or {}
    good_with = (pet.get("personality") or {}).get("goodWith") or {}
    return [f"還不確定{name}能否和{label}相處，建議先向送養人確認"
            for flag, key, label in _UNKNOWN_GOOD_WITH if env.get(flag) and good_with.get(key) is None]


def rule_reason(pet: dict, user: dict) -> dict:
    analysis = calculate_match(pet, user, normalized=True)["analysis"]
    name = pet.get("name") or "這隻毛孩"
    strengths = analysis["strengths"]
    summary = f"{name}：{'、'.join(strengths[:2])}。" if strengths else f"{name}符合你的基本條件，可以進一步了解。"
    return {
        "summary": summary[:SUMMARY_MAX],
        "highlights": (strengths + analysis["highlights"])[:LIST_MAX],
        "cautions": (_unknown_good_with(pet, user) + analysis["concerns"])[:LIST_MAX],
        "source": "rule",
    }


def _pick(d: dict | None, keys: tuple) -> dict:
    d = d or {}
    return {k: d[k] for k in keys if k in d}


def _llm_input(pet: dict, user: dict) -> dict:
    """只放契約 §0 白名單欄位；姓名、Email、電話、地址、健康與醫療紀錄一律不送。"""
    p = pet.get("personality") or {}
    return {
        "pet": {
            **{k: pet.get(k) for k in ("name", "species", "breed", "ageCategory", "size")},
            "traits": p.get("traits") or [],
            "activityLevel": p.get("activityLevel"),
            "goodWith": _pick(p.get("goodWith"), ("children", "otherPets", "strangers")),
            "specialNeeds": p.get("specialNeeds") or [],
        },
        "user": {
            "lifestyleProfile": _pick(user.get("lifestyleProfile"), ("activityLevel", "availableTime", "housingType")),
            "experienceProfile": _pick(user.get("experienceProfile"), ("petOwnershipExperience", "trainingExperience")),
            "environmentProfile": _pick(user.get("environmentProfile"),
                                        ("hasChildren", "hasOtherPets", "noiseSensitive", "hasAllergies")),
            "petType": ((user.get("gameProfile") or {}).get("petType") or {}).get("label"),
        },
    }


def _valid_list(v) -> bool:
    return isinstance(v, list) and len(v) <= LIST_MAX and all(isinstance(s, str) and s.strip() for s in v)


def _valid(out: dict | None) -> bool:
    if not isinstance(out, dict):
        return False
    summary = out.get("summary")
    return (isinstance(summary, str) and 0 < len(summary.strip()) <= SUMMARY_MAX
            and _valid_list(out.get("highlights")) and _valid_list(out.get("cautions")))


async def explain(pet: dict, user: dict) -> dict:
    start = time.monotonic()
    out = await llm.generate_json(SYSTEM_PROMPT, json.dumps(_llm_input(pet, user), ensure_ascii=False))
    if _valid(out):
        cautions = _unknown_good_with(pet, user)
        cautions += [c for c in out["cautions"] if c not in cautions]
        reason = {"summary": out["summary"].strip(), "highlights": out["highlights"], "cautions": cautions[:LIST_MAX],
                  "source": "ai"}
    else:
        reason = rule_reason(pet, user)
    # 契約 §0：log 只記 user id、pet id、source、耗時
    logger.info("explain user=%s pet=%s source=%s elapsed_ms=%d", user.get("_id"), pet.get("_id"),
                reason["source"], (time.monotonic() - start) * 1000)
    return reason
