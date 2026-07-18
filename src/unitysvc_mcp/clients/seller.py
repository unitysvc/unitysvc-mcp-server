"""Client for the seller API (`unitysvc-sellers`).

A different package, host, and key from the customer API — kept separate so
neither the role nor the host has to be repeated in every method name.
"""

from __future__ import annotations

from unitysvc_sellers import AsyncClient

from ..models import ServicesPage
from ..settings import Settings
from ._summary import service_summary


class SellerApi:
    """Operations on the seller API. Every call requires a seller key."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_services(
        self,
        *,
        api_key: str,
        status: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List the services owned by the seller holding this key."""

        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.seller_api_url),
        ) as client:
            page = await client.services.list(cursor=cursor, limit=limit, status=status)

        return ServicesPage(
            role="seller",
            data=[service_summary(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )
