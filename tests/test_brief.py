"""Tests for brief planning and the dry-run safety guarantee."""

from adkit import core

BRIEF = {
    "campaign": {"name": "Demo", "objective": "outcome_traffic", "daily_budget": 5000},
    "adsets": [
        {
            "name": "Builders",
            "daily_budget": 2500,
            "countries": ["US"],
            "ads": [
                {"name": "Static one", "message": "m", "headline": "h", "link": "https://e.com", "image": "x.png"},
                {"name": "Founder reel", "message": "m", "headline": "h",
                 "generate": {"type": "video", "prompt": "p"}},
            ],
        }
    ],
}


def test_plan_brief_summarizes_without_api():
    plan = core.plan_brief(BRIEF)
    assert plan["objective"] == "OUTCOME_TRAFFIC"
    assert plan["campaign"] == "Demo"
    assert len(plan["adsets"]) == 1
    ads = plan["adsets"][0]["ads"]
    assert ads[0]["media"] == "image"
    assert ads[0]["will_generate"] is False
    assert ads[1]["media"] == "video"
    assert ads[1]["will_generate"] is True


def test_launch_from_brief_dry_run_creates_nothing(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("dry run must not call the Graph API")

    monkeypatch.setattr(core.graph, "post", explode)
    monkeypatch.setattr(core.graph, "get", explode)

    result = core.launch_from_brief(BRIEF, go=False)
    assert result["mode"] == "dry_run"
    assert result["created"] is None
    assert result["plan"]["campaign"] == "Demo"
