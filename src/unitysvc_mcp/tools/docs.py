"""Documentation tools — no credentials required, always registered.

The platform documentation "topics" the `/docs` site renders: primitives,
aliases, the billing model, a glossary of terms. Public, so — like `market_*`
— these register in every deployment, including the hosted anonymous one at
mcp.unitysvc.com, whose whole purpose is answering "what is this and how do I
use it" without a key.

Distinct from `market_*`: those explain one *service* (dynamic, per-service);
these explain platform *concepts* (static prose). `docs_` is a second
credential-free prefix alongside `market_` — see `tools/__init__.py`.
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from ..app_context import AppContext, app
from ..models import TopicSummary


async def docs_list_topics(ctx: Context[AppContext]) -> list[TopicSummary]:
    """List the platform documentation topics you can read.

    The menu — each topic's slug and title. Pick one and read it with
    docs_get_topic. Topics cover platform concepts (request primitives,
    aliases, the billing model) and include a `glossary` defining platform
    terms. This is NOT the service catalog; use market_list_services for
    services on offer.
    """
    return await app(ctx).docs.list_topics()


async def docs_get_topic(
    ctx: Context[AppContext],
    slug: Annotated[
        str, Field(description="Topic slug, from docs_list_topics (the `slug` field).")
    ],
) -> str:
    """Read a platform documentation topic as markdown.

    Returns the topic's prose (e.g. `alias`, `customer`, or `glossary` for the
    definitions of platform terms). Use docs_list_topics first to see which
    slugs exist.
    """
    return await app(ctx).docs.get_topic(slug)


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(docs_list_topics)
    server.add_tool(docs_get_topic)
    return ["docs_list_topics", "docs_get_topic"]
