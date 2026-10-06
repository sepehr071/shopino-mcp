"""Finding products: search, cheapest offers, category / shop / tag / listing browsing, filters, categories,
brands, deals and campaigns."""

from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urlparse

from pydantic import Field

from .http import SITE, ApiError, api
from .registry import tool

APP = "/api/v1/app"

Query = Annotated[
    str,
    Field(
        min_length=2,
        max_length=100,
        description="Product name or keyword, Persian works best, e.g. 'مانتو کتان' or 'کفش ورزشی'.",
    ),
]
CategoryId = Annotated[
    int | None,
    Field(
        ge=1,
        le=100_000,
        description="Category id from sh_categories, e.g. 385 (women's manteaus); includes sub-categories.",
    ),
]
SlugText = Annotated[str | None, Field(pattern=r"^[^/?#.%\s\\]{1,100}$")]
MinPrice = Annotated[int | None, Field(ge=0, description="Minimum price to pay in Toman, e.g. 500000.")]
MaxPrice = Annotated[int | None, Field(ge=1, description="Maximum price to pay in Toman, e.g. 2000000.")]
InStock = Annotated[bool, Field(description="Only products in stock now.")]
Discounted = Annotated[bool, Field(description="Only discounted products.")]
City = Annotated[
    str | None,
    Field(
        min_length=2,
        max_length=40,
        description="Only shops with same-day courier delivery in this city, e.g. 'تهران' (list in sh_filters).",
    ),
]

SORTS = {
    "relevance": None,
    "cheapest": "price",
    "most_expensive": "-price",
    "newest": "-datetime",
    "biggest_discount": "-discount",
}
Sort = Annotated[
    Literal["relevance", "cheapest", "most_expensive", "newest", "biggest_discount"],
    Field(
        description="Order: relevance (Shopino's ranking), cheapest / most_expensive (price to pay), newest, biggest_discount."
    ),
]

# The size filter of the site (bundle constant): size system -> allowed values.
SIZES: dict[str, list[str]] = {
    "standard": "2XS,XS,S,M,L,XL,2XL,3XL,4XL,5XL".split(","),
    "european": "32,34,36,38,40,42,44,46,48,50,52,54,56+".split(","),
    "shoe": [str(n) for n in range(30, 48)],
    "kid_shoe": [str(n) for n in range(20, 37)],
    "pants": "26,27,28,29,30,31,32,33,34,36,38,40,42,44,46,48,50,52".split(","),
    "underwear": [str(n) for n in range(60, 111, 5)],
    "baby": ["0-3", "3-6", "6-9", "9-12", "12-24"],  # months
    "kid": ["1-3", "3-5", "5-7", "7-9", "9-15"],  # years
}
SIZE_TITLES = {
    "standard": "استاندارد (لباس)",
    "european": "اروپایی (لباس)",
    "shoe": "کفش",
    "kid_shoe": "کفش کودک",
    "pants": "شلوار",
    "underwear": "لباس زیر",
    "baby": "نوزاد (ماه)",
    "kid": "کودک (سال)",
}
SizeSystem = Annotated[
    Literal["standard", "european", "shoe", "kid_shoe", "pants", "underwear", "baby", "kid", "freesize"] | None,
    Field(
        description="Size system for `sizes` (values in sh_filters): standard (S, M, L...), european (38, 40...), shoe, kid_shoe, pants, underwear, baby, kid; freesize = only free-size items."
    ),
]
Cursor = Annotated[
    str | None,
    Field(
        pattern=r"^[A-Za-z0-9_%=&.~+-]{1,600}$",
        description="next_cursor of the previous reply, for the next page (keep the other arguments the same).",
    ),
]
# Query keys of a list's `next` URL that carry the paging state. Product lists must be paged this way:
# the product feed answers `page=N` in its default ranking, ignoring `sort`, and search ignores `page`.
PAGING_KEYS = ("cursor", "search_seed", "c", "fid", "videos_after", "page", "offset")
Sizes = Annotated[
    list[Annotated[str, Field(pattern=r"^[0-9A-Z+-]{1,6}$")]] | None,
    Field(max_length=10, description="Sizes in the chosen size_system (any of them), e.g. ['M', 'L'] or ['40']."),
]


