# Driving adkit from Claude Code

adkit ships a `.claude/` folder so you can run your ad account by talking to an
agent, with the same safety guardrails as the CLI.

## What ships

- `.claude/skills/adkit/SKILL.md`: teaches Claude how adkit works and the rules
  it must follow (read-only commands are free; creation is PAUSED and safe; only
  `ad activate` and `generate` cost money or go live; never print secrets).
- `.claude/commands/launch-campaign.md`: the `/launch-campaign` slash command.
- `.claude/commands/make-creative.md`: the `/make-creative` slash command.
- `.claude/settings.json`: a permission allowlist so read-only commands run
  without prompts, while spending and generation always ask first.

## Setup

1. Install adkit so the `adkit` command is on your PATH (`pip install -e .`).
2. Fill in `.env`.
3. Open this repo in Claude Code. The skill and commands are picked up from the
   `.claude/` folder automatically.

## Try it

```
/launch-campaign a lead-gen campaign in the US for a developer tool,
two ad sets (AI engineers, and technical founders), $50/day, send them to our docs
```

Claude will run `adkit verify`, search targeting, draft a brief, dry-run it with
`adkit automate launch`, show you the plan, and wait for your plain-text "go"
before building anything. Everything it creates is PAUSED.

```
/make-creative a dark, terminal-style Instagram ad with the headline
"Stop building retrieval from scratch"
```

Claude writes a prompt, tells you the estimated cost, and on your go runs
`adkit generate image`, then reports the file and running spend.

## Why it is safe to hand to an agent

The dangerous actions are few and explicit. Creating campaigns, ad sets,
creatives, and ads never spends, because they are PAUSED. The only commands that
cost money are `adkit ad activate` (starts delivery) and `adkit generate` /
`automate launch --go` (creative generation), and the settings file makes both
prompt for confirmation.
