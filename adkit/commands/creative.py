from pathlib import Path

import click

from .. import core

LEAD_CTAS = ["SIGN_UP", "LEARN_MORE", "GET_QUOTE", "SUBSCRIBE", "APPLY_NOW", "BOOK_TRAVEL"]


@click.group()
def creative():
    """Create and list ad creatives."""


@creative.command("create")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option(
    "--page",
    default=None,
    help="Page id behind the creative. Defaults to META_PAGE_ID in .env.",
)
@click.option(
    "--ig-actor",
    default=None,
    help="Instagram actor id. Defaults to META_INSTAGRAM_ACTOR_ID in .env.",
)
@click.option("--name", required=True, help="Creative name shown in Ads Manager.")
@click.option(
    "--lead-form-id",
    default=None,
    help="Instant Form id (from `leadform create`) for lead-gen ads. "
    "Omit for a plain website/link creative.",
)
@click.option(
    "--image",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ad image. One of --image/--image-hash/--video/--video-id is required.",
)
@click.option("--image-hash", default=None, help="Reuse a previously uploaded image hash.")
@click.option(
    "--video",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ad video (.mp4). Triggers a video creative.",
)
@click.option("--video-id", default=None, help="Reuse a previously uploaded video id.")
@click.option(
    "--thumbnail",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Static thumbnail for the video creative (required for video).",
)
@click.option("--thumbnail-hash", default=None, help="Reuse a previously uploaded thumbnail hash.")
@click.option("--message", required=True, help="Primary text (the body above the image/video).")
@click.option("--headline", required=True, help="Headline (bold text under the creative).")
@click.option("--description", default=None, help="Optional link description / sub-headline.")
@click.option(
    "--link",
    default=None,
    help="Destination link. Falls back to ADVERTISER_URL in .env for website creatives.",
)
@click.option(
    "--cta",
    type=click.Choice(LEAD_CTAS, case_sensitive=False),
    default="LEARN_MORE",
    show_default=True,
    help="Call-to-action button text.",
)
def create(
    account, page, ig_actor, name, lead_form_id, image, image_hash, video, video_id,
    thumbnail, thumbnail_hash, message, headline, description, link, cta,
):
    """Create an ad creative (image or video), website or lead-gen."""
    click.echo("→ Creating creative...")
    try:
        result = core.create_creative(
            name, message, headline,
            image=image, image_hash=image_hash, video=video, video_id=video_id,
            thumbnail=thumbnail, thumbnail_hash=thumbnail_hash, description=description,
            link=link, cta=cta, lead_form_id=lead_form_id,
            page=page, ig_actor=ig_actor, account=account,
        )
    except ValueError as e:
        raise SystemExit(str(e))
    click.echo(f"  ✓ creative id: {result['id']}")
    click.echo(f"    kind={result['kind']}  headline={headline!r}  cta={cta.upper()}")
    click.echo("    Use this id as --creative-id when creating the ad.")


@creative.command("list")
@click.option(
    "--account",
    default=None,
    help="Ad account id (act_<id> or bare <id>). Defaults to META_AD_ACCOUNT_ID in .env.",
)
@click.option("--limit", type=int, default=25, show_default=True)
def list_creatives(account, limit):
    """List ad creatives in the account."""
    rows = core.list_creatives(account, limit)
    if not rows:
        click.echo("(no creatives)")
        return
    for c in rows:
        click.echo(
            f"{c['id']}  {c.get('status','?'):<10}  "
            f"{c.get('object_type','?'):<14}  {c.get('name','')}"
        )
