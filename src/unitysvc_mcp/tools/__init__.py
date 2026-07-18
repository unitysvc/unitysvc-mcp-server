"""Tool modules, one per credential requirement.

The module a tool lives in *is* its access rule, and the `<domain>_` name
prefix states that rule to the model:

    market_*    no credentials            always registered
    seller_*    UNITYSVC_SELLER_API_KEY   registered when that key is set

So a prefixed tool needs that role's key, and `market_` is free. That rule is
mechanical enough for an agent to apply without reading descriptions, and it
keeps same-verb pairs unambiguous — a future `customer_get_usage` (your spend)
versus `seller_get_usage` (your revenue).

A `customer_` module arrives with the customer-side tools in Phase 3 of
unitysvc#1492. It is not stubbed here: with no tools to register it would be
scaffolding that does nothing, gated on a key that unlocks nothing.
"""

from . import market, seller

__all__ = ["market", "seller"]
