"""Shared async HTTP client for the Shopino API.

Shopino serves one REST API from two hosts with the same `/api/v1/app/...` paths: the Go backend
(`api-go.shopino.app`: search, product lists, product page, shops, sliders, landings) and the Django
backend (`api.shopino.app`: curated listings, similar shops, blog, courier cities). Each path lives on
exactly one host; the other answers 404. Every tool goes through `api`. `_send` caps concurrency,
retries (jittered backoff) when the server drops the connection, times out, answers 429/5xx or 200 with
an empty body, and turns HTTP failures into `ToolError` messages the model can act on.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import time
from typing import Any

import httpx
from curl_cffi import CurlOpt
from httpx_curl_cffi import AsyncCurlTransport
from mcp.server.mcpserver.exceptions import ToolError

GO = "https://api-go.shopino.app"
DJANGO = "https://api.shopino.app"
SITE = "https://shopino.app"

HEADERS = {
    # User-Agent, sec-ch-ua and TLS come from the impersonated Chrome profile (see _get_client).
    "Accept": "application/json",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    # Both API hosts are subdomains of shopino.app, so the site's XHRs are same-site cross-origin.
    "Origin": SITE,
    "Referer": f"{SITE}/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "priority": "u=1, i",
}

MAX_CONCURRENCY = 2
JITTER = (0.15, 0.6)  # seconds before each uncached call
MAX_RETRIES = 2
MAX_RETRY_WAIT = 10  # cap for Retry-After and backoff, seconds
RETRY_DELAY = 0.5  # base of the exponential backoff, seconds
CACHE_TTL = 3600  # seconds a cached static reply (category tree, courier cities) is reused

_transport: httpx.AsyncBaseTransport | None = None
_client: httpx.AsyncClient | None = None
_limit: asyncio.Semaphore | None = None
_proxy_index = 0
_retired: set[asyncio.Task] = set()
_browser_lock: asyncio.Lock | None = None
_cleared: tuple[httpx.AsyncClient, float] | None = None
_cache: dict[tuple, tuple[float, Any]] = {}


class _XhrTransport(AsyncCurlTransport):
    """The Chrome profile sends navigation-only headers; a None value makes curl drop them (API calls are XHR)."""

    def _create_request_params(self, req: httpx.Request) -> dict[str, Any]:
        p = super()._create_request_params(req)
        p["headers"] = [*p["headers"], (b"upgrade-insecure-requests", None), (b"sec-fetch-user", None)]
        return p


class ApiError(ToolError):
    """A failed upstream call. `status` is the HTTP status, or None for network errors."""

    def __init__(self, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Swap the transport (tests use httpx.MockTransport). Drops the current client."""
    global _transport, _client, _limit, _proxy_index, _browser_lock, _cleared
    _transport, _client, _limit, _proxy_index, _browser_lock, _cleared = transport, None, None, 0, None, None
    _cache.clear()


def _proxies() -> list[str]:
    """SHOPINO_MCP_PROXY: one proxy URL, or a comma-separated list used one at a time."""
    return [p.strip() for p in os.environ.get("SHOPINO_MCP_PROXY", "").split(",") if p.strip()]


# A bare empty 403 is the upstream's answer for an unknown path, not a bot check: only a marked HTML page counts.
_CHALLENGE = re.compile(r"just a moment|captcha|challenge|arvan|attention required|enable javascript", re.I)


def _is_challenge(r: httpx.Response) -> bool:
    """A bot-check page: 403/429/503 with an HTML body that carries a known challenge marker."""
    return (
        r.status_code in (403, 429, 503)
        and "html" in r.headers.get("content-type", "") + r.text[:20].lower()
        and bool(_CHALLENGE.search(r.text[:5000]))
    )


def _next_proxy(client: httpx.AsyncClient) -> None:
    """Sticky pool: move to the next proxy after a block or connect error; the next call rebuilds the client.

    Only the client that failed may rotate: a slower request that failed on an old client must not skip a good proxy.
    The old client is closed late because other requests may still be using it.
    """
    global _client, _limit, _proxy_index
    if len(_proxies()) < 2 or client is not _client:
        return
    _client, _limit, _proxy_index = None, None, _proxy_index + 1
    t = asyncio.create_task(_close_later(client))
    _retired.add(t)
    t.add_done_callback(_retired.discard)


async def _close_later(client: httpx.AsyncClient) -> None:
    await asyncio.sleep(30)  # longer than the 30 s request timeout
    await client.aclose()


