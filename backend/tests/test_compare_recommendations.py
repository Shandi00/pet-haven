from datetime import datetime, timezone

from scripts.compare_recommendations import PERSONAS, render_markdown

REASON = {"summary": "小黑很親人", "highlights": ["親人"], "cautions": ["需|陪伴"], "source": "ai"}


def test_render_markdown_lists_three_methods_and_blank_annotation():
    res = [{"persona": PERSONAS[0],
            "popular": [{"name": "阿福", "recommendationReasons": ["熱門寵物"]}],
            "top3": [{"pet": {"name": "小黑"}, "score": 88, "matchLevel": "excellent",
                      "reason": REASON, "ruleReason": {**REASON, "source": "rule"}}]}]
    md = render_markdown(res, datetime(2026, 11, 26, tzinfo=timezone.utc))
    assert "熱門推薦（既有）" in md and "規則理由" in md and "規則＋AI 理由" in md
    assert "| 1 | 阿福（熱門寵物） | 小黑（88 分，excellent） |  |" in md
    assert "| 2 | — | — |  |" in md  # 不足 3 筆時補「—」
    assert "需／陪伴" in md  # 表格內的 | 要換掉，避免破壞表格
    assert "| ai |  |" in md  # 人工標註欄留空


def test_empty_persona_has_no_profiles():
    md = render_markdown([{"persona": PERSONAS[2], "popular": [], "top3": []}], datetime.now(timezone.utc))
    assert "沒有填寫任何配對檔案" in md
