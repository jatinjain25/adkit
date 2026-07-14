"""Tests for the optimizer: pure verdicts, lead-quality redaction, insight
parsing, fetch paths, and the recommend-only / confirmed-apply CLI."""

from click.testing import CliRunner

from adkit import core
from adkit import optimize as o
from adkit.commands import optimize as opt_cmd


# --------------------------------------------------------------------------- #
# evaluate() verdict table
# --------------------------------------------------------------------------- #
def _leadgen(**kw):
    base = dict(objective="OUTCOME_LEADS", daily_budget=5000, spend=60.0, days_running=3, leads=20)
    base.update(kw)
    return o.AdMetrics(**base)


def test_new_ad_in_window_is_insufficient_data():
    m = _leadgen(days_running=1)
    assert o.evaluate(m, o.EvaluationPolicy(target_cpl=3.0)).verdict == "INSUFFICIENT_DATA"


def test_below_spend_floor_is_watch():
    # daily_budget 5000 cents -> $50 floor; spend $10 is under it.
    m = _leadgen(spend=10.0, days_running=3)
    assert o.evaluate(m, o.EvaluationPolicy(target_cpl=3.0)).verdict == "WATCH"


def test_leadgen_high_cpl_is_kill():
    m = _leadgen(spend=200.0, leads=20)   # $10 per lead
    d = o.evaluate(m, o.EvaluationPolicy(target_cpl=3.0))
    assert d.verdict == "KILL" and d.metric == "cpql"


def test_leadgen_low_cpl_is_scale():
    # $0.60 per lead (target 3 -> under 0.6*3), and spend $60 clears the $50 floor.
    m = _leadgen(spend=60.0, leads=100)
    assert o.evaluate(m, o.EvaluationPolicy(target_cpl=3.0)).verdict == "SCALE"


def test_leadgen_on_target_is_keep():
    m = _leadgen(spend=50.0, leads=20)    # $2.50 per lead, between 0.6*3 and 3
    assert o.evaluate(m, o.EvaluationPolicy(target_cpl=3.0)).verdict == "KEEP"


def test_leadgen_no_target_keeps_and_reports():
    d = o.evaluate(_leadgen(spend=50.0, leads=20), o.EvaluationPolicy(target_cpl=None))
    assert d.verdict == "KEEP" and d.value is not None


def test_marketing_no_revenue_keeps_with_proxies():
    m = o.AdMetrics(objective="OUTCOME_TRAFFIC", daily_budget=5000, spend=60.0, ctr=1.1, cpc=0.8, days_running=3)
    d = o.evaluate(m, o.EvaluationPolicy())
    assert d.verdict == "KEEP" and "no revenue" in d.reasons[-1].lower()


def test_marketing_low_roas_is_kill_high_is_scale():
    m = o.AdMetrics(objective="OUTCOME_TRAFFIC", daily_budget=5000, spend=100.0, days_running=3)
    assert o.evaluate(m, o.EvaluationPolicy(target_roas=1.0), revenue=50.0).verdict == "KILL"
    assert o.evaluate(m, o.EvaluationPolicy(target_roas=1.0), revenue=300.0).verdict == "SCALE"


# --------------------------------------------------------------------------- #
# lead quality: heuristics + redaction (no raw PII ever leaves)
# --------------------------------------------------------------------------- #
def test_score_lead_quality_flags_and_redacts():
    leads = [
        {"fields": {"full_name": "Real Person", "phone_number": "+1 415 555 0199", "email": "real@gmail.com"}},
        {"fields": {"full_name": "Bad Phone", "phone_number": "12", "email": "x@example.com"}},
        {"fields": {"full_name": "Disposable", "phone_number": "+14155550123", "email": "a@mailinator.com"}},
        {"fields": {"full_name": "Dupe", "phone_number": "+1 415 555 0199", "email": "real@gmail.com"}},
    ]
    q = o.score_lead_quality(leads)
    assert q.total == 4
    assert q.qualified == 1
    assert q.disqualified == 3
    assert q.reasons.get("implausible_phone") == 1
    assert q.reasons.get("disposable_email") == 1
    assert q.reasons.get("duplicate") == 1
    blob = " ".join(q.samples)
    # No full raw phone or full raw email may appear in the redacted samples.
    assert "14155550199" not in blob
    assert "real@gmail.com" not in blob


