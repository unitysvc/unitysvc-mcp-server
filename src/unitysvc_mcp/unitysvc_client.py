from __future__ import annotations

from typing import Any

from unitysvc import AsyncClient as CustomerClient
from unitysvc_sellers import AsyncClient as SellerClient

from .models import ServicesPage, ServiceSummary
from .settings import Settings


class UnitySvcClient:
    """UnitySVC API adapter backed by the official SDKs.

    Takes the API key per call rather than holding one, so the caller decides
    whether a request is anonymous or authenticated. `api_key=None` is a
    first-class case: unitysvc-py >=0.1.16 constructs without a key and sends
    no Authorization header, which the customer API reads as anonymous
    (unitysvc#1610).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_catalog_services(
        self,
        *,
        api_key: str | None = None,
        group: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List catalog services, anonymously or as an authenticated customer.

        Catalog discovery is group-rooted, so with no group named this falls
        back to the platform-wide collection the marketplace tree is rooted on.
        """
        group_name = group or self._settings.default_catalog_group or "all_services"

        async with CustomerClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            page = await client.groups.services(group_name, cursor=cursor, limit=limit)

        return ServicesPage(
            role="customer" if api_key else "anonymous",
            data=[self._summary(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )

    async def list_seller_services(
        self,
        *,
        api_key: str,
        status: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List the services owned by the seller holding this key."""

        async with SellerClient(
            api_key=api_key,
            base_url=str(self._settings.seller_api_url),
        ) as client:
            page = await client.services.list(cursor=cursor, limit=limit, status=status)

        return ServicesPage(
            role="seller",
            data=[self._summary(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )

    def _summary(self, item: Any) -> ServiceSummary:
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
