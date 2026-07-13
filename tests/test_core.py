"""Unit tests for adkit.core. These never touch the network: the Graph layer is
monkeypatched, so we assert on the payloads adkit builds and on its safety
defaults."""

import json

import pytest

from adkit import config, core


def test_ad_account_normalizes_prefix():
    assert config.ad_account("123456") == "act_123456"
    assert config.ad_account("act_123456") == "act_123456"


def test_build_targeting_accepts_string_and_list():
    from_str = core.build_targeting("US,GB", interest_ids="1,2")
    assert from_str["geo_locations"]["countries"] == ["US", "GB"]
    assert from_str["flexible_spec"][0]["interests"] == [{"id": "1"}, {"id": "2"}]

    from_list = core.build_targeting(["us", "ca"], interest_ids=["9"])
    assert from_list["geo_locations"]["countries"] == ["US", "CA"]
    assert from_list["flexible_spec"][0]["interests"] == [{"id": "9"}]


def test_build_targeting_defaults_to_us_and_no_flexible_spec():
    spec = core.build_targeting("")
    assert spec["geo_locations"]["countries"] == ["US"]
    assert "flexible_spec" not in spec


def test_create_campaign_defaults_paused_and_uppercases(monkeypatch):
    captured = {}

    def fake_post(path, data=None, **kwargs):
        captured["path"] = path
        captured["data"] = data
        return {"id": "camp_1"}

    monkeypatch.setattr(core.graph, "post", fake_post)
    result = core.create_campaign("Test", objective="outcome_traffic", account="act_1")

    assert result["id"] == "camp_1"
    assert captured["data"]["status"] == "PAUSED"
    assert captured["data"]["objective"] == "OUTCOME_TRAFFIC"
    # No campaign budget means budget lives at the ad-set level.
    assert captured["data"]["is_adset_budget_sharing_enabled"] == "false"


def test_create_ad_defaults_paused(monkeypatch):
    captured = {}
    monkeypatch.setattr(core.graph, "post", lambda path, data=None, **k: captured.update(data=data) or {"id": "ad_1"})
    core.create_ad("Ad", "adset_1", "creative_1", account="act_1")
    assert captured["data"]["status"] == "PAUSED"
    assert json.loads(captured["data"]["creative"]) == {"creative_id": "creative_1"}


def test_create_creative_requires_media(monkeypatch):
    monkeypatch.setattr(core.config, "ad_account", lambda a=None: "act_1")
    monkeypatch.setattr(core.config, "page", lambda p=None: "page_1")
    monkeypatch.setattr(core.config, "ig_actor", lambda i=None: None)
    monkeypatch.setattr(core.config, "optional", lambda name: "https://example.com")
    with pytest.raises(ValueError):
        core.create_creative("c", "msg", "headline")  # no image and no video
