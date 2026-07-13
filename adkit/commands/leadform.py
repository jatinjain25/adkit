import click

from .. import core


@click.group()
def leadform():
    """Create and list Instant Forms (lead gen forms) on the Page."""


@leadform.command("create")
@click.option(
    "--page",
    default=None,
    help="Page that owns the form. Defaults to META_PAGE_ID in .env.",
)
@click.option("--name", required=True, help="Form name shown in Ads Manager (not seen by leads).")
@click.option(
    "--privacy-url",
    required=True,
    help="URL of your privacy policy. Meta REQUIRES this for lead forms.",
)
@click.option(
    "--privacy-link-text",
    default="Privacy Policy",
    show_default=True,
    help="Visible link text for the privacy policy.",
)
@click.option("--locale", default="en_US", show_default=True, help="Form locale, e.g. en_US.")
@click.option(
    "--headline",
    default="Get in touch",
    show_default=True,
    help="Intro/headline shown at the top of the form.",
)
@click.option(
    "--description",
    default="Leave your name and phone and we'll call you back.",
    show_default=True,
    help="Intro body text.",
)
@click.option("--thank-you-title", default="Thanks! We'll be in touch shortly.", show_default=True)
@click.option(
    "--thank-you-url",
    default=None,
    help="Optional URL for the 'View website' button on the thank-you screen.",
)
def create(
    page, name, privacy_url, privacy_link_text, locale, headline, description,
    thank_you_title, thank_you_url,
):
    """Create an Instant Form capturing FULL_NAME + PHONE (auto-prefilled, high CVR)."""
    click.echo("→ Creating lead form...")
    result = core.create_lead_form(
        name, privacy_url, privacy_link_text=privacy_link_text, locale=locale,
        headline=headline, description=description, thank_you_title=thank_you_title,
        thank_you_url=thank_you_url, page=page,
    )
    click.echo(f"  ✓ lead form id: {result['id']}")
    click.echo(f"    name={name}  fields=FULL_NAME,PHONE  locale={locale}")
    click.echo("    Use this id as --lead-form-id when creating the creative.")


@leadform.command("list")
@click.option(
    "--page",
    default=None,
    help="Page to list forms for. Defaults to META_PAGE_ID in .env.",
)
@click.option("--limit", type=int, default=25, show_default=True)
def list_forms(page, limit):
    """List lead forms on the configured Page."""
    rows = core.list_lead_forms(page, limit)
    if not rows:
        click.echo("(no lead forms)")
        return
    for f in rows:
        click.echo(
            f"{f['id']}  {f.get('status','?'):<10}  "
            f"leads={f.get('leads_count','-'):<6}  {f.get('name','')}"
        )
