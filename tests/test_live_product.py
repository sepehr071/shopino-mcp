import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def _discounted_product(client) -> int:
    """Products come and go: take a current in-stock, discounted one."""
    data = await call(client, "sh_browse", {"category_id": 385, "discounted_only": True, "limit": 5})
    return data["products"][0]["id"]


async def test_sh_product(client):
    product_id = await _discounted_product(client)
    data = await call(client, "sh_product", {"product_id": product_id})
    assert data["in_stock"] and data["final_price"] < data["price"] and data["discount_pct"] > 0
    assert data["variants"] and all("stock" in v for v in data["variants"])
    assert data["shop"]["id"] and data["original_url"]


async def test_sh_similar(client):
    product_id = await _discounted_product(client)
    data = await call(client, "sh_similar", {"product_id": product_id, "sort": "cheapest", "limit": 10})
    prices = [p["final_price"] for p in data["products"]]
    assert prices and prices == sorted(prices) and product_id not in [p["id"] for p in data["products"]]
