# Changelog

All notable changes to adkit are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and adkit uses semantic
versioning.

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
