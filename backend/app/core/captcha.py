"""登入與註冊的人機驗證（Cloudflare Turnstile），擋住用程式大量註冊或猜密碼。

沒設定 TURNSTILE_SECRET_KEY 時不驗證（開發與 CI）。Cloudflare 提供永遠通過的測試金鑰，見 .env.example。
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TOKEN_MAX = 2048


async def _siteverify(secret: str, token: str, ip: str | None) -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(VERIFY_URL, data={"secret": secret, "response": token, "remoteip": ip or ""})
        r.raise_for_status()
        return r.json()


async def verify_captcha(token, ip: str | None) -> bool:
    secret = get_settings().turnstile_secret_key.get_secret_value()
    if not secret:
        return True
    if not isinstance(token, str) or not token or len(token) > TOKEN_MAX:
        return False
    try:
        return bool((await _siteverify(secret, token, ip)).get("success"))
    except (httpx.HTTPError, ValueError) as exc:
        # shortcut: Cloudflare 連不上時放行，避免展示時整個登入壞掉（失敗次數限流仍然有效）；
        # 正式營運要改成拒絕，或改用多家驗證服務
        logger.warning("captcha verify unavailable type=%s", type(exc).__name__)
        return True
