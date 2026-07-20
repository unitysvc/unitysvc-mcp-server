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
from ..models import ServiceExamples, ServicesPage


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
    """
    # Deliberately anonymous even when a customer key is configured. The
    # backend hardcodes status='active' AND visibility='public' for this
    # listing and ignores caller identity, so a key cannot widen the result —
    # it can only turn a working call into a 401 when the key is expired or
    # wrong. Revisit if the endpoint ever varies by customer.
    return await app(ctx).customer_api.list_services(
        group=group,
        limit=limit,
        cursor=cursor,
    )


async def market_service_access(
    ctx: Context[AppContext],
    service_id: Annotated[
        str, Field(description="Service id, from market_list_services (the `id` field).")
    ],
) -> str:
    """Explain how to sign up for and use a marketplace service.

    Returns a derived, per-channel guide (markdown): which channels the service
    offers, whether each is free or paid, what secrets a customer must set (and
    how to obtain them), whether enrollment is required and with what
    parameters, and how to call it. Synthesized from service metadata, so it
    needs no credentials. Use market_service_example for the actual code.
    """
    return await app(ctx).customer_api.service_usage(service_id)


async def market_service_example(
    ctx: Context[AppContext],
    service_id: Annotated[
        str, Field(description="Service id, from market_list_services (the `id` field).")
    ],
    language: Annotated[
        str | None,
        Field(description="Filter examples by language/mime type, e.g. python, bash."),
    ] = None,
) -> ServiceExamples:
    """Get runnable code examples for calling a marketplace service.

    Returns seller-authored code examples, rendered against a real access
    interface (real gateway base URL, not a template placeholder). Filter by
    `language` for one runtime. Use market_service_access first for the
    sign-up/setup steps; this tool is the "show me the code" follow-up.
    """
    return await app(ctx).customer_api.service_examples(service_id, language=language)


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(market_list_services)
    server.add_tool(market_service_access)
    server.add_tool(market_service_example)
    return ["market_list_services", "market_service_access", "market_service_example"]
