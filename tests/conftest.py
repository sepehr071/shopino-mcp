import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from shopino_mcp import http
from shopino_mcp.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    """A recorded (trimmed) response, parsed JSON."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fresh_http_client():
    """The shared httpx client is bound to one event loop; each test gets a new loop."""
    http.set_transport(None)
    yield
    http.set_transport(None)


@pytest.fixture
def api():
    """Route table for a fake Shopino API (both hosts).

    Keys are decoded URL paths (api["/api/v1/app/initial-info/"]). Values: a dict/list (JSON) or a
    callable(request) -> httpx.Response. Unknown paths return 404 with an empty body, like the Go
    host. Every request is appended to api.calls.
    """

    class Routes(dict):
        calls: list[httpx.Request]

        def params(self, i: int = -1) -> dict[str, str]:
            return dict(self.calls[i].url.params)

        def hosts(self) -> list[str]:
            return [c.url.host for c in self.calls]

    routes = Routes()
    routes.calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        routes.calls.append(request)
        target = routes.get(request.url.path)
        if target is None:
            return httpx.Response(404)
        if callable(target):
            return target(request)
        return httpx.Response(200, json=target)

    http.set_transport(httpx.MockTransport(handler))
    return routes


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c
