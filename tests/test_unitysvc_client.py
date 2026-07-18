from __future__ import annotations

import httpx
import pytest

from unitysvc_mcp.settings import Settings
from unitysvc_mcp.unitysvc_client import UnitySvcClient

CUSTOMER_BASE = "https://customer.test/v1"
SELLER_BASE = "https://seller.test/v1"

SERVICE_ROW = {
    "id": "0f2f0f9e-1111-4222-8333-444444444401",
    "name": "svc-a",
    "display_name": "Service A",
    "service_type": "llm",
    "gateway_type": "http",
}

# ServicePublic requires id/seller_id/offering_id/listing_id/status/created_at.
SELLER_ROW = {
    "id": "0f2f0f9e-1111-4222-8333-444444444401",
    "seller_id": "0f2f0f9e-1111-4222-8333-444444444402",
    "offering_id": "0f2f0f9e-1111-4222-8333-444444444403",
    "listing_id": "0f2f0f9e-1111-4222-8333-444444444404",
    "status": "active",
    "created_at": "2026-07-01T00:00:00+00:00",
    "name": "svc-a",
    "display_name": "Service A",
    "service_type": "llm",
}


def _settings() -> Settings:
    # _env_file=None so a developer's local .env cannot influence the test.
    return Settings(
        _env_file=None,
        UNITYSVC_API_URL=CUSTOMER_BASE,
        UNITYSVC_SELLER_API_URL=SELLER_BASE,
    )


def _page(row: dict[str, object]) -> dict[str, object]:
    return {"data": [row], "next_cursor": "CUR2", "has_more": True}


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    """Route every SDK-constructed httpx client through a mock transport.

    The SDKs build their own httpx clients internally, so there is no seam to
    inject one — patching the constructor is the least invasive way to observe
    what they actually send.
    """
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(recording)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
    return seen


@pytest.mark.asyncio
async def test_anonymous_catalog_sends_no_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anonymous browsing goes through the customer host with no credential.

    The header must be absent rather than empty — the customer API reads an
    absent Authorization header as anonymous, and a malformed one as a 401.
    """
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=_page(SERVICE_ROW)))

    client = UnitySvcClient(_settings())
    page = await client.list_catalog_services(limit=5)

    request = seen[-1]
    assert str(request.url).startswith(CUSTOMER_BASE)
    assert request.url.path.endswith("/groups/all_services/services")
    assert "authorization" not in {k.lower() for k in request.headers}
    assert page.role == "anonymous"
    assert [s.name for s in page.data] == ["svc-a"]
    assert page.next_cursor == "CUR2"


@pytest.mark.asyncio
async def test_authenticated_catalog_uses_the_callers_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=_page(SERVICE_ROW)))

    client = UnitySvcClient(_settings())
    page = await client.list_catalog_services(api_key="svcpass_cust", limit=5)

    assert seen[-1].headers["authorization"] == "Bearer svcpass_cust"
    assert page.role == "customer"


@pytest.mark.asyncio
async def test_explicit_group_overrides_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=_page(SERVICE_ROW)))

    client = UnitySvcClient(_settings())
    await client.list_catalog_services(group="llm")

    assert seen[-1].url.path.endswith("/groups/llm/services")


@pytest.mark.asyncio
async def test_seller_listing_uses_the_seller_host_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=_page(SELLER_ROW)))

    client = UnitySvcClient(_settings())
    page = await client.list_seller_services(api_key="svcpass_sell", status="active", limit=5)

    request = seen[-1]
    assert str(request.url).startswith(SELLER_BASE)
    assert request.headers["authorization"] == "Bearer svcpass_sell"
    assert request.url.params.get("status") == "active"
    assert page.role == "seller"
