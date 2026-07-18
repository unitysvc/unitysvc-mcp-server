"""Customer tools — require UNITYSVC_API_KEY.

Operations on your own buyer-side account: enrollments, aliases, secrets, and
invoking services you have enrolled in. None are implemented yet — they are
Phase 3 of unitysvc#1492 — but the module exists so the registration rule is
uniform across all three roles and the next tool has an obvious home rather
than landing in whichever file is nearest.

Note that browsing the market is NOT here: it works without credentials, so
it lives in `market` and is always registered. A customer key widens what
that listing returns; it does not gate it.
"""

from __future__ import annotations

from mcp.server import MCPServer

from ..app_context import AppContext


def register(server: MCPServer[AppContext]) -> list[str]:
    return []
