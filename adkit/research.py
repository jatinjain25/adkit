"""Competitive research via Meta's official Ad Library API.

The first step in automating ads is understanding what already works in your
market. This module queries the Ad Library (`ads_archive`) for competitor ads in
a category and country, then ranks and analyzes them.

Why the API and not scraping: scraping Meta's site violates their Terms and can
get your ad account banned. The API returns the same ad content cleanly.

What you can and cannot learn:
  * You CAN see each ad's creative (body text, link title/caption), the
    advertiser, the platforms, and how long it has been running.
  * You CANNOT see impressions or spend for commercial ads. Meta exposes those
    only for political / social-issue ads. So we rank by a proxy for success:
    how long an ad has run and how many variants an advertiser is running.
    Advertisers kill losers fast, so a long-running, heavily-varied ad is almost
    certainly a winner.

Access: the Ad Library API needs a one-time identity confirmation and terms
acceptance at https://www.facebook.com/ads/library/api. Until that is done the
API returns a permission error, which we surface as AdLibraryAccessError with
setup guidance.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

from . import graph

SETUP_URL = "https://www.facebook.com/ads/library/api"

AD_FIELDS = [
    "id",
    "page_id",
    "page_name",
    "ad_creative_bodies",
    "ad_creative_link_titles",
    "ad_creative_link_captions",
    "ad_creative_link_descriptions",
    "ad_snapshot_url",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "publisher_platforms",
    "languages",
]

ACTIVE_STATUSES = ["ACTIVE", "INACTIVE", "ALL"]
MEDIA_TYPES = ["ALL", "IMAGE", "VIDEO", "MEME", "NONE"]


class AdLibraryAccessError(Exception):
    """Raised when the token lacks Ad Library API access (needs identity check)."""


def search_ad_library(
    keyword: str,
    country: str = "IN",
    *,
    active_status: str = "ACTIVE",
    media_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return ads matching `keyword` delivered to `country` from the Ad Library.

    Paginates until `limit` ads are collected or results run out. Raises
    AdLibraryAccessError if the account has not completed Ad Library API access.
    """
    params: dict = {
        "search_terms": keyword,
        "ad_reached_countries": json.dumps([country.upper()]),
        "ad_active_status": active_status.upper(),
        "fields": ",".join(AD_FIELDS),
        "limit": min(limit, 100),
    }
    if media_type and media_type.upper() != "ALL":
        params["media_type"] = media_type.upper()

    ads: list[dict] = []
    after: str | None = None
    while len(ads) < limit:
        page_params = dict(params)
        if after:
            page_params["after"] = after
        try:
            resp = graph.get("ads_archive", page_params)
        except graph.GraphError as e:
            msg = str(e)
            if "2332002" in msg or "permission for this action" in msg.lower():
                raise AdLibraryAccessError(
                    "Ad Library API access is not enabled for this account.\n"
                    f"Confirm your identity and accept the terms at {SETUP_URL},\n"
                    "then try again. (This is a one-time setup, like enabling lead ads.)"
                ) from None
            raise
        batch = resp.get("data", [])
        ads.extend(batch)
        after = resp.get("paging", {}).get("cursors", {}).get("after")
        if not batch or not after:
            break
    return ads[:limit]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    # Meta returns e.g. "2024-05-01T07:00:00+0000" or "2024-05-01".
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _days_running(ad: dict, now: datetime) -> int:
    start = _parse_time(ad.get("ad_delivery_start_time"))
    if not start:
        return 0
    stop = _parse_time(ad.get("ad_delivery_stop_time")) or now
    return max(0, (stop - start).days)


def _domain(caption: str | None) -> str | None:
    if not caption:
        return None
    text = caption.strip().lower()
    if "://" not in text:
        text = "http://" + text
    host = urlparse(text).netloc
    return host[4:] if host.startswith("www.") else host or None


def _first(seq, default=None):
    return seq[0] if seq else default


