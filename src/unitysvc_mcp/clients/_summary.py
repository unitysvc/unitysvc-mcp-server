"""Shared mapping from an SDK model to our compact row.

Both SDKs wrap their generated models in attribute-proxying objects and use a
generated `UNSET` sentinel for unfilled optionals, so the coercion is the same
on either side — the one thing the two API clients genuinely share.
"""

from __future__ import annotations

from typing import Any

from ..models import ServiceSummary


def clean(value: Any) -> str | None:
    """Normalise None, the SDKs' `UNSET` sentinel, and UUIDs to str | None."""
    if value is None:
        return None
    if type(value).__name__ == "Unset":
        return None
    return str(value)


def service_summary(item: Any) -> ServiceSummary:
    """Build a ServiceSummary from either SDK's service model."""
    return ServiceSummary(
        id=clean(getattr(item, "id", None)),
        name=str(clean(getattr(item, "name", None)) or ""),
        display_name=clean(getattr(item, "display_name", None)),
        service_type=clean(getattr(item, "service_type", None)),
        gateway_type=clean(getattr(item, "gateway_type", None)),
        status=clean(getattr(item, "status", None)),
    )
