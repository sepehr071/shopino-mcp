"""Shops: find shops by name, category or city, and one shop's profile with ratings and buyer surveys."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal

from pydantic import Field

from .catalog import APP, _categories
from .http import SITE, api
from .product import _shop
from .registry import tool

ORDERS = {"relevance": None, "most_followed": "-followers", "newest": "-lived_at"}


@tool("Find shops")
async def sh_shops(
    query: Annotated[
        str | None, Field(min_length=2, max_length=60, description="Shop name, e.g. 'پاپیون' or 'papion'.")
    ] = None,
    category_group: Annotated[
        Literal["clothing", "shoes-and-bags", "accessory"] | None, Field(description="Only shops selling this group.")
    ] = None,
    gender: Annotated[Literal["women", "men"] | None, Field(description="Only women's or men's shops.")] = None,
    order: Annotated[
        Literal["relevance", "most_followed", "newest"],
        Field(description="relevance (Shopino's order), most_followed (Instagram followers) or newest on Shopino."),
    ] = "relevance",
    city: Annotated[
        str | None,
        Field(min_length=2, max_length=40, description="Only shops with same-day courier delivery here, e.g. 'تهران'."),
    ] = None,
    page: Annotated[int, Field(ge=1, le=200, description="Page number, from 1.")] = 1,
    limit: Annotated[int, Field(ge=1, le=50, description="Shops per page.")] = 20,
) -> dict[str, Any]:
    """Find Shopino shops (online and Instagram shops) by name, category group, gender or courier city,
    with rating, number of buyer surveys, followers and product count.

    Use to get a shop_id for sh_shop / sh_browse(shop_id=...) / sh_search(shop_id=...), or for
    "best-known women's clothing shops with delivery in Tehran" (order='most_followed').
    """
    data = await api(
        "/api/v2/app/shops/",
        {
            "search": query,
            "category_group": category_group,
            "base_category": gender,
            "ordering": ORDERS[order],
            "city": city,
            "limit": limit,
            "offset": (page - 1) * limit,
        },
    )
    return {
        "page": page,
        "has_more": bool(data.get("next")),
        "shops": [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "username": s.get("username"),
                "rating": s.get("rating") or None,
                "surveys": s.get("surveys_count") or 0,
                "followers": s.get("followers") or None,
                "products_count": s.get("products_count"),
                **({"courier_city": s["fast_delivery_city"]} if s.get("fast_delivery_city") else {}),
                "shopino_cart": s.get("direct_purchase_enabled"),
                "url": f"{SITE}/shops/{s.get('id')}",
            }
            for s in data.get("results") or []
        ],
    }


@tool("Shop profile")
async def sh_shop(
    shop: Annotated[
        str,
        Field(pattern=r"^[A-Za-z0-9._]{1,60}$", description="Shop id or username, e.g. '489' or 'papionlady'."),
    ],
    similar_shops: Annotated[bool, Field(description="Also list up to 10 similar shops.")] = False,
) -> dict[str, Any]:
    """Get a shop's profile: rating, customer rating, buyer survey (satisfied, quality, price, on-time
    delivery %), followers, product count, main categories, courier city, contacts and website.

    Use to judge whether a shop is trustworthy before buying, or to see what it sells. Its products:
    sh_browse(shop_id=...) or sh_search(shop_id=...); its brands (watch shops): sh_brands.
    """
    s, info = await asyncio.gather(api(f"{APP}/shops/{shop}/"), api(f"{APP}/initial-info/"))
    tree = _categories(info)
    out = {
        **_shop(s),
        "description": (s.get("description") or "").strip() or None,
        "categories": [
            {
                "id": c.get("category"),
                "title": (tree.get(c.get("category")) or {}).get("title"),
                "count": c.get("count"),
            }
            for c in (s.get("product_count_by_category") or [])[:12]
        ],
        "brands_count": len(s.get("brands") or []),
    }
    if similar_shops:
        similar = await api(f"{APP}/shops/{s['id']}/similar-shops/", django=True)
        out["similar_shops"] = [
            {
                "id": x.get("id"),
                "title": x.get("title"),
                "rating": x.get("rating") or None,
                "surveys": x.get("surveys_count"),
            }
            for x in similar or []
        ]
    return {k: v for k, v in out.items() if v is not None}
