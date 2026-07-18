from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# How a listing was made. Not an identity claim the server derived — it simply
# records which key (if any) the call used, so the caller can tell an anonymous
# catalog view from an authenticated one.
Role = Literal["anonymous", "customer", "seller"]


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
