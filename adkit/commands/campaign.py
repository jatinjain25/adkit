import json

import click

from .. import config, graph


OBJECTIVES = [
    "OUTCOME_LEADS",
    "OUTCOME_TRAFFIC",
    "OUTCOME_ENGAGEMENT",
    "OUTCOME_AWARENESS",
    "OUTCOME_SALES",
    "OUTCOME_APP_PROMOTION",
]


@click.group()
def campaign():
    """Create and list ad campaigns."""


@campaign.command("create")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--name", required=True, help="Campaign name (shown in Ads Manager).")
@click.option(
    "--objective",
    type=click.Choice(OBJECTIVES, case_sensitive=False),
    default="OUTCOME_LEADS",
    show_default=True,
    help="Campaign objective. Use OUTCOME_LEADS for Instant Form lead gen.",
)
@click.option(
    "--status",
    type=click.Choice(["PAUSED", "ACTIVE"], case_sensitive=False),
    default="PAUSED",
    show_default=True,
    help="Effective status on creation. Default PAUSED so nothing spends until you flip it on.",
)
@click.option(
    "--daily-budget",
    type=int,
    default=None,
    help="Optional campaign-level daily budget (CBO) in account currency MINOR units (cents). "
    "Omit to set budget at the ad set level instead.",
)
@click.option(
    "--special-ad-category",
    type=click.Choice(
        ["NONE", "EMPLOYMENT", "HOUSING", "CREDIT", "ISSUES_ELECTIONS_POLITICS"],
        case_sensitive=False,
    ),
    default="NONE",
    show_default=True,
    help="Required by Meta. NONE for almost all commercial ads.",
)
def create(account, name, objective, status, daily_budget, special_ad_category):
    """Create a new campaign in the configured ad account."""
    ad_account_id = config.ad_account(account)

    data = {
        "name": name,
        "objective": objective.upper(),
        "status": status.upper(),
        "special_ad_categories": json.dumps(
            [] if special_ad_category.upper() == "NONE" else [special_ad_category.upper()]
        ),
    }
    if daily_budget is not None:
        data["daily_budget"] = daily_budget
    else:
        # Required by Meta when there's no campaign-level budget. False = each
        # ad set keeps its own budget (the normal case); True enables 20%
        # cross-ad-set budget sharing (Advantage Campaign Budget).
        data["is_adset_budget_sharing_enabled"] = "false"

    click.echo(f"→ Creating campaign in {ad_account_id}...")
    resp = graph.post(f"{ad_account_id}/campaigns", data=data)
    cid = resp.get("id")
    click.echo(f"  ✓ campaign id: {cid}")
    click.echo(f"    name={name}  objective={objective.upper()}  status={status.upper()}")
    if daily_budget is not None:
        click.echo(f"    daily_budget={daily_budget} (minor units, e.g. cents)")


@campaign.command("list")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--limit", type=int, default=25, show_default=True)
def list_campaigns(account, limit):
    """List campaigns in the configured ad account."""
    ad_account_id = config.ad_account(account)
    resp = graph.get(
        f"{ad_account_id}/campaigns",
        {
            "fields": "id,name,objective,status,effective_status,daily_budget,lifetime_budget,created_time",
            "limit": limit,
        },
    )
    rows = resp.get("data", [])
    if not rows:
        click.echo("(no campaigns)")
        return
    for c in rows:
        click.echo(
            f"{c['id']}  {c.get('effective_status','?'):<14}  "
            f"{c.get('objective','?'):<22}  {c.get('name','')}"
        )
