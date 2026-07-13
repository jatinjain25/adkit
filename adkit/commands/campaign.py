import click

from .. import core


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
    type=click.Choice(core.OBJECTIVES, case_sensitive=False),
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
    click.echo("→ Creating campaign...")
    result = core.create_campaign(
        name, objective=objective, status=status, daily_budget=daily_budget,
        special_ad_category=special_ad_category, account=account,
    )
    click.echo(f"  ✓ campaign id: {result['id']}")
    click.echo(f"    name={name}  objective={result['objective']}  status={result['status']}")
    if daily_budget is not None:
        click.echo(f"    daily_budget={daily_budget} (minor units, e.g. cents)")


@campaign.command("activate")
@click.option("--campaign-id", required=True, help="Campaign id to set ACTIVE.")
def activate(campaign_id):
    """Set a campaign ACTIVE. Ads still need their ad set and ad ACTIVE to deliver."""
    core.set_campaign_status(campaign_id, "ACTIVE")
    click.echo(f"  ✓ campaign {campaign_id} is now ACTIVE")


@campaign.command("pause")
@click.option("--campaign-id", required=True, help="Campaign id to pause (stops all delivery under it).")
def pause(campaign_id):
    """Pause a campaign. This stops delivery for every ad set and ad under it."""
    core.set_campaign_status(campaign_id, "PAUSED")
    click.echo(f"  ✓ campaign {campaign_id} is now PAUSED")


@campaign.command("list")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--limit", type=int, default=25, show_default=True)
def list_campaigns(account, limit):
    """List campaigns in the configured ad account."""
    rows = core.list_campaigns(account, limit)
    if not rows:
        click.echo("(no campaigns)")
        return
    for c in rows:
        click.echo(
            f"{c['id']}  {c.get('effective_status','?'):<14}  "
            f"{c.get('objective','?'):<22}  {c.get('name','')}"
        )
