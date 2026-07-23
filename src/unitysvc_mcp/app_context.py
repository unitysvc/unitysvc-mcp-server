"""Shared request-scoped state and its accessor.

Lives outside `server` so the tool modules can import it without importing
the server that imports them.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.mcpserver import Context

from .clients import CustomerApi, DocsClient, SellerApi
from .customer_context import CustomerContextCache
from .seller_context import SellerContextCache


@dataclass
class AppContext:
    """One client per API, so a tool names the API it talks to.

    The API clients are always constructed — they are cheap, and holding one
    does not imply having a key for it, since keys are passed per call (and the
    docs client needs none at all). ``customer_context``/``seller_context`` are
    present only when the matching key is configured (the caller-context
    caches the ``customer_*``/``seller_*`` command tools read).
    """

    customer_api: CustomerApi
    seller_api: SellerApi
    docs: DocsClient
    customer_context: CustomerContextCache | None = None
    seller_context: SellerContextCache | None = None


def app(ctx: Context[AppContext]) -> AppContext:
    """Reach the lifespan state.

    `Context` exposes it via `request_context.lifespan_context`; the bare
    `.lifespan` shortcut belongs to the unrelated `mcp.server.context.Context`.
    """
    return ctx.request_context.lifespan_context
