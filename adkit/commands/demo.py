"""Zero-credential first run.

`adkit demo` shows the whole build-a-campaign flow as a dry run, needing no Meta
account, no API keys, and no files on disk. It is the first thing a new user
should run, so it must not touch config, the network, or the optional `yaml` /
`creative_gen` dependencies. `adkit init` writes a real starter brief they can edit.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import click

from .. import core

# Embedded so `adkit demo` works on a bare `pip install meta-adkit` with no
# `yaml` extra installed. It mirrors data/example_brief.yaml (which `init` ships
# to disk with its comments intact).
_DEMO_BRIEF: dict = {
    "campaign": {
        "name": "Example | TOF | Traffic",
        "objective": "OUTCOME_TRAFFIC",
        "daily_budget": 5000,
    },
    "adsets": [
        {
            "name": "Agent builders",
            "daily_budget": 2500,
            "countries": ["US", "GB", "CA"],
            "ads": [
                {
                    "name": "Expensive chatbot",
                    "message": "Your agent forgets every user the second the session ends. "
                    "Add memory in one API call instead of building it for six weeks.",
                    "headline": "Give your product a memory",
                    "link": "https://example.com",
                    "cta": "LEARN_MORE",
                    "image": "creatives/expensive_chatbot.png",
                },
                {
                    "name": "Buy vs build",
                    "message": "Build your own retrieval stack: 6 to 8 weeks. Or ship today "
                    "with one API. Model agnostic, no lock in.",
                    "headline": "Don't build a memory team",
                    "link": "https://example.com",
                    "cta": "SIGN_UP",
                    "image": "creatives/buy_vs_build.png",
                },
            ],
        }
    ],
}


def _bundled_brief_text() -> str:
    return resources.files("adkit").joinpath("data/example_brief.yaml").read_text()


@click.command()
def demo() -> None:
    """See adkit build a whole campaign (dry run, no account or keys needed)."""
    plan = core.plan_brief(_DEMO_BRIEF)
    click.echo("=== adkit demo [DRY RUN] ===")
    click.echo("This is exactly what `adkit automate launch --brief <file>` prints before")
    click.echo("it builds anything. It writes nothing and needs no credentials.\n")
    click.echo(f"objective={plan['objective']}")
    click.echo(f"campaign: {plan['campaign']}")
    for aset in plan["adsets"]:
        click.echo(f"  adset: {aset['name']}  budget={aset['daily_budget']} (minor units)")
        for ad in aset["ads"]:
            tag = " (will generate)" if ad["will_generate"] else ""
            click.echo(f"    ad: {ad['name']}  [{ad['media']}]  cta={ad['cta']}{tag}")
    click.echo(
        "\nNothing was created. When you're ready to run this on a real account:\n"
        "  1. adkit verify                 # connect your Meta account (adkit guides you)\n"
        "  2. adkit research --keyword \"<your category>\" --country <cc> --seed-brief my-brief.yaml\n"
        "                                  # see what's working, seed a brief from it\n"
        "  3. adkit automate launch --brief my-brief.yaml        # dry run again\n"
        "  4. adkit automate launch --brief my-brief.yaml --go   # build it, all PAUSED\n"
        "  (no research access yet? use `adkit init my-brief.yaml` for a blank starter brief.)"
    )


@click.command()
@click.argument("out", type=click.Path(dir_okay=False, path_type=Path), default="brief.yaml")
def init(out: Path) -> None:
    """Write a starter campaign brief you can edit (default: brief.yaml)."""
    if out.exists():
        raise SystemExit(f"{out} already exists; choose another path or delete it first.")
    out.write_text(_bundled_brief_text())
    click.echo(f"  ✓ wrote starter brief: {out}")
    click.echo(
        "Tip: seed a brief from what's already working instead: "
        "adkit research --keyword \"<category>\" --country <cc> --seed-brief " + str(out)
    )
    click.echo("Edit it, then: adkit automate launch --brief " + str(out) + " (add --go to build).")
