"""Unit tests for adkit.core. These never touch the network: the Graph layer is
monkeypatched, so we assert on the payloads adkit builds and on its safety
defaults."""

import json

import pytest

from adkit import config, core


def test_ad_account_normalizes_prefix():
    assert config.ad_account("123456") == "act_123456"
    assert config.ad_account("act_123456") == "act_123456"


def test_find_env_file_prefers_cwd_then_explicit(monkeypatch, tmp_path):
    # A .env in the working directory is discovered (the pipx/plugin case, where
    # there is no repo checkout to read from).
    cwd_env = tmp_path / ".env"
    cwd_env.write_text("META_ACCESS_TOKEN=from_cwd\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ADKIT_ENV", raising=False)
    assert config.find_env_file() == cwd_env

    # ADKIT_ENV overrides everything.
    explicit = tmp_path / "custom.env"
    explicit.write_text("META_ACCESS_TOKEN=from_explicit\n")
    monkeypatch.setenv("ADKIT_ENV", str(explicit))
    assert config.find_env_file() == explicit


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


def test_build_targeting_sets_advantage_audience_flag():
    # Meta requires this flag on every ad set; default is 0 (use the audience as
    # defined), and it must be settable to 1 (let Advantage expand it).
    assert core.build_targeting("US")["targeting_automation"] == {"advantage_audience": 0}
    assert core.build_targeting("US", advantage_audience=1)["targeting_automation"] == {
        "advantage_audience": 1
    }


def test_create_adset_injects_flag_into_targeting_override(monkeypatch):
    captured = {}
    monkeypatch.setattr(core.config, "ad_account", lambda a=None: "act_1")
    monkeypatch.setattr(core.config, "page", lambda p=None: "page_1")
    monkeypatch.setattr(core.graph, "post", lambda path, data=None, **k: captured.update(data=data) or {"id": "as_1"})
    # A hand-supplied targeting spec that omits the required flag must still get it.
    core.create_adset("s", "camp_1", 1000, targeting={"geo_locations": {"countries": ["US"]}})
    sent = json.loads(captured["data"]["targeting"])
    assert sent["targeting_automation"] == {"advantage_audience": 0}


def test_create_creative_uses_instagram_user_id(monkeypatch):
    # instagram_actor_id is deprecated; the creative must send instagram_user_id.
    captured = {}
    monkeypatch.setattr(core.config, "ad_account", lambda a=None: "act_1")
    monkeypatch.setattr(core.config, "page", lambda p=None: "page_1")
    monkeypatch.setattr(core.config, "ig_actor", lambda i=None: "ig_123")
    monkeypatch.setattr(core.config, "optional", lambda name: "https://example.com")
    monkeypatch.setattr(core, "upload_image", lambda *a, **k: "hash_1")
    monkeypatch.setattr(core.graph, "post", lambda path, data=None, **k: captured.update(data=data) or {"id": "cr_1"})
    core.create_creative("c", "msg", "head", image="x.png", cta="LEARN_MORE")
    oss = json.loads(captured["data"]["object_story_spec"])
    assert oss["instagram_user_id"] == "ig_123"
    assert "instagram_actor_id" not in oss
