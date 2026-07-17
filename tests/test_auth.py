from __future__ import annotations

import httpx
import pytest

from unitysvc_mcp.auth import AuthService, extract_bearer_token
from unitysvc_mcp.settings import Settings


def test_extract_bearer_token() -> None:
    assert extract_bearer_token({"Authorization": "Bearer abc"}) == "abc"
    assert extract_bearer_token({"authorization": "Bearer abc"}) == "abc"
    assert extract_bearer_token({"Authorization": "Basic abc"}) is None
    assert extract_bearer_token({}) is None


@pytest.mark.asyncio
async def test_dev_token_resolves_seller() -> None:
    settings = Settings(
        UNITYSVC_MCP_DEV_TOKENS='{"seller-token":{"subject":"u_1","roles":["seller"],"seller_id":"s_1"}}'
    )
    async with httpx.AsyncClient() as client:
        auth = AuthService(settings, client)
        principal = await auth.resolve({"Authorization": "Bearer seller-token"})

    assert principal.subject == "u_1"
    assert principal.is_seller
    assert principal.seller_id == "s_1"
