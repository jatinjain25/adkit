<h1 align="center">adkit</h1>

<p align="center">
  <b>Plug-and-play Meta (Facebook + Instagram) ads automation.</b><br>
  Drive your entire ad chain from the terminal or from Claude Code, with AI-generated creative. Bring your own keys.
</p>

<p align="center">
  <code>verify</code> · <code>targeting</code> · <code>generate</code> · <code>campaign</code> · <code>adset</code> · <code>creative</code> · <code>ad</code> · <code>leadform</code> · <code>automate</code>
</p>

<p align="center">
  <a href="https://github.com/jatinjain25/adkit/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/jatinjain25/adkit/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green">
</p>

---

Launching Meta ads through the Marketing API is fiddly: tokens and scopes, the Page to Instagram link, targeting IDs, creative uploads, the campaign to ad-set to creative to ad chain, and the ever-present risk of accidentally spending money. adkit turns that into a handful of clean commands, plus one command that builds a whole campaign from a single brief file. It is safe by default: every object is created **PAUSED**, and the end-to-end automation is **dry-run** until you explicitly say go.

It also plugs straight into **Claude Code**, so you can run your ads by talking to an agent, with cost and safety guardrails built in.

## The adkit flow

adkit is the whole journey of automating an ad, one command per step:

**Research** competitors → write a **Brief** → generate **Creative** → **Build** the campaign → **Launch** it → **Optimize** what runs.

```
research  →  init / brief  →  generate  →  automate  →  ad activate  →  optimize
```

## Try it in 30 seconds (no account needed)

```bash
pipx install meta-adkit     # or: pip install meta-adkit
adkit demo
```

`adkit demo` prints the exact plan adkit would build from a brief. It writes nothing, calls nothing, and needs no Meta account or API keys, so you can see the whole flow before you set anything up:

```
=== adkit demo [DRY RUN] ===
objective=OUTCOME_TRAFFIC
campaign: Example | TOF | Traffic
  adset: Agent builders  budget=2500 (minor units)
    ad: Expensive chatbot  [image]  cta=LEARN_MORE
    ad: Buy vs build  [image]  cta=SIGN_UP
```

When you're ready to run it on a real account, `adkit init my-brief.yaml` writes a starter brief and `adkit verify` walks you through connecting Meta.

> The command is `adkit`; the PyPI package is `meta-adkit` (the name `adkit` was already taken).

## Why adkit

- **One brief, one command.** Describe a campaign in YAML and `adkit automate launch` builds the campaign, ad sets, creatives, and ads for you.
- **AI creative, cost-aware.** Generate feed images and Reels videos with `adkit generate`, with a running spend log so you always know what a run cost.
- **Safe by construction.** Objects are created PAUSED. The one command that spends (`ad activate`) and the ones that generate media are the only ones that cost anything, and they say so.
- **Bring your own keys, keep them yours.** Every secret is read from a local `.env` that is gitignored. Nothing sensitive is ever committed. See [SECURITY.md](SECURITY.md).
- **Claude Code native.** Ships a skill and slash commands so an agent can drive it end to end.

## Install

Pick whichever fits how you want to use it.

**As a command-line tool** (isolated, recommended):

```bash
pipx install "meta-adkit[yaml]"     # or: uvx --from "meta-adkit[yaml]" adkit --help
```

**As a library or to hack on it:**

```bash
git clone https://github.com/jatinjain25/adkit
cd adkit
pip install -e ".[dev]"             # dev extra = yaml + mcp + pytest + ruff
```

**As a Claude Code plugin** (adds the slash commands, skill, and MCP server in one step):

```bash
# in Claude Code
/plugin marketplace add jatinjain25/adkit
/plugin install adkit
```

## Connect your Meta account (when you're ready to go live)

Everything above works with no account. To build on a real ad account, configure your credentials once:

```bash
cp .env.example .env                # fill in your own values, never commit .env
```

adkit looks for `.env` in your current directory (and its parents), then in
`~/.config/adkit/.env`, so it works the same whether you installed from a clone,
via `pipx`, or as a Claude Code plugin. Put a `.env` in the project you run adkit
from, or a user-wide one at `~/.config/adkit/.env`. `ADKIT_ENV=/path/to/.env`
overrides everything. `adkit verify` prints which file it loaded.

You need a Meta app with a token that has ads and pages scopes, an ad account, and a Page linked to an Instagram account. Walkthrough: [docs/setup-token.md](docs/setup-token.md).

