from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Role = Literal["anonymous", "customer", "seller", "admin", "support"]


class Principal(BaseModel):
    """Authenticated UnitySVC principal derived from the bearer token."""

    subject: str = "anonymous"
    roles: list[Role] = Field(default_factory=lambda: ["anonymous"])
    customer_id: str | None = None
    seller_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    token: str | None = Field(default=None, exclude=True)
    claims: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def is_anonymous(self) -> bool:
        return self.subject == "anonymous" or "anonymous" in self.roles

    @property
    def is_seller(self) -> bool:
        return "seller" in self.roles

    @property
    def is_customer(self) -> bool:
        return "customer" in self.roles


class ServiceSummary(BaseModel):
    """Compact service row returned by MCP listing tools."""

    id: str | None = None
    name: str
    display_name: str | None = None
    description: str | None = None
    service_type: str | None = None
    status: str | None = None
    visibility: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    list_price: dict[str, Any] | None = None


class ServicesPage(BaseModel):
    """Paginated service list response."""

    role: Role
    data: list[ServiceSummary]
    count: int | None = None
    next_cursor: str | None = None
