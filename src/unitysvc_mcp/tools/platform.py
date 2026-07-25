"""Platform-documentation tools — no credentials required, always registered.

The UnitySVC docs are single-source markdown "topics" (unitysvc/unitysvc#1662),
public and api-key-independent — the same content whether the reader is a
customer, a seller, or anonymous. So this is one generic, anonymous surface
with no role split: the *tools* elsewhere are gated by which key is present,
but the *docs* are not, so there is nothing to scope. It ships in the hosted
empty-environment deployment alongside ``market_*``.

These answer questions about the PLATFORM itself (what a channel is, BYOK vs
enrollment, how billing works) — distinct from the catalog (``market_*``).
"""

from __future__ import annotations

from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from ..app_context import AppContext, app
from ..models import TopicRef


async def platform_list_topics(ctx: Context[AppContext]) -> list[TopicRef]:
    """List the UnitySVC platform documentation topics (slug + title).

    These explain the PLATFORM — concepts like channel, enrollment, secret,
    wallet, group, gateway, pricing, and billing — not individual services (use
    market_list_services for the catalog). This is the authoritative set of
    slugs; pick one and read it with platform_read_topic.
    """
    return await app(ctx).topics_api.list_topics()


async def platform_read_topic(
    ctx: Context[AppContext],
    topic: Annotated[
        str,
        Field(description="Topic slug from platform_list_topics, e.g. 'channel'."),
    ],
) -> str:
    """Read one UnitySVC platform documentation topic, as markdown.

    The authoritative answer for platform-concept questions ("what is a
    channel?", "BYOK vs enrollment?", "how does billing work?") — read it
    instead of answering from prior knowledge. Topics cross-reference each other
    with links written as `[channel](?topic=channel)`; to follow one, call this
    tool again with that slug (here, `channel`). When a topic doesn't fully
    answer the question, read the topics it references. An unknown slug returns
    the list of valid ones.
    """
    md = await app(ctx).topics_api.read_topic(topic)
    if md is None:
        topics = await app(ctx).topics_api.list_topics()
        slugs = ", ".join(t.slug for t in topics)
        return f"No topic named '{topic}'. Available topics: {slugs}"
    return md


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(platform_list_topics)
    server.add_tool(platform_read_topic)
    return ["platform_list_topics", "platform_read_topic"]
