"""The single HTTP surface for the Meta Graph API.

Security notes:
  * The access token travels in the `Authorization: Bearer` header, never in the
    URL query string. This keeps it out of request URLs, which are the thing that
    ends up in exception messages, proxy logs, and CI output.
  * Every code path that could carry the token in a string (a raised network
    exception, a non-JSON body) is scrubbed before it is surfaced, so the token
    cannot leak into a traceback or log even indirectly.
"""

from __future__ import annotations

import random
import time

import requests

from . import config

REDACTED = "<redacted-token>"

# Meta error codes that mean "you are being throttled, back off and retry".
# These are safe to retry even for a write, because Meta rejected the call
# outright, so no object was created.
# https://developers.facebook.com/docs/marketing-api/error-reference
_THROTTLE_CODES = {4, 17, 32, 341, 613, 80000, 80004}
_MAX_RETRIES = 4
_BACKOFF_BASE = 1.5  # seconds; grows exponentially with jitter


class GraphError(Exception):
    pass


def _url(path: str) -> str:
    return f"{config.GRAPH_HOST}/{config.GRAPH_VERSION}/{path.lstrip('/')}"


def _scrub(text: str, token: str | None) -> str:
    return text.replace(token, REDACTED) if token else text


def _sleep(attempt: int) -> None:
    time.sleep(_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.5))


def _throttled(resp: requests.Response) -> bool:
    """True if the response is a rate-limit signal we should back off and retry."""
    if resp.status_code == 429:
        return True
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return False
    return err.get("code") in _THROTTLE_CODES


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    files: dict | None = None,
    access_token: str | None = None,
    timeout: int = 30,
    retry_network: bool = True,
) -> dict:
    token = access_token or config.require("META_ACCESS_TOKEN")
    url = _url(path)
    headers = {"Authorization": f"Bearer {token}"}
    # We retry two things and nothing else, on purpose:
    #   * Rate-limit responses (HTTP 429 or a Meta throttle code). Meta rejected
    #     the call, so a retry cannot create a duplicate object.
    #   * Pre-response network errors, but only when retry_network is set. For a
    #     write that could double-create on a lost response, the caller turns it
    #     off. We never blanket-retry 5xx on a write for the same reason.
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.request(
                method, url, params=params, data=data, files=files,
                headers=headers, timeout=timeout,
            )
        except requests.RequestException as e:
            if retry_network and attempt < _MAX_RETRIES:
                _sleep(attempt)
                continue
            # Never let the token ride out in a network-error message. `from None`
            # drops the original exception so its (potentially token-bearing) repr
            # is not chained into the traceback either.
            raise GraphError(
                f"Network error calling Graph API ({method} {url}): {_scrub(str(e), token)}"
            ) from None

        if _throttled(resp) and attempt < _MAX_RETRIES:
            _sleep(attempt)
            continue
        return _handle(resp, token)

    return _handle(resp, token)  # pragma: no cover - loop always returns above


def get(path: str, params: dict | None = None, *, access_token: str | None = None) -> dict:
    return _request("GET", path, params=params, access_token=access_token)


def post(
    path: str,
    data: dict | None = None,
    files: dict | None = None,
    *,
    access_token: str | None = None,
    timeout: int = 60,
) -> dict:
    # A file upload streams a one-shot body, so a network retry cannot safely
    # replay it; and any write could double-create on a lost response. Rate-limit
    # retries are still safe (Meta rejected the call) and stay on.
    return _request(
        "POST", path, data=data, files=files, access_token=access_token,
        timeout=timeout, retry_network=False,
    )


def delete(path: str, params: dict | None = None, *, access_token: str | None = None) -> dict:
    return _request("DELETE", path, params=params, access_token=access_token)


def _handle(r: requests.Response, token: str | None = None) -> dict:
    try:
        body = r.json()
    except ValueError:
        raise GraphError(f"Non-JSON response ({r.status_code}): {_scrub(r.text[:500], token)}")
    if isinstance(body, dict) and "error" in body:
        e = body["error"]
        parts = [
            f"Meta API error #{e.get('code')} (subcode {e.get('error_subcode')}): {e.get('message')}",
            f"  type={e.get('type')}  fbtrace_id={e.get('fbtrace_id')}",
        ]
        if e.get("error_user_title") or e.get("error_user_msg"):
            parts.append(
                f"  user-facing: {e.get('error_user_title')!r}: {e.get('error_user_msg')}"
            )
        if e.get("error_data"):
            parts.append(f"  error_data: {e.get('error_data')}")
        raise GraphError(_scrub("\n".join(parts), token))
    return body
