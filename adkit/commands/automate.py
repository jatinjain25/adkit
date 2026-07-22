"""End-to-end automation: build an entire ad chain from a single brief file.

This command is a thin wrapper over `core.launch_from_brief`. The whole
implementation lives in the importable core, so the MCP server and any Python
caller get the exact same behavior.

Safety by design:
  * Dry run is the default. Nothing is written to Meta until you pass --go.
  * Every object is created PAUSED, so no spend starts until you flip it on.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .. import core


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
    plan = core.plan_brief(spec)

    mode = "LIVE" if go else "DRY RUN"
    click.echo(f"=== adkit automate launch [{mode}] ===")
    click.echo(f"objective={plan['objective']}")
    click.echo(f"campaign: {plan['campaign']}")
    for aset in plan["adsets"]:
        click.echo(f"  adset: {aset['name']}  budget={aset['daily_budget']} (minor units)")
        for ad in aset["ads"]:
            tag = " (will generate)" if ad["will_generate"] else ""
            click.echo(f"    ad: {ad['name']}  [{ad['media']}]  cta={ad['cta']}{tag}")

    if not go:
        if any(ad["will_generate"] for aset in plan["adsets"] for ad in aset["ads"]):
            from ..research import research_reminder
            tip = research_reminder()
            if tip:
                click.echo("\n" + tip)
        click.echo(
            "\nDry run complete. Nothing was created and no creative was generated.\n"
            "Re-run with --go to build it (all objects start PAUSED)."
        )
        return

    click.echo("")
    try:
        result = core.launch_from_brief(
            spec, go=True,
            creatives_dir=spec.get("creatives_dir", "creatives"),
            on_event=lambda m: click.echo(f"  ✓ {m}"),
        )
    except core.LaunchError as e:
        raise SystemExit(f"\n✗ {e}")

    created = result["created"]
    click.echo(
        f"\n✓ Built campaign {created['campaign_id']}: "
        f"{len(created['ad_ids'])} ads. Everything is PAUSED.\n"
        f"Review in Ads Manager, then go live with the whole delivery chain:\n"
        f"  adkit ad activate --ad-id <id>   (activates the ad, its ad set, and its campaign)"
    )