@tool("Search products")
async def sh_search(
    query: Query,
    sort: Sort = "relevance",
    in_stock_only: InStock = True,
    discounted_only: Discounted = False,
    min_price: MinPrice = None,
    max_price: MaxPrice = None,
    category_id: CategoryId = None,
    shop_id: Annotated[
        int | None, Field(ge=1, description="Search inside one shop (id from sh_shops / sh_shop), e.g. 489.")
    ] = None,
    size_system: SizeSystem = None,
    sizes: Sizes = None,
    city: City = None,
    cursor: Cursor = None,
    limit: Annotated[int, Field(ge=1, le=60, description="Products per page.")] = 20,
) -> dict[str, Any]:
    """Search products across all Shopino shops by keyword: price to pay, discount, stock and selling shop.

    Use first for "price of X" / "where can I buy X". Narrow with category_id (sh_categories),
    shop_id, size, price range or city (same-day courier). For the cheapest matches in one flat list
    use sh_find_cheapest. Sizes, colors and stock per variant: sh_product. More results: pass
    next_cursor back as cursor (keep the other arguments the same).
    """
    _check_range(min_price, max_price)
    params = _filters(
        sort=sort,
        in_stock_only=in_stock_only,
        discounted_only=discounted_only,
        min_price=min_price,
        max_price=max_price,
        category_id=category_id,
        size_system=size_system,
        sizes=sizes,
        city=city,
    )
    params.update(page_size=limit, shop_ids=shop_id, **_cursor_params(cursor))
    data = await api(f"{APP}/products/search/{quote(query.strip(), safe='')}/", params)
    return {"next_cursor": _next_cursor(data.get("next")), "products": _items(data.get("results"))}


@tool("Find cheapest product")
async def sh_find_cheapest(
    query: Query,
    category_id: CategoryId = None,
    city: City = None,
    match_all_words: Annotated[
        bool, Field(description="Keep only products whose title or shop name contains every word of the query.")
    ] = True,
    scan: Annotated[
        int, Field(ge=50, le=1000, description="Max search results to scan, cheapest first, 200 per request.")
    ] = 400,
    limit: Annotated[int, Field(ge=1, le=50, description="Max offers to return.")] = 20,
) -> dict[str, Any]:
    """Find the cheapest in-stock products for a keyword across all shops, one flat list sorted by price to pay (Toman).

    Use when the user wants the lowest price for X. The site sorts in-stock matches by price to pay;
    this drops loose matches whose title lacks a query word (match_all_words) and items without a
    price. Narrow with category_id (sh_categories) or city. A product's price is its cheapest
    variant: check the wanted size / color with sh_product. complete=false: matches go on past
    `scanned`, raise scan.
    """
    words = _norm(query).split()
    offers: list[dict[str, Any]] = []
    scanned, cursor, done = 0, None, False
    params = _filters(sort="cheapest", in_stock_only=True, category_id=category_id, city=city)
    while scanned < scan:
        page_params = {**params, "page_size": min(200, scan - scanned), **_cursor_params(cursor)}
        data = await api(f"{APP}/products/search/{quote(query.strip(), safe='')}/", page_params)
        items = data.get("results") or []
        scanned += len(items)
        for p in items:
            text = _norm(f"{p.get('title') or ''} {(p.get('shop') or {}).get('title') or ''}")
            if (p.get("discounted_price") or p.get("price")) and (not match_all_words or all(w in text for w in words)):
                offers.append(_item(p))
        cursor = _next_cursor(data.get("next"))
        done = not items or not cursor
        # Sorted by price: once `limit` offers are in, later pages only hold dearer ones.
        if len(offers) >= limit or done:
            break
    offers = _dedupe(offers)
    offers.sort(key=lambda o: o["final_price"] or 0)
    return {"scanned": scanned, "complete": len(offers) >= limit or done, "offers": offers[:limit]}


