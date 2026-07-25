"""Platform-docs topics: the client contract, session caching, and the tools.

The docs live on the webapp's ``/topics`` endpoint (unitysvc/unitysvc#1662);
this asserts the client fetches them anonymously, caches every fetch for the
process, and that the tools surface them (including a helpful miss).
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from unitysvc_mcp.app_context import AppContext
from unitysvc_mcp.clients import TopicsApi
from unitysvc_mcp.instructions import PRIMER
from unitysvc_mcp.settings import Settings
from unitysvc_mcp.tools import platform

DOCS_BASE = "https://docs.test"

INDEX = [
    {"slug": "channel", "title": "Channel"},
    {"slug": "enrollment", "title": "Enrollment"},
]
CHANNEL_MD = (
    "---\nslug: channel\ntitle: Channel\n---\n\n"
    "A channel is one way a [service](?topic=service) is reached."
)


def _settings() -> Settings:
    return Settings(_env_file=None, UNITYSVC_DOCS_URL=DOCS_BASE)  # type: ignore[arg-type]


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> list[httpx.Request]:
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
        return httpx.Response(200, json=INDEX)
    if path == "/topics/channel":
        return httpx.Response(200, text=CHANNEL_MD, headers={"content-type": "text/markdown"})
    return httpx.Response(404, text="Not found")


def _ctx(topics_api: TopicsApi) -> SimpleNamespace:
    app_ctx = AppContext(customer_api=None, seller_api=None, topics_api=topics_api)  # type: ignore[arg-type]
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=app_ctx))


@pytest.mark.asyncio
async def test_list_topics_fetches_index_anonymously(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _handler)

    topics = await TopicsApi(_settings()).list_topics()

    request = seen[-1]
    assert str(request.url) == f"{DOCS_BASE}/topics"
    assert "authorization" not in {k.lower() for k in request.headers}
    assert [(t.slug, t.title) for t in topics] == [
        ("channel", "Channel"),
        ("enrollment", "Enrollment"),
    ]


@pytest.mark.asyncio
async def test_read_topic_returns_markdown_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _handler)

    md = await TopicsApi(_settings()).read_topic("channel")

    assert seen[-1].url.path == "/topics/channel"
    assert md == CHANNEL_MD  # unchanged — frontmatter + cross-reference intact


@pytest.mark.asyncio
async def test_read_topic_unknown_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _handler)

    assert await TopicsApi(_settings()).read_topic("does-not-exist") is None


@pytest.mark.asyncio
async def test_each_fetch_is_cached_for_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _handler)
    api = TopicsApi(_settings())

    await api.list_topics()
    await api.list_topics()
    await api.read_topic("channel")
    await api.read_topic("channel")

    # One request for the index, one for the topic — repeats hit the cache.
    paths = [r.url.path for r in seen]
    assert paths == ["/topics", "/topics/channel"]


@pytest.mark.asyncio
async def test_tool_lists_topics(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, _handler)

    topics = await platform.platform_list_topics(_ctx(TopicsApi(_settings())))

    assert {t.slug for t in topics} == {"channel", "enrollment"}


@pytest.mark.asyncio
async def test_tool_reads_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, _handler)

    md = await platform.platform_read_topic(_ctx(TopicsApi(_settings())), topic="channel")

    assert md == CHANNEL_MD


@pytest.mark.asyncio
async def test_tool_unknown_topic_answers_with_valid_slugs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _handler)

    msg = await platform.platform_read_topic(_ctx(TopicsApi(_settings())), topic="nope")

    assert "No topic named 'nope'" in msg
    assert "channel" in msg and "enrollment" in msg


def test_primer_maps_tools_and_forbids_guessing() -> None:
    """The injected primer names the docs tools and tells the model not to
    answer platform questions from training data."""
    assert "platform_read_topic" in PRIMER
    assert "platform_list_topics" in PRIMER
    assert "training data" in PRIMER
    assert "?topic=" in PRIMER  # explains the cross-reference format
