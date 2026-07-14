import click

from .. import config, core

DOCS = "docs/setup-token.md"


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
    # Friendly first-run wall: a missing token is the most common state, so guide
    # instead of throwing a raw error deep in the Graph layer.
    if not config.optional("META_ACCESS_TOKEN"):
        loaded = config.find_env_file()
        click.echo("adkit can't find your Meta credentials yet. Here's what you need:\n")
        click.echo("  1. A Meta access token with ads + pages scopes")
        click.echo("  2. Your ad account id, Page id, and linked Instagram account")
        click.echo(f"\nPut them in a .env file. {'adkit loaded ' + str(loaded) if loaded else 'No .env found.'}")
        click.echo("adkit looks in the current directory (and parents), then ~/.config/adkit/.env.")
        click.echo(f"Copy .env.example there and fill it in. Full walkthrough: {DOCS}")
        click.echo("\nNo account yet? Run `adkit demo` to see the whole flow with no credentials.")
        raise SystemExit(1)

    r = core.verify_credentials(account=account, page=page)

    click.echo(f"→ Config loaded from: {r['env_file'] or '(no .env found; using process env)'}")
    click.echo(f"→ Token: valid={r['token_valid']}  expires_at={r['expires_at']} (0 = never)")
    click.echo(f"  scopes ({len(r['scopes'])}): {', '.join(r['scopes']) if r['scopes'] else '(none)'}")
    if r["missing_scopes"]:
        click.echo(f"  ! missing scopes: {', '.join(r['missing_scopes'])}")
        click.echo(f"    Fix: regenerate the token with these scopes ({DOCS}#2-get-a-token-with-the-right-scopes).")
    if r.get("missing_recommended_scopes"):
        click.echo(f"  ~ optional scopes (for `adkit optimize` lead quality): "
                   f"{', '.join(r['missing_recommended_scopes'])}")
    if not r["token_valid"]:
        raise SystemExit(f"Token is not valid. Regenerate it ({DOCS}#2-get-a-token-with-the-right-scopes).")

    pg = r["page"]
    click.echo(f"\n→ Page {pg['id']}: {pg['name']}")
    if pg["instagram_linked"]:
        click.echo(f"  ✓ IG linked: id={pg['instagram_id']}")
    else:
        click.echo("  ✗ Page is NOT linked to an IG business account.")
        click.echo(f"    Fix: Page Settings, Linked accounts, Instagram, Connect ({DOCS}#3-link-instagram-the-step-people-miss).")

    acct = r["ad_account"]
    click.echo(f"\n→ Ad account {acct['id']}: {acct['name']}")
    click.echo(
        f"  status={acct['status']}  currency={acct['currency']}  tz={acct['timezone']}"
    )
    if not acct["active"]:
        click.echo("  ✗ Ad account is not active (status != 1). It cannot deliver ads until resolved.")

    click.echo(f"\n{'All checks passed.' if r['healthy'] else 'Some checks need attention (see above).'}")