def analyze(ads: list[dict], now: datetime | None = None) -> dict:
    """Turn raw Ad Library rows into a ranked competitive report.

    Ranking uses winner_score = variants * longest_run_days, the best proxy we
    have without spend data. Returns advertisers (ranked), top individual ads,
    and an aggregate pattern summary. Never fabricates metrics.
    """
    now = now or datetime.now(timezone.utc)
    for ad in ads:
        ad["_days_running"] = _days_running(ad, now)

    advertisers: dict[str, dict] = {}
    for ad in ads:
        name = ad.get("page_name") or ad.get("page_id") or "(unknown)"
        adv = advertisers.setdefault(
            name,
            {"advertiser": name, "page_id": ad.get("page_id"), "variants": 0,
             "days": [], "ctas": Counter(), "domains": Counter(),
             "platforms": Counter(), "sample_ads": []},
        )
        adv["variants"] += 1
        adv["days"].append(ad["_days_running"])
        title = _first(ad.get("ad_creative_link_titles"))
        if title:
            adv["ctas"][title.strip()] += 1
        dom = _domain(_first(ad.get("ad_creative_link_captions")))
        if dom:
            adv["domains"][dom] += 1
        for p in ad.get("publisher_platforms", []) or []:
            adv["platforms"][p] += 1
        if len(adv["sample_ads"]) < 3:
            adv["sample_ads"].append({
                "days_running": ad["_days_running"],
                "body": (_first(ad.get("ad_creative_bodies")) or "")[:240],
                "link_title": title,
                "snapshot_url": ad.get("ad_snapshot_url"),
            })

    ranked = []
    for adv in advertisers.values():
        longest = max(adv["days"]) if adv["days"] else 0
        ranked.append({
            "advertiser": adv["advertiser"],
            "page_id": adv["page_id"],
            "variants": adv["variants"],
            "longest_run_days": longest,
            "median_run_days": int(median(adv["days"])) if adv["days"] else 0,
            "winner_score": adv["variants"] * longest,
            "top_ctas": [c for c, _ in adv["ctas"].most_common(3)],
            "domains": [d for d, _ in adv["domains"].most_common(3)],
            "platforms": [p for p, _ in adv["platforms"].most_common()],
            "sample_ads": sorted(adv["sample_ads"], key=lambda a: -a["days_running"]),
        })
    ranked.sort(key=lambda a: (a["winner_score"], a["longest_run_days"]), reverse=True)

    top_ads = sorted(
        (
            {
                "advertiser": ad.get("page_name"),
                "days_running": ad["_days_running"],
                "body": (_first(ad.get("ad_creative_bodies")) or "")[:240],
                "link_title": _first(ad.get("ad_creative_link_titles")),
                "snapshot_url": ad.get("ad_snapshot_url"),
            }
            for ad in ads
        ),
        key=lambda a: -a["days_running"],
    )[:10]

    all_ctas = Counter(t.strip() for ad in ads for t in (ad.get("ad_creative_link_titles") or []) if t)
    all_domains = Counter(d for ad in ads if (d := _domain(_first(ad.get("ad_creative_link_captions")))))
    platform_mix = Counter(p for ad in ads for p in (ad.get("publisher_platforms") or []))

    return {
        "total_ads": len(ads),
        "total_advertisers": len(advertisers),
        "advertisers": ranked,
        "top_ads": top_ads,
        "patterns": {
            "dominant_ctas": [c for c, _ in all_ctas.most_common(5)],
            "dominant_domains": [d for d, _ in all_domains.most_common(5)],
            "platform_mix": dict(platform_mix),
        },
        "note": (
            "Ranked by longevity x variant count. Meta does not expose impressions "
            "or spend for commercial ads, so these are proxies for what is working, "
            "not measured performance."
        ),
    }


def research(
    keyword: str,
    country: str = "IN",
    *,
    active_status: str = "ACTIVE",
    media_type: str | None = None,
    limit: int = 100,
) -> dict:
    """Convenience: fetch + analyze in one call. Returns the analysis report."""
    ads = search_ad_library(
        keyword, country, active_status=active_status, media_type=media_type, limit=limit
    )
    return analyze(ads)


# --------------------------------------------------------------------------- #
# Seed brief: turn research into a starter campaign brief (research -> brief ->
# creative). We encode the winning *patterns* and link to competitor ads to
# study, never their verbatim copy.
# --------------------------------------------------------------------------- #
_CTA_MAP = [
    ("sign up", "SIGN_UP"), ("apply", "APPLY_NOW"), ("subscribe", "SUBSCRIBE"),
    ("quote", "GET_QUOTE"), ("book", "BOOK_TRAVEL"),
]
_STOP = set(
    "the a an and or to for of in on with your you our we is are it this that get how why what "
    "best top new free now your yours their they them from at by as be will can more most just "
    "about into over out up down off all any one two your".split()
)


def _meta_cta(text: str | None) -> str:
    t = (text or "").lower()
    for needle, cta in _CTA_MAP:
        if needle in t:
            return cta
    return "LEARN_MORE"


def _themes(report: dict, n: int = 6) -> list[str]:
    counts: Counter = Counter()
    for ad in report.get("top_ads", []):
        for word in re.findall(r"[a-zA-Z]{4,}", (ad.get("body") or "").lower()):
            if word not in _STOP:
                counts[word] += 1
    return [w for w, _ in counts.most_common(n)]


