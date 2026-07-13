# X / Twitter launch thread

Build-in-public thread. Lead with the pain, not the feature list. Post the demo
GIF/screenshot on tweet 1 or 2 for reach. Swap in your handle where noted.

---

**1/**
Launching Meta ads through the API is a nightmare: access tokens, a dozen
scopes, the Page-to-Instagram link, targeting IDs, creative uploads, and the
whole campaign -> ad set -> creative -> ad chain. One wrong field and you're
either broken or spending money you didn't mean to.

So I built adkit.

**2/**
adkit turns that mess into a handful of clean commands, plus one that builds a
whole campaign from a single YAML brief.

It's safe by construction: every object is created PAUSED, and the end-to-end
automation is a dry run until you explicitly say --go. Nothing spends by accident.

**3/**
You can try the whole flow in 30 seconds with no Meta account and no API keys:

    pipx install meta-adkit
    adkit demo

It prints exactly what it would build. Writes nothing. Costs nothing.

[attach: screenshot/GIF of `adkit demo` output]

**4/**
The part I'm most into: it's Claude Code / MCP native.

Point an agent at it and say "launch a US traffic campaign for my landing page."
It researches targeting, drafts the brief, dry-runs it, and waits for your go.
Spend and delivery are gated so an agent literally cannot spend without an
explicit opt-in.

**5/**
One brief, one command:

    adkit automate launch --brief brief.yaml --go

Campaign, ad sets, creatives, ads: all built, all PAUSED. Re-run it and it
reuses what already exists instead of duplicating. When you're ready:

    adkit ad activate --ad-id <id>   # flips the whole delivery chain live

**6/**
It's open source (MIT), bring-your-own-keys, nothing sensitive ever leaves your
machine. AI creative (Gemini images + Veo video) is optional and cost-logged.

Repo: https://github.com/jatinjain25/adkit
`pip install meta-adkit`

Built by @YOUR_HANDLE. Stars and brutal feedback both welcome.
