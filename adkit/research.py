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
from collections import Counter
from datetime import datetime, timezone
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
