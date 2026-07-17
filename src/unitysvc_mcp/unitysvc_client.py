from __future__ import annotations

from typing import Any

import httpx

from .models import Principal, ServiceSummary, ServicesPage
from .settings import Settings


class UnitySvcClient:
    """Small UnitySVC API adapter used by MCP tools."""

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
        """List services visible to anonymous/customer users."""

        group_name = group or self._settings.default_catalog_group
        headers = self._auth_headers(principal)

        if group_name:
            payload = await self._get_json(
                str(self._settings.customer_api_url),
                f"/groups/{group_name}/services",
                headers=headers,
                params={"limit": limit, "cursor": cursor},
            )
            return self._services_page("customer", payload)

        # Customer discovery is group-rooted in UnitySVC. For the starter, list
        # visible groups, then pull services from each until the requested limit.
        groups_payload = await self._get_json(
            str(self._settings.customer_api_url),
            "/groups",
            headers=headers,
            params={"limit": min(limit, 100), "cursor": cursor},
        )
        groups = self._extract_rows(groups_payload)
        services: list[ServiceSummary] = []
        for row in groups:
            name = row.get("name")
            if not name:
                continue
            group_payload = await self._get_json(
                str(self._settings.customer_api_url),
                f"/groups/{name}/services",
                headers=headers,
                params={"limit": max(1, limit - len(services))},
            )
            services.extend(self._coerce_services(self._extract_rows(group_payload)))
            if len(services) >= limit:
                break

        return ServicesPage(
            role="customer",
            data=services[:limit],
            count=len(services[:limit]),
            next_cursor=self._next_cursor(groups_payload),
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

        payload = await self._get_json(
            str(self._settings.seller_api_url),
            "/services",
            headers=self._auth_headers(principal),
            params={"status": status, "limit": limit, "cursor": cursor},
        )
        return self._services_page("seller", payload)

    async def _get_json(
        self,
        base_url: str,
        path: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        clean_params = {key: value for key, value in params.items() if value is not None}
        response = await self._http_client.get(
            f"{base_url.rstrip('/')}{path}",
            headers=headers,
            params=clean_params,
            timeout=20,
        )
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {"data": body}

    def _auth_headers(self, principal: Principal) -> dict[str, str]:
        if not principal.token:
            return {}
        return {"Authorization": f"Bearer {principal.token}"}

    def _services_page(self, role: str, payload: dict[str, Any]) -> ServicesPage:
        return ServicesPage(
            role=role,  # type: ignore[arg-type]
            data=self._coerce_services(self._extract_rows(payload)),
            count=self._count(payload),
            next_cursor=self._next_cursor(payload),
        )

    def _extract_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", payload.get("items", payload.get("results", [])))
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    def _coerce_services(self, rows: list[dict[str, Any]]) -> list[ServiceSummary]:
        services: list[ServiceSummary] = []
        for row in rows:
            service_id = row.get("id") or row.get("service_id")
            name = row.get("name") or row.get("service_name")
            if not name:
                continue
            capabilities = row.get("capabilities") or []
            services.append(
                ServiceSummary(
                    id=str(service_id) if service_id else None,
                    name=str(name),
                    display_name=row.get("display_name"),
                    description=row.get("description"),
                    service_type=row.get("service_type"),
                    status=row.get("status"),
                    visibility=row.get("visibility"),
                    capabilities=capabilities if isinstance(capabilities, list) else [],
                    list_price=row.get("list_price") if isinstance(row.get("list_price"), dict) else None,
                )
            )
        return services

    def _count(self, payload: dict[str, Any]) -> int | None:
        value = payload.get("count") or payload.get("total")
        return int(value) if isinstance(value, int | float | str) and str(value).isdigit() else None

    def _next_cursor(self, payload: dict[str, Any]) -> str | None:
        value = payload.get("next_cursor") or payload.get("nextCursor")
        return str(value) if value else None
