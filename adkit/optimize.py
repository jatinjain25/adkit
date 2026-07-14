"""adkit optimizer: turn live-ad performance into a KILL / SCALE / KEEP verdict.

This module is pure judgment. It does no printing and touches no network, so you
can import it, feed it numbers, and get a decision back. The Meta API fetches
live in `adkit.core` (`get_insights`, `get_ads_with_insights`, `get_leads`); this
module only reasons about what they return.

Make your own logic
-------------------
The whole decision surface is a plain dataclass policy plus a pure function:

    from adkit.optimize import EvaluationPolicy, evaluate, AdMetrics

    policy = EvaluationPolicy(target_cpl=300, min_days_before_judging=3)
    decision = evaluate(metrics, policy)     # -> Decision(verdict=..., reasons=[...])

Swap the thresholds, or replace `evaluate` entirely and reuse the dataclasses.
adkit's CLI and MCP server call exactly these functions, so your policy applies
everywhere.

Privacy
-------
`score_lead_quality` takes real lead PII but never returns it: callers get
aggregate counts and redacted samples only. Nothing here writes to disk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Meta reports lead conversions under a few different action_type names
# depending on the destination. We sum any of these as "leads".
_LEAD_ACTION_TYPES = {
    "lead",
    "leadgen_grouped",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.fb_pixel_lead",
}

# A small, non-exhaustive set of throwaway email domains. Founders can extend it
# via EvaluationPolicy.disposable_domains.
_DEFAULT_DISPOSABLE = frozenset({
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
    "trashmail.com", "yopmail.com", "sharklasers.com", "getnada.com",
    "throwawaymail.com", "maildrop.cc", "dispostable.com", "fakeinbox.com",
})

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --------------------------------------------------------------------------- #
# Policy, metrics, decision
# --------------------------------------------------------------------------- #
@dataclass
class EvaluationPolicy:
    """Thresholds the optimizer judges against. Every field has a sane default
    and is meant to be overridden per advertiser.

    The learning-window guard (min_days / min_spend / min_conversions) is what
    stops adkit from killing an ad that is still in Meta's learning phase: a
    verdict of KILL or SCALE is only issued once *enough* time and spend have
    accrued to trust the numbers.
    """

    # Lead-gen target, in account-currency MAJOR units (dollars) to match what
    # Meta insights report for spend and cost-per-lead.
    target_cpl: float | None = None            # cost per (qualified) lead you'll accept, e.g. 3.00
    # Marketing target.
    target_roas: float = 1.0                   # revenue / spend break-even; >1 to require profit

    # Learning-window guard: judge only after all of these clear.
    min_days_before_judging: int = 2
    min_spend_before_judging: float = 0.0      # MAJOR units (dollars); 0 => derive ~1x daily budget
    min_conversions_before_judging: int = 3    # leads (or clicks, for proxy-only marketing)

    # Scale a winner when it is comfortably under target and has volume.
    scale_when_ratio: float = 0.6              # e.g. CPL <= 0.6*target, or ROAS >= target/0.6
    scale_budget_pct: int = 25                 # suggested daily-budget increase

    # Lead-quality knobs.
    disposable_domains: frozenset[str] = field(default_factory=lambda: _DEFAULT_DISPOSABLE)
    min_phone_digits: int = 7
    max_phone_digits: int = 15


@dataclass
class AdMetrics:
    """Normalized performance for a single ad."""

    # Meta reports insights money in MAJOR units (dollars) but budgets in MINOR
    # units (cents). We keep each as the API gives it and convert where they meet.
    objective: str = "OUTCOME_TRAFFIC"
    daily_budget: int | None = None            # MINOR units (cents), from the parent ad set
    spend: float = 0.0                         # MAJOR units (dollars)
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0                           # percent, as Meta reports it
    cpc: float = 0.0                           # MAJOR units (dollars)
    leads: int = 0
    cost_per_lead: float | None = None         # MAJOR units (dollars)
    days_running: int = 0

    @property
    def is_leadgen(self) -> bool:
        return self.objective.upper() == "OUTCOME_LEADS" or self.leads > 0


@dataclass
class Decision:
    """The optimizer's call on one ad."""

    verdict: str                               # KILL | SCALE | KEEP | WATCH | INSUFFICIENT_DATA
    reasons: list[str] = field(default_factory=list)
    suggested_action: str | None = None        # human phrase, e.g. "pause" / "raise budget 25%"
    metric: str | None = None                  # the number the verdict hinged on, e.g. "cpl"
    value: float | None = None                 # its value


@dataclass
class QualityReport:
    """Aggregate lead-quality result. Deliberately carries no raw PII."""

    total: int = 0
    qualified: int = 0
    disqualified: int = 0
    reasons: dict[str, int] = field(default_factory=dict)   # reason -> count
    samples: list[str] = field(default_factory=list)        # redacted examples only

    @property
    def qualified_rate(self) -> float:
        return self.qualified / self.total if self.total else 0.0