@tool("Browse a category, shop, tag or listing")
async def sh_browse(
    category_id: CategoryId = None,
    shop_id: Annotated[
        int | None, Field(ge=1, description="List one shop's products (id from sh_shops / sh_shop), e.g. 489.")
    ] = None,
    tag: Annotated[
        SlugText,
        Field(
            description="Product tag slug from sh_product `tags`, e.g. 'مانتو-بلند-مشکی-زنانه'. Only sort, in_stock_only and discounted_only apply."
        ),
    ] = None,
    listing: Annotated[
        SlugText,
        Field(
            description="Curated listing slug from sh_campaign tabs, e.g. 'پیراهن-مردانه'. Only sort, in_stock_only and discounted_only apply."
        ),
    ] = None,
    sort: Sort = "relevance",
    in_stock_only: InStock = True,
    discounted_only: Discounted = False,
    min_price: MinPrice = None,
    max_price: MaxPrice = None,
    size_system: SizeSystem = None,
    sizes: Sizes = None,
    brand_id: Annotated[
        int | None,
        Field(ge=1, description="Brand id from sh_brands(shop_id=...) (watch brands), e.g. 12 (Tommy Hilfiger)."),
    ] = None,
    city: City = None,
    cursor: Cursor = None,
    limit: Annotated[int, Field(ge=1, le=60, description="Products per page (a tag always gives 16 per page).")] = 24,
) -> dict[str, Any]:
    """List products of a category, a shop, a product tag or a curated listing, with sorting, price range and filters.

    Use for "cheapest women's manteau in size L under 2,000,000 Toman", "newest products of shop X",
    "biggest discounts in bags" (discounted_only + biggest_discount). With no category / shop / tag /
    listing it browses all shops (e.g. today's discounts). Ids: sh_categories, sh_shops, sh_brands;
    size values: sh_filters. Details of a product: sh_product. More results: pass next_cursor back
    as cursor with the same other arguments.
    """
    if sum(x is not None for x in (shop_id, tag, listing)) > 1:
        raise ApiError("Pass at most one of shop_id, tag or listing.")
    _check_range(min_price, max_price)
    if tag or listing:
        extra = {
            "category_id": category_id,
            "min_price": min_price,
            "max_price": max_price,
            "size_system / sizes": size_system or sizes,
            "brand_id": brand_id,
            "city": city,
        }
        if unsupported := [k for k, v in extra.items() if v is not None]:
            raise ApiError(f"{'A tag' if tag else 'A listing'} does not support: {', '.join(unsupported)}.")
        if tag:  # 16 per page, page_size and in_stock ignored: stock is filtered below
            params = {"sort": SORTS[sort], "off": _flag(discounted_only), **_cursor_params(cursor)}
            data = await api(f"{APP}/product-tags/{tag}/products/", params)
        else:  # no `off` filter: discounts are filtered below
            params = {"sort": SORTS[sort], "in_stock": _flag(in_stock_only), "limit": limit, **_cursor_params(cursor)}
            data = await api(f"{APP}/product-listings/{listing}/products/", params, django=True)
        items = _items(data.get("results"))
        kept = [i for i in items if (i["in_stock"] or not in_stock_only) and (i["discount_pct"] or not discounted_only)]
        return {"next_cursor": _next_cursor(data.get("next")) if items else None, "products": kept}
    params = _filters(
        sort=sort,
        in_stock_only=in_stock_only,
        discounted_only=discounted_only,
        min_price=min_price,
        max_price=max_price,
        category_id=category_id,
        size_system=size_system,
        sizes=sizes,
        brand_id=brand_id,
    )
    params.update(page_size=limit, **_cursor_params(cursor))
    if shop_id is not None:
        if city:
            raise ApiError("city does not apply to one shop: see the shop's courier_city in sh_shop.")
        data = await api(f"{APP}/shops/{shop_id}/products/", params)
    else:
        data = await api(f"{APP}/products/recommendation/", {**params, "city": city})
    items = _items(data.get("results"))
    return {"next_cursor": _next_cursor(data.get("next")) if items else None, "products": items}


