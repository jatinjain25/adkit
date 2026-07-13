# Contributing to adkit

Thanks for helping make Meta ads automation less painful.

## Setup

```bash
git clone https://github.com/jatinjain25/adkit
cd adkit
python -m venv .venv && source .venv/bin/activate
pip install -e ".[yaml]"
cp .env.example .env   # fill in your own sandbox credentials
```

## Ground rules

- **Never commit a secret.** Real credentials live only in `.env`, which is
  gitignored. Before pushing, run the scan in [SECURITY.md](SECURITY.md).
- **Keep it safe by default.** New create paths must default to PAUSED. Anything
  that spends money or generates paid media must announce it and, in the agent
  flow, prompt.
- **One HTTP surface.** Route Graph calls through `adkit/graph.py`.
- **Style.** Match the existing Click patterns. Do not use em dashes in code,
  comments, or docs; use commas, colons, or parentheses.

## Adding a command

Create `adkit/commands/<name>.py` with a Click group, register it in
`adkit/cli.py`, and add a row to the command table in `README.md`.

## Testing a change

adkit talks to a live API, so test against a sandbox ad account or with objects
created PAUSED, and clean them up after. `adkit verify` is a good first check
that your environment is wired correctly. `adkit automate launch` without `--go`
exercises the brief parser and planning without writing anything.

## Pull requests

Keep them focused. Describe what changed and how you verified it. Screenshots of
CLI output are welcome.
