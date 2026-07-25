"""The platform primer injected into the MCP server's ``instructions``.

Instructions reach the client when the connector loads, before any tool call,
so this grounds every session in what UnitySVC is and which tool answers which
question — and, crucially, tells the model NOT to answer platform questions
from training data (this is a private platform its training does not cover).

Kept deliberately small: an overview and a map of the tools, not the docs. The
authoritative detail lives in the ``docs_*`` topics and is read on demand — one
source of truth (unitysvc/unitysvc#1662), never duplicated here.
"""

from __future__ import annotations

PRIMER = """\
# UnitySVC

UnitySVC is a marketplace for LLM and API services. Sellers publish
provider-backed services; customers call them through the UnitySVC gateway,
which handles authentication, routing, and billing.

This is a private platform your training data does NOT cover. Do not answer
questions about how UnitySVC works from prior knowledge — use the tools below,
and say so if none can answer.

## Tools

- **docs_list_topics** / **docs_get_topic** — authoritative documentation about
  the PLATFORM itself: concepts and primitives (channel, enrollment, secret,
  wallet, group, gateway), the billing model, and a `glossary` of terms. For
  any platform-concept question you are unsure of, read the topic instead of
  guessing. A topic's markdown cross-references other topics as links written
  `[channel](?topic=channel)`; to follow one, call `docs_get_topic` with that
  slug (here, `channel`), and keep following references until you have the
  detail you need.
- **market_list_services** / **market_service_access** / **market_service_example**
  — the catalog: which services are offered, a generic guide to signing up for
  and using one, and runnable code to call it.
- **customer_\\*** (needs a customer key) — the same, personalized to YOUR
  account: `customer_service_access` folds in your secrets and enrollments, and
  `customer_cli` / `customer_sdk` / `customer_endpoints` generate ready-to-run
  commands.
- **seller_\\*** (needs a seller key) — publishing and managing the services you
  offer.

Tools you don't see aren't available in this deployment: the hosted anonymous
server exposes only `market_*` and `docs_*`; `customer_*` / `seller_*` appear
when the matching key is configured.

## Using a service (customer)

1. Get a UnitySVC API key (`svcpass_...`) from the dashboard.
2. Browse with `market_list_services`; understand access with
   `market_service_access(service_id)` (or `customer_service_access` for your
   own account); get code with `market_service_example` / the `customer_*`
   command tools.
3. Set any required secrets or enroll as that guide says, then call the
   service's gateway base_url with your key as a Bearer token.

For the concepts behind any of this — channels, secrets, enrollment, wallets,
billing, groups — read the docs topics rather than guessing.
"""
