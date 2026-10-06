import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

APP = "/api/v1/app"


async def test_sh_shops(client, api):
    api["/api/v2/app/shops/"] = fixture("shops.json")
    args = {"query": "پاپیون", "gender": "women", "order": "most_followed", "city": "قم", "page": 2, "limit": 3}
    out = (await client.call_tool("sh_shops", args)).structured_content
    assert out == {
        "page": 2,
        "has_more": False,
        "shops": [
            {
                "id": 489,
                "title": "پاپیون لیدی",
                "username": "papionlady",
                "rating": 4.9,
                "surveys": 3507,
                "followers": 2119755,
                "products_count": 6738,
                "courier_city": "قم",
                "shopino_cart": True,
                "url": "https://shopino.app/shops/489",
            }
        ],
    }
    assert api.params() == {
        "search": "پاپیون",
        "base_category": "women",
        "ordering": "-followers",
        "city": "قم",
        "limit": "3",
        "offset": "3",
    }


async def test_sh_shop(client, api):
    api[f"{APP}/shops/papionlady/"] = fixture("shop_489.json")
    api[f"{APP}/initial-info/"] = fixture("initial_info.json")
    api[f"{APP}/shops/489/similar-shops/"] = fixture("similar_shops.json")
    out = (await client.call_tool("sh_shop", {"shop": "papionlady", "similar_shops": True})).structured_content
    assert out["id"] == 489 and out["rating"] == 4.9 and out["survey_pct"]["satisfied"] == 92
    assert out["categories"][0] == {"id": 377, "title": "شلوار زنانه", "count": 565}
    assert out["brands_count"] == 0 and "description" not in out
    assert out["similar_shops"][0] == {"id": 8211, "title": "مارویا", "rating": None, "surveys": 0}
    # similar shops live on the Django host only
    assert api.calls[-1].url.host == "api.shopino.app"


async def test_sh_shop_rejects_paths(client, api):
    result = await client.call_tool("sh_shop", {"shop": "../products"})
    assert result.is_error and not api.calls
