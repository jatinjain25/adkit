"""adkit: plug-and-play Meta Ads automation.

Use it three ways:
  * CLI:      `adkit ...` (see adkit.cli)
  * Library:  `from adkit import core` then call core.create_campaign(...) etc.
  * MCP:      `adkit-mcp` exposes the same operations as tools (see adkit.mcp_server)
"""

from . import core  # noqa: F401

__version__ = "0.1.0"