def build_seed_brief(report: dict, keyword: str, country: str) -> str:
    """Render a starter brief (YAML text) seeded from a research report.

    The copy fields are paraphrased placeholders that cite the winning pattern
    and link to competitor ads; the user rewrites them in their own voice.
    """
    country = country.upper()
    ctas = report.get("patterns", {}).get("dominant_ctas", []) or []
    dom_cta_text = ctas[0] if ctas else None
    meta_cta = _meta_cta(dom_cta_text)
    themes = _themes(report)
    theme_str = ", ".join(themes) if themes else "(no recurring themes found)"
    winners = report.get("advertisers", [])[:3]
    top_ads = report.get("top_ads", [])[:3]

    header = [
        f"# adkit brief seeded from Ad Library research: '{keyword}' in {country}",
        f"# Generated {datetime.now(timezone.utc):%Y-%m-%d}. These are STARTING POINTS derived from",
        "# what is working in this market. Rewrite the copy in your own voice; do not copy",
        "# competitors verbatim. Fill in the budget, targeting, and destination.",
        "#",
        f"# Recurring themes in top ads: {theme_str}",
        f"# Most common CTA/headline seen: {dom_cta_text or '(none)'}",
    ]
    if winners:
        header.append("# Top advertisers (by longevity x variants):")
        for adv in winners:
            header.append(
                f"#   - {adv['advertiser']} "
                f"({adv['variants']} variants, up to {adv['longest_run_days']}d)"
            )
    if top_ads:
        header.append("# Study these long-running ads:")
        for ad in top_ads:
            if ad.get("snapshot_url"):
                header.append(f"#   {ad['days_running']}d  {ad['snapshot_url']}")

    body = f"""
account: null
page: null
creatives_dir: creatives

campaign:
  name: "{keyword.title()} | Research-seeded"
  objective: OUTCOME_TRAFFIC        # switch to OUTCOME_LEADS for an Instant Form

adsets:
  - name: "{country} | {keyword} audience"
    daily_budget: 20000             # minor units; set to your budget (20000 = 200.00)
    countries: [{country}]
    age_min: 25
    age_max: 55
    interest_ids: []                # find IDs with: adkit targeting search "{keyword}"
    optimization_goal: LINK_CLICKS
    destination_type: WEBSITE
    ads:
      - name: "Angle 1"
        # Winning ads here lead with: {theme_str}
        message: "REWRITE: your hook for {keyword} buyers in {country}, in your own voice."
        headline: "REWRITE: your promise in 4-6 words"
        link: "https://your-site.com"
        cta: {meta_cta}             # most common competitor CTA was: {dom_cta_text or 'n/a'}
        generate:
          type: image               # switch to video (aspect 9:16) for Reels/Stories
          prompt: "On-brand ad for {keyword} in {country}, bold headline, clean modern look, angle: {theme_str}"
          aspect: "1:1"

      - name: "Angle 2"
        message: "REWRITE: a second, different angle (e.g. proof, urgency, or outcome)."
        headline: "REWRITE: a sharper second hook"
        link: "https://your-site.com"
        cta: {meta_cta}
        generate:
          type: image
          prompt: "Alternative ad concept for {keyword}, different visual, same offer"
          aspect: "1:1"
"""
    return "\n".join(header) + "\n" + body.lstrip("\n")


# --------------------------------------------------------------------------- #
# Soft "did you research first?" nudge. State lives in a small cache marker so
# the tip only shows when research was not run recently. Never blocks anything.
# --------------------------------------------------------------------------- #
_TRUTHY = {"1", "true", "yes", "on"}


def _cache_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "adkit" / "last_research.json"


def record_research(keyword: str, country: str) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "keyword": keyword, "country": country,
        "ts": datetime.now(timezone.utc).isoformat(),
    }))


def recent_research(max_age_days: int = 30) -> dict | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        ts = datetime.fromisoformat(data["ts"])
    except (ValueError, KeyError, OSError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - ts).days > max_age_days:
        return None
    return data


def research_reminder() -> str | None:
    """One-line, suppressible nudge to research before making creatives.
    Returns None if tips are silenced or research was run recently."""
    if os.environ.get("ADKIT_NO_TIPS", "").strip().lower() in _TRUTHY:
        return None
    if recent_research():
        return None
    return (
        "Tip: base creatives on what's already working, look at winning ads first:\n"
        "     adkit research --keyword \"<your category>\" --country <cc>   (silence: ADKIT_NO_TIPS=1)"
    )
