"""Seller tools — require UNITYSVC_SELLER_API_KEY.

Registered only when that key is present, so an agent never sees an option it
cannot use. The key itself carries `role_type=seller`; the backend authorises
every call, so nothing here re-derives a role.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from ..app_context import AppContext, app
from ..models import ServicesPage
from ..settings import settings


async def seller_list_services(
    ctx: Context[AppContext],
    status: Annotated[
        str | None, Field(description="Filter by service status, e.g. active.")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Field(description="Opaque cursor from a previous page.")] = None,
) -> ServicesPage:
    """List the services YOU publish as a seller — your own listings.

    This is your own inventory, including services not yet active or public.
    It does NOT browse the marketplace; use market_list_services for what is
    on offer from others.
    """
    if not settings.seller_api_key:  # pragma: no cover - not registered without it
        raise RuntimeError("UNITYSVC_SELLER_API_KEY is not set")
    return await app(ctx).seller_api.list_services(
        api_key=settings.seller_api_key,
        status=status,
        limit=limit,
        cursor=cursor,
    )


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(seller_list_services)
    return ["seller_list_services"]