@tool("Filters for listings")
async def sh_filters(
    category_id: Annotated[
        int | None, Field(ge=1, le=100_000, description="Category id from sh_categories: adds its sub-categories.")
    ] = None,
) -> dict[str, Any]:
    """List the filter values sh_search / sh_browse accept: size systems with their sizes, sort orders,
    cities with same-day courier delivery, and (with category_id) the sub-categories of a category.

    Use before filtering by size or city. Price range is free (Toman); brand ids (watches only) come
    from sh_brands. Shopino has no color filter that works (the site's own color filter returns nothing).
    """
    info, cities = await asyncio.gather(api(f"{APP}/initial-info/"), api(f"{APP}/cities-list/", django=True))
    out: dict[str, Any] = {}
    if category_id is not None:
        tree = _categories(info)
        if category_id not in tree:
            raise ApiError(f"No category {category_id} on Shopino. Get ids from sh_categories.")
        out["category"] = tree[category_id]
        out["sub_categories"] = [c for c in tree.values() if c["parent_id"] == category_id]
    return {
        **out,
        "sorts": list(SORTS),
        "size_systems": {k: {"title": SIZE_TITLES[k], "sizes": v} for k, v in SIZES.items()},
        "freesize": "size_system='freesize' (no sizes) = only free-size items",
        "courier_cities": cities,
    }


@tool("List categories")
async def sh_categories(
    query: Annotated[
        str | None,
        Field(
            min_length=2,
            description="Optional filter on the Persian name or English slug path, any level, e.g. 'مانتو' or 'sneakers'.",
        ),
    ] = None,
    max_level: Annotated[
        int, Field(ge=1, le=5, description="Deepest level to list when no query is given (1 = the 14 top categories).")
    ] = 2,
) -> dict[str, Any]:
    """List Shopino's category tree (clothing, bags, shoes, accessories, watches, jewelry, gold, cosmetics, ...)
    with ids, URL paths and levels, plus the total product and shop counts.

    Use to get a category_id for sh_search / sh_browse / sh_find_cheapest. Without a query only
    levels up to max_level are listed; with a query every level is searched.
    """
    info = await api(f"{APP}/initial-info/")
    categories = list(_categories(info).values())
    if query:
        q = _norm(query)
        categories = [c for c in categories if q in _norm(c["title"]) or q in c["path"].lower()]
    else:
        categories = [c for c in categories if c["level"] <= max_level]
    categories.sort(key=lambda c: c["path"])
    return {
        "products_count": info.get("products_count"),
        "shops_count": info.get("shops_count"),
        "categories": categories,
    }


@tool("Brands")
async def sh_brands(
    shop_id: Annotated[
        int | None, Field(ge=1, description="A shop id (e.g. 1771, a watch shop) to list its brands with brand ids.")
    ] = None,
) -> dict[str, Any]:
    """Without shop_id: the official brand shops Shopino features (each is a shop: browse it with
    sh_browse(shop_id=...)). With shop_id: the brands that shop sells, with brand ids for the brand_id
    filter of sh_search / sh_browse (only watch shops have brands).

    Use for "show me brand X" (find its shop) or to filter a watch shop by brand.
    """
    if shop_id is None:
        data = await api(f"{APP}/featured-brands/")
        return {
            "brand_shops": [
                {
                    "shop_id": b.get("id"),
                    "title": b.get("title"),
                    "rating": b.get("rating") or None,
                    "surveys": b.get("surveys_count"),
                    "url": f"{SITE}/shops/{b.get('id')}",
                }
                for b in data or []
            ]
        }
    shop = await api(f"{APP}/shops/{shop_id}/")
    return {
        "shop": shop.get("title"),
        "brands": [
            {"id": b.get("id"), "name": b.get("title_fa"), "name_en": b.get("title_en"), "count": b.get("count")}
            for b in shop.get("brands") or []
        ],
    }


