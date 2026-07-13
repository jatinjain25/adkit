import click

from .. import config, graph


@click.command()
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>) to probe. Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option(
    "--page",
    default=None,
    help="Page id to probe for the IG link. Defaults to META_PAGE_ID in .env.",
)
def verify(account, page):
    """Smoke test credentials: token validity, scopes, Page↔IG link, ad account access."""
    token = config.require("META_ACCESS_TOKEN")

    click.echo("→ Validating token via debug_token...")
    dbg = graph.get("debug_token", {"input_token": token}).get("data", {})
    is_valid = dbg.get("is_valid")
    expires_at = dbg.get("expires_at")
    scopes = dbg.get("scopes", [])
    click.echo(f"  is_valid={is_valid}  expires_at={expires_at} (0 = never)")
    click.echo(f"  scopes ({len(scopes)}): {', '.join(scopes) if scopes else '(none)'}")
    _check_scopes(scopes)
    if not is_valid:
        raise SystemExit("Token is not valid. Regenerate it (see docs/setup-token.md).")

    page_id = config.page(page)
    click.echo(f"\n→ Probing Page {page_id} for instagram_business_account...")
    page = graph.get(page_id, {"fields": "name,instagram_business_account"})
    click.echo(f"  page name: {page.get('name')}")
    iba = page.get("instagram_business_account")
    if iba:
        click.echo(f"  ✓ IG linked: id={iba.get('id')}")
        configured = config.optional("META_INSTAGRAM_ACTOR_ID")
        if configured and configured != iba.get("id"):
            click.echo(
                f"  ! META_INSTAGRAM_ACTOR_ID in .env ({configured}) does not match "
                f"the Page's linked IG ({iba.get('id')})."
            )
    else:
        click.echo("  ✗ Page is NOT linked to an IG business account.")
        click.echo(
            "    Fix: Page Settings → Linked accounts → Instagram → Connect "
            "(see docs/setup-token.md, 'Link Instagram')."
        )

    ad_account_id = config.ad_account(account)
    click.echo(f"\n→ Probing ad account {ad_account_id}...")
    acct = graph.get(
        ad_account_id,
        {"fields": "name,account_status,currency,timezone_name,amount_spent,balance"},
    )
    click.echo(
        f"  name={acct.get('name')}  status={acct.get('account_status')} "
        f" currency={acct.get('currency')}  tz={acct.get('timezone_name')}"
    )

    click.echo("\nAll checks completed.")


REQUIRED_SCOPES = [
    "ads_management",
    "ads_read",
    "business_management",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_ads",
    "pages_manage_posts",
    "pages_manage_metadata",
    "instagram_basic",
    "instagram_content_publish",
]


def _check_scopes(scopes: list[str]) -> None:
    missing = [s for s in REQUIRED_SCOPES if s not in scopes]
    if missing:
        click.echo(f"  ! missing scopes: {', '.join(missing)}")