For AI creative generation you also need a `GEMINI_API_KEY` and the [gemskills](https://github.com/b-open-io/gemskills) toolkit. That part is optional; the ad automation works without it. To run adkit as an MCP server, install the `mcp` extra: `pipx install "meta-adkit[mcp]"`, then point your agent at the `adkit-mcp` command.

## 60-second tour

```bash
# 1. Confirm your credentials, scopes, IG link, and ad account are healthy
adkit verify

# 2. Find targeting IDs
adkit targeting search "LangChain"
adkit targeting search "CTO" --type adworkposition

# 3. Generate a creative (prints the ~cost first; logs spend)
adkit generate image "Dark developer-brand ad, bold headline 'Give your AI a memory'" \
  --out creatives/hook.png --aspect 1:1

# 4. Launch a whole campaign from a brief. Dry run first (writes nothing):
adkit automate launch --brief examples/briefs/example.yaml
# Then build it for real. Everything is created PAUSED:
adkit automate launch --brief examples/briefs/example.yaml --go

# 5. When you are ready to spend, go live. This flips the ad AND its parent
#    ad set and campaign to ACTIVE (all three must be active to deliver):
adkit ad activate --ad-id <id>
```

## Research competitors first

Before you build anything, see what already works in your market:

```bash
adkit research --keyword "edtech" --country IN
```

adkit pulls matching ads from Meta's **official Ad Library API** (not scraping, which violates Meta's Terms), then ranks advertisers by **how long and how widely they run** their ads. Meta does not expose impressions or spend for commercial ads, so longevity and variant count are the honest proxy: advertisers kill losers fast, so a long-running, heavily-varied ad is almost certainly a winner. You get the winning advertisers, their longest-running ads (with snapshot links to view), and the common hooks, offers, CTAs, and placements, so you can design your ad from what's proven.

Turn the findings straight into a starter brief, so research feeds your creative:

```bash
adkit research --keyword "edtech" --country IN --seed-brief edtech.yaml
# then edit the copy and: adkit automate launch --brief edtech.yaml
```

Research is meant to come **before you make creatives**. `adkit generate` and `automate` print a gentle one-line reminder if you haven't researched recently (silence it with `ADKIT_NO_TIPS=1`), and the Claude Code skill runs research as step one.

First use requires a one-time identity confirmation and terms acceptance at [facebook.com/ads/library/api](https://www.facebook.com/ads/library/api); adkit tells you if it's not set up yet. API coverage of non-EU commercial ads can be sparse; the public Ad Library website is the manual fallback.

## The brief

A brief is a declarative description of a campaign. adkit reads it top to bottom and creates each object, optionally generating the creative first.

```yaml
campaign:
  name: "Example | TOF | Traffic"
  objective: OUTCOME_TRAFFIC
  daily_budget: 5000            # minor units: 5000 = $50.00
adsets:
  - name: "Agent builders"
    daily_budget: 2500
    countries: [US, GB, CA]
    interest_ids: []            # from `adkit targeting search`
    ads:
      - name: "Expensive chatbot"
        message: "Your agent forgets every user. Add memory in one API call."
        headline: "Give your product a memory"
        link: "https://example.com"
        cta: LEARN_MORE
        image: "creatives/hook.png"
        # or generate it on the fly:
        # generate: { type: image, prompt: "...", aspect: "1:1" }
```

Full example with comments: [examples/briefs/example.yaml](examples/briefs/example.yaml).

## Optimize live ads (kill losers, scale winners)

Once ads are delivering, `adkit optimize report` pulls each ad's performance and tells you, in plain language, what to do — without touching anything:

```bash
# Lead-gen: judge on cost per QUALIFIED lead (pulls the form's leads and scores quality)
adkit optimize report --target-cpl 3.00 --lead-form-id <form_id>

# Marketing: judge on ROAS from revenue you supply
adkit optimize report --revenue <ad_id>=480 --target-roas 2.0
```

Each ad comes back as **KILL** (over target, draining budget), **SCALE** (a winner worth more budget), **KEEP**, or **WAIT** — and it will never judge an ad still in Meta's learning phase (the 2-3 day / budget window is a policy default). The report prints the exact command to enact each call. Nothing changes until you run it:

```bash
adkit optimize apply --ad-id <id> --action pause --yes    # stop a loser
adkit optimize apply --ad-id <id> --action scale --yes    # raise the winner's ad set budget
```

**Build your own logic.** The decision engine is a pure, importable function with an overridable policy — swap the thresholds or the whole function; the CLI and the agent use whatever you set:

```python
from adkit.optimize import EvaluationPolicy, evaluate_account

policy = EvaluationPolicy(target_cpl=3.00, min_days_before_judging=3, scale_budget_pct=30)
report = evaluate_account(policy=policy, lead_form_id="<form_id>")
```

Lead quality is scored locally (implausible phone, disposable/invalid email, duplicates) and **lead PII is never written to disk, never printed unredacted, and never returned over MCP** — only aggregate counts. Pulling leads needs the `leads_retrieval` scope; `adkit verify` flags it if missing.

## Drive it from Claude Code

adkit ships a `.claude/` folder with a skill and two slash commands, so an agent can operate your account with the same guardrails:

- `/launch-campaign <plain-language brief>` drafts a brief, dry-runs it, and waits for your go.
- `/make-creative <description>` writes a prompt, tells you the cost, and generates the asset.

The skill teaches Claude the golden rules: read-only commands are free, creation is PAUSED and safe, and only `ad activate` and `generate` cost money or go live. More in [docs/claude-code.md](docs/claude-code.md).

## Use it as a library

Every operation is a plain function in `adkit.core`, so you can build adkit into your own code:

```python
from adkit import core

core.verify_credentials()                       # health check
ids = core.search_targeting("LangChain")         # find interest IDs
camp = core.create_campaign("My campaign", objective="OUTCOME_TRAFFIC")
core.launch_from_brief(brief_dict, go=True)      # or build a whole campaign
```

The CLI and the MCP server are both thin layers over these functions, so there is one implementation of each operation.

## Use it as an MCP server

Any MCP-capable agent (Claude Code, Cursor, Claude Desktop, or your own app) can drive adkit. Install the `mcp` extra so the `adkit-mcp` command exists:

```bash
pipx install "meta-adkit[mcp]"
```

**Claude Code** — one line:

```bash
claude mcp add adkit -- adkit-mcp
```

**Any MCP client** — drop this into your client's config (e.g. `~/.cursor/mcp.json`, or Claude Desktop's config):

