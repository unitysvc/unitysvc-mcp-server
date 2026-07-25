"""Tool modules, one per credential requirement.

The module a tool lives in *is* its access rule, and the `<domain>_` name
prefix states that rule to the model:

    market_*    no credentials            always registered
    platform_*  no credentials            always registered
    seller_*    UNITYSVC_SELLER_API_KEY   registered when that key is set

So a prefixed tool needs that role's key, and `market_` / `platform_` are free.
`market_*` is the catalog (what to buy and call); `platform_*` is the
documentation about the platform itself, which is public and api-key
independent, so it has no role split. That rule is mechanical enough for an
agent to apply without reading descriptions, and it keeps same-verb pairs
unambiguous — a future `customer_get_usage` (your spend) versus
`seller_get_usage` (your revenue).

A `customer_` module arrives with the customer-side tools in Phase 3 of
unitysvc#1492. It is not stubbed here: with no tools to register it would be
scaffolding that does nothing, gated on a key that unlocks nothing.
"""

from . import market, platform, seller

__all__ = ["market", "platform", "seller"]