# --------------------------------------------------------------------------- #
# Parsing Meta insights -> AdMetrics
# --------------------------------------------------------------------------- #
def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _days_running(row: dict) -> int:
    start, stop = row.get("date_start"), row.get("date_stop")
    if not start or not stop:
        return 0
    from datetime import date

    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(stop)
    except ValueError:
        return 0
    return (e - s).days + 1  # inclusive


def normalize_insights(row: dict, *, objective: str, daily_budget: int | None = None) -> AdMetrics:
    """Turn a raw Meta insights row into AdMetrics, extracting leads from the
    `actions` / `cost_per_action_type` arrays."""
    leads = 0
    for action in row.get("actions", []) or []:
        if action.get("action_type") in _LEAD_ACTION_TYPES:
            leads += int(_to_float(action.get("value")))

    cost_per_lead = None
    for cpa in row.get("cost_per_action_type", []) or []:
        if cpa.get("action_type") in _LEAD_ACTION_TYPES:
            cost_per_lead = _to_float(cpa.get("value"))
            break
    spend = _to_float(row.get("spend"))
    if cost_per_lead is None and leads:
        cost_per_lead = spend / leads

    return AdMetrics(
        objective=objective,
        daily_budget=daily_budget,
        spend=spend,
        impressions=int(_to_float(row.get("impressions"))),
        clicks=int(_to_float(row.get("clicks"))),
        ctr=_to_float(row.get("ctr")),
        cpc=_to_float(row.get("cpc")),
        leads=leads,
        cost_per_lead=cost_per_lead,
        days_running=_days_running(row),
    )


# --------------------------------------------------------------------------- #
# Lead quality (PII in, aggregates + redactions out)
# --------------------------------------------------------------------------- #
def _find(fields: dict, *names: str) -> str:
    """Case-insensitive lookup across likely field names, incl. Meta defaults."""
    lowered = {k.lower(): v for k, v in fields.items()}
    for n in names:
        if n in lowered and lowered[n]:
            return str(lowered[n]).strip()
    return ""


def _redact_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) <= 4:
        return "*" * len(digits)
    return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]


def _redact_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    head = local[0] if local else ""
    return f"{head}***@{domain}"


def score_lead_quality(leads: list[dict], policy: EvaluationPolicy | None = None) -> QualityReport:
    """Heuristic quality pass over pulled leads. Returns aggregates + redacted
    samples; never raw PII.

    A lead is disqualified if its phone is implausible, its email is invalid or
    disposable, or it duplicates an earlier lead's phone/email.
    """
    policy = policy or EvaluationPolicy()
    report = QualityReport(total=len(leads))
    seen_phone: set[str] = set()
    seen_email: set[str] = set()

    def bump(reason: str) -> None:
        report.reasons[reason] = report.reasons.get(reason, 0) + 1

    for lead in leads:
        fields = lead.get("fields", {})
        phone = _find(fields, "phone_number", "phone", "phone number")
        email = _find(fields, "email", "email address")
        bad: list[str] = []

        digits = re.sub(r"\D", "", phone)
        if phone and not (policy.min_phone_digits <= len(digits) <= policy.max_phone_digits):
            bad.append("implausible_phone")
        if email:
            if not _EMAIL_RE.match(email):
                bad.append("invalid_email")
            elif email.rsplit("@", 1)[-1].lower() in policy.disposable_domains:
                bad.append("disposable_email")

        key_phone = digits if digits else None
        key_email = email.lower() if email else None
        if (key_phone and key_phone in seen_phone) or (key_email and key_email in seen_email):
            bad.append("duplicate")
        if key_phone:
            seen_phone.add(key_phone)
        if key_email:
            seen_email.add(key_email)

        if bad:
            report.disqualified += 1
            for r in bad:
                bump(r)
            if len(report.samples) < 5:
                tag = ",".join(bad)
                shown = _redact_phone(phone) if phone else _redact_email(email)
                report.samples.append(f"{shown} [{tag}]")
        else:
            report.qualified += 1

    return report


# --------------------------------------------------------------------------- #
# The verdict
# --------------------------------------------------------------------------- #
def _effective_min_spend(metrics: AdMetrics, policy: EvaluationPolicy) -> float:
    """Spend floor before we trust the numbers, in MAJOR units (dollars)."""
    if policy.min_spend_before_judging > 0:
        return policy.min_spend_before_judging
    # Default: about one day's budget must have been spent before we trust it.
    # daily_budget is MINOR units, spend is MAJOR, so convert cents -> dollars.
    return metrics.daily_budget / 100.0 if metrics.daily_budget else 0.0


