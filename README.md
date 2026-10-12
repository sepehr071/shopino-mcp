<!-- mcp-name: io.github.sepehr071/shopino-mcp -->

<div align="center">

<img src="https://raw.githubusercontent.com/sepehr071/shopino-mcp/main/.github/banner.png" alt="shopino-mcp: unofficial Shopino MCP server for Claude, Cursor and Copilot" width="100%">

# shopino-mcp: Shopino MCP server for AI agents 👗

**Unofficial, read-only MCP server that lets your AI agent shop for clothes, bags and shoes across thousands of Iranian shops on Shopino (شاپینو).**<br>
Search one catalog of about 960,000 products from 10,000 online and Instagram shops, compare real prices,<br>
check which size and color is in stock, judge the shop, and catch today's flash sale, all from Claude, Cursor or Copilot.

[![PyPI](https://img.shields.io/pypi/v/shopino-mcp?color=2563eb)](https://pypi.org/project/shopino-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/shopino-mcp)](https://pypi.org/project/shopino-mcp/)
[![CI](https://github.com/sepehr071/shopino-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/shopino-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.sepehr071%2Fshopino--mcp-7c3aed)](https://registry.modelcontextprotocol.io/?q=shopino-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/shopino-mcp/blob/main/LICENSE)

[![Install in Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en/install-mcp?name=shopino&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJzaG9waW5vLW1jcCJdfQ==)
[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_shopino--mcp-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=shopino&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22shopino-mcp%22%5D%7D)

[Quick start](#quick-start) · [For AI agents](#for-ai-agents) · [What it can do](#what-it-can-do) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server for Shopino (shopino.app, شاپینو), an Iranian fashion marketplace that gathers products from thousands of online and Instagram shops. Queries work best in Persian; prices are in Toman.
- **Install:** `claude mcp add shopino -- uvx shopino-mcp` (stdio transport, needs [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+).
- **Auth:** none. Optional `SHOPINO_MCP_PROXY` sets an HTTP proxy for requests to shopino.app.
- **Access:** read-only. No login, cart, orders or likes, so no write tools exist.
- **Tools:** 14, all prefixed `sh_`. Start with `sh_find_cheapest`, `sh_search`, `sh_product`, `sh_shop` or `sh_deals`. Typical sequence: `sh_find_cheapest` → `sh_product` → `sh_shop`, then `sh_similar` to compare the same item at other shops.
- **Use when:** comparing clothing, bag and shoe prices, sizes and stock, judging a shop by its rating and buyer surveys, or checking the flash sale and discount codes.
- **Do not use when:** the user wants to buy something (no cart or checkout), or needs a shipping fee (quoted per shop and address at checkout, which needs a login).
- **Output:** compact JSON. `final_price` is what the buyer pays, `price` is before discount, `discount_pct` is a whole percent, `null` price means no price shown (usually out of stock). Pass a product's `id` from `sh_search` or `sh_browse` as `product_id` to `sh_product` and `sh_similar`, and its `shop_id` to `sh_shop`. Page with the returned `next_cursor`.
- **Machine-readable:** [`server.json`](server.json), and the catalog of all Iranian MCP servers at [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp) ([TOOLS.md](https://github.com/sepehr071/awesome-iran-mcp/blob/main/TOOLS.md), [servers.json](https://github.com/sepehr071/awesome-iran-mcp/blob/main/servers.json), [llms.txt](https://github.com/sepehr071/awesome-iran-mcp/blob/main/llms.txt)).

## Why

Shopino puts the products of about 10,000 Iranian online and Instagram shops in one place. A search for
"linen manteau" mixes out-of-stock items, colors and sizes with their own stock, shops you've never heard of,
and discount codes hidden in small labels. Finding *the cheapest one in your size from a shop you can trust*
means a lot of clicking. An agent with `shopino-mcp` does that in seconds:

> **You:** Cheapest linen manteau in stock right now, from a well-rated shop?
>
> **Agent:** *calls* `sh_find_cheapest(query="مانتو کتان")` → `sh_shop(shop="489")`
>
> | Price | Product | Shop |
> |---:|---|---|
> | **999,000** (56% off) | مانتو کتان ازالیا (1123) | وایت گالری پلاس (not rated yet) |
> | **999,000** (47% off) | مانتو کتان زنانه 442170 | صنم گالری, 4.6, same-day courier in Tehran |
> | **1,100,000** (21% off) | 6556-مانتو کتان قلبی | پاپیون لیدی, 4.9 from 3,507 buyer surveys, 92% satisfied |
>
> The two cheapest cost the same; Sanam Gallery is rated and delivers same-day in Tehran. Papion Lady costs
> 101,000 more but has the best buyer record. Want me to check which sizes are left with `sh_product`?

<sub>Real tool output from 2026-10-06; prices change all the time. Prices are in Toman.</sub>

## What it can do

- 🔎 **Search** every shop at once in Persian or English, with price, discount, stock and the selling shop
- 💸 **Find the cheapest** in-stock match for a keyword, optionally in one category or with courier delivery in your city
- 🗂️ **Browse** any category, shop, tag or curated listing sorted by price, date or biggest discount, with price range and size filters
- 📏 **Check sizes**: every color and size of a product with its own price and units left, plus the shop's size guide
- 🏪 **Judge the shop**: rating, buyer surveys (satisfied, quality, price, on-time %), followers, contacts and website
- 🪞 **Find the same item elsewhere** by photo similarity, cheapest first
- ⚡ **Catch deals**: the flash sale with its end time, best sellers, campaigns and the shops' discount codes
- 📝 **Read style guides** from the Shopino blog
- 🔒 **Read-only by design**: no login, no cart, no orders, no likes

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add shopino -- uvx shopino-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "shopino": { "command": "uvx", "args": ["shopino-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Cursor</b></summary>

Click **Install in Cursor** above, or add the Claude Desktop block to `~/.cursor/mcp.json`.
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

Click **Install in VS Code** above, or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "shopino": { "type": "stdio", "command": "uvx", "args": ["shopino-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Anything else</b></summary>

It's a standard stdio MCP server: run `uvx shopino-mcp`, or `pip install shopino-mcp` and run `shopino-mcp`.
</details>

Then just ask:

- "Cheapest women's manteau in size L under 2,000,000 Toman, from a shop with good reviews?"
- "Is this product (2578018) cheaper at another shop?"
- "What's in today's flash sale, and are there any discount codes?"
- <span dir="rtl">ارزان&zwnj;ترین کفش ورزشی سایز ۴۰ با ارسال پیک در تهران چند است؟</span>

## How it works

```text
  AI agent  (Claude, Cursor, Copilot, ...)
      │
      │  MCP over stdio
      ▼
  shopino-mcp  (runs on your machine)
      │
      │  HTTPS
      ├──────▶  api-go.shopino.app   search, products, shops, deals
      └──────▶  api.shopino.app      curated listings, similar shops, blog
```

`shopino-mcp` runs locally and calls the same public endpoints the shopino.app website uses.
There's no hosted server in between, no API key, and nothing about you is sent anywhere else.

## Tools

<details open>
<summary><b>🔎 Find products</b> (8)</summary>

| Tool | What it does |
|---|---|
| `sh_search` | Search every shop by keyword: price, discount, stock, shop; filter by category, shop, size, price, city |
| `sh_find_cheapest` | Cheapest in-stock matches for a keyword, one flat list sorted by price to pay |
| `sh_browse` | A category, shop, tag or curated listing sorted by price / date / discount, with price range and size filters |
| `sh_filters` | Size systems and sizes, sort orders, courier cities and the sub-categories of a category |
| `sh_categories` | Category tree with ids and paths, plus total product and shop counts |
| `sh_brands` | Featured official brand shops, or the brands (with ids) a watch shop sells |
| `sh_deals` | Flash sale with end time, best sellers and themed rows, biggest discount first, campaigns and discount codes |
| `sh_campaign` | A campaign page's product rows and tabs |
</details>

<details open>
<summary><b>👗 One product</b> (2)</summary>

| Tool | What it does |
|---|---|
| `sh_product` | Every color / size with its own price and units in stock, size guide, description, shop trust signals, original link |
| `sh_similar` | Products that look like this one at other shops (cheapest first), or Shopino's related products |
</details>

<details open>
<summary><b>🏪 Shops</b> (2)</summary>

| Tool | What it does |
|---|---|
| `sh_shops` | Find shops by name, category group, gender or courier city, with rating, surveys and followers |
| `sh_shop` | A shop's rating, buyer survey, followers, main categories, contacts, website and similar shops |
</details>

<details open>
<summary><b>📝 Blog</b> (2)</summary>

| Tool | What it does |
|---|---|
| `sh_blog_search` | Style guides and model galleries from the Shopino blog |
| `sh_blog_post` | One blog post as plain text |
</details>

All 14 tools are annotated `readOnlyHint: true` and return compact structured JSON, so they don't flood the agent's context.

## Good to know

- **Prices are in Toman.** `final_price` is what you pay, `price` is before discount, `discount_pct` is a whole percent. `null` means the shop shows no price (usually out of stock).
- **Every product has an `image`** (absolute https URL of its first photo); `sh_product` also gives up to 4 in `images`.
- **Sizes and colors can differ in price and stock.** A product's `final_price` is its cheapest variant; `sh_product` lists each color / size with its own price and `stock` (units left).
- **Each product is sold by one shop.** Many can be bought in the Shopino cart; `shop_site_only` / `shopino_cart: false` means only on the shop's own site (`original_url`).
- **Shipping is not public.** It is quoted per shop and address at checkout (needs a login), so the order total is items + the shop's shipping − one discount code. `courier_city` means same-day courier delivery in that city.
- **Discount codes** come from the shops' promotion labels (`promo`, e.g. "1 میلیون تخفیف با کد: hana70"); one code per order, entered at checkout.
- **Some "before" prices are inflated.** A 90% discount can be real or a made-up list price; compare with `sh_similar`.
- **Flash-sale items sort and filter on their pre-sale price.** Shopino ranks `flash_sale` items by their usual price,
  so in a "cheapest" list or a price range they can show up below the range or out of order (the site shows them the same way).
- **Two shop ratings.** `rating` / `surveys` come from Shopino's buyer surveys; the stars the site shows next to a shop
  are `customer_rating` (`customer_rating_count`) in `sh_product` / `sh_shop`.
- **There is no working color filter** on Shopino (the site's own color filter returns nothing); put the color in the search words.
- **Persian queries match best** (`مانتو کتان`, `کفش ورزشی مردانه`).

## FAQ

<details>
<summary><b>Can it place an order for me?</b></summary>

No, and that's deliberate. It has no login and never touches the cart, checkout, discount code, like, follow, board,
review or ticket endpoints. The agent finds the best option; you buy it on shopino.app or the shop's own site.
</details>

<details>
<summary><b>Is there a Shopino API or MCP server for AI agents?</b></summary>

Shopino doesn't publish an official API for agents. `shopino-mcp` is an unofficial MCP server that wraps the public
endpoints of shopino.app as 14 read-only tools, so any MCP client can search and compare products.
</details>

<details>
<summary><b>How do I use Shopino with Claude, Cursor or Copilot?</b></summary>

Install the server once (see [Quick start](#quick-start)), then ask in plain language, in Persian or English. In Claude Code
the install is `claude mcp add shopino -- uvx shopino-mcp`.
</details>

<details>
<summary><b>Is it official, safe and free?</b></summary>

It is unofficial and free (MIT). It is read-only, needs no account or API key, and runs on your machine with no
hosted server in between.
</details>

<details>
<summary><b>How do I get more results?</b></summary>

`sh_search` and `sh_browse` return a `next_cursor`. Pass it back as `cursor` with the same other arguments for the
next page. (Shopino's own `page` numbers drop the sort order, so this server pages with the API's cursor.)
</details>

<details>
<summary><b>Why does <code>sh_find_cheapest</code> skip some items?</b></summary>

It keeps only in-stock items with a price whose title or shop name contains every word of your query
(`match_all_words: false` turns that off). It scans up to 400 results, cheapest first; `complete: false` means more
matches lie past that, so raise `scan` (up to 1,000) or narrow with `category_id`.
</details>

<details>
<summary><b>I get "Could not reach shopino.app"</b></summary>

The server retries a dropped connection once. If it still fails, check your internet connection. System proxy
variables are ignored on purpose; set `SHOPINO_MCP_PROXY` if you need a proxy.
</details>

<details>
<summary><b>Claude Desktop says <code>uvx</code> is not found</b></summary>

Use the full path to `uvx` (`where uvx` on Windows, `which uvx` on macOS/Linux) as `command`.
</details>

<details>
<summary><b>How do I debug what the agent sees?</b></summary>

```bash
npx @modelcontextprotocol/inspector uvx shopino-mcp
```
</details>

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SHOPINO_MCP_PROXY` | unset | HTTP proxy for every request, e.g. `http://user:pass@host:port` |

<a id="فارسی"></a>

## فارسی: سرور MCP شاپینو

<div dir="rtl">

**shopino-mcp** یک سرور MCP غیررسمی برای بازار اینترنتی ایرانی شاپینو است و به دستیار هوش مصنوعی شما (Claude، Cursor، Copilot و ...) اجازه می&zwnj;دهد در شاپینو، میان محصولات هزاران
فروشگاه اینترنتی و اینستاگرامی جستجو کند، ارزان&zwnj;ترین محصول موجود را پیدا کند، موجودی هر رنگ و سایز را ببیند،
امتیاز و نظرسنجی خریداران هر فروشگاه را بررسی کند و تخفیف&zwnj;های شگفت&zwnj;انگیز و کدهای تخفیف را پیدا کند.

- فقط خواندنی است: وارد حساب نمی&zwnj;شود، سبد خرید نمی&zwnj;سازد، سفارش ثبت نمی&zwnj;کند و چیزی را لایک نمی&zwnj;کند.
- قیمت&zwnj;ها به تومان است.
- روی سیستم خود شما اجرا می&zwnj;شود و به هیچ سرور واسطی داده نمی&zwnj;فرستد.

**نصب در Claude Code:**

</div>

```bash
claude mcp add shopino -- uvx shopino-mcp
```

<div dir="rtl">

بعد بپرسید: «ارزان&zwnj;ترین مانتو کتان زنانه سایز L زیر ۲ میلیون تومان از یک فروشگاه خوش&zwnj;نام کدام است؟»

برای جستجو کافی است محصول را به فارسی بنویسید و در صورت نیاز سایز، شهر یا فروشگاه را اضافه کنید، مثلاً «کفش ورزشی مردانه سایز ۴۰ با پیک در تهران».

</div>

## Development

```bash
git clone https://github.com/sepehr071/shopino-mcp && cd shopino-mcp
uv sync
uv run pytest            # offline, against recorded responses
uv run pytest -m live    # real shopino.app
uv run ruff check .
```

Tools live in `src/shopino_mcp/catalog.py`, `product.py`, `shop.py` and `info.py`; each is a typed async function with a
docstring that tells the agent when to use it. Issues and PRs are welcome, especially new tools and fixes for site changes.

Releases: bump the version in `pyproject.toml` and `server.json`, then push a `v*` tag. GitHub Actions tests,
publishes to PyPI and the [MCP Registry](https://registry.modelcontextprotocol.io), and creates the GitHub Release.

## Related servers

- [Khanoumi MCP server](https://github.com/sepehr071/khanoumi-mcp) for cosmetics and skin care prices
- [Asal Banoo MCP server](https://github.com/sepehr071/asalbanoo-mcp) for skin care, hair care and make-up
- All Iranian MCP servers: [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp)

If this saves you clicks, a star helps others find it.

## Disclaimer

Unofficial and not affiliated with or endorsed by Shopino. It uses the public endpoints of the shopino.app
website, which can change without notice. Please keep request rates reasonable.

## License

[MIT](https://github.com/sepehr071/shopino-mcp/blob/main/LICENSE)
