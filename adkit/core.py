"""adkit core library.

Every Meta Ads operation adkit performs lives here as a plain function that
takes arguments and returns data. No printing, no click, no argument parsing.

This is the import surface for adkit. The CLI (`adkit/commands/*`), the MCP
server (`adkit/mcp_server.py`), and the brief automation all call these
functions, so there is exactly one implementation of each operation.

    from adkit import core
    camp = core.create_campaign("My campaign", objective="OUTCOME_TRAFFIC")
    print(camp["id"])

All create functions default status to PAUSED, so nothing spends by accident.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Iterable

from . import config, graph

Emit = Callable[[str], None]


class LaunchError(Exception):
    """A brief launch failed partway. `created` holds the ids built before the
    failure so callers can report or clean them up. Nothing is ever left
    spending: every object adkit creates is PAUSED."""

    def __init__(self, message: str, *, created: dict):
        super().__init__(message)
        self.created = created


def _noop(_msg: str) -> None:
    pass


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def upload_image(image_path: str | Path, *, account: str | None = None) -> str:
    """Upload an image to the ad account and return its image hash."""
    ad_account_id = config.ad_account(account)
    image_path = Path(image_path)
    with image_path.open("rb") as fh:
        resp = graph.post(
            f"{ad_account_id}/adimages",
            files={"filename": (image_path.name, fh)},
        )
    images = resp.get("images", {})
    if not images:
        raise ValueError(f"Upload returned no image hash: {json.dumps(resp)}")
    return next(iter(images.values()))["hash"]


def upload_video(video_path: str | Path, *, account: str | None = None) -> str:
    """Upload a video (single-shot, fine up to ~25 MB) and return its video id."""
    ad_account_id = config.ad_account(account)
    video_path = Path(video_path)
    with video_path.open("rb") as fh:
        resp = graph.post(
            f"{ad_account_id}/advideos",
            files={"source": (video_path.name, fh, "video/mp4")},
            timeout=300,
        )
    video_id = resp.get("id")
    if not video_id:
        raise ValueError(f"Video upload returned no id: {json.dumps(resp)}")
    return video_id


# --------------------------------------------------------------------------- #
# Verify
# --------------------------------------------------------------------------- #
REQUIRED_SCOPES = [
    "ads_management", "ads_read", "business_management",
    "pages_show_list", "pages_read_engagement", "pages_manage_ads",
    "pages_manage_posts", "pages_manage_metadata",
    "instagram_basic", "instagram_content_publish",
]


def verify_credentials(account: str | None = None, page: str | None = None) -> dict:
    """Check the token, scopes, Page to Instagram link, and ad account.

    Returns a structured report; raises nothing for the normal 'unhealthy'
    cases so callers can present the findings.
    """
    env_file = config.find_env_file()
    token = config.require("META_ACCESS_TOKEN")
    dbg = graph.get("debug_token", {"input_token": token}).get("data", {})
    scopes = dbg.get("scopes", [])
    report: dict = {
        "env_file": str(env_file) if env_file else None,
        "token_valid": bool(dbg.get("is_valid")),
        "expires_at": dbg.get("expires_at"),
        "scopes": scopes,
        "missing_scopes": [s for s in REQUIRED_SCOPES if s not in scopes],
    }

    page_id = config.page(page)
    page_info = graph.get(page_id, {"fields": "name,instagram_business_account"})
    iba = page_info.get("instagram_business_account")
    report["page"] = {
        "id": page_id,
        "name": page_info.get("name"),
        "instagram_linked": bool(iba),
        "instagram_id": iba.get("id") if iba else None,
    }

    ad_account_id = config.ad_account(account)
    acct = graph.get(
        ad_account_id,
        {"fields": "name,account_status,currency,timezone_name,amount_spent,balance"},
    )
    # Meta account_status: 1 = active. Anything else (2 disabled, 3 unsettled,
    # 7 pending risk review, 9 in grace period, ...) means you cannot deliver,
    # so it must fail the health check even if the token and links are fine.
    account_status = acct.get("account_status")
    report["ad_account"] = {
        "id": ad_account_id,
        "name": acct.get("name"),
        "status": account_status,
        "active": account_status == 1,
        "currency": acct.get("currency"),
        "timezone": acct.get("timezone_name"),
    }
    report["healthy"] = (
        report["token_valid"]
        and not report["missing_scopes"]
        and report["page"]["instagram_linked"]
        and report["ad_account"]["active"]
    )
    return report


# --------------------------------------------------------------------------- #
# Targeting
# --------------------------------------------------------------------------- #
TARGETING_TYPES = ["adinterest", "adworkposition", "adworkemployer", "adeducationschool"]


def search_targeting(query: str, type_: str = "adinterest", limit: int = 15) -> list[dict]:
    """Search Meta's targeting taxonomy. Returns rows with id, name, size, topic."""
    resp = graph.get("search", {"type": type_.lower(), "q": query, "limit": limit})
    rows = []
    for r in resp.get("data", []):
        rows.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "audience_size": r.get("audience_size_lower_bound") or r.get("audience_size"),
            "topic": r.get("topic") or (r.get("path", [""])[-1] if r.get("path") else ""),
        })
    return rows


