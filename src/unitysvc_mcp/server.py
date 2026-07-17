from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import httpx
from pydantic import Field
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server.fastmcp import Context, FastMCP

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
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    async with httpx.AsyncClient(follow_redirects=True) as http_client:
        yield AppContext(
            http_client=http_client,
            auth=AuthService(settings, http_client),
            unitysvc=UnitySvcClient(settings, http_client),
        )


mcp = FastMCP(
    "UnitySVC MCP Server",
    lifespan=mcp_lifespan,
    stateless_http=True,
    json_response=True,
)


def _headers(ctx: Context | None) -> Mapping[str, str] | None:
    if ctx is None:
        return None
    headers = getattr(ctx, "headers", None)
    if headers is not None:
        return headers
    request = getattr(ctx.request_context, "request", None)
    return getattr(request, "headers", None)


async def _principal(ctx: Context | None) -> Principal:
    if ctx is None:
        return Principal()
    return await ctx.request_context.lifespan_context.auth.resolve(_headers(ctx))


@mcp.tool()
async def list_services(
    ctx: Context,
    status: Annotated[str | None, Field(description="Seller service status filter. Ignored for catalog listing.")] = None,
    group: Annotated[str | None, Field(description="Catalog group name for anonymous/customer listing.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List services visible to this session: seller-owned services for sellers, catalog services otherwise."""

    principal = await _principal(ctx)
    if principal.is_seller:
        return await ctx.request_context.lifespan_context.unitysvc.list_seller_services(
            principal,
            status=status,
            limit=limit,
            cursor=cursor,
        )
    return await ctx.request_context.lifespan_context.unitysvc.list_catalog_services(
        principal,
        group=group,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool()
async def list_catalog_services(
    ctx: Context,
    group: Annotated[str | None, Field(description="Optional customer-visible group name.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List catalog services visible to anonymous or customer sessions."""

    principal = await _principal(ctx)
    return await ctx.request_context.lifespan_context.unitysvc.list_catalog_services(
        principal,
        group=group,
        limit=limit,
        cursor=cursor,
    )


@mcp.tool()
async def list_seller_services(
    ctx: Context,
    status: Annotated[str | None, Field(description="Optional seller service status filter.")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> ServicesPage:
    """List services owned by the authenticated seller."""

    principal = await _principal(ctx)
    if not principal.is_seller:
        raise PermissionError("list_seller_services requires the seller role")
    return await ctx.request_context.lifespan_context.unitysvc.list_seller_services(
        principal,
        status=status,
        limit=limit,
        cursor=cursor,
    )


async def healthz(request) -> JSONResponse:  # type: ignore[no-untyped-def]
    return JSONResponse({"status": "ok", "service": "unitysvc-mcp-server"})


@asynccontextmanager
async def app_lifespan(app: Starlette) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/healthz", healthz, methods=["GET"]),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=app_lifespan,
)


def main() -> None:
    import uvicorn

    uvicorn.run("unitysvc_mcp.server:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
