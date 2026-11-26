"""推薦理由：Top 3（T13）與 POST /api/ai/explain（T12）共用。

目前只有規則理由；T12 加入 Gemini 時在 explain() 補上 LLM 路徑，失敗時仍回傳 rule_reason()。
"""
from app.services.advanced_matching import calculate_match

SUMMARY_MAX = 80
LIST_MAX = 3
_UNKNOWN_GOOD_WITH = (("hasChildren", "children", "小孩"), ("hasOtherPets", "otherPets", "其他寵物"))


def rule_reason(pet: dict, user: dict) -> dict:
    analysis = calculate_match(pet, user)["analysis"]
    name = pet.get("name") or "這隻毛孩"
    env = user.get("environmentProfile") or {}
    good_with = (pet.get("personality") or {}).get("goodWith") or {}
    unknown = [f"還不確定{name}能否和{label}相處，建議先向送養人確認"
               for flag, key, label in _UNKNOWN_GOOD_WITH if env.get(flag) and good_with.get(key) is None]
    strengths = analysis["strengths"]
    summary = f"{name}：{'、'.join(strengths[:2])}。" if strengths else f"{name}符合你的基本條件，可以進一步了解。"
    return {
        "summary": summary[:SUMMARY_MAX],
        "highlights": (strengths + analysis["highlights"])[:LIST_MAX],
        "cautions": (unknown + analysis["concerns"])[:LIST_MAX],
        "source": "rule",
    }


async def explain(pet: dict, user: dict) -> dict:
    return rule_reason(pet, user)
