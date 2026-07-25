"""Client for the platform-docs "topics" contract on the webapp.

UnitySVC docs are single-source markdown "topics" served statically by the
frontend (unitysvc/unitysvc#1662): ``GET /topics`` lists ``{slug, title}`` and
``GET /topics/<slug>`` returns the raw markdown. That endpoint is public and
api-key-independent — the same content for a customer, a seller, or an
anonymous reader — so this client sends no credential.

It also **caches every fetch for the process lifetime**. The topics are
``force-static``, so a slug never changes under a running server; a fresh
server picks up doc edits. This is the "retrieve from the docs side, cache for
the session" contract the tools promise, kept in one place.

Named for the API it talks to (the webapp's topics endpoint), like the other
clients — not the SDK, because there is no SDK here; topics live on the
frontend host, not ``*_api_url``.
"""

from __future__ import annotations

import httpx

from ..models import TopicRef
from ..settings import Settings

_TIMEOUT = httpx.Timeout(15.0)


class TopicsApi:
    """Read the platform-docs topics, caching each fetch for the session."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index: list[TopicRef] | None = None
        self._topics: dict[str, str] = {}

    @property
    def _base(self) -> str:
        return str(self._settings.docs_url).rstrip("/")

    async def list_topics(self) -> list[TopicRef]:
        """The topic index — ``[{slug, title}, …]`` — fetched once and cached.

        This is the authoritative, closed set of slugs; ``platform_read_topic``
        takes one of them.
        """
        if self._index is None:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self._base}/topics")
                resp.raise_for_status()
                self._index = [TopicRef(**row) for row in resp.json()]
        return self._index

    async def read_topic(self, slug: str) -> str | None:
        """One topic's raw markdown (verbatim, frontmatter included), cached.

        Returns ``None`` for an unknown slug (the endpoint 404s) so the tool can
        answer with the valid slugs rather than an error. The markdown is
        returned unchanged — it is the authoritative content contract, and its
        ``[title](?topic=<slug>)`` cross-references let a reader follow up via
        this same method.
        """
        if slug not in self._topics:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{self._base}/topics/{slug}")
                if resp.status_code == httpx.codes.NOT_FOUND:
                    return None
                resp.raise_for_status()
                self._topics[slug] = resp.text
        return self._topics[slug]
