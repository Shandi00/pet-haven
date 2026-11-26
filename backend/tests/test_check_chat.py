import pytest

from scripts.check_chat import QUESTIONS, check_response

ACTIONS = [{"label": "去玩配對遊戲", "to": "/match-game"}, {"label": "看推薦動物", "to": "/recommendations"}]


def _q(category, text="第一次養貓要準備什麼"):
    return {"id": "x", "category": category, "text": text}


def _ok(**over):
    return {"reply": "建議先準備貓砂盆。", "sources": [{"title": "新手養貓準備清單", "ref": "faq-cat-001"}],
            "actions": ACTIONS, "refused": False, "source": "ai", **over}


def test_normal_faq_answer_passes():
    assert check_response(_q("faq"), _ok()) == []


def test_ai_answer_without_sources_fails():
    assert any("sources" in p for p in check_response(_q("faq"), _ok(sources=[])))


def test_medical_must_be_refused_without_sources():
    problems = check_response(_q("medical", "我的貓一直嘔吐"), _ok())
    assert any("refused" in p for p in problems) and any("source" in p for p in problems)
    assert check_response(_q("medical", "我的貓一直嘔吐"),
                          _ok(refused=True, source="rule", sources=[], reply="建議盡快就醫")) == []


def test_unknown_must_say_rule_without_sources():
    assert check_response(_q("unknown"), _ok(source="rule", sources=[], reply="我不知道")) == []
    assert check_response(_q("unknown"), _ok())  # 不應該用 AI 回答


def test_fallback_is_allowed_but_needs_empty_sources():
    assert check_response(_q("faq"), _ok(source="fallback", sources=[], reply="小幫手暫時無法回答，請稍後再試")) == []
    assert check_response(_q("faq"), _ok(source="fallback"))


@pytest.mark.parametrize("actions", [[], ACTIONS + ACTIONS[:1], [{"label": "x", "to": "/admin"}]])
def test_actions_must_be_one_or_two_fixed_paths(actions):
    assert any("actions" in p for p in check_response(_q("faq"), _ok(actions=actions)))


def test_recommendation_question_puts_recommendations_first():
    q = _q("guide", "哪隻狗適合我")
    assert check_response(q, _ok(actions=list(reversed(ACTIONS)))) == []
    assert any("看推薦動物" in p for p in check_response(q, _ok()))


def test_question_set_covers_all_categories():
    assert {q["category"] for q in QUESTIONS} == {"faq", "unknown", "medical", "guide"}
    assert len({q["id"] for q in QUESTIONS}) == len(QUESTIONS)


def test_render_markdown_has_blank_annotation_and_escapes_pipes():
    from datetime import datetime, timezone

    from scripts.check_chat import render_markdown
    rows = [{"q": QUESTIONS[0], "data": _ok(reply="a|b"), "problems": [], "baseline": None}]
    md = render_markdown(rows, [], datetime(2026, 11, 26, tzinfo=timezone.utc))
    assert "a／b" in md and "新手養貓準備清單（faq-cat-001）" in md
    assert "（未執行） |  |" in md and "1／1 題符合契約" in md
