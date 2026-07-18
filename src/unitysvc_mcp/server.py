"""MCP server exposing the UnitySVC catalog and account operations.

Two deployments, one package. What differs is the transport and whether the
process environment carries credentials:

- **stdio** (default) — a subprocess of the user's MCP client, on their
  machine, holding their own API keys. Gets the full surface.
- **http** — the hosted deployment at mcp.unitysvc.com, run with an *empty*
  environment. Only the context tools register, so it has no credential to
  hold, log, or leak.

Tools are therefore split by what they need, not by where they run:

- **context tools** need no credentials and are always available
- **acting tools** need an API key and register only when one is present

Which key is present is the only role signal. `svcpass_` keys already encode
`role_type`, and the backend authorises every call from the key, so this
server never infers a role of its own.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from mcp.server import MCPServer

# NOT `mcp.server.context.Context` — that is a different class, and the tool
# decorator only recognises (and excludes from the input schema) this one.
from mcp.server.mcpserver import Context
from pydantic import Field

from .models import ServicesPage
from .settings import Settings, settings
from .unitysvc_client import UnitySvcClient

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    unitysvc: UnitySvcClient


@asynccontextmanager
async def lifespan(server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
    yield AppContext(unitysvc=UnitySvcClient(settings))


mcp = MCPServer("UnitySVC MCP Server", lifespan=lifespan)


def _app(ctx: Context[AppContext]) -> AppContext:
    """Reach the lifespan state.

    `Context` exposes it via `request_context.lifespan_context`; the bare
    `.lifespan` shortcut belongs to the unrelated `mcp.server.context.Context`.
    """
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# Context tools — no credentials required, always registered
# ---------------------------------------------------------------------------


async def list_catalog_services(
    ctx: Context[AppContext],
    group: Annotated[
        str | None, Field(description="Catalog group name. Defaults to all_services.")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Field(description="Opaque cursor from a previous page.")] = None,
) -> ServicesPage:
    """List services in the public UnitySVC catalog.

    Works without credentials. When a customer API key is configured the same
    listing is made as that customer, which can widen what is visible.
    """
    return await _app(ctx).unitysvc.list_catalog_services(
        api_key=settings.customer_api_key,
        group=group,
        limit=limit,
        cursor=cursor,
    )


# ---------------------------------------------------------------------------
# Acting tools — require an API key, registered only when one is present
# ---------------------------------------------------------------------------


async def list_seller_services(
    ctx: Context[AppContext],
    status: Annotated[
        str | None, Field(description="Filter by service status, e.g. active.")
    ] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Field(description="Opaque cursor from a previous page.")] = None,
) -> ServicesPage:
    """List the services you own as a seller.

    Requires UNITYSVC_SELLER_API_KEY. This tool is not advertised at all when
    that key is absent, so an agent never sees an option it cannot use.
    """
    if not settings.seller_api_key:  # pragma: no cover - not registered without it
        raise RuntimeError("UNITYSVC_SELLER_API_KEY is not set")
    return await _app(ctx).unitysvc.list_seller_services(
        api_key=settings.seller_api_key,
        status=status,
        limit=limit,
        cursor=cursor,
    )


def register_tools(server: MCPServer[AppContext], config: Settings = settings) -> list[str]:
    """Register the tools this process is actually able to serve.

    Decided once, at startup, from the environment — which is exactly right for
    both deployments. A user's stdio process has their keys and gets
    everything; the hosted process has an empty environment and gets the
    context tools only. Neither needs to know which transport it is on.
    """
    server.add_tool(list_catalog_services)
    names = ["list_catalog_services"]

    if config.can_act_as_seller:
        server.add_tool(list_seller_services)
        names.append("list_seller_services")

    return names


_REGISTERED = register_tools(mcp)


def main() -> None:
    logger.info(
        "unitysvc-mcp-server starting: transport=%s mode=%s tools=%s",
        settings.transport,
        settings.mode,
        ",".join(_REGISTERED),
    )
    if settings.transport == "http":
        mcp.run(transport="streamable-http", host=settings.host, port=settings.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
