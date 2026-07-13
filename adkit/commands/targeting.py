import click

from .. import core


@click.group()
def targeting():
    """Look up Meta targeting taxonomy (interests, behaviors, demographics)."""


@targeting.command("search")
@click.argument("query")
@click.option(
    "--type",
    "type_",
    type=click.Choice(core.TARGETING_TYPES, case_sensitive=False),
    default="adinterest",
    show_default=True,
    help="adinterest = interests; adworkposition = job titles.",
)
@click.option("--limit", type=int, default=15, show_default=True)
def search(query, type_, limit):
    """Search Meta's targeting taxonomy by name."""
    rows = core.search_targeting(query, type_, limit)
    if not rows:
        click.echo("(no matches)")
        return
    for r in rows:
        size = r.get("audience_size") or "-"
        click.echo(f"{str(r.get('id')):<22}  ~{str(size):<14}  {r.get('name','')}  ({r.get('topic','')})")
