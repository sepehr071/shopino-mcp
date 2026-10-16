"""One product: details with every color / size variant and its stock, and similar products from other shops."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from .catalog import APP, _image, _items, _prices, _text
from .http import SITE, ApiError, api
from .registry import tool

ProductId = Annotated[
    int, Field(ge=1, le=100_000_000, description="Product id from sh_search / sh_browse, e.g. 2578018.")
]


@tool("Product details")
async def sh_product(
    product_id: ProductId,
    full_text: Annotated[bool, Field(description="Return size guide and description uncut.")] = False,
) -> dict[str, Any]:
    """Get one product's full record: price, every color / size variant with its own price and stock, size
    guide, description, tags, the selling shop with trust signals, and the shop-site link.

    Use when the user picks a product, to check their size / color is in stock and the shop is trustworthy.
    Same item elsewhere: sh_similar. More from the shop: sh_browse(shop_id=...). Related: sh_browse(tag=...).
    """
    p = await api(f"{APP}/products/{product_id}/")
    price, final, pct = _prices(p)
    shop = p.get("shop") or {}
    out = {
        "id": int(p["id"]),
        "title": (p.get("title") or "").strip(),
        "final_price": final,
        "price": price,
        "discount_pct": pct,
        "in_stock": bool(p.get("in_stock")),
        "category_id": p.get("category"),
        "options": {a.get("name"): a.get("options") or [] for a in p.get("attributes") or []},
        "variants": [_variant(v) for v in p.get("variations") or []],
        "freesize": bool(p.get("freesize")),
        "size_guide": _clip(_text(p.get("size_guide")), None if full_text else 800),
        "description": _clip(_text(p.get("caption")), None if full_text else 1000),
        "made_in_iran": p.get("originality") == "made_in_iran" or None,
        "likes": p.get("likes"),
        **({"flash_sale": True} if p.get("flash_sale") else {}),
        **({"promo": promo.strip()} if (promo := (p.get("promotion_tag") or {}).get("title")) else {}),
        "tags": [{"slug": t.get("slug"), "title": t.get("title")} for t in p.get("related_tags") or []],
        "image": _image(p),
        "images": [m.get("url") for m in p.get("medias") or [] if not m.get("is_video")][:4],
        "shop": _shop(shop),
        "original_url": p.get("website_url"),
        "url": f"{SITE}/product/{p['id']}",
    }
    # null prices are documented (shop shows no price); other empty fields are dropped
    return {k: v for k, v in out.items() if v is not None or k in ("final_price", "price")}


@tool("Similar products")
async def sh_similar(
    product_id: ProductId,
    kind: Annotated[
        Literal["visual", "similar"],
        Field(
            description="visual = photo-alike products from all shops (to find the same item cheaper); similar = Shopino's 10 related products."
        ),
    ] = "visual",
    sort: Annotated[
        Literal["relevance", "cheapest"], Field(description="relevance (as returned) or cheapest first.")
    ] = "relevance",
    in_stock_only: Annotated[bool, Field(description="Only products in stock now.")] = True,
    limit: Annotated[int, Field(ge=1, le=100, description="Max products to return.")] = 20,
) -> dict[str, Any]:
    """Find products like this one at other shops (itself left out).

    Use when it is out of stock or too expensive, or to find the same item cheaper (kind='visual', sort='cheapest').
    """
    if kind == "similar":
        data = await api(f"{APP}/products/{product_id}/similar-products/")
    else:
        p = await api(f"{APP}/products/{product_id}/")
        media = next((m for m in p.get("medias") or [] if m.get("id") and not m.get("is_video")), None)
        if media is None:
            raise ApiError(f"Product {product_id} has no photo to compare; try kind='similar'.")
        # The crop box is required (HTTP 500 without it); this is the site's default (the whole photo).
        crop = {"x": 0.025, "y": 0.025, "w": 0.95, "h": 0.95}
        data = (await api(f"{APP}/post-medias/{media['id']}/similar-products/", crop)).get("results")
    items = [i for i in _items(data) if i["id"] != product_id and (i["in_stock"] or not in_stock_only)]
    if sort == "cheapest":
        items = sorted((i for i in items if i["final_price"]), key=lambda i: i["final_price"])
    return {"count": len(items), "products": items[:limit]}


def _variant(v: dict[str, Any]) -> dict[str, Any]:
    """One buyable color / size combination with its own price and stock."""
    price, final, pct = _prices(v)
    return {
        "id": v.get("id"),
        **{a.get("name"): a.get("option") for a in v.get("attributes") or []},
        "final_price": final,
        "price": price,
        "discount_pct": pct,
        "stock": v.get("stock_quantity"),
    }


def _shop(s: dict[str, Any]) -> dict[str, Any]:
    """The seller, with trust signals (shared with sh_shop)."""
    customer = s.get("customer_rating") or {}
    survey = s.get("survey_report") or {}
    phone = s.get("landline_phone")
    out = {
        "id": s.get("id"),
        "title": s.get("title"),
        "username": s.get("username"),
        "rating": s.get("rating") or None,  # 0-5 from buyer surveys; 0 = not rated
        "surveys": s.get("surveys_count") or 0,
        "customer_rating": customer.get("value"),
        "customer_rating_count": customer.get("count"),
        "survey_pct": {
            "satisfied": _pct(survey.get("customer_satisfaction")),
            "good_quality": _pct(survey.get("positive_high_quality")),
            "good_price": _pct(survey.get("positive_low_price")),
            "on_time": _pct(survey.get("positive_timely_delivery")),
        }
        if survey
        else None,
        "followers": s.get("followers") or None,  # Instagram followers
        "products_count": s.get("products_count"),
        "courier_city": s.get("fast_delivery_city") or None,
        "shopino_cart": s.get("direct_purchase_enabled"),  # false = buy only on the shop's own site
        "website": s.get("website") or None,
        "instagram": s.get("instagram_username") or None,
        "phone": f"{s.get('landline_phone_prefix') or ''}{phone}" if phone else s.get("mobile_phone"),
        "url": f"{SITE}/shops/{s.get('id')}",
    }
    return {k: v for k, v in out.items() if v is not None}


def _pct(x: float | None) -> int | None:
    return round(x) if x is not None else None


def _clip(text: str, n: int | None) -> str | None:
    """Cut to n characters; n=None keeps the whole text."""
    return (text[:n] + "…" if n and len(text) > n else text) or None