@tool("Deals, flash sale and campaigns")
async def sh_deals(
    limit: Annotated[int, Field(ge=1, le=100, description="Max deals to return.")] = 30,
) -> dict[str, Any]:
    """List today's featured deals from the Shopino home page: the flash sale (شگفت انگیز) with its end
    time, best sellers, newest and themed rows, biggest discount first, plus running campaigns and the
    shop discount codes seen on those products.

    Use for "what's on sale" / "best discounts today". Open a campaign with sh_campaign(slug); for
    every discounted product of a category use sh_browse(discounted_only=true, sort='biggest_discount').
    """
    sliders, banners = await asyncio.gather(api(f"{APP}/product-sliders/"), api(f"{APP}/banners/"))
    sections, deals, seen, codes = [], [], set(), {}
    for s in sliders or []:
        title = (s.get("title_simple") or "").strip()
        sections.append(
            {
                "id": s.get("id"),
                "title": title,
                "flash_sale": bool(s.get("flash_sale")),
                **({"ends_at": s["ends_at"]} if s.get("ends_at") else {}),
            }
        )
        for p in s.get("products") or []:
            item = _item(p)
            if item.get("promo"):
                codes.setdefault(item["promo"], item["shop"])
            if item["id"] not in seen and item["discount_pct"]:
                seen.add(item["id"])
                deals.append({**item, "section": title})
    deals.sort(key=lambda d: -d["discount_pct"])
    campaigns: dict[str, None] = {}
    for b in banners or []:
        if m := re.search(r"/landing/([^/?#]+)", b.get("target_url") or ""):
            campaigns[m.group(1)] = None
    return {
        "sections": sections,
        "campaigns": [{"slug": c, "url": f"{SITE}/landing/{c}"} for c in campaigns],
        "discount_codes": [{"text": t, "shop": s} for t, s in codes.items()],
        "count": len(deals),
        "deals": deals[:limit],
    }


@tool("Campaign page")
async def sh_campaign(
    slug: Annotated[
        str,
        Field(
            pattern=r"^[A-Za-z0-9_-]{1,60}$",
            description="Campaign / landing slug from sh_deals campaigns, e.g. 'sale07', or a top category's: 'clothing', 'bag', 'shoes', 'sports'.",
        ),
    ],
    per_row: Annotated[int, Field(ge=1, le=12, description="Products to show per product row.")] = 6,
) -> dict[str, Any]:
    """Open a Shopino campaign or landing page: its product rows (with prices) and its tabs.

    Each tab names where its products come from: `listing` -> sh_browse(listing=...), `shop_id` ->
    sh_browse(shop_id=...), `category_id` -> sh_browse(category_id=...), `flash_sale` -> sh_deals.
    """
    data = await api(f"{APP}/landings/{slug}/")
    rows, tabs = [], []
    for c in data.get("components") or []:
        if c.get("type") == "product_slider":
            s = c.get("product_slider") or {}
            products = _items(s.get("products"))
            rows.append(
                {"title": (s.get("title_simple") or "").strip(), "count": len(products), "products": products[:per_row]}
            )
        for t in c.get("tabs") or []:
            source = {
                "listing": t.get("listing_slug"),
                "shop_id": t.get("shop_id"),
                "category_id": t.get("category_id"),
                "flash_sale": t.get("flash_sale") or None,
                "filters": t.get("filters") or None,
            }
            tabs.append({"title": t.get("title"), **{k: v for k, v in source.items() if v}})
    return {
        "title": data.get("title"),
        "slug": data.get("slug"),
        "rows": rows,
        "tabs": tabs,
        "url": f"{SITE}/landing/{slug}",
    }


def _filters(
    *,
    sort: str = "relevance",
    in_stock_only: bool = False,
    discounted_only: bool = False,
    min_price: int | None = None,
    max_price: int | None = None,
    category_id: int | None = None,
    size_system: str | None = None,
    sizes: list[str] | None = None,
    brand_id: int | None = None,
    city: str | None = None,
) -> dict[str, Any]:
    """The list filters shared by search, product feed and shop products."""
    return {
        "category": category_id,
        "sort": SORTS[sort],
        "off": _flag(discounted_only),
        "in_stock": _flag(in_stock_only),
        "price_from": min_price,
        "price_to": max_price,
        "sizes": _sizes(size_system, sizes),
        "brand": brand_id,
        "city": city,
    }


def _sizes(system: str | None, values: list[str] | None) -> str | None:
    """The `sizes` JSON the API takes: {"standard":["M","L"]} or {"freesize":true}."""
    if system is None:
        if values:
            raise ApiError("Pass size_system with sizes (see sh_filters).")
        return None
    if system == "freesize":
        return '{"freesize":true}'
    if not values:
        raise ApiError(f"Pass sizes for size_system '{system}': {', '.join(SIZES[system])}.")
    if bad := [v for v in values if v not in SIZES[system]]:
        raise ApiError(f"Unknown {system} sizes {bad}. Valid: {', '.join(SIZES[system])}.")
    return json.dumps({system: values}, separators=(",", ":"))