# --------------------------------------------------------------------------- #
# Campaign
# --------------------------------------------------------------------------- #
OBJECTIVES = [
    "OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT",
    "OUTCOME_AWARENESS", "OUTCOME_SALES", "OUTCOME_APP_PROMOTION",
]


def create_campaign(
    name: str,
    *,
    objective: str = "OUTCOME_LEADS",
    status: str = "PAUSED",
    daily_budget: int | None = None,
    special_ad_category: str = "NONE",
    account: str | None = None,
) -> dict:
    ad_account_id = config.ad_account(account)
    data = {
        "name": name,
        "objective": objective.upper(),
        "status": status.upper(),
        "special_ad_categories": json.dumps(
            [] if special_ad_category.upper() == "NONE" else [special_ad_category.upper()]
        ),
    }
    if daily_budget is not None:
        data["daily_budget"] = daily_budget
    else:
        data["is_adset_budget_sharing_enabled"] = "false"
    resp = graph.post(f"{ad_account_id}/campaigns", data=data)
    return {"id": resp.get("id"), "name": name, "objective": objective.upper(), "status": status.upper()}


def list_campaigns(account: str | None = None, limit: int = 25) -> list[dict]:
    ad_account_id = config.ad_account(account)
    resp = graph.get(
        f"{ad_account_id}/campaigns",
        {"fields": "id,name,objective,status,effective_status,daily_budget,lifetime_budget,created_time",
         "limit": limit},
    )
    return resp.get("data", [])


# --------------------------------------------------------------------------- #
# Ad set
# --------------------------------------------------------------------------- #
OPTIMIZATION_GOALS = [
    "LEAD_GENERATION", "QUALITY_LEAD", "LINK_CLICKS", "REACH", "IMPRESSIONS",
    "LANDING_PAGE_VIEWS", "OFFSITE_CONVERSIONS", "POST_ENGAGEMENT",
]
BILLING_EVENTS = ["IMPRESSIONS", "LINK_CLICKS", "THRUPLAY"]
DESTINATION_TYPES = ["ON_AD", "WEBSITE", "MESSENGER", "INSTAGRAM_DIRECT"]


def build_targeting(
    countries: str | Iterable[str] = "US",
    age_min: int = 25,
    age_max: int = 55,
    interest_ids: str | Iterable[str] = "",
) -> dict:
    if isinstance(countries, str):
        country_list = [c.strip().upper() for c in countries.split(",") if c.strip()]
    else:
        country_list = [str(c).strip().upper() for c in countries if str(c).strip()]
    spec = {
        "geo_locations": {"countries": country_list or ["US"]},
        "age_min": age_min,
        "age_max": age_max,
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed"],
        "instagram_positions": ["stream"],
    }
    if isinstance(interest_ids, str):
        ids = [i.strip() for i in interest_ids.split(",") if i.strip()]
    else:
        ids = [str(i).strip() for i in interest_ids if str(i).strip()]
    if ids:
        spec["flexible_spec"] = [{"interests": [{"id": i} for i in ids]}]
    return spec