def evaluate(
    metrics: AdMetrics,
    policy: EvaluationPolicy | None = None,
    *,
    revenue: float | None = None,
    quality: QualityReport | None = None,
) -> Decision:
    """Judge one ad. Pure: same inputs, same Decision.

    Order of reasoning:
      1. Learning-window guard. Too new / too little spend / too few conversions
         -> WATCH or INSUFFICIENT_DATA. Never kill an ad still learning.
      2. Lead-gen: judge cost-per-QUALIFIED-lead (if a quality report is given)
         against target_cpl. Marketing: ROAS = revenue/spend against target_roas
         when revenue is supplied, otherwise report proxies without a hard KILL.
    """
    policy = policy or EvaluationPolicy()
    reasons: list[str] = []

    # 1. Learning-window guard.
    min_spend = _effective_min_spend(metrics, policy)
    if metrics.days_running < policy.min_days_before_judging:
        return Decision("INSUFFICIENT_DATA", [
            f"only {metrics.days_running}d running (< {policy.min_days_before_judging}d window); still learning"
        ], suggested_action="wait")
    if min_spend and metrics.spend < min_spend:
        return Decision("WATCH", [
            f"spend {metrics.spend:.2f} below judging floor {min_spend:.2f}; let it gather data"
        ], suggested_action="wait")

    if metrics.is_leadgen:
        return _evaluate_leadgen(metrics, policy, quality, reasons)
    return _evaluate_marketing(metrics, policy, revenue, reasons)


def _evaluate_leadgen(
    metrics: AdMetrics, policy: EvaluationPolicy, quality: QualityReport | None, reasons: list[str]
) -> Decision:
    qualified = quality.qualified if quality else metrics.leads
    if quality:
        reasons.append(
            f"{qualified}/{quality.total} leads qualified "
            f"({quality.qualified_rate:.0%}); disqualified: {quality.reasons or 'none'}"
        )
    if qualified < policy.min_conversions_before_judging:
        return Decision("WATCH", reasons + [
            f"only {qualified} qualified lead(s) (< {policy.min_conversions_before_judging}); too few to judge"
        ], suggested_action="wait")

    cpql = metrics.spend / qualified if qualified else None
    if cpql is None:
        return Decision("WATCH", reasons + ["no qualified leads yet"], suggested_action="wait")
    reasons.append(f"cost per qualified lead = {cpql:.2f}")

    if policy.target_cpl is None:
        return Decision("KEEP", reasons + [
            "no target_cpl set; showing cost per qualified lead for your call"
        ], suggested_action="set a target_cpl to get KILL/SCALE calls", metric="cpql", value=cpql)

    if cpql > policy.target_cpl:
        return Decision("KILL", reasons + [
            f"cost per qualified lead {cpql:.2f} exceeds target {policy.target_cpl:.2f}"
        ], suggested_action="pause", metric="cpql", value=cpql)
    if cpql <= policy.target_cpl * policy.scale_when_ratio:
        return Decision("SCALE", reasons + [
            f"cost per qualified lead {cpql:.2f} well under target {policy.target_cpl:.2f}"
        ], suggested_action=f"raise budget {policy.scale_budget_pct}%", metric="cpql", value=cpql)
    return Decision("KEEP", reasons + [
        f"cost per qualified lead {cpql:.2f} within target {policy.target_cpl:.2f}"
    ], suggested_action="keep running", metric="cpql", value=cpql)


def _evaluate_marketing(
    metrics: AdMetrics, policy: EvaluationPolicy, revenue: float | None, reasons: list[str]
) -> Decision:
    if revenue is None:
        return Decision("KEEP", reasons + [
            f"no revenue supplied; proxies: CTR {metrics.ctr:.2f}%, CPC {metrics.cpc:.2f}, "
            f"spend {metrics.spend:.2f}. Pass revenue for a ROAS verdict."
        ], suggested_action="supply revenue for ROAS", metric="ctr", value=metrics.ctr)

    roas = revenue / metrics.spend if metrics.spend else 0.0
    reasons.append(f"ROAS = {roas:.2f} (revenue {revenue:.2f} / spend {metrics.spend:.2f})")
    if roas < policy.target_roas:
        return Decision("KILL", reasons + [
            f"ROAS {roas:.2f} below target {policy.target_roas:.2f}"
        ], suggested_action="pause", metric="roas", value=roas)
    if policy.scale_when_ratio and roas >= policy.target_roas / policy.scale_when_ratio:
        return Decision("SCALE", reasons + [
            f"ROAS {roas:.2f} comfortably above target {policy.target_roas:.2f}"
        ], suggested_action=f"raise budget {policy.scale_budget_pct}%", metric="roas", value=roas)
    return Decision("KEEP", reasons + [
        f"ROAS {roas:.2f} at or above target {policy.target_roas:.2f}"
    ], suggested_action="keep running", metric="roas", value=roas)


