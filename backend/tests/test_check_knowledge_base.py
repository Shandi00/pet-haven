import json

from scripts import check_knowledge_base as tool

GOOD = {"id": "faq-cat-001", "title": "新手養貓準備清單", "source": "範例來源",
        "content": "第一次養貓建議先準備貓砂盆與貓砂、飼料與水碗。", "tags": ["貓"]}


def _write(tmp_path, data):
    path = tmp_path / "kb.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_valid_file_passes_and_shows_hits(tmp_path, capsys):
    code = tool.main([_write(tmp_path, [GOOD]), "--ask", "第一次養貓要準備什麼", "--ask", "兔子可以吃巧克力嗎"])
    out = capsys.readouterr().out
    assert code == 0
    assert "1 筆條目，格式正確" in out
    assert "faq-cat-001" in out and "新手養貓準備清單" in out
    assert "查無資料" in out  # 第二題


def test_problems_are_listed_and_fail(tmp_path, capsys):
    code = tool.main([_write(tmp_path, [GOOD, {**GOOD, "source": ""}])])
    out = capsys.readouterr().out
    assert code == 1 and "source 必填" in out and "重複" in out


def test_missing_or_broken_file_fails(tmp_path, capsys):
    assert tool.main([str(tmp_path / "none.json")]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{不是 JSON", encoding="utf-8")
    assert tool.main([str(broken)]) == 1
    assert "無法讀取" in capsys.readouterr().out
