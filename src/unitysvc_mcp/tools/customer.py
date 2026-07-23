"""Customer tools — require UNITYSVC_API_KEY.

The customer-aware counterpart to ``market_*``: same public catalog, but the
guide is rendered with the caller's own context joined in — which secrets are
already set (names only) and their live ``/e/<CODE>`` enrollment URLs. Only
registered when a customer key is present; the hosted anonymous deployment
never carries one.
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlsplit

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from .. import commands
from ..app_context import AppContext, app
from ..customer_context import CustomerContext, EnrollmentInfo
from ..render import RenderContext, render_access_plan


def _endpoint_url(enrollment: EnrollmentInfo) -> str | None:
    """Build the caller's ``/e/<CODE>`` URL from an enrollment (like the site)."""
    if not enrollment.code or not enrollment.proxy_endpoint:
        return None
    parts = urlsplit(enrollment.proxy_endpoint)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}/e/{enrollment.code}"


def _service_view(context: CustomerContext, service_id: str) -> RenderContext:
    """Reduce the whole-account context to the view for one service.

    Secret names are account-wide (a secret is set or not, regardless of
    service); enrollment URLs are filtered to this service.
    """
    urls = [
        url
        for enrollment in context.enrollments
        if enrollment.service_id == service_id
        for url in (_endpoint_url(enrollment),)
        if url is not None
    ]
    return RenderContext(set_secret_names=context.secret_names, enrollment_urls=urls)


async def customer_service_access(
    ctx: Context[AppContext],
    service_id: Annotated[
        str, Field(description="Service id, from market_list_services (the `id` field).")
    ],
) -> str:
    """Explain how to use a service, personalized to YOUR account.

    Same guide as market_service_access, but with your own context filled in:
    each required secret marked (set) or (not set) from the secrets you've
    configured, and your live per-enrollment `/e/<CODE>` URL(s) for this
    service. Use this instead of market_service_access when acting for a
    specific customer.
    """
    application = app(ctx)
    plan = await application.customer_api.access_plan(service_id)

    cache = application.customer_context
    if cache is None:  # pragma: no cover - not registered without a customer key
        return render_access_plan(plan)

    context = await cache.get()
    return render_access_plan(plan, context=_service_view(context, service_id))


_SERVICE_ID = Annotated[
    str | None,
    Field(description="Service id (from market_list_services). Omit for account-level usage."),
]


async def _plan_and_view(ctx: Context[AppContext], service_id: str) -> tuple[object, RenderContext]:
    application = app(ctx)
    plan = await application.customer_api.access_plan(service_id)
    cache = application.customer_context
    context = await cache.get() if cache is not None else CustomerContext(frozenset(), ())
    return plan, _service_view(context, service_id)


async def customer_cli(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Runnable `usvc` CLI commands, generated from the installed unitysvc-py.

    With a service_id: the exact commands to set up and call THAT service —
    which secrets to set (only the unset ones), enroll if required, and
    dispatch — filled from your context. Without it: the `usvc` command tree.
    """
    if service_id is None:
        return commands.cli_overview()
    plan, view = await _plan_and_view(ctx, service_id)
    return commands.render_cli(service_id, plan, view)  # type: ignore[arg-type]


async def customer_sdk(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Python (`unitysvc.Client`) usage, generated from the installed unitysvc-py.

    With a service_id: a filled snippet to set up and call THAT service.
    Without it: the Client resources and their method signatures.
    """
    if service_id is None:
        return commands.sdk_overview()
    plan, view = await _plan_and_view(ctx, service_id)
    return commands.render_sdk(service_id, plan, view)  # type: ignore[arg-type]


async def customer_endpoints(ctx: Context[AppContext], service_id: _SERVICE_ID = None) -> str:
    """Raw HTTP (curl) to call a service, from its access plan + your context.

    With a service_id: the curl to call it (your live endpoint URL, auth
    header). Without it: a pointer to the per-service form.
    """
    if service_id is None:
        return commands.endpoints_overview()
    plan, view = await _plan_and_view(ctx, service_id)
    return commands.render_endpoints(service_id, plan, view)  # type: ignore[arg-type]


def register(server: MCPServer[AppContext]) -> list[str]:
    server.add_tool(customer_service_access)
    server.add_tool(customer_endpoints)
    server.add_tool(customer_sdk)
    server.add_tool(customer_cli)
    return [
        "customer_service_access",
        "customer_endpoints",
        "customer_sdk",
        "customer_cli",
    ]
