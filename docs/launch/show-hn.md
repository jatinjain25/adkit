# Show HN

Post from your own account. HN rewards honesty and specifics; be upfront about
scope and what it doesn't do. Reply fast in the first hour.

---

## Title

Show HN: adkit – Drive Meta (FB/Instagram) ads from the terminal or Claude Code

## URL

https://github.com/jatinjain25/adkit

## Text

Launching Meta ads through the Marketing API is a slog: access tokens and
scopes, linking the Page to Instagram, looking up targeting IDs, uploading
creative, and wiring the campaign -> ad set -> creative -> ad chain by hand. And
the whole time you're one wrong field away from spending real money.

adkit turns that into a few clean commands, plus one that builds an entire
campaign from a single YAML brief. Two design choices I cared about most:

- Safe by construction. Every object is created PAUSED. The end-to-end
  automation is a dry run until you pass --go. The only actions that spend money
  or start delivery announce it, and (over MCP) are refused unless the operator
  sets ADKIT_ALLOW_SPEND=1, so an auto-approving agent or a prompt injection
  can't spend on your behalf.
- One implementation, three front ends. Every operation is a plain function in
  adkit.core; the CLI, the MCP server, and the brief automation are thin layers
  over it.

You can see the whole flow with no account and no keys:

    pipx install meta-adkit
    adkit demo

It prints the campaign it would build and writes nothing.

It's also MCP-native, so you can drive it from Claude Code or Cursor: the agent
researches targeting, drafts a brief, dry-runs it, and waits for your go.

Honest about scope: it's a solo, early (v0.1) project focused on lead-gen and
traffic campaigns. It does single-shot video uploads (fine for short Reels), no
conversions/pixel objectives yet, and no analytics. AI creative generation
(Gemini images + Veo video) is optional and logs estimated spend locally; the
authoritative number is always your provider dashboard.

MIT licensed, bring-your-own-keys, nothing sensitive is committed. I built it
because I got tired of clicking through Ads Manager. Feedback and PRs very
welcome, especially on the safety model and the brief format.