def create_adset(
    name: str,
    campaign_id: str,
    daily_budget: int,
    *,
    targeting: dict | None = None,
    countries: str | Iterable[str] = "US",
    age_min: int = 25,
    age_max: int = 55,
    interest_ids: str | Iterable[str] = "",
    optimization_goal: str = "LEAD_GENERATION",
    billing_event: str = "IMPRESSIONS",
    destination_type: str = "ON_AD",
    status: str = "PAUSED",
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP",
    account: str | None = None,
    page: str | None = None,
) -> dict:
    ad_account_id = config.ad_account(account)
    page_id = config.page(page)
    spec = targeting if targeting is not None else build_targeting(countries, age_min, age_max, interest_ids)
    data = {
        "name": name,
        "campaign_id": campaign_id,
        "daily_budget": daily_budget,
        "billing_event": billing_event.upper(),
        "optimization_goal": optimization_goal.upper(),
        "bid_strategy": bid_strategy.upper(),
        "destination_type": destination_type.upper(),
        "status": status.upper(),
        "targeting": json.dumps(spec),
        "promoted_object": json.dumps({"page_id": page_id}),
    }
    resp = graph.post(f"{ad_account_id}/adsets", data=data)
    return {"id": resp.get("id"), "name": name, "targeting": spec}


def list_adsets(account: str | None = None, campaign_id: str | None = None, limit: int = 25) -> list[dict]:
    ad_account_id = config.ad_account(account)
    path = f"{campaign_id}/adsets" if campaign_id else f"{ad_account_id}/adsets"
    resp = graph.get(
        path,
        {"fields": "id,name,campaign_id,status,effective_status,optimization_goal,billing_event,daily_budget,destination_type",
         "limit": limit},
    )
    return resp.get("data", [])


# --------------------------------------------------------------------------- #
# Creative
# --------------------------------------------------------------------------- #
def create_creative(
    name: str,
    message: str,
    headline: str,
    *,
    image: str | Path | None = None,
    image_hash: str | None = None,
    video: str | Path | None = None,
    video_id: str | None = None,
    thumbnail: str | Path | None = None,
    thumbnail_hash: str | None = None,
    description: str | None = None,
    link: str | None = None,
    cta: str = "LEARN_MORE",
    lead_form_id: str | None = None,
    page: str | None = None,
    ig_actor: str | None = None,
    account: str | None = None,
) -> dict:
    """Create an ad creative. Supports image or video, and either a plain
    website/link CTA or a lead-gen (Instant Form) CTA."""
    ad_account_id = config.ad_account(account)
    page_id = config.page(page)
    ig_actor_id = config.ig_actor(ig_actor)
    link = link or config.optional("ADVERTISER_URL")

    has_video = bool(video or video_id)
    has_image = bool(image or image_hash)
    if has_video and has_image:
        raise ValueError("Pick one media type: image or video, not both.")
    if not has_video and not has_image:
        raise ValueError("Provide an image or a video.")
    if not link and not lead_form_id:
        raise ValueError("Provide a link (or set ADVERTISER_URL), or a lead_form_id.")

    cta_type = cta.upper()
    if has_video:
        vid = video_id or upload_video(video, account=ad_account_id)
        thumb = thumbnail_hash or (upload_image(thumbnail, account=ad_account_id) if thumbnail else None)
        if not thumb:
            raise ValueError("Video creatives need a thumbnail (path or hash).")
        cta_value = {"lead_gen_form_id": lead_form_id, "link": link} if lead_form_id else {"link": link}
        video_data = {
            "video_id": vid, "image_hash": thumb, "message": message,
            "title": headline, "call_to_action": {"type": cta_type, "value": cta_value},
        }
        if description:
            video_data["link_description"] = description
        object_story_spec = {"page_id": page_id, "video_data": video_data}
    else:
        img_hash = image_hash or upload_image(image, account=ad_account_id)
        cta_value = {"lead_gen_form_id": lead_form_id} if lead_form_id else {"link": link}
        link_data = {
            "message": message, "name": headline, "image_hash": img_hash,
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
        data={"name": name, "object_story_spec": json.dumps(object_story_spec)},
    )
    return {"id": resp.get("id"), "name": name, "kind": "video" if has_video else "image"}


def list_creatives(account: str | None = None, limit: int = 25) -> list[dict]:
    ad_account_id = config.ad_account(account)
    resp = graph.get(f"{ad_account_id}/adcreatives", {"fields": "id,name,status,object_type", "limit": limit})
    return resp.get("data", [])


# --------------------------------------------------------------------------- #
# Ad
# --------------------------------------------------------------------------- #
def create_ad(
    name: str, adset_id: str, creative_id: str, *, status: str = "PAUSED", account: str | None = None
) -> dict:
    ad_account_id = config.ad_account(account)
    resp = graph.post(
        f"{ad_account_id}/ads",
        data={"name": name, "adset_id": adset_id,
              "creative": json.dumps({"creative_id": creative_id}), "status": status.upper()},
    )
    return {"id": resp.get("id"), "name": name, "status": status.upper()}


