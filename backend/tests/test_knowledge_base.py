import json

import pytest

from app.services import knowledge_base as kb

FAQ = [
    {"id": "faq-cat-001", "title": "新手養貓準備清單", "source": "範例來源",
     "content": "第一次養貓建議先準備貓砂盆與貓砂、飼料與水碗、貓抓板、外出籠。", "tags": ["貓", "新手", "準備"]},
    {"id": "faq-dog-001", "title": "狗狗每天要散步多久", "source": "範例來源",
     "content": "多數成犬每天需要散步兩次，每次約三十分鐘，依體型與年齡調整。", "tags": ["狗", "運動"]},
    {"id": "faq-adopt-001", "title": "認養流程", "source": "範例來源",
     "content": "在平台送出認養申請後，送養人會審核並安排見面，確認後完成認養。", "tags": ["認養", "流程"]},
]


@pytest.fixture
def entries(monkeypatch):
    monkeypatch.setattr(kb, "_load", lambda: FAQ)


def test_bigrams_ignore_spaces_and_punctuation():
    assert kb.bigrams("養 貓？") == {"養貓"}
    assert kb.bigrams("ABc") == {"ab", "bc"}
    assert kb.bigrams("貓") == set()


def test_related_question_finds_entry(entries):
    hits = kb.search("第一次養貓要準備什麼？")
    assert hits[0]["id"] == "faq-cat-001"
    assert set(hits[0]) == {"id", "title", "content", "source"}


def test_unrelated_question_finds_nothing(entries):
    assert kb.search("兔子可以吃巧克力嗎") == []


def test_question_words_alone_find_nothing(entries):
    assert kb.search("請問可以嗎？要怎麼做") == []


def test_results_sorted_and_limited(entries):
    hits = kb.search("認養流程與養貓準備", k=2)
    assert len(hits) <= 2
    scores = [kb.score(kb.bigrams("認養流程與養貓準備") - kb.STOP_BIGRAMS, e) for e in hits]
    assert scores == sorted(scores, reverse=True)


def test_missing_file_means_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(kb, "KB_PATH", tmp_path / "none.json")
    kb._load.cache_clear()
    assert kb.search("第一次養貓要準備什麼") == []
    kb._load.cache_clear()


def test_invalid_entries_are_dropped_on_load(monkeypatch, tmp_path):
    path = tmp_path / "kb.json"
    path.write_text(json.dumps([FAQ[0], {"id": "bad", "title": "x", "content": "y"}], ensure_ascii=False),
                    encoding="utf-8")
    monkeypatch.setattr(kb, "KB_PATH", path)
    kb._load.cache_clear()
    assert [e["id"] for e in kb._load()] == ["faq-cat-001"]
    kb._load.cache_clear()


@pytest.mark.parametrize("entry, problem", [
    ({**FAQ[0], "id": "cat-1"}, "id"),
    ({**FAQ[0], "content": "字" * 501}, "content"),
    ({**FAQ[0], "content": ""}, "content"),
    ({**FAQ[0], "source": ""}, "source"),
    ({**FAQ[0], "title": None}, "title"),
    ({**FAQ[0], "tags": "貓"}, "tags"),
    ({**FAQ[0], "url": 1}, "url"),
    ({**FAQ[0], "content": "聯絡 a@example.com"}, "個資"),
    ({**FAQ[0], "content": "電話 0912-345-678"}, "個資"),
])
def test_validate_reports_problems(entry, problem):
    problems = kb.validate([entry])
    assert problems and problem in problems[0]


def test_validate_reports_duplicate_ids():
    assert any("重複" in p for p in kb.validate([FAQ[0], FAQ[0]]))
    assert kb.validate(FAQ) == []


def test_repo_knowledge_base_is_valid():
    # T11 交付 backend/app/data/knowledge_base.json 後，這個測試確保格式符合契約附錄
    if not kb.KB_PATH.exists():
        pytest.skip("knowledge_base.json 尚未交付（T11）")
    assert kb.validate(json.loads(kb.KB_PATH.read_text(encoding="utf-8"))) == []
