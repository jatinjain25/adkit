# Security

adkit drives a live ad account and can spend money, so safety is a first-class
design goal, not an afterthought. This document describes the threat model, the
controls that back it, and how to report a problem.

## Threat model

adkit assumes:

- **You trust the machine it runs on.** It reads your credentials from a local
  `.env` and calls the Meta and Google APIs as you. It is not a multi-tenant
  service and does not sandbox the host.
- **You may not fully trust the agent driving it.** Because adkit exposes an MCP
  server, an LLM agent (or a prompt injection reaching one) can call its tools.
  The controls below assume the caller can be careless or adversarial.

The assets worth protecting are your **access token**, your **ad budget**, and
the **files on your machine**.

## Controls

### Secrets never enter the repo

- Every credential is read from the environment via a local `.env`, never
  hardcoded (`adkit/config.py`). `.env` is gitignored; only `.env.example`
  (placeholders) is tracked.
- The Gemini key is passed to the gemskills subprocess through the environment
  at call time (`adkit/creative_gen.py`), never written to a file adkit creates.

### The access token never rides in a URL

- The Meta token is sent in the `Authorization: Bearer` header, never as a query
  parameter (`adkit/graph.py`). URLs are what leak into exception messages,
  proxy logs, and CI output, so keeping the token out of them removes that class
  of leak.
- Every string that could carry the token (a network-error message, a non-JSON
  body) is scrubbed to `<redacted-token>` before it is raised, and the original
  exception is dropped (`raise ... from None`) so it cannot be chained into a
  traceback. `adkit verify` reports validity, expiry, and scopes, never the token.

### Nothing spends by accident

- Campaigns, ad sets, and ads are always created **PAUSED**. Delivery starts
  only on an explicit `adkit ad activate`.
- `adkit automate launch` is a **dry run** until `--go`.
- Over MCP, the actions that spend money or go live (`activate_ad`,
  `generate_image`, `generate_video`, `launch_brief(go=True)`) are refused
  unless the operator sets **`ADKIT_ALLOW_SPEND=1`** in the server environment.
  This is enforced server-side, so an auto-approving client or a prompt
  injection cannot bypass it with a persuasive tool call.
- **`ADKIT_GENERATION_DAILY_CAP_USD`** sets a hard per-day ceiling on AI
  generation spend, enforced across both the CLI and MCP.

### MCP file tools cannot escape their directory

- The MCP `generate_*` and `create_ad_from_image` tools resolve every path
  against the creatives working directory (`ADKIT_CREATIVE_DIR`, default
  `./creatives`) and reject anything that escapes it. This blocks an agent from
  writing arbitrary files or reading and uploading `/etc/passwd`.

## Supply chain and trust boundaries

- **Runtime dependencies** are `requests` and `click` (plus optional `pyyaml`
  and `mcp`). They are version-floored, not hash-pinned; for a locked, auditable
  install, generate a lock file (`pip-compile` or `uv pip compile`) and install
  from it.
- **AI creative generation executes third-party code.** `adkit/creative_gen.py`
  shells out to the [gemskills](https://github.com/b-open-io/gemskills) toolkit
  via the `bun` runtime. That code runs with your privileges and your Gemini
  key. Only point `GEMSKILLS_ROOT` and `BUN` at binaries you trust, and treat a
  gemskills update like any other dependency bump. adkit invokes it with an
  argument list (never a shell), so a creative prompt cannot inject shell
  commands, but the toolkit itself is still code you are choosing to run.

## Before you push

```bash
git grep -nE 'EAA[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}' -- . ':!*.example' || echo "clean"
```

`EAA...` is the shape of a Meta token, `AIza...` a Google API key. If either
matches outside an example file, remove it and rotate the credential.

## Reporting a vulnerability

Open a private security advisory on the repository, or email the maintainers.
Please do not file public issues for suspected vulnerabilities.
