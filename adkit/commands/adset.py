import json
from pathlib import Path

import click

from .. import core


@click.group()
def adset():
    """Create and list ad sets."""


@adset.command("create")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option(
    "--page",
    default=None,
    help="Page id to promote. Defaults to META_PAGE_ID in .env.",
)
@click.option("--name", required=True, help="Ad set name shown in Ads Manager.")
@click.option("--campaign-id", required=True, help="Parent campaign ID (from `campaign create`).")
@click.option(
    "--daily-budget",
    type=int,
    required=True,
    help="Daily budget in account-currency MINOR units (cents for USD, paise for INR). "
    "E.g. 5000 = $50.00/day on a USD account.",
)
@click.option(
    "--countries",
    default="US",
    show_default=True,
    help="Comma-separated ISO country codes, e.g. 'US' or 'US,CA,GB'.",
)
@click.option("--age-min", type=int, default=25, show_default=True)
@click.option("--age-max", type=int, default=55, show_default=True)
@click.option(
    "--interest-ids",
    default="",
    help="Comma-separated Meta interest IDs (find via `adkit targeting search`). "
    "Leave empty for broad targeting.",
)
@click.option(
    "--targeting-json",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional path to a JSON file with a full Meta targeting spec. "
    "Overrides --countries/--age-*/--interest-ids if provided.",
)
@click.option(
    "--optimization-goal",
    type=click.Choice(core.OPTIMIZATION_GOALS, case_sensitive=False),
    default="LEAD_GENERATION",
    show_default=True,
)
@click.option(
    "--billing-event",
    type=click.Choice(core.BILLING_EVENTS, case_sensitive=False),
    default="IMPRESSIONS",
    show_default=True,
)
@click.option(
    "--destination-type",
    type=click.Choice(core.DESTINATION_TYPES, case_sensitive=False),
    default="ON_AD",
    show_default=True,
    help="ON_AD = Instant Form (lead capture in-app). WEBSITE sends to your landing page.",
)
@click.option(
    "--status",
    type=click.Choice(["PAUSED", "ACTIVE"], case_sensitive=False),
    default="PAUSED",
    show_default=True,
)
@click.option(
    "--bid-strategy",
    type=click.Choice(
        ["LOWEST_COST_WITHOUT_CAP", "LOWEST_COST_WITH_BID_CAP", "COST_CAP"],
        case_sensitive=False,
    ),
    default="LOWEST_COST_WITHOUT_CAP",
    show_default=True,
)
def create(
    account, page, name, campaign_id, daily_budget, countries, age_min, age_max,
    interest_ids, targeting_json, optimization_goal, billing_event, destination_type,
    status, bid_strategy,
):
    """Create a new ad set under a campaign."""
    spec = json.loads(targeting_json.read_text()) if targeting_json else None
    click.echo(f"→ Creating ad set under campaign {campaign_id}...")
    result = core.create_adset(
        name, campaign_id, daily_budget, targeting=spec,
        countries=countries, age_min=age_min, age_max=age_max, interest_ids=interest_ids,
        optimization_goal=optimization_goal, billing_event=billing_event,
        destination_type=destination_type, status=status, bid_strategy=bid_strategy,
        account=account, page=page,
    )
    click.echo(f"  ✓ adset id: {result['id']}")
    click.echo(f"    name={name}  goal={optimization_goal.upper()}  status={status.upper()}")
    click.echo(f"    daily_budget={daily_budget} (minor units)")
    click.echo(f"    targeting: {json.dumps(result['targeting'], indent=2)}")


@adset.command("list")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--campaign-id", default=None, help="Filter to one campaign.")
@click.option("--limit", type=int, default=25, show_default=True)
def list_adsets(account, campaign_id, limit):
    """List ad sets in the account (or under one campaign)."""
    rows = core.list_adsets(account, campaign_id, limit)
    if not rows:
        click.echo("(no ad sets)")
        return
    for a in rows:
        click.echo(
            f"{a['id']}  {a.get('effective_status','?'):<14}  "
            f"{a.get('optimization_goal','?'):<18}  budget={a.get('daily_budget','-'):<8}  "
            f"{a.get('name','')}"
        )
