import click

from .. import core


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
    """Smoke test credentials: token validity, scopes, Page to IG link, ad account access."""
    r = core.verify_credentials(account=account, page=page)

    click.echo(f"→ Token: valid={r['token_valid']}  expires_at={r['expires_at']} (0 = never)")
    click.echo(f"  scopes ({len(r['scopes'])}): {', '.join(r['scopes']) if r['scopes'] else '(none)'}")
    if r["missing_scopes"]:
        click.echo(f"  ! missing scopes: {', '.join(r['missing_scopes'])}")
    if not r["token_valid"]:
        raise SystemExit("Token is not valid. Regenerate it (see docs/setup-token.md).")

    pg = r["page"]
    click.echo(f"\n→ Page {pg['id']}: {pg['name']}")
    if pg["instagram_linked"]:
        click.echo(f"  ✓ IG linked: id={pg['instagram_id']}")
    else:
        click.echo("  ✗ Page is NOT linked to an IG business account.")
        click.echo("    Fix: Page Settings, Linked accounts, Instagram, Connect (docs/setup-token.md).")

    acct = r["ad_account"]
    click.echo(f"\n→ Ad account {acct['id']}: {acct['name']}")
    click.echo(
        f"  status={acct['status']}  currency={acct['currency']}  tz={acct['timezone']}"
    )

    click.echo(f"\n{'All checks passed.' if r['healthy'] else 'Some checks need attention (see above).'}")
