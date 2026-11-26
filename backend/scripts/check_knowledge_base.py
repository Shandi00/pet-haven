"""檢查 FAQ 知識庫（T11 交付、T14 使用）：格式是否符合契約附錄，並試幾個問題看會檢索到哪幾筆。

用法：
    cd backend
    .venv/Scripts/python -m scripts.check_knowledge_base
    .venv/Scripts/python -m scripts.check_knowledge_base app/data/knowledge_base.json --ask "第一次養貓要準備什麼"

格式正確回傳 0，有問題回傳 1（可以放進 CI）。
"""
import argparse
import json
import sys

from app.services import knowledge_base as kb

SAMPLE_QUESTIONS = ["第一次養貓要準備什麼？", "認養流程是什麼？", "狗狗一天要散步幾次？", "兔子可以吃巧克力嗎？"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="檢查 FAQ 知識庫格式與檢索結果")
    ap.add_argument("path", nargs="?", default=str(kb.KB_PATH))
    ap.add_argument("--ask", action="append", help="要試的問題，可給多次；不給就用內建範例問題")
    args = ap.parse_args(argv)

    try:
        with open(args.path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"無法讀取 {args.path}：{type(exc).__name__}")
        return 1

    problems = kb.validate(data)
    if problems:
        print(f"發現 {len(problems)} 個問題（不合格的條目不會被檢索到）：")
        for p in problems:
            print(f"  - {p}")
    else:
        print(f"{len(data)} 筆條目，格式正確")

    entries = [e for e in data if isinstance(e, dict) and not kb.validate([e])] if isinstance(data, list) else []
    print(f"\n檢索試跑（門檻 {kb.MIN_SCORE}，每題最多 {kb.TOP_K} 筆）：")
    for q in args.ask or SAMPLE_QUESTIONS:
        hits = kb.ranked(q, entries)[:kb.TOP_K]
        print(f"\n問：{q}")
        if not hits:
            print("  查無資料（聊天會回答不知道）")
        for s, e in hits:
            print(f"  {s:.2f}  {e['id']}  {e['title']}（來源：{e['source']}）")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
