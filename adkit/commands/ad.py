import json

import click

from .. import config, graph


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
    ad_account_id = config.ad_account(account)

    data = {
        "name": name,
        "adset_id": adset_id,
        "creative": json.dumps({"creative_id": creative_id}),
        "status": status.upper(),
    }

    click.echo(f"→ Creating ad under ad set {adset_id}...")
    resp = graph.post(f"{ad_account_id}/ads", data=data)
    aid = resp.get("id")
    click.echo(f"  ✓ ad id: {aid}")
    click.echo(f"    name={name}  status={status.upper()}  creative={creative_id}")
    if status.upper() == "PAUSED":
        click.echo("    Review it in Ads Manager, then: adkit ad activate --ad-id " + str(aid))


@ad.command("activate")
@click.option("--ad-id", required=True, help="Ad id to flip ACTIVE (starts spending).")
def activate(ad_id):
    """Set an ad's status to ACTIVE."""
    graph.post(ad_id, data={"status": "ACTIVE"})
    click.echo(f"  ✓ ad {ad_id} is now ACTIVE")


@ad.command("pause")
@click.option("--ad-id", required=True, help="Ad id to pause.")
def pause(ad_id):
    """Set an ad's status to PAUSED."""
    graph.post(ad_id, data={"status": "PAUSED"})
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
    ad_account_id = config.ad_account(account)
    path = f"{adset_id}/ads" if adset_id else f"{ad_account_id}/ads"
    resp = graph.get(
        path,
        {
            "fields": "id,name,status,effective_status,adset_id,creative",
            "limit": limit,
        },
    )
    rows = resp.get("data", [])
    if not rows:
        click.echo("(no ads)")
        return
    for a in rows:
        click.echo(
            f"{a['id']}  {a.get('effective_status','?'):<14}  {a.get('name','')}"
        )
