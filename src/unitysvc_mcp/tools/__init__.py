"""Tool modules, one per credential requirement.

The module a tool lives in *is* its access rule, and the `<domain>_` name
prefix states that rule to the model:

    market_*    no credentials            always registered
    docs_*      no credentials            always registered
    customer_*  UNITYSVC_API_KEY          registered when that key is set
    seller_*    UNITYSVC_SELLER_API_KEY   registered when that key is set

So `market_` and `docs_` are free, and `customer_`/`seller_` each need that
role's key. Two free prefixes rather than one because they answer different
questions — `market_` is the service *catalog* (what to buy, how to call it),
`docs_` is the platform *documentation* (concepts, primitives, glossary) — and
a shared prefix would misstate what a tool does. The rule stays mechanical
enough for an agent to apply without reading descriptions, and it keeps
same-verb pairs unambiguous — `customer_service_access` (how YOU use a service,
with your secrets/enrollments) versus `market_service_access` (how anyone uses
it), and a future `customer_get_usage` (your spend) versus `seller_get_usage`
(your revenue).
"""

from . import customer, docs, market, seller

__all__ = ["customer", "docs", "market", "seller"]
