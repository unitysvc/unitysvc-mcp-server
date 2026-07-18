"""MCP server exposing the UnitySVC marketplace and account operations.

Two deployments, one package. What differs is the transport and whether the
process environment carries credentials:

- **stdio** (default) — a subprocess of the user's MCP client, on their
  machine, holding their own API keys. Gets the full surface.
- **http** — the hosted deployment at mcp.unitysvc.com, run with an *empty*
  environment. Only `market_*` registers, so it has no credential to hold,
  log, or leak.

Tools are grouped by the credential they need, one module per group, and the
name prefix states that requirement — see `tools/__init__.py`. Which key is
present is the only role signal: `svcpass_` keys already encode `role_type`
and the backend authorises every call, so this server never infers a role of
its own.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server import MCPServer

from .app_context import AppContext
from .settings import Settings, settings
from .tools import customer, market, seller
from .unitysvc_client import UnitySvcClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
    yield AppContext(unitysvc=UnitySvcClient(settings))


mcp = MCPServer("UnitySVC MCP Server", lifespan=lifespan)


def register_tools(server: MCPServer[AppContext], config: Settings = settings) -> list[str]:
    """Register the tools this process is actually able to serve.

    The module a tool lives in is its access rule, so this stays a direct
    transcription of that rule rather than a per-tool check. Decided once, at
    startup, from the environment — which covers both deployments without
    either needing to know its transport: a user's stdio process has their
    keys and gets everything, the hosted process has an empty environment and
    gets `market_*` only.
    """
    names = market.register(server)
    if config.can_act_as_customer:
        names += customer.register(server)
    if config.can_act_as_seller:
        names += seller.register(server)
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