# --------------------------------------------------------------------------- #
# Orchestration (the one function here that does I/O, via adkit.core)
# --------------------------------------------------------------------------- #
def _is_leadgen_adset(adset: dict) -> bool:
    return (adset.get("optimization_goal") == "LEAD_GENERATION"
            or adset.get("destination_type") == "ON_AD")


def evaluate_account(
    *,
    account: str | None = None,
    campaign_id: str | None = None,
    date_preset: str = "last_3d",
    policy: EvaluationPolicy | None = None,
    revenue: dict[str, float] | None = None,
    lead_form_id: str | None = None,
    page: str | None = None,
) -> dict:
    """Pull performance for every ad and return a structured report.

    This is the orchestration entry point: it calls the fetchers in `adkit.core`
    (so it does I/O) and applies the pure `evaluate` per ad. Everything else in
    this module stays pure and unit-testable.

    revenue maps ad_id -> revenue (MAJOR units) for marketing ads. If
    lead_form_id is given, its leads are pulled once and scored, and that
    form-level quality is applied to lead-gen ads. Lead PII is not returned;
    only the aggregate QualityReport is.
    """
    from . import core  # lazy: keeps the pure module import-light

    policy = policy or EvaluationPolicy()
    revenue = revenue or {}

    quality: QualityReport | None = None
    if lead_form_id:
        quality = score_lead_quality(core.get_leads(lead_form_id, page=page), policy)

    rows = core.get_ads_with_insights(account, campaign_id, date_preset=date_preset)
    ads_out = []
    tally: dict[str, int] = {}
    for row in rows:
        ad, ins = row["ad"], row["insights"]
        adset = ad.get("adset", {}) or {}
        leadgen = _is_leadgen_adset(adset)
        metrics = normalize_insights(
            ins,
            objective="OUTCOME_LEADS" if leadgen else "OUTCOME_TRAFFIC",
            daily_budget=_to_int(adset.get("daily_budget")),
        )
        decision = evaluate(
            metrics, policy,
            revenue=revenue.get(ad.get("id")),
            quality=quality if leadgen else None,
        )
        tally[decision.verdict] = tally.get(decision.verdict, 0) + 1
        ads_out.append({
            "id": ad.get("id"),
            "name": ad.get("name"),
            "adset_id": ad.get("adset_id"),
            "daily_budget": metrics.daily_budget,
            "verdict": decision.verdict,
            "reasons": decision.reasons,
            "suggested_action": decision.suggested_action,
            "metric": decision.metric,
            "value": decision.value,
        })
    return {
        "window": date_preset,
        "summary": tally,
        "lead_quality": _quality_dict(quality) if quality else None,
        "ads": ads_out,
    }


def _to_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _quality_dict(q: QualityReport) -> dict:
    return {
        "total": q.total,
        "qualified": q.qualified,
        "disqualified": q.disqualified,
        "qualified_rate": round(q.qualified_rate, 3),
        "reasons": q.reasons,
        "samples": q.samples,   # already redacted
    }


# --------------------------------------------------------------------------- #
# Founder-facing report (pure)
# --------------------------------------------------------------------------- #
_VERDICT_MARK = {
    "KILL": "✗ KILL ", "SCALE": "▲ SCALE", "KEEP": "= KEEP ",
    "WATCH": "· WATCH", "INSUFFICIENT_DATA": "· WAIT ",
}


def format_report(report: dict) -> str:
    """Render a report dict (from evaluate_account) as founder-facing text, with
    the exact command to enact each KILL/SCALE. Contains no raw PII."""
    lines = [f"=== adkit optimize report (window: {report['window']}) ==="]
    summary = report.get("summary") or {}
    if summary:
        lines.append("verdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))

    q = report.get("lead_quality")
    if q:
        lines.append(
            f"lead quality: {q['qualified']}/{q['total']} qualified "
            f"({q['qualified_rate']:.0%}); flagged: {q['reasons'] or 'none'}"
        )
        if q["samples"]:
            lines.append("  flagged (redacted): " + "; ".join(q["samples"]))

    if not report.get("ads"):
        lines.append("\n(no ads with delivery in this window)")
        return "\n".join(lines)

    for ad in report["ads"]:
        mark = _VERDICT_MARK.get(ad["verdict"], ad["verdict"])
        lines.append(f"\n{mark}  {ad['name']}  (ad {ad['id']})")
        for r in ad["reasons"]:
            lines.append(f"    - {r}")
        if ad["verdict"] == "KILL":
            lines.append(f"    -> enact: adkit optimize apply --ad-id {ad['id']} --action pause --yes")
        elif ad["verdict"] == "SCALE":
            lines.append(f"    -> enact: adkit optimize apply --ad-id {ad['id']} --action scale --yes")

    lines.append("\nNothing was changed. adkit only recommends; you decide what to enact.")
    return "\n".join(lines)

