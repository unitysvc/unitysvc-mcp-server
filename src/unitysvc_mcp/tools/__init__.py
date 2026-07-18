"""Tool modules, one per credential requirement.

The module a tool lives in *is* its access rule, and the `<domain>_` name
prefix states that rule to the model:

    market_*    no credentials      always registered
    customer_*  UNITYSVC_API_KEY    registered when that key is set
    seller_*    UNITYSVC_SELLER_API_KEY   registered when that key is set

So a prefixed tool needs that role's key, and `market_` is free. That rule is
mechanical enough for an agent to apply without reading descriptions, and it
keeps same-verb pairs unambiguous — `customer_get_usage` (your spend) versus
`seller_get_usage` (your revenue).
"""

from . import customer, market, seller

__all__ = ["customer", "market", "seller"]
