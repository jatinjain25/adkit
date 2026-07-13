"""End-to-end automation: build an entire ad chain from a single brief file.

`adkit automate launch --brief campaign.yaml` reads a declarative brief and,
in order:

  1. (optional) generates each ad's creative with AI (Gemini / Veo),
  2. creates the campaign,
  3. (optional) creates an Instant Form for lead-gen objectives,
  4. creates each ad set with its targeting,
  5. creates each creative and the ad that places it.

Safety by design:
  * Dry run is the default. Nothing is written to Meta until you pass --go.
  * Every object is created PAUSED, so no spend starts until you flip it on in
    Ads Manager (or with `adkit ad activate`).
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .. import config, creative_gen, graph
from .creative import _upload_image, _upload_video


def _load_brief(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError:
            raise SystemExit(
                "This brief is YAML but PyYAML is not installed. "
                "Run `pip install pyyaml`, or use a .json brief."
            )
        return yaml.safe_load(text) or {}
    return json.loads(text)


def _build_targeting(adset: dict) -> dict:
    override = adset.get("targeting_json")
    if override:
        return json.loads(Path(override).read_text())
    spec = {
        "geo_locations": {"countries": [c.upper() for c in adset.get("countries", ["US"])]},
        "age_min": adset.get("age_min", 25),
        "age_max": adset.get("age_max", 55),
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed"],
        "instagram_positions": ["stream"],
    }
    ids = [str(i) for i in adset.get("interest_ids", []) if str(i).strip()]
    if ids:
        spec["flexible_spec"] = [{"interests": [{"id": i} for i in ids]}]
    return spec


def _resolve_creative_asset(ad: dict, creatives_dir: Path, *, go: bool) -> None:
    """If the ad declares a `generate` block, produce the asset and set ad['image']
    or ad['video'] to the generated path. Runs even in dry mode is avoided: we only
    spend on generation when --go is set, to keep dry runs free."""
    gen = ad.get("generate")
    if not gen:
        return
    kind = gen.get("type", "image")
    name = ad.get("name", "creative").lower().replace(" ", "_")
    if not go:
        click.echo(f"    [dry] would generate {kind} for ad '{ad.get('name')}' "
                   f"(prompt: {gen.get('prompt','')[:60]}...)")
        return
    if kind == "image":
        out = creatives_dir / f"{name}.png"
        creative_gen.generate_image(
            gen["prompt"], out, aspect=gen.get("aspect", "1:1"), size=gen.get("size", "2K")
        )
        ad["image"] = str(out)
        click.echo(f"    ✓ generated image: {out}")
    elif kind == "video":
        out = creatives_dir / f"{name}.mp4"
        creative_gen.generate_video(
            gen["prompt"], out,
            image=Path(gen["seed_image"]) if gen.get("seed_image") else None,
            duration=int(gen.get("duration", 8)),
            aspect=gen.get("aspect", "9:16"),
            fast=gen.get("fast", True),
        )
        ad["video"] = str(out)
        click.echo(f"    ✓ generated video: {out}")
    else:
        raise SystemExit(f"Unknown generate.type: {kind!r} (use image or video).")


def _make_creative(
    ad_account_id: str, page_id: str, ig_actor_id: str | None,
    ad: dict, lead_form_id: str | None,
) -> str:
    """Create an ad creative. Supports both lead-gen (Instant Form) and plain
    website/link creatives, image or video."""
    message = ad["message"]
    headline = ad["headline"]
    description = ad.get("description")
    link = ad.get("link") or config.optional("ADVERTISER_URL")
    cta_type = (ad.get("cta") or "LEARN_MORE").upper()

    if not link and not lead_form_id:
        raise SystemExit(
            f"Ad '{ad.get('name')}' needs a `link` (or set ADVERTISER_URL), "
            "or a lead form for a lead-gen objective."
        )

    has_video = bool(ad.get("video") or ad.get("video_id"))
    if has_video:
        video_id = ad.get("video_id") or _upload_video(ad_account_id, Path(ad["video"]))
        thumb_hash = ad.get("thumbnail_hash")
        if not thumb_hash and ad.get("thumbnail"):
            thumb_hash = _upload_image(ad_account_id, Path(ad["thumbnail"]))
        if not thumb_hash:
            raise SystemExit(
                f"Video ad '{ad.get('name')}' needs a thumbnail. "
                "Add `thumbnail: path.png` (or thumbnail_hash)."
            )
        cta_value = {"lead_gen_form_id": lead_form_id, "link": link} if lead_form_id else {"link": link}
        video_data = {
            "video_id": video_id,
            "image_hash": thumb_hash,
            "message": message,
            "title": headline,
            "call_to_action": {"type": cta_type, "value": cta_value},
        }
        if description:
            video_data["link_description"] = description
        object_story_spec = {"page_id": page_id, "video_data": video_data}
    else:
        image_hash = ad.get("image_hash") or _upload_image(ad_account_id, Path(ad["image"]))
        cta_value = {"lead_gen_form_id": lead_form_id} if lead_form_id else {"link": link}
        link_data = {
            "message": message,
            "name": headline,
            "image_hash": image_hash,
            "link": link or "https://facebook.com",
            "call_to_action": {"type": cta_type, "value": cta_value},
        }
        if description:
            link_data["description"] = description
        object_story_spec = {"page_id": page_id, "link_data": link_data}

    if ig_actor_id:
        object_story_spec["instagram_actor_id"] = ig_actor_id

    resp = graph.post(
        f"{ad_account_id}/adcreatives",
        data={"name": ad.get("name", headline), "object_story_spec": json.dumps(object_story_spec)},
    )
    return resp["id"]


@click.group()
def automate():
    """Run a whole campaign from one brief file."""


@automate.command("launch")
@click.option(
    "--brief",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Path to a campaign brief (.yaml or .json). See examples/briefs/.",
)
@click.option(
    "--go",
    is_flag=True,
    default=False,
    help="Actually create objects and run any AI generation. Without this, "
    "adkit prints the plan and writes nothing (dry run).",
)
def launch(brief, go):
    """Read a brief and build the full campaign (dry run unless --go)."""
    spec = _load_brief(brief)
    ad_account_id = config.ad_account(spec.get("account"))
    page_id = config.page(spec.get("page"))
    ig_actor_id = config.ig_actor(spec.get("ig_actor"))
    creatives_dir = Path(spec.get("creatives_dir") or "creatives")

    camp = spec["campaign"]
    objective = camp.get("objective", "OUTCOME_TRAFFIC").upper()
    is_leadgen = objective == "OUTCOME_LEADS"

    mode = "LIVE" if go else "DRY RUN"
    click.echo(f"=== adkit automate launch [{mode}] ===")
    click.echo(f"account={ad_account_id}  page={page_id}  objective={objective}")
    click.echo(f"campaign: {camp['name']}")
    for aset in spec.get("adsets", []):
        click.echo(f"  adset: {aset['name']}  budget={aset.get('daily_budget')} (minor units)")
        for ad in aset.get("ads", []):
            media = "video" if (ad.get("video") or ad.get("generate", {}).get("type") == "video") else "image"
            click.echo(f"    ad: {ad.get('name')}  [{media}]  cta={ad.get('cta','LEARN_MORE')}")

    if not go:
        click.echo(
            "\nDry run complete. Nothing was created and no creative was generated.\n"
            "Re-run with --go to build it (all objects start PAUSED)."
        )
        return

    # 1. generate any AI creatives up front
    click.echo("\n→ Generating creatives...")
    for aset in spec.get("adsets", []):
        for ad in aset.get("ads", []):
            _resolve_creative_asset(ad, creatives_dir, go=go)

    # 2. campaign
    camp_data = {
        "name": camp["name"],
        "objective": objective,
        "status": "PAUSED",
        "special_ad_categories": json.dumps(camp.get("special_ad_categories", [])),
    }
    if camp.get("daily_budget"):
        camp_data["daily_budget"] = camp["daily_budget"]
    else:
        camp_data["is_adset_budget_sharing_enabled"] = "false"
    click.echo("→ Creating campaign...")
    campaign_id = graph.post(f"{ad_account_id}/campaigns", data=camp_data)["id"]
    click.echo(f"  ✓ campaign {campaign_id}")

    # 3. optional lead form
    lead_form_id = None
    if is_leadgen and spec.get("lead_form"):
        lf = spec["lead_form"]
        page_token = graph.get(page_id, {"fields": "access_token"}).get("access_token")
        form_data = {
            "name": lf["name"],
            "locale": lf.get("locale", "en_US"),
            "questions": json.dumps([{"type": "FULL_NAME"}, {"type": "PHONE"}]),
            "privacy_policy": json.dumps(
                {"url": lf["privacy_url"], "link_text": lf.get("privacy_link_text", "Privacy Policy")}
            ),
            "context_card": json.dumps(
                {"title": lf.get("headline", "Get in touch"),
                 "content": [lf.get("description", "")], "style": "PARAGRAPH_STYLE"}
            ),
            "thank_you_page": json.dumps(
                {"title": lf.get("thank_you_title", "Thanks!"), "body": "We received your details.",
                 "button_type": "VIEW_WEBSITE", "button_text": "Visit our site",
                 "website_url": lf.get("thank_you_url") or lf["privacy_url"]}
            ),
            "access_token": page_token,
        }
        lead_form_id = graph.post(f"{page_id}/leadgen_forms", data=form_data)["id"]
        click.echo(f"  ✓ lead form {lead_form_id}")

    # 4 + 5. ad sets, creatives, ads
    summary = []
    for aset in spec.get("adsets", []):
        adset_data = {
            "name": aset["name"],
            "campaign_id": campaign_id,
            "daily_budget": aset["daily_budget"],
            "billing_event": aset.get("billing_event", "IMPRESSIONS").upper(),
            "optimization_goal": aset.get(
                "optimization_goal", "LEAD_GENERATION" if is_leadgen else "LINK_CLICKS"
            ).upper(),
            "bid_strategy": aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP").upper(),
            "destination_type": aset.get("destination_type", "ON_AD" if is_leadgen else "WEBSITE").upper(),
            "status": "PAUSED",
            "targeting": json.dumps(_build_targeting(aset)),
            "promoted_object": json.dumps({"page_id": page_id}),
        }
        click.echo(f"→ Creating ad set '{aset['name']}'...")
        adset_id = graph.post(f"{ad_account_id}/adsets", data=adset_data)["id"]
        click.echo(f"  ✓ adset {adset_id}")
        for ad in aset.get("ads", []):
            creative_id = _make_creative(ad_account_id, page_id, ig_actor_id, ad, lead_form_id)
            ad_id = graph.post(
                f"{ad_account_id}/ads",
                data={
                    "name": ad.get("name", "ad"),
                    "adset_id": adset_id,
                    "creative": json.dumps({"creative_id": creative_id}),
                    "status": "PAUSED",
                },
            )["id"]
            click.echo(f"    ✓ ad {ad_id}  (creative {creative_id})")
            summary.append(ad_id)

    click.echo(
        f"\n✓ Built campaign {campaign_id}: {len(spec.get('adsets', []))} ad sets, "
        f"{len(summary)} ads. Everything is PAUSED.\n"
        f"Review in Ads Manager, then flip on with: adkit ad activate --ad-id <id>"
    )
