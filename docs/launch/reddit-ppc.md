# Reddit (r/PPC, r/marketing, r/FacebookAds)

These subs dislike self-promo that reads like an ad. Lead with the tool as a
utility, be honest it's free/open-source, and invite critique. Check each sub's
self-promotion rules first. Don't cross-post the identical text; lightly reword.

---

## Title

I built a free, open-source CLI to run Meta ads from the terminal (and from AI agents) - safe by default

## Body

I do a lot of Meta lead-gen and got tired of the API busywork: tokens and
scopes, the Page/Instagram link, targeting IDs, creative uploads, and building
the campaign -> ad set -> ad chain by hand, always one wrong field away from
spending money I didn't mean to.

So I made adkit, a small open-source tool that turns that into a few commands,
plus one that builds a whole campaign from a single YAML brief.

The two things that might be useful to this sub:

- Nothing spends by accident. Everything is created PAUSED and the automation is
  a dry run until you explicitly confirm. Going live is one command that flips
  the whole delivery chain on.
- You can drive it from an AI agent (Claude Code / Cursor via MCP) with spend
  and delivery gated behind an explicit opt-in, so the agent can't burn budget.

You can see the entire flow with no account and no keys: `pipx install meta-adkit`
then `adkit demo` prints the campaign it would build and writes nothing.

It's MIT-licensed and bring-your-own-keys. It's early (v0.1) and focused on
lead-gen and traffic objectives right now, so I'd genuinely value feedback from
people who run more volume than I do - especially on the targeting builder and
the brief format.

Repo: https://github.com/jatinjain25/adkit

Not selling anything; there's no paid tier. Happy to answer questions in the
comments.
