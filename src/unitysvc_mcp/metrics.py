"""Prometheus instrumentation for the hosted (HTTP) deployment.

The hosted server at ``mcp.unitysvc.com`` is a long-lived process our
kube-prometheus-stack is built to watch, yet it emits nothing today. This
module adds the platform's house-style telemetry: Prometheus **pull** (a
``/metrics`` endpoint a ServiceMonitor scrapes), matching the backend and the
gateways, rather than OpenTelemetry push.

Two pieces, kept apart on purpose:

- **`MetricsMiddleware`** — a `ServerMiddleware` (the same tier the SDK's own
  `OpenTelemetryMiddleware` runs at) that times every inbound MCP message and
  records per-method and per-tool counters/histograms. This is the only layer
  that sees the *tool name*: over HTTP every tool call is a JSON-RPC POST to the
  one ``/mcp`` path, so an ASGI/HTTP middleware could never split by tool.
- **`start_metrics_server`** — serves the Prometheus text format on a
  **dedicated port** (default 9090), separate from the MCP port (8000). The
  ``mcp.unitysvc.com`` ingress forwards ``/`` to 8000, so putting ``/metrics``
  there would publish it; a separate ClusterIP-only port the ingress never
  routes to keeps it internal, mirroring the s3/smtp gateways' dedicated
  metrics port.

See unitysvc/unitysvc-mcp-server#16 for the design.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Latency buckets tuned for MCP calls: most are a single upstream API round
# trip (tens of ms) but a cold docs fetch or a slow backend can reach seconds.
_LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# The MCP methods worth their own label. Anything else — a malformed or
# unknown method, which reaches this middleware before method lookup and would
# otherwise let a misbehaving client mint unbounded label values — collapses to
# "other". Notifications keep their `notifications/*` names; the label makes
# request-vs-notification obvious without a second metric.
_KNOWN_METHODS = frozenset(
    {
        "initialize",
        "ping",
        "completion/complete",
        "tools/list",
        "tools/call",
        "resources/list",
        "resources/templates/list",
        "resources/read",
        "resources/subscribe",
        "resources/unsubscribe",
        "prompts/list",
        "prompts/get",
        "logging/setLevel",
        "notifications/initialized",
        "notifications/cancelled",
        "notifications/progress",
        "notifications/roots/list_changed",
    }
)

REQUESTS = Counter(
    "mcp_requests_total",
    "Inbound MCP messages handled, by JSON-RPC method and outcome. Includes "
    "notifications (under their notifications/* method label).",
    ["method", "status"],
)
REQUEST_DURATION = Histogram(
    "mcp_request_duration_seconds",
    "Time to handle an inbound MCP message, by JSON-RPC method.",
    ["method"],
    buckets=_LATENCY_BUCKETS,
)
TOOL_CALLS = Counter(
    "mcp_tool_calls_total",
    "tools/call invocations, by tool name and outcome. An unregistered or "
    "malformed tool name collapses to 'unknown' to bound cardinality.",
    ["tool", "outcome"],
)
TOOL_DURATION = Histogram(
    "mcp_tool_call_duration_seconds",
    "Time to execute a tool, by tool name (dominated by the upstream API call).",
    ["tool"],
    buckets=_LATENCY_BUCKETS,
)
SESSIONS = Counter(
    "mcp_sessions_total",
    "MCP sessions opened — one per initialize. rate() gives the connect rate; "
    "this is the 'number of connectors' signal.",
)
REGISTERED_TOOLS = Gauge(
    "mcp_registered_tools",
    "Tools this process advertises. Varies by which credentials are present, "
    "so it is labelled by the process mode.",
    ["mode"],
)


def _method_label(method: str) -> str:
    return method if method in _KNOWN_METHODS else "other"


def _tool_label(params: Mapping[str, Any] | None, known: frozenset[str]) -> str:
    """The tool name for a tools/call, bounded to the registered set.

    The name is caller-supplied and unvalidated at this tier, so an unknown or
    non-string value becomes 'unknown' rather than a fresh label value.
    """
    name = params.get("name") if params else None
    if isinstance(name, str) and name in known:
        return name
    return "unknown"


class MetricsMiddleware:
    """Times each inbound message and records Prometheus metrics.

    Structurally a `mcp.server.context.ServerMiddleware` — `(ctx, call_next)
    -> result`, installed on the lowlevel server's middleware list. A failed
    request arrives here as a raised exception; we record it as ``error`` and
    re-raise so nothing observes differently because metrics are on.
    """

    def __init__(self, registered_tools: frozenset[str]) -> None:
        self._known_tools = registered_tools

    async def __call__(
        self,
        ctx: Any,
        call_next: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        start = time.perf_counter()
        status = "ok"
        try:
            return await call_next(ctx)
        except Exception:
            status = "error"
            raise
        finally:
            elapsed = time.perf_counter() - start
            method = _method_label(ctx.method)
            REQUESTS.labels(method=method, status=status).inc()
            REQUEST_DURATION.labels(method=method).observe(elapsed)
            if ctx.method == "tools/call":
                tool = _tool_label(ctx.params, self._known_tools)
                TOOL_CALLS.labels(tool=tool, outcome=status).inc()
                TOOL_DURATION.labels(tool=tool).observe(elapsed)
            elif ctx.method == "initialize":
                SESSIONS.inc()


def install_metrics(server: Any, registered_tools: list[str], mode: str) -> MetricsMiddleware:
    """Attach the metrics middleware and seed the registered-tools gauge.

    Registers on ``server._lowlevel_server.middleware`` — the same list the SDK
    appends its own `OpenTelemetryMiddleware` to, and the only per-tool hook the
    2.0 beta exposes (there is no public `add_middleware` yet). Cheap enough to
    install in both transports; only the hosted HTTP process actually serves the
    numbers (see `start_metrics_server`).
    """
    middleware = MetricsMiddleware(frozenset(registered_tools))
    server._lowlevel_server.middleware.append(middleware)
    REGISTERED_TOOLS.labels(mode=mode).set(len(registered_tools))
    return middleware


def start_metrics_server(port: int, host: str = "0.0.0.0") -> None:
    """Serve ``/metrics`` on its own port (default 9090), off the MCP port.

    Prometheus' own tiny WSGI server, so it stays independent of the MCP
    Starlette app on 8000 that the public ingress routes to.
    """
    start_http_server(port, addr=host)
    logger.info("prometheus metrics available on %s:%d/metrics", host, port)
