"""The seller context cache — lazy load, then a TTL window."""

from __future__ import annotations

import pytest

from unitysvc_mcp.seller_context import SellerContext, SellerContextCache, SellerServiceInfo
from unitysvc_mcp.settings import Settings


class _FakeApi:
    """Counts fetches so we can prove the cache hits vs. refetches."""

    def __init__(self) -> None:
        self.calls = 0

    async def list_service_infos(self, *, api_key: str | None) -> list[SellerServiceInfo]:
        self.calls += 1
        return [SellerServiceInfo(id="s1", name="svc-1", status="draft")]


def _settings(ttl: int = 300) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        UNITYSVC_SELLER_API_KEY="svcpass_sell",
        UNITYSVC_SELLER_CONTEXT_TTL=str(ttl),
    )


@pytest.mark.asyncio
async def test_get_loads_the_inventory_into_a_snapshot() -> None:
    api = _FakeApi()
    context = await SellerContextCache(api, _settings()).get()  # type: ignore[arg-type]

    assert isinstance(context, SellerContext)
    assert context.services[0].id == "s1"
    assert context.services[0].status == "draft"
    assert api.calls == 1


@pytest.mark.asyncio
async def test_cache_serves_a_second_get_within_the_ttl() -> None:
    api = _FakeApi()
    cache = SellerContextCache(api, _settings(ttl=300))  # type: ignore[arg-type]

    await cache.get()
    await cache.get()

    assert api.calls == 1  # second served from cache


@pytest.mark.asyncio
async def test_cache_refetches_after_expiry() -> None:
    api = _FakeApi()
    cache = SellerContextCache(api, _settings(ttl=0))  # type: ignore[arg-type]

    await cache.get()
    await cache.get()

    assert api.calls == 2  # ttl=0 → always expired
