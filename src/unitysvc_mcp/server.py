from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import httpx
from pydantic import Field

from mcp.server import MCPServer

# NOT `mcp.server.context.Context` — that is a different class, and the tool
# decorator only recognises (and excludes from the input schema) this one.
from mcp.server.mcpserver import Context

from .auth import AuthService
from .models import Principal, ServicesPage
from .settings import settings
from .unitysvc_client import UnitySvcClient


@dataclass
class AppContext:
    http_client: httpx.AsyncClient
    auth: AuthService
    unitysvc: UnitySvcClient


@asynccontextmanager
async def lifespan(server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        yield AppContext(
            http_client=http_client,
            auth=AuthService(settings, http_client),
            unitysvc=UnitySvcClient(settings),
        )


mcp = MCPServer("UnitySVC MCP Server", lifespan=lifespan)


def _app(ctx: Context[AppContext]) -> AppContext:
    """Reach the lifespan state.

    `Context` exposes it via `request_context.lifespan_context`; the bare
    `.lifespan` shortcut belongs to the unrelated `mcp.server.context.Context`.
    """
    return ctx.request_context.lifespan_context


def _headers(ctx: Context[AppContext] | None) -> Mapping[str, str] | None:
    return ctx.headers if ctx is not None else None


async def _principal(ctx: Context[AppContext] | None) -> Principal:
    if ctx is None:
        return Principal()
    return await _app(ctx).auth.resolve(_headers(ctx))


@mcp.tool()
async def list_services(
    ctx: Context[AppContext],
    status: Annotated[str | None, Field(description="Seller service status filter. Ignored for catalog listing.")] = None,
    group: Annotated[str | None, Field(description="Catalog group name for anonymous/customer listing.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List services visible to this session: seller-owned services for sellers, catalog services otherwise."""

    principal = await _principal(ctx)
    if principal.is_seller:
        return await _app(ctx).unitysvc.list_seller_services(
            principal,
            status=status,
            limit=limit,
            cursor=cursor,
        )
    return await _app(ctx).unitysvc.list_catalog_services(
        principal,
        group=group,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool()
async def list_catalog_services(
    ctx: Context[AppContext],
    group: Annotated[str | None, Field(description="Optional customer-visible group name.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List catalog services visible to anonymous or customer sessions."""

    principal = await _principal(ctx)
    return await _app(ctx).unitysvc.list_catalog_services(
        principal,
        group=group,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool()
async def list_seller_services(
    ctx: Context[AppContext],
    status: Annotated[str | None, Field(description="Optional seller service status filter.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List services owned by the authenticated seller."""

    principal = await _principal(ctx)
    if not principal.is_seller:
        raise PermissionError("list_seller_services requires the seller role")
    return await _app(ctx).unitysvc.list_seller_services(
        principal,
        status=status,
        limit=limit,
        cursor=cursor,
    )


def main() -> None:
    mcp.run(transport="streamable-http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
