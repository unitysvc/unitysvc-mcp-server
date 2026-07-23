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

from .. import seller_commands
from ..app_context import AppContext, app
from ..models import ServicesPage
from ..seller_context import SellerServiceInfo
from ..settings import settings

_SERVICE_ID = Annotated[
    str | None,
    Field(description="Service id (from seller_list_services). Omit for the command overview."),
]


async def _find(ctx: Context[AppContext], service_id: str) -> SellerServiceInfo | None:
    cache = app(ctx).seller_context
    if cache is None:  # pragma: no cover - not registered without a seller key
        return None
    context = await cache.get()
    for info in context.services:
        if info.id == service_id:
            return info
    return None


async def seller_endpoints(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Raw HTTP notes for managing a service, from the seller side.

    Without a service_id: a pointer to seller_cli/seller_sdk (the seller API
    has no documented direct raw-HTTP surface). With one: the same pointer,
    plus your service's current status.
    """
    if service_id is None:
        return seller_commands.endpoints_overview()
    info = await _find(ctx, service_id)
    return seller_commands.render_endpoints(service_id, info)


async def seller_sdk(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Python (`unitysvc_sellers.Client`) usage, generated from the installed unitysvc-sellers.

    With a service_id: a filled snippet to inspect and manage THAT service —
    submit for review if it isn't yet, otherwise update/run-tests — using your
    own inventory to pick the next step. Without it: the Client resources and
    their method signatures.
    """
    if service_id is None:
        return seller_commands.sdk_overview()
    info = await _find(ctx, service_id)
    return seller_commands.render_sdk(service_id, info)


async def seller_cli(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Runnable `usvc_seller` CLI commands, generated from the installed unitysvc-sellers.

    With a service_id: the exact commands to inspect and manage THAT service —
    submit for review if it isn't yet, otherwise update/run-tests. Without it:
    the `usvc_seller` command tree.
    """
    if service_id is None:
        return seller_commands.cli_overview()
    info = await _find(ctx, service_id)
    return seller_commands.render_cli(service_id, info)


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
    server.add_tool(seller_endpoints)
    server.add_tool(seller_sdk)
    server.add_tool(seller_cli)
    return ["seller_list_services", "seller_endpoints", "seller_sdk", "seller_cli"]
