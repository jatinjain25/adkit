# Changelog

All notable changes to adkit are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and adkit uses semantic
versioning.

## [Unreleased]

### Added
- `adkit research`: competitive research via Meta's official Ad Library API. Pulls
  competitor ads for a keyword + country, ranks advertisers by longevity x variant
  count (the honest proxy, since Meta hides spend for commercial ads), and
  summarizes winning hooks, offers, CTAs, and placements. This is the front of the
  flow (Research → Brief → Creative → Build → Launch → Optimize). Uses the
  sanctioned API, never scraping.
- `adkit research --seed-brief <file>`: writes a starter brief seeded from the
  winning patterns (dominant CTA, recurring themes, a `generate:` creative prompt,
  and competitor snapshot links to study), connecting research directly to creative.
- Research-first nudges: `adkit generate` and `adkit automate` print a one-line,
  suppressible reminder (`ADKIT_NO_TIPS=1`) to research before making creatives when
  none was run recently; the Claude Code skill, slash commands, and onboarding now
  put research as step one.

## [0.1.1]

Security and reliability hardening.

### Security
- The Meta access token now travels in the `Authorization: Bearer` header
  instead of the URL query string, and every error path scrubs the token, so it
  cannot leak into tracebacks, proxy logs, or CI output.
- The MCP server refuses money or live actions (`activate_ad`, `generate_image`,
  `generate_video`, `launch_brief(go=True)`) unless `ADKIT_ALLOW_SPEND=1` is set
  in the server environment. Enforced server-side.
- New `ADKIT_GENERATION_DAILY_CAP_USD` sets a hard daily ceiling on AI
  generation spend, across the CLI and MCP.
- MCP file tools are confined to the creatives working directory, blocking path
  traversal (arbitrary file read/write).
- Added a threat model and supply-chain section to SECURITY.md.

### Added
- Security regression tests (token header, token scrubbing, spend gate, path
  confinement, daily cap).

## [0.1.0]

First public release.

### Added
- CLI for the Meta Marketing API: `verify`, `targeting`, `campaign`, `adset`,
  `creative`, `ad`, `leadform`.
- Importable core library (`adkit.core`): every operation is a plain function
  that returns data, so other Python code can build on adkit.
- AI creative generation (`adkit generate image|video|spend`) via gemskills,
  with a local spend log.
- End-to-end automation (`adkit automate launch --brief`) that builds a whole
  campaign from one YAML or JSON brief. Dry run by default.
- MCP server (`adkit-mcp`) exposing the operations as tools for any agent.
- Claude Code integration: a skill, `/launch-campaign` and `/make-creative`
  slash commands, a permission allowlist, and a plugin manifest.
- Docs (setup, Claude Code, architecture), examples, MIT license.

### Safety
- All created objects default to PAUSED; automation is dry-run until `--go`.
- No secrets in the repo: `.env` is gitignored, only `.env.example` is tracked.
