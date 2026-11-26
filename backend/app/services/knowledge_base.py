"""FAQ 知識庫檢索（T14）：契約 §0「知識庫檢索」與附錄「知識庫格式」。

search() 用字元 bigram 計算問題與條目的重疊；低於 MIN_SCORE 視為查無資料，聊天就回「不知道」、不呼叫 LLM。
"""
import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

KB_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge_base.json"
TOP_K = 3
# 問題 bigram 被條目涵蓋的比例；門檻要在 T19 用實際問題集再調整
MIN_SCORE = 0.3
CONTENT_MAX = 500
# 問句常見詞，不代表主題，不列入比對
STOP_BIGRAMS = {"什麼", "怎麼", "可以", "如何", "請問", "一下", "應該", "需要", "是不", "不是", "有沒", "沒有",
                "為什", "麼要", "麼做", "要怎", "我想", "想要", "知道"}
_ID = re.compile(r"^faq-[a-z0-9]+(-[a-z0-9]+)*-\d{3}$")
_PERSONAL = (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(r"09\d{2}-?\d{3}-?\d{3}"))
_FIELDS = ("id", "title", "content", "source")


def bigrams(text: str) -> set[str]:
    s = "".join(c for c in (text or "").lower() if c.isalnum())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _entry_text(e: dict) -> str:
    return " ".join([e.get("title") or "", " ".join(e.get("tags") or []), e.get("content") or ""])


def score(query_bigrams: set[str], entry: dict) -> float:
    if not query_bigrams:
        return 0.0
    return len(query_bigrams & bigrams(_entry_text(entry))) / len(query_bigrams)


def _entry_problems(e) -> list[str]:
    if not isinstance(e, dict):
        return ["條目不是物件"]
    out = []
    if not isinstance(e.get("id"), str) or not _ID.match(e["id"]):
        out.append("id 格式應為 faq-<主題>-<三位數>")
    for key in ("title", "source"):
        if not isinstance(e.get(key), str) or not e[key].strip():
            out.append(f"{key} 必填")
    content = e.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > CONTENT_MAX:
        out.append(f"content 必填且最多 {CONTENT_MAX} 字")
    if "url" in e and not isinstance(e["url"], str):
        out.append("url 必須是字串")
    if "tags" in e and not (isinstance(e["tags"], list) and all(isinstance(t, str) for t in e["tags"])):
        out.append("tags 必須是字串陣列")
    if any(p.search(_entry_text(e)) for p in _PERSONAL):
        out.append("疑似含個資（Email 或手機號碼）")
    return out


def validate(entries) -> list[str]:
    """回傳所有不符合契約附錄的地方；空陣列代表格式正確。"""
    if not isinstance(entries, list):
        return ["知識庫必須是陣列"]
    problems, seen = [], set()
    for i, e in enumerate(entries):
        label = e.get("id") if isinstance(e, dict) else f"#{i}"
        problems += [f"{label}：{p}" for p in _entry_problems(e)]
        if isinstance(e, dict) and e.get("id") in seen:
            problems.append(f"{label}：id 重複")
        seen.add(label)
    return problems


@lru_cache
def _load() -> list[dict]:
    # 檔案只在啟動後第一次檢索時讀取；改了知識庫要重啟後端
    if not KB_PATH.exists():
        logger.warning("knowledge base not found path=%s", KB_PATH.name)
        return []
    try:
        data = json.loads(KB_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("knowledge base unreadable type=%s", type(exc).__name__)
        return []
    if not isinstance(data, list):
        logger.warning("knowledge base is not a list")
        return []
    valid = [e for e in data if not _entry_problems(e)]
    if len(valid) != len(data):
        logger.warning("knowledge base dropped invalid entries count=%d", len(data) - len(valid))
    return valid


def ranked(query: str, entries: list[dict]) -> list[tuple[float, dict]]:
    """所有達到門檻的 (分數, 條目)，分數高的在前；檢查工具也用這個顯示分數。"""
    qb = bigrams(query) - STOP_BIGRAMS
    scored = [(score(qb, e), e) for e in entries]
    return sorted((se for se in scored if se[0] >= MIN_SCORE), key=lambda se: (-se[0], se[1]["id"]))


def search(query: str, k: int = TOP_K) -> list[dict]:
    """回傳最相關的前 k 筆 {id, title, content, source}；查無資料回空陣列。"""
    return [{f: e[f] for f in _FIELDS} for _, e in ranked(query, _load())[:k]]


def all_entries() -> list[dict]:
    """整份知識庫的 {id, title, content, source}：關鍵字比對不到時，交給 LLM 依語意挑選（聊天的後備檢索）。
    shortcut: 知識庫只有幾十則，直接整份放進提示；超過約 200 則時改用向量檢索。"""
    return [{f: e[f] for f in _FIELDS} for e in _load()]
