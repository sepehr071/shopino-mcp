import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_sh_search(client):
    data = await call(client, "sh_search", {"query": "مانتو", "sort": "cheapest", "min_price": 500000, "limit": 20})
    # flash-sale items are ranked by their pre-sale price (the site too): leave them out of the order checks
    prices = [p["final_price"] for p in data["products"] if not p.get("flash_sale")]
    assert len(data["products"]) == 20 and prices == sorted(prices) and prices[0] >= 500000
    assert all(p["in_stock"] for p in data["products"]) and data["next_cursor"]
    more = await call(
        client, "sh_search", {"query": "مانتو", "sort": "cheapest", "min_price": 500000, "cursor": data["next_cursor"]}
    )
    assert [p for p in more["products"] if not p.get("flash_sale")][0]["final_price"] >= prices[-1]


async def test_sh_find_cheapest(client):
    data = await call(client, "sh_find_cheapest", {"query": "کفش ورزشی", "limit": 10})
    prices = [o["final_price"] for o in data["offers"]]
    assert len(prices) == 10 and prices == sorted(prices) and prices[0] > 0
    assert all("کفش" in o["title"] and o["in_stock"] for o in data["offers"])


async def test_sh_browse(client):
    args = {"category_id": 385, "sort": "cheapest", "min_price": 1000000, "max_price": 3000000, "limit": 12}
    data = await call(client, "sh_browse", args)
    prices = [p["final_price"] for p in data["products"] if not p.get("flash_sale")]
    assert prices == sorted(prices) and all(1000000 <= p <= 3000000 for p in prices) and data["next_cursor"]
    # the next page keeps the sort (the feed's `page=N` would not)
    more = await call(client, "sh_browse", {**args, "cursor": data["next_cursor"]})
    more_prices = [p["final_price"] for p in more["products"] if not p.get("flash_sale")]
    assert more_prices == sorted(more_prices) and more_prices[0] >= prices[-1]


async def test_sh_filters(client):
    data = await call(client, "sh_filters", {"category_id": 358})
    assert any(c["id"] == 385 for c in data["sub_categories"]) and "تهران" in data["courier_cities"]


async def test_sh_categories(client):
    data = await call(client, "sh_categories", {"query": "maanto"})
    assert any(c["id"] == 385 and c["path"] == "clothing/women/maanto" for c in data["categories"])


async def test_sh_brands(client):
    data = await call(client, "sh_brands", {"shop_id": 1771})
    assert any(b["id"] == 12 and b["name_en"] == "Tommy Hilfiger" for b in data["brands"])


async def test_sh_deals(client):
    data = await call(client, "sh_deals", {"limit": 10})
    pcts = [d["discount_pct"] for d in data["deals"]]
    assert pcts and pcts == sorted(pcts, reverse=True) and data["sections"]
    assert all(d["final_price"] < d["price"] for d in data["deals"])


async def test_sh_campaign(client):
    slug = (await call(client, "sh_deals", {"limit": 1}))["campaigns"][0]["slug"]
    data = await call(client, "sh_campaign", {"slug": slug})
    assert data["title"] and (data["rows"] or data["tabs"])
