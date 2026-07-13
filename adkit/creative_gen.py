"""AI creative generation: Gemini images and Veo videos, driven through the
gemskills toolkit.

Design goals:
  * Never read or embed a secret. The Gemini key comes only from the
    environment (GEMINI_API_KEY), the same place the rest of adkit reads config.
  * Fail with a clear, actionable message when a dependency is missing, instead
    of a stack trace.
  * Log every generation and its estimated cost to a local spend file so you
    always know what a run cost before you scale it.

This module shells out to the gemskills scripts (a small Bun toolkit). It does
not bundle model weights or call the model directly, which keeps adkit light and
lets gemskills own model selection.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config


class CreativeGenError(Exception):
    pass


# Rough per-call cost estimates (USD) used only for the local spend log. The
# authoritative number is always your provider dashboard.
COST_IMAGE = 0.15
COST_VIDEO = {4: 0.60, 6: 0.90, 8: 1.20}

FAST_VIDEO_MODEL = "veo-3.1-fast-generate-preview"
QUALITY_VIDEO_MODEL = "veo-3.1-generate-preview"


def _bun() -> str:
    candidate = os.environ.get("BUN") or str(Path.home() / ".bun/bin/bun")
    if Path(candidate).is_file():
        return candidate
    found = shutil.which("bun")
    if found:
        return found
    raise CreativeGenError(
        "bun not found. Install it with: curl -fsSL https://bun.sh/install | bash\n"
        "or point BUN at the binary in your .env."
    )


def _gemskills_root() -> Path:
    root = Path(
        os.environ.get("GEMSKILLS_ROOT") or (Path.home() / "dev/gemskills")
    ).expanduser()
    if not root.is_dir():
        raise CreativeGenError(
            f"gemskills not found at {root}. Clone it once with:\n"
            "  git clone https://github.com/b-open-io/gemskills ~/dev/gemskills\n"
            "  cd ~/dev/gemskills && bun install\n"
            "or set GEMSKILLS_ROOT in your .env."
        )
    return root


def _spend_log_path() -> Path:
    out_dir = Path(os.environ.get("ADKIT_CREATIVE_DIR") or (Path.cwd() / "creatives"))
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / ".spend.log"


def _log_spend(kind: str, cost: float, out: Path) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} {kind} ${cost:.2f} {out}\n"
    with _spend_log_path().open("a") as fh:
        fh.write(line)


def _today_spend() -> float:
    """Sum today's logged generation spend (UTC), from the local spend log."""
    path = _spend_log_path()
    if not path.exists():
        return 0.0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = 0.0
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].startswith(today) and parts[2].startswith("$"):
            try:
                total += float(parts[2][1:])
            except ValueError:
                pass
    return total


def _enforce_daily_cap(pending_cost: float) -> None:
    """If ADKIT_GENERATION_DAILY_CAP_USD is set, refuse a generation that would
    push today's total generation spend over the cap. Applies to every path
    (CLI and MCP), so it is a hard local ceiling on generation cost."""
    raw = os.environ.get("ADKIT_GENERATION_DAILY_CAP_USD", "").strip()
    if not raw:
        return
    try:
        cap = float(raw)
    except ValueError:
        raise CreativeGenError(f"ADKIT_GENERATION_DAILY_CAP_USD is not a number: {raw!r}")
    spent = _today_spend()
    if spent + pending_cost > cap:
        raise CreativeGenError(
            f"Daily generation cap reached: ${spent:.2f} spent today, this call adds "
            f"~${pending_cost:.2f}, cap is ${cap:.2f}. Raise ADKIT_GENERATION_DAILY_CAP_USD "
            "or wait until tomorrow (UTC)."
        )


def _run(script: Path, args: list[str], extra_env: dict[str, str]) -> None:
    env = dict(os.environ)
    env["GEMINI_API_KEY"] = config.require("GEMINI_API_KEY")
    env["GEMSKILLS_ROOT"] = str(_gemskills_root())
    env.update(extra_env)
    root = _gemskills_root()
    cmd = [_bun(), "run", "--cwd", str(root), str(script), *args]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CreativeGenError(
            f"generation failed (exit {proc.returncode}).\n"
            f"stderr:\n{proc.stderr.strip()[:1500]}"
        )


def generate_image(
    prompt: str,
    out: Path,
    *,
    aspect: str = "1:1",
    size: str = "2K",
) -> Path:
    """Generate a still image from a text prompt. Returns the output path."""
    _enforce_daily_cap(COST_IMAGE)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    script = _gemskills_root() / "skills/generate-image/scripts/generate.ts"
    _run(
        script,
        [prompt, "--aspect", aspect, "--size", size, "--output", str(out)],
        extra_env={},
    )
    _log_spend("image", COST_IMAGE, out)
    return out


def generate_video(
    prompt: str,
    out: Path,
    *,
    image: Path | None = None,
    duration: int = 8,
    aspect: str = "9:16",
    resolution: str = "720p",
    fast: bool = True,
) -> Path:
    """Generate a video from a prompt (optionally seeded by an image).

    fast=True uses the Veo Fast model (cheaper, the default). Set fast=False for
    the higher-fidelity model only when a draft has already validated the shot.
    Returns the output path.
    """
    cost = COST_VIDEO.get(duration, COST_VIDEO[8])
    _enforce_daily_cap(cost)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    script = _gemskills_root() / "skills/generate-video/scripts/generate.ts"
    args = [
        prompt,
        "--aspect", aspect,
        "--resolution", resolution,
        "--duration", str(duration),
        "--output", str(out),
    ]
    if image:
        args += ["--input", str(Path(image).resolve())]
    model = FAST_VIDEO_MODEL if fast else QUALITY_VIDEO_MODEL
    _run(script, args, extra_env={"GEMINI_VIDEO_MODEL": model})
    _log_spend(f"video-{duration}s{'-fast' if fast else ''}", cost, out)
    return out


def spend_summary() -> str:
    """Human-readable summary of logged generation spend."""
    path = _spend_log_path()
    if not path.exists():
        return "No creative spend logged yet."
    total = 0.0
    lines = path.read_text().splitlines()
    for line in lines:
        parts = line.split()
        if len(parts) >= 3 and parts[2].startswith("$"):
            try:
                total += float(parts[2][1:])
            except ValueError:
                pass
    recent = "\n".join(lines[-10:])
    return (
        f"Logged creative spend: ${total:.2f} over {len(lines)} calls\n"
        f"Authoritative usage: https://aistudio.google.com/apikey (Usage tab)\n"
        f"Recent:\n{recent}"
    )
