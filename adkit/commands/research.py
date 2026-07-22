import json as _json
from pathlib import Path

import click

from .. import research as research_lib


@click.command()
@click.option("--keyword", required=True, help="Category or term to research, e.g. \"edtech\".")
@click.option(
    "--country",
    default="IN",
    show_default=True,
    help="ISO country code the ads are delivered to, e.g. IN, US.",
)
@click.option(
    "--active-status",
    type=click.Choice(research_lib.ACTIVE_STATUSES, case_sensitive=False),
    default="ACTIVE",
    show_default=True,
    help="ACTIVE = currently running (best signal), ALL = include stopped ads.",
)
@click.option(
    "--media-type",
    type=click.Choice(research_lib.MEDIA_TYPES, case_sensitive=False),
    default="ALL",
    show_default=True,
)
@click.option("--limit", type=int, default=100, show_default=True, help="Max ads to pull.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the raw report as JSON.")
@click.option(
    "--seed-brief",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Also write a starter campaign brief seeded from the findings (research -> brief -> creative).",
)
def research(keyword, country, active_status, media_type, limit, as_json, seed_brief):
    """Research competitor ads in the Ad Library (the start of the flow).

    Finds ads for a category in a country, ranks advertisers by how long and how
    widely they run (a proxy for what works, since Meta hides spend for
    commercial ads), and summarizes the winning patterns.
    """
    try:
        report = research_lib.research(
            keyword, country, active_status=active_status, media_type=media_type, limit=limit
        )
    except research_lib.AdLibraryAccessError as e:
        raise SystemExit(str(e))

    # Record that research happened so the "did you research first?" nudge stays quiet.
    research_lib.record_research(keyword, country)

    if seed_brief is not None:
        if seed_brief.exists():
            raise SystemExit(f"{seed_brief} already exists; choose another path or delete it first.")
        seed_brief.write_text(research_lib.build_seed_brief(report, keyword, country))
        click.echo(f"  ✓ wrote research-seeded brief: {seed_brief}")
        click.echo(f"    Edit the copy, then: adkit automate launch --brief {seed_brief}")

    if as_json:
        click.echo(_json.dumps(report, indent=2))
        return

    if report["total_ads"] == 0:
        click.echo(
            f"No ads found for '{keyword}' in {country}.\n"
            "Try --active-status ALL, a broader keyword, or another country. "
            "Note: the API's coverage of non-EU commercial ads can be sparse; "
            "the public Ad Library website may show more."
        )
        return

    click.echo(
        f"=== Ad Library research: '{keyword}' in {country} ===\n"
        f"{report['total_ads']} ads across {report['total_advertisers']} advertisers\n"
    )

    click.echo("Top advertisers (by winner-proxy = variants x longest run):")
    for i, adv in enumerate(report["advertisers"][:8], 1):
        ctas = f"  CTA: {adv['top_ctas'][0]}" if adv["top_ctas"] else ""
        dom = f"  -> {adv['domains'][0]}" if adv["domains"] else ""
        click.echo(
            f" {i}. {adv['advertiser']}  "
            f"[{adv['variants']} variants, up to {adv['longest_run_days']}d running]{dom}{ctas}"
        )

    click.echo("\nLongest-running individual ads (open the snapshot to view):")
    for ad in report["top_ads"][:6]:
        click.echo(f"  • {ad['days_running']}d  {ad['advertiser']}: \"{(ad['body'] or '').strip()[:90]}\"")
        if ad["snapshot_url"]:
            click.echo(f"      {ad['snapshot_url']}")

    p = report["patterns"]
    click.echo("\nWhat's working (patterns across the set):")
    if p["dominant_ctas"]:
        click.echo(f"  Common CTAs/headlines: {', '.join(p['dominant_ctas'][:5])}")
    if p["dominant_domains"]:
        click.echo(f"  Where they send traffic: {', '.join(p['dominant_domains'][:5])}")
    if p["platform_mix"]:
        click.echo(f"  Placements: {', '.join(f'{k}={v}' for k, v in p['platform_mix'].items())}")
    click.echo(f"\n{report['note']}")
