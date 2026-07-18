"""Shared request-scoped state and its accessor.

Lives outside `server` so the tool modules can import it without importing
the server that imports them.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.mcpserver import Context

from .unitysvc_client import UnitySvcClient


@dataclass
class AppContext:
    unitysvc: UnitySvcClient


def app(ctx: Context[AppContext]) -> AppContext:
    """Reach the lifespan state.

    `Context` exposes it via `request_context.lifespan_context`; the bare
    `.lifespan` shortcut belongs to the unrelated `mcp.server.context.Context`.
    """
    return ctx.request_context.lifespan_context
