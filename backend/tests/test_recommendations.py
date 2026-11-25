import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.routers import recommendations as rec_router
from app.services.recommendation import (freshness_score, generate_reasons, popularity_score, preference_score,
                                         total_score)

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "recommendation_golden.json").read_text(encoding="utf-8"))


def test_scores_match_legacy_js_golden():
    # golden 由舊版 recommendationService.js 產生（freshness 固定為 85）
    for i, c in enumerate(GOLDEN):
        exp = c["expected"]
        pref = preference_score(c["pet"], c["user"].get("recommendationProfile") or {})
        pop = popularity_score(c["pet"])
        scores = {"preferenceScore": pref, "popularityScore": pop, "freshnessScore": 85}
        assert math.isclose(pref, exp["preferenceScore"], abs_tol=1e-9), i
        assert math.isclose(pop, exp["popularityScore"], abs_tol=1e-9), i
        assert math.isclose(total_score(scores), exp["total"], abs_tol=1e-9), i
        assert generate_reasons(scores, c["user"]) == exp["reasons"], i


def test_freshness_bands():
    now = datetime(2026, 11, 25, tzinfo=timezone.utc)
    pet = lambda days: {"shelterInfo": {"intakeDate": now - timedelta(days=days)}}  # noqa: E731
    assert freshness_score(pet(10), now) == 90
    assert freshness_score(pet(60), now) == 55
    assert math.isclose(freshness_score(pet(100), now), 37.8)
    assert freshness_score(pet(1000), now) == 0
    assert freshness_score({}, now) == 50


def test_endpoint_guest_user_cache_and_refresh(api, make_user, make_pet, sync_db):
    rec_router._cache.clear()
    owner, _ = make_user("shelter")
    make_pet(owner, name="熱門", views=5)
    make_pet(owner, name="冷門", species="cat")
    r = api.get("/api/recommendations").json()
    assert r["guest"] is True and r["recommendations"][0]["name"] == "熱門"
    assert r["recommendations"][0]["recommendationReasons"] == ["熱門寵物"]
    assert api.get("/api/recommendations").json()["fromCache"] is True

    user, h = make_user(recommendationProfile={"species": ["cat"], "sizes": [], "personality": []})
    r = api.get("/api/recommendations", headers=h).json()
    assert r["hasPreferences"] is True and r["recommendations"][0]["name"] == "冷門"
    assert "scoreBreakdown" in r["recommendations"][0]
    assert api.get("/api/recommendations", headers=h).json()["fromCache"] is True
    assert api.post("/api/recommendations/refresh", headers=h).json()["cleared"] is True
    assert api.get("/api/recommendations", headers=h).json()["fromCache"] is False