# --------------------------------------------------------------------------- #
# normalize_insights parsing (leads + CPL from actions arrays)
# --------------------------------------------------------------------------- #
def test_normalize_insights_extracts_leads_and_cpl():
    row = {
        "spend": "60.00", "impressions": "1000", "clicks": "50", "ctr": "5", "cpc": "1.2",
        "actions": [{"action_type": "lead", "value": "20"}, {"action_type": "link_click", "value": "50"}],
        "cost_per_action_type": [{"action_type": "lead", "value": "3.0"}],
        "date_start": "2026-07-10", "date_stop": "2026-07-12",
    }
    m = o.normalize_insights(row, objective="OUTCOME_LEADS", daily_budget=5000)
    assert m.leads == 20
    assert m.cost_per_lead == 3.0
    assert m.spend == 60.0
    assert m.days_running == 3   # inclusive


# --------------------------------------------------------------------------- #
# fetch paths (token never in the URL; correct edges)
# --------------------------------------------------------------------------- #
def test_get_insights_path(monkeypatch):
    captured = {}
    monkeypatch.setattr(core.graph, "get",
                        lambda path, params=None, **k: captured.update(path=path, params=params) or {})
    core.get_insights("ad_1", date_preset="last_7d")
    assert captured["path"] == "ad_1"
    assert "insights.date_preset(last_7d)" in captured["params"]["fields"]


def test_get_leads_uses_page_token_and_leads_edge(monkeypatch):
    captured = {}
    monkeypatch.setattr(core, "page_access_token", lambda pid: "PAGETOKEN")
    monkeypatch.setattr(core.config, "page", lambda p=None: "page_1")

    def fake_get(path, params=None, *, access_token=None):
        captured.update(path=path, token=access_token)
        return {"data": [{"id": "l1", "created_time": "t", "field_data": [
            {"name": "phone_number", "values": ["+14155550199"]}]}]}

    monkeypatch.setattr(core.graph, "get", fake_get)
    leads = core.get_leads("form_9")
    assert captured["path"] == "form_9/leads"
    assert captured["token"] == "PAGETOKEN"
    assert leads[0]["fields"]["phone_number"] == "+14155550199"


# --------------------------------------------------------------------------- #
# CLI: report mutates nothing; apply requires --yes and routes correctly
# --------------------------------------------------------------------------- #
def test_report_cli_is_read_only(monkeypatch):
    fake = {"window": "last_3d", "summary": {"KILL": 1}, "lead_quality": None, "ads": [
        {"id": "a1", "name": "Loser", "adset_id": "s1", "daily_budget": 5000,
         "verdict": "KILL", "reasons": ["cost per qualified lead 9.00 exceeds target 3.00"],
         "suggested_action": "pause", "metric": "cpql", "value": 9.0}]}
    monkeypatch.setattr(opt_cmd, "evaluate_account", lambda **k: fake)
    # Any mutation call should blow up.
    for fn in ("set_ad_status", "scale_ad_budget", "set_adset_budget"):
        monkeypatch.setattr(opt_cmd.core, fn, lambda *a, **k: (_ for _ in ()).throw(AssertionError("mutation!")))
    res = CliRunner().invoke(opt_cmd.report, ["--target-cpl", "3"])
    assert res.exit_code == 0
    assert "KILL" in res.output and "apply --ad-id a1" in res.output


def test_apply_requires_yes(monkeypatch):
    calls = []
    monkeypatch.setattr(opt_cmd.core, "set_ad_status", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(opt_cmd.core, "scale_ad_budget", lambda *a, **k: calls.append(a))
    # Without --yes: prints intent, mutates nothing.
    r1 = CliRunner().invoke(opt_cmd.apply, ["--ad-id", "a1", "--action", "pause"])
    r2 = CliRunner().invoke(opt_cmd.apply, ["--ad-id", "a1", "--action", "scale"])
    assert r1.exit_code == 0 and r2.exit_code == 0 and calls == []


def test_apply_pause_and_scale_route(monkeypatch):
    calls = {}
    monkeypatch.setattr(opt_cmd.core, "set_ad_status", lambda ad, st: calls.setdefault("pause", (ad, st)))
    monkeypatch.setattr(opt_cmd.core, "scale_ad_budget",
                        lambda ad, pct: calls.setdefault("scale", (ad, pct)) or
                        {"adset_id": "s1", "old_daily_budget": 5000, "new_daily_budget": 6250})
    CliRunner().invoke(opt_cmd.apply, ["--ad-id", "a1", "--action", "pause", "--yes"])
    CliRunner().invoke(opt_cmd.apply, ["--ad-id", "a1", "--action", "scale", "--scale-pct", "25", "--yes"])
    assert calls["pause"] == ("a1", "PAUSED")
    assert calls["scale"] == ("a1", 25)
