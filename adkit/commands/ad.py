import click

from .. import core


@click.group()
def ad():
    """Create, list, and toggle ads."""


@ad.command("create")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--name", required=True, help="Ad name shown in Ads Manager.")
@click.option("--adset-id", required=True, help="Parent ad set id (from `adset create`).")
@click.option("--creative-id", required=True, help="Creative id (from `creative create`).")
@click.option(
    "--status",
    type=click.Choice(["PAUSED", "ACTIVE"], case_sensitive=False),
    default="PAUSED",
    show_default=True,
    help="Default PAUSED so you can review in Ads Manager before spending.",
)
def create(account, name, adset_id, creative_id, status):
    """Create an ad that places a creative into an ad set."""
    click.echo(f"→ Creating ad under ad set {adset_id}...")
    result = core.create_ad(name, adset_id, creative_id, status=status, account=account)
    click.echo(f"  ✓ ad id: {result['id']}")
    click.echo(f"    name={name}  status={result['status']}  creative={creative_id}")
    if result["status"] == "PAUSED":
        click.echo(f"    Review it in Ads Manager, then: adkit ad activate --ad-id {result['id']}")


@ad.command("activate")
@click.option("--ad-id", required=True, help="Ad id to make live (starts spending).")
@click.option(
    "--ad-only",
    is_flag=True,
    default=False,
    help="Flip only this ad ACTIVE and leave its ad set / campaign as-is. "
    "By default adkit activates the whole delivery chain so the ad actually runs.",
)
def activate(ad_id, ad_only):
    """Make an ad deliver.

    A Meta ad only serves when the ad, its ad set, AND its campaign are all
    ACTIVE. Since adkit builds everything PAUSED, this activates the whole chain
    by default so the ad genuinely goes live. Other ads in the ad set stay
    PAUSED.
    """
    if ad_only:
        core.set_ad_status(ad_id, "ACTIVE")
        click.echo(f"  ✓ ad {ad_id} is now ACTIVE (parents unchanged; it will only")
        click.echo("    deliver if its ad set and campaign are also ACTIVE)")
        return
    result = core.activate_delivery(ad_id)
    for step in result["activated"]:
        click.echo(f"  ✓ {step['level']} {step['id']} is now ACTIVE")
    click.echo("  → ad is live and can start spending. Pause with: adkit ad pause --ad-id " + ad_id)


@ad.command("pause")
@click.option("--ad-id", required=True, help="Ad id to pause.")
def pause(ad_id):
    """Set an ad's status to PAUSED."""
    core.set_ad_status(ad_id, "PAUSED")
    click.echo(f"  ✓ ad {ad_id} is now PAUSED")


@ad.command("list")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--adset-id", default=None, help="Filter to one ad set.")
@click.option("--limit", type=int, default=25, show_default=True)
def list_ads(account, adset_id, limit):
    """List ads in the account (or under one ad set)."""
    rows = core.list_ads(account, adset_id, limit)
    if not rows:
        click.echo("(no ads)")
        return
    for a in rows:
        click.echo(f"{a['id']}  {a.get('effective_status','?'):<14}  {a.get('name','')}")
