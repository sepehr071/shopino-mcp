import httpx
import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

APP = "/api/v1/app"


async def test_sh_product_variants_and_stock(client, api):
    api[f"{APP}/products/2620755/"] = fixture("product_2620755.json")
    out = (await client.call_tool("sh_product", {"product_id": 2620755})).structured_content
    assert out["final_price"] == out["price"] == 4980000 and out["discount_pct"] == 0
    assert out["options"] == {"رنگ": ["استخوانی", "سرمه ای", "قهوه ای", "مشکی"], "سایز": ["1", "2"]}
    assert len(out["variants"]) == 8
    assert out["variants"][0] == {
        "id": 11038932,
        "رنگ": "قهوه ای",
        "سایز": "1",
        "final_price": 4980000,
        "price": 4980000,
        "discount_pct": 0,
        "stock": 1,
    }
    assert sum(v["stock"] for v in out["variants"]) == 10
    assert out["shop"]["title"] == "وایت گالری پلاس" and out["shop"]["shopino_cart"] is True
    assert "rating" not in out["shop"]  # 0 = not rated
    assert out["original_url"].startswith("https://whitepluss.ir/") and out["made_in_iran"] is True
    assert {"slug": "مانتو-بلند-مشکی-زنانه", "title": "مانتو بلند مشکی زنانه"} in out["tags"]
    assert "flash_sale" not in out


async def test_sh_product_flash_sale(client, api):
    # product 2529820 in the browser: flash sale, 1,899,000 -> 968,490 تومان "49% تخفیف"
    api[f"{APP}/products/2620755/"] = {
        **fixture("product_2620755.json"),
        "flash_sale": True,
        "price": 1899000,
        "discounted_price": 968490,
    }
    out = (await client.call_tool("sh_product", {"product_id": 2620755})).structured_content
    assert out["flash_sale"] is True
    assert (out["price"], out["final_price"], out["discount_pct"]) == (1899000, 968490, 49)


async def test_sh_product_discount_shop_trust_and_size_guide(client, api):
    api[f"{APP}/products/2578018/"] = fixture("product_2578018.json")
    out = (await client.call_tool("sh_product", {"product_id": 2578018})).structured_content
    # the page shows 1,478,000 -> 1,000,000 تومان with "32% تخفیف"
    assert (out["price"], out["final_price"], out["discount_pct"]) == (1478000, 1000000, 32)
    assert out["variants"] == [
        {
            "id": 10793523,
            "انتخاب رنگ": "شیری",
            "final_price": 1000000,
            "price": 1478000,
            "discount_pct": 32,
            "stock": 5,
        }
    ]
    assert out["shop"] == {
        "id": 489,
        "title": "پاپیون لیدی",
        "username": "papionlady",
        "rating": 4.9,
        "surveys": 3507,
        "customer_rating": 4.4,
        "customer_rating_count": 3725,
        "survey_pct": {"satisfied": 92, "good_quality": 97, "good_price": 96, "on_time": 95},
        "followers": 2119755,
        "products_count": 2443,
        "courier_city": "قم",
        "shopino_cart": True,
        "website": "https://papionlady.com",
        "instagram": "papion.lady",
        "phone": "02532890754",
        "url": "https://shopino.app/shops/489",
    }
    assert out["size_guide"].splitlines()[:2] == ["اندازه | فری سایز", "قد لباس | 83cm"]
    assert out["description"].startswith("جنس: لینن") and "<" not in out["description"]
    assert len(out["images"]) == 2 and out["url"] == "https://shopino.app/product/2578018"


async def test_sh_product_removed(client, api):
    api[f"{APP}/products/1/"] = lambda r: httpx.Response(410)
    result = await client.call_tool("sh_product", {"product_id": 1})
    assert result.is_error and "HTTP 410" in result.content[0].text


async def test_sh_similar_visual(client, api):
    api[f"{APP}/products/2578018/"] = fixture("product_2578018.json")
    api[f"{APP}/post-medias/2578018_05861e2e/similar-products/"] = fixture("visual.json")
    args = {"product_id": 2578018, "sort": "cheapest", "limit": 3}
    out = (await client.call_tool("sh_similar", args)).structured_content
    assert out["count"] == 5 and 2578018 not in [p["id"] for p in out["products"]]  # the product itself is left out
    assert [p["final_price"] for p in out["products"]] == [624000, 700000, 749000]
    assert api.params() == {"x": "0.025", "y": "0.025", "w": "0.95", "h": "0.95"}


async def test_sh_similar_related(client, api):
    api[f"{APP}/products/2578018/similar-products/"] = fixture("similar.json")
    out = (await client.call_tool("sh_similar", {"product_id": 2578018, "kind": "similar"})).structured_content
    assert out["count"] == 4 and out["products"][0]["id"] == 2200452 and len(api.calls) == 1
