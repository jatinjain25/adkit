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


def test_launch_reuses_existing_objects_by_name(monkeypatch):
    """Re-running a brief must not duplicate: a campaign/ad set/ad that already
    exists by name is reused, and no create_* call is made."""
    monkeypatch.setattr(core, "list_campaigns", lambda *a, **k: [{"id": "camp_1", "name": "Demo"}])
    monkeypatch.setattr(core, "list_adsets", lambda *a, **k: [{"id": "adset_1", "name": "Builders"}])
    monkeypatch.setattr(
        core, "list_ads",
        lambda *a, **k: [{"id": "ad_static", "name": "Static one"}, {"id": "ad_reel", "name": "Founder reel"}],
    )

    def explode(*a, **k):
        raise AssertionError("nothing should be created when everything already exists")

    for fn in ("create_campaign", "create_adset", "create_ad", "create_creative"):
        monkeypatch.setattr(core, fn, explode)

    result = core.launch_from_brief(BRIEF, go=True)
    assert result["mode"] == "live"
    assert result["created"]["campaign_id"] == "camp_1"
    assert result["created"]["ad_ids"] == ["ad_static", "ad_reel"]


def test_launch_partial_failure_reports_created_ids(monkeypatch):
    """If a step fails partway, the error carries what was already built so
    nothing is orphaned silently."""
    monkeypatch.setattr(core, "list_campaigns", lambda *a, **k: [])
    monkeypatch.setattr(core, "list_adsets", lambda *a, **k: [])
    monkeypatch.setattr(core, "list_ads", lambda *a, **k: [])
    monkeypatch.setattr(core, "create_campaign", lambda *a, **k: {"id": "camp_9"})

    def boom(*a, **k):
        raise core.graph.GraphError("adset rejected")

    monkeypatch.setattr(core, "create_adset", boom)

    import pytest

    with pytest.raises(core.LaunchError) as ei:
        core.launch_from_brief(BRIEF, go=True)
    assert ei.value.created["campaign_id"] == "camp_9"


def test_activate_delivery_walks_the_whole_chain(monkeypatch):
    """Activating an ad must also activate its ad set and campaign, in order,
    or Meta will not deliver."""
    calls = []
    monkeypatch.setattr(core.graph, "get", lambda path, params=None, **k: {"campaign_id": "c1", "adset_id": "a1"})
    monkeypatch.setattr(core.graph, "post", lambda path, data=None, **k: calls.append((path, data["status"])) or {})

    result = core.activate_delivery("ad_1")
    assert calls == [("c1", "ACTIVE"), ("a1", "ACTIVE"), ("ad_1", "ACTIVE")]
    assert [step["level"] for step in result["activated"]] == ["campaign", "adset", "ad"]
