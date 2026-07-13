import click

from .. import graph


@click.group()
def targeting():
    """Look up Meta targeting taxonomy (interests, behaviors, demographics)."""


@targeting.command("search")
@click.argument("query")
@click.option(
    "--type",
    "type_",
    type=click.Choice(
        ["adinterest", "adworkposition", "adworkemployer", "adeducationschool"],
        case_sensitive=False,
    ),
    default="adinterest",
    show_default=True,
    help="adinterest = interests; adworkposition = job titles.",
)
@click.option("--limit", type=int, default=15, show_default=True)
def search(query, type_, limit):
    """Search Meta's targeting taxonomy by name."""
    resp = graph.get(
        "search",
        {"type": type_.lower(), "q": query, "limit": limit},
    )
    rows = resp.get("data", [])
    if not rows:
        click.echo("(no matches)")
        return
    for r in rows:
        size = r.get("audience_size_lower_bound") or r.get("audience_size") or "-"
        topic = r.get("topic") or r.get("path", [""])[-1] or ""
        click.echo(f"{r.get('id'):<22}  ~{size:<14}  {r.get('name','')}  ({topic})")
