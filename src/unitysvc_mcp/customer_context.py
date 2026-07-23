"""The caller's own context — a lazily-loaded, TTL-cached local snapshot.

In stdio mode with a customer key, the ``customer_*`` tools join the caller's
context onto the generic access plan: which secrets are set (names only —
values are write-only) and their live ``/e/<CODE>`` enrollment URLs. Fetching
that on every call would be two extra round-trips, so it is cached per process
and refreshed after a short TTL (a secret set or enrollment made mid-session
shows up within the window).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clients import CustomerApi
    from .settings import Settings


@dataclass(frozen=True)
class EnrollmentInfo:
    """One enrollment, reduced to what rendering needs."""

    service_id: str
    status: str
    code: str | None = None
    proxy_endpoint: str | None = None


@dataclass(frozen=True)
class CustomerContext:
    """A snapshot of the caller's own state (never any secret *values*)."""

    secret_names: frozenset[str]
    enrollments: tuple[EnrollmentInfo, ...]


class CustomerContextCache:
    """Lazily loads and TTL-caches the customer's :class:`CustomerContext`.

    Constructed only when a customer key is configured; the key is passed per
    call to the client, matching how the anonymous market reads work.
    """

    def __init__(self, customer_api: CustomerApi, settings: Settings) -> None:
        self._api = customer_api
        self._key = settings.api_key
        self._ttl = settings.customer_context_ttl_seconds
        self._cached: tuple[float, CustomerContext] | None = None

    async def get(self) -> CustomerContext:
        now = time.monotonic()
        if self._cached is not None and self._cached[0] > now:
            return self._cached[1]
        secret_names = await self._api.list_secret_names(api_key=self._key)
        enrollments = await self._api.list_enrollments(api_key=self._key)
        context = CustomerContext(secret_names=secret_names, enrollments=tuple(enrollments))
        self._cached = (now + self._ttl, context)
        return context