def _get_client() -> tuple[httpx.AsyncClient, asyncio.Semaphore]:
    global _client, _limit
    if _client is None:
        # Shopino answers direct connections fine (a proxy is about 4x slower); a proxy is only
        # used when the user opts in with SHOPINO_MCP_PROXY. curl_cffi presents Chrome's TLS/HTTP2
        # fingerprint and default headers; cookies and redirects stay with httpx. The proxy goes to the
        # transport (a client-level proxy would be ignored once a transport is given).
        proxies = _proxies()
        _client = httpx.AsyncClient(
            transport=_transport
            or _XhrTransport(
                impersonate="chrome",
                default_headers=True,
                proxy=proxies[_proxy_index % len(proxies)] if proxies else None,
                # httpx-curl-cffi drops its own NOPROXY=* unless curl_options is passed, so curl would read HTTPS_PROXY.
                curl_options={CurlOpt.NOPROXY: "" if proxies else "*"},
                max_connections=2 * MAX_CONCURRENCY,
            ),
            headers=HEADERS,
            timeout=httpx.Timeout(30, connect=5),
            limits=httpx.Limits(max_connections=2 * MAX_CONCURRENCY),
            follow_redirects=True,
            trust_env=False,
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
    """GET with up to MAX_RETRIES retries of timeouts, network errors, 429, 5xx and empty 200s; 403 is never retried."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await _once(url, **kwargs)
        except ApiError as e:
            if attempt == MAX_RETRIES or (e.status is not None and e.status != 429 and e.status < 500):
                raise
            wait = e.retry_after if e.retry_after is not None else RETRY_DELAY * 2**attempt * random.uniform(1, 1.5)
            await asyncio.sleep(min(wait, MAX_RETRY_WAIT))
            continue
        if r.status_code == 200 and not r.content and attempt < MAX_RETRIES:
            await asyncio.sleep(min(RETRY_DELAY * 2**attempt * random.uniform(1, 1.5), MAX_RETRY_WAIT))
            continue  # empty 200 seen once while mapping; a retry works
        return r
    raise AssertionError("unreachable")


async def _fetch(client: httpx.AsyncClient, limit: asyncio.Semaphore, url: str, **kwargs: Any) -> httpx.Response:
    try:
        async with limit:
            await asyncio.sleep(random.uniform(*JITTER))
            return await client.get(url, **kwargs)
    except httpx.TimeoutException as e:
        raise ApiError("shopino.app did not answer in time. Try again in a moment.") from e
    except httpx.TooManyRedirects as e:
        _next_proxy(client)
        raise ApiError("shopino.app kept redirecting. Try again in a moment.") from e
    except httpx.TransportError as e:
        if isinstance(e, httpx.ConnectError | httpx.ProxyError):
            _next_proxy(client)
        raise ApiError(
            f"Could not reach shopino.app ({type(e).__name__}). Check the internet connection, "
            "or set SHOPINO_MCP_PROXY."
        ) from e


async def _browser_cookies(proxy: str | None) -> list[dict[str, Any]]:
    """Open the home page in headless patchright, wait for the challenge to clear, return the cookies."""
    try:
        from patchright.async_api import async_playwright
    except ImportError as e:
        raise ApiError(
            "Shopino served a bot-check page. Install the browser extra (`pip install shopino-mcp[browser]`, or "
            "`uvx --with patchright==1.63.0 shopino-mcp`) and run `patchright install chromium`.",
            403,
        ) from e
    u = httpx.URL(proxy) if proxy else None
    opts = u and {"server": f"{u.scheme}://{u.host}:{u.port}", "username": u.username, "password": u.password}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=opts)
        try:
            page = await browser.new_page()
            await page.goto(SITE, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_function(
                "!/just a moment|access denied|attention required|arvancloud/i.test(document.title)", timeout=30_000
            )
            return await browser.contexts[0].cookies()
        finally:
            await browser.close()


async def _clear_challenge(client: httpx.AsyncClient) -> None:
    """Rung 2: let a real browser pass the bot check once and share its cookies with the httpx jar."""
    global _browser_lock, _cleared
    _browser_lock = _browser_lock or asyncio.Lock()
    async with _browser_lock:  # one browser at a time; callers that waited reuse the cookies just fetched
        if _cleared and _cleared[0] is client and time.monotonic() - _cleared[1] < 30:
            return
        proxies = _proxies()
        try:
            cookies = await _browser_cookies(proxies[_proxy_index % len(proxies)] if proxies else None)
        except ApiError:
            raise
        except Exception as e:
            raise ApiError(f"Shopino bot check was not cleared by the browser ({type(e).__name__}).", 403) from e
        for c in cookies:
            client.cookies.set(c["name"], c["value"], domain=c["domain"], path=c["path"])
        _cleared = (client, time.monotonic())


def _retry_after(r: httpx.Response) -> float | None:
    """Seconds from a numeric Retry-After on a 429/503, else None (HTTP-date form is ignored)."""
    v = r.headers.get("retry-after", "")
    return float(v) if r.status_code in (429, 503) and v.replace(".", "", 1).isdigit() else None


async def _once(url: str, **kwargs: Any) -> httpx.Response:
    client, limit = _get_client()
    r = await _fetch(client, limit, url, **kwargs)
    if _is_challenge(r):
        _next_proxy(client)
        client, limit = _get_client()
        await _clear_challenge(client)
        r = await _fetch(client, limit, url, **kwargs)  # one retry; a second block is final
        if _is_challenge(r):
            _next_proxy(client)
    if r.status_code >= 400:
        if r.status_code in (403, 429):
            _next_proxy(client)
        detail = ""
        try:
            body = r.json()
            detail = str(body.get("detail") or "")[:300] if isinstance(body, dict) else ""
        except ValueError:
            pass
        raise ApiError(
            _status_message(r.status_code) + (f" Site says: {detail}" if detail else ""),
            r.status_code,
            _retry_after(r),
        )
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
