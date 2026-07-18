"""Client for the customer API (`unitysvc-py`).

Serves both the anonymous marketplace view and authenticated customer
operations — since unitysvc#1610 the same host answers with or without a key,
so `api_key=None` is a first-class case rather than an error path. That is why
the market tools use this client: they call the customer API *anonymously*.
"""

from __future__ import annotations

from unitysvc import AsyncClient

from ..models import ServicesPage
from ..settings import Settings
from ._summary import service_summary


class CustomerApi:
    """Operations on the customer API.

    Takes the key per call rather than holding one, so the caller decides
    whether a request is anonymous or authenticated.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_services(
        self,
        *,
        api_key: str | None = None,
        group: str | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> ServicesPage:
        """List marketplace services, anonymously or as a named customer.

        The backend calls this the customer *catalog*; we name it for the
        marketplace instead. Discovery is group-rooted, so with no group named
        this falls back to the platform-wide collection the marketplace tree is
        rooted on.
        """
        group_name = group or self._settings.default_catalog_group or "all_services"

        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            page = await client.groups.services(group_name, cursor=cursor, limit=limit)

        return ServicesPage(
            role="customer" if api_key else "anonymous",
            data=[service_summary(item) for item in page.data],
            count=len(page.data),
            next_cursor=page.next_cursor,
        )
