from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# How a listing was made. Not an identity claim the server derived — it simply
# records which key (if any) the call used, so the caller can tell an anonymous
# catalog view from an authenticated one.
Role = Literal["anonymous", "customer", "seller"]


class TopicSummary(BaseModel):
    """One row in the docs topic menu (`docs_list_topics`).

    The `/topics` manifest is intentionally just slug + title — a menu the
    agent picks from, then reads with `docs_get_topic(slug)`.
    """

    slug: str
    title: str


class ServiceSummary(BaseModel):
    """Compact service row returned by MCP listing tools.

    Fields are the union of what the SDK models actually return. Not every
    path fills every one: the customer summary carries no status, and the
    seller model no gateway_type.
    """

    id: str | None = None
    name: str
    display_name: str | None = None
    service_type: str | None = None
    gateway_type: str | None = None
    status: str | None = None


class ServicesPage(BaseModel):
    """Paginated service list response."""

    role: Role
    data: list[ServiceSummary]
    count: int | None = None
    next_cursor: str | None = None


class CodeExample(BaseModel):
    """One rendered code example for calling a service.

    ``language`` is the document's mime_type (``python`` / ``bash`` / …);
    ``content`` is the example rendered against a real interface, or None with
    ``render_error`` set when it could not be rendered.
    """

    title: str
    language: str | None = None
    content: str | None = None
    render_error: str | None = None


class ServiceExamples(BaseModel):
    """Runnable code examples for a service, and which interface they target.

    ``interface`` is the user-access-interface key the examples were rendered
    against (e.g. ``canonical``); ``available_interfaces`` lists the
    alternatives a caller can re-request (unitysvc#1617).
    """

    interface: str | None = None
    available_interfaces: list[str] = []
    examples: list[CodeExample] = []
