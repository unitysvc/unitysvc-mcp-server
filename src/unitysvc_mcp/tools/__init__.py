"""Tool modules, one per credential requirement.

The module a tool lives in *is* its access rule, and the `<domain>_` name
prefix states that rule to the model:

    market_*    no credentials            always registered
    docs_*      no credentials            always registered
    seller_*    UNITYSVC_SELLER_API_KEY   registered when that key is set

So `market_` and `docs_` are free and `seller_` needs that role's key. Two
free prefixes rather than one because they answer different questions —
`market_` is the service *catalog* (what to buy, how to call it), `docs_` is
the platform *documentation* (concepts, primitives, glossary) — and a shared
prefix would misstate what a tool does. The rule stays mechanical enough for
an agent to apply without reading descriptions, and it keeps same-verb pairs
unambiguous — a future `customer_get_usage` (your spend) versus
`seller_get_usage` (your revenue).

A `customer_` module arrives with the customer-side tools in Phase 3 of
unitysvc#1492. It is not stubbed here: with no tools to register it would be
scaffolding that does nothing, gated on a key that unlocks nothing.
"""

from . import docs, market, seller

__all__ = ["docs", "market", "seller"]
