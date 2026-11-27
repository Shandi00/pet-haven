"""審核輔助（T13 延伸，選做，2026-11-27 加入）：給送養者審核申請時參考。

寵物目前還有幾份申請在進行、申請人在平台上的概況（只給數字），以及申請表和動物資料對不上、需要確認的事項。
全部由規則產生，不呼叫 LLM；只指出要確認的地方，不評分申請人、不建議核准或拒絕，由審核者決定。
"""
from app.db import get_db
from app.models.adoption import ACTIVE_STATUSES
from app.services.advanced_matching import calculate_match
from app.services.ai_explain import _filled

PROFILE_KEYS = ("lifestyleProfile", "experienceProfile", "environmentProfile")
SPECIES = {"dog": "狗", "cat": "貓"}
SPECIAL_NEEDS_MAX = 100


def checks(application: dict, pet: dict) -> list[dict]:
    """申請表答案對照動物資料；warning 是明確衝突，info 是需要確認。只用兩邊實際填寫的欄位。"""
    d = application.get("applicantDetails") or {}
    personality = pet.get("personality") or {}
    good_with = personality.get("goodWith") or {}
    name = pet.get("name") or "這隻動物"
    out: list[dict] = []

    children = (d.get("householdMembers") or {}).get("children") or 0
    if children and good_with.get("children") is False:
        out.append(("warning", f"申請表填有 {children} 位兒童，{name}標示不適合有小孩的家庭"))
    elif children and good_with.get("children") is None:
        out.append(("info", f"申請表填有 {children} 位兒童，{name}和小孩相處的情況未填寫，請和申請人說明並確認"))

    current = (d.get("petExperience") or {}).get("currentPets") or []
    if current and good_with.get("otherPets") is False:
        out.append(("warning", f"申請人目前養了 {len(current)} 隻寵物，{name}標示不適合與其他寵物相處"))
    elif current and good_with.get("otherPets") is None:
        out.append(("info", f"申請人目前養了 {len(current)} 隻寵物，{name}和其他寵物相處的情況未填寫，請確認"))

    if (d.get("allergies") or {}).get("hasAllergies"):
        # 與 Top 3 硬條件一致：有過敏時貓直接排除，所以貓是明確衝突
        level = "warning" if pet.get("species") == "cat" else "info"
        out.append((level, f"申請人表示家中有人過敏，請確認是否對{SPECIES.get(pet.get('species'), '這種動物')}過敏"))

    if d.get("isRented") and d.get("landlordApproval") is False:
        out.append(("warning", "申請人租屋，申請表填寫尚未取得房東同意"))

    if personality.get("activityLevel") == "high" and d.get("housingType") == "apartment" and not d.get("hasYard"):
        out.append(("info", f"{name}活動量高，申請人住公寓且沒有院子，請確認每天的運動安排"))

    needs = [n for n in personality.get("specialNeeds") or [] if isinstance(n, str) and n.strip()]
    if needs:
        # 照刊登者填的原文轉述，不做醫療判斷
        out.append(("info", f"{name}有特殊照顧需求：{'、'.join(needs)[:SPECIAL_NEEDS_MAX]}，請確認申請人了解"))

    out.sort(key=lambda c: c[0] != "warning")  # 穩定排序：明確衝突放前面
    return [{"level": level, "message": message} for level, message in out]


async def build(application: dict, pet: dict) -> dict:
    """application 要是還沒 populate 的原始文件（applicant 是 ObjectId）。"""
    db = get_db()
    applicant_id = application["applicant"]
    others = {"_id": {"$ne": application["_id"]}, "status": {"$in": list(ACTIVE_STATUSES)}}
    user = await db.users.find_one({"_id": applicant_id}, {k: 1 for k in (*PROFILE_KEYS, "recommendationProfile")})
    filled = bool(user) and any(_filled(user, k) for k in PROFILE_KEYS)
    match = None
    if filled:
        # 和 Top 3 用同一套計分；文字分析是寫給認養者的，這裡只給分數
        m = calculate_match(pet, user, normalized=True)
        match = {"score": round(m["matchScore"]), "label": m["matchLevel"]["label"],
                 "breakdown": {k: round(v) for k, v in m["breakdown"].items()}}
    return {
        "pet": {"otherActiveApplications": await db.adoptions.count_documents({"pet": pet["_id"], **others})},
        # 只給數字：申請人在其他送養者那裡的申請內容不給這位審核者看
        "applicant": {
            "otherActiveApplications": await db.adoptions.count_documents({"applicant": applicant_id, **others}),
            "completedAdoptions": await db.adoptions.count_documents({"applicant": applicant_id, "status": "completed"}),
            "matchingProfileFilled": filled,
        },
        "match": match,
        "checks": checks(application, pet),
        "source": "rule",
    }
