"""The metrics middleware records the counters the dashboards will read.

These assert the observable contract (unitysvc-mcp-server#16): a tool call
increments `mcp_tool_calls_total` with the right `tool`/`outcome`, a failing
call is counted as `error` and the exception still propagates, an unregistered
tool name collapses to `unknown`, and `initialize` counts a session. Counters
are process-global singletons, so every test measures a *delta* rather than an
absolute value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from prometheus_client import REGISTRY

from unitysvc_mcp.metrics import MetricsMiddleware

KNOWN = frozenset({"market_list_services"})


@dataclass
class _Ctx:
    """The slice of ServerRequestContext the middleware reads."""

    method: str
    params: dict[str, Any] | None = None
    request_id: int | None = 1


def _sample(name: str, labels: dict[str, str]) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def _run(mw: MetricsMiddleware, ctx: _Ctx, result: Any = "ok", *, boom: bool = False) -> Any:
    async def call_next(_: Any) -> Any:
        if boom:
            raise RuntimeError("upstream failed")
        return result

    return await mw(ctx, call_next)


@pytest.mark.asyncio
async def test_successful_tool_call_is_counted() -> None:
    mw = MetricsMiddleware(KNOWN)
    labels = {"tool": "market_list_services", "outcome": "ok"}
    before = _sample("mcp_tool_calls_total", labels)

    out = await _run(mw, _Ctx("tools/call", {"name": "market_list_services"}), result="done")

    assert out == "done"
    assert _sample("mcp_tool_calls_total", labels) == before + 1


@pytest.mark.asyncio
async def test_failing_tool_call_counts_error_and_reraises() -> None:
    mw = MetricsMiddleware(KNOWN)
    labels = {"tool": "market_list_services", "outcome": "error"}
    before = _sample("mcp_tool_calls_total", labels)

    with pytest.raises(RuntimeError, match="upstream failed"):
        await _run(mw, _Ctx("tools/call", {"name": "market_list_services"}), boom=True)

    assert _sample("mcp_tool_calls_total", labels) == before + 1


@pytest.mark.asyncio
async def test_unregistered_tool_name_collapses_to_unknown() -> None:
    """A caller-supplied name outside the registered set must not mint a label."""
    mw = MetricsMiddleware(KNOWN)
    labels = {"tool": "unknown", "outcome": "ok"}
    before = _sample("mcp_tool_calls_total", labels)

    await _run(mw, _Ctx("tools/call", {"name": "totally_made_up"}))

    assert _sample("mcp_tool_calls_total", labels) == before + 1


@pytest.mark.asyncio
async def test_initialize_counts_a_session() -> None:
    mw = MetricsMiddleware(KNOWN)
    before = _sample("mcp_sessions_total", {})

    await _run(mw, _Ctx("initialize", {"protocolVersion": "2025-06-18"}))

    assert _sample("mcp_sessions_total", {}) == before + 1


@pytest.mark.asyncio
async def test_unknown_method_collapses_to_other() -> None:
    """A junk method reaches the middleware before lookup; bound the label."""
    mw = MetricsMiddleware(KNOWN)
    before = _sample("mcp_requests_total", {"method": "other", "status": "ok"})

    await _run(mw, _Ctx("carrier/pigeon"))

    assert _sample("mcp_requests_total", {"method": "other", "status": "ok"}) == before + 1


@pytest.mark.asyncio
async def test_request_total_records_method_and_status() -> None:
    mw = MetricsMiddleware(KNOWN)
    labels = {"method": "tools/list", "status": "ok"}
    before = _sample("mcp_requests_total", labels)

    await _run(mw, _Ctx("tools/list"))

    assert _sample("mcp_requests_total", labels) == before + 1
