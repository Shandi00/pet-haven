import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.core.ratelimit import UserRateLimiter
from app.services import llm

SETTINGS = SimpleNamespace(gemini_api_key="test-key", gemini_model="gemini-test", llm_timeout_seconds=1)


def _reply(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: SETTINGS)


def _fake_post(monkeypatch, result, seen=None):
    async def fake(url, key, body, timeout):
        if seen is not None:
            seen.update(url=url, key=key, body=body, timeout=timeout)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(llm, "_post", fake)


def test_generate_json_parses_reply_and_keeps_key_out_of_url(monkeypatch):
    seen = {}
    _fake_post(monkeypatch, _reply('{"summary": "好"}'), seen)
    assert asyncio.run(llm.generate_json("sys", "prompt")) == {"summary": "好"}
    assert seen["url"].endswith("/models/gemini-test:generateContent") and "test-key" not in seen["url"]
    assert seen["key"] == "test-key" and seen["timeout"] == 1
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "prompt"


@pytest.mark.parametrize("result", [
    {"candidates": []},                 # 空回應
    _reply("不是 JSON"),                 # 不是 JSON
    _reply("[1, 2]"),                   # JSON 但不是物件
    _reply(""),                         # 空字串
    httpx.ReadTimeout("timeout"),       # 逾時
    httpx.HTTPStatusError("429", request=httpx.Request("POST", "http://x"), response=httpx.Response(429)),
])
def test_generate_json_returns_none_on_failure(monkeypatch, result):
    _fake_post(monkeypatch, result)
    assert asyncio.run(llm.generate_json("sys", "prompt")) is None


def test_generate_json_without_key_returns_none_without_calling(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: SimpleNamespace(**{**vars(SETTINGS), "gemini_api_key": ""}))
    seen = {}
    _fake_post(monkeypatch, _reply("{}"), seen)
    assert asyncio.run(llm.generate_json("sys", "prompt")) is None
    assert seen == {}  # 沒有金鑰就不呼叫


def test_user_rate_limiter():
    limiter = UserRateLimiter(2, 60, enabled=True)
    limiter.check("u1")
    limiter.check("u1")
    with pytest.raises(HTTPException) as e:
        limiter.check("u1")
    assert e.value.status_code == 429 and e.value.detail == "呼叫太頻繁，請稍後再試"
    limiter.check("u2")  # 別人不受影響


def test_user_rate_limiter_disabled_in_test_env():
    limiter = UserRateLimiter(1, 60)
    for _ in range(3):
        limiter.check("u1")


def test_failure_log_has_status_but_no_prompt(monkeypatch, caplog):
    err = httpx.HTTPStatusError("404", request=httpx.Request("POST", "http://x"), response=httpx.Response(404))
    _fake_post(monkeypatch, err)
    with caplog.at_level("WARNING", logger="app.services.llm"):
        asyncio.run(llm.generate_json("sys", "秘密提示"))
    assert "status=404" in caplog.text and "秘密提示" not in caplog.text and "test-key" not in caplog.text


def test_generate_json_enforces_total_deadline(monkeypatch, caplog):
    # httpx 的 timeout 是每個階段各自計算，不是整體期限；契約 §0 要整體不超過 LLM_TIMEOUT_SECONDS
    monkeypatch.setattr(llm, "get_settings", lambda: SimpleNamespace(**{**vars(SETTINGS), "llm_timeout_seconds": 0.05}))

    async def slow(url, key, body, timeout):
        await asyncio.sleep(1)
        return _reply("{}")
    monkeypatch.setattr(llm, "_post", slow)
    with caplog.at_level("WARNING", logger="app.services.llm"):
        assert asyncio.run(llm.generate_json("sys", "prompt")) is None
    assert "type=TimeoutError" in caplog.text