def set_ad_status(ad_id: str, status: str) -> dict:
    graph.post(ad_id, data={"status": status.upper()})
    return {"id": ad_id, "status": status.upper()}


def set_adset_status(adset_id: str, status: str) -> dict:
    graph.post(adset_id, data={"status": status.upper()})
    return {"id": adset_id, "status": status.upper()}


def set_campaign_status(campaign_id: str, status: str) -> dict:
    graph.post(campaign_id, data={"status": status.upper()})
    return {"id": campaign_id, "status": status.upper()}


def activate_delivery(ad_id: str) -> dict:
    """Actually make an ad deliver.

    A Meta ad only serves when its own status AND its parent ad set AND its
    parent campaign are all ACTIVE. adkit builds everything PAUSED, so flipping
    just the ad on would leave it stuck behind two paused parents and it would
    never spend. This walks up from the ad and activates the whole chain, which
    is what "go live" actually means. Other ads in the same ad set stay PAUSED,
    so this only starts the one ad you named.
    """
    parents = graph.get(ad_id, {"fields": "adset_id,campaign_id"})
    campaign_id = parents.get("campaign_id")
    adset_id = parents.get("adset_id")
    activated = []
    if campaign_id:
        set_campaign_status(campaign_id, "ACTIVE")
        activated.append({"level": "campaign", "id": campaign_id})
    if adset_id:
        set_adset_status(adset_id, "ACTIVE")
        activated.append({"level": "adset", "id": adset_id})
    set_ad_status(ad_id, "ACTIVE")
    activated.append({"level": "ad", "id": ad_id})
    return {"ad_id": ad_id, "activated": activated}


def list_ads(account: str | None = None, adset_id: str | None = None, limit: int = 25) -> list[dict]:
    ad_account_id = config.ad_account(account)
    path = f"{adset_id}/ads" if adset_id else f"{ad_account_id}/ads"
    resp = graph.get(path, {"fields": "id,name,status,effective_status,adset_id,creative", "limit": limit})
    return resp.get("data", [])


# --------------------------------------------------------------------------- #
# Lead forms
# --------------------------------------------------------------------------- #
def page_access_token(page_id: str) -> str:
    token = graph.get(page_id, {"fields": "access_token"}).get("access_token")
    if not token:
        raise ValueError(
            f"Could not get a Page access token for {page_id}. "
            "Your user token needs pages_manage_ads and a role on the Page."
        )
    return token


def create_lead_form(
    name: str,
    privacy_url: str,
    *,
    privacy_link_text: str = "Privacy Policy",
    locale: str = "en_US",
    headline: str = "Get in touch",
    description: str = "Leave your name and phone and we'll call you back.",
    thank_you_title: str = "Thanks! We'll be in touch shortly.",
    thank_you_url: str | None = None,
    page: str | None = None,
) -> dict:
    page_id = config.page(page)
    token = page_access_token(page_id)
    data = {
        "name": name,
        "locale": locale,
        "questions": json.dumps([{"type": "FULL_NAME"}, {"type": "PHONE"}]),
        "privacy_policy": json.dumps({"url": privacy_url, "link_text": privacy_link_text}),
        "context_card": json.dumps({"title": headline, "content": [description], "style": "PARAGRAPH_STYLE"}),
        "thank_you_page": json.dumps({
            "title": thank_you_title, "body": "We received your details.",
            "button_type": "VIEW_WEBSITE", "button_text": "Visit our site",
            "website_url": thank_you_url or privacy_url,
        }),
        "follow_up_action_url": thank_you_url or privacy_url,
        "is_optimized_for_quality": "true",
    }
    # Lead forms are Page-owned, so they must be written with the Page token,
    # passed via the Authorization header (see graph._request), not the body.
    resp = graph.post(f"{page_id}/leadgen_forms", data=data, access_token=token)
    return {"id": resp.get("id"), "name": name}


def list_lead_forms(page: str | None = None, limit: int = 25) -> list[dict]:
    page_id = config.page(page)
    token = page_access_token(page_id)
    resp = graph.get(
        f"{page_id}/leadgen_forms",
        {"fields": "id,name,status,locale,leads_count", "limit": limit},
        access_token=token,
    )
    return resp.get("data", [])


