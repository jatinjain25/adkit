import json
from pathlib import Path

import click

from .. import config, graph


LEAD_CTAS = ["SIGN_UP", "LEARN_MORE", "GET_QUOTE", "SUBSCRIBE", "APPLY_NOW", "BOOK_TRAVEL"]


def _upload_image(ad_account_id: str, image_path: Path) -> str:
    """Upload an image to the ad account and return its image_hash."""
    click.echo(f"→ Uploading image {image_path.name}...")
    with image_path.open("rb") as fh:
        resp = graph.post(
            f"{ad_account_id}/adimages",
            files={"filename": (image_path.name, fh)},
        )
    images = resp.get("images", {})
    if not images:
        raise SystemExit(f"Upload returned no image hash: {json.dumps(resp)}")
    first = next(iter(images.values()))
    image_hash = first.get("hash")
    click.echo(f"  ✓ image_hash: {image_hash}")
    return image_hash


def _upload_video(ad_account_id: str, video_path: Path) -> str:
    """Upload a video to the ad account and return its video_id.

    Single-shot upload, fine for files up to ~25 MB. Larger files would need
    Meta's chunked upload protocol (start/transfer/finish), not implemented here.
    """
    size_mb = video_path.stat().st_size / (1024 * 1024)
    click.echo(f"→ Uploading video {video_path.name} ({size_mb:.1f} MB)...")
    with video_path.open("rb") as fh:
        resp = graph.post(
            f"{ad_account_id}/advideos",
            files={"source": (video_path.name, fh, "video/mp4")},
            timeout=300,
        )
    video_id = resp.get("id")
    if not video_id:
        raise SystemExit(f"Video upload returned no id: {json.dumps(resp)}")
    click.echo(f"  ✓ video_id: {video_id}")
    return video_id


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
    required=True,
    help="Instant Form id (from `leadform create`). Wires the CTA to open the form.",
)
@click.option(
    "--image",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ad image. Either --image, --image-hash, --video, or --video-id is required.",
)
@click.option(
    "--image-hash",
    default=None,
    help="Reuse a previously uploaded image hash instead of --image.",
)
@click.option(
    "--video",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ad video (.mp4). Triggers a video creative instead of an image one.",
)
@click.option(
    "--video-id",
    default=None,
    help="Reuse a previously uploaded video id instead of --video.",
)
@click.option(
    "--thumbnail",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Static thumbnail for the video creative (required for video). Uploaded as an adimage.",
)
@click.option(
    "--thumbnail-hash",
    default=None,
    help="Reuse a previously uploaded thumbnail image hash instead of --thumbnail.",
)
@click.option("--message", required=True, help="Primary text (the body above the image/video).")
@click.option("--headline", required=True, help="Headline (bold text under the creative).")
@click.option("--description", default=None, help="Optional link description / sub-headline.")
@click.option(
    "--link",
    default=None,
    help="Destination link. For Instant Form ads this is a fallback; defaults to the advertiser site.",
)
@click.option(
    "--cta",
    type=click.Choice(LEAD_CTAS, case_sensitive=False),
    default="SIGN_UP",
    show_default=True,
    help="Call-to-action button text.",
)
def create(
    account, page, ig_actor, name, lead_form_id,
    image, image_hash, video, video_id, thumbnail, thumbnail_hash,
    message, headline, description, link, cta,
):
    """Create a lead-ad creative (image or video + copy + CTA opening the Instant Form)."""
    ad_account_id = config.ad_account(account)
    page_id = config.page(page)
    ig_actor_id = config.ig_actor(ig_actor)

    has_video = bool(video or video_id)
    has_image = bool(image or image_hash)
    if has_video and has_image:
        raise SystemExit("Pick a media type: pass --image OR --video, not both.")
    if not has_video and not has_image:
        raise SystemExit("Provide --image / --image-hash, or --video / --video-id.")

    fallback_link = link or config.optional("ADVERTISER_URL")
    if not fallback_link:
        raise SystemExit(
            "No destination link. Pass --link https://your-site.com "
            "or set ADVERTISER_URL in .env."
        )
    cta_spec = {
        "type": cta.upper(),
        "value": {"lead_gen_form_id": lead_form_id, "link": fallback_link},
    }

    if has_video:
        if video and not video_id:
            video_id = _upload_video(ad_account_id, video)
        if not thumbnail_hash:
            if not thumbnail:
                raise SystemExit(
                    "Video creatives require a static preview image. "
                    "Pass --thumbnail <path.jpg|.png> or --thumbnail-hash <hash>."
                )
            thumbnail_hash = _upload_image(ad_account_id, thumbnail)
        video_data = {
            "video_id": video_id,
            "image_hash": thumbnail_hash,
            "message": message,
            "title": headline,
            "call_to_action": cta_spec,
        }
        if description:
            video_data["link_description"] = description
        object_story_spec = {"page_id": page_id, "video_data": video_data}
    else:
        if image and not image_hash:
            image_hash = _upload_image(ad_account_id, image)
        link_data = {
            "message": message,
            "name": headline,
            "image_hash": image_hash,
            "link": fallback_link,
            "call_to_action": {
                "type": cta.upper(),
                "value": {"lead_gen_form_id": lead_form_id},
            },
        }
        if description:
            link_data["description"] = description
        object_story_spec = {"page_id": page_id, "link_data": link_data}

    if ig_actor_id:
        object_story_spec["instagram_actor_id"] = ig_actor_id

    data = {
        "name": name,
        "object_story_spec": json.dumps(object_story_spec),
    }

    click.echo(f"→ Creating creative in {ad_account_id}...")
    resp = graph.post(f"{ad_account_id}/adcreatives", data=data)
    cid = resp.get("id")
    media_kind = "video" if has_video else "image"
    click.echo(f"  ✓ creative id: {cid}")
    click.echo(f"    kind={media_kind}  headline={headline!r}  cta={cta.upper()}  lead_form={lead_form_id}")
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
    ad_account_id = config.ad_account(account)
    resp = graph.get(
        f"{ad_account_id}/adcreatives",
        {"fields": "id,name,status,object_type", "limit": limit},
    )
    rows = resp.get("data", [])
    if not rows:
        click.echo("(no creatives)")
        return
    for c in rows:
        click.echo(
            f"{c['id']}  {c.get('status','?'):<10}  "
            f"{c.get('object_type','?'):<14}  {c.get('name','')}"
        )
