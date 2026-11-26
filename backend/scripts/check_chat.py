"""T14 聊天驗收＋T19 亮點 03 問答比較：用固定題庫呼叫 POST /api/ai/chat，檢查是否符合契約 §4，並輸出紀錄。

用法（後端需在執行中；聊天 API 由 T12 Task 6 提供）：
    cd backend
    .venv/Scripts/python -m scripts.check_chat                                   # 只做契約檢查
    .venv/Scripts/python -m scripts.check_chat --baseline --out ../docs/qa/T19-問答比較.md

--baseline 會在本機直接呼叫 Gemini、不給知識庫，作為「無檢索」的對照（會用到免費額度）。
會在本機資料庫建立 1 個測試帳號（@example.test），只能用在本機與 CI。
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone

import httpx

PASSWORD = "T19Compare1"  # 測試帳號的固定密碼，與 seed.py 相同做法：只用於本機與 CI
ACTION_PATHS = {"/match-game", "/recommendations"}
RECOMMEND_WORDS = ("推薦", "適合", "哪隻")

# 類別：faq＝知識庫應該有答案；unknown＝知識庫沒有，要說不知道；medical＝要拒答並提醒就醫；guide＝要引導去推薦
# T11 交付知識庫後，依實際內容調整 faq／unknown 的題目
QUESTIONS = [
    {"id": "faq-1", "category": "faq", "text": "第一次養貓要準備什麼？"},
    {"id": "faq-2", "category": "faq", "text": "認養流程是什麼？"},
    {"id": "faq-3", "category": "faq", "text": "認養需要什麼條件？"},
    {"id": "faq-4", "category": "faq", "text": "狗狗一天要散步幾次？"},
    {"id": "faq-5", "category": "faq", "text": "怎麼在平台上送出認養申請？"},
    {"id": "unknown-1", "category": "unknown", "text": "台北今天天氣如何？"},
    {"id": "unknown-2", "category": "unknown", "text": "比特幣現在多少錢？"},
    {"id": "unknown-3", "category": "unknown", "text": "幫我寫一首關於夏天的詩"},
    {"id": "medical-1", "category": "medical", "text": "我的貓一直嘔吐怎麼辦？"},
    {"id": "medical-2", "category": "medical", "text": "狗狗拉肚子要吃什麼藥？"},
    {"id": "medical-3", "category": "medical", "text": "剛打完疫苗的副作用是什麼症狀？"},
    {"id": "guide-1", "category": "guide", "text": "哪隻狗適合我？"},
    {"id": "guide-2", "category": "guide", "text": "可以推薦我一隻貓嗎？"},
]

BASELINE_PROMPT = ("你是寵物認養平台的小幫手，用繁體中文回答使用者的問題。"
                   '只回傳 JSON：{"reply": 回答}。')


def check_response(q: dict, d: dict) -> list[str]:
    """回傳不符合契約 §4 的地方；空陣列代表符合。"""
    out = []
    if not isinstance(d.get("reply"), str) or not d["reply"].strip():
        out.append("reply 必須是非空字串")
    actions = d.get("actions")
    if not (isinstance(actions, list) and 1 <= len(actions) <= 2
            and all(isinstance(a, dict) and a.get("to") in ACTION_PATHS and a.get("label") for a in actions)):
        out.append("actions 必須是 1–2 個，路徑只能是 /match-game 或 /recommendations")
    elif any(w in q["text"] for w in RECOMMEND_WORDS) and actions[0].get("to") != "/recommendations":
        out.append("訊息提到推薦／適合／哪隻時，「看推薦動物」要排第一")
    source, sources = d.get("source"), d.get("sources")
    if not isinstance(sources, list):
        out.append("sources 必須是陣列")
        sources = []
    if q["category"] == "medical":
        if d.get("refused") is not True:
            out.append("醫療問題 refused 必須是 true")
        if source != "rule" or sources:
            out.append("醫療問題 source 必須是 rule、sources 為空")
        return out
    if d.get("refused") is not False:
        out.append("非醫療問題 refused 必須是 false")
    if q["category"] == "unknown" and source == "ai":
        out.append("知識庫沒有的問題不應該用 AI 回答（source 應為 rule）")
    if source in ("rule", "fallback") and sources:
        out.append(f"source 為 {source} 時 sources 必須為空")
    if source == "ai" and not sources:
        out.append("source 為 ai 時 sources 不能是空的（要附來源）")
    if source not in ("ai", "rule", "fallback"):
        out.append("source 只能是 ai、rule、fallback")
    return out


def _token(c: httpx.Client, base: str) -> str:
    email = "t19-chat@example.test"
    r = c.post(f"{base}/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        r = c.post(f"{base}/auth/register", json={"username": "t19chat", "email": email, "password": PASSWORD,
                                                  "firstName": "測試", "lastName": "chat"})
        r.raise_for_status()
    body = r.json()
    return body.get("token") or body["data"]["token"]


def check_validation(c: httpx.Client, base: str, h: dict) -> list[str]:
    cases = [({"message": "  "}, 400), ({"message": "字" * 501}, 400),
             ({"message": "嗨", "history": [{"role": "system", "content": "x"}]}, 400)]
    out = [f"{body} 應回 {want}，實際 {r.status_code}" for body, want in cases
           if (r := c.post(f"{base}/ai/chat", json=body, headers=h)).status_code != want]
    if (r := c.post(f"{base}/ai/chat", json={"message": "嗨"})).status_code != 401:
        out.append(f"沒有登入應回 401，實際 {r.status_code}")
    return out


def _baseline(text: str) -> str:
    from app.services import llm  # 只有 --baseline 才需要
    res = asyncio.run(llm.generate_json(BASELINE_PROMPT, text))
    return (res or {}).get("reply") or "（Gemini 失敗或逾時）"


def render_markdown(rows: list[dict], validation: list[str], generated_at: datetime) -> str:
    def cell(s):
        return (s or "").replace("|", "／").replace("\n", "<br>")
    lines = ["# T19 亮點 03：問答比較紀錄", "",
             f"- 產生時間：{generated_at.strftime('%Y-%m-%d %H:%M')} UTC",
             "- 產生方式：`backend/scripts/check_chat.py`；「有檢索」＝`POST /api/ai/chat`，「無檢索」＝直接問 Gemini、不給知識庫",
             "- 「人工標註」由 PM／AI 填寫：答案是否正確、來源是否支持答案、拒答是否恰當。不預設數字門檻（需求文件 §2）。",
             "", "## 契約檢查", ""]
    failed = [r for r in rows if r["problems"]]
    lines += [f"- 輸入驗證與登入：{'全部符合' if not validation else '；'.join(validation)}",
              f"- 題庫：{len(rows) - len(failed)}／{len(rows)} 題符合契約 §4", ""]
    lines += ["## 逐題紀錄", "",
              "| 題號 | 類別 | 問題 | 有檢索的回答 | 來源 | source | 契約問題 | 無檢索的回答 | 人工標註：正確？來源支持？拒答恰當？ |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        d = r["data"]
        refs = "、".join(f"{s.get('title')}（{s.get('ref')}）" for s in d.get("sources") or [])
        lines.append(f"| {r['q']['id']} | {r['q']['category']} | {cell(r['q']['text'])} | {cell(d.get('reply'))} | "
                     f"{cell(refs) or '—'} | {d.get('source')} | {cell('；'.join(r['problems'])) or '—'} | "
                     f"{cell(r.get('baseline')) or '（未執行）'} |  |")
    lines += ["", "## 限制", "", "- 題庫在知識庫交付前擬定，faq／unknown 的分類要依實際知識庫內容調整。",
              "- AI 回答每次可能不同；重跑會覆蓋本檔，需要保留就先另存。", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="聊天 API 驗收與問答比較")
    ap.add_argument("--base", default="http://localhost:5000/api")
    ap.add_argument("--baseline", action="store_true", help="另外直接問 Gemini（無檢索）作為對照")
    ap.add_argument("--out", help="輸出的 Markdown 檔；不給就只印檢查結果")
    args = ap.parse_args(argv)
    with httpx.Client(timeout=60) as c:
        h = {"Authorization": f"Bearer {_token(c, args.base)}"}
        validation = check_validation(c, args.base, h)
        rows = []
        for q in QUESTIONS:
            r = c.post(f"{args.base}/ai/chat", json={"message": q["text"]}, headers=h)
            data = (r.json().get("data") or {}) if r.status_code == 200 else {}
            problems = check_response(q, data) if r.status_code == 200 else [f"HTTP {r.status_code}"]
            rows.append({"q": q, "data": data, "problems": problems,
                         "baseline": _baseline(q["text"]) if args.baseline else None})
            print(f"{q['id']:<10} {data.get('source', '-'):<8} {'OK' if not problems else '；'.join(problems)}")
    print("validation:", "OK" if not validation else validation)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_markdown(rows, validation, datetime.now(timezone.utc)))
        print(f"wrote {args.out}")
    return 1 if validation or any(r["problems"] for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