# --------------------------------------------------------------------------- #
# Brief automation
# --------------------------------------------------------------------------- #
def plan_brief(brief: dict) -> dict:
    """Summarize what a brief would build, without touching the API."""
    camp = brief["campaign"]
    adsets = []
    for aset in brief.get("adsets", []):
        ads = []
        for ad in aset.get("ads", []):
            gen = ad.get("generate") or {}
            media = "video" if (ad.get("video") or gen.get("type") == "video") else "image"
            ads.append({"name": ad.get("name"), "media": media, "cta": ad.get("cta", "LEARN_MORE"),
                        "will_generate": bool(gen)})
        adsets.append({"name": aset["name"], "daily_budget": aset.get("daily_budget"), "ads": ads})
    return {
        "objective": camp.get("objective", "OUTCOME_TRAFFIC").upper(),
        "campaign": camp["name"],
        "adsets": adsets,
    }


def _generate_asset(ad: dict, creatives_dir: Path, emit: Emit) -> None:
    """Run the ad's `generate` block (if any) and set ad['image'] or ad['video'].

    If the target file already exists we reuse it instead of regenerating, so a
    re-run after a partial failure never pays for the same creative twice.
    """
    gen = ad.get("generate")
    if not gen:
        return
    kind = gen.get("type", "image")
    slug = (ad.get("name", "creative")).lower().replace(" ", "_")
    if kind == "image":
        out = creatives_dir / f"{slug}.png"
        if out.exists():
            ad["image"] = str(out)
            emit(f"reusing existing image {out} (no spend)")
            return
        from . import creative_gen  # imported lazily so the ads API works without it
        creative_gen.generate_image(gen["prompt"], out, aspect=gen.get("aspect", "1:1"), size=gen.get("size", "2K"))
        ad["image"] = str(out)
        emit(f"generated image: {out}")
    elif kind == "video":
        out = creatives_dir / f"{slug}.mp4"
        if out.exists():
            ad["video"] = str(out)
            emit(f"reusing existing video {out} (no spend)")
            return
        from . import creative_gen
        creative_gen.generate_video(
            gen["prompt"], out,
            image=Path(gen["seed_image"]) if gen.get("seed_image") else None,
            duration=int(gen.get("duration", 8)), aspect=gen.get("aspect", "9:16"), fast=gen.get("fast", True),
        )
        ad["video"] = str(out)
        emit(f"generated video: {out}")
    else:
        raise ValueError(f"Unknown generate.type: {kind!r} (use image or video).")


def _find_by_name(rows: list[dict], name: str) -> str | None:
    """Return the id of the first row whose name matches, else None."""
    for row in rows:
        if row.get("name") == name:
            return row.get("id")
    return None