def _flag(on: bool) -> str | None:
    return "true" if on else None


def _cursor_params(cursor: str | None) -> dict[str, str]:
    params = dict(parse_qsl(cursor or ""))
    if set(params) - set(PAGING_KEYS):
        raise ApiError("Bad cursor: pass next_cursor from the previous reply unchanged.")
    return params


def _next_cursor(next_url: str | None) -> str | None:
    """The paging state of a list's `next` URL (cursor, search_seed, page, offset, ...), for the next call."""
    params = dict(parse_qsl(urlparse(next_url or "").query))
    keep = {k: params[k] for k in PAGING_KEYS if k in params}
    return urlencode(keep) if keep else None


def _items(products: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return _dedupe([_item(p) for p in products or []])


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Some shops list each color as its own card with the same product id: keep the first."""
    seen: set[int] = set()
    return [i for i in items if not (i["id"] in seen or seen.add(i["id"]))]


def _item(p: dict[str, Any]) -> dict[str, Any]:
    """A product card of a list reply (search, feed, shop, slider, similar). Prices are Toman."""
    price, final, pct = _prices(p)
    shop = p.get("shop") or {}
    out: dict[str, Any] = {
        "id": int(p["id"]),
        "title": (p.get("title") or "").strip(),
        "final_price": final,
        "price": price,
        "discount_pct": pct,
        "in_stock": bool(p.get("in_stock")),
        "shop": shop.get("title"),
        "shop_id": shop.get("id"),
    }
    if shop.get("rating"):
        out["shop_rating"] = shop["rating"]
    if shop.get("fast_delivery_city"):
        out["courier_city"] = shop["fast_delivery_city"]
    if shop.get("direct_purchase_enabled") is False:
        out["shop_site_only"] = True  # not buyable in the Shopino cart, only on the shop's own site
    if p.get("flash_sale"):
        out["flash_sale"] = True
    if promo := (p.get("promotion_tag") or {}).get("title"):
        out["promo"] = promo.strip()
    out["url"] = f"{SITE}/product/{p['id']}"
    return out


def _prices(p: dict[str, Any]) -> tuple[int | None, int | None, int]:
    """(price before discount, price to pay, discount %) in Toman; None when the shop shows no price."""
    price, discounted = p.get("price") or 0, p.get("discounted_price") or 0
    final = discounted or price
    pct = round(100 * (price - final) / price) if price and 0 < discounted < price else 0
    return (price if pct else final) or None, final or None, pct


def _categories(info: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """id -> {id, title, path, level, parent_id}; path = slugs from the root (the site URL /category/<path>)."""
    raw = {c["id"]: c for c in info.get("categories") or []}
    out = {}
    for cid, c in raw.items():
        chain, node = [], c
        while node is not None and len(chain) < 10:
            chain.append(node)
            node = raw.get(node.get("parent"))
        path = "/".join(n.get("slug") or "" for n in reversed(chain))
        out[cid] = {
            "id": cid,
            "title": c.get("title") or c.get("name"),
            "path": path,
            "level": len(chain),
            "parent_id": c.get("parent"),
            **({"landing": c["landing_slug"]} if c.get("landing_slug") else {}),
        }
    return out


def _check_range(min_price: int | None, max_price: int | None) -> None:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ApiError("min_price must be <= max_price.")


def _text(fragment: str | None) -> str:
    """HTML to plain text; table cells become 'a | b' lines."""
    s = re.sub(r"</t[dh]>", " | ", re.sub(r"\s+", " ", fragment or ""))  # source line breaks mean nothing in HTML
    s = re.sub(r"</tr>|</p>|<br\s*/?>|</li>|</h\d>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip(" |") for line in s.splitlines())
    return "\n".join(line for line in lines if line)


def _norm(s: str) -> str:
    """Match Persian text loosely: Arabic ي/ك as Persian, half-space as space, case-insensitive."""
    return re.sub(r"\s+", " ", s.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")).strip().lower()
