"""Shared async HTTP client for the Shopino API.

Shopino serves one REST API from two hosts with the same `/api/v1/app/...` paths: the Go backend
(`api-go.shopino.app`: search, product lists, product page, shops, sliders, landings) and the Django
backend (`api.shopino.app`: curated listings, similar shops, blog, courier cities). Each path lives on
exactly one host; the other answers 404. Every tool goes through `api`. `_send` caps concurrency,
retries once (after a short fixed pause) when the server drops the connection, answers 502/503/504 or
200 with an empty body, and turns HTTP failures into `ToolError` messages the model can act on.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

GO = "https://api-go.shopino.app"
DJANGO = "https://api.shopino.app"
SITE = "https://shopino.app"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0",
    "Accept": "application/json",
}

MAX_CONCURRENCY = 4
RETRY_DELAY = 0.5  # seconds before the single retry of a GET
CACHE_TTL = 3600  # seconds a cached static reply (category tree, courier cities) is reused

_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_limit: asyncio.Semaphore | None = None
_cache: dict[tuple, tuple[float, Any]] = {}


class ApiError(ToolError):
    """A failed upstream call."""


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Swap the transport (tests use httpx.MockTransport). Drops the current client."""
    global _transport, _client, _limit
    _transport, _client, _limit = transport, None, None
    _cache.clear()


def _get_client() -> tuple[httpx.AsyncClient, asyncio.Semaphore]:
    global _client, _limit
    if _client is None:
        # Shopino answers direct connections fine (a proxy is about 4x slower); a proxy is only
        # used when the user opts in with SHOPINO_MCP_PROXY.
        _client = httpx.AsyncClient(
            transport=_transport,
            headers=HEADERS,
            timeout=httpx.Timeout(30, connect=5),
            follow_redirects=True,
            trust_env=False,
            proxy=os.environ.get("SHOPINO_MCP_PROXY") or None,
        )
        _limit = asyncio.Semaphore(MAX_CONCURRENCY)
    assert _limit is not None
    return _client, _limit


async def api(path: str, params: dict[str, Any] | None = None, *, django: bool = False) -> Any:
    """GET an API path (`/api/v1/app/...`) on the Go host (or the Django host) and return the parsed JSON."""
    r = await _send(
        f"{DJANGO if django else GO}{path}", params={k: v for k, v in (params or {}).items() if v is not None}
    )
    try:
        return r.json()
    except ValueError as e:
        raise ApiError(f"shopino.app returned a non-JSON response for {path} (HTTP {r.status_code}).") from e


async def cached_api(path: str, params: dict[str, Any] | None = None, *, django: bool = False) -> Any:
    """`api` with a TTL cache for static replies. The result is shared: callers must not mutate it."""
    key = (path, django, tuple(sorted((params or {}).items())))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    data = await api(path, params, django=django)
    _cache[key] = (time.monotonic(), data)
    return data


async def _send(url: str, **kwargs: Any) -> httpx.Response:
    client, limit = _get_client()
    for attempt in (1, 2):
        try:
            async with limit:
                r = await client.get(url, **kwargs)
        except httpx.TimeoutException as e:
            raise ApiError("shopino.app did not answer in time. Try again in a moment.") from e
        except httpx.TransportError as e:
            if attempt == 2:
                raise ApiError(
                    f"Could not reach shopino.app ({type(e).__name__}). Check the internet connection, "
                    "or set SHOPINO_MCP_PROXY."
                ) from e
            await asyncio.sleep(RETRY_DELAY)
            continue
        if attempt == 1 and (r.status_code in (502, 503, 504) or (r.status_code == 200 and not r.content)):
            await asyncio.sleep(RETRY_DELAY)  # empty 200 seen once while mapping; a retry works
            continue
        break
    if r.status_code >= 400:
        detail = ""
        try:
            body = r.json()
            detail = str(body.get("detail") or "")[:300] if isinstance(body, dict) else ""
        except ValueError:
            pass
        raise ApiError(_status_message(r.status_code) + (f" Site says: {detail}" if detail else ""))
    return r


def _status_message(code: int) -> str:
    if code == 400:
        return "shopino.app rejected the parameters (HTTP 400)."
    if code == 401:
        return "This needs a logged-in Shopino account (HTTP 401); this server is read-only and has no login."
    if code == 403:
        return "shopino.app blocked the request (HTTP 403). Turn off VPN/proxy or set SHOPINO_MCP_PROXY."
    if code == 404:
        return "Not found on shopino.app (HTTP 404). Check the shop id, slug or campaign name."
    if code == 410:
        return "This product was removed from Shopino or never existed (HTTP 410). Find products with sh_search."
    if code == 429:
        return "shopino.app is rate limiting requests (HTTP 429). Wait a minute before retrying."
    if code >= 500:
        return f"shopino.app had a server error (HTTP {code}). Check the ids, or try again later."
    return f"shopino.app rejected the request (HTTP {code})."