def launch_from_brief(
    brief: dict,
    *,
    go: bool = False,
    creatives_dir: str | Path = "creatives",
    reuse: bool = True,
    on_event: Emit | None = None,
) -> dict:
    """Build a whole campaign from a brief.

    go=False returns the plan and creates nothing (a dry run).

    go=True builds everything PAUSED. It is written to be safe to re-run:

      * Idempotent by name (reuse=True, the default). A campaign / ad set / ad /
        lead form whose name already exists is reused instead of duplicated, so
        re-running after a mid-way failure resumes where it stopped rather than
        creating a second copy of everything.
      * Cheap-fail-first. The campaign and ad-set shells (free, PAUSED) are
        created before any creative is generated, so a bad objective or budget
        fails before you spend a cent on media.
      * No double spend on creative. `generate` blocks skip generation when the
        output file already exists.

    on_event, if given, receives progress strings. On any failure part-way
    through, the exception carries the ids created so far so nothing is orphaned
    silently.
    """
    emit = on_event or _noop
    plan = plan_brief(brief)
    if not go:
        return {"mode": "dry_run", "plan": plan, "created": None}

    creatives_dir = Path(creatives_dir)
    account = brief.get("account")
    page = brief.get("page")
    ig_actor = brief.get("ig_actor")
    camp = brief["campaign"]
    objective = camp.get("objective", "OUTCOME_TRAFFIC").upper()
    is_leadgen = objective == "OUTCOME_LEADS"

    created: dict = {"campaign_id": None, "lead_form_id": None, "ad_ids": []}
    try:
        existing_campaign = _find_by_name(list_campaigns(account, limit=200), camp["name"]) if reuse else None
        if existing_campaign:
            campaign = {"id": existing_campaign}
            emit(f"reusing campaign {existing_campaign} ({camp['name']})")
        else:
            campaign = create_campaign(
                camp["name"], objective=objective, daily_budget=camp.get("daily_budget"),
                special_ad_category=camp.get("special_ad_category", "NONE"), account=account,
            )
            emit(f"campaign {campaign['id']}")
        created["campaign_id"] = campaign["id"]

        lead_form_id = None
        if is_leadgen and brief.get("lead_form"):
            lf = brief["lead_form"]
            existing_form = _find_by_name(list_lead_forms(page, limit=200), lf["name"]) if reuse else None
            if existing_form:
                lead_form_id = existing_form
                emit(f"reusing lead form {lead_form_id}")
            else:
                form = create_lead_form(
                    lf["name"], lf["privacy_url"],
                    privacy_link_text=lf.get("privacy_link_text", "Privacy Policy"),
                    locale=lf.get("locale", "en_US"), headline=lf.get("headline", "Get in touch"),
                    description=lf.get("description", ""), thank_you_title=lf.get("thank_you_title", "Thanks!"),
                    thank_you_url=lf.get("thank_you_url"), page=page,
                )
                lead_form_id = form["id"]
                emit(f"lead form {lead_form_id}")
        created["lead_form_id"] = lead_form_id

        for aset in brief.get("adsets", []):
            existing_adset = (
                _find_by_name(list_adsets(account, campaign["id"], limit=200), aset["name"]) if reuse else None
            )
            if existing_adset:
                adset = {"id": existing_adset}
                emit(f"reusing adset {existing_adset} ({aset['name']})")
            else:
                adset = create_adset(
                    aset["name"], campaign["id"], aset["daily_budget"],
                    targeting=json.loads(Path(aset["targeting_json"]).read_text()) if aset.get("targeting_json") else None,
                    countries=aset.get("countries", ["US"]), age_min=aset.get("age_min", 25),
                    age_max=aset.get("age_max", 55), interest_ids=aset.get("interest_ids", ""),
                    optimization_goal=aset.get("optimization_goal", "LEAD_GENERATION" if is_leadgen else "LINK_CLICKS"),
                    billing_event=aset.get("billing_event", "IMPRESSIONS"),
                    destination_type=aset.get("destination_type", "ON_AD" if is_leadgen else "WEBSITE"),
                    bid_strategy=aset.get("bid_strategy", "LOWEST_COST_WITHOUT_CAP"),
                    account=account, page=page,
                )
                emit(f"adset {adset['id']} ({aset['name']})")

            existing_ads = list_ads(account, adset["id"], limit=200) if reuse else []
            for ad in aset.get("ads", []):
                ad_name = ad.get("name", ad["headline"])
                already = _find_by_name(existing_ads, ad_name) if reuse else None
                if already:
                    emit(f"reusing ad {already} ({ad_name}); skipping generation")
                    created["ad_ids"].append(already)
                    continue
                # Only now (ad set exists, ad does not) do we spend on creative.
                _generate_asset(ad, creatives_dir, emit)
                creative = create_creative(
                    ad_name, ad["message"], ad["headline"],
                    image=ad.get("image"), image_hash=ad.get("image_hash"),
                    video=ad.get("video"), video_id=ad.get("video_id"),
                    thumbnail=ad.get("thumbnail"), thumbnail_hash=ad.get("thumbnail_hash"),
                    description=ad.get("description"), link=ad.get("link"),
                    cta=ad.get("cta", "LEARN_MORE"), lead_form_id=lead_form_id,
                    page=page, ig_actor=ig_actor, account=account,
                )
                made = create_ad(ad_name, adset["id"], creative["id"], account=account)
                emit(f"ad {made['id']} (creative {creative['id']})")
                created["ad_ids"].append(made["id"])
    except Exception as exc:
        raise LaunchError(
            f"Brief launch failed partway: {exc}\n"
            f"Created so far (all PAUSED, nothing is spending): {json.dumps(created)}\n"
            "Fix the cause and re-run the same brief; adkit reuses what already exists.",
            created=created,
        ) from exc

    return {"mode": "live", "plan": plan, "created": created}
