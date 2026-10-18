import asyncio
import re
import sys
from pathlib import Path

import httpx
import pytest

from shopino_mcp import http

pytestmark = pytest.mark.anyio

FEATURED = "/api/v1/app/featured-brands/"


async def test_all_tools_are_read_only(client):
    tools = (await client.list_tools()).tools
    assert len(tools) == 14
    for t in tools:
        assert t.name.startswith("sh_"), t.name
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False, t.name
        assert t.description and t.title, t.name


async def test_readme_tool_tables_match_the_server(client):
    readme = (Path(__file__).parent.parent / "README.md").read_text(encoding="utf-8")
    listed = re.findall(r"^\| `(sh_\w+)` \|", readme, re.M)
    assert sorted(listed) == sorted(t.name for t in (await client.list_tools()).tools)


async def test_dropped_connection_is_retried_once(client, api):
    attempts = []

    def flaky(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.", request=request)
        return httpx.Response(200, json=[])

    api[FEATURED] = flaky
    result = await client.call_tool("sh_brands", {})
    assert not result.is_error and len(attempts) == 2


async def test_empty_200_body_is_retried_once(client, api):
    replies = iter([httpx.Response(200), httpx.Response(200, json=[{"id": 1, "title": "x"}])])
    api[FEATURED] = lambda r: next(replies)
    out = (await client.call_tool("sh_brands", {})).structured_content
    assert out["brand_shops"][0]["shop_id"] == 1 and len(api.calls) == 2


async def test_network_error_after_retry(client, api):
    def down(request):
        raise httpx.ConnectError("[SSL: UNEXPECTED_EOF_WHILE_READING]", request=request)

    api[FEATURED] = down
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and "Could not reach shopino.app (ConnectError)" in result.content[0].text
    assert len(api.calls) == 3


async def test_timeout_is_retried_twice(client, api):
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    api[FEATURED] = slow
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and "did not answer in time" in result.content[0].text and len(api.calls) == 3


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (404, "HTTP 404"),
        (410, "removed from Shopino"),
        (429, "rate limiting"),
        (500, "server error (HTTP 500)"),
        (403, "blocked"),
        (401, "logged-in"),
    ],
)
async def test_http_errors_are_actionable(client, api, status, text):
    api[FEATURED] = lambda r: httpx.Response(status)
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and text in result.content[0].text


async def test_django_error_detail_is_passed_on(client, api):
    body = {"detail": "No ShopTag matches the given query."}
    api[FEATURED] = lambda r: httpx.Response(404, json=body)
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and "Site says: No ShopTag matches the given query." in result.content[0].text


async def test_non_json_reply(client, api):
    api[FEATURED] = lambda r: httpx.Response(200, text="<html>oops</html>")
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and "non-JSON" in result.content[0].text


async def test_browser_user_agent_and_no_env_proxy(client, api, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")  # must be ignored (trust_env=False)
    api[FEATURED] = []
    result = await client.call_tool("sh_brands", {})
    h = api.calls[0].headers
    assert not result.is_error and h["origin"] == "https://shopino.app" and h["sec-fetch-mode"] == "cors"


async def test_503_is_retried_once(client, api):
    replies = iter([httpx.Response(503), httpx.Response(200, json=[])])
    api[FEATURED] = lambda r: next(replies)
    result = await client.call_tool("sh_brands", {})
    assert not result.is_error and len(api.calls) == 2


async def test_initial_info_is_cached(client, api):
    api["/api/v1/app/initial-info/"] = {"categories": [], "products_count": 1, "shops_count": 2}
    for _ in range(2):
        await client.call_tool("sh_categories", {})
    assert len(api.calls) == 1


async def test_input_schemas_have_no_title_noise(client):
    for t in (await client.list_tools()).tools:
        assert "title" not in t.input_schema
        assert all("title" not in p for p in t.input_schema["properties"].values()), t.name


def test_is_challenge():
    html = {"content-type": "text/html"}
    assert http._is_challenge(httpx.Response(403, text="<html>Just a moment...</html>", headers=html))
    assert not http._is_challenge(httpx.Response(403))
    assert not http._is_challenge(httpx.Response(403, text="<html>Forbidden</html>", headers=html))
    assert not http._is_challenge(httpx.Response(200, text="<html></html>", headers=html))


async def test_proxy_list_rotates_and_stale_client_does_not(monkeypatch, api):
    monkeypatch.setenv("SHOPINO_MCP_PROXY", "http://p1:1, http://p2:2")
    assert http._proxies() == ["http://p1:1", "http://p2:2"]
    old, _ = http._get_client()
    http._next_proxy(old)
    new, _ = http._get_client()
    assert http._proxy_index == 1 and new is not old
    http._next_proxy(old)  # a late failure on the retired client must not skip the proxy now in use
    assert http._proxy_index == 1 and http._client is new


async def test_challenge_cleared_by_browser_once(monkeypatch, api):
    runs = []

    async def fake_browser(proxy):
        runs.append(proxy)
        await asyncio.sleep(0.01)
        return [{"name": "clearance", "value": "ok", "domain": ".shopino.app", "path": "/"}]

    monkeypatch.setattr(http, "_browser_cookies", fake_browser)

    def guarded(request):
        if "clearance=ok" not in request.headers.get("cookie", ""):
            return httpx.Response(403, text="<html>Just a moment</html>", headers={"content-type": "text/html"})
        return httpx.Response(200, json=[])

    api[FEATURED] = guarded
    await asyncio.gather(http.api(FEATURED), http.api(FEATURED, {"a": 1}))
    assert len(runs) == 1  # the second caller reused the cookies the first one fetched


async def test_challenge_without_patchright(monkeypatch, api):
    monkeypatch.setitem(sys.modules, "patchright.async_api", None)  # makes the import fail
    api[FEATURED] = lambda r: httpx.Response(403, text="<html>Just a moment</html>")
    with pytest.raises(http.ApiError, match=r"shopino-mcp\[browser\].*patchright install chromium"):
        await http.api(FEATURED)


async def test_403_is_not_retried_and_retry_after_is_honoured(monkeypatch, api):
    waits = []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(http.asyncio, "sleep", fake_sleep)
    api[FEATURED] = lambda r: httpx.Response(403)
    with pytest.raises(http.ApiError):
        await http.api(FEATURED)
    assert len(api.calls) == 1
    replies = iter([httpx.Response(429, headers={"Retry-After": "999"}), httpx.Response(200, json=[])])
    api[FEATURED] = lambda r: next(replies)
    await http.api(FEATURED)
    assert len(api.calls) == 3 and http.MAX_RETRY_WAIT in waits
