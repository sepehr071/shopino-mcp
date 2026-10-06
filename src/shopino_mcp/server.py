"""MCP server entry point: registers every read-only Shopino tool."""

import logging

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import __version__, catalog, info, product, shop  # noqa: F401  (imports register the tools)
from .registry import TOOLS

INSTRUCTIONS = """\
Unofficial, read-only access to Shopino (shopino.app), an Iranian fashion marketplace that gathers the
products of about 10,000 online and Instagram shops (about 960,000 products): clothing, bags, shoes,
accessories, watches, jewelry, gold, cosmetics and more. Each product is sold by one shop; many can be
bought in the Shopino cart, others only on the shop's own site (shop_site_only / original_url). Nothing
here can log in, add to a cart, order, like, follow or post.

Workflow:
1. Find products: sh_search (keyword, sort, price range, size, city, category, one shop; page on with
   next_cursor) or sh_find_cheapest (cheapest in-stock matches, one flat list).
2. Browse with sort / price / size filters: sh_browse with a category_id (sh_categories), a shop_id
   (sh_shops), a tag (sh_product tags) or a listing (sh_campaign tabs); nothing = all shops.
   Size systems and values, sorts and courier cities: sh_filters. Brand shops and watch brand ids: sh_brands.
3. One product: sh_product (every color / size with its own price and units in stock, size guide,
   shop rating and buyer survey, original link). Same item at other shops: sh_similar (kind='visual',
   sort='cheapest').
4. Shops: sh_shops (by name, group, gender, city), sh_shop (trust signals, categories, contacts).
5. Deals: sh_deals (flash sale with end time, best sellers, campaigns, shop discount codes),
   sh_campaign (a campaign page's rows and tabs). Style advice: sh_blog_search, sh_blog_post.

Conventions: all prices are Toman. final_price is what the customer pays, price is before discount
(equal when there is none), discount_pct is an int; null prices = the shop shows no price. A product's
price is its cheapest variant: check the chosen size / color in sh_product variants (stock = units).
Shop rating is 0-5 from buyer surveys (null = not rated); the stars the site shows are customer_rating
(sh_product / sh_shop). flash_sale items are sorted and price-filtered by their pre-sale price, so they can
appear out of order or under min_price. promo is a shop's offer, often with a
discount code ('... با کد: hana70'); one code per order, entered at checkout. courier_city = same-day
courier delivery in that city. Shipping is not public: it is quoted per shop and address at checkout
(login), so the true cost is sum(final_price x qty) + the shop's shipping - discount. Returns: within
7 days of delivery, except personal items (underwear, swimwear, cosmetics, ...). Some shops post
inflated "before" prices, so check discount_pct against similar items. Persian queries match best
('مانتو کتان', 'کفش ورزشی مردانه'); there is no working color filter: put the color in the query.
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)

mcp = MCPServer(
    "shopino-mcp",
    title="Shopino",
    instructions=INSTRUCTIONS,
    version=__version__,
    website_url="https://github.com/sepehr071/shopino-mcp",
)

for fn, title in TOOLS:
    mcp.add_tool(fn, title=title, annotations=READ_ONLY)


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per request floods client logs
    mcp.run()


if __name__ == "__main__":
    main()
