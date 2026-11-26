"""Gemini 呼叫層（T12）：只負責送出請求與解析 JSON；任何失敗都回 None，由呼叫端改用備援。"""
import json
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


async def _post(url: str, key: str, body: dict, timeout: float) -> dict:
    # 金鑰放標頭，不放網址參數，避免出現在 log
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers={"x-goog-api-key": key}, json=body)
        r.raise_for_status()
        return r.json()


async def generate_json(system: str, prompt: str) -> dict | None:
    s = get_settings()
    if not s.gemini_api_key:
        return None
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    start = time.monotonic()
    try:
        data = await _post(f"{API_BASE}/models/{s.gemini_model}:generateContent", s.gemini_api_key, body,
                           s.llm_timeout_seconds)
        result = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        if not isinstance(result, dict):
            raise ValueError("not a JSON object")
        return result
    except Exception as exc:  # noqa: BLE001 — 任何失敗都改用備援，不能讓主線中斷
        # 只記類型、HTTP 狀態碼與耗時，不記提示或回覆內容
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else "-"
        logger.warning("gemini call failed type=%s status=%s elapsed_ms=%d", type(exc).__name__, status,
                       (time.monotonic() - start) * 1000)
        return None
