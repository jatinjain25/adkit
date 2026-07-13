# Security and secrets

adkit is built so that a working setup never puts a secret in the repository.

## How secrets are handled

- Every credential is read from the environment (via a local `.env`), never
  hardcoded. See `adkit/config.py`.
- `.env` is gitignored. Only `.env.example`, which contains placeholders, is
  tracked.
- The Gemini key for creative generation is passed to the gemskills subprocess
  through the environment at call time (`adkit/creative_gen.py`); it is never
  written to a file adkit creates.
- Access tokens are never printed in full. `adkit verify` reports validity,
  expiry, and scopes, not the token itself.

## Before you push

Run a quick scan to be sure nothing slipped in:

```bash
git grep -nE 'EAA[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}|act_[0-9]{6,}' -- . ':!*.example' || echo "clean"
```

`EAA...` is the shape of a Meta token, `AIza...` a Google API key. If either
matches outside an example file, remove it and rotate the credential.

## Reporting a vulnerability

Open a private security advisory on the repository, or email the maintainers.
Please do not file public issues for suspected vulnerabilities.
