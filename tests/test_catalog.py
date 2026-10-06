import httpx
import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

APP = "/api/v1/app"
SEARCH = f"{APP}/products/search/مانتو کتان/"
FEED = f"{APP}/products/recommendation/"
INFO = f"{APP}/initial-info/"


async def test_sh_search(client, api):
    api[SEARCH] = fixture("search.json")
    args = {"query": "مانتو کتان", "sort": "cheapest", "min_price": 500000, "limit": 6}
    out = (await client.call_tool("sh_search", args)).structured_content
    assert out["products"][0] == {
        "id": 2385657,
        "title": "مانتو کتان ازالیا (1123)",
        "final_price": 999000,
        "price": 2280000,
        "discount_pct": 56,
        "in_stock": True,
        "shop": "وایت گالری پلاس",
        "shop_id": 8578,
        "url": "https://shopino.app/product/2385657",
    }
    # shop rating / courier city only when set; no discount -> price == final_price
    second, fourth = out["products"][1], out["products"][3]
    assert second["shop_rating"] == 4.6 and second["courier_city"] == "تهران"
    assert fourth["final_price"] == fourth["price"] == 1115000 and fourth["discount_pct"] == 0
    assert out["next_cursor"] == "cursor=cD10cnVlJTJDMTI5ODAwMCUyQzIwNzEwLjM2OTE1MzEwMTg1Mg%3D%3D"
    assert api.params() == {"sort": "price", "in_stock": "true", "price_from": "500000", "page_size": "6"}
    assert api.hosts() == ["api-go.shopino.app"]


async def test_sh_search_paging_and_filters(client, api):
    api[SEARCH] = fixture("search.json")
    args = {
        "query": "مانتو کتان",
        "cursor": "cursor=abc%3D&search_seed=f00",
        "shop_id": 489,
        "size_system": "standard",
        "sizes": ["M", "L"],
        "city": "تهران",
        "in_stock_only": False,
        "discounted_only": True,
    }
    await client.call_tool("sh_search", args)
    assert api.params() == {
        "off": "true",
        "sizes": '{"standard":["M","L"]}',
        "city": "تهران",
        "page_size": "20",
        "shop_ids": "489",
        "cursor": "abc=",
        "search_seed": "f00",
    }


@pytest.mark.parametrize(
    ("args", "text"),
    [
        ({"min_price": 5, "max_price": 1}, "min_price"),
        ({"size_system": "shoe", "sizes": ["XL"]}, "Unknown shoe sizes"),
        ({"sizes": ["M"]}, "Pass size_system"),
        ({"size_system": "standard"}, "Pass sizes"),
        ({"cursor": "page_size=200"}, "Bad cursor"),
    ],
)
async def test_sh_search_bad_args(client, api, args, text):
    result = await client.call_tool("sh_search", {"query": "مانتو", **args})
    assert result.is_error and text in result.content[0].text and not api.calls


async def test_sh_search_freesize(client, api):
    api[f"{APP}/products/search/مانتو/"] = fixture("search.json")
    await client.call_tool("sh_search", {"query": "مانتو", "size_system": "freesize"})
    assert api.params()["sizes"] == '{"freesize":true}'


async def test_sh_find_cheapest(client, api):
    api[SEARCH] = fixture("search_cheapest.json")
    out = (await client.call_tool("sh_find_cheapest", {"query": "مانتو کتان", "limit": 5})).structured_content
    prices = [o["final_price"] for o in out["offers"]]
    assert out["scanned"] == 12 and out["complete"] is True and len(prices) == 5 and prices == sorted(prices)
    assert prices[0] == 999000
    assert api.params() == {"sort": "price", "in_stock": "true", "page_size": "200"}


