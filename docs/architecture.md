# Architecture

adkit is a small, readable Click application over the Meta Marketing API, plus a
thin creative-generation layer.

```
adkit/
  cli.py            Click group; registers every command.
  config.py         Loads .env; resolves account/page/ig-actor; require/optional.
  graph.py          One place that talks to the Graph API: get/post/delete +
                    consistent error surfacing (GraphError with fbtrace ids).
  creative_gen.py   Shells out to gemskills for Gemini images and Veo video.
                    Key comes from the environment; spend is logged locally.
  commands/
    verify.py       Credential and link smoke test.
    targeting.py    Interest and job-title lookup.
    campaign.py     Campaign create/list.
    adset.py        Ad set create/list with a targeting builder.
    creative.py     Image and video creative builder (+ upload helpers).
    ad.py           Ad create/list/activate/pause.
    leadform.py     Instant Form create/list (Page-token aware).
    generate.py     `generate image|video|spend` over creative_gen.
    automate.py     Reads a brief and runs the whole chain end to end.
```

## Principles

- **One HTTP surface.** All Graph calls go through `graph.py`, so auth, timeouts,
  and error formatting live in exactly one place.
- **Config, not constants.** Anything environment-specific (account, page, keys,
  advertiser URL) is read through `config.py` from `.env`. There are no hardcoded
  ids or secrets.
- **Safe defaults.** Statuses default to PAUSED across campaign, ad set, and ad.
  `automate launch` is dry-run until `--go`.
- **Money is explicit.** The two spending surfaces (ad activation and creative
  generation) announce cost or live status; generation spend is logged.

## Extending

- Add a command: create `commands/<name>.py` with a Click group and register it
  in `cli.py`.
- Add a creative model: extend `creative_gen.py`; keep the "key from env, log the
  spend" contract.
- Add a brief field: parse it in `commands/automate.py`. Keep the brief
  declarative and the safety defaults intact.
