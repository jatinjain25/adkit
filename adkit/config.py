import os
from pathlib import Path

# Where the repo-local .env lives when you run adkit from a clone. This is only
# one of several places we look; see find_env_file().
_REPO_ENV = Path(__file__).resolve().parent.parent / ".env"


def _candidate_env_paths() -> list[Path]:
    """Places to look for a .env, in priority order.

    The whole point: a `pipx`/plugin install has no repo, so the token must be
    discoverable from wherever the user actually runs `adkit`. We look in the
    current directory and its parents first (project-local config), then a
    user-level config dir, then the repo copy (for people hacking on adkit).
    An explicit ADKIT_ENV always wins.
    """
    paths: list[Path] = []
    explicit = os.environ.get("ADKIT_ENV")
    if explicit:
        paths.append(Path(explicit).expanduser())

    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        paths.append(directory / ".env")

    xdg = os.environ.get("XDG_CONFIG_HOME")
    config_home = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    paths.append(config_home / "adkit" / ".env")
    paths.append(Path.home() / ".adkit.env")

    paths.append(_REPO_ENV)
    return paths


def find_env_file() -> Path | None:
    """Return the first .env that exists, or None. Exposed so `adkit verify`
    (and users) can see which file adkit actually loaded."""
    for path in _candidate_env_paths():
        if path.is_file():
            return path
    return None


def _parse_env(path: Path) -> None:
    for line in path.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def load_env() -> None:
    path = find_env_file()
    if path is not None:
        _parse_env(path)


load_env()

GRAPH_HOST = "https://graph.facebook.com"
GRAPH_VERSION = os.environ.get("META_API_VERSION", "v21.0")


def require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        loaded = find_env_file()
        where = f"adkit loaded {loaded}" if loaded else "adkit found no .env file"
        raise SystemExit(
            f"Missing required setting: {name}.\n"
            f"{where}. adkit looks for .env in the current directory (and its "
            "parents), then ~/.config/adkit/.env; ADKIT_ENV=/path/to/.env overrides.\n"
            "Copy .env.example to one of those, fill in your values, and see "
            "docs/setup-token.md for how to get a Meta token.\n"
            "No account yet? Try `adkit demo` first, it needs no credentials."
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
