"""One client per UnitySVC API, mirroring the tool modules.

`unitysvc-py` and `unitysvc-sellers` are separate packages hitting separate
hosts with separate keys, so wrapping both in a single adapter forced the role
into every method name (`list_seller_services`). Splitting them puts the role
in the object instead: `seller_api.list_services()`.

Named for the API each talks to rather than the SDK package, because the
market tools legitimately call the *customer* API with no key at all —
`customer_api.list_services(api_key=None)` says exactly that.
"""

from .customer import CustomerApi
from .seller import SellerApi

__all__ = ["CustomerApi", "SellerApi"]
