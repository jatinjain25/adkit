"""Tests for the Ad Library research module. No network: graph.get is mocked."""

from datetime import datetime, timezone

import pytest

from adkit import research

NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)

SAMPLE = [
    # Advertiser A: 2 variants, one running ~171 days -> strong winner
    {"page_name": "BrightLearn", "page_id": "1", "ad_delivery_start_time": "2026-02-01",
     "ad_creative_bodies": ["Crack your exams with live classes"],
     "ad_creative_link_titles": ["Book a free demo"],
     "ad_creative_link_captions": ["brightlearn.in"], "publisher_platforms": ["facebook", "instagram"],
     "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=1"},
    {"page_name": "BrightLearn", "page_id": "1", "ad_delivery_start_time": "2026-07-01",
     "ad_creative_bodies": ["New batch starting"], "ad_creative_link_titles": ["Book a free demo"],
     "ad_creative_link_captions": ["brightlearn.in"], "publisher_platforms": ["instagram"],
     "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=2"},
    # Advertiser B: 1 variant, ~11 days -> weaker
    {"page_name": "QuickTutor", "page_id": "2", "ad_delivery_start_time": "2026-07-11",
     "ad_creative_bodies": ["1:1 tutoring"], "ad_creative_link_titles": ["Sign up"],
     "ad_creative_link_captions": ["quicktutor.app"], "publisher_platforms": ["facebook"],
     "ad_snapshot_url": "https://www.facebook.com/ads/library/?id=3"},
]


def test_days_running_uses_stop_or_now():
    ad = {"ad_delivery_start_time": "2026-07-01", "ad_delivery_stop_time": "2026-07-11"}
    assert research._days_running(ad, NOW) == 10
    ongoing = {"ad_delivery_start_time": "2026-07-12"}
    assert research._days_running(ongoing, NOW) == 10  # to NOW


def test_analyze_ranks_by_winner_proxy():
    report = research.analyze([dict(a) for a in SAMPLE], now=NOW)
    assert report["total_ads"] == 3
    assert report["total_advertisers"] == 2
    # BrightLearn (2 variants x long run) must outrank QuickTutor.
    assert report["advertisers"][0]["advertiser"] == "BrightLearn"
    assert report["advertisers"][0]["variants"] == 2
    assert report["advertisers"][0]["winner_score"] > report["advertisers"][1]["winner_score"]
    # Longest-running ad surfaces first with its snapshot link.
    assert report["top_ads"][0]["advertiser"] == "BrightLearn"
    assert report["top_ads"][0]["snapshot_url"].endswith("id=1")


def test_analyze_extracts_patterns():
    report = research.analyze([dict(a) for a in SAMPLE], now=NOW)
    assert "Book a free demo" in report["patterns"]["dominant_ctas"]
    assert "brightlearn.in" in report["patterns"]["dominant_domains"]
    assert report["patterns"]["platform_mix"]["instagram"] == 2


def test_search_maps_permission_error(monkeypatch):
    def boom(path, params=None, **k):
        raise research.graph.GraphError("Meta API error #10 (subcode 2332002): permission")

    monkeypatch.setattr(research.graph, "get", boom)
    with pytest.raises(research.AdLibraryAccessError) as ei:
        research.search_ad_library("edtech", "IN")
    assert "library/api" in str(ei.value)


def test_build_seed_brief_is_valid_and_seeded():
    from adkit import core
    report = research.analyze([dict(a) for a in SAMPLE], now=NOW)
    text = research.build_seed_brief(report, "edtech", "in")
    import yaml  # available via the yaml/dev extra used in CI
    spec = yaml.safe_load(text)
    # It must parse and be a valid brief adkit can plan.
    plan = core.plan_brief(spec)
    assert plan["adsets"][0]["ads"][0]["will_generate"] is True  # has a generate: block
    assert spec["adsets"][0]["countries"] == ["IN"]
    # The dominant competitor CTA ("Book a free demo") maps to a Meta CTA enum.
    assert spec["adsets"][0]["ads"][0]["cta"] in {"BOOK_TRAVEL", "LEARN_MORE"}
    # It links competitors to study, not their verbatim copy.
    assert "ads/library" in text


def test_research_marker_and_reminder(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv("ADKIT_NO_TIPS", raising=False)
    # No research yet -> reminder shows.
    assert research.recent_research() is None
    assert research.research_reminder() is not None
    # After recording -> reminder is silent.
    research.record_research("edtech", "IN")
    assert research.recent_research()["keyword"] == "edtech"
    assert research.research_reminder() is None


def test_reminder_silenced_by_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))  # fresh: no marker
    monkeypatch.setenv("ADKIT_NO_TIPS", "1")
    assert research.research_reminder() is None


def test_search_paginates_then_stops(monkeypatch):
    pages = [
        {"data": SAMPLE[:2], "paging": {"cursors": {"after": "CUR"}}},
        {"data": SAMPLE[2:], "paging": {}},
    ]
    calls = {"n": 0}

    def fake_get(path, params=None, **k):
        assert path == "ads_archive"
        i = calls["n"]
        calls["n"] += 1
        return pages[i]

    monkeypatch.setattr(research.graph, "get", fake_get)
    ads = research.search_ad_library("edtech", "IN", limit=100)
    assert len(ads) == 3
    assert calls["n"] == 2
