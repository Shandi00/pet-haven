import asyncio
import json

import pytest

from app.services import ai_chat, knowledge_base, llm

FAQ = [{"id": "faq-cat-001", "title": "新手養貓準備清單", "content": "準備貓砂盆與貓砂、飼料與水碗。", "source": "範例"},
       {"id": "faq-cat-002", "title": "貓咪結紮", "content": "結紮可以減少流浪貓。", "source": "範例"}]


def answer(message, history=None):
    return asyncio.run(ai_chat.answer(message, history or []))


def _llm(monkeypatch, reply):
    """把 generate_json 換成固定回覆，並記下送出的提示。"""
    calls = []

    async def fake(system, prompt):
        calls.append((system, prompt))
        return reply

    monkeypatch.setattr(llm, "generate_json", fake)
    return calls


@pytest.mark.parametrize("message", ["我的貓一直嘔吐怎麼辦", "狗狗拉肚子要吃什麼藥", "可以推薦獸醫嗎"])
def test_medical_question_refused_without_llm(monkeypatch, message):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: FAQ)
    calls = _llm(monkeypatch, {"reply": "x", "usedIds": ["faq-cat-001"]})
    res = answer(message)
    assert res["refused"] is True and res["source"] == "rule" and res["sources"] == []
    assert "獸醫" in res["reply"] and not calls


def test_no_knowledge_says_unknown_without_llm(monkeypatch):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: [])
    calls = _llm(monkeypatch, {"reply": "亂編的答案", "usedIds": []})
    res = answer("兔子可以吃巧克力嗎")
    assert res["source"] == "rule" and res["sources"] == [] and res["refused"] is False
    assert "不知道" in res["reply"] and not calls


@pytest.mark.parametrize("reply", [None, {}, {"reply": "", "usedIds": ["faq-cat-001"]},
                                   {"reply": "答案", "usedIds": "faq-cat-001"}, {"reply": "字" * 501, "usedIds": []}])
def test_llm_failure_or_bad_output_falls_back(monkeypatch, reply):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: FAQ)
    _llm(monkeypatch, reply)
    res = answer("第一次養貓要準備什麼")
    assert res["source"] == "fallback" and res["sources"] == [] and res["refused"] is False
    assert res["reply"] == "小幫手暫時無法回答，請稍後再試" and res["actions"]


def test_answer_cites_only_used_and_retrieved_sources(monkeypatch):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: FAQ)
    # faq-dog-999 不在檢索結果裡，不能列為來源
    _llm(monkeypatch, {"reply": " 建議先準備貓砂盆。 ", "usedIds": ["faq-cat-001", "faq-dog-999"]})
    res = answer("第一次養貓要準備什麼")
    assert res == {
        "reply": "建議先準備貓砂盆。",
        "sources": [{"title": "新手養貓準備清單", "ref": "faq-cat-001"}],
        "actions": [{"label": "去玩配對遊戲", "to": "/match-game"}, {"label": "看推薦動物", "to": "/recommendations"}],
        "refused": False,
        "source": "ai",
    }


def test_ai_answer_without_citation_is_treated_as_unknown(monkeypatch):
    # 沒有引用任何檢索到的條目，代表知識庫裡沒有答案，不能當成 AI 有根據的回答
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: FAQ)
    _llm(monkeypatch, {"reply": "資料裡沒有提到。", "usedIds": []})
    res = answer("第一次養貓要準備什麼")
    assert res["source"] == "rule" and res["sources"] == [] and "不知道" in res["reply"]


def test_recommendation_question_guides_to_recommendations(monkeypatch):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: [])
    calls = _llm(monkeypatch, {"reply": "x", "usedIds": []})
    res = answer("哪隻狗比較適合我")
    assert res["actions"][0] == {"label": "看推薦動物", "to": "/recommendations"}
    assert res["source"] == "rule" and res["sources"] == [] and "推薦" in res["reply"] and not calls
    other = answer("怎麼申請認養")
    assert other["actions"][0] == {"label": "去玩配對遊戲", "to": "/match-game"} and "不知道" in other["reply"]


def test_prompt_masks_personal_data_and_keeps_last_history(monkeypatch):
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: FAQ)
    calls = _llm(monkeypatch, {"reply": "好的。", "usedIds": ["faq-cat-001"]})
    history = [{"role": "user", "content": f"第{i}句"} for i in range(12)]
    answer("第一次養貓要準備什麼？我的電話 0912-345-678，信箱 a.b@example.com", history)
    system, prompt = calls[0]
    data = json.loads(prompt)
    assert "0912" not in prompt and "example.com" not in prompt
    assert [h["content"] for h in data["history"]] == [f"第{i}句" for i in range(2, 12)]
    assert {e["id"] for e in data["knowledge"]} == {"faq-cat-001", "faq-cat-002"}
    assert "只能根據" in system


# --- API ---

def test_chat_validation(api, make_user):
    _, h = make_user()
    assert api.post("/api/ai/chat", json={"message": "  "}, headers=h).status_code == 400
    assert api.post("/api/ai/chat", json={}, headers=h).status_code == 400
    assert api.post("/api/ai/chat", json={"message": "字" * 501}, headers=h).status_code == 400
    bad_role = {"message": "嗨", "history": [{"role": "system", "content": "x"}]}
    assert api.post("/api/ai/chat", json=bad_role, headers=h).status_code == 400
    long_history = {"message": "嗨", "history": [{"role": "user", "content": "字" * 501}]}
    res = api.post("/api/ai/chat", json=long_history, headers=h)
    assert res.status_code == 400 and res.json() == {"success": False, "message": "參數錯誤"}


def test_chat_returns_contract_shape(api, make_user, monkeypatch):
    _, h = make_user()
    monkeypatch.setattr(knowledge_base, "search", lambda q, k=3: [])
    many = [{"role": "assistant" if i % 2 else "user", "content": "嗨"} for i in range(15)]  # 超過 10 則只取最後 10 則
    res = api.post("/api/ai/chat", json={"message": " 第一次養貓要準備什麼 ", "history": many}, headers=h)
    assert res.status_code == 200
    data = res.json()["data"]
    assert set(data) == {"reply", "sources", "actions", "refused", "source"} and data["source"] == "rule"


def test_chat_requires_login(client):
    assert client.post("/api/ai/chat", json={"message": "嗨"}).status_code == 401
