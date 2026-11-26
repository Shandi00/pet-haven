"""T19 亮點 02：用同一批測資比較三種推薦，輸出 Markdown 紀錄（人工標註欄留空）。

三種推薦：
1. 熱門推薦（既有）：GET /api/recommendations
2. 規則排序：GET /api/matching/top3 的排序，理由用 rule_reason()（不呼叫 LLM）
3. 規則＋AI 理由：GET /api/matching/top3 回傳的理由（Gemini 失敗時會標示 source=rule）

用法（後端需在執行中，並已執行 npm run seed）：
    cd backend
    .venv/Scripts/python -m scripts.compare_recommendations --out ../docs/qa/T19-推薦比較.md

會在本機資料庫建立 3 個測試帳號（@example.test），只能用在本機與 CI，不可用在任何對外環境。
"""
import argparse
import sys
from datetime import datetime, timezone

import httpx

from app.services.ai_explain import rule_reason

# 測試帳號的固定密碼，與 seed.py 相同做法：只用於本機與 CI
PASSWORD = "T19Compare1"

PERSONAS = [
    {
        "key": "apartment_cat", "label": "A：住公寓、第一次養、想養貓",
        "recommendationProfile": {"species": ["cat"], "sizes": ["small", "medium"], "personality": ["calm", "friendly"]},
        "lifestyle": {"activityLevel": "low", "availableTime": "moderate", "housingType": "apartment"},
        "experience": {"petOwnershipExperience": "none", "trainingExperience": False},
        "environment": {"hasChildren": False, "hasOtherPets": False, "noiseSensitive": True, "hasAllergies": False},
    },
    {
        "key": "family_dog", "label": "B：有小孩的家庭、有經驗、想養狗",
        "recommendationProfile": {"species": ["dog"], "sizes": ["medium", "large"],
                                  "personality": ["friendly", "playful"]},
        "lifestyle": {"activityLevel": "high", "availableTime": "extensive", "housingType": "house-with-yard"},
        "experience": {"petOwnershipExperience": "intermediate", "trainingExperience": True},
        "environment": {"hasChildren": True, "childrenAges": ["4-6"], "hasOtherPets": False,
                        "noiseSensitive": False, "hasAllergies": False},
    },
    {"key": "empty", "label": "C：剛註冊、檔案都沒填（資料欄位缺漏）"},
]


def _token(c: httpx.Client, base: str, p: dict) -> str:
    email = f"t19-{p['key'].replace('_', '-')}@example.test"
    r = c.post(f"{base}/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        r = c.post(f"{base}/auth/register", json={
            "username": f"t19{p['key'].replace('_', '')}", "email": email, "password": PASSWORD,
            "firstName": "測試", "lastName": p["key"]})
        r.raise_for_status()
    body = r.json()
    return body.get("token") or body["data"]["token"]


def _setup(c: httpx.Client, base: str, h: dict, p: dict) -> None:
    if "recommendationProfile" in p:
        c.put(f"{base}/users/profile", json={"recommendationProfile": p["recommendationProfile"]},
              headers=h).raise_for_status()
    for part in ("lifestyle", "experience", "environment"):
        if part in p:
            c.put(f"{base}/matching/profile/{part}", json=p[part], headers=h).raise_for_status()
    c.delete(f"{base}/matching/feedback", headers=h).raise_for_status()


def collect(base: str) -> list[dict]:
    results = []
    with httpx.Client(timeout=60) as c:
        for p in PERSONAS:
            h = {"Authorization": f"Bearer {_token(c, base, p)}"}
            _setup(c, base, h, p)
            popular = c.get(f"{base}/recommendations", params={"limit": 3, "refresh": "true"},
                            headers=h).json()["recommendations"]
            profile = c.get(f"{base}/matching/profile", headers=h).json()["data"]
            items = c.get(f"{base}/matching/top3", headers=h).json()["data"]["items"]
            top3 = []
            for it in items:
                raw = c.get(f"{base}/pets/{it['pet']['_id']}").json()
                pet = (raw.get("data", raw) if isinstance(raw, dict) else raw)
                pet = pet.get("pet", pet)
                top3.append({**it, "ruleReason": rule_reason(pet, profile)})
            results.append({"persona": p, "popular": popular, "top3": top3})
    return results


