"""/api/recommendations：對應舊版 routes/recommendations.js（含 1 小時記憶體快取）。"""
import time

from fastapi import APIRouter, Depends, Request

from app.deps import current_user, optional_user
from app.services.recommendation import generate_recommendations, get_popular_pets
from app.core.params import limit_param

router = APIRouter(prefix="/api/recommendations", tags=["Recommendations"])

CACHE_TTL = 60 * 60
# shortcut: 單一程序的記憶體快取，多個 worker 時各自快取；要多台部署時改用 Redis
_cache: dict[str, tuple[float, list]] = {}


def _clean() -> None:
    now = time.time()
    for key in [k for k, (ts, _) in _cache.items() if now - ts > CACHE_TTL]:
        _cache.pop(key, None)


def _int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.get("", summary="推薦寵物（登入時依偏好，否則熱門）")
async def recommendations(request: Request, user: dict | None = Depends(optional_user)):
    q = request.query_params
    limit_raw = q.get("limit", "8")
    limit = limit_param(limit_raw, 8)
    refresh = q.get("refresh", "false") == "true"
    now = time.time()
    if user:
        key = f"recommendations:{user['_id']}:{limit}"
        if not refresh and key in _cache and now - _cache[key][0] < CACHE_TTL:
            ts, data = _cache[key]
            return {"recommendations": data, "fromCache": True, "cacheAge": int((now - ts) * 1000)}
        profile = user.get("recommendationProfile") or {}
        has_prefs = any(profile.get(k) for k in ("species", "sizes", "personality"))
        recs = await (generate_recommendations(user, limit) if has_prefs else get_popular_pets(limit))
    else:
        has_prefs = False
        key = f"recommendations:guest:{limit}"
        if not refresh and key in _cache and now - _cache[key][0] < CACHE_TTL:
            return {"recommendations": _cache[key][1], "fromCache": True, "guest": True}
        recs = await get_popular_pets(limit)
    _cache[key] = (now, recs)
    _clean()
    return {"recommendations": recs, "fromCache": False, "hasPreferences": has_prefs, "guest": not user,
            "count": len(recs)}


@router.post("/refresh", summary="清除我的推薦快取")
async def refresh(user: dict = Depends(current_user)):
    # 舊版用 req.user.userId（不存在），實際上清不到；改用使用者 _id
    prefix = f"recommendations:{user['_id']}:"
    for key in [k for k in _cache if k.startswith(prefix)]:
        _cache.pop(key, None)
    return {"message": "推薦已重新整理", "cleared": True}
