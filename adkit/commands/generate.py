from pathlib import Path

import click

from .. import creative_gen
from ..research import research_reminder


def _nudge():
    tip = research_reminder()
    if tip:
        click.echo(tip)


@click.group()
def generate():
    """Generate ad creative with AI (Gemini images, Veo videos)."""


@generate.command("image")
@click.argument("prompt")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output image path, e.g. creatives/hook.png.",
)
@click.option(
    "--aspect",
    type=click.Choice(["1:1", "4:5", "9:16", "16:9", "4:3", "3:4"]),
    default="1:1",
    show_default=True,
    help="1:1 or 4:5 for feed, 9:16 for Stories/Reels.",
)
@click.option(
    "--size",
    type=click.Choice(["1K", "2K", "4K"]),
    default="2K",
    show_default=True,
)
def image(prompt, out, aspect, size):
    """Generate a still ad image from a text prompt."""
    _nudge()
    click.echo(f"[~${creative_gen.COST_IMAGE:.2f}] image -> {out}")
    try:
        path = creative_gen.generate_image(prompt, out, aspect=aspect, size=size)
    except creative_gen.CreativeGenError as e:
        raise SystemExit(str(e))
    click.echo(f"  ✓ saved: {path}")


@generate.command("video")
@click.argument("prompt")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output video path, e.g. creatives/founder.mp4.",
)
@click.option(
    "--image",
    "seed_image",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional seed image for image-to-video (keeps a subject consistent).",
)
@click.option(
    "--duration",
    type=click.Choice(["4", "6", "8"]),
    default="8",
    show_default=True,
)
@click.option(
    "--aspect",
    type=click.Choice(["9:16", "16:9", "1:1"]),
    default="9:16",
    show_default=True,
)
@click.option(
    "--quality",
    is_flag=True,
    default=False,
    help="Use the higher-fidelity (pricier) model. Default is Fast. "
    "Only use after a Fast draft validates the shot.",
)
def video(prompt, out, seed_image, duration, aspect, quality):
    """Generate a short ad video. Fast model by default to control cost."""
    _nudge()
    dur = int(duration)
    est = creative_gen.COST_VIDEO.get(dur, creative_gen.COST_VIDEO[8])
    click.echo(f"[~${est:.2f}] {dur}s video ({'quality' if quality else 'fast'}) -> {out}")
    try:
        path = creative_gen.generate_video(
            prompt, out, image=seed_image, duration=dur, aspect=aspect, fast=not quality
        )
    except creative_gen.CreativeGenError as e:
        raise SystemExit(str(e))
    click.echo(f"  ✓ saved: {path}")


@generate.command("spend")
def spend():
    """Show logged creative-generation spend."""
    click.echo(creative_gen.spend_summary())
