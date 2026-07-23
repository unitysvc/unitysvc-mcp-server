"""Client for the customer API (`unitysvc-py`).

Serves both the anonymous marketplace view and authenticated customer
operations — since unitysvc#1610 the same host answers with or without a key,
so `api_key=None` is a first-class case rather than an error path. That is why
the market tools use this client: they call the customer API *anonymously*.
"""

from __future__ import annotations

from unitysvc import AccessPlan, AsyncClient

from ..context import EnrollmentInfo
from ..models import CodeExample, ServiceExamples, ServicesPage
from ..render import render_access_plan
from ..settings import Settings
from ._summary import clean, service_summary


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

    async def access_plan(
        self,
        service_id: str,
        *,
        api_key: str | None = None,
    ) -> AccessPlan:
        """The generic, context-free ``AccessPlan`` for a service (unitysvc#1638).

        The backend serves structure, not prose; needs no key. Callers render
        it — generically (``service_usage``) or with customer context.
        """
        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            return await client.services.access_plan(service_id)

    async def service_usage(
        self,
        service_id: str,
        *,
        api_key: str | None = None,
    ) -> str:
        """The "how to use this service" guide, as markdown.

        Fetches the ``AccessPlan`` and renders it generically (no customer
        context). Plain text, which is what an agent wants to read.
        """
        return render_access_plan(await self.access_plan(service_id, api_key=api_key))

    async def list_secret_names(self, *, api_key: str | None) -> frozenset[str]:
        """The names of the caller's secrets (never the values — write-only)."""
        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            secrets = await client.secrets.list()
        return frozenset(s.name for s in secrets.data)

    async def list_enrollments(self, *, api_key: str | None) -> list[EnrollmentInfo]:
        """The caller's enrollments, reduced to ``EnrollmentInfo`` for rendering."""
        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            enrollments = await client.enrollments.list()
        return [
            EnrollmentInfo(
                service_id=str(e.service_id),
                status=str(e.status),
                code=e.code if isinstance(e.code, str) else None,
                proxy_endpoint=e.proxy_endpoint if isinstance(e.proxy_endpoint, str) else None,
            )
            for e in enrollments.data
        ]

    async def service_examples(
        self,
        service_id: str,
        *,
        api_key: str | None = None,
        language: str | None = None,
        interface: str | None = None,
    ) -> ServiceExamples:
        """Rendered code examples for calling a service (unitysvc#1617).

        Filters to ``code_example`` documents; ``language`` narrows by mime
        type (``python`` / ``bash`` / …). Examples come back rendered against
        the default interface unless one is named.
        """
        async with AsyncClient(
            api_key=api_key,
            base_url=str(self._settings.customer_api_url),
        ) as client:
            resp = await client.services.documents(
                service_id,
                category="code_example",
                mime_type=language,
                include_content=True,
                interface=interface,
            )

        docs = getattr(resp, "documents", None) or []
        available = getattr(resp, "available_interfaces", None)
        return ServiceExamples(
            interface=clean(getattr(resp, "interface", None)),
            available_interfaces=[str(x) for x in available] if isinstance(available, list) else [],
            examples=[
                CodeExample(
                    title=str(clean(getattr(d, "title", None)) or ""),
                    language=clean(getattr(d, "mime_type", None)),
                    content=clean(getattr(d, "content", None)),
                    render_error=clean(getattr(d, "render_error", None)),
                )
                for d in docs
            ],
        )
