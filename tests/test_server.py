import json

import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

SEARCH = "/api/v1/app/products/search/مانتو کتان/"


async def test_compact_output(client, api):
    api[SEARCH] = fixture("search.json")
    result = await client.call_tool("sh_search", {"query": "مانتو کتان", "limit": 3})
    text = result.content[0].text
    assert len(result.content) == 1
    assert "\n" not in text and '":' in text and "\\u" not in text
    assert json.loads(text) == result.structured_content
    assert all(t.output_schema is None for t in (await client.list_tools()).tools)


async def test_raw_client_sees_one_text_block_and_no_structured_content(api):
    from mcp import Client

    from shopino_mcp.server import mcp

    api[SEARCH] = fixture("search.json")
    async with Client(mcp) as c:  # not the conftest fixture: no parsing patch
        result = await c.call_tool("sh_search", {"query": "مانتو کتان", "limit": 3})
        assert len(result.content) == 1 and result.structured_content is None
        assert all(t.output_schema is None for t in (await c.list_tools()).tools)
