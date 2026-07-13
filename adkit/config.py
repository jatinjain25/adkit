import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


load_env()

GRAPH_HOST = "https://graph.facebook.com"
GRAPH_VERSION = os.environ.get("META_API_VERSION", "v21.0")


def require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(
            f"Missing required env var: {name}. Set it in .env (see .env.example)."
        )
    return val


def optional(name: str) -> str | None:
    val = os.environ.get(name)
    return val if val else None


def ad_account(override: str | None = None) -> str:
    """Resolve the target ad account: --account override, else META_AD_ACCOUNT_ID.

    Accepts a bare id or an act_-prefixed id and always returns the act_ form.
    """
    val = (override or os.environ.get("META_AD_ACCOUNT_ID") or "").strip()
    if not val:
        raise SystemExit(
            "No ad account. Pass --account act_<id> (or a bare id) "
            "or set META_AD_ACCOUNT_ID in .env."
        )
    return val if val.startswith("act_") else f"act_{val}"


def page(override: str | None = None) -> str:
    """Resolve the target Page: --page override, else META_PAGE_ID."""
    val = (override or os.environ.get("META_PAGE_ID") or "").strip()
    if not val:
        raise SystemExit("No Page. Pass --page <id> or set META_PAGE_ID in .env.")
    return val


def ig_actor(override: str | None = None) -> str | None:
    """Resolve the Instagram actor: --ig-actor override, else META_INSTAGRAM_ACTOR_ID."""
    val = (override or os.environ.get("META_INSTAGRAM_ACTOR_ID") or "").strip()
    return val or None
