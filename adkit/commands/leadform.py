import json

import click

from .. import config, graph


def _page_token(page_id: str) -> str:
    """Lead forms are owned by the Page, so the write must use a Page access token."""
    resp = graph.get(page_id, {"fields": "access_token"})
    token = resp.get("access_token")
    if not token:
        raise SystemExit(
            f"Could not get a Page access token for {page_id}. "
            "Your user token needs pages_manage_ads/leads_retrieval and a role on the Page."
        )
    return token


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
@click.option(
    "--locale",
    default="en_US",
    show_default=True,
    help="Form locale, e.g. en_US.",
)
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
@click.option(
    "--thank-you-title",
    default="Thanks! We'll be in touch shortly.",
    show_default=True,
)
@click.option(
    "--thank-you-url",
    default=None,
    help="Optional URL for the 'View website' button on the thank-you screen.",
)
def create(
    page,
    name,
    privacy_url,
    privacy_link_text,
    locale,
    headline,
    description,
    thank_you_title,
    thank_you_url,
):
    """Create an Instant Form capturing FULL_NAME + PHONE (auto-prefilled → high CVR)."""
    page_id = config.page(page)
    page_token = _page_token(page_id)

    questions = [{"type": "FULL_NAME"}, {"type": "PHONE"}]

    thank_you_page = {
        "title": thank_you_title,
        "body": "We received your details.",
        "button_type": "VIEW_WEBSITE",
        "button_text": "Visit our site",
        "website_url": thank_you_url or privacy_url,
    }

    data = {
        "name": name,
        "locale": locale,
        "questions": json.dumps(questions),
        "privacy_policy": json.dumps({"url": privacy_url, "link_text": privacy_link_text}),
        "context_card": json.dumps(
            {
                "title": headline,
                "content": [description],
                "style": "PARAGRAPH_STYLE",
            }
        ),
        "thank_you_page": json.dumps(thank_you_page),
        "follow_up_action_url": thank_you_url or privacy_url,
        # Higher-intent leads; trades volume for quality. Good for warm-call funnels.
        "is_optimized_for_quality": "true",
        "access_token": page_token,
    }

    click.echo(f"→ Creating lead form on Page {page_id}...")
    resp = graph.post(f"{page_id}/leadgen_forms", data=data)
    fid = resp.get("id")
    click.echo(f"  ✓ lead form id: {fid}")
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
    page_id = config.page(page)
    page_token = _page_token(page_id)
    resp = graph.get(
        f"{page_id}/leadgen_forms",
        {"fields": "id,name,status,locale,leads_count", "limit": limit},
        access_token=page_token,
    )
    rows = resp.get("data", [])
    if not rows:
        click.echo("(no lead forms)")
        return
    for f in rows:
        click.echo(
            f"{f['id']}  {f.get('status','?'):<10}  "
            f"leads={f.get('leads_count','-'):<6}  {f.get('name','')}"
        )
