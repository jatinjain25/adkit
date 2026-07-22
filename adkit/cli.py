import click

from .commands.ad import ad
from .commands.adset import adset
from .commands.automate import automate
from .commands.campaign import campaign
from .commands.creative import creative
from .commands.demo import demo, init
from .commands.generate import generate
from .commands.leadform import leadform
from .commands.optimize import optimize
from .commands.research import research
from .commands.targeting import targeting
from .commands.verify import verify


@click.group()
def cli():
    """adkit: plug-and-play Meta (Facebook + Instagram) ads automation.

    Drive your whole ad chain from the terminal or from Claude Code: verify
    credentials, research targeting, generate AI creative, and launch campaigns
    from a single brief. Everything is created PAUSED so nothing spends by
    accident.
    """


cli.add_command(demo)
cli.add_command(init)
cli.add_command(research)
cli.add_command(verify)
cli.add_command(targeting)
cli.add_command(campaign)
cli.add_command(adset)
cli.add_command(leadform)
cli.add_command(creative)
cli.add_command(ad)
cli.add_command(generate)
cli.add_command(automate)
cli.add_command(optimize)


if __name__ == "__main__":
    cli()
