"""The Shopino style blog: search posts and read one."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from .catalog import APP, _text
from .http import SITE, api
from .product import _clip
from .registry import tool

PER_PAGE = 3  # fixed by the API (limit is ignored)


@tool("Search the style blog")
async def sh_blog_search(
    query: Annotated[
        str | None,
        Field(min_length=2, max_length=80, description="Topic, Persian, e.g. 'مدل مانتو'."),
    ] = None,
    page: Annotated[int, Field(ge=1, le=100, description="Page number, from 1 (3 posts per page).")] = 1,
) -> dict[str, Any]:
    """Search the style blog (guides and model galleries), newest first; no query = latest posts.

    Use for what is in fashion or which model to choose; read a post with sh_blog_post(slug), then sh_search.
    """
    data = await api(
        f"{APP}/blog-posts/",
        {"search": query, "ordering": "-created_at", "offset": (page - 1) * PER_PAGE},
        django=True,
    )
    return {
        "page": page,
        "has_more": bool(data.get("next")),
        "posts": [
            {
                "title": p.get("title"),
                "slug": p.get("slug"),
                "date": (p.get("created_at") or "")[:10] or None,
                "url": f"{SITE}/blog/{p.get('slug')}",
            }
            for p in data.get("results") or []
        ],
    }


@tool("Read a blog post")
async def sh_blog_post(
    slug: Annotated[
        str, Field(pattern=r"^[^/?#.%\s\\]{1,150}$", description="Post slug from sh_blog_search, e.g. 'مدل-مانتو-شب'.")
    ],
    max_chars: Annotated[
        int, Field(ge=500, le=20000, description="Cut text after this many characters; up to 20000 for long posts.")
    ] = 4000,
) -> dict[str, Any]:
    """Read one blog post as plain text, with its category id for sh_browse (after sh_blog_search)."""
    p = await api(f"{APP}/blog-posts/{slug}/", django=True)
    out = {
        "title": p.get("title"),
        "date": (p.get("created_at") or "")[:10] or None,
        "category_id": int(p["category"]) if str(p.get("category") or "").isdigit() else None,
        "text": _clip(_text(p.get("content")), max_chars),
        "url": f"{SITE}/blog/{p.get('slug') or slug}",
    }
    return {k: v for k, v in out.items() if v is not None}
