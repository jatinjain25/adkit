from __future__ import annotations

import requests

from . import config


class GraphError(Exception):
    pass


def _url(path: str) -> str:
    return f"{config.GRAPH_HOST}/{config.GRAPH_VERSION}/{path.lstrip('/')}"


def _with_token(params: dict | None, token: str | None = None) -> dict:
    merged = dict(params or {})
    merged["access_token"] = token or config.require("META_ACCESS_TOKEN")
    return merged


def get(path: str, params: dict | None = None, *, access_token: str | None = None) -> dict:
    return _handle(
        requests.get(_url(path), params=_with_token(params, access_token), timeout=30)
    )


def post(
    path: str,
    data: dict | None = None,
    files: dict | None = None,
    *,
    access_token: str | None = None,
    timeout: int = 60,
) -> dict:
    return _handle(
        requests.post(
            _url(path),
            data=_with_token(data, access_token),
            files=files,
            timeout=timeout,
        )
    )


def delete(path: str, params: dict | None = None, *, access_token: str | None = None) -> dict:
    return _handle(
        requests.delete(_url(path), params=_with_token(params, access_token), timeout=30)
    )


def _handle(r: requests.Response) -> dict:
    try:
        body = r.json()
    except ValueError:
        raise GraphError(f"Non-JSON response ({r.status_code}): {r.text[:500]}")
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
        raise GraphError("\n".join(parts))
    return body
