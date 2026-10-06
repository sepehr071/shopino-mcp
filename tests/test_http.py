import re
from pathlib import Path

import httpx
import pytest

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
    assert len(api.calls) == 2


async def test_timeout_is_not_retried(client, api):
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    api[FEATURED] = slow
    result = await client.call_tool("sh_brands", {})
    assert result.is_error and "did not answer in time" in result.content[0].text and len(api.calls) == 1


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
    assert not result.is_error and "Chrome" in api.calls[0].headers["User-Agent"]
