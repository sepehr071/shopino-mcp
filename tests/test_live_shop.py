import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_sh_shops(client):
    data = await call(client, "sh_shops", {"query": "پاپیون"})
    assert any(s["id"] == 489 and s["username"] == "papionlady" for s in data["shops"])


async def test_sh_shop(client):
    data = await call(client, "sh_shop", {"shop": "papionlady", "similar_shops": True})
    assert data["id"] == 489 and data["rating"] > 4 and data["survey_pct"]["satisfied"] > 50
    assert data["categories"][0]["title"] and data["similar_shops"]