async def test_sh_find_cheapest_follows_the_cursor_and_drops_loose_matches(client, api):
    page1 = fixture("search_cheapest.json")
    page1 = {**page1, "next": "https://api-go.shopino.app/x/?cursor=NEXT&sort=price", "results": page1["results"][:6]}
    page2 = {**page1, "next": None, "results": fixture("search_cheapest.json")["results"][6:]}
    pages = iter([page1, page2])
    api[f"{APP}/products/search/مانتو کتان گلدوزی/"] = lambda r: httpx.Response(200, json=next(pages))
    out = (await client.call_tool("sh_find_cheapest", {"query": "مانتو کتان گلدوزی"})).structured_content
    # only titles holding every word survive (3 of 12)
    assert [o["id"] for o in out["offers"]] == [2650596, 2451254, 2444204]
    assert out["scanned"] == 12 and out["complete"] is True
    assert api.params(1)["cursor"] == "NEXT" and len(api.calls) == 2


async def test_sh_browse_category(client, api):
    api[FEED] = fixture("feed.json")
    args = {"category_id": 385, "sort": "cheapest", "max_price": 3000000, "in_stock_only": False, "limit": 8}
    out = (await client.call_tool("sh_browse", args)).structured_content
    ids = [p["id"] for p in out["products"]]
    assert len(ids) == len(set(ids)) == 7  # one card per color of 1768703 -> deduped
    gone = out["products"][1]
    assert gone["id"] == 1768703 and gone["final_price"] is None and gone["price"] is None and not gone["in_stock"]
    # the product feed must be paged with its cursor: `page=N` drops the sort
    assert out["next_cursor"] == "page=3"
    assert api.params() == {"category": "385", "sort": "price", "price_to": "3000000", "page_size": "8"}


async def test_sh_browse_shop(client, api):
    api[f"{APP}/shops/489/products/"] = fixture("shop_products.json")
    args = {"shop_id": 489, "sort": "biggest_discount", "discounted_only": True, "limit": 4, "cursor": "page=2"}
    out = (await client.call_tool("sh_browse", args)).structured_content
    assert [p["discount_pct"] for p in out["products"]] == [55, 47, 44, 43]
    assert api.params() == {"sort": "-discount", "off": "true", "in_stock": "true", "page_size": "4", "page": "2"}


async def test_sh_browse_tag(client, api):
    api[f"{APP}/product-tags/مانتو-بلند-مشکی-زنانه/products/"] = fixture("tag.json")
    args = {"tag": "مانتو-بلند-مشکی-زنانه", "sort": "cheapest"}
    out = (await client.call_tool("sh_browse", args)).structured_content
    assert [p["final_price"] for p in out["products"]] == [399000, 598000, 698000, 700000, 736000]
    assert out["next_cursor"] == "offset=16" and api.params() == {"sort": "price"}


async def test_sh_browse_listing_on_django_host(client, api):
    api[f"{APP}/product-listings/پیراهن-مردانه/products/"] = fixture("listing.json")
    out = (await client.call_tool("sh_browse", {"listing": "پیراهن-مردانه", "limit": 4})).structured_content
    assert out["products"][0]["promo"] == "1 میلیون تخفیف با کد: benix7"
    assert api.hosts() == ["api.shopino.app"] and api.params() == {"in_stock": "true", "limit": "4"}
    assert out["next_cursor"] == "offset=4"


@pytest.mark.parametrize(
    ("args", "text"),
    [
        ({"shop_id": 1, "tag": "x"}, "at most one"),
        ({"tag": "x", "min_price": 5}, "does not support: min_price"),
        ({"listing": "x", "city": "تهران"}, "does not support: city"),
        ({"shop_id": 1, "city": "تهران"}, "city does not apply"),
        ({"tag": "../../x"}, "pattern"),
    ],
)
async def test_sh_browse_bad_args(client, api, args, text):
    result = await client.call_tool("sh_browse", args)
    assert result.is_error and text in result.content[0].text and not api.calls


