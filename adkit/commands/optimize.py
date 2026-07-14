"""adkit optimize: analyze live ads and recommend KILL / SCALE / KEEP.

`optimize report` is read-only and mutates nothing: it pulls performance, judges
each ad against your policy, and prints a founder-facing report (never any raw
lead PII). `optimize apply` is the separate, explicitly-confirmed step that
enacts one verdict (pause a loser, or raise a winner's budget).
"""

import json as _json

import click

from .. import core
from ..optimize import EvaluationPolicy, evaluate_account, format_report


def _parse_revenue(pairs: tuple[str, ...]) -> dict[str, float]:
    """Parse repeated --revenue AD_ID=AMOUNT into {ad_id: amount} (MAJOR units)."""
    out: dict[str, float] = {}
    for raw in pairs:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" not in part:
                raise click.BadParameter(f"expected AD_ID=AMOUNT, got {part!r}")
            ad_id, amount = part.split("=", 1)
            out[ad_id.strip()] = float(amount.strip())
    return out


@click.group()
def optimize():
    """Analyze live ads and recommend what to kill or scale."""


@optimize.command("report")
@click.option("--account", default=None, help="Ad account id. Defaults to META_AD_ACCOUNT_ID.")
@click.option("--campaign-id", default=None, help="Limit to one campaign.")
@click.option("--window", default="last_3d", show_default=True,
              help="Meta date preset, e.g. last_3d, last_7d, maximum.")
@click.option("--target-cpl", type=float, default=None,
              help="Target cost per (qualified) lead, in account-currency dollars. "
                   "Required for KILL/SCALE calls on lead-gen ads.")
@click.option("--target-roas", type=float, default=1.0, show_default=True,
              help="Break-even ROAS for marketing ads (revenue/spend).")
@click.option("--revenue", multiple=True, metavar="AD_ID=AMOUNT",
              help="Revenue (dollars) for a marketing ad, repeatable or comma-separated.")
@click.option("--lead-form-id", default=None,
              help="Pull and quality-score this Instant Form's leads (needs leads_retrieval).")
@click.option("--page", default=None, help="Page id for lead pulling. Defaults to META_PAGE_ID.")
@click.option("--min-days", type=int, default=2, show_default=True,
              help="Don't judge ads younger than this (learning window).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the raw report as JSON.")
def report(account, campaign_id, window, target_cpl, target_roas, revenue,
           lead_form_id, page, min_days, as_json):
    """Pull performance and recommend KILL/SCALE/KEEP. Changes nothing."""
    policy = EvaluationPolicy(
        target_cpl=target_cpl, target_roas=target_roas, min_days_before_judging=min_days,
    )
    result = evaluate_account(
        account=account, campaign_id=campaign_id, date_preset=window, policy=policy,
        revenue=_parse_revenue(revenue), lead_form_id=lead_form_id, page=page,
    )
    if as_json:
        click.echo(_json.dumps(result, indent=2))
    else:
        click.echo(format_report(result))


@optimize.command("apply")
@click.option("--ad-id", required=True, help="Ad to act on.")
@click.option("--action", type=click.Choice(["pause", "scale"]), required=True,
              help="pause = stop a losing ad (safe). scale = raise its ad set's budget (spends more).")
@click.option("--scale-pct", type=float, default=25, show_default=True,
              help="Percent to raise the ad set's daily budget when --action scale.")
@click.option("--yes", is_flag=True, default=False,
              help="Required to actually apply. Without it, this prints what it would do.")
def apply(ad_id, action, scale_pct, yes):
    """Enact one recommendation. `scale` spends more, so it requires --yes."""
    if action == "pause":
        if not yes:
            click.echo(f"Would pause ad {ad_id}. Re-run with --yes to apply.")
            return
        core.set_ad_status(ad_id, "PAUSED")
        click.echo(f"  ✓ ad {ad_id} is now PAUSED (spend stopped)")
        return

    # scale
    if not yes:
        click.echo(f"Would raise ad {ad_id}'s ad set daily budget by {scale_pct:.0f}%. "
                   "This increases spend. Re-run with --yes to apply.")
        return
    try:
        result = core.scale_ad_budget(ad_id, scale_pct)
    except ValueError as e:
        raise SystemExit(str(e))
    click.echo(
        f"  ✓ ad set {result['adset_id']} daily budget "
        f"{result['old_daily_budget']} -> {result['new_daily_budget']} (minor units, +{scale_pct:.0f}%)"
    )
