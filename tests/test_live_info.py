import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_sh_blog_search(client):
    data = await call(client, "sh_blog_search", {"query": "مانتو"})
    assert len(data["posts"]) == 3 and all("مانتو" in p["title"] for p in data["posts"])


async def test_sh_blog_post(client):
    slug = (await call(client, "sh_blog_search", {}))["posts"][0]["slug"]
    data = await call(client, "sh_blog_post", {"slug": slug, "max_chars": 1000})
    assert data["title"] and len(data["text"]) > 100
