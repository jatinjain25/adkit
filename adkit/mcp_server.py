"""adkit MCP server.

Exposes adkit's operations as Model Context Protocol tools, so any MCP-capable
agent (Claude Code, Cursor, or your own app) can drive a Meta ad account, not
just the CLI. Every tool is a thin call into `adkit.core`, so behavior is
identical to the CLI.

Run it:
    adkit-mcp                 # after `pip install "meta-adkit[mcp]"`

Register it with an MCP client by pointing the client at the `adkit-mcp`
command over stdio.

Safety notes carried into the tool descriptions:
  * Creating campaigns, ad sets, creatives, and ads is safe: everything is
    PAUSED and spends nothing.
  * Two tools cost money or go live and say so: `activate_ad` (starts spend) and
    `generate_image` / `generate_video` (a few cents to ~$1.20 each).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import core

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    raise SystemExit(
        "The MCP server needs the 'mcp' package. Install it with:\n"
        "  pip install \"meta-adkit[mcp]\""
    )

mcp = FastMCP("adkit")

_TRUTHY = {"1", "true", "yes", "on"}


def _require_spend_opt_in(action: str) -> None:
    """Server-side guard for actions that spend money or go live.

    Descriptions asking the agent to 'confirm with the user' are advisory only:
    an auto-approving client or a prompt injection could ignore them. This gate
    is enforced by the server. The operator must opt in by setting
    ADKIT_ALLOW_SPEND=1 in the environment the server runs in.
    """
    if os.environ.get("ADKIT_ALLOW_SPEND", "").strip().lower() not in _TRUTHY:
        raise PermissionError(
            f"'{action}' is blocked: it spends money or starts ad delivery. "
            "The server operator must set ADKIT_ALLOW_SPEND=1 to enable spending "
            "actions. This protects against auto-approving clients and prompt injection."
        )


def _creative_base() -> Path:
    return Path(os.environ.get("ADKIT_CREATIVE_DIR") or (Path.cwd() / "creatives")).resolve()


def _confined_path(path: str) -> Path:
    """Resolve `path` and require it to stay inside the creatives working
    directory. Blocks path traversal so an agent cannot read or write arbitrary
    files through the MCP tools."""
    base = _creative_base()
    base.mkdir(parents=True, exist_ok=True)
    resolved = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if base != resolved and base not in resolved.parents:
        raise PermissionError(
            f"Path {path!r} is outside the allowed creatives directory ({base}). "
            "Over MCP, adkit only reads and writes inside that directory."
        )
    return resolved


# --- read-only, always safe ------------------------------------------------ #
@mcp.tool()
def verify() -> dict:
    """Check the Meta token, scopes, Page to Instagram link, and ad account.
    Read-only and free. Run this first."""
    return core.verify_credentials()


@mcp.tool()
def search_targeting(query: str, type: str = "adinterest", limit: int = 15) -> list[dict]:
    """Search Meta's targeting taxonomy for interest or job-title IDs.
    type: adinterest (interests) or adworkposition (job titles). Read-only."""
    return core.search_targeting(query, type, limit)


@mcp.tool()
def list_campaigns(limit: int = 25) -> list[dict]:
    """List campaigns in the ad account. Read-only."""
    return core.list_campaigns(limit=limit)


@mcp.tool()
def list_ads(adset_id: str | None = None, limit: int = 25) -> list[dict]:
    """List ads in the account, or under one ad set. Read-only."""
    return core.list_ads(adset_id=adset_id, limit=limit)


# --- creation, safe (everything is PAUSED, no spend) ----------------------- #
@mcp.tool()
def create_campaign(name: str, objective: str = "OUTCOME_TRAFFIC", daily_budget: int | None = None) -> dict:
    """Create a campaign (PAUSED, no spend). objective e.g. OUTCOME_TRAFFIC or
    OUTCOME_LEADS. daily_budget is in minor units (5000 = $50.00)."""
    return core.create_campaign(name, objective=objective, daily_budget=daily_budget)


@mcp.tool()
def create_adset(
    name: str, campaign_id: str, daily_budget: int,
    countries: list[str] | None = None, interest_ids: list[str] | None = None,
    optimization_goal: str = "LEAD_GENERATION", destination_type: str = "ON_AD",
) -> dict:
    """Create an ad set under a campaign (PAUSED, no spend). daily_budget in
    minor units. countries e.g. ['US','GB']. interest_ids from search_targeting.
    Defaults match the CLI: LEAD_GENERATION + ON_AD (Instant Form). For a
    website-traffic ad set pass optimization_goal='LINK_CLICKS',
    destination_type='WEBSITE'."""
    return core.create_adset(
        name, campaign_id, daily_budget,
        countries=countries or ["US"], interest_ids=interest_ids or [],
        optimization_goal=optimization_goal, destination_type=destination_type,
    )


@mcp.tool()
def create_ad_from_image(
    name: str, adset_id: str, image_path: str, message: str, headline: str,
    link: str | None = None, cta: str = "LEARN_MORE",
) -> dict:
    """Create an image creative and place it as an ad (PAUSED, no spend).
    image_path must be inside the creatives directory. Returns the creative and
    ad ids. link falls back to ADVERTISER_URL."""
    safe_image = _confined_path(image_path)
    creative = core.create_creative(name, message, headline, image=str(safe_image), link=link, cta=cta)
    made = core.create_ad(name, adset_id, creative["id"])
    return {"creative_id": creative["id"], "ad_id": made["id"]}


@mcp.tool()
def plan_brief(brief: dict[str, Any]) -> dict:
    """Summarize what a campaign brief would build, without touching the API.
    Safe and free. Use before launch_brief."""
    return core.plan_brief(brief)


@mcp.tool()
def launch_brief(brief: dict[str, Any], go: bool = False) -> dict:
    """Build a whole campaign from a brief. go=False (default) is a dry run that
    creates nothing. go=True creates everything PAUSED and runs any AI creative
    generation declared in the brief (which costs money, so it is gated by
    ADKIT_ALLOW_SPEND). Confirm with the user before passing go=True."""
    if go:
        _require_spend_opt_in("launch_brief(go=True)")
    events: list[str] = []
    return core.launch_from_brief(brief, go=go, on_event=events.append) | {"events": events}


# --- spends money or goes live: gated by ADKIT_ALLOW_SPEND ------------------ #
@mcp.tool()
def generate_image(prompt: str, out_path: str, aspect: str = "1:1") -> dict:
    """Generate an ad image with AI. COSTS about $0.15 and is gated by
    ADKIT_ALLOW_SPEND. out_path must be inside the creatives directory."""
    _require_spend_opt_in("generate_image")
    from . import creative_gen
    path = creative_gen.generate_image(prompt, _confined_path(out_path), aspect=aspect)
    return {"path": str(path), "estimated_cost_usd": creative_gen.COST_IMAGE}


@mcp.tool()
def generate_video(prompt: str, out_path: str, duration: int = 8, aspect: str = "9:16") -> dict:
    """Generate an ad video with AI. COSTS about $0.60 to $1.20 and is gated by
    ADKIT_ALLOW_SPEND. Uses the Fast model. out_path must be inside the
    creatives directory."""
    _require_spend_opt_in("generate_video")
    from . import creative_gen
    path = creative_gen.generate_video(prompt, _confined_path(out_path), duration=duration, aspect=aspect)
    return {"path": str(path), "estimated_cost_usd": creative_gen.COST_VIDEO.get(duration, 1.20)}


@mcp.tool()
def activate_ad(ad_id: str) -> dict:
    """Make an ad deliver. THIS STARTS AD SPEND. Gated by ADKIT_ALLOW_SPEND.
    A Meta ad only serves when the ad, its ad set, AND its campaign are all
    ACTIVE, so this activates the whole delivery chain for this ad; other ads in
    the ad set stay PAUSED. Returns which objects were activated."""
    _require_spend_opt_in("activate_ad")
    return core.activate_delivery(ad_id)


@mcp.tool()
def pause_ad(ad_id: str) -> dict:
    """Set an ad to PAUSED (stops spend). Safe."""
    return core.set_ad_status(ad_id, "PAUSED")


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
