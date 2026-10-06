import pytest
from conftest import fixture

pytestmark = pytest.mark.anyio

APP = "/api/v1/app"


async def test_sh_blog_search(client, api):
    api[f"{APP}/blog-posts/"] = fixture("blog_posts.json")
    out = (await client.call_tool("sh_blog_search", {"query": "مانتو", "page": 2})).structured_content
    assert out["has_more"] is True and len(out["posts"]) == 3
    assert out["posts"][0] == {
        "title": "مدل مانتو کتی کوتاه",
        "slug": "مدل-مانتو-کتی-کوتاه",
        "date": "2024-05-26",
        "url": "https://shopino.app/blog/مدل-مانتو-کتی-کوتاه",
    }
    assert api.params() == {"search": "مانتو", "ordering": "-created_at", "offset": "3"}
    assert api.hosts() == ["api.shopino.app"]


async def test_sh_blog_post(client, api):
    api[f"{APP}/blog-posts/مدل-مانتو-شب/"] = fixture("blog_post.json")
    out = (await client.call_tool("sh_blog_post", {"slug": "مدل-مانتو-شب", "max_chars": 500})).structured_content
    assert out["title"] == "مدل مانتو شب" and out["category_id"] == 385 and out["date"] == "2024-05-26"
    assert out["text"].startswith("مانتو، به عنوان") and out["text"].endswith("…") and len(out["text"]) == 501
    assert "<p>" not in out["text"]
