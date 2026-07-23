"""The docs client: manifest parsing, markdown cleanup, caching, errors.

The site is mocked with `httpx.MockTransport` (patched onto every
`httpx.AsyncClient`, mirroring test_clients), so these assert what the client
sends and how it treats the responses — no network.
"""

from __future__ import annotations

import httpx
import pytest

from unitysvc_mcp.clients.docs import DocsClient, TopicNotFoundError
from unitysvc_mcp.settings import Settings

SITE = "https://site.test"

MANIFEST = [
    {"slug": "alias", "title": "Alias"},
    {"slug": "customer", "title": "Customer Documentation"},
    {"slug": "glossary", "title": "Glossary"},
]

ALIAS_MD = "---\nslug: alias\ntitle: Alias\ntype: topic\n---\n\nBody of alias.\n"


def _settings(ttl: int = 900) -> Settings:
    # _env_file=None so a developer's local .env cannot influence the test.
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        UNITYSVC_SITE_URL=SITE,
        UNITYSVC_DOCS_CACHE_TTL=str(ttl),
    )


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
    """Route every httpx client the docs client builds through a mock transport."""
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(recording)
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
    return seen


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/topics":
        return httpx.Response(200, json=MANIFEST)
    if path == "/topics/alias":
        return httpx.Response(200, text=ALIAS_MD, headers={"content-type": "text/markdown"})
    return httpx.Response(404, text="Not found")


@pytest.mark.asyncio
async def test_list_topics_parses_the_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _handler)

    topics = await DocsClient(_settings()).list_topics()

    assert seen[-1].url.path == "/topics"
    assert [(t.slug, t.title) for t in topics] == [
        ("alias", "Alias"),
        ("customer", "Customer Documentation"),
        ("glossary", "Glossary"),
    ]


@pytest.mark.asyncio
async def test_get_topic_strips_frontmatter_and_prepends_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _handler)

    md = await DocsClient(_settings()).get_topic("alias")

    # Clean, self-titled prose — no YAML frontmatter.
    assert md == "# Alias\n\nBody of alias."
    assert "slug:" not in md
    assert "---" not in md


@pytest.mark.asyncio
async def test_get_topic_without_frontmatter_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(200, text="Just prose, no frontmatter."),
    )

    md = await DocsClient(_settings()).get_topic("plain")

    assert md == "Just prose, no frontmatter."


@pytest.mark.asyncio
async def test_get_topic_unknown_slug_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, _handler)

    with pytest.raises(TopicNotFoundError):
        await DocsClient(_settings()).get_topic("does-not-exist")


@pytest.mark.asyncio
async def test_get_topic_rejects_traversal_slug_without_a_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _handler)

    for bad in ("../../README", "a/b", "", "."):
        with pytest.raises(TopicNotFoundError):
            await DocsClient(_settings()).get_topic(bad)

    # No request was ever issued — rejected before building the URL.
    assert seen == []


@pytest.mark.asyncio
async def test_cache_serves_a_second_call_without_refetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _handler)
    client = DocsClient(_settings(ttl=900))

    await client.list_topics()
    await client.list_topics()

    # One fetch: the second call is served from the TTL cache.
    assert [r.url.path for r in seen] == ["/topics"]


@pytest.mark.asyncio
async def test_cache_refetches_after_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _handler)
    # ttl=0 → every entry is already expired when re-read, so each call refetches.
    client = DocsClient(_settings(ttl=0))

    await client.list_topics()
    await client.list_topics()

    assert [r.url.path for r in seen] == ["/topics", "/topics"]
