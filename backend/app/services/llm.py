"""Gemini 呼叫層（T12）：只負責送出請求與解析 JSON；任何失敗都回 None，由呼叫端改用備援。"""
import asyncio
import json
import logging
import time

import httpx

from app.config import get_settings
from app.core.ratelimit import UserRateLimiter

logger = logging.getLogger(__name__)
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# 全站每分鐘最多 30 次 Gemini 呼叫（所有使用者合計），保住展示當天的免費額度
site_limiter = UserRateLimiter(30, 60)


async def _post(url: str, key: str, body: dict, timeout: float) -> dict:
    # 金鑰放標頭，不放網址參數，避免出現在 log
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers={"x-goog-api-key": key}, json=body)
        r.raise_for_status()
        return r.json()


async def generate_json(system: str, prompt: str) -> dict | None:
    s = get_settings()
    key = s.gemini_api_key.get_secret_value()
    if not key:
        return None
    if not site_limiter.allow("site"):
        # 全站上限：每人限流擋不住大量帳號輪流呼叫；超過時回 None，呼叫端改用規則回覆
        logger.warning("gemini site limit reached")
        return None
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    start = time.monotonic()
    try:
        # httpx 的 timeout 是每個階段各自計算；外層 wait_for 才是契約 §0 的整體期限
        data = await asyncio.wait_for(
            _post(f"{API_BASE}/models/{s.gemini_model}:generateContent", key, body,
                  s.llm_timeout_seconds),
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
