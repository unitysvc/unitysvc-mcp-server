"""Marketplace tools — no credentials required, always registered.

This is the public face of UnitySVC: what is on offer, what it costs, and how
to call it. It is exactly the surface the hosted deployment at
mcp.unitysvc.com exposes, because that process runs with an empty environment
and so registers nothing else.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from ..app_context import AppContext, app
from ..models import ServicesPage
from ..settings import settings


async def market_list_services(
    ctx: Context[AppContext],
    group: Annotated[
        str | None, Field(description="Marketplace group name. Defaults to all_services.")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Field(description="Opaque cursor from a previous page.")] = None,
) -> ServicesPage:
    """Browse services offered ON the UnitySVC marketplace — what you can buy and call.

    This is the public view of the market and needs no credentials. It does
    NOT list services you publish as a seller; use seller_list_services for
    those.

    With a customer API key configured, the listing is made as that customer,
    which can widen what is visible.
    """
    return await app(ctx).unitysvc.list_market_services(
        api_key=settings.customer_api_key,
        group=group,
        limit=limit,
        cursor=cursor,
    )


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(market_list_services)
    return ["market_list_services"]