def _reason_text(r: dict) -> str:
    parts = [r.get("summary") or ""]
    if r.get("highlights"):
        parts.append("優點：" + "、".join(r["highlights"]))
    if r.get("cautions"):
        parts.append("注意：" + "、".join(r["cautions"]))
    return "<br>".join(p.replace("|", "／") for p in parts if p)


def _conditions(p: dict) -> str:
    if "lifestyle" not in p:
        return "沒有填寫任何配對檔案"
    rp, life, exp, env = p["recommendationProfile"], p["lifestyle"], p["experience"], p["environment"]
    flags = [k for k in ("hasChildren", "hasOtherPets", "noiseSensitive", "hasAllergies") if env.get(k)]
    return (f"偏好物種 {'、'.join(rp['species'])}，體型 {'、'.join(rp['sizes'])}，個性 {'、'.join(rp['personality'])}；"
            f"活動量 {life['activityLevel']}，時間 {life['availableTime']}，住所 {life['housingType']}；"
            f"經驗 {exp['petOwnershipExperience']}；環境 {'、'.join(flags) or '無特殊'}")


def render_markdown(results: list[dict], generated_at: datetime) -> str:
    lines = [
        "# T19 亮點 02：推薦比較紀錄",
        "",
        f"- 產生時間：{generated_at.strftime('%Y-%m-%d %H:%M')} UTC",
        "- 產生方式：`backend/scripts/compare_recommendations.py`（seed 測資＋3 個測試帳號）",
        "- 「人工標註」由 PM／AI 填寫：理由是否只引用真實欄位、排序是否合理、注意事項是否有用。"
        "不預設數字門檻，只記錄結果與限制（需求文件 §2）。",
        "",
    ]
    for res in results:
        p = res["persona"]
        lines += [f"## 使用者 {p['label']}", "", f"條件：{_conditions(p)}", "",
                  "### 排序比較", "",
                  "| 名次 | 熱門推薦（既有） | 規則排序／規則＋AI（同一個排序） | 人工標註：排序合理嗎？ |",
                  "|---|---|---|---|"]
        for i in range(3):
            pop = res["popular"][i] if i < len(res["popular"]) else None
            top = res["top3"][i] if i < len(res["top3"]) else None
            pop_txt = f"{pop['name']}（{'、'.join(pop.get('recommendationReasons') or [])}）" if pop else "—"
            top_txt = f"{top['pet']['name']}（{top['score']} 分，{top['matchLevel']}）" if top else "—"
            lines.append(f"| {i + 1} | {pop_txt} | {top_txt} |  |")
        lines += ["", "### 理由比較", "",
                  "| 動物 | 規則理由 | 規則＋AI 理由 | AI 來源 | 人工標註：有沒有引用不存在的資料？哪個比較有用？ |",
                  "|---|---|---|---|---|"]
        for top in res["top3"]:
            lines.append(f"| {top['pet']['name']} | {_reason_text(top['ruleReason'])} | "
                         f"{_reason_text(top['reason'])} | {top['reason'].get('source')} |  |")
        lines.append("")
    lines += ["## 限制", "",
              "- 只有 seed 的動物與 3 個測試帳號，樣本很小。",
              "- 「規則＋AI」那欄的 AI 來源為 `rule` 時，代表當次 Gemini 失敗或逾時，改用規則理由。",
              "- AI 回答每次可能不同；重跑會覆蓋本檔，需要保留就先另存。", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost:5000/api")
    ap.add_argument("--out", help="輸出的 Markdown 檔；不給就印到畫面")
    args = ap.parse_args()
    md = render_markdown(collect(args.base), datetime.now(timezone.utc))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
