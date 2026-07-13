<h1 align="center">adkit</h1>

<p align="center">
  <b>Plug-and-play Meta (Facebook + Instagram) ads automation.</b><br>
  Drive your entire ad chain from the terminal or from Claude Code, with AI-generated creative. Bring your own keys.
</p>

<p align="center">
  <code>verify</code> · <code>targeting</code> · <code>generate</code> · <code>campaign</code> · <code>adset</code> · <code>creative</code> · <code>ad</code> · <code>leadform</code> · <code>automate</code>
</p>

---

Launching Meta ads through the Marketing API is fiddly: tokens and scopes, the Page to Instagram link, targeting IDs, creative uploads, the campaign to ad-set to creative to ad chain, and the ever-present risk of accidentally spending money. adkit turns that into a handful of clean commands, plus one command that builds a whole campaign from a single brief file. It is safe by default: every object is created **PAUSED**, and the end-to-end automation is **dry-run** until you explicitly say go.

It also plugs straight into **Claude Code**, so you can run your ads by talking to an agent, with cost and safety guardrails built in.

## Why adkit

- **One brief, one command.** Describe a campaign in YAML and `adkit automate launch` builds the campaign, ad sets, creatives, and ads for you.
- **AI creative, cost-aware.** Generate feed images and Reels videos with `adkit generate`, with a running spend log so you always know what a run cost.
- **Safe by construction.** Objects are created PAUSED. The one command that spends (`ad activate`) and the ones that generate media are the only ones that cost anything, and they say so.
- **Bring your own keys, keep them yours.** Every secret is read from a local `.env` that is gitignored. Nothing sensitive is ever committed. See [SECURITY.md](SECURITY.md).
- **Claude Code native.** Ships a skill and slash commands so an agent can drive it end to end.

## Install

```bash
git clone https://github.com/your-org/adkit
cd adkit
pip install -e ".[yaml]"      # yaml extra enables YAML briefs; JSON works without it
cp .env.example .env          # then fill in your own values (never commit .env)
```

You need a Meta app with a token that has ads and pages scopes, an ad account, and a Page linked to an Instagram account. Walkthrough: [docs/setup-token.md](docs/setup-token.md).

For AI creative generation you also need a `GEMINI_API_KEY` and the [gemskills](https://github.com/b-open-io/gemskills) toolkit. That part is optional; the ad automation works without it.

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

# 5. When you are ready to spend, flip an ad on:
adkit ad activate --ad-id <id>
```

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

## Drive it from Claude Code

adkit ships a `.claude/` folder with a skill and two slash commands, so an agent can operate your account with the same guardrails:

- `/launch-campaign <plain-language brief>` drafts a brief, dry-runs it, and waits for your go.
- `/make-creative <description>` writes a prompt, tells you the cost, and generates the asset.

The skill teaches Claude the golden rules: read-only commands are free, creation is PAUSED and safe, and only `ad activate` and `generate` cost money or go live. More in [docs/claude-code.md](docs/claude-code.md).

## Commands

| Command | What it does |
| --- | --- |
| `adkit verify` | Check token validity, scopes, Page to Instagram link, ad account. |
| `adkit targeting search` | Look up interest and job-title IDs from Meta's taxonomy. |
| `adkit generate image \| video \| spend` | Generate AI creative and see spend. |
| `adkit campaign create \| list` | Create and list campaigns. |
| `adkit adset create \| list` | Create ad sets with targeting. |
| `adkit creative create \| list` | Build image or video creatives. |
| `adkit ad create \| activate \| pause \| list` | Build and toggle ads. |
| `adkit leadform create \| list` | Create Instant Forms for lead-gen. |
| `adkit automate launch` | Build a whole campaign from a brief (dry run unless `--go`). |

## Safety model

- **Nothing spends by accident.** Campaigns, ad sets, and ads are all created PAUSED. Ad delivery starts only when you run `adkit ad activate`.
- **Dry run by default.** `automate launch` prints the plan and writes nothing until `--go`.
- **Costs are surfaced.** `generate` prints an estimate before it runs and logs every call to `creatives/.spend.log`.
- **Secrets stay local.** All credentials come from `.env` (gitignored). See [SECURITY.md](SECURITY.md).

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). adkit is MIT licensed.

## Acknowledgements

AI creative generation is powered by [gemskills](https://github.com/b-open-io/gemskills) (Gemini images and Veo video). Built by people who got tired of clicking through Ads Manager.