async def test_sh_filters(client, api):
    api[INFO] = fixture("initial_info.json")
    api[f"{APP}/cities-list/"] = fixture("cities.json")
    out = (await client.call_tool("sh_filters", {"category_id": 358})).structured_content
    assert out["category"] == {"id": 358, "title": "لباس زنانه", "path": "clothing/women", "level": 2, "parent_id": 314}
    assert {"id": 385, "title": "مانتو زنانه", "path": "clothing/women/maanto", "level": 3, "parent_id": 358} in out[
        "sub_categories"
    ]
    assert out["size_systems"]["standard"]["sizes"][:4] == ["2XS", "XS", "S", "M"]
    assert out["size_systems"]["shoe"]["sizes"][0] == "30" and out["size_systems"]["shoe"]["sizes"][-1] == "47"
    assert out["courier_cities"][0] == "تهران" and "biggest_discount" in out["sorts"]
    assert api.hosts() == ["api-go.shopino.app", "api.shopino.app"]


async def test_sh_filters_unknown_category(client, api):
    api[INFO] = fixture("initial_info.json")
    api[f"{APP}/cities-list/"] = fixture("cities.json")
    result = await client.call_tool("sh_filters", {"category_id": 99999})
    assert result.is_error and "sh_categories" in result.content[0].text


async def test_sh_categories(client, api):
    api[INFO] = fixture("initial_info.json")
    out = (await client.call_tool("sh_categories", {"query": "maanto"})).structured_content
    assert out["categories"] == [
        {"id": 385, "title": "مانتو زنانه", "path": "clothing/women/maanto", "level": 3, "parent_id": 358}
    ]
    top = (await client.call_tool("sh_categories", {"max_level": 1})).structured_content
    assert len(top["categories"]) == 14 and top["products_count"] > 900000
    assert {
        "id": 314,
        "title": "لباس",
        "path": "clothing",
        "level": 1,
        "parent_id": None,
        "landing": "clothing",
    } in top["categories"]


async def test_sh_brands(client, api):
    api[f"{APP}/featured-brands/"] = fixture("featured_brands.json")
    out = (await client.call_tool("sh_brands", {})).structured_content
    assert out["brand_shops"][0] == {
        "shop_id": 156,
        "title": "پوشاک کروم",
        "rating": None,
        "surveys": 387,
        "url": "https://shopino.app/shops/156",
    }
    api[f"{APP}/shops/1771/"] = fixture("shop_1771.json")
    out = (await client.call_tool("sh_brands", {"shop_id": 1771})).structured_content
    assert out["brands"][0] == {"id": 12, "name": "تامی هیلفیگر", "name_en": "Tommy Hilfiger", "count": 255}


async def test_sh_deals(client, api):
    api[f"{APP}/product-sliders/"] = fixture("sliders.json")
    api[f"{APP}/banners/"] = fixture("banners.json")
    out = (await client.call_tool("sh_deals", {"limit": 4})).structured_content
    assert out["sections"][0] == {
        "id": 1,
        "title": "شگفت\u200cانگیزها",
        "flash_sale": True,
        "ends_at": "2026-10-06T08:30:00Z",
    }
    assert [c["slug"] for c in out["campaigns"]] == ["sale07", "gift-cards"]
    assert {"text": "1 میلیون تخفیف با کد: hana70", "shop": "هانا گالری"} in out["discount_codes"]
    pcts = [d["discount_pct"] for d in out["deals"]]
    assert out["count"] == 8 and len(pcts) == 4 and pcts == sorted(pcts, reverse=True) and pcts[0] == 69
    assert out["deals"][0]["flash_sale"] is True and out["deals"][0]["section"] == "شگفت\u200cانگیزها"


async def test_sh_campaign(client, api):
    api[f"{APP}/landings/sale07/"] = fixture("landing.json")
    out = (await client.call_tool("sh_campaign", {"slug": "sale07", "per_row": 2})).structured_content
    assert out["title"] == "فروش ویژه مهر" and out["url"] == "https://shopino.app/landing/sale07"
    assert out["rows"][0]["title"] == "لباس میخری با تخفیف بالا" and out["rows"][0]["count"] == 3
    assert len(out["rows"][0]["products"]) == 2
    assert out["tabs"][0] == {"title": "چرمی\u200cهای پاییزه", "listing": "چرمی-های-پاییزه"}
    assert {"title": "پاییزه\u200cهای جدید", "shop_id": 7785} in out["tabs"]
