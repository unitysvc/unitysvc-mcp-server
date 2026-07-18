from __future__ import annotations

from typing import Any

from unitysvc import AsyncClient as CustomerClient
from unitysvc_sellers import AsyncClient as SellerClient

from .models import Principal, ServicesPage, ServiceSummary
from .settings import Settings


class UnitySvcClient:
    """UnitySVC API adapter backed by the official SDKs.

    Every call is made with the caller's own token, constructed per request —
    the server holds no credential of its own, so a caller can never see more
    than their token allows.

    Anonymous callers get the same code path with no token at all: since
    unitysvc#1610 the customer API serves catalog reads without credentials,
    and unitysvc-py >=0.1.16 can be constructed without an api_key. That
    replaced a hand-rolled httpx path against a separate public host.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_catalog_services(
        self,
        principal: Principal,
        *,
        group: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List catalog services for an anonymous or customer caller.

        Catalog discovery is group-rooted, so with no group named this falls
        back to the platform-wide collection the marketplace tree is rooted on.
        """
        group_name = group or self._settings.default_catalog_group or "all_services"

        # api_key=None means anonymous; the SDK then sends no Authorization
        # header, which is what the customer API reads as an anonymous caller.
        async with CustomerClient(
            api_key=principal.token,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            page = await client.groups.services(group_name, cursor=cursor, limit=limit)

        return ServicesPage(
            role="customer" if principal.token else "anonymous",
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
        )

    def _clean(self, value: Any) -> str | None:
        """Normalise None, the SDKs' `UNSET` sentinel, and UUIDs to str | None."""
        if value is None:
            return None
        if type(value).__name__ == "Unset":
            return None
        return str(value)