```json
{
  "mcpServers": {
    "adkit": {
      "command": "adkit-mcp"
    }
  }
}
```

It exposes tools like `verify`, `search_targeting`, `create_campaign`, `launch_brief`, and `generate_image`. The tool descriptions carry the same safety notes: creation is PAUSED, and the tools that cost money or go live say so. Actions that spend money or start delivery (`activate_ad`, `generate_image`, `generate_video`, `launch_brief --go`) are refused unless the operator sets `ADKIT_ALLOW_SPEND=1` in the server's environment, so an auto-approving client or a prompt injection can't spend on your behalf.

## Commands

| Command | What it does |
| --- | --- |
| `adkit demo` | Dry-run the whole flow with no account or keys. Start here. |
| `adkit init [brief.yaml]` | Write a starter campaign brief you can edit. |
| `adkit research` | Research competitor ads in the Ad Library; rank winners by longevity. |
| `adkit verify` | Check token validity, scopes, Page to Instagram link, ad account. |
| `adkit targeting search` | Look up interest and job-title IDs from Meta's taxonomy. |
| `adkit generate image \| video \| spend` | Generate AI creative and see spend. |
| `adkit campaign create \| activate \| pause \| list` | Create, toggle, and list campaigns. |
| `adkit adset create \| activate \| pause \| list` | Create ad sets with targeting; toggle them. |
| `adkit creative create \| list` | Build image or video creatives. |
| `adkit ad create \| activate \| pause \| list` | Build ads; `activate` takes the whole ad→set→campaign chain live. |
| `adkit leadform create \| list` | Create Instant Forms for lead-gen. |
| `adkit automate launch` | Build a whole campaign from a brief (dry run unless `--go`). |
| `adkit optimize report` | Analyze live ads; recommend KILL/SCALE/KEEP. Read-only. |
| `adkit optimize apply` | Enact one recommendation (pause a loser / scale a winner). |

## Safety model

- **Nothing spends by accident.** Campaigns, ad sets, and ads are all created PAUSED. A Meta ad only delivers when the ad, its ad set, and its campaign are *all* ACTIVE, so `adkit ad activate` flips the whole chain live in one step (other ads in the set stay PAUSED). Use `--ad-only` to flip just the ad.
- **Dry run by default.** `automate launch` prints the plan and writes nothing until `--go`.
- **Costs are surfaced.** `generate` prints an estimate before it runs and logs every call to `creatives/.spend.log`.
- **Secrets stay local.** All credentials come from `.env` (gitignored). See [SECURITY.md](SECURITY.md).

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). adkit is MIT licensed.

## Acknowledgements

AI creative generation is powered by [gemskills](https://github.com/b-open-io/gemskills) (Gemini images and Veo video).

---

Built by [Jatin Jain](https://github.com/jatinjain25), who got tired of clicking through Ads Manager. If adkit saved you some clicks, a star helps others find it.
