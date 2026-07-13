"""Security regression tests. These lock in the hardening:

  * the access token rides in the Authorization header, never the URL;
  * a network error never surfaces the token;
  * the MCP server refuses spending actions without an explicit opt-in;
  * MCP file tools cannot escape the creatives directory;
  * the daily generation cap is enforced.
"""


import pytest
import requests

from adkit import creative_gen, graph


# --- M1: token handling ---------------------------------------------------- #
def test_token_goes_in_header_not_url(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers", {})
        captured["params"] = kwargs.get("params")

        class R:
            status_code = 200

            def json(self):
                return {"ok": True}

        return R()

    monkeypatch.setattr(graph.requests, "request", fake_request)
    graph.get("me", {"fields": "id"}, access_token="SECRET123")

    assert "access_token" not in captured["url"]
    assert "SECRET123" not in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer SECRET123"
    # The token must not be smuggled into query params either.
    assert "access_token" not in (captured["params"] or {})


def test_network_error_scrubs_token(monkeypatch):
    def boom(method, url, **kwargs):
        raise requests.ConnectionError(f"failed to reach {url}?access_token=SECRET123")

    monkeypatch.setattr(graph.requests, "request", boom)
    # Don't actually sleep through the retry/backoff during the test.
    if hasattr(graph, "_sleep"):
        monkeypatch.setattr(graph, "_sleep", lambda *a, **k: None)
    with pytest.raises(graph.GraphError) as ei:
        graph.get("me", access_token="SECRET123")
    assert "SECRET123" not in str(ei.value)
    assert "<redacted-token>" in str(ei.value)


# --- M2 + L3: MCP guards (skip if the mcp package is not installed) --------- #
mcp_server = pytest.importorskip("adkit.mcp_server")


def test_activate_ad_blocked_without_opt_in(monkeypatch):
    monkeypatch.delenv("ADKIT_ALLOW_SPEND", raising=False)
    with pytest.raises(PermissionError):
        mcp_server.activate_ad("ad_1")


def test_activate_ad_allowed_with_opt_in(monkeypatch):
    monkeypatch.setenv("ADKIT_ALLOW_SPEND", "1")
    monkeypatch.setattr(mcp_server.core, "set_ad_status", lambda ad_id, status: {"id": ad_id, "status": status})
    assert mcp_server.activate_ad("ad_1")["status"] == "ACTIVE"


def test_confined_path_blocks_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("ADKIT_CREATIVE_DIR", str(tmp_path / "creatives"))
    # Inside is fine.
    assert mcp_server._confined_path("ok.png").name == "ok.png"
    # Escaping the base is rejected.
    with pytest.raises(PermissionError):
        mcp_server._confined_path("../../etc/passwd")
    with pytest.raises(PermissionError):
        mcp_server._confined_path("/etc/passwd")


# --- daily generation cap -------------------------------------------------- #
def test_daily_cap_blocks_over_budget(monkeypatch, tmp_path):
    monkeypatch.setenv("ADKIT_CREATIVE_DIR", str(tmp_path))
    monkeypatch.setenv("ADKIT_GENERATION_DAILY_CAP_USD", "0.10")
    # COST_IMAGE (0.15) already exceeds a 0.10 cap, so this must refuse.
    with pytest.raises(creative_gen.CreativeGenError):
        creative_gen._enforce_daily_cap(creative_gen.COST_IMAGE)


def test_daily_cap_absent_allows(monkeypatch):
    monkeypatch.delenv("ADKIT_GENERATION_DAILY_CAP_USD", raising=False)
    # No cap set: must not raise.
    creative_gen._enforce_daily_cap(99.0)
