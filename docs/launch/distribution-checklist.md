# Distribution checklist

Do these in order. The first two are the make-or-break gates; everything after is
reach. Nothing here is automated for you - each is an action you take.

## 0. Publish (must happen first)

- [ ] On pypi.org: Account -> Publishing -> add a **pending trusted publisher**
      for project `meta-adkit`, repo `jatinjain25/adkit`, workflow `publish.yml`,
      environment `pypi`.
- [ ] Push all changes to `main`; confirm CI is green.
- [ ] Create a GitHub Release with tag `v0.1.2` -> the `publish.yml` workflow
      publishes to PyPI automatically (no token needed).
- [ ] Verify on a clean machine: `pipx install meta-adkit && adkit demo`.
      This is the single most important check. If it fails, stop and fix.

## 1. Make the repo landing page sell

- [ ] Add a short demo GIF of `adkit demo` (and one of the agent flow) to the top
      of the README. A moving picture converts far better than text.
- [ ] Set the GitHub repo description and topics: `meta-ads`, `facebook-ads`,
      `mcp`, `claude-code`, `cli`, `marketing-automation`, `ai`.
- [ ] Pin the repo on your GitHub profile.

## 2. Seed the MCP discovery channels (high-intent audience)

- [ ] **awesome-mcp-servers** (github.com/punkpeye/awesome-mcp-servers): open a PR
      adding one line under the marketing/ads or "Other" category. Suggested entry:

      - [adkit](https://github.com/jatinjain25/adkit) - Drive Meta (Facebook + Instagram) ads: research targeting, generate AI creative, and launch whole campaigns from a brief. Safe by default (everything PAUSED, spend gated).

- [ ] **GitHub MCP Registry** (github.com/modelcontextprotocol/registry): follow
      the current submission process in that repo's README to list the `adkit`
      server. Reuse the one-line description above.
- [ ] Submit to any "MCP servers" directories you use (Glama, mcp.so, etc.) with
      the same blurb.

## 3. Tell the story (see the other files in this folder)

- [ ] Post the X thread (`x-thread.md`). Lead with the pain, attach the demo GIF.
- [ ] Post Show HN (`show-hn.md`) early on a weekday; be around to reply for the
      first couple of hours.
- [ ] Post to r/PPC and r/marketing (`reddit-ppc.md`), reworded per sub; read
      each sub's self-promo rules first.
- [ ] Send it to your own newsletter/Substack audience.

## 4. After launch

- [ ] Triage issues/PRs quickly for the first week; responsiveness is the
      strongest reputation signal there is.
- [ ] Add a `CHANGELOG` entry for each release and keep cutting GitHub Releases so
      publishing stays one click.
