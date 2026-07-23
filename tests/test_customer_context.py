"""The customer context cache — lazy load, then a TTL window."""

from __future__ import annotations

import pytest

from unitysvc_mcp.customer_context import CustomerContext, CustomerContextCache, EnrollmentInfo
from unitysvc_mcp.settings import Settings


class _FakeApi:
    """Counts fetches so we can prove the cache hits vs. refetches."""

    def __init__(self) -> None:
        self.secret_calls = 0
        self.enrollment_calls = 0

    async def list_secret_names(self, *, api_key: str | None) -> frozenset[str]:
        self.secret_calls += 1
        return frozenset({"OPENAI_API_KEY"})

    async def list_enrollments(self, *, api_key: str | None) -> list[EnrollmentInfo]:
        self.enrollment_calls += 1
        return [
            EnrollmentInfo(
                service_id="s1", status="active", code="c1", proxy_endpoint="https://gw/x"
            )
        ]


def _settings(ttl: int = 300) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        UNITYSVC_API_KEY="svcpass_cust",
        UNITYSVC_CUSTOMER_CONTEXT_TTL=str(ttl),
    )


@pytest.mark.asyncio
async def test_get_loads_both_lists_into_a_snapshot() -> None:
    api = _FakeApi()
    context = await CustomerContextCache(api, _settings()).get()  # type: ignore[arg-type]

    assert isinstance(context, CustomerContext)
    assert context.secret_names == frozenset({"OPENAI_API_KEY"})
    assert context.enrollments[0].service_id == "s1"
    assert api.secret_calls == 1
    assert api.enrollment_calls == 1


@pytest.mark.asyncio
async def test_cache_serves_a_second_get_within_the_ttl() -> None:
    api = _FakeApi()
    cache = CustomerContextCache(api, _settings(ttl=300))  # type: ignore[arg-type]

    await cache.get()
    await cache.get()

    assert api.secret_calls == 1  # second served from cache


@pytest.mark.asyncio
async def test_cache_refetches_after_expiry() -> None:
    api = _FakeApi()
    cache = CustomerContextCache(api, _settings(ttl=0))  # type: ignore[arg-type]

    await cache.get()
    await cache.get()

    assert api.secret_calls == 2  # ttl=0 → always expired
