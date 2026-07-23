"""The seller's own context — a lazily-loaded, TTL-cached local snapshot.

In stdio mode with a seller key, the ``seller_*`` command tools (``seller_cli``
/ ``seller_sdk`` / ``seller_endpoints``) join the caller's own inventory —
which services they publish and each one's status — onto the generic command
generators, so a per-service render can suggest the next step (submit vs.
update/run-tests). Fetching that on every call would be an extra round-trip,
so it is cached per process and refreshed after a short TTL (mirrors
``customer_context.py``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clients import SellerApi
    from .settings import Settings


@dataclass(frozen=True)
class SellerServiceInfo:
    """One service the seller publishes, reduced to what rendering needs."""

    id: str | None
    name: str
    status: str | None


@dataclass(frozen=True)
class SellerContext:
    """A snapshot of the seller's own inventory."""

    services: tuple[SellerServiceInfo, ...]


class SellerContextCache:
    """Lazily loads and TTL-caches the seller's :class:`SellerContext`.

    Constructed only when a seller key is configured; the key is passed per
    call to the client, matching how the anonymous market reads work.
    """

    def __init__(self, seller_api: SellerApi, settings: Settings) -> None:
        self._api = seller_api
        self._key = settings.seller_api_key
        self._ttl = settings.seller_context_ttl_seconds
        self._cached: tuple[float, SellerContext] | None = None

    async def get(self) -> SellerContext:
        now = time.monotonic()
        if self._cached is not None and self._cached[0] > now:
            return self._cached[1]
        services = await self._api.list_service_infos(api_key=self._key)
        context = SellerContext(services=tuple(services))
        self._cached = (now + self._ttl, context)
        return context
