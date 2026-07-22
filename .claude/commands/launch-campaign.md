---
description: Draft and dry-run a Meta ad campaign with adkit from a plain-language brief
---

The user wants to launch a Meta ad campaign. Their request:

$ARGUMENTS

Do this:

1. Run `adkit verify` and confirm the account is healthy. If not, stop and
   explain what to fix.
2. Research the market first: `adkit research --keyword "<category>" --country <cc>`
   to see the winning ads and angles. You can seed the brief directly with
   `adkit research ... --seed-brief briefs/<slug>.yaml`. If Ad Library access
   isn't set up, note it and continue.
3. If the brief implies specific interests, run `adkit targeting search` to find
   the interest IDs.
4. Write (or refine the seeded) brief at `briefs/<slug>.yaml` following
   `examples/briefs/example.yaml`: campaign objective and budget, one ad set per
   audience with targeting, and one or more ads with copy informed by the
   research and a `link` (or a `generate` block if they want AI creative).
4. Run `adkit automate launch --brief briefs/<slug>.yaml` (dry run) and show the
   plan.
5. Ask the user to confirm with a plain "go" before you run it with `--go`.
   Remind them creative generation (if any) costs a few cents to ~$1.20 per asset
   and that all objects are created PAUSED.
