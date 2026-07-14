---
name: adkit
description: Drive Meta (Facebook + Instagram) ads from Claude Code using the adkit CLI. Use when the user wants to research ad targeting, generate ad creative, create or list campaigns/ad sets/ads/lead forms, or launch a whole campaign from a brief. Covers verify, targeting, generate, campaign, adset, creative, ad, leadform, and automate.
---

# adkit: run Meta Ads from Claude Code

adkit is a Python CLI that wraps the Meta Marketing API and AI creative
generation. You (Claude) can operate the user's ad account safely because every
object is created PAUSED and the end-to-end automation is dry-run by default.

## Golden rules

1. **Never spend without explicit confirmation.** Creating objects is safe (they
   are PAUSED). Two actions actually cost money or go live: `adkit ad activate`
   (starts ad spend; it activates the ad AND its parent ad set and campaign,
   because all three must be ACTIVE for Meta to deliver) and `adkit generate` /
   `automate launch --go` (image and video generation cost a few cents to
   ~$1.20 each). Before either, state the cost or the fact that it goes live, and
   get a plain-text "go" from the user.
2. **Dry run first.** For `automate launch`, always run without `--go` and show
   the plan before proposing the real run.
3. **Read-only commands are free to run anytime:** `verify`, every `list`
   subcommand, and `targeting search`.
4. **Never print or ask for the access token or API keys.** They live in `.env`.

## First step, always

Run `adkit verify` to confirm the token, scopes, Page to Instagram link, and ad
account are healthy. If it reports missing scopes or an unlinked IG account,
fix that before anything else (see docs/setup-token.md).

## Command map

- Research targeting: `adkit targeting search "LangChain"` (add `--type adworkposition` for job titles). Returns interest IDs to use in ad sets.
- Generate creative: `adkit generate image "PROMPT" --out creatives/x.png --aspect 1:1` and `adkit generate video "PROMPT" --out creatives/x.mp4 --duration 8`. Check spend with `adkit generate spend`.
- Build by hand: `adkit campaign create` then `adkit adset create --campaign-id <id>` then `adkit creative create` then `adkit ad create --adset-id <id> --creative-id <id>`.
- Lead-gen (Instant Form): `adkit leadform create` first, then pass `--lead-form-id` to `adkit creative create`.
- Build everything at once: write a brief (see examples/briefs/example.yaml) and run `adkit automate launch --brief brief.yaml` (dry run), then `--go`.
- Go live: `adkit ad activate --ad-id <id>` (only after the user confirms). This
  flips the whole delivery chain (campaign + ad set + ad) ACTIVE so the ad
  actually serves; other ads in the set stay PAUSED. `adkit ad pause` stops it.
- Optimize live ads: `adkit optimize report [--target-cpl N] [--lead-form-id ID]
  [--revenue AD_ID=AMT] [--target-roas N]` is read-only and free; it recommends
  KILL/SCALE/KEEP per ad and never judges an ad still in the learning window.
  Enact a call with `adkit optimize apply --ad-id <id> --action pause|scale --yes`
  (only after the user confirms; `--action scale` raises budget, i.e. spends more).
  Never surface raw lead PII; the report only carries redacted aggregates.
- Re-running `automate launch --go` after a failure is safe: adkit reuses any
  campaign/ad set/ad that already exists by name and won't regenerate creative
  whose file is already on disk, so nothing is duplicated or double-charged.

## Typical flow you should follow

1. `adkit verify`
2. `adkit targeting search "<interest>"` to pick interest IDs.
3. Draft a brief YAML (campaign, ad sets with targeting, ads with copy).
4. `adkit automate launch --brief brief.yaml` (dry run) and show the plan.
5. On the user's "go": `adkit automate launch --brief brief.yaml --go`.
6. Report the created IDs. Remind the user everything is PAUSED, and that
   `adkit ad activate --ad-id <id>` takes the whole chain live when they're ready.

Minor budget units matter: budgets are in the account currency's minor units
(cents on USD), so 5000 = $50.00.
