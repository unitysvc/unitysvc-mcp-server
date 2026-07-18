from __future__ import annotations

from typing import Any

import httpx
from unitysvc import AsyncClient as CustomerClient
from unitysvc_sellers import AsyncClient as SellerClient

from .models import Principal, ServicesPage, ServiceSummary
from .settings import Settings


class UnitySvcClient:
    """UnitySVC API adapter backed by the official SDKs.

    Authenticated calls go through `unitysvc` / `unitysvc_sellers`, constructed
    per request with the caller's own token — the server holds no credential of
    its own, so a caller can never see more than their token allows.

    Anonymous catalog reads are the one exception: the SDKs require an api_key,
    so those hit the public host directly with no auth.
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http_client = http_client

    async def list_catalog_services(
        self,
        principal: Principal,
        *,
        group: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List catalog services for an anonymous or customer caller."""

        if not principal.token:
            return await self._list_public_services(limit=limit, cursor=cursor)

        # Customer-visible services are addressed per group, so with no group
        # named, fall back to the platform-wide collection that the marketplace
        # tree itself is rooted on.
        group_name = group or self._settings.default_catalog_group or "all_services"

        async with CustomerClient(
            api_key=principal.token,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            page = await client.groups.services(group_name, cursor=cursor, limit=limit)

        return ServicesPage(
            role="customer",
            data=[self._summary_from_sdk(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )

    async def list_seller_services(
        self,
        principal: Principal,
        *,
        status: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List the authenticated seller's own services."""

        if not principal.token:
            raise PermissionError("Seller tools require bearer authentication")

        async with SellerClient(
            api_key=principal.token,
            base_url=str(self._settings.seller_api_url),
        ) as client:
            page = await client.services.list(cursor=cursor, limit=limit, status=status)

        return ServicesPage(
            role="seller",
            data=[self._summary_from_sdk(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )

    async def _list_public_services(self, *, limit: int, cursor: str | None) -> ServicesPage:
        """Read the anonymous public catalog.

        This route lives on the `frontend` BFF deployment (reached via the site
        host's ingress), which is the only one mounting it unauthenticated. It
        paginates by offset rather than keyset, so the opaque `next_cursor`
        carried here is just the next `skip`.
        """
        skip = self._decode_offset(cursor)
        response = await self._http_client.get(
            f"{str(self._settings.public_api_url).rstrip('/')}/services/",
            params={"skip": skip, "limit": limit},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        raw = payload.get("data") if isinstance(payload, dict) else None
        rows = [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []
        total = payload.get("count") if isinstance(payload, dict) else None

        next_offset = skip + len(rows)
        has_more = isinstance(total, int) and next_offset < total
        return ServicesPage(
            role="anonymous",
            data=[self._summary_from_mapping(row) for row in rows],
            count=total if isinstance(total, int) else len(rows),
            next_cursor=str(next_offset) if has_more else None,
        )

    def _decode_offset(self, cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            return max(0, int(cursor))
        except ValueError as exc:
            raise ValueError("Invalid cursor for the public catalog listing") from exc

    def _summary_from_sdk(self, item: Any) -> ServiceSummary:
        """Build a summary from an SDK model.

        Both SDKs wrap their generated models in attribute-proxying objects, and
        unset optional fields come back as the generated `UNSET` sentinel rather
        than None — hence the coercion in `_clean`.
        """
        return ServiceSummary(
            id=self._clean(getattr(item, "id", None)),
            name=str(self._clean(getattr(item, "name", None)) or ""),
            display_name=self._clean(getattr(item, "display_name", None)),
            service_type=self._clean(getattr(item, "service_type", None)),
            gateway_type=self._clean(getattr(item, "gateway_type", None)),
            status=self._clean(getattr(item, "status", None)),
            currency=self._clean(getattr(item, "currency", None)),
        )

    def _summary_from_mapping(self, row: dict[str, Any]) -> ServiceSummary:
        tags = row.get("tags")
        return ServiceSummary(
            id=self._clean(row.get("id")),
            name=str(row.get("name") or ""),
            display_name=self._clean(row.get("display_name")),
            service_type=self._clean(row.get("service_type")),
            gateway_type=self._clean(row.get("gateway_type")),
            status=self._clean(row.get("status")),
            currency=self._clean(row.get("currency")),
            tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
        )

    def _clean(self, value: Any) -> str | None:
        """Normalise None, the SDKs' `UNSET` sentinel, and UUIDs to str | None."""
        if value is None:
            return None
        if type(value).__name__ == "Unset":
            return None
        return str(value)
