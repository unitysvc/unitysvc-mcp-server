"""Client for the docs "topics" the frontend site serves.

Unlike the customer/seller clients, this wraps no SDK — the topics live on the
frontend site (`/topics`, `/topics/<slug>`), not the API backends, and are
public, so it is a plain `httpx` fetch with no credential. A small in-memory
TTL cache keeps the long-lived hosted process from refetching static docs on
every call; edits appear within the TTL window with no restart.
"""

from __future__ import annotations

import json
import re
import time

import httpx

from ..models import TopicSummary
from ..settings import Settings

# A topic slug is a simple token (the site's slugify output). Reject anything
# with a path separator or "." *before* building the URL — the same traversal
# guard the frontend applies (unitysvc#1662 P1), here avoiding a pointless
# round-trip and giving a clear local error.
_SAFE_SLUG = re.compile(r"^[A-Za-z0-9_-]+$")

# A leading YAML frontmatter block, and the topic title within it. Parsed with
# a light regex rather than a YAML dependency — the block is simple key: value
# lines, and only the title is needed.
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


class TopicNotFoundError(Exception):
    """Raised for an unknown or malformed topic slug (surfaced as a tool error)."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"topic {slug!r} not found")
        self.slug = slug


def _clean_markdown(raw: str) -> str:
    """Strip the YAML frontmatter and prepend the title as an H1.

    The raw file begins with a `---` frontmatter block; an agent wants clean,
    self-titled prose, not the YAML. Files without frontmatter pass through.
    """
    match = _FRONTMATTER.match(raw)
    if not match:
        return raw.strip()
    front, body = match.group(1), match.group(2).strip()
    title_match = _TITLE.search(front)
    if not title_match:
        return body
    title = title_match.group(1).strip().strip("\"'")
    return f"# {title}\n\n{body}" if body else f"# {title}"


class DocsClient:
    """Reads the public docs topics, with an in-memory TTL cache.

    A key is never involved — the topics are public. Holds no persistent HTTP
    client; each fetch opens one (cheap next to the cache), matching how the
    SDK-backed clients construct per call.
    """

    def __init__(self, settings: Settings) -> None:
        self._base = str(settings.site_url).rstrip("/")
        self._ttl = settings.docs_cache_ttl_seconds
        # path -> (expires_at_monotonic, body_text)
        self._cache: dict[str, tuple[float, str]] = {}

    async def _get(self, path: str) -> str | None:
        """Fetch `path` (cached); return the body, or None on 404."""
        now = time.monotonic()
        hit = self._cache.get(path)
        if hit is not None and hit[0] > now:
            return hit[1]
        async with httpx.AsyncClient(base_url=self._base, timeout=10.0) as client:
            resp = await client.get(path)
        if resp.status_code == 404:
            return None  # not cached: a topic may be added later
        resp.raise_for_status()
        text = resp.text
        self._cache[path] = (now + self._ttl, text)
        return text

    async def list_topics(self) -> list[TopicSummary]:
        """The topic menu — every topic's slug and title, from `/topics`."""
        text = await self._get("/topics")
        if text is None:
            return []
        return [TopicSummary(slug=row["slug"], title=row["title"]) for row in json.loads(text)]

    async def get_topic(self, slug: str) -> str:
        """A topic's markdown (frontmatter stripped, title as H1).

        Raises `TopicNotFoundError` for a malformed slug (before any request)
        or an unknown one (the site's 404).
        """
        if not _SAFE_SLUG.match(slug or ""):
            raise TopicNotFoundError(slug)
        text = await self._get(f"/topics/{slug}")
        if text is None:
            raise TopicNotFoundError(slug)
        return _clean_markdown(text)
