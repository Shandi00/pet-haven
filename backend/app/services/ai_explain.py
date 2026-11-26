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
CACHE_TTL_SECONDS = 600
CACHE_MAX = 500
_cache: dict[str, tuple[float, dict]] = {}
_UNKNOWN_GOOD_WITH = (("hasChildren", "children", "小孩"), ("hasOtherPets", "otherPets", "其他寵物"))
# 對應 advanced_matching.generate_analysis 的文字；「需要較多照顧經驗」講的是動物的 careLevel，沒填也保留
_PROFILE_CLAIMS = (
    ("lifestyleProfile", ("生活方式非常匹配", "生活方式可能需要調整以適應寵物需求")),
    ("experienceProfile", ("您的經驗適合照顧這隻寵物",)),
    ("environmentProfile", ("家庭環境理想", "家庭環境可能需要改善以適合寵物")),
)

SYSTEM_PROMPT = (
    "你是寵物認養平台的配對小幫手，用繁體中文、親切的語氣，向認養者說明這隻動物為什麼適合或需要注意什麼。"
    "只能根據使用者訊息中提供的 JSON 欄位說明；欄位沒有提供或值為 null 的資訊不能推測或編造。"
    "user 裡是空物件或沒有的欄位，代表認養者沒有填寫：不要描述或猜測認養者的生活方式、個性、喜好、時間或居住環境，"
    "只說明動物本身的特質。"
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


def _filled(user: dict, key: str) -> bool:
    return any(v is not None for k, v in (user.get(key) or {}).items() if k != "lastUpdated")


def _unfilled_claims(user: dict) -> set[str]:
    # 沒填的檔案在舊計分裡用預設分數，產生的優點／注意事項不是使用者的實際狀況
    return {claim for key, claims in _PROFILE_CLAIMS if not _filled(user, key) for claim in claims}


def rule_reason(pet: dict, user: dict) -> dict:
    analysis = calculate_match(pet, user, normalized=True)["analysis"]
    name = pet.get("name") or "這隻毛孩"
    skip = _unfilled_claims(user)
    strengths = [s for s in analysis["strengths"] if s not in skip]
    concerns = [c for c in analysis["concerns"] if c not in skip]
    summary = f"{name}：{'、'.join(strengths[:2])}。" if strengths else f"{name}符合你的基本條件，可以進一步了解。"
    return {
        "summary": summary[:SUMMARY_MAX],
        "highlights": (strengths + analysis["highlights"])[:LIST_MAX],
        "cautions": (_unknown_good_with(pet, user) + concerns)[:LIST_MAX],
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


async def _cached_generate(prompt: str) -> tuple[dict | None, bool]:
    # 免費額度每分鐘請求數有限：輸入完全相同就重用上次的 AI 輸出；失敗不快取，下次再試
    # shortcut: 存在單一程序記憶體，多個 worker 不共用、重啟就清空；要多台部署時改用 Redis
    now = time.monotonic()
    hit = _cache.get(prompt)
    if hit and now - hit[0] < CACHE_TTL_SECONDS:
        return hit[1], True
    out = await llm.generate_json(SYSTEM_PROMPT, prompt)
    if _valid(out):
        _cache.pop(prompt, None)
        while len(_cache) >= CACHE_MAX:
            _cache.pop(next(iter(_cache)))  # 移除最早放入的
        _cache[prompt] = (now, out)
    return out, False


async def explain(pet: dict, user: dict) -> dict:
    start = time.monotonic()
    out, cached = await _cached_generate(json.dumps(_llm_input(pet, user), ensure_ascii=False))
    if _valid(out):
        cautions = _unknown_good_with(pet, user)
        cautions += [c for c in out["cautions"] if c not in cautions]
        reason = {"summary": out["summary"].strip(), "highlights": out["highlights"], "cautions": cautions[:LIST_MAX],
                  "source": "ai"}
    else:
        reason = rule_reason(pet, user)
    # 契約 §0：log 只記 user id、pet id、source、耗時
    logger.info("explain user=%s pet=%s source=%s cached=%s elapsed_ms=%d", user.get("_id"), pet.get("_id"),
                reason["source"], cached, (time.monotonic() - start) * 1000)
    return reason
