from __future__ import annotations

import httpx
import pytest

from unitysvc_mcp.models import Principal
from unitysvc_mcp.settings import Settings
from unitysvc_mcp.unitysvc_client import UnitySvcClient

PUBLIC_BASE = "https://public.test/v1"


def _settings() -> Settings:
    return Settings(UNITYSVC_PUBLIC_API_URL=PUBLIC_BASE)


def _catalog_page(rows: list[dict[str, object]], count: int) -> httpx.Response:
    return httpx.Response(200, json={"data": rows, "count": count})


@pytest.mark.asyncio
async def test_anonymous_listing_uses_public_host_without_auth() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        row = {
            "id": "svc-1",
            "name": "resp200",
            "display_name": "OK",
            "status": "ready",
            "currency": "USD",
        }
        return _catalog_page([row], count=1)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = UnitySvcClient(_settings(), http_client)
        page = await client.list_catalog_services(Principal(), limit=5)

    assert str(seen[0].url).startswith(f"{PUBLIC_BASE}/services/")
    # Anonymous callers must not send an Authorization header.
    assert "authorization" not in {k.lower() for k in seen[0].headers}
    assert page.role == "anonymous"
    assert [s.name for s in page.data] == ["resp200"]
    assert page.data[0].currency == "USD"


@pytest.mark.asyncio
async def test_public_listing_cursor_advances_then_stops() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params.get("skip", 0))
        rows = [{"id": f"svc-{skip}", "name": f"svc-{skip}"}] if skip < 3 else []
        return _catalog_page(rows, count=3)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = UnitySvcClient(_settings(), http_client)

        first = await client.list_catalog_services(Principal(), limit=1)
        assert first.next_cursor == "1"

        # Offset reaches the total, so pagination terminates rather than looping.
        last = await client.list_catalog_services(Principal(), limit=1, cursor="2")
        assert last.next_cursor is None


@pytest.mark.asyncio
async def test_public_listing_rejects_non_numeric_cursor() -> None:
    transport = httpx.MockTransport(lambda request: _catalog_page([], count=0))
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = UnitySvcClient(_settings(), http_client)
        with pytest.raises(ValueError):
            await client.list_catalog_services(Principal(), cursor="not-a-number")


@pytest.mark.asyncio
async def test_seller_listing_requires_a_token() -> None:
    async with httpx.AsyncClient() as http_client:
        client = UnitySvcClient(_settings(), http_client)
        with pytest.raises(PermissionError):
            await client.list_seller_services(Principal())
